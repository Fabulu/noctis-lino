"""w5spec - an independent model of the Wave 5 buffer model and framebuffer.

Written from the 1996 sources and from docs-notes/BUFFERMODEL.md, and from
nothing else. In particular it is NOT written from tests/w5probe.txt, from
work/fb*.txt, or from noctis-harness/fb_*.{py,c}: those are the things it
grades. Where a number could have been copied it is derived instead --
the layout is parsed out of NOCTIS-D.H and NOCTIS.CPP rather than typed in,
so a change to either source moves this model and the lino independently.

Sources, by line:

  NOCTIS-D.H:25-56        the nine buffer sizes
  NOCTIS.CPP:2163-2172    the farmalloc order, and the two DOS aliases
                          (ruinschart = objectschart, txtr = p_background,
                          digimap2 = &n_globes_map[gl_bytes])
  NOCTIS-0.CPP:53         adapted's neighbour is the VGA segment 0xA0000000
  NOCTIS-0.CPP:166        range8088, the fixed greyscale ramp
  NOCTIS-0.CPP:179        tavola_colori: copy, filter in place, upload from 0
  NOCTIS-0.CPP:1151       shade: truncating, binary32 accumulators
  NOCTIS.CPP:614-628      digit_at, which writes txtr[-6..-1]
  NOCTIS.CPP:3779-3784    the background colour cycle, over s_background
  NOCTIS-D.H:171-176      the quadrant bitfield order
  TDPOLYGS.H:2817-2821    the 16-bit texel address

The tick model is arithmetic, not documentary: the period is the exact
rational 65536/1193182 s expressed in timer counts, and the model
enumerates the same recurrence with Python's unbounded integers, which is
a genuinely different construction from the lino's 32-bit one.
"""

import os
import re
import struct

M32 = 0xFFFFFFFF

# ---------------------------------------------------------------- the layout

# Borland's far-heap block header. Not measured; recorded as an assumption
# in BUFFERMODEL.md section 3 and used identically by both sides.
PAD = 16
# The pad below the first region. digit_at is not the reason (its txtr is
# p_surfacemap, whose underflow lands in p_background's trailing pad) -- the
# reason is that a region must never be the first thing in the workspace, or
# an underflow walks off the vector instead of into a guard.
LOWPAD = 16

NOCTIS_SRC = r"C:\programmieren\noctis\niv-plus\source"

# farmalloc order, NOCTIS.CPP:2163-2172. The second element is the
# NOCTIS-D.H symbol, or a tuple of symbols to add.
FARMALLOC = [
    ("n_offsets_map", ("om_bytes",)),
    ("n_globes_map", ("gl_bytes", "gl_brest")),
    ("s_background", ("st_bytes",)),
    ("p_background", ("pl_bytes",)),
    ("p_surfacemap", ("ps_bytes",)),
    ("objectschart", ("oc_bytes",)),
    ("pvfile", ("pv_bytes",)),
    ("adapted", ("sc_bytes",)),
    # adaptor has no farmalloc: it is the literal far pointer 0xA0000000
    # (NOCTIS-0.CPP:53). It is placed last and sized like adapted, because
    # mask_pixels wraps a 16-bit DI through it and nothing overruns into it.
    ("adaptor", ("sc_bytes",)),
]


def parse_sizes(src_dir=NOCTIS_SRC):
    """The nine sizes, parsed out of NOCTIS-D.H. Returns None if absent."""
    path = os.path.join(src_dir, "NOCTIS-D.H")
    if not os.path.exists(path):
        return None
    text = open(path, "r", encoding="latin-1").read()
    out = {}
    for m in re.finditer(r"#define\s+(\w+)\s+(\d+)", text):
        out[m.group(1)] = int(m.group(2))
    return out


