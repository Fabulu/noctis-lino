# OPENITEMS -- what is settled, by what evidence, and what is not

Written 2026-08-05 at the end of Wave 6. This file exists because three
things were carried forward as "open" and it was becoming hard to tell, from
the other documents alone, which of them had actually been answered and which
had merely been measured. Each entry below says: the status, the evidence
that produced it, the test that keeps it honest, and -- for anything still
open -- the route to closing it.

The house rule this file is written under: an honestly open item is worth
more than a manufactured answer. Three of the entries are settled. Two are
not, and are not dressed up.

The regression test for everything here is `tests/test_geometry.py`
(standalone: `python tests/test_geometry.py`, about 70 seconds, needs gcc and
the extended L.in.oleum toolchain). It recomputes every number quoted below
on every run.

---

## 1. The float-to-int cast boundary -- **SETTLED** (the original's behaviour)

**Status.** A C cast site in Noctis IV chops the **live 80-bit `st(0)`**. In
the Wave 6 reference engines that is `--cast chop --castsrc ext`.

**Evidence -- the shipped 1996 machine code, not a document.**
`C:\programmieren\noctis\niv-plus\modules\NOCTIS.EXE`. The MZ header gives
the load image base (608 paragraphs → file offset 9728), so Borland's
`__ftol` at image `1265h` is file offset 14437. Its body decodes completely --
21 instructions, ending in `retf`, no byte unaccounted for -- and three
properties follow:

| property | how it is read | what it means |
|---|---|---|
| every frame access is a **negative** `bp` displacement | the decode; there is no read from the parameter area | `__ftol` takes no parameter, so its operand is `st(0)` |
| `or byte [bp-1],0Ch` | one instruction, an OR and not an AND/OR pair | `RC` ← 11 = **chop**; the `PC` bits (mask 03h) are untouched, so the chop happens at 64-bit precision |
| `fistp qword [bp-0Ah]`, low 32 bits returned in DX:AX | the decode | a 32-bit `fistp` would store the integer indefinite instead of letting the low half through -- a different operation |
| of **274** `lcall 0000:1265` sites in the image, **130** are fed directly by an x87 instruction and **0** of those is a store | forward decode of the instruction that ends where each call begins | the value chopped is live at 80 bits, everywhere, not only at the geometry sites |

The eleven `prepare_nearstar` float-argument sites are located from the
binary rather than from a stored offset list: the `:4089` shape (`fld dword`
300.0f / `fmul dword` `nearstar_ray` / `lcall __ftol`) is unique in the
image, and the registry is that anchor plus the next ten `__ftol` calls --
file offsets 61555 … 62793, a span of 1238 bytes. None of the eleven has an
`fstp` between the last arithmetic and the call.

**Why it matters.** Getting it wrong is not cosmetic: chop vs
round-to-nearest moves **3,298 of 22,768** planetary geometry values
(14.485%) over a 200-system corpus, and it reaches exactly four of the eight
geometry fields (`orb_seed`, `tilt`, `orb_tilt`, `orb_ecc`); the live vs
binary64-first axis moves 63 of 22,768 (0.277%).

**What keeps it honest.** `tests/test_geometry.py` sections 1 and 2:

* section 1 re-derives the decode from the binary on every run, and **breaks
  itself five ways on an in-memory copy** -- `or 0Ch` → `or 0`, OR → AND,
  `fistp qword` → `fistp dword`, `mov al,[bp-1]` → `mov al,[bp+6]`, and
  `fld qword` → `fstp qword` at a call site -- requiring each check to fail;
* section 2 requires **both** reference engines to *default* to chop/ext,
  with a flag-flip control proving the reading is a measurement.

That second check is the one that was missing. The wave's own `geo_grade.py`
cross-checks the two engines under `(near, ext)` and `(chop, f64)` and prints
"the cast boundary stays OPEN" -- but agreement between the engines cannot
pin the boundary, because **they also agree bit for bit under `(near, f64)`,
the hypothesis furthest from the binary's answer**. Section 3 of the test
measures that on purpose so nobody mistakes engine agreement for a decision.

