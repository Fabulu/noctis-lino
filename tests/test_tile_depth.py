"""Exact integer discriminator for the live terrain distance bin."""

from __future__ import annotations

from math import isqrt
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
GROUND = ROOT / "work" / "vhground.txt"
LOD_STEPS = (1, 8, 16)
ROOT_LIMIT = 128
ROOT_STEPS = 6
WORD_MASK = (1 << 32) - 1
WIDE_MASK = (1 << 64) - 1
TABLE_LIMIT = ROOT_LIMIT * ROOT_LIMIT

sys.path.insert(0, str(HERE))
import linoharness as lh  # noqa: E402


def fallback_root(value: int) -> int:
    low = 0 if value < 4096 else 64
    high = low + 64
    for _ in range(ROOT_STEPS):
        middle = (low + high) >> 1
        if middle * middle <= value:
            low = middle
        else:
            high = middle
    return low


def packed_root(value: int) -> tuple[int, int]:
    if value < 64:
        return fallback_root(value), 0
    block_root = isqrt((value >> 5) << 5)
    next_square = (block_root + 1) * (block_root + 1)
    corrections = 0
    while corrections < 2 and value >= next_square:
        block_root += 1
        corrections += 1
        next_square = (block_root + 1) * (block_root + 1)
    return block_root, corrections


def lino_reduced_square(dx: int, dz: int) -> int:
    dx_square = (dx * dx) & WIDE_MASK
    dz_square = (dz * dz) & WIDE_MASK
    dx_low, dx_high = dx_square & WORD_MASK, dx_square >> 32
    dz_low, dz_high = dz_square & WORD_MASK, dz_square >> 32
    low = (dx_low + dz_low) & WORD_MASK
    carry = int(low < dz_low)
    high = (dx_high + dz_high + carry) & WORD_MASK
    return (low >> 28) | (high << 4)


def accepted_pairs():
    for lod_step in LOD_STEPS:
        for tile_dx in range(-90, 91):
            for tile_dz in range(-90 + abs(tile_dx), 91 - abs(tile_dx)):
                for fraction_x in (0, 16383):
                    for fraction_z in (0, 16383):
                        yield (
                            (tile_dx << 14) + (lod_step << 13) - fraction_x,
                            (tile_dz << 14) + (lod_step << 13) - fraction_z,
                        )


def integer_raw_depth(dx: int, dz: int) -> int:
    value = lino_reduced_square(dx, dz)
    return packed_root(value)[0]


def integer_depth(dx: int, dz: int) -> int:
    return max(integer_raw_depth(dx, dz) - 1, 0)


def reference_depth(dx: int, dz: int) -> int:
    return max((isqrt(dx * dx + dz * dz) >> 14) - 1, 0)


def main() -> int:
    checks = lh.Check("exact integer terrain depth")

    fallback_wrong = [value for value in range(TABLE_LIMIT)
                      if fallback_root(value) != isqrt(value)]
    checks.eq(fallback_wrong, [],
              "six binary decisions give the exact root throughout both live ranges")

    packed_wrong = []
    maximum_corrections = 0
    for value in range(TABLE_LIMIT):
        root, corrections = packed_root(value)
        maximum_corrections = max(maximum_corrections, corrections)
        if root != isqrt(value):
            packed_wrong.append(value)
    checks.eq(packed_wrong, [],
              "packed 32-value roots plus at most two square corrections are exact")
    checks.ok(maximum_corrections == 2,
              "the packed lookup exercises and bounds its two correction steps",
              f"maximum corrections {maximum_corrections}")

    reduction_wrong = []
    remainder_max = (1 << 28) - 1
    for value in range(TABLE_LIMIT):
        expected = isqrt(value)
        for remainder in (0, remainder_max):
            square = (value << 28) + remainder
            if (isqrt(square) >> 14) != expected:
                reduction_wrong.append((value, remainder))
    checks.eq(reduction_wrong, [],
              "discarding 28 low square bits is exact at both sides of every depth bin")

    pairs = list(accepted_pairs())
    split_wrong = [(dx, dz) for dx, dz in pairs
                   if lino_reduced_square(dx, dz)
                   != (dx * dx + dz * dz) >> 28]
    checks.eq(split_wrong, [],
              "signed full-width squares and unsigned low-word carry reconstruct S >> 28")
    differences = [(dx, dz) for dx, dz in pairs
                   if integer_depth(dx, dz) != reference_depth(dx, dz)]
    checks.eq(differences, [],
              "accepted LOD offsets equal floor(sqrt) >> 14 at all fractional corners")

    maximum = max((dx * dx + dz * dz) >> 28 for dx, dz in pairs)
    checks.ok(maximum < TABLE_LIMIT,
              "the packed root interval strictly contains every accepted terrain distance",
              f"maximum reduced square {maximum}, limit {TABLE_LIMIT}")

    source = GROUND.read_text(encoding="utf-8")
    routine = source.split('"VHGND tile depth"', 1)[1].split(
        '"VHGND tile shade"', 1)[0]
    required = (
        "A - [VHGNDcamx]; B = A; A *% B; [VHGNDslo] = A; [VHGNDshi] = B;",
        "A - [VHGNDcamz]; B = A; A *% B;",
        "C = [VHGNDslo]; C + A;",
        "? C '>= A -> VHGND tile depth x sum ready; B + 1;",
        "C = [VHGNDdlo]; C + A;",
        "? C '>= A -> VHGND tile depth z sum ready; B + 1;",
        "C > 28; A = B; A < 4; A | C; [VHGNDdepthn] = A;",
        "C = A; A > 7; A + VHGNDhalfdepthroots; D = [A];",
        "C = VHGNDdepthsquares; C + A; C = [C]; A < 1; A + 1; C + A;",
        "A = [VHGNDdepthn]; ? A < C -> VHGND tile depth square terminal;",
        "[VHGNDdepthlo] = 0; [VHGNDdepthhi] = 64; [VHGNDdepthstep] = 6;",
        "[VHGNDdepthlo] = 64; [VHGNDdepthhi] = 128;",
        "A '* A; ? A <= [VHGNDdepthn] -> VHGND tile depth root low;",
        "A = [VHGNDdepthlo]; [VHGNDrawdepth] = A;",
        "A - 1; ? A >= 0 -> VHGND tile depth ready; A = 0;",
    )
    checks.ok(all(fragment in routine for fragment in required)
              and routine.count(
                  "? A < C -> VHGND tile depth square terminal;") == 2
              and routine.count("[VHGNDdepthlo]+;") == 2,
              "production uses full-width squares, exact packed lookup, and bounded fallback")
    checks.ok(all(fragment not in routine for fragment in (
        "=> IntToF;", "=> FMul;", "=> FAdd;", "=> FSqrt;", "=> FToIntChop;")),
        "the hot terrain distance bin no longer enters scalar floating-point")

    return checks.done()


if __name__ == "__main__":
    raise SystemExit(main())
