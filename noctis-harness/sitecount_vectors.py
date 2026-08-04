# Generate the operand table that all three 64-bit-multiply backends are run
# against, plus the exact answers computed in Python arbitrary precision.
#
# The ground truth here is Python's bignum, not any x86 behaviour: "what is a
# 32x32 -> 64 product" is a question about integers, and answering it with the
# same hardware instruction under test would be circular.
#
# The table MUST contain pairs where exactly one operand has bit 31 set. Those
# are the only ones on which the signed and unsigned high halves differ, and
# without them a backend that calls MUL where it should call IMUL passes
# everything.
#
#   work/sitecount-vec.bin   [N][x0][y0][x1][y1]...   32-bit little-endian
#   answers returned in memory by expected()

import os
import random
import struct
import sys

WORK = os.path.join(r"C:\programmieren\linoleum", "work")
VEC = os.path.join(WORK, "sitecount-vec.bin")

M32 = 0xFFFFFFFF

# The nine adversarial pairs already used by sitecount_verify.py CLAIM C.
ADVERSARIAL = [
    (0, 0), (1, 1), (M32, M32), (0x80000000, 0x80000000),
    (0x7FFFFFFF, 0x7FFFFFFF), (0x80000000, 1), (M32, 1),
    (0xFFFF0000, 0x0000FFFF), (0x12345678, 0x9ABCDEF0),
]

# Every combination of the seven interesting magnitudes: zero, one, limb
# boundary either side, both signed extremes, all-ones.
CORNERS = [0, 1, 0xFFFF, 0x10000, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF]

NRANDOM = 4000
SEED = 20260804


def vectors():
    v = list(ADVERSARIAL)
    for x in CORNERS:
        for y in CORNERS:
            v.append((x, y))
    rng = random.Random(SEED)
    for _ in range(NRANDOM):
        v.append((rng.getrandbits(32), rng.getrandbits(32)))
    return v


def signed(v):
    return v - 0x100000000 if v & 0x80000000 else v


def expected(pairs):
    """Exact (lo_u, hi_u, lo_s, hi_s) per pair, in Python arbitrary precision."""
    out = []
    for x, y in pairs:
        pu = x * y
        ps = (signed(x) * signed(y)) & 0xFFFFFFFFFFFFFFFF
        out.append((pu & M32, (pu >> 32) & M32, ps & M32, (ps >> 32) & M32))
    return out


def write(path=VEC):
    pairs = vectors()
    blob = struct.pack("<I", len(pairs))
    for x, y in pairs:
        blob += struct.pack("<II", x, y)
    with open(path, "wb") as f:
        f.write(blob)
    return pairs


def sign_sensitive(pairs):
    """Pairs on which signed and unsigned high halves differ."""
    n = 0
    for x, y in pairs:
        pu = (x * y) >> 32
        ps = ((signed(x) * signed(y)) & 0xFFFFFFFFFFFFFFFF) >> 32
        if pu != ps:
            n += 1
    return n


if __name__ == "__main__":
    pairs = write()
    print("wrote %s: %d pairs, %d bytes" % (VEC, len(pairs), os.path.getsize(VEC)))
    print("  adversarial=%d corners=%d random=%d"
          % (len(ADVERSARIAL), len(CORNERS) ** 2, NRANDOM))
    ss = sign_sensitive(pairs)
    print("  sign-sensitive pairs (signed hi != unsigned hi) = %d" % ss)
    if ss == 0:
        print("  FAIL: table cannot tell MUL from IMUL")
        sys.exit(1)
