//! Embedded CPython lifecycle and the first application function.
//!
//! The runtime is deliberately small: Python is initialized by PyO3, calls are
//! made while holding the GIL, and the caller is expected to run this type from
//! a worker (the bridge dispatcher does that for the native host).

use kourosh_bridge::{
    BridgeError, CancellationToken as RustCancellationToken, Method, ValidatedRequest,
    PROTOCOL_VERSION,
};
use pyo3::prelude::*;
use pyo3::types::PyModule;
use serde_json::Value;
use std::fmt::{Display, Formatter};
use std::fs;
use std::path::Path;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

const PYTHON_MODULE: &str = r#"
def greet(name):
    if not isinstance(name, str) or not name:
        raise ValueError("name must be a non-empty string")
    return {"message": f"Hello, {name}!"}
"#;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PythonError {
    pub code: &'static str,
    pub message: String,
}

impl Display for PythonError {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> std::fmt::Result {
        formatter.write_str(&self.message)
    }
}

impl std::error::Error for PythonError {}

impl From<PyErr> for PythonError {
    fn from(error: PyErr) -> Self {
        Self {
            code: "python_error",
            message: error.to_string(),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RuntimeCapabilities {
    pub runtime_id: &'static str,
    pub runtime_version: &'static str,
    pub protocol_version: u8,
    pub capabilities: Vec<&'static str>,
    pub initialization_duration: Duration,
}

/// Python-visible view of the Rust cooperative cancellation signal. The
/// object is intentionally small and only exposes polling; it cannot stop a
/// Python thread or roll back handler side effects.
#[pyclass(name = "CancellationToken")]
#[derive(Clone)]
struct PythonCancellationToken {
    token: RustCancellationToken,
}

#[pymethods]
impl PythonCancellationToken {
    fn is_canceled(&self) -> bool {
        self.token.is_canceled()
    }

    fn is_cancelled(&self) -> bool {
        self.token.is_cancelled()
    }
}

/// Narrow runtime contract used by the native host. Future adapters may
/// implement the same request/response and lifecycle semantics without
/// exposing their interpreter details to the host.
pub trait RuntimeAdapter: Send + Sync {
    fn capabilities(&self) -> RuntimeCapabilities;
    fn methods(&self) -> &[String];
    fn dispatch(&self, request: ValidatedRequest) -> Result<Value, BridgeError>;
    fn dispatch_with_cancellation(
        &self,
        request: ValidatedRequest,
        cancellation: &RustCancellationToken,
    ) -> Result<Value, BridgeError> {
        let _ = cancellation;
        self.dispatch(request)
    }
    fn shutdown(&self);
    fn is_shutdown(&self) -> bool;
}

pub struct PythonRuntime {
    closed: AtomicBool,
    module: Py<PyModule>,
    app: Option<Py<PyAny>>,
    methods: Vec<String>,
    initialization_duration: Duration,
}

impl PythonRuntime {
    pub fn new() -> Result<Self, PythonError> {
        let started = Instant::now();
        let module = Python::with_gil(|py| load_module(py).map(Bound::unbind))?;
        Ok(Self {
            closed: AtomicBool::new(false),
            module,
            app: None,
            methods: vec!["greet".to_owned()],
            initialization_duration: started.elapsed(),
        })
    }

    /// Load a developer application's Python module. The module must expose
    /// an `app` object created by `kourosh.App`; its explicit registry is used
    /// as the native allowlist before any request reaches Python.
    pub fn new_with_app(path: &Path) -> Result<Self, PythonError> {
        let started = Instant::now();
        let source = fs::read_to_string(path).map_err(|error| PythonError {
            code: "app_load_error",
            message: format!("unable to read application source: {error}"),
        })?;
        let filename = path.to_string_lossy().into_owned();
        Python::with_gil(|py| {
            let search_paths = std::env::var_os("KOUROSH_PYTHON_PATH")
                .map(|value| std::env::split_paths(&value).collect::<Vec<_>>())
                .unwrap_or_else(
                    || vec![Path::new(env!("CARGO_MANIFEST_DIR")).join("../../python")],
                );
            let sys_path = py.import_bound("sys")?.getattr("path")?;
            for sdk_path in search_paths.into_iter().rev() {
                if sdk_path.is_dir() {
                    sys_path.call_method1("insert", (0, sdk_path.to_string_lossy().as_ref()))?;
                }
            }
            py.import_bound("os")?
                .getattr("environ")?
                .set_item("KOUROSH_HOST_APP", "1")?;
            let module = PyModule::from_code_bound(py, &source, &filename, "kourosh_user_app")?;
            let app = module.getattr("app")?;
            let methods: Vec<String> = app.getattr("_method_names")?.call0()?.extract()?;
            if methods.is_empty()
                || methods.len() > 256
                || methods.iter().any(|method| !valid_method_name(method))
            {
                return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    "application method registry contains an invalid name",
                ));
            }
            Ok(Self {
                closed: AtomicBool::new(false),
                module: module.unbind(),
                app: Some(app.unbind()),
                methods,
                initialization_duration: started.elapsed(),
            })
        })
        .map_err(PythonError::from)
    }

    pub fn greet(&self, name: &str) -> Result<Value, PythonError> {
        self.ensure_open()?;
        Python::with_gil(|py| {
            let module = self.module.bind(py);
            let result = module.getattr("greet")?.call1((name,))?;
            let message: String = result.get_item("message")?.extract()?;
            Ok(serde_json::json!({"message": message}))
        })
    }

    pub fn call(&self, request: ValidatedRequest) -> Result<Value, BridgeError> {
        self.call_with_cancellation(request, None)
    }

    pub fn call_with_cancellation(
        &self,
        request: ValidatedRequest,
        cancellation: Option<&RustCancellationToken>,
    ) -> Result<Value, BridgeError> {
        match request.method {
            Method::Greet => self.greet(&request.name).map_err(|error| BridgeError {
                code: error.code.to_owned(),
                message: if error.code == "runtime_shutdown" {
                    "the Python runtime is shut down".to_owned()
                } else {
                    "the Python handler raised an exception".to_owned()
                },
            }),
            Method::Custom(method) => self.call_app(&method, &request.args, cancellation),
        }
    }

    pub fn methods(&self) -> &[String] {
        &self.methods
    }

    pub fn capabilities(&self) -> RuntimeCapabilities {
        RuntimeCapabilities {
            runtime_id: "python",
            runtime_version: env!("CARGO_PKG_VERSION"),
            protocol_version: PROTOCOL_VERSION,
            capabilities: vec!["embedded-cpython", "rpc-dispatch", "graceful-shutdown"],
            initialization_duration: self.initialization_duration,
        }
    }

    fn call_app(
        &self,
        method: &str,
        args: &serde_json::Map<String, Value>,
        cancellation: Option<&RustCancellationToken>,
    ) -> Result<Value, BridgeError> {
        self.ensure_open().map_err(|error| BridgeError {
            code: error.code.to_owned(),
            message: error.message,
        })?;
        let app = self.app.as_ref().ok_or_else(|| BridgeError {
            code: "method_not_allowed".to_owned(),
            message: "the requested method is not allowlisted".to_owned(),
        })?;
        Python::with_gil(|py| {
            let args_json = serde_json::to_string(args).map_err(|error| BridgeError {
                code: "invalid_args".to_owned(),
                message: format!("arguments are not JSON compatible: {error}"),
            })?;
            let result = match cancellation {
                Some(token) => {
                    let python_token = Py::new(
                        py,
                        PythonCancellationToken {
                            token: token.clone(),
                        },
                    )
                    .map_err(|error| python_exception_to_bridge_error(py, error))?;
                    app.bind(py)
                        .call_method1("_dispatch", (method, args_json, python_token))
                        .map_err(|error| python_exception_to_bridge_error(py, error))?
                }
                None => app
                    .bind(py)
                    .call_method1("_dispatch", (method, args_json))
                    .map_err(|error| python_exception_to_bridge_error(py, error))?,
            };
            let json = py
                .import_bound("json")
                .map_err(|error| python_exception_to_bridge_error(py, error))?
                .call_method1("dumps", (result,))
                .map_err(|error| python_exception_to_bridge_error(py, error))?
                .extract::<String>()
                .map_err(|error| python_exception_to_bridge_error(py, error))?;
            serde_json::from_str(&json).map_err(|_| BridgeError {
                code: "python_error".to_owned(),
                message: "the Python handler returned a non-JSON value".to_owned(),
            })
        })
    }

    fn ensure_open(&self) -> Result<(), PythonError> {
        if self.closed.load(Ordering::Acquire) {
            Err(PythonError {
                code: "runtime_shutdown",
                message: "the Python runtime is shut down".to_owned(),
            })
        } else {
            Ok(())
        }
    }

    /// Mark this runtime closed. PyO3 owns the process-global interpreter and
    /// intentionally does not expose a safe `Py_Finalize` operation; dropping
    /// this handle releases application ownership without finalizing Python
    /// underneath other Rust/Python values.
    pub fn shutdown(&self) {
        self.closed.store(true, Ordering::Release);
    }

    pub fn is_shutdown(&self) -> bool {
        self.closed.load(Ordering::Acquire)
    }
}

impl RuntimeAdapter for PythonRuntime {
    fn capabilities(&self) -> RuntimeCapabilities {
        self.capabilities()
    }

