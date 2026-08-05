# BUFFERMAP — the complete aliasing and overrun map of Noctis IV

**Wave 5, Recon A. Read-only analysis. No implementation.**

Sources analysed (the actual build set — `NOCTIS.MAK` links exactly three objects):

| file | role |
|---|---|
| `C:\programmieren\noctis\niv-plus\source\NOCTIS.CPP` | module 3: main, cockpit, GOES net, allocation |
| `C:\programmieren\noctis\niv-plus\source\NOCTIS-0.CPP` | module 1: base library, page ops, globes, star/planet surfaces |
| `C:\programmieren\noctis\niv-plus\source\NOCTIS-1.CPP` | module 2: planetary surface, sea, animals |
| `C:\programmieren\noctis\niv-plus\source\TDPOLYGS.H` | included by NOCTIS-0.CPP:720 — the 3D/texture engine |
| `C:\programmieren\noctis\niv-plus\source\NOCTIS-D.H` | buffer size constants |
| `C:\programmieren\noctis\niv-plus\source\NOCTIS-0.H` | shared externs |
| `C:\programmieren\noctis\niv-plus\source\NOCTIS-2.H`, `defs.h` | small shared externs |

Cross-checked against the modernised clone
`C:\programmieren\noctis\niv-lr\src\{noctis.cpp,noctis-0.cpp,noctis-1.cpp,tdpolygs.h,noctis-d.h}`.

**`GFX.H`, `FAST3D.H`, `TEXT3D.H`, `PITAGORA.H`, `ASSEMBLY.H` are NOT in the Noctis
build.** They belong to the older standalone tools (`DL.CPP`, `ST.CPP`, …). Several
`extern` declarations in `NOCTIS-0.H` are leftovers from them and have no definition
anywhere in the build — see §7 (dead declarations). Do not port them.

---

## 0. Executive summary — what the buffer model has to survive

1. **Eight heap buffers, 336,480 bytes total.** All eight are aliased by at least one
   other name; three are aliased by three or more.
2. **`txtr` is a roving byte pointer**, not a buffer. It is re-based at runtime onto
   `p_background`, `s_background` (indirectly), `n_globes_map`, `p_surfacemap`,
   `p_surfacemap + 2064`, and is *incremented by arbitrary byte amounts*
   (`txtr += 48`, `txtr += (x << 3)`). This is the single hardest constraint on the
   port: it forbids "one lino array per Noctis buffer".
3. **The texture unit always reads a full 64 KiB window** from wherever `txtr` points,
   because the texel address is built in the 16-bit register `BX`
   (`TDPOLYGS.H:2817-2821`). Three of the buffers `txtr` gets pointed at are smaller
   than 64 KiB. Those reads went into neighbouring DOS heap blocks and were harmless
   because nothing was read back.
4. **`adapted` is not a 64,000-byte page.** It is a full 64 KiB segment plus 4 bytes,
   because `poly3d`'s scanline filler computes its destination through a 16-bit `DI`
   that can be fed a garbage row address (`riga[]` indexed out of range).
5. **Borland `farmalloc` returns far pointers with offset 4**, and every hard-coded
   `es:[di+4]` in the assembly *is that offset* — it is not a 4-pixel skew. Proof in
   §4.1. Getting this wrong shifts every polygon 4 pixels relative to every HUD glyph.
6. **The DOS frame period is confirmed from source**: `sync_start`/`sync_stop`
   (`NOCTIS-0.CPP:6025-6038`) busy-wait for exactly one `clock()` tick, i.e.
   65536/1193182 s = **54.9254 ms**. The 55 ms in `niv-lr`'s `noctis-d.h:174` is a
   rounding, not the original.
7. **Recommended model (the answer this map feeds into decision A): one flat
   byte-per-unit workspace with integer base offsets, not separate arrays.** Cost
   ≈ 484,000 units ≈ 1.85 MiB against the measured 1 GB ceiling — 0.18%. See §8.

---

## 1. The eight heap buffers

All allocated once in `main()`, `NOCTIS.CPP:2163-2173`. Sizes from `NOCTIS-D.H:25-56`.

| # | name | decl type | bytes | alloc site | what it holds |
|---|---|---|---|---|---|
| 1 | `n_offsets_map` | `unsigned char far *` | 7,340 (`om_bytes`) | `NOCTIS.CPP:2163` | `offsets.map` — concave (sky) QT-VR sphere |
| 2 | `n_globes_map` | `char far *` **(signed!)** | 32,768 (`gl_bytes` 22,586 + `gl_brest` 10,182) | `NOCTIS.CPP:2164` | `globes.map` convex sphere / sea texture / pilot font |
| 3 | `s_background` | `unsigned char far *` | 64,800 (`st_bytes`) | `NOCTIS.CPP:2165` | star surface map / moon surface map / sky map / shading |
| 4 | `p_background` | `unsigned char far *` | 65,552 (`pl_bytes`) | `NOCTIS.CPP:2166` | 360×180 planetary map from orbit; ground texture |
| 5 | `p_surfacemap` | `unsigned char huge *` | 40,000 (`ps_bytes`) | `NOCTIS.CPP:2167` | 200×200 altimetry / disk read buffer / cockpit-screen texture |
| 6 | `objectschart` | `quadrant far *` | 40,000 (`oc_bytes`) | `NOCTIS.CPP:2168` | 200×200 surface object chart; atmosphere overlay |
| 7 | `pvfile` | `unsigned char far *` | 20,480 (`pv_bytes`) | `NOCTIS.CPP:2170` | polygonal-model arena, 16 handles |
| 8 | `adapted` | `unsigned char far *` | 65,540 (`sc_bytes`) | `NOCTIS.CPP:2171` | the off-screen 320×200 page + 1.5 KiB of slop |

**Total: 336,480 bytes.**

> `NOCTIS-D.H:58` claims `totale bytes 334941`. That figure is stale — it is short by
> 1,539. Recompute, do not copy.

