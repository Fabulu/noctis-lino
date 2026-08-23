# Capture reproducible screenshots from the shipping Noctis IV executable.

[CmdletBinding()]
param(
    [string]$OutputDirectory = 'screenshots',
    [string]$GameExecutable,
    [ValidateSet('all', 'stardrifter', 'planetclose',
        'orbithot', 'orbitlunar', 'orbitdense', 'orbithabitable', 'orbitrocky',
        'orbitthin', 'orbitlarge', 'orbitfrozen', 'orbitmilky',
        'orbitsubstellar', 'orbitmultiple',
        'lunar', 'lunarsun', 'dense', 'densesun', 'habitable', 'tree', 'hopper', 'rocky', 'rockysun',
        'thin', 'thinsun',
        'frozen', 'frozensun', 'frozenflare', 'quartz', 'ruins', 'cube')]
    [string]$Scene = 'all',
    [int]$WarmupSeconds = 7,
    [ValidateRange(1, 600)]
    [int]$DiagnosticTimeoutSeconds = 180,
    [int]$Longitude,
    [int]$Latitude,
    [int]$BodyIndex,
    [int]$ViewAngle,
    [int]$NavigationAngle,
    [int]$OrbitalViewAngle,
    [ValidateRange(0.01, 100.0)]
    [double]$OrbitalDistanceScale,
    [double]$OrbitalLocalX,
    [double]$OrbitalLocalY,
    [double]$OrbitalLocalZ,
    [ValidateRange(0, 7)]
    [int]$OrbitalSync,
    [int]$ViewPitch,
    [int]$PlayerX,
    [int]$PlayerY,
    [int]$PlayerZ,
    [int]$CapsuleX = 131072,
    [int]$CapsuleZ = 131072,
    [ValidateRange(272, 962)]
    [int]$WindowWidth = 642,
    [ValidateRange(120, 626)]
    [int]$WindowHeight = 426,
    [ValidateSet(-1, 0, 1)]
    [int]$LensMode = 0,
    [switch]$OpenHud,
    [ValidateSet(15)]
    [int]$CheckpointVersion = 15,
    [switch]$Fast,
    [switch]$ReportPerformance,
    [int]$ClockSeconds = 1344638527,
    [switch]$KeepStages,
    [switch]$UseGameSnapshot,
    [switch]$CaptureHostWindow,
    [switch]$CapsuleReturn,
    [switch]$OpenFcs,
    [switch]$DiagnosticOnly,
    [switch]$DefaultDesktop,
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

if ($DefaultDesktop -and -not $DiagnosticOnly) {
    throw 'DefaultDesktop requires DiagnosticOnly'
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
       LocalX=-0.046885; LocalY=0.0; LocalZ=0.110461 },
    # Target-relative fine-approach frames for every orbital body class. Each
    # offset is scaled from the type-8 checkpoint by the target's generated
    # p_ray, keeping the camera at the same apparent body radius. Preserve the
    # authored 23-degree cockpit axis and negate its target-local offset because
    # source from_vehicle() adds the exterior half-turn before projection.
    @{ Name='orbithot'; FileName='planet-space-hot.png'; Mode=0;
       X=4162480; Y=-6132645; Z=587893; Body=1; Type=0; Lon=0; Lat=60;
       Beta=23; Pitch=0; Warmup=1; PlayerX=2813; PlayerY=0; PlayerZ=-1397;
       LocalX=-0.025697; LocalY=0.0; LocalZ=0.060539 },
    @{ Name='orbitlunar'; FileName='planet-space-lunar.png'; Mode=0;
       X=174288; Y=-44389; Z=-688771; Body=0; Type=1; Lon=0; Lat=60;
       Beta=23; Pitch=0; Warmup=1; PlayerX=2813; PlayerY=0; PlayerZ=-1397;
       LocalX=-0.010794; LocalY=0.0; LocalZ=0.025432 },
    @{ Name='orbitdense'; FileName='planet-space-dense.png'; Mode=0;
       X=4304272; Y=-4664874; Z=-1062549; Body=0; Type=2; Lon=0; Lat=60;
       Beta=23; Pitch=0; Warmup=1; PlayerX=2813; PlayerY=0; PlayerZ=-1397;
       LocalX=-0.034346; LocalY=0.0; LocalZ=0.080919 },
    @{ Name='orbithabitable'; FileName='planet-space-habitable.png'; Mode=0;
       X=1463568; Y=-4728350; Z=-437812; Body=3; Type=3; Lon=0; Lat=60;
       Beta=23; Pitch=0; Warmup=1; PlayerX=2813; PlayerY=0; PlayerZ=-1397;
       LocalX=-0.032783; LocalY=0.0; LocalZ=0.077237 },
    @{ Name='orbitrocky'; FileName='planet-space-rocky.png'; Mode=0;
       X=1463568; Y=-4728350; Z=-437812; Body=9; Type=4; Lon=0; Lat=60;
       Beta=23; Pitch=0; Warmup=1; PlayerX=2813; PlayerY=0; PlayerZ=-1397;
       LocalX=-0.027804; LocalY=0.0; LocalZ=0.065506 },
    @{ Name='orbitthin'; FileName='planet-space-thin.png'; Mode=0;
       X=-1996240944; Y=72703; Z=944799; Body=3; Type=5; Lon=0; Lat=60;
       Beta=23; Pitch=0; Warmup=1; PlayerX=2813; PlayerY=0; PlayerZ=-1397;
       LocalX=-0.030966; LocalY=0.0; LocalZ=0.072956 },
    @{ Name='orbitlarge'; FileName='planet-space-large.png'; Mode=0;
       X=770352; Y=-131847; Z=665208; Body=0; Type=6; Lon=0; Lat=60;
       Beta=23; Pitch=0; Warmup=1; PlayerX=2813; PlayerY=0; PlayerZ=-1397;
       LocalX=-0.261698; LocalY=0.0; LocalZ=0.616521 },
    @{ Name='orbitfrozen'; FileName='planet-space-frozen.png'; Mode=0;
       X=2952848; Y=-6448045; Z=-840503; Body=9; Type=7; Lon=0; Lat=60;
       Beta=23; Pitch=0; Warmup=1; PlayerX=2813; PlayerY=0; PlayerZ=-1397;
       LocalX=-0.039580; LocalY=0.0; LocalZ=0.093250 },
    @{ Name='orbitmilky'; FileName='planet-space-milky.png'; Mode=0;
       X=3904272; Y=-4365172; Z=-679394; Body=1; Type=8; Lon=0; Lat=60;
       Beta=23; Pitch=0; Warmup=1; PlayerX=2813; PlayerY=0; PlayerZ=-1397;
       LocalX=-0.055611; LocalY=0.0; LocalZ=0.131011 },
    @{ Name='orbitsubstellar'; FileName='planet-space-substellar.png'; Mode=0;
       X=1463568; Y=-4728350; Z=-437812; Body=1; Type=9; Lon=0; Lat=60;
       Beta=23; Pitch=0; Warmup=1; PlayerX=2813; PlayerY=0; PlayerZ=-1397;
       LocalX=-0.333919; LocalY=0.0; LocalZ=0.786714 },
    # ROTOR IGNE is a generated class-8 multiple system. This native-matched
    # navigation-120 pose keeps body 3 behind the exterior camera and protects
    # the negative visibility contract. Override -NavigationAngle 300 for the
    # retained front-facing companion corona and radial-flare context.
    @{ Name='orbitmultiple'; FileName='planet-space-multiple-system.png'; Mode=0;
       X=3866416; Y=-4813508; Z=-735695; Body=0; Type=5; Lon=0; Lat=60;
       Beta=0; Nav=120; Pitch=-34; Warmup=1; PlayerX=0; PlayerY=0; PlayerZ=-500;
       OpenHud=$true; Sync=1;
       LocalX=-0.025440362261571668; LocalY=0.0; LocalZ=-0.014688000000000005 },
    # IDEAL's only body is an authentic type-1 primary. This avoids spending
    # screenshot startup time generating JROT's pathological 80-body system.
    @{ Name='lunar';     X=174288; Y=-44389; Z=-688771; Body=0; Type=1; Lon=0; Lat=60;
       Beta=90; Pitch=-12; PlayerY=-19032 },
    # IDEAL I at the pinned NIV+ clock and player position. The primary is
    # close enough that distance < 10*ray, so planetary_main draws its white
    # disc/corona but authentically suppresses the radial surface flare.
    @{ Name='lunarsun'; FileName='planet-lunar-sun.png';
       X=174288; Y=-44389; Z=-688771; Body=0; Type=1; Lon=0; Lat=60;
       Beta=90; Pitch=-44; PlayerX=1638400; PlayerY=-19032; PlayerZ=1638400 },
    @{ Name='dense';     X=1463568; Y=-4728350; Z=-437812; Body=0; Type=2; Lon=0; Lat=60; Beta=180; Pitch=-12 },
    # Same-clock stock NIV+ checkpoint.  The dense atmosphere keeps the source
    # disc and broad corona but suppresses radial rays below the 10*ray gate.
    @{ Name='densesun'; FileName='planet-dense-sun.png';
       X=1463568; Y=-4728350; Z=-437812; Body=0; Type=2; Lon=0; Lat=60;
       Beta=90; Pitch=-44; PlayerX=1638400; PlayerY=0; PlayerZ=1638400 },
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
    # Airless day-side oracle. The primary disc is visible but its live
    # 9133-unit distance exceeds the source's 1000*ray flare gate, so the
    # authentic result deliberately has no radial beams.
    @{ Name='rockysun'; FileName='planet-rocky-sun.png';
       X=1463568; Y=-4728350; Z=-437812; Body=9; Type=4; Lon=90; Lat=60;
       Beta=270; Pitch=-38; PlayerX=1645000; PlayerZ=1641000 },
    @{ Name='thin';      X=1463568; Y=-4728350; Z=-437812; Body=2; Type=5; Lon=0; Lat=60;
       Beta=167; Pitch=-12; PlayerX=1645000; PlayerZ=1641000 },
    # Native-matched clear type-5 lighting state. Longitude 45 and the lower
    # camera pitch keep the complete radial flare visibly centred in the sky,
    # instead of letting its authentic near-vertical spoke resemble the old
    # horizon-pillar defect as it crosses the terrain.
    @{ Name='thinsun'; FileName='planet-thin-sun.png';
       X=1463568; Y=-4728350; Z=-437812; Body=2; Type=5; Lon=45; Lat=60;
       Beta=90; Pitch=-40; PlayerX=1645000; PlayerZ=1641000 },
    @{ Name='frozen';    X=2952848; Y=-6448045; Z=-840503; Body=9; Type=7; Lon=0; Lat=60;
       Beta=193; Pitch=-12; PlayerX=1645000; PlayerZ=1641000 },
    # Class-1 primary over an airless frozen world. The disc is visible while
    # its live distance remains outside the original flare gate.
    @{ Name='frozensun'; FileName='planet-frozen-sun.png';
       X=2952848; Y=-6448045; Z=-840503; Body=9; Type=7; Lon=0; Lat=60;
       Beta=90; Pitch=-44; PlayerX=1645000; PlayerZ=1641000 },
    # RENIET VIII is a genuine type-7 primary around a class-0 star. Its
    # roughly 610-stellar-radius orbit lies inside the source flare gate,
    # complementing the deliberately beamless distant frozen-world fixture.
    # This is a valid post-walk state: the capsule remains at its generated
    # landing tile while the player has moved far enough to uncover the sun.
    # A sector-first Borland NIV+ capture produced the same centre sample and
    # the same positive radial flare at this pose.
    @{ Name='frozenflare'; FileName='planet-frozen-sunbeams.png';
       X=-1418337904; Y=1953670; Z=-1274313078; Body=7; Type=7; Lon=0; Lat=60;
       Beta=90; Pitch=-20; PlayerX=1645000; PlayerZ=1641000 },
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
$orbitalLocalOverrides = @('OrbitalLocalX', 'OrbitalLocalY', 'OrbitalLocalZ') |
    Where-Object { $PSBoundParameters.ContainsKey($_) }
if ($orbitalLocalOverrides.Count -ne 0 -and $orbitalLocalOverrides.Count -ne 3) {
    throw '-OrbitalLocalX, -OrbitalLocalY, and -OrbitalLocalZ must be supplied together'
}
try {
foreach ($spec in $scenes) {
    if ($PSBoundParameters.ContainsKey('Longitude')) { $spec.Lon = $Longitude }
    if ($PSBoundParameters.ContainsKey('Latitude')) { $spec.Lat = $Latitude }
    if ($PSBoundParameters.ContainsKey('BodyIndex')) { $spec.Body = $BodyIndex }
    if ($PSBoundParameters.ContainsKey('ViewAngle')) { $spec.Beta = $ViewAngle }
    if ($PSBoundParameters.ContainsKey('NavigationAngle')) { $spec.Nav = $NavigationAngle }
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
    if ($PSBoundParameters.ContainsKey('OrbitalDistanceScale') -and $spec.ContainsKey('LocalZ')) {
        $spec.LocalX = [double]$spec.LocalX * $OrbitalDistanceScale
        $spec.LocalY = [double]$spec.LocalY * $OrbitalDistanceScale
        $spec.LocalZ = [double]$spec.LocalZ * $OrbitalDistanceScale
    }
    if ($orbitalLocalOverrides.Count -eq 3) {
        if (-not $spec.ContainsKey('LocalZ')) {
            throw "Scene $($spec.Name) has no orbital local pose to override"
        }
        $spec.LocalX = $OrbitalLocalX
        $spec.LocalY = $OrbitalLocalY
        $spec.LocalZ = $OrbitalLocalZ
    }
    if ($PSBoundParameters.ContainsKey('OrbitalSync')) {
        if (-not $spec.ContainsKey('LocalZ')) {
            throw "Scene $($spec.Name) has no orbital sync state to override"
        }
        $spec.Sync = $OrbitalSync
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
$diagnosticSizes = [ordered]@{
    'game-vh-out.bin' = 156
    'game-sun-out.bin' = 128
    'game-local-out.bin' = 176
    'game-palette-out.bin' = 3072
    'game-page-out.bin' = 64000
    'game-s-background-out.bin' = 64800
    'game-p-surfacemap-out.bin' = 40000
    'game-p-background-out.bin' = 65552
    'game-render-state-out.bin' = 24
}

Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Runtime.InteropServices;
using System.Text;
public static class NoctisCaptureWin32 {
    public delegate bool EnumWindowDelegate(IntPtr hwnd, IntPtr lParam);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hwnd, out RECT rect);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hwnd, IntPtr hdc, uint flags);
    [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr hwnd, uint msg, IntPtr wParam, IntPtr lParam);
    [DllImport("user32.dll")] public static extern bool ShowWindowAsync(IntPtr hwnd, int command);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hwnd);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint processId);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowDelegate callback, IntPtr lParam);
    [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr parent, EnumWindowDelegate callback, IntPtr lParam);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hwnd, int command);
    [DllImport("user32.dll")] public static extern bool GetCursorPos(out POINT point);
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern int GetSystemMetrics(int index);
    [DllImport("user32.dll", CharSet = CharSet.Auto)] public static extern int GetClassName(IntPtr hwnd, StringBuilder name, int capacity);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
    [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
    private static POINT savedCursor;
    private static bool cursorSaved;

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
        EnumChildWindows(host, delegate(IntPtr hwnd, IntPtr lParam) {
            StringBuilder name = new StringBuilder(128);
            GetClassName(hwnd, name, name.Capacity);
            if (name.ToString().IndexOf("tooltips_class32", StringComparison.OrdinalIgnoreCase) >= 0)
                ShowWindow(hwnd, 0);
            return true;
        }, IntPtr.Zero);
    }

    public static void ClearHover(IntPtr host) {
        cursorSaved = GetCursorPos(out savedCursor);
        SetCursorPos(GetSystemMetrics(0) - 1, GetSystemMetrics(1) - 1);
        PostMessage(host, 0x02A3, IntPtr.Zero, IntPtr.Zero); // WM_MOUSELEAVE
    }

    public static void RestoreCursor() {
        if (cursorSaved) SetCursorPos(savedCursor.X, savedCursor.Y);
        cursorSaved = false;
    }
}
'@

