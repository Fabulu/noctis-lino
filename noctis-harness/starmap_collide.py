"""Quantify how much of the STARMAP match rate is real and how much is chance.

The star id is a lossy product of three coordinates, so a hit inside the
+/-1e-5 lookup window is not by itself proof that we generated the right star.
Three measurements:

  1. self-collision: how often two *different* generated stars share an id
     to within the lookup epsilon;
  2. a decoy control: the same match procedure run against catalogues whose
     ids have been perturbed enough to destroy any real correspondence but
     not their distribution.  Whatever that scores is the false-positive floor;
  3. coordinate-permutation collisions, which are systematic rather than random
     (id is symmetric under permuting x, y, z).
"""

import struct
import sys
import numpy as np

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
from starmap_sweep import hash_block, load_catalogue, s32, SECTOR, IDSCALE  # noqa: E402

EPS = 1e-5


def generate(K):
    ks = np.arange(-K, K + 1, dtype=np.int64) * SECTOR
    KX, KY = np.meshgrid(ks, ks, indexing="ij")
    KXf, KYf = KX.ravel().astype(np.uint32), KY.ravel().astype(np.uint32)
    chunks = []
    for kz in ks:
        sz = np.full(KXf.shape, kz, dtype=np.int64).astype(np.uint32)
        tx, ty, tz, dead = hash_block(KXf, KYf, sz)
        live = ~dead
        x = tx[live].astype(np.float64)
        y = ty[live].astype(np.float64)
        z = tz[live].astype(np.float64)
        chunks.append(x / 100000 * y / 100000 * z / 100000)
    return np.concatenate(chunks)


def count_hits(gen_sorted, cat):
    lo = np.searchsorted(gen_sorted, cat - EPS, side="right")
    hi = np.searchsorted(gen_sorted, cat + EPS, side="left")
    return int((hi > lo).sum())


def main():
    K = int(sys.argv[1]) if len(sys.argv) > 1 else 64
    stars, _ = load_catalogue()
    cat = np.array(sorted(s[0] for s in stars))

    print(f"generating sectors -{K}..{K} ...")
    gen = generate(K)
    gen.sort()
    print(f"{len(gen)} generated stars; |id| range {np.abs(gen).min():.3g} .. {np.abs(gen).max():.6g}")

    # --- 1. self-collision among generated stars ---
    gaps = np.diff(gen)
    coll = int((gaps < 2 * EPS).sum())
    print(f"\n1. self-collision: {coll} adjacent generated-id pairs are within 2e-5 "
          f"({100.0*coll/len(gen):.4f}% of generated stars have an epsilon-twin)")
    # how many distinct id 'clusters' does the sweep really resolve
    clusters = len(gen) - coll
    print(f"   the sweep's {len(gen)} stars resolve to ~{clusters} distinguishable ids")

    # --- 2. real vs decoy ---
    real = count_hits(gen, cat)
    print(f"\n2. real catalogue: {real}/{len(cat)} = {100.0*real/len(cat):.2f}% matched")
    rng = np.random.default_rng(20260804)
    scores = []
    for trial in range(8):
        # multiplicative jitter: preserves magnitude distribution exactly,
        # destroys the exact values.  1e-3 relative is >> the 1e-5 window
        # for every |id| above 0.01, and we report the small-|id| caveat.
        decoy = np.sort(cat * (1.0 + rng.uniform(1e-3, 5e-3, size=cat.shape)))
        scores.append(count_hits(gen, decoy))
    scores = np.array(scores)
    print(f"   decoy catalogues (id * (1+U[1e-3,5e-3])), 8 trials: "
          f"mean {scores.mean():.1f}, max {scores.max()}, "
          f"= {100.0*scores.mean()/len(cat):.3f}% false-positive floor")
    small = int((np.abs(cat) < 0.01).sum())
    print(f"   caveat: {small} catalogue ids have |id| < 0.01, where the "
          f"multiplicative decoy shifts by less than the window")

    # additive decoy avoids that caveat for small ids
    scores2 = []
    for trial in range(8):
        decoy = np.sort(cat + rng.uniform(1e-3, 5e-3, size=cat.shape))
        scores2.append(count_hits(gen, decoy))
    scores2 = np.array(scores2)
    print(f"   additive decoy (id + U[1e-3,5e-3]): mean {scores2.mean():.1f} "
          f"= {100.0*scores2.mean()/len(cat):.3f}%")

    # --- 3. permutation symmetry ---
    print("\n3. permutation collisions are systematic, not random:")
    print("   id = (x/1e5)*(y/1e5)*(z/1e5) is symmetric in x,y,z, and the hash")
    print("   emits mirrored sectors, so (X,Y,Z) and (Z,Y,X) share an id exactly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
