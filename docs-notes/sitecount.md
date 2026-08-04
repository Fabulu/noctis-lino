# Multiply-site inventory for the Noctis IV port

The inventory is reconnaissance; everything from "Three interchangeable
backends" onwards is compiled, run and checked against external references.
Regenerate with:

    python noctis-harness/sitecount_scan.py      # the inventory below
    python noctis-harness/sitecount_scan.py --check   # census as a regression test
    python noctis-harness/sitecount_verify.py    # the three claims below
    python noctis-harness/sitecount_ctypes.py    # scale of the C-level multiplies
    python noctis-harness/sitecount_rndoracle.py # the two fast_random oracles
    python noctis-harness/sitecount_vectors.py   # the operand table
    python noctis-harness/sitecount_cmp.py       # nine builds, the whole grid

`sitecount_cmp.py` is the one that matters: it builds every program under every
backend, runs each with the poll-and-kill launcher in `sitecount_run.py`, and
exits non-zero if any two disagree or if any drifts from its external anchor.

Sources: `C:\programmieren\noctis\niv-plus\source` (DOS original),
cross-checked against `C:\programmieren\noctis\niv-lr\src` (de-assembled C++).

## Scope: what actually links into the game

`NOCTIS.MAK` builds NOCTIS.EXE from exactly three translation units --
`noctis-0.cpp`, `noctis-1.cpp`, `noctis.cpp` (the `.H` files are `#include`d into
them). `DL.CPP`, `PAR.CPP`, `SL.CPP`, `ST.CPP`, `CAST/CAT/WHERE/...` are separate
GOES-Net utility EXEs. niv-lr agrees: it keeps `goesnet/` and dumps the rest in
`Old/`. Their multiply sites are counted below but are not on the port's
critical path.

Compiler config (`NOCTIS.MAK` writes `noctis.cfg`): `-ml -3 -f287 -O -Oe -Ob`.
`-3` means the C compiler may itself emit 32-bit `imul`; that is always the
two-operand low-half form, because Borland C++ 3.1 has **no 64-bit integer
type** at all. `Qword`/`Uqword` exist in `defs.h:41-42` but only inside the
32-bit (modern-port) `#ifdef` branch, and are referenced nowhere.

## Inventory of assembly multiply sites (20 total, 12 in the game)

### (c) Genuine 32x32 -> 64, the high half is consumed

| file | line | function | operation |
|---|---|---|---|
| NOCTIS-0.CPP | 1093 | `fast_random` | `db 0x66; mul dx` = `mul edx`, unsigned |
| NOCTIS-0.CPP | 2835 | `sky` | `db 0x66; imul dx` = `imul edx`, signed |
| NOCTIS-0.CPP | 2846 | `sky` | `db 0x66; imul dx` |
| NOCTIS-0.CPP | 5673 | `isthere` | `db 0x66; imul dx` |
| NOCTIS-0.CPP | 5681 | `isthere` | `db 0x66; imul dx` |
| DL.CPP | 460, 468 | `isthere` | duplicate of the above (tool) |
| PAR.CPP | 398, 409 | `isthere` | duplicate (tool) |
| SL.CPP | 345, 353 | `isthere` | duplicate (tool) |
| ST.CPP | 458, 466 | `isthere` | duplicate (tool) |

Five in the game; thirteen counting the tools. But only **two distinct
algorithms**: the galaxy hash (`sky`/`isthere`, four sites plus eight copies) and
the `fast_random` PRNG (one site).

Corroborated independently: `niv-lr/src/noctis-0.cpp` contains exactly five
`int64_t`/`uint64_t` multiplies, at lines 834 (`fast_random`), 2390 and 2407
(`sky`), 5298 and 5311 (`isthere`). Nothing else in the whole de-assembled port
is 64-bit.

### (b) 32x32 -> 32, low half only

| file | line | function | note |
|---|---|---|---|
| NOCTIS-0.CPP | 2823 | `sky` | `db 0x66, 0x0F, 0xAF, 0xCA` = `imul ecx, edx` -- **dead code** |

