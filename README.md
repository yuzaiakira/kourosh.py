# Kourosh.py

Kourosh.py is a Python-first desktop framework prototype. Python owns
application logic while a small Rust host owns the window and WebView lifecycle.

The current vertical slice includes a bounded, default-deny asynchronous JSON
bridge, embedded CPython through PyO3, a Python `App` SDK, a developer CLI,
vanilla and React/Vite templates, and a Windows x64 portable packaging
pipeline. A user app's `@app.expose` methods are loaded by the native host and
allowlisted in Rust before invocation. The Windows host uses WRY/WebView2 and
is guarded behind Windows compilation. Linux cloud validation exercises the
bridge, embedded Python, SDK, CLI, staging, checksums, and generated-project
tests; it does not claim a Windows GUI or packaged executable smoke test.

## Verify locally

Install Python 3.12 and Rust stable, then run:

```sh
./scripts/check.sh
```

For a relocated Python distribution, the check script derives the adjacent
shared-library directory for PyO3 linking and runtime loading. A Windows host
should use its normal Python installation and WebView2 runtime.

The script runs Rust formatting, workspace tests, Clippy, Python compilation,
and the standard-library Python test suite. On Windows it also provides the command sequence
for the WRY host; WebView2 must be installed separately.

Create a project with `kourosh create myapp`, validate prerequisites with
`kourosh doctor`, and read [docs/cli.md](docs/cli.md) and
[docs/sdk.md](docs/sdk.md) for the supported developer flow. See
[docs/ROADMAP.md](docs/ROADMAP.md), the architecture notes under
`docs/architecture/`, [docs/benchmarks.md](docs/benchmarks.md), and
[CONTRIBUTING.md](CONTRIBUTING.md) for scope and security constraints.

React and TypeScript projects are available through the local Vite templates:

```sh
kourosh create react-demo --ui react --typescript
cd react-demo
npm install
kourosh dev
```

Use `kourosh frontend build` followed by `kourosh run` for static production
frontend execution; Node.js is not part of that runtime path.

The real SQLite notes application in [examples/notes-react-ts](examples/notes-react-ts)
demonstrates React/TypeScript CRUD methods backed by embedded Python and a
user-data SQLite database. Its typecheck, production Vite build, and Python
CRUD tests run locally; its native Windows validation uses
`scripts/package-smoke.ps1`.

For a reproducible cloud setup, see [docs/cloud-onboarding.md](docs/cloud-onboarding.md).

See [docs/javascript-sdk.md](docs/javascript-sdk.md),
[docs/react-quickstart.md](docs/react-quickstart.md), and
[docs/vite-development.md](docs/vite-development.md) for the frontend
workflow. Read [docs/cli.md](docs/cli.md) for command reference and
[docs/troubleshooting.md](docs/troubleshooting.md) for structured diagnostics.
Read [docs/windows-build.md](docs/windows-build.md),
[docs/python-runtime.md](docs/python-runtime.md), and
[docs/portable-distribution.md](docs/portable-distribution.md) before making a
Windows artifact.
