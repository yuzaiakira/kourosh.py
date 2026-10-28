---
icon: lucide/rocket
---

<div class="hero">

# Build Python-first desktop apps

Kourosh.py pairs Python application logic with HTML, CSS, JavaScript, TypeScript,
React, and a small Rust host. The browser-to-Python bridge is asynchronous,
allowlisted, bounded, and designed for local desktop applications.

<div class="status-line">0.1.0-alpha.1 · experimental · Windows GUI validation pending</div>

</div>

!!! warning "Alpha status"

    The source tree is cloud-tested, but the native WRY/WebView2 host, portable
    package, installer, and clean-machine behavior still require a real Windows
    10/11 x64 validation run. The project is not production-certified and has
    not been published to PyPI or npm.

## Start here

1. Read [prerequisites](getting-started/prerequisites.md).
2. Follow the [installation guide](getting-started/installation.md).
3. Build your first [vanilla application](getting-started/quickstart.md).
4. Continue with [React and TypeScript](frontend/react-typescript.md) when you
   need a component-based frontend.

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
kourosh doctor
kourosh create hello
```

## What is included?

<div class="grid cards" markdown>

- **Python owns application logic**

  Register explicit functions with `@app.expose` and return JSON-compatible
  values from synchronous or asynchronous handlers.

- **A secure browser bridge**

  Promise-based calls use request IDs, origin checks, payload limits, timeouts,
  structured errors, and default-deny method registration.

- **Static frontend assets**

  Use plain HTML or build React/Vite assets during development. Node.js is not
  part of the packaged runtime.

- **Local, inspectable tooling**

  The CLI creates projects, runs diagnostics, builds frontend assets, and stages
  Windows distributions without GitHub Actions or a hosted service.

</div>

## Follow the complete guide

| Goal | Guide |
| --- | --- |
| Learn the architecture | [Architecture overview](introduction/architecture.md) |
| Register Python methods | [Python handlers](python/handlers.md) |
| Call Python from a browser | [RPC guide](guides/rpc.md) |
| Build a React app | [React and TypeScript](frontend/react-typescript.md) |
| Package for Windows | [Portable distribution](portable-distribution.md) |
| Diagnose a failed launch | [Troubleshooting](troubleshooting.md) |

The [compatibility matrix](compatibility.md), [known limitations](known-limitations.md),
and [release checklist](alpha-release-checklist.md) distinguish implemented,
cloud-tested, experimental, planned, and Windows-unverified behavior.
