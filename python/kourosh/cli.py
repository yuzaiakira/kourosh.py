"""Command-line tooling for creating and running Kourosh applications."""

from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from . import __version__, _find_host_binary


@dataclass(frozen=True)
class ProjectConfig:
    title: str
    width: int
    height: int
    entrypoint: Path
    frontend: Path


def load_config(project_root: Path) -> ProjectConfig:
    config_path = project_root / "kourosh.toml"
    try:
        with config_path.open("rb") as stream:
            raw = tomllib.load(stream)
    except FileNotFoundError as error:
        raise ValueError(f"missing project configuration: {config_path}") from error
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"invalid TOML in {config_path}: {error}") from error
    section = raw.get("app")
    if not isinstance(section, dict):
        raise ValueError("kourosh.toml must contain an [app] table")
    title = section.get("title")
    width = section.get("width", 960)
    height = section.get("height", 640)
    entrypoint = section.get("entrypoint", "main.py")
    frontend = section.get("frontend", "ui/index.html")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("[app].title must be a non-empty string")
    if not isinstance(width, int) or not isinstance(height, int):
        raise ValueError("[app].width and [app].height must be integers")
    if not 1 <= width <= 16_384 or not 1 <= height <= 16_384:
        raise ValueError("[app].width and [app].height must be between 1 and 16384")
    if len(title.encode("utf-8")) > 256:
        raise ValueError("[app].title must be at most 256 bytes")
    if not isinstance(entrypoint, str) or not isinstance(frontend, str):
        raise ValueError("[app].entrypoint and [app].frontend must be strings")
    entrypoint_path = _safe_project_path(project_root, entrypoint, "entrypoint")
    frontend_path = _safe_project_path(project_root, frontend, "frontend")
    if not entrypoint_path.is_file():
        raise ValueError(f"entrypoint does not exist: {entrypoint_path}")
    if not frontend_path.is_file():
        raise ValueError(f"frontend does not exist: {frontend_path}")
    return ProjectConfig(title, width, height, entrypoint_path, frontend_path)


def create_project(name: str, destination: Path) -> Path:
    if not _valid_project_name(name):
        raise ValueError("project name must match [A-Za-z][A-Za-z0-9_-]{0,63}")
    root = (destination / name).resolve()
    if root.exists():
        raise FileExistsError(f"destination already exists: {root}")
    (root / "ui").mkdir(parents=True)
    (root / "assets").mkdir()
    files = {
        "main.py": _MAIN_PY,
        "kourosh.toml": _TOML,
        "ui/index.html": _INDEX_HTML,
        "ui/style.css": _STYLE_CSS,
        "ui/app.js": _APP_JS,
        "ui/kourosh.js": _BRIDGE_JS,
    }
    for relative, content in files.items():
        target = root / relative
        target.write_text(content, encoding="utf-8", newline="\n")
    return root


def run_dev(project: Path) -> int:
    project = project.resolve()
    config = load_config(project)
    if sys.platform != "win32":
        print(
            "kourosh dev requires Windows WebView2; project validation passed, but no mock host was launched",
            file=sys.stderr,
        )
        return 2
    host = _find_host_binary()
    if host is None:
        raise RuntimeError("kourosh-host was not found; set KOUROSH_HOST_BIN or build the Windows host")
    environment = os.environ.copy()
    environment["KOUROSH_HOST_APP"] = "1"
    framework_python = Path(__file__).resolve().parent.parent
    old_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = str(framework_python) + (
        os.pathsep + old_pythonpath if old_pythonpath else ""
    )
    command = [
        str(host),
        "--app",
        str(config.entrypoint),
        "--frontend",
        str(config.frontend),
        "--title",
        config.title,
        "--width",
        str(config.width),
        "--height",
        str(config.height),
    ]
    try:
        return subprocess.run(command, cwd=project, env=environment, check=False).returncode
    except KeyboardInterrupt:
        return 130


def doctor() -> int:
    print(f"kourosh {__version__}")
    print(f"Python: {platform.python_version()} ({sys.executable})")
    print(f"Platform: {platform.system()} {platform.machine()}")
    host = _find_host_binary()
    print(f"Native host: {host if host else 'not found'}")
    if sys.platform != "win32":
        print("WebView2 GUI: unavailable on this platform (Windows x64 is the initial target)")
        return 0
    print(f"WebView2 runtime: {'check Windows installation' if _webview2_present() else 'not detected'}")
    return 0 if host and _webview2_present() else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kourosh", description="Python-first desktop development tools")
    parser.add_argument("--version", action="version", version=f"kourosh {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="create a vanilla JavaScript project")
    create.add_argument("name")
    create.add_argument("--directory", type=Path, default=Path.cwd())

    dev = subparsers.add_parser("dev", help="run the native development host")
    dev.add_argument("path", type=Path, nargs="?", default=Path.cwd())

    subparsers.add_parser("doctor", help="check local runtime prerequisites")
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            root = create_project(args.name, args.directory)
            print(f"Created {root}")
            return 0
        if args.command == "dev":
            return run_dev(args.path)
        return doctor()
    except (FileExistsError, OSError, RuntimeError, ValueError) as error:
        print(f"kourosh: error: {error}", file=sys.stderr)
        return 2


def _valid_project_name(name: str) -> bool:
    return bool(name) and name[0] in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz" and all(
        character in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-" for character in name
    ) and len(name) <= 64


