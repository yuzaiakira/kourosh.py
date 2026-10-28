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

requests="${KOUROSH_STRESS_REQUESTS:-256}"
concurrency="${KOUROSH_STRESS_CONCURRENCY:-8}"
echo "Running bounded bridge stress: requests=$requests concurrency=$concurrency"
KOUROSH_STRESS_REQUESTS="$requests" \
KOUROSH_STRESS_CONCURRENCY="$concurrency" \
cargo test -p kourosh-bridge bounded_stress_completes_without_active_work_leaking -- --nocapture
echo "Stress completed; inspect the Rust metrics assertions for active/queued cleanup."
