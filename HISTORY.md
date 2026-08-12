# Noctis IV L.in.oleum port -- development history

This document is the public, chronological account of how the playable port
was built, what each major phase established, which regressions were found in
the integrated game, and what remains. It complements `PLAYTEST.md`, which is
the detailed evidence log, and `PORTPLAN.md`, which is the technical
implementation and source-parity ledger.

## 2026-08-12 -- faithful terrain renderer correction

Live walking identified camera-relative black/white walls, floor gaps, and
crashes when backing away. The black pillar was isolated to the panorama even
with terrain disabled: the port had swapped the pitch/yaw cursor axes, omitted
NIV+'s 360-byte row stride, and omitted its -639 shift. Restoring the literal
source cursor removes the pillar across the quartz and lunar fixed scenes.

The remaining moving walls came from an invented 8/32-tile terrain mesh and a
late ruins overlay. Landed rendering now submits NIV+'s unit tiles through the
source depth-64 circle, triangle facing checks, fully textured path and
view-quadrant painter order. Legitimate distant crystals were separately
identified by live walking and retained. Source-safe Manhattan and wholly
off-screen polygon rejection are live; deferring the exact texture basis until
after screen rejection cut the hidden 60-frame checkpoint from 6,689 to 5,728
ms and render counts from 38,792,130 to 31,852,389. Inlining the exact bounded
surface-map byte reads then cut the steady 12-frame sample from 1,319 to 1,053
ms, raising the measured rate from 9 to 11 FPS. The 60-FPS optimization goal
remains open.

## 2026-08-12 -- source-lit Stardrifter and natural surface fauna

The final release audit passed all 24 registered suites. One Wave 5
documentation gate initially rejected six stale Unicode punctuation pins; the
underlying framebuffer/timing checks passed, the pins were corrected to the
documents' actual ASCII-safe text, and the complete Wave 5 rerun passed all 188
checks. A 600,000-frame integrated build/flight/render/present soak then ran for
8,125.55 seconds (2 h 15 min 25.55 s) at 73.84 FPS, advanced state and power,
retained nonzero framebuffer samples, and exited cleanly with its exact 96-byte
terminal telemetry.

The reproducible capture tool now derives the observer's galactic position by
inverting the source camera rotations, placing a selected star at a valid flare
distance without altering the renderer. The resulting production frame shows
the stellar corona and reflection ghosts through transparent Stardrifter
windows, with the hull's source lighting and occlusion intact.

The habitable-world capture was also moved off the initially selected ocean
pixel and away from map boundaries. Its fixed central dry cell contains a
naturally generated hopper, flying birds and trees under the local sun; no
fauna or scenery is injected for the screenshot. The capture tool records the
exact proven coordinates for that scene and for the two ruin examples.

The same audit exposed a misleading screenshot-tool failure: iGUI's native
window caption remains `vhgame` even after its custom chrome says `Noctis IV`,
so title polling waited on a condition that could never become true. Capture
readiness now samples the production framebuffer and rejects only the genuinely
black pre-initialization host. An authentic one-planet type-1 system named
IDEAL now supplies the lunar scene. A later fidelity review rejected the
temporary four-crater startup bound: type-1 generation again retains the
source's full zero-to-thirty height-crater field, uncapped texture craters and
uncapped dark lines. A radial profile cache removes repeated sqrt/sin/pow work
for equal integer radii without changing defined terrain bytes.

The manual Galactic Cartography target also corrects NIV+'s ten-character
Parsis editor oversight. A sign no longer consumes one of the ten coordinate
digits, and explicit signed 32-bit limits prevent wraparound.

## 2026-08-12 -- reproducible world gallery and coverage boundary

The production screenshot path now builds isolated version-15 compatibility
checkpoints at fixed known-dry cells, launches the shipping executable, captures
the native iGUI client, and cleans up the staged run. Keeping the capsule away
from the observer prevents its transparent shell from being mistaken for a
terrain grid. The resulting gallery records multiple planet classes, a local
sun with vegetation/fauna, marked historical ruin silhouettes, and an elevated
view along the source 25-by-25 Suricrasian Cube wall.

The focused integrated gameplay regression passed in full. A new coverage
ledger distinguishes those automated checks from native visual/input sessions
and names the representative procedural and native-timing boundaries. During
recovery, an obsolete hourly scheduled Codex task was found launching
concurrent builds and edits in this checkout; its worker was stopped and the
task disabled.

## 2026-08-12 -- stable map-edge traversal and signed surface motion

A native debugger trace found that the disappearing or black surface frame was
an access violation in far-terrain traversal, not a capsule or Stardrifter
colour failure. At a map edge, a descending z loop compared its first negative
index as unsigned, wrapped past zero, and eventually sampled outside the height
map. Both descending terrain passes now use signed lower-bound comparisons, and
the four live eye-height samples use bounded direct map reads.

The same signedness audit fixed surface gravity, backward/lateral friction,
slope motion, and capsule centring. Linoleum's apostrophe division is unsigned;
using it on a negative velocity had turned a brief backward step into a
planet-scale launch. Negative movement now decays in the intended direction,
ordinary low-gravity jumps remain airborne without corrupting the floor, and
capsule re-entry pulls toward the pod from every side.

An isolated production run walked away with W, returned with S, completed the
capsule ascent, and remained alive for 24 seconds. It saved ship mode at
`(0,0,-300)` and ended on a visible gold Stardrifter frame rather than black.
The focused integrated gameplay regression passes, and the restored production
executable is 520,858 bytes.

## 2026-08-11 -- grounded capsule recovery and final surface landmark parity

Surface input had one cross-mode error with outsized consequences: its common
cleanup path always applied the Stardrifter's interior boundary clamp. During
capsule descent or an interrupted surface checkpoint this replaced planetary
x/z coordinates with a ship corner, placing the pod or walker below unrelated
terrain. Ship-only clamping now runs only in ship mode, and an idle airborne
surface checkpoint deterministically settles at its persisted pod.

The capsule now retains the source's signed shell placement, mapped transparent
panels, structural line modes, local aperture and beacon. Walking away arms
recovery; spherical re-entry opens nearby panels and pulls the player inward.
Seal/ascent completion is queued to a clean top-level frame, while a wall-clock
accumulator preserves the original 18.206-Hz timing even when surface rendering
cannot sustain 60 presentations per second. A DOS scan-code movement smoke
stayed grounded, and an isolated complete ascent returned to ship mode, saved
`(0,0,-300)`, and exited cleanly.

