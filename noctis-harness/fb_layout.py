#!/usr/bin/env python3
"""fb_layout.py -- Wave 5-corrective, implementer 2.

Derives the Noctis workspace layout INDEPENDENTLY, by parsing the 1996 sources:

  * region SIZES come from `#define *_bytes` in NOCTIS-D.H
  * region ORDER comes from the actual farmalloc() call sequence in NOCTIS.CPP
  * `adaptor` is not farmalloc'd; it is the literal far pointer 0xA0000000
    (NOCTIS-0.CPP:53) and is appended last, at a full segment + 4.
  * QUADWORDS's steady state is derived from `QUADWORDS -= 1440` in NOCTIS.CPP,
    not transcribed.  (BUFFERMAP:454 / BUFFERMODEL:166 carry 16000; that is the
    DECLARATION.  The value in force at every pcopy/pclear/mask_pixels call
    site after NOCTIS.CPP:2206 is 14560.)
  * alias 8's address is derived from the `mov es:[0xFA00], al` literal in
    TDPOLYGS.H, not transcribed as "63996".

Nothing here reads LINOBUF.md, work/fb*.txt, or fb_ref.c.  The constants in
LINOBUF.md 2.3 are a PREDICTION that this script either reproduces or refutes.

WAVE 5-CORRECTIVE CHANGES
-------------------------
1. Each 16-unit gap is SPLIT into two 8-unit zones with different owners and
   different poison, because the pads had two mutually exclusive jobs (guard
   band vs. the legitimate destination of digit_at's txtr[-6..-1]):

       gap[k]  = NW[end(k) .. base(k+1)-1]                        16 units
         TAIL(k)   = gap[k] + 0..+7   owned by region k    guard   PGUARD
         SUB(k+1)  = gap[k] + 8..+15  owned by region k+1  allow   PALLOW
                     SUB(k+1)+4..+7 == region k+1's segment offsets 0..3

   11 pads, 22 zones.  A violation and a legitimate write now live in disjoint
   unit sets carrying different poison, so they are distinguishable by
   CONSTRUCTION rather than by a whitelist.

2. Segment origins.  Every farmalloc'd block's segment starts 4 units below its
   base (Borland's far-heap block header; `adaptor` is A000:0000 and starts AT
   its base).  A 16-bit index wrap is taken against the SEGMENT ORIGIN, not the
   buffer base -- `seg_index()` -- which is the primitive class A actually
   needs.  Allocation size cannot reproduce a wrap; an AND can.

3. The canary is a 4-unit-per-pad record every unit of which is read back out
   of the workspace or produced by the walker.  See `canary_v2`.

  python fb_layout.py                 # derive, assert, print the table
  python fb_layout.py --zones         # the 22-zone table
  python fb_layout.py --dump out.bin  # also write FBDUMP kind 5
  python fb_layout.py --break ORDER   # sabotage; assertions must then fail
"""

import argparse
import os
import re
import struct
import sys

# ---------------------------------------------------------------- source paths

NIVPLUS = r"C:\programmieren\noctis\niv-plus\source"
DATA = r"C:\programmieren\noctis\niv-plus\data"

D_H = os.path.join(NIVPLUS, "NOCTIS-D.H")
MAIN_CPP = os.path.join(NIVPLUS, "NOCTIS.CPP")
ZERO_CPP = os.path.join(NIVPLUS, "NOCTIS-0.CPP")
TDP_H = os.path.join(NIVPLUS, "TDPOLYGS.H")
SUPPORTS = os.path.join(DATA, "SUPPORTS.NCT")

# The one design constant that is ours, not the original's: a stand-in for
# Borland's far-heap block header.  16 units, split 8 + 8.
PAD = 16
ZONE = PAD // 2
# A second pad below the first region, so digit_at's txtr[-6..-1] underflow has
# somewhere to land when txtr is based at the very first buffer.
LOWPAD = 16

# Borland's far-heap block header sits immediately below the block, and the
# pointer farmalloc hands back has offset 4 inside its own segment.  This is
# INFERRED, not measured -- see `open item 1` -- but it now has four
# independent source-level witnesses, three of which this file can check:
#   (a) Stick/Segmento's `mov byte ptr es:[di+4], 255`   TDPOLYGS.H:250-258
#   (b) sc_bytes == 65540 == 65536 + 4                   NOCTIS-D.H:47
#   (c) wave()'s `add ax, 4`                             NOCTIS-0.CPP:4583-4588
#   (d) polymap's `mov es:[0xFA00], al` into a 65540-byte page  TDPOLYGS.H:2684
SEG_OFFSET = 4          # farmalloc'd blocks
ADAPTOR_SEG_OFFSET = 0  # adaptor is A000:0000

PGUARD = 0xA5A5A5A5   # poison for a TAIL zone: a write here is a VIOLATION
PALLOW = 0x5A5A5A5A   # poison for a SUB  zone: a write here may be EXPECTED

WRAP16 = 0x10000

BREAKS = {
    # LINOBUF 7 sabotage 9.  NOTE: this is WEAKER than that document claims.
    # NOCTIS-D.H declares om, gl, st, pl, ps, oc, sc, pv -- which differs from
    # farmalloc order ONLY by swapping pvfile and adapted at the tail.  Every
    # class-C neighbour relation in LINOBUF 2.4 involves the first six regions,
    # so declaration order does NOT break the neighbour assertions.  It is
    # caught by L1 alone.  SWAPSEA below is the sabotage that actually
    # exercises L6.
    "ORDER": "lay the regions out in NOCTIS-D.H declaration order, not farmalloc order",
    "SWAPSEA": "put s_background before n_globes_map, so the sea-texture read-overrun no longer lands on its DOS neighbour",
    "NOPAD": "PAD = 0, so the regions abut with no far-heap stand-in",
    "SHRINKADAPTED": "adapted sized 64000 instead of sc_bytes (65540)",
    "CLAMPPBG": "p_background sized 65536 instead of pl_bytes (65552)",
    # -- wave 5-corrective additions --------------------------------------
    "SEGBASE": "segment origin taken at the region BASE instead of base-4  [S-SEGADDR-BASE]",
    "ONEZONE": "one 16-unit zone per pad instead of TAIL+SUB  [S-PAD-ONEMAGIC]",
}

# Sabotages of the LAYOUT itself: Layout.check() must reject every one.
LAYOUT_BREAKS = sorted(BREAKS)

# Sabotages of the WORKSPACE (the walker, the masks, the raster loop).  These
# do not move the layout, so Layout.check() is silent about them by design;
# they are rejected by the canary-v2 record, the wrap counters, the pad
# expectation count and the page compare.  Listed here so nothing is invisible.
WORKSPACE_BREAKS = {
    "NINEWALK": "walk the 9 region pads only, not all 11 pads / 22 zones  [S-PAD-9WALK]",
    "MASKSPOT": "drop the 16-bit store mask at spot  [S-MASK-SPOT]",
    "MASKCIRRUS": "drop the 16-bit store mask at cirrus",
    "MASKCIRRUSADDR": "mask cirrus' ADDRESS instead of its truncation point  [S-MASK-CIRRUS-ADDR]",
    "DIGITN1": "digit_at's raster loop starts at n=1 (niv-lr's bug)  [S-PAD-NODIGIT]",
    "TINTA64000": "alias 8 relocated to 64000 (niv-lr's divergence)",
    "QUADWORDS": "page ops hard-code 64000 bytes",
    "CANSTUBCHECK": "the pad walker never compares  [S-CAN-STUBCHECK]",
    "CANSTUBPOISON": "the pads are never poisoned  [S-CAN-STUBPOISON]",
    "CANCONSTACTUAL": "the canary's `actual` field is a literal  [S-CAN-CONSTACTUAL]",
}

# --------------------------------------------------------------- source parsing


def read_text(path):
    with open(path, "r", encoding="latin-1") as fh:
        return fh.read()


