"""Small SQLite notes app used by the Windows validation workflow."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

from kourosh import App


def _data_directory() -> Path:
    configured = os.environ.get("KOUROSH_NOTES_DATA_DIR")
    if configured:
        directory = Path(configured).expanduser()
    elif os.name == "nt":
        directory = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Kourosh" / "NotesExample"
    else:
        directory = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "kourosh" / "notes-example"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


DB_PATH = _data_directory() / "notes.sqlite3"


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute(
        "CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )
    connection.commit()
    return connection


def _text(value: Any, field: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{field} must be a non-empty string of at most {maximum} characters")
    return value.strip()


def _note(row: sqlite3.Row) -> dict[str, Any]:
    return {"id": row["id"], "title": row["title"], "body": row["body"], "updated_at": row["updated_at"]}


app = App(title="Kourosh Notes", width=980, height=720)


@app.expose
def list_notes() -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute("SELECT id, title, body, updated_at FROM notes ORDER BY updated_at DESC, id DESC").fetchall()
    return [_note(row) for row in rows]


@app.expose
def create_note(title: str, body: str) -> dict[str, Any]:
    title = _text(title, "title", 200)
    body = _text(body, "body", 20_000)
    with _connect() as connection:
        cursor = connection.execute("INSERT INTO notes(title, body) VALUES (?, ?)", (title, body))
        connection.commit()
        row = connection.execute(
            "SELECT id, title, body, updated_at FROM notes WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    assert row is not None
    return _note(row)


@app.expose
def update_note(note_id: int, title: str, body: str) -> dict[str, Any]:
    if not isinstance(note_id, int) or isinstance(note_id, bool) or note_id <= 0:
        raise ValueError("note_id must be a positive integer")
    title = _text(title, "title", 200)
    body = _text(body, "body", 20_000)
    with _connect() as connection:
        updated = connection.execute(
            "UPDATE notes SET title = ?, body = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (title, body, note_id),
        ).rowcount
        if updated != 1:
            raise ValueError("note does not exist")
        connection.commit()
        row = connection.execute(
            "SELECT id, title, body, updated_at FROM notes WHERE id = ?", (note_id,)
        ).fetchone()
    assert row is not None
    return _note(row)


@app.expose
def delete_note(note_id: int) -> dict[str, bool]:
    if not isinstance(note_id, int) or isinstance(note_id, bool) or note_id <= 0:
        raise ValueError("note_id must be a positive integer")
    with _connect() as connection:
        deleted = connection.execute("DELETE FROM notes WHERE id = ?", (note_id,)).rowcount
        connection.commit()
    if deleted != 1:
        raise ValueError("note does not exist")
    return {"deleted": True}


app.run("dist/index.html")
