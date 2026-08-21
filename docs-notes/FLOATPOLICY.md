# FLOATPOLICY -- how floating point is done, per subsystem

Wave 3's settled answer, written down 2026-08-05 after the implementers, the
adversarial review and the QA pass. Everything below is a decision plus the
measurement that forced it. Where the wave did not settle something, this file
says so in those words rather than inventing a policy.

The regression test that keeps this file honest is
`tests/test_floatcontract.py` (suite entry 15). It recomputes every number
quoted here on every run. If a claim in this document ever stops being true,
that test fails and names the battery.

The portable 2026-08-20 FP update, its mathematical oracle, consumer gates,
workspace boundary, and transitive native-block rule are recorded in
`docs-notes/TRANSCENDENTALS.md`. That document supersedes this older wave's
references to native x87 scalar routines and raw generated fragments. The
original-program measurements and expression schedules below remain evidence,
not permission to ship those opcodes.

**Current shipping architecture.** Production arithmetic is ordinary Lino
integer code that models the required 64-bit x87 significand and spill schedule.
The 75-file, 88-import game/NIVGEN closure contains zero raw target blocks.
`work/fp/fpctl.txt` is a portable fixed-state contract; platform runtimes own
`FCWEXT = 133Fh`. The historical raw x87 control witness lives only in
`work/fp/fpctlx87.txt`, which the test harness privately maps to `fpctl.txt`.
The closure gate also pins all 36 remaining ordinary Lino floating operations
(25 in `main/lib/gen/rect.txt`, eight in `work/supaint.txt`, and three in
`work/supal.txt`) and permits no production `??` floating comparison.

`XQuoCore` is an internal arithmetic kernel for two normalized finite
mantissas, not a scalar IEEE division entry point. Scalar wrappers already
handle zero classes outside it, and every direct expression schedule must do
the same before calling it. Focused ordinary-Lino gates currently expose six
violations of that rule: two geometry seed/eccentricity schedules, two surface
contrast schedules, and two tree-parameter schedules fail when a valid random
numerator is zero; their nonzero or parallel fixed-point controls remain exact.
Those call sites must be repaired without silently broadening the core contract.

---

## 0. The one-paragraph version

Generation arithmetic -- anything that becomes a seed -- follows the original
x87 schedule at **control word 133Fh** (64-bit significand precision, round to
nearest even, all exceptions masked), with no modeled binary64 spill unless the
original stored one. Production implements that model in ordinary Lino integer
code; the historical x87 fragments are private characterization fixtures.
Platform runtimes state the control word at every application/C boundary rather
than inheriting host state. Rendering has lower fidelity exposure but still runs
through the reviewed engine and consumer gates. At the **float-to-int cast
boundary** the original **chops the live 80-bit `st(0)`** -- settled by Wave 6
out of the shipped `NOCTIS.EXE` (§3.3). Shipping code reproduces each needed
expression schedule without embedding target-machine bytes in game source.

---

## 1. The precision ladder, and why 24 bits is fatal

