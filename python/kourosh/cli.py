"""Command-line tooling for creating, building, and running Kourosh apps."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.request
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from . import __version__, _find_host_binary


@dataclass(frozen=True)
class ProjectConfig:
    root: Path
    name: str
    version: str
    identifier: str
    title: str
    width: int
    height: int
    entrypoint: Path
    frontend: Path
    frontend_type: str = "static"
    frontend_root: Path | None = None
    dev_port: int = 5173
    build_target: str = "windows"
    build_format: str = "portable"

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
    name = app.get("name", root.name)
    version = app.get("version", __version__)
    default_identifier = re.sub(r"[^a-z0-9_.-]+", "_", root.name.lower())
    identifier = app.get("identifier", f"local.{default_identifier}")
    title = app.get("title")
    width = app.get("width", 960)
    height = app.get("height", 640)
    entrypoint = app.get("entrypoint", "main.py")
    app_frontend = app.get("frontend", "ui/index.html")
    if not isinstance(name, str) or not _valid_metadata_name(name, 128):
        raise ValueError("[app].name must be a safe non-empty application name")
    if not isinstance(version, str) or not _valid_metadata_name(version, 64):
        raise ValueError("[app].version must be a safe non-empty version")
    if not isinstance(identifier, str) or not _valid_identifier(identifier):
        raise ValueError("[app].identifier must contain only letters, digits, '.', '_' or '-'")
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
        build_target, build_format = _build_metadata(raw)
        return ProjectConfig(root, name, version, identifier, title, width, height, entrypoint_path, frontend_path, "vite", frontend_root, dev_port, build_target, build_format)

    frontend_path = _safe_project_path(root, app_frontend, "frontend")
    if require_frontend and not frontend_path.is_file():
        raise ValueError(f"frontend does not exist: {frontend_path}")
    build_target, build_format = _build_metadata(raw)
    return ProjectConfig(root, name, version, identifier, title, width, height, entrypoint_path, frontend_path, "static", None, 5173, build_target, build_format)


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


def build_windows(
    project: Path,
    *,
    output: Path | None = None,
    format: str = "portable",
    host_binary: Path | None = None,
    python_runtime: Path | None = None,
) -> int:
    """Build a self-contained Windows x64 portable distribution.

    The build deliberately requires real inputs: a PE host executable and an
    official embeddable CPython directory. It never creates a placeholder host
    or downloads an unverified runtime on behalf of the application developer.
    """

    if format not in {"portable", "installer"}:
        raise ValueError("Windows build format must be portable or installer")
    project = project.resolve()
    config = load_config(project, require_frontend=False)
    if config.frontend_type == "vite":
        result = run_frontend_build(project)
        if result != 0:
            return result
    config = load_config(project, require_frontend=True)
    if format == "installer":
        return _build_windows_installer(
            config,
            output=output,
            host_binary=host_binary,
            python_runtime=python_runtime,
        )

    host = _resolve_windows_host(project, host_binary)
    runtime = _resolve_python_runtime(python_runtime)
    output_base = _prepare_output_base(project, output)
    artifact_name = f"{_safe_filename(config.name)}-{_safe_filename(config.version)}-windows-x64"
    artifact_dir = output_base / artifact_name
    archive_path = output_base / f"{artifact_name}.zip"
    if artifact_dir.exists() or archive_path.exists():
        raise RuntimeError(f"build output already exists; remove it before rebuilding: {artifact_dir}")

    temporary = Path(tempfile.mkdtemp(prefix=f".{artifact_name}-", dir=output_base))
    staged = temporary / artifact_name
    temporary_archive = output_base / f".{archive_path.name}.tmp"
    try:
        _stage_portable_distribution(config, host, runtime, staged)
        _write_build_manifest(staged, config, host, runtime)
        _write_checksums(staged)
        _zip_directory(staged, temporary_archive)
        staged.replace(artifact_dir)
        temporary.rmdir()
        # The archive is written atomically after the staged directory moves.
        temporary_archive.replace(archive_path)
        archive_path.with_suffix(archive_path.suffix + ".sha256").write_text(
            f"{_sha256(archive_path)}  {archive_path.name}\n", encoding="utf-8"
        )
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        temporary_archive.unlink(missing_ok=True)
        raise
    print(f"Built portable Windows distribution: {artifact_dir}")
    print(f"ZIP archive: {archive_path}")
    print(f"SHA-256: {(archive_path.with_suffix('.zip.sha256')).read_text(encoding='utf-8').strip() if archive_path.with_suffix('.zip.sha256').is_file() else _sha256(archive_path)}")
    return 0


def _build_windows_installer(
    config: ProjectConfig,
    *,
    output: Path | None,
    host_binary: Path | None,
    python_runtime: Path | None,
) -> int:
    if sys.platform != "win32":
        raise RuntimeError("installer builds require Windows and Inno Setup; use --format portable on this host")
    iscc = shutil.which("ISCC.exe") or shutil.which("iscc")
    if iscc is None:
        raise RuntimeError("installer format requires Inno Setup (ISCC.exe); portable packaging remains available")
    # Build the portable payload first, then compile a checked-in-style script
    # in the output directory. Inno Setup remains an optional local tool.
    result = build_windows(config.root, output=output, format="portable", host_binary=host_binary, python_runtime=python_runtime)
    if result != 0:
        return result
    output_base = _prepare_output_base(config.root, output)
    artifact_name = f"{_safe_filename(config.name)}-{_safe_filename(config.version)}-windows-x64"
    script = output_base / f"{artifact_name}.iss"
    payload = output_base / artifact_name
    installer = output_base / f"{artifact_name}-setup.exe"
    script.write_text(_inno_script(config, payload, installer), encoding="utf-8", newline="\r\n")
    completed = subprocess.run([iscc, str(script)], cwd=config.root, check=False)
    if completed.returncode != 0:
        return completed.returncode
    if not installer.is_file():
        raise RuntimeError(f"Inno Setup completed without producing {installer}")
    print(f"Built installer: {installer}")
    return 0


def _resolve_windows_host(project: Path, explicit: Path | None) -> Path:
    candidates = [explicit] if explicit else []
    if not candidates:
        environment_host = os.environ.get("KOUROSH_HOST_BIN")
        if environment_host:
            candidates.append(Path(environment_host))
    candidates.extend(
        [
            project / "target" / "x86_64-pc-windows-msvc" / "release" / "kourosh-host.exe",
            project / "target" / "x86_64-pc-windows-gnu" / "release" / "kourosh-host.exe",
            project / "target" / "release" / "kourosh-host.exe",
        ]
    )
    for candidate in candidates:
        if candidate is None:
            continue
        path = candidate.expanduser().resolve()
        if path.is_file() and _is_windows_x64_pe(path):
            return path
    if sys.platform == "win32":
        cargo = shutil.which("cargo")
        if cargo is not None:
            target = "x86_64-pc-windows-msvc"
            completed = subprocess.run(
                [cargo, "build", "--release", "-p", "kourosh-host", "--target", target],
                cwd=project,
                check=False,
            )
            built = project / "target" / target / "release" / "kourosh-host.exe"
            if completed.returncode == 0 and _is_windows_x64_pe(built):
                return built.resolve()
    target = "x86_64-pc-windows-msvc" if sys.platform == "win32" else "x86_64-pc-windows-gnu"
    raise RuntimeError(
        "a real Windows x64 kourosh-host.exe is required; build it with "
        f"'cargo build --release -p kourosh-host --target {target}' or pass --host"
    )


def _is_windows_x64_pe(path: Path) -> bool:
    try:
        with path.open("rb") as stream:
            if stream.read(2) != b"MZ":
                return False
            stream.seek(0x3C)
            offset = int.from_bytes(stream.read(4), "little")
            stream.seek(offset)
            return stream.read(4) == b"PE\0\0" and int.from_bytes(stream.read(2), "little") == 0x8664
    except (OSError, ValueError):
        return False


def _resolve_python_runtime(explicit: Path | None) -> Path:
    candidates = [explicit] if explicit else []
    if not candidates and os.environ.get("KOUROSH_PYTHON_RUNTIME"):
        candidates.append(Path(os.environ["KOUROSH_PYTHON_RUNTIME"]))
    if not candidates:
        raise RuntimeError(
            "an official Windows embeddable CPython directory is required; "
            "pass --python-runtime or set KOUROSH_PYTHON_RUNTIME"
        )
    runtime = candidates[0].expanduser().resolve()
    if not runtime.is_dir():
        raise RuntimeError(f"Python runtime directory does not exist: {runtime}")
    dlls = list(runtime.glob("python3*.dll"))
    stdlib = list(runtime.glob("python*.zip"))
    licenses = [path for path in runtime.iterdir() if path.is_file() and path.name.lower().startswith("license")]
    if not dlls or not stdlib:
        raise RuntimeError("Python runtime must contain python3*.dll and a python*.zip standard library")
    if not licenses:
        raise RuntimeError("Python runtime must include its CPython license/redistribution notice")
    return runtime


def _prepare_output_base(project: Path, output: Path | None) -> Path:
    raw_base = (output if output is not None else project / "dist").expanduser()
    if raw_base.is_symlink():
        raise RuntimeError(f"build output must not be a symlink: {raw_base}")
    base = raw_base.resolve()
    default_base = (project / "dist").resolve()
    if output is not None and _is_within(base, project) and not _is_within(base, default_base):
        raise RuntimeError("--output must be project/dist or a directory outside the project")
    if base.exists() and not base.is_dir():
        raise RuntimeError(f"build output is not a directory: {base}")
    base.mkdir(parents=True, exist_ok=True)
    return base


def _stage_portable_distribution(config: ProjectConfig, host: Path, runtime: Path, destination: Path) -> None:
    destination.mkdir(parents=True)
    shutil.copy2(host, destination / f"{_safe_filename(config.name)}.exe")
    _copy_tree_no_symlinks(runtime, destination / "python")
    # Windows resolves import-table DLLs beside the executable before Python
    # initialization. Keep the full runtime under python/ for inspection and
    # place its DLL payload beside the host so a copied package is runnable.
    for runtime_dll in runtime.glob("*.dll"):
        shutil.copy2(runtime_dll, destination / runtime_dll.name)
    _copy_tree_no_symlinks(config.root, destination / "app", excluded={".git", ".venv", "node_modules", "dist", "__pycache__"})
    _copy_tree_no_symlinks(config.frontend.parent, destination / "frontend")
    sdk_source = Path(__file__).resolve().parent
    _copy_tree_no_symlinks(sdk_source, destination / "runtime" / "python" / "kourosh", excluded={"__pycache__"})
    for sibling in host.parent.glob("*.dll"):
        shutil.copy2(sibling, destination / sibling.name)
    licenses = destination / "LICENSES"
    licenses.mkdir()
    runtime_license = next(path for path in runtime.iterdir() if path.is_file() and path.name.lower().startswith("license"))
    shutil.copy2(runtime_license, licenses / "CPython.txt")
    (licenses / "README.txt").write_text(
        "This distribution includes the CPython embeddable runtime. See CPython.txt for its redistribution notice.\n",
        encoding="utf-8",
    )
    manifest = {
        "schema": 1,
        "app": f"app/{config.entrypoint.relative_to(config.root).as_posix()}",
        "frontend": "frontend/index.html",
        "python": "python",
        "runtime_python": "runtime/python",
        "name": config.name,
        "version": config.version,
        "identifier": config.identifier,
        "title": config.title,
        "target": "windows-x64",
    }
    runtime_dir = destination / "runtime"
    runtime_dir.mkdir(exist_ok=True)
    (runtime_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (runtime_dir / "README.txt").write_text(
        "Requires the Microsoft Evergreen WebView2 Runtime. Install it from Microsoft's official distribution channels.\n",
        encoding="utf-8",
    )


def _copy_tree_no_symlinks(source: Path, destination: Path, excluded: set[str] | None = None) -> None:
    source = source.resolve()
    excluded = excluded or set()
    for current, directories, files in os.walk(source, followlinks=False):
        current_path = Path(current)
        relative = current_path.relative_to(source)
        if any(part in excluded for part in relative.parts):
            directories[:] = []
            continue
        for directory in list(directories):
            path = current_path / directory
            if path.is_symlink():
                raise RuntimeError(f"packaging refuses symlinked resource: {path}")
            if directory in excluded:
                directories.remove(directory)
        target_dir = destination / relative
        target_dir.mkdir(parents=True, exist_ok=True)
        for filename in files:
            source_path = current_path / filename
            if source_path.is_symlink():
                raise RuntimeError(f"packaging refuses symlinked resource: {source_path}")
            target = target_dir / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target)


def _write_checksums(staged: Path) -> None:
    entries = []
    for path in sorted(item for item in staged.rglob("*") if item.is_file() and item.name != "SHA256SUMS.txt"):
        entries.append(f"{_sha256(path)}  {path.relative_to(staged).as_posix()}")
    (staged / "SHA256SUMS.txt").write_text("\n".join(entries) + "\n", encoding="utf-8")


def _write_build_manifest(staged: Path, config: ProjectConfig, host: Path, runtime: Path) -> None:
    manifest = {
        "name": config.name,
        "version": config.version,
        "identifier": config.identifier,
        "target": "windows-x64",
        "format": "portable",
        "host_sha256": _sha256(host),
        "python_runtime": sorted(path.name for path in runtime.iterdir()),
        "artifact_bytes": sum(path.stat().st_size for path in staged.rglob("*") if path.is_file()),
    }
    (staged / "build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def _zip_directory(source: Path, destination: Path) -> None:
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(source.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(source.parent).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _inno_script(config: ProjectConfig, payload: Path, installer: Path) -> str:
    return f'''[Setup]
AppId={config.identifier}
AppName={config.name}
AppVersion={config.version}
DefaultDirName={{autopf}}\\{config.name}
OutputDir={installer.parent}
OutputBaseFilename={installer.stem}
PrivilegesRequired=lowest
UninstallDisplayName={config.name}

[Files]
Source: "{payload}\\*"; DestDir: "{{app}}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{{autoprograms}}\\{config.name}"; Filename: "{{app}}\\{config.name}.exe"
'''


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

    package = subparsers.add_parser("build", help="build a distributable application")
    package.add_argument("path", type=Path, nargs="?", default=Path.cwd())
    package.add_argument("--target", choices=("windows",), default="windows")
    package.add_argument("--format", choices=("portable", "installer"), default="portable")
    package.add_argument("--output", type=Path)
    package.add_argument("--host", type=Path, help="path to a real Windows x64 kourosh-host.exe")
    package.add_argument("--python-runtime", type=Path, help="official Windows embeddable CPython directory")

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
        if args.command == "build":
            if args.target != "windows":
                raise ValueError("only the Windows target is supported")
            return build_windows(
                args.path,
                output=args.output,
                format=args.format,
                host_binary=args.host,
                python_runtime=args.python_runtime,
            )
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
    for asset in config.frontend.parent.rglob("*"):
        if asset.is_symlink() or not _is_within(asset.resolve(), config.root):
            raise RuntimeError(f"built asset escapes the project: {asset}")


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


def _valid_metadata_name(value: str, maximum: int) -> bool:
    return bool(value) and len(value) <= maximum and not any(
        character in value for character in '/\\\x00\r\n'
    ) and all(character.isprintable() for character in value)


def _valid_identifier(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,127}", value))


def _build_metadata(raw: dict) -> tuple[str, str]:
    build = raw.get("build", {})
    if not isinstance(build, dict):
        raise ValueError("[build] must be a TOML table")
    target = build.get("target", "windows")
    format = build.get("format", "portable")
    if target != "windows":
        raise ValueError("[build].target must be 'windows'")
    if format not in {"portable", "installer"}:
        raise ValueError("[build].format must be 'portable' or 'installer'")
    return target, format


def _safe_filename(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    if not sanitized:
        raise ValueError("application metadata produced an empty filename")
    return sanitized


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
