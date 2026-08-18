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
- [Machine-readable sheet](https://litterbox.moos.es/sheets/nivgen_planets?page=1&pageSize=2000)
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
```

The default limit is one. A live corpus sweep is a release or explicit accuracy
run, not a routine edit gate. Each live page is requested at most once. The
scorer never retries or polls an unavailable host. Prefer `--sheet-json` for
repeated local work against a deliberately saved snapshot. `--all-pages` is
explicit because the API is paginated; it makes exactly one request for each
advertised page and stops immediately if any page is unavailable.

## Current measured position

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
