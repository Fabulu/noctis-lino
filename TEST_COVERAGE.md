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
| Floating-point and transcendental boundary | Exact import/export, signed zero, subnormals, overflow, one-ULP mathematical grading, 4,113 historical catalogue rows, all 16 spill schedules, zero x87 TOP drift, 45 production-consumer checks, zero production target blocks, the exact 36-operation ordinary-float inventory, a model-vs-x87 audit of all 9,564,210 reachable fractional-crater-power pairs, and 4,096 compiled-Lino boundary cases | Generated Windows PEs receive the fail-closed post-link `FCWEXT=133Fh` patch while all eight protected runtime variants retain their upstream bytes; Linux and macOS assembly pin their own loads, and a real x86_64 perturb/load/read/restore probe is wired on Intel macOS and Rosetta but still awaits both hosted runs |
| NIVGEN public accuracy | Canonical 5,188-row snapshots distinguish visible zero-error markers from independently comparable hashes; a retained complete offline run scores all 49,823 authoritative fields on 4,546 rows, reaching 49,774 exact fields and 4,513 exact rows; `test_nivgen_precision.py` pins the NIVGEN-only binary64 geometry mode while `test_nearstar.py` retains historical game behavior | Production Rosetta has a 7/7 sector smoke; Windows native score children run on private inactive desktops; the remaining 49 fields are explicitly classified rather than omitted |
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
python tests\test_floatcontract.py
python tests\test_fp_runtime_boundary.py
python tests\test_fractional_pow.py
python tests\test_fractional_pow.py --deep  # model vs x87 on all 9,564,210 pairs; Lino uses 4,096 cases
python tests\test_geoconv_zero.py
python tests\test_suseed_zero.py
python tests\test_grnd_zero.py
python tests\test_nivgen_sheet_report.py
python tests\test_nivgen_score.py
python tests\test_nivgen_precision.py
powershell -File tools\capture_noctis_scenes.ps1 -Scene all
python tests\run_all.py  # 36 registered; run the complete gate before release
```

The retained complete NIVGEN run covers all 49,823 authoritative fields on 4,546
comparable rows: 49,774 field comparisons and 4,513 rows are exact, versus
38,893 fields and 426 rows in the sheet snapshot. Types 0, 6, 7, 8, 9, and 10
are completely exact; every orbital surface and palette is exact. The 49
remaining fields are 24 type-3 atmospheres, three non-XENOFELYS type-3 random
skies, and 22 landed fields across six XENOFELYS bodies. The precision gate
proves the public binary64 geometry boundary without changing the default
historical game schedule. Full corpus parity remains required before release.

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
