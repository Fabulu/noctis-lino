# FLOATPOLICY — how floating point is done, per subsystem

Wave 3's settled answer, written down 2026-08-05 after the implementers, the
adversarial review and the QA pass. Everything below is a decision plus the
measurement that forced it. Where the wave did not settle something, this file
says so in those words rather than inventing a policy.

The regression test that keeps this file honest is
`tests/test_floatcontract.py` (suite entry 15). It recomputes every number
quoted here on every run. If a claim in this document ever stops being true,
that test fails and names the battery.

---

## 0. The one-paragraph version

Generation arithmetic — anything that becomes a seed — is done on the x87
register stack at **control word 133Fh** (64-bit precision, round to nearest
even, all exceptions masked), with the intermediates **never stored** across
an expression. The control word is **stated at every boundary**, never
inherited. Rendering is not held to that: it goes through the same engine but
its errors are cosmetic and it is graded against a hardware reference rather
than against the 1996 catalogue. The **float-to-int cast boundary is
UNSETTLED** and nothing in the graded path is allowed to depend on it.

---

## 1. The precision ladder, and why 24 bits is fatal

| engine | significand per operation | held across an expression? |
|---|---|---|
| original, DOS x87, `fp87.lib` | 64 bits (PC=64) | **yes** — asm chains keep values in `st(0)` over many ops with no intervening store |
| noctis-iv-lr, SSE2 | 53 bits | no — every op narrows |
| L.in.oleum native `++ -- ** //` | 24 bits | no — narrows after **every** instruction |

Noctis's star identity is not a number, it is a seed:

```
nearstar_identity = x/100000 * y/100000 * z/100000        NOCTIS-0.CPP:4078
```

The game truncates it to an integer and generates a whole solar system from
the result. One ULP is a different planet, not a nearby one. There is no
tolerance to set, which is why every number in this file is an exact-match
count and never a distance.

**The measurement.** Over 4113 catalogue records (see §2 for why 4113):

