# Port plan -- Noctis IV in L.in.oleum

Source of truth for what is done and what is next. The hourly heartbeat reads
this file. Update it when a wave completes; do not let it drift.

## Current completion target

Finish a complete, playable Noctis IV port first, then extend that foundation
toward Noctis IV+. Project authorization update reported by the user on
2026-08-09: Alex confirmed that this port may proceed and that the Noctis
manual soundtrack may be included. Music is therefore part of the completion
goal, with an in-game off control preserving the original silent experience.

## Standing rules

- Never launch `compiler.exe` directly. Build only via `lino_build.ps1`, which
  polls for artifacts and kills the GUI process.
- Never modify anything under `main/`. Every hash in `PRISTINE.sha256` must
  keep matching. The licence position depends on it.
- Publication is authorised under the original WPL while preserving Noctis IV's
  original gameplay and credits. Keep licence scope and provenance explicit.
- Verify claims by running things. A wave is not done because an agent said so.

## Lean check before any new wave

```powershell
python tests\run_all.py          # optional --deep release/historical audit
```
Routine work needs only the focused regression relevant to the change (with a verification
budget of about 10% of implementation effort), plus the relevant `PRISTINE.sha256` check.
Use the full roster as an explicit release/deep audit; if that audit fails, fix that
first -- a broken foundation makes every later result meaningless.

---

## Done

### Native GUI performance, landing safety, and Stardrifter lift
- Each completed 320x200 indexed render is palette-expanded into a stable
  logical RGB composition page. HUD, notices, GOES input, FPS, and the control
  card are drawn there before the completed page is nearest-neighbour expanded
  into the GUI backdrop. The completed backdrop is explicitly copied to the
  primary display and then retraced: iGUI can disable `Update Area` while
  preparing its control loop, which silently left the live window black even
  though the composed Stardrifter frame was complete. Desktop-duplication
  capture now shows the full hull on the first presented frame at 2x scale.
- The host now opens at 642x426, presenting the unchanged 320x200 framebuffer
  at a practical 2x size.  The real iGUI size/full-view controls retain centered
  8:5 aspect fitting through the configured 962x626 maximum, and the logical
  HUD/control-card composition follows that same transform instead of remaining
  as tiny host-resolution text.
- The native maximize, drag-resize, and restart paths have now been exercised
  rather than inferred from an externally forced window rectangle.  A 642x426
  host maximized to 962x626 and persisted it; a native drag produced 702x460,
  restart restored 702x460, right-drag look changed the saved view, and resized
  GOES both retargeted and appended one 32-byte name record.  At maximum size
  the same production loop measured 60.17 FPS in 60-Hz mode and 18.13 FPS in
  original mode.  If the legacy 962x626 exclusive display mode is unavailable,
  iGUI now restores the exact prior window position and dimensions instead of
  silently maximizing and overwriting the saved preference.  A successful
  exclusive session likewise returns to its pre-full-screen geometry, and an
  exit while exclusive persists that windowed geometry.
- Profiling showed that GUI presentation was about 1% of measured frame work;
  the dominant cost was repeated 729-sector star projection and trigonometric
  helper chains. Short-lived visible-star projection caching and lazy exact
  degree-table caching cut measured startup-frame render work by about 70%.
  The game starts in the original 18.206-FPS presentation mode while retaining
  that same simulation cadence; F5 opts into the 60-Hz presenter.
  Timer probes now clean the x87 boundary before each render phase so profiling
  cannot corrupt the floating-point camera state it is measuring.
- Landing now bounds-checks the selected body, visibly rejects non-landable
  types, labels accepted descent, and batches 32 unchanged source-physics
  steps per presented frame. Planetary far/middle terrain keeps the 64-tile
  horizon with 32/8-tile LOD while preserving an exact three-tile walking ring.
  Coarse triangles are flat shaded, texture mapping is limited to the nearest
  two depth bands, and the settled capsule retains both structural grids while
  its costly translucent fill remains on the animated descent/ascent pod.
- E maps the original DOS Up lift event while leaving all four arrows available
  for looking. Like the source event, it starts directly from inside the ship
  rather than passing through a port-invented center gate. The ascent and
  descent retain the source velocity ramps, pitch changes, middle-ascent push,
  and center restraint. The desktop ascent begins at a calibrated `-70`, which
  exposes twelve rise frames without the extra forward-carry frame caused by
  nearby slower values; roof descent retains the source `+75`. The return is:
  `distance + step < 1100` starts descent automatically when the player enters
  the cupola opening. The port-specific second-key and movement-threshold return
  state machine has been removed.
- The source's middle-ride `step=-pos_y`, descending half-velocity motion,
  endpoint clamps, movement friction, player controls, and movement/render/
  center-restraint order are retained. Signed arithmetic now follows the actual
  Linoleum operator rules; apostrophe-prefixed unsigned operators are not used
  for negative lift coordinates or pitch deltas. In 60-Hz presentation mode,
  the restraint still runs only on an 18.206-Hz simulation tick.
- The native iGUI GAME menu now exposes Controls, GOES, checkpoint save/load,
  FPS, 60/18-Hz presentation, soundtrack, and clean save-and-quit actions.
  Its F10/Up/Down/Enter path is fully keyboard-accessible; a production GUI
  run selected Save from the rendered dropdown and updated a valid 152-byte
  checkpoint before exit. Menu and function-key paths share the same action
  routines so their capsule-motion guards and player notices cannot diverge.
- Right-button dragging now supplies resize-normalized mouse look in both ship
  and surface modes while leaving unpressed motion and all chrome/menu regions
  to iGUI. A real 2x-host drag changed `(alpha,beta)` from `(0,180)` to
  `(-6,168)` without changing position. Negative deltas explicitly use signed
  division; the first integrated run caught and removed a `+44` pitch clamp
  caused by the unsigned operator.
- The camera's lazy integral-angle cache is explicitly cleared at startup;
  L.in.oleum workspace storage is uninitialised and previously produced a
  garbage first camera matrix, making the hull invisible or intermittent.
- The 60-FPS presenter uses a 16.667-ms deadline that waits when early and
  rebases when late.  It no longer feeds iGUI's retrace into the original
  skip-to-next-grid timer, which caused a second wait and an effective 30 FPS.
  A live executable smoke measures 60 FPS with 720 hull leaves and zero bad
  leaves; F5 retains the original 18.206-Hz presentation option.
  A loaded landed checkpoint in fast mode measures 60 FPS at native presentation
  and 59 FPS by the integer overlay after iGUI expands its own display to the
  configured 962x626 maximum.
  The full-size capture shows the generated surface correctly aspect-fitted
  and centered rather than left at 320x200.  Earlier high-20s/30-FPS surface
  measurements predate the current presenter and panorama cache.
- Settled surfaces expose an unobtrusive GUI-scaled pod range and captured-bird
  line, keeping the capsule-return condition discoverable after exploration.
  Pressing R outside the original 1,600-unit capsule boundary now reports
  `RETURN TO CAPSULE` instead of silently ignoring the request.
- I now cycles three full-page onboard data sheets shaped after the original
  miscellaneous-device display: remote star identity/class/system counts,
  selected planet-or-moon identity/type/radius/ownership/landability, and live
  ship or surface environment/resources. Mutable rows use dedicated bounded
  buffers, catalogue record tags are hidden from player labels, and the live
  FCS row dereferences its selected status string. The physical I-key table is
  retained alongside buffered ASCII so iGUI character-message timing cannot
  make the pages unreachable.
- Ship-mode R now opens the original miscellaneous-device page with its 6-9
  keyboard commands. Command 6 changes the live halogen fixture between the
  source's +1/-1 color states, suppresses its flare while off, and consumes one
  power unit per original 84-second interval; 7-9 select the three data sheets.
  The same R key retains capsule return on surfaces. Version-8 checkpoints
  persist the light state, and a production load/save round trip retained OFF
  as signed -1 in the new 156-byte record.
- Ship-mode R now first opens the complete four-branch onboard root. Navigation
  restores the real 9-to-14-sector field amplifier, a projected target-finder
  reticle, six tracking states with five source-distance holds, and mgloop's
  native 44x/1.5x anti-radiation stand-off. Device power advances only at the
  18.206-Hz simulation cadence. Cartography seeds the live GOES editor for
  star/body naming and manual coordinates, while an in-range browser walks the
  source-generated sector cache and shows signed X/Y/Z before explicit Vimana
  selection;
  emergency exposes system reset, rescue, lithium collection, and status clear.
  Version-9 checkpoints pack all navigation settings into the new 160-byte
  record and retain v1-v8 compatibility. The amplified 2,744-sector renderer
  remains view/sector-invalidated but reuses an unchanged projection for 30
  frames to protect the 60-Hz host.
