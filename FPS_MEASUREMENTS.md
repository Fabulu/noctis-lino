# Native FPS measurements

This tracked record is updated whenever a retained native-performance checkpoint is published. It keeps healthy-host absolute measurements separate from depressed-host ABBA comparisons and rejected experiments.

## Current status

- Goal: sustained full-fidelity **60 Hz** presentation while preserving at least **18.206 Hz** authentic simulation.
- Best healthy-host presentation: **57.54962903549228 Hz**.
- Healthy-host simulation: **18.64848606376579 Hz**.
- Remaining measured gap: **2.45037096450772 Hz**.
- Current production executable: `work/vhgame.exe`, 646,594 bytes, SHA-256 `e775171d8c9e07ddd2bd8387e703a778ab7a614789b0f58d3ec01ae408f0d501`.
- The best healthy absolute result predates the current production executable. Later retained changes were accepted by controlled ABBA comparisons on the currently depressed host; depressed-host values do not replace the healthy record.

## Fixed discriminator

Unless a row says otherwise, controlled capsule measurements use:

- checkpoint clock `1344638527`;
- five-second measurement;
- last physical core (physical core 3, affinity `0xc0` on the recorded host);
- above-normal process priority;
- private inactive desktop;
- native executable built from the shared tracked Lino closure;
- 320x200 indexed full-fidelity rendering and authentic 18.206-Hz simulation.

Candidates run in Candidate A / Baseline A / Baseline B / Candidate B order. Candidate A must first preserve 18.206-Hz simulation. A candidate is retained only if both orderings win presentation throughput and process cycles per presentation, followed by synchronized exact fidelity.

## Healthy-host absolute record

| Date | Executable SHA-256 | Presentation | Simulation | Render | Terrain | Present | Cycles/presentation | Evidence |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2026-08-28 | `8ad3ad2fdc7bad34123c3987001f28062f44e39e55cd29a2801dc75ff1c5a987` | **57.54962903549228 Hz** | **18.64848606376579 Hz** | 13.591972683857533 ms | 10.581430141990426 ms | 0.7478364056237748 ms | 39,874,447.452961676 | `build/fixed-terrain-rotate-20260828/baseline-a/capsule/report.json` |

This remains the accepted healthy-host absolute record. It is not replaced by measurements from the currently depressed host.

## Latest retained ABBA checkpoint

Terrain replay cursor/count retention produced the current production executable and was accepted on 2026-08-28. These values establish a relative win on the depressed host, not a new absolute FPS record.

| Run | Presentation | Simulation | Terrain | Cycles/presentation |
|---|---:|---:|---:|---:|
| Candidate A | 36.886907174706124 Hz | 19.051479529793273 Hz | 20.143804808931186 ms | 62,064,193.807692304 |
| Baseline A | 36.23040911866477 Hz | 18.92937105638103 Hz | 20.5902728983334 ms | 62,791,225.19662921 |
| Baseline B | 35.909920876445526 Hz | 19.07080543720836 Hz | 20.777090332565777 ms | 63,604,588.56497175 |
| Candidate B | 37.105371053710535 Hz | 18.86018860188602 Hz | 20.003200418596776 ms | 61,969,457.160220996 |

- Ordering A gain: +0.656498056041354 Hz and -727,031.388936907 cycles/presentation.
- Ordering B gain: +1.195450177265009 Hz and -1,635,131.404750754 cycles/presentation.
- Synchronized indexed-page and semantic-state fidelity: exact.
- Evidence: `build/replay-register-retention-padded-20260828/result.json`.
- Published implementation: commit `409abb2` (`Retain terrain replay cursors in registers`).

## Latest evaluated experiment

The layout-stable i386m register-nonzero branch candidate was rejected on 2026-08-28. It reached a byte-exact compiler fixpoint and changed exactly 47 same-size sites, but lost both required Ordering A metrics on the depressed host.

| Run | Presentation | Simulation | Terrain | Cycles/presentation |
|---|---:|---:|---:|---:|
| Candidate A | 34.328661385334144 Hz | 18.281535648994517 Hz | 21.682032010346138 ms | 65,983,452.964497045 |
| Baseline A | 34.688013136289 Hz | 19.088669950738915 Hz | 21.438358697132614 ms | 65,931,137.1183432 |

Candidate minus baseline: -0.3593517509548556 Hz and +52,315.84615384787 cycles/presentation. Ordering B and fidelity were skipped by the binding rejection gate. No candidate code was retained. Local evidence: `build/compare-zero-backedge-20260828/result.json`.

## Publication rule

For every retained performance checkpoint, update this file in the same commit with:

1. production executable size and SHA-256;
2. healthy absolute result, or an explicit statement that it remains unchanged;
3. presentation and simulation rates;
4. render/terrain/presentation timing and cycles per presentation;
5. discriminator conditions and host classification;
6. ABBA deltas and synchronized fidelity disposition;
7. the local raw-report path and published commit identity.
