# EMPTY class-0 orbital-primary flare oracle

This directory retains matched NIV+ and shipping-product evidence used by
`tests/test_orbitprimary_class0_oracle.py`. EMPTY at
`(2931408,-6222148,1891299)` is an authentic class-0 star with ray
`6.445000171661377`, spin zero, and no generated bodies (`nop=0`, `nob=0`). It
therefore has no authentic surface checkpoint: this oracle is an untargeted
Stardrifter exterior view, not a synthetic planet pose.

## Retained artifacts

| File | Bytes | SHA-256 |
|---|---:|---|
| `native.CURRENT.BIN` | 385 | `772bc1ad76fc36244bfa2398fe9c57c1a0994ab3795355d4521973831072afce` |
| `native-capture.cmd` | 82 | `3de94c13c72b31f0fc2df95e07fa53176b3a72e11f1d4ff1634805408cb19b93` |
| `native.shot.BMP` | 65,078 | `30c4ccf033a01b3d8046c31c861d457f5c28f0634eccd93f1f0c9022a52a3ced` |
| `native.adapted` | 65,540 | `3be09754365343bfd7288d82d0d27ba003bc403b397722740dc3caeea661c989` |
| `native-continuity.bin` | 245 | `d01d0c29f771a56f126426c04ab7e5e82ceaef09453c86eb16673162e3d4eef3` |
| `product-vh.bin` | 156 | `5a89fcb4362ab22468ff3b14fd8af728421ff60e7bc4ac71f7dfcdbe154b7d08` |
| `product-palette.bin` | 3,072 | `2cf1c3be9905561ca8f53afddf7b078ab23f4f993b6890ab62a9afea06babac2` |
| `product-page.bin` | 64,000 | `79ad249a665edfa49be6a9277496c62954ad60636db35c5996d43ec19aee60fd` |
| `provenance.json` | 8,354 | `dfa2a1318897bf8edfce05a1d73caac2784cdeceea4da338548b05e2418ca5db` |

The BMP's top-down indexed page hashes to
`d3d99be81f6d4a5f84b76762f30bfb313fa156e6b5e2cb21391dd0f3e020d125`;
its packed 256-entry six-bit RGB palette hashes to
`d492ce31940e0b5ae3e05ecd576d061117c9a7e3645a7c6b0fa5d6ab8f16d9b8`.
The 245-byte continuity record was extracted at the established continuity-block
offset 206,300 from a 16-MiB frozen RAM image whose SHA-256 is
`10256dc4d56acdd17a391969e98076651f2071f5972f231cd689907af98dac4e`.
The full RAM image is capture-only and is not retained.

## What this proves

The Stardrifter is at `(2813,0,-1397)`, pitch 0, user beta 23, navigation beta
0. Source exterior projection therefore uses beta `23 + 0 + 180 = 203`. The
retained Dzat places the star `322.25000858312563` units away before the source's
`+1` adjustment, producing `l_dsd=323.25000858312563`. The strict orbital
primary gate is distance-positive:

```text
6 * ray < l_dsd < 1000 * ray
38.67000102996826 < 323.25000858312563 < 6445.000171661377
```

It also lies strictly between 8 and 100 stellar radii, so the source draws the
white disc/corona without a textured globe. Class 0 is not one of the source's
5/6/10 exclusions, so the 60-spoke radial flare is admitted. This is the
orbital rule; the surface renderer's `10*ray` lower threshold is not substituted
here.

In the inclusive flare crop `(120,60)..(195,115)`, native and product retain
162 and 153 pixels at low-six intensity 40 or above. Their inclusive bounds are
`(150,91)..(165,106)` and `(149,89)..(164,103)`, respectively. Both metrics pin
a centred bright radial-flare core independently rather than demanding identical
startup phase or smoothing. All 4,256 crop pixels retain their native palette
band, the first 201 native/product palette components match exactly, and the
native BMP differs from its post-snapshot adapted page at only two crop indices
and zero crop bands. The latter makes the graded flare structure locally stable
despite the whole page not being atomic.

Complete native/product pages differ at 30,058 indices and 1,200 palette bands.
The BMP and post-snapshot adapted page differ at 6,568 indices and 2,217 bands.
Those complete-page counts document the authority limit; they are not equality
requirements. Product diagnostics do not retain a live orbital-distance scalar,
so the product leg derives distance from the pinned scene/Dzat and does not
claim telemetry that does not exist. No surface, selected-body, landed-body,
matched-clock HUD, or whole-page contract is asserted.

The product was warmed for 30 seconds after requesting clock `1345723200`, but
its mode-0 UTC diagnostic was `1345702533`; the native input used `1345723200`
and froze at `1345723227.4444444`. A recapture is unnecessary for the admitted
contracts: EMPTY has spin zero and the class-0 flare phase is static. The
empirical crop bands and independently pinned bright-core metrics remain the
graded evidence.

## Reproduction

Generate the native continuity input from the tracked model:

```text
python tests/gen/recon_w7b/mkcurrent.py --x 2931408 --y -6222148 --z 1891299 --target -1 --sync 0 --secs 1345723200 --pos-x 2813 --pos-y 0 --pos-z -1397 --pitch 0 --view-angle 23 --navigation-angle 0 --local-x -125.91310950934057 --local-y 0 --local-z 296.6326969258054 --out build/empty-class0-primary.CURRENT.BIN
```

Then run the retained CRLF command file through the headless native capturer:

```text
python tests/gen/recon_w7b/capture_orbital_w7b.py --current build/empty-class0-primary.CURRENT.BIN --command tests/native-oracles/orbital-class0-empty/native-capture.cmd --name empty_class0_primary --timeout 180 --poll-milliseconds 1 --cycles max
```

Capture the warmed shipping-product diagnostics on the private inactive desktop:

```text
powershell -NoProfile -ExecutionPolicy Bypass -File tools/capture_noctis_scenes.ps1 -Scene stardrifterclass0 -DiagnosticOnly -ClockSeconds 1345723200 -WarmupSeconds 30 -OutputDirectory build/renderer-class0-primary-warm-candidate
```

Do not pass `-DefaultDesktop`. `provenance.json` records capture-only diagnostic
hashes, the clock distinction, exact flare metrics, and the authority boundary.
