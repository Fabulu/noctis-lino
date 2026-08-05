# WAVEPLAN — Noctis IV in L.in.oleum, from here to playable

Consolidated wave sequence, written by the consolidating architect 2026-08-05
after the five-recon survey (distilled in `PORTPLAN.md`). This file is the
durable record; the recon transcripts are gone, so anything load-bearing found
during planning is written down here, not remembered.

## Hard rules — restate these verbatim into every spawned agent's prompt

- Never launch `main/compiler.exe` or `main/lib/gen/compiler114m.exe` directly.
  They are GUI-subsystem binaries that paint over the terminal and wait for a
  human. Build only via `C:\programmieren\linoleum\lino_build.ps1`.
- To run a compiled lino program, use the poll-and-kill pattern
  (`ProcessStartInfo` with `UseShellExecute=false`, poll for an output file
  newer than launch, then `Stop-Process`). Never start one and wait.
- Never modify anything under `main/`. Every hash in `PRISTINE.sha256` must
  keep matching — the licence position depends on it.
- Never `git push` or publish. Private until the original author grants
  permission.
- Paths must never contain `--` (the lino argument parser truncates on it and
  then blames the CPU pack).
- Additional standing traps: `"variables"` vs `"workspace"` semantics;
  underscores in lino string literals become spaces (use `\us` or hyphens);
  a lino program that fails still exits 0 — grade output files by mtime, never
  by exit code; delete the target file before every run.

**Gate before any wave:** `python tests\run_all.py` must pass 12/12 and every
`PRISTINE.sha256` hash must match. After any wave: same again.

**Pipeline shape per wave:** 3+ recons (parallel, read-only), 1 architect,
2+ implementers on disjoint file namespaces, 1 reviewer (adversarial, reads
files not reports), 1 QA (re-runs everything), 1 test writer (tests proven by
breaking the subject).

---

## 0. Facts verified during this planning session (not in PORTPLAN.md)

These were checked against the actual bytes on 2026-08-05; they are inputs to
the waves below and must not be re-derived from memory.

1. **`zrandom` takes `int`** (`NOCTIS-0.CPP:3987`:
   `float zrandom (int range) { return (random(range) - random(range)); }`).
   In Borland large model `int` is 16-bit. Therefore *inside* `zrandom` the
   arithmetic is **pure integer** (Borland's `random(num)` macro with an
   integer `num` is `(int)(((long)rand()*(num))/(RAND_MAX+1))` — all integer).
   Unknown 1 (double-kept-in-double) does **not** apply inside `zrandom`; it
   applies at the direct `random(float/double-expr)` sites:
   `NOCTIS-0.CPP:4089` (`random (300 * nearstar_ray)`), `:4092`
   (`random (nearstar_p_orb_seed[n] + 10*fabs(nearstar_p_orb_tilt[n]))`),
   `:4093` (`random (nearstar_p_orb_seed[n])`), and their moon-loop twins
   (`:4195` region), plus any others the W3 registry finds.
   The float→int16 conversion **at zrandom's call boundary**
   (e.g. `zrandom (10*nearstar_p_orb_seed[n])`) is its own quantisation site:
   Borland converts float→long via `__ftol` (chop) and the caller takes the
   low 16 bits — wraparound is defined behaviour and must be reproduced.
2. **Unknown 2 is settled by one function body.** `zrandom` is a real function
   compiled once, so the `random(r) - random(r)` evaluation order is fixed in
   its single compiled body — it does not vary per call site. Unknown 1 is a
   macro and must be read per call site.
3. **`seedval` call sites confirmed** (`NOCTIS-0.CPP:5380-5411`): products of
   4–6 mixed float/double factors (`1000000 * nearstar_ray * type * orient`,
   `2000000 * n * orb_seed * orb_tilt * orb_ecc * ...`), passed as `double`,
   then `fast_srand (seedval + 4112)` / `fast_srand (seedval * 10)` inside
   `surface()` (`:4784`, `:4811`). `global_surface_seed` confirmed at
   `NOCTIS-1.CPP:3671-3673`: `(p_ray + p_orb_ray + p_orb_orient) * 4112`
   assigned to `long` (chop via `__ftol`), then conditionally `++` under a
   `srand`/`random(5)`/latitude test at `:3675-3679`.
4. **NOCTIS.EXE is not overlaid** — no `FBOV` (VROOMM) signature in NOCTIS.EXE
   or DL.EXE. Plain MZ, header 608 paragraphs, load image starts at file
   offset 0x2600.
5. **rand() is uniquely locatable in NOCTIS.EXE.** The Borland LCG multiplier
   0x015A4E35's low half (`35 4E` little-endian) occurs at exactly **one**
   file offset: 15982 (0x3E6E). Function identification is anchored, not
   heuristic.
