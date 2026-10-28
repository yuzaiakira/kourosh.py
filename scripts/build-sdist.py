#!/usr/bin/env python3
"""Build a deterministic local source archive without publishing anything."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import tarfile
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {".git", "target", "node_modules", "dist", "__pycache__"}
INCLUDED_ROOTS = ("AGENTS.md", "PRD.md", "README.md", "CONTRIBUTING.md", "LICENSE", "pyproject.toml", "Cargo.toml", "Cargo.lock", "version.json", "CHANGELOG.md")
INCLUDED_DIRS = ("python", "crates", "packages", "examples", "docs", "scripts", "tests")


def files_to_archive() -> list[Path]:
    files = [ROOT / name for name in INCLUDED_ROOTS if (ROOT / name).is_file()]
    for directory in INCLUDED_DIRS:
        base = ROOT / directory
        if not base.is_dir():
            continue
        files.extend(
            path
            for path in base.rglob("*")
            if path.is_file() and not any(part in EXCLUDED_PARTS for part in path.relative_to(ROOT).parts)
        )
    return sorted(set(files))


def main() -> int:
    parser = argparse.ArgumentParser(description="build a reproducible Kourosh.py source archive")
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/kourosh-sdist"))
    args = parser.parse_args()
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / f"kourosh-{version}.tar.gz"
    top = f"kourosh-{version}"
    with archive.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as tar:
                for path in files_to_archive():
                    relative = path.relative_to(ROOT)
                    data = path.read_bytes()
                    info = tarfile.TarInfo(f"{top}/{relative.as_posix()}")
                    info.size = len(data)
                    info.mode = 0o644
                    info.mtime = 0
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    tar.addfile(info, io.BytesIO(data))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    print(f"source_archive={archive}")
    print(f"sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
