# WAVE4_NEARSTAR -- star identity and planetary system generation

Wave 4's settled answer, written down 2026-08-05 after the implementers, the
adversarial review, the QA pass and the regression test.

Every number in sections 2, 3 and 4 is recomputed on every run of
`tests/test_nearstar.py` (suite entry 16) from the galaxy hash, the 1996
STARMAP.BIN and the 1996 DL.EXE captures. Nothing there is copied forward from
a stored artifact; if one of those figures stops being true, that test fails
and names the check. A handful of figures elsewhere come from
`noctis-harness/ns_grade.py`, which the suite does **not** run; each of those
is attributed where it appears, so nobody mistakes it for something the
regression run keeps honest.

Where the wave did not settle something, this file says so in those words.

---

## 0. The one-paragraph version

`prepare_nearstar` is one seeded stream of Borland `rand()` calls, and the
whole problem is **how many draws it takes and in what order**. The port
reproduces that stream exactly: it agrees bit for bit with two independent
references on all 100 fields of 5,540 systems, reproduces the star class of
every player-named record in the 1996 catalogue, reproduces the stored
identity double bit for bit, never generates fewer bodies than players have
named, and reproduces all 4,365 owner/moon-id constraints the 1996 executable
itself printed. **Geometry is not ported and is not graded** -- the wave scoped
it out deliberately, and section 6 says exactly what that costs.

---

## 1. The two expressions, which are not the same expression

```c
nearstar_identity = star_x/100000 * star_y/100000 * star_z/100000;   // :4078
srand ((long)star_x%10000 * (long)star_y%10000 * (long)star_z%10000); // :4080
```

**The identity** is `double` arithmetic on the x87 at control word 133Fh, five
operations with ONE store and nothing spilled in between -- Wave 3's contract,
`docs-notes/FLOATPOLICY.md`. It is a *chain*: `x`, divide, multiply by `y`,
divide, multiply by `z`, divide. Graded against the binary64 the 1996 file
stores: **exact on every record**.

**The seed** is `long` arithmetic and shares nothing with it. `*`, `/` and `%`
sit at one precedence level and associate **left to right**, so the expression
is

```
((((x % 10000) * y) % 10000) * z) % 10000
```

-- a *chain of remainders*, not a product of three remainders. The running
value is a 32-bit `long` and it **overflows on most real stars**; that wrap is
part of the answer, not an accident, and the reference is compiled `-fwrapv`
for that reason. C's `%` truncates toward zero, which matters because the
normal case here is negative coordinates.

The natural misreading -- `(x%10000) * (y%10000) * (z%10000)` -- is a different
number on essentially every star. Both readings are scored in
`noctis-harness/ns_catalogue.py` (run by `ns_grade.py`, not by the suite): the
left-to-right one is never refuted and the flat product is refuted on 73 of
176 class-2/7 systems.

`starnop()` (:4047-4057) uses the *same* seed expression at :4051 and consumes
three draws of its own. It runs **before** `prepare_nearstar` and the draw
counters are reset in between, or its draws pollute the accounting.

---

## 2. The draw table

`random(n)` is **one** `rand()` for every `n`, including `n == 0` and `n < 0`:
`rand` has exactly one caller in NOCTIS.EXE, so `random()` was compiled as a
real out-of-line function and the call is not predicated. `zrandom(r)` is
**two**, first draw minus second (Wave 2: left to right).

Site ids are NOCTIS-0.CPP line numbers.

