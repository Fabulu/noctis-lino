# WAVE 6b -- what is exact, what is bounded, what is ungraded

**Scope.** `globe()`, `glowinglobe()`, `white_globe()`, `white_sun()`,
`background()`, `surface()`'s day/night band, the sphere pixel scaler, and
`.NCC` model loading (`loadpv` / `copypv` / `modpv` / `drawpv`'s dispatch).
Not `poly3d`, not `polymap`, not `project3d` -- those are Wave 6a and are not
restated here.

**Executable form.** `tests/test_spheres.py`. Every number below is produced on
every run by implementations that are recomputed from source in that run: the
lino port, rebuilt from `work/sp*.txt` into `tests/gen/w6b` and driven with the
poll-and-kill runner; `noctis-harness/sp_ref.c`, implementer 2's C
transliteration of the inline assembly, rebuilt with gcc; and
`noctis-harness/sp_spec.py`, implementer 2's Python model built from the asset
bytes and the 1996 sources. Nothing is graded against a stored artifact, and in
particular **nothing is graded against `work/sp-out.bin`**, which is a file the
code under test wrote.

**Result: 93 checks, PASS, about 52 seconds.** Eight deliberately broken lino
builds -- one edit each, one per surface the checks claim to cover -- every one
caught. Thirteen record and asset perturbations, every one caught. Zero
`tests/w5audit.py` findings.

```
python tests/test_spheres.py            # 93 checks, ~52 s
python tests/test_spheres.py --quick    # skips the eight sabotages; NOT a pass
python tests/w5audit.py                 # PASS; zero findings in test_spheres.py
```

`tests/w5audit.py` gained one line (`"test_spheres"` in `scope_files()`), which
is the same accommodation Wave 6a took. Nothing else outside `tests/` was
touched: `PRISTINE.sha256` verifies 6/6 before and after, `work/sp-out.bin` is
still `9d642d8f…c111`, and `C:\programmieren\noctis` is read-only to this file.

---

## 1. The join nobody had written

The Wave 6b QA pass reported, correctly, that **the port and the oracles had
never been joined**. The two sides consume incompatible fixtures: `sp_ref.c`
and `sp_spec.py` read `noctis-harness/sp_corpus.spc` (`CASE id KIND k=v`),
while the lino tokeniser understands exactly one lexeme -- a signed decimal
integer -- and reads `work/sp-corpus.txt`. The two dump formats are equally
incompatible: a 64-byte 16-`int32` binary record stream on one side, a
whitespace text grammar on the other. Nothing in the repository read the
binary stream.

`tests/test_spheres.py` closes that. It parses the `SPD1` stream directly,
replays the lino corpus in `sp_spec`'s model *in file order* -- order is part of
the fixture, because pre-state 2 means "carry" -- and compares pages byte for
byte and censuses field for field.

| | claim | strength | measured |
|---|---|---|---|
| L1 | `globe()`'s page | EXACT | 11 pages, 0 differ |
| L3 | `glowinglobe()`'s page | EXACT | 6 pages, 0 differ |
| L5 | `background()`'s page | EXACT | 9 pages, 0 differ |
| L7 | `surface()`'s day/night band | EXACT | 5 pages, 0 differ |
| L9a | `white_globe()`'s page | EXACT | 5 pages, 0 differ |
| L9b | `white_sun()`'s page | EXACT | 4 pages, 0 differ |
| L10 | all of the above together | EXACT | 40 pages, **2,564,000 bytes**, 0 differ |
| L11 | census, preamble, arena and binary32 fields | EXACT | 3,798 fields, 0 differ |
| L12 | the sphere pixel scaler | EXACT | 17,808 integers, 0 differ |
| L13 | `loadpv`'s post-scale float32 arrays | EXACT | VEHICLE on 2 cases |
| O1 | the two oracles emit the same record keys | EXACT | 19 kinds, 162 keys |
| O2 | …and agree field for field | EXACT | 4,238 records, 0 differ |
| O3/O4 | …and their page images are identical | EXACT | 50 pages, 0 differ |
| T1-T7 | the two asset censuses, decoded a third time here | EXACT | agrees with `sp_spec` on all 10,780 draws and all 3,670 words |

Three surfaces are graded here that no producer graded before:

* **`white_globe()` and `white_sun()`** -- 9 pages and their census. The QA pass
  found `sp_ref.c` and `sp_spec.py` compared to each other on `WHITE` cases fed
  *pre-computed centres*; the lino computes the centre itself and its pages
  were joined to nothing. Here the preamble is run at `variant` 2/3 and its
  `cx_d`/`cy_d` feed `white_body`, so the whole path is graded. This is what
  catches `WHITEUNS`.
* **The float preamble** (`SETUP`, 74 fields over 16 cases). The port's
  `__ftol`-chopped centres, the clamped `mag_factor` bit pattern and the
  fill-manager selector, joined to `sp_spec.preamble` at the camera
  `pgfp.txt` hard-codes (`dpp = 210.0f`, `alfa = beta = gamma = 0`,
  `cam = (0,0,0)`, so the optimised table is `(210, 0, 1, 0, 1, 0, 210, 0)`).
* **The `pvfile` arena layout.** `ARENA` records over five load cases: the
  handle, `npolygs`, `dataptr`, `datalen`, the depth-sort flag, the nine DOS
  sub-array offsets and `datatop`. The shipped load order gives
  `0 / 3740 / 7480 / 8840` with `datatop 10200`, and a re-laid-out arena fails
  on every one of them.

### Two conditional fields, and why they are conditional

A slot one side never wrote is stale state, not a disagreement. Two are
compared conditionally and each condition is read out of the code:

| slot | rule | source |
|---|---|---|
| `SETUP.centre_x/centre_y/mag/gman` | compared only when the preamble did **not** reject | the port leaves `[GBcx]`/`[GBcy]` at their previous value on the reject path (`spglobe.txt` `"SP gs out"` jumps straight to the emit) |
| `SETUP.gman` | compared only for `which == 0` | `gman` is *globe's* fill-manager selector; `glowinglobe` has none and never writes the slot |

Without the first rule three cases (1407, 1456, 1457) report a stale `158/99`
against the oracle's zeroes; that is a fixture artefact and not a defect, and
saying so in code is better than widening the check.

---

## 2. The predictor, and the residual bound

`GLOBES.MAP` is **shipped** and compared byte-exactly. The recovered
projective model is the test's *independent predictor*, and it is bounded, not
exact. The constants are PORTPLAN.md:611-620's, pinned as source text and
never refitted at test time -- a refit would be table-versus-table and would
prove nothing.

```
row k = round((i - 5.5)/360)          column s = i - 5.5 - 360k
latitude  = -60 + 1.00047 k           longitude = -1.00060 s
dx = 250.84 cos(lat) sin(lon) / (2.506 - cos(lat) cos(lon))
dy = 200.68 sin(lat)           / (2.506 - cos(lat) cos(lon))
```

| | required | measured |
|---|---|---|
| GP1 every draw record within 1 px of the rounded prediction, both components | 10,780 of 10,780 | **10,780 of 10,780** |
| GP4 worst single-component residual | ≤ 1.50 px | **1.4331 px** |
| RMS residual per record | ≤ 0.80 px | **0.7647 px** (0.5407 per component) |

**The mandate's "RMS residual 0.47" does not reproduce, under either model.**
`sp_spec.py` ships a *re-fitted* set of constants (`Fx 250.8530`,
`Fy 200.6760`, `D 2.50666`, `lat0 −59.7960`, `dlat 1.000740`, `dlon −1.000960`,
`i0 5.7350`) which measure 0.5054 per record and 0.3574 per component. Neither
number is 0.47. G3 pins PORTPLAN's model and G4 pins `sp_spec`'s, so the
discrepancy stays visible instead of being edited into agreement.

### The predictor is predicting, not restating

Twelve wrong answers, each fed to the *same fixed function*, each required to
collapse GP1 below half:

| control | GP1 | RMS/record |
|---|---|---|
| working model | **10,780** | 0.76 |
| G7 texture stride 256, not 360 | 20 | 90.3 |
| G8 `Fx` and `Fy` swapped | 25 | 17.7 |
| **G9 isotropic at Wave 6a's `dpp = 210`** | **176** | **9.60** |
| G10 latitude sign flipped | 105 | 108.8 |
| G11 longitude sign flipped | 0 | 113.5 |
| G12 orthographic instead of perspective | 9 | 22.5 |
| G13 camera distance 2.0 instead of 2.506 | 6 | 31.2 |
| G14 bytes swapped (x,y) | 2 of 11,011 | 111.0 |
| G15 cursor origin off by one | 3,276 | 2.34 |
| G16 `y` read unsigned | 5,386 | 181.2 |
| G17 `x` read unsigned | 5,333 | 182.2 |
| G18 every skip advances by exactly 1 | 16 | 107.1 |

**G9 is the cross-validation the mandate asked for, and it comes out
negative.** Wave 6a measured `project3d`'s focal length at `dpp = 210.0f`;
substituting it into the sphere model collapses GP1 from 10,780 to 176. The
sphere table's focal length is a **baked asset constant**, not the camera's --
`Fy ≈ 200.68` with `Fx/Fy = 1.2500` (G5, the 320×200-on-4:3 pixel aspect).
The two must not be derived from each other, and now there is a check that
fails if somebody tries.

---

## 3. Two corrections to the established facts

Both were stated in the mandate as settled and both are wrong on the shipped
bytes. Both are now pinned by a check, so neither can drift back.

**C1 -- the total advance is 42,845, not 43,200.** Decoded twice (this file's
own decoder and `sp_spec`'s, compared record by record in T4), `GLOBES.MAP`
holds 11,293 records: 10,780 draws advancing the cursor by 1 each, and 513 RLE
skips whose bytes sum to 32,065. `10,780 + 32,065 = 42,845`, which is 355 short
of `360 × 120` -- 119 full texture rows and a partial 120th. T3 pins it. The
*consequence* the mandate draws -- that only latitudes −60 to +59 are ever
displayed -- is unaffected: `round(42,844 − 5.5)/360) = 119`.

**C2 -- `pixels + skip == 360` is not an invariant of `OFFSETS.MAP`.** It holds
in **39 of the 48 bands**; the other nine measure 346, 351, 358, 359, 361, 362,
369, 374 and 1564 (the last band absorbs a trailing pad). T7f pins that with
the deviations printed. What *is* true of every band, and is now checked:

* T7b -- 1 lead-in skip of 991, 48 scan bands, two trailing pads of 1,535;
  3,620 painting words and 50 skipping words (T7c).
* T7d -- band *k* starts on source row *k+2*, for all 48.
* T7e -- the band widths and the band source phases are palindromic, so the
  panorama is symmetric about its middle band.

---

## 4. The .NCC garbage slot

For a triangle the fourth vertex slot of a `.NCC` file holds uninitialised
memory from the 1996 editor. `loadpv` zeroes it **before** the scale-and-move
pass; skip that and the transform produces infinities.

| | measured |
|---|---|
| N2a | VEHICLE: 52 triangles, 156 slot-3 cells, **150 non-zero** |
| N2b | 26 of them exceed 1e6 and **2 are not finite**; max finite 2.9857e38 |
| N3a | zeroed first: 1,392 components, all finite, max &#124;v&#124; 4.18e4 |
| N3b | not zeroed: **5 non-finite** components, max finite &#124;v&#124; 7.00e37 |
| N3c | the zeroing changes 150 of 1,392 components |
| N4 | BIRDY's un-zeroed garbage is **55 small finite numbers**, max &#124;v&#124; 2000 |

**N4 is the argument for exactness.** BIRDY's garbage surfaces as −10.0, 12.0,
6.25 -- entirely plausible geometry. No tolerance and no eyeball catches it;
only bit-exact equality does. That is why nothing in this file uses a
tolerance, and why L13 requires **VEHICLE specifically** to be in the graded
set rather than "some model": VEHICLE is the only shipped model whose garbage
overflows, so it is the only one whose *presence* proves the zeroing was
graded rather than merely exercised. The check prints which model each `F32`
case dumps, so a corpus that quietly lost VEHICLE fails instead of shrinking.

B13 closes the loop from the other side: an oracle run with `nozero=True`
stops matching the port on **355 fields**. The check is grading the zeroing,
not the file format.

---

## 5. Every check broken, by breaking it

**Record and asset perturbations** -- each moves exactly what it should:

| | perturbation | effect |
|---|---|---|
| B1 | one bit of one page byte | exactly 1 of 40 pages fails |
| B2 | one bit of **every** page | all 40 fail -- no page passes for a reason other than its own content |
| B3 | +1 on one `globe` clip field | 1 field fails |
| B4 | +1 on one preamble centre | 1 field fails |
| B5 | +1 on one `loadpv` binary32 word | 1 field fails |
| B6 | +1 on one `white` census field | 1 field fails |
| B7 | +1 on one scaler output | 1 of 17,808 fails |
| B8 | a dump with **no** page records at all | 40 reported missing |
| B9 | every `PAGE` line deleted from an oracle dump | 50 keys reported missing |
| B10 | every `GLOBE` line deleted | 20 keys reported missing |
| B11 | one field of one oracle record perturbed | exactly 1 difference |
| B12 | **one byte of a sandbox `GLOBES.MAP`** | 5 of 40 pages move **and** GP3 4038→4037, RMS 0.764710→0.765258 |
| B13 | the oracle's slot-3 zeroing suppressed | 355 fields move |

B8/B9/B10 exist because of a specific known defect. `sp_compare.full_compare`
reports `total_diffs == 0` and `pages.ndiff == 0` for a producer that emits
**no page records at all**, because `PAGE` sits inside its `covered` set and an
absent kind joins zero rows. `compare_dumps` in this file compares the key sets
first and per kind, so deleting a kind, a case or a single line is a failure
and not silence. `join()` does the same for the lino side: every expected page
and field record must be *present*, and a missing one is counted as missing
rather than skipped.

B12 is worth reading twice. It is the mandate's "single corrupted table
record", and it needs **two** detectors to be honest: the rendered page (which
reacts because the oracle reads the corrupted table too) and the formula
predictor (which reacts because the record no longer sits where the model says
it should). B12d records the limit explicitly: **GP1 alone is too coarse** --
it moves only 10,780 → 10,779 on a three-unit corruption and does not move at
all on a one-unit one. GP3 and RMS are the statistics that carry it, and the
document says so rather than letting a reader assume GP1 covers everything.

### Eight real defects, compiled and run through the whole pipeline

One per surface the checks claim to cover, because "the page check bites" is a
claim about a renderer and not about a bitmap. Each is one localised edit to
one library in a cloned sandbox; the anchor must be unique or the sabotage
fails loudly instead of reporting "not caught".

| sabotage | library | the defect | caught by |
|---|---|---|---|
| `GLOBEOFF1` | `spglobe.txt` | globe's Y low bound 6 → 7 (niv-lr's `pos > 6`) | 3 pages, 9 fields |
| `CURSORCLIP` | `spglobe.txt` | `clipout` forgets `add bx,1`: only drawn records advance the tapestry cursor | 10 pages, 11 fields |
| `SATFLOOR` | `spglobe.txt` | the saturation floor is masked to six bits | 1 page |
| `GLOWDECIM` | `spglow.txt` | `glowinglobe` decimates on `test dx,7`, not `test dx,3` | 6 pages, 8 fields |
| `BGPLUS4` | `spbg.txt` | `background` drops the source `add bp,4` (niv-lr's commented-out `/*+4*/`) | 9 pages, 9 fields |
| `DARKSHIFT` | `spdark.txt` | `surface`'s band shifts right by 1 instead of 2 | 5 pages |
| `NCCZERO` | `spncc.txt` | `loadpv` never zeroes the slot-3 garbage | 355 fields |
| `WHITEUNS` | `spwhite.txt` | `white`'s `pix += target[pixptr]` treated as **unsigned** char | 2 pages, 4 fields |

`DARKSHIFT` and `SATFLOOR` move **pages only** -- no counter sees them, and the
byte-exact page is the only thing that does. `NCCZERO` moves **fields only**.
That asymmetry is the argument for carrying both kinds of check, and it is
measured here rather than assumed.

Two candidate sabotages were **rejected during development and are recorded so
nobody re-proposes them**:

* `SATSIGNED` -- making the saturation compare signed instead of unsigned. In
  the port both operands are already masked to `0..255` and held in 32-bit
  units, so signed and unsigned are the *same comparison*. It is a genuine
  no-op, not an uncaught defect.
* `GLOWX9` -- `glowinglobe`'s X low bound 9 → 10. No corpus case produces an X
  of exactly 9, so the edit is unreachable. It would have reported "not
  caught" and blamed the checks for a corpus gap. Widening the GLOW corpus is
  a fixture change and therefore a coordinator commit.

---

## 6. What is NOT graded

Stated as a list rather than implied by a PASS. Every item is *counted* by a
check, and U1c asserts that graded + ungraded = every one of the 167 corpus
cases, so a case cannot fall out of both sets silently.

1. **`glass_bubble()` and `smootharound_64()`.** 176 lines of
   `work/spglobe.txt:531-708`, reached by GRAS case 130 (`bubble=1`). Neither
   `sp_spec.py` nor `sp_ref.c` implements either -- both merely *name*
   `smootharound_64` in a header comment. That page is produced by code no
   second implementation covers. **This file refuses to grade it and says so
   (U1a); it does not pass it silently.** Closing this needs an oracle, not a
   change to the test.
2. **`glowinglobe()`'s out-of-range `riga[]` VALUES.** The index sequence is
   graded exactly (`oob_n`, `oob_min`, `oob_max` in L11). The values come from
   whatever DGROUP holds at `DS:435Ch ± 2*DI`, which is not statically
   recoverable. U4 **measures the size of the hole**: running the oracle under
   an all-`0xFF` DGROUP filler instead of zeros moves **1 page and 5 bytes**.
   That is the entire surface of the wave that depends on the unrecoverable
   image.
3. **`glowinglobe()`'s `start -= terminator_start; while (start<0) start+=360`
   wrap normalisation.** It appears 3 times in `sp_ref.c` and twice in
   `sp_spec.py` and **nowhere in the port**; the lino GLOW opcode carries no
   `terminator_start` field, so no corpus case can reach it. U3 pins that
   absence and will fail the day somebody implements it -- which is the point:
   the claim then gets re-checked instead of quietly staying wrong.
   **`work/spglow.txt` should grow the parameter, and its corpus a case that
   wraps; this file cannot and does not edit `work/`.**
4. **`drawpv()`'s actual rendering.** U2 measures, by census in both oracles,
   that neither calls `poly3d`, `polymap` or `randomic_mapper` -- 0 occurrences
   each. Only `loadpv` / `copypv` / `modpv` / `QuickSort` / `pv_dep_i` and the
   mode dispatch are delivered. Wave 6a grades `poly3d` and `polymap` on their
   own corpus; this file does not restate it. Joining the two is a wave of its
   own.
5. **`copypv` and `modpv` against an oracle.** `sp_spec.py` implements
   neither, so handles 1, 2 and 3 carry state the oracle never applied and
   their `F32` dumps (cases 1020, 1031, 1041, 1060) are excluded, counted by
   U1b. Only VEHICLE on handle 0 -- which is never copied or modified -- is
   graded.
6. **The unsigned skip advance against the shipped table.** T5 measures that
   the largest skip byte is 100, so signed and unsigned agree on **all 513** of
   them and a check built on the shipped file *cannot fail*. It is refused
   here rather than shipped as a green row. `noctis-harness/sp_bin.py` grades
   it against `NOCTIS.EXE`'s `30 E4` at file offset 54190 and against a
   synthetic table; that is a different owner pair and a different file.
7. **Anything needing the 1996 binary.** `sp_bin.py`'s 18 anchors are that
   file's job and are not duplicated here.
8. **`white_body`'s arithmetic width.** `sp_ref.c` keeps `pf` at `long double`
   and `sp_spec.py` at binary64 before an identical truncating cast. They
   agree exactly on this corpus (O2/O4) and the port agrees with both (L9),
   but no envelope and no envelope-control exists. **That is a measurement on
   one corpus, not a proof**, and it is the wave's one genuinely unbounded
   floating-point surface.

---

## 7. The known harness defects were not built on

The mandate pinned six live defects and forbade a seventh. None is on a path
this file uses:

* `fb_tick.py`'s tautological ring sweep -- not used.
* `T2.LINO.MATRIX.NULL` -- not used.
* `fb_ref.c`'s E1 pair -- not used.
* the `inrow:` escape hatch -- not used; every check here names a falsifier that
  is executed in the same run.
* `pg_grade.py`'s two void `PASS-if-tally-nonzero` rows -- not used; this file
  does not read any `pg_*` grader.
* `work/sp-break.py:281`'s `compare(clean, clean)` -- not used. This file builds
  its own eight sabotages and never runs that battery, which also means it
  never leaves `work/sp-out.bin` holding a sabotage's bytes (the QA pass's N2).

