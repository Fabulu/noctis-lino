# Class-3 lunar native sun oracle

This directory retains byte-for-byte copies of the certified NIV+ type-1
surface capture used by `tests/test_sun_gallery.py --case lunar-class3-sun75`.

- `native.shot.BMP`: SHA-256
  `cb8c4d22ddd098fd6dc9e20a04769ba7d863acddfd5d35932cf9a4297d0b522a`
- `native.SURFACE.BIN`: SHA-256
  `4891b835291f0b0f717c9044d26ada2df101bb09645d1b73a47a56433d3f9122`

The files were copied without transformation from the retained capture files
`tests/gen/recon_w7b/out/type1_class3_positive_native.shot.BMP` and
`tests/gen/recon_w7b/out/type1_class3_positive_native.SURFACE.BIN`. The surface
record pins SIENA V, body 4 of the class-3 system at
`(3363568,-4274032,-2404452)`, longitude 75, latitude 60, player
`(1638400,1,1638400)`, pitch -34, and heading 270. The frozen 16-MiB guest
memory image was certified separately at capture time: body 4 remained the
reached synchronous target, `landed` was 1, power was 20000, and source time
was `1345723230.090909` seconds after 1984-01-01. The BMP yields indexed-page
SHA-256
`a4229d3e139354506136409f93ef5ecd6eed8eae33d7a8c4d7ef1a379e05b2c1`
and six-bit palette SHA-256
`16d8b262b94d5e443b12963b9faaf1a8e95d4dde88d1b47ac6662c0a5e4b8a4f`.

The matched product frame admits the orange primary at `(161,71)`, matches its
native centre index 73, all 768 palette components, and all 37,800 indices in
the `(40,10)..(309,149)` upper-sky crop. Its distance `2365.4727` lies inside
`10 * 27.753 <= distance < 1000 * 27.753`, extending positive surface-flare
coverage to star class 3. Complete-page equality remains informational: 2,272
indices differ, and the 128 palette-band differences are confined to
snapshot-time terrain rows 157 through 185.
