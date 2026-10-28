# Kourosh.py roadmap

## Phase 0 — repository foundation (this task)

- Rust workspace with a portable, bounded RPC validator/dispatcher.
- PyO3 embedded CPython runtime with one real `greet` callback.
- Local vanilla HTML/CSS/JS demo and direct verification scripts.
- Architecture, threat model, and platform limitations documented.

## Phase 1 — native proof of concept (in progress)

- Windows host code uses WRY/TAO, a packaged document, navigation restrictions,
  and event-loop delivery of asynchronous bridge responses.
- Linux CI-free validation covers bridge and embedded Python behavior, including
  concurrent requests, timeouts, and shutdown. A Windows machine with WebView2
  is required to complete the GUI gate.
- Local benchmark scripts now measure embedded-Python startup, RPC latency, and
  bounded-dispatcher throughput; Windows host memory/startup requires Windows.

## Phase 2 — Python SDK and developer CLI (implemented, Windows GUI pending)

- Public `kourosh.App` with validated metadata, explicit `@app.expose`
  registration, JSON dispatch, structured errors, and deterministic close
  behavior.
- `kourosh create`, `kourosh dev`, and `kourosh doctor` with a vanilla
  JavaScript project generator and no Node.js runtime dependency.
- Native host loading of a user `main.py`, Rust-side method allowlisting, and
  canonicalized local frontend resources.
- Framework-independent browser SDK with bounded Promise requests and close
  cleanup.
- Python, Rust, and JavaScript tests cover generated project registration,
  malformed/unknown calls, and unsupported-platform reporting.

The real Windows WebView2 smoke test remains the release gate. Packaging,
signing, React/Vite templates, and broad native capabilities remain future
work.
