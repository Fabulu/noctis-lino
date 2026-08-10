# PLAYTEST.md - Noctis IV L.in.oleum port

This is a test checklist and capability inventory.  Interactive and automated
production runs are called out explicitly below; unchecked scenarios remain
requirements rather than implied results.

## What the playable build can do right now

| Capability | Status |
|---|---|
| Walk inside/on top of the Stardrifter | Live first-person hull, lift, cupolas, glass, consoles and HUD |
| Fly to a generated star | Live Vimana approach with exact galaxy hash and selected-star globe, visible power/lithium reserves, source-shaped stellar lithium collection, and a visible fine approach to the selected planet before landing |
| Enter a generated planetary system | Source-generated body topology with an animated console map: central star, retained relative orbits/orientations, selected planet, and correctly parented moons; the flight HUD identifies planets versus moons and shows a readable world class plus authoritative landability |
| Land and walk | Physical capsule descent, gravity, rebounds and settling lead into first-person type-specific terrain, across the source 64-tile view radius with live textures, shading, crevasses, deterministic rocks, historical ruins, open-ocean sea level, calm-water/ice terrain reflections, shimmer, contracting wind crests and expanding swimmer wakes, type-3 vegetation/trees, three mammal gaits, landing/flying/capturable birds, atmospheric skies, type-3 rain/lightning, source-shaped gravity/temperature/pressure/pulse telemetry, low-gravity jumping, hold-to-thrust jetpack flight, and capsule ascent |
| Resize the game | Live iGUI window with centered 8:5 nearest-neighbour aspect-fit scaling; validated dimensions persist across clean restarts |
| Save / load | A valid `CURRENT.LIN` resumes automatically at startup; verified saves refresh `CURRENT.BAK`, and a present-but-malformed primary visibly recovers from that last-known-good copy while a deliberately missing primary starts clean. Global F6/F7 checkpoints work in the ship and on settled surfaces, retain target/player state plus landing and settled-capsule coordinates, window dimensions, presentation, diagnostics, soundtrack, internal light, navigation devices, capture progress, power, lithium, collector, pending-rescue state, and a UTC timestamp for closed-game evolution, and show visible success/failure feedback; v1 through v10 port saves remain loadable and the exact original CURRENT.BIN codec remains available as a component |
| Distributable bundle | `package_noctis.ps1` builds an isolated play folder with every linked map/model/font/audio/catalog asset, a relocatable working-directory launcher, player instructions, the Noctis WPL, and a SHA-256 manifest |
| Quit | Esc, the red iGUI close button, and Alt+F4 all exit through checkpoint/audio cleanup |

## How to run

```powershell
# Play the existing build (builds automatically when missing)
powershell -NoProfile -ExecutionPolicy Bypass -File C:\programmieren\linoleum\play_noctis.ps1

# Force a fresh production build, then play
powershell -NoProfile -ExecutionPolicy Bypass -File C:\programmieren\linoleum\play_noctis.ps1 -Build

# Build a self-contained redistributable play folder
powershell -NoProfile -ExecutionPolicy Bypass -File C:\programmieren\linoleum\package_noctis.ps1
```

