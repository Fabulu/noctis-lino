# Launch the playable Noctis IV port from its asset/save directory.

param(
    [switch]$Build
)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$workDir = Join-Path $projectRoot 'work'
$gameSource = Join-Path $workDir 'vhgame.txt'
$gameExe = Join-Path $workDir 'vhgame.exe'
$buildScript = Join-Path $projectRoot 'lino_build.ps1'
$compiler = Join-Path $projectRoot 'main\lib\gen\compiler114m.exe'

if ($Build -or -not (Test-Path -LiteralPath $gameExe)) {
    Write-Host 'Building Noctis IV...'
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $buildScript `
        -Src $gameSource `
        -Compiler $compiler `
        -Cpu i386m `
        -StageExtension .lxe `
        -TimeoutSec 60
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

if (-not (Test-Path -LiteralPath $gameExe)) {
    Write-Error "Game executable was not created: $gameExe"
    exit 2
}

Write-Host 'Starting Noctis IV...'
$game = Start-Process -FilePath $gameExe -WorkingDirectory $workDir -PassThru -Wait
exit $game.ExitCode
