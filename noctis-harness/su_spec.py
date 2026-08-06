r"""su_spec.py - Python reference for Noctis IV's surface(), Wave 7a.

PROVENANCE, WHICH IS THE POINT OF THIS FILE
-------------------------------------------
Transliterated from the DOS sources only:

    C:\programmieren\noctis\niv-plus\source\NOCTIS-0.CPP
        surface()          :4766-5196
        the painters       :4488-4756  (spot permanent_storm crater band wave
                                        fracture volcano contrast randoface
                                        negate crater_juice cirrus atm_cyclon
                                        storm)
        ssmooth/lssmooth   :4380-4441
        psmooth_grays      :480-510
        pclear             :332-360
        fast_srand/fast_random/ranged_fast_random  :1075-1107
        shade              :1151-1199
        tavola_colori      :179-241
    PITAGORA.H:136         const double deg = M_PI/180

It is NOT derived from noctis-iv-lr, which PORTPLAN disqualifies as an oracle
for this function (type-3 land noise ASSIGNs where vanilla ADDs; type 9 paints
the offscreen page; lssmooth smooths one pixel fewer).  Where the two differ
this file implements VANILLA, and the divergence is called out in a comment
tagged  LR-DIVERGENCE.

It is NOT derived from su_ref.c either: su_ref.c is written from the same DOS
text by a separate pass, and the two are compared, not merged.

The brtl LCG comes from brtl_oracle.py, which was disassembled out of
NOCTIS.EXE (Wave 1).  fast_random is re-implemented here from the inline
assembly rather than imported, so a bug in one file cannot hide in the other;
su_check.py asserts the two agree.

BUFFER MODEL (Wave 5 / BUFFERMAP 4.1)
-------------------------------------
farmalloc hands back seg:0004.  Every asm block in surface() does
`les di, dword ptr p_background` and then does 16-bit offset arithmetic, so a
faithful model needs the four-byte lead-in and 16-bit wraparound.  `pseg` is
therefore a 65536-byte segment window and the 64,800-byte map lives at
pseg[4:64804].  wave()'s mysterious `add ax, 4` (NOCTIS-0.CPP:4593) is that
same offset being re-applied after `mov di, ax` destroys the loaded one - so
there is NO pixel skew.  objectschart is modelled the same way in `oseg`.
"""

import math
import struct
import sys
from fractions import Fraction

import numpy as np

from brtl_oracle import Brtl
from su_fp import (DEG, TWO_PI, Fraction as _Fr, d2u16, ext, f32, fistp16,
                   ftol32, round_to_bits)

M16 = 0xFFFF
M32 = 0xFFFFFFFF
PB = 4                      # offset(p_background) inside its far heap block
OV = 4                      # offset(objectschart)
MAPBYTES = 64800
OVLBYTES = 32400

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
    """C integer division: truncate toward zero."""
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q


def crem(a, b):
    return a - cdiv(a, b) * b


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

    def rfr(self, rng, site=0):
        """ranged_fast_random - NOCTIS-0.CPP:1103.  Used NOWHERE else in the
        game, which is why it is the type switch's own generator.  rng is a
        positive literal at every call site, so crem(v, rng) never divides by
        zero; the dead `if rng <= 0: rng = 1` guard (w5audit's one Wave 7a
        finding) was removed by the 7a remediation rather than carried as a
        pinned OPEN."""
        v = self.random(0x7FFF)
        out = i16(crem(v, rng))
        self.n += 1
        self.h = fnv(self.h, out)
        if self.keep:
            self.log.append((site, rng, out))
        return out

    def raw(self, mask, site=0):
        v = self.random(mask)
        self.n += 1
        self.h = fnv(self.h, v)
        if self.keep:
            self.log.append((site, mask, v))
        return v


class Brt(object):
    """Borland random(), counted.  The generator itself is brtl_oracle.Brtl,
    disassembled from NOCTIS.EXE in Wave 1 and untouched here."""

    __slots__ = ("g", "n", "h", "log", "keep")

    def __init__(self, keep=False):
        self.g = Brtl()
        self.n = 0
        self.h = FNV_OFF
        self.log = []
        self.keep = keep

    def srand(self, v):
        self.g.srand(v)

    def random(self, n, site=0):
        v = self.g.random(i16(n))
        self.n += 1
        self.h = fnv(self.h, v & M32)
        if self.keep:
            self.log.append((site, n, v))
        return v


# ---------------------------------------------------------------------------
# 2.  The `a` accumulator sequences, precomputed in x87 extended precision.
# ---------------------------------------------------------------------------

_EXT_DEG = ext(DEG)
_STEP4 = ext(_Fr(4) * _EXT_DEG)       # 4*deg : int*double, exact in extended
_STEP6 = ext(_Fr(6) * _EXT_DEG)


def _accum(a0, step, stop=None, count=None):
    """a_{k+1} = f32( ext(a_k) + step ), the float32 global round-tripped
    through memory that Borland emits for `a += 4*deg`."""
    out = [a0]
    a = a0
    if count is None:
        while a < stop:
            a = f32(ext(_Fr(a) + step))
            out.append(a)
        return out[:-1]                # the last one failed the test
    for _ in range(count):
        a = f32(ext(_Fr(a) + step))
        out.append(a)
    return out


# for (a=0; a<2*M_PI; a+=4*deg)   -- crater, volcano, permanent_storm, storm
ASEQ4 = _accum(0.0, _STEP4, stop=TWO_PI)

_A6CACHE = {}


def aseq6(k, n):
    """atm_cyclon: a = ranged_fast_random(360) * deg, then a += 6*deg."""
    cur = _A6CACHE.get(k)
    if cur is None or len(cur) < n + 1:
        a0 = f32(ext(_Fr(k) * _EXT_DEG))
        cur = _accum(a0, _STEP6, count=max(n, 256))
        _A6CACHE[k] = cur
    return cur


_KDEG = {}


def kdeg(k):
    """ext(k * deg) for the integer k that fracture() adds each step."""
    v = _KDEG.get(k)
    if v is None:
        v = ext(_Fr(k) * _EXT_DEG)
        _KDEG[k] = v
    return v


