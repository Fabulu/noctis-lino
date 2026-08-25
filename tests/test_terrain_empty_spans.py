"""Empty projected terrain spans preserve polymap's visible side effects."""

from __future__ import annotations

from itertools import product
from pathlib import Path
import struct
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


def f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def edge_limits(vertices: tuple[tuple[int, int], ...], min_y: int, max_y: int
                ) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Run PG edges' exact wide-accumulator schedule over one polygon."""
    ipart = {row: 311 for row in range(min_y, max_y + 1)}
    fpart = {row: 5 for row in range(min_y, max_y + 1)}
    closed = vertices + (vertices[0],)
    for (x1, y1), (x2, y2) in zip(closed, closed[1:]):
        if y2 < y1:
            x1, y1, x2, y2 = x2, y2, x1, y1
        if y2 == y1:
            continue
        kx = f32((x2 - x1) / (y2 - y1))
        if y1 < 10:
            x1 = round(float(x1) + float(10 - y1) * kx)
            ity = 10
        else:
            ity = y1
        jty = min(y2, 190)
        bndx = float(x1)
        if ity >= jty:
            continue
        for row in range(ity, jty + 1):
            column = max(-10_000, min(10_000, round(bndx)))
            if row in fpart and column > fpart[row]:
                fpart[row] = 311 if column >= 311 else column
            if row in ipart and column < ipart[row]:
                ipart[row] = 5 if column <= 5 else column
            bndx += kx
    return (tuple(ipart[row] for row in range(min_y, max_y + 1)),
            tuple(fpart[row] for row in range(min_y, max_y + 1)))


def discriminator_page(ipart: tuple[int, ...], fpart: tuple[int, ...], min_y: int
                       ) -> bytes:
    """Apply one deterministic span payload to the complete indexed page."""
    page = bytearray([0xA7]) * 64_000
    page[SCRATCH_TINTA] = 0x35
    page[SCRATCH_ESCRESCENZE] = 0x71
    for offset, (right, left) in enumerate(zip(ipart, fpart)):
        row = min_y + offset
        for column in range(right, left):
            page[row * 320 + column] = (row * 17 + column * 29) & 0xFF
    return bytes(page)


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

    triangle = ((43, 25), (161, 167), (278, 49))
    min_y = min(y for _, y in triangle)
    max_y = max(y for _, y in triangle)
    three_limits = edge_limits(triangle, min_y, max_y)
    four_limits = edge_limits(triangle + (triangle[-1],), min_y, max_y)
    checks.ok(three_limits == four_limits,
              "three real edges preserve every exact ipart/fpart integer")
    three_page = discriminator_page(*three_limits, min_y)
    four_page = discriminator_page(*four_limits, min_y)
    checks.ok(three_page == four_page,
              "three real edges preserve all 64,000 indexed page bytes")
    checks.eq(three_page[SCRATCH_TINTA:SCRATCH_ESCRESCENZE + 1],
              bytes((0x35, 0x71)),
              "both polymap scratch pixels remain exact")

    projection = PROJECTION.read_text(encoding="utf-8")
    ground = GROUND.read_text(encoding="utf-8")
    prebasis = section(projection,
                       "The texture basis depends only on the original rotated vertices.",
                       '"PG pm basis"')
    terrain_scan = section(projection, '"PG pm terrain edges"', '"PG pm basis"')
    postbasis = section(projection, '"PG pm k"', '"PG pm out"')
    polymap = section(projection, '"PG polymap"',
                      "The texture basis depends only on the original rotated vertices.")
    fast_entry = section(polymap, '"PG pm preprojected terrain"', '"PG pm 2d"')
    mapped = section(ground, '"VHGND terrain mapped"',
                     '"VHGND terrain facing"')
    cached_bounds = section(ground, '"VHGND terrain cached bounds"',
                            '"VHGND terrain mapped"')
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
    checks.ok(polymap.index("? A != 0 -> PG pm preprojected terrain;")
              < polymap.index('"PG pm duplicate input generic"')
              and all(fragment in fast_entry for fragment in (
                  "[PJdx] = 3;", "[PJnrv] = 3;", "[PJvr2] = 3;",
                  "[PJvr22] = 6;", "-> PG pm projected;"))
              and "=> PJ zload;" not in fast_entry,
              "preprojected terrain bypasses input duplication and zload")
    checks.ok("[VHGNDmpi] = 3;" in cached_bounds
              and "[PJvr] = 3;" in cached_bounds
              and "[VHGNDmpi] = 4;" not in cached_bounds
              and "A = FSRXF; A + 2; A + A;" not in mapped
              and "[PJdoflag] = 4;" not in mapped,
              "cached terrain keeps only its three real projected vertices")

    return checks.done()


if __name__ == "__main__":
    raise SystemExit(main())
