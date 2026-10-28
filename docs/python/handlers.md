# Exposing Python handlers

Use `@app.expose` to create an allowlisted RPC method:

```python
@app.expose
def greet(name: str) -> dict[str, str]:
    return {"message": f"Hello {name}!"}
```

You can choose a public name explicitly:

```python
@app.expose(name="lookup_user")
def lookup(user_id: int) -> dict[str, int]:
    return {"id": user_id}
```

Handlers may be synchronous or asynchronous:

```python
@app.expose
async def refresh() -> dict[str, bool]:
    return {"ready": True}
```

Rules enforced by the SDK and native bridge:

- Names match `[A-Za-z_][A-Za-z0-9_]{0,63}`.
- Arguments are one JSON object; positional arguments are not supported.
- Results must serialize as finite, JSON-compatible values.
- Duplicate names, malformed arguments, unknown methods, and Python failures
  become structured errors.
- Registration is default-deny. The browser cannot call arbitrary Python.

Do not expose filesystem, shell, import, or evaluator functions to a renderer.
Put validation and authorization in the Python handler as well as relying on
the bridge boundary.
