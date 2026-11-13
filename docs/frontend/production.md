# Production frontend builds

Vite is a build-time tool. A production project should contain a built static
entrypoint before `kourosh run` or packaging:

```sh
kourosh frontend build
test -s dist/index.html
kourosh run
```

The CLI verifies that the configured `dist/index.html` exists, is non-empty,
stays inside the project, and has no unsafe symlinked resources. The native
host loads those assets through the trusted local protocol. It does not start
Vite, Node.js, or a localhost server after packaging.

For a Windows artifact, continue with the [portable distribution](../portable-distribution.md)
guide and retain the generated checksum files.
