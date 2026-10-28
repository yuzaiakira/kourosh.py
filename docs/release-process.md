# Local alpha release process

Kourosh.py does not publish packages or create GitHub releases from the
repository. Prepare a candidate locally, review the machine-readable report,
and obtain separate owner approval before publishing through approved PyPI or
npm credentials.

1. Ensure `work` is clean and the required Git identity is configured.
2. Run `scripts/release-check.sh --` (the script takes no required options).
   Set `KOUROSH_RELEASE_REPORT=/tmp/kourosh-release.json` to choose the report
   path. The report records the commit, every check, artifact sizes, and
   SHA-256 values.
3. Review `CHANGELOG.md`, `RELEASE_NOTES_ALPHA.md`, compatibility, known
   limitations, and the Windows validation checklist.
4. Build the wheel/source archive locally. Do not upload them in this phase.
5. On a real Windows machine, execute `scripts/package-smoke.ps1`, retain the
   JSON results and manual observations, and complete the final platform gate.

The Python mapping is `0.1.0a1`, the browser SDK is `0.1.0-alpha.1`, Rust
components remain `0.1.0`, the human release is `v0.1.0-alpha.1`, and the RPC
protocol is version 1. `scripts/version-check.py` rejects mismatches.

PyPI publication will require a trusted build environment, package metadata
review, license/dependency review, and an owner-approved upload. npm
publication will require the same review for `@kourosh/sdk`, its declarations,
and provenance. Neither registry is contacted by the local release tooling.