`adaptor` (`NOCTIS-0.CPP:53`) is not a buffer: it is the literal far pointer
`0xA0000000` = VGA `A000:0000`. It is only ever the *destination* of
`pcopy`/`pclear`/`areaclear`. Nothing draws to it directly.

`sizeof(quadrant) == 1`. This is not obvious — the bitfields are declared `unsigned`
(`NOCTIS-D.H:171-176`), which normally implies a 2-byte storage unit — but it is
forced by the code: `NOCTIS-1.CPP:1177-1180` reads `ruinschart[h1]` and
`NOCTIS-1.CPP:1324` reads `objectschart[h1].nr_of_objects` **with the same index
`h1`**. If the struct were 2 bytes, the `for (ptr = 0; ptr < oc_bytes; ptr++)` loops
(`NOCTIS-1.CPP:1994, 2238, 2281, 2606, 2621`) would write 80,000 bytes into a
40,000-byte allocation and smash `pvfile` and `adapted`. It is 1 byte. Borland's
default byte alignment (`NOCTIS.MAK` compiler config: no `-a` flag) gives this.

### 1.1 Pointer identities inside `pvfile`

`pvfile` is a hand-rolled arena. Sixteen handles, each carving five (or ten)
sub-arrays out of one byte stream (`loadpv`, `NOCTIS-0.CPP:2303-2417`):

```
pv_n_vtx [h] = pvfile + datatop ;  datatop +=  1*npolygs   // char
pvfile_x [h] = pvfile + datatop ;  datatop += 16*npolygs   // float[4] per polygon
pvfile_y [h] = pvfile + datatop ;  datatop += 16*npolygs
pvfile_z [h] = pvfile + datatop ;  datatop += 16*npolygs
pvfile_c [h] = pvfile + datatop ;  datatop +=  1*npolygs   // char
   -- if depth_sort --
pv_mid_x [h] = pvfile + datatop ;  datatop +=  4*npolygs
pv_mid_y [h] = pvfile + datatop ;  datatop +=  4*npolygs
pv_mid_z [h] = pvfile + datatop ;  datatop +=  4*npolygs
pv_mid_d [h] = pvfile + datatop ;  datatop +=  4*npolygs
pv_dep_i [h] = pvfile + datatop ;  datatop +=  2*npolygs   // int
```

50 bytes/polygon, 68 with depth sorting. The whole polygon block is filled by **one
packed `_read`** (`NOCTIS-0.CPP:2350`). See §6.1 for why this breaks unit addressing.

---

## 2. The alias map

### 2.1 `n_globes_map` — triple-purposed, 32,768 bytes

| span (bytes) | alias | set at | contents |
|---|---|---|---|
| 0 … 22,585 | `n_globes_map` | `NOCTIS.CPP:2164` | `globes.map`: 11,293 `(dy,dx)` byte pairs, the convex QT-VR sphere |
| 22,586 … 31,945 | `digimap2` (`unsigned long far *`) | `NOCTIS.CPP:2173` | 32×36 pilot font, 65 glyphs × 36 rows of `uint32` bitmaps (`dm2_bytes` = 9,360) |
| 0 … 32,767 | `txtr` (sea/horizon texture) | `NOCTIS-1.CPP:4004, 4066, 4239, 4322, 4344` | 256×128 sea gradient at stride 256 |

**Timing.** `NOCTIS-1.CPP:4000-4003` fills the entire 32,768 bytes:

```c
QUADWORDS = 256;
for (ptr = 0; ptr < 32; ptr++) pclear (&n_globes_map[ptr<<10], ptr >> 1);
```

32 × 1,024 = 32,768 — the sea gradient destroys `globes.map` **and** `digimap2`.
Further writes: `NOCTIS-1.CPP:4086` (`n_globes_map[fast_random(32767)]`),
`NOCTIS-1.CPP:4096`, `NOCTIS-1.CPP:4241` and `4364` (the wave scroll
`n_globes_map[ptr] = n_globes_map[ptr-256] >> 1` for `ptr` 20,736…32,767),
`NOCTIS-1.CPP:4355-4360`.

**Repair.** All three maps are reloaded together on leaving a planet:
`NOCTIS-1.CPP:5039-5041` → `load_QVRmaps()` (`NOCTIS-0.CPP:6077`, reloads
`n_offsets_map` *and* `n_globes_map[0..22585]`), `load_starface()`,
`load_digimap2()` (`NOCTIS-0.CPP:6094`, reloads `n_globes_map[22586..31945]`).
Same trio at init, `NOCTIS.CPP:2185-2187`.

**`digimap2` is misaligned.** 22,586 mod 4 = 2. It is a `uint32` array starting at
byte offset 22,586 of a byte array. Every `digimap2[n+d]` read (`NOCTIS.CPP:621`) is
a 2-mod-4 dword load.

**`n_globes_map` is `char` (signed).** `NOCTIS-0.CPP:1004`. It is assigned to
`unsigned char huge *txtr` (`NOCTIS-1.CPP:1219` etc.) and passed as
`unsigned char far *` to `globe`/`glowinglobe` (`NOCTIS.CPP:2588`,
`NOCTIS-0.CPP:5592`). The scroll `n_globes_map[ptr-256] >> 1` at
`NOCTIS-1.CPP:4241` is therefore an **arithmetic** shift in the original. Values are
0…63 in practice so it does not bite, but the port must not silently switch to
unsigned and call it equivalent without checking the loaded `globes.map` bytes.

### 2.2 `objectschart` — three names, one byte, two of them sub-byte

```c
objectschart  = (quadrant far *) farmalloc (oc_bytes);   // NOCTIS.CPP:2168
ruinschart    = (unsigned char far *) objectschart;      // NOCTIS.CPP:2169
```
plus two function-local aliases:
```c
char far *atmosphere = (char far *) objectschart;              // NOCTIS-0.CPP:5255 (planets)
unsigned char far *overlay = (unsigned char far *)objectschart;// NOCTIS-0.CPP:4774 (surface)
```

The `quadrant` byte layout (`NOCTIS-D.H:171-176`), bit 0 = LSB:

```
bits 0-1  nr_of_objects
bits 2-3  object0_class
bits 4-5  object1_class
bits 6-7  object2_class
```

