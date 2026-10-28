#!/usr/bin/env bash
set -euo pipefail

project_root="${1:-.}"
project_root="$(cd "$project_root" && pwd)"
cd "$project_root"
command -v npm >/dev/null || { echo "npm is required" >&2; exit 1; }
[[ -d node_modules ]] || { echo "node_modules is missing; run npm install first" >&2; exit 1; }

now_ms() { date +%s%3N; }
build_started="$(now_ms)"
npm run build
build_elapsed_ms=$(("$(now_ms)" - build_started))
dist_bytes="$(du -sb dist | awk '{print $1}')"
echo "frontend_build_elapsed_ms=$build_elapsed_ms"
echo "frontend_dist_bytes=$dist_bytes"

dev_port="$(python3 - <<'PY'
import socket
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
    probe.bind(("127.0.0.1", 0))
    print(probe.getsockname()[1])
PY
)"
npm run dev -- --host 127.0.0.1 --port "$dev_port" --strictPort >/tmp/kourosh-vite-bench.log 2>&1 &
vite_pid=$!
cleanup() {
  kill "$vite_pid" 2>/dev/null || true
  wait "$vite_pid" 2>/dev/null || true
}
trap cleanup EXIT
server_started="$(now_ms)"
for _ in $(seq 1 100); do
  if python3 - "$dev_port" <<'PY'
import sys
import urllib.request
try:
    with urllib.request.urlopen(f"http://127.0.0.1:{sys.argv[1]}/", timeout=0.2) as response:
        raise SystemExit(0 if response.status == 200 else 1)
except Exception:
    raise SystemExit(1)
PY
  then
    echo "vite_dev_ready_elapsed_ms=$(("$(now_ms)" - server_started))"
    exit 0
  fi
  if ! kill -0 "$vite_pid" 2>/dev/null; then
    cat /tmp/kourosh-vite-bench.log >&2
    exit 1
  fi
  sleep 0.1
done
cat /tmp/kourosh-vite-bench.log >&2
echo "Vite did not become ready" >&2
exit 1
