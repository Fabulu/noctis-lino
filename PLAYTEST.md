# PLAYTEST.md - Noctis IV L.in.oleum port

This is a test checklist and capability inventory.  Interactive and automated
production runs are called out explicitly below; unchecked scenarios remain
requirements rather than implied results.

The concise coverage boundary is in `TEST_COVERAGE.md`. On 2026-08-12 the
focused integrated gameplay suite passed in full, including capsule recovery,
focus-safe GUI repaint, resizing, ship movement, jetpack, every accepted terrain
class, vegetation, trees, mammals, birds, ruins, and the Cube. That result is
broad regression coverage, not a claim that every procedural seed and native
input timing combination can be exhaustively enumerated.

On 2026-08-12 the production capture path placed the opening system's selected
star at a source-valid 200-unit flare distance by inverting the live camera
rotation. The native frame shows the corona and reflection ghosts through the
Stardrifter windows with hull occlusion intact. A separate fixed, central dry
cell on a class-3 world shows the local sun, a naturally generated hopper,
flying birds and trees. Earlier shoreline and map-edge candidates were rejected
rather than promoted as representative terrain. Both coordinates are now
reproducible through `tools\capture_noctis_scenes.ps1`.

The same capture audit found that title-based readiness was invalid for iGUI:
Windows reports the programme name `vhgame`, while `Noctis IV` is painted by
the custom chrome. A framebuffer-content readiness check now refuses the real
black pre-initialization host without waiting forever on that caption. The
catalogued one-body system IDEAL provides an authentic type-1 primary. The
temporary four-crater reduction was rejected during fidelity review: the live
generator now preserves the source's complete zero-to-thirty height-crater
field and uncapped texture details. Equal-radius profile results are cached
inside each crater to accelerate the unchanged workload.

The hosted `STAR x y z` path used by Galactic Cartography now accepts the full
signed 32-bit Parsis range: ten digits plus an optional sign, with explicit
overflow rejection. This deliberately corrects NIV+'s ten-total-character
manual editor oversight rather than inheriting its unreachable far region.

## What the playable build can do right now

| Capability | Status |
|---|---|
| Walk inside/on top of the Stardrifter | Live first-person hull, lift, cupolas, glass, consoles and HUD |
| Fly to a generated star | Live Vimana approach with exact galaxy hash and selected-star globe, visible power/lithium reserves, source-exact stellar lithium collection, and a visible fine approach to the selected planet before landing |
| Enter a generated planetary system | Source-generated body topology with an animated console map: central star, retained relative orbits/orientations, selected planet, and correctly parented moons; the flight HUD identifies planets versus moons and shows a readable world class plus authoritative landability |
| Land and walk | Physical capsule descent, gravity, rebounds and settling lead into first-person type-specific terrain, across the source 64-tile view radius with live textures, shading, crevasses, deterministic rocks, historical ruins, open-ocean sea level, calm-water/ice terrain reflections, shimmer, contracting wind crests and expanding swimmer wakes, type-3 vegetation/trees, three mammal gaits, landing/flying/capturable birds, atmospheric skies, type-3 rain/lightning, source-shaped indexed EPOC/SQC/compass and smoothed environmental visor data, low-gravity jumping, hold-to-thrust jetpack flight, and capsule ascent |
| Resize the game | Live iGUI window with centered 8:5 nearest-neighbour aspect-fit scaling; validated dimensions persist across clean restarts |
| Save / load | A valid `CURRENT.LIN` resumes automatically at startup; verified saves refresh `CURRENT.BAK`, and a present-but-malformed primary visibly recovers from that last-known-good copy while a deliberately missing primary starts clean. Global F6/F7 checkpoints work in the ship and on settled surfaces, retain target/player state plus the local fine-approach and parked-world state, landing and settled-capsule coordinates, window dimensions, presentation, F2 visual preferences, original PFS preferences and navigation heading, diagnostics, soundtrack, internal light, navigation devices, capture progress, power, lithium, collector, pending-rescue state, and a UTC timestamp for closed-game evolution, and show visible success/failure feedback; v1 through v14 port saves remain loadable and the exact original CURRENT.BIN codec remains available as a component |
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

### Native map-edge and complete capsule-return regression

