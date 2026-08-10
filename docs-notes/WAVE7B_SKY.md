# Wave 7b sky: frozen implementation architecture

Status: final verified implementation, frozen 2026-08-08. This document narrows
the sky portion of `WAVE7B_PLAN.md`; it does not broaden Wave 7b into the walking
renderer. The production result is `work/sky.txt`, implementing NIV+ R2.3
`create_sky`, `cloudy_sky`, and `nebular_sky` from `NOCTIS-1.CPP:1674-1765` and
`:2736-3139`.

The first binary-qualified target is deliberately narrow: the captured, landed,
type-3 OCEAN/night fixture. Its final 360x180 `s_background` and its 256-colour
`surface_palette` are exact binary oracles. Other cases establish source fidelity and
branch coverage through three independent implementations; they do not acquire a
NIV+ binary claim merely by agreeing.

## Final verification (2026-08-08)

`tests/test_sky.py` passes in full: **16/16 tests** (wall time **1999 s**).
The canonical Python/C/Lino run agrees on **27/27 cases and 408 records**;
first-launch output is exact, malformed-input coverage is **7/7**, binary anchors
are exact, C mutants are **26/26** killed, and static plus dynamic Lino mutants
are **27/27** killed. H1 source/work immutability also passes. The independent
replay stream SHA-256 is
`a68a5775f2ad05d04cdd6c399b42f06a5d2a24cd555e81348ef7e47f70ecf421`.

These results close the sky implementation and D/R/J attribution gates. They do
not grade screenshots. The type-3 `p_surfacemap` `round_hill` mismatch remains a
measured **XFAIL (39,710 bytes)** and is outside the sky claim.

## 1. Settled facts and non-negotiable semantics

The call chain is:

```
resume -> planets()/surface() -> planetary_main -> memset(s_background)
       -> create_sky(atmosphere) -> cloudy_sky()/nebular_sky()
       -> surface_palette + pressure/temperature + horizon darkening
       -> build_surface() -> per-frame SP background
```

`create_sky(char atmosphere)` receives a boolean. It is not the global
`objectschart` alias bearing the same historical name. The caller has already set
planet type/subtype, filters, albedo, raininess, brightness, latitude-related state,
and the global surface seed. `create_sky` reads no clock. It re-seeds both NIV+ random
streams from the global surface seed; `build_surface` later re-seeds them again.

The exact framebuffer workspace rules are part of the algorithm:

* `RSBG = 40172`, size 64,800 bytes, logical shape 360x180.
* `ZSBG = 64800`; no sky painter may write at or beyond `RSBG+ZSBG`.
* `SU ssmooth`, `SU lssmooth`, and `SU psmooth grays` from `work/susm.txt` are reused
  with `SUpbase=RSBG`. They preserve DOS dword-add carries, in-place order, stride
  320 where the source uses it, and `lssmooth`'s `i,i+1,i+360,i+361` reads.
* `lssmooth` may read 41 bytes beyond the logical end. The runner supplies readable,
  deterministic tail bytes and canaries; it must not clamp those reads.
* `QUADWORDS` is saved before a painter changes it and restored on exit.
* `surface_palette` is `srfpal6`, not the active display `pal6`.
* Palette shading reuses `PAL shade` from `work/fbpal.txt`, with `SHdstb=srfpal6`.
* Panorama composition reuses `SP background` from `work/spbg.txt`. Sky production
  never contains a private copy of the composer.

The earlier `noctis-harness/sky_spec.py` is reconnaissance, not an oracle. It models
the smoothers byte-wise, has placeholder/dead loops, misses state and palette outputs,
and has incorrect random draw counts (notably OCEAN consumes 11 `flandom` calls before
`cloudy_sky`, not 12; planet type 5 consumes 6, not 9). It must be replaced, not
incrementally blessed. This is why `work/sky.txt` never safely landed.

## 2. Namespaces and file ownership

All Lino symbols are link-global. The following prefixes are exclusive:

* Production sky library: `GRSK*`; human-readable labels start `GR sky `.
* Standalone sky runner/dump/parser: `GRSKH*`; labels start `GR sky harness `.
* Existing libraries remain authoritative: `SU*`, `PAL*`, `SP*`, `FB*`, `FP*`,
  `PGF*`, and their current register names.
* `VH*` belongs to Wave 10 vehicle work. Sky code must declare no `VH*` symbol.
* Do not introduce generic `SK*` or new bare `GR*` symbols; both are too collision
  prone during later game integration.

The implementation packages own disjoint files:

