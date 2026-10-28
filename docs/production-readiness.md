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
| Python/CLI API stabilization | Implemented and automatically tested | async dispatch, JSON contract tests, `kourosh doctor --json` |
| JavaScript/TypeScript protocol v1 | Implemented and automatically tested | Rust validator, SDK, concurrent and malformed-response tests |
| Structured diagnostics and troubleshooting | Implemented and documented | `configure_logging`, doctor schema, troubleshooting guide |
| Linux performance regression baseline | Measured | `scripts/bench.sh`, `scripts/bench-cli.sh`, frontend and SDK benchmarks |
| Runtime adapter contract | Implemented and automatically tested | `RuntimeAdapter`, Python capability discovery, host trait usage |
| Trusted Python plugin lifecycle | Implemented and automatically tested | metadata, duplicate, rollback, and cleanup tests |
| Dispatcher cancellation and resource metrics | Implemented and automatically tested | cooperative token, bounded stress, timeout and counter assertions |
| Python-level cooperative cancellation | Implemented with explicit opt-in | `cancellation` handler parameter, timeout race test; no forced thread termination |
| Linux resource instrumentation | Implemented where supported | `/proc` RSS/peak-RSS, fd, thread, active/queued samples in benchmark reports |
| Bounded soak testing | Implemented and cloud-executed | `scripts/stress.sh` quick mode; configurable standard/extended durations |
| Repeatable benchmark comparison | Implemented | `scripts/bench.sh` warmup, JSON reports, metrics-enabled/disabled comparison |
| Code signing and public release | Planned | No signing keys or service are embedded |

Phase 4B remains pending until the Windows rows are executed and recorded.
Phase 5A implementation is complete only for the rows marked implemented and
automatically tested; it is not a production certification claim.