On 2026-08-12 a debugger reproduced the black/disappearing surface as an access
violation in the terrain renderer: a descending z loop crossed map-edge zero
under an unsigned comparison and formed an invalid height-map index. Signed
terrain bounds and bounded eye-height reads kept the exact fixture alive for 24
seconds. A separate input trace exposed unsigned division of negative retained
velocities; after converting gravity, friction, slope, and capsule pull to
signed arithmetic, short and sustained S input no longer crossed the planet.

The final isolated production run held W away from the pod, held S back,
completed automatic sealing and ascent, stayed alive for 24 seconds, and exited
cleanly. Its checkpoint was in ship mode at `(0,0,-300)`, and the final captured
frame showed the normal gold Stardrifter interior rather than a black window.
The focused gameplay regression passed against the restored production source.

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
samples nonzero). A 36,000-frame headless soak passed on 2026-08-11: 488 s wall
(8.1 min, 73.8 FPS), dzat/pwr progressed, 4/8 framebuffer samples nonzero, and a
clean exit with deterministic output (sha256
f439fb1d6e3bf02e6ebc9ace4f4620e4b60850b714042d1b9eec79b9483c51ed).
The release-duration run on 2026-08-12 completed exactly 600,000 integrated
frames in 8,125.55 seconds (2 h 15 min 25.55 s, 73.84 FPS). It advanced dzat,
reduced live power from 30,000 to 27,097, retained 4/8 nonzero framebuffer
samples, wrote the exact 96-byte terminal record, and exited cleanly. The
telemetry SHA-256 is
`df088206c4c2ff97f502b137733df82b9b746a56f70caee1cf97afdf7307edf7`.

### Native GOES PRIF smoke

On 2026-08-11 a temporary exact-product entry point loaded the shipped
`STARMAP.BIN` and `GUIDE.BIN`, copied `PRIF SURICRASIA:1..2` into the normal
GOES command buffer, and called the real parser. The compiled executable exited
normally and created `GDOUTPUT.TXT` at 457 bytes with SHA-256
`31fec7d78405964d3a1814f9d07dfba106ad00926e881945ae4914909cd18d99`.
The output contained the planet subject header and exactly the first two
SURICRASIA records in the shared 72-column PRI layout. The temporary entry point
was then removed and the ordinary interactive production executable rebuilt.

### Native GOES X queue smoke

On 2026-08-11 a temporary exact-product entry point submitted `X FIRST SIGNAL`
and `X SECOND SIGNAL` through the normal GOES parser. The first command created
`X.TXT` with the exact 12 ASCII bytes `FIRST SIGNAL`; because that active slot
existed, the second created `XBUFF.TXT` with the exact 13 bytes `SECOND SIGNAL`.
The smoke then destroyed the active file as an Xnice consumer would and
submitted bare `X`. The executable exited normally with `SECOND SIGNAL` promoted
to `X.TXT` and no remaining `XBUFF.TXT`. The temporary entry point and generated
files were removed, and the interactive production executable was rebuilt.

### Native touchdown and retained-movement smoke

On 2026-08-11 the production executable resumed the approached opening system
in optional 60-Hz mode. Four human-cadence L events completed fine approach,
opened the physical landing selector, confirmed the site, and began the normal
visible capsule descent. Before the fix, both the current build and the prior
committed executable exited with `0xc0000005` on the first settled terrain
frame. A bounded trace localized the failure after background, local sun, and
water rendering but before the first landed far-terrain tile.

The cause was the presentation-only transition from the last airborne sample
to the first settled walking pose. Settlement now invalidates that sample. The
same production sequence completed touchdown, remained alive for twelve
seconds, accepted a two-second W hold, and stayed responsive for a further five
seconds. The process was then stopped by the harness, the real version-11 save
was restored, and all trace code and files were removed. The focused regression
also pins the original retained forward/lateral motion, friction, slope replay,
tiredness, and radial surface limits.

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

### Native 60-Hz autonomous-pose trace

The former interpolation boundary was after render, which proved only that
late player input could be smoothed. A disposable full-game build forced the
real roof lift in F5 mode and recorded the render-only Y coordinate after
interpolation on each of twelve native iGUI frames. The result was
`0, -21, -42, -70, -90, -111, -139, -159, -180, -207, -227, -247`: every frame
advanced monotonically, including the intermediate positions between source
simulation ticks. The same pre-simulation capture now admits capsule descent
and ascent when `landed` is clear but capsule state remains active. The trace
hook was removed and the normal production executable rebuilt afterward.

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
  save/load, FPS, presentation rate, music, visual effects, Flight control,
  Onboard devices, Preferences, and clean quit, and Enter activates the selected
  action
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
- Face the first right-wall computer and press Enter: focus the physical GOES
  command screen; Enter submits the command and returns to movement