| phase | lines | draws | shape |
|---|---|---|---|
| prelude | 4082 | **1** | `random(class_planets[class]+1)` → `nop` |
| **A** | 4086-4107 | **12 per planet**, 13 on class 8's else branch | 4088, 4089, 4090×2, 4091×2, 4092, 4093, 4094×2, 4094(1000), then the type draw: `random(planet_types)` at 4096, or at 4098 `random(2)` and -- when that came out 0 -- a 13th at 4103 |
| **B** | 4111-4115 | **3 iff class == 0**, else 0 | three `random(4)`; nothing short-circuits, and the writes to `p_type[2..4]` happen whether or not `nop` reaches them |
| **C** | 4120-4139 | **unbounded**, and only for classes 2, 5, 9, 11 | `while` loops re-rolling `random(10)`; class 7 assigns type 9 and draws nothing. The port's own source header records maxima of 109 (class 9) and 78 (class 11) iterations on one star; the graded corpus below reaches 66 |
| **D** | 4145-4168 | **0..2 per planet** | 4148 `random(8)` for type 0; for type 3, 4152 `random(4)` fires only when `2<=n<=6` **and** class != 0 (`&&` short-circuits), then 4153 `random(2)` only if the whole guard came out true; 4161 `random(2)` for type 7 with `n<7` |
| **E** | 4172-4260 | **0 for classes 2, 7, 15** (`goto no_moons`, and `nob == nop`); otherwise a moon-count draw per planet plus 10 base draws per moon | 4183/4186 the count; per moon 4194, 4195×2, 4196×2, 4197×2, 4198, 4199, 4201; plus up to four extras at 4213, 4214, 4238, 4255. The `nob+t>80` clamp removes **bodies, never a draw** |
| **F** | 4300-4341 | **exactly 4 × nob** | two `zrandom(100)` per planet (4308, 4310) and two per moon (4331, 4333) |
| **G** | 4345-4361 | **exactly 2 × nop** | 4348 `random(3)`, then 4354 `random(5)` or 4358 `random(2)` |
| **H** | 4363-4369 | **0** | `search_id_code` over STARMAP.BIN; reads an external file, draws nothing |

**42 distinct draw sites.** The test replays the class-override block through
the C reference's per-draw ledger -- 360,734 draws over 1,440 systems -- and
requires every one of the 42 to be reached and no site outside the list to
appear. A comparison that never reaches a site proves nothing about it.

### Two behaviours a tidy port silently repairs. Both are required.

1. `:4213  if (n > 7 && random(c)) r = 7;` fires on the **first** moon too,
   where `c == 0`. `random(0)` still calls `rand()`. Skipping it because "the
   answer is always 0" desynchronises the stream.
2. `:4232  if (n > 7) r = 7;` runs **before** the `:4238` test, which can then
   set `r = 5` over the top of it.

And one that is **not** repaired: `nearstar_p_moonid[q]` is written only inside
the moon loop, so a planet's slot keeps whatever the previous star left there.
That is real behaviour, it is invisible, and the interchange format forbids
grading the field for `k < nop`.

### The counts, measured

The graded corpus is 4,100 real stars of DL.EXE's own box with phase H on,
followed by 12 × 120 class-override rows on the same coordinates: 5,540
systems. The test recomputes this table from the port's own counters on every
run and prints it as "the draw table".

| phase | total draws | max on one system | systems > 0 |
|---|---|---|---|
| prelude | 5,540 | 1 | 5,540 |
| A | 302,181 | 240 | 4,085 |
| B | 4,770 | 3 | 1,590 |
| C | 9,583 | 66 | 684 |
| D | 6,652 | 10 | 2,900 |
| E | 588,548 | 747 | 2,853 |
| F | 320,424 | 320 | 4,085 |
| G | 50,254 | 40 | 4,085 |
| **total** | **1,287,952** | **1,357** | mean **232.5** per system |

The draw budget is 100,000 per system; the worst system used 1,357 of it,
1.36%. 1,455 of the 5,540 systems take no draws past the prelude, because
`nop` came out 0 -- always for a class-6 star, which has no planets by table,
and sometimes for any other class. The 80-body clamp fires on 119 systems.

---

## 3. What is graded, and by what

Everything is recomputed each run. The corpus is re-swept from the galaxy hash
over DL.EXE's own 100³-sector box and re-paired against STARMAP.BIN under the
single-candidate rule (a record matched by more than one sector, or a sector
matching more than one record, is **discarded unexamined** -- 42 of them), so
the grader can never be measuring its own chooser.

