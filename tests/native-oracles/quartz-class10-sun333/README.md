# Class-10 quartz surface suppression oracle

This directory retains the matched NIV+ and shipping-product evidence used by
`tests/test_surfaceclass10_oracle.py`. The pose is body 1, the primary-owned
landable type-8 quartz world in the BISTARIAL/SORZ class-10 system at
`(5411056,-7441017,-1775473)`: longitude 333, latitude 60, player
`(1638400,1,1638400)`, pitch -30, and heading 270.

## Retained artifacts

| File | Bytes | SHA-256 |
|---|---:|---|
| `native.CURRENT.BIN` | 385 | `bec49d24ba3bc946ea774768a96b401f7db0d0e998bc0de84a05620a7ce5d57f` |
| `native.SURFACE.BIN` | 40 | `742e907ee37d877ee6a720787d769d9aaba1723e511be9130d77221437e54d52` |
| `native-capture.cmd` | 77 | `1054cdca274994e7771f958056c4402109e8bb3b1ba8c98b493227ff5dd0f1bc` |
| `native.shot.BMP` | 65,078 | `384c61522050fb75a63994dc1569e484b769d056c671845d272b09112f68876a` |
| `product.CURRENT.LIN` | 264 | `d300e89708c8c6043cea06d4806ab3e7a9a24a236ef5f480451ae24c3667cc7c` |
| `product-vh.bin` | 156 | `f78bfc9837bc608a243018d55377287a351f366f8c0c75f075af84f8d8cdfe08` |
| `product-sun.bin` | 128 | `eeaaf19ce8d1951ee79af6d53163d331749067303c8013ea0d64f1653693f1c0` |
| `product-local.bin` | 176 | `da7a1883067a5f52b2c52349282a92a4d434af9693f9aa759e835ece5a200261` |
| `product-palette.bin` | 3,072 | `d8c5ee1c69ab373a2670511c1d020ceb66e19153873abc615270d1a6f27c7e40` |
| `product-page.bin` | 64,000 | `846a72617a070ba4ff94dc40618c410421de655d797a983de2637e33ed9e2a9d` |
| `provenance.json` | 5,418 | `0f9ed75fda4a1d39add6343cc141309a25ef695ec40d16625eb5b944ce0a7ce0` |

The BMP contains the authentic 320x200 indexed native frame. Its indexed page
hash is
`2477cfc669cbfd537321c72f262a141eec1b05c59f0b8700f5cc0f409d62f6cd`;
its packed 256-entry six-bit RGB palette hash is
`d8c5ee1c69ab373a2670511c1d020ceb66e19153873abc615270d1a6f27c7e40`.
The product frame has the same six-bit palette, the exact 572 indices in the
half-open sun crop `[145,88,171,110]`, and the same palette band for every one
of the 29,700 indices in the half-open upper-sky crop `[40,10,310,120]`.

## What this proves

The native image shows the centred white stellar disc/corona without radial
spokes. `provenance.json` retains decoded native continuity that authenticates
class 10, target 1, landed state, the camera, and source clock `1344638526.9`
after the BMP was published. Product telemetry reports distance `400.133026`
and stellar ray `30.8439999`, so the ordinary surface radial interval is
satisfied strictly:

```text
10 * ray < distance < 1000 * ray
308.439999 < 400.133026 < 30843.9999
```

Despite that in-gate distance, product radial-flare admission, centre, and
sample are all zero. Together these facts protect the source-authentic class-10
exclusion rather than a coincidental lower- or upper-distance suppression.

The evidence deliberately does **not** claim a snapshot-atomic native live
distance or complete-page equality. DOSBox-X froze after BMP publication, so
the decoded RAM is post-snapshot continuity evidence; its adapted page differs
from the BMP at 24,399 indices. Native and product complete pages differ at
9,507 indices and 621 palette bands due to terrain/HUD timing, while the
palette and authoritative crops above remain exact at their stated scopes.

## Reproduction notes

Regenerate the authored product checkpoint with:

```text
python tools/make_noctis_checkpoint.py --star-x 5411056 --star-y -7441017 --star-z -1775473 --body 1 --longitude 333 --latitude 60 --beta 270 --pitch -30 --fast tests/native-oracles/quartz-class10-sun333/product.CURRENT.LIN
```

The native runner was `tests/gen/recon_w7b/capture_orbital_w7b.py`, headless,
with a 30-second snapshot delay and the retained `native-capture.cmd`. NIV+
uses its seconds-since-1984 clock: DOS guest date `11.08.2026 22:41:37`
correctly freezes at `1344638526.9`; the naive Gregorian date `10.08.2026`
freezes exactly one source day early. Frozen RAM, the product executable, and
rendered convenience PNGs are capture-only and are not retained here; their
hashes and the authority boundary are recorded in `provenance.json`.
