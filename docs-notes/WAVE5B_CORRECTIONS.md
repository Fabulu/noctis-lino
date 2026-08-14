# WAVE 5b -- what was corrected, what was proven unnecessary, what remains open

**Scope.** Wave 5 delivered a buffer model, a framebuffer and a tick, and the
adversarial reviewer rejected it. The suite reported 17/17 because the test
writer built 109 careful checks around a model that had already been rejected --
and one of those checks could not fail at all. This wave fixes the six named
defects and nothing else. The three surviving decisions (one Noctis byte per
32-bit unit; one flat 402,196-unit workspace in `farmalloc` order; the tick's
PERIOD arithmetic, accumulation, skip-to-grid and signed-difference predicate)
are untouched, and `docs-notes/BUFFERMAP.md` is untouched.

**Executable form.** `tests/test_wave5.py`, suite entry 17. Every number quoted
below is produced on every run by both sides independently: the lino rebuilt
from `work/fb*.txt` into `tests/gen/w5`, the model re-derived in
`tests/w5spec.py` from `NOCTIS-D.H`, `NOCTIS.CPP`, `NOCTIS-0.CPP` and
arithmetic. Nothing here is graded against a stored artifact.

**Suite result: `test_wave5.py` 156 checks, PASS; `run_all.py` 18 of 18, PASS.**
23 deliberately broken builds, one edit each, every one caught by a named
check; 59 one-unit perturbations of the reference dump, every one noticed by
the check that claims to read that field; zero checks left unproved, and only
six checks exempt from perturbation -- each with a reason printed on every run.

---

## The two rules this wave was run by

**1. No check may be unbreakable.** Every graded check is proved to bite, either
by a broken BUILD (a real defect) or by a one-unit PERTURBATION of the reference
dump. `every graded check is proved breakable` is itself a check and it names
the exceptions with a reason for each. There are six: two belong to the display
variant, two read the 1996 sources rather than the dump, one is covered by a
sabotage, and one is a check whose result is a *build failure*.

**2. No asserted defects.** An XFAIL is a promise to fix something later. Wave 5
used three of them to record defects this wave was told to fix. All three are
now positive assertions. Two NEW xfails remain, for two things genuinely not
closed, and each states the boundary at which it breaks so that "still open" is
a measurement rather than a note.

---

## CRITICAL 1 -- the tick servo wrapped

### Fixed

The sampler re-bases **both** anchors unconditionally *before* the band test, so
the bracket is one window and never the whole run. The estimator is split out of
the sampler (`TK servo apply`), which is what makes it drivable with exact
synthetic windows in milliseconds instead of hours; nothing test-only lives in
`fbtick.txt` and the shipped path calls the same two routines in the same order.

Four further properties, each independently sabotageable and each now with a
check that reaches it:

| rule | check | what reaches it |
|---|---|---|
| a re-base first, unconditionally | H1, H2 | the horizon replay |
| b the acceptance band is SIGNED and two-sided | **H5** | a −86,395,000 ms midnight straddle |
| c servo ceiling under the aliasing point | **H7** | 1,000,000 cpms |
| d the divide is ROUNDED | **H4** | the jittered scenario |
| e the clamp step has a floor of 1 | **H6** | a 60 cpms counter |

### The check that would have caught it

`w5probe.txt` replays a whole run against a synthetic free-running counter
`C(t) = (C0 + cpms*t) mod 2^32` -- 85 consecutive windows of 14,061 ms, 19.9
simulated minutes, from **nine synthetic origins** placing the 2^32 crossing at
nine different phases. Waiting eight minutes is not a test; setting the origin
is. Three legs run over the identical timeline:

```
1 WINDOWED, shipped estimator    srvcnt = C(t) − C(t−w),  srvms = w
2 ANCHORED, shipped estimator    srvcnt = C(t) − C(0),    srvms = t
3 ANCHORED, ORIGINAL estimator   the same, through the pre-correction arithmetic
```

