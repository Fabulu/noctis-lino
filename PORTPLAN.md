# Port plan â€” Noctis IV in L.in.oleum

Source of truth for what is done and what is next. The hourly heartbeat reads
this file. Update it when a wave completes; do not let it drift.

## Standing rules

- Never launch `compiler.exe` directly. Build only via `lino_build.ps1`, which
  polls for artifacts and kills the GUI process.
- Never modify anything under `main/`. Every hash in `PRISTINE.sha256` must
  keep matching. The licence position depends on it.
- Never push or publish. Private until the original author grants permission.
- Verify claims by running things. A wave is not done because an agent said so.

## Gate before any new wave

```powershell
python tests\run_all.py          # must be all-pass (14 tests)
```
plus every `PRISTINE.sha256` hash still matching. If either fails, fix that
first â€” a broken foundation makes every later result meaningless.

---

## Done

### Toolchain
- `lino_build.ps1` drives the GUI-subsystem compiler non-interactively:
  launches, polls for artifacts, kills. Classifies warnings vs errors, and
  refuses paths containing `--` (see bug 1).
- Regression suite: `tests/run_all.py`, 12 tests, 313 checks, ~176 s. Nothing
  is graded against a stored binary; every side is rebuilt each run, and each
  test builds a deliberately broken version of its subject and requires that
  to fail.

### Language extension (optional, not load-bearing)
- `*%` / `*%'` split-multiply added: 242 patterns, all semantically verified on
  real hardware. Needs `main/lib/gen/compiler114m.exe` with `-Cpu i386m`.
- Patched compiler passes the fixpoint test â€” recompiles itself byte-identically.
- `main/lib/gen/compiler.txt` is NOT modified; `tools/patchcompiler.py` produces
  a copy. Reversible by deleting one file.

### Ported and verified
- **Galaxy hash** â€” `work/galaxy.txt` (ML fragment) and `work/galaxy2.txt`
  (`*%`). Bit-exact against a C oracle lifted from `noctis-iv-lr` and an
  independent arbitrary-precision Python implementation, across 343 sectors
  spanning the galactic origin. The signed multiply is load-bearing: unsigned
  builds a plausible galaxy that matches nothing.
- **`fast_random`** â€” the second of only two algorithms needing a full 64-bit
  product. Bit-exact on all three backends.
- **Star catalogue validation** â€” generated positions checked against the real
  `STARMAP.BIN`, 37,578 records charted by players over twenty years, including
  the author's own hard-coded stars matched uniquely. Collisions are quantified
  rather than assumed away, and signal is measured against an unsigned-and-decoy
  control rather than a bare chance floor.

### Wave 1 â€” Borland's LCG, exhaustive (DONE)

`srand` / `rand` / `random` ported and proven across the **entire seed space**:
65,536 seeds x 16 draws = 1,048,576 draws, plus the full `random()` argument
domain (all int16 values x 4 seeds x 2 draws). Three independent
implementations â€” lino, C, and an arbitrary-precision Python written from the
algorithm rather than transcribed. Registered as `tests/test_brtlrand.py`.

Anchored on the shipped binary, not on anyone's transcription: Borland's
`rand()` sits at file offset 15979 of `NOCTIS.EXE`, and the multiplier's low
half `35 4E` occurs exactly once in 215 KB, so the location is unambiguous.

Builds with the **stock compiler and stock pack** â€” the multiply is 32x32 into
32 low half only, so no `*%` is involved.

**The finding that propagates: `int` is 16 bits in the DOS build.** A
`random(n)` call with n above 32767 wraps negative â€” `random(40000)` passes
âˆ’25536 and returns a negative result. Reproducing this needs explicit narrowing
at the call site (`BrtlToInt16` then `BrtlRandom`); calling `BrtlRandom`
directly with a large argument diverges from the game. **Every call site in
later waves must be checked for arguments above 32767.**

**Recorded so it is not re-litigated:** replacing the logical shift with an
arithmetic one in `(seed >> 16) & 0x7FFF` is **semantically neutral** â€” the
mask keeps bits 16..30 and sign-fill only touches bits it discards (verified
over 200,000 random seeds, zero differences). No behavioural test can catch
that mutation; the byte-template check is the only way to pin it, and it does.

