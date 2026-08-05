# fbrun.ps1 - run one Wave 5 framebuffer build and collect its FBDUMP.
#
# A lino program is a subsystem-2 (GUI) binary: it never writes to stdout and
# it lingers on screen until dismissed.  So it is started detached, polled for
# work\fb-out.bin with a timestamp strictly newer than launch, and killed the
# moment that appears.  Every build writes the SAME filename, so the file is
# renamed to <tag>.bin afterwards and the next build cannot be graded against
# a stale artifact.
#
# Usage: powershell -File fbrun.ps1 -Exe fbmain.exe -Tag fbmain [-TimeoutSec 120]

param(
    [Parameter(Mandatory=$true)][string]$Exe,
    [Parameter(Mandatory=$true)][string]$Tag,
    [int]$TimeoutSec = 120
)
$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not [IO.Path]::IsPathRooted($Exe)) { $Exe = Join-Path $here $Exe }
if (-not (Test-Path $Exe)) { Write-Output "RUN-FAIL exe not found: $Exe"; exit 2 }
$Exe = (Resolve-Path $Exe).Path

$out   = Join-Path $here 'fb-out.bin'
$final = Join-Path $here "$Tag.bin"

Remove-Item -LiteralPath $final -ErrorAction SilentlyContinue
$startedAt = Get-Date
Start-Sleep -Milliseconds 1100      # NTFS timestamps are coarse

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName         = $Exe
$psi.UseShellExecute  = $false
$psi.WorkingDirectory = $here
$proc = [System.Diagnostics.Process]::Start($psi)

$got = $null
for ($i = 0; $i -lt ($TimeoutSec * 2); $i++) {
    Start-Sleep -Milliseconds 500
    if ((Test-Path $out) -and ((Get-Item $out).LastWriteTime -gt $startedAt)) {
        Start-Sleep -Milliseconds 600   # let the write settle
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
    Write-Output ("RUN-FAIL no fresh fb-out.bin for {0} after {1}s" -f $Tag, $elapsed)
    exit 3
}
