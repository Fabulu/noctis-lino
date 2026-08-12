# Capture reproducible screenshots from the shipping Noctis IV executable.

[CmdletBinding()]
param(
    [string]$OutputDirectory = 'screenshots',
    [string]$GameExecutable,
    [ValidateSet('all', 'stardrifter', 'lunar', 'dense', 'habitable', 'rocky', 'thin', 'frozen', 'quartz', 'ruins', 'cube')]
    [string]$Scene = 'all',
    [int]$WarmupSeconds = 7,
    [int]$Longitude,
    [int]$Latitude,
    [int]$ViewAngle,
    [int]$ViewPitch,
    [int]$PlayerX,
    [int]$PlayerY,
    [int]$PlayerZ,
    [int]$CapsuleX = 131072,
    [int]$CapsuleZ = 131072,
    [ValidateSet(15)]
    [int]$CheckpointVersion = 15,
    [switch]$KeepStages
)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$workDir = Join-Path $projectRoot 'work'
$gameExe = if ($GameExecutable) {
    if ([IO.Path]::IsPathRooted($GameExecutable)) {
        [IO.Path]::GetFullPath($GameExecutable)
    } else {
        [IO.Path]::GetFullPath((Join-Path $projectRoot $GameExecutable))
    }
} else {
    Join-Path $workDir 'vhgame.exe'
}
$outputPath = if ([IO.Path]::IsPathRooted($OutputDirectory)) {
    [IO.Path]::GetFullPath($OutputDirectory)
} else {
    [IO.Path]::GetFullPath((Join-Path $projectRoot $OutputDirectory))
}

if (-not (Test-Path -LiteralPath $gameExe -PathType Leaf)) {
    throw "Missing production executable: $gameExe"
}
$sourceSnapshot = Join-Path $env:TEMP ("noctis-capture-source-{0}.exe" -f [Guid]::NewGuid().ToString('N'))
Copy-Item -LiteralPath $gameExe -Destination $sourceSnapshot
if (-not (Test-Path -LiteralPath $outputPath)) {
    New-Item -ItemType Directory -Path $outputPath | Out-Null
}

