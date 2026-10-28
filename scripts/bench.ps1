$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

cargo build --release -p kourosh-python --example runtime_bench
Write-Output "Measured embedded-Python RPC benchmark:"
& .\target\release\examples\runtime_bench.exe

cargo build --release -p kourosh-host
$Started = Get-Date
$Process = Start-Process -FilePath ".\target\release\kourosh-host.exe" -PassThru
try {
    Start-Sleep -Seconds 2
    $Elapsed = ((Get-Date) - $Started).TotalMilliseconds
    $Process.Refresh()
    Write-Output ("host_process_start_observed_ms={0:N3}" -f $Elapsed)
    $AllProcesses = @(Get-CimInstance Win32_Process | Select-Object ProcessId, ParentProcessId)
    $Ids = [System.Collections.Generic.HashSet[int]]::new()
    $Ids.Add($Process.Id) | Out-Null
    $Pending = [System.Collections.Generic.Queue[int]]::new()
    $Pending.Enqueue($Process.Id)
    while ($Pending.Count -gt 0) {
        $ParentId = $Pending.Dequeue()
        foreach ($Child in $AllProcesses | Where-Object { $_.ParentProcessId -eq $ParentId }) {
            if ($Ids.Add([int]$Child.ProcessId)) { $Pending.Enqueue([int]$Child.ProcessId) }
        }
    }
    $WorkingSet = (Get-Process -Id ([int[]]$Ids) -ErrorAction SilentlyContinue |
        Measure-Object -Property WorkingSet64 -Sum).Sum
    Write-Output ("host_process_tree_working_set_bytes={0}" -f $WorkingSet)
} finally {
    if (-not $Process.HasExited) {
        $Process.CloseMainWindow() | Out-Null
        $Process.WaitForExit(5000)
        if (-not $Process.HasExited) { $Process.Kill() }
    }
}
