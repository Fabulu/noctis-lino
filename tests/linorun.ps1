# linorun.ps1 - run a compiled L.in.oleum program non-interactively.
#
# A lino program is a subsystem-2 (GUI) binary like the compiler: it never
# writes to stdout and can linger until dismissed. Run it on a private,
# inactive desktop and poll for a fresh output file. By default the first
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

$repo = Split-Path $PSScriptRoot -Parent
$privateRunner = Join-Path $repo 'tools\run_lino_program_private.py'
$runnerOutput = @(& python $privateRunner `
    "--executable=$Exe" `
    "--working-directory=$dir" `
    "--output=$Out" `
    "--timeout=$TimeoutSec" `
    "--expected-bytes=$ExpectedBytes")
$status = $LASTEXITCODE
$runnerOutput | Write-Output
exit $status
