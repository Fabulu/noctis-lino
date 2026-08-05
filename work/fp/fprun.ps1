# fprun.ps1 - run every schedule through both implementations and diff.
#
# For each schedule id: generate the vectors, run the C hardware reference,
# run the L.in.oleum build with the poll-and-kill pattern, compare.
#
# Usage: powershell -ExecutionPolicy Bypass -File fprun.ps1 [-Exe fptest.exe]

param(
    [string]$Exe = 'fptest.exe',
    [int[]]$Scheds = @(1,2,3,4,5,6,7,8,9,10,11,12,13,20,21,22)
)
$ErrorActionPreference = 'Stop'
$here = Split-Path $MyInvocation.MyCommand.Path -Parent
Set-Location $here

$names = @{
    1='FAdd'; 2='FSub'; 3='FMul'; 4='FQuo'; 5='FSqrt'; 6='FNeg'; 7='FAbs';
    8='FSin'; 9='FCos'; 10='FAtan2'; 11='FCmp'; 12='IntToF'; 13='F32Narrow';
    20='NsIdentity'; 21='Prod4'; 22='Prod4Spilled'
}

$fails = 0
foreach ($s in $Scheds) {
    & python fpvecgen.py $s fpvec.bin | Out-Null
    & .\fpref.exe fpvec.bin fprefout.bin | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Output "REF FAIL on schedule $s"; $fails++; continue }

    Remove-Item -LiteralPath (Join-Path $here 'fpout.bin') -ErrorAction SilentlyContinue
    $r = & powershell -ExecutionPolicy Bypass -File ..\..\tests\linorun.ps1 `
            -Exe (Join-Path $here $Exe) -Out (Join-Path $here 'fpout.bin') -TimeoutSec 60
    if ($r -notmatch '^RAN-OK') { Write-Output "RUN FAIL on schedule $s : $r"; $fails++; continue }

    & python fpdiff.py fpout.bin fprefout.bin $names[$s]
    if ($LASTEXITCODE -ne 0) { $fails++ }
}
Write-Output ""
Write-Output "SCHEDULES WITH DIFFERENCES: $fails"
exit $fails
