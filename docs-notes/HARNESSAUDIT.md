# HARNESS AUDIT -- every comparison in `noctis-harness/fb_*`

**Recon A, Wave 5c. Read-only. This file is the deliverable; a finding that lives
only in a transcript is a finding this project loses, and that has already
happened once here.**

Scope: `noctis-harness/fb_compare.py`, `fb_layout.py`, `fb_tick.py`, `fb_pal.py`,
`fb_wrap.py`, `fb_stick.py`, `fb_bmp.py`, `fb_ref.c`. Every comparison,
assertion and grading decision is enumerated below and answers one question:

> **Could this record differ between a working mechanism and a broken one?**

If the answer is no, or "only if the recording code itself changed", the check is
void. Line numbers are as of 2026-08-06.

---

## 0. Verdict vocabulary

| verdict | meaning |
|---|---|
| **SOUND** | the two sides are independently produced and the record demonstrably differs between a working and a broken mechanism |
| **TAUTOLOGICAL** | the two sides reduce to one value, or the assertion is a constant. Includes literal `True` and `x or True` |
| **CIRCULAR-STORED** | one side is read from a file the code under test wrote |
| **CIRCULAR-SELF** | the "reference" is derived *from the datum being graded*, or is the same implementation invoked twice with a flag |
| **WEAK** | not void, but falsifiable only by a mutation aimed at the check itself; carries no information about the mechanism it names |
| **DEAD** | never executed |

---

## 1. Headline result

Everything below was **measured, not read**. Commands and outputs are quoted in §6.

| | |
|---|---|
| `fb_compare.py --suite --fast` (no lino) | **103 checks, 100 passed, 1 failed, 2 NOT GRADED** |
| `fb_compare.py --suite --fast --lino ... --lino-break ×19` | **FAIL**; 19 sabotage rows, **17 of them reporting the identical catcher set** |
| the clean, un-sabotaged lino dump fed to the sabotage matrix | reported **`CAUGHT by adapted,adaptor,canary,glyph,kself,wrapcount` PASS** |
| `fb_ref.c` self-test checks never falsified by any of its 25 sabotages | **17 of 36** |
| `fb_layout.Layout.check()` checks never falsified by any of its 7 sabotages | **19 of 48** |
| `canary_v2` fields moved by any *mechanism* sabotage | `dirty_read` (11 of 44 units): **none** |
| `fb_tick.py --servo` with a do-nothing estimator | **T8a ×6, T8b ×2, T8c ×2, T8f-good, T8g ×3, T8h all PASS** |
| `ring_sweep`'s identity clause firings, all lengths, all origins | **0** |
| `grade_ticklog` on a log running 10 % fast with a header claiming 9000 cpms | **PASS** |

**The three known instances are confirmed. Eleven more are new.** The instance
count is not the point: §5 proposes the mechanical test that finds them without
anyone thinking to ask again.

---

## 2. The three known instances -- confirmed, with evidence

### 2.1 `fb_compare.py:903-957` `lino_break_matrix` -- CIRCULAR-STORED, criterion independent of the sabotage

The row's verdict is `bool(judged)`, and `judged` is built at :934 by comparing
each sabotaged lino record against `fbout/fb-ref-<name>.bin`. The **clean** lino
build already disagrees with that reference on `adapted, adaptor, canary, glyph,
kself, wrapcount` (§3.9). Therefore `judged` is non-empty for **every** input,
sabotaged or not, and the `PASS` at :946 is a hard-coded literal `True`.

The sound signal is computed and then thrown away: `moved` (:918-925) compares
the sabotage against the *clean lino's own records* and **is** sabotage-dependent
-- but it is only consulted in the `elif`, i.e. only when `judged` is empty, which
never happens.

Measured. Feeding the matrix the clean build itself:

```
      implementer 1's sabotaged builds, through this grader:
  [T2] lino sabotage fbmain      CAUGHT by adapted,adaptor,canary,glyph,kself,wrapcount PASS
```

and the real 19-row matrix, 17 rows identical:

```
  [T2] lino sabotage fbbreak4    CAUGHT by adapted,adaptor,canary,glyph,kself,wrapcount PASS
  [T2] lino sabotage fbbreak6    CAUGHT by adapted,adaptor,canary,glyph,kself,wrapcount PASS
  [T2] lino sabotage fbcanconst  CAUGHT by adapted,adaptor,canary,glyph,kself,wrapcount PASS
  [T2] lino sabotage fbmaskspot  CAUGHT by adapted,adaptor,canary,glyph,kself,wrapcount PASS
  [T2] lino sabotage fbpad9walk  CAUGHT by adapted,adaptor,canary,glyph,kself,wrapcount PASS
  [T2] lino sabotage fbsegbase   CAUGHT by adapted,adaptor,canary,glyph,kself,wrapcount PASS
  ... 11 more, byte-identical text
```

Only `fbbreak5` and `fbs12` add anything (`TICKLOG(K4c)`), and `fbbreak1/2/3/9/10`
differ only in which *already-passing* records (`lut`, `pal6`, `curpal6`,
`layout`, `zones`) additionally moved.

**Fix shape:** the criterion must be a *difference of two verdict sets* --
records the clean lino passes and the sabotage fails -- and `moved` (sabotage vs
clean lino) must be a catch, not a "blind spot" failure. A row whose catcher set
equals the clean build's failure set is by definition not a catch.

### 2.2 `fb_layout.py:1122-1124` / `fb_ref.c:384` `witness(i)` -- TAUTOLOGICAL

`witness(i)` returns the bare literal `0xC0DE0000 | i`. `canary_v2` writes it at
`off` (`fb_layout.py:1136`, `fb_ref.c:398`), runs the walker -- which never
writes -- and reads the same address back into unit 1 (`:1141` / `:406`).
`fb_ref.c:1286` then asserts `can[1] == witness(0)`: a literal compared against
itself, under a comment reading *"the dirty read is READ BACK, not written by
construction"*.

Measured. Across all ten `WORKSPACE_BREAKS`, the `dirty_read` field of all
eleven pads moves under exactly one sabotage -- `CANCONSTACTUAL`, the one written
to overwrite that field:

```
  field -> breaks that move it:
    clean_read  ['CANSTUBPOISON']
    dirty_read  ['CANCONSTACTUAL']          <- no mechanism sabotage moves it
    fired       ['CANSTUBCHECK', 'NINEWALK']
    at          ['CANSTUBCHECK', 'CANSTUBPOISON', 'NINEWALK']
  dirty_read values (clean run): C0DE0000 C0DE0001 ... C0DE000A
```

`fired` and `at` are the load-bearing fields and they are SOUND. `dirty_read` is
11 of 44 units carrying no information about the canary at all -- it is a memory
read-back test wearing a canary's clothes. `WAVE5B_CORRECTIONS.md` MAJOR 5 says
the witness "folds in the poison the walker itself wrote"; **it does not** -- the
code shipped is the bare literal, and the documented `0xB0B32000 + 17i + (clean &
255)` rule exists nowhere in `fb_layout.py` or `fb_ref.c`. The document describes
a mechanism the harness does not implement.

### 2.3 `fb_tick.py:325-347` `ring_sweep` -- TAUTOLOGICAL

```python
start = (end - want) & M32
got   = (end - start) & M32
if got != (want & M32) or want > M32: fails += 1
```

`got` is algebraically `want & M32` for every `end`. The first clause can never
fire; the verdict is the second clause, `cpms*L > 2**32`, which does not depend
on `end` at all. The advertised 9 lengths × 65 536 origins = 589 824 cases are
**nine evaluations of one inequality**.

Measured:

