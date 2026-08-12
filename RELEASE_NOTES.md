# Noctis IV L.in.oleum port -- Windows release

This release completes the playable Windows route from the Stardrifter through
galactic flight, local approach, capsule descent, surface exploration, and
automatic capsule return. It also repairs the final capsule coordinate-space
and timing failures found during live play, restores the historical
Suricrasian Cube, and retains the source-equivalent ship, terrain, devices,
GOES modules, persistence, presentation, and soundtrack systems established in
the earlier betas.

The README gallery refresh is in progress. Corrected planet-class captures,
animals, trees, a distant whole-Cube view, and a close space-view planet remain
explicit deliverables; stale artifacted frames are not accepted as evidence.

Type-1 lunar landings retain the source's complete zero-to-thirty height-crater
field, uncapped texture-crater field, dark lines, rocks, mottling and airless
presentation. A radial profile cache reuses the identical float result for
pixels at equal integer squared radius, accelerating the authentic workload
without shrinking or removing terrain content.

Galactic Cartography's manual Parsis target now accepts ten coordinate digits
plus an optional minus sign. This corrects the original ten-character editor
limit while retaining signed 32-bit range checks, so the distant Feltyrion
region is reachable without wrapping a coordinate.

Landed terrain now uses NIV+'s fully textured unit-tile depth-64 mesh, source
triangle-facing test and view-quadrant painter order. The invented 8/32-tile
mesh and compensating late ruins pass were removed; they caused moving walls
and erased real terrain detail. The panorama cursor now follows NIV+'s exact
pitch/yaw formula, eliminating the camera-relative black pillar and floor gap.
An off-screen `polymap` rejection and the source Manhattan gate reduce only
work that cannot contribute pixels. Texture-basis construction now occurs
after that rejection, cutting the hidden lunar checkpoint from 38,792,130 to
31,852,389 render counts and from 6,689 to 5,728 ms for 60 frames. Specialized
bounded surface-map reads then reduced its steady 12-frame sample from 1,319
to 1,053 ms and raised the measured rate from 9 to 11 FPS. The 60-FPS
optimization target remains open.

The earlier release audit passed all 24 then-registered suites. The integrated
build/flight/render/present loop also completed 600,000 frames in 8,125.55
seconds (2 h 15 min 25.55 s) at 73.84 FPS, with advanced state and power,
nonzero framebuffer samples, exact terminal telemetry, and a clean exit. That
ship-mode soak predates the faithful landed renderer and is not evidence of
the current surface frame rate.

## What is playable

- Walk through the Stardrifter interior, use the roof lift, explore the roof,
  and operate the onboard devices.
- Use GOES to select a nearby generated star or enter exact coordinates.
- Fly through the deterministic Feltyrion galaxy and inspect generated systems.
- Select generated planets and moons, approach them, choose longitude/latitude,
  and land in the physical capsule.
- Walk generated surfaces with distinct terrain classes, skies, weather,
  source-positioned local suns, vegetation, animals, capturable birds, ruins,
  water/ice effects, jump, and jetpack behavior.
- Return to the capsule and Stardrifter, manage power and lithium, collect fuel,
  or request the complete two-minute rescue fly-by with a second lit
  Stardrifter.
- Stellar lithium collection now preserves the original class-5 minimum yield,
  class-6 distance failure, reached-target gate, collection during planetary
  approach, `+1` distance term, and continuously refreshed status feedback.
- Save and resume versioned checkpoints. Verified saves retain a backup and a
  damaged primary visibly recovers from the last-known-good copy.
- Resize the native iGUI window while the authentic 320x200 renderer remains
  nearest-neighbor scaled and aspect fitted.
- F5's optional 60-Hz presenter now interpolates simulation-driven flight,
  roof-lift, capsule descent/recovery, ordinary player poses, and surface
  mammal/bird translation, gait, wing articulation, ocean swell, player wakes,
  and class-specific close-star rotation while leaving gameplay at the original
  18.206-Hz cadence. Non-spinning star classes retain the source's separate
  clock-driven globe phase, and the physical orbital console no longer runs
  faster when F5 is active. Its interpolation phase follows measured scheduler
  time, eliminating the periodic catch-up step between uneven presentation gaps.
