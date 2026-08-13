[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [int]$ProcessId,
    [int]$DurationSeconds = 180,
    [string]$OutputDirectory = 'surface-session',
    [switch]$Jetpack
)

$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Drawing
if (-not ([System.Management.Automation.PSTypeName]'NoctisSurfaceDebugWin32').Type) {
    Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class NoctisSurfaceDebugWin32 {
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int Left, Top, Right, Bottom; }
    [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, ref RECT r);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint flags);
}
'@
}

$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$outputPath = if ([IO.Path]::IsPathRooted($OutputDirectory)) {
    [IO.Path]::GetFullPath($OutputDirectory)
} else {
    [IO.Path]::GetFullPath((Join-Path $projectRoot $OutputDirectory))
}
New-Item -ItemType Directory -Path $outputPath -Force | Out-Null
$logPath = Join-Path $outputPath 'session.log'

function Send-Key {
    param([IntPtr]$Handle, [int]$VirtualKey, [int]$ScanCode, [bool]$Down)
    $message = if ($Down) { 0x0100 } else { 0x0101 }
    $flags = if ($Down) { ($ScanCode -shl 16) -bor 1 } else { 0xC0000001 -bor ($ScanCode -shl 16) }
    [NoctisSurfaceDebugWin32]::PostMessage(
        $Handle, $message, [IntPtr]$VirtualKey, [IntPtr]$flags
    ) | Out-Null
}

function Save-Frame {
    param([IntPtr]$Handle, [string]$Path)
    $rect = New-Object NoctisSurfaceDebugWin32+RECT
    if (-not [NoctisSurfaceDebugWin32]::GetWindowRect($Handle, [ref]$rect)) { return }
    $width = $rect.Right - $rect.Left
    $height = $rect.Bottom - $rect.Top
    if ($width -lt 100 -or $height -lt 100) { return }
    $bitmap = New-Object Drawing.Bitmap $width, $height, ([Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $graphics = [Drawing.Graphics]::FromImage($bitmap)
    try {
        # These sessions are deliberately visible. Copy the composed desktop
        # window because iGUI's retained client surface can make PrintWindow
        # report success while returning a black bitmap after focus changes.
        $graphics.CopyFromScreen(
            $rect.Left, $rect.Top, 0, 0, [Drawing.Size]::new($width, $height)
        )
        $bitmap.Save($Path, [Drawing.Imaging.ImageFormat]::Png)
    } finally {
        $graphics.Dispose()
        $bitmap.Dispose()
    }
}

$process = Get-Process -Id $ProcessId -ErrorAction Stop
$deadline = [DateTime]::UtcNow.AddSeconds(15)
do {
    Start-Sleep -Milliseconds 100
    $process.Refresh()
} until ($process.HasExited -or $process.MainWindowHandle -ne [IntPtr]::Zero -or [DateTime]::UtcNow -ge $deadline)
if ($process.HasExited -or $process.MainWindowHandle -eq [IntPtr]::Zero) {
    throw "No live Noctis window for PID $ProcessId"
}

$handle = $process.MainWindowHandle
$stopwatch = [Diagnostics.Stopwatch]::StartNew()
$nextCapture = 0
$nextYaw = 12
$yawRight = $false
$activeYaw = 0
$yawReleaseAt = -1

"START pid=$ProcessId jetpack=$Jetpack duration=$DurationSeconds" | Set-Content -Path $logPath
Send-Key -Handle $handle -VirtualKey 0x57 -ScanCode 0x11 -Down $true
if ($Jetpack) {
    Send-Key -Handle $handle -VirtualKey 0x20 -ScanCode 0x39 -Down $true
}

try {
    while ($stopwatch.Elapsed.TotalSeconds -lt $DurationSeconds) {
        Start-Sleep -Milliseconds 100
        $process.Refresh()
        if ($process.HasExited) {
            "EXIT second=$([int]$stopwatch.Elapsed.TotalSeconds) code=$($process.ExitCode)" | Add-Content -Path $logPath
            break
        }
        $second = [int]$stopwatch.Elapsed.TotalSeconds
        if ($second -ge $nextCapture) {
            $frame = Join-Path $outputPath ("frame-{0:D3}.png" -f $second)
            Save-Frame -Handle $handle -Path $frame
            "CAPTURE second=$second file=$([IO.Path]::GetFileName($frame))" | Add-Content -Path $logPath
            $nextCapture += 10
        }
        if ($activeYaw -ne 0 -and $second -ge $yawReleaseAt) {
            $scan = if ($activeYaw -eq 0x25) { 0x4B } else { 0x4D }
            Send-Key -Handle $handle -VirtualKey $activeYaw -ScanCode $scan -Down $false
            $activeYaw = 0
        }
        if ($activeYaw -eq 0 -and $second -ge $nextYaw) {
            $yawRight = -not $yawRight
            $activeYaw = if ($yawRight) { 0x27 } else { 0x25 }
            $scan = if ($yawRight) { 0x4D } else { 0x4B }
            Send-Key -Handle $handle -VirtualKey $activeYaw -ScanCode $scan -Down $true
            $yawReleaseAt = $second + 2
            $nextYaw += 18
            "YAW second=$second direction=$(if ($yawRight) {'right'} else {'left'})" | Add-Content -Path $logPath
        }
    }
} finally {
    Send-Key -Handle $handle -VirtualKey 0x57 -ScanCode 0x11 -Down $false
    Send-Key -Handle $handle -VirtualKey 0x20 -ScanCode 0x39 -Down $false
    Send-Key -Handle $handle -VirtualKey 0x25 -ScanCode 0x4B -Down $false
    Send-Key -Handle $handle -VirtualKey 0x27 -ScanCode 0x4D -Down $false
    "DONE second=$([int]$stopwatch.Elapsed.TotalSeconds)" | Add-Content -Path $logPath
}