| leg | oracle | result |
|---|---|---|
| TRANSCRIPTION | ns_ref.c (x87, source-ordered) and ns_spec.py (Fractions, draw-table-ordered) | **3/3 sides agree on all 100 fields of all 5,540 records** |
| CLASS | the `S` tail of a 1996 record: `srand(chop(identity)); random(12)` | **4,099 / 4,099** (1 placeholder record excluded and counted) |
| IDENTITY | the binary64 stored in the record | **4,100 / 4,100 bit-exact** |
| NOB | every player-named body index must exist in the model | **0 violations over 2,450 systems**, and the highest charted index lands **exactly** on `nob` on 1,238 of them |
| CLASS6 | `class_planets[6] == 0`, so a class-6 star has no body | 689 catalogued class-6 stars, **0** named and **0** modelled |
| PHASE H | `nearstar_labeled` against an independent recount of the catalogue | **4,100 / 4,100**, 16,307 labelled bodies |
| DRAW SITES | the C reference's per-draw ledger | all **42** sites reached, none outside the list |
| DL | the 1996 executable's own stdout, 122 captures | **4,365 / 4,365 owner/moon-id constraints** |
| DRAW AUDIT | ten invariants read out of NOCTIS-0.CPP by hand | **0 violations over 5,540 systems** |
| coordinates | :4080's three `(long)` chops are the identity only if every coordinate is an exact integer in int32 | 12,300 checked, **0** not exact |

Every leg carries a control that must fail, and does:

| control | result |
|---|---|
| class tags permuted across records | CLASS collapses to 739/4,099 = 18.0% |
| one flipped bit in the last place of the identity | IDENTITY 0 / 4,100 |
| `nob` reduced by one | 1,238 NOB violations |
| the same shrink, seen by phase H independently | 1,239 systems disagree |
| a hand-built record satisfying all ten audit invariants, then one deliberate violation of each | the base passes; all ten violations are flagged **by name** |

One caveat on the PHASE H leg, because it is easy to overread. It recounts
using the port's **own** `nob`, so it grades the port's `search_id_code` -- the
binary64 add, the ±1e-5 window, the key map, the two malformed records -- over
16,307 real bodies, and it does **not** independently constrain `nob`. That
job belongs to the NOB leg above, which is an external bound, and to the
three-way comparison.

---

## 4. Breaking it on purpose

Seven single-edit sabotages of the port's own draw sequence, each built with
the real compiler, run over the real corpus and graded by every leg. All seven
compile -- they are wrong, not broken.

| break | phase | edit | counts moved | records changed | DL score | caught by |
|---|---|---|---|---|---|---|
| `adrop` | A | the `random(1000)` at :4094 removed | 3,837 | 4,085 | 1,354 / 4,365 | refs, audit, catalogue, dl |
| `bclip` | B | phase B skipped when `nop <= 4` | 561 | 561 | 4,365 / 4,365 | refs, audit, catalogue -- **and `dl` since Wave 6**, 4,597 / 4,707 on the extended capture set |
| `cadd` | C | one spurious draw per class-9 re-roll | 242 | 243 | 3,663 / 4,365 | refs, catalogue, dl |
| `d4152` | D | the short-circuited `random(4)` at :4152 removed | 280 | 345 | 3,894 / 4,365 | refs, catalogue, dl |
| `e4213` | E | `random(c)` at :4213 skipped when `c == 0` | 1,030 | 1,040 | 3,970 / 4,365 | refs, catalogue, dl |
| `eorder` | E | the :4201 type draw moved from stream position 7 to 2 | 594 | 2,549 | 3,842 / 4,365 | refs, catalogue, dl |
| `gadd` | G | one extra draw per planet | 4,085 | 4,085 | 4,365 / 4,365 | refs, audit |

