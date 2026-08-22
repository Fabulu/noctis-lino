#!/usr/bin/env python3
"""fpvecgen.py - write fpvec.bin for one schedule id.

    python fpvecgen.py <schedule-id> [out.bin]

Format is the one frozen in the Wave 3 architecture note.  All units are
little-endian, which is not an assumption: fpstar's slot 0/1 sentinel puts
fld1 through fstp qword and reads back 00000000 3FF00000, so the byte order
of a double assembled from two units is measured, not hoped for.

    unit 0    magic 'FPVC'  46505643h
    unit 1    format version 1
    unit 2    NCASE
    unit 3    CASEU = 16
    unit 4    schedule id
    unit 5    control word to load
    unit 6,7  reserved zero
    unit 8..  NCASE cases of 16 units:
        +0..+7   four f64, each LOW unit then HIGH unit
        +8..+11  four int32
        +12      live mask, bits 0-3 f64 slots, bits 4-7 int slots
        +13..15  reserved zero

VECTOR CHOICE.  Not random noise.  The interesting inputs for this engine
are the ones where a 64-bit intermediate and a 53-bit intermediate disagree,
which means operands whose exact result lands very near a binary64 rounding
boundary.  So the set mixes: exact small integers, values built to make
a+b and a*b fall a hair either side of a tie, the actual magnitudes Noctis
uses (1e5-ish coordinates, 3.8e6 ship positions, angles in radians), and
values chosen to exercise the int16 wrap that star classes 1, 3, 4 and 9
take as their normal path.
"""
import math
import struct
import sys
import random

NCASE = 4096
CASEU = 16
MAGIC = 0x46505643


def d2u(x):
    b = struct.unpack('<Q', struct.pack('<d', x))[0]
    return b & 0xFFFFFFFF, (b >> 32) & 0xFFFFFFFF


def f32(x):
    return struct.unpack('<f', struct.pack('<f', x))[0]


def i2u(x):
    return x & 0xFFFFFFFF