`ruinschart[pt] = AF1` where `AF1 = 0x40`, `AF2 = 0x80`, `AF3 = 0xC0`
(`NOCTIS-D.H:155-157`). **The ruin style is stored in the `object2_class` bitfield.**
`ruinschart` and `objectschart` are not merely two views of the same array — they are
two views of the same *byte*, and the ruins writer clobbers an object slot. Sites:
`NOCTIS-1.CPP:1813, 1827, 1831, 1837, 1841, 1863, 1866, 1874, 1877, 1899, 1904, 1919,
1935, 1937, 2703, 2707`; readers `NOCTIS-1.CPP:1177-1180, 1251-1254`.

**Two different resolutions, two different lifetimes:**

| phase | alias | extent | stride |
|---|---|---|---|
| in orbit | `atmosphere` / `overlay` | bytes 0 … 32,399 | one byte per **two** cells of the 360×180 orbital map: index `(360*lat + lon) >> 1` |
| landed | `objectschart` / `ruinschart` | bytes 0 … 39,999 | one byte per cell of the 200×200 surface grid |

The orbital atmosphere is written by `cirrus()` (`NOCTIS-0.CPP:4716-4727`) —
inline asm, `bx = (py + px) >> 1`, 16-bit — and by
`atm_cyclon`/`storm`/`permanent_storm`. It is consumed at
`NOCTIS-0.CPP:5089-5092` (merged into `p_background`) and read back at
`NOCTIS-0.CPP:5501, 5508, 5513` as `atmosphere[ptr>>1]` to recover the true ground
albedo before landing. The landed object chart is built by `NOCTIS-1.CPP:1970`
(`_fmemset(objectschart, 0, oc_bytes)`) onward, destroying the atmosphere overlay.

Naming trap: `create_sky(char atmosphere)` (`NOCTIS-1.CPP:2736`) has a **parameter**
named `atmosphere` that shadows nothing (the alias is a local in `planets`) — it is a
boolean, not the buffer. Do not conflate.

### 2.3 `p_background` ⟷ `s_background` — a *runtime pointer swap*

This is the alias the task brief did not list and it is the most dangerous one,
because the identity of `p_background` changes mid-frame.

```c
void planets () {
    unsigned char far *surface_backup = (unsigned char far*)p_background;  // NOCTIS-0.CPP:5256
    ...
    for (c=0; c<nearstar_nob; c++) {
        if (nearstar_p_owner[n] > -1) { p_background = s_background;   colorbase = 128; }  // 5326
        else                          { p_background = surface_backup; colorbase = 192; }  // 5331
        ...
    }
    p_background = surface_backup;   // NOCTIS-0.CPP:5605  (restored on exit)
}
```

Rationale is documented at `NOCTIS-0.CPP:4460-4478`: from a moon you can see its
parent planet, so two 64,800-byte surface maps must be resident at once. The star
surface map (`s_background`) is sacrificed to hold the moon's. `resident_map1` /
`resident_map2` (declared `NOCTIS-0.CPP:869`, maintained at `NOCTIS-0.CPP:5291-5318`)
track which two bodies are cached; `npcs` invalidates the cache.

**Consequence: `s_background` is 64,800 bytes but is used everywhere `p_background`
(65,552 bytes) is used.** Everything in §4.3 that overruns `p_background` overruns
`s_background` by 752 more bytes. `s_background` also holds the sky map
(`NOCTIS-1.CPP:3683-3694`) and a shading buffer, and is the `tapestry` argument to
`globe()` for the star (`NOCTIS.CPP:2588`).

### 2.4 `p_surfacemap` — triple-punned, and the only `huge` pointer

| use | alias / cast | site | extent |
|---|---|---|---|
| 200×200 byte altimetry | `p_surfacemap` | `NOCTIS-1.CPP:1969` onward | 0 … 39,999 |
| STARMAP.BIN record buffer, **char and double simultaneously** | `char far *buffer_ascii`, `double far *buffer_double` | `NOCTIS-0.CPP:4008-4009`, `NOCTIS-0.CPP:5751-5752` | 0 … 39,999 |
| 256-stride cockpit-screen texture | `txtr` | `NOCTIS.CPP:615`, `NOCTIS.CPP:1010` | −6 … 10,301 written, 0 … 67,599 read |

The double-punning is real simultaneous aliasing, not sequential reuse:

```c
char   far *buffer_ascii  = (char far *)p_surfacemap;
double far *buffer_double = (double far *)p_surfacemap;
...
if (buffer_ascii[ptr + 29] == type)                 // byte 29 of a 32-byte record
    if (buffer_double[index] > id_low && ...)       // index = ptr/4 → the double at byte ptr
```
`ptr += 32; index += 4;` — 32-byte records, an 8-byte `double` at record offset 0 and
a type byte at record offset 29. `NOCTIS-0.CPP:4020-4030` and `5768-5790`.

`p_surfacemap` is the only buffer declared `huge` (`NOCTIS-0.CPP:998`) — because it is
the only one indexed with a `long` (`p_surfacemap[200*(long)z+x]`,
`NOCTIS-1.CPP:1515,1524`) and the only one with a **negative** index (§4.2).

### 2.5 `txtr` — a roving base pointer, not a buffer

`unsigned char huge *txtr` — declared `TDPOLYGS.H:1775`, never allocated in Noctis
(`init_texture_mapping`, `TDPOLYGS.H:1778`, is **never called**; `load_texture` and
`fast_load_texture` are dead too). It is only ever an alias. Complete list of bases:

| base | sites |
|---|---|
| `p_background` | `NOCTIS.CPP:2172` (initial), `NOCTIS.CPP:1106`, `NOCTIS-1.CPP:813, 1176, 1250, 1339, 4062, 4114, 4307, 4337, 4407` |
| `n_globes_map` | `NOCTIS-1.CPP:1219, 4004, 4066, 4239, 4322, 4344` |
| `p_surfacemap` | `NOCTIS.CPP:615` (`digit_at`) |
| `p_surfacemap + 256*8 + 16` (= +2,064) | `NOCTIS.CPP:1010` (`vehicle`, GOES screens) |
| saved/restored around a sub-draw | `NOCTIS-1.CPP:247/279, 289/312`; `NOCTIS.CPP:592/642` |
| **byte-granular slides** | `NOCTIS-1.CPP:274` `txtr += 48`; `NOCTIS-1.CPP:1273` `txtr += (x << 3)` |

