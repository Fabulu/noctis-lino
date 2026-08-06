# su-run.ps1 - the poll-and-kill runner for the Wave 7a lino port.
#
# A compiled L.in.oleum programme is a subsystem-2 (GUI) binary: it never
# writes to stdout and it does not exit on its own. So it is launched
# detached, its OUTPUT FILE is polled for a timestamp newer than the launch,
# and it is then killed. Never run it in the foreground.
#
#   powershell -ExecutionPolicy Bypass -File work\su-run.ps1 [-TimeoutSec 900]

param(
    [string]$Exe = 'C:\programmieren\linoleum\work\sumain.exe',
    [string]$Out = 'C:\programmieren\linoleum\work\su-out.bin',
    [int]$TimeoutSec = 900
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path $Exe)) { Write-Output "FAIL: no $Exe"; exit 2 }

Remove-Item -LiteralPath $Out -ErrorAction SilentlyContinue
$startedAt = Get-Date

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName         = $Exe
$psi.Arguments        = ''
$psi.UseShellExecute  = $false
$psi.WorkingDirectory = (Split-Path $Exe -Parent)
$proc = [System.Diagnostics.Process]::Start($psi)

try {
    $seen = $null
    for ($i = 0; $i -lt ($TimeoutSec * 2); $i++) {
        Start-Sleep -Milliseconds 500
        if ((Test-Path $Out) -and ((Get-Item $Out).LastWriteTime -gt $startedAt)) {
            # the writer sets the size after the write, so wait for the
            # length to stop changing before declaring it done
            $len = (Get-Item $Out).Length
            Start-Sleep -Milliseconds 600
            if ((Get-Item $Out).Length -eq $len) { $seen = $len; break }
        }
        if ($proc.HasExited) { break }
    }
} finally {
    if (-not $proc.HasExited) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
}

$elapsed = [math]::Round(((Get-Date) - $startedAt).TotalSeconds, 1)
if (Test-Path $Out) {
    $it = Get-Item $Out
    Write-Output ("OK  {0}  {1} bytes  {2}s" -f $Out, $it.Length, $elapsed)
    exit 0
} else {
    Write-Output "TIMEOUT after ${elapsed}s - no output file"
    exit 3
}
