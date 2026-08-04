"""How badly does IEEE-double id arithmetic break the catalogue lookup?

search_id_code() accepts a record when |computed_id - stored_id| < 1e-5, and
the stored ids were computed with 80-bit x87 intermediates.  A port that
computes the id in plain doubles introduces a rounding difference that scales
with |id|.  This measures where that difference eats the epsilon.
"""

import re
import struct
import sys
from fractions import Fraction

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
from starmap_precision import id_at, to_double  # noqa: E402

HITS = r"C:\programmieren\linoleum\work\starmap_hits.txt"
STARMAP = r"C:\programmieren\noctis\niv-plus\data\STARMAP.BIN"
EPS = 1e-5


def main():
    rows = []
    for line in open(HITS):
        name = line[:21].rstrip()
        rest = line[21:].split()
        cat = float(rest[0].replace("np.float64(", "").rstrip(")"))
        rows.append((name, cat, int(rest[1]), int(rest[2]), int(rest[3])))

    buckets = {}
    worst = []
    for name, cat, x, y, z in rows:
        a53 = to_double(id_at(x, y, z, 53))
        a64 = to_double(id_at(x, y, z, 64))
        err = abs(a53 - a64)
        mag = abs(a64)
        b = 0 if mag == 0 else int(max(0, min(12, __import__("math").log10(mag) + 1)))
        d = buckets.setdefault(b, [0, 0.0, 0])
        d[0] += 1
        d[1] = max(d[1], err)
        if err >= EPS:
            d[2] += 1
        worst.append((err, name, mag, a53, a64, cat))

    print(f"{len(rows)} stars.  |A53 - A64| = the error a double-only port makes,")
    print(f"against the 1e-5 lookup epsilon.\n")
    print(f"{'|id| decade':>14} {'stars':>7} {'max err':>12} {'>= 1e-5':>8}")
    for b in sorted(buckets):
        n, mx, over = buckets[b]
        print(f"{'1e'+str(b-1)+'..1e'+str(b):>14} {n:>7} {mx:>12.3e} {over:>8}")

    worst.sort(reverse=True)
    print("\nlargest errors:")
    for err, name, mag, a53, a64, cat in worst[:8]:
        print(f"  {name:<20} |id|={mag:.6g}  err={err:.3e}  "
              f"{'BREAKS LOOKUP' if err >= EPS else 'ok'}")

    # Extrapolate to the whole catalogue: 1 ulp at |id| = M is 2^-52 * M, and
    # five roundings can compound.
    blob = open(STARMAP, "rb").read()[4:]
    ids = [struct.unpack_from("<d", blob, i * 32)[0]
           for i in range(len(blob) // 32) if blob[i * 32 + 29] == ord("S")]
    import math
    risky = [v for v in ids if abs(v) > 0 and 5 * 2 ** -53 * abs(v) > EPS]
    print(f"\ncatalogue stars where 5 ulp of |id| already exceeds 1e-5: "
          f"{len(risky)}/{len(ids)} = {100.0*len(risky)/len(ids):.2f}%  "
          f"(|id| > {EPS/(5*2**-53):.4g})")
    marginal = [v for v in ids if 2 ** -53 * abs(v) > EPS]
    print(f"catalogue stars where a single ulp exceeds 1e-5: {len(marginal)} "
          f"(|id| > {EPS*2**53:.4g})")
    print(f"catalogue |id| max = {max(abs(v) for v in ids):.6g}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
