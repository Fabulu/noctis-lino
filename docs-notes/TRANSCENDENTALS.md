# Portable transcendental contract and acceptance

This document records the production contract for `FSin`, `FCos`, and
`FAtan2`, the evidence required before changing them, and the distinction
between a mathematical oracle and the historical x87 implementation. It was
last measured on 2026-08-21.

## Public ABI

The public scalar interface is declared by `work/fp/fpabi.txt` and exported by
`work/fp/fpx87.txt`:

- `FA0/FA1` is the input accumulator and result, low binary64 word first.
- `FB0/FB1` is the second input, low binary64 word first.
- `FAtan2` computes `atan2(FA, FB)`: `FA` is `y` and `FB` is `x`.
- Every result writes both halves of `FA`.
- `A/B/C/D/E` are preserved across every public scalar call.
- A call leaves the host x87 stack at the same TOP/depth it found.
- Production enters the FP boundary with `FCWEXT = 133Fh`: 64-bit x87
  significand precision, nearest-even rounding, and masked exceptions.

The implementation imports a binary64 exactly, computes in the modeled 64-bit
x87 significand format, and performs one nearest-even binary64 spill at the
public result boundary. It does not use L.in.oleum's native 24-bit floating
instructions.

## Algorithms and input range

`work/fp/fpsoft.txt` contains the portable integer implementation.

- Sine and cosine reduce with a 256-bit Payne-Hanek `2/pi` constant, then use
  extended Horner/Taylor kernels on `[-pi/4,+pi/4]`.
- The supported finite instruction interval is `|x| < 2^63`.
- At `|x| >= 2^63`, the wrapper preserves the x87 FSIN/FCOS "argument
  unchanged" behavior rather than pretending the instruction reduced it.
- Atan uses angle-addition intervals and an odd degree-33 series with
  `|u| <= tan(pi/16)`.
- Signed-zero and signed-axis `atan2` behavior is part of the contract.

Intel FSIN/FCOS's internal 66-bit approximation to pi is **not** the accuracy
oracle. In particular, matching its large-argument reduction would make the
portable result less mathematically accurate.

## Acceptance rules

A transcendental change is accepted only when all of these layers pass:

1. **Independent mathematical oracle.** `work/fp/fptransgrade.py` uses
   standard-library `Decimal` at precision 180, raised to 1,200 only for
   extreme atan ratios whose subnormal half-ULP depends on `atan(z) < z`, and a
   checked-in 200-digit pi. Every finite result must be within one binary64 ULP
   of that independent oracle, with exact signed-zero behavior.
2. **State contract.** The complete FP schedules must leave control word
   `033Fh`, TOP zero, and no schedule-dependent output divergence.
3. **Historical characterization.** A hardware x87 build is compared directly,
   but its FSIN/FCOS pi approximation is reported as characterization rather
   than promoted to the mathematical oracle.
4. **Consumer boundaries.** Production consumers are compared byte-for-byte
   between a portable build and a build in which only the three transcendental
   wrappers use hardware x87. Authoritative NIV+ artifacts remain stronger
   where they exist.
5. **Production generation.** The exact diagnostic NIVGEN fixture must retain
   all seven published FNV-1a hashes. Representative public-sheet coverage is
   reported with the row count and every mismatch; it is never weakened into a
   fuzzy comparison.
6. **Architecture.** The complete shipping dependency closure contains zero
   target-machine blocks. Platform runtimes establish the fixed FP environment;
   the historical x87 control/status witness is test-only and outside that
   closure.

The current 4,096-case schedules measure:

| Operation | Exact mathematical | Within 1 ULP | Exact legacy x87 |
| --- | ---: | ---: | ---: |
| `FSin` | 4096 | 4096 | 2469 |
| `FCos` | 4095 | 4096 | 2510 |
| `FAtan2` | 4092 | 4096 | 4095 |

All non-transcendental scalar, conversion, and schedule columns are
4096/4096; the control word is `033Fh`, TOP is zero, and the schedules have no
differences. The legacy columns explain why "equal to FSIN" and "accurate" are
not interchangeable claims.

## Production dependency-closure gate

`tools/check_lino_native_closure.py` recursively follows each Lino file's
`"libraries"` section from `work/vhgame.txt` and `work/vhnivgen.txt`. It resolves
relative, `work/`, and `main/` library names against tracked production sources,
ignores comments and brace strings, and rejects both one-line and multiline
executable brace blocks in imported files as well as in the roots.

The current closure is 75 files and 89 imports, with zero executable raw target
blocks. `tests/test_native_closure.py` independently pins the seven historical
x87 control/status blocks in `work/fp/fpctlx87.txt`, proves that file is outside
the production closure, and proves that production policy would reject every
one of those blocks. It also proves that a block imported one level down is
found, semicolon-suffixed programme blocks cannot bypass the scanner, and a
tracked owner cannot escape through an untracked sibling.

