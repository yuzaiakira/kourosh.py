//! Security and transport primitives for the JavaScript-to-Python bridge.
//!
//! The native host owns origin checks and uses this crate before a message can
//! reach Python. The dispatcher uses a bounded queue and reports structured
//! errors; it never evaluates arbitrary Python or JavaScript supplied code.

use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::mpsc::{self, Receiver, SyncSender, TrySendError};
use std::sync::Arc;
use std::thread;
use std::time::Duration;

// WRY maps the custom `kourosh` protocol to this HTTPS origin on Windows.
pub const TRUSTED_ORIGIN: &str = "https://kourosh.app";
pub const MAX_REQUEST_BYTES: usize = 64 * 1024;
pub const MAX_REQUEST_ID_BYTES: usize = 128;
pub const MAX_NAME_BYTES: usize = 256;
pub const DEFAULT_QUEUE_CAPACITY: usize = 32;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Method {
    Greet,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ValidatedRequest {
    pub id: String,
    pub method: Method,
    pub name: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct BridgeError {
    pub code: String,
    pub message: String,
}

impl BridgeError {
    fn new(code: &str, message: impl Into<String>) -> Self {
        Self {
            code: code.to_owned(),
            message: message.into(),
        }
    }

    pub fn invalid_origin() -> Self {
        Self::new("invalid_origin", "the request origin is not trusted")
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct RpcResponse {
    pub id: Option<String>,
    pub ok: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub result: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<BridgeError>,
}

impl RpcResponse {
    pub fn success(id: String, result: Value) -> Self {
        Self {
            id: Some(id),
            ok: true,
            result: Some(result),
            error: None,
        }
    }

    pub fn failure(id: Option<String>, error: BridgeError) -> Self {
        Self {
            id,
            ok: false,
            result: None,
            error: Some(error),
        }
    }

    pub fn to_json(&self) -> String {
        serde_json::to_string(self).expect("RpcResponse contains only serializable fields")
    }
}

/// Validate a raw message before it is accepted by the bridge queue.
pub fn parse_request(raw: &str, origin: &str) -> Result<ValidatedRequest, BridgeError> {
    if origin != TRUSTED_ORIGIN {
        return Err(BridgeError::invalid_origin());
    }
    if raw.len() > MAX_REQUEST_BYTES {
        return Err(BridgeError::new(
            "request_too_large",
            format!("request exceeds the {} byte limit", MAX_REQUEST_BYTES),
        ));
    }

    let value: Value = serde_json::from_str(raw)
        .map_err(|_| BridgeError::new("malformed_request", "request must be valid JSON"))?;
    let object = value
        .as_object()
        .ok_or_else(|| BridgeError::new("malformed_request", "request must be a JSON object"))?;

    let id = object
        .get("id")
        .and_then(Value::as_str)
        .filter(|id| !id.is_empty() && id.len() <= MAX_REQUEST_ID_BYTES)
        .ok_or_else(|| {
            BridgeError::new(
                "invalid_request_id",
                format!("id must be a non-empty string of at most {MAX_REQUEST_ID_BYTES} bytes"),
            )
        })?
        .to_owned();

    let method = object
        .get("method")
        .and_then(Value::as_str)
        .ok_or_else(|| BridgeError::new("invalid_method", "method must be a string"))?;
    if method != "greet" {
        return Err(BridgeError::new(
            "method_not_allowed",
            "the requested method is not allowlisted",
        ));
    }

    let args = object
        .get("args")
        .and_then(Value::as_object)
        .ok_or_else(|| BridgeError::new("invalid_args", "args must be a JSON object"))?;
    if args.len() != 1 || !args.contains_key("name") {
        return Err(BridgeError::new(
            "invalid_args",
            "greet accepts exactly one argument: name",
        ));
    }
    let name = args
        .get("name")
        .and_then(Value::as_str)
        .filter(|name| !name.is_empty() && name.len() <= MAX_NAME_BYTES)
        .ok_or_else(|| {
            BridgeError::new(
                "invalid_args",
                format!("name must be a non-empty string of at most {MAX_NAME_BYTES} bytes"),
            )
        })?
        .to_owned();

    Ok(ValidatedRequest {
        id,
        method: Method::Greet,
        name,
    })
}

fn request_id(raw: &str) -> Option<String> {
    serde_json::from_str::<Value>(raw)
        .ok()
        .and_then(|value| value.get("id").and_then(Value::as_str).map(str::to_owned))
}

type Handler = dyn Fn(ValidatedRequest) -> Result<Value, BridgeError> + Send + Sync + 'static;

struct Job {
    request: ValidatedRequest,
    timeout: Duration,
    response: SyncSender<RpcResponse>,
}

/// A bounded asynchronous dispatcher. The host submits work quickly from the
/// UI/IPC callback and receives a one-shot channel for the response.
pub struct AsyncDispatcher {
    sender: SyncSender<Job>,
    active: Arc<AtomicUsize>,
    max_inflight: usize,
}

impl AsyncDispatcher {
    pub fn new<F>(queue_capacity: usize, handler: F) -> Self
    where
        F: Fn(ValidatedRequest) -> Result<Value, BridgeError> + Send + Sync + 'static,
    {
        let queue_capacity = queue_capacity.max(1);
        let (sender, receiver) = mpsc::sync_channel(queue_capacity);
        let active = Arc::new(AtomicUsize::new(0));
        let worker_handler: Arc<Handler> = Arc::new(handler);
        let worker_active = Arc::clone(&active);

        thread::Builder::new()
            .name("kourosh-bridge".to_owned())
            .spawn(move || worker_loop(receiver, worker_handler, worker_active))
            .expect("bridge worker thread must start");

        Self {
            sender,
            active,
            max_inflight: queue_capacity,
        }
    }

    pub fn submit(
        &self,
        raw: &str,
        origin: &str,
        timeout: Duration,
    ) -> Result<Receiver<RpcResponse>, BridgeError> {
        let request = parse_request(raw, origin)?;
        if !self.reserve_inflight_slot() {
            return Err(BridgeError::new(
                "busy",
                "the bridge has reached its in-flight request limit",
            ));
        }

        let id = request.id.clone();
        let (response_tx, response_rx) = mpsc::sync_channel(1);
        let job = Job {
            request,
            timeout,
            response: response_tx,
        };
        match self.sender.try_send(job) {
            Ok(()) => Ok(response_rx),
            Err(TrySendError::Full(_)) => {
                self.active.fetch_sub(1, Ordering::AcqRel);
                Err(BridgeError::new("busy", "the bridge request queue is full"))
            }
            Err(TrySendError::Disconnected(_)) => {
                self.active.fetch_sub(1, Ordering::AcqRel);
                Err(BridgeError::new(
                    "shutdown",
                    format!("request {id} was not accepted"),
                ))
            }
        }
    }

    fn reserve_inflight_slot(&self) -> bool {
        let mut current = self.active.load(Ordering::Acquire);
        loop {
            if current >= self.max_inflight {
                return false;
            }
            match self.active.compare_exchange_weak(
                current,
                current + 1,
                Ordering::AcqRel,
                Ordering::Acquire,
            ) {
                Ok(_) => return true,
                Err(updated) => current = updated,
            }
        }
    }

    /// Synchronous convenience method used by the host's IPC callback and
    /// integration tests. It still executes the handler on the bridge worker.
    pub fn dispatch_raw(&self, raw: &str, origin: &str, timeout: Duration) -> RpcResponse {
        let id = request_id(raw);
        match self.submit(raw, origin, timeout) {
            Ok(receiver) => receiver.recv().unwrap_or_else(|_| {
                RpcResponse::failure(id, BridgeError::new("shutdown", "bridge worker stopped"))
            }),
            Err(error) => RpcResponse::failure(id, error),
        }
    }
}

fn worker_loop(receiver: Receiver<Job>, handler: Arc<Handler>, active: Arc<AtomicUsize>) {
    while let Ok(job) = receiver.recv() {
        let (result_tx, result_rx) = mpsc::sync_channel(1);
        let request = job.request.clone();
        let handler = Arc::clone(&handler);
        let active_for_job = Arc::clone(&active);
        thread::spawn(move || {
            let result = handler(request);
            let _ = result_tx.send(result);
            active_for_job.fetch_sub(1, Ordering::AcqRel);
        });

        let response = match result_rx.recv_timeout(job.timeout) {
            Ok(Ok(result)) => RpcResponse::success(job.request.id, result),
            Ok(Err(error)) => RpcResponse::failure(Some(job.request.id), error),
            Err(mpsc::RecvTimeoutError::Timeout) => RpcResponse::failure(
                Some(job.request.id),
                BridgeError::new("timeout", "the Python call exceeded its timeout"),
            ),
            Err(mpsc::RecvTimeoutError::Disconnected) => RpcResponse::failure(
                Some(job.request.id),
                BridgeError::new("handler_stopped", "the bridge handler stopped"),
            ),
        };
        let _ = job.response.send(response);
    }
}

pub fn greet_result(name: &str) -> Value {
    let mut result = Map::new();
    result.insert(
        "message".to_owned(),
        Value::String(format!("Hello, {name}!")),
    );
    Value::Object(result)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn request(id: &str, name: &str) -> String {
        serde_json::json!({"id": id, "method": "greet", "args": {"name": name}}).to_string()
    }

    #[test]
    fn accepts_valid_greet_request() {
        let parsed = parse_request(&request("r1", "Akira"), TRUSTED_ORIGIN).unwrap();
        assert_eq!(parsed.id, "r1");
        assert_eq!(parsed.method, Method::Greet);
        assert_eq!(parsed.name, "Akira");
    }

    #[test]
    fn rejects_untrusted_origin_and_unknown_method() {
        let error = parse_request(&request("r1", "Akira"), "https://evil.example").unwrap_err();
        assert_eq!(error.code, "invalid_origin");

        let raw = serde_json::json!({"id":"r2","method":"read_file","args":{}}).to_string();
        let error = parse_request(&raw, TRUSTED_ORIGIN).unwrap_err();
        assert_eq!(error.code, "method_not_allowed");
    }

    #[test]
    fn rejects_malformed_and_invalid_arguments() {
        assert_eq!(
            parse_request("{}", TRUSTED_ORIGIN).unwrap_err().code,
            "invalid_request_id"
        );
        assert_eq!(
            parse_request("not json", TRUSTED_ORIGIN).unwrap_err().code,
            "malformed_request"
        );
        let bad = serde_json::json!({"id":"r3","method":"greet","args":{"name":7}}).to_string();
        assert_eq!(
            parse_request(&bad, TRUSTED_ORIGIN).unwrap_err().code,
            "invalid_args"
        );
    }

    #[test]
    fn rejects_oversized_requests() {
        let raw = "x".repeat(MAX_REQUEST_BYTES + 1);
        assert_eq!(
            parse_request(&raw, TRUSTED_ORIGIN).unwrap_err().code,
            "request_too_large"
        );
    }

    #[test]
    fn returns_structured_success_and_error_responses() {
        let dispatcher = AsyncDispatcher::new(2, |request| Ok(greet_result(&request.name)));
        let success = dispatcher.dispatch_raw(
            &request("r4", "Ada"),
            TRUSTED_ORIGIN,
            Duration::from_secs(1),
        );
        assert!(success.ok);
        assert_eq!(success.result.unwrap()["message"], "Hello, Ada!");
        let denied = dispatcher.dispatch_raw(
            &serde_json::json!({"id":"r5","method":"nope","args":{}}).to_string(),
            TRUSTED_ORIGIN,
            Duration::from_secs(1),
        );
        assert!(!denied.ok);
        assert_eq!(denied.error.unwrap().code, "method_not_allowed");
    }

    #[test]
    fn enforces_timeout_and_inflight_bound() {
        let dispatcher = AsyncDispatcher::new(1, |_request| {
            thread::sleep(Duration::from_millis(50));
            Ok(greet_result("slow"))
        });
        let first = dispatcher
            .submit(
                &request("r6", "slow"),
                TRUSTED_ORIGIN,
                Duration::from_millis(5),
            )
            .unwrap();
        let busy = dispatcher.submit(
            &request("r7", "busy"),
            TRUSTED_ORIGIN,
            Duration::from_secs(1),
        );
        assert_eq!(busy.unwrap_err().code, "busy");
        assert_eq!(first.recv().unwrap().error.unwrap().code, "timeout");
    }
}
