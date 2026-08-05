# fpbreakrun.ps1 - run the deliberately broken builds and REQUIRE them to fail.
#
# A break that passes means the harness is not testing what it claims to.
# So the verdicts are inverted: a break MUST show differences, and a
# schedule the break did not touch MUST NOT.
#
# NOTE for anyone editing this: a PowerShell function returns its whole
# pipeline output, not just the value after `return`.  Writing this with a
# function that both prints and returns a code made $rc an ARRAY, and
# `$rc -eq 0` on an array is a filter, not a test - which reported
# collateral damage that did not exist.  The exit code is passed back in a
# script-scope variable for that reason.

$ErrorActionPreference = 'Stop'
$here = Split-Path $MyInvocation.MyCommand.Path -Parent
Set-Location $here
$script:rc = 0

function Run-One($exe, $out, $sched, $label) {
    & python fpvecgen.py $sched fpvec.bin | Out-Null
    & .\fpref.exe fpvec.bin fprefout.bin | Out-Null
    Remove-Item -LiteralPath (Join-Path $here $out) -ErrorAction SilentlyContinue
    $r = & powershell -ExecutionPolicy Bypass -File ..\..\tests\linorun.ps1 `
            -Exe (Join-Path $here $exe) -Out (Join-Path $here $out) -TimeoutSec 60
    if ($r -notmatch '^RAN-OK') { Write-Output "RUN FAIL: $r"; $script:rc = 99; return }
    & python fpdiff.py $out fprefout.bin $label
    $script:rc = $LASTEXITCODE
}

$problems = 0

Write-Output "=== BREAK 1: fpx87bad - FSub is fsubr, FQuo is fdivr ==="
foreach ($s in @(2, 4)) {
    Run-One 'fpbreakenc.exe' 'fpbreakencout.bin' $s "brk-enc-$s"
    if ($script:rc -eq 0) { Write-Output "  *** BREAK PASSED - the harness is blind ***"; $problems++ }
    else { Write-Output "  -> break detected, as required" }
}
Write-Output "--- and the schedules it did NOT touch must still pass ---"
foreach ($s in @(1, 3)) {
    Run-One 'fpbreakenc.exe' 'fpbreakencout.bin' $s "brk-enc-$s"
    if ($script:rc -ne 0) { Write-Output "  *** collateral damage on schedule $s ***"; $problems++ }
    else { Write-Output "  -> untouched, as required" }
}

Write-Output ""
Write-Output "=== BREAK 2: fpconvbad - FToIntChop has no fldcw bracket ==="
Run-One 'fpbreakchop.exe' 'fpbreakchopout.bin' 1 'brk-chop'
if ($script:rc -eq 0) { Write-Output "  *** BREAK PASSED - the cast rule is not tested ***"; $problems++ }
else { Write-Output "  -> break detected, as required" }

Write-Output ""
Write-Output "BREAKS THAT FAILED TO FAIL: $problems"
exit $problems
