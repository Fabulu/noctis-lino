# Runs probe_w5b_excl.exe and records what the exclusive-mode switch does to
# the user's desktop: screen resolution, and the position of every visible
# top-level window, sampled before and after.
$ErrorActionPreference = 'Stop'
$dir = 'C:\programmieren\linoleum\work'
$exe = Join-Path $dir 'probe_w5b_excl.exe'
$res = Join-Path $dir 'probew5bexcl.bin'

if (-not ([System.Management.Automation.PSTypeName]'DW').Type) {
Add-Type @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
public static class DW {
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern int GetWindowTextW(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L,T,R,B; }
  public static List<string> Snap() {
    var outp = new List<string>();
    EnumWindows((h,l) => {
      if (!IsWindowVisible(h)) return true;
      var sb = new StringBuilder(200); GetWindowTextW(h, sb, 200);
      if (sb.Length == 0) return true;
      RECT r; GetWindowRect(h, out r);
      outp.Add(h.ToInt64() + "|" + sb.ToString() + "|" + r.L + "," + r.T + "," + r.R + "," + r.B);
      return true;
    }, IntPtr.Zero);
    return outp;
  }
}
"@
}
function ScreenWH {
  Add-Type -AssemblyName System.Windows.Forms
  $b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
  "$($b.Width)x$($b.Height)"
}

$before = [DW]::Snap()
$resBefore = ScreenWH
"desktop before : $resBefore, $($before.Count) visible top-level windows"

Remove-Item -LiteralPath $res -ErrorAction SilentlyContinue
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $exe; $psi.UseShellExecute = $false; $psi.WorkingDirectory = $dir
$p = [System.Diagnostics.Process]::Start($psi)
$sw = [System.Diagnostics.Stopwatch]::StartNew()
$midRes = $null
while ($true) {
    Start-Sleep -Milliseconds 200
    if ($p.HasExited) { break }
    $r = ScreenWH
    if ($r -ne $resBefore -and $null -eq $midRes) { $midRes = $r; "desktop DURING  : screen resolution changed to $r at $($sw.ElapsedMilliseconds) ms" }
    if (Test-Path $res) { Start-Sleep -Milliseconds 500; break }
    if ($sw.ElapsedMilliseconds -gt 90000) { "TIMEOUT"; break }
}
if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
Start-Sleep -Milliseconds 1500

$after = [DW]::Snap()
$resAfter = ScreenWH
"desktop after  : $resAfter, $($after.Count) visible top-level windows"
if ($null -eq $midRes) { "screen resolution never observed to change (poll was 200 ms)" }

$bh = @{}; foreach ($e in $before) { $k,$t,$r = $e -split '\|',3; $bh[$k] = @($t,$r) }
$moved = 0; $gone = 0; $new = 0
$movedList = @()
foreach ($e in $after) {
    $k,$t,$r = $e -split '\|',3
    if ($bh.ContainsKey($k)) { if ($bh[$k][1] -ne $r) { $moved++; $movedList += "  $t : $($bh[$k][1])  ->  $r" } }
    else { $new++ }
}
$ah = @{}; foreach ($e in $after) { $k = ($e -split '\|',3)[0]; $ah[$k] = 1 }
foreach ($k in $bh.Keys) { if (-not $ah.ContainsKey($k)) { $gone++ } }
"windows moved  : $moved    disappeared: $gone    new: $new"
if ($moved -gt 0) { "moved windows:"; $movedList | Select-Object -First 25 }
if (Test-Path $res) { "result: $((Get-Item $res).Length) bytes" } else { "NO RESULT FILE" }
