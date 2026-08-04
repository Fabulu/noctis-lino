"""Independent Python implementation of Noctis IV's galaxy hash.

Written against the algorithm, not transcribed from oracle.c, so that a
misreading of the original would have to occur twice, identically, to slip
through. Python's arbitrary-precision integers mean the 64-bit product is
exact by construction - there is no hardware behaviour to get wrong here,
which is exactly what makes it a useful referee.

Same conventions as oracle.c: all three coordinates computed
unconditionally, cutoffs reported as flags, rarity gate omitted.
"""

import struct
import sys

CUTOFF = 50000
SECTOR = 100000
KMIN, KMAX = -3, 3
M32 = 0xFFFFFFFF


def signed32(v):
    """Reinterpret the low 32 bits of v as a signed two's-complement value."""
    v &= M32
    return v - 0x100000000 if v & 0x80000000 else v


def fold_mul(a, b):
    """Signed 32x32 -> 64 multiply with the high half folded into the low.

    This is the original's `imul` followed by `edx += eax`. The signedness
    matters: sector coordinates go negative, and an unsigned product would
    give a different high word and therefore a different galaxy.
    """
    product = signed32(a) * signed32(b)
    lo = product & M32
    hi = (product >> 32) & M32
    return (hi + lo) & M32


def hash_sector(sect_x, sect_y, sect_z):
    sum_xz = (sect_x + sect_z) & M32
    flags = 0

    temp_x = ((sum_xz & 0x0001FFFF) + sect_x) & M32
    if temp_x == CUTOFF:
        flags |= 1
    temp_x = (temp_x - CUTOFF) & M32

    accum = fold_mul(temp_x, sum_xz)

    idk = (sum_xz + accum) & M32

    temp_y = ((accum & 0x0001FFFF) + sect_y) & M32
    if temp_y == CUTOFF:
        flags |= 2
    temp_y = (temp_y - CUTOFF) & M32

    accum = fold_mul(temp_y, idk)

    temp_z = ((accum & 0x0001FFFF) + sect_z) & M32
    if temp_z == CUTOFF:
        flags |= 4
    temp_z = (temp_z - CUTOFF) & M32

    netpos = (temp_x + temp_y + temp_z) & M32
    return temp_x, temp_y, temp_z, netpos, flags


def sweep():
    for kx in range(KMIN, KMAX + 1):
        for ky in range(KMIN, KMAX + 1):
            for kz in range(KMIN, KMAX + 1):
                yield hash_sector(kx * SECTOR, ky * SECTOR, kz * SECTOR)


def main():
    records = list(sweep())

    with open("python.bin", "wb") as fh:
        for rec in records:
            fh.write(struct.pack("<5I", *rec))
    print(f"python.bin: {len(records)} sectors, {len(records) * 20} bytes")

    # Referee against the C oracle if it has been run.
    try:
        blob = open("oracle.bin", "rb").read()
    except FileNotFoundError:
        print("oracle.bin not present - skipping comparison")
        return 0

    if len(blob) != len(records) * 20:
        print(f"SIZE MISMATCH: oracle.bin {len(blob)} vs expected {len(records) * 20}")
        return 2

    c_records = [struct.unpack_from("<5I", blob, i * 20) for i in range(len(records))]

    bad = [i for i, (a, b) in enumerate(zip(records, c_records)) if a != b]
    if bad:
        print(f"MISMATCH in {len(bad)}/{len(records)} sectors. First 5:")
        for i in bad[:5]:
            print(f"  sector {i}:  python {records[i]}")
            print(f"              C      {c_records[i]}")
        return 1

    print(f"C and Python agree on all {len(records)} sectors")

    stars = sum(1 for r in records if r[4] == 0)
    print(f"  {stars} sectors with no cutoff hit, {len(records) - stars} with")
    return 0


if __name__ == "__main__":
    sys.exit(main())