- Surface mammals no longer snap between four cardinal travel directions.
  Their source-seeded stop and turn decisions, species speed ranges,
  scale-dependent reaction, continuous heading, and sine/cosine movement are
  restored from `live_animal`.
- Surface birds now use `live_animal`'s continuous flight path as well, including
  its grounded, descent, low-altitude and high-altitude regimes, deterministic
  heading and altitude wander, and cautious-approach takeoff response.
- Wildlife RNG schedules now use NIV+'s raw 18 Hz tick. Mammal turn and stop
  decisions plus low-, mid-, and high-flight bird wandering no longer wait on
  an invented one-second quantization.
- Flying bird wings now use NIV+'s global six-tick and twenty-tick flap cycles;
  the port's invented per-bird phase offset is gone.
- Surface rain now reacts to the player's movement as well as atmospheric
  wind, restoring NIV+'s per-tick apparent streak direction.
- Storm drops now use the original backward-shifted rain camera and luminous
  line mode, with both states restored before subsequent rendering.
- Lightning restores NIV+'s raininess-scaled probability and variable palette
  intensity instead of using coarse probability buckets and one fixed blend.
- Lightning now activates on the source-ordered following tick and temporarily
  inverts the mapped sky source, restoring the original illuminated cloud flash
  without persisting the inverted panorama in the cache.
- Ground birds now fold both wing groups at the source's scale-dependent rate
  instead of sharing an oversized fixed-altitude closing ramp.
- Ocean-world birds use their sampled ground height as well as the biome when
  choosing between grounded and flight poses, restoring island behavior.
- Captured birds restore all five original trailing cords around the player.
- Those cords now apply the original short-lived drag to surface momentum while
  their capture counter relaxes.
- Wildlife range now includes vertical separation through the original 3D
  distance calculation. Mammals restore planetary skin mapping; close birds
  alternate the original textured and recursively remapped appearances, with
  depth sorting enabled at the source threshold.
- Out-of-range wildlife now re-enters around the player through the original
  live RNG continuation and complete 100,000-unit draw range instead of
  repeating a truncated fixed offset. Presentation-only F5 frames no longer
  mutate relocation state.
- Rare mammals generated on open-ocean biomes now use the original swimming
  silhouette and stroke: flattened body, hidden legs, raised pitch, and a
  smoothly presented half-second oscillation replace the terrestrial gait.
- Terrestrial mammal animation now follows NIV+'s shared half-second clock,
  exact species bounce amplitudes, full body/rear articulation, and
  source-indexed idle-tail selection instead of the port's per-animal wobble.
- Mammal posture now uses the original forward terrain sample and atan slope
  calculation, including its full 45-degree inclination range.
- The documented GOES `PRIF name[:X..Y]` module is live and writes its selected
  72-column Galactic Guide stream to the historical `GDOUTPUT.TXT` file.
- GOES `X text` restores the Release 9 Xnice file bridge, including active
  `X.TXT`, FIFO `XBUFF.TXT`, and bare-`X` promotion. `IMPORTGD` now explains why
  its NICE-only old-to-new database conversion does not apply to this build.
- Toggle Ryan J. Bury's manual soundtrack with F8; silence remains available.
- Save the completed 320x200 game view with M or `*`. Numbered BMP files are
  written to `GALLERY` without overwriting earlier captures.
- Open the original moviemaker with F3 and record numbered raw 320x200 frames
  into selectable `MOVIES\DDD` decks, with the source interval, flash, pause,
  resume, frame count, and rate controls.
- F1 restores the original framed Noctis IV+ About page with separate ship and
  surface text. F9 or `?` retains the accurate current-port control card.

## Important behavior in this build

- Descending terrain traversal now stops safely at map-edge zero instead of
  interpreting a negative tile index as unsigned and clearing or crashing the
  surface frame.
