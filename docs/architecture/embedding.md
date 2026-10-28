# Embedded CPython lifecycle

`kourosh-python` uses PyO3's embedded interpreter initialization and acquires
the GIL only around Python module loading and function calls. The packaged
proof of concept loads a small in-memory module containing `greet(name)`;
developer mode loads a validated `main.py`, reads its `kourosh.App` registry,
and invokes its `_dispatch` method with JSON arguments. Python exceptions are
converted to structured bridge errors so traceback contents are not sent to
the renderer.

The native host owns the runtime for the window lifetime. Python calls run on
the bridge worker path, never directly on the UI event-loop callback. Closing a
window marks both the dispatcher and runtime closed, rejects queued work, and
prevents new calls. PyO3 owns the process-global interpreter; Kourosh.py does
not call unsafe `Py_Finalize` while Python objects or other Rust handles may
still exist. Redistribution of a private CPython build is handled by the
Windows packaging pipeline, with clean-machine runtime validation still
pending.

An RPC timeout bounds the caller's wait and response delivery. The dispatcher
now signals a cooperative `CancellationToken` on timeout or shutdown to
handlers that explicitly accept that contract. The token is advisory: Python
code already running on a worker may finish later, and Kourosh.py never
force-cancels a CPython thread. The current Python SDK does not inject a token
into arbitrary application handlers, so synchronous and async Python handlers
must implement their own cooperative cancellation state if they need it.
