# Positive orbital-primary class gallery

This directory retains matched NIV+ and shipping-product evidence used by
`tests/test_orbitprimary_positive_gallery.py`. It closes the ordinary positive
orbital-primary class set that was missing after the standalone EMPTY class-0
and WIRE class-7 checkpoints: classes 1, 2, 3, 4, 8, and 9. Every selected
catalogue star is an authentic bodyless system (`nop=0`, `nob=0`), so these are
untargeted Stardrifter exterior views rather than synthetic planet or surface
poses.

## Cases

| Directory | Star | Coordinates | Class | Ray | Spin | Authored distance | Retained source `l_dsd` |
|---|---|---|---:|---:|---:|---:|---:|
| `class1-ybarra` | YBARRA | `(5476048,-5957484,82716)` | 1 | `19.466999053955078` | 0 | `973.3499526977539` | `974.3499526976742` |
| `class2-eogilie` | EOGILIE | `(4265328,-5738799,2583670)` | 2 | `0.4819999933242798` | 3 | `24.09999966621399` | `25.099999666341578` |
| `class3-redian` | REDIAN | `(4700336,-4332862,233642)` | 3 | `20.06599998474121` | 0 | `1003.2999992370605` | `1004.2999992371516` |
| `class4-marrin` | MARRIN | `(-1325712,773546,757027)` | 4 | `18.986000061035156` | 0 | `949.3000030517578` | `950.3000030518166` |
| `class8-solo` | SOLO | `(3844976,-4358971,1862310)` | 8 | `4.546999931335449` | 0 | `227.34999656677246` | `228.3499965668031` |
| `class9-akyaasle` | AKYAASLE | `(-1150000,2650000,1050000)` | 9 | `8.9399995803833` | 0 | `446.99997901916504` | `447.99997901923007` |

The common camera is `(2813,0,-1397)`, pitch 0, user beta 23, and navigation
beta 0. Source exterior projection therefore uses beta
`23 + 0 + 180 = 203`. Each authored primary is 50 stellar radii from Dzat.
After the source's `+1` adjustment, every case remains strictly inside both:

```text
6 * ray < l_dsd < 1000 * ray       radial-flare interval
8 * ray < l_dsd < 100 * ray        white-corona/no-globe interval
```

Classes 1, 2, 3, 4, 8, and 9 are not among the explicit 5/6/10 source
exclusions, so all six admit the ordinary 60-spoke flare. The class-11 phase
gate does not apply. EOGILIE's catalogue spin of 3 therefore does not weaken
this phase-static contract.

## Retained artifacts

Each case directory contains the same immutable eight-file set:

| File | Bytes | Role |
|---|---:|---|
| `native.CURRENT.BIN` | 385 | Authored untargeted native continuity input |
| `native-capture.cmd` | 82 | CRLF native date/time and silent-launch command |
| `native-continuity.bin` | 245 | Live post-snapshot continuity extracted at RAM offset 206,300 |
| `native.adapted` | 65,540 | Post-snapshot native adapted page record |
| `native.shot.BMP` | 65,078 | Complete indexed native capture and active six-bit palette |
| `product-vh.bin` | 156 | Warmed product camera and stellar-state diagnostic |
| `product-palette.bin` | 3,072 | Warmed product six-bit RGB palette diagnostic |
| `product-page.bin` | 64,000 | Warmed product final indexed page diagnostic |

`provenance.json` pins the size and SHA-256 of all 48 retained case artifacts,
the top-down native page and packed six-bit palette hashes, the capture-only
16-MiB RAM hashes, authored and frozen continuity, product clocks and
capture-only diagnostic hashes, exact comparisons, and authority limits. The
full RAM images and the remaining product diagnostics are capture-only and are
not retained here.

## What this proves

The inclusive flare crop `(120,60)..(195,115)` contains 4,256 pixels. Every
case has zero native/product palette-band differences across that complete crop;
all six native crop-band streams share SHA-256
`54f421304ba7e5d7a91209dd2f5f42769db4c430e4849ea47b596c5b615a9fda`.
The BMP and post-snapshot adapted page also differ by zero crop bands and by
only two through six crop indices. This makes the local positive-flare
structure stable even though the surrounding snapshot is not atomic.