1. **Python/corpus package** owns `noctis-harness/sky_spec.py`,
   `noctis-harness/sky_corpus.py`, `noctis-harness/sky_grade.py`, fixture extraction
   helpers under `tests/gen/recon_w7b/`, and later `tests/test_sky.py`.
2. **C/mutant package** owns `noctis-harness/sky_ref.c`,
   `noctis-harness/sky_break.py`, and generated C mutant sources in the test sandbox.
3. **Lino package** owns `work/sky.txt` and `work/skymain.txt` only.

Nobody in these packages edits `tests/run_all.py`, `work/game-vh.txt`, Wave 10 files,
or existing `SU`/`SP`/palette libraries. Registration and game linkage are coordinator
work after all three packages pass independently.

`work/sky.txt` is a pure library: no `program name`, corpus parser, file name, fixture,
or dump code. `work/skymain.txt` is the only standalone programme and contains only
initialisation plus `GRSKH run`. Thus production cannot accidentally depend on the
test format.

## 3. Canonical input record

The canonical corpus source is a Python list in `sky_corpus.py`. Tests regenerate a
flat text stream in their private sandbox for every run; no generated `.bin` is a
checked-in oracle. The Lino runner is given that sandbox file as `sky-corpus.txt`.

The grammar is exactly the existing `su`/`sp` convention: whitespace-separated signed
decimal integers only. Each token is decoded to one little-endian 32-bit unit. Values
whose semantic type is `u32` are printed using the signed two's-complement spelling
when bit 31 is set. Binary32 values are their raw IEEE-754 bits, never decimal floats.

Each case contains exactly 29 units in this order:

| unit | name | semantic width/type | rule |
|---:|---|---|---|
| 0 | `opcode` | u32 | `1` = sky case, `0` = end; no fields follow end |
| 1 | `case_id` | u32 | unique, stable, nonzero |
| 2 | `flags` | u32 | claim/output flags below |
| 3 | `ptype` | i32 | NIV+ planet type |
| 4 | `sctype` | i32 | NIV+ surface class/subtype |
| 5 | `atmosphere` | i32 | canonical boolean 0 or 1 |
| 6 | `nightzone` | i32 | canonical boolean 0 or 1 |
| 7 | `ip_targetted` | i32 | target slot, retained to exercise state wiring |
| 8 | `nearstar_owner` | i32 | owner of the target planet |
| 9 | `nearstar_class` | i32 | target star class |
| 10 | `global_surface_seed` | u32 | raw 32-bit seed |
| 11 | `albedo` | i32 | source-domain integer |
| 12 | `rainy_bits` | binary32 | raw bits |
| 13 | `sky_brightness_in` | u32 | entry value/fill byte; low 8 bits are used |
| 14 | `sky_red_filter` | i32 | source-domain signed char promoted to i32 |
| 15 | `sky_grn_filter` | i32 | same |
| 16 | `sky_blu_filter` | i32 | same |
| 17 | `gnd_red_filter` | i32 | same |
| 18 | `gnd_grn_filter` | i32 | same |
| 19 | `gnd_blu_filter` | i32 | same |
| 20 | `dsd1_bits` | binary32 | raw bits |
| 21 | `exposure_bits` | binary32 | raw bits |
| 22 | `landing_pt_lat` | i32 | source-domain latitude integer |
| 23 | `quadwords_in` | u32 | value which must be restored at return |
| 24 | `tail_mode` | u32 | `0` = zero, `1` = deterministic hostile tail |
| 25 | `tail_seed` | u32 | seed for hostile tail; ignored by mode 0 |
| 26 | `bg_start` | i32 | `SP background` replay/join start |
| 27 | `bg_shift` | u32 | replay/join horizontal shift |
| 28 | `bg_bytes` | u32 | `SP background` offsets-table traversal length; canonical page rows use `OMBYTES=7,340` |

Flag bits are fixed:

| bit | name | meaning |
|---:|---|---|
| 0 | `BINARY_ANCHOR` | outputs may be compared to captured NIV+ bytes |
| 1 | `GRADE_PALETTE` | palette is defined and must be emitted/compared |
| 2 | `GRADE_SCALARS` | pressure, temperature, brightness and RNG state grade |
| 3 | `GRADE_PAGE` | replay and joined 320x200 pages grade |
| 4 | `TAIL_SENSITIVE` | hostile-tail companion must change a witnessed read path |
| 5 | `LIVE_REACHABLE` | fixture is known reachable by the NIV+ caller |
| 6 | `PALETTE_UNDEFINED` | source contains undefined palette state; bit 1 must be 0 |