The estimator is seeded **4 % below** the true rate, so "do nothing" scores a
4 % error and the graded quantity is convergence, not the tautology "an
estimator seeded at the answer returns the answer".

Measured, on every run:

```
                       t=0..1,195,185 ms, 85 firings, seed 4% low
  windowed  converged in 4 firings, held EXACTLY, worst error 0
            2-3 wrap-straddling windows per scenario
  anchored (shipped)    ends 8,990 vs 8,999   worst error 273
  anchored (ORIGINAL)   ends 5,355 vs 8,999   worst error 3,644
```

**Leg 3 is why leg 1 means anything.** Leg 2 alone *recovers*, because `SRVMAX`
refuses every bracket past 60 s -- so a test comparing only 1 and 2 would report
success for reasons with nothing to do with the wrap. Leg 3 is the defect
itself, and on the same data it collapses. That is H3, and it is the check that
turns "the windowed servo holds across the wrap" into a claim that could have
come out false.

### Proven unnecessary

**The "wrap sweep" identities were dropped, not extended.** Wave 5's ring sweep
computed `start = (end − want) & M32` then `got = (end − start) & M32` and
tested `got != want`, over 589,824 cases, and the identity clause fired 0 times
in every one of them. It restates `(x+y)−x = y`. The horizon replay keeps a
single such cross-check -- that `C(t) − C(t−w)` equals an independently built
`cpms*w mod 2^32` -- and the code and the test **both say in so many words that
it is a distributivity identity, is expected to hold in every build, and is not
counted as wrap evidence anywhere**. The wrap evidence is the triple
(wraps > 0, windowed error 0, ORIGINAL estimator destroyed on the same data).

### Consequences elsewhere

**`SERVON` is a driver constant.** It was 256 inside `fbtick` while the soak ran
200 ticks, so `TK servo` **had never executed in a soak** -- which is exactly how
the wrap shipped past a 109-check suite. The reference run now sets it to 96
(5.27 s, over `SRVMIN`) and the servo fires twice, both samples accepted (T4).

**T1 is therefore piecewise.** cpms changes *during* the soak now, so a grid
rebuilt with one cpms is wrong. The servo log (FBDUMP kind 11) says when it
changed and T1 replays `fbtick`'s own recurrence across the schedule. Measured:
the single-cpms reconstruction misses **199 of 200** deadlines on a run whose
deadlines are every one of them exactly on the grid. That number is printed on
every run, which is how the piecewise part is known to be load-bearing.

**T12 was re-founded.** It converted the counter span with `[TKcpms]`, which
stopped meaning anything the moment the servo began running -- it read 19.8 ms
against its own 5 ms bound on a run with every deadline exactly on the grid. It
now compares `READ TIME` against the nominal grid: two independent clocks. It is
explicitly a **gross-failure backstop** and says so, because four runs of one
binary spread −14.7 to +8.3 ms while a 55 ms period would show +15.3 ms, inside
that noise. The period is graded exactly by T5 and T6's 256 deadlines instead.

### Closed after Wave 5b -- H7

The production servo now derives its maximum accepted window from the live
counter rate: `min(60000, floor((2^32-1)/cpms)/4)`. Both calibration and the
running servo use that ceiling. At 1,000,000 cpms the maximum is 1,118 ms, so
the unsafe 14,061 ms replay windows are rejected before their counter delta can
alias. All nine synthetic origins retain the safe runtime seed. H7 asserts this
positively; X1 is no longer an expected failure.

---

## CRITICAL 2 -- class A did not reproduce a 16-bit wrap

### Fixed

"Allocate the full segment, 1,540 units, **no code**" is dead. An allocation
size cannot fold an index: under DOS the write folded back to offset 0 *of the
segment*, and under 32-bit unit addressing the index keeps counting and walks
linearly through whatever follows.

**The mask sits at each site's own truncation point, and that point differs:**

