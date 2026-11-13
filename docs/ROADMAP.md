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
signing, and broad native capabilities remain future work.

## Phase 3 — React, TypeScript, Vite, and developer experience (implemented, Windows GUI pending)

- React and React+TypeScript generators with local `@kourosh/sdk` files,
  Vite configuration, Python entrypoints, and real RPC examples.
- Typed Promise SDK with structured errors, reload cleanup, and no Node runtime
  dependency in production.
- Loopback-only Vite development server management, exact Rust trusted-origin
  validation, and child-process cleanup.
- `kourosh frontend build` and `kourosh run` for static production assets.
- Frontend build, readiness, and SDK wrapper benchmark tooling.

Vue/Svelte templates, Windows GUI/HMR validation, signing, and final desktop
packaging remain outside this phase.

## Phase 4 — production packaging and Windows distribution (Level A implementation complete; Level B pending)

- `kourosh build --target windows --format portable` stages a real Windows x64
  PE host, an official embeddable CPython runtime, the Python application,
  frontend assets, framework SDK, license notices, a manifest, checksums, and
  a ZIP archive.
- Packaged host startup discovers and validates the manifest, applies isolated
  Python search paths, and preserves the existing trusted-origin bridge.
- Optional `--format installer` integration emits an Inno Setup script and
  requires `ISCC.exe` on Windows; it is not complete or tested on Linux.
- Headless tests cover metadata, real-input rejection, staging layout,
  traversal/symlink handling, checksums, and archive creation.

Level B remains pending until a real Windows x64 machine launches a copied
package with WebView2 and verifies frontend rendering, RPC success and
exceptions, clean shutdown, prerequisite diagnostics, and startup/memory
measurements. Code signing, installer certification, native-extension
dependency audits, and clean-VM verification are next release tasks.

## Phase 5A — production hardening (implementation in progress; Windows gate pending)

- Packaged CPython input now requires the matching 3.12 DLL/stdlib and a
  restrictive `python312._pth`; the host clears ambient Python search paths.
- WebView2 receives an application-specific writable data directory under the
  Windows user profile through WRY `WebContext`, including symlink and escape
  checks.
- `scripts/package-smoke.ps1` is the single Windows validation entry point and
  can emit JSON results; `scripts/bench.ps1` records process-tree, WebView2,
  CPU, startup, and shutdown measurements without inventing GUI timings.
- `examples/notes-react-ts` exercises a real SQLite CRUD app through the
  existing secure bridge and SDK.

Phase 5A remains pending for clean Windows execution, installer validation,
and measured production startup/memory/RPC evidence.

## Phase 6 — developer experience and API stabilization (implementation in progress; cloud checks active)

- Python dispatch now supports synchronous and asynchronous handlers from both
  normal and already-running event-loop callers, separates argument binding
  errors from handler failures, and reports non-JSON returns as
  `serialization_error`.
- `kourosh doctor --json` emits a versioned capability report with available,
  missing, unsupported, and failure categories. The CLI supports the
  `--template react-ts` generator alias and cleans up Vite process groups.
- Browser and TypeScript SDKs validate method/argument contracts locally,
  preserve structured error metadata, emit bridge protocol version 1, and
  reject malformed responses and stale renderer calls.
- Documentation covers protocol compatibility, diagnostics, CLI behavior,
  troubleshooting, and Linux-only performance methodology.

Remaining Phase 6 work is regression measurement on the current cloud machine,
broader generated-app integration coverage, and final API documentation review.

## Phase 7 — runtime reliability and extensibility foundation (cloud implementation in progress; Windows deferred)

- `RuntimeAdapter` defines initialization capabilities, explicit method
  discovery, validated dispatch, and graceful shutdown. The existing embedded
  Python runtime is the only implementation and is used by the Windows host
  through the trait object.
- The bounded dispatcher exposes active/queued/accepted/rejected/completed,
  timeout, and cooperative-cancellation counters. Cancellable Rust handlers can
  observe a token on timeout or shutdown without unsafe thread termination.
- Trusted, application-bundled Python plugins have explicit metadata,
  protocol/capability validation, duplicate detection, initialization rollback,
  and reverse-order cleanup. No arbitrary plugin discovery or native loading is
  added.
- Finite Linux stress tests cover concurrent requests, timeout cancellation,
  overload bounds, and resource counter cleanup.

Phase 7 still requires no additional cloud implementation. Windows WebView2,
packaged runtime, installer, and clean-machine behavior remain unverified and
must wait for the final platform-validation milestone.
Real Windows GUI behavior is intentionally deferred to the platform-validation
phase; it must not be marked verified from Linux.

## Phase 8A — performance recovery and runtime reliability (cloud implementation complete; Windows deferred)

- Phase 6 versus Phase 7 benchmark conditions were compared in isolated
  worktrees with equivalent release workloads. The observed ranges overlap and
  do not support a confirmed Phase 7 throughput regression.
- The dispatcher now has a queue-counter race fix, an instrumentation-disabled
  comparison path, direct active/queued counters, and Linux `/proc` resource
  snapshots for RSS, peak RSS, file descriptors, and threads.
- Benchmark reports include commit/toolchain/workload metadata, warmup,
  latency percentiles, throughput, dispatcher counters, and resource trends.
- Quick, standard, and extended bounded soak modes cover burst traffic,
  overload, repeated calls, shutdown cleanup, and active/queued counter checks.
- Python handlers can opt into cooperative cancellation by declaring the
  reserved `cancellation` keyword. The token is advisory and never forcibly
  terminates a CPython thread.

Phase 8A Linux implementation is complete for the measurable cloud scope.
Remaining risks are allocator-retained RSS, thread-per-request scheduling under
heavy load, and all Windows WebView2/packaging measurements. Phase 8B should
profile the Windows host on real hardware, evaluate a bounded worker pool, and
repeat process-level memory studies before changing scheduling primitives.

## Phase 8B — API stabilization and alpha preparation (cloud implementation in progress; Windows deferred)

- Provisional alpha contracts now document public, experimental, and internal
  Python, browser, CLI, configuration, protocol, plugin, and runtime-adapter
  surfaces. Alpha compatibility is intentionally weaker than a 1.0 promise.
- Framework version mapping is explicit and checked: Python `0.1.0a1`, browser
  SDK `0.1.0-alpha.1`, Rust `0.1.0`, human release `v0.1.0-alpha.1`, protocol 1.
- Local release checks produce a machine-readable report, wheel, deterministic
  source archive, checksums, documentation/version checks, Rust/Python/Node
  verification, and Windows-target cross-Clippy results. They never publish or
  create tags/releases.
- Alpha changelog, release notes, compatibility matrix, known limitations, and
  final Windows validation checklist are maintained in the source tree.

Phase 8B remains pending the final Windows platform-validation milestone and
any owner-approved publication review.
