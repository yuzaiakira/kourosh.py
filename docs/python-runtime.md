# Embedded Python runtime distribution

Kourosh.py expects the official CPython Windows embeddable package matching
the PyO3 ABI used to build the host. For the current host this is CPython
3.12 x64. Pass its extracted directory to `--python-runtime`, or set
`KOUROSH_PYTHON_RUNTIME`.

The directory must contain `python312.dll`, `python312.zip`,
`python312._pth`, and the distributor's license/redistribution notice. The
`._pth` file is inspected and must not contain `import site`, absolute paths,
or parent-directory escapes. The build copies these files without modifying
them. It rejects incomplete or ABI-mismatched input instead of falling back
to a system interpreter.

At launch the packaged host sets `PYTHONHOME` to the bundled directory,
disables the user site, clears ambient `PYTHONPATH`, and inserts only
`app/` and `runtime/python/` into the interpreter search path. Pure Python
application dependencies should be vendored under the project and are copied
into `app/`; native extensions must be tested against the same CPython ABI and
their DLLs supplied beside the package or through an explicitly reviewed
build input. Arbitrary PyPI compatibility is not claimed.

The host marks shutdown cooperatively and does not call unsafe `Py_Finalize`
while Rust/Python handles may still exist.
