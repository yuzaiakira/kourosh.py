"""Python-first application SDK for the Kourosh native runtime."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Callable, TypeVar, overload

__version__ = "0.2.0"

_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
_MAX_TITLE_BYTES = 256
_MAX_DIMENSION = 16_384
_METHOD_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
_F = TypeVar("_F", bound=Callable[..., Any])

_LOGGER = logging.getLogger("kourosh")


def configure_logging(level: str | None = None) -> None:
    """Configure opt-in SDK diagnostics without logging request data.

    The default is quiet. ``KOUROSH_LOG_LEVEL`` may be set by a developer to
    ``DEBUG``, ``INFO``, ``WARNING`` or ``ERROR``; production applications can
    leave it unset to avoid diagnostic output altogether.
    """

    selected = (level or os.environ.get("KOUROSH_LOG_LEVEL", "CRITICAL")).upper()
    numeric = getattr(logging, selected, None)
    if not isinstance(numeric, int):
        raise ValueError("log level must be DEBUG, INFO, WARNING, ERROR, or CRITICAL")
    if not _LOGGER.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("kourosh %(levelname)s: %(message)s"))
        _LOGGER.addHandler(handler)
    _LOGGER.setLevel(numeric)
    _LOGGER.propagate = False


configure_logging()


class KouroshError(RuntimeError):
    """An SDK error with a stable code suitable for a UI or CLI."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class App:
    """Describe a desktop app and register its Python RPC methods."""

    def __init__(self, *, title: str, width: int = 960, height: int = 640) -> None:
        if not isinstance(title, str) or not title.strip():
            raise ValueError("title must be a non-empty string")
        if len(title.encode("utf-8")) > _MAX_TITLE_BYTES:
            raise ValueError(f"title must be at most {_MAX_TITLE_BYTES} bytes")
        if not isinstance(width, int) or isinstance(width, bool) or not 1 <= width <= _MAX_DIMENSION:
            raise ValueError(f"width must be an integer from 1 to {_MAX_DIMENSION}")
        if not isinstance(height, int) or isinstance(height, bool) or not 1 <= height <= _MAX_DIMENSION:
            raise ValueError(f"height must be an integer from 1 to {_MAX_DIMENSION}")
        self.title = title
        self.width = width
        self.height = height
        self._methods: dict[str, Callable[..., Any]] = {}
        self._closed = False
        caller = inspect.currentframe()
        self.source_path = (
            Path(caller.f_back.f_globals["__file__"]).resolve()
            if caller and caller.f_back and "__file__" in caller.f_back.f_globals
            else None
        )
        del caller

    @overload
    def expose(self, function: _F) -> _F: ...

    @overload
    def expose(self, function: None = None, *, name: str | None = None) -> Callable[[_F], _F]: ...

    def expose(self, function: _F | None = None, *, name: str | None = None):
        """Register a callable under an explicit, default-deny RPC name."""

        if function is None:
            return lambda decorated: self._register(decorated, name=name)
        return self._register(function, name=name)

    def _register(self, function: _F, *, name: str | None = None) -> _F:
        if self._closed:
            raise KouroshError("app_closed", "cannot register methods after app shutdown")
        if not callable(function):
            raise TypeError("exposed object must be callable")
        method_name = name or getattr(function, "__name__", "")
        if not isinstance(method_name, str) or not _NAME_RE.fullmatch(method_name):
            raise ValueError("method names must match [A-Za-z_][A-Za-z0-9_]{0,63}")
        if method_name in self._methods:
            raise ValueError(f"method already registered: {method_name}")
        self._methods[method_name] = function
        return function

    def _method_names(self) -> list[str]:
        return list(self._methods)

    @property
    def closed(self) -> bool:
        """Whether the application has completed SDK-side shutdown."""

        return self._closed

    def _dispatch(self, method: str, args_json: str) -> Any:
        """Called by the embedded runtime after native allowlist checks."""

        if not isinstance(method, str) or not _METHOD_RE.fullmatch(method):
            raise _RpcError("invalid_method", "method must match the public RPC name format")
        if self._closed:
            raise _RpcError("shutdown", "the application is shut down")
        function = self._methods.get(method)
        if function is None:
            raise _RpcError("method_not_allowed", "the requested method is not allowlisted")
        try:
            args = json.loads(args_json)
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise _RpcError("invalid_args", "arguments must be valid JSON") from error
        if not isinstance(args, dict):
            raise _RpcError("invalid_args", "arguments must be a JSON object")
        try:
            result = function(**args)
            if inspect.isawaitable(result):
                result = _run_awaitable(result)
        except _RpcError:
            raise
        except TypeError as error:
            raise _RpcError("invalid_args", "arguments did not match the exposed function") from error
        except Exception as error:  # noqa: BLE001 - scrub details at the RPC boundary.
            _LOGGER.error("Python handler failed for registered method %s", method)
            raise _RpcError("python_error", "the Python handler raised an exception") from error
        try:
            json.dumps(result, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError, OverflowError) as error:
            raise _RpcError("serialization_error", "the Python handler returned a non-JSON value") from error
        return result

    def configuration(self) -> dict[str, Any]:
        """Return JSON-compatible metadata used by the developer host."""

        return {
            "title": self.title,
            "width": self.width,
            "height": self.height,
            "methods": self._method_names(),
        }

    def close(self) -> None:
        """Prevent further registrations and release SDK-side state."""

        self._closed = True

    def run(self, frontend: str | Path | None = None) -> int | None:
        """Launch the configured native host, or no-op while it imports this app."""

        if os.environ.get("KOUROSH_HOST_APP") == "1":
            return None
        if sys.platform != "win32":
            raise KouroshError(
                "unsupported_platform",
                "the WRY/WebView2 desktop host is currently supported on Windows only",
            )
        if self.source_path is None:
            raise KouroshError("app_source_missing", "App.run() must be called from a Python module")
        host = _find_host_binary()
        if host is None:
            raise KouroshError(
                "host_unavailable",
                "kourosh-host was not found; set KOUROSH_HOST_BIN or install the native host",
            )
        app_root = self.source_path.parent
        frontend_path = Path(frontend) if frontend is not None else app_root / "ui" / "index.html"
        frontend_path = (
            (app_root / frontend_path).resolve() if not frontend_path.is_absolute() else frontend_path.resolve()
        )
        if not _is_within(frontend_path, app_root) or not frontend_path.is_file():
            raise KouroshError("invalid_frontend", "frontend must be an existing file under the app directory")
        environment = os.environ.copy()
        environment["KOUROSH_HOST_APP"] = "1"
        framework_python = Path(__file__).resolve().parent.parent
        existing_pythonpath = environment.get("PYTHONPATH")
        environment["PYTHONPATH"] = str(framework_python) + (
            os.pathsep + existing_pythonpath if existing_pythonpath else ""
        )
        try:
            completed = subprocess.run(
                [
                    str(host),
                    "--app",
                    str(self.source_path),
                    "--identifier",
                    "kourosh-dev",
                    "--frontend",
                    str(frontend_path),
                    "--title",
                    self.title,
                    "--width",
                    str(self.width),
                    "--height",
                    str(self.height),
                ],
                cwd=app_root,
                env=environment,
                check=False,
            )
        finally:
            self.close()
        if completed.returncode != 0:
            raise KouroshError("host_exit", f"native host exited with status {completed.returncode}")
        return completed.returncode


