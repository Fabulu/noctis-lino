#!/usr/bin/env python3
"""fb_pal.py -- Wave 5-corrective, implementer 2.  Independent Python palette
reference.

Written from NOCTIS-0.CPP:166-241 (range8088, tavola_colori), :1151-1200
(shade) and :6418-6420 (snapshot's DAC scaling).  It does not read fb_ref.c
and it does not read work/fb*.txt.

Model
-----
pal6     the master palette, Noctis's `tmppal`, 768 entries of 0..63
curpal6  what has actually been "uploaded" to the DAC.  tavola_colori's
         asm tail always starts the upload at colour 0 and runs to
         (first+n)*3, so an update to a high band refreshes every band
         below it and leaves everything above it STALE.
srfpal6  `surface_palette` (NOCTIS-0.CPP:57).  shade()'s destination at 14 of
         its 21 call sites.
retpal6  `return_palette` (NOCTIS-0.CPP:58).
pal      the 256-entry 00RRGGBB LUT, rebuilt from curpal6.

THREE CORRECTIONS THIS FILE MAKES TO THE WAVE 5 VERSION
-------------------------------------------------------
1. tavola_colori's filter is MODULAR UNSIGNED, not unbounded floor division.
   `unsigned temp` is 16 bits under Borland; `temp *= filtro` with a SIGNED
   CHAR filter converts the filter to unsigned and multiplies mod 65536; the
   `/= 63` that follows is an UNSIGNED divide.  The previous version used
   Python's unbounded ints and floor division and merely RAISED for |f| > 127,
   so it never ran a negative filter at all.  Measured divergence:
   8064 of 16384 (v, f) pairs over v in 0..63, f in -128..-1.
2. `shade` takes a DESTINATION BUFFER.  The original's signature is
   `shade(unsigned char far *palette_buffer, ...)` and 14 of its 21 call sites
   pass `surface_palette`, not `tmppal`.  A palette library that cannot
   express two thirds of the game's shade calls is not a palette library.
3. The scenario is the pinned LINOBUF 6.1 "surface", implemented from the
   normative text, not from fb_ref.c.

  python fb_pal.py                    # self-test + proofs + the 1996 fit
  python fb_pal.py --scenario surface --dump-pal6 p.bin --dump-lut l.bin
  python fb_pal.py --break ROUNDSHADE  # sabotage; the checks must then fail
  python fb_pal.py --separation        # which step separates which sabotage
"""

import argparse
import os
import re
import struct
import sys

from fb_layout import (NIVPLUS, read_text, fbdump_write, fnv1a32,
                       KIND_PALETTE6, KIND_LUT, TAG)

BREAKS = {
    "SHIFTOR": "LUT built with (v<<2)|(v>>4) instead of v*4  [LINOBUF sabotage 1]",
    "UPLOADFIRST": "tavola_colori uploads [first,first+n) instead of [0,first+n)  [sabotage 2]",
    "ROUNDSHADE": "shade() rounds to nearest instead of truncating  [sabotage 3]",
    "DIV64": "tavola_colori's filter divides by 64 instead of 63",
    "NOCLAMP": "tavola_colori's filter drops the >63 clamp",
    # NOT offered as a sabotage, and this is a finding rather than an omission:
    # shade()'s "inverted" clamp (`if (v > 0) 63 else 0`) is PROVABLY
    # EQUIVALENT to a plain clamp.  The else-branch is only reached when v is
    # outside [0,64), so v is either < 0 (both give 0) or >= 64 (both give 63).
    "NOSELF": "tavola_colori's self-copy case copies from a stale buffer instead of filtering in place  [trap 1]",
    # -- wave 5-corrective additions --------------------------------------
    "PYFILT": "restore the unbounded floor-division filter this file used to "
              "carry -- wrong for every negative filtro  [BREAK_PYFILT]",
    "IGNOREDST": "shade() ignores its destination buffer and always writes "
                 "tmppal  [SH-IGNOREDST]",
    "SELFSOURCE": "the fade re-reads tmppal instead of surface_palette, so "
                  "successive fades COMPOUND  [SH-COMPOUND]",
}

SELF = "SELF"  # sentinel: source aliases tmppal at 3*first (NOCTIS.CPP:3777)

PAL6, SRFPAL6, RETPAL6 = "pal6", "srfpal6", "retpal6"


# ------------------------------------------------------------ range8088


def range8088_generated():
    """The 64-step grey ramp: entry i is (i, i, i)."""
    return [v for i in range(64) for v in (i, i, i)]


