# Kourosh.py — Product Requirements Document (PRD)

**Status:** Draft for implementation  
**Version:** 0.1.0  
**Date:** 2026-10-28  
**Product:** `kourosh.py`  
**Owner:** Akira Yuzai  
**Target release:** Desktop technical MVP (Windows-first)  
**Implementation agent:** ChatGPT Codex Cloud

> This document defines the product and engineering requirements. Architectural choices below are hypotheses to validate, not evidence of superior runtime performance.

## 1. Product vision

Build a production-oriented, Python-first application framework that lets developers write desktop applications using Python for application logic and HTML, CSS, JavaScript, TypeScript, React, Vue, Svelte, or other browser-compatible frontend technologies for user interfaces.

Kourosh.py should offer a secure, typed, asynchronous bridge between the frontend and Python, with a native application host that prioritizes resource efficiency, startup performance, maintainability, and packaging. Desktop and mobile must have **separate native host architectures**; only the public developer experience, high-level contracts, and reusable compatible Python application logic should be shared.

**Core principle:** Python owns application logic; Rust/native code owns windowing, rendering integration, privileged OS operations, and latency-sensitive infrastructure. Additional language integrations may be added later through opt-in adapters, without shipping their runtimes by default.

## 2. Users and representative use cases

- Python developers creating local productivity and business applications with web UI technologies.
- Teams pairing a React/Vite frontend with Python business logic and local data access.
- Developers building multiple native windows, file pickers, notifications, and offline-friendly desktop workflows.
- Future: mobile developers reusing compatible Python logic and frontend code via platform-specific mobile hosts.

## 3. Goals

1. Provide an ergonomic Python SDK (`from kourosh import App`) and CLI (`kourosh create`, `kourosh dev`, `kourosh build`).
2. Support browser-compatible frontends without requiring Node.js at **application runtime**. Node.js/Vite may be used during development and frontend build.
3. Run application Python through embedded CPython, initially integrated with a Rust desktop host.
4. Make frontend–Python calls asynchronous, typed where possible, bounded, and explicitly authorized.
5. Support a minimal working Windows desktop app using WebView2, with native Windows testing required for certification.
6. Make tests, performance metrics, reliability evidence, and packaging reproducible.
7. Permit optional Rust/C++ native extensions and future language adapters through stable, versioned contracts.
8. Avoid GitHub Actions entirely and keep verification runnable locally and in Codex Cloud where supported.

## 4. Explicit non-goals for v0.1

- Android/iOS host implementation; only document their future interfaces and constraints.
- CEF engine implementation. CEF may be re-evaluated as an optional future backend after measurement.
- Shipping a Node.js runtime, web server, or arbitrary runtime interpreters inside the released application.
- Automatic update service, plugin marketplace, multi-language VM, SSR framework hosting, and custom renderer engine.
- Claiming parity with Electron/Tauri, universal library compatibility, or production certification without benchmarks and OS-specific test evidence.
- Supporting all Windows/macOS/Linux variants in the first technical MVP. Design for ports, do not pretend they are already tested.

## 5. Initial technical architecture

### 5.1 Desktop — Windows-first

- **Native host:** Rust, with a small, explicit application lifecycle and event loop.
- **WebView:** WRY over Microsoft WebView2 on Windows; use TAO or a compatible windowing dependency if it simplifies the event loop.
- **Python:** Embedded CPython via PyO3, with strict ownership of initialization, shutdown, and callback execution.
- **Bridge:** request/response RPC between web JavaScript and a method registry in Python, mediated and validated by Rust.
- **Frontend build:** Vite for React/TypeScript templates; plain HTML/CSS/JS template without Node tooling must also work.
- **Asset loading:** packaged local resources through a custom, trusted app origin or another secure local resource mechanism. Avoid a localhost HTTP server in packaged applications by default.
- **Core data:** JSON initially, with future extensibility for binary payload transport if profiling justifies it.
- **Processes:** prefer a small host and embedded CPython first; recognize WebView2 itself is multiprocess. Benchmark the entire process tree.

