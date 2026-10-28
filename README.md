# Kourosh.py

Kourosh.py is a Python-first desktop framework prototype. Python owns
application logic while a small Rust host owns the window and WebView lifecycle.

The current vertical slice includes a bounded, default-deny asynchronous JSON
bridge, embedded CPython through PyO3, a Python `App` SDK, a developer CLI, and
a vanilla HTML demo. A user app's `@app.expose` methods are loaded by the
native host and allowlisted in Rust before invocation. The Windows host uses
WRY/WebView2 and is guarded behind Windows compilation. Linux cloud validation
exercises the portable bridge, embedded Python, SDK, CLI, and generated-project
tests; it does not claim a Windows GUI smoke test.

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