```
  ms=    500 want=     4499500 want>M32=False reported fails=     0  identity-only fails=0
  ms= 470000 want=  4229530000 want>M32=False reported fails=     0  identity-only fails=0
  ms= 477271 want=  4294961729 want>M32=False reported fails=     0  identity-only fails=0
  ms= 500000 want=  4499500000 want>M32=True  reported fails= 65536  identity-only fails=0
```

Both `T8b` assertions (`fb_tick.py:833-841`) therefore assert
`8999*470000 ≤ 2³²` and `8999*500000 > 2³²`. The claim in the run text --
*"unsigned subtraction across the wrap is EXACT … on all 65536 ring origins"* --
is not what was measured, and the sweep is **not** what makes `SRVMAX` a measured
limit.

`WAVE5B_CORRECTIONS.md` §CRITICAL 1 states *"the wrap sweep identities were
dropped, not extended."* They were dropped from `tests/`; they are still here,
still graded, and still the stated justification for `SRVMAX`.

---

## 3. The full table

### 3.1 `fb_compare.py` -- the grader

| file:line | what it compares | side A | side B | verdict |
|---|---|---|---|---|
| 230,233,236,244 | FBDUMP container magic / version / declared count / trailing bytes | file bytes | format literals | SOUND |
| 257-260 `diff_payload` | -- | -- | -- | **DEAD** (no caller) |
| 299-307 | KSELF reads as strictly increasing `(id,value)` pairs | payload | shape rule | SOUND |
| 309-314 | KSELF/WRAPCOUNT on the intersection of normative keys | impl A record | impl B record | SOUND |
| 343 / 348 / 350 / 353 | kind, count, geometry, tag agreement | record A | record B | SOUND |
| 358 | payload equality | record A | record B | SOUND |
| 486 | `Layout().check()` rolled up as one row | see §3.2 | | SOUND (inherits) |
| 491-493 ×7 | each `LAYOUT_BREAK` must make `check()` fail | sabotaged model | clean model | SOUND |
| 501 | `fb_ref.c` builds with no `-Wall -Wextra` warning | gcc output | literal | SOUND |
| 505 | `fb_ref.exe` self-test return code | see §3.7 | | SOUND (inherits) |
| 514-516 ×11 | Python record == C record, exact | `fb_layout/fb_pal` (parses 1996 sources) | `fb_ref.c` (transcribes them) | **SOUND** -- the strongest thing in the harness |
| 527-530 | alias 8: KSELF 7/8/9 vs `Layout().alias8()` | C transcribes `0xFA00` | Python parses `0xFA00` | SOUND on placement; **premise `SEG_OFFSET==4` is shared by both sides** (Tier 0, declared) |
| 531 | Tier 0 declaration | -- | -- | NOT GRADED, correctly |
| 538 | 15 986 of 32 000 sea texels overrun `n_globes_map` | measurement | `> 0` | SOUND |
| 541 | 5 of those land in a pad | measurement | `> 0` | SOUND |
| 544 | `(violations, expectations) == (0, 6)` | walker output | literal | SOUND (`DIGITN1` → 0) |
| 549 | 1 unit past `n_globes_map` → exactly 1 TAIL violation | walker output | literal | SOUND |
| 556-576 | canary v1 is bit-identical under sabotages v2 catches | v1 record | v2 record, same workspace, same sabotage | SOUND -- a model demonstration |
| 579-588 ×10 | each `WORKSPACE_BREAK` moves ≥1 graded record | sabotaged Python | clean Python | SOUND (mutation test) |
| 593 | `fb_pal.selftest()` | see §3.4 | | SOUND (inherits) |
| 598 | `fb_tick --wrap-sweep` | see §3.3 | | SOUND (inherits) |
| 601 | `fb_wrap.run()` | see §3.5 | | mixed (inherits) |
| 619-638 ×25 | each `-DBREAK_*` build must move its named target record | sabotaged C, fresh run | clean C, fresh run | **SOUND** -- nothing stored, both sides rebuilt |
| **651** | "capture artifacts present (n BMP, m PNG)" | -- | **literal `True`** | **TAUTOLOGICAL** -- cannot fail; the real check is 650 |
| 663-669 | BMP is ×4-scaled, PNG is shift-or-scaled, mutually exclusive | 1996/DOSBox artifact | arithmetic predicate | **SOUND** -- Tier 1, external |
| 674-678 | BMP pal6 == PNG pal6 on all 768 components | artifact 1 | artifact 2 | SOUND -- two independent captures |
| 681-688 | band 0-63 fits `v*f/63`; round-to-nearest and `/64` fit nothing | artifact | falsifiers | SOUND -- falsified both ways |
| 691-693 | PNG 2×2 doubling, 0 non-uniform subpixels | artifact | literal | SOUND |
| 695-702 | two snapshots differ in pixels but not in palette | artifact 1 | artifact 2 | SOUND |
| 724 | clean tick loop passes K1..K5 | `fb_tick.run_loop` | `fb_tick.grade_ticklog` | **CIRCULAR-SELF** -- simulator and grader are the same module. Valid as a grader self-test, not as evidence about any port; see §3.3 K2/K3 |
| 733 | `NOCARRY` caught in a 400-tick log | sabotaged sim | grader | SOUND |
| 739 | a legitimate 1-count servo step is accepted | sim | grader | SOUND |
| 746 | a 5 % cpms lurch is rejected | sim | grader | SOUND |
| 750 ×3 | `REBASE`/`NOSKIP`/`ROUND55` rejected | sabotaged sim | grader | SOUND |
| 757 | `fb_tick --servo` battery | see §3.3 | | **mixed -- 3 of 8 legs void** |
| 761 ×6 | each servo sabotage is rejected | sabotaged | grader | SOUND |
| 768 ×5 | each `fb_wrap` sabotage is rejected | sabotaged | `run()` | SOUND |
| 770/772 | `fb_stick` A1 proof and its `CLIPSTAGE` sabotage | model | swept bbox | SOUND |
| 775 | `fb_stick` A2 corpus | see §3.6 | | mixed |
| 790-793 | LINOBUF 6.1 "carries every scenario constant" | 20 substrings | a doc section | **WEAK / MIS-TARGETED** -- see §4.6 |
| 806 | lino dump exists | filesystem | -- | SOUND |
| 816 | lino dump is FBDUMP v2 | header | literal | SOUND |
| 834-845 ×11 | lino record == C **and** == Python | lino | two references rebuilt this run | SOUND |
| 854 | lino TICKLOG passes K1..K5 | lino log | `grade_ticklog` | SOUND *as a cross-implementation check*, but see §3.3 K2/K3 for what it cannot see |
| 866 | lino SERVOLOG passes S1..S6 | lino log | `grade_servolog` | SOUND cross-implementation |
| 873 | SERVOLOG missing → NOT GRADED | -- | -- | correct |
| 888 | undefined kind emitted → NOT GRADED | -- | -- | correct |
| **903-957** | **the lino sabotage matrix** | sabotaged lino | **`fbout/fb-ref-*.bin`, which the clean lino already fails** | **CIRCULAR-STORED -- see §2.1** |
| 946 | the matrix's PASS | -- | **literal `True`** | TAUTOLOGICAL |

### 3.2 `fb_layout.py` -- `Layout.check()`, 48 checks

