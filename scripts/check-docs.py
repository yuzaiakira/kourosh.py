#!/usr/bin/env python3
"""Validate the local documentation structure without contacting a service."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
CONFIG = ROOT / "zensical.toml"
LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
CLI_COMMANDS = ("create", "dev", "run", "frontend", "build", "doctor")


def nav_paths(value: object) -> list[str]:
    paths: list[str] = []
    if isinstance(value, str):
        if value.endswith(".md"):
            paths.append(value)
    elif isinstance(value, list):
        for item in value:
            paths.extend(nav_paths(item))
    elif isinstance(value, dict):
        for item in value.values():
            paths.extend(nav_paths(item))
    return paths


def check_nav(errors: list[str]) -> None:
    if not CONFIG.is_file():
        errors.append("missing zensical.toml")
        return
    config = tomllib.loads(CONFIG.read_text(encoding="utf-8"))
    project = config.get("project", {})
    for target in nav_paths(project.get("nav", [])):
        path = DOCS / target
        if not path.is_file():
            errors.append(f"navigation target does not exist: {target}")


def check_markdown(errors: list[str]) -> None:
    for page in sorted(DOCS.rglob("*.md")):
        lines = page.read_text(encoding="utf-8").splitlines()
        fence = None
        python_block: list[str] | None = None
        python_start = 0
        for number, line in enumerate(lines, start=1):
            match = FENCE_RE.match(line)
            if match:
                marker = match.group(1)[0]
                if fence is None:
                    fence = marker
                    language = line[match.end() :].strip().split()[0] if line[match.end() :].strip() else ""
                    if language in {"python", "py"}:
                        python_block = []
                        python_start = number
                elif marker == fence:
                    fence = None
                    if python_block is not None:
                        try:
                            compile("\n".join(python_block), f"{page}:{python_start}", "exec")
                        except SyntaxError as error:
                            errors.append(f"invalid Python example in {page}:{python_start}: {error.msg}")
                        python_block = None
                elif python_block is not None:
                    python_block.append(line)
            elif python_block is not None:
                python_block.append(line)
        if fence is not None:
            errors.append(f"unclosed {fence * 3} fence: {page}")

        for match in LINK_RE.finditer("\n".join(lines)):
            target = match.group(1).strip().split()[0].strip("<>")
            parsed = urlsplit(target)
            if parsed.scheme or target.startswith("//") or target.startswith("#"):
                continue
            local = target.split("#", 1)[0]
            if not local:
                continue
            resolved = (page.parent / local).resolve()
            if not resolved.exists():
                errors.append(f"broken local link in {page}: {target}")


def run_cli_help(errors: list[str]) -> None:
    environment = dict(os.environ, PYTHONPATH=str(ROOT / "python"))
    commands = [("--help",)] + [(command, "--help") for command in CLI_COMMANDS]
    for arguments in commands:
        result = subprocess.run(
            [sys.executable, "-m", "kourosh.cli", *arguments],
            cwd=ROOT,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode != 0:
            errors.append(f"CLI help failed for {' '.join(arguments)}: {result.stderr.strip()}")


def check_versions(errors: list[str]) -> None:
    mapping = json.loads((ROOT / "version.json").read_text(encoding="utf-8"))
    required = (mapping["python"], mapping["javascript"], mapping["rust"], f"protocol {mapping['protocol']}")
    searchable = "\n".join(path.read_text(encoding="utf-8") for path in DOCS.rglob("*.md"))
    for value in required:
        if value not in searchable:
            errors.append(f"documented version value is missing: {value}")


def check_windows_language(errors: list[str]) -> None:
    misleading = (
        "windows gui validation passed",
        "windows validation is complete",
        "production-ready",
        "production ready",
    )
    for page in DOCS.rglob("*.md"):
        text = page.read_text(encoding="utf-8").lower()
        for phrase in misleading:
            if phrase in text and "not" not in text[max(0, text.find(phrase) - 80) : text.find(phrase) + len(phrase) + 80]:
                errors.append(f"possibly misleading Windows/release claim in {page}: {phrase}")


def main() -> int:
    errors: list[str] = []
    check_nav(errors)
    check_markdown(errors)
    run_cli_help(errors)
    check_versions(errors)
    check_windows_language(errors)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"documentation checks passed: {len(list(DOCS.rglob('*.md')))} Markdown pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
