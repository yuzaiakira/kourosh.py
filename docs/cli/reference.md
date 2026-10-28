# CLI reference

The installed command is `kourosh`. The current alpha exposes these commands:

| Command | Purpose |
| --- | --- |
| `kourosh create NAME` | Generate a vanilla, React, or React+TypeScript project |
| `kourosh dev [PATH]` | Start Vite when configured and launch the native host on Windows |
| `kourosh run [PATH]` | Launch a built static frontend without Node.js |
| `kourosh frontend build [PATH]` | Run the configured Vite production build |
| `kourosh build ...` | Stage a Windows portable package or optional installer |
| `kourosh doctor [--json]` | Report available, missing, unsupported, or failed prerequisites |

Create options:

```sh
kourosh create app
kourosh create react-app --ui react
kourosh create react-ts-app --ui react --typescript
kourosh create react-ts-app --template react-ts
```

The package command accepts `--target windows`, `--format portable|installer`,
`--python-runtime PATH`, `--host PATH`, and `--output PATH`. Installer builds
require Windows and Inno Setup. The [original CLI guide](../cli.md) contains
the complete packaging examples and return-code behavior.

All command failures are actionable. Linux does not pretend to start a
Windows GUI.
