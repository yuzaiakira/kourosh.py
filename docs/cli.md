# Developer CLI

Install the checkout in an environment with Python 3.12 or newer:

```sh
python -m pip install -e .
kourosh --version
```

Create a plain HTML/CSS/JavaScript project without Node.js:

```sh
kourosh create myapp
cd myapp
```

The generator writes `main.py`, `kourosh.toml`, `ui/index.html`,
`ui/style.css`, `ui/app.js`, `ui/kourosh.js`, and an `assets/` directory.
`kourosh.toml` controls the title, window dimensions, Python entrypoint, and
frontend document. Project and resource paths must remain inside the project.

React projects are generated with a local SDK package and Vite configuration:

```sh
kourosh create react-app --ui react
kourosh create react-ts-app --ui react --typescript
```

Run the native development host with:

```sh
kourosh dev
```

`dev` validates the project before starting `kourosh-host`. Windows is the
initial GUI target. On Linux it performs validation and reports that WebView2
is unavailable; it never substitutes a simulated host. Set `KOUROSH_HOST_BIN`
when using a host binary outside the normal `target` directories.

For a Vite project, use `kourosh frontend build` to create production assets
and `kourosh run` to load them without Node.js. `kourosh dev` is the only
command that starts Vite.

Use `kourosh doctor` to inspect Python, platform, host discovery, and the
Windows WebView2 prerequisite. Packaging and distribution are intentionally
out of scope for this phase.
