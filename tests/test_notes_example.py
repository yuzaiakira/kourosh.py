import json
import os
import runpy
import tempfile
import unittest
from pathlib import Path


class NotesExampleTests(unittest.TestCase):
    def test_sqlite_crud_uses_registered_methods(self) -> None:
        example = Path(__file__).parents[1] / "examples" / "notes-react-ts" / "main.py"
        with tempfile.TemporaryDirectory() as temporary:
            previous_host = os.environ.get("KOUROSH_HOST_APP")
            previous_data = os.environ.get("KOUROSH_NOTES_DATA_DIR")
            os.environ["KOUROSH_HOST_APP"] = "1"
            os.environ["KOUROSH_NOTES_DATA_DIR"] = temporary
            try:
                namespace = runpy.run_path(str(example))
            finally:
                if previous_host is None:
                    os.environ.pop("KOUROSH_HOST_APP", None)
                else:
                    os.environ["KOUROSH_HOST_APP"] = previous_host
                if previous_data is None:
                    os.environ.pop("KOUROSH_NOTES_DATA_DIR", None)
                else:
                    os.environ["KOUROSH_NOTES_DATA_DIR"] = previous_data
            app = namespace["app"]
            self.assertEqual(app._method_names(), ["list_notes", "create_note", "update_note", "delete_note"])
            self.assertEqual(app._dispatch("list_notes", json.dumps({})), [])
            created = app._dispatch("create_note", json.dumps({"title": "First", "body": "Body"}))
            self.assertEqual(created["title"], "First")
            updated = app._dispatch(
                "update_note", json.dumps({"note_id": created["id"], "title": "Updated", "body": "Changed"})
            )
            self.assertEqual(updated["body"], "Changed")
            self.assertEqual(app._dispatch("list_notes", json.dumps({}))[0]["title"], "Updated")
            self.assertEqual(app._dispatch("delete_note", json.dumps({"note_id": created["id"]})), {"deleted": True})
            with self.assertRaisesRegex(Exception, "Python handler"):
                app._dispatch("delete_note", json.dumps({"note_id": created["id"]}))


if __name__ == "__main__":
    unittest.main()