6. **Tooling on this machine:** python 3.14 with **capstone 5.0.7**, `gcc`
   (mingw64), `ndisasm`, **`nasm`** (can hand-build DOS .COM probes).
   **DOSBox is NOT installed** (neither dosbox nor dosbox-x on PATH).
7. **DL.EXE is an automatable oracle.** `DL.CPP:1077-1080`: the only gate is
   BIOS byte `0040h:0049h == 0x13` (video mode 13h) — and DOS video mode
   persists after a program exits, so a 6-byte `SETMODE.COM`
   (`B8 13 00 CD 10 C3`, buildable with nasm) run first in AUTOEXEC satisfies
   it. DL prints via `printf` (stdout), so `DL <NAME>:<RANGE> > DLOUT.TXT`
   captures a planet/moon dependencies listing non-interactively. `ST.EXE`
   (`settarget()`) writes the autopilot target into `Current.BIN` from the
   command line, which lets a scripted NOCTIS session start already targeted.
   DL/ST/PAR contain their own compiled copies of `prepare_nearstar`,
   `zrandom` and the LCG from near-identical source — DL.EXE (46 KB, no
   overlays) is a *smaller, cleaner disassembly subject* for the shared
   functions, cross-checked against NOCTIS.EXE itself.
8. **`starnop()` exists** (`NOCTIS-0.CPP:4047-4057`): planet-count estimate
   from star coords, `srand((long)x%10000*(long)y%10000*(long)z%10000)` then
   three `random()` draws — pure integer after the `(long)` chops. Same
   seeding expression in `prepare_nearstar` (`:4080`).

---

## 1. The two blocking unknowns — the experiment that settles them

Both gate all planetary geometry. Design principle: **the shipped binary is
the ground truth and it encodes both answers statically.** Running it is
confirmation, not the primary measurement.

### Experiment E1 — static binary archaeology (primary; runnable today, no installs)

**What gets run.** A Python rig (`noctis-harness/exe_disasm.py`) that:
1. Parses the MZ headers of `NOCTIS.EXE` and `DL.EXE` (no overlays — verified).
2. Anchors on the unique `35 4E` hit (offset 15982 in NOCTIS.EXE) and decodes
   outward with capstone `CS_MODE_16` to delimit `rand()` (prologue/epilogue,
   the full LCG: `seed = seed*0x015A4E35 + 1; return (seed>>16) & 0x7FFF`).
   Also record the constants actually in the binary — this is the empirical
   anchor for Wave 1's LCG, independent of both source trees.
3. Finds all call sites of `rand` (near/far call scan across the load image).
   `zrandom` is the function containing exactly two `rand` call clusters
   followed by a subtract and a float materialisation. Cross-identified in
   DL.EXE the same way; the two bodies must agree in shape (same compiler).
4. Locates `prepare_nearstar`'s first loop by its constant cloud (imul by 300,
   divide by 100, the 2000/500/5000 divisors, `fabs`, the 4112 constants for
   `surface`/`global_surface_seed` sites) and extracts annotated disassembly
   of every `random(FP-expr)` site, every `seedval` product, the
   `global_surface_seed` expression, and the `isthere` window compare.
5. Disassembles the RTL `__ftol` in the binary to confirm chop-mode conversion
   and the take-low-16-bits caller behaviour.

**What is observed, and what each outcome implies.**

*Unknown 1 — does `random(double-expr)` stay in double?* At the compiled site
of `NOCTIS-0.CPP:4089`:
- **Outcome A: x87 code** (`fild` of rand's result, `fmul` the float product,
  `fdiv` by 32768, then `__ftol`) → Borland's macro kept the argument in FP;
  the whole expression is extended-precision FP; **LR's int16-cast reading is
  wrong** and our implementation routes these sites through the float engine.
- **Outcome B: pure integer code** (a `__ftol` of `300*nearstar_ray` *before*
  the multiply, then integer `imul`/long-divide) → LR's reading is right and
  these sites reduce to exact integers with one chop-convert at the front.
- Each FP-argument site is read independently (macro = per-site expansion);
  the answer is recorded per site, not assumed uniform.

*Unknown 2 — `random(r) - random(r)` order?* In `zrandom`'s single body: which
`rand` call's (scaled) result is the minuend.
- **Outcome A: first-executed minus second-executed** → left-to-right;
  LR-compatible; implement in call order.
- **Outcome B: second minus first** → right-to-left; **every `zrandom` in LR
  is negated**; we implement draw-then-swap, and every planet tilt/radius LR
  produces is wrong in sign — LR is then disqualified as a geometry oracle
  even where its arithmetic is otherwise fine.

