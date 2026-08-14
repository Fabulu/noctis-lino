"""ns_spec.py -- Wave 4 reference side B.

The second of the two reference implementations.  ns_ref.c is a line-ordered
transcription of NOCTIS-0.CPP; this one is built the other way round, from
the DRAW TABLE outwards: every phase is a generator of draw sites, the draw
ledger is the primary object and the topology falls out of it.  The two
programmes are therefore wrong in different ways when they are wrong, which
is the entire point of having both.

HONESTY NOTE, because the house standard asks for it plainly.  Both sides
were written by the same agent in the same session, so this is not the same
thing as two people working from a spec in separate rooms.  What it does buy:

  * different construction order.  ns_ref.c follows the source top to bottom
    and derives the counts; this file follows the counts and derives the
    control flow.  A transposition, an off-by-one in a loop bound or a
    dropped short-circuit shows up in one and not the other.
  * different LCG.  ns_ref.c implements Borland's rand() in C from the
    pinned disassembly; this file calls Wave 1's already-pinned Python
    oracle (noctis-harness/brtl_oracle.Brtl), which
    tests/test_brtlrand.py grades over the whole 65,536-seed space.
  * different arithmetic.  ns_ref.c computes the identity on the real x87 at
    control word 133Fh; this file computes it in exact Fraction arithmetic
    with an explicit round-to-64-bit-significand step.  There is no shared
    floating-point code path at all.

What actually makes the answer trustworthy is neither of those: it is that
both are graded against artifacts this project did not produce -- the 1996
STARMAP.BIN and DL.EXE's live output.  Agreement between the two sides is
reported as its own check class (TRANSCRIPTION) and must never be read as
evidence about semantics.

--------------------------------------------------------------------------
THE DRAW TABLE.  random(n) is ONE draw for every n, including n == 0 and
n < 0.  zrandom(r) is TWO, first draw minus second (Wave 2, left to right).
Site ids are NOCTIS-0.CPP line numbers.

  prelude  1                       4082  random(class_planets[class]+1)

  A  per planet, 12 draws (13 on class 8 taking the else branch):
       4088 random(360)                        1
       4089 random(300*ray)                    1   [D]
       4090 zrandom(10*orb_seed)               2   [D]
       4091 zrandom(10*orb_seed)               2   [D]
       4092 random(orb_seed+10|orb_tilt|)      1   [D]
       4093 random(orb_seed)                   1   [D]
       4094 zrandom(p_ray)                     2   [D]
       4094 random(1000)                       1
       4096 random(planet_types)  class != 8   1
       4098 random(2)             class == 8   1
       4103 random(planet_types)  class == 8 and the 4098 draw was 0

  B  3 draws iff class == 0        4112 4113 4114 random(4)
     all three ifs evaluate, nothing short-circuits, and the writes to
     p_type[2..4] happen whether or not nop reaches them

  C  per planet, switch on CLASS, while-loops, UNBOUNDED
       class 2   while type==3               4123 random(10)
       class 5   while type in {6,9}         4127 random(10)
       class 7   type = 9                          ZERO draws
       class 9   while type not in {0,6,9}   4134 random(10)
       class 11  while type not in {1,7}     4138 random(10)

  D  per planet, switch on TYPE, no loops, 0..2 draws
       type 0                                4148 random(8)     1
       type 3   (n<2)||(n>6)||(class&&random(4))  -- SHORT-CIRCUITS
                4152 random(4) only when 2<=n<=6 and class != 0
                4153 random(2) only when the whole guard came out true
       type 7 and n<7                        4161 random(2)     1

  E  nob = nop; classes 2, 7 and 15 goto no_moons -- ZERO draws
     per planet: n<2  -> t=0, 4183 random(3) only if type==10
                 n>=2 -> 4186 random(possiblemoons[type]+1)  always
                 the nob+t>80 clamp removes BODIES, never a draw
     per moon, 10 base:
       4194 random(360)                        1
       4195 zrandom(300*p_ray[parent])         2   [D]
       4196 zrandom(10*orb_seed[q])            2   [D]
       4197 zrandom(10*orb_seed[q])            2   [D]
       4198 random(orb_seed[q]+10|tilt|)       1   [D]
       4199 random(orb_seed[PARENT])           1   [D]  value dead, draw live
       4201 random(planet_types)               1
     plus up to four extras:
       4213 random(c)  only if n>7   -- c==0 on the first moon: STILL DRAWS
       4214 random(c)  only if n>9
       4238 random(4)  only if r==3 and s<9 and class!=0
       4255 random(n)  only if class in {2,5,7,11} -> in practice {5,11}

  F  exactly 4 * nob    4308 4310 per planet, 4331 4333 per moon
  G  exactly 2 * nop    4348 random(3), then 4354 random(5) or 4358 random(2)
  H  0
--------------------------------------------------------------------------

Usage:
    python ns_spec.py <in.nsin> <out.nstopo> [--digest] [--ledger PATH]
                      [--identchop ext|f64] [--jitter EPS] [--starmap PATH]
"""