`sky` computes `ecx = sect_y * sect_z` and then two instructions later executes
`db 0x66; mov cx, ax` (`mov ecx, eax`), destroying it. The intervening
`add eax, edx` also overwrites the flags, so nothing survives. niv-lr dropped the
instruction entirely (no `sect_y * sect_z` appears anywhere in its `sky`).

### (a) 16x16 -> 32, fits inside a native 32-bit multiply

| file | line | function | operation |
|---|---|---|---|
| NOCTIS-0.CPP | 4585 | `wave` | `mul dx` (dx=360); `dx` high half discarded |
| NOCTIS-0.CPP | 4823 | `surface` | `imul ax` then `add ax, dx` |
| NOCTIS-0.CPP | 4914 | `surface` | `imul ax` then `add ax, dx` |
| NOCTIS-0.CPP | 6054 | `load_starface` | `imul ax` then `add ax, dx` |
| NOCTIS-1.CPP | 1686 | `nebular_sky` | `imul ax` then `add ax, dx` |
| NOCTIS.CPP | 357 | `command` | `mul dx` (dx=27); high half discarded |

Four of these do use the high half (`dx`), but the whole product is 32 bits wide,
so a native signed `*` plus `> 16` reproduces it. Verified exhaustively.

### (d) x87 floating point -- a separate problem

354 `fmul`/`fimul`/`fmulp` mnemonics in assembly blocks (PITAGORA.H 146,
TDPOLYGS.H 135, NOCTIS-0.CPP 53, tools 20) plus roughly 2000 C-level float
multiplies. Unrelated to `*%`; L.in.oleum's `**` (MUL.f) covers the operation but
not the precision -- see traps.

### Negative results worth recording

* **No multiply is hidden as raw opcode bytes.** `sitecount_scan.py` decodes every
  literal `db` byte run looking for `F7 /4`, `F7 /5`, `0F AF`, `69`, `6B` with or
  without a `66` prefix. Across 263 `db 0x66` lines in TDPOLYGS.H, 170 in
  NOCTIS-0.CPP, 86 in PITAGORA.H and 27 in ASSEMBLY.H it finds **zero** extra
  sites; the byte-count scan and the mnemonic scan agree at 20. Grepping for the
  literal bytes confirms: `0xF7` and `0xAF` appear only at NOCTIS-0.CPP:2823, in
  `defs.h`, and once as an unrelated bitmask constant (PITAGORA.H:712). The whole
  3D rasteriser needs no widening multiply.
* **No 32-bit divide anywhere.** The only `div` sites are NOCTIS-0.CPP:1645/1650,
  TDPOLYGS.H:217/222 and ASSEMBLY.H:859, all 16-bit `div bx` / `div word ptr L`.
  The pre-existing `/%` split-divide that `*%` was modelled on is itself
  unnecessary for this port.
* **The `IMUL_EDX` / `IMUL_ECX_EDX` macros in `defs.h:155-156` and `254-255` are
  never used.** Every call site writes the `db` form out longhand.

## Verified claims

Output of `noctis-harness/sitecount_verify.py`:

    CLAIM A  16x16 PRNG: mismatches over 393216 cases = 0
             worst |product| = 1073741824, fits in 32 bits: True
    CLAIM B  fast_random: divergences in 200000 draws = 199995
             first divergence at draw 1 (ref=46877, low32only=46992)
             high-half bits consumed: 32..39 only (add al, dl is 8-bit)
    CLAIM C  pure-32-bit emulation over 300009 pairs: unsigned bad=0 signed bad=0
             cost: 4 multiplies + ~10 shift/and/add, no carry flag needed

A: the `imul ax` / `add ax,dx` idiom is exactly reproducible with a plain 32-bit
signed multiply, checked over all 65536 seeds for six values of `cx`.

B: `fast_random` really does need the high half. Dropping it diverges on the
second draw and stays wrong. It needs only bits 32..39, because `add al, dl` is
an 8-bit add with no carry out.