The same gate inventories every ordinary Lino floating operation in executable
production periods. The exact reviewed inventory is 36 operations in three
files: 25 in `main/lib/gen/rect.txt`, eight in `work/supaint.txt`, and three in
`work/supal.txt`. There are no production `??` floating comparisons. Any added,
removed, reordered, or changed operation fails review rather than silently
expanding the target-dependent surface.

`work/fp/fpctl.txt` is a portable state contract with no machine escape. The
eight licence-protected Windows runtime variants retain their exact upstream
bytes; one selected runtime in each generated PE receives the size-preserving,
fail-closed `133Fh` post-link patch. Linux and macOS load `133Fh` before
application entry and reload it immediately after each C/runtime isocall.
`tests/test_fp_runtime_boundary.py` pins the protected variants, output patch,
rejection paths, source sites, constants, and hosted-probe wiring. The test-only
x86_64 Mach-O probe performs real `fldcw`/`fnstcw` perturb/load/read/restore on
both Intel macOS and Apple Silicon through Rosetta; the local x86_64 probe is
exact and the two hosted jobs remain required before release. Ordinary game
code, including `work/fp/fpx87.txt`, contains no raw x86 block. A clean root file
is not sufficient; the transitive gate is the policy.

## Executable consumer evidence

`tests/test_transcendental_consumers.py` copies only tracked `work/` inputs into
an isolated `tests/gen/transcendental-consumers/` tree and explicitly excludes
the four protected FP artifacts. It builds one portable and one reference tree;
the reference changes only the three public wrappers to direct x87 `FSIN`,
`FCOS`, and `FPATAN`. Every output is compared byte for byte, checked for its
exact size, and pinned by SHA-256. The current matrix passes 45 checks.

The existing capsule, sun/flare, and tree probes cover flight-state chains,
authoritative rendered pages, and orientation/geometry state. A derived full
`vhgame` main links `work/vhtransprobe.txt`, retaining the complete current game
global layout while replacing only the entry call. Its deterministic record
covers:

- `VH set view` followed by the production `VHG forward` and `VHG strafe`
  camera/walk basis;
- `SP glass bubble` globe stepping, integer coordinate chops, smoothing, and the
  complete 64,000-byte page;
- all used vertices of the shipped vehicle through `SP modpv`'s Y/X/Z Euler
  transform, with four transformed vertices decoded in the state record;
- four hundredth-degree animal headings through the production sine and cosine
  movement services;
- the live-animal terrain inclination boundary at `-45, -27, 0, 27, 45`
  degrees after clamp, signed `atan2`, degree conversion, and nearest rounding;
- a retained generated system through `VHGND exact viewpoint`, pinning orbital
  viewpoint `288` and the source vector halves.

The full-game state hash is
`4903b877abf104a9126be8471687da4cd1ef08cc6ebbe95b80528d81389290dc`;
the globe page hash is
`5a9fbebabc9e64b07f6a66ab9ba9419255b6b7f47e9523aed78df370d1535263`.
Both are byte-identical to the direct-x87 reference. The test also re-hashes all
production sources it reads after both builds, so an isolated comparison cannot
silently rewrite a source fixture.

## Workspace boundary

The first portable version allocated 220 additional Lino workspace units.
Together with the new scalar state this made the Wave 7a executable cross a
real static/workspace boundary and terminate with `C0000005`. Variables alone
passed, workspace alone passed, and the failure remained when the three
transcendentals were switched back to native x87, so it was not a numerical
failure.

The production tables now occupy 124 units:

| Allocation | Units |
| --- | ---: |
| `XPAY` | 20 |
| `XPC` | 16 |
| `XMANT` | 4 |
| `XSINTAB` | 40 |
| `XCOSTAB` | 44 |

The former 64-unit atan table and 32-unit constant table are immediate extended
constants. Workspace size is therefore part of regression acceptance, not a
cosmetic optimization.

## NIVGEN evidence

The exact diagnostic fixture is:

```text
x=-1996209872 y=55508 z=816148 body=2 lon=0 lat=60
surf=390A2CCB  atmo=114562E8  pal=26961E4A
hm=97022FD7    oc=22913F4E    stex=0D52F001  sky=1E308D29
```

It also emits 13 diagnostic records and reports the expected body type and
owner. This fixture is required exactly on the production library graph.

The fractional standard-crater power path has its own historical x87 oracle.
`tests/test_fractional_pow.py --deep` derives the complete reachable type-1 and
type-5 input domain from the production radius, factor, exponent, radial-test,
and spill rules, including type 5's `random(5) * 0.015`: 586,183 pre-power
combinations, 490,424 distinct type/base pairs, and 9,564,210 base/exponent
pairs. The independent integer operation mirror agrees with the exact
historical x87 sequence on every final binary32 result, with pinned digest
`b3c1aef60b2f697211e33d21b9f1d3be7f2cbcb0003fa5bc88810a46708ea937`.
The 4,096-case compiled-Lino boundary corpus is pinned separately at
`1e84ea9324e385321a3b97e5f6f4f0ebe2779cd0b714905949de534d6aaec831`.
It includes the reachable exact base 8.0 for every type-1 exponent, exercising
`XPowPositive`'s internal `z=(m-1)/(m+1)=0` path. That path retains exact zero
instead of violating `XQuoCore`'s normalized-finite numerator contract.

