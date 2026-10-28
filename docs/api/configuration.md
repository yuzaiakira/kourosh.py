# Configuration schema reference

## `[app]`

| Key | Type | Default | Notes |
| --- | --- | --- | --- |
| `name` | string | project directory name | Safe metadata name |
| `version` | string | `0.1.0a1` | Safe metadata version |
| `identifier` | string | `local.<project>` | Letters, digits, `.`, `_`, `-` |
| `title` | string | required | Non-empty, at most 256 UTF-8 bytes |
| `width` / `height` | integer | 960 / 640 | Range 1–16,384 |
| `entrypoint` | path | `main.py` | Must stay inside project |
| `frontend` | path | `ui/index.html` | Static document or Vite dist |

## `[frontend]`

`type` is `static` or `vite`. Vite projects may set `root`, `dist`, and
`dev_port` (1024–65,535). Vite builds require `package.json`, local
`node_modules`, and a non-empty configured dist entrypoint.

## `[build]`

`target` is currently `windows`; `format` is `portable` or `installer`.
Installer output requires Windows and Inno Setup.
