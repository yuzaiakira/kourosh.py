# Windows build guide

The first distribution target is Windows x64. Build from a Windows machine
with Rust stable, Python 3.12 development dependencies, and the official
CPython 3.12 Windows embeddable distribution. WebView2 is a separate
operating-system prerequisite; see [webview2.md](webview2.md).

For a generated React project:

```powershell
kourosh create hello --ui react --typescript
Set-Location hello
npm install
kourosh frontend build
kourosh build --target windows --format portable `
  --python-runtime C:\runtimes\python-3.12-embed-amd64 `
  --host C:\kourosh\target\x86_64-pc-windows-msvc\release\kourosh-host.exe
```

The command creates `dist/Hello Kourosh-0.2.0-windows-x64/` (the exact name
comes from `[app].name` and `[app].version`) and a ZIP plus `.sha256` file.
The host argument may be omitted when the release host is in the normal target
directory or `KOUROSH_HOST_BIN` is set. The runtime argument may likewise use
`KOUROSH_PYTHON_RUNTIME`.

Copy the directory or ZIP to a different Windows machine, install WebView2 if
needed, and launch the application executable from its copied directory. The
application does not use the source checkout, system Python, a virtualenv, or
Node.js at runtime. Use `scripts/package-smoke.ps1` for the manual clean-path
procedure, including a path containing spaces and Unicode.

Linux can validate configuration, staging, checksums, and cross-target Rust
compilation. It cannot execute the WRY/WebView2 GUI, a Windows PE host, or a
Windows package; those are Level B checks and remain unverified until a real
Windows machine runs them.
