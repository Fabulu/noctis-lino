r"""gr_spec.py - Python reference for Wave 7b build_surface() + SURFACE.BIN.

PROVENANCE
----------
Transliterated from the DOS sources only:

    C:\programmieren\noctis\niv-plus\source\NOCTIS-1.CPP
        build_surface()         :1948-2731
        round_hill              :1494-1528
        smoothterrain           :1530-1543
        rockyground             :1545-1559
        SURFACE.BIN read        :3722-3735
        SURFACE.BIN write       :4992-5002
        global_surface_seed     :3671-3673
    C:\programmieren\noctis\niv-plus\source\NOCTIS-0.CPP
        fast_srand/fast_random  :1075-1107
        flandom                 :1109-1110
    C:\programmieren\noctis\niv-plus\source\NOCTIS-D.H
        struct quadrant         :171-176
        ps_bytes/oc_bytes       :42/45
        ROCKS/VEGET/TREES       :148-151

It is NOT derived from noctis-iv-lr, which PORTPLAN disqualifies for this
function.  Where the two differ this file implements VANILLA, and the
divergence is called out in a comment tagged LR-DIVERGENCE.

The two generators (fast_random and Borland random) are re-implemented here
from the DOS inline assembly / machine code rather than imported from su_spec,
so a bug in one file cannot hide in the other.  The float chop uses su_fp.py's
exact-rational helpers, which are general-purpose Wave 3 utilities.

SCOPE: this file covers SURFACE.BIN I/O (40-byte NIV+ R2.3 pack/unpack), the
global_surface_seed chop, the build_surface prologue (groundflares, tree
parameters, objectschart ROCKS fill), and the two integer painters that are
purely random-driven: rockyground and smoothterrain.  The float-using painters
(round_hill, std_crater, etc.) are present for the prologue draw-accounting
but their float outputs are not byte-exact-graded in this tier.
"""

import struct
import sys
from fractions import Fraction

import numpy as np

from su_fp import ext, f32, ftol32

M16 = 0xFFFF
M32 = 0xFFFFFFFF

# ---------------------------------------------------------------------------
# Constants from NOCTIS-D.H
# ---------------------------------------------------------------------------

PS_BYTES = 40000          # p_surfacemap, 200×200 heightmap
OC_BYTES = 40000          # objectschart, one quadrant struct per cell
TXTR_BYTES = 65536        # txtr / p_background, 256×256 ground texture
SURFACE_BIN_SIZE = 40     # NIV+ R2.3 SURFACE.BIN

ROCKS = 0
VEGET = 1
TREES = 2
NOTHING = 3

FNV_OFF = 0x811C9DC5
FNV_PRIME = 0x01000193


def fnv(h, v):
    v &= M32
    for _ in range(4):
        h = ((h ^ (v & 0xFF)) * FNV_PRIME) & M32
        v >>= 8
    return h


def fnv_bytes(buf):
    h = FNV_OFF
    for byte in bytes(buf):
        h = ((h ^ byte) * FNV_PRIME) & M32
    return h


def i16(v):
    v &= M16
    return v - 0x10000 if v & 0x8000 else v


def cdiv(a, b):
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q


# ---------------------------------------------------------------------------
# 1.  The two generators, each with its own draw counter.
# ---------------------------------------------------------------------------

class Fast(object):
    """NOCTIS-0.CPP:1075-1107.

        fast_srand:  or word ptr seed, 3        <- LOW WORD only
                     mov dword flat_rnd_seed, seed
        fast_random: eax = edx = flat_rnd_seed
                     mul edx                    <- UNSIGNED 32x32 -> 64
                     add al, dl                 <- EIGHT-bit add, no carry out
                     add flat_rnd_seed, eax     <- 32-bit
                     and eax, mask
    """

    __slots__ = ("s", "n", "h", "log", "keep")

    def __init__(self, keep=False):
        self.s = 0
        self.n = 0
        self.h = FNV_OFF
        self.log = []
        self.keep = keep

    def srand(self, seed):
        s = seed & M32
        self.s = (s & 0xFFFF0000) | ((s & M16) | 3)

    def random(self, mask):
        p = self.s * self.s                     # exact, unsigned
        eax = p & M32
        edx = (p >> 32) & M32
        al = (eax + edx) & 0xFF                 # 8-bit fold
        eax = (eax & 0xFFFFFF00) | al
        self.s = (self.s + eax) & M32
        return eax & mask

    def raw(self, mask, site=0):
        v = self.random(mask)
        self.n += 1
        self.h = fnv(self.h, v)
        if self.keep:
            self.log.append((site, mask, v))
        return v


