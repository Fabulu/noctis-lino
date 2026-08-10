r"""Independent Python oracle for Wave 7b ``create_sky``.

The implementation is a source transcription of NIV+ R2.3
``NOCTIS-1.CPP:1674-1765,2736-3139,3683-3697``.  It deliberately keeps the
caller-side horizon pass separate from ``create_sky`` so D (derive) failures
can be attributed.  It does not read C or L.in.oleum output.

The captured type-3 OCEAN fixture is a *pixel/palette* binary anchor.  Its
gallery palette proves the special night branch byte-for-byte, but the old RAM
image was not retained.  Therefore its scalar-only dsd1/exposure inputs use
documented poison values and GRADE_SCALARS is clear.  Synthetic rows grade the
complete scalar/RNG path three ways; they do not acquire a NIV+ binary claim.
"""

from __future__ import division

import hashlib
import math
import os
import struct
from dataclasses import dataclass

from brtl_oracle import Brtl
from fb_pal import Palette, SRFPAL6
from su_fp import ext, f32, fr

M16 = 0xFFFF
M32 = 0xFFFFFFFF
FNV_OFF = 0x811C9DC5
FNV_PRIME = 0x01000193
ST_BYTES = 64800
TAIL_BYTES = 64
PAGE_BYTES = 64000
OFFSET_MAP_BYTES = 7340
SKY_MAGIC = 0x31594B53
SKY_VERSION = 1

OCEAN, PLAINS, DESERT, ICY = 1, 2, 3, 4

BINARY_ANCHOR = 1 << 0
GRADE_PALETTE = 1 << 1
GRADE_SCALARS = 1 << 2
GRADE_PAGE = 1 << 3
TAIL_SENSITIVE = 1 << 4
LIVE_REACHABLE = 1 << 5
PALETTE_UNDEFINED = 1 << 6
KNOWN_FLAGS = (1 << 7) - 1

META = 1
PRE_HORIZON = 2
FINAL_SBG = 3
PALETTE = 4
SCALARS = 5
LEDGER = 6
GUARDS = 7
REPLAY_PAGE = 8
JOIN_PAGE = 9
CASE_END = 10
STREAM_END = 255

PHASES = ("ENTRY", "SEEDED", "COLOURS", "PAINTER", "PALETTE",
          "THERMO", "HORIZON", "DONE")

FIELD_NAMES = (
    "opcode", "case_id", "flags", "ptype", "sctype", "atmosphere",
    "nightzone", "ip_targetted", "nearstar_owner", "nearstar_class",
    "global_surface_seed", "albedo", "rainy_bits", "sky_brightness_in",
    "sky_red_filter", "sky_grn_filter", "sky_blu_filter",
    "gnd_red_filter", "gnd_grn_filter", "gnd_blu_filter", "dsd1_bits",
    "exposure_bits", "landing_pt_lat", "quadwords_in", "tail_mode",
    "tail_seed", "bg_start", "bg_shift", "bg_bytes",
)

SIGNED_FIELDS = {
    "ptype", "sctype", "atmosphere", "nightzone", "ip_targetted",
    "nearstar_owner", "nearstar_class", "albedo", "sky_red_filter",
    "sky_grn_filter", "sky_blu_filter", "gnd_red_filter",
    "gnd_grn_filter", "gnd_blu_filter", "landing_pt_lat", "bg_start",
}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANCHOR_SBG = os.path.join(ROOT, "tests", "gen", "recon_w7b", "out",
                          "t3_equator.s_background")
ANCHOR_BMP = os.path.join(ROOT, "tests", "gen", "recon_w7b", "out",
                          "t3_equator.shot.BMP")
ANCHOR_SBG_SHA256 = "e140cde39ef27240f9a8a5ba4a420c66b0a3e55acb01f5b3434895e5963aba01"
ANCHOR_PALETTE_SHA256 = "8fe2f8a9d2e3e7fc262133d8fa1cf9062306f20a7ac9388ae9693b74637ff5b1"


def u32(v):
    return int(v) & M32


def i32(v):
    v = u32(v)
    return v - 0x100000000 if v & 0x80000000 else v


def fbits(v):
    return struct.unpack("<I", struct.pack("<f", float(v)))[0]


def from_fbits(v):
    return struct.unpack("<f", struct.pack("<I", u32(v)))[0]


def fnv_u32(h, v):
    v = u32(v)
    for _ in range(4):
        h = ((h ^ (v & 255)) * FNV_PRIME) & M32
        v >>= 8
    return h


def fnv_bytes(data):
    h = FNV_OFF
    for v in bytes(data):
        h = ((h ^ v) * FNV_PRIME) & M32
    return h


def sha256(data):
    return hashlib.sha256(bytes(data)).hexdigest()


def _f(v):
    """Store an expression to a source ``float`` object."""
    return f32(ext(fr(v)))


def _fast_f32(v):
    """Binary32 store for high-volume sites whose RHS is binary64-typed.

    ``cloudy_sky`` calls libm ``sqrt`` (a double result) and stores after
    each compound assignment; the horizon RHS is an exactly representable
    integer promoted to float.  A native binary64 evaluation followed by this
    store therefore has the same required narrowing without constructing a
    Fraction tens of thousands of times.
    """
    return struct.unpack("<f", struct.pack("<f", float(v)))[0]


