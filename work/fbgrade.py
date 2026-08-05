#!/usr/bin/env python3
"""fbgrade.py - grade the reference build and require every sabotage to be caught.

The rule this file enforces: for each of the ten breaks, a named predicate must
PASS on the reference dump and FAIL on that break's dump.  A predicate that
fails on the reference is a broken test, not a caught sabotage, and is reported
as such - so a test that always fails cannot be mistaken for a test that works.

Usage: python fbgrade.py
"""
import struct
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
MAGIC = 0x46424431
TARGET_MS = 65536 / 1193182.0 * 1000.0        # 54.9254012...


def load(tag):
    data = open(os.path.join(HERE, tag + ".bin"), "rb").read()
    recs = []
    off = 0
    while off + 64 <= len(data):
        h = struct.unpack_from("<16I", data, off)
        assert h[0] == MAGIC and h[1] == 1
        n = h[5]
        recs.append({"kind": h[2], "w": h[3], "h": h[4],
                     "p": struct.unpack_from("<%dI" % n, data, off + 64) if n else ()})
        off += 64 + 4 * n
    assert off == len(data)
    d = {}
    for r in recs:
        d.setdefault(r["kind"], []).append(r["p"])
    return d


# ---------------------------------------------------------------- predicates
# Each returns (ok, detail).  ok must be True for the reference.

def p_layout(d, _ref):
    lay = d[5][0]
    # derived independently from NOCTIS-D.H sizes, in main()'s farmalloc order
    want = [("n_offsets_map", 7340), ("n_globes_map", 32768),
            ("s_background", 64800), ("p_background", 65552),
            ("p_surfacemap", 40000), ("objectschart", 40000),
            ("pvfile", 20480), ("adapted", 65540), ("adaptor", 65540)]
    base = 32
    for i, (nm, sz) in enumerate(want):
        b, s, pb, rid = lay[4 * i:4 * i + 4]
        if rid != i:
            return False, "region %d has id %d" % (i, rid)
        if b != base:
            return False, "%s base %d, expected %d" % (nm, b, base)
        if s != sz:
            return False, "%s size %d, expected %d (NOCTIS-D.H)" % (nm, s, sz)
        if pb != b + s:
            return False, "%s padbase %d" % (nm, pb)
        base = b + s + 16
    if base != 402196:
        return False, "top %d" % base
    return True, "9 regions, farmalloc order, 16-unit pads, top 402196"


def p_bytes(d, _ref):
    v = d[7][0][0]
    return v == 0, "bchk=%d" % v


def p_canary(d, _ref):
    s = d[7][0]
    clean_f, clean_n, dirty_f, dirty_n, dirty_at = s[5], s[6], s[7], s[8], s[9]
    if clean_f or clean_n:
        return False, "clean check fired (%d,%d)" % (clean_f, clean_n)
    if dirty_f != 2 or dirty_n != 1 or dirty_at != 40156:
        return False, ("one-unit overrun not caught as region 1: "
                       "fired=%d n=%d at=%d" % (dirty_f, dirty_n, dirty_at))
    return True, "clean=0, injected overrun -> region 1 at nw+40156, 1 unit"


def p_wrap(d, _ref):
    s = d[7][0]
    return s[10] == 0 and s[11] > 400000, \
        "failures=%d over %d constructed cases" % (s[10], s[11])


def p_lut(d, _ref):
    cur = d[2][1]
    lut = d[3][0]
    for c in range(256):
        want = ((cur[3 * c] & 63) * 4 << 16) | ((cur[3 * c + 1] & 63) * 4 << 8) \
               | ((cur[3 * c + 2] & 63) * 4)
        if lut[c] != want:
            return False, "colour %d: %06X != %06X" % (c, lut[c], want)
    return True, "all 256 entries are curpal6 * 4"


def p_lut_same(d, ref):
    return d[3][0] == ref[3][0], "LUT record identical to reference"


def p_curpal_same(d, ref):
    n = sum(1 for i in range(768) if d[2][1][i] != ref[2][1][i])
    return n == 0, "curpal6 differs from reference in %d components" % n


def p_pal6_same(d, ref):
    n = sum(1 for i in range(768) if d[2][0][i] != ref[2][0][i])
    return n == 0, "pal6 differs from reference in %d components" % n


def p_stale(d, _ref):
    pal6, cur = d[2][0], d[2][1]
    diff = [c for c in range(256)
            if pal6[3 * c:3 * c + 3] != cur[3 * c:3 * c + 3]]
    lo = [c for c in diff if c < 128]
    if lo:
        return False, "colours below 128 stale: %s" % lo[:8]
    if not diff:
        return False, "no stale band at all - S12 should have left one"
    return True, ("upload-from-zero holds: 0..127 current, %d stale colours "
                  "all >= 128 (%d..%d)" % (len(diff), min(diff), max(diff)))


def p_page_same(d, ref):
    n = sum(1 for i in range(64000) if d[1][0][i] != ref[1][0][i])
    return n == 0, "adapted page differs from reference in %d pixels" % n


def p_page_row0(d, _ref):
    p = d[1][0]
    bad = [x for x in range(320) if p[x] != (0 * x + x + 0) & 255]
    return not bad, "row 0 correct" if not bad else "row 0 wrong in %d px" % len(bad)


def p_tinta(d, _ref):
    p = d[1][0]
    return (p[63996], p[63997]) == (17, 34), \
        "adapted[63996..7] = %d,%d (row 199 cols 316-317)" % (p[63996], p[63997])


