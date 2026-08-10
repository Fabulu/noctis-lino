# LINOBUF -- the buffer model, the alias register, and the Wave 5 shell

**Wave 5 architect's decision document. Normative for the whole port.**
Written 2026-08-05 from recons A (aliasing/overruns), B (display path) and C
(tick/visual oracle), plus this document's own keystone probe
(`work/probe_w5arch.txt` → `work/probew5arch.bin`, built and run; PRISTINE 6/6
before and after).

Every number quoted below was produced on this machine. Where a recon's number
and mine disagree, both are shown and the disagreement is explained rather than
averaged.

---

## 0. The decisions, in one page

| # | Decision |
|---|---|
| 1 | **One Noctis byte per 32-bit lino unit**, everywhere in working memory. Packing survives only at the disk boundary. |
| 2 | **One flat workspace `NW` of 402,196 units, laid out in `farmalloc` order**, with named integer base offsets. Not one lino array per Noctis buffer -- that is unimplementable. |
| 3 | **Overruns are classified three ways, not policed one way.** Read-back overruns are made faithful *by the layout order, at zero cost*; write-only overruns get a dead pad; wrap-contained writes get the full 64 KiB segment. |
| 4 | **Aliases: keep all but two.** Split `digimap2` (proven safe) and re-lay the `pvfile` arena (unimplementable otherwise). Everything else stays aliased, because the game depends on it or because keeping it is free. |
| 5 | **Cooperative 320×200, permanently.** Exclusive mode buys nothing measurable and rearranges the user's desktop. |
| 6 | **Accumulated deadline with skip-to-grid**, exact rational period, signed-difference wait predicate, 16 ms sleep margin, counts-per-ms **calibrated, not reported**. |

**Measured budget for the whole shell**, working set fully resident:

```
full Noctis-shaped frame   1.47 ms p50 back-to-back   =  2.7% of a 54.9254 ms tick
                           2.05 ms p50 paced          =  3.7%
palette expand alone       0.054 ms                   =  0.099%
whole port's working set   ~494,000 units ~1.98 MB    =  0.18% of the 1 GB ceiling
```

---

## 1. Decision 1 -- one item per unit

**Decided: one Noctis byte per 32-bit lino unit, values 0..255 in the low bits,
no packing anywhere in working memory.** This overturns nothing -- PORTPLAN and
WAVEPLAN §3 both recommended it -- but the recons justified it on grounds that
are *true but not decisive*, and it is worth recording the argument that
actually is, because a later wave will be tempted to re-open this.

**The two arguments already on record, and why neither settles it.**

*Memory.* 1.98 MB against a measured 1 GB ceiling, 0.18%. True, but "packing
would also fit" is equally true -- packing costs 500 KB. Memory does not choose.

*Speed.* Recon B measured both (`work/probe_w5b_pack.txt`) and found **packing
is not slower -- it is faster on two of five patterns**: expand ×0.51, clear
×0.18, sequential get ×1.06, sequential put ×1.26, scattered put ×1.23. The
entire spread is under 0.1 ms against a 54.9 ms tick. Speed does not choose
either, and it mildly favours packing. Recon B was right to say so.

**The argument that decides it is `txtr`.**

`txtr` is not a buffer, it is a roving byte pointer (recon A §2.5). It is
re-based onto four different allocations and slid by runtime byte amounts --
`txtr += 48` (`NOCTIS-1.CPP:274`), `txtr += (x << 3)` (`NOCTIS-1.CPP:1273`),
base `p_surfacemap + 2064` (`NOCTIS.CPP:1010`). The texture unit then reads it
with a texel index built in the 16-bit `BX`:

```
texel = ((V>>8) & 0xFF) * 256 + ((U>>8) & 0xFF)          TDPOLYGS.H:2817-2821
```

Under **one byte per unit, a byte offset *is* a unit offset.** Every one of
those expressions -- and every `&n_globes_map[gl_bytes]`, every
`p_surfacemap[200*z + x]`, every `riga[c] = 320*c` -- transfers from the C source
**verbatim, with no arithmetic change at all**. That is the property that makes
a 20,000-line port reviewable: a reviewer can put the C and the lino side by
side and compare index expressions character by character.

Under **packing**, every byte offset needs an address `>>2` *and* a phase `&3`,
and because `txtr` slides by runtime amounts **the phase is dynamic**. The
texture fetch stops being "a shift and a mask" and becomes a variable-count
shift whose count must be carried as a second piece of state alongside every
pointer, re-derived by hand at every one of the several hundred indexing sites,
in the subsystem we have the *least* ability to test. Recon A measured the
fetch frequency from the source's own comment: `fragment`/`hpoint` run
**160,000 times per frame** (`NOCTIS-1.CPP:17-26`).

**And the corollary that seals it.** The original's out-of-bounds writes were
harmless *because neighbouring bytes were harmless*. Under packing, every
tolerated overrun corrupts **three innocent neighbours inside the same unit**.
That converts the whole overrun strategy from "reproduce it" (Decision 3, which
costs 1,556 units and no code) into "prevent it" -- a larger job, less
verifiable, and one that changes behaviour.

> **Packing does not cost memory and does not cost cycles. It costs correctness
> in exactly the subsystem where correctness is hardest to verify.** That is the
> reason, and it is the only one that holds.

**The one exception: the disk boundary.** Files stay byte-packed on disk. A
single pack/unpack helper pair converts at every read and write, and no other
code ever touches packed data. Two sub-cases that must *not* go through the
bulk helper:

* **`freeze`/`unfreeze`** (`NOCTIS.CPP:453`, `NOCTIS-0.CPP:739-820`) writes 245
  raw bytes starting at `&sync` -- 40+ consecutive globals of mixed `char`/`int`/
  `float`/`double`/`char[11]` with **no alignment padding**, 8-byte doubles at
  byte offsets 71, 79, 87… **Build this record field by field.** It cannot come
  out of a struct and it cannot come out of a bulk pack.
* **`loadpv`'s single packed `_read`** of `50*npolygs` bytes
  (`NOCTIS-0.CPP:2350`) becomes a per-field scatter. See §4, alias 9.

**Byte semantics, verified.** `work/probe_w5arch.txt` K6 (`bchk = 0`, all four
cases): store-and-mask reproduces byte wraparound (300 → 44, −1 → 255) and 8→32
sign extension is a mask-test-subtract (0xC0 → −64, 0x3F → +63). Sign extension
is **required**, not decorative: `n_globes_map` is declared `char` (signed) at
`NOCTIS-0.CPP:1004` and is right-shifted at `NOCTIS-1.CPP:4241, 4364`, and
`GLOBES.MAP` (y,x) pairs sign-extend 8→16 (PORTPLAN corrections table).

---

## 2. Decision 2 -- one flat workspace in `farmalloc` order

**Decided: a single contiguous workspace vector `NW` of 402,196 units, with
every buffer at a named constant base offset, laid out in exactly the order
`main()` calls `farmalloc`.**

### 2.1 Why flat, and not one array per buffer

Recon A §8.3 established that "one lino array per Noctis buffer" is
unimplementable, and it is right for four independent reasons. Flat with base
offsets dissolves all four:

