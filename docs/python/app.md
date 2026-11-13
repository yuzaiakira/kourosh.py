# App and window configuration

`App` is the public Python entrypoint:

```python
from kourosh import App

app = App(title="Inventory", width=1200, height=800)
```

Signature:

```text
App(*, title: str, width: int = 960, height: int = 640)
```

`title` must be non-empty and at most 256 UTF-8 bytes. `width` and `height`
must be integers from 1 through 16,384. Invalid values raise `ValueError`.

Register methods with `@app.expose` and launch with `app.run(frontend=None)`.
The optional frontend path must resolve to an existing file inside the app
directory. The native WRY/WebView2 host is currently Windows-only.

The `kourosh.toml` project configuration is used by the CLI; see the
[configuration schema](../api/configuration.md).

!!! note "Stability"

    `App`, `expose`, `close`, `closed`, and `run` are public alpha APIs. Methods
    beginning with `_` are implementation and test hooks.
