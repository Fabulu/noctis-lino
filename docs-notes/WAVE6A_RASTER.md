# WAVE 6a — what is exact, what is bounded, what is ungraded

**Scope.** The 3D-to-screen projection and its clipping, `poly3d` (the flat
polygon rasteriser) and `polymap` (the perspective-correct texture-mapped one).
Not spheres, not `.NCC` model loading, not the background — those are Wave 6b.

**Executable form.** `tests/test_raster.py`. Every number below is produced on
every run by two independently-owned implementations: the lino port, rebuilt
from `work/pg*.txt` into `tests/gen/w6a` and driven with the poll-and-kill
runner; and `noctis-harness/pg_ref.c`, implementer 2's transliteration of
`TDPOLYGS.H`'s inline assembly, rebuilt with gcc. Nothing is graded against a
stored artifact, and in particular nothing is graded against `work/pg-out.bin`,
which is a file the code under test wrote.

**Result: 65 checks, PASS, about 35 seconds.** Four deliberately broken lino
builds — one edit each, one per surface the page check claims to cover — every
one caught. Ten record perturbations, every one caught. One alternative
rounding schedule of the oracle, caught. Zero checks left unproved.

---

## 1. The correctness split, and what it bought

The wave was scoped on one claim: **a rasteriser is integer-exact once its
vertices are pinned**, so it can be byte-compared with no tolerance, while
projection is floating point and has to be graded inside an envelope.

The rasteriser half held exactly as designed. The projection half came out
*better* than the design allowed for, and the reason is worth stating because
it changes what the check should be.

| | claim | strength | measured |
|---|---|---|---|
| R1 | the rasteriser page, all 64,000 visible pixels | EXACT | 107 pages, 0 differ |
| R1e | the colour-255 sentinel classes are in the compared set | EXACT | 5 of 5 present |
| R2 | the bounding-box gate | EXACT | 14 cases, 0 differ |
| R3 | `ipart[]`/`fpart[]` over the graded interval | EXACT | 23 cases, 5,028 integers, 0 differ |
| P1 | projection topology | EXACT | 122 field groups, 0 differ |
| P2 | the projected vertex table `mp[]` | BOUND ±1, CHECKED 0 | 222 components, max&#124;Δ&#124; **0** |
| P3 | `getcoords` | EXACT | 4 cases, 0 differ |
| F1 | the two sides' raster inputs are the same numbers | EXACT | 2,285 integers across 144 cases |
| F2 | the two sides' projection inputs are the same numbers | EXACT | 309 binary32 patterns across 35 cases |

### Why P2 is checked at 0 and not at ±1

`docs-notes/FLOATPOLICY.md` grades projection inside a ±1 pixel envelope, and
that is the DECLARED bound. This corpus measures **0**: every one of 222 `mp[]`
components agrees exactly between the two implementations.

That difference is not cosmetic, and the test proves it rather than asserting
it. Run the oracle with `--round=chop` — the same code with the x87 rounding
control moved off round-to-nearest-even — and **18 of 30 cases move, by exactly
1**. A ±1 envelope therefore passes a systematically wrong rounding mode; an
exact check does not. Both facts are checks in the file (B10, B11), so the
reasoning cannot rot without the suite noticing.

This closes the specific hole the Wave 6a QA pass identified: *"a systematic
chop error at 59/336 components passes [the ±1 envelope] undetected"*.

The two bounds are also both shown non-vacuous, in the same run:

* B7 — add 1 to every `mp[]` component: fails the exact check, **passes** the
  declared envelope. That is the whole argument for checking at 0.
* B8 — add 2: fails the declared envelope too, so the envelope is not
  decoration either.

**If a future corpus genuinely produces a 1-pixel spread**, P2c must be relaxed
to the declared bound and the relaxation recorded here. Relaxing it because a
regression appeared would be grading to fit and is exactly what this paragraph
exists to forbid.

### Colour 255, the polygon-edge sentinel — established, then relied on

