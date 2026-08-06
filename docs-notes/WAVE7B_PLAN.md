# Wave 7b — ground renderer, sky, SURFACE.BIN, walking

Architect's consolidation of the three 7b recons (ground renderer, build_surface +
SURFACE.BIN, sky + reuse + oracles). Written 2026-08-07, after Wave 7a landed (committed
aabfd0f). The recon transcripts are gone; everything load-bearing is here or in the
file:line anchors the recons verified against the niv-plus source.

WAVEPLAN §7 is the parent spec. This file makes the wave's decisions concrete: files,
namespace, impl split, correctness, failure modes.

## Goal

The "standing on a planet" view. `build_surface()` generates the ground (heightmap +
texture + objects) from the planet seed; the renderer walks the player across it frame by
frame (`fragment → polymap`); `create_sky()` paints the sky/horizon; `SURFACE.BIN`
(40-byte NIV+) saves/restores the landing. Reuses Wave 6's `polymap`/`poly3d`/projection
and Wave 7a's `p_background` (which `iperficie` samples as the ground texture via
`txtr = p_background`).

## What 7b builds vs reuses

**Builds fresh** (no port exists):
- `build_surface()` + its integer painters (`round_hill`, `rockyground`, `smoothterrain`,
  craters, ruins, vegetation) → `p_surfacemap` (200×200 heightmap), `p_background`
  (256×256 ground texture, overwrites 7a's orbital albedo), `objectschart` (object/ruins
  slots). NOCTIS-1.CPP:1948-2700.
- `create_sky()` + `nebular_sky`/`cloudy_sky` → `s_background` (sky texture) +
  `surface_palette` bands + horizon darkening. NOCTIS-1.CPP:1674-1765, 2736-3139.
- Traversal: `iperifie` (grid walk, paint order), `fragment` (per-tile 6-vertex emit),
  `hpoint` (bilinear height query). NOCTIS-1.CPP:63-93, 1028-1471.
