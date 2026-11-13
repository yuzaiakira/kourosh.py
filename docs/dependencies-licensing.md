# Dependencies and licensing

The package records the selected application metadata and host/runtime hashes
in `build-manifest.json`. It copies the CPython redistribution notice into
`LICENSES/CPython.txt` and includes a short runtime notice. Projects remain
responsible for adding licenses for their own Python dependencies, frontend
dependencies, native DLLs, and application assets before redistribution.

Build-time dependencies are the pinned Rust lockfile, the Python environment,
and (for React/Vite projects) the project's npm lockfile and local
`node_modules`. Node.js and Vite are build-time tools only. No credentials or
signing keys are read or embedded by the packaging command.

The ZIP entry timestamps are fixed to improve repeatability. Exact bytes can
still differ when the Rust toolchain, CPython distribution, frontend lockfile,
or native dependencies differ. Kourosh.py does not claim bit-for-bit
reproducible Windows executables yet.