def _safe_project_path(root: Path, value: str, label: str) -> Path:
    candidate = (root / value).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as error:
        raise ValueError(f"{label} path must stay inside the project") from error
    return candidate


def _webview2_present() -> bool:
    if sys.platform != "win32":
        return False
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    return any(
        (Path(program_files_x86) / relative).exists()
        for relative in (
            r"Microsoft\EdgeWebView\Application",
            r"Microsoft\EdgeUpdate\MicrosoftEdgeUpdate.exe",
        )
    )


_TOML = """[app]\ntitle = \"Hello Kourosh\"\nwidth = 1000\nheight = 700\nentrypoint = \"main.py\"\nfrontend = \"ui/index.html\"\n"""
_MAIN_PY = '''from kourosh import App\n\napp = App(title="Hello Kourosh", width=1000, height=700)\n\n@app.expose\ndef greet(name: str) -> dict[str, str]:\n    return {"message": f"Hello {name}!"}\n\napp.run()\n'''
_INDEX_HTML = '''<!doctype html>\n<html lang="en">\n<head>\n  <meta charset="utf-8">\n  <meta name="viewport" content="width=device-width, initial-scale=1">\n  <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none';">\n  <title>Hello Kourosh</title>\n  <link rel="stylesheet" href="style.css">\n</head>\n<body>\n  <main>\n    <h1>Hello Kourosh</h1>\n    <form id="greet-form">\n      <label for="name">Name</label>\n      <input id="name" value="Akira" maxlength="256" autocomplete="off">\n      <button>Greet from Python</button>\n    </form>\n    <output id="result" aria-live="polite"></output>\n  </main>\n  <script src="kourosh.js"></script>\n  <script src="app.js"></script>\n</body>\n</html>\n'''
_STYLE_CSS = """body { font: 16px system-ui, sans-serif; margin: 3rem; }\nmain { max-width: 42rem; }\nform { display: grid; gap: .75rem; max-width: 20rem; }\noutput { display: block; margin-top: 1rem; }\n"""
_APP_JS = '''document.getElementById("greet-form").addEventListener("submit", async (event) => {\n  event.preventDefault();\n  const result = document.getElementById("result");\n  result.textContent = "Calling Python…";\n  try {\n    const response = await window.kourosh.invoke("greet", { name: document.getElementById("name").value });\n    result.textContent = response.message;\n  } catch (error) {\n    result.textContent = `${error.code || "error"}: ${error.message || "bridge call failed"}`;\n  }\n});\n'''
_BRIDGE_JS = '''(() => {\n  "use strict";\n  const MAX_REQUEST_BYTES = 64 * 1024;\n  const MAX_PENDING_REQUESTS = 32;\n  const DEFAULT_TIMEOUT_MS = 5000;\n  const pending = new Map();\n  let sequence = 0;\n  const nextId = () => `js-${Date.now().toString(36)}-${(++sequence).toString(36)}`;\n  window.__kouroshReceive = (response) => {\n    if (!response || typeof response.id !== "string") return;\n    const call = pending.get(response.id);\n    if (!call) return;\n    pending.delete(response.id);\n    clearTimeout(call.timer);\n    response.ok === true ? call.resolve(response.result) : call.reject(response.error || { code: "unknown_error", message: "bridge call failed" });\n  };\n  window.__kouroshRejectAll = (error = { code: "window_closed", message: "window is closing" }) => {\n    for (const call of pending.values()) { clearTimeout(call.timer); call.reject(error); }\n    pending.clear();\n  };\n  window.kourosh = Object.freeze({ invoke(method, args, options = {}) {\n    if (typeof method !== "string" || !method) return Promise.reject({ code: "invalid_method", message: "method must be a non-empty string" });\n    if (pending.size >= MAX_PENDING_REQUESTS) return Promise.reject({ code: "busy", message: "too many bridge calls are in flight" });\n    const id = nextId();\n    const raw = JSON.stringify({ id, method, args });\n    if (new TextEncoder().encode(raw).byteLength > MAX_REQUEST_BYTES) return Promise.reject({ code: "request_too_large", message: "request exceeds the bridge limit" });\n    if (!window.ipc || typeof window.ipc.postMessage !== "function") return Promise.reject({ code: "bridge_unavailable", message: "the native host IPC channel is unavailable" });\n    const timeoutMs = Number.isFinite(options.timeoutMs) && options.timeoutMs > 0 ? Math.min(options.timeoutMs, DEFAULT_TIMEOUT_MS) : DEFAULT_TIMEOUT_MS;\n    return new Promise((resolve, reject) => {\n      const timer = setTimeout(() => { pending.delete(id); reject({ code: "timeout", message: "the bridge call timed out" }); }, timeoutMs);\n      pending.set(id, { resolve, reject, timer });\n      try { window.ipc.postMessage(raw); } catch (_error) { pending.delete(id); clearTimeout(timer); reject({ code: "transport_error", message: "the native IPC channel rejected the request" }); }\n    });\n  }});\n})();\n'''


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
