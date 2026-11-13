# SQLite and application data

Keep database access in Python. The SQLite Notes example exposes only typed,
allowlisted operations:

```python
@app.expose
def list_notes() -> list[dict[str, object]]:
    with _connect() as connection:
        return [dict(row) for row in connection.execute("SELECT id, title, body FROM notes")]
```

Use parameterized SQL and keep filesystem paths out of browser arguments. The
browser should send note values and identifiers, never SQL strings or an
arbitrary database path.

The example uses `%LOCALAPPDATA%\\Kourosh\\NotesExample` on Windows and
`$XDG_DATA_HOME/kourosh/notes-example` (or the platform home directory) on
Linux development. Read [the Notes example](../notes-example.md) for the
complete CRUD flow and its test isolation.
