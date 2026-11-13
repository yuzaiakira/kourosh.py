#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
export PYTHONPATH="$repo_root/python${PYTHONPATH:+:$PYTHONPATH}"

now_ns() { date +%s%N; }
measure_command() {
  local name="$1"
  shift
  local started elapsed
  started="$(now_ns)"
  "$@" >/dev/null
  elapsed="$((($(now_ns) - started) / 1000000))"
  echo "${name}_elapsed_ms=${elapsed}"
}

measure_command cli_version python3 -m kourosh.cli --version
measure_command cli_doctor_json python3 -m kourosh.cli doctor --json
echo "methodology=single-process wall-clock shell timing; excludes interpreter installation and Windows host startup"