### Census
Noctis IV has 20 multiply sites, 5 that matter, and only 2 distinct algorithms
need a full 64-bit product â€” both now ported. Six of nine builds use the stock
compiler and stock pack. **`*%` is a contribution, not a dependency.**

---

## The wave pipeline â€” every wave, no exceptions

Not a suggestion and not scaled down for "small" waves. A wave that skips
stages is not a wave.

| # | Stage | Count | Role |
|---|---|---|---|
| 1 | **Recons** | **3+, parallel** | independent angles on the subject. Read-only. Verify assumptions against the actual bytes rather than repeating them. |
| 2 | **Architect** | 1 | consolidates the recons into a plan: files, algorithm, how correctness gets demonstrated, failure modes. May reject the wave's premise. |
| 3 | **Implementers** | **2+, parallel** | each owns a *disjoint file namespace* so they cannot collide. Build it, run it, report actual output. |
| 4 | **Reviewer** | 1 | adversarial. Reads the real files, not the implementers' reports. Hunts circular verification, the `variables`/`workspace` trap, signedness, register clobbering, silent error paths. |
| 5 | **QA** | 1 | re-runs everything independently. Confirms or refutes each claim, then tries to break it with edge cases. |
| 6 | **Test writer** | 1 | durable regression tests that provably fail when the guarded thing breaks â€” demonstrated by breaking it and showing the catch. |

â‰ˆ9â€“10 agents per wave.

**Why the plurals are load-bearing.** Multiple recons because one angle misses
things and two agreeing independently is real evidence â€” the CPU pack format
was cross-validated that way, and the `6241` figure was derived three separate
times before it was trusted. Multiple implementers because disjoint namespaces
let real work proceed in parallel without merge conflicts.

**Why review, QA and tests are separate people.** They catch different classes
of error. In the three-track run, the reviewer found design problems, QA found
a claim that did not survive re-running, and the test writer found that some
tests passed even when the subject was deliberately broken. Collapsing those
roles loses the disagreement that makes them useful.

## Oracle trust â€” read before using any reference

**`noctis-iv-lr` is NOT ground truth everywhere.** Its README lists planetary
surface generation as unfinished, and its changelog deliberately excludes
assembly-to-C++ translation artifacts â€” so its silence never implied
correctness. Confirmed divergences from vanilla:

| Where | Divergence | Consequence |
|---|---|---|
| type 3 land noise | vanilla **adds** to smoothed terrain, LR **assigns** | changes albedo at the landing site, hence scenario type, hence all ground terrain. **LR unusable as an oracle for habitable planets.** |
| type 9 | writes to the offscreen video page, not the surface buffer | substellar objects get an unfilled surface map |
| `wave()` | drops a `+4` byte offset | affects gas giants; correct answer depends on Borland's allocator |
| `lssmooth` | one fewer pixel per call, added to silence a memory checker | small but systematic |

**`niv-plus` is a fork**, Noctis IV+ Release 2.3, not the pristine 2003 drop.
Every generation-path function was compared against LR and matches, so it is a
valid stand-in *for generation*. Do not assume that holds elsewhere.

**Where neither is trustworthy, the DOS binary under DOSBox is the only
reference.**

## Wave 2 â€” the two geometry unknowns (SETTLED)

Both answered by static analysis of the shipped `NOCTIS.EXE`. Full evidence
chain in `docs-notes/WAVE2_ANSWERS.md`; pinned by `tests/test_wave2.py`.

```
unknown1.verdict = NARROWED_AT_CALL_BOUNDARY
unknown2.verdict = LEFT_TO_RIGHT
```

1. **The `double` does NOT survive into `rand`.** It is chopped by Borland's
   `__ftol` and narrowed to `int16` at the call boundary.
2. **`zrandom` is first draw minus second.** Left to right.

**Both answers vindicate `noctis-iv-lr`.** These were flagged as the most
likely sources of silent planetary divergence; they are not. **No sign flips
are needed**, and LR's planetary geometry is trustworthy on these two points.

**Structural finding that dissolves the original premise:** `rand` has exactly
**one caller**, so `random()` was compiled as a real function rather than
expanded as a textual macro. The narrowing is therefore uniform at every call
site instead of varying with the argument's declared type.