`refs` is the comparison against the reference NSTOPO recomputed the same run.
STARMAP.BIN alone catches six of the seven; DL.EXE alone catches five; `refs`
catches all seven. Three rows of that table are worth reading carefully.

**`eorder` takes the same number of draws at the site it moves, and the counts
still move** -- on 594 systems. That is not a bug in the classification: the
draws at :4238 and :4255 are conditional on the type value that :4201 lands
on, so a pure reordering propagates into a count change downstream. It is a
useful demonstration that "the counters agree" is a weaker statement than "the
stream agrees".

**`gadd` is invisible to both 1996 artifacts.** The catalogue is clean on
every leg and DL.EXE scores a perfect 4,365 / 4,365. This is structural, not a
weakness of the harness: phase G is the last drawing phase, its values reach
only `p_ring`, and every later `rand()` user in the original re-seeds first
(NOCTIS-1.CPP:1975, 2052, 2642, 2796, 3171, 3225). It is caught by the
reference comparison and by the per-phase counter invariant `G == 2 × nop`.
That is why `r12..r19` are **load-bearing evidence in this port and not
diagnostics**, and why the test asserts the invariant table rather than only
comparing implementations.

**`bclip` is invisible to DL.EXE**, for a duller reason: it only touches
class-0 stars whose `nop` is 4 or less, and the 122-star capture set does not
happen to contain one. That is a limit of the capture set's size, not of the
oracle, and it is exactly why the test requires an aggregate (five of seven)
rather than demanding DL catch everything.

> **CLOSED by Wave 6, 2026-08-05.** The prediction in that paragraph was
> tested by taking more captures rather than by arguing. 88 further DL.EXE
> captures were chosen for class-0 stars with small `nop`; against the
> extended **210**-capture set the same `bclip` sabotage loses **110 of
> 4,707** constraints (97.66%), first mismatch `JUNOVA` body 6 `MONNEZHA`,
> want owner/moonid (3,0), the sabotaged port says (2,1). The unmutated port
> still scores 4,365/4,365 and 4,707/4,707. `bclip` was therefore a gap in
> the CAPTURE SET, exactly as recorded, and not in the method.
> `tests/test_geometry.py` section 7 rebuilds both ports with the real
> compiler and re-grades both sets on every run: it requires `bclip` to be
> still invisible to the 122 and caught by the 210, so neither half of the
> statement can rot. **`gadd` is unaffected** -- it remains invisible to both
> 1996 artifacts for the structural reason given above, and Wave 6's coverage
> sweep confirms it moves 0 charted bodies in either capture set.

The audit is an honest partial. It carries an *exact* invariant only for the
prelude and phases A, B, F and G; phases C, D and E have unbounded while-loops
and short-circuits, so only range invariants exist there and the audit cannot
see a sabotage inside them. The test states that per break instead of claiming
uniform coverage: each break must be caught by every leg that can be *argued*
to see it, plus the aggregate requirement that STARMAP.BIN alone catches at
least five of the seven and DL.EXE alone catches at least five.

---

## 5. What is proven

* The **seed expression** is left-to-right. Confirmed against an independent
  gcc build of the verbatim C and, behaviourally, by the catalogue: the
  left-to-right spelling is never refuted while the flat three-remainder
  product, the x/z swap and the no-modulus spelling are refuted 73, 71 and 77
  times respectively out of 176 class-2/7 systems, against a random-seed
  control that is refuted about 82 times. (Those four figures are
  `ns_catalogue.py`'s, via `ns_grade.py`; the suite's own SEED evidence is
  indirect -- a wrong seed gives a wrong `nop`, which the NOB and DL legs
  catch.)
* The **identity** reproduces the stored 1996 double bit for bit on every
  record in the corpus, computed at 64-bit precision on an unspilled x87
  chain. A one-ULP flip of the result scores zero.
