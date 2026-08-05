"""geo_spec.py -- Wave 6 geometry reference side B.

Written from the SPECIFICATION, not from geo_ref.c: the draw table of
docs-notes/WAVE4_NEARSTAR.md section 2, the field formulas of
NOCTIS-0.CPP:4086-4361, and the arithmetic contract of
docs-notes/FLOATPOLICY.md section 3.1.  The two sides share no code and no
number format.  geo_ref.c runs on a real x87 at control word 133Fh; this
file contains NO hardware floating point in its arithmetic at all -- every
value is an exact rational and every operation is followed by an explicit
round-to-nearest-even to a stated significand width.  If the two agree bit
for bit, they agree for a reason.

WHY THAT SHAPE.  FLOATPOLICY.md's ladder says an engine that narrows after
every operation reproduces 2239 of 4113 catalogue records and one that does
not reproduces 4113.  The difference is invisible unless the precision of
every intermediate is a stated quantity.  Here it is:

    ext   64-bit significand   every intermediate inside one statement
    f64   53-bit significand   every assignment to a `double`
    f32   24-bit significand   every assignment to a `float`
                               (nearstar_ray, and zrandom's return type)

The original's expressions are instruction schedules that keep the running
value in st(0) and store once.  So in each statement below the operations
round to `ext` and the assignment rounds to `f64`.  That is the whole model.

THE OPEN QUESTION IS A PARAMETER, NOT A CHOICE.  The eleven float-argument
draw sites convert a double to a 16-bit int at a call boundary.  Borland's
__ftol truncates; a bare fistp under 133Fh rounds to nearest even; and the
value converted may be the live 80-bit intermediate or its binary64
rounding.  FLOATPOLICY.md 3.3 calls this UNSETTLED and forbids the graded
path from depending on it, so both axes are parameters here and geo_grade.py
measures the spread rather than picking a winner.

Usage:
    python geo_spec.py <in.nsin> <out.geob> [--cast chop|near]
                       [--castsrc ext|f64] [--prec ext|f64] [--limit N]
    python geo_spec.py --selftest
"""

import struct
import sys
from fractions import Fraction as F

# --------------------------------------------------------------------------
# exact binary rounding.  No Python float takes part in any of this.
# --------------------------------------------------------------------------

EXT, F64, F32 = 64, 53, 24


def _binexp(n, d):
    """smallest e with n/d < 2**e, for positive ints n, d."""
    e = n.bit_length() - d.bit_length()

    def lt(k):                                  # n/d < 2**k ?
        return n < (d << k) if k >= 0 else (n << -k) < d

    while not lt(e):
        e += 1
    while lt(e - 1):
        e -= 1
    return e


def _rhe(num, den):
    """round num/den (both positive) to the nearest integer, ties to even."""
    q, r = divmod(num, den)
    two = 2 * r
    if two > den or (two == den and (q & 1)):
        q += 1
    return q


def rnd(x, prec):
    """round an exact rational to `prec` significand bits, nearest-even."""
    if x == 0:
        return F(0)
    s = -1 if x < 0 else 1
    a = -x if x < 0 else x
    n, d = a.numerator, a.denominator
    e = _binexp(n, d)
    k = prec - e                                # scale so the result is an int
    if k >= 0:
        q = _rhe(n << k, d)
    else:
        q = _rhe(n, d << -k)
    return s * (F(q) / F(1 << k) if k >= 0 else F(q * (1 << -k)))


class Eng:
    """the arithmetic engine.  `op` is one x87 operation, `st` is a store."""

    def __init__(self, prec_f64=False):
        self.iw = F64 if prec_f64 else EXT       # intermediate width

    def op(self, x):
        return rnd(x, self.iw)

    def f64(self, x):
        return rnd(x, F64)

    def f32(self, x):
        return rnd(x, F32)


def lit(x):
    """a C floating literal: the exact value of the binary64 the compiler
    emitted.  This is a conversion of a constant, not arithmetic."""
    return F(x)


def bits(fr):
    """little-endian binary64 bytes of an exact value that IS a binary64."""
    f = float(fr)
    if F(f) != fr:
        raise AssertionError("value %r is not exactly a binary64" % (fr,))
    return struct.pack("<d", f)


# --------------------------------------------------------------------------
# Wave 1: Borland's LCG.  state16 seeded, 32-bit LCG, bits 16..30 returned.
# --------------------------------------------------------------------------

