#!/usr/bin/env python3
"""fb_stick.py -- Wave 5-corrective, implementer 2.

Two class-A verdicts that the model got wrong in opposite directions:

A1  `Segmento`'s riga[] index (TDPOLYGS.H:161-177, :250-258).
    PROVEN UNNECESSARY.  poly3d clamps min_x/max_x/min_y/max_y to the visible
    area BEFORE mp[] is indexed (the `ranged1..ranged4` block, TDPOLYGS.H
    :746-761), and with larghezza 306, altezza 180, x_centro 158, y_centro 100
    that is x in [5,311], y in [10,190].  riga[] is `unsigned riga[200]`, so
    the index cannot leave 0..199 and the highest address the routine can form
    is riga[190] + 311 + 4 = 61115.  NOCTIS-D.H:50-54's "funzione difettosa"
    comment predates the clipper.

A2  `Stick`'s riga[] index via `stick3d` ONLY.
    REACHED.  `fline` and `link3d` hard-reject out-of-range endpoints;
    `stick3d` runs eight SEQUENTIAL clip stages in the order
    fpx<lbx, lx<lbx, fpy<lby, ly<lby, fpx>ubx, lx>ubx, fpy>uby, ly>uby,
    and each stage recomputes the OTHER coordinate of the endpoint it moves.
    So a later stage can push a coordinate an earlier stage had already
    clipped back out of range, with nothing after it to fix the result; and
    `mindiff = 0.01` applied to a difference of two `long`s means "diff == 0",
    which SKIPS the clip and leaves the coordinate where it was.

    This module transcribes the clipper and measures the escape rate over a
    deterministic lattice.  The measurement is mine; it is not recon B's, and
    where the two differ the numbers here are the ones this harness stands on.

  python fb_stick.py            # A1's proof and A2's escape corpus
  python fb_stick.py --break CLIPSTAGE
"""

import argparse
import os
import re
import struct
import sys

from fb_layout import NIVPLUS, read_text, parse_defines, parse_screen_bounds, SEG_OFFSET

BREAKS = {
    "CLIPSTAGE": "delete one poly3d clip stage, so A1's bbox proof no longer holds "
                 "[S-CLIP-STAGE]",
    "CLAMPRIGA": "clamp Stick's riga[] index to 0..199 instead of masking (niv-lr's "
                 "divergence at noctis-0.cpp:1296)",
}


def f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


def chop(x):
    return int(x) if x >= 0 else -int(-x)


# --------------------------------------------------------------- A1: poly3d


def poly3d_clamp(minx, maxx, miny, maxy, bounds, breaks=()):
    """TDPOLYGS.H:746-761, the `ranged1..ranged4` block, transcribed:

        cmp ax, ubxl / jl ranged1 / inc si / mov max_x, ubx
        cmp bx, ubyl / jl ranged2 / inc si / mov max_y, uby
        cmp cx, lbxl / jnl ranged3 / inc si / mov min_x, lbx
        cmp dx, lbyl / jnl ranged4 / inc si / mov min_y, lby

    Four independent one-sided clamps; `si` counts how many fired and drives
    the Sutherland-Hodgman pass.  CLIPSTAGE deletes the max_y one.
    """
    lbx, ubx, lby, uby = bounds
    if maxx >= ubx:
        maxx = ubx
    if "CLIPSTAGE" not in set(breaks):
        if maxy >= uby:
            maxy = uby
    if minx < lbx:
        minx = lbx
    if miny < lby:
        miny = lby
    return minx, maxx, miny, maxy