| site | source | truncates at | delta if masked wrongly |
|---|---|---|---|
| `spot` | `NOCTIS-0.CPP:4485` | the 16-bit `DI`, **after** both adds | 65,536 |
| `cirrus` | `NOCTIS-0.CPP:4715` | `BX`, **before** the shift | 32,768 |

Measured over 340 cases per site, on every run: `spot` **min = max = 65,536**
over 212 wrapping cases, `cirrus` **min = max = 32,768** over 208. `min = max`
is the point -- the fold is a single constant, not an average. M4 asserts the two
deltas differ by exactly a factor of two, which is what makes "one helper for
both sites" a catchable mistake rather than a stylistic one.

**Two masks, two sabotages, two different catchers.** The first version of the
battery pre-masked `spot`'s offset and then handed the already-masked value to
`MEM seg addr`, which masks again -- so `spot`'s fold was applied twice and
deleting either mask alone left `spot` unchanged, with the sabotage caught only
by `cirrus`. That is a check passing for the wrong reason. `spot` now hands
`MEM seg addr` the RAW offset; S08 (delete `MEM u16`) is caught by M2 and S23
(delete the mask at `MEM u16 site`) is caught by M3.

The mask is taken against the **segment origin**, not the buffer base: `SEG` is
`R* − 4` for every `farmalloc`'d block, so a masked offset of 0..3 lands on the
four header units below the buffer -- which is the `SUB` zone's allowance, and
which is why CRITICAL 2 and MAJOR 3 had to be solved together.

### Proven unnecessary -- and stated rather than asserted

**Containment is a property of the constants, not a result of the battery.**
`SPBG + m` spans `RPBG−4 … RPBG+65531` against a legal window of
`RPBG−8 … RPBG+65551`; `SOBJ + ((m>>1)+4)` spans `ROBJ … ROBJ+32767` against
`ROBJ−8 … ROBJ+40000`. Both hold for **every** input at **both** sites. The
check M5 is kept because a wrong `SAlo`/`SAhi` or a mask against the base
instead of the origin would break it -- but its detail text says outright that
the 340-case battery is not what makes it true, so nobody can quote it as
empirical coverage.

### Still open -- X2, XFAIL, and it resolves BUFFERMODEL open item 6

**No game call site drives the mask.** Wave 5 has no `spot()`, `cirrus()`,
`crater()`, `wave()` or `stick()`: FBDUMP kind 10 reads `calls = 0` for sites
2..5 and the only callers of the primitives anywhere are the synthetic
batteries. **The reachability census is not exhaustive and must not be called
so.** Two callers with the same escape shape are not censused at all:

* `volcano` (`NOCTIS-0.CPP:4625`), whose `px = cx + cos(a)*g` runs `g` over
  `cr/2 .. cr−1`;
* `atm_cyclon` (`:4735-4740`), which applies `px += random(4)` / `px -= random(4)`
  to an already-wrapped unsigned `px` between calls.

Of the omitted callers only the `4990/4993` loop is provably safe
(`px = ranged_fast_random(360)`, never negative). BUFFERMODEL open item 6 is
rewritten from "the wrap is not expressible" -- it is now expressible and
expressed -- to "the mechanism has no game caller", which is the honest remaining
statement and is Wave 6's first job.

---

## MAJOR 3 -- the pads had two mutually exclusive jobs

### Fixed

Ordering (poison → check → zero) separates the *debug* job from the *release*
job and does nothing about the fact that within one debug run a pad is both a
guard band and the legitimate destination for `digit_at`'s `txtr[-6..-1]`. The
two jobs are now **separated by structure**: every pad is two zones, each with an
explicit allowance list.

```
pad p = nw[padbase(p) .. padbase(p)+15]
        TAIL = low  8 units, above region p−2, magic 0xA5A5A5A5
        SUB  = high 8 units, below region p−1, magic 0x5A5A5A5A
11 pads, 22 zones, and nw[0..31] is covered
```