*Bonus deliverable, load-bearing for Wave 4:* the transcribed x87 instruction
schedules (exact `fld/fmul/fst` order and where values spill to 64-bit
memory) for the seed-feeding expressions. "80 bits across whole expressions"
is only reproducible if we copy the *actual* spill points, and the binary is
the only place they exist.

**Why this is not circular.** The subject is the shipped executable that
players ran for twenty years — the same artifact that wrote STARMAP.BIN. No
reference implementation is consulted for the answer; the two source trees are
used only to *find* the code, and two implementers decode independently
(capstone script vs `ndisasm` + manual anchors) and must agree.

**Failure mode & mitigation.** 16-bit segmented code with a stripped symbol
table can resist function delimiting. Mitigations, in order: the unique-LCG
anchor (already verified); DL.EXE as the smaller twin subject; constant-cloud
matching (300, 100, 2000, 4112, 32768.0 in the data segment); worst case, the
dynamic experiment E2 decides behaviourally between the 2×2 hypothesis grid.

### Experiment E2 — dynamic confirmation under DOSBox (secondary; needs one install)

**What I need:** DOSBox-X installed
(`winget install joncampbell123.dosbox-x`, or the portable zip — plain
DOSBox 0.74 is NOT acceptable untested: its FPU emulation holds host doubles,
53-bit, which is precisely the corruption we care about).

**Step 0 — FP fidelity probe, mandatory before trusting any capture.** A
nasm-built .COM that runs a chain discriminating PC=64 from PC=53 (a classic
double-rounding case, e.g. accumulating `1 + 2^-53 + 2^-64` products with
results stored to memory as doubles) and prints the raw hex. If the emulator
shows 53-bit intermediates, its captures are only valid for integer-driven
observables (planet counts, types, names), not geometry. Record the verdict in
this file.

**Step 1 — automated captures.** AUTOEXEC in dosbox-x.conf:
`SETMODE.COM` (mode 13h persists) → `DL <starname>:200 > DLOUT.TXT` → exit.
Repeat over a star sample (the 343-sector sweep stars plus the author's
hard-coded stars). DLOUT.TXT gives planet/moon listings — integer-random
driven, so they validate the Wave 1 LCG + draw-order plumbing end-to-end
against the real binary regardless of FP fidelity.

**Step 2 — geometry-sensitive capture.** `ST <starname>` writes the target
into Current.BIN; then a scripted NOCTIS session (DOSBox-X's AUTOTYPE for
keystroke injection; fallback: one 10-minute human session, which I hereby
request if AUTOTYPE proves unreliable) flies to a planet, lands, quits.
Harvest **SURFACE.BIN and CURRENT.BIN as byte-exact golden files** — these are
the dynamic oracles for Waves 7 and 8. One session per scenario type wanted;
even a single habitable-planet landing is worth a wave on its own, because it
is the only non-LR oracle for type-3 terrain.

**Outcome logic.** E1's static answer selects one cell of the 2×2 hypothesis
grid; a candidate implementation (Wave 4) must then reproduce E2's captures.
Agreement closes the loop. Disagreement means a spill-schedule divergence or
emulator FP infidelity — halt geometry work and investigate; do not tolerate
it away.

---

## 2. Float strategy, per subsystem

Ground rules from PORTPLAN.md stand: lino native floats are 24-bit-per-op and
are **forbidden anywhere a result is truncated or compared into a discrete
decision**. Three engines exist:

- **INT** — exact integer reduction (proven: galaxy hash, fast_random).
- **X87** — x87-by-fragment: ML fragments executing real x87 opcodes on the
  host (32-bit x86 process, x87 always present), `fldcw` to 0x133F (PC=64,
  round-nearest, exceptions masked — the original's exact control word) at
  every helper entry, operands in memory addressed via registers. Preferred
  engine for generation FP. Feasibility is Wave 3's first question.
- **SOFT** — soft-float in pure lino integer arithmetic (64-bit ints already
  proven). Both binary64 and the 80-bit extended ops the schedules need.
  Slow, portable, deterministic forever — the guaranteed fallback. Generation
  runs per-star/per-planet, so even 100× cost is invisible next to a 55 ms
  tick.

Per subsystem:

| Subsystem | Engine | Notes |
|---|---|---|
| galaxy hash, `fast_random`, Borland LCG, `random(int)` | INT | done / Wave 1; pure integer |
| `zrandom` core | INT | verified this session: `int` parameter → macro is all-integer inside |
| `zrandom` call-boundary float→int16 | chop-convert helper | `__ftol` chop + low-16 wrap; exact, cheap |
| `srand((long)x%10000*...)` seeding, `starnop` | INT | chop-converts of exactly-representable doubles, then integer |
| terrain noise / surface fractal | INT | byte ops driven by `fast_random` |
| `nearstar_identity`, `isthere` window compare | X87 (SOFT fallback) | ~5 correctly-rounded ops on exact integer inputs; single precision proven insufficient (window < 3 single ULPs at origin, 390× too narrow at start coords) |
| `prepare_nearstar` geometry chain | X87 (SOFT fallback) + schedule transcription | the E1-transcribed spill schedule is authoritative at every site feeding a seed |
| `seedval` products, `global_surface_seed` | X87/SOFT, **exact required** | one ULP = a different planet; no tolerance exists |
| `random(FP-expr)` sites | per E1 outcome | per-site answer recorded in the registry |
| ship position / navigation state (`dzat_*` etc.) | X87/SOFT | 24-bit cannot even represent position at 3.8e6 scale; position quantises into sector coords → galaxy hash inputs. Low frequency (few dozen ops/tick) |
| projection, texture mapping, sphere rendering | native lino floats | tolerance allowed; the 38 hand-`fistp` sites round-to-nearest = lino `=,` for free |
| rendering C-cast sites that feed state | chop-convert helper | registry decides which |
| audio mixing | INT | |

**Integer reduction goes further than first framed** — the zrandom-is-integer
finding moves the majority of `prepare_nearstar`'s draws out of FP entirely.
What genuinely cannot be reduced: the identity/isthere chain, the orbital
geometry accumulation (`key_radius` running sums in double), the seed
products, and ship position. All are low-frequency.

**The registry is a Wave 3 deliverable** (`docs-notes/FLOATPOLICY.md`): every
float→int cast and every float comparison that selects a branch, with
file:line, kind (C-cast chop / `fistp` nearest / compare), classification
(exact-required / tolerant), and engine assignment. The recon's registry died
with its transcript; it gets rebuilt from source by grep + read, and every
exact-required row must eventually be covered by a test.

---

## 3. The buffer model — one decision, applied everywhere

**Decision: one item per unit.** One byte of Noctis state per 32-bit lino
unit, values 0..255 in the low bits, no packing anywhere in working memory.

Justification: 4× memory on a ~643 KB working set is ~2.5 MB against a
measured successful 1 GB allocation; per-access cost beats shift/mask; every
index in ported code stays byte-count-identical to the original (no /4
arithmetic to get wrong); and under packing, every tolerated out-of-bounds
write would corrupt three innocent neighbours inside the same unit, turning
the original's harmless overruns into new bugs. Packing survives only at the
**disk boundary**: files stay byte-packed on disk, and a single pack/unpack
helper pair (`work/bytebuf.txt`) converts at every read/write. No other code
touches packed data, ever.

Byte semantics: store helpers mask with `AND 0xFF` so arithmetic carry-out
reproduces byte wraparound; sign-extension helpers for the int8 reads
(GLOBES.MAP (y,x) pairs sign-extend 8→16 — see PORTPLAN corrections table).

**Aliased buffers — made explicit, one by one.** Known aliases (each becomes a
row in `docs-notes/LINOBUF.md`, the Wave 5 conventions doc):
1. The 32,768-byte triple-purpose buffer (globe table / sea-horizon texture /
   pilot font at the tail) → **three separate buffers**; the original's
   "ground renderer overwrites it, reload maps on leaving a planet" behaviour
   becomes an explicit reload call, preserved because the reload is what
   resets state.
2. `p_surfacemap` read as both `char*` and `double*` (`search_id_code`,
   NOCTIS-0.CPP:4008-4009) → byte array + an assemble-double-from-8-bytes
   helper (the soft-float double is two units anyway).
3. `laststar_x/y/z` int32/double punning inside one basic block (sitecount
   trap 1) → explicit conversion sequence copied from the disassembly.
4. Framebuffer page aliasing (type 9 writes the offscreen page — vanilla
   behaviour, LR diverges) → explicit page buffers; reproduce the vanilla
   target.
5. Any further aliases found by the Wave 5 recons get added to LINOBUF.md
   before code is written against them.

**Tolerated out-of-bounds writes.** Deliverable: an OOB audit (Wave 5 recon)
enumerating every overrun site, seeded from the two buffers LR demonstrably
inflated as guard bands, then verified against the DOS source. Each buffer
gets an explicit named guard band sized by the audit, plus one canary unit
after the guard; a debug build checks canaries every tick and halts loudly.
Guard contents are part of observable behaviour only where the original later
*read* the overrun bytes — the audit must classify write-only vs read-back
overruns; read-back ones must land in the guard band deterministically.

---

## 4. The wave sequence

Ordered for risk reduction: Waves 2 and 3 can each invalidate everything
downstream, so they run before any geometry or rendering is built. Waves 1 and
2 are independent of each other (1 is near-zero-risk and feeds 2's dynamic
side). Every wave uses the full pipeline; sizes below say how the 2+
implementers split.

### Wave 1 — Borland LCG, exhaustively
- **Goal:** `rand` / `srand` / `random(int)` / the zrandom integer core in
  lino, bit-exact for all time.
- **Unblocks:** all 346 `random()` call sites; planet counts and types;
  interpretation of every E2 capture.
- **Deliverables:** `work/brtl.txt` (LCG + `random(int)` + zrandom-core with
  explicit draw-order parameter pending E1), oracle rigs in `noctis-harness/`,
  regression test in `tests/`.
- **Correctness:** exhaustive — `srand` takes 16 bits, so all 65,536 seeds ×
  fixed draw depth is a complete proof, not a sample. Three oracles, none
  derived from another: (a) exact-integer Python from the documented Borland
  RTL algorithm; (b) C compiled verbatim from LR's `brtl_rand`; (c) **the LCG
  constants read out of NOCTIS.EXE itself** (unique anchor at offset 15982) —
  (c) is what makes this non-circular: both source-derived oracles are checked
  against the shipped artifact's actual constants. Edge vectors: `num` = 0,
  negative, ≥32768; the int16 truncation of the macro's outer `(int)` cast.
- **Depends on:** nothing.
- **Stall mode:** essentially none; residual risk is misreading the macro's
  integer promotion rules — caught by oracle (b) disagreeing with (a).
- **Size:** impl A = lino library; impl B = oracles + vectors + the
  NOCTIS.EXE constant extraction. Small, fast wave.

### Wave 2 — Binary archaeology: run experiments E1 (and E2 step 0–1 if DOSBox-X gets installed)
- **Goal:** settle unknowns 1 and 2; transcribe the x87 schedules at every
  seed-feeding expression; confirm `__ftol` semantics; capture DL.EXE golden
  listings.
- **Unblocks:** all planetary geometry (Wave 4), the exact-site list for the
  float engine (Wave 3 registry cross-check), LR's status as a geometry
  oracle (possibly: disqualified).
- **Deliverables:** `noctis-harness/exe_disasm.py`, annotated disassembly
  extracts + findings in `docs-notes/BINARCH.md` (answers recorded per site),
  `SETMODE.COM` + probe COMs (nasm), DL golden captures if DOSBox-X is
  available, DOSBox-X FP-fidelity verdict.
- **Correctness:** the subject is the ground truth; non-circularity is
  independence of decoders — impl A (capstone rig) and impl B (ndisasm +
  manual anchor walk) must produce agreeing readings of `zrandom` and at least
  two `random(FP)` sites, and the DL.EXE twin bodies must agree in shape with
  NOCTIS.EXE's. The reviewer checks the readings against the source
  expressions line-by-line (structure must match; a mislocated function shows
  up as a structural mismatch).
- **Depends on:** nothing (Wave 1 helpful for interpreting DL captures).
- **Stall mode:** function delimiting resists automation → fall back to
  DL.EXE (smaller, same functions), constant-cloud anchors, and ultimately E2
  behavioural discrimination of the 2×2 grid. If DOSBox-X cannot be installed,
  E2 steps are deferred to Wave 7's precondition, and E1 alone decides.
- **Size:** impl A = capstone rig + extraction; impl B = independent decode +
  nasm probes + DOSBox-X setup/captures.

### Wave 3 — The float engine: x87-by-fragment probe, soft-float fallback, quantisation registry
- **Goal:** a callable double/extended arithmetic layer that reproduces
  Borland x87 chains, plus the complete quantisation-site registry.
- **Unblocks:** star identity, all generation FP, navigation state; converts
  PORTPLAN's "highest-leverage open question" into a settled yes/no.
- **Deliverables:** `work/x87frag.txt` (fldcw 0x133F, load/store double,
  chained add/sub/mul/div/`fabs`/compare, `__ftol`-chop and `fistp`-nearest
  converts), `work/softfp.txt` (binary64 + extended-64-mantissa ops in pure
  lino), probes for CW survival across isocalls and runtime clobbering,
  `docs-notes/FLOATPOLICY.md` (the registry: every float→int cast, every
  branch-selecting comparison, file:line, kind, classification, engine),
  tests.
- **Correctness, per engine:** (a) **STARMAP decode: 4194/4194** records must
  match under the engine's identity computation — the killer oracle: written
  by the real binary over twenty years, already proven to discriminate 80-bit
  from 64-bit arithmetic (4194 vs 2315). Not circular: the data predates this
  project and was produced by the artifact we are cloning. (b) A directed
  vector set including double-rounding traps, checked against a Python x87
  emulator (mpmath, PC=64 semantics, explicit store-rounding) AND against a
  gcc `-m32 -mfpmath=387` C harness executing the same chains on real x87 —
  two independent oracles of different construction. (c) X87 and SOFT engines
  must agree bit-for-bit on the full vector set (they are each other's
  cross-check; disagreement means one is wrong, the vectors say which).
- **Depends on:** Wave 2 only for the registry's per-site E1 answers (the
  engines themselves depend on nothing).