$scenes = @(
    # The opening Felysia checkpoint. New-Checkpoint places its sun on the
    # requested camera axis at a source-valid flare distance.
    @{ Name='stardrifter'; Mode=0; X=3979984; Y=-43407; Z=-43984; Body=0; Type=0;
       Lon=0; Lat=60; Beta=23; Pitch=0; Warmup=12;
       PlayerX=2813; PlayerY=0; PlayerZ=-1397; StarDistance=200.0 },
    # IDEAL's only body is an authentic type-1 primary. This avoids spending
    # screenshot startup time generating JROT's pathological 80-body system.
    @{ Name='lunar';     X=174288; Y=-44389; Z=-688771; Body=0; Type=1; Lon=0; Lat=60; Beta=180; Pitch=-12 },
    @{ Name='dense';     X=1463568; Y=-4728350; Z=-437812; Body=0; Type=2; Lon=0; Lat=60; Beta=180; Pitch=-12 },
    # Naturally generated plains mammal, birds, vegetation and the local sun.
    @{ Name='habitable'; FileName='planet-habitable-sun.png';
       X=1463568; Y=-4728350; Z=-437812; Body=3; Type=3; Lon=0; Lat=60;
       Beta=65; Pitch=-10; Warmup=7; PlayerX=1598248; PlayerZ=2251369 },
    @{ Name='rocky';     X=1463568; Y=-4728350; Z=-437812; Body=9; Type=4; Lon=0; Lat=60; Beta=180; Pitch=-12 },
    @{ Name='thin';      X=1463568; Y=-4728350; Z=-437812; Body=2; Type=5; Lon=0; Lat=60; Beta=180; Pitch=-12 },
    @{ Name='frozen';    X=2952848; Y=-6448045; Z=-840503; Body=9; Type=7; Lon=0; Lat=60; Beta=180; Pitch=-12 },
    @{ Name='quartz';    X=1463568; Y=-4728350; Z=-437812; Body=7; Type=8; Lon=0; Lat=60; Beta=180; Pitch=-12 },
    # Ylastravenya III's marked ruin edge, photographed outside the Cube.
    @{ Name='ruins';     FileName='planet-triangular-ruins.png';
       X=-56784; Y=-15693; Z=-129542; Body=3; Type=3; Lon=18; Lat=60;
       Beta=45; Pitch=10; Warmup=5; PlayerX=1327104; PlayerZ=1884160 },
    # Ylastravenya III at the original photographed site. The player starts
    # west of the map-space Cube and faces its centre.
    @{ Name='cube';      FileName='planet-suricrasian-cube.png';
       X=-56784; Y=-15693; Z=-129542; Body=3; Type=3; Lon=18; Lat=60;
       Beta=90; Pitch=35; Warmup=5; PlayerX=1318912; PlayerY=-30000; PlayerZ=1318912 }
)
if ($Scene -ne 'all') {
    $scenes = @($scenes | Where-Object Name -eq $Scene)
}
try {
foreach ($spec in $scenes) {
    if ($PSBoundParameters.ContainsKey('Longitude')) { $spec.Lon = $Longitude }
    if ($PSBoundParameters.ContainsKey('Latitude')) { $spec.Lat = $Latitude }
    if ($PSBoundParameters.ContainsKey('ViewAngle')) { $spec.Beta = $ViewAngle }
    if ($PSBoundParameters.ContainsKey('ViewPitch')) { $spec.Pitch = $ViewPitch }
    if ($PSBoundParameters.ContainsKey('PlayerX')) { $spec.PlayerX = $PlayerX }
    if ($PSBoundParameters.ContainsKey('PlayerY')) { $spec.PlayerY = $PlayerY }
    if ($PSBoundParameters.ContainsKey('PlayerZ')) { $spec.PlayerZ = $PlayerZ }
}

$assetNames = @(
    'globes.map', 'offsets.map', 'vehicle.ncc', 'mammal.ncc', 'birdy.ncc',
    'digimap2.bin', 'STARMAP.BIN', 'GUIDE.BIN', 'noctis_music.pcm'
)

Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class NoctisCaptureWin32 {
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hwnd, out RECT rect);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hwnd, IntPtr hdc, uint flags);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
}
'@

function New-Checkpoint {
    param([hashtable]$Spec, [string]$Path)
    $playerX = if ($Spec.ContainsKey('PlayerX')) { $Spec.PlayerX } else { 1638400 }
    $playerZ = if ($Spec.ContainsKey('PlayerZ')) { $Spec.PlayerZ } else { 1638400 }
    $u = New-Object 'System.Int32[]' 67
    $u[0] = [int]0x56485356
    $u[1] = $CheckpointVersion
    $u[2] = if ($Spec.ContainsKey('Mode')) { $Spec.Mode } else { 1 }
    $u[3] = $Spec.Body
    $u[4] = $playerX
    $u[5] = if ($Spec.ContainsKey('PlayerY')) { $Spec.PlayerY } else { -600 }
    $u[6] = $playerZ
    $u[7] = if ($Spec.ContainsKey('Pitch')) { $Spec.Pitch } else { -12 }
    $u[8] = $Spec.Beta
    $u[9] = 0
    $u[10] = 0
    $u[11] = -300
    if ($Spec.ContainsKey('StarDistance')) {
        # Invert VH space flare's beta/alpha rotations so the relative star
        # vector projects to the centre of the 320x200 source viewport.
        $radians = [Math]::PI / 180.0
        $distance = [double]$Spec.StarDistance
        $pitch = if ($Spec.ContainsKey('Pitch')) { $Spec.Pitch } else { -12 }
        $cosAlpha = [Math]::Cos($pitch * $radians)
        $relativeX = -[Math]::Sin($Spec.Beta * $radians) * $cosAlpha * $distance
        $relativeY = [Math]::Sin($pitch * $radians) * $distance
        $relativeZ = [Math]::Cos($Spec.Beta * $radians) * $cosAlpha * $distance
        $galacticX = [double]$Spec.X - $relativeX
        $galacticY = [double]$Spec.Y - $relativeY
        $galacticZ = [double]$Spec.Z - $relativeZ
        [Buffer]::BlockCopy([BitConverter]::GetBytes($galacticX), 0, $u, 48, 8)
        [Buffer]::BlockCopy([BitConverter]::GetBytes($galacticY), 0, $u, 56, 8)
        [Buffer]::BlockCopy([BitConverter]::GetBytes($galacticZ), 0, $u, 64, 8)
    }
    $u[18] = 30000
    $u[19] = 1
    $u[22] = 1
    $u[23] = 300
    $u[24] = $Spec.X
    $u[25] = $Spec.Y
    $u[26] = $Spec.Z
    $u[27] = 0
    $u[28] = 0
    $u[29] = 0
    $u[31] = 3
    $u[35] = 1344638527
    $u[36] = 642
    $u[37] = 426
    $u[38] = 1
    $u[39] = 12
    $u[40] = $Spec.Lon
    $u[41] = $Spec.Lat
    $u[42] = $CapsuleX
    $u[43] = 0
    $u[44] = $CapsuleZ
    $u[47] = 5
    $u[48] = 0
    $u[49] = -1
    $u[64] = 4
    $u[65] = 0
    $byteCount = 264
    $bytes = New-Object byte[] $byteCount
    [Buffer]::BlockCopy($u, 0, $bytes, 0, $bytes.Length)
    [IO.File]::WriteAllBytes($Path, $bytes)
}