def range8088_parsed():
    """The same table, lifted out of the NOCTIS-0.CPP literal, so the
    generated form above is checked rather than trusted."""
    text = read_text(os.path.join(NIVPLUS, "NOCTIS-0.CPP"))
    m = re.search(r"range8088\s*\[\s*64\s*\*\s*3\s*\]\s*=\s*\{(.*?)\}", text, re.S)
    if not m:
        raise SystemExit("range8088 literal not found in NOCTIS-0.CPP")
    return [int(v) for v in re.findall(r"-?\d+", m.group(1))]


def count_shade_sites():
    """How many `shade(...)` call sites there are and what each passes as its
    destination.  Measured, because LINOBUF 5.3's "17 of 24" is stale."""
    dst = {}
    total = 0
    for f in ("NOCTIS.CPP", "NOCTIS-0.CPP", "NOCTIS-1.CPP"):
        text = read_text(os.path.join(NIVPLUS, f))
        for m in re.finditer(r"\bshade\s*\(\s*([A-Za-z_][A-Za-z_0-9]*)", text):
            name = m.group(1)
            if name == "unsigned":          # the definition itself
                continue
            total += 1
            dst[name] = dst.get(name, 0) + 1
    return total, dst


# ------------------------------------------------------------ float helpers


def f32(x):
    """Round a Python float to IEEE-754 binary32, as storing to a C `float`
    local does.  shade()'s start_*/delta_*/k are all `float`, so every step of
    the accumulation is rounded to single precision."""
    return struct.unpack("<f", struct.pack("<f", x))[0]


def chop_to_uchar(v):
    """C's float -> unsigned char conversion: truncate toward zero.
    lino's `=,` rounds to nearest, which is why LINOBUF makes this a
    named trap and a sabotage."""
    return int(v) if v >= 0 else -int(-v)


def schar(f):
    """`char filtro_rosso` is SIGNED under Borland's default.  A caller that
    passes 200 does not get 200; it gets -56.  The previous version raised
    here, which is why the pinned scenario never exercised a negative filter
    and the trap it documents went untested."""
    return ((int(f) + 128) & 0xFF) - 128


# ------------------------------------------------------------ the palette


