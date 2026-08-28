# Native FPS measurements

This tracked record is updated whenever a retained native-performance checkpoint is published. It keeps healthy-host absolute measurements, depressed-host ABBA comparisons, rejected experiments, and instrumentation-only evidence separate.

The retrospective tables below record every result recovered for this publication pass from retained raw reports and completed task records. Values marked as task-record summaries are rounded exactly as they were preserved there; no missing precision has been invented.

## Current status

- Goal: sustained full-fidelity **60 Hz** presentation while preserving at least **18.206 Hz** authentic simulation.
- Best retained healthy-host presentation: **57.54962903549228 Hz**.
- Healthy-host simulation: **18.64848606376579 Hz**.
- Remaining measured gap: **2.45037096450772 Hz**.
- Current production executable: `work/vhgame.exe`, 646,594 bytes, SHA-256 `e775171d8c9e07ddd2bd8387e703a778ab7a614789b0f58d3ec01ae408f0d501`.
- The healthy absolute record represents executable `8ad3ad2fdc7bad34123c3987001f28062f44e39e55cd29a2801dc75ff1c5a987`. Later retained changes were accepted by controlled ABBA comparisons on the currently depressed host; depressed-host values do not replace the healthy record.
- A rejected experimental candidate reached **57.71976341015705 Hz**, but it is not a record because it failed the reverse ordering and was never retained.

## Evidence classes

- **Healthy-host absolute:** an absolute production observation on a responsive host. This class establishes progress toward 60 Hz.
- **Depressed-host ABBA:** same-host candidate/baseline discrimination. This class can retain a relative optimization but must not replace a healthy absolute result.
- **Experimental peak:** an unretained candidate observation. It is never reported as production performance.
- **Simulation-gate failure:** Candidate A was below 18.206 Hz, so baseline, reverse ordering, and fidelity were not admitted.
- **Layout/model/attribution only:** no candidate FPS conclusion was admitted.

## Fixed discriminator

Unless a row says otherwise, controlled capsule measurements use:

- checkpoint clock `1344638527`;
- five-second measurement;
- last physical core (physical core 3, affinity `0xc0` on the recorded host);
- above-normal process priority;
- private inactive desktop;
- native executable built from the shared tracked Lino closure;
- 320x200 indexed full-fidelity rendering and authentic 18.206-Hz simulation.

Candidates run in Candidate A / Baseline A / Baseline B / Candidate B order. Candidate A must first preserve 18.206-Hz simulation. A candidate is retained only if both orderings win presentation throughput and process cycles per presentation, followed by synchronized fidelity.

## Retained healthy-host absolute milestones

| Checkpoint | Executable SHA-256 | Presentation | Simulation | Render | Terrain | Present | Cycles/presentation | Evidence |
|---|---|---:|---:|---:|---:|---:|---:|---|
| Packed-threshold Baseline A, then-record | `24d398fc2cd7b8c81222689f6f5c1e9edf886d4771532e379592b661ac8b38b2` | 54.973821989528794 Hz | 18.525976641159886 Hz | 15.071525993902453 ms | 11.76056728760782 ms | 0.8487283214656896 ms | 41,751,507.307692304 | `build/packed-depth-threshold-20260828/baseline-a/capsule/report.json` |
| Fixed-slot-rotation Baseline A, current record | `8ad3ad2fdc7bad34123c3987001f28062f44e39e55cd29a2801dc75ff1c5a987` | **57.54962903549228 Hz** | **18.64848606376579 Hz** | 13.591972683857533 ms | 10.581430141990426 ms | 0.7478364056237748 ms | 39,874,447.452961676 | `build/fixed-terrain-rotate-20260828/baseline-a/capsule/report.json` |

The first row was 5.026178010471206 Hz short of 60. The current record is 2.45037096450772 Hz short. The latter remains the accepted healthy-host absolute record.

## Historical production observations

These are useful host-state observations, not replacements for the healthy record.

| Checkpoint | Presentation | Simulation | Cycles/presentation | Classification | Evidence |
|---|---:|---:|---:|---|---|
| Task #50 production recheck | 39.603960396 Hz | 18.976897690 Hz | Not retained in task summary | Historical task-record summary; host class not preserved | Completed Task #50 record |
| Task #85 accepted square-table production recheck | 35.64880831126502 Hz | 18.944795273986557 Hz | 62,802,012.05142857 | Depressed-host absolute observation | `build/production-square-recheck-20260828/capsule/report.json` |

## Experimental healthy-host peak that was rejected

