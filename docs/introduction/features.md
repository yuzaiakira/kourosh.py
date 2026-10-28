# Features

## Application runtime

- Python 3.12 application logic embedded through PyO3.
- `App` metadata for title and bounded window dimensions.
- Synchronous and asynchronous exposed handlers.
- Cooperative cancellation tokens for handlers that opt in.
- Explicit lifecycle cleanup and trusted plugin hooks.

## Frontend bridge

- Framework-independent JavaScript and TypeScript SDK.
- Protocol version 1 with request IDs and Promise results.
- Default-deny method registry and trusted-origin validation in Rust.
- Bounded request size, pending calls, timeout, and structured error mapping.
- Pending-call rejection when a request times out, a window closes, or a
  renderer reloads.

## Developer workflow

- `kourosh create` for vanilla, React, and React+TypeScript projects.
- `kourosh doctor --json` for machine-readable prerequisite diagnostics.
- `kourosh dev` for Vite development on Windows.
- `kourosh frontend build` and `kourosh run` for static production assets.
- Local Windows portable staging with embedded CPython and checksums.

The [API stability contract](../api-stability.md) labels public, experimental,
and internal surfaces.
