# Windows WebView2 smoke test

This is the required manual Phase 1 GUI check. It must run on Windows 10/11
x64 with Rust stable, the repository checkout, and the Microsoft Evergreen
WebView2 Runtime installed. A Linux cloud run cannot substitute for it.

From PowerShell at the repository root:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\smoke.ps1
```

The script verifies that a WebView2 runtime is discoverable, builds the release
host, launches it, and prints the manual assertions. Confirm the bundled page,
click the greeting button, verify the Python response, repeat with another
non-empty name, and close the window. A successful result requires the process
to exit with code 0. Record the Windows build, Rust version, Python runtime
distribution, WebView2 version, and the commit SHA tested.

The script does not inject test JavaScript or claim a result without a human
checking the visible window. Portable bridge, malformed-request, timeout,
concurrency, and shutdown tests run through `scripts/check.ps1` independently.

To smoke-test a generated Phase 2 project after the bundled host check, install
the package and run `kourosh dev` from the generated project directory. The
same visible assertions should show the generated title and the project's
`@app.expose` greeting. Record the project path and commit SHA with the host
version; do not count a Linux `kourosh dev` validation message as GUI evidence.

For Phase 3, run `npm install` in a generated React project, then use
`kourosh dev` and confirm Fast Refresh or a CSS edit updates the window while a
new greeting call still reaches Python. Run `kourosh frontend build` and
`kourosh run` afterward to verify the static production path without a Vite
process. Record the Vite, Node.js, WebView2, Rust, and commit versions.
