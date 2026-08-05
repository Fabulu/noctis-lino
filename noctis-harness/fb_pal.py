#!/usr/bin/env python3
"""fb_pal.py -- Wave 5, implementer 2.  Independent Python palette reference.

Written from NOCTIS-0.CPP:166-241 (range8088, tavola_colori), :1151-1200
(shade) and :6418-6420 (snapshot's DAC scaling).  It does not read fb_ref.c
and it does not read work/fb*.txt.

Python has unbounded integers, so the integer path here is a genuinely
different construction from the C one: nothing can wrap silently, and any
place where the C relies on 16-bit `unsigned temp` would show up as a
disagreement rather than as matching garbage.

Model
-----
pal6     the master palette, Noctis's `tmppal`, 768 entries of 0..63
curpal6  what has actually been "uploaded" to the DAC.  tavola_colori's
         asm tail always starts the upload at colour 0 and runs to
         (first+n)*3, so an update to a high band refreshes every band
         below it and leaves everything above it STALE.  Modelling
         curpal6 separately is what makes that observable.
pal      the 256-entry 00RRGGBB LUT, rebuilt from curpal6.

Six-bit to eight-bit is `v * 4`.  This is not a preference: the game's own
snapshot() writes `tmppal[c]*4` into the BMP palette, and fb_bmp.py's scale
audit measures 768/768 palette bytes ≡ 0 mod 4 with max 252 in the shipped
captures -- consistent with x4 and inconsistent with (v<<2)|(v>>4).

  python fb_pal.py                    # self-test + the 1996-artifact fit
  python fb_pal.py --scenario boot --dump-pal6 p.bin --dump-lut l.bin
  python fb_pal.py --break ROUNDSHADE  # sabotage; the checks must then fail
"""

import argparse
import os
import re
import struct
import sys

from fb_layout import NIVPLUS, read_text, fbdump_write, KIND_PALETTE6, KIND_LUT

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
    # There is no input that separates them.  LINOBUF 5.3 trap 3 is right that
    # the TRUNCATION matters -- see ROUNDSHADE -- but the clamp shape does not.
    "NOSELF": "tavola_colori's self-copy case copies from a stale buffer instead of filtering in place  [trap 1]",
}

SELF = "SELF"  # sentinel: source aliases tmppal at 3*first (NOCTIS.CPP:3777)


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


# ------------------------------------------------------------ the palette


class Palette(object):
    def __init__(self, breaks=()):
        self.breaks = set(breaks)
        self.pal6 = [0] * 768        # tmppal
        self.curpal6 = [0] * 768     # what the DAC actually holds
        self.uploads = []            # (start, end) of every upload, for the audit

    # -- NOCTIS-0.CPP:179-241 -------------------------------------------

    def tavola_colori(self, src, first, n, fr, fg, fb):
        """src is either a 3*n list, or SELF meaning `tmppal + 3*first`.

        Three steps and the third is the trap:
          1. copy n*3 bytes from src into pal6[first*3 ...]
          2. filter that same window in place, v = v*f/63 clamped to 63
          3. upload from colour ZERO up to (first+n)*3
        Step 3 is the asm tail: `mov cx, colore_di_partenza; add cx, nr_colori`
        with both already multiplied by 3, `mov al,0; out 0x3c8,al`.
        """
        # filtro_* is a signed char in the original.  NOCTIS-1.CPP:3934 passes
        # random(64)+64 = 64..127, which fits; above 127 it would go negative
        # and the `> 63` clamp would not catch it.  Assert, do not trust.
        for f in (fr, fg, fb):
            if not (-128 <= f <= 127):
                raise ValueError("filtro %d does not fit a signed char" % f)

        n3 = n * 3
        c0 = first * 3

        # step 1 -- copy
        if src is SELF:
            if "NOSELF" in self.breaks:
                # the sabotage: pretend there is a separate source buffer that
                # still holds the PREVIOUS contents (all zeros here)
                for i in range(n3):
                    self.pal6[c0 + i] = 0
            # otherwise: source aliases destination, the copy is a no-op and
            # step 2 filters in place
        else:
            if len(src) < n3:
                raise ValueError("source table has %d entries, need %d" % (len(src), n3))
            for i in range(n3):
                self.pal6[c0 + i] = src[i]

        # step 2 -- filter in place
        div = 64 if "DIV64" in self.breaks else 63
        c = c0
        while c < c0 + n3:
            for f in (fr, fg, fb):
                temp = self.pal6[c] * f
                temp //= div
                if "NOCLAMP" not in self.breaks:
                    if temp > 63:
                        temp = 63
                self.pal6[c] = temp & 0xFF
                c += 1

        # step 3 -- upload
        end = c0 + n3
        start = c0 if "UPLOADFIRST" in self.breaks else 0
        for i in range(start, end):
            self.curpal6[i] = self.pal6[i]
        self.uploads.append((start, end))

    # -- NOCTIS-0.CPP:1151-1200 -----------------------------------------

    def shade(self, first_color, number_of_colors, sr, sg, sb, fr, fg, fb):
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
            # Equivalent to a plain clamp; kept in this shape to match the
            # source, not because it changes any result.
            return 63 if v > 0 else 0

        while count:
            self.pal6[i + 0] = place(cr)
            self.pal6[i + 1] = place(cg)
            self.pal6[i + 2] = place(cb)
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


