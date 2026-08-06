# pgall.ps1 - build and run the Wave 6a reference build and every sabotage.
#
# GUI-subsystem binaries: build ONLY via lino_build.ps1 and run ONLY with
# the poll-and-kill pattern.  Each run writes work\pg-out.bin, which is
# then renamed to work\pg-<tag>.bin before the next run starts.
param([string]$Only = "")

$ErrorActionPreference = 'Continue'
$W = 'C:\programmieren\linoleum\work'
$BUILD = 'C:\programmieren\linoleum\lino_build.ps1'
$RUN = 'C:\programmieren\linoleum\tests\linorun.ps1'

$srcs = @()
if ($Only -eq "") {
    $srcs += 'pgmain'
    Get-ChildItem $W -Filter 'pgbrk*main.txt' | Sort-Object Name | ForEach-Object {
        $srcs += [IO.Path]::GetFileNameWithoutExtension($_.Name)
    }
} else { $srcs += $Only }

foreach ($s in $srcs) {
    $src = Join-Path $W "$s.txt"
    $out = & powershell -ExecutionPolicy Bypass -File $BUILD -Src $src
    if ($LASTEXITCODE -ne 0) { Write-Output "BUILD-FAIL $s : $out"; continue }
    $exe = Join-Path $W "$s.exe"
    $bin = Join-Path $W 'pg-out.bin'
    if (Test-Path $bin) { Remove-Item -LiteralPath $bin -Force }
    $r = & powershell -ExecutionPolicy Bypass -File $RUN -Exe $exe -Out $bin -TimeoutSec 300
    if ($LASTEXITCODE -ne 0) { Write-Output "RUN-FAIL $s : $r"; continue }
    $tag = Join-Path $W "pg-$s.bin"
    Move-Item -LiteralPath $bin -Destination $tag -Force
    $h = (Get-FileHash $tag -Algorithm SHA256).Hash.ToLower()
    Write-Output ("OK {0} {1} bytes sha256 {2}" -f $s, (Get-Item $tag).Length, $h)
}