The launcher always uses `work\` as the game directory, preventing checkpoints
and other persistent files from being split across whichever directory happened
to be current in the shell. The bounded timeout harness below remains available
for automated smoke work; it is not the normal interactive launcher.

For a bounded, self-terminating integrated soak (the checked-in game is
intentionally long-lived), use the sandbox utility. It copies the source and
its declared libraries into `tests/gen/game_soak`, builds through
`lino_build.ps1`, and runs through `w7arun.ps1` with clean-exit proof:

```powershell
python tests/soak_game.py --frames 1000 --timeout 600
```

The utility grades the exact 24-unit/96-byte telemetry contract: terminal
frame, changed dzat, progressed pwr, nonzero framebuffer samples, clean exit,
and wall-time/FPS. A 5-frame smoke run passed on 2026-08-08 (6/8 framebuffer
samples nonzero).

The playable build opens in iGUI under its `Noctis IV` title at 642x426, with
an exact 640x400 work area presenting the authentic 320x200 framebuffer at 2x.
New games and capsule returns face into the illuminated Stardrifter interior
instead of outward through the open nose into empty space.
Dragging iGUI's size control scales the completed logical frame--including the
HUD, notices, GOES prompt, FPS counter, and control card--and adds centered
black bars when the window is not 8:5. The authentic indexed renderer remains
320x200. The build keeps unmodified
local copies of iGUI and its `.tga` chrome assets under `work/` because this
compiler cannot reliably concatenate stockfile parts while switching between
the main-source and library directories. `-StageExtension .lxe` also prevents
Windows executable scanners from briefly locking the growing PE between iGUI
stockfile appends; the build driver renames the settled result to `vhgame.exe`.

The presentation path now palette-expands a stable logical RGB page, composes
all player-facing overlays there, scales the completed page into the iGUI
backdrop, and publishes the composed window once. It
caches the visible 729-sector star projection in short source-derived batches,
and lazily reuses exact integral-degree trigonometry. Measured startup-frame
work fell by about 70% from the pre-pass candidate; the current 60-FPS smoke
averages about 8.4 ms for render plus native GUI presentation, below its
16.7-ms budget. The current production build explicitly starts iGUI unfolded,
removes the duplicate Primary-layer writes and second cursor retrace, and
completed 60 real control-loop frames in 1,012 ms (59.29 FPS, integer overlay
59) at the default 2x window. Average measured ship rendering was 9.7 ms and
logical-page preparation/presentation 1.7 ms per frame. The real iGUI full-size
control remains correctly centered and aspect-fitted, including the capsule HUD.
The one-time world/model initialization is not included in these per-frame
figures.

Controls:

- F10: open/close the native GAME menu; Up/Down moves between Controls, GOES,
  save/load, FPS, presentation rate, music, and clean quit, and Enter activates
  the selected action
- Right mouse drag: look around in the ship or on a surface; sensitivity is
  normalized through the current aspect-fit size and ordinary pointer motion
  remains available to the iGUI chrome and GAME menu
- `?` or F9: show/hide the in-game control card (available in ship, GOES, and
  surface modes; F9 is the layout-independent fallback because the Windows
  iGUI host does not expose a distinct F1 state)
- Left/right/down arrows: look around
- E: start the Stardrifter roof lift from inside the ship; walk clear after
  arrival, then step into the roof cupola opening to trigger the original
  automatic return
- W/S: forward/back
- A/D: strafe left/right
- Ctrl + W/A/S/D: stalk slowly on habitable surfaces. Birds take off when
  approached at ordinary speed; close the final gap cautiously to capture one
- G or Enter: open the Stardrifter's GOES console; Tab or Enter submits the
  visible screen-space command line
- Type `SAVE` or `LOAD` in GOES: write/read `CURRENT.LIN`
- Type `NEXT` in GOES: select the next source-generated star in the local
  729-sector navigation cube and begin a real Vimana transit from the current position
- Type `NEW` in GOES: replace the resumed checkpoint with a fresh opening
  flight; presentation mode, soundtrack preference, and starmap names remain
- Type `STAR X Y Z` in GOES: target exact integer coordinates from a starmap
- Type `NAME STAR LABEL` or `NAME PLANET LABEL` in GOES: add the current
  target or selected body to the persistent local starmap (labels are up to
  20 characters; duplicate identities and labels are rejected visibly)
- 1/2/3/4/5: directly select the first five bodies on the planetary display
- `[` / `]`: cycle backward/forward through every generated planet and moon
- L: after star `CALIBRATED`, start fine approach to the selected body; press
  again after `STANDBY` to open the landing-site selector. Arrows choose the
  source `000..359` longitude and `001..119` latitude, L/Enter begins descent,
  and C cancels
- C: at a calibrated class-5 star, or a class-6 star with radius above 4,
  toggle lithium collection; the `PWR`/`LI`/`ON` readout shows live progress
- H: when both usable power and lithium reach zero, request the emergency
  three-unit rescue reserve so an exploration checkpoint cannot be stranded
- R: aboard the Stardrifter, open/close the onboard-device root or return from
  a child page; on a surface, seal the capsule and ascend while inside it
- At the onboard root, 6/7/8/9 open navigation, miscellaneous, cartography,
  and emergency pages. Their displayed 6-9 rows operate the field amplifier,
  target finder, five tracking modes, anti-radiation stand-off, internal light,
  data sheets, starmap naming/targeting, reset, rescue, and lithium collector
- The surface HUD shows approximate `POD` range, an `F/L/B/R` direction toward
  it relative to your current view, captured `BIRDS`, and the `CTRL:STALK` and
  `R@POD` reminders; an out-of-range R press reports `RETURN TO CAPSULE`
- F4: show/hide the measured FPS counter
- F5: toggle between the default original 18.2 FPS presentation and optional
  60 FPS mode (gameplay simulation always remains 18.2 Hz)
- F6: quick-save a stable ship or landed state
- F7: quick-load the checkpoint and reconstruct its ship/surface environment
- F8: toggle the authorized Noctis soundtrack (the game remains playable and
  silent if the asset or audio device is unavailable)
- I: cycle remote-target, local-target, and external-environment data sheets;
  pressing I after the environment page closes the display
- Esc, red close button, or Alt+F4: save and quit

GOES input is shown along the bottom of the game viewport. The local starmap
is created automatically if a distribution starts without `STARMAP.BIN`; its
first name remains available after relaunch. Lookup and naming skip exponent-zero,
Inf/NaN, over-range, and `Removed:` records without rewriting the player's file.

## Fidelity claims (proven)

- **Surface generation**: 18/18 cases byte-exact lino==spec==cref, all 10 planet types
- **Ground renderer**: 604/604 three-way (hpoint + fragment + p_Forward + change_angle_of_view + iperificie)
- **Saves**: CURRENT.BIN 381-byte round-trip byte-exact across recon captures
- **Game loop exact kernel**: 699 units three-way byte-exact (sector chop, nearstar_identity, approach, landing roundtrip, additional_consumes, keyboard)
- **Audio fidelity**: silence is the faithful original ship state. The
  authorized Ryan J. Bury manual soundtrack is now an explicit completion
  feature, with an off control so the original behavior remains available.

## Known limitations (honest)

- **Surface presentation**: every accepted landable class now has a distinct terrain arm: lunar crater fields (type 1), thick-atmosphere plateaus (2), four habitable biomes (type 3), corrugated boulder worlds (4), thin-atmosphere eroded/permafrost terrain (5), striated frozen shelves (7), and milky quartz worlds (8). These join the generated day/night sky palette, diffuse shading, textures, crevasses, rocks, capsule/beacon, historical ruins, calm-water and ice reflections, wind crests, swimmer wakes, vegetation, trees, mammals, capturable birds, the original type-2 dense-atmosphere grayscale smoothing, and the original type-3 storm gates. Raininess 2+ can flash the surface palette; raininess above 3 submits wind-slanted foreground rain sticks. Storm density retains the source 50-stick floor but caps accumulated extras at 174 sticks to protect 60 Hz presentation. The original offsets-map panorama now runs through a fixed-buffer direct specialization and is cached as a complete 320x200 indexed sky until pitch or yaw changes; this removes the generic per-byte dispatch freeze while restoring generated horizon detail. Wind and fauna state continue at 18.206 Hz in both presentation modes, while rain positions refresh at presentation cadence. Distant terrain uses 8-tile and 32-tile cells around an exact three-tile walking ring; only the nearest two depth bands are texture mapped, historical walls retain their marked unit-tile overlay, and the settled pod keeps both support grids while full translucent panels remain visible during descent/ascent. Reflections retain the source terrain-only half-scan pass and are suppressed during incoming wind waves. Current production load and resize smokes report 60 FPS at native and full-size presentation; movement advances without capsule recentering and persists the changed view angle.
- **General surface identity**: the measured opening target retains its exact body seeds. Other selected stars now retain `p_orb_seed`, `p_tilt`, `p_orb_tilt`, `p_orb_ecc`, radian orientation, initial/final `p_ray`, and `p_orb_ray` through the original live x87 expression boundaries. The opening orbital probe matches the independent reference bit-for-bit across all checked fields. The original three-term `* 4112` surface seed now uses those retained binary64 fields and the live `__ftol` boundary. Each non-pinned landing coordinate also runs the verified source globe generator and samples its exact location albedo together with its atmosphere, clouds, rain, and scenario output.
- **Capsule physics**: the source gravity, 0.32 rebound, settle thresholds, 32-frame seal, and 250-frame ascent cutoff are live. Touchdown now executes the original 252-step, 0.025-radian scan around the complete 1,024-unit pod circle, with binary32 angle/coordinate stores, chopped `hpoint` arguments, the 512-unit maximum-lip decision, and steepest-slope direction handed back to atmospheric drift after a rebound. Atmospheric worlds use the source lateral formula after vertical physics and evolve `iwp`, `wp`, and `wdir` every simulation tick through the live Borland stream. The original RNG state entering the five pre-surface initialization draws is not retained, so that initial state remains deterministically surface-seeded rather than claimed bit-exact.
- **Landing state**: direct keys select bodies 0..4 and bracket keys wrap through every generated planet and moon; checkpoints retain both the selected body and galactic target. General landings read UTC, reproduce Noctis's seconds-since-1984 clock and rotation-period draw ranges, compose eccentric target/parent orbit vectors, and use the original planet-versus-moon rotation seed expressions, 130-degree night band, and twilight exposure. The opening system remains pinned to its measured sky inputs.
- **Orbital console**: every selected system now uses the `nstopo`-retained orbital radii, orientations, body count, and moon ownership. A monotonic logarithmic compression keeps very wide generated systems inside the physical screen; planets have 24-segment orbit tracks and moons are independently scaled around their actual parent. The detailed rails remain proximity-gated at the physical wall station to protect general ship-frame performance.
- **Fine approach**: star calibration and selected-body arrival retain separate
  `ap_reached`/`ip_reached` state. The live game feeds each body's retained
  orbital radius and physical radius into the original MG approach cascade,
  draws the closing globe, shows `FCS APPROACH` until arrival, and requires
  the genuine `STANDBY` state before landing. The accepted landing is committed
  at the next clean frame boundary, with explicit x87 resets between terrain,
  sky, and capsule phases. Thirty-two
  unchanged source steps are batched per simulation tick, reducing the opening
  planet's measured 8,895-step approach from roughly eight minutes to about
  fifteen seconds without changing its state sequence.
- **Offline save evolution**: the live game implements source-shaped stellar
  lithium collection, reserve-cell top-up, persistent collector state, and the
  negative-charge OMEGA behavior. Version-6 checkpoints now retain Noctis UTC
  time; loading credits one lithium unit per 30 closed seconds up to 120,
  restores the source 15,000--19,999 partial-fill power range, and advances or
  completes a pending rescue.
- **Emergency assistance**: the depleted-state gate and three-unit lithium
  delivery match the original outcome. A second Stardrifter now follows the
  source's squared approach, close orbit/transfer, and squared departure path;
  the original two-minute visible phase is compressed to about ten seconds.
- **x87 across isocalls**: the lino win32 stub corrupts the x87 stack - fix is fninit+fldcw before each FP phase (documented in game.txt header)
- **Regression inventory**: test_ground.py is registered (22 registered, 0 unregistered); nsrun NSIN validation is fixed and test_geometry passes
- **Open ground work**: the type-3 texture matches the NIV+ capture exactly. Disassembly of the original `round_hill` proved that Borland compares its 16-bit `unsigned` loop bounds without clipping wrapped top/left hills; reproducing that rule reduced the post-landing captured heightmap residual from 39,710 to 1,752 bytes. The surviving RAM image was taken after the landed loop began reusing `p_surfacemap` as scratch, so it is retained as a capture-boundary XFAIL rather than mislabeled as a pristine generator mismatch.

## What's not yet verified

- The full integrated game loop under exclusive mode (the bounded soak harness passes; multi-hour coverage remains open)
- Multi-hour stability (the complete production journey and bounded capsule
  runs plus a 189.8-second interactive standalone-bundle session pass, but an
  unattended multi-hour session has not been completed)

The automated iGUI capsule probe now targets a generated class-3 system and
selects a calm ocean reflection case. It completes atmospheric fall, 11
bounded rebounds, slope-checked touchdown, walking, seal, ascent, and
restoration to the Stardrifter. The latest end-to-end run completed in 13.7
seconds with `bad=0`, 720 hull leaves, and 54 reflected terrain tiles submitted
while incoming wind waves remained disabled. A prior class-2 run also verified
the general UTC daylight path at 54.782-degree exposure and retained sun
distance 48.06368. This is a bounded runtime smoke, not a claim that the
interactive checklist or remaining surface-content paths are complete.

A focused headless production-library capsule smoke on 2026-08-10 exercised
the current atmospheric integrator independently of iGUI activation. Ideal
wind changed from 277 to 534 in Q10 and direction from 2342 to 2274 in
degree-sixteenths; the pod accumulated peak 14/20-unit lateral displacement
before its source-style tile-centre touchdown snap, settled after 11 rebounds,
and completed seal/ascent back to ship mode in eight batched calls with a
clean process exit.

A focused headless rainy-world smoke on 2026-08-10 exercised the production
weather layer at raininess 3.75. It submitted all 108 requested wind-slanted
rain sticks, produced 52 visible foreground pixels, brightened the sampled
palette component from 0 to 31 for lightning, restored it exactly to 0, and
exited cleanly. The local weather stream left terrain and Borland wind RNG
state isolated.

The same focused surface-effects probe filled a type-2 frame with palette index
200 and ran the dense-atmosphere pass. The untouched top and bottom guards
remained 200 while the 56,960-byte interior normalized and smoothed to index 8;
the bounded process again exited cleanly.

A focused non-opening daylight probe on 2026-08-10 generated a 22-body system,
selected a type-3 body, retained its exact surface/rotation inputs, composed
the eccentric parent-relative star vector, produced a normalized terminator
and daylight exposure, and exited cleanly. The paired opening-orbit probe
matched the independent geometry reference bit-for-bit for all 30 checked
binary64 values.

The historical-surface probe targets Felysia at Balastrackonastreya's exact
catalogue coordinates `(-18928, -29680, -67336)`. It generated 92 ruin-map
marks and submitted a peak of 179 full-detail ruin tiles, then completed the
same 11-bounce walk/return path in 7.9 seconds with 720 hull leaves and zero
invalid leaves. The detached GUI probe now explicitly initializes the unfolded
host state and prepares its scaler before the first repaint, matching production.
This run also caught and fixed unsigned lower-bound checks that had removed the
near terrain ring and truncated map-edge traversal.

The global checkpoint controls were exercised in the real GUI executable with
the earlier version-2 codec: F6 produced a validated 108-byte `CURRENT.LIN`, movement changed the live ship
position, and F7 restored `(0, 0, -500)`. Capsule descent/ascent states are
refused with an on-screen notice because those transient integrator fields are
deliberately not part of the stable checkpoint contract. Versions 3 through 6
expanded the record to 144 bytes for presentation mode, FPS overlay,
soundtrack choice, captured-fauna progress, power/lithium state, an in-flight
rescue, and the closed-game timestamp. Version 7 is 152 bytes and adds the
validated iGUI width/height while continuing to accept 96-byte v1, 108-byte
v2, 124-byte v3, 132-byte v4, 140-byte v5, and 144-byte v6 records.
The production startup path was also launched in two isolated directories:
a valid 144-byte landed checkpoint opened directly on its surface without F7,
while the directory with no checkpoint opened the clean Stardrifter unchanged.

The Stardrifter regression path was exercised again through the real GUI and
physical Windows key events on 2026-08-10 after the presentation repairs. The
first exact-build run exposed the remaining wobble: ascent fed Noctis's large
`step=-pos_y` through ordinary camera-relative walking, moving from `z=-2020`
past the platform centre to `z=-3674` before the positional restraint recovered.
The shipping lift now uses only the monotonic platform-centering restraint.
The rebuilt run approached at `(0,0,-2340)`, reached and released at
`(0,-750,-3023)` with `lifter=0,onroof=1` and no centre overshoot, walked off
to `z=-4821` without recapture, then returned and descended to
`(0,0,-2491)` with `lifter=0,onroof=0`. Esc exited naturally with code 0.
E away from the aperture cannot start motion, and a held key cannot restart
the lift. The current build reports where to stand when E is pressed elsewhere.
The roof endpoint releases the player cleanly; walking back into the opening
starts the original automatic descent.

The RC24 lift-guidance smoke exercised that complete path through the real GUI.
E at the opening position displayed `LIFT: STAND IN CENTER APERTURE`; after W
reached `z=-2420`, one E arrived and released at
`(0,-750,-3031)` with `lifter=0,onroof=1` and displayed
`LIFT: ROOF LEVEL - WALK CLEAR`. Walking back into the opening returned to
`(0,0,-3095)` with `lifter=0,onroof=0`, and Esc exited with code 0.
`work/vhgame-rc24-lift-hint.png` and
`work/vhgame-rc24-lift-roof-arrived.png` are the corresponding PrintWindow
captures.

The layout-independent help fallback was exercised through the production GUI
on 2026-08-10. A physical F9 event opened the fully scaled control card with
its `?/F9:CLOSE` legend; a second F9 restored the live Stardrifter frame. Esc
then exited naturally with code 0 and wrote a valid 152-byte version-7 save.

The native iGUI GAME menu was exercised through its built-in F10 keyboard path
on 2026-08-10. The shipping dropdown rendered, Up/Down selected its third
option, Enter invoked the same checkpoint action as F6, and `CURRENT.LIN` was
updated to a valid 152-byte version-7 record before the later clean exit. The
menu also exposes Controls, GOES, load, FPS, 60/18-Hz presentation, music, and
save-and-quit without requiring gameplay key knowledge.

Resizable right-drag mouselook was exercised through real Win32 pointer events
on 2026-08-10. At the default 2x host size, a 90-pixel right/60-pixel upward
drag changed the saved view from `(alpha=0,beta=180)` to `(-6,168)` while the
player remained exactly at `(0,0,-500)`. The first run caught an unsigned
negative-Y division that clamped pitch to `+44`; the shipping path uses signed
scaling through the current fitted width/height and the corrected run exited
cleanly.

The selected-body HUD was exercised in a fresh production GUI on 2026-08-10.
Body 2 displayed `P02 T04 LAND ROCKY`; body 3 displayed
`P03 T06 NO-L GASGIANT`, and foreground Esc exited naturally with code 0.
The same formatter reserves both type digits, recognizes moon ownership, and
marks generated type-10 companion stars non-landable instead of displaying
their former `TYPE :` overflow.

The live catalog filter was exercised with two 36-byte player catalogs at a
zero-identity target. A smallest-normal binary64 record displayed `VALID ZERO`;
an otherwise identical `-0.0` record remained uncharted. Both files were left
byte-for-byte intact. The full 1,202,500-byte player catalog then reached its
GUI window in 1.35 seconds, exited with code 0, and retained the same SHA-256.

A clean production executable was driven through the full opening journey with
real GUI key events on 2026-08-10: calibrated Stardrifter, L approach, visible
STANDBY, second-L descent, stable mode-1 landing, surface walk, capsule seal and
ascent, Stardrifter restoration at `(0,0,-500)`, checkpoint exit, and automatic
mode-0 resume. The walk also exercised the capsule boundary: at 4,800 units R
was refused, the player followed the POD indicator back to 1,200 units, and R
then returned normally. The refusal now displays `RETURN TO CAPSULE`; its
focused replay exited with code 0 while retaining the landed checkpoint.

The bundle path was exercised independently of `work\` on 2026-08-10.
Its twelve-entry SHA-256 manifest covered the executable, relocatable launcher,
and every external runtime input; the thirteenth file was the manifest itself,
for a total of 27,751,675 bytes. The resulting GUI restored the full Stardrifter model and
console structure, toggled the available soundtrack OFF, persisted that choice,
resumed, toggled it ON, and wrote a valid 152-byte ship checkpoint. Both bundle
runs exited with code 0 at the persisted 642x426 window size.

The launcher was then invoked from a deliberately unrelated working directory.
It returned exit code 0 after a clean Esc save, wrote the 152-byte checkpoint
and runtime diagnostic only inside the bundle, and left the caller directory
empty. All 12 packaged hashes still matched the manifest. This is the supported
bundle entry path; running the payload executable directly does not establish
its relative-file directory.

The same standalone bundle then ran for 189.8 seconds under repeated real GUI
movement/look, help repaint, FPS overlay, 18.2/60-Hz presentation, soundtrack,
and checkpoint controls. All 43 bounded responsiveness probes returned. Working
set moved from 72,101,888 to 72,089,600 bytes (maximum 72,253,440), private
memory from 101,281,792 to 101,044,224 (maximum 101,511,168), and handles from
300 to 297 (maximum 301). The end frame retained complete ship geometry; clean
exit, checkpoint resume, and the resumed exit all succeeded with code 0. This
is bounded stability evidence, not a substitute for the still-open multi-hour
session.

The focused tree executable renders the production `VHGND tree` path through
the real polygon rasterizer. Its 2026-08-10 run completed a 4,879-unit,
three-branch tree with all three limb faces closed and 1,665 non-background
framebuffer pixels, then exited cleanly.

The paired biome generator smoke completed desert and ice surfaces in 5.8
seconds. Desert produced 0--127 dune relief, 128-scale coarse sand, and no
rocks; the ice seed selected the source-valid flat cracked-ice class with a
36-scale frost texture and rare-rock parameters.

The remaining-landable-types smoke ran lunar, thin-atmosphere, and striated
ice generation through the production library in one process. Their terrain
ranges were respectively 0--24, 0--127, and 0--67, with distinct texture
totals and rock populations. This run also exercised the completed x87
`pow(y,h_raiser)` crater profile and caught the formerly erased positive-level
terrain before the integrated rebuild.

The real GUI journey smoke on 2026-08-10 used the shipping controls from the
opening Stardrifter: star calibration, `L` fine approach, visible
`FCS APPROACH` to `FCS STANDBY`, a second `L`, capsule landing on body 1's
type-8 terrain, and F6 save. The resulting v6 checkpoint was 144 bytes with
`mode=1`, body 0, and settled position `(1646592,-600,1646592)`. A clean
relaunch loaded that checkpoint with F7, rendered the same surface, accepted
`R` from the capsule, returned to the Stardrifter, and saved `mode=0`.

A follow-up production beta journey on 2026-08-10 repeated the clean ship,
calibrated approach, standby, landing, surface save, walking, turning, pod
guidance, capsule return, and final ship-save path. It exposed an unsigned
angle-normalization bug: yaw `-12` was treated as `244` because `'%` is the
unsigned remainder operator. Backward movement consequently displaced
`(-5929,+2893)` instead of following the camera. Camera, pod, wind, orbital,
terminator, and panorama normalization now use signed `%`; the identical saved
state then displaced `(-1375,-6457)`, returned successfully to mode 0, and held
the negative-yaw horizon pixel-stable across consecutive production captures.

