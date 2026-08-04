"""Referee work/starmap_kernel.bin against Python arbitrary-precision integers.

Python big ints are a genuinely independent implementation: there is no
shared 32-bit limb code that could be wrong the same way twice, and no
rounding anywhere on this side. N is additionally computed twice on the
Python side - once from the exponent/mantissa fields and once as
trunc(Fraction(the double) * 10**15) - and the two must agree before either
is used to judge the L.in.oleum result.

Exact equality is required on all 96 bits, and on which vectors are
rejected. Nothing here is approximate, so nothing here is graded on a
curve.
"""

import struct
import sys
from fractions import Fraction

WORK = r"C:\programmieren\linoleum\work"
VEC = WORK + r"\starmap_vec.bin"
OUT = WORK + r"\starmap_kernel.bin"

M32 = 0xFFFFFFFF
M96 = (1 << 96) - 1


def limbs96(v):
    v &= M96
    return v & M32, (v >> 32) & M32, (v >> 64) & M32


def expect_P(x, y, z):
    """(limbs, rej). 0x80000000 has no 32-bit magnitude, so it is refused."""
    if -0x80000000 in (x, y, z):
        return (0, 0, 0), 1
    return limbs96(x * y * z), 0


def expect_N(lo, hi):
    """(limbs, rej) for N = trunc(d * 1e15)."""
    e = (hi >> 20) & 0x7FF
    if e == 0:
        return (0, 0, 0), 1           # zero or denormal - unusable
    if e == 0x7FF:
        return (0, 0, 0), 2           # inf / NaN
    if e >= 1068:
        return (0, 0, 0), 3           # would not fit 96 bits
    sign = hi >> 31
    m = (((hi & 0xFFFFF) << 32) | lo) | (1 << 52)
    k = 1075 - e
    mag = 0 if k >= 104 else (m * 10 ** 15) >> k

    # Second, independent path: the exact rational value of the double.
    d = struct.unpack("<d", struct.pack("<II", lo, hi))[0]
    exact = Fraction(d) * 10 ** 15
    trunc = int(exact)                # int() on a Fraction truncates toward zero
    want = -mag if sign else mag
    if trunc != want:
        raise AssertionError(f"python disagrees with itself on {lo:08x}{hi:08x}: "
                             f"fields {want} vs fraction {trunc}")
    return limbs96(want), 0


def main():
    vb = open(VEC, "rb").read()
    n = struct.unpack_from("<I", vb, 0)[0]
    if len(vb) != 4 + 20 * n:
        print(f"FAIL vector file is {len(vb)} bytes, expected {4 + 20*n}")
        return 2

    ob = open(OUT, "rb").read()
    if len(ob) != 32 * n:
        print(f"FAIL {OUT} is {len(ob)} bytes, expected {32*n} for {n} vectors")
        return 2

    badP = badN = badPr = badNr = 0
    first = []
    rejP = rejN = 0
    for i in range(n):
        x, y, z, lo, hi = struct.unpack_from("<5I", vb, 4 + 20 * i)
        sx = x - (1 << 32) if x >> 31 else x
        sy = y - (1 << 32) if y >> 31 else y
        sz = z - (1 << 32) if z >> 31 else z

        gP, gPr, gN, gNr = (struct.unpack_from("<3I", ob, 32 * i),
                            struct.unpack_from("<I", ob, 32 * i + 12)[0],
                            struct.unpack_from("<3I", ob, 32 * i + 16),
                            struct.unpack_from("<I", ob, 32 * i + 28)[0])

        wP, wPr = expect_P(sx, sy, sz)
        wN, wNr = expect_N(lo, hi)
        rejP += wPr != 0
        rejN += wNr != 0

        if gPr != wPr:
            badPr += 1
            first.append(f"  [{i}] Prej lino {gPr} want {wPr}  x={sx} y={sy} z={sz}")
        elif gP != wP:
            badP += 1
            first.append(f"  [{i}] P lino {gP} want {wP}  x={sx} y={sy} z={sz}")
        if gNr != wNr:
            badNr += 1
            first.append(f"  [{i}] Nrej lino {gNr} want {wNr}  d={lo:08x}:{hi:08x}")
        elif gN != wN:
            badN += 1
            e = (hi >> 20) & 0x7FF
            first.append(f"  [{i}] N lino {gN} want {wN}  d={lo:08x}:{hi:08x} "
                         f"e={e} k={1075-e} r={(1075-e)%32}")

    print(f"vectors            : {n}")
    print(f"  P rejected       : {rejP} (coordinate 0x80000000)")
    print(f"  N rejected       : {rejN} (e==0, e==0x7FF, e>=1068)")
    print(f"  P mismatches     : {badP}   P-rejection mismatches: {badPr}")
    print(f"  N mismatches     : {badN}   N-rejection mismatches: {badNr}")
    if first:
        print("first 12 disagreements:")
        for line in first[:12]:
            print(line)
        print("KERNEL FAIL")
        return 1
    print("KERNEL PASS - all 96 bits of P and N agree with Python on every vector")
    return 0


if __name__ == "__main__":
    sys.exit(main())