import os
import struct
import sys
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from brtl_oracle import Brtl                                    # noqa: E402

STARMAP = r"C:\programmieren\noctis\niv-plus\data\STARMAP.BIN"

M16 = 0xFFFF
M32 = 0xFFFFFFFF

# ------------------------------------------------------------------ tables
# NOCTIS-0.CPP 922-930, 976-985; NOCTIS-D.H 140-144.
STAR_CLASSES = 12
PLANET_TYPES = 10
AVGMOONS = 4
MAXBODIES = 20 * AVGMOONS                     # 80

CLASS_RAY = (5000, 15000, 300, 20000, 15000, 1000, 3000, 2000, 4000, 1500,
             30000, 250)
CLASS_RAYVAR = (2000, 10000, 200, 15000, 5000, 1000, 3000, 500, 5000, 10000,
                1000, 10)
CLASS_PLANETS = (12, 18, 8, 15, 20, 3, 0, 1, 7, 20, 2, 5)
POSSIBLEMOONS = (1, 1, 2, 3, 2, 2, 18, 2, 3, 20, 20)

PLANET_ORB_SCALING = 5.0
AVG_PLANET_SIZING = 2.4
MOON_ORB_SCALING = 12.8
AVG_MOON_SIZING = 1.8
AVG_PLANET_RAY = (0.007, 0.003, 0.010, 0.011, 0.010,
                  0.008, 0.064, 0.009, 0.012, 0.125, 5.000)
DEG = 3.14159265358979323846 / 180.0

# phase names, indexed the way NSTOPO r12..r19 are laid out
PHASES = ("prelude", "A", "B", "C", "D", "E", "F", "G")

# The eleven float-argument sites whose drawn value the port discards.
FLOAT_SITES = (4089, 4090, 4091, 4092, 4093, 4094, 4195, 4196, 4197, 4198, 4199)


# --------------------------------------------------------------- narrowing

def i16(v):
    """int is 16 bits in the DOS build.  Sign-extended: this is random()'s
    `movsx ax, word ptr [bp+6]`."""
    v &= M16
    return v - 0x10000 if v & 0x8000 else v


def i32(v):
    v &= M32
    return v - 0x100000000 if v & 0x80000000 else v


def ftoi16(d):
    """Borland's __ftol (chop to a 32-bit long) followed by reading AX.

    Two explicit steps, deliberately.  LR collapses this into a single (int)
    cast, which is undefined behaviour at exactly these sites.  An out-of-
    range value yields the x87 integer indefinite 0x80000000; that is real
    behaviour, not an error path.
    """
    if d != d or not (-2147483649.0 < d < 2147483648.0):
        l = -2147483648
    else:
        l = int(d)              # Python int() truncates toward zero, like C
    return i16(l)


def f32(v):
    """Narrow to IEEE binary32, which is what storing into a `float` does."""
    return struct.unpack("<f", struct.pack("<f", v))[0]