Measured on the clean build: **141 guarded + 35 allowance = 176 units over 22
zones**, `nw[0..31]` covered, 0 violations, 0 violating units.

| citation | zone | units |
|---|---|---|
| `NOCTIS.CPP:614-628` (`digit_at`) | `p_surfacemap`'s SUB | `+2..+7` |
| `NOCTIS-0.CPP:2383-2391` (`loadpv`) | `pvfile`'s TAIL | `+0` |
| BUFFERMODEL §3, §4.0 (segment origin `R*−4`) | every owned SUB but `adaptor`'s | `+4..+7` |

`digit_at`'s six writes are now **counted** (`exp = 6`, `fired = 0`), derived
from what the programme did rather than written by construction -- a build that
never performs the write fails as hard as one that performs it in the wrong
place.

### The half that keeps the fix honest

**O3b.** One unit *further* past `pvfile` -- pad 8, `TAIL+1` -- is still a
violation, and it is asserted to be: `fired = 9, n = 1, at = 271,069`. Without
it, an allowance covering the whole pad would still pass O2 and O3, and the two
jobs would have been merged the other way round. Sabotage S07 widens the TAIL
allowance to 255 and O3b catches it; S06 removes the allowance entirely and O2
catches it. The separation is pinned from both sides.

### Remaining caveat, recorded not hidden

The third allowance entry (every owned `SUB+4..+7`, 32 units across 8 regions)
rests on the model's own segment-origin argument rather than on a line of 1996
source, because the thing it encodes -- `farmalloc` offset == 4 -- is BUFFERMODEL
open item 4 and is *inferred*, not measured. `[MCexp]` is also a single global
counter, so it cannot say *which* allowance was touched. Both are stated in
BUFFERMODEL §4.1 rather than smoothed over.

---

## MAJOR 4 -- Tier 2 for the palette, the LUT and the index page

### What this test can say, precisely

`test_wave5.py` grades the port against `tests/w5spec.py`, a model written from
`NOCTIS-0.CPP:179` (`tavola_colori`), `:1151` (`shade`) and `:166`
(`range8088`) and from nothing else. On the palette pipeline that is a **second
independent implementation**, and with `noctis-harness/fb_pal.py` and `fb_ref.c`
producing the same 768 components and 256 LUT entries there are **three
producers** -- Tier 2. The three port-side sabotages S15 (`(v<<2)|(v>>4)` instead
of `v*4`), S16 (upload from `first` instead of colour zero) and S17/S18 (round
instead of chop, clamp inverted) are each caught.

* **Palette (kind 2): Tier 2.** P1, P2 exact on all 768 components; the
  self-copy form, the upload-from-zero stale band (P4), the negative
  `signed char` filter (P5) and the inverted clamp are each exercised.
* **LUT (kind 3): Tier 2.** P3 exact on all 256 entries; `v*4` sabotaged and
  caught.
* **Index page (kind 1): NOT Tier 2, and this file does not claim otherwise.**

### What remains ungraded -- stated precisely, as instructed

**The index page is Tier 1, not Tier 2.** F1/F2/F3 compare the port against a
Python model of the *same* fixture, exactly, all 64,000 pixels of both pages and
all 64,000 units of the expansion, and a single wrong pixel fails. What they do
**not** do is agree with `noctis-harness/fb_ref.c`, because the two "pinned
page" scenarios are **different fixtures** and no document reconciles them:

```
w5probe   G0..G9: pclear the full segment, (x*y>>4 + 3x + 5y) & 255,
          tinta/escrescenze at 63,996, pcopy, HUD poke, digit_at(65,200,0)
fb_ref.c  steps 1..9: pclear(7), srand(1996)-seeded globes, 32,000 sea texels,
          digit_at('A',104,1), alias 8 at 0x37/0x5B, wrap battery, pcopy, areaclear
```