**What is NOT settled by this**, and it is a different question: a general
L.in.oleum routine still cannot accept an unstored live `st(0)` value across a
routine boundary. The generator-side hazard is closed: `genfp` now rejects
both bare `fistp` and `fist`, including an integer-input-slot bypass, and the
known live chops exist as hand-checked expression fragments in
`work/geoconv.txt`. See FLOATPOLICY.md §3.3 and §6.1. Any future conversion
site still needs a named expression shape rather than a generic stored-value
helper.

---

## 2. Planetary geometry -- **PARTIALLY SETTLED, and honestly so**

**Status.** The values are computed by two independent references that agree
bit for bit. They are **not graded against the 1996 machine**, and on the
present evidence they cannot be.

**What exists.** `noctis-harness/geo_ref.c` (a line-ordered transcription of
NOCTIS-0.CPP:4059-4376, 80-bit x87 chains at control word 133Fh on real
hardware) and `noctis-harness/geo_spec.py` (built from the draw table
outwards, exact rational arithmetic, no hardware float anywhere) agree on
**22,768 of 22,768** values over a 200-system corpus -- 8 fields × 2,846
bodies, from 200 systems carrying 951 planets. That is evidence about
**transcription**. It is not evidence about the 1996 machine.

**Why there is no oracle, re-derived every run.** All eighteen shipped GOES
binaries are scanned for printf conversion specifiers. **DL.EXE -- the
executable Wave 4 graded 4,365 owner/moon-id constraints against -- contains
no floating-point conversion at all** (its whole format set is `%02d %d %ld
%s %u`), and neither does any other module except NOCTIS.EXE, PAR.EXE and
SL.EXE. PAR and SL print only star coordinates and a distance. The **only**
planetary number any 1996 binary ever prints is `nearstar_p_ray` at `"%1.4f"`
on NOCTIS.EXE's graphical HUD (NOCTIS.CPP:3083).

**And that one printout is blind to the open question by construction.**
Measured, not argued: `ray` moves on **0 of 2,846 bodies** under the cast
axis and 0 under the castsrc axis, because phase F (`:4306`) overwrites
`p_ray` for every body from `avg_planet_ray[type]` and `zrandom(100)` -- an
integer argument. Under a 53-bit engine it moves on some bodies but never by
as much as 5e-5, so a `%1.4f` readout could not see that either. Even a
perfect capture would support only **|ours − theirs| < 5e-5, a BOUND, never
an equality**, and it would settle nothing.

**How sharp the reference-vs-reference grading actually is -- measured.** The
:4092 eccentricity store is perturbed in a sandbox copy of `geo_ref.c`, built
with the real compiler, and re-graded. `orb_ecc` is terminal, so nothing
cascades and the counts are the grading's raw resolution:

| perturbation | caught (200-system corpus, 951 planetary `orb_ecc` values) |
|---|---|
| 1 ULP of the **stored binary64** (`nextafter`) | **951 of 951 -- 100%** |
| 1 ULP of the **live 80-bit intermediate** (`nextafterl`, 2048× smaller) | **0 of 951 -- 0.0%**, effectively invisible |

So section 3 of the test is exact to one binary64 ULP **and is a BOUND below
that**: it is structurally blind to any perturbation of an 80-bit
intermediate that does not change the rounding at a store. The test states
that in those words rather than implying an equality it does not have.