Two more of the QA pass's findings are answered rather than inherited:

* **`sp_compare`'s deletion blindness** (findings 4 and N4) -- superseded by
  `compare_dumps`, and B9/B10 demonstrate the difference.
* **`sp_compare`'s permanently-empty `SCALE` row** (finding 2c) -- superseded by
  `join_scale`, which compares 17,808 real integers and is broken by B7.

`tests/test_spheres.py` uses `linoharness.Check.ok`, which `w5audit.py` does
read, and it is inside that analyser's scope (one line added to
`scope_files()`). It has **zero findings**. One check was rewritten to earn
that honestly rather than to evade it: GP3 was originally
`if rx == dx and ry == dy: exact += 1`, which the analyser correctly flags as a
tally whose predicate is false under every random assignment. It is now
counted per component and required in both, which is the same arithmetic in a
form the analyser can watch change.

---

## 8. Open items

**O1 -- `work/spglow.txt` has no `terminator_start`.** Section 6 item 3. Both
oracles implement the wrap normalisation and the port does not. This is a
`work/` change and a corpus change, so it is a coordinator commit, not a test
change. Until then U3 keeps the absence visible.

**O2 -- `glass_bubble` / `smootharound_64` has no oracle at all.** Section 6
item 1. 176 lines of shipped port code with no second implementation. Either
`sp_spec.py` grows one -- it is integer code and cheap -- or the wave ships with
a named hole. Right now it ships with a named hole.