The RC4 fauna smoke loaded a real version-7 checkpoint on a generated type-3
surface one thousand units behind a ground bird. Hardware-style held Ctrl+W
input moved the shipping executable 2,320 units at the 80-unit stalking pace,
closed against the bird's source-scaled 31-unit reaction speed, captured
exactly one bird, and exited naturally with code 0. The resulting 152-byte
checkpoint retained `mode=1`, body 3, and `captures=1`.

The paired reload smoke started the shipping executable from a type-3
checkpoint already holding `captures=1`, then drove Ctrl+W another 2,080 units
through the regenerated first bird's spawn. Surface reconstruction restored
that bird's captured record, the game exited naturally, and the next 152-byte
checkpoint still held exactly one capture rather than duplicating it.

The RC6 surface-HUD smoke loaded a real landed version-7 checkpoint into the
production GUI and rendered the original `surrounding()` gravity, temperature,
pressure, and movement-sensitive pulse fields. The first integrated frame
showed that the former bottom baseline was clipped and touched the shared
checkpoint-notice row. The shipping row now occupies logical Y=160; the repeat
capture retained the full cyan telemetry line above the complete green
`CHECKPOINT LOADED` notice, and foreground Esc exited with code 0 while writing
a valid 152-byte checkpoint.

The RC7 surface-motion smoke drove the production GUI through real Windows key
events from the same landed checkpoint. Starting at `y=-600`, J produced a
sampled airborne position of `-2685`; body-dependent gravity returned the
player to exactly `-600`. Holding Space then reached `y=-7149`, proving that
the physical-key path supplies continuing jetpack thrust rather than a
one-frame impulse. The game exited naturally with code 0 and retained a valid
152-byte checkpoint.

