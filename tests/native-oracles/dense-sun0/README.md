# Dense-atmosphere native sun oracle

This directory retains byte-for-byte copies of the certified NIV+ type-2
surface capture used by `tests/test_sun_gallery.py --case dense-sun0`.

- `native.shot.BMP`: SHA-256
  `3f49a3ac6d730b028766f354ac81d3cd077dc843a2b6ddd8731d759f39becb47`
- `native.SURFACE.BIN`: SHA-256
  `db6835c47e8edc213d82448ac3d6bf45ba245e71e9c5425eed3c1ec2b982f5dc`

The files were copied without transformation from the retained capture files
`tests/gen/recon_w7b/out/dense_sun0_exact_oracle.shot.BMP` and
`tests/gen/recon_w7b/out/dense_sun0_exact_oracle.SURFACE.BIN`. The surface
record pins LANE I at longitude 0, latitude 60, player
`(1638400,1,1638400)`, pitch -44, and heading 90. The BMP yields indexed page
SHA-256
`a33a33802da8072710fb732cfe8a68d0037b6239ac4f1e19beecbef52e5df4e7`
and six-bit palette SHA-256
`c7e3d402b9e2a5b6a596a076d25f52209acdfa37fae511a60979a79a3a5aa778`.

The product gate requires every pixel's palette band. Exact palette equality
remains informational because the native rig did not retain palette-easing
history; the matched product capture differs in 101 of 768 components while
retaining all 64,000 bands. The live solar distance is below `10*ray`,
authenticating the lower-distance radial flare suppression boundary.
