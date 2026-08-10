# w7arun.ps1 - poll-and-kill runner for the Wave 7a lino programme.
#
# A compiled L.in.oleum programme is a subsystem-2 (GUI) binary: it writes
# nothing to stdout and it does not exit on its own. So it is launched
# detached, its OUTPUT FILE is polled for a timestamp strictly newer than the
# launch, and the process is then killed. It is never run in the foreground.
# The optional -RequireCleanExit mode waits for a naturally observed exit.
#
# The dump is 1-3 MB and the writer sets the file SIZE after the write, so a
# freshly-appeared file is not yet a complete one: the length has to stop
# changing before it is declared done. tests/linorun.ps1 does not do that,
# which is why this wave has its own runner.
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
$Exe = (Resolve-Path $Exe).Path

Remove-Item -LiteralPath $Out -Force -ErrorAction SilentlyContinue
$startedAt = Get-Date
Start-Sleep -Milliseconds 1100   # NTFS timestamp granularity

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName         = $Exe
$psi.Arguments        = ''
$psi.UseShellExecute  = $false
$psi.WorkingDirectory = (Split-Path $Exe -Parent)
$proc = [System.Diagnostics.Process]::Start($psi)

if ($ActivateWindow) {
    Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class W7Window {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int command);
}
'@
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        Start-Sleep -Milliseconds 100
        $proc.Refresh()
        if ($proc.HasExited) { break }
        if ($proc.MainWindowHandle -ne [IntPtr]::Zero) {
            [W7Window]::ShowWindow($proc.MainWindowHandle, 5) | Out-Null
            [W7Window]::SetForegroundWindow($proc.MainWindowHandle) | Out-Null
            break
        }
    }
}

$seen = $null
$cleanExitObserved = $false
$cleanExitCode = $null
try {
    for ($i = 0; $i -lt ($TimeoutSec * 2); $i++) {
        Start-Sleep -Milliseconds 500
        if ((Test-Path $Out) -and ((Get-Item $Out).LastWriteTime -gt $startedAt)) {
            $len = (Get-Item $Out).Length
            Start-Sleep -Milliseconds 700
            if ((Get-Item $Out).Length -eq $len) {
                $seen = $len
                if (-not $RequireCleanExit -or $proc.HasExited) { break }
            }
        }
        if ($proc.HasExited) {
            $proc.Refresh()
            $cleanExitObserved = $true
            $cleanExitCode = $proc.ExitCode
            break
        }
    }
} finally {
    # Capture natural termination before any force-kill. HasExited after
    # Stop-Process is not evidence of a clean exit.
    if ($proc.HasExited) {
        $proc.Refresh()
        if (-not $cleanExitObserved) {
            $cleanExitObserved = $true
            $cleanExitCode = $proc.ExitCode
        }
    } else {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
}

$elapsed = [math]::Round(((Get-Date) - $startedAt).TotalSeconds, 1)
if ($seen -ne $null -and (-not $RequireCleanExit -or ($cleanExitObserved -and $cleanExitCode -eq 0))) {
    $h = (Get-FileHash $Out -Algorithm SHA256).Hash.ToLower()
    if ($RequireCleanExit) {
        Write-Output ("RAN-OK {0} {1} bytes {2}s clean-exit sha256 {3}" -f $Out, $seen, $elapsed, $h)
    } else {
        Write-Output ("RAN-OK {0} {1} bytes {2}s sha256 {3}" -f $Out, $seen, $elapsed, $h)
    }
    exit 0
} elseif ($RequireCleanExit -and $seen -ne $null) {
    if ($cleanExitObserved) {
        Write-Output ("RUN-FAIL no clean exit (exit code {0}) after {1}s" -f $cleanExitCode, $elapsed)
    } else {
        Write-Output ("RUN-FAIL no clean exit after {0}s" -f $elapsed)
    }
    exit 4
} else {
    Write-Output ("RUN-FAIL no settled {0} after {1}s" -f $Out, $elapsed)
    exit 3
}