**Route to settling it properly.** There are only two, and both are
expensive: (a) instrument NOCTIS.EXE under DOSBox-X to dump `nearstar_p_*`
after `prepare_nearstar` -- which is a debugger exercise on a graphical,
keyboard-driven program, not a capture; or (b) find a 1996-era artifact that
records geometry (a save file, a player's screenshot of the HUD radius). (b)
would still only give the bound above. Until one of those exists, **geometry
must not be quoted as graded**.

---

## 3. The DL capture blind spot (`bclip`) -- **SETTLED**

**Status.** Closed. It was a gap in the capture set, exactly as
WAVE4_NEARSTAR.md section 4 predicted, and not in the method.

**Evidence.** Wave 4's `bclip` sabotage -- phase B skipped when `nop <= 4` --
scored a perfect 4,365 / 4,365 against the 122-capture set because that set
contains no class-0 star with `nop <= 4`. 88 further DL.EXE captures were
taken for exactly that shape. Against the extended **210**-capture set the
same sabotage loses **110 of 4,707** constraints (97.66%); first mismatch
`JUNOVA` body 6 `MONNEZHA`, want owner/moonid (3,0), the sabotaged port says
(2,1). The unmutated port scores 4,365/4,365 and 4,707/4,707.

**What keeps it honest.** `tests/test_geometry.py` section 7 rebuilds **both**
ports with the real compiler on every run and grades both against both sets.
It requires all four results: unmutated 100% on both, `bclip` still invisible
to the 122 (so the recorded blind spot cannot be quietly rewritten), and
`bclip` caught by the 210.

**Unchanged:** `gadd` remains invisible to both 1996 artifacts, for the
structural reason in WAVE4_NEARSTAR.md section 4 (phase G is the last drawing
phase and every later `rand()` user re-seeds). That is not a capture-set
problem and no capture set can fix it.

**One caveat, recorded because it cost a QA pass to find.** The stored
captures are not byte-reproducible from the checked-in tree: `DL.CPP`'s
`notesabout()` returns 0 when `gh == -1`, and the batch3/4/5 captures were
taken with `..\DATA\GUIDE.BIN` **absent**, while GUIDE.BIN is present in the
tree today. Re-running the same commands now emits extra `(N NOTES)` lines.
The graded content is unaffected -- the object tree and every `$NN`/`[NN`
marker is identical, and the port scores 100% against notes-carrying captures
-- but nothing in the repo records the dependency. **Route:** either note the
GUIDE.BIN precondition in `tests/gen/recon_c/README.md` and in
`w6c_redo.py`, or re-take the whole set with GUIDE.BIN present.

---

## 4. `nsrun` validates its NSIN payload length -- **SETTLED**

**Status.** Settled by the delivered `nrfilebytes` guard.

**Evidence -- behavioural, not a text search.** `tests/test_geometry.py`
section 8 builds the delivered port and feeds it an intact file whose header
claims **8** records, then a file whose header still claims **8** while the
payload holds **5**. The intact control emits 8 records; the truncated input
is refused and leaves no `nstopo.bin`, including no stale output.

`work/nsrun.txt:166` reads the file size into `nrfilebytes` and compares it
against `16 + nrn * 8 * BYTES PER UNIT` before processing records. The Python
reference (`geo_spec.py`) independently validates the same bound.

**Evidence -- the guard and its behavioural result.** Two lines after
`A = [nrhdr plus 2]; [nrn] = A;`:

```
	A = [nrn]; A * 8; A * BYTES PER UNIT; A + 16;
      ? [nrfilebytes] < A -> nrdie;
```

`tests/test_geometry.py` section 8 compiles the delivered port and confirms
that the truncated file is refused (no `nstopo.bin`, including no stale
output) while the intact 8-record control still produces 8 records.

---

## 5. Intermittent Stardrifter interior-light flicker -- **SETTLED**

The observation came from the public `v0.1.0-beta.1` build on 2026-08-10 and
predates the source-faithful ship-palette path in `ce730ad`. Current ordinary
interior lighting updates only on simulation ticks, so 60 FPS presentation
cannot alternate its palette independently. Random lamp variation remains
confined to the original emergency-light state.

On 2026-08-14, two fresh production runs held the same fixed Stardrifter view
for 15 seconds, one at the original 18.2 FPS presentation rate and one in
smooth mode. Their complete 213,956-pixel game viewports were identical. The
top 54,090-pixel and bottom 72,120-pixel hull-light regions each had zero pixel
differences as well. Both runs remained healthy and reported 18 and 58 FPS,
respectively. The earlier report is therefore closed as a defect of the old
build, not a current rendering fault.

---

## 6. Sun beams and lens flares across the game -- **OPEN / DOCKET**

Authenticate the complete sun-beam and lens-flare treatment against native
captures across every star class, every planet class in representative surface
atmospheres and weather states, single- and multiple-sun situations, orbital
planet views, and the Stardrifter interior, cupola, and exterior. The comparison
must cover direction, occlusion, colour, intensity, geometry, and transition
behaviour. A flare merely being present is not sufficient; the implementation
must match the native renderer in each context.

**Completed foundation.** The flare raster, clipping, trig setup, ghost
reflection, surface occlusion, and brightness-band behaviour now match direct
NIV+ page dumps. A 12-class star matrix compares four 64,000-byte checkpoints
per class (white core, flare, smoothing, and mask), with zero differing bytes
across all 48 comparisons. A thirteenth space case uses the exact opening
Stardrifter star (`40DDB22D`) and 200-unit gallery distance; its four complete
pages also match the Borland-built NIV+ oracle with zero differing bytes.
Nine surface-flare oracle cases likewise have zero page differences. Three of
those cases use the exact binary32 ray and distance captured from the current
thin-atmosphere, quartz-world, and clear habitable-world scenes.

**Playable evidence so far.** A fresh sequential opening Stardrifter capture
shows a bright filled corona and radial beams at 60 FPS, backed by the exact
four-stage comparison above rather than appearance alone. The habitable scene
shows its sun disc. East-facing surface captures
also expose why the thin-atmosphere and quartz scenes can show a conspicuous
near-vertical ray across the ground: the captured thin input is ray
`40A4CCCD`, distance `42E0A1F0`, while quartz is ray `40A4CCCD`, distance
`457B07C0`; both complete 64,000-byte flare pages match the Borland-built NIV+
oracle exactly. That bright ray is therefore authentic flare geometry for
those inputs, not the unrelated black horizon-pillar defect. Parallel
screenshot processes can interfere and produced two all-black captures, so
this matrix must be captured sequentially. Still open: representative views
for every planet and atmosphere class, weather and day/night boundaries,
companion and multiple suns, orbital views, and the full Stardrifter
interior/cupola/exterior transition.

A generated class-8 system is now part of the reproducible capture gallery.
Its 300-degree view shows a planet partially occluding the primary disc while
the companion flare remains separately visible. This is useful production
coverage and proves both sources are live, but it does not by itself settle
native full-context ordering or occlusion parity; that comparison remains open.

The production habitable-world sweep also exercised the source weather gates:
full flare at rain 0.5 and 0.625, sun without primary flare at rain 1.67 and
2.0, and storm rendering without a flare at rain 2.5 through 5.0. The clear
case's complete flare page now matches the native oracle byte for byte.

The Stardrifter local-system pass now restores the companion-star corona's
source expression too: each type-10 body reseeds the fast generator with its
body index plus the signed system-star X coordinate, then passes the narrowed
`0.15 - fast_flandom() * 0.3` factor to `whiteglobe`. The former fixed `0.15`
factor was a real multi-sun mismatch. A fresh ROTOR IGNE product smoke retained
both the eclipsed primary and companion beam field at 60 FPS. Full-context
native framebuffer comparison remains required before this matrix is closed.

**Required authenticity matrix.** Capture and compare the visible beams, disc,
ghosts, and occlusion against the native renderer for:

- every planet and atmosphere class, including clear, cloudy, stormy, horizon,
  overhead, sunrise, and sunset views;
- every sun class and colour, including companion and multiple-sun scenes;
- orbital planet views with the sun both beside and behind the globe;
- the Stardrifter interior, cupola, exterior, launch, and landing transitions.

Do not treat the beams as incidental flare decoration. Grade their count,
origin, direction, length, spread, colour, brightness, clipping, and palette
interaction separately for each planet/sun pairing. The Stardrifter cases must
also cover beams seen through the cockpit and cupola geometry, from outside the
ship, and while crossing between surface, launch, space, and landing states.

Each case needs a matching native viewpoint or raw framebuffer oracle. Visual
plausibility alone does not close this item. The finished result must look and
behave authentically in motion, including beam direction, clipping, brightness,
palette response, and transitions between contexts.

## 7. Cross-references

| document | what Wave 6 changed in it |
|---|---|
| `FLOATPOLICY.md` §0, §3.3, §5 table, §6.1 | the cast boundary is settled for the original; the interim rule survives but now guards the code generator rather than covering an unknown |
| `WAVE4_NEARSTAR.md` §4, §5, §6 | `bclip` closed; the cast boundary settled; geometry still ungraded, with the reference status added |
| `tests/test_geometry.py` | the regression test for all four entries above |
| `noctis-harness/geo_grade.py` | the wave's own run. Its summary line still prints "the cast boundary stays OPEN", which entry 1 refutes; read it for the measurements, not for that sentence |