function New-Checkpoint {
    param([hashtable]$Spec, [string]$Path)
    $playerX = if ($Spec.ContainsKey('PlayerX')) { $Spec.PlayerX } else { 1638400 }
    $playerZ = if ($Spec.ContainsKey('PlayerZ')) { $Spec.PlayerZ } else { 1638400 }
    # NIV+ clamps user_alfa to +/-44.9. The port stores whole-degree camera
    # angles, so +/-44 is its closest playable checkpoint boundary. Clamp
    # authored states here as well because Fast capture mode intentionally
    # skips simulation and would otherwise preserve an impossible pitch.
    $pitch = if ($Spec.ContainsKey('Pitch')) { [int]$Spec.Pitch } else { -12 }
    if ($pitch -gt 44) { $pitch = 44 }
    if ($pitch -lt -44) { $pitch = -44 }
    $u = New-Object 'System.Int32[]' 67
    $u[0] = [int]0x56485356
    $u[1] = $CheckpointVersion
    $u[2] = if ($Spec.ContainsKey('Mode')) { $Spec.Mode } else { 1 }
    $u[3] = $Spec.Body
    $u[4] = $playerX
    $u[5] = if ($Spec.ContainsKey('PlayerY')) { $Spec.PlayerY } else { -600 }
    $u[6] = $playerZ
    $u[7] = $pitch
    $u[8] = $Spec.Beta
    $u[9] = 0
    $u[10] = 0
    $u[11] = -300
    if ($Spec.ContainsKey('StarDistance')) {
        # Invert VH space flare's beta/alpha rotations so the relative star
        # vector projects to the centre of the 320x200 source viewport.
        $radians = [Math]::PI / 180.0
        $distance = [double]$Spec.StarDistance
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
    $u[36] = $WindowWidth
    $u[37] = $WindowHeight
    $u[38] = 1
    $u[39] = 12
    $u[40] = $Spec.Lon
    $u[41] = $Spec.Lat
    $u[42] = $CapsuleX
    $u[43] = 0
    $u[44] = $CapsuleZ
    # Graphics word: lens mode + 1 in bits 0..1, source HUD enabled in bit 2.
    $sceneOpenHud = $OpenHud -or ($Spec.ContainsKey('OpenHud') -and $Spec.OpenHud)
    $u[47] = ($LensMode + 1) + 4 + $(if ($sceneOpenHud) { 16 } else { 0 })
    $u[48] = 0
    $u[49] = -1
    if ($Spec.ContainsKey('LocalZ')) {
        $localX = [double]$Spec.LocalX
        $localY = [double]$Spec.LocalY
        $localZ = [double]$Spec.LocalZ
        $localDistance = [Math]::Sqrt(
            $localX * $localX + $localY * $localY + $localZ * $localZ
        )
        # Navigation word: sync in bits 3..5, with anti-radiation in bit 2.
        # Most authored orbital poses remain fixed. The ROTOR IGNE companion
        # fixture opts into source fixed-chase tracking at its exact equilibrium.
        $sceneSync = if ($Spec.ContainsKey('Sync')) { [int]$Spec.Sync } else { 0 }
        $u[39] = 4 + 8 * $sceneSync
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
    $u[65] = if ($Spec.ContainsKey('Nav')) { $Spec.Nav } else { 0 }
    # Synthetic scenes intentionally use the complete version-15 subset.
    # Versions 16 and 17 add live transient lighting/reset/drive state that
    # these fixtures do not author and must not invent. The loader reconstructs
    # the stable stopped-drive invariant from their completed-approach flag.
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

function Save-GameSnapshotPng {
    param([Diagnostics.Process]$Process, [string]$Stage, [string]$Path)
    $gallery = Join-Path $Stage 'GALLERY'
    if (Test-Path -LiteralPath $gallery) {
        Remove-Item -LiteralPath $gallery -Recurse -Force
    }
    [NoctisCaptureWin32]::PostMessage($Process.MainWindowHandle, 0x0100, [IntPtr]0x4D, [IntPtr]1) | Out-Null
    Start-Sleep -Milliseconds 50
    [NoctisCaptureWin32]::PostMessage($Process.MainWindowHandle, 0x0101, [IntPtr]0x4D, [IntPtr]0xC0000001) | Out-Null
    $deadline = [DateTime]::UtcNow.AddSeconds(4)
    $snapshot = $null
    do {
        Start-Sleep -Milliseconds 100
        $snapshot = Get-ChildItem -LiteralPath $gallery -Filter '*.BMP' -File -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending | Select-Object -First 1
    } until ($snapshot -or [DateTime]::UtcNow -ge $deadline)
    if (-not $snapshot) { return $false }
    $bitmap = [Drawing.Bitmap]::FromFile($snapshot.FullName)
    try {
        $bitmap.Save($Path, [Drawing.Imaging.ImageFormat]::Png)
    } finally {
        $bitmap.Dispose()
    }
    return $true
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

function Export-SceneDiagnostics {
    param(
        [hashtable]$Spec,
        [string]$Stage,
        [string]$OutputPath,
        [switch]$RequireComplete
    )
    foreach ($entry in $diagnosticSizes.GetEnumerator()) {
        $source = Join-Path $Stage $entry.Key
        if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
            if ($RequireComplete) {
                throw "Scene $($Spec.Name) did not emit $($entry.Key)"
            }
            continue
        }
        $length = (Get-Item -LiteralPath $source).Length
        if ($RequireComplete -and $length -ne $entry.Value) {
            throw "Scene $($Spec.Name) emitted $($entry.Key) with length $length, expected $($entry.Value)"
        }
        $diagnosticName = '{0}-{1}' -f $Spec.Name, $entry.Key
        $diagnosticPath = Join-Path $OutputPath $diagnosticName
        Copy-Item -LiteralPath $source -Destination $diagnosticPath -Force
        Write-Output ("DIAGNOSTIC {0} ({1} bytes) -> {2}" -f
            $entry.Key, $length, $diagnosticPath)
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

        if ($DiagnosticOnly) {
            if ($Interactive) { throw 'DiagnosticOnly cannot be interactive' }
            $privateRunner = Join-Path $projectRoot 'tools\run_hidden_noctis.py'
            $runnerArguments = @(
                $privateRunner,
                '--executable', (Join-Path $stage 'Noctis-IV.exe'),
                '--working-directory', $stage,
                '--timeout', [string]$DiagnosticTimeoutSeconds
            )
            if ($DefaultDesktop) {
                $runnerArguments += '--default-desktop'
            }
            $runnerArguments += @("clock=$ClockSeconds", 'quit')
            & python @runnerArguments
            if ($LASTEXITCODE -ne 0) {
                throw "Scene $($spec.Name) private diagnostic run failed"
            }
            Export-SceneDiagnostics -Spec $spec -Stage $stage `
                -OutputPath $outputPath -RequireComplete
            continue
        }

        # Automated captures must not open an interactive window on the user's
        # desktop: input would both interrupt them and taint fixed-scene probes.
        $windowStyle = if ($Interactive) { 'Normal' } else { 'Hidden' }
        $startArgs = @{
            FilePath = (Join-Path $stage 'Noctis-IV.exe')
            WorkingDirectory = $stage
            WindowStyle = $windowStyle
            PassThru = $true
        }
        if (-not $Interactive -or $PSBoundParameters.ContainsKey('ClockSeconds')) {
            $startArgs.ArgumentList = "clock=$ClockSeconds"
        }
        $proc = Start-Process @startArgs
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
        $wantGameSnapshot = $UseGameSnapshot -or -not $CaptureHostWindow
        if ($wantGameSnapshot -and $sceneWarmup -lt 4) {
            # Synthetic checkpoints announce their load for roughly three
            # source-rate seconds. Keep that transient text out of gallery art.
            $sceneWarmup = 4
        }
        Start-Sleep -Seconds $sceneWarmup
        if ($OpenFcs) {
            if ($spec.ContainsKey('Mode') -and $spec.Mode -ne 0) {
                throw 'OpenFcs requires a Stardrifter scene'
            }
            [NoctisCaptureWin32]::PostMessage(
                $proc.MainWindowHandle, 0x0100, [IntPtr]0x35, [IntPtr]1) | Out-Null
            Start-Sleep -Milliseconds 80
            [NoctisCaptureWin32]::PostMessage(
                $proc.MainWindowHandle, 0x0101, [IntPtr]0x35,
                [IntPtr]0xC0000001) | Out-Null
            Start-Sleep -Seconds 1
        }
        if ($CapsuleReturn) {
            if (($spec.ContainsKey('Mode') -and $spec.Mode -eq 0) -or
                -not $spec.ContainsKey('PlayerX') -or
                -not $spec.ContainsKey('PlayerZ') -or
                $spec.PlayerX -ne $CapsuleX -or $spec.PlayerZ -ne $CapsuleZ) {
                throw 'CapsuleReturn requires a landed scene with PlayerX/PlayerZ equal to CapsuleX/CapsuleZ'
            }
            # Exercise the shipping return path in the same process that loaded
            # the authored checkpoint. Reopening a save written during automated
            # shutdown is a different persistence test and can hide the takeoff
            # frame behind startup work. The source seals for 32 ticks and lifts
            # through tick 250, so these samples cover the complete transition.
            $samples = @(0.0, 0.5, 1.5, 2.2, 3.5, 5.0, 7.0, 9.0, 11.0, 13.0, 15.0)
            $watch = [Diagnostics.Stopwatch]::StartNew()
            [NoctisCaptureWin32]::PostMessage(
                $proc.MainWindowHandle, 0x0100, [IntPtr]0x52, [IntPtr]1) | Out-Null
            Start-Sleep -Milliseconds 80
            [NoctisCaptureWin32]::PostMessage(
                $proc.MainWindowHandle, 0x0101, [IntPtr]0x52,
                [IntPtr]0xC0000001) | Out-Null
            foreach ($sample in $samples) {
                $remaining = $sample - $watch.Elapsed.TotalSeconds
                if ($remaining -gt 0) {
                    Start-Sleep -Milliseconds ([int]($remaining * 1000))
                }
                $proc.Refresh()
                if ($proc.HasExited) {
                    throw "Capsule return exited before the $sample-second sample (code $($proc.ExitCode))"
                }
                $sampleMs = [int]($sample * 1000)
                $destination = Join-Path $outputPath (
                    '{0}-capsule-return-{1:D5}ms.png' -f $spec.Name, $sampleMs)
                Save-WindowPng -Handle $proc.MainWindowHandle -Path $destination
                Write-Output ("CAPTURED {0} capsule return {1:N1}s -> {2}" -f
                    $spec.Name, $sample, $destination)
            }
            continue
        }
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
        $capturedInternally = $false
        if ($wantGameSnapshot) {
            $capturedInternally = Save-GameSnapshotPng -Process $proc -Stage $stage -Path $destination
        }
        if (-not $capturedInternally) {
            [NoctisCaptureWin32]::ClearHover($proc.MainWindowHandle)
            try {
                Start-Sleep -Milliseconds 150
                [NoctisCaptureWin32]::HideProcessPopups($proc.MainWindowHandle)
                Save-WindowPng -Handle $proc.MainWindowHandle -Path $destination
            } finally {
                [NoctisCaptureWin32]::RestoreCursor()
            }
        }
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
                if ($sunBytes.Length -eq 128) {
                    $sun = New-Object 'System.Int32[]' 32
                    [Buffer]::BlockCopy($sunBytes, 0, $sun, 0, $sunBytes.Length)
                    $sunFloats = New-Object 'System.Single[]' 32
                    [Buffer]::BlockCopy($sunBytes, 0, $sunFloats, 0, $sunBytes.Length)
                    $rain = $sunFloats[6]
                    $exposure = $sunFloats[7]
                    $distance = $sunFloats[8]
                    $ray = $sunFloats[9]
                    Write-Output (
                        'SUN {0} mode={1} landed={2} type={3} class={4} atmo={5} night={6} rain={7:R} exposure={8:R} distance={9:R}[{10:X8}] ray={11:R}[{12:X8}] center={13},{14} visible={15} sample={16} secondary={17}' -f
                        $spec.Name, $sun[0], $sun[1], $sun[2], $sun[3],
                        $sun[4], $sun[5], $rain, $exposure, $distance, $sun[8],
                        $ray, $sun[9], $sun[17], $sun[18], $sun[16],
                        $sun[19], $sun[20]
                    )
                    Write-Output (
                        'LIGHT {0} period={1} rotation={2} viewpoint={3} plwp={4} term={5}..{6} edge={7} xfactor={8}' -f
                        $spec.Name, $sun[24], $sun[25], $sun[26], $sun[27],
                        $sun[28], $sun[29], $sun[30], $sun[31]
                    )
                }
            }
            $localPath = Join-Path $stage 'game-local-out.bin'
            if (Test-Path -LiteralPath $localPath) {
                $localBytes = [IO.File]::ReadAllBytes($localPath)
                if ($localBytes.Length -eq 176) {
                    $local = New-Object 'System.Int32[]' 44
                    [Buffer]::BlockCopy($localBytes, 0, $local, 0, $localBytes.Length)
                    $localX = [BitConverter]::ToDouble($localBytes, 32)
                    $localY = [BitConverter]::ToDouble($localBytes, 40)
                    $localZ = [BitConverter]::ToDouble($localBytes, 48)
                    $targetX = [BitConverter]::ToDouble($localBytes, 56)
                    $targetY = [BitConverter]::ToDouble($localBytes, 64)
                    $targetZ = [BitConverter]::ToDouble($localBytes, 72)
                    $bodyRay = [BitConverter]::ToDouble($localBytes, 80)
                    $bodyDistance = [BitConverter]::ToDouble($localBytes, 88)
                    Write-Output (
                        'LOCAL {0} active={1} utc={2} phase={3} body={4} type={5} view={6} nav={7} offset={8:R},{9:R},{10:R} target={11:R},{12:R},{13:R} ray={14:R} distance={15:R} globe={16} center={17},{18} mag={19:R}' -f
                        $spec.Name, $local[1], $local[2], $local[3], $local[4],
                        $local[7], $local[5], $local[6], $localX, $localY,
                        $localZ, $targetX, $targetY, $targetZ, $bodyRay,
                        $bodyDistance, $local[24], $local[25], $local[26],
                        [BitConverter]::ToSingle($localBytes, 108)
                    )
                    if ($local[28] -ge 0) {
                        Write-Output (
                            'COMPANION {0} body={1} type={2} relative={3:R},{4:R},{5:R} distance={6:R} ray={7:R} flare={8} center={9},{10}' -f
                            $spec.Name, $local[28], $local[29],
                            [BitConverter]::ToDouble($localBytes, 120),
                            [BitConverter]::ToDouble($localBytes, 128),
                            [BitConverter]::ToDouble($localBytes, 136),
                            [BitConverter]::ToDouble($localBytes, 144),
                            [BitConverter]::ToDouble($localBytes, 152),
                            $local[40], $local[41], $local[42]
                        )
                    }
                }
            }
        }
        if ($KeepStages) {
            Export-SceneDiagnostics -Spec $spec -Stage $stage `
                -OutputPath $outputPath -RequireComplete
        }
    } finally {
        # Keep any diagnostics emitted before an early product exit. This makes a
        # hosted failure discriminating without weakening the successful path's
        # complete size checks above.
        if (-not $Interactive -and ($KeepStages -or $DiagnosticOnly) -and
            (Test-Path -LiteralPath $stage)) {
            Export-SceneDiagnostics -Spec $spec -Stage $stage -OutputPath $outputPath
        }
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
