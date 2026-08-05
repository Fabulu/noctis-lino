"""Does rnd53(80-bit x87 chain) == rnd53(exact x*y*z/1e15) in general, or only
on the 4194 charted stars?

Chain A is  x/100000*y/100000*z/100000  with every x87 op rounded to `prec`
bits, then one store to double.  ONCE53 is the exact integer product x*y*z
divided by 10^15 and rounded once.  If the two never disagree, the star
identity needs NO floating-point arithmetic at all - just the exact 96-bit
product we already have, and one correctly-rounded scaled division.

Everything here is plain Python ints: (sign, mantissa, exp2) with mantissa
exactly `prec` bits.  No Fractions, so it runs over a whole galaxy.
"""
import sys, struct

sys.path.insert(0, r"C:\programmieren\linoleum\tests")
import galaxyspec as G          # the refereed hash
import starmapspec as S

E5 = 100000
E15 = 10 ** 15


def norm(num, den, prec):
    """round(num/den) to `prec` significant bits, nearest-even.
    num>0, den>0.  Returns (m, e) with value = m*2^e and m exactly prec bits."""
    e = num.bit_length() - den.bit_length()
    if (num << max(0, -e)) < (den << max(0, e)):
        e -= 1                                     # now 2^e <= num/den < 2^(e+1)
    sh = e - prec + 1
    d = den << max(0, sh)
    q, r = divmod(num << max(0, -sh), d)
    if 2 * r > d or (2 * r == d and (q & 1)):
        q += 1
        if q.bit_length() > prec:                  # rounded up out of the binade
            q >>= 1
            sh += 1
    return q, sh


def chainA(x, y, z, prec):
    """(sign, m, e) of the x87 chain at `prec` bits per operation."""
    sgn = (x < 0) ^ (y < 0) ^ (z < 0)
    ax, ay, az = abs(x), abs(y), abs(z)
    m, e = norm(ax, E5, prec)                       # x/1e5
    m, e2 = norm(m * ay, 1, prec); e += e2          # *y
    m, e2 = norm(m, E5, prec); e += e2              # /1e5
    m, e2 = norm(m * az, 1, prec); e += e2          # *z
    m, e2 = norm(m, E5, prec); e += e2              # /1e5
    return sgn, m, e


def to_double(sgn, m, e):
    v = float(m) * 2.0 ** e if -1000 < e < 900 else float(m << max(0, e))
    # exact path: build via integer ratio to avoid intermediate error
    from fractions import Fraction
    v = float(Fraction(m << e) if e >= 0 else Fraction(m, 1 << -e))
    return -v if sgn else v


def once53(x, y, z):
    p = x * y * z
    sgn = p < 0
    if p == 0:
        return 0.0
    m, e = norm(abs(p), E15, 53)
    return to_double(sgn, m, e)


def main():
    K = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    prec = int(sys.argv[2]) if len(sys.argv) > 2 else 64
    n = dis = 0
    worst = (0, None)
    for ix in range(-K, K + 1):
        sx = ix * S.SECTORSIZE
        for iy in range(-K, K + 1):
            sy = iy * S.SECTORSIZE
            for iz in range(-K, K + 1):
                tx, ty, tz, _net, flags = S.hash_sector(sx, sy, iz * S.SECTORSIZE)
                if flags:
                    continue
                x, y, z = S.s32(tx), S.s32(ty), S.s32(tz)
                if x == 0 or y == 0 or z == 0:
                    continue
                a = to_double(*chainA(x, y, z, prec))
                b = once53(x, y, z)
                n += 1
                if a != b:
                    dis += 1
                    if dis <= 5:
                        print("   DISAGREE (%d,%d,%d) chain=%r once=%r" % (x, y, z, a, b))
    print("K=%d prec=%d : %d live stars, %d disagreements (%.4g%%)"
          % (K, prec, n, dis, 100.0 * dis / max(n, 1)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