The ordinary-Lino driver also pins all eight stack positions, depth, soft-stack
sentinels, and the single final `XToF32` boundary. Production ground gates retain
three authoritative complete map/object pairs: type-1 default
`FDDDF3A2`/`1AA95391`, type-5 default `301D7754`/`34B1E2D4`, and the random
`OLIKETT I|7` site `46586E03`/`98264D87`. The object checks supply the captured
16-byte allocation gap explicitly and pin the corresponding Borland draw counts.

The complete offline type-1/type-5 rescore proves the corpus effect rather than
inferring it from those anchors. The exact-power-of-two repair changes 209
values relative to the post-zero-quotient build: 174 random heightmaps and 35
random object charts. Every change is an exact repair; there are no regressions
or wrong-to-different-wrong transitions. The final score is 18,120/18,128 exact
comparisons and 1,646/1,648 fully exact rows, with score SHA-256
`b118f2530e260faf6dd550f338d8b9c6c9e0dba0029e85e1bcc0c801049af719`.
Only `XENOFELYS|4` and `XENOFELYS|10` remain, across eight fields. Since their
retained targets break otherwise complete type-level output invariants, resolve
them with an original/reference first-divergence trace rather than weakening the
power oracle or introducing fixture-specific behavior.

The public `nivgen_planets` sheet is the authoritative parity corpus, not the
fixture above or a selected type sample. A canonical 5,188-row snapshot taken
on 2026-08-21 has SHA-256
`ab73b236957f225247e07460eaae1a7e26891e701d6b5bd4c93d573208231f97`.
`tools/nivgen_sheet_report.py` fetched its eleven pages sequentially with a
one-second delay and no retries.

The visible zero-error/checkmark count is not an exactness denominator while
backfill is incomplete: 642 rows have no authoritative hashes, and the sheet
marks those rows as zero-error. Lino therefore shows 1,068/5,188 zero-error
markers, but only 426/4,546 independently comparable rows are hash-exact (9.4%).
Rust shows 4,888 markers but 4,246/4,546 comparable exact rows (93.4%). LR's 613
zero-error markers are all unbackfilled; it has 0/4,546 fully exact comparable
rows and 175 rows with missing LR results.

Field-level Lino results expose the dominant failures:

| Field | Exact / authoritative | Rate |
| --- | ---: | ---: |
| orbital surface | 401 / 4,485 | 8.9% |
| atmosphere | 3,627 / 4,485 | 80.9% |
| palette | 2,622 / 4,485 | 58.5% |
| default heightmap | 2,895 / 4,546 | 63.7% |
| default object chart | 4,538 / 4,546 | 99.8% |
| random heightmap | 3,233 / 4,546 | 71.1% |
| random object chart | 3,439 / 4,546 | 75.6% |
| default surface texture | 4,545 / 4,546 | 100.0% minus one |
| default sky | 4,544 / 4,546 | 100.0% minus two |
| random surface texture | 4,508 / 4,546 | 99.2% |
| random sky | 4,541 / 4,546 | 99.9% |

Among comparable rows, Lino is fully exact on 174/220 type-3, 192/215 type-9,
and 59/61 type-10 bodies. Types 0, 1, 4, 5, 6, 7, and 8 currently have zero
fully exact comparable rows; type 2 has one. Planets score 294/1,438 and moons
132/3,108. The earlier zero-error counts looked less severe because they mixed
real exact rows with unbackfilled checkmarks. The one-row-per-type run remains a
narrow smoke subset and cannot establish NIVGEN parity.

## Required commands

Run these from a Windows checkout with the extended compiler available:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File work\fp\fprun.ps1
python tests\test_native_closure.py
python tests\test_fp_runtime_boundary.py
python tests\test_transcendental_consumers.py
python tests\test_fractional_pow.py
python tests\test_fractional_pow.py --deep
python tests\test_nivgen_score.py
python tests\test_nivgen_sheet_report.py
python tests\test_surface.py
python tests\test_ground.py
python tests\test_vhgame.py
```

The FP runner rebuilds both the current Lino driver and independent C reference
inside a fresh directory. It must not copy, execute, overwrite, or otherwise
depend on the checked-in or user-owned `fpout.bin`, `fprefout.bin`, `fptest.exe`,
or `fpvec.bin` files in `work/fp`. Consumer-probe and NIVGEN runs likewise use
isolated working directories and record exact inputs, executable provenance,
output sizes, and hashes.
