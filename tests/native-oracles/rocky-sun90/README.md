# Rocky native sun oracle

This directory retains byte-for-byte copies of the certified NIV+ type-4
surface capture used by `tests/test_sun_gallery.py --case rocky-sun90`.

- `native.shot.BMP`: SHA-256
  `f983407da7c9ff5c9da47560c23d4f9a77040708b70da010ce6b4dc6b9c94b0a`
- `native.SURFACE.BIN`: SHA-256
  `6010d36d894ec6e086e9a7a47e4d7d0ab8e4113527f7c282800fe0c4623e4b09`

The files were copied without transformation from the retained capture files
`tests/gen/recon_w7b/out/rocky_sun90_pinned_oracle.shot.BMP` and
`tests/gen/recon_w7b/out/rocky_sun90_pinned_oracle.SURFACE.BIN`. The surface
record pins LANE X at longitude 90, latitude 60, player
`(1645000,1,1641000)`, pitch -38, and heading 270. The BMP yields indexed page
SHA-256
`6789a54784a2721cb475d8c7b6eae171b87ab0b46b296ff78a96745a1425dae1`
and six-bit palette SHA-256
`1b7d437f34c8ff90711e56d4ad6a477fe1d9135ddd10d597299f45626a8b6ed2`.

The product gate requires the exact 300-by-90 upper-sky crop and all 768
palette components. Complete-page palette bands remain informational because
the retained rig did not preserve snapshot-time terrain and HUD history. The
live solar distance is at least `1000*ray`, authenticating the upper-distance
radial flare suppression boundary.
