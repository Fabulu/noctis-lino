"""Protect the exact guarded fast path for tree polar binary32 multiply-adds.

Run: python tests/test_tree_polar_madd.py
"""
from pathlib import Path
import itertools
import sys

ROOT = Path(__file__).resolve().parents[1]
GROUND = ROOT / "work" / "vhground.txt"


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print("PASS", message)


def f32_pair(bits):
    """Decode one finite binary32 bit pattern as exact m * 2**e."""
    sign = bits >> 31
    exponent = (bits >> 23) & 0xFF
    fraction = bits & 0x7FFFFF
    if exponent == 0xFF:
        raise ValueError(f"nonfinite binary32 {bits:08x}")
    if exponent == 0:
        mantissa, power = fraction, -149
    else:
        mantissa, power = (1 << 23) | fraction, exponent - 150
    return (-mantissa if sign else mantissa, power)


def add_pair(left, right):
    lm, le = left
    rm, re = right
    if le < re:
        return lm + (rm << (re - le)), le
    return (lm << (le - re)) + rm, re


def mul_pair(left, right):
    return left[0] * right[0], left[1] + right[1]


def round_pair(value, precision):
    """Round an exact binary integer pair to nearest-even precision bits."""
    mantissa, power = value
    if mantissa == 0:
        return 0, 0
    negative = mantissa < 0
    magnitude = -mantissa if negative else mantissa
    discard = magnitude.bit_length() - precision
    if discard <= 0:
        return value
    divisor = 1 << discard
    rounded, remainder = divmod(magnitude, divisor)
    halfway = divisor >> 1
    if remainder > halfway or (remainder == halfway and (rounded & 1)):
        rounded += 1
    if rounded.bit_length() > precision:
        rounded >>= 1
        discard += 1
    return (-rounded if negative else rounded), power + discard


def canonical(value):
    mantissa, power = value
    if mantissa == 0:
        return 0, 0
    while (mantissa & 1) == 0:
        mantissa >>= 1
        power += 1
    return mantissa, power


def f64_bits(value):
    """Encode a normal-or-zero p53 pair without using host floating point."""
    mantissa, power = round_pair(value, 53)
    if mantissa == 0:
        return 0
    negative = mantissa < 0
    magnitude = -mantissa if negative else mantissa
    shift = 53 - magnitude.bit_length()
    if shift > 0:
        magnitude <<= shift
        power -= shift
    biased = power + 52 + 1023
    if not 0 < biased < 0x7FF:
        raise ValueError(f"test value outside normal binary64: exponent {biased}")
    return ((int(negative) << 63) | (biased << 52) |
            (magnitude - (1 << 52)))


def schedules(a_bits, b_bits, c_bits):
    a, b, c = map(f32_pair, (a_bits, b_bits, c_bits))
    product = mul_pair(a, b)
    # A finite binary32 product has at most 48 significant bits, so both
    # schedules retain it exactly. Only the following addition can diverge.
    sum53 = round_pair(add_pair(round_pair(product, 53), c), 53)
    sum64 = round_pair(add_pair(round_pair(product, 64), c), 64)
    return sum53, sum64


def needs_p64(sum53):
    bits = f64_bits(sum53)
    exponent = (bits >> 52) & 0x7FF
    return (exponent < 897 or
            (bits & 0x1FFFFFFF) == 0x10000000)


def final32(value):
    return canonical(round_pair(value, 24))


def main():
    source = GROUND.read_text(encoding="utf-8")
    fast = source.split('"VHGND tree polar madd"', 1)[1].split(
        '"VHGND tree polar madd p64"', 1)[0]
    fallback = source.split('"VHGND tree polar madd p64"', 1)[1].split(
        '"VHGND tree trig init"', 1)[0]
    check("[FA0] *: [FB0];" in fast and "[FA0] +: [FB0];" in fast,
          "tree polar fast path uses the exact compiler-owned p53 spill schedule")
    check("? C < 897 -> VHGND tree polar madd p64;" in fast and
          "A & 1FFFFFFFh; ? A = 10000000h -> VHGND tree polar madd p64;" in fast,
          "subnormal-range sums and every normal binary32 midpoint fall back")
    check(fast.count("A & 7F800000h; ? A = 7F800000h ->") == 3,
          "all three binary32 inputs reject NaN and infinity to the p64 path")
    check(all(token in fallback for token in
              ("=> XMulCore;", "=> XAddCore;", "=> XToF32;")),
          "fallback retains the complete p64 multiply-add and binary32 store")

    counterexample = (0x3F800001, 0x3FC00000, 0xA1800000)
    sum53, sum64 = schedules(*counterexample)
    check(final32(sum53) != final32(sum64),
          "unguarded p53 path fails the exact halfway-minus-epsilon case")
    check(needs_p64(sum53),
          "midpoint detector sends that required negative case to p64")

    positive = [
        0x00000001, 0x00000002, 0x007FFFFF, 0x00800000, 0x00800001,
        0x3EFFFFFF, 0x3F000000, 0x3F000001, 0x3F7FFFFF, 0x3F800000,
        0x3F800001, 0x3FC00000, 0x40000000, 0x49FFFFFF, 0x4A000000,
        0x7F000000, 0x7F7FFFFF,
    ]
    values = positive + [bits | 0x80000000 for bits in positive]
    vectors = list(itertools.product(values, repeat=3))
    vectors.extend((
        counterexample,
        (0xBF800001, 0x3FC00000, 0x21800000),
        (0x3F800001, 0xBFC00000, 0x21800000),
        (0x00800000, 0x3F000000, 0x80000001),
        (0x7F7FFFFF, 0x7F7FFFFF, 0xFF7FFFFF),
    ))

    fallbacks = disagreements = 0
    for vector in vectors:
        sum53, sum64 = schedules(*vector)
        fallback_needed = needs_p64(sum53)
        fallbacks += int(fallback_needed)
        disagreements += int(final32(sum53) != final32(sum64))
        selected = sum64 if fallback_needed else sum53
        if final32(selected) != final32(sum64):
            raise AssertionError(
                "guard missed %08x * %08x + %08x" % vector)
    check(fallbacks > 0 and fallbacks < len(vectors),
          f"adversarial sweep exercises both paths ({fallbacks}/{len(vectors)} fallback)")
    check(disagreements > 0,
          f"adversarial sweep includes {disagreements} real p53/p64 divergences")
    check(True,
          f"guarded result equals p64 over all {len(vectors)} adversarial triples")
    print("tree polar guarded multiply-add: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
