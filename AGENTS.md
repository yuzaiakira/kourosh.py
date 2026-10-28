# AGENTS.md — Persistent instructions for Kourosh.py

These instructions govern **every coding task and commit** in this repository. If task instructions conflict, follow the most restrictive applicable repository/security rule unless the repository owner explicitly changes it.

## Project identity and priorities

- Project: `kourosh.py`, a Python-first, production-oriented desktop application framework using HTML/CSS/JS/TS frontends.
- Python owns business logic; native OS hosts own window lifecycle, platform integration, and fast-path infrastructure.
- Desktop and mobile will have separate platform-specific host architectures. Mobile is out of scope for v0.1.
- Optimize for correctness, performance evidence, modest memory use, security, and maintainability — not superficial feature counts.
- Read `PRD.md` and existing architectural decisions before changing behavior or public APIs.

## v0.1 architecture guardrails

- Windows-first host: Rust + WRY/WebView2 + embedded CPython through PyO3.
- Favor minimal dependencies and a functional vertical slice over speculative plugin/adapter systems.
- Browser frontends are framework-agnostic; React/Vite/TypeScript are supported through static asset build, not an embedded Node.js production process.
- Rust↔Python integration must respect interpreter initialization, GIL requirements, shutdown behavior, and the OS UI event loop.
- JS↔Python bridge: asynchronous, request IDs, allowlisted methods, origin checks, bounded payloads/timeouts, validated arguments, structured errors.
- No untrusted web origin gets privileged bridge methods; no unrestricted `eval`/shell/OS access from JavaScript.
- Never fabricate successful Windows GUI smoke tests when running in a Linux cloud environment.

## Absolute Git rules

1. **Every commit must have Author and Committer name `Akira Yuzai` and email `yuzai.akira@gmail.com`.** Before any commit, set repository-local values:

   ```sh
   git config --local user.name "Akira Yuzai"
   git config --local user.email "yuzai.akira@gmail.com"
   ```

2. Before each commit check `git diff --check`, inspect `git status`, run relevant tests, and avoid accidentally staging secrets, build outputs, or unrelated files.
3. Use focused conventional commit messages. Do not rewrite shared history, force-push, or push directly to a protected default branch.
4. **Immediately after each successful commit, push that commit to GitHub** on the authorized working branch: `git push -u origin HEAD` (or an equivalent permitted command). Verify with Git remote branch inspection.
5. **If pushing fails, do not create another commit until the blocker is fixed**. Keep local changes safe, show the failing command/diagnostic, and tell the user what permission or setup is required. Never claim that a commit was pushed without verification.
6. The user explicitly requested commits and pushes, subject to the available repository permissions. Never assume remote GitHub access or invent a repository URL.
7. Never paste a personal access token into a file, command transcript, README, or task output. Use the configured Codex Cloud GitHub connection/approved secure credentials.

## GitHub Actions: forbidden

- **Do not use or create GitHub Actions under any circumstances.**
- **Never create `.github/workflows/` or workflow YAML files.**
- Do not enable GitHub-hosted CI, scheduled actions, auto-release workflows, or CodeQL via Actions.
- Use `scripts/check.sh`, `scripts/check.ps1`, `cargo test`, `cargo fmt`, `cargo clippy`, `pytest`, etc. directly in development environments.
- Avoid other billable CI unless the owner explicitly requests it in a later task.

## Working methodology

- Inspect current code, branch, and toolchain before editing. Do not overwrite existing user work.
- Make a concise plan, then implement the smallest testable vertical slice. Maintain an up-to-date `docs/ROADMAP.md` or a similarly compact progress log.
- Use stable dependencies, lockfiles where practical, readable types, and narrow error handling.
- Provide unit/integration tests that validate actual functionality; no dummy tests asserting `True`.
- Run feasible checks and clearly distinguish passed, failed, and **not run** tests.
- On Linux Codex Cloud, Windows-only WebView2 GUI or packaging validation is **blocked pending Windows host**. Record this explicitly.
- Do not claim production readiness before security review, real Windows smoke tests, distribution verification, and reproducible performance measurements.
- Stop when a true permission/toolchain blocker is encountered; otherwise make a useful implementation before reporting.

## Task completion report

Report concisely:
- Implemented functionality and changed files
- Test commands and results
- OS-specific tests not performed and why
- Commit SHA, Author/Committer verification, branch, push status, and remote reference if verified
- Security/performance caveats and next recommended phase