| file:line | check | verdict |
|---|---|---|
| 564 | **L1** `want == got` where `got` is built by iterating `want` (`seq = list(self.alloc)`, :382) | **TAUTOLOGICAL** except under `ORDER`/`SWAPSEA`, which permute `seq` before the copy |
| 568-569 | **L2** `a.end <= b.padbase` and `b.base - a.end == self.pad`, ×16 | **TAUTOLOGICAL** -- the constructor is `cur += pad; base = cur; cur += size`. Under `NOPAD` it reads `0 == 0` and still passes |
| 574 ×5 | **L3** 64 KiB readable window fits above each `txtr` base | SOUND (property of parsed sizes) |
| 580-586 | **L4** `p_surfacemap-6..-1` lie in that region's own SUB zone | WEAK -- construction under no break; falsified by `NOPAD`/`ONEZONE` |
| 595-599 | **L5** `adapted`/`adaptor`/`p_background` ≥ 65536; `adaptor` segoff 0 | SOUND (parsed sizes vs literal) |
| 604-606 | **L6** the three class-C neighbour relations | SOUND (falsified by `SWAPSEA`) |
| 611 | **L7** `objectschart > 32772` | SOUND |
| 616 | **L8** heap total == 336 480 | **SOUND** -- parsed sum vs an external literal |
| 622-636 | **L9** 11 pads / 22 zones / 18 owned / two magics / origins in own SUB | WEAK -- construction counts; falsified by `NOPAD`/`ONEZONE` |
| 642-650 | **L10** `adapted`'s window ends below its end; `objectschart`'s spans `adapted` | SOUND |
| 657-666 | **L11** QUADWORDS 16000/14560 parsed; `mask_pixels` DI < 65536 | SOUND (parse vs literal) |
| 670 | **L12a** alias 8 == `adapted[63996]` row 199 col 316 | SOUND as a pin; rests on the Tier-0 `SEG_OFFSET` |
| **675** | **L12b** `a8["nw"] == self.seg_index("adapted", self.alias8_segoff)` -- and `alias8()` **returns** exactly `self.seg_index("adapted", self.alias8_segoff)` (:539) | **TAUTOLOGICAL -- `x == x`, unfalsifiable by any edit** |
| 683 | **L13a** poly3d clamp keeps `y` in 0..199 | SOUND |
| 688 | **L13b** highest Segmento address == 61115 | SOUND (literal pin) |
| **696** | **L14** `((0-320) & 0xFFFFFFFF) >= 64000` | **TAUTOLOGICAL -- a Python arithmetic fact referencing no subject at all** |

**Measured mutation coverage: 19 of the 48 messages are never falsified by any of
the 7 available layout sabotages.** Twelve of those nineteen are L2 gap
identities. The rest are legitimate constant-pins (L3, L5, L11, L13) that a
source edit would catch but a sabotage set does not contain.

### 3.3 `fb_tick.py`

| file:line | check | verdict |
|---|---|---|
| 39-40 | `PERIOD_MS == 32768000/596591` and `55 - 44505/596591 == PERIOD_MS` | SOUND (module-load assertions, exact rationals) |
| 735-737 | **A1** decomposition tracks the exact rational within 1 count, 7 cpms values | **SOUND** -- 32-bit decomposition vs unbounded `Fraction`, genuinely different constructions |
| 738 | **A2** largest intermediate fits int32 | SOUND |
| 741 | **A3** period takes ≤2 adjacent values | SOUND |
| 750 | **A2b** overflow ceiling is exactly 48239 | SOUND (two-sided) |
| 759 | **A4** `9000*552086 > 2³¹` | SOUND (states the straw man is real) |
| 769-776 | **A5** carry bounds the error; without it error grows 3191 → 25533 counts | **SOUND** -- the growth is measured, not asserted |
| 133-158, 786 | wrap sweep of `expired()` against unbounded-integer truth, 1.5 M cases | **SOUND** -- the truth side is independent |
| 810-827 | **T8a** window-length battery, 6 rows | **TAUTOLOGICAL on the value axis.** `Servo` is seeded **at** the true rate (`Servo(TRUE)`, and `counts += TRUE*L`), so "cpms within 1 of TRUE" is satisfied by an estimator that returns its seed. Measured: a do-nothing estimator passes all six rows. Only the `why` column carries signal |
| **833-841** | **T8b** the ring sweep | **TAUTOLOGICAL -- §2.3** |
| 850-859 | **T8c** midnight refusal + fold monotone (`86399900 → 86400100, Δ200`) | SOUND (falsified by `WALLNOFOLD`) |
| 872 | **T8d** rounded vs truncated differ by exactly 1 cpms | CIRCULAR-SELF in form (same function, flag flipped) but the expected pair `(TRUE+1, TRUE)` is independently checkable arithmetic → SOUND in substance |
| 886 | **T8e** clamp floor: from cpms 99 the servo climbs | SOUND |
| 900 | **T8f-good** windowed servo over 20 min, worst error 0.0000 % | **TAUTOLOGICAL** -- `servo_replay` seeds `Servo(true_cpms)` (:360) and feeds it `true_cpms`-derived counts. Measured: a do-nothing estimator scores worst error 0.0000 %, 0.00 s/hour and PASSES. Contrast `tests/w5probe.txt`, which seeds 4 % low precisely so "do nothing" cannot pass -- the harness leg does not do this |
| 907 | **T8f-bad** the shipped run-start bracket collapses on the same input | **SOUND -- this is the leg that carries the whole servo claim** |
| 918/921/926 | **T8g** `cal_end` clean / midnight / zero brackets | SOUND (literal expectations) |
| 940 | **T8h** `grade_servolog(s.payload())` | **CIRCULAR-SELF** -- S4's bound `max(1, cpms//100)` is *exactly* `Servo.fire`'s own clamp (:274-281), S5's window is exactly `cal_end`'s, S6 is enforced by the clamp floor. On `Servo` output S1-S6 cannot fail. Measured: passes with a do-nothing estimator. Sound only when `grade_servolog` is pointed at a **lino** SERVOLOG |
| 413-436 | **S1..S6** as a grader of foreign logs | SOUND in that role |
| 581-583 | **K1** tick count | SOUND |
| 590-597 | **K2** every deadline step is a whole period within 1 count | **CIRCULAR-SELF (partial):** `icpms` is recovered *from* `dgaps` (:548-553) and the reference `exact` is `round(icpms)*PERIOD_MS`. The check therefore asks "is the implied cpms near an integer?", never "is it the right cpms". The header's `cpms` is used only as a divisor for reporting |
| 603 | **K3** accumulated drift ≤ 1 count per constant-cpms run | same self-derived reference as K2 |
| 613 | **K3b** cpms spread within 1 % *within one log* | SOUND for its claim |
| 642 | **K4** next deadline strictly future; skip flag agrees with `k` | SOUND |
| 655 | **K4c** no back-to-back fire after a hitch | SOUND |
| 662 | **K5** no fire precedes its deadline | SOUND |

> **Measured consequence of K2/K3's self-derived reference:** a 400-tick log
> generated at **9900 cpms** and written with a header claiming **9000** is graded
> **PASS**, with the segment report cheerfully printing `cpms [9900]`.
> ```
>   real cpms  9000, header says 9000 -> grade PASS  segments cpms [9000]  fails -
>   real cpms  9900, header says 9000 -> grade PASS  segments cpms [9900]  fails -
>   real cpms  4500, header says 9000 -> grade FAIL  fails ['K4c']
>   real cpms 18000, header says 9000 -> grade FAIL  fails ['K4']
> ```
> A port whose tick runs 10 % fast passes `grade_ticklog`. It is caught only by
> a factor-of-two error, and then by accident (the work-time floor, not the
> period). **No check compares the log's implied cpms against the header's.**

### 3.4 `fb_pal.py` -- `selftest()`, 22 checks