- R and device digits 6-9 now also read iGUI's physical enhanced-key table.
  One shared held edge suppresses the physical fallback when the buffered
  character already arrived, avoiding a double toggle while still surviving a
  missing WM_CHAR. A real production-key run changed all four navigation
  settings, selected a different generated target through cartography, exited
  naturally, and round-tripped the expected v9 packed value 19 and target
  coordinates through a second launch.
- Habitable-world birds now preserve the original cautious-approach game
  instead of being collected automatically at a broad radius. Ordinary walking
  trips the source 250/100-unit escape thresholds; Ctrl + WASD supplies an
  80-unit stalking pace, and capture requires closing within 500 units. Bird
  reaction speed is scaled by model size as in `live_animal`, so stalking can
  overtake the first bird (80 versus 31 units/tick). A real-input type-3 run
  captured one bird and persisted it in a valid version-7 checkpoint.
- Reload reconstruction now reapplies that count to the deterministic bird
  records. A real-input checkpoint replay walked through the first bird's spawn
  and retained `captures=1`, closing the former save/reload recapture exploit.
- Surface panorama rendering now specializes the original fixed Noctis buffer
  layout directly, retaining its offset records, skips, 5x5 expansion and
  16-bit wrapping. A full indexed-frame cache is invalidated only by pitch,
  yaw, or planet regeneration, avoiding the former generic-dispatch freeze.
- Landed surfaces again expose the original `surrounding()` environmental
  readout: retained body radius supplies fractional gravity, the generated sky
  supplies temperature and atmospheric pressure, altitude adjusts the live
  temperature, and walking raises a decaying pulse. The GUI-scaled line owns a
  lower-HUD row above notices instead of clipping against the 200-line page.
- Surface movement no longer pins the player to the terrain on every tick.
  J restores NIV+'s `-500` jump impulse; held Space supplies repeated `-50`
  jetpack thrust, C cuts thrust, and the selected body's retained radius
  supplies the original `p_ray*2000` fall acceleration. Terrain contact clears
  all transient flight state, capsule return is refused while airborne, and a
  loaded surface checkpoint is reconciled safely back onto its generated
  ground. A real-input run rose from `-600` to `-2685`, landed at exactly
  `-600`, then reached `-7149` under sustained thrust before clean exit.

### Live general-world identity
- `nstopo` now retains phase-A `p_orb_seed`, `p_tilt`, `p_orb_tilt`,
  `p_orb_ecc`, initial radius, exact radian orientation, and phase-F final
  `p_ray`/`p_orb_ray` without changing its RNG schedule. Landings use Noctis's
  `(p_ray + p_orb_ray + p_orb_orient) * 4112` live-conversion formula; the
  former coordinate hash is gone. The opening geometry probe matches the
  independent reference bit-for-bit across every checked retained value.

### Live generated-system console
- The planetary wall console now reads each target system's retained body
  count, orbital radius, orientation, and moon owner instead of displaying
  opening-system constants. A cheap monotonic log2 score from the retained
  binary64 radius preserves relative spacing while fitting systems ranging
  from one planet to many orders of orbital scale on the small screen.
- The flight HUD now presents the selected target in a compact readable row:
  planet/moon identity, two-digit body and type numbers, authoritative
  `LAND`/`NO-L` state, and an eight-character world class. Type-10 companion
  stars no longer render as `TYPE :` or claim to be landable.
- Moons are scaled within their own parent's retained radius span and orbit
  the stored parent position. The existing wall-proximity gate still avoids
  drawing the 24-segment orbit rails when the player is away from the console.
- The original five direct body keys remain available, while bracket keys
  wrap through all generated planets and moons. Checkpoint restoration now
  validates against the full body count, so a selected moon is not discarded.

### Live ocean scenario
- Type-3 OCEAN landings now retain sea level instead of texturing zero-height
  ground as land. A source-scale 128x sea plane supplies the ocean palette and
  animated shimmer, the one-in-three island arm rises through it, and packed
  surface-object counts are cleared wherever the height map remains water.
  The source's ten wind-wave records contract toward their sea centre, while
  fifteen player-wake records expand from sea-level movement, flatten, expire,
  and suppress their segments over land. Calm high-albedo oceans and ICY
  surfaces now run the source-shaped terrain-only mirror pass with half-scan
  presentation; incoming wind swell suppresses it, while swimmer wakes remain
  available on calm water. Frozen glints are position-stable and liquid-water
  glints continue to move. A wind crest crossing the swimmer now retains its
  source ring, applies the short radial shove and view disturbance, and runs
  the original central-page, low-six-bit wet-lens smoothing for one to three
  simulation ticks. Crest contraction, wake expansion, impacts, and camera
  response remain fixed at 18.206 Hz under both presentation modes.

### Source-shaped surface trees
- Plains tree objects no longer use crossed trunk and crown cards. The live
  renderer now follows `build_fractal_tree`'s 120-degree branch detail with
  tapered three-sided limbs, source-scale variation, broadleaf/conifer palette
  classes, a one-or-three-way branch silhouette, and three terminal leaf faces.
- Recursion is intentionally bounded to one split inside the existing
  full-detail near-object radius. A focused production-rasterizer smoke drew
  1,665 non-background pixels and returned with every branch and face complete.

### Distinct habitable biomes
- Type-3 desert and icy landings no longer reuse the plains fallback. Deserts
  now use the source dune roughness/smoothing relationship, coarse 128-scale
  sand, and no scattered rocks. Icy worlds select snowfield, bare ice, rounded
  snow hills, or broken iceberg relief, followed by smoothed snow or cracked
  frost texture and rare large rocks.
- The expensive snow-hill outcome is bounded to 24 overlapping hills for live
  landing latency. A paired production-generator smoke completed both biomes
  in 5.8 seconds and verified distinct relief, texture scale, and rock state.

### Complete landable surface-class switch
- Accepted types 1, 5, and 7 no longer share the generic rocky fallback.
  Lunar worlds carry rounded ground, powered rim profiles, mottled craters and
  optional sharp stones; thin-atmosphere worlds carry eroded plains/permafrost,
  profile craters and fissures; frozen type-7 worlds carry elevated shelves,
  long surface striations, texture pits and short cracks.
- `GR std crater` now evaluates non-unit `h_raiser` with an x87
  `fyl2x`/`f2xm1`/`fscale` sequence instead of silently treating every
  exponent as one. `GR rockyground` also distinguishes positive elevation
  from negative cutoffs; the old shared path erased elevated frozen worlds.
- A combined production smoke completed all three classes with distinct
  terrain ranges, texture totals, and rock populations. The fallback is now
  defensive only; every class accepted by the landing control has its own arm.
- Type-3 OCEAN and PLAINS no longer use the port's generic rockyground/fixed
  island shortcut. Production now follows the original shoreline, open-sea,
  low-hill and mountain branches, including Borland right-to-left draws,
  unsigned 16-bit hill bounds, vegetation classes, grass asterisms, fast
  terrain noise, rocks, and calm-water state. A real iGUI journey generated
  the new terrain in under one second and completed land/walk/return with
  `bad=0`; the focused ground oracle remains texture-exact and its post-landing
  RAM residual fell from 39,710 to 1,752 bytes.

### Checkpoint preferences and surface progress
- Startup invokes the same reconciled checkpoint loader after timer/audio
  initialization. Valid saves resume before the GUI loop; absent, stale, or
  malformed files leave the initialized clean-flight state untouched.
- `GOES> NEW` is the explicit counterpart to auto-resume. It resets player,
  Vimana, target, resources, lift/capsule and surface progress to the opening
  flight, preserves presentation/audio preferences and starmap names, and
  immediately replaces the prior checkpoint.
- `CURRENT.LIN` version 11 is a 180-byte record retaining landing longitude and
  latitude, the settled capsule's X/Y/Z coordinates, navigation-device settings,
  internal-light state, and the last
  validated iGUI width/height alongside the 60/original
  presentation choice, FPS-overlay visibility, soundtrack state,
  captured-fauna count, lithium reserve, active collector, player, ship,
  target, Vimana, lift, landed state, and pending emergency-rescue phase. Its
  Noctis-epoch UTC timestamp advances an active collector and pending rescue
  across time spent outside the game.