The mandate asked where index 255 comes from and why, before anything leans on
it. It is not a palette convention: **Segmento stores 255 and nothing else**
(`pgrast.txt:194` vertical branch, `:245` general branch), and **drawb's row
loop scans the row for 255** with `repne scasb` / `repe scasb` and fills
*between* the runs it finds (`pgrast.txt:616-648`). The wireframe is the input
to the fill; the fill has no other record of where the polygon's edges are.

The consequence, which is the reason it matters here: a 255 pixel that was
already on the page before the polygon was drawn is **indistinguishable** from
an edge this polygon just laid, so the fill brackets the wrong span. The frozen
corpus has five cases built around exactly that — `PRE255MID`, `PRE255RIGHT`,
`ADJ255`, `COL255_A`, `COL255_B` — and `R1c` grades all five byte for byte.
`R1e` checks they are actually in the compared set, because a corpus that
quietly lost them would still report `R1c` green and mean considerably less.

---

## 2. Projection went from *not graded at all* to graded on 35 cases

The QA pass on the implementer's harness found projection ungraded on every
axis: *"the rotation nucleus, both matrices, the p/t table distinction, the fst
wide/narrow asymmetry, the near-plane clip and the topology. Zero records
join."* That was correct. The lino dump over `work/pg-corpus.txt` contains
**zero** kind-24 records, because that corpus contains no `PROJ`, `PMAP` or
`GETC` row — even though `pgmain.txt` implements opcodes 6, 7 and 8 for exactly
those.

The port hard-codes the camera (`pgfp.txt` "PGF constants": `dpp = 210.0f`,
`uneg = 100.0f`, `alfa = beta = gamma = 0`, `cam = (0,0,0)`) and has no setter,
so it was assumed no frozen `PROJ` case could join. That assumption was wrong:
**31 of the 51 frozen `PROJ` rows and 4 of the 14 `GETC` rows use precisely
that camera.**

`tests/test_raster.py` transliterates those 35 rows into the lino integer
grammar, runs the *unmodified* port over them, and joins the result against the
oracle's records for the *same* frozen rows. The shipped fixture is not
touched; the frozen corpus is not touched; the transliteration is regenerated
every run and checked back off disk by F2.

What that grades, that nothing graded before:

* the rotation nucleus and both optimised tables (`p`- and `t`-), through the
  per-vertex near flags `rwf[]` and `doflag`;
* the near-plane Sutherland–Hodgman walk against `z == uneg`, through `vr2`;
* all four 2-D clip stages, through `vr3..vr6` at every stage actually reached;
* the screen bounding box the clipper does *not* recompute;
* the two `fistp` sites in `project3d`, through `mp[]`, at round-to-nearest-even;
* `getcoords`' returned char and its coordinates.

### The three conditional fields, and why they are conditional

A record slot one side never wrote for a case is not a disagreement; comparing
it would be comparing stale state. Three slots are compared conditionally, and
each condition is read out of the code rather than fitted to the data:

| slot | rule | source |
|---|---|---|
| `rwf[k]` | compared for `k < nrv` only | both sides loop `k < nrv` (`pg_ref.c:1222`, `pgproj.txt:196-197`); `rwf[3]` of a triangle describes a vertex neither side has — zero on the oracle's zeroed `TOPO`, stale on the lino |
| `vr2` | compared against the oracle's `vr6` when the 2-D chain ran and succeeded, against `vr2` otherwise | `pgproj.txt:680` assigns `[PJvr2] = [PJvr6]` once all five stages pass |
| `min_x`, `max_x` | not compared on the `polymap` path | `polymap` has no 2-D clipper and `PJ projectmap` searches only Y (`pgproj.txt:395-403`); the oracle leaves both 0 |

The remaining 42 frozen projection rows are **NOT GRADED**, counted with a
reason on every run:

```
ang!=0                       7      cam!=0                        2
cam!=0,ang!=0                5      dpp!=210.0f                  16
no lino opcode for ROWUV     9      no lino opcode for FACING     3
```

`N1` asserts that graded + ungraded = every row, so a case cannot fall out of
both sets silently.

---

## 3. The fixture problem, and why this wave stopped using a hash