All other flag bits must be zero. The parser rejects truncated records, unknown opcodes,
noncanonical booleans, contradictory palette flags, and tokens after the terminator.
For `GRADE_PAGE` rows it also requires `bg_bytes == OMBYTES` (7,340); 64,800 is the
panorama size, not this field.  Delivered `SP background` treats its DOS `BP` through
`SSBG = RSBG - 4`, so an independent composer must map `BP=4` to raw panorama byte 0
(equivalently, expose a four-byte prefix before the 64,800-byte SBG).

For `tail_mode=1`, byte `i` at `RSBG+64800+i`, for `0 <= i < 64`, is exactly:

```
(tail_seed + 73*i + ((i*i) >> 1)) & 255
```

Sixty-four bytes exceed the known 41-byte read window and leave room for an outer
canary. All producers use the same formula; it is not an output oracle.

## 4. Output framing

Every producer writes the same little-endian u32-framed stream. A record begins with a
16-unit (64-byte) header, followed by `body_units` u32 units. Byte bodies are packed
four bytes per unit, low byte first; unused bytes in the final unit are zero. This is
the delivered `SUDUMP` convention, with a sky-specific magic.

Header layout:

| unit | name | value/meaning |
|---:|---|---|
| 0 | `magic` | `0x31594B53` (`SKY1` as little-endian bytes) |
| 1 | `version` | `1` |
| 2 | `kind` | enumeration below |
| 3 | `width` | logical width, or fixed-body unit count |
| 4 | `height` | logical height, or 1 for fixed bodies |
| 5 | `body_units` | exact following u32 count |
| 6 | `case_id` | copied from input |
| 7 | `phase` | phase enumeration, otherwise 0 |
| 8 | `body_bytes` | significant bytes before zero padding |
| 9 | `sequence` | zero-based record number within the case |
| 10 | `flags` | copied input flags |
| 11..15 | `reserved` | zero; nonzero is a format error |

Kinds and bodies:

| kind | name | body |
|---:|---|---|
| 1 | `META` | the 28 input units after opcode, unchanged |
| 2 | `PRE_HORIZON` | packed 64,800-byte sky after painter/palette/scalars, before horizon loop |
| 3 | `FINAL_SBG` | packed 64,800-byte final `s_background` |
| 4 | `PALETTE` | packed 768 bytes, RGB triplets for 256 entries from `srfpal6` |
| 5 | `SCALARS` | fixed 12-unit body below |
| 6 | `LEDGER` | fixed 8-unit body below; one record per phase |
| 7 | `GUARDS` | fixed 10-unit body below |
| 8 | `REPLAY_PAGE` | packed 64,000-byte page made from independently supplied expected SBG |
| 9 | `JOIN_PAGE` | packed 64,000-byte page made from this producer's `FINAL_SBG` |
| 10 | `CASE_END` | no body |
| 255 | `STREAM_END` | fixed 4 units: case count, error count, record count, zero |

For byte images, width/height are respectively 360/180, 256/1, or 320/200. Palette
`body_bytes` is 768 even though width is 256. Kinds 8 and 9 are omitted unless
`GRADE_PAGE` is set. Kind 4 is always emitted for stable framing, but graders ignore
its contents when `GRADE_PALETTE` is clear and require its 768 bytes to be zero when
`PALETTE_UNDEFINED` is set. No producer may leak uninitialised host bytes.

The `SCALARS` body order is:

```
0 final_sky_brightness (u32)
1 pp_pressure_bits      (binary32)
2 pp_temp_bits          (binary32)
3 base_pp_pressure_bits (binary32)
4 base_pp_temp_bits     (binary32)
5 brtl_final_state      (u32)
6 fast_final_state      (u32)
7 brtl_draw_count       (u32)
8 fast_draw_count       (u32)
9 brtl_ledger_hash      (u32 FNV-1a over returned u32 values)
10 fast_ledger_hash     (u32 FNV-1a over returned u32 values)
11 quadwords_after      (u32; must equal input unit 23)
```

The `LEDGER` phases are 0 `ENTRY`, 1 `SEEDED`, 2 `COLOURS`, 3 `PAINTER`, 4
`PALETTE`, 5 `THERMO`, 6 `HORIZON`, and 7 `DONE`, emitted in that order. Its body is:

```
phase, brtl_draw_count, fast_draw_count, brtl_hash, fast_hash,
brtl_state, fast_state, FNV1a32(s_background[0..64799])
```