The RC8 onboard-data smoke rendered the production GUI with each of the three
datasheet states selected in turn. Remote target, local body, and ship
environment rows remained bounded and readable at the default 2x host; a
version-6 landed checkpoint then reconstructed its surface and showed live
gravity, temperature, pressure, pulse, airborne, capture, and resource state
on the environment page. This visual pass caught two integrated defects before
packaging: editable string rows shared unsafe declaration boundaries, and the
FCS row passed the address of its pointer rather than the chosen status string.
Dedicated workspace rows and an explicit pointer dereference fixed both. All
four runs exited through foreground Esc with code 0; the landed run upgraded
cleanly to a valid 152-byte version-7 checkpoint.

The RC9 miscellaneous-device smoke rendered the production 2x GUI with the
original ship-side command numbers: 6 internal light, 7 remote target, 8 local
target, and 9 environment. The bounded cyan menu and close/select legend fit
the logical page without touching the iGUI chrome. Its first clean exit wrote
a 156-byte version-8 checkpoint. The final shipping executable then loaded a
checkpoint whose light field was OFF (`-1`), exited normally, and rewrote the
same 156-byte record with version 8 and `-1` intact, exercising the real
load/reconcile/save path rather than only the codec text.

The RC10 onboard-system smoke rendered the new root and navigation pages in
the production 2x GUI. The navigation page reported normal-field/finder-off,
fixed tracking, and anti-radiation-on defaults; a separate forced amplifier
run built and displayed the expanded 14x14x14, 2,744-sector star field and
remained responsive for the bounded run. Unchanged amplified views now reuse
their projected cache for 30 frames, while look-bucket and sector changes
still invalidate immediately. Cartography commands seed the live GOES editor
for star/body labels and coordinate targets, and emergency commands share the
existing collector and visible rescue services. Version-9 checkpoints add one
packed navigation word in a 160-byte record while accepting all v1-v8 sizes.