| constraint | under flat + offsets |
|---|---|
| `txtr` re-based onto four buffers and slid by arbitrary bytes | `txtr` is an `int` variable holding a unit offset. Assignment and `+=` are literal. |
| `p_background` *becomes* `s_background` at runtime (`NOCTIS-0.CPP:5326`) | one offset assignment |
| `digimap2` sits inside `n_globes_map` at a 2-mod-4 byte offset | addressable -- though it is split anyway, §4 alias 2 |
| `polymap` reads a 64 KiB window from any base and must not fault | guaranteed by the layout, §3 |

Do **not** rely on the compiler placing separately-declared `"workspace"`
vectors adjacently. `NW` is one declaration and every base is a constant
computed at design time. That removes a dependency on undocumented layout
behaviour entirely.

### 2.2 The order is `farmalloc` order, and that is the whole trick

`NOCTIS.CPP:2163-2172` allocates in a fixed sequence. Reproducing that sequence
in the flat workspace makes **every read-past-the-end land on the same
neighbouring buffer DOS gave it**, for zero cost and zero code. This is
strictly more faithful than recon A §8.2's proposal of padding each `txtr` base
out to 64 KiB with zeros, and it is **61,128 units cheaper**.

Recon A's padding proposal is not wrong -- it is *safe* rather than *faithful*.
Where the two differ is exactly the interesting case: what does the sea texture
sample when its V accumulator exceeds row 127? Under zero-padding, zeros. Under
farmalloc order, the star/sky surface map -- which is what DOS gave it, because
`s_background` is the very next allocation.

### 2.3 The normative layout

Sizes are `NOCTIS-D.H:25-56`, unchanged. `PAD = 16` units between blocks stands
in for Borland's far-heap block header.

```
region          base      size    ends at    aliases and notes
--------------------------------------------------------------------------------
(low pad)          0        16         16    absorbs digit_at's txtr[-6..-1]
n_offsets_map     32     7,340      7,372    offsets.map; background() only
n_globes_map   7,388    32,768     40,156    globes.map | sea/horizon texture
s_background  40,172    64,800    104,972    star map | moon map | sky | shading
p_background 104,988    65,552    170,540    orbital 360x180 map; ground texture
p_surfacemap 170,556    40,000    210,556    altimetry | STARMAP buffer | cockpit
objectschart 210,572    40,000    250,572    == ruinschart == atmosphere == overlay
pvfile       250,588    20,480    271,068    polygon arena, 16 handles
adapted      271,084    65,540    336,624    the hidden page (full segment + 4)
adaptor      336,640    65,540    402,180    the visible page (DOS: VGA A000:0)
--------------------------------------------------------------------------------
NW top                            402,196    = 1,608,784 bytes
```

`adaptor` has no `farmalloc` in DOS -- it is the literal far pointer `0xA0000000`
(`NOCTIS-0.CPP:53`). It is placed last, sized a full segment because
`mask_pixels` wraps a 16-bit `DI` past 65,535 back through 0
(`NOCTIS-0.CPP:691-710`), and nothing overruns *into* it.

**Verified by the keystone probe, not asserted:**

```
K1  402,196-unit workspace + 64,000-unit display allocate and run
    nw[0] = 0x12345678, nw[top-1] = 0x9ABCDEF0 read back exactly
K2  OR of 403 units sampled at stride 997 across all nine regions
    and all nine pads = 0   -> "workspace" really is zero at launch,
    so guard bands and canaries cost no initialisation code
K3  every one of the five txtr bases has a full 65,536-unit readable
    window inside NW with NO per-buffer padding:
      p_background       base 104,988   headroom +231,672
      s_background       base  40,172   headroom +296,488
      n_globes_map       base   7,388   headroom +329,272
      p_surfacemap       base 170,556   headroom +166,104
      p_surfacemap+2064  base 172,620   headroom +164,040
    txchk = 0: every window fits and every window's top unit is live
K7  the 16-bit texel address swept over 5 bases x 65,536 (U,V) pairs,
    including a +48 slide and a +(37<<3) slide: min offset 7,388,
    max 238,499, never outside NW, never below its own base
```

### 2.4 Where each read-overrun lands, by construction

| overrun | source | lands on (DOS) | lands on (ours) |
|---|---|---|---|
| sea texture texel 32,768..65,535 | `TDPOLYGS.H:2821`, base `n_globes_map` | `s_background` | pad, then `s_background` ✓ |
| cockpit texture texel → +65,535 | base `p_surfacemap+2064` | `objectschart` | `objectschart` ✓ |
| `globe` tapestry +718 | `NOCTIS-0.CPP:3092-3140` on swapped `s_background` | `p_background` | `p_background` ✓ |
| `ssmooth` `es:[di+360]` +39 | `NOCTIS-0.CPP:4419-4427` | `p_background` | `p_background` ✓ |
| `hpoint` `p_surfacemap[cpos+201]` | `NOCTIS-1.CPP:77` | `objectschart` | `objectschart` ✓ |
| `fragment` `p_surfacemap[h1-1]` | `NOCTIS-1.CPP:1127` | previous block | pad ✓ |

The 16-unit pad is the one place we knowingly differ: DOS put far-heap metadata
there, we put zeros (or poison, in debug builds). **No read-overrun in recon A's
audit is proven to sample the pad**, and every write-overrun into it is
write-only. Recorded as a divergence rather than hidden.

---

## 3. Decision 3 -- the overrun strategy, three ways

The brief asks "guard bands, bounds checks, or fixing the writes". The honest
answer is that these are three answers to three *different* questions, and
applying one policy uniformly is what produced `niv-lr`'s two known bugs.

**Bounds checks are rejected outright.** `fragment`/`hpoint` run 160,000 times
per frame; a check there is 160,000 branches per frame. Worse, it is
*semantically* wrong: these overruns are behaviour to reproduce, not bugs to
trap.