# ---------------------------------------------------------- the identity
# NOCTIS-0.CPP:4078 as an x87 instruction schedule at control word 133Fh:
#   fild x / fidiv 1e5 / fild y / fmulp / fidiv 1e5 / fild z / fmulp / fidiv
#   1e5 / fstp id.   Five operations, ONE store, nothing spilled between
# them.  Written here in exact rational arithmetic with an explicit round to
# a 64-bit significand after each operation, so there is no host floating
# point involved and nothing to get wrong twice.

def _round_sig(v, bits=64):
    """Round a Fraction to `bits` significant binary digits, ties to even."""
    if v == 0:
        return Fraction(0)
    neg = v < 0
    v = -v if neg else v
    e = v.numerator.bit_length() - v.denominator.bit_length()
    while Fraction(2) ** e > v:
        e -= 1
    while Fraction(2) ** (e + 1) <= v:
        e += 1
    shift = bits - 1 - e
    n = v * (Fraction(2) ** shift)
    q, r = divmod(n.numerator, n.denominator)
    twice = 2 * r
    if twice > n.denominator or (twice == n.denominator and (q & 1)):
        q += 1
    out = Fraction(q) / (Fraction(2) ** shift)
    return -out if neg else out


def identity_ext(x, y, z):
    """The extended (64-bit-significand) value the DOS routine leaves in
    st(0), as an exact Fraction."""
    v = Fraction(int(x))
    for op, k in (("d", 100000), ("m", int(y)), ("d", 100000),
                  ("m", int(z)), ("d", 100000)):
        v = v / k if op == "d" else v * k
        v = _round_sig(v, 64)
    return v


def to_f64(v):
    """Round a Fraction to binary64, ties to even, and return (float, bits)."""
    # float(Fraction) is correctly rounded, so the explicit 53-bit round is
    # belt and braces; it also documents that the store is a single rounding
    # of the extended value and not a double rounding.
    d = float(_round_sig(v, 53))
    return d, struct.unpack("<Q", struct.pack("<d", d))[0]


def ident_chop16(x, y, z, mode="ext"):
    """srand's argument.

    mode 'ext'  -- extract_ap_target_infos (NOCTIS-0.CPP:3970) computes the
                   product INLINE as srand's argument, so __ftol chops the
                   live extended value.
    mode 'f64'  -- update_star_label (NOCTIS.CPP:1244 then :1257) stores the
                   same expression into the double ap_target_id FIRST and
                   then calls srand on it, so that path chops a binary64.
                   The catalogue's 'S' class tags were written by THAT path.
    Both are offered because they are two different sites with two different
    answers, and ns_catalogue.py measures which one the catalogue agrees
    with rather than this file asserting it.
    """
    v = identity_ext(x, y, z)
    if mode == "f64":
        v = Fraction(to_f64(v)[0])
    # Borland __ftol stores a signed 64-bit integer and returns its low word.
    # Every int32-coordinate identity is far inside that 64-bit range.
    t = int(v)                                    # toward zero
    return t & M16                                # srand(unsigned): low 16


# ------------------------------------------------------------------ seed
# NOCTIS-0.CPP:4080 and :4051.  *, / and % share a precedence level and
# associate LEFT TO RIGHT, so
#     (long)x%10000*(long)y%10000*(long)z%10000
# is  ((((x%10000)*y)%10000)*z)%10000  -- a CHAIN of remainders, not a
# product of three of them.  The running value is a 32-bit long and it
# overflows on most real stars; that wrap is part of the answer.

def crem(a, b):
    """C's %, which truncates toward zero.  Python's % floors, and for the
    negative coordinates that are the normal case here the two differ."""
    q = abs(a) // abs(b)
    q = -q if (a < 0) != (b < 0) else q
    return a - q * b


def seed_from_xyz(x, y, z):
    t = crem(int(x), 10000)
    t = i32(t * int(y))
    t = crem(t, 10000)
    t = i32(t * int(z))
    t = crem(t, 10000)
    return t


# ===========================================================================


class Ledger(object):
    """(site, argument, value) for every draw, plus per-phase counts."""

    __slots__ = ("rows", "counts", "total", "budget", "over")

    def __init__(self, budget=100000):
        self.rows = []
        self.counts = [0] * 8
        self.total = 0
        self.budget = budget
        self.over = False