The ship visual audit followed `vehicle()` and `polycupola()` through the
original C++: both cupola passes, flare mode 2, color index 64, and the dynamic
stellar palette band agree. The tested gold dome is the correct result for the
nearby warm class-0 star. Native iGUI resizing also scaled a live Stardrifter
from 642x426 to 962x626; apparent duplicate windows were stale direct-display
pixels left by force-killed diagnostics, not additional native hosts.

The historical-surface audit found one genuine omission outside the capsule:
the separate Suricrasian Cube restoration fragment. Suricrasia at LQ 018:060
now receives the exact 25x25 maximum-height plateau and marked wall rows and
columns from `NOCTIS-1.CPP`, alongside the six existing ruin styles, trees,
mammals/hoppers, and birds. That checkpoint built at 515,110 bytes and passed
the focused integrated gameplay regression.

## 2026-08-11 -- gradual surface leveling and safe capsule exits

F5 presentation now meters its unchanged 18.206-Hz simulation against the
normalized wall clock. Slow presentation frames therefore carry their elapsed
time forward instead of making the game simulation run in slow motion, while
focus and suspend gaps are discarded rather than replayed as a burst.

Surface pulse telemetry now includes the original twice-per-second variation:
the game reseeds Noctis IV+'s fast generator from secs/2, draws the two
fast_flandom() terms, and applies their eight-point difference around the
tiredness-derived heart rate before the source one-percent HUD smoothing.

Close surface rocks no longer stop after one reduced tetrahedron. They now
restore Noctis IV+'s fivefold near scale, full density-selected group, shrinking
successive stones, and cdown-weighted centre drift while retaining the distant
single-triangle level of detail.

Suricrasia's photographed historical Cube is again present specifically at
LQ 018:060: its 25-by-25 maximum-height plateau and selected northern and side
ruin faces feed the ordinary close-range ruin renderer.

Tree-class objects on terrain above -15,000 units now take Noctis IV+'s
cespuglio() path instead of incorrectly becoming full trees. The restored
bushes collapse to distant foliage at depth three and use the source 3,000-unit
scale, .75 reduction, .15 width, two-faced limbs, randomized terminal leaves,
and depth-selected one-to-four-way branching nearby.

Grass no longer uses one identical crossed placeholder at every distance.
ciuffo() now disappears at depth four, becomes a greenmush-style randomized
speckle mass at depth three, and restores the source three-, four-, and
six-face one-to-eight-way blade density at depths two, one, and zero.

Walking within 1,200 vertical units of the ground now restores Noctis IV+'s
`user_alfa /= 1 + fabs(step) * 0.000064` camera behavior. Because the port's
surface coordinates are eightfold and its visible pitch is integral, a
retained remainder carries sub-degree decay between source ticks. Looking up
or down therefore returns gradually toward the horizon while walking instead
of staying tilted forever or snapping level one degree per frame.

Every native close path also collapses an active capsule descent or recovery
to a deterministic settled checkpoint before saving. Esc, Alt+F4, the GAME
menu, and iGUI's red close button can no longer persist transient capsule state
that the checkpoint format deliberately does not encode.

Completed ascent now defers the surface-to-Stardrifter renderer switch until
the next top-level frame boundary. The capsule physics stack therefore finishes
entirely in surface mode instead of leaving one presentation frame half terrain
and half ship, which was the transition crash exposed during live testing.

The focused gameplay regression passes and the production executable rebuilds
successfully at 514,586 bytes.

## 2026-08-11 -- terrain-dependent surface mouse walking

Held left-click walking now follows `NOCTIS-1.CPP`'s terrain-dependent pace
instead of applying one universal impulse. The original 50, 75, 125, and 150
source-unit steps become 400, 600, 1000, and 1200 in the port's established
eightfold surface coordinate scale. Sea-level ocean/desert, ordinary ground,
non-habitable flats, and habitable ice therefore feel distinct again while
keyboard walking, cruise, momentum, friction, and capsule recovery keep their
existing source ordering.

The focused integrated regression pins each source branch and translated
constant. The 513,938-byte production build completed successfully and stayed
responsive after loading an isolated landed checkpoint; the real save was not
used or changed.

The frame boundary also repairs the otherwise impossible state produced by an
older or interrupted checkpoint that says surface mode but retains neither a
settled walker nor active capsule physics. Such a resume now settles at the
saved pod position before input or rendering instead of opening on an idle
airborne transition.

## 2026-08-11 -- source-equivalent surface air control

Surface movement now distinguishes an ordinary jump from active jetpack
flight as `NOCTIS-1.CPP` does. A normal jump retains its takeoff heading and
restores the pre-input forward/lateral velocities, while an armed jetpack
accepts steering and updates the movement heading from the live view. Fixed
digit cruise remains additive because the source snapshots velocity after
adding that automatic step.

The port-specific `-1200` thrust cap and airborne 750,000-unit exploration
radius are gone. Held Space supplies the original repeated `-50` impulse, L
adds the original `+400` descent impulse, and the final 300 units above terrain
use the source near-ground gravity spring. The distinct 200-unit `jumping`
threshold now controls slope resistance and jetpack shutdown without forcing
the camera prematurely onto the terrain plane.

The integrated regression passes and the production executable compiles. An
isolated v15 checkpoint loaded the real generated surface at
`(1638400, -8792, 1638400)`. The legacy iGUI host rejected both posted and
hardware-style synthetic keys, so the live jump/jet arc remains a short manual
confirmation rather than an automated claim.

## 2026-08-11 -- focus-safe native window presentation

The resizable iGUI host no longer advances or publishes a client frame while
its cooperative display is inactive. Resize callbacks are state-free, and the
normal presenter hands completed frames to iGUI through `Update Area` instead
of issuing a competing direct `RETRACE`. This removes the re-entrant raster and
display-transition path that produced a flat brown client area or an access
violation when the window lost focus during capsule descent.

The production executable was rebuilt and packaged in isolation. An unchanged
native smoke moved and resized the window and performed six minimize/restore
cycles. The earlier executable lost its window before the final capture; the
rebuilt executable remained alive and its final frame contained 649 distinct
sampled colours, with the Stardrifter still visibly rendered.

## 2026-08-11 -- source-equivalent capsule aperture and recovery

The settled capsule now makes the same lower and upper `polycupola` calls as
the moving capsule in `NOCTIS-1.CPP`, with the original globes-map texture
window and flare 4. Its panels therefore remain visible after touchdown and
open locally around the walker instead of leaving an inert shell.

Surface recovery now follows the original interaction rather than requiring a
port-specific key: walking beyond the true three-dimensional 1,600-unit pod
sphere arms recovery, and walking back inside automatically opens nearby
panels and pulls each signed position delta inward by one eighth. R remains an
accessible fallback. The seal and ascent now advance once per original
18.206-Hz simulation frame, preserving the 32-frame closure and 250-frame
return cutoff that had been compressed by the port's 32-step batch.

