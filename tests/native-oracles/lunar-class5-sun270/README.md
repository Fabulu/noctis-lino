# Class-5 lunar native sun oracle

This directory retains byte-for-byte copies of the certified NIV+ type-1
surface capture used by `tests/test_sun_gallery.py --case lunar-class5-sun270`.

- `native.shot.BMP`: SHA-256
  `0617cdf3347a7f50c554d15df5f9ef18d1fa80d6cfcaed5b2a66b668102d7f0b`
- `native.SURFACE.BIN`: SHA-256
  `2ac785fe76a8b92b7f5a567770716decad00f63b9f305badb83da20b68c27d87`

The files were copied without transformation from the retained capture files
`tests/gen/recon_w7b/out/type1_class5_suppressed_native.shot.BMP` and
`tests/gen/recon_w7b/out/type1_class5_suppressed_native.SURFACE.BIN`. The
surface record pins GALLID III, body 2 of the class-5 system at
`(3052848,-5636380,-959161)`, longitude 270, latitude 60, player
`(1638400,1,1638400)`, pitch -30, and heading 270. The frozen 16-MiB guest
memory image was certified separately at capture time: body 2 remained the
reached synchronous target, `landed` was 1, power was 20000, and source time
was `1345723230.0` seconds after 1984-01-01. The BMP yields indexed-page
SHA-256
`3f9986abf40ca5660b786def059e91e6de585a1125179191730af1d267995ca2`
and six-bit palette SHA-256
`bb64a406daa7bad9bbb70d1bf431ba59f4b937bd715e956e55c13664647f91cd`.

The matched product frame reproduces the brown-red primary's white disc and
corona, including exact centre index 127 at `(158,96)`, all 768 palette
components, all 64,000 palette bands, and all 47,250 indices in the
`(40,10)..(309,184)` sky-and-disc crop. The live distance `32.3576` lies
inside `10 * 1.39 <= distance < 1000 * 1.39`, but the source excludes star
class 5 before radial-flare projection; both native and product therefore show
the disc without radial rays, and the product reports zero flare admission.
Complete-page equality remains informational: only 391 low-six-bit indices
differ, entirely in snapshot-time HUD and border regions outside the exact
crop.