**"Fixing the writes" is rejected, and we have the receipts.** `niv-lr` fixed
`digit_at` by starting its loop at `n = 1` after Valgrind complained
(`noctis.cpp:643-646`, comment: *"I just blindly changed this loop to start at
one. It probably breaks things..."*). It does: it silently drops the top
scanline of every cockpit glyph. `niv-lr` also clamped `Stick`
(`noctis-0.cpp:1296`, *"TODO; Figure out why this is over-running"*). Both are
divergences we must not inherit.

### The classification

| class | sites | treatment | cost |
|---|---|---|---|
| **A -- write, contained by 16-bit wrap inside the buffer's own segment** | `Segmento`/`Stick` `riga[]` scatter (`TDPOLYGS.H:245-259`); `mask_pixels` `DI` wrap; `cirrus` `bx = (py+px)>>1` wrap into `objectschart[0..32767]`; `spot` `di` wrap; `NOCTIS-0.CPP:5069, 6423` unsigned counter wraps | allocate the **full segment**: `adapted` and `adaptor` at 65,540; `p_background` already 65,552 ≥ 65,536; `objectschart` 40,000 > 32,768 | **1,540 units**, no code |
| **B -- write, outside the buffer, never read back** | `digit_at` `txtr[-6..-1]` (`NOCTIS.CPP:615-619`); `loadpv`'s `3*npolygs` past `pvfile_c` (`NOCTIS-0.CPP:2383-2391`) | **dead pad**: 16 units below `p_surfacemap`; `loadpv` fixed by the arena re-layout (§4 alias 9) | **16 units**, no code |
| **C -- read, outside the buffer** | `polymap`'s 64 KiB window from any `txtr` base; `ssmooth` +39; `globe` tapestry +718; `hpoint` +201; `fragment` −1 | **farmalloc-order layout** (§2.2) -- the read lands on the neighbour DOS gave it | **0 units, 0 code** |

`sc_bytes = 65540` is class A and is kept **faithful, not clamped**. Recon A
§4.5 recommends this and I concur: `NOCTIS-D.H:50-54` calls the function
*"difettosa … che non ho né tempo né voglia di modificare"* and sized the page
at a full segment plus 4 precisely so it could scribble. 1,540 units to
reproduce the author's own workaround exactly.

### Canaries -- a debug-build tool, not a release mechanism

**SUPERSEDED IN TWO WAYS by BUFFERMODEL §4.1 and §4.2.** The paragraph below is
kept because the *release/debug* distinction it draws is still right; the two
corrections are that there are **eleven** pads and not nine, and that a pad is
not one magic.

Each 16-unit pad is split into two ZONES. **Debug build**: `TAIL` (the low 8
units) is filled with `0xA5A5A5A5` and `SUB` (the high 8) with `0x5A5A5A5A`,
every zone carries an explicit allowance list, and all 22 zones over all 11 pads
are verified; a change to a guarded unit halts loudly and names the pad, while a
change to an allowance unit is COUNTED. **Release build**: pads are zero (the
faithful state) and the check is compiled out.

They are *not* the same build, and that matters: the debug build's poison
changes what a class-C read-overrun samples. Grading runs use the release build.

**Two corrections to the text this replaces.**

1. *"all 16 units of all nine pads"* left `nw[0..31]` -- the two pads below
   `n_offsets_map` -- guarded by nothing, because nine is `rtab`'s region count
   and a workspace has eleven pads. The pad list is now written out
   independently of `rtab`. Measured: corrupting `nw[3]` and `nw[20]` after
   poisoning reports `fired = 1, n = 2, at = 3`; the `rtab`-derived walker
   reports `0, 0, 0`.
2. One magic per pad made the guard band and the legitimate-write destination
   the same thing, so `digit_at`'s `txtr[-6..-1]` (`NOCTIS.CPP:614-628`, landing
   in `nw[170,550..170,555]`) fired the canary and halted -- the first cockpit
   glyph of a debug build was indistinguishable from a buffer overrun.

**Verified, including both negatives:**

```
    all zones poisoned, check run clean : fired = 0, n = 0, exp = 0
    digit_at txtr[-6..-1]               : fired = 0, n = 0, exp = 6   COUNTED
    loadpv one unit past pvfile         : fired = 0, n = 0, exp = 1   COUNTED
    one unit FURTHER (pad 8, TAIL+1)    : fired = 9, n = 1, at = 271,069
    nw[3] and nw[20] after poisoning    : fired = 1, n = 2, at = 3
```

A canary that always fires cannot pass this, because the clean check runs first
and must report zero. A canary that *never* fires cannot pass it either, which
FBDUMP kind 6 v1 could not establish -- see §6.1.

---

## 4. Decision 4 -- the alias register

For each alias: **keep** (an explicit shared region) or **split**. Splitting is
safer and now affordable, so the burden is on *keeping* -- except where the game
depends on the aliasing, where the burden reverses.

| # | alias | verdict | reason |
|---|---|---|---|
| 1 | `n_globes_map` ⟷ sea/horizon texture (`txtr`) | **KEEP** | Sequential reuse, never simultaneous. `globe()` is called only from `NOCTIS.CPP:2588, 2592` and `NOCTIS-0.CPP:5564, 5592` -- **none inside `planetary_main()`** (verified by grep over lines 3313-5045). The sea gradient destroys `globes.map` and nothing reads it until `load_QVRmaps()` at `NOCTIS-1.CPP:5039`. Keeping preserves the class-C neighbour relation for free. |
| 2 | `n_globes_map` ⟷ `digimap2` (+22,586, **2 mod 4**) | **SPLIT** -- 2,340 units, one `uint32` per unit | The only misalignment in the project, and **provably safe to split**: `digimap2` has exactly one reader, `NOCTIS.CPP:621` inside `digit_at`, and `digit_at`'s callers are all in `screen()`, `vehicle()` and `main()` -- **none reachable from `planetary_main()`**, which uses only `wrouthud` (a *static* `digimap[325]`, not `digimap2`). So the font is destroyed by the sea fill and **never read while destroyed**. `load_digimap2()` at `:5041` is pure restoration, not a behaviour dependency. Splitting costs nothing and removes a 2-mod-4 dword-assemble from every glyph row. |
| 3 | `objectschart` ⟷ `ruinschart` | **KEEP -- mandatory** | Same *byte*, different bitfields. `AF1/AF2/AF3` = 0x40/0x80/0xC0 write the `object2_class` field, and `ruinschart[h1]` (`NOCTIS-1.CPP:1177`) and `objectschart[h1].nr_of_objects` (`:1324`) use the **same index**. The ruins writer clobbering an object slot is observable behaviour. Splitting changes the game. |
| 4 | `objectschart` ⟷ `atmosphere` / `overlay` | **KEEP** | Sequential reuse with different resolutions -- orbital `[ptr>>1]` over 0..32,399, landed `[ptr]` over 0..39,999. The transition is explicit (`_fmemset(objectschart,0,oc_bytes)`, `NOCTIS-1.CPP:1970`). Free to keep. **Trap:** `create_sky(char atmosphere)` (`NOCTIS-1.CPP:2736`) has a *parameter* of the same name that is a boolean. Do not conflate. |
| 5 | `p_background` ⟷ `s_background` **runtime swap** | **KEEP -- nothing to split** | `NOCTIS-0.CPP:5326`/`:5331`, restored `:5605`. `p_background` must be a **variable** base offset, not a constant. Keep both at their natural sizes (64,800 vs 65,552) in farmalloc order -- the size difference *is* what creates `s_background`'s three class-C overruns, and the layout catches all three in `p_background`. |
| 6 | `p_surfacemap` ⟷ `txtr` at +0 and +2,064 | **KEEP** | Free under one-per-unit: an offset variable. |
| 7 | `p_surfacemap` `char` ⟷ `double` (STARMAP) | **KEEP storage, SPLIT the view** | 32-byte records, `double` at record offset 0, type byte at 29 (`NOCTIS-0.CPP:4020-4030`, `:5768-5790`). Byte array + an assemble-double-from-8-units helper. The soft-float double is two units anyway (FLOATPOLICY), so this is a helper, not a buffer. |
| 8 | `adapted` ⟷ `tinta`/`escrescenze` scratch | **KEEP, faithfully at 63,996..63,997** | Under recon A §4.1's `offset == 4` reading these are **visible pixels**, row 199 cols 316-317. `niv-lr` relocated them to 64,000 (`tdpolygs.h:938`). Ours stays at 63,996 and the test must **reject** the LR variant. Conditional on the open item in §9. |
| 9 | `pvfile` sub-arrays at unaligned byte offsets | **RE-LAY-OUT** | `pvfile_x[h] = (float far *)(pvfile + datatop)` where `datatop` has advanced by `1*npolygs` -- a `float` array at a non-multiple-of-4 byte offset whenever `npolygs % 4 != 0`. Unit addressing cannot express this. Re-lay so every sub-array is unit-aligned; replace the one packed `_read` with a per-field scatter; `unloadpv`'s `_fmemmove` compaction moves in sub-array units. **Observationally equivalent** -- nothing outside `loadpv`/`unloadpv` reads `pvfile` as raw bytes (recon A checked; **re-grep at implementation time**). Also fixes class-B overrun 2 for free. |