class Brt(object):
    """Borland random(), counted. Uses brtl_oracle.Brtl for the generator."""

    __slots__ = ("g", "n", "h", "log", "keep")

    def __init__(self, keep=False):
        from brtl_oracle import Brtl as _Brtl
        self.g = _Brtl()
        self.n = 0
        self.h = FNV_OFF
        self.log = []
        self.keep = keep

    def srand(self, v):
        self.g.srand(v & M16)

    def random(self, n, site=0):
        v = self.g.random(i16(n))
        self.n += 1
        self.h = fnv(self.h, v & M32)
        if self.keep:
            self.log.append((site, n, v))
        return v


# ---------------------------------------------------------------------------
# 2.  SURFACE.BIN - 40-byte NIV+ R2.3 layout
# ---------------------------------------------------------------------------
#     NOCTIS-1.CPP:3722-3735 (read), :4992-5002 (write).
#
#     off 0  landing_pt_lon  int16        off 20 pos_x      float32
#     off 2  landing_pt_lat  int16        off 24 pos_y      float32
#     off 4  atl_x           int32 quot   off 28 pos_z      float32
#     off 8  atl_z           int32 quot   off 32 user_alfa  float32
#     off 12 atl_x2          int32 rem    off 36 user_beta  float32
#     off 16 atl_z2          int32 rem    total 40
#
#     pos_x == (atl_x<<14)+atl_x2; on fresh landing atl_x2==atl_z2==8192
#     (write-once, NOT re-derived as you walk).  Stock/LR adds 5 trailing
#     bytes which NIV+ dropped — port writes 40, NEVER 45.

SURFACE_BIN_FIELDS = (
    "landing_pt_lon", "landing_pt_lat",
    "atl_x", "atl_z", "atl_x2", "atl_z2",
    "pos_x", "pos_y", "pos_z", "user_alfa", "user_beta",
)


def pack_surface_bin(d):
    """Pack the 11 fields into 40 bytes, NIV+ R2.3 layout.

    Uses struct '<hh4i5f': two int16, four int32, five float32.  Little-endian
    matches the DOS _read/_write byte order (Borland on x86).
    """
    return struct.pack("<hh4i5f",
                       i16(d["landing_pt_lon"]),
                       i16(d["landing_pt_lat"]),
                       d["atl_x"], d["atl_z"], d["atl_x2"], d["atl_z2"],
                       float(d["pos_x"]), float(d["pos_y"]), float(d["pos_z"]),
                       float(d["user_alfa"]), float(d["user_beta"]))


def unpack_surface_bin(buf):
    """Unpack 40 bytes into the 11-field dict.  Round-trip of pack_surface_bin."""
    if len(buf) < SURFACE_BIN_SIZE:
        raise ValueError("SURFACE.BIN too short: %d bytes" % len(buf))
    lon, lat, ax, az, ax2, az2, px, py, pz, ua, ub = \
        struct.unpack("<hh4i5f", buf[:SURFACE_BIN_SIZE])
    return dict(landing_pt_lon=lon, landing_pt_lat=lat,
                atl_x=ax, atl_z=az, atl_x2=ax2, atl_z2=az2,
                pos_x=px, pos_y=py, pos_z=pz, user_alfa=ua, user_beta=ub)


def derive_atl(pos, atl_quot, atl_rem):
    """The pos_x == (atl_x<<14)+atl_x2 identity check.

    On fresh landing atl_x2/atl_z2 are frozen at 8192 and are NOT re-derived
    as the walker moves.  This function verifies the identity holds at the
    moment of writing."""
    return (atl_quot << 14) + atl_rem


# ---------------------------------------------------------------------------
# 3.  global_surface_seed - the exact-required float chop
# ---------------------------------------------------------------------------
#     NOCTIS-1.CPP:3671-3673:
#
#       global_surface_seed = (nearstar_p_ray[ip_targetted]
#                              + nearstar_p_orb_ray[ip_targetted]
#                              + nearstar_p_orb_orient[ip_targetted]) * 4112;
#
#     ray is double, orb_ray and orb_orient are float (promoted to double
#     in the sum).  The result is stored to `long global_surface_seed` via
#     __ftol (chop).  The +*4112 happens in double before the chop.

