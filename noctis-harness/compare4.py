"""Four-way bit-exact comparison of the Noctis galaxy hash.

    oracle.bin  - C, lifted from noctis-iv-lr            (int64_t product)
    python.bin  - independent Python, arbitrary precision (bignum product)
    lino.bin    - L.in.oleum, inline IMUL fragment { F7 EB }, stock toolchain
    lino2.bin   - L.in.oleum, *% instruction, compiler114m.exe + -Cpu i386m

The first three are independent implementations of the same specification;
the fourth is what this comparison is here to qualify. Agreement between
lino2 and lino alone would only prove the rewrite did not change anything,
so the C and Python references are what make the result non-circular: they
share neither the language nor the multiply mechanism.

Records are 5 little-endian uint32 per sector:
    temp_x, temp_y, temp_z, netpos, flags

Usage:
    python compare4.py [oracle.bin python.bin lino.bin lino2.bin]
"""

import hashlib
import itertools
import os
import struct
import sys

FIELDS = ("temp_x", "temp_y", "temp_z", "netpos", "flags")
REC = 20
DEFAULTS = ("oracle.bin", "python.bin", "lino.bin", "lino2.bin")


def load(path):
    if not os.path.exists(path):
        raise SystemExit(f"missing: {path}")
    blob = open(path, "rb").read()
    if len(blob) % REC:
        raise SystemExit(f"{path}: {len(blob)} bytes is not a multiple of {REC}")
    digest = hashlib.sha256(blob).hexdigest()
    recs = [struct.unpack_from("<5I", blob, i * REC) for i in range(len(blob) // REC)]
    return recs, digest


def main():
    paths = sys.argv[1:] or list(DEFAULTS)
    if len(paths) < 2:
        raise SystemExit("need at least two files to compare")

    sets, digests = {}, {}
    for p in paths:
        name = os.path.splitext(os.path.basename(p))[0]
        if name in sets:
            raise SystemExit(f"duplicate label {name!r} - two files share a basename")
        sets[name], digests[name] = load(p)

    for name in sets:
        print(f"  {name:<8} {len(sets[name]):>4} sectors  sha256 {digests[name]}")
    print()

    sizes = {name: len(recs) for name, recs in sets.items()}
    if len(set(sizes.values())) != 1:
        print(f"SECTOR COUNT MISMATCH: {sizes}")
        return 2
    n = next(iter(sizes.values()))

    all_ok = True
    for a, b in itertools.combinations(sets, 2):
        bad = [i for i in range(n) if sets[a][i] != sets[b][i]]
        if bad:
            all_ok = False
            print(f"  {a:<8} vs {b:<8}  MISMATCH in {len(bad)}/{n} sectors")
            for i in bad[:4]:
                print(f"      sector {i}:")
                for f, va, vb in zip(FIELDS, sets[a][i], sets[b][i]):
                    flag = "  <-- differs" if va != vb else ""
                    print(f"        {f:<7} {a}={va:>11}  {b}={vb:>11}{flag}")
        else:
            print(f"  {a:<8} vs {b:<8}  identical on all {n} sectors")

    print()
    if all_ok:
        print(f"ALL {len(sets)} IMPLEMENTATIONS AGREE, BIT FOR BIT.")
        ref = sets[next(iter(sets))]
        star = [r for r in ref if r[4] == 0]
        print(f"  {len(star)}/{n} sectors produced a star position with no cutoff")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