The `GUARDS` body is:

```
0 minimum_sbg_write_offset   (relative; 0xFFFFFFFF if none)
1 maximum_sbg_write_offset   (relative; 0xFFFFFFFF if none)
2 total_sbg_byte_writes
3 out_of_bounds_sbg_writes   (must be 0)
4 tail_hash_before
5 tail_hash_after            (must equal before)
6 outer_canary_before
7 outer_canary_after         (must equal before)
8 quadwords_before
9 quadwords_after            (must equal before)
```

Instrumentation counters are harness/reference concerns, not production branches.
The production Lino library exposes only deliberate phase callbacks compiled as no-ops
in game linkage; `skymain` binds them to ledger/dump hooks. C and Python instrument the
same semantic write and RNG wrappers.

Per-case record order is `META`, `PRE_HORIZON`, `FINAL_SBG`, `PALETTE`, `SCALARS`,
eight `LEDGER`s, `GUARDS`, optional `REPLAY_PAGE`, optional `JOIN_PAGE`, `CASE_END`.
After the last case comes one `STREAM_END`. Record order, reserved zeros, padding zeros,
and trailer counts grade before bodies do.

## 5. Fixture and corpus ownership

The Python/corpus package is the sole owner of fixture values.  Captures are never
modified by a test.  Two different observations must not be conflated:

* The pinned binary assets came from a landed type-3 OCEAN **night** capture at star
  `(1463568,-4728350,-437812)`, target body 3, longitude 0, latitude 60.  Its RAM image
  was not retained, so its complete caller state cannot be claimed as captured.
* A later live diagnostic at the same site was a **day** state: sky filters
  `(39,56,48)`, ground filters `(42,70,44)`, `albedo=40`, `rainy=3.75`,
  `sky_brightness=48`, `nightzone=0`, `dsd1=0x4373BE4C`,
  `exposure=0x41A2C7E3`, and `global_surface_seed=1029155`.  It is a separate
  piece of live diagnostic evidence, not the binary anchor state; it must not be
  described as a canonical corpus row unless those exact fields are added there.

The night asset's output-driving inputs are reconstructed and independently
falsified, not presented as recovered RAM: type 3, OCEAN, `nightzone=1`,
`sky_brightness=8`, seed `1029155`, and albedo `32` reproduce both captured assets
exactly.  Albedo 31 image-collides for this seed but is source-unreachable because the
type-3 caller quantises albedo to a multiple of eight.  Filters and raininess cannot
affect the special type-3 night palette or the sky painter output; `dsd1` and exposure
are read only by the later scalar path.  The anchor row therefore uses documented
poison for unobserved scalar-only inputs, clears `GRADE_SCALARS` and `LIVE_REACHABLE`,
and proves that perturbing those poison fields leaves the two anchored outputs
unchanged.  `horiz_brt` is not read by `create_sky` or the 120-row horizon transform
and is consequently not part of the 29-unit record.

Pinned captured assets:

* `s_background`: 64,800 bytes, SHA-256
  `e140cde39ef27240f9a8a5ba4a420c66b0a3e55acb01f5b3434895e5963aba01`.
* `surface_palette`: 768 bytes recovered from the BMP palette, SHA-256
  `8fe2f8a9d2e3e7fc262133d8fa1cf9062306f20a7ac9388ae9693b74637ff5b1`.

The palette corresponds to the four source `PAL shade` calls with starts 0, 64, 128,
and 192. It must be regenerated by the implementation, not copied from the capture.

Minimum synthetic corpus, owned and named by Python:

* the binary OCEAN/night anchor and an exact repeated row at corpus end;
* OCEAN companions that distinguish 11 from 12 pre-cloud RNG draws;
* type-5 companions that distinguish 6 from 9 draws and stale brightness;
* atmosphere 0/1 pairs;
* day/night pairs where source palette state is defined;
* hostile-tail zero/nonzero pairs covering `lssmooth`'s final reads;
* smallest-reachable-denominator colour-scaling cases.  A zero denominator is
  unreachable in `cloudy_sky`: it requires `x=-r,y=-r`, while that point fails
  the painter predicate because `sqrt(1.2)*r < r` is false for every positive
  source radius.  The corpus must test the reachable boundary, not fabricate a
  call outside production semantics;
* albedo boundary cases;
* one page case with nonzero `bg_start` and `bg_shift`;
* source-reachable cases for every defined planet branch;
* explicit undefined-palette rows for type-3 PLAINS and unhandled planet types, with
  `PALETTE_UNDEFINED` set and palette grading disabled.

