# Thin-world native sun oracle

This directory retains byte-for-byte copies of the certified NIV+ type-5
surface capture used by `tests/test_sun_gallery.py --case thin-sun45`.

- `native.shot.BMP`: SHA-256
  `a8e94775d1d4b7d7e4817088116d716a43e42b2b456c4734125430e1714de93b`
- `native.SURFACE.BIN`: SHA-256
  `8e63c9ed2d588f2fe642ef4cf184e833edea251572b376a8a8700b1a09aabe2f`

The files were copied without transformation from the retained capture files
`tests/gen/recon_w7b/out/thin_sun45_pinned_oracle.shot.BMP` and
`tests/gen/recon_w7b/out/thin_sun45_pinned_oracle.SURFACE.BIN`. The surface
record pins body longitude 45, latitude 60, player `(1645000, 1, 1641000)`,
pitch -30, and heading 90. The BMP yields the exact indexed-page SHA-256
`b9c33fba1389c3244634f9e3bca7c91b63eb7657678060e6cfec74df39d22812`
and active six-bit palette SHA-256
`5c4f3d10d756593012618d64d217327241559de094ce351b9f9faf15a9de94a2`.

The native rig did not retain snapshot-time camera, simulation, and HUD state.
Consequently the complete final BMP page is not a same-state product target.
The automated product gate grades only the contracts supported by the retained
bytes and matched deterministic lighting state: camera, all 768 palette
components, every pixel's palette band, flare-centre index, flare gate,
exposure, solar distance, and stellar ray. Complete-page equality remains
informational until a new native capture retains the missing live state.