The RC11 cartography smoke rendered the production in-range target browser
with separate signed X/Y/Z rows and previous/next/select/back commands. Its
first visual build exposed unterminated mutable rows, causing X to continue
through Y and Z; explicit 13-unit boundaries fixed that. A second pass exposed
brace-string whitespace compaction beside the live sign, so the final formatter
constructs each row explicitly as axis, ASCII space, one sign, nine digits, and
terminator. The corrected GUI showed `X +003979984`, `Y -000043407`, and
`Z -000043984`, remained responsive, and the final closed-startup build passed
the focused game check.

The RC12 physical-device smoke drove the unforced production GUI with Windows
key-down/up events through R, navigation 6-9, cartography, the target browser,
target selection, emergency, and Escape. A direct iGUI key-table fallback now
shares one held edge with buffered characters, so missing WM_CHAR delivery
cannot make those controls unreachable and an ordinary character is not
repeated on the next presentation frame. The run exited through the game's own
save path with a 160-byte v9 checkpoint: amplifier/finder ON, tracking FAR,
anti-radiation OFF encoded exactly as packed value 19. Browser selection moved
the target from the opening star to `(3228560,-666563,-451543)`. A production
relaunch loaded that record, exited naturally, and retained the same target and
packed word, proving the live load/reconcile/save round trip.

