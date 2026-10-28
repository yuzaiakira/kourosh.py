"""Command-line tooling for creating, building, and running Kourosh apps."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import signal
import socket
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from . import __version__, _find_host_binary


@dataclass(frozen=True)
class ProjectConfig:
    root: Path
    title: str
    width: int
    height: int
    entrypoint: Path
    frontend: Path
    frontend_type: str = "static"
    frontend_root: Path | None = None
    dev_port: int = 5173

    @property
    def resolved_frontend_root(self) -> Path:
        return self.frontend_root or self.frontend.parent


def load_config(project_root: Path, *, require_frontend: bool = True) -> ProjectConfig:
    root = project_root.resolve()
    config_path = root / "kourosh.toml"
    try:
        with config_path.open("rb") as stream:
            raw = tomllib.load(stream)
    except FileNotFoundError as error:
        raise ValueError(f"missing project configuration: {config_path}") from error
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"invalid TOML in {config_path}: {error}") from error

    app = raw.get("app")
    if not isinstance(app, dict):
        raise ValueError("kourosh.toml must contain an [app] table")
    title = app.get("title")
    width = app.get("width", 960)
    height = app.get("height", 640)
    entrypoint = app.get("entrypoint", "main.py")
    app_frontend = app.get("frontend", "ui/index.html")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("[app].title must be a non-empty string")
    if len(title.encode("utf-8")) > 256:
        raise ValueError("[app].title must be at most 256 bytes")
    if not isinstance(width, int) or isinstance(width, bool) or not isinstance(height, int) or isinstance(height, bool):
        raise ValueError("[app].width and [app].height must be integers")
    if not 1 <= width <= 16_384 or not 1 <= height <= 16_384:
        raise ValueError("[app].width and [app].height must be between 1 and 16384")
    if not isinstance(entrypoint, str) or not isinstance(app_frontend, str):
        raise ValueError("[app].entrypoint and [app].frontend must be strings")

    entrypoint_path = _safe_project_path(root, entrypoint, "entrypoint")
    if not entrypoint_path.is_file():
        raise ValueError(f"entrypoint does not exist: {entrypoint_path}")

    frontend_section = raw.get("frontend")
    if frontend_section is None:
        frontend_section = {}
    if not isinstance(frontend_section, dict):
        raise ValueError("[frontend] must be a TOML table")
    frontend_type = frontend_section.get("type", "static")
    if frontend_type not in {"static", "vite"}:
        raise ValueError("[frontend].type must be either 'static' or 'vite'")
    if frontend_type == "vite":
        frontend_root_value = frontend_section.get("root", ".")
        dist_value = frontend_section.get("dist", app_frontend)
        dev_port = frontend_section.get("dev_port", 5173)
        if not isinstance(frontend_root_value, str) or not isinstance(dist_value, str):
            raise ValueError("[frontend].root and [frontend].dist must be strings")
        if not isinstance(dev_port, int) or isinstance(dev_port, bool) or not 1024 <= dev_port <= 65_535:
            raise ValueError("[frontend].dev_port must be an integer from 1024 to 65535")
        frontend_root = _safe_project_path(root, frontend_root_value, "frontend root")
        frontend_path = _safe_project_path(root, dist_value, "frontend dist")
        if not (frontend_root / "package.json").is_file():
            raise ValueError(f"Vite project is missing package.json: {frontend_root / 'package.json'}")
        if require_frontend and not frontend_path.is_file():
            raise ValueError(f"built frontend does not exist: {frontend_path}; run 'kourosh frontend build'")
        return ProjectConfig(root, title, width, height, entrypoint_path, frontend_path, "vite", frontend_root, dev_port)

    frontend_path = _safe_project_path(root, app_frontend, "frontend")
    if require_frontend and not frontend_path.is_file():
        raise ValueError(f"frontend does not exist: {frontend_path}")
    return ProjectConfig(root, title, width, height, entrypoint_path, frontend_path)


def create_project(name: str, destination: Path, *, ui: str = "vanilla", typescript: bool = False) -> Path:
    if not _valid_project_name(name):
        raise ValueError("project name must match [A-Za-z][A-Za-z0-9_-]{0,63}")
    if ui not in {"vanilla", "react"}:
        raise ValueError("--ui must be vanilla or react")
    if typescript and ui != "react":
        raise ValueError("--typescript is supported only with --ui react")
    root = (destination / name).resolve()
    if root.exists():
        raise FileExistsError(f"destination already exists: {root}")
    (root / "assets").mkdir(parents=True)
    files = _vanilla_files() if ui == "vanilla" else _react_files(typescript)
    for relative, content in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
    return root


def run_frontend_build(project: Path) -> int:
    config = load_config(project, require_frontend=False)
    if config.frontend_type != "vite":
        raise ValueError("frontend build is available for Vite projects only")
    npm = _npm_command()
    if npm is None:
        raise RuntimeError("npm is required for Vite frontend builds")
    if not (config.resolved_frontend_root / "node_modules").is_dir():
        raise RuntimeError(f"frontend dependencies are missing; run 'npm install' in {config.resolved_frontend_root}")
    completed = subprocess.run([npm, "run", "build"], cwd=config.resolved_frontend_root, check=False)
    if completed.returncode != 0:
        return completed.returncode
    _validate_built_frontend(config)
    print(f"Built frontend: {config.frontend}")
    return 0


def run_dev(project: Path) -> int:
    project = project.resolve()
    config = load_config(project, require_frontend=False)
    if config.frontend_type != "vite":
        return _launch_native_host(config)
    npm = _npm_command()
    if npm is None:
        raise RuntimeError("npm is required for Vite development")
    if not (config.resolved_frontend_root / "node_modules").is_dir():
        raise RuntimeError(f"frontend dependencies are missing; run 'npm install' in {config.resolved_frontend_root}")
    port = _available_loopback_port(config.dev_port)
    server = _start_vite(npm, config.resolved_frontend_root, port)
    try:
        _wait_for_vite(server, port)
        if sys.platform != "win32":
            print(
                f"Vite development server is ready at http://127.0.0.1:{port}/; the native WRY/WebView2 host requires Windows, so no mock host was launched",
                file=sys.stderr,
            )
            return 2
        return _launch_native_host(config, dev_url=f"http://127.0.0.1:{port}/")
    finally:
        _stop_process(server)


def run_production(project: Path) -> int:
    config = load_config(project, require_frontend=True)
    return _launch_native_host(config)


def doctor() -> int:
    print(f"kourosh {__version__}")
    print(f"Python: {platform.python_version()} ({sys.executable})")
    print(f"Platform: {platform.system()} {platform.machine()}")
    print(f"Node.js: {shutil.which('node') or 'not found'}")
    print(f"npm: {shutil.which('npm') or shutil.which('npm.cmd') or 'not found'}")
    host = _find_host_binary()
    print(f"Native host: {host if host else 'not found'}")
    if sys.platform != "win32":
        print("WebView2 GUI: unavailable on this platform (Windows x64 is the initial target)")
        return 0
    print(f"WebView2 runtime: {'detected' if _webview2_present() else 'not detected'}")
    return 0 if host and _webview2_present() else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kourosh", description="Python-first desktop development tools")
    parser.add_argument("--version", action="version", version=f"kourosh {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="create a project")
    create.add_argument("name")
    create.add_argument("--directory", type=Path, default=Path.cwd())
    create.add_argument("--ui", choices=("vanilla", "react"), default="vanilla")
    create.add_argument("--template", choices=("vanilla", "react"), dest="template", help=argparse.SUPPRESS)
    create.add_argument("--typescript", action="store_true")

    dev = subparsers.add_parser("dev", help="run the development frontend and native host")
    dev.add_argument("path", type=Path, nargs="?", default=Path.cwd())

    run = subparsers.add_parser("run", help="run a built static frontend without Node.js")
    run.add_argument("path", type=Path, nargs="?", default=Path.cwd())

    frontend = subparsers.add_parser("frontend", help="frontend build tools")
    frontend_commands = frontend.add_subparsers(dest="frontend_command", required=True)
    build = frontend_commands.add_parser("build", help="build a Vite frontend")
    build.add_argument("path", type=Path, nargs="?", default=Path.cwd())

    subparsers.add_parser("doctor", help="check local runtime prerequisites")
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            ui = args.template or args.ui
            root = create_project(args.name, args.directory, ui=ui, typescript=args.typescript)
            print(f"Created {root}")
            return 0
        if args.command == "dev":
            return run_dev(args.path)
        if args.command == "run":
            return run_production(args.path)
        if args.command == "frontend":
            return run_frontend_build(args.path)
        return doctor()
    except (FileExistsError, OSError, RuntimeError, ValueError) as error:
        print(f"kourosh: error: {error}", file=sys.stderr)
        return 2


def _launch_native_host(config: ProjectConfig, *, dev_url: str | None = None) -> int:
    if sys.platform != "win32":
        print("the native WRY/WebView2 host requires Windows; no mock host was launched", file=sys.stderr)
        return 2
    host = _find_host_binary()
    if host is None:
        raise RuntimeError("kourosh-host was not found; set KOUROSH_HOST_BIN or build the Windows host")
    environment = os.environ.copy()
    environment["KOUROSH_HOST_APP"] = "1"
    framework_python = Path(__file__).resolve().parent.parent
    old_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = str(framework_python) + (os.pathsep + old_pythonpath if old_pythonpath else "")
    command = [str(host), "--app", str(config.entrypoint), "--title", config.title, "--width", str(config.width), "--height", str(config.height)]
    command.extend(["--dev-url", dev_url] if dev_url else ["--frontend", str(config.frontend)])
    try:
        return subprocess.run(command, cwd=config.root, env=environment, check=False).returncode
    except KeyboardInterrupt:
        return 130


def _validate_built_frontend(config: ProjectConfig) -> None:
    if not config.frontend.is_file():
        raise RuntimeError(f"Vite build did not create {config.frontend}")
    if config.frontend.stat().st_size == 0:
        raise RuntimeError(f"built frontend is empty: {config.frontend}")
    if not _is_within(config.frontend.resolve(), config.root):
        raise RuntimeError(f"built frontend escapes the project: {config.frontend}")


def _start_vite(npm: str, root: Path, port: int) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [npm, "run", "dev", "--", "--host", "127.0.0.1", "--port", str(port), "--strictPort"],
        cwd=root,
        start_new_session=os.name != "nt",
    )


def _wait_for_vite(process: subprocess.Popen[str], port: int, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    url = f"http://127.0.0.1:{port}/"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Vite exited before becoming ready; inspect the npm output above")
        try:
            with urllib.request.urlopen(url, timeout=0.5) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.1)
    raise RuntimeError(f"Vite did not become ready at {url}")


def _stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _available_loopback_port(preferred: int) -> int:
    for port in [preferred, *_free_ports()]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError("unable to allocate a loopback development port")


def _free_ports() -> Iterable[int]:
    for _ in range(8):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            yield probe.getsockname()[1]


def _npm_command() -> str | None:
    return shutil.which("npm") or shutil.which("npm.cmd")


def _valid_project_name(name: str) -> bool:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    allowed = alphabet + "0123456789_-"
    return bool(name) and name[0] in alphabet and all(character in allowed for character in name) and len(name) <= 64


def _safe_project_path(root: Path, value: str, label: str) -> Path:
    candidate = (root / value).resolve()
    if not _is_within(candidate, root.resolve()):
        raise ValueError(f"{label} path must stay inside the project")
    return candidate


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _webview2_present() -> bool:
    if sys.platform != "win32":
        return False
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    return any((Path(program_files_x86) / relative).exists() for relative in (r"Microsoft\EdgeWebView\Application", r"Microsoft\EdgeUpdate\MicrosoftEdgeUpdate.exe"))


def _common_python(ui: str) -> str:
    frontend = 'app.run("dist/index.html")' if ui == "react" else "app.run()"
    message = 'f"Hello {name} from Python!"' if ui == "react" else 'f"Hello {name}!"'
    return f'''from kourosh import App

app = App(title="Hello Kourosh", width=1000, height=700)

@app.expose
def greet(name: str) -> dict[str, str]:
    return {{"message": {message}}}

{frontend}
'''


def _bridge_file() -> str:
    return '''(() => {
  "use strict";
  if (window.__kouroshInstalled) return;
  window.__kouroshInstalled = true;
  const MAX_REQUEST_BYTES = 64 * 1024;
  const MAX_PENDING_REQUESTS = 32;
  const DEFAULT_TIMEOUT_MS = 5000;
  const pending = new Map();
  let sequence = 0;
  const nextId = () => `js-${Date.now().toString(36)}-${(++sequence).toString(36)}`;
  window.__kouroshReceive = (response) => {
    if (!response || typeof response.id !== "string") return;
    const call = pending.get(response.id);
    if (!call) return;
    pending.delete(response.id);
    clearTimeout(call.timer);
    response.ok === true ? call.resolve(response.result) : call.reject(response.error || { code: "unknown_error", message: "bridge call failed" });
  };
  window.__kouroshRejectAll = (error = { code: "window_closed", message: "window is closing" }) => {
    for (const call of pending.values()) { clearTimeout(call.timer); call.reject(error); }
    pending.clear();
  };
  window.addEventListener?.("beforeunload", () => window.__kouroshRejectAll({ code: "window_reloaded", message: "the renderer is reloading" }));
  window.kourosh = Object.freeze({ invoke(method, args, options = {}) {
    if (typeof method !== "string" || !method) return Promise.reject({ code: "invalid_method", message: "method must be a non-empty string" });
    if (pending.size >= MAX_PENDING_REQUESTS) return Promise.reject({ code: "busy", message: "too many bridge calls are in flight" });
    const id = nextId();
    const raw = JSON.stringify({ id, method, args });
    if (new TextEncoder().encode(raw).byteLength > MAX_REQUEST_BYTES) return Promise.reject({ code: "request_too_large", message: "request exceeds the bridge limit" });
    if (!window.ipc || typeof window.ipc.postMessage !== "function") return Promise.reject({ code: "bridge_unavailable", message: "the native host IPC channel is unavailable" });
    const timeoutMs = Number.isFinite(options.timeoutMs) && options.timeoutMs > 0 ? Math.min(options.timeoutMs, DEFAULT_TIMEOUT_MS) : DEFAULT_TIMEOUT_MS;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => { pending.delete(id); reject({ code: "timeout", message: "the bridge call timed out" }); }, timeoutMs);
      pending.set(id, { resolve, reject, timer });
      try { window.ipc.postMessage(raw); } catch (_error) { pending.delete(id); clearTimeout(timer); reject({ code: "transport_error", message: "the native IPC channel rejected the request" }); }
    });
  }});
})();
'''


def _sdk_files() -> dict[str, str]:
    sdk_root = Path(__file__).resolve().parents[2] / "packages" / "sdk"
    if sdk_root.is_dir():
        return {f"vendor/@kourosh/sdk/{name}": (sdk_root / name).read_text(encoding="utf-8") for name in ("package.json", "index.js", "index.d.ts")}
    return {"vendor/@kourosh/sdk/package.json": '{"name":"@kourosh/sdk","version":"0.1.0","private":true,"type":"module","exports":{".":{"types":"./index.d.ts","import":"./index.js"}}}\n', "vendor/@kourosh/sdk/index.js": _SDK_JS, "vendor/@kourosh/sdk/index.d.ts": _SDK_DTS}


def _vanilla_files() -> dict[str, str]:
    return {"main.py": _common_python("vanilla"), "kourosh.toml": '[app]\ntitle = "Hello Kourosh"\nwidth = 1000\nheight = 700\nentrypoint = "main.py"\nfrontend = "ui/index.html"\n', ".gitignore": "__pycache__/\n.venv/\nnode_modules/\ndist/\n", "ui/index.html": _VANILLA_HTML, "ui/style.css": _STYLE_CSS, "ui/app.js": _VANILLA_APP_JS, "ui/kourosh.js": _bridge_file()}


def _react_files(typescript: bool) -> dict[str, str]:
    extension = "tsx" if typescript else "jsx"
    files = {"main.py": _common_python("react"), "kourosh.toml": _REACT_TOML, ".gitignore": "__pycache__/\n.venv/\nnode_modules/\ndist/\n", "index.html": _REACT_HTML.format(extension=extension), "public/kourosh-bridge.js": _bridge_file(), "src/styles.css": _REACT_CSS, f"src/main.{extension}": _REACT_MAIN_TSX if typescript else _REACT_MAIN_JSX, f"src/App.{extension}": _REACT_APP_TSX if typescript else _REACT_APP_JSX, "package.json": json.dumps(_react_package(typescript), indent=2) + "\n", "vite.config.ts" if typescript else "vite.config.js": _VITE_CONFIG_TS if typescript else _VITE_CONFIG_JS}
    if typescript:
        files["tsconfig.json"] = _TSCONFIG
        files["tsconfig.node.json"] = _TSCONFIG_NODE
    files.update(_sdk_files())
    return files


def _react_package(typescript: bool) -> dict[str, object]:
    package: dict[str, object] = {"private": True, "type": "module", "scripts": {"dev": "vite", "build": "vite build"}, "dependencies": {"@kourosh/sdk": "file:vendor/@kourosh/sdk", "react": "^18.3.1", "react-dom": "^18.3.1"}, "devDependencies": {"@vitejs/plugin-react": "^4.3.0", "vite": "^5.4.0"}}
    if typescript:
        package["scripts"] = {**package["scripts"], "typecheck": "tsc --noEmit"}
        package["devDependencies"] = {**package["devDependencies"], "@types/react": "^18.3.3", "@types/react-dom": "^18.3.0", "typescript": "^5.5.4"}
    return package


_REACT_TOML = '''[app]
title = "Kourosh React"
width = 1000
height = 700
entrypoint = "main.py"
frontend = "dist/index.html"

[frontend]
type = "vite"
root = "."
dist = "dist/index.html"
dev_port = 5173
'''
_REACT_HTML = '''<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self' http://127.0.0.1:* ws://127.0.0.1:*; object-src 'none'; base-uri 'none';" />
    <title>Kourosh React</title>
  </head>
  <body>
    <div id="root"></div>
    <script src="/kourosh-bridge.js"></script>
    <script type="module" src="/src/main.{extension}"></script>
  </body>
</html>
'''
_REACT_MAIN_JSX = '''import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";

createRoot(document.getElementById("root")).render(<React.StrictMode><App /></React.StrictMode>);
'''
_REACT_MAIN_TSX = '''import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";

createRoot(document.getElementById("root")!).render(<React.StrictMode><App /></React.StrictMode>);
'''
_REACT_APP_JSX = '''import { useState } from "react";
import { invoke } from "@kourosh/sdk";

export default function App() {
  const [name, setName] = useState("Akira");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function greet() {
    setError("");
    try {
      const result = await invoke("greet", { name });
      setMessage(result.message);
    } catch (caught) {
      setError(`${caught.code}: ${caught.message}`);
    }
  }

  return <main><h1>Kourosh.py + React</h1><label>Name <input value={name} onChange={(event) => setName(event.target.value)} /></label><button onClick={greet}>Call Python</button><p aria-live="polite">{message || error}</p></main>;
}
'''
_REACT_APP_TSX = '''import { useState } from "react";
import { invoke, KouroshError } from "@kourosh/sdk";

type GreetResult = { message: string };

export default function App() {
  const [name, setName] = useState("Akira");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function greet(): Promise<void> {
    setError("");
    try {
      const result = await invoke<GreetResult>("greet", { name });
      setMessage(result.message);
    } catch (caught) {
      const error = caught instanceof KouroshError ? caught : new KouroshError({ code: "unknown_error", message: String(caught) });
      setError(`${error.code}: ${error.message}`);
    }
  }

  return <main><h1>Kourosh.py + React</h1><label>Name <input value={name} onChange={(event) => setName(event.target.value)} /></label><button onClick={greet}>Call Python</button><p aria-live="polite">{message || error}</p></main>;
}
'''
_VITE_CONFIG_JS = 'import { defineConfig } from "vite";\nimport react from "@vitejs/plugin-react";\nexport default defineConfig({ plugins: [react()] });\n'
_VITE_CONFIG_TS = _VITE_CONFIG_JS
_TSCONFIG = '{"compilerOptions":{"target":"ES2020","useDefineForClassFields":true,"lib":["ES2020","DOM","DOM.Iterable"],"skipLibCheck":true,"esModuleInterop":true,"allowSyntheticDefaultImports":true,"strict":true,"forceConsistentCasingInFileNames":true,"module":"ESNext","moduleResolution":"Bundler","resolveJsonModule":true,"isolatedModules":true,"noEmit":true,"jsx":"react-jsx"},"include":["src","vite.config.ts"]}\n'
_TSCONFIG_NODE = '{"compilerOptions":{"composite":true,"skipLibCheck":true,"module":"ESNext","moduleResolution":"Bundler","allowSyntheticDefaultImports":true},"include":["vite.config.ts"]}\n'
_REACT_CSS = "body { margin: 0; min-width: 320px; font: 16px system-ui, sans-serif; background: #f7f7fb; color: #20212a; }\nmain { max-width: 42rem; margin: 4rem auto; padding: 2rem; background: white; border-radius: 1rem; box-shadow: 0 1rem 3rem #20212a18; }\nlabel { display: grid; gap: .5rem; margin: 1rem 0; }\ninput, button { font: inherit; padding: .6rem .8rem; }\nbutton { cursor: pointer; }\n"
_VANILLA_HTML = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none';"><title>Hello Kourosh</title><link rel="stylesheet" href="style.css"></head>
<body><main><h1>Hello Kourosh</h1><form id="greet-form"><label for="name">Name</label><input id="name" value="Akira" maxlength="256" autocomplete="off"><button>Greet from Python</button></form><output id="result" aria-live="polite"></output></main><script src="kourosh.js"></script><script src="app.js"></script></body></html>
'''
_STYLE_CSS = "body { font: 16px system-ui, sans-serif; margin: 3rem; }\nmain { max-width: 42rem; }\nform { display: grid; gap: .75rem; max-width: 20rem; }\noutput { display: block; margin-top: 1rem; }\n"
_VANILLA_APP_JS = '''document.getElementById("greet-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const result = document.getElementById("result");
  try {
    const response = await window.kourosh.invoke("greet", { name: document.getElementById("name").value });
    result.textContent = response.message;
  } catch (error) {
    result.textContent = `${error.code || "error"}: ${error.message || "bridge call failed"}`;
  }
});
'''
_SDK_JS = 'export class KouroshError extends Error { constructor(error) { const normalized = error && typeof error === "object" ? error : { code: "unknown_error", message: "bridge call failed" }; super(normalized.message || "bridge call failed"); this.name = "KouroshError"; this.code = normalized.code || "unknown_error"; } }\nexport async function invoke(method, args, options) { if (!globalThis.kourosh || typeof globalThis.kourosh.invoke !== "function") throw new KouroshError({ code: "bridge_unavailable", message: "the Kourosh bridge has not been initialized" }); try { return await globalThis.kourosh.invoke(method, args, options); } catch (error) { throw new KouroshError(error); } }\n'
_SDK_DTS = 'export type JsonPrimitive = string | number | boolean | null;\nexport type JsonValue = JsonPrimitive | JsonObject | JsonValue[];\nexport type JsonObject = { [key: string]: JsonValue };\nexport interface InvokeOptions { timeoutMs?: number; }\nexport interface KouroshErrorShape { code: string; message: string; }\nexport class KouroshError extends Error { readonly code: string; constructor(error: KouroshErrorShape); }\nexport function invoke<TResult = unknown, TArgs extends JsonObject = JsonObject>(method: string, args: TArgs, options?: InvokeOptions): Promise<TResult>;\n'


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