The table below grades low-six intensity 40 or above. `Core` is the largest
8-connected component in the flare crop; isolated one-pixel satellites are
retained separately in provenance. This prevents an unrelated or detached
bright sample from inflating the centred-corona bounds.

| Class | Native/product threshold pixels | Native core pixels/bounds | Product core pixels/bounds | Exact palette prefix |
|---:|---:|---|---|---:|
| 1 | 163 / 162 | 162, `(150,91)..(165,106)` | 161, `(149,89)..(164,103)` | 203 |
| 2 | 164 / 163 | 163, `(150,91)..(165,106)` | 162, `(149,89)..(164,103)` | 281 |
| 3 | 111 / 108 | 111, `(151,94)..(163,106)` | 108, `(150,92)..(162,102)` | 201 |
| 4 | 164 / 163 | 162, `(150,91)..(165,106)` | 161, `(149,89)..(164,103)` | 201 |
| 8 | 162 / 161 | 161, `(150,91)..(165,106)` | 160, `(149,89)..(163,103)` | 281 |
| 9 | 159 / 152 | 159, `(150,92)..(165,106)` | 152, `(149,89)..(164,103)` | 284 |

Native and product independently retain a centred bright component for every
eligible class, while the exact crop-band contract protects the full radial
morphology. The class-specific palette-prefix lengths protect colour setup
without claiming equality for easing state that the native snapshot did not
retain.

Complete native/product pages differ at 27,173 through 30,753 indices and 1,200
palette bands. BMP/post-snapshot adapted pages differ at 6,543 through 26,155
indices and 2,217 through 19,841 bands. Those exact per-case counts and bounds
are provenance, not equality requirements. Product mode-0 diagnostics do not
retain a live orbital-distance scalar, so the product leg authenticates the
pinned camera, Dzat X, class, ray, and zero-body state without inventing
telemetry. No selected-body, surface, landed, matched-clock HUD, exact
whole-page, or product live-distance contract is asserted.

The native input clock is `1345723200`; frozen native times are around
`1345723229`. Warmed product UTC diagnostics differ by case and do not match the
native clock. This is admissible because none of these six ordinary classes has
the class-11 phase gate. The empirical crop bands, native continuity, and
independently pinned bright components remain the graded evidence.

## Reproduction

Generate each native input with the tracked continuity builder. All cases use:

```text
--target -1 --sync 0 --secs 1345723200 --pos-x 2813 --pos-y 0 --pos-z -1397 --pitch 0 --view-angle 23 --navigation-angle 0 --local-y 0
```

Substitute the case-specific star and local offsets:

| Case | `--x --y --z` | `--local-x --local-z` |
|---|---|---|
| YBARRA | `5476048 -5957484 82716` | `-380.3181254325744 895.9733555659857` |
| EOGILIE | `4265328 -5738799 2583670` | `-9.416620066170909 22.18416666095217` |
| REDIAN | `4700336 -4332862 233642` | `-392.020540915184 923.5425187665439` |
| MARRIN | `-1325712 773546 757027` | `-370.9210614672842 873.8352601915595` |
| SOLO | `3844976 -4358971 1862310` | `-88.83272072056747 209.27677527210972` |
| AKYAASLE | `-1150000 2650000 1050000` | `-174.65680623683997 411.4656501802804` |

Run each generated CURRENT file with its retained command through
`tests/gen/recon_w7b/capture_orbital_w7b.py` using `--timeout 180
--poll-milliseconds 1 --cycles max`. Capture each corresponding product scene
with a warmed private inactive desktop, for example:

```text
powershell -NoProfile -ExecutionPolicy Bypass -File tools/capture_noctis_scenes.ps1 -Scene stardrifterclass1 -DiagnosticOnly -ClockSeconds 1345723200 -WarmupSeconds 30 -OutputDirectory build/renderer-class1-primary-warm-candidate
```

Use `stardrifterclass2`, `stardrifterclass3`, `stardrifterclass4`,
`stardrifterclass8`, or `stardrifterclass9` for the other cases. Do not pass
`-DefaultDesktop`.
