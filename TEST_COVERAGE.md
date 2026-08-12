# Test coverage and remaining evidence

Noctis IV is covered by a focused integrated regression, lower-level renderer
and generator tests, native Windows playtests, and reproducible production-build
screenshots. This is broad coverage, not a claim that every procedural world,
long-running state combination, or visual composition has been exhaustively
tested.

## Current coverage

| Area | Automated evidence | Native/product evidence |
|---|---|---|
| Stardrifter, movement, roof lift and cupolas | `tests/test_vhgame.py` pins controls, lift states, cupola apertures, hull order, focus-safe repaint and resize | `screenshots/stardrifter-interior.png`; resize and movement sessions in `PLAYTEST.md` |
| Capsule descent, exit, transparent shell, walk-away/re-entry, seal and ascent | Integrated source/order/state assertions and independent capsule-gate models | `screenshots/planet-surface.png`; complete landing/return sessions in `PLAYTEST.md` |
| Planet classes, terrain, water, weather and suns | All accepted class arms, terrain bounds, daylight, secondary suns, reflections, waves and storms | Multi-class gallery plus dry-cell sun scene; native sessions in `PLAYTEST.md` |
| Trees, hoppers/mammals and birds | Generation, source branch-stack tree shapes, three mammal morphs/gaits, bird flight/stalking/capture and persistence | Habitable sun/fauna screenshot and the bird capture/reload session in `PLAYTEST.md` |
| Jump and NIV+ jetpack | Gravity, jump/hold-thrust/cancel/descent and landing state assertions | Hardware-key jetpack session recorded in `PLAYTEST.md` |
| Historical ruins and Suricrasian Cube | All six source ruin styles, three historical systems, Cube footprint and marked wall rows/columns | Marked triangular-silhouette ruin and elevated Cube-wall screenshots |
| GOES, Guide, starmap and devices | Integrated command, parsing, persistence, file, power, lithium and rescue checks | Physical-console screenshots and native sessions |
| Save/load and distribution | Version 1-15 migration, version 16 state, backup recovery, packaging and protected upstream checks | Corrupt-primary recovery and packaged-launch sessions in `PLAYTEST.md` |
| CI/CD | Hosted focused regression, snapshot package and tagged prerelease jobs; separate interactive source-build workflow | Current `master` run is green; no `lino-gui` runner is registered, so the optional fresh-source artifact is unavailable |

## Commands

```powershell
python tests\test_vhgame.py
powershell -File tools\capture_noctis_scenes.ps1 -Scene all
python tests\run_all.py  # explicit deep/release audit, not a routine gate
```

## Honest gaps

- Procedural generation makes exhaustive visual enumeration impossible; the
  gallery uses known dry cells and representative classes.
- Pixel appearance, focus switching, live input timing, sound, and resizing
  still need native Windows evidence in addition to source/state assertions.
- Multi-hour travel, rescue, soundtrack, and every combination of preferences
  are not exhaustively replayed on every change.
- A composed Stardrifter-through-cupola stellar-flare screenshot remains open;
  the code path is covered, but the current reproducible checkpoint places the
  selected sun outside the roof view.

`PLAYTEST.md` is the detailed evidence log. `CI_RELEASES.md` documents what
hosted CI can prove and the separate interactive source-build boundary.