def global_surface_seed_chop(ray, orb_ray, orb_orient):
    """Compute (long)((ray + orb_ray + orb_orient) * 4112) with the exact
    x87 model: the sum and product are in extended precision, then chopped
    to 32 bits via __ftol.

    ray:        binary64 (Python float)
    orb_ray:    binary32, stored as Python float holding the float32 value
    orb_orient: binary32, stored as Python float holding the float32 value
    """
    # The three operands are widened to extended (64-bit mantissa) on the x87
    # stack.  The sum is computed at extended precision, then the multiply by
    # 4112 (fild dword -> extended, fmul -> extended).  Then __ftol chops.
    s = ext(Fraction(ray)) + ext(Fraction(orb_ray)) + ext(Fraction(orb_orient))
    p = ext(s) * ext(Fraction(4112))
    return ftol32(p)


# ---------------------------------------------------------------------------
# 4.  build_surface - the machine
# ---------------------------------------------------------------------------

# objectschart byte packing: struct quadrant { 2-bit nr_of_objects, object0/1/2_class }
# bits 0-1: nr_of_objects, bits 2-3: obj0, bits 4-5: obj1, bits 6-7: obj2

def pack_quadrant(nr_of_objects, obj0_class, obj1_class, obj2_class):
    return ((nr_of_objects & 3) | ((obj0_class & 3) << 2) |
            ((obj1_class & 3) << 4) | ((obj2_class & 3) << 6))


# The initial objectschart fill byte: ROCKS=0 for all three class fields,
# nr_of_objects=0 (cleared by _fmemset at :1970).  All bits zero.
ROCKS_BYTE = pack_quadrant(0, ROCKS, ROCKS, ROCKS)   # == 0x00


