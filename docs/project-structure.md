# Generated project structure

```text
myapp/
├── main.py              # App metadata and @app.expose functions
├── kourosh.toml         # title, dimensions, entrypoint, frontend
├── ui/
│   ├── index.html       # local document with a restrictive CSP
│   ├── style.css
│   ├── app.js           # application UI code
│   └── kourosh.js       # framework-independent Promise bridge SDK
└── assets/              # local static resources
```

The Windows host canonicalizes the configured frontend directory and rejects
requests containing traversal segments, backslashes, NUL bytes, or files
outside that directory. The custom `kourosh` protocol maps to the trusted
`https://kourosh.app` origin, so remote pages cannot inherit the RPC channel.
