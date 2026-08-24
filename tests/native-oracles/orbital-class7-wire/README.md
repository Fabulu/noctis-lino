# Native WIRE class-7 orbital-primary oracle

This retained NIV+ frame closes a source-valid positive orbital-primary case for
class 7. WIRE is at `(-1187856,-195673,1064757)` with stellar radius
`2.191999912261963`; its generated system has one type-9 body but no landable
surface. The camera is therefore an untargeted exterior Stardrifter pose rather
than an invented landing.

The frozen continuity block retains camera position `(2813,0,-1397)`, pitch
`0`, user beta `23`, navigation beta `0`, and star-relative vector
`(85.64826336479746,0,-201.77466387674212)`. Its source distance is `220.2`
including the source's `+1`: comfortably above `6 * ray = 13.151999473571777`
and below `1000 * ray = 2191.999912261963`. Class 7 passes the source's explicit
class exclusions, so the visible central flare core and radial spokes are a
positive primary-flare result.

## Reproduction

The 385-byte continuity file was built with the tracked helper's explicit
untargeted mode:

```text
python tests/gen/recon_w7b/mkcurrent.py \
  --x -1187856 --y -195673 --z 1064757 --target -1 --sync 0 \
  --secs 1345723200 --pos-x 2813 --pos-y 0 --pos-z -1397 \
  --pitch 0 --view-angle 23 --navigation-angle 0 \
  --local-x -85.64826336484876 --local-y 0 \
  --local-z 201.77466387677492 \
  --out build/wire-class7-primary.CURRENT.BIN
```

The silent DOSBox-X command set DOS date/time to `24.08.2026 12:00:00.00`,
installed `autotype -w 30 -p 3 b`, and launched `noctis.exe`. The tracked
`capture_orbital_w7b.py` runner stopped on the complete 65,078-byte gallery BMP,
froze 16 MiB of guest RAM, and restored the DOS sandbox. `provenance.json`
retains the command, continuity, RAM, adapted-page, BMP, indexed-page, and
packed six-bit-palette hashes.

## Authority

`native.shot.BMP` is the unmodified native gallery file. Its decoded page and
active palette are authoritative, as are positive primary-flare visibility and
the retained camera state. In crop `(120,60)..(195,115)`, 148 pixels have a
low-six intensity of at least 40, spanning `(149,91)..(165,111)`.

The snapshot is not state-atomic with the frozen adapted page: DOSBox-X was
suspended after publication and the guest had begun its next frame, producing
30,095 page differences. Complete-page equality against that later page or a
separately captured product frame is therefore not claimed.

## Hashes

```text
native.shot.BMP
254daba81c49072da33ec65f2aa9ac639fdf74f887114c22cdba71ce2c1feae1

indexed page
23c2c66529021bf43952b9e0f526f50fb710c4698cdcfc0032631c291e9e5995

packed <768I six-bit palette
78dff3c46c7cd75014e9e77a05ca9f07ae60bba3af6d3d09ad19c63f45634ec1
```
