#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if [[ -x /workspace/.cargo/bin/cargo ]]; then
  export PATH="/workspace/.cargo/bin:$PATH"
  export RUSTUP_HOME="${RUSTUP_HOME:-/workspace/.rustup}"
  export CARGO_HOME="${CARGO_HOME:-/workspace/.cargo}"
  export RUSTUP_TOOLCHAIN="${RUSTUP_TOOLCHAIN:-stable}"
fi
command -v cargo >/dev/null || { echo "cargo is required" >&2; exit 1; }

# PyO3 links an embedded interpreter. Some managed Python distributions report
# a build-time `/install/lib` path after relocation, so add the interpreter's
# real sibling lib directory to both the linker and runtime search paths.
PYTHON_FOR_PYO3="${PYO3_PYTHON:-$(command -v python3)}"
PYTHON_FOR_PYO3="$(readlink -f "$PYTHON_FOR_PYO3")"
PYTHON_PREFIX="$(cd "$(dirname "$PYTHON_FOR_PYO3")/.." && pwd)"
for candidate in "$PYTHON_PREFIX/lib" "$PYTHON_PREFIX/lib"/*; do
  if compgen -G "$candidate/libpython*.so*" >/dev/null 2>&1; then
    export PYO3_PYTHON="$PYTHON_FOR_PYO3"
    export RUSTFLAGS="${RUSTFLAGS:-} -L native=$candidate"
    export LD_LIBRARY_PATH="$candidate${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    break
  fi
done

cargo fmt --all -- --check
cargo test --workspace
cargo clippy --workspace --all-targets -- -D warnings

PYTHONPATH="$repo_root/python${PYTHONPATH:+:$PYTHONPATH}" python3 -m compileall -q python tests
PYTHONPATH="$repo_root/python${PYTHONPATH:+:$PYTHONPATH}" python3 -m unittest discover -s tests -p 'test_*.py' -q
python3 scripts/version-check.py --json >/dev/null
if command -v node >/dev/null 2>&1; then
  node --check examples/hello-vanilla/bridge.js
  node --check examples/hello-vanilla/app.js
  node --check examples/notes-react-ts/public/kourosh-bridge.js
  node --check packages/sdk/kourosh.js
  node --check packages/sdk/index.js
  node --check scripts/bench-sdk.mjs
  bash -n scripts/bench-cli.sh
  bash -n scripts/stress.sh
  bash -n scripts/release-check.sh
  node tests/bridge.test.js
else
  echo "node is not installed; JavaScript syntax checks were not run" >&2
fi

case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) ;;
  *) echo "Windows WRY/WebView2 GUI smoke test not run on this host" ;;
esac

if command -v zensical >/dev/null 2>&1; then
  ./scripts/docs-check.sh
else
  echo "Zensical is not installed; documentation site checks were not run" >&2
fi
