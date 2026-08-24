# Quartz native sun oracle

This directory retains byte-for-byte copies of the certified NIV+ type-8
surface capture used by `tests/test_sun_gallery.py --case quartz-sun228`.

- `native.shot.BMP`: SHA-256
  `9d4ae059276c202e1d55975e38587e0dc40a9a6e01d46f4887e5e621433b9e16`
- `native.SURFACE.BIN`: SHA-256
  `aa6a53c04a3353b9fad206cc1776f236c2df880abe08bbde4f1adbacd0bbd4c8`

The files were copied without transformation from the retained capture files
`tests/gen/recon_w7b/out/quartz_sun228_oracle.shot.BMP` and
`tests/gen/recon_w7b/out/quartz_sun228_oracle.SURFACE.BIN`. The surface record
pins LANE VIII at longitude 228, latitude 60, player
`(1638400,1,1638400)`, pitch -30, and heading 270. The frozen 16-MiB guest
memory image was certified separately at capture time: body 7 remained the
reached synchronous target, `landed` was 1, power was 17263, and source time
was exactly 1345761727 seconds after 1984-01-01. The BMP yields indexed page
SHA-256
`06270d9f7af9374196783fefbef368b71b40b921354fc1fe99967a7938acef39`
and six-bit palette SHA-256
`04812fc5c5eeb2fbdc31885443da79e17b791ea67d24ad48754a6c858bec98ad`.

The matched product frame retains the exact projected centre index 97, all 768
palette components, and every palette band in the 300-by-120 upper-sky crop.
Its live distance lies inside `10*ray <= distance < 1000*ray`, adding a
full-context positive radial flare for the previously omitted type-8 class.
Complete-page bands and upper-sky low-six-bit indices remain informational
without snapshot-atomic terrain, HUD, and the two source smoothing passes.
