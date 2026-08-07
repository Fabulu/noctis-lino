# Wave 8 — the game: main loop, navigation, saves, console

Architect's consolidation of the three Wave 8 recons (main loop + flight; saves + starmap;
console + namespace). Written 2026-08-07. The recon transcripts are gone; the load-bearing
detail is here or in the file:line anchors the recons verified.

WAVEPLAN §8 is the parent spec. This file makes Wave 8's decisions concrete.

## Goal

The playable game: launch → target → fly (vimana/lithium) → land (Wave 7b) → walk → name →
save. One do-while main loop (NOCTIS.CPP:2268-4485), 22 phases per iteration. ESC-to-quit
gated by 4-clause continuation. Navigation via `isthere` (80-bit x87 window match). Saves via
CURRENT.BIN (381-byte NIV+) round-trip. Console via native GOES commands (CLR/DL/ST/PAR/naming).

## Task 0 — namespace refactor (FIRST, unblocks composition)

L.in.oleum has no linker namespacing. Today each wave links one collider per family; Wave 8
links them ALL. The exact collisions (verified by identifier-intersection):

**Family 1 — `SHfirst`/`SHn` (fbpal vs supal):** ONLY these 2 collide (supal already prefixes
its shade state SF*; shade() routines are already PAL shade / SU shade). Fix: fbpal→FBSHfirst/
FBSHn; supal→SUSHfirst/SUSHn.

**Family 2 — `OPEND`+`CR*` corpus-reader (subuf vs spmem vs pgmem — 3-way):** Each ships an
identical-shape reader. Fix: subuf→SU (SUOPEND/SUCR*/"SU CR *"); spmem→SP; pgmem→PG.

**Family 3 — `SD*`/`CS*`/`CORPUSMAX`/`TOKMAX` (cross-library):** The DANGEROUS one — CORPUSMAX
and TOKMAX have DIFFERENT VALUES in spmem vs pgmem (120000 vs 200000; 400000 vs 60000). This is
silent link-order-dependent corruption. Fix: prefix per library (SPCORPUSMAX/PGCORPUSMAX etc.).

Callers to update: ~50 files (fbpal-family, sumain+subrk*main, spmain, pgmain+pgbrk*main+
fragpage). The build LOUDLY catches any missed reference (unlike the silent CORPUSMAX/TOKMAX bug).

## Task 1 — main loop + flight + nav + input (impl A)

The 22-phase do-while. Key elements:
- `dzat_x/y/z` as **double** (24-bit float can't represent ~3.8e6; ULP=0.25). Plus the
  landing roundtrip degradation (float backup_dzat_x, deliberate — preserve not optimise).
- Vimana/approach coefficient integrator (low-pass filter on l_dsd, 5 phases each).
- `pwr` signed 16-bit with +15000 bias (live threshold ~15 sites). `charge` signed (<0=OMEGA).
- Input: ASCII FIFO + extended codes mapped to lino's LUCK held-key table.
- **5 exact-required float sites** (via the Wave 3 float engine): sector-crossing chop
  `(dzat-k)/100000` toward zero, `isthere`'s 80-bit identity + window compare,
  `search_id_code`'s window, `nearstar_identity`, `ap_target_id == nearstar_identity`.
- Smooth motion (vimana integrator) tolerant vs C oracle. **No LR divergence in flight** (confirmed).

## Task 2 — saves + starmap + console (impl B)

- **CURRENT.BIN 381-byte NIV+ R2.3**: 245-byte stock prefix (the `&sync` block, field-by-field
  in recon #2) + 136-byte NIV+ extension. `freeze()`/`unfreeze()` with **hidden evolution**
  (lithium recharge, consumi supplementari, OMEGA-in-recharge trap — replicate verbatim).
- **SURFACE.BIN 40-byte** (the >>14 atl_x/z quotient + remainders, write-once 8192).
- **STARMAP.BIN**: 1,202,500 bytes, 37,578 × 32-byte records. Append (seek END, tombstones
  skipped). The two malformed records (#3876 WESTOS=-0.0, #34754 MDIR 17=byte-reversed NaN)
  **rejected** from the key set, **not zeroed**.
- **GOES console**: CLR resident inline; DL/ST/PAR/naming reimplemented natively (can't exec
  DOS modules); COMM.BIN protocol (2-byte local, 24-byte remote). Oracle: Wave 2 DL golden captures.

## Correctness oracles

1. **CURRENT.BIN round-trip** (DECISIVE): port's save loads in NOCTIS.EXE + vice versa.
   Field-by-field fuzz under DOSBox localises hidden semantics.
2. **DL golden captures** (Wave 2): the native DL command vs the 1996 captures.
3. **`isthere` via float engine**: the 80-bit identity + window compare, byte-exact.

## L.in.oleum file-I/O constraints

No SEEK_END (TEST for size first). Short reads silent (check Block Size after every read).
CWD ≠ exe dir (SET DIR). No open/close (each I/O a complete transaction). Underscores→spaces
(use \us in filenames).

## Impl split

- **Task 0**: namespace refactor (one agent, mechanical, ~50 files).
- **Impl A**: main loop + nav + HUD (work/main.txt, work/nav.txt, work/hud.txt).
- **Impl B**: saves + starmap + console (work/save.txt, work/starmap.txt, work/console.txt).
- **Namespace**: pg (game loop) + ns (navigation) + sv (saves) + cl (console).
