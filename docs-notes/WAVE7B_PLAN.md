# Wave 7b -- ground renderer, sky, SURFACE.BIN, walking

## Final sky closeout (2026-08-08)

The sky portion is verified and closed: `tests/test_sky.py` is **16/16 PASS**
(1999 s). Canonical Python/C/Lino agree on **27/27 cases and 408 records**;
first launch is exact, malformed inputs are **7/7**, binary anchors are exact,
C mutants are **26/26**, static and dynamic Lino mutants are **27/27**, and H1
source/work immutability passes. Replay SHA-256:
`a68a5775f2ad05d04cdd6c399b42f06a5d2a24cd555e81348ef7e47f70ecf421`.

This is historical closeout evidence, not a standing workload. Routine changes use one
focused smoke/regression check for the changed path. The 27-case/26C+27Lino mutation matrix
is optional `--deep` evidence for high-risk oracle changes; requiring it for every fix adds
detrimental process and testing overhead. Screenshots and playtest are product feedback,
not another oracle-construction obligation.

Screenshots remain ungraded. The original type-3 `p_surfacemap` discrepancy
has been reduced from 39,710 to a measured **post-landing XFAIL of 1,752
bytes** after reproducing Borland's unsigned 16-bit `round_hill` bounds.

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

Two-letter prefix **`gr`** (ground) for 7b -- disjoint from 7a's `su`. Implementers own
disjoint sets:

- **B1 (generation + save):** `work/grnd.txt` (build_surface + painters), `work/surfio.txt`
  (SURFACE.BIN 40-byte read/write); harness `noctis-harness/gr_spec.py`, `gr_ref.c`,
  `gr_grade.py`, `gr_break.py`.
- **B2 (rendering + sky):** `work/walk.txt` (`iperifie`/`fragment`/`hpoint` + walking +
  frame compose), `work/sky.txt` (`create_sky` + painters); harness `noctis-harness/grv_*`
  (renderer) and `sky_*`.

Neither edits `tests/run_all.py` (coordinator) or `tests/test_surface.py` (7a's delivered
result). The new test registers as `tests/test_ground.py`.

## Correctness -- three tiers

