#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
sp_matrix.py -- Wave 6b: the C-side sabotage battery, REBUILT EVERY RUN.

House standard: every check provably breakable, DEMONSTRATED by breaking it.
`tests/w5audit.py` executes check conditions over random assignments and finds
ones that cannot fail -- but it reads Python, and the C oracle is outside its
reach.  The C side is covered by THIS battery and by nothing else.  Say so;
do not let a reader assume the audit covered it.

Built on `fb_compare.py:619-638`'s model, the soundest thing in the harness:
each defect is a one-line edit behind a -DBREAK_* macro, the binary is
recompiled from the SAME source on every run, and the result is joined
against the clean producers.  No stored .exe and no stored .dump is
consulted -- Wave 6a's O2 (a 9.4 MB artifact no current source can
regenerate) is why.

THE FIRST ROW IS THE POINT.  HARNESSAUDIT.md 5.3: feed the grading matrix the
CLEAN build and require NOT CAUGHT.  A battery that fires on a correct
implementation catches everything and means nothing.

Rows worth reading twice:
  * GMAN4 and DARKSHIFT move PAGES ONLY.  A fill-manager defect and a shift
    defect are invisible in every counter; the byte-exact page is the only
    thing that sees them.
  * DARKROWS moves the DARK FIELD ONLY, and NO page: the 180th row writes
    past the emitted 64,000-byte page (into p_background's tail), so the page
    check does NOT cover it.  That asymmetry is the argument for carrying
    both, and it is measured rather than assumed.
  * NCCZERO (zero slot 3 AFTER the scale pass) moves NINE fields, all on the
    SYNTHETIC model.  Every shipped loadpv call passes zero translation, so
    the three shipped models cannot tell "zeroed too late" from "zeroed in
    time".  --nozero (never zeroed) is the different defect and moves 354.
  * --scalemul=dbl moves NOTHING, and that is CORRECT, not a gap: the exact
    product of an int16 and a float32 needs at most 33 significand bits, so
    binary64 is exact too.  Only the FLOAT32 multiply rounds twice.
  * --castsrc=f64 moves NOTHING on this corpus.  A real LIMIT: these checks
    discriminate the rounding MODE (chop vs nearest) and do NOT discriminate
    whether the cast saw the live 80-bit value or a stored double.
  * --dgroup=ff and --dgroup=prng move exactly 2 pages, 9 bytes in total
    (4 in LWOOB, 5 in LWOOBHI).  That is the ENTIRE surface of the wave that
    depends on the unrecoverable DGROUP image behind glowinglobe's
    out-of-range riga[] read -- the NOT-GRADED set, measured, not asserted.

THIS FILE RENDERS NO VERDICTS.  It prints a table.  tests/test_sphere.py
decides what a row must say, in `linoharness.Check.ok`.

Usage:  python sp_matrix.py [--work DIR] [--cc gcc]
"""

import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sp_compare                                              # noqa: E402

BREAKS = [
    ("GLOWCLAMP",  "glowinglobe's Y clip becomes niv-lr's `pos > 10 && "
                   "pos < 190` -- an AND where vanilla has an OR"),
    ("GLOBEOFF1",  "globe's Y low bound 6 -> 7 (niv-lr's `pos > 6`)"),
    ("GMAN4",      "gman4x4's bottom row drops the farmalloc +4"),
    ("CURSORCLIP", "clipout forgets `add bx,1`: only DRAWN records advance "
                   "the tapestry cursor"),
    ("BGPLUS4",    "background drops the source `add bp,4` (niv-lr's "
                   "commented-out /*+4*/)"),
    ("DARKSHIFT",  "surface's day/night band shifts by 1 instead of 2"),
    ("DARKROWS",   "surface's band covers 180 rows instead of 179"),
    ("NCCZERO",    "loadpv zeroes the slot-3 garbage AFTER the scale pass"),
]

FLAGS = [
    (["--cast=near"],      "__ftol rounds half-to-even instead of chopping"),
    (["--castsrc=f64"],    "the cast sees a stored double, not the live "
                           "80-bit st(0)"),
    (["--scalemul=f32"],   "the pixel loop does a FLOAT32 multiply (double "
                           "rounding) instead of the exact chain"),
    (["--scalemul=dbl"],   "the pixel loop multiplies in binary64 -- a "
                           "CONTROL that must move nothing"),
    (["--nozero"],         "loadpv never zeroes the slot-3 garbage"),
    (["--dgroup=ff"],      "the unrecoverable DGROUP image is all 0xFF"),
    (["--dgroup=prng:0x1234"], "the DGROUP image is a different filler"),
]


def sh(*a, **kw):
    subprocess.run(list(a), check=True, cwd=HERE, **kw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default=os.path.join(HERE, "spwork"))
    ap.add_argument("--cc", default="gcc")
    x = ap.parse_args()
    W = x.work
    os.makedirs(W, exist_ok=True)
    corpus = os.path.join(HERE, "sp_corpus.spc")

    sh(sys.executable, "sp_mkcorpus.py", stdout=subprocess.DEVNULL)
    sh(x.cc, "-O2", "-std=gnu11", "-o", os.path.join(W, "sp_ref.exe"),
       "sp_ref.c", "-lm")
    ref = os.path.join(W, "ref.dump")
    refp = os.path.join(W, "pref")
    spec = os.path.join(W, "spec.dump")
    specp = os.path.join(W, "pspec")
    os.makedirs(refp, exist_ok=True)
    os.makedirs(specp, exist_ok=True)
    sh(os.path.join(W, "sp_ref.exe"), "--corpus=" + corpus,
       "--out=" + ref, "--pages=" + refp)
    sh(sys.executable, "sp_spec.py", "--corpus=" + corpus, "--out=" + spec,
       "--pages=" + specp, stdout=subprocess.DEVNULL)

    rows = []

    def run(tag, exe, extra, why):
        safe = "".join(c if c.isalnum() else "_" for c in tag)
        d = os.path.join(W, "m_%s.dump" % safe)
        pd = os.path.join(W, "mp_%s" % safe)
        os.makedirs(pd, exist_ok=True)
        sh(exe, "--corpus=" + corpus, "--out=" + d, "--pages=" + pd, *extra)
        r = sp_compare.full_compare(d, spec, pd, specp)
        per = {}
        for k, v in r["keyed"].items():
            if v["diffs"]:
                per[k] = len(v["diffs"])
        for k in ("slot3", "mid", "nonfin", "xsun", "wcentre", "bgidx", "oob",
                  "bgb", "swap", "sort", "pvl", "scale"):
            if r[k]["diffs"]:
                per[k.upper()] = len(r[k]["diffs"])
        if r["pages"]["ndiff"]:
            per["PAGE"] = "%d/%d" % (r["pages"]["ndiff"], r["pages"]["joined"])
        rows.append((tag, r["total_compared"], r["total_diffs"],
                     r["pages"]["ndiff"], r["pages"]["joined"], per, why))
        # 16 runs x 50 pages x 64,000 bytes is 51 MB of pages and 800 MB of
        # dumps if they are kept.  They are compared and then DELETED: a
        # stored artifact no current source regenerates is Wave 6a's O2, and
        # keeping one here would be the same mistake with a different name.
        for fn in os.listdir(pd):
            os.remove(os.path.join(pd, fn))
        os.rmdir(pd)
        os.remove(d)

    clean = os.path.join(W, "sp_ref.exe")
    run("NULL-INPUT (clean)", clean, [],
        "HARNESSAUDIT 5.3 -- MUST be NOT CAUGHT")
    for b, why in BREAKS:
        exe = os.path.join(W, "sp_brk_%s.exe" % b)
        sh(x.cc, "-O2", "-std=gnu11", "-DBREAK_" + b, "-o", exe,
           "sp_ref.c", "-lm")
        run(b, exe, [], why)
    for fl, why in FLAGS:
        run("flag " + " ".join(fl), clean, fl, why)

    print("%-24s %9s %7s %9s   %s"
          % ("SABOTAGE", "compared", "fields", "pages", "which records moved"))
    for t, c, d, pn, pj, per, why in rows:
        print("%-24s %9d %7d %5d/%-3d  %s"
              % (t, c, d, pn, pj, per if per else "-- NOTHING MOVED --"))
    print()
    for t, c, d, pn, pj, per, why in rows:
        print("  %-24s %s" % (t, why))
    print()
    nullrow = rows[0]
    print("null-input row moved %d fields and %d pages (must be 0 and 0)"
          % (nullrow[2], nullrow[3]))
    caught = sum(1 for r in rows[1:1 + len(BREAKS)] if r[2] or r[3])
    print("%d of %d compiled defects caught; %d flag controls run"
          % (caught, len(BREAKS), len(FLAGS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
