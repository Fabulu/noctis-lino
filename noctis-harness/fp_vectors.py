"""WAVE 3 / IMPLEMENTER 2 - test vectors, and the STARMAP hit set REGENERATED.

The house standard forbids grading against a stored artifact.  Every existing
starmap_*.py reads work/starmap_hits.txt, a file produced by an earlier run of
a tool nobody re-ran; the decision document calls that out (section 3(g)) and
this file is the replacement.  Nothing here is read from a previous sweep: the
galaxy hash is swept live, the catalogue is read from STARMAP.BIN itself, and
the window collisions are re-derived rather than looked up.

THE CIRCULARITY THAT HAD TO BE DESIGNED OUT.  MEASURED: 81 of the 4194
reachable catalogue records have more than one live star inside the +-1e-5
acceptance window - not the six the decision document expected, because six is
the number that happened to be MIS-resolved by the old sweep's first-found
rule, not the number that collide.  The obvious fix, "keep whichever candidate
reproduces the stored double", grades the engine against the answer and would
hand 4194/4194 to any engine at all.  So no candidate is ever selected here.
Every candidate of every record is emitted as its own case, and fp_starmap.py
scores a record as reproduced when SOME candidate reproduces it.  The rule is
fixed before any engine runs and is identical for the engine under test and
for the negative controls, which is what makes the other scores meaningful.

Usage:
    python fp_vectors.py starmap [K]        default K=64, the oracle set
    python fp_vectors.py galaxy  [K]        default K=40, every live star
    python fp_vectors.py scalar  [N]        boundary + random doubles
"""

import os
import struct
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fp_sched  # noqa: E402

STARMAP = r"C:\programmieren\noctis\niv-plus\data\STARMAP.BIN"
OUTDIR = fp_sched.OUTDIR
SECTOR = 100000
CUTOFF = 50000
IDSCALE = 1e-5
VMAGIC = 0x46505643

# ---------------------------------------------------------------------------
# The galaxy hash.  Written here from the algorithm (imul; add edx,eax; the
# 0x1FFFF window; the ==50000 cutoff), then refereed on every run against
# noctis-harness/oracle.py, which is an independently-written scalar version
# already refereed against oracle.c.  A vectorisation slip therefore cannot
# quietly change how many stars exist.
# ---------------------------------------------------------------------------


def _s32(u):
    return u.view(np.int32).astype(np.int64)


def _foldmul(a, b):
    p = _s32(a) * _s32(b)
    return (((p >> 32) & 0xFFFFFFFF).astype(np.uint32)
            + (p & 0xFFFFFFFF).astype(np.uint32))


def hash_block(sx, sy, sz):
    sxz = sx + sz
    tx = (sxz & np.uint32(0x1FFFF)) + sx
    dead = tx == np.uint32(CUTOFF)
    tx = tx - np.uint32(CUTOFF)
    acc = _foldmul(tx, sxz)
    idk = sxz + acc
    ty = (acc & np.uint32(0x1FFFF)) + sy
    dead |= ty == np.uint32(CUTOFF)
    ty = ty - np.uint32(CUTOFF)
    acc = _foldmul(ty, idk)
    tz = (acc & np.uint32(0x1FFFF)) + sz
    dead |= tz == np.uint32(CUTOFF)
    tz = tz - np.uint32(CUTOFF)
    return _s32(tx), _s32(ty), _s32(tz), dead


def selftest():
    import oracle
    ks = list(range(-4, 5)) + [-137, 500, 1234, -9999, 31337, -65536]
    sx, sy, sz, exp = [], [], [], []
    for a in ks:
        for b in ks:
            for c in ks:
                sx.append(a * SECTOR); sy.append(b * SECTOR); sz.append(c * SECTOR)
                exp.append(oracle.hash_sector(a * SECTOR, b * SECTOR, c * SECTOR))
    u = lambda v: np.array(v, dtype=np.int64).astype(np.uint32)
    tx, ty, tz, dead = hash_block(u(sx), u(sy), u(sz))
    bad = 0
    for i, (ex, ey, ez, _np_, fl) in enumerate(exp):
        want = (oracle.signed32(ex), oracle.signed32(ey), oracle.signed32(ez))
        got = (int(tx[i]), int(ty[i]), int(tz[i]))
        if want != got or bool(fl) != bool(dead[i]):
            bad += 1
    print("hash selftest vs oracle.py: %d sectors, %d mismatches" % (len(exp), bad))
    return bad == 0