The exact 1-KiB hybrid terrain-root candidate produced a higher isolated Candidate A result than the retained record, but acceptance requires both orderings. Host conditions changed sharply before Ordering B; the evidence classes remain separate rather than being averaged.

| Run | Presentation | Simulation | Render | Terrain | Present | Cycles/presentation |
|---|---:|---:|---:|---:|---:|---:|
| Candidate A | **57.71976341015705 Hz** | 18.764022027330206 Hz | 13.829992888884002 ms | 10.678777814731673 ms | 0.7497625374158181 ms | 39,747,340.56890459 |
| Baseline A | 54.855749695245834 Hz | 18.69158878504673 Hz | 15.070758259650859 ms | 11.717779426616376 ms | 0.8233788824996393 ms | 41,838,132.825925924 |
| Baseline B | 37.76717161236771 Hz | 18.883585806183856 Hz | 24.972034587560465 ms | 19.64219180930366 ms | 1.4668690797238377 ms | 60,478,207.428571425 |
| Candidate B | 36.087758868156655 Hz | 18.864055771990976 Hz | 26.12363952020202 ms | 20.618669823232324 ms | 1.499153409090909 ms | 63,271,407.39772727 |

- Ordering A: candidate gained 2.8640137149112164 Hz and removed 2,090,792.2570213303 cycles/presentation.
- Ordering B: candidate lost 1.6794127442110565 Hz and added 2,793,199.969155848 cycles/presentation.
- Disposition: rejected after Ordering B; fidelity skipped; accepted production restored.
- Evidence: `build/hybrid-depth-root-20260828/result.json`.

## Retained ABBA checkpoints

### Terrain square lookup — Task #81

| Run | Presentation | Simulation | Terrain | Cycles/presentation |
|---|---:|---:|---:|---:|
| Candidate A | 36.86449260684626 Hz | 18.83735061778408 Hz | 20.180204517704517 ms | 61,793,284.983516484 |
| Baseline A | 35.816618911174785 Hz | 18.82930822758903 Hz | 20.317069483046136 ms | 63,828,237.01142857 |
| Baseline B | 37.12720632988436 Hz | 18.867924528301888 Hz | 19.963073448551512 ms | 60,797,699.03825136 |
| Candidate B | 41.33577682753003 Hz | 18.733455508043168 Hz | 18.048480542254808 ms | 55,401,491.37438424 |

- Ordering A: +1.047873695671477 Hz and -2,034,952.0279120877 cycles/presentation.
- Ordering B: +4.208570497645674 Hz and -5,396,207.663867123 cycles/presentation.
- Synchronized authoritative renderer/gameplay fidelity passed; baseline-controlled live-UTC telemetry differences were excluded as capture nondeterminism.
- Retained executable: `8ad3ad2fdc7bad34123c3987001f28062f44e39e55cd29a2801dc75ff1c5a987`.
- Evidence: `build/depth-square-lookup-20260828/result.json`.

### Layout-stable i386m multiply-by-200 — Task #98

| Run | Presentation | Simulation | Terrain | Cycles/presentation |
|---|---:|---:|---:|---:|
| Candidate A | 45.38021259198692 Hz | 18.806214227309894 Hz | 16.330135570715765 ms | 50,422,532.68918919 |
| Baseline A | 37.89731051344743 Hz | 18.744906275468622 Hz | 19.512840037936613 ms | 60,317,375.91935484 |
| Baseline B | 47.051696284329566 Hz | 18.780290791599352 Hz | 15.790322980690988 ms | 48,706,945.53218884 |
| Candidate B | 47.60940032414911 Hz | 18.638573743922205 Hz | 15.402947300673885 ms | 48,091,463.70638298 |

- Ordering A: +7.482902078539489 Hz and -9,894,843.230165653 cycles/presentation.
- Ordering B: +0.5577040398195408 Hz and -615,481.8258058578 cycles/presentation.
- Compiler self-hosting fixpoint, 17 exact same-size substitutions, edge semantics, synchronized indexed-page/state fidelity, and toolchain gates passed.
- Retained executable after this checkpoint: `a06008e652cc253e8a532f7f6cdb29cee20a43ac6f27cfe6dc71a2ee9a9160af`.
- Evidence: `build/i386m-fixed-mul200-codegen-20260828/result.json`.

### Layout-stable terrain replay cursor/count retention — Task #106

