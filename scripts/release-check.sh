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

report_path="${KOUROSH_RELEASE_REPORT:-/tmp/kourosh-release-check-$(date +%Y%m%dT%H%M%SZ).json}"
work_dir="$(mktemp -d /tmp/kourosh-release-check.XXXXXX)"
artifact_dir="$work_dir/artifacts"
log_dir="$work_dir/logs"
mkdir -p "$artifact_dir" "$log_dir"
entries="$work_dir/checks.tsv"
: > "$entries"

record() {
  printf '%s\t%s\t%s\n' "$1" "$2" "$3" >> "$entries"
}

run_check() {
  local name="$1"
  shift
  local log="$log_dir/$name.log"
  if "$@" >"$log" 2>&1; then
    record "$name" passed "${3:-command completed}"
  else
    record "$name" failed "see $log"
  fi
}

run_shell_check() {
  local name="$1"
  local command="$2"
  local log="$log_dir/$name.log"
  if bash -lc "$command" >"$log" 2>&1; then
    record "$name" passed "command completed"
  else
    record "$name" failed "see $log"
  fi
}

run_shell_check clean_worktree 'test -z "$(git status --porcelain)"'
run_check version_consistency python3 scripts/version-check.py --json
run_check python_tests env PYTHONPATH="$repo_root/python" python3 -m unittest discover -s tests -p 'test_*.py' -q
run_shell_check python_compile 'PYTHONPATH=python python3 -m compileall -q python tests'
run_check rust_format cargo fmt --all -- --check

python_for_pyo3="${PYO3_PYTHON:-$(command -v python3)}"
python_for_pyo3="$(readlink -f "$python_for_pyo3")"
python_prefix="$(cd "$(dirname "$python_for_pyo3")/.." && pwd)"
for candidate in "$python_prefix/lib" "$python_prefix/lib"/*; do
  if compgen -G "$candidate/libpython*.so*" >/dev/null 2>&1; then
    export PYO3_PYTHON="$python_for_pyo3"
    export RUSTFLAGS="${RUSTFLAGS:-} -L native=$candidate"
    export LD_LIBRARY_PATH="$candidate${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    break
  fi
done

run_check rust_tests cargo test --workspace
run_check rust_clippy cargo clippy --workspace --all-targets -- -D warnings
run_check windows_target_clippy env PYO3_CROSS=1 PYO3_CROSS_PYTHON_VERSION=3.12 cargo clippy -p kourosh-host --target x86_64-pc-windows-gnu -- -D warnings
run_check wheel_build env WHEEL_DIR="$artifact_dir" python3 -m pip wheel --no-deps --no-build-isolation --wheel-dir "$artifact_dir" .
run_check source_archive python3 scripts/build-sdist.py --output-dir "$artifact_dir"
run_check license_metadata bash -lc 'test -s LICENSE && test -s docs/dependencies-licensing.md'
run_shell_check docs_consistency 'for file in CHANGELOG.md RELEASE_NOTES_ALPHA.md docs/release-process.md docs/compatibility.md docs/known-limitations.md docs/alpha-release-checklist.md docs/api-stability.md; do test -s "$file" || exit 1; done'
run_check docs_site ./scripts/docs-check.sh
run_shell_check no_workflows 'test ! -d .github/workflows'
run_check javascript_tests node tests/bridge.test.js
run_shell_check javascript_syntax 'node --check packages/sdk/index.js && node --check packages/sdk/kourosh.js && node --check examples/hello-vanilla/bridge.js && node --check examples/hello-vanilla/app.js'
run_shell_check frontend_checks 'cd examples/notes-react-ts && npm run typecheck && npm run build'
run_check packaging_tests env PYTHONPATH="$repo_root/python" python3 -m unittest tests.test_package -q

python3 - "$entries" "$report_path" "$artifact_dir" <<'PY'
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

entries_path, report_path, artifact_dir = map(Path, sys.argv[1:])
checks = []
for line in entries_path.read_text(encoding="utf-8").splitlines():
    name, status, detail = line.split("\t", 2)
    checks.append({"name": name, "status": status, "detail": detail})
artifacts = []
for path in sorted(artifact_dir.glob("*")):
    if path.is_file():
        artifacts.append({"name": path.name, "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
report = {
    "schema": 1,
    "tool": "kourosh-release-check",
    "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
    "branch": subprocess.check_output(["git", "branch", "--show-current"], text=True).strip(),
    "platform": {"system": os.name, "python": sys.version.split()[0]},
    "checks": checks,
    "artifacts": artifacts,
    "ok": all(item["status"] == "passed" for item in checks),
}
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"release_check_report={report_path}")
print(json.dumps({"ok": report["ok"], "failed": [item["name"] for item in checks if item["status"] != "passed"]}))
raise SystemExit(0 if report["ok"] else 1)
PY
