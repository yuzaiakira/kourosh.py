# Windows packaging architecture

Kourosh.py packages a Python-first application as a self-contained Windows
x64 directory. The portable pipeline is deliberately explicit: it accepts a
real PE `kourosh-host.exe` and an official Windows embeddable CPython
directory, validates both, and never fabricates an executable or downloads
runtime code during a build.

The generated layout is:

```text
dist/MyApp-1.2.3-windows-x64/
  MyApp.exe
  app/                  # application source and kourosh.toml
  frontend/             # production HTML and hashed assets
  python/               # embeddable CPython files
  runtime/
    manifest.json       # relative resource paths and window metadata
    python/kourosh/     # framework SDK used by the embedded app
  LICENSES/
  SHA256SUMS.txt
  build-manifest.json
```

The native host discovers `runtime/manifest.json` beside its executable when
it starts without command-line arguments. It validates every manifest path
against the package root, sets an isolated Python search path containing only
the packaged app and framework SDK, disables the user site, and loads the
frontend through the existing trusted `https://kourosh.app` origin. It does
not start Node.js or a local HTTP server.

The build stages into a temporary sibling directory and moves the finished
directory into place. Existing artifact directories are never overwritten.
Symlinked resources and paths outside the project are rejected. The ZIP uses
fixed entry timestamps; remaining nondeterminism comes from input bytes and
the host toolchain.

`kourosh build --target windows --format installer` is an optional wrapper
around the portable payload and requires Inno Setup on Windows. It is not
available on Linux and does not silently fall back to a fake installer.
