# Python SDK

The public SDK is the `kourosh` Python package. An application creates an
`App`, registers only the functions it wants to expose, and calls `run`:

```python
from kourosh import App

app = App(title="Hello Kourosh", width=1000, height=700)

@app.expose
def greet(name: str) -> dict[str, str]:
    return {"message": f"Hello {name}!"}

app.run()
```

`@app.expose` accepts synchronous or asynchronous callables. Invocation
arguments must be a JSON object and return values must be JSON-compatible.
Duplicate names and names outside `[A-Za-z_][A-Za-z0-9_]{0,63}` are rejected.
The native host loads the module, reads the explicit method registry, and
checks that registry again in Rust before dispatching a request. The Python
object is never an unrestricted evaluator.

`App.run()` starts the WRY/WebView2 host on Windows. During native module
loading it returns immediately, allowing the native event loop to remain in
charge. On Linux and other unsupported platforms it reports the Windows-only
limitation instead of launching a mock host. `KOUROSH_HOST_BIN` can point at a
locally built host during development.

Python exceptions are scrubbed at the bridge boundary into stable structured
errors. `method_not_allowed`, `invalid_args`, `python_error`, `timeout`, and
`window_closed` are examples of codes a frontend can handle. A timed-out
Python call is no longer delivered to JavaScript, but its Python work may
finish cooperatively in the worker thread.
