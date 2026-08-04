"""Sweep sectors with the ported galaxy hash and match the results against
the real STARMAP.BIN catalogue.

The generator is a vectorised copy of noctis-harness/oracle.py (which is
already refereed against oracle.c). It is re-validated against oracle.py on
every run before any sweeping happens, so a vectorisation bug cannot quietly
inflate or deflate the match rate.

Usage:  python starmap_sweep.py <K>       sweeps sectors -K..K on all 3 axes
"""

import struct
import sys
import time
import numpy as np

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import oracle  # noqa: E402  (the proven scalar reference)

STARMAP = r"C:\programmieren\noctis\niv-plus\data\STARMAP.BIN"
SECTOR = 100000
CUTOFF = 50000
IDSCALE = 1e-5
M32 = np.uint32(0xFFFFFFFF)


def s32(a):
    """View a uint32 array as signed 32-bit."""
    return a.view(np.int32).astype(np.int64)


def fold_mul(a_u32, b_u32):
    """Signed 32x32 -> 64 with the high half folded into the low (imul; add edx,eax)."""
    prod = s32(a_u32) * s32(b_u32)          # exact in int64
    lo = (prod & 0xFFFFFFFF).astype(np.uint32)
    hi = ((prod >> 32) & 0xFFFFFFFF).astype(np.uint32)
    return hi + lo                           # uint32, wraps


def hash_block(sx, sy, sz):
    """sx/sy/sz: uint32 arrays of sector coords already multiplied by 100000."""
    sum_xz = sx + sz
    tx = (sum_xz & np.uint32(0x1FFFF)) + sx
    dead = tx == np.uint32(CUTOFF)
    tx = tx - np.uint32(CUTOFF)

    accum = fold_mul(tx, sum_xz)
    idk = sum_xz + accum

    ty = (accum & np.uint32(0x1FFFF)) + sy
    dead |= ty == np.uint32(CUTOFF)
    ty = ty - np.uint32(CUTOFF)

    accum = fold_mul(ty, idk)

    tz = (accum & np.uint32(0x1FFFF)) + sz
    dead |= tz == np.uint32(CUTOFF)
    tz = tz - np.uint32(CUTOFF)

    return s32(tx), s32(ty), s32(tz), dead


def selftest():
    """Referee the vectorised hash against the scalar oracle.py."""
    ks = list(range(-3, 4)) + [-137, 500, 1234, -9999]
    sx, sy, sz = [], [], []
    exp = []
    for a in ks:
        for b in ks:
            for c in ks:
                sx.append(a * SECTOR)
                sy.append(b * SECTOR)
                sz.append(c * SECTOR)
                r = oracle.hash_sector(a * SECTOR, b * SECTOR, c * SECTOR)
                exp.append(r)
    to_u32 = lambda v: np.array(v, dtype=np.int64).astype(np.uint32)
    tx, ty, tz, dead = hash_block(to_u32(sx), to_u32(sy), to_u32(sz))
    bad = 0
    for i, (ex, ey, ez, netpos, flags) in enumerate(exp):
        want = (oracle.signed32(ex), oracle.signed32(ey), oracle.signed32(ez))
        got = (int(tx[i]), int(ty[i]), int(tz[i]))
        if want != got or bool(flags) != bool(dead[i]):
            bad += 1
            if bad < 4:
                print(f"  SELFTEST MISMATCH {sx[i]},{sy[i]},{sz[i]}: want {want} flags {flags} "
                      f"got {got} dead {dead[i]}")
    print(f"selftest: {len(exp)} sectors vs oracle.py, mismatches = {bad}")
    return bad == 0


