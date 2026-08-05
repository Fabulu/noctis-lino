# qarun.ps1 - poll-and-kill runner for the QA verification probe.
param(
    [Parameter(Mandatory=$true)][string]$Exe,
    [Parameter(Mandatory=$true)][string]$Out,
    [Parameter(Mandatory=$true)][string]$Tag,
    [int]$TimeoutSec = 240
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not [IO.Path]::IsPathRooted($Exe)) { $Exe = Join-Path $here $Exe }
$Exe = (Resolve-Path $Exe).Path
$out   = Join-Path $here $Out
$final = Join-Path $here "$Tag.bin"
Remove-Item -LiteralPath $final -ErrorAction SilentlyContinue
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
    Move-Item -LiteralPath $got -Destination $final -Force
    $it = Get-Item $final
    $h  = (Get-FileHash $final -Algorithm SHA256).Hash.ToLower()
    Write-Output ("RAN-OK {0} {1} bytes {2}s sha256 {3}" -f $final, $it.Length, $elapsed, $h)
    exit 0
} else {
    Write-Output ("RUN-FAIL no fresh {0} for {1} after {2}s" -f $Out, $Tag, $elapsed)
    exit 3
}
