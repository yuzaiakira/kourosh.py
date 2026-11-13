# Python SDK reference

The public Python package is `kourosh` version `0.1.0a1`.

## `App`

```text
App(*, title: str, width: int = 960, height: int = 640)
```

Creates application metadata and an empty method registry. `title` is required;
dimensions are bounded positive integers.

```text
app.expose(function=None, *, name=None) -> function | decorator
```

Registers a callable under a validated name. Sync and async callables are
accepted. Arguments are JSON objects and results must be JSON-compatible.

```text
app.register_plugin(plugin: Plugin) -> Plugin
app.plugin_metadata() -> list[dict[str, object]]
app.close() -> None
app.run(frontend: str | Path | None = None) -> int | None
app.closed -> bool
```

`register_plugin` is public alpha/experimental. `close` is idempotent. `run`
launches the Windows native host and raises `KouroshError` for unsupported
platforms, invalid frontend paths, missing hosts, or non-zero host exits.

## Errors and cancellation

`KouroshError(code, message)` is the stable SDK error type. Bridge failures
use codes such as `invalid_args`, `method_not_allowed`, `python_error`,
`serialization_error`, `timeout`, `shutdown`, and `unsupported_platform`.

`CancellationToken` exposes `is_canceled()` and `is_cancelled()`. It is
cooperative and only supplied to handlers that declare `cancellation`.

`configure_logging(level=None)` accepts `DEBUG`, `INFO`, `WARNING`, `ERROR`,
or `CRITICAL`. Default logging is quiet and does not include request payloads.

## Stability

The classes and methods above are public alpha surfaces. `PluginMetadata` and
`Plugin` are experimental. Names beginning with `_`, including `_dispatch`,
`_method_names`, and `_find_host_binary`, are internal test/embedding hooks.
