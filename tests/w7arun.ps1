# w7arun.ps1 - run Wave 7 L.in.oleum programs on a private desktop.
#
# The dump is 1-3 MB and the writer sets the file size after the write, so the
# private runner waits for a fresh output whose size has settled before it
# terminates the GUI process. -RequireCleanExit additionally requires the
# program to terminate naturally with exit code zero.
#
#   powershell -ExecutionPolicy Bypass -File tests\w7arun.ps1 -Exe <exe> -Out <bin>

param(
    [Parameter(Mandatory = $true)][string]$Exe,
    [Parameter(Mandatory = $true)][string]$Out,
    [int]$TimeoutSec = 600,
    [switch]$RequireCleanExit,
    [switch]$ActivateWindow
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path $Exe)) { Write-Output "RUN-FAIL exe not found: $Exe"; exit 2 }
if ($ActivateWindow) {
    Write-Output "RUN-FAIL -ActivateWindow is incompatible with private-desktop execution"
    exit 2
}

$Exe = (Resolve-Path $Exe).Path
$dir = Split-Path $Exe -Parent
Remove-Item -LiteralPath $Out -Force -ErrorAction SilentlyContinue

$repo = Split-Path $PSScriptRoot -Parent
$privateRunner = Join-Path $repo 'tools\run_lino_program_private.py'
$runnerArgs = @(
    $privateRunner,
    "--executable=$Exe",
    "--working-directory=$dir",
    "--output=$Out",
    "--timeout=$TimeoutSec"
)
if ($RequireCleanExit) {
    $runnerArgs += '--require-clean-exit'
}

$runnerOutput = @(& python @runnerArgs)
$status = $LASTEXITCODE
$runnerOutput | Write-Output
exit $status