`fb_compare.py --suite` is where that disagreement lives and it is **not
silenced here**. Reconciling the two fixtures is a document that does not exist
(there is no LINOBUF §6.1 defining a shared page scenario -- §6.1 as written
defines the FBDUMP v2 record set, not a fixture) and it is out of scope for a
corrective wave whose brief was six named defects.

**Alias 8's premise remains Tier 0.** `farmalloc` offset == 4 is inferred from
the `Stick`/`Segmento` split, not measured; BUFFERMODEL open item 4 says how to
measure it (DOSBox-X + `NOCTIS.SYM`) and that rig is not part of this wave. Both
`adapted[63,996..63,997]` being visible pixels and the `SUB+4..+7` allowance
depend on it.

**The raster loop is only reached through the page**, so it inherits the page's
tier.

---

## MAJOR 5 -- the canary cross-check passed regardless

### Fixed

FBDUMP kind 6 v1 was 18 units in which **both** the "expected" and the "actual"
field held `0xA5A5A5A5`, written by construction on both sides. A clean run and
a build with the walker deleted produced a **bit-identical** record. The grader
compounded it by comparing `can[i]` against `can[i+1]` -- two copies of one
literal. That check passed for every build that could ever be made, and it is
the check the brief called out as the reason a check that cannot fail is worse
than no check.

**v2 is 4 units per pad, eleven pads, 44 units, and stores no literal.** Every
unit is read back out of the workspace or produced by the walker; the grader
derives all four from the layout alone (clean read from the zone role, witness
from the witness rule, `fired` from `i+1`, `at` from `padbase(i)+slot(i)`).
`slot(i)` sweeps mod 12 and not mod 16, because `+12..+15` are `SUB+4..+7`, an
allowance that cannot fire by design.

**Two independent walks exist and use different sweeps** -- `work/fbshell.txt`
uses `(7i+1) mod 12`, `tests/w5probe.txt` uses `(5i+3) mod 12` -- so neither is a
transcription of the other, and both avoid `pvfile`'s `TAIL+0` and
`p_surfacemap`'s `SUB+2..+7`.

**Proved by breaking the thing it guards.** Sabotage S03 makes `MEM check pads`
return immediately -- the canary deleted -- and **22 of the 44 units move**. Under
v1 the same edit moved nothing at all. S05 (a zone table derived from `rtab`'s
nine regions) and S07 (the allowance widened) are also caught by C1.

### Still open -- a limit, not a defect

`WITNESS(i) = 0xB0B32000 + 17i + (clean & 255)` folds in the poison the walker
itself wrote, so no single literal can stand in for it -- but **a saboteur who
reads the rule can recompute it instead of loading it**, and such a build
produces a bit-identical unit 1. This is inherent to any cross-check whose rule
is public and it is not claimed to be closed. The load-bearing fields are 0, 2
and 3, and it is those that S03 moves. BUFFERMODEL §4.2 and LINOBUF §6.1 both
record the limit in the same words.

---

## MAJOR 6 -- the shade routine hard-coded its destination

### Fixed

`PAL shade` computes `3*[SHfirst] + [SHdstb]`, and `PAL zero` defaults
`[SHdstb]` to `pal6` so the `tmppal` call sites need no change. The signature is
confirmed at `NOCTIS-0.CPP:1151`:

```c
void shade (unsigned char far *palette_buffer, unsigned first_color,
            unsigned num_of_colors, float start_r, ..., float finish_b)
```

**The brief's "17 of 24" is stale; counted from source it is 14 of 21** -- 3 in
`NOCTIS.CPP:3774-3776` (`tmppal`), 4 in `NOCTIS-0.CPP:5180-5183` (`tmppal`), 14
in `NOCTIS-1.CPP:3050-3086` (`surface_palette`). Two thirds, either way.