def load_catalogue():
    blob = open(STARMAP, "rb").read()[4:]
    stars, planets = [], []
    for i in range(len(blob) // 32):
        r = blob[i * 32:(i + 1) * 32]
        rec = (struct.unpack_from("<d", r, 0)[0], r[8:28].rstrip(b" ").decode("latin-1"))
        (stars if r[29:30] == b"S" else planets).append(rec)
    return stars, planets


def main():
    K = int(sys.argv[1]) if len(sys.argv) > 1 else 32
    if not selftest():
        return 1

    stars, planets = load_catalogue()
    cat_ids = np.array(sorted(s[0] for s in stars))
    name_of = {}
    for v, n in stars:
        name_of.setdefault(v, n)
    print(f"catalogue: {len(stars)} named stars, {len(planets)} named planets")

    ks = np.arange(-K, K + 1, dtype=np.int64) * SECTOR
    total = len(ks) ** 3
    print(f"sweeping sectors -{K}..{K} on each axis = {total} sectors")

    t0 = time.time()
    hits_a, hits_b, ndead, nlive = {}, {}, 0, 0
    KX, KY = np.meshgrid(ks, ks, indexing="ij")
    KXf, KYf = KX.ravel().astype(np.uint32), KY.ravel().astype(np.uint32)

    for kz in ks:
        sz = np.full(KXf.shape, kz, dtype=np.int64).astype(np.uint32)
        tx, ty, tz, dead = hash_block(KXf, KYf, sz)
        live = ~dead
        ndead += int(dead.sum())
        nlive += int(live.sum())
        x, y, z = tx[live].astype(np.float64), ty[live].astype(np.float64), tz[live].astype(np.float64)

        for tag, ids in (("A", x / 100000 * y / 100000 * z / 100000),
                         ("B", (x * IDSCALE) * (y * IDSCALE) * (z * IDSCALE))):
            lo = np.searchsorted(cat_ids, ids - IDSCALE, side="right")
            hi = np.searchsorted(cat_ids, ids + IDSCALE, side="left")
            m = hi > lo
            if m.any():
                d = hits_a if tag == "A" else hits_b
                for idx, l in zip(np.nonzero(m)[0], lo[m]):
                    d.setdefault(cat_ids[l], []).append(
                        (int(x[idx]), int(y[idx]), int(z[idx]), float(ids[idx])))

    dt = time.time() - t0
    print(f"swept {total} sectors in {dt:.1f}s ({total/max(dt,1e-9)/1e6:.2f} M/s); "
          f"{nlive} live, {ndead} killed by the coordinate==0 cutoff")

    for tag, d in (("A  x/1e5*y/1e5*z/1e5 (prepare_nearstar / update_star_label)", hits_a),
                   ("B  (x*idscale)*(y*idscale)*(z*idscale) (isthere)", hits_b)):
        print(f"\nformula {tag}")
        print(f"  catalogue stars reproduced: {len(d)}/{len(stars)} "
              f"= {100.0*len(d)/len(stars):.2f}%")
        multi = {k: v for k, v in d.items() if len(v) > 1}
        print(f"  catalogue ids claimed by >1 generated star (collisions): {len(multi)}")
        for k, v in list(multi.items())[:5]:
            print(f"    {name_of.get(k,'?')!r} id={k!r}: {v[:4]}")

    # bit-exactness of the two formulas on the matched stars
    exact_a = sum(1 for k, v in hits_a.items() if any(w[3] == k for w in v))
    exact_b = sum(1 for k, v in hits_b.items() if any(w[3] == k for w in v))
    print(f"\nbit-exact id reproduction (==, not epsilon): A {exact_a}/{len(hits_a)}, "
          f"B {exact_b}/{len(hits_b)}")

    only_a = set(hits_a) - set(hits_b)
    only_b = set(hits_b) - set(hits_a)
    print(f"matched by A but not B: {len(only_a)}; by B but not A: {len(only_b)}")

    named = [(k, name_of.get(k, "?")) for k in sorted(hits_a)]
    out = rf"C:\programmieren\linoleum\work\starmap_hits{'' if K == 64 else K}.txt"
    with open(out, "w") as fh:
        for k, n in named:
            x, y, z, gid = hits_a[k][0]
            fh.write(f"{n:<21} {k!r:<24} {x} {y} {z}  gen={gid!r}\n")
    print(f"wrote {len(named)} matches to {out}")
    print("sample:", [n for _, n in named[:12]])
    return 0


if __name__ == "__main__":
    sys.exit(main())
