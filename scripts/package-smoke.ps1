param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectPath,
    [Parameter(Mandatory = $true)]
    [string]$PythonRuntime,
    [string]$HostPath,
    [string]$OutputPath
)

$ErrorActionPreference = "Stop"
if ($env:OS -ne "Windows_NT") {
    throw "The packaged application smoke test requires Windows 10/11."
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
    throw "Microsoft Evergreen WebView2 Runtime was not found. Install it from Microsoft's official channel."
}

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Project = (Resolve-Path $ProjectPath).Path
$Runtime = (Resolve-Path $PythonRuntime).Path
$BuildOutput = if ($OutputPath) { $OutputPath } else { Join-Path $Project "dist" }
$BuildArgs = @(
    "-m", "kourosh.cli", "build", $Project,
    "--target", "windows", "--format", "portable",
    "--python-runtime", $Runtime, "--output", $BuildOutput
)
if ($HostPath) { $BuildArgs += @("--host", (Resolve-Path $HostPath).Path) }
$env:PYTHONPATH = "$RepoRoot\python"
& python @BuildArgs
if ($LASTEXITCODE -ne 0) { throw "kourosh build failed with exit code $LASTEXITCODE" }

$Manifest = Get-ChildItem -Path $BuildOutput -Directory |
    Where-Object { Test-Path (Join-Path $_.FullName "runtime\manifest.json") } |
    ForEach-Object { Get-Item (Join-Path $_.FullName "runtime\manifest.json") } |
    Select-Object -First 1
if (-not $Manifest) { throw "The build did not produce runtime\manifest.json." }
$PackageRoot = $Manifest.Directory.Parent.FullName
# The executable is named from [app].name; locate it without trusting a path
# from the project or the current working directory.
$Executable = Get-ChildItem -Path $PackageRoot -Filter "*.exe" | Select-Object -First 1
if (-not $Executable) { throw "The portable directory has no native executable." }

$UnicodeRoot = Join-Path $env:TEMP ("Kourosh Smoke – 空間 " + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $UnicodeRoot | Out-Null
Copy-Item -Path (Join-Path $PackageRoot "*") -Destination $UnicodeRoot -Recurse
$CopiedExecutable = Join-Path $UnicodeRoot $Executable.Name
if (-not (Test-Path $CopiedExecutable)) { throw "The copied package is missing its executable." }
if (Get-ChildItem -Path $UnicodeRoot -Filter "python.exe" -Recurse -ErrorAction SilentlyContinue) {
    throw "The package unexpectedly contains a system Python launcher."
}
if (Get-ChildItem -Path $UnicodeRoot -Filter "node.exe" -Recurse -ErrorAction SilentlyContinue) {
    throw "The package unexpectedly contains Node.js."
}

Write-Output "WebView2 runtime: $($WebViewRuntime.FullName)"
Write-Output "Copied package: $UnicodeRoot"
Write-Output "Manual checks in the opened window:"
Write-Output "  1. Confirm the real frontend loads from the copied Unicode/space path."
Write-Output "  2. Call the registered Python method and verify its result."
Write-Output "  3. Trigger a Python exception and verify a structured error is shown."
Write-Output "  4. Close the window and confirm clean process shutdown."
$Process = Start-Process -FilePath $CopiedExecutable -WorkingDirectory $UnicodeRoot -PassThru
$Process.WaitForExit()
if ($Process.ExitCode -ne 0) { throw "Packaged application exited with code $($Process.ExitCode)." }

Write-Output "Packaged smoke procedure completed; retain the Windows build, WebView2 version, and commit SHA with the manual observations."