    fn methods(&self) -> &[String] {
        self.methods()
    }

    fn dispatch(&self, request: ValidatedRequest) -> Result<Value, BridgeError> {
        self.call(request)
    }

    fn dispatch_with_cancellation(
        &self,
        request: ValidatedRequest,
        cancellation: &RustCancellationToken,
    ) -> Result<Value, BridgeError> {
        self.call_with_cancellation(request, Some(cancellation))
    }

    fn shutdown(&self) {
        self.shutdown();
    }

    fn is_shutdown(&self) -> bool {
        self.is_shutdown()
    }
}

impl Drop for PythonRuntime {
    fn drop(&mut self) {
        self.shutdown();
    }
}

fn load_module<'py>(py: Python<'py>) -> PyResult<Bound<'py, PyModule>> {
    PyModule::from_code_bound(py, PYTHON_MODULE, "kourosh_app.py", "kourosh_app")
}

fn python_exception_to_bridge_error(py: Python<'_>, error: PyErr) -> BridgeError {
    let value = error.value_bound(py);
    let code = value
        .getattr("code")
        .ok()
        .and_then(|value| value.extract::<String>().ok())
        .unwrap_or_else(|| "python_error".to_owned());
    let message = if code == "python_error" {
        "the Python handler raised an exception".to_owned()
    } else {
        value
            .getattr("message")
            .ok()
            .and_then(|value| value.extract::<String>().ok())
            .unwrap_or_else(|| "the Python request was rejected".to_owned())
    };
    BridgeError { code, message }
}

