"""Which arithmetic produced the id values stored in STARMAP.BIN?

The catalogue was written by Borland C++ 3.1 on a 387, where every
intermediate of `x/100000*y/100000*z/100000` lives in an 80-bit x87 register
(64-bit mantissa) and only the final store rounds to double.  Modern IEEE
double-everywhere arithmetic rounds five times instead of once, so the two
need not agree in the last ulp.  This measures which one matches the file.

Reads work/starmap_hits.txt produced by starmap_sweep.py.
"""

import struct
import sys
from fractions import Fraction

HITS = r"C:\programmieren\linoleum\work\starmap_hits.txt"


def rnd(frac, prec):
    """Round a Fraction to `prec` mantissa bits, nearest-even, and return a Fraction."""
    if frac == 0:
        return Fraction(0)
    neg = frac < 0
    f = -frac if neg else frac
    e = 0
    while f >= 2:
        f /= 2
        e += 1
    while f < 1:
        f *= 2
        e -= 1
    scaled = f * (1 << (prec - 1))
    n = scaled.numerator // scaled.denominator
    rem = scaled - n
    if rem > Fraction(1, 2) or (rem == Fraction(1, 2) and n % 2):
        n += 1
    out = Fraction(n, 1 << (prec - 1)) * Fraction(2) ** e
    return -out if neg else out


def id_at(x, y, z, prec):
    """x/100000*y/100000*z/100000, left-associative, rounded to `prec` bits per step."""
    t = rnd(Fraction(x, 100000), prec)
    t = rnd(t * y, prec)
    t = rnd(t / 100000, prec)
    t = rnd(t * z, prec)
    t = rnd(t / 100000, prec)
    return t


def to_double(frac):
    return float(rnd(frac, 53))


def main():
    import re
    num = re.compile(r"np\.float64\(([^)]*)\)|(-?[\d.eE+-]+)")
    rows = []
    for line in open(HITS):
        name = line[:21].rstrip()
        rest = line[21:].split()
        cat = float(rest[0].replace("np.float64(", "").rstrip(")"))
        x, y, z = int(rest[1]), int(rest[2]), int(rest[3])
        rows.append((name, cat, x, y, z))
    print(f"{len(rows)} matched stars from {HITS}")

    stats = {k: 0 for k in ("A53", "A64", "B53", "B64")}
    ulp_off = {}
    for name, cat, x, y, z in rows:
        a53 = to_double(id_at(x, y, z, 53))
        a64 = to_double(id_at(x, y, z, 64))
        b53 = (x * 1e-5) * (y * 1e-5) * (z * 1e-5)
        # B in 80-bit: idscale itself is the double nearest 1e-5
        sc = Fraction(struct.unpack("<d", struct.pack("<d", 1e-5))[0])
        b64f = rnd(rnd(rnd(Fraction(x) * sc, 64) * rnd(Fraction(y) * sc, 64), 64)
                   * rnd(Fraction(z) * sc, 64), 64)
        b64 = to_double(b64f)
        for tag, v in (("A53", a53), ("A64", a64), ("B53", b53), ("B64", b64)):
            if v == cat:
                stats[tag] += 1
            else:
                ulp_off.setdefault(tag, []).append((name, cat, v))

    print("\nbit-exact reproduction of the catalogue double:")
    for k in ("A53", "A64", "B53", "B64"):
        print(f"  {k}: {stats[k]}/{len(rows)} = {100.0*stats[k]/len(rows):.2f}%")
    print("   A = x/100000*y/100000*z/100000 (left-assoc, as in prepare_nearstar)")
    print("   B = (x*idscale)*(y*idscale)*(z*idscale) (as in isthere)")
    print("   53 = IEEE double throughout; 64 = 80-bit x87 intermediates, one final round")

    best = min(stats, key=lambda k: -stats[k])
    print(f"\nnon-matching examples for {best}:")
    for name, cat, v in ulp_off.get(best, [])[:8]:
        print(f"   {name:<20} file={cat!r} computed={v!r} "
              f"reldiff={abs(v-cat)/max(abs(cat),1e-300):.3e}")

    # How far off are the misses, in units of the lookup epsilon?
    for tag in ("A53", "A64"):
        miss = ulp_off.get(tag, [])
        if miss:
            worst = max(abs(v - c) for _, c, v in miss)
            print(f"  {tag}: {len(miss)} misses, worst absolute error {worst:.3e} "
                  f"(lookup epsilon is 1e-5)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
