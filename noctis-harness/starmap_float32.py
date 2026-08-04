"""Can a 32-bit-unit L.in.oleum float hold a Noctis star id at all?

Registers and memory units are 32 bits wide (docs/director.htm: "unit = 32"),
so the ** // ++ -- instructions round to IEEE binary32 after every step.
The catalogue stores binary64 values and search_id_code accepts a record only
when the computed id is within 1e-5 ABSOLUTE of the stored one.  This measures
how many of the catalogue's stars a single-precision id can still find.
"""

import struct
import sys
import numpy as np

HITS = r"C:\programmieren\linoleum\work\starmap_hits.txt"
STARMAP = r"C:\programmieren\noctis\niv-plus\data\STARMAP.BIN"
EPS = 1e-5
F = np.float32


def main():
    rows = []
    for line in open(HITS):
        rest = line[21:].split()
        cat = float(rest[0].replace("np.float64(", "").rstrip(")"))
        rows.append((line[:21].rstrip(), cat, int(rest[1]), int(rest[2]), int(rest[3])))
    print(f"{len(rows)} stars with known parsis coordinates\n")

    ok32 = 0
    worst = []
    for name, cat, x, y, z in rows:
        # exactly what "A ,= [x]; A // 100000f; A ** [y]; ..." would do
        t = F(x)
        t = F(t / F(100000))
        t = F(t * F(y))
        t = F(t / F(100000))
        t = F(t * F(z))
        t = F(t / F(100000))
        v = float(t)
        if abs(v - cat) < EPS:
            ok32 += 1
        worst.append((abs(v - cat), name, cat, v))

    print(f"float32 ids that still fall inside the +/-1e-5 lookup window: "
          f"{ok32}/{len(rows)} = {100.0*ok32/len(rows):.2f}%")
    worst.sort(reverse=True)
    print("\nlargest float32 errors (lookup epsilon = 1e-5):")
    for e, name, cat, v in worst[:6]:
        print(f"  {name:<20} stored={cat!r} float32={v!r} err={e:.4g}")
    print("\nsmallest float32 errors:")
    for e, name, cat, v in worst[-4:]:
        print(f"  {name:<20} stored={cat!r} float32={v!r} err={e:.4g}")

    # Also: is the coordinate itself representable?  Parsis coordinates reach
    # ~1e8, and binary32 has 24 mantissa bits = exact integers only to 2^24.
    xs = np.array([abs(r[2]) for r in rows] + [abs(r[3]) for r in rows]
                  + [abs(r[4]) for r in rows])
    print(f"\nparsis |coordinate| max in the swept sample: {xs.max()}")
    print(f"binary32 represents integers exactly only up to 2^24 = {2**24}")
    print(f"  coordinates already too large for exact float32: "
          f"{int((xs > 2**24).sum())}/{len(xs)} = {100.0*(xs > 2**24).mean():.2f}%")

    blob = open(STARMAP, "rb").read()[4:]
    ids = np.array([struct.unpack_from("<d", blob, i * 32)[0]
                    for i in range(len(blob) // 32) if blob[i * 32 + 29] == ord("S")])
    ulp32 = np.abs(ids) * 2 ** -24
    print(f"\nover the whole catalogue ({len(ids)} stars): one binary32 ulp of |id|")
    print(f"  exceeds the 1e-5 window for {int((ulp32 > EPS).sum())}/{len(ids)} = "
          f"{100.0*(ulp32 > EPS).mean():.2f}% of stars (|id| > {EPS*2**24:.4g})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
