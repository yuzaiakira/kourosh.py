# Production readiness checklist

| Area | State | Evidence |
| --- | --- | --- |
| Portable staging and ZIP/checksums | Implemented and automatically tested | `kourosh build`, Python packaging tests |
| Runtime manifest/path validation | Implemented and cross-compiled | Windows target `cargo check`, host source |
| Python import isolation | Implemented and regression-tested | embeddable `python312._pth` validation; packaged `PYTHONHOME`/`PYTHONNOUSERSITE` |
| WebView2 per-app user data | Implemented in Windows host | `WebContext` uses `%LOCALAPPDATA%\Kourosh\<identifier>` |
| React/TypeScript SQLite app | Implemented and automatically tested | notes example CRUD test, `npm run typecheck`, `npm run build` |
| Windows GUI/WebView2 execution | Not verified | Requires a real Windows machine |
| Clean-machine Python/Node independence | Not verified | Windows copied-package smoke required |
| Installer installation/uninstall | Not verified | Requires Windows and Inno Setup |
| Windows startup/memory/RPC measurements | Tooling implemented; measurements pending | `scripts/bench.ps1` |
| Code signing and public release | Planned | No signing keys or service are embedded |

Phase 4B remains pending until the Windows rows are executed and recorded.
Phase 5A implementation is complete only for the rows marked implemented and
automatically tested; it is not a production certification claim.