# ---------------------------------------------------------------------------
# 3.  The machine.
# ---------------------------------------------------------------------------

PLANET_RGB_AND_VAR = [
    60, 30, 15, 20,   40, 50, 40, 25,   32, 32, 32, 32,
    16, 32, 48, 40,   32, 40, 32, 20,   32, 32, 32, 32,
    32, 32, 32, 32,   32, 40, 48, 24,   40, 40, 40, 30,
    50, 25, 10, 20,   40, 40, 40, 40,
]


class Surface(object):

    def __init__(self, keep_draws=False, ledger=True):
        self.pseg = bytearray(65536)
        self.oseg = bytearray(65536)
        self.pv = np.frombuffer(self.pseg, dtype=np.uint8)
        self.ov = np.frombuffer(self.oseg, dtype=np.uint8)
        self.tmppal = bytearray(768)
        self.F = Fast(keep_draws)
        self.B = Brt(keep_draws)
        self._cj_zeros = 0  # crater() ray-zero count; feeds the derived cj_brtl (A5)
        self.QUADWORDS = 16000
        # the painter parameter globals - NOCTIS-0.CPP:4444
        self.c = self.gr = self.r = self.g = self.b = 0
        self.cr = self.cx = self.cy = 0
        self.a = 0.0                    # float
        self.kfract = 2.0               # float
        self.lave = 0
        self.crays = 0
        self.px = self.py = 0           # unsigned
        self.vptr = 0                   # unsigned
        self.rec = []
        self.ledger_on = ledger
        self.notes = []
        self._a6 = [0.0]
        self._seed = 0
        # `secs` at the instant surface() ran is NOT recoverable from the
        # captured artefact (recon C section 4).  Every use of it inside the
        # switch has the shape  ((long)(k*secs) / D) % 360  with D drawn from
        # the FAST stream, so the ONLY thing the map can see is the single
        # integer (long)(k*secs).  _secs_scaled substitutes that integer
        # directly so a search runs over integers, not over a real.  When it
        # is None the value is computed from `secs` exactly as the source does.
        self._secs_scaled = None
        self.secs_sites = []
        self.stop_after_switch = False
        self.gates = {}

    # -- ledger ------------------------------------------------------------

    def mark(self, phase):
        if not self.ledger_on:
            return
        self.rec.append((
            phase, self.F.n, self.B.n, self.F.h, self.B.h,
            fnv_bytes(self.pseg[PB:PB + MAPBYTES]),
            fnv_bytes(self.oseg[OV:OV + OVLBYTES]),
        ))

    # -- map accessors -----------------------------------------------------

    def map_bytes(self):
        return bytes(self.pseg[PB:PB + MAPBYTES])

    def ovl_bytes(self):
        return bytes(self.oseg[OV:OV + OVLBYTES])

    # ------------------------------------------------------------------
    # smoothing / clearing.  NOCTIS-0.CPP:4380-4441, :332, :480
    # ------------------------------------------------------------------

    def ssmooth(self):
        """4x(1x4) box filter, stride 360.  The four dword loads are added as
        32-bit quantities BEFORE the 0xFCFCFCFC mask, so carries really do
        cross lane boundaries; that is the behaviour, not a bug."""
        n = ((self.QUADWORDS << 2) & M16)
        n = (n - ((360 << 2) & M16)) & M16
        v = self.pv
        base = PB + 360
        # Chunking is exact only up to 357.  Iteration i writes flat 360+i and
        # reads flat [i..i+3], so it consumes the bytes written by iterations
        # i-360 .. i-357; those must already have been applied, which forces
        # the chunk length to be at most 357.  (Chunking by 360 leaves the last
        # three iterations of every chunk reading stale bytes -- measured as
        # 196/614/3724 wrong pixels on the type 7/4/0 captures.)
        step = 320
        off = 0
        while off < n:
            L = min(step, n - off)
            p = base + off
            d0 = _dw(v, p - 360, L)
            d1 = _dw(v, p, L)
            d2 = _dw(v, p + 360, L)
            d3 = _dw(v, p + 720, L)
            e = (d0 + d1 + d2 + d3) & np.uint32(0xFCFCFCFC)
            e >>= np.uint32(2)
            al = (e & np.uint32(0xFF)).astype(np.uint32)
            al = al + ((e >> np.uint32(8)) & np.uint32(0xFF))
            al = al + ((e >> np.uint32(16)) & np.uint32(0xFF))
            al = al + ((e >> np.uint32(24)) & np.uint32(0xFF))
            al &= np.uint32(0xFF)
            al >>= np.uint32(2)
            v[p:p + L] = al.astype(np.uint8)
            off += L

    def lssmooth(self):
        """2x2 average preserving the top two bits.  NOCTIS-0.CPP:4417.

        LR-DIVERGENCE: niv-lr smooths one pixel FEWER per call (a change made
        to silence a memory checker).  Vanilla's count is
        (QUADWORDS-80)<<2 = 64480, and the last iterations read up to 41 bytes
        PAST the 64,800-byte map.  On a planet those 41 bytes are the tail of
        the same farmalloc block; on a MOON, where p_background aliases
        s_background whose declared size is exactly 64800, they are the
        neighbouring block.  The read overrun is preserved."""
        n = ((self.QUADWORDS - 80) << 2) & M16
        v = self.pv
        p = PB
        d0 = v[p:p + n].astype(np.uint16)
        d1 = v[p + 1:p + 1 + n].astype(np.uint16)
        b0 = v[p + 360:p + 360 + n].astype(np.uint16)
        b1 = v[p + 361:p + 361 + n].astype(np.uint16)
        keep = (d0 & 0xC0).astype(np.uint8)
        s = (d0 & 0x3F) + (d1 & 0x3F) + (b0 & 0x3F) + (b1 & 0x3F)
        s = (s & 0xFF) >> 2
        v[p:p + n] = keep | s.astype(np.uint8)

    def psmooth_grays(self):
        """Same kernel as ssmooth but stride 320 and all four lanes summed.

        LR-DIVERGENCE: niv-lr narrows the lane accumulator to uint8_t, which
        drops two of the four lanes.  Vanilla sums all four."""
        n = ((self.QUADWORDS << 2) & M16)
        n = (n - ((320 << 2) & M16)) & M16
        v = self.pv
        base = PB + 320
        # chunk <= 317 for the stride-320 kernel, same argument as ssmooth
        off = 0
        while off < n:
            L = min(300, n - off)
            p = base + off
            d0 = _dw(v, p - 320, L)
            d1 = _dw(v, p, L)
            d2 = _dw(v, p + 320, L)
            d3 = _dw(v, p + 640, L)
            e = (d0 + d1 + d2 + d3) & np.uint32(0xFCFCFCFC)
            e >>= np.uint32(2)
            al = (e & np.uint32(0xFF)).astype(np.uint32)
            al = al + ((e >> np.uint32(8)) & np.uint32(0xFF))
            al = al + ((e >> np.uint32(16)) & np.uint32(0xFF))
            al = al + ((e >> np.uint32(24)) & np.uint32(0xFF))
            al &= np.uint32(0xFF)
            al >>= np.uint32(2)
            v[p:p + L] = al.astype(np.uint8)
            off += L

    def pclear(self, pattern):
        n = self.QUADWORDS * 4
        self.pv[PB:PB + n] = np.uint8(pattern)

    # ------------------------------------------------------------------
    # the modular painters.  NOCTIS-0.CPP:4488-4756
    # ------------------------------------------------------------------

    def spot(self):
        di = (PB + self.py + self.px) & M16
        al = (self.pseg[di] + (self.gr & 0xFF)) & 0xFF
        if al >= 0x3E:
            al = 0x3E
        self.pseg[di] = al

    def cirrus(self):
        bx = ((self.py + self.px) & M16) >> 1
        di = (OV + bx) & M16
        al = (self.oseg[di] + (self.gr & 0xFF)) & 0xFF
        if al >= 0x1F:
            al = 0x1F
        self.oseg[di] = al

    def permanent_storm(self):
        self.g = 1
        while self.g < self.cr:
            for a in ASEQ4:
                self.a = a
                self.px = d2u16(self.cx + self.g * math.cos(a))
                self.py = d2u16(self.cy + self.g * math.sin(a))
                self.py = (self.py * 360) & M16
                self.spot()
            self.g = i16(self.g + 1)
        self.a = _after(ASEQ4, _STEP4)

    def storm(self):
        self.g = 1
        while self.g < self.cr:
            for a in ASEQ4:
                self.a = a
                self.px = d2u16(self.cx + self.g * math.cos(a))
                self.py = d2u16(self.cy + self.g * math.sin(a))
                self.py = (self.py * 360) & M16
                self.cirrus()
            self.g = i16(self.g + 1)
        self.a = _after(ASEQ4, _STEP4)

    def volcano(self):
        for a in ASEQ4:
            self.a = a
            self.b = self.gr
            self.g = cdiv(self.cr, 2)
            while self.g < self.cr:
                self.px = d2u16(self.cx + math.cos(a) * self.g)
                self.py = d2u16(self.cy + math.sin(a) * self.g)
                self.py = (self.py * 360) & M16
                self.spot()
                self.gr = i16(self.gr - 1)
                if self.gr < 0:
                    self.gr = 0
                self.g = i16(self.g + 1)
            self.gr = self.b
        self.a = _after(ASEQ4, _STEP4)

    def crater(self):
        for a in ASEQ4:
            self.a = a
            ca, sa = math.cos(a), math.sin(a)
            self.gr = 0
            while self.gr < self.cr:
                self.px = d2u16(self.cx + ca * self.gr)
                self.py = d2u16(self.cy + sa * self.gr)
                self.vptr = (self.px + ((360 * self.py) & M16)) & M16
                di = (PB + self.vptr) & M16
                al = self.pseg[di]
                ah = (self.gr & 0xFF) >> (self.lave & 0xFF)
                if al < ah:
                    al = 0                      # jnc entro / xor al,al
                else:
                    al = al - ah
                self.pseg[di] = al
                self.gr = i16(self.gr + 1)
            di = (PB + self.vptr) & M16
            self.pseg[di] = 0x3E                # mov ax,0x013E ; mov [di],ax
            self.pseg[(di + 1) & M16] = 0x01
            if self.crays and not self.B.random(self.crays, 4551):
                self._cj_zeros += 1
                self.b = i16((2 + self.B.random(2, 4552)) * self.cr)
                if self.cy - self.b > 0 and self.cy + self.b < 179:
                    self.gr = i16(self.cr + 1)
                    while self.gr < self.b:
                        self.px = d2u16(self.cx + ca * self.gr)
                        self.py = d2u16(self.cy + sa * self.gr)
                        self.vptr = (self.px + ((360 * self.py) & M16)) & M16
                        di = (PB + self.vptr) & M16
                        al = (self.pseg[di] + (self.cr & 0xFF)) & 0xFF
                        if al >= 0x3E:
                            al = 0x3E
                        self.pseg[di] = al
                        self.gr = i16(self.gr + 1)
        self.a = _after(ASEQ4, _STEP4)

    def band(self):
        di = (PB + self.py) & M16
        ah = self.g & 0xFF
        n = self.cr & M16
        if n == 0:
            n = 0x10000                         # dec cx / jnz : 65536 passes
        for _ in range(n):
            al = self.pseg[di]
            al = 0 if al < ah else al - ah
            self.pseg[di] = al
            di = (di + 1) & M16

    def wave(self):
        """NOCTIS-0.CPP:4578-4600.  `add ax, 4` re-applies offset(p_background)
        after `mov di, ax` clobbers the one `les di` loaded, so the pixel
        index is py*360 + px with NO skew (BUFFERMAP 4.1)."""
        self.px = 360
        bx = self.cy & M16
        av = self.a
        while True:
            val = math.sin(self.px * av) * i16(self.cr)
            self.py = fistp16(_Fr(val))
            self.py = (self.py + bx) & M16
            ax = (self.py * 360) & M16
            ax = (ax + 4) & M16
            di = (ax + self.px) & M16
            self.pseg[di] = 0
            self.px = (self.px - 1) & M16
            if self.px == 0:
                break

    def fracture(self, max_latitude):
        """NOCTIS-0.CPP:4602-4626.  `px`/`py` here are LOCAL floats that shadow
        the unsigned globals; `a` and `gr` are the globals and are clobbered."""
        self.a = f32(ext(_Fr(self.B.random(360, 4604)) * _EXT_DEG))
        self.gr = i16(self.gr + 1)
        px = float(self.cx)
        py = float(self.cy)
        kf = self.kfract
        ml = max_latitude
        while True:
            k = self.B.random(self.g, 4608) - self.B.random(self.g, 4608)
            self.a = f32(ext(_Fr(self.a) + kdeg(k)))
            a = self.a
            px = f32(ext(_Fr(px) + ext(_Fr(kf) * _Fr(math.cos(a)))))
            if px > 359:
                px = f32(_Fr(px) - 360)
            if px < 0:
                px = f32(_Fr(px) + 360)
            py = f32(ext(_Fr(py) + ext(_Fr(kf) * _Fr(math.sin(a)))))
            if py > ml - 1:
                py = f32(_Fr(py) - _Fr(ml))
            if py < 0:
                py = f32(_Fr(py) + _Fr(ml))
            self.vptr = d2u16(px + ((360 * d2u16(py)) & M16))
            di = (PB + self.vptr) & M16
            self.pseg[di] = self.pseg[di] >> (self.b & 0xFF)
            self.gr = i16(self.gr - 1)
            if self.gr == 0:
                break

    def negate(self):
        v = self.pv
        v[PB:PB + MAPBYTES] = (np.uint8(0x3E) - v[PB:PB + MAPBYTES])

    def contrast(self, kt, kq, thrshld):
        """NOCTIS-0.CPP:4692.  `c` is a LOCAL unsigned that shadows the global;
        `a` is the global float and is left holding the last pixel."""
        v = self.pv[PB:PB + MAPBYTES].astype(np.float32)
        t = np.float32(thrshld)
        v = (v - t).astype(np.float32)
        pos = v > np.float32(0)
        v = np.where(pos, v * np.float32(kt), v * np.float32(kq)).astype(np.float32)
        v = (v + t).astype(np.float32)
        v = np.where(v < np.float32(0), np.float32(0), v)
        v = np.where(v > np.float32(63), np.float32(63), v)
        self.a = float(v[-1])
        self.pv[PB:PB + MAPBYTES] = v.astype(np.uint8)

    def randoface(self, rng, upon):
        """NOCTIS-0.CPP:4711.  Data-dependent brtl consumption: two draws for
        every pixel that passes the gate and none for the rest.  This is the
        single largest coupling between the map's content and the brtl stream's
        consumption point."""
        pb = self.pseg
        R = self.B.random
        hits = 0
        for i in range(MAPBYTES):
            gr = pb[PB + i]
            if (upon > 0 and gr >= upon) or (upon < 0 and gr <= -upon):
                hits += 1
                gr = gr + R(rng, 4716) - R(rng, 4717)
                if gr > 63:
                    gr = 63
                if gr < 0:
                    gr = 0
                pb[PB + i] = gr
        self.gates["rf_hits"] = self.gates.get("rf_hits", 0) + hits
        self.gr = i16(pb[PB + MAPBYTES - 1])

    def crater_juice(self):
        self.lave = _tochar(self.B.random(3, 4681))
        self.crays = _tochar(self.B.random(3, 4682) * 2)
        self._cj_zeros = 0
        self.c = 0
        while self.c < self.r:
            self.cx = self.B.random(360, 4684)
            self.cr = i16(2 + self.B.random(1 + self.r - self.c, 4685))
            while self.cr > 20:
                self.cr = i16(self.cr - 10)
            self.cy = i16(self.B.random(178 - 2 * self.cr, 4687) + self.cr)
            self.crater()
            if self.cr > 15:
                self.lssmooth()
            self.c = i16(self.c + 1)

    def atm_cyclon(self):
        """NOCTIS-0.CPP:4728-4746.  Three brtl draws and six cirrus writes per
        step; the step count is g * cr and is set by two FAST draws, which is
        one of the four fast->brtl coupling shapes."""
        self.b = 0
        seq = self._a6
        idx = 0
        R = self.B.random
        while self.cr > 0:
            a = seq[idx]
            self.a = a
            self.px = d2u16(self.cx + self.cr * math.cos(a))
            self.py = d2u16(self.cy + self.cr * math.sin(a))
            self.py = (self.py * 360) & M16
            self.cirrus()
            self.px = (self.px + R(4, 4735)) & M16
            self.cirrus()
            self.py = (self.py + 359) & M16
            self.cirrus()
            self.px = (self.px - R(4, 4737)) & M16
            self.cirrus()
            self.py = (self.py + 361) & M16
            self.cirrus()
            self.px = (self.px + R(4, 4739)) & M16
            self.cirrus()
            self.b = i16(self.b + 1)
            self.b = crem(self.b, self.g)
            if not self.b:
                self.cr = i16(self.cr - 1)
            idx += 1
            if idx >= len(seq):
                seq = self._extend6(idx)
        self.a = seq[idx]

    def _extend6(self, need):
        cur = self._a6
        while len(cur) <= need:
            cur.append(f32(ext(_Fr(cur[-1]) + _STEP6)))
        return cur

    # ------------------------------------------------------------------
    # 4.  surface() itself.  NOCTIS-0.CPP:4766-5196
    # ------------------------------------------------------------------

    def run(self, logical_id, ptype, seedval, colorbase,
            secs=0.0, plwp=None, owner=-1,
            nearstar_rgb=(0, 0, 0), moon=False):
        """seedval must already be the binary64 the caller pushed - see
        su_seed.py, which builds it on the x87 stack with no intermediate
        store as Wave 3 requires."""
        self.rec = []
        F, B = self.F, self.B
        QW = self.QUADWORDS
        out = {}

        if ptype == 10:
            out["early"] = "type10"
            out["fast_n"] = out["brtl_n"] = 0
            return out                          # UNGRADED: unreachable in the
                                                # shipped build (§2 U2)

        # --- prologue : draws F1..F3 ----------------------------------
        F.srand(ftol32(_Fr(seedval) + 4112))    # :4811  the +4112 is added in
                                                # DOUBLE, before __ftol
        rt = (10 * (F.rfr(50, 4790) + 1)
              + 10 * F.rfr(25, 4791)
              + F.rfr(250, 4792) + 41)
        out["rtperiod"] = i16(rt)
        rot = i16(ftol32(_Fr(secs) / rt)) if rt else 0
        rot = i16(crem(rot, 360))
        out["rotation"] = rot

        if plwp is None:
            raise ValueError("plwp must be supplied: cplx_planet_viewpoint() "
                             "is Wave 8 and is deliberately UNGRADED here")
        self.mark("PROLOGUE")

        # --- the cross-seeding bridge :4815-4817 ----------------------
        F.srand(ftol32(_Fr(seedval) * 10))
        seed = F.raw(0xFFFF, 4816) & M16
        self._seed = seed

        B.srand(seed)                           # :4819
        # --- rndpat : the self-squaring 16-bit hash over all 64,800 ---
        ax = seed
        pb = self.pseg
        di = PB
        cx = MAPBYTES
        while cx:
            ax = (ax + cx) & M16
            sv = ax - 0x10000 if ax & 0x8000 else ax
            p = (sv * sv) & 0xFFFFFFFF
            dx = (p >> 16) & M16
            ax = ((p & M16) + dx) & M16
            pb[di] = ax & 0x3E
            di += 1
            cx -= 1
        self.mark("RNDPAT")

        self.oseg[OV:OV + OVLBYTES] = b"\x00" * OVLBYTES

        B.srand(seed)                           # :4844  UNGRADED (§2 U3):
        # nothing between the two srand(seed) calls draws and Borland's srand
        # is idempotent, so no check can distinguish them.  Both are executed
        # because the source does; nothing claims to detect the difference.
        self.QUADWORDS = 16200

        self.secs_sites = []
        self.gates = {}
        self._switch(ptype, secs)
        if self.stop_after_switch:
            # the overlay is complete here and nothing after the switch ever
            # touches it again, so an overlay-only search can stop.
            out["fast_n"] = F.n
            out["brtl_n"] = B.n
            self.QUADWORDS = QW
            return out

        # --- renormalisation :5070 ------------------------------------
        if ptype == 3 or ptype == 5:
            self.pv[PB:PB + MAPBYTES] >>= np.uint8(1)
        self.mark("RENORM")

        if ptype == 3:
            if F.rfr(2, 5079):
                self.lssmooth()
            else:
                self.ssmooth()

        # --- merge terrain + atmosphere :5088 -------------------------
        v = self.pv
        ovl = self.ov[OV:OV + OVLBYTES].astype(np.uint16)
        even = v[PB:PB + MAPBYTES:2].astype(np.uint16) + ovl
        even = np.where(even > 0x3E, 0x3E, even)
        v[PB:PB + MAPBYTES:2] = even.astype(np.uint8)
        odd = v[PB + 1:PB + MAPBYTES:2].astype(np.uint16) + ovl
        odd = np.where(odd > 0x3E, 0x3E, odd)
        v[PB + 1:PB + MAPBYTES:2] = odd.astype(np.uint8)
        self.px = OVLBYTES
        self.py = MAPBYTES
        self.mark("MERGE")

        knot1 = 0
        if ptype == 2:
            if not B.random(3, 5098):
                self.psmooth_grays()
                knot1 = 1
        self.gates["knot1"] = knot1

        # --- day/night terminator :5106-5124 --------------------------
        ts = i16(plwp + 35)
        if ts >= 360:
            ts = i16(ts - 360)
        te = i16(ts + 130)
        if te >= 360:
            te = i16(te - 360)
        out["term_start"] = ts
        out["term_end"] = te
        di = (PB + plwp + 35) & M16
        for _ in range(179):
            seg = self.pv[di:di + 130]
            if len(seg) == 130:
                self.pv[di:di + 130] = seg >> np.uint8(2)
            else:                               # 16-bit wrap inside a row
                for k in range(130):
                    p = (di + k) & M16
                    self.pseg[p] = self.pseg[p] >> 2
            di = (di + 130 + 230) & M16
        self.mark("TERMINATOR")

        # --- final retouches :5128-5146 -------------------------------
        if ptype == 2:
            if knot1:
                self.ssmooth()
            else:
                self.r = i16(3 + F.rfr(5, 5134))
                self.c = 0
                while self.c < self.r:
                    self.ssmooth()
                    self.c = i16(self.c + 1)
        if ptype == 6:
            for _ in range(3):
                if F.rfr(2, 5141):
                    self.ssmooth()
        if ptype == 9:
            for _ in range(6):
                self.ssmooth()
        self.mark("POST")

        # --- palette :5148-5195 ---------------------------------------
        if colorbase == 255:                    # UNGRADED (§2 U1): the two
            self.QUADWORDS = QW                 # live call sites pass 128/192
            out["early"] = "colorbase255"
            out["fast_n"] = F.n
            out["brtl_n"] = B.n
            return out
        self._palette(logical_id, ptype, colorbase, owner, nearstar_rgb)
        self.mark("PALETTE")

        self.QUADWORDS = QW
        out["knot1"] = knot1
        out["seed"] = seed
        out["fast_n"] = F.n
        out["brtl_n"] = B.n
        return out

    # ------------------------------------------------------------------

    def _palette(self, logical_id, ptype, colorbase, owner, nsrgb):
        B = self.B
        t = i16(ptype << 2)
        r = PLANET_RGB_AND_VAR[t + 0]
        g = PLANET_RGB_AND_VAR[t + 1]
        b = PLANET_RGB_AND_VAR[t + 2]
        c = PLANET_RGB_AND_VAR[t + 3]
        nr, ng, nb = nsrgb
        r = i16(i16(i16(r << 1) + nr) >> 1)
        g = i16(i16(i16(g << 1) + ng) >> 1)
        b = i16(i16(i16(b << 1) + nb) >> 1)
        # `x + random(c) - random(c)` : operands of + and - evaluate LEFT to
        # RIGHT, so the first draw is added and the second subtracted.  This
        # is pinned by the palette captures themselves (check C3).
        r1 = float(r + B.random(c, 5166) - B.random(c, 5166))
        g1 = float(g + B.random(c, 5167) - B.random(c, 5167))
        b1 = float(b + B.random(c, 5168) - B.random(c, 5168))
        r2 = float(r + B.random(c, 5169) - B.random(c, 5169))
        g2 = float(g + B.random(c, 5170) - B.random(c, 5170))
        b2 = float(b + B.random(c, 5171) - B.random(c, 5171))
        r3 = float(r + B.random(c, 5172) - B.random(c, 5172))
        g3 = float(g + B.random(c, 5173) - B.random(c, 5173))
        b3 = float(b + B.random(c, 5174) - B.random(c, 5174))
        r1 = f32(_Fr(r1) * _Fr(0.25)); g1 = f32(_Fr(g1) * _Fr(0.25))
        b1 = f32(_Fr(b1) * _Fr(0.25))
        r2 = f32(_Fr(r2) * _Fr(0.75)); g2 = f32(_Fr(g2) * _Fr(0.75))
        b2 = f32(_Fr(b2) * _Fr(0.75))
        r3 = f32(_Fr(r3) * _Fr(1.25)); g3 = f32(_Fr(g3) * _Fr(1.25))
        b3 = f32(_Fr(b3) * _Fr(1.25))
        self._shade(colorbase + 0, 16, 0.0, 0.0, 0.0, r1, g1, b1)
        self._shade(colorbase + 16, 16, r1, g1, b1, r2, g2, b2)
        self._shade(colorbase + 32, 16, r2, g2, b2, r3, g3, b3)
        self._shade(colorbase + 48, 16, r3, g3, b3, 64.0, 64.0, 64.0)
        brt = _tochar(owner)                 # char brt <- int nearstar_p_owner
        if brt == -1:
            brt = _tochar(logical_id)
        if brt <= 4:
            brt = _tochar(64)
        else:
            brt = _tochar(64 - (4 * (brt - 4)))
        self._tavola_colori(colorbase, 64, brt, brt, brt)

    def _shade(self, first_color, ncolors, sr, sg, sb, fr_, fg, fb):
        """NOCTIS-0.CPP:1151.  Every arithmetic step is float32."""
        count = ncolors
        k = f32(_Fr(1.0) / _Fr(float(ncolors)))
        dr = f32(ext(ext(_Fr(fr_) - _Fr(sr)) * _Fr(k)))
        dg = f32(ext(ext(_Fr(fg) - _Fr(sg)) * _Fr(k)))
        db = f32(ext(ext(_Fr(fb) - _Fr(sb)) * _Fr(k)))
        fc = first_color * 3
        pal = self.tmppal
        while count:
            for off, val in ((0, sr), (1, sg), (2, sb)):
                if 0 <= val < 64:
                    pal[fc + off] = int(val)
                elif val > 0:
                    pal[fc + off] = 63
                else:
                    pal[fc + off] = 0
            sr = f32(ext(_Fr(sr) + _Fr(dr)))
            sg = f32(ext(_Fr(sg) + _Fr(dg)))
            sb = f32(ext(_Fr(sb) + _Fr(db)))
            fc += 3
            count -= 1

    def _tavola_colori(self, start, ncolors, fr_, fg, fb):
        """NOCTIS-0.CPP:179.  The copy loop copies tmppal onto itself because
        surface() passes `tmppal + 3*colorbase` as the source; only the filter
        pass has an effect."""
        n = ncolors * 3
        s = start * 3
        pal = self.tmppal
        for cc in range(n):
            pal[s + cc] = pal[s + cc]
        c = s
        filt = (fr_, fg, fb)
        while c < n + s:
            for f in filt:
                temp = (pal[c] * f) & 0xFFFF    # unsigned temp, char filtro
                temp = temp // 63
                if temp > 63:
                    temp = 63
                pal[c] = temp
                c += 1

    # ------------------------------------------------------------------
    # 5.  the ten cases.  NOCTIS-0.CPP:4847-5065
    # ------------------------------------------------------------------

    def _switch(self, ptype, secs):
        F, B = self.F, self.B
        v = self.pv

        if ptype == 0:
            self.r = i16(F.rfr(3, 4848) + 5)
            for self.c in range(self.r):
                self.ssmooth()
            m = v[PB:PB + MAPBYTES]
            np.copyto(m, np.uint8(62), where=(m >= 28))
            self.r = i16(F.rfr(5, 4857) + 5)
            for self.c in range(self.r):
                self.ssmooth()
            self.r = i16(5 + F.rfr(26, 4859))
            self.gates["r_volc"] = self.r
            for c in range(self.r):
                self.c = c
                self.cr = i16(5 + F.rfr(20, 4861))
                self.cx = F.rfr(360, 4862)
                self.cy = i16(F.rfr(130, 4863) + 25)
                self.gr = i16(F.rfr(cdiv(self.cr, 2), 4864)
                              + cdiv(self.cr, 2) + 2)
                self.volcano()
            self.r = i16(100 + F.rfr(100, 4867))
            self.b = i16(F.rfr(3, 4868) + 1)
            self.g = 360
            self.gates["r_frac"] = self.r
            self.gates["frac_gr"] = []
            for c in range(self.r):
                self.c = c
                self.cx = F.rfr(360, 4871)
                self.cy = F.rfr(180, 4872)
                self.gr = F.rfr(100, 4873)
                self.gates["frac_gr"].append(self.gr)
                self.fracture(180.0)
            self.lssmooth()

        elif ptype == 1:
            if F.rfr(2, 4878):
                self.ssmooth()
            self.r = i16(10 + F.rfr(41, 4879))
            self.crater_juice()
            self.gates["cj_brtl"] = 2 + 3 * self.r + (
                0 if not self.crays else self.r * len(ASEQ4) + self._cj_zeros)
            self.lssmooth()
            if not F.rfr(5, 4882):
                self.negate()

        elif ptype == 2:
            self.r = i16(5 + F.rfr(25, 4884))
            self.gates["t2_branch"] = []
            for c in range(self.r):
                self.c = c
                self.cr = i16(F.rfr(20, 4886) + 1)
                self.cy = i16(F.rfr(178 - 2 * self.cr, 4887) + self.cr)
                _br = B.random(2, 4888)
                self.gates["t2_branch"].append(_br)
                if _br == 0:
                    self.cx = _secs_site(self, 10, secs, F.rfr(3600, 4890) + 180)
                    self.gr = i16(F.rfr(12, 4891) + 2)
                    self.storm()
                else:
                    self.gr = i16(F.rfr(15, 4894) + 3)
                    self.py = (self.cy * 360) & M16
                    self.cr = i16(self.cr * 360)
                    self.g = i16(1 + F.rfr(self.gr, 4896))
                    self.band()
            if not F.rfr(3, 4900):
                self.negate()

        elif ptype == 3:
            self.r = i16(F.rfr(3, 4902) + 4)
            self.g = i16(26 + F.rfr(3, 4903) - F.rfr(5, 4903))
            for self.c in range(self.r):
                self.ssmooth()
            self._sda()
            self.r = i16(20 + F.rfr(40, 4921))
            self.gates["t3_cygate"] = []
            self.gates["t3_gcr"] = []
            for c in range(self.r):
                self.c = c
                self.gr = i16(F.rfr(5, 4923) + 1)
                self.cr = i16(F.rfr(10, 4924) + 10)
                _gate = F.rfr(3, 4925)
                self.gates["t3_cygate"].append(_gate)
                if _gate:
                    self.cy = i16(F.rfr(172 - 2 * self.cr, 4926) + self.cr + 2)
                else:
                    self.cy = i16(60 + F.rfr(10, 4928) - F.rfr(10, 4928))
                self.cx = _secs_site(self, 1, secs, F.rfr(360, 4929) + 180)
                self.g = i16(F.rfr(5, 4930) + 7)
                self.gates["t3_gcr"].append((self.g, self.cr))
                k = F.rfr(360, 4931)
                self._a6 = list(aseq6(k, 8 + self.g * self.cr))
                self.a = self._a6[0]
                self.atm_cyclon()

        elif ptype == 4:
            self.ssmooth()
            if F.rfr(2, 4936):
                self.ssmooth()
            self._lmrip()
            self.r = F.rfr(30, 4946)
            if self.r > 20:
                self.r = i16(self.r * 10)
            self.b = i16(F.rfr(3, 4948) + 1)
            self.g = i16(200 + F.rfr(300, 4949))
            self.gates["r_frac"] = self.r
            self.gates["frac_gr"] = []
            for c in range(self.r):
                self.c = c
                self.cx = F.rfr(360, 4951)
                self.cy = F.rfr(180, 4952)
                self.gr = i16(50 + F.rfr(100, 4953))
                self.gates["frac_gr"].append(self.gr)
                self.fracture(180.0)
            self.r = i16(F.rfr(25, 4956) + 1)
            self.crater_juice()
            self.gates["cj_brtl"] = 2 + 3 * self.r + (
                0 if not self.crays else self.r * len(ASEQ4) + self._cj_zeros)
            self.lssmooth()
            if F.rfr(2, 4958):
                self.lssmooth()

        elif ptype == 5:
            self.r = i16(F.rfr(3, 4960) + 4)
            for self.c in range(self.r):
                self.ssmooth()
            # arguments are evaluated RIGHT TO LEFT (Borland cdecl), so the
            # thrshld draw comes first.  Sabotage ARGORDER flips this.
            thr = i16(25 + F.rfr(3, 4963))
            kq = f32(ext(ext(_Fr(F.rfr(350, 4963)) / 100) + _Fr(4.0)))
            kt = f32(ext(ext(_Fr(F.rfr(200, 4962)) / 900) + _Fr(0.6)))
            self.contrast(kt, kq, float(thr))
            upon = i16(-20 * (F.rfr(3, 4965) + 1))
            rng = i16(5 + F.rfr(3, 4965))
            self.randoface(rng, upon)
            self.r = i16(5 + F.rfr(5, 4966))
            self.gates["r_volc"] = self.r
            for c in range(self.r):
                self.c = c
                self.cr = i16(5 + F.rfr(10, 4968))
                self.cx = F.rfr(360, 4969)
                self.cy = i16(F.rfr(145, 4970) + 15)
                self.gr = i16(F.rfr(cdiv(self.cr, 2), 4971) + 2)
                self.volcano()
            self.r = i16(5 + F.rfr(5, 4974))
            self.gates["r_pstorm"] = self.r
            for c in range(self.r):
                self.c = c
                self.cr = i16(F.rfr(30, 4976) + 1)
                self.cy = i16(F.rfr(178 - 2 * self.cr, 4977) + self.cr)
                self.cx = _secs_site(self, 60, secs, F.rfr(3600, 4978) + 360)
                self.gr = i16(F.rfr(2, 4979) + 1)
                self.permanent_storm()
            for c in range(10000):
                self.c = i16(c)
                self.gr = i16(F.rfr(10, 4983) + 10)
                self.px = F.rfr(360, 4984) & M16
                self.py = F.rfr(10, 4985) & M16
                self.py = (self.py * 360) & M16
                self.spot()
                self.px = F.rfr(360, 4986) & M16
                self.py = i16(125 - F.rfr(10, 4987)) & M16
                self.py = (self.py * 360) & M16
                self.spot()
            self.c = 10000
            if F.rfr(2, 4990):
                self.ssmooth()
            else:
                self.lssmooth()

        elif ptype == 6:
            self.r = i16(3 + F.rfr(5, 4995))
            for self.c in range(self.r):
                self.ssmooth()
            self.r = i16(50 + F.rfr(100, 4997))
            self.gates["t6_wave"] = []
            for c in range(self.r):
                self.c = c
                self.cr = i16(F.rfr(10, 4999) + 1)
                self.cy = i16(F.rfr(178 - 2 * self.cr, 5000) + self.cr)
                _g8 = F.rfr(8, 5001)
                self.gates["t6_wave"].append(_g8 == 0)
                if _g8:
                    self.gr = i16(F.rfr(5, 5002) + 2)
                    self.g = i16(1 + F.rfr(self.gr, 5003))
                    self.py = (self.cy * 360) & M16
                    self.cr = i16(self.cr * 360)
                    self.band()
                else:
                    self.a = f32(ext(_Fr(5 + F.rfr(10, 5009)) / 30))
                    self.cr = i16(cdiv(self.cr, 4) + 1)
                    self.wave()
            self.r = i16(50 + F.rfr(100, 5014))
            self.gates["r_storm"] = self.r
            for c in range(self.r):
                self.c = c
                self.cr = i16(F.rfr(15, 5016) + 1)
                self.cy = i16(F.rfr(178 - 2 * self.cr, 5017) + self.cr)
                self.cx = _secs_site(self, 60, secs, F.rfr(8000, 5018) + 360)
                self.gr = i16(F.rfr(2, 5019) + 1)
                if F.rfr(10, 5020):
                    self.cr = i16(cdiv(self.cr, 2) + 1)
                else:
                    self.gr = i16(self.gr * 3)
                self.storm()
            self.lssmooth()
            if not F.rfr(3, 5026):
                self.negate()

        elif ptype == 7:
            self.r = i16(5 + F.rfr(5, 5028))
            for self.c in range(self.r):
                self.ssmooth()
            self.r = i16(10 + F.rfr(50, 5030))
            self.g = i16(5 + F.rfr(20, 5031))
            self.b = i16(F.rfr(2, 5032) + 1)
            self.gates["r_frac"] = self.r
            self.gates["frac_gr"] = []
            for c in range(self.r):
                self.c = c
                self.cx = F.rfr(360, 5034)
                self.cy = F.rfr(180, 5035)
                self.gr = F.rfr(300, 5036)
                self.gates["frac_gr"].append(self.gr)
                self.fracture(180.0)
            if F.rfr(2, 5039):
                self.lssmooth()
            rng = i16(1 + F.rfr(10, 5040))
            self.randoface(rng, 1)
            if F.rfr(2, 5041):
                self.negate()

        elif ptype == 8:
            self.r = i16(F.rfr(10, 5043) + 1)
            for self.c in range(self.r):
                self.lssmooth()
            self.r = i16(100 + F.rfr(50, 5045))
            self.gates["r_pstorm"] = self.r
            for c in range(self.r):
                self.c = c
                self.cr = i16(F.rfr(5, 5047) + 1)
                self.gr = i16(F.rfr(5, 5048) + 1)
                self.cx = F.rfr(360, 5049)
                self.cy = i16(F.rfr(178 - 2 * self.cr, 5050) + self.cr)
                self.permanent_storm()
            if F.rfr(2, 5053):
                self.negate()

        elif ptype == 9:
            self.pclear(0x1F)
            for px in range(OVLBYTES):
                self.oseg[(OV + px) & M16] = 0x1F
            self.px = OVLBYTES
        self.mark("CASE%d" % ptype)

    # --- the two byte-level loops that only exist inside the switch ----

    def _sda(self):
        """NOCTIS-0.CPP:4906-4919.

        LR-DIVERGENCE, the one PORTPLAN calls out as fatal:
          * vanilla `add es:[di], bl`   -- ADDS the noise to the smoothed
            terrain;  niv-lr ASSIGNS it, which makes the following clamp
            unreachable.
          * the clamp is `mov WORD ptr es:[di], 0x3E`, so it also zeroes the
            NEXT pixel.  niv-lr stores a byte and loses that side effect.
          * the noise register `ax` is advanced ONLY on the land branch; the
            sea branch jumps straight to `mare`.
        """
        pb = self.pseg
        di = PB
        cx = 64000
        ax = self._seed
        gl = self.g & 0xFF
        dx = 0
        while cx:
            cur = pb[di]
            if cur < gl:
                pb[di] = 16
                # dl still holds g; dx is NOT reloaded, and ax is NOT advanced
            else:
                ax = (ax + cx) & M16
                sv = ax - 0x10000 if ax & 0x8000 else ax
                p = (sv * sv) & 0xFFFFFFFF
                dx = (p >> 16) & M16
                ax = ((p & M16) + dx) & M16
                bl = ax & 0x3E
                nv = (pb[di] + bl) & 0xFF
                pb[di] = nv
                if nv >= 0x3E:
                    pb[di] = 0x3E
                    pb[(di + 1) & M16] = 0x00   # the word store's high byte
            di = (di + 1) & M16
            cx -= 1

    def _lmrip(self):
        """NOCTIS-0.CPP:4940-4944."""
        pb = self.pseg
        di = PB
        for _ in range(64000):
            if pb[di] == 32:
                pb[di] = 0x01
                pb[(di + 1) & M16] = 0x3E
                pb[(di + 360) & M16] = 0x01
            di = (di + 1) & M16


def _secs_site(self, k, secs, D):
    self.secs_sites.append((k, D))
    sl = self._secs_scaled
    if sl is None:
        sl = ftol32(_Fr(k) * _Fr(secs))
    return i16(crem(cdiv(sl, D), 360))


def _tochar(v):
    v &= 0xFF
    return v - 256 if v & 0x80 else v


def _after(seq, step):
    return f32(ext(_Fr(seq[-1]) + step))


def _dw(v, p, L):
    """L little-endian dwords starting at byte p."""
    return (v[p:p + L].astype(np.uint32)
            | (v[p + 1:p + 1 + L].astype(np.uint32) << np.uint32(8))
            | (v[p + 2:p + 2 + L].astype(np.uint32) << np.uint32(16))
            | (v[p + 3:p + 3 + L].astype(np.uint32) << np.uint32(24)))
