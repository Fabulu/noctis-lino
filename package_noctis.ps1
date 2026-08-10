# Build a self-contained redistributable Noctis IV play bundle.

[CmdletBinding()]
param(
    [string]$OutputDirectory = 'dist\Noctis-IV',
    [switch]$SkipBuild
)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$workDir = Join-Path $projectRoot 'work'
$gameSource = Join-Path $workDir 'vhgame.txt'
$gameExe = Join-Path $workDir 'vhgame.exe'

if (-not $SkipBuild) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass `
        -File (Join-Path $projectRoot 'lino_build.ps1') `
        -Src $gameSource `
        -Compiler (Join-Path $projectRoot 'main\lib\gen\compiler114m.exe') `
        -Cpu i386m `
        -StageExtension .lxe `
        -TimeoutSec 60
    if ($LASTEXITCODE -ne 0) {
        throw "Production build failed with exit code $LASTEXITCODE"
    }
}

if (-not [IO.Path]::IsPathRooted($OutputDirectory)) {
    $OutputDirectory = Join-Path $projectRoot $OutputDirectory
}
$outputPath = [IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $outputPath) {
    throw "Output already exists; choose a new empty path: $outputPath"
}

$assets = @(
    @{ Source = $gameExe;                                  Name = 'Noctis-IV.exe';     Size = 0 },
    @{ Source = (Join-Path $workDir 'globes.map');         Name = 'globes.map';        Size = 22586 },
    @{ Source = (Join-Path $workDir 'offsets.map');        Name = 'offsets.map';       Size = 7340 },
    @{ Source = (Join-Path $workDir 'vehicle.ncc');        Name = 'vehicle.ncc';       Size = 5802 },
    @{ Source = (Join-Path $workDir 'mammal.ncc');         Name = 'mammal.ncc';        Size = 2752 },
    @{ Source = (Join-Path $workDir 'birdy.ncc');          Name = 'birdy.ncc';         Size = 1002 },
    @{ Source = (Join-Path $workDir 'digimap2.bin');       Name = 'digimap2.bin';      Size = 9360 },
    @{ Source = (Join-Path $workDir 'STARMAP.BIN');        Name = 'STARMAP.BIN';       Size = -1 },
    @{ Source = (Join-Path $workDir 'noctis_music.pcm');  Name = 'noctis_music.pcm'; Size = -2 },
    @{ Source = (Join-Path $projectRoot 'Play Noctis IV.cmd'); Name = 'Play Noctis IV.cmd'; Size = 0 },
    @{ Source = (Join-Path $projectRoot 'PLAYER_README.txt'); Name = 'README.txt';     Size = 0 },
    @{ Source = (Join-Path $projectRoot 'LICENSE.htm');    Name = 'WPL.htm';           Size = 0 }
)

foreach ($asset in $assets) {
    if (-not (Test-Path -LiteralPath $asset.Source -PathType Leaf)) {
        throw "Required bundle input is missing: $($asset.Source)"
    }
    $length = (Get-Item -LiteralPath $asset.Source).Length
    if ($asset.Size -gt 0 -and $length -ne $asset.Size) {
        throw "Unexpected size for $($asset.Name): $length, expected $($asset.Size)"
    }
    if ($asset.Name -eq 'Noctis-IV.exe') {
        $bytes = [IO.File]::ReadAllBytes($asset.Source)
        if ($bytes.Length -lt 2 -or $bytes[0] -ne 0x4D -or $bytes[1] -ne 0x5A) {
            throw 'vhgame.exe is not a valid Windows MZ/PE image'
        }
    }
    if ($asset.Size -eq -1) {
        $bytes = [IO.File]::ReadAllBytes($asset.Source)
        if ($bytes.Length -lt 4 -or ($bytes.Length - 4) % 32 -ne 0 -or
            [BitConverter]::ToInt32($bytes, 0) -ne $bytes.Length -or
            $bytes.Length -gt 1280004) {
            throw 'STARMAP.BIN does not satisfy the 4 + 32n record contract'
        }
    }
    if ($asset.Size -eq -2 -and
        ($length -le 0 -or $length -gt 26400000 -or $length % 4 -ne 0)) {
        throw 'noctis_music.pcm must be non-empty interleaved stereo S16LE data'
    }
}

$parent = Split-Path -Parent $outputPath
if (-not (Test-Path -LiteralPath $parent)) {
    New-Item -ItemType Directory -Path $parent | Out-Null
}
$stage = Join-Path $parent ('.noctis-package-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null

try {
    foreach ($asset in $assets) {
        Copy-Item -LiteralPath $asset.Source -Destination (Join-Path $stage $asset.Name)
    }

    $manifestLines = foreach ($file in Get-ChildItem -LiteralPath $stage -File | Sort-Object Name) {
        $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        '{0} *{1}' -f $hash, $file.Name
    }
    $utf8NoBom = New-Object Text.UTF8Encoding($false)
    [IO.File]::WriteAllLines((Join-Path $stage 'MANIFEST.sha256'), $manifestLines, $utf8NoBom)

    Move-Item -LiteralPath $stage -Destination $outputPath
} finally {
    if (Test-Path -LiteralPath $stage) {
        $resolvedStage = (Resolve-Path -LiteralPath $stage).Path
        $resolvedParent = (Resolve-Path -LiteralPath $parent).Path
        if (-not $resolvedStage.StartsWith($resolvedParent + [IO.Path]::DirectorySeparatorChar) -or
            -not ([IO.Path]::GetFileName($resolvedStage)).StartsWith('.noctis-package-')) {
            throw "Refusing unsafe staging cleanup: $resolvedStage"
        }
        Remove-Item -LiteralPath $resolvedStage -Recurse -Force
    }
}

$files = Get-ChildItem -LiteralPath $outputPath -File
$total = ($files | Measure-Object Length -Sum).Sum
Write-Output ("PACKAGED {0}  {1} files  {2} bytes" -f $outputPath, $files.Count, $total)