- G: open the large accessible GOES view from anywhere inside the Stardrifter
- Type `HELP` in GOES: print the original seven-row resident-module directory
- Type `SAVE` or `LOAD` in GOES: write/read `CURRENT.LIN`
- Type `NEXT` in GOES: select the next source-generated star in the local
  729-sector navigation cube and begin a real Vimana transit from the current position
- Type `NEW` in GOES: replace the resumed checkpoint with a fresh opening
  flight; presentation mode, soundtrack preference, and starmap names remain
- Type `STAR X Y Z` in GOES: target exact integer coordinates from a starmap
- Type `NAME STAR LABEL` or `NAME PLANET LABEL` in GOES: add the current
  target or selected body to the persistent local starmap (labels are up to
  20 characters; duplicate identities and labels are rejected visibly)
- Type `PRI name[:X..Y]` in GOES: export the selected Galactic Guide records
  to `GUIDE-PRINT.TXT` beside the executable, in the original 72-column printer
  layout
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
- Direct R and 5 render the source `screen()` geometry at world z=0: four
  controls at c=-64..-45, four 27-character commands across the top row, and
  three information rows. Turn toward the forward windows to see the plane.
  The centre gaze uses the source half-distance march and exact control/command
  bounds; the selected slot receives a physical frame and one left-click runs it
- The third physical control opens Preferences. Its four command slots restore
  auto screen sleep, reversed gaze-side navigation steering, auto-hidden versus
  persistent menu rows, and the source's polarized/depolarized Stardrifter hull
- The GAME menu's Onboard devices, Flight control, and Preferences entries open
  the same actions as resize-aware clickable rows. Pointer coordinates are converted
  through the live 320x200 aspect fit, the hovered row turns white, and a held
  button cannot repeat a command across presentation frames. These accessible
  rows remain transparent over the live cabin rather than opening a black page
- The surface HUD shows approximate `POD` range, an `F/L/B/R` direction toward
  it relative to your current view, captured `BIRDS`, and the `CTRL:STALK` and
  `R@POD` reminders; an out-of-range R press reports `RETURN TO CAPSULE`
- F2: open visual effects; while open, T toggles passive HUD text, F cycles
  flare-reflection modes, and B toggles the default/seamless visor border
- Page Up/Page Down: open/close the animated visor
- X: close onboard control/data pages and return to the unobstructed view
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

- **Interior-light flicker**: the reported intermittent Stardrifter light pop
  traced to an invented `condition=1` center-pixel test. The original
  `alogena()` call passes `condition=0`; removing the test stops dark hull
  pixels from switching the fixture flare on and off. Surface sun flares are
  separate original calls and retain their real center-occlusion condition.
  The focused gameplay regression and production build pass.
- **Wall computers**: the original position-and-facing test now selects all
  three right-wall stations, including their individual illuminated selector
  bars. A targeted production-window smoke focused the first station, submitted
  `NEXT`, returned to the ship, and displayed `VIMANA TARGET SET`. A compact
  readable GOES prompt now sits on the physical first face while temporary
  power/FCS/body HUD rows are suppressed around any selected wall computer.
  The third face starts planetary approach, opens the live coordinate selector
  over its generated orbital display at STANDBY, and lands with Enter. The
  second GOES output face retains command output with source-equivalent line,
  page, and end scrolling.
- **Surface frame**: a valid cabin-to-console-to-landing run reproduced the
  reported bright stair-stepped perimeter. The source clips its world to a
  306x180 view and leaves the outer DOS page cleared; the port had instead
  filled that guard band with `sky_brightness`, which is nearly white on the
  opening surface palette. The live background first preserves a clean cleared
  source-sized guard band without changing palette index 255 or the authentic
  polygon rasterizer, then the completed frame applies the original default
  `surrounding()` graded visor after terrain and weather. A second complete
  landing confirmed the white and jagged perimeter is gone.
