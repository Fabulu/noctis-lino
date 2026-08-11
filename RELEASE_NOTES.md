# Noctis IV L.in.oleum port -- 0.1.0 beta 3

This beta restores the source-positioned Stardrifter wall computers, makes the
physical planetary station usable through landing, corrects the surface guard
frame, and retains the source-equivalent cupola and lift behavior confirmed in
beta 2. It is an intermediate milestone toward uncompromised Noctis IV+ feature
parity, not a claim that parity is complete.

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
- Save and resume versioned checkpoints. Verified saves retain a backup and a
  damaged primary visibly recovers from the last-known-good copy.
- Resize the native iGUI window while the authentic 320x200 renderer remains
  nearest-neighbor scaled and aspect fitted.
- Toggle Ryan J. Bury's manual soundtrack with F8; silence remains available.

## Important behavior in this build

- The authentic 18.206 FPS presentation is the default.
- F5 opts into the higher presentation rate; simulation remains 18.206 Hz in
  either presentation mode.
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
- E directly starts the source lift event while inside the Stardrifter. Up
  remains a look control, and walking into the roof cupola opening starts the
  original automatic return. The calibrated ascent retains the source's
  forward momentum through the final roof frame, carries the player clear, and
  uses the same heading for the view and ride motion.
- Facing the first right-wall computer and pressing Enter focuses physical
  GOES. Command input and retained output use the original mapped 32x36 font
  directly on the wall faces. The original resident `CLR` command clears the
  output tree, while `WHERE <catalogued name>` searches the mutable starmap,
  distinguishes stars from planets, reports ambiguous prefixes, and resolves
  a planet's parent star. Bare `SL` lists every non-removed star in source file
  order. Its 7,586 output rows fit in the expanded 8,192-row scrollback, and
  literal underscores in catalogue names remain visible. `PAR <catalogued
  name>[:range]` now regenerates the
  original procedural sector cube and reports X, -Y, Z coordinates. The G
  shortcut includes the same seven retained output rows as the wall display.
  `ST <catalogued name>[:range]` now sends a resolved star to Vimana or begins
  local drive for a named planet belonging to the currently reached system.
  `CAT <catalogued name>[:X..Y]` reads the original 48,376-record Galactic
  Guide with its source one-based ranges and 21-column word wrapping.
  `CAST <catalogued name>:<notes>` appends a source-compatible 84-byte record
  after the consolidated guide boundary. Notes are limited to 76 characters,
  persist in `GUIDE.BIN`, and are readable by a later `CAT` command.
  `REP <catalogued name>:<record>:<notes>` corrects a selected local record
  while retaining the original module's protection for consolidated entries.
  `DELE <catalogued name>[:X..Y]` applies the original `Removed:` tombstone to
  ranged local entries and reports total, removed, and protected counts.
  `CLEAN` compacts tombstones from both mutable databases and preserves the
  consolidated source boundary separately from appended player data.
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
- Version 15 saves retain those PFS settings and the navigation heading in
  addition to local flight, settled capsule, and visual preferences; v1 through
  v14 saves migrate without stranding the player or losing their
  established defaults.

## Run it

Extract the ZIP without removing individual files, then double-click
`Play Noctis IV.cmd`. The launcher keeps assets, `CURRENT.LIN`, `CURRENT.BAK`,
the mutable `STARMAP.BIN`, mutable `GUIDE.BIN`, and diagnostics in the
extracted game folder.

Useful controls:

- W/A/S/D: move; right-drag or arrows: look
- E inside the Stardrifter: ascend; walk into the roof opening to return
- First wall panel + Enter: physical GOES; `NEXT`: choose/fly to a nearby star
- Bare `SL`: list all known stars; Home/End/Page Up/Page Down: scroll output
- `CAT`: read; `CAST`: add; `REP`: correct; `DELE`: remove; `CLEAN`: compact
- Third wall panel + Enter: approach, select a landing site, and descend
- G and L: accessible GOES and landing fallbacks
- R: device back/close aboard ship; return in capsule on a surface
- F2: visual effects; Page Up/Down: visor; F4: FPS display; F5: higher presentation rate
- F6/F7: save/load; F8: music; F9 or `?`: complete control card
- Esc: save and quit

## Known limitations

- Windows is the supported packaged platform. The historical Linux runtime's
  PCM layer is a stub, so soundtrack support is Windows-only.
- The second physical GOES face retains command output with source-equivalent
  line, page, and end scrolling.
- The Stardrifter halogen follows `alogena()`'s actual non-occluded flare path,
  removing the dark-hull center test that made it flicker on and off.
- Higher-rate presentation now interpolates ordinary Stardrifter and settled
  surface movement/look without changing the original 18.206 Hz simulation.
  Surface wave feedback is forwarded once into the restored live pose;
  animated capsule descent/ascent retains source-tick presentation.
- Planetary daylight now renders the original active-sun disc and corona with
  latitude/exposure placement, dawn/dusk direction, rain and night gating,
  and the correct companion-star radius in multiple systems. A nearby
  companion also appears as the original independently positioned secondary
  sun, including the source's owner-role swap and separate terminator.
- Eligible surface suns now carry their original additive lens flares after
  terrain, including distance, weather, star-class, phase, and center-occlusion
  gates. Resolved star globes use source-generated class-specific spin instead
  of rotating every presentation frame.
- Full Noctis IV+ feature parity remains the release criterion. Historical
  screens, complete GUI behavior, and presentation details are still being
  implemented rather than cut from scope. Stellar lithium collection and
  emergency depletion recovery are live gameplay systems.

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
