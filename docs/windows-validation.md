# Windows validation entry point

Phase 4B requires a real Windows 10/11 x64 machine with WebView2. Linux and
cross-compilation checks cannot certify WebView2 rendering, bundled-Python
independence, read-only installation paths, or installer behavior.

Run the single packaged validation entry point from PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\package-smoke.ps1 `
  -ProjectPath .\examples\notes-react-ts `
  -PythonRuntime C:\runtimes\python-3.12-embed-amd64 `
  -HostPath .\target\x86_64-pc-windows-msvc\release\kourosh-host.exe `
  -ResultsPath .\windows-validation-results.json
```

The script detects WebView2, builds the package, copies it outside the source
tree to a path containing spaces and Unicode, checks that `python.exe` and
`node.exe` are absent, and launches the copied executable. It writes a
machine-readable JSON file for automated checks that actually ran and marks
frontend rendering, JavaScript-to-Python success, structured Python errors,
and manual close behavior as `manual` until the operator observes them.

Repeat the launch several times, make the copied package directory read-only,
and verify that WebView2 data is created under the user's local application
data directory. Record the Windows build, CPU/RAM, CPython version, WebView2
version, artifact checksums, and commit SHA.

The installer path is separate:

```powershell
kourosh build --target windows --format installer ...
```

It requires Inno Setup and is blocked when `ISCC.exe` is unavailable.
