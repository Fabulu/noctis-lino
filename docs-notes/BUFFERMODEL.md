# BUFFERMODEL -- the settled buffer model for the Noctis IV port

**Normative. Every wave after 5 inherits this document.**
Where it disagrees with `PORTPLAN.md`, `WAVEPLAN.md` or `docs-notes/LINOBUF.md`,
this document wins and §9 says why.

Executable form: `tests/test_wave5.py` (suite entry 17). Everything asserted
here that *can* be executed is executed there, on both sides, on every run --
the lino side rebuilt from `work/fb*.txt`, the model side re-derived from the
1996 sources. Nothing in this document is graded against a stored artifact.
Everything that *cannot* be executed is in §10, named, rather than implied.

---

## 1. The decisions, in one page

| # | Decision | §  |
|---|---|---|
| 1 | **One Noctis byte per 32-bit lino unit.** A byte offset *is* a unit offset. Packing survives only on disk. | 2 |
| 2 | **One flat workspace `NW`, 402,196 units, in `farmalloc` order**, with named constant base offsets. Not one lino array per Noctis buffer. | 3 |
| 3 | **Overruns are classified three ways, not policed one way.** Class C is free (the layout order), class A gets the full segment, class B gets a pad. Bounds checks are rejected; "fixing the writes" is rejected. | 4 |
| 4 | **Keep every alias but two.** Split `digimap2`; re-lay the `pvfile` arena. Everything else stays shared, because the game depends on it or because keeping it is free. | 5 |
| 5 | **The palette is four buffers and one LUT**, `v*4`, upload always from colour zero, `shade()` chops and **takes its destination as a parameter**. | 6 |
| 6 | **The present is read-only on the index page.** Cooperative 320×200, 1:1, `expand` reads `adaptor` and writes `fb` and touches nothing else. The background colour cycle is a *separate* pass over `s_background`. | 7 |
| 7 | **Accumulated deadline, exact rational period, skip-to-grid, signed-difference predicate, 16 ms sleep margin, calibrated cpms, servo bracketed against the PREVIOUS servo point.** | 8 |

Measured working set: `NW` 1.61 MB, whole port ≈ 1.98 MB, **0.18 % of the
measured 1 GB ceiling**. Memory is not a constraint and will not become one.

---

## 2. Decision 1 -- one item per unit

**One Noctis byte per 32-bit lino unit, value 0..255 in the low bits, no
packing anywhere in working memory.**

The argument is not memory (packing also fits) and not speed (packing measured
*faster* on two of five patterns, and the whole spread is under 0.1 ms against
a 54.9 ms tick). The argument is `txtr`.

`txtr` is not a buffer, it is a roving byte pointer. It is re-based onto four
different allocations and slid by **runtime byte amounts** -- `txtr += 48`
(`NOCTIS-1.CPP:274`), `txtr += (x << 3)` (`NOCTIS-1.CPP:1273`), base
`p_surfacemap + 2064` (`NOCTIS.CPP:1010`) -- and then indexed with a texel
address built in the 16-bit `BX`:

```
texel = ((V>>8) & 0xFF) * 256 + ((U>>8) & 0xFF)        TDPOLYGS.H:2817-2821
```

Under one byte per unit **every one of those expressions transfers from the C
verbatim**. Under packing, every byte offset needs an address `>>2` *and* a
phase `&3`, and because `txtr` slides by runtime amounts the phase is dynamic --
a second piece of state carried alongside every pointer, re-derived by hand at
several hundred indexing sites, in the subsystem we have the least ability to
test. `fragment`/`hpoint` run 160,000 times per frame (`NOCTIS-1.CPP:17-26`).

And the corollary that seals it: the original's out-of-bounds writes were
harmless *because neighbouring bytes were harmless*. Under packing every
tolerated overrun corrupts three innocent neighbours inside the same unit, which
converts §4 from "reproduce it" into "prevent it".

> Packing costs neither memory nor cycles. It costs correctness in exactly the
> subsystem where correctness is hardest to verify.

**Byte semantics, all executed** (`test_wave5.py` B1/B2/B3):

* a store truncates: `300 → 44`, `-1 → 255`;
* a byte store leaves the neighbouring unit untouched;
* eight distinct byte offsets -- including `0,1,2,3`, which a packed store would
  collide into one unit, and the top four units of the workspace -- each hold a
  distinct value and read back;
* 8→32 sign extension is required, not decorative: `n_globes_map` is `char`
  (`NOCTIS-0.CPP:1004`) and is right-shifted (`NOCTIS-1.CPP:4241, 4364`).
  `192 → -64`, `128 → -128`, `63 → 63`, `127 → 127`.

Sabotage S02 replaces the store with a packed four-per-unit one and B2 must
catch it.

**The one exception: the disk boundary.** Files stay byte-packed on disk; one
pack/unpack helper pair converts at every read and write. Two sub-cases must
*not* go through the bulk helper:

* **`freeze`/`unfreeze`** (`NOCTIS.CPP:453`, `NOCTIS-0.CPP:739-820`) writes 245
  raw bytes from `&sync` -- 40+ consecutive globals of mixed types with no
  alignment padding, 8-byte doubles at byte offsets 71, 79, 87. **Build it
  field by field.**
* **`loadpv`'s single packed `_read`** of `50*npolygs` bytes
  (`NOCTIS-0.CPP:2350`) becomes a per-field scatter -- see §5 alias 9.

---

## 3. Decision 2 -- one flat workspace in `farmalloc` order

**A single contiguous vector `NW` of 402,196 units. Every buffer sits at a
named constant base offset. The order is exactly the order `main()` calls
`farmalloc` (`NOCTIS.CPP:2163-2172`).**

One lino array per Noctis buffer is unimplementable: `txtr` re-bases across four
allocations, `p_background` *becomes* `s_background` at runtime
(`NOCTIS-0.CPP:5326`), and `polymap` reads a 64 KiB window from any base. Flat
plus offsets dissolves all three -- a base is an `int` variable and a re-base is
an assignment.

Do **not** rely on the compiler placing separately-declared vectors adjacently.
`NW` is one declaration and every base is a design-time constant.

### 3.1 The per-buffer table

