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
  vegetation, animals, capturable birds, ruins, water/ice effects, jump, and
  jetpack behavior.
- Return to the capsule and Stardrifter, manage power and lithium, collect fuel,
  or request the visible rescue sequence.
- Save and resume versioned checkpoints. Verified saves retain a backup and a
  damaged primary visibly recovers from the last-known-good copy.
- Resize the native iGUI window while the authentic 320x200 renderer remains
  nearest-neighbor scaled and aspect fitted.
- Toggle Ryan J. Bury's manual soundtrack with F8; silence remains available.

## Important behavior in this build

- The authentic 18.206 FPS presentation is the default.
- F5 opts into the higher presentation rate; simulation remains 18.206 Hz in
  either presentation mode.
- The Stardrifter is visible from the initial frame and remains stable during
  movement.
- E directly starts the source lift event while inside the Stardrifter. Up
  remains a look control, and walking into the roof cupola opening starts the
  original automatic return. The calibrated ascent retains the source's
  forward momentum through the final roof frame, carries the player clear, and
  uses the same heading for the view and ride motion.
- Facing the first right-wall computer and pressing Enter focuses physical
  GOES. The third station starts planetary approach and, after FCS reaches
  STANDBY, opens the physical longitude/latitude selector.
- Planetary views finish with the original default `surrounding()` visor
  frame. Its stable graded edge replaces both the incorrect bright sawtooth
  and the intermediate plain-black guard without changing polygon clipping.
- Version 11 saves retain settled capsule coordinates, and older landed saves
  migrate without stranding the player away from the pod.

## Run it

Extract the ZIP without removing individual files, then double-click
`Play Noctis IV.cmd`. The launcher keeps assets, `CURRENT.LIN`, `CURRENT.BAK`,
the mutable `STARMAP.BIN`, and diagnostics in the extracted game folder.

Useful controls:

- W/A/S/D: move; right-drag or arrows: look
- E inside the Stardrifter: ascend; walk into the roof opening to return
- First wall panel + Enter: physical GOES; `NEXT`: choose/fly to a nearby star
- Third wall panel + Enter: approach, select a landing site, and descend
- G and L: accessible GOES and landing fallbacks
- R: device back/close aboard ship; return in capsule on a surface
- F4: FPS display; F5: higher presentation rate
- F6/F7: save/load; F8: music; F9 or `?`: complete control card
- Esc: save and quit

## Known limitations

- Windows is the supported packaged platform. The historical Linux runtime's
  PCM layer is a stub, so soundtrack support is Windows-only.
- The second physical GOES face retains command output with source-equivalent
  line, page, and end scrolling.
- The Stardrifter halogen flare now obeys the original projected center-pixel
  occlusion test instead of leaking through hull geometry and popping at its
  edges.
- Higher-rate presentation does not yet interpolate the original 18.206 Hz
  simulation, so it is not expected to feel like a modern native 60 Hz game.
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