- **Surface presentation**: every accepted landable class now has a distinct terrain arm: lunar crater fields (type 1), thick-atmosphere plateaus (2), four habitable biomes (type 3), corrugated boulder worlds (4), thin-atmosphere eroded/permafrost terrain (5), striated frozen shelves (7), and milky quartz worlds (8). These join the generated day/night sky palette, diffuse shading, textures, crevasses, rocks, capsule/beacon, historical ruins, calm-water and ice reflections, wind crests, swimmer wakes, vegetation, trees, mammals, capturable birds, the original type-2 dense-atmosphere grayscale smoothing, and the original type-3 storm gates. Raininess 2+ can flash the surface palette; raininess above 3 submits wind-slanted foreground rain sticks. Storm density retains the source 50-stick floor but caps accumulated extras at 174 sticks to protect presentation. The offsets-map panorama now uses NIV+'s exact pitch/yaw cursor formula through a fixed-buffer direct specialization and caches the complete indexed sky until the view changes. Landed terrain uses NIV+'s fully textured unit-tile mesh, depth-64 circle, source Manhattan gate, triangle facing test, and quadrant-dependent painter order; the former 8/32-tile mesh and late ruins overlay were removed because they produced moving walls and erased detail. Wind and fauna state continue at 18.206 Hz in both presentation modes, while rain positions refresh at presentation cadence. Reflections retain the source terrain-only half-scan pass and are suppressed during incoming wind waves. The current faithful lunar benchmark is 9 FPS, so 60 FPS remains active optimization work rather than a claimed result.
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
  source's squared approach, close orbit/transfer, and squared departure path
  for the original two-minute visible phase. Its complete external hull is drawn
  between the near and far cupola passes from `other_vehicle_at()`, followed by
  all four source-positioned, hull-occluded exterior halogen flares.
  A production-window smoke resumed second 50 at a non-default player position,
  rendered 720 player-hull leaves and 140 cupola panels without mapper errors,
  remained responsive, exited cleanly, and saved the still-active rescue at
  second 56 in a valid version-15 checkpoint.
- **x87 across isocalls**: the lino win32 stub corrupts the x87 stack - fix is fninit+fldcw before each FP phase (documented in game.txt header)
- **Regression inventory**: all 24 `test_*.py` suites are registered; nsrun NSIN validation is fixed and test_geometry passes
- **Ground provenance boundary**: the type-3 texture matches the NIV+ capture exactly. Disassembly of the original `round_hill` proved that Borland compares its 16-bit `unsigned` loop bounds without clipping wrapped top/left hills; reproducing that rule reduced the post-landing captured heightmap residual from 39,710 to 1,752 bytes. The surviving RAM image was taken after the landed loop began reusing `p_surfacemap` as scratch, so it remains a capture-boundary XFAIL rather than being mislabeled as a generator mismatch.

## Native boundary

The full integrated build/flight/render/present loop has passed a 600,000-frame,
2 h 15 min unattended run. The longest native iGUI session remains the
189.8-second standalone-bundle playtest below because the GUI build requires a
logged-in desktop and real input. Extended combinations of interactive resize,
full-view transitions, repeated landings, rescue, and soundtrack playback are
representative native evidence rather than an exhaustively permuted matrix.

The automated iGUI capsule probe now targets a generated class-3 system and
selects a calm ocean reflection case. It completes atmospheric fall, 11
bounded rebounds, slope-checked touchdown, walking, seal, ascent, and
restoration to the Stardrifter. The latest end-to-end run completed in 13.7
seconds with `bad=0`, 720 hull leaves, and 54 reflected terrain tiles submitted
while incoming wind waves remained disabled. A prior class-2 run also verified
the general UTC daylight path at 54.782-degree exposure and retained sun
distance 48.06368. This bounded probe complements the production-window
journeys and representative gallery captures recorded below.

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

The 2026-08-11 parity follow-up restored the separate historical fragment that
recreates the photographed Suricrasian Cube at Ylastravenia body 3, LQ 018:060:
all 625 height-map points are raised to 127 and the source's two rows plus four
columns are marked for the close ruin-face pass. The production build and the
focused integrated-game regression pass with that landmark enabled.

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

The 2026-08-11 follow-up expanded iGUI's installed and visible menu capacities
from eight to twelve, then drove F10, ten Down keys, Enter, and Preferences row
6 in the production window. F6 wrote a valid 264-byte version-15 checkpoint with
PFS bits changed from 4 to 5, proving the formerly clipped Preferences service
was live through the real keyboard menu path.

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
exit, checkpoint resume, and the resumed exit all succeeded with code 0. The
separate 600,000-frame unattended run above supplies the multi-hour integrated
loop evidence that this native-input session intentionally does not.

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

