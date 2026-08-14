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
Ten surface-flare oracle cases likewise preserve their expected pages. Four of
those cases use the exact binary32 ray and distance captured from the current
thin-atmosphere, quartz-world, clear habitable-world, and airless lunar scenes.
The lunar case is the source-gated unchanged-page negative described below.

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

The product gallery publishes the fixed-epoch checkpoints as
`planet-lunar-sun.png`, `planet-thin-sun.png`, `planet-rocky-sun.png`, and
`planet-frozen-sun.png`. Their captions distinguish a real radial flare from
the source-gated no-flare discs so screenshots do not imply that every visible
sun must emit beams.

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

## 7. Smooth 60 Hz presentation -- **SETTLED / MONITORED**

Harden the optional 60 Hz renderer until sustained walking, looking, jetpack
flight, capsule travel, orbital flight, and Stardrifter movement remain evenly
paced while every gameplay decision continues at the original 18.206-Hz rate.
Acceptance requires long real-input sessions across the heaviest habitable
surface and every major mode transition, with no duplicated-pose hitch,
catch-up burst, terrain loss, input loss, or simulation acceleration.

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

## 8. Cross-references

| document | what Wave 6 changed in it |
|---|---|
| `FLOATPOLICY.md` §0, §3.3, §5 table, §6.1 | the cast boundary is settled for the original; the interim rule survives but now guards the code generator rather than covering an unknown |
| `WAVE4_NEARSTAR.md` §4, §5, §6 | `bclip` closed; the cast boundary settled; geometry still ungraded, with the reference status added |
| `tests/test_geometry.py` | the regression test for all four entries above |
| `noctis-harness/geo_grade.py` | the wave's own run. Its summary line still prints "the cast boundary stays OPEN", which entry 1 refutes; read it for the measurements, not for that sentence |
