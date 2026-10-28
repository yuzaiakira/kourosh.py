$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

cargo fmt --all -- --check
cargo test --workspace
cargo clippy --workspace --all-targets -- -D warnings

$env:PYTHONPATH = "$RepoRoot/python;$env:PYTHONPATH"
python -m compileall -q python tests
python -m unittest discover -s tests -p "test_*.py" -q
if (Get-Command node -ErrorAction SilentlyContinue) {
    node --check examples/hello-vanilla/bridge.js
    node --check examples/hello-vanilla/app.js
    node --check packages/sdk/kourosh.js
    node --check packages/sdk/index.js
    node --check scripts/bench-sdk.mjs
    node tests/bridge.test.js
} else {
    Write-Warning "node is not installed; JavaScript syntax checks were not run"
}

if ($env:OS -ne "Windows_NT") {
    Write-Output "Windows WRY/WebView2 GUI smoke test not run on this host"
}
