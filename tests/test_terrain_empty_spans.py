"""Empty projected terrain spans preserve polymap's visible side effects."""

from __future__ import annotations

from itertools import product
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
PROJECTION = ROOT / "work" / "pgproj.txt"
GROUND = ROOT / "work" / "vhground.txt"
SCRATCH_TINTA = 63_996
SCRATCH_ESCRESCENZE = 63_997

sys.path.insert(0, str(HERE))
import linoharness as lh  # noqa: E402


def trace_writes(spans: tuple[tuple[int, int], ...],
                 tinta: int = 0x35, escrescenze: int = 0x71
                 ) -> tuple[tuple[int, int], ...]:
    writes = [(SCRATCH_TINTA, tinta), (SCRATCH_ESCRESCENZE, escrescenze)]
    for row, (left, right) in enumerate(spans):
        if right - left > 0:
            writes.extend((row * 320 + column, row)
                          for column in range(left, right))
    return tuple(writes)


def terrain_span_writes(spans: tuple[tuple[int, int], ...]
                        ) -> tuple[tuple[int, int], ...]:
    if not any(right - left > 0 for left, right in spans):
        return ((SCRATCH_TINTA, 0x35), (SCRATCH_ESCRESCENZE, 0x71))
    return trace_writes(spans)


def section(source: str, start: str, end: str) -> str:
    return source.split(start, 1)[1].split(end, 1)[0]


def main() -> int:
    checks = lh.Check("empty terrain span specialization")

    cases: list[tuple[tuple[int, int], ...]] = []
    pairs = tuple(product(range(-2, 3), repeat=2))
    cases.extend((pair,) for pair in pairs)
    cases.extend(product(pairs, repeat=2))
    state = 0x243F6A88
    for _ in range(20_000):
        rows = []
        for _ in range(1 + (state & 7)):
            state = (state * 1664525 + 1013904223) & 0xFFFFFFFF
            left = (state >> 24) - 128
            state = (state * 1664525 + 1013904223) & 0xFFFFFFFF
            right = (state >> 24) - 128
            rows.append((left, right))
        cases.append(tuple(rows))

    differences = [spans for spans in cases
                   if terrain_span_writes(spans) != trace_writes(spans)]
    checks.eq(differences, [],
              "empty-span exit and full trace have identical page writes")
    checks.ok(trace_writes(((2, 2),))[:2] == (
                  (SCRATCH_TINTA, 0x35), (SCRATCH_ESCRESCENZE, 0x71))
              and len(trace_writes(((2, 2),))) == 2,
              "zero-width rows still write both visible polymap scratch bytes")
    missed_row = ((4, 4), (7, 8))
    checks.ok(len(trace_writes(missed_row)) == 3
              and not all(right - left <= 0 for left, right in missed_row),
              "the discriminator catches a positive span after an empty row")

    projection = PROJECTION.read_text(encoding="utf-8")
    ground = GROUND.read_text(encoding="utf-8")
    prebasis = section(projection,
                       "The texture basis depends only on the original rotated vertices.",
                       '"PG pm basis"')
    terrain_scan = section(projection, '"PG pm terrain edges"', '"PG pm basis"')
    postbasis = section(projection, '"PG pm k"', '"PG pm out"')
    mapped = section(ground, '"VHGND terrain mapped"',
                     '"VHGND terrain facing"')
    generic = section(ground, '"VHGND terrain mapped generic"',
                      '"VHGND secondary sun setup"')

    checks.ok(all(fragment in prebasis for fragment in (
                  "A = [SPterrain]; ? A = 0 -> PG pm basis;",
                  "A = [SPhalf]; ? A = 0 -> PG pm terrain edges;",
                  "[SPterrain] = 0; -> PG pm basis;",
              )), "only non-halfscan terrain enters the edge-first specialization")
    checks.ok(all(fragment in terrain_scan for fragment in (
                  "=> PG edges;",
                  "[SPi] = [BXminy];",
                  "D - E; [SPsec] = D; ? D > 0 -> PG pm basis;",
                  "? A '<= [BXmaxy] -> PG pm terrain span;",
                  "A = PGSCRT; A + PGDOFF;",
                  "A = PGSCRE; A + PGDOFF;",
                  "[PJgate] = 0; -> PG pm out;",
              )), "empty terrain scans every row and preserves trace's scratch writes")
    checks.ok("A = [SPterrain]; ? A != 0 -> PG pm traced;" in postbasis
              and postbasis.count("=> PG edges;") == 1
              and postbasis.index("=> PG edges;") < postbasis.index('"PG pm traced"'),
              "positive terrain spans reuse their exact precomputed edges")
    checks.ok("[SPterrain] = 0;" in mapped
              and "[SPterrain] = 1; [PJpreproject] = 1;" in mapped
              and mapped.index("=> VHGND terrain cached bounds;")
              < mapped.index("[SPterrain] = 1; [PJpreproject] = 1;")
              and "[SPterrain] = 1;" not in generic,
              "only the cached preprojected terrain path enables the specialization")

    return checks.done()


if __name__ == "__main__":
    raise SystemExit(main())