A native production smoke showed the textured shell opening locally and the
process remaining alive. The legacy iGUI host rejected synthetic movement
messages, so exact automatic walk-away/re-entry remains a short human
confirmation rather than an automated visual claim.

## 2026-08-11 -- source-equivalent surface momentum and safe touchdown

Surface WASD, held left-click walking, and digit cruise originally moved the
player immediately and discarded velocity at the end of each input sample.
The integrated loop now follows `NOCTIS-1.CPP`'s retained `step`, `shift`, and
`directional_beta` ordering. It applies lateral and forward movement through a
shared heading, uses the original 1/1.5 lateral and 1/1.25 forward ground
friction, replays steep uphill motion after the source gravity-based reduction,
accumulates tiredness from the retained forward speed, and restores the
1,500,000-unit landed and 750,000-unit airborne radial exploration bounds.

The first native landing smoke exposed an older transition crash that also
reproduced from the previous committed executable. In optional 60-Hz mode, a
single presentation frame could settle the capsule and then interpolate the
new walking camera from the preceding airborne sample. That sample was valid
for the broad descent mesh but could address outside the landed LOD grid,
causing an access violation before the first settled terrain tile. Capsule
settlement now invalidates the presentation sample, so the first walking frame
starts at the authoritative tile-centre pose. The same live landing sequence
then completed, accepted two seconds of forward input, and remained responsive.

## 2026-08-11 -- hosted tagged prereleases

The release path no longer waits indefinitely for hardware that the public
repository does not have. A pushed `v*` tag now runs the focused integrated
regression and protected-source check, verifies the checked-in i386 PE, builds
the standalone ZIP on a GitHub-hosted Windows runner, uploads its checksum and
explicit provenance record, and publishes a GitHub prerelease. Each downstream
job depends on the preceding job, so a test, validation, or packaging failure
prevents publication.

The GUI-subsystem L.in.oleum compiler boundary remains visible rather than
being papered over: the release provenance says that the versioned executable
was compiled locally before tagging. Exact clean source rebuilding remains a
separate manually dispatched workflow for a dedicated logged-in `lino-gui`
runner. No such runner is currently registered, but that no longer blocks tag
publication.

## 2026-08-11 -- source-build CI/CD path

Hosted CI and real releases were separated. Pull requests and master pushes
continue to verify protected sources, run the focused gameplay regression, and
assemble a snapshot from the committed PE. A tag or authorized manual dispatch
now targets an interactive `lino-gui` Windows runner, removes stale outputs,
compiles the checked-out source, validates the fresh i386 PE, and emits a hash
provenance record. The source machine has read-only repository access; an
ephemeral hosted job alone receives permission to publish the tagged release.
The workflow is checked in, while its first run awaits registration of the
dedicated desktop runner described in `CI_RELEASES.md`.

## 2026-08-11 -- historical GOES PRIF output

