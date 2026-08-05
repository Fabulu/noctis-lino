#!/usr/bin/env python3
"""fbgrade.py - for every sabotage, print the OBSERVABLES that moved.

Rewritten for FBDUMP v2 and for the Wave 5-corrective sabotage register.

The house standard is that every check must be provably breakable, demonstrated
by breaking the thing it guards.  This compares each sabotage's FBDUMP against
its harness's reference dump - fbshort for the shell (the reference at the SAME
driver constants as the sabotages), fbsrv for the servo battery, fbshade for the
shade battery - and prints which named observable changed.

A sabotage that changes NOTHING is a blind spot and is reported as one.  That is
the whole point: FBDUMP v1's kind 6 was bit-identical between a clean build and
a build with no canary in it, and nothing in the project could see it.

Usage: python fbgrade.py
"""
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
MAGIC = 0x46424431

TAGNAME = {1: "adapted", 2: "adaptor", 3: "glyph", 4: "pal6", 5: "curpal6",
           6: "lut", 7: "layout", 8: "canary", 9: "zones", 10: "ticklog",
           11: "servolog", 12: "wrapcount", 13: "selfcheck", 14: "framecost",
           15: "wrapbat", 16: "sky", 17: "srfpal6",
           19: "srv_windows", 20: "srv_oldreplay",
           22: "fade48", 23: "fade24", 24: "fade24_compounded"}

SHELL_SELF = {
    0: "bchk", 1: "qchk", 2: "txchk",
    5: "canary_clean_fired", 6: "canary_clean_n", 7: "canary_clean_exp",
    8: "glyph_expectation", 9: "glyph_violation_pad",
    10: "wrap_predicate_failures", 18: "skips", 22: "pv_range",
    32: "cal_why", 34: "servolog_overflow",
    40: "glyph_violation_units", 41: "containment_failures",
    42: "containment_at", 43: "spot_cases_relocated",
    44: "spot_delta_min", 45: "spot_delta_max",
    46: "cirrus_delta_min", 47: "cirrus_delta_max",
    48: "maskpixels_precondition",
}
SRV_SELF = {
    5: "round_truncated", 6: "round_rounded",
    7: "clampfloor_after_1", 8: "clampfloor_after_5",
    10: "rebase_window_1_ms", 11: "rebase_why_1",
    12: "rebase_window_2_ms", 13: "rebase_why_2",
    15: "fold_at_000000_100", 17: "fold_delta",
    18: "midnight_why", 19: "midnight_cpms",
    21: "ring_failures", 30: "servolog_overflow",
    32: "rebase_counts_1", 33: "rebase_counts_2",
}
SHADE_SELF = {
    0: "sentinel_broken", 1: "srfpal6_nonzero", 2: "pal6_nonzero_after_ladder",
    3: "fade_components_differing", 4: "fade_max_difference",
    6: "pal6[0]", 7: "pal6[1]", 8: "pal6[2]",
}

