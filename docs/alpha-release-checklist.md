# Alpha release checklist

The checklist is intentionally incomplete until Windows validation is run.

- [x] Version mapping and protocol version pass `scripts/version-check.py`.
- [x] Python wheel and deterministic local source archive build in cloud.
- [x] Rust format, workspace tests, Clippy, and Windows-target cross-Clippy pass.
- [x] Python, JavaScript, TypeScript, React/Vite, and packaging regression tests pass.
- [x] Changelog, release notes, API contract, compatibility, and known limitations are reviewed.
- [x] No `.github/workflows` or publishing command is present.
- [ ] Real Windows 10/11 x64 WebView2 GUI smoke test.
- [ ] Copied portable package launches from Unicode/space and read-only paths.
- [ ] React/TypeScript and SQLite Notes RPC behavior on Windows.
- [ ] No system Python or Node.js runtime requirement on a clean machine.
- [ ] Installer install/uninstall and WebView2 prerequisite behavior.
- [ ] Startup, total process-tree memory, latency, and clean shutdown measurements.
- [ ] Code-signing and dependency/license review for the actual distribution.

Do not label the project production-ready or mark Phase 4B complete while any
Windows item remains unchecked.
