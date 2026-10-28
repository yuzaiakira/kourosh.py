#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

python3 scripts/check-docs.py
command -v zensical >/dev/null || {
  echo "zensical is required; install with: python3 -m pip install -r docs/requirements.txt" >&2
  exit 1
}
zensical build --clean
test -s site/index.html
echo "documentation site built: site/index.html"
