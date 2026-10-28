# Contributing

Install Python 3.12 and the Rust stable toolchain. From the repository root,
run `scripts/check.sh`; on Windows use `scripts/check.ps1`. These checks are
local and intentionally do not require GitHub Actions.

Keep application logic in Python and native lifecycle code in Rust. Add bridge
methods only with explicit validation, origin policy, bounded inputs, structured
errors, and positive and negative tests. Do not add `.github/workflows` files.

For SDK and CLI work, install the package in editable mode and exercise the
generated project without a Node.js runtime:

```sh
python -m pip install -e .
kourosh create scratch-app
kourosh doctor
```

Run `kourosh dev` on Windows with WebView2 to exercise the native host. On
Linux, it validates the project and reports the Windows-only limitation rather
than launching a simulated desktop process. Keep generated-project tests in
the standard-library test suite so they run through `scripts/check.sh`.

Before every commit, configure and verify the repository-local identity:

```sh
git config --local user.name "Akira Yuzai"
git config --local user.email "yuzai.akira@gmail.com"
git diff --check
```