- **Stall mode:** the runtime resets/clobbers the x87 control word or stack
  between fragments → mitigation: re-`fldcw` at helper entry and keep each
  helper's x87 stack self-contained (open, compute, store, clear). If x87
  fragments are outright impossible, **the wave still succeeds via SOFT** —
  cost measured and acceptable at generation frequencies. This wave is
  designed to be un-stallable: its worst outcome is "preferred engine dead,
  fallback proven", which is still a definitive answer.
- **Size:** impl A = x87 fragment library + probes; impl B = soft-float;
  test-writer + one recon carry the registry.

### Wave 4 — Star identity and planetary system generation, bit-exact
- **Goal:** `nearstar_identity`, `isthere`'s window match, `starnop`, and the
  full `prepare_nearstar` — counts, types, owners, moons, and geometry
  (orb_seed, tilt, ecc, ray, orb_ray, ring) — exact.
- **Unblocks:** everything planetary: surfaces, landing, the playable game.
- **Deliverables:** `work/nearstar.txt` (+ split modules), oracle harness,
  tests over a star corpus.
- **Correctness, layered:** (1) integer layer (counts, types, owners) against
  a C oracle from niv-plus source with the E1-resolved semantics, and against
  **DL.EXE golden listings** captured in Wave 2 — the listings come from the
  shipped binary, closing the loop non-circularly; (2) geometry layer against
  a replay harness: a gcc `-m32` program executing the **E1-transcribed x87
  schedules instruction-for-instruction** (not gcc's own compilation of the
  expressions — gcc's spill points differ from Borland's, which is exactly
  the error this construction avoids); (3) identity layer against STARMAP
  planet records (type 'P'): player-named planets must be found by
  `search_id_code` at the right positions. LR is used only where E1 confirmed
  its reading; if E1 outcome B2 (negated zrandom) holds, LR geometry is not
  consulted at all.