`PAD = 16` units between blocks stands in for Borland's far-heap block header.
`LOWPAD = 16` sits below everything. Sizes come from `NOCTIS-D.H:25-56` and are
**parsed, not typed** (`tests/w5spec.py:parse_sizes`).

```
offset    units   region          NOCTIS-D.H          aliases and notes
--------------------------------------------------------------------------------
      0      16   (low pad)                           zones 0-1, both UNOWNED
     16      16   (pad)                               zone 2 UNOWNED, zone 3 = region 0's SUB
     32   7,340   n_offsets_map   om_bytes            offsets.map; background() only
  7,372      16   (pad)
  7,388  32,768   n_globes_map    gl_bytes+gl_brest   globes.map | sea/horizon texture
 40,156      16   (pad)                               class C lands here first
 40,172  64,800   s_background    st_bytes            star map | moon map | sky map |
                                                      shading buffer | colour cycle
104,972      16   (pad)
104,988  65,552   p_background    pl_bytes            orbital 360x180 map; ground
                                                      texture; a txtr base
170,540      16   (pad)                               class B: digit_at txtr[-6..-1]
170,556  40,000   p_surfacemap    ps_bytes            altimetry | STARMAP records |
                                                      cockpit screens; txtr, txtr+2064
210,556      16   (pad)
210,572  40,000   objectschart    oc_bytes            == ruinschart == atmosphere
                                                      == overlay
250,572      16   (pad)
250,588  20,480   pvfile          pv_bytes            polygon arena, 16 handles,
                                                      409 polygons at 50 units each
271,068      16   (pad)                               class B: loadpv +3*npolygs
271,084  65,540   adapted         sc_bytes            hidden page; full segment + 4
336,624      16   (pad)
336,640  65,540   adaptor         sc_bytes            visible page (DOS: VGA A000:0)
402,180      16   (pad)
--------------------------------------------------------------------------------
NWTOP   402,196 units = 1,608,784 bytes
```

Outside `NW`:

```
fb            64,000 units   [Display Origin], 00RRGGBB
pal              256 units   the expanded LUT
pal6             768 units   tmppal, the master six-bit palette
curpal6          768 units   what has been UPLOADED
retpal6          768 units   return_palette   (fade source)
srfpal6          768 units   surface_palette  (fade source, and shade's usual
                             destination - §6)
range8088        192 units   the fixed 64-entry greyscale ramp
digimap2       2,340 units   32x36 pilot font, one uint32 per unit (split, §5)
statics       ~22,000 units  nearstar_*, ani_*/tgt_*, lft_sin/cos, riga, m200, ...
--------------------------------------------------------------------------------
total         ~494,000 units  ~1.98 MB
```

`adaptor` has no `farmalloc` in DOS -- it is the literal far pointer
`0xA0000000` (`NOCTIS-0.CPP:53`). It is placed last, sized a full segment
because `mask_pixels` wraps a 16-bit `DI` past 65,535 back through 0
(`NOCTIS-0.CPP:691-710`), and nothing overruns *into* it.

**The low pad is not there for `digit_at`.** LINOBUF §2.3 annotated
`nw[0..15]` "absorbs `digit_at`'s `txtr[-6..-1]`", which is wrong: `digit_at`'s
`txtr` is `p_surfacemap`, so its underflow lands in `p_background`'s trailing
pad -- measured at `NW+170,550`, region 3, six units (O2). The low pad exists so
that no region is ever the first thing in the workspace, where an underflow
would walk off the vector instead of into a guard.

### 3.2 The order is the whole trick

Reproducing `farmalloc` order makes **every read past the end of a buffer land
on the neighbour DOS gave it**, for zero units and zero code. That is strictly
more faithful than padding each `txtr` base out to 64 KiB with zeros, and 61,128
units cheaper. The interesting case is exactly where the two differ: what does
the sea texture sample when its V accumulator exceeds row 127? Zero-padding says
zeros; `farmalloc` order says the star/sky surface map, which is what DOS gave
it -- `s_background` is the very next allocation.

Executed (`test_wave5.py` O4): a marker is written into `s_background[0]`, then
read back through the *texture* base at texel 32,784. It reads 123. Texel 32,768
reads the pad, which is zero in a release build.

### 3.3 The `QUADWORDS` trap

`int QUADWORDS = 16000` (`NOCTIS-0.CPP:51`) is the dword count for `pcopy`,
`pclear`, `pfade`, `psmooth_*`, `ssmooth`, `lssmooth` and `mask_pixels`, and it
is **changed at runtime** -- eight distinct values, steady-stating at **14,560**
(58,240 bytes = 182 rows) after `NOCTIS.CPP:2206`, not 16,000. Any page
operation that hard-codes 64,000 gets the HUD visor animation and surface
generation wrong. Make it a variable and pass it.

---

## 4. Decision 3 -- the overrun strategy, three classes

Guard bands, bounds checks and "fixing the writes" are three answers to three
*different* questions. Applying one uniformly is what produced `niv-lr`'s two
known bugs.

**Bounds checks are rejected.** `fragment`/`hpoint` run 160,000 times per frame;
a check there is 160,000 branches per frame, and it is semantically wrong --
these overruns are behaviour to reproduce, not bugs to trap.

