# Supported platforms

The alpha has one native desktop target:

| Platform | Status | What is tested |
| --- | --- | --- |
| Windows 10/11 x64 | Target platform; GUI validation pending | Cross-target Clippy, packaging logic, and component tests in cloud |
| Linux cloud | Development and component validation only | Rust, embedded Python, SDK, CLI, frontend, packaging, and benchmarks |
| macOS | Not an alpha release target | No native host claim |
| Android/iOS | Future architecture work | No mobile host implementation |

Windows requires the Evergreen WebView2 Runtime and an official CPython 3.12
x64 embeddable distribution for packaging. Node.js is needed to develop and
build React/Vite assets, never to run a packaged application.

See [Windows validation](../windows-validation.md) for the handoff procedure
and [known limitations](../known-limitations.md) for the current release gate.