The RC17 host smoke used iGUI's own controls. Full-size changed the real window
from 642x426 to 962x626 and F6 stored those exact dimensions; a top-right native
size drag produced 702x460 and the following launch restored 702x460. At that
arbitrary aspect, right-drag look changed beta from 180 to 170, F9 opened and
closed without stalling, GOES `NEXT` changed the persisted target, and `NAME
STAR HOSTRC17` appended exactly one 32-byte record. At the maximum host size,
two checkpoint-sampled intervals measured 60.17 FPS in fast presentation and
18.13 FPS in original presentation. The old exclusive-mode fallback was also
reproduced on a 1280x720 desktop: unsupported 962x626 exclusive mode used to
leave a 962x626 window and overwrite a prior 702x460 preference. The rebuilt
path restored the exact 642x426 pre-full geometry and persisted 642x426 before
a natural exit, with no display-resolution change or residual process.

The RC18 landing-site smoke drove a clean production GUI from opening-star
calibration through local approach and `STANDBY`. The new full-page selector
accepted real arrow events, moved from `000:060` to `008:054`, and F6 recorded
those coordinates in a valid 168-byte version-10 checkpoint before confirmation.
L then committed terrain/sky generation, capsule descent settled normally, and
the landed checkpoint retained mode 1, body 0, and `008:054`. A clean relaunch
reconstructed the landed surface with the same coordinates and exited with code
0. Separately, a real 160-byte v9 ship checkpoint loaded and rewrote as v10 while
retaining `(0,0,-500)`, the opening target, and packed navigation value 12; its
new location fields correctly defaulted to the original `000:060` site.

