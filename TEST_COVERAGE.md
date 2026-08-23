# Test coverage and remaining evidence

Noctis IV is covered by a focused integrated regression, lower-level renderer
and generator tests, native Windows playtests, and reproducible production-build
screenshots. This is broad coverage, not a claim that every procedural world,
long-running state combination, or visual composition has been exhaustively
tested.

## Current coverage

| Area | Automated evidence | Native/product evidence |
|---|---|---|
| Stardrifter, movement, roof lift and cupolas | `tests/test_vhgame.py` pins controls, lift states, cupola apertures, hull order, focus-safe repaint and resize, the four source smoothing rates and formatting for the lower environmental row, its `draw_hud` gate, source-ordered in-place diffusion at all four visor lamps, and the black absent-moon palette bootstrap; `tests/test_orbitlunar_oracle.py` pins the strict one-unit interior/roof branch, the 69-pixel normalized `GRAVITY`/lamp-fringe mask, and all 192 exact black moon-band components in a planet state | Retained native inside/roof captures plus private-desktop product pairs prove the product's 28-by-5 environmental crop is byte-identical to native in both modes; a fresh pair reduces the complete active-palette mismatch from 241 to 54 components by removing all 187 erroneous nonzero moon-band components. Whole-row numerical-state and complete-palette equality remain unclaimed because the retained runs have different smoothing and palette-easing histories. Interior and through-window stellar-flare screenshots, resize, and movement sessions remain in `PLAYTEST.md`. |
| Target labels and direct editing | Static source/order checks plus `tests/test_label_editing_runtime.py` on a private inactive desktop prove star/body ownership, exact mutation and persistence, physical-Escape cancellation while held through another capture, observed latch clearing after release, byte-exact player-local removal, native `EXTANT`/`DENIED` duplicate/protection results, a byte-identical full-page blink-cycle recurrence, and same-phase fixed-position cursor movement confined to the old/new underscore rasters | The retained cupola-boundary oracle authenticates the fixed source label cameras and the runtime gate records exact STARMAP and complete 64,000-byte cursor-raster outcomes without using the interactive desktop |
| Capsule descent, exit, transparent shell, walk-away/re-entry, seal and ascent | Integrated source/order/state assertions and independent capsule-gate models | `screenshots/planet-surface.png`; complete landing/return sessions in `PLAYTEST.md` |
| Planet classes, terrain, water, weather and suns | All accepted class arms, terrain bounds, daylight, secondary suns, reflections, waves and storms | Lunar/dense/thin/frozen gallery plus dry-cell sun scene; native sessions in `PLAYTEST.md` |
| Floating-point and transcendental boundary | Exact import/export, signed zero, subnormals, overflow, one-ULP mathematical grading, 4,113 historical catalogue rows, all 16 spill schedules, zero x87 TOP drift, 45 production-consumer checks, zero production target blocks, the exact 36-operation ordinary-float inventory, a model-vs-x87 audit of all 9,564,210 reachable fractional-crater-power pairs, and 4,096 compiled-Lino boundary cases | Generated Windows PEs receive the fail-closed post-link `FCWEXT=133Fh` patch while all eight protected runtime variants retain their upstream bytes; Linux and macOS assembly pin their own loads, and the real x86_64 perturb/load/read/restore probe passed hosted Intel run 32556467204 and tagged Apple-Silicon/Rosetta run 32555351033 |
| NIVGEN public accuracy | Canonical 5,188-row snapshots distinguish visible zero-error markers from independently comparable hashes; retained complete evidence scores all 49,823 authoritative fields on 4,546 rows, with historical game semantics at 49,771 fields/4,512 rows and public-artifact compatibility semantics at 49,801 fields/4,540 rows; `test_nivgen_precision.py` pins the request-scoped 30-field divergence while `test_nearstar.py` retains historical game behavior | Production Rosetta has a 7/7 sector smoke; Windows native score children run on private inactive desktops; the remaining 22 fields are explicitly classified rather than omitted |
| Trees, hoppers/mammals and birds | Generation, source branch-stack tree shapes, three mammal morphs/gaits, bird flight/stalking/capture and persistence | Habitable sun/fauna screenshot and the bird capture/reload session in `PLAYTEST.md` |
| Jump and NIV+ jetpack | Gravity, jump/hold-thrust/cancel/descent and landing state assertions | Hardware-key jetpack session recorded in `PLAYTEST.md` |
| Historical ruins and Suricrasian Cube | All six source ruin styles, three historical systems, Cube footprint and marked wall rows/columns | Marked triangular-silhouette ruin and elevated Cube-wall screenshots |
| GOES, Guide, starmap and devices | Integrated command, parsing, persistence, file, power, lithium and rescue checks | Physical-console screenshots and native sessions |
| Save/load and distribution | Version 1-15 migration, version 16 state, backup recovery, Windows plus x86_64/arm64 macOS package assembly, internal manifests, protected-source checks, macOS signature/Mach-O/payload validation, and mutable-resource tests | Corrupt-primary recovery and packaged-launch sessions in `PLAYTEST.md`; both Mac package routes close through the ordinary game save path and require a nonempty `CURRENT.LIN` |
| Long-duration loop | 600,000 integrated build/flight/render/present frames, exact terminal telemetry and clean exit over 2 h 15 min | 189.8-second standalone Windows bundle session with 43/43 responsive probes and stable memory/handles |
| macOS x86_64 | Intel-hosted Cocoa/headless RTM builds; Apple-Silicon runtime provenance; Linux fixpoint cross-build; Rosetta NIVGEN 7/7; extracted manifest/signature, launcher, first-retrace, and graceful-quit checks | Public Beta 24 archive independently downloaded/audited; end-to-end product smoke runs through Rosetta 2 |
| macOS arm64 runtime and product | `test_macos_aarch64_runtime.py` validates the Darwin register bridge, complete 4-GiB `__PAGEZERO`, 96-byte image ABI, full-width runtime pointers, W^X policy, complete service workspace, 16-KiB `__LINKEDIT` normalization, exact code-signature suffix, stock-resource preservation, malformed-image refusals, GlobalK bounds/storage, AudioQueue ABI, launcher/package metadata, and the reusable native release workflow | Hosted run 32593712423 compiled and executed the compiler-owned fixture and complete Noctis game natively on macOS 15 arm64, proved all pointers above 4 GiB, exercised GlobalK write/read/destroy and audio metadata, reached a real Cocoa retrace, and completed raw plus extracted-package graceful save/quit smokes; tagged run 32595409634 repeated that product gate with tag-derived metadata, published all nine platform assets, and the public ARM64 archive independently passed checksum, safe-path, manifest, thin-architecture, bundle-version, provenance, and exact-final-image validation |
| Linux AArch64 runtime and compiler target | `test_aarch64_runtime.py` bootstraps `compiler114m.txt` to an i386m fixpoint, packs the checked runtime as an AArch64 SYS, and compiles a real Lino source without a CPU pack; that image executes moves, workspace access, all register/direct/indirect value-exchange pairings with alias-safe pointer preservation, wrapping add/subtract and low-word multiply, signed/unsigned division and remainder, two-destination signed/unsigned quotient-remainder division and low/high multiplication with tracked alias ordering, bitwise operations, logical/arithmetic shifts, variable rotates, integer inversion/negation/absolute value, scalar binary32 negation/magnitude/addition/subtraction/multiplication/division, signed binary32/integer conversion, all six floating comparisons, scalar square root, sine, cosine, partial remainder, and partial arctangent, tracked q71/q72 whole-register save/restore with a full-width WS slot and deliberately skipped saved-SP slot, aligned stack push/pop, unit-count SP adjustment, immediate-relative stack load/store, equality, signed/unsigned comparisons, bit tests, control flow, calls, and full-width isocalls above 4 GB, including register, direct-workspace, and canonical indirect-workspace forms; floating execution covers ordinary arithmetic, the minimum subnormal, overflow to infinity, signed zero, masked-invalid opposite-infinity addition, equal-infinity subtraction, zero-times-infinity multiplication, right-precedence payload/sign-preserving add/subtract/multiply NaNs, in-range ties-to-even conversion, masked-invalid/out-of-range conversion to integer indefinite, the 2^24 integer-to-binary32 boundary, ordered plus x87-compatible unordered quiet-NaN comparisons, square root of an exact square and minimum subnormal, square root of negative zero, masked-invalid negative square root, payload/sign-preserving quiet/signaling square-root NaNs, masked-invalid zero/zero and infinity/infinity division, right-precedence payload/sign-preserving division NaNs, sine and cosine of 1.0, sine of negative zero, cosine of zero, x87 raw-result behavior for finite trigonometric inputs at or above `2^63`, trigonometric infinities and quiet/signaling NaNs, positive and negative completed remainders, one-step partial remainders at exponent differences 64, 101, and 276, invalid/infinite/NaN remainder operands, and first-quadrant/axis/signed-zero/infinite/NaN arctangents with tracked `FPATAN` operand order; stack-relative nesting retains a one-unit generated-call frame, pop-all restores rewritten A-E/X slots and subsequent direct access through the restored full-width WS, indirect forms preserve pointer registers, and all memory forms retain source-before-destination and writeback semantics, while independent ABI fixtures keep seven malformed-image refusals; all 12 checks passed under QEMU in hosted run 32579864461 at `d22af14` | This proves the aligned integer/stack slice, bounded ordinary scalar binary32 arithmetic, and libm-backed bounded unary/binary transcendental bridges plus the Linux runtime bridge; it does not prove x86-compatible integer divide traps, exact FP exception-state compatibility, exact x87 trigonometric range reduction below `2^63` or observable C2/status output, x87 FPREM reduction widths other than the measured reference, or every remaining x87 exception/transcendental semantic. The separate Darwin product gate above proves the native macOS application boundary. |
| CI/CD | Hosted focused regression, source builds, snapshot packages, exact Rosetta app package, focused AArch64/QEMU execution, native Apple-Silicon product execution, and nine-asset tagged prerelease graph; separate interactive source-build workflow | Windows, Intel-macOS runtime, Apple-Silicon Rosetta/package, Linux AArch64 fixture, and native macOS arm64 product workflows are green; no `lino-gui` runner is registered, so the optional independent Win32 compiler-host artifact is unavailable |

