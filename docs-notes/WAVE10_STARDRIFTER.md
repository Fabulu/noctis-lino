# Wave 10 — the Stardrifter interior, the game's first screen

**Goal:** when the port starts, you are standing inside the Stardrifter, looking at what a
1996 player saw. Not a planet surface, not a heightmap flyover — the actual opening view.

## Architect correction — read before the original brief below

The three Wave 10 recons found four load-bearing errors/omissions in the initial brief:

1. The clean-start view is the **interior**, not the roof. Source defaults are
   `pos=(0,0,-500)`, `user_alfa=user_beta=0`, `lifter=0`, `opencapcount=0`; the first main
   loop computes `ontheroof=0` before calling `vehicle()`.
2. The player's own hull is always `drawpv` **mode 2**: two deterministic
   `randomic_mapper` subdivisions normally, three while depolarized. Mode 0 at
   `NOCTIS.CPP:1157` belongs only to `other_vehicle_at()`. Phase 0 remains useful, but only
   as a narrow outside-hull join probe.
3. Wave 6b's emitted `K3A/CALL` dispatch is **not graded by the durable suite**.
   `tests/test_spheres.py` classifies DRAW as ungraded and never compares CALL rows. Wave
   10 must first build a real dispatch oracle; it cannot use an unchanged-dispatch claim as
   evidence.
4. The dependency list omitted `randomic_mapper`, the complete 2-D `Stick`, `alogena`,
   `lens_flares_for`, and `fline`. `alogena`'s flare branch is active at clean startup
   (`ilightv=1`, `elight=0`), so it is required for an authentic opening and cannot be
   hidden in NOT-GRADED. Only `cupola`'s `gburst>1` flare branch is startup-unreachable.

The frozen verification split is **D/R/J**: independently grade dispatch (D), grade the
raster page from independently expected dispatch/leaf records (R), then grade the joined
path's pre-render trace and page (J). A page is never credited unless its matching trace
passes. Wave 10 does not begin implementation until the Wave 9 foundation suite is
genuinely green; in particular, ordinary failing assertions must not masquerade as XFAIL.

This document is written for an agent who has never seen this project. Part 1 is the whole
project. Part 2 is the wave.

---

# PART 1 — THE PROJECT

## What this is

Noctis IV (Alessandro Ghignola, 1996, DOS, Borland C++ real-mode) is being ported to
**L.in.oleum**, the cross-platform assembly language written by the same author. The point
is fidelity: the port should compute what the original computed, and where it cannot, it
should say so precisely rather than approximate quietly.

Nine waves are done, committed and pushed. The game builds, runs at ~30 fps, flies, renders
3D terrain from live camera state, and round-trips saves byte-exact.

## Where everything is

```
C:\programmieren\linoleum              the repo (origin Fabulu/noctis-lino)
  main\                                the stock L.in.oleum toolchain - NEVER MODIFY
  work\*.txt                           lino source (~260 programmes and libraries)
  tests\                               the regression suite - run_all.py is the roster
  noctis-harness\                      C and Python reference implementations per subsystem
  docs-notes\                          per-wave findings, the buffer map, the float policy
  tools\                               packtool, genmul, buildpack, patchcompiler
  PORTPLAN.md                          source of truth: done, open, standing rules
  PRISTINE.sha256                      6 toolchain hashes that must always match

C:\programmieren\noctis\niv-plus       reference clone: DOS sources + data - READ ONLY
C:\programmieren\noctis\niv-lr         reference clone: the C++ de-assembly - READ ONLY
```

`niv-plus\source\*.CPP` is the 1996 code. It is the specification — there is no other.

## L.in.oleum in ninety seconds

Untyped, unstructured, register-based assembly. Registers `A B C D E` map to
`eax ebx ecx edx esi`; `O` is the workspace origin (`edi`), `X` is `ebp`. A programme is
divided into periods: `"directors"`, `"constants"`, `"variables"`, `"workspace"`,
`"programme"`. **Unit-addressed, 32 bits per unit, no byte pointers.** Machine-language
fragments are written `{ F7 E3 }` inside `"programme"`.

Traps that have each cost real time:

- **`"variables"` and `"workspace"` are not interchangeable.** In `variables`, `name = N;`
  declares a variable initialised to N. In `workspace`, `name = N;` allocates an
  *uninitialised vector of N units* and the name becomes its **address**. So `foo = 0;` in
  `workspace` allocates nothing, the top never advances, and every symbol silently collapses
  onto one cell. No warning. Uniformly wrong values.