class Palette(object):
    def __init__(self, breaks=()):
        self.breaks = set(breaks)
        self.pal6 = [0] * 768        # tmppal        (unsigned char)
        self.curpal6 = [0] * 768     # what the DAC actually holds
        self.srfpal6 = [0] * 768     # surface_palette   (char, but see below)
        self.retpal6 = [0] * 768     # return_palette    (char)
        self.uploads = []            # (start, end) of every upload
        self.trace = []              # (step label, pal6 fnv, curpal6 fnv)

    def buf(self, name):
        return getattr(self, name)

    # -- NOCTIS-0.CPP:179-241 -------------------------------------------

    def filter_one(self, v, f):
        """The DOS-16 filter, exactly.

            unsigned temp;            <- 16 bits under Borland
            temp = tmppal[c];         <- 0..255
            temp *= filtro_rosso;     <- signed char -> int -> unsigned, mod 65536
            temp /= 63;               <- UNSIGNED divide
            if (temp > 63) temp = 63;

        Both operands of the multiply are converted to `unsigned int`, so a
        negative filter becomes 65536-|f| and the product wraps.  Since
        |v*f| <= 255*128 = 32640 < 65536, every negative product lands in
        [32896, 65535], divides to at least 522, and CLAMPS to 63.  That is
        why a 32-bit C `unsigned` gives the same answer as the 16-bit one --
        proved exhaustively in `proof_dos16_vs_c32()`.
        """
        div = 64 if "DIV64" in self.breaks else 63
        if "PYFILT" in self.breaks:
            temp = (v * f) // div            # the defect: unbounded, floored
        else:
            temp = ((v * f) & 0xFFFF) // div  # modular unsigned, as DOS
        if "NOCLAMP" not in self.breaks:
            if temp > 63:
                temp = 63
        return temp & 0xFF

    def tavola_colori(self, src, first, n, fr, fg, fb):
        """src is either a 3*n list, or SELF meaning `tmppal + 3*first`.

        Three steps:
          1. copy n*3 bytes from src into pal6[first*3 ...]
          2. filter that same window in place, v = v*f/63 clamped to 63
          3. upload from colour ZERO up to (first+n)*3
        Step 3 is the asm tail: `mov cx, colore_di_partenza; add cx, nr_colori`
        with both already multiplied by 3, `mov al,0; out 0x3c8,al`.

        The DESTINATION is always tmppal, whatever the first argument says --
        that argument is the SOURCE (NOCTIS-0.CPP:186, `tmppal[c] = ...`).
        Do not "fix" this symmetrically with shade's destination parameter.
        """
        fr, fg, fb = schar(fr), schar(fg), schar(fb)
        n3 = n * 3
        c0 = first * 3

        # step 1 -- copy
        if src is SELF or src == SELF:
            if "NOSELF" in self.breaks:
                for i in range(n3):
                    self.pal6[c0 + i] = 0
            # otherwise: source aliases destination, the copy is a no-op and
            # step 2 filters in place
        else:
            if isinstance(src, str):
                src = self.buf(src)[c0:c0 + n3] if len(self.buf(src)) == 768 else src
            if len(src) < n3:
                raise ValueError("source table has %d entries, need %d" % (len(src), n3))
            for i in range(n3):
                self.pal6[c0 + i] = src[i] & 0xFF

        # step 2 -- filter in place
        c = c0
        while c < c0 + n3:
            for f in (fr, fg, fb):
                self.pal6[c] = self.filter_one(self.pal6[c], f)
                c += 1

        # step 3 -- upload
        end = c0 + n3
        start = c0 if "UPLOADFIRST" in self.breaks else 0
        for i in range(start, end):
            self.curpal6[i] = self.pal6[i]
        self.uploads.append((start, end))

    def fade_from(self, srcname, first, n, fr, fg, fb):
        """`tavola_colori(surface_palette, first, n, w, w, w)` -- the shape 14
        of shade's callers set up.  The whole point of surface_palette is that
        the SOURCE is the unfiltered original, so two successive fades do not
        compound.  SELFSOURCE reproduces the compounding."""
        if "SELFSOURCE" in self.breaks:
            return self.tavola_colori(SELF, first, n, fr, fg, fb)
        src = self.buf(srcname)[3 * first: 3 * (first + n)]
        return self.tavola_colori(src, first, n, fr, fg, fb)

    # -- NOCTIS-0.CPP:1151-1200 -----------------------------------------

    def shade(self, dst, first_color, number_of_colors, sr, sg, sb, fr, fg, fb):
        """`void shade (unsigned char far *palette_buffer, ...)`.

        `dst` is the buffer NAME.  In the game it is `tmppal` at 7 call sites
        and `surface_palette` at 14.  IGNOREDST is the Wave 5 defect: the
        destination hard-coded to tmppal.

        Note detail (2) of the plan: surface_palette and return_palette are
        declared `char` (signed) but shade takes `unsigned char far *`, so the
        STORES are unsigned, and every read is through tavola_colori's
        `unsigned char *` parameter.  No sign extension ever occurs, and
        applying an 8->32 sign extension on loads from srfpal6 would be a bug.
        """
        if "IGNOREDST" in self.breaks:
            dst = PAL6
        buf = self.buf(dst)
        count = number_of_colors
        k = f32(1.00 / float(number_of_colors))
        dr = f32(f32(fr - sr) * k)
        dg = f32(f32(fg - sg) * k)
        db = f32(f32(fb - sb) * k)
        cr, cg, cb = f32(sr), f32(sg), f32(sb)
        i = first_color * 3

        def place(v):
            if 0 <= v < 64:
                if "ROUNDSHADE" in self.breaks:
                    return int(v + 0.5)
                return chop_to_uchar(v)
            # the original's inverted clamp, NOCTIS-0.CPP:1166-1189.
            return 63 if v > 0 else 0

        while count:
            buf[i + 0] = place(cr)
            buf[i + 1] = place(cg)
            buf[i + 2] = place(cb)
            cr = f32(cr + dr)
            cg = f32(cg + dg)
            cb = f32(cb + db)
            i += 3
            count -= 1

    # -- the LUT ---------------------------------------------------------

    def lut(self):
        """256 units of 00RRGGBB, rebuilt from the UPLOADED palette."""
        out = []
        for i in range(256):
            r, g, b = self.curpal6[3 * i: 3 * i + 3]
            if "SHIFTOR" in self.breaks:
                r = (r << 2) | (r >> 4)
                g = (g << 2) | (g >> 4)
                b = (b << 2) | (b >> 4)
            else:
                r, g, b = r * 4, g * 4, b * 4
            out.append((r << 16) | (g << 8) | b)
        return out

    def mark(self, label):
        self.trace.append((label, fnv1a32(self.pal6), fnv1a32(self.curpal6),
                           fnv1a32(self.srfpal6)))

    # -- trace digests -----------------------------------------------------
    #
    # The pinned scenario's FINAL state does not separate every choice, and
    # that is a measured fact rather than a worry: BREAK_UPLOADFIRST changes
    # the upload spans of steps 4 and 5 but step 7 uploads [0,768) either way,
    # so the final pal6, curpal6 and LUT are bit-identical.  A grader that
    # only compares the final records CANNOT catch it.  These three digests
    # are the fix: each is a pure function of state the scenario passes
    # through, computable independently by any implementation of LINOBUF 6.1,
    # and each is dumped as a KSELF field.

    def pal6_trace_fnv(self):
        return fnv1a32([t[1] for t in self.trace])

    def curpal6_trace_fnv(self):
        return fnv1a32([t[2] for t in self.trace])

    def upload_spans_fnv(self):
        out = []
        for a, b in self.uploads:
            out += [a, b]
        return fnv1a32(out)


