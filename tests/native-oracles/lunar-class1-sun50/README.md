# Class-1 lunar native sun oracle

This directory retains byte-for-byte copies of the certified NIV+ type-1
surface capture used by `tests/test_sun_gallery.py --case lunar-class1-sun50`.

- `native.shot.BMP`: SHA-256
  `f6f5093dfaf4be7f339da58845233ecdf8930bc3f43297ee89014501d4bbf11c`
- `native.SURFACE.BIN`: SHA-256
  `8bb6cba9e72852ff5ad9b6846696f60ace162bf9c9dc2665f8410b1b2326bfe8`

The files were copied without transformation from the retained capture files
`tests/gen/recon_w7b/out/type1_class1_positive_native.shot.BMP` and
`tests/gen/recon_w7b/out/type1_class1_positive_native.SURFACE.BIN`. The surface
record pins body 4 of the class-1 system at `(2952848,-6448045,-840503)`,
longitude 50, latitude 60, player `(1638400,1,1638400)`, pitch -30, and heading
90. The frozen 16-MiB guest memory image was certified separately at capture
time: body 4 remained the reached synchronous target, `landed` was 1, power was
19998, and source time was exactly 1345636830 seconds after 1984-01-01. The BMP
yields indexed-page SHA-256
`e191fc2841a00ab4c5ef63823ed1bc2ecdc5349c750eb76f0dd5919d074633b5`
and six-bit palette SHA-256
`90bb990e6edc353b2a682ca156aae2a802c75019d29046a48287dbb5c008b1de`.

The matched product frame admits the primary at `(161,91)`, retains the native
palette band at that centre, matches all 768 palette components, and preserves
the native palette band at all 64,000 final-page pixels. Its distance
`1757.4972` lies inside
`10 * 21.879 <= distance < 1000 * 21.879`, adding a full-context positive
radial flare for type 1 around a class-1 star. Native centre index 78 and
product centre index 80 remain in the same band; complete low-six-bit page
values depend on snapshot-time smoothing and remain informational.
