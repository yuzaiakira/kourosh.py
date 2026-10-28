# Kourosh.py

Kourosh.py is a Python-first desktop framework prototype. Python owns
application logic while a small Rust host owns the window and WebView lifecycle.

The current vertical slice includes a bounded, default-deny asynchronous JSON
bridge, embedded CPython through PyO3, and a vanilla HTML demo exposing one
function: `greet`. The Windows host uses WRY/WebView2 and is guarded behind
Windows compilation. Linux cloud validation exercises the portable bridge and
embedded Python tests; it does not claim a Windows GUI smoke test.

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

See [docs/ROADMAP.md](docs/ROADMAP.md), the architecture notes under
`docs/architecture/`, [docs/benchmarks.md](docs/benchmarks.md), and
[CONTRIBUTING.md](CONTRIBUTING.md) for scope and security constraints.