The type-3 PLAINS source assigns `fr[2]` three times, leaving `fg[2]` and `fb[2]`
uninitialised. The corpus must not silently choose values and call them NIV+ exact.
The Python source model may expose a documented deterministic poison value solely to
prove that production never receives an exact-palette claim for that row.

The NIV+ screenshot is not a byte oracle: the two otherwise identical captures differ
in 642 pixel bytes (629 in sky rows 40..99 and 13 in ground). It may support a bounded
visual test only. Strong static witnesses include row 0 all zero, row 119 containing
values 3/4, row 120 containing 8/9 with all 360 pixels changed from row 119, and rows
150 and 179 all 8 for the pinned anchor.

## 6. D/R/J attribution gates

Do not first test a production sky joined directly to the composer. Use three gates:

**D -- Derive.** Run `create_sky` only. Compare framing, ledger, pre-horizon texture,
final SBG, defined palette, scalars, RNG terminal states, and guards across Python, C,
and Lino. For the anchor, compare final SBG and palette to the captured bytes as a
fourth party.

**R -- Replay.** The grader freshly materialises the Python/C-agreed expected final SBG
as a sandbox `sky-replay.bin`. `skymain` loads that independent blob, clears `adapted`,
and calls the delivered `SP background` with corpus units 26..28. Compare the resulting
`REPLAY_PAGE` to the Python composer model and the existing `SP background` oracle.
R never invokes production `GRSK create`.

**J -- Join.** In the same runner, clear `adapted`, call production `GRSK create`, then
call the same `SP background` on its live `RSBG`. Compare `JOIN_PAGE` to the expected
page. A joined-page failure is actionable only after D and R pass: D failure belongs
to sky generation; R failure belongs to replay/composer/setup; J-only failure belongs
to buffer/register wiring or lifecycle.

`sky-replay.bin` is generated inside the test sandbox on every run, length- and
SHA-checked before use, and deleted with the sandbox. It is not a stored authority.

## 7. Shared-library linkage order

`work/skymain.txt` declares libraries in this exact order, preserving the already
delivered drivers' ordering:

```
fp/fpabi; fp/fpctl; fp/fpx87; fp/fpconv;
fbmem; fbpal;
pgfp;
spmem; spbg;
brtl; mul64frag;
suseed; surng; subuf; susm;
sky;
```

If `SP background` is excluded for a D-only diagnostic build, omit `pgfp`, `spmem`, and
`spbg` as one contiguous group; do not reorder the remaining libraries. The eventual
game uses its existing superset order and adds `sky` after `susm`, before the first
ground/walking library. Only the coordinator edits the game library list.

Initialisation order in `skymain` is `FEnter`, existing FP constants/init required by
`fbpal`, `PGF constants`, required SP table/register init, sky palette base init, dump
reset, corpus load/tokenise, replay load, case loop, trailer/write, `FLeave`. A producer
must not derive fixture values during initialisation.

## 8. Three disjoint implementation packages

### A. Python/corpus

Replace `sky_spec.py` with an explicit u8/u32 implementation. Dword additions use
32-bit little-endian loads/stores with carry; all smoothers are in-place and reproduce
source traversal order. RNG wrappers count and hash every returned value. Implement the
record encoder/decoder and strict structural validator first, then the corpus and
D/R/J expected streams. Extract the binary anchor from captures and verify its two
SHA-256 values before grading. This package never reads C or Lino output to construct
an expected result.

### B. C reference and optional deep mutants

Transcribe the NIV+ source into fixed-width C with an explicitly sized workspace,
readable 64-byte tail, canaries, deterministic binary32 environment, counted RNG
wrappers, and the common framed writer. Compile/run only through the eventual durable
test sandbox. It consumes the canonical text corpus and optional fresh replay blob;
it contains no copied Python tables of expected output.

The 1999-second mutation run (26 C mutants and 27 Lino mutants) is historical, one-time
closeout evidence. It can be repeated with an optional `--deep` workflow for a high-risk
oracle or sky algorithm change, but is not the routine acceptance bar. The focused default
is one smoke/regression check for the changed path.

`sky_break.py` can produce one-edit mutants for the following deep audit set:

