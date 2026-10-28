# Kourosh.py 0.1.0-alpha.1 (unreleased)

This document describes the first planned alpha source tree. It is an
experimental developer release and has not been published to PyPI, npm, or
GitHub Releases.

The alpha includes a Python-first SDK, a secure asynchronous JavaScript to
Python bridge, a Rust host path for Windows WRY/WebView2, vanilla and
React/TypeScript examples, local CLI tooling, and portable-package staging.
Protocol version 1 is retained. Python handlers may opt into cooperative
cancellation by declaring `cancellation`; arbitrary synchronous Python work is
never forcibly terminated safely.

The current cloud environment verifies Rust, embedded CPython, SDK behavior,
CLI logic, package metadata, frontend builds, cross-target Clippy, resource
instrumentation, and bounded soak tests. Windows GUI execution has not been
validated. WebView2 production behavior, installer execution, clean Windows
machine independence, code signing, startup measurements, and total Windows
memory remain pending real platform validation.

Alpha updates may contain breaking API changes. Applications should pin the
alpha version, avoid private underscore APIs, and review the changelog before
upgrading.
