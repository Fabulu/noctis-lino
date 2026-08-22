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
import math
from fractions import Fraction

import numpy as np

from su_fp import ext, f32, ftol32

M_PI = math.pi
M_PI_2 = math.pi / 2

# Fast float32 rounder — uses struct pack/unpack instead of Fraction arithmetic.
# This is ~100x faster than su_fp.f32() and produces the same result for
# all values that don't overflow/underflow float32.
def _f32(x):
    return struct.unpack('<f', struct.pack('<f', float(x)))[0]

# Float-to-byte truncation (chop toward zero, keep low 8 bits)
def _ftob(y):
    return int(y) & 0xFF

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

    def __init__(self, keep_draws=False, ledger=True, allocation_gap=None):
        self.smap = bytearray(PS_BYTES)
        self.txtr = bytearray(TXTR_BYTES)
        self.objs = bytearray(OC_BYTES)
        if allocation_gap is None:
            self.allocation_gap = None
        else:
            self.allocation_gap = bytes(allocation_gap)
            if len(self.allocation_gap) != 16:
                raise ValueError("surface/object allocation gap must be 16 bytes")
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

    def _inclination_map_byte(self, index):
        if index < PS_BYTES:
            return self.smap[index]
        if self.allocation_gap is None:
            return 0
        offset = index - PS_BYTES
        if offset < len(self.allocation_gap):
            return self.allocation_gap[offset]
        object_index = offset - len(self.allocation_gap)
        if object_index < OC_BYTES:
            return self.objs[object_index]
        return 0

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
        self.liquid_water = 0
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

        NOTE: ptr+1 and ptr+200 can read through 199 bytes after the map.
        With an explicit 16-byte allocation gap, this models the original flat
        heap: first the gap, then the already-mutated prefix of the adjacent
        object chart.  The default remains the older zero-overread model so
        existing self-contained corpus cases retain their established boundary.
        """
        B = self.B
        sm = self.smap
        for i in range(OC_BYTES):
            n1 = self._inclination_map_byte(i + 1)
            n2 = self._inclination_map_byte(i + 200)
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
        self.txtr = bytearray(TXTR_BYTES)
        self.rec = []
        self.gates = {}

        # _fmemset (txtr, 16, 65535) :1968 — fills 65535 bytes, NOT 65536
        for i in range(65535):
            self.txtr[i] = 16

        # Prologue
        out = self.prologue(gseed, ip_type, sctype, albedo, latitude)

        # Re-seed for painters (simplified: use gseed as env_seed)
        self.F.srand(gseed)
        self.B.srand(gseed & M16)

        # Type switch (the rockyground/round_hill/etc. calls)
        self._switch(ip_type, sctype, albedo)

        # Post-switch: felisian crevasses + smoothing (:2583-2599)
        self._post_switch()

        # Objectschart inclination pass (:2606-2615)
        self._objects_inclination()

        # Liquid water check (:2620-2625)
        if self.liquid_water:
            for i in range(OC_BYTES):
                if not self.smap[i]:
                    self.objs[i] = self.objs[i] & 0xFC  # nr_of_objects = 0

        # Optional plains noise add (test harness feature for the ADD-vs-ASSIGN check)
        if plains_noise:
            self.plains_noise_add()

        out["fast_n"] = self.F.n
        out["brtl_n"] = self.B.n
        out["fast_h"] = self.F.h
        out["brtl_h"] = self.B.h
        return out

    # ------------------------------------------------------------------
    # FLOAT PAINTERS — NOCTIS-1.CPP:1494-1670
    # ------------------------------------------------------------------
    # All float vars (dx, dz, d, y, v) are float32: every assignment
    # rounds to 24-bit significand via f32().  Intermediate arithmetic
    # is in extended (64-bit) via ext().  Transcendental functions use
    # Python math (double, 53-bit) — close enough for most inputs; any
    # divergence from the hardware x87 is at sub-ULP-of-double level and
    # usually rounds to the same float32/byte.
    # The final byte store is ftol32 (chop) then & 0xFF.

    def round_hill(self, cx, cz, r, h, hmax, allowcanyons):
        """NOCTIS-1.CPP:1494-1528.  Canyon mirror at :1517 is VANILLA."""
        # Borland's `unsigned r` participates in both loop conditions before
        # x/z are converted back to signed int16 locals.  Thus a negative
        # cx-r or cz-r is a large uint16 and skips that loop wholesale; the
        # original does not clip such a hill against the top/left edges.
        # NOCTIS.EXE 0180DB..018293 confirms `jna` for both bounds.
        r = int(r) & 0xFFFF
        h_f = _f32(h)
        hmax_f = _f32(hmax)
        v = _f32(float(r) / M_PI_2)
        x = (int(cx) - r) & 0xFFFF
        x_end = (int(cx) + r) & 0xFFFF
        while x < x_end:
            sx = x if x < 0x8000 else x - 0x10000
            z = (int(cz) - r) & 0xFFFF
            z_end = (int(cz) + r) & 0xFFFF
            while z < z_end:
                sz = z if z < 0x8000 else z - 0x10000
                if -1 < sx < 200 and -1 < sz < 200:
                    dx = _f32(float(sx - cx))
                    dz = _f32(float(sz - cz))
                    d = _f32(math.sqrt(dx * dx + dz * dz))
                    y = _f32(math.cos(d / v) * h_f)
                    if y >= 0:
                        idx = 200 * sz + sx
                        y = _f32(y + float(self.smap[idx]))
                        if allowcanyons:
                            if y > 127:
                                y = _f32(254.0 - y)    # LR-REJECTED canyon mirror
                        else:
                            if y > hmax_f:
                                y = hmax_f
                        self.smap[idx] = _ftob(y)
                z = (z + 1) & 0xFFFF
            x = (x + 1) & 0xFFFF

    def std_crater(self, mapbuf, cx, cz, r, lim_h, h_factor, h_raiser, align):
        """NOCTIS-1.CPP:1561-1587.  Uses sqrt, sin, pow."""
        h = float(r) * float(h_factor)
        r = abs(r)
        fr = float(r)
        for x in range(cx - r, cx + r):
            for z in range(cz - r, cz + r):
                if -1 < x < align and -1 < z < align:
                    dx = float(x - cx)
                    dz = float(z - cz)
                    d = math.sqrt(dx * dx + dz * dz)
                    if d <= fr:
                        y = math.sin(M_PI * (d / fr)) * h
                        if h_raiser != 1.0:
                            y = math.pow(y, float(h_raiser)) if y > 0 else 0.0
                        idx = align * z + x
                        y += mapbuf[idx]
                        if y < 0:
                            y = 0
                        if y > lim_h:
                            y = lim_h
                        mapbuf[idx] = int(y) & 0xFF

    def srf_darkline(self, mapbuf, length, x_trend, z_trend, align):
        """NOCTIS-1.CPP:1589-1603.  Pure integer random walk."""
        B = self.B
        fx = B.random(align, 1592)
        fz = B.random(align, 1592)
        mapsize = align * align
        while length:
            fx += B.random(3, 1597) + x_trend
            fz += B.random(3, 1598) + z_trend
            # DOS `unsigned` is 16-bit.  The long expression is narrowed on
            # assignment, so a wandering line wraps through the 64 KiB map.
            location = (align * fz + fx) & 0xFFFF
            if 0 < location < mapsize:
                mapbuf[location] >>= 1
            length -= 1

    def felisian_srf_darkline(self, mapbuf, length, x_trend, z_trend, align):
        """NOCTIS-1.CPP:1605-1633."""
        B = self.B
        fx = B.random(align, 1608)
        fz = B.random(align, 1608)
        mapsize = align * align
        deviation = B.random(25, 1613) - 50
        variability = 2 + B.random(10, 1614)
        while length:
            fx += B.random(3, 1616) + x_trend
            fz += B.random(3, 1617) + z_trend
            deviation += B.random(variability, 1618) - (variability >> 1)
            location = (align * fz + fx) & 0xFFFF
            if 0 < location < mapsize:
                peak = mapbuf[location] + deviation
                if peak < 0:
                    peak = 0
                if peak > 127:
                    peak = 127
                for off in (0, 1, -1, align, -align):
                    p = location + off
                    if 0 <= p < len(mapbuf):
                        mapbuf[p] = peak & 0xFF
            length -= 1

    def smoothterrain_n(self, passes):
        """Wrapper to call smoothterrain from type-switch context."""
        self.smoothterrain(passes)

    def asterism(self, mapbuf, x, y, base, variation, density, size, align):
        """NOCTIS-1.CPP:1635-1670.  Grass tuft painter — uses cos, sin.

        EVERY float variable (ad, ang, shift_d, var, color) is stored as
        float32 in the C source. Each assignment rounds to 24-bit significand.
        Missing any of these float32 stores changes loop iteration counts
        (the LOOP91 hazard), cascading through all subsequent brtl draws.
        """
        if density <= 0:
            return
        B = self.B
        ad = _f32(M_PI * 2.0 / float(density))
        ang = _f32(0.0)
        while ang < M_PI * 2.0:
            # shift_d = (float)random(1000) / 1000  →  float32 store
            # shift_d *= size  →  float32 store
            sd = _f32(_f32(float(B.random(1000, 1652)) / 1000.0) * float(size))
            if sd >= 1.0:
                # var = (float)variation / shift_d  →  float32 store
                var = _f32(float(variation) / sd)
                # color = base  (float)
                color = _f32(float(base))
                while sd > 0:
                    shift_x = int(math.cos(ang) * sd + x)
                    shift_y = int(math.sin(ang) * sd + y)
                    if shift_x > 0 and shift_y > 0 and shift_x < align and shift_y < align:
                        shift_p = shift_y * align + shift_x
                        c = int(color)
                        if 0 <= shift_p < len(mapbuf):
                            mapbuf[shift_p] = c & 0xFF
                    # color += var  →  float32 store
                    color = _f32(color + var)
                    # shift_d--  →  float32 store
                    sd = _f32(sd - 1.0)
            # ang += ad  →  float32 store
            ang = _f32(ang + ad)

    def _post_switch(self):
        """Post-switch code at :2583-2599 — felisian crevasses + smoothing."""
        B = self.B
        n = B.random(5, 2583)
        if n:
            while n:
                length = B.random(500, 2586)
                self.felisian_srf_darkline(self.smap, length, -1, -1, 200)
                n -= 1
            sm = self.smap
            for i in range(200, 38800):
                v = sm[i] + sm[i-1] + sm[i+1] + sm[i-200] + sm[i+200]
                sm[i] = (v // 5) & 0xFF

    def _objects_inclination(self):
        """Objectschart inclination pass at :2606-2615."""
        B = self.B
        sm = self.smap
        for i in range(OC_BYTES):
            v1 = self._inclination_map_byte(i + 1)
            v2 = self._inclination_map_byte(i + 200)
            incl = abs(sm[i] - v1) + abs(sm[i] - v2)
            nr = 0
            if incl < 20:
                nr = B.random(2, 2610)
            if incl < 15:
                nr = B.random(3, 2612)
            if incl < 10:
                nr = B.random(4, 2614)
            self.objs[i] = (self.objs[i] & 0xFC) | (nr & 3)

    def _ocean_terrain(self, albedo):
        """NOCTIS-1.CPP:2151-2204.  The OCEAN sub-case of type 3.

        For albedo > 20: goto revert (PLAINS terrain with waswet=1).
        For albedo <= 20: island/shore code, possibly goto addtrees.
        """
        B = self.B
        waswet = False

        if albedo > 20:
            # goto revert — PLAINS terrain with waswet=1
            waswet = True
            self._plains_terrain(waswet=True)
            return

        # albedo <= 20
        if albedo > 16:
            # rockyground check
            if B.random(2, 2167):
                _rnd = B.random(2, 2168)
                self.rockyground(10, _rnd, -5)

        # Island check
        if not B.random(3, 2174):
            # Island code — two round_hills + goto addtrees
            cx = B.random(100, 2175) + 50
            cz = B.random(100, 2176) + 50
            # First round_hill — right-to-left:
            # round_hill(cx+random(15), cz+random(15), random(100)+25, random(10)+1, 0, 1)
            _h1 = float(B.random(10, 2180) + 1)
            _r1 = B.random(100, 2179) + 25
            _czoff1 = B.random(15, 2178)
            _cxoff1 = B.random(15, 2177)
            self.round_hill(cx + _cxoff1, cz + _czoff1, _r1, _h1, 0.0, True)
            # Second round_hill — right-to-left:
            # round_hill(cx, cz, random(100)+25, random(100)+1, 0, 1)
            _h2 = float(B.random(100, 2183) + 1)
            _r2 = B.random(100, 2182) + 25
            self.round_hill(cx, cz, _r2, _h2, 0.0, True)
            waswet = True
            # goto addtrees
            self._addtrees_and_texture(waswet)
            return

        # Full ocean: sandy texture, rock params, liquid_water=1
        # (not reached for the capture, but implemented for completeness)
        n = B.random(30, 2189) + 2
        ptr = 65535
        while ptr:
            self.txtr[ptr] = B.random(n, 2192) & 0xFF
            ptr -= 1
        _ = B.random(75, 2196); _ = B.random(25, 2197)
        if B.random(3, 2198):
            pass  # rockdensity = 31
        self.liquid_water = 1

    def _addtrees_and_texture(self, waswet):
        """NOCTIS-1.CPP:2235-2294.  Shared addtrees+texture+noise code."""
        B = self.B
        F = self.F
        # Vegetation assignment
        n = B.random(6, 2237)
        for i in range(OC_BYTES):
            h = self.smap[i]
            cls = h // 25
            byte = self.objs[i]
            nr = byte & 0x03
            obj0 = (byte >> 2) & 3
            if cls == 0:
                self.objs[i] = nr | (obj0 << 2) | (VEGET << 4) | (VEGET << 6)
            elif cls == 1:
                self.objs[i] = nr | (obj0 << 2) | (VEGET << 4) | (TREES << 6)
            elif cls == 2:
                self.objs[i] = nr | (obj0 << 2) | (TREES << 4) | (TREES << 6)
            else:
                self.objs[i] = nr | (TREES << 2) | (TREES << 4) | (TREES << 6)
        # Grass texture
        n = B.random(15, 2256) + 2
        ptr = 65535
        while ptr:
            self.txtr[ptr] = B.random(n, 2259) & 0xFF
            ptr -= 1
        # Asterism grass tufts
        n = 100 + B.random(500, 2262)
        while n:
            _sz = B.random(15, 2266) + 6
            _dn = B.random(25, 2265) + 6
            _var = B.random(16, 2265)
            _base = B.random(16, 2264)
            _y = B.random(256, 2264)
            _x = B.random(256, 2264)
            self.asterism(self.txtr, _x, _y, _base, _var, _dn, _sz, 256)
            n -= 1
        # Noise add — LR ASSIGN-vs-ADD defect
        # if (!waswet || (waswet && !random(5)))
        do_noise = False
        if not waswet:
            do_noise = True
        else:
            if not B.random(5, 2281):
                do_noise = True
        if do_noise:
            for i in range(OC_BYTES):
                v = self.smap[i] + F.raw(3, 2282)
                if v > 255:
                    v = 255
                self.smap[i] = v & 0xFF
        # Rock params
        _ = B.random(200, 2285); _ = B.random(200, 2286)
        _ = B.random(2, 2287)

    def _plains_terrain(self, waswet=False):
        """NOCTIS-1.CPP:2207-2294.  The PLAINS sub-case of type 3."""
        B = self.B
        if B.random(2, 2213):
            ptr = B.random(50, 2215) + 5
            while ptr:
                _h = float(B.random(30, 2219) + 1)
                _r = B.random(200, 2219) + 1
                _cz = B.random(200, 2218)
                _cx = B.random(200, 2217)
                self.round_hill(_cx, _cz, _r, _h, 0.0, True)
                ptr -= 1
        else:
            ptr = B.random(25, 2226) + 10
            while ptr:
                _h = float(B.random(100, 2230) + 1)
                _r = B.random(200, 2230) + 1
                _cz = B.random(200, 2229)
                _cx = B.random(200, 2228)
                self.round_hill(_cx, _cz, _r, _h, 0.0, True)
                ptr -= 1
        self._addtrees_and_texture(waswet)

    # ------------------------------------------------------------------
    # DESERT — NOCTIS-1.CPP:2296-2316 (sctype=3)
    # ------------------------------------------------------------------

    def _desert_terrain(self):
        """The DESERT sub-case of type 3 (sctype=3), :2296-2316.

        One rockyground tuned for dunes (higher relief + more smoothing
        yields wind-rounded shapes), then a coarse-grained sand texture.
        Sets rockdensity=0, gtx=1 (flags, no draws).  NO quartz check and
        NO goto similar: the DESERT arm breaks directly out of the inner
        switch.  (The shared quartz check at :2385 is not modelled here,
        matching the existing OCEAN/PLAINS handling.)
        """
        B = self.B
        n = B.random(100, 2304)
        self.rockyground(50 + n, 5 + (n >> 4), 0)
        # T_SCALE = 128 (rendering param, not byte-graded)
        ptr = 65535
        while ptr:
            self.txtr[ptr] = B.random(32, 2310) & 0xFF
            ptr -= 1
        # rockdensity = 0; gtx = 1  (flags, no draws)

    # ------------------------------------------------------------------
    # ICY — NOCTIS-1.CPP:2318-2380 (sctype=4)
    # ------------------------------------------------------------------

    def _icy_terrain(self):
        """The ICY sub-case of type 3 (sctype=4), :2318-2380.

        Four orography variants via switch(random(4)) — flat snowfield,
        bare permanent ice, snow hills, or icebergs — setting snowy/frosty
        accordingly.  Then three rock-param draws (:2350-2352) and the
        shared texture processing at the `similar:` label (:2353-2379),
        which is also reached by type 8 via `goto similar` (:2579).
        """
        B = self.B
        snowy = False
        frosty = False
        sel = B.random(4, 2322)
        if sel == 0:
            # praticamente piana, distesa nevosa
            self.rockyground(15, 5, 0)
            snowy = True
        elif sel == 1:
            # brulla distesa di ghiaccio permanente
            # rockyground(10+random(10), 1+random(2), 0)
            # Borland R-to-L: arg2=1+random(2) drawn BEFORE arg1=10+random(10)
            _rounding = 1 + B.random(2, 2330)
            _roughness = 10 + B.random(10, 2330)
            self.rockyground(_roughness, _rounding, 0)
            frosty = True
        elif sel == 2:
            # colline di neve
            ptr = B.random(50, 2334) + 50
            while ptr:
                # round_hill(random(200), random(200), random(200)+1, random(75)+1, 0, 1)
                # Borland R-to-L draws: h=random(75), r=random(200), cz=random(200), cx=random(200)
                _h = float(B.random(75, 2339) + 1)
                _r = B.random(200, 2338) + 1
                _cz = B.random(200, 2337)
                _cx = B.random(200, 2336)
                self.round_hill(_cx, _cz, _r, _h, 0.0, True)
                ptr -= 1
            snowy = True
        else:  # sel == 3 — e anche icebergs
            # rockyground(50+random(50), 3+random(3), -(random(40)+20))
            # Borland R-to-L: level arg=-(random(40)+20), then rounding=3+random(3),
            # then roughness=50+random(50)
            _level = -(B.random(40, 2345) + 20)
            _rounding = 3 + B.random(3, 2345)
            _roughness = 50 + B.random(50, 2345)
            self.rockyground(_roughness, _rounding, _level)
            frosty = True
        # qualche sasso? raro e grosso. (rock params — draws only, not byte-graded)
        _ = B.random(500, 2350)   # rockscaling = 200 + random(500)
        _ = B.random(250, 2351)   # rockpeaking = 150 + random(250)
        _ = B.random(2, 2352)     # rockdensity = 2 * random(2)
        # shared texture code at the `similar:` label
        self._similar_texture(snowy, frosty)

    # ------------------------------------------------------------------
    # similar: label — NOCTIS-1.CPP:2353-2379 (shared texture code)
    # ------------------------------------------------------------------
    # Reached by ICY (sctype=4) falling through past the rock-param draws,
    # and by type 8 via `goto similar` at :2579 (which sets snowy/frosty at
    # :2574-2578 first).  Kept as a helper so both callers run the same code.

    def _similar_texture(self, snowy, frosty):
        """The `similar:` label, :2353-2379.

        If snowy or frosty: fill txtr with random(16+random(16)), then run
        1+random(3) box-blur passes over it (a 2D averaging filter).  If
        frosty: additionally set T_SCALE and draw random(250) srf_darkline
        darkening walks across the texture.
        """
        B = self.B
        if snowy or frosty:
            # T_SCALE = 32 (rendering param, not byte-graded)
            n = B.random(16, 2355) + 16
            ptr = 65535
            while ptr:
                self.txtr[ptr] = B.random(n, 2358) & 0xFF
                ptr -= 1
            n = 1 + B.random(3, 2361)
            while n:
                ptr = 65535 - 257     # = 65278; reads up to txtr[65278+257]=txtr[65535]
                while ptr:
                    acc = (self.txtr[ptr] + self.txtr[ptr + 1]
                           + self.txtr[ptr + 256] + self.txtr[ptr + 257])
                    self.txtr[ptr] = (acc >> 2) & 0xFF
                    ptr -= 1
                n -= 1
        if frosty:
            # T_SCALE = 16 + random(48) (rendering param, not byte-graded)
            n = B.random(250, 2374)
            while n:
                # srf_darkline(txtr, 100+random(200), -random(2), 0, 256)
                # Borland R-to-L: x_trend=-random(2) drawn BEFORE length=100+random(200)
                _x_trend = -B.random(2, 2376)
                _length = 100 + B.random(200, 2376)
                self.srf_darkline(self.txtr, _length, _x_trend, 0, 256)
                n -= 1

    # ------------------------------------------------------------------
    # THE TYPE SWITCH — NOCTIS-1.CPP:2054-2581
    # ------------------------------------------------------------------
    # Each arm models the random draws in EXACT source order, then calls
    # the painters.  p_surfacemap ops are byte-graded; txtr ops keep the
    # draw streams synchronized.  After _fmemset(txtr, 16, 65535) at
    # :1968, txtr[0..65534]=16, txtr[65535]=0.

    def _switch(self, ip_type, sctype, albedo):
        F, B = self.F, self.B
        if ip_type == 1:
            n = B.random(5, 2062)
            if n <= 2:
                self.rockyground(25, 4 + B.random(4, 2063), 0)
            if n == 3:
                self.rockyground(5 + B.random(5, 2064), 1, 1)
            if n == 4:
                self.rockyground(10, 2, -B.random(5, 2065))
            n = B.random(48, 2067) + 32 - albedo
            if n > 30: n = 30
            if n < 0: n = 0
            while n:
                hf = float(B.random(32, 2073)) * 0.01
                hr = float(B.random(20, 2073) + 5) * 0.075
                _r = B.random(50, 2074) + 5
                _cz = B.random(200, 2074)
                _cx = B.random(200, 2074)
                self.std_crater(self.smap, _cx, _cz, _r, 127, hf, hr, 200)
                n -= 1
            n = B.random(48, 2078) + 64 - albedo
            if n < 0: n = 0
            hf = 0.35
            while n:
                cx = B.random(200, 2082)
                cz = B.random(200, 2083)
                cr = B.random(32, 2084) + 10
                self.std_crater(self.txtr, cx, cz, cr, 31, hf, 1.0, 256)
                if cr % 2:
                    self.std_crater(self.txtr, cx + cr // 3, cz + cr // 3,
                                    -cr, 31, hf, 1.0, 256)
                n -= 1
            n = B.random(100, 2089)
            while n:
                self.srf_darkline(self.txtr, B.random(1000, 2091), -1, -1, 256)
                n -= 1
            # rock params (draws only, not byte-graded)
            _ = B.random(2, 2095); _ = B.random(2, 2095)
            _ = B.random(500, 2096); _ = B.random(300, 2097)

        elif ip_type == 3:
            # Habitable — sub-switch on sctype (OCEAN/PLAINS/DESERT/ICY)
            # The sctype is determined by cplx_planet_viewpoint (:3634-3646)
            # which runs BEFORE build_surface and draws from brtl.
            # For the capture site (srand(0)): random(100)=0 <= 5, so
            # sctype = random(4)+1 = 0+1 = 1 = OCEAN.
            # Live RAM pins albedo at 40, so build_surface's OCEAN case takes
            # `goto revert` into the shared PLAINS terrain with waswet=1.
            # The resulting texture is byte-exact against all 65,536 captured
            # NIV+ bytes.
            if sctype == 1:
                self._ocean_terrain(albedo)
            elif sctype == 2:
                self._plains_terrain()
            elif sctype == 3:
                self._desert_terrain()
            elif sctype == 4:
                self._icy_terrain()

        elif ip_type == 2:
            self.rockyground(10, 1, 0)
            n = albedo + B.random(100, 2102)
            while n:
                _h = float(B.random(50, 2108) + 10)
                _r = B.random(100, 2107) + 50
                _cz = B.random(200, 2106)
                _cx = B.random(200, 2105)
                self.round_hill(_cx, _cz, _r, _h, 0.0, True)
                n -= 1
            br = B.random(2, 2112)
            if br == 0:
                n = albedo + B.random(200, 2114) - B.random(100, 2114)
                hf = float(B.random(10, 2115)) * 0.02
                if n < 0: n = 0
                while n:
                    cx = B.random(256, 2118)
                    cz = B.random(256, 2119)
                    cr = B.random(8, 2120) + 8
                    if B.random(2, 2121):
                        self.std_crater(self.txtr, cx, cz, -cr, 31, hf, 1.0, 256)
                    else:
                        self.std_crater(self.txtr, cx, cz, cr, 31, hf, 1.0, 256)
                    n -= 1
            else:
                n = albedo + B.random(500, 2129)
                ptr = B.random(2000, 2130)
                while n:
                    self.srf_darkline(self.txtr, B.random(ptr, 2132), -1, -1, 256)
                    n -= 1
            _ = B.random(500, 2137); _ = B.random(2, 2138)
            _ = B.random(150, 2139)

        elif ip_type == 4:
            _level = -B.random(5, 2401)
            _rounding = 3 + B.random(3, 2401)
            self.rockyground(15, _rounding, _level)
            n = B.random(15, 2405)
            while n:
                hf = float(B.random(15, 2407) + 7)
                # hr = hf * (flandom()*3.5+3.5)
                hr = hf * (float(B.random(32767, 2408)) * 0.000030518 * 3.5 + 3.5)
                ht = hr * (float(B.random(32767, 2409)) * 0.000030518 * 0.2 + 0.3)
                if ht > 127: ht = 127
                _cz = B.random(200, 2412)
                _cx = B.random(200, 2411)
                self.round_hill(_cx, _cz, int(hf), hr, ht, False)
                n -= 1
            self.smoothterrain(1 + B.random(2, 2419))
            n = 64 - albedo
            hf = 0.25
            while n:
                cx = B.random(150, 2430) + 25
                cz = B.random(150, 2431) + 25
                cr = B.random(10, 2432) + 15
                self.std_crater(self.txtr, cx, cz, -cr, 31, hf, 1.0, 256)
                n -= 1
            _ = B.random(200, 2439); _ = B.random(2, 2440)
            _ = B.random(200, 2441)

        elif ip_type == 5:
            if B.random(2, 2451):
                n = 5 + B.random(10, 2452)
                if albedo > 48: n //= 2
                self.rockyground(n, 1, 0)
            else:
                n = 15 + B.random(32, 2457)
                if albedo > 48: n //= 2
                self.rockyground(n, 1, -B.random(24, 2459))
            n = B.random(68, 2462) - albedo
            if n > 10: n = 10
            if n < 1: n = 1
            while n:
                hf = float(B.random(5, 2466)) * 0.015
                hr = float(B.random(10, 2466) + 10) * 0.27
                _r = B.random(35, 2469) + 5
                _cz = B.random(200, 2469)
                _cx = B.random(200, 2468)
                self.std_crater(self.smap, _cx, _cz, _r, 127, hf, hr, 200)
                n -= 1
            _ = B.random(400, 2476); _ = B.random(250, 2477)
            _ = B.random(2, 2478)
            if albedo > 40 and albedo <= 50:
                _ = B.random(2, 2489); _ = B.random(5, 2490)
                _ = B.random(5, 2490)
                hf = float(B.random(5, 2490)) * 0.01
                hr = float(B.random(5, 2491) + 5) * 0.5
                _r = 100 + B.random(10, 2494)
                _cz = 90 + B.random(20, 2493)
                _cx = 90 + B.random(20, 2493)
                self.std_crater(self.smap, _cx, _cz, _r, 127, hf, hr, 200)
            ptr = B.random(1500, 2498) + 500
            n = albedo * 5
            while n:
                self.srf_darkline(self.txtr, B.random(ptr, 2501), -1, -1, 256)
                n -= 1

        elif ip_type == 7:
            self.rockyground(10 - (albedo // 8), 0, 20 + B.random(100, 2507))
            n = albedo - B.random(albedo, 2508) + 10
            while n:
                self.felisian_srf_darkline(self.smap, B.random(500, 2510),
                                           -1, -1, 200)
                n -= 1
            n = albedo + B.random(200, 2513) - B.random(100, 2513)
            if n < 0: n = 0
            while n:
                cx = B.random(192, 2515) + 32
                cz = B.random(192, 2516) + 32
                cr = B.random(16, 2517) + 16
                self.std_crater(self.txtr, cx, cz, -cr, 31, 0.15, 1.0, 256)
                n -= 1
            n = (albedo + B.random(100, 2521) - B.random(50, 2521)) // 2
            if n < 0: n = 0
            while n:
                _z_trend = -B.random(2, 2523)
                _x_trend = -B.random(2, 2523)
                _length = B.random(100, 2523)
                self.srf_darkline(self.txtr, _length, _x_trend, _z_trend, 256)
                n -= 1
            _ = B.random(400, 2527); _ = B.random(200, 2528)
            _ = B.random(2, 2529)

        elif ip_type == 8:
            if albedo < 20:
                ptr = 100 - albedo
                while ptr:
                    hr = float(B.random(300, 2538))
                    _r = B.random(5, 2541) + 2
                    _cz = B.random(150, 2540) + 25
                    _cx = B.random(150, 2539) + 25
                    self.round_hill(_cx, _cz, _r, hr + 1, 127, False)
                    ptr -= 1
                self.smoothterrain(2 + B.random(3, 2545))
            ptr = (100 - albedo) * 2
            while ptr:
                _h = float(B.random(25, 2553) + 1)
                _r = B.random(25, 2553) + 1
                _cz = B.random(200, 2552)
                _cx = B.random(200, 2551)
                self.round_hill(_cx, _cz, _r, _h, 0.0, True)
                ptr -= 1
            _ = B.random(300, 2560); _ = B.random(300, 2561)
            _ = B.random(2, 2562)
            if albedo > 40:
                _ = B.random(2, 2569)
                self.smoothterrain(1 + B.random(10, 2570))
