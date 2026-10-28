# Contributing

Install Python 3.12 and the Rust stable toolchain. From the repository root,
run `scripts/check.sh`; on Windows use `scripts/check.ps1`. These checks are
local and intentionally do not require GitHub Actions.

Keep application logic in Python and native lifecycle code in Rust. Add bridge
methods only with explicit validation, origin policy, bounded inputs, structured
errors, and positive and negative tests. Do not add `.github/workflows` files.

Before every commit, configure and verify the repository-local identity:

```sh
git config --local user.name "Akira Yuzai"
git config --local user.email "yuzai.akira@gmail.com"
git diff --check
```