## Commands

```powershell
python tests\test_vhgame.py
python tests\test_label_editing_runtime.py  # Windows private inactive desktop
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
python tests\test_aarch64_runtime.py  # add --require-execution with AArch64 GCC/QEMU
powershell -File tools\capture_noctis_scenes.ps1 -Scene all
python tests\run_all.py  # 45 registered; run the complete gate before release
```

The retained complete NIVGEN evidence covers all 49,823 authoritative fields on
4,546 comparable rows. Historical live-game semantics reach 49,771 exact fields
and 4,512 exact rows against the public artifacts. The validated request-scoped
compatibility composite reaches 49,801 fields and 4,540 rows, versus 38,893
fields and 426 rows in the sheet snapshot. The 30-field/28-row gain is public
artifact compatibility, not evidence that live gameplay matches those fields.
Under compatibility semantics, types 0, 6, 7, 8, 9, and 10 are completely exact
and every orbital surface, atmosphere, and palette matches. A six-shard rerun of
all 220 type-3 rows is 2,417/2,420 fields and 219/220 rows exact. The 22 remaining
fields are all landed outputs across six XENOFELYS bodies. The 30-check precision
gate proves the request-scoped binary64 geometry/atmosphere boundaries and exact
doubled half-degree seed threshold without changing the default historical game
schedule. The retained dual-score audit records all 30 transitions with zero
regressions. A private-desktop NIV+ R2.3 capture stopped at the first instruction
after `create_sky` for airless type-1 XENOFELYS 10, with the target reached and
synchronized but before ATL landed state. All 46,080 scored native sky bytes are
zero (FNV-1a `7B252DC5`), including byte 12,167, and match current Lino exactly;
the authoritative value 80 and hash `CBD77DB5` therefore arise after the native
generator return. An independent FNV/palette check also confirms three non-unique
visible-plus-two-invisible reconstructions for body 8 random sky and twelve
non-unique two-invisible-index reconstructions for body 9 default texture; these
prove image compatibility, not source bytes. A corrected single-process LR
body/site batch reproduced zero of the 22 residual targets and perturbed clean
outputs, rejecting that tested reuse order. The actual SheetBot caller is now
pinned: it starts five separate `NIVTEST.EXE` processes per body, in sorted
12-body chunks that share one DOSBox-X session. This explains the upload groups
and changes the unresolved boundary from shared C globals to persistent guest
RAM/DOS allocation state. A direct two-COM probe confirms that DOSBox-X can return
the same 65,536-byte segment to the next executable with its writer payload
intact, while a clean session returns zeros; that proves the reuse mechanism is
possible, not that NIVTEST consumes it. The ordering independently confines all
22 residuals to bodies 4--11 after the exact type-9 body 3 process group and
before the chunk reset; all later chunks are exact. Replaying body 3's exact
nonmodal 16-byte gap into body 4 changes only the object charts and matches none
of the four HM/OC targets, excluding that visible gap as the complete mechanism.
The exact DOS harness and executable remain unpublished, so acceptance still
requires same-DOSBox versus clean-DOSBox captures at the pre-hash boundary. This
discriminator does not make atmospheric gameplay sky a public-caller oracle
because those caller filters differ. Full corpus parity remains required before a
full-parity claim.

