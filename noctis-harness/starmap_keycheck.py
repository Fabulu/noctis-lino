"""Referee work/starmap_keys.bin - the L.in.oleum decode of the real catalogue.

Every one of the 37,578 records is decoded on both sides and required to
agree exactly: the 96-bit N, the rejection code, and the record tail field
that carries the type tag. The Python side reads the bytes independently
and computes N with Fraction, so no arithmetic is shared with the L.in.oleum
programme.

This gate proves the file reader and the decoder on real data. It says
nothing at all about the galaxy generator.
"""

import struct
import sys
from fractions import Fraction

WORK = r"C:\programmieren\linoleum\work"
STARMAP = WORK + r"\STARMAP.BIN"
KEYS = WORK + r"\starmap_keys.bin"

M32 = 0xFFFFFFFF
M96 = (1 << 96) - 1


def limbs96(v):
    v &= M96
    return v & M32, (v >> 32) & M32, (v >> 64) & M32


def expect_N(lo, hi):
    e = (hi >> 20) & 0x7FF
    if e == 0:
        return (0, 0, 0), 1
    if e == 0x7FF:
        return (0, 0, 0), 2
    if e >= 1068:
        return (0, 0, 0), 3
    d = struct.unpack("<d", struct.pack("<II", lo, hi))[0]
    return limbs96(int(Fraction(d) * 10 ** 15)), 0


def main():
    blob = open(STARMAP, "rb").read()
    keys = open(KEYS, "rb").read()

    nrec = (len(blob) - 4) // 32
    want_bytes = 4 * (4 + 5 * nrec)
    if len(keys) != want_bytes:
        print(f"FAIL {KEYS} is {len(keys)} bytes, expected {want_bytes}")
        return 2

    hdr = struct.unpack_from("<4I", keys, 0)
    print(f"header from lino  : nrec={hdr[0]} nstar={hdr[1]} "
          f"bad_byte28={hdr[2]} tombstones={hdr[3]}")

    body = blob[4:]
    nstar = sum(1 for i in range(nrec) if body[i * 32 + 29] == ord("S"))
    nbad28 = sum(1 for i in range(nrec) if body[i * 32 + 28] != 0x20)
    ntomb = sum(1 for i in range(nrec) if body[i * 32:i * 32 + 8] == b"Removed:")
    print(f"header from python: nrec={nrec} nstar={nstar} "
          f"bad_byte28={nbad28} tombstones={ntomb}")
    if hdr != (nrec, nstar, nbad28, ntomb):
        print("FAIL header disagreement")
        return 1

    badN = badR = badT = 0
    rejected = []
    first = []
    for i in range(nrec):
        r = body[i * 32:(i + 1) * 32]
        lo, hi = struct.unpack_from("<II", r, 0)
        want_tail = struct.unpack_from("<I", r, 28)[0]

        tail, rej, n0, n1, n2 = struct.unpack_from("<5I", keys, 16 + 20 * i)
        wN, wR = expect_N(lo, hi)

        if tail != want_tail:
            badT += 1
            if len(first) < 12:
                first.append(f"  [{i}] tail lino {tail:08x} want {want_tail:08x}")
        if rej != wR:
            badR += 1
            if len(first) < 12:
                first.append(f"  [{i}] rej lino {rej} want {wR}")
        elif (n0, n1, n2) != wN:
            badN += 1
            if len(first) < 12:
                e = (hi >> 20) & 0x7FF
                first.append(f"  [{i}] N lino {(n0,n1,n2)} want {wN} "
                             f"e={e} k={1075-e} r={(1075-e)%32}")
        if wR:
            name = r[8:28].rstrip(b" ").decode("latin-1")
            rejected.append((i, name, chr(r[29]), wR, r[0:8].hex()))

    print(f"records compared  : {nrec}")
    print(f"  tail mismatches : {badT}")
    print(f"  rej  mismatches : {badR}")
    print(f"  N    mismatches : {badN}")
    print(f"unusable records  : {len(rejected)}")
    for i, name, tag, code, raw in rejected:
        print(f"    #{i:<6} {name:<12} '{tag}' rej={code} raw={raw}")

    star_rej = sum(1 for i, n, t, c, r in rejected if t == "S")
    print(f"star records usable as catalogue keys: {nstar - star_rej} "
          f"of {nstar}  ({star_rej} excluded)")

    if first:
        print("first disagreements:")
        for line in first:
            print(line)
        print("KEYS FAIL")
        return 1
    print("KEYS PASS - lino and Python agree on all 37578 records, bit for bit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
