# fprun.ps1 - run every schedule through the portable backend and its oracle.
#
# Each run lives in a fresh temporary directory.  The current Lino driver and C
# reference are rebuilt there by default, so fixed historical filenames cannot
# overwrite fpvec.bin, fpout.bin, fprefout.bin, or fptest.exe in the source tree.
# -Exe is an explicit diagnostic override for a caller-supplied Lino executable.
#
# Usage: powershell -ExecutionPolicy Bypass -File fprun.ps1 [-Exe PATH]

param(
    [string]$Exe = '',
    [int[]]$Scheds = @(1,2,3,4,5,6,7,8,9,10,11,12,13,20,21,22),
    [string]$RunDir = ''
)
$ErrorActionPreference = 'Stop'
$here = Split-Path $MyInvocation.MyCommand.Path -Parent
$root = Resolve-Path (Join-Path $here '..\..')
$runner = Join-Path $root 'tests\linorun.ps1'
$builder = Join-Path $root 'lino_build.ps1'
$compiler = Join-Path $root 'main\lib\gen\compiler114m.exe'
$generator = Join-Path $here 'fpvecgen.py'
$diff = Join-Path $here 'fpdiff.py'
$transgrade = Join-Path $here 'fptransgrade.py'
$referenceSource = Join-Path $here 'fpref.c'
if (-not $RunDir) {
    $RunDir = Join-Path ([IO.Path]::GetTempPath()) `
        ("noctis-fp-{0}-{1}" -f $PID, [Guid]::NewGuid().ToString('N'))
}
if (Test-Path -LiteralPath $RunDir) { throw "run directory already exists: $RunDir" }
New-Item -ItemType Directory -Path $RunDir | Out-Null

$runExe = Join-Path $RunDir 'fptest.exe'
if ($Exe) {
    $sourceExe = if ([IO.Path]::IsPathRooted($Exe)) { $Exe } else { Join-Path $here $Exe }
    if (-not (Test-Path -LiteralPath $sourceExe)) { throw "test executable not found: $sourceExe" }
    Copy-Item -LiteralPath $sourceExe -Destination $runExe
}
else {
    foreach ($name in @('fpabi.txt', 'fpctl.txt', 'fpx87.txt', 'fpconv.txt',
                         'fpsoft.txt', 'fpchains.txt', 'fptest.txt')) {
        Copy-Item -LiteralPath (Join-Path $here $name) -Destination $RunDir
    }
    $testSource = Join-Path $RunDir 'fptest.txt'
    $buildResult = & powershell -NoProfile -ExecutionPolicy Bypass -File $builder `
        -Src $testSource -Compiler $compiler -Cpu i386m -TimeoutSec 300
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $runExe)) {
        throw "isolated fptest build failed: $($buildResult -join [Environment]::NewLine)"
    }
    Write-Output ($buildResult -join [Environment]::NewLine)
}

$reference = Join-Path $RunDir 'fpref.exe'
$referenceBuild = & gcc -O1 -o $reference $referenceSource 2>&1
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $reference)) {
    throw "isolated fpref build failed: $($referenceBuild -join [Environment]::NewLine)"
}

$names = @{
    1='FAdd'; 2='FSub'; 3='FMul'; 4='FQuo'; 5='FSqrt'; 6='FNeg'; 7='FAbs';
    8='FSin'; 9='FCos'; 10='FAtan2'; 11='FCmp'; 12='IntToF'; 13='F32Narrow';
    20='NsIdentity'; 21='Prod4'; 22='Prod4Spilled'
}

$fails = 0
foreach ($s in $Scheds) {
    $vec = Join-Path $RunDir 'fpvec.bin'
    $out = Join-Path $RunDir 'fpout.bin'
    $ref = Join-Path $RunDir ("fprefout-{0}.bin" -f $s)
    Remove-Item -LiteralPath $vec -ErrorAction SilentlyContinue
    $generatorResult = & python $generator $s $vec 2>&1
    $generatorExit = $LASTEXITCODE
    if ($generatorExit -ne 0 -or -not (Test-Path -LiteralPath $vec)) {
        Write-Output "VECTOR FAIL on schedule $s : $($generatorResult -join [Environment]::NewLine)"
        $fails++
        continue
    }
    $vectorBytes = [IO.File]::ReadAllBytes($vec)
    $validHeader = $vectorBytes.Count -ge 24 -and
        [BitConverter]::ToUInt32($vectorBytes, 0) -eq 0x46505643 -and
        [BitConverter]::ToUInt32($vectorBytes, 4) -eq 1 -and
        [BitConverter]::ToInt32($vectorBytes, 16) -eq $s -and
        [BitConverter]::ToUInt32($vectorBytes, 20) -eq 0x133F
    if (-not $validHeader) {
        Write-Output "VECTOR FAIL on schedule $s : generated header does not identify this schedule"
        $fails++
        continue
    }
    Remove-Item -LiteralPath $ref -ErrorAction SilentlyContinue
    & $reference $vec $ref | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Output "REF FAIL on schedule $s"; $fails++; continue }

    Remove-Item -LiteralPath $out -ErrorAction SilentlyContinue
    $r = & powershell -ExecutionPolicy Bypass -File $runner `
            -Exe $runExe -Out $out -TimeoutSec 60
    if ($r -notmatch '^RAN-OK') { Write-Output "RUN FAIL on schedule $s : $r"; $fails++; continue }

    if ($s -in @(8,9,10)) {
        & python $transgrade $vec $out $ref $names[$s]
    }
    else {
        & python $diff $out $ref $names[$s]
    }
    if ($LASTEXITCODE -ne 0) { $fails++ }
}
Write-Output ""
Write-Output "isolated evidence: $RunDir"
Write-Output "SCHEDULES WITH DIFFERENCES: $fails"
exit $fails
