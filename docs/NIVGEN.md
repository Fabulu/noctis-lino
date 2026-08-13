# NIVGEN accuracy procedure

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
python tools\nivtest.py sector -x -1996209872 -y 55508 -z 816148 -p 0 -lon 0 -lat 60
python tools\nivtest.py surftex -x -1996209872 -y 55508 -z 816148 -p 0 -lon 301 -lat 68
```

Use `-dump DIR` for the public lowercase raw names. Setting `NIVDUMP` produces
the uppercase Rust-style names as well. `-secs`, `-sc`, `-albedo`, `-night`,
and `-gap` mirror the published harness inputs.

`tools/nivgen_score.py` downloads the live sheet, extracts coordinates from the
original artifact URLs, supplies each original gap, and compares Lino hashes to
every non-null original field it generated.

```powershell
# One deliberate smoke row
python tools\nivgen_score.py --limit 1 --planet-only

# One complete type-2 row, including its random landing
python tools\nivgen_score.py --type 2 --limit 1

# A larger local batch with a machine-readable report
python tools\nivgen_score.py --type 2 --limit 25 --json-out nivgen-type2.json
```

The default limit is one. A live corpus sweep is a release or explicit accuracy
run, not a routine edit gate.

## Current measured position

The sheet is live, so all counts require a timestamp. On 2026-08-13 it exposed
more than 1,500 rows. Rust was the accuracy leader in the inspected snapshot.
Its orbital surface, atmosphere, palette, default heightmap, default surface
texture, and all sky hashes were exact on its completed rows. Most misses were
type-2 random landed heightmaps, object charts, and surface textures, with a
small number of object-chart misses on types 1, 4, and 5.

The first production Lino type-2 smoke matched all six landed hashes:

- default heightmap, object chart, and surface texture
- random-coordinate heightmap, object chart, and surface texture

That is encouraging because those fields are the current leader's largest
public gap. It is one row, not yet a corpus-wide claim. On the same row Lino's
orbital fields and sky missed. A type-1 smoke matched atmosphere and sky but
missed the other fields. These mismatches are now actionable output from the
real executable rather than predictions from the Python or C transcriptions.

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
