# WebView selection and origin policy

The Windows host is Rust plus TAO and WRY over Microsoft WebView2. The host
serves packaged or developer-configured local HTML, JavaScript, and CSS through
WRY's `kourosh` custom protocol (mapped to the explicit
`https://kourosh.app` origin on Windows) and rejects navigation outside that
origin. Developer resource paths are canonicalized under the configured
frontend directory and traversal-like request paths return 404. The bridge IPC
handler repeats the origin check using the request URI before dispatching work.

This Linux environment cannot instantiate WebView2. The Windows compile and
manual smoke test are therefore explicitly unverified until run on a Windows
10/11 x64 host with the WebView2 runtime installed. The reproducible procedure
is [docs/windows-smoke-test.md](../windows-smoke-test.md), launched by
`scripts/smoke.ps1`.