**Confidence, stated honestly.** Three decoders by different routes (capstone
anchor / ndisasm symbol-signature / byte-template with no disassembler), a
15-mutant battery in which every expectation must first differ from the
pristine answer, and a generated liar-decoder control that must be caught on
all 15. Caveat: `bx_w2.py` carries a hardcoded verdict for unknown 1, so that
answer rests on **two** genuinely independent routes, not three. The asymmetry
is encoded in the test rather than hidden.

Note: `NOCTIS.EXE` is a **large-model** build using far calls. Any independent
re-derivation needs the segment mapping â€” near-call assumptions find nothing.

## Floating point â€” sharper than first framed

The earlier rule (make quantisation points exact, tolerate the rest) holds, but
the worst cases are not comparisons â€” **they are seeds**. `global_surface_seed`
is a double sum times 4112 truncated to long; `seedval` is a product of up to
six doubles. One ULP changes the truncated seed and you do not get a slightly
different planet, you get a **different planet**. No tolerance exists there.

Vanilla was built `-f287`: x87 with 80-bit intermediates. Whether lino can be
made to match that is the single highest-leverage open question.

## Floating point â€” the precision ladder, and why lino loses

**The original's FPU state is known exactly.** Control word `0x133F`, read out of
the shipped `NOCTIS.EXE` by parsing the MZ header and the Borland C0 startup:
precision control = **64-bit extended (80-bit)**, rounding = **nearest-even**,
all exceptions masked. It links `fp87.lib`, not the emulator â€” hardware FPU.

**The ladder, worst news first:**

| | precision held |
|---|---|
| original (DOS, x87) | **80 bits across whole expressions** â€” asm chains keep values on the x87 stack over many operations with no store |
| noctis-iv-lr (SSE2) | 53 bits per operation |
| **L.in.oleum** | **24 bits per operation** â€” narrows after *every single instruction* |

The earlier hypothesis that lino might sit closer to the original than LR does
is not merely wrong, it is wrong by the largest possible margin. lino's native
floats **cannot** reproduce the original's generation arithmetic.

**Why that is fatal specifically for generation.** The seeds are floating-point
values truncated to integers (`nearstar_identity`, `global_surface_seed`,
`seedval`). One ULP changes the truncated seed, and the result is a *different
planet*, not a nearby one. At 24 bits versus 80, divergence is certain, not
possible. There is no tolerance to set.

**Therefore, for generation code: integer reduction first, soft-float second.**
Do not attempt to emulate the original's float chains â€” reduce the arithmetic
to exact integer operations wherever the algebra permits, and fall back to a
soft-float double only where it does not. Rendering keeps native floats; a
quarter-pixel is invisible.

