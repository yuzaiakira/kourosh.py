# Architecture overview

Kourosh.py separates application logic from native lifecycle responsibilities:

| Layer | Responsibility |
| --- | --- |
| Python SDK | App metadata, method registration, business logic, plugins, and lifecycle hooks |
| Embedded CPython | Executes registered Python handlers with controlled initialization and shutdown |
| Rust bridge | Validates origins, protocol envelopes, methods, arguments, bounds, deadlines, and responses |
| Rust host | Owns the Windows event loop, WRY/WebView2 window, local assets, and user-data context |
| Browser SDK | Serializes requests, tracks Promise calls, normalizes errors, and cleans up pending calls |
| Frontend | Renders the application and calls only the registered API |

The full design notes are in [bridge architecture](../architecture/bridge.md),
[embedding](../architecture/embedding.md), [packaging](../architecture/packaging.md),
and the [threat model](../architecture/threat-model.md).

!!! warning "Platform boundary"

    Rust cross-compilation and Linux bridge tests validate source-level and
    component behavior. They do not prove that a Windows WebView2 window runs.
