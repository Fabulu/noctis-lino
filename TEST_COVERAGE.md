# Test coverage and remaining evidence

Noctis IV is covered by a focused integrated regression, lower-level renderer
and generator tests, native Windows playtests, and reproducible production-build
screenshots. This is broad coverage, not a claim that every procedural world,
long-running state combination, or visual composition has been exhaustively
tested.

## Current coverage

| Area | Automated evidence | Native/product evidence |
|---|---|---|
| Stardrifter, movement, roof lift and cupolas | `tests/test_vhgame.py` pins controls, lift states, cupola apertures, hull order, focus-safe repaint and resize | Interior and through-window stellar-flare screenshots; resize and movement sessions in `PLAYTEST.md` |
| Capsule descent, exit, transparent shell, walk-away/re-entry, seal and ascent | Integrated source/order/state assertions and independent capsule-gate models | `screenshots/planet-surface.png`; complete landing/return sessions in `PLAYTEST.md` |
| Planet classes, terrain, water, weather and suns | All accepted class arms, terrain bounds, daylight, secondary suns, reflections, waves and storms | Lunar/dense/thin/frozen gallery plus dry-cell sun scene; native sessions in `PLAYTEST.md` |
| Trees, hoppers/mammals and birds | Generation, source branch-stack tree shapes, three mammal morphs/gaits, bird flight/stalking/capture and persistence | Habitable sun/fauna screenshot and the bird capture/reload session in `PLAYTEST.md` |
| Jump and NIV+ jetpack | Gravity, jump/hold-thrust/cancel/descent and landing state assertions | Hardware-key jetpack session recorded in `PLAYTEST.md` |
| Historical ruins and Suricrasian Cube | All six source ruin styles, three historical systems, Cube footprint and marked wall rows/columns | Marked triangular-silhouette ruin and elevated Cube-wall screenshots |
| GOES, Guide, starmap and devices | Integrated command, parsing, persistence, file, power, lithium and rescue checks | Physical-console screenshots and native sessions |
| Save/load and distribution | Version 1-15 migration, version 16 state, backup recovery, Windows and macOS package assembly, internal manifests, protected-source checks, macOS signature/Mach-O/payload validation, and mutable-resource tests | Corrupt-primary recovery and packaged-launch sessions in `PLAYTEST.md`; Rosetta close/Quit smoke writes a nonempty `CURRENT.LIN` |
| Long-duration loop | 600,000 integrated build/flight/render/present frames, exact terminal telemetry and clean exit over 2 h 15 min | 189.8-second standalone Windows bundle session with 43/43 responsive probes and stable memory/handles |
| macOS x86_64 | Intel-hosted Cocoa/headless RTM builds; Apple-Silicon runtime provenance; Linux fixpoint cross-build; Rosetta NIVGEN 7/7; extracted manifest/signature, launcher, first-retrace, and graceful-quit checks | Development and public beta 22 archives independently downloaded/audited; end-to-end product smoke runs through Rosetta 2 |
| CI/CD | Hosted focused regression, source builds, snapshot packages, exact Rosetta app package, and six-asset tagged prerelease graph; separate interactive source-build workflow | Windows, Intel-macOS runtime, and Apple-Silicon package workflows are green; no `lino-gui` runner is registered, so the optional independent Win32 compiler-host artifact is unavailable |

## Commands

```powershell
python tests\test_vhgame.py
powershell -File tools\capture_noctis_scenes.ps1 -Scene all
python tests\run_all.py  # explicit deep/release audit, not a routine gate
```

## Honest gaps

- Procedural generation makes exhaustive visual enumeration impossible; the
  gallery uses known dry cells and representative classes.
- Pixel appearance, focus switching, live input timing, sound, and resizing retain
  native Windows evidence plus bounded Cocoa smokes; they are not exhaustively
  replayed across every supported Windows and Mac host on every change.
- The complete macOS app smoke is proven on Apple Silicon through Rosetta 2.
  Intel CI builds both runtimes but does not yet run the extracted game package;
  native ARM64 does not exist yet.
- Multi-hour integrated stability is covered; multi-hour real-input travel,
  rescue, soundtrack, resize, and every preference combination are not
  exhaustively replayed on every change.
- No finite gallery can show every generated star, world, ruin, animal, weather
  state, viewing angle, or preference combination. The checked-in images are
  reproducible representative evidence, not golden-image tests.

`PLAYTEST.md` is the detailed evidence log. `CI_RELEASES.md` documents what
hosted CI can prove and the separate interactive source-build boundary.
