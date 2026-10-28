//! Embedded CPython lifecycle and the first application function.
//!
//! The runtime is deliberately small: Python is initialized by PyO3, calls are
//! made while holding the GIL, and the caller is expected to run this type from
//! a worker (the bridge dispatcher does that for the native host).

use kourosh_bridge::{BridgeError, Method, ValidatedRequest};
use pyo3::prelude::*;
use pyo3::sync::GILOnceCell;
use pyo3::types::PyModule;
use serde_json::Value;
use std::fmt::{Display, Formatter};
use std::sync::atomic::{AtomicBool, Ordering};

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

pub struct PythonRuntime {
    closed: AtomicBool,
    module: GILOnceCell<Py<PyModule>>,
}

impl PythonRuntime {
    pub fn new() -> Result<Self, PythonError> {
        let runtime = Self {
            closed: AtomicBool::new(false),
            module: GILOnceCell::new(),
        };
        Python::with_gil(|py| {
            runtime
                .module
                .get_or_try_init(py, || load_module(py).map(Bound::unbind))?;
            Ok(runtime)
        })
    }

    pub fn greet(&self, name: &str) -> Result<Value, PythonError> {
        self.ensure_open()?;
        Python::with_gil(|py| {
            let module = self
                .module
                .get(py)
                .expect("PythonRuntime initializes its module before returning");
            let module = module.bind(py);
            let result = module.getattr("greet")?.call1((name,))?;
            let message: String = result.get_item("message")?.extract()?;
            Ok(serde_json::json!({"message": message}))
        })
    }

    pub fn call(&self, request: ValidatedRequest) -> Result<Value, BridgeError> {
        match request.method {
            Method::Greet => self.greet(&request.name).map_err(|error| BridgeError {
                code: error.code.to_owned(),
                message: if error.code == "runtime_shutdown" {
                    "the Python runtime is shut down".to_owned()
                } else {
                    "the Python handler raised an exception".to_owned()
                },
            }),
        }
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

impl Drop for PythonRuntime {
    fn drop(&mut self) {
        self.shutdown();
    }
}

fn load_module<'py>(py: Python<'py>) -> PyResult<Bound<'py, PyModule>> {
    PyModule::from_code_bound(py, PYTHON_MODULE, "kourosh_app.py", "kourosh_app")
}

#[cfg(test)]
mod tests {
    use super::*;
    use kourosh_bridge::Method;

    #[test]
    fn initializes_embedded_python_and_calls_greet() {
        let runtime = PythonRuntime::new().expect("Python should initialize");
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
    fn bridge_dispatch_maps_python_errors_to_structured_errors() {
        let runtime = PythonRuntime::new().unwrap();
        let request = ValidatedRequest {
            id: "r1".to_owned(),
            method: Method::Greet,
            name: "Ada".to_owned(),
        };
        assert_eq!(
            runtime.call(request).unwrap(),
            serde_json::json!({"message":"Hello, Ada!"})
        );

        let bad_request = ValidatedRequest {
            id: "r2".to_owned(),
            method: Method::Greet,
            name: String::new(),
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
                })
                .unwrap_err()
                .code,
            "runtime_shutdown"
        );
    }
}
