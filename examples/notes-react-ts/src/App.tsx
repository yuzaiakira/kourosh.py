import { useEffect, useState } from "react";
import { invoke, KouroshError } from "@kourosh/sdk";

type Note = { id: number; title: string; body: string; updated_at: string };

function errorMessage(error: unknown): string {
  const normalized = error instanceof KouroshError ? error : new KouroshError({ code: "unknown_error", message: String(error) });
  return `${normalized.code}: ${normalized.message}`;
}

export default function App() {
  const [notes, setNotes] = useState<Note[]>([]);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [error, setError] = useState("");

  async function refresh(): Promise<void> {
    try { setNotes(await invoke<Note[]>("list_notes", {})); setError(""); }
    catch (caught) { setError(errorMessage(caught)); }
  }

  useEffect(() => { void refresh(); }, []);

  async function create(): Promise<void> {
    try {
      await invoke<Note>("create_note", { title, body });
      setTitle(""); setBody(""); await refresh();
    } catch (caught) { setError(errorMessage(caught)); }
  }

  async function remove(id: number): Promise<void> {
    try { await invoke("delete_note", { note_id: id }); await refresh(); }
    catch (caught) { setError(errorMessage(caught)); }
  }

  return <main>
    <h1>Kourosh Notes</h1>
    <p>React and TypeScript call SQLite methods in embedded Python.</p>
    <section className="editor">
      <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Title" maxLength={200} />
      <textarea value={body} onChange={(event) => setBody(event.target.value)} placeholder="Write a note" maxLength={20000} />
      <button onClick={() => void create()} disabled={!title.trim() || !body.trim()}>Save note</button>
    </section>
    {error && <p className="error" role="alert">{error}</p>}
    <section className="notes" aria-live="polite">
      {notes.map((note) => <article key={note.id}><h2>{note.title}</h2><p>{note.body}</p><button onClick={() => void remove(note.id)}>Delete</button></article>)}
      {!notes.length && <p>No notes yet.</p>}
    </section>
  </main>;
}
