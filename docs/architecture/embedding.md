# Embedded CPython lifecycle

`kourosh-python` uses PyO3's embedded interpreter initialization and acquires
the GIL only around Python module loading and function calls. The first proof
of concept loads a small in-memory module containing `greet(name)`. Python
exceptions are converted to a generic structured bridge error so traceback
contents are not sent to the renderer.

The native host owns the runtime for the window lifetime. Python calls run on
the bridge worker path, never directly on the UI event-loop callback. Shutdown
behavior and redistribution of a private CPython build remain Windows
packaging work for Phase 3.