M32 = 0xFFFFFFFF


def i16(v):
    v &= 0xFFFF
    return v - 0x10000 if v >= 0x8000 else v


def i32(v):
    v &= M32
    return v - 0x100000000 if v >= 0x80000000 else v


class Rng:
    def __init__(self):
        self.s = 1
        self.draws = 0
        self.fdraws = 0
        self.infs = False

    def srand(self, seed):
        self.s = seed & 0xFFFF

    def rand(self):
        self.draws += 1
        if self.infs:
            self.fdraws += 1
        self.s = (self.s * 0x015A4E35 + 1) & M32
        return (self.s >> 16) & 0x7FFF

    def random(self, n):
        """random(n) is ONE rand() for every n, including 0 and negative n.
        The prototype is int random(int), so the argument narrows to int16 at
        the call; the product is a 32-bit imul; the divide by 0x8000 is idiv,
        which truncates toward zero; the quotient narrows to int16 again."""
        n = i16(n)
        r = self.rand()
        p = i32(r * n)
        q = abs(p) // 0x8000
        return i16(-q if p < 0 else q)

    def zrandom(self, n):
        """left to right: first draw minus second, subtracted as int16, then
        widened to the float zrandom() returns."""
        a = self.random(n)
        b = self.random(n)
        return F(i16(a - b))


# --------------------------------------------------------------------------
# the float-to-int cast boundary.  Both axes are parameters.
# --------------------------------------------------------------------------

class Cast:
    def __init__(self, near=False, src_f64=False):
        self.near = near
        self.src_f64 = src_f64
        self.sites = 0

    def to_i16(self, x):
        self.sites += 1
        if self.src_f64:
            x = rnd(x, F64)
        if not (F(-2147483649) < x < F(2147483648)):
            return 0                             # low 16 of 0x80000000
        if self.near:
            n = _rhe(abs(x).numerator, abs(x).denominator)
            v = -n if x < 0 else n
        else:
            a = abs(x)
            n = a.numerator // a.denominator     # truncate toward zero
            v = -n if x < 0 else n
        return i16(v)


# --------------------------------------------------------------------------
# the constant tables, NOCTIS-0.CPP 922-985 / NOCTIS-D.H 140-144
# --------------------------------------------------------------------------

STAR_CLASSES = 12
PLANET_TYPES = 10
MAXBODIES = 80

CLASS_RAY = [5000, 15000, 300, 20000, 15000, 1000, 3000, 2000, 4000, 1500,
             30000, 250]
CLASS_RAYVAR = [2000, 10000, 200, 15000, 5000, 1000, 3000, 500, 5000, 10000,
                1000, 10]
CLASS_PLANETS = [12, 18, 8, 15, 20, 3, 0, 1, 7, 20, 2, 5]
POSSIBLE_MOONS = [1, 1, 2, 3, 2, 2, 18, 2, 3, 20, 20]

PLANET_ORB_SCALING = lit(5.0)
AVG_PLANET_SIZING = lit(2.4)
MOON_ORB_SCALING = lit(12.8)
AVG_MOON_SIZING = lit(1.8)

AVG_PLANET_RAY = [lit(v) for v in
                  (0.007, 0.003, 0.010, 0.011, 0.010,
                   0.008, 0.064, 0.009, 0.012, 0.125, 5.000)]

# TDPOLYGS.H:95 / DL.CPP:356 -- `const double deg = M_PI / 180;`, with
# Borland's M_PI spelled 3.14159265358979323846.  The compiler rounds the
# decimal literal to a binary64 FIRST and then does one correctly rounded
# binary64 division; rounding the exact rational pi_decimal/180 in one step
# is a different (and wrong) number.  Both steps are spelled out.
PI64 = rnd(F(314159265358979323846, 10 ** 20), F64)
DEG = rnd(PI64 / F(180), F64)

FIELDS = ("orb_orient", "orb_seed", "tilt", "orb_tilt",
          "orb_ecc", "ray", "orb_ray", "ring")


class Star:
    """one system.  Arrays are 80 long and slots above nob are never read."""

    def __init__(self):
        self.cls = 0
        self.nop = 0
        self.nob = 0
        self.ray = F(0)                          # nearstar_ray, a float
        self.identity = F(0)
        self.type = [0] * MAXBODIES
        self.owner = [0] * MAXBODIES
        self.moonid = [0] * MAXBODIES
        self.g = {f: [F(0)] * MAXBODIES for f in FIELDS}


