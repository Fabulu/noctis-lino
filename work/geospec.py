"""geospec.py -- an exact-rational referee for the cast-boundary probe.

Shares NO arithmetic with the L.in.oleum engine and none with the x87: every
number here is computed with Fractions and an explicitly written round-to-
nearest-even, so a rounding bug in one side cannot be a rounding bug in the
other.  Python has no 80-bit float on win32, which is precisely why the
extended-precision leg has to be modelled rather than evaluated.

What is modelled, instruction for instruction:

  PC=64 (control word 133Fh) means every x87 arithmetic instruction rounds
  its result to a 64-bit significand, round to nearest even.  `fstp qword`
  then rounds THAT to 53 bits -- so a spilled value is DOUBLE ROUNDED, and
  round53(round64(v)) is not round53(v).  Modelling it as the latter would
  quietly agree with Python's own float arithmetic and would stop being an
  independent check, so it is written out the long way.

  `fistp` under RC=chop truncates toward zero.

Usage: python geospec.py [geocast.bin]
"""
import os
import struct
import sys
from fractions import Fraction as F

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "geocast.bin")

TWO = F(2)


def rnd(v, p):
    """round the exact rational v to a p-bit significand, nearest-even."""
    if v == 0:
        return F(0)
    s = -1 if v < 0 else 1
    a = v if v > 0 else -v
    e = a.numerator.bit_length() - a.denominator.bit_length()
    while TWO ** e > a:
        e -= 1
    while TWO ** (e + 1) <= a:
        e += 1
    scale = TWO ** (p - 1 - e)
    m = a * scale
    n = m.numerator // m.denominator
    rem = m - n
    if rem > F(1, 2) or (rem == F(1, 2) and n % 2):
        n += 1
    return s * F(n) / scale


def r64(v):
    return rnd(v, 64)


def r53(v):
    return rnd(v, 53)


def chop(v):
    """fistp dword under RC=chop: truncate toward zero."""
    n = v.numerator // v.denominator          # floor
    if v < 0 and n * v.denominator != v.numerator:
        n += 1
    return n


def d(x):
    """an exact Fraction for the binary64 nearest x, via Python's own float."""
    return F(float(x))


# --------------------------------------------------------------------------
# battery 1 : (long)(1.0/41.0*41.0)
# --------------------------------------------------------------------------
q_live = r64(r64(F(1, 41)) * 41)                 # fld1; fdiv 41; fmul 41
q_sp1 = r64(r53(r64(F(1, 41))) * 41)             # ... with the quotient stored
q_sp2 = r53(r64(r64(F(1, 41)) * 41))             # ... with the product stored
B1 = (chop(q_live), chop(q_sp1), chop(q_sp2))

# --------------------------------------------------------------------------
# batteries 2-6 : the four call-site shapes
# --------------------------------------------------------------------------


def kmul(xs, K):
    nd = first = live = spill = 0
    for i, x in xs:
        p = r64(x * K)                            # fmul, PC=64
        a = chop(p)                               # live  : fistp on st(0)
        b = chop(r53(p))                          # spill : fstp qword, fld, fistp
        if a != b:
            nd += 1
            if not first:
                first, live, spill = i, a, b
    return nd, first, live, spill


N = 4000

b2 = kmul(((k, d(F(k)) / 10 if False else d(float(k) / 10.0)) for k in range(1, N + 1)), 10)
b3 = kmul(((r, d(21.0 + float(r) / 100.0)) for r in range(N)), 10)
b4 = kmul(((r, d(float(r) / 1000.0)) for r in range(1, N + 1)), 300)


def seedtilt(N):
    nd = first = live = spill = 0
    for r in range(N):
        y = d(-(float(r) / 500.0))
        x = d(21.0 + float(r) / 100.0)
        t = r64(abs(y) * 10)                      # fabs; fmul ten
        p = r64(x + t)                            # faddp
        a = chop(p)
        b = chop(r53(p))
        if a != b:
            nd += 1
            if not first:
                first, live, spill = r, a, b
    return nd, first, live, spill


b5 = seedtilt(N)


def ctrl(N):
    nd = 0
    for r in range(1, N + 1):
        x = d(struct.unpack("<f", struct.pack("<f", float(r) / 1000.0))[0])
        p = r64(x * 300)
        if chop(p) != chop(r53(p)):
            nd += 1
    return nd


b6 = ctrl(N)

# --------------------------------------------------------------------------
# compare against the probe
# --------------------------------------------------------------------------
u = list(struct.unpack("<64i", open(PATH, "rb").read()[:256]))
fails = []


def cmp(label, got, want):
    ok = got == want
    if not ok:
        fails.append(label)
    print("  %-46s lino %-22s spec %-22s %s"
          % (label, got, want, "ok" if ok else "*** DIFFER ***"))


print("geospec.py -- exact-rational referee vs %s" % PATH)
print()
print("BATTERY 1  (long)(1.0/41.0*41.0)")
cmp("live / spill-after-divide / spill-after-mul", (u[7], u[8], u[9]), B1)
print()
print("BATTERY 2  K=10, x = fl64(k)/10.0")
cmp("(ndiff, first, live, spill)", (u[13], u[14], u[15], u[16]), b2)
print()
print("BATTERY 3  K=10, x = 21.0 + fl64(r)/100.0")
cmp("(ndiff, first+1, live, spill)", (u[20], u[21], u[22], u[23]),
    (b3[0], b3[1] + 1 if b3[0] else 0, b3[2], b3[3]))
print()
print("BATTERY 4  K=300, x = fl64(r)/1000.0")
cmp("(ndiff, first, live, spill)", (u[27], u[28], u[29], u[30]), b4)
print()
print("BATTERY 5  x + 10*fabs(y)")
cmp("(ndiff, first+1, live, spill)", (u[34], u[35], u[36], u[37]),
    (b5[0], b5[1] + 1 if b5[0] else 0, b5[2], b5[3]))
print()
print("BATTERY 6  control, must be 0 on both sides")
cmp("ndiff", u[39], b6)
print()
print("BATTERY 7  int16 at the call boundary, sign extended")


def i16(v):
    return ((v & 0xFFFF) ^ 0x8000) - 0x8000


cmp("(chop16 218231, -218231, 25816)", (u[40], u[41], u[42]),
    (i16(218231), i16(-218231), i16(25816)))
print()
print("BATTERY 8  fistp qword (what __ftol does) vs fistp dword, x = 3.0e9")
q = 3000000000
cmp("(qword low32, dword, int16 of the qword)", (u[46] & 0xFFFFFFFF, u[47] & 0xFFFFFFFF, u[48]),
    (q & 0xFFFFFFFF, 0x80000000, i16(q)))
print()
print("STRUCTURE")
cmp("magic / version / units", (u[0] & 0xFFFFFFFF, u[1], u[2]), (0x47454F43, 1, 64))
cmp("fld1 layout guard (FA0, FA1)", (u[4] & 0xFFFFFFFF, u[5] & 0xFFFFFFFF), (0, 0x3FF00000))
cmp("control word in / out, masked", (u[3] & 0xFFFF, u[44] & 0xFFFF), (0x033F, 0x033F))
cmp("x87 stack top before / after", (u[6], u[43]), (0, 0))
print()
if fails:
    print("SPEC FAIL: %d battery/batteries differ: %s" % (len(fails), ", ".join(fails)))
    sys.exit(1)
print("SPEC OK: the L.in.oleum x87 and the exact-rational model agree on every battery.")
