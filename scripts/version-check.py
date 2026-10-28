#!/usr/bin/env python3
"""Validate the alpha version mapping without importing build dependencies."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def cargo_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for manifest in sorted((ROOT / "crates").glob("*/Cargo.toml")):
        package = re.search(r'^name\s*=\s*"([^"]+)"', manifest.read_text(encoding="utf-8"), re.MULTILINE)
        version = re.search(r'^version\s*=\s*"([^"]+)"', manifest.read_text(encoding="utf-8"), re.MULTILINE)
        if package and version:
            versions[package.group(1)] = version.group(1)
    return versions


def package_version(path: Path) -> str:
    return json.loads(path.read_text(encoding="utf-8"))["version"]


def main() -> int:
    parser = argparse.ArgumentParser(description="check Kourosh.py release version consistency")
    parser.add_argument("--json", action="store_true", help="emit a machine-readable report")
    args = parser.parse_args()

    mapping = json.loads((ROOT / "version.json").read_text(encoding="utf-8"))
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    checks: list[dict[str, object]] = []

    def check(name: str, actual: object, expected: object) -> None:
        checks.append({"name": name, "status": "passed" if actual == expected else "failed", "actual": actual, "expected": expected})

    check("python-source", mapping["python"], project["version"])
    sys.path.insert(0, str(ROOT / "python"))
    from kourosh import __version__  # noqa: PLC0415

    check("python-runtime", __version__, mapping["python"])
    check("javascript-package", package_version(ROOT / "packages/sdk/package.json"), mapping["javascript"])
    check(
        "generated-javascript-package",
        package_version(ROOT / "examples/notes-react-ts/vendor/@kourosh/sdk/package.json"),
        mapping["javascript"],
    )
    for name, version in cargo_versions().items():
        check(f"rust:{name}", version, mapping["rust"])
    bridge_source = (ROOT / "crates/kourosh-bridge/src/lib.rs").read_text(encoding="utf-8")
    check("rust-protocol", f"PROTOCOL_VERSION: u8 = {mapping['protocol']};" in bridge_source, True)
    sdk_source = (ROOT / "packages/sdk/kourosh.js").read_text(encoding="utf-8")
    check("javascript-protocol", f"PROTOCOL_VERSION = {mapping['protocol']}" in sdk_source, True)
    failed = [item for item in checks if item["status"] == "failed"]
    report = {"schema": 1, "mapping": mapping, "checks": checks, "ok": not failed}
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        for item in checks:
            print(f"[{item['status']}] {item['name']}: {item['actual']} (expected {item['expected']})")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
