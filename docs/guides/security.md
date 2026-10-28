# Security and permissions

Treat the renderer as potentially compromised:

- Register only the methods the application intends to expose.
- Validate origins in the native host; JavaScript cannot grant itself access.
- Keep CSP restrictive and disallow uncontrolled navigation.
- Bound serialized requests, pending calls, and deadlines.
- Return stable, scrubbed errors instead of Python tracebacks or secrets.
- Keep filesystem, shell, dialogs, and native capabilities behind explicit
  application-level authorization.
- Vendor and review dependencies before distributing a package.

Trusted plugins are regular in-process Python code. Metadata and registration
are explicit, but plugins are not a sandbox. Do not auto-discover plugin files
or load native libraries from renderer input.

Read the [threat model](../architecture/threat-model.md), [bridge design](../architecture/bridge.md),
and [known limitations](../known-limitations.md) before adding a capability.
