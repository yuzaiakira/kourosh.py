# Initial threat model

The renderer is treated as potentially compromised. The host rejects
unapproved navigation, checks the trusted local document policy before bridge
dispatch, validates every envelope, bounds payloads, applies a timeout, and
uses a default-deny method registry. A developer app's method list is read
from its explicit Python registry and enforced again in Rust. Python receives
only validated arguments. Frontend files are canonicalized under the
configured project directory before the custom protocol serves them.

The package itself is trusted input for this prototype; a malicious package,
dependency supply-chain compromise, and renderer escape still require code
signing, dependency audits, capability scoping, and Windows packaging review.
No credentials are passed through the demo bridge, and no network request is
made by the template.

Vite development is a separate trust mode. The server is bound to
`127.0.0.1`, the chosen port is passed to the native host, and Rust accepts
only the exact `http://127.0.0.1:<port>` origin. Remote pages, alternate
loopback names, wildcard hosts, and different ports cannot use the bridge.
Production uses the existing `https://kourosh.app` custom protocol and does
not start a development server.

Portable packaging adds a second boundary around resources: the build rejects
symlinks and path escapes, writes only a new artifact directory, validates the
host as a Windows x64 PE file, and requires the CPython DLL, standard-library
ZIP, and redistribution notice. At startup the native host validates the
packaged manifest against the executable directory and clears ambient
`PYTHONPATH`/user-site imports. A package can still contain a malicious Python
application or dependency; package signing, dependency review, and clean-VM
verification remain release responsibilities.