Three details the parameterisation deliberately does not lose, recorded in
`fbpal.txt` at the declaration: `tavola_colori` stays hard-coded to `pal6`
(`NOCTIS-0.CPP:179-241` always writes `tmppal` regardless of its
`nuova_tavolozza` argument, which is the *source*); `surface_palette` and
`return_palette` are `char` but every access is through an `unsigned char *`
parameter, so `MEM sx8` must **not** be applied to loads from them; `shade`
never writes `return_palette` in the game, and the parameter is kept general
anyway.

### The correction this wave had to make to its own test

P7 was graded **only** in the separate `w5shade.txt` probe. A sabotage of the
library is applied to a *renamed copy* that `w5shade.txt` does not link -- so
S19, which restores the hard-coded `pal6`, was reported as "the grader never
reached P7". The shade-into-`srfpal6` is now performed in the main probe and
dumped as a third kind-2 record, so P7 is graded from the main dump and S19 is
caught (45 of 48 components move, and P1 fires too because `pal6` is clobbered).
`w5shade.txt` is kept as **P7b**, whose result is a *build failure*: a library
with no `[SHdstb]` cannot compile it, and that failure is the finding.

`srfpal6` and `retpal6` are no longer dead weight: `srfpal6` is written and
graded on every run.

---

## What the test file itself changed

| | Wave 5 | Wave 5b |
|---|---|---|
| checks | 109 around a rejected model | 156, PASS |
| unbreakable checks | 1 (`O1b`, comparing two copies of one literal) | 0, and "every graded check is proved breakable" is itself a check |
| XFAILs | 3, all asserting defects this wave was told to fix | 2, both for things genuinely not closed, each with the boundary |
| sabotage builds | 13 | 23 |
| perturbations | 37 | 59 |
| servo evidence | 6 single questions, then XFAILed | 9 synthetic origins × 85 firings × 3 legs, with the ORIGINAL estimator as the control |
| class A | a size, and a claim | a mask per truncation point, two deltas, two sabotages |
| the canary | 18 units of one literal, both sides | 44 units, no literal, proved by deleting the walker |

**Checks removed as unable to fail:** `O1b canary table dumped clean`
(`can[i] == can[i+1]`). Its replacement is C1.

**Checks re-founded because their premise had changed:** T1 (piecewise across
the servo schedule), T12 (a second clock instead of the servo's own estimate),
O2 and O3 (counted, not flagged), O5 (narrowed to the size claim only, with the
text saying outright that a size cannot fold an index).

**Three sabotages that revealed genuine holes while this wave was being
written**, each of which is now covered rather than dropped:

* **S13** (clamp step floor removed) changed nothing, because no scenario drove
  cpms below 100 -- rule e was **unexercised**. Fixed by horizon scenario 8, a
  60 cpms counter. Now H6.
* **S14** (band unsigned) changed nothing, because nothing drove a negative
  window -- the SIGNED band was **unexercised**. Fixed by the band battery, six
  windows including a −86,395,000 ms midnight straddle. Now H5.
* **S08** (mask deleted) was caught only by `cirrus`, because `spot`'s offset was
  masked twice. Fixed by handing `MEM seg addr` the raw offset. Now M2 and M3
  are separately breakable.

---

## For the coordinator

`tests/run_all.py` was **not** edited (entry 17 is already registered and
another wave owns that file), so its docstring is now stale in three places: it
says test_wave5 builds "thirteen" broken variants (23), that "Three of its
checks are XFAIL" (2), and it points at "BUFFERMODEL.md section 10" for the list
(still correct, but the list has changed). Worth a one-line fix when that file
is next free.

`work/fbshell.txt`, `work/fbmain.txt`, `work/fbsrv.txt` and
`noctis-harness/fb_compare.py` are the *other* implementer's artifacts and were
not touched by this wave; `fb_compare.py --suite` still reports the index-page
disagreement described under MAJOR 4, and that is the correct behaviour for a
disagreement nobody has reconciled.
