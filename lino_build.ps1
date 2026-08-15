# lino_build.ps1 - drive the L.in.oleum compiler non-interactively.
#
# The compiler is a subsystem-2 (GUI) binary: it never writes to stdout and it
# lingers on screen until dismissed. So we detect completion from the files it
# leaves behind, wait for those files to settle, and then terminate it.
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
    [string]$LinoEnv  = 'C:\programmieren\linoleum\main',
    # The CPU pack is named per invocation, so an extended pack can sit beside
    # the stock one and the two toolchains never collide. The compiler checks
    # alignment * patterns + 8 == filesize exactly, so a mismatched pairing
    # fails loudly rather than miscompiling.
    [string]$Cpu = 'i386',
    # Large GUI builds append many stockfile compounds to the output.  Some
    # Windows scanners briefly lock a growing .exe between appends; compiling
    # under a neutral extension avoids that race, then the settled PE is
    # renamed to .exe.  Empty keeps the historical direct-.exe behaviour.
    [string]$StageExtension = ''
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
$compilerExtension = '.exe'
if ($StageExtension) {
    if ($StageExtension -notmatch '^\.[A-Za-z0-9]+$') {
        Write-Output "FAIL: StageExtension must be a simple extension such as .lxe"
        exit 2
    }
    $compilerExtension = $StageExtension
}
$compilerOut = Join-Path $dir "$base$compilerExtension"
$strayExe = Join-Path $dir "$leaf $compilerExtension" # produced if the arg picks up a trailing space
$errorLog = Join-Path $dir 'errorlog.txt'

Remove-Item $outExe, $compilerOut, $strayExe, $errorLog -ErrorAction SilentlyContinue
$startedAt = Get-Date
$startedUtc = [DateTime]::UtcNow

# Launch via .NET rather than Start-Process: Start-Process appends a trailing
# space to the argument string, which the compiler folds into the output
# filename ("prog.txt .exe"). ProcessStartInfo.Arguments is passed verbatim.
$argLine = "--sys:win32--cpu:$Cpu--ext:$compilerExtension--env:$LinoEnv--src:$Src"
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName        = $Compiler
$psi.Arguments       = $argLine
$psi.UseShellExecute = $false
$psi.CreateNoWindow  = $true
$psi.WindowStyle     = [System.Diagnostics.ProcessWindowStyle]::Hidden
$psi.WorkingDirectory = $dir
$proc = [System.Diagnostics.Process]::Start($psi)

function Get-FreshInfo($path) {
    if (-not (Test-Path -LiteralPath $path)) { return $null }
    $item = Get-Item -LiteralPath $path -ErrorAction SilentlyContinue
    if ($null -eq $item -or $item.LastWriteTimeUtc -le $startedUtc) { return $null }
    return [pscustomobject]@{
        Path          = $path
        Length        = [int64]$item.Length
        LastWriteTicks = [int64]$item.LastWriteTimeUtc.Ticks
    }
}

function Same-FileState($a, $b) {
    if ($null -eq $a -or $null -eq $b) { return $false }
    return ($a.Path -eq $b.Path -and $a.Length -eq $b.Length -and
            $a.LastWriteTicks -eq $b.LastWriteTicks)
}

function Same-OptionalFileState($a, $b) {
    # A clean build may not create errorlog.txt at all.  In that case the
    # absence of the relevant log is itself the stable state; a later log
    # appearance still resets the settle counter.
    if ($null -eq $a -and $null -eq $b) { return $true }
    return (Same-FileState $a $b)
}

# compiler.exe is a GUI subsystem process and normally remains resident after
# it has produced the files.  Seeing the PE header is therefore not completion:
# the compiler can still be appending the Lino payload and warning lines.  A
# candidate is accepted only after both files have remained unchanged for a
# run of polls.  The polling cadence is merely observation; file state, not a
# one-off sleep, is the completion authority.
$pollMilliseconds = 250
$settlePolls = 5                 # 1.0s of observed quiet, across both files
$built = $null
$settled = $false
$naturalExitBeforeSettle = $false
$previousExe = $null
$previousLog = $null
$stablePolls = 0
$deadline = $startedAt.AddSeconds([Math]::Max(0, $TimeoutSec))

