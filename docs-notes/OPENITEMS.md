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
evidence rather than that single timing delta.

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

**ROTOR IGNE visible-companion checkpoint.** A second certified native pose
turns 34 degrees downward while keeping the visor open. Body 3 is then visible
at native relative screen coordinate `(-15,17)` with its long source flare,
while the class-8 primary is behind the camera. A shared-workspace bug had let
the companion pass overwrite `SFXX/SFYY/SFZZ`; the following primary-flare
call consequently redrew the companion using the primary star's much shorter
distance and produced a large false cyan bloom. The local-system renderer now
reconstructs the primary coordinates at the original call boundary. Fresh
same-clock native and Lino captures agree on body 0 radius `0.01632`, body 3
radius `15.6`, its three-dimensional local vector, visibility, centre, and
radial-beam layout. Companion radii now remain binary64 through the source's
`(10 * ray) / distance` calculation instead of being narrowed to binary32 at
the flare boundary. A focused product capture changed no pixels in the sun
region; its only 20 differences from the prior frame were clock glyphs. The
false secondary bloom is gone, but exact full-frame corona and palette grading
against native remains open.

A second defect was in the checkpoint state rather than the flare raster.
Restoring an active local system rebuilt the fine-approach integrator but left
the outer Vimana drive at its startup `stspeed=1`, `ap_reached=0` values. The
gallery scene was therefore fading and accumulating additive rays as if it
were still in fast travel, while the native checkpoint was stationary. Active
local-system checkpoints now restore `stspeed=0`, `ap_reached=1`, and stationary
space frames perform the source's exact `pclear(adapted+2880,0)` viewport clear.
The clear is eight-way unrolled so restoring the source boundary does not add
an interpreter-scale fill penalty. In the same 41-by-31 sun crop, pixels above
the bright RGB thresholds 160 and 220 fell from 180/141 to 55/31; the native
frame contains 64/37. This removes the accumulated blue slab and leaves a
native-sized centre while exact whole-frame grading remains open.

The gallery checkpoint had also disabled synchronization while its native
reference visibly reported `TRACKING`. It now selects source fixed-chase sync;
the retained body offset is already the exact navigation-120 equilibrium, so
the viewpoint remains stable. The outer HUD now follows the source's settled
local branch and renders `TRACKING`, or `MOVIEMAKER` while recording, instead
of leaking the fine-approach integrator's `STANDBY` state.

The reproducible `orbitmultiple` gallery scene uses this open-visor
native-matched pose by default. This closes the coordinate, drive-state, and
beam-accumulation defects in one real visible-companion context, not the
remaining cross-context matrix.

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
compositing remain separate coverage.

**Airless rocky native-context checkpoint.** The same fixed epoch now covers
the system's type-4 body at longitude 90, heading 270, and pitch -38. Both
renderers retain distance `9133.45`, exposure `53.2168`, rain `0`, day state,
albedo 36, and seed 38821023. Both show the small primary disc over the black
airless sky and deliberately draw no radial flare: the distance exceeds the
source's `1000 * ray` upper gate. The reproducible `rockysun` scene preserves
this negative case. Authenticity includes correct beam suppression, not merely
adding rays whenever a disc is visible.

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
coordinates (`C140A69B`, `C1A89AA9`, `B5774B25`).  Both frames show the same
large white disc and broad corona over the purple atmosphere. The reproducible
`densesun` scene records this authenticated positive case. A full-context
stage dump now proves more than the screenshot: the native and Lino local-sun
passes change the same 15,469 indexed pixels in the same `(70,9)..(246,112)`
box and apply the same transformation to every changed pixel. Their following
palette-band masks also cover the same 58,240 pixels in
`(0,9)..(319,190)`. The later `lens_flares_for` pass changes zero pixels in
both engines at this pose, so the visible corona and radial layout belong to
the exactly matched local-sun pass. The remaining 2,676 differences were all
zeroed Lino pixels in the panorama mapper's irregular edge area. The port had
added a rectangular guard-band erase that does not exist in NIV+ and could
present as a black horizon edge. Removing that erase makes the complete
64,000-byte pre-sun page exact, so the full background, sun, and mask sequence
is now byte-exact for this real scene. Final terrain and object compositing
remain separate coverage.

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
no-beam case. Exact full indexed-frame grading remains open.

