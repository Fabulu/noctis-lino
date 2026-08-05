"""Are the 6 records that the 80-bit chain fails to reproduce PRECISION
failures, or WINDOW COLLISIONS - a different star claiming the record because
the acceptance window is 1e-5 ABSOLUTE and their |id| is tiny?

Sweeps a large box with the vectorised hash (validated against oracle.py by
starmap_sweep.selftest) and, for each record, lists every live star inside its
window together with whether that star's exact identity reproduces the stored
double bit-for-bit.
"""
import sys, struct, bisect
import numpy as np
from fractions import Fraction

sys.path.insert(0, r"C:\programmieren\linoleum\noctis-harness")
sys.path.insert(0, r"C:\programmieren\linoleum\work")
import starmap_sweep as SW
import probe_w3c_scale as P

SECTOR = 100000
W = 10 ** 10
STARMAP = r"C:\programmieren\noctis\niv-plus\data\STARMAP.BIN"


def sweep(K):
    ax = (np.arange(-K, K + 1, dtype=np.int64) * SECTOR).astype(np.uint32)
    out_x, out_y, out_z = [], [], []
    for sx in ax:
        gy, gz = np.meshgrid(ax, ax, indexing="ij")
        sxa = np.full(gy.shape, sx, dtype=np.uint32)
        tx, ty, tz, dead = SW.hash_block(sxa, gy.astype(np.uint32), gz.astype(np.uint32))
        keep = ~dead
        out_x.append(tx[keep]); out_y.append(ty[keep]); out_z.append(tz[keep])
    return (np.concatenate(out_x), np.concatenate(out_y), np.concatenate(out_z))


def main():
    K = int(sys.argv[1]) if len(sys.argv) > 1 else 80
    print("selftest:", SW.selftest())
    x, y, z = sweep(K)
    print("live stars in the K=%d box: %d" % (K, len(x)))
    # exact product needs ~80 bits -> use python ints via object array only for
    # candidates; first bucket by float identity to narrow.
    approx = (x.astype(np.float64) * 1e-5) * (y.astype(np.float64) * 1e-5) \
        * (z.astype(np.float64) * 1e-5)
    order = np.argsort(approx)
    approx_s = approx[order]

    blob = open(STARMAP, "rb").read()[4:]
    recs = {}
    for i in range(len(blob) // 32):
        r = blob[i * 32:(i + 1) * 32]
        if r[29] != ord("S"):
            continue
        nm = r[8:28].rstrip(b" \x00").decode("latin-1")
        recs.setdefault(nm, []).append(struct.unpack("<d", r[0:8])[0])

    want = ["SOLSTAR", "DECANTER", "GAIA", "SOLARIS PRIME", "EDOM", "P MCGOOHAN",
            # controls: three records the chain DOES reproduce, same treatment
            "PITSTOP 3", "HALLUCINOGENIA", "DARK NIGHT"]
    for nm in want:
        for stored in recs.get(nm, []):
            N = int(Fraction(stored) * 10 ** 15)
            lo = bisect.bisect_left(approx_s, stored - 2e-5)
            hi = bisect.bisect_right(approx_s, stored + 2e-5)
            cands = []
            for j in range(lo, hi):
                k = order[j]
                xi, yi, zi = int(np.int32(x[k])), int(np.int32(y[k])), int(np.int32(z[k]))
                if abs(xi * yi * zi - N) < W:
                    cands.append((xi, yi, zi))
            marks = ["%s%s" % ("EXACT " if P.once53(*c) == stored else "off   ", c)
                     for c in cands]
            print("%-16s |id|=%-12.5g stored=%r  candidates=%d"
                  % (nm, abs(stored), stored, len(cands)))
            for m in marks:
                print("      " + m)
    return 0


if __name__ == "__main__":
    sys.exit(main())