def parse_defines(text):
    """Every `#define NAME <integer literal>` in the header."""
    out = {}
    for m in re.finditer(r"^\s*#define\s+(\w+)\s+(-?\d+)\s*(?://.*)?$", text, re.M):
        out[m.group(1)] = int(m.group(2))
    return out


def parse_farmalloc_order(text, defines):
    """The initial farmalloc() call sequence out of main(), in source order.

    Returns [(pointer_name, size_in_bytes, raw_expression)].
    The size expression is evaluated after stripping C casts and substituting
    the NOCTIS-D.H defines, so the size is derived, never transcribed.

    NOCTIS.CPP has NINE farmalloc calls, not eight: `solong:` at :501
    re-allocates `adapted` after the GOES-net shell-out farfree'd it.  That is
    a re-allocation, not part of the initial heap layout, so the parse takes
    the longest CONTIGUOUS run of calls (gap <= 4 source lines) and requires
    the pointer names in it to be distinct.  Under a flat workspace the
    re-allocation is a no-op: the offset never moves.
    """
    hits = []
    pat = re.compile(r"(\w+)\s*=\s*\([^)]*\)\s*farmalloc\s*\((.*?)\)\s*;")
    for m in pat.finditer(text):
        line = text.count("\n", 0, m.start()) + 1
        hits.append((line, m.group(1), m.group(2)))

    runs, cur = [], []
    for h in hits:
        if cur and h[0] - cur[-1][0] > 4:
            runs.append(cur)
            cur = []
        cur.append(h)
    if cur:
        runs.append(cur)
    run = max(runs, key=len)
    names = [h[1] for h in run]
    if len(set(names)) != len(names):
        raise SystemExit("initial farmalloc run has a repeated pointer: %s" % names)

    order = []
    for _line, name, expr in run:
        clean = re.sub(r"\(\s*unsigned\s*(?:char|int|long)?\s*\)", "", expr)
        clean = re.sub(r"\(\s*(?:int|long|char)\s*\)", "", clean)
        if not re.fullmatch(r"[\w\s+\-*/]+", clean):
            raise SystemExit("unparsable farmalloc size expression: %r" % expr)
        try:
            size = eval(clean, {"__builtins__": {}}, dict(defines))  # noqa: S307
        except Exception as exc:  # pragma: no cover
            raise SystemExit("cannot evaluate %r: %s" % (clean, exc))
        order.append((name, int(size), expr.strip()))
    return order


def parse_adaptor(text):
    """adaptor's literal far pointer, from NOCTIS-0.CPP."""
    m = re.search(
        r"adaptor\s*=\s*\(\s*unsigned\s+char\s+far\s*\*\s*\)\s*(0x[0-9A-Fa-f]+)", text
    )
    if not m:
        raise SystemExit("adaptor's far-pointer declaration not found")
    return int(m.group(1), 16)


def parse_quadwords(zero_text, main_text):
    """QUADWORDS is a VARIABLE.  Derive both values rather than transcribing:
    the declaration in NOCTIS-0.CPP and the `-= 1440` in NOCTIS.CPP that puts
    it in its steady state before any page op the port will ever run.

    Returns (declared, steady).  BUFFERMAP.md:454 and BUFFERMODEL.md:166 both
    compute the mask_pixels DI reach from the DECLARED 16000; at the three real
    call sites it is 14560, and that difference is the whole of class-A site
    A3's reachability.
    """
    m = re.search(r"int\s+QUADWORDS\s*=\s*(\d+)", zero_text)
    if not m:
        raise SystemExit("QUADWORDS declaration not found in NOCTIS-0.CPP")
    declared = int(m.group(1))
    m2 = re.search(r"QUADWORDS\s*-=\s*(\d+)", main_text)
    if not m2:
        raise SystemExit("QUADWORDS -= ... not found in NOCTIS.CPP")
    return declared, declared - int(m2.group(1))


def parse_mask_pixels_start(text):
    """mask_pixels' three call sites all pass `adapted+2880` (NOCTIS.CPP:2577,
    NOCTIS-1.CPP:3998, :4450).  `lds di, target` therefore starts DI at
    2880 + SEG_OFFSET.  Parsed, not transcribed, because the whole of class-A
    site A3's reachability is this number crossed with QUADWORDS."""
    hits = set(int(m.group(1)) for m in
               re.finditer(r"mask_pixels\s*\(\s*adapted\s*\+\s*(\d+)", text))
    if not hits:
        raise SystemExit("no `mask_pixels (adapted+N` call site found")
    return sorted(hits)


def parse_alias8_offset(tdp_text):
    """polymap stashes `tinta` and `escrescenze` on the hidden page with

        asm les ax, dword ptr adapted
        asm mov es:[0xFA00], al
        asm mov es:[0xFA01], al

    ES is the SEGMENT of `adapted`; the pointer's own offset (in AX) is
    discarded.  So the two bytes are at SEGMENT offsets 0xFA00/0xFA01, i.e.
    `adapted[0xFA00 - SEG_OFFSET]`.  This is a segment-relative address, which
    is exactly what `seg_index()` models -- alias 8 is not a special case, it
    is the general primitive with a constant index.

    Returns the raw segment offset, parsed.
    """
    m = re.search(r"mov\s+es:\[\s*(0x[0-9A-Fa-f]+)\s*\]\s*,\s*al", tdp_text)
    if not m:
        raise SystemExit("polymap's `mov es:[0x....], al` not found in TDPOLYGS.H")
    return int(m.group(1), 16)


