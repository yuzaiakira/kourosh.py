# Trusted Python plugins

`App.register_plugin(plugin)` provides a small extension point for
application-bundled Python code. A plugin supplies immutable `PluginMetadata`
with:

- a unique identifier,
- a version string,
- declared capability names, and
- protocol compatibility (`1` today).

Registration is explicit and deterministic. Kourosh.py does not scan plugin
directories, import arbitrary files, download plugins, or load native
libraries. The plugin's `initialize(app)` hook may register allowlisted Python
methods through the normal `@app.expose` path. If initialization fails, newly
registered methods are rolled back and the error is reported as `plugin_init`.
Duplicate identifiers and incompatible metadata are rejected before a plugin
is retained.

Plugins execute in the application's CPython process and are trusted
application code. Metadata and explicit registration improve lifecycle and
capability review; they are not a sandbox. `App.close()` calls retained plugin
shutdown hooks in reverse registration order, continues cleanup if one hook
fails, and is idempotent.

Native plugins, hot unloading, remote marketplaces, and isolation boundaries
are intentionally deferred. A future native extension must use an explicit
capability contract and signed, trusted packaging before it can be considered.

Lifecycle tests also cover shutdown exceptions and attempts to register after
`App.close()`. A shutdown exception is logged and cleanup continues in reverse
registration order; the closed application rejects further plugin or method
registration.
