# Wave 7a - surface(), the orbital globe texture

`surface()` is NOCTIS-0.CPP:4766-5196 (niv-lr `src/noctis-0.cpp:4178-4752`). It builds a
360x180 albedo map in `p_background` and a 180x90 cloud overlay in `objectschart`, then a
64-entry palette block. Its output is a 64,800-byte artefact, which is what Wave 6b's four
sphere renderers consume - so this wave closes the loop from generation to pixels.

Scope is deliberately narrow. `build_surface()`, the ground-level terrain system, the sky
and SURFACE.BIN are Wave 7b and are not touched here.

Test: `tests/test_surface.py` - standalone, and to be registered in `tests/run_all.py`'s
`TESTS` by the coordinator (that file is not this wave's to edit, and its `unregistered()`
guard will refuse a full suite run until the entry exists, which is what it is for).
Runner: `tests/w7arun.ps1`.
Sandbox: `tests/gen/w7a`, rebuilt from source on every run.

---

## 1. The oracle situation, stated plainly

**There is no 1996 artefact in this project and this wave does not have one.**

Exactly one distinct `NOCTIS.EXE` exists on this machine - sha256 `5e64d532091c9be1...`,
215,744 bytes, three copies. It is **Noctis IV+ Release 2.3**, a community fork. The ten
capture files under `tests/gen/recon_w7a/out/` were lifted out of *that* binary's guest RAM
by recon C under DOSBox-X. Every row this wave reports as EXACT therefore means
"byte-exact against NIV+ Release 2.3", never "against the 1996 binary".

The argument that NIV+ 2.3's `surface()` is still vanilla's is:

* documentary - no `#ifdef` around any of it, no fork edit marker, and `WEIRDDOSHILLS`
  (the community "surface fix" flag) is `#define`d at `defs.h:14` and referenced by no
  `.CPP` in the tree (it survives only in the compiler's `NOCTIS.SYM`); plus
* one confirming datum - the type-3 land-noise site reads `add es:[di], bl`
  (NOCTIS-0.CPP:4918), not `mov`.

Verified here rather than quoted: three copies of `NOCTIS.EXE` exist under
`C:\programmieren` (`tests/gen/recon_w5c/dos/modules`, `tests/gen/recon_w7a/dos/modules`,
`noctis/niv-plus/modules`) and all three hash to the same `5E64D532091C9BE1...`, 215,744
bytes. There is no second binary.

That is not a byte-level diff against a stock 1996 or 2003 executable, because there is
nothing on this machine to diff against. Read every "EXACT" below with that qualifier.

**noctis-iv-lr is disqualified as an oracle here.** PORTPLAN's oracle-trust table records
four confirmed LR divergences inside this one function; three of them are in the type-3
land noise alone and section 4 grades all three directly rather than trusting either side.

**How this compares to the earlier waves.** Wave 3 was graded by the shipped STARMAP.BIN;
Wave 4 by DL.EXE's own output over 4,365 records. This wave's evidence is one
binary-derived artefact per capture (ten of them, one per planet type 0..9), three
independent implementations agreeing on all of it, and a per-stream draw audit. That is
weaker than Waves 3 and 4 had, and nothing in this document should be read as claiming
otherwise.

---

## 2. The three implementations

| side | source | derived from | rebuilt per run |
|---|---|---|---|
| `lino` | `work/su*.txt`, `work/fp/*.txt` | the DOS text; **the deliverable** | yes, `lino_build.ps1` into `tests/gen/w7a`, run poll-and-kill |
| `spec` | `noctis-harness/su_spec.py` | the DOS inline assembly, x87 modelled with exact rationals | yes (source) |
| `cref` | `noctis-harness/su_ref.c` | the same DOS text, separate pass, hardware x87 at CW 133Fh | yes, `gcc -O2 -fno-fast-math` |

Nothing is graded against a stored `.bin`. The only thing read from disk and not rebuilt is
the capture set, which is the one thing no code in this project produced. The test hashes
all 58 source and oracle files it reads before and after and fails if any of them moved.

All three are driven from **one** fixture, emitted in both corpus formats by the test
itself, so a case cannot exist on one side and not another and no side can be handed a
different `seedval` from another. 24 cases: the 10 captures plus 14 synthetic cases that no
capture covers (both moons, colorbase 255, type 10, case 4's `r>20` branch, `knot1==1`, the
negative-fractional seedval that makes `SEEDTRUNC` visible).

---

## 3. EXACT - anchored to the NIV+ 2.3 binary's own buffers

Ten captures, one per planet type 0..9, all ten maps mutually distinct.

* **`p_background`, 64,800 bytes** - byte-exact on all ten, from all three implementations.
* **`objectschart`, the 32,400-byte prefix** - byte-exact on all ten, all three. (The
  capture file is 40,000 bytes; the comparison is a *prefix* match, not a whole-file hash.
  The manifest's `objectschart_sha256` is the digest of the whole 40,000, so it cannot be
  the digest of the 32,400 that are graded.)
* **the 64 palette triples** at `tmppal[3*colorbase ..]` - byte-exact on all ten, all
  three, against the palette read back out of the game's own gallery BMP.
* **the 752 bytes past the map** (`64,800..65,551`) - zero in the capture, in the spec's
  segment and in the lino dump. A 32-bit `vptr` in `crater()` would splatter into them.
* **the cross-seeding bridge that reaches the map** -
  `fast_srand(seedval * 10)` / `seed = fast_random(0xFFFF)` / `srand(seed)` at
  NOCTIS-0.CPP:4810-4816, and the repeat `srand(seed)` at :4844. The seed reaches all 64,800
  bytes through `rndpat`, so a wrong seed is a wholly wrong map and the artefact pins it.
  (The *other* bridge in the function, `fast_srand(seedval + 4112)` at :4784, only feeds
  `rtperiod` and is BOUNDED - section 7. The third one the plan lists,
  `srand(fast_random(0x7FFF))`, is at NOCTIS.CPP:3672 inside the class-8 variable-star
  colour path and is **not in `surface()` at all**; it is out of this wave's scope.)
* **vanilla's type-3 ADD** - see section 4.
* **the terminator's shape** - see section 5.

Per-stream totals over the ten captures: **52,992** `ranged_fast_random` draws and
**241,408** Borland `random()` draws. Over the whole 24-case fixture: 106,308 and 579,120.

---

## 4. The type-3 divergence, graded three ways

PORTPLAN names three departures at niv-lr's land-noise site. The test implements each as a
separate negative control on the spec side (build-free, so it runs even under `--quick`)
and measures what the capture says. The control with all three flags off is checked to
reproduce the unmodified spec first, because a negative control that is broken in its own
right "detects" everything.

| LR's choice | bytes wrong vs the capture, of 64,800 |
|---|---|
| ASSIGN the noise instead of ADDing it | **53,373** |
| clamp with a BYTE store (losing the word store's zeroing of the next pixel) | **54,221** |
| advance the noise register on the SEA branch too | **47,023** |

All three are individually distinguished. The same ASSIGN defect is then reinstated in the
C reference and in the lino port and rebuilt; both move only the type-3 capture, by the
same 53,373 bytes.

This matters beyond aesthetics: the albedo at the landing site sets the scenario type,
which sets all of Wave 7b's ground terrain.

---

## 5. The terminator, and the constants shared with Wave 6b

`plwp` is an **input** - `cplx_planet_viewpoint()` is Wave 8 - recovered per capture by
exhaustive search over all 360 values against the captured bytes. So "the band lands in the
right place" is circular and is not claimed. Its **shape** is not circular:

> Over a 5 x 5 x 4 = **100-triple** search space of (offset, arc, rows), exactly one triple
> turns the spec's pre-terminator map into the **captured** bytes on all seven capture types
> whose post-terminator retouches are a no-op, and it is **(35, 130, 179)**.

One capture (`jrot_b01_t0`, type 0) also accepts `rows=180`, because its 180th row's band
bytes are already below 4 and a further `shr 2` is invisible there. The intersection over
the seven is still the single triple.

Cross-wave: `sp_spec.terminator_constants()` and `sp_spec.surface_band()` - Wave 6b's own
code, written for `glowinglobe`'s crescent - give the same `term_start`/`term_end`, the same
arc of 130, and reproduce the spec's post-terminator map byte for byte from its
pre-terminator map on every case where the two marks bracket only the band. The lino port's
own `term_start`/`term_end` agree as well. Change 35 or 130 in either place and the crescent
stops matching the band burned into the texture.

---

## 6. The two interleaved streams

`ranged_fast_random` owns the type switch (used nowhere else in the game); Borland's
`random()` owns the modular painters called from inside it. Getting either stream's draw
*count* wrong moves the other's *consumption point*, so a bug in one corrupts the visible
output of both. What is graded:

* **totals** agree `lino == spec == cref` on every case;
* **per phase** - PROLOGUE, RNDPAT, MERGE, TERMINATOR, POST, PALETTE - both draw counters,
  both stream **value** hashes and the map hash agree `lino == spec`, 137 phase records.
  Counts, values and buffer are separable evidence and the sabotages show all three axes:
  `CFRACDRAW` moves a count, `LRNDPATUNS` moves the map hash with *no* draw consumed at all,
  and `LSUBORDER` moves neither - see section 9.
* **a closed form** from `su_ledger.py` predicts both counters on all 23 non-type-10 cases.
  `crater_juice`'s brtl term is **derived** here from `(r, crays, how many ray draws came
  back zero, 90 angles)` rather than echoed from the observed delta the way
  `su_ledger.predict_switch()` does it - see section 10, item 4.
* six painter-level draw injections (crater_juice +1 brtl, crater_juice +1 fast, fracture
  +1, atm_cyclon +1, randoface +1, palette +1) each make the predictor disagree on every
  type that reaches them. The type set beside each injection is read off the switch, and a
  type that did not actually reach the painter is reported as not reached rather than
  quietly skipped.

`RENORM` is excluded from the per-phase comparison on purpose: the spec marks it *before*
the type-3 `rfr(2)` that picks `lssmooth` or `ssmooth` and the lino port marks it *after*, so
on type 3 the two fast counters legitimately differ by one there. MERGE, the very next mark,
agrees on every case, which is what shows that difference is a label and not a draw.

---

## 7. BOUNDED - agreement without a binary anchor

* **The 14 synthetic cases.** Three-way agreement only. No artefact exists for colorbase
  255, type 10, the two moons, case 4's `r>20` branch or the seed flip. They are labelled
  synthetic everywhere and claim nothing about the DOS binary. Their value is coverage: the
  lino port previously had *none* outside the ten captures.
* **`nearstar_p_rtperiod`.** The only observable of the first bridge,
  `fast_srand(seedval + 4112)`, which is reseeded before anything touches the map. Compared
  spec-to-cref-to-lino, never to the binary. The `CSEEDTRUNC` sabotage measures exactly how
  little that bridge is pinned: truncating `seedval` before the `+4112` moves `rtperiod` on
  2 of the 24 cases and moves **no** capture map at all, so without the synthetic corpus it
  would be invisible.
* **`nearstar_p_rotation`.** `lino == spec` only; the C reference is handed `secs = 0` and is
  not asked. On 5 of the 10 captures a flooring `%` would give a different answer from the
  truncating one, and the port gives the truncating one - so the row is live, not decorative.
* **The four secs-dependent captures** (types 2, 3, 5, 6). See section 8, N2.
* **The two `seedval` derivations.** `su_seed.chain()` builds the product on the x87 stack
  with one rounding (Wave 3's no-spill discipline); `work/su-mkcorpus.py` builds it in plain
  binary64, spilling at every step. The raw doubles differ on **4 of 10** captures. Only two
  numbers derived from `seedval` can reach the map - `__ftol(seedval+4112)` and
  `__ftol(seedval*10)` - and those agree **10 of 10**. So the Wave 3 no-spill discipline is
  *unexercised* by this wave: it is not wrong here, it just does not bite.

---

## 8. NOT GRADED - item by item

| # | item | why |
|---|---|---|
| N1 | `cplx_planet_viewpoint` / `plwp` | Wave 8. An input here, recovered from the capture. Section 5 grades the shape instead. |
| N2 | the elapsed guest seconds for types 2/3/5/6 | A declared unknown, fitted per capture against the artefact. Those four captures are CONSISTENT-with, not PREDICTED-by, the oracle. The other six touch `secs` nowhere. The two implementers fitted it independently and landed on *different* integers inside the same invariance plateau (`lane_b00_t2`: 556,778,145 vs 556,778,335, in a plateau ~19.5 guest seconds wide; the narrowest plateau measured is 0.78 s on `jrot_b00_t6`). One value is used for all three sides rather than two being compared, because equality would be false and both are right. |
| N3 | the second `srand(seed)` at :4844 | Nothing between the two calls draws and Borland's `srand` is idempotent, so **no** check can distinguish them. Both are executed because the source executes both. |
| N4 | type 10's scalars | In DOS the early return leaves the `nearstar_p_*` globals at their previous values; spec and cref reset per-case counters and the lino port does not. A harness lifetime difference, not a game one. The *buffer* is graded and is comparable: `rndpat` writes all 64,800 bytes, so "unchanged" really does separate returning from not returning. |
| N5 | the `fast_srand(seedval + 4112)` bridge | Its only observable is `rtperiod`, which is BOUNDED (section 7). No artefact in this wave anchors that bridge to the binary. |
| N6 | a moon's last 41 `lssmooth` bytes | On a moon `s_background`'s block is 64,800 bytes exactly and `lssmooth` reads 41 past it, into DOS heap slack this port zeroes. No capture in the set is a moon; the two synthetic moons are three-way agreement only. |
| N7 | `BrtlToInt16` narrowing at `work/surng.txt`'s call site | The largest brtl argument in this corpus is 380. Latent, not exercised. |
| N8 | `build_surface()`, ground, sky, SURFACE.BIN | Wave 7b. |

---

## 9. Every check, broken by breaking the code

A check nobody has broken is a check nobody has tested. Seventeen sabotages run on every
non-`--quick` invocation. Each names the check it is expected to trip; a row caught by
nothing would be reported as caught by nothing rather than dropped.

| sabotage | side | what it does | caught by |
|---|---|---|---|
| `CT3ASSIGN` | C ref | ASSIGN the type-3 land noise | A1.cref; **only** the type-3 capture moves, 53,373 bytes |
| `CFRACDRAW` | C ref | one extra brtl draw per `fracture()` | C1 (draw totals) on 3 captures, and their maps |
| `CTERM36` | C ref | terminator band one column east | A1.cref on 10/10; **no** draw count moves, so C1 alone would have missed it |
| `CSEEDTRUNC` | C ref | truncate `seedval` before the `+4112` | C4 (rtperiod) on the synthetic seed-flip cases and on **no** capture map - which is why the synthetic corpus exists |
| `LT3ASSIGN` | lino | the same type-3 defect, in the deliverable | A1.lino, the same 53,373 bytes |
| `LSUBORDER` | lino | `x + random(c) - random(c)` right to left | A3 (palette) 10/10 **alone** - see the note below |
| `LRNDPATUNS` | lino | the surface noise folded with an UNSIGNED multiply, the one-character difference from the galaxy hash | C3's per-phase **map** hash on **every** case, and A1.lino on 9 of 10 - see the note below |
| `LSTRAY` | lino | one byte stored past the 64,800 | A5's tail arm alone; maps and draw totals untouched |
| `SSTRAY` | spec | `crater()` stores 100 bytes past the map | A5's spec arm |
| `NOEARLY` | spec | the type-10 early return not taken | A6 - `rndpat` fills all 64,800, so "unchanged" is not automatic |
| `BAND` | spec | band placed one column either side of `plwp` | E3/E4 |
| 6 x `PRED[...]` | spec | one extra draw in `crater_juice` (brtl), `crater_juice` (fast), `fracture`, `atm_cyclon`, `randoface`, the palette | C2, on every type that reaches the painter |

**A correction this table forced, recorded rather than quietly fixed.** `LSUBORDER` was
first written down as "same counts, different VALUES, so the brtl value hash catches it".
It does not. Swapping `+` and `-` changes how two drawn numbers are *combined*, not which
numbers are drawn: the run measured 10/10 palettes wrong, **0** phase records wrong, 0 draw
totals wrong. So the palette bytes are the only evidence for that defect anywhere in the
wave, which is exactly why C3's stream hashes are not a substitute for grading the artefact.
The row now claims what it measures.

`LSUBORDER` and `CTERM36` between them are why draw totals alone are not a grader:
`LSUBORDER` moves only the palette, `CTERM36` moves only the 64,800 bytes, and neither moves
a single draw count.

**`LRNDPATUNS` is the reason the per-phase records exist, and it also found something.** It
corrupts the buffer at `RNDPAT`, before the switch has drawn anything: at that mark the
sabotaged build differs from the clean one in the map hash and in *nothing* else, on all 23
cases that reach `RNDPAT` (the type 10 returns before it). Two things follow that no summary
would have shown.

* The final artefact moves on only **9 of 10** captures. The exception is the type 9, whose
  switch arm opens with `pclear(p_background, 0x1F)` (NOCTIS-0.CPP:5061) and writes all 64,800 bytes - so `rndpat`'s output
  cannot survive into its map at all. A grader holding only the final artefact is blind to a
  corrupt `rndpat` on that type; the per-phase map hash is not. The check states the
  exemption and derives it from the source, rather than counting 9/10 as a pass.
* The draw totals move on **2** captures - types 5 and 7, whose `randoface` draws twice for
  every pixel that passes its gate. A defect in the *buffer* propagating into the *brtl
  stream* is precisely the interleaving hazard this wave was set up to test, and here it is,
  measured.

---

## 10. Open items for the coordinator

Found while writing the test; **none of them changes this wave's result**, and none is in
this test's namespace to fix.

1. **`su_grade.py`'s `C6m` cannot fail.** Its `ok` argument is the literal `True` and it is
   not folded into `all_ok`. In the clean run 3 of its 10 rows already disagree
   (`lane_b00_t2` (142,272) vs (134,264); `jrot_b00_t6` (183,313) vs (179,311);
   `jrot_b02_t9` (358,128) vs (0,360)) and the summary still prints `C6m 10 ok 0 fail`.
   `tests/test_surface.py` does not use a manifest terminator detector at all.
2. **`su_grade.py`'s `E1e` rotation arm cannot fail**, because `su_grade` always calls
   `S.run(..., secs=0.0)` so `rot` is identically 0 on both sides. The consequence is real:
   the lino port computes rotation from the guest clock and gets 141, 176, -274, -79, 309,
   -117, 336, -187, -48, 302 while spec and cref get 0, and nothing compares them.
   `tests/test_surface.py` passes the corpus's own `secs` and the two agree 10/10 - so the
   port is fine and the *grader* was blind. One-line fix in `su_grade.py`.
3. **`su_break.py` never increments `hit['E1e']`**, so the shipped tool prints
   `uncaught: [SEEDTRUNC, SRANDONCE]` rather than the table the exit report claims.
4. **`su_ledger.predict_switch()`'s brtl arm on types 1 and 4 is an echo**, not a
   prediction: `su_spec` sets `gates['cj_brtl'] = B.n - _n0` around `crater_juice` and the
   predictor reads it straight back, contradicting `su_ledger`'s own docstring. An injected
   extra draw gives `observed == predicted`. `tests/test_surface.py` derives that term from
   the loop structure instead and catches the injection on every case that reaches it.
   Fourteen derivation helpers in `su_ledger.py` are dead code.
5. **`work/su-check.py`'s `SECS_TYPES = {2,3,5,6}` is an `inrow`-class escape hatch.** It
   exempts 4 of 10 captures, so a one-byte flip on the type-3 capture, and all three stored
   type-3 sabotages including `TYPE3ASSIGN` at 53,373 bytes wrong, print
   `MAP 9 exact, 0 FAILED, 1 ungraded`. It swallows precisely the LR divergence this wave
   exists to test. `tests/test_surface.py` has no per-type exemption and reads its own dump
   with its own reader.
6. **`tests/w5audit.py`'s `scope_files()` still excludes `noctis-harness/su_*.py`.** This
   test adds only its own filename to the scope (Waves 6a and 6b did the same), scores 0
   findings there, and *reports* the audit over the 11 Wave 7a python files without failing
   the suite on another wave's file. That run currently returns 1 finding,
   `su_spec.py:139 'rng <= 0'` - a rule-C constant condition. Wave 7a's honest w5audit score
   is therefore 1, not 0, until someone dispositions it.
7. **The manifest's `objectschart_sha256` is the digest of the whole 40,000-byte file**, not
   of the 32,400 bytes that are graded. The true claim is a byte-for-byte prefix match; this
   document states it that way.
8. **`work/su-mkcorpus.py`'s stated plateau for `lane_b00_t2` is wrong** (the measured
   interval is [556778145, 556778339]), and its `seedval()` does not go through
   `su_seed.chain()`. Neither changes any map - see section 7 - but the comment claims more
   than the code does.

---

## 11. What this test writer touched

Created: `tests/test_surface.py`, `tests/w7arun.ps1`, `docs-notes/WAVE7A_SURFACE.md`.
Edited: `tests/w5audit.py` - one line, adding `test_surface` to `scope_files()`, which is
what Waves 6a and 6b did with their own filenames.
Generated: everything under `tests/gen/w7a`, wiped and rebuilt on every run.

`tests/run_all.py` is untouched. `main/` is untouched - PRISTINE 6/6, asserted by the test
itself. `noctis/` is untouched. No git was run and DOSBox-X was never started.

One disclosure: `noctis-harness/su_corpus.spc`'s **mtime** moved, because
`python noctis-harness/su_grade.py` was run once to measure how long the existing grader
takes and that script regenerates the file. Its **contents** are byte-identical to what
`su_corpus.write(su_corpus.all_cases())` produces
(sha256 `af39686126d6da3d3ecc7888bef694c8627a333b433f72755935b584bc8d90ed`), so nothing
changed but the timestamp. `tests/test_surface.py` itself writes only inside `tests/gen/w7a`
and re-hashes all 58 files it reads to prove it.

---

## 12. How to run it

```
python tests/test_surface.py            # everything, including the sabotages
python tests/test_surface.py --quick    # skips the sabotages. NOT a pass.
python tests/run_all.py surface
```

The full run rebuilds: the lino port and four sabotaged copies of it, the C reference and
four sabotaged copies of it, and re-runs the Python spec 24 times plus the negative
controls, and takes about four and a half minutes. Prerequisites: `gcc` on PATH, the
extended lino toolchain, and `tests/gen/recon_w7a/out`. No DOSBox-X and nothing written
outside `tests/`.

As shipped, standalone:

```
RESULT: PASS - 57 checks
real    4m35.756s
```

with `PRISTINE.sha256 6 ok 0 bad`, `G2 all unchanged` over the 58 files it reads, `G3 0
w5audit findings` in this file, and all seventeen sabotages caught by the check each was
aimed at.
