r"""su_solve.py - recovering (long)(k*secs) ALGEBRAICALLY instead of fitting it.

su_secs.py brute-forces a window of the guest clock.  That works only if the
window is right, and it grades the whole artefact against every candidate,
which is both slow and weak: a "best" candidate always exists.

This file does something much stronger and does not need a window at all.

THE ARGUMENT
------------
Every cloud painter writes through cirrus(), which only ever ADDS to the
overlay (NOCTIS-0.CPP:4716-4726).  So for the true parameters, the set of
overlay cells ONE cyclone touches must be a SUBSET of the cells that are
non-zero in the captured overlay.  That is a falsifiable, per-cyclone test
with 360 candidates, and it does not involve secs at all - the cyclone's
shape, radius, latitude and its three random(4) jitters are all fixed by the
FAST/BRTL streams, which the six secs-free captures already pinned.

Run it for every cyclone and most come back with EXACTLY ONE feasible cx.
Each of those is an equation

        (S / D_i) mod 360 == cx_i          C division, truncating

in the single unknown S = (long)(k*secs), with D_i known.  Two or three such
equations already pin S to a handful of values over the whole 31-bit range;
fifty of them leave one.

So S is not fitted against the map: it is SOLVED from the overlay, and the
map is then an independent check that was in no way used to choose it.  If
the solved S reproduces all 64,800 bytes, that is a genuine prediction.

A cyclone with ZERO feasible cx is a falsification of the model, not a reason
to relax the test - it would mean the painter writes somewhere the binary
never wrote.
"""

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import numpy as np

import su_seed
import su_spec
from su_fp import d2u16

OUT = r"C:\programmieren\linoleum\tests\gen\recon_w7a\out"
M16 = 0xFFFF


class _Tap(object):
    """Records the brtl values a painter consumes without changing them."""
    __slots__ = ("b", "sink")

    def __init__(self, b):
        self.b = b
        self.sink = None

    def random(self, n, site=0):
        v = self.b.random(n, site)
        if self.sink is not None:
            self.sink.append(v)
        return v

    def srand(self, v):
        self.b.srand(v)

    def __getattr__(self, k):
        return getattr(self.b, k)


def harvest(tag, painter, plwp=0):
    """One run with S = 0 that records each secs-dependent painter's
    secs-INDEPENDENT parameters, plus the divisors D_i."""
    man = json.load(open(os.path.join(OUT, "manifest.json")))
    e = [m for m in man if m["tag"] == tag][0]
    inp = su_seed.body_inputs(*e["star"], e["body"])
    log = []
    orig = getattr(su_spec.Surface, painter)

    def patched(self):
        rec = dict(cr=self.cr, cy=self.cy, g=self.g, gr=self.gr,
                   a=list(getattr(self, "_a6", [])), rnd=[])
        self.B.sink = rec["rnd"]
        orig(self)
        self.B.sink = None
        log.append(rec)

    setattr(su_spec.Surface, painter, patched)
    try:
        M = su_spec.Surface(ledger=False)
        M._secs_scaled = 0
        M.stop_after_switch = True
        M.B = _Tap(M.B)
        M.run(e["body"], e["planet_type"], inp["seedval"], inp["colorbase"],
              secs=0.0, plwp=plwp, owner=inp["owner"], nearstar_rgb=inp["rgb"])
    finally:
        setattr(su_spec.Surface, painter, orig)
    ks = [k for k, d in M.secs_sites]
    return e, inp, log, [d for k, d in M.secs_sites], (ks[0] if ks else 1)


def cells_atm_cyclon(rec, cx):
    """The overlay cells one atm_cyclon() call touches for a given cx."""
    t = set()
    cr, cy, g = rec["cr"], rec["cy"], rec["g"]
    seq, rnd = rec["a"], rec["rnd"]
    b = 0
    idx = 0
    ri = 0
    while cr > 0:
        a = seq[idx]
        px = d2u16(cx + cr * math.cos(a))
        py = d2u16(cy + cr * math.sin(a))
        py = (py * 360) & M16
        t.add(((py + px) & M16) >> 1)
        px = (px + rnd[ri]) & M16; ri += 1
        t.add(((py + px) & M16) >> 1)
        py = (py + 359) & M16
        t.add(((py + px) & M16) >> 1)
        px = (px - rnd[ri]) & M16; ri += 1
        t.add(((py + px) & M16) >> 1)
        py = (py + 361) & M16
        t.add(((py + px) & M16) >> 1)
        px = (px + rnd[ri]) & M16; ri += 1
        t.add(((py + px) & M16) >> 1)
        b = (b + 1) % g
        if not b:
            cr -= 1
        idx += 1
    return t


def cells_storm(rec, cx):
    """storm(): concentric rings of cirrus, g = 1 .. cr-1."""
    t = set()
    cr, cy = rec["cr"], rec["cy"]
    for g in range(1, cr):
        for a in su_spec.ASEQ4:
            px = d2u16(cx + g * math.cos(a))
            py = d2u16(cy + g * math.sin(a))
            py = (py * 360) & M16
            t.add(((py + px) & M16) >> 1)
    return t


def feasible(log, cells, nonzero):
    return [set(cx for cx in range(360) if cells(rec, cx) <= nonzero)
            for rec in log]


def solve(feas, D, limit=2 ** 31):
    """All S in [0, limit) satisfying every uniquely-determined equation."""
    uniq = [(i, D[i], next(iter(feas[i])))
            for i in range(len(feas)) if len(feas[i]) == 1]
    if not uniq:
        return [], uniq
    i0, D0, c0 = uniq[0]
    rest = uniq[1:]
    sols = []
    m = 0
    while True:
        base = D0 * (c0 + 360 * m)
        if base >= limit:
            break
        for S in range(base, min(base + D0, limit)):
            if all((S // d) % 360 == c for _, d, c in rest):
                sols.append(S)
        m += 1
    return sols, uniq


def report(tag, painter, cells, plwp=0):
    e, inp, log, D, k = harvest(tag, painter, plwp)
    ovl = open(os.path.join(OUT, tag + ".objectschart"), "rb").read()[:32400]
    nz = set(int(i) for i in np.nonzero(np.frombuffer(ovl, dtype=np.uint8))[0])
    feas = feasible(log, cells, nz)
    empty = [i for i, f in enumerate(feas) if not f]
    sols, uniq = solve(feas, D)
    return dict(tag=tag, k=k, n_painters=len(log), n_unique=len(uniq),
                n_empty=len(empty), empty=empty, solutions=sols[:16],
                n_solutions=len(sols), divisors=D)


if __name__ == "__main__":
    jobs = [("lane_b03_t3", "atm_cyclon", cells_atm_cyclon, 102),
            ("lane_b00_t2", "storm", cells_storm, 99),
            ("jrot_b00_t6", "storm", cells_storm, 0)]
    res = {}
    for tag, painter, cells, plwp in jobs:
        r = report(tag, painter, cells, plwp)
        res[tag] = r
        print("%-14s k=%-3d painters=%-3d unique=%-3d empty=%-2d "
              "solutions=%d %s" % (r["tag"], r["k"], r["n_painters"],
                                   r["n_unique"], r["n_empty"],
                                   r["n_solutions"], r["solutions"][:4]))
    json.dump(res, open(os.path.join(HERE, "su_solve.json"), "w"), indent=1)