**"Fixing the writes" is rejected, with receipts.** `niv-lr` fixed `digit_at` by
starting its loop at `n = 1` after Valgrind complained (`noctis.cpp:643-646`,
comment: *"I just blindly changed this loop to start at one. It probably breaks
things..."*). It does: it silently drops the top scanline of every cockpit
glyph. `niv-lr` also clamped `Stick` (`noctis-0.cpp:1296`, *"TODO; Figure out
why this is over-running"*). Both are divergences we must not inherit.

| class | what | sites | treatment | cost |
|---|---|---|---|---|
| **A** | write, contained by a 16-bit wrap inside the buffer's own segment | `Segmento`/`Stick` `riga[]` scatter (`TDPOLYGS.H:245-259`); `mask_pixels` `DI` wrap; `cirrus` `bx=(py+px)>>1`; `spot` `di` wrap; `NOCTIS-0.CPP:5069,6423` counter wraps | **a MASK at each site's own truncation point**, plus the full segment so the folded address lands in the owning region: `adapted`/`adaptor` at 65,540, `p_background` 65,552, `objectschart` 40,000 > 32,768 | 1,540 units **and code** -- `MEM u16`, `MEM u16 site`, `MEM seg addr`, `MEM seg check` |
| **B** | write, outside the buffer, never read back | `digit_at` `txtr[-6..-1]` (`NOCTIS.CPP:614-628`); `loadpv`'s `3*npolygs` past `pvfile_c` (`NOCTIS-0.CPP:2383-2391`) | **dead pad**, and `loadpv` additionally fixed by the arena re-layout (§5 alias 9) | 16 units, no code |
| **C** | read, outside the buffer | `polymap`'s 64 KiB window from any `txtr` base; `ssmooth` +39; `globe` tapestry +718; `hpoint` +201; `fragment` −1 | **`farmalloc`-order layout** (§3.2) | 0 units, 0 code |

`sc_bytes = 65540` is class A and is kept **faithful, not clamped**:
`NOCTIS-D.H:50-54` calls `poly3d` *"difettosa … che non ho né tempo né voglia di
modificare"* and sized the page at a full segment plus 4 precisely so it could
scribble. Executed (O5): `adapted[65536..65539]` are writable, readable, and are
not `adaptor`.

### 4.0 CORRECTED -- an allocation size cannot reproduce a wrap

The row above used to read *"allocate the full segment … 1,540 units, no
code"*, and that was **wrong**, not merely incomplete. Under DOS the write
folded back to offset 0 **of the segment**; under 32-bit unit addressing the
index keeps counting and the write walks linearly past the region end into
whatever follows. No choice of *size* changes an *index*. A natural 32-bit
transcription of `cirrus` with `py = 65000, px = 60000` -- both legal `unsigned`,
`NOCTIS-0.CPP:4446` -- computes 62,500 where 16-bit `BX` computes 29,732, and the
write lands 273,072 units away, over a pad and over the whole `pvfile` arena,
undetected.

**The mechanism is a mask, and it belongs at the site's own truncation point.**
That point is *not* the same for the two sites, which is why one helper cannot
serve both:

| site | source | truncates at | masked form | delta if wrong |
|---|---|---|---|---|
| `spot` | `NOCTIS-0.CPP:4485` | the 16-bit `DI`, **after** both adds | `SPBG + ((4 + py + px) & 65535)` | 65,536 |
| `cirrus` | `NOCTIS-0.CPP:4715` | `BX`, **before** the shift (`mov bx,py / add bx,px`) | `SOBJ + ((((py+px) & 65535) >> 1) + 4)` | 32,768 |

A single "mask the final index" helper halves `cirrus`'s error and is still
wrong, so the *difference between the two deltas* is the graded quantity, not
the fact that a mask exists. Measured over 340 cases per site: `spot` min = max
= 65,536 over 212 wrapping cases, `cirrus` min = max = 32,768 over 208. Two
separate sabotages, one per mask, are each caught by a different check (M2, M3).

**The mask is taken against the SEGMENT ORIGIN, not the buffer base.** `SEG` is
`R* − 4` for every `farmalloc`'d block, so a masked offset of 0..3 lands on the
four header units below the buffer, which is the `SUB` zone's *allowance* and
not a violation. `adaptor` is the exception: it is the literal far pointer
`A000:0000`, so its segment offset 0 *is* its base.

**Containment is by construction, and saying so is part of the finding.**
`SPBG + m` spans `RPBG−4 … RPBG+65531` against a legal window of
`RPBG−8 … RPBG+65551`, so the assertion holds for *every* input at both sites.
The 340-case battery is not what makes it true and must not be quoted as if it
were.

**Still open (§10 item 6):** the mask has no *game* call site. Wave 5 has no
`spot()`, `cirrus()`, `crater()`, `wave()` or `stick()`, so the reachability
census is **not exhaustive** and must not be called so -- `volcano`
(`NOCTIS-0.CPP:4625`) and `atm_cyclon` (`:4735-4740`) are callers whose `px` can
escape and are not censused.

Executed class B (O2, O3): `digit_at`'s six bytes below `p_surfacemap` land at
`NW+170,550`; one unit past `pvfile` lands at `NW+271,068`. **Both are now
COUNTED, not flagged** -- see §4.1.

### 4.1 CORRECTED -- the pad's two jobs are SEPARATED, not ordered

The previous rule -- *poison, check, then zero, in that order* -- solved the wrong
half of the problem. Ordering separates the **debug** job from the **release**
job. It does nothing about the fact that within a single debug run the pad is
*simultaneously* a guard band (any write is a violation) and the legitimate
destination for `digit_at`'s `txtr[-6..-1]` (`NOCTIS.CPP:614-628`, with
`txtr = p_surfacemap`, landing in `nw[170,550..170,555]`). So the first cockpit
glyph of a debug build fired the canary and halted, and a legitimate write was
indistinguishable from an overrun.

**Rule: every pad is TWO ZONES, and every zone carries an explicit allowance
list.**

```
pad p  =  nw[padbase(p) .. padbase(p)+15]
          TAIL = the low  8 units, immediately ABOVE region p−2   magic 0xA5A5A5A5
          SUB  = the high 8 units, immediately BELOW region p−1   magic 0x5A5A5A5A
zone index zi = 2p + role,  so the table is a pure function of the layout
```

Eleven pads, twenty-two zones, and **`nw[0..31]` is covered** -- the pad list has
eleven entries and is written out rather than derived from `rtab`'s nine, which
is precisely the bug that left the two low pads guarded by nothing.

Three allowance entries, each with its citation:

| zone | units | why |
|---|---|---|
| every owned `SUB` except `adaptor`'s | `SUB+4..+7` | the region's DOS segment offsets 0..3, reachable by any 16-bit wrap (§4.0) |
| `p_surfacemap`'s `SUB` | `SUB+2..+7` | `digit_at`, `NOCTIS.CPP:614-628` |
| `pvfile`'s `TAIL` | `TAIL+0` | `loadpv`, `NOCTIS-0.CPP:2383-2391`; retired when alias 9 re-lays the arena |

An allowance unit that changes is **counted** in `[MCexp]`; anything else is a
violation. A build that never performs `digit_at`'s write fails just as hard as
one that performs it in the wrong place, because the count is derived from what
the programme did.

**The guard must not be swallowed by the allowance.** One unit *further* past
`pvfile` -- `TAIL+1` -- is still a violation and is asserted to be (O3b). Without
that, an allowance covering the whole pad would pass O2 and O3 and the two jobs
would have been merged the other way round.

Poison → check → zero still applies to the *release* state, and
`test_wave5.py` still runs the class-C reads after `MEM zero pads`, which is why
O4 expects 0 at texel 32,768.

### 4.2 CORRECTED -- a canary that cannot fail is worse than no canary

The old text said *"a canary that always fires cannot pass"*, and that half was
right: the clean check runs first and requires `fired = 0, n = 0, exp = 0`. The
half that was missing cost more. **FBDUMP kind 6 v1 was 18 units in which both
the "expected" and the "actual" field held `0xA5A5A5A5`, written by construction
on both sides.** A clean run and a build with the walker deleted produced a
**bit-identical** record, and the grader compared `can[i]` against `can[i+1]` --
two copies of one literal. The check passed for every build that could ever be
made.

**v2 stores no literal.** Four units per pad, eleven pads:

| unit | field | what the grader derives it from |
|---|---|---|
| 0 | clean read of `nw[padbase+slot]` after poisoning | the zone role: `0xA5A5A5A5` in a `TAIL`, `0x5A5A5A5A` in a `SUB` |
| 1 | the same address re-read after storing `WITNESS(i)` | the witness rule |
| 2 | the pad index + 1 the walker reported | `i + 1` |
| 3 | the `nw` offset of the first violation | `padbase(i) + slot(i)` |

`slot(i)` sweeps **mod 12, not mod 16**: units `+12..+15` are `SUB+4..+7`, an
allowance that cannot fire by design, so a probe expecting them to fire would be
asserting the guard model is wrong. Two independent walks exist and use
different sweeps -- `work/fbshell.txt` uses `(7i+1) mod 12`, `tests/w5probe.txt`
uses `(5i+3) mod 12` -- and both avoid `pvfile`'s `TAIL+0` and
`p_surfacemap`'s `SUB+2..+7`.

**Proved by breaking it:** stubbing `MEM check pads` moves 22 of the 44 units.
Under v1 the same edit moved nothing.

**Stated limit.** `WITNESS(i)` folds the poison the walker itself wrote into the
value (`0xB0B32000 + 17i + (clean & 255)`), so no single literal can stand in
for it -- but a saboteur who reads the rule can still *recompute* it instead of
loading it, and a build doing that produces a bit-identical unit 1. The
load-bearing fields are 0, 2 and 3.

---

## 5. Decision 4 -- the alias register

Splitting is safer and now affordable, so the burden is on *keeping* -- except
where the game depends on the aliasing, where the burden reverses.

| # | alias | verdict | reason | executed as |
|---|---|---|---|---|
| 1 | `n_globes_map` ⟷ sea/horizon texture (`txtr`) | **KEEP** | Sequential reuse, never simultaneous. `globe()` is called only from `NOCTIS.CPP:2588, 2592` and `NOCTIS-0.CPP:5564, 5592` -- none inside `planetary_main()`. The sea gradient destroys `globes.map` and nothing reads it until `load_QVRmaps()` (`NOCTIS-1.CPP:5039`). Keeping preserves the class-C neighbour relation for free. | A2 |
| 2 | `n_globes_map` ⟷ `digimap2` (+22,586, **2 mod 4**) | **SPLIT** -- 2,340 units, one `uint32` per unit | The only misalignment in the project, and provably safe to split: `digimap2` has exactly one reader (`NOCTIS.CPP:621`, inside `digit_at`) and `digit_at`'s callers are all in `screen()`, `vehicle()` and `main()` -- none reachable from `planetary_main()`, which uses the *static* `digimap[325]`. So the font is destroyed by the sea fill and never read while destroyed; `load_digimap2()` is restoration, not a dependency. | A3 |
| 3 | `objectschart` ⟷ `ruinschart` | **KEEP -- mandatory** | Same *byte*, different bitfields. `AF1/AF2/AF3` = 0x40/0x80/0xC0 write `object2_class` and `ruinschart[h1]` (`NOCTIS-1.CPP:1177`) and `objectschart[h1].nr_of_objects` (`:1324`) use the **same index**. The ruins writer clobbering an object slot is observable behaviour. Splitting changes the game. | A1, Q1 |
| 4 | `objectschart` ⟷ `atmosphere` / `overlay` | **KEEP** | Sequential reuse at different resolutions -- orbital `[ptr>>1]` over 0..32,399, landed `[ptr]` over 0..39,999; the transition is an explicit `_fmemset` (`NOCTIS-1.CPP:1970`). Free to keep. **Trap:** `create_sky(char atmosphere)` (`NOCTIS-1.CPP:2736`) has a *parameter* of the same name that is a boolean. | -- |
| 5 | `p_background` ⟷ `s_background` **runtime swap** | **KEEP -- nothing to split** | `NOCTIS-0.CPP:5326`/`:5331`, restored `:5605`. `p_background`'s base must be a **variable**. Keep both at their natural sizes: the size difference *is* what creates `s_background`'s three class-C overruns, and the layout catches all three in `p_background`. | A4 |
| 6 | `p_surfacemap` ⟷ `txtr` at +0 and +2,064 | **KEEP** | Free under one-per-unit: an offset variable. | A5 |
| 7 | `p_surfacemap` `char` ⟷ `double` (STARMAP) | **KEEP storage, SPLIT the view** | 32-byte records, `double` at record offset 0, type byte at 29 (`NOCTIS-0.CPP:4020-4030`, `:5768-5790`). Byte array plus an assemble-double-from-8-units helper; the soft-float double is two units anyway (FLOATPOLICY). | `MEM dbl` |
| 8 | `adapted` ⟷ `tinta`/`escrescenze` scratch | **KEEP, at 63,996..63,997** | Under `farmalloc` offset == 4 these are **visible pixels**, row 199 columns 316-317. `niv-lr` relocated them to 64,000 (`tdpolygs.h:938`); ours stays where the original put them and the test **rejects** the LR variant. Conditional on §10 item 4. | F1, sabotage S13 |
| 9 | `pvfile` sub-arrays at unaligned byte offsets | **RE-LAY-OUT** | `pvfile_x[h] = (float far *)(pvfile + datatop)` where `datatop` has advanced by `1*npolygs` -- a `float` array at a non-multiple-of-4 byte offset whenever `npolygs % 4 != 0`. Unit addressing cannot express it. Re-lay so every sub-array is unit-aligned; replace the one packed `_read` with a per-field scatter; `unloadpv`'s `_fmemmove` compaction moves in sub-array units. **Observationally equivalent only if nothing outside `loadpv`/`unloadpv` reads `pvfile` as raw bytes** -- §10 item 3. Aligning changes no size: 50 units per polygon, 409 polygons, same arena. | L5 |

**Two behaviour dependencies, one per direction.** Alias 3 is a genuine
dependency and must be kept. Aliases 1 and 2 *look* like dependencies (the game
reloads all three maps on leaving a planet) and are not -- the reload is
restoration. That reachability check is what makes the `digimap2` split safe,
and it was checked rather than assumed.

---

## 6. Decision 5 -- the palette

**Structure.** `pal6` is the master (Noctis's `tmppal`); `curpal6` is what has
been "uploaded"; `pal` is the 256-entry `00RRGGBB` LUT rebuilt from `curpal6`.
The port needs both `pal6` and `curpal6` because the DAC is now software.
`retpal6`/`srfpal6` are fade sources so fades do not compound.

**Bands** (`NOCTIS.CPP:2218`): 0–63 vehicle/computer/artefacts; 64–127
cosmos/galactic background/clear skies; 128–191 stars or moons; 192–255 planets.

**`tavola_colori(src, first, n, fr, fg, fb)` -- three steps, and the third is a
trap.** Copy `n*3` from `src` into `pal6[first*3…]`; filter in place
(`v = v*f/63`, clamped to 63, integer throughout); then **upload starting at
colour 0** and running to `(first+n)*3`. The upload always starts at zero, so an
update to band 64–127 uploads colours 0–127 and **leaves 128–255 stale**. That
is behaviour, not an accident, and the test makes it observable inside a single
run: the pinned sequence ends with a `shade` over 192..255 that uploads nothing,
so `pal6` and `curpal6` differ over 186 of those 192 components (P4).

**Four traps, all reproduced and all executed:**

1. **`tavola_colori(tmppal + 3*k, k, n, …)` is a self-copy** -- source aliases
   destination (`NOCTIS.CPP:3777`, `NOCTIS-0.CPP:5193`). With separate buffers
   this must become "filter in place"; copying from `curpal6` instead silently
   changes the sky, because `curpal6` is one upload stale.
2. **`filtro_*` is a signed `char`** and `temp` is a 16-bit unsigned. Above 127
   it goes negative, becomes a huge unsigned, and clamps to 63 -- the `> 63` test
   never sees a negative. Reproduced, and the out-of-range condition is
   **recorded** (`PVrange`), not assumed away. `NOCTIS-1.CPP:3934` passes
   `random(64)+64` = 64..127, which fits; assert it, do not trust it. (P5)
3. **`shade()` truncates.** The store is a C float-to-`unsigned char`
   conversion, which is a cast, which chops; lino's `=,` rounds to nearest and
   would be wrong. Use the Wave 3 engine's `FToIntChop` (Borland's `__ftol`) --
   do not rebuild it. The running value is narrowed to binary32 after every
   `+=` because `start_r` is a `float` variable. The clamp is the original's
   inverted one: `>= 0 && < 64` chops, else 63 if `> 0` else 0.
   Sabotages S10 (round) and S11 (clamp inverted) must both fail P1.
4. **Six bits to eight is `v * 4`** (63 → 252). Not because `niv-lr` does it,
   but because the game's own `snapshot()` writer scales the DAC by ×4, which
   makes our index→RGB mapping *identical* to the palette inside the BMPs that
   are oracle route 1. DOSBox writes `(v<<2)|(v>>4)`; `PLTE>>2` recovers the
   6-bit DAC on both sides. **Made once, in the LUT rebuild.** Sabotage S08.

**`shade()` takes its destination buffer.** `NOCTIS-0.CPP:1151` declares
`void shade (unsigned char far *palette_buffer, unsigned first_color, …)`
and **14 of its 21 call sites pass `surface_palette`**, not `tmppal`
(3 sites in `NOCTIS.CPP:3774-3776`, 4 in `NOCTIS-0.CPP:5180-5183`, 14 in
`NOCTIS-1.CPP:3050-3086`). A `shade` that can only write `pal6` cannot express
the majority of the original's calls. **This is not yet implemented** -- §10
item 5 -- and `tests/w5shade.txt` asks for the parameter and fails to compile,
which is the executable form of the finding.

`tavola_colori` is different: it *always* writes `tmppal` (`NOCTIS-0.CPP:179`),
so hard-coding `pal6` there is faithful. Do not "fix" it.

**Cost is a non-issue and must not be optimised.** A full 256-entry LUT rebuild
measured 0.0004 ms; the 64-colour filter 0.0009 ms; a 16-step fade ladder
0.06 ms. Four orders of magnitude below the tick. Do not band the rebuild, do
not cache it.

---

## 7. Decision 6 -- the framebuffer and the present

**Cooperative 320×200, permanently, presented 1:1.** Exclusive mode works and
buys nothing measurable: zero per-frame advantage, 508 ms to enter, 768 ms to
leave, `RETRACE` not vsync-locked either way -- and it left a maximized window
squashed to 221×109 that Windows did not restore. PORTPLAN's "exclusive 320×200,
closest thing to mode 13h" is superseded: true, and irrelevant.

**Both pages are real.** `adaptor` is VGA memory in DOS; here it is an index
buffer, and `pcopy(adaptor, adapted)` stays an index→index copy. Do **not**
optimise it away by expanding `adapted` directly: `pclear(adaptor,0)`
(`NOCTIS-1.CPP:5021`), `areaclear`, and vanilla's type-9 substellar case all
write the *visible* page. That last one is a confirmed `niv-lr` divergence and
the one thing DOSBox's raw capture can see that the game's own BMP cannot.

```
Present:  for i in 0..63999:  fb[i] = pal[adaptor[i]]        unrolled x4
          [Display Command] = RETRACE; isocall
```

**The expand is READ-ONLY on the index page.** LINOBUF §5.4 directed that
Noctis's background colour cycle be *fused* into the expand loop, for a measured
22 %. That is the right arithmetic applied to the wrong buffer at the wrong
rate. The loop exists -- verbatim, at `NOCTIS.CPP:3779-3784`:

```c
if (!farstar) { for (ir=0; ir<64800; ir++) {
        ig = (s_background[ir]+1)%64;
        ib = (s_background[ir]>>6)<<6;
        s_background[ir] = ig+ib; } }
```

-- but it cycles **`s_background`**, a 64,800-byte offscreen star/sky map, inside
the sky-palette redefinition path. It is not the visible page and it does not
run once per present. Fusing it corrupts every visible unit on every present.
`PAL cycle` is therefore a separate pass over `s_background` (P6), and sabotage
S12 reinstates the fusion and must fail F2.

**Do not pre-bias the index buffer** to hold `pal+index`: measured at 0.0565 vs
0.0566 ms (nothing -- the add hides in memory latency) and it would destroy the
byte semantics a read-modify-write on the index depends on. **Do not build
dirty-rectangle tracking:** a 16×16 live region against the whole display saved
15 %, 16 %, 2 % for 1/250th of the area. The present is fixed cost.

**Budget -- ranges, never points.** The same binary on this machine measured a
full Noctis-shaped frame at p50 **1.47 / 2.60 / 4.78 ms** across three runs, and
the palette expand at **0.054 / 0.069 / 0.123 ms**. Two 60-present runs of
`tests/w5probe.txt` in display mode measured expand+`RETRACE` at
min 1.05–1.80, p50 **1.60–2.01**, p90 2.04–2.37, max 18.4–35.9 ms -- the max
being one `RETRACE` stall, which recon B saw once per ~600 presents in every
run.

> The conclusion "the platform is not the constraint" survives at ~9 % of a
> tick. **The individual numbers are not a budget** and must not be quoted as
> one; PORTPLAN's "0.799 ms" and LINOBUF §5.7's "1.472 ms" are both single
> samples of a quantity with ±100 % run-to-run variance.

**Input.** Events are pumped on their own thread -- a 7.1 s isocall-free
computation stayed `Responding` on all 66 samples and still *saw* a posted
`WM_KEYDOWN`. So the frame loop isocalls because it wants to present, not
because it must pump. PORTPLAN's "a frame that makes no isocall stops
responding" is refuted in both halves. Use the 98-unit LUCK table for held-key
flight input and `GET CONSOLE INPUT` for the ASCII FIFO. **There is no
window-close event; ESC-to-quit is the only exit.**

---

## 8. Decision 7 -- the tick

**The period is 65536/1193182 s = 54.9254012… ms, not 55.** 55 is `niv-lr`'s
rounding (`noctis-d.h:174`). Carried as an exact rational in timer counts,
decomposed so nothing overflows 32 bits:

```
period_counts = 55*cpms - (cpms*44505 + carry) / 596591
```

with the remainder carried across ticks. The naive `cpms*552086` overflows; the
largest intermediate here is `44505*cpms ≈ 4.0e8`.

**Seven rules.**

1. **Accumulate, never re-base.** Not because re-basing drifts much -- measured
   at +0.002 to +0.004 ms/tick on this machine, which refutes PORTPLAN's
   "+0.057 ms/tick" (that figure measures a 55 ms period, not the discipline)
   and does not reproduce LINOBUF's "+0.00071 ms/tick" either. The reason is
   that accumulation **recovers**: its minimum inter-fire gap is *below* the
   period, so a long tick is followed by a short one and the total returns to
   zero; re-base's minimum gap is never below the period and it keeps every
   hitch forever. Measured cumulative drift at ticks 55/110/165/219:
   accumulate +0.0001/+0.0001/+0.0000/+0.0001 ms; re-base
   +0.0635/+0.1633/+0.2961/+0.4419 ms, monotone and linear.
2. **Skip to the next grid point strictly in the future after a miss.** This is
   a **fidelity** requirement, not a timing one. The original computes no
   deadline at all -- `sync_stop` busy-waits for the next *edge* of a free-running
   counter (`NOCTIS-0.CPP:6025-6038`) -- so an overrunning frame loses a whole
   tick and re-aligns, and the frame rate is 18.2065/k and never anything
   between. The real game under capture measured 15–17 fps with a mean of
   exactly 1.50 ticks: a 50/50 mixture of 1- and 2-tick frames, which is what
   quantisation gives and a continuously-variable rate does not.
3. **The wait predicate is the sign of the difference, never a timestamp
   compare.** `A = [Counts]; A - [deadline]; ? A < 0 -> wait;`. `[Counts]` wraps
   about every 477 s, and an unsigned `now >= deadline` collapses a run of ticks
   to nothing at the wrap. Enumerated across the wrap and the 2^31 sign boundary
   (T7); sabotage S05 is the unsigned form.
4. **Sleep to a 16 ms margin, then spin.** Margin 16 costs 4.4× less CPU than
   spinning with identical p50/p90/max. Margin 4 is unusable: Windows `SLEEP`
   overshoots by more than 4 ms, giving 17.6 ms peak-to-peak jitter. Make it a
   constant with 0 = spin-only for benchmarking.
5. **Calibrate counts-per-millisecond; do not use the reported value.**
   `[Counts Per Millisecond]` is a per-process estimate reporting 8984…9023
   across launches (0.43 % spread) while the true rate is stable to 0.016 %; one
   launch carried a **+0.258 % rate error**, and accumulation cannot remove a
   rate error. Seed from it, then recompute across a bracketed phase of ≥1 s of
   real work (the residency touch qualifies and costs nothing extra).
6. **The servo brackets against the PREVIOUS servo point, not the start of the
   run.** This corrects LINOBUF §5.5 rule 5, which mandated "total counts /
   total ms since start" and thereby specified a defect: `[Counts]` is 32 bits
   and wraps at `2^32/cpms` = **477 s = 7.95 minutes**, after which the
   difference is wrapped and the computed rate collapses -- measured 8999 at
   60/300/450 s, then **1840** at 600 s and **4226** at 900 s, each clamped by
   the ±1 % bound into a permanent 1 %-per-14-seconds ratchet. Bracketing over
   the servo interval (~14 s, ~126,000 counts) can never wrap. Keep the ±1 %
   clamp, keep the "no update under 500 ms" rule, and keep a running estimate
   rather than a from-scratch one. **Not yet implemented -- §10 item 2.**
7. **The tick log is RAW.** Three units per tick -- absolute counts at fire, the
   deadline it fired against, a flag word -- so a grader recomputes periods,
   drift and skips itself rather than trusting a statistic the program computed.

**What is exact and what is a bound.** The deadline sequence is integer
arithmetic and is compared with **zero tolerance**: every logged deadline must
lie exactly on the rational grid, no tick may fire early, and every inter-fire
gap must be a whole number of periods. Only *overshoot* -- how far past its
deadline a tick actually fires -- is a measurement, and only it carries a bound.
`tests/test_wave5.py`'s header states the four bounds and why each is where it
is. Measured over 200 ticks under a full page-build + expand load with a 60 ms
hitch every 37 ticks, over four runs: p50 overshoot 0.000000 ms, p90
0.000000–0.000111 ms, max 3.10–11.50 ms, total drift 0.00003–0.0105 ms, gaps
quantised to {1,2} periods with 5 skips.

---

## 9. What this document changes

| claim | source | status |
|---|---|---|
| the colour cycle is fused into the expand | LINOBUF §5.4 | **overruled.** The loop is real (`NOCTIS.CPP:3779-3784`) but it cycles `s_background`, not the visible page, and not per present. §7 |
| the servo brackets against the start of the run | LINOBUF §5.5 rule 5 | **overruled.** It wraps at 477 s. §8 rule 6 |
| `shade` may hard-code its destination | LINOBUF §5.3 implicitly | **overruled.** 14 of 21 call sites pass `surface_palette`. §6 |
| `shade()` has 24 call sites, 17 with `surface_palette` | LINOBUF §5.3 | **corrected:** 21 and 14 |
| the pad's two jobs are unresolved | LINOBUF §3 | **resolved by SEPARATION:** two zones per pad, each with an explicit allowance list. Ordering alone was not enough and is what shipped. §4.1 |
| class A costs "1,540 units, no code" | this document, before Wave 5b | **wrong.** An allocation size cannot fold an index. A mask is required at each site's own truncation point. §4.0 |
| FBDUMP kind 6 proves the canary works | LINOBUF §6 | **wrong.** v1 was 18 units of `0xA5A5A5A5` on both sides; a deleted canary produced a bit-identical record. §4.2 |
| full frame 1.472 ms; expand 0.054 ms | LINOBUF §5.7 | **not reproducible.** 1.47/2.60/4.78 and 0.054/0.069/0.123 across runs. Quote ranges. §7 |
| re-basing costs +0.057 ms/tick | PORTPLAN | **refuted:** +0.002 to +0.004 ms/tick here. Accumulate anyway, because it recovers. §8 rule 1 |
| correctly-rounded re-base drifts +0.00071 ms/tick | LINOBUF §8 | **not reproduced:** 3–6× that |
| median tick 55.0000 ms | PORTPLAN | the target is **54.9254 ms** |
| exclusive 320×200 is the closest thing to mode 13h | PORTPLAN | true and irrelevant. **Cooperative, permanently.** §7 |
| a frame that makes no isocall stops responding | PORTPLAN | **refuted in both halves.** §7 |
| clear + expand + RETRACE = 0.799 ms; 785 fps | PORTPLAN | not reproducible; the probe's own stored output is self-contradictory (RETRACE alone 1.2735 ms vs expand+RETRACE 0.7988 ms) |
| the low pad "absorbs `digit_at`'s `txtr[-6..-1]`" | LINOBUF §2.3 | **wrong.** `digit_at`'s `txtr` is `p_surfacemap`; the underflow lands in `p_background`'s trailing pad, measured at `NW+170,550`. §3.1 |
| the working set is ~643 KB | PORTPLAN | **1.98 MB**, of which `NW` is 1.61 MB. `NOCTIS-D.H:58`'s "334941" is stale by 1,539 |
| split the 32,768-byte triple-purpose buffer into three | WAVEPLAN §3 | **overruled in part.** Split `digimap2` only; keep `globes.map` ⟷ sea texture. §5 |
| `[Counts Per Millisecond]` is usable as reported | -- | a per-process **guess**, 0.43 % spread, up to +0.26 % rate error. **Calibrate.** |

---

## 10. What remains open

Ranked. Two items are **executable and asserted**: `test_wave5.py` grades 2b and
6 XFAIL, so the suite fails the day one of them is fixed and this list is not
updated.

**Items 1, 2 and 5 are CLOSED.** They were the three defects Wave 5 asserted
rather than fixed, and each closure is justified by a measurement rather than by
an edit to this list:

- ~~1. The low pads are guarded by nothing.~~ **Closed.** `MEM build ztab`
  walks eleven pads from its own `MEM pad base` rather than from `rtab`'s nine.
  Corrupting `nw[3]` and `nw[20]` after poisoning now reports `fired = 1,
  n = 2, at = 3`; a walker derived from `rtab` reports `0, 0, 0`, and that
  sabotage (S05) is built and caught on every run. *Now asserted positively by:*
  C3.
- ~~2. The servo wraps at 2^32.~~ **Closed for the shipped rate; see 2b.** The
  sampler re-bases both anchors unconditionally *before* the band test, so the
  bracket is one window and never the whole run. Eight synthetic origins × 85
  firings of a 14,061 ms window (19.9 simulated minutes), seeded 4 % low:
  converged to the true rate in 4 firings and held it exactly across 2–3
  wrap-straddling windows per scenario, worst error 0. The **original**
  estimator on the identical data collapses to 5,355 against a true 8,999 --
  that control is what makes the result a claim rather than a tautology. *Now
  asserted positively by:* H1, H2, H3, T4.
- ~~5. `shade()` has no destination parameter.~~ **Closed.** `PAL shade`
  computes `3*[SHfirst] + [SHdstb]`; `PAL zero` defaults it to `pal6` so the 7
  `tmppal` sites need no change. Sabotage S19 restores the hard-coded `pal6`
  and is caught. *Now asserted positively by:* P7 (in the main dump) and P7b
  (the separate probe, whose *build failure* is the result).

2b. **`SRVMAX` is a literal, so the servo still aliases on a fast host.**
   `fbtick.txt:141 SRVMAX = 60000` and `fb_tick.py`'s copy are compile-time
   constants; neither derives from `[Counts Per Millisecond]`. The band
   therefore accepts a window whose *count* aliases 2^32 whenever
   `cpms > 2^32/SRVMAX = 71,583`. Driven at 1,000,000 cpms the shipped
   estimator reproduces the original ratchet exactly: 408,595 against a true
   1,000,000 after 85 firings, clamp-lo throughout, 59 % error. This host
   reports ≈ 9,000, so the shipped configuration is 8× inside the boundary --
   but the guard is a constant, not a derivation. *Fix:* one line, reject when
   `window_ms > 2^32/(k*cpms)`. *Guarded by:* X1, XFAIL.
3. **Re-grep `pvfile` for raw-byte readers** outside `loadpv`/`unloadpv` before
   the arena is re-laid out (§5 alias 9). None found; confirm at implementation
   time, because the re-layout is only observationally equivalent if that holds.
4. **`farmalloc` offset == 4** is inferred from the `Stick`/`Segmento` split,
   not measured. Nothing in Wave 5 depends on it, but alias 8 and every
   `es:[di+4]` reading do. Decisive experiment: DOSBox-X + `NOCTIS.SYM`, read
   the offset word of `adapted` after `init_FP_segments`; the rig exists
   (`tests/gen/recon_w5c/hostshot4.ps1`). Falsifiable prediction to check in the
   same session: `adapted[63996..63997]` carry `polymap`'s fill colour whenever
   `polymap` has run -- row 199, columns 316-317.
6. **The class-A mask has no GAME call site, and the census is not
   exhaustive.** The mechanism itself is closed -- §4.0 replaces
   "1,540 units, no code" with a mask at each site's own truncation point, and
   both deltas (65,536 for `spot`, 32,768 for `cirrus`) are measured with
   min = max over 212 and 208 wrapping cases. What is **not** closed is
   reachability. Wave 5 has no `spot()`, `cirrus()`, `crater()`, `wave()` or
   `stick()`: `FBDUMP` kind 10 reads `calls = 0` for sites 2..5, and the only
   callers of the masking primitives anywhere are the two synthetic batteries.
   The census must therefore **not** be called exhaustive. Two callers with the
   same escape shape are not censused at all: `volcano` (`NOCTIS-0.CPP:4625`),
   whose `px = cx + cos(a)*g` runs `g` over `cr/2 .. cr-1`, and `atm_cyclon`
   (`:4735-4740`), which applies `px += random(4)` / `px -= random(4)` to an
   already-wrapped unsigned `px` between calls. Of the omitted callers only the
   `4990/4993` loop is provably safe (`px = ranged_fast_random(360)`, never
   negative). The remaining audit -- `Segmento`/`Stick` `riga[]`, `mask_pixels`,
   `pv_dep_i` -- **is Wave 6's first job**, and it is now an audit of *call
   sites* rather than of the mechanism. *Guarded by:* X2, XFAIL.
7. **`n_globes_map` is `char` (signed)** and is right-shifted. Values are 0..63
   in practice, so it does not bite -- but check the loaded `globes.map` bytes
   rather than silently switching to unsigned.
8. **Whether any class-C read-overrun is actually sampled** with real data.
   Unknown until a real frame renders. The layout preserves DOS adjacency for
   every read-overrun the audit found; whether any is *reached* is a Wave 6/7
   question and the first suspect if a texture band differs from DOSBox.
9. **27 dead `extern`s and three dead `TDPOLYGS.H` texture loaders.**
   `init_texture_mapping` is never called, so `txtr` is *only* ever an alias.
   Do not port them. `GFX.H`/`FAST3D.H`/`TEXT3D.H`/`PITAGORA.H` are not in the
   build set at all.
10. **Long sessions.** The longest soak on record is 22 s; `test_wave5.py`'s is
    11 s. Multi-hour behaviour belongs to Waves 8–9 and item 2 is the known
    landmine.
11. **Everything visual.** No renderer exists, so no frame can be compared
    against DOSBox-X or the game's own BMP; the palette pipeline is the only
    part of the display chain that Wave 5 can grade against the 1996 binary,
    and `test_wave5.py` grades the framebuffer only as an exact transformation
    of an index page it built itself. Nothing is eyeballed as a pass criterion.

---

## 11. Wave 5c -- how the model's own evidence is now policed

Nothing in sections 1–9 changes. This section records the one mechanism added
around them, because a buffer model is only worth what its graders are worth,
and this project has now shipped a check that could not fail three times.

**`tests/w5audit.py`, run inside `tests/test_wave5.py` (entry 17 of
`run_all.py`).** It reads every check condition in `noctis-harness/fb_*.py`,
`fbx_*.py` and `tests/`, inlines the locals and module functions feeding it,
replaces what is left with opaque atoms keyed by source text, and **executes**
the condition over 300 random assignments. A condition that comes out true
under every one of them cannot fail, and the run fails. A comparison one of
whose sides is *derived from the other* -- its atom set strictly containing the
other's -- and whose truth never changes when the non-shared atoms vary is the
second rule: that is a sweep whose axis carries no information.

Why this belongs in the buffer model's own document: the two rules are exactly
the two ways this model has been mis-graded.

* **One item per unit (§2)** is what makes a canary readable at all, and Wave 5's
  kind-6 canary compared `0xA5A5A5A5` against `0xA5A5A5A5` -- both written by
  construction. Rule A.
* **The 32-bit counter ring (§8)** is what the tick servo has to survive, and
  the sweep that was supposed to prove it recovers `want` from
  `(end - ((end - want) & M32)) & M32`. Rule B. It is still in the tree,
  recorded OPEN, and re-measured every run: 65,536 origins, **one** distinct
  outcome per window length.

Four checks were **deleted as void** from `tests/` during this wave, all found
by the analyser on its first run over its own author's files. They are
enumerated with their reasoning in `HARNESSAUDIT.md` §8.4, which is the
list a future wave should read before writing a check.

**What did NOT change.** The one-item-per-unit rule, the flat 402,196-unit
workspace in `farmalloc` order, the three overrun classes, the alias register,
the palette pipeline, the framebuffer and the corrected tick servo are all
untouched. `test_wave5.py`'s own canary replacement and its 23-sabotage battery
are untouched. The open items in §10 are unchanged and both XFAILs remain open:
`SRVMAX` is still a literal, and no game call site drives the class-A mask.