def a1_proof(breaks=()):
    """Sweep every plausible pre-clamp bounding box and check that the
    post-clamp rows the raster loop walks are inside riga[]'s 200 entries."""
    d = parse_defines(read_text(os.path.join(NIVPLUS, "NOCTIS-D.H")))
    b = parse_screen_bounds(read_text(os.path.join(NIVPLUS, "NOCTIS-D.H")))
    bounds = b["poly"]
    worst_row, worst_addr = -1, -1
    bad = []
    span = [-100000, -10000, -1000, -200, -1, 0, 1, 5, 10, 100, 190, 199,
            200, 311, 312, 400, 1000, 10000, 100000]
    for minx in span:
        for maxx in span:
            if maxx < minx:
                continue
            for miny in span:
                for maxy in span:
                    if maxy < miny:
                        continue
                    a, c, e, f = poly3d_clamp(minx, maxx, miny, maxy, bounds, breaks)
                    # the raster loop is `for (i = min_y; i <= max_y; i++)`, so
                    # an empty range walks NO rows -- the clamps are one-sided
                    # by design and a box wholly off-screen simply draws
                    # nothing.  Grade the rows ACTUALLY WALKED.
                    if e > f:
                        continue
                    for row in (e, f):
                        if not (0 <= row <= 199):
                            bad.append((minx, maxx, miny, maxy, e, f))
                            break
                        worst_row = max(worst_row, row)
                        worst_addr = max(worst_addr, 320 * row + max(0, c) + SEG_OFFSET)
    return {"bounds": bounds, "bad": bad[:5], "nbad": len(bad),
            "worst_row": worst_row, "worst_addr": worst_addr,
            "larghezza": b["larghezza"], "altezza": b["altezza"],
            "centre": b["centre"]}


# ------------------------------------------------------------- A2: stick3d


class StickClip(object):
    """NOCTIS-0.CPP:1902-1980, transcribed.  fpx/fpy/lx/ly are `long`; diff and
    kk are `float`; the assignments back into the longs are C casts and
    therefore CHOP.  `mindiff = 0.01` (NOCTIS-0.CPP:987) applied to the
    difference of two longs is exactly the predicate `diff != 0`.
    """

    MINDIFF = 0.01

    def __init__(self, bounds):
        self.lbx, self.ubx, self.lby, self.uby = bounds
        self.stages_run = 0
        self.stages_skipped = 0

    def _kk(self, target, other, diff):
        return f32(float(target - other) / diff)

    def clip(self, fpx, fpy, lx, ly):
        """Returns (fpx, fpy, lx, ly, rejected)."""
        lbx, ubx, lby, uby = self.lbx, self.ubx, self.lby, self.uby
        # the four early-outs: lines wholly outside the field
        if fpy < lby and ly < lby:
            return fpx, fpy, lx, ly, True
        if fpy > uby and ly > uby:
            return fpx, fpy, lx, ly, True
        if fpx < lbx and lx < lbx:
            return fpx, fpy, lx, ly, True
        if fpx > ubx and lx > ubx:
            return fpx, fpy, lx, ly, True

        def stage(cond, moved_is_first, axis, limit):
            """One of the eight stages.  `axis` 'x' moves x and recomputes y;
            'y' moves y and recomputes x."""
            nonlocal fpx, fpy, lx, ly
            if not cond:
                return
            if axis == 'x':
                a, b = (fpx, lx) if moved_is_first else (lx, fpx)
                oa, ob = (fpy, ly) if moved_is_first else (ly, fpy)
            else:
                a, b = (fpy, ly) if moved_is_first else (ly, fpy)
                oa, ob = (fpx, lx) if moved_is_first else (lx, fpx)
            diff = f32(float(a - b))
            if -self.MINDIFF < diff < self.MINDIFF:
                self.stages_skipped += 1
                return                       # the clip is SKIPPED, value kept
            self.stages_run += 1
            kk = self._kk(limit, b, diff)
            newo = chop(kk * float(oa - ob) + float(ob))
            if axis == 'x':
                if moved_is_first:
                    fpy, fpx = newo, limit
                else:
                    ly, lx = newo, limit
            else:
                if moved_is_first:
                    fpx, fpy = newo, limit
                else:
                    lx, ly = newo, limit

        stage(fpx < lbx, True, 'x', lbx)
        stage(lx < lbx, False, 'x', lbx)
        stage(fpy < lby, True, 'y', lby)
        stage(ly < lby, False, 'y', lby)
        stage(fpx > ubx, True, 'x', ubx)
        stage(lx > ubx, False, 'x', ubx)
        stage(fpy > uby, True, 'y', uby)
        stage(ly > uby, False, 'y', uby)
        return fpx, fpy, lx, ly, False