| Run | Presentation | Simulation | Terrain | Cycles/presentation |
|---|---:|---:|---:|---:|
| Candidate A | 36.886907174706124 Hz | 19.051479529793273 Hz | 20.143804808931186 ms | 62,064,193.807692304 |
| Baseline A | 36.23040911866477 Hz | 18.92937105638103 Hz | 20.5902728983334 ms | 62,791,225.19662921 |
| Baseline B | 35.909920876445526 Hz | 19.07080543720836 Hz | 20.777090332565777 ms | 63,604,588.56497175 |
| Candidate B | 37.105371053710535 Hz | 18.86018860188602 Hz | 20.003200418596776 ms | 61,969,457.160220996 |

- Ordering A: +0.656498056041354 Hz and -727,031.388936907 cycles/presentation.
- Ordering B: +1.195450177265009 Hz and -1,635,131.404750754 cycles/presentation.
- Synchronized indexed-page and semantic-state fidelity: exact.
- Current production executable: `e775171d8c9e07ddd2bd8387e703a778ab7a614789b0f58d3ec01ae408f0d501`.
- Evidence: `build/replay-register-retention-padded-20260828/result.json`.
- Published implementation: commit `409abb2` (`Retain terrain replay cursors in registers`).

## Rejected full-ABBA candidate

### Deferred terrain terminal-state loads — Task #92

| Run | Presentation | Simulation | Terrain | Cycles/presentation |
|---|---:|---:|---:|---:|
| Candidate A | 50.151668351870576 Hz | 18.6046511627907 Hz | 13.201962889747506 ms | 45,825,641.14516129 |
| Baseline A | 46.24159706661234 Hz | 18.741087797922184 Hz | 15.748775603895407 ms | 49,425,647.339207046 |
| Baseline B | 50.46535677352637 Hz | 18.200620475698035 Hz | 14.479662095832703 ms | 45,414,039.15983607 |
| Candidate B | 50.40816326530612 Hz | 18.775510204081634 Hz | 14.62135733079178 ms | 45,510,665.83805668 |

- Ordering A: +3.9100712852582333 Hz and -3,600,006.1940457523 cycles/presentation.
- Ordering B: -0.05719350822025149 Hz and +96,626.67822061479 cycles/presentation.
- Disposition: rejected after Ordering B; fidelity skipped; accepted production restored.
- Evidence: `build/deferred-terrain-state-20260828/result.json`.

## Rejected Ordering-A candidates

All candidates in this table passed Candidate A's 18.206-Hz simulation gate, then lost either or both required Ordering-A metrics. Reverse ordering and fidelity were skipped.

| Experiment | Candidate / Baseline presentation | Candidate simulation | Candidate / Baseline cycles/presentation | Candidate delta | Evidence |
|---|---:|---:|---:|---|---|
| Packed terrain thresholds, Task #79 | 47.227926078028744 / 54.973821989528794 Hz | 18.8911704312115 Hz | 48,448,103.17826087 / 41,751,507.307692304 | -7.74589591150005 Hz; +6,696,595.870568566 cycles | `build/packed-depth-threshold-20260828/result.json` |
| Bounded ground tint masks, Task #87 | 42.29668982427462 / 55.53327987169206 Hz | 19.0028606456886 Hz | 53,941,235.801932365 / 41,182,185.85198556 | -13.236590047417437 Hz; +12,759,049.949946806 cycles | `build/ground-tint-mask-20260828/result.json` |
| Early wide-Z denominator handoff, Task #89 | 38.508309687880015 / 40.55714870954527 Hz | 18.646128901499797 Hz | 59,530,025.510526314 / 56,560,368.78282829 | -2.048839021665252 Hz; +2,969,656.727698028 cycles | `build/early-z-handoff-20260828/result.json` |
| Fixed-slot exact terrain rotation, Task #90 | 56.477732793522264 / 57.54962903549228 Hz | 18.62348178137652 Hz | 40,620,539.15412186 / 39,874,447.452961676 | -1.0718962419700162 Hz; +746,091.701160185 cycles | `build/fixed-terrain-rotate-20260828/result.json` |
| Monotone terrain map index, Task #94 | 43.14204314204314 / 50.733496332518335 Hz | 18.72201872201872 Hz | 52,992,789.344339624 / 45,220,363.59437751 | -7.5914531904751925 Hz; +7,772,425.749962114 cycles | `build/monotone-terrain-map-index-20260828/result.json` |
| Direct-threaded terrain depth, Task #96 | 48.690671031096564 / 52.17036886081109 Hz | 18.821603927986907 Hz | 47,084,223.51680672 / 44,026,362.83984375 | -3.4796978297145245 Hz; +3,057,860.6769629717 cycles | `build/direct-threaded-terrain-depth-20260828/result.json` |
| Accounted i386m multiply-by-18, Task #103 | 35.32277710109622 / 41.11270198404582 Hz | 18.879415347137638 Hz | 64,614,391.82183908 / 55,515,525.323383085 | -5.789924882949599 Hz; +9,098,866.498455994 cycles | `build/i386m-fixed-mul18-codegen-20260828/result-accounted.json` |
| Unpadded replay register retention, Task #105 | 35.823950870010236 / 36.221444741716404 Hz | 19.037871033776867 Hz | 63,831,594.58857143 / 63,088,209.1875 | -0.39749387170616757 Hz; +743,385.4010714293 cycles | `build/replay-register-retention-20260828/result.json` |
| Layout-stable register-nonzero branches, Task #114 | 34.328661385334144 / 34.688013136289 Hz | 18.281535648994517 Hz | 65,983,452.964497045 / 65,931,137.1183432 | -0.3593517509548556 Hz; +52,315.84615384787 cycles | `build/compare-zero-backedge-20260828/result.json` |
| Direct-B absolute replay pointer, Task #115 | 34.16717510677242 / 36.87590636005801 Hz | 18.91397193410616 Hz | 66,846,338.678571425 / 62,043,054.38764045 | -2.70873125328559 Hz; +4,803,284.290930979 cycles | `build/replay-direct-b-pointer-20260828/result.json` |