def _fmul(a, b):
    """One source float multiplication, including its binary32 result.

    NIV+'s un-suffixed decimal constants promote a chain to double, in which
    case callers use one final ``_f`` store.  This helper is only for the
    all-float/integer expressions whose C result type remains float.
    """
    return _f(float(a) * float(b))


def _chop(v):
    return int(v) if v >= 0 else -int(-v)


def _pack_bytes(data):
    data = bytes(data)
    pad = (-len(data)) & 3
    if pad:
        data += b"\0" * pad
    return list(struct.unpack("<%dI" % (len(data) // 4), data))


def _unpack_units(units, nbytes):
    raw = struct.pack("<%dI" % len(units), *[u32(x) for x in units])
    return raw[:nbytes]


class BrtlLedger:
    def __init__(self):
        self.g = Brtl()
        self.n = 0
        self.h = FNV_OFF

    @property
    def state(self):
        return self.g.state & M32

    def srand(self, seed):
        self.g.srand(seed)

    def random(self, n):
        v = self.g.random(int(n))
        self.n += 1
        self.h = fnv_u32(self.h, v)
        return v

    def flandom(self):
        return _f(float(self.random(32767)) * 0.000030518)


class FastLedger:
    def __init__(self):
        self.s = 0
        self.n = 0
        self.h = FNV_OFF

    @property
    def state(self):
        return self.s & M32

    def srand(self, seed):
        s = u32(seed)
        self.s = (s & 0xFFFF0000) | ((s & M16) | 3)

    def random(self, mask):
        p = self.s * self.s
        eax = p & M32
        edx = (p >> 32) & M32
        eax = (eax & 0xFFFFFF00) | ((eax + edx) & 255)
        self.s = (self.s + eax) & M32
        v = eax & u32(mask)
        self.n += 1
        self.h = fnv_u32(self.h, v)
        return v

    def flandom(self):
        return _f(float(self.random(32767)) * 0.000030518)


class Workspace:
    """Logical SBG, readable hostile tail, write accounting and canary."""
    def __init__(self, fill, tail_mode, tail_seed):
        self.data = bytearray([fill & 255] * ST_BYTES)
        if tail_mode:
            self.tail = bytearray((tail_seed + 73 * i + ((i * i) >> 1)) & 255
                                  for i in range(TAIL_BYTES))
        else:
            self.tail = bytearray(TAIL_BYTES)
        self.data.extend(self.tail)
        self.canary = bytes.fromhex("d3 71 4a c9 26 8e 5b f0 19 a7 63 bc 40 2d e1 95")
        # The tested operation begins with the caller's source `_fmemset`.
        # It is a semantic SBG write and therefore belongs in GUARDS even
        # though ENTRY observes the already-filled page.
        self.min_write = 0
        self.max_write = ST_BYTES - 1
        self.writes = ST_BYTES
        self.oob_writes = 0
        self.tail_before = fnv_bytes(self.tail)
        self.canary_before = fnv_bytes(self.canary)

    def write(self, p, v):
        if 0 <= p < ST_BYTES:
            self.data[p] = v & 255
            self.min_write = p if self.min_write == M32 else min(self.min_write, p)
            self.max_write = p if self.max_write == M32 else max(self.max_write, p)
            self.writes += 1
        else:
            self.oob_writes += 1

    def sky(self):
        return bytes(self.data[:ST_BYTES])

    def guards(self, qw_before, qw_after):
        return [self.min_write, self.max_write, self.writes, self.oob_writes,
                self.tail_before, fnv_bytes(self.data[ST_BYTES:ST_BYTES + TAIL_BYTES]),
                self.canary_before, fnv_bytes(self.canary),
                u32(qw_before), u32(qw_after)]


def _ld32(a, p):
    return (a[p] | (a[p + 1] << 8) | (a[p + 2] << 16) | (a[p + 3] << 24))


def ssmooth(w, stride=360):
    """Exact in-place DOS dword-carry smoother from delivered ``susm``."""
    n = ST_BYTES - 4 * stride
    p = stride
    for _ in range(n):
        e = (_ld32(w.data, p - stride) + _ld32(w.data, p)
             + _ld32(w.data, p + stride) + _ld32(w.data, p + 2 * stride)) & M32
        e = (e & 0xFCFCFCFC) >> 2
        al = ((e & 255) + ((e >> 8) & 255) + ((e >> 16) & 255)
              + ((e >> 24) & 255)) & 255
        w.write(p, al >> 2)
        p += 1


def lssmooth(w):
    """Exact in-place 2x2 smoother, including the 41-byte tail read."""
    n = (ST_BYTES // 4 - 80) * 4
    for p in range(n):
        d0, d1 = w.data[p], w.data[p + 1]
        b0, b1 = w.data[p + 360], w.data[p + 361]
        out = (d0 & 0xC0) | (((d0 & 0x3F) + (d1 & 0x3F)
                              + (b0 & 0x3F) + (b1 & 0x3F)) >> 2)
        w.write(p, out)


def psmooth_grays(w):
    ssmooth(w, 320)


def cloudy_sky(w, B, density, smooths, albedo):
    n = B.random(density + albedo)
    while n > 0:
        cx = B.random(360)
        r = B.random(25) + 5
        cy = B.random(50) + 25 + r
        for yi in range(-r, r):
            for xi in range(-2 * r, 2 * r):
                if math.sqrt(xi * xi * 0.2 + yi * yi) < r:
                    p = (xi + cx + 360 * (yi + cy)) & M16
                    if p < ST_BYTES:
                        den = math.sqrt((xi + r) * (xi + r) +
                                        (yi + r) * (yi + r))
                        b = float("inf") if den == 0 else _fast_f32(1.4142 / den)
                        b = _fast_f32(b * 64.0)
                        b = _fast_f32(b + w.data[p])
                        if b > 63:
                            b = 63.0
                        w.write(p, _chop(b))
        n -= 1
    for _ in range(smooths):
        ssmooth(w)


def cloudy_denominator_bound():
    """Return the exact smallest denominator reachable by cloudy_sky.

    A zero denominator requires ``x=-r,y=-r``.  That point fails the paint
    predicate because ``sqrt(1.2)*r < r`` is false for every positive r.
    Enumerating the source's complete integer radius/domain (r=5..29) gives
    the tight reachable witness denominator 1 at r=5,x=-5,y=-4.
    """
    best = None
    zero_predicate = None
    for r in range(5, 30):
        zx, zy = -r, -r
        zero_predicate = math.sqrt(zx * zx * 0.2 + zy * zy) < r
        if zero_predicate:
            raise AssertionError("zero cloudy denominator became reachable")
        for y in range(-r, r):
            for x in range(-2 * r, 2 * r):
                if math.sqrt(x * x * 0.2 + y * y) < r:
                    q = (x + r) ** 2 + (y + r) ** 2
                    candidate = (q, r, x, y)
                    if best is None or candidate < best:
                        best = candidate
    if best != (1, 5, -5, -4):
        raise AssertionError("cloud denominator bound drift: %r" % (best,))
    return best


def ocean_cloud_radii(case):
    """Source-order radius ledger for an OCEAN corpus row (test witness)."""
    c = normalize_case(case)
    if (c["ptype"], c["sctype"]) != (3, OCEAN):
        raise ValueError("radius witness requires type3 OCEAN")
    B = BrtlLedger(); B.srand(c["global_surface_seed"])
    for _ in range(11):
        B.flandom()
    n = B.random(50 + c["albedo"])
    out = []
    for _ in range(n):
        B.random(360)
        out.append(B.random(25) + 5)
        B.random(50)
    return out


def venus_optional_gates(case):
    """Return the two post-nebular smoother decisions for a type-2 row."""
    c = normalize_case(case)
    if c["ptype"] != 2:
        raise ValueError("Venus gate witness requires ptype 2")
    B = BrtlLedger(); B.srand(c["global_surface_seed"])
    for _ in range(18):
        B.flandom()
    B.random(10000)
    return bool(B.random(2)), bool(B.random(3))


def nebular_sky(w, B):
    ax = B.random(10000) & M16
    cx = ST_BYTES
    p = 0
    while cx:
        ax = (ax + cx) & M16
        sv = ax - 0x10000 if ax & 0x8000 else ax
        prod = (sv * sv) & M32
        dx = (prod >> 16) & M16
        ax = ((prod & M16) + dx) & M16
        w.write(p, ax & 0x3F)
        p += 1
        cx -= 1
    lssmooth(w)
    if B.random(2):
        ssmooth(w)
    if B.random(3):
        psmooth_grays(w)


def apply_horizon(w, nightzone):
    """Caller phase, NOCTIS-1.CPP:3683-3697; not part of create_sky."""
    p = 0
    for row in range(120):
        for _ in range(360):
            v = _fast_f32((w.data[p] * row) / 120.0)
            if nightzone:
                v = _fast_f32(v / 2.0)
            w.write(p, _chop(v))
            p += 1


def horizon_operation_proof():
    """Exhaust the valid horizon domain and expose the killable order bug.

    Reassociating the two floating operations is observationally equivalent
    after the byte chop for every input byte 0..63 and row 0..119, both day
    and night.  It is therefore not a valid mutant.  Performing integer
    division prematurely, ``(b/120)*row``, is killable; the first day witness
    is returned.
    """
    reassociation_diffs = 0
    premature_witness = None
    for night in (0, 1):
        for b in range(64):
            for row in range(120):
                src = _fast_f32(float(b * row))
                src = _fast_f32(src / 120.0)
                alt = _fast_f32(_fast_f32(float(row) / 120.0) * b)
                if night:
                    src = _fast_f32(src / 2.0)
                    alt = _fast_f32(alt / 2.0)
                if _chop(src) != _chop(alt):
                    reassociation_diffs += 1
                premature = (b // 120) * row
                if night:
                    premature //= 2
                if premature_witness is None and _chop(src) != premature:
                    premature_witness = (night, b, row, _chop(src), premature)
    if reassociation_diffs:
        raise AssertionError("horizon reassociation became observable")
    if premature_witness is None:
        raise AssertionError("premature integer horizon division has no witness")
    return reassociation_diffs, premature_witness


def _shade(pal, first, n, sr, sg, sb, er, eg, eb):
    pal.shade(SRFPAL6, first, n, sr, sg, sb, er, eg, eb)


def _colour_factors(case):
    """Evaluate the source locals computed before the planet-type switch."""
    owner = case["nearstar_owner"]
    # NIV+ declares dfs, sb, and saturation as float.  Each initializer and
    # compound assignment therefore spills to binary32 before the next source
    # statement reads it; retaining Python binary64 here masks real palette
    # differences for nontrivial owner/class/rain combinations.
    dfs = _f(1.0 - ((case["ip_targetted"] if owner == -1 else owner) * 0.05))
    atmosphere = case["atmosphere"]
    sb = _f(1.0 if not atmosphere else case["sky_brightness_in"] / 24.0)
    if atmosphere and case["nightzone"]:
        dfs = _f(dfs * 0.5)
    if owner > 2:
        sb = _fmul(sb, _fmul(dfs, dfs))
    else:
        dfs = _f(1.0)
    cls = case["nearstar_class"]
    factors = (1.0, 1.5, 0.5, 0.8, 1.2, 0.1, 0.1, 0.4, 0.9, 1.3, 0.5, 0.2)
    if 0 <= cls < len(factors):
        dfs = _f(dfs * factors[cls])
    sat = _f(1.0 - 0.15 * from_fbits(case["rainy_bits"]))
    return dfs, sb, sat


def _scale_colours(c, case, factors=None):
    # In particular, type 5 mutates the global sky_brightness inside the
    # switch, but the local sb was already frozen above it in NIV+.
    dfs, sb, sat = factors if factors is not None else _colour_factors(case)
    for k in range(4):
        for band in c:
            if band[k] < 0:
                band[k] = 0.0
    if case["ptype"] in (3, 5):
        for k in range(4):
            for band in c:
                band[k] = _f((band[k] - 0.5) * sat + 0.5)
    fr_, fg_, fb_ = c
    for band in (fr_, fg_, fb_):
        band[0] = _fmul(_fmul(band[0], 64.0), dfs)
        band[1] = _fmul(_fmul(_fmul(band[1], 64.0), dfs), sb)
        band[2] = _fmul(_fmul(band[2], 64.0), dfs)
        band[3] = _fmul(_fmul(band[3], 64.0), dfs)


def _make_palette(c, case, defined):
    pal = Palette()
    if not defined:
        return pal
    fr_, fg_, fb_ = c
    atmosphere = case["atmosphere"]
    night = case["nightzone"]
    ptype = case["ptype"]
    if not atmosphere:
        _shade(pal, 64, 64, 0, 0, 0, 100, 110, 120)
    elif night:
        _shade(pal, 64, 64, 0, 0, 0, 60, 62, 64)
        if ptype == 3:
            _shade(pal, 0, 64, 0, 0, 0, 64, 62, 60)
            _shade(pal, 128, 64, 0, 0, 0, 64, 64, 64)
            _shade(pal, 192, 64, 8, 12, 16, 56, 60, 64)
            return pal
        for band in (fr_, fg_, fb_):
            band[0] = _f(band[0] * (0.33 if band is fr_ else 0.44 if band is fg_ else 0.55))
            band[2] = _f(band[2] * (0.33 if band is fr_ else 0.44 if band is fg_ else 0.55))
            band[3] = _f(band[3] * (0.33 if band is fr_ else 0.44 if band is fg_ else 0.55))
    else:
        _shade(pal, 64, 64, 0, 0, 0, fr_[1], fg_[1], fb_[1])

    _shade(pal, 0, 44, 0, 0, 0, fr_[0], fg_[0], fb_[0])
    _shade(pal, 44, 20, fr_[0], fg_[0], fb_[0], fr_[1], fg_[1], fb_[1])
    _shade(pal, 128, 10, 0, 0, 0, fr_[0], fg_[0], fb_[0])
    _shade(pal, 138, 44, fr_[0], fg_[0], fb_[0], fr_[2], fg_[2], fb_[2])
    _shade(pal, 182, 10, fr_[2], fg_[2], fb_[2], fr_[1], fg_[1], fb_[1])
    _shade(pal, 192, 10, 0, 0, 0, fr_[0], fg_[0], fb_[0])
    _shade(pal, 202, 44, fr_[0], fg_[0], fb_[0], fr_[3], fg_[3], fb_[3])
    _shade(pal, 246, 10, fr_[3], fg_[3], fb_[3], fr_[1], fg_[1], fb_[1])
    return pal


def _thermo(case, F, pressure):
    dsd1 = from_fbits(case["dsd1_bits"])
    exposure = from_fbits(case["exposure_bits"])
    temp = _f(90.0 - dsd1 * 0.33)
    if not case["atmosphere"]:
        temp = _f(temp - 44.0)
        temp = _f(temp * abs(temp * 0.44))
        temp = _f(temp * (0.3 if case["nightzone"] else 0.3 + exposure * 0.0077))
    else:
        temp = _f(temp * (0.6 if case["nightzone"] else 0.6 + exposure * 0.0044))
    temp = _f(temp - (0.5 + 0.5 * F.flandom()) * abs(case["landing_pt_lat"] - 60))
    if temp < -269:
        temp = _f(-269 + 4 * F.flandom())
    if case["ptype"] == 2:
        temp = _f(temp + F.flandom() * 150)
    if case["ptype"] == 3:
        lohi = {OCEAN: (10, 60), PLAINS: (-10, 45), DESERT: (20, 80), ICY: (-120, 4)}
        lo, hi = lohi.get(case["sctype"], (-1e30, 1e30))
        guard = 0
        while temp < lo and guard < 100000:
            temp = _f(temp + F.flandom() * 5); guard += 1
        while temp > hi and guard < 100000:
            temp = _f(temp - F.flandom() * 5); guard += 1
        if guard >= 100000:
            raise RuntimeError("temperature convergence guard")
    return pressure, temp


def normalize_case(case):
    missing = [x for x in FIELD_NAMES if x not in case]
    if missing:
        raise ValueError("missing fields: %s" % ", ".join(missing))
    c = {k: int(case[k]) for k in FIELD_NAMES}
    if c["opcode"] != 1 or c["case_id"] == 0:
        raise ValueError("sky rows require opcode=1 and nonzero case_id")
    if c["flags"] & ~KNOWN_FLAGS:
        raise ValueError("unknown flag bits")
    if c["atmosphere"] not in (0, 1) or c["nightzone"] not in (0, 1):
        raise ValueError("noncanonical boolean")
    if c["tail_mode"] not in (0, 1):
        raise ValueError("bad tail_mode")
    if c["flags"] & PALETTE_UNDEFINED and c["flags"] & GRADE_PALETTE:
        raise ValueError("undefined palette cannot be graded")
    if c["bg_bytes"] < 0 or c["bg_bytes"] > OFFSET_MAP_BYTES:
        raise ValueError("bad bg_bytes")
    if c["flags"] & GRADE_PAGE and c["bg_bytes"] != OFFSET_MAP_BYTES:
        raise ValueError("page rows require the complete offsets.map byte bound")
    for k in FIELD_NAMES:
        c[k] = i32(c[k]) if k in SIGNED_FIELDS else u32(c[k])
    return c


@dataclass
class SkyResult:
    case: dict
    pre_horizon: bytes
    final_sbg: bytes
    palette: bytes
    scalars: list
    ledgers: list
    guards: list
    replay_page: bytes = b""
    join_page: bytes = b""


class SkyModel:
    def run(self, raw_case, replay_sbg=None):
        case = normalize_case(raw_case)
        input_case = case
        qw_before = case["quadwords_in"]
        qw = qw_before
        w = Workspace(case["sky_brightness_in"], case["tail_mode"], case["tail_seed"])
        B, F = BrtlLedger(), FastLedger()
        ledgers = []

        def mark(phase):
            ledgers.append([phase, B.n, F.n, B.h, F.h, B.state, F.state,
                            fnv_bytes(w.sky())])

        mark(0)
        B.srand(case["global_surface_seed"])
        F.srand(case["global_surface_seed"])
        mark(1)

        br = _f(case["sky_red_filter"] / 64.0)
        bg = _f(case["sky_grn_filter"] / 64.0)
        bb = _f(case["sky_blu_filter"] / 64.0)
        tr = _f(case["gnd_red_filter"] / 64.0)
        tg = _f(case["gnd_grn_filter"] / 64.0)
        tb = _f(case["gnd_blu_filter"] / 64.0)
        al = float(int(case["albedo"] / 64))  # source integer division
        colour_factors = _colour_factors(case)
        fr_ = [0.0] * 4; fg_ = [0.0] * 4; fb_ = [0.0] * 4
        pressure = 0.0
        defined = True
        ptype, sctype = case["ptype"], case["sctype"]

        if ptype in (1, 4):
            if ptype == 4:
                pressure = _f(F.flandom() * 0.1)
            fr_[0], fg_[0], fb_[0] = tr, tg, tb
            fr_[1] = fg_[1] = fb_[1] = 1.5
            fr_[2], fg_[2], fb_[2] = _f(2 * fr_[0]), _f(2 * fg_[0]), _f(2 * fb_[0])
        elif ptype == 2:
            fr_[0] = _f(1.2 - tr); fg_[0] = _f(1.2 - tg); fb_[0] = _f(1.2 - tb)
            for band, base in ((fr_, tr), (fg_, tg), (fb_, tb)):
                band[1] = _f(base + B.flandom() * .15 - B.flandom() * .15 + .3)
                band[2] = _f(base + B.flandom() * .30 - B.flandom() * .30 + .2)
                band[3] = _f(base + B.flandom() * .45 - B.flandom() * .45 + .1)
            mark(2); nebular_sky(w, B)
            pressure = _f(F.flandom() * 20 + case["albedo"] + 1)
        elif ptype == 3:
            fr_[1] = _f(br * .5 + .5 * B.flandom())
            fg_[1] = _f(bg * .5 + .5 * B.flandom())
            fb_[1] = _f(bb * .5 + .5 * B.flandom())
            if sctype == OCEAN:
                fr_[0] = _f(.65 + .5 * B.flandom()); fg_[0] = _f(.45 + .4 * B.flandom()); fb_[0] = _f(.25 + .3 * B.flandom())
                if fg_[0] < .6: fg_[0] = _f(fg_[0] * 2)
                fr_[2] = _f(.8 * B.flandom()); fg_[2] = _f(.8 * B.flandom()); fb_[2] = _f(fb_[0] * 2 + .4)
                fr_[3] = _f(.2 + B.flandom()); fg_[3] = _f(.4 + B.flandom()); fb_[3] = _f(B.flandom() * .6)
                mark(2); cloudy_sky(w, B, 50, 1, case["albedo"])
            elif sctype == PLAINS:
                fr_[0] = _f(.25 + .5 * B.flandom()); fg_[0] = _f(.50 + .4 * B.flandom()); fb_[0] = _f(.25 + .3 * B.flandom())
                if fg_[0] < .75: fg_[0] = _f(fg_[0] * 1.5)
                fr_[2] = _f(B.flandom() * .4 + fr_[0] * .3)
                fr_[2] = _f(B.flandom() * .7 + fg_[0] * .3)
                fr_[2] = _f(B.flandom() * .2 + fb_[0] * .3)
                fr_[3] = B.flandom(); fg_[3] = B.flandom(); fb_[3] = B.flandom()
                defined = False
                mark(2); cloudy_sky(w, B, 33, 1, case["albedo"])
            elif sctype == DESERT:
                fr_[0] = _f(tr + B.flandom() * .33); fg_[0] = _f(tg + B.flandom() * .25); fb_[0] = _f(tb + B.flandom() * .12)
                fr_[2], fg_[2], fb_[2] = tr, tg, tb
                fr_[3] = _f(.5 * B.flandom()); fg_[3] = _f(.9 * B.flandom()); fb_[3] = _f(.4 * B.flandom())
                mark(2); cloudy_sky(w, B, 10, 1, case["albedo"])
            elif sctype == ICY:
                fr_[0] = _f(.25 + B.flandom()); fg_[0] = _f(.55 + B.flandom()); fb_[0] = _f(1 + B.flandom())
                fr_[2] = _f(fr_[0] * .6); fg_[2] = _f(fg_[0] * .8); fb_[2] = fb_[0]
                fr_[3] = _f(.95 * B.flandom()); fg_[3] = _f(.95 * B.flandom()); fb_[3] = _f(.95 * B.flandom())
                mark(2); cloudy_sky(w, B, 15, 1, case["albedo"])
            else:
                defined = False; mark(2)
            pressure = _f(F.flandom() * .8 + .6)
        elif ptype == 5:
            fr_[0] = _f(tr + .33 * B.flandom() * al); fg_[0] = _f(tg + .33 * B.flandom() * al); fb_[0] = _f(tb + .33 * B.flandom() * al)
            fr_[1] = _f(.8 * tb + .2 * B.flandom() * al); fg_[1] = _f(.8 * tg + .2 * B.flandom() * al); fb_[1] = _f(.8 * tr + .2 * B.flandom() * al)
            fr_[2] = _f(.5 + fr_[0] * .5 * al); fg_[2] = _f(.5 + fg_[0] * .5 * al); fb_[2] = _f(.5 + fb_[0] * .5 * al)
            case = dict(case); case["sky_brightness_in"] = _chop(_f(case["sky_brightness_in"] * .65)) & 255
            mark(2); cloudy_sky(w, B, 10, 2, case["albedo"])
            pressure = _f(F.flandom() * .05 + .01)
        elif ptype in (7, 8):
            pressure = _f(F.flandom() * (.02 if ptype == 7 else 1.0) + (0 if ptype == 7 else .2))
            fr_[0] = _f(tr + B.flandom() * al); fg_[0] = _f(tg + B.flandom() * al); fb_[0] = _f(tb + B.flandom() * al)
            fr_[1], fg_[1], fb_[1] = 1.3, 1.4, 1.5
            fr_[2], fg_[2], fb_[2] = _f(.5 + fr_[0]), _f(.5 + fg_[0]), _f(.5 + fb_[0])
            mark(2)
        else:
            defined = False; mark(2)

        if len(ledgers) == 2: mark(2)
        mark(3)
        _scale_colours((fr_, fg_, fb_), case, colour_factors)
        pal = _make_palette((fr_, fg_, fb_), case, defined)
        palette = bytes(pal.srfpal6) if defined else bytes(768)
        mark(4)
        pressure, temp = _thermo(case, F, pressure)
        mark(5)
        pre = w.sky()
        apply_horizon(w, case["nightzone"])
        mark(6)
        qw = qw_before
        mark(7)
        final = w.sky()
        scalars = [case["sky_brightness_in"], fbits(pressure), fbits(temp),
                   fbits(pressure), fbits(temp), B.state, F.state, B.n, F.n,
                   B.h, F.h, qw]
        guards = w.guards(qw_before, qw)
        replay = join = b""
        if case["flags"] & GRADE_PAGE:
            expected = final if replay_sbg is None else bytes(replay_sbg)
            replay = compose_background(expected, case["bg_start"], case["bg_shift"], case["bg_bytes"])
            join = compose_background(final, case["bg_start"], case["bg_shift"], case["bg_bytes"])
        # META is the 28 input units unchanged.  Type 5 mutates the runtime
        # sky brightness inside create_sky, but must not rewrite its corpus
        # input record.
        return SkyResult(input_case, pre, final, palette, scalars, ledgers, guards,
                         replay, join)


def compose_background(source, start, shift, bg_bytes, offsets_path=None):
    """Independent SP-background replay using the delivered offset asset.

    SP's BP is a DOS segment offset and starts at ``start + 4`` because
    ``SSBG = RSBG - 4``.  The corpus source is raw RSBG byte zero, so prefix
    the four-byte segment header.  ``bg_bytes`` bounds traversal of the
    delivered offsets.map, not the 64,800-byte panorama source.  Passing raw
    SBG directly shifts every source lookup by four.
    """
    from sp_spec import background_raster
    offsets_path = offsets_path or os.path.join(ROOT, "work", "offsets.map")
    with open(offsets_path, "rb") as fh:
        offsets = fh.read()
    if bg_bytes > len(offsets) or bg_bytes & 1:
        raise ValueError("bad offsets.map traversal byte bound")
    src = bytes(4) + bytes(source)
    return background_raster(offsets, bg_bytes, src, start, shift)["page"]


@dataclass
class Record:
    kind: int
    width: int
    height: int
    case_id: int
    phase: int
    body_bytes: int
    sequence: int
    flags: int
    body: list

    def units(self):
        h = [SKY_MAGIC, SKY_VERSION, self.kind, self.width, self.height,
             len(self.body), self.case_id, self.phase, self.body_bytes,
             self.sequence, self.flags, 0, 0, 0, 0, 0]
        return [u32(x) for x in h + self.body]


def result_records(result):
    c = result.case
    seq = 0
    out = []
    def add(kind, width, height, body, body_bytes=None, phase=0):
        nonlocal seq
        bb = len(body) * 4 if body_bytes is None else body_bytes
        out.append(Record(kind, width, height, c["case_id"], phase, bb,
                          seq, c["flags"], [u32(x) for x in body]))
        seq += 1
    meta = [c[x] for x in FIELD_NAMES[1:]]
    add(META, 28, 1, meta)
    add(PRE_HORIZON, 360, 180, _pack_bytes(result.pre_horizon), ST_BYTES)
    add(FINAL_SBG, 360, 180, _pack_bytes(result.final_sbg), ST_BYTES)
    add(PALETTE, 256, 1, _pack_bytes(result.palette), 768)
    add(SCALARS, 12, 1, result.scalars)
    for phase, ledger in enumerate(result.ledgers):
        if ledger[0] != phase:
            raise ValueError("ledger phase drift")
        add(LEDGER, 8, 1, ledger, phase=phase)
    add(GUARDS, 10, 1, result.guards)
    if c["flags"] & GRADE_PAGE:
        add(REPLAY_PAGE, 320, 200, _pack_bytes(result.replay_page), PAGE_BYTES)
        add(JOIN_PAGE, 320, 200, _pack_bytes(result.join_page), PAGE_BYTES)
    add(CASE_END, 0, 0, [], 0)
    return out


def encode_stream(results):
    records = []
    for result in results:
        records.extend(result_records(result))
    trailer = Record(STREAM_END, 4, 1, 0, 0, 16, 0, 0,
                     [len(results), 0, len(records), 0])
    records.append(trailer)
    units = []
    for r in records:
        units.extend(r.units())
    return struct.pack("<%dI" % len(units), *units)


def _decode_records_unchecked(blob):
    if len(blob) & 3:
        raise ValueError("stream length is not u32 aligned")
    units = list(struct.unpack("<%dI" % (len(blob) // 4), blob))
    out, p = [], 0
    while p < len(units):
        if len(units) - p < 16:
            raise ValueError("truncated header")
        h = units[p:p + 16]; p += 16
        if h[0] != SKY_MAGIC or h[1] != SKY_VERSION:
            raise ValueError("bad magic/version")
        if any(h[11:16]):
            raise ValueError("nonzero reserved header")
        n = h[5]
        if len(units) - p < n:
            raise ValueError("truncated body")
        body = units[p:p + n]; p += n
        r = Record(h[2], h[3], h[4], h[6], h[7], h[8], h[9], h[10], body)
        if r.body_bytes > len(body) * 4 or len(body) * 4 - r.body_bytes > 3:
            raise ValueError("bad significant byte count")
        if r.body_bytes & 3 and body:
            used = r.body_bytes & 3
            if body[-1] >> (used * 8):
                raise ValueError("nonzero body padding")
        out.append(r)
    return out


def decode_stream(blob):
    out = _decode_records_unchecked(blob)
    validate_records(out)
    return out


def decode_rejection_stream(blob):
    """Decode the sole permitted diagnostic stream for rejected input.

    Successful streams require trailer ``bad == 0`` and continue through
    ``decode_stream``.  A parser/replay rejection is deliberately disjoint:
    one STREAM_END record, zero cases/records, and a nonzero bad count.  This
    helper never relaxes validation for a stream containing partial records.
    """
    records = _decode_records_unchecked(blob)
    if len(records) != 1:
        raise ValueError("rejection stream contains partial records")
    r = records[0]
    if (r.kind, r.width, r.height, len(r.body), r.body_bytes, r.case_id,
            r.phase, r.sequence, r.flags) != \
            (STREAM_END, 4, 1, 4, 16, 0, 0, 0, 0):
        raise ValueError("bad rejection stream framing")
    if r.body[0] != 0 or r.body[1] == 0 or r.body[2] != 0 or r.body[3] != 0:
        raise ValueError("bad rejection trailer")
    return records


def validate_records(records):
    if not records or records[-1].kind != STREAM_END:
        raise ValueError("missing stream end")
    dims = {
        META: (28, 1, 28, 112),
        PRE_HORIZON: (360, 180, ST_BYTES // 4, ST_BYTES),
        FINAL_SBG: (360, 180, ST_BYTES // 4, ST_BYTES),
        PALETTE: (256, 1, 768 // 4, 768),
        SCALARS: (12, 1, 12, 48),
        LEDGER: (8, 1, 8, 32),
        GUARDS: (10, 1, 10, 40),
        REPLAY_PAGE: (320, 200, PAGE_BYTES // 4, PAGE_BYTES),
        JOIN_PAGE: (320, 200, PAGE_BYTES // 4, PAGE_BYTES),
        CASE_END: (0, 0, 0, 0),
    }
    case_count = 0; record_count = 0; current = None; current_flags = 0
    seq = 0; phases = []
    kinds = []
    for r in records[:-1]:
        record_count += 1
        if r.kind not in dims:
            raise ValueError("unknown record kind %d" % r.kind)
        want = dims[r.kind]
        got = (r.width, r.height, len(r.body), r.body_bytes)
        if got != want:
            raise ValueError("kind %d dimensions/body %r != %r" %
                             (r.kind, got, want))
        if current is None:
            if r.kind != META or r.sequence != 0:
                raise ValueError("case must begin with META sequence 0")
            current = r.case_id; seq = 0; phases = []
            current_flags = r.flags
            kinds = []
            if r.body[0] != r.case_id or r.body[1] != r.flags:
                raise ValueError("META/header id or flags drift")
        if r.case_id != current or r.flags != current_flags or r.sequence != seq:
            raise ValueError("case id/sequence drift")
        seq += 1
        kinds.append(r.kind)
        if r.kind == LEDGER:
            if r.phase >= 8 or r.body[0] != r.phase:
                raise ValueError("ledger header/body phase drift")
            phases.append(r.phase)
        if r.kind == CASE_END:
            if phases != list(range(8)):
                raise ValueError("ledger phases missing/out of order")
            base = [META, PRE_HORIZON, FINAL_SBG, PALETTE, SCALARS] \
                   + [LEDGER] * 8 + [GUARDS]
            pages = [REPLAY_PAGE, JOIN_PAGE] if r.flags & GRADE_PAGE else []
            if kinds != base + pages + [CASE_END]:
                raise ValueError("case record order/optional pages drift")
            current = None; case_count += 1
    if current is not None:
        raise ValueError("unterminated case")
    t = records[-1]
    if (t.width, t.height, len(t.body), t.body_bytes, t.case_id, t.phase,
            t.sequence, t.flags) != (4, 1, 4, 16, 0, 0, 0, 0):
        raise ValueError("bad stream-end framing")
    if t.body != [case_count, 0, record_count, 0]:
        raise ValueError("bad stream trailer")


def fixture_palette_from_bmp(path=ANCHOR_BMP):
    d = open(path, "rb").read()
    if d[:2] != b"BM" or len(d) < 1078:
        raise ValueError("bad anchor BMP")
    out = bytearray()
    for i in range(256):
        b, g, r, _ = d[54 + i * 4:58 + i * 4]
        if (r | g | b) & 3:
            raise ValueError("BMP palette is not exact DAC*4")
        out.extend((r // 4, g // 4, b // 4))
    return bytes(out)


def verify_anchor_assets():
    sbg = open(ANCHOR_SBG, "rb").read()
    pal = fixture_palette_from_bmp()
    if len(sbg) != ST_BYTES or sha256(sbg) != ANCHOR_SBG_SHA256:
        raise ValueError("anchor SBG hash/length drift")
    if len(pal) != 768 or sha256(pal) != ANCHOR_PALETTE_SHA256:
        raise ValueError("anchor palette hash/length drift")
    # Strong branch falsifier: the captured palette is exactly the four
    # special-night calls, independent of any RAM symbol interpretation.
    p = Palette()
    _shade(p, 64, 64, 0, 0, 0, 60, 62, 64)
    _shade(p, 0, 64, 0, 0, 0, 64, 62, 60)
    _shade(p, 128, 64, 0, 0, 0, 64, 64, 64)
    _shade(p, 192, 64, 8, 12, 16, 56, 60, 64)
    if bytes(p.srfpal6) != pal:
        raise ValueError("captured palette is not special-night branch")
    return sbg, pal


if __name__ == "__main__":
    sbg, pal = verify_anchor_assets()
    print("anchor SBG %d %s" % (len(sbg), sha256(sbg)))
    print("anchor palette %d %s (special-night exact)" % (len(pal), sha256(pal)))