class System(object):
    """One star: extract_ap_target_infos, starnop and prepare_nearstar."""

    def __init__(self, x, y, z, force_class=-1, force_seed=-1,
                 identchop="ext", jitter=0.0, keep_ledger=False,
                 budget=100000):
        self.x, self.y, self.z = float(x), float(y), float(z)
        self.g = Brtl()
        self.led = Ledger(budget)
        self.keep_ledger = keep_ledger
        self.counting = False
        self.phase = 0
        self.site = 0
        self.extra_draws = 0
        self.jitter = jitter
        self.identchop = identchop
        self.force_class = force_class
        self.force_seed = force_seed

        self.p_type = [0] * MAXBODIES
        self.p_owner = [0] * MAXBODIES
        self.p_moonid = [0] * MAXBODIES
        self.p_ring = [0.0] * MAXBODIES
        self.p_tilt = [0.0] * MAXBODIES
        self.p_ray = [0.0] * MAXBODIES
        self.p_orb_ray = [0.0] * MAXBODIES
        self.p_orb_seed = [0.0] * MAXBODIES
        self.p_orb_tilt = [0.0] * MAXBODIES
        self.p_orb_orient = [0.0] * MAXBODIES
        self.p_orb_ecc = [0.0] * MAXBODIES

        self.labeled = -1
        self.run()

    # ------------------------------------------------------------ the RNG
    # Nothing in this class calls self.g.random directly; every draw goes
    # through _r or _z so the ledger cannot be bypassed.

    def _r(self, site, n):
        """random(n).  n is narrowed to int16 here and nowhere else."""
        n = i16(n)
        v = self.g.random(n)
        if self.counting:
            self.led.total += 1
            self.led.counts[self.phase] += 1
            if self.led.total > self.led.budget:
                self.led.over = True
            if self.keep_ledger:
                self.led.rows.append((site, n, v))
        else:
            self.extra_draws += 1
        return v

    def _rf(self, site, d):
        return self._r(site, ftoi16(d))

    def _z(self, site, n):
        """zrandom(n): two draws, first minus second, wrapping in int16."""
        n = i16(n)
        a = self._r(site, n)
        b = self._r(site, n)
        return float(i16(a - b))

    def _zf(self, site, d):
        return self._z(site, ftoi16(d))

    # --------------------------------------- NOCTIS-0.CPP:3968-3983

    def extract_ap_target_infos(self):
        self.g.srand(ident_chop16(self.x, self.y, self.z, self.identchop))
        self.ap_class = self._r(3972, STAR_CLASSES)
        ray = f32(f32(CLASS_RAY[self.ap_class]) +
                  f32(self._r(3973, CLASS_RAYVAR[self.ap_class])))
        self.ap_ray = f32(ray * 0.001)
        self.ap_spin = 0
        if self.ap_class == 11:
            self.ap_spin = self._r(3980, 30) + 1
        if self.ap_class == 7:
            self.ap_spin = self._r(3981, 12) + 1
        if self.ap_class == 2:
            self.ap_spin = self._r(3982, 4) + 1
        if self.force_class >= 0:
            self.ap_class = self.force_class

    # --------------------------------------- NOCTIS-0.CPP:4047-4057

    def starnop(self):
        self.g.srand(seed_from_xyz(self.x, self.y, self.z) & M16)
        r = self._r(4052, CLASS_PLANETS[self.ap_class] + 1)
        r += self._r(4053, 2)
        r -= self._r(4054, 2)
        return 0 if r < 0 else r

    # --------------------------------------- NOCTIS-0.CPP:4059-4376

    def run(self):
        self.extract_ap_target_infos()
        self.snop = self.starnop()

        self.cls = self.ap_class
        self.ray = f32(self.ap_ray + self.jitter)

        self.identity_frac = identity_ext(self.x, self.y, self.z)
        self.identity, self.identity_bits = to_f64(self.identity_frac)

        self.seed = (self.force_seed if self.force_seed >= 0
                     else seed_from_xyz(self.x, self.y, self.z)) & M16
        self.g.srand(self.seed)

        self.counting = True
        self.phase = 0
        self.nop = self._r(4082, CLASS_PLANETS[self.cls] + 1)
        self.nob = self.nop        # so a budget abort still has a record

        self._phase_a()
        self._phase_b()
        if self._phase_c():
            return
        self._phase_d()
        self._phase_e()
        self._phase_f()
        self._phase_g()
        self.counting = False

    # ---- A : 4086-4107
    def _phase_a(self):
        self.phase = 1
        cls = self.cls
        for n in range(self.nop):
            self.p_owner[n] = -1
            self.p_orb_orient[n] = DEG * float(self._r(4088, 360))
            self.p_orb_seed[n] = (3 * (n * n + 1) * self.ray +
                                  float(self._rf(4089, 300 * self.ray)) / 100)
            self.p_tilt[n] = self._zf(4090, 10 * self.p_orb_seed[n]) / 500
            self.p_orb_tilt[n] = self._zf(4091, 10 * self.p_orb_seed[n]) / 5000
            self.p_orb_ecc[n] = 1 - float(self._rf(
                4092, self.p_orb_seed[n] + 10 * abs(self.p_orb_tilt[n]))) / 2000
            self.p_ray[n] = float(self._rf(4093, self.p_orb_seed[n])) * 0.001 + 0.01
            # the only expression in the routine with two draw sites: the
            # zrandom is evaluated first, then random(1000)
            zr = self._zf(4094, self.p_ray[n])
            rr = float(self._r(4094, 1000))
            self.p_ring[n] = zr * (1 + rr / 100)
            if cls != 8:
                self.p_type[n] = self._r(4096, PLANET_TYPES)
            else:
                if self._r(4098, 2):
                    self.p_type[n] = 10
                    self.p_orb_tilt[n] *= 100
                else:
                    self.p_type[n] = self._r(4103, PLANET_TYPES)
            if cls in (2, 7, 15):
                self.p_orb_seed[n] *= 10

    # ---- B : 4111-4115
    def _phase_b(self):
        self.phase = 2
        if self.cls == 0:
            for site, idx in ((4112, 2), (4113, 3), (4114, 4)):
                if self._r(site, 4) == 2:
                    self.p_type[idx] = 3

    # ---- C : 4120-4140.  Returns True if the draw budget blew.
    def _phase_c(self):
        self.phase = 3
        cls = self.cls
        t = self.p_type
        for n in range(self.nop):
            if cls == 2:
                while t[n] == 3:
                    t[n] = self._r(4123, 10)
                    if self.led.over:
                        return True
            elif cls == 5:
                while t[n] == 6 or t[n] == 9:
                    t[n] = self._r(4127, 10)
                    if self.led.over:
                        return True
            elif cls == 7:
                t[n] = 9
            elif cls == 9:
                while t[n] != 0 and t[n] != 6 and t[n] != 9:
                    t[n] = self._r(4134, 10)
                    if self.led.over:
                        return True
            elif cls == 11:
                while t[n] != 1 and t[n] != 7:
                    t[n] = self._r(4138, 10)
                    if self.led.over:
                        return True
        return False

    # ---- D : 4145-4168
    def _phase_d(self):
        self.phase = 4
        t = self.p_type
        for n in range(self.nop):
            if t[n] == 0:
                if self._r(4148, 8):
                    t[n] += 1
            elif t[n] == 3:
                # || and && short-circuit: the random(4) fires only when
                # 2 <= n <= 6 AND the class is non-zero.
                if n < 2 or n > 6 or (self.cls != 0 and self._r(4152, 4)):
                    if self._r(4153, 2):
                        t[n] += 1
                    else:
                        t[n] -= 1
            elif t[n] == 7:
                if n < 7:
                    if self._r(4161, 2):
                        t[n] -= 1
                    else:
                        t[n] -= 2

    # ---- E : 4172-4260
    def _phase_e(self):
        self.phase = 5
        self.nob = self.nop
        cls = self.cls
        if cls in (2, 7, 15):
            return                                  # goto no_moons: 0 draws
        for n in range(self.nop):
            s = self.p_type[n]
            if n < 2:
                t = 0
                if s == 10:
                    t = self._r(4183, 3)
            else:
                t = self._r(4186, POSSIBLEMOONS[s] + 1)
            if self.nob + t > MAXBODIES:            # removes bodies, not draws
                t = MAXBODIES - self.nob
            for c in range(t):
                q = self.nob + c
                self.p_owner[q] = n
                self.p_moonid[q] = c
                self.p_orb_orient[q] = DEG * float(self._r(4194, 360))
                self.p_orb_seed[q] = ((c * c + 4) * self.p_ray[n] +
                                      self._zf(4195, 300 * self.p_ray[n]) / 100)
                self.p_tilt[q] = self._zf(4196, 10 * self.p_orb_seed[q]) / 50
                self.p_orb_tilt[q] = self._zf(4197, 10 * self.p_orb_seed[q]) / 500
                self.p_orb_ecc[q] = 1 - float(self._rf(
                    4198, self.p_orb_seed[q] + 10 * abs(self.p_orb_tilt[q]))) / 2000
                # 4199 reads the PARENT's orbital seed, index n not q.  The
                # value is dead; the draw is not.
                self.p_ray[q] = float(self._rf(4199, self.p_orb_seed[n])) * 0.05 + 0.1
                self.p_ring[q] = 0
                self.p_type[q] = self._r(4201, PLANET_TYPES)
                r = self.p_type[q]
                if r == 9 and s != 10:
                    r = 2
                if r == 6 and s < 9:
                    r = 5
                # c == 0 on the first moon of a planet: random(0) STILL draws
                if n > 7 and self._r(4213, c):
                    r = 7
                if n > 9 and self._r(4214, c):
                    r = 7
                if r in (2, 3, 4, 8):
                    if s != 6 and s < 9:
                        r = 1
                # so reaching 4238 needs s == 6 exactly
                if r == 3 and s < 9:
                    if n > 7:
                        r = 7
                    if cls != 0 and self._r(4238, 4):
                        r = 5
                    if cls in (2, 7, 11):
                        r = 8
                if r == 7 and n <= 5:
                    r = 1
                if cls in (2, 5, 7, 11) and self._r(4255, n):
                    r = 7
                self.p_type[q] = r
            self.nob += t

    # ---- F : 4300-4341, exactly 4 * nob draws
    def _phase_f(self):
        self.phase = 6
        key = self.ray * PLANET_ORB_SCALING
        if self.cls == 8:
            key *= 2
        if self.cls == 2:
            key *= 16
        if self.cls == 7:
            key *= 18
        if self.cls == 11:
            key *= 20
        for n in range(self.nop):
            apr = AVG_PLANET_RAY[self.p_type[n]]
            self.p_ray[n] = apr + apr * self._z(4308, 100) / 200
            self.p_ray[n] *= AVG_PLANET_SIZING
            self.p_orb_ray[n] = key + key * self._z(4310, 100) / 500
            self.p_orb_ray[n] += key * apr
            key += self.p_orb_ray[n] if n < 8 else 0.22 * self.p_orb_ray[n]

        n = self.nop
        while n < self.nob:
            q = 0
            c = self.p_owner[n]
            key = self.p_ray[c] * MOON_ORB_SCALING
            while n < self.nob and self.p_owner[n] == c:
                apr = AVG_PLANET_RAY[self.p_type[n]]
                self.p_ray[n] = apr + apr * self._z(4331, 100) / 200
                self.p_ray[n] *= AVG_MOON_SIZING
                self.p_orb_ray[n] = key + key * self._z(4333, 100) / 250
                self.p_orb_ray[n] += key * apr
                if q < 2:
                    key += self.p_orb_ray[n]
                if 2 <= q < 8:
                    key += 0.12 * self.p_orb_ray[n]
                if q >= 8:
                    key += 0.025 * self.p_orb_ray[n]
                q += 1
                n += 1

    # ---- G : 4345-4361, exactly 2 * nop draws
    def _phase_g(self):
        self.phase = 7
        for n in range(self.nop):
            self.p_ring[n] = 0.75 * self.p_ray[n] * (2 + self._r(4348, 3))
            s = self.p_type[n]
            if s != 6 and s != 9:
                if self._r(4354, 5):
                    self.p_ring[n] = 0
            else:
                if self._r(4358, 2):
                    self.p_ring[n] = 0

    # ---- H : 4363-4369, zero draws
    def phase_h(self, catalogue):
        self.labeled = 0
        for n in range(1, self.nob + 1):
            if catalogue.find(self.identity + n, b"P"):
                self.labeled += 1

    # ------------------------------------------------------------ output

    def record(self):
        r = [0] * 100
        r[0] = int(self.x) & M32
        r[1] = int(self.y) & M32
        r[2] = int(self.z) & M32
        r[3] = self.cls
        r[4] = self.seed & M16
        r[5] = self.nop
        r[6] = self.nob
        r[7] = self.snop
        r[8] = self.labeled & M32
        r[9] = self.identity_bits & M32
        r[10] = (self.identity_bits >> 32) & M32
        r[11] = self.led.total
        for i in range(8):
            r[12 + i] = self.led.counts[i]
        for b in range(MAXBODIES):
            if b >= self.nob:
                r[20 + b] = 0xFFFFFFFF
                continue
            ty = self.p_type[b] & 0xFF
            ow = (self.p_owner[b] + 1) & 0xFF
            mi = (self.p_moonid[b] & 0xFF) if b >= self.nop else 0
            r[20 + b] = ty | (ow << 8) | (mi << 16)
        return r


