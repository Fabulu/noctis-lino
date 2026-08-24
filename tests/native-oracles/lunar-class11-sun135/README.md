# Class-11 lunar native sun oracle

This directory retains byte-for-byte copies of the certified NIV+ type-1
surface capture used by `tests/test_sun_gallery.py --case lunar-class11-sun135`.

- `native.shot.BMP`: SHA-256
  `e1eca960e63efec582e3c32c8fae5ae5d7109aa4a83186d46ff8550cc161bb08`
- `native.SURFACE.BIN`: SHA-256
  `c858b3429baf8272e3eba62c2fe0612db8587c0c005fa3f2828288d0f2cccf8f`

The files were copied without transformation from the retained capture files
`tests/gen/recon_w7b/out/type1_class11_positive_native_final.shot.BMP` and
`tests/gen/recon_w7b/out/type1_class11_positive_native_final.SURFACE.BIN`. The
surface record pins LUX I, body 0 of the class-11 system at
`(4879984,-4603699,-1023471)`, longitude 135, latitude 60, player
`(1638400,1,1638400)`, pitch -34, and heading 270. The frozen 16-MiB guest
memory image was certified separately at capture time: body 0 remained the
reached synchronous target, `landed` was 1, power was 17482, and source time
was `1345723229.7777777` seconds after 1984-01-01. The BMP yields indexed-page
SHA-256
`17c25bcb97300107f83dc494e9eb115ec294def23fbeba2093fa143d0bcff596`
and six-bit palette SHA-256
`2fdd396ff08a4586cc15efd52b32cae41f280610f5d388b62e63925d38d2032c`.

The matched product frame admits the cyan primary at `(161,100)`, matches its
native centre index 105, matches all 768 palette components, and preserves the
native palette band at all 64,000 final-page pixels. Its distance `23.0416`
lies inside `10 * 0.256 <= distance < 1000 * 0.256`, extending positive
surface-flare coverage to star class 11. The 450 complete-page low-six-bit
mismatches remain informational because the timed native snapshot did not
retain the exact smoothing phase.