The last row is the killer for unit addressing: `txtr += 48` and `txtr += x*8` shift
the texture window by a number of bytes that is not a multiple of 4 in general
(`x<<3` is, `48` is, but the *base* `p_surfacemap + 2064` combined with `−4` in the
fetch is not — see §3).

### 2.6 `adapted` — the page, plus two scratch bytes inside it

`adapted[0xFA00]` and `adapted[0xFA01]` (segment-relative 64,000/64,001) are used by
`polymap` as scratch registers for the fill colour `tinta` and the bump colour
`escrescenze` (`TDPOLYGS.H:2684-2687`, read back at `2701, 2733, 2861, 2869`).
`niv-lr` reproduces this at `tdpolygs.h:938-939`. In pointer terms (offset 4, §4.1)
those are `adapted[63996]` and `adapted[63997]` — **inside the visible page**, row
199, columns 316-317. Falsifiable prediction for a later wave: those two pixels
carry polygon fill colour in real Noctis whenever `polymap` has run.

`adapted` is also a general-purpose 1 KiB I/O scratch in the BMP writer
(`NOCTIS-1.CPP:4693-4714`: `_read (i9997, adapted, 1024)` etc.) — which runs *after*
the frame has been copied out.

`adapted` is **freed and reallocated** at runtime: `farfree(adapted)`
(`NOCTIS.CPP:479`) before launching a GOES Net module, `farmalloc` again at
`NOCTIS.CPP:501`. `seg_adapted` (`NOCTIS-0.CPP:1006`) is *not* recomputed —
`init_FP_segments()` (`NOCTIS-0.CPP:5610`) is called exactly once, at
`NOCTIS.CPP:2200`. The code silently depends on `farmalloc` returning the same
address. Port note: keep the framebuffer address fixed and this problem disappears.

### 2.7 Alias summary table

| allocation | aliases | offset into allocation |
|---|---|---|
| `n_globes_map` | `digimap2` | +22,586 (2 mod 4) |
| `n_globes_map` | `txtr` | 0 |
| `objectschart` | `ruinschart` | 0 (same byte, different bitfields) |
| `objectschart` | `atmosphere`, `overlay` | 0 (half-resolution index) |
| `p_background` | `txtr` | 0 |
| `p_background` | *becomes* `s_background` | pointer swap |
| `p_surfacemap` | `buffer_ascii`, `buffer_double` | 0 (simultaneous char/double) |
| `p_surfacemap` | `txtr` | 0 and +2,064 |
| `pvfile` | `pv_n_vtx[h]`, `pvfile_x/y/z[h]`, `pvfile_c[h]`, `pv_mid_*[h]`, `pv_dep_i[h]` | arbitrary, per handle, unaligned |
| `adapted` | `tinta`/`escrescenze` scratch | +63,996 (segment 0xFA00) |

---

## 3. How the texture unit addresses `txtr` — the 64 KiB window

`polymap`'s inner fill (`TDPOLYGS.H:2821-2825`) builds the texel address like this:

```asm
mov bh, dh          ; BH = bits 8..15 of the 32-bit V accumulator
mov bl, ah          ; BL = bits 8..15 of the 32-bit U accumulator
db 0x64, 0x02, 0x2F ; add ch, fs:[bx]      ; FS = segment of txtr
```

`BX` is a 16-bit register. **The texel index is `((V>>8)&0xFF)*256 + ((U>>8)&0xFF)`,
always in 0…65535, always wrapping, never clipped.** `FS` is built at
`TDPOLYGS.H:2677-2681` by folding the far pointer's offset into the segment
(`shr dx,4; add ax,dx`) — so the window really is `txtr[0 .. 65535]`.

`niv-lr` translates this literally at `tdpolygs.h:1013-1015`:
```cpp
tch += txtr[(uint16_t) (tbx - 4)];   // NOTE; Fudge factor ... loss of offset on txtr
```
(the `−4` is their compensation for normalising the far-pointer offset away).

**Therefore every buffer `txtr` can point at needs a 65,536-byte readable window from
its `txtr` base.** Current sizes:

| `txtr` base | window needed | actually allocated | shortfall |
|---|---|---|---|
| `p_background` | 65,536 | 65,552 | 0 (this is why `pl_bytes` = 65,536 + 16) |
| `s_background` (via the swap) | 65,536 | 64,800 | **736** |
| `n_globes_map` | 65,536 | 32,768 | **32,768** |
| `p_surfacemap` | 65,536 | 40,000 | **25,536** |
| `p_surfacemap + 2,064` | 67,600 | 40,000 | **27,600** |

`niv-lr` papers over exactly the last two with
`malloc(ps_bytes | 65536)` = 105,536 bytes (`noctis.cpp:2605`, with the comment
"polymap keeps running over the end … The bug is present in the original source").
They did **not** pad `n_globes_map` or `s_background` — those are still live
out-of-bounds reads in `niv-lr`.

`H_MATRIXS`/`V_MATRIXS` change `XSIZE`/`YSIZE` (`TDPOLYGS.H:121-124`,
`change_txm_repeating_mode` at `TDPOLYGS.H:396`) and so change how fast `U`/`V`
sweep, but never the 64 KiB wrap.

---

## 4. Out-of-bounds accesses the DOS layout absorbed

### 4.1 SETTLED: `farmalloc` returns offset 4; `es:[di+4]` is that offset

Three addressing conventions coexist in the assembly:

* **(a) offset-included.** `les di, dword ptr <ptr>` then `add di, <index>`, write
  `es:[di]`. Used by `pclear` (`NOCTIS-0.CPP:339`), `pcopy` (`:317-318`), `areacopy`
  (`:372-375`), `areaclear`, `mask_pixels` (`:703`), `ssmooth` (`:4423`),
  `spot` (`:4487`), `cirrus` (`:4717`), `load_starface` (`:6049`),
  `globe`'s **tapestry** (`:3092-3094`, `add start, ax`), `pointer_cross_for`
  (`NOCTIS.CPP:265-266`), and the vertical-line branch of `Stick`
  (`NOCTIS-0.CPP:1566-1569`) and `Segmento` (`TDPOLYGS.H:167-171`).
* **(b) segment-only + hard-coded `+4`.** `mov es, seg_adapted` or
  `les ax, dword ptr <ptr>` (offset discarded), write `es:[di+4]`. Used by the general
  branch of `Stick` (`NOCTIS-0.CPP:1657-1675`), `Segmento` (`TDPOLYGS.H:245-256`),
  `polymap`'s fills (`TDPOLYGS.H:2820-2900`, `mov [di+3]` after `inc di`), the `gman`
  dot writers (`NOCTIS-0.CPP:3009, 3015, 3022, 3033`), `NOCTIS-0.CPP:2730, 2921-2944,
  3267-3269`, `NOCTIS-1.CPP:150-152`, `NOCTIS.CPP:3174-3175`.
* **(c) segment-only, `DI = 0`.** `pfade` (`NOCTIS-0.CPP:514-540`) and `psmooth_64`
  (`NOCTIS-0.CPP:574-604`): `lds ax, target; mov ax, ds; add ax, segshift; mov ds, ax;
  xor di, di`.

**The decisive evidence is `Stick`.** Its vertical special case
(`NOCTIS-0.CPP:1553-1571`) computes `pi = riga[yp] + xp`, adds the far-pointer offset
(`add pi, si` where `les si, adapted`), and writes `es:[si]` with **no** `+4`. Its
general case (`NOCTIS-0.CPP:1668-1675`) computes `di = riga[y] + x` **without** the
offset and writes `es:[di+4]`. Both write the same word `0x3E00`. Vertical and
near-vertical sticks are drawn side by side every frame (the surface-map crosshair,
`NOCTIS.CPP:1085-1092`). They can only land in the same column if
`offset(adapted) == 4`. `Segmento` in `TDPOLYGS.H` has the identical split.

Corroboration: `sc_bytes = 65540 = 64 KiB + 4`, described at `NOCTIS-D.H:47-54` as an
extension "to avoid the overrun of poly3d". With offset 4 and a 16-bit `DI`, the
reachable write range is exactly segment offsets 4 … 65,539.

**Port consequences.**
* `adapted[0]` is the top-left pixel. There is **no** 4-pixel skew to reproduce.
* Convention (c) *is* skewed by 4 bytes relative to the pixel grid. It only ever runs
  a whole-page fade/smooth, so the skew is invisible — reproduce it or don't, but know
  it is there before you "fix" a 4-byte offset in a fade.
* The `tinta`/`escrescenze` scratch at segment 0xFA00 lands at `adapted[63996..63997]`
  — a visible pixel pair. `niv-lr` relocated it to `adapted[64000]`
  (`tdpolygs.h:938`). Relocating is the sane choice; record that it is a deliberate
  divergence.
* Residual uncertainty: this is inferred, not measured on hardware. **Decisive
  experiment** if it ever matters: run `NOCTIS.EXE` under DOSBox-X, break after
  `init_FP_segments`, and read the offset word of the global `adapted` (address
  obtainable from `NOCTIS.SYM`). One read settles it.

### 4.2 `digit_at` writes 6 bytes *below* `p_surfacemap`

`NOCTIS.CPP:614-628`:

```c
txtr = p_surfacemap;
for (n = 0; n < 36; n++) {
    i = 256 * n - 5;
    txtr[i-1] = 0;          // n == 0  ->  txtr[-6]
    for (m = 0; m < 32; m++) { ... txtr[i] = ...; i++; }   // n == 0 -> txtr[-5 .. 26]
}
```

At `n == 0`, `i == -5`, so `txtr[-6] … txtr[-1]` are written — **6 bytes before the
allocation**. `txtr` is `huge`, so the index sign-extends and the segment normalises
down; the writes land in the far-heap block header region.

Independently confirmed by `niv-lr`: `noctis.cpp:643-646` —
"Valgrind said there was a big bad invalid write happening here, so I just blindly
changed this loop to start at one. It probably breaks things..." — and it does: their
`for (n = 1; ...)` drops the top scanline of every cockpit glyph. **The port must
allocate 6 bytes (2 units) of headroom below `p_surfacemap`, not truncate the loop.**

Upper end of `digit_at` is clean: last write is `txtr[256*36-6]` = `txtr[9210]`
(`NOCTIS.CPP:629`).

### 4.3 Reads past the end of the map buffers

| site | expression | max index | buffer | overrun |
|---|---|---|---|---|
| `NOCTIS-1.CPP:77` (`hpoint`) | `p_surfacemap[cpos+201]` | 40,200 | 40,000 | **+201 read** |
| `NOCTIS-1.CPP:1127` (`fragment`) | `p_surfacemap[h1 + sh_delta]`, `sh_delta ∈ {−1,0,+1}` (`NOCTIS-1.CPP:2718-2723`) | −1 … 40,000 | 40,000 | **±1 read** |
| `NOCTIS-0.CPP:4419-4427` (`ssmooth`) | `es:[di+360]`, `di < (QUADWORDS−80)*4` with `QUADWORDS = 16200` (`NOCTIS-0.CPP:4845`) | 64,839 | `s_background` 64,800 when swapped | **+39 read** |
| `NOCTIS-0.CPP:3092-3140` (`globe`) | tapestry `BX` = `start + Σ run-lengths`, `start = plwp + rotation ≤ 718` (`NOCTIS-0.CPP:5564`) | ≈65,518 | `p_background` 65,552 OK; `s_background` 64,800 when swapped | **+718 read** |
| `TDPOLYGS.H:2821` (`polymap`) | `txtr[BX]`, `BX` 16-bit | 65,535 | see §3 table | up to **+32,768** |

