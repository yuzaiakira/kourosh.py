# JavaScript–Python bridge

The bridge accepts JSON envelopes shaped as `{ "id", "method", "args" }`.
The Rust host checks the source document policy before it passes the message to
`kourosh-bridge`. The validator uses a default-deny method registry, accepts
only `greet`, requires a string `name`, and bounds request, ID, and argument
sizes. Responses always contain the request ID, an `ok` flag, and either a
result or a structured `{code, message}` error.

When validation fails before queueing, Rust recovers a valid ID from the raw
envelope so the matching Promise is rejected instead of waiting for its timer.
Messages without a valid ID cannot be correlated and are intentionally dropped
by the browser helper after its bounded timeout.

`AsyncDispatcher` uses a bounded synchronous queue and a worker thread. The
native IPC callback does not execute Python or wait on the GIL; it submits work
and the event loop receives a user event when the result is ready. Calls have a
deadline. A timed-out Python thread is allowed to finish cooperatively while
its result is discarded; future cancellation tokens will be added before long
running application work is exposed.

The browser helper never evaluates response text. It matches IDs in a pending
map and resolves or rejects a Promise from the structured response. It rejects
all pending calls when the host begins window shutdown and converts a thrown
IPC transport error into a structured rejection. It exposes no shell,
filesystem, import, or arbitrary-evaluation method.
