# OUTER RUN WIND class-10 orbital-primary suppression oracle

This directory retains matched NIV+ and shipping-product evidence used by
`tests/test_orbitprimary_class10_oracle.py`. OUTER RUN WIND at
`(-1027472,-5805997,-5135362)` is an authentic class-10 star with ray
`30.30500030517578`, spin zero, and no generated bodies (`nop=0`, `nob=0`). It
therefore has no authentic surface checkpoint: this oracle is an untargeted
Stardrifter exterior view, not a synthetic planet pose.

## Retained artifacts

| File | Bytes | SHA-256 |
|---|---:|---|
| `native.CURRENT.BIN` | 385 | `e4fea3d0e0a1960c73186c45a0b592f64878b0aa06632cfa77d4bd07739e9dfb` |
| `native-capture.cmd` | 82 | `3de94c13c72b31f0fc2df95e07fa53176b3a72e11f1d4ff1634805408cb19b93` |
| `native.shot.BMP` | 65,078 | `b9c0a80c5084db72be335161acd49b95f94c08a9e270eaf3f5f3b44eb5a47d31` |
| `native.adapted` | 65,540 | `22026719651f4eb0a7ac3aaf5d2d50023ee651db980129ffd3a73a159bd9836b` |
| `native-continuity.bin` | 245 | `96a209060c5904932254f82938a4edfb385eed59bcb83928bedb1321e6eed7df` |
| `product-vh.bin` | 156 | `7cf48e500490403e4a6260b6b7246d2d1cf98c88727492cc1073296938205349` |
| `product-palette.bin` | 3,072 | `3f0a8491961ddbdb7c1c0747d173e1b51867f64a2cc91691a495695de30c217a` |
| `product-page.bin` | 64,000 | `38600f5e5ebfc90bcabf95bddde0152535914b200d5437223cd1fb5c78eeac04` |
| `provenance.json` | 9,253 | `761c3d8c2fcae56cb8ed0eaf573a6697bddda9a414931dbd61d7d69c362d6945` |

The BMP's top-down indexed page hashes to
`ef231aed2b0a324d742318c17d4e1763318de95e9a3bb5a0e0a60a3d9bccaa25`;
its packed 256-entry six-bit RGB palette hashes to
`b1b04d5e518cc4f95355c25def015198afa12cc09e57d47c0f4c4165eeff319a`.
The 245-byte continuity record was extracted at the unique continuity-block
offset 206,300 from a 16-MiB frozen RAM image whose SHA-256 is
`6310f7cd1cbc26ce492768ca4c2f8761c34569a1d2bc511c9e85c3e15c41a364`.
The full RAM image is capture-only and is not retained.

## What this proves

The Stardrifter is at `(2813,0,-1397)`, pitch 0, user beta 23, navigation beta
0. Source exterior projection therefore uses beta `23 + 0 + 180 = 203`. The
retained Dzat places the star `1515.2500152586724` units away before the source's
`+1` adjustment, producing `l_dsd=1516.2500152586724`. The strict orbital
primary gate is distance-positive:

```text
6 * ray < l_dsd < 1000 * ray
181.8300018310547 < 1516.2500152586724 < 30305.00030517578
```

It also lies strictly between 8 and 100 stellar radii, so the source draws the
white disc/corona without a textured globe. Class 10 is then excluded alongside
classes 5 and 6 before the 60-spoke radial flare. This is the orbital rule; the
surface renderer's `10*ray` lower threshold is not substituted here.

The native and product pages both contain one compact corona plus the same two
isolated background stars in the half-open search crop `[120,60,195,130]`.
Native corona: 218 nonzero-low-six pixels, inclusive bounds
`(148,93)..(166,107)`, maximum low six 59. Product corona: 206 pixels, bounds
`(148,90)..(165,104)`, maximum low six 56. Neither page contains an extended
radial component. The first 576 palette components match exactly. Native and
product match every palette band in both the 2,025-pixel half-open core crop
`[135,75,180,120]` and the 20,160-pixel upper strip `[0,64,320,127]`. The native
core is also byte-exact to the post-snapshot adapted page, making the local star
visual snapshot-stable despite the whole page not being atomic.

Complete native/product pages differ at 16,283 indices and 1,200 palette bands.
The BMP and post-snapshot adapted page differ at 6,858 indices and 2,217 bands.
Those complete-page counts document the authority limit; they are not equality
requirements. Product diagnostics do not retain a live orbital-distance scalar,
so the product leg derives distance from the pinned scene/Dzat and does not
claim telemetry that does not exist. No surface, selected-body, landed-body,
matched-clock HUD, or whole-page contract is asserted.

The product was warmed for 30 seconds after requesting clock `1345723200`, but
its mode-0 UTC diagnostic was `1345701527`; the native input used `1345723200`
and froze at `1345723228.5294118`. A recapture is unnecessary for the admitted
contracts: OUTER RUN WIND has spin zero and no bodies, class 10 exits before
flare phase logic, and the white-corona path is clock-independent. The empirical
crop and palette-band relationships above remain the graded evidence.

## Reproduction

Generate the native continuity input from the tracked model:

```text
python tests/gen/recon_w7b/mkcurrent.py --x -1027472 --y -5805997 --z -5135362 --target -1 --sync 0 --secs 1345723200 --pos-x 2813 --pos-y 0 --pos-z -1397 --pitch 0 --view-angle 23 --navigation-angle 0 --local-x -592.0553484054556 --local-y 0 --local-z 1394.7949932395998 --out build/outer-run-wind-class10-primary.CURRENT.BIN
```

Then run the retained CRLF command file through the headless native capturer:

```text
python tests/gen/recon_w7b/capture_orbital_w7b.py --current build/outer-run-wind-class10-primary.CURRENT.BIN --command tests/native-oracles/orbital-class10-outer-run-wind/native-capture.cmd --name outer_run_wind_class10_primary --timeout 180 --poll-milliseconds 1 --cycles max
```

Capture the warmed shipping-product diagnostics on the private inactive desktop:

```text
powershell -NoProfile -ExecutionPolicy Bypass -File tools/capture_noctis_scenes.ps1 -Scene stardrifterclass10 -DiagnosticOnly -ClockSeconds 1345723200 -WarmupSeconds 30 -OutputDirectory build/renderer-class10-primary-warm-candidate
```

Do not pass `-DefaultDesktop`. `provenance.json` records capture-only diagnostic
hashes, the clock distinction, exact crop metrics, and the authority boundary.
