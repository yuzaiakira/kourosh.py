param(
    [int]$Samples = 1000,
    [int]$Concurrency = 8,
    [string]$ResultsPath = "windows-benchmark-results.json"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$env:KOUROSH_BENCH_SAMPLES = $Samples
$env:KOUROSH_BENCH_CONCURRENCY = $Concurrency
cargo build --release -p kourosh-python --example runtime_bench
Write-Output "Measured embedded-Python RPC benchmark:"
$RpcLines = @(& .\target\release\examples\runtime_bench.exe)
$RpcLines | ForEach-Object { Write-Output $_ }

cargo build --release -p kourosh-host
$Started = [System.Diagnostics.Stopwatch]::StartNew()
$Process = Start-Process -FilePath ".\target\release\kourosh-host.exe" -PassThru
$ProcessTreeIds = [System.Collections.Generic.HashSet[int]]::new()
$WebViewIds = [System.Collections.Generic.HashSet[int]]::new()
try {
    Start-Sleep -Seconds 2
    $ObservedStartupMs = $Started.Elapsed.TotalMilliseconds
    $AllProcesses = @(Get-CimInstance Win32_Process | Select-Object ProcessId, ParentProcessId, Name)
    $ProcessTreeIds.Add($Process.Id) | Out-Null
    $Pending = [System.Collections.Generic.Queue[int]]::new()
    $Pending.Enqueue($Process.Id)
    while ($Pending.Count -gt 0) {
        $ParentId = $Pending.Dequeue()
        foreach ($Child in $AllProcesses | Where-Object { $_.ParentProcessId -eq $ParentId }) {
            if ($ProcessTreeIds.Add([int]$Child.ProcessId)) { $Pending.Enqueue([int]$Child.ProcessId) }
        }
    }
    foreach ($Entry in $AllProcesses | Where-Object { $ProcessTreeIds.Contains([int]$_.ProcessId) -and $_.Name -like "msedgewebview2*" }) {
        $WebViewIds.Add([int]$Entry.ProcessId) | Out-Null
    }
    $BeforeCpu = (Get-Process -Id ([int[]]$ProcessTreeIds) -ErrorAction SilentlyContinue |
        Measure-Object -Property CPU -Sum).Sum
    Start-Sleep -Seconds 1
    $AfterCpu = (Get-Process -Id ([int[]]$ProcessTreeIds) -ErrorAction SilentlyContinue |
        Measure-Object -Property CPU -Sum).Sum
    $WorkingSet = (Get-Process -Id ([int[]]$ProcessTreeIds) -ErrorAction SilentlyContinue |
        Measure-Object -Property WorkingSet64 -Sum).Sum
    $WebViewWorkingSet = (Get-Process -Id ([int[]]$WebViewIds) -ErrorAction SilentlyContinue |
        Measure-Object -Property WorkingSet64 -Sum).Sum
    $IdleCpuPercent = if ($null -eq $BeforeCpu -or $null -eq $AfterCpu) { $null } else {
        (($AfterCpu - $BeforeCpu) / 1.0) / [Environment]::ProcessorCount * 100
    }
} finally {
    $ShutdownStarted = [System.Diagnostics.Stopwatch]::StartNew()
    if (-not $Process.HasExited) {
        $Process.CloseMainWindow() | Out-Null
        $Process.WaitForExit(5000)
        if (-not $Process.HasExited) { $Process.Kill() }
    }
    $ShutdownStarted.Stop()
}

$WebViewCandidates = @(
    "${env:ProgramFiles(x86)}\Microsoft\EdgeWebView\Application\*\msedgewebview2.exe",
    "$env:ProgramFiles\Microsoft\EdgeWebView\Application\*\msedgewebview2.exe",
    "$env:LOCALAPPDATA\Microsoft\EdgeWebView\Application\*\msedgewebview2.exe"
)
$WebViewRuntime = $WebViewCandidates |
    ForEach-Object { Get-ChildItem -Path $_ -ErrorAction SilentlyContinue } |
    Select-Object -First 1
$Computer = Get-CimInstance Win32_ComputerSystem
$Processor = Get-CimInstance Win32_Processor | Select-Object -First 1
$RpcMap = [ordered]@{}
foreach ($Line in $RpcLines) {
    if ($Line -match '^([^=]+)=(.*)$') { $RpcMap[$Matches[1]] = $Matches[2] }
}
$Result = [ordered]@{
    schema = 1
    generated_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    environment = [ordered]@{
        windows_version = [Environment]::OSVersion.VersionString
        processor = $Processor.Name
        processor_count = [Environment]::ProcessorCount
        memory_bytes = $Computer.TotalPhysicalMemory
        python = (& python --version 2>&1 | Out-String).Trim()
        webview2 = if ($WebViewRuntime) { $WebViewRuntime.VersionInfo.ProductVersion } else { $null }
        rust_profile = "release"
    }
    rpc_internal = $RpcMap
    host = [ordered]@{
        startup_to_process_observed_ms = [Math]::Round($ObservedStartupMs, 3)
        process_tree_pids = @($ProcessTreeIds)
        process_tree_working_set_bytes = $WorkingSet
        webview2_process_count = $WebViewIds.Count
        webview2_working_set_bytes = $WebViewWorkingSet
        idle_cpu_percent = if ($null -eq $IdleCpuPercent) { $null } else { [Math]::Round($IdleCpuPercent, 3) }
        shutdown_ms = [Math]::Round($ShutdownStarted.Elapsed.TotalMilliseconds, 3)
        exit_code = $Process.ExitCode
        visible_window = "manual"
    }
    methodology = "Internal RPC values come from runtime_bench and do not include WebView2 IPC. Host startup is process-observed after a two-second initialization window; visible-window timing and frontend interaction require manual observation."
}
$Result | ConvertTo-Json -Depth 8 | Set-Content -Path $ResultsPath -Encoding UTF8
Write-Output "Machine-readable benchmark results: $ResultsPath"