# --------------------------------------------------------------------------
# the identity chain and the seed chain.  Unchanged from Wave 3 / Wave 4;
# reproduced here because the draw stream starts from them.
# --------------------------------------------------------------------------

def identity_ext(x, y, z, e):
    """x/1e5*y/1e5*z/1e5, five operations, nothing stored in between."""
    v = e.op(F(x) / F(100000))
    v = e.op(v * F(y))
    v = e.op(v / F(100000))
    v = e.op(v * F(z))
    v = e.op(v / F(100000))
    return v


def chop16(v):
    if not (F(-2147483649) < v < F(2147483648)):
        return 0
    a = abs(v)
    n = a.numerator // a.denominator
    return (-n if v < 0 else n) & 0xFFFF


def seed_xyz(x, y, z):
    """((((x%10000)*y)%10000)*z)%10000 -- left to right, wrapping in int32,
    with C's truncating %."""
    def cmod(a, b):
        r = abs(a) % b
        return -r if a < 0 else r

    t = cmod(x, 10000)
    t = i32(t * y)
    t = cmod(t, 10000)
    t = i32(t * z)
    t = cmod(t, 10000)
    return t


# --------------------------------------------------------------------------
# the generator, phase by phase, in draw-table order
# --------------------------------------------------------------------------

def generate(x, y, z, forced_class=-1, forced_seed=-1,
             prec_f64=False, cast=None):
    e = Eng(prec_f64)
    r = Rng()
    c = cast or Cast()
    s = Star()

    def fs(fn, arg):
        """a float-argument site: narrow, then draw."""
        r.infs = True
        v = fn(c.to_i16(arg))
        r.infs = False
        return v

    # ---- extract_ap_target_infos, :3968-3983 -----------------------------
    r.srand(chop16(identity_ext(x, y, z, e)))
    ap_class = r.random(STAR_CLASSES)
    # ap_target_ray is a float: one store at 24 bits
    v = e.op(F(CLASS_RAY[ap_class]) + F(r.random(CLASS_RAYVAR[ap_class])))
    ap_ray = e.f32(e.op(v * lit(0.001)))
    if ap_class == 11:
        r.random(30)
    if ap_class == 7:
        r.random(12)
    if ap_class == 2:
        r.random(4)

    if forced_class >= 0:
        ap_class = forced_class

    # ---- starnop, :4047-4057.  Runs before prepare_nearstar. -------------
    r.srand(seed_xyz(x, y, z) & 0xFFFF)
    r.random(CLASS_PLANETS[ap_class] + 1)
    r.random(2)
    r.random(2)

    # ---- prepare_nearstar ------------------------------------------------
    s.cls = ap_class
    s.ray = ap_ray
    s.identity = e.f64(identity_ext(x, y, z, e))
    r.draws = 0
    r.fdraws = 0
    r.srand((forced_seed if forced_seed >= 0 else seed_xyz(x, y, z)) & 0xFFFF)

    g = s.g

    # prelude, :4082 -- 1 draw
    s.nop = r.random(CLASS_PLANETS[s.cls] + 1)

    # ---- phase A, :4086-4107 -- 12 draws per planet, 13 on class 8's else
    for n in range(s.nop):
        s.owner[n] = -1

        # :4088
        g["orb_orient"][n] = e.f64(e.op(DEG * F(r.random(360))))

        # :4089  3*(n*n+1)*ray + (float)random(300*ray)/100
        a = e.op(F(3 * (n * n + 1)) * s.ray)
        d = fs(r.random, e.op(F(300) * s.ray))
        b = e.op(F(d) / F(100))
        g["orb_seed"][n] = e.f64(e.op(a + b))

        # :4090  zrandom(10*orb_seed)/500
        d = fs(r.zrandom, e.op(F(10) * g["orb_seed"][n]))
        g["tilt"][n] = e.f64(e.op(d / F(500)))

        # :4091  zrandom(10*orb_seed)/5000
        d = fs(r.zrandom, e.op(F(10) * g["orb_seed"][n]))
        g["orb_tilt"][n] = e.f64(e.op(d / F(5000)))

        # :4092  1 - random(orb_seed + 10*fabs(orb_tilt))/2000
        ab = e.op(F(10) * abs(g["orb_tilt"][n]))
        d = fs(r.random, e.op(g["orb_seed"][n] + ab))
        g["orb_ecc"][n] = e.f64(e.op(F(1) - e.op(F(d) / F(2000))))

        # :4093  random(orb_seed)*0.001 + 0.01
        d = fs(r.random, g["orb_seed"][n])
        g["ray"][n] = e.f64(e.op(e.op(F(d) * lit(0.001)) + lit(0.01)))

        # :4094  zrandom(ray) * (1 + random(1000)/100).  Source order: the
        # zrandom's two draws come first.  The value is dead (phase G
        # overwrites every planet's ring) but the four draws are live.
        zr = fs(r.zrandom, g["ray"][n])
        rr = F(r.random(1000))
        k = e.op(F(1) + e.op(rr / F(100)))
        g["ring"][n] = e.f64(e.op(zr * k))

        if s.cls != 8:
            s.type[n] = r.random(PLANET_TYPES)
        else:
            if r.random(2):
                s.type[n] = 10
                g["orb_tilt"][n] = e.f64(e.op(g["orb_tilt"][n] * F(100)))
            else:
                s.type[n] = r.random(PLANET_TYPES)

        if s.cls in (2, 7, 15):
            g["orb_seed"][n] = e.f64(e.op(g["orb_seed"][n] * F(10)))

    # ---- phase B, :4111-4115 -- 3 draws iff class 0, none short-circuited
    if s.cls == 0:
        if r.random(4) == 2:
            s.type[2] = 3
        if r.random(4) == 2:
            s.type[3] = 3
        if r.random(4) == 2:
            s.type[4] = 3

    # ---- phase C, :4120-4139 -- unbounded re-rolls, classes 2/5/9/11 -----
    for n in range(s.nop):
        if s.cls == 2:
            while s.type[n] == 3:
                s.type[n] = r.random(10)
        elif s.cls == 5:
            while s.type[n] in (6, 9):
                s.type[n] = r.random(10)
        elif s.cls == 7:
            s.type[n] = 9
        elif s.cls == 9:
            while s.type[n] not in (0, 6, 9):
                s.type[n] = r.random(10)
        elif s.cls == 11:
            while s.type[n] not in (1, 7):
                s.type[n] = r.random(10)

    # ---- phase D, :4145-4168 -- 0..2 draws per planet, && short-circuits -
    for n in range(s.nop):
        t = s.type[n]
        if t == 0:
            if r.random(8):
                s.type[n] += 1
        elif t == 3:
            if (n < 2) or (n > 6) or (s.cls != 0 and r.random(4)):
                if r.random(2):
                    s.type[n] += 1
                else:
                    s.type[n] -= 1
        elif t == 7:
            if n < 7:
                if r.random(2):
                    s.type[n] -= 1
                else:
                    s.type[n] -= 2

    # ---- phase E, :4172-4260 --------------------------------------------
    s.nob = s.nop
    if s.cls not in (2, 7, 15):
        for n in range(s.nop):
            parent = s.type[n]
            if n < 2:
                t = r.random(3) if parent == 10 else 0
            else:
                t = r.random(POSSIBLE_MOONS[parent] + 1)
            if s.nob + t > MAXBODIES:
                t = MAXBODIES - s.nob            # removes bodies, never draws
            for cc in range(t):
                q = s.nob + cc
                s.owner[q] = n
                s.moonid[q] = cc

                # :4194
                g["orb_orient"][q] = e.f64(e.op(DEG * F(r.random(360))))

                # :4195  (c*c+4)*ray[n] + (float)zrandom(300*ray[n])/100
                a = e.op(F(cc * cc + 4) * g["ray"][n])
                d = fs(r.zrandom, e.op(F(300) * g["ray"][n]))
                b = e.op(d / F(100))
                g["orb_seed"][q] = e.f64(e.op(a + b))

                # :4196
                d = fs(r.zrandom, e.op(F(10) * g["orb_seed"][q]))
                g["tilt"][q] = e.f64(e.op(d / F(50)))

                # :4197
                d = fs(r.zrandom, e.op(F(10) * g["orb_seed"][q]))
                g["orb_tilt"][q] = e.f64(e.op(d / F(500)))

                # :4198
                ab = e.op(F(10) * abs(g["orb_tilt"][q]))
                d = fs(r.random, e.op(g["orb_seed"][q] + ab))
                g["orb_ecc"][q] = e.f64(e.op(F(1) - e.op(F(d) / F(2000))))

                # :4199  reads the PARENT's seed, index n, not q
                d = fs(r.random, g["orb_seed"][n])
                g["ray"][q] = e.f64(e.op(e.op(F(d) * lit(0.05)) + lit(0.1)))

                g["ring"][q] = F(0)

                s.type[q] = r.random(PLANET_TYPES)
                rr = s.type[q]
                if rr == 9 and parent != 10:
                    rr = 2
                if rr == 6 and parent < 9:
                    rr = 5
                if n > 7 and r.random(cc):       # random(0) still draws
                    rr = 7
                if n > 9 and r.random(cc):
                    rr = 7
                if rr in (2, 3, 4, 8):
                    if parent != 6 and parent < 9:
                        rr = 1
                if rr == 3 and parent < 9:
                    if n > 7:
                        rr = 7
                    if s.cls != 0 and r.random(4):
                        rr = 5
                    if s.cls in (2, 7, 11):
                        rr = 8
                if rr == 7 and n <= 5:
                    rr = 1
                if s.cls in (2, 5, 7, 11) and r.random(n):
                    rr = 7
                s.type[q] = rr
            s.nob += t

    # ---- phase F, :4300-4341 -- exactly 4 draws per body -----------------
    key = e.f64(e.op(s.ray * PLANET_ORB_SCALING))
    if s.cls == 8:
        key = e.f64(e.op(key * F(2)))
    if s.cls == 2:
        key = e.f64(e.op(key * F(16)))
    if s.cls == 7:
        key = e.f64(e.op(key * F(18)))
    if s.cls == 11:
        key = e.f64(e.op(key * F(20)))

    for n in range(s.nop):
        avg = AVG_PLANET_RAY[s.type[n]]
        v = e.op(e.op(avg * r.zrandom(100)) / F(200))
        g["ray"][n] = e.f64(e.op(avg + v))
        g["ray"][n] = e.f64(e.op(g["ray"][n] * AVG_PLANET_SIZING))
        v = e.op(e.op(key * r.zrandom(100)) / F(500))
        g["orb_ray"][n] = e.f64(e.op(key + v))
        g["orb_ray"][n] = e.f64(e.op(g["orb_ray"][n] + e.op(key * avg)))
        if n < 8:
            key = e.f64(e.op(key + g["orb_ray"][n]))
        else:
            key = e.f64(e.op(key + e.op(lit(0.22) * g["orb_ray"][n])))

    n = s.nop
    while n < s.nob:
        q = 0
        owner = s.owner[n]
        key = e.f64(e.op(g["ray"][owner] * MOON_ORB_SCALING))
        while n < s.nob and s.owner[n] == owner:
            avg = AVG_PLANET_RAY[s.type[n]]
            v = e.op(e.op(avg * r.zrandom(100)) / F(200))
            g["ray"][n] = e.f64(e.op(avg + v))
            g["ray"][n] = e.f64(e.op(g["ray"][n] * AVG_MOON_SIZING))
            v = e.op(e.op(key * r.zrandom(100)) / F(250))
            g["orb_ray"][n] = e.f64(e.op(key + v))
            g["orb_ray"][n] = e.f64(e.op(g["orb_ray"][n] + e.op(key * avg)))
            if q < 2:
                key = e.f64(e.op(key + g["orb_ray"][n]))
            if 2 <= q < 8:
                key = e.f64(e.op(key + e.op(lit(0.12) * g["orb_ray"][n])))
            if q >= 8:
                key = e.f64(e.op(key + e.op(lit(0.025) * g["orb_ray"][n])))
            q += 1
            n += 1

    # ---- phase G, :4345-4361 -- exactly 2 draws per planet ---------------
    for n in range(s.nop):
        v = e.op(lit(0.75) * g["ray"][n])
        g["ring"][n] = e.f64(e.op(v * F(2 + r.random(3))))
        if s.type[n] not in (6, 9):
            if r.random(5):
                g["ring"][n] = F(0)
        else:
            if r.random(2):
                g["ring"][n] = F(0)

    s.draws = r.draws
    s.fdraws = r.fdraws
    s.castsites = c.sites
    return s