The two sides cannot read the same file. The oracle parses `KEY id k=v`; the
lino tokeniser understands exactly one lexeme, a signed decimal integer. So
`work/pg-corpus.txt` is necessarily a transliteration of the frozen corpora and
**can never have the same sha256**.

`noctis-harness/pg_grade.py`'s `FIXTURE.shared_corpus` row compares those two
hashes, and therefore reports FAIL in the shipped configuration and blocks all
eight of that grader's lino rows. Worse, it is emitted inside an
`if os.path.exists(theirs):`, so **deleting `work/pg-corpus.txt` makes that
grader print `17 rows, 0 FAIL` and exit 0** — the single signal that the wave
was ungraded disappears when the artifact is absent.

F1 replaces the hash with the thing it was standing in for. `test_raster.py`
parses **both** grammars and compares the pinned numbers case by case, field by
field: 2,285 integers across 144 cases, plus the case order, which is part of
the fixture because pre-state 3 hands one case's output page to the next. An
absent file fails F1 instead of skipping it. F2 does the same for the
projection fixture this file has to generate: it is read back off the disk the
lino reads and every binary32 pattern is compared against the frozen hex, so a
transliteration slip fails as a *fixture* error rather than masquerading as a
disagreement about the port.

---

## 4. Every check broken, by breaking it

House standard: *nothing graded against a stored artifact the code under test
produced; every check provably breakable, demonstrated by breaking it.*

**Record perturbations** — each moves exactly the count it should:

| | perturbation | effect |
|---|---|---|
| B1 | one bit of one pixel, index 12345, in ONE page | R1c fails on exactly 1 page |
| B2 | one bit of one pixel in EVERY page | R1c fails on all 107 — no page passes for a reason other than its own content |
| B3 | +1 on one bbox `min_x` | R2b fails, 1 of 14 |
| B4 | +1 on one `ipart` | R3b fails, 1 of 23 |
| B5 | one topology field | P1b fails, 1 of 122 |
| B6 | one `getcoords` return | P3b fails, 1 of 4 |
| B7 | +1 on every `mp[]` component | P2c fails, P2b passes |
| B8 | +2 on every `mp[]` component | both fail |
| B9 | +1 on one pinned corpus integer | F1c fails, 1 of 144 |
| B9b | +1 on one binary32 pattern | F2 fails, 1 of 309 |

**A different implementation of the same thing** — not a perturbation:

* B10/B11/B12 — the oracle rebuilt with `--round=chop`: `mp[]` moves in 18 of
  30 cases and the topology bbox in 12 of 122 field groups, all by 1. P2c
  fails; P2b passes. That pair is the evidence for section 1.

**Four real one-line defects, compiled and run through the whole pipeline** —
one per surface the page check claims to cover, because "the page check bites"
is a claim about a rasteriser, not about a bitmap:

| sabotage | library | the defect | caught |
|---|---|---|---|
| `SEGCLOSED` | `pgrast.txt` | Segmento's DDA closes the half-open x interval, so the greater-x endpoint gets painted | R1c, 2 of 107 pages |
| `FILLROW` | `pgrast.txt` | `poly3d`'s flat fill stops one row short of its own limit | R1c, 20 of 107 pages |
| `SCRATCHOFF` | `pgtex.txt` | the span's `tinta` re-read drops `farmalloc`'s offset 4 | R1c, 23 of 107 pages |
| `PROJXC` | `pgproj.txt` | `project3d` adds the vertical screen centre to the horizontal coordinate | P1b, 29 of 122 groups; `mp[]` max&#124;Δ&#124; 128 |

`SEGCLOSED` catching only 2 of 107 pages is worth reading twice. It is a real
catch, but it says the corpus exercises Segmento's *general* branch — the one
whose endpoint is at issue — on very few pages, because `poly3d` then fills
over most of the stroke. It is the weakest of the four and the number is
printed on every run rather than summarised away.

`SCRATCHOFF` is the settled trap. `TDPOLYGS.H`'s `wave()` has a "+4" that
earlier reconnaissance called unresolvable without emulation; `BUFFERMAP.md`
§4.1 settled it — `farmalloc` returns offset 4, and the mysterious `es:[di+4]`
is that offset. Removing it from one read moves 23 pages, so the settlement is
load-bearing here and not a note.