fn valid_method_name(method: &str) -> bool {
    let mut characters = method.chars();
    let Some(first) = characters.next() else {
        return false;
    };
    (first == '_' || first.is_ascii_alphabetic())
        && method.len() <= 64
        && characters.all(|character| character == '_' || character.is_ascii_alphanumeric())
}

#[cfg(test)]
mod tests {
    use super::*;
    use kourosh_bridge::Method;

    #[test]
    fn initializes_embedded_python_and_calls_greet() {
        let runtime = PythonRuntime::new().expect("Python should initialize");
        let capabilities = runtime.capabilities();
        assert_eq!(capabilities.runtime_id, "python");
        assert_eq!(
            capabilities.protocol_version,
            kourosh_bridge::PROTOCOL_VERSION
        );
        assert!(capabilities.capabilities.contains(&"embedded-cpython"));
        assert_eq!(
            runtime.greet("Akira").unwrap(),
            serde_json::json!({"message":"Hello, Akira!"})
        );
    }

    #[test]
    fn python_exception_is_not_returned_as_success() {
        let runtime = PythonRuntime::new().unwrap();
        let error = runtime.greet("").unwrap_err();
        assert_eq!(error.code, "python_error");
        assert!(error.message.contains("name must be a non-empty string"));
    }

    #[test]
    fn reports_application_initialization_failures_without_leaking_runtime_state() {
        let error = match PythonRuntime::new_with_app(std::path::Path::new(
            "/definitely/missing/main.py",
        )) {
            Ok(_) => panic!("missing application should not initialize"),
            Err(error) => error,
        };
        assert_eq!(error.code, "app_load_error");
    }

    #[test]
    fn bridge_dispatch_maps_python_errors_to_structured_errors() {
        let runtime = PythonRuntime::new().unwrap();
        let request = ValidatedRequest {
            id: "r1".to_owned(),
            method: Method::Greet,
            name: "Ada".to_owned(),
            args: serde_json::json!({"name":"Ada"})
                .as_object()
                .unwrap()
                .clone(),
        };
        assert_eq!(
            runtime.call(request).unwrap(),
            serde_json::json!({"message":"Hello, Ada!"})
        );

        let bad_request = ValidatedRequest {
            id: "r2".to_owned(),
            method: Method::Greet,
            name: String::new(),
            args: serde_json::json!({"name":""}).as_object().unwrap().clone(),
        };
        let error = runtime.call(bad_request).unwrap_err();
        assert_eq!(error.code, "python_error");
    }

    #[test]
    fn shutdown_rejects_new_python_calls_without_finalizing_process_python() {
        let runtime = PythonRuntime::new().unwrap();
        runtime.shutdown();
        assert!(runtime.is_shutdown());
        let error = runtime.greet("Ada").unwrap_err();
        assert_eq!(error.code, "runtime_shutdown");
        assert_eq!(
            runtime
                .call(ValidatedRequest {
                    id: "r3".to_owned(),
                    method: Method::Greet,
                    name: "Ada".to_owned(),
                    args: serde_json::json!({"name":"Ada"})
                        .as_object()
                        .unwrap()
                        .clone(),
                })
                .unwrap_err()
                .code,
            "runtime_shutdown"
        );
    }