**Two behaviour dependencies found, one per direction.** Alias 3 is a genuine
dependency and must be kept. Aliases 1 and 2 look like dependencies (the game
reloads all three maps on leaving a planet) and are **not** -- the reload is
restoration, and I checked the reachability rather than assuming it. That check
is the load-bearing new fact in this section; it is what makes the `digimap2`
split safe.

### `QUADWORDS` is a variable, not a constant

`int QUADWORDS = 16000` (`NOCTIS-0.CPP:51`) is the dword count for `pcopy`,
`pclear`, `pfade`, `psmooth_*`, `ssmooth`, `lssmooth`, `mask_pixels`, and it is
**changed at runtime**. Eight distinct values (recon A §5); it steady-states at
**14,560 (58,240 bytes = 182 rows)** after `NOCTIS.CPP:2206`, not 16,000. Any
page operation that hard-codes 64,000 gets the HUD visor animation and surface
generation wrong. Make it a variable and pass it.

---

## 5. Decision 5 -- framebuffer, palette, present and tick

### 5.1 Mode: cooperative 320×200, permanently

Recon B ran exclusive mode and it **succeeded** -- and left a maximized Chrome
window squashed to 221×109 which Windows did not restore. Against that: zero
measured per-frame advantage, 508 ms to enter, 768 ms to leave, and RETRACE is
not vsync-locked in exclusive either.

**PORTPLAN's "exclusive 320×200 -- real mode switch, closest thing to mode 13h"
is hereby superseded.** It is a real mode switch; it is not an advantage.

Present 1:1 at 320×200, not upscaled to 640×400. The index buffer is 320×200
exactly, which is what both visual oracles deliver; 2× costs 1.0-2.5 ms against
0.56; and upscaling changes nothing upstream, so it is a Wave 9 polish item.

**`[Display Physical Height]` reports 672 on this 720-line desktop** -- it
excludes the taskbar. Never size anything from it assuming it equals the screen.
Confirmed again by the keystone probe (`1280 x 672`, `[Display Status] = 2`).

### 5.2 Buffers

```
NW           402,196 units   the Noctis workspace (§2.3)
  adapted     65,540         hidden page, INDEX values 0..255
  adaptor     65,540         visible page, INDEX values 0..255
fb            64,000 units   [Display Origin], 00RRGGBB           <- outside NW
pal              256 units   the expanded LUT
pal6             768 units   tmppal: 256 colours x RGB, 0..63
curpal6          768 units   the *uploaded* palette
retpal6          768 units   return_palette  (fade source)
srfpal6          768 units   surface_palette (fade source)
range8088        192 units   the fixed 64-entry greyscale ramp
digimap2       2,340 units   32x36 pilot font, one uint32 per unit  (split, §4)
statics       ~22,000 units  nearstar_*, ani_*/tgt_*, lft_sin/cos, riga, m200, ...
--------------------------------------------------------------------------------
total         ~494,000 units  ~1.98 MB  =  0.18% of the measured 1 GB ceiling
```

