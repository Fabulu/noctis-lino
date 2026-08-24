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

**Fresh-start sun defect.** The first visible sun in the JavaScript build has
been observed with a black-square dither pattern across its disc. Determine
whether desktop Lino produces the same pixels by replaying the identical fresh
start, then grade both implementations against a pinned NIV+ framebuffer and
palette capture. Preserve the input state, indexed framebuffer, palette, and
sun-stage intermediates. Do not classify the pattern as authentic unless the
native oracle reproduces it.

**JavaScript defect fixed locally on 2026-08-16.** The portable translation of
`VHT smooth grays` incorrectly carried EBP between destination pixels. The x86
back-edge actually lands on `xor ebp,ebp`, so every output begins with a fresh
packed-lane accumulator. Correcting that one control-flow edge removes the
black lattice from the stellar core. The optimized JavaScript path now matches
the pinned Borland NIV+ white, flare, smooth, and mask pages across all 64,000
bytes at every stage. A separate checkpoint defect caused the spectacular
screen-filling white smear: old saves retained `MgApreached` but omitted the
paired `MgStspeed` drive/fade flag. Checkpoint version 17 now persists that flag
and reconstructs the stable stopped-drive invariant for versions 1 through 16.
Desktop and browser captures of the same migrated opening fixture now show the
bounded filled sun and flare. The broader cross-class/context coverage below
remains open.

**Reopened by a later public-build report.** A player subsequently observed
the white Stardrifter smear spreading across the screen, retaining hundreds of
black dots, and becoming expensive enough to collapse the frame rate. Treat
that report as authoritative for its persisted session even though a fresh
local version-17 checkpoint now remains bounded during stationary and held-key
runs. Capture the player's stored `CURRENT.LIN`, exact deployed asset identity,
drive state, and successive indexed pages. Do not call the symptom authentic
or closed until that real state is reproduced and compared with the native
renderer.

**Space-effect cadence fix staged on 2026-08-16.** Smooth presentation had a
second independent way to exaggerate persistent effects: between authoritative
18.206-Hz flight ticks it reran `pfade` and submitted the identical additive
stars, suns, and flares two or three times at the same pose. The completed
indexed flight page is now reused on those duplicate presentation frames.
Surface interpolation and the per-presentation fine-approach step remain live.
A 30-second browser smoke held the Stardrifter effect bounded across successive
captures, reduced the steady runner cost to about 2.1 ms per presentation, and
ended at a reported 57 rendered FPS on a 60-Hz display with no browser errors.
This addresses cadence amplification and its redundant renderer cost. It does
not close the player's persisted-session report or authenticate the complete
Stardrifter composition against NIV+.

**Current post-repair replay, 2026-08-17.** A fresh browser start was turned
through sixteen consecutive cockpit views and a separate twelve-frame
stationary sequence. The visible sun remained a filled bright core with bounded
radial and ghost flares; no black lattice, persistent white band, stray line,
or increasing frame cost appeared. The stationary sequence ended around
57 rendered FPS with roughly 1.8 ms of runner work, consistent with the exact
four-stage oracle below. This is useful current-build evidence, but it does not
replace the missing persisted checkpoint from the reported failing session or
the still-open cupola/exterior transition coverage.

**Completed foundation.** The flare raster, clipping, trig setup, ghost
reflection, surface occlusion, and brightness-band behaviour now match direct
NIV+ page dumps. A 12-class star matrix compares four 64,000-byte checkpoints
per class (white core, flare, smoothing, and mask), with zero differing bytes
across all 48 comparisons. A thirteenth space case uses the exact opening
Stardrifter star (`40DDB22D`) and 200-unit gallery distance; its four complete
pages also match the Borland-built NIV+ oracle with zero differing bytes.
Ten surface-flare oracle cases likewise preserve their expected pages. Four of
those cases use the exact binary32 ray and distance captured from the current
thin-atmosphere, quartz-world, clear habitable-world, and airless lunar scenes.
The lunar case is the source-gated unchanged-page negative described below.

The vertical and fixed-point spoke pixel loops now execute as bounded native
kernels instead of one Lino dispatch chain per sampled point. They preserve the
source clipping, exclusive vertical endpoint, every-other-position general
sampling, low-six-bit saturation, write order, and final fixed-point cursors.
The ten-case probe retains its exact 640,000-byte before and after hashes,
including the four real surface inputs. One matched thin-world product sample
reduced measured rendering from 8.71 to 6.96 ms; host timing varied on later
runs, so the pinned page hashes and eliminated interpreter loop are the durable
evidence rather than that single timing delta. The registered
`test_surface_flare_oracle.py` gate now rebuilds the focused probe from current
source and requires the six-page concatenated Borland oracle, the exact thin,
quartz, and habitable positive pages, and the unchanged lunar lower-gate page;
the former stale `mgmain`/`vhstar` programme dependencies were removed from the
probe rather than being allowed to mask source drift.

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
additional companion and multiple-sun arrangements, orbital views, and the
full Stardrifter interior/cupola/exterior transition.

The thin gallery case now also has a full-context NIV+ oracle, not only the
synthetic uniform-page flare check. An instrumented Borland build rendered the
exact body, longitude, latitude, player position, pitch, heading, and pinned
clock through `planetary_main`; its pre/post-flare pages changed 2,833 bytes and
contain the same long near-vertical spoke. The gallery camera uses pitch -40 so
that authentic spoke reads as part of the radial flare in the sky instead of
resembling the unrelated horizon-pillar defect across the ground.

A generated class-8 system is now part of the reproducible capture gallery.
Its 300-degree view shows a planet partially occluding the primary disc beside
radial light spokes. Live tracing corrected the earlier interpretation of
those spokes: the companion star is off-screen and its flare gate is closed in
this view. They are Stardrifter fixture lights, not a second sun. The scene is
still useful production coverage, but it is not evidence of a visible
companion flare.

The production habitable-world sweep also exercised the source weather gates:
full flare at rain 0.5 and 0.625, sun without primary flare at rain 1.67 and
2.0, and storm rendering without a flare at rain 2.5 through 5.0. The clear
case's complete flare page now matches the native oracle byte for byte.

The Stardrifter local-system pass now restores the companion-star corona's
source expression too: each type-10 body reseeds the fast generator with its
body index plus the signed system-star X coordinate, then passes the narrowed
`0.15 - fast_flandom() * 0.3` factor to `whiteglobe`. The former fixed `0.15`
factor was a real multi-sun mismatch. A fresh ROTOR IGNE product smoke retained
the eclipsed primary and ship-light field at 60 FPS.

**ROTOR IGNE native-context checkpoint.** A certified NIV+ run and the current
Lino renderer were placed at the same class-8 system, body 0, source UTC phase,
1.8-radius orbital distance, cockpit position, user yaw, and navigation yaw.
Lino reported the native body radius `0.01632`, distance `0.029376`, projected
centre `(158,100)`, and magnification `0.5555555`. At UTC second `1344854657`,
its selected-body vector differed from NIV+ by less than `2.5e-10` on every
axis. Both full-context frames kept the primary behind the planet and emitted
no companion flare. This settles that one dark, aligned viewpoint and the
identity of the showcase spokes. It does not settle visible companion views or
the wider matrix below.

**ROTOR IGNE exterior-pose correction.** The earlier claim that the open-visor
navigation-120 checkpoint showed body 3 was invalid. A retained NIV+ BMP now
brackets the source camera on both sides of the snapshot: position
`(0,0,-500)`, `user_alfa=-34`, `user_beta=0`, `navigation_beta=120`, fixed-chase
`TRACKING`, and raw clock `1344638526.8333333`. Its target-relative Stardrifter
position differs from the second-1344638526 product diagnostic by less than
`7e-6` on every axis. The native companion crop contains one ordinary bright
star and no corona or radial flare.

The defect was the exterior camera, not the companion raster. Native
`from_vehicle()` installs `user_beta + navigation_beta + 180`; the product had
omitted the final half-turn based on an inadmissible visual alignment. It
therefore projected the behind-camera companion to `(145,117)`, reported a live
flare, and filled the crop with 1,393 non-background indices. Restoring the
source half-turn makes the projected depth negative, clears the companion flare
flag, and leaves at most two ordinary star points in the same crop. Complete-page
equality remains ungraded because DOSBox-X was suspended after the BMP closed
and `adapted` had already entered the next frame; the retained BMP itself is the
exact indexed-page and active-palette authority for this negative visibility
contract.

The prior shared-workspace, binary64-radius, stationary-drive, and fixed-chase
repairs remain source-grounded and independently protected. Active local-system
checkpoints restore `stspeed=0`, `ap_reached=1`, use the source viewport clear,
and report `TRACKING`.

A second retained capture rotates only `navigation_beta` from 120 to 300, so the
corrected source half-turn makes body 3 genuinely front-facing. The native BMP
now authenticates the type-10 companion's white corona and radial flare: the
pinned crop contains 151 pixels above six-bit component 32, versus one ordinary
star in the behind-camera control. The matched product retains the clock and
camera, brackets the target-relative position within `0.003` on each axis,
projects the companion in front of the camera, sets its flare diagnostic, and
renders a real corona and rays. Its crop currently contains 61 pixels above the
same threshold and its complete page differs at 16,155 indices. Those brightness,
shape, palette, and whole-page gaps remain open; this positive capture prevents
them from being hidden behind the now-correct negative checkpoint.

A scoped source audit found no material caller divergence that can explain that
61-versus-151 count: native and product retain companion seeding, binary64 ray,
binary32 distance, companion-before-primary flare order, smoothing, and masking.
Both paths clear rather than accumulate: the fresh native process initializes
`stspeed=0` and queues only the snapshot key, while the product restore path also
installs zero. Prior fast-generator phase is irrelevant because both companion
callers reseed immediately. The native snapshot still lacks exact fractional-time
companion coordinates and pages at the white-globe, flare, and smoothing
boundaries. Do not tune the flare from this measurement. The discriminating
native capture must export those exact inputs and the page after each stage; only
then can the product repair the first proven divergence, or limit the residual to
palette easing if all indexed stages match.

The discriminating capture path is now implemented without changing the upstream
NIV+ clone. `instrument_rotor_igne.py` generates an exactly anchored source copy,
materializes the companion's real one-time random factor, and atomically publishes
a 192,062-byte `ROTOR.BIN`: a 62-byte typed scalar header followed by the three
64,000-byte pages after companion corona, after companion flare, and after
smoothing before masking. Pages are written as 200 normalized huge-pointer rows,
and `capture_orbital_w7b.py` can stop on the completed file while preserving and
restoring pre-existing sandbox outputs. The registered ROTOR oracle checks the
trigger, field order, 16-bit header layout, one-time RNG use, stage order, size,
and close-before-rename publication against the available source.

This tooling is not itself the missing native evidence. The ordinary NIV+ build
route requires Borland C++ 3.1, which is absent from the accessible, non-protected
fixture tree; no protected `.tmp-*` compiler or capture tree may be reused. A real
`ROTOR.BIN` and its product-stage comparison therefore remain open rather than
being inferred from the static instrumentation.

**IDEAL orbital camera pair.** Two retained class-0/type-1 captures bracket
the same raw second, fixed-chase state, palette, and Stardrifter position while
changing only `user_beta` from 0 to -97. The exterior view authenticates the
complete lunar globe silhouette with the primary outside the viewport. The
turned view authenticates the primary corona and radial rays through the
Stardrifter interior, including ship occlusion. At the exact product clock and
camera, the star-relative Stardrifter position differs by less than `1e-6` on
every axis and the lunar radius and distance are exact. The exterior palette bands
differ only at 35 product-only globe-limb pixels.

The current private-desktop interior capture also retains the required source HUD
and `-OpenHud` composition. It now uses native fixed-chase sync 1 and visibly
retains `TRACKING`; a compensated authored local Z converges to the exact staged
`0.01283555` target distance. Compared with the earlier sync-0 discriminator,
this changes 491 complete-page indices but zero pixels in the graded crop, while
the 1,190 complete-page palette-band mismatches are unchanged. All 18,000 pixels
in `(30,30)-(180,150)` retain the native palette band, and 17,395 retain the
exact index. Exchanging the pages and palettes gives four brightness counts
above six-bit component 32: native/native
8,338, native/product 8,338, product/native 8,215, and product/product 8,215.
Neither crop contains index 77. The current 123-pixel deficit is therefore
entirely selected by the 605 same-band indexed-page differences; the 54 palette
component differences contribute zero in this crop. Upper and lower projected
HUD rows account for 460 differences and 66 deficit pixels; 367 product values
equal native X-1, directly assigning that portion to cross-host projected-font
fidelity. The remaining 145 differences and 57 deficit pixels occupy right
fixture and central flare regions. A source/port trace retains the same
composition order, float-local clipping and truncation, x87-width spoke products,
center and `Stick` sampling, and two source-ordered smoothing passes; the reviewed
angular-step difference is inactive at this camera. Native pass-level indexed
buffers and projected endpoints were not retained, so those 145 pixels do not
yet support a repair. Complete-page, complete-lighting, and complete-palette
equality remain informational because the BMP capture still lacks snapshot-time
simulation and palette-easing state.

A third IDEAL capture now supplies the previously missing genuine primary-beside-
globe positive. It holds the class-0/type-1 system at raw second `1344638736`,
uses a sync-0 target-local pose `(-0.01181518607173147,
0.0000025128783893597895, 0.005015248936280497)`, and turns only to
`user_beta=67`. The following-frame native continuity block retains that staged
star-local position within `3e-11` on every axis, with `STANDBY` flight control.
Through separate Stardrifter windows, the native page shows the clipped primary
immediately beside the dark lunar limb. The 4,000-pixel primary-window crop has
exact native/product palette-band and brightness masks: 2,408 dark pixels and
1,592 bright pixels. The native globe's band-3 mask is 8,620 pixels in
`(106,51)-(217,148)`; the product has 8,535 in `(106,51)-(216,148)`, with only
99 bounded limb-mask differences. The retained pre-repair complete pages differ at
6,478 indices and their active palettes at 241 components, so those remain
informational. This closes one real orbital beside-primary composition, not the companion-stage
or Stardrifter transition gaps.

**IDEAL roof/cupola checkpoint.** A fourth capture holds the same sync-0
class-0/type-1 system at raw second `1344638737` and moves the player to the
stable source roof pose `(0,-750,-1900)`, looking outward at `user_beta=180`.
Its 1,200-unit distance from the cupola aperture remains outside the source's
`<1100` automatic-return gate; the following native continuity block retains
`lifter=0`, `STANDBY`, and the staged star-local ship position within `3e-11` on
every axis. The captured BMP's complete 64,000-byte indexed page is also exact
to the frozen post-snapshot framebuffer, rather than having entered the next
rendered page.

At the matched clock, position, camera, radius, and distance, the product retains
59,804 of 64,000 exact page indices. It retains 31,977 of 34,200 exact indices
in the upper exterior cupola/aperture crop and 18,586 of 19,800 in the lower
hull crop; their palette-band differences are bounded at 1,660 and 1,190. This
authenticates the stable roof branch's upper cupola, grid, aperture, and exterior
hull composition while keeping the intensity gap explicit: native/product bright
counts are 21,521/20,346 in the cupola crop and 622/307 in the hull crop. The
retained pre-repair product palette differed at 241 components. Complete-page and
exact lighting remain ungraded because the frozen continuity variables still follow
BMP serialization rather than being snapshot-atomic. This checkpoint protects
one stationary exterior-cupola state.