def vectors(sched):
    rnd = random.Random(0x4E4F4354)     # 'NOCT'
    out = []

    def add(fa=0.0, fb=1.0, fc=1.0, fd=1.0, j0=0, j1=0, j2=0, j3=0, mask=0xFF):
        out.append((fa, fb, fc, fd, j0, j1, j2, j3, mask))

    # ---- 1. exact small integers: nothing may round, anywhere
    for i in range(-32, 33):
        add(float(i), float(i + 3 or 1), float(i * 2 + 1), 2.0,
            i, i + 3, i * 2 + 1, 7)

    # ---- 2. the magnitudes Noctis actually uses
    #        star coordinates, ship positions, the 1e5 divisor
    for _ in range(400):
        x = rnd.randint(-6000000, 6000000)
        y = rnd.randint(-6000000, 6000000)
        z = rnd.randint(-6000000, 6000000)
        add(x / 1e5, y / 1e5, z / 1e5, 100000.0, x, y, z, 100000)
    for _ in range(200):
        # dzat_x/y/z live around 3.8e6, where a binary32 ulp is 0.25 -
        # these are the F32Narrow vectors
        v = rnd.uniform(-4.2e6, 4.2e6)
        add(v, v + rnd.uniform(-0.5, 0.5), 0.25, 3.8e6,
            int(v) & 0x7FFFFFFF, 4, 0, 1)

    # ---- 3. near-tie constructions: exact result a hair from a boundary
    for _ in range(600):
        e = rnd.randint(-40, 40)
        m = rnd.getrandbits(52) | (1 << 52)
        a = m * 2.0 ** (e - 52)
        # b chosen so a+b needs a rounding decision at bit 54..64
        k = rnd.randint(53, 66)
        b = (rnd.getrandbits(11) + 1) * 2.0 ** (e - k)
        add(a, b, a * (1 + 2.0 ** -30), b if b else 1.0,
            rnd.randint(-70000, 70000), rnd.randint(1, 99999),
            rnd.randint(-99999, 99999), rnd.randint(1, 1000))
    for _ in range(600):
        # products whose exact 106-bit result sits near a 53-bit boundary
        a = (rnd.getrandbits(27) | (1 << 26)) * 2.0 ** rnd.randint(-30, 30)
        b = (rnd.getrandbits(27) | (1 << 26)) * 2.0 ** rnd.randint(-30, 30)
        add(a, b, a / b if b else 1.0, a * b,
            rnd.randint(-2000000000, 2000000000), rnd.randint(1, 1 << 20),
            rnd.randint(-32768, 32767), rnd.randint(1, 3))

    # ---- 4. the int16 wrap.  Star classes 1, 3, 4 and 9 overflow the
    #        16-bit int by up to 6.7x as the NORMAL path, so the wrap has
    #        to be exercised well past the boundary in both directions.
    for _ in range(500):
        v = rnd.uniform(-250000.0, 250000.0)
        add(v, v + 0.5, -v, 32768.0,
            int(v), 32767, -32768, 65536)
    for k in (32766, 32767, 32768, 32769, -32767, -32768, -32769, 65535,
              65536, 65537, 131072, 219999, -219999):
        for frac in (0.0, 0.5, -0.5, 0.4999999999, 0.5000000001):
            add(k + frac, 0.5, float(k), 1.0, k, k, k, 1)

    # ---- 5. angles, for fsin / fcos / fpatan
    for _ in range(400):
        t = rnd.uniform(-7.0, 7.0)
        add(t, rnd.uniform(-7.0, 7.0), abs(t) + 0.001, 1.0,
            int(t * 1000), 180, 360, 1)

    # The portable transcendental contract has a denser, schedule-specific
    # tail.  It includes the signed axes, exact neighboring binary64 values at
    # quadrant boundaries, and the accumulated angles used by production.  It
    # also reaches the complete x87-supported reduction interval: those large
    # cases intentionally grade mathematical range reduction rather than the
    # x87 instruction's documented 66-bit approximation of pi.
    if sched in (8, 9, 10):
        min_subnormal = math.ldexp(1.0, -1074)
        min_normal = math.ldexp(1.0, -1022)
        max_subnormal = math.nextafter(min_normal, 0.0)
        for value in (min_subnormal, -min_subnormal,
                      max_subnormal, -max_subnormal,
                      min_normal, -min_normal):
            add(value, 1.0)
        if sched == 10:
            add(min_subnormal, 2.0)
            add(-min_subnormal, 2.0)
            add(3.0 * min_subnormal, 2.0)
            add(-3.0 * min_subnormal, 2.0)

        for y in (0.0, -0.0, 1.0, -1.0):
            for x in (0.0, -0.0, 1.0, -1.0):
                add(y, x)

        for step, radius in ((math.pi / 2.0, 16), (math.pi, 8)):
            for k in range(-radius, radius + 1):
                center = k * step
                add(math.nextafter(center, -math.inf), 1.0)
                add(center, -1.0)
                add(math.nextafter(center, math.inf), 1.0)

        angle = 0.0
        degree_step = math.pi / 180.0
        for degree in range(361):
            if degree % 6 == 0:
                add(angle, -angle if angle else -0.0)
            angle += degree_step

        angle32 = f32(0.0)
        capsule_step = f32(0.025)
        for tick in range(253):
            if tick % 8 == 0:
                add(float(angle32), -float(angle32) if angle32 else -0.0)
            angle32 = f32(angle32 + capsule_step)

        for angle in (
                -1310.0, -1304.0, -168.0, -2.0 * math.pi, -math.pi,
                -math.pi / 4.0, math.pi / 4.0, math.pi, 2.0 * math.pi,
                168.0, 1304.0, 1310.0):
            add(angle, math.nextafter(angle, math.inf) or 1.0)

        if sched == 10:
            for y, x in ((1e-300, 1e300), (-1e-300, 1e300),
                         (1e300, 1e-300), (-1e300, 1e-300),
                         (1e-300, -1e300), (-1e-300, -1e300),
                         (1e300, -1e-300), (-1e300, -1e-300)):
                add(y, x)

        for exponent in (20, 30, 40, 50, 57, 60, 61, 62):
            magnitude = math.nextafter(2.0 ** exponent, 0.0)
            add(magnitude, -magnitude)
            add(-magnitude, magnitude)

        if sched in (8, 9):
            limit = 2.0 ** 63
            for magnitude in (
                    2.0 ** 62,
                    math.nextafter(2.0 ** 62, math.inf),
                    1.5 * (2.0 ** 62),
                    math.nextafter(limit, 0.0),
                    limit,
                    math.nextafter(limit, math.inf)):
                add(magnitude, -magnitude)
                add(-magnitude, magnitude)

    # ---- 6. exact halves and quarters, where round-nearest-EVEN and
    #         round-half-away differ and a naive converter shows itself
    for k in range(-64, 65):
        for frac in (0.5, -0.5, 0.25, 0.75):
            add(k + frac, 0.5, float(k), 2.0, k, 2, 4, 8)

    # ---- 7. sqrt inputs, including perfect squares
    for _ in range(300):
        v = rnd.uniform(0.0, 1e7)
        add(v, rnd.uniform(0.1, 1e5), v * v, 1.0,
            int(v), 3, 5, 7)
    for k in range(1, 121):
        add(float(k * k), float(k), 1.0 / k, 1.0, k * k, k, 1, 1)

    # pad or trim to exactly NCASE
    while len(out) < NCASE:
        a = rnd.uniform(-1e6, 1e6)
        b = rnd.uniform(-1e6, 1e6)
        add(a, b if b else 1.0, a - b, a + b,
            rnd.randint(-1 << 30, 1 << 30), rnd.randint(1, 1 << 24),
            rnd.randint(-40000, 40000), rnd.randint(1, 9))
    return out[:NCASE]


def main():
    sched = int(sys.argv[1])
    dest = sys.argv[2] if len(sys.argv) > 2 else 'fpvec.bin'
    cases = vectors(sched)
    u = [MAGIC, 1, NCASE, CASEU, sched, 0x133F, 0, 0]
    for (fa, fb, fc, fd, j0, j1, j2, j3, mask) in cases:
        for v in (fa, fb, fc, fd):
            lo, hi = d2u(v)
            u.append(lo)
            u.append(hi)
        for v in (j0, j1, j2, j3):
            u.append(i2u(v))
        u.append(mask)
        u.append(0)
        u.append(0)
        u.append(0)
    open(dest, 'wb').write(struct.pack('<%dI' % len(u), *u))
    print('fpvecgen: schedule %d, %d cases, %d units -> %s'
          % (sched, NCASE, len(u), dest))


if __name__ == '__main__':
    main()