def load_catalogue(path=STARMAP):
    blob = open(path, "rb").read()
    head, body = blob[:4], blob[4:]
    stars, planets = [], []
    for i in range(len(body) // 32):
        r = body[i * 32:(i + 1) * 32]
        v = struct.unpack_from("<d", r, 0)[0]
        nm = r[8:28].rstrip(b" \x00").decode("latin-1")
        (stars if r[29:30] == b"S" else planets).append((v, nm))
    return head, stars, planets


def sweep(K):
    ks = np.arange(-K, K + 1, dtype=np.int64) * SECTOR
    KX, KY = np.meshgrid(ks, ks, indexing="ij")
    KXf = KX.ravel().astype(np.uint32)
    KYf = KY.ravel().astype(np.uint32)
    xs, ys, zs = [], [], []
    ndead = 0
    for kz in ks:
        sz = np.full(KXf.shape, kz, dtype=np.int64).astype(np.uint32)
        tx, ty, tz, dead = hash_block(KXf, KYf, sz)
        live = ~dead
        ndead += int(dead.sum())
        xs.append(tx[live]); ys.append(ty[live]); zs.append(tz[live])
    return (np.concatenate(xs), np.concatenate(ys), np.concatenate(zs),
            len(ks) ** 3, ndead)


def build_starmap_cases(K=64, window=IDSCALE):
    if not selftest():
        raise SystemExit("hash selftest FAILED - refusing to sweep")
    head, stars, planets = load_catalogue()
    print("STARMAP.BIN: header %r, %d star records, %d planet records"
          % (head, len(stars), len(planets)))

    # one entry per DISTINCT stored id; a star named twice is one datum
    ids = {}
    for v, nm in stars:
        ids.setdefault(v, nm)
    cat = np.array(sorted(ids), dtype=np.float64)
    print("distinct stored star identities: %d" % len(cat))

    t0 = time.time()
    x, y, z, nsect, ndead = sweep(K)
    print("swept sectors -%d..%d on 3 axes = %d sectors in %.1fs; %d live, %d cut off"
          % (K, K, nsect, time.time() - t0, len(x), ndead))

    approx = (x.astype(np.float64) / 100000.0 * y.astype(np.float64) / 100000.0
              * z.astype(np.float64) / 100000.0)
    order = np.argsort(approx, kind="stable")
    aps = approx[order]

    lo = np.searchsorted(aps, cat - window, side="left")
    hi = np.searchsorted(aps, cat + window, side="right")
    ncand = hi - lo

    reached = np.nonzero(ncand > 0)[0]
    collide = np.nonzero(ncand > 1)[0]
    print("catalogue identities with >=1 candidate in the +-%g window: %d/%d"
          % (window, len(reached), len(cat)))
    print("catalogue identities with >1 candidate (WINDOW COLLISIONS): %d"
          % len(collide))
    for ci in collide:
        v = float(cat[ci])
        cands = [(int(x[order[j]]), int(y[order[j]]), int(z[order[j]]))
                 for j in range(lo[ci], hi[ci])]
        print("   %-18s id=%r  %d candidates %s"
              % (ids[v], v, len(cands), cands))

    cases, manifest = [], []
    for rec, ci in enumerate(reached):
        v = float(cat[ci])
        for j in range(lo[ci], hi[ci]):
            k = order[j]
            xi, yi, zi = int(x[k]), int(y[k]), int(z[k])
            manifest.append((len(cases), rec, ids[v],
                             struct.unpack("<Q", struct.pack("<d", v))[0],
                             xi, yi, zi))
            cases.append(([0, 0, 0, 0], [xi, yi, zi, 0], 0x70))
    print("cases emitted: %d for %d records" % (len(cases), len(reached)))
    return cases, manifest, len(reached)


def write_vec(path, sid, cw, cases):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out = bytearray()
    out += struct.pack("<8I", VMAGIC, 1, len(cases), 16, sid, cw, 0, 0)
    for f64, i32, mask in cases:
        u = []
        for b in f64:
            u.append(b & 0xFFFFFFFF)
            u.append((b >> 32) & 0xFFFFFFFF)
        for v in i32:
            u.append(struct.unpack("<I", struct.pack("<i", v))[0])
        u += [mask, 0, 0, 0]
        assert len(u) == 16
        out += struct.pack("<16I", *u)
    open(path, "wb").write(bytes(out))
    return len(out)


def write_manifest(path, manifest, nrec):
    with open(path, "w", newline="\n") as fh:
        fh.write("# case\trecord\tname\tstored_hex\tx\ty\tz\n")
        fh.write("# records=%d cases=%d\n" % (nrec, len(manifest)))
        for c, r, nm, hx, xi, yi, zi in manifest:
            fh.write("%d\t%d\t%s\t%016x\t%d\t%d\t%d\n" % (c, r, nm, hx, xi, yi, zi))


def cmd_starmap(argv):
    K = int(argv[0]) if argv else 64
    cases, manifest, nrec = build_starmap_cases(K)
    vec = os.path.join(OUTDIR, "fpvec_starmap.bin")
    man = os.path.join(OUTDIR, "fpcases_starmap.tsv")
    n = write_vec(vec, fp_sched.CHAINS["NsIdentity"].sid, 0x133F, cases)
    write_manifest(man, manifest, nrec)
    print("wrote %s (%d bytes) and %s" % (vec, n, man))
    return 0


def cmd_scalar(argv):
    """Level-2 scalar vectors: values chosen to land on rounding boundaries
    rather than at random, plus a random tail seeded fixed."""
    N = int(argv[0]) if argv else 2048
    rng = np.random.default_rng(20260805)
    vals = []
    # exact-tie makers: consecutive doubles, powers of two, and values whose
    # sum/product falls exactly halfway between two representable numbers
    seeds = [1.0, 2.0, 0.5, 3.0, 1e-5, 1e5, 1e10, 1e-10, 1.0 + 2 ** -52,
             1.0 - 2 ** -53, 2 ** -1022, 16777216.0, 16777217.0, 9007199254740993.0,
             1234567.891, -3.8e6, 3.8e6, 1e300, 1e-300]
    for a in seeds:
        for b in seeds:
            vals.append((a, b))
    while len(vals) < N:
        e1 = int(rng.integers(-60, 60))
        e2 = int(rng.integers(-60, 60))
        a = float(rng.random() * 2 - 1) * (2.0 ** e1)
        b = float(rng.random() * 2 - 1) * (2.0 ** e2)
        if a == 0.0 or b == 0.0:
            continue
        vals.append((a, b))
    vals = vals[:N]
    cases = []
    for a, b in vals:
        ba = struct.unpack("<Q", struct.pack("<d", a))[0]
        bb = struct.unpack("<Q", struct.pack("<d", abs(b) if b else 1.0))[0]
        cases.append(([ba, bb, 0, 0], [0, 0, 0, 0], 0x03))
    # fsqrt takes only the first operand, and a negative one is a NaN on
    # silicon and undefined in exact arithmetic; give that chain |a|.
    scases = []
    for f64, i32, mask in cases:
        a = struct.unpack("<d", struct.pack("<Q", f64[0]))[0]
        ba = struct.unpack("<Q", struct.pack("<d", abs(a)))[0]
        scases.append(([ba, f64[1], 0, 0], i32, mask))
    for name in ("ScalarAdd", "ScalarSub", "ScalarMul", "ScalarDiv",
                 "ScalarSqrt", "ScalarDiffSq"):
        c = fp_sched.CHAINS[name]
        p = os.path.join(OUTDIR, "fpvec_%s.bin" % name.lower())
        use = scases if name == "ScalarSqrt" else cases
        n = write_vec(p, c.sid, c.cw, use)
        print("wrote %s (%d cases, %d bytes)" % (p, len(use), n))
    return 0


def cmd_galaxy(argv):
    """The galaxy-scale differential set.

    The STARMAP oracle is necessary but NOT sufficient: it cannot separate the
    true 64-bit chain from an exact product rounded once, because those two
    agree on all but about one star in 3400 and 4194 rows is too few to see it.
    This set is the one that can.  Every live star in the K box is a case, so
    the disagreements are actually present in the data rather than being argued
    about, and the reference answer comes from a physical CPU executing the
    schedule - not from a model of one.
    """
    K = int(argv[0]) if argv else 40
    if not selftest():
        raise SystemExit("hash selftest FAILED")
    t0 = time.time()
    x, y, z, nsect, ndead = sweep(K)
    print("K=%d box: %d sectors, %d live, %d cut off, %.1fs"
          % (K, nsect, len(x), ndead, time.time() - t0))
    cases = [([0, 0, 0, 0], [int(x[i]), int(y[i]), int(z[i]), 0], 0x70)
             for i in range(len(x))]
    vec = os.path.join(OUTDIR, "fpvec_galaxy.bin")
    n = write_vec(vec, fp_sched.CHAINS["NsIdentity"].sid, 0x133F, cases)
    print("wrote %s (%d cases, %d bytes)" % (vec, len(cases), n))
    return 0


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd = sys.argv[1]
    if cmd == "starmap":
        return cmd_starmap(sys.argv[2:])
    if cmd == "galaxy":
        return cmd_galaxy(sys.argv[2:])
    if cmd == "scalar":
        return cmd_scalar(sys.argv[2:])
    print("unknown command %r" % cmd)
    return 2


if __name__ == "__main__":
    sys.exit(main())