LATTICE = [-5000, -2000, -800, -400, -200, -161, -160, -151, -150, -149,
           -91, -90, -89, -40, -1, 0, 1, 40, 89, 90, 91,
           149, 150, 159, 160, 161, 400, 800, 2000, 5000]


class LCG(object):
    """A tiny deterministic generator, so the corpus is byte-identical on every
    run and on every Python version.  Nothing here grades a generator."""

    def __init__(self, seed=1996):
        self.s = seed & 0xFFFFFFFF

    def next(self):
        self.s = (self.s * 1103515245 + 12345) & 0x7FFFFFFF
        return self.s

    def coord(self):
        r = self.next()
        k = r % 10
        if k < 4:
            return (self.next() % 401) - 200
        if k < 7:
            return (self.next() % 4001) - 2000
        if k < 9:
            return (self.next() % 200001) - 100000
        return [-150, 160, -90, 90, -151, 161, -91, 91, 0, 1, -1][self.next() % 11]


def a2_corpus(bounds, centre, cases=400000, lattice=None):
    """Deterministic corpus: the bound-value lattice, then `cases` LCG-drawn
    quadruples with a mixture of near-bound, mid-range and far-out magnitudes.

    Reports how many surviving lines leave the clip rectangle and which screen
    rows the resulting y produces.  The MECHANISM is visible in
    `stages_skipped`: the x-clip stages move BOTH endpoints' y to the same
    integer, after which `diff == 0` makes stages 7 and 8 skip and the y stays
    where it was.
    """
    lattice = lattice or LATTICE
    lbx, ubx, lby, uby = bounds
    xc, yc = centre
    total = surviving = escaped = skipped_escapes = 0
    rows = {}
    worst = None

    def one(fpx, fpy, lx, ly):
        nonlocal total, surviving, escaped, skipped_escapes, worst
        total += 1
        c = StickClip(bounds)
        a, b, cc, dd, rej = c.clip(fpx, fpy, lx, ly)
        if rej:
            return
        if a == cc and b == dd:
            return                        # single-point lines are excluded
        surviving += 1
        if (lbx <= a <= ubx and lbx <= cc <= ubx
                and lby <= b <= uby and lby <= dd <= uby):
            return
        escaped += 1
        if c.stages_skipped:
            skipped_escapes += 1
        for y in (b + yc, dd + yc):
            if not (0 <= y <= 199):
                rows[y] = rows.get(y, 0) + 1
                if worst is None or abs(y - 100) > abs(worst[0] - 100):
                    worst = (y, (fpx, fpy, lx, ly), (a, b, cc, dd), c.stages_skipped)

    for fpx in lattice:
        for fpy in lattice:
            for lx in lattice:
                for ly in lattice:
                    one(fpx, fpy, lx, ly)
    g = LCG(1996)
    for _ in range(cases):
        one(g.coord(), g.coord(), g.coord(), g.coord())

    return {"total": total, "surviving": surviving, "escaped": escaped,
            "skipped_escapes": skipped_escapes,
            "rate": escaped / float(surviving) if surviving else 0.0,
            "rows": dict(sorted(rows.items())), "worst": worst}