# ------------------------------------------------------- phase H catalogue

class Catalogue(object):
    """search_id_code, NOCTIS-0.CPP:4002-4041.  Consumes no draws."""

    IDSCALE = 0.00001

    def __init__(self, path=STARMAP):
        blob = open(path, "rb").read()
        self.n = (len(blob) - 4) // 32
        self.ids = []
        self.typ = []
        for i in range(self.n):
            off = 4 + 32 * i
            self.ids.append(struct.unpack_from("<d", blob, off)[0])
            self.typ.append(blob[off + 29])
        # nearstar_labeled only needs found/not-found, and "is there any
        # record of this type inside the window" is the same question whether
        # you scan in file order or bisect a sorted list.  find_scan() below
        # is the literal file-order scan, and phase_h_check() proves the two
        # agree on a sample rather than assuming it.
        self._sorted = {}
        for t in (ord("P"), ord("S")):
            self._sorted[t] = sorted(v for i, v in enumerate(self.ids)
                                     if self.typ[i] == t)

    def find(self, id_code, type_byte):
        import bisect
        t = type_byte[0] if isinstance(type_byte, bytes) else type_byte
        arr = self._sorted[t]
        j = bisect.bisect_right(arr, id_code - self.IDSCALE)
        return j < len(arr) and arr[j] < id_code + self.IDSCALE

    def find_scan(self, id_code, type_byte):
        """search_id_code exactly: file order, first hit, returns its offset."""
        lo = id_code - self.IDSCALE
        hi = id_code + self.IDSCALE
        t = type_byte[0] if isinstance(type_byte, bytes) else type_byte
        for i in range(self.n):
            if self.typ[i] == t and lo < self.ids[i] < hi:
                return 4 + 32 * i
        return None