**Frozen-world class-1 checkpoint.** A separate system extends the matrix
beyond class-0 primaries. On its type-7 body at longitude 0, heading 90, and
pitch -44, both renderers retain star class 1, stellar radius `21.879`, solar
distance `34167.4`, exposure `58.695`, rain `0`, and day state. Certified
frames place the larger white disc against the frozen world's black sky and
again suppress beams because `34167.4 > 1000 * 21.879`. The reproducible
`frozensun` scene records this distinct star-size and no-flare case. The wider
frozen starfield parity item remains open independently.

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
for continued movement after takeoff. Renderer fidelity; audio; file mutation and
persistence services; complete game-mode coverage; and the performance work needed
for smooth play also remain open.

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

## 10. NIVGEN public accuracy integration -- **DEFERRED PENDING UPSTREAM EVIDENCE**

The local investigation is deferred as of 2026-08-22 at the user's direction.
Historical game semantics and the distinct public-artifact compatibility policy
are now measured and retained; the final 22 fields require the unpublished exact
NIVTEST harness/executable or paired upstream captures. Do not resume corpus
sweeps, add fixture-specific answers, omit fields, or weaken comparisons without
material new upstream evidence. Continue the actionable project docket while
Joris reviews the reports.

`docs/NIVGEN.md` remains the operating procedure if the boundary reopens;
`tools/nivtest.py` runs a production case, `tools/nivgen_score.py` scores a
bounded local selection, and `tools/nivgen_sheet_report.py` snapshots,
classifies, and diffs the complete public API corpus. Live reads are eleven
sequential 500-row requests with a one-second delay and no retries.

**Measured baseline, 2026-08-21.** The canonical 5,188-row snapshot is
`ab73b236957f225247e07460eaae1a7e26891e701d6b5bd4c93d573208231f97`.
The sheet's zero-error/checkmark marker is not the exactness denominator during
backfill: 642 rows have no authoritative hashes and are marked zero-error. Lino
shows 1,068/5,188 markers but only 426/4,546 independently comparable rows are
fully hash-exact (9.4%). Rust is 4,246/4,546 (93.4%). LR's 613 visible markers
are all unbackfilled; it is 0/4,546 fully exact with 175 missing result rows.
Lino field exactness is:

| field | exact / authoritative | rate |
|---|---:|---:|
| orbital surface | 401 / 4,485 | 8.9% |
| atmosphere | 3,627 / 4,485 | 80.9% |
| palette | 2,622 / 4,485 | 58.5% |
| default heightmap | 2,895 / 4,546 | 63.7% |
| default object chart | 4,538 / 4,546 | 99.8% |
| random heightmap | 3,233 / 4,546 | 71.1% |
| random object chart | 3,439 / 4,546 | 75.6% |
| default surface texture | 4,545 / 4,546 | 99.98% |
| default sky | 4,544 / 4,546 | 99.96% |
| random surface texture | 4,508 / 4,546 | 99.2% |
| random sky | 4,541 / 4,546 | 99.9% |

Comparable exact rows are concentrated in types 3 (174/220), 9 (192/215), and
10 (59/61). Types 0, 1, 4, 5, 6, 7, and 8 currently have none; type 2 has one.
Planets score 294/1,438 and moons 132/3,108. The earlier 1,128 "exact" count was
actually the previous zero-error marker count and mixed true matches with
unbackfilled rows. As backfill advanced it fell to 1,068, confirming the user's
observation that apparent checkmarks can disappear. The dominant orbital-
surface mismatch and broad height/object mismatch classes remain release gates.

**Complete local result, 2026-08-22.** Every authoritative row and field has been
executed in retained, non-overlapping private-desktop shards. The scores now
separate historical live-game fidelity from public-artifact compatibility.
Historical game semantics reach 49,771/49,823 exact fields and 4,512/4,546 exact
rows against the public data. Request-scoped NIVGEN compatibility semantics
reach 49,801/49,823 fields and 4,540/4,546 rows. That policy alone adds exactly
30 fields and 28 rows with zero regressions; these are compatibility matches,
not proof that live gameplay agrees with the artifacts. Under compatibility
semantics, types 0, 6, 7, 8, 9, and 10 are fully exact and every orbital surface,
atmosphere, and palette matches. All 22 residual fields are landed outputs across
XENOFELYS bodies 4, 5, 8, 9, 10, and 11. The full 30-transition audit is
`tests/gen/nivgen-historical-vs-public-compatibility.json` (SHA-256
`a6a750495eff4d7fe7ace95834ada312203894ed2f2ee197b2c726d803d29348`).