while ((Get-Date) -lt $deadline) {
    $candidate = Get-FreshInfo $compilerOut
    if ($null -eq $candidate) { $candidate = Get-FreshInfo $strayExe }
    $logState = Get-FreshInfo $errorLog

    # Fatal conditions mean no valid output will ever appear.  "internal
    # problem:" is included because mismatched compiler/pack pairs use that
    # wording rather than "error:".
    if (Test-Path -LiteralPath $errorLog) {
        $logText = Get-Content -LiteralPath $errorLog -Raw -ErrorAction SilentlyContinue
        if ($logText -match 'error:|internal problem:') { break }
    }

    if ($null -ne $candidate -and $candidate.Length -gt 0) {
        if ((Same-FileState $candidate $previousExe) -and
            (Same-OptionalFileState $logState $previousLog)) {
            $stablePolls++
        }
        else {
            $stablePolls = 1
        }
        $previousExe = $candidate
        $previousLog = $logState

        if ($stablePolls -ge $settlePolls) {
            $built = $candidate.Path
            $settled = $true
            break
        }
    }
    else {
        # Missing/zero output is not a settled build.  An absent errorlog is
        # handled above as a valid stable state for warning-free builds; a
        # zero-byte or section-only PE can never be promoted merely because
        # the process stopped polling.
        $stablePolls = 0
        $previousExe = $null
        $previousLog = $null
    }

    if ($proc.HasExited) {
        # Some compiler builds exit naturally after a successful write while
        # others remain resident.  A natural non-zero exit is an error; a
        # natural zero exit still gets the same settle observations so a
        # complete artifact is accepted but a zero/partial one is not.
        if ($proc.ExitCode -ne 0 -or $null -eq $candidate -or $candidate.Length -le 0) {
            $naturalExitBeforeSettle = $true
            break
        }
    }

    $remaining = [int][Math]::Max(1, [Math]::Min($pollMilliseconds,
        (($deadline - (Get-Date)).TotalMilliseconds)))
    Start-Sleep -Milliseconds $remaining
}

$compilerExited = $proc.HasExited
if (-not $compilerExited) {
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
}
# Stop-Process is asynchronous.  Do not return while the GUI compiler is
# still unwinding: callers commonly start the next build immediately and a
# transient old process can otherwise be mistaken for that build.  The wait
# is only cleanup confirmation; settled file state above remains the build
# authority, and the bound prevents a stuck process from extending timeout
# handling indefinitely.
try { [void]$proc.WaitForExit(5000) } catch { }
$compilerExited = $proc.HasExited
$proc.Dispose()
$elapsed = [math]::Round(((Get-Date) - $startedAt).TotalSeconds, 1)

# Normalise the stray or deliberately staged name only after the compiler has
# stopped and the file has settled.  The contents are still a Win32 PE.
if ($built -and $built -ne $outExe) {
    Move-Item -LiteralPath $built -Destination $outExe -Force
    $built = $outExe
}

$warnings = @()
$errors   = @()
if (Test-Path $errorLog) {
    foreach ($line in (Get-Content $errorLog)) {
        if ($line -match 'error:|internal problem:') { $errors   += $line.Trim() }
        elseif ($line -match 'warning:')             { $warnings += $line.Trim() }
    }
}

if ($errors.Count) {
    Write-Output "FAIL after ${elapsed}s - $($errors.Count) error(s):"
    $errors | ForEach-Object { "  $_" }
    exit 1
}
elseif ($built -and $settled -and (Get-Item -LiteralPath $built).Length -gt 0) {
    Write-Output ("OK  {0}  {1} bytes  {2}s" -f $built, (Get-Item $built).Length, $elapsed)
    if ($warnings.Count) {
        Write-Output "  $($warnings.Count) warning(s):"
        $warnings | ForEach-Object { "    $_" }
    }
    exit 0
}
else {
    if ($naturalExitBeforeSettle) {
        Write-Output "FAIL after ${elapsed}s - compiler exited before output settled (zero/truncated/unsettled artifact rejected)."
    }
    else {
        Write-Output "TIMEOUT after ${elapsed}s - no settled .exe and no fatal error. Compiler may be showing a dialog."
    }
    exit 3
}