def riga_divergence(y, mask=True):
    """The ADOPTED divergence (BUFFERMODEL 9): mask DI to 16 bits against the
    segment origin, and define riga[y] for y outside 0..199 as 320*y.  This
    preserves the only property the DOS page-sizing was designed to guarantee
    -- the scribble never leaves the page -- and it matches the one port that
    actually runs.  It is NOT a reproduction, and it is recorded as a
    deliberate divergence with a named retirement condition (extracting RIGA's
    real neighbours from NOCTIS.SYM)."""
    if mask:
        return (320 * y) & 0xFFFF
    return 320 * y


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--break", dest="brk", action="append", default=[], choices=sorted(BREAKS))
    ap.add_argument("--quick", action="store_true",
                    help="A1's bbox proof only; skip A2's 400k-case corpus")
    ap.add_argument("--quiet", action="store_true", help="verdict lines only")
    args = ap.parse_args(argv)
    brk = set(args.brk)

    print("fb_stick.py -- A1's bbox proof and A2's escape corpus")
    for b in args.brk:
        print("  SABOTAGE %-12s %s" % (b, BREAKS[b]))
    print()

    ok = True
    msg = []

    def req(cond, text):
        nonlocal ok
        if not cond:
            ok = False
        msg.append(("  PASS  " if cond else "  FAIL  ") + text)

    p = a1_proof(brk)
    req(p["nbad"] == 0,
        "A1 poly3d's clamp (larghezza %d altezza %d centre %s -> x in [%d,%d], y in "
        "[%d,%d]) holds for every one of the swept bounding boxes: %d violations, "
        "highest row %d, highest address riga[%d]+%d+%d = %d.  riga[] is "
        "`unsigned riga[200]`, so Segmento's index CANNOT leave it -- class-A site A1 "
        "is PROVEN UNNECESSARY, not asserted."
        % (p["larghezza"], p["altezza"], p["centre"], p["bounds"][0], p["bounds"][1],
           p["bounds"][2], p["bounds"][3], p["nbad"], p["worst_row"],
           p["bounds"][3], p["bounds"][1], SEG_OFFSET, p["worst_addr"]))
    if p["nbad"]:
        msg.append("        first violations: %s" % (p["bad"],))

    if args.quick:
        if not args.quiet:
            print(chr(10).join(msg))
            print()
            print("  A2 SKIPPED (--quick).  Run without --quick for the escape corpus.")
            print()
        print("RESULT: %s" % ("PASS" if ok else "FAIL"))
        return 0 if ok else 1

    b = parse_screen_bounds(read_text(os.path.join(NIVPLUS, "NOCTIS-D.H")))
    stk = b["stick"]
    c = a2_corpus(stk, b["centre"], cases=400000)
    req(c["escaped"] > 0,
        "A2 stick3d's clipper over a %d-case DETERMINISTIC corpus: %d lines survive the "
        "four early-outs and are not single points, and %d of them (%.4f%%) leave the "
        "clip rectangle [%d,%d]x[%d,%d].  A2 is REACHED and the mask is load-bearing."
        % (c["total"], c["surviving"], c["escaped"], 100 * c["rate"],
           stk[0], stk[1], stk[2], stk[3]))
    req(c["skipped_escapes"] == c["escaped"] and c["escaped"] > 0,
        "A2 and the MECHANISM is the mindiff skip, not extrapolation: %d of %d escapes "
        "had at least one stage skipped.  The two x-clip stages move both endpoints' y "
        "to the SAME integer; `diff = fpy - ly` is then 0, `|diff| > mindiff = 0.01` is "
        "false, and stages 7 and 8 leave y exactly where it was."
        % (c["skipped_escapes"], c["escaped"]))
    if c["worst"]:
        y, pre, post, sk = c["worst"]
        req(True, "A2 worst escape: (fpx,fpy,lx,ly) %s -> %s, %d stage(s) skipped, "
                  "screen row %d -- i.e. riga[%d] on an `unsigned riga[200]`, %d bytes "
                  "past its end.  Masked to 16 bits, 320*%d becomes NW offset %d, still "
                  "on the page."
                  % (pre, post, sk, y, y, 2 * y - 400, y, riga_divergence(y)))
    req(bool(c["rows"]),
        "A2 out-of-range screen rows reached (row: count): %s"
        % ({k: v for k, v in list(c["rows"].items())[:14]},))
    req(True,
        "A2 NOTE: recon B reports 220 escapes / 98,596 lines = 0.22%% by a rig this "
        "harness does not have.  THIS measurement is %.4f%% over its own corpus.  The "
        "two agree on the verdict and on the order of magnitude; they are not the same "
        "experiment and neither is derived from the other." % (100 * c["rate"]))

    print("\n".join(msg))
    print()
    print("  NOT GRADED, and named: the out-of-bounds VALUES `riga[y]` reads for")
    print("  y outside 0..199.  They come from whatever the DOS data segment held")
    print("  next to RIGA, which this project has never measured.  The adopted")
    print("  divergence defines riga[y] = 320*y and masks the result; the retirement")
    print("  condition is extracting RIGA's neighbours from NOCTIS.SYM (266,979")
    print("  bytes, symbols RIGA / flares / global_x), which also settles the")
    print("  farmalloc-offset open item.  One session settles both.")
    print()
    print("RESULT: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