# --------------------------------------------------------------------------
# NSIN in, GEOB out -- the same container geo_ref.c writes
# --------------------------------------------------------------------------

NSIN_MAGIC = 0x4E53494E
GEOB_MAGIC = 0x47454F42
NSIN_STRIDE = 8


def read_nsin(path, limit=None):
    with open(path, "rb") as fh:
        blob = fh.read()
    magic, ver, nrec, stride = struct.unpack_from("<4I", blob, 0)
    if magic != NSIN_MAGIC or stride != NSIN_STRIDE:
        raise SystemExit("geo_spec: %s is not NSIN" % path)
    need = 16 + nrec * stride * 4
    if len(blob) < need:
        raise SystemExit("geo_spec: NSIN header claims %d records, file holds "
                         "%d bytes (needs %d)" % (nrec, len(blob), need))
    out = []
    for k in range(nrec if limit is None else min(nrec, limit)):
        out.append(struct.unpack_from("<8i", blob, 16 + k * 32))
    return out


def write_geob(path, recs, cast_near, castsrc_f64, prec_f64):
    with open(path, "wb") as fh:
        fh.write(struct.pack("<8I", GEOB_MAGIC, 1, len(recs), len(FIELDS),
                             int(cast_near), int(castsrc_f64), int(prec_f64), 0))
        for s in recs:
            fh.write(struct.pack("<4I", s.cls & 0xFFFFFFFF, s.nop, s.nob,
                                 s.draws))
            for b in range(s.nob):
                for f in FIELDS:
                    fh.write(bits(s.g[f][b]))