- Surface gravity, backward/lateral momentum, slope motion, and capsule
  centring use signed arithmetic. Backward input no longer launches the player
  across the planet, and re-entry pulls inward correctly from every side.
- Surface and capsule coordinates can no longer pass through the ship-interior
  clamp. Interrupted old checkpoints settle at the persisted pod rather than
  resuming underground.
- The settled pod is mapped and transparent, keeps the source structural line
  modes and sky beacon, opens locally as the player leaves/re-enters, seals for
  32 original ticks, and returns after the source 250-tick ascent.
- Capsule simulation now uses elapsed wall time at a fixed 18.206 Hz and hands
  back to the Stardrifter only at a clean top-level frame boundary.
- Ylastravenia body 3 at LQ 018:060 restores the source's separate 25x25
  Suricrasian Cube landmark and marked wall faces.
- Focus changes no longer let a re-entrant iGUI repaint corrupt the live game
  frame. The supported iGUI size control scales both ship and surface views.

- This is the first prerelease produced by the automated tagged GitHub path.
  GitHub reran the focused regression, verified the versioned i386 PE, built the
  standalone ZIP, and published its checksum and explicit build provenance.
- The authentic 18.206 FPS presentation is the default.
- F5 opts into the higher presentation rate; simulation remains 18.206 Hz in
  either presentation mode.
- Capsule settlement now resets the final airborne presentation sample before
  the landed LOD renderer starts. Optional 60-Hz mode no longer crashes on the
  first walking frame after a live descent.
- Surface walking now retains the original forward and lateral momentum,
  asymmetric ground friction, steep-uphill resistance, tiredness input, and
  circular landed/airborne exploration limits. WASD, held left-click, and digit
  cruise all feed that same source-ordered motion.
- F2 opens the source-equivalent visual-effects card. T toggles passive HUD
  text, F cycles visor-only/always-on/always-off flare reflections, and B
  selects the default or seamless visor border. These choices persist.
- Page Up and Page Down animate the source visor edge at its original five
  lines per simulation tick; visor-only reflections follow its closed state.
- Landed views restore the original 3x5 SQC location readout, scrolling compass
  strip, and four corner HUD lamps; jetpack thrust produces the bright flash.
- Ship and surface visors restore the live Noctis EPOC clock and its three
  zero-padded sub-billion second triads.
- The ship visor again carries the compact source command strip. Large temporary
  power, capsule, FCS, and body rows no longer cover ordinary gameplay; FCS stays
  on its original 3D HUD path, and X returns from onboard pages to the clear view.
- Landed gravity, temperature, pressure, and pulse now use the original indexed
  3x5 lower-visor line and source smoothing rates instead of an oversized host-font row.
- The Stardrifter is visible from the initial frame and remains stable during
  movement.
- The Stardrifter hull now uses the original live palette instead of a fixed
  cobalt tint. Selected-star color and distance, navigation heading, planetary
  eclipses, and the internal lamp's gradual 0-through-63 fade all affect its
  lighting at the authentic simulation cadence, without presentation-mode
  flicker.
- True emergency illumination is now separate from ordinary hull lighting.
  Depleting both power and lithium blacks the wall-console text, disconnects
  navigation, suppresses the normal halogen reflection, and enables only the
  source's intentional emergency flicker. Rescue transmission adds its exact
  recurring 63-tick signal and four-frame white hull pulse, while onboard reset
  restores systems through the original staged 150-step sequence.
- Approaching stars now cross the source's actual geometric detail thresholds:
  the luminous shell appears inside 100 stellar radii and the textured globe
  inside eight, independently of the autopilot's final arrival flag. From
  1,550 to 100 radii the selected target also gains the source's rising,
  three-pass light-emitting point and complete spread halo. Inside eight radii,
  its full 64,800-texel stellar surface cycles at the original source cadence.
- Close stars now recover the source's live distance response: globe detail
  uses the per-star seeded saturation floor, nearby stellar colors whiten with
  distance, and all six palette endpoints ease by one unit per source tick.
  The original `sqrt(...)+1` boundary arithmetic is retained.
