# Codex Cloud development setup

The repository does not require a long-lived service. A fresh cloud machine
can prepare the Python package and the real React/TypeScript example with:

```sh
set -eu
cd /workspace/kourosh.py
python3 -m venv .venv
.venv/bin/python -m pip install --no-deps --no-build-isolation -e .
.venv/bin/python -m pip check
.venv/bin/python -c "import sqlite3, ssl, venv; c = sqlite3.connect(':memory:'); assert c.execute('select 1').fetchone() == (1,)"
cd examples/notes-react-ts
npm ci --no-audit --no-fund
npm run typecheck
npm run build
```

Use `source /workspace/kourosh.py/.venv/bin/activate` for interactive Python
work. From the repository root, `scripts/check.sh` runs Rust formatting,
workspace tests, Clippy, Python tests, JavaScript tests, and reports that the
Windows WRY/WebView2 GUI smoke test is unavailable on Linux. `scripts/bench.sh`,
`scripts/bench-cli.sh`, `scripts/bench-frontend.sh`, and
`node scripts/bench-sdk.mjs` provide the local performance measurements.

No credentials or service variables are required. Git operations use the
managed HTTPS proxy. Keep `node_modules`, `.venv`, `target`, and frontend
`dist` outputs local; they are ignored and should not be committed. A Windows
machine is still required for WebView2 GUI, portable package launch, installer,
and production distribution validation.