The RC19 display smoke reproduced the reported black/invisible Stardrifter in
the real desktop output while the indexed page, palette, RGB composition, and
GUI backdrop all contained a complete hull. The final iGUI `Update Area` call
was disabled during control-loop preparation, so it silently failed to copy
the backdrop to Primary. Production now performs that complete layer copy and
direct whole-display retrace explicitly; the outer loop adds the pointer. A
desktop-duplication capture shows the full Stardrifter on startup, and landed
v10 checkpoints at `008:054` and `180:060` show visibly different source-sampled
terrain and horizons. Both surface runs reported 59 FPS with roughly 1,000 ms
wall time per 60-frame sentinel. The focused gameplay check passes, and no
diagnostic dump path remains in the production source.

The RC20 type-3 pass replaced the production shortcut with the original
OCEAN/PLAINS terrain branches: right-to-left hill draws, unsigned 16-bit hill
bounds, shoreline/open-sea decisions, vegetation classes, source grass
asterisms, fast height noise, rock parameters, and calm-water propagation.
The real 322x226 iGUI probe generated a type-3 OCEAN site in under one second,
completed descent, settled walking, 155 reflected terrain submissions,
capsule ascent, and Stardrifter restoration in 15.0 seconds with `bad=0`.
`work/vhgame-rc20-type3.png` is the PrintWindow capture of that settled frame.