- **Underscores in string literals become spaces.** Use `\us`.
- **A failing lino programme still exits 0.** Grade output files by mtime, never by exit
  code, and delete the target before every run.
- **No path may contain `--`** — the argument parser truncates on it and then reports
  `internal problem: invalid cpu pack`, blaming a file that is perfectly intact.
- **A short read is not an error.** `[Block Size]` is silently corrected to what was
  actually read. Every read needs an explicit check.

`docs-notes/LINOBUGS.md` has the full list, with what was fixed and what was not.

## How to build and run — the only supported way

```powershell
powershell -File C:\programmieren\linoleum\lino_build.ps1 `
  -Src C:\programmieren\linoleum\work\<prog>.txt `
  -Compiler C:\programmieren\linoleum\main\lib\gen\compiler114m.exe -Cpu i386m
```

```powershell
powershell -File C:\programmieren\linoleum\tests\w7arun.ps1 `
  -Exe ...\work\<prog>.exe -Out ...\work\<prog>-out.bin
```

`compiler.exe` and `compiler114m.exe` are **GUI-subsystem binaries**. Launched directly they
open a window over the user's terminal and wait for a human. `lino_build.ps1` drives them
non-interactively — launch, poll for artifacts, kill. Use `w7arun.ps1` rather than
`linorun.ps1` for anything with a large dump: it waits for the output size to *settle*.

## The verification philosophy — this is the important part

The project's standard is not "the code looks right". It is:

1. **Rebuild every side, every run.** Nothing is graded against a stored `.bin`, because a
   stored `.bin` is exactly the thing that goes stale without anyone noticing.
2. **Three-way where possible** — lino == Python spec == C reference. Two independent
   transliterations plus the port.
3. **Every check must be provably able to fail.** Each test builds deliberately broken
   variants of its own subject and requires them to fail. A check that has never been seen
   to fail is not evidence.
4. **Say what is not graded.** Every wave document has a NOT-GRADED section listing each
   ungraded item and why, rather than letting absence be inferred.

### The failure mode this project keeps hitting

**The tautological check** — a check that passes regardless of input, because it compares a
value to itself, hardcodes its own verdict, or is never folded into the result. It has
recurred in Waves 5, 5b, 5c and 7a. The Wave 7a instance is instructive: a grader row passed
`True` as its literal verdict while the computed comparison went only into a note string,
and the row was not ANDed into the total. It printed `10 ok 0 fail` while three of its ten
rows disagreed.

`tests/w5audit.py` detects this mechanically by executing check conditions over 300 random
assignments. **Its default scope does not yet include `noctis-harness/su_*.py`** — extending
it is open work (`docs-notes/WAVE7A_REMEDIATION.md` section B).

### Oracles, and why they are scarce

The 1996 binary emits only what a player needed. Data files record outcomes, not
intermediates. `niv-lr` targets playability rather than fidelity and does not document its
translation choices. So the strongest available oracle differs per subsystem, and the
*honest name* of each one matters:

| wave | oracle | strength |
|---|---|---|
| 3, 4 | `STARMAP.BIN`, `DL.EXE` captures | strong — 1996 artifacts |
| 7a, 7b | NIV+ Release 2.3 guest RAM captures | weaker — a fork, not 1996 |
| 6a, 6b | three-way internal consistency | weakest — no external artifact |

There is **no stock 1996 `NOCTIS.EXE` on this machine** — all three copies hash
`5E64D532091C9BE1…`, 215,744 bytes, NIV+ Release 2.3. Never write "byte-exact" without
saying byte-exact *against what*.

## Standing rules — restate these in every prompt

- Never launch `compiler.exe` or `compiler114m.exe` directly. Build only via `lino_build.ps1`.
- To run a compiled lino programme, use the poll-and-kill pattern (`w7arun.ps1`).
- **Never modify anything under `main\`.** All six `PRISTINE.sha256` hashes must keep matching.
  The licence position depends on it: `main/lib/gen/compiler.txt` is under the WTOF Public
  License, which forbids modification without the author's authorisation. Every fix lives in
  a *copy* produced by `tools/patchcompiler.py`.
- **Never modify the reference clones** under `C:\programmieren\noctis`.
- **Never run git — not even `git status`.** Committing and pushing is the coordinator's job,
  after independent verification.
- **Publication terms.** The repository may be published under the original WPL with
  the author's authorisation, while preserving Noctis IV's original gameplay and credits.

## What exists after nine waves

| wave | subsystem | state |
|---|---|---|
| 1 | Borland `rand`/`srand`/`random`, galaxy hash, `fast_random` | byte-exact, all 65,536 seeds |
| 2 | catalogue decoder, `random()` argument type | pinned |
| 3 | the float engine (x87, 133Fh control word, 64-bit extended) | graded by `STARMAP.BIN` |
| 4 | `nearstar` generation, draw accounting | graded by `DL.EXE`, 4,365 records |
| 5 | buffer model, framebuffer, the 54.9254 ms tick | 188 checks |
| 6a | projection, `poly3d`, `polymap` — the rasteriser | byte-exact over 64,000 pixels |
| 6b | spheres, starfield, `.NCC` loading, `loadpv`, `drawpv` **dispatch** | byte-exact; **pixels deliberately out of scope** |
| 7a | `surface()` — the orbital globe texture | three-way, 10 captures + 14 synthetics |
| 7b | `build_surface()`, `SURFACE.BIN`, ground terrain | 604/604 three-way |
| 8 | the 22-phase main loop, flight, nav, saves | `CURRENT.BIN` round-trip byte-exact |
| 9 | full-game integration driver — `work/game.txt` | runs, flies, renders |

The suite is `python tests\run_all.py`; treat it as an explicit deep or release audit, not a
routine gate. Ordinary Stardrifter work uses one focused smoke/regression check and a lean
verification budget. Run the full roster only when the change warrants it; keep its roster
registration current as a coordination convention.

## Known state of `work/game.txt` (Wave 9's driver)

Two things a new agent will otherwise waste time rediscovering:

1. **The "freeze" is not a bug.** `GM flight init` seeds the approach target to the origin,
   so the vimana cascade flies the ship there and parks it — `MgStatus` 4 → 2, power draw
   collapses, `dzat_x` decays exponentially. Since the camera is `viewtile = dzat>>14`, a
   parked ship means a static picture. Measured: 30 fps throughout, 97% CPU, flat memory,
   ESC responsive. Nothing is hung.
2. **The terrain texture is a procedural formula, not the planet.** `PGtexf = 1` with
   `SPsrc = 1` derives per-pixel UV from projected position; it does not sample
   `p_surfacemap`. The *previous* commit was more faithful — `shade = surf[h1] & 31` reads
   the real heightmap — and had a wider 17×17 grid.

---

# PART 2 — THE WAVE

## The target

`void vehicle (float opencapcount)` — **`NOCTIS.CPP:753-1139`**, about 390 lines. This is
the first screen. The main loop opens on its state (`NOCTIS.CPP:2268`): `pos_y`, `lifter`,
`ontheroof`, `user_alfa`, `step` — the "terrazza panoramica", the roof of the Stardrifter.

Player state lives in `NOCTIS-0.H:124-128`: `pos_x`, `pos_y`, `pos_z`, `user_alfa`,
`user_beta`.

## The geometry is already here and already graded

The Stardrifter model is **not** a separate asset to hunt down:

- `loadpv(vehicle_handle, vehicle_ncc, 15,15,15, 0,0,0, 0, 1)` — `NOCTIS.CPP:2180`
- `vehicle_ncc = -35782` (`NOCTIS-D.H:107`) is a virtual position counted **back from the
  end** of `SUPPORTS.NCT`, whose length is 60,776 bytes (`off_digimap2 = -60776`). So the
  model sits at offset **24,994**, and runs to 30,796 — **5,802 bytes**.
- Already extracted to **`work/vehicle.ncc`**.
- Already loaded by the port's `loadpv` and graded **bit for bit**: `tests/test_spheres.py`
  L13, "loadpv's post-scale binary32 arrays for VEHICLE".

**Keep VEHICLE in any corpus you build.** Its triangles carry uninitialised garbage in the
fourth vertex slot — 150 of 156 components non-zero, 26 exceeding 1e6, two not finite, the
largest finite one 2.99e38, one multiply from infinity. `loadpv` zeroes those slots *before*
the scale-and-move pass; swap the order and infinities propagate through the midpoints and
the depth sort. BIRDY cannot expose this (its garbage maxes at 20.0), so a corpus without
VEHICLE grades that zeroing pass **vacuously**.

## What `vehicle()` needs, and what we have

Counted over `NOCTIS.CPP:753-1139`:

| dependency | calls | state |
|---|---|---|
| `poly3d` | 6 | ✅ Wave 6a, byte-exact |
| `polymap` | — | ✅ Wave 6a, byte-exact |
| `digit_at` | 3 | ✅ Wave 5 |
| `change_angle_of_view` | 2 | ✅ Wave 7b, graded |
| `drawpv` | 2 | ⚠️ **dispatch only — no pixels** |
| `polycupola` | 5 | ❌ not ported |
| `cupola` | 5 | ❌ not ported |
| `stick3d` | 4 | ❌ not ported |
| 2-D `Stick` + `fline` | opening path | ❌ not ported |
| `randomic_mapper` | hull, mode 2 | ❌ not ported; deterministic recursion |
| `alogena` + `lens_flares_for` | 1 + startup flare | ❌ not ported; startup-reachable |
| `setfx` / `resetfx` | 7 / 7 | ❌ not ported (small — swaps a control variable, `NOCTIS-0.CPP:1541-1543`) |
| `change_txm_repeating_mode` | 2 | ❌ not ported |

## The one genuinely hard part

Wave 6b stopped `drawpv` deliberately, and said so in `work/spncc.txt`:

> *"drawpv MODE 2 (randomic_mapper) IS OUT OF SCOPE, and so — as a declared deviation from
> the wave plan — are modes 0 and 1's PIXELS. This file emits the DISPATCH: the polygon
> order, the vertex base index, the vertex count, the colour and, for mode 1, the mangled
> colour. Routing the dispatch into Wave 6a's poly3d and polymap would make the graded
> artifact a joint product of two waves, so that a page difference could not be attributed."*

That was the right implementation boundary for verification and it is now the obstacle.
However, the durable test never completed the claimed dispatch grade: DRAW is explicitly
ungraded and CALL records are not compared. **Building a real dispatch oracle and then
joining dispatch to the rasteriser are this wave's central tasks**, and they inherit the
exact attribution problem 6b was avoiding: once pixels are involved, a wrong page could
come from dispatch, raster replay, or shared join state.

**Solve attribution before writing the join, not after.** The suggested approach: grade the
dispatch and the pixels *separately* — assert the dispatch list still matches 6b's graded
output exactly (it must not change), then grade the page given that dispatch as input. If
both hold, a page difference is attributable to the join alone. Do not proceed by rendering
and eyeballing.

The Phase 0 exterior probe uses **mode 0** (`drawpv(vehicle_handle, 0, 0, …)` at
`NOCTIS.CPP:1157`, in `other_vehicle_at`). The authentic interior uses **mode 2** with two
iterations, or three while depolarized. `randomic_mapper` is deterministic four-child
triangle subdivision with fixed colour offsets; it is required Wave 10 scope.

## Proposed phases

**Phase 0 — the cheap probe, do this first.** First establish the D/R/J attribution gates,
then wire mode-0 dispatch to the rasteriser for a single static frame of the hull from
*outside*, no camera trace, no loop, and dump raw page + PNG. The fixed fixture loads
VEHICLE at scale `(15,15,15)`, moves it to `z=12000`, uses identity camera/angles, and
expects 116 dispatch rows. The raw 64,000-byte page is graded; recognisability and PNG are
demonstration only. Phase 0 proves the join seam, not the opening renderer.

**Phase 1 — mode 2 and missing primitives.** `randomic_mapper`, the complete 2-D `Stick`,
`stick3d`, `fline`, `cupola`, `polycupola`, `setfx`/`resetfx`,
`change_txm_repeating_mode`, `alogena`, and the startup `lens_flares_for` path. Each gets
call/leaf traces before pixels and three-way treatment: lino == Python spec == C reference,
with deliberately broken variants that must fail. VEHICLE must emit exactly 720 leaves at
iteration 2 and 2,880 at iteration 3.

**Phase 2 — the interior camera.** Trace `pos_x/y/z`, `user_alfa/beta`, `lifter`,
`ontheroof` to their startup values and reproduce the opening eye position. The fixed offsets
in `vehicle()` (`cam_x -= 3395`, `cam_y += 480`, `cam_z += 200`, `cam_z -= 2*54*15`,
`cam_z += 3100`) are part of this and are exact constants, not tuning knobs.

**Phase 3 — assemble `vehicle()`** in its real order, including the `opencapcount` branch
and the `ontheroof` branch.

**Phase 4 — drive it from the game loop**, replacing `GM render ground` in a *copy* of
`game.txt`. Do not edit `work/game.txt` until a picture is worth showing.

## Frozen execution contract

Wave-owned production files are `work/vhmem.txt` (shared contracts/state),
`vhjoin.txt` (dispatch replay and D/R/J taps), `vhrmap.txt` (mode 2), `vhstick.txt`
(`Stick`/`stick3d`/`fline`), `vhcupola.txt`, `vhlight.txt` (`alogena` and startup flare),
`vhvehicle.txt`, `vhprobe.txt`, and `game-vh.txt`. Corpora are split into
`vh-corpus.txt`, `vh-mode2-corpus.txt`, and `vh-primitive-corpus.txt`. Independent oracles
are `noctis-harness/vh_spec.py` and `vh_ref.c`; the durable test is
`tests/test_vehicle.py`.

Keep Wave 6b's eight-unit dispatch row unchanged:

```
p, c, 4*c, nrv[c], raw_color, mangled_color, nrv[p], mode
```

Mode 2 adds a VH-owned leaf trace immediately before rasterization: sequence, source
polygon, quad half, recursion path, effective color, `nrv=3`, and the nine binary32 XYZ
vertex patterns. `VH join` consumes post-load arena values through `SP getf32`, transfers
their exact patterns with `PGF setf32`, and calls PG only after tracing. Do not add raster
calls inside `SP drawpv`.

Disjoint implementer ownership after the Wave 9 gate:

- **J — join/attribution:** `vhjoin.txt`, `vhprobe.txt`, `vh-corpus.txt`.
- **M — mode 2:** `vhrmap.txt`, `vh-mode2-corpus.txt`.
- **I — primitives/interior:** `vhstick.txt`, `vhcupola.txt`, `vhlight.txt`,
  `vhvehicle.txt`, `vh-primitive-corpus.txt`.

No package edits SP/PG libraries or another package's VH files. Phase 0 proceeds when the
focused D/R/J checks pass. Isolated mutation checks are optional deep evidence for a risky
oracle change. Interior integration
additionally requires mode-2 iterations 2/3, every startup primitive, the clean-start state,
and `alogena`'s reachable flare path to pass.

## Delivery workflow

Reconnaissance is complete. Use one owner and a direct delivery loop: implement a complete
visible slice, run one relevant seam check, integrate it into the game copy, and continue.
There is no standing recon/architect/reviewer/QA/test-writer pipeline.

Namespace convention is a two-letter prefix per wave: `pg` rasterisers, `sp` spheres, `fb`
framebuffer, `ns` star systems, `su` surfaces, `gr` ground, `mg` main loop. **Wave 10 owns
`vh`** — `work/vh*.txt`, `noctis-harness/vh_*.py`, `tests/test_vehicle.py`.

Keep `tests/run_all.py` registration coordinated when adding a test. Routine work does not
need to run or modify the full roster; use it for explicit deep/release audits.

## Risks, stated up front

- **Attribution** (above) is the main one. It is a design problem, not a coding problem.
- **`opencapcount` and `ontheroof`** are branch state. Clean startup is now traced rather
  than presumed: both are zero before the opening render. Separate roof/capsule fixtures
  are still required because `vehicle()` has 57 conditionals and a wrong branch can look
  plausible.
- **`_open`/`_close` inside `vehicle()`** read `..\DATA\GOESfile.TXT`. It is absent from the
  checked reference tree; open failure leaves the zeroed screen blank and does not block
  clean startup. Interactive/file-present branches remain separate fixtures.
- **Mode 2 `randomic_mapper`** is settled required scope: deterministic subdivision with
  720 VEHICLE leaves at iteration 2 and 2,880 at iteration 3. Phase 0 mode 0 does not prove
  it.
- **The oracle is weak here.** There is no 1996 artifact for this screen on this machine.
  Grading will be three-way internal consistency, which is the weakest tier. Say so in the
  wave document; do not let "byte-exact" stand unqualified.

## Definition of done

The port starts, and you are standing inside the Stardrifter. `tests/test_vehicle.py` grades
it, the NOT-GRADED list is explicit, and the relevant smoke/regression check passes with the
relevant PRISTINE hashes matching. A full-suite run and mutation campaign are optional
deep/release evidence, not routine completion gates.
The opening grade includes the startup-reachable `alogena` flare path. Exact pixel claims
are against the independent Python/C/Lino internal trio unless an external artifact is
named; no stock-1996 opening-frame capture exists on this machine.
