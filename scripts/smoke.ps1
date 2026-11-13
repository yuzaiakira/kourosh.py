param(
    [int]$WaitSeconds = 30
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

if ($env:OS -ne "Windows_NT") {
    throw "This smoke test requires Windows 10/11 and Microsoft WebView2."
}

$WebViewCandidates = @(
    "${env:ProgramFiles(x86)}\Microsoft\EdgeWebView\Application\*\msedgewebview2.exe",
    "$env:ProgramFiles\Microsoft\EdgeWebView\Application\*\msedgewebview2.exe",
    "$env:LOCALAPPDATA\Microsoft\EdgeWebView\Application\*\msedgewebview2.exe"
)
$WebViewRuntime = $WebViewCandidates |
    ForEach-Object { Get-ChildItem -Path $_ -ErrorAction SilentlyContinue } |
    Select-Object -First 1
if (-not $WebViewRuntime) {
    throw "Microsoft WebView2 Runtime was not found. Install the Evergreen Runtime and retry."
}
Write-Output ("WebView2 runtime: {0}" -f $WebViewRuntime.FullName)

cargo build --release -p kourosh-host
$HostPath = Join-Path $RepoRoot "target\release\kourosh-host.exe"
$Process = Start-Process -FilePath $HostPath -PassThru
try {
    Write-Output "Manual checks for the opened Kourosh.py window:"
    Write-Output "  1. Confirm the bundled page shows the Kourosh.py heading."
    Write-Output "  2. Leave the name as Akira and click 'Greet from Python'."
    Write-Output "  3. Confirm the page displays 'Hello, Akira!'."
    Write-Output "  4. Enter a different non-empty name and repeat the call."
    Write-Output "  5. Close the window and confirm the process exits without a crash."
    if (-not $Process.WaitForExit($WaitSeconds * 1000)) {
        Write-Output ("Window remained open for {0} seconds; finish the manual checks and close it." -f $WaitSeconds)
        $Process.WaitForExit()
    }
    if ($Process.ExitCode -ne 0) {
        throw "kourosh-host exited with code $($Process.ExitCode)."
    }
} finally {
    if (-not $Process.HasExited) {
        $Process.CloseMainWindow() | Out-Null
        $Process.WaitForExit(5000)
        if (-not $Process.HasExited) { $Process.Kill() }
    }
}