# --------------------------------------------------------------- NSIN/NSTOPO

NSIN_MAGIC = 0x4E53494E
NSTOPO_MAGIC = 0x4E53544F
NSIN_STRIDE = 8
NSTOPO_STRIDE = 100


def write_nsin(path, rows):
    """rows: (x, y, z, class_override, seed_override, reserved, flags, 0)."""
    with open(path, "wb") as fh:
        fh.write(struct.pack("<4I", NSIN_MAGIC, 1, len(rows), NSIN_STRIDE))
        for r in rows:
            fh.write(struct.pack("<8i", *r))


def read_nsin(path):
    blob = open(path, "rb").read()
    magic, ver, nrec, stride = struct.unpack_from("<4I", blob, 0)
    if magic != NSIN_MAGIC:
        raise ValueError("%s is not NSIN: magic %08X, want %08X"
                         % (path, magic, NSIN_MAGIC))
    if ver != 1 or stride != NSIN_STRIDE:
        raise ValueError("NSIN version %d stride %d unsupported" % (ver, stride))
    out = []
    for i in range(nrec):
        out.append(struct.unpack_from("<8i", blob, 16 + 32 * i))
    return out


def read_nstopo(path):
    blob = open(path, "rb").read()
    magic, ver, nrec, stride, mode, producer, _r6, _r7 = \
        struct.unpack_from("<8I", blob, 0)
    if magic != NSTOPO_MAGIC:
        raise ValueError("%s is not NSTOPO: magic %08X, want %08X"
                         % (path, magic, NSTOPO_MAGIC))
    hdr = dict(version=ver, nrec=nrec, stride=stride, mode=mode,
               producer=producer)
    if mode == 1:
        dig = []
        for k in range(STAR_CLASSES):
            dig.append(struct.unpack_from("<3I", blob, 32 + 12 * k))
        return hdr, dig
    recs = []
    for i in range(nrec):
        recs.append(list(struct.unpack_from("<%dI" % stride, blob,
                                            32 + 4 * stride * i)))
    return hdr, recs


