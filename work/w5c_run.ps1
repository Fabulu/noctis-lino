# w5c_run.ps1 -- run a compiled lino probe with the poll-and-kill pattern and
# report the process's CPU time as well as its wall time.
#
# Same discipline as tests/linorun.ps1 (never start one and wait): launch
# detached, poll for the output file with an mtime strictly newer than launch,
# then Stop-Process.  The addition here is TotalProcessorTime, sampled just
# before the kill, which is the only way to see what a busy-wait tick actually
# costs -- a lino program cannot read its own CPU time.
#
#   powershell -File w5c_run.ps1 -Exe X.exe -Out X.bin [-TimeoutSec 180]

param(
    [Parameter(Mandatory=$true)][string]$Exe,
    [Parameter(Mandatory=$true)][string]$Out,
    [int]$TimeoutSec = 180
)
$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $Exe)) { Write-Output "RUN-FAIL exe not found: $Exe"; exit 2 }
$Exe = (Resolve-Path $Exe).Path
$dir = Split-Path $Exe -Parent

if (Test-Path -LiteralPath $Out) { Remove-Item -LiteralPath $Out -Force }

$startedAt = Get-Date
Start-Sleep -Milliseconds 1100

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName         = $Exe
$psi.UseShellExecute  = $false
$psi.WorkingDirectory = $dir
$proc = [System.Diagnostics.Process]::Start($psi)

$got = $null
$cpu = -1.0
$usr = -1.0
for ($i = 0; $i -lt ($TimeoutSec * 4); $i++) {
    Start-Sleep -Milliseconds 250
    if ((Test-Path -LiteralPath $Out) -and ((Get-Item -LiteralPath $Out).LastWriteTime -gt $startedAt)) {
        try {
            $proc.Refresh()
            $cpu = $proc.TotalProcessorTime.TotalMilliseconds
            $usr = $proc.UserProcessorTime.TotalMilliseconds
        } catch {}
        Start-Sleep -Milliseconds 400
        $got = $Out; break
    }
    if ($proc.HasExited) { break }
}
# Sample CPU time whether the program ended by itself or is still up: a lino
# program that finished normally is the common case here, and its accounting
# is still readable through the handle we are holding.
try { $proc.Refresh(); if ($cpu -lt 0) { $cpu = $proc.TotalProcessorTime.TotalMilliseconds; $usr = $proc.UserProcessorTime.TotalMilliseconds } } catch {}
if (-not $proc.HasExited) {
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
}
$elapsed = ((Get-Date) - $startedAt).TotalSeconds

if ($got) {
    $it = Get-Item -LiteralPath $got
    Write-Output ("RAN-OK {0} {1} bytes wall {2:N2}s cpu {3:N0}ms user {4:N0}ms" -f `
                  $got, $it.Length, $elapsed, $cpu, $usr)
    exit 0
} else {
    Write-Output ("RUN-FAIL no fresh {0} after {1:N1}s" -f $Out, $elapsed)
    exit 3
}
