import contextlib
import io
import json
import os
import runpy
import tempfile
import unittest
import zipfile
from pathlib import Path

from kourosh import App, KouroshError, __version__
from kourosh.cli import (
    _stage_portable_distribution,
    _prepare_output_base,
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

    def test_generated_project_is_valid_and_uses_sdk_registry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = create_project("myapp", Path(temporary))
            config = load_config(root)
            self.assertEqual(config.title, "Hello Kourosh")
            self.assertTrue((root / "assets").is_dir())
            self.assertTrue((root / "ui" / "kourosh.js").is_file())
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
            (runtime / "LICENSE.txt").write_text("notice", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                _stage_portable_distribution(config, host, runtime, Path(temporary) / "staged")
            with self.assertRaises(RuntimeError):
                _prepare_output_base(root, root / "unsafe-output")

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


if __name__ == "__main__":
    unittest.main()
