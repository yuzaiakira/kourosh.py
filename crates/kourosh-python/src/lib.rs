//! Embedded CPython lifecycle and the first application function.
//!
//! The runtime is deliberately small: Python is initialized by PyO3, calls are
//! made while holding the GIL, and the caller is expected to run this type from
//! a worker (the bridge dispatcher does that for the native host).

use kourosh_bridge::{BridgeError, Method, ValidatedRequest};
use pyo3::prelude::*;
use pyo3::types::PyModule;
use serde_json::Value;
use std::fmt::{Display, Formatter};

const PYTHON_MODULE: &str = r#"
def greet(name):
    if not isinstance(name, str) or not name:
        raise ValueError("name must be a non-empty string")
    return {"message": f"Hello, {name}!"}
"#;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PythonError {
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
            message: error.to_string(),
        }
    }
}

pub struct PythonRuntime;

impl PythonRuntime {
    pub fn new() -> Result<Self, PythonError> {
        Python::with_gil(|py| {
            let _ = load_module(py)?;
            Ok(Self)
        })
    }

    pub fn greet(&self, name: &str) -> Result<Value, PythonError> {
        Python::with_gil(|py| {
            let module = load_module(py)?;
            let result = module.getattr("greet")?.call1((name,))?;
            let message: String = result.get_item("message")?.extract()?;
            Ok(serde_json::json!({"message": message}))
        })
    }

    pub fn call(&self, request: ValidatedRequest) -> Result<Value, BridgeError> {
        match request.method {
            Method::Greet => self.greet(&request.name).map_err(|_error| BridgeError {
                code: "python_error".to_owned(),
                message: "the Python handler raised an exception".to_owned(),
            }),
        }
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
}