# ------------------------------------------------------------- scenarios

# Pinned inputs for the surface scenario.  These are NOT derived from a star;
# they are fixed so both implementations compute the same object, and they are
# chosen to exercise every branch of shade()'s inverted clamp: a negative
# start, an above-64 finish, and an exact 64.0.
SURFACE_ARGS = dict(
    colorbase=128,
    r1=3.25, g1=5.50, b1=7.75,
    r2=19.50, g2=24.75, b2=33.00,
    r3=66.25, g3=-2.50, b3=48.125,
    brt=64,
)


def scenario_boot(breaks=()):
    """NOCTIS.CPP:2218-2219, the two calls main() makes before the game loop.
    The second one is the self-copy: tavola_colori(tmppal, 0, 256, 64,64,64)."""
    p = Palette(breaks)
    p.tavola_colori(range8088_generated(), 0, 64, 16, 32, 63)
    p.tavola_colori(SELF, 0, 256, 64, 64, 64)
    return p


def scenario_surface(breaks=()):
    """boot, then NOCTIS-0.CPP:5180-5193's four-rung shade ladder into band
    128..191 followed by the band's own self-copy tavola_colori.

    Steps 1-2 exist to make the UPLOAD-FROM-ZERO rule observable, and they
    are not decoration: shade() writes tmppal WITHOUT uploading, and
    NOCTIS.CPP:3777 re-filters the sky band 64..127 every frame.  Because the
    upload runs from colour 0 to (first+n)*3, that sky update is what carries
    the changed band 0..63 to the DAC.  A scenario that only ever touches the
    band it uploads cannot tell the two upload rules apart -- the first
    version of this scenario could not, and BREAK_UPLOADFIRST slipped through.
    """
    p = scenario_boot(breaks)
    a = SURFACE_ARGS
    cb = a["colorbase"]
    # 1. change band 0..63 with shade(), which does NOT upload
    p.shade(0, 64, 8.0, 8.0, 8.0, 40.0, 52.0, 63.0)
    # 2. the sky band's own self-copy filter: uploads [0, 384), so it is this
    #    call that pushes the band-0 change above to the DAC
    p.tavola_colori(SELF, 64, 64, 48, 52, 63)
    p.shade(cb + 0, 16, 0.0, 0.0, 0.0, a["r1"], a["g1"], a["b1"])
    p.shade(cb + 16, 16, a["r1"], a["g1"], a["b1"], a["r2"], a["g2"], a["b2"])
    p.shade(cb + 32, 16, a["r2"], a["g2"], a["b2"], a["r3"], a["g3"], a["b3"])
    p.shade(cb + 48, 16, a["r3"], a["g3"], a["b3"], 64.0, 64.0, 64.0)
    p.tavola_colori(SELF, cb, 64, a["brt"], a["brt"], a["brt"])
    return p


SCENARIOS = {"boot": scenario_boot, "surface": scenario_surface}


# ------------------------------------------------ Tier 1: the 1996 artifact


