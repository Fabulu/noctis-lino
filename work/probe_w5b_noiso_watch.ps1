# Watches probe_w5b_noiso.exe and samples Process.Responding while it runs.
# Responding is a WM_NULL SendMessageTimeout against the main window, so it is
# true only while that window is pumping messages. Marker files delimit the
# three phases.
$ErrorActionPreference = 'Stop'
$dir = 'C:\programmieren\linoleum\work'
$exe = Join-Path $dir 'probe_w5b_noiso.exe'
$marks = @('w5bm0.bin','w5bm1.bin','w5bm2.bin','w5bm3.bin') | ForEach-Object { Join-Path $dir $_ }
$res = Join-Path $dir 'probew5bnoiso.bin'

Remove-Item -LiteralPath $res -ErrorAction SilentlyContinue
foreach ($m in $marks) { Remove-Item -LiteralPath $m -ErrorAction SilentlyContinue }

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $exe
$psi.UseShellExecute = $false
$psi.WorkingDirectory = $dir
$proc = [System.Diagnostics.Process]::Start($psi)
$t0 = Get-Date

$log = @()
for ($i = 0; $i -lt 400; $i++) {
    Start-Sleep -Milliseconds 100
    if ($proc.HasExited) { break }
    $proc.Refresh()
    $r = $null
    try { if ($proc.MainWindowHandle -ne 0) { $r = $proc.Responding } } catch { $r = 'ERR' }
    $phase = 0
    for ($k = 0; $k -lt 4; $k++) { if (Test-Path $marks[$k]) { $phase = $k + 1 } }
    $log += [pscustomobject]@{
        ms    = [int]((Get-Date) - $t0).TotalMilliseconds
        phase = $phase
        resp  = $r
        hwnd  = ($proc.MainWindowHandle -ne 0)
    }
    if (Test-Path $res) { Start-Sleep -Milliseconds 300; break }
}
if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }

# phase 0 = before m0, 1 = phase A, 2 = phase B (no isocalls), 3 = phase C, 4 = done
$names = @{0='pre';1='A isocalls';2='B NO isocalls';3='C isocalls';4='done'}
foreach ($g in $log | Group-Object phase | Sort-Object Name) {
    $tot = $g.Count
    $yes = ($g.Group | Where-Object { $_.resp -eq $true }).Count
    $no  = ($g.Group | Where-Object { $_.resp -eq $false }).Count
    $nul = ($g.Group | Where-Object { $null -eq $_.resp }).Count
    $t1 = ($g.Group | Measure-Object ms -Minimum).Minimum
    $t2 = ($g.Group | Measure-Object ms -Maximum).Maximum
    "{0,-16} samples {1,3}  {2,5}..{3,5} ms   responding: true {4,3}  false {5,3}  nowindow {6,3}" -f `
        $names[[int]$g.Name], $tot, $t1, $t2, $yes, $no, $nul
}
""
"raw transitions:"
$prev = $null
foreach ($e in $log) {
    $key = "$($e.phase)/$($e.resp)"
    if ($key -ne $prev) { "  {0,6} ms  phase {1} ({2})  responding={3}" -f $e.ms, $e.phase, $names[$e.phase], $e.resp; $prev = $key }
}
""
if (Test-Path $res) { "result file written: $((Get-Item $res).Length) bytes" } else { "NO RESULT FILE" }