FNV_OFF = 14695981039346656037
FNV_PRIME = 1099511628211
M64 = (1 << 64) - 1


def fnv_u32(h, v):
    for k in range(4):
        h ^= (v >> (8 * k)) & 0xFF
        h = (h * FNV_PRIME) & M64
    return h


def main(argv):
    args, opts = [], {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--digest":
            opts["digest"] = True
        elif a in ("--ledger", "--identchop", "--jitter", "--starmap"):
            opts[a[2:]] = argv[i + 1]
            i += 1
        else:
            args.append(a)
        i += 1
    if len(args) < 2:
        print(__doc__)
        return 2
    inpath, outpath = args[0], args[1]
    digest = opts.get("digest", False)
    identchop = opts.get("identchop", "ext")
    jitter = float(opts.get("jitter", 0.0))
    ledpath = opts.get("ledger")

    rows = read_nsin(inpath)
    cat = None
    led = open(ledpath, "wb") if ledpath else None

    out = [struct.pack("<8I", NSTOPO_MAGIC, 1, len(rows), NSTOPO_STRIDE,
                       1 if digest else 0, 2, 0, 0)]
    dg = [FNV_OFF] * STAR_CLASSES
    dgn = [0] * STAR_CLASSES

    for k, r in enumerate(rows):
        x, y, z, fcls, fseed, _res, flags, _z2 = r
        s = System(x, y, z, force_class=fcls, force_seed=fseed,
                   identchop=identchop, jitter=jitter,
                   keep_ledger=led is not None)
        if s.led.over:
            sys.stderr.write("ns_spec: DRAW BUDGET EXCEEDED at record %d\n" % k)
            return 3
        if flags & 1:
            if cat is None:
                cat = Catalogue(opts.get("starmap", STARMAP))
            s.phase_h(cat)
        if led is not None:
            led.write(struct.pack("<3i", -1, k, 0))
            for site, arg, val in s.led.rows:
                led.write(struct.pack("<3i", site, arg, val))
        rec = s.record()
        if digest:
            c = s.cls
            for v in rec:
                dg[c] = fnv_u32(dg[c], v)
            dgn[c] += 1
        else:
            out.append(struct.pack("<%dI" % NSTOPO_STRIDE, *rec))

    if digest:
        for c in range(STAR_CLASSES):
            out.append(struct.pack("<3I", dg[c] & M32, (dg[c] >> 32) & M32,
                                   dgn[c]))
    open(outpath, "wb").write(b"".join(out))
    if led is not None:
        led.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
