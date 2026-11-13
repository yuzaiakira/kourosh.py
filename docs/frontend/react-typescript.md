# React and TypeScript

Create the generated project requested by the CLI contract:

```sh
kourosh create myapp --ui react --typescript
cd myapp
npm install
npm run typecheck
```

The project contains:

```text
myapp/
├── main.py
├── kourosh.toml
├── index.html
├── public/kourosh-bridge.js
├── src/App.tsx
├── src/main.tsx
├── src/styles.css
├── vendor/@kourosh/sdk/
└── vite.config.ts
```

The generated package points `@kourosh/sdk` at the local vendored files. It
does not require a published npm package:

```tsx
import { invoke, KouroshError } from "@kourosh/sdk";

type Greeting = { message: string };

async function greet(name: string): Promise<string> {
  try {
    const result = await invoke<Greeting>("greet", { name });
    return result.message;
  } catch (caught) {
    const error = caught instanceof KouroshError
      ? caught
      : new KouroshError({ code: "unknown_error", message: String(caught) });
    return `${error.code}: ${error.message}`;
  }
}
```

The Python entrypoint registers the matching method:

```python
@app.expose
def greet(name: str) -> dict[str, str]:
    return {"message": f"Hello {name} from Python!"}
```

Run Vite and the native host together on Windows:

```sh
kourosh dev
```

For Linux development, `kourosh dev` validates and starts Vite but returns the
explicit Windows-only host limitation. Build static assets for production:

```sh
kourosh frontend build
kourosh run
```

Vite hot reload is development-only. The bridge rejects stale calls on
`beforeunload`; production execution uses the generated `dist/` assets and no
Node.js process.
