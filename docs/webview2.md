# WebView2 prerequisite

Kourosh.py uses Microsoft's Evergreen WebView2 Runtime supplied by the
operating system. It does not bundle a Chromium distribution and does not
download executable code during application startup.

On Windows, `kourosh doctor` checks the standard Evergreen installation
locations and reports an actionable missing-runtime error. Install the
Evergreen Runtime using Microsoft's official bootstrapper for online
deployment. For offline deployment, distribute Microsoft's official Evergreen
standalone installer through the organization's normal software channel and
run it as a prerequisite before the Kourosh package. The exact installer and
version policy must follow Microsoft's current redistribution terms.

The portable package records this prerequisite in `runtime/README.txt`. An
installer build generated with Inno Setup uses a per-user installation by
default; teams should add their approved WebView2 prerequisite check to their
installer policy before public distribution. No code-signing key is embedded
or required for local builds.