- Space stars now restore the original pre-mask optical pass. Beyond six
  radii, eligible stellar classes produce the source's 60-spoke visor flare
  below 1,000 radii, including the rotating class-11 visibility gate. The
  exact four-row grayscale smoother then softens the space field before its
  conversion into stellar palette band 64.
- Generated companion stars now contribute their original flare as well as
  their corona when the Stardrifter lies between five and 1,000 companion
  radii. Their source float distance rounding and shared visor reflections are
  retained.
- Space frames now follow the original palette and draw order: luminous
  coronas are drawn first, the central space viewport moves into stellar band 64,
  resolved globes and planets follow, and the generated galaxy is submitted
  only after the Stardrifter. The source `sky(0x405C)` target gate therefore
  keeps stars behind the hull while allowing approach halos to brighten space.
- During Vimana flight, the central 182-row space viewport now retains and
  fades its prior low-six-bit intensities by eight instead of being cleared.
  Moving stars consequently leave the original short luminous trails.
- E directly starts the source lift event while inside the Stardrifter. Up
  remains a look control, and walking into the roof cupola opening starts the
  original automatic return. The calibrated ascent retains the source's
  forward momentum through the final roof frame, carries the player clear, and
  uses the same heading for the view and ride motion.
- Facing the first right-wall computer and pressing Enter focuses physical
  GOES. Command input and retained output use the original mapped 32x36 font
  directly on the wall faces. `HELP` restores the exact original seven-row
  resident module directory. The original resident `CLR` command clears the
  output tree, while `WHERE <catalogued name>` searches the mutable starmap,
  distinguishes stars from planets, reports ambiguous prefixes, and resolves
  a planet's parent star. Bare `SL` lists every non-removed star in source file
  order. Its 7,586 output rows fit in the expanded 8,192-row scrollback, and
  literal underscores in catalogue names remain visible. `SL <range>` runs
  the original centred procedural scan, reports matching stars with X, -Y, Z,
  and two-decimal light-year distance, and can be interrupted with Escape while
  the window remains responsive. `PAR <catalogued
  name>[:range]` now regenerates the
  original procedural sector cube and reports X, -Y, Z coordinates. The G
  shortcut includes the same seven retained output rows as the wall display.
  `ST <catalogued name>[:range]` now sends a resolved star to Vimana or begins
  local drive for a named planet belonging to the currently reached system.
  `DL <catalogued name>[:range]` now regenerates the requested system and lists
  its charted planets, moons, and Guide note counts in the original dependency
  tree. Bare `DL` examines the current remote target, and every query restores
  the player's prior generated system and selected body.
  `CAT <catalogued name>[:X..Y]` reads the original 48,376-record Galactic
  Guide with its source one-based ranges and 21-column word wrapping.
  `PRI <catalogued name>[:X..Y]` selects the same subject records and exports
  them beside the game as `GUIDE-PRINT.TXT`, preserving the original heading,
  padded subject label, continuous message stream, CRLF lines, and 72-column
  printer word wrapping.
  `CAST <catalogued name>:<notes>` appends a source-compatible 84-byte record
  after the consolidated guide boundary. Notes are limited to 76 characters,
  persist in `GUIDE.BIN`, and are readable by a later `CAT` command.
  `REP <catalogued name>:<record>:<notes>` corrects a selected local record
  while retaining the original module's protection for consolidated entries.
  `DELE <catalogued name>[:X..Y]` applies the original `Removed:` tombstone to
  ranged local entries and reports total, removed, and protected counts.
  `CLEAN` compacts tombstones from both mutable databases and preserves the
  consolidated source boundary separately from appended player data.
  `REPAIR` restores the original first-record-wins duplicate scan. It uses the
  source identity window for STARMAP and requires both that subject match and
  an exact 76-byte comment for GUIDE, then leaves compaction to `CLEAN`.
  `OUTBOX` exports only those live player additions to `OUTBOX.ZIP` using the
  original `STARMAP_` and `GUIDE___` packet framing, ready to copy to another
  Stardrifter installation.
  `INBOX` completes that exchange path. It validates a received `INBOX.ZIP`
  before writing, imports non-duplicate records into the consolidated archives,
  replaces matching local copies, retains unrelated local additions, and can
  restore both original database images if a write fails.
  The third station starts planetary approach and,
  after FCS reaches STANDBY, opens the physical longitude/latitude selector.