def fit_filter(observed64, src=None):
    """Given 64 observed 6-bit values for one channel of band 0..63, return
    every integer filter f for which  min(v*f//63, 63)  reproduces all 64.

    This grades tavola_colori's filter arithmetic against a capture of the
    1996 binary with only ONE fitted integer per channel over 64 samples.  If
    the division were /64, or rounded instead of truncated, no f would fit.
    """
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
    # falsifiers: no f should fit under round-to-nearest or /64
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

    # P2 -- upload always starts at colour 0, so a high band leaves the tail
    #       stale and refreshes everything below it
    p = Palette(breaks)
    p.pal6 = [0] * 768
    p.tavola_colori([63] * 192, 64, 64, 63, 63, 63)   # write band 64..127
    req(p.uploads[-1] == (0, 384), "P2 upload span is [0,384) not [192,384)  (got %s)" % (p.uploads[-1],))
    req(all(v == 0 for v in p.curpal6[384:]), "P2 colours 128..255 left stale by the upload")

    # P3 -- the self-copy is a no-op, so a second identical filter compounds
    p = Palette(breaks)
    p.tavola_colori(range8088_generated(), 0, 64, 63, 63, 63)
    before = list(p.pal6[:192])
    p.tavola_colori(SELF, 0, 64, 32, 32, 32)
    after = list(p.pal6[:192])
    req(after == [min(v * 32 // 63, 63) for v in before],
        "P3 self-copy filters in place (compounds) rather than reloading a source")

    # P4 -- shade's inverted clamp: >64 saturates to 63, negative to 0,
    #       and the in-range case truncates
    p = Palette(breaks)
    p.shade(0, 4, 62.75, -1.0, 64.0, 66.75, -1.0, 64.0)
    req(p.pal6[0] == 62, "P4 shade truncates 62.75 -> 62  (got %d)" % p.pal6[0])
    req(p.pal6[1] == 0, "P4 shade sends -1.0 -> 0  (got %d)" % p.pal6[1])
    req(p.pal6[2] == 63, "P4 shade sends 64.0 -> 63  (got %d)" % p.pal6[2])

    # P5 -- the LUT scaling is x4
    p = Palette(breaks)
    p.curpal6 = [63, 32, 0] + [0] * 765
    req(p.lut()[0] == 0xFC8000, "P5 LUT (63,32,0) -> 0x00FC8000  (got 0x%08X)" % p.lut()[0])

    # P7 -- the filter arithmetic itself: truncating /63 and the >63 clamp.
    #       Inputs chosen so /63 and /64 disagree and so the clamp fires;
    #       P3 alone does not separate them.
    p = Palette(breaks)
    p.tavola_colori([63, 63, 63, 32, 32, 32], 0, 2, 63, 63, 63)
    req(p.pal6[0] == 63 and p.pal6[3] == 32,
        "P7 filter v*63/63 is identity  (got %d, %d)" % (p.pal6[0], p.pal6[3]))
    p = Palette(breaks)
    p.tavola_colori([63, 63, 63, 62, 62, 62], 0, 2, 127, 127, 127)
    req(p.pal6[0] == 63, "P7 filter clamps 63*127/63 = 127 -> 63  (got %d)" % p.pal6[0])
    req(p.pal6[3] == 63, "P7 filter clamps 62*127/63 = 124 -> 63  (got %d)" % p.pal6[3])
    p = Palette(breaks)
    p.tavola_colori([1, 1, 1], 0, 1, 62, 62, 62)
    req(p.pal6[0] == 0, "P7 filter truncates 1*62/63 = 0 (not 1)  (got %d)" % p.pal6[0])
    p = Palette(breaks)
    p.tavola_colori([32, 32, 32], 0, 1, 63, 63, 63)
    req(p.pal6[0] == 32, "P7 filter /63 not /64: 32*63/63 = 32  (got %d)" % p.pal6[0])

    # P6 -- filtro_* range assertion actually fires
    p = Palette(breaks)
    try:
        p.tavola_colori([0] * 3, 0, 1, 200, 0, 0)
        req(False, "P6 filtro 200 rejected as not fitting a signed char")
    except ValueError:
        req(True, "P6 filtro 200 rejected as not fitting a signed char")

    return ok, out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", choices=sorted(SCENARIOS), default="boot")
    ap.add_argument("--dump-pal6", metavar="PATH")
    ap.add_argument("--dump-lut", metavar="PATH")
    ap.add_argument("--capture", metavar="PATH", help="a BMP/PNG capture to run the Tier 1 fit against")
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

    p = SCENARIOS[args.scenario](args.brk)
    print("scenario %r: pal6 nonzero %d, curpal6 nonzero %d, uploads %s"
          % (args.scenario, sum(1 for v in p.pal6 if v),
             sum(1 for v in p.curpal6 if v), p.uploads))
    print("  pal6[0:12]    %s" % p.pal6[:12])
    print("  pal6[189:192] %s" % p.pal6[189:192])
    if args.scenario == "surface":
        print("  pal6[384:396] %s" % p.pal6[384:396])
        print("  pal6[573:576] %s" % p.pal6[573:576])
    print("  lut[0:4]      %s" % ["%08X" % v for v in p.lut()[:4]])
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
        fbdump_write(args.dump_pal6, KIND_PALETTE6, p.pal6)
        print("wrote %s" % args.dump_pal6)
    if args.dump_lut:
        fbdump_write(args.dump_lut, KIND_LUT, p.lut())
        print("wrote %s" % args.dump_lut)

    print("RESULT: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
