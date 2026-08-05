# fball.ps1 - build and run the reference builds and every sabotage, in one
# batch, so the display windows flash once rather than thirty times spread over
# an afternoon.
#
# Three harnesses now, not one:
#   fbmain / fbshort   the shell (fbshort is the reference at the SABOTAGE
#                      driver constants, so a sabotage is compared against a
#                      reference that ran the same soak length)
#   fbsrv              the servo battery
#   fbshade            the shade-destination and fade-compounding battery
#
# Usage: powershell -File fball.ps1 [-Only a,b,c] [-NoRun] [-NoBuild]

param([string[]]$Only, [switch]$NoRun, [switch]$NoBuild)

$ErrorActionPreference = 'Continue'
$here  = Split-Path -Parent $MyInvocation.MyCommand.Path
$build = Join-Path (Split-Path -Parent $here) 'lino_build.ps1'

$targets = @(
  'fbmain','fbshort','fbsrv','fbshade',
  'fbbreak1','fbbreak2','fbbreak3','fbbreak4','fbbreak5',
  'fbbreak6','fbbreak7','fbbreak8','fbbreak9','fbbreak10',
  'fbsrvrunstart','fbsrvunsigned','fbsrvwidemax','fbsrvtrunc',
  'fbsrvclampfl','fbsrvnofold',
  'fbmaskspot','fbmaskcirrus','fbsegbase',
  'fbpadonemagic','fbpadnodigit','fbpad9walk',
  'fbcanstubpoison','fbcanconst','fbshdst','fbs12'
)
if ($Only) { $targets = $Only }

$fail = 0
foreach ($t in $targets) {
    if (-not (Test-Path (Join-Path $here "$t.txt"))) {
        Write-Output "NO-SOURCE  $t"; $fail++; continue
    }
    if (-not $NoBuild) {
        $r = & powershell -ExecutionPolicy Bypass -File $build -Src (Join-Path $here "$t.txt")
        if ($LASTEXITCODE -ne 0) { Write-Output "BUILD-FAIL $t : $r"; $fail++; continue }
    }
    if ($NoRun) { Write-Output "BUILD-OK   $t"; continue }
    $r = & powershell -ExecutionPolicy Bypass -File (Join-Path $here 'fbrun.ps1') `
            -Exe "$t.exe" -Tag $t -TimeoutSec 300
    if ($LASTEXITCODE -ne 0) { Write-Output "RUN-FAIL   $t : $r"; $fail++; continue }
    Write-Output "RUN-OK     $t : $r"
}
Write-Output "failures: $fail"
