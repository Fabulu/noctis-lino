# fball.ps1 - build and run the Wave 5 reference shell and all ten sabotages,
# in one batch, so the display windows flash once rather than eleven times
# spread over an afternoon.
#
# Usage: powershell -File fball.ps1 [-Only fbmain] [-NoRun]

param([string]$Only = "", [switch]$NoRun, [switch]$NoBuild)

$ErrorActionPreference = 'Continue'
$here  = Split-Path -Parent $MyInvocation.MyCommand.Path
$build = Join-Path (Split-Path -Parent $here) 'lino_build.ps1'

$targets = @('fbmain')
1..10 | ForEach-Object { $targets += "fbbreak$_" }
if ($Only) { $targets = @($Only) }

$fail = 0
foreach ($t in $targets) {
    if (-not $NoBuild) {
        $r = & powershell -ExecutionPolicy Bypass -File $build -Src (Join-Path $here "$t.txt")
        if ($LASTEXITCODE -ne 0) { Write-Output "BUILD-FAIL $t : $r"; $fail++; continue }
        Write-Output "BUILD-OK   $t"
    }
    if ($NoRun) { continue }
    $timeout = if ($t -eq 'fbmain') { 120 } else { 60 }
    $r = & powershell -ExecutionPolicy Bypass -File (Join-Path $here 'fbrun.ps1') `
            -Exe "$t.exe" -Tag $t -TimeoutSec $timeout
    if ($LASTEXITCODE -ne 0) { Write-Output "RUN-FAIL   $t : $r"; $fail++; continue }
    Write-Output "RUN-OK     $t : $r"
}
Write-Output "failures: $fail"