### Physical planetary console and surface-frame correction

The source-positioned third wall station now owns the landing route. Enter
starts the existing local approach, waits for the authentic STANDBY state, then
opens a coordinate selector over the physical orbital display. Arrow keys
change longitude and latitude and Enter deploys the capsule. The global L path
remains available as an accessibility fallback.

Two isolated production-window journeys exercised that route without taking
desktop focus. Both reached the generated surface. The first proved that the
bright jagged perimeter was present on a valid landing, not only in a forced
checkpoint. Comparison with `TDPOLYGS.H` and an original Noctis surface frame
identified the 306x180 cleared guard band. The corrected build retains the
clean clipped view, adds the source final graded visor frame, leaves the
polygon sentinel untouched, and passes
`python tests/test_vhgame.py` before compiling to the production Windows PE.

### Physical Stardrifter computer text correction

The physical GOES font was present but invisible because every character quad
collapsed its two right vertices to one point and its two left vertices to a
second point. The resulting zero-area diagonal could not carry the mapped
32x36 glyph. The corrected order matches `digit_at()` exactly: right-bottom,
right-top, left-top, left-bottom. The original local `z=0`, beta-plus-90 camera
transform, 35.25-unit spacing, SUPPORTS.NCT font, and bright texture mode are
otherwise unchanged.

A deterministic checkpoint at `x=2800, y=0, z=-1935, beta=-90` put the real
production window directly in front of station zero. Enter focused the physical
console and buffered character input visibly produced `NEXT_` on its 3D face.
The same slice moved retained output and `LQ %03d:%03d` landing status back to
their source-shaped render paths instead of covering the ship with host-font
fallbacks. The production PE rebuilt successfully and the focused
`python tests/test_vhgame.py` regression passed.

The next physical-FCS smoke loaded a clean ship checkpoint, sent the real 5
input, and captured the class-0 yellow-star prose on the z=0 computer plane.
The page now composes the original local-target, remote-target, and
range/lithium lines from live game state into three bounded 108-character
buffers. The production build and focused integrated regression both passed.

The physical navigation smoke then used real foreground R and 6 key edges. It
displayed the source amplification/radiation sentence and disconnected tracking
state on the world-space plane. A finder-enabled checkpoint exercised the third
row through its distance calculation and showed the generated planet/minor-body
report. The 1.2 MB starmap's persistent system-label count completed before the
window appeared; measured startup-to-window time was 1,417 ms. The focused
regression and production build passed.

The physical cartography smoke used real foreground R and 8 key edges from the
same deterministic cabin position. The live rounded Parsis coordinate row
appeared on the z=0 plane. The page also composes the current EPOC with three
zero-padded triads and the source navigation sine/cosine heading pair; the
production build and focused regression passed.

The final physical-device smoke used real foreground R and 9 key edges. The
emergency page rendered the original no-emergency/help-not-sent report on the
world-space plane. Its active-rescue branch retains blank information rows, as
in the original. The focused regression and production build passed.

The data-sheet correction supersedes RC8's full-page host overlay. A clean
packaged production run used four real foreground I edges and captured the
remote, local, environment, and closed states. Each open state kept the live
Stardrifter visible around the original 101x50 logical-pixel card; the local
state displayed `LOCAL TARGET NOT SET`, and the final close animation removed
the card completely. The card uses the source palette indices, coordinates,
four-unit slide delta, reveal limit, and indexed 3x5 glyph path. The focused
integrated regression passed and the production PE rebuilt successfully.

A second packaged run exercised the restored source contents. The remote card
showed the opening target's 6.9280 radius, 1.970222 BAL M primary mass, and
7757 K / 7484 C / 13503 F surface temperatures. A forced reached-star save then
started a real local approach and displayed rotation triads, revolution EPOCs,
the generated body type, and radius. The environment card displayed live K/C/F
temperature plus identity-seeded lithium-ion and time-jittered radiation rows.
All three states stayed responsive and visible over the cabin. The focused
regression passed and the production PE rebuilt. A subsequent source-equivalence
pass restored the projected local-body eclipse calculation and corrected the
environment geometry to follow the live target-relative Stardrifter during fine
approach. A packaged foreground smoke kept the game responsive and showed the
environment values changing from the galactic position to the approached body's
actual local position.