`MAGILLA PRIME|5` was the sole downstream integer-boundary difference between
the historical extended and complete binary64 geometry hypotheses over 4,473
model-valid rows. Public NIVGEN matches binary64 nearstar expression boundaries
and a stored left-to-right rotation seed; the shipped game retains historical
x87 behavior by default. The NIVGEN-only driver enables and restores the general
reference mode. Request-scoped binary64 stores after each atmosphere coordinate
product and final sum repair the final 24 atmosphere fields. Retaining doubled
half-degree latitude through the type-3 strict polar-seed comparison repairs the
three remaining non-XENOFELYS random skies. The 30-check focused gate pins these
general boundaries and confirms no body, coordinate, fixture, or expected-hash
exception was introduced.

The pre-atmosphere complete score remains
`tests/gen/nivgen-portable-f64-complete-score.json` (SHA-256
`709604cb7f25d79152391001721eb8c871c0c513d24e62036f2ffcd05578d2b3`).
The final type-3 merge and validated full composite are
`tests/gen/nivgen-f64-final-type3-complete.json` and
`tests/gen/nivgen-f64-final-composite-score.json`, with SHA-256 values
`ea48450b3a7e979729bf922473c8445ccf9bf7114ce6b22a11d0e93125d69047` and
`e21ea9cc83b189650221b88703576c48f6ba4bdb763aa1da6c3f088556755d6a`.
Full parity remains the release gate; this is not yet the release milestone.

