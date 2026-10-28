import contextlib
import io
import json
import os
import runpy
import tempfile
import unittest
from pathlib import Path

from kourosh import App, KouroshError, __version__
from kourosh.cli import create_project, load_config, main, run_dev


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
