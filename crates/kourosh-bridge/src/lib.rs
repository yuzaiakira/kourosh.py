//! Security and transport primitives for the JavaScript-to-Python bridge.
//!
//! The native host owns origin checks and uses this crate before a message can
//! reach Python. The dispatcher uses a bounded queue and reports structured
//! errors; it never evaluates arbitrary Python or JavaScript supplied code.

use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::mpsc::{self, Receiver, SyncSender, TrySendError};
use std::sync::{Arc, OnceLock};
use std::thread;
use std::time::{Duration, Instant};

// WRY maps the custom `kourosh` protocol to this HTTPS origin on Windows.
pub const TRUSTED_ORIGIN: &str = "https://kourosh.app";
pub const PROTOCOL_VERSION: u8 = 1;
pub const MAX_REQUEST_BYTES: usize = 64 * 1024;
pub const MAX_REQUEST_ID_BYTES: usize = 128;
pub const MAX_NAME_BYTES: usize = 256;
pub const DEFAULT_QUEUE_CAPACITY: usize = 32;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Method {
    Greet,
    Custom(String),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ValidatedRequest {
    pub id: String,
    pub method: Method,
    pub name: String,
    pub args: Map<String, Value>,
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
    pub protocol: u8,
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
            protocol: PROTOCOL_VERSION,
            id: Some(id),
            ok: true,
            result: Some(result),
            error: None,
        }
    }

    pub fn failure(id: Option<String>, error: BridgeError) -> Self {
        Self {
            protocol: PROTOCOL_VERSION,
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

/// Validate a raw message against the built-in `greet` allowlist.
pub fn parse_request(raw: &str, origin: &str) -> Result<ValidatedRequest, BridgeError> {
    static GREET: OnceLock<Vec<String>> = OnceLock::new();
    parse_request_with_methods_internal(
        raw,
        origin,
        GREET.get_or_init(|| vec!["greet".to_owned()]),
        true,
    )
}

/// Validate a raw message against an explicit method allowlist. The host owns
/// this list and obtains it from the Python SDK's `@app.expose` registry.
pub fn parse_request_with_methods(
    raw: &str,
    origin: &str,
    allowed_methods: &[String],
) -> Result<ValidatedRequest, BridgeError> {
    parse_request_with_methods_internal(raw, origin, allowed_methods, false)
}

fn parse_request_with_methods_internal(
    raw: &str,
    origin: &str,
    allowed_methods: &[String],
    builtin_greet: bool,
) -> Result<ValidatedRequest, BridgeError> {
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

    if let Some(protocol) = object.get("protocol") {
        if protocol.as_u64() != Some(u64::from(PROTOCOL_VERSION)) {
            return Err(BridgeError::new(
                "unsupported_protocol",
                format!("bridge protocol version must be {PROTOCOL_VERSION}"),
            ));
        }
    }

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
        .filter(|method| !method.is_empty() && method.len() <= MAX_NAME_BYTES)
        .ok_or_else(|| BridgeError::new("invalid_method", "method must be a non-empty string"))?;
    if !allowed_methods.iter().any(|allowed| allowed == method) {
        return Err(BridgeError::new(
            "method_not_allowed",
            "the requested method is not allowlisted",
        ));
    }

    let args = object
        .get("args")
        .and_then(Value::as_object)
        .ok_or_else(|| BridgeError::new("invalid_args", "args must be a JSON object"))?;
    let name = if method == "greet" {
        if args.len() != 1 || !args.contains_key("name") {
            return Err(BridgeError::new(
                "invalid_args",
                "greet accepts exactly one argument: name",
            ));
        }
        args.get("name")
            .and_then(Value::as_str)
            .filter(|name| !name.is_empty() && name.len() <= MAX_NAME_BYTES)
            .ok_or_else(|| {
                BridgeError::new(
                    "invalid_args",
                    format!("name must be a non-empty string of at most {MAX_NAME_BYTES} bytes"),
                )
            })?
            .to_owned()
    } else {
        String::new()
    };

    Ok(ValidatedRequest {
        id,
        method: if builtin_greet && method == "greet" {
            Method::Greet
        } else {
            Method::Custom(method.to_owned())
        },
        name,
        args: args.clone(),
    })
}

fn request_id(raw: &str) -> Option<String> {
    serde_json::from_str::<Value>(raw)
        .ok()
        .and_then(|value| value.get("id").and_then(Value::as_str).map(str::to_owned))
}

/// Build an error response while retaining a syntactically recoverable request
/// ID. This lets the browser reject a pending Promise even when validation
/// fails before a request can enter the worker queue.
pub fn response_for_error(raw: &str, error: BridgeError) -> RpcResponse {
    RpcResponse::failure(request_id(raw), error)
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
    closed: Arc<AtomicBool>,
    allowed_methods: Arc<Vec<String>>,
    builtin_greet: bool,
    max_inflight: usize,
}

impl AsyncDispatcher {
    pub fn new<F>(queue_capacity: usize, handler: F) -> Self
    where
        F: Fn(ValidatedRequest) -> Result<Value, BridgeError> + Send + Sync + 'static,
    {
        Self::new_with_methods_internal(queue_capacity, vec!["greet".to_owned()], true, handler)
    }

    pub fn new_with_methods<F>(
        queue_capacity: usize,
        allowed_methods: Vec<String>,
        handler: F,
    ) -> Self
    where
        F: Fn(ValidatedRequest) -> Result<Value, BridgeError> + Send + Sync + 'static,
    {
        Self::new_with_methods_internal(queue_capacity, allowed_methods, false, handler)
    }

    fn new_with_methods_internal<F>(
        queue_capacity: usize,
        allowed_methods: Vec<String>,
        builtin_greet: bool,
        handler: F,
    ) -> Self
    where
        F: Fn(ValidatedRequest) -> Result<Value, BridgeError> + Send + Sync + 'static,
    {
        let queue_capacity = queue_capacity.max(1);
        let allowed_methods = Arc::new(allowed_methods);
        let (sender, receiver) = mpsc::sync_channel(queue_capacity);
        let active = Arc::new(AtomicUsize::new(0));
        let closed = Arc::new(AtomicBool::new(false));
        let worker_handler: Arc<Handler> = Arc::new(handler);
        let worker_active = Arc::clone(&active);
        let worker_closed = Arc::clone(&closed);

        thread::Builder::new()
            .name("kourosh-bridge".to_owned())
            .spawn(move || worker_loop(receiver, worker_handler, worker_active, worker_closed))
            .expect("bridge worker thread must start");

        Self {
            sender,
            active,
            closed,
            allowed_methods,
            builtin_greet,
            max_inflight: queue_capacity,
        }
    }

    pub fn submit(
        &self,
        raw: &str,
        origin: &str,
        timeout: Duration,
    ) -> Result<Receiver<RpcResponse>, BridgeError> {
        if self.closed.load(Ordering::Acquire) {
            return Err(BridgeError::new("shutdown", "the bridge is shut down"));
        }
        self.submit_with_timeout(raw, origin, timeout)
    }

    fn submit_with_timeout(
        &self,
        raw: &str,
        origin: &str,
        timeout: Duration,
    ) -> Result<Receiver<RpcResponse>, BridgeError> {
        if self.closed.load(Ordering::Acquire) {
            return Err(BridgeError::new("shutdown", "the bridge is shut down"));
        }
        let request = parse_request_with_methods_internal(
            raw,
            origin,
            &self.allowed_methods,
            self.builtin_greet,
        )?;
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
            if self.closed.load(Ordering::Acquire) || current >= self.max_inflight {
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

    /// Stop accepting work. Queued requests receive a structured shutdown
    /// response, and the current handler is allowed to finish cooperatively.
    pub fn shutdown(&self) {
        self.closed.store(true, Ordering::Release);
    }

    pub fn is_shutdown(&self) -> bool {
        self.closed.load(Ordering::Acquire)
    }

    /// Synchronous convenience method for integration tests and non-UI
    /// callers. It still executes the handler on the bridge worker.
    pub fn dispatch_raw(&self, raw: &str, origin: &str, timeout: Duration) -> RpcResponse {
        let id = request_id(raw);
        match self.submit(raw, origin, timeout) {
            Ok(receiver) => receiver.recv().unwrap_or_else(|_| {
                RpcResponse::failure(id, BridgeError::new("shutdown", "bridge worker stopped"))
            }),
            Err(error) => RpcResponse::failure(id, error),
        }
    }

    pub fn allowed_methods(&self) -> &[String] {
        self.allowed_methods.as_slice()
    }
}

impl Drop for AsyncDispatcher {
    fn drop(&mut self) {
        self.shutdown();
    }
}

fn worker_loop(
    receiver: Receiver<Job>,
    handler: Arc<Handler>,
    active: Arc<AtomicUsize>,
    closed: Arc<AtomicBool>,
) {
    loop {
        let job = match receiver.recv_timeout(Duration::from_millis(50)) {
            Ok(job) => job,
            Err(mpsc::RecvTimeoutError::Timeout) if closed.load(Ordering::Acquire) => {
                reject_queued(&receiver, &active);
                break;
            }
            Err(mpsc::RecvTimeoutError::Timeout) => continue,
            Err(mpsc::RecvTimeoutError::Disconnected) => break,
        };
        if closed.load(Ordering::Acquire) {
            active.fetch_sub(1, Ordering::AcqRel);
            let _ = job.response.send(RpcResponse::failure(
                Some(job.request.id),
                BridgeError::new("shutdown", "the bridge is shut down"),
            ));
            continue;
        }

        let (result_tx, result_rx) = mpsc::sync_channel(1);
        let request = job.request.clone();
        let handler = Arc::clone(&handler);
        let active_for_job = Arc::clone(&active);
        thread::spawn(move || {
            let result = handler(request);
            let _ = result_tx.send(result);
            active_for_job.fetch_sub(1, Ordering::AcqRel);
        });

        let response = wait_for_result(result_rx, job.request.id, job.timeout, &closed);
        let _ = job.response.send(response);
    }
}

fn reject_queued(receiver: &Receiver<Job>, active: &AtomicUsize) {
    while let Ok(job) = receiver.try_recv() {
        active.fetch_sub(1, Ordering::AcqRel);
        let _ = job.response.send(RpcResponse::failure(
            Some(job.request.id),
            BridgeError::new("shutdown", "the bridge is shut down"),
        ));
    }
}

fn wait_for_result(
    receiver: Receiver<Result<Value, BridgeError>>,
    id: String,
    timeout: Duration,
    closed: &AtomicBool,
) -> RpcResponse {
    let deadline = Instant::now() + timeout;
    loop {
        if closed.load(Ordering::Acquire) {
            return RpcResponse::failure(
                Some(id),
                BridgeError::new("shutdown", "the bridge is shut down"),
            );
        }
        let remaining = deadline.saturating_duration_since(Instant::now());
        if remaining.is_zero() {
            return RpcResponse::failure(
                Some(id),
                BridgeError::new("timeout", "the Python call exceeded its timeout"),
            );
        }
        match receiver.recv_timeout(remaining.min(Duration::from_millis(50))) {
            Ok(Ok(result)) => return RpcResponse::success(id, result),
            Ok(Err(error)) => return RpcResponse::failure(Some(id), error),
            Err(mpsc::RecvTimeoutError::Timeout) => continue,
            Err(mpsc::RecvTimeoutError::Disconnected) => {
                return RpcResponse::failure(
                    Some(id),
                    BridgeError::new("handler_stopped", "the bridge handler stopped"),
                )
            }
        }
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
        assert_eq!(parsed.args["name"], "Akira");
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
    fn accepts_legacy_requests_and_rejects_unknown_protocol_versions() {
        assert!(parse_request(&request("legacy", "Ada"), TRUSTED_ORIGIN).is_ok());
        let incompatible = serde_json::json!({
            "protocol": PROTOCOL_VERSION + 1,
            "id": "future",
            "method": "greet",
            "args": {"name": "Ada"}
        })
        .to_string();
        assert_eq!(
            parse_request(&incompatible, TRUSTED_ORIGIN)
                .unwrap_err()
                .code,
            "unsupported_protocol"
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

    #[test]
    fn handles_concurrent_invocations_without_crossing_responses() {
        let dispatcher = Arc::new(AsyncDispatcher::new(32, |request| {
            thread::sleep(Duration::from_millis(1));
            Ok(greet_result(&request.name))
        }));
        let mut workers = Vec::new();
        for index in 0..16 {
            let dispatcher = Arc::clone(&dispatcher);
            workers.push(thread::spawn(move || {
                let id = format!("concurrent-{index}");
                let raw = request(&id, &format!("Name {index}"));
                dispatcher.dispatch_raw(&raw, TRUSTED_ORIGIN, Duration::from_secs(1))
            }));
        }
        for (index, worker) in workers.into_iter().enumerate() {
            let response = worker.join().unwrap();
            assert!(response.ok);
            assert_eq!(
                response.id.as_deref(),
                Some(format!("concurrent-{index}").as_str())
            );
            assert_eq!(
                response.result.unwrap()["message"],
                format!("Hello, Name {index}!")
            );
        }
    }

    #[test]
    fn preserves_ids_for_validation_errors_and_rejects_after_shutdown() {
        let dispatcher = AsyncDispatcher::new(2, |request| Ok(greet_result(&request.name)));
        let malformed = serde_json::json!({"id":"bad-1","method":"greet","args":{}}).to_string();
        let response = dispatcher.dispatch_raw(&malformed, TRUSTED_ORIGIN, Duration::from_secs(1));
        assert_eq!(response.id.as_deref(), Some("bad-1"));
        assert_eq!(response.error.unwrap().code, "invalid_args");

        dispatcher.shutdown();
        assert!(dispatcher.is_shutdown());
        let response = dispatcher.dispatch_raw(
            &request("after-close", "Ada"),
            TRUSTED_ORIGIN,
            Duration::from_secs(1),
        );
        assert_eq!(response.id.as_deref(), Some("after-close"));
        assert_eq!(response.error.unwrap().code, "shutdown");
    }

    #[test]
    fn shutdown_rejects_queued_work_and_wakes_the_worker() {
        let dispatcher = AsyncDispatcher::new(2, |_request| {
            thread::sleep(Duration::from_millis(200));
            Ok(greet_result("late"))
        });
        let first = dispatcher
            .submit(
                &request("queued-1", "Ada"),
                TRUSTED_ORIGIN,
                Duration::from_secs(1),
            )
            .unwrap();
        let second = dispatcher
            .submit(
                &request("queued-2", "Ada"),
                TRUSTED_ORIGIN,
                Duration::from_secs(1),
            )
            .unwrap();
        thread::sleep(Duration::from_millis(10));
        dispatcher.shutdown();
        assert_eq!(first.recv().unwrap().error.unwrap().code, "shutdown");
        assert_eq!(second.recv().unwrap().error.unwrap().code, "shutdown");
    }

    #[test]
    fn accepts_only_explicit_custom_methods() {
        let allowed = vec!["add".to_owned()];
        let raw = serde_json::json!({
            "id": "custom-1",
            "method": "add",
            "args": {"left": 2, "right": 3}
        })
        .to_string();
        let parsed = parse_request_with_methods(&raw, TRUSTED_ORIGIN, &allowed).unwrap();
        assert_eq!(parsed.method, Method::Custom("add".to_owned()));
        assert_eq!(parsed.args["left"], 2);

        let denied = serde_json::json!({"id":"custom-2","method":"shell","args":{}}).to_string();
        assert_eq!(
            parse_request_with_methods(&denied, TRUSTED_ORIGIN, &allowed)
                .unwrap_err()
                .code,
            "method_not_allowed"
        );

        let custom_greet = serde_json::json!({
            "id":"custom-greet",
            "method":"greet",
            "args":{"name":"App"}
        })
        .to_string();
        let custom_methods = vec!["greet".to_owned()];
        assert_eq!(
            parse_request_with_methods(&custom_greet, TRUSTED_ORIGIN, &custom_methods)
                .unwrap()
                .method,
            Method::Custom("greet".to_owned())
        );
    }
}
