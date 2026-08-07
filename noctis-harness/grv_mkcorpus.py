r"""grv_mkcorpus.py - generate the pinned renderer corpus for Wave 7b.

Two opcodes, one file:
  op 1 (hpoint):    1 px pz s1 s2 s3 s4
  op 2 (fragment):  2 x z posx posz s1 s2 s3 s4 shd ssh seed branch
    posx/posz are the SIGNED DECIMAL of pos_x/pos_z's binary32 BIT PATTERN
    (the convention all three sides share so no decimal float parser is).

DETERMINISTIC.  Covers:
  hpoint: the icx+icz = 16383/16384/16385 boundary, both bilinear triangles,
         m200 indexing across the grid, surf-byte corners.
  fragment: tiles at several depths around the walker (depth 0..~10), the
         exact-required depth chop (sqrt + (long)>>14), both c1 branches
         (sh_delta slope and diffuse fast_random), surf-byte corners,
         positive/negative sh_delta, and the depth>64 far cull.

Writes noctis-harness/grv-corpus.txt.  Re-run freely; byte-stable.
"""

import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))


def bits(f):
    u = struct.unpack("<I", struct.pack("<f", float(f)))[0]
    return u - 0x100000000 if u & 0x80000000 else u


def hp_rows():
    out = []
    def tile(px14, pz14, sub=0, s=None):
        if s is None:
            s = (0, 0, 0, 0)
        px = (px14 << 14) | (sub & 16383)
        pz = (pz14 << 14) | (sub & 16383)
        out.append((1, px, pz, s[0], s[1], s[2], s[3]))
    for sub in (0, 1, 8191, 8192, 8193, 16383):
        tile(10, 10, sub, (30, 60, 90, 0))
    for (sx, sz) in [(16383, 0), (0, 16383), (16384, 0), (0, 16384),
                     (100, 16284), (16284, 100)]:
        out.append((1, (10 << 14) | sx, (10 << 14) | sz, 200, 10, 120, 240))
    for s in [(0, 0, 0, 0), (255, 255, 255, 255), (128, 128, 128, 128),
              (1, 255, 1, 255), (255, 1, 255, 1), (127, 128, 129, 200)]:
        tile(50, 77, 4096, s)
        tile(51, 77, 12288, s)
    for (c, r) in [(0, 0), (1, 1), (99, 99), (198, 198), (197, 0),
                   (0, 197), (198, 1), (123, 45)]:
        tile(c, r, 5000, (80, 100, 120, 90))
    for r in range(0, 50):
        s1 = (r * 7) & 255
        out.append((1, (13 << 14) | 7000, (r << 14) | 7000,
                    s1, (s1 * 3) & 255, (s1 ^ 0x5A) & 255, (255 - s1) & 255))
    return out


def frag_rows():
    """fragment cases.  Walker stands at tile (100,100), sub-position 8192."""
    out = []
    ipfx = ipfz = 100
    pos = float((ipfx << 14) + 8192)      # walker X = Z = 1646592.0
    pb = bits(pos)
    # 1. tiles at depths 0..9 around the walker, varied heights, diffuse.
    for (dx, dz) in [(0, 0), (1, 0), (0, 1), (1, 1), (-1, 0), (0, -1),
                     (2, 0), (0, 2), (2, 2), (-2, -2), (3, 1), (1, 3),
                     (5, 0), (0, 5), (5, 5), (-3, 4), (4, -3), (7, 7),
                     (9, 0), (0, 9), (6, 6), (-7, 2)]:
        x = ipfx + dx
        z = ipfz + dz
        s1 = (dx * 13 + 40) & 255
        s2 = (dz * 17 + 50) & 255
        s3 = (dx * dz + 120) & 255
        s4 = (s1 ^ s2) & 255
        out.append((2, x, z, pb, pb, s1, s2, s3, s4,
                    1, (s4 + 1) & 255, 1234567, 0))
    # 2. same tiles, sh_delta slope branch (positive and negative delta).
    for (dx, dz, shd) in [(1, 0, 1), (0, 1, 200), (2, 2, -1), (-2, -2, -200),
                          (4, 0, 1), (0, 4, 200), (3, 3, -1), (5, 5, 1)]:
        x = ipfx + dx
        z = ipfz + dz
        s1 = (dx * 19 + 30) & 255
        s2 = (dz * 23 + 60) & 255
        s3 = 200
        s4 = 100
        out.append((2, x, z, pb, pb, s1, s2, s3, s4,
                    shd, (s1 + 17) & 255, 9876543, 1))
    # 3. far tiles to drive depth toward the >64 cull (depth carries it).
    for (dx, dz) in [(20, 0), (0, 20), (30, 30), (40, 0), (50, 10), (63, 63),
                     (64, 0), (65, 5)]:
        out.append((2, ipfx + dx, ipfz + dz, pb, pb,
                    80, 90, 100, 110, 1, 85, 5555555, 0))
    # 4. diffuse branch with several seeds (exercises the LCG fold).
    for seed in [0, 1, 42, 100000, 2147483647, -1, 7777, 123123]:
        out.append((2, 102, 102, pb, pb, 64, 128, 192, 200, 1, 70, seed, 0))
    # 5. DEPTH-BOUNDARY cases: walker nudged 0.4 above the tile centre so
    #    hpdep lands at k*16384 - 0.4 (just UNDER the k-th boundary).  There
    #    chop(hpdep) = k*16384-1 but near(hpdep) = k*16384, so depth (>>14)
    #    flips by one - the only place the EXACT-REQUIRED depth chop is
    #    observable.  Without these the chop is invisible to >>14.
    pb_b = bits(float((ipfx << 14) + 8192) + 0.4)          # walker X = 1646592.4
    pb_z = bits(float((ipfz << 14) + 8192))                # walker Z = 1646592.0
    for k in (1, 2, 3, 4, 5):                              # tiles at distance k
        out.append((2, ipfx + k, ipfz, pb_b, pb_z,
                    70, 80, 90, 100, 1, 75, 24680, 0))
    return out


