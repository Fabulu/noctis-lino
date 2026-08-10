# Noctis IV L.in.oleum port -- 0.1.0 beta 1

This is the first public playable Windows build of the Noctis IV L.in.oleum
port. It is a beta: the complete core journey is playable, while extended
multi-hour hardening and some historical screens remain future work.

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
- The lift activates with E only while centered in its aperture. Up remains a
  look control; walking into the roof opening starts the original automatic
  return, and pressing E elsewhere gives visible guidance.
- Version 11 saves retain settled capsule coordinates, and older landed saves
  migrate without stranding the player away from the pod.

## Run it

Extract the ZIP without removing individual files, then double-click
`Play Noctis IV.cmd`. The launcher keeps assets, `CURRENT.LIN`, `CURRENT.BAK`,
the mutable `STARMAP.BIN`, and diagnostics in the extracted game folder.

Useful controls:

- W/A/S/D: move; right-drag or arrows: look
- E while centered in the Stardrifter aperture: ascend; walk into the roof
  opening to return
- G or Enter: GOES; `NEXT`: choose/fly to a nearby star
- L: approach, choose landing site, and descend
- R: device back/close aboard ship; return in capsule on a surface
- F4: FPS display; F5: higher presentation rate
- F6/F7: save/load; F8: music; F9 or `?`: complete control card
- Esc: save and quit

## Known limitations

- Windows is the supported packaged platform. The historical Linux runtime's
  PCM layer is a stub, so soundtrack support is Windows-only.
- A multi-hour session spanning repeated resize/full-view changes, many
  landings, and extended audio remains the principal release-hardening gap.
- This is a faithful playable port in active development, not a claim that
  every original Noctis IV screen or incidental behavior is complete.

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
