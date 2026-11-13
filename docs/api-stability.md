# Alpha API contract

Kourosh.py alpha releases provide a provisional contract for the Python SDK,
browser SDK, CLI, configuration file, and protocol. The contract is intended
to make application examples portable across alpha updates; it is not a 1.0
compatibility promise. Alpha releases may change APIs with migration notes.

| Surface | Alpha contract | Status |
| --- | --- | --- |
| `kourosh.App` | `title`, bounded `width`/`height`, `@app.expose`, `run`, `close`, `closed` | Public |
| Python handlers | Sync/async callables, JSON-object arguments, JSON-compatible results | Public |
| `cancellation` keyword | Optional cooperative polling token with `is_canceled()` and `is_cancelled()` | Public alpha; experimental |
| `PluginMetadata` / `App.register_plugin` | Explicit trusted in-process plugins, protocol 1 metadata, rollback and reverse cleanup | Public alpha; experimental |
| `KouroshError` | Stable `code` and `message`; optional request ID/details on the browser side | Public |
| `@kourosh/sdk` `invoke` | Typed Promise wrapper, protocol 1, bounded timeout and pending-call cleanup | Public alpha |
| `kourosh.toml` | `[app]`, optional `[frontend]` and `[build]` fields documented in the CLI guide | Public alpha |
| `RuntimeAdapter` | Rust source-level adapter contract for Python and future runtimes | Experimental Rust API |
| `_dispatch`, `_method_names`, `_find_host_binary` | Embedding and test hooks | Internal; may change |

Protocol version 1 accepts legacy envelopes without an explicit `protocol`
field and rejects explicit unsupported versions. The default-deny method
registry, trusted-origin checks, payload bounds, and structured errors are
security contracts. They must not be widened for compatibility shortcuts.

Alpha applications should avoid relying on private underscore methods, exact
diagnostic wording, internal dispatcher metrics layout, or Rust trait ABI. The
Python package version is `0.1.0a1`; the browser package and human release
version are `0.1.0-alpha.1`; the protocol remains version 1.
