# Kourosh.py

Kourosh.py is a Python-first desktop application framework. Python owns
application logic; a small Rust host owns the Windows window and WebView2
lifecycle; HTML, CSS, JavaScript, TypeScript, and React provide the UI.

The current source tree contains a bounded, default-deny asynchronous bridge,
embedded CPython through PyO3, a Python SDK and CLI, vanilla and React/Vite
templates, and Windows portable staging. It is experimental alpha software.

!!! warning "Windows validation is still pending"

    Cloud checks cover the bridge, embedded Python, SDK, CLI, frontend builds,
    and packaging logic. A real Windows 10/11 x64 machine is still required to
    validate WRY/WebView2 rendering, the portable package, installer behavior,
    clean-machine independence, and Windows performance.

## Quick installation

The alpha has not been published to PyPI. Install from the repository:

```sh
git clone https://github.com/yuzaiakira/kourosh.py.git
cd kourosh.py
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
kourosh doctor
```

Create a vanilla application:

```sh
kourosh create hello
cd hello
kourosh dev
```

On Linux, `kourosh dev` validates the project and reports the Windows-only
host limitation. It never launches a fake desktop window.

## Documentation

Read the [developer documentation](docs/index.md) for installation, the
[quick start](docs/getting-started/quickstart.md), Python and JavaScript API
references, React/Vite workflow, CLI commands, packaging, security, examples,
and troubleshooting.

Build or preview the static documentation site locally:

```sh
python -m pip install -r docs/requirements.txt
zensical build --clean
zensical serve
```

## React and TypeScript

```sh
kourosh create react-demo --ui react --typescript
cd react-demo
npm install
npm run typecheck
kourosh frontend build
```

The generated project includes a local vendored `@kourosh/sdk`; no unpublished
npm package is required. Node.js is a build-time dependency and is not part of
the packaged runtime.

## Project status

- Python SDK: `0.1.0a1`
- JavaScript SDK: `0.1.0-alpha.1`
- Rust components: `0.1.0`
- RPC protocol: `1`
- Planned release: `v0.1.0-alpha.1` (unreleased)

Use the [compatibility matrix](docs/compatibility.md), [known limitations](docs/known-limitations.md),
and [Windows validation handoff](docs/windows-validation.md) to distinguish
implemented, cloud-tested, experimental, planned, and unverified behavior.

## Development

```sh
./scripts/check.sh
./scripts/docs-check.sh
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [architecture notes](docs/architecture/),
the [roadmap](docs/ROADMAP.md), and the [release process](docs/release-process.md).
Kourosh.py does not use GitHub Actions and does not publish packages or
documentation automatically.
