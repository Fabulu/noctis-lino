# FUEL TWO class-6 orbital-primary suppression oracle

This directory retains the matched NIV+ and shipping-product evidence used by
`tests/test_orbitprimary_class6_oracle.py`. FUEL TWO at
`(-125712,-174213,-150246)` is an authentic class-6 star with ray
`5.129000186920166`, spin zero, and no generated bodies (`nop=0`, `nob=0`). It
therefore has no authentic surface checkpoint: this oracle is an untargeted
Stardrifter exterior view, not a synthetic planet pose.

## Retained artifacts

| File | Bytes | SHA-256 |
|---|---:|---|
| `native.CURRENT.BIN` | 385 | `fdc3a60686e73dab58ef2c5ea6b8540d0f4b5760fc1ae6fe44a14afc4c666beb` |
| `native-capture.cmd` | 82 | `3de94c13c72b31f0fc2df95e07fa53176b3a72e11f1d4ff1634805408cb19b93` |
| `native.shot.BMP` | 65,078 | `c24d13d64ca86f8b6ec975455752b771f87717c3425a47dea2b5e6c95bf6befa` |
| `native.adapted` | 65,540 | `7514c719a671b0bfae39e87cd540a32ff5a8e6504e20d9c033a3e67baea7385f` |
| `native-continuity.bin` | 245 | `e0b7bb2124d2da8ec3f4150acbe808c3f2301c0c62e1df78041771fd1c78af02` |
| `product-vh.bin` | 156 | `95eac6c93ff64af0585aa447ae6a8aedf10971336b5f83ecf700b535f6d8aac5` |
| `product-palette.bin` | 3,072 | `bbcd3ab1be0c88fc151b25c541c94ce9f57b862218d7c13efdd8fe55cbdae821` |
| `product-page.bin` | 64,000 | `7add23f58bec10341faf4a6ace7b0eacda5aff857cf198b4c6f2045c1f631b26` |
| `provenance.json` | 8,894 | `d66f1e8fcb40c07c367f311a6b99438f2e79d020bd1280ad06103f360d361372` |

The BMP's top-down indexed page hashes to
`2f679a47a4f80119720fdccb4663df4bdb71f5cc06284181965a7a22088b931f`;
its packed 256-entry six-bit RGB palette hashes to
`15c34e0e8a53b47986cc835782e6ef106c3d88cb91027d53d3b819bb3fd9a989`.
The 245-byte continuity record was extracted at the unique continuity-block
offset 206,300 from a 16-MiB frozen RAM image whose SHA-256 is
`305e7d4a6485b5dac3e667a93aefe62498b0fa8599e6009bebc17ea87b998cea`.
The full RAM image is capture-only and is not retained.

## What this proves

The Stardrifter is at `(2813,0,-1397)`, pitch 0, user beta 23, navigation beta
0. Source exterior projection therefore uses beta `23 + 0 + 180 = 203`. The
retained Dzat places the star 256.45 units away before the source's `+1`
adjustment, producing `l_dsd=257.45000000000874`. The strict orbital primary
gate is distance-positive:

```text
6 * ray < l_dsd < 1000 * ray
30.774001121520996 < 257.45000000000874 < 5129.000186920166
```

It also lies strictly between 8 and 100 stellar radii, so the source draws the
white disc/corona without a textured globe. Class 6 is then excluded alongside
classes 5 and 10 before the 60-spoke radial flare. This is the orbital rule; the
surface renderer's `10*ray` lower threshold is not substituted here.

The native and product pages both contain one compact corona plus the same four
isolated background stars in the half-open search crop `[120,60,195,130]`.
Native corona: 218 nonzero-low-six pixels, inclusive bounds
`(148,92)..(166,106)`, maximum low six 59. Product corona: 206 pixels, bounds
`(148,89)..(165,103)`, maximum low six 56. Neither page contains an extended
radial component. The first 576 palette components match exactly. Every
palette band matches in both the 2,025-pixel half-open core crop
`[135,75,180,120]` and the 20,160-pixel upper strip `[0,64,320,127]`.
The native core is also byte-exact to the post-snapshot adapted page, making the
local star visual snapshot-stable despite the whole page not being atomic.

Complete native/product pages differ at 16,166 indices and 1,200 palette bands.
The BMP and post-snapshot adapted page differ at 6,648 indices and 2,217 bands.
Those complete-page counts document the authority limit; they are not equality
requirements. Product diagnostics do not retain a live orbital-distance scalar,
so the product leg derives distance from the pinned scene/Dzat and does not
claim telemetry that does not exist. No surface, selected-body, landed-body,
matched-clock HUD, or whole-page contract is asserted.

The product used clock `1344638527`; the native input used `1345723200` and
froze at `1345723229.6666667`. A recapture is unnecessary for the admitted
contracts: FUEL TWO has spin zero and no bodies, class 6 exits before flare phase
logic, and the white-corona path is clock-independent. The empirical crop and
palette-band relationships above remain the graded evidence.

## Reproduction

Generate the native continuity input from the tracked model:

```text
python tests/gen/recon_w7b/mkcurrent.py --x -125712 --y -174213 --z -150246 --target -1 --sync 0 --secs 1345723200 --pos-x 2813 --pos-y 0 --pos-z -1397 --pitch 0 --view-angle 23 --navigation-angle 0 --local-x -100.2029979010742 --local-y 0 --local-z 236.06346966787834 --out build/fuel-two-class6-primary.CURRENT.BIN
```

Then run the retained CRLF command file through the headless native capturer:

```text
python tests/gen/recon_w7b/capture_orbital_w7b.py --current build/fuel-two-class6-primary.CURRENT.BIN --command tests/native-oracles/orbital-class6-fuel-two/native-capture.cmd --name fuel_two_class6_primary --timeout 180 --poll-milliseconds 1 --cycles max
```

Capture the shipping product diagnostics on the private inactive desktop:

```text
powershell -NoProfile -ExecutionPolicy Bypass -File tools/capture_noctis_scenes.ps1 -Scene stardrifterclass6 -Fast -DiagnosticOnly -OutputDirectory build/renderer-class6-primary-candidate
```

Do not pass `-DefaultDesktop`. `provenance.json` records capture-only diagnostic
hashes, the clock distinction, exact crop metrics, and the authority boundary.