C: if `*%` were rejected, the 64-bit product is still reachable in pure
L.in.oleum via four 16-bit-limb products, each of which fits in 32 bits, with
carries propagated by explicit `> 16` -- no carry flag required.

## The fragment idiom was re-proven end to end, with the STOCK toolchain

`work/galaxy.txt` contains no `*%` -- it uses only `{ F7 EB }`. Copied to
`work/sitecount_frag.txt` with its output redirected to `sitcnt.bin`, built with
the **unpatched** `main/compiler.exe` against the **stock** `i386` pack:

    powershell -File lino_build.ps1 -Src ...\work\sitecount_frag.txt -Cpu i386
    OK  C:\programmieren\linoleum\work\sitecount_frag.exe  19424 bytes  1.5s

and run under the poll-and-kill pattern, `sitcnt.bin` is SHA-256 identical to the
known-good `galaxy.bin` (6860 bytes, `CCA439690014C864...`). So the only
non-negotiable 64-bit algorithm in the game is already solved without any
language extension, using the stock compiler and stock CPU pack.

## Three interchangeable backends, one interface

The three ways to get a 64-bit product were turned into three files exporting
the same two entry points, so choosing between them is a one-line change and
the port commits to none of them:

    "Mul64u"   in [m64a],[m64b] -> out [m64lo],[m64hi]   unsigned 32x32 -> 64
    "Mul64s"   same shape, signed
                                  both destroy A, B, C, D

Operands go through memory rather than registers because `mul64frag` clobbers
`D` invisibly to the compiler and `mul64limb` needs more scratch than there are
registers. The two entry points are deliberately separate rather than one
routine with a sign flag: **`sky`/`isthere` are IMUL, `fast_random` is MUL**,
and one shared routine that guessed wrong would build a complete, plausible,
entirely wrong universe with no diagnostic anywhere.

| file | mechanism | non-comment lines | compiler | `-Cpu` |
|---|---|---|---|---|
| `work/mul64frag.txt` | `{ F7 E3 }` / `{ F7 EB }` | 24 | stock `main\compiler.exe` | `i386` |
| `work/mul64limb.txt` | four 16-bit limbs, pure L.in.oleum | 44 | stock `main\compiler.exe` | `i386` |
| `work/mul64star.txt` | `*%` / `*%'` | 20 | `compiler114m.exe` | `i386m` |

A program names `mul64be` in its `"libraries"` period;
`sitecount_run.select_backend()` copies one of the three into
`work/mul64be.txt`. The compiler resolves a relative library name against the
source directory first, so nothing else in the program changes between builds.

Exact toolchain identities, so a reader can see per row that no extension was
involved in the two stock columns:

    main\compiler.exe             136774 bytes  SHA-256 390B909BAE1077DCBD20AD477BEF0241FBE57B6D3A3BDCD0651D9BA8090A5A88
    main\cpu\i386.bin             299576 bytes  SHA-256 26714BDE27CC6C3D91B6BE3A19E59F3EF8C856B942B08252D88034CCE367786E
    main\lib\gen\compiler114m.exe  63968 bytes  SHA-256 14090F2EC40A3B806156B90FE89D5E5134F21F98A5198D316DE81EC9C0C69182
    main\cpu\i386m.bin            311192 bytes  SHA-256 E6C171616EC8138D1AEAA737470EC84E55DF3E4461B5B864C887D40E5C816966

`PRISTINE.sha256` re-verified after all builds: 6/6 files unchanged.

## The primitives were pinned before anything was built on them

`work/sitecount_shifts.txt` runs first, because the limb backend is wrong in a
way that only shows on negative operands if `>` and `>>` are the other way
round. Actual output of `work/sitecount-shifts.bin`:

    minus 1 >  31   (SHR, zero fill)   =            1  expect            1  ok
    minus 1 >> 31   (SAR, sign fill)   =           -1  expect           -1  ok
    minus 1 >  16   (limb split)       =        65535  expect        65535  ok
    65535 '* 65535  (MUL.n on limbs)   =      -131071  expect      -131071  ok
    (1<<31) >  31   (SHR)              =            1  expect            1  ok
    (1<<31) >> 31   (SAR)              =           -1  expect           -1  ok
    sentA[0] after writing 111         =          111  expect          111  ok
    sentB[0] after writing 222         =          222  expect          222  ok