def p_skip(d, _ref):
    tk = d[4][0]
    s = d[7][0]
    srv = [(s[32 + 2 * i], s[33 + 2 * i]) for i in range(8) if s[33 + 2 * i]]
    n = len(tk) // 3

    def sd(a, b):
        x = (a - b) & 0xFFFFFFFF
        return x - 0x100000000 if x >= 0x80000000 else x
    cpms_at = [0] * n
    cur = srv[0][1] if srv else s[13]
    j = 0
    for i in range(n):
        while j < len(srv) and srv[j][0] <= i:
            cur = srv[j][1]; j += 1
        cpms_at[i] = cur
    per = [sd(tk[3 * i], tk[3 * (i - 1)]) / cpms_at[i] for i in range(1, n)]
    lat = [sd(tk[3 * i], tk[3 * i + 1]) / cpms_at[i] for i in range(n)]
    bb = [i for i in range(1, n) if per[i - 1] < TARGET_MS * 0.5]
    skips = sum(1 for i in range(n) if tk[3 * i + 2] & 1)
    # The behavioural signature, and the one that does not merely re-read the
    # flag the sabotage removes: with skip-to-grid the deadline is ALWAYS in
    # the future when the wait starts, so no tick can fire measurably late.
    # Without it, an overrunning frame fires immediately and its lateness is
    # the whole of the overrun.
    late = [(i, lat[i]) for i in range(n) if lat[i] > 1.0]
    if late:
        return False, ("%d ticks fired more than 1 ms late, worst %.3f ms at "
                       "tick %d - the deadline was already in the past"
                       % (len(late), max(x for _, x in late),
                          max(late, key=lambda t: t[1])[0]))
    if bb:
        return False, ("%d back-to-back fires after a hitch (first at tick %d, "
                       "%.3f ms)" % (len(bb), bb[0], per[bb[0] - 1]))
    if skips == 0:
        return False, "no grid point was ever skipped - the hitch never fired"
    return True, ("%d grid points skipped, 0 back-to-back fires, max lateness "
                  "%.4f ms" % (skips, max(lat)))


def p_period(d, _ref):
    tk = d[4][0]
    s = d[7][0]
    srv = [(s[32 + 2 * i], s[33 + 2 * i]) for i in range(8) if s[33 + 2 * i]]
    n = len(tk) // 3

    def sd(a, b):
        x = (a - b) & 0xFFFFFFFF
        return x - 0x100000000 if x >= 0x80000000 else x
    cpms_at = [0] * n
    cur = srv[0][1] if srv else s[13]
    j = 0
    for i in range(n):
        while j < len(srv) and srv[j][0] <= i:
            cur = srv[j][1]; j += 1
        cpms_at[i] = cur
    err = 0.0
    steps = 0
    for i in range(1, n):
        c = cpms_at[i]
        ideal = c * 32768000 / 596591.0
        got = sd(tk[3 * i + 1], tk[3 * (i - 1) + 1])
        k = round(got / ideal)
        err += (got - k * ideal) / c
        steps += k
    if abs(err) > 1.0:
        return False, "accumulated deadline error %.4f ms over %d grid points" % (err, steps)
    return True, ("accumulated deadline error %+.5f ms over %d grid points "
                  "(budget 1 ms)" % (err, steps))


TESTS = {
    "layout": p_layout,
    "bytes": p_bytes,
    "canary": p_canary,
    "wrap": p_wrap,
    "lut_is_x4": p_lut,
    "lut_same": p_lut_same,
    "curpal_same": p_curpal_same,
    "pal6_same": p_pal6_same,
    "upload_from_zero": p_stale,
    "page_same": p_page_same,
    "page_row0": p_page_row0,
    "tinta_at_63996": p_tinta,
    "skip_to_grid": p_skip,
    "period_exact": p_period,
}

# which predicate each sabotage must break
BREAKS = {
    1:  ("lut_is_x4",        "LUT built with (v<<2)|(v>>4) instead of v*4"),
    2:  ("curpal_same",      "tavola_colori uploads only its own band"),
    3:  ("pal6_same",        "shade() rounds to nearest instead of chopping"),
    4:  ("wrap",             "unsigned timestamp compare instead of the sign"),
    5:  ("skip_to_grid",     "no skip-to-grid after a missed deadline"),
    6:  ("page_row0",        "raster loop started at 1 (niv-lr's digit_at bug)"),
    7:  ("canary",           "canary check that can never fire"),
    8:  ("tinta_at_63996",   "tinta/escrescenze relocated to 64000 (niv-lr)"),
    9:  ("layout",           "declaration order instead of farmalloc order"),
    10: ("bytes",            "byte store packed four to a unit"),
}


def main():
    ref = load("fbmain")
    print("=== REFERENCE BUILD (fbmain.bin) ===")
    refok = {}
    bad = 0
    for name, fn in TESTS.items():
        ok, detail = fn(ref, ref)
        refok[name] = ok
        print("  %-18s %-4s %s" % (name, "PASS" if ok else "FAIL", detail))
        if not ok:
            bad += 1
    print()
    print("=== SABOTAGES: each must be CAUGHT by its named predicate ===")
    caught = 0
    for n in sorted(BREAKS):
        pname, what = BREAKS[n]
        try:
            d = load("fbbreak%d" % n)
        except FileNotFoundError:
            print("  break %-2d MISSING dump" % n); bad += 1; continue
        ok, detail = TESTS[pname](d, ref)
        if not refok[pname]:
            print("  break %-2d BROKEN-TEST  %s already fails on the reference"
                  % (n, pname))
            bad += 1
            continue
        if ok:
            print("  break %-2d NOT CAUGHT   %-18s %s" % (n, pname, detail))
            bad += 1
        else:
            caught += 1
            print("  break %-2d caught by     %-18s %s" % (n, pname, detail))
        print("           sabotage: %s" % what)
    print()
    print("reference predicates passing : %d/%d" % (sum(refok.values()), len(TESTS)))
    print("sabotages caught             : %d/%d" % (caught, len(BREAKS)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
