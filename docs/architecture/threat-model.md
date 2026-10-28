# Initial threat model

The renderer is treated as potentially compromised. The host rejects
unapproved navigation, checks the trusted local document policy before bridge
dispatch, validates every envelope, bounds payloads, applies a timeout, and
uses a default-deny method registry. Python receives only validated arguments.

The package itself is trusted input for this prototype; a malicious package,
dependency supply-chain compromise, and renderer escape still require code
signing, dependency audits, capability scoping, and Windows packaging review.
No credentials are passed through the demo bridge, and no network request is
made by the template.
