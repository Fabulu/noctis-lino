# geobreakrun.ps1 - build and run every deliberately broken geoconv and
# REQUIRE each one to be caught by the exact-rational referee.
#
# A break that compiles and then still passes is the failure this script
# exists to find: it means the probe is not measuring what it claims to.
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$breaks = @('nochop', 'spilled', 'nospill', 'chopd32', 'nosext')
$bad = @()

foreach ($b in $breaks) {
    Write-Output "=== break: $b ==="
    & python (Join-Path $here 'geomkbreak.py') $b
    if ($LASTEXITCODE -ne 0) { $bad += "$b (generator failed)"; continue }

    $r = & powershell -ExecutionPolicy Bypass -File (Join-Path $here '..\lino_build.ps1') `
                      -Src (Join-Path $here 'geocastbrk.txt')
    Write-Output "  build: $r"
    if ($LASTEXITCODE -ne 0) { $bad += "$b (did not compile - a break must be WRONG, not BROKEN)"; continue }

    Remove-Item -LiteralPath (Join-Path $here 'geocastbrk.bin') -ErrorAction SilentlyContinue
    $r = & powershell -ExecutionPolicy Bypass -File (Join-Path $here 'georun.ps1') `
                      -Exe geocastbrk.exe -Out geocastbrk.bin
    Write-Output "  run:   $r"
    if ($LASTEXITCODE -ne 0) { $bad += "$b (produced no output)"; continue }

    $spec = & python (Join-Path $here 'geospec.py') (Join-Path $here 'geocastbrk.bin')
    $code = $LASTEXITCODE
    $spec | Where-Object { $_ -match 'DIFFER|SPEC (FAIL|OK)' } | ForEach-Object { "  $_" }
    if ($code -eq 0) { $bad += "$b (SURVIVED the referee)" }
    else { Write-Output "  CAUGHT" }
    Write-Output ""
}

if ($bad.Count) {
    Write-Output "BREAK-FAIL: $($bad.Count) break(s) not caught:"
    $bad | ForEach-Object { "  $_" }
    exit 1
}
Write-Output "BREAK-OK: all $($breaks.Count) breaks compiled, ran, and were caught."
exit 0
