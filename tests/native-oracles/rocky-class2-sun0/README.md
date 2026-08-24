# Class-2 rocky native sun oracle

This directory retains byte-for-byte copies of the certified NIV+ type-4
surface capture used by `tests/test_sun_gallery.py --case rocky-class2-sun0`.

- `native.shot.BMP`: SHA-256
  `ea6696f9ad039d0c0409b60ec8997855d1e15c1ca284650ec10b46b4d7f4796d`
- `native.SURFACE.BIN`: SHA-256
  `dcad65a8be49d3522b125625c8f82147b1c80bf1ab59c7812db0c35274203352`

The files were copied without transformation from the retained capture files
`tests/gen/recon_w7b/out/type4_class2_positive_native.shot.BMP` and
`tests/gen/recon_w7b/out/type4_class2_positive_native.SURFACE.BIN`. The surface
record pins ROSVITA II, body 1 of the class-2 system at
`(5800336,-4462999,-925592)`, longitude 0, latitude 60, player
`(1638400,1,1638400)`, pitch -12, and heading 270. The frozen 16-MiB guest
memory image was certified separately at capture time: body 1 remained the
reached synchronous target, `landed` was 1, power was 17482, and source time
was `1345723229.7` seconds after 1984-01-01. The BMP yields indexed-page
SHA-256
`529d63dec71e53a999f2dfc88da926363cad5511c95bb71ed6272105a71ca9b4`
and six-bit palette SHA-256
`87b403eee35a762a83175163c3fd9a48c30339c3a0fe2188c56aa3d4d3b52b03`.

The matched product frame admits the white primary at `(161,100)`, matches its
native centre index 108, all 768 palette components, and all 27,000 indices in
the `(10,10)..(309,99)` upper-sky crop. Its distance `61.7717` lies inside
`10 * 0.363 <= distance < 1000 * 0.363`, extending positive surface-flare
coverage to star class 2. Complete-page equality remains informational: 20,256
low-six-bit values differ, and 1,081 palette-band differences are confined to
the snapshot-time horizon rows 115 through 123.
