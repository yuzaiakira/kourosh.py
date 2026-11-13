# Troubleshooting

Run the diagnostic report before investigating a native launch:

```sh
kourosh doctor
kourosh doctor --json > doctor.json
```

`available` means the capability was found, `missing` means a prerequisite is
absent, `unsupported` means the current operating system cannot provide that
capability, and `failure` is reserved for a check that ran and failed. Linux
reports the Windows WebView2 host as unsupported and does not launch a mock
window. A Windows report must show both a native host and the Evergreen
WebView2 Runtime before GUI testing can start.

For Python-side diagnostics, set `KOUROSH_LOG_LEVEL=INFO` or call
`configure_logging("DEBUG")` during development. Logs contain method names and
stable error categories only; request arguments, credentials, and exception
traces are intentionally omitted from the default bridge boundary.

Common errors:

- `bridge_unavailable`: the page loaded without the bootstrap script or the
  native IPC channel is not present. Check that `kourosh.js` or
  `kourosh-bridge.js` is included before application code.
- `invalid_origin`: the native host rejected a page outside the trusted local
  origin. Do not work around this by widening the origin allowlist.
- `method_not_allowed`: the method was not registered with `@app.expose` or
  was rejected by the Rust registry. Check the method spelling and restart the
  app after changing registrations.
- `timeout`: the caller's wait deadline elapsed. Python work is allowed to
  finish cooperatively; the timed-out result is discarded. Add application
  cancellation for long-running work instead of forcing interpreter thread
  termination.
- `unsupported_platform`: the current system cannot run the WRY/WebView2
  desktop host. Use the Linux bridge and packaging tests in cloud development,
  then follow the Windows smoke procedure for GUI behavior.

For Vite projects, `kourosh frontend build` requires `npm` and an installed
`node_modules` directory. `kourosh dev` owns the loopback server process and
terminates its process group on exit or Ctrl+C. Production `kourosh run` loads
static assets and does not start Node.js.

For packaged applications, use `scripts/package-smoke.ps1` on Windows. It
checks the copied package path, records the WebView2 version, and writes a
human checklist plus optional JSON results. Installer output requires Inno
Setup; portable packaging is the supported fallback when `ISCC.exe` is absent.
