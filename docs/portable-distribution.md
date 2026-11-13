# Portable application distribution

Portable output is the supported Phase 4 format:

```powershell
kourosh build --target windows --format portable --python-runtime <CPython-embed-dir>
```

The command validates `kourosh.toml`, builds a Vite frontend when configured,
requires a real Windows x64 host, stages the app and frontend, copies the
embeddable CPython runtime and framework SDK, writes `SHA256SUMS.txt`, and
creates a ZIP with a fixed timestamp policy. Run the executable from any
directory, including one with spaces or Unicode characters. User-writable
state must be placed by application code in an appropriate per-user directory;
the framework does not write beside the executable at runtime.

Verify the archive before distribution:

```powershell
Get-FileHash .\dist\MyApp-1.2.3-windows-x64.zip -Algorithm SHA256
Get-Content .\dist\MyApp-1.2.3-windows-x64.zip.sha256
```

Artifacts are unsigned development builds until a separate organizational
code-signing process signs the executable and installer. Signing integration
is documented but not performed by Kourosh.py.
