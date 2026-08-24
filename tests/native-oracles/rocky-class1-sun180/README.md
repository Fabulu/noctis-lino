# Class-1 rocky native sun oracle

This directory retains byte-for-byte copies of the certified NIV+ type-4
surface capture used by `tests/test_sun_gallery.py --case rocky-class1-sun180`.

- `native.shot.BMP`: SHA-256
  `3d0082eca8f2dc26759ff48eb7e19a5786601c0c23b0801addb0b74b32f55ba8`
- `native.SURFACE.BIN`: SHA-256
  `95cb83c43172d18799b58f65cee14cbd701690271c1f5bee04a76e0d97c0e48f`

The files were copied without transformation from the retained capture files
`tests/gen/recon_w7b/out/type4_class1_positive_native.shot.BMP` and
`tests/gen/recon_w7b/out/type4_class1_positive_native.SURFACE.BIN`. The surface
record pins body 1 of the class-1 system at `(2952848,-6448045,-840503)`,
longitude 180, latitude 60, player `(1638400,1,1638400)`, pitch -10, and
heading 270. The frozen 16-MiB guest memory image was certified separately at
capture time: body 1 remained the reached synchronous target, `landed` was 1,
power was 31505, and source time was exactly 1345723230 seconds after
1984-01-01. The BMP yields indexed-page SHA-256
`f87bab92428a89bbdd17cb0ddf65ac63dca65954dd9b494dc8fd1418cf12f0b9`
and six-bit palette SHA-256
`20480ec2fd03efb83ff3e3ac8a0480fa590c8ec7e7f0e9fe127ead90ab91073a`.

The matched product frame retains the exact projected centre `(161,72)` and
index 126, all 768 palette components, and every one of the 27,000 indices in
the `(10,10)..(309,99)` upper-sky crop. Its distance `245.8964` lies inside
`10 * 21.879 <= distance < 1000 * 21.879`, adding a full-context positive
radial flare for type 4 around a class-1 star. Complete-page terrain, HUD, and
post-snapshot smoothing history remain informational.