def selftest():
    ok = True
    # rnd() against known binary64 boundaries
    cases = [(F(1), 53, F(1)),
             (F(1, 3), 53, F(6004799503160661, 2 ** 54)),
             (F(1, 3), 64, F(12297829382473034411, 2 ** 65)),
             (F(-1, 3), 24, F(-11184811, 2 ** 25)),
             (F(3), 1, F(4)),                    # ties to even, upward
             (F(5), 2, F(4)),                    # ties to even, downward
             (F(0), 53, F(0))]
    for x, p, want in cases:
        got = rnd(x, p)
        if got != want:
            print("FAIL rnd(%s,%d) = %s want %s" % (x, p, got, want))
            ok = False
    # 0.001 as a binary64 must match the literal exactly
    if lit(0.001) != F(1152921504606847, 2 ** 60):
        print("FAIL lit(0.001) = %s" % (lit(0.001),))
        ok = False
    # the LCG, first four draws from seed 1 (Wave 1, pinned bytes)
    r = Rng()
    r.srand(1)
    got = [r.rand() for _ in range(4)]
    st = 1
    want = []
    for _ in range(4):
        st = (st * 0x015A4E35 + 1) & M32
        want.append((st >> 16) & 0x7FFF)
    if got != want:
        print("FAIL lcg %s vs %s" % (got, want))
        ok = False
    # int16 wrap at the cast boundary, Wave 1's finding
    c = Cast()
    if c.to_i16(F(40000)) != -25536:
        print("FAIL cast 40000 -> %d" % c.to_i16(F(40000)))
        ok = False
    if Cast(near=True).to_i16(F(1, 2)) != 0 or Cast(near=True).to_i16(F(3, 2)) != 2:
        print("FAIL ties-to-even at the cast boundary")
        ok = False
    if Cast().to_i16(F(3, 2)) != 1 or Cast().to_i16(F(-3, 2)) != -1:
        print("FAIL chop at the cast boundary")
        ok = False
    print("geo_spec selftest:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main(argv):
    if "--selftest" in argv:
        return selftest()
    pos = [a for a in argv if not a.startswith("--")]
    def opt(name, default):
        return argv[argv.index(name) + 1] if name in argv else default
    if len(pos) < 2:
        print(__doc__)
        return 2
    limit = int(opt("--limit", "0")) or None
    cast_near = opt("--cast", "chop") == "near"
    castsrc_f64 = opt("--castsrc", "ext") == "f64"
    prec_f64 = opt("--prec", "ext") == "f64"

    recs = []
    for (x, y, z, fclass, fseed, _a, _b, _c) in read_nsin(pos[0], limit):
        recs.append(generate(x, y, z, fclass, fseed, prec_f64,
                             Cast(cast_near, castsrc_f64)))
    write_geob(pos[1], recs, cast_near, castsrc_f64, prec_f64)
    print("geo_spec: %d systems -> %s (cast=%s castsrc=%s prec=%s)"
          % (len(recs), pos[1], "near" if cast_near else "chop",
             "f64" if castsrc_f64 else "ext", "f64" if prec_f64 else "ext"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
