"""Write work/starmap_vec.bin - the test vectors for work/starmap_kernel.txt.

The kernel under test does two things that nothing in L.in.oleum does for
you: a 96-bit signed product of three 32-bit coordinates, and the exact
conversion of an IEEE double to trunc(d * 1e15) as a 96-bit signed integer.
Both are hand-rolled limb arithmetic, so the vectors are chosen to hit the
places where limb arithmetic goes wrong rather than to look impressive:

  * the funnel shift.  x86 masks shift counts to 5 bits, so the `x << 32`
    that appears when (1075 - e) is a multiple of 32 is a NO-OP, not a zero.
    Vectors with (1075-e) mod 32 == 0 and == 31 pin both edges.
  * carry propagation.  Products whose limbs straddle 0x80000000 tell a
    signed compare apart from an unsigned one; a carry test written with
    the signed `<` passes on small values and fails exactly here.
  * the rejections.  Two catalogue records are unusable (WESTOS is -0.0,
    MDIR 17 is a byte-reversed NaN that reads as a denormal).  Both have a
    biased exponent of 0 and both would otherwise scale to N = 0, whose
    +/-1e10 window claims every small star in the galaxy.  The kernel must
    refuse them, and the referee checks that it refuses exactly these.
  * 0x80000000 as a coordinate, whose magnitude does not fit in 32 bits.

Each vector is 5 units: x, y, z, double_lo, double_hi.
"""

import random
import struct
import sys

STARMAP = r"C:\programmieren\noctis\niv-plus\data\STARMAP.BIN"
OUT = r"C:\programmieren\linoleum\work\starmap_vec.bin"

M32 = 0xFFFFFFFF