**One piece of free good news.** The original has *two* floatâ†’int behaviours:
C casts truncate (Borland's `__ftol` flips to chop and back), but **38
hand-written `fistp` sites round to nearest-even** because the rounding control
stays at 00. Those are the projection and texture-mapper sites. Under a
round-to-nearest policy lino's `=,` reproduces all 38 **for free**, and an
explicit correction helper is needed only at the C-cast sites. That also means
LR's half-away-from-zero `round()` is LR's bug, not something we inherit.

**A decoy that will mislead any audit.** `PITAGORA.H` contains a
`_control87(RC_CHOP, MCW_RC)` call that **never executes** â€” Noctis includes
`tdpolygs.h` and never `pitagora.h`. The same trap is preserved in LR's `Old/`
tree. Anyone checking for control-word handling finds it first and concludes
the original ran in chop mode. It did not.

**Mixed-precision round-trips are observable behaviour.** The declared-type
split is `double` for generation, `float` for rendering, and some values are
deliberately narrowed mid-expression (`nearstar_ray` is `float` but feeds
`double` math). Preserve the narrowings; do not optimise them away.

**Outstanding:** the full quantisation-site registry was produced by the recon
but survives only in its transcript. Rebuilding it â€” every floatâ†’int cast and
every float comparison that selects a branch, with file:line â€” is a task for
the float wave, not something to reconstruct from memory.

## x87 is not optional â€” settled by the data

The starmap harness proved the catalogue's stored doubles decode bit-exactly
**only under 80-bit x87**: 4194/4194 records, against 2315/4194 with IEEE
doubles throughout. That is a fingerprint identifying Borland + 387 as the
writer, and it matches the shipped compiler config `-ml -3 -f287`.

So extended precision is required to read the shipped data correctly, not
merely to match the original's flavour. Whether lino can be made to run at
64-bit precision â€” via the x87 control word, legally settable from an ML
fragment â€” is the highest-leverage open question in the project.

Two catalogue records are malformed and must be **rejected, not zeroed**:
`#3876 WESTOS` is âˆ’0.0, `#34754 MDIR 17` is a byte-reversed NaN.

## Corrections to earlier claims â€” do not re-introduce

| Claimed | Actually |
|---|---|
| `GLOBES.MAP` is int16 records | **int8 (y,x) pairs.** The int16 reading is an artifact of a constant y byte in the high position; the code sign-extends 8â†’16. Texture stride 360, not 256. |
| `CURRENT.BIN` is 245 bytes | 245 is only the documented first block. Real size **370** (stock/LR), **381** (NIV+). |
| `SURFACE.BIN` is 45 bytes | 45 stock/LR, **40** in NIV+. Not interchangeable. |
| the `pwr` +15000 bias is a harmless legacy | **Live threshold in ~12 places.** Store power unbiased and the ship reads as permanently dead. |
| `charge < 0` is corruption | Deliberate cheat (infinite fuel, prints OMEGA). Do not clamp. |
| `atl_x`/`atl_z` are 0..3276800 | The code stores the **quotient** (`>>14`); on-disk range is 0..~200. |

## L.in.oleum file-interface constraints

- **No `SEEK_END`.** `[File Position]` is absolute-from-start only; negative is
  a hard error. Noctis seeks from the end throughout, so every such read needs
  `TEST` first to learn the size, then an explicit subtraction.
- **Short reads are silent.** A partial read is not an error â€” `[Block Size]`
  is quietly corrected to what was actually read, and does not survive the
  isocall. Check it after every read.
- **CWD is not the executable's directory.** The runtime passes names straight
  to `open()`. Noctis handles this by parsing `argv[0]` and `chdir`-ing; do the
  equivalent with `SET DIR` before touching any asset.
- **No open/close** â€” each I/O is a complete transaction.

**Ship assets as plain files, not via the stockfile.** The stockfile is
read-only, cannot report a member's size at runtime, forces â‰¤8-character
lowercase names, and requires a recompile per asset edit. The plain-file path
is needed anyway for saves and catalogue appends, and one I/O path beats two.
Both reference ports moved assets out of the executable independently.

## Asset manifest

Ship three files: `supports.nct` (60,776), `STARMAP.BIN` (1,202,500),
`GUIDE.BIN` (4,063,588). `globes.map` and `offsets.map` live inside the NCT and
need not ship separately.

Do **not** port: the seven `.VOC` files (zero references in either tree),
`ALPHABET.NCC` / `EXT-VHCL.NCC` / `FACE.NCC` / `PARATIE.NCC` (never loaded),
`TEXT3D.H` (not in the build). Only three models are ever loaded â€” VEHICLE (the
stardrifter), MAMMAL, BIRDY.

**`.NCC` trap:** triangles carry uninitialised garbage in their unused fourth
vertex slot, some decoding near 1e38. The loader zeroes it *before* the
transform pass; skip that and the transform produces infinities.

## Runtime feasibility â€” measured, not estimated

The platform is not the constraint. All figures below were measured with probe
programs built and run on this machine.

| Facility | Result |
|---|---|
| clear + palette-expand + RETRACE, 320Ã—200 | **0.799 ms â€” 1.5% of a 55 ms tick** |
| unthrottled frame rate | 785 fps (RETRACE does not block on vsync) |
| median tick, busy-wait on the HPT | **55.0000 ms**; p90 within 0.1 Âµs |
| timer resolution | 111 ns (TSC/256, ~9000 counts/ms) |
| `SLEEP` as a tick source | **useless** â€” 62.75 ms for a 55 ms request |
| workspace growth | 1 GB allocation succeeded |
| exclusive 320Ã—200 | real mode switch, closest thing to mode 13h |

**Implications.** ~54 ms of every tick is free for the renderer. Palette
animation costs a full re-expand each time (0.10 ms) since there is no palette
hardware â€” affordable hundreds of times per tick. Memory is a non-issue: the
entire working set is ~643 KB, ~2.5 MB even at one byte per 32-bit unit.

Two refinements to build in from the start: target the true DOS period of
**54.9254 ms** (65536/1193182 s), not 55; and accumulate the deadline rather
than re-basing each tick, which removes a measured +0.057 ms/tick drift.

**Input is better than LR's.** The LUCK table gives true held-key state â€” 1
while physically down, 0 on release â€” which is the direct equivalent of the DOS
BIOS key-down table Noctis used and which LR had to reconstruct from polling.
98 keys, arbitrary combinations, no repeat. `GET CONSOLE INPUT` is a separate
ASCII FIFO, right for command letters and name entry, useless for flight.
Events are drained at the top of every isocall, so a frame that makes no
isocall stops responding.

**MIDI: SETTLED â€” the game never played music.** The soundtrack is the
background music of the HTML *manual*, via a `<bgsound>` tag that only Internet
Explorer honoured. Ryan Bury's credit enumerates it among manual assets ("this
manual, its non-screenshot graphics, and *its* soundtrack"), and NIV+ 2.4
modernised the same tag to `<audio>` with an MP3. A browser played it.

Verified against four real distributions spanning ~25 years (original DOS,
Noctis IV CE, NIV+ 2.3 and 2.4): **none ever set a `mididevice`, and none ever
placed a MIDI file near `modules/` or `data/`.** `NOCTIS.EXE` has no sound-card
port I/O and no audio filenames; `GO!.EXE` is a 4.6 KB ShellExecute shim; the
PC-speaker routines live only in a header included solely by the model editor
and are never called. `niv-lr` did not drop audio â€” across 302 commits it never
mentions it. There was never any to drop.

The VOGONS thread that suggested otherwise says the opposite on a closer read:
the same poster wrote "there is no sound, so I didn't worry about those
settings". The Linux crash is a DOSBox ALSA bug independent of the guest.

**Consequence: the port has ZERO fidelity obligation for audio.** Silence is a
legitimate, faithful ship state â€” it is what the original, every distribution,
`niv-lr` and the Windows port all shipped.

**If we want music anyway, it is new content, and pre-rendering is correct.**
Render offline, ship as PCM, stream through the working audio path. A free win:
lino's stereo-16 packing (channel 1 low half, channel 2 high half of one unit)
is bit-identical to interleaved S16LE, so a headerless 44100/16/stereo render
loads straight into the workspace with no conversion. Full track ~24.6 MB,
2.4% of the demonstrated ceiling, fits in memory â€” no disk streaming needed.
Unverified: that lino assembles file bytes into units little-endian. Probe it;
if wrong, fix it in the offline baker, not in lino.

**A wavetable synth is UNNECESSARY, not infeasible** â€” correcting the earlier
claim in both directions. ~800â€“1,200 lines of lino for output worse than a
fluidsynth render, on content that never responds to game state. Justified only
if someone later wants music that reacts to gameplay, which is a new feature
rather than a port requirement.

**Licensing, separate from Ghignola's.** The music is **Ryan J. Bury's**,
credited separately and contributed as manual decoration. The "private until
the author permits" rule covers Ghignola; shipping a rendered soundtrack needs
Bury's permission as a distinct matter. Gate music as an optional, separately
licensed add-on pack rather than part of the base asset manifest â€” especially
since the render alone would be ~4.6x the size of every other game asset
combined.

**VOC effects.** One loop buffer with a live playback cursor
â€” write ahead of the cursor each tick with all effects summed. A software
mixer, ~300â€“500 lines, ordinary work. There is no MIDI interface in the comm
area at all; the soundtrack would require writing a General-MIDI softsynth.
**MIDI is the only genuinely infeasible item in the entire port.** Audio is
also Win32-only â€” the Linux runtime's PCM layer is a stub.

**No window-close event exists.** ESC-to-quit is the only exit, as in LR.

## The hardest problem: no byte addressing

L.in.oleum is unit-addressed, 32 bits per unit, with no byte pointers anywhere.

Noctis is built on byte arrays indexed with byte arithmetic, deliberately
aliased onto one another, read from disk as packed byte streams, and written
through a byte-per-pixel framebuffer whose overruns the original tolerated
because neighbouring bytes were harmless. LR had to inflate two buffers purely
as guard bands for out-of-bounds writes present in the original source.

None of this translates mechanically. **Every buffer needs an explicit
decision** â€” one item per unit (4Ã— memory, simple, fast, and now trivially
affordable) or packed four-per-unit with shift/mask on every access. Every
aliasing relationship and every out-of-bounds write the DOS layout silently
absorbed must be found and made explicit.

Laborious, not infeasible â€” but it touches essentially every rendering
function, and it is where the bugs will live. **Default to one item per unit**
unless a specific buffer proves it needs packing; memory is free here and
correctness is not.

## Gotchas discovered by probing

- **Underscores in lino string literals become spaces.** Use `\us`. A filename
  literal with an underscore silently writes to a differently-named file.
- A partial read is not an error; `[Block Size]` is quietly corrected.
- `[Counts]` wraps every ~477 s, but unsigned subtraction across the wrap still
  gives the correct delta.

## Sphere rendering â€” the table is a formula

`GLOBES.MAP` is not opaque data. Its geometry was recovered by fitting, with
**RMS residual 0.47 px over all 10,780 records**:

```
row k = round((i-5.5)/360), column s = i-5.5-360k
latitude  psi    = -60 deg + 1.00047*k       (1 deg per texture row)
longitude lambda = -1.00060*s                (1 deg per texture column)
camera distance D = 2.506 sphere radii
dx = 250.84 * cos(psi)*sin(lambda) / (D - cos(psi)*cos(lambda))
dy = 200.68 * sin(psi)             / (D - cos(psi)*cos(lambda))
```

The constants are round numbers â€” `Fy ~ 200` is the engine's own focal length,
`Fx/Fy = 1.250` is the 320x200-on-4:3 pixel aspect, `D = 2.5`. This is the
original derivation recovered, not a curve fit. A port may regenerate the table
rather than ship it, though shipping is safer for bit-exactness.

Total advance is exactly 43,200 = 360 x 120, so `globe()` only ever displays
**latitudes -60 to +59** â€” 60 rows of the 360x180 texture are never shown.

**Traps:**

- **Lighting is baked into the texture, not computed.** `surface()` darkens a
  130-degree longitude band starting 35 degrees after the sub-stellar point by
  a shift, across 179 rows. 130 rather than 180 is deliberate (diffuse light
  plus limb foreshortening, per the author's note). `glowinglobe` re-derives
  the same constants at draw time so the crescent matches. **There is no N.L
  anywhere in the planet path.**
- **`globe()`'s parameter is named `offsetsmap`, but every caller passes the
  globes map.** The offsets map goes only to `background()`. Easy to wire a
  port backwards.
- **The 32,768-byte buffer is triple-purposed** â€” globe table, sea/horizon
  texture, and the 32x36 pilot font aliased at its tail. The ground renderer
  overwrites it, which is why the maps are reloaded on leaving a planet. **Use
  separate buffers.**
- LR parameterised `globe()` for arbitrary resolution but left `glowing_globe`,
  `white_globe` and `white_sun` hard-coded, so the four now disagree about the
  clip rectangle. Another entry for the unreliable-oracle list.

## Wave plan

Populated by the architect once the five recons report.

Strong candidate for **Wave 1**, from the planet-generation recon: port
`brtl_rand` / `brtl_random` / `brtl_srand`, Borland's LCG, and prove it
**exhaustively** â€” `brtl_srand` takes a `uint16_t`, so all 65,536 seeds at a
fixed draw depth is a complete proof rather than a sample. Zero floating point,
needs no `*%` (the multiply is 32Ã—32â†’32 low half only), and it gates 346
`random()` call sites. Nothing downstream can be verified until it is exact.

Then, before any geometry: the **DOSBox evaluation-order experiment** to settle
the two unknowns above.

- [ ] **Wave 1** â€” pending architect
- [ ] **Wave 2** â€” pending architect
- [ ] **Wave 3** â€” pending architect

### Reconnaissance in flight

| Track | Question |
|---|---|
| Renderer | the 3D pipeline: `poly3d`, `polymap`, projection, the 2D primitives, sphere rendering |
| Planet generation | `prepare_nearstar`, the Borland LCG, surface terrain, where LR is an unreliable oracle |
| Floating point | what lino's float support actually is, and where bit-exactness is achievable |
| Data formats | `SUPPORTS.NCT`, `.NCC` models, the map tables, saves, and how they map onto lino's stockfile |
| Runtime gaps | framebuffer, 18.2 Hz tick, input, audio, memory â€” can this be a playable game at all |

---

## Floating-point policy

Bit-exactness is never lost, only deferred. Design so it can be switched on
later without touching call sites.

**Three tiers, by cost:**

| Tier | Mechanism | Cost | Use |
|---|---|---|---|
| native | lino's own float instructions, inline | free | rendering |
| controlled | x87 precision-control set to match the original | ~free if available | generation |
| soft-float | IEEE 754 in integer arithmetic | slow, but bit-identical on any machine forever | fallback, and the guarantee |

Soft-float is the escape hatch that makes this safe to defer: exact 64-bit
integer arithmetic in lino is already proven, so a deterministic double is
buildable whenever we need one.

**The rule that actually matters.** Smooth float differences are cosmetic â€” a
planet a hair's width off looks identical. The failures that matter are where a
float is **truncated or compared into a discrete decision**: floatâ†’int casts,
comparisons that select a branch, anything feeding an array index or a shift
count. The known example is `rarity_factor`, where `sqrt` feeds a truncation to
`int16` that becomes a shift count and flips a star in or out of existence.

So: **make the quantisation points exact, not everything.** Those sites are
rare and cheap to protect; the arithmetic between them is not worth chasing.

**Structure:**

```
generation   -> every float op through the policy layer
                (per star / per planet; call overhead irrelevant)
rendering    -> native ops inline
                (per pixel; exactness cosmetic, speed is not)
quantisation -> ALWAYS exact, whichever policy is active
```

**The registry.** `FLOATPOLICY.md` (to be written from the float recon) lists
every float site with its classification â€” exact-required or tolerant â€” so
"what matters" is version-controlled rather than remembered. Changing a
classification and rebuilding is the intended edit; the harness then reports
whether it changed any output.

**Detection.** The test harness runs the same generation code under two
policies and reports exactly where results diverge, so switching from tolerant
to exact is a measurement rather than a leap of faith.

## Known hazards

- **`"variables"` vs `"workspace"`** â€” in `variables`, `name = N;` initialises a
  variable to N; in `workspace` it allocates an *uninitialised vector of N units*
  and the name is its address. `foo = 0;` in `workspace` allocates nothing, top of
  workspace never advances, and every symbol collapses onto the same cell. No
  error, no warning, uniformly wrong values.
- **Self-hosting trap** â€” `lino_build.ps1` clears the output path before
  building. Compiling a compiler with itself deletes the compiler mid-build.
  Build under a different name.
- **Floating point is the next real unknown.** The original ran x87 with 80-bit
  intermediates; LR uses SSE2 doubles; lino has its own float instructions.
  Bit-exactness will not be available everywhere. The hazards are not smooth
  differences â€” they are float results that get truncated or compared into
  discrete decisions, such as `sqrt` feeding a truncation that becomes a shift
  count and makes a star blink in or out.
- **LR is not a trustworthy oracle everywhere.** Planetary surface generation is
  unfinished there. Establish per-subsystem whether it can be used as ground
  truth before relying on it.

## Bugs found in L.in.oleum

1. Command-line parser truncates on `--` anywhere, then blames the CPU pack.
2. `main/linux_compiler.bin` segfaults at startup on modern systems.
3. Relative-address modifier documented backwards; `+` and `-` both subtract.
   Fixed in the patched compiler: `+` left alone, `-` now adds.
4. Application-name field not cleared before writing, leaving a shard of the
   runtime template string in every executable.