The resident HELP directory listed PRIF even though the recovered NIV+ source
and module bundle contained no PRIF implementation. The surviving Noctis IV
[manual](https://mooses.nl/nice/docs/miscdocs/noctis_iv_manual.html) supplies
the missing contract: PRIF accepts the same object and optional record range as
PRI, but writes the output to `GDOUTPUT.TXT`. The integrated command now shares
PRI's source-compatible lookup, one-based range selection, continuous record
stream, and 72-column word wrapping while selecting that historical destination.
PRI remains available as the port's practical printer substitute and continues
to write `GUIDE-PRINT.TXT`.

A temporary exact-product entry point submitted `PRIF SURICRASIA:1..2` through
the real command parser after loading the shipped starmap and guide. The native
executable exited cleanly and produced a 457-byte `GDOUTPUT.TXT` containing the
planet heading, exactly the first two Guide records, divider, and end marker.

## 2026-08-11 -- Xnice bridge and IMPORTGD boundary

The preserved [NICE Release 9 source archive](https://mooses.nl/nice/old/nice-src-r9.zip)
finally identifies the last two unexplained HELP entries. `X.CPP` is the text
file bridge for the optional Xnice Windows companion: its first message occupies
`X.TXT`, later messages form a line queue in `XBUFF.TXT`, and bare `X` promotes
the oldest waiting line when the companion removes the active file. That FIFO
protocol is now integrated directly into GOES, with a 64 KiB safety bound on an
externally enlarged buffer.

The same source proves that `IMPORTGD` is not a missing Noctis IV+ database
feature. It reads the old 84-byte `GUIDE.BIN` format, which this port already
uses natively, and converts selected records into NICE Release 9's unrelated
`STARMAP3.GD` format. The NIV+ package ships neither that destination database
nor the importer module. The resident command now explains this boundary and
does not risk importing `GUIDE.BIN` into itself.

A native exact-product smoke submitted two X messages through the real command
parser. The first became `X.TXT`, the second became `XBUFF.TXT`; after removal
of the active file, bare `X` promoted `SECOND SIGNAL` and removed the exhausted
buffer. The temporary smoke entry point and generated bridge files were removed
before rebuilding production.

## 2026-08-11 -- complete 60-Hz pose interpolation

The optional F5 presenter previously interpolated only motion committed after
the render by player input. Flight, roof-lift, and capsule physics had already
advanced before the old snapshot, so those visible poses still repeated at
18.206 Hz even while the counter reported 60 FPS. Pose capture now happens
before every authoritative simulation step and the same presentation-only path
covers airborne capsule descent and recovery as well as ship and settled
surface movement. Simulation, persistence, collision, and source cadence remain
unchanged.

A native instrumented roof-lift run recorded twelve rendered Y positions:
`0, -21, -42, -70, -90, -111, -139, -159, -180, -207, -227, -247`.
The former path would have repeated each authoritative position until the next
18.206-Hz tick. The focused regression and restored production build pass.

## 2026-08-11 -- original GOES REPAIR utility

The last standalone database-maintenance command in the resident HELP roster
is integrated. Because this historical module shipped without C++ source, its
exact behavior was established by running `REPAIR.EXE` under DOS against
controlled binary fixtures. STARMAP keeps the first valid identity and marks
later identities inside the original strict +/-0.00001 window as `Removed:`;
duplicate names alone do not count. GUIDE requires that same subject match plus
an exact 76-byte comment match. The utility never compacts the files, preserves
the original `GARGABE` message, and asks the pilot to run `CLEAN` separately.

The integrated command uses bounded in-memory scans and one whole-image write
per changed database. A native full-game smoke loaded disposable six-record
files and produced exactly the expected tombstones at records 1 and 2 in both
archives while retaining the pre-existing tombstone at record 5. The normal
production executable was rebuilt afterward and the focused regression passed.

## 2026-08-11 -- resident GOES help

The integrated console gained the original `N_Help_3.asm` seven-row resident
module directory. `HELP` now routes through the same bounded output history as
the physical GOES screen and accessible G view, preserving all 140 source
display characters and the original module roster exactly.
The production executable rebuilt and the focused source-equivalence regression
passed.

## Starting point

The repository began with Alessandro Ghignola's L.in.oleum 1.14 tree and its
Windows runtime. The protected upstream files under `main/` were kept
byte-for-byte unchanged. Port-specific compiler work was made in a separate
copy and a separately named CPU pack, so the original compiler and instruction
pack remain available and verifiable through `PRISTINE.sha256`.

Noctis IV does not store a conventional galaxy database. Its stars, systems,
worlds, terrain, skies, and much of its simulation are reconstructed from
deterministic integer and floating-point streams. The first half of the port
therefore concentrated on proving those streams before they were connected to
a player-facing game.

## 2026-08-04 to 2026-08-06 -- deterministic foundation

### Wave 1: integer runtime and galaxy generation

- Reproduced the Borland `rand`, `srand`, and `random` behavior used by Noctis.
- Implemented the signed high/low multiply required by negative galactic
  sector coordinates.
- Ported the galaxy hash and checked generated stars against independent C and
  Python references across positive and negative sectors.
- Added an append-only `*%`/`*%'` split-multiply extension in a copied compiler
  and CPU pack. Existing instruction records remained byte-identical.

### Wave 2: catalogue decoding

- Reconstructed the fixed-width starmap record format and identity rules.
- Preserved the distinction between valid values, removed records, exponent
  zero, negative zero, infinities, NaNs, and out-of-range coordinates.
- Established the mutable local `STARMAP.BIN` catalogue used by GOES naming and
  browsing.

### Wave 3: floating-point compatibility

- Added x87-backed binary64 operations and the control-word boundaries needed
  to match the original 32-bit program.
- Accounted for L.in.oleum's unit-addressed memory and the Win32 runtime's x87
  behavior across system calls.
- Reproduced the conversion and truncation points that feed star, orbit, and
  terrain seeds.

### Wave 4: nearby-star generation

- Ported the local-sector search and star identity pipeline.
- Matched the reference near-star stream and connected it to the navigable
  universe rather than a static demonstration table.

### Wave 5: framebuffer and timing

- Established the indexed 320x200 framebuffer, palette operations, drawing
  primitives, and original 54.9254 ms simulation tick.
- Kept simulation time separate from presentation time, which later made the
  optional 60 FPS presenter possible without speeding up gameplay.

## 2026-08-06 to 2026-08-08 -- rendering and flight

### Wave 6: polygon pipeline

- Implemented projection, clipping, polygon rasterization, and texture mapping.
- Added sphere, starfield, model, and globe drawing paths.
- Adapted byte-oriented Noctis data to L.in.oleum's 32-bit unit-addressed
  memory without changing the protected toolchain sources.

### Wave 7: planetary surfaces and skies

- Ported the ten source terrain classes and their deterministic height and
  color generation.
- Added atmospheric sky generation, day/night exposure, clouds, weather,
  horizon detail, and the source-derived surface palette paths.
- Added type-specific terrain presentation including crater fields, plateaus,
  habitable biomes, corrugated rock, permafrost/erosion, frozen shelves, and
  quartz terrain.

### Wave 8: saves and game-state bridge

- Retained the original `CURRENT.BIN` codec as a verified component.
- Defined a versioned native checkpoint for the port so expanding integrated
  state could be saved without pretending to be the original binary layout.
- Connected flight, approach, landing, surface, and return state into one
  persistent journey.

### Wave 9: first integrated game

- Produced the first executable with live camera flight and generated 3D
  terrain.
- Moved from a set of subsystem demonstrations to one continuous program.
- Added per-frame interleaving and wider terrain presentation so the game
  remained responsive while rendering.

## 2026-08-08 to 2026-08-09 -- the Stardrifter and native GUI

### Wave 10: walkable Stardrifter

- Loaded and rendered the actual `VEHICLE.NCC` hull rather than a placeholder.
- Added the interior deck, roof, cupolas, glass, lighting, consoles, and a
  walkable first-person camera.
- Added the roof lift and the physical aperture connecting the interior and
  exterior.
- Built GOES into the ship: nearby and exact-coordinate targeting, transit,
  body selection, approach, landing, naming, and new-game control.
- Added the navigation, miscellaneous, cartography, and emergency device pages.

### Wave 11: resizable iGUI host

- Integrated the game into L.in.oleum's native iGUI window.
- Kept the authentic 320x200 logical renderer and nearest-neighbor scaled the
  completed frame into a resizable, aspect-fitted 8:5 viewport.
- Composed HUD, notices, GOES, FPS, and help into the same stable logical page
  before presentation.
- Made Esc, the red close button, and Alt+F4 converge on the same checkpoint
  and audio cleanup path.

## 2026-08-09 to 2026-08-10 -- playable journey completion

### Navigation and planetary systems

- Added generated system topology with planets, moons, ownership, retained
  orbital radii, eccentricity, orientation, and tilt.
- Added an animated orbital console view and selection of every generated body.
- Added fine approach to the selected body's actual standby state.
- Added a longitude/latitude landing-site selector so different locations on
  one world use their local globe, climate, daylight, weather, and scenario
  values.

### Capsule and surface exploration

- Added physical descent, gravity, rebounds, terrain-lip scanning, atmospheric
  drift, settling, seal, and ascent.
- Added first-person walking, a low-gravity jump, jetpack, capsule-range and
  bearing HUD, and safe return gating.
- Added terrain crevasses, rocks, ruins, sea level, water/ice reflections,
  wind crests, swimmer wakes, vegetation, trees, mammals, rain, lightning, and
  capturable birds.
- Added source-shaped surface telemetry: gravity, temperature, pressure, and
  movement-sensitive pulse.

### Ship resources and rescue

- Added usable power, lithium, stellar collection, offline checkpoint
  evolution, and the partial reserve-cell behavior.
- Added the depleted-ship rescue sequence with a visible approaching second
  Stardrifter and lithium transfer.

### Soundtrack and controls

- Added Ryan J. Bury's manual soundtrack as authorized project content,
  pre-rendered to the runtime's native stereo PCM representation.
- Kept silence available as the faithful original state through F8.
- Added the native GAME menu, complete in-game control card, keyboard and mouse
  look, and visible feedback for save/load and invalid actions.

## Release-candidate hardening

The integrated game exposed several bugs that subsystem checks could not show.
They were fixed in the running production path and then retained by focused
regressions.

### Stardrifter visibility and flicker

Symptom: the Stardrifter could be invisible on the first frame and flicker in
and out after movement.

Resolution: the GUI presentation path now publishes a complete stable frame,
and the ship camera/projection cache is synchronized with the visible camera
state. The initial production frame and subsequent movement retain the complete
hull instead of alternating between incomplete render states.

### Spatial wall-computer restoration

The first integrated port drew three right-wall computer faces but activated
GOES through an unrelated full-screen shortcut. A source-equivalence pass found
the original `active_screen` rule in `NOCTIS.CPP`: x greater than 2,580, z from
-1,560 through -3,930 in three 810-unit stations, while looking toward the wall
between -135 and -45 degrees. The production game now uses that geometry,
illuminates the matching selector below each face, and lets Enter focus physical
GOES at station zero. G and the GAME menu retain the large accessible console.

A targeted window smoke submitted `NEXT` through the physical station and
received `VIMANA TARGET SET`. A readable compact prompt was then integrated on
the physical first face and temporary HUD rows were suppressed while any wall
station is selected. The third station now starts local approach, opens the
live landing-coordinate selector over the orbital display at STANDBY, and
deploys the capsule with Enter. The second GOES output face now retains the
same source-format command history and line, page, and end scrolling as the
original station.

The same session reproduced the reported bright, stair-stepped surface border,
first from a forced checkpoint and then through a valid physical-console
landing. The renderer was correct: `TDPOLYGS.H` deliberately clips the world to
x=5..311 and y=10..190. The port incorrectly prefilled the surrounding guard
band with `sky_brightness`, which maps near white on this surface palette.
Restoring a cleared index-zero guard band removed both the white halo and its
ragged edge without recoloring palette index 255 or changing polygon fill.

### Lift suction, wobble, and failure to release

Symptom: pressing Up could pull the player toward the lift center from outside
the aperture, trap them there, and oscillate instead of delivering them cleanly
to the deck or roof.

Resolution: E maps the original DOS Up event while leaving all four arrows
available for looking. A later source-equivalence pass removed the invented
center activation gate and roof-return state machine. The original direct
lift event, automatic `distance + step < 1100` descent, velocity ramps, camera
pitch, player movement, endpoint clamps, forward friction, and movement/render/
restraint order now form one path. The desktop ascent impulse is calibrated to
`-70`: twelve visible rise steps give the panels time to clear and finish 1,827
units from the aperture center, while the adjacent slower impulses add another
source carry frame and overshoot farther. Roof descent retains the source `+75`.

The pass also found that an attempted signedness fix had interpreted Linoleum's
operators backward. Apostrophe-prefixed operators are unsigned. Restoring the
signed comparisons and signed pitch arithmetic prevented negative lift state
from taking unsigned branches. The cupola keeps its fixed support grid and
raises only glass panels within the original 1,000-unit local radius, capped at
600 units. The 60-Hz presenter applies center restraint only on simulation
ticks, matching the original 18.206-Hz loop.

### Incorrect 60 FPS mode

Symptom: the high-frame-rate mode reported roughly 30 FPS and felt choppier
than the original cadence.

Resolution: a duplicate wait in the presentation loop was removed and render
work was reduced through stable-frame composition and cache reuse. Gameplay
simulation remains at 18.206 Hz. The original 18.206 FPS presentation is the
default, and F5 explicitly opts into the higher presentation rate.

### Capsule placement and checkpoint recovery

- Version 11 checkpoints retain exact settled capsule coordinates so a resumed
  surface journey cannot restore the player away from the pod.
- Older landed checkpoints migrate by anchoring the capsule at the saved walker
  position, avoiding an unrecoverable legacy save.
- A save is verified before the previous checkpoint becomes `CURRENT.BAK`.
- Loading falls back to the backup only when a primary exists but is invalid;
  a deliberately absent primary still begins a clean game.
- Failed candidates do not partially mutate live state. Recovery is reported
  onscreen as `CHECKPOINT RECOVERED FROM BACKUP`.

### Terrain and landing corrections

- Restored the habitable type-3 terrain path after a regression made its
  presentation diverge.
- Replaced an approximate capsule support check with the complete source-shaped
  slope scan around the pod footprint.
- Preserved exact selected landing coordinates through generation and reload.

### Interior halogen stability

An earlier source-equivalence pass incorrectly applied `condition=1` center
occlusion to the Stardrifter's `alogena()` flare. The actual original call in
`NOCTIS.CPP` passes `condition=0`; the invented pixel test made the light switch
off whenever its center crossed dark hull geometry and caused the reported
flicker. That test is now removed from the halogen path. Its original 90-spoke
additive flare and fixture color clamp at index 100 remain intact.

### Source surface visor frame

Clearing the planetary guard band removed the reported white sawtooth, but it
left a plain black rectangle that was only an intermediate repair. The original
finishes every planetary frame with `surrounding()`. The live port now performs
its default ten-row and ten-column graded frame after terrain and weather,
including dense type-2 atmospheres. Later polygon work can no longer dirty the
edge, and the intended Noctis visor treatment replaces the black workaround.

### High-rate Stardrifter pose interpolation

The 60 Hz presenter previously repeated each ordinary 18.206 Hz ship pose,
which made a correct FPS counter look almost as stepped as original mode. Ship
position, pitch, and shortest-path yaw now interpolate between committed source
ticks for rendering only. The authoritative pose is restored before input,
collision, save, and the next simulation step, so Noctis movement timing is not
changed. Settled surface walking uses the same render-only path; X/Z/pitch wave
feedback produced by the interpolated render is measured, the live pose is
restored, and those effects are applied exactly once. Capsule descent and
ascent remain on authoritative source poses.

### Source-positioned surface sun

Planetary daylight previously generated the correct sky palette but omitted
the visible local sun. The surface renderer now restores the original
`planetary_main` path before terrain: latitude and terminator exposure rotate
the active sun into view, the nearer dawn or dusk terminator selects its side,
and atmosphere selects the original radius and corona values. Night and rain
at 2.5 or above suppress it, while worlds owned by a class-10 companion use
that companion's radius rather than the primary star's.

Multiple systems now also restore the original secondary-sun branch. The port
selects the class-10 companion nearest the landed world, swaps the primary and
secondary roles when that world belongs to a companion, derives a separate
terminator and latitude offset for the second observer, and uses its stricter
2.0 rain cutoff. Sun angles and coordinates retain the source's binary32
assignment boundaries before projection.

The later surface pass now restores `lens_flares_for()` for both suns. The
primary retains its class exclusions, class-11 phase gate, 1.2 rain cutoff,
and 10-to-1000-radius distance window; the secondary has its own 2.1 rain
cutoff. Unlike the interior halogen, these original calls do use center-pixel
occlusion after terrain. Resolved close stars also advance their globe only by
the source's class-specific spin; ordinary classes no longer rotate once per
presentation frame.

### Source visual-effects settings

F2 now restores the original visual-effects card. Its T control hides or shows
passive HUD text, F cycles visor-only, forced, and disabled lens reflections,
and B switches between the default rectangular visor frame and the source's
tapered seamless edge. The flare setting deliberately governs the three
secondary reflections while retaining the central sunburst, matching
`lens_flares_for()` rather than treating the menu wording as a new renderer.
Page Up and Page Down now drive the original `-5`/`+5` visor motion across
both Stardrifter and surface frames. Visor-only reflections follow the saved
closed state instead of behaving like a second spelling of always-off.
Surface frames also regain `surrounding()`'s 28-character N/E/S/W strip with
its nine-degree scroll and four corner lamps. The lamps use the source's 4x4
resting geometry and expand to the bright 5x5 state during jetpack thrust.
The adjacent SQC line reports the selected landing longitude/latitude and the
walker's live 16,384-unit terrain square with `alphavalue()`-style unpadded
signed decimals.
The shared prefix now also restores `EPOC 6011 + seconds/1e9` and the original
three zero-padded sub-billion triads. UTC is refreshed once per authentic
18.206 Hz simulation tick, so the display advances without depending on the
optional presentation rate.
The lower surface line now follows `surrounding()` as well: gravity,
temperature, pressure, and pulse are smoothed by the original 0.25, 0.05,
0.02, and 0.01 factors and rendered through the indexed 3x5 alphabet at y=192.
The former oversized GUI-host telemetry row is gone from ordinary play; the
same live values remain available on the environment data page.
The ship side now appends a compact, indexed command strip to EPOC, following
the source `5\FLIGHTCTR R\DEVICES ... X\SCREEN OFF` layout. F2 remains a separate
desktop visual-effects card. The temporary host-font power, capsule,
FCS, and body rows no longer obscure the world. Resource and body details remain
on explicit data pages, FCS status already uses the original 3D digit path, and
X now clears onboard pages as advertised by the visor.
Version 13 expands `CURRENT.LIN` to 192 bytes for these preferences while
retaining explicit readers and defaults for versions 1 through 12.

Version 14 expands the record to 256 bytes and preserves the separate local
fine-approach integrator and parked-world position. A surface save can now return
the capsule to the same waiting Stardrifter after a restart instead of forgetting
the completed approach. Explicit readers remain available for versions 1 through
13.

The physical Preferences control now opens Noctis's actual PFS page instead of
redirecting to the port's F2 visual card. Its four source commands drive the
18.206 Hz screen-sleep countdown, reversed gaze-side navigation steering,
auto-hidden menu rows, and the polarized/depolarized Stardrifter subdivision.
Version 15 expands `CURRENT.LIN` to 264 bytes to retain these four settings and
the navigation heading, with explicit readers for versions 1 through 14.
The native GAME menu now mirrors those same four commands in its resize-aware
accessibility layer. Closing that layer, Flight control, or Onboard devices also
releases the physical computer immediately instead of leaving its gaze controls
disabled until another direct keyboard open.
The host menu's installed and on-screen capacities are now twelve rather than
eight. The old limit silently discarded Flight control, Onboard devices,
Preferences, and Save and quit even though their datascript entries existed.

The emergency helper Stardrifter now renders its complete external VEHICLE hull
between the source-ordered near and far cupola passes. The earlier port drew two
cupolas without the ship body even though `other_vehicle_at()` explicitly draws
the vehicle model during the full two-minute rescue orbit. Its four exterior
halogens now follow the same source positions, three-degree spoke cadence,
hull-occlusion test, and visor reflection preference as the original.

### Clickable onboard controls

The complete FCS and onboard-device pages no longer require memorizing their
keyboard slots. Their existing four source-shaped command rows now track the
pointer through the resizable 320x200 aspect fit, highlight the hovered command,
and accept one action per left-button edge. The target browser maps its final
four visible rows to the same 6-9 command slots, while each page's bottom hint
retains the original back or close action. Keyboard controls remain unchanged.
A production-window smoke opened the miscellaneous page from the onboard root
and changed its live internal-light row from ON to OFF with two mouse clicks.
The device and FCS command text also stopped blanking the cabin with a black
host rectangle. It remained transparent over the live Stardrifter as an
intermediate step toward the original physical layout.

### Physical onboard computer

Direct R and 5 now build the live device/FCS command set on the source's z=0
computer plane. The implementation retains `screen()`'s four 50-unit control
rows at c=-64, four 27-character top-row command slots beginning at c=-44,
-17, 10, and 37, three information rows, `digit_at(...,-6,-16,4,...)` glyph
bounds, and the player's actual camera perspective. A clean production-window
capture loaded the original `(0,0,-500)` distance facing the plane and showed
only the command slots inside its real frustum rather than a fixed GUI page.

The native GAME menu now offers Flight control and Onboard devices as explicit
accessibility routes. Those entries retain the previously verified resizable
click rows and hover feedback; direct source keys no longer cover the physical
screen with them.

The physical screen is interactive as well. Its centre gaze repeats the
original half-distance advance toward z=0, including the 25-unit hit tolerance,
3,000-unit side cutoff, `(-2040,-1320)` control band, 50-unit control rows, and
810-unit command slots. A four-stick world-space frame marks the selected slot.
In a production-window smoke aimed ten degrees upward from `(0,0,-500)`, that
frame enclosed command 2 and one left-click changed the root's `miscellaneous`
slot into the live internal-light and target-data commands.

The flight-control plane now restores the information produced by the original
`fcs()` routine. Its first row names a selected planet or moon with Noctis's
ordinal spelling and full planet description, its second row reports the live
remote star class and full class description, and its third row shows elapsed
kilodyams and remaining lithium. A production-window smoke opened the physical
5 page and rendered the opening class-0 yellow-star description directly on the
world-space plane; the focused integrated regression also pins every live input
and all three output buffers.

The adjacent navigation-instruments page now reports the original live
amplification and high-radiation policy, tracking connection and mode, and
planet-finder result instead of a static heading. The finder performs the
source 20,000-unit distance test, reports planets and minor bodies from the
generated system, and counts matching persistent body identities in
`STARMAP.BIN`. Real foreground R then 6 input displayed the radiation and
disconnected-tracking rows; a finder-enabled checkpoint also displayed the
system body report. Startup still reached the production window in 1.4 seconds
with the 1.2 MB working catalogue.

The physical galactic-cartography page no longer spends its information area
on a static title. It now assembles the original EPOC and three comma-separated
time triads, rounded X/-Y/Z Parsis coordinates, and navigation heading/pitch
pair from live state. Real foreground R then 8 input displayed the changing
coordinate row on the source plane, and the production build plus focused
regression passed.

The emergency branch now completes the physical device tree. In the ordinary
quiet state it displays Noctis's `NOTE: there are no emergencies at the moment.`
and `help request not sent.` rows; an active rescue leaves the information area
blank as the original `gburst` branch does. Real foreground R then 9 input
rendered the quiet report, and the focused regression passed.

The miscellaneous data sheets then moved off the port-specific full-screen
black GUI page and back into Noctis's compact indexed HUD card. The shipping
path now retains the source card coordinates, palette bands, four-unit slide,
character reveal, and 3x5 glyph rendering while the Stardrifter remains visible
around it. A clean packaged run opened remote, local, and environment states
with real I-key edges, showed the original no-local-target state, slid closed,
and left the cabin unobstructed. A follow-up restored the card contents from
the same source routines: class-corrected remote mass, radius and temperature;
local rotation/revolution triads, type and radius; and external temperature,
lithium ions and radiation. In the opening system the live remote card showed
radius 6.9280, mass 1.970222 BAL M, and 7757 K / 7484 C / 13503 F, matching the
source equations. The environment calculation now follows the Stardrifter's
actual target-relative position during fine approach, analytically reproduces
the source's star-centred `watch()`/`xy()` projection at `dpp=200`, and applies
nearby-body eclipse to both external temperature and radiation. A packaged
foreground smoke exercised the galactic and approached-body paths without
losing responsiveness.

## GOES network restoration

The command face previously accepted only the port's direct flight, naming,
and checkpoint conveniences. The first original GOES Net slice now restores
the resident `CLR` branch from `run_goesnet_module()` and the complete lookup
behavior of `WHERE.CPP`. Queries scan the same 32-byte mutable starmap records
used by onboard naming, prefer a full name over ambiguous prefixes, list all
prefix candidates through the retained 21-column output tree, distinguish
stars and planets, and recover a planet's parent star from its encoded ordinal
and binary64 system identity. No DOS subprocess or parallel catalogue format
was introduced.

A disposable production-window run submitted `WHERE TITANIA` and `CLR` through
the real buffered GOES editor. The game remained responsive and saved a valid
264-byte version-15 checkpoint on its natural Esc exit. The focused regression
also decodes the shipped catalogue independently, confirms TITANIA is `P01`
and FAIRY is its parent, and pins the original source branches.

The next GOES slice restores `PAR.CPP`. A catalogue name, with optional
`:range`, is resolved with the same exact-name preference and planet-parent
identity rule as WHERE. PAR then centres the source-sized sector cube on the
live Stardrifter, regenerates candidate stars with Noctis's signed integer hash,
compares their binary64 identities within the original 0.00001 tolerance, and
reports X, -Y, Z. A disposable native probe resolved ELRAINE at range 14 to
`X=3811056`, `Y=707894`, `Z=-212149`, matching an independent implementation.
The accessible G console now shows its seven retained output rows, and the
GOES strings use Lino's underscore encoding so their intended spaces survive
compilation.

`ST.CPP` now consumes that same verified lookup and scan instead of requiring
players to retype PAR's numeric result into the port-only STAR command. A star
hit retargets live Vimana travel and prints the original remote-target status;
a planet hit is accepted only after its parent star has been reached, then
selects the encoded body ordinal and starts the existing local approach. The
native regression targeted ELRAINE, moved Vimana to its exact coordinates,
then targeted FENHOME P03 in that reached system and entered local drive with
body index 2.

The original Galactic Guide is now live data rather than dormant provenance.
The packaged `GUIDE.BIN` contains 48,376 validated 84-byte records. Resident
`CAT` resolves a starmap subject, accepts its original one-based `X..Y` range,
matches the guide's binary64 identity, and word-wraps each 76-byte message into
the physical 21-column output tree. The native probe's `CAT SURICRASIA:1..2`
result reproduced the first two guide blocks, including their `(1)` and `(2)`
headers, and the package check retained the source asset's exact SHA-256.

The companion `PRI.CPP` path now lives inside GOES as well. `PRI` shares CAT's
exact or unambiguous catalogue lookup and one-based record ranges, then writes
the selected Guide prose to `GUIDE-PRINT.TXT` in place of the DOS printer
device. The export retains the source heading, 72-underscore rules, padded
20-character subject label, continuous record stream, CRLF endings, and exact
72-column word-wrap decisions. A disposable native `PRI SURICRASIA:1..2` run
produced 457 bytes that matched an independent replay of the original routine
byte for byte; that run also caught and removed an early packed-line counter
collision before publication.

The companion `CAST.CPP` path now contributes persistent player notes to that
same database. The port keeps the original four-byte consolidated boundary
untouched and appends each local contribution as the source's binary64 subject
identity plus a zero-padded 76-byte message. Both the loader and packager
distinguish consolidated source records from bounded local additions. A native
disposable-package probe cast `CODEX WAS HERE` for SURICRASIA, reloaded the
84-byte-larger file as 48,377 records, and read the new record back through CAT.

Resident `REP` restores the correction side of that contribution workflow.
It accepts the source's `OBJECT:RECORD:NOTES` form, counts matching subject
records from one, and permits replacement only at or after the consolidated
boundary. A disposable native sequence cast SURICRASIA record 193, corrected
it to `CORRECTED NOTE`, rejected an attempted correction of protected record 1,
and read the corrected text back with CAT. The consolidated guide prefix
remained byte-for-byte identical throughout.

The resident `DELE` module now completes ranged removal of contributed Guide
records. It retains the original one-based subject numbering and summary,
writes `Removed:` only to local records, and treats the consolidated source
region as protected. CAT immediately ignores the tombstone just as the source
database tools do.

`CLEAN` restores the companion database maintenance pass for both STARMAP and
GUIDE. The port first corrected STARMAP's header semantics so player names are
appended beyond, rather than folded into, the consolidated boundary. CLEAN then
compacts complete in-memory images, adjusts only affected source boundaries,
rewrites each validated image once, and truncates it to the resulting size.

Bare `SL` restores the original global catalogue branch. It emits every
non-removed star record in file order, preserves all twenty padded label cells,
and retains the complete 7,586-row result in an expanded 8,192-row physical
GOES history. Separating the output terminator from the command cursor also
restored printable underscores in names such as `ALEXANDER_HAMILTON`.

The optional ranged `SL` branch then restored `SL.CPP`'s catalogue-ordered
procedural search and its X, -Y, Z, light-year, divider, range-fallback, and
interruption behavior. Unlike the DOS module's blocking loop, the hosted scan
advances a measured candidate batch per frame, preserving resize and repaint
responsiveness while Escape returns to play instead of closing the game.

The companion `DL` module now rebuilds a charted star's dependency tree from
the same procedural system generator used by flight. Named stars and planets,
or the current remote target with bare `DL`, receive the original planet/moon
branch characters and Galactic Guide note counts. Its potentially large range
scan advances in bounded frame batches and Escape cancels it without quitting.
The temporary system generation then restores the player's prior target and
selected body. A native range-14 query reproduced ELRAINE's charted P03
FENHOME tree exactly and exposed a first-command divider initialization defect,
which was corrected before publication.

GOES `OUTBOX` now makes the port's player-created catalogue data portable. It
uses the protected boundary stored at the start of each database to exclude all
shipped records, skips local tombstones, and writes the original packet framing
and record bytes to `OUTBOX.ZIP`. A native run with one disposable label and
one disposable Guide note produced the expected 132-byte packet: `STARMAP_`,
the exact 32-byte label, `GUIDE___`, and the exact 84-byte note. The command
also reports both exported counts on the physical GOES output tree.

The matching `INBOX` command completes the original Stardrifter archive
exchange loop. A received packet is fully checked for both framing markers,
record alignment, and bounded final sizes before either mutable database is
written. Incoming source duplicates are ignored; accepted records move into
the consolidated boundary, matching local copies are replaced, and unrelated
local additions are appended afterward. Unlike the DOS utility, a mid-write
failure can restore both still-loaded original images. A disposable native
merge imported one label and one note, kept one unrelated local entry in each
database, and made a repeated import a zero-change operation.

## Packaging and publication

- `play_noctis.ps1` is the supported source-tree launcher and fixes the runtime
  working directory before play.
- `package_noctis.ps1` builds a clean standalone folder, validates every
  runtime dependency, copies the player instructions and verbatim Noctis WPL,
  and generates `MANIFEST.sha256`.
- The public checkout includes the extended compiler, CPU pack, original
  starmap, GUI assets, model/map/font data, and soundtrack required to build and
  package without a second private source tree.
- Local saves, diagnostics, screenshots, and historical release-candidate
  folders are deliberately excluded from version control.
- GitHub-hosted Actions verifies protected source, runs the focused integrated
  regression, and assembles a non-publishing snapshot from the committed PE.
  Tags use `tagged-release.yml` to repeat validation, package the versioned PE,
  and publish its ZIP, checksum, and honest provenance record as a prerelease.
- `source-release.yml` is a separate manual clean-source rebuild. It requires
  the interactive self-hosted `lino-gui` desktop documented in
  `CI_RELEASES.md`, and does not block the normal tag publication path.

## 2026-08-11 -- About screen and numbered Gallery snapshots

F1 now opens the original `ShowAboutPage()` presentation independently of the
port-specific F9/`?` control card. The source's five framed regions, palette
indices, inverse-colour 3x5 HUD lettering, credits, ship/surface text branches,
Omega-drive notice, and release footer are composed into the logical game page
before scaling. The retained HUD font gained the remaining letter and
punctuation shapes required by the complete screen.

The original M and `*` snapshot path is resident again. It finds the next free
eight-digit name in `GALLERY`, captures the fully composed 320x200 logical game
page before host scaling, and writes an uncompressed 32-bit BMP in the source's
bottom-up row order. Existing captures are not overwritten. A readiness guard
also rejects input queued before the first complete frame instead of saving a
black startup page. B now restores the original raw variant by capturing the
current game image before the port-only overlays while sharing the same safe
numbering sequence.

The surface-only N/`/` and V/`.` panoramic paths now capture the original
three headings at 71-degree offsets and stitch the same 309/299/308-pixel
crops into a numbered 916x200 Gallery BMP. The middle panel carries the data
overlay only for N. In-memory assembly keeps the operation responsive and the
player's exact heading is restored afterward.

Surface digits now restore the original `fixed_step` cruise control. Digits 1
through 9 select 10 through 90 source units of automatic forward movement per
simulation tick, mapped into the port's terrain scale; the active digit or 0
stops it. Manual WASD movement remains additive and a new descent resets the
setting as a fresh original planetary session did.

Plus and minus now restore the original `surlight` control. Each buffered key
changes the shared ship/surface visor frame by one step within the source's
10 through 63 bounds. The same source-derived gradients and corner lamps react
immediately, without consuming those characters while GOES or an onboard page
owns text input.

The original F3 moviemaker is resident again. `ShowMovieSetup()` occupies its
source lower-visor bounds and exposes deck selection, capture interval, flash
treatment, start/stop, pause/resume, frame count, measured rate, and existing
deck warnings. Recording follows source gameplay ticks rather than the host's
optional presentation rate and writes raw 320x200 frames into numbered
`MOVIES\DDD` decks. The numeric keypad plus and minus paths are handled from
their physical keys so Ctrl deck selection remains reliable in the Windows
host. A native session recorded 50 complete consecutive BMPs, paused and
resumed at frame 33, and stopped without leaving a partial file.

Surface exploration again accepts the original held left mouse button as a
forward step, in addition to the port's WASD and fixed-speed controls. The hit
path is limited to the aspect-fitted game image and yields to chrome and active
overlays. Physical Delete also restores the source raw-snapshot alias on a
settled surface. During its native smoke the older Gallery writer exposed a
multi-second stall from 200 row-sized file calls, so numbered 320x200 captures
now assemble the identical bottom-up pixel block in memory and submit one
256,000-byte write. The final production run moved by held left-click and
completed the Delete capture in 514 ms.

## Current state

The project is a complete playable Windows port of the Noctis IV+ route. A
normal journey can:

1. explore the Stardrifter interior and roof;
2. use ship devices and GOES;
3. target and fly to a generated star;
4. inspect and select generated planets and moons;
5. approach and choose a landing site;
6. descend, walk, observe weather/fauna, and return in the capsule;
7. manage power/lithium and request rescue;
8. save, quit, recover a damaged checkpoint, and resume.

Automated, native-window, and long-duration evidence is recorded in
`PLAYTEST.md`; `TEST_COVERAGE.md` keeps the non-exhaustive procedural and native
timing boundaries explicit. Linux runtime audio remains unavailable because the
historical Linux PCM layer is a stub.

## Licence and authorization record

Noctis IV and Noctis-derived port material are distributed under the original
WTOF Public License in `LICENSE.htm`. On 2026-08-09 the user reported Alessandro
Ghignola's authorization for this port to proceed and to include the manual
soundtrack, with the original gameplay preserved. The repository and release
retain Alessandro Ghignola's and Ryan J. Bury's original credits and do not
replace either copyright notice with an invented licence.