**IDEAL strict cupola-boundary pair.** Two further captures hold the same
class-0/type-1 target, raw second `1344638737`, sync-0 ship position, stopped
lift, palette, pitch, and outward heading. They differ only at the source's
strict `pos_y < -500` predicate: `(0,-500,-1900)` remains inside, while
`(0,-501,-1900)` selects `ontheroof`, redraws the upper cupola after the hull,
and returns before interior details. The native pages retain 59,428 of 64,000
identical indices with only 649 palette-band differences. In the status crop,
the inside frame adds 465 bright pixels without changing any palette band; in
the left target/FCS telemetry crop it adds 538 bright pixels, with none lost.
Both following native blocks retain the common state and star-local position,
but their pages had advanced by 7,958 and 12,208 indices, so complete-page
same-state authority remains disabled.

At those exact product states, the just-outside page retains 61,619 native
indices with 1,588 band differences, suppresses the interior overlays, and
remains byte-exact to native across all 4,620 pixels of the lower telemetry
crop. The inside path retains the two source range rows with the native binary64
`5E-5`/`1E-2` scales, two-decimal rounding, fixed visor cameras, indexed glyph
geometry, colour bands, spacing, and `L.Y.`/`DYAMS` suffixes before both smoothing
passes. Two private launch pairs retained identical scoped indexed rasters while
the ungraded product palette varied; the exact range crop is therefore the
runtime contract, with observed inside brightness of 750 pixels versus native
601 and an unchanged roof count of 63.

The same path now restores the preceding fixed 24-character star and selected-
body rows at native camera Y values `250` and `180`, colours `127` and `112`, and
40-unit advances. Live `STARMAP.BIN` hits supply the 20-character names; unknown
stars, planets, and moons retain the source `UNKNOWN STAR / CLASS Snn`,
`NAMELESS PLANET / N. Pnn`, and `NAMELESS MOON #mm/pp&Pnn` forms. The native
upper-label crop adds exactly 275 bright-mask pixels at the inside boundary; the
product's repeat-stable indexed label crop is present inside and has the distinct
roof-suppressed hash outside. This contract uses the ordinary source-HUD-enabled
capture state without `-OpenHud`; the replaced inside-label hash belonged to the
moving open-visor composition. The just-inside complete page retains 23,698 native
indices with 3,932 band differences. Direct star/body editing is now closed by a
private-inactive-desktop runtime gate: it proves editor input ownership, uppercase
conversion, Backspace, physical-Escape cancellation while the key remains held
through a following capture, release survival with the Escape latch observed clear,
Return, the 20-byte cap, and exact 32-byte `STARMAP.BIN` appends. A 32-byte state
diagnostic also proves the active editor preconditions and the native `EXTANT` result for a case-insensitive
duplicate plus `DENIED` for consolidated-record removal; player-local identity
tombstones remain byte-exact. The same gate freezes simulation while rebuilding
complete 64,000-byte indexed pages and samples the native
`127 - 2 * (clock % 32)` cursor phases in eight-step increments. A full modulo-32
cycle reproduces every page byte; a distinct phase changes only 34 underscore
pixels at `(83,32)-(91,35)`. At the same blink phase, an invisible trailing
space changes only the 72 old/new underscore pixels at
`(83,32)-(102,35)`, translating the raster 11 pixels to its next fixed position.
The HUD wrapper now returns before projection for spaces and out-of-atlas bytes,
so padding cannot remap the previous underscore across the rest of the row.

The lower environmental row now follows the source in modes 0 and 1: its gravity,
temperature, pressure, and pulse fields continue smoothing by one quarter, one
twentieth, one fiftieth, and one hundredth respectively, while `wrouthud`'s
`draw_hud` gate still owns visibility. The product constructs the exact source
spacing and fixed-point units from source defaults. All four visor lamps now run
`smootharound_64`'s strict radius-five disk in left-to-right, top-to-bottom order,
averaging each overlapping 2-by-2 low-six-bit block in place while retaining each
pixel's palette band.

The retained native inside and roof pages share a 69-pixel normalized mask over
`(2,192)-(30,197)`, covering `GRAVITY` and the lower-left lamp fringe. Both latest
ordinary product pages match those 140 native indices byte-for-byte, and a second
private pair after recompilation has the same scoped raster. This closes the
missing environmental HUD construction and its lamp interaction without claiming
that different accumulated smoothing histories make all numerical glyphs across
the complete row byte-identical.

The first concrete palette divergence is also closed. `VHG palette` had invented a
warm `128..191` bootstrap even when no resident moon owned that band. Native
`surface()` selects and uploads band 128 only for a moon and band 192 for a planet;
the retained IDEAL target is a planet and its native moon band is entirely black.
The product now leaves that absent band at `PAL zero`. Fresh private inside and
roof captures have zero nonzero components there and match all 192 native
components exactly, removing 187 of the previous 241 complete-palette mismatches.
The remaining 54 components are not graded as defects because the native snapshot
did not retain its palette-easing phase. The matched open-HUD interior flare crop
uses only bands 0 and 1; its four-way 8,338/8,338/8,215/8,215 brightness matrix
proves those components contribute zero to the current 123-pixel gap. The 460
projected-HUD differences move to the cross-host font docket. The 145 remaining
flare/fixture differences stay open only for pass-level attribution; the reviewed
source and port paths do not support a speculative repair.

Actual lift motion is now closed at the production indexed-page boundary. An
opt-in `lifttrace` launch on a private inactive desktop records, after rendering
and the source-order restraint, eight signed 32-bit scalar fields plus the
complete 64,000-byte indexed page on each authoritative simulation tick. The
live ascent exactly retains the eight `-100,-199,-297,-394,-490,-585,-679,-750`
vertical states, and a separately staged roof return retains all twelve states
from `lifter=+75` through the exact `y=0` clamp. Both directions switch the roof
branch only across strict `y < -500`; camera pitch and forward restraint retain
the observed source ordering, and all 20 indexed pages are distinct. The trace
is gated by a complete command-line token and by `VHGdosim`, so ordinary
launches neither pack nor write it and 60-Hz presentation does not duplicate
simulation states.

Exact projected glyph raster across hosts, complete interior lighting, the
remaining unretained palette-easing state, and whole-row numerical environmental-state
equality remain open rather than being claimed as full parity.

The generic orbital gallery had retained the target-local signs authored around
the former missing exterior half-turn. After the camera repair those eleven
poses looked away from their targets. Their local X/Z offsets are now negated
while preserving the authored 23-degree cockpit axis; a fresh default IDEAL
capture again places the type-1 globe in the forward window. Exact orbital-local
X/Y/Z overrides are all-or-none, and a bounded orbital-sync override permits
native fixed-chase discriminators without changing the ordinary sync-0 gallery,
so matched oracle captures no longer need
to distort the camera to reproduce a retained ship position.

**Frozen-world native-context checkpoint.** The landed NIV+ capture rig now
accepts independent capsule and player coordinates plus the exact camera pose
needed by product checkpoints. Source `user_alfa` is vertical pitch and
`user_beta` is heading; reversing them produces an impossible camera and is
not admissible oracle evidence. A certified type-7 capture placed the player
at `(1645000, 1641000)`, the remote capsule at `(131072, 131072)`, pitch at
`-12`, and heading at `193`. This removed the huge vertical lines produced by
the earlier invalid capsule-underfoot setup and broadly aligned the native and
Lino ground views. A separate lens-mode `0` versus `-1` pair changed only one
gameplay viewport pixel, proving those earlier lines were the capsule's own
three locator beams, not lens flare. NIV+ still has sparse sky points absent
from the earlier all-black Lino sky. Source inspection identified the missing
`sky(003Eh)` call: on dark, dry surfaces it uses the Stardrifter's galactic
position with the player's walking angles after the planetary background and
before both suns and the palette mask. That exact mode and ordering are now in
production. A fresh frozen-world product smoke shows the same sparse field;
31 unobstructed native star components align with the Lino points after the
capture-frame offset. Three dim or top-edge points still need raw-page palette
grading, so the omitted pass is fixed but whole-frame frozen-sky parity remains
open. This pose cannot authenticate the primary sun, which is off-screen in
the current Lino trace.

The shared galaxy renderer no longer rounds the view into four-degree buckets
or reuses a moving Stardrifter position for an arbitrary frame count. Its draw
cache now requires exact integer angles and bit-identical binary64 coordinates.
Three fused x87 kernels retain the established subtraction, narrowing,
rotation, depth, and projection schedule while removing the interpreted helper
chains that made exact turning too slow. The frozen checkpoint retained all 34
visible sky pixels exactly across the change. A ten-second alternating turn
dropped from 17.90 ms to 16.29 ms of measured render plus presentation work per
frame, while the stationary Stardrifter checkpoint held 60 FPS.

A matched-clock frozen-world run exposed an upstream lighting-state defect.
The general surface path computed the live terminator correctly, then the sky
handoff replaced its night flag, dawn/dusk side, and exposure with the special
opening-system defaults before deciding that no recomputation was needed. Those
defaults now live only inside the opening-system compatibility branch. At the
type-7 checkpoint NIV+ and Lino now both retain exposure `18.7824`, classify the
pose as night, and suppress the primary sun. The bright point previously read
as a possible sun was a galaxy star revealed by the false daylight state.

Automated gallery captures now pass an explicit source UTC second through the
shipping executable's `clock=<decimal>` capture option. The default fixture
second is the one already stored by the authored checkpoints. Interactive and
ordinary launches do not pass the option and continue using live UTC. This
removes wall-clock drift from planet, weather, disc, and flare comparisons.

The first retained type-3 comparison was invalidated rather than used to tune
the renderer. NIV+ reloads `secs` from the DOS clock during landed resume, so
the saved fixture epoch had silently been replaced by the capture machine's
date. A Borland-built source harness with `secs=1344638527` now supplies the
valid oracle at body 3, longitude 270. NIV+ and Lino both report solar distance
`243.633`, exposure `35.9996`, rain `0`, day classification, surface class 1,
albedo 16, and surface seed 1029155. Surface lighting now obtains that distance
from the source's live phase-dependent body vector instead of the nominal
orbital radius, including the separate companion-owner rule.

That matched-state comparison also exposed an invalid camera fixture. NIV+
clamps surface pitch to `-44.9` degrees, but a fast product capture had retained
an impossible `-45` checkpoint and displaced the flare centre by 15 rows. The
capture tool now clamps authored integer pitches to the port's playable
`-44..44` range even when simulation is disabled. At `-44`, the product and
pinned native frames align the primary centre at approximately `(161,130)` and
show the same giant radial layout. The standalone page oracle already grades
this exact flare algorithm byte for byte. Exact full-context framebuffer and
palette grading for this viewpoint remains open; the false storm comparison is
not admissible evidence.

**Habitable whole-page provenance audit, 2026-08-23.** The retained 40-byte
`SURFACE.BIN` authenticates the native resume input, but it does not record the
live state that produced the later gallery frame. The native rig waits 30
seconds before typing `b`, continues the ordinary landed loop, and only dumps
RAM when DOSBox is killed at 60 seconds. That loop advances mouse input and the
ordinary HUD clock before the snapshot. The product checkpoint separately pins
solar lighting and exports after 60 presentation frames, so its complete page
is not a same-state oracle target for this BMP. The hosted ARM64 comparison
reports 30,190 differing indices but now grades only contracts the artifacts
actually establish: immutable BMP/surface hashes, the exact 768-component
palette, reproducible checkpoint and camera, every palette band including the
flare centre, the pre-smoothing flare gate and centre, exposure, and solar
distance. The exact low-six-bit final centre is not a separate same-state
contract because the two source `psmooth_64` passes mix it with unretained live
neighbours. Restoring exact whole-page grading requires a new native capture
that retains snapshot-time camera, simulation, and HUD state; renderer constants
must not be tuned against this provenance gap.

**Thin-atmosphere native-context checkpoint.** A second fixed-epoch comparison
uses the same generated system's type-5 body at longitude 45, heading 90, and
pitch -30. NIV+ and Lino both retain distance `112.235`, exposure `84.5208` at
longitude 0 and `49.3038` at longitude 45, rain `0`, day classification,
albedo 24, and seed 472392. The longitude-45 pose brings the otherwise
near-zenith star into the playable camera range. Certified native and product
frames place its disc at the top centre and show the same long radial pattern
over the teal atmospheric gradient. The reproducible `thinsun` gallery scene
now captures that pose. After removing the port's non-native rectangular
panorama-edge erase, full-context staged grading is exact: the complete
64,000-byte pages before the sun, after the sun, and after palette-band masking
each differ from NIV+ at zero pixels. This closes the reported thin-world
pillar for the complete sky and sun sequence, while final terrain and object
compositing remain separate coverage. The hosted Apple-Silicon product gate now
rebuilds this exact checkpoint and requires the native camera, all 768 active
palette components, every framebuffer palette band, the pre-smoothing flare
admission sample and centre, exposure, distance, and stellar ray. A canonical
private-Windows pass trace localized the apparent final centre discrepancy: the
completed terrain/flare page has index 126, then the exact two source
`psmooth_64(adapted,160)` passes change 22,537 indices and mix that centre to
125; the following 11,098-index surrounding-border pass leaves it at 125. This
rejects both a flare-raster defect and the earlier apparent border attribution.
Because the retained BMP omits the live neighbouring pixels consumed by those
blur passes, its final low-six-bit centre is not a same-state cross-product
contract; the gate retains the exact native centre in the artifact and grades
the product's centre band plus pre-smoothing admission state instead. The later
complete page likewise stays informational rather than being misrepresented as
a same-state final-frame oracle.

**Airless rocky native-context checkpoint.** The same fixed epoch now covers
the system's type-4 body at longitude 90, heading 270, and pitch -38. Both
renderers retain distance `9133.45`, exposure `53.2168`, rain `0`, day state,
albedo 36, and seed 38821023. Both show the small primary disc over the black
airless sky and deliberately draw no radial flare: the distance exceeds the
source's `1000 * ray` upper gate. The reproducible `rockysun` scene preserves
this negative case. Its automated product gate requires all 27,000 indices in
the native `(10,10)..(309,99)` sky crop and all 768 active palette components;
terrain/HUD-dependent complete-page bands remain informational. Authenticity
includes correct beam suppression, not merely adding rays whenever a disc is
visible.