* OCEAN pre-cloud draw count 11->12 and type-5 6->9;
* remove `+albedo`;
* alter the smallest-reachable cloudy-pixel denominator/scaling or its clamp;
* byte-wise rather than dword-carry smoothing;
* out-of-place instead of in-place smoothing;
* 320/360 stride substitution;
* `lssmooth` dropping `i+1`/`i+361`, or clamping the tail read;
* horizon 120->119 and 120->121, width 360->359/361, premature integer division,
  and omit the night divide-by-two.  A pure binary32 multiply/divide reassociation
  is not a valid falsifier here: exhaustive `b=0..63,row=0..119` evaluation gives
  the same chopped byte for every source-reachable pair, including the night path;
* boolean/buffer atmosphere mix-up;
* palette destination redirected from `srfpal6` to `pal6`;
* round-to-nearest in a chop site;
* remove the type-3 night control transfer;
* wrong RNG seed/stream, stale type-5 brightness, missing `QUADWORDS` restore, and an
  SBG write at offset 64800.

When the deep audit is run, each mutant should be killed by a named corpus row and record/
field, not merely by an aggregate SHA mismatch. This is optional diagnostic evidence.

### C. Lino production and runner

Implement `work/sky.txt` against delivered `SU`, `PAL`, RNG, and framebuffer APIs.
It receives all caller state through documented `GRSK*` variables bound by the game;
it must not parse corpus data. Keep source loop order and alias behaviour visible in
small labelled fragments. Save/restore `QUADWORDS` on every return path.

Implement `work/skymain.txt` plus `GRSKH*` parser/dumper in that file. It realises the
29-unit record, deterministic tail, phase hooks, framing, replay load, and D/R/J runs.
It must reject malformed input rather than partially execute it. Mutant builds replace
one library with one edited copy; the driver and corpus remain byte-identical.

## 9. Acceptance tests

The durable `tests/test_sky.py` records the historical deep closeout below. Routine work uses
one focused smoke/regression check covering the changed path; the full suite, mutation matrix,
and 11-item list are not required for every fix. Use the full list when explicitly choosing a
deep sky audit:

1. Corpus schema/version/framing validation, including malformed-input negative tests.
2. Python determinism, repeated-row independence, tail-preservation, and exact draw
   ledger assertions.
3. C == Python for every graded record and field.
4. Lino == Python == C for D, including pre-horizon, final SBG, defined palette,
   scalars, ledger, and guards.
5. Anchor final SBG and palette equal the two captured hashes and bytes; perturbing
   anchor seed or albedo proves the comparison is live.
6. R pages agree independently and J pages agree after D and R pass.
7. Anchor band witnesses at rows 119/120 and bottom rows, plus no write past 64,800.
8. Zero/hostile tail companions prove the intended overread path while preserving
   tail and outer canaries.
9. `QUADWORDS` equals `quadwords_in` after every case, including early/airless paths.
10. All required C and Lino one-edit mutants are killed at their declared witness.
11. A quiet-machine suite run reports no unregistered test and no regression in
    `test_surface.py` or `test_spheres.py`.

Screenshots and playtest captures are product feedback, not additional oracle construction.
For deep audits, dispatch/ledger and pixels remain useful separate diagnostics; routine
acceptance should stay proportional to the changed behavior.

## 10. Claim boundary

With the current evidence, the only byte-exact NIV+ R2.3 claim is:

> For the reconstructed output-driving inputs of the pinned landed type-3 OCEAN/night
> capture, `create_sky` produces the captured 64,800-byte final `s_background` and the
> captured 768-byte `surface_palette` exactly.

The pre-horizon buffer, scalar ledger, and joined page are source-model/port attribution
evidence unless separately captured. Synthetic cases establish source fidelity, branch
coverage, and mutation strength, not NIV+ binary identity. Whole screenshots remain
bounded visual evidence. Undefined/unhandled palette branches have no byte-exact claim.

## 11. Fixture qualification gate

The original demand for complete RAM recovery cannot be satisfied because the old
night RAM image was not retained.  It must not be silently replaced with the later day
RAM.  The narrower binary-output gate is acceptable only when all of these hold:

* the output-driving night inputs above reproduce both captured byte arrays;
* the anchor is not flagged `LIVE_REACHABLE` and carries no scalar exactness claim;
* changing scalar poison leaves the anchored pixels/palette unchanged;
* a separating seed perturbation and a source-reachable albedo perturbation both make
  the binary comparison fail; and
* the exact anchor case ID/count is required, so an anchor-free stream cannot pass the
  named binary grader vacuously.

The later day diagnostic remains external live whole-state evidence.  A future night
RAM recapture may strengthen the anchor's state claim, but is not required for the
strictly bounded pixel/palette claim above.
