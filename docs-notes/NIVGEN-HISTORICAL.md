# NIVGEN historical evidence

> Archived on 2026-08-22. This material is retained for provenance and is not part of the active project plan. NIVGEN is deferred indefinitely; do not resume it without a new explicit direction.


The local investigation is deferred as of 2026-08-22 at the user's direction.
Historical game semantics and the distinct public-artifact compatibility policy
are now measured and retained; the final 22 fields require the unpublished exact
NIVTEST harness/executable or paired upstream captures. Do not resume corpus
sweeps, add fixture-specific answers, omit fields, or weaken comparisons without
a new explicit user direction. Continue the actionable project docket.

`docs/NIVGEN.md` remains the operating procedure only if the boundary is
explicitly reopened;
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
on macOS. The patch was substantively reviewed, merged as `68dea51`, and retained
exact Windows surface hashes and all Wave 5 palette checks. The Apple-Silicon
Rosetta workflow dumps the selected 192-byte palette and rejects both uniform
`0x3f` white and any other uniform value before packaging. Hosted Rosetta runs
passed this gate, and the hardened NIVGEN worker subsequently confirmed the
non-white palette and corrected CPU-pack provenance in production.

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