### 5.2 Future mobile architecture (design only)

- **Android:** Kotlin-native host + Android WebView + an embedded mobile-compatible Python distribution.
- **iOS:** Swift-native host + WKWebView + an embedded iOS-compatible Python distribution.
- **Shared:** public API semantics, serialization/schema contracts, permissions vocabulary, and portable Python business logic where possible.
- **Not shared:** native process and UI lifecycle, rendering engine integration, OS permissions, Python bootstrap implementation, packaging, signing, and distribution.

### 5.3 Future language adapters (design only)

- Specify a narrow `LanguageRuntimeAdapter` interface and capability metadata.
- Python is the only **required** language runtime in v0.1.
- Native extensions written in Rust/C++ may be called from Python using existing ABI/binding strategies where appropriate.
- No additional VM or interpreter is started unless a project explicitly opts into that runtime.

## 6. Public developer experience

### 6.1 Intended API (design target, not yet implemented)

```python
from kourosh import App

app = App(title="Hello Kourosh", width=960, height=640)

@app.expose
async def greet(name: str) -> dict[str, str]:
    return {"message": f"Hello, {name}!"}

app.run("frontend/dist/index.html")
```

```ts
import { invoke } from "@kourosh/sdk";
const result = await invoke<{ message: string }>("greet", { name: "Akira" });
console.log(result.message);
```

The implemented API may vary slightly for legitimate technical reasons, but the end-user experience must be comparably straightforward. **Do not hardcode a public API before validating the Python embedding and RPC bridge.**

### 6.2 CLI targets

```sh
kourosh create hello --template vanilla
kourosh create dashboard --template react-ts
kourosh dev
kourosh build --target windows
```

At each phase, expose only commands that actually work. If a command is a scaffold or unsupported on the current build OS, return an honest, actionable error; never silently succeed.

## 7. Functional requirements

| ID | Requirement | v0.1 priority | Acceptance evidence |
|---|---|---|---|
| FR-01 | Create and display a desktop window with local HTML/CSS/JS | P0 | Windows smoke test + simple demo |
| FR-02 | Initialize embedded CPython and run Python business logic | P0 | Rust/Python integration test |
| FR-03 | Expose an allowlisted Python function to JS via asynchronous RPC | P0 | Promise resolve/reject and integration tests |
| FR-04 | Enforce trusted origins and explicit API access | P0 | Negative permission/origin tests |
| FR-05 | Return structured errors, request IDs, bounded input sizes, and timeouts | P0 | Boundary and malformed message tests |
| FR-06 | Avoid blocking UI thread on Python callbacks; define worker scheduling | P0 | UI responsiveness and long-running task test |
| FR-07 | Provide a plain web template, Python example, and development CLI | P0 | End-to-end documented demo |
| FR-08 | Provide React + TypeScript + Vite template | P1 | Frontend build and call into Python |
| FR-09 | Produce a distributable Windows artifact including required Python dependencies | P1 | Clean Windows VM/install smoke test |
| FR-10 | Add native file dialogs with capability-based permission model | P1 | Manual + automated tests where feasible |
| FR-11 | Multi-window, events, clipboard, and notifications | P2 | Later scoped milestones |
| FR-12 | Linux/macOS support and mobile host implementation | Future | Dedicated platform roadmaps |

## 8. Security baseline

