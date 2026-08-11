# Noctis IV L.in.oleum port -- development history

This document is the public, chronological account of how the playable port
was built, what each major phase established, which regressions were found in
the integrated game, and what remains. It complements `PLAYTEST.md`, which is
the detailed evidence log, and `PORTPLAN.md`, which is the technical source of
truth and remaining-work ledger.

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
the source `5\FLIGHTCTR R\DEVICES ... X\SCREEN OFF` layout with F2 substituted
for the desktop port's preferences key. The temporary host-font power, capsule,
FCS, and body rows no longer obscure the world. Resource and body details remain
on explicit data pages, FCS status already uses the original 3D digit path, and
X now clears onboard pages as advertised by the visor.
Version 13 expands `CURRENT.LIN` to 192 bytes for these preferences while
retaining explicit readers and defaults for versions 1 through 12.

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
- GitHub Actions verifies the protected source, runs the focused integrated
  regression, and assembles the versioned production payload and assets.
  Version tags additionally produce a ZIP, checksum, and GitHub Release. The
  historical GUI-subsystem compiler exits in GitHub's noninteractive Windows
  service session, so the production PE is built locally with the pinned
  compiler and committed; CI does not misrepresent package assembly as a
  headless source build.

## Current state

The project is a playable Windows beta, not a claim of exact feature parity
with every Noctis IV screen. A normal journey can:

1. explore the Stardrifter interior and roof;
2. use ship devices and GOES;
3. target and fly to a generated star;
4. inspect and select generated planets and moons;
5. approach and choose a landing site;
6. descend, walk, observe weather/fauna, and return in the capsule;
7. manage power/lithium and request rescue;
8. save, quit, recover a damaged checkpoint, and resume.

The main remaining release-hardening item is a multi-hour interactive session
covering repeated resize/full-view transitions, many landings, and extended
audio playback. Linux runtime audio remains unavailable because the historical
Linux PCM layer is a stub. See `PLAYTEST.md` for the precise evidence and open
coverage rather than treating this overview as a test report.

## Licence and authorization record

Noctis IV and Noctis-derived port material are distributed under the original
WTOF Public License in `LICENSE.htm`. On 2026-08-09 the user reported Alessandro
Ghignola's authorization for this port to proceed and to include the manual
soundtrack, with the original gameplay preserved. The repository and release
retain Alessandro Ghignola's and Ryan J. Bury's original credits and do not
replace either copyright notice with an invented licence.
