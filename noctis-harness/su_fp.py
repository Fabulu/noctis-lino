"""su_fp.py - exact x87 arithmetic helpers for the Wave 7a surface() reference.

PROVENANCE
----------
Written from the DOS sources and from Wave 3's settled float policy
(docs-notes/FLOATPOLICY.md: control word 133Fh, PC=11 -> 64-bit mantissa,
RC=00 -> round to nearest even).  Nothing here is transliterated from
noctis-iv-lr, from any L.in.oleum file, or from su_ref.c.

WHY THIS FILE EXISTS AT ALL

surface() accumulates a float32 global `a` by a double increment:

    for (a = 0; a < 2*M_PI; a += 4*deg)          NOCTIS-0.CPP:4514, 4547, ...

On the 8087 that is  a_f32 <- round24( round64( ext(a) + ext(4*deg) ) ).
`a` carries 24 mantissa bits at exponent ~2 and 4*deg carries 53 at exponent
-4, so the exact sum needs about 59 bits.  Rounding it to float64 first and
then to float32 - which is what plain Python arithmetic does - is a DOUBLE
ROUNDING and is not guaranteed to agree.  The number of iterations of that
loop (90 vs 91) is exactly the LOOP91 hazard the plan names, so the
arithmetic has to be done at the width the hardware uses.

Everything here works on exact Fractions and rounds explicitly.
"""

from fractions import Fraction
import math
import struct

__all__ = [
    "round_to_bits", "ext", "f32", "f64", "fr",
    "ftol64", "ftol32", "d2u16", "fistp16",
    "DEG", "TWO_PI",
]

DEG = math.pi / 180.0            # PITAGORA.H:136  const double deg = M_PI/180
TWO_PI = 2.0 * math.pi


def fr(x):
    """Exact Fraction of a Python float (which is exactly a binary64)."""
    return x if isinstance(x, Fraction) else Fraction(x)


def round_to_bits(v, p):
    """Round an exact rational to the nearest binary float with p mantissa
    bits, ties to even.  Returns an exact Fraction.

    p = 64 is the x87 extended significand under CW 133Fh (PC = 11).
    p = 53 is binary64.  p = 24 is binary32.
    """
    f = fr(v)
    if f == 0:
        return Fraction(0)
    neg = f < 0
    if neg:
        f = -f
    num, den = f.numerator, f.denominator
    e = num.bit_length() - den.bit_length() - p

    def scaled(k):
        if k >= 0:
            return Fraction(num, den << k)
        return Fraction(num << (-k), den)

    hi = Fraction(1 << p)
    lo = Fraction(1 << (p - 1))
    while scaled(e) >= hi:
        e += 1
    while scaled(e) < lo:
        e -= 1
    s = scaled(e)
    m, rem = divmod(s.numerator, s.denominator)
    remf = Fraction(rem, s.denominator)
    half = Fraction(1, 2)
    if remf > half or (remf == half and (m & 1)):
        m += 1
    if m == (1 << p):
        m >>= 1
        e += 1
    out = Fraction(m) * (Fraction(2) ** e)
    return -out if neg else out


def ext(v):
    """Round to the x87 extended register format (64-bit significand)."""
    return round_to_bits(v, 64)


def f64(v):
    """Round to binary64 and hand back a Python float."""
    if isinstance(v, float):
        return v
    return float(round_to_bits(v, 53))


def f32(v):
    """Round to binary32 and hand back a Python float holding that value."""
    x = round_to_bits(v, 24)
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


# ---------------------------------------------------------------------------
# __ftol:  fstcw / or 0x0C (chop) / fistp qword / take the low 32 bits.
# It never saturates - a value that will not fit simply loses its high bits.
# The x87 "integer indefinite" 8000000000000000h only appears when the value
# does not fit in 64 bits at all.
# ---------------------------------------------------------------------------

_I64 = 1 << 63


def ftol64(v):
    """double -> long long, truncating toward zero (chop), as a signed int."""
    f = fr(v)
    t = int(f) if f >= 0 else -int(-f)      # trunc toward zero, exact
    if t < -_I64 or t >= _I64:
        return -_I64                        # integer indefinite
    return t


def ftol32(v):
    """Borland's (long) cast: __ftol then keep AX:DX, i.e. the low 32 bits."""
    lo = ftol64(v) & 0xFFFFFFFF
    return lo - 0x100000000 if lo & 0x80000000 else lo


def d2u16(v):
    """double -> `unsigned` (16 bit on this target): __ftol then keep AX."""
    return ftol64(v) & 0xFFFF


def fistp16(v):
    """FISTP word under RC = 00: round to nearest, ties to even, 16-bit store.

    Used by wave() (NOCTIS-0.CPP:4586) which is the ONLY place surface()
    stores a float to an integer without a chop-mode cast.
    """
    f = fr(v)
    n = f.numerator
    d = f.denominator
    q, rem = divmod(n, d)                   # floor division
    remf = Fraction(rem, d)
    half = Fraction(1, 2)
    if remf > half or (remf == half and (q & 1)):
        q += 1
    if q < -32768 or q > 32767:
        return 0x8000                       # integer indefinite
    return q & 0xFFFF
