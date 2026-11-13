# Compatibility matrix

The matrix records implemented or tested combinations only. A successful
cross-compilation check is not evidence that a Windows GUI ran.

| Component | Supported/tested combination | Evidence | Limitation |
| --- | --- | --- | --- |
| Python SDK | CPython 3.12 on Linux cloud | Unit tests, embedded PyO3 tests, wheel build | Other Python versions are not release-tested |
| Rust toolchain | Stable Rust 1.99.1 in the current cloud environment | `cargo test`, fmt, Clippy | Minimum declared toolchain is Rust 1.76; older versions are not reverified here |
| Native host | Windows x64 target, `x86_64-pc-windows-gnu` cross-Clippy | Cross-target Clippy | WRY/WebView2 execution remains unverified |
| Embedded Python | CPython 3.12, PyO3 0.22.6 | Runtime tests and packaging validation | Official Windows embeddable runtime still needs Windows smoke testing |
| WebView | Microsoft Evergreen WebView2 on Windows 10/11 x64 | Requirement and PowerShell checks | No Linux/macOS GUI support is claimed |
| Browser SDK | Framework-independent ES modules, Node tests | `tests/bridge.test.js`, SDK type declarations | Browser/WebView integration needs Windows execution |
| TypeScript/React | React 18, TypeScript 5.5, Vite 5.4 | Notes example typecheck/build | Node.js is build-time only, never a packaged runtime dependency |
| RPC | Protocol version 1 | Rust validator, JavaScript tests | Explicit unknown versions are rejected; legacy no-version envelopes remain accepted |
| Runtime adapters | Python adapter, protocol 1 | Rust adapter tests | Trait is source-level Rust API, not stable dynamic ABI |
| Packaging | Portable Windows x64 staging logic | Python packaging tests and cross-checks | PE launch, installer, signing, and clean-machine behavior need Windows |

Linux and macOS desktop GUI support are not implemented release targets. Mobile
hosts are future architecture work.
