# georun.ps1 - poll-and-kill runner for the Wave 6 geometry / cast-boundary
# probes.  Same shape as qarun.ps1: launch detached, watch for an output file
# newer than the launch, then kill.  A lino programme that fails still exits 0,
# so the ONLY evidence of success is a fresh output file.
param(
    [Parameter(Mandatory=$true)][string]$Exe,
    [Parameter(Mandatory=$true)][string]$Out,
    [int]$TimeoutSec = 240
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not [IO.Path]::IsPathRooted($Exe)) { $Exe = Join-Path $here $Exe }
$Exe = (Resolve-Path $Exe).Path
$out = Join-Path $here $Out

$startedAt = Get-Date
Start-Sleep -Milliseconds 1100

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName         = $Exe
$psi.UseShellExecute  = $false
$psi.WorkingDirectory = $here
$proc = [System.Diagnostics.Process]::Start($psi)

$got = $null
for ($i = 0; $i -lt ($TimeoutSec * 2); $i++) {
    Start-Sleep -Milliseconds 500
    if ((Test-Path $out) -and ((Get-Item $out).LastWriteTime -gt $startedAt)) {
        Start-Sleep -Milliseconds 700
        $got = $out; break
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
    Write-Output ("RUN-FAIL no fresh {0} after {1}s" -f $Out, $elapsed)
    exit 3
}