### GOES CLR and WHERE production smoke

A disposable production directory copied the current PE and only its declared
runtime assets, then started without a checkpoint. Real foreground input opened
the accessible GOES editor, submitted `WHERE TITANIA`, reopened it, submitted
`CLR`, and exited naturally through Esc. The process returned code 0 and wrote
a valid 264-byte version-15 checkpoint. The camera walk used only to frame the
small physical output face overshot into the hull, so that screenshot is not
used as visual evidence. Runtime responsiveness is paired with the focused
catalogue regression: it decodes the production `STARMAP.BIN`, identifies
TITANIA as planet record `P01`, resolves FAIRY by the source identity rule,
proves the single-letter prefix `F` is ambiguous, and checks the restored code
against `WHERE.CPP` plus the resident `CLR` branch in `NOCTIS.CPP`.

### GOES PAR native regression

A disposable probe built from the shipping game source invoked resident PAR
after the ordinary target, catalogue, panel, and flight initialization. With
the opening Stardrifter position and `PAR ELRAINE:14`, its real 21-column output
tree contained `SUBJECT: STAR;`, `NAME: ELRAINE`, `X=3811056`, `Y=707894`, and
`Z=-212149`, then exited with code 0. An independent Python implementation of
the source sector base, signed folded multiply, star hash, and identity formula
found the same catalogue record and coordinates. The focused integrated check
also pins the relevant `PAR.CPP` branches and the G-overlay output rows.

The companion ST probe used the same live scan to submit `ST ELRAINE:14`.
Vimana's target became `(3811056,-707894,-212149)` and the output tree reported
`REM. TARGET DATA SENT` followed by `STARTING VIMANA DRIVE`. After placing the
probe at that reached star, `ST FENHOME:3` resolved its P03 catalogue identity,
selected zero-based body 2, set local approach active, and emitted the source's
two local-drive confirmation rows. Both operations completed in one native
process with exit code 0.

### GOES CAT and Galactic Guide regression

The shipping game loaded the original 4,063,588-byte `GUIDE.BIN`, validated
its header and all 48,376 fixed records, then ran `CAT SURICRASIA:1..2` in a
native probe. The retained output identified SURICRASIA as a planet and emitted
the `(1)` and `(2)` guide records with source-width wrapping, beginning
`SURICRASIA: ONE OF / THE MOST BEAUTIFUL / PLANETS IN THE WHOLE / GALAXY, AT`
and `LEAST FROM MY POINT / OF VIEW. NOBODY / SHOULD MISS THE / SURICRASIAN SKY AT`.
The process exited 0. A disposable package contained the identical 4,063,588
bytes and SHA-256 `e2d22f76383a8ac254f3bd6dd956faec69a47f080955b332cc0fbf8fb228b3b3`.

### GOES CAST persistence regression

A disposable production package ran `CAST SURICRASIA:CODEX WAS HERE`, closed
and reloaded its guide, then queried the appended record with CAT. GOES reported
`TRANSFER SUCCEDED`, `MESSAGE ACCEPTED`, and record `(48377)` containing
`CODEX WAS HERE`. The disposable `GUIDE.BIN` grew from 4,063,588 to 4,063,672
bytes, exactly one 84-byte record; its four-byte consolidated boundary remained
4,063,588. Reload reported 48,377 readable records and the native process exited
0. The tracked original guide was not modified.

### GOES REP correction and protection regression

A disposable production package ran four resident commands in one native
process: `CAST SURICRASIA:ORIGINAL NOTE`,
`REP SURICRASIA:193:CORRECTED NOTE`, `REP SURICRASIA:1:BAD`, and
`CAT SURICRASIA:193..193`. GOES reported `CORRECTION ACCEPTED.` for the local
record and `MESSAGE IS PROTECTED.` for consolidated record 1, then displayed
record `(193)` as `CORRECTED NOTE`. The guide grew by exactly one 84-byte CAST
record, its header stayed 4,063,588, and all 4,063,588 original bytes compared
identically with the tracked source asset.

### GOES DELE range and protection regression

