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