# ------------------------------------------------------------- proofs
#
# "Prove it, do not assert it" applies to the negative verdicts too.


def proof_trap2_unreachable():
    """LINOBUF 5.3 trap 2 asserts a 16-bit wrap in `temp *= filtro`.  For every
    LEGAL filter it is unreachable: max product 63*127 = 8001 < 65536, zero
    wraps over all 64*128 = 8192 (v, f) pairs with f in 0..127.  The trap only
    exists for filters already outside the callers' range -- which is exactly
    what pinned scenario step 7 constructs."""
    wraps = sum(1 for v in range(64) for f in range(128) if v * f >= 65536)
    return {"pairs": 64 * 128, "wraps": wraps,
            "max_product": max(v * f for v in range(64) for f in range(128))}


def proof_dos16_vs_c32():
    """A 16-bit `unsigned temp` (Borland) and a 32-bit `unsigned` (gcc) must
    give the same answer for every reachable input, or fb_ref.c and this file
    are not comparable.  Exhaustive over v in 0..255, f in -128..127."""
    bad = []
    for v in range(256):
        for f in range(-128, 128):
            a = min(((v * f) & 0xFFFF) // 63, 63)
            b = min(((v * f) & 0xFFFFFFFF) // 63, 63)
            if a != b:
                bad.append((v, f, a, b))
    return {"pairs": 256 * 256, "disagreements": len(bad), "first": bad[:3]}


def proof_pyfilt_divergence():
    """How wrong the unbounded floor-division filter was.  Exhaustive over
    v in 0..63 (a legal 6-bit component), f in -128..127."""
    bad = []
    for v in range(64):
        for f in range(-128, 128):
            dos = min(((v * f) & 0xFFFF) // 63, 63) & 0xFF
            py = min((v * f) // 63, 63) & 0xFF
            if dos != py:
                bad.append((v, f, dos, py))
    negs = [b for b in bad if b[1] < 0]
    return {"pairs": 64 * 256, "disagreements": len(bad),
            "all_negative_filters": len(bad) == len(negs),
            "example": next((b for b in bad if b[0] == 1 and b[1] == -128), None)}


# ------------------------------------------------------------- scenarios
#
# LINOBUF 6.1 -- THE PINNED SCENARIO.  NORMATIVE, architect-authored.
# *** This is a test fixture, not a claim about the game. ***
#
# Both implementers implement it from the text; neither reads the other.  The
# text is reproduced in fb_compare.py --scenario-spec, which reads LINOBUF 6.1
# off disk when the architect has landed it and says so when it has not.

SURFACE_STEPS = [
    # (label, what it separates)
    ("1 zero pal6/curpal6/srfpal6, build range8088", "--"),
    ("2 tavola(range8088, first=0,   n=64,  16,32,63)", "filter arithmetic"),
    ("3 shade(pal6, 0, 64, 0,0,0, 63,63,63)  [no upload]", "chop vs round, at the FIRST entry"),
    ("4 tavola(SELF, first=192, n=64, 50,50,50)", "the self-copy"),
    ("5 tavola(range8088, first=64, n=64, 60,55,50)", "upload-from-zero"),
    ("6 shade(pal6, 160, 16, 19.5,24.75,33, 66.25,-2.5,48.125)", "the clamp's saturation value"),
    ("7 tavola(SELF, first=0, n=256, 200,64,64)", "trap 2: filter 200 = signed char -56"),
    ("8 rebuild the LUT from curpal6", "v*4"),
]


def scenario_surface(breaks=()):
    """LINOBUF 6.1 SCENARIO "surface", implemented from the normative text."""
    p = Palette(breaks)
    r8 = range8088_generated()
    p.mark("1")
    p.tavola_colori(r8, 0, 64, 16, 32, 63)
    p.mark("2")
    p.shade(PAL6, 0, 64, 0.0, 0.0, 0.0, 63.0, 63.0, 63.0)
    p.mark("3")
    p.tavola_colori(SELF, 192, 64, 50, 50, 50)
    p.mark("4")
    p.tavola_colori(r8, 64, 64, 60, 55, 50)
    p.mark("5")
    p.shade(PAL6, 160, 16, 19.50, 24.75, 33.00, 66.25, -2.50, 48.125)
    p.mark("6")
    p.tavola_colori(SELF, 0, 256, 200, 64, 64)
    p.mark("7")
    p.lut()
    p.mark("8")
    return p


def scenario_boot(breaks=()):
    """NOCTIS.CPP:2218-2219, the two calls main() makes before the game loop.
    Kept because the boot state is what the 1996 captures were taken in."""
    p = Palette(breaks)
    p.tavola_colori(range8088_generated(), 0, 64, 16, 32, 63)
    p.tavola_colori(SELF, 0, 256, 64, 64, 64)
    return p


# The NOCTIS-1.CPP:3050-3086 ladder, with its float arguments pinned.  Nine
# rungs, every one of them into `surface_palette`.
LADDER = [
    (64, 64, 0.0, 0.0, 0.0, 60.0, 62.0, 64.0),
    (0, 44, 0.0, 0.0, 0.0, 40.0, 30.0, 20.0),
    (44, 20, 40.0, 30.0, 20.0, 55.0, 48.0, 41.0),
    (128, 10, 0.0, 0.0, 0.0, 40.0, 30.0, 20.0),
    (138, 44, 40.0, 30.0, 20.0, 22.0, 33.0, 44.0),
    (182, 10, 22.0, 33.0, 44.0, 55.0, 48.0, 41.0),
    (192, 10, 0.0, 0.0, 0.0, 40.0, 30.0, 20.0),
    (202, 44, 40.0, 30.0, 20.0, 12.0, 50.0, 18.0),
    (246, 10, 12.0, 50.0, 18.0, 55.0, 48.0, 41.0),
]


def scenario_compound(breaks=()):
    """SH-COMPOUND.  The first probe in this project that touches srfpal6 at
    all, and the one that tests what the buffer is FOR.

    Run the NOCTIS-1.CPP ladder into surface_palette, then two descending
    fades `tavola_colori(surface_palette, 0, 256, w, w, w)`.  With a correct
    destination the second fade filters the ORIGINAL surface palette; with the
    Wave 5 hard-coded destination surface_palette is never written and the
    fades read zeros; with a self-sourced fade they COMPOUND.

    Returns (palette, expected_pal6) where expected_pal6 is filter(ladder, 24)
    computed directly -- so the check is an equality against a value derived
    from the ladder, not a "> 0".
    """
    p = Palette(breaks)
    for (first, n, sr, sg, sb, fr, fg, fb) in LADDER:
        p.shade(SRFPAL6, first, n, sr, sg, sb, fr, fg, fb)
    ladder_snapshot = list(p.srfpal6)
    p.fade_from(SRFPAL6, 0, 256, 48, 48, 48)
    p.fade_from(SRFPAL6, 0, 256, 24, 24, 24)
    ref = Palette()          # a clean instance, used only as the arithmetic
    want = [ref.filter_one(v, 24) for v in ladder_snapshot]
    return p, want, ladder_snapshot


SCENARIOS = {"boot": scenario_boot, "surface": scenario_surface}


# ------------------------------------------------ Tier 1: the 1996 artifact


def fit_filter(observed64, src=None):
    """Given 64 observed 6-bit values for one channel of band 0..63, return
    every integer filter f for which  min(v*f//63, 63)  reproduces all 64."""
    if src is None:
        src = [i for i in range(64)]
    return [f for f in range(0, 256)
            if all(min(src[i] * f // 63, 63) == observed64[i] for i in range(64))]


def tier1_palette_audit(pal6, breaks=()):
    """Run the fit against a captured pal6, and against the two falsifiers."""
    res = {}
    for ch, name in ((0, "R"), (1, "G"), (2, "B")):
        obs = [pal6[3 * i + ch] for i in range(64)]
        res[name] = fit_filter(obs)
        if "DIV64" in breaks:
            res[name] = [f for f in range(256)
                         if all(min(i * f // 64, 63) == obs[i] for i in range(64))]
    obsR = [pal6[3 * i + 0] for i in range(64)]
    res["_round_to_nearest_fits"] = [
        f for f in range(256)
        if all(min((i * f + 31) // 63, 63) == obsR[i] for i in range(64))
    ]
    res["_div64_fits"] = [
        f for f in range(256) if all(min(i * f // 64, 63) == obsR[i] for i in range(64))
    ]
    return res


# -------------------------------------------------------------------- main


def separation_matrix():
    """Which sabotage does each pinned step actually separate?  MEASURED, not
    claimed: run the scenario under every sabotage and report the first step
    whose pal6/curpal6 differs from the clean run.

    This exists because a pinned scenario's own rationale is a claim, and a
    claim about a test fixture is exactly the kind of thing that should be
    checked rather than believed.
    """
    clean = scenario_surface()
    rows = []
    for b in sorted(BREAKS):
        if b in ("IGNOREDST", "SELFSOURCE"):
            continue      # graded by scenario_compound, not by "surface"
        p = scenario_surface([b])
        first = None
        for i in range(len(p.trace)):
            if p.trace[i][1:] != clean.trace[i][1:]:
                first = i + 1          # trace[i] is the state AFTER step i+1
                break
        lutdiff = sum(1 for a, c in zip(p.lut(), clean.lut()) if a != c)
        paldiff = sum(1 for a, c in zip(p.pal6, clean.pal6) if a != c)
        curdiff = sum(1 for a, c in zip(p.curpal6, clean.curpal6) if a != c)
        digests = (p.pal6_trace_fnv() != clean.pal6_trace_fnv()
                   or p.curpal6_trace_fnv() != clean.curpal6_trace_fnv()
                   or p.upload_spans_fnv() != clean.upload_spans_fnv())
        rows.append((b, first, paldiff, curdiff, lutdiff, digests))
    return clean, rows


def selftest(breaks=()):
    ok = True
    out = []

    def req(cond, text):
        nonlocal ok
        if not cond:
            ok = False
        out.append(("  PASS  " if cond else "  FAIL  ") + text)

    # P1 -- the generated ramp equals the literal in the 1996 source
    req(range8088_generated() == range8088_parsed(),
        "P1 range8088 generated == NOCTIS-0.CPP literal")

    # P2 -- upload always starts at colour 0
    p = Palette(breaks)
    p.tavola_colori([63] * 192, 64, 64, 63, 63, 63)
    req(p.uploads[-1] == (0, 384), "P2 upload span is [0,384) not [192,384)  (got %s)" % (p.uploads[-1],))
    req(all(v == 0 for v in p.curpal6[384:]), "P2 colours 128..255 left stale by the upload")

    # P3 -- the self-copy is a no-op, so a second identical filter compounds
    p = Palette(breaks)
    p.tavola_colori(range8088_generated(), 0, 64, 63, 63, 63)
    before = list(p.pal6[:192])
    p.tavola_colori(SELF, 0, 64, 32, 32, 32)
    req(p.pal6[:192] == [Palette().filter_one(v, 32) for v in before],
        "P3 self-copy filters in place (compounds) rather than reloading a source")

    # P4 -- shade's inverted clamp and truncation
    p = Palette(breaks)
    p.shade(PAL6, 0, 4, 62.75, -1.0, 64.0, 66.75, -1.0, 64.0)
    req(p.pal6[0] == 62, "P4 shade truncates 62.75 -> 62  (got %d)" % p.pal6[0])
    req(p.pal6[1] == 0, "P4 shade sends -1.0 -> 0  (got %d)" % p.pal6[1])
    req(p.pal6[2] == 63, "P4 shade sends 64.0 -> 63  (got %d)" % p.pal6[2])

    # P5 -- the LUT scaling is x4
    p = Palette(breaks)
    p.curpal6 = [63, 32, 0] + [0] * 765
    req(p.lut()[0] == 0xFC8000, "P5 LUT (63,32,0) -> 0x00FC8000  (got 0x%08X)" % p.lut()[0])

    # P6 -- the filter is MODULAR UNSIGNED.  This replaces the old P6, which
    # asserted that a filter of 200 raises.  It does not raise in C; it is a
    # signed char, and it is -56.
    req(schar(200) == -56, "P6 filtro 200 is a signed char: -56  (got %d)" % schar(200))
    p = Palette(breaks)
    p.tavola_colori([1, 1, 1], 0, 1, 200, 200, 200)
    req(p.pal6[0] == 63,
        "P6 v=1 f=200(-56): (1*-56) mod 65536 = 65480, /63 = 1039, clamp -> 63  (got %d)"
        % p.pal6[0])
    p = Palette(breaks)
    p.tavola_colori([0, 0, 0], 0, 1, 200, 200, 200)
    req(p.pal6[0] == 0, "P6 v=0 with a negative filter stays 0  (got %d)" % p.pal6[0])

    # P7 -- the filter arithmetic: truncating /63 and the >63 clamp
    p = Palette(breaks)
    p.tavola_colori([63, 63, 63, 32, 32, 32], 0, 2, 63, 63, 63)
    req(p.pal6[0] == 63 and p.pal6[3] == 32,
        "P7 filter v*63/63 is identity  (got %d, %d)" % (p.pal6[0], p.pal6[3]))
    p = Palette(breaks)
    p.tavola_colori([63, 63, 63, 62, 62, 62], 0, 2, 127, 127, 127)
    req(p.pal6[0] == 63 and p.pal6[3] == 63, "P7 filter clamps 127-scaled values to 63")
    p = Palette(breaks)
    p.tavola_colori([1, 1, 1], 0, 1, 62, 62, 62)
    req(p.pal6[0] == 0, "P7 filter truncates 1*62/63 = 0 (not 1)  (got %d)" % p.pal6[0])
    p = Palette(breaks)
    p.tavola_colori([32, 32, 32], 0, 1, 63, 63, 63)
    req(p.pal6[0] == 32, "P7 filter /63 not /64: 32*63/63 = 32  (got %d)" % p.pal6[0])

    # P8 -- shade's DESTINATION.  The whole of MAJOR 6.
    n, dst = count_shade_sites()
    req(n == 21 and dst.get("surface_palette") == 14 and dst.get("tmppal") == 7,
        "P8 shade has %d call sites: %s.  (LINOBUF 5.3's '17 of 24' is stale; two "
        "thirds unexpressible stands, the numerator and denominator do not.)" % (n, dst))
    p = Palette(breaks)
    p.shade(SRFPAL6, 0, 4, 10.0, 20.0, 30.0, 10.0, 20.0, 30.0)
    req(p.srfpal6[:3] == [10, 20, 30] and p.pal6[:3] == [0, 0, 0],
        "P8 shade(surface_palette, ...) writes srfpal6 and leaves tmppal alone "
        "(srfpal6 %s, pal6 %s)" % (p.srfpal6[:3], p.pal6[:3]))
    p = Palette(breaks)
    p.shade(RETPAL6, 0, 2, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0)
    req(p.retpal6[:3] == [5, 5, 5], "P8 the destination parameter is general (retpal6)")

    # P9 -- no sign extension on srfpal6.  It is declared `char`, but shade
    # takes `unsigned char far *` and tavola_colori reads through
    # `unsigned char *`, so a stored 200 reads back as 200, not -56.
    p = Palette(breaks)
    p.srfpal6[0] = 200
    p.fade_from(SRFPAL6, 0, 1, 63, 63, 63)
    req(p.pal6[0] == 63,
        "P9 srfpal6 is read UNSIGNED: 200*63/63 = 200 -> clamp 63, not sign-extended "
        "to -56  (got %d)" % p.pal6[0])

    # P10 -- SH-COMPOUND.  The observable the buffers exist for.
    p, want, ladder = scenario_compound(breaks)
    req(any(v for v in ladder), "P10 the ladder actually wrote surface_palette")
    req(p.pal6 == want,
        "P10 two successive fades do NOT compound: pal6 == filter(ladder, 24) exactly "
        "(%d of 768 components differ)" % sum(1 for a, b in zip(p.pal6, want) if a != b))

    # P11 -- the proofs
    t2 = proof_trap2_unreachable()
    req(t2["wraps"] == 0,
        "P11 trap 2's 16-bit wrap is UNREACHABLE for every legal filter: %d of %d "
        "(v,f) pairs wrap, max product %d < 65536.  Proof, not assertion."
        % (t2["wraps"], t2["pairs"], t2["max_product"]))
    eq = proof_dos16_vs_c32()
    req(eq["disagreements"] == 0,
        "P11 16-bit `unsigned temp` and 32-bit `unsigned` agree on all %d (v,f) pairs, "
        "so fb_pal.py and fb_ref.c are comparable at all" % eq["pairs"])
    dv = proof_pyfilt_divergence()
    req(dv["disagreements"] == 8064 and dv["all_negative_filters"],
        "P11 the OLD unbounded floor-division filter disagreed with DOS on %d of %d "
        "pairs, every one of them a negative filter (v=1 f=-128: DOS %d, old Python %d)"
        % (dv["disagreements"], dv["pairs"],
           dv["example"][2] if dv["example"] else -1,
           dv["example"][3] if dv["example"] else -1))

    return ok, out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", choices=sorted(SCENARIOS), default="surface")
    ap.add_argument("--dump-pal6", metavar="PATH")
    ap.add_argument("--dump-curpal6", metavar="PATH")
    ap.add_argument("--dump-lut", metavar="PATH")
    ap.add_argument("--capture", metavar="PATH", help="a BMP/PNG capture to run the Tier 1 fit against")
    ap.add_argument("--separation", action="store_true",
                    help="measure which pinned step separates which sabotage")
    ap.add_argument("--break", dest="brk", action="append", default=[], choices=sorted(BREAKS))
    args = ap.parse_args(argv)

    print("fb_pal.py -- independent Python palette reference")
    if args.brk:
        for b in args.brk:
            print("  SABOTAGE %-12s %s" % (b, BREAKS[b]))
    print()

    ok, out = selftest(args.brk)
    print("self-test:")
    print("\n".join(out))
    print()

    if args.separation:
        clean, rows = separation_matrix()
        print("pinned scenario 'surface' -- what each step is FOR, and what it MEASURABLY separates:")
        for i, (lbl, why) in enumerate(SURFACE_STEPS):
            print("  step %-58s %s" % (lbl, why))
        print()
        print("  sabotage      first differing step   pal6  curpal6   lut   trace digests")
        for b, first, pd, cd, ld, dg in rows:
            step = ("step %d" % first) if first is not None else "none"
            print("  %-12s  %-21s %5d %8d %5d   %s"
                  % (b, step, pd, cd, ld, "DIFFER" if dg else "identical"))
        print()
        print("  Two of the fixture's own claims do NOT hold, measured above:")
        print("    * step 4 does not separate the self-copy.  pal6[576:768] is still zero")
        print("      when step 4 runs, so 'copy from curpal6' and 'no copy' agree there.")
        print("      NOSELF is separated by step 7, whose self band is the whole palette.")
        print("    * BREAK_UPLOADFIRST changes NOTHING in the final pal6, curpal6 or LUT,")
        print("      because step 7 uploads [0,768) under either rule.  It is caught only")
        print("      by the trace digests (KSELF 15/22/23), which is why they exist.")
        print()

    p = SCENARIOS[args.scenario](args.brk)
    print("scenario %r: pal6 nonzero %d, curpal6 nonzero %d, uploads %s"
          % (args.scenario, sum(1 for v in p.pal6 if v),
             sum(1 for v in p.curpal6 if v), p.uploads))
    print("  pal6[0:12]     %s" % p.pal6[:12])
    print("  pal6[189:192]  %s" % p.pal6[189:192])
    print("  pal6[480:492]  %s" % p.pal6[480:492])
    print("  curpal6[0:12]  %s" % p.curpal6[:12])
    print("  lut[0:4]       %s" % ["%08X" % v for v in p.lut()[:4]])
    print("  fnv pal6 %08X curpal6 %08X lut %08X"
          % (fnv1a32(p.pal6), fnv1a32(p.curpal6), fnv1a32(p.lut())))
    print()

    if args.capture:
        import fb_bmp
        idx, pal6, pal8, info = fb_bmp.load_any(args.capture)
        audit = fb_bmp.scale_audit(pal8)
        fit = tier1_palette_audit(pal6, args.brk)
        print("Tier 1 -- %s  (%s)" % (os.path.basename(args.capture), info["route"]))
        print("  DAC scaling consistent with x4=%s  shift-or=%s  distinct=%s"
              % (audit["consistent_with_x4"], audit["consistent_with_shift_or"], audit["distinct"]))
        for ch in "RGB":
            print("  band 0-63 %s: exact v*f/63 filters fitting all 64 samples -> %s" % (ch, fit[ch]))
        print("  falsifier round-to-nearest fits: %s" % fit["_round_to_nearest_fits"])
        print("  falsifier /64 fits:              %s" % fit["_div64_fits"])
        t1 = (len(fit["R"]) >= 1 and len(fit["G"]) >= 1 and len(fit["B"]) >= 1
              and not fit["_round_to_nearest_fits"] and not fit["_div64_fits"])
        print("  TIER1 %s" % ("PASS" if t1 else "FAIL"))
        ok = ok and t1
        print()

    if args.dump_pal6:
        fbdump_write(args.dump_pal6, KIND_PALETTE6, p.pal6, tag=TAG["pal6"])
        print("wrote %s" % args.dump_pal6)
    if args.dump_curpal6:
        fbdump_write(args.dump_curpal6, KIND_PALETTE6, p.curpal6, tag=TAG["curpal6"])
        print("wrote %s" % args.dump_curpal6)
    if args.dump_lut:
        fbdump_write(args.dump_lut, KIND_LUT, p.lut(), tag=TAG["lut"])
        print("wrote %s" % args.dump_lut)

    print("RESULT: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