def parse_farmalloc_order(src_dir=NOCTIS_SRC):
    """The allocation order, read back out of NOCTIS.CPP. Returns None if absent.

    This exists so that "the layout is in farmalloc order" is checked against
    the original rather than asserted: if main() ever allocated in a different
    order than FARMALLOC says, this disagrees and the test fails.
    """
    path = os.path.join(src_dir, "NOCTIS.CPP")
    if not os.path.exists(path):
        return None
    hits = []
    for lineno, line in enumerate(open(path, "r", encoding="latin-1"), 1):
        m = re.search(r"(\w+)\s*=\s*\([^)]*\)\s*farmalloc\s*\(([^;]*)\);", line)
        if m:
            hits.append((lineno, m.group(1), m.group(2)))
    # NOCTIS.CPP:501 re-allocates `adapted` on its own in the restart path,
    # so take the contiguous block -- the one main() runs, at :2163-2171.
    block = []
    for h in hits:
        if block and h[0] - block[-1][0] > 3:
            block = []
        block.append(h)
        if len(block) >= len(FARMALLOC) - 1:
            break
    return [(n, a) for _, n, a in block]


ROLTAIL, ROLSUB = 0, 1
ZHALF = PAD // 2
PGUARD = 0xA5A5A5A5      # the TAIL magic: pure guard band
PALLOW = 0x5A5A5A5A      # the SUB magic:  guard band WITH an allowance list


class Layout(object):
    """base / size / trailing-pad for every region, plus the two low pads.

    From Wave 5b this also carries the ZONE table, which is what defect 3
    is about. The 16-unit pads had two mutually exclusive jobs: a guard
    band, where any write is a violation, and the legitimate destination
    for digit_at's txtr[-6..-1] (NOCTIS.CPP:614-628, txtr = p_surfacemap,
    landing in nw[170550..170555]). So the first cockpit glyph of a debug
    build fired the canary and halted, and a legitimate write could not be
    told from an overrun.

    The two jobs are separated by splitting every pad into two zones and
    giving each zone an explicit ALLOWANCE LIST:

      TAIL  the low 8 units, immediately ABOVE region p-2
      SUB   the high 8 units, immediately BELOW region p-1

    An allowance unit is COUNTED, never flagged; every other unit is a
    guard. Three allowance entries exist and each is derived here rather
    than copied:

      SUB+4..+7 of every owned SUB except adaptor's -- these are the
          region's DOS segment offsets 0..3. Every farmalloc'd block's
          segment origin is base-4 (BUFFERMODEL section 3), so a 16-bit
          index that wraps to a small offset lands here by construction.
          adaptor is excluded: it is the literal far pointer A000:0000,
          so its segment offset 0 IS its base and its SUB is pure guard.
      SUB+2..+7 of p_surfacemap's SUB -- digit_at, NOCTIS.CPP:614-628.
      TAIL+0 of pvfile's TAIL -- loadpv, NOCTIS-0.CPP:2383-2391.
    """

    def __init__(self, sizes):
        self.sizes = sizes
        self.regions = []
        base = LOWPAD + PAD
        for rid, (name, syms) in enumerate(FARMALLOC):
            size = sum(sizes[s] for s in syms)
            self.regions.append(dict(id=rid, name=name, base=base, size=size,
                                     end=base + size, pad=base + size,
                                     seg=(base - 4) if name != "adaptor" else base))
            base = base + size + PAD
        self.top = base
        # every pad in the workspace, low ones first
        self.pads = [0, LOWPAD] + [r["pad"] for r in self.regions]
        self.zones = [self.zone(p, r) for p in range(len(self.pads))
                      for r in (ROLTAIL, ROLSUB)]

    def zone(self, pad, role):
        """One zone, derived from the pad list. zi = 2*pad + role."""
        base = self.pads[pad] + (0 if role == ROLTAIL else ZHALF)
        if role == ROLTAIL:
            owner = pad - 2 if pad >= 2 else -1
        else:
            # pad 9's SUB is the eight units immediately below adaptor's
            # base, so it is owned; pad 10's SUB is below nothing at all.
            owner = pad - 1 if 1 <= pad <= len(self.regions) else -1
        return dict(zi=2 * pad + role, pad=pad, role=role, base=base,
                    length=ZHALF, owner=owner, mask=self.allow(owner, role))

    @staticmethod
    def allow(owner, role):
        """The 8-bit allowance mask. Bit u set == unit u is legitimate."""
        if owner < 0:
            return 0
        if role == ROLTAIL:
            return 1 if owner == 6 else 0          # loadpv, pvfile
        m = 0 if owner == 8 else 240               # segment offsets 0..3
        if owner == 4:
            m |= 252                               # digit_at, p_surfacemap
        return m

    def magic(self, role):
        return PGUARD if role == ROLTAIL else PALLOW

    def zone_of(self, off):
        for z in self.zones:
            if z["base"] <= off < z["base"] + z["length"]:
                return z
        return None

    def __getitem__(self, name):
        for r in self.regions:
            if r["name"] == name:
                return r
        raise KeyError(name)

    def region_of(self, off):
        for r in self.regions:
            if r["base"] <= off < r["end"]:
                return r
        return None


