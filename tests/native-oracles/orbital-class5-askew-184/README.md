# ASKEW 184 class-5 orbital-primary suppression oracle

This directory retains matched NIV+ and shipping-product evidence used by
`tests/test_orbitprimary_class5_oracle.py`. ASKEW 184 at
`(3438192,-1233198,1856484)` is an authentic class-5 star with ray
`1.4919999837875366`, spin zero, and no generated bodies (`nop=0`, `nob=0`). It
therefore has no authentic surface checkpoint: this oracle is an untargeted
Stardrifter exterior view, not a synthetic planet pose.

## Retained artifacts

| File | Bytes | SHA-256 |
|---|---:|---|
| `native.CURRENT.BIN` | 385 | `c8ce191a8ae44e50c92372aa4456591827a46525550f0bf82b273ea17561cc26` |
| `native-capture.cmd` | 82 | `3de94c13c72b31f0fc2df95e07fa53176b3a72e11f1d4ff1634805408cb19b93` |
| `native.shot.BMP` | 65,078 | `8fc168d4f0d0578ce13c4ce7ab9d2662dde00f8f8747b167ba6669f33c26f9d3` |
| `native.adapted` | 65,540 | `a0d6c236583be4f477482092a38817a55eba97e3b2d9cb431869d075a6a330c4` |
| `native-continuity.bin` | 245 | `b300a5e588dbbab4b1a4e6ebcea705a2c589d72efd93f83eb6b9f149ede71ac3` |
| `product-vh.bin` | 156 | `e7b1d0dd9591a7651554832d09df66c8e0c0eabbcd2db8ea7421c299d3553938` |
| `product-palette.bin` | 3,072 | `476fc4a6453fcde7eb6e7b907284905fb8b136a9326d517ede47e09d4cae5de1` |
| `product-page.bin` | 64,000 | `a362a0e3660a533c5a804686ce4f2a3d9972b698c0abfeff408bfc06661cfd0a` |
| `provenance.json` | 9,251 | `08dca519891aa7eaa744f612fd4d21467a15abfd274edc16eb821a4c1954677c` |

The BMP's top-down indexed page hashes to
`f3fedbd6c2ab294b2720b1c58569b7e98daf7ffed4fe794a7716fc71735f4578`;
its packed 256-entry six-bit RGB palette hashes to
`a055ef67edf7b3482ecdeefbacdb7a2615a75be5a7f871b5b56867ad0a761f6d`.
The 245-byte continuity record was extracted at the unique continuity-block
offset 206,300 from a 16-MiB frozen RAM image whose SHA-256 is
`3de62600dd6ad8b3dd58b855654979b64d38e481619eab08dcfefeb820288b87`.
The full RAM image is capture-only and is not retained.

## What this proves

The Stardrifter is at `(2813,0,-1397)`, pitch 0, user beta 23, navigation beta
0. Source exterior projection therefore uses beta `23 + 0 + 180 = 203`. The
retained Dzat places the star `74.59999918948498` units away before the source's
`+1` adjustment, producing `l_dsd=75.59999918948498`. The strict orbital primary
gate is distance-positive:

```text
6 * ray < l_dsd < 1000 * ray
8.95199990272522 < 75.59999918948498 < 1491.9999837875366
```

It also lies strictly between 8 and 100 stellar radii, so the source draws the
white disc/corona without a textured globe. Class 5 is then excluded alongside
classes 6 and 10 before the 60-spoke radial flare. This is the orbital rule; the
surface renderer's `10*ray` lower threshold is not substituted here.

The native and product pages both contain one compact corona plus the same five
isolated background stars in the half-open search crop `[120,60,195,130]`.
Native corona: 218 nonzero-low-six pixels, inclusive bounds
`(148,93)..(166,107)`, maximum low six 59. Product corona: 206 pixels, bounds
`(148,90)..(165,104)`, maximum low six 56. Neither page contains an extended
radial component. The first 576 palette components match exactly. Native and
product match every palette band in both the 2,025-pixel half-open core crop
`[135,75,180,120]` and the 20,160-pixel upper strip `[0,64,320,127]`. The native
core is also byte-exact to the post-snapshot adapted page, making the local star
visual snapshot-stable despite the whole page not being atomic.

Complete native/product pages differ at 16,265 indices and 1,200 palette bands.
The BMP and post-snapshot adapted page differ at 6,743 indices and 2,217 bands.
Those complete-page counts document the authority limit; they are not equality
requirements. Product diagnostics do not retain a live orbital-distance scalar,
so the product leg derives distance from the pinned scene/Dzat and does not
claim telemetry that does not exist. No surface, selected-body, landed-body,
matched-clock HUD, or whole-page contract is asserted.

The product was warmed for 30 seconds after requesting clock `1345723200`, but
its mode-0 UTC diagnostic was `1345700841`; the native input used `1345723200`
and froze at `1345723229.368421`. A recapture is unnecessary for the admitted
contracts: ASKEW 184 has spin zero and no bodies, class 5 exits before flare
phase logic, and the white-corona path is clock-independent. The empirical crop
and palette-band relationships above remain the graded evidence.

## Reproduction

Generate the native continuity input from the tracked model:

```text
python tests/gen/recon_w7b/mkcurrent.py --x 3438192 --y -1233198 --z 1856484 --target -1 --sync 0 --secs 1345723200 --pos-x 2813 --pos-y 0 --pos-z -1397 --pitch 0 --view-angle 23 --navigation-angle 0 --local-x -29.148541868564102 --local-y 0 --local-z 68.66966132136949 --out build/askew-184-class5-primary.CURRENT.BIN
```

Then run the retained CRLF command file through the headless native capturer:

```text
python tests/gen/recon_w7b/capture_orbital_w7b.py --current build/askew-184-class5-primary.CURRENT.BIN --command tests/native-oracles/orbital-class5-askew-184/native-capture.cmd --name askew_184_class5_primary --timeout 180 --poll-milliseconds 1 --cycles max
```

Capture the warmed shipping-product diagnostics on the private inactive desktop:

```text
powershell -NoProfile -ExecutionPolicy Bypass -File tools/capture_noctis_scenes.ps1 -Scene stardrifterclass5 -DiagnosticOnly -ClockSeconds 1345723200 -WarmupSeconds 30 -OutputDirectory build/renderer-class5-primary-warm-candidate
```

Do not pass `-DefaultDesktop`. `provenance.json` records capture-only diagnostic
hashes, the clock distinction, exact crop metrics, and the authority boundary.