- Loading reconciles the live timer and audio device after validation, then
  restores capture progress after deterministic surface regeneration. The
  reader remains backward-compatible with 96-byte v1, 108-byte v2,
  124-byte v3, 132-byte v4, 140-byte v5, 144-byte v6, 152-byte v7, 156-byte v8,
  160-byte v9, and 168-byte v10 saves; transient capsule integrator state remains
  intentionally unsavable. Version 11 reapplies the settled capsule only after
  deterministic surface regeneration, preventing wind-displaced landings from
  stranding a resumed player at the generated default pod site. Older landed
  formats perform a one-time safe migration by reconstructing the capsule on
  the saved walker's terrain position, after which the exact site is retained.
- A completed primary save refreshes `CURRENT.BAK` only after `CURRENT.LIN`
  passes its size check. A present-but-invalid primary falls back to that
  last-known-good record with a five-second onscreen recovery message; a
  deliberately missing primary still starts clean. Closed-game collector and
  rescue evolution runs only after every candidate field validates.

### Live selected-body fine approach
- Landing no longer jumps directly from calibrated interstellar arrival to
  capsule descent. Pressing L starts the original local MG approach cascade
  against the selected body's retained orbital radius and physical radius;
  the exterior view draws the closing globe and the screen-space FCS now holds
  `APPROACH` until `ip_reached` is true instead of falsely advertising
  `STANDBY` between internal batches.
- Local coordinates are kept separate from galactic `dzat`, preserving later
  NEXT/STAR navigation and existing checkpoint position semantics. Changing
  the selected body resets only the local approach.
- The second L queues descent for the next clean frame boundary. Explicit x87
  resets separate planet preparation, terrain generation, sky generation, and
  capsule initialization; this removes the real-GUI access violation seen when
  landing directly after the close-globe renderer.
- The opening planet reaches exact `STANDBY` after 8,895 source steps with
  power 21,105. The live game batches 32 unchanged steps per simulation tick,
  matching the capsule acceleration policy and reducing that wait to about
  fifteen seconds at the fixed 18.206-Hz gameplay cadence.

### Live lithium and power loop
- Target changes no longer reset `pwr`; Vimana and local approach costs now
  persist across exploration. At the +15000 threshold, one stored lithium unit
  restores power to 20000, while negative charge retains the original OMEGA
  infinite-reserve behavior.
- C toggles the original collector after calibration at class-5 stars or
  class-6 stars with radius above 4. Each simulation tick repeats the source
  `srand(identity); random(50)` rate and class-specific `125/dsd` or `25/dsd`
  penalty, fills power first, then banks charge up to 120. Planet approach and
  star retargeting stop collection.
- A compact ship overlay exposes unbiased power, lithium reserve, and
  collector ON/OFF state. Current checkpoints retain both resource and
  collector state; older port checkpoints load with the source default of
  three reserve units.
- Version-6 load reconciliation follows the source's hidden evolution: every
  30 closed seconds adds one banked unit up to 120, full banks restore 20000
  power, partial banks seed the original 15000..19999 range from current UTC,
  and pending emergency assistance advances or completes while closed.
- H restores the original emergency escape from a zero-power, zero-lithium
  softlock. It uses the source request gate, then renders another Stardrifter
  on the original squared approach/close-orbit/departure path before delivering
  three reserve units. The 120-second source fly-by is compressed to 180
  simulation ticks (just under ten seconds), and pending progress is saved.

### In-game control discovery
- `?` serves NIV+'s help/about role because this Windows iGUI host does not
  expose a distinct F1 state. The unused F9 enhanced-key flag provides a
  layout-independent fallback. The live port presents a compact
  control card covering movement, lift, GOES targeting, body selection,
  persistent star/planet naming, approach/landing, lithium/rescue, checkpoint,
  presentation, and audio keys.
- GOES now has a visible screen-space command line. ASCII is consumed every
  presentation frame but debounced against the runtime's physical key table,
  so 60-Hz mode neither drops two-thirds of typed characters nor repeats a
  retained console-buffer value. `G`/Tab are reliable open/submit fallbacks
  for the iGUI-owned Enter key, while Enter remains wired through a menu-safe
  client hook.
- Naming from a distribution without `STARMAP.BIN` creates the authentic
  four-byte total-size header before its first 32-byte record. Relaunching
  reloads that record; malformed existing headers are refused rather than
  overwritten. Record lookup and duplicate-name checks apply the proven
  catalogue decoder's identity domain: exponent-zero, Inf/NaN, over-range,
  and `Removed:` records are skipped without modifying the player's file.
- The card covers the completed frame with the source help page's opaque black
  field and is redrawn onto both synchronized GUI
  layers after every present/repaint. Its origin follows the centered 8:5 game
  area, so resizing or non-8:5 letterboxing cannot detach it from the view.

### Atmospheric capsule landing
- Atmospheric descents now reproduce the source wind state shape: five
  deterministic initialization draws supply `wdir`, `iwp`, and `rwp`, then
  every atmospheric simulation tick perturbs and clamps ideal power, eases
  current power five percent toward `iwp*rwp`, and varies direction through
  two more Borland draws. Capsule motion applies the current vector after its
  vertical physics step and resamples terrain beneath the displaced pod;
  airless worlds remain vertical. The exact RNG state that entered the
  original pre-surface initialization is not retained, so only those first
  five values are surface-seed-derived rather than claimed bit-exact. Live
  evolution consumes the retained post-surface Borland stream.
- Low-speed impact now runs the original complete 1,024-unit circumference:
  252 binary32 angle steps at 0.025 radians, binary32 coordinate stores,
  chopped `hpoint` arguments, the source 512-unit maximum-lip threshold, and
  the steepest-slope direction fed back to wind after a rebound. The real GUI
  journey landed after eleven bounces at 2.08 seconds, never exceeded a 232-ms
  observed frame interval, returned to the Stardrifter in 15.17 seconds, and
  reported zero bad geometry leaves.
- A focused production-library atmospheric smoke observed changing ideal
  power and direction, 14/20-unit peak lateral displacement before the
  source-style tile-centre snap, 11 rebounds, and a complete eight-call
  seal/ascent return to ship mode.

### Atmospheric storms
- The live type-3 surface renderer now consumes `create_sky`'s existing
  `rainy` value at the source thresholds: raininess 2.0 enables intermittent
  lightning and values above 3.0 submit the original camera-local 3-D rain
  field. Rain sticks inherit the capsule's evolving `wdir/wp` vector.
- Lightning temporarily brightens the full generated surface palette and
  restores the exact `srfpal6` components on the following clear tick.
  Weather cadence advances at 18.206 Hz, while drop positions use the current
  presentation frame so 60 Hz mode does not repeat a visibly choppy storm.
- Weather owns an isolated deterministic LCG because the original reseeds both
  rain streams from `clock()`. It therefore cannot perturb terrain's fast RNG
  or the live Borland stream used by capsule wind. The source 50-stick floor
  remains; accumulated extra density is capped at 174 submissions to keep a
  mature storm inside the software renderer's frame budget.
- The focused production-library smoke submitted 108/108 rain sticks, drew 52
  foreground pixels with a 50-unit wind slant, verified palette 0 -> 31 -> 0
  across flash/restore, and exited cleanly.

### Dense type-2 atmosphere
- The original Venusian post-effect now runs after terrain, capsule, ruins,
  and fauna: `adapted+2880` is reduced to the first 64 palette levels and
  passed through the source `psmooth_grays` four-row/four-lane kernel.
- Counts are derived from the live 14,560-dword steady page, bounding the
  shifted mask to 58,240 bytes and the smoothing writes to 56,960 bytes.
  A focused guard smoke preserved top/bottom index 200 while producing index 8
  throughout the processed interior and exited cleanly.

### Historical ruins
- The three source identity gates now recognise Balastrackonastreya, Fenia,
  and Ylastravenia from retained binary64 star identity. Their original body
  tables select skyscrapers, roofless wall shells, plazas/colonnades, palaces,
  colonial cross-buildings, and stepped domed Suricrasian blocks.
- Ruins modify the live 200x200 height map and carry a separate `ruinschart`
  marker map, selecting the source 2x texture scale and palette band 64..127.
  A sparse unit-tile overlay preserves narrow historical walls through the
  normal 8/16-tile distant-terrain LOD without making every surface expensive.
- The Felysia GUI probe produced 92 marked points and a peak of 174 visible
  ruin tiles, then landed, walked, ascended, and restored 720/0 ship leaves.
- The same smoke exposed unsigned comparisons in signed terrain bounds. Map
  edges now clamp before traversal and `mindepth=-1` once again enables the
  intended full-detail near ring; related signed surface/capsule deltas were
  corrected at the same time.