## Honest gaps

- Procedural generation makes exhaustive visual enumeration impossible; the
  gallery uses known dry cells and representative classes.
- Pixel appearance, focus switching, live input timing, sound, and resizing retain
  native Windows evidence plus bounded Cocoa smokes; they are not exhaustively
  replayed across every supported Windows and Mac host on every change.
- The complete macOS app smoke is proven on Apple Silicon through Rosetta 2.
  Intel CI builds both x86_64 runtimes but does not yet run the extracted game
  package. The checked Linux AArch64 bridge executes both independent ABI
  fixtures and a real compiler-produced image under QEMU; the native macOS
  AArch64 bridge now executes one signed compiler-produced headless fixture on
  Apple Silicon. The emitter still lacks x86-compatible integer divide traps,
  exact FP exception-state compatibility, exact x87 trigonometric range
  reduction below `2^63` and observable C2/status output, x87 FPREM widths other
  than the measured reference, and remaining exception/transcendental semantics.
  No native Cocoa application or native ARM64 Noctis build exists yet.
- Multi-hour integrated stability is covered; multi-hour real-input travel,
  rescue, soundtrack, resize, and every preference combination are not
  exhaustively replayed on every change.
- No finite gallery can show every generated star, world, ruin, animal, weather
  state, viewing angle, or preference combination. The checked-in images are
  reproducible representative evidence, not golden-image tests.

`PLAYTEST.md` is the detailed evidence log. `CI_RELEASES.md` documents what
hosted CI can prove and the separate interactive source-build boundary.