* **Draw accounting is externally constrained, phase by phase**, and the
  strength differs by phase -- demonstrated, not asserted:
  phases **A, C, D and E** by *both* 1996 artifacts, in count and in order;
  phase **B** by STARMAP.BIN alone at the time of this wave -- by DL.EXE too
  since Wave 6 extended the capture set to 210 (section 4);
  phase **G** by neither (section 4), only by the counters and the references.
  All seven sabotages disagree with the references.
* Phase **A is 12 draws per planet**, and 13 on class 8's else branch. (The
  Wave 4 brief's reconnaissance figure of "~10, 11 for class 8" is wrong; the
  port, both references and the delivered records all say 12/13, and the
  audit invariant is checked on every record of every run.)
* **Five of the eight phases have an exact closed form** and all five hold on
  every record: prelude 1, A 12 (13) per planet, B 3-or-0, **F exactly 4 per
  body**, **G exactly 2 per planet**. C, D and E do not -- unbounded
  while-loops and short-circuits -- and only range invariants exist there.
* Every coordinate in the corpus is an exact integer inside int32, so :4080's
  three `(long)` chops are the identity function and the seed never goes
  through `__ftol`. Checked, not assumed, at corpus-build time.

---

## 6. What is NOT covered -- say this out loud

* **GEOMETRY IS OUT OF SCOPE.** The wave scoped it out. What is ported is the
  **topology**: `nop`, `nob`, and every body's type, owner and moon id, plus
  the draw sequence. The eleven float-argument draw sites take their draws and
  **discard the values**. `p_orb_seed`, `p_tilt`, `p_orb_tilt`, `p_orb_ecc`,
  `p_ray`, `p_orb_ray`, `p_orb_orient`, `p_ring` and `key_radius` are not
  computed by this port at all, so no test result above is evidence about
  them. The site registry is pinned at exactly eleven sites / 17 draws so
  that the day geometry arrives it arrives as a deliberate change that fails
  the regression test first.

  This is *licensed*, not merely tolerated: every draw whose result selects a
  branch, a count or a type takes an **integer** argument, and `random(n)`
  consumes exactly one `rand()` for every `n`. So the topology is provably
  independent of every float value in the routine --
  `ns_diff.py --jitter` perturbs `nearstar_ray` by 1e-7 and requires the
  topology, the draw counts and the identity not to move.

  > **Wave 6 status, 2026-08-05.** Still true of *this port*: the eleven sites
  > still discard their values and `tests/test_geometry.py` section 6 keeps
  > the registry pinned at eleven sites / 17 draws in `work/nstopo.txt`. What
  > changed is that the values now exist in two independent **references** --
  > `noctis-harness/geo_ref.c` (80-bit x87) and `geo_spec.py` (exact
  > rationals) -- which agree bit for bit on 22,768 values over 200 systems.
  > Read that as transcription evidence and nothing more: **planetary
  > geometry is still UNGRADED against the 1996 machine**, because no 1996
  > artifact contains a radius, orbital radius, tilt, eccentricity or ring
  > value. See docs-notes/OPENITEMS.md.

* **The float-to-int cast boundary was UNSETTLED here; Wave 6 settled it, and
  `NsIdentChop16` turns out to have been right.** What this wave could say
  was only this: the catalogue **cannot** separate the two candidates --
  chopping the live extended value and chopping its binary64 rounding give a
  **different** seed on **0 of 4,099** records (measured by
  `ns_catalogue.py`, not by the suite) -- and the CLASS leg ranks chop against
  floor, ceil and nearest and nothing finer. So the boundary was closed here
  by construction and by measurement, not by an oracle, which is a different
  and weaker thing.

  > **SETTLED by Wave 6, 2026-08-05, from the shipped machine code.**
  > Borland's `__ftol` in `NOCTIS.EXE` reads nothing from its parameter area,
  > forces the rounding control to 11 (chop) with an `OR 0Ch` that leaves the
  > precision control alone, and does `fistp QWORD` on `st(0)`. Of the 274
  > `__ftol` call sites in the image, 130 are fed directly by an x87
  > instruction and **none** of those stores the value first. So a cast site
  > is `chop(live extended)`: `NsIdentChop16`'s reading is the original's.
  > FLOATPOLICY.md §3.3 carries the decode; `tests/test_geometry.py` section
  > 1 re-derives it from the binary every run and breaks itself four ways to
  > show the checks can fail. What is still open is only what *`genfp`* can
  > emit, which is a code-generator limitation, not an unknown.

  Additionally, the catalogue's `S` tail was written by NOCTIS.CPP:1244-1257,
  which assigns the expression into the `double ap_target_id` **first** and
  only then calls `srand` -- a chop of a *stored* binary64. So the leg cannot
  even be said to grade the live-extended site directly.