**macOS palette regression and PR #22.** Contributor PR #22 changes `SU shade
byte` to convert finite binary32 through `FToIntChop`, then clamp the signed
integer to `0..63`. That is the correct original order and removes two target-
dependent Lino floating comparisons that made planet palettes uniformly white
on macOS. The patch was substantively reviewed locally and appears correct; the retained
Windows surface hashes remained exact and all Wave 5 palette checks passed. It
is applied locally but not yet merged. The Apple-Silicon Rosetta workflow now dumps
the selected 192-byte palette and rejects both uniform `0x3f` white and any
other uniform value before packaging. That source gate still needs a hosted
macOS run because Windows CI did not reproduce the defect.

**Scored extent reconciliation.** The hash, transport, fill, and image sizes are
now independently pinned rather than conflated. Surface and sky transport/render
`360 * 180 = 64,800` bytes but hash only the first `360 * 128 = 46,080`; the sky
prefill additionally initializes 64 allocation-slack bytes. Surface texture
transports `256 * 256 = 65,536` bytes but both its hash and public PNG stop at
`256 * 254 = 65,024`. The excluded two texture rows contain the known
nondeterministic tail and are not parity inputs. `nivtest.HASH_EXTENTS`, its
focused scorer test, the published LR harness, and measured public PNG dimensions
all agree. No residual XENOFELYS field can be repaired by changing a scored
boundary.

**Acceptance path.** Run the non-white Rosetta gate, then use the retained
snapshot/differential report to classify and reproduce the dominant mismatch
clusters by field, body type, and planet/moon status. Preserve raw artifacts for
every locally reproduced mismatch. Backfill only from a named source revision
and executable hash; report exact row and field counts before and after every
repair. The one-sector seven-hash CI fixture remains useful as a fast smoke but
is not NIVGEN parity evidence.

**Complete type-1/type-5 power-fixed milestone.** The retained 2026-08-21
offline run grades all eleven fields on 1,648 rows and 18,128 comparisons. It
improves from 11,120 exact comparisons and no fully exact rows in the sheet
snapshot to 18,120 comparisons and 1,646 fully exact rows. Relative to the
post-zero-quotient score, the exact-power-of-two repair makes 209 exact repairs
(174 random heightmaps and 35 random object charts), with zero regressions and
zero wrong-to-different-wrong changes. Surface, atmosphere, palette, and default
texture are 1,648/1,648. Six fields are 1,647/1,648; random object chart is
1,646/1,648. The score and transition are
`b118f2530e260faf6dd550f338d8b9c6c9e0dba0029e85e1bcc0c801049af719`
and `d79805fdd9f63c25469c935ff38dbb26dbe204d1535b7034046daf7f896f4853`.
The retained score-to-score comparison is
`c7c226a6f62104e9831242149c01dbe6737082663d3cffbe9cc4788348f0bae1`.
Its executable remains bound to the exact closure manifest and dirty patch; the
scoring run additionally binds the private-desktop runner and shard merger.

**Two residual invariant-breaking rows.** Only `XENOFELYS|4` and
`XENOFELYS|10` remain in this complete type-1/type-5 selection. The former
misses default HM/OC/sky and random HM/OC; the latter misses random OC/texture/
sky. `XENOFELYS|10` random HM is now exact. The retained corpus otherwise has
one default type-5 heightmap (`301D7754`) on 630/631 rows and one random type-1
sky (`7B252DC5`) on 1,016/1,017 rows; each XENOFELYS target is the sole outlier.
All authoritative hashes remain unchanged. Before changing production again,
obtain a fresh original/reference first-divergence trace at ground reseed,
type-switch return, post-smoothing, inclination, and sky painter/horizon
boundaries. Distinguish captured call/allocation context from a remaining x87
sine or spill delta. Do not search parameter space for a matching hash and do
not add star-, body-, coordinate-, or expected-value-specific behavior.

The retained public sky images narrow this further. `XENOFELYS|4`'s default and
random original PNGs are byte-identical despite different raw-sky FNVs.
`XENOFELYS|10`'s random target `CBD77DB5` is exactly a 46,080-byte zero sky with
one byte changed at offset 12,167 (`x=287`, `y=33`, value 80); the published PNG
also differs from the default black sky by that single pixel.

A clean private-desktop NIV+ R2.3 boundary capture now proves the generator does
not write that byte. DOS-aware MZ disassembly identified `create_sky`, its caller,
and file offset `0x1DA03` immediately after return. A copied executable patched
only there with an `EB FE` self-loop stopped XENOFELYS body 10 at `(130,9)` while
target 10 was reached/synchronized, power was still 15,000, and the
`Surface.BIN` landed pattern was absent. The recovered far-heap sky matched
current Lino byte-for-byte: all 46,080 scored bytes were zero, FNV-1a
`7B252DC5`, including zero at 12,167. Original and patched executable SHA-256
values are `5e64d532091c9be1f91d7e0bc57719df24020ba38b0662f225f65d3c55e579ac`
and `5d9c23bc959039d78e5d4ab8e71095f57e9d98a4995d4b1d3f9edc948f2f37f8`.
The retained report SHA-256 is
`e58437be86dd93522f5e97fbb31c1935f7dc6f1879f27f6421d6813bd79b03d9`.
The anomalous value 80 therefore lies between native generator return and the
NIVTEST pre-hash boundary, can reflect same-DOSBox residual state, or belongs only
to the retained artifact. Atmospheric game captures remain non-oracles because
gameplay applies different filters from the public caller.

A complete public-image reconstruction now identifies nine sparse target-compatible
residual fields rather than only the body-10 sky. Unique one-byte substitutions
recover body 4 default sky, body 5 random texture, body 9 default sky, both body
10 random image fields, and body 11 default heightmap; two public RGB pixels
recover body 11 random texture exactly. The body-5 default and random
HM/OC/texture also match extracted late-game NIV+ R2.3 buffers byte-hash for
byte-hash. Two additional constructions are exact but deliberately remain
non-source evidence: body 8 random sky reaches its target with the public visible
`30 -> 14` candidate plus any of three pairs of palette-equivalent substitutions,
and body 9 default texture has twelve distinct two-index palette-equivalent
solutions. Body 9 random texture remains unreconstructed. The retained report
SHA-256 is `b281be3f41610ac33ecac94d2734f0cb087ca0e6020cfc36a221575415737c64`.
Multiplicity prevents selecting authoritative bytes or a generating mechanism;
these results strengthen the capture-state or anomalous-artifact diagnosis and
block per-field source patches.

The published `noctis-iv-lr` harness at commit `01c6a3a` runs each landed command
once rather than reusing buffers across bodies or sites. Although it allocates
with `malloc`, `build_surface` clears all 40,000 height and object bytes and fills
texture offsets 0 through 65,534; `surftex` fills all 64,800 rendered sky bytes
before `create_sky`. Only one texture-tail byte and 64 sky-slack bytes remain
allocator-dependent, all outside the scored extents. It also replays the exact
per-row 16-byte gap. The canonical sheet supplies another independent
discriminator: all 22 residual originals differ from current Lino, sheet Rust,
and sheet LR; current and Rust agree on 21, while all three implementations agree
on eight. No authoritative residual matches any of the three implementations.
Ordinary in-process allocation/reuse in the LR harness therefore does not explain
the cluster.

The actual original-engine orchestration is public in SheetBot's
`nivgen-integration` branch, pinned at
`b7847bef16f08976c0a7e813410eec07d03d7775`; commit
`4b2706e492c497cb90c3acf6b0f4edc8da50c990` introduced it. `origEngine()` runs
`planet-all` in one DOSBox-X session, sorts bodies, and processes chunks of 12.
For every body in a chunk it starts five separate `NIVTEST.EXE` processes in one
shared DOSBox-X session: default `sector`, random `sector`, default `surftex`,
random `surftex`, then `planet`. This exactly explains upload groups 0--11,
12--23, and 24--32. The commands do not pass `-gap`; those bytes arise from the
actual DOS allocation state. Each command has fresh C globals, but guest RAM and
DOS allocator/header contents can survive between executable invocations. A
direct DOSBox-X 2026.08.02 probe proves that premise: a writer and reader in
separate COM processes requested the same 65,536-byte allocation at segment
`0913`; the reader recovered all 256 sampled writer bytes in the shared session,
while an otherwise identical clean session returned 256 zero bytes at `0913`.
The retained report SHA-256 is
`1458c2497b1cb966a695ccb50c81a3442838fc11b1d98b205b05b13495c3aaf1`.
This establishes possible cross-process payload reuse, not that NIVTEST reads it.
The ordering adds a sharper correlation: XENOFELYS bodies 0--3 are exact; body 3
is the last exact body and the only first-chunk row with a nonmodal random-sector
gap (`...C5090000` instead of `...C5096055`). All 22 residuals then fall on bodies
4--11 before the DOSBox reset, while every comparable row in chunks 12--23 and
24--32 is exact. Bodies 6 and 7 inside the window are also exact, and body 14 has
a nonmodal gap without later residuals, so the gap is a marker rather than a
sufficient cause. The retained order-correlation report SHA-256 is
`80eb577da71679ce8abff16cbc0a04007fb882a85abd40fab4e2c0e2b5574497`.
A single source-grounded replay rules out the visible gap as the whole mechanism:
using body 3's exact nonmodal gap for body 4 left both heightmaps unchanged and
changed the default/random object charts to `DA454969`/`FDB335DA`, none of which
matches the four authoritative HM/OC residuals. The retained report SHA-256 is
`b3367dc37137743076436f963ad2d75711570bdf7384319b1fbac999769c18c0`.
No alternative gap was searched; unrecorded heap payload and allocation history
remain open. A second bounded check rejects direct same-offset carryover from
each random `surftex` command's immediately preceding default command: none of
the six sparse authoritative candidate bytes for bodies 5, 8, 10, and 11 equals
the predecessor byte at that offset. Its report SHA-256 is
`f877cd3d11c969e13bfaec356161b8b451fa5bae24703e17d22791478563d51f`. No shifted offsets or
alternate values were searched, so other allocation mappings and earlier chunk
history remain open.

The NIV+ 2.3 source boundary now limits direct payload reuse further. Its fixed
heap order places 64,800-byte `s_background`, 65,552-byte
`p_background`/`txtr`, 40,000-byte `p_surfacemap`, and 40,000-byte
`objectschart` consecutively. The landed path fills the complete sky buffer, all
scored texture bytes, and both complete 40,000-byte maps before scoring. The
known terminal inclination loop reads 200 bytes beyond the heightmap--the
observed 16-byte allocator gap plus 184 bytes of the already initialized current
object chart--but writes only object counts. It cannot modify the already built
sky or texture and does not write the heightmap. Generic same-address payload
survival therefore remains relevant to object-chart header influence, but does
not explain residual HM/texture/sky hashes through the published source-shaped
path. The missing NIVTEST capture/copy/scratch boundary remains open. The
retained source trace SHA-256 is
`4274b1af13cfea66a22f40b985b1af2f81e87aadf1d94eb429242890ace01e0d`;
it searched no target hash, byte, offset, or parameter.

SheetBot pins the original engine source as
`fb067a16c36f3b67a139fec3c47be483e3bb93965d467612724234d608ef21ac`.
The hash covers `tests/harness/NIVTEST.CPP`, `NIVHASH.C`, `NIVHASH.H`,
`NIVSTUBS.C`, `tests/dosbox/BUILD.BAT`, `LINK.RSP`, both generator translation
units, and every source header. The exact harness/build files and corresponding
`NIVTEST.EXE` are absent from the public Noctis-IV-Plus branches. Its separate
public `planetdump` branch emits orbital BMPs from `NOCTIS.EXE` and is not the
landed NIVTEST harness.

The prior timestamp experiment consequently tested a different sharing boundary.
A local LR probe generated XENOFELYS once, then generated each orbital surface and
both recorded landed sites in one native process while preserving the measured
gap. Before interpretation, an isolated body-0 control exposed and repaired two
probe-only omissions: LR's `quadrant` declaration occupied two bytes under MinGW
despite the documented one-byte object-chart ABI, and the headless harness had
not allocated `adapted`. The corrected control reproduced the authoritative
body-0 default heightmap `301D7754`. The completed single-process batch matched
none of the 22 residual targets and changed formerly clean sky/texture outputs
relative to fresh LR commands. Its report SHA-256 is
`aea64f0281b2a205f7885f46a9f3291b71559f9bdc82c649f26197bfa1b6898d`.
This rejects only that native body/site ordering; it does not reproduce the
actual same-DOSBox, separate-executable allocation history.

Obtain the unpublished DOS harness source or exact `NIVTEST.EXE`, then run the
five-command, 12-body sequence both inside one DOSBox-X session and with one clean
DOSBox-X session per command. Capture allocation segments, the 16 bytes after the
object chart, and every full scored buffer immediately before hashing. If those
materials cannot be obtained, ask for authoritative XENOFELYS regeneration under
both session policies before changing generator arithmetic.

**Pull-request handling policy.** Review incoming PRs against the current
production tree and deal with them as appropriate: merge clean unique work,
adapt or cherry-pick useful pieces from stacked branches, or close changes that
are obsolete, duplicated, unsafe, or superseded. Before closing any PR, leave a
specific public comment stating what was evaluated, what landed elsewhere (if
anything), why the PR is being closed, and what work remains. Do not silently
close a contributor's branch merely because current master has moved ahead.

**Production runner merged, 2026-08-18.** PR #5 landed the portable executable
handoff, macOS x86_64 container build, and SheetBot-facing `tools/nivlin`
wrapper on master. The wrapper calls the generated production harness rather
than the older duplicated `nivlin`/`nivlinvh` implementations. GitHub's Windows
gameplay and package checks passed, and a cached public `OLIKETT I|0` row scored
7/7 through the prebuilt-executable route. One farther-away row from every
planet class then scored 118/118 fields, while 20 type-7 moon cases scored
140/140 after the two-pass surface-buffer repair. Those selected checks proved
the runner route but badly overstated corpus-wide parity; the 5,188-row baseline
above supersedes them as accuracy evidence.

A fresh late-corpus batch on 2026-08-18 covered 20 `RAVALISS` bodies of types
0, 2, 3, 5, and 7. Both the fixed and random landed sectors were graded along
with orbital surface, atmosphere, and palette output: all 220 available NIV+
hashes matched. This adds two arbitrary-coordinate type-2 cases, but it remains
a selected historical batch rather than evidence against the full-sheet
mismatch distribution above.

**Cold generation acceleration, 2026-08-18.** The shared 40,000-cell terrain
fill, in-place smoothing, signed level pass, and fast-noise pass now execute as
bounded native kernels. The same exact Borland fill and smoothing kernels also
cover the 65,535-cell planet texture paths. Borland's signed `random(n)`, both
RNG states, draw counts, FNV ledgers, traversal directions, and in-place write
order remain intact. The focused painter artifact stayed byte-identical at
SHA-256 `99067B096289AD60F7D663A03FB638037CD52B3B0CBC8D5D153B187B75859721`
while its warm execution fell from about 224 ms to 7 ms. A real cold habitable
scene reached its first capturable frame in 9.23 seconds instead of 17.18
seconds. The production clean-return fixture still matches NIV+ on all 40,000
height bytes and all 65,532 deterministic texture bytes.

The following radial-profile pass shares one generation-stamped cache between
`round_hill` and `std_crater`. Each hill now evaluates the exact qword-spilled
`sqrt` and `cos` chain once per integer squared distance, then reuses the same
binary32 profile for symmetric pixels. The same cold habitable scene reached
its first capturable frame in 4.92 seconds. A fresh production clean-return
comparison still reported zero heightmap and deterministic-texture differences
against NIV+.

Habitable asterism rays now retain each ray's exact binary64 sine and cosine
once instead of recomputing the same pair for every pixel along that ray. The
same product smoke reached its first capturable frame in 3.17 seconds, down
from the original 17.18-second baseline. The clean-return NIV+ comparison again
reported zero differences after this pass.

**Portability correction, 2026-08-19.** The native generation kernels described
above violated the project's portable-Lino architecture and have been removed.
Their parity fixtures and performance measurements remain useful evidence, but
the implementation and timings are historical, not the current production
state. Recover this speed only through ordinary Lino algorithms, compiler/CPU
pack improvements, or platform runtime work below the language boundary.

**Coordinate-convention guard.** Gameplay checkpoint fixtures store the star Y
value in the port's internal convention, while the public NIVGEN command uses
the public catalogue convention. Do not copy a checkpoint Y directly into a
runner invocation: doing so can select a different topology and make a valid
body index look missing. Take parity inputs from the sheet/scorer record itself
and retain one known 11/11 row as the runner smoke.

## 11. GitHub documentation and README -- **SETTLED / MONITORED**

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
remaining defects are back on the docket, but explicitly last. Finish the
native runtime/compiler, rendering, optimization, static-analysis, bug-hunting,
documentation, and cleanup items before reopening browser work.

## 12. Release, portability, and macOS gates -- **OPEN / CRITICAL**

These are near-term release gates, not background polish.

### 12.1 Finish the portable-Lino repair -- **IMPLEMENTED / HOSTED BOUNDARY PROVEN**

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

### 12.2 Keep releases usable -- **RESTORED / HOSTED GRAPH HARDENED**

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
Rosetta exact generation, both packages, and prerelease publication. Do not make
a full-parity claim while the 22 retained NIVGEN fields remain unresolved.

### 12.3 Keep macOS/Rosetta executable -- **CRASH FIXED / REGRESSION EXPANSION OPEN**

The beta 20 Rosetta segmentation fault was reproduced and repaired. The x86_64
runtime now maps Lino workspaces below the 32-bit address ceiling, grows them by
safe map/copy/clear/unmap, and repairs the translated return path with
`lea rsp,[rsp+4]` so flags remain intact. Headless NIVGEN and the Cocoa game run
on Apple Silicon through Rosetta; the package is Finder-safe, ad-hoc signed,
manifested, and includes AudioQueue PCM. Intel-native x86_64 and Rosetta are the
supported macOS routes. The download is not notarized and is not native ARM64.

Keep the exact known-sector hash and Cocoa launch/quit checks, but add the
uniform-white palette rejection from PR #22 and full/mismatch-class NIVGEN
coverage. The `133Fh` host probe passed the current hosted Intel and Rosetta
executions recorded above. A native ARM64 game remains a larger port. The
read-only review of retained PR #10 at tip `2402172` found useful
`__PAGEZERO`/above-4-GB design notes, the conceptual `x19` through `x25` register
map, and a non-truncating code-entry pointer, but its implementation must not be
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
Unconditional and status branches, internal calls, returns, and the exact
full-width isocall ABI are also covered. Fixed two-word immediates keep pass-one
and code-pass lengths identical, and internal calls preserve the host link
register.

Ordinary scalar binary32 negation, magnitude, addition, subtraction,
multiplication, and division transfer raw IEEE-754 bits between W registers and
S0/S1 and return each single-precision result to its W destination. Register,
direct, and indirect left operands plus immediate, register, direct, and indirect
binary right operands use the established source-first and memory-writeback
paths. The executed fixture covers ordinary values, the minimum subnormal,
overflow to infinity, and signed zero.

Signed conversions now cover register, direct, and indirect destinations and
sources. `SCVTF` plus binary32 writeback reproduces the tracked `FILD`/`FSTP`
round-to-nearest boundary, including 16,777,217 rounding to 16,777,216, while
`FCVTNS` reproduces in-range ties-to-even `FISTP` examples on both sides of zero.
All six binary32 comparisons use `FCMP`. Additional conditional branches preserve
the x87 `FCOMP`/`FSTSW`/`SAHF` unordered mapping: equality, lower, and
lower-or-equal accept quiet-NaN unordered results; inequality, greater, and
greater-or-equal reject them.

Scalar square root now uses `FSQRT S0,S0` between raw W/S transfers and binary32
writeback for register, direct, and indirect forms. The generated image executes
an exact square, the minimum subnormal, and negative zero. Tracked q29/q30 use
x87 `FSIN`/`FCOS`; because AArch64 has no scalar trigonometric instruction, the
emitter now sends raw bits through the full-width helper and the Linux runtime
applies `sinf` or `cosf`. The generated image executes sine and cosine of 1.0,
sine of negative zero, and cosine of zero across register, direct, and indirect
writeback forms. This does not claim x87-compatible large-argument range
reduction or C2 behavior. Tracked q66/q67 load the right operand before the left
and execute one `FPREM`/`FPATAN`; the binary helper applies bounded
`fmodf(left,right)` or `atan2f(right,left)` accordingly. The generated image
executes positive and negative remainders plus first-quadrant, axis, and zero-angle
arctangents across register, direct, and indirect writeback. Multi-step partial
remainders, exceptional divisors, signed-zero quadrants, and exact FP exception
state remain open. Invalid or out-of-range conversion results, negative finite
square-root results, signaling-NaN state, NaN payload equivalence, and remaining
transcendental compatibility remain separate work.

The focused gate bootstraps the modified compiler to an i386m byte-identical
fixpoint, packs the built runtime as an AArch64 SYS, compiles a real Lino source,
and executes the resulting ELF above 4 GB under QEMU. Independent encoded
fixtures continue to prove relocation, old-data retention, zeroed growth,
register preservation, exact instruction words, and seven malformed-image
refusals. All 12 checks, including compiler-produced value exchange, split
division, split multiplication, scalar arithmetic, conversion, ordered/unordered
comparison, square-root, sine, cosine, bounded partial-remainder, and
partial-arctangent execution, passed in hosted run 32575511694 at commit
`fa158b0`.

Remaining floating-point/x87 semantics, full runtime services, native macOS/Cocoa
and Mach-O packaging, and a native ARM64 Noctis build remain open.
Expand instruction/runtime coverage before
beginning Mach-O or native-game integration. Keep Joris van de Donk's source and
commit credit. Leave a specific public review
before adapting or closing PR #10; no public action has yet been taken.

### 12.4 Finish with one coherent repository audit -- **OPEN**

After the active runtime and remaining docket changes settle, run the complete
registered regression once from the same source state, including the explicit
deep sky/ground modes where their libraries changed. Include NIVGEN-specific
work only if material upstream evidence reopens that deferred boundary. Repeat the production
closure and floating-operator scans, runtime-boundary checks, Python compilation,
workflow lint, package/provenance checks, and targeted static searches for raw
target blocks, target-dependent floating comparisons, stale duplicated NIVGEN
implementations, and release-note drift. Record every skipped external oracle as
a gap rather than a pass.

Before any commit or release, recheck the protected artifact hashes, inspect the
complete intended diff and repository status, and account for every tracked and
new file. The user-owned `work/fp/fpout.bin`, `fprefout.bin`, `fptest.exe`, and
`fpvec.bin`, `docs-notes/Optimization.txt`, and the existing `.tmp-*` corpus are
not cleanup targets and must remain outside broad reset, copy, stage, or delete
operations. Close this item only when the final platform run and coherent suite
use the same accepted runtime baseline.

## 13. Cross-references

| document | what Wave 6 changed in it |
|---|---|
| `FLOATPOLICY.md` §0, §3.1-3.5, §5, §6 | original x87 evidence retained; shipping arithmetic and control ownership reconciled with the zero-native production closure |
| `WAVE4_NEARSTAR.md` §4, §5, §6 | `bclip` closed; the cast boundary settled; geometry still ungraded, with the reference status added |
| `tests/test_geometry.py` | the regression test for all four entries above |
| `noctis-harness/geo_grade.py` | the wave's own run. Its summary line still prints "the cast boundary stays OPEN", which entry 1 refutes; read it for the measurements, not for that sentence |