**Both pages are real.** `adaptor` is VGA memory in DOS; here it is an index
buffer, and `pcopy(adaptor, adapted)` stays an index→index copy. Do **not**
optimise it away by expanding `adapted` directly: `pclear(adaptor,0)`
(`NOCTIS-1.CPP:5021`), `areaclear`, and vanilla's type-9 substellar case all
write the *visible page* rather than the surface buffer. That last one is a
confirmed `niv-lr` divergence (PORTPLAN's oracle-trust table) and the one thing
DOSBox's raw capture can see that the game's own BMP cannot.

### 5.3 The palette

**Structure.** `pal6` is the master (Noctis's `tmppal`); `curpal6` is what has
been "uploaded"; `pal` is the 256-entry `00RRGGBB` LUT rebuilt from `curpal6`.
The port needs both `pal6` and `curpal6` -- `niv-lr` calls the second `currpal`.
`retpal6`/`srfpal6` are fade sources so fades do not compound.

**Bands**, from the author's comment at `NOCTIS.CPP:2218`:

| range | contents | changes |
|---|---|---|
| 0-63 | vehicle, computer selections, artefacts | every frame, starlight tint |
| 64-127 | cosmos, galactic background, clear skies | every frame, sky tint |
| 128-191 | stars, or moons | on arrival, in `surface()` |
| 192-255 | planets | on arrival, in `surface()` |

**`tavola_colori(src, first, n, fr, fg, fb)` -- three steps, and the third is a
trap.** Copy `n*3` from `src` into `pal6[first*3…]`; filter in place
(`v = v*f/63`, clamped to 63, integer throughout); then **upload starting at
colour 0** and running to `(first+n)*3`. The upload always starts at zero.
Consequence the port must keep: an update to band 64-127 uploads colours 0-127
and **leaves 128-255 stale** until something covers them.

**Four traps, all from recon B §3, all under test (§7):**

1. **`tavola_colori(tmppal + 3*k, k, n, …)` is a self-copy** -- source aliases
   destination. `NOCTIS.CPP:3777` (sky, every frame) and `NOCTIS-0.CPP:5193`
   (planet band). With separate buffers this must become "filter in place";
   copying from a stale buffer instead silently changes the sky.
2. **`filtro_*` is a signed `char`.** `NOCTIS-1.CPP:3934` passes
   `random(64)+64` = 64..127, which fits. Above 127 it goes negative and the
   `> 63` clamp does not catch it. **Assert the range; do not trust it.**
3. **`shade()` truncates.** lino's `=,` rounds to nearest. Use the Wave 3 float
   engine's existing `__ftol`-chop helper -- do not rebuild it -- then the
   original's inverted clamp (`>= 0 && < 64`, else 63 if `> 0` else 0).
4. **Six bits to eight is a choice. Decided: `v * 4` (63 → 252).** Not because
   `niv-lr` does it, but because **the game's own `snapshot()` writer scales the
   DAC by ×4** -- so our index→RGB mapping is *identical* to the palette in the
   BMPs that are oracle route 1, making palette comparison exact rather than
   off-by-one. DOSBox writes `(v<<2)|(v>>4)` instead; `PLTE>>2` recovers the
   6-bit DAC on both sides (recon C: 154/256 identical, every difference +1).
   **Made once, in one place: the LUT rebuild.**

**Cost -- it is a non-issue and must not be optimised.** Recon B measured a full
256-entry LUT rebuild at **0.0004 ms**; the 64-colour `tavola_colori` filter at
0.0009 ms; the whole 16-step fade ladder at 0.06 ms. Four orders of magnitude
below the tick. Do not band the rebuild, do not cache it.

### 5.4 The present path

```
Present:  expand adaptor -> fb through pal, unrolled x4
          [Display Command] = RETRACE; isocall
```

Unroll ×4: 12% for free and safe. **Do not pre-bias the index buffer** to hold
`pal+index` -- recon B measured it at 0.0565 vs 0.0566 ms (exactly nothing, the
add hides in memory latency) and it would destroy the byte semantics the
background colour cycle depends on (a read-modify-write on the index).

**Fuse the background colour cycle into the expand:** 0.0961 ms fused versus
0.123 ms as two passes, worth 22%.

**Do not build dirty-rectangle tracking.** Recon B measured a 16×16 live region
against the whole display: 15%, 16%, 2% saved for 1/250th of the area. The
present is fixed cost, not per-pixel cost.

### 5.5 The tick

**Period, as exact integer arithmetic** (recon C; no 64-bit product, nothing
overflows -- largest intermediate `44505*cpms ≈ 4.0e8`):

```
period_counts = cpms*55 - (cpms*44505 + carry) / 596591
```
with the remainder carried in an accumulator across ticks. The naive
decomposition `cpms*552086` **overflows 32 bits**; this one does not.

**Five rules, each with its evidence:**

1. **Accumulate, never re-base.** Recon C measured re-base drifting only
   +0.00071 ms/tick, and corrects PORTPLAN's "+0.057 ms/tick" -- *that figure
   measures re-basing on a 55 ms period, not the discipline.* The real reason to
   accumulate is that **it recovers**: phase A's worst tick (55.1348 ms) was
   immediately followed by 54.7161 ms, cancelling to +0.000 ms total drift over
   210 ticks. Re-base keeps every hitch forever.

2. **Skip to the next grid point strictly in the future after a miss.** The
   original does not compute a deadline at all -- `sync_stop` busy-waits for the
   next *edge* of a free-running counter (`NOCTIS-0.CPP:6025-6038`). So an
   overrunning frame loses a whole tick and re-aligns, and the frame rate is
   18.2065/k and never anything between. Recon C measured the real game at
   **15-17 fps** with a mean of exactly 1.50 ticks under heavy capture -- the
   signature of a 50/50 mixture of 1- and 2-tick frames, which is what
   quantisation gives and a continuously-variable rate does not.
   **This is a fidelity requirement, not a timing one.** It is also mandatory in
   practice: my keystone probe saw a **36.88 ms** back-to-back frame (67% of a
   tick) from one RETRACE stall; recon B saw ~25 ms once per 600 presents in
   every run. Without skip-to-grid that becomes a double-speed catch-up frame.

3. **The wait predicate is the sign of the difference, never a timestamp
   compare.** `A = [Counts]; A - [deadline]; ? A < 0 -> wait;`. Recon C proved
   this over 3.1M constructed cases across the wrap and the 2^31 sign boundary,
   with zero failures -- and built the broken control, which collapses 22
   consecutive ticks to under 1 ms at the wrap. `[Counts]` wraps every ~477 s,
   so this is the eight-minute bug.

4. **Sleep to a 16 ms margin.** Recon C, measured from outside the process:
   6,984 ms CPU spin-only → 1,594 ms at margin 16 (**4.4× less**) with identical
   p50/p90/max. Margin 4 is unusable -- Windows `SLEEP` overshoots by more than
   4 ms, giving 17.6 ms peak-to-peak jitter and 60/120 ticks over +1 ms. Make it
   a constant with 0 = spin-only for benchmarking.

5. **Calibrate counts-per-millisecond; do not use the reported value.** Recon C
   found `[Counts Per Millisecond]` is a per-process estimate reporting 8984…
   9023 across seven launches (0.43% spread) while the true rate was stable to
   0.016%. In one launch the reported value carried a **+0.258% rate error** --
   +9 s per hour, and **accumulation cannot remove it, because it is not a
   rounding error.** My own run reported 9000.
   **Design:** seed from `[Counts Per Millisecond]`; bracket the asset-load
   phase (≥1 s of real work, no added wait) with `READ TIME` + `READ COUNTS` at
   both ends and recompute; then servo every 256 ticks (~14 s) against total
   counts / total ms since start, with the correction bounded to ±1% so one bad
   sample cannot wreck the tick, and no update if the interval is under 500 ms.
   `READ TIME`'s `[Milliseconds]` steps by 1 ms in 200 of 256 observations -- it
   is a usable reference.

### 5.6 Input, and a correction to PORTPLAN

**PORTPLAN's "Events are drained at the top of every isocall, so a frame that
makes no isocall stops responding" is refuted in both halves**, and the wave
plan should stop carrying it as a constraint.

Recon B ran 7.1 s of pure computation with zero isocalls: `Process.Responding`
true on all 66 samples, because the produced executable imports `CreateThread`
alongside a blocking `GetMessageA`/`DispatchMessageA` trio -- **the pump is on
its own thread.** And the application still *sees* the events: with a
`WM_KEYDOWN` posted straight to the probe's own window handle, the LUCK table
lit up after 11,977,387 isocall-free iterations, against a control that ran the
full 200,000,000 cap with LUCK still zero.

**Consequence: the frame loop isocalls because it wants to present, not because
it must pump.** Use the 98-unit LUCK table for held-key flight input and
`GET CONSOLE INPUT` for the ASCII FIFO (command letters, name entry). There is
still no window-close event; ESC-to-quit is the only exit.

### 5.7 Budget -- measured at the real working set

Recon B warned that its own expand read 0.057 ms in one probe and 0.130 ms in
another -- *the same loop at different resident working-set sizes* -- and that one
must "compare within a run, never across". The Wave 5 shell's working set is
1.98 MB, so I measured there. `work/probe_w5arch.txt` K4, whole workspace
touched before timing:

| battery | min | p50 | p90 | max |
|---|---|---|---|---|
| full frame, back-to-back (clear 65,540 + draw 64,000 + pcopy 64,000 + expand + RETRACE) | 1.196 | **1.472** | 2.095 | **36.880** |
| palette expand alone | 0.053 | **0.054** | 0.101 | 0.106 |
| full frame, paced at 54.9254 ms | 1.487 | **2.055** | 2.344 | 2.522 |

**The expand at the real working set is 0.054 ms** -- the palette probe's figure,
not the packing probe's. That settles recon B's caveat: budget 0.054, not 0.130.

**A Noctis-shaped frame is 2.7-3.7% of a tick with the whole workspace live.**
Consistent with recon C's independently measured 2.39 ms / 4.36%. The 1996
binary under DOSBox-X misses its tick 10-20% of the time; the port has ~27×
headroom. **The platform is not the constraint and will not become one.**

One finding worth carrying: **the paced battery's max was 2.52 ms while the
back-to-back battery's was 36.88 ms.** Pacing did not merely tolerate the
RETRACE stall over 100 frames -- it avoided it. Do not read back-to-back
benchmark numbers as the game's worst case; they are a different regime.

---

## 6. Decision 6 -- the file plan and the interchange format

Two disjoint namespaces, as the brief specifies. Neither implementer reads the
other's source; they meet only at the dump format below.

### Implementer 1 -- `work/fb*.txt` (lino)

lino has a `"libraries"` period that textually includes another `.txt` from the
program's own source directory (verified in `docs/librarie.htm`; `work/fbmem`
resolves to `work/fbmem.txt`). So this is real modularity, not concatenation.

| file | contents |
|---|---|
| `work/fbmem.txt` | the layout: every base and size as a named constant; `PAD`, poison and canary magic; poison/check routines; byte store/load with `AND 255`; 8→32 sign extension; `quadrant` bitfield get/set; assemble-`uint32` (digimap2) and assemble-`double` (STARMAP) helpers; the FBDUMP writer |
| `work/fbpal.txt` | `pal6`/`curpal6`/`retpal6`/`srfpal6`/`pal`/`range8088`; `tavola_colori` (copy, in-place filter, upload-from-zero); `shade` (chop + inverted clamp); LUT rebuild (`v*4`) |
| `work/fbtick.txt` | calibration + servo; the exact rational period with carry; accumulate + skip-to-grid; sleep-to-margin; the signed-difference predicate; the TICKLOG writer |
| `work/fbmain.txt` | the shell: opens the display, runs the tick loop, drains LUCK + console, presents, ESC-quits, dumps |
| `work/fbbreak1.txt` … `fbbreak10.txt` | the ten deliberately broken builds of §7, one single edit each |

### Implementer 2 -- `noctis-harness/fb_*.py`, `fb_*.c` (reference and grading)

| file | contents |
|---|---|
| `fb_layout.py` | computes every base and size **independently**, from `NOCTIS-D.H` parsed directly; asserts farmalloc order, non-overlap, ≥65,536 units above every `txtr` base, ≥8 below `p_surfacemap` |
| `fb_ref.c` | the C reference: same layout, same palette math, same present path, writing FBDUMP. **Written from `NOCTIS-0.CPP` and the assembly, never from implementer 1's lino.** |
| `fb_pal.py` | independent Python palette reference (unbounded ints) |
| `fb_tick.py` | independent exact-rational period; re-enumerates recon C's 3.1M wrap cases |
| `fb_bmp.py` | reads the game's 8bpp BMP **and** DOSBox's raw PNG; returns a 320×200 index plane + a 6-bit palette from both, on a common footing |
| `fb_compare.py` | the grader |

### The interchange format -- FBDUMP v1

lino cannot write bytes; it writes units. So everything is a stream of 32-bit
**little-endian** units, and the format is the same on all three sides.

```
header, 16 units
  0  magic     0x46424431 ('FBD1')
  1  version   1
  2  kind      1 INDEXPAGE | 2 PALETTE6 | 3 LUT | 4 TICKLOG | 5 LAYOUT | 6 CANARY
  3  width     kind 1 only, else 0
  4  height    kind 1 only, else 0
  5  count     number of payload units that follow
  6  cpms      the CALIBRATED counts-per-ms at write time
  7  ticks     tick number at write time
  8..15        reserved, 0
payload: `count` units
```

| kind | payload |
|---|---|
| 1 INDEXPAGE | 64,000 units, one index 0..255 per pixel, row-major from top-left. **The primary comparison object** -- exactly what the game's own BMP holds and what DOSBox's raw PNG holds after ÷2. |
| 2 PALETTE6 | 768 units, 0..63, R,G,B per colour. Directly comparable to the BMP palette ÷4 and the PNG `PLTE` ÷4. |
| 3 LUT | 256 units, `00RRGGBB` |
| 4 TICKLOG | 3 units per tick: absolute `[Counts]` at fire, the deadline it fired against, a flag word (bit 0 = skipped a grid point, bit 1 = slept). **Raw, so the grader recomputes periods, drift and skips itself** rather than trusting a lino-computed statistic. |
| 5 LAYOUT | 4 units per region: base, size, pad base, region id. How the two implementations compare layouts without either reading the other's source. |
| 6 CANARY | 2 units per region: expected, actual -- **withdrawn, see §6.1** |

Grading: exact unit-for-unit compare on kinds 1, 2, 3, 5, 6; recomputed
statistics on kind 4.

### 6.1 FBDUMP v2 -- what v1 got wrong, and the corrected record set

**Header unit 1 is now `2`, and header unit 8 carries a TAG.** Version 1
identified a record only by its `kind`, so two records of the same kind in one
stream -- `pal6` and `curpal6`, the hidden page and the visible page -- were told
apart by *position*, which is not an identity. The tag namespace is independent
of order and of kind.

**Kind 6 v1 was a check that could not fail, and this is the correction that
matters most.** It was two units per region, "expected" and "actual", and both
were `0xA5A5A5A5` -- *written by construction on both sides*. A clean run and a
build with the canary walker deleted produced a **bit-identical** record, so
"lino CANARY == the reference" passed for a build with no canary in it. The
grader compounded it by comparing `can[i]` against `can[i+1]`: two copies of one
literal.

**Kind 6 v2 is 4 units per PAD, eleven pads, 44 units, and stores no literal.**
Every unit is either read back out of the workspace or produced by the walker,
and the grader derives all four from the layout alone:

| unit | field | derived from |
|---|---|---|
| 0 | clean read of `nw[padbase(i)+slot(i)]` after poisoning | the zone role: `0xA5A5A5A5` in a `TAIL`, `0x5A5A5A5A` in a `SUB` |
| 1 | the same address re-read after storing `WITNESS(i)` | the witness rule |
| 2 | the pad index + 1 the walker reported | `i + 1` |
| 3 | the `nw` offset of the first violation | `padbase(i) + slot(i)` |

Four failure modes are separated: no poison (unit 0), a constant "actual"
(unit 1), a stubbed comparison (unit 2), the wrong address or the wrong pad set
(unit 3). Proved by breaking it -- stubbing `MEM check pads` moves 22 of the 44
units, where under v1 the same edit moved nothing. *Limit, stated:* a saboteur
who reads the witness rule can recompute unit 1 instead of loading it, so the
load-bearing fields are 0, 2 and 3.

**The record set, v2:**

| kind | tag | payload |
|---|---|---|
| 1 INDEXPAGE | 1 `adapted`, 2 `adaptor`, 3 glyph page | 64,000 units, row-major from top-left |
| 2 PALETTE6 | 4 `pal6`, 5 `curpal6`, 17 `srfpal6`, 18 `retpal6` | 768 units, 0..63 |
| 3 LUT | 6 | 256 units, `00RRGGBB` |
| 4 TICKLOG | 10 | 3 units per tick, RAW |
| 5 LAYOUT | 7 | 4 units per region: base, size, pad base, id |
| 6 CANARY | 8 | **4 units per PAD, 11 pads** -- see above |
| 7 SELF | 13 | the writer's own self-checks |
| 8 FRAMECOST | 14 | raw per-present counts |
| 9 ZONE | 9 | **new.** 4 units per zone, 22 zones: base, length, owner region id (−1 unowned), role (0 `TAIL`, 1 `SUB`). This is how the guard/allowance separation is compared without either side reading the other's source. |
| 10 WRAPCOUNT | 12 | **new.** 3 units per class-A site: site id, calls, wraps |
| 11 SERVOLOG | 11 | **new.** 3 units per servo firing: the first tick at which the value is in force, the cpms, the why-code (0 applied, 1 clamped low, 2 clamped high, 3 too short, 4 too long). **Rejections are logged too** -- a run of rejections is the signature of a suspend or a mis-set band, and a log carrying only successes could not show it. |
| 12 WRAPBATTERY | 15 | **new.** 6 units per synthetic class-A case |

`tests/w5probe.txt` adds its own kinds above this namespace -- 16 SELF, 17
ADVANCE, 19 FRAMEBUFFER, 20 FRAMECOST, 21 SKY, 22 SERVO HORIZON, 23 CLASS-A
MASK, 24 SERVO BAND -- because the probe is not the shell and must not be
mistaken for it.

**`cpms` in header unit 6 is no longer a stream-wide constant.** `SERVON` is a
driver constant now and a soak long enough to fire the servo changes cpms
mid-stream. A reader that converts a whole `TICKLOG` with one factor gets the
drift wrong; kind 11 says exactly when it changed and the grid must be rebuilt
piecewise. Measured: the single-cpms reconstruction misses 199 of 200 deadlines
on a run whose deadlines are every one of them exactly on the grid.

**Filename trap, hit twice already:** underscores in lino string literals become
spaces, so `{ fb_page.bin }` writes `fb page.bin`. Use hyphens or `\us` in every
output filename. Recon C reported four false failures from exactly this.

**Two symbol-collision traps** (recon B): spaces are ignored in symbols, so a
workspace symbol `keys` collides with the LUCK entry `key s`, and a subroutine
`"Luck or"` collides with a variable `luckor`. Both fail as
`declaration error: symbol already declared` with no hint which pair collided.

---

## 7. Decision 7 -- the proof, and what is scoped out

Rendering is visual, which is why this section is longer than it would like to
be. The rule is unchanged: **nothing is graded against a stored artifact this
project produced, and every test builds a broken subject and requires the
catch.**

### Tier 1 -- exact, against artifacts this project did not make

Recon C established that **both** capture routes deliver *indices*, not RGB --
the game's own `snapshot()` (`NOCTIS-0.CPP:6292`, key `b`) writes an 8bpp
palette-indexed BMP straight out of `adapted`, and DOSBox-X's raw screenshot is
a palette-indexed PNG that is exactly 2×2 pixel-and-line doubled, so ÷2 recovers
the 320×200 index plane. **Frame grading is therefore byte-exact index compare,
not tolerance compare.**

**What Wave 5 can actually put on this tier: the palette, and only the
palette.** Wave 5 has no renderer, so it cannot produce a frame to compare. But
it *can* compare all 768 six-bit DAC components against both routes at a pinned
state, and that grades the entire palette pipeline -- `tavola_colori`, `shade`,
the band structure, the upload-from-zero rule, and the ×4 choice -- against the
1996 binary, with no renderer at all. Recon C already measured the two routes
agreeing on 154/256 entries with every difference explained by the ×4 vs
`(v<<2)|(v>>4)` scaling, so both are usable and `PLTE>>2` puts them on a common
footing.

Rig: `tests/gen/recon_w5c/hostshot4.ps1` (`PostMessage` `WM_COMMAND` 5213/5214
to DOSBox-X's real Win32 menu -- the hotkeys are unbound and six chords were
tested and failed) and `godos_w5c.ps1` (headless `-silent` + AUTOTYPE).
**State must be pinned** or it is a picture, not an oracle: recon C measured two
snapshots 2 s apart differing in 10 of 64,000 pixels.

### Tier 2 -- exact, two independent implementations

lino vs C, byte-exact on every FBDUMP kind; lino vs Python for the tick
arithmetic and the wrap predicate (Python has unbounded integers, so it is a
genuinely different construction). **Non-circular only because `fb_ref.c` is
written from `NOCTIS-0.CPP` and the assembly by a different agent than the lino,
and the reviewer checks the C against the original line by line** -- the same
construction Waves 1-4 used.

### Tier 3 -- properties that need no oracle

The **layout** is graded by construction: `fb_layout.py` derives every base from
`NOCTIS-D.H` and asserts farmalloc order, non-overlap, and the window/underflow
inequalities; the lino build dumps kind 5; the two must agree unit for unit.
Neither derives from the other. The **canary** and **tick soak** are likewise
self-graded from raw logs (drift ≤ 1 ms over 400 ticks -- recon C measured
0.0004 ms -- and zero back-to-back fires after a hitch).

### The ten sabotages -- each one edit, each must be caught

1. LUT rebuilt with `(v<<2)|(v>>4)` instead of `v*4` → palette compare against
   the game's BMP must fail.
2. `tavola_colori` uploading `[first, first+n)` instead of `[0, first+n)` →
   band-staleness test must fail.
3. `shade()` using `=,` round-to-nearest instead of chop → must fail.
4. Tick predicate replaced by the unsigned timestamp compare → must fail at the
   wrap. (Recon C already built this control; reuse it.)
5. `Advance` without skip-to-grid → "no back-to-back fire after a hitch" must
   fail.
6. `digit_at`'s loop started at `n = 1` -- **`niv-lr`'s actual bug** -- → glyph
   compare must fail. (WAVEPLAN demands exactly this construction for
   `lssmooth`; this is its Wave 5 instance.)
7. One-unit overrun per region → each region's canary must fire, and the clean
   check must first report zero. **Already demonstrated** (§3).
8. `tinta`/`escrescenze` relocated to 64,000 -- `niv-lr`'s divergence -- → the
   `adapted` page compare must fail.
9. Layout in declaration order instead of farmalloc order → `fb_layout.py`'s
   neighbour assertions must fail.
10. A packed-4-per-unit byte store → byte-semantics test must fail. *(This one
    exists to prove one-per-unit is actually in force, not merely claimed.)*

### Scoped OUT -- stated plainly, not pretended

* **Anything needing a renderer.** No polygons, no globes, no textures, no
  frame-versus-DOSBox compare. `txtr` is *modelled* (an offset variable plus the
  16-bit texel address, unit-tested in K7) but nothing is textured.
* **Whether the class-C read-overruns are ever exercised.** The layout makes
  them faithful *if* they happen. Recon A found them by static bounds analysis;
  **none is proven reachable with real data.** Honest status: "the layout
  preserves DOS adjacency for every read-overrun the audit found; whether any is
  sampled is unknown until Wave 6/7 renders a real frame."
* **`farmalloc` offset == 4.** Inferred from the `Stick`/`Segmento` split, not
  measured. Nothing Wave 5 draws depends on it -- but alias 8 and every
  `es:[di+4]` reading do, so see §9.
* **Sub-index precision.** Everything upstream is observable only through the
  index it quantises to. A frame compare grades the **rasteriser exactly** and
  the **projection only within ±1 px** -- which is the envelope WAVEPLAN's Wave 6
  already assumes.
* **"Looks right."** Nothing is eyeballed as a pass criterion. A human may look;
  the look is not evidence.
* **Long-session behaviour.** The longest soak on record is 22 s. Multi-hour
  behaviour belongs to Waves 8-9 and no earlier evidence de-risks it.

---

## 8. Corrections this document makes to PORTPLAN and WAVEPLAN

| claim | status |
|---|---|
| "clear + palette-expand + RETRACE at 320×200 = 0.799 ms" | **Not reproducible**, including from its own probe, whose stored output is self-contradictory (RETRACE alone 1.2735 ms vs expand+RETRACE 0.7988 ms -- a superset cheaper than its subset). Warm-up. Use 1.47 ms p50 for a full frame at the real working set. Run-to-run variance on this machine is ±100%; **quote ranges, never points.** |
| "unthrottled 785 fps" | re-measures at 931 fps -- and is a *worse* per-frame cost than the game will see, not a better one |
| "median tick 55.0000 ms" | the target is **54.9254 ms**; 55 is `niv-lr`'s rounding (`noctis-d.h:174`) |
| "re-basing costs +0.057 ms/tick" | **measures the 55 ms period, not the discipline.** Correctly-rounded re-base drifts +0.00071 ms/tick. Accumulate anyway -- because it *recovers*. |
| "exclusive 320×200 -- closest thing to mode 13h" | true and irrelevant. **Cooperative, permanently.** |
| "a frame that makes no isocall stops responding" | **refuted in both halves.** Pump is on its own thread; the comm area is live without isocalls. |
| "the entire working set is ~643 KB, ~2.5 MB at one byte per unit" | **1.98 MB**, of which `NW` is 1.61 MB. Heap total is 336,480 bytes; `NOCTIS-D.H:58`'s "334941" is stale by 1,539. |
| WAVEPLAN §3 "the 32,768-byte triple-purpose buffer → **three separate buffers**" | **overruled in part.** Split `digimap2` only; keep `globes.map` ⟷ sea texture as one region (§4 aliases 1-2). Splitting it discards the class-C neighbour relation for no gain. |
| `[Counts Per Millisecond]` | a per-process **guess**, 0.43% spread across launches, up to +0.26% rate error. **Calibrate.** |

---

## 9. Open items, ranked

1. **`farmalloc` offset == 4** (recon A §9.1). Inferred, not measured. Decisive
   experiment: DOSBox-X + `NOCTIS.SYM`, read the offset word of `adapted` after
   `init_FP_segments`. **Cheap, the rig exists (`hostshot4.ps1`), and it should
   run inside Wave 5 even though Wave 5 does not depend on it** -- because if it
   is not 4, alias 8 moves and every `es:[di+4]` reading in recon A shifts.
   Falsifiable prediction to check in the same session: `adapted[63996..63997]`
   carry `polymap`'s fill colour whenever `polymap` has run -- row 199, columns
   316-317.
2. **Re-grep `pvfile`** for any raw-byte reader outside `loadpv`/`unloadpv`
   before the arena is re-laid out (§4 alias 9). Recon A found none; confirm at
   implementation time, because the re-layout is only observationally equivalent
   if that holds.
3. **`n_globes_map` is `char` (signed)** and is right-shifted. Values are 0..63
   in practice so it does not bite -- but check the loaded `globes.map` bytes
   rather than silently switching to unsigned.
4. **Whether any class-C read-overrun is actually sampled.** Unknown until a
   real frame renders. First suspect if a Wave 6/7 texture band differs from
   DOSBox.
5. **27 dead `extern`s and three dead `TDPOLYGS.H` texture loaders** (recon A
   §7) -- `init_texture_mapping` is never called, so `txtr` is *only* ever an
   alias. Do not port them. `GFX.H`/`FAST3D.H`/`TEXT3D.H`/`PITAGORA.H` are not
   in the build set at all.

---

## 10. Wave 5c -- §7's rule, made executable

§7 states the rule this project works by: *nothing is graded against a stored
artifact this project produced, and every test builds a broken subject and
requires the catch.* The rule was stated in §7, restated in
`fb_ledger.py`'s docstring, and restated again in `fb_lint.py` -- and the wave
that wrote those three statements shipped two more checks that could not fail.

`tests/w5audit.py` executes it. It runs inside `tests/test_wave5.py`, costs
2.4 s, and fails the suite when a check that cannot fail is added anywhere in
`noctis-harness/fb_*.py`, `fbx_*.py` or `tests/`.

### 10.1 What it adds to the three evidence levels

The levels in §7 say what a *sound* comparison looks like. The audit says what
an *unsound* one looks like, mechanically, and the two are now cross-checked:

* **The level named in a check id is a claim, and it is recomputed.** A cid
  beginning `T2` claims the second level -- "exact, two independent
  implementations" -- so its two `fb_ledger` sides must carry two **distinct**
  owners, neither of them `external`. A parsed 1996 source, a DOSBox capture or
  an exact rational is evidence, but it is not a second implementation. Eight
  rows currently fail that recomputation and are pinned with a budget that may
  fall and may not rise; they are listed in `HARNESSAUDIT.md` §8.5.
* **`fb_compare.TIER_TABLE` is graded the same way.** Four elements claim the
  two-implementation level while every supporting row has one producer, and
  they are listed in `HARNESSAUDIT.md` §8.6.
* **The prose in this file is pinned.** The three headings below in §7 are
  registered in `w5audit.TIER_CLAIMS` together with the ledger rows that
  support them. If a heading's text drifts, or the rows behind it stop
  supporting the level it names, the suite fails -- and any *new* line in this
  file that names a level and is not registered also fails the suite. That last
  gate fired on its first execution, against the paragraph being written to
  satisfy the other two.

### 10.2 The two rules, and why a name-based lint is not enough

`fb_lint.py` looks for a local called `want` and a local called `got`. Rename
them and it goes silent; that is measured every run and printed. `w5audit`
never reads a name -- it inlines the locals into the condition, turns the
remainder into atoms keyed by source text (so two spellings of one call become
one atom taking one value), and executes:

* **rule A** -- the condition is true under every random assignment. It cannot
  fail. `req(True, ...)`, `x or True`, two literals compared.
* **rule B** -- one side is *derived from* the other and the predicate ignores
  every atom the two sides do not share. The 65,536-origin ring sweep in
  `fb_tick.py` is the standing instance, and its origin axis is re-measured
  every run at **one distinct outcome per window length**.
* **rule C** -- a tally, `if <pred>: fails += 1`, whose predicate is false for
  every case the sweep enumerates. It exists because rule B is evadable by
  spelling the truth as a literal rather than as a shared variable; that
  evasion was written, run against the analyser, and escaped before rule C
  was added.

### 10.3 The interchange format is unchanged

No record kind, tag, header word or file name in §6 changes. The audit reads
source, not dumps; it writes nothing; and `test_wave5.py` now re-hashes every
`noctis-harness/fb_*.py` it read and fails if one moved, for the same reason it
re-hashes `work/`: a grader that edits its subject is the stored-artifact defect
in its most direct form.
