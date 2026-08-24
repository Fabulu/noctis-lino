# Class-8 dense native sun oracle

This directory retains byte-for-byte copies of the certified NIV+ type-2
surface capture used by `tests/test_sun_gallery.py --case dense-class8-sun0`.

- `native.shot.BMP`: SHA-256
  `16d54dacda5231d7a0034c40295450e87b52cfde061a24f1763530397253f5bc`
- `native.SURFACE.BIN`: SHA-256
  `0970f803529c10431eb46a5f6a5a30a145f98660cd21b27e645eafd512a9399a`

The files were copied without transformation from the retained capture files
`tests/gen/recon_w7b/out/type2_class8_positive_native.shot.BMP` and
`tests/gen/recon_w7b/out/type2_class8_positive_native.SURFACE.BIN`. The surface
record pins body 1 of the class-8 system at `(-1996240944,72703,944799)`,
longitude 0, latitude 60, player `(1638400,1,1638400)`, pitch -30, and heading
90. The frozen 16-MiB guest memory image was certified separately at capture
time: body 1 remained the reached synchronous target, `landed` was 1, power was
19998, and source time was 1345636830 seconds after 1984-01-01. The BMP yields
indexed-page SHA-256
`f0f2d630e6fb677edb570077f97e38175bfaa42def729a1c21358fd519eb8f45`
and six-bit palette SHA-256
`15c0987fb84ca7a2aaed5c2d2a34817e4d6cc3e9f046574a6559d4200fa5ff24`.

The matched product frame admits the primary at `(161,85)` and preserves the
native palette band at all 64,000 final-page pixels. Its distance `129.4516`
lies inside `10 * 6.505 <= distance < 1000 * 6.505`, adding the positive
counterpart to the retained class-0 type-2 lower-gate scene. Native centre index
60 and product centre index 59 remain in the same band. Complete low-six-bit
page values and exact palette easing remain informational: the timed native
snapshot did not retain that history, and the matched product palette differs
in 157 of 768 components.
