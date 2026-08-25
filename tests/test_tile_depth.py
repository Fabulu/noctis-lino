"""Exact integer discriminator for the live terrain distance bin."""

from __future__ import annotations

from math import isqrt
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
GROUND = ROOT / "work" / "vhground.txt"
MAP_LOW = 122880
MAP_HIGH = 3145728
TILE_SIZE = 16384
LOD_STEPS = (1, 8, 16)
ROOT_LIMIT = 512
ROOT_STEPS = 9
WORD_MASK = (1 << 32) - 1
WIDE_MASK = (1 << 64) - 1
MAX_DELTA = MAP_HIGH
MAX_REDUCED_SQUARE = (2 * MAX_DELTA * MAX_DELTA) >> 28

sys.path.insert(0, str(HERE))
import linoharness as lh  # noqa: E402


def reduced_root(value: int) -> int:
    low, high = 0, ROOT_LIMIT
    for _ in range(ROOT_STEPS):
        middle = (low + high) >> 1
        if middle * middle <= value:
            low = middle
        else:
            high = middle
    return low


def lino_reduced_square(dx: int, dz: int) -> int:
    dx_square = (dx * dx) & WIDE_MASK
    dz_square = (dz * dz) & WIDE_MASK
    dx_low, dx_high = dx_square & WORD_MASK, dx_square >> 32
    dz_low, dz_high = dz_square & WORD_MASK, dz_square >> 32
    low = (dx_low + dz_low) & WORD_MASK
    carry = int(low < dz_low)
    high = (dx_high + dz_high + carry) & WORD_MASK
    return (low >> 28) | (high << 4)


def integer_raw_depth(dx: int, dz: int) -> int:
    return reduced_root(lino_reduced_square(dx, dz))


def integer_depth(dx: int, dz: int) -> int:
    return max(integer_raw_depth(dx, dz) - 1, 0)


def reference_depth(dx: int, dz: int) -> int:
    return max((isqrt(dx * dx + dz * dz) >> 14) - 1, 0)


def main() -> int:
    checks = lh.Check("exact integer terrain depth")

    wrong = [value for value in range(MAX_REDUCED_SQUARE + 1)
             if reduced_root(value) != isqrt(value)]
    checks.eq(wrong, [],
              "nine binary decisions give the exact root for every reachable reduced square")

    reduction_wrong = []
    remainder_max = (1 << 28) - 1
    for value in range(MAX_REDUCED_SQUARE + 1):
        expected = isqrt(value)
        for remainder in (0, remainder_max):
            square = (value << 28) + remainder
            if (isqrt(square) >> 14) != expected:
                reduction_wrong.append((value, remainder))
    checks.eq(reduction_wrong, [],
              "discarding 28 low square bits is exact at both sides of every depth bin")

    deltas = {0, 1, -1, MAX_DELTA, -MAX_DELTA}
    cameras = (MAP_LOW, (MAP_LOW + MAP_HIGH) // 2, MAP_HIGH)
    for lod in LOD_STEPS:
        for tile in range(0, 200 - lod):
            centre = tile * TILE_SIZE + lod * (TILE_SIZE // 2)
            deltas.update(camera - centre for camera in cameras)
    ordered = sorted(deltas)
    pairs = [(dx, dz) for dx in ordered for dz in (
        ordered[0], ordered[len(ordered) // 3], 0,
        ordered[(2 * len(ordered)) // 3], ordered[-1])]
    pairs.extend((value, value) for value in ordered)
    split_wrong = [(dx, dz) for dx, dz in pairs
                   if lino_reduced_square(dx, dz)
                   != (dx * dx + dz * dz) >> 28]
    checks.eq(split_wrong, [],
              "signed full-width squares and unsigned low-word carry reconstruct S >> 28")
    differences = [(dx, dz) for dx, dz in pairs
                   if integer_depth(dx, dz) != reference_depth(dx, dz)]
    checks.eq(differences, [],
              "reachable map edges, LOD centres, axes, and diagonals equal floor(sqrt) >> 14")

    maximum = max((dx * dx + dz * dz) >> 28 for dx, dz in pairs)
    checks.ok(maximum < ROOT_LIMIT * ROOT_LIMIT,
              "the fixed root interval strictly contains every reachable terrain distance",
              f"maximum reduced square {maximum}, limit {ROOT_LIMIT * ROOT_LIMIT}")

    source = GROUND.read_text(encoding="utf-8")
    routine = source.split('"VHGND tile depth"', 1)[1].split(
        '"VHGND tile shade"', 1)[0]
    required = (
        "A = C; B = A; A *% B; [VHGNDdlo] = A; [VHGNDdhi] = B;",
        "A = C; B = A; A *% B; [VHGNDslo] = A; [VHGNDshi] = B;",
        "? A '>= B -> VHGND tile depth sum ready; [VHGNDdhi]+;",
        "A = [VHGNDdlo]; A > 28; C = A;",
        "A = [VHGNDdhi]; A < 4; A | C; [VHGNDdepthn] = A;",
        "[VHGNDdepthlo] = 0; [VHGNDdepthhi] = 512; [VHGNDdepthstep] = 9;",
        "A '* A; [VHGNDdepthsq] = A;",
        "? A <= [VHGNDdepthn] -> VHGND tile depth root low;",
        "A = [VHGNDdepthlo]; [VHGNDrawdepth] = A;",
        "A - 1; ? A >= 0 -> VHGND tile depth ready; A = 0;",
    )
    checks.ok(all(fragment in routine for fragment in required),
              "production uses full-width squares, carry, exact reduction, and nine-step root")
    checks.ok(all(fragment not in routine for fragment in (
        "=> IntToF;", "=> FMul;", "=> FAdd;", "=> FSqrt;", "=> FToIntChop;")),
        "the hot terrain distance bin no longer enters scalar floating-point")

    return checks.done()


if __name__ == "__main__":
    raise SystemExit(main())