## Candidate-A simulation-gate failures

Baseline A, Ordering B, and fidelity were skipped under the binding stop rule.

| Experiment | Candidate presentation | Candidate simulation | Terrain | Cycles/presentation | Evidence |
|---|---:|---:|---:|---:|---|
| Pure-Lino dual publication, Task #70 | 40.479140850888065 Hz | 18.174308137133416 Hz | Not retained in summary | 56,692,015.81122449 | `build/pure-lino-dual-publication-20260827/result.json` |
| Layout-stable i386m multiply-by-320, Task #100 | 36.4405073485001 Hz | 18.11958928930944 Hz | 20.48425306637529 ms | 62,548,029.81767956 | `build/i386m-fixed-mul320-codegen-20260828/result.json` |
| Absolute replay stream pointer in A, Task #108 | 34.63203463203463 Hz | 18.140589569160998 Hz | 21.13248357827206 ms | 65,268,425.14880952 | `build/replay-absolute-pointer-20260828/result.json` |
| Combined replay decrement/backedge, Task #110 | 37.98994974874372 Hz | 18.09045226130653 Hz | 19.53835273995132 ms | 60,143,173.4021164 | `build/replay-combined-backedge-20260828/result.json` |
| 64-byte-aligned direct-B replay pointer, Task #116 | 36.880290205562275 Hz | 18.137847642079805 Hz | 20.01978055772834 ms | 61,625,879.96721312 | `build/replay-aligned-b-pointer-20260828/result.json` |

## Pre-timing and attribution results

These results informed optimization selection but are not candidate FPS measurements.

| Task | Result | Disposition | Evidence |
|---|---|---|---|
| #64, complete tile-admission/material stage attribution | 0.5796 ms/presentation; 95% CI 0.5473-0.6119; 18.899-Hz simulation | Below admission gates; no candidate | `build/tile-admission-diagnostic-20260827/result.json` |
| #66, exact viewport-mask body attribution | 0.3730 ms/presentation; 95% CI 0.3686-0.3774; 18.872-Hz simulation | Below admission gates; no candidate | `build/viewport-mask-diagnostic-20260827/result.json` |
| #69, leaf-call inlining screen | Full selected body had only a 0.71159-ms 95% upper bound | Call overhead necessarily smaller; no implementation | `build/leaf-inline-selection-20260827/result.json` |
| #102, initial i386m multiply-by-18 localization | Three substitutions found while only two source sites had been proved | Timing skipped; later accounted by Task #103 | `build/i386m-fixed-mul18-codegen-20260828/result.json` |
| #112, paired replay records | Candidate body was at least 30 generated bytes beyond the accepted downstream boundary | Exact-layout gate failed; timing skipped | `build/replay-paired-records-20260828/result.json` |

## Publication rule

For every retained performance checkpoint, update this file in the same commit with:

1. production executable size and SHA-256;
2. healthy absolute result, or an explicit statement that it remains unchanged;
3. presentation and simulation rates;
4. render/terrain/presentation timing and cycles per presentation;
5. discriminator conditions and host classification;
6. ABBA deltas and synchronized fidelity disposition;
7. the local raw-report path and published commit identity when known.

Rejected trials that materially affect optimization selection should also be appended in their correct evidence class, without replacing retained records.
