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
mode="${KOUROSH_STRESS_MODE:-quick}"
case "$mode" in
  quick) soak_duration_ms="${KOUROSH_SOAK_DURATION_MS:-1000}" ;;
  standard) soak_duration_ms="${KOUROSH_SOAK_DURATION_MS:-300000}" ;;
  extended) soak_duration_ms="${KOUROSH_SOAK_DURATION_MS:-900000}" ;;
  *) echo "KOUROSH_STRESS_MODE must be quick, standard, or extended" >&2; exit 2 ;;
esac
echo "Running bounded bridge stress: requests=$requests concurrency=$concurrency mode=$mode soak_ms=$soak_duration_ms"
KOUROSH_STRESS_REQUESTS="$requests" \
KOUROSH_STRESS_CONCURRENCY="$concurrency" \
KOUROSH_SOAK_DURATION_MS="$soak_duration_ms" \
KOUROSH_SOAK_CONCURRENCY="$concurrency" \
cargo test -p kourosh-bridge bounded_stress_completes_without_active_work_leaking -- --nocapture
KOUROSH_SOAK_DURATION_MS="$soak_duration_ms" \
KOUROSH_SOAK_CONCURRENCY="$concurrency" \
cargo test -p kourosh-bridge bounded_soak_handles_bursts_and_cleans_up_after_shutdown -- --nocapture
echo "Stress and soak completed; inspect the Rust metrics assertions for active/queued cleanup."
