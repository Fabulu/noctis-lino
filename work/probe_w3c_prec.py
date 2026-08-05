"""RECON C step 1-2: exactly what the STARMAP oracle demands, and the
minimum precision that satisfies it.

No dependence on the earlier transcript's numbers - everything is recomputed
from C:\\programmieren\\noctis\\niv-plus\\data\\STARMAP.BIN and from the
sector coordinates recovered by the sweep.
"""
import struct, sys, re
from fractions import Fraction

HITS = r"C:\programmieren\linoleum\work\starmap_hits.txt"
STARMAP = r"C:\programmieren\noctis\niv-plus\data\STARMAP.BIN"


# ---------------------------------------------------------------- rounding
def rnd(frac, prec):
    """Round a Fraction to `prec` significant bits, nearest-even. Exact."""
    if frac == 0:
        return Fraction(0)
    neg = frac < 0
    f = -frac if neg else frac
    p, q = f.numerator, f.denominator
    e = p.bit_length() - q.bit_length()          # 2^(e-1) <= f < 2^(e+1)
    if p * (1 << max(0, -e)) < q * (1 << max(0, e)):
        e -= 1
    # invariant: 2^e <= f < 2^(e+1)
    s = e - prec + 1                             # want n = round(f / 2^s)
    if s >= 0:
        num, den = p, q << s
    else:
        num, den = p << (-s), q
    n, r2 = divmod(num, den)                     # n in [2^(prec-1), 2^prec]
    if 2 * r2 > den or (2 * r2 == den and (n & 1)):
        n += 1
    out = Fraction(n << s) if s >= 0 else Fraction(n, 1 << (-s))
    return -out if neg else out


def to_double(frac):
    return float(rnd(frac, 53))


E5 = Fraction(100000)
E15 = Fraction(10 ** 15)


def chainA(x, y, z, prec):
    """nearstar_x/100000*nearstar_y/100000*nearstar_z/100000, left to right,
    every x87 operation rounded to `prec` bits (the register precision)."""
    t = rnd(Fraction(x) / E5, prec)
    t = rnd(t * y, prec)
    t = rnd(t / E5, prec)
    t = rnd(t * z, prec)
    t = rnd(t / E5, prec)
    return t


def exact_once(x, y, z):
    """The exact rational x*y*z/1e15, rounded ONCE to double.
    x*y*z is an exact integer, so this needs no float arithmetic at all -
    only an exact 96-bit product and one correctly-rounded division."""
    return Fraction(x * y * z, 10 ** 15)


def main():
    rows = []
    for line in open(HITS):
        name = line[:21].rstrip()
        rest = line[21:].split()
        cat = float(rest[0].replace("np.float64(", "").rstrip(")"))
        rows.append((name, cat, int(rest[1]), int(rest[2]), int(rest[3])))
    n = len(rows)
    print("rows in %s: %d" % (HITS, n))

    # --------------------------------------------- how ambiguous is a "hit"?
    # a record is claimed by (x,y,z) when |computed - stored| < 1e-5 ABSOLUTE.
    # For |id| ~ 100 that window is ~1e-7 RELATIVE - far wider than a double
    # ulp - so a small-|id| record can be claimed by coordinates that did not
    # produce it. Those records cannot referee a precision question.
    print()
    hdr = "%-8s %8s %8s %8s %8s %8s" % ("|id| >=", "count", "A53", "A64",
                                        "ONCE53", "A64==ONCE")
    print(hdr)
    print("-" * len(hdr))

    results = {}
    for name, cat, x, y, z in rows:
        exact = exact_once(x, y, z)
        r = {
            "A53": to_double(chainA(x, y, z, 53)),
            "A64": to_double(chainA(x, y, z, 64)),
            "A80": to_double(chainA(x, y, z, 113)),   # ~unbounded per-op
            "ONCE53": to_double(exact),
        }
        results[(name, x, y, z)] = (cat, r)

    for thresh in (0, 1e2, 1e3, 1e4, 1e5, 1e6):
        sub = [(c, r) for (c, r) in results.values() if abs(c) >= thresh]
        if not sub:
            continue
        a53 = sum(1 for c, r in sub if r["A53"] == c)
        a64 = sum(1 for c, r in sub if r["A64"] == c)
        o53 = sum(1 for c, r in sub if r["ONCE53"] == c)
        agree = sum(1 for c, r in sub if r["A64"] == r["ONCE53"])
        print("%-8g %8d %8d %8d %8d %8d" % (thresh, len(sub), a53, a64, o53, agree))

    # --------------------------------------------- the six A64 misses
    print("\nA64 misses in full:")
    for (name, x, y, z), (cat, r) in results.items():
        if r["A64"] != cat:
            print("  %-20s stored=%r  A64=%r  ONCE53=%r  reldiff=%.3e"
                  % (name, cat, r["A64"], r["ONCE53"],
                     abs(r["A64"] - cat) / max(abs(cat), 1e-300)))

    # --------------------------------------------- collision census
    # how many DISTINCT (x,y,z) in the swept box land inside a given record's
    # window?  If more than one, the row's coordinates are not identified.
    from collections import Counter
    byname = Counter(nm for (nm, _x, _y, _z) in results)
    dupes = {k: v for k, v in byname.items() if v > 1}
    print("\nnames claimed by more than one (x,y,z) in this file: %d" % len(dupes))

    # --------------------------------------------- where A64 and ONCE53 part
    dis = [(nm, x, y, z, c, r) for (nm, x, y, z), (c, r) in results.items()
           if r["A64"] != r["ONCE53"]]
    print("A64 != ONCE53 on %d/%d rows (%.3f%%)" % (len(dis), n, 100.0 * len(dis) / n))
    for nm, x, y, z, c, r in dis[:6]:
        e = exact_once(x, y, z)
        print("   %-20s exact=%s" % (nm, float(e)))
        print("      A64=%r ONCE53=%r stored=%r" % (r["A64"], r["ONCE53"], c))

    # --------------------------------------------- per-op precision ladder
    print("\nper-operation precision ladder, all %d rows, "
          "chain A rounded to p bits then stored as double:" % n)
    for p in (24, 32, 40, 48, 53, 56, 60, 62, 63, 64, 65, 70, 80, 113):
        hit = sum(1 for (nm, x, y, z), (c, r) in results.items()
                  if to_double(chainA(x, y, z, p)) == c)
        print("   p=%-4d %6d/%d = %6.2f%%" % (p, hit, n, 100.0 * hit / n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