**Dense-atmosphere native-context checkpoint.** LANE I now has a certified
stock NIV+ comparison at longitude 0, heading 90, pitch -44, and the same raw
Noctis clock scalar.  The first apparent contradiction, a native frame without
a sun, was invalid: DOSBox-X rejected the rig's `MM-DD-YYYY` command because
this guest expects `DD.MM.YYYY`, so that run silently retained a host date three
days later.  The original also counts leap days with its own 1984-based rule,
placing raw second `1344638527` on guest date 11 August 2026 rather than the
Gregorian date inferred by a host library.  With both boundaries corrected,
NIV+ and Lino agree exactly on rotation period `457`, terminator `77..207`,
distance bits `41C22E20`, exposure bits `42710A72`, and all three binary32 sun
coordinates (`C140A69B`, `C1A89AA9`, `B5774B25`). Both frames show the same
large white disc and broad corona over the purple atmosphere. The reproducible
`densesun` scene records this authenticated visible-disc lower-gate case:
`24.2725 < 10 * 5.15`, so the later radial-flare pass is correctly suppressed.
A full-context stage dump now proves more than the screenshot: the native and
Lino local-sun passes change the same 15,469 indexed pixels in the same `(70,9)..(246,112)`
box and apply the same transformation to every changed pixel. Their following
palette-band masks also cover the same 58,240 pixels in
`(0,9)..(319,190)`. The later `lens_flares_for` pass changes zero pixels in
both engines at this pose, so the visible disc and corona belong to the exactly
matched local-sun pass. The remaining 2,676 differences were all
zeroed Lino pixels in the panorama mapper's irregular edge area. The port had
added a rectangular guard-band erase that does not exist in NIV+ and could
present as a black horizon edge. Removing that erase makes the complete
64,000-byte pre-sun page exact, so the full background, sun, and mask sequence
is now byte-exact for this real scene. The final product gate requires all
64,000 native palette bands while leaving its 101 easing-dependent palette
components informational; final terrain/object low-six-bit indices remain
separate coverage.

**Airless lunar lower-gate checkpoint.** IDEAL I adds the complementary close
sun case on a type-1 world at longitude 0, heading 90, and pitch -44. Product
and pinned NIV+ memory agree exactly on the widened binary32 sun coordinates,
distance bits `420A4E15` (`34.576252`), ray bits `40DE8F5C` (`6.955`), and
exposure `49.3038`. The disc and corona are visible, but the real planetary
loop suppresses radial beams because `34.576252 < 10 * 6.955`. A direct call
to the standalone flare routine would add one spoke and is therefore not an
admissible full-context oracle for this pose. The tenth surface-flare fixture
now protects the correct unchanged page. Direct palette tracing exposed and
fixed a real stable-state error: native `resolve` starts at 1 and advances by
4, so its sequence ends at 61 and never visits 63. The old product uploaded
the unfiltered surface palette at 63. Classic and smooth product captures now
emit the exact 768 active native components, SHA-256
`ce2b034ee3da7e553e1d5ba2fd5ccaeee9721b5ee9cdb3bab4515bdb73bc0a81`,
with smooth mode interpolating only between the original 18.206-Hz fade
endpoints. The reproducible `lunarsun` scene preserves this close-disc,
no-beam case. The product gate now requires all 36,000 indices in the native
`(10,10)..(309,129)` upper-sky crop and all 768 active palette components;
complete terrain/HUD-dependent bands and low-six-bit indices remain
informational.

**Frozen-world class-1 checkpoint.** A separate system extends the matrix
beyond class-0 primaries. On its type-7 body at longitude 0, heading 90, and
pitch -44, both renderers retain star class 1, stellar radius `21.879`, solar
distance `34167.4`, exposure `58.695`, rain `0`, and day state. Certified
frames place the larger white disc against the frozen world's black sky and
again suppress beams because `34167.4 > 1000 * 21.879`. The reproducible
`frozensun` scene records this distinct star-size and no-flare case. Its product
gate requires all 64,000 native palette bands, all 36,000 indices in the
`(10,10)..(309,129)` upper-sky crop, and all 768 palette components. The lower
starfield/terrain low-six-bit context remains open independently.

**Quartz-world positive-flare checkpoint.** LANE VIII closes the omitted type-8
surface class at longitude 228, heading 270, pitch -30, and source time
`1345761727`. The frozen guest memory retained body 7 as the reached synchronous
target, `landed=1`, and live power above the target-retention threshold. Product
and native then place the admitted flare at `(161,101)` with exact final centre
index 97, exposure `29.7388`, solar distance `3923.7273`, and class-0 stellar
ray `5.15`; this lies inside `10*ray <= distance < 1000*ray`. All 768 active
palette components and all 36,000 palette bands in the
`(10,10)..(309,129)` upper-sky crop are exact. The crop's low-six-bit smoothing
history and 198 complete-page lower terrain/HUD band differences remain
informational.

**Seven-class automated surface-sun gate, 2026-08-24.** The retained type 1, 2,
3, 4, 5, 7, and 8 BMP/surface pairs are now immutable test inputs rather than
untracked capture-tree evidence. One default non-GUI run validates every BMP,
40-byte surface record, indexed-page hash, six-bit palette hash, projected
centre, and reproducible 264-byte product checkpoint. Product grading then
requires exact camera, planet and star class, atmosphere/day/weather state,
projected-sun admission and centre, pre-flare centre sample, exposure, solar
distance, and stellar ray. Habitable, thin, and quartz cases authenticate the
`10*ray <= distance < 1000*ray` interval; lunar/dense authenticate lower-gate
suppression; rocky/frozen authenticate upper-gate suppression. Authority stays
case-specific: habitable, thin, dense, and frozen require every palette band;
lunar, rocky, and frozen additionally require exact 36,000-, 27,000-, and
36,000-index upper-sky crops; quartz requires all 36,000 upper-sky palette bands
and its exact final centre index; every palette is exact except dense's
explicitly unretained easing state. The Apple-Silicon product job now executes
all seven checkpoints independently and retains each diagnostic set. Whole
final pages remain informational where snapshot-time terrain, simulation, or HUD state was
not captured.

**Frozen-world class-0 positive-flare checkpoint.** RENIET VIII body 7 adds
the missing positive counterpart at longitude 0, heading 90, pitch -20, and
the pinned source clock. The native rig now generates the requested sector
before rendering it, preventing stale terrain and object buffers from
invalidating the comparison. Current Lino and Borland NIV+ then match all
40,000 height bytes, all 40,000 object-chart bytes, and the complete 65,024
byte landed texture payload. At the post-walk camera position, both renderers
sample indexed value `108` at sun centre `(161,114)` before the flare pass and
draw the same screen-wide radial spoke geometry. The native flare changes the
centre to `126`; its pre-flare and post-flare page hashes are respectively
`37DD345C1F26969839B4AC8F8F82241016BD6515541414AC771B8D3978F58FE1`
and `09931622318561CB10470B606581EC4C09E74DC5FB03D4DC37DA9372C4E1D463`.
Moving the capsule under the camera instead yields centre sample `62` and
suppresses the flare in both engines, confirming that the gate is authentic
foreground occlusion rather than a renderer accident. The reproducible
`frozenflare` scene and `planet-frozen-sunbeams.png` publish the unobscured
positive case. This closes one real type-7 positive-flare context, not the
remaining all-class and transition matrix.

The product gallery publishes the fixed-epoch checkpoints as
`planet-lunar-sun.png`, `planet-thin-sun.png`, `planet-rocky-sun.png`, and
`planet-frozen-sun.png`, plus the positive class-0 frozen case as
`planet-frozen-sunbeams.png`. Their captions distinguish a real radial flare
from the source-gated no-flare discs so screenshots do not imply that every
visible sun must emit beams.

**Required authenticity matrix.** Capture and compare the visible beams, disc,
ghosts, and occlusion against the native renderer for:

This is cross-context coverage, not a small representative sample: sun beams
must be authenticated across all planet classes, all sun classes, and all
Stardrifter viewpoints where they can appear.

- every planet and atmosphere class, including clear, cloudy, stormy, horizon,
  overhead, sunrise, and sunset views;
- every sun class, colour, apparent size, and beam pattern, including companion
  and multiple-sun scenes where each light source is graded independently;
- orbital planet views with the sun both beside and behind the globe;
- the Stardrifter interior, cupola, and exterior in both surface and orbital
  situations, plus launch and landing transitions.

For every applicable planet class, star class, and Stardrifter viewpoint, the
matrix must include a native-positive case in which beams actually render, not
only a visible disc or a source-gated negative. It must also retain native
no-beam cases at the distance, weather, occlusion, and transition boundaries so
that increasing apparent spectacle cannot masquerade as improved fidelity.

Do not treat the beams as incidental flare decoration. Grade their count,
origin, direction, length, spread, colour, brightness, clipping, and palette
interaction separately for each planet/sun pairing. The Stardrifter cases must
also cover beams seen through the cockpit and cupola geometry, from outside the
ship, and while crossing between surface, launch, space, and landing states.

Each case needs a matching native viewpoint or raw framebuffer oracle. Visual
plausibility alone does not close this item. The finished result must look and
behave authentically in motion, including beam direction, clipping, brightness,
palette response, and transitions between contexts.

**Orbital rocky/frozen pillar report resolved, 2026-08-17.** The vertical
bands in the rocky and frozen gallery globes were not a native rendering quirk.
Matched instrumented NIV+ orbital frames showed complete textured globes. Two
port regressions combined to produce the bad captures. The exterior view added
the source half-turn twice, moving the approached world off axis, and the
two-resident cache ranked `FCmp`'s signed `-1/0/+1` result with an unsigned
predicate. A closer body therefore could not replace the first catalogue
entry, leaving the real surface map unavailable and exposing the distant
crescent fallback as stripes. The renderer now uses the port's already-shifted
exterior angle, refreshes the selected body origin before the scan, and ranks
all three resident comparisons as signed values. Fresh rocky and frozen product
captures show complete textured globes without pillars; focused regression
checks pin the comparison and camera conventions.

## 7. Smooth 60 Hz presentation -- **SETTLED / MONITORED, FPS PARITY OPEN**

Harden the optional 60 Hz renderer until sustained walking, looking, jetpack
flight, capsule travel, orbital flight, and Stardrifter movement remain evenly
paced while every gameplay decision continues at the original 18.206-Hz rate.
Acceptance requires long real-input sessions across the heaviest habitable
surface and every major mode transition, with no duplicated-pose hitch,
catch-up burst, terrain loss, input loss, or simulation acceleration.

**Desktop Lino Noctis FPS parity is a separate open acceptance item.** The
ordinary packaged desktop game must sustain the intended 60 Hz presentation
rate on the agreed reference machine in every planet class, Stardrifter mode,
orbital flight, capsule travel, and the heaviest landed scenes. A fast isolated
checkpoint is not sufficient. Measure completed presentations, renderer time,
present time, simulation ticks, missed deadlines, and input latency separately
so a cumulative frame counter, duplicated presentation, dropped detail, or
accelerated gameplay cannot masquerade as parity. Preserve the authoritative
18.206-Hz gameplay clock and require smooth pacing as well as the average FPS.

The presenter already interpolates player, ship, capsule, wave, fauna, palette,
and instrument poses between authoritative source ticks. Its cadence remainder
now uses calibrated high-resolution counts with a carried fractional residue,
removing the former whole-millisecond phase quantization. The focused current
habitable smoke held the target rate. A 30-second real-input surface session
also held forward continuously, alternated left and right yaw, and retained
terrain and detail without a crash, black pillar, or input stall.

A later product session completed a surface capsule return into the Stardrifter,
held a stationary 60 Hz interior view for 23 seconds, paused the inactive client
for five seconds, and resumed through the normal focus path. Four pre-pause
internal frames were byte-identical. The recovered frame differed in only 17
pixels, all inside the advancing epoch clock glyph, and the process exited
through its normal save path in Stardrifter mode. That closes the capsule-return
and focus-loss legs. The same audit removed the port's old `-70` lift impulse:
the live lift now uses NIV+'s `-100`, with smooth presentation interpolating the
original eight simulation steps instead of changing their gameplay timing.

**Capsule terrain withdrawal matched, 2026-08-18.** A production return capture
kept detailed terrain through roughly 2.2 seconds and showed only the distant
background bands by 3.5 seconds. A render-only NIV+ oracle then executed all 251
original ascent frames with the same deterministic LANE IV terrain buffers. Its
frame 40 still contained the nearby ground, while frame 60 had the same terrain
withdrawal; at the source 18.206-Hz tick rate those are 2.20 and 3.30 seconds.
The source changes `landed` after capsule count 32, raises the camera rapidly,
and retains the capsule grid over the receding background until handoff. The
reported few-second ground disappearance during takeoff is therefore matched
source behavior, not a streaming failure. Long-distance walking terrain loss
remains a separate bug class and is not closed by this ascent oracle.

A 60-second fine-approach session then held forward movement inside the
Stardrifter, alternated left and right view input, and captured the internal
indexed page every 15 seconds. At second 25 the live client was enlarged from
640x440 to 2560x1600 for six seconds, then restored. The window remained active
and responsive at every five-second heartbeat, all five snapshots completed on
schedule, post-load frames continued changing with the commanded view, and the
game exited through its normal save path. The final checkpoint retained fast
presentation, the same body and fine-approach state, and source-rate frame
advancement rather than a 60-Hz gameplay clock. Startup telemetry reported 61
FPS with 5.56 ms render, 3.01 ms present, and 1.69 ms space work. This closes
the orbital movement and overloaded-client recovery legs of the cadence item.

**All-class desktop checkpoint, 2026-08-18.** One production fast-mode capture
measured lunar 59, dense 59, habitable 60, rocky 63, thin-atmosphere 57,
frozen 60, quartz 60, and Stardrifter 61 FPS. Landed render time ranged from
6.86 to 10.88 ms; Stardrifter
rendered in 1.07 ms. The only miss was the thin-atmosphere capture, whose
renderer took 9.20 ms but whose host presentation rose to 8.96 ms. Its frame
was complete and showed neither the former horizon pillar nor lost terrain.
This moves the remaining shortfall out of planet-specific geometry and into
desktop presentation jitter. Keep sustained motion, capsule transitions, and
input-latency parity open; do not lower detail or accelerate the 18.206-Hz
simulation to conceal a late host frame.

**Terminal private-desktop baseline, 2026-08-23.** The current portable-FP
Windows product (`vhgame.exe` SHA-256
`15be8bb9e3e9236f113f97835a5a3994e121550c54e38ad6163ac34db7047467`)
was measured on an inactive Win32 desktop after its existing 60-frame sentinel,
with independent terminal counts rather than the startup snapshot. Sustained
forward motion reached 1.37 presentations/s on the habitable surface (725.65 ms
render; 720.30 ms game-detection-to-present response), 18.17 in open
Stardrifter space (49.49 ms; 69.40 ms), and 15.09 in close orbit (65.17 ms;
73.79 ms). Open FCS reached 12.81 presentations/s with a 73.62 ms renderer. A
20-second capsule-return attempt reached only 44 authoritative ticks and could
not complete its source 251-tick transition. Every measured presentation missed
its 60-Hz deadline; only open Stardrifter movement kept the authoritative clock
near 18.206 Hz. This supersedes the fast startup-only checkpoint for the current
binary and makes the portable scalar/render boundary an evidence-backed
performance blocker. Fix arithmetic or equivalent exact work, not detail,
cadence, or transition length.

## 8. LinoJava browser runtime and reversible fullscreen -- **IN PROGRESS / DOCKET**

