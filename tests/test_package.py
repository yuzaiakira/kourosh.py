import contextlib
import asyncio
import io
import json
import os
import runpy
import tempfile
import unittest
import zipfile
from pathlib import Path

from kourosh import App, KouroshError, Plugin, PluginMetadata, __version__
from kourosh.cli import (
    _stage_portable_distribution,
    _prepare_output_base,
    _resolve_python_runtime,
    _inno_script,
    _write_build_manifest,
    _write_checksums,
    _zip_directory,
    build_windows,
    create_project,
    load_config,
    main,
    run_dev,
    run_frontend_build,
)


class PackageTests(unittest.TestCase):
    def test_package_version_and_app_configuration(self) -> None:
        self.assertEqual(__version__, "0.2.0")
        app = App(title="Hello", width=1000, height=700)
        self.assertEqual(app.configuration(), {"title": "Hello", "width": 1000, "height": 700, "methods": []})

    def test_expose_dispatch_and_structured_errors(self) -> None:
        app = App(title="Test")

        @app.expose
        def greet(name: str) -> dict[str, str]:
            return {"message": f"Hello {name}!"}

        self.assertEqual(app._method_names(), ["greet"])
        self.assertEqual(app._dispatch("greet", json.dumps({"name": "Ada"})), {"message": "Hello Ada!"})
        with self.assertRaisesRegex(Exception, "allowlisted"):
            app._dispatch("unknown", "{}")
        with self.assertRaises(ValueError):
            app.expose(greet)

        bad = App(title="Bad")
        with self.assertRaises(ValueError):
            bad.expose(lambda: None, name="read-file")

    def test_async_handlers_and_json_contract_errors(self) -> None:
        app = App(title="Async")

        @app.expose
        async def greet_async(name: str) -> dict[str, str]:
            await asyncio.sleep(0)
            return {"message": f"Hello {name}"}

        async def dispatch_from_loop() -> None:
            self.assertEqual(app._dispatch("greet_async", '{"name":"Ada"}')['message'], "Hello Ada")

        asyncio.run(dispatch_from_loop())
        bad = App(title="Serialization")

        @bad.expose
        def returns_nan() -> float:
            return float("nan")

        with self.assertRaisesRegex(Exception, "non-JSON"):
            bad._dispatch("returns_nan", "{}")
        failing = App(title="Handler failure")

        @failing.expose
        def raises_type_error() -> None:
            raise TypeError("handler bug")

        with self.assertRaises(Exception) as handler_error:
            failing._dispatch("raises_type_error", "{}")
        self.assertEqual(handler_error.exception.code, "python_error")
        with self.assertRaises(Exception) as raised:
            app._dispatch("bad-name", "{}")
        self.assertEqual(raised.exception.code, "invalid_method")

    def test_trusted_plugins_have_explicit_metadata_and_deterministic_cleanup(self) -> None:
        events: list[str] = []

        class ExamplePlugin(Plugin):
            metadata = PluginMetadata("example.notes", "1.0", ("notes",))

            def initialize(self, app: App) -> None:
                events.append("init")

                @app.expose(name="plugin_method")
                def plugin_method() -> dict[str, bool]:
                    return {"ok": True}

            def shutdown(self) -> None:
                events.append("shutdown")

        app = App(title="Plugins")
        plugin = app.register_plugin(ExamplePlugin())
        self.assertIsNotNone(plugin)
        self.assertEqual(app.plugin_metadata()[0]["identifier"], "example.notes")
        self.assertEqual(app._dispatch("plugin_method", "{}"), {"ok": True})
        with self.assertRaises(KouroshError) as duplicate:
            app.register_plugin(ExamplePlugin())
        self.assertEqual(duplicate.exception.code, "plugin_duplicate")
        app.close()
        app.close()
        self.assertEqual(events, ["init", "shutdown"])

    def test_plugin_registration_rolls_back_methods_on_initialization_failure(self) -> None:
        class BrokenPlugin(Plugin):
            metadata = PluginMetadata("broken", "1.0")

            def initialize(self, app: App) -> None:
                @app.expose
                def leaked() -> None:
                    return None

                raise RuntimeError("broken plugin")

        app = App(title="Broken plugin")
        with self.assertRaises(KouroshError) as raised:
            app.register_plugin(BrokenPlugin())
        self.assertEqual(raised.exception.code, "plugin_init")
        self.assertEqual(app._method_names(), [])
        with self.assertRaises(ValueError):
            PluginMetadata("bad id/with/path", "1.0")
        with self.assertRaises(ValueError):
            PluginMetadata("future", "1.0", protocol=2)

    def test_generated_project_is_valid_and_uses_sdk_registry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = create_project("myapp", Path(temporary))
            config = load_config(root)
            self.assertEqual(config.title, "Hello Kourosh")
            self.assertTrue((root / "assets").is_dir())
            self.assertTrue((root / "ui" / "kourosh.js").is_file())
            self.assertIn('protocol: PROTOCOL_VERSION', (root / "ui" / "kourosh.js").read_text(encoding="utf-8"))
            previous = os.environ.get("KOUROSH_HOST_APP")
            os.environ["KOUROSH_HOST_APP"] = "1"
            try:
                namespace = runpy.run_path(str(config.entrypoint))
            finally:
                if previous is None:
                    os.environ.pop("KOUROSH_HOST_APP", None)
                else:
                    os.environ["KOUROSH_HOST_APP"] = previous
            app = namespace["app"]
            self.assertEqual(app._method_names(), ["greet"])
            self.assertEqual(app._dispatch("greet", '{"name":"Akira"}'), {"message": "Hello Akira!"})

    def test_project_name_and_path_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                create_project("../escape", Path(temporary))
            root = create_project("safe_app", Path(temporary))
            (root / "kourosh.toml").write_text(
                '[app]\ntitle="Bad"\nentrypoint="../main.py"\nfrontend="ui/index.html"\n',
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_config(root)

    def test_build_metadata_and_portable_staging_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = create_project("package_app", Path(temporary))
            (root / "kourosh.toml").write_text(
                '[app]\nname="Package App"\nversion="1.2.3"\nidentifier="com.example.package_app"\ntitle="Package App"\nentrypoint="main.py"\nfrontend="ui/index.html"\n',
                encoding="utf-8",
            )
            config = load_config(root)
            installer_script = _inno_script(config, Path(temporary) / "payload", Path(temporary) / "setup.exe")
            self.assertIn("AppId=com.example.package_app", installer_script)
            self.assertIn("AppVersion=1.2.3", installer_script)
            host = Path(temporary) / "kourosh-host.exe"
            pe = bytearray(0x100)
            pe[:2] = b"MZ"
            pe[0x3C:0x40] = (0x80).to_bytes(4, "little")
            pe[0x80:0x84] = b"PE\0\0"
            pe[0x84:0x86] = (0x8664).to_bytes(2, "little")
            host.write_bytes(pe)
            runtime = Path(temporary) / "python-runtime"
            runtime.mkdir()
            (runtime / "python312.dll").write_bytes(b"runtime")
            (runtime / "python312.zip").write_bytes(b"stdlib")
            (runtime / "python312._pth").write_text("python312.zip\n.\n", encoding="utf-8")
            (runtime / "LICENSE.txt").write_text("CPython redistribution notice", encoding="utf-8")
            staged = Path(temporary) / "staged"
            _stage_portable_distribution(config, host, runtime, staged)
            _write_build_manifest(staged, config, host, runtime)
            _write_checksums(staged)
            archive = Path(temporary) / "package.zip"
            _zip_directory(staged, archive)
            self.assertTrue((staged / "Package_App.exe").is_file())
            self.assertTrue((staged / "app" / "main.py").is_file())
            self.assertTrue((staged / "frontend" / "index.html").is_file())
            self.assertTrue((staged / "python" / "python312.dll").is_file())
            self.assertTrue((staged / "runtime" / "manifest.json").is_file())
            self.assertTrue((staged / "SHA256SUMS.txt").is_file())
            with zipfile.ZipFile(archive) as contents:
                names = set(contents.namelist())
            self.assertIn("staged/Package_App.exe", names)
            self.assertIn("staged/runtime/manifest.json", names)
            self.assertEqual(build_windows(root, host_binary=host, python_runtime=runtime), 0)
            output = root / "dist" / "Package_App-1.2.3-windows-x64"
            self.assertTrue((output / "Package_App.exe").is_file())
            self.assertTrue(Path(f"{output}.zip").is_file())
            self.assertTrue(Path(f"{output}.zip.sha256").is_file())

    def test_packaging_requires_real_runtime_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = create_project("package_app", Path(temporary))
            with self.assertRaises(RuntimeError):
                # The CLI must fail clearly instead of fabricating a host or
                # silently falling back to the developer's Python install.
                from kourosh.cli import build_windows

                build_windows(root)

    def test_packaging_rejects_symlinked_resources_and_unsafe_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = create_project("package_app", Path(temporary))
            outside = Path(temporary) / "outside.txt"
            outside.write_text("outside", encoding="utf-8")
            link = root / "ui" / "outside.txt"
            try:
                link.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks are unavailable on this filesystem")
            config = load_config(root)
            host = Path(temporary) / "kourosh-host.exe"
            pe = bytearray(0x100)
            pe[:2] = b"MZ"
            pe[0x3C:0x40] = (0x80).to_bytes(4, "little")
            pe[0x80:0x84] = b"PE\0\0"
            pe[0x84:0x86] = (0x8664).to_bytes(2, "little")
            host.write_bytes(pe)
            runtime = Path(temporary) / "python-runtime"
            runtime.mkdir()
            (runtime / "python312.dll").write_bytes(b"runtime")
            (runtime / "python312.zip").write_bytes(b"stdlib")
            (runtime / "python312._pth").write_text("python312.zip\n.\n", encoding="utf-8")
            (runtime / "LICENSE.txt").write_text("notice", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                _stage_portable_distribution(config, host, runtime, Path(temporary) / "staged")
            with self.assertRaises(RuntimeError):
                _prepare_output_base(root, root / "unsafe-output")

    def test_python_embedded_runtime_rejects_site_imports(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary)
            (runtime / "python312.dll").write_bytes(b"runtime")
            (runtime / "python312.zip").write_bytes(b"stdlib")
            (runtime / "python312._pth").write_text("python312.zip\nimport site\n", encoding="utf-8")
            (runtime / "LICENSE.txt").write_text("notice", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "user-site"):
                _resolve_python_runtime(runtime)

    def test_react_and_typescript_generators_are_self_contained(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary)
            react = create_project("react_app", destination, ui="react")
            react_config = load_config(react, require_frontend=False)
            self.assertEqual(react_config.frontend_type, "vite")
            self.assertTrue((react / "src" / "App.jsx").is_file())
            self.assertTrue((react / "vendor" / "@kourosh" / "sdk" / "index.d.ts").is_file())
            package = json.loads((react / "package.json").read_text(encoding="utf-8"))
            self.assertEqual(package["dependencies"]["@kourosh/sdk"], "file:vendor/@kourosh/sdk")

            typescript = create_project("typescript_app", destination, ui="react", typescript=True)
            ts_config = load_config(typescript, require_frontend=False)
            self.assertEqual(ts_config.frontend_type, "vite")
            self.assertTrue((typescript / "src" / "App.tsx").is_file())
            self.assertTrue((typescript / "tsconfig.json").is_file())
            with self.assertRaises(RuntimeError):
                run_frontend_build(typescript)

            with self.assertRaises(ValueError):
                create_project("bad", destination, ui="vanilla", typescript=True)

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["create", "template_alias", "--directory", str(destination), "--template", "react-ts"]), 0)
            alias = destination / "template_alias"
            self.assertTrue((alias / "src" / "App.tsx").is_file())

            (react / "kourosh.toml").write_text(
                '[app]\ntitle="React"\nentrypoint="main.py"\nfrontend="dist/index.html"\n[frontend]\ntype="vite"\nroot="."\ndist="dist/index.html"\ndev_port=80\n',
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_config(react, require_frontend=False)

    def test_dev_reports_linux_limitation_without_mocking_host(self) -> None:
        if os.name == "nt":
            self.skipTest("Linux-only assertion")
        with tempfile.TemporaryDirectory() as temporary:
            root = create_project("devapp", Path(temporary))
            self.assertEqual(run_dev(root), 2)

    def test_cli_version_and_close_cleanup(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit) as raised:
                main(["--version"])
        self.assertEqual(raised.exception.code, 0)
        self.assertIn("kourosh 0.2.0", output.getvalue())
        app = App(title="Close")
        app.close()
        with self.assertRaises(KouroshError):
            app.expose(lambda: None)
        with self.assertRaises(Exception):
            app._dispatch("anything", "{}")
        self.assertTrue(app.closed)

    def test_doctor_json_report_is_machine_readable(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(["doctor", "--json"]), 0)
        report = json.loads(output.getvalue())
        self.assertEqual(report["schema"], 1)
        checks = {check["name"]: check for check in report["checks"]}
        self.assertIn(checks["webview2"]["status"], {"unsupported", "available", "missing"})
        self.assertTrue(all(set(("name", "status", "detail", "required")) <= set(check) for check in report["checks"]))


if __name__ == "__main__":
    unittest.main()