| how the chain is evaluated | reproduces the 1996 bits |
|---|---|
| 64 bits, unspilled, RC=nearest — **the policy** | **4113 / 4113** |
| 53 bits (any IEEE-double engine) | 2239 / 4113 = 54.4% |
| 24 bits (L.in.oleum's own float instructions) | **4 / 4113 = 0.10%** |
| 64 bits but RC=chop | 2048 / 4113 |
| 64 bits with ONE intermediate stored to a double | 3043–3063 / 4113 |
| 64 bits with a store after every operation | 2239 / 4113 |
| the game's own `isthere()` lookup formula | **0 / 4113** |

Read the 53-bit row carefully: a plain IEEE-double port is not obviously
broken, it is *half right*. That is exactly the failure a tolerance-based test
calls a pass.

---

## 2. The oracle, and the number 4113

`STARMAP.BIN` holds 37,578 records of stars and planets charted by players
since 1996. Each stores the `double` the original computed. It is the only
place in this port where "did we get the floating point right" has an answer
that predates the question, produced by a machine we do not have and a
compiler we are not running.

**Why 4113 and not 4194 — rule 1, no choice.** A galaxy sweep at K=64 matches
4194 catalogue records inside the ±1e-5 acceptance window. 81 of those have
**more than one** candidate coordinate triple. A record with two candidates can
be scored by whichever candidate happens to reproduce it — which measures the
chooser, not the arithmetic. The QA pass found exactly that had happened: six
rows of `work/fp/fpstarin.bin` had been substituted from
`starmap_verify.py`, whose selection rule is literally "keep the candidate
whose 80-bit id matches the catalogue". The honest headline is therefore:

> **4113 / 4113, over records the sweep offered exactly one candidate for.**

**Rule 2, no coincidences.** Noctis's acceptance window, `|P − N| < 1e10`, is
`idscale = 1e-5` scaled by 1e15. That is the game's tolerance for *finding* a
star by name; it is far looser than what *pairing* a record with a triple for
bit-exactness needs. A record genuinely written from a triple stores a rounded
binary64 of the same exact integer product, so its residue `|P − N| / |P|` is
a few double ULPs. Measured over the believed population: **median 2⁻⁵⁴·⁵,
worst 2⁻⁴²·⁶, and then nothing.**

At K=64 nothing exceeds that. At K=96 exactly one record does — **#25015
'L4 LEG 5A', residue 2⁻²⁹·⁴**, thirteen binades outside the population — and
no hypothesis in the whole ladder reproduces it: not 64, 53 or 24 bits,
neither rounding mode, no spill point, not the lookup formula. It is a
different star that landed inside the window. The test therefore pairs on the
residue with a threshold of 2⁻³⁶, which sits in the empty band, and it
**verifies every drop** by trying all 13 hypotheses against it. Both
directions are guarded: a threshold moved down drops a real record and the
justification check catches it by name; a threshold moved up admits the
coincidence and the headline claim fails.

Deep mode (`--K 96`) therefore reads **4528 / 4528**.

The population's own distribution is itself evidence, and it is reported every
run rather than assumed: a catalogue written at 24-bit precision would show
residues around 2⁻²⁴. It shows 2⁻⁵⁴·⁵.

`work/fp/fpgrade.py`'s "4194/4194" is inflated by those six and its claim of
"deliberately NOT graded against any table this project produced" is true of
the expected *values* and false of the *inputs*. The regression test does not
use those files at all: it re-sweeps every run, discards the ambiguous records
unexamined, and reads the expected bits out of the catalogue.

**What the oracle can and cannot resolve.** Measured, not assumed:

* precision class — 64 vs 53 vs 24 bits: **decisive** (4113 vs 2239 vs 4).
* spilled vs unspilled: **decisive** (4113 vs 3043).
* one ULP of the **final binary64**: **decisive** (0 / 4113, and none of those
  values occurs anywhere in the catalogue).
* one binary64 ULP (extended significand bit 11) in an **intermediate**:
  caught, 341 / 4113 survive.
* one **extended** ULP (bit 0, 2⁻⁶³) in an intermediate: **NOT caught** —
  4113 / 4113 survive. The graded quantity is a binary64, so a 2⁻⁶³ nudge is
  absorbed by the final rounding roughly 999 times in 1000.

So the oracle certifies precision *classes*, not last-bit correctness of an
extended chain. The test measures that gap and pins it, so nobody can later
cite "4113/4113" as bit-exactness of the intermediates.

---

## 3. Per-subsystem decisions

### 3.1 Generation arithmetic — SETTLED, PROVEN

**Decision.** Seeds and everything feeding them are evaluated as *instruction
schedules*, not as expressions: the schedule is transcribed from `NOCTIS.EXE`
into `work/fp/fpsched.txt`, and `tools/genfp.py` turns it into one L.in.oleum
ML fragment per chain. The running value stays in `st(0)`; the only `fstp` is
the last one. Control word 133Fh.

**Why a schedule and not an expression.** In a schedule the absence of an
`fstp` is the absence of an `fstp` — there is nothing to re-derive. One
spilled intermediate costs about a quarter of the catalogue, so where Borland
did and did not store is semantics, not an optimisation detail.

**Evidence.** Four independent engines agree bit for bit on all 4113 records:
the L.in.oleum ML fragments, a gcc-built hardware x87 (built and run inside
the test), an exact-integer x87 model in Python (`tests/fpspec.py`), and the
1996 binary itself. `--backend native` is **refused** by the generator for any
chain marked `exact`, because compiling one through 24-bit instructions
produces a plausible wrong answer, which is worse than an error.

**Do not** call the scalar `fpx87` routines in sequence to evaluate a
generation expression. Each of them stores. That is battery 7 above: 2239.

### 3.2 The control word — SETTLED, and it is not decoration

**Decision.** Every boundary calls `FEnter` (save ambient, install `[FCW]`)
and `FLeave` (put back exactly what was found). `[FCW]` defaults to
`FCWEXT = 133Fh`. `FLoadCW` is for changing it again *inside* an existing
bracket; calling `FEnter` twice would make `FLeave` restore the wrong word.

**Why it is mandatory.** Measured on this machine, reported by the probe's own
header rather than taken from documentation:

* ambient control word at programme entry on win32: **0E7Fh** — the C
  runtime's 027Fh with **0C00h ORed in**, i.e. 53-bit precision *and rounding
  toward zero*.
* `main/sys/win32.bin` contains exactly 8 copies of
  `fnstcw / and ax,0F3FFh / or ax,0C00h / fldcw`.
* `main/sys/linux.bin` contains **zero** `fldcw` and zero `fnstcw`.

So the same L.in.oleum source computes differently on the two runtimes unless
the word is stated. Under the ambient win32 word the identity chain scores
**7 / 4113**. Documenting this would not have removed it; `FEnter` does.

**Isocall persistence.** The word survives a real file-write isocall performed
inside the bracket: read back 033Fh (masked) immediately before and
immediately after, and the chain re-run afterwards is bit-identical on all
4113 records. **Scope limit, stated plainly:** only file-I/O isocalls have
been tested. Graphics, sound, timer and memory isocalls are untested, and
given the 8 chop-forcing sites in `win32.bin` the question is not academic.

**The decoy that misleads audits.** `PITAGORA.H` contains a
`_control87(RC_CHOP, MCW_RC)` call that **never executes** — Noctis includes
`tdpolygs.h` and never `pitagora.h`. The same trap is preserved in
`niv-lr/src/Old/`. Anyone checking control-word handling finds it first and
concludes the original ran in chop mode. It did not: the shipped `NOCTIS.EXE`
carries 133Fh, read out of the MZ image and the Borland C0 startup.

### 3.3 Float to int — **UNSETTLED**

The original has **two** float-to-int behaviours and they are not
interchangeable:

* **cast sites.** A C cast truncates. Borland implements that in `__ftol`,
  which flips the rounding control to chop, does the `fistp`, and flips it
  back. These are the seed sites. One ULP here is a different planet.
* **hand-written sites.** 37 of them (36 `fistp`, 1 `fist`) in the inline
  assembly of the projector and the texture mapper. The rounding control is
  left at 00, so they round to nearest even. Under `FEnter`'s 133Fh,
  `FToIntNear` reproduces all 37 for free. A quarter pixel is invisible.

`fpconv.txt` implements both, and the asymmetry is deliberate: emit
`FToIntChop` unless the site registry names the site as one of the 37, because
a wrong chop site is critical and a wrong near site is cosmetic.

**What is not settled.** The engine has **no way to truncate an unstored
extended value**. `FToIntChop` begins `fld qword [FA0]`, so the 80-bit
intermediate is narrowed to binary64 *before* the truncation; and `genfp`'s
`out` directive accepts only `f64`, so a generated chain must end in an
`fstp` before any conversion. On hardware the two differ:
`(long)(1.0/41.0*41.0)` is **0** with the chain kept in `st(0)` and **1** with
the intermediate spilled to a binary64, at the same control word. The
delivered `fpconv` can only produce the second answer.

Separately, `genfp` will happily emit a bare `fistp` with no `fldcw` bracket,
which under 133Fh rounds to **nearest** where a C cast **truncates**. Modelled
at the three landmark sites in `NOCTIS-1.CPP`, that divergence changes the
seed for 1488/2981, 663/1376 and 231/475 of the in-range stars. The rule
"NEVER emit a bare `=,`" is currently a comment in `fpconv.txt` with nothing
enforcing it.

**Interim policy, and what the test enforces.** Until an `FToIntChopExt`
exists (bracket the control word around a `fistp` on the *live* `st(0)`) and
`genfp` refuses a bare `fistp`:

> No generation chain may convert to an integer. The cast boundary is not to
> be relied on by anything the oracle grades.

`test_floatcontract.py` asserts exactly that and nothing stronger: `genfp`
refuses a non-`f64` output, and the generated `fpchains.txt` contains no
`fistp` encoding at all. It deliberately does **not** assert a cast policy the
wave did not prove.

Mitigating fact, so this is not overstated: the narrowing hazard's probability
is about 1e-7 per site at these magnitudes, and it does not bite at any of the
three landmark sites on either input set (0 differences measured). It is real
on hardware; it is simply not exercised yet.

### 3.4 Rendering, projection, `F32Narrow` — PLAUSIBLE, cosmetic exposure

The 16 scalar and conversion schedules match a gcc-built hardware x87
reference on 4096/4096 vectors across all six graded columns
(`work/fp/fprun.ps1`). Nothing external grades them — there is no 1996
artifact for a pixel — and both references model `FToIntNear` as *forced*
nearest rather than *ambient-inherited*, so a non-nearest ambient word would
go undetected there. The stated cost of being wrong is a quarter of a pixel.

`F32Narrow` is behaviour to reproduce, not a workaround: `NOCTIS-1.CPP`
saves `dzat_x/y/z` into `float` locals and restores them, and at coordinates
around 3.8e6 a binary32 ULP is 0.25, so landing quantises the ship's position
observably in the original. That is why ship state is carried as a double and
narrowed at those points rather than kept in lino's native 24-bit floats.

### 3.5 Backends — interchangeable through `fpabi`, with one known hole

`fpabi.txt` declares the register file and nothing else; `fpx87`, `fpsoft` and
`fpnative` are compiled against it alone, so a call site never knows which is
linked. Measured cross-checks: X87 == SOFT at 133Fh on 4194/4194 (hardware vs
an integer soft-float that never touches the FPU); SOFT PC=64 == SOFT PC=24;
NATIVE at RC=nearest == x87 held at PC=24 on 4194/4194 — so "24 bits per
operation" is a *measurement*; and NATIVE PC=64 == NATIVE PC=24, which closes
off "just raise the precision control" as a shortcut.

**Known hole:** in `fpnative`, `FAdd/FSub/FMul/FQuo/FSqrt/FNeg/FAbs/FSin/
FCos/FAtan2` write `FA0` only and leave `FA1` stale — only `FLoad` and
`FWiden` update it. A call site written against `fpx87` gets a garbage high
half when relinked. Nothing currently miscomputes because `fpstarnat` calls
`FWiden` before every store, but the ABI does not hold as written.

### 3.6 Register-file layout — pinned, because it fails silently

`fstp qword` writes eight bytes from the first unit of a pair, so `FA0/FA1`
(and FB/FC/FD) must stay adjacent and low-half-first. Every probe checks this
at run time with `fld1` before grading anything: a binary64 1.0 must read
`00000000h` then `3FF00000h`. If the compiler ever reorders declarations, that
check fails loudly instead of every score below becoming quietly meaningless.

---

## 4. The interface, in one place

| symbol | file | contract |
|---|---|---|
| `FEnter` / `FLeave` | `fpctl` | save ambient CW, install `[FCW]`; restore. Mandatory at every boundary. |
| `FLoadCW` | `fpctl` | install `[FCW]` **without** saving — for a second change inside an existing bracket. |
| `FCWRead` / `FSWRead` / `FStackOK` | `fpctl` | read back, masked with 0F3Fh. `fnstcw` returns bit 6 set whatever was loaded, so every comparison must mask. |
| `FCWEXT`=133Fh, `FCWDBL`=123Fh, `FCWSGL`=103Fh, `FCWEXTCHOP`=1F3Fh | `fpabi` | the four words. Only the first is the original's. |
| `FA0/FA1 … FD0/FD1`, `FJ0..FJ3`, `FI`, `FS0` | `fpabi` | the register file. **Order is load-bearing.** |
| generated chains (`NsIdentity`, `Prod4`, …) | `fpchains` (from `fpsched`) | one fragment each, result in `FA`, no intermediate reaches memory, control word NOT set — call `FEnter` first. |
| `FToIntChop` / `FToIntNear` / `FToInt16*` | `fpconv` | cast sites vs the 37 hand-written sites. **See §3.3 — this boundary is unsettled.** |
| `F32Narrow`, `FStoreF32`, `FLoadF32` | `fpconv` | the deliberate binary32 quantisations. |

---

## 5. What the regression test actually checks

`tests/test_floatcontract.py`, entry 15 of `tests/run_all.py`. ~32 s. Needs
the reference clone's `STARMAP.BIN`; the gcc leg is skipped with a note if
gcc is absent.

Every run, from scratch:

1. regenerates `fpchains.txt` from `fpsched.txt` and requires it byte-identical
   to the checked-in library;
2. re-sweeps the galaxy, keeps only single-candidate records whose pairing
   residue is believable, verifies every dropped record against all 13
   hypotheses, and reads the expected bits out of `STARMAP.BIN`. **It never
   opens `fpstarin.bin`, `fpstarexp.txt` or `fpstarout.bin`;**
3. builds one L.in.oleum probe carrying **14 batteries** and compares every
   value against `fpspec.py` — an exact-integer x87 sharing no arithmetic with
   the engine — and three of them additionally against a gcc-built hardware
   x87 compiled during the run;
4. requires the exact chain to score N/N and every wrong variant to score less:
   ambient word, PC=53, PC=24, RC=chop, one spill, all spills, the lookup
   formula, a bit-11 flip, a final-ULP flip;
5. records — and does not assert as policy — that a one-**extended**-ULP flip
   is *not* caught, and that a bit-11 flip *is*, which locates the oracle's
   resolution;
6. builds the same probe twice more against **deliberately broken engine
   sources** (every `fldcw [FCW]` removed from `fpctl`; one `fstp/fld qword`
   pair inserted into `NsIdentity`) and requires each to fail the oracle **and
   to produce exactly what the referee predicted it would produce instead**.

Proven by breaking it: nine mutations were applied one at a time, each
restored afterwards with its SHA-256 confirmed back, and each failed the test
with attributable messages —

| mutation | what failed |
|---|---|
| a spill added to the graded schedule (`fpsched.txt`) | 12 checks, starting "exactly ONE fstp: got 2" |
| `FEnter` stops installing the word (`fpctl.txt`) | "FEnter installed 133Fh: got 0E3F" |
| `FCWEXT` becomes 123Fh (`fpabi.txt`) | 28 checks, including every catalogue score |
| `fpchains.txt` drifts from `fpsched.txt` | the byte-identity check |
| the referee's round-to-nearest gets a denominator bug | "battery 4 == the referee: 128/1130 differ" |
| the oracle stops requiring a unique candidate | the PC=24 control inflates 0.35% → 3.25% |
| the pairing threshold moves DOWN into the population | it drops a real record, 'ILYASTRAFEL', and the justification check names the five hypotheses that reproduce it |
| the pairing threshold moves UP out of its band (at K=96) | the coincidence is admitted and the claim drops to 4528/4529 |
| the extended-ULP battery flips a visible bit instead | the three "measured" checks |

That fifth row is not hypothetical: the denominator bug was really in
`fpspec.py`, it only appeared at PC=24 on about a tenth of the catalogue, and
the gcc hardware witness is what caught it. Two implementations that agree can
be wrong in the same way; a Python model of rounding is exactly the kind of
thing that is wrong in a way only hardware notices. The 'L4 LEG 5A'
coincidence was likewise found by running the deep mode, not by reasoning
about it.

---

## 6. What remains open

1. **The cast boundary (§3.3).** Needs an `FToIntChopExt` that brackets the
   control word around a `fistp` on the live `st(0)`, and a `genfp` rule that
   refuses a bare `fistp`. Until then, no generation chain may convert to int.
2. **Isocalls other than file I/O.** Control-word persistence is measured only
   across a file write. Graphics, sound, timer and memory isocalls are
   untested and `win32.bin` has 8 chop-forcing sites.
3. **`fpnative`'s stale `FA1` (§3.5).** The ABI does not hold as written; it
   works only because the current call sites widen first.
4. **`work/fp/fpgrade.py` and `fpstarin.bin`.** The score is inflated by six
   selected rows and the provenance sentence is wrong about the inputs. Either
   regenerate the input set from a checked-in script using the
   single-candidate rule, or delete the files and let the regression test be
   the grader. `fpall.ps1` also ignores the exit status of `fpgrade.py`,
   `fpbackends.py`, `fprun.ps1` and `fpbreakrun.ps1`.
5. **Rendering has no external grader (§3.4).** Accepted: the exposure is a
   quarter of a pixel. If that ever stops being true — a projection feeding a
   seed, say — it needs an oracle of its own.