### The four known harness defects were not built on

The mandate pinned four live defects and forbade a fifth. None of them is on a
path this file uses:

* `fb_tick.py`'s tautological ring sweep — not used.
* `T2.LINO.MATRIX.NULL` — not used.
* `fb_ref.c`'s E1 pair — not used; this file's C side is `pg_ref.c`, and it is
  exercised by two independent means (the cross-owner joins, and `--round=chop`
  as a negative control).
* the `inrow:` escape hatch — not used. Every check here names a falsifier that
  is executed in the same run.

And `tests/test_raster.py` is now inside `w5audit.py`'s scope (one line added to
`scope_files()`), so its checks are executed over random assignments on every
suite run and a tautology fails the build. It has **zero findings**. That
matters because the previous wave's grader evaded the audit by accident: the
analyser's `CHECK_CALLS` list does not contain the recorder `pg_grade.py` uses
for every verdict, so all five `noctis-harness/pg_*.py` files return zero
findings for the wrong reason. This file uses `linoharness.Check.ok`, which the
analyser does read.

Two consequences of being inside the audit, recorded because they shaped the
code: `chk.eq(x, 1, ...)` trips Rule A, because the analyser judges *every*
argument of a check call and a bare `1` is a constant that cannot fail — so
every such comparison is written `chk.ok(x == 1, ...)`. And a tally whose
predicate compares two whole tuples reads as always-true to the analyser, so F2
compares element by element.

---

## 5. What is NOT graded

Stated as a list rather than implied by a PASS. Each item is *counted* by a
check, so it cannot quietly become stale.

1. **20 of the 51 frozen `PROJ` cases and 10 of the 14 `GETC` cases.** The
   port hard-codes the camera and has no setter. Grading them needs a camera
   setter in the port, not a change to the test. Counted by N1.
2. **The `polymap` texture-gradient basis (oracle `K29`) and the derived row
   `u`/`v` (`K2A`).** The lino emits no counterpart record at all — 34 oracle
   records with nothing to join. N2 pins the exact set of record shapes the
   lino emits, so adding an emitter fails the check and forces this list to be
   revisited; N2b asserts the oracle side is non-empty, so N2 is a gap and not
   an empty set.
3. **The 16-bit address truncation.** Exercised by nothing on either side. The
   QA pass proved this independently and in both directions: removing all three
   masks from `pg_ref.c` (with a clean control that only widens the backing
   array) moves 0 records, and a lino build with `MEM seg addr` bypassed
   produces a bit-identical dump. The buffer model's central claim is not
   driven by this corpus. Wave 6b or a dedicated probe, not this file.
4. **`gamma != 0`.** `pgfp.txt:294` says *"The port asserts gamma == 0 ... set
   it non-zero and the flag fires"*. There is no assertion and no flag: `FSGAM`
   is declared once, initialised to zero once, and never read. N3 pins that
   absence and will fail the day somebody implements it, which is the point —
   the claim then gets re-checked instead of staying wrong. **The comment in
   `pgfp.txt` should be corrected by whoever owns `work/`; this file cannot,
   and does not, edit it.**
5. **Anything needing the 1996 binary.** `noctis-harness/pg_bin.py` grades the
   clip immediates, the `farmalloc` offset, the two scratch-pixel stores and
   three constant-free instruction censuses against `NOCTIS.EXE` — 21 checks,
   all 21 shown breakable by the QA pass. That is a different owner pair and a
   different file, and `test_raster.py` does not duplicate or restate it.
6. **`polymap`'s span output on the projection fixture.** The transliterated
   `PMAP` cases are graded on projection topology and `mp[]` only; the span
   parameters are pinned at zero because the frozen `PROJ` rows carry none.
   The span rasteriser itself is graded by R1/R3 on the 48 frozen `SPAN` cases,
   which is a separate and complete surface.

---

## 6. Open items