def p_forward_rows():
    """opcode 5: delta, opt_tsinbeta, opt_tcosbeta, opt_tcosalfa, pos_x, pos_z
    as signed-decimal binary32 bit patterns."""
    import math
    def b(f):
        u = struct.unpack("<I", struct.pack("<f", float(f)))[0]
        return u - 0x100000000 if u & 0x80000000 else u
    out = []
    for delta in (8192.0, 16384.0, 50000.5, -8192.0):
        for (beta, alfa) in [(0, 0), (90, 0), (45, 0), (30, 30), (60, 10), (180, 0)]:
            sb = math.sin(math.radians(beta))
            cb = math.cos(math.radians(beta))
            ca = math.cos(math.radians(alfa))
            for px in (1646592.0, 1646592.5, -1000000.0):
                out.append((5, b(delta), b(sb), b(cb), b(ca), b(px), b(px)))
    return out


def cav_rows():
    """opcode 6: alfa beta dpp -- change_angle_of_view (binary32 bit patterns)."""
    import math
    def b(f):
        u = struct.unpack("<I", struct.pack("<f", float(f)))[0]
        return u - 0x100000000 if u & 0x80000000 else u
    out = []
    # avoid EXACT multiples of 90: there cos/sin's true value is 0 but the x87
    # fsin/fcos yields a tiny nonzero whose float32 store is precision-sensitive
    # and the spec's libm sin/cos cannot match it.  89/91/179/etc test the
    # near-boundary without hitting the exact-zero point.  lino==cref (both
    # x87) holds at the exact boundaries too; only the spec witness is bounded.
    for alfa in (0, 1, 10, 30, 45, 60, 89, 91, 135, 179, 181, 269, 271, -30, -89, 359, 400, 0.5, 12.25):
        for beta in (0, 45, 89, 91, 179, -45, 123.5):
            for dpp in (210.0, 128.0, 200.0):
                out.append((6, b(alfa), b(beta), b(dpp)))
    return out


def main():
    path = os.path.join(HERE, "grv-corpus.txt")
    with open(path, "w", newline="\n") as fh:
        fh.write("# grv-corpus.txt - pinned renderer cases (Wave 7b).\n")
        fh.write("# op 1: px pz s1 s2 s3 s4                 (hpoint)\n")
        fh.write("# op 2: x z posx posz s1 s2 s3 s4 shd ssh seed branch\n")
        fh.write("#       (posx/posz = signed decimal of the binary32 bits)\n")
        fh.write("# generated by grv_mkcorpus.py - byte-stable.\n")
        for row in hp_rows() + frag_rows() + p_forward_rows() + cav_rows():
            fh.write(" ".join(str(v) for v in row) + "\n")
    print("wrote %s (%d hpoint + %d fragment + %d p_forward)"
          % (path, len(hp_rows()), len(frag_rows()), len(p_forward_rows())))


if __name__ == "__main__":
    main()
