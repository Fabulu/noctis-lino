# NIVGEN accuracy procedure

> **Service availability (2026-08-14):** NIVGEN is live again. A failed live
> request is an offline-state signal, not a transient error to retry. Record it
> once, stop contacting the service, and continue from the most recent saved
> snapshot until the project owner confirms that the host is back.

This repository can drive its current production Noctis generator through the
public NIVGEN planet corpus. The goal is full, auditable accuracy against the
original implementation, not a low error count obtained by omitting outputs.

## Public reference

- [NIVGEN planet sheet](https://litterbox.moos.es/sheet.html?sheet=nivgen_planets)
- [Machine-readable sheet](https://litterbox.moos.es/sheets/nivgen_planets?page=1&pageSize=500)
- [Published LR harness at commit 01c6a3a](https://github.com/jorisvddonk/noctis-iv-lr/blob/01c6a3a/src/harness.cpp)
- [SheetBot help](https://litterbox.moos.es/help.html)

The public harness accepts star coordinates, body index, landing longitude and
latitude, a pinned `secs` value, optional scenario/albedo/night overrides, and
an optional 16-byte far-heap gap. User-facing Parsis Y is negated before the
system generator receives it.

The scored FNV-1a boundaries are:

| Field | Bytes |
| --- | ---: |
| Orbital surface | 46,080 |
| Atmosphere overlay | 32,400 |
| Relevant palette band | 192 |
| Landed heightmap | 40,000 |
| Landed object chart | 40,000 |
| Landed surface texture | 65,024 |
| Landed sky | 46,080 |

The surface texture boundary is exactly `254 * 256`. It excludes the final two
rows, including the four tail bytes that NIV vanilla and NIV+ can derive from
nondeterministic reads. Do not broaden this into a fuzzy comparison, and do not
introduce host-language uninitialized memory to imitate it.

The 16-byte allocation gap after the heightmap is separate from the texture
tail. It is an explicit generator input because the original inclination loop
can read it. The public sheet exposes the original gap for both landing sites.

## Local commands

`tools/nivtest.py` builds a derived headless main from `work/vhgame.txt`, links
`work/vhnivgen.txt`, and runs the real production topology, orbital surface,
landed surface, and sky implementations. Python handles command-line parsing,
low-byte packing, hashes, and raw dump names only.

```powershell
python tools\nivtest.py planet -x -1996209872 -y 55508 -z 816148 -p 0 --build
python tools\nivtest.py planet-all -x -1996209872 -y 55508 -z 816148
python tools\nivtest.py sector -x -1996209872 -y 55508 -z 816148 -p 0 -lon 0 -lat 60
python tools\nivtest.py surftex -x -1996209872 -y 55508 -z 816148 -p 0 -lon 301 -lat 68
```

`nivtest.py` normally rebuilds and runs the local Windows harness. A remote
worker can instead pass `--exe /path/to/nivtest` or set
`LINO_NIVTEST_EXE`. This keeps one generator implementation: the executable is
still compiled from the production `vhgame.txt` library graph plus
`work/vhnivgen.txt`, while Python only supplies the public command protocol and
hash boundaries.

For the contributor's macOS x86_64 compiler/runtime container:

```sh
./build/build_nivtest.sh
./tools/nivlin planet -x -1996209872 -y 55508 -z 816148 -p 0
```

The build script transfers only tracked `.txt` sources and the derived main to
the isolated compiler container. `tools/nivlin` is the SheetBot-facing command;
it executes the resulting `build/nivtest` binary through the same production
protocol used by local scoring. Do not deploy the older standalone
`work/nivlin.txt` or `work/nivlinvh.txt` generators: they duplicate generation
logic and the live sheet currently demonstrates that they have drifted far
behind this implementation.

Use `-dump DIR` for the public lowercase raw names. Setting `NIVDUMP` produces
the uppercase Rust-style names as well. `-secs`, `-sc`, `-albedo`, `-night`,
and `-gap` mirror the published harness inputs.

`tools/nivgen_sheet_report.py` is the complete-corpus audit layer. It fetches at
most 500 rows per request, waits one second between sequential pages by default,
never retries, validates the page schema and unique row keys, and writes a
canonical snapshot with a stable SHA-256. Repeated reports and before/after
comparisons use snapshots without contacting the service.

```powershell
# Fetch all 5,188 rows once, retain the canonical input and aggregate report
python tools\nivgen_sheet_report.py --live --snapshot-out nivgen-sheet.json --json-out nivgen-report.json

# Reproduce the same report without a network request
python tools\nivgen_sheet_report.py --snapshot nivgen-sheet.json

# Classify every row and field transition from an older snapshot
python tools\nivgen_sheet_report.py --snapshot nivgen-sheet-new.json --compare nivgen-sheet-old.json --json-out nivgen-diff.json
```

The report distinguishes the sheet's visible zero-error marker from independent
hash exactness. During original backfill, a row with no authoritative hash can
show zero errors; it is reported as unavailable, never as an accuracy success.

`tools/nivgen_score.py` downloads the live sheet, extracts coordinates from the
original artifact URLs, supplies each original gap, and compares Lino hashes to
every non-null original field it generated.

The original artifact filenames are authoritative for both the system
coordinates and the random landing longitude/latitude. The sheet's separate
`rand_lon` and `rand_lat` columns can describe a newer requested site while its
retained original hashes and PNG URLs still describe the older captured site.
Comparing those columns to the retained hashes produces convincing but false
terrain failures. The scorer therefore reads the random site from
`orig_rand_*_<body>_<lon>_<lat>_*.png` when that evidence is available, records
the chosen site in its JSON report, and uses the columns only as a fallback.
Rows with no original hashes are not scoreable and are skipped. Cached API JSON
may contain a UTF-8 BOM and is accepted without altering the snapshot.

```powershell
# One deliberate smoke row
python tools\nivgen_score.py --limit 1 --planet-only

# The same smoke without another network request
python tools\nivgen_score.py --sheet-json PATH\TO\nivgen-planets.json --limit 1 --planet-only

# Deliberately read every live API page once
python tools\nivgen_score.py --all-pages --limit 1 --planet-only

# One complete type-2 row, including its random landing
python tools\nivgen_score.py --type 2 --limit 1

# A larger local batch with a machine-readable report
python tools\nivgen_score.py --sheet-json PATH\TO\nivgen-planets.json --type 2 --rust-errors-only --limit 25 --json-out nivgen-type2.json

# Score every field in the pinned type-1/type-5 selection, then compare the
# local hashes with the Lino hashes retained in that exact snapshot
python tools\nivgen_score.py --sheet-json nivgen-sheet.json --type 1 --type 5 --limit 1648 --build --json-out nivgen-type1-type5.json
python tools\nivgen_score_transition.py nivgen-sheet.json nivgen-type1-type5.json --executable RETAINED-SCORED-EXECUTABLE --source-revision "REVISION plus described working state" --source-state NIVTEST-SOURCE-CLOSURE.sha256 --source-state NIVTEST-DIRTY-SOURCE.patch --source-state SCORE-RUN.txt --source-state tools\nivgen_score.py --source-state tools\nivtest.py --source-state tests\linoharness.py --json-out nivgen-type1-type5-transition.json
python tools\nivgen_score_compare.py PREVIOUS-SCORE.json nivgen-type1-type5.json --before-transition PREVIOUS-TRANSITION.json --after-transition nivgen-type1-type5-transition.json --json-out score-to-score-comparison.json
```

`nivgen_score_transition.py` rejects duplicate or unknown row keys, expected
hashes from a different snapshot, invalid match flags, and inconsistent score
totals. Its report records the snapshot, score, and executable SHA-256 values,
plus the SHA-256 and byte length of each repeatable `--source-state` artifact.
For a dirty score, retain both a complete transitive source-closure manifest and
a closure-only patch; a revision description alone is not exact provenance. Bind
the exact scoring driver as additional source state too: `nivgen_score.py`,
`nivtest.py`, and `tests/linoharness.py` determine selection, arguments, output
boundaries, and hashes even when the executable was built earlier. Retain and
bind a short run record with the exact command, interpreter, platform, and the
hashes of those inputs; the score JSON alone does not record them.
The report also records comparison and whole-row exactness before and after the
local run, changed values, field transitions, and remaining mismatch-field
clusters by body type. It compares only fields actually emitted by the selected
score, so an omitted field is never presented as an accuracy success.

`nivgen_score_compare.py` compares two retained scores over the same selection
and requires identical authoritative hashes. It validates every stored match
flag and aggregate total, then records exact fixes, exact regressions,
wrong-value-to-different-wrong-value transitions, whole-row transitions, and
reported zero-seed metadata. Optional transition arguments prove that each
source-state transition is bound to the score it claims to describe.

The default limit is one. A live corpus sweep is a release or explicit accuracy
run, not a routine edit gate. Each live page is requested at most once. The
scorer never retries or polls an unavailable host. Prefer `--sheet-json` for
repeated local work against a deliberately saved snapshot. `--all-pages` is
explicit because the API is paginated; it makes exactly one request for each
advertised page, waits one second between pages by default, and stops immediately
if any page is unavailable. Prefer `nivgen_sheet_report.py` when the goal is a
complete canonical snapshot rather than executing a bounded local sample.

## Current measured position

The 5,188-row canonical snapshot taken on 2026-08-21 has SHA-256
`ab73b236957f225247e07460eaae1a7e26891e701d6b5bd4c93d573208231f97`.
The sheet shows 1,068 Lino zero-error markers, but 642 of all rows are not yet
backfilled with any authoritative hashes. Independent comparison therefore
finds 426 fully exact Lino rows among 4,546 comparable rows (9.4%), not
1,068/5,188. Rust is 4,246/4,546 (93.4%). LR has no fully exact comparable row
in this snapshot and is missing results on 175 rows; its 613 visible zero-error
markers are all unbackfilled rows.

Lino's dominant field gaps are orbital surface at 401/4,485, palette at
2,622/4,485, default heightmap at 2,895/4,546, random heightmap at
3,233/4,546, and random object chart at 3,439/4,546. Atmosphere is
3,627/4,485. Default object charts, textures, and skies are near exact but still
retain eight, one, and two mismatches respectively. Full exactness is
concentrated in comparable types 3 (174/220), 9 (192/215), and 10 (59/61);
types 0, 1, 4, 5, 6, 7, and 8 currently have none.

Backfill explains why the visible result appeared to get worse while adding
checkmarks. The previous 2026-08-20 marker count was 1,128; as authoritative
hashes replaced no-data rows, it fell to 1,068 and exposed new mismatches. Use
the independent hash counts and snapshot diff, not zero-error markers, for
release claims.

The seven-field production diagnostic remains exactly:

```text
surf=390A2CCB atmo=114562E8 pal=26961E4A hm=97022FD7
oc=22913F4E stex=0D52F001 sky=1E308D29
```

That fixture and the selected 114/118 historical sample below are smoke tests
only. They do not supersede the full-sheet result.

### Current type-1/type-5 repair evidence

The fractional-crater replacement restores the complete authoritative default
heightmap FNVs `FDDDF3A2` (type 1) and `301D7754` (type 5). Its independent
deep gate uses the authoritative type-5 `random(5) * 0.015` factor rule and
matches the integer operation mirror against historical x87 on all 9,564,210
reachable base/exponent pairs. A separate compiled-Lino gate covers 4,096
boundary and spread cases with exact outputs and intact soft-stack state; see
`docs-notes/TRANSCENDENTALS.md` for the arithmetic contract.

The complete retained power-fixed run scores all eleven fields on 1,017 type-1
and 631 type-5 rows. It reaches 18,120/18,128 exact comparisons and
1,646/1,648 fully exact rows, up from 11,120/18,128 and 0/1,648 in the sheet
snapshot. Field exactness is surface, atmosphere, palette, default texture all
1,648/1,648; default heightmap, default object chart, default sky, random
heightmap, random texture, and random sky all 1,647/1,648; and random object
chart 1,646/1,648.

Against the retained post-zero-quotient score, the exact-power-of-two repair
changes 209 values: 174 random heightmaps and 35 random object charts, all exact
repairs, with zero regressions and zero wrong-to-different-wrong transitions.
Fully exact rows rise from 1,473 to 1,646. The snapshot, score, executable,
source-closure manifest, dirty-source patch, transition, comparison, and run
record SHA-256 values are respectively:

```text
ab73b236957f225247e07460eaae1a7e26891e701d6b5bd4c93d573208231f97
b118f2530e260faf6dd550f338d8b9c6c9e0dba0029e85e1bcc0c801049af719
8fd1f4617fe652414bdeb87ad80d860b87c9bfff7ef1d605a663013b9ad99523
9b9438a78c89f8b33fb2c64450adb13fe744f37f2f6213151acc59d421553d86
76c0df790117a5b33b6781930071b74002bba6e4f9c4d135cfa252d356c7b044
d79805fdd9f63c25469c935ff38dbb26dbe204d1535b7034046daf7f896f4853
c7c226a6f62104e9831242149c01dbe6737082663d3cffbe9cc4788348f0bae1
499df1e38c0a7d7852626f318bb728b7484f428b9131b2d9ce60dc542b5d5863
```

The retained artifacts are
`tests/gen/nivgen-pow-type1-type5-power2-base-score.json`,
`tests/gen/nivgen-pow-type1-type5-power2-base-transition.json`,
`tests/gen/nivgen-pow-type1-type5-post-zero-to-power2-base-comparison.json`,
and `tests/gen/nivgen-pow-type1-type5-power2-base-score-run.txt`. The score was
executed offline in sixteen independently retained 103-row shards. On Windows,
each native child ran on a private inactive desktop so the sweep could not take
focus from the active user desktop.

Only two corpus rows remain. `XENOFELYS|4` differs in default heightmap, object
chart, and sky plus random heightmap and object chart. `XENOFELYS|10` differs in
random object chart, texture, and sky. Their other fourteen fields are exact,
including both orbital outputs, both palettes, both atmosphere overlays,
`XENOFELYS|10`'s default sector, and its repaired random heightmap. These rows
also break otherwise complete corpus invariants: 630/631 type-5 default
heightmaps are `301D7754`, while `XENOFELYS|4` alone retains `54297E41`; and
1,016/1,017 type-1 random skies are `7B252DC5`, while `XENOFELYS|10` alone
retains `CBD77DB5`. Preserve those authoritative outliers. The next diagnostic
must locate the first state divergence against a fresh original/reference
trace; it must not introduce body-, coordinate-, or expected-hash-specific
behavior.

The published sky images sharpen that boundary. The `XENOFELYS|4` default and
random original PNGs are byte-identical (SHA-256
`bbfe0cf853619cc6e24e73eff156be083f652351cf1ea6e460e385015c0d49e7`) even
though their retained raw-sky FNVs differ. For `XENOFELYS|10`, the random target
`CBD77DB5` is exactly the FNV-1a of the 46,080-byte zero sky (`7B252DC5`) with
one byte changed: offset 12,167, coordinate `(287,33)`, value 80. Its published
PNG likewise differs from the default black sky by exactly that one pixel, RGB
`(101,109,122)`. The retained analysis record is
`tests/gen/nivgen-xenofelys-sky-residual.json` (SHA-256
`56ce497edfdf4f3fe10415e64bc481bd099cfea9dc79f31e17d7d6a9da5bc333`).
This is evidence for a caller/capture overlay or context difference, not
permission to add a body-specific pixel. A fresh original trace must establish
which caller writes that byte and must regenerate or confirm both outlier rows
before changing production.

## Historical bounded measurements -- **SUPERSEDED**

**Bounded measurement from 2026-08-19.** A fresh isolated harness derived from
the current `work/vhgame.txt` matches the seven-field diagnostic fixture exactly:

```text
surf=390A2CCB atmo=114562E8 pal=26961E4A hm=97022FD7
oc=22913F4E stex=0D52F001 sky=1E308D29
```

One saved public row of every type 0 through 10, including default and arbitrary
landing coordinates where available, matches 114/118 scored fields. Types 0, 2,
3, 4, 6, 7, 8, and 9 are 11/11; type 5 is 10/11; type 1 is 8/11; type 10 is
8/8. The four exact failures are:

```text
type 1 default hm  89FF166B != FDDDF3A2
type 1 random hm   2CA3DC97 != BAD7DDAC
type 1 random oc   51876015 != 2DA704F7
type 5 default hm  4FAFAB45 != 301D7754
```

All four reproduce with the current source linked to hardware x87
transcendentals and with the pre-transcendental FP build. An older harness still
matches at least the type-1 default heightmap. The misses therefore remain a
separate current-source/runtime delta to isolate; they are not attributed to the
portable transcendental replacement, and no public hash or acceptance boundary
is weakened. See `docs-notes/TRANSCENDENTALS.md` for the replacement's exact
acceptance contract.

On 2026-08-17 the public sheet exposed Lino results, but they were not yet the
output of this repository's current local harness. In the first 2,000 rows,
1,269 had Lino results and none was perfect; the largest failures included both
landed surface-texture fields. A fresh local replay of the same live type-2 row
matched all 11 original hashes. No upstream PR, public fork, or NIVGEN branch
was visible in either this repository or the original Linoleum repository at
that time. Treat the public Lino column as an integration bring-up until the
announced upstream patch arrives and its runner is identified with the current
source and executable hash.

The sheet is live, so all counts require a timestamp. On 2026-08-14 the API
advertised 7,616 rows. Its first 2,000-row page had Rust results for 1,312 rows:
98 rows had 254 mismatched fields, including 85 type-2 rows. This is a
page-limited snapshot, not a complete current leaderboard count. Rust was the
accuracy leader in the inspected snapshot.
Its orbital surface, atmosphere, palette, default heightmap, default surface
texture, and all sky hashes were exact on its completed rows. Most misses were
type-2 random landed heightmaps, object charts, and surface textures, with a
small number of object-chart misses on types 1, 4, and 5.

After matching the published call boundaries, the first production Lino
type-2 smoke matched all 11 scored hashes:

- orbital surface, atmosphere overlay, and palette band
- default heightmap, object chart, surface texture, and sky
- random-coordinate heightmap, object chart, surface texture, and sky

That is encouraging because those fields are the current leader's largest
public gap. It is one row, not yet a corpus-wide claim.

One representative public row for every planet type 0 through 9 now matches
all 11 scored hashes, including both landed coordinates. This is representative
coverage, not a claim that the complete live corpus is already perfect.

The live sheet also contains type-10 companion-star rows. Their orbital oracle
fields can be absent because `surface()` is a no-op, so only non-null fields are
graded. Five sampled type-10 rows match all 40 available landed hashes. A second
breadth point for each ordinary type 0 through 9 matches all 110 hashes. This
sample exposed and fixed the stale random-coordinate scoring error above; it did
not require a generator exception or a planet-specific output change.

A bounded 2026-08-14 pass selected ten type-2 rows where Rust had public
errors. Lino matches all 110 original hashes. Eight systems were exact
immediately. The remaining two were moons in `NOCHUT`, whose stellar identity
is `3,546,965,295.741...`, beyond signed 32-bit. Borland's `__ftol` performs a
qword integer store and returns its low bits; the old specialized identity
helper used a dword store and therefore selected class 0 instead of class 9.
Restoring the qword conversion made both rows exact across orbital output and
both landed sites. This is still a bounded first-page result, not a full-corpus
claim.

The sweep then covered the remaining 75 first-page type-2 rows where Rust had
public errors. After one source-memory correction, all 85 selected rows match
all 935 original hashes. This includes orbital surface, atmosphere, and palette
plus both sites' heightmap, object chart, surface texture, and sky. It is exact
coverage of that dated first-page subset, not a claim about all 7,616 rows.

Three random-site object charts initially missed while their other ten fields
were exact: `MAAREN|8`, `VENE'EREIB|36`, and `SADA'UKEIRIT|63`. A focused
Borland C++ 3.1 NIV+ build reproduced MAAREN's public `B4FA7DB8` height hash and
`3CB001B1` object hash. Raw comparison found only four object-byte differences.
The root was `felisian_srf_darkline()`: the source checks its centre location
against the 40,000-byte map but writes the four neighbours without additional
bounds checks. At the south edge, `location + 200` crosses the 16-byte allocator
header and writes into the adjacent object chart. That changed one class byte;
the later inclination loop read it back and changed three more object counts.
Lino now performs the same writes in explicit flat memory. It models the
historical spill deterministically and does not depend on uninitialized host
memory.

The other 13 first-page rows carrying Rust errors cover types 1, 4, 5, 6, and
9. They match all 143 original hashes without further changes. Combined with
the type-2 result, Lino matches all 1,078 scored hashes across every one of the
98 leader-error rows in the saved first page. This is the most useful public
competitive subset because each row contains at least one field the current
leader misses. It still does not replace a complete 7,616-row run or hidden
holdout.

The landed fixes behind that result are source-level corrections rather than
fixture exceptions:

- Type 1 needed the exact `std_crater` x87 opcode and signed negative-radius
  bounds.
- Types 1 and 4 exposed `rockyground`'s source cutoff. Positive and negative
  levels both apply `value >= abs(level)` before adding the signed level.
- Type 5 needed Borland's argument evaluation order and the source albedo
  reduction of roughness.
- Type 7 needed the original expression and function-argument random draw
  order for craters and dark lines.
- Type 8 reaches the type-3 `similar:` label with `goto`. After that inner
  switch exits, NIV+ consumes one shared `random(5)` draw before the common
  crevasse pass. Omitting it left the planet texture exact but shifted every
  landed post-pass draw.

For the type-8 diagnosis, an isolated Borland C++ 3.1 build of the NIV+
`planetdump` source wrote the original 40,000-byte heightmap and object chart
at the clean `build_surface()` return boundary. Their FNV-1a hashes were
`D035342C` and `2FA9DADD`, exactly matching the public sheet. A temporary
per-hill trace then proved all 136 Lino hills already matched NIV+; the first
difference appeared in the shifted shared crevasse pass. After restoring the
missing draw, both the default and random public sectors became 11 for 11.

These are deliberate smoke rows, not yet corpus-wide accuracy claims. Larger
per-type sweeps still belong at stable accuracy milestones and before release.

Two source-state details were decisive. The `planet` command calls `surface()`
immediately after system preparation, while the shared `plx` and `plz` scratch
coordinates are still zero. It must not pre-position the body as gameplay does.
The `surftex` command fills the sky and calls `create_sky()` directly; it does
not apply planetary_main's later 120-row horizon pass. The Lino driver keeps
both benchmark-only boundaries separate from normal gameplay.

A third boundary matters for moons. The NIV+ landing handoff first calls
`surface()` while `p_background` still points at the 65,552-byte planet
allocation, then `planets()` regenerates the selected body after swapping the
pointer to the 64,800-byte moon allocation. Moon `lssmooth()` reads 41 bytes
past the visible map, through 12 bytes of paragraph slack and a 4-byte Borland
heap header into the first pass's live map. On `SOTETI III|21`, that changes one
`randoface()` decision, advances the Borland stream by two draws, and changes
the palette hash from `1D1FDD34` to the original `C6E1BAA8`. The production
Lino NIVGEN driver now reproduces this two-pass buffer history explicitly. Its
focused cached-sheet result is 11 exact fields out of 11; no host uninitialized
memory or fixture-specific adjustment is used.

The leading upstream suspect is the eleven floating-point system/body
properties that `test_nearstar.py` has historically left outside its exactness
claim. They feed orbital `seedval`, the planet viewpoint, the global landed
surface seed, and sky geometry. Fix the generating arithmetic and rounding
boundaries. Never key code to sheet stars, bodies, coordinates, or expected
hashes.

## Submission procedure

1. Pin the source commit and build the headless executable from a clean tree.
2. Record the executable SHA-256, compiler version, x87 control mode, sheet
   timestamp, and exact command line.
3. Run a small public smoke, then the complete public corpus.
4. Keep raw artifacts for every mismatch and report coverage beside accuracy.
5. Run an unseen local holdout before publishing a claim.
6. Submit only fields the runner actually emits, but do not present omitted
   fields as accuracy successes.

SheetBot runs remotely supplied task code. Use a clean isolated worktree or VM
with no personal credentials. Give it only the benchmark API key, pin tool
versions, copy out the generated artifacts, and discard the worker afterward.
Do not run it in the main development checkout.

## Organizer questions still open

The public material does not define the prize deadline, scoring weights,
tie-break, hidden holdout, failure/timeout policy, exact original binary and
DOSBox/x87 environment, or the NIVGEN-specific SheetBot capability contract.
Before submission, ask the organizer for those details and whether PNGs are
judged or merely displayed.

Also confirm why original gaps vary from the LR harness's documented default
and whether the 65,024-byte surface texture hash is the permanent scoring mask.