- Walking physics + camera (`planetary_main`'s ground loop, `p_Forward`, `from_user`).
  NOCTIS-1.CPP:3313-5045; NOCTIS-0.CPP:1281-1392.
- `SURFACE.BIN` I/O (40-byte NIV+). NOCTIS-1.CPP:3721-3742 (read), 4989-5007 (write).

**Reuses** (already ported, do not rebuild): `polymap`/`poly3d`/`facing`/
`change_angle_of_view`/`change_camera_lens` (Wave 6, TDPOLYGS.H); `background`/`sky`/
`whitesun` (Wave 6b); the framebuffer shell, 2D primitives, palette engine, tick (Wave 5);
the float engine + LCG (Waves 1/3); `p_background` as a settled byte-exact input (7a).

## Namespace and files

Two-letter prefix **`gr`** (ground) for 7b — disjoint from 7a's `su`. Implementers own
disjoint sets:

- **B1 (generation + save):** `work/grnd.txt` (build_surface + painters), `work/surfio.txt`
  (SURFACE.BIN 40-byte read/write); harness `noctis-harness/gr_spec.py`, `gr_ref.c`,
  `gr_grade.py`, `gr_break.py`.
- **B2 (rendering + sky):** `work/walk.txt` (`iperifie`/`fragment`/`hpoint` + walking +
  frame compose), `work/sky.txt` (`create_sky` + painters); harness `noctis-harness/grv_*`
  (renderer) and `sky_*`.

Neither edits `tests/run_all.py` (coordinator) or `tests/test_surface.py` (7a's delivered
result). The new test registers as `tests/test_ground.py`.

## Correctness — three tiers

1. **`build_surface()` output, byte-exact (strongest).** `p_surfacemap` (40,000 B) +
   256×256 `p_background` (65,536 B) + `objectschart` ruins slots. Pure integer
   generation, `fast_random`/`random(int)` driven — the Wave 7a pattern, three-way (lino
   == spec == cref) with sabotage controls. **LR ASSIGN-vs-ADD candidates to reject:**
   `p_surfacemap[ptr] += fast_random(3)` at NOCTIS-1.CPP:2280-2282 and the `round_hill`
   canyon mirror at :1517-1518 (the analogues of 7a's type-3 defect).
2. **`polymap` rasterisation given pinned vertices, byte-exact** on an `adapted`
   sub-rectangle — Wave 6a's `test_raster.py` pattern (integer-exact once vertices fixed).
3. **Landed frame from DOSBox-X** (`adapted` as 320×200 indices vs the gallery BMP), within
   a ±1-texel envelope at the 38 hand-`fistp` sites (the cosmetic exposure; keep Wave 6a's
   B10/B11 `--round=chop` controls + add a `FToIntNear`→`FToIntChop` flip at the per-pixel
   `fistp u/v`).
4. **SURFACE.BIN round-trip** (40-byte write/reload) — quotient:remainder is integer,
   trivially exact; cross-checks Wave 8's freeze/unfreeze.
5. **Sky band / horizon boundary** — capturable; `lssmooth`/`ssmooth`/`nebular_sky`/
   `cloudy_sky` touch it; grade the boundary ±1 px.

## The oracle that gates everything: the landed-view capture

**Feasible via the resume-from-save shortcut** (the recon's find): NOCTIS.CPP:2231-2255 —
if `Surface.BIN` exists at startup, NOCTIS regenerates `surface()`, sets `entryflag=1`,
calls `planetary_main()`, which reads the 40-byte save and starts `landed=1`. **The descent
is skipped.** So:

1. `mkcurrent.py` (7a's rig) writes `Current.BIN` (sync=1, right star/planet).
2. Hand-build `dos/data/Surface.BIN` (40 bytes): `landing_pt_lon/lat`, `atl_x=atl_z=100`,
   `atl_x2=atl_z2=8192`, `pos_x=pos_z=100<<14+8192`, `pos_y≈hpoint`, `user_alfa=user_beta=0`.
3. Headless DOSBox-X + autotype the gallery-shot key `b` (snapshot at NOCTIS-1.CPP:4932) +
   the `[dosbox] memory file =` RAM read (extends 7a's `godos_w7a.ps1`/`memfind.py`).
4. Extends `certify.py` to require `landed==1` + correct `ip_targetted`.

Yields byte-exact vs NIV+ R2.3: `p_background` (ground texture), `p_surfacemap`
(altimetry), `objectschart`, `adapted` (visible frame), palette. Pin the guest clock
(7a's `synchronize time=false` + pinned date/time — `surface()` consumes `secs`, types
3/5/6 still need it). **This is 7b's first infra task.** AUTOTYPE only needs the one
snapshot key (not a full descent), so it is far more tractable than WAVEPLAN §7 feared;
the human 10-minute session is the fallback only if that single-key AUTOTYPE fails. **One
capture per planet type (10); per (type, sctype) for type-3.**

Until a capture exists, 7b grades on tiers 1–2 (C-from-source three-way) and carries the
**"type-3 ground terrain unvalidated against hardware" flag** (WAVEPLAN §7 stall mode) —
which now covers all ten types, not just type-3.

## Float sites (exact-required)

Three C-cast chops on the ground path, all feeding discrete decisions — use `FToIntChop`
or `work/geoconv.txt`'s live-chop fragments (FLOATPOLICY §3.3) until `genfp` refuses a
bare `fistp`:
- `depth = (long)(hpdep) >> 14` (NOCTIS-1.CPP:1088) — chop of `sqrt`; drives cull/fog/detail.
- `ipfx/ipfz = ((long)cam_x/cam_z) >> 14` (:4063-4064, :4311-4312) — drives fragment bounds.
- `atl_x = ((long)pos_x) >> 14` (:4179-4182) → SURFACE.BIN (state-carrying).

Everything else on the ground/sky path is rendering-tolerant (native lino floats, ±1 px
envelope) — the 37 hand-`fistp` sites reproduce for free under `FEnter`'s 133Fh.

## Buffer-alias hazards (do NOT clamp)

- `txtr = n_globes_map` (32,768 B) read as 256×256 overruns into `s_background` whenever
  the horizon renders — **faithful by farmalloc order (LINOBUF §2.4 row 1); the sea-texture
  overrun WILL fire in 7b.** The flat workspace's layout already lands it correctly.
- `tinta`/`escrescenze` at `adapted` offset 63,996 (LINOBUF §4 alias 8) — the per-texel
  shade colour; `niv-lr` relocates to 64,000, a confirmed divergence the test must reject.
- `create_sky(char atmosphere)` — the `atmosphere` **parameter is a boolean**, not the
  `objectschart`-aliased buffer. Easy to wire backwards.

## SURFACE.BIN — 40-byte NIV+ R2.3 layout

Write NOCTIS-1.CPP:4992-5002 (ESC && landed), read :3722-3735 (entryflag). 11 fields:

```
off 0  landing_pt_lon  int16        off 20 pos_x      float (walker X)
off 2  landing_pt_lat  int16        off 24 pos_y      float (~−260000..0)
off 4  atl_x           int32 quot   off 28 pos_z      float (walker Z)
off 8  atl_z           int32 quot   off 32 user_alfa  float (yaw)
off 12 atl_x2          int32 rem    off 36 user_beta  float (pitch)
off 16 atl_z2          int32 rem    total 40
```

`pos_x == (atl_x<<14)+atl_x2`; on fresh landing `atl_x2==atl_z2==8192` (write-once, NOT
re-derived as you walk). Stock/LR adds 5 trailing bytes (`openhuddelta/openhudcount/
hud_rtl_closed`) which NIV+ dropped — port writes 40, never 45. **Trap: `remove(surface_file)`
at NOCTIS.CPP:4487 deletes it on program exit — capture before the DOS process ends.**

## Out of scope

- The capsule descent (opencapdelta/bounces, cumulative gravity) — use the `entryflag=1`
  shortcut, never simulate the descent.
- `cplx_planet_viewpoint` + sun-angle math (Wave 8).
- Multi-hour walk frame sequences (input timing not bit-reproducible).

## One-line doc fix to pick up

FLOATSITES.md §2.1 row for NOCTIS-1.CPP:4179/4180 says "Current.BIN" — it is Surface.BIN.
