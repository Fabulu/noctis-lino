"""End-to-end checks on the matched stars, and a profile of the ones we miss."""

import struct
import sys
import numpy as np

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
from starmap_sweep import hash_block, load_catalogue, SECTOR  # noqa: E402
from starmap_precision import id_at, to_double  # noqa: E402

EPS = 1e-5


def sweep_records(K):
    ks = np.arange(-K, K + 1, dtype=np.int64) * SECTOR
    KX, KY = np.meshgrid(ks, ks, indexing="ij")
    KXf, KYf = KX.ravel().astype(np.uint32), KY.ravel().astype(np.uint32)
    xs, ys, zs, ids = [], [], [], []
    for kz in ks:
        sz = np.full(KXf.shape, kz, dtype=np.int64).astype(np.uint32)
        tx, ty, tz, dead = hash_block(KXf, KYf, sz)
        live = ~dead
        x = tx[live].astype(np.float64)
        y = ty[live].astype(np.float64)
        z = tz[live].astype(np.float64)
        xs.append(x); ys.append(y); zs.append(z)
        ids.append(x / 100000 * y / 100000 * z / 100000)
    return (np.concatenate(xs), np.concatenate(ys),
            np.concatenate(zs), np.concatenate(ids))


def main():
    K = int(sys.argv[1]) if len(sys.argv) > 1 else 64
    stars, planets = load_catalogue()
    name_of = {}
    for v, n in stars:
        name_of.setdefault(v, n)
    cat = np.array(sorted(name_of))

    x, y, z, ids = sweep_records(K)
    order = np.argsort(ids)
    x, y, z, ids = x[order], y[order], z[order], ids[order]
    print(f"sweep -{K}..{K}: {len(ids)} stars")

    lo = np.searchsorted(ids, cat - EPS, side="right")
    hi = np.searchsorted(ids, cat + EPS, side="left")
    hit = hi > lo

    print(f"matched {int(hit.sum())}/{len(cat)}")

    # --- landmarks ---
    print("\nlandmark stars (ids hard-coded in niv-lr/src/noctis-1.cpp:3164/3187/3208):")
    for want, label in ((-0.037828, "BALASTRACKONASTREYA"), (15995.51984, "FENIA"),
                        (-0.11543634, "YLASTRAVENYA")):
        i = np.searchsorted(cat, want - 1e-4)
        j = np.searchsorted(cat, want + 1e-4)
        for k in range(i, j):
            if name_of[cat[k]] != label:
                continue
            if not hit[k]:
                print(f"  {label}: id {cat[k]!r} NOT in the -{K}..{K} sweep")
                continue
            a, b = lo[k], hi[k]
            for t in range(a, b):
                exact = to_double(id_at(int(x[t]), int(y[t]), int(z[t]), 64))
                print(f"  {label}: id {cat[k]!r} -> parsis "
                      f"({int(x[t])}, {int(y[t])}, {int(z[t])})  "
                      f"sector ({int(x[t])//100000}, {int(y[t])//100000}, {int(z[t])//100000})  "
                      f"x87-id {exact!r}  bitexact={exact == cat[k]}")

    # game start position, noctis-0.cpp:605-607
    dz = (3797120, -4352112, -925018)
    print(f"\ngame start dzat = {dz} -> sector "
          f"({dz[0]//100000}, {dz[1]//100000}, {dz[2]//100000})")

    # --- how many matched stars are bit-exact under x87, and are the misses collisions? ---
    nbit, nmiss, miss_multi = 0, 0, 0
    exact_rows = []
    for k in np.nonzero(hit)[0]:
        cands = list(range(lo[k], hi[k]))
        vals = [to_double(id_at(int(x[t]), int(y[t]), int(z[t]), 64)) for t in cands]
        good = [t for t, v in zip(cands, vals) if v == cat[k]]
        if good:
            nbit += 1
            t = good[0]
            exact_rows.append((name_of[cat[k]], cat[k],
                               int(x[t]), int(y[t]), int(z[t]), len(cands)))
        else:
            nmiss += 1
            if hi[k] - lo[k] > 1:
                miss_multi += 1
    out = rf"C:\programmieren\linoleum\work\starmap_exact{'' if K == 64 else K}.txt"
    with open(out, "w") as fh:
        for n, v, a, b, c, nc in exact_rows:
            fh.write(f"{n:<21} {v!r} {a} {b} {c} {nc}\n")
    print(f"wrote {len(exact_rows)} x87-bit-exact triples to {out}")
    print(f"\nof {int(hit.sum())} matched catalogue stars, {nbit} have at least one "
          f"generated triple whose 80-bit id equals the stored double bit-for-bit")
    print(f"  {nmiss} do not; of those, {miss_multi} had >1 candidate triple "
          f"(i.e. the epsilon window caught a collision, not the real star)")

    # --- profile of the unmatched ---
    un = cat[~hit]
    print(f"\nunmatched: {len(un)} catalogue stars")
    a = np.abs(un)
    a = a[a > 0]
    print("  |id| percentiles: " + ", ".join(
        f"p{p}={np.percentile(a, p):.4g}" for p in (10, 25, 50, 75, 90, 99)))
    print(f"  cube-root of median |id| = {np.percentile(a, 50) ** (1/3):.1f} "
          f"(rough mean sector magnitude)")
    inrange = int((a < (K + 0.9) ** 3).sum())
    print(f"  {inrange} of them have |id| small enough to have fitted in this box "
          f"(|id| < {(K+0.9)**3:.4g}) yet were not produced")
    print("  sample unmatched names:",
          [name_of[v] for v in un[:8]], "...",
          [name_of[v] for v in un[-4:]])
    return 0


if __name__ == "__main__":
    sys.exit(main())