| engine | significand per operation | held across an expression? |
|---|---|---|
| original, DOS x87, `fp87.lib` | 64 bits (PC=64) | **yes** -- asm chains keep values in `st(0)` over many ops with no intervening store |
| noctis-iv-lr, SSE2 | 53 bits | no -- every op narrows |
| L.in.oleum native `++ -- ** //` | 24 bits | no -- narrows after **every** instruction |

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
| 64 bits, unspilled, RC=nearest -- **the policy** | **4113 / 4113** |
| 53 bits (any IEEE-double engine) | 2239 / 4113 = 54.4% |
| 24 bits (L.in.oleum's own float instructions) | **4 / 4113 = 0.10%** |
| 64 bits but RC=chop | 2048 / 4113 |
| 64 bits with ONE intermediate stored to a double | 3043-3063 / 4113 |
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

**Why 4113 and not 4194 -- rule 1, no choice.** A galaxy sweep at K=64 matches
4194 catalogue records inside the ±1e-5 acceptance window. 81 of those have
**more than one** candidate coordinate triple. A record with two candidates can
be scored by whichever candidate happens to reproduce it -- which measures the
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

At K=64 nothing exceeds that. At K=96 exactly one record does -- **#25015
'L4 LEG 5A', residue 2⁻²⁹·⁴**, thirteen binades outside the population -- and
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

* precision class -- 64 vs 53 vs 24 bits: **decisive** (4113 vs 2239 vs 4).
* spilled vs unspilled: **decisive** (4113 vs 3043).
* one ULP of the **final binary64**: **decisive** (0 / 4113, and none of those
  values occurs anywhere in the catalogue).
* one binary64 ULP (extended significand bit 11) in an **intermediate**:
  caught, 341 / 4113 survive.
* one **extended** ULP (bit 0, 2⁻⁶³) in an intermediate: **NOT caught** --
  4113 / 4113 survive. The graded quantity is a binary64, so a 2⁻⁶³ nudge is
  absorbed by the final rounding roughly 999 times in 1000.

So the oracle certifies precision *classes*, not last-bit correctness of an
extended chain. The test measures that gap and pins it, so nobody can later
cite "4113/4113" as bit-exactness of the intermediates.

---

## 3. Per-subsystem decisions

### 3.1 Generation arithmetic -- SETTLED, PROVEN

**Decision.** Seeds and everything feeding them are evaluated as instruction
schedules, not algebraically reassociated expressions. The schedules were
transcribed from `NOCTIS.EXE` into `work/fp/fpsched.txt`; production's ordinary-
Lino integer engine models the same 64-bit significand and explicit spill
points. `tools/genfp.py` and its raw x87 output remain historical test witnesses,
not production libraries.

**Why a schedule and not an expression.** Whether the original issued an
`fstp` is observable semantics. One spilled intermediate costs about a quarter
of the catalogue, so the portable model must reproduce each store rather than
letting host compilation choose one.

**Evidence.** Four independent engines agreed bit for bit on all 4113 records:
the historical Lino x87 witness, a gcc-built hardware x87, an exact-integer x87
model in Python (`tests/fpspec.py`), and the 1996 binary itself. Current
production validation adds portable schedule comparisons and byte-exact
consumer outputs. No shipping root imports the raw `fpchains.txt` witness.

**Do not** decompose a generation expression into stored scalar calls. Each
public scalar call returns a binary64. That is battery 7 above: 2239.

### 3.2 The control word -- SETTLED, and it is not decoration

**Decision.** The production process owns one fixed environment:
`FCWEXT = 133Fh`. `FEnter`, `FLeave`, and `FLoadCW` preserve the historical call
surface but do not pretend portable source can save or load host x87 state.
`FEnter` rejects any requested word other than `FCWEXT`; `FLeave` reasserts that
fixed contract.

The environment is installed below the language boundary. The eight variants in
licence-protected `main/sys/win32.bin` retain their exact upstream bytes. After
the compiler copies one selected variant into a generated PE,
`tools/patch_runtime_fcw.py` replaces its one reviewed control sequence with the
size-preserving `133Fh` form and rejects missing, duplicate, or already-patched
sequences. Linux and macOS runtimes load `133Fh` before application entry and
reload it immediately after every C/runtime isocall.
`tests/test_fp_runtime_boundary.py` pins all eight protected variants, the
post-link Windows instruction shape, both load sites and the one constant in each
assembly source, and the absence of machine escapes from production `fpctl.txt`.

**Why it is mandatory.** The historical probe measured the old Windows runtime
entering at `0E7Fh`: 53-bit precision and round-toward-zero. Under that ambient
word the identity chain scored **7 / 4113**. The private x87 witness now records
the patched runtime word (`033Fh`), deliberately installs hostile `0E3Fh`, and
proves `FEnter` installs `033Fh`. Deleting every private `fldcw [FCW]` leaves the
negative control at 7/1130 in the focused K=24 run, exactly as the independent
referee predicts. That separates platform ownership from the historical witness
instead of inferring one from the other.

**The decoy that misleads audits.** `PITAGORA.H` contains a
`_control87(RC_CHOP, MCW_RC)` call that **never executes** -- Noctis includes
`tdpolygs.h` and never `pitagora.h`. The same trap is preserved in
`niv-lr/src/Old/`. Anyone checking control-word handling finds it first and
concludes the original ran in chop mode. It did not: the shipped `NOCTIS.EXE`
carries 133Fh, read out of the MZ image and the Borland C0 startup.

### 3.3 Float to int -- **the original is settled; production models it portably**

> **Current status, 2026-08-20.** The original behavior remains chop on the
> live 80-bit `st(0)`. The shipping generator paths reproduce the required
> expression schedules in ordinary Lino integer code. The raw `fistp` fragments
> discussed below are historical characterization and mutation fixtures outside
> the production closure; they document how the answer was established, not the
> current implementation architecture.

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

**What Wave 6 settled, and how.** Not by argument from Borland's calling
convention -- by decoding the shipped `NOCTIS.EXE`. The MZ header gives the
image base (608 paragraphs → file 9728), so `__ftol` at image `1265h` is file
14437, and its whole body decodes to 21 instructions:

```
push bp / mov bp,sp / sub sp,0Ah
fnstcw word [bp-2]          ; save the caller's control word
mov   al,[bp-1]             ; save its high byte
or    byte [bp-1],0Ch       ; RC <- 11 = CHOP.  OR, not AND/OR.
fldcw word [bp-2]
fistp qword [bp-0Ah]        ; truncates whatever is in st(0)
mov   [bp-1],al / fldcw word [bp-2]      ; put the caller's word back
mov ax,[bp-0Ah] / mov dx,[bp-8] / retf   ; low 32 bits, in DX:AX
```

Three readings follow from that and are asserted, not narrated:

* **It takes no parameter.** Every frame access in the body is a *negative*
  displacement from `bp`; nothing is read from the parameter area. Its input
  can only be `st(0)`.
* **The operand is still live at 80 bits.** Of the **274** `lcall 0000:1265`
  sites in the image, **130** are fed directly by an x87 instruction and
  **none** of those is a store. At the eleven `prepare_nearstar` geometry
  sites specifically there is no `fstp` between the last arithmetic and the
  call.
* **Only `RC` is touched.** `OR 0Ch` sets both rounding-control bits and
  leaves the precision-control bits alone, so the 64-bit chain the caller
  built is chopped *at 64-bit precision*.

So a cast site is `chop(live extended)`. In the Wave 6 reference engines that
is spelled `--cast chop --castsrc ext`, and both `geo_ref.c` and `geo_spec.py`
**default** to it; `test_geometry.py` section 2 requires that default and
fails if either engine's default moves. The cost of getting it wrong is
measured on the real generator rather than guessed: chop vs round-to-nearest
moves **14.5%** of planetary geometry values, and live-extended vs
binary64-first moves **0.28%**.

Nothing here changes the **37 hand-written `fistp` sites**. They inherit
133Fh and round to nearest even; that was never the open half.

**Historical harness limitation.** The original Lino code generator could not
hand a live `st(0)` value between routines: `FToIntChop` first loaded a stored
binary64, and `genfp`'s `out` directive required a store. The private
`work/geoconv.txt` witness therefore used one raw fragment per expression shape
to prove the live-versus-spilled distinction. On hardware,
`(long)(1.0/41.0*41.0)` is **0** with the chain kept in `st(0)` and **1** after a
binary64 spill at the same control word.

That limitation no longer licenses target bytes in shipping source. Production
models the extended value and truncation with ordinary integer operations; the
closure gate rejects `geoconv.txt` or any other raw witness if a shipping root
imports it. `genfp` still rejects both `fistp` and `fist`, including the former
integer-input-slot bypass, so generated raw schedules cannot accidentally claim
to solve the boundary.

The rule is now:

> No production game source may use a raw conversion fragment. Preserve the
> original expression schedule and live-extended chop in ordinary Lino, and
> validate it against the historical binary/model witnesses.

`tests/test_geometry.py` keeps the settled reading honest. The historical
`NsIdentChop16` and `geoconv` fragments remain useful negative/reference
fixtures but are not reachable from `work/vhgame.txt` or `work/vhnivgen.txt`.

### 3.4 Rendering, projection, `F32Narrow` -- PLAUSIBLE, cosmetic exposure

The 16 scalar and conversion schedules match a gcc-built hardware x87
reference on 4096/4096 vectors across all six graded columns
(`work/fp/fprun.ps1`). Nothing external grades them -- there is no 1996
artifact for a pixel -- and both references model `FToIntNear` as *forced*
nearest rather than *ambient-inherited*, so a non-nearest ambient word would
go undetected there. The stated cost of being wrong is a quarter of a pixel.

`F32Narrow` is behaviour to reproduce, not a workaround: `NOCTIS-1.CPP`
saves `dzat_x/y/z` into `float` locals and restores them, and at coordinates
around 3.8e6 a binary32 ULP is 0.25, so landing quantises the ship's position
observably in the original. That is why ship state is carried as a double and
narrowed at those points rather than kept in lino's native 24-bit floats.

### 3.5 Historical backends and current public ABI

The backend comparisons below are retained as characterization. Production's
`fpx87`-named public scalar surface now delegates to `fpsoft` ordinary-Lino
integer routines; the name is compatibility, not an opcode exception. It writes
both `FA0` and `FA1`, preserves `A/B/C/D/E`, and contains no raw target block.

Historically, `fpabi.txt` allowed `fpx87`, `fpsoft`, and `fpnative` test backends
to be compiled against the same slots. Measured cross-checks were: X87 == SOFT
at 133Fh on 4194/4194; SOFT PC=64 == SOFT PC=24; NATIVE at RC=nearest == x87
held at PC=24 on 4194/4194; and NATIVE PC=64 == NATIVE PC=24. Those measurements
closed off "just raise the precision control" as a shortcut.

The historical `fpnative` fixture leaves `FA1` stale after scalar arithmetic and
transcendentals. It remains a deliberately limited characterization backend and
must not be substituted for production `fpx87`.

### 3.6 Register-file layout -- pinned, because it fails silently

`fstp qword` writes eight bytes from the first unit of a pair, so `FA0/FA1`
(and FB/FC/FD) must stay adjacent and low-half-first. Every probe checks this
at run time with `fld1` before grading anything: a binary64 1.0 must read
`00000000h` then `3FF00000h`. If the compiler ever reorders declarations, that
check fails loudly instead of every score below becoming quietly meaningless.

---

## 4. The interface, in one place

| symbol | file | contract |
|---|---|---|
| `FEnter` / `FLeave` | `fpctl` | assert/restate the runtime-owned fixed `FCWEXT` contract; no host instruction in production source. |
| `FLoadCW` | `fpctl` | accept only `FCWEXT`; other requested words fail. |
| `FCWRead` / `FSWRead` / `FStackOK` | `fpctl` | portable production contract values. Raw historical observations come only from test-only `fpctlx87.txt`. |
| `FCWEXT`=133Fh, `FCWDBL`=123Fh, `FCWSGL`=103Fh, `FCWEXTCHOP`=1F3Fh | `fpabi` | historical words; production runtime state is fixed to the first. |
| `FA0/FA1 … FD0/FD1`, `FJ0..FJ3`, `FI`, `FS0` | `fpabi` | the register file. **Order is load-bearing.** |
| production scalar and generation schedules | `fpx87` / `fpsoft` and consumer libraries | ordinary-Lino integer model of binary64 import, 64-bit x87 significand operations, and explicit spills. |
| `XQuoCore` | private `fpsoft` kernel | divide normalized finite mantissas only; scalar wrappers and direct schedules handle zero/exceptional classes before entry. |
| historical generated chains (`NsIdentity`, `Prod4`, …) | test-only `fpchains` (from `fpsched`) | raw x87 characterization witness, outside the shipping closure. |
| `FToIntChop` / `FToIntNear` / `FToInt16*` | `fpconv` | stored binary64 conversion helpers; live-extended production expressions must be modeled as complete ordinary-Lino schedules. |
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
   value against `fpspec.py` -- an exact-integer x87 sharing no arithmetic with
   the engine -- and three of them additionally against a gcc-built hardware
   x87 compiled during the run;
4. requires the exact chain to score N/N and every wrong variant to score less:
   ambient word, PC=53, PC=24, RC=chop, one spill, all spills, the lookup
   formula, a bit-11 flip, a final-ULP flip;
5. records -- and does not assert as policy -- that a one-**extended**-ULP flip
   is *not* caught, and that a bit-11 flip *is*, which locates the oracle's
   resolution;
6. builds the same historical probe twice more against **deliberately broken
   private witness sources** (every `fldcw [FCW]` removed from test-only
   `fpctlx87.txt`; one `fstp/fld qword` pair inserted into `NsIdentity`) and
   requires each to fail the oracle **and to produce exactly what the referee
   predicted it would produce instead**.

Proven by breaking it: nine mutations were applied one at a time, each
restored afterwards with its SHA-256 confirmed back, and each failed the test
with attributable messages --

| mutation | what failed |
|---|---|
| a spill added to the graded schedule (`fpsched.txt`) | 12 checks, starting "exactly ONE fstp: got 2" |
| private x87 `FEnter` stops loading the word (`fpctlx87.txt`) | hostile ambient word remains 0E3Fh and the exact-chain control collapses as predicted |
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

1. **Run the hosted macOS boundary.** Source/static checks are complete. A
   test-only x86_64 Mach-O probe now perturbs the host to `123Fh`, loads
   `133Fh`, reads both states with `fnstcw`, and restores the incoming word; its
   C source passes locally and both Intel-macOS and Apple-Silicon/Rosetta
   workflows execute it. Those hosted jobs still must run on the current source,
   together with the existing exact Rosetta NIVGEN and game-consumer smokes.
2. **Complete integrated regression.** The default K=64 historical contract
   passes all 80 checks over 4,113 unambiguous catalogue rows. All 16 4,096-case
   schedules and 45 consumer checks also pass. One coherent project-wide suite
   still has to pass with the final runtime baseline.
3. **Historical fixture hygiene.** `work/fp/fpgrade.py` and `fpstarin.bin` still
   carry the older six-row input-selection problem. They are not production
   inputs, but should be regenerated from the single-candidate rule or retired.
4. **Rendering exposure.** The scalar model is mathematically and consumer
   tested, while the remaining 36 ordinary Lino float operations are inventory-
   pinned rather than externally graded at every pixel. Any path that starts
   feeding generation state needs a stronger oracle before release.

The earlier attempt to modify protected `main/sys/win32.bin` was reverted. Its
upstream SHA-256 remains
`6620f38b49762a434267f6ea46a0c38673f55e5ca87cff7f82dfbda9e0fa175b`;
generated Windows PEs receive the reviewed size-preserving `133Fh` patch instead.