function Save-WindowPng {
    param([IntPtr]$Handle, [string]$Path)
    $rect = New-Object NoctisCaptureWin32+RECT
    if (-not [NoctisCaptureWin32]::GetWindowRect($Handle, [ref]$rect)) {
        throw 'GetWindowRect failed'
    }
    $width = $rect.Right - $rect.Left
    $height = $rect.Bottom - $rect.Top
    $bitmap = New-Object Drawing.Bitmap $width, $height, ([Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $graphics = [Drawing.Graphics]::FromImage($bitmap)
    try {
        $hdc = $graphics.GetHdc()
        try {
            if (-not [NoctisCaptureWin32]::PrintWindow($Handle, $hdc, 2)) {
                throw 'PrintWindow failed'
            }
        } finally {
            $graphics.ReleaseHdc($hdc)
        }
        $bitmap.Save($Path, [Drawing.Imaging.ImageFormat]::Png)
    } finally {
        $graphics.Dispose()
        $bitmap.Dispose()
    }
}

function Test-NoctisWindowReady {
    param([IntPtr]$Handle)
    $rect = New-Object NoctisCaptureWin32+RECT
    if (-not [NoctisCaptureWin32]::GetWindowRect($Handle, [ref]$rect)) {
        return $false
    }
    $width = $rect.Right - $rect.Left
    $height = $rect.Bottom - $rect.Top
    if ($width -lt 100 -or $height -lt 100) { return $false }
    $bitmap = New-Object Drawing.Bitmap $width, $height, ([Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $graphics = [Drawing.Graphics]::FromImage($bitmap)
    try {
        $hdc = $graphics.GetHdc()
        try {
            if (-not [NoctisCaptureWin32]::PrintWindow($Handle, $hdc, 2)) {
                return $false
            }
        } finally {
            $graphics.ReleaseHdc($hdc)
        }
        # iGUI paints its own title bar; MainWindowTitle remains the programme
        # name (`vhgame`) and cannot distinguish the temporary black `NO NAME`
        # host from a completed Noctis frame. Sample below the chrome instead.
        $nonBlack = 0
        for ($y = 28; $y -lt $height; $y += 8) {
            for ($x = 8; $x -lt ($width - 8); $x += 8) {
                $pixel = $bitmap.GetPixel($x, $y)
                if (($pixel.R -bor $pixel.G -bor $pixel.B) -ne 0) {
                    $nonBlack++
                    if ($nonBlack -ge 20) { return $true }
                }
            }
        }
        return $false
    } finally {
        $graphics.Dispose()
        $bitmap.Dispose()
    }
}

foreach ($spec in $scenes) {
    $proc = $null
    $stage = Join-Path $env:TEMP ("noctis-capture-{0}-{1}" -f $spec.Name, [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $stage | Out-Null
    try {
        Copy-Item -LiteralPath $sourceSnapshot -Destination (Join-Path $stage 'Noctis-IV.exe')
        foreach ($asset in $assetNames) {
            Copy-Item -LiteralPath (Join-Path $workDir $asset) -Destination (Join-Path $stage $asset)
        }
        New-Checkpoint -Spec $spec -Path (Join-Path $stage 'CURRENT.LIN')
        Copy-Item -LiteralPath (Join-Path $stage 'CURRENT.LIN') -Destination (Join-Path $stage 'CURRENT.BAK')

        # Automated captures must not open an interactive window on the user's
        # desktop: input would both interrupt them and taint fixed-scene probes.
        $proc = Start-Process -FilePath (Join-Path $stage 'Noctis-IV.exe') -WorkingDirectory $stage -WindowStyle Hidden -PassThru
        $deadline = [DateTime]::UtcNow.AddSeconds(15)
        do {
            Start-Sleep -Milliseconds 100
            $proc.Refresh()
        } until ($proc.HasExited -or $proc.MainWindowHandle -ne [IntPtr]::Zero -or [DateTime]::UtcNow -ge $deadline)
        if ($proc.HasExited) { throw "Scene $($spec.Name) exited early with code $($proc.ExitCode)" }
        if ($proc.MainWindowHandle -eq [IntPtr]::Zero) { throw "Scene $($spec.Name) did not open a window" }
        # iGUI exposes its host before the game has finished terrain/model
        # initialization. Capturing that intermediate window produces the
        # misleading black `NO NAME` frame seen on slower cold launches.
        $readyDeadline = [DateTime]::UtcNow.AddSeconds(90)
        $ready = $false
        do {
            Start-Sleep -Milliseconds 250
            $proc.Refresh()
            if (-not $proc.HasExited) {
                $ready = Test-NoctisWindowReady -Handle $proc.MainWindowHandle
            }
        } until ($proc.HasExited -or $ready -or [DateTime]::UtcNow -ge $readyDeadline)
        if ($proc.HasExited) { throw "Scene $($spec.Name) exited during initialization with code $($proc.ExitCode)" }
        if (-not $ready) {
            throw "Scene $($spec.Name) did not finish initialization"
        }
        $sceneWarmup = if ($PSBoundParameters.ContainsKey('WarmupSeconds')) {
            $WarmupSeconds
        } elseif ($spec.ContainsKey('Warmup')) {
            $spec.Warmup
        } else {
            7
        }
        Start-Sleep -Seconds $sceneWarmup
        $fileName = if ($spec.ContainsKey('FileName')) {
            $spec.FileName
        } elseif ($spec.Name -eq 'stardrifter') {
            'stardrifter-sun.png'
        } else {
            "planet-$($spec.Name).png"
        }
        $destination = Join-Path $outputPath $fileName
        Save-WindowPng -Handle $proc.MainWindowHandle -Path $destination
        Write-Output ("CAPTURED {0} type {1} -> {2}" -f $spec.Name, $spec.Type, $destination)
    } finally {
        if ($proc -and -not $proc.HasExited) {
            $proc.CloseMainWindow() | Out-Null
            if (-not $proc.WaitForExit(3000)) {
                Stop-Process -Id $proc.Id -Force
                $proc.WaitForExit()
            }
        }
        if (-not $KeepStages -and (Test-Path -LiteralPath $stage)) {
            $resolvedStage = (Resolve-Path -LiteralPath $stage).Path
            $resolvedParent = (Resolve-Path -LiteralPath (Split-Path -Parent $stage)).Path
            if ((Split-Path -Parent $resolvedStage) -ne $resolvedParent -or
                -not (Split-Path -Leaf $resolvedStage).StartsWith("noctis-capture-$($spec.Name)-")) {
                throw "Refusing unsafe capture cleanup: $resolvedStage"
            }
            Remove-Item -LiteralPath $resolvedStage -Recurse -Force
        }
    }
}
} finally {
    if (Test-Path -LiteralPath $sourceSnapshot) {
        Remove-Item -LiteralPath $sourceSnapshot -Force
    }
}