1. **`build_surface()` output, byte-exact (strongest).** `p_surfacemap` (40,000 B) +
   256×256 `p_background` (65,536 B) + `objectschart` ruins slots. Pure integer
   generation, `fast_random`/`random(int)` driven -- the Wave 7a pattern, three-way (lino
   == spec == cref) with sabotage controls. **LR ASSIGN-vs-ADD candidates to reject:**
   `p_surfacemap[ptr] += fast_random(3)` at NOCTIS-1.CPP:2280-2282 and the `round_hill`
   canyon mirror at :1517-1518 (the analogues of 7a's type-3 defect).
2. **`polymap` rasterisation given pinned vertices, byte-exact** on an `adapted`
   sub-rectangle -- Wave 6a's `test_raster.py` pattern (integer-exact once vertices fixed).
3. **Landed frame from DOSBox-X** (`adapted` as 320×200 indices vs the gallery BMP), within
   a ±1-texel envelope at the 38 hand-`fistp` sites (the cosmetic exposure; keep Wave 6a's
   B10/B11 `--round=chop` controls + add a `FToIntNear`→`FToIntChop` flip at the per-pixel
   `fistp u/v`).
4. **SURFACE.BIN round-trip** (40-byte write/reload) -- quotient:remainder is integer,
   trivially exact; cross-checks Wave 8's freeze/unfreeze.
5. **Sky band / horizon boundary** -- capturable; `lssmooth`/`ssmooth`/`nebular_sky`/
   `cloudy_sky` touch it; grade the boundary ±1 px.

## The oracle that gates everything: the landed-view capture

**✅ DONE (2026-08-07): rig built (`tests/gen/recon_w7b/`) and WORKS.** The
single-key AUTOTYPE (`b`) is reliable headlessly -- **the human DOSBox-X session
is NOT required** (7b's biggest unknown, resolved). Two captures of the type-3
equator site (lon 0 / lat 60) are **byte-identical** on `p_surfacemap` (40000 B),
`p_background` (65552 B), `objectschart` (40000 B), `s_background` (64800 B) --
the static tier-1 oracle, now binary-anchored vs NIV+ R2.3. Only `shot.BMP`
varies 642 B (sky/horizon atmospheric noise -- tier-3 ±1-texel). Two rig flags:
`landed` is at `atl_x-1` (Borland packs char before long, no padding); `pos_y=1.0`
(descent skipped → snaps to ground frame 1). The capture lifts the lack-of-oracle
flag, but the **type-3 heightmap is not yet byte-exact**; the 2026-08-08 audit
below separates the validated texture/RNG path from the remaining map-only gap.
Extend the rig to other types for full coverage.
Deliverables: `mksurface.py` (40-byte Surface.BIN), `capture_w7b.ps1`,
`godos_w7b.ps1`, `certify_w7b.py`, extended `memfind.py`.

**Feasible via the resume-from-save shortcut** (the recon's find): NOCTIS.CPP:2231-2255 --
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
(7a's `synchronize time=false` + pinned date/time -- `surface()` consumes `secs`, types
3/5/6 still need it). **This is 7b's first infra task.** AUTOTYPE only needs the one
snapshot key (not a full descent), so it is far more tractable than WAVEPLAN §7 feared;
the human 10-minute session is the fallback only if that single-key AUTOTYPE fails. **One
capture per planet type (10); per (type, sctype) for type-3.**

Before this capture existed, 7b graded only tiers 1-2 (C-from-source three-way)
and carried the **"type-3 ground terrain unvalidated against hardware" flag**
(WAVEPLAN §7 stall mode).  The capture now provides the binary oracle; the
remaining limitation is the measured heightmap mismatch below, not a missing
oracle or an unknown RNG seed.

### 2026-08-08 correction: type-3 fixture and exact remaining bound

The first `test_ground.py` capture fixture used `sctype=OCEAN, albedo=17` and
attributed its mismatch to an intervening Borland `random()` draw between
`srand(landing_pt_lat * landing_pt_lon)` at :2052 and the type switch at :2054.
That explanation is false:

- A preserved 16 MiB DOSBox-X guest-RAM image, decoded by
  `tests/gen/recon_w7b/diag_ground_state.py`, uniquely pins the shipped NIV+
  state at `sctype=OCEAN`, `albedo=40`, `rainy=3.75`, `latitude=0`, and
  `global_surface_seed=1029155`.
- The landing site is lon 0 / lat 60, so :2051-2052 re-seed both generators
  with `0`.  The source contains no call between that `srand(0)` and the switch.
- Because `albedo > 20`, OCEAN immediately takes `goto revert` into the shared
  PLAINS terrain with `waswet=1`.  The corrected source model matches all
  **65,536/65,536 ground-texture bytes** from NIV+; the old albedo-17 fixture
  differs in **42,277 bytes**.  This exact long random-driven texture agreement
  rules out the proposed one-draw shift.
- The first corrected model still differed in **39,710/40,000 bytes**. All
  24 possible evaluation orders for the four random `round_hill` arguments
  were tried; none matched. Later disassembly of `NOCTIS.EXE` proved the
  missing rule: DOS `unsigned` is 16-bit, so a negative `cx-r` or `cz-r`
  wraps and the original unsigned loop comparison skips that hill instead of
  clipping it at the map edge. Reproducing those exact bounds closes 37,958
  bytes and leaves **1,752/40,000** different.
- That residual is not safely attributable to `build_surface`: the available
  RAM oracle is captured after `planetary_main` has begun and the original
  reuses `p_surfacemap` as scratch. An earlier 15-second certified capture is
  byte-identical, confirming stability but not restoring the missing
  return-boundary image. The residual is therefore kept as a post-landing
  capture XFAIL, not as a claim that `round_hill` is still unknown.

The durable test now asserts the exact texture positively, rejects the old
fixture as a broken control, and carries the post-landing heightmap residual as
`diff == 1752`. It also changes one byte that currently agrees and requires
the boundary to change to 1,753, proving the check can fail. A pristine
return-boundary capture may replace this residual with byte equality; it must
not silently update the stored difference count.

## Float sites (exact-required)

Three C-cast chops on the ground path, all feeding discrete decisions -- use `FToIntChop`
or `work/geoconv.txt`'s live-chop fragments (FLOATPOLICY §3.3) until `genfp` refuses a
bare `fistp`:
- `depth = (long)(hpdep) >> 14` (NOCTIS-1.CPP:1088) -- chop of `sqrt`; drives cull/fog/detail.
- `ipfx/ipfz = ((long)cam_x/cam_z) >> 14` (:4063-4064, :4311-4312) -- drives fragment bounds.
- `atl_x = ((long)pos_x) >> 14` (:4179-4182) → SURFACE.BIN (state-carrying).

Everything else on the ground/sky path is rendering-tolerant (native lino floats, ±1 px
envelope) -- the 37 hand-`fistp` sites reproduce for free under `FEnter`'s 133Fh.

## Buffer-alias hazards (do NOT clamp)

- `txtr = n_globes_map` (32,768 B) read as 256×256 overruns into `s_background` whenever
  the horizon renders -- **faithful by farmalloc order (LINOBUF §2.4 row 1); the sea-texture
  overrun WILL fire in 7b.** The flat workspace's layout already lands it correctly.
- `tinta`/`escrescenze` at `adapted` offset 63,996 (LINOBUF §4 alias 8) -- the per-texel
  shade colour; `niv-lr` relocates to 64,000, a confirmed divergence the test must reject.
- `create_sky(char atmosphere)` -- the `atmosphere` **parameter is a boolean**, not the
  `objectschart`-aliased buffer. Easy to wire backwards.

## SURFACE.BIN -- 40-byte NIV+ R2.3 layout

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
hud_rtl_closed`) which NIV+ dropped -- port writes 40, never 45. **Trap: `remove(surface_file)`
at NOCTIS.CPP:4487 deletes it on program exit -- capture before the DOS process ends.**

## Out of scope

- The capsule descent (opencapdelta/bounces, cumulative gravity) -- use the `entryflag=1`
  shortcut, never simulate the descent.
- `cplx_planet_viewpoint` + sun-angle math (Wave 8).
- Multi-hour walk frame sequences (input timing not bit-reproducible).

## One-line doc fix to pick up

FLOATSITES.md §2.1 row for NOCTIS-1.CPP:4179/4180 says "Current.BIN" -- it is Surface.BIN.