def parse_screen_bounds(d_h_text):
    """poly3d's visible-area clamp, and stick3d's.  Both are #defines in
    NOCTIS-D.H, and A1's proof rests on the first pair, so parse them."""
    d = parse_defines(d_h_text)
    lar, alt = d["larghezza"], d["altezza"]
    xc, yc = d["x_centro"], d["y_centro"]
    # C integer division truncates toward zero: -306/2 == -153
    poly = (-(lar // 2) + xc, lar // 2 + xc, -(alt // 2) + yc, alt // 2 + yc)
    stick = (d["stk_lbx"], d["stk_ubx"], d["stk_lby"], d["stk_uby"])
    return {"poly": poly, "stick": stick, "centre": (xc, yc),
            "larghezza": lar, "altezza": alt}


# ---------------------------------------------------------- 16-bit primitives


def u16(v):
    """The store mask.  Applied WHERE THE DOS CODE TRUNCATES -- at each
    assignment to a variable DOS declared `unsigned` -- and NOT at the final
    address.  The two are not the same operation:

        ((py+px) mod 65536) >> 1   !=   ((py+px) >> 1) mod 65536

    which is why `cirrus`'s measured error is 32768 and `spot`'s is 65536.
    A single "mask the final index" helper would silently halve cirrus's
    error and still be wrong.
    """
    return v & 0xFFFF


def fnv1a32(units):
    """FNV-1a over a unit sequence, little-endian.  Used to carry the identity
    of a long index sequence in a 1-unit field, so a kind-10 record can say
    WHICH addresses were produced, not only how many wrapped."""
    h = 0x811C9DC5
    for v in units:
        x = v & 0xFFFFFFFF
        for _ in range(4):
            h = ((h ^ (x & 0xFF)) * 0x01000193) & 0xFFFFFFFF
            x >>= 8
    return h


# ------------------------------------------------------------------- the layout


class Region(object):
    __slots__ = ("rid", "name", "base", "size", "padbase", "note", "segoff")

    def __init__(self, rid, name, base, size, padbase, note, segoff):
        self.rid = rid
        self.name = name
        self.base = base
        self.size = size
        self.padbase = padbase
        self.note = note
        self.segoff = segoff

    @property
    def end(self):
        return self.base + self.size

    @property
    def segbase(self):
        """NW index of this region's SEGMENT origin -- the anchor a 16-bit
        index wrap is taken against."""
        return self.base - self.segoff

    @property
    def window_end(self):
        """One past the last NW index a 16-bit index into this segment can
        reach.  NOT the same interval as the buffer: `adapted[65536..65539]`
        (the four units sc_bytes = 65540 exists for) lie OUTSIDE the wrap
        window and are reachable only through the non-truncating path."""
        return self.segbase + WRAP16


class Zone(object):
    """One half of one pad.  TAIL is a guard band; SUB is an allowance area."""
    __slots__ = ("zid", "padindex", "base", "length", "owner", "role")

    def __init__(self, zid, padindex, base, length, owner, role):
        self.zid = zid
        self.padindex = padindex
        self.base = base
        self.length = length
        self.owner = owner          # region id, or -1 for an unowned zone
        self.role = role            # 0 = TAIL (guard), 1 = SUB (allowance)

    @property
    def magic(self):
        return PGUARD if self.role == 0 else PALLOW

    @property
    def rolename(self):
        return "TAIL" if self.role == 0 else "SUB"


# The allowance table.  Three entries, each with its citation.  A SUB unit
# named here is COUNTED when it changes, not forbidden; every other pad unit
# that changes is a violation.
#   `region` may be a name, or "*" meaning every region.
ALLOWANCES = [
    ("p_surfacemap", 1, 2, 7, "digit_at txtr[-6..-1], NOCTIS.CPP:614-628"),
    ("pvfile", 0, 0, 0, "loadpv writes 1 past pvfile_c, NOCTIS-0.CPP:2383-2391 "
                        "(retired when alias 9 re-lays the arena)"),
    ("*", 1, 4, 7, "the region's own segment offsets 0..3"),
]


class Layout(object):
    def __init__(self, breaks=()):
        self.breaks = set(breaks)
        self.d_h_text = read_text(D_H)
        self.defines = parse_defines(self.d_h_text)
        self.alloc = parse_farmalloc_order(read_text(MAIN_CPP), self.defines)
        self.adaptor_fp = parse_adaptor(read_text(ZERO_CPP))
        self.qw_declared, self.qw_steady = parse_quadwords(
            read_text(ZERO_CPP), read_text(MAIN_CPP))
        self.alias8_segoff = parse_alias8_offset(read_text(TDP_H))
        self.bounds = parse_screen_bounds(self.d_h_text)
        self.mp_starts = parse_mask_pixels_start(
            read_text(MAIN_CPP) + read_text(os.path.join(NIVPLUS, "NOCTIS-1.CPP")))

        pad = 0 if "NOPAD" in self.breaks else PAD
        lowpad = 0 if "NOPAD" in self.breaks else LOWPAD

        seq = list(self.alloc)
        if "ORDER" in self.breaks:
            decl = ["n_offsets_map", "n_globes_map", "s_background", "p_background",
                    "p_surfacemap", "objectschart", "adapted", "pvfile"]
            seq.sort(key=lambda t: decl.index(t[0]))
        if "SWAPSEA" in self.breaks:
            i = [t[0] for t in seq].index("n_globes_map")
            seq[i], seq[i + 1] = seq[i + 1], seq[i]

        sc = self.defines["sc_bytes"]
        seq = seq + [("adaptor", sc, "0x%08X (literal far pointer)" % self.adaptor_fp)]

        if "SHRINKADAPTED" in self.breaks:
            seq = [(n, 64000 if n == "adapted" else s, e) for (n, s, e) in seq]
        if "CLAMPPBG" in self.breaks:
            seq = [(n, 65536 if n == "p_background" else s, e) for (n, s, e) in seq]

        self.regions = []
        cur = lowpad
        for rid, (name, size, expr) in enumerate(seq):
            padbase = cur
            cur += pad
            segoff = ADAPTOR_SEG_OFFSET if name == "adaptor" else SEG_OFFSET
            if "SEGBASE" in self.breaks:
                segoff = 0
            self.regions.append(Region(rid, name, cur, size, padbase, expr, segoff))
            cur += size
        self.toppad = cur
        self.top = cur + pad
        self.pad = pad
        self.lowpad = lowpad

        self.by_name = {r.name: r for r in self.regions}
        self._build_zones()

    # -- pads and zones -----------------------------------------------------

    def _build_zones(self):
        """11 pads, 22 zones.  Pad 0 is NW[0..15] (nobody's neighbour on either
        side -- the thing above it is pad 1, not a region); pad 1 is NW[16..31]
        and its SUB carries region 0's segment offsets; pads 2..9 are the eight
        inter-region gaps; pad 10 is the top pad.

        The physical justification for the split is not convenience: in DOS the
        16 bytes between two far-heap blocks ARE the upper block's own header,
        and offset == 4 means the upper block's header occupies the four bytes
        immediately below its base -- exactly the bytes a wrap or a negative
        index reaches.
        """
        self.padbases = [0]
        self.padbases += [r.padbase for r in self.regions]
        self.padbases.append(self.toppad)
        if self.pad == 0:            # NOPAD sabotage: there are no pads
            self.padbases = []
        # dedupe defensively (a zero-size lowpad would collide with pad 1)
        seen, pb = set(), []
        for b in self.padbases:
            if b not in seen:
                seen.add(b)
                pb.append(b)
        self.padbases = pb

        self.zones = []
        nz = 0
        for i, base in enumerate(self.padbases):
            below = [r for r in self.regions if r.end == base]
            above = [r for r in self.regions if r.base == base + self.pad]
            tail_owner = below[0].rid if below else -1
            sub_owner = above[0].rid if above else -1
            if "ONEZONE" in self.breaks:
                # one 16-unit guard zone per pad: a legitimate write and a
                # violation become indistinguishable again
                self.zones.append(Zone(nz, i, base, self.pad, tail_owner, 0))
                nz += 1
                continue
            self.zones.append(Zone(nz, i, base, ZONE, tail_owner, 0))
            nz += 1
            self.zones.append(Zone(nz, i, base + ZONE, ZONE, sub_owner, 1))
            nz += 1

    def zone_of(self, off):
        for z in self.zones:
            if z.base <= off < z.base + z.length:
                return z
        return None

    def allowed(self, zone, off):
        """Is NW[off], inside `zone`, on the allowance list?  Returns the
        citation, or None."""
        rel = off - zone.base
        for name, role, lo, hi, why in ALLOWANCES:
            if role != zone.role:
                continue
            if zone.owner < 0:
                continue
            if name != "*" and self.regions[zone.owner].name != name:
                continue
            if lo <= rel <= hi:
                return why
        return None

    # -- derived constants other modules want -------------------------------

    def base(self, name):
        return self.by_name[name].base

    def segbase(self, name):
        return self.by_name[name].segbase

    def seg_index(self, name, off):
        """The address mask.  NW index of segment offset `off` of `name`, with
        the 16-bit wrap taken AGAINST THE SEGMENT ORIGIN.

            nw = SEG(B) + ((OFF(B) + i) & 65535)      OFF = 4, or 0 for adaptor

        This is the only address primitive class A needs, and it is what
        allocation size cannot do.
        """
        return self.by_name[name].segbase + u16(off)

    def region_at(self, nw):
        """Which region (or pad zone) an NW index lands in.  Used to say where
        an UNMASKED index would have gone."""
        for r in self.regions:
            if r.base <= nw < r.end:
                return r.name
        z = self.zone_of(nw)
        if z is not None:
            return "pad%d.%s" % (z.padindex, z.rolename)
        return "outside NW" if not (0 <= nw < self.top) else "?"

    @property
    def txtr_bases(self):
        """Every base `txtr` is ever set to.  NOCTIS.CPP:2172 (p_background),
        NOCTIS.CPP:614 (p_surfacemap), NOCTIS.CPP:1010 (p_surfacemap+2064),
        NOCTIS-1.CPP (s_background, n_globes_map sea texture)."""
        b = self.base
        return [
            ("p_background", b("p_background")),
            ("s_background", b("s_background")),
            ("n_globes_map", b("n_globes_map")),
            ("p_surfacemap", b("p_surfacemap")),
            ("p_surfacemap+2064", b("p_surfacemap") + 2064),
        ]

    # -- alias 8, derived ---------------------------------------------------

    def alias8(self):
        """polymap's tinta/escrescenze stash.  DERIVED: the asm literal 0xFA00
        parsed out of TDPOLYGS.H, resolved through the same seg_index()
        primitive every other class-A site uses.

        The PLACEMENT arithmetic below reaches Tier 2 (this derivation and
        fb_ref.c's are independent).  Its PREMISE -- SEG_OFFSET == 4 -- does
        not: it is inferred from four source-level witnesses and has never been
        measured.  See `python fb_compare.py --ungraded`.
        """
        nw = self.seg_index("adapted", self.alias8_segoff)
        idx = nw - self.base("adapted")
        return {"segoff": self.alias8_segoff, "nw": nw, "index": idx,
                "row": idx // 320, "col": idx % 320,
                "lr_index": self.alias8_segoff}   # niv-lr's tdpolygs.h:938

    # -- assertions ---------------------------------------------------------

    def check(self):
        """Returns (ok, [messages]).  Every failure is reported, not just the
        first, so a sabotage shows its whole blast radius."""
        msg = []
        ok = True

        def req(cond, text):
            nonlocal ok
            if cond:
                msg.append("  PASS  " + text)
            else:
                ok = False
                msg.append("  FAIL  " + text)

        # L1 -- farmalloc order, taken from the source, is the layout order
        want = [n for (n, _, _) in self.alloc] + ["adaptor"]
        got = [r.name for r in self.regions]
        req(want == got, "L1 layout order == farmalloc order %s" % (want,))

        # L2 -- no region overlaps another, and pads separate them
        for a, b in zip(self.regions, self.regions[1:]):
            req(a.end <= b.padbase, "L2 %s ends %d <= %s pad %d" % (a.name, a.end, b.name, b.padbase))
            req(b.base - a.end == self.pad, "L2 gap %s..%s == PAD" % (a.name, b.name))

        # L3 -- every txtr base has a full 64 KiB readable window inside NW
        for name, base in self.txtr_bases:
            head = self.top - base - 65536
            req(head >= 0, "L3 txtr window fits at %-18s base %6d headroom %+d" % (name, base, head))

        # L4 -- digit_at writes txtr[-6..-1] with txtr == p_surfacemap, and
        # every one of those six units must be in p_surfacemap's SUB zone --
        # NOT in the TAIL of the region below it, which is a guard band.
        ps = self.by_name["p_surfacemap"]
        req(ps.base - 6 >= 0, "L4 p_surfacemap-6 >= 0 (digit_at underflow lands in NW)")
        req(ps.base - 6 >= self.by_name["p_background"].end,
            "L4 p_surfacemap-6 is pad, not live p_background")
        zs = [self.zone_of(ps.base - k) for k in range(1, 7)]
        req(all(z is not None and z.role == 1 and z.owner == ps.rid for z in zs),
            "L4 all six digit_at underflow units are in p_surfacemap's own SUB zone "
            "(NW %d..%d), so a legitimate write can never fire a guard"
            % (ps.base - 6, ps.base - 1))

        # L5 -- class-A CONTAINMENT (a precondition, not the mechanism).
        # adaptor is A000:0000, so its 16-bit window is exactly 65536 units and
        # every masked address in it is a legal store to real VRAM: REQUIRED
        # 65536, delivered 65540, 4 units slack.  BUFFERMODEL 3's mask_pixels
        # justification for this size is void -- see L11.
        for nm in ("adapted", "adaptor"):
            req(self.by_name[nm].size >= 65536, "L5 %s >= 65536 (16-bit window contained)" % nm)
        req(self.by_name["p_background"].size >= 65536, "L5 p_background >= 65536")
        req(self.by_name["adaptor"].segoff == 0,
            "L5 adaptor's segment offset is 0 (A000:0000), so its window is exactly "
            "[base, base+65536) and every masked store is real VRAM")

        # L6 -- the class-C neighbour relations of LINOBUF 2.4
        nb = {r.name: (self.regions[i + 1].name if i + 1 < len(self.regions) else None)
              for i, r in enumerate(self.regions)}
        req(nb["n_globes_map"] == "s_background", "L6 sea texture overrun -> s_background")
        req(nb["s_background"] == "p_background", "L6 globe tapestry +718 / ssmooth +39 -> p_background")
        req(nb["p_surfacemap"] == "objectschart", "L6 hpoint +201 / cockpit texture -> objectschart")

        # L7 -- objectschart is big enough that cirrus' (py+px)>>1 wrap
        # (0..32767, plus the segment's own offset 4) stays inside it.  Note
        # what carries this: the `shr bx,1`, NOT the mask.
        req(self.by_name["objectschart"].size > 32768 + SEG_OFFSET,
            "L7 objectschart > 32772 (cirrus' MASKED bx reach is 0..32767 + segoff)")

        # L8 -- the heap total the original allocated
        heap = sum(r.size for r in self.regions if r.name != "adaptor")
        req(heap == 336480, "L8 farmalloc heap total == 336480 bytes (got %d)" % heap)

        # -- wave 5-corrective ------------------------------------------------

        # L9 -- 11 pads, 22 zones, and every zone's role/owner is derivable
        if self.pad:
            req(len(self.padbases) == 11, "L9 exactly 11 pads (got %d)" % len(self.padbases))
            req(len(self.zones) == 22, "L9 exactly 22 zones (got %d)" % len(self.zones))
            owned = sum(1 for z in self.zones if z.owner >= 0)
            req(owned == 18, "L9 18 of the 22 zones have an owner; 4 (pad 0 both, pad 1 TAIL, "
                             "pad 10 SUB) have none and take an EMPTY allowance list (got %d)" % owned)
            req(all(z.magic in (PGUARD, PALLOW) for z in self.zones),
                "L9 two distinct magics, so a guard unit and an allowance unit are "
                "distinguishable by construction")
            # the split must be exactly aligned with the segment origins
            bad = [r.name for r in self.regions
                   if r.segoff and self.zone_of(r.segbase) is not None
                   and not (self.zone_of(r.segbase).role == 1
                            and self.zone_of(r.segbase).owner == r.rid)]
            req(not bad, "L9 every region's segment origin lies in its OWN SUB zone (%s)"
                % (bad or "all 8 farmalloc'd regions"))

        # L10 -- the wrappable window and the buffer are NOT the same interval.
        # This is the fact the delivered model does not state, and it decides
        # which units a mask can and cannot reach.
        ad = self.by_name["adapted"]
        req(ad.window_end < ad.end,
            "L10 adapted's 16-bit window ends at NW %d, %d units BELOW its end %d -- so "
            "adapted[65536..65539], the four units sc_bytes exists for, are outside the "
            "wrap window" % (ad.window_end, ad.end - ad.window_end, ad.end))
        oc = self.by_name["objectschart"]
        spans = [r.name for r in self.regions if r.base < oc.window_end and r.end > oc.end]
        req("adapted" in spans,
            "L10 objectschart's window runs to NW %d and spans %s -- containment is the "
            "`shr bx,1`, not the mask" % (oc.window_end - 1, ",".join(spans)))

        # L11 -- QUADWORDS.  Derived, and the value that matters is the steady
        # state, not the declaration.
        mp0 = self.mp_starts[0] + SEG_OFFSET
        mp_hi = mp0 + 4 * self.qw_steady - 1
        mp_hi_decl = mp0 + 4 * self.qw_declared - 1
        req(self.qw_declared == 16000 and self.qw_steady == 14560,
            "L11 QUADWORDS declared %d, steady state %d after NOCTIS.CPP's `-= 1440` "
            "(all three mask_pixels call sites pass adapted+%s)"
            % (self.qw_declared, self.qw_steady, self.mp_starts))
        req(mp_hi < 65536,
            "L11 mask_pixels' DI runs %d..%d at the STEADY QUADWORDS -- under 65536, so "
            "class-A site A3's 16-bit DI wrap is PROVEN UNNECESSARY.  At the DECLARED "
            "16000 it would reach %d, and that is the computation BUFFERMAP:454 / "
            "BUFFERMODEL:166 make.  The routine is idempotent anyway "
            "(and 0x3F3F3F3F; add mask)." % (mp0, mp_hi, mp_hi_decl))

        # L12 -- alias 8, derived from the asm literal
        a8 = self.alias8()
        req(a8["index"] == 63996 and (a8["row"], a8["col"]) == (199, 316),
            "L12 alias 8: es:[0x%04X] with segoff %d is adapted[%d] = row %d col %d "
            "(niv-lr relocated it to %d)"
            % (a8["segoff"], self.by_name["adapted"].segoff, a8["index"],
               a8["row"], a8["col"], a8["lr_index"]))
        req(a8["nw"] == self.seg_index("adapted", self.alias8_segoff),
            "L12 alias 8 resolves through the SAME seg_index primitive as every other "
            "class-A site -- it is not a special case")

        # L13 -- A1's bbox proof.  poly3d clamps min/max x,y to the visible
        # area BEFORE mp[] is indexed, so Segmento's riga[] index cannot leave
        # 0..199.  Derived from NOCTIS-D.H, not asserted.
        lbx, ubx, lby, uby = self.bounds["poly"]
        req(0 <= lby and uby <= 199,
            "L13 poly3d's clamp is x in [%d,%d], y in [%d,%d] (larghezza %d altezza %d, "
            "centre %s) -- riga[] index stays in 0..199, so class-A site A1 (Segmento) "
            "is PROVEN UNNECESSARY" % (lbx, ubx, lby, uby, self.bounds["larghezza"],
                                       self.bounds["altezza"], self.bounds["centre"]))
        req(320 * uby + ubx + SEG_OFFSET == 61115,
            "L13 the highest address Segmento can form is riga[%d]+%d+%d = %d, far under "
            "65536" % (uby, ubx, SEG_OFFSET, 320 * uby + ubx + SEG_OFFSET))

        # L14 -- A7's typing requirement.  TDPOLYGS.H:150's `ptr` runs
        # 63680 -> 0 -> "-320"; at 32-bit UNSIGNED that is 4294966976 >= 64000
        # so the loop exits after exactly 200 iterations, identical to DOS.
        # At 32-bit SIGNED it is -320 < 64000 and the loop never ends.
        req(((0 - 320) & 0xFFFFFFFF) >= 64000,
            "L14 A7 reclassified: `ptr` must be UNSIGNED (0-320 = %d >= 64000 -> exits); "
            "signed would loop forever.  One assertion, zero cost."
            % ((0 - 320) & 0xFFFFFFFF))

        return ok, msg

    # -- output -------------------------------------------------------------

    def table(self):
        w = []
        w.append("region          rid    base      size    ends at   pad base   segbase  window end")
        w.append("-" * 92)
        for r in self.regions:
            w.append("%-14s %3d %7d %9d %9d %10d %9d %11d"
                     % (r.name, r.rid, r.base, r.size, r.end, r.padbase, r.segbase, r.window_end))
        w.append("-" * 92)
        w.append("%-14s     %7s %9s %9d" % ("NW top", "", "", self.top))
        w.append("PAD=%d (TAIL %d + SUB %d) LOWPAD=%d  bytes=%d"
                 % (self.pad, ZONE, ZONE, self.lowpad, self.top * 4))
        return "\n".join(w)

    def zone_table(self):
        w = ["zid pad  role  base    len  owner", "-" * 46]
        for z in self.zones:
            own = self.regions[z.owner].name if z.owner >= 0 else "-- none --"
            w.append("%3d %3d  %-4s %7d %4d  %s" % (z.zid, z.padindex, z.rolename,
                                                    z.base, z.length, own))
        w.append("-" * 46)
        w.append("PGUARD %08X in every TAIL, PALLOW %08X in every SUB" % (PGUARD, PALLOW))
        w.append("allowances:")
        for name, role, lo, hi, why in ALLOWANCES:
            w.append("  %-14s %-4s +%d..+%d   %s"
                     % (name, "TAIL" if role == 0 else "SUB", lo, hi, why))
        return "\n".join(w)


# ------------------------------------------------------------------ FBDUMP v2
#
# v1 pinned the CONTAINER and nothing else.  Three changes matter:
#   * version 2;
#   * header unit 8 is a TAG.  Record identity stops depending on emission
#     order, which in v1 was documented only in a comment in one implementer's
#     source file.
#   * kind 5 unit 2 is DEFINED as base+size (the trailing gap base).  v1 named
#     the field and never defined it, and the two sides legally disagreed.

FBD_MAGIC = 0x46424431
FBD_VERSION = 2

KIND_INDEXPAGE = 1
KIND_PALETTE6 = 2
KIND_LUT = 3
KIND_TICKLOG = 4
KIND_LAYOUT = 5
KIND_CANARY = 6
KIND_KSELF = 7
KIND_KFRM = 8
KIND_ZONES = 9
KIND_WRAPCOUNT = 10
KIND_SERVOLOG = 11

KIND_NAME = {
    1: "INDEXPAGE", 2: "PALETTE6", 3: "LUT", 4: "TICKLOG", 5: "LAYOUT",
    6: "CANARY", 7: "KSELF", 8: "KFRM", 9: "ZONES", 10: "WRAPCOUNT",
    11: "SERVOLOG",
}

TAG_NAME = {
    0: "(v1, untagged)",
    1: "adapted", 2: "adaptor", 3: "glyph", 4: "pal6", 5: "curpal6", 6: "lut",
    7: "layout", 8: "canary", 9: "zones", 10: "ticklog", 11: "servolog",
    12: "wrapcount", 13: "selfcheck", 14: "framecost",
}
TAG = {v: k for k, v in TAG_NAME.items() if k}

# kind 7 KSELF: 2 units per field, (field id, value).  Field ids 1..99 are
# NORMATIVE and independently computable, so they are GRADED.  100+ are
# port-local: reported, never graded.
KSELF_FIELD = {
    1: "nw_top",
    2: "zone_count",
    3: "pad_count",
    4: "pad_violations",
    5: "pad_expectation_hits",
    6: "quadwords_steady",
    7: "alias8_nw_index",
    8: "alias8_row",
    9: "alias8_col",
    10: "spot_masked_fnv",
    11: "spot_naive_fnv",
    12: "cirrus_masked_fnv",
    13: "cirrus_naive_fnv",
    14: "glyph_nonzero",
    15: "curpal6_trace_fnv",
    16: "srfpal6_nonzero",
    17: "adapted_fnv",
    18: "adaptor_fnv",
    19: "glyph_fnv",
    20: "canary_v2_bad",
    21: "shade_compound_fnv",
    22: "pal6_trace_fnv",
    23: "upload_spans_fnv",
}


def fbdump_write(path, kind, payload, width=0, height=0, cpms=0, ticks=0, tag=0):
    hdr = [FBD_MAGIC, FBD_VERSION, kind, width, height, len(payload), cpms, ticks,
           tag] + [0] * 7
    with open(path, "wb") as fh:
        fh.write(struct.pack("<16I", *hdr))
        fh.write(struct.pack("<%dI" % len(payload), *[v & 0xFFFFFFFF for v in payload]))


def fbdump_read(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    if len(raw) < 64:
        raise ValueError("%s: shorter than an FBDUMP header" % path)
    hdr = struct.unpack("<16I", raw[:64])
    if hdr[0] != FBD_MAGIC:
        raise ValueError("%s: bad magic %08X" % (path, hdr[0]))
    if hdr[1] not in (1, 2):
        raise ValueError("%s: unsupported version %d" % (path, hdr[1]))
    count = hdr[5]
    body = raw[64:]
    if len(body) < count * 4:
        raise ValueError("%s: truncated, want %d units have %d" % (path, count, len(body) // 4))
    payload = list(struct.unpack("<%dI" % count, body[: count * 4]))
    return {
        "kind": hdr[2], "version": hdr[1], "width": hdr[3], "height": hdr[4],
        "count": count, "cpms": hdr[6], "ticks": hdr[7],
        "tag": hdr[8] if hdr[1] >= 2 else 0,
        "payload": payload, "path": path,
    }


def layout_payload(lay):
    """kind 5: 4 units per region -- base, size, TRAILING GAP BASE (== base +
    size), region id.

    FBDUMP v1 called unit 2 "pad base" and never said which pad.  lino emitted
    base+size, the reference emitted the PRECEDING pad; the geometry was never
    in dispute and both were legal readings of the text.  v2 closes it by
    fiat: unit 2 is base+size.
    """
    out = []
    for r in lay.regions:
        out += [r.base, r.size, r.base + r.size, r.rid]
    return out


def zones_payload(lay):
    """kind 9: 4 units per zone -- base, length, owner region id (0xFFFFFFFF
    for none), role (0 TAIL / 1 SUB)."""
    out = []
    for z in lay.zones:
        out += [z.base, z.length, z.owner & 0xFFFFFFFF, z.role]
    return out


# ------------------------------------------------------------------------ font


def load_digimap2(defines=None):
    """The real 1996 32x36 pilot font, straight out of the shipped
    SUPPORTS.NCT.  off_digimap2 = -60776 from EOF, dm2_bytes = 9360
    (NOCTIS-D.H:83-84), read as 2340 little-endian unsigned longs."""
    if defines is None:
        defines = parse_defines(read_text(D_H))
    off = defines["off_digimap2"]
    n = defines["dm2_bytes"]
    size = os.path.getsize(SUPPORTS)
    start = size + off
    if start < 0 or start + n > size:
        raise SystemExit("SUPPORTS.NCT is %d bytes; offset %d does not fit" % (size, off))
    with open(SUPPORTS, "rb") as fh:
        fh.seek(start)
        raw = fh.read(n)
    return list(struct.unpack("<%dI" % (n // 4), raw))


def load_bmp_header54(defines=None):
    """The 54-byte BMP header snapshot() copies verbatim (header_bmp)."""
    if defines is None:
        defines = parse_defines(read_text(D_H))
    off = defines["header_bmp"]
    size = os.path.getsize(SUPPORTS)
    with open(SUPPORTS, "rb") as fh:
        fh.seek(size + off)
        return fh.read(54)


# ------------------------------------------------------- the workspace model
#
# The Python twin of fb_ref.c's buffer half.  Written from the same 1996
# sources, so C-vs-Python on the page scenario is a real two-implementation
# check on the buffer model itself -- byte semantics, QUADWORDS-limited page
# ops, the 16-bit texel address, digit_at's underflow, the class-C read
# overrun that farmalloc order is supposed to make faithful, and the class-A
# 16-bit index masks.

PP32 = [1 << m for m in range(32)]

# class-A site ids for the kind-10 WRAPCOUNT record
SITE_SPOT = 1
SITE_CIRRUS = 2
SITE_CRATER = 3
SITE_ALIAS8 = 4
SITE_NAME = {1: "spot", 2: "cirrus", 3: "crater", 4: "alias8/polymap"}


class Workspace(object):
    """One Noctis byte per 32-bit unit.  A byte offset IS a unit offset."""

    def __init__(self, lay=None, breaks=()):
        self.lay = lay or Layout([b for b in breaks if b in BREAKS])
        self.breaks = set(breaks)
        self.nw = [0] * self.lay.top
        self.QUADWORDS = self.lay.qw_declared
        self.digimap2 = load_digimap2(self.lay.defines)
        self.lcg = 0
        self.wrap = {}          # site -> [calls, wraps]
        self.masked_idx = {}    # site -> [nw index, ...]
        self.naive_idx = {}
        self.containment = []   # (site, nw, region) for every escape

    # -- byte access --------------------------------------------------------

    def put(self, off, v):
        self.nw[off] = v & 0xFF

    def get(self, off):
        return self.nw[off] & 0xFF

    def get_signed(self, off):
        v = self.get(off)
        return v - 256 if v & 0x80 else v

    def quad_get(self, off, field):
        return (self.get(off) >> (2 * field)) & 3

    def quad_set(self, off, field, v):
        b = self.get(off)
        self.put(off, (b & ~(3 << (2 * field))) | ((v & 3) << (2 * field)))

    # -- Wave 1's Borland LCG, reused not rebuilt ---------------------------

    def srand(self, s):
        self.lcg = s & 0xFFFF

    def rand(self):
        self.lcg = (self.lcg * 0x015A4E35 + 1) & 0xFFFFFFFF
        return (self.lcg >> 16) & 0x7FFF

    # -- page ops, NOCTIS-0.CPP:307-345 -------------------------------------

    def pclear(self, base, pattern):
        n = 64000 if "QUADWORDS" in self.breaks else self.QUADWORDS * 4
        for i in range(n):
            self.nw[base + i] = pattern & 0xFF

    def pcopy(self, dest, sorg):
        n = 64000 if "QUADWORDS" in self.breaks else self.QUADWORDS * 4
        nw = self.nw
        nw[dest:dest + n] = nw[sorg:sorg + n]

    def areaclear(self, base, x, y, l, a, color):
        for j in range(a):
            row = base + 320 * (y + j) + x
            for i in range(l):
                self.nw[row + i] = color & 0xFF

    # -- TDPOLYGS.H:2817-2821, assembled in the 16-bit BX --------------------

    @staticmethod
    def texel_addr(u, v):
        return (((v >> 8) & 0xFF) * 256) + ((u >> 8) & 0xFF)

    # -- class A: the two mask points ---------------------------------------
    #
    # The rule the delivered model does not state: the mask goes WHERE THE DOS
    # CODE TRUNCATES, not at the final address.  spot and cirrus differ in
    # exactly this way, and their measured errors differ accordingly.

    def _count(self, site, masked, naive):
        c = self.wrap.setdefault(site, [0, 0])
        c[0] += 1
        if masked != naive:
            c[1] += 1
            self.containment.append((site, naive, self.lay.region_at(naive)))
        self.masked_idx.setdefault(site, []).append(masked)
        self.naive_idx.setdefault(site, []).append(naive)
        return masked

    def spot_index(self, px, py):
        """NOCTIS-0.CPP:4485.  `les di, p_background; add di, py; add di, px`
        -- DI is 16 bits, and the pointer's own offset 4 is already in it.
        So the truncation is on (4 + py + px)."""
        naive = self.lay.segbase("p_background") + (SEG_OFFSET + py + px)
        if "MASKSPOT" in self.breaks:
            masked = naive
        else:
            masked = self.lay.seg_index("p_background", SEG_OFFSET + py + px)
        return self._count(SITE_SPOT, masked, naive)

    def cirrus_index(self, px, py):
        """NOCTIS-0.CPP:4715.  `mov bx, py; add bx, px; shr bx, 1;
        mov al, es:[bx+di]` -- the truncation is on (py+px) BEFORE the shift,
        and the segment offset is added AFTER.  Masking the final address
        instead halves the error, which is what MASKCIRRUSADDR does."""
        base = self.lay.segbase("objectschart")
        naive = base + SEG_OFFSET + ((py + px) >> 1)
        if "MASKCIRRUSADDR" in self.breaks:
            masked = base + u16(SEG_OFFSET + ((py + px) >> 1))
        elif "MASKCIRRUS" in self.breaks:
            masked = naive
        else:
            masked = base + SEG_OFFSET + (u16(py + px) >> 1)
        return self._count(SITE_CIRRUS, masked, naive)

    def alias8_index(self):
        """polymap's tinta stash: the same primitive with a constant index."""
        a = self.lay.alias8()
        naive = self.lay.base("adapted") + a["segoff"]
        return self._count(SITE_ALIAS8, a["nw"], naive)

    # -- NOCTIS.CPP:604-628 -------------------------------------------------

    def digit_at(self, digit, color, shader):
        txtr = self.lay.base("p_surfacemap")
        # NOCTIS.CPP:605 -- the colour comes from `color`, not from `digit`.
        pixel_color = color % 64
        code = ord(digit) if isinstance(digit, str) else digit
        if not (32 < code <= 96):
            return
        d = (code - 32) * 36
        start = 1 if "DIGITN1" in self.breaks else 0
        for n in range(start, 36):
            i = 256 * n - 5
            self.put(txtr + i - 1, 0)          # txtr[-6] when n == 0
            for m in range(32):
                self.put(txtr + i, pixel_color if (self.digimap2[n + d] & PP32[m]) else 0)
                i += 1
            if shader:
                pixel_color -= 1
        self.put(txtr + 256 * 36 - 6, 0)

    def glyph_plane(self):
        b = self.lay.base("p_surfacemap") - 5
        return [self.get(b + i) for i in range(9216)]

    # -- pads: poison, walk, check ------------------------------------------

    def poison_pads(self):
        for z in self.lay.zones:
            for j in range(z.length):
                self.nw[z.base + j] = z.magic

    def zero_pads(self):
        for z in self.lay.zones:
            for j in range(z.length):
                self.nw[z.base + j] = 0

    def walk_pads(self):
        """The two-sided check.  Returns (violations, expectations, first_diff).

        (i)  VIOLATION -- any unit that is not on the allowance list and no
             longer carries its zone's magic.  Named by region and offset.
        (ii) EXPECTATION -- an allowance-listed unit that is no longer PALLOW.
             COUNTED, not forbidden.  The test asserts the EXACT count, so a
             build that never performs the legitimate write FAILS, and so does
             one that writes the wrong units.  That is a value derived from
             what the program did, not written by construction on both sides.
        """
        violations, expectations, first = [], 0, None
        zones = self.lay.zones
        if "NINEWALK" in self.breaks:
            # walk only the nine region pads (pad indices 1..9): the low pad
            # and the top pad go unwatched, which is exactly what a walker
            # driven off `rtab`'s 9 regions does.
            zones = [z for z in zones if 1 <= z.padindex <= 9]
        for z in zones:
            for j in range(z.length):
                off = z.base + j
                if self.nw[off] == z.magic:
                    continue
                why = self.lay.allowed(z, off)
                if why is not None:
                    expectations += 1
                    continue
                owner = (self.lay.regions[z.owner].name if z.owner >= 0 else "unowned")
                violations.append((off, z.padindex, z.rolename, owner, self.nw[off]))
                if first is None:
                    first = off
        return violations, expectations, first

    # -- the canary, v2 -----------------------------------------------------
    #
    # v1 was 18 units in which BOTH the expected and the actual field were the
    # literal 0xA5A5A5A5, written by construction on both sides.  A clean run
    # and a completely stubbed-out mechanism produced a bit-identical dump.
    # v2 is 4 units per pad, and every one of them is either read back out of
    # the workspace or produced by the walker.

    def probeslot(self, i):
        """The slot sweeps the pad, so a walker that only checks the last unit
        fails.  The +1 is not cosmetic either: with slot 0 on pad 0 (base 0)
        the `at` field is 0 in both the clean and the stubbed case.

        It also SKIPS allowance-listed units -- a probe that lands on one is
        COUNTED rather than flagged, and the record would then read "not fired"
        for a perfectly good walker.  Deriving the slot from the allowance
        table means an implementation with the WRONG table probes a different
        address and the `at` field moves: one more thing this record catches.
        """
        pb = self.lay.padbases[i]
        for k in range(PAD):
            s = ((i * 7) + 1 + k) % PAD
            z = self.lay.zone_of(pb + s)
            if z is None:
                continue
            if self.lay.allowed(z, pb + s) is None:
                return s
        return 0

    @staticmethod
    def witness(i):
        return 0xC0DE0000 | i

    def canary_v2(self):
        """Returns 44 units: per pad (clean_read, dirty_read, fired, at)."""
        out = []
        for i, pb in enumerate(self.lay.padbases):
            slot = self.probeslot(i)
            off = pb + slot
            self.poison_pads()
            if "CANSTUBPOISON" in self.breaks:
                self.zero_pads()
            clean = self.nw[off]
            self.nw[off] = self.witness(i)
            if "CANSTUBCHECK" in self.breaks:
                viol, _exp, first = [], 0, None
            else:
                viol, _exp, first = self.walk_pads()
            dirty = self.nw[off]
            if "CANCONSTACTUAL" in self.breaks:
                # v1's actual defect, transplanted: the "actual" field is
                # written by CONSTRUCTION rather than read back out of NW.
                dirty = self.lay.zone_of(off).magic
            fired = 0
            for (o, padindex, _role, _owner, _v) in viol:
                if o == off:
                    fired = padindex + 1
                    break
            out += [clean, dirty, fired, (first if first is not None else 0)]
        self.zero_pads()
        return out

    # -- the isolated pad probes --------------------------------------------
    #
    # Ordering is normative and unchanged: poison -> probe -> check -> zero ->
    # render.  A release build never poisons, and the graded page records come
    # from the release state.  These two probes are the DEBUG half, and they
    # are deliberately isolated so the counts they produce are exact integers
    # a test can assert rather than "greater than zero".

    def pad_probe_expectation(self):
        """One digit_at glyph column, nothing else.  digit_at's txtr[-6..-1]
        land in p_surfacemap's SUB at +2..+7, which is on the allowance list.
        A conforming build reports 0 violations and EXACTLY 6 expectations.

        A build whose raster loop starts at n = 1 reports 0, not 6: the whole
        underflow belongs to the n = 0 iteration (`i = -5`, and `txtr[i-1]`),
        so niv-lr's bug removes the legitimate write entirely.  The count is a
        value derived from what the program DID; a build that never performs
        the write now FAILS instead of silently passing.
        """
        self.poison_pads()
        self.digit_at('A', 64 + 40, 1)
        v, e, first = self.walk_pads()
        self.zero_pads()
        return len(v), e, first

    def pad_probe_violation(self):
        """One unit written past the end of n_globes_map: exactly one TAIL
        violation, in pad 3, owned by n_globes_map."""
        self.poison_pads()
        r = self.lay.by_name["n_globes_map"]
        self.nw[r.end] = 0xDEADBEEF
        v, e, first = self.walk_pads()
        self.zero_pads()
        return v, e, first

    def canary_v1(self):
        """FBDUMP v1's kind 6, reproduced HERE AND ONLY HERE so that its
        blindness can be demonstrated rather than argued.

        18 units, 2 per region: `expected` is the literal CANARY_MAGIC and
        `actual` is initialised to the same literal and only overwritten if a
        differing unit is found.  Both fields are therefore written by
        construction on both sides, and a build whose check never runs emits a
        bit-identical record to a clean one.  That is MAJOR 5.
        """
        out = []
        # v1 poisoned with ONE magic -- that is the defect being reproduced, so
        # do not poison with the v2 two-magic scheme here or the comparison
        # measures the pad model instead of the record design.
        for z in self.lay.zones:
            for j in range(z.length):
                self.nw[z.base + j] = PGUARD
        if "CANSTUBPOISON" in self.breaks:
            self.zero_pads()
        for r in self.lay.regions:
            actual = PGUARD
            if "CANSTUBCHECK" not in self.breaks:
                for j in range(PAD):
                    v = self.nw[r.padbase + j]
                    if v != PGUARD:
                        actual = v
            out += [PGUARD, actual]
        self.zero_pads()
        return out

    # -- the pinned page scenario -------------------------------------------

    def scenario_page(self):
        """LINOBUF 6.1 SCENARIO "page".  A TEST FIXTURE, not a claim about the
        game.  Every step exists to separate one implementation choice; see
        fb_compare.py --scenario-spec for the normative text.
        """
        L = self.lay
        adapted, adaptor = L.base("adapted"), L.base("adaptor")
        globes, sbg = L.base("n_globes_map"), L.base("s_background")

        # 1 -- the release pad state.  5 of step 4's 32000 texels land in a
        #      pad, so poison left in place changes the page.
        self.zero_pads()

        # 2 -- QUADWORDS.  Steady state DERIVED (`QUADWORDS -= 1440`), not the
        #      magic 16000-1440.  The clear pattern is non-zero so the extent
        #      of the clear is observable at all.
        self.QUADWORDS = L.qw_declared
        self.pclear(adaptor, 0)
        self.QUADWORDS = L.qw_steady
        self.pclear(adapted, 7)

        # 3 -- seed
        self.srand(1996)
        for i in range(32768):
            self.put(globes + i, self.rand() & 63)
        for i in range(4096):
            self.put(sbg + i, 128 + (self.rand() & 63))

        # 4 -- sea texture: V driven past row 127 so texels 32768..65535 read
        #      PAST n_globes_map.  Under farmalloc order that lands on
        #      s_background, which is what DOS gave it.  Class C.
        for i in range(32000):
            u = (i * 517) & 0xFFFF
            v = (i * 1031) & 0xFFFF
            self.put(adapted + i, self.get(globes + self.texel_addr(u, v)))

        # 5 -- the raster loop, from n = 0.  Visible in TWO independent places:
        #      the 256x36 glyph plane, and the six units of p_surfacemap's SUB.
        self.digit_at('A', 64 + 40, 1)
        src = L.base("p_surfacemap") - 5
        for i in range(9216):
            self.put(adapted + 32000 + i, self.get(src + i))

        # 6 -- alias 8, through seg_index.  63996, not 64000.
        a8 = self.alias8_index()
        if "TINTA64000" in self.breaks:
            self.put(adapted + 64000, 0x37)
            self.put(adapted + 64001, 0x5B)
        else:
            self.put(a8, 0x37)
            self.put(a8 + 1, 0x5B)

        # 7 -- the class-A wrap battery, on its real destinations.  Deterministic
        #      corpus; see fb_wrap.py for the reachability measurement.
        self.wrap_battery()

        # 8 -- present.  CORRECTION 5 to the draft fixture: the page flip must
        #      come BEFORE the HUD band, or the band is overwritten by the copy
        #      and the adaptor record is bit-identical to the adapted one --
        #      which it was, measured, so the areaclear graded nothing.
        self.QUADWORDS = L.qw_declared
        self.pcopy(adaptor, adapted)

        # 9 -- vanilla's areaclear writes the VISIBLE page, after the flip
        self.areaclear(adaptor, 2, 191, 316, 7, 64 + 63)

    def wrap_battery(self):
        """The synthetic class-A battery.  Replays the exact `spot` and
        `cirrus` index expressions over a pinned corpus that straddles the
        wrap, on all sides, comparing masked index, naive index and landing
        region.  No renderer needed, and it grades the ARITHMETIC, which is
        the thing being decided.

        The corpus is the escape shape fb_wrap.py measures on the real
        generator: px just below zero (stored to an `unsigned`, so 65536-k)
        with py = 360*row.
        """
        for row in range(0, 180, 12):
            py = u16(360 * row)
            for k in range(1, 33):
                px = u16(-k)             # cx + g*cos(a) with cx < g
                self.put(self.spot_index(px, py), 0x3E)
            for k in range(1, 17):
                px = u16(-k)
                self.put(self.cirrus_index(px, py), 0x1F)
        # and the in-range control, which must NOT wrap
        for row in range(0, 180, 12):
            py = u16(360 * row)
            for px in (0, 1, 179, 359):
                self.put(self.spot_index(px, py), 0x3E)
                self.put(self.cirrus_index(px, py), 0x1F)

    def page(self, name):
        b = self.lay.base(name)
        return [self.get(b + i) for i in range(64000)]

    # -- records ------------------------------------------------------------

    def wrapcount_payload(self):
        """kind 10: 3 units per site -- (site id, calls, wraps)."""
        out = []
        for site in sorted(self.wrap):
            c = self.wrap[site]
            out += [site, c[0], c[1]]
        return out

    def kself_payload(self, extra=None):
        """kind 7: 2 units per field.  Ids 1..99 are normative and graded."""
        L = self.lay
        a8 = L.alias8()
        nviol, exp, _ = self.pad_probe_expectation()
        glyph = self.glyph_plane()
        f = {
            1: L.top, 2: len(L.zones), 3: len(L.padbases),
            4: nviol, 5: exp, 6: L.qw_steady,
            7: a8["nw"], 8: a8["row"], 9: a8["col"],
            10: fnv1a32(self.masked_idx.get(SITE_SPOT, [])),
            11: fnv1a32(self.naive_idx.get(SITE_SPOT, [])),
            12: fnv1a32(self.masked_idx.get(SITE_CIRRUS, [])),
            13: fnv1a32(self.naive_idx.get(SITE_CIRRUS, [])),
            14: sum(1 for v in glyph if v),
            17: fnv1a32(self.page("adapted")),
            18: fnv1a32(self.page("adaptor")),
            19: fnv1a32(glyph),
        }
        if extra:
            f.update(extra)
        out = []
        for k in sorted(f):
            out += [k, f[k] & 0xFFFFFFFF]
        return out

    # -- how many sea texels actually left n_globes_map ---------------------

    def overrun_census(self):
        gsize = self.lay.by_name["n_globes_map"].size
        out = pad = 0
        for i in range(32000):
            u = (i * 517) & 0xFFFF
            v = (i * 1031) & 0xFFFF
            t = self.texel_addr(u, v)
            if t >= gsize:
                out += 1
                if t < gsize + PAD:
                    pad += 1
        return out, pad


# ------------------------------------------------------------------------ main


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dump", metavar="PATH", help="write FBDUMP kind 5 LAYOUT")
    ap.add_argument("--dump-zones", metavar="PATH", help="write FBDUMP kind 9 ZONES")
    ap.add_argument("--zones", action="store_true", help="print the 22-zone table")
    ap.add_argument("--break", dest="brk", action="append", default=[], choices=sorted(BREAKS),
                    help="deliberately sabotage the layout; assertions must then fail")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    lay = Layout(args.brk)
    ok, msg = lay.check()

    if not args.quiet:
        print("fb_layout.py -- layout derived from NOCTIS-D.H + NOCTIS.CPP farmalloc order")
        if args.brk:
            for b in args.brk:
                print("  SABOTAGE %-14s %s" % (b, BREAKS[b]))
        print()
        print("farmalloc sequence as parsed from NOCTIS.CPP:")
        for i, (n, s, e) in enumerate(lay.alloc):
            print("  %d  %-14s %6d   farmalloc(%s)" % (i, n, s, e))
        print("  8  %-14s %6d   0x%08X literal far pointer, NOCTIS-0.CPP:53"
              % ("adaptor", lay.defines["sc_bytes"], lay.adaptor_fp))
        print()
        print(lay.table())
        print()
        print("QUADWORDS declared %d, steady %d (derived from `QUADWORDS -= 1440`)"
              % (lay.qw_declared, lay.qw_steady))
        a8 = lay.alias8()
        print("alias 8   es:[0x%04X] -> NW %d = adapted[%d] = row %d col %d"
              % (a8["segoff"], a8["nw"], a8["index"], a8["row"], a8["col"]))
        print()
        if args.zones:
            print(lay.zone_table())
            print()
        print("assertions:")
        print("\n".join(msg))
        print()
        print("RESULT: %s   (%d checks, %d failed)"
              % ("PASS" if ok else "FAIL", len(msg), sum(1 for m in msg if m.startswith("  FAIL"))))

    if args.dump:
        fbdump_write(args.dump, KIND_LAYOUT, layout_payload(lay), tag=TAG["layout"])
        if not args.quiet:
            print("wrote %s (%d units)" % (args.dump, len(layout_payload(lay))))
    if args.dump_zones:
        fbdump_write(args.dump_zones, KIND_ZONES, zones_payload(lay), tag=TAG["zones"])
        if not args.quiet:
            print("wrote %s (%d units)" % (args.dump_zones, len(zones_payload(lay))))

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