1. Never expose arbitrary Python evaluation, unrestricted import, or unrestricted filesystem/shell access to web content.
2. Allow only explicitly registered/annotated Python functions. Use a default-deny method registry.
3. Check the source window and origin **in the host** before dispatch, not only in JavaScript.
4. Do not grant privileged RPC to remote URLs or untrusted iframe content. Default to local packaged content; disallow uncontrolled navigation.
5. Enforce serialized request size limits, argument validation, per-call timeout, error scrubbing, and predictable cancellation semantics where feasible.
6. Use CSP in production templates; prevent unexpected mixed content, remote debug exposure, and secret leakage to the renderer.
7. Scope native filesystem/dialog capabilities by window and operation. Avoid a broad `execute(command)` or `read_any_file` API.
8. No secrets or credentials in commits, documentation examples, fixtures, or logs. No automatic network calls from templates without clear intent.
9. Document threat model: compromised renderer, malicious package, unsafe web navigation, dependency supply chain, and app origin spoofing.
10. Pin and audit dependencies with local commands; do not depend on paid CI services.

## 9. Performance and reliability requirements

Performance claims need a reproducible benchmark on named hardware, OS build, Python version, WebView2 runtime, release configuration, and frontend build.

**Measure at minimum:**
- Cold start to visible/interactable window and warm start time.
- Total resident/working-set memory across app + embedded Python + WebView child processes.
- Idle and active CPU usage.
- One-way and round-trip latency of JS↔Python RPC at p50, p95, and p99 for small and moderate payloads.
- UI responsiveness while a Python task is slow or CPU-bound.
- Build artifact size, installed footprint, and time-to-first-interaction.
- Crash containment/recovery behavior and useful diagnostics.

**Provisional evaluation targets, not guaranteed product promises:**
- No sustained CPU spin when the UI is idle.
- Zero blocking calls on the primary UI event loop from Python callbacks.
- No unbounded message queues; backpressure for heavy event traffic.
- Optimized startup and idle memory **relative to a matched Electron baseline**, with measured figures recorded before declaring success.

Prefer measurable regression thresholds based on first validated baselines over invented hard memory numbers.

## 10. Implementation phases and acceptance gates

### Phase 0 — Repository foundation

- Inspect existing repository first; preserve pre-existing user work.
- Add source layout, root `AGENTS.md`, this PRD, architecture decisions, `README.md`, `CONTRIBUTING.md`, license decision placeholder (do not invent a license), and minimal `docs/ROADMAP.md`.
- Set up reproducible Rust/Python/TypeScript project files without introducing unnecessary build dependencies.
- Add local test/lint/format scripts; **do not create GitHub Actions or `.github/workflows`**.
- Configure repository-local Git identity and verify it before committing.
- Gate: repository integrity checks run; clear setup and blocker documentation.

### Phase 1 — Working native proof of concept

- Minimal Rust native host using WRY and embedded CPython via PyO3.
- Display locally bundled HTML and call a safe registered Python `greet` function asynchronously.
- Correct event-loop/threading, lifecycle, request ID matching, error handling, timeouts, and allowlisting.
- Prefer a safe, functional vertical slice over generalized abstraction.
- Gate: tests of bridge and Python execution pass where OS allows; a Windows manual smoke test is explicitly required and marked **unverified** if Windows cannot run in the cloud environment.

### Phase 2 — Developer SDK and frontend examples

- `kourosh` Python SDK, minimal CLI create/dev, vanilla example, and React/TypeScript/Vite example.
- Build frontend into static artifacts. No Node process in packaged app.
- JS/TS SDK with typed `invoke` and robust error mapping.
- Gate: end-to-end demo instructions are reproducible; no sham placeholders labeled functional.

### Phase 3 — Desktop packaging and security hardening

- Windows build output, CPython redistribution plan, version pins, environment detection, WebView2 installation/availability handling, and signing documentation.
- Strengthen capabilities, origin validation, local resources, dependency auditing, crash/error reporting, and tests.
- Gate: verify on a real Windows machine / clean VM before claiming complete. Cloud-only tests are insufficient.

### Phase 4 — Performance baseline and stabilization

- Benchmark scripts, reproducible test fixture, comparison notes, performance profile and optimizations based on measurements.
- Define platform-specific release support policy and a decision record for future macOS/Linux and mobile hosts.
- Gate: measurable evidence, passing supported-platform tests, and no open P0 security issues.

