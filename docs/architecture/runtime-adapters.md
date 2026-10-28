# Runtime adapter contract

The native host depends on the `kourosh_python::RuntimeAdapter` trait instead
of depending on CPython implementation details. The contract is intentionally
small:

- `capabilities()` reports a runtime identifier, runtime version, protocol
  version, supported capability names, and initialization duration.
- `methods()` returns the explicit method registry used by the Rust default
  deny validator.
- `dispatch(request)` accepts a validated protocol request and returns a JSON
  result or a scrubbed `BridgeError`.
- `dispatch_with_cancellation(request, token)` is the opt-in cooperative path;
  the Python adapter injects the token only into handlers that declare the
  reserved `cancellation` keyword.
- `shutdown()` and `is_shutdown()` define deterministic ownership of runtime
  work without calling unsafe CPython finalization.

Python is the only implemented adapter. The host stores the adapter behind an
`Arc<dyn RuntimeAdapter>` on Windows, so a future adapter can be added without
making the host know how its interpreter initializes or acquires its execution
lock. The trait is a source-level Rust contract, not a stable dynamic ABI;
future adapters must be compiled against the workspace and preserve protocol
version 1 semantics.

Cancellation is advisory across every adapter. A timeout or window close
signals the token and rejects the browser response, but an already-running
handler is allowed to finish and may have performed side effects. Adapters
must never terminate interpreter threads forcibly.

Adapter initialization occurs before the WebView is built. If application
loading or registry validation fails, the host returns the structured startup
error and does not create a window. Shutdown marks the runtime closed before
the event loop exits. PyO3 remains the owner of process-global interpreter
lifetime.