    #[test]
    fn loads_python_sdk_app_and_dispatches_registered_method() {
        let directory = tempfile_directory();
        let path = directory.join("main.py");
        std::fs::write(
            &path,
            r#"
from kourosh import App
app = App(title="Test")
@app.expose
def add(left: int, right: int):
    return {"value": left + right}
app.run()
"#,
        )
        .unwrap();
        let runtime = PythonRuntime::new_with_app(&path).unwrap();
        assert_eq!(runtime.methods(), &["add"]);
        let request = ValidatedRequest {
            id: "r4".to_owned(),
            method: Method::Custom("add".to_owned()),
            name: String::new(),
            args: serde_json::json!({"left":2,"right":3})
                .as_object()
                .unwrap()
                .clone(),
        };
        assert_eq!(
            runtime.call(request).unwrap(),
            serde_json::json!({"value":5})
        );
        let _ = std::fs::remove_dir_all(directory);
    }

    #[test]
    fn generated_app_round_trips_through_the_bounded_rpc_dispatcher() {
        let directory = tempfile_directory();
        let path = directory.join("main.py");
        std::fs::write(
            &path,
            "from kourosh import App\napp = App(title='Test')\n@app.expose\ndef greet(name):\n    return {'message': 'Custom ' + name}\napp.run()\n",
        )
        .unwrap();
        let runtime = std::sync::Arc::new(PythonRuntime::new_with_app(&path).unwrap());
        let dispatcher = kourosh_bridge::AsyncDispatcher::new_with_methods(
            2,
            runtime.methods().to_vec(),
            move |request| runtime.call(request),
        );
        let raw = serde_json::json!({
            "id":"rpc-1",
            "method":"greet",
            "args":{"name":"Akira"}
        })
        .to_string();
        let response = dispatcher.dispatch_raw(
            &raw,
            kourosh_bridge::TRUSTED_ORIGIN,
            std::time::Duration::from_secs(1),
        );
        assert_eq!(response.id.as_deref(), Some("rpc-1"));
        assert_eq!(
            response.result,
            Some(serde_json::json!({"message":"Custom Akira"}))
        );
        let denied = dispatcher.dispatch_raw(
            &serde_json::json!({"id":"rpc-2","method":"shell","args":{}}).to_string(),
            kourosh_bridge::TRUSTED_ORIGIN,
            std::time::Duration::from_secs(1),
        );
        assert_eq!(denied.error.unwrap().code, "method_not_allowed");
        let _ = std::fs::remove_dir_all(directory);
    }

    #[test]
    fn timeout_token_reaches_a_cancellation_aware_python_handler() {
        let directory = tempfile_directory();
        let path = directory.join("main.py");
        std::fs::write(
            &path,
            r#"
import time
from kourosh import App
app = App(title="Cancellation")
@app.expose
def wait_for_cancel(cancellation):
    while not cancellation.is_cancelled():
        time.sleep(0.001)
    return {"cancelled": cancellation.is_canceled()}
app.run()
"#,
        )
        .unwrap();
        let runtime = std::sync::Arc::new(PythonRuntime::new_with_app(&path).unwrap());
        let runtime_for_dispatch = std::sync::Arc::clone(&runtime);
        let dispatcher = kourosh_bridge::AsyncDispatcher::new_with_methods_cancellable(
            2,
            runtime.methods().to_vec(),
            move |request, cancellation| {
                runtime_for_dispatch.dispatch_with_cancellation(request, &cancellation)
            },
        );
        let raw = serde_json::json!({
            "id": "cancel-python",
            "method": "wait_for_cancel",
            "args": {}
        })
        .to_string();
        let response = dispatcher.dispatch_raw(
            &raw,
            kourosh_bridge::TRUSTED_ORIGIN,
            std::time::Duration::from_millis(10),
        );
        assert_eq!(response.error.unwrap().code, "timeout");
        for _ in 0..100 {
            if dispatcher.metrics().active == 0 {
                break;
            }
            std::thread::sleep(std::time::Duration::from_millis(2));
        }
        assert_eq!(dispatcher.metrics().active, 0);
        assert_eq!(dispatcher.metrics().timeouts, 1);
        let _ = std::fs::remove_dir_all(directory);
    }

    fn tempfile_directory() -> std::path::PathBuf {
        let directory = std::env::temp_dir().join(format!(
            "kourosh-python-test-{}-{}",
            std::process::id(),
            std::thread::current().name().unwrap_or("worker")
        ));
        std::fs::create_dir_all(&directory).unwrap();
        directory
    }
}
