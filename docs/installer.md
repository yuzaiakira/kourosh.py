# Optional installer

`kourosh build --target windows --format installer` is a thin, local Inno
Setup integration. It first creates the portable payload, emits a generated
`.iss` file with application identity, per-user install location, Start Menu
shortcut, and uninstall metadata, then invokes `ISCC.exe`.

Installer support is incomplete on Linux and is not claimed unless a Windows
machine with Inno Setup produces and launches the installer. WebView2 remains
an operating-system prerequisite; the generated script does not silently
bundle or download it. Desktop shortcuts and Start Menu entries are optional
policy decisions for a product release and should be reviewed before signing.