- **Depends on:** Waves 1, 2, 3.
- **Stall mode:** residual divergence at a spill point the transcription
  missed → the harness reports the first diverging planet field per star;
  return to the binary for that one expression. Quantify divergence rate over
  the corpus rather than hand-waving; do not proceed to Wave 7 above 0.
- **Size:** impl A = identity/isthere/starnop + integer extraction; impl B =
  geometry chain + replay harness.

### Wave 5 — Framebuffer shell: buffer model, tick, input, 2D layer, assets
- **Goal:** the game's skeleton — 320×200 exclusive mode, palette expand,
  54.9254 ms accumulated tick, LUCK held-key input + console FIFO, one-per-
  unit byte buffers with guards, plain-file asset loading, 2D primitives and
  the pilot font drawing on screen.
- **Unblocks:** every rendering wave; first pixels a human can judge.
- **Deliverables:** `docs-notes/LINOBUF.md` (buffer conventions, alias
  registry, OOB audit), `work/bytebuf.txt`, `work/fb.txt` (mode, palette,
  tick, input), `work/prim2d.txt` (lines, boxes, blits, lssmooth, text),
  asset loader (`supports.nct` member extraction to plain files at install
  time, `SET DIR` handling, TEST-then-read since no SEEK_END), canary debug
  build, tests.
- **Correctness:** primitives graded by **buffer dump, not screenshot** —
  render into the byte buffer, write it to a file, byte-compare against a C
  oracle reimplemented from the niv-plus *assembly* (reviewer checks the C
  against the asm line-by-line; LR is cross-read but its `lssmooth`
  one-pixel divergence is a known wrong answer the test must reject —
  deliberately implement the LR variant once and require the test to catch
  it). Font/glyph rendering additionally eyeballed against DOSBox screenshots
  when available. Tick and input re-verified with the Wave-5 probes (numbers
  already measured; the wave re-runs them inside the real shell).
- **Depends on:** nothing upstream except the standing toolchain (can run in
  parallel with Wave 4 if pipeline capacity allows — disjoint namespaces).
- **Stall mode:** exclusive-mode/palette surprises inside a long-running loop
  (measured probes were short) → mitigation: soak test early in the wave; if
  exclusive mode is flaky, windowed 320×200 scaled is an acceptable fallback
  rendering target, decided by measurement.
- **Size:** impl A = fb/tick/input/palette; impl B = bytebuf + primitives +
  asset pipeline.

### Wave 6 — 3D pipeline and spheres
- **Goal:** projection, `poly3d`/`polymap`, .NCC model loading (VEHICLE,
  MAMMAL, BIRDY), `globe()`/`glowinglobe`/`white_globe`/`white_sun` with the
  shipped GLOBES.MAP, `background()` with the offsets map, the baked lighting
  band.