The last two are the `"workspace"` aliasing sentinel: two separately declared
vectors, two distinct writes, read back distinct.

## fast_random is now ported, and pinned by two independent oracles

This is the half of category (c) that had never been written in any language.
`work/sitecount_rnd.txt` implements `fast_srand` and `fast_random` over the
shared interface. It is checked against two oracles that are not derived from
each other:

* `noctis-harness/sitecount_rndoracle.py` -- written from the DOS assembly at
  `NOCTIS-0.CPP:1086-1101`, in Python exact integers, so there is no 64-bit
  truncation to get wrong.
* `noctis-harness/sitecount_rndoracle.c` -- `fast_srand`/`fast_random` copied
  **verbatim** from `niv-lr/src/noctis-0.cpp:822-845`, a different author's
  independent de-assembly. Built `gcc -O2 -fwrapv` (the copied lines overflow
  a signed `int32_t` seed on purpose; `-fwrapv` makes C agree with a 32-bit
  register add without touching them).

The two oracles agree on 4096/4096 draws, and only then were the Lino builds
compared. Human-checkable golden vector, `fast_srand(12345)`, mask `0FFFFh`,
first 16 draws:

    11673 46877 35395 41614  6091 22323 36880 43493
    25490 22381 34338 38609 34996 29267 25289 63327

Draw 1 is 46877, which is the value CLAIM B above reports as the point where a
low-32-only multiply first diverges -- so a wrong fold is visible in the first
row of this vector.

## Results: nine builds, three columns, one answer

Actual output of `python noctis-harness/sitecount_cmp.py` (exit 0):

    BUILDING (3 backends x 3 programs = 9 builds)
      built and ran all 3 programs under frag  (compiler.exe, -Cpu i386)
      built and ran all 3 programs under limb  (compiler.exe, -Cpu i386)
      built and ran all 3 programs under star  (compiler114m.exe, -Cpu i386m)

    SHA-256 GRID (every column must be identical down its row)
      output                   frag (stock)       limb (stock)       *% (patched)
      sitecount-mul64.bin      87CBF6E370FC2DF9   87CBF6E370FC2DF9   87CBF6E370FC2DF9
      sitecount-rnd.bin        F18ACE3A73A7C6C5   F18ACE3A73A7C6C5   F18ACE3A73A7C6C5
      sitecount-galaxy2.bin    CCA439690014C864   CCA439690014C864   CCA439690014C864

    EXTERNAL ANCHORS (each row checked against something not under test)
      fast_random oracles: python == niv-lr C over 4096 draws
      galaxy reference   : galaxy.bin  6860 bytes  CCA439690014C864ADA48DDF
      mul64  /frag  vs Python bignum   : 4058 pairs, 0 mismatches
      rnd    /frag  vs both oracles     : 4096 draws, 0 mismatches
      galaxy /frag  vs frozen galaxy.bin: IDENTICAL (6860 bytes)
      mul64  /limb  vs Python bignum   : 4058 pairs, 0 mismatches
      rnd    /limb  vs both oracles     : 4096 draws, 0 mismatches
      galaxy /limb  vs frozen galaxy.bin: IDENTICAL (6860 bytes)
      mul64  /star  vs Python bignum   : 4058 pairs, 0 mismatches
      rnd    /star  vs both oracles     : 4096 draws, 0 mismatches
      galaxy /star  vs frozen galaxy.bin: IDENTICAL (6860 bytes)

    RESULT: all three backends agree with each other and with every external anchor.