### 4.4 Writes that depend on 16-bit wrap

None of these leave the 64 KiB segment; all of them *depend* on the truncation.

| site | mechanism |
|---|---|
| `NOCTIS-0.CPP:4716-4727` (`cirrus`) | `bx = (py + px) >> 1` with `py = 360*lat` possibly negative or > 180 (`atm_cyclon` at `:4735-4740` freely adds `±359`, `±361`). `bx` wraps mod 65536 before the `>>1`, landing anywhere in `objectschart[0..32767]`. |
| `NOCTIS-0.CPP:4485-4496` (`spot`) | `di = offset(p_background) + py + px`, 16-bit, `unsigned px, py` (`NOCTIS-0.CPP:4446`). Negative `cy` wraps to the tail of the buffer. |
| `NOCTIS-0.CPP:5069-5071` | `for (px = 0; px < 64800; px++)` with `unsigned px` — relies on 16-bit unsigned counting. |
| `NOCTIS-0.CPP:6423` | `for (ptr = 63680; ptr < 64000; ptr -= 320)` — terminates only because `ptr` is `unsigned` and wraps to 65,216 after 0. |
| `NOCTIS-0.CPP:691-710` (`mask_pixels`) | `add di, 4` × `QUADWORDS` from `adapted+2880`; with `QUADWORDS = 16000` the 16-bit `DI` wraps past 65,535 back through 0. Call sites `NOCTIS-1.CPP:3998, 4450`, `NOCTIS.CPP:2577`. |

### 4.5 The one that forced `sc_bytes = 65540`

`Segmento` (`TDPOLYGS.H:245-259`) and `Stick` (`NOCTIS-0.CPP:1668-1675`) do:

```asm
mov bx, word ptr global_y[2]   ; integer part of the interpolated Y
add bx, bx
add di, word ptr riga[bx]      ; riga is `unsigned riga[200]`  (TDPOLYGS.H:130)
mov byte ptr es:[di+4], 255
```

`riga[]` has 200 entries. Nothing bounds `global_y`'s integer part to 0…199. Whenever
it strays, `riga[bx]` reads adjacent data-segment globals and `DI` becomes arbitrary
— the write then lands anywhere in `adapted`'s 64 KiB segment. That is precisely the
"funzione difettosa … che non ho né tempo né voglia di modificare" of
`NOCTIS-D.H:50-54`, and precisely why the page is a full segment plus 4.

`niv-lr` clamps it instead (`noctis-0.cpp:1296`,
`index = std::min(index, adapted_width*adapted_height - 1)` with the comment
"TODO; Figure out why this is over-running and actually fix it").

**Port decision to make explicitly: clamp (visible artefact differs) or allocate the
full 65,540-byte page and let it scribble (bit-faithful).** Cost of faithful is 1,540
extra units. Take the faithful one.

### 4.6 `loadpv` writes 3 × npolygs bytes past `pvfile_c`

`NOCTIS-0.CPP:2383-2391`:

```c
for (c = 0; c < 4*pvfile_npolygs[handle]; c++) {
    pvfile_x[handle][c] *= xscale; ...      // correct: 4 floats per polygon
    pvfile_c[handle][c] += base_color;      // WRONG: pvfile_c is npolygs BYTES
}
```

`pvfile_c[h]` was sized `1 * npolygs` (`NOCTIS-0.CPP:2334-2335`). The loop writes
`4 * npolygs`. With `depth_sort` the extra 3 × npolygs bytes land in the
`pv_mid_*` region, which is fully initialised immediately afterwards
(`NOCTIS-0.CPP:2394-2412`) — self-repairing. **Without** `depth_sort` they land in
unallocated arena, and if `datatop` is near `pv_bytes` they leave the 20,480-byte
buffer entirely. Load order therefore matters. `unloadpv`
(`NOCTIS-0.CPP:2226-2271`) compacts the arena with `_fmemmove` and rebases every
handle's pointers by `-datalen`, so any corruption migrates.

### 4.7 Small static-buffer overruns (Noctis-IV-Plus era, not 1996)

* `snapfilename[24]` (`NOCTIS-0.CPP:6291`) vs
  `sprintf(snapfilename, "..\\MOVIES\\%03i\\%08d.BMP", ...)` (`NOCTIS-0.CPP:6343`) —
  26 chars + NUL = **27 bytes into 24**. The gallery path (`:6345`) fits exactly at 24.
* `ctb[512]` (`NOCTIS-0.CPP:840`) is written by `cline`/`other`
  (`NOCTIS.CPP:291-320`) with `movsb` until NUL and **no length check**; overflow
  runs into `dec[20]` and `triadFormat[10]` (`NOCTIS-0.CPP:841-842`).
* `wrouthud` (`NOCTIS-0.CPP:6117-6140`) indexes `digimap[(text[n]-32)*5 + i]` with no
  range check; any character outside 32…96 reads outside `digimap[325]`.

---

## 5. `QUADWORDS` — the mutable page-length global

`int QUADWORDS = 16000;` (`NOCTIS-0.CPP:51`). It is the dword count for `pcopy`,
`pclear`, `pfade`, `psmooth_grays`, `psmooth_64`, `ssmooth`, `lssmooth`,
`mask_pixels`. **It is changed at runtime and every one of those routines silently
reinterprets its operand size.**

| value | bytes | set at | meaning |
|---|---|---|---|
| 16,000 | 64,000 | default; `NOCTIS.CPP:2261, 3635`; `NOCTIS-1.CPP:4578` | full 320×200 page |
| 14,560 | 58,240 | `NOCTIS.CPP:2206` (`QUADWORDS -= 1440`), then `pqw` | 182 rows — the steady-state value for the whole session |
| 16,200 | 64,800 | `NOCTIS-0.CPP:4845` (inside `surface`) | the 360×180 planetary map |
| 16,200 | 64,800 | `NOCTIS-1.CPP:1679, 1709` (`st_bytes/4`) | the sky map in `s_background` |
| 256 | 1,024 | `NOCTIS-1.CPP:4000` | one 1 KiB slab of the sea gradient |
| 800 / 15,040 | 3,200 / 60,160 | `NOCTIS.CPP:511, 513` | GOES module screen restore |
| 160 + 80·`openhudcount` | — | `NOCTIS-1.CPP:4525`, `NOCTIS.CPP:2970` | HUD visor animation |