- Planetary views finish with the original default `surrounding()` visor
  frame. Its stable graded edge replaces both the incorrect bright sawtooth
  and the intermediate plain-black guard without changing polygon clipping.
- The Stardrifter's physical Preferences control restores the original PFS page:
  auto screen sleep, reversed navigation steering, auto-hidden menus, and the
  polarized/depolarized hull are functional rather than opening the F2 card.
  A resize-aware GAME-menu mirror exposes the same four commands and cleanly
  returns control to the physical computer when closed.
- The native GAME dropdown now installs and displays all twelve actions; its
  former eight-entry capacity silently clipped the final four menu commands.
- Emergency assistance now shows the complete second Stardrifter hull between
  its source-ordered near and far cupola passes throughout the two-minute orbit.
- Version 16 saves additionally retain the internal lamp's exact fade level,
  emergency illumination, rescue-signal phase, and staged reset progress.
  Versions 1 through 15 migrate without stranding the player or losing their
  established defaults.

## Run it

Extract the ZIP without removing individual files, then double-click
`Play Noctis IV.cmd`. The launcher keeps assets, `CURRENT.LIN`, `CURRENT.BAK`,
the mutable `STARMAP.BIN`, mutable `GUIDE.BIN`, and diagnostics in the
extracted game folder.

Useful controls:

- W/A/S/D: move; held left-click also walks forward on surfaces; right-drag or arrows: look
- E inside the Stardrifter: ascend; walk into the roof opening to return
- First wall panel + Enter: physical GOES; `NEXT`: choose/fly to a nearby star
- `SL` lists all known stars; `SL <range>` scans locally; Escape stops a scan
- `CAT`: read; `PRI`: text export; `CAST`: add; `REP`: correct; `DELE`: remove;
  `REPAIR`: find duplicates; `CLEAN`: compact
- `OUTBOX`: export player data; `INBOX`: import a received `INBOX.ZIP`
- Third wall panel + Enter: approach, select a landing site, and descend
- G and L: accessible GOES and landing fallbacks
- R: device back/close aboard ship; return in capsule on a surface
- F2: visual effects; Page Up/Down: visor; F4: FPS display; F5: higher presentation rate
- F6/F7: save/load; F8: music; M or `*`: numbered Gallery snapshot
- B, or surface Delete: raw Gallery snapshot without port display overlays
- F3: moviemaker; +/-: interval; Ctrl +/-: deck; F: flash; Enter/P: record/pause
- Surface N or `/`: 916x200 panorama; V or `.`: raw panorama
- Plus/minus: adjust the original HUD and visor-frame brightness
- F1: original About page; F9 or `?`: complete current-port control card
- Esc: save and quit

## Known limitations

- Windows is the supported packaged platform. The historical Linux runtime's
  PCM layer is a stub, so soundtrack support is Windows-only.
- The native L.in.oleum compiler requires a logged-in Windows desktop. Hosted
  GitHub Actions validate and package the committed executable; the separate
  source-build workflow needs a registered interactive `lino-gui` runner.

## Integrity and licence

The release includes `MANIFEST.sha256` for every file in the extracted bundle;
the GitHub release also supplies a checksum for the ZIP itself.

Noctis IV and Noctis-derived port material are distributed under the original
WTOF Public License included as `WPL.htm`, with Alessandro Ghignola's
authorization for this port and the condition that original gameplay be
preserved. Redistribution must remain free and comply with the included terms.
Original Noctis IV and L.in.oleum credits belong to Alessandro Ghignola;
manual/soundtrack portions are credited to Ryan J. Bury.

For the full development timeline and technical evidence, see `HISTORY.md` and
`PLAYTEST.md` in the source repository.