A disposable native run cast SURICRASIA record 193, deleted `193..193`, tried
to delete protected record 1, then queried record 193 with CAT. The first DELE
reported `TOTAL RECORDS: 193`, `REMOVED: 1`, and `PROTECTED: 192`; the protected
pass reported 192 total, zero removed, and 192 protected. CAT no longer found
record 193. The appended record began with the exact `Removed:` tombstone while
the complete 4,063,588-byte consolidated prefix remained identical.

### GOES CLEAN two-database lifecycle regression

A disposable package appended one local `Removed:` record beyond STARMAP's
1,202,500-byte consolidated boundary, then used CAST and DELE to create the
same condition beyond GUIDE's 4,063,588-byte boundary. Resident CLEAN reported
37,579 starmap records with one removed and 48,377 guide records with one
removed. Both files returned byte-for-byte to their tracked original assets,
and the following CAT query confirmed the deleted guide record stayed absent.

### GOES REPAIR binary-oracle and native regression

The original `REPAIR.EXE` was run under DOS against two controlled archive
fixtures because no corresponding C++ module source survives in the reference
tree. The oracle proved that STARMAP ignores duplicate names and tombstones
only later identities inside the strict +/-0.00001 window. GUIDE tombstones a
later record only when both its approximate subject and all 76 comment bytes
match. Existing `Removed:` records remain for a later `CLEAN` pass.

The integrated kernels then ran through the full native game's real loaders
and file-write paths against disposable six-record archives. STARMAP and GUIDE
each changed records 1 and 2 to `Removed:`, retained record 0 as the first copy,
and left the existing tombstone at record 5 unchanged. The source build and
focused integration regression passed after restoring the normal production
entry path.

### GOES global SL and full scrollback regression

A production-derived native probe submitted bare `SL` through the resident
command parser and dumped the complete physical output history. It exited 0
with 7,586 retained rows: five source header/divider rows, all 7,579
non-removed `S` records in exact STARMAP file order, the closing divider, and
`STARS LISTING END.`. Every one of the 172,032 history cells matched an
independent decode of the tracked `STARMAP.BIN`; the unused tail was blank.
The comparison included `ALEXANDER_HAMILTON`, proving that a literal underscore
is now rendered as catalogue text rather than mistaken for the input cursor.

The ranged follow-up submitted `SL 14` from the opening galactic position. A
production-derived native run completed the same 20.8-million-candidate search
in 5,076 bounded advance calls and emitted exactly nineteen rows. The two hits
were source-ordered ELRAINE at `3811056,707894,-212149`, `$D=35.30 L.Y.`, then
ONIMACMAROOS at `3973200,721255,-448030`, `$D=39.47 L.Y.`. Headers, per-hit
dividers, coordinates, rounded distances, closing divider, and end marker all
matched an independent `SL.CPP` sector model. Production uses a larger measured
65,536-candidate frame batch while retaining the same results and Escape path.

### GOES DL dependency-tree regression

A production-derived native probe submitted `DL ELRAINE:14` from the opening
galactic position. Its exact nine retained rows were `DEPENDENCIES LISTING:`,
the source divider, `SUBJECT: STAR;`, `NAME: ELRAINE`, another divider,
`*ELRAINE`, the last-child tree row `[03&FENHOME`, a closing divider, and
`PLANETS LISTING END.`. The process exited 0 after restoring target
`(3979984,-43407,-43984)` and selected body index 1. The first run caught that
DL's shared divider workspace was uninitialized when DL was the first GOES
command; the corrected run proves all three required divider rows. The focused
integration check pins `DL.CPP`'s generator, planet/moon ordering, note-count,
range, and restore paths.

### GOES OUTBOX packet regression

A production-derived native probe added one disposable in-memory catalogue
record and one disposable Guide record beyond the original consolidated
boundaries, then submitted `OUTBOX` through the real resident parser. GOES
reported one outgoing label and one outgoing comment and produced a 132-byte
`OUTBOX.ZIP`. Its bytes were exactly `STARMAP_`, the original first 32-byte
catalogue record, `GUIDE___`, and the original first 84-byte Guide record used
as disposable payloads. Both payload comparisons were byte-for-byte equal,
the process exited 0, and the tracked `STARMAP.BIN` and `GUIDE.BIN` were never
written.

### GOES INBOX merge and idempotence regression