class BuildSurface(object):
    """Models the integer/random-driven parts of build_surface().

    Buffers:
      surfacemap: PS_BYTES bytes (p_surfacemap, 200×200 heightmap)
      texture:    TXTR_BYTES bytes (txtr / p_background, 256×256 ground texture)
      objects:    OC_BYTES bytes (objectschart, one quadrant byte per cell)

    Generators:
      F: fast_random (the fast LCG)
      B: Borland random() (the brtl stream)
    """

    def __init__(self, keep_draws=False, ledger=True):
        self.smap = bytearray(PS_BYTES)
        self.txtr = bytearray(TXTR_BYTES)
        self.objs = bytearray(OC_BYTES)
        self.sv = np.frombuffer(self.smap, dtype=np.uint8)
        self.tv = np.frombuffer(self.txtr, dtype=np.uint8)
        self.ov = np.frombuffer(self.objs, dtype=np.uint8)
        self.F = Fast(keep_draws)
        self.B = Brt(keep_draws)
        self.rec = []
        self.ledger_on = ledger
        self.gates = {}

    # -- map accessors --------------------------------------------------

    def map_bytes(self):
        return bytes(self.smap)

    def txtr_bytes(self):
        return bytes(self.txtr)

    def obj_bytes(self):
        return bytes(self.objs)

    def mark(self, phase):
        if not self.ledger_on:
            return
        self.rec.append((phase, self.F.n, self.B.n, self.F.h, self.B.h,
                         fnv_bytes(self.smap), fnv_bytes(self.objs)))

    # ------------------------------------------------------------------
    # The seed setup and prologue — NOCTIS-1.CPP:1974-2053
    # ------------------------------------------------------------------

    def prologue(self, gseed, ip_type, sctype, albedo, latitude):
        """Run the build_surface prologue (lines 1974-2053).

        Seeds both generators from global_surface_seed, then draws:
          - cz = random(2), cx = random(100) for groundflares
          - fills objectschart with ROCKS (no draws)
          - tree params: flandom() draws from the brtl stream
          - rootshade/treeflares/leafflares: random() draws

        Returns the prologue globals set.
        """
        F, B = self.F, self.B
        # fast_srand (global_surface_seed) :1974
        F.srand(gseed)
        # srand (global_surface_seed) :1975 — NOTE: Borland srand takes int16
        B.srand(gseed)

        # groundflares :1983-1990
        cz = B.random(2, 1983)
        cx = B.random(100, 1984)
        groundflares = 0
        if cx > 97:
            groundflares = 2 + (2 * cz)
        if cx > 45 and cx < 55:
            if ip_type == 3 and latitude > 75:
                groundflares = 2 + (2 * cz)

        # objectschart ROCKS fill :1994-1998 — no draws, pure write
        # struct quadrant: nr_of_objects=0, obj0=obj1=obj2=ROCKS=0
        for i in range(OC_BYTES):
            self.objs[i] = ROCKS_BYTE

        # tree parameters — flandom() = (float)random(32767) * 0.000030518
        # The float values feed rendering params (not byte-graded here), but
        # the DRAWS consume from the brtl stream and must be counted.
        if latitude > 45:
            _ = B.random(32767, 2005)   # flandom() for treepeaking
        else:
            _ = B.random(32767, 2007)   # flandom() for treepeaking

        # rootshade :2010-2014
        _ = B.random(3, 2010)           # switch(random(3))

        # treeflares :2017-2022
        _ = B.random(30, 2017)          # switch(random(30))

        # leafflares :2024-2029
        _ = B.random(15, 2024)          # switch(random(15))

        # treescaling, treespreads, branchwidth, rootheight :2031-2034
        # each uses TWO flandom() calls (the formula is a - b pattern)
        _ = B.random(32767, 2031)       # flandom() * 3000
        _ = B.random(32767, 2031)       # flandom() * 1500
        _ = B.random(32767, 2032)       # flandom() * 0.50
        _ = B.random(32767, 2032)       # flandom() * 0.50
        _ = B.random(32767, 2033)       # flandom() * 0.15
        _ = B.random(32767, 2034)       # flandom()

        # type-3 groundflares bump :2042-2047
        if ip_type == 3:
            if sctype != 4 and sctype != 3:  # ICY=4, DESERT=3
                if B.random(4, 2044):
                    groundflares = 8

        self.groundflares = groundflares
        self.mark("PROLOGUE")
        return dict(groundflares=groundflares)

    # ------------------------------------------------------------------
    # The second seed bridge — NOCTIS-1.CPP:2051-2052
    # ------------------------------------------------------------------

    def seed_environment(self, landing_pt_lat, landing_pt_lon):
        """fast_srand/srand from landing_pt_lat * landing_pt_lon (:2051-2052).

        Both are 16-bit int; their product is 16-bit int (wraps).  Then:
          fast_srand((long)product) — sign-extended to 32 bits
          srand((int)product)       — stays 16 bits
        """
        lat = i16(landing_pt_lat)
        lon = i16(landing_pt_lon)
        prod = i16(lat * lon)             # 16-bit multiply, wraps
        self.F.srand(prod)                # fast_srand takes long; sign-ext
        self.B.srand(prod)                # srand takes int16
        self._env_seed = prod
        return prod

    # ------------------------------------------------------------------
    # rockyground — NOCTIS-1.CPP:1545-1559
    # ------------------------------------------------------------------

    def rockyground(self, roughness, rounding, level):
        """Produce una superficie più o meno accidentata.

            for (ptr = 0; ptr < 40000; ptr++)
                p_surfacemap[ptr] = random (roughness);
            smoothterrain (rounding);
            for (ptr = 0; ptr < 40000; ptr++) {
                if (p_surfacemap[ptr] >= abs(level))
                    p_surfacemap[ptr] += level;  (clamped to 127)
                else
                    p_surfacemap[ptr] = 0;
            }

        Pure integer / random-driven.  The `level` parameter is a Borland
        `char` (signed 8-bit); abs(level) is int.
        """
        B = self.B
        r = i16(roughness)
        rnd = i16(rounding)
        lvl = level & 0xFF
        if lvl & 0x80:
            lvl = lvl - 256             # sign-extend char
        alvl = abs(lvl)

        # fill with random(roughness)
        for i in range(PS_BYTES):
            self.smap[i] = B.random(r, 1548) & 0xFF

        # smooth
        self.smoothterrain(rnd)

        # level adjust
        for i in range(PS_BYTES):
            v = self.smap[i]
            if v >= alvl:
                v += lvl
                if v > 127:
                    v = 127
                self.smap[i] = v & 0xFF
            else:
                self.smap[i] = 0
        self.mark("ROCKYGROUND")

    # ------------------------------------------------------------------
    # smoothterrain — NOCTIS-1.CPP:1530-1543
    # ------------------------------------------------------------------

    def smoothterrain(self, rounding):
        """Smussa il profilo del terreno.

            while (rounding) {
                for (ptr = 0; ptr < 39799; ptr++) {
                    n  = p_surfacemap[ptr];
                    n += p_surfacemap[ptr + 1];
                    n += p_surfacemap[ptr + 200];
                    n += p_surfacemap[ptr + 201];
                    p_surfacemap[ptr] = n >> 2;
                }
                rounding--;
            }

        Note: the loop runs 0..39798 inclusive = 39799 iterations.  ptr+201
        peaks at 39999 = PS_BYTES-1, so no overrun.  Integer only.
        """
        rnd = rounding
        sm = self.smap
        while rnd > 0:
            for i in range(39799):
                n = sm[i] + sm[i + 1] + sm[i + 200] + sm[i + 201]
                sm[i] = (n >> 2) & 0xFF
            rnd -= 1

    # ------------------------------------------------------------------
    # The PLAINS noise add — NOCTIS-1.CPP:2280-2283
    # ------------------------------------------------------------------

    def plains_noise_add(self):
        """The p_surfacemap[ptr] += fast_random(3) at :2280-2282.

        LR-DIVERGENCE: niv-lr ASSIGNS here (= fast_random(3)) where vanilla
        ADDs (+= fast_random(3)).  This is the ground-path analogue of 7a's
        type-3 defect.  Vanilla ADDs; the mutation `ASSIGN` is the falsifier.
        """
        F = self.F
        for i in range(OC_BYTES):
            v = self.smap[i] + F.raw(3, 2282)
            if v > 255:
                v = 255           # unsigned char wrap — the store is a byte
            self.smap[i] = v & 0xFF
        self.mark("PLAINS_NOISE")

    # ------------------------------------------------------------------
    # The objectschart inclination pass — NOCTIS-1.CPP:2606-2615
    # ------------------------------------------------------------------

    def objects_inclination(self):
        """Distribute nr_of_objects based on terrain inclination (:2606-2615).

            for (ptr = 0; ptr < oc_bytes; ptr++) {
                incl  = abs(p_surfacemap[ptr] - p_surfacemap[ptr+1]);
                incl += abs(p_surfacemap[ptr] - p_surfacemap[ptr+200]);
                if (incl < 20) nr_of_objects = random(2);
                if (incl < 15) nr_of_objects = random(3);
                if (incl < 10) nr_of_objects = random(4);
            }

        NOTE: ptr+1 and ptr+200 can read up to OC_BYTES+199 = 40199, i.e.
        PAST the 40000-byte objectschart.  p_surfacemap IS 40000 bytes too,
        and ptr < oc_bytes means ptr peaks at 39999; ptr+200 peaks at 40199,
        which is 200 bytes past p_surfacemap.  In DOS this reads into the
        neighbouring farmalloc block — faithfully modelled as reading the
        surfacemap segment (which is exactly 40000 bytes here, so the read
        wraps into whatever follows).  This port reads zeroes past the map
        (the segment is 40000 bytes).  The discrepancy is noted in the exit
        report; it affects at most 200 cells at the south edge.
        """
        B = self.B
        sm = self.smap
        for i in range(OC_BYTES):
            n1 = sm[i + 1] if i + 1 < PS_BYTES else 0
            n2 = sm[i + 200] if i + 200 < PS_BYTES else 0
            incl = abs(sm[i] - n1) + abs(sm[i] - n2)
            nr = 0
            if incl < 20:
                nr = B.random(2, 2610)
            if incl < 15:
                nr = B.random(3, 2612)
            if incl < 10:
                nr = B.random(4, 2614)
            # nr_of_objects is bits 0-1; preserve the class bits
            self.objs[i] = (self.objs[i] & 0xFC) | (nr & 3)
        self.mark("OBJ_INCL")

    # ------------------------------------------------------------------
    # run_build - orchestrate a full build test case
    # ------------------------------------------------------------------

    def run_build(self, gseed, ip_type, sctype, albedo, latitude,
                  roughness, rounding, level, plains_noise):
        """Run the prologue + painters for a build test case.

        Returns dict with draw counts and hashes.  The buffers (smap, objs)
        are populated and can be read via map_bytes() / obj_bytes().

        After the prologue, re-seeds from gseed for the painters (in the real
        game this is landing_pt_lat * landing_pt_lon; here we use gseed to
        keep the corpus self-contained — the painter algorithm is under test).
        """
        # Reset generators and buffers
        self.F = Fast(self.F.keep)
        self.B = Brt(self.B.keep)
        self.smap = bytearray(PS_BYTES)
        self.objs = bytearray(OC_BYTES)
        self.rec = []
        self.gates = {}

        # Prologue
        out = self.prologue(gseed, ip_type, sctype, albedo, latitude)

        # Re-seed for painters (simplified: use gseed as env_seed)
        self.F.srand(gseed)
        self.B.srand(gseed & M16)

        # Rockyground
        self.rockyground(roughness, rounding, level)

        # Optional plains noise add
        if plains_noise:
            self.plains_noise_add()

        out["fast_n"] = self.F.n
        out["brtl_n"] = self.B.n
        out["fast_h"] = self.F.h
        out["brtl_h"] = self.B.h
        return out
