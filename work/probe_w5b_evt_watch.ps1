# Drives probe_w5b_evt.exe. Phase B runs with ZERO isocalls and exits the
# instant the LUCK table shows anything, so the m1 -> m2 wall time is the
# latency from a posted WM_KEYDOWN to the application seeing it.
#
#   -NoPoke   the control: nothing is posted, so phase B must run to its
#             200,000,000-iteration cap with luckor still zero.
#
# PostMessage targets one window handle. Nothing enters the desktop input
# queue, so no other application can receive any of it.
param([switch]$NoPoke, [int]$PokeAfterMs = 700)

$ErrorActionPreference = 'Stop'
$dir = 'C:\programmieren\linoleum\work'
$exe = Join-Path $dir 'probe_w5b_evt.exe'
$res = Join-Path $dir 'probew5bevt.bin'
$m = 0..3 | ForEach-Object { Join-Path $dir "w5bem$_.bin" }

if (-not ([System.Management.Automation.PSTypeName]'W').Type) {
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class W {
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h,uint m,IntPtr w,IntPtr l);
}
"@
}

Remove-Item -LiteralPath $res -ErrorAction SilentlyContinue
foreach ($f in $m) { Remove-Item -LiteralPath $f -ErrorAction SilentlyContinue }

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $exe; $psi.UseShellExecute = $false; $psi.WorkingDirectory = $dir
$p = [System.Diagnostics.Process]::Start($psi)

$hwnd = [IntPtr]::Zero
$sw = [System.Diagnostics.Stopwatch]::StartNew()
while (-not (Test-Path $m[1])) {
    Start-Sleep -Milliseconds 20
    if ($p.HasExited -or $sw.ElapsedMilliseconds -gt 30000) { break }
    $p.Refresh(); if ($p.MainWindowHandle -ne 0) { $hwnd = $p.MainWindowHandle }
}
$bstart = $sw.ElapsedMilliseconds
$p.Refresh(); if ($p.MainWindowHandle -ne 0) { $hwnd = $p.MainWindowHandle }
"mode          : {0}" -f $(if ($NoPoke) {'CONTROL - nothing posted'} else {'poke'})
"phase B began : {0} ms after launch,  hwnd {1}" -f $bstart, $hwnd

$posted = $null
$m2at = $null
while ($true) {
    Start-Sleep -Milliseconds 20
    if ($p.HasExited) { break }
    $el = $sw.ElapsedMilliseconds - $bstart
    if (-not $NoPoke -and $null -eq $posted -and $el -ge $PokeAfterMs -and $hwnd -ne [IntPtr]::Zero) {
        [W]::PostMessage($hwnd,0x0100,[IntPtr]0x41,[IntPtr]0x001E0001) | Out-Null
        $posted = $sw.ElapsedMilliseconds - $bstart
        "WM_KEYDOWN 'A' posted at +{0} ms into phase B" -f $posted
    }
    if ($null -eq $m2at -and (Test-Path $m[2])) {
        $m2at = $sw.ElapsedMilliseconds - $bstart
        "phase B ended at +{0} ms into phase B" -f $m2at
        if (-not $NoPoke) {
            [W]::PostMessage($hwnd,0x0101,[IntPtr]0x41,[IntPtr]0xC01E0001) | Out-Null
        }
    }
    if (Test-Path $res) { Start-Sleep -Milliseconds 400; break }
    if ($sw.ElapsedMilliseconds -gt 90000) { "TIMEOUT"; break }
}
if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }

if ($null -ne $posted -and $null -ne $m2at) {
    "latency posted -> application saw it : {0} ms  (no isocall in between)" -f ($m2at - $posted)
}
if (Test-Path $res) { "result: $((Get-Item $res).Length) bytes" } else { "NO RESULT FILE" }
