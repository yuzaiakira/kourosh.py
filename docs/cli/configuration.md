# Project configuration

Projects use `kourosh.toml`:

```toml
[app]
title = "Hello Kourosh"
width = 1000
height = 700
entrypoint = "main.py"
frontend = "ui/index.html"

[frontend]
type = "vite"
root = "."
dist = "dist/index.html"
dev_port = 5173

[build]
target = "windows"
format = "portable"
```

`[app].title`, `width`, `height`, `entrypoint`, and `frontend` are validated.
`name`, `version`, and `identifier` are optional metadata with safe defaults.
Frontend `type` is `static` or `vite`; Vite projects require `package.json` and
their built `dist` file before production execution. `dev_port` must be from
1024 through 65,535.

Paths must remain inside the project. The build target is currently `windows`
and the format is `portable` or `installer`.

Environment overrides:

- `KOUROSH_HOST_BIN` selects a host executable for development.
- `KOUROSH_PYTHON_RUNTIME` selects the embeddable runtime for packaging.
- `KOUROSH_LOG_LEVEL` enables SDK diagnostics.
- `KOUROSH_HOST_APP=1` marks the embedded module-loading process.
