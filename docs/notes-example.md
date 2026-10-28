# SQLite notes example

`examples/notes-react-ts` is a small real application used by the validation
workflow. Python owns a parameterized SQLite database and exposes four
allowlisted methods: `list_notes`, `create_note`, `update_note`, and
`delete_note`. React and TypeScript use the official local `@kourosh/sdk`
Promise API; no HTTP server or Node.js process is part of production runtime.

Run the development build:

```sh
cd examples/notes-react-ts
npm install
npm run typecheck
npm run build
kourosh dev
```

On Windows, application data is stored under
`%LOCALAPPDATA%\Kourosh\NotesExample\notes.sqlite3`. Linux development uses
`$XDG_DATA_HOME/kourosh/notes-example` (or `~/.local/share`). Tests set
`KOUROSH_NOTES_DATA_DIR` to a temporary directory and exercise all CRUD
methods without touching a user's real data.

The browser only supplies note values and IDs. It receives no filesystem path,
SQL string, or unrestricted native capability.
