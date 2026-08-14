# Capture reproducible screenshots from the shipping Noctis IV executable.

[CmdletBinding()]
param(
    [string]$OutputDirectory = 'screenshots',
    [string]$GameExecutable,
    [ValidateSet('all', 'stardrifter', 'planetclose',
        'orbithot', 'orbitlunar', 'orbitdense', 'orbithabitable', 'orbitrocky',
        'orbitthin', 'orbitlarge', 'orbitfrozen', 'orbitmilky',
        'orbitsubstellar', 'orbitmultiple',
        'lunar', 'dense', 'habitable', 'tree', 'hopper', 'rocky', 'thin',
        'frozen', 'quartz', 'ruins', 'cube')]
    [string]$Scene = 'all',
    [int]$WarmupSeconds = 7,
    [int]$Longitude,
    [int]$Latitude,
    [int]$BodyIndex,
    [int]$ViewAngle,
    [int]$OrbitalViewAngle,
    [int]$ViewPitch,
    [int]$PlayerX,
    [int]$PlayerY,
    [int]$PlayerZ,
    [int]$CapsuleX = 131072,
    [int]$CapsuleZ = 131072,
    [ValidateSet(-1, 0, 1)]
    [int]$LensMode = 0,
    [ValidateSet(15)]
    [int]$CheckpointVersion = 15,
    [switch]$Fast,
    [switch]$ReportPerformance,
    [switch]$KeepStages,
    [switch]$Interactive
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
    # The opening system's type-8 primary after a completed fine approach,
    # held 3.88 planetary radii away on the calibrated forward window axis.
    @{ Name='planetclose'; FileName='planet-close-space.png'; Mode=0;
       X=3979984; Y=-43407; Z=-43984; Body=0; Type=8; Lon=0; Lat=60;
       Beta=23; Pitch=0; Warmup=1; PlayerX=2813; PlayerY=0; PlayerZ=-1397;
       LocalX=0.046885; LocalY=0.0; LocalZ=-0.110461 },
    # Target-relative fine-approach frames for every orbital body class. Each
    # offset is scaled from the type-8 checkpoint by the target's
    # generated p_ray, keeping the camera at the same apparent body radius.
    @{ Name='orbithot'; FileName='planet-space-hot.png'; Mode=0;
       X=4162480; Y=-6132645; Z=587893; Body=1; Type=0; Lon=0; Lat=60;
       Beta=23; Pitch=0; Warmup=1; PlayerX=2813; PlayerY=0; PlayerZ=-1397;
       LocalX=0.025697; LocalY=0.0; LocalZ=-0.060539 },
    @{ Name='orbitlunar'; FileName='planet-space-lunar.png'; Mode=0;
       X=174288; Y=-44389; Z=-688771; Body=0; Type=1; Lon=0; Lat=60;
       Beta=23; Pitch=0; Warmup=1; PlayerX=2813; PlayerY=0; PlayerZ=-1397;
       LocalX=0.010794; LocalY=0.0; LocalZ=-0.025432 },
    @{ Name='orbitdense'; FileName='planet-space-dense.png'; Mode=0;
       X=4304272; Y=-4664874; Z=-1062549; Body=0; Type=2; Lon=0; Lat=60;
       Beta=23; Pitch=0; Warmup=1; PlayerX=2813; PlayerY=0; PlayerZ=-1397;
       LocalX=0.034346; LocalY=0.0; LocalZ=-0.080919 },
    @{ Name='orbithabitable'; FileName='planet-space-habitable.png'; Mode=0;
       X=1463568; Y=-4728350; Z=-437812; Body=3; Type=3; Lon=0; Lat=60;
       Beta=23; Pitch=0; Warmup=1; PlayerX=2813; PlayerY=0; PlayerZ=-1397;
       LocalX=0.032783; LocalY=0.0; LocalZ=-0.077237 },
    @{ Name='orbitrocky'; FileName='planet-space-rocky.png'; Mode=0;
       X=1463568; Y=-4728350; Z=-437812; Body=9; Type=4; Lon=0; Lat=60;
       Beta=23; Pitch=0; Warmup=1; PlayerX=2813; PlayerY=0; PlayerZ=-1397;
       LocalX=0.027804; LocalY=0.0; LocalZ=-0.065506 },
    @{ Name='orbitthin'; FileName='planet-space-thin.png'; Mode=0;
       X=-1996240944; Y=72703; Z=944799; Body=3; Type=5; Lon=0; Lat=60;
       Beta=23; Pitch=0; Warmup=1; PlayerX=2813; PlayerY=0; PlayerZ=-1397;
       LocalX=0.030966; LocalY=0.0; LocalZ=-0.072956 },
    @{ Name='orbitlarge'; FileName='planet-space-large.png'; Mode=0;
       X=770352; Y=-131847; Z=665208; Body=0; Type=6; Lon=0; Lat=60;
       Beta=23; Pitch=0; Warmup=1; PlayerX=2813; PlayerY=0; PlayerZ=-1397;
       LocalX=0.261698; LocalY=0.0; LocalZ=-0.616521 },
    @{ Name='orbitfrozen'; FileName='planet-space-frozen.png'; Mode=0;
       X=2952848; Y=-6448045; Z=-840503; Body=9; Type=7; Lon=0; Lat=60;
       Beta=23; Pitch=0; Warmup=1; PlayerX=2813; PlayerY=0; PlayerZ=-1397;
       LocalX=0.039580; LocalY=0.0; LocalZ=-0.093250 },
    @{ Name='orbitmilky'; FileName='planet-space-milky.png'; Mode=0;
       X=3904272; Y=-4365172; Z=-679394; Body=1; Type=8; Lon=0; Lat=60;
       Beta=23; Pitch=0; Warmup=1; PlayerX=2813; PlayerY=0; PlayerZ=-1397;
       LocalX=0.055611; LocalY=0.0; LocalZ=-0.131011 },
    @{ Name='orbitsubstellar'; FileName='planet-space-substellar.png'; Mode=0;
       X=1463568; Y=-4728350; Z=-437812; Body=1; Type=9; Lon=0; Lat=60;
       Beta=23; Pitch=0; Warmup=1; PlayerX=2813; PlayerY=0; PlayerZ=-1397;
       LocalX=0.333919; LocalY=0.0; LocalZ=-0.786714 },
    # ROTOR IGNE is a generated class-8 multiple system. Body 0 is a primary
    # planet and body 3 is its companion star, so this view exercises the
    # real two-star corona/flare ordering instead of a synthetic overlay.
    @{ Name='orbitmultiple'; FileName='planet-space-multiple-system.png'; Mode=0;
       X=3866416; Y=-4813508; Z=-735695; Body=0; Type=5; Lon=0; Lat=60;
       Beta=300; Pitch=0; Warmup=1; PlayerX=2813; PlayerY=0; PlayerZ=-1397;
       LocalX=-0.05479262724126303; LocalY=0.0; LocalZ=-0.03163453808735004 },
    # IDEAL's only body is an authentic type-1 primary. This avoids spending
    # screenshot startup time generating JROT's pathological 80-body system.
    @{ Name='lunar';     X=174288; Y=-44389; Z=-688771; Body=0; Type=1; Lon=0; Lat=60;
       Beta=90; Pitch=-12; PlayerY=-19032 },
    @{ Name='dense';     X=1463568; Y=-4728350; Z=-437812; Body=0; Type=2; Lon=0; Lat=60; Beta=180; Pitch=-12 },
    # Naturally generated plains mammal, birds, vegetation and the local sun.
    @{ Name='habitable'; FileName='planet-habitable-sun.png';
       X=1463568; Y=-4728350; Z=-437812; Body=3; Type=3; Lon=0; Lat=60;
       Beta=65; Pitch=-10; Warmup=7; PlayerX=1598248; PlayerZ=2251369 },
    # LANE IV's naturally generated GIANT_TREE at (1086769,2139184), viewed
    # from 45,000 units south. This coordinate and its source parameters were
    # verified directly against the NIV+ tree renderer.
    @{ Name='tree'; FileName='planet-habitable-tree.png';
       X=1463568; Y=-4728350; Z=-437812; Body=3; Type=3; Lon=0; Lat=60;
       Beta=180; Pitch=0; Warmup=2; PlayerX=1086769; PlayerZ=2184184 },
    # LANE IV's naturally generated index-15 hopper, viewed from five
    # thousand surface units away. It remains in its source fauna record;
    # the checkpoint does not inject or relocate showcase scenery.
    @{ Name='hopper'; FileName='planet-habitable-hopper.png';
       X=1463568; Y=-4728350; Z=-437812; Body=3; Type=3; Lon=0; Lat=60;
       Beta=90; Pitch=0; Warmup=1; PlayerX=1747153; PlayerZ=872226 },
    # Do not stage these at the exact 100,100 grid corner on a cardinal
    # heading. At walking height the four nearest source tiles then meet on
    # the centre column and make an ordinary terrain edge look like a pillar.
    @{ Name='rocky';     X=1463568; Y=-4728350; Z=-437812; Body=9; Type=4; Lon=0; Lat=60;
       Beta=173; Pitch=-12; PlayerX=1645000; PlayerZ=1641000 },
    @{ Name='thin';      X=1463568; Y=-4728350; Z=-437812; Body=2; Type=5; Lon=0; Lat=60;
       Beta=167; Pitch=-12; PlayerX=1645000; PlayerZ=1641000 },
    @{ Name='frozen';    X=2952848; Y=-6448045; Z=-840503; Body=9; Type=7; Lon=0; Lat=60;
       Beta=193; Pitch=-12; PlayerX=1645000; PlayerZ=1641000 },
    @{ Name='quartz';    X=1463568; Y=-4728350; Z=-437812; Body=7; Type=8; Lon=0; Lat=60; Beta=180; Pitch=-12 },
    # Ylastravenya III's marked ruin edge, photographed outside the Cube.
    @{ Name='ruins';     FileName='planet-triangular-ruins.png';
       X=-56784; Y=-15693; Z=-129542; Body=3; Type=3; Lon=18; Lat=60;
       Beta=45; Pitch=10; Warmup=5; PlayerX=1327104; PlayerZ=1884160 },
    # Ylastravenya III from a high northeastern ridge. The complete 25x25
    # Cube and both marked wall bands remain inside the faithful 64-tile pass.
    @{ Name='cube';      FileName='planet-suricrasian-cube.png';
       X=-56784; Y=-15693; Z=-129542; Body=3; Type=3; Lon=18; Lat=60;
       Beta=61; Pitch=-10; Warmup=1; PlayerX=2785280; PlayerY=-350000; PlayerZ=1474560 }
)
if ($Scene -ne 'all') {
    $scenes = @($scenes | Where-Object Name -eq $Scene)
}
try {
foreach ($spec in $scenes) {
    if ($PSBoundParameters.ContainsKey('Longitude')) { $spec.Lon = $Longitude }
    if ($PSBoundParameters.ContainsKey('Latitude')) { $spec.Lat = $Latitude }
    if ($PSBoundParameters.ContainsKey('BodyIndex')) { $spec.Body = $BodyIndex }
    if ($PSBoundParameters.ContainsKey('ViewAngle')) { $spec.Beta = $ViewAngle }
    if ($PSBoundParameters.ContainsKey('OrbitalViewAngle') -and $spec.ContainsKey('LocalZ')) {
        $distance = [Math]::Sqrt(
            [double]$spec.LocalX * $spec.LocalX +
            [double]$spec.LocalY * $spec.LocalY +
            [double]$spec.LocalZ * $spec.LocalZ
        )
        $angle = $OrbitalViewAngle * [Math]::PI / 180.0
        $spec.LocalX = [Math]::Sin($angle) * $distance
        $spec.LocalY = 0.0
        $spec.LocalZ = -[Math]::Cos($angle) * $distance
        $spec.Beta = (($OrbitalViewAngle % 360) + 360) % 360
    }
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
    public delegate bool EnumWindowDelegate(IntPtr hwnd, IntPtr lParam);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hwnd, out RECT rect);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hwnd, IntPtr hdc, uint flags);
    [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr hwnd, uint msg, IntPtr wParam, IntPtr lParam);
    [DllImport("user32.dll")] public static extern bool ShowWindowAsync(IntPtr hwnd, int command);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hwnd);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint processId);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowDelegate callback, IntPtr lParam);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hwnd, int command);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }

    public static void HideProcessPopups(IntPtr host) {
        uint processId;
        GetWindowThreadProcessId(host, out processId);
        EnumWindows(delegate(IntPtr hwnd, IntPtr lParam) {
            uint candidateProcessId;
            GetWindowThreadProcessId(hwnd, out candidateProcessId);
            if (candidateProcessId != processId) return true;
            if (hwnd != host) ShowWindow(hwnd, 0);
            return true;
        }, IntPtr.Zero);
    }
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
    $u[27] = if ($Fast) { 1 } else { 0 }
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
    # Graphics word: lens mode + 1 in bits 0..1, source HUD enabled in bit 2.
    $u[47] = ($LensMode + 1) + 4
    $u[48] = 0
    $u[49] = -1
    if ($Spec.ContainsKey('LocalZ')) {
        $localX = [double]$Spec.LocalX
        $localY = [double]$Spec.LocalY
        $localZ = [double]$Spec.LocalZ
        $localDistance = [Math]::Sqrt(
            $localX * $localX + $localY * $localY + $localZ * $localZ
        )
        $u[39] = 4 # no tracking drift; radiation limiter remains enabled
        $u[48] = 1
        $u[49] = $Spec.Body
        [Buffer]::BlockCopy([BitConverter]::GetBytes($localX), 0, $u, 200, 8)
        [Buffer]::BlockCopy([BitConverter]::GetBytes($localY), 0, $u, 208, 8)
        [Buffer]::BlockCopy([BitConverter]::GetBytes($localZ), 0, $u, 216, 8)
        [Buffer]::BlockCopy([BitConverter]::GetBytes($localDistance), 0, $u, 224, 8)
        [Buffer]::BlockCopy([BitConverter]::GetBytes($localDistance), 0, $u, 232, 8)
        $u[60] = 0
        $u[61] = 1
        $u[62] = 0
        $u[63] = 0
    }
    $u[64] = 4
    $u[65] = 0
    # Synthetic scenes intentionally use the complete version-15 subset.
    # Version 16 adds live transient lighting/reset state that these fixtures
    # do not author and must not invent.
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
        $windowStyle = if ($Interactive) { 'Normal' } else { 'Hidden' }
        $proc = Start-Process -FilePath (Join-Path $stage 'Noctis-IV.exe') -WorkingDirectory $stage -WindowStyle $windowStyle -PassThru
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
        if ($Interactive) {
            [NoctisCaptureWin32]::ShowWindowAsync($proc.MainWindowHandle, 9) | Out-Null
            [NoctisCaptureWin32]::SetForegroundWindow($proc.MainWindowHandle) | Out-Null
            $interactivePid = $proc.Id
            $proc = $null
            Write-Output ("LAUNCHED {0} type {1}, PID {2}, stage {3}" -f $spec.Name, $spec.Type, $interactivePid, $stage)
            continue
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
        # The hidden iGUI host can inherit the desktop cursor over its fold
        # button. Suppress its owned popup windows so the framebuffer capture
        # stays clean without moving the user's cursor or gameplay input.
        [NoctisCaptureWin32]::HideProcessPopups($proc.MainWindowHandle)
        Save-WindowPng -Handle $proc.MainWindowHandle -Path $destination
        Write-Output ("CAPTURED {0} type {1} -> {2}" -f $spec.Name, $spec.Type, $destination)
        if ($ReportPerformance) {
            $profilePath = Join-Path $stage 'game-vh-out.bin'
            if (Test-Path -LiteralPath $profilePath) {
                $bytes = [IO.File]::ReadAllBytes($profilePath)
                if ($bytes.Length -eq 156) {
                    $profile = New-Object 'System.Int32[]' 39
                    [Buffer]::BlockCopy($bytes, 0, $profile, 0, $bytes.Length)
                    $countsPerMs = $profile[25]
                    if ($countsPerMs -gt 0) {
                        $renderMs = $profile[18] / [double]$countsPerMs / 60.0
                        $presentMs = $profile[19] / [double]$countsPerMs / 60.0
                        $spaceMs = $profile[20] / [double]$countsPerMs / 60.0
                        $cupolaMs = $profile[21] / [double]$countsPerMs / 60.0
                        $hullMs = $profile[22] / [double]$countsPerMs / 60.0
                        $detailMs = $profile[23] / [double]$countsPerMs / 60.0
                        Write-Output (
                            'PERF {0} fps={1} render={2:N2}ms present={3:N2}ms space={4:N2}ms cupola={5:N2}ms hull={6:N2}ms detail={7:N2}ms' -f
                            $spec.Name, $profile[24], $renderMs, $presentMs,
                            $spaceMs, $cupolaMs, $hullMs, $detailMs
                        )
                    }
                }
            }
            $sunPath = Join-Path $stage 'game-sun-out.bin'
            if (Test-Path -LiteralPath $sunPath) {
                $sunBytes = [IO.File]::ReadAllBytes($sunPath)
                if ($sunBytes.Length -eq 96) {
                    $sun = New-Object 'System.Int32[]' 24
                    [Buffer]::BlockCopy($sunBytes, 0, $sun, 0, $sunBytes.Length)
                    $sunFloats = New-Object 'System.Single[]' 24
                    [Buffer]::BlockCopy($sunBytes, 0, $sunFloats, 0, $sunBytes.Length)
                    $rain = $sunFloats[6]
                    $exposure = $sunFloats[7]
                    $distance = $sunFloats[8]
                    $ray = $sunFloats[9]
                    Write-Output (
                        'SUN {0} mode={1} landed={2} type={3} class={4} atmo={5} night={6} rain={7:R} exposure={8:R} distance={9:R}[{10:X8}] ray={11:R}[{12:X8}] center={13},{14} visible={15} added={16} secondary={17}' -f
                        $spec.Name, $sun[0], $sun[1], $sun[2], $sun[3],
                        $sun[4], $sun[5], $rain, $exposure, $distance, $sun[8],
                        $ray, $sun[9], $sun[17], $sun[18], $sun[16],
                        $sun[19], $sun[20]
                    )
                }
            }
        }
    } finally {
        if ($proc -and -not $proc.HasExited) {
            # Prefer the game's own Escape path so it saves state and flushes
            # performance telemetry. Hidden automated windows cannot receive
            # physical input, so post the same key transition to their queue.
            if ($proc.MainWindowHandle -ne [IntPtr]::Zero) {
                [NoctisCaptureWin32]::PostMessage($proc.MainWindowHandle, 0x0100, [IntPtr]0x1B, [IntPtr]1) | Out-Null
                Start-Sleep -Milliseconds 50
                [NoctisCaptureWin32]::PostMessage($proc.MainWindowHandle, 0x0101, [IntPtr]0x1B, [IntPtr]0xC0000001) | Out-Null
            }
            if (-not $proc.WaitForExit(3000)) {
                $proc.CloseMainWindow() | Out-Null
                if (-not $proc.WaitForExit(3000)) {
                    Stop-Process -Id $proc.Id -Force
                    $proc.WaitForExit()
                }
            }
        }
        if (-not $Interactive -and -not $KeepStages -and (Test-Path -LiteralPath $stage)) {
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