**O3 -- the GLOW corpus does not reach the X clip boundary.** `GLOWX9` (X low
bound 9 → 10) is uncatchable because no case produces an X of exactly 9. A
handful of GLOW cases with centres near the left edge would close it; it is a
fixture change.

**O4 -- `sp_ex1.py` prints `CONTROL: MUST be non-zero` on rows whose exit code
does not enforce it**, and under `--quick` the random/f32 control legitimately
measures 0. A test writer copying the printed label would ship an assertion
that fails on correct code. `test_spheres.py` does not use `sp_ex1.py`; the
exactness of the scaler is graded here by L12 (17,808 integers, cross-owner)
and B7. The label in `sp_ex1.py` should still be corrected by its owner.

**O5 -- `noctis-harness/spwork/` is untracked but not ignored.** `.gitignore`
has `noctis-harness/*.exe` and `noctis-harness/*.bin`, neither of which matches
a subdirectory or a `.dump`/`.page`. `test_spheres.py` writes nothing there --
its C-oracle build, dumps and page dirs all live in `tests/gen/w6b`, which *is*
ignored -- but the directory should be either ignored or cleaned.

**O6 -- the two projective models should be reconciled.** PORTPLAN.md prints one
set of constants and `sp_spec.py` ships a re-fitted one; they differ by about
0.5 % in `Fy`, 0.2 degrees in `lat0` and 0.235 in `i0`, and they score GP3 4038
versus 7614 on the same table. Both satisfy GP1 completely, so nothing is
broken, but one of the two documents is stale. Whoever owns `PORTPLAN.md`
should either adopt the re-fit or record why not; G3/G4 pin both until then.
