# Vite development and production

Vite projects use a `[frontend]` table in `kourosh.toml`:

```toml
[frontend]
type = "vite"
root = "."
dist = "dist/index.html"
dev_port = 5173
```

`kourosh dev` validates `package.json` and `node_modules`, chooses the
configured port when available or an allocated loopback port otherwise, and
starts Vite with `--host 127.0.0.1 --strictPort`. It waits for an HTTP 200
response before launching the native host with an exact trusted origin such
as `http://127.0.0.1:5173`. The Rust host rejects other schemes, hosts, and
ports. Vite is terminated when the host exits or development is interrupted.

Hot reload is development-only. The bridge rejects pending promises with
`window_reloaded` during `beforeunload`, and the bootstrap guard prevents
duplicate listeners if a frontend tool reinjects the script.

Build production assets with:

```sh
kourosh frontend build
kourosh run
```

The build command runs the configured Vite build, requires local dependencies,
and verifies a non-empty `dist/index.html` inside the project. `kourosh run`
loads those static assets through the existing custom protocol; it starts no
Node.js or Vite process.