### Live general landing daylight
- Non-opening landings now read UTC through the runtime and reproduce NIV+'s
  seconds-since-1984 clock, every-four-years leap rule, per-body rotation
  period draw ranges, 130-degree night band, terminator distance, and twilight
  exposure. The orbital phase uses retained star/body radii and the source
  mass/revolution formula; ordinary moons inherit their parent planet's solar
  phase and companion-owned moons take the alternate body-mass branch.
- Generated owner, star class, target, sun distance, albedo, atmospheric load,
  and day/night brightness feed the existing source-derived sky renderer.
  `nstopo` now retains the phase-A seed, axial/orbital tilt, eccentricity,
  radian orientation, and initial radius through live x87 assignment boundaries.
  General landings compose the source eccentric body/parent vectors and use
  the original separate planet/moon rotation-seed products. The measured
  opening system remains byte-for-byte pinned at its default `000:060` site.
- A non-opening class-2 seven-planet GUI probe completed terrain generation,
  atmospheric descent, 11 rebounds, capsule return, and ship restoration in
  63.8 seconds with 720 hull leaves, zero invalid leaves, and live daylight
  telemetry (54.782-degree exposure at retained distance 48.06368).
- A class-3 calm-ocean GUI probe completed the same landing/walk/return path in
  13.7 seconds and recorded 54 mirrored terrain tiles with `waves_in=0`, while
  retaining 720 hull leaves and zero invalid leaves after ship restoration.

### Selectable planetary landing sites
- Reaching local `STANDBY` now opens the original landing-coordinate decision
  instead of immediately committing descent. A resize-safe logical page shows
  longitude `000..359` and latitude `001..119`; arrows move the site, L or Enter
  confirms, and C cancels without disturbing the ship view or roof lift.
- The chosen latitude drives polar climate and sky temperature, longitude is
  evaluated against the live UTC terminator, and the source location-local
  terrain and historical-ruin streams are reseeded from `latitude*longitude`.
  The measured opening palette remains pinned only at its original `000:060`
  point; every other site runs the verified source globe generator and samples
  its exact `p_background[360*latitude+longitude]` albedo plus atmosphere,
  cloud, rain, and scenario outputs. Real GUI captures at `008:054` and
  `180:060` show visibly different terrain and horizons while both report
  59 FPS.
- Version-10 checkpoints add longitude/latitude to the 168-byte record and
  preserve v1-v9 compatibility. Version 11 extends that record to 180 bytes with
  the settled capsule X/Y/Z position and preserves v1-v10 compatibility. A
  real-input opening run selected `008:054`,
  descended, settled, saved, exited, and automatically reconstructed the same
  site. A real 160-byte v9 record migrated to v10 with its player, target, and
  navigation word intact and the original `000:060` location default.

### Toolchain
- `lino_build.ps1` drives the GUI-subsystem compiler non-interactively:
  launches, polls for artifacts, kills. Classifies warnings vs errors, and
  refuses paths containing `--` (see bug 1).
- The production iGUI path now declares its initially full-height window
  unfolded before the first client loop. Presentation writes the backdrop,
  copies that authoritative complete frame to Primary, and performs one direct
  whole-display retrace; the outer control-loop pass adds the cursor. A 60-frame
  production sentinel measured 1,012 ms / 59.29 FPS at the default 2x host.
- Regression suite: `tests/run_all.py`. One test per wave-ish; the count grows
  every wave, so **no document states a number** -- `run_all.py` prints its own
  and refuses to run if a `test_*.py` exists that is not registered in `TESTS`.
  Expect roughly 40 s per test on the full suite. Nothing is graded against a
  stored binary; every side is rebuilt each run, and each test builds a
  deliberately broken version of its subject and requires that to fail.
- `tests/` holds more files than tests -- shared oracles, sandbox builders and
  the Wave 5 audit tool live there too. Counting files overstates the suite;
  `TESTS` in `run_all.py` is the only real list.

### Distributable play bundle
- `package_noctis.ps1` optionally rebuilds production, validates every linked
  external map/model/font/catalog/audio input, stages into a unique directory,
  and refuses to merge with existing output. The completed folder contains
  player instructions, WPL, and a SHA-256 manifest beside `Noctis-IV.exe`.
- `Play Noctis IV.cmd` is the bundle entry point. It changes to its own
  relocatable directory before invoking the game, keeping relative assets,
  `CURRENT.LIN`, `STARMAP.BIN`, and diagnostics inside the bundle even when a
  shell or frontend starts it with an unrelated working directory.
- A standalone two-launch smoke verified the full ship/console presentation,
  soundtrack OFF/ON persistence, version-7 checkpoint creation, 642x426 window
  persistence, manifest integrity, and two clean exit-code-0 shutdowns.
- A following 189.8-second interactive bundle session repeated movement/look,
  help/FPS repaints, cadence/audio toggles, and checkpoints with 43/43 responsive
  window probes. Working/private memory and handle counts ended below baseline,
  the rendered ship remained coherent, and exit/resume/exit all completed with
  code 0. Multi-hour coverage remains a separate open release-hardening item.
- A fresh relocated-launch smoke invoked `Play Noctis IV.cmd` from an unrelated
  working directory. The game and launcher exited with code 0, the valid
  152-byte version-7 checkpoint and diagnostic appeared only in the bundle,
  the caller directory stayed empty, and all 12 manifest hashes verified.

### Language extension (optional, not load-bearing)
- `*%` / `*%'` split-multiply added: 242 patterns, all semantically verified on
  real hardware. Needs `main/lib/gen/compiler114m.exe` with `-Cpu i386m`.
- Patched compiler passes the fixpoint test -- recompiles itself byte-identically.
- `main/lib/gen/compiler.txt` is NOT modified; `tools/patchcompiler.py` produces
  a copy. Reversible by deleting one file.

### Ported and verified
- **Galaxy hash** -- `work/galaxy.txt` (ML fragment) and `work/galaxy2.txt`
  (`*%`). Bit-exact against a C oracle lifted from `noctis-iv-lr` and an
  independent arbitrary-precision Python implementation, across 343 sectors
  spanning the galactic origin. The signed multiply is load-bearing: unsigned
  builds a plausible galaxy that matches nothing.
- **`fast_random`** -- the second of only two algorithms needing a full 64-bit
  product. Bit-exact on all three backends.
- **Star catalogue validation** -- generated positions checked against the real
  `STARMAP.BIN`, 37,578 records charted by players over twenty years, including
  the author's own hard-coded stars matched uniquely. Collisions are quantified
  rather than assumed away, and signal is measured against an unsigned-and-decoy
  control rather than a bare chance floor.

### Wave 1 -- Borland's LCG, exhaustive (DONE)

`srand` / `rand` / `random` ported and proven across the **entire seed space**:
65,536 seeds x 16 draws = 1,048,576 draws, plus the full `random()` argument
domain (all int16 values x 4 seeds x 2 draws). Three independent
implementations -- lino, C, and an arbitrary-precision Python written from the
algorithm rather than transcribed. Registered as `tests/test_brtlrand.py`.

Anchored on the shipped binary, not on anyone's transcription: Borland's
`rand()` sits at file offset 15979 of `NOCTIS.EXE`, and the multiplier's low
half `35 4E` occurs exactly once in 215 KB, so the location is unambiguous.

Builds with the **stock compiler and stock pack** -- the multiply is 32x32 into
32 low half only, so no `*%` is involved.

**The finding that propagates: `int` is 16 bits in the DOS build.** A
`random(n)` call with n above 32767 wraps negative -- `random(40000)` passes
-25536 and returns a negative result. Reproducing this needs explicit narrowing
at the call site (`BrtlToInt16` then `BrtlRandom`); calling `BrtlRandom`
directly with a large argument diverges from the game. **Every call site in
later waves must be checked for arguments above 32767.**

**Recorded so it is not re-litigated:** replacing the logical shift with an
arithmetic one in `(seed >> 16) & 0x7FFF` is **semantically neutral** -- the
mask keeps bits 16..30 and sign-fill only touches bits it discards (verified
over 200,000 random seeds, zero differences). No behavioural test can catch
that mutation; the byte-template check is the only way to pin it, and it does.

### Wave 3 -- the float engine (DONE)

**Extended precision works in L.in.oleum.** The x87 control word can be set to
`133Fh` (64-bit precision, round-to-nearest-even, exceptions masked) from a
machine-language fragment -- which modifies nothing and needs no permission --
and the 1996 catalogue then decodes exactly.

```
PC=64, values held on the x87 stack   4113/4113
PC=53 (IEEE double)                   2239
PC=24 (lino native)                      4
ambient Windows control word             7
PC=64 but with ONE spill to memory    3063
```

