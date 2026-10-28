# Kourosh.py roadmap

## Phase 0 — repository foundation (this task)

- Rust workspace with a portable, bounded RPC validator/dispatcher.
- PyO3 embedded CPython runtime with one real `greet` callback.
- Local vanilla HTML/CSS/JS demo and direct verification scripts.
- Architecture, threat model, and platform limitations documented.

## Phase 1 — native proof of concept (in progress)

- Windows host code uses WRY/TAO, a packaged document, navigation restrictions,
  and event-loop delivery of asynchronous bridge responses.
- Linux CI-free validation covers bridge and embedded Python behavior. A Windows
  machine with WebView2 is required to complete the GUI gate.

## Next task

Build and manually smoke-test the Windows host on a Windows 10/11 x64 machine,
then add the Phase 2 Python SDK and CLI only after the host lifecycle, origin
policy, and bridge timing are measured.
