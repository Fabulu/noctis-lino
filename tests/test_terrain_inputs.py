"""Deferred terrain inputs preserve both source triangles exactly."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
GROUND = ROOT / "work" / "vhground.txt"
LOD_STEPS = (1, 8, 16)

sys.path.insert(0, str(HERE))
import linoharness as lh  # noqa: E402


def source_triangles(x: int, z: int, lod: int,
                     heights: tuple[int, int, int, int]
                     ) -> tuple[tuple[tuple[int, int, int], ...], ...]:
    s1, s2, s3, s4 = heights
    return (
        ((x << 14, -(s1 << 9), z << 14),
         ((x + lod) << 14, -(s2 << 9), z << 14),
         (x << 14, -(s4 << 9), (z + lod) << 14)),
        (((x + lod) << 14, -(s2 << 9), z << 14),
         ((x + lod) << 14, -(s3 << 9), (z + lod) << 14),
         (x << 14, -(s4 << 9), (z + lod) << 14)),
    )


def deferred_triangles(x: int, z: int, lod: int,
                       heights: tuple[int, int, int, int]
                       ) -> tuple[tuple[tuple[int, int, int], ...], ...]:
    s1, s2, s3, s4 = heights
    common = (x << 14, -(s4 << 9), (z + lod) << 14)
    first = ((x << 14, -(s1 << 9), z << 14),
             ((x + lod) << 14, -(s2 << 9), z << 14), common)
    second = (((x + lod) << 14, -(s2 << 9), z << 14),
              ((x + lod) << 14, -(s3 << 9), (z + lod) << 14), common)
    return first, second


def section(source: str, start: str, end: str) -> str:
    return source.split(start, 1)[1].split(end, 1)[0]


def main() -> int:
    checks = lh.Check("deferred terrain vertex inputs")

    heights = [
        (0, 0, 0, 0), (255, 255, 255, 255),
        (0, 1, 254, 255), (255, 128, 127, 0),
        (0, -1, -254, -255), (-255, -128, -127, 0),
    ]
    state = 0x13579BDF
    for _ in range(4096):
        row = []
        for _ in range(4):
            state = (state * 1664525 + 1013904223) & 0xFFFFFFFF
            value = (state >> 24) & 255
            row.append(-value if state & 1 else value)
        heights.append(tuple(row))

    differences = []
    for lod in LOD_STEPS:
        for x in (0, 1, 99, 198 - lod, 199 - lod):
            for z in (0, 1, 99, 198 - lod, 199 - lod):
                for row in heights:
                    if deferred_triangles(x, z, lod, row) != source_triangles(
                            x, z, lod, row):
                        differences.append((x, z, lod, row))
    checks.eq(differences, [],
              "shared vertex 2 plus each deferred pair reconstruct both triangles")

    source = GROUND.read_text(encoding="utf-8")
    common = section(source, '"VHGND terrain common input"',
                     '"VHGND terrain remaining input"')
    remaining = section(source, '"VHGND terrain remaining input"',
                        '"VHGND terrain cache frame"')
    mapped = section(source, '"VHGND terrain mapped"',
                     '"VHGND secondary sun setup"')
    tile = section(source, '"VHGND tile"', '"VHGND render tile fauna"')

    checks.ok(all(fragment in common for fragment in (
        "[VHGNDvi] = 2;",
        "A = [VHGNDx]; A < 14;",
        "A = [VHGNDs4]; A < VHGNDHS;",
        "A = [VHGNDz]; A + [VHGNDlodstep]; A < 14;",
    )), "production loads the shared third vertex once")
    checks.ok(all(fragment in remaining for fragment in (
        "? A != 0 -> VHGND terrain remaining second;",
        "A = [VHGNDs1]; A < VHGNDHS;",
        "A = [VHGNDs2]; A < VHGNDHS;",
        "A = [VHGNDs3]; A < VHGNDHS;",
        "[VHGNDvi] = 2; [VHGNDinputready] = 1;",
    )), "production reconstructs the triangle-specific first two vertices")
    checks.ok(all(fragment in mapped for fragment in (
        '"VHGND terrain mapped ensure begin"',
        '"VHGND terrain facing build"',
        '"VHGND terrain facing generic"',
        '"VHGND terrain mapped generic"',
        "=> VHGND terrain remaining input;",
    )), "normal misses, projection misses, mirrors, and clipping request full inputs")
    checks.ok(tile.count("=> VHGND terrain common input;") == 1
              and "=> VHGND vload;" not in tile,
              "the common tile path performs no eager duplicate vertex loads")

    return checks.done()


if __name__ == "__main__":
    raise SystemExit(main())