**Setting the precision is NOT sufficient.** A single store to memory anywhere
in a chain costs 1,050 records. The original's 80-bit behaviour comes from
values staying in `st(0)` across whole expressions, so the port must reproduce
the *scheduling*, not just the precision. Generation arithmetic runs on the x87
stack with intermediates never stored across an expression, and the control
word is stated at every boundary rather than inherited.

Policy in `docs-notes/FLOATPOLICY.md`, pinned by `tests/test_floatcontract.py`,
which recomputes every quoted number on each run.

**The float-to-int cast boundary is UNSETTLED** and nothing in the graded path
may depend on it. Recorded as open rather than guessed.

Two corrections the wave made to its own brief: a one-*extended*-ULP flip does
**not** fail the oracle (it still scores 4113/4113), so the test pins that
number and instead asserts a binary64-ULP flip is caught at 341/4113, locating
the real resolution; and a gcc-built hardware witness caught a genuine
round-to-nearest bug in the Python referee that a self-agreeing referee would
have shipped.

### Wave 4 -- star identity and system generation (DONE)

The port turns a star's coordinates into its planetary system, and **the 1996
binary agrees**.

```
IDENTITY   4100/4100 bit-exact      NOB      0 violations / 2450
CLASS      4099/4099                PHASE H  4100/4100 (16,307 bodies)
DL.EXE     4365/4365                3-way    bit-exact, all 100 fields
```

`DL.EXE` is the first *dynamic* oracle in the project -- the real game executing
under DOSBox-X rather than a static file. Proven by breaking: seven single-edit
sabotages, one per generation phase, each built and run. A dropped phase-A draw
moves 3,837 of 5,540 systems.

**Two sabotages are invisible to the 1996 oracles, recorded as measurements
rather than worked around.** Adding a draw in phase G is undetectable by
anything -- structurally, phase G is last and every later `rand()` consumer
re-seeds. The class-0 clip is invisible to DL because the capture set has no
class-0 star with few enough planets. The test requires 5 of 7 caught per
oracle rather than implying all seven.

**Correction to earlier reconnaissance:** phase A is **12 draws**, not ~10, and
**13** on class 8's else branch. Checked on every record now.

Geometry is deliberately **out of scope**, stated in the test header, with the
float-site registry pinned at 11 sites / 17 draws so geometry's arrival fails
that test first rather than slipping in ungraded. Detail in
`docs-notes/WAVE4_NEARSTAR.md`.

### Wave 5 -- buffer model and framebuffer (REVIEWER REJECTED -- corrective wave required)

**Do not treat this wave as done.** The suite passes 17/17, but the tests were
written around a model the adversarial reviewer rejected. Green tests over a
wrong model is exactly the failure the separate review/QA/test roles exist to
catch, and here they caught it.

**Sound, keep:** Decision 1 (one Noctis byte per 32-bit unit) and Decision 2
(one flat 402,196-unit workspace in `farmalloc` order) -- triple-corroborated
across all 27 layout units. The tick's period arithmetic, accumulation,
skip-to-grid and signed-difference predicate are correct and cross-graded.
`docs-notes/BUFFERMAP.md` (718 lines) stands and is the wave's durable value.

**CRITICAL 1 -- the tick servo wraps.** `TK servo` divides counts-since-start by
wall-ms-since-start. `[Counts]` is 32 bits and wraps every 477.3 s; the
denominator grows without bound. From ~8 minutes in the ratio is nonsense --
1840 cpms at t=600 s against a true 8999, 4226 at t=900 s -- and the ±1% clamp
turns a one-shot collapse into a **permanent 1%-per-14-s ratchet**. The period
is proportional to cpms, so the whole tick degrades. Reproduced arithmetically.

**CRITICAL 2 -- class A does not reproduce a 16-bit wrap.** Decision 3 treats
"write contained by 16-bit wrap inside the buffer's own segment" by allocating
the full segment. **Allocation size cannot reproduce a wrap.** Under DOS the
write folded to offset 0; under 32-bit unit addressing it walks linearly past
the region end. This is the decision Waves 6-9 inherit.