Create a separate open-source project at `C:\Programmieren\linojava` that
turns L.in.oleum programs into fast browser applications and uses the current
Noctis port as its flagship playable workload. Create a second open-source
project at `C:\Programmieren\Linoctissite` for the actual hosted, playable
Noctis website. The site must consume a pinned LinoJava compiler/runtime build
rather than hiding game-specific behaviour inside the reusable language
project. The product goal is a real website version of Noctis with the
actual Lino iGUI rendered by Lino program code, game controls, sound,
persistence, resizing, and smooth presentation intact. The current HTML and
CSS chrome is temporary bring-up scaffolding, not an acceptable substitute for
the game drawing and operating its own authentic interface.

The project name does not dictate a slow source interpreter. Choose the best
implementation after measuring the language and the current port. The product
architecture is a real Lino machine implemented in JavaScript: an ahead-of-time
compiler emits optimized JavaScript regions over typed workspace memory, while
JavaScript hosts browser services such as Canvas, Web Audio, input, files, and
saved state. This must not redispatch every source operation through a slow
interpreter. Playable Noctis performance and faithful 32-bit unit semantics
take priority. Native x86 byte fragments used by the optimized desktop port
must be translated into exact portable JavaScript intrinsics or rejected with
a clear diagnostic; the browser must never silently execute a different
program. WebAssembly is optional future research, not a delivery dependency.

Audit the behavior of every iGUI title-bar, menu, and window-management action
on both the browser host and desktop build. Move, resize, minimize or fold,
hide, restore, maximize, exclusive mode, screen-off, close, and menu actions
must either perform their documented operation in that host or be deliberately
remapped to a coherent equivalent. Browser actions must not mutate imaginary
Windows coordinates or leave controls performing unrelated operations. Check
pointer capture, focus, keyboard ownership, resized work-area publication, and
state restoration across every transition. If the stock iGUI assumptions are
not portable, adapt the Lino GUI services explicitly instead of accumulating
host-side exceptions.

Treat this as a source-level iGUI behavior audit, not merely a host shim pass.
Inventory every visible button, hotspot, drag region, tooltip, and state icon
from the Lino GUI code, record its intended desktop behavior, and define the
browser and desktop result beside it. Disable or replace actions that have no
honest browser equivalent, such as moving an operating-system window or hiding
an application into a Windows-only registry. If the original title bar cannot
express a coherent portable interface, reprogram its Lino layout, labels,
tooltips, and state machine so the controls remain real Lino-rendered controls
with useful host-specific behavior. Do not leave buttons that appear to work
but perform a surprising, unrelated, or invisible operation.

Both products need an obvious fullscreen route that does not steal Escape from
Noctis. In the browser, fullscreen should present the game canvas itself, hide
the Lino desktop chrome, including its top bar, and ordinary page controls.
Reveal a small, unmistakable exit control when the pointer reaches an edge or
when fullscreen focus changes, then let it fade so it does not cover play. The
exit must also have a discoverable non-Escape keyboard shortcut. Audit the same
game-only fullscreen option on desktop, where appropriate, instead of assuming
the iGUI title bar belongs in exclusive play. Repeated entry and exit must
preserve the aspect-fitted game page, input focus, controls, audio, and saved
state. Escape remains available to the original game behavior.

Acceptance is product-level: publish both standalone repositories under an
open-source licence, deploy the Linoctis static build through the existing
Cloudflare setup and GitHub automation used by the author's other projects,
boot the current Noctis program through LinoJava, and demonstrate
windowed/fullscreen round trips on desktop browsers. Performance work belongs
in the compiler/runtime, not in reduced game detail or altered 18.206-Hz
gameplay semantics. Push source and publish the live Cloudflare site at stable,
player-visible milestones as the implementation improves, rather than waiting
for the entire port or deploying every internal edit.

