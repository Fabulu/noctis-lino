# Class-9 lunar native sun oracle

This directory retains byte-for-byte copies of the certified NIV+ type-1
surface capture used by `tests/test_sun_gallery.py --case lunar-class9-sun135`.

- `native.shot.BMP`: SHA-256
  `85c257928f307b9d75bdb69d3afa919201b5d8de6ee377f583d51d9ed3d3c9d8`
- `native.SURFACE.BIN`: SHA-256
  `c858b3429baf8272e3eba62c2fe0612db8587c0c005fa3f2828288d0f2cccf8f`

The files were copied without transformation from the retained capture files
`tests/gen/recon_w7b/out/type1_class9_positive_native.shot.BMP` and
`tests/gen/recon_w7b/out/type1_class9_positive_native.SURFACE.BIN`. The surface
record pins LAMBO VII, body 6 of the class-9 system at
`(1405360,-789781,-1941535)`, longitude 135, latitude 60, player
`(1638400,1,1638400)`, pitch -34, and heading 270. The frozen 16-MiB guest
memory image was certified separately at capture time: body 6 remained the
reached synchronous target, `landed` was 1, power was 20000, and source time
was `1345723230.0` seconds after 1984-01-01. The BMP yields indexed-page
SHA-256
`4489f211257b83614d1eecf82576efbfd3e803a3a8e6b7e29c3aba032fb1d641`
and six-bit palette SHA-256
`5183075f60cb8abed98d24fe9f2b979adf5f1bdcc3436c8d2c534a1f8d612539`.

The matched product frame admits the purple primary at `(161,56)` and
reproduces exact final centre index 70, all 768 palette components, all 64,000
palette bands, and all 49,140 indices in the `(40,10)..(309,191)`
sky-and-flare crop. Its live distance `4244.9551` lies inside
`10 * 9.841 <= distance < 1000 * 9.841`, extending positive surface-flare
coverage to star class 9. Complete-page equality remains informational: only
452 low-six-bit indices differ, entirely in snapshot-time HUD and border
regions outside the exact crop.
