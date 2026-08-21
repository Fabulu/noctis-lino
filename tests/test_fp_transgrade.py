"""Focused contract checks for the independent transcendental grader."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import math


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "work" / "fp" / "fptransgrade.py"
spec = importlib.util.spec_from_file_location("fptransgrade", MODULE)
grade = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(grade)
VECTOR_MODULE = ROOT / "work" / "fp" / "fpvecgen.py"
vector_spec = importlib.util.spec_from_file_location("fpvecgen", VECTOR_MODULE)
vectors = importlib.util.module_from_spec(vector_spec)
assert vector_spec.loader is not None
vector_spec.loader.exec_module(vectors)


def main() -> int:
    errors: list[str] = []

    def check(condition: bool, message: str) -> None:
        print("PASS" if condition else "FAIL", message)
        if not condition:
            errors.append(message)

    plus_zero = 0x0000000000000000
    minus_zero = 0x8000000000000000
    exact, within, error = grade.accuracy(minus_zero, plus_zero)
    check(not exact and not within and error and "signed zero" in error,
          "opposite zero signs fail the exact and one-ULP gates")
    check(grade.accuracy(minus_zero, minus_zero) == (True, True, None),
          "matching negative zero is exact")
    check(grade.expected_bits(8, -0.0, 1.0) == minus_zero,
          "the sine oracle preserves negative zero")
    check(grade.expected_bits(9, -0.0, 1.0) == 0x3FF0000000000000,
          "the cosine oracle maps negative zero to positive one")
    check(grade.expected_bits(10, -0.0, 1.0) == minus_zero,
          "the atan2 oracle preserves a negative-zero ordinate on the positive axis")
    min_subnormal = math.ldexp(1.0, -1074)
    min_normal = math.ldexp(1.0, -1022)
    max_subnormal = math.nextafter(min_normal, 0.0)
    check(grade.expected_bits(8, min_subnormal, 1.0) == 1 and
          grade.expected_bits(8, -min_subnormal, 1.0) ==
          0x8000000000000001,
          "the sine oracle retains both signs of the minimum subnormal")
    check(grade.expected_bits(10, min_subnormal, 1.0) == 1 and
          grade.expected_bits(10, -min_subnormal, 1.0) ==
          0x8000000000000001,
          "the atan2 oracle retains subnormal quotients")
    check(grade.expected_bits(10, min_subnormal, 2.0) == plus_zero and
          grade.expected_bits(10, -min_subnormal, 2.0) == minus_zero,
          "atan2 underflow ties round to an even signed zero")
    check(grade.expected_bits(10, 3.0 * min_subnormal, 2.0) == 1 and
          grade.expected_bits(10, -3.0 * min_subnormal, 2.0) ==
          0x8000000000000001,
          "atan(z) nudges exact subnormal ties toward zero")
    for schedule in (8, 9, 10):
        inputs = {case[0] for case in vectors.vectors(schedule)}
        check({min_subnormal, -min_subnormal,
               max_subnormal, -max_subnormal} <= inputs,
              f"schedule {schedule} contains signed subnormal boundaries")

    check(grade.accuracy(0x3FF0000000000001,
                         0x3FF0000000000000) == (False, True, None),
          "one adjacent binary64 value is accepted but not exact")
    exact, within, error = grade.accuracy(0x3FF0000000000002,
                                          0x3FF0000000000000)
    check(not exact and not within and error and "2 ULP" in error,
          "a two-ULP result is rejected")

    limit = 2.0 ** 63
    below = math.nextafter(limit, 0.0)
    above = math.nextafter(limit, math.inf)
    sine_inputs = {case[0] for case in vectors.vectors(8)}
    check({below, -below, limit, -limit, above, -above} <= sine_inputs,
          "the vector corpus straddles both signs of the 2^63 instruction boundary")
    check(grade.expected_bits(8, below, 1.0) != grade.f64_bits(below),
          "the value immediately below 2^63 still uses mathematical reduction")
    for schedule in (8, 9):
        for value in (limit, -limit, above, -above):
            check(grade.expected_bits(schedule, value, 1.0) ==
                  grade.f64_bits(value),
                  f"schedule {schedule} preserves {value!r} outside the instruction interval")
    check(grade.int32_result(limit, False) == -0x80000000 and
          grade.int32_result(-limit, True) == -0x80000000,
          "conversion grading models x87 integer-indefinite outside int32")

    if errors:
        print(f"transcendental grader: {len(errors)} failure(s)")
        return 1
    print("transcendental grader: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
