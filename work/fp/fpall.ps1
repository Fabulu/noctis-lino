# fpall.ps1 - regenerate, rebuild and re-run every part of the fp* engine.
#
#   powershell -ExecutionPolicy Bypass -File fpall.ps1
#
# Nothing here is incremental and nothing is cached: the chains are
# regenerated from fpsched.txt, every binary is rebuilt, every run is
# poll-and-kill, and the scores are re-derived.  A number that only
# reproduces when the previous output file is still lying around is not a
# number.

$ErrorActionPreference = 'Stop'
$here = Split-Path $MyInvocation.MyCommand.Path -Parent
Set-Location $here
$root = Resolve-Path (Join-Path $here '..\..')
$build = Join-Path $root 'lino_build.ps1'
$run = Join-Path $root 'tests\linorun.ps1'
$m114 = Join-Path $root 'main\lib\gen\compiler114m.exe'

Write-Output "=== 1. generate the chains from the schedule ==="
& python (Join-Path $root 'tools\genfp.py') fpsched.txt fpchains.txt
& python (Join-Path $root 'tools\genfp.py') --backend soft `
        --only NsIdentity,NsIdentityPermuted fpsched.txt fpchainssoft.txt
Write-Output ""
Write-Output "the native backend must REFUSE the exact chains:"
& python (Join-Path $root 'tools\genfp.py') --backend native fpsched.txt nul.tmp
if ($LASTEXITCODE -eq 0) { Write-Output "*** it did not refuse ***" } else { Write-Output "  refused, as required" }
Remove-Item -LiteralPath (Join-Path $here 'nul.tmp') -ErrorAction SilentlyContinue

Write-Output ""
Write-Output "=== 2. the deliberately broken variants ==="
& python fpmkbreak.py

Write-Output ""
Write-Output "=== 3. build ==="
foreach ($s in @('fpstar', 'fpstarnat', 'fptest', 'fpbreakenc', 'fpbreakchop')) {
    & powershell -ExecutionPolicy Bypass -File $build -Src (Join-Path $here "$s.txt")
}
& powershell -ExecutionPolicy Bypass -File $build -Src (Join-Path $here 'fpstarsoft.txt') `
        -Compiler $m114 -Cpu i386m
& gcc -O1 -o fpref.exe fpref.c
Write-Output "  fpref.exe (gcc hardware reference) rebuilt"

Write-Output ""
Write-Output "=== 4. the STARMAP oracle, X87 backend ==="
Remove-Item -LiteralPath (Join-Path $here 'fpstarout.bin') -ErrorAction SilentlyContinue
& powershell -ExecutionPolicy Bypass -File $run -Exe (Join-Path $here 'fpstar.exe') `
        -Out (Join-Path $here 'fpstarout.bin') -TimeoutSec 120
& python fpgrade.py

Write-Output ""
Write-Output "=== 5. the same oracle, NATIVE and SOFT backends ==="
Remove-Item -LiteralPath (Join-Path $here 'fpstarnatout.bin') -ErrorAction SilentlyContinue
& powershell -ExecutionPolicy Bypass -File $run -Exe (Join-Path $here 'fpstarnat.exe') `
        -Out (Join-Path $here 'fpstarnatout.bin') -TimeoutSec 120
Remove-Item -LiteralPath (Join-Path $here 'fpstarsoftout.bin') -ErrorAction SilentlyContinue
& powershell -ExecutionPolicy Bypass -File $run -Exe (Join-Path $here 'fpstarsoft.exe') `
        -Out (Join-Path $here 'fpstarsoftout.bin') -TimeoutSec 180
& python fpbackends.py

Write-Output ""
Write-Output "=== 6. scalar and conversion vectors vs the gcc x87 reference ==="
& powershell -ExecutionPolicy Bypass -File fprun.ps1

Write-Output ""
Write-Output "=== 7. the breaks, which must fail ==="
& powershell -ExecutionPolicy Bypass -File fpbreakrun.ps1
