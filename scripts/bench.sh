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

echo "Building the release runtime benchmark..."
cargo build --release -p kourosh-python --example runtime_bench

report_dir="${KOUROSH_BENCH_REPORT_DIR:-/tmp/kourosh-bench}"
mkdir -p "$report_dir"
commit="$(git rev-parse HEAD)"
rust_version="$(rustc --version)"
python_version="$(python3 --version 2>&1)"
run_benchmark() {
  local metrics_mode="$1"
  local report_path="$report_dir/${metrics_mode}-${commit}.json"
  echo "Measured embedded-Python RPC benchmark: metrics=$metrics_mode report=$report_path"
  KOUROSH_BENCH_METRICS="$metrics_mode" \
  KOUROSH_BENCH_REPORT="$report_path" \
  KOUROSH_BENCH_COMMIT="$commit" \
  KOUROSH_RUST_VERSION="$rust_version" \
  KOUROSH_PYTHON_VERSION="$python_version" \
  target/release/examples/runtime_bench
}

run_benchmark enabled
if [[ "${KOUROSH_BENCH_COMPARE_METRICS:-1}" != "0" ]]; then
  run_benchmark disabled
fi

case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*)
    cargo build --release -p kourosh-host
    /usr/bin/time -f 'host_process_max_rss_kb=%M' target/release/kourosh-host.exe
    ;;
  *)
    echo "host_startup=not-measured (Windows WebView2 is required)"
    echo "host_idle_memory=not-measured (Windows WebView2 is required)"
    ;;
esac
