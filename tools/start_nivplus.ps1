# Start the native NIV+ reference build with a responsive interactive DOSBox-X
# profile. Capture and byte-oracle rigs deliberately keep their own pinned
# configurations instead of using this launcher.

[CmdletBinding()]
param(
    [string]$NativeRoot,
    [string]$DosBoxExecutable,
    [switch]$Fullscreen,
    [switch]$Wait
)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (-not $NativeRoot) {
    $NativeRoot = Join-Path $projectRoot '.tmp-nivplus-planetdump'
}
if (-not $DosBoxExecutable) {
    $DosBoxExecutable = Join-Path $projectRoot '.tmp-dosbox-x\mingw-build\mingw-sdl2\dosbox-x.exe'
}

$NativeRoot = [IO.Path]::GetFullPath($NativeRoot)
$DosBoxExecutable = [IO.Path]::GetFullPath($DosBoxExecutable)
$nativeGame = Join-Path $NativeRoot 'modules\NOCTIS.EXE'
if (-not (Test-Path -LiteralPath $nativeGame -PathType Leaf)) {
    throw "Missing native NIV+ executable: $nativeGame"
}
if (-not (Test-Path -LiteralPath $DosBoxExecutable -PathType Leaf)) {
    throw "Missing DOSBox-X executable: $DosBoxExecutable"
}

$tempStem = Join-Path ([IO.Path]::GetTempPath()) ("noctis-nivplus-play-{0}" -f [Guid]::NewGuid().ToString('N'))
$configPath = "$tempStem.conf"
$mapperPath = "$tempStem.map"
$capturePath = "$tempStem-captures"
$fullscreenValue = if ($Fullscreen) { 'true' } else { 'false' }
$dosRoot = $NativeRoot.Replace('\', '/')
$dosMapper = $mapperPath.Replace('\', '/')
$dosCapture = $capturePath.Replace('\', '/')

$config = @"
[sdl]
fullscreen=$fullscreenValue
fullresolution=desktop
windowresolution=1280x800
output=openglnb
autolock=true
waitonerror=true
priority=higher,normal
mapperfile=$dosMapper

[dosbox]
memsize=32
synchronize time=true
captures=$dosCapture

[render]
frameskip=0
aspect=true
scaler=none
vsyncmode=off

[cpu]
core=dynamic_x86
cputype=pentium_iii
cycles=max

[dos]
keyboardlayout=auto

[autoexec]
mount c "$dosRoot"
c:
cd modules
noctis.exe
exit
"@

[IO.File]::WriteAllText($configPath, $config, [Text.UTF8Encoding]::new($false))
[IO.Directory]::CreateDirectory($capturePath) | Out-Null

try {
    $arguments = @('-conf', ('"{0}"' -f $configPath))
    $process = Start-Process -FilePath $DosBoxExecutable -ArgumentList $arguments -WorkingDirectory $NativeRoot -PassThru
    Write-Host "Started native NIV+ in DOSBox-X (PID $($process.Id))."
    Write-Host 'Ctrl+F10 releases the mouse. Ctrl+F11/F12 adjusts cycles if needed.'
    if ($Wait) {
        $process.WaitForExit()
    } else {
        try {
            [void]$process.WaitForInputIdle(5000)
        } catch {
            # DOSBox-X has still consumed its configuration before game launch.
        }
    }
} finally {
    Remove-Item -LiteralPath $configPath -Force -ErrorAction SilentlyContinue
    if ($Wait -or -not $process -or $process.HasExited) {
        Remove-Item -LiteralPath $mapperPath -Force -ErrorAction SilentlyContinue
        if (Test-Path -LiteralPath $capturePath) {
            Remove-Item -LiteralPath $capturePath -Force -ErrorAction SilentlyContinue
        }
    }
}
