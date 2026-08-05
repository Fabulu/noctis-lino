#!/usr/bin/env python3
"""fb_layout.py -- Wave 5, implementer 2.

Derives the Noctis workspace layout INDEPENDENTLY, by parsing the 1996 sources:

  * region SIZES come from `#define *_bytes` in NOCTIS-D.H
  * region ORDER comes from the actual farmalloc() call sequence in NOCTIS.CPP
  * `adaptor` is not farmalloc'd; it is the literal far pointer 0xA0000000
    (NOCTIS-0.CPP:53) and is appended last, at a full segment + 4.

Nothing here reads LINOBUF.md, work/fb*.txt, or fb_ref.c.  The constants in
LINOBUF.md 2.3 are a PREDICTION that this script either reproduces or refutes.

It then asserts the structural properties the buffer model depends on, and can
emit an FBDUMP v1 kind-5 LAYOUT record for unit-for-unit comparison against the
lino and C sides.

  python fb_layout.py                 # derive, assert, print the table
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
SUPPORTS = os.path.join(DATA, "SUPPORTS.NCT")

# The one design constant that is ours, not the original's: a stand-in for
# Borland's far-heap block header.  16 units.  LINOBUF 2.3.
PAD = 16
# A second pad below the first region, so digit_at's txtr[-6..-1] underflow has
# somewhere to land when txtr is based at the very first buffer.
LOWPAD = 16

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


# ------------------------------------------------------------------- the layout


class Region(object):
    __slots__ = ("rid", "name", "base", "size", "padbase", "note")

    def __init__(self, rid, name, base, size, padbase, note):
        self.rid = rid
        self.name = name
        self.base = base
        self.size = size
        self.padbase = padbase
        self.note = note

    @property
    def end(self):
        return self.base + self.size


class Layout(object):
    def __init__(self, breaks=()):
        self.breaks = set(breaks)
        self.defines = parse_defines(read_text(D_H))
        self.alloc = parse_farmalloc_order(read_text(MAIN_CPP), self.defines)
        self.adaptor_fp = parse_adaptor(read_text(ZERO_CPP))

        pad = 0 if "NOPAD" in self.breaks else PAD
        lowpad = 0 if "NOPAD" in self.breaks else LOWPAD

        seq = list(self.alloc)
        if "ORDER" in self.breaks:
            # declaration order in NOCTIS-D.H, which is NOT farmalloc order
            decl = [
                "n_offsets_map",
                "n_globes_map",
                "s_background",
                "p_background",
                "p_surfacemap",
                "objectschart",
                "adapted",
                "pvfile",
            ]
            seq.sort(key=lambda t: decl.index(t[0]))
        if "SWAPSEA" in self.breaks:
            i = [t[0] for t in seq].index("n_globes_map")
            seq[i], seq[i + 1] = seq[i + 1], seq[i]

        # adaptor: no farmalloc, appended last, full segment + 4 like adapted.
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
            self.regions.append(Region(rid, name, cur, size, padbase, expr))
            cur += size
        self.toppad = cur
        self.top = cur + pad
        self.pad = pad
        self.lowpad = lowpad

        self.by_name = {r.name: r for r in self.regions}

    # -- derived constants other modules want -------------------------------

    def base(self, name):
        return self.by_name[name].base

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

        # L4 -- digit_at writes txtr[-6..-1] with txtr == p_surfacemap
        req(self.base("p_surfacemap") - 6 >= 0, "L4 p_surfacemap-6 >= 0 (digit_at underflow lands in NW)")
        req(
            self.base("p_surfacemap") - 6 >= self.by_name["p_background"].end,
            "L4 p_surfacemap-6 is dead pad, not live p_background",
        )

        # L5 -- class-A wrap containment: pages are a full segment
        for nm in ("adapted", "adaptor"):
            req(self.by_name[nm].size >= 65536, "L5 %s >= 65536 (16-bit DI wrap contained)" % nm)
        req(self.by_name["p_background"].size >= 65536, "L5 p_background >= 65536")

        # L6 -- the class-C neighbour relations of LINOBUF 2.4, each derived
        # here from the farmalloc order rather than assumed
        nb = {r.name: (self.regions[i + 1].name if i + 1 < len(self.regions) else None)
              for i, r in enumerate(self.regions)}
        req(nb["n_globes_map"] == "s_background", "L6 sea texture overrun -> s_background")
        req(nb["s_background"] == "p_background", "L6 globe tapestry +718 / ssmooth +39 -> p_background")
        req(nb["p_surfacemap"] == "objectschart", "L6 hpoint +201 / cockpit texture -> objectschart")

        # L7 -- objectschart is big enough that cirrus' (py+px)>>1 wrap
        # (0..32767) stays inside it
        req(self.by_name["objectschart"].size > 32768, "L7 objectschart > 32768 (cirrus bx wrap contained)")

        # L8 -- the heap total the original allocated
        heap = sum(r.size for r in self.regions if r.name != "adaptor")
        req(heap == 336480, "L8 farmalloc heap total == 336480 bytes (got %d)" % heap)

        return ok, msg

    # -- output -------------------------------------------------------------

    def table(self):
        w = []
        w.append("region          rid    base      size    ends at   pad base")
        w.append("-" * 62)
        for r in self.regions:
            w.append("%-14s %3d %7d %9d %9d %10d" % (r.name, r.rid, r.base, r.size, r.end, r.padbase))
        w.append("-" * 62)
        w.append("%-14s     %7s %9s %9d" % ("NW top", "", "", self.top))
        w.append("PAD=%d LOWPAD=%d  bytes=%d" % (self.pad, self.lowpad, self.top * 4))
        return "\n".join(w)


# ------------------------------------------------------------------ FBDUMP v1

FBD_MAGIC = 0x46424431
KIND_INDEXPAGE = 1
KIND_PALETTE6 = 2
KIND_LUT = 3
KIND_TICKLOG = 4
KIND_LAYOUT = 5
KIND_CANARY = 6

KIND_NAME = {
    1: "INDEXPAGE",
    2: "PALETTE6",
    3: "LUT",
    4: "TICKLOG",
    5: "LAYOUT",
    6: "CANARY",
}


def fbdump_write(path, kind, payload, width=0, height=0, cpms=0, ticks=0):
    hdr = [FBD_MAGIC, 1, kind, width, height, len(payload), cpms, ticks] + [0] * 8
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
    if hdr[1] != 1:
        raise ValueError("%s: unsupported version %d" % (path, hdr[1]))
    count = hdr[5]
    body = raw[64:]
    if len(body) < count * 4:
        raise ValueError("%s: truncated, want %d units have %d" % (path, count, len(body) // 4))
    payload = list(struct.unpack("<%dI" % count, body[: count * 4]))
    return {
        "kind": hdr[2],
        "width": hdr[3],
        "height": hdr[4],
        "count": count,
        "cpms": hdr[6],
        "ticks": hdr[7],
        "payload": payload,
        "path": path,
    }


def layout_payload(lay):
    """kind 5: 4 units per region -- base, size, pad base, region id."""
    out = []
    for r in lay.regions:
        out += [r.base, r.size, r.padbase, r.rid]
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
# ops, the 16-bit texel address, digit_at's underflow, and the class-C read
# overrun that farmalloc order is supposed to make faithful.

PP32 = [1 << m for m in range(32)]


class Workspace(object):
    """One Noctis byte per 32-bit unit.  A byte offset IS a unit offset."""

    def __init__(self, lay=None, breaks=()):
        self.lay = lay or Layout()
        self.breaks = set(breaks)
        self.nw = [0] * self.lay.top
        self.QUADWORDS = 16000
        self.digimap2 = load_digimap2(self.lay.defines)
        self.lcg = 0

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

    # -- the page scenario, matching fb_ref.c's scenario_page ---------------

    def scenario_page(self):
        L = self.lay
        adapted, adaptor = L.base("adapted"), L.base("adaptor")
        globes, sbg = L.base("n_globes_map"), L.base("s_background")

        self.QUADWORDS = 16000
        self.pclear(adaptor, 0)
        # NOCTIS.CPP:2206 steady state, 14560 dwords = 58240 bytes = 182 rows.
        # Non-zero pattern so the extent of the clear is observable at all.
        self.QUADWORDS = 16000 - 1440
        self.pclear(adapted, 7)

        self.srand(1996)
        for i in range(32768):
            self.put(globes + i, self.rand() & 63)
        for i in range(4096):
            self.put(sbg + i, 128 + (self.rand() & 63))

        # sea texture: V driven past row 127 so texels 32768..65535 read PAST
        # n_globes_map.  Under farmalloc order that lands on s_background.
        for i in range(32000):
            u = (i * 517) & 0xFFFF
            v = (i * 1031) & 0xFFFF
            self.put(adapted + i, self.get(globes + self.texel_addr(u, v)))

        self.digit_at('A', 64 + 40, 1)
        src = L.base("p_surfacemap") - 5
        for i in range(9216):
            self.put(adapted + 32000 + i, self.get(src + i))

        if "TINTA64000" in self.breaks:
            self.put(adapted + 64000, 0x37)
            self.put(adapted + 64001, 0x5B)
        else:
            self.put(adapted + 63996, 0x37)
            self.put(adapted + 63997, 0x5B)

        self.areaclear(adaptor, 2, 191, 316, 7, 64 + 63)

        self.QUADWORDS = 16000
        self.pcopy(adaptor, adapted)

    def page(self, name):
        b = self.lay.base(name)
        return [self.get(b + i) for i in range(64000)]

    # -- how many sea texels actually left n_globes_map ---------------------

    def overrun_census(self):
        """How many sea texels leave n_globes_map, and how many land in the
        16-unit PAD rather than on the neighbouring buffer.

        The pad count matters: LINOBUF 2.4 records "no read-overrun in recon
        A's audit is proven to sample the pad" and treats the pad as the one
        knowing divergence from DOS.  The 16-bit texel address reaches it
        easily -- texels 32768..32783 are exactly the pad -- so the pad is
        reachable in principle, and its contents are observable.  That is why
        a grading run must use the release (zero) pad state and not the
        poisoned debug one.
        """
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
        print("assertions:")
        print("\n".join(msg))
        print()
        print("RESULT: %s   (%d checks, %d failed)"
              % ("PASS" if ok else "FAIL", len(msg), sum(1 for m in msg if m.startswith("  FAIL"))))

    if args.dump:
        fbdump_write(args.dump, KIND_LAYOUT, layout_payload(lay))
        if not args.quiet:
            print("wrote %s (%d units)" % (args.dump, len(layout_payload(lay))))

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