**Execution policy:** Work in small verified vertical slices. For initial Codex Cloud task, implement Phase 0 and as much of Phase 1 as is verifiable within the environment; document and stop at true toolchain or permission blockers. Subsequent phases are separate reviewable tasks.

## 11. Suggested repository structure

```text
kourosh.py/
├── AGENTS.md
├── README.md
├── PRD.md
├── pyproject.toml
├── Cargo.toml
├── crates/
│   ├── kourosh-host/           # Rust desktop application host
│   ├── kourosh-bridge/         # typed, secure RPC primitives
│   └── kourosh-python/         # PyO3 integration and lifecycle
├── python/
│   └── kourosh/               # Python developer SDK + CLI
├── packages/
│   └── sdk/                   # browser-side TypeScript SDK (future Phase 2)
├── examples/
│   ├── hello-vanilla/
│   └── hello-react/           # future Phase 2
├── docs/
│   ├── architecture/
│   ├── decisions/
│   └── ROADMAP.md
├── scripts/
│   ├── check.sh
│   └── check.ps1
└── tests/
```

The structure is a target, not a mandate to create empty directories or dummy modules. Favor the smallest viable layout.

## 12. Quality and definition of done

- No fabricated results, fake passing smoke tests, or `TODO` stubs masquerading as implemented capabilities.
- All code formatted, linted and tested with the locally available toolchain. Record skipped verification explicitly.
- Reasonable unit/integration tests for the actual code added.
- Examples represent real supported flows and include exact prerequisites.
- No production runtime dependency on Vite/Node or a background Python HTTP server.
- Document architectural tradeoffs, OS-specific constraints, and known issues.
- Commits have configured identity and are pushed immediately where the cloud environment's GitHub permissions allow.
- No `.github/workflows` files or GitHub Actions configuration, at any phase.

## 13. Git and collaboration contract

- **Commit author name and committer name:** `Akira Yuzai`
- **Commit author email and committer email:** `yuzai.akira@gmail.com`
- Set identity with repository-local `git config user.name` and `git config user.email` before any commit; verify every commit's metadata.
- Use conventional commit messages (e.g., `feat(host): add window bootstrap`).
- Work on the currently provided feature/task branch, or create a `codex/*` branch if permitted. Never force-push or rewrite shared history; do not push directly to a protected default branch.
- After **every successful commit**, immediately attempt `git push -u origin HEAD` (or the authorized branch-ref equivalent), then verify the remote branch contains the commit before doing more commits.
- If the push fails because credentials, repository access, branch protections, or network egress are missing: **stop before making further commits**, preserve work, report the exact blocker, and request the required user-side configuration. Do not claim a successful push.
- Never request or embed plaintext PATs in source files or prompts. Use supported, user-approved GitHub connection/credential mechanisms.
- **Strict prohibition:** No GitHub Actions, including `.github/workflows/*`, new workflow files, or recommending GitHub-hosted runners as a necessary validation path. All tests use direct commands and optional user-controlled machines.

## 14. Open decisions

- GitHub repository URL/ownership: supplied by the user during Codex environment setup; do not guess.
- Operating system supported at release: initial Windows x64 target; broaden after successful validation.
- Python distribution and redistribution approach/license audit: prototype and decide after Phase 1.
- Public license: user decision, not inferred from repository visibility.
- Final package/application ID naming: confirm before public release.
- Benchmark baselines: establish using identified reference hardware.

## 15. Primary references

- Codex Cloud and repository permissions: https://help.openai.com/en/articles/20001545-using-codex-cloud
- Codex project instructions (`AGENTS.md`): https://developers.openai.com/cookbook/examples/codex/iterating-development-workflows-with-codex
- WRY platform WebView backend and event loop: https://docs.rs/wry/latest/wry/
- PyO3 Python embedding and distribution: https://pyo3.rs/main/building-and-distribution
- GitHub commit email/identity: https://docs.github.com/en/account-and-profile/how-tos/email-preferences/setting-your-commit-email-address