# ------------------------------------------------------------ byte semantics

def put_byte(v):
    """A C store to a char: 300 -> 44, -1 -> 255."""
    return v & 255


def sx8(v):
    """8 -> 32 sign extension. n_globes_map is `char` and is right-shifted."""
    v &= 255
    return v - 256 if v & 128 else v


def quad_get(byte, field):
    """NOCTIS-D.H:171-176: nr_of_objects 0-1, obj0 2-3, obj1 4-5, obj2 6-7."""
    return (byte >> (2 * field)) & 3


def quad_set(byte, field, value):
    sh = 2 * field
    return (byte & ~(3 << sh) & 255) | ((value & 3) << sh)


def texel(u, v):
    """TDPOLYGS.H:2817-2821, built in the 16-bit BX."""
    return ((v >> 8) & 255) * 256 + ((u >> 8) & 255)


# ------------------------------------------------------------- the framebuffer

def f32(x):
    """Round a Python float to binary32, the way a C store to a float does."""
    return struct.unpack("<f", struct.pack("<f", x))[0]


def f32_bits(x):
    return struct.unpack("<I", struct.pack("<f", x))[0]


class Palette(object):
    """pal6 / curpal6 / pal, and the three functions that write them.

    pal6     Noctis's tmppal, the master, six-bit components
    curpal6  what has actually been uploaded; Noctis has no such array
             because in DOS the DAC is the array
    pal      the 256-entry 00RRGGBB LUT, rebuilt from curpal6
    """

    def __init__(self):
        self.pal6 = [0] * 768
        self.curpal6 = [0] * 768
        self.pal = [0] * 256
        # NOCTIS-0.CPP:166 - range8088[3k+0..2] = k
        self.range8088 = [i // 3 for i in range(192)]

    # -- NOCTIS-0.CPP:179 ---------------------------------------------------
    def tavola(self, first, n, fr, fg, fb, src=None, self_copy=False):
        """Copy, filter in place, then upload starting at colour ZERO.

        The filters are `signed char` and `temp` is a 16-bit unsigned, so a
        filter above 127 goes negative, becomes a huge unsigned and clamps to
        63 -- the `> 63` test never sees a negative. Reproduced, and the
        out-of-range flag is returned rather than assumed away.
        """
        flags = 0
        f = []
        for bit, raw in enumerate((fr, fg, fb)):
            s = sx8(raw)
            if s < 0 or s > 127:
                flags |= 1 << bit
            f.append(s & 0xFFFF)
        if not self_copy:
            for i in range(n * 3):
                self.pal6[first * 3 + i] = src[i] & 255
        for i in range(n * 3):
            j = first * 3 + i
            t = ((self.pal6[j] & 255) * f[i % 3]) & 0xFFFF
            t //= 63
            if t >= 64:
                t = 63
            self.pal6[j] = t
        self.upload(first + n)
        return flags

    def upload(self, count):
        """The DAC write. tavola_colori's asm tail runs from component 0."""
        for i in range(count * 3):
            self.curpal6[i] = self.pal6[i]
        self.lut(0, count)

    def lut(self, first, n):
        """The ONE place six bits become eight. v*4, so 63 -> 252.

        Chosen because the game's own snapshot() writer scales the DAC by 4,
        which makes this LUT identical to the palette inside the BMPs.
        """
        for i in range(n):
            r = (self.curpal6[(first + i) * 3 + 0] & 63) * 4
            g = (self.curpal6[(first + i) * 3 + 1] & 63) * 4
            b = (self.curpal6[(first + i) * 3 + 2] & 63) * 4
            self.pal[first + i] = (r << 16) | (g << 8) | b

    # -- NOCTIS-0.CPP:1151 --------------------------------------------------
    def shade(self, first, n, start, finish):
        """Truncating, with the original's inverted clamp.

        The running value is a float VARIABLE, so it is narrowed to binary32
        after every +=; the store to the palette is a C float-to-unsigned-char
        conversion, which is a cast, which CHOPS. Rounding to nearest here is
        sabotage 10 and must fail.
        """
        k = f32(1.0 / n)
        cur = [f32(v) for v in start]
        delta = [f32((f32(finish[c]) - f32(start[c])) * k) for c in range(3)]
        for i in range(n):
            for c in range(3):
                v = cur[c]
                if v < 0.0:
                    b = 0
                elif v >= 64.0:
                    b = 63
                else:
                    b = int(v)          # chop toward zero
                self.pal6[(first + i) * 3 + c] = b & 255
                cur[c] = f32(v + delta[c])


def expand(index_page, lut):
    """The present. Read-only on the index page: fb[i] = pal[adaptor[i]].

    BUFFERMODEL.md section 6. Noctis's background colour cycle is NOT fused
    in here: NOCTIS.CPP:3779-3784 cycles s_background, an offscreen map, in
    the sky-palette path -- not the visible page and not once per present.
    """
    return [lut[v & 255] for v in index_page]


def sky_cycle(buf):
    """NOCTIS.CPP:3779-3784, verbatim.

        ig = (s_background[ir]+1) % 64;
        ib = (s_background[ir] >> 6) << 6;
        s_background[ir] = ig + ib;
    """
    return [(((v + 1) % 64) + ((v >> 6) << 6)) & 255 for v in buf]


# ------------------------------------------------------------------- the tick

# 65536 / 1193182 s, the real DOS timer period. NOT 55 ms: 55 is niv-lr's
# rounding at noctis-d.h:174.
PERIOD_NUM = 65536
PERIOD_DEN = 1193182
SUBN = 44505
SUBD = 596591


def period_parts(cpms):
    """55*cpms and 44505*cpms -- the decomposition that does not overflow.

    period = cpms*65536000/1193182 = 55*cpms - cpms*44505/596591.
    The naive cpms*552086 overflows 32 bits; the largest intermediate here
    is 44505*cpms, about 4.0e8 at 9000 counts/ms.
    """
    return 55 * cpms, SUBN * cpms


def grid(cpms, k):
    """Offset of the k'th deadline from the start, in counts, exactly.

    Derived independently of the lino's carried accumulator: after k steps
    the carried numerator is (k*subper) mod SUBD, so the cumulative offset is
    k*base - floor(k*subper/SUBD). Two constructions of the same recurrence.
    """
    base, subper = period_parts(cpms)
    return k * base - (k * subper) // SUBD


def period_ms(cpms):
    base, subper = period_parts(cpms)
    return (base - subper / float(SUBD)) / cpms


def is_late(now, deadline):
    """The wait predicate: THE SIGN OF THE DIFFERENCE, never a compare.

    [Counts] wraps about every 477 s; an unsigned `now >= deadline` collapses
    a run of ticks to nothing at the wrap.
    """
    d = (now - deadline) & M32
    return 0 if d >= 0x80000000 else 1


def wrap_cases(anchors, offsets=(-3, -2, -1, 0, 1, 2, 3)):
    """Every (now, deadline) pair the probe enumerates, and the answer."""
    for a in anchors:
        for off in offsets:
            yield a & M32, (a + off) & M32, (1 if off <= 0 else 0)


def probe_anchors(n, stride=65537, named=(0, 1, 2147483647, 2147483648,
                                          2147483649, 4294967295)):
    """The anchor sequence w5probe.txt sweeps: six by name, then an odd
    stride so that the sweep visits all 2^32 rather than a subrange."""
    out = list(named)
    a = 0
    for _ in range(n):
        out.append(a & M32)
        a = (a + stride) & M32
    return out


def s32(x):
    x &= M32
    return x - 0x100000000 if x >= 0x80000000 else x


# ------------------------------------------------- the canary that can fail
#
# DEFECT 5. FBDUMP kind 6 v1 was 18 units in which both the "expected" and
# the "actual" field held 0xA5A5A5A5, written by construction on BOTH sides.
# A clean run and a build whose canary had been deleted produced a
# bit-identical record, so the check could not fail. This is its replacement:
# four units per pad, none of them a literal, all four derived HERE from the
# layout and never read out of the lino.

CANWIT = 0xB0B32000


def canary_slot(i):
    """w5probe.txt's sweep. Deliberately not fbshell.txt's (7i+1) mod 12.

    mod 12 and not mod 16 because units +12..+15 of a pad are SUB+4..+7, an
    ALLOWANCE by construction: a probe that expected them to fire would be
    asserting the guard model is wrong.
    """
    return (5 * i + 3) % 12


def expected_canary(L):
    """The 44 units of FBDUMP kind 6 v2, from the layout alone."""
    out = []
    for i in range(len(L.pads)):
        slot = canary_slot(i)
        role = ROLTAIL if slot < ZHALF else ROLSUB
        clean = L.magic(role)
        wit = (CANWIT + 17 * i + (clean & 255)) & M32
        out += [clean, wit, i + 1, L.pads[i] + slot]
    return out


def expected_zones(L):
    """The 88 units of FBDUMP kind 9: base, length, owner, role per zone."""
    out = []
    for z in L.zones:
        out += [z["base"] & M32, z["length"], z["owner"] & M32, z["role"]]
    return out


# ------------------------------------- class A: the 16-bit index wrap, for real
#
# CRITICAL 2. Class A used to be "allocate the full segment, 1,540 units, no
# code". AN ALLOCATION SIZE CANNOT REPRODUCE A WRAP: under DOS the write
# folded back to offset 0 of the segment, and under 32-bit unit addressing it
# walks linearly past the region end no matter how the region was sized.
#
# The mechanism is a mask, and it belongs where the ORIGINAL truncates. That
# is not the same place for the two sites, which is why the two failure
# deltas differ and why the difference is a graded quantity.

MASK_ROWS = (0, 360, 720, 36000, 64440)


def mask_cases(nwrap=52, nctl=16):
    """(py, px) exactly as w5probe.txt's battery enumerates them."""
    for py in MASK_ROWS:
        for k in range(1, nwrap + 1):
            yield py, 65536 - k
        for k in range(nctl):
            yield py, 100 + k


def expected_mask(L, nwrap=52, nctl=16):
    """calls / wraps / delta-min / delta-max for spot and cirrus.

    spot    NOCTIS-0.CPP:4485. The truncation point IS the 16-bit DI, formed
            AFTER both adds, so the mask and the address coincide.
    cirrus  NOCTIS-0.CPP:4715. "mov bx,py / add bx,px" truncates in BX and
            only THEN shifts right, so the mask is one step earlier and the
            error a masked-at-the-address implementation makes is HALVED --
            32,768, not 65,536. A single "mask the final index" helper would
            be wrong for cirrus and right for spot, so one delta cannot
            stand in for the other.
    """
    pbg, obj = L["p_background"], L["objectschart"]
    sd, cd, sw, cw, n = [], [], 0, 0, 0
    oob = 0
    for py, px in mask_cases(nwrap, nctl):
        n += 1
        # spot
        naive = (pbg["base"] + py + px) & M32
        if py + px + 4 > 0xFFFF:
            sw += 1
        masked = (pbg["seg"] + ((py + px + 4) & 0xFFFF)) & M32
        d = (naive - masked) & M32
        if d:
            sd.append(d)
        if not (pbg["base"] - ZHALF <= masked < pbg["base"] + pbg["size"]):
            oob += 1
        # cirrus
        naive = (obj["base"] + ((py + px) >> 1)) & M32
        if py + px > 0xFFFF:
            cw += 1
        masked = (obj["seg"] + (((((py + px) & 0xFFFF) >> 1) + 4) & 0xFFFF)) & M32
        d = (naive - masked) & M32
        if d:
            cd.append(d)
        if not (obj["base"] - ZHALF <= masked < obj["base"] + obj["size"]):
            oob += 1
    return dict(calls=n, spot_wraps=sw, cirrus_wraps=cw, oob=oob,
                spot_delta=(min(sd) if sd else 0, max(sd) if sd else 0),
                cirrus_delta=(min(cd) if cd else 0, max(cd) if cd else 0),
                spot_ndiff=len(sd))


# ----------------------------------------- the servo, over a long horizon
#
# CRITICAL 1. [Counts] is 32 bits and wraps every 2^32 counts = 477.3 s at
# 8999 cpms. The old servo divided ([Counts] - [TKsrv0c]) by the milliseconds
# since the START OF THE RUN, so the numerator aliased while the denominator
# grew without bound. The unsigned subtraction was never the bug -- modular
# arithmetic gives the true delta as long as the delta itself is under 2^32.
# The bug was the BRACKET.

SRVMIN, SRVMAX = 4000, 60000
SVWAPPLY, SVWCLLO, SVWCLHI, SVWSHORT, SVWLONG = 0, 1, 2, 3, 4

HOR_FIRE, HOR_WIN, HOR_SETTLE = 85, 14061, 16
HOR_JM, HOR_JP = 40503, 21031

# (C0, true cpms, jitter). Seven wrap phases plus one jittered rate.
HOR_SCEN = [
    (0, 8999, 0),
    (4294967295, 8999, 0),
    (1531079939, 8999, 0),
    (3535163461, 8999, 0),
    (2147483648, 8984, 0),
    (999999937, 9023, 0),
    (0, 1000000, 0),                # past the aliasing boundary
    (271828182, 8999, 1),           # jittered: the rounded divide
    (123456789, 60, 0),             # very slow: the clamp step floor
]

# The window/count pairs the band battery drives, and nothing more: a band
# that accepts everything and a band that rejects everything both pass a
# battery made of only one kind, so three of these are accepted and three
# are refused, and one of the refusals is NEGATIVE.
BAND_CASES = [
    (0, -86395000),          # a midnight straddle: unsigned this reads 4.2e9
    (35996001, 3999),        # one ms under SRVMIN
    (36000000, 4000),        # exactly SRVMIN
    (540000000, 60000),      # exactly SRVMAX
    (540009000, 60001),      # one ms over SRVMAX
    (1000000, 600000),       # long enough for the counter to have aliased
]
BAND_SEED = 9000


def expected_band():
    """(counts, ms, why, cpms after) for every band case, from BAND_SEED."""
    out = []
    for cnt, ms in BAND_CASES:
        c, w = servo_apply(BAND_SEED, cnt & M32, ms & M32)
        out += [cnt & M32, ms & M32, w, c]
    return out


def servo_apply(cpms, cnt, ms):
    """work/fbtick.txt's estimator, re-derived: signed band, rounded divide,
    clamp step with a floor of 1. Returns (cpms, why)."""
    if s32(ms) < SRVMIN:
        return cpms, SVWSHORT
    if s32(ms) > SRVMAX:
        return cpms, SVWLONG
    new = (cnt + ms // 2) // ms
    step = cpms // 100 or 1
    lo, hi, why = cpms - step, cpms + step, SVWAPPLY
    if new < lo:
        new, why = lo, SVWCLLO
    if new > hi:
        new, why = hi, SVWCLHI
    return new, why


def servo_apply_original(cpms, cnt, ms):
    """THE DEFECT, as it shipped: an UNSIGNED band with no upper bound, a
    TRUNCATING divide, and a clamp step with no floor. The positive control."""
    if (ms & M32) < 500:
        return cpms
    new = (cnt & M32) // (ms & M32)
    step = cpms // 100
    lo, hi = cpms - step, cpms + step
    if new < lo:
        new = lo
    if new > hi:
        new = hi
    return new


def hor_sample(c0, cpms, t, k, jit):
    v = (c0 + cpms * t) & M32
    if jit:
        v = (v + ((k * HOR_JM) % HOR_JP) - HOR_JP // 2) & M32
    return v


def expected_horizon(scen=None):
    """Replay every scenario three ways, exactly as w5probe.txt does.

    Returns one dict per scenario. The graded facts are:
      * the WINDOWED leg converges to the true rate and stays there across
        windows that straddle 2^32,
      * the ANCHORED leg through the ORIGINAL estimator is destroyed by the
        same data -- which is what makes the first statement a claim rather
        than a tautology,
      * scenario 6 shows the windowed leg failing too, because SRVMAX is a
        literal rather than anything derived from cpms.
    """
    out = []
    for c0, true, jit in (scen or HOR_SCEN):
        seed = true - true // 25
        # leg 1: windowed, shipped estimator
        cpms, worst, wraps, sub, why, hit, bias = seed, 0, 0, 0, 0, HOR_FIRE, 0
        prev = hor_sample(c0, true, 0, 0, jit)
        t = 0
        for k in range(HOR_FIRE):
            t += HOR_WIN
            cur = hor_sample(c0, true, t, k + 1, jit)
            if cur < prev:
                wraps += 1
            if not jit and ((cur - prev) & M32) != ((HOR_WIN * true) & M32):
                sub += 1
            cpms, w = servo_apply(cpms, (cur - prev) & M32, HOR_WIN)
            why |= 1 << w
            if hit == HOR_FIRE and cpms == true:
                hit = k
            if k >= HOR_SETTLE:
                bias += cpms - true
                worst = max(worst, abs(cpms - true))
            prev = cur
        win, winerr = cpms, worst
        # leg 2: anchored, shipped estimator
        cpms, aworst, t = seed, 0, 0
        for k in range(HOR_FIRE):
            t += HOR_WIN
            cur = hor_sample(c0, true, t, k + 1, jit)
            cpms, _ = servo_apply(cpms, (cur - c0) & M32, t)
            aworst = max(aworst, abs(cpms - true))
        anc, ancerr = cpms, aworst
        # leg 3: anchored, ORIGINAL estimator
        cpms, oworst, t = seed, 0, 0
        for k in range(HOR_FIRE):
            t += HOR_WIN
            cur = hor_sample(c0, true, t, k + 1, jit)
            cpms = servo_apply_original(cpms, (cur - c0) & M32, t)
            oworst = max(oworst, abs(cpms - true))
        out.append(dict(c0=c0, true=true, jit=jit, seed=seed,
                        win=win, winerr=winerr, wraps=wraps, sub=sub,
                        why=why, hit=hit, bias=bias,
                        anc=anc, ancerr=ancerr, old=cpms, olderr=oworst,
                        n=HOR_FIRE, w=HOR_WIN, t=t))
    return out


# --------------------------------------------- the deadline grid, PIECEWISE
#
# cpms changes DURING the soak now: SERVON is a driver constant and the
# reference run sets it low enough that the servo actually fires, which the
# Wave 5 probe never did -- and never firing it in a soak is exactly how the
# wrap shipped. A grid rebuilt with one cpms is therefore wrong. The servo
# log says when the value changed, so the grid is rebuilt piecewise from the
# RAW logs and nothing is taken on trust.

def cpms_schedule(srvlog):
    """[(first tick at which in force, cpms)], from FBDUMP kind 11."""
    n = len(srvlog) // 3
    return [(srvlog[3 * i], srvlog[3 * i + 1]) for i in range(n)]


def cpms_at(sched, tick):
    cur = sched[0][1]
    for t, c in sched:
        if t <= tick:
            cur = c
    return cur


def replay_grid(deadlines, sched, maxmult=8):
    """Reproduce every logged deadline by running fbtick's own recurrence.

    TK advance is  acc += SUBN*cpms; b = acc/SUBD; acc -= b*SUBD;
                   deadline += 55*cpms - b
    with acc CARRIED ACROSS ticks and across changes of cpms. Returns
    (multiples, bad) where bad is the number of deadlines that no number of
    advances reproduces.
    """
    acc, off = 0, 0

    def advance(c):
        nonlocal acc, off
        acc += SUBN * c
        b = acc // SUBD
        acc -= b * SUBD
        off += 55 * c - b

    advance(cpms_at(sched, 0))
    base = (deadlines[0] - off) & M32
    mult, bad = [1], 0
    for i in range(1, len(deadlines)):
        c = cpms_at(sched, i)
        k = 0
        while k < maxmult:
            advance(c)
            k += 1
            if ((base + off) & M32) == deadlines[i]:
                break
        else:
            bad += 1
            mult.append(0)
            continue
        mult.append(k)
    return mult, bad


# ----------------------------------------------------------------- FBDUMP v2

FBMAGIC = 0x46424431
KPAGE, KPAL6, KLUT, KTICK, KLAY, KCAN = 1, 2, 3, 4, 5, 6
KSELF, KFRM, KZONE, KWCNT, KSRVL, KWRAPB = 7, 8, 9, 10, 11, 12
# w5probe.txt's own extensions, above fbmem's namespace
TWKSLF, TWKADV, TWKFB, TWKFRM, TWKSKY = 16, 17, 19, 20, 21
TWKHOR, TWKMSK, TWKBND = 22, 23, 24


def read_fbdump(blob):
    """Walk the stream by header. Returns a list of (kind, w, h, cpms, ticks,
    payload-tuple) in file order; raises on a malformed stream."""
    if len(blob) % 4:
        raise ValueError("FBDUMP length %d is not a whole number of units" % len(blob))
    u = struct.unpack("<%dI" % (len(blob) // 4), blob)
    out = []
    i = 0
    while i < len(u):
        if i + 16 > len(u):
            raise ValueError("truncated header at unit %d" % i)
        if u[i] != FBMAGIC:
            raise ValueError("bad magic %08X at unit %d" % (u[i], i))
        kind, w, h, cnt = u[i + 2], u[i + 3], u[i + 4], u[i + 5]
        if i + 16 + cnt > len(u):
            raise ValueError("record kind %d runs past end of file" % kind)
        out.append((kind, w, h, u[i + 6], u[i + 7], u[i + 16:i + 16 + cnt]))
        i += 16 + cnt
    return out


def by_kind(records):
    d = {}
    for kind, w, h, cpms, ticks, payload in records:
        d.setdefault(kind, []).append(payload)
    return d


# --------------------------------------------------- the probe's own pinned state

# w5probe.txt's index-page pattern. Two-dimensional and not symmetric in x
# and y, so a transposed page or an off-by-one scanline table shows up
# instead of cancelling.
def draw_pattern(w=320, h=200):
    page = [0] * (w * h)
    for y in range(h):
        row = 320 * y
        for x in range(w):
            page[row + x] = (((x * y) >> 4) + 3 * x + 5 * y) & 255
    return page


def expected_pages(lut):
    """adapted, adaptor and fb as w5probe.txt leaves them.

    adapted  drawn, then tinta/escrescenze at 63996..63997 - which under
             farmalloc offset == 4 are VISIBLE PIXELS, row 199 columns
             316-317. niv-lr relocated them to 64000; alias 8 keeps them
             where the original put them, and sabotage 13 is the LR variant.
    adaptor  pcopy of adapted, then vanilla's type-9 substellar poke, which
             writes the VISIBLE page - the reason adaptor cannot be
             optimised away.
    fb       the expand, and nothing else: the index page is not written.
    """
    adapted = draw_pattern()
    adapted[63996] = 211
    adapted[63997] = 212
    adaptor = list(adapted)
    for i in range(64):
        adaptor[320 * 100 + 128 + i] = 255
    return adapted, adaptor, expand(adaptor, lut)


def expected_palette():
    """The pinned palette sequence w5probe.txt runs, step for step.

    Chosen so that every documented trap is exercised at least once and the
    clean run itself carries the evidence: P7 rewrites pal6 192..255 and
    uploads nothing, so pal6 and curpal6 differ in one dump and the
    upload-from-zero rule is observable without comparing two builds.
    """
    p = Palette()
    # P2: a real tavola_colori from range8088. Filter 64 on red makes the
    # "> 63" clamp fire exactly once, at v = 63.
    p.tavola(0, 64, 64, 40, 10, src=p.range8088[:192], self_copy=False)
    # P3: a non-dyadic k
    p.shade(64, 24, (0, 0, 0), (63, 40, 20))
    # P4: descending ramps, so the chop is visible
    p.shade(88, 40, (63, 40, 20), (1, 2, 3))
    # P5: the running value leaves 0..64 at BOTH ends - the inverted clamp
    p.shade(128, 16, (-8, -8, -8), (70, 70, 70))
    # P6: the SELF-COPY form, NOCTIS-0.CPP:5193. Uploads 0..191.
    p.tavola(128, 64, 63, 50, 40, self_copy=True)
    # P7: rewrites pal6 192..255 and uploads NOTHING
    p.shade(192, 64, (0, 0, 0), (63, 63, 63))
    # P8: filter 200 is a NEGATIVE signed char
    flags = p.tavola(0, 8, 200, 100, 5, self_copy=True)
    return p, flags


def expected_sky(n=264):
    buf = [0] * 64800
    for i in range(256):
        buf[i] = i
    return sky_cycle(buf)[:n]
