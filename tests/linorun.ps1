# linorun.ps1 - run a compiled L.in.oleum program non-interactively.
#
# A lino program is a subsystem-2 (GUI) binary like the compiler: it never
# writes to stdout and it lingers on screen until dismissed. So we start it
# detached and poll for a fresh output file. By default the first settled fresh
# output is sufficient. Tests whose programme appends multiple records pass
# -ExpectedBytes, preventing an intermediate write from being mistaken for the
# finished artifact.
#
# The 1.1s pre-sleep exists because NTFS timestamps have coarse granularity:
# without it a stale output file from a previous run can look "fresh" and the
# test would silently grade the wrong bytes.
#
# Usage: powershell -File linorun.ps1 -Exe prog.exe -Out prog.bin [-TimeoutSec 60]
# Prints "RAN-OK <path> <bytes> <secs> sha256 <hex>" and exits 0, or exits 3.

param(
    [Parameter(Mandatory=$true)][string]$Exe,
    [Parameter(Mandatory=$true)][string]$Out,
    [int]$TimeoutSec = 60,
    [long]$ExpectedBytes = 0
)
$ErrorActionPreference = 'Stop'

if (-not (Test-Path $Exe)) { Write-Output "RUN-FAIL exe not found: $Exe"; exit 2 }
$Exe = (Resolve-Path $Exe).Path
$dir = Split-Path $Exe -Parent

$startedAt = Get-Date
Start-Sleep -Milliseconds 1100   # ensure any fresh write is strictly newer

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName         = $Exe
$psi.UseShellExecute  = $false
$psi.WorkingDirectory = $dir
$proc = [System.Diagnostics.Process]::Start($psi)

$got = $null
$sizeError = $null
for ($i = 0; $i -lt ($TimeoutSec * 2); $i++) {
    Start-Sleep -Milliseconds 500
    if ((Test-Path $Out) -and ((Get-Item $Out).LastWriteTime -gt $startedAt)) {
        $item = Get-Item $Out
        if ($ExpectedBytes -gt 0 -and $item.Length -gt $ExpectedBytes) {
            $sizeError = "output grew to $($item.Length) bytes, expected $ExpectedBytes"
            break
        }
        if ($ExpectedBytes -le 0 -or $item.Length -eq $ExpectedBytes) {
            $observedLength = $item.Length
            Start-Sleep -Milliseconds 500
            $settled = Get-Item $Out -ErrorAction SilentlyContinue
            if ($settled -and $settled.Length -eq $observedLength -and
                ($ExpectedBytes -le 0 -or $settled.Length -eq $ExpectedBytes)) {
                $got = $Out
                break
            }
        }
    }
    if ($proc.HasExited) { break }
}
if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
$elapsed = [math]::Round(((Get-Date) - $startedAt).TotalSeconds, 1)

if ($got) {
    $it = Get-Item $got
    $h  = (Get-FileHash $got -Algorithm SHA256).Hash.ToLower()
    Write-Output ("RAN-OK {0} {1} bytes {2}s sha256 {3}" -f $got, $it.Length, $elapsed, $h)
    exit 0
} else {
    if ($sizeError) {
        Write-Output "RUN-FAIL $sizeError"
    } elseif ($ExpectedBytes -gt 0) {
        $actual = if (Test-Path $Out) { (Get-Item $Out).Length } else { 0 }
        Write-Output ("RUN-FAIL no complete {0} after {1}s ({2}/{3} bytes)" -f
            $Out, $elapsed, $actual, $ExpectedBytes)
    } else {
        Write-Output ("RUN-FAIL no fresh {0} after {1}s" -f $Out, $elapsed)
    }
    exit 3
}