Any port that hard-codes 64,000 into its page operations will get the HUD-open/closed
animation and the surface-map generation wrong.

---

## 6. Byte arithmetic that does not survive unit addressing

Ordered by how much it hurts.

### 6.1 Mixed-type sub-arrays at arbitrary byte offsets (`pvfile`)

`pvfile_x[h] = (float far *)(pvfile + pvfile_datatop)` where `datatop` has just been
advanced by `1 * npolygs` (`NOCTIS-0.CPP:2326-2329`). If `npolygs` is not a multiple
of 4, **the float array starts at a non-multiple-of-4 byte offset**. The 8086 does not
care. A unit-addressed machine cannot express it at all without either (i) storing
each float across two units with shifts, or (ii) re-laying-out the arena so every
sub-array is unit-aligned and fixing the single packed `_read` at
`NOCTIS-0.CPP:2350` to a per-field scatter. **(ii) is the only sane choice**; it is
observationally equivalent because nothing outside `loadpv` depends on the packing.
`unloadpv`'s `_fmemmove` compaction (`NOCTIS-0.CPP:2261-2263`) must move in
sub-array units, not bytes.

### 6.2 `digimap2` at byte offset 22,586 inside a byte array

2 mod 4. A `uint32` view of `n_globes_map[22586 …]`. Under unit addressing the font
must be a separate unit array (it is logically separate anyway) — but then the
"sea texture destroys the font" behaviour at `NOCTIS-1.CPP:4000-4003` must be
reproduced deliberately, or the font must be reloaded on the same schedule.

### 6.3 Sub-byte fields (`quadrant` / `ruinschart`)

Four 2-bit fields in one byte, written through two different names (§2.2). Under one
byte per unit this is a shift/mask on a unit — cheap and exact. Under 4-bytes-per-unit
packing it is a shift/mask *inside* a shift/mask.

### 6.4 Half-resolution index aliasing

`atmosphere[ptr >> 1]` where `ptr = 360*lat + lon` (`NOCTIS-0.CPP:5501, 5508, 5513`)
and `bx = (py + px) >> 1` (`NOCTIS-0.CPP:4720`). Fine in units, but the `>>1` must be
applied to the *wrapped 16-bit* value, not to the wide value.

### 6.5 Odd strides

* 200 and 201 — `p_surfacemap[cpos]`, `[cpos+1]`, `[cpos+200]`, `[cpos+201]`
  (`NOCTIS-1.CPP:75-78`, `3277-3280`); `m200[]` is the ×200 lookup
  (`NOCTIS-0.CPP:1029`).
* 360 — the orbital map (`NOCTIS-0.CPP:5111-5124`, the day/night terminator asm:
  130 bytes then `add di, 230`).
* 256 — the texture and cockpit-screen stride, on buffers whose natural width is 200
  or 360.
* 320 — every `adapted` write; `riga[c] = 320*c` (`TDPOLYGS.H:132-137`).
* 5 bytes per glyph in `digimap`, 3 bits used per byte (`NOCTIS-0.CPP:6128-6132`).

### 6.6 Packed reads and writes from disk

| site | shape |
|---|---|
| `NOCTIS-0.CPP:2323` | `_read(fh, &pvfile_npolygs[handle], 2)` — 16-bit LE count |
| `NOCTIS-0.CPP:2350` | one `_read` of `50*npolygs` bytes: `char[n]`, `float[4n]`×3, `char[n]` |
| `NOCTIS-0.CPP:6083, 6089, 6100` | raw map/font blobs straight into the heap buffers |
| `NOCTIS-0.CPP:4017, 5759` | STARMAP.BIN read into `p_surfacemap`, then punned char/double |
| `NOCTIS.CPP:453` (`freeze`) | `_write(fh, &sync, 245)` — **a byte-exact dump of 40+ consecutive globals** |
| `NOCTIS-0.CPP:6305, 6416-6423` | 54-byte BMP header + palette + bottom-up scanlines |

The `freeze`/`unfreeze` block is the nastiest of these: `NOCTIS-0.CPP:739-820` declares
`char`, `int`, `float`, `double` and `char[11]` in a fixed order and the code writes
245 raw bytes starting at `&sync`. The documented offsets in the comments
(`// 0`, `// 25`, `// 39`, `// 71`, `// 183`, `// 244`) confirm **byte packing with no
alignment padding** — 8-byte doubles at offsets 71, 79, 87, 95, … and 4-byte floats at
39, 43, 47. Any port must build this record explicitly, field by field; it cannot come
out of a struct.

### 6.7 Signedness

* `char far *n_globes_map` is signed (`NOCTIS-0.CPP:1004`) and is right-shifted
  (`NOCTIS-1.CPP:4241, 4364`).
* `n_globes_map` is passed to functions expecting `unsigned char far *` without a
  cast (`NOCTIS.CPP:2588`, `NOCTIS-0.CPP:5592`) — legal-with-warning in Borland.
* `digimap2` is `unsigned long`.
* `objectschart`'s bitfields are `unsigned`.
* `p_surfacemap` values are used as `- ((long)v << 11)` (`NOCTIS-1.CPP:75-78`), so
  they are unsigned 0…127 heights.

---

## 7. Dead declarations — do not port

Declared `extern` in `NOCTIS-0.H` but **never defined anywhere in the build set**
(verified by grep over `NOCTIS-0.CPP`, `NOCTIS-1.CPP`, `NOCTIS.CPP`, `TDPOLYGS.H`):

`wtxtr` (`NOCTIS-0.H:77`), `cyclon[384]` (`:172`), `fnv`, `fcolor`, `fx`, `inv_fx`,
`fy`, `fz`, `vhx`, `vhy`, `vhz`, `vhxm`, `vhym`, `vhzm`, `vh_mdq`, `vhnv`, `vhcolor`,
`vhindex`, `ix`, `iy`, `iz`, `inv`, `icolor`, `alpha_nv`, `alpha_x`, `alpha_y`,
`alpha_z` (`:265-276`).

