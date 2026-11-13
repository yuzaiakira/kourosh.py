# Prerequisites

## All developers

- Python 3.12 or newer.
- A checkout of `yuzaiakira/kourosh.py`.
- A virtual environment for the editable Python installation.

## Native host development

- Rust stable and Cargo.
- A compiler environment suitable for the Windows target.
- Microsoft WebView2 Evergreen Runtime on the Windows machine that will run
  the GUI.

The cloud checks can run without a GUI. They do not replace the Windows
runtime check.

## React and Vite development

- Node.js and npm.
- Dependencies installed in the generated project's `node_modules` directory.

Node.js is only a development/build prerequisite. `kourosh run` loads static
assets and does not start a Node process.

## Check before coding

```sh
python --version
cargo --version
kourosh doctor --json
```

On Linux, `doctor` reports the Windows WebView2 host as unsupported rather than
launching a mock window.
