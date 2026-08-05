#!/usr/bin/env python3
"""fbpalref.py - a second implementation of the pinned palette state.

Written from NOCTIS-0.CPP:166 (range8088), :179 (tavola_colori) and :1151
(shade) in Python, with binary32 narrowing done explicitly through struct so
that a C float variable is modelled as a C float variable and not as a double.

This is NOT the project's independent reference - that is implementer 2's
fb_ref.c, written by a different agent.  This exists to catch implementer 1's
own transcription errors before the two sides meet, and it is reported as
exactly that: a self-check, not a Tier-2 grade.

Usage: python fbpalref.py fbmain.bin
"""
import struct
import sys


def f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


class Pal:
    def __init__(self):
        self.pal6 = [0] * 768
        self.cur = [0] * 768
        self.lut = [0] * 256
        self.range8088 = [k for k in range(64) for _ in range(3)]

    def upload(self, ncolours):
        # tavola_colori's asm tail outs from component 0 up to (first+n)*3.
        for i in range(3 * ncolours):
            self.cur[i] = self.pal6[i]
        for c in range(ncolours):
            self.lut[c] = (((self.cur[3 * c] & 63) * 4) << 16) \
                        | (((self.cur[3 * c + 1] & 63) * 4) << 8) \
                        | ((self.cur[3 * c + 2] & 63) * 4)

    def tavola(self, src, first, n, fr, fg, fb):
        # filtro_* are signed char; temp is a 16-bit unsigned, so the product
        # is taken mod 65536 and the divide is unsigned.
        f = []
        for v in (fr, fg, fb):
            v &= 0xFF
            if v & 0x80:
                v -= 0x100
            f.append(v & 0xFFFF)
        if src is not None:
            for i in range(n * 3):
                self.pal6[first * 3 + i] = src[i] & 0xFF
        c = first * 3
        while c < first * 3 + n * 3:
            for j in range(3):
                t = self.pal6[c] & 0xFF
                t = (t * f[j]) & 0xFFFF
                t //= 63
                if t > 63:
                    t = 63
                self.pal6[c] = t
                c += 1
        self.upload(first + n)

    def shade(self, first, n, s, e, near=False):
        k = f32(1.0 / f32(n))
        d = [f32((f32(e[i]) - f32(s[i])) * k) for i in range(3)]
        cur = [f32(s[i]) for i in range(3)]
        fc = first * 3
        for _ in range(n):
            for i in range(3):
                v = cur[i]
                if 0 <= v < 64:
                    # a C cast chops; lino's =, would round to nearest even.
                    self.pal6[fc + i] = _rne(v) if near else int(v)
                else:
                    self.pal6[fc + i] = 63 if v > 0 else 0
            for i in range(3):
                cur[i] = f32(cur[i] + d[i])
            fc += 3


def _rne(v):
    import decimal
    f = float(v)
    n = int(f)
    r = f - n
    if r > 0.5:
        n += 1
    elif r == 0.5 and (n & 1):
        n += 1
    return min(63, n)


def pinned(near=False):
    p = Pal()
    sh = lambda *a: p.shade(*a, near=near)
    p.tavola(p.range8088, 0, 64, 16, 32, 63)                      # S1
    sh(192, 16, (0, 0, 0), (4, 2, 1))                        # S2
    sh(208, 16, (4, 2, 1), (24, 18, 12))                     # S3
    sh(224, 16, (24, 18, 12), (60, 55, 50))                  # S4
    sh(240, 16, (60, 55, 50), (64, 64, 64))                  # S5
    p.tavola(None, 192, 64, 50, 50, 50)                           # S6 self
    sh(0, 64, (0, 0, 0), (63, 63, 63))                       # S7
    sh(64, 24, (0, 0, 0), (24, 31, 40))                      # S8
    sh(88, 16, (24, 31, 40), (48, 52, 56))                   # S9
    sh(104, 24, (48, 52, 56), (63, 63, 63))                  # S10
    p.tavola(None, 64, 64, 60, 55, 50)                            # S11 self
    sh(128, 64, (0, 0, 0), (63, 63, 63))                     # S12
    return p


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "fbmain.bin"
    data = open(path, "rb").read()
    recs, off = [], 0
    while off + 64 <= len(data):
        h = struct.unpack_from("<16I", data, off)
        n = h[5]
        recs.append((h[2], struct.unpack_from("<%dI" % n, data, off + 64)))
        off += 64 + 4 * n
    pal6 = [p for k, p in recs if k == 2][0]
    cur = [p for k, p in recs if k == 2][1]
    lut = [p for k, p in recs if k == 3][0]

    m = pinned()
    bad6 = [i for i in range(768) if m.pal6[i] != pal6[i]]
    badc = [i for i in range(768) if m.cur[i] != cur[i]]
    badl = [i for i in range(256) if m.lut[i] != lut[i]]
    print("pal6     components differing: %d" % len(bad6))
    print("curpal6  components differing: %d" % len(badc))
    print("LUT      entries    differing: %d" % len(badl))
    for nm, bad, mine, theirs in (("pal6", bad6, m.pal6, pal6),
                                  ("curpal6", badc, m.cur, cur),
                                  ("LUT", badl, m.lut, lut)):
        for i in bad[:8]:
            print("   %s[%d]: model %d, lino %d" % (nm, i, mine[i], theirs[i]))
    ok = not (bad6 or badc or badl)
    print("AGREE" if ok else "DISAGREE")
    # the chop is doing work: where does round-to-nearest first disagree?
    mn = pinned(near=True)
    d = [i for i in range(768) if mn.pal6[i] != m.pal6[i]]
    print("chop vs round-to-nearest: %d of 768 components differ, first at "
          "%d (chop %d, near %d)" % (len(d), d[0], m.pal6[d[0]], mn.pal6[d[0]]))
    try:
        b3 = open("fbbreak3.bin", "rb").read()
    except IOError:
        return 0 if ok else 1
    recs3, o = [], 0
    while o + 64 <= len(b3):
        h = struct.unpack_from("<16I", b3, o)
        recs3.append((h[2], struct.unpack_from("<%dI" % h[5], b3, o + 64)))
        o += 64 + 4 * h[5]
    p3 = [q for k, q in recs3 if k == 2][0]
    bad3 = [i for i in range(768) if mn.pal6[i] != p3[i]]
    print("fbbreak3 (FToIntNear) vs the round-to-nearest model: %d differing"
          % len(bad3))
    if bad3[:4]:
        print("   first:", [(i, mn.pal6[i], p3[i]) for i in bad3[:4]])
    return 0 if (ok and not bad3) else 1


if __name__ == "__main__":
    sys.exit(main())