The columns agreeing with each other is the weak half of that. What makes it
non-circular is the anchor column: the operand table is checked against Python
arbitrary precision (ground truth for "what is a 32x32 -> 64 product",
independent of any x86 behaviour), `fast_random` against two separately-authored
oracles, and `sitecount-galaxy2.bin` against the frozen `work/galaxy.bin`, which
`compare3.py` had already matched to `harness/oracle.c` and `harness/oracle.py`
across all 343 sectors.

The operand table is 4058 pairs: 9 adversarial, 49 corner combinations of
`{0, 1, FFFFh, 10000h, 7FFFFFFFh, 80000000h, FFFFFFFFh}`, and 4000 seeded
random. **2952 of them are sign-sensitive** -- the signed and unsigned high
halves differ -- which is what makes the table able to catch a backend that
called MUL where it should have called IMUL. `sitecount_cmp.py` asserts that
count is non-zero rather than trusting it.

## Cost

`work/sitecount_bench.txt`, signed products over a walking operand pair with
both halves XOR-folded into a checksum. Measured at two loop counts so process
startup and the launcher's poll granularity cancel out of the slope; the raw
single-point numbers are useless here, because at 2M iterations all three
backends land within 0.15s of each other and `*%` even measures *negative*.

| backend | 40M iters | 400M iters | ns/multiply (slope) | ratio | bench .exe |
|---|---|---|---|---|---|
| frag | 1.31s | 4.12s | 7.8 | 1.0x | 18960 B |
| limb | 2.39s | 11.26s | 24.6 | ~3.2x | 19304 B |
| star | 1.31s | 3.57s | 6.3 | ~0.8x | 18968 B |

Medians of 3. Read the ratios as "roughly 3x", not as a profile. All three
produce the same checksum at every loop count (`8D32597D` at 2M, `C695ACDA` at
40M, `A3836F13` at 400M), which is a fourth agreement on top of the grid above.

The limb backend costs about three times a hardware multiply, not the ~20x its
instruction count suggests, because the four partial products are independent
and the loop is not multiply-bound.

## Category (d) is the harder problem, and it is NOT about *%

`isthere` does not match a star by coordinates. It builds a double-precision
identity and compares it against a stored one inside a fixed window
(NOCTIS-0.CPP:5643-5704):

    laststar_id = (x * 1e-5) * (y * 1e-5) * (z * 1e-5)
    accept if  star_id - 1e-5 < laststar_id < star_id + 1e-5

L.in.oleum's `**` is MUL.f on 32-bit units, i.e. IEEE single. Measured by
`noctis-harness/sitecount_idprec.py` against the real coordinates in
`work/galaxy.bin`:

| |coord| | |id| | single ulp | window / ulp |
|---|---|---|---|
| 377489 (galaxy.bin sample, at the origin) | 53.8 | 3.8e-06 | 2.62 |
| 3797120 (`dzat_x` at game start, NOCTIS-0.CPP:780) | 54747 | 3.9e-03 | 0.003 |
| 10000000 | 1.0e6 | 6.3e-02 | 0.0002 |

Even at the galactic origin the acceptance window is under three single-precision
ULPs wide; at the coordinates the game actually starts at, one ULP is 390x wider
than the whole window. Star identity matching cannot be done in single
precision. This is a real blocker, and `*%` does nothing for it.

## How much of the game depends on category (c)

* Galaxy hash: every star position in the game. Already ported bit-exact in
  `work/galaxy.txt` using the `{ F7 EB }` fragment.
* `fast_random`: `fast_random` is called 21 times and `ranged_fast_random` 106
  times in NOCTIS-0.CPP, plus 33 and 8 lines in NOCTIS-1.CPP and NOCTIS.CPP --
  roughly 168 call sites. It seeds every planet surface (`surface()` does
  `fast_srand(seedval*10); seed = fast_random(0xFFFF)`), every star name, every
  terrain feature. It must be bit-exact or nothing in the universe matches.

## Recommendation

**`*%` is not load-bearing. Ship the fragment backend, keep all three.**

