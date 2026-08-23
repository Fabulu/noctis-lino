# Frozen native sun oracle

This directory retains byte-for-byte copies of the certified NIV+ type-7
surface capture used by `tests/test_sun_gallery.py --case frozen-sun0`.

- `native.shot.BMP`: SHA-256
  `1f221358d756737d349926d36e98ae8e99e71063d63c4bf577dbb7971357d01a`
- `native.SURFACE.BIN`: SHA-256
  `0e0efa5fc114a99fcae0b31f467b85dd3ef5e44849794680fd5000d9c6463154`

The files were copied without transformation from the retained capture files
`tests/gen/recon_w7b/out/frozen_sun0_pinned_oracle.shot.BMP` and
`tests/gen/recon_w7b/out/frozen_sun0_pinned_oracle.SURFACE.BIN`. The surface
record pins body index 9 in the selected class-1 system at longitude 0,
latitude 60, player
`(1645000,1,1641000)`, pitch -44, and heading 90. The BMP yields indexed page
SHA-256
`f7fc6e9f84073f145e4648f697840afdbd79a04c703aa76957bcc665636ebe96`
and six-bit palette SHA-256
`843334d0b9ac9a7f013810ed80ca46da5b98c2f5f497a7ff7f265371d1f56824`.

The product gate requires all 64,000 palette bands, the exact 300-by-120
upper-sky crop, and all 768 palette components. The live solar distance is at
least `1000*ray`, authenticating the upper-distance radial flare suppression
boundary. Complete-page low-six-bit equality remains informational without the
native rig's snapshot-time terrain and HUD history.
