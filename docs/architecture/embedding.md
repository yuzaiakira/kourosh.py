# Embedded CPython lifecycle

`kourosh-python` uses PyO3's embedded interpreter initialization and acquires
the GIL only around Python module loading and function calls. The first proof
of concept loads a small in-memory module containing `greet(name)`. Python
exceptions are converted to a generic structured bridge error so traceback
contents are not sent to the renderer.

The native host owns the runtime for the window lifetime. Python calls run on
the bridge worker path, never directly on the UI event-loop callback. Closing a
window marks both the dispatcher and runtime closed, rejects queued work, and
prevents new calls. PyO3 owns the process-global interpreter; Kourosh.py does
not call unsafe `Py_Finalize` while Python objects or other Rust handles may
still exist. Redistribution of a private CPython build remains Windows
packaging work for Phase 3.