- **Unblocks:** star system view, stardrifter, planet approach — the visible
  game.
- **Deliverables:** `work/proj.txt`, `work/poly.txt`, `work/globe.txt`,
  `work/ncc.txt` (zeroing the garbage fourth vertex slot before transform),
  tests.
- **Correctness:** rasterisers are integer-exact once vertices are fixed:
  feed pinned integer vertices and byte-compare buffer dumps against the
  C-from-asm oracle (same method as Wave 5). Projection is float-tolerant
  (native floats; `=,` reproduces the 38 `fistp` sites) — graded within a
  ±1px envelope against the oracle, except registry-flagged sites which are
  exact. Sphere geometry anchored by the recovered GLOBES.MAP formula (RMS
  0.47 px) — ship the table, use the formula as the test's independent
  predictor. Traps under explicit test: `globe()`'s misnamed `offsetsmap`
  parameter wired to the *globes* map; the four globe variants' clip
  rectangles per vanilla (LR's parameterisation divergence is a known wrong
  answer); `wave()`'s `+4` offset resolved from the binary (Wave 2 rig
  reused) rather than from LR.
- **Depends on:** Wave 5 (buffers, fb); Wave 4 not required for pinned-vertex
  testing.
- **Stall mode:** tolerance comparisons flap → tighten by splitting the test:
  exact rasteriser given exact vertices, separately-bounded projection error.
  If `wave()`'s allocator-dependent offset cannot be settled from the binary,
  grade gas-giant textures against DOSBox screenshots and accept the visually
  matching reading, documented.
- **Size:** impl A = projection + rasterisers; impl B = loaders + globes +
  background.

### Wave 7 — Planet surfaces and landing
- **Goal:** `surface()` (seed chain exact), terrain generation per scenario
  type with vanilla add-semantics for type-3 noise, `build_surface`, sky,
  SURFACE.BIN write/read, walking on the ground.
- **Unblocks:** the core of the game — being a stardrifter on a planet.
- **Deliverables:** `work/surface.txt`, `work/terrain.txt`, `work/ground.txt`,
  golden SURFACE.BIN comparisons, tests.
- **Correctness:** **LR is disqualified here** (type-3 assign-vs-add, type-9
  page target — both confirmed divergences). Oracles: (a) C oracle compiled
  from **niv-plus source** with E1 semantics, reviewed against the binary's
  schedule at the seed sites; (b) the E2 dynamic captures: byte-exact
  SURFACE.BIN from a real DOSBox-X landing (precondition: DOSBox-X installed
  + FP-fidelity probe passed + one scripted or human session per scenario
  type). SURFACE.BIN as a file-compare is the strongest oracle in the entire
  plan: 40/45 bytes written by the real binary at a reproducible landing
  site. NIV+ writes 40 bytes vs stock 45 — we grade against the binary we
  actually run, NIV+ R2.3, and record the layout choice.
- **Depends on:** Waves 3, 4 (seeds), 5 (buffers), 6 (globe textures feed
  approach view); E2 step 2.
- **Stall mode:** no dynamic capture possible (DOSBox-X blocked or FP-infidel)
  → the wave proceeds on oracle (a) alone but its exit report must say so,
  and the port carries a "type-3 terrain unvalidated against hardware" flag
  until a capture exists. This is the wave most likely to need the human's
  ten minutes; ask for it early, not at the end.
- **Size:** impl A = surface/seed/terrain generation; impl B = ground
  renderer + sky + SURFACE.BIN I/O.

### Wave 8 — The game: main loop, navigation, saves, console
- **Goal:** flight (vimana/lithium/pwr), HUD and menus, CURRENT.BIN
  save/load, starmap lookup/append, the onboard console with a native subset
  of the GOES commands, ESC quit.
- **Unblocks:** a playable loop: launch → target → fly → land → walk → name →
  save.
- **Deliverables:** `work/main.txt`, `work/nav.txt`, `work/hud.txt`,
  `work/save.txt`, `work/console.txt`, tests.
- **Correctness:** the decisive test is the **save-file round trip with the
  real binary**: a CURRENT.BIN written by our port must load in NOCTIS.EXE
  under DOSBox-X and vice versa (381-byte NIV+ layout — the binary we
  validate against is NIV+ R2.3). Not circular: the other side of the trip is
  the shipped executable. Field semantics under explicit test: `pwr` stored
  biased +15000 (live threshold in ~12 places), `charge < 0` preserved as the
  OMEGA cheat, `atl_x/atl_z` stored as the `>>14` quotient. Starmap append
  must reject (not zero) the two malformed records. Navigation dynamics:
  discrete decisions (sector crossings, target acquisition via `isthere`)
  exact via the float engine; smooth motion tolerant vs a C oracle
  cross-checked niv-plus↔LR (flight code has no known LR divergence — recon
  confirms before trusting). Console commands are reimplemented natively
  (the port cannot exec DOS modules); scope = the in-game-essential set:
  target listing (DL-equivalent), set-target (ST), parameters (PAR), naming.
  Graded against the Wave 2 DL golden captures.