**MAJOR:** the 16-unit pads are given two mutually exclusive jobs (guard band
*and* legitimate destination for `digit_at`'s `txtr[-6..-1]`), so the first
cockpit glyph fires the canary; Tier 2 was not achieved for the palette, LUT or
index page (one implementation only, so the two-implementation standard is
unmet there); the canary cross-check writes the same poison on both sides by
construction and therefore **passes regardless**; and `PAL shade` hard-codes its
destination while 17 of 24 original call sites pass a different buffer.

**Honestly recorded by the wave itself:** three XFAILs asserting things are
still broken (so a silent fix fails the test), and the 16-bit index wrap is
**not expressible in the delivered model** -- `BUFFERMODEL.md` open item 6, and
Wave 6's first job.

### Wave 5b -- corrections (PARTIAL: tests fixed, harness still defective)

**Fixed and verified by the reviewer in the source:** the tick servo. Sampler
and estimator are split, both anchors re-base unconditionally before a SIGNED
band test, the divide is rounded, the clamp has a floor, and there is a
wall-fold plus a calibration-end clamp that never existed. The long-horizon leg
is the proof: over 19.9 simulated minutes across wrap-straddling windows, the
**original** estimator collapses to 5,355 against a true 8,999 while the new
one holds with worst error 0.

**Also fixed:** all three XFAILs converted to positive assertions with
evidence; the fake canary in `tests/` deleted and replaced by one deriving all
four fields from the layout with no stored literal; a blocking build break
repaired; and three sabotages that revealed *real* holes were closed rather
than dropped (a clamp floor nothing drove, a band nothing drove negative, and a
mask double-applied so its deletion was invisible).

**STILL DEFECTIVE -- the same pattern recurred in a different file.** This wave
existed because a canary compared a constant against itself. `tests/` was
fixed; `noctis-harness/` now carries three fresh instances:

- `lino_break_matrix` grades each sabotage against stored references and all 19
  rows read identically -- **passes regardless**.
- `fb_layout.py`'s replacement canary returns a bare literal, then compares
  against that same literal by construction.
- the ring sweep computes `start` from `end` and `want`, then recovers `want`
  from `start` and `end` -- tautological in **both** implementations.

`fb_compare.py --suite` reports **FAIL**: 117 checks, 6 failed, 3 NOT GRADED.
The index page differs in 63,988 of 64,000 units because `w5probe` and
`fb_ref.c` run different scenarios that no document reconciles.

**Grading tiers, stated precisely rather than claimed:** palette and LUT reach
Tier 2 (three producers, three sabotages caught). The index page is **Tier 1**.
Alias 8's premise -- that `farmalloc` returns offset 4 -- is **Tier 0**.

**Two new XFAILs, both genuinely open:** `SRVMAX` is a literal, so above
~71,583 cpms the estimator still ratchets; and no game call site drives the
class-A mask, so sites 2..5 read zero calls and two painters are uncensused.

**The lesson worth keeping:** fixing the instance you are pointed at does not
fix the pattern. The next wave that touches the harness must re-audit every
comparison for "could this record differ between a working and a broken
mechanism?"

### Wave 5c -- harness audit (INSTRUMENT BUILT, HARNESS NOT CLEANED)

**The class is now measurable rather than eliminated, and that is the honest
summary.** `tests/w5audit.py` runs inside the suite and does not read variable
names: it inlines single-assignment locals and module constants, atomises the
remainder keyed by source text -- so two spellings of the same call become one
atom -- then **executes** each check condition over 300 random assignments drawn
from a spread containing every integer literal in the condition ±1.

Three rules: always-true; one side's atoms strictly containing the other's with
the predicate insensitive to the rest; and a tally never incremented. **Rule C
exists because rule B was evadable by spelling** -- the wave wrote the evasion,
ran it, watched it escape, and closed the hole.

It found **four void checks in the wave's own test files**, including one in the
very file criticising the pattern. `fb_lint` -- name-based -- returns zero
findings on all four.

**STILL LIVE, and pinned so they cannot be silently dropped:**

- `fb_tick.py:406` ring sweep -- **instance 3 of the original brief, unfixed**.
  `start = (end-want)&M32` then `got = (end-start)&M32` recovers `want` for
  every origin. The audit detects it every run; nobody repaired it.
- `T2.LINO.MATRIX.NULL` passes vacuously -- its `gradeable` set is empty.
- `fb_ref.c`'s E1 pair cannot distinguish a working expander from a deleted
  one -- proven by gutting `present_expand` in a sandbox. **The audit reads
  Python only, so the whole C side is outside its reach.**
- the `inrow:` escape hatch is unverified and load-bearing: 78 of 127 GRADED
  entries rely on it alone.

`OPEN_BUDGET = 4` may fall and may never rise, and each open item is asserted
**still present**, so a silent deletion fails the suite too. Tier pinning caught
**4 over-claims** and 8 ledger violations.

**Decision: stop here and proceed to Wave 6.** Three waves on the buffer model
is enough -- its core decisions (one byte per unit, one flat workspace) have
never been in dispute and are triple-corroborated. What remains contested is
*grading confidence in the harness*, which is now quantified and ratcheted
rather than unknown. Wave 6 builds its own grading and is subject to
`w5audit.py`, so the instrument travels forward even though the harness is
imperfect.

### Census
Noctis IV has 20 multiply sites, 5 that matter, and only 2 distinct algorithms
need a full 64-bit product -- both now ported. Six of nine builds use the stock
compiler and stock pack. **`*%` is a contribution, not a dependency.**

---

## Delivery loop

Reconnaissance through Wave 10 is complete. There is no standing multi-agent
pipeline and no required role ceremony. One owner takes a user-visible slice
from source to the running game:

1. implement the smallest complete product path;
2. run one focused check at its load-bearing seam;
3. launch the integrated game path and inspect the actual behavior;
4. fix observed failures and continue immediately.

Use another agent only when a genuinely independent implementation task can
run in parallel without coordination overhead. Review, extra oracles, mutation
campaigns, and the full suite are optional deep/release work, never prerequisites
for ordinary progress. The active target is a playable port in roughly half a
working week, so testing and process together stay near 10% of elapsed effort.

## Oracle trust -- read before using any reference

**`noctis-iv-lr` is NOT ground truth everywhere.** Its README lists planetary
surface generation as unfinished, and its changelog deliberately excludes
assembly-to-C++ translation artifacts -- so its silence never implied
correctness. Confirmed divergences from vanilla:

| Where | Divergence | Consequence |
|---|---|---|
| type 3 land noise | vanilla **adds** to smoothed terrain, LR **assigns** | changes albedo at the landing site, hence scenario type, hence all ground terrain. **LR unusable as an oracle for habitable planets.** |
| type 9 | writes to the offscreen video page, not the surface buffer | substellar objects get an unfilled surface map |
| `wave()` | drops a `+4` byte offset | affects gas giants; correct answer depends on Borland's allocator |
| `lssmooth` | one fewer pixel per call, added to silence a memory checker | small but systematic |

**`niv-plus` is a fork**, Noctis IV+ Release 2.3, not the pristine 2003 drop.
Every generation-path function was compared against LR and matches, so it is a
valid stand-in *for generation*. Do not assume that holds elsewhere.

**Where neither is trustworthy, the DOS binary under DOSBox is the only
reference.**

## Wave 2 -- the two geometry unknowns (SETTLED)

Both answered by static analysis of the shipped `NOCTIS.EXE`. Full evidence
chain in `docs-notes/WAVE2_ANSWERS.md`; pinned by `tests/test_wave2.py`.

```
unknown1.verdict = NARROWED_AT_CALL_BOUNDARY
unknown2.verdict = LEFT_TO_RIGHT
```

1. **The `double` does NOT survive into `rand`.** It is chopped by Borland's
   `__ftol` and narrowed to `int16` at the call boundary.
2. **`zrandom` is first draw minus second.** Left to right.

**Both answers vindicate `noctis-iv-lr`.** These were flagged as the most
likely sources of silent planetary divergence; they are not. **No sign flips
are needed**, and LR's planetary geometry is trustworthy on these two points.

**Structural finding that dissolves the original premise:** `rand` has exactly
**one caller**, so `random()` was compiled as a real function rather than
expanded as a textual macro. The narrowing is therefore uniform at every call
site instead of varying with the argument's declared type.

**Confidence, stated honestly.** Three decoders by different routes (capstone
anchor / ndisasm symbol-signature / byte-template with no disassembler), a
15-mutant battery in which every expectation must first differ from the
pristine answer, and a generated liar-decoder control that must be caught on
all 15. Caveat: `bx_w2.py` carries a hardcoded verdict for unknown 1, so that
answer rests on **two** genuinely independent routes, not three. The asymmetry
is encoded in the test rather than hidden.

Note: `NOCTIS.EXE` is a **large-model** build using far calls. Any independent
re-derivation needs the segment mapping -- near-call assumptions find nothing.

## Floating point -- sharper than first framed

The earlier rule (make quantisation points exact, tolerate the rest) holds, but
the worst cases are not comparisons -- **they are seeds**. `global_surface_seed`
is a double sum times 4112 truncated to long; `seedval` is a product of up to
six doubles. One ULP changes the truncated seed and you do not get a slightly
different planet, you get a **different planet**. No tolerance exists there.

Vanilla was built `-f287`: x87 with 80-bit intermediates. Whether lino can be
made to match that is the single highest-leverage open question.

## Floating point -- the precision ladder, and why lino loses

**The original's FPU state is known exactly.** Control word `0x133F`, read out of
the shipped `NOCTIS.EXE` by parsing the MZ header and the Borland C0 startup:
precision control = **64-bit extended (80-bit)**, rounding = **nearest-even**,
all exceptions masked. It links `fp87.lib`, not the emulator -- hardware FPU.

**The ladder, worst news first:**

| | precision held |
|---|---|
| original (DOS, x87) | **80 bits across whole expressions** -- asm chains keep values on the x87 stack over many operations with no store |
| noctis-iv-lr (SSE2) | 53 bits per operation |
| **L.in.oleum** | **24 bits per operation** -- narrows after *every single instruction* |

The earlier hypothesis that lino might sit closer to the original than LR does
is not merely wrong, it is wrong by the largest possible margin. lino's native
floats **cannot** reproduce the original's generation arithmetic.

**Why that is fatal specifically for generation.** The seeds are floating-point
values truncated to integers (`nearstar_identity`, `global_surface_seed`,
`seedval`). One ULP changes the truncated seed, and the result is a *different
planet*, not a nearby one. At 24 bits versus 80, divergence is certain, not
possible. There is no tolerance to set.

**Therefore, for generation code: integer reduction first, soft-float second.**
Do not attempt to emulate the original's float chains -- reduce the arithmetic
to exact integer operations wherever the algebra permits, and fall back to a
soft-float double only where it does not. Rendering keeps native floats; a
quarter-pixel is invisible.

**One piece of free good news.** The original has *two* float->int behaviours:
C casts truncate (Borland's `__ftol` flips to chop and back), but **38
hand-written `fistp` sites round to nearest-even** because the rounding control
stays at 00. Those are the projection and texture-mapper sites. Under a
round-to-nearest policy lino's `=,` reproduces all 38 **for free**, and an
explicit correction helper is needed only at the C-cast sites. That also means
LR's half-away-from-zero `round()` is LR's bug, not something we inherit.

**A decoy that will mislead any audit.** `PITAGORA.H` contains a
`_control87(RC_CHOP, MCW_RC)` call that **never executes** -- Noctis includes
`tdpolygs.h` and never `pitagora.h`. The same trap is preserved in LR's `Old/`
tree. Anyone checking for control-word handling finds it first and concludes
the original ran in chop mode. It did not.

**Mixed-precision round-trips are observable behaviour.** The declared-type
split is `double` for generation, `float` for rendering, and some values are
deliberately narrowed mid-expression (`nearstar_ray` is `float` but feeds
`double` math). Preserve the narrowings; do not optimise them away.

**Outstanding:** the full quantisation-site registry was produced by the recon
but survives only in its transcript. Rebuilding it -- every float->int cast and
every float comparison that selects a branch, with file:line -- is a task for
the float wave, not something to reconstruct from memory.

## x87 is not optional -- settled by the data

The starmap harness proved the catalogue's stored doubles decode bit-exactly
**only under 80-bit x87**: 4194/4194 records, against 2315/4194 with IEEE
doubles throughout. That is a fingerprint identifying Borland + 387 as the
writer, and it matches the shipped compiler config `-ml -3 -f287`.

So extended precision is required to read the shipped data correctly, not
merely to match the original's flavour. Whether lino can be made to run at
64-bit precision -- via the x87 control word, legally settable from an ML
fragment -- is the highest-leverage open question in the project.

Two catalogue records are malformed and must be **rejected, not zeroed**:
`#3876 WESTOS` is -0.0, `#34754 MDIR 17` is a byte-reversed NaN.

## Corrections to earlier claims -- do not re-introduce

| Claimed | Actually |
|---|---|
| `GLOBES.MAP` is int16 records | **int8 (y,x) pairs.** The int16 reading is an artifact of a constant y byte in the high position; the code sign-extends 8->16. Texture stride 360, not 256. |
| `CURRENT.BIN` is 245 bytes | 245 is only the documented first block. Real size **370** (stock/LR), **381** (NIV+). |
| `SURFACE.BIN` is 45 bytes | 45 stock/LR, **40** in NIV+. Not interchangeable. |
| the `pwr` +15000 bias is a harmless legacy | **Live threshold in ~12 places.** Store power unbiased and the ship reads as permanently dead. |
| `charge < 0` is corruption | Deliberate cheat (infinite fuel, prints OMEGA). Do not clamp. |
| `atl_x`/`atl_z` are 0..3276800 | The code stores the **quotient** (`>>14`); on-disk range is 0..~200. |

## L.in.oleum file-interface constraints

- **No `SEEK_END`.** `[File Position]` is absolute-from-start only; negative is
  a hard error. Noctis seeks from the end throughout, so every such read needs
  `TEST` first to learn the size, then an explicit subtraction.
- **Short reads are silent.** A partial read is not an error -- `[Block Size]`
  is quietly corrected to what was actually read, and does not survive the
  isocall. Check it after every read.
- **CWD is not the executable's directory.** The runtime passes names straight
  to `open()`. Noctis handles this by parsing `argv[0]` and `chdir`-ing; do the
  equivalent with `SET DIR` before touching any asset.
- **No open/close** -- each I/O is a complete transaction.

**Ship assets as plain files, not via the stockfile.** The stockfile is
read-only, cannot report a member's size at runtime, forces <=8-character
lowercase names, and requires a recompile per asset edit. The plain-file path
is needed anyway for saves and catalogue appends, and one I/O path beats two.
Both reference ports moved assets out of the executable independently.

## Asset manifest

The integrated executable's complete runtime read audit requires the extracted
`globes.map` (22,586), `offsets.map` (7,340), `vehicle.ncc` (5,802),
`mammal.ncc` (2,752), `birdy.ncc` (1,002), `digimap2.bin` (9,360), the mutable
`STARMAP.BIN` catalogue, and the authorized `noctis_music.pcm` soundtrack.
`package_noctis.ps1` validates and copies those files beside the executable,
then emits their SHA-256 manifest. `CURRENT.LIN` is generated on first clean
exit. `SUPPORTS.NCT` is the upstream container from which the map/model/font
assets were extracted; `GUIDE.BIN` is provenance data but is not opened by the
integrated executable, so neither is a runtime-bundle dependency.

Do **not** port: the seven `.VOC` files (zero references in either tree),
`ALPHABET.NCC` / `EXT-VHCL.NCC` / `FACE.NCC` / `PARATIE.NCC` (never loaded),
`TEXT3D.H` (not in the build). Only three models are ever loaded -- VEHICLE (the
stardrifter), MAMMAL, BIRDY.

**`.NCC` trap:** triangles carry uninitialised garbage in their unused fourth
vertex slot, some decoding near 1e38. The loader zeroes it *before* the
transform pass; skip that and the transform produces infinities.

## Runtime feasibility -- measured, not estimated

The platform is not the constraint. All figures below were measured with probe
programs built and run on this machine.

| Facility | Result |
|---|---|
| clear + palette-expand + RETRACE, 320x200 | **0.799 ms -- 1.5% of a 55 ms tick** |
| unthrottled frame rate | 785 fps (RETRACE does not block on vsync) |
| median tick, busy-wait on the HPT | **55.0000 ms**; p90 within 0.1 us |
| timer resolution | 111 ns (TSC/256, ~9000 counts/ms) |
| `SLEEP` as a tick source | **useless** -- 62.75 ms for a 55 ms request |
| workspace growth | 1 GB allocation succeeded |
| exclusive 320x200 | real mode switch, closest thing to mode 13h |

**Implications.** ~54 ms of every tick is free for the renderer. Palette
animation costs a full re-expand each time (0.10 ms) since there is no palette
hardware -- affordable hundreds of times per tick. Memory is a non-issue: the
entire working set is ~643 KB, ~2.5 MB even at one byte per 32-bit unit.

Two refinements to build in from the start: target the true DOS period of
**54.9254 ms** (65536/1193182 s), not 55; and accumulate the deadline rather
than re-basing each tick, which removes a measured +0.057 ms/tick drift.

**Input is better than LR's.** The LUCK table gives true held-key state -- 1
while physically down, 0 on release -- which is the direct equivalent of the DOS
BIOS key-down table Noctis used and which LR had to reconstruct from polling.
98 keys, arbitrary combinations, no repeat. `GET CONSOLE INPUT` is a separate
ASCII FIFO, right for command letters and name entry, useless for flight.
Events are drained at the top of every isocall, so a frame that makes no
isocall stops responding.

**MIDI: SETTLED -- the game never played music.** The soundtrack is the
background music of the HTML *manual*, via a `<bgsound>` tag that only Internet
Explorer honoured. Ryan Bury's credit enumerates it among manual assets ("this
manual, its non-screenshot graphics, and *its* soundtrack"), and NIV+ 2.4
modernised the same tag to `<audio>` with an MP3. A browser played it.

Verified against four real distributions spanning ~25 years (original DOS,
Noctis IV CE, NIV+ 2.3 and 2.4): **none ever set a `mididevice`, and none ever
placed a MIDI file near `modules/` or `data/`.** `NOCTIS.EXE` has no sound-card
port I/O and no audio filenames; `GO!.EXE` is a 4.6 KB ShellExecute shim; the
PC-speaker routines live only in a header included solely by the model editor
and are never called. `niv-lr` did not drop audio -- across 302 commits it never
mentions it. There was never any to drop.

The VOGONS thread that suggested otherwise says the opposite on a closer read:
the same poster wrote "there is no sound, so I didn't worry about those
settings". The Linux crash is a DOSBox ALSA bug independent of the guest.

**Consequence for fidelity:** silence remains the faithful original ship state
-- it is what the original, every distribution, `niv-lr` and the Windows port
all shipped. The completed port keeps that state available through a music off
control.

**Music is now an authorized completion feature, and pre-rendering is correct.**
Use `noctis/niv-plus/manual/Files/RYAN_BURY_-_NOCTIS.MID` as the source, render
it offline, ship as PCM, and loop it through the working audio path. A free win:
lino's stereo-16 packing (channel 1 low half, channel 2 high half of one unit)
is bit-identical to interleaved S16LE, so a headerless 44100/16/stereo render
loads straight into the workspace with no conversion. Full track ~24.6 MB,
2.4% of the demonstrated ceiling, fits in memory -- no disk streaming needed.
Unverified: that lino assembles file bytes into units little-endian. Probe it;
if wrong, fix it in the offline baker, not in lino.

**A wavetable synth is UNNECESSARY, not infeasible** -- correcting the earlier
claim in both directions. ~800-1,200 lines of lino for output worse than a
fluidsynth render, on content that never responds to game state. Justified only
if someone later wants music that reacts to gameplay, which is a new feature
rather than a port requirement.

**Authorization record.** The music is **Ryan J. Bury's**, credited separately
and contributed as manual decoration. On 2026-08-09 the user reported Alex's
confirmation that the project may include it. This is a project-scope record,
not an invented licence text; preserve the original credit and source asset in
any distributable manifest.

**VOC effects.** One loop buffer with a live playback cursor
-- write ahead of the cursor each tick with all effects summed. A software
mixer, ~300-500 lines, ordinary work. There is no MIDI interface in the comm
area at all; the soundtrack would require writing a General-MIDI softsynth.
**MIDI is the only genuinely infeasible item in the entire port.** Audio is
also Win32-only -- the Linux runtime's PCM layer is a stub.

**Window close is reconciled.** ESC, iGUI's red close button, and Alt+F4 all
return from `Enter Integrated GUI`, then write the versioned checkpoint and
stop audio before leaving the floating-point environment. A production click
smoke exited naturally with code 0 and a fresh valid save timestamp.

## The hardest problem: no byte addressing

L.in.oleum is unit-addressed, 32 bits per unit, with no byte pointers anywhere.

Noctis is built on byte arrays indexed with byte arithmetic, deliberately
aliased onto one another, read from disk as packed byte streams, and written
through a byte-per-pixel framebuffer whose overruns the original tolerated
because neighbouring bytes were harmless. LR had to inflate two buffers purely
as guard bands for out-of-bounds writes present in the original source.

None of this translates mechanically. **Every buffer needs an explicit
decision** -- one item per unit (4x memory, simple, fast, and now trivially
affordable) or packed four-per-unit with shift/mask on every access. Every
aliasing relationship and every out-of-bounds write the DOS layout silently
absorbed must be found and made explicit.

Laborious, not infeasible -- but it touches essentially every rendering
function, and it is where the bugs will live. **Default to one item per unit**
unless a specific buffer proves it needs packing; memory is free here and
correctness is not.

## Gotchas discovered by probing

- **Underscores in lino string literals become spaces.** Use `\us`. A filename
  literal with an underscore silently writes to a differently-named file.
- A partial read is not an error; `[Block Size]` is quietly corrected.
- `[Counts]` wraps every ~477 s, but unsigned subtraction across the wrap still
  gives the correct delta.

## Sphere rendering -- the table is a formula

`GLOBES.MAP` is not opaque data. Its geometry was recovered by fitting, with
**RMS residual 0.47 px over all 10,780 records**:

```
row k = round((i-5.5)/360), column s = i-5.5-360k
latitude  psi    = -60 deg + 1.00047*k       (1 deg per texture row)
longitude lambda = -1.00060*s                (1 deg per texture column)
camera distance D = 2.506 sphere radii
dx = 250.84 * cos(psi)*sin(lambda) / (D - cos(psi)*cos(lambda))
dy = 200.68 * sin(psi)             / (D - cos(psi)*cos(lambda))
```

The constants are round numbers -- `Fy ~ 200` is the engine's own focal length,
`Fx/Fy = 1.250` is the 320x200-on-4:3 pixel aspect, `D = 2.5`. This is the
original derivation recovered, not a curve fit. A port may regenerate the table
rather than ship it, though shipping is safer for bit-exactness.

**CORRECTED by Wave 6b -- the earlier "correction" was wrong.** Total advance is
**42,845**, not 43,200: 10,780 draws plus 513 skips, decoded twice and
cross-checked. The data-formats recon originally reported 42,845; the renderer
recon "corrected" it to 43,200 and I propagated that into this file. The
original was right. The latitude-range consequence survives -- only about 120 of
the 180 texture rows are ever displayed.

**Also corrected:** `pixels + skip == 360` is **NOT an invariant** of
OFFSETS.MAP -- it holds for 39 of 48 bands. What *is* invariant, and is checked
instead: band k starts on source row k+2, and the widths and phases are
palindromic.

**And the fit is looser than recorded.** "RMS 0.47 px" does not reproduce. This
file's constants measure **0.7647** per record; an independent re-fit gives
0.5054. The test pins both and states the bound it actually requires.

**The Wave 6a cross-validation came out NEGATIVE, and that is a real finding.**
Substituting the projection's dpp = 210 collapses the fit from 10,780 records
to 176. The sphere table's focal length is a **baked asset constant, not the
camera's** -- the two subsystems do not share a projection. Now a standing
check.

**Traps:**

- **Lighting is baked into the texture, not computed.** `surface()` darkens a
  130-degree longitude band starting 35 degrees after the sub-stellar point by
  a shift, across 179 rows. 130 rather than 180 is deliberate (diffuse light
  plus limb foreshortening, per the author's note). `glowinglobe` re-derives
  the same constants at draw time so the crescent matches. **There is no N.L
  anywhere in the planet path.**
- **`globe()`'s parameter is named `offsetsmap`, but every caller passes the
  globes map.** The offsets map goes only to `background()`. Easy to wire a
  port backwards.
- **The 32,768-byte buffer is triple-purposed** -- globe table, sea/horizon
  texture, and the 32x36 pilot font aliased at its tail. The ground renderer
  overwrites it, which is why the maps are reloaded on leaving a planet. **Use
  separate buffers.**
- LR parameterised `globe()` for arbitrary resolution but left `glowing_globe`,
  `white_globe` and `white_sun` hard-coded, so the four now disagree about the
  clip rectangle. Another entry for the unreliable-oracle list.

## Wave plan

Populated by the architect once the five recons report.

Strong candidate for **Wave 1**, from the planet-generation recon: port
`brtl_rand` / `brtl_random` / `brtl_srand`, Borland's LCG, and prove it
**exhaustively** -- `brtl_srand` takes a `uint16_t`, so all 65,536 seeds at a
fixed draw depth is a complete proof rather than a sample. Zero floating point,
needs no `*%` (the multiply is 32x32->32 low half only), and it gates 346
`random()` call sites. Nothing downstream can be verified until it is exact.

Then, before any geometry: the **DOSBox evaluation-order experiment** to settle
the two unknowns above.

- [ ] **Wave 1** -- pending architect
- [ ] **Wave 2** -- pending architect
- [ ] **Wave 3** -- pending architect

### Reconnaissance in flight

| Track | Question |
|---|---|
| Renderer | the 3D pipeline: `poly3d`, `polymap`, projection, the 2D primitives, sphere rendering |
| Planet generation | `prepare_nearstar`, the Borland LCG, surface terrain, where LR is an unreliable oracle |
| Floating point | what lino's float support actually is, and where bit-exactness is achievable |
| Data formats | `SUPPORTS.NCT`, `.NCC` models, the map tables, saves, and how they map onto lino's stockfile |
| Runtime gaps | framebuffer, 18.2 Hz tick, input, audio, memory -- can this be a playable game at all |

---

## Floating-point policy

Bit-exactness is never lost, only deferred. Design so it can be switched on
later without touching call sites.

**Three tiers, by cost:**

| Tier | Mechanism | Cost | Use |
|---|---|---|---|
| native | lino's own float instructions, inline | free | rendering |
| controlled | x87 precision-control set to match the original | ~free if available | generation |
| soft-float | IEEE 754 in integer arithmetic | slow, but bit-identical on any machine forever | fallback, and the guarantee |

Soft-float is the escape hatch that makes this safe to defer: exact 64-bit
integer arithmetic in lino is already proven, so a deterministic double is
buildable whenever we need one.

**The rule that actually matters.** Smooth float differences are cosmetic -- a
planet a hair's width off looks identical. The failures that matter are where a
float is **truncated or compared into a discrete decision**: float->int casts,
comparisons that select a branch, anything feeding an array index or a shift
count. The known example is `rarity_factor`, where `sqrt` feeds a truncation to
`int16` that becomes a shift count and flips a star in or out of existence.

So: **make the quantisation points exact, not everything.** Those sites are
rare and cheap to protect; the arithmetic between them is not worth chasing.

**Structure:**

```
generation   -> every float op through the policy layer
                (per star / per planet; call overhead irrelevant)
rendering    -> native ops inline
                (per pixel; exactness cosmetic, speed is not)
quantisation -> ALWAYS exact, whichever policy is active
```

**The registry.** `FLOATPOLICY.md` (to be written from the float recon) lists
every float site with its classification -- exact-required or tolerant -- so
"what matters" is version-controlled rather than remembered. Changing a
classification and rebuilding is the intended edit; the harness then reports
whether it changed any output.

**Detection.** The test harness runs the same generation code under two
policies and reports exactly where results diverge, so switching from tolerant
to exact is a measurement rather than a leap of faith.

## Known hazards

- **`"variables"` vs `"workspace"`** -- in `variables`, `name = N;` initialises a
  variable to N; in `workspace` it allocates an *uninitialised vector of N units*
  and the name is its address. `foo = 0;` in `workspace` allocates nothing, top of
  workspace never advances, and every symbol collapses onto the same cell. No
  error, no warning, uniformly wrong values.
- **Self-hosting trap** -- `lino_build.ps1` clears the output path before
  building. Compiling a compiler with itself deletes the compiler mid-build.
  Build under a different name.
- **Floating point is the next real unknown.** The original ran x87 with 80-bit
  intermediates; LR uses SSE2 doubles; lino has its own float instructions.
  Bit-exactness will not be available everywhere. The hazards are not smooth
  differences -- they are float results that get truncated or compared into
  discrete decisions, such as `sqrt` feeding a truncation that becomes a shift
  count and makes a star blink in or out.
- **LR is not a trustworthy oracle everywhere.** Planetary surface generation is
  unfinished there. Establish per-subsystem whether it can be used as ground
  truth before relying on it.

## Bugs found in L.in.oleum

1. Command-line parser truncates on `--` anywhere, then blames the CPU pack.
2. `main/linux_compiler.bin` segfaults at startup on modern systems.
3. Relative-address modifier documented backwards; `+` and `-` both subtract.
   Fixed in the patched compiler: `+` left alone, `-` now adds.
4. Application-name field not cleared before writing, leaving a shard of the
   runtime template string in every executable.
