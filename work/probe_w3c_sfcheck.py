"""Referee for probe_w3c_sf: are the soft-float routines correctly rounded,
and what do they cost?

The referee side uses Python Fractions and integer arithmetic only - it shares
no code with the L.in.oleum programme. Timing is read from the header the
programme wrote with its own high performance timer, so process startup and
the poll granularity of linorun.ps1 are excluded.
"""
import struct, sys
from fractions import Fraction

VEC = r"C:\programmieren\linoleum\work\sfvec.bin"
OUT = r"C:\programmieren\linoleum\work\sfout.bin"


def rn(frac, prec):
    if frac == 0:
        return Fraction(0)
    neg = frac < 0
    f = -frac if neg else frac
    p, q = f.numerator, f.denominator
    e = p.bit_length() - q.bit_length()
    if (p << max(0, -e)) < (q << max(0, e)):
        e -= 1
    s = e - prec + 1
    num, den = (p, q << s) if s >= 0 else (p << -s, q)
    n, r = divmod(num, den)
    if 2 * r > den or (2 * r == den and (n & 1)):
        n += 1
    out = Fraction(n << s) if s >= 0 else Fraction(n, 1 << -s)
    return -out if neg else out


def d2f(bits):
    return struct.unpack("<d", struct.pack("<Q", bits))[0]


def pack(v):
    """binary64 bits of an exact Fraction, round-nearest-even, no denormals."""
    if v == 0:
        return 0
    r = rn(v, 53)
    return struct.unpack("<Q", struct.pack("<d", float(r)))[0]


def main():
    vb = open(VEC, "rb").read()
    ob = open(OUT, "rb").read()
    hdr = struct.unpack_from("<16I", ob, 0)
    cpm, nvec, reps, cmul, cadd, cdiv, cxm, nrej, sink = hdr[:9]
    assert hdr[15] == 0x5346574C, "magic"
    print("counts per millisecond   %d" % cpm)
    print("vectors %d, reps %d, rejects %d" % (nvec, reps, nrej))
    tot = nvec * reps
    print()
    print("%-28s %12s %12s %12s" % ("routine", "counts", "ms total", "ns per call"))
    for name, c in (("SFMul  binary64 multiply", cmul),
                    ("SFAdd  binary64 add", cadd),
                    ("SFQuo  binary64 divide", cdiv),
                    ("XMul   64-bit mant. mul", cxm)):
        ms = c / cpm
        print("%-28s %12d %12.2f %12.1f" % (name, c, ms, ms * 1e6 / tot))

    # ------------------------------------------------ correctness
    badm = bada = badd = badx = 0
    firsts = []
    for i in range(nvec):
        aL, aH, bL, bH = struct.unpack_from("<4I", vb, 16 * i)
        mL, mH, sL, sH, qL, qH, xL, xH = struct.unpack_from("<8I", ob, 64 + 32 * i)
        A = Fraction(d2f(aL | (aH << 32)))
        B = Fraction(d2f(bL | (bH << 32)))
        if pack(A * B) != (mL | (mH << 32)):
            badm += 1
            if len(firsts) < 4:
                firsts.append("mul[%d] got %016x want %016x"
                              % (i, mL | (mH << 32), pack(A * B)))
        if pack(A + B) != (sL | (sH << 32)):
            bada += 1
            if len(firsts) < 4:
                firsts.append("add[%d] %r + %r got %016x want %016x"
                              % (i, float(A), float(B), sL | (sH << 32), pack(A + B)))
        if pack(A / B) != (qL | (qH << 32)):
            badd += 1
            if len(firsts) < 4:
                firsts.append("div[%d] got %016x want %016x"
                              % (i, qL | (qH << 32), pack(A / B)))
        # XMul: the two 64-bit mantissas are the vector words with bit 63 forced
        ma = (aL | (aH << 32)) | (1 << 63)
        mb = (bL | (bH << 32)) | (1 << 63)
        p = ma * mb                                     # in [2^126, 2^128)
        delta = 1 if p >= (1 << 127) else 0
        sh = 63 + delta
        m = p >> sh
        rbit = (p >> (sh - 1)) & 1
        sticky = p & ((1 << (sh - 1)) - 1)
        if rbit and (sticky or (m & 1)):
            m += 1
            if m >> 64:
                m >>= 1
                delta += 1
        gotm = xL | (xH << 32)
        gotd = delta
        if gotm != m:
            badx += 1
            if len(firsts) < 6:
                firsts.append("xmul[%d] got %016x d%d want %016x d%d"
                              % (i, gotm, gotd, m, delta))
    print()
    print("SFMul  mismatches vs exact round-nearest-even: %d / %d" % (badm, nvec))
    print("SFAdd  mismatches vs exact round-nearest-even: %d / %d" % (bada, nvec))
    print("SFQuo  mismatches vs exact round-nearest-even: %d / %d" % (badd, nvec))
    print("XMul   mismatches vs exact round-nearest-even: %d / %d" % (badx, nvec))
    for s in firsts:
        print("   " + s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
