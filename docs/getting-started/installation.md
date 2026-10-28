# Installation

The alpha package has **not** been published to PyPI. Install from a checkout
in a virtual environment:

```sh
git clone https://github.com/yuzaiakira/kourosh.py.git
cd kourosh.py
git switch work
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Verify the installed SDK and local prerequisites:

```sh
kourosh --version
kourosh doctor
kourosh doctor --json > doctor.json
```

The Python installation provides the SDK and CLI. It does not, by itself,
provide a working Windows native host. The host must be built for Windows and
the target machine must have WebView2. A packaged application additionally
needs the official CPython 3.12 embeddable runtime.

## Documentation tooling

To build this website locally, install the pinned documentation tool:

```sh
python -m pip install -r docs/requirements.txt
zensical build --clean
```

The generated `site/` directory is local build output and is ignored by Git.

## Operating-system notes

Linux and macOS can run SDK, bridge, CLI, frontend, and packaging checks where
their dependencies are available. They cannot launch the Windows WRY/WebView2
host. Use a real Windows 10/11 x64 machine for the GUI and portable package
workflow.