CASES = [
    ("fbbreak1", "fbshort", "LUT (v<<2)|(v>>4) instead of v*4"),
    ("fbbreak2", "fbshort", "tavola uploads only its own band"),
    ("fbbreak3", "fbshort", "shade rounds instead of chopping"),
    ("fbbreak4", "fbshort", "unsigned timestamp compare"),
    ("fbbreak5", "fbshort", "no skip-to-grid"),
    ("fbbreak6", "fbshort", "FB draw raster loop from y = 1"),
    ("fbbreak7", "fbshort", "guard check that can never fire"),
    ("fbbreak8", "fbshort", "tinta/escrescenze at 64000"),
    ("fbbreak9", "fbshort", "layout in declaration order"),
    ("fbbreak10", "fbshort", "byte store packed 4 per unit"),
    ("fbsrvrunstart", "fbsrv", "S-SRV-RUNSTART: no re-base"),
    ("fbsrvunsigned", "fbsrv", "S-SRV-UNSIGNEDBAND"),
    ("fbsrvwidemax", "fbsrv", "S-SRV-WIDEMAX"),
    ("fbsrvtrunc", "fbsrv", "S-SRV-TRUNC"),
    ("fbsrvclampfl", "fbsrv", "S-SRV-CLAMPFLOOR"),
    ("fbsrvnofold", "fbsrv", "S-WALL-NOFOLD"),
    ("fbmaskspot", "fbshort", "S-MASK-SPOT"),
    ("fbmaskcirrus", "fbshort", "S-MASK-CIRRUS-ADDR"),
    ("fbsegbase", "fbshort", "S-SEGADDR-BASE"),
    ("fbpadonemagic", "fbshort", "S-PAD-ONEMAGIC"),
    ("fbpadnodigit", "fbshort", "S-PAD-NODIGIT"),
    ("fbpad9walk", "fbshort", "S-PAD-9WALK"),
    ("fbcanstubpoison", "fbshort", "S-CAN-STUBPOISON"),
    ("fbcanconst", "fbshort", "S-CAN-CONSTACTUAL"),
    ("fbshdst", "fbshade", "SH-IGNOREDST"),
    ("fbs12", "fbshort", "S12: colour cycle fused into the expand"),
]
SELFMAP = {"fbshort": SHELL_SELF, "fbsrv": SRV_SELF, "fbshade": SHADE_SELF}

# timing-dependent records: not discriminators, excluded and SAID so
NOISY = {10, 14, 11}

# self words that are MEASUREMENTS, not values.  A difference here is only a
# discriminator if it is large; a few counts is jitter.  Named rather than
# silently dropped, because "the check moved" has to mean the check moved.
TOLERANT = {"rebase_counts_1", "rebase_counts_2"}
# skip counts jitter by one because a hitch can straddle a grid point;
# a change of more than one is a discriminator, a change of one is not.
JITTER1 = {"skips"}
TOLERANCE = 0.01
TOLFLOOR = 1000      # counts; 1000 at 9000 cpms is 0.11 ms


def load(tag):
    buf = open(os.path.join(HERE, tag + ".bin"), "rb").read()
    off, by = 0, {}
    while off + 64 <= len(buf):
        h = struct.unpack_from("<16I", buf, off)
        assert h[0] == MAGIC, tag
        n = h[5]
        by[h[8]] = struct.unpack_from("<%dI" % n, buf, off + 64) if n else ()
        off += 64 + 4 * n
    return by


def s32(v):
    return v - (1 << 32) if v >= (1 << 31) else v


def main():
    blind = []
    print("excluded as timing-dependent, not as passing: ticklog, framecost, "
          "servolog\n")
    for name, ref, headline in CASES:
        a, b = load(ref), load(name)
        moved = []
        for tag in sorted(set(a) | set(b)):
            if tag in NOISY:
                continue
            pa, pb = a.get(tag, ()), b.get(tag, ())
            if tag == 13:
                for i, nm in sorted(SELFMAP[ref].items()):
                    if i >= len(pa) or i >= len(pb) or pa[i] == pb[i]:
                        continue
                    x, y = s32(pa[i]), s32(pb[i])
                    if nm in JITTER1 and abs(x - y) <= 1:
                        continue
                    if nm in TOLERANT:
                        base = max(abs(x), abs(y), 1)
                        if abs(x - y) < max(TOLFLOOR, TOLERANCE * base):
                            continue
                    moved.append("%s  %d -> %d" % (nm, x, y))
                continue
            if pa != pb:
                if len(pa) != len(pb):
                    moved.append("%s length %d -> %d"
                                 % (TAGNAME.get(tag, tag), len(pa), len(pb)))
                else:
                    d = sum(1 for x, y in zip(pa, pb) if x != y)
                    moved.append("%s differs in %d of %d units"
                                 % (TAGNAME.get(tag, tag), d, len(pa)))
        print("%-16s %s" % (name, headline))
        if moved:
            for m in moved:
                print("      caught: %s" % m)
        else:
            print("      *** NOTHING MOVED - BLIND SPOT ***")
            blind.append(name)
        print()
    print("sabotages: %d,  blind spots: %d %s"
          % (len(CASES), len(blind), blind if blind else ""))


main()
