# Lifecycle, cancellation, and logging

## Closing an application

`app.close()` is idempotent. It marks the SDK closed, rejects new registrations
and dispatches, and shuts down registered plugins in reverse order. The
`app.closed` property reports the SDK-side state.

```python
if not app.closed:
    app.close()
```

The native host owns the event loop and performs its own shutdown coordination.
Do not call unsafe interpreter-finalization APIs from application code.

## Cooperative cancellation

A handler opts in by declaring a keyword-compatible `cancellation` parameter:

```python
@app.expose
def import_rows(rows: list[dict], cancellation=None) -> dict[str, int]:
    imported = 0
    for row in rows:
        if cancellation and (cancellation.is_canceled() or cancellation.is_cancelled()):
            break
        save_row(row)
        imported += 1
    return {"imported": imported}
```

Cancellation is advisory. A timeout or window close does not forcibly kill an
arbitrary Python thread, roll back side effects, or guarantee that synchronous
work stops immediately.

## Diagnostics

Diagnostics are quiet by default. Use either form during development:

```sh
KOUROSH_LOG_LEVEL=INFO kourosh doctor
```

```python
from kourosh import configure_logging
configure_logging("DEBUG")
```

Logs contain stable categories and method names, not request payloads or
credentials. See [troubleshooting](../troubleshooting.md) for CLI diagnostics.