Dead **code** in `TDPOLYGS.H`: `init_texture_mapping` (`:1778`), `load_texture`
(`:1791`), `fast_load_texture` (`:1823`) — `txtr` is overwritten by the alias at
`NOCTIS.CPP:2172` and none of these is ever called. The `farmalloc` at
`TDPOLYGS.H:1783` never runs.

---

## 8. Quantification

### 8.1 Bytes today

**Heap: 336,480 bytes** (§1).

**Static / data-segment buffers**, the ones large enough to matter:

| buffer | bytes | site |
|---|---|---|
| `nearstar_p_*` × 17 arrays, `maxbodies` = 80 | 6,640 | `NOCTIS-0.CPP:932-950` |
| `ani_*` / `tgt_*` × 14 arrays, `LFS` = 100 | 4,500 | `NOCTIS-1.CPP:549-562` |
| `lft_sin[361]` + `lft_cos[361]` (float) | 2,888 | `NOCTIS-0.CPP:3619-3620` |
| `tmppal` + `return_palette` + `surface_palette` (768 each) | 2,304 | `NOCTIS-0.CPP:56-58` |
| `targets_table_id/px/py/pz[50]` (double) | 1,600 | `NOCTIS-0.CPP:5741-5744` |
| `pv_*[16]` pointer tables (10 arrays) | 640 | `NOCTIS-0.CPP:1059-1068` |
| `ctb[512]` | 512 | `NOCTIS-0.CPP:840` |
| `m200[200]`, `riga[200]` (unsigned) | 800 | `NOCTIS-0.CPP:1029`, `TDPOLYGS.H:130` |
| `osscreen[2][148]` + `osscreen_textbuffer[148]` | 444 | `NOCTIS.CPP:395-398` |
| `digimap[325]`, `range8088[192]`, `goesnet_command[120]`, `pp[32]`, labels, `mp[24]`, star/planet tables | ≈1,700 | various |
| **static total** | **≈22,000** | |

**Grand total ≈ 358,500 bytes.**

### 8.2 Bytes at one byte per 32-bit unit

| item | units | bytes of workspace |
|---|---|---|
| heap buffers as-is | 336,480 | 1,345,920 |
| `n_globes_map` padded to a 64 KiB `txtr` window | +32,768 | +131,072 |
| `p_surfacemap` padded to 67,600 above + 8 below | +27,608 | +110,432 |
| `s_background` padded to 65,552 | +752 | +3,008 |
| static buffers | ≈22,000 | ≈88,000 |
| index page `adapted` — already counted (65,540) | — | — |
| 320×200 `00RRGGBB` display buffer | 64,000 | 256,000 |
| 256-entry expanded palette | 256 | 1,024 |
| **total** | **≈483,900** | **≈1,935,600 (1.85 MiB)** |

Against the **measured 1 GB workspace ceiling** (≈268 M units): **0.18%**. Padding
every buffer to a full 64 KiB `txtr` window and giving `adapted` its complete 64 KiB
segment costs nothing we can measure.

The alternative — packing 4 Noctis bytes per unit, 84,120 units, 336 KB — saves
1.5 MB and buys a shift+mask on **every** access in `fragment`/`hpoint`, which the
source itself says run 160,000 times per frame (`NOCTIS-1.CPP:17-26`). Not worth it.

### 8.3 The layout the aliases force

The alias set makes "one lino array per Noctis buffer" unimplementable:

* `txtr` must be expressible as an integer base offset that can be re-pointed at four
  different buffers and slid by arbitrary byte amounts (§2.5).
* `p_background` must be re-pointable at `s_background` at runtime (§2.3).
* `digimap2` sits *inside* `n_globes_map` at a 2-mod-4 offset (§2.1).
* `polymap` reads a 64 KiB window from any of them and must not fault (§3).

**One contiguous byte-per-unit workspace with named integer base offsets** satisfies
all four with no special cases: `txtr` becomes an `int` offset, the `p_background`
swap becomes an offset assignment, and the 64 KiB window is guaranteed readable as
long as the buffers are laid out with the padding in §8.2 (or simply placed so that
64 KiB of *some* workspace always follows each `txtr` base). Guard bands then cost
address space, not code.

---

## 9. Open items for the rest of Wave 5

1. **`farmalloc` offset = 4** (§4.1) is inferred from the `Stick`/`Segmento` split,
   not measured. Decisive experiment: DOSBox-X + `NOCTIS.SYM`, read the offset word of
   `adapted` after `init_FP_segments`. Cheap; do it before Wave 6 draws anything.
2. **`adapted[63996..63997]`** carry `polymap`'s `tinta`/`escrescenze` scratch under
   the offset-4 reading. That is a visible, falsifiable prediction — check it in the
   same DOSBox-X session.
3. **Clamp vs. faithful scribble** for `Segmento`/`Stick`'s `riga[]` overrun (§4.5).
   Recommendation: faithful, 65,540-unit page.
4. **`pvfile` re-layout** (§6.1) changes the arena's internal byte offsets. Confirm by
   inspection that nothing outside `loadpv`/`unloadpv` reads `pvfile` as raw bytes —
   this map found no such site, but the claim should be re-grepped when the arena is
   written.
5. **`niv-lr` divergences already identified** — record these so they are never used
   as a reference oracle: `p_surfacemap` inflated to 105,536 (`noctis.cpp:2605`);
   `digit_at` loop truncated to `n = 1` (`noctis.cpp:645`), dropping a scanline;
   `sc_bytes` set to 640×480 (`noctis-d.h:47`); `Stick` clamped
   (`noctis-0.cpp:1296-1297`); the `+4` normalised away (`tdpolygs.h:953, 1014`);
   frame time rounded to 55 ms (`noctis-d.h:174`); `n_globes_map` and `s_background`
   left unpadded and still reading out of bounds.