def catalogue():
    """(raw 8 bytes, value, name, tag) for every record, in file order."""
    blob = open(STARMAP, "rb").read()[4:]
    out = []
    for i in range(len(blob) // 32):
        r = blob[i * 32:(i + 1) * 32]
        out.append((r[0:8], struct.unpack_from("<d", r, 0)[0],
                    r[8:28].rstrip(b" ").decode("latin-1"), chr(r[29])))
    return out


def bits(raw8):
    lo, hi = struct.unpack("<II", raw8)
    return lo, hi


def dbl(x):
    return bits(struct.pack("<d", x))


def synth(e, mant52):
    """Build the double with biased exponent e and 52-bit mantissa field."""
    hi = ((e & 0x7FF) << 20) | ((mant52 >> 32) & 0xFFFFF)
    lo = mant52 & M32
    return lo, hi


def main():
    recs = catalogue()
    stars = [r for r in recs if r[3] == "S"]
    by_name = {}
    for raw, v, n, t in stars:
        by_name.setdefault(n, (raw, v))

    vecs = []          # (x, y, z, lo, hi, why)

    def add(x, y, z, lohi, why):
        vecs.append((x & M32, y & M32, z & M32, lohi[0], lohi[1], why))

    # --- the three anchor stars: the author's own constants ---------------
    anchors = [
        ("BALASTRACKONASTREYA", -18928, -29680, -67336),
        ("YLASTRAVENYA", -56784, -15693, -129542),
        ("FENIA", 4342128, -4559934, -807862),
    ]
    for name, x, y, z in anchors:
        raw, v = by_name.get(name, (struct.pack("<d", 0.0), 0.0))
        add(x, y, z, bits(raw), f"anchor {name}")

    # --- the extremes of the real catalogue -------------------------------
    usable = [(raw, v, n) for raw, v, n, t in stars
              if 0 < ((bits(raw)[1] >> 20) & 0x7FF) < 0x7FF]
    by_mag = sorted(usable, key=lambda r: abs(r[1]))
    for raw, v, n in by_mag[-7:]:
        add(1, 1, 1, bits(raw), f"largest |id| {n}")
    for raw, v, n in by_mag[:20]:
        add(1, 1, 1, bits(raw), f"smallest |id| {n}")

    # --- the two poison records, which must be REJECTED -------------------
    for raw, v, n, t in stars:
        e = (bits(raw)[1] >> 20) & 0x7FF
        if e == 0 or e == 0x7FF:
            add(3, 5, 7, bits(raw), f"poison {n}")

    # --- funnel-shift edges: (1075-e) mod 32 == 0 and == 31 ---------------
    # Take them from the file where they exist, and synthesise them too so
    # the coverage does not depend on what players happened to chart.
    want0 = {e for e in range(1, 1068) if (1075 - e) % 32 == 0}
    want31 = {e for e in range(1, 1068) if (1075 - e) % 32 == 31}
    got0 = got31 = 0
    for raw, v, n in usable:
        e = (bits(raw)[1] >> 20) & 0x7FF
        if e in want0 and got0 < 6:
            add(2, 3, 5, bits(raw), f"file (1075-e)%32==0 e={e} {n}")
            got0 += 1
        elif e in want31 and got31 < 6:
            add(2, 3, 5, bits(raw), f"file (1075-e)%32==31 e={e} {n}")
            got31 += 1
    rnd = random.Random(20260804)
    for e in sorted(want0)[::7] + sorted(want31)[::7]:
        for _ in range(2):
            add(1, 1, 1, synth(e, rnd.getrandbits(52)),
                f"synth e={e} k={(1075-e)}")

    # --- exponent boundary cases -----------------------------------------
    add(1, 1, 1, synth(1, 0), "e=1 denormal boundary (usable, k=1074 -> N=0)")
    add(1, 1, 1, synth(1067, (1 << 52) - 1), "e=1067 largest accepted")
    add(1, 1, 1, synth(1068, 0), "e=1068 must be REJECTED (would overflow)")
    add(1, 1, 1, synth(1069, 1 << 51), "e=1069 must be REJECTED")
    add(1, 1, 1, synth(0x7FF, 0), "+inf must be REJECTED")
    add(1, 1, 1, synth(0x7FF, 1 << 51), "NaN must be REJECTED")
    add(1, 1, 1, synth(0, 0), "+0.0 must be REJECTED")
    add(1, 1, 1, synth(0, 12345), "denormal must be REJECTED")
    # k exactly 103/104 - the boundary of the "N is certainly 0" shortcut
    for e in (1075 - 104, 1075 - 103, 1075 - 102, 1075 - 96, 1075 - 95):
        add(1, 1, 1, synth(e, (1 << 52) - 1), f"k boundary e={e} k={1075-e}")

    # --- coordinate edges -------------------------------------------------
    d1 = dbl(1.0)
    for v in (1, -1, 0x7FFFFFFF, -0x7FFFFFFF, 0):
        add(v, 1, 1, d1, f"x={v}")
        add(1, v, 1, d1, f"y={v}")
        add(1, 1, v, d1, f"z={v}")
    add(-0x80000000, 1, 1, d1, "x=0x80000000 must be REJECTED")
    add(1, -0x80000000, 1, d1, "y=0x80000000 must be REJECTED")
    add(1, 1, -0x80000000, d1, "z=0x80000000 must be REJECTED")
    add(0x7FFFFFFF, 0x7FFFFFFF, 0x7FFFFFFF, d1, "largest positive product")
    add(-0x7FFFFFFF, -0x7FFFFFFF, -0x7FFFFFFF, d1, "largest negative product")

    # all eight sign combinations, on values whose limbs straddle 0x80000000
    for sx in (1, -1):
        for sy in (1, -1):
            for sz in (1, -1):
                add(sx * 0x5A827999, sy * 0x6ED9EBA1, sz * 0x8F1BBCDC & M32
                    if sz > 0 else -(0x8F1BBCDC & 0x7FFFFFFF), d1,
                    f"signs {sx}{sy}{sz}")
    for sx in (1, -1):
        for sy in (1, -1):
            for sz in (1, -1):
                add(sx * 1518500249, sy * 1859775393, sz * 2027608667, d1,
                    f"signs2 {sx}{sy}{sz}")

    # --- bulk random ------------------------------------------------------
    cat_raws = [r[0] for r in usable]
    for _ in range(1500):
        x = rnd.randrange(-500_000_000, 500_000_001)
        y = rnd.randrange(-500_000_000, 500_000_001)
        z = rnd.randrange(-500_000_000, 500_000_001)
        add(x, y, z, bits(rnd.choice(cat_raws)), "random")

    with open(OUT, "wb") as fh:
        fh.write(struct.pack("<I", len(vecs)))
        for x, y, z, lo, hi, _ in vecs:
            fh.write(struct.pack("<5I", x, y, z, lo, hi))

    print(f"wrote {OUT}: {len(vecs)} vectors, {4 + 20*len(vecs)} bytes")
    kinds = {}
    for v in vecs:
        kinds[v[5].split()[0]] = kinds.get(v[5].split()[0], 0) + 1
    print("  by kind:", kinds)
    return 0


if __name__ == "__main__":
    sys.exit(main())
