# Quick start: vanilla JavaScript

This tutorial uses the generator's actual vanilla template and a single
allowlisted Python method.

## 1. Create the project

```sh
kourosh create hello
cd hello
```

The generator creates `main.py`, `kourosh.toml`, `ui/index.html`,
`ui/style.css`, `ui/app.js`, `ui/kourosh.js`, and `assets/`.

## 2. Register a Python method

The generated `main.py` contains the same contract as this minimal example:

```python
from kourosh import App

app = App(title="Hello Kourosh", width=1000, height=700)

@app.expose
def greet(name: str) -> dict[str, str]:
    return {"message": f"Hello {name}!"}

app.run()
```

Only functions registered with `@app.expose` can be called. Arguments must be
a JSON object and results must be JSON-compatible.

## 3. Call Python from JavaScript

The generated page loads `ui/kourosh.js` before `ui/app.js`. Application code
calls the Promise API:

```js
const response = await window.kourosh.invoke("greet", { name: "Akira" });
result.textContent = response.message;
```

Handle failures as structured values:

```js
try {
  await window.kourosh.invoke("unknown_method", {});
} catch (error) {
  result.textContent = `${error.code}: ${error.message}`;
}
```

## 4. Run and build

```sh
kourosh doctor
kourosh dev
```

`kourosh dev` launches the native host on Windows. On Linux it validates the
project and reports that WebView2 is unavailable; it does not simulate a GUI.

For a static production frontend:

```sh
kourosh run
```

The command requires a built frontend and a Windows host. It never starts
Node.js in the packaged runtime.

## 5. Prepare a Windows portable build

On Windows, build or provide a real `kourosh-host.exe` and download the
official CPython 3.12 x64 embeddable distribution through your normal trusted
software process:

```powershell
kourosh build --target windows --format portable `
  --python-runtime C:\runtimes\python-3.12-embed-amd64 `
  --host C:\path\to\kourosh-host.exe
```

Use [portable distribution](../portable-distribution.md) and [Windows
validation](../windows-validation.md) before sharing an artifact.