The RC21 capsule pass replaced the eight-point landing adapter with Noctis's
complete 252-sample touchdown circumference. In the real GUI probe the pod
landed after 11 rebounds at 2.08 seconds; the largest observed frame interval
was 232 ms, and descent, walking, ascent, and Stardrifter restoration completed
in 15.17 seconds with `bad=0`, so the fidelity repair remains interactively
responsive.

The RC22 persistence smoke reproduced the atmospheric edge case at the far
map corner: player `(122880,-600,3145728)`, settled capsule
`(122880,0,3145728)`. A version-11 checkpoint restored those capsule
coordinates after deterministic terrain regeneration; the packaged executable
then accepted R, completed ascent, wrote a 180-byte ship checkpoint with
`mode=0`/`landed=0`, and exited through Esc with code 0. Versions 1 through 10
remain accepted; because those formats did not record a wind-displaced
touchdown, their one-time landed migration anchors the capsule at the saved
walker's terrain position so an existing RC21 save cannot remain stranded.

The RC23 compatibility smoke then fed the shipping executable the reproduced
168-byte RC21/v10 landed record from that same map corner. It reconstructed the
capsule at `(122880,0,3145728)`, accepted R, returned to the Stardrifter, and
rewrote the checkpoint as a 180-byte v11 record with `mode=0`/`landed=0` before
a clean code-0 exit. This is the upgrade path for saves made before capsule
coordinates existed.

The RC25 recovery smoke created matching 180-byte `CURRENT.LIN` and
`CURRENT.BAK` files with the FPS preference enabled, replaced the primary magic
with zero, and relaunched the packaged GUI. It retained the saved preference,
displayed `CHECKPOINT RECOVERED FROM BACKUP`, exited with code 0, and rewrote a
valid version-11 primary identical to the backup. Offline evolution is now
deferred until the entire candidate record validates, so a rejected primary
cannot apply collector or rescue time before fallback.

The RC26 cadence smoke launched a clean packaged game and confirmed its first
version-11 checkpoint stores `fast=0`, the original 18.206-FPS presentation.
After relaunch, one F5 press stored `fast=1`; both sessions exited with code 0
and maintained `CURRENT.BAK`. Existing checkpoints continue to retain whichever
presentation mode their player selected.

The RC27 lift smoke started the production executable from a temporary
version-11 checkpoint with the player centered and `lifter=-100`, so no desktop
key injection was involved. Before the fix, the captured sequence reached
`LIFT: ROOF LEVEL` and then returned to `LIFT: INTERIOR DECK` within one second.
The source comparison showed that the port had discarded `step` friction,
continued center restraint on the endpoint frame, and rotated only the movement
basis by 180 degrees. The rebuilt sequence shares one heading between view and
motion, preserves `step /= 1.25`, clamps to `y=-750` before restraint, and
remains under open sky. A same-camera roof comparison also shows only the local
upper cupola panels displaced while its support grid remains fixed, matching
`polycupola(+1, 1)`. The independent route check pins a centered ascent 1,711
units from the cupola center, outside its 1,100-unit automatic-return radius;
the roof-center checkpoint still descends to `y=0`.

### Unreleased Stardrifter source-equivalence correction

The follow-up pass compared the complete lift and upper-cupola path with
`NOCTIS.CPP` and `NOCTIS-0.CPP`, including input, vertical state, forward
motion, boundary clamps, vehicle draw order, local panel displacement,
post-render center restraint, and automatic return. It supersedes the older
RC24 and RC27 lift conclusions above where they describe a center activation
gate or a port-specific return threshold.

Concrete corrections are: direct E activation as the desktop mapping of DOS
Up; a calibrated `lifter=-70` ascent with twelve visible rise frames; source
`distance + step < 1100` roof descent; movement kept
available during the ride; clamping before vehicle rendering; centering after
rendering and only on simulation ticks; signed negative-coordinate and pitch
arithmetic; and signed local cupola clamps so only nearby glass panels rise
while support lines remain fixed. `python tests/test_vhgame.py` passes and the
production source builds to a Windows PE. The lift, cupola, ascent, and descent
were then confirmed interactively before this checkpoint.
