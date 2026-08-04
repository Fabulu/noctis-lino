# lino_build.ps1 - drive the L.in.oleum compiler non-interactively.
#
# The compiler is a subsystem-2 (GUI) binary: it never writes to stdout and it
# lingers on screen until dismissed. So we detect completion from the files it
# leaves behind and kill it as soon as they appear.
#
#   errorlog.txt : written for BOTH warnings and errors, and it lands ~1s
#                  BEFORE the .exe. Its mere existence is not failure - only
#                  lines containing "error:" are fatal.
#   <name>.exe   : the real success signal.
#
# Usage: powershell -File lino_build.ps1 -Src C:\path\to\prog.txt [-TimeoutSec 240]

param(
    [Parameter(Mandatory = $true)][string]$Src,
    [int]$TimeoutSec = 240,
    [string]$Compiler = 'C:\programmieren\linoleum\main\compiler.exe',
    [string]$LinoEnv  = 'C:\programmieren\linoleum\main'
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path $Src)) { Write-Output "FAIL: source not found: $Src"; exit 2 }
$Src = (Resolve-Path $Src).Path

# The compiler splits its command line on '--' wherever it occurs, including
# inside a path. A path containing '--' silently truncates and the build dies
# with a bogus "error reading cpu pack". Refuse rather than mislead.
foreach ($p in @($Src, $LinoEnv)) {
    if ($p -match '--') { Write-Output "FAIL: path contains '--', which breaks the lino argument parser: $p"; exit 2 }
}

$dir      = Split-Path $Src -Parent
$base     = [IO.Path]::GetFileNameWithoutExtension($Src)
$leaf     = Split-Path $Src -Leaf
$outExe   = Join-Path $dir "$base.exe"
$strayExe = Join-Path $dir "$leaf .exe"     # produced if the arg picks up a trailing space
$errorLog = Join-Path $dir 'errorlog.txt'

Remove-Item $outExe, $strayExe, $errorLog -ErrorAction SilentlyContinue
$startedAt = Get-Date

# Launch via .NET rather than Start-Process: Start-Process appends a trailing
# space to the argument string, which the compiler folds into the output
# filename ("prog.txt .exe"). ProcessStartInfo.Arguments is passed verbatim.
$argLine = "--sys:win32--cpu:i386--ext:.exe--env:$LinoEnv--src:$Src"
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName        = $Compiler
$psi.Arguments       = $argLine
$psi.UseShellExecute = $false
$psi.WorkingDirectory = $dir
$proc = [System.Diagnostics.Process]::Start($psi)

function Get-Fresh($path) {
    if ((Test-Path $path) -and ((Get-Item $path).LastWriteTime -gt $startedAt)) { return $path }
    return $null
}

$built = $null
for ($i = 0; $i -lt $TimeoutSec; $i++) {
    Start-Sleep -Milliseconds 500

    $built = (Get-Fresh $outExe); if (-not $built) { $built = (Get-Fresh $strayExe) }
    if ($built) { Start-Sleep -Milliseconds 400; break }

    # Fatal errors mean no .exe will ever appear - stop waiting.
    if (Test-Path $errorLog) {
        if ((Get-Content $errorLog -Raw) -match 'error:') { break }
    }
    if ($proc.HasExited) { break }
}

if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
$elapsed = [math]::Round(((Get-Date) - $startedAt).TotalSeconds, 1)

# Normalise the stray name if the compiler produced one.
if ($built -eq $strayExe) { Move-Item $strayExe $outExe -Force; $built = $outExe }

$warnings = @()
$errors   = @()
if (Test-Path $errorLog) {
    foreach ($line in (Get-Content $errorLog)) {
        if ($line -match 'error:')       { $errors   += $line.Trim() }
        elseif ($line -match 'warning:') { $warnings += $line.Trim() }
    }
}

if ($errors.Count) {
    Write-Output "FAIL after ${elapsed}s - $($errors.Count) error(s):"
    $errors | ForEach-Object { "  $_" }
    exit 1
}
elseif ($built) {
    Write-Output ("OK  {0}  {1} bytes  {2}s" -f $built, (Get-Item $built).Length, $elapsed)
    if ($warnings.Count) {
        Write-Output "  $($warnings.Count) warning(s):"
        $warnings | ForEach-Object { "    $_" }
    }
    exit 0
}
else {
    Write-Output "TIMEOUT after ${elapsed}s - no .exe and no fatal error. Compiler may be showing a dialog."
    exit 3
}