**Completed browser compiler, real-iGUI, and first full-game boot milestone.** The public
[`Fabulu/linojava`](https://github.com/Fabulu/linojava) repository now contains
the independent ahead-of-time JavaScript compiler, a recursive project linker,
the complete published IsoKernel layout, explicit 32-bit workspace, shared
typed call/data stack, float32 operations, and every ordinary instruction form
used by the current Noctis project. It links 73 modules, 23 stockfiles, 56,945
programme instructions, and 5,895 labels. Portable JavaScript covers all 202
unique native fragment IDs, and the site compiles without allowing missing
intrinsics. Straight source
regions use generated fallthrough, large projects are split into bounded
browser-safe runners, and hot PGF calls use exact portable service fast paths.
The host supplies pointer state, queued ASCII, the held-key table, monotonic
counts, and millisecond sleeps. Unsupported native paths remain explicit
errors. The current compiler revision is pinned by the separate
[`Fabulu/Linoctissite`](https://github.com/Fabulu/Linoctissite) repository.
That site now ships the transitive `work/vhgame.txt` closure and native
intrinsics, compiles it in Chromium, and reaches real cupola game frames from
the actual Lino entry point. A focused browser smoke advanced five frames,
accepted W and Left Arrow through Lino memory, and produced no page or console
errors. Game-only fullscreen presents the live VHGUI rectangle without the
outer desktop title bar; a corner control, double-click, and Ctrl+Shift+F exit
without consuming Noctis's Escape key. It is deployed through the author's
Cloudflare account at
[`linoctis.pages.dev`](https://linoctis.pages.dev/).

The first host-contract defect from the iGUI audit is fixed. LinoJava now
rejects exclusive-mode requests unless the host explicitly accepts them, and
keeps `Display Status` cooperative on failure. The X11/XQuartz runtime likewise
returns failure when exclusive mode was not compiled in instead of printing an
unsupported warning and then reporting success. The stock iGUI failure path
now restores its exact former width, height, and position. The browser uses its
game-only fullscreen surface, but entry is now bridged from the real
Lino-rendered fullscreen hotspot while the browser still has a live user
gesture. Normal page chrome disappears; the corner exit and Ctrl+Shift+F
remain available. The Lino tooltip no longer advertises Escape as the required
way out. Browser CSS now preserves the current Lino display's intrinsic aspect
ratio instead of forcing every resized or folded shape to 4:3. Compiler helper
windows are also launched hidden and terminated after their output settles.

LinoJava now implements the 255-unit Global K read, write, and destroy service
used by iGUI's dormant-window registry. Browser pointer presses, releases, and
delta movements are now queued until Lino consumes them, so a complete click
cannot disappear between two `READ POINTER` calls. Display size and position
changes are applied on every isocall, matching the desktop runtime contract.
The browser publishes its real viewport as the physical display and presents
the normal 642x426 Lino window at a crisp 1:1 scale.

A single uninstrumented Chromium product run exercised the real Lino controls:
title dragging moved the window and survived sleep/wake; dormant mode changed
642x426 to 126x25 and back; fold/unfold changed 642x426 to 642x25 and back; a
size-grip drag reached 722x466; maximize reached 962x626; and the Lino
fullscreen button completed a game-only fullscreen round trip. The resize host
preserves the total drag vector even when Chromium coalesces pointer events.

Still open are the remaining iGUI action cases, especially hide or screen-off,
restore, close, menu behavior, focus loss, and repeated edge transitions in each host.
A reported fullscreen softlock has a concrete focus-transition case to reproduce: walk
toward the Stardrifter console, then click the window control that selects takeoff. The
click appears to move focus away from the JavaScript canvas, after which the game no
longer responds or advances. Pin canvas focus, pointer/keyboard ownership, fullscreen
state, and the Lino console transition before and after that click; repair the host
contract without swallowing the authentic control action, and add a browser regression
for continued movement after takeoff.

**Systemic fullscreen interaction report, 2026-08-23.** Activating the GOES
console with the mouse pointer in game-only fullscreen stole focus and soft-locked
the running game. Do not patch this as one GOES-specific event. Audit every
pointer-driven game, console, menu, cockpit, and title-control transition under
fullscreen for canvas focus, pointer capture, keyboard ownership, user-gesture
lifetime, worker advancement, and presentation credits. The regression must use
the real browser pointer route to enter GOES in fullscreen, prove that console
input and live rendering continue, exit and re-enter fullscreen, and exercise the
same contract across representative interactions. No host interaction may leave
the canvas unfocused or the Lino VM/presenter starved.

Renderer fidelity; audio; file mutation and persistence services; complete game-mode
coverage; and the performance work needed for smooth play also remain open.

**First strict-JavaScript optimization and complete runtime-data milestone.**
LinoJava now batches instruction budgets, keeps hot PGF services inside the
generated runner, and replaces the exact iGUI glyph, dimming, layer-copy, and
Stardrifter viewport loops with typed-array JavaScript kernels. There is no
WebAssembly backend or dependency. A focused state differential found zero
unit differences across the complete machine memory for the exercised frame
sequence. The public status line now calls its cumulative counter
`presentations` and separately reports a measured presentation rate instead
of looking like an FPS counter.

**Landed hot-path progress on 2026-08-16.** The JavaScript replacement for
`VHGND vload` skipped its Lino prologue: it read stale `FI` instead of the
caller's `VHGNDvv` coordinate and failed to restore `PJfwbase`. That could
suppress detail or project it through stale terrain state. The replacement now
performs both source assignments before its native body. The ordinary aligned
nearest-mode triangle-vector, mapped-step, and row-trace paths now use one
cached `Float64Array` over the same Lino memory while preserving the original
binary64 scratch writes and binary32 narrowing points. In the same stationary
rocky-world fixture, the product moved from the prior 31.8 measured FPS to
39.8 measured FPS after the row kernel was split into a JIT-sized helper. The
visible frame remained intact and the focused intrinsic regression passed.
A second delivery wave split the still-oversized vector and conservative tile
visibility kernels, cached direct code handles, and routed aligned qword reads
and writes through the same typed memory. The actual worker product then
measured 98.0 FPS in that rocky fixture with 9.4 ms average runner work. A
following Stardrifter smoke measured 73.7 FPS, stayed visually bounded, and
reported no runtime errors. This proves that the pure-JavaScript architecture
can clear 60 without reducing terrain or gameplay. The acceptance item remains
open until moving play and every planet class also hold the target smoothly.

**Habitable-tree follow-up.** A cold type-3 fixture exposed the remaining
worst case: its completed-frame rate was only 1.49 FPS on a loaded development
host even though the public per-slice timer displayed a much smaller render
cost. LinoJava now lets the original Lino tree routine generate each
deterministic model once, records its world-space branch polygons and foliage
calls in painter order, and replays them through the live facing and mapped
renderer. The bounded greenmush path is now direct JavaScript with the same
unsigned-square RNG transitions, binary32 point setup, strict projection
bounds, six-pixel stamp order, and final RNG state. Cached tree bounds permit a
conservative whole-model frustum rejection with extra foliage margin. Across
successive loaded-host samples this moved the same fixture to 3.83 FPS, then
7.48 FPS after the direct foliage path; a later visual smoke under heavier load
measured 4.21 FPS and retained trees, foliage, terrain, HUD text, and the notice
overlay without a worker error. This is a material multiplier, not completion:
habitable rendering and its multi-minute cold surface build remain open, and
the next pass must batch or cache the repeated tree polygon transforms rather
than spending effort on small dispatch savings.

That whole-tree transform pass is now implemented. Each deterministic cached
tree model interns bit-identical world vertices shared by its branch and leaf
polygons. For the current camera it performs the original binary32-narrowed
rotation and mapped projection once per unique vertex, then feeds the cached
results into each polygon in the unchanged painter order. Facing remains live;
any polygon crossing the near plane falls back to the complete mapper; texture,
flare, tint, culling, UV, and raster state are restored per command exactly as
before. On the same fixed type-3 checkpoint at heading -163 degrees, measured
rendering increased from 17.0 to 27.9 FPS. The product capture retained the
continuous terrain coverage, trees, HUD, and border without a worker error.
The corresponding continuously turning session reached 32.2 measured FPS,
compared with 18.6 FPS in the pre-cache moving run; changing the camera every
frame therefore still exercises the intended invalidation path and retains the
gain.
This is a substantial multiplier but does not close the cross-scene 60-FPS
goal, and the several-minute cold surface build remains a separate bottleneck.

**Exact crater, facing, and wind-varying tree kernels.** The complete standard
crater loop now runs as one JavaScript service while retaining its signed
radius quirk, unsigned clipping, radial stamps, x87 narrowing schedule, map
writes, registers, RNG, and FPU exit state. Four direct-versus-source cases had
zero differences across the entire machine memory. In the same lunar product
fixture, time through surface construction and the following sample fell from
111.6 to 84.7 seconds; steady rendering was intentionally unchanged.

Mapped facing no longer allocates temporary edge, cross-product, and normal
arrays for every polygon. Its scalar schedule produces the same whole-memory
hash as the previous kernel. A tree-heavy turning product sample moved from
about 29.0 to 31.5 measured FPS, although the changing final camera makes that
measurement directional rather than a controlled frame-for-frame comparison.

The remaining tree-cache invalidation was structural: the key included the
incoming fast-RNG seed even though `VHGND tree` immediately overwrites it from
the tree's world coordinates. Wind also changed leaf-tip coordinates without
changing branch topology. LinoJava now caches the topology independently,
recomputes every wind-dependent binary32 leaf tip and greenmush seed, preserves
the source-visible random mask and final scratch coordinates, and projects the
updated shared vertices. A normal steady frame and a forced between-frame wind
change both matched the source path with zero differences across the complete
machine memory. Instrumented tree traversal fell from about 430 to 88 ms in
the steady comparison and from 490 to 149 ms after the forced wind change. The
actual worker product reached the same habitable turning scene in 69.2 seconds,
continued without errors, and reported 31.4 rendered FPS with only 1.9 ms of
render work plus 0.5 ms of display work. This removes interpreter pressure and
cold-frame stutter, but it also makes the next open issue explicit: the
remaining roughly 30-Hz gameplay cadence is not renderer saturation and must
be reconciled with the 60-FPS desktop/parity requirement without changing the
original simulation rate.

The direct foliage pass also exposed a critical address-space bug. Its
translated native fragment treated the workspace-relative `RADPT` symbol as
an absolute unit address instead of adding Noctis's workspace base. Every
mushroom stamp therefore wrote into unrelated live machine state rather than
the display page. This explains the observed vertical dotted columns and could
destabilize later text, GUI, or menu execution. The fixed path resolves
`RADPT` through the Noctis buffer base; a focused regression checks the six
pixel writes and proves the old workspace locations remain untouched. The
corrected full habitable product smoke completed without a worker error at
24.8 measured FPS and showed dense ground foliage without the vertical
columns. This removes one source of broad browser corruption, but the GAME
menu report remains open until it is retested through the real public input
route after this build is deployed.

That result did not initially close the older horizon-column family. A later
continuous-turn type-3 habitable capture showed long dotted vertical structures
extending below a slanted visible terrain strip with both the ordinary facing
routine and a discarded cached-facing experiment. The cause was a separate
JavaScript-only whole-tile screen rejection inside the direct terrain kernel.
When that speculative test rejected a foreground ground tile, the traversal
still rendered the tile's tall trees and fauna, exposing distant foliage through
ground that should have occluded it. Removing the rejection restores the source
far-to-near terrain workload. A fixed checkpoint at the original failing
heading of -163 degrees then rendered continuous foreground coverage with no
dotted vertical structures, no worker error, and 17.0 measured FPS. The dark
ground is populated framebuffer output rather than unwritten memory. Its exact
palette remains subject to NIV+ visual grading, and this fix does not close the
separate horizon-pillar reports in other planet scenes.

The first published browser build showed cupola geometry without the
Stardrifter exterior because the host shipped only the font file. Named reads
for `globes.map`, `offsets.map`, `vehicle.ncc`, `mammal.ncc`, and `birdy.ncc`
failed, leaving the VEHICLE dispatch table empty. Linoctissite now packages all
six currently requested runtime files. The same strict machine path builds
720 of 720 hull cache leaves with `VHRbad=0`, and a fresh Chromium product
capture contains the hull between the cupola passes with no page or console
errors. That smoke measured about 7.4 display presentations per second. This
is a useful improvement and fixes the missing hull, but it is not yet smooth
gameplay and it is not a claim of 7.4 simulation frames per second. Continue
collapsing measured Lino hot loops into exact pure-JavaScript kernels while
preserving the original gameplay cadence.

**JavaScript translation-state audit and mapped-camera corruption fix.** A
framebuffer-only comparison was not strong enough for the direct JavaScript
services. Several routines produced the expected immediate pixels while
leaving different Lino-visible cursors, helper words, or workspace values.
The live audit now compares the complete machine memory where practical and
found concrete state defects in rectangle fill, standard text, TGA loading,
the cupola cache, the white-body raster, and the Stardrifter hull cache. The
hull's whole-frame pixel replay was removed because it skipped every public
polygon and raster transition; the retained shared-geometry path is still
about twice as fast as interpreted source in the focused steady run and ends
with identical complete memory.

The most serious defect was in the mapped UV-step translation. Its wide
temporaries were written to literal float-workspace offsets 24 through 27,
but the source scratch slots are numbered 248 through 251. The wrong writes
overwrote the projection distance and near-plane values. One correctly drawn
HUD glyph could therefore corrupt the camera used by the following glyph,
mapped hull panel, or terrain polygon. A two-glyph reproduction had 54 wrong
pixels and omitted the second glyph. Addressing the named scratch slots makes
both glyph pages exact and makes the complete presented Stardrifter frame hash
match the interpreted Lino path. A focused regression now asserts that one UV
step updates slots 248 through 251 without changing slots 24 through 27.

The Cloudflare build published from LinoJava `11148f5` and Linoctissite
`53a58db` held 60.0 rendered FPS and 60.0 Hz display in the post-deployment
Stardrifter smoke, with 5.6 ms render and 0.8 ms display work. Fresh rocky and
frozen landed smokes retained visible terrain and text without runtime errors;
their reported rendered rates were about 48 to 50 FPS, so the cross-scene
60-FPS acceptance item remains open. This evidence establishes direct
JavaScript parity with the current Lino routines for the exercised paths. It
does not replace the separate NIV+ native-renderer oracle required for visual
authenticity.

**Exact landed-runtime optimization checkpoint, 2026-08-16.** The browser now
uses conservative wind-adjusted bounds for cached trees, direct cached
addresses in the repeated greenmush RNG/pixel path, allocation-free exact
BigInt bit-length calculation in the x87 model, and direct typed float-bit
views. In the fixed habitable worker fixture these changes raised the measured
rate from about 14.2 to 21.7 FPS and cut tree replay from roughly 54 ms to 27 ms
per terrain render. LinoJava's 42 checks, the site check, and a deployed GAME
menu smoke passed. This is a substantial cross-planet checkpoint, not closure:
the hard 60-FPS landed acceptance item remains open.

**Second exact landed-runtime checkpoint, 2026-08-16.** LinoJava `92d5897`
removes repeated symbol, typed-view, and scalar scratch lookups from the
floating tree-particle projector and uses one cached unaligned qword view
through the exact one-point rotation path. It retains the original binary32
spill points, workspace side effects, fast-RNG order, framebuffer writes, and
x87 control changes. The same fixed habitable browser session rendered 375
measured frames at 31.2 FPS, up from the preceding 21.7-FPS checkpoint, with a
complete nonzero page, loaded font data, and no runtime error. This version is
published through Linoctissite `6d24a2f`. It is another material step, but the
60-FPS landed target and cross-planet acceptance remain open.

The following exact particle-stamp batch in LinoJava `a6cf8e1` retains every
fast-RNG transition and framebuffer write but publishes the final Lino RNG
workspace and registers once per inner stamp loop instead of after each of its
three immediately consumed draws. The same browser fixture reached 36.1
measured FPS over 434 frames without a runtime error. Linoctissite `065bdab` is
the corresponding public build. A broader outer-loop batch was measured,
failed to improve the result, and was removed before publication.

LinoJava `46257da` then replaces eight projected AABB corners per cached terrain
model with a widened circumscribed-sphere test against the four camera frustum
planes. The projection context and plane norms are built once per terrain
traversal. The widened sphere is conservative, so uncertain models still enter
the unchanged renderer. In a deterministic 28-frame comparison, steady frame
time fell from 34.29 to 30.38 ms while the complete machine-memory, raster,
display, and tree-command hashes remained identical. The browser run completed
435 measured frames at 36.2 FPS with a final live rate of 38.8 FPS and no error.
Linoctissite `586bd9d` publishes this checkpoint. The hard 60-FPS target remains
open.

**Allocation-free JavaScript runner boundary.** LinoJava `e4ab148` reuses each
machine's typed memory view and sends region exits through one common epilogue,
removing the fresh DataView and two closure allocations formerly paid by every
nested Lino call. This benefits fauna, terrain detail, GUI, Stardrifter, and
arbitrary Lino projects rather than one renderer service. The compact emitter
keeps static runners at 7.4 MiB instead of the first experimental 9.8 MiB.
Across the deterministic habitable run it reduced steady frame time from 30.38
to 28.33 ms with identical complete machine state, raster, and display hashes.
All 42 LinoJava checks passed. Linoctissite `0cad531` is deployed, and a fresh
public canvas click on GAME continued rendering with no page error or failure
packet. This does not close the player-reported GAME failure or the 60-FPS
target.

**Exact moving-fauna dispatch checkpoint, 2026-08-17.** LinoJava `b964d85`
builds the source merge order for mammals and birds once per terrain traversal
and dispatches only the records currently occupying each painted tile. When a
rendered creature moves, its bucket is updated immediately, preserving the
source behavior where that creature can enter a later tile during the same
frame. The replacement also reproduces the loop's counters, selected record,
registers, status, and final scratch state. A matched 12-frame habitable-world
A/B ended with zero differing units across the complete 73,702,444-byte machine
image, including identical raster, display, and presented hashes. Steady frame
time in that run fell from 45.11 to 30.30 ms. Linoctissite `b7fd3bc` publishes
the change. The hard 60-FPS and cross-planet acceptance items remain open.

**Exact cached-particle visibility checkpoint, 2026-08-17.** LinoJava
`89a2021` applies the existing conservative terrain frustum test to each cached
greenmush particle cloud after a tree's whole-model test succeeds. Static cloud
bounds retain the source scale radius and ten-pixel stamp margin. Wind-driven
leaf clouds translate those same widened bounds by the exact current binary32
wind displacement. Only a cloud whose complete possible footprint misses the
viewport is skipped; every potentially visible command retains its original
RNG, projection, and pixel path. A matched habitable run ended with identical
registers and zero differing units across the complete 73,702,444-byte VM
image, including identical raster and display hashes, while measured frame time
fell from 22.16 to 21.22 ms. Linoctissite `53664fd` publishes the change. The
hard 60-FPS landed target remains open.

**Exact terrain pixel-loop checkpoint, 2026-08-17.** LinoJava `9a30977`
removes redundant 16-bit page-address wrapping from the ordinary terrain-only
texture loop. Terrain raster rows are already clipped to x 5 through 311 and y
10 through 190, so their largest destination remains below the 65,536-unit
page boundary. Required 16-bit U and V wrapping is unchanged, as are texture
indices, tint arithmetic, culling duplication, pixel order, and final scratch
state. The same deterministic habitable run remained identical to the prior
complete 73,702,444-byte VM image, raster, display, and registers. Measured
frame time fell from 21.22 to 18.60 ms. Linoctissite `a28e930` publishes the
change. Browser-wide 60-FPS acceptance remains open.

**Exact shared HPOINT checkpoint, 2026-08-17.** Noctis Lino `a4ff43c`
exposes the existing terrain-height sampler as a service at every production
caller, and LinoJava `e41e75c` executes its complete clamped byte lookup,
triangle interpolation, binary32 spill, chopped conversion, and scratch-state
publication directly. Birds, mammals, rocks, the capsule, collision, and
landed setup all use this shared boundary. The desktop Lino game compiles with
the service unchanged. A matched browser-runtime run ended with identical
registers and zero differences across the complete VM image, raster, and
display, while measured frame time fell from 20.98 to 19.00 ms. Linoctissite
`1a1b2ea` publishes the change. The hard 60-FPS and cross-planet acceptance
items remain open.

**Exact foliage projection checkpoint, 2026-08-17.** LinoJava `0733268`
fuses each greenmush particle's one-point rotation and projection while
retaining the original binary32 narrowing points, qword scratch values, final
offset state, and pixel order. The matched habitable run ended with the same
SHA-256 hash across all 73,702,444 bytes of VM state. Steady frame time fell
from 19.00 to 18.57 ms. Linoctissite `8dc7bfc` publishes the change.

**Exact terrain scanline checkpoint, 2026-08-17.** LinoJava `2279fcb` fuses
the ordinary terrain UV update and mapped pixel blocks into one bounded
JavaScript scanline kernel. It preserves the x87 spill schedule, current
control word, 16-bit texture-coordinate wrapping, culling duplication, and all
published scratch state. The same complete 73,702,444-byte VM image remained
identical, while the matched landed-frame benchmark fell from 18.57 to 17.48
ms. Linoctissite `03e5de5` is deployed at `linoctis.pages.dev`. A fresh Chrome
habitable run measured 38.9 FPS, so the hard 60-FPS and cross-planet target
remain open.

**Flagged mapped-vector checkpoint, 2026-08-17.** Cached tree leaves set
`SPtrifast` for their three-vertex mapped fans, while limb faces set
`SPmapfast` for four-vertex mapped quads. Both still repeated the generic
midpoint, transform, edge-vector, and nine-gradient helper pipeline on every
visible cached command. LinoJava `1d49bef` now routes those explicit fast flags
through the existing fused vector schedule and selects the original one-third
or one-quarter centroid constant from the vertex count. Unflagged polygons,
near-plane projection fallback, texture and flare modes, and raster order are
unchanged. The focused intrinsic checks pass; a real habitable browser run
finished with a complete nonzero framebuffer, no runtime errors, and about
30 gameplay FPS. A Stardrifter save/load and twelve-frame replay retained its
mauve palette, accumulated no smear, and finished near 59 FPS; GAME-to-GOES
still displayed complete text at 60 FPS without a crash. Linoctissite
`4e48014` publishes the change. The landed hard-60 target remains open.

**Stale public deployment repaired, 2026-08-17.** The repeated discrepancy
between passing local smokes and the player's public-page failures had a real
deployment cause. Linoctissite's workflow rebuilt every push from pinned
LinoJava and Noctis revisions, but those pins were far behind the checked-in
generated runtime. The successful GitHub job could therefore validate one
artifact while Cloudflare continued serving another. The pins now identify
LinoJava `1d49bef` and Noctis Lino `5db0c0b`, and CI fails if rebuilding those
pins changes the checked-in runners or runtime files. The exact image was then
published through the authenticated Cloudflare path. Its public runtime ID is
`1b491e3209ccfa9774d39d62`; a fresh public canvas interaction opened GAME,
entered GOES, displayed the complete console text, sustained 59.4 gameplay FPS
at 60 Hz, and produced no crash or browser error. This resolves the stale-build
mechanism, not the broader iGUI audit or the hard-60 landed target.

**Browser Stardrifter accumulation and iGUI menu crash.** The JavaScript build
had a multi-frame failure that the single-call service comparisons did not
cover. The Stardrifter's white smear/corona effects spread across the viewport,
retained hundreds of black holes like the defective sun core, and progressively
reduced the rendered frame rate. A reproduced long run reached only about 26
rendered FPS with 32.6 ms of render work and showed most of the viewport covered
by stale white geometry. The initial wall-clock catch-up fade hid the symptom
but was not source-exact and punched holes into slow-host effects. It has been
removed. The real accumulation cause was checkpoint state: completed stellar
approaches restored `MgApreached=1` while leaving `MgStspeed=1`, so the moving
fade path kept consuming the stationary hull. Version 17 persists the exact
drive flag and versions 1 through 16 reconstruct a completed approach as
stationary. The remaining black core came from the separately corrected
`VHT smooth grays` back-edge. A steady deployed run now keeps one source fade
per rendered frame, shows a bounded filled corona, matches every pinned native
stage hash, and has substantial 60 Hz render headroom.

Opening the JavaScript build's GAME menu was reported to crash the game. The
first complete reproduction found three interacting causes: browser input could
starve behind a long Lino execution slice, stale queued button state could
replay a press after release, and the menu's real `FX Shadow` operation was
missing from the JavaScript host. The unsupported effect stopped the worker and
left its last frame visible, which looked like a game crash. The production
browser now uses responsive execution slices and current pointer state, and its
pure-JavaScript host implements the exact packed-channel shadow operation and
raw tiled-region path. The Lino game also pauses frame publication while an
iGUI menu or file selector owns the backdrop. A deployed interaction smoke
opened the real 12-row Lino GAME menu, held it for one second, dismissed it,
and continued rendering without an error.

**Reopened by a fresh player report on 2026-08-16.** Activating GAME in the
published JavaScript build still crashes or halts the game in at least one real
interaction sequence. The earlier automated open-hold-dismiss smoke therefore
covered only its exact synthetic pointer path and must not be treated as menu
closure. Reproduce the player's ordinary click from a fresh public load, retain
the worker exception and last committed machine state, and fix the first
source-level or host-contract divergence. Then exercise every GAME command,
keyboard and pointer dismissal, repeated opening, and return to live play. A
menu is accepted only when an ordinary player can use it without stopping,
corrupting, or silently freezing the Lino machine.

**Direct report repeated after the deployed retest.** The user again reports
that merely pressing GAME crashes the published game and describes the current
JavaScript GUI implementation as broadly unreliable. Treat that observation as
authoritative over the synthetic non-reproduction below. Do not close this item
from scripted pointer injection alone: reproduce it through the public page's
real DOM/canvas event route, including its exact viewport scale, pointer
capture, focus, worker scheduling, and menu-layer transition. Preserve a crash
packet in the page when the worker stops so the next real occurrence exposes
the exception, active code handle, menu state, and recent input events instead
of leaving only a frozen last frame.

**Current deployed retest.** After the input, shadow, scheduler, and checkpoint
fixes were published, a fresh production load accepted an ordinary held pointer
click on GAME. A single session then selected all eleven non-quit rows with the
same player-like press duration. Every option closed the menu, returned to the
idle game loop, kept the worker running, and produced no page or worker error.
GAME to GOES also displayed its complete cyan and green console text. Keep the
manual report open: the latest direct player report still says that pressing
GAME crashes the game, so the automated sweep is only a non-reproduction on one
input path and browser state, not closure. Capture the real click sequence,
cache/build identity, worker exception, and last committed machine state from a
player-equivalent run. Test Save and quit separately as an intentional orderly
halt rather than treating its stopped worker as a crash.

The browser now retains an actionable failure packet instead of only freezing
the last frame. An unexpected worker or foreground-runtime exception exposes a
copyable report in the page and stores it in session storage. The packet
contains the JavaScript stack, current Lino instruction and source location,
all matching labels, A-E/X, stack depth and top entries, rendered-frame count,
and the worker's last 32 key, pointer, physical-display, or display-position
events. A synthetic run failure verified both the visible and persisted packet
at the real `VHG run` call site. Intentional source `end` remains a normal stop
and does not masquerade as a crash.

After correcting the foliage framebuffer base and deploying LinoJava
`ac9bec9`, another fresh public-page run used the actual DOM/canvas pointer
route, opened GAME, selected the first command, and continued at about 58 FPS
with no page or worker error. This is consistent with the foliage overwrite
having poisoned GUI state in some sessions, but it is still a non-reproduction
on one browser path. Keep the issue open until the reporter confirms the
corrected public build and the crash packet catches any remaining failure.

**Fresh direct report after that retest:** pressing GAME still crashes the game
for the player, and the JavaScript GUI remains broadly unreliable. This report
supersedes any implication that the synthetic menu sweep closed the defect.
Treat the crash panel as diagnostic infrastructure, not as the fix. Reproduce
and repair the actual player path, then require a manual GAME-menu confirmation
before release closure. Audit missing console and overlay text in the same live
session because corrupted machine state, menu layers, font pointers, or host
event ordering may connect those symptoms.

**Newest public-build regression bundle.** Treat the following as active,
possibly connected release blockers even where an older focused smoke reported
success:

- GAME can crash or halt the running game from an ordinary player click. The
  complete browser iGUI contract remains suspect, including layer ownership,
  pointer routing, focus, menu dispatch, and unsupported desktop window actions.
- All game and console text can disappear, not only one damaged glyph route.
  Audit font loading, address relocation, text services, clipping, palette use,
  and state left behind by translated drawing routines.
- The Stardrifter exterior can acquire long stray lines. Its white smear can
  grow across the screen without clearing, contain hundreds of black dots, and
  become progressively more expensive until frame rate collapses.
- The opening sun can lose its lens flares and show a black-square dither or
  punched-out core. This is not authenticated original behavior. Compare the
  indexed page and intermediate sun stages against a matched NIV+ oracle.
- Saving and loading a checkpoint can change the Stardrifter from mauve to blue.
  A snapshot must restore the authoritative palette and visual state, not act as
  an accidental palette initializer or repair step.

Audit every JavaScript routine translation exercised by these paths for both
immediate pixels and complete Lino-visible exit state. In particular, compare
scratch words, cursors, stack, framebuffer ownership, palette, clip state, and
all persistence fields before accepting a visually plausible single frame.
Reproduce the multi-frame smear and menu failure in the actual public product;
one-call service tests and synthetic pointer injection are insufficient.

**Stardrifter composition repair, 2026-08-17.** Two source omissions and one
angle mix-up are now corrected. The port again runs NIV+'s two `psmooth_64`
passes after the interior and halogen are composed, uses the unshifted player
view for the interior, and reserves `navigation_beta + 180` for the external
`from_vehicle` camera instead of reversing the physical hull-lighting term.
The native and pure-JavaScript products render the same corrected frame, and a
focused browser run sustained about 50 rendered FPS. The frame is still too
mauve and still contains unauthenticated radial flare geometry, so sun, flare,
palette restoration, and multi-frame visual fidelity remain release blockers.

**Stardrifter false halogen flare repaired, 2026-08-17.** The radial lines in
the opening window were not an authentic renderer quirk. The port incorrectly
carried the two temporary `cam_z += 54*15` screen offsets into `alogena`, even
though NIV+ cancels both before applying the lamp's own `cam_z += 200`. That
placed the fixture camera 1,620 units too far aft and projected its complete
visor flare into the window. The port now uses the source-effective camera
`player_z + 200`. The matched NIV+ lens-enabled capture and the corrected
browser frame both contain no fixture rays at the opening pose; the browser
continued at about 49 rendered FPS. Keep the wider sun, exterior smear,
checkpoint-palette, and multi-frame clearing audit open.

**Checkpoint ship-palette repair, 2026-08-17.** Save/load did not lose the
selected star or require new persisted colour fields. `VHG palette` rebuilt
band 0 with its cobalt bootstrap ramp, but retained `VHGshipoldr/g/b`. The next
geometry-derived ship update could compute those same cached values and skip
the upload, leaving the bootstrap band visible after load. Every base-palette
rebuild now invalidates that upload cache. A browser save/load reproduction
retained the same Stardrifter hull/chrome colours before and after restore,
while gameplay and rendering continued. The complete checkpoint-state and
cross-scene palette audit remains open; this closes the reported stale band-0
mechanism rather than claiming all palette progression is authenticated.

**Latest manual confirmation.** Pressing the GAME title-bar menu itself still
crashes or halts the public JavaScript game for the player. More generally, the
browser iGUI is not yet trustworthy enough for ordinary use: controls can map
desktop-only window behavior into incoherent browser actions, and a scripted
menu success does not establish that the real player path is safe. Keep GAME
and the complete iGUI interaction audit open until the public build survives
manual menu use, every non-quit command, dismissal, repeated opening, and
return to live rendering without corrupting machine, layer, input, or font
state.

**Returning-browser persistence hardening deployed on 2026-08-16.** Clean
automation and the player's long-lived browser were not starting from the same
machine state. The host loaded all iGUI GlobalK blocks across deployments even
though those 255-unit records can contain addresses and handles belonging to a
different linked build. It also allowed persisted virtual files to override the
packaged font and model assets. The public runtime now fingerprints each linked
runner, loads GlobalK only for that exact fingerprint, and makes manifest assets
authoritative and read-only while keeping versioned `CURRENT.LIN` checkpoints
portable. A focused returning-browser smoke deliberately stored a zeroed
`DIGIMAP2.BIN` and invalid legacy GlobalK data; the reloaded product retained
visible text, live rendering at 72 FPS, and no crash. A second real DOM/canvas
GAME interaction selected a command and returned to play at 95 rendered FPS
without a page or worker error. This removes a concrete clean-versus-returning
session divergence. It does not close the direct reports or authenticate the
Stardrifter lines, sun, palette progression, or translated renderer against
NIV+.

**GAME-menu render flood fixed and deployed on 2026-08-16.** A real click on
the public GAME button exposed a host failure that looked like a crash without
throwing an exception: iGUI's unpaced RETRACE loop produced roughly 4,000
presentations per second, continuously recycled superseded buffers as new
render credits, and saturated the worker/main-thread message path. Dropped
frames now return only their storage; only a frame actually presented by the
browser grants another render credit. The worker stops when those credits are
exhausted and resumes on the next browser presentation. The same public click
now leaves the real Lino menu visible, reports about 50-60 rendered FPS on a
60-Hz display, and produces no crash packet or console error. This closes the
identified render-flood cause, but the broader menu item, repeated interaction,
and browser iGUI contract audit remains open pending player confirmation.

**Player verdict after the current public performance build: still a release
blocker.** The faster build reaches a useful frame rate, but its translated
rendering and GUI paths are not yet trustworthy. The reported failures are:

- clicking GAME can still crash or halt the game in the player's ordinary
  browser session, despite the isolated render-flood fix;
- the Stardrifter exterior grows persistent white smear bands and stray lines
  instead of clearing them, with dense black holes/dots inside the effect;
- that accumulated smear becomes dramatically slower as it spreads;
- game, HUD, and console text can all be absent;
- the opening sun has no convincing lens flare and shows a black-square/dithered
  centre that has not been authenticated against NIV+;
- checkpoint save/load changes the Stardrifter palette from mauve to blue,
  proving that live and restored visual state currently diverge.

Treat these as one audit of the JavaScript translations and machine-state
contract, not six cosmetic patches. Validate every optimized/direct routine
against the ordinary Lino implementation for framebuffer output and all
caller-visible state, then grade sun and effect behavior against a matched NIV+
oracle. The acceptance run must exercise several consecutive Stardrifter
frames, open and use GAME, enter GOES, show its text, save and reload, and return
to stable live rendering without new pixels accumulating or frame time growing.

Keep the broader iGUI audit on the docket as a release blocker. Exercise every menu command and
title-bar control, including menu construction, dormant-window registration,
layer ownership, focus, dismissal, command dispatch, resize, fold, hide,
screen-off, fullscreen entry and exit, and return to the game runner. Browser
actions that have no honest operating-system-window equivalent need an explicit
safe behavior instead of inherited desktop assumptions. Every action must
either work or explain that it is unavailable; none may corrupt or halt the
Lino machine. Preserve an easy game-only fullscreen exit that does not consume
Noctis's Escape key, and audit the same behavior on the desktop host. This is a
functional rework of the JavaScript iGUI contract, not a cosmetic pass: button
hit testing, pressed-state feedback, focus ownership, command routing, and
unsupported window-manager actions all need coherent browser-native outcomes
while the visible chrome continues to be rendered by the real Lino GUI.

The first full title-bar control sweep found one concrete browser-host defect.
Fold/unfold, sleep/wake, cropped game-only fullscreen, and the explicit
fullscreen exit all completed through the real Lino buttons, but maximize kept
the old window origin and enlarged the DOM window beyond the right and top
edges of the viewport. Normal browser windows are now clamped to the visible
viewport after Lino changes their logical size, and the corrected coordinates
are written back to the Lino display workspace. Dormant 126x25 windows retain
their source grid placement. The focused sweep now maximizes to an entirely
visible window at the viewport edge and exits fullscreen cleanly with no page
or worker error. Dragging, free resize, repeated state transitions, and every
remaining command still belong to the open audit.

**Fresh player report, 2026-08-16:** clicking the published JavaScript build's
GAME title-bar control still crashes or halts the game, and the browser GUI as a
whole remains visibly unreliable. Keep this as a current release blocker even
though isolated scripted paths have passed. The next repair must start from the
ordinary public-page click path and retain the exact input-event sequence,
active Lino location, layer/focus state, and worker failure or starvation state.
Acceptance requires manual use of GAME plus every non-quit command, repeated
open/dismiss cycles, and continued live rendering. The same pass must give every
desktop-only title-bar action an explicit browser-safe meaning, including move,
resize, maximize, fold, hide/screen-off, and game-only fullscreen with an exit
that does not consume Noctis's Escape key.

One real host-contract hole from that report is now repaired. Both the worker
and foreground browser hosts publish an explicit Lino button-up transition when
Chromium cancels a pointer, drops capture, hides the page, or moves focus away.
They also abandon any pending title drag, resize, or fullscreen activation.
Previously those browser events cleared keys but could leave iGUI's left-button
hotspot latched indefinitely, trapping GAME or a title-bar control in its modal
pressed loop. A focused real-page run cancelled a press over GAME, observed
`Pointer Status=3`, then opened and dismissed GAME normally with continued
rendering and no crash or console error. Keep the broader player report open
until this deployed build is confirmed in the affected interactive session.

**Fresh player report, 2026-08-17:** clicking GAME still crashes or halts the
published JavaScript game. This supersedes the passing scripted menu smokes and
keeps the defect open as a release blocker. Treat it as part of the broader
browser iGUI reliability failure, not an isolated menu cosmetic: capture and
repair the ordinary real-pointer path, then manually confirm repeated GAME
open/use/dismiss cycles, every non-quit command, and continued rendering. The
same acceptance pass must cover layer and focus ownership plus safe browser
meanings for move, resize, maximize, fold, hide/screen-off, and fullscreen.
No unsupported desktop-window action may crash, freeze, or corrupt the Lino
machine.

**GAME title-control hardening, 2026-08-17:** the browser host now recognizes
the live Lino `Menu Button Hotspot` and schedules the original
`service Menu Button Action` on the VM call stack. This avoids routing a
browser title control through the modal pointer-capture loop while retaining
the real Lino menu, layers, reset routine, and retrace. The call is asynchronous
because the service legitimately yields during its display retrace. Real DOM
clicks now open and dismiss GAME with continued rendering and no crash in the
worker, foreground, and legacy main-thread runtimes. Keep the broader iGUI
audit open until ordinary play has exercised every menu command and all
desktop-only title controls have explicit browser-safe behavior.

**Post-hardening player recurrence, 2026-08-17:** clicking GAME in ordinary
published play still crashes or halts the game. Reopen this as an observed
release blocker; the focused host smoke above is diagnostic evidence only and
does not close it. Capture the public-build pointer event, VM location and call
stack, worker error or starvation state, active layer, focus/capture state, and
the first failed menu command from a real click. Repair the underlying iGUI
contract, then manually exercise repeated GAME open/use/dismiss cycles and
every non-quit item while rendering continues. Keep the whole JavaScript GUI
implementation under audit: browser-inapplicable move, resize, maximize, fold,
hide/screen-off, and fullscreen actions need coherent safe behavior and none
may crash, freeze, or corrupt the Lino machine.

The latest player verdict is that the JavaScript iGUI remains sketchy as a
whole, not merely that GAME has one bad command. Do not treat the current GUI
as release-ready and do not close this from synthetic pointer injection. The
public build must survive ordinary manual clicks through the real canvas/DOM
route, retain correct focus and layer ownership, and return from every safe
menu or title-control action to a visibly live game. GAME itself is a hard
release blocker until that exact player route stops crashing.

**Command-specific player recurrence, 2026-08-17:** selecting Visual Effects
through the real JavaScript GAME menu is broken and crashes, and selecting the
GOES console through that menu is also broken and crashes. Do not generalize a
successful GAME-open or direct-key GOES smoke to either route. Capture the
ordinary click sequence, selected command, VM continuation and stack, active
layer, worker failure/starvation state, and first bad frame for each command.
Acceptance requires repeated menu entry into Visual Effects and GOES, visible
and usable resulting screens, dismissal back to live gameplay, and no crash,
halt, lost text, palette change, or renderer-state corruption.

**GAME crash root cause and repair, 2026-08-17:** the browser shortcut entered
`Menu Button Action` by pushing the current continuation and changing `pc`
immediately, even when the worker was yielded in the middle of the renderer.
One captured ordinary click changed a live render state at `pc=26049`, stack
depth 10, into the menu service at depth 11. That spliced a GUI call into the
wrong call stack and explains why identical-looking clicks could either work at
iGUI idle or corrupt the game. Both JavaScript runtimes now leave the request
pending until the real `eclj25` GUI-idle yield and enter the original service
from that stable continuation. The worker also keeps the oldest unconsumed
browser pointer edge in Lino's workspace; a fast press/release pair can no
longer erase its press before `Check Hot Spot` samples it. A zero-duration DOM
click opened GAME, selected Controls, displayed the original Controls screen,
continued near 58 rendered FPS, and produced no crash packet or browser error.
Publish this repair, then retain the wider command/title-control audit and
player confirmation requirement rather than generalizing one accepted path.

**Complete pointer-scan and GOES text repair, 2026-08-17:** retaining edge
order was not sufficient because one JavaScript VM slice can execute multiple
`READ POINTER` calls before iGUI reaches `Check Hot Spot`. A fast click could
therefore consume both queued edges inside one slice and become hover-only.
Each edge is now the stable live sample until the full iGUI control loop
returns to `eclj25`; only then is the next edge exposed. Instantaneous DOM
clicks now open GAME and activate GOES in both worker and foreground runtimes.
The resulting screen contains the green title/prompt, cyan revision and output
rows, and live input cursor, with continued rendering and no browser error or
crash packet. This supplies current evidence against the old all-text-missing
browser state. Keep the wider glyph-fidelity and XQuartz audit open because a
healthy browser asset/runtime does not prove every compatibility host.

**Complete-frame browser pacing, 2026-08-17:** iGUI performs a changed-area
retrace and then a pointer/composition retrace during one Noctis gameplay
frame. The worker previously spent one browser presentation credit on each,
which made a renderer capable of 60 gameplay frames appear capped near 30.
Linoctissite `ec67846` now recognizes the first retrace from the authoritative
`VHGtimingcalls` counter, keeps that intermediate page in the worker, and
publishes the following fully composed page. A real GAME-to-GOES smoke rendered
the complete console text, reported 59.0 gameplay FPS on a 60 Hz display, and
produced no crash or browser error. Habitable landed terrain remains around
26 to 27 gameplay FPS in the current matched benchmark, so the hard-60 task is
still open and now cleanly isolated from the former double-pacing defect.

## 9. Font fidelity across every text path -- **OPEN / DOCKET**

Audit and authenticate every game and host font against NIV+ across Windows,
the browser runtime, and compatibility hosts such as Wine and XQuartz on
macOS. Cover the lower-left notices, lower-right status text, GOES
console input and output, HUD and FCS labels, onboard devices, data sheets,
menus, help, About, counters, coordinates, and iGUI chrome. Grade the complete
glyph set, character mapping, spacing, baseline, row stride, clipping, colour,
palette interaction, nearest-neighbour scaling, and resize/fullscreen behavior.

The desktop game also needs a fresh matched-oracle pass for both physical
Stardrifter text routes: GOES console output and the text rendered onto the
interior wall/panels. Compare the production desktop build, the JavaScript
runtime, and the same NIV+/vanilla state. Grade glyph identity, character
mapping, projected placement, clipping, colour, persistence, and the transition
into and out of GOES. Treat the JavaScript failures as potentially different
until the raw font data, pointers, and framebuffer evidence identify a shared
cause.

Visible but unselectable text boxes or input fields in the game/iGUI window are
also an open parity question. Establish from a matched original Noctis/iGUI
oracle which boxes are meant to be editable, focusable, read-only, decorative,
or hidden in each state. Then make focus, hit testing, caret, keyboard input,
selection feedback, and disabled appearance match the original on desktop and
in the browser; do not preserve inert host artifacts merely because they are
visible in the current port.

The motivating external report is asymmetric: lower-left text such as the
checkpoint-restored notice remained legible, while lower-right text was
corrupted into shapes that did not resemble letters, and GOES console text was
corrupted in the same way. The supplied XQuartz screenshot confirms that the
macOS-native window chrome remains legible while the top in-game status run is
compressed or overlapping and the lower-right glyph run is severely malformed.
Preserve that distinction as a diagnostic case. It suggests a shared font
pointer, glyph workspace, row-pitch, character-index, unit-width, or
memory-clobber path used by lower-right and GOES rendering rather than a global
Mac font failure. Reproduce it under XQuartz with the reporter's exact runtime
and launch command, then test the ordinary Windows build and browser host with
the same strings and window geometries.

A second external capture shows another projected-pilot-font failure while the
ordinary overlay font remains clean in the same frame. `UNCHARTED STAR` and
`UNCHARTED BODY` are recognizable but have missing, shifted, or joined strokes;
the nearby `CALIBRATED` overlay is intact. Treat this separately from a corrupt
or byte-swapped atlas: authenticate those exact strings against a matched NIV+
screen, then grade the `VHP digit -> FB digit at -> polymap` raster, row
selection, spacing, quad projection, and clipping at the captured geometry.
The atlas hash alone cannot close a rendering-path defect after a valid atlas
has loaded.

**Projected pilot-font repair, 2026-08-18.** The source audit found two exact
translation omissions in that path. NIV+'s `digit_at()` temporarily sets
`XSIZE=512` and `YSIZE=576` for every physical glyph, whereas the port inherited
whatever texture dimensions the preceding mapper left behind. NIV+'s three
information rows also use `p*46+12` in the port's equivalent world coordinates,
not the generic control-row `p*50`. The physical onboard renderer now pins the
512-by-576 basis and uses the source information spacing. A hidden production
FCS capture changed the giant shredded glyphs into compact coherent letters;
a controlled NIV+ camera sweep confirms the source's projected font is compact
and perspective-distorted rather than the prior port artifact. The focused
desktop regression passes. Keep the wider glyph-set, GOES, clipping, and
XQuartz reporter checks open; this closes the identified onboard projection
translation defect, not every compatibility-host font report.

The first static split is concrete. The working checkpoint notice is drawn by
`VHG notice overlay` through the ordinary `STD Write` font onto `VHGUIframe`.
The broken lower-right FCS status and both GOES wall displays instead converge
on `VHP digit`, which calls `FB digit at`, reads the 2,340-unit `digimap2`
glyph map loaded from the 9,360-byte `digimap2.bin`, and maps the result as a
3-D textured quad. Start the XQuartz reproduction at that shared file-load,
32-bit-unit, glyph-row, and texture handoff. Keep the standard-font notice in
the same frame as a positive control. The reporter is also bringing up a
headless content dumper for comparison-sheet output, which may provide stable
raw captures from the affected host rather than screenshot-only evidence.

**Browser named-file corruption fixed.** The JavaScript IsoKernel formerly
ignored nonzero `File Name` pointers and served every `READ` from the combined
iGUI stockfile. `VH panels init` therefore copied the first 9,360 bytes of skin
graphics into `digimap2`, producing the reported random-looking FCS and GOES
glyphs. LinoJava now distinguishes `STOCK FILE` from named virtual files,
decodes the Lino filename, reports missing files as errors, and reads the
selected byte stream with the requested position and length. Linoctissite now
ships `digimap2.bin` as a named runtime file. A strict five-frame machine run
loaded all 2,340 little-endian glyph units with zero differences from the
checked-in file; a 37-frame Chromium product smoke showed recognizable
`STANDBY` glyphs with no page or console errors; and a production desktop
capture rendered the same `STANDBY` source text. This closes the browser file
selection bug only. XQuartz reproduction, complete glyph grading, projection
and clipping parity, and matched NIV+ oracle evidence remain open.

A later production GAME to GOES run rendered the complete `GOES COMMAND
CONSOLE`, version, output, channel, and prompt strings and remained active at a
reported 56.7 rendered FPS with no page or worker errors. This strengthens the
browser product check but does not close the separate XQuartz path.

**Pilot-font word-order hardening, 2026-08-17.** The lower-right status and
physical GOES screens share the 2,340-word `digimap2` pilot font, while the
legible lower-left notice uses the unrelated iGUI standard font. Its loader
copied packed file words directly into glyph units and therefore assumed the
host exposed each four-byte word in little-endian order. The XQuartz screenshot
is consistent with the first lit `!` row changing from `0001C000h` to the
byte-reversed `00C00100h`. Startup now recognizes that exact alternate form,
byte-swaps all 2,340 scanlines once, and rejects any unrelated corrupt asset
instead of rendering it as text. The normal Windows product still renders the
complete `STANDBY` glyph and holds 60 FPS; a direct reverse-word check restored
all 2,340 rows exactly. This is a portability repair with a strong matching
failure signature, but the XQuartz item remains open until the reporter runs
the rebuilt executable on the affected host.

**Reopened browser text and checkpoint palette report.** A later player run of
the public JavaScript build showed no console text at all, and reported that
saving then loading a checkpoint changed the Stardrifter palette from mauve to
blue. Preserve the pre-save, post-save, and post-load indexed page, palette,
font pointers, named-file hashes, and checkpoint bytes from that persisted
session. The local GOES smoke is a non-reproduction, not closure. Loading must
restore the source-authoritative visual state without using checkpoint reload
as an accidental palette initializer.

Do not close this from plausible screenshots. Use matched NIV+ framebuffer or
glyph-atlas evidence for the source fonts, then require stable product captures
through each live text route. Include nonletters and boundary characters so a
partially shifted or incorrectly indexed font table cannot pass on a short
uppercase message.

The loader now checks that complete failure mode as well as its sentinel row.
After optional host-word normalization it computes FNV-1a over all 9,360
canonical atlas bytes and enables physical FCS/GOES text only for the checked-in
`494B1F1D` image. This prevents a partial or mixed-order file read from being
projected as plausible garbage. It is host hardening, not matched XQuartz or
NIV+ visual closure; the reporter still needs to exercise the rebuilt binary.

**Remaining source font rules restored, 2026-08-18.** A direct audit of
NIV+'s `vehicle()` and `screen()` found two visible rules that the port still
flattened. GOES uses a 6.5-unit glyph and colour 138 for `$`, `[`, `]`, `*`,
`&`, and `_`, while parentheses carry colour 191 until the closing parenthesis;
ordinary console glyphs remain 5.5 units and colour 152. The onboard computer
uses steady colour 127 for lowercase and punctuation, while source-uppercase
text blinks through `127 - 12 * (clock() % 6)`. The port now reproduces those
rules with its retained 18.206-Hz source clock. The production game rebuilt,
the focused gameplay regression passed, and a fresh physical-screen capture
remained coherent. Matched XQuartz reporter output and a complete glyph-set
comparison remain required before closing the wider compatibility item.

## 10. GitHub documentation and README -- **SETTLED / MONITORED**

The GitHub-facing documentation is split into readable sections, short
paragraphs, restrained bullet lists, and focused reference documents. The
README links the playable Windows and browser builds, gives the essential
controls before the deeper feature inventory, and no longer describes the
browser as an iGUI-only preview. The current browser paragraph identifies the
pure-JavaScript runtime, real Lino GUI, complete game route, and the remaining
dense-vegetation performance limit.

`README.md`, `HISTORY.md`, `PLAYTEST.md`, `PORTPLAN.md`, `RELEASE_NOTES.md`,
`TEST_COVERAGE.md`, `CI_RELEASES.md`, and `docs/NIVGEN.md` contain zero em dash
characters. Keep that invariant when editing them. Continue removing stale
claims and redundant history at release checkpoints instead of turning the
README back into one chronological wall of text.

The JavaScript/LinoJava version, its dense-scene speed limit, and its other
remaining defects follow the remaining native rendering, performance, font, and
final-audit work. They are the last active docket item. NIVGEN is excluded from
the active plan indefinitely; its retained evidence is archived separately in
`docs-notes/NIVGEN-HISTORICAL.md`.

## 11. Release, portability, and macOS gates -- **OPEN / CRITICAL**

These are near-term release gates, not background polish.

### 11.1 Finish the portable-Lino repair -- **IMPLEMENTED / HOSTED BOUNDARY PROVEN**

No Noctis game logic or optimization may embed raw x86 opcode blocks. The real
`vhgame.txt`/`vhnivgen.txt` closure is now 75 files, 89 imports, and zero raw
target blocks. Portable scalar arithmetic, exact square root, transcendentals,
and generation schedules are ordinary Lino integer code. The seven historical
x87 control/status blocks moved to test-only `work/fp/fpctlx87.txt`; production
`fpctl.txt` contains no machine escape. The closure gate additionally pins the
36 remaining ordinary Lino floating operations in three files and forbids
production `??` floating comparisons.

The positive fractional-crater helper keeps its result live through one final
binary32 store and preserves every soft-stack slot. The deep gate compares the
integer operation mirror with its historical-x87 oracle on all 9,564,210
reachable type-1/type-5 base/exponent pairs derived from the production factor
rules, including type 5's `random(5) * 0.015`, and from 586,183 pre-power
combinations and 490,424 distinct type/base pairs. Every mirrored pair agrees,
with pinned result digest
`b3c1aef60b2f697211e33d21b9f1d3be7f2cbcb0003fa5bc88810a46708ea937`.
The separate compiled-Lino driver is exact on 4,096 boundary and spread cases
and preserves all soft-stack sentinels.
Complete production default maps retain authoritative digests `FDDDF3A2` for
type 1 and `301D7754` for type 5. Corpus-wide NIVGEN effects are retained in
the deferred accuracy evidence rather than inferred from those two anchors.

Generated Windows PEs receive exact `133Fh` through a size-preserving,
fail-closed post-link patch; all eight licence-protected runtime variants retain
their upstream bytes and `PRISTINE.sha256` identity. Linux and macOS source load
`133Fh` before application entry and after C/runtime isocalls. Focused runtime,
closure, default K=64 historical-control (80 checks), 16-schedule, and 45-consumer
gates pass. The real x86_64 probe performs a `123Fh` perturb plus `133Fh`
load/readback/restore and passes locally. It also passed hosted Intel-macOS run
32556467204 and the tagged Apple-Silicon/Rosetta run 32555351033 with the current
NIVGEN/game consumers.

### 11.2 Keep releases usable -- **RESTORED / HOSTED GRAPH HARDENED**

Compiled releases have resumed. Tagged builds compile the selected source,
produce Windows and macOS packages, attach SHA-256 checksums, internal manifests,
and provenance, and independently verify uploaded assets. Release bodies now
contain only the selected release's own notes rather than the cumulative
history. Beta 23 was published from commit
`6c40d9e62cabe14978d148a457cb83dbbeeb98d8`; its six uploaded artifacts,
checksums, internal manifests, and provenance were independently verified.

The two release-pipeline hardening findings are repaired in source. The tagged
workflow no longer schedules or depends on the optional self-hosted
`[numerical, lino-gui]` job; hosted validation now feeds Windows and macOS
compilation directly, while the complete historical FP and consumer comparison
remains available in the separately dispatched interactive source workflow.
Rerunning an existing tag clobbers only the six generated assets and explicitly
preserves the existing release body, including later manual audit additions.
`test_release_notes.py` pins both properties. Tagged run 32555351033 proved the
changed graph end to end across validation, Windows and macOS compilation,
Rosetta exact generation, both packages, and prerelease publication. NIVGEN is
not an active release criterion; any historical parity claim must still state
that its 22 retained fields were unresolved when the work was archived.

The tagged graph now also invokes the reusable native ARM64 product gate and
waits for its tested package before publication. It retains and publishes
`Noctis-IV-macos-arm64.zip`, its SHA-256 sidecar, and its provenance record
alongside the Windows and x86_64 macOS assets. Tagged run 32595409634 proved the
real `tagged_release: true` metadata path, all native execution/package smokes,
and nine-asset prerelease publication at immutable commit `6cf9614`. Beta 24's
nine public assets were then independently downloaded and audited for GitHub and
sidecar digests, safe ZIP paths, complete internal manifests, PE/Mach-O
architectures, exact tag metadata, package provenance, and native final-image
geometry.

### 11.3 Keep macOS/Rosetta executable -- **CRASH FIXED / NATIVE ARM64 PRODUCT PROVEN**

The beta 20 Rosetta segmentation fault was reproduced and repaired. The x86_64
runtime now maps Lino workspaces below the 32-bit address ceiling, grows them by
safe map/copy/clear/unmap, and repairs the translated return path with
`lea rsp,[rsp+4]` so flags remain intact. Headless NIVGEN and the Cocoa game run
on Apple Silicon through Rosetta; the package is Finder-safe, ad-hoc signed,
manifested, and includes AudioQueue PCM. Intel-native x86_64 and Rosetta remain
supported compatibility routes. That x86_64 download is not notarized; a
separate native ARM64 product is now proven below.

The exact known-sector hash, Cocoa launch/quit checks, and uniform-white palette
rejection now pass on the Rosetta route. Broader mismatch-class NIVGEN work is
archived in `docs-notes/NIVGEN-HISTORICAL.md` rather than an unrun macOS gate. The
native ARM64 replacement below supersedes the earlier port attempt. The
read-only review of retained PR #10 at tip `2402172` found useful
`__PAGEZERO`/above-4-GB design notes, the conceptual `x19` through `x25` register
map, and a non-truncating code-entry pointer, but its implementation was not
merged as-is. Critical defects corrupt `x29`/`x30` across normal and nonlocal
returns, pass an `mmap` workspace to `realloc`, fail to clear growth, leave
translated workspace state stale after a move, force addresses, truncate
pointers, scan code unsafely, dump files unconditionally, and omit required
build inputs, translation, and Mach-O support.

The safe replacement on branch `arm64-runtime` now includes both a checked
static Linux AArch64 bridge and a compiler-owned integer target. The runtime
retains the 32-bit image layout while publishing full-width isokernel, code,
scalar-unary-helper, and scalar-binary-helper pointers in eight new UI units. It
preserves the x19-x25 Lino map, reserves x18, balances x29/x30 and SP, reloads WS
after every C isocall, seals loaded code RX, keeps workspace RW, and grows by
map/copy/zero/refresh/unmap.

`compiler114m.txt` recognizes `--cpu:aarch64` without loading a CPU pack and
emits deterministic little-endian words directly from compiler IR. The current
slice covers fixed-width 32-bit immediate/register moves plus direct and
canonical indirect workspace loads/stores. Indirect operands add a fixed unit
displacement to an A-E 32-bit unit-index pointer, scale from full-width x25, and
leave the pointer unchanged. Wrapping addition/subtraction, low-word signed or
unsigned multiplication, signed/unsigned division and remainder, AND/OR/XOR,
logical left/right shifts, arithmetic right shifts, variable rotates, bitwise
inversion, wrapping negation, and wrapping signed absolute value accept their
canonical register, direct, or indirect forms; binary right operands may be
immediate, register, direct, or indirect. Memory left operands are written back.
Remainders use a W12 quotient and `MSUB`; rotate-left negates its count into W12
before `RORV`; both retain W9 effective indexes through memory writeback.
Equality, signed and unsigned comparisons, and zero/nonzero bit-test branches
accept the same binary inputs without writeback. Source-first loads preserve
aliases across direct/indirect pairs. Tracked q73 value exchange now covers all
121 register, direct, and canonical indirect pairings. Memory pairs load both
old values before either write, recompute the right effective index, and fix an
indirect address before changing an aliased pointer register such as `A <> [A]`.

Tracked q69/q70 split division likewise covers all 121 pairs. The emitter
captures both old values and memory indexes, uses `UDIV` or `SDIV` with `MSUB`,
and writes quotient-left/remainder-right while matching the packs' alias order:
an aliased register retains the quotient, whereas an aliased memory cell retains
the later remainder. The generated image executes every register/direct/indirect
class pair, both pointer-alias directions, high-bit unsigned division, and signed
negative quotient/remainder cases. Divide-by-zero and signed-minimum divided by
minus one remain non-trapping AArch64 differences and are not claimed compatible.

The x64 pack continues past the i386 pack's q73 endpoint with q74/q75 split
multiplication. Those 121-pair unsigned and signed forms reuse the captured-value
and address path, apply `UMULL` or `SMULL`, and write low-left/high-right.
Tracked alias order leaves the low half in an aliased register and the later high
half in aliased memory. The generated image executes high-bit unsigned and
negative signed products, register and memory destinations, both pointer-alias
directions, and both alias write orders.

Stack push/pop, `$+`/`$-` unit-count adjustment, and `=$:`/`$:=`
immediate-relative access now cover every canonical immediate, register, direct,
and indirect shape. The logical contract remains 32-bit units, but each abstract
stack unit maps to one 16-byte physical SP slot. Signed extended adjustments,
pre/post-indexed push/pop, and scaled relative addresses therefore preserve
AArch64 alignment; a generated call occupies one such slot, and the execution
fixture proves a callee can reach its caller's stack value at relative unit one.
Tracked q71/q72 preserve the eight-slot `PUSHA`/`POPA` order
A,C,D,B,saved-SP,X,E,WS in one aligned 128-byte block. WS is saved and restored
at full pointer width, while pop-all deliberately skips the saved-SP slot. The
generated image rewrites every exposed restore slot, proves A-E and the DONE
value in X were restored, and then uses direct workspace access to prove the
restored WS remains valid. Unconditional and status branches, internal calls,
returns, and the exact full-width isocall ABI are also covered. Fixed two-word
immediates keep pass-one and code-pass lengths identical, and internal calls
preserve the host link register.

Ordinary scalar binary32 negation, magnitude, addition, subtraction,
multiplication, and division transfer raw IEEE-754 bits between W registers and
S0/S1 and return each single-precision result to its W destination. Register,
direct, and indirect left operands plus immediate, register, direct, and indirect
binary right operands use the established source-first and memory-writeback
paths. The executed fixture covers ordinary values, the minimum subnormal,
overflow to infinity, and signed zero. Tracked q44/q45/q46 repair opposite-infinity
addition, equal-signed-infinity subtraction, and zero-times-infinity multiplication
to x87 real indefinite `FFC00000h`. All three preserve the selected NaN payload
and sign, quiet signaling inputs, and apply measured right-operand precedence.
Generated register/direct/indirect cases cover each invalid class, dual quiet NaNs,
and signaling inputs in both operand positions. Tracked q47 also captures both raw
operand magnitudes and rewrites masked-invalid zero/zero and infinity/infinity
results to
the x87 real-indefinite bits `FFC00000h`, independent of operand signs. The
fixture executes register `0/0`, direct positive-infinity/negative-infinity, and
indirect negative-zero/zero cases; finite nonzero division by zero remains the
native signed infinity. NaN repair preserves the selected payload/sign, quiets
signaling inputs, and applies the measured x87 right-operand precedence. Generated
register/direct/indirect execution covers left, right, and dual quiet NaNs, both
signaling positions, and signaling-left/quiet-right precedence.

Signed conversions now cover register, direct, and indirect destinations and
sources. `SCVTF` plus binary32 writeback reproduces the tracked `FILD`/`FSTP`
round-to-nearest boundary, including 16,777,217 rounding to 16,777,216, while
`FCVTNS` reproduces in-range ties-to-even `FISTP` examples on both sides of zero.
A raw-input range repair maps positive and negative out-of-range binary32 values,
infinities, and NaNs to masked-x87 integer indefinite `80000000h` while preserving
the valid `-2^31` boundary. The generated image executes same-register quiet-NaN
conversion, direct positive overflow, indirect positive infinity, the largest
valid positive input, and a negative out-of-range input. Exact exception flags
and traps remain outside this bounded result-compatibility claim.

All six binary32 comparisons use `FCMP`. Additional conditional branches preserve
the x87 `FCOMP`/`FSTSW`/`SAHF` unordered mapping: equality, lower, and
lower-or-equal accept quiet-NaN unordered results; inequality, greater, and
greater-or-equal reject them.

Scalar square root now uses `FSQRT S0,S0` between raw W/S transfers and binary32
writeback for register, direct, and indirect forms. The generated image executes
an exact square, the minimum subnormal, and negative zero. A raw-input repair maps
negative finite inputs and negative infinity to masked-x87 real indefinite
`FFC00000h` without changing negative zero; register `sqrt(-1)`, direct
`sqrt(-infinity)`, and indirect `sqrt(-4)` execute under QEMU. Quiet NaNs preserve
payload/sign and signaling NaNs are quieted without replacing either; both signs
and register/direct/indirect writeback execute. Tracked q29/q30 use
x87 `FSIN`/`FCOS`; because AArch64 has no scalar trigonometric instruction, the
emitter now sends raw bits through the full-width helper and the Linux runtime
applies `sinf` or `cosf`. The generated image executes sine and cosine of 1.0,
sine of negative zero, and cosine of zero across register, direct, and indirect
writeback forms. The runtime now also reproduces the measured x87 result boundary
for both operations: finite magnitudes at or above `2^63` return their raw input,
infinities become real indefinite `FFC00000h`, quiet NaNs preserve payload and
sign, and signaling NaNs are quieted without replacing payload or sign. Generated
execution covers the exact positive threshold, a negative value above it, maximum
finite magnitudes, both infinity signs, and quiet/signaling NaNs. This does not
claim exact x87 range reduction below `2^63`, observable C2/status output, or
exception-state compatibility. Tracked q66/q67 load the right operand before the
left and execute one `FPREM`/`FPATAN`. Below exponent difference 64 the binary
helper applies `fmodf(left,right)`. At larger differences it reproduces the
measured one-step reduction width `N = 32 + (D mod 32)` by scaling the divisor
before one remainder operation, deliberately retaining the partial result rather
than iterating to completion. Generated register/direct/indirect execution covers
the complete `D=63` boundary, partial `D=64` and positive/negative `D=101`
results, and maximum-finite/minimum-subnormal `D=276`. Since x87 permits an
implementation-dependent N from 32 through 63, this pins the measured reference,
not every x87 model, and does not expose C2/status. Remainder classification maps
a zero divisor or infinite dividend to real indefinite `FFC00000h`, preserves a
finite dividend against an infinite divisor, and gives the right NaN precedence
while quieting signaling inputs. The same helper applies `atan2f(right,left)`.
Generated execution covers positive and negative zero, positive/negative-pi
signed-zero quadrants, one opposing-infinity quadrant, and right-precedence
quiet/signaling NaNs. Exact FP status/exception state and remaining transcendental
rounding remain separate work.

The focused gate bootstraps the modified compiler to an i386m byte-identical
fixpoint, packs the built runtime as an AArch64 SYS, compiles a real Lino source,
and executes the resulting ELF above 4 GB under QEMU. Independent encoded
fixtures continue to prove relocation, old-data retention, zeroed growth,
register preservation, exact instruction words, and seven malformed-image
refusals. All 12 checks, including compiler-produced value exchange, split
division, split multiplication, q71/q72 whole-register save/restore, scalar
arithmetic, masked-invalid and right-precedence payload-preserving NaN results for
addition, subtraction, multiplication, and division, in-range and
invalid/out-of-range conversion, ordered/unordered comparison, ordinary,
masked-invalid, and payload-preserving NaN square root, ordinary plus
large-finite/exceptional sine and cosine, ordinary/partial/exceptional one-step
remainder, and ordinary/signed-zero/infinite/NaN arctangent execution, passed in
hosted run 32579864461 at commit `d22af14`.

The separate native-macOS gate builds a thin unsigned arm64 RTM on an Apple
Silicon runner with the normal 4-GiB `__PAGEZERO`, then bootstraps the compiler
on Linux and appends a real compiler-owned AArch64 Lino fixture. A checked
post-link finalizer extends only `__LINKEDIT` over the appended payload, rounds
its VM geometry to 16 KiB, ad-hoc signs the result, and permits only that exact
signature suffix beyond `physappsize`. Run 32583022080 at commit `785532c`
executed the signed image natively on macOS 15 arm64 with status zero, exact
A-E=`1..5`, X=`DONE`, and code/workspace/isokernel pointers all above 4 GiB. The
final executable SHA-256 was
`ed312b96856f2dcfc43a4604ca2a4995064def423ec9e66d0a292fc2442f070e`.

The Darwin implementation now completes that foundation as a native product.
It adds Cocoa display, input, focus, file dialogs and event handling; exact
dynamic procedure calls; checked workspace relocation; AudioQueue stereo PCM;
and checked GlobalK storage for the only remaining optional service family
reachable from shipped Noctis source. APD, Printer, Net, and Clipboard remain
explicitly rejected because shipped Noctis does not issue those commands. The
full game compiles through the compiler-owned target, runs as a thin arm64
Mach-O above 4 GiB, survives raw and packaged retrace/save/quit smokes, and ships
in a Finder-safe ad-hoc-signed app with mutable data under Application Support.
Hosted run 32593712423 proved the complete native product gate. Reusable run
32594152146 proved the dedicated archive, checksum, and provenance artifact.
Tagged run 32595409634 then exercised the tag-derived bundle metadata, repeated
the raw and packaged native smokes, and published those three ARM64 files with
the Windows and x86_64 macOS assets in Beta 24.

PR #10 was closed as superseded after a specific public resolution identified
what was retained and why the prototype could not be merged. Joris van de
Donk's PAGEZERO analysis, register-map contribution, and technical credit remain
preserved on the derived commits.

### 11.4 Finish with one coherent repository audit -- **OPEN**

After the active runtime and remaining docket changes settle, run the complete
registered regression once from the same source state, including the explicit
deep sky/ground modes where their libraries changed. Repeat the production
closure and floating-operator scans, runtime-boundary checks, Python compilation,
workflow lint, package/provenance checks, and targeted static searches for raw
target blocks, target-dependent floating comparisons, and release-note drift.
Record every skipped external oracle as a gap rather than a pass.

Before any commit or release, recheck the protected artifact hashes, inspect the
complete intended diff and repository status, and account for every tracked and
new file. The user-owned `work/fp/fpout.bin`, `fprefout.bin`, `fptest.exe`, and
`fpvec.bin`, `docs-notes/Optimization.txt`, and the existing `.tmp-*` corpus are
not cleanup targets and must remain outside broad reset, copy, stage, or delete
operations. Close this item only when the final platform run and coherent suite
use the same accepted runtime baseline.

## 12. Cross-references

| document | what Wave 6 changed in it |
|---|---|
| `FLOATPOLICY.md` §0, §3.1-3.5, §5, §6 | original x87 evidence retained; shipping arithmetic and control ownership reconciled with the zero-native production closure |
| `WAVE4_NEARSTAR.md` §4, §5, §6 | `bclip` closed; the cast boundary settled; geometry still ungraded, with the reference status added |
| `tests/test_geometry.py` | the regression test for all four entries above |
| `noctis-harness/geo_grade.py` | the wave's own run. Its summary line still prints "the cast boundary stays OPEN", which entry 1 refutes; read it for the measurements, not for that sentence |