| file:line | check | verdict |
|---|---|---|
| 543 | **P1** generated `range8088` == the literal parsed out of NOCTIS-0.CPP | **SOUND** -- two constructions of the same table |
| 549-550 | **P2** upload span is `[0,384)`; 128..255 left stale | SOUND (literal) |
| 557 | **P3** self-copy compounds; expected side uses a **clean** `Palette().filter_one` | SOUND (the clean reference is the right call; C's twin is not -- see §3.7 S2) |
| 563-565 | **P4** shade truncates 62.75→62, −1→0, 64→63 | SOUND (literals) |
| 570 | **P5** LUT (63,32,0) → `0x00FC8000` | SOUND |
| 575-583 | **P6** `schar(200) == -56`; the modular-unsigned filter | SOUND |
| 588-598 | **P7** four filter identities against literals | SOUND |
| 602 | **P8** 21 shade sites, 14 `surface_palette`, 7 `tmppal` | **SOUND** -- regex over the 1996 source vs a literal; this is how "17 of 24" was caught as stale |
| 607/612 | **P8** shade's destination parameter is general | SOUND |
| 620 | **P9** srfpal6 read unsigned | SOUND |
| 626-628 | **P10** two fades do not compound; `want` uses a **clean** `filter_one` | SOUND |
| 633-646 | **P11** three exhaustive proofs (trap 2 unreachable, DOS16 == C32 on 65 536 pairs, PYFILT diverges on exactly 8064) | **SOUND** -- each has a real possible answer other than the asserted one |
| 470-496 | `fit_filter` / `tier1_palette_audit` against a capture | SOUND (external observed side, falsifiers reported) |
| 502-529 | `separation_matrix` | reporting, not grading; **honest** -- it prints two of the fixture's own claims that do **not** hold |

`fb_pal.py` is the cleanest file in the harness. No tautologies found.

### 3.5 `fb_wrap.py` -- `run()`, 15 checks

| file:line | check | verdict |
|---|---|---|
| 302 | **W1** `spot` naive − masked == 65536 | **WEAK/TAUTOLOGICAL** -- `n − (n mod 65536) == 65536` is an identity for any `n ∈ [65536, 131072)`. The value can never be anything else for any masked implementation; the check reduces to "is a mask present", which `MASKSPOT` already answers |
| 307 | **W1** `cirrus` delta == 32768 | same shape |
| 315 | **W1** masking the address ≠ masking the truncation point | SOUND (two branches, real difference) |
| 325-332 ×2 | **W2** the unmasked index leaves its own buffer | SOUND (layout property) |
| 339/343 | **W2b** `126739 → NW 231727 = objectschart+21155`, `63911 → NW 274483 = adapted+3399` | **PROVENANCE UNVERIFIED** -- the literals are "the architect's recon" numbers. If that recon derived them from this same layout model, the check is the same implementation invoked twice. It pins the layout either way, so keep it, but the provenance must be established or the row downgraded |
| 361 | **W3** every masked address is inside its region or its own SUB, 340 cases | **TAUTOLOGICAL over its corpus.** `mask = segbase + u16(x)` spans `[segbase, segbase+65535]`; every region involved is ≥ 65536 with `base = segbase+4`, so containment holds for **every** input, not just the 340. `WAVE5B_CORRECTIONS.md` §CRITICAL 2 admits this for `tests/`' M5 and requires the detail text to say so; **fb_wrap.py's W3 text carries no such disclaimer** and reads as empirical coverage |
| 376 | **W3b** `px = 65536-k, k=1..4` folds onto segment offsets 3,2,1,0 | **TAUTOLOGICAL** -- computed `segbase + u16(4-k+65536)` vs wanted `segbase + (4-k)`: the same expression. Falsifiable only by `SEGADDRBASE` |
| 387/395 | **W4** exhaustive escape census, `escapes > 0` | SOUND (0 was a possible answer). Caveat: `escape_census` counts by closed form (`n = min(360, floor(-1-c)+1)`, :210) rather than enumerating `cx`, so an error in the closed form is unfalsifiable |
| 399 | **W4** `py` is never a wrap source | **SCOPE OVERSTATED** -- the text claims "every one of the (cr,g,angle,cy) boundary cases" but `py_never_wraps` (:225) samples `cy ∈ {cr, 177-cr}` only, i.e. the two endpoints of a range |
| 408 | **W5** crater rate `c3 > c2 > 0` | SOUND |
| **416** | **W6** `req(m != n or True, …)` | **TAUTOLOGICAL -- literally the constant `True`.** No build, edit or sabotage can fail it |
| 425/428 | **W7** unsigned `ptr` terminates at 200, signed never | SOUND |

### 3.6 `fb_stick.py`

| file:line | check | verdict |
|---|---|---|
| 314 | **A1** `nbad == 0` over the swept bounding boxes | SOUND (falsified by `CLIPSTAGE`) |
| 338 | **A2** `escaped > 0` over a 400 k deterministic corpus | SOUND |
| 344 | **A2** every escape had a skipped stage (the mechanism) | SOUND -- a real claim about causation |
| **352** | **A2** "worst escape: …" -- `req(True, …)` | **TAUTOLOGICAL** -- a print statement counted as a passing check |
| 357 | **A2** `bool(c["rows"])` | WEAK (implied by `escaped > 0`) |
| **360** | **A2 NOTE:** "recon B reports 220/98 596 …" -- `req(True, …)` | **TAUTOLOGICAL** -- a print statement counted as a passing check. It even *states* a cross-check against recon B and then does not perform it |

### 3.7 `fb_ref.c` -- the C reference's own self-test, 36 checks

| file:line | check | verdict |
|---|---|---|
| 1163-1166 | **B1-B3** byte store/mask/sign-extend | SOUND (literals); no sabotage reaches them |
| 1173/1176 | **B4** quadrant bitfield | SOUND (literals) |
| 1182 | **B5** one byte per unit | SOUND (falsified by `PACK4`) |
| **1193** | **A1 spot** `n - m == 65536 \|\| site_wraps[SITE_SPOT] == 0` | **TAUTOLOGICAL under the sabotage it names.** `BREAK_MASKSPOT` sets `masked = naive`, so `site_wraps == 0` and the escape clause passes the check. Measured, from a real `-DBREAK_MASKSPOT` build: `PASS A1 spot py=61200 px=65535: masked NW 231723, naive NW 231723, delta 0`. The sabotage is caught by A2/A3/E2 instead -- but A1, the check that names the mask, is disarmed by its own `\|\|` |
| **1197** | **A1 cirrus** same `\|\| site_wraps == 0` escape | same |
| 1203 | **A1** the unmasked cirrus address lands off-buffer | never falsified by any sabotage |
| 1217 | **A2** `k=1..4` folds onto segment offsets 3..0 | SOUND (falsified by `MASKSPOT`, `SEGADDRBASE`, `PADONEMAGIC`) |
| 1222 | **A3** containment, `site_contain_fail == 0` | SOUND *here* (unlike Python's W3, the C battery includes unmasked sabotages that escape) |
| 1229 | **A4** alias 8 == `adapted[63996]` | SOUND (falsified by `SEGADDRBASE`) |
| 1238 | **A5** A7 typing | SOUND (literal) |
| 1249 | **P1** 22 zones | SOUND (falsified by `PADONEMAGIC`) |
| **1252** | **P1** "a freshly poisoned workspace reports 0 violations and 0 expectations" | **TAUTOLOGICAL** -- `poison_pads` writes `zone_magic(z)` and `walk_pads` skips units equal to `zone_magic(z)`. Write X, then check X. `PADONEMAGIC` changes both sides consistently and it still passes |
| 1262 | **P2** one glyph → 0 violations, exactly 6 expectations | **SOUND** -- the count is derived from what the program did |
| 1271 | **P3** one unit past `n_globes_map` → 1 TAIL violation at the right NW | SOUND |
| 1284 | **C1** every pad reports its own probe fired | **SOUND** -- the load-bearing canary check |
| **1286** | **C1** `can[1] == witness(0)` | **TAUTOLOGICAL -- §2.2** |
| 1290 | **C1** `can[3] == padbase[0]+probeslot(0) && can[3] != 0` | WEAK -- identity except that a stubbed walker sends it to 0 |
| 1310 | **T1** 4096 ticks total vs an exact int64 formula | **SOUND** -- independent construction |
| 1313 | **T1** ≤2 adjacent period values | SOUND |
| 1314-1316 | **T2** three wait-predicate literals | SOUND (falsified by `TICKCMP`, except the sign-boundary row) |
| 1321/1322 | **S1** `schar(200) == -56`; `filter_one(1,-56) == 63` | SOUND. Note: the second **passes under `BREAK_DIV64`** (65480/64 = 1023, still clamped to 63) |
| 1331 | **S1** trap 2 unreachable | SOUND |
| 1341/1351 | **S1** shade destination general; srfpal6 read unsigned | SOUND |
| **1367** | **S2** `cmp_got == cmp_want`, where `cmp_want` at :947 is built with **the same `#ifdef`'d `filter_one`** as the code under test | **CIRCULAR-SELF on the filter axis.** Under `BREAK_DIV64` both sides use `/64` and S2 passes. Measured: `BREAK_DIV64 caught by curpal6,kself,lut,pal6` -- **no `selftest`**, i.e. the C self-test is completely blind to it. Python's twin (P10, :459) avoids this by building `want` from a *clean* `Palette()` |
| **1383** | **E1** `FB[i] == PAL[nw_get(adaptor+i)]` for all 64 000 | **TAUTOLOGICAL -- `present_expand` (:668) is literally `FB[i] = PAL[nw_get(src+i)]`.** The check re-executes the assignment it is checking. Never falsified by any of the 25 sabotages |
| 1385 | **E2** the wrap battery actually wrapped | SOUND |
| 1389 | **E2** containment after the battery | SOUND (falsified by 4 sabotages) |

**Measured mutation coverage: 17 of 36 self-test checks are never falsified by
any of the 25 sabotages.** Several of those are legitimate literal pins (B1-B4,
T1, S1) that a source edit would catch. Four are structurally unable to fail:
A1×2 (escape clause), P1-poison, E1.

### 3.8 `fb_bmp.py`

| file:line | check | verdict |
|---|---|---|
| 47/52-55 | BMP signature, bpp, planes, compression | SOUND (format validation) |
| 160/177/181 | PNG depth/interlace/colour-type/PLTE/geometry | SOUND |
| 185-193 | every 2×2 block uniform, else "not a raw mode-13h dump" | **SOUND** -- refuses the oracle rather than resampling it |
| 237-239 | `consistent_with_x4` / `consistent_with_shift_or`, both reported | **SOUND** -- falsifiable in both directions, which is why the Tier 1 row means something |

No defects. This file is the only genuinely external oracle in the harness and it
is handled correctly.

### 3.9 The `ADAPTED` disagreement -- what is actually being compared

`fb_compare --suite --lino` reports `lino ADAPTED != C (63988 of 64000 units
differ)`. The twelve agreeing units are **all zero** and agree by coincidence:

```
agree: 12 units; indices [58246, 58502, 59016, 59634, 60308, 60862,
                          61118, 61504, 62314, 62732, 62988, 63606]
values at those: all 0
lino value histogram (top 5): 127×3546, 95×2826, 79×2347, 111×2346, 119×1867
C    value histogram (top 5):   0×28715,  7×17279, 44×322, 35×310, 32×306
```

The C page is dominated by `0` (from `pclear(adaptor,0)`) and `7` (from
`pclear(adapted,7)`); the lino page contains neither in quantity. **These are not
two implementations of one scenario that disagree; they are two different
scenarios.** The comparison is therefore not a graded check at all -- it is a
category error dressed as a FAIL, and it will stay FAIL under every possible
correct implementation of either fixture.

Same category for `ADAPTOR`, `GLYPH`, `CANARY`, `KSELF`, `WRAPCOUNT`. `PAL6`,
`CURPAL6`, `LUT`, `LAYOUT`, `ZONES` pass, because the palette scenario *is*
shared and the layout is scenario-free.

**This is what makes §2.1 possible:** the six permanently-failing records are
exactly the catcher set every sabotage row reports.

---

## 4. New findings, ranked

| # | finding | file:line | class |
|---|---|---|---|
| 1 | The sabotage matrix's pass criterion does not depend on the sabotage; the clean build is reported CAUGHT | `fb_compare.py:903-957` | CIRCULAR-STORED |
| 2 | `witness(i)` is a bare literal; `dirty_read` (11 of 44 canary units) moves under no mechanism sabotage. The documented `0xB0B32000+17i+(clean&255)` rule is not implemented anywhere | `fb_layout.py:1123`, `fb_ref.c:384,1286` | TAUTOLOGICAL |
| 3 | `ring_sweep`'s identity clause never fires; 589 824 "cases" are 9 evaluations of one inequality; it is the stated basis for `SRVMAX` | `fb_tick.py:325-347, 833-841` | TAUTOLOGICAL |
| 4 | **`fb_ref.c` A1 is disarmed by its own escape clause under `BREAK_MASKSPOT` -- measured PASS with `delta 0`** | `fb_ref.c:1193,1197` | TAUTOLOGICAL |
| 5 | **`E1` re-executes the assignment it checks** | `fb_ref.c:1383` vs `:668` | TAUTOLOGICAL |
| 6 | **`grade_ticklog` recovers cpms from the log and never compares it to the header -- a 10 %-fast tick passes** | `fb_tick.py:548-606` | CIRCULAR-SELF |
| 7 | **`T8a` and `T8f-good` seed the servo AT the true rate; a do-nothing estimator passes both** | `fb_tick.py:810-827, 900` | TAUTOLOGICAL |
| 8 | **`T8h` grades `Servo` output with bounds that are `Servo`'s own clamp rules -- S1..S6 cannot fail on it** | `fb_tick.py:940` | CIRCULAR-SELF |
| 9 | **`fb_ref.c` S2 builds its `want` with the sabotaged `filter_one`; the C self-test is blind to `BREAK_DIV64`** | `fb_ref.c:947,1367` | CIRCULAR-SELF |
| 10 | **Four unconditional `True` checks inflate the pass count** | `fb_wrap.py:416`, `fb_stick.py:352,360`, `fb_compare.py:651` | TAUTOLOGICAL |
| 11 | **`L12b` is `x == x`; `L14` references no subject** | `fb_layout.py:675,696` | TAUTOLOGICAL |
| 12 | **`W3`/`W3b` are true for every input, not just their 340-case corpus, and say otherwise** | `fb_wrap.py:361,376` | TAUTOLOGICAL |
| 13 | **`P1`-poison is write-X-check-X** | `fb_ref.c:1252` | TAUTOLOGICAL |
| 14 | **L1 and L2 are constructor identities** (`got` built by iterating `want`; `gap == PAD` by construction, and `0 == 0` under `NOPAD`) | `fb_layout.py:564,568-569` | TAUTOLOGICAL |
| 15 | **The LINOBUF 6.1 check now grades the wrong section** | `fb_compare.py:198-199, 790` | see §4.6 |
| 16 | `py_never_wraps` samples two `cy` endpoints while the text claims "every one of the … cases" | `fb_wrap.py:225,399` | scope overstated |
| 17 | `escape_census` counts by closed form, not enumeration -- a closed-form error is unfalsifiable | `fb_wrap.py:210` | unfalsifiable sub-computation |
| 18 | `W2b`'s "recon cross-check" literals have unverified provenance | `fb_wrap.py:337-346` | provenance |

### 4.6 The LINOBUF 6.1 check, in detail

`read_linobuf_61` (`fb_compare.py:198`) matches any line starting `### 6.1`.
`LINOBUF.md`'s §6.1 is **"FBDUMP v2 -- what v1 got wrong, and the corrected record
set"** -- the record format, not a fixture. The check then hunts 20 scenario
constants in it and reports **FAIL, 16 missing**:

```
present (4): ['16', '63', '64', '200']
missing (16): ['range8088','32','0.984375','192','50','60','55','160',
               '19.5','24.75','66.25','14560','63996','1996','517','1031']
```

Two things are wrong. First, the verdict flipped from `NOT GRADED` to `FAIL`
**because an unrelated section acquired the number 6.1**, not because anything
about the scenario changed -- a check whose signal is document numbering.
`WAVE5B_CORRECTIONS.md` MAJOR 4 already records that §6.1 is the record set and
not a fixture; the code was never told. Second, the four "present" markers are
`16`, `63`, `64`, `200` -- bare integers that appear in essentially any technical
prose (13 of the 20 appear *somewhere* in `LINOBUF.md`). Substring-matching bare
integers against a document is close to unfalsifiable in the passing direction
and meaningless in the failing one.

This is the **only failing row** in the no-lino suite run (`103 checks, 100
passed, 1 failed, 2 NOT GRADED`). The suite's headline FAIL is therefore
currently produced by a mis-targeted documentary check, not by any measurement.

---

## 5. The mechanical test -- so a future wave does not have to think of asking

Every finding above except §4.15-4.18 is detectable by **one property**:

> A graded check must be falsified by at least one available mutation.
> A check that survives every mutation is either a constant pin (declare it) or
> it is void.

Two prototypes were written and run for this recon. Both are ~30 lines and both
found real defects on their first execution. Proposed as
`noctis-harness/fb_mutcov.py`, run as a suite row that **fails** when the
never-falsified set changes.

### 5.1 Mutation coverage -- the core test

For each check *c* and each available mutation *m*, record `passed(c, m)`.
Then:

```
NEVER-FALSIFIED(c)  ==  for all m: passed(c, m)
```

Every never-falsified check must appear in an explicit, checked-in
`EXEMPT` list with a stated reason, exactly as `tests/test_wave5.py`'s
"every graded check is proved breakable" does for its six exemptions. The
suite row fails when the measured set differs from `EXEMPT` **in either
direction** -- a new void check fails, and a check that becomes breakable
must be removed from the list.

Measured today, with no exemption list at all:

```
Layout.check():   48 checks, 19 NEVER falsified by any of the 7 layout sabotages
fb_ref.c selftest: 36 checks, 17 NEVER falsified by any of the 25 sabotages
```

Implementation notes that matter:

* Key each check by its message with all digits replaced by `#` -- the messages
  interpolate measured values, so raw-string keying breaks immediately. Both
  prototypes do `re.sub(r'[-+]?\d[\d,\.]*','#',msg)`.
* A check **absent** under a mutation counts as falsified, but tag it
  `(absent)` -- a check that stops being emitted is a different event from one
  that fails, and the layout sweep shows twelve of those.
* Cost: `Layout.check()` sweep is under a second. The `fb_ref.c` sweep is 25
  gcc builds, ~90 s, and the suite already performs those builds in
  `tier2_sabotage` -- the coverage matrix is free if it reuses them.

### 5.2 Three cheap static lints, run over `fb_*.py` and `fb_*.c`

1. **Unconditional assertions.** Grep for `req(True`, `rec(..., True)`,
   `or True`, `assert True`, `|| <expr that the sabotage makes true>`. Today:
   `fb_wrap.py:416`, `fb_stick.py:352`, `fb_stick.py:360`, `fb_compare.py:651`,
   `fb_compare.py:946`, and the two `||` escape clauses at `fb_ref.c:1193,1197`.
   The `||` form needs a human eye; the literal forms do not.
2. **Syntactic self-comparison.** Flag any comparison whose two sides normalise
   to the same expression tree. Catches `fb_layout.py:675` (`a8["nw"] ==
   seg_index(...)` where `alias8()` *is* `seg_index(...)`) and
   `fb_ref.c:1383`/`:668`.
3. **Expected-side provenance.** Any `want`/`expected` computed by calling the
   same function the subject calls, under the same `#ifdef`/`breaks` set, is
   circular. Catches `fb_ref.c:947`. The correct pattern is already in the tree:
   `fb_pal.py:459` builds `want` from a **clean** `Palette()`.

### 5.3 The null-input test -- the cheapest of all

**Feed every grading matrix an input that is not sabotaged and require it to
report NOT CAUGHT.** One line per matrix. Today:

```python
Suite(linosrc=CLEAN, linobreaks=[CLEAN]).lino_break_matrix(read_container(CLEAN))
# ->  lino sabotage fbmain  CAUGHT by adapted,adaptor,canary,glyph,kself,wrapcount  PASS
```

That single call is the whole of §2.1. The same shape catches §4.7 (drive the
servo battery with a do-nothing estimator; it must fail) and §4.6-adjacent
problems generally. **A grader that cannot tell a clean build from a broken one
has no business grading either.**

### 5.4 Round-trip invariance probes for self-derived references

For every grader that recovers a parameter from the datum it is grading
(`grade_ticklog`'s `icpms`, `grade_servolog`'s implied bounds), assert that
**changing the true parameter changes the verdict**:

```python
for real in (9000, 9900, 4500, 18000):
    log = run_loop(real, work); write_ticklog(p, log, cpms=9000, ...)
    assert grade_ticklog(p)[0] == (real == 9000)   # fails today at 9900
```

---

## 6. Reproduction

All figures above were produced by these commands on 2026-08-06, from
`C:\programmieren\linoleum\noctis-harness`.

```
python fb_compare.py --suite --fast
  -> TOTAL 103 checks, 100 passed, 1 failed, 2 NOT GRADED   RESULT: FAIL
     the single failure is the LINOBUF 6.1 marker row (§4.6)

python fb_compare.py --suite --fast --lino ../work/fbmain.bin \
       --lino-break '../work/fbbreak*.bin' --lino-break '../work/fbcan*.bin' \
       --lino-break '../work/fbmask*.bin'  --lino-break '../work/fbpad*.bin' \
       --lino-break '../work/fbs12.bin'    --lino-break '../work/fbsegbase.bin'
  -> 19 sabotage rows, 17 with the identical catcher set

gcc -std=c99 -O2 -DBREAK_MASKSPOT -o fb_brk_ms.exe fb_ref.c && ./fb_brk_ms.exe ...
  -> PASS  A1 spot py=61200 px=65535: masked NW 231723, naive NW 231723, delta 0
  -> FAIL  A2 ...   FAIL  A3 ...   FAIL  E2 ...   PASS  E1 ...
```

The four ad-hoc probes (ring-sweep identity, do-nothing estimator, ticklog rate
invariance, canary field sensitivity, and the two mutation-coverage sweeps) are
reproduced verbatim in §2 and §3; each is under 30 lines and none writes to the
tree. They are the seed of `fb_mutcov.py` in §5.

---

## 7. What this audit does NOT claim

* It does not re-grade the buffer model, the layout, the servo arithmetic or the
  palette pipeline. `BUFFERMAP.md`, the corrected tick servo and
  `tests/test_wave5.py`'s own canary and 23-sabotage battery are out of scope by
  the wave brief and nothing here contradicts them.
* `fb_pal.py` and `fb_bmp.py` are clean. The Tier 1 palette evidence against the
  1996 BMP is the soundest thing in the harness and none of the findings touch it.
* The 25-sabotage C matrix (`fb_compare.py:610-641`) is **sound** -- both sides
  rebuilt every run, nothing stored, and the target record must move. It is the
  model the lino matrix should have copied and did not.
* Finding counts are a floor, not a ceiling. §5 exists because the next one will
  be in a file nobody thought to point at.

---

## 8. Wave 5c addendum -- the rule, executed (`tests/w5audit.py`)

Sections 5.1-5.3 above propose the mechanical test. This section records what
was actually built, what it found on its first run, and what was deleted.

**The rule is no longer a sentence.** `tests/w5audit.py` runs inside
`tests/test_wave5.py`, which is entry 17 of `tests/run_all.py`, so the suite
fails when a check that cannot fail is added. It costs 2.4 s.

### 8.1 Why it is not a fourth lint rule

`fb_lint.py` is a **name filter**: it looks for a local called `want` and one
called `got` and asks whether one function produced both. Rename them and it
goes silent. That is measured, every run, by `w5audit.lint_blindness()`:

```
same_producer: fb_lint 1 finding(s), renamed 0; this audit 1 and 1
ring_sweep:    fb_lint 0 finding(s), renamed 0; this audit 1 and 1
```

The renamed snippet is the same computation with `want` to `reference` and
`got` to `subject`. `fb_lint` returns **zero** findings on it. So does it on the
shipped ring sweep, under either name.

`w5audit` never reads a name. For every check condition in
`noctis-harness/fb_*.py`, `fbx_*.py` and `tests/`, it

1. **inlines** every single-assignment local, module constant and
   single-`return` module function into the condition, transitively;
2. **atomises** what is left -- a call, an attribute, a subscript -- keyed by its
   source text, so two spellings of `filter_one(data)` become **one atom taking
   one value**. That is what turns "both sides came from the same producer" into
   a measurement instead of a guess about naming;
3. **executes** the condition over 300 random assignments drawn from a spread
   that includes every integer literal in the condition itself, plus and minus
   one -- so `if bpp != 8` is sampled *at 8* and is not mistaken for a tautology.

Three rules fire:

| rule | fires when | the shape it kills |
|---|---|---|
| **A** | the condition is TRUE under every assignment | `req(True)`, `x or True`, two literals compared |
| **B** | one side's atom set strictly **contains** the other's, and the predicate's truth never changes when the non-shared atoms vary | *the sweep whose axis carries nothing* -- instance 3 |
| **C** | a tally -- `if <pred>: fails += 1` -- whose predicate is FALSE under every assignment | *"0 of 65,536" that would read 0 of 65,536 for a broken mechanism too* |

Rule B is the one no name-based lint can have. In `ring_sweep` the two sides
really are different expressions; they are just not independent, and the 65,536
origins the loop enumerates are the atoms whose variation the predicate ignores.

Rule C exists because rule B is **evadable by spelling**. Write the truth as a
literal instead of as a variable the other side shares --
`if ((seed - ((seed - 4096) & M32)) & M32) != 4096: lost += 1` -- and rule B's
precondition (one atom set containing the other) is no longer met. That sweep
was written, run against the analyser, and escaped; rule C was added and it does
not. Only a *tally* is judged this way: an equality between two opaque calls is
naturally false under random atoms, and that is a check, not a defect.

**Proved end to end.** A copy of `fb_pal.py` -- a copy; nothing in
`noctis-harness/` was edited -- was given three reintroductions of the class in
one function: `reference = walker(ws); subject = walker(ws); req(reference ==
subject)`, the literal-spelled ring sweep above, and `req(True, "768 components
enumerated")`. The clean file yields **0** findings; the injected copy yields
**3**, one per rule, none of them dispositioned, which is the state that fails
the suite.

### 8.2 What it found on its first run -- 6 findings over 17 files

| file | line | condition | rule | disposition |
|---|---|---|---|---|
| `fb_tick.py` | 406 | `got != want` | B | **OPEN** |
| `fb_tick.py` | 941 | `naive > 1 << 31` | A | **OPEN** |
| `fb_stick.py` | 352, 360 | `True` | A | **OPEN** (one fingerprint, two sites) |
| `fb_wrap.py` | 416 | `m != n or True` | A | **OPEN** |
| `tests/test_wave5.py` | 1213 | `after == base` | A | **REFUTED**, by experiment |

Plus four in `tests/` that were **deleted rather than recorded** -- see 8.4.

### 8.3 Dispositions: there are two, and neither of them is "ignore"

**REFUTED** -- the analyser is wrong about this site, *and here is a callable
that runs every time the audit runs and produces both outcomes*. If the
demonstration stops discriminating, the audit fails. A refutation is an
experiment, not an assertion. The one live REFUTED entry is
`test_wave5.py`'s `after == base`: both sides are `grade(blob)` on the same
bytes, so the analyser is right that they are one atom -- but the claim is that
`grade()` is **pure across the thirty-odd perturbation grades run between
them**, and the demonstration builds a stateful grader and shows the identical
comparison reading `False`.

**OPEN** -- the analyser is right; the check is void. The entry names the file
that owns it, and the audit

* **asserts the finding is still present** -- a fix has to arrive with the
  entry's deletion, so a silent repair fails the run just as a silent
  regression does; and
* runs a **live measurement** where one exists. For the ring sweep:

```
OPEN 888189881a7e (fb_tick.py) is STILL void, measured this run
  [500 ms: 1 distinct outcome(s) over the origin axis; 60000 ms: 1; 470000 ms: 1;
   500000 ms: 1; got == want & M32 in every sampled case (0 exceptions)]
```

**`OPEN_BUDGET = 4`.** The number may fall and may never rise. A new void check
fails the run and prints the fingerprint to paste. There is no third
disposition and no suppression list, and **a finding under `tests/` may not be
OPEN at all** -- that is itself a checked rule.

### 8.4 DELETED AS VOID -- the evidence for the next wave

This is the list the brief asked for: what the class looks like when it is
found in one's own work. All four were in `tests/`, all four were found by the
analyser on its first run, and none was recorded as OPEN, because the file that
owns them is the file the audit ships in.

1. **`tests/test_wave5.py` -- `chk.ok(True, "reference probe builds and runs", note)`**
   Preceded by `if blob is None: chk.ok(False, ...); return`. The `ok(True)` is
   a *print statement occupying a slot in the pass count*: it is emitted only on
   the path where the answer is already known, so it can report nothing.
   Replaced by one call with the real condition in it,
   `if not chk.ok(blob is not None, ...): return chk.done()`.
   **The same shape as `fb_stick.py:352`, in the file that was criticising it.**

2. **`tests/test_wave5.py` -- `chk.ok(True, "display probe builds and runs", dnote)`**
   Identical shape, inside an `else:` branch. Same fix.

3. **`tests/test_wave5.py` -- `chk.ok(True, label, "did not even produce a dump")`**
   in the sabotage loop. A sabotage that fails to *build* is a genuine catch --
   but writing it as `ok(True)` means the branch cannot record anything else,
   and the loop then had three exits with three different verdict expressions.
   Replaced by one computed `caught` and one `chk.ok(caught, label, detail)`.

4. **`tests/linoharness.py` -- `check.ok(True, "all %d %s produced %d records")`**
   Reached only when the counts already agree, and *agreeing on zero records is
   agreement about nothing*: a producer that emits nothing agrees with every
   other producer that emits nothing. Replaced by
   `check.ok(sizes[names[0]] > 0, "... and the record set is not empty")`,
   which is a real claim about a real failure mode. This one was live in
   **every** test that calls `compare_records`, not just Wave 5.

The lesson is items 1 and 4 together. Both were written by the people writing
the rule, in the same tree as the rule, while the rule was on screen. Neither
was noticed by review, by `fb_lint`, or by the two rejections. The detector is
not a formality.

### 8.5 The ledger gate -- the forged row, rejected

The QA pass on Wave 5c registered a `GRADED` entry whose falsifier no body
constructs and whose second side was relabelled `external:` so
`fb_ledger.validate()`'s same-owner rule could not see it. All four existing
gates passed the forgery. Two gates here do not, and the audit **runs the
forgery every time** rather than describing it:

```
a hand-forged GRADED row is REJECTED by this audit's gates
  [{'fb_ledger.validate() before': True,
    'fb_ledger.validate() with the forgery': True,     <- upstream still passes it
    'tier gate caught it': True,
    'falsifier gate caught it': True}]
```

* **falsifier constructibility** -- a `GRADED` row whose declared falsifier
  tokens appear in **no source in the tree** (`fb_ledger.py` itself excluded)
  is a declaration nothing can drive. Measured today: **9 rows**, budget 9.
  `T1.CAPTURE.AGREE inrow:RAWBYTES`, `T1.CAPTURE.PRESENT inrow:EMPTYDIR`,
  `T1.PAL.NOROUND inrow:ROUNDTONEAREST`, `T1.PNG.DOUBLING inrow:NONUNIFORM`,
  `T1.PNG.SCALE inrow:X4`, `T2.CBUILD.CLEAN inrow:GCCWARNING`,
  `T3.TICK.RATEPROBE inrow:RATEOFF`, `T3.TICK.SERVOSTEP` and
  `T3.TICK.SERVOWILD inrow:SRVWILD`. Several are hypothesis names rather than
  sabotage names, which is exactly the ambiguity the budget exists to retire.
* **cid-prefix consistency** -- the `T0/T1/T2/T3` prefix of a check id is a
  claim about the evidence, and it is recomputed against the row's own owners.
  Measured today: **8 rows**, budget 8. Seven claim two implementations with an
  `external` side (`T2.CBUILD.CLEAN`, `T2.CSELFTEST`, `T2.LINO.TAGSPRESENT`,
  `T2.LINO.V2`, `T2.PAL.SELFTEST`, `T2.TICK.ARITH`, `T2.WRAP.CLASSA`); one
  (`T3.TICK.SELFGRADE`) carries a graded prefix and is `NOTGRADED`.

### 8.6 The tier pin -- a document that over-claims fails the test

Three gates, all recomputed from `fb_ledger.LEDGER` on every run:

1. **`fb_compare.TIER_TABLE`.** A row whose evidence level contains a 2 must
   have at least one supporting `GRADED` cid with **two distinct non-`external`
   owners** -- `LINOBUF` §7 defines that level as "two independent
   implementations", and a parsed 1996 source, a capture or an exact rational
   is not an implementation. Measured today: **4 over-claims**, budget 4 --
   `shade's destination buffer` (`T2.CSELFTEST` = imp2|external), `the raster
   loop (digit_at n=0)` (`T3.PADPROBE.EXPECTATION` = imp1|external), `the
   22-zone pad model` (`T3.PADPROBE.VIOLATION` = imp1|external), `the tick
   period` (`T2.TICK.ARITH` = imp1|external). All four are honest evidence
   filed one level too strong.
2. **Pinned prose.** Fourteen registered claims across `test_wave5.py`,
   `HARNESSAUDIT.md` and `LINOBUF.md`, each quoting its sentence **verbatim**
   and naming the cids it rests on. The quote must still be in the file, the
   level must be what the cids support, and a stated producer *count* must equal
   the recomputed one.
3. **Completeness.** Every line in the four scanned files that names a level at
   all must be registered -- as a claim, or explicitly as a mention that asserts
   nothing. Unregistered prose fails the run. This gate fired on its first
   execution, against the paragraph being written to satisfy gate 2.

**One over-claim was found and fixed by these gates:** `tests/test_wave5.py`
said the index page reached the external-artifact level. It does not, on two
counts -- there is no external artifact for the page, and the two producers use
different fixtures, so `T2.LINO.ADAPTED.CROSSFIXTURE` is `NOTGRADED`.
`fb_compare`'s own `TIER_TABLE` had already deleted the same claim
(`ev0`, one producer per fixture) and the two documents had drifted apart. The
sentence now reads "UNGRADED for the page" and is pinned.

### 8.7 Proved breakable, by breaking it

Every gate above takes its inputs as arguments so that
`w5audit.self_falsification()` can feed each a broken input and require the
complaint. Ten of the audit's thirty-two checks are that battery:

```
ok  BREAKS: an undispositioned finding is reported  [injected 4051326d2c93 -> ['4051326d2c93']]
ok  and the real tree has none
ok  BREAKS: a disposition with no finding behind it is reported  [['ffffffffffff']]
ok  BREAKS: a finding under tests/ disposed OPEN is reported  [['29bb3f13140a']]
ok  BREAKS: a pinned tier claim whose text has drifted is reported
ok  BREAKS: a Tier 2 claim resting on a ONE-PRODUCER row is reported
ok  BREAKS: a producer COUNT that the ledger does not support is reported
ok  BREAKS: an unregistered tier claim in a scanned file is reported
ok  the sampler assigns by SORTED atom key, so the audit is reproducible across processes
ok  BREAKS: with `!=` removed from the algebra the analyser goes blind  [intact 1, crippled 0]
```

The last one is the audit pointed at itself: delete `NotEq` from the algebra and
the ring-sweep corpus entry stops being detected, which is what makes the corpus
gate load-bearing rather than decorative. A twelfth check requires **every rule
to be exercised by the corpus** -- `A <- constant_arithmetic, kind6_canary,
literal_true, or_true, same_producer, same_producer_renamed, witness_literal;
B <- ring_sweep, ring_sweep_renamed; C <- dead_sweep, recovered_offset` -- so a
rule that stops firing cannot sit in the file looking like coverage.

The sampler line is not decoration either. Before the atom keys were sorted,
two runs of the same tree reported **6 findings and 7 findings**: Python
randomises string hashing per process, so a borderline condition got different
random values in different runs. A ratchet that reports a different number every
run is not a ratchet, and that defect would have surfaced as an unexplainable
intermittent suite failure.

### 8.8 What `w5audit` cannot do -- stated, not implied

* **It reads Python.** `fb_ref.c` is 2,622 lines of C and is **not analysed**.
  The QA pass demonstrated a live void pair there -- `REF.E1.PAGESDIFFER` and
  `REF.E1.RIGHTPAGE` both `PASS` on a build with `present_expand`'s body
  replaced by `for(i=0;i<64000;i++) FB[i]=0;`, byte-identical output to the
  baseline. Nothing in this audit sees that. It has to be found by the C
  sabotage battery, and it is open.
* **Atoms are opaque.** Two *different* calls that happen to compute the same
  thing read as sound. Rule B catches derivation through visible arithmetic, not
  through a shared implementation two modules away. That is what the ledger's
  owner rule is for, and why both mechanisms are kept.
* **The domain is unmodelled.** Atoms are drawn from a spread, not from the
  values the program can produce, so a bounded quantity can look unbounded.
  `fb_wrap.py`'s `py_never_wraps` is the standing example: its predicate does
  discriminate, at `v = 183`, where `360*v` crosses 65535. The only admissible
  answer to a false positive is a REFUTED disposition with a running experiment.
* **Sampling is random with a fixed seed.** Deterministic per run, not
  exhaustive. A condition false on a measure-zero set of assignments can be
  reported as rule A. Same answer: refute it with an experiment.