- **Depends on:** everything above.
- **Stall mode:** hidden CURRENT.BIN field semantics → round-trip testing
  localises them field-by-field (fuzz one field, observe the binary's
  reaction under DOSBox). Scope creep in the console → the essential-set list
  is fixed by the architect at wave start; everything else is Wave 9+.
- **Size:** impl A = main loop + nav + HUD; impl B = save/starmap/console.
  Possibly the wave to run twice (8a systems, 8b integration) if the reviewer
  finds it overloaded.

### Wave 9 — Audio and polish
- **Goal:** VOC sound effects through a software mixer (one loop buffer, live
  cursor, write-ahead each tick); final QA of playability; performance soak;
  regression consolidation.
- **Unblocks:** ship-shape.
- **Deliverables:** `work/mixer.txt`, VOC decode table, effect wiring,
  full-suite regression run, a PLAYTEST.md checklist executed by QA.
- **Correctness:** VOC decode graded against a Python reference decoder
  (checksum of PCM); mixer summing graded by rendered-buffer checksum against
  a Python mixer on the same inputs. In-game timing judged by ear + the tick
  soak (no oracle exists for "sounds right"; say so). Win32 only — the Linux
  runtime's PCM layer is a stub, recorded as a platform limitation, not a
  bug.
- **Depends on:** Wave 8.
- **Stall mode:** audio API behaviour under exclusive mode unknown →
  mitigation: probe first; audio is severable — the game ships silent rather
  than stalls.
- **Size:** impl A = mixer + VOC; impl B = wiring + polish backlog.

**Cross-wave notes.** Waves 4 and 5 are disjoint and can overlap if capacity
exists. The Wave 2 disassembly rig is reused in Waves 4, 6 (wave()+4), 7, 8.
The E2 DOSBox-X install pays off in Waves 2, 7, 8 — install it once, early;
its absence degrades three waves' oracles.

---

## 5. What is not reachable, and what stays uncertain

**Not in this port (plainly):**
- **The MIDI soundtrack.** No MIDI interface exists in the comm area; playing
  it would mean writing a General-MIDI softsynth. Out of scope. (A future
  option — out of scope and unpromised — is pre-rendering the module music to
  PCM and streaming it through the Wave 9 mixer.)
- **Audio on Linux.** The Linux runtime's PCM layer is a stub. Win32 only.
- **Graceful window close.** No close event exists in the runtime; ESC-to-quit
  is the only exit, as in LR.
- **GOES-Net as a network.** Inbox/outbox/inter-player modules are external
  DOS programs and a defunct online service; the port reimplements only the
  in-game-essential console commands natively.
- **Bit-exact rendering.** Not promised and not needed; rendering runs native
  floats within a pixel-level envelope. Bit-exactness is promised only where
  a value quantises into state (the registry's exact-required rows).
- **The seven .VOC files never referenced, the four never-loaded .NCC models,
  TEXT3D.H** — dead content, deliberately not ported.

**Genuinely uncertain (and who resolves it):**
- Whether x87-by-fragment survives the runtime's isocall/context behaviour —
  Wave 3 probes; SOFT fallback removes the schedule risk but not the answer.
- Whether Borland's spill schedule is fully captured at every seed expression
  — Wave 2 transcribes, Wave 4 measures residual divergence over a corpus;
  until that number is 0, planet geometry is "matches the binary except at N
  listed stars", honestly reported.
- DOSBox-X FP fidelity (80-bit intermediates) — gated by the Wave 2 probe; if
  it fails, dynamic geometry oracles are limited to integer observables and
  SURFACE.BIN captures lose authority for FP-sensitive scenario selection.
- Whether a fully automated landing capture is achievable (AUTOTYPE) — else
  one human DOSBox session per scenario type is required; requested in
  Wave 7.
- Stock-2003 vs NIV+ R2.3 behaviour outside the generation path — the only
  runnable binary is NIV+, so the port validates against NIV+ where they
  might differ (saves: 381 bytes; SURFACE.BIN: 40 bytes) and records each
  choice. Claiming fidelity to the pristine 2003 build everywhere would be
  unsupported.
- Whole-game feel (pacing under exclusive mode, input latency over hours) —
  measured components all pass; the integrated soak happens in Waves 8–9 and
  no earlier evidence fully de-risks it.