* **Phase G's draw count is invisible to every 1996 artifact** (section 4).
  It is held only by the port's own counters and by the two references.

* **The NSIN seed override's scope over `starnop`.** The port applies an NSIN
  seed override to `starnop()`; the two references do not. Both readings are
  defensible and the interchange spec does not choose. The test **pins the
  disagreement** rather than avoiding it: with a seed override the three sides
  differ on field `r7` and on **nothing else**, and the graded corpus uses no
  seed override at all, so no other number in this document is touched by it.

* **Rare branches on override rows are graded by transcription, not by an
  oracle.** The class-override block reaches the branches real coordinates
  rarely produce -- the 80-body clamp (119 systems in the graded corpus),
  class 8's type-10 else branch, class 9's long phase C -- but those rows have
  no catalogue record and no DL capture behind them, so what grades them is
  the C and Python references agreeing with the port. That is evidence about
  transcription. The 4,100 real rows are what the 1996 artifacts grade.

* **The class-override sweep is not a seed sweep.** Because the seed override
  is off the table (above), the sweep varies the class over 120 real
  coordinates rather than over all 65,536 seeds. The harness's
  `ns_corpus.py --synthetic` does sweep seeds and `ns_grade.py` runs it across
  12 classes × 4,096 of them -- but only between the two references, for the
  same reason.

* **`nsrun` validates the NSIN payload length against its header.** The
  delivered `nrfilebytes` guard rejects an NSIN whose header claims more
  records than the file holds, before any fictitious records can be emitted.
  `tests/test_geometry.py` section 8 confirms an intact eight-record control,
  refusal of a header-8/payload-5 input, and absence of stale `nstopo.bin`.

* **The DL captures are not re-captured on every run.** They are DL.EXE's own
  stdout, taken under DOSBox-X and reproduced byte-identical in a second
  session, and they are read-only. Re-capturing them requires opening a
  DOSBox-X window, which a routine regression run must not do. They are an
  oracle of the same kind as STARMAP.BIN -- an artifact of the 1996 program --
  and not a stored expectation of ours.

---

## 7. Where the code is

| file | what it is |
|---|---|
| `work/nstopo.txt` | `starnop` and `prepare_nearstar`, phases A-G, topology only |
| `work/nsident.txt` | the identity chain and `NsIdentChop16` |
| `work/nsseed.txt` | the :4080 remainder chain |
| `work/nsrng.txt` | the draw counters and the `NsDrawOnly` / `NsZDrawOnly` sites |
| `work/nslabel.txt` | phase H: `search_id_code` over STARMAP.BIN |
| `work/nsrun.txt` | the driver: NSIN in, NSTOPO + nsdiag out |
| `noctis-harness/ns_ref.c` | reference A: source-ordered C, real x87, build `-fwrapv` |
| `noctis-harness/ns_spec.py` | reference B: draw-table-ordered Python, exact Fractions |
| `noctis-harness/ns_grade.py` | the reference-side grading run, end to end |
| `tests/test_nearstar.py` | suite entry 16 -- the regression test this file describes |
| `tests/nsdrive.py` | its sandbox, corpus and the seven sabotages |
| `tests/nsspec.py` | its catalogue referee and the draw-audit invariants |