The count says two distinct algorithms in Noctis IV need a full 64-bit product
-- the galaxy hash (`sky`/`isthere`, 4 sites in the game plus 8 copies in
standalone tools) and `fast_random` (1 site, ~168 call sites). That is now not
an argument from counting: **both** are ported, and both are bit-exact under
**all three** backends, two of which use nothing but the stock `compiler.exe`
and the stock `i386` pack. Six of the nine builds involve no language extension
of any kind.

The deciding argument is not instruction count, and it is not performance.
It is **licence**. `main/lib/gen/compiler.txt` is under the WTOF Public
License, which forbids modification without the original author's
authorisation. `*%` exists only in `compiler114m.exe`, a patched build.
`mul64frag.txt` needs no patched compiler and no extended pack, so it is the
only backend the project can currently redistribute. That reasoning holds
regardless of how elegant `*%` is.

So:

* **Ship `mul64frag`.** It is the only currently-redistributable backend, it is
  the fastest measured, and the algorithm it carries is the one with the
  strongest external anchoring.
* **Keep `*%`.** It is the most readable of the three (20 lines against 44), it
  is the only one that would survive a non-x86 CPU pack, and it costs nothing
  to keep: it is already built, fixpoint-verified, and rebuilds all 7
  pre-existing programs byte-identically. Keeping it commits the port to
  nothing, because the backend is one line in a `"libraries"` period.
* **Keep `mul64limb` too.** It will not ship, but it is the proof that the
  language is sufficient on its own -- no fragment, no patched compiler, no
  x86, no carry flag. At ~3.2x the cost of a hardware multiply it is also a
  perfectly usable fallback rather than a token one.

The port's blast radius for 64-bit arithmetic is now exactly two subroutine
names, `Mul64u` and `Mul64s`. The `*%` question does not need to be answered
before the port proceeds, which is the real result here.

## Traps for the implementer

1. `laststar_x/y/z` are declared `double` (NOCTIS-0.CPP:5628) but the assembly
   first stores a 32-bit **integer** into their low four bytes
   (`db 0x66; mov word ptr laststar_x, dx`), then `fild dword ptr` reads those
   bytes back as an integer and `fst` overwrites the whole 8 bytes with the
   double. The same symbol is an int32 and a double within one basic block. A
   port that gives it a single type will be silently wrong.
2. `add al, dl` in `fast_random` is an **8-bit** add with no carry out. Widening
   it to 32 bits changes the sequence. Only bits 32..39 of the product matter.
3. `sect_x *= 100000` is a C `long` multiply that **truncates to 32 bits**. If it
   overflows, the wraparound is part of the algorithm; use L.in.oleum's plain `*`
   and do not widen it.
4. `sky()` skips sectors whose temp coordinate equals the 50000 cutoff; some
   `isthere()` copies do not. Diff the five copies rather than assuming they are
   the same function -- only the hash core is common.
5. The `{ F7 EB }` fragment writes `edx`, i.e. register `D`, invisibly to the
   compiler. That is harmless here because L.in.oleum is an assembly language
   with programmer-managed registers, but a fragment placed where `D` is live
   will corrupt it with no diagnostic.
6. Do not trust `defs.h`'s `IMUL_EDX` / `IMUL_ECX_EDX` / `Qword` / `DOUBLE_` --
   all four are dead definitions, and `Qword`/`DOUBLE_` belong to the 32-bit
   branch that the DOS build never takes.
7. **An underscore inside a `{ }` string is the blank space marker**
   (`docs/variable.htm`, character 95). `result file name = { foo_bar.bin };`
   silently opens `"foo bar.bin"`. This cost real time here: the first two
   programs compiled cleanly, ran, exited 0, and wrote their output to a file
   nobody was looking for, which is indistinguishable from a crash unless you
   list the directory. All lino file names in this track use hyphens.
8. A lino program that fails still exits 0. The only reliable success signal is
   the output file's mtime being newer than launch, which is why
   `sitecount_run.py` deletes the target first and checks `st_mtime > t0`
   rather than mere existence -- otherwise a crashed program "passes" on the
   previous run's leftovers.
