# Lunar native sun oracle

This directory retains byte-for-byte copies of the certified NIV+ type-1
surface capture used by `tests/test_sun_gallery.py --case lunar-sun0`.

- `native.shot.BMP`: SHA-256
  `ddc0582655a2e194a97cb071187b26da5a6b368e07be11b31027f70e06b2ffa1`
- `native.SURFACE.BIN`: SHA-256
  `46b02d475662b76691baa8dc8e44fbc3a670adfce7a1e89ebd9dc5031c4efcd1`

The files were copied without transformation from the retained capture files
`tests/gen/recon_w7b/out/lunar_sun0_pinned_oracle.shot.BMP` and
`tests/gen/recon_w7b/out/lunar_sun0_pinned_oracle.SURFACE.BIN`. The surface
record pins IDEAL I at longitude 0, latitude 60, player
`(1638400,-19032,1638400)`, pitch -44, and heading 90. The BMP yields indexed
page SHA-256
`38b5b2347fff4c3fe5016337904a8a51ff1d5f7276e2555e7461f8623a87997b`
and six-bit palette SHA-256
`a6570716a7b04a4629ac7cdfa0ddb21d23305a207a80a8cafda707a50543e9ab`.

The product gate requires the exact 300-by-120 upper-sky crop and all 768
palette components. Complete-page palette bands remain informational because
the retained rig did not preserve snapshot-time terrain and HUD history. The
live solar distance is below `10*ray`, authenticating the lower-distance radial
flare suppression boundary.
