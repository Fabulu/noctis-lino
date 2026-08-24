# Class-4 lunar native sun oracle

This directory retains byte-for-byte copies of the certified NIV+ type-1
surface capture used by `tests/test_sun_gallery.py --case lunar-class4-sun135`.

- `native.shot.BMP`: SHA-256
  `357529f492a22166bb4a84076ab45b7205d8c1249f6b8e0e53d531bc2e82ce96`
- `native.SURFACE.BIN`: SHA-256
  `601eb8cea5703abc40266bc41b1a90a35229e45fde250242dbfe840aba2906db`

The files were copied without transformation from the retained capture files
`tests/gen/recon_w7b/out/type1_class4_positive_native.shot.BMP` and
`tests/gen/recon_w7b/out/type1_class4_positive_native.SURFACE.BIN`. The surface
record pins RIZI V, body 4 of the class-4 system at
`(3628560,-4254023,-915798)`, longitude 135, latitude 60, player
`(1638400,1,1638400)`, pitch -5, and heading 90. The frozen 16-MiB guest memory
image was certified separately at capture time: body 4 remained the reached
synchronous target, `landed` was 1, power was 20000, and source time was
`1345723230.0` seconds after 1984-01-01. The BMP yields indexed-page SHA-256
`1ae8588bbc0ea065c005393edfeaf9339774d75a472436ccdf3b805e1c837533`
and six-bit palette SHA-256
`642ba729ec892bd53237cde00323309939383ac159f9c6a6950b99b1fe65290e`.

The matched product frame admits the yellow-orange primary at `(161,102)`,
matches all 768 palette components, and retains every palette band in the
29,700-pixel `(10,10)..(309,108)` upper-sky crop. Native centre index 76 and
product centre index 79 remain in the same band. Its distance `1438.3975` lies
inside `10 * 19.877 <= distance < 1000 * 19.877`, extending positive
surface-flare coverage to star class 4. Complete-page equality remains
informational: 29,884 indices differ, and the 489 palette-band differences are
confined to snapshot-time horizon and terrain rows 109 through 159.
