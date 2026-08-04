"""An exact-integer route to the star identity, avoiding floats entirely.

id = x*y*z / 1e15, and search_id_code accepts |computed - stored| < 1e-5.
Multiplying through, that is |x*y*z - stored*1e15| < 1e10 -- a comparison
between two integers, no floating point on our side at all.  x*y*z needs up
to ~80 bits, which the project's new *% split multiply can build exactly.

This checks the tolerance really is safe: it measures, for every star whose
coordinates we recovered, the exact integer gap and how much of the 1e10
budget it uses.
"""

import struct
import sys
from fractions import Fraction

HITS = r"C:\programmieren\linoleum\work\starmap_hits.txt"
STARMAP = r"C:\programmieren\noctis\niv-plus\data\STARMAP.BIN"
EPS = Fraction(1, 100000)
SCALE = 10 ** 15


def main():
    rows = []
    for line in open(HITS):
        rest = line[21:].split()
        cat = float(rest[0].replace("np.float64(", "").rstrip(")"))
        rows.append((line[:21].rstrip(), cat, int(rest[1]), int(rest[2]), int(rest[3])))

    budget = EPS * SCALE          # 1e10, exact
    print(f"{len(rows)} stars; integer budget = {int(budget)} out of |x*y*z| up to 1e24\n")

    worst = 0
    worst_row = None
    bits = 0
    fails = 0
    for name, cat, x, y, z in rows:
        exact = x * y * z                      # exact, arbitrary precision
        stored = Fraction(cat) * SCALE         # exact rational value of the double
        gap = abs(Fraction(exact) - stored)
        bits = max(bits, abs(exact).bit_length())
        if gap >= budget:
            fails += 1
        frac = float(gap / budget)
        if frac > worst:
            worst, worst_row = frac, (name, cat, x, y, z, float(gap))

    print(f"stars where |x*y*z - stored*1e15| >= 1e10 (would miss the lookup): {fails}")
    print(f"worst budget usage: {worst*100:.6f}%  ->  {worst_row}")
    print(f"widest x*y*z seen: {bits} bits")

    # widen to the whole catalogue: how many bits does the product need
    # anywhere in the galaxy?  |coord| <= |sector| + 81071.
    blob = open(STARMAP, "rb").read()[4:]
    ids = [struct.unpack_from("<d", blob, i * 32)[0]
           for i in range(len(blob) // 32) if blob[i * 32 + 29] == ord("S")]
    mx = max(abs(v) for v in ids)
    print(f"\ncatalogue max |id| = {mx:.6g}  ->  |x*y*z| up to {mx*SCALE:.6g} "
          f"= {int(mx*SCALE).bit_length()} bits")
    print(f"a 96-bit product (three 32-bit *% steps) covers it with "
          f"{96-int(mx*SCALE).bit_length()} bits to spare")

    # and the precision of the stored double itself, in budget units
    worst_ulp = max(abs(Fraction(v) * SCALE) * Fraction(2) ** -53 for v in ids)
    print(f"one ulp of the stored double, scaled: up to {float(worst_ulp):.4g} "
          f"= {float(worst_ulp/budget)*100:.4f}% of the 1e10 budget")
    return 0


if __name__ == "__main__":
    sys.exit(main())