**O1 — the shipped grader has two void rows and one that goes green when its
input is deleted.** `pg_grade.py:204` (`S6.P3.exact_fraction`) and `:209`
(`S6.P3.f32_control`) are emitted as `PASS if tot else N/A`, where `tot` is the
number of components compared and is never zero. The QA pass demonstrated both
still print PASS with every `mp[]` component off by 1,000. The first of these
is the row `pg_ledger.py` names as the pass/fail constant for the `S6.P3`
GRADED row. Separately, `FIXTURE.shared_corpus` disappears — and `pg_grade`
exits 0 — if `work/pg-corpus.txt` is absent. These are implementer 2's files.
`test_raster.py` does not use any of them, and F1 supersedes
`FIXTURE.shared_corpus` on the only question it was asking. **Recommendation:
delete the two void rows and the eight permanently-`N/A` `[lino]` rows, and
retire `FIXTURE.shared_corpus` in favour of F1.**

**O2 — `work/pg-pgbrk15main.bin` is stale and cannot be regenerated.**
`work/pgbrk15main.exe` (BUMPROW) hangs; three runs at 120 s, 120 s and 300 s
produced nothing, yet a 9,367,352-byte artifact for it sits on disk.
`work/pgall.ps1` prints `RUN-FAIL` and moves on without recording anything.
`test_raster.py` builds its own sabotages and reads none of the `pgbrk*`
artifacts, so this does not affect anything here — but a stored `.bin` that no
current source produces is exactly the failure mode the house standard exists
to prevent, and it should be deleted.

**O3 — `brk19` (UV32) is caught by nothing.** Of the 26 shipped lino
sabotages, the QA pass reproduced 21 caught on the frozen corpus, 3 more only
on the own corpus, `brk15` unrunnable, and `brk19` caught on neither. Either
the sabotage is a no-op or the corpus has no case that reaches it. Not
addressed here; `test_raster.py`'s four sabotages are its own and all four bite.

**O4 — `nrv` is unbounded and aliases at 5.** `FSINX=252`, `FSINY=256`,
`FSINZ=260` are adjacent 4-slot arrays and `PG read verts` writes `FSINX+i` for
`i = 0..nrv-1`, so vertex 4's X lands exactly on vertex 0's Y. The QA pass
demonstrated it on real geometry: at `nrv=3` changing `v0.y` changes the dump;
at `nrv=5` the same change alters nothing. Every case this file feeds the port
has `nrv <= 4`, so nothing here trips it — which is precisely why it needs a
bound in the port rather than a check in the test.

**O5 — the corpus does not exercise Segmento's general branch hard.**
`SEGCLOSED` moves 2 of 107 pages. A handful of `SEG` cases whose stroke is not
subsequently filled over would raise that number and is cheap; it is a fixture
change and therefore a coordinator commit.

**O6 — `--acc` and `--fst` are invisible on the projection subset.** Running
the oracle with `--acc=f32`, `--acc=f64`, `--fst=allwide` or `--fst=allnarrow`
moves **zero** `K22`/`K24`/`K27` records over the whole frozen `PROJ` corpus.
So P1/P2 discriminate the rounding *mode* and do not discriminate accumulator
width or the `fst` wide/narrow asymmetry. That is a real limit on what
"projection is exact" means here, and closing it needs corpus geometry chosen
to be sensitive to those axes — the oracle already measures that the sensitivity
lives in `K29 BASIS` and `K2A ROWUV`, which item 2 of section 5 says are
ungraded. **These two gaps are the same gap.**

---

## 7. Reproducing

```
python tests/test_raster.py            # 65 checks, ~35 s
python tests/test_raster.py --quick    # skips the four sabotages; NOT a pass
python tests/w5audit.py --findings     # zero findings in test_raster.py
```

Prerequisites: the extended toolchain (`main/lib/gen/compiler114m.exe` and
`main/cpu/i386m.bin`), `gcc` on PATH, and the four frozen corpora under
`noctis-harness/`. A missing prerequisite is reported as a skipped leg with a
non-zero exit, never as a pass. Nothing under `main/` is touched
(`PRISTINE.sha256` verifies with 0 violations before and after), nothing under
`C:\programmieren\noctis` is touched, and nothing in `work/` is written — the
whole run lives in `tests/gen/w6a`.