A native probe ran against disposable copies of both production databases.
Each copy first received two local records: one matching the incoming packet
and one unrelated record that had to survive. The 132-byte `INBOX.ZIP` carried
one label and one Guide note in the exact OUTBOX framing. Resident `INBOX`
reported one imported label and one imported comment, advanced the consolidated
boundaries from 1,202,500 to 1,202,532 and from 4,063,588 to 4,063,672, placed
the incoming records at those former boundaries, discarded their matching
local copies, and retained both unrelated local records after the new
boundaries. A second process imported the unchanged packet and reported zero
new records; both file sizes and boundaries remained unchanged. Neither
tracked production database participated in the run.

### Numbered in-game snapshot regression

The production executable was launched through its real iGUI host, allowed to
complete a gameplay frame, and sent the original M command. It created
`GALLERY\00000001.BMP` at exactly 256,054 bytes. Independent header parsing
reported `BM`, pixel offset 54, a 40-byte DIB, 320x200 dimensions, one plane,
32 bits per pixel, no compression, and a 256,000-byte pixel block. The captured
Stardrifter view contained 35 distinct colors and 60,814 non-black pixels, and
visual inspection confirmed correct orientation, HUD composition, and live
geometry. The first probe deliberately exposed an input-before-first-frame
race; the shipping path now guards that state.

### Original F1 About-page regression

The production executable received a physical F1 key-down/up pair through its
real Windows/iGUI event path. After the page composed, the resident M command
captured it as a complete 320x200 Gallery image. Visual inspection confirmed
the five source bounds, palette bands, title and credits, space-key branch,
release footer, correct orientation, and the previously missing B, J, K, W, X,
Z, comma, parentheses, asterisk, slash, and question-mark glyph shapes. The
current-port control card remains separately available on F9 and `?`.

### Surface fixed-step cruise regression

An isolated production package resumed a cloned version-11 landed checkpoint,
leaving the real save and databases untouched. Sending 9 through the Windows
character path advanced the player 20,880 world units in 1.6 seconds. Sending
9 again cancelled the selected source speed; two later F6 checkpoints 1.6
seconds apart retained identical X/Z coordinates. The process exited and its
temporary 32 MB package was removed.

### Surface panorama regression

The same isolated landed-package method sent N through the production Windows
character path. The game wrote a numbered 732,854-byte BMP with `BM`, pixel
offset 54, 916x200 dimensions, 32 bits per pixel, and a 732,800-byte image
block. Visual inspection confirmed a coherent three-panel planetary horizon
and the center-panel data treatment. The clean exit checkpoint retained the
starting heading exactly at zero; the temporary package was removed and the
captured panorama was promoted to `screenshots/planet-panorama.png`.

### HUD brightness regression

An isolated production package captured the opening frame at default
`surlight` 16, received six minus characters at human cadence, and captured a
second complete frame at the source minimum of 10. The same outer-frame pixel
changed from RGB 124,108,56 to RGB 64,52,28; both BMPs were exactly 256,054
bytes. The temporary package and process were removed afterward.

### Original F3 moviemaker regression

An isolated production package received F3 through the real Windows/iGUI key
path and displayed the source-shaped lower-visor moviemaker page over the live
Stardrifter. Enter began deck 001, P paused at frame 33, P resumed, and Enter
stopped after 50 frames. Files `00000001.BMP` through `00000050.BMP` were all
exactly 256,054 bytes; no incomplete file remained. A second physical-key run
held Ctrl with numeric-keypad plus and visibly selected movie deck 002,
covering the host path that does not reliably emit an ASCII plus character.

### Surface mouse walk and Delete snapshot regression

A disposable version-11 surface checkpoint was loaded by the production iGUI
executable. Holding the real left mouse button over the game image for 650 ms,
then sending F6, changed the persisted X/Z position by 5,844/-2,364 terrain
units while retaining settled surface mode. Physical Delete then wrote exactly
one raw `00000001.BMP` at 256,054 bytes. Replacing the former 200 row writes
with one in-memory pixel-block write reduced measured Delete-to-complete time
from several seconds to 514 ms. The process and isolated package were removed.

### Exact class-5 lithium collection regression

An isolated production package resumed two units from a generated class-5
star with zero lithium, 18,000 power, and its collector active. This distance
makes the identity-seeded draw lose to `125/dsd`, directly exercising the
source's minimum-yield branch. After 60 original-rate frames the ship reported
class 5, calibrated arrival, 20,000 power, 720 valid hull leaves, and zero bad
leaves. The temporary process and package were removed.
