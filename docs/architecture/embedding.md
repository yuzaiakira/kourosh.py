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

An RPC timeout only bounds the caller's wait and response delivery. Python code
already running on the worker may finish later; the runtime does not attempt to
force-cancel a CPython thread. Applications that need cancellation should
expose cooperative cancellation state in their own handler contract.
