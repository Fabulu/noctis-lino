# POE class-11 phase-positive orbital-primary oracle

This retained checkpoint closes the last eligible orbital-primary class. POE is
a generated bodyless class-11 system at `(3131408, -4623621, 1755683)` with
ray `0.2590000033378601`, spin `21`, `nop=0`, and `nob=0`. A fresh native
process and a fresh product process view its primary from 50 stellar radii in
the standard untargeted exterior pose.

Class 11 differs from the other positive classes: the historical source draws
its radial flare only while `gl_start < 90`. This evidence is deliberately
phase-aware rather than treating class 11 as phase-static.

## Why this pose is phase-positive

Both implementations initialize the phase to zero when they extract a star:

```text
historical: gl_start = 0
product:    VHTphase = VHTprevphase = VHTrenderphase = VHTspin = 0
```

The class-specific spin is then extracted, but phase advances only inside the
textured-globe path. That path requires `l_dsd < 8*ray`. This checkpoint has:

```text
ray                  = 0.2590000033378601
retained star range  = 12.950000166917533
source l_dsd         = 13.950000166917533
8*ray                = 2.072000026702881
```

Consequently neither fresh process enters the sole phase-advance path. The
render phase remains zero, strictly inside the source's class-11 positive
interval `phase % 360 < 90`, throughout the warm capture. The phase value is
source-grounded, not claimed as a directly retained diagnostic scalar.

The same distance is strictly inside both relevant geometric intervals:

```text
1.5540000200271606 < 13.950000166917533 < 259.0000033378601
2.072000026702881  < 13.950000166917533 < 25.90000033378601
```

These are respectively the orbital radial-flare interval
`6*ray < l_dsd < 1000*ray` and the white-corona/no-textured-globe interval
`8*ray < l_dsd < 100*ray`.

## Retained evidence

- `native.CURRENT.BIN`: exact 385-byte authored continuity.
- `native-capture.cmd`: exact 82-byte CRLF headless command stream.
- `native-continuity.bin`: 245 live bytes beginning at `sync`, extracted from
  RAM offset 206300 after the completed native snapshot.
- `native.shot.BMP`: native 320x200 indexed frame and six-bit palette.
- `native.adapted`: post-snapshot native work page.
- `product-vh.bin`: product camera and stellar-state diagnostic.
- `product-page.bin`: product 64,000-byte indexed frame.
- `product-palette.bin`: product 768-component six-bit palette.
- `provenance.json`: hashes, decoded state, geometric and phase gates,
  comparisons, and authority limits.

The inclusive flare crop `(120,60)..(195,115)` contains 4,256 pixels. Native,
post-snapshot adapted, and product pages retain every palette band in that
crop. At low-six intensity 40, the native/product largest eight-connected
bright components contain 160/157 pixels with bounds
`(151,91)..(165,106)` and `(150,89)..(164,103)`. Both retain the same detached
one-pixel sample at `(140,104)`. This centred radial morphology independently
authenticates that the positive class-11 branch rendered.

## Authority

The native BMP page and palette are snapshot artifacts. The continuity block
was extracted after snapshot completion, so it authenticates the live camera,
star, ray, class, and distance but is not a snapshot-atomic simulation-state
record. The product view independently authenticates camera position, Dzat X,
class 11, ray, `nop=0`, `nob=0`, and `ap_reached=1`; it does not retain a live
orbital-distance scalar.

The product UTC diagnostic differs from the native clock. That mismatch cannot
alter this class-11 result because phase is initialized at process start and
cannot advance outside the `<8*ray` globe path. Nevertheless, matched-clock
HUD and whole-page equality are not claimed. Direct phase-scalar, surface/body,
and product live-distance claims are also excluded.

Informational non-contract differences remain nonzero: native/product pages
differ at 30,632 indices and 1,200 palette bands; native BMP/post-snapshot
adapted pages differ at 18,421 indices and 11,690 bands. Local flare evidence,
not complete-page equality, is authoritative.

## Reproduction

Generate the input:

```text
python tests/gen/recon_w7b/mkcurrent.py --x 3131408 --y -4623621 --z 1755683 --target -1 --sync 0 --secs 1345723200 --pos-x 2813 --pos-y 0 --pos-z -1397 --pitch 0 --view-angle 23 --navigation-angle 0 --local-x -5.059968179146384 --local-y 0 --local-z 11.920538005834924 --out build/poe-class11-primary.CURRENT.BIN
```

Capture native evidence headlessly:

```text
python tests/gen/recon_w7b/capture_orbital_w7b.py --current build/poe-class11-primary.CURRENT.BIN --command build/poe-class11-primary.cmd --name poe_class11_primary --timeout 180 --poll-milliseconds 1 --cycles max
```

Capture product diagnostics on the private inactive desktop (never pass
`-DefaultDesktop`):

```text
powershell -NoProfile -ExecutionPolicy Bypass -File tools/capture_noctis_scenes.ps1 -Scene stardrifterclass11 -DiagnosticOnly -ClockSeconds 1345723200 -WarmupSeconds 30 -OutputDirectory build/renderer-class11-primary-warm-candidate
```