class _RpcError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _run_awaitable(awaitable: Any) -> Any:
    """Resolve an async handler from a synchronous Rust/PyO3 callback.

    Embedded callbacks normally run on a bridge worker without an active event
    loop. If an application invokes ``_dispatch`` from an existing loop during
    tests or embedding, execute the coroutine on a short-lived helper thread
    instead of nesting ``asyncio.run`` and producing an unsafe loop error.
    """

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)

    result: list[Any] = []
    failure: list[BaseException] = []

    def runner() -> None:
        try:
            result.append(asyncio.run(awaitable))
        except BaseException as error:  # propagate the original handler failure
            failure.append(error)

    thread = threading.Thread(target=runner, name="kourosh-async-handler")
    thread.start()
    thread.join()
    if failure:
        raise failure[0]
    return result[0]


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _find_host_binary() -> Path | None:
    candidates = [os.environ.get("KOUROSH_HOST_BIN"), shutil.which("kourosh-host")]
    repository_root = Path(__file__).resolve().parents[2]
    candidates.extend(
        [
            str(repository_root / "target" / "release" / "kourosh-host.exe"),
            str(repository_root / "target" / "debug" / "kourosh-host.exe"),
        ]
    )
    for candidate in candidates:
        if candidate:
            path = Path(candidate)
            if path.is_file():
                return path.resolve()
    return None


__all__ = ["App", "KouroshError", "configure_logging", "__version__"]
