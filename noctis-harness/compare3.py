"""Three-way bit-exact comparison of the Noctis galaxy hash.

    oracle.bin  - C, lifted from noctis-iv-lr
    python.bin  - independent Python, arbitrary precision
    lino.bin    - L.in.oleum, using an inline IMUL fragment

Records are 5 little-endian uint32 per sector:
    temp_x, temp_y, temp_z, netpos, flags
"""

import struct
import sys

FIELDS = ("temp_x", "temp_y", "temp_z", "netpos", "flags")
REC = 20


def load(path):
    blob = open(path, "rb").read()
    if len(blob) % REC:
        raise SystemExit(f"{path}: {len(blob)} bytes is not a multiple of {REC}")
    return [struct.unpack_from("<5I", blob, i * REC) for i in range(len(blob) // REC)]


def main():
    sets = {name: load(f"{name}.bin") for name in ("oracle", "python", "lino")}

    sizes = {name: len(recs) for name, recs in sets.items()}
    if len(set(sizes.values())) != 1:
        print(f"SECTOR COUNT MISMATCH: {sizes}")
        return 2
    n = next(iter(sizes.values()))
    print(f"{n} sectors from each of C, Python and L.in.oleum\n")

    pairs = [("oracle", "python"), ("oracle", "lino"), ("python", "lino")]
    all_ok = True

    for a, b in pairs:
        bad = [i for i in range(n) if sets[a][i] != sets[b][i]]
        if bad:
            all_ok = False
            print(f"  {a:<7} vs {b:<7}  MISMATCH in {len(bad)}/{n} sectors")
            for i in bad[:4]:
                print(f"      sector {i}:")
                for f, va, vb in zip(FIELDS, sets[a][i], sets[b][i]):
                    flag = "  <-- differs" if va != vb else ""
                    print(f"        {f:<7} {a}={va:>11}  {b}={vb:>11}{flag}")
        else:
            print(f"  {a:<7} vs {b:<7}  identical on all {n} sectors")

    print()
    if all_ok:
        print("ALL THREE IMPLEMENTATIONS AGREE, BIT FOR BIT.")
        star = [r for r in sets["lino"] if r[4] == 0]
        print(f"  {len(star)}/{n} sectors produced a star position with no cutoff")
        print("  sample star coordinates (signed):")
        for r in sets["lino"][:5]:
            sx = [v - 0x100000000 if v & 0x80000000 else v for v in r[:3]]
            print(f"    x={sx[0]:>12}  y={sx[1]:>12}  z={sx[2]:>12}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
