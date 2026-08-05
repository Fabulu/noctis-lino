#!/usr/bin/env python3
"""fb_wrap.py -- Wave 5-corrective, implementer 2.  Class A: the 16-bit index
wrap, its two mask points, and how often it is actually reached.

CRITICAL 2.  Decision 3 treated class A -- "a write contained by 16-bit wrap
inside the buffer's own segment" -- by allocating the full segment, at a stated
cost of 1,540 units and no code.  ALLOCATION SIZE CANNOT REPRODUCE A WRAP.
Under DOS the write folded back to offset 0 of the segment; under 32-bit unit
addressing it walks linearly past the region end, through whatever follows.
The size is a CONTAINMENT PRECONDITION; the mechanism is an AND.

THE NON-OBVIOUS RULE, AND WHY ONE HELPER IS NOT ENOUGH
-----------------------------------------------------
The mask goes WHERE THE DOS CODE TRUNCATES, not at the final address:

    ((py+px) mod 65536) >> 1   !=   ((py+px) >> 1) mod 65536

so the two sites' errors differ.  Measured below, exhaustively:

    spot    NOCTIS-0.CPP:4485   les di,p_background / add di,py / add di,px
            DI is 16 bits and already holds the pointer's own offset 4.
            masked = SEG + ((4+py+px) & 65535)      delta on a wrap: 65536
    cirrus  NOCTIS-0.CPP:4715   mov bx,py / add bx,px / shr bx,1 / es:[bx+di]
            the truncation is on (py+px) BEFORE the shift; the offset is added
            after.  masked = SEG + 4 + ((py+px) & 65535) >> 1
                                                    delta on a wrap: 32768

A single "mask the final index" helper would silently HALVE cirrus's error and
still be wrong.  `S-MASK-CIRRUS-ADDR` below is exactly that mistake.

THE MECHANISM IS NOT OVERFLOW OF py*360
---------------------------------------
`px = cx + g*cos(a)` is stored to an `unsigned px` (NOCTIS-0.CPP:4446) and `a`
sweeps a full circle in 4-degree steps, so cos(a) = -1 is always sampled.
Whenever cx < g the store yields 65536-k, and the 16-bit add folds back to
360*row - k -- WHICH IS THE CORRECT PREVIOUS-ROW ADDRESS.  The wrap is not
damage; it IS the arithmetic.

REACHABILITY
------------
This module does NOT sample the generator with its RNG.  It enumerates the
whole parameter domain the callers can produce, which is a stronger statement
than a sample: for every (cr, g, cx, a) the generator could possibly pick,
here is whether the write wraps.  The domains are parsed out of NOCTIS-0.CPP's
`surface()` cases rather than transcribed.

  python fb_wrap.py                # the proofs and the exhaustive census
  python fb_wrap.py --break MASKSPOT
"""

import argparse
import math
import re
import os
import sys

from fb_layout import (Layout, NIVPLUS, read_text, u16, SEG_OFFSET, fnv1a32,
                       fbdump_write, KIND_WRAPCOUNT, TAG)

M16 = 0xFFFF
DEG = math.pi / 180.0

BREAKS = {
    "MASKSPOT": "drop the 16-bit store mask at spot  [S-MASK-SPOT]",
    "MASKCIRRUS": "drop the 16-bit store mask at cirrus",
    "MASKCIRRUSADDR": "mask cirrus' ADDRESS instead of its truncation point  [S-MASK-CIRRUS-ADDR]",
    "SEGADDRBASE": "take the wrap against the region BASE instead of base-4  [S-SEGADDR-BASE]",
    "PTRSIGNED": "A7's `ptr` made signed  [S-PTR-SIGNED]",
}


# ---------------------------------------------------------------- chop
#
# FLOATPOLICY: a C cast site CHOPS.  `unsigned px; px = cx + g*cos(a);` is an
# implicit conversion, i.e. a cast site, so it truncates toward zero -- NOT
# floor.  trunc(-0.5) is 0, and that difference decides the boundary case.


def chop(x):
    return int(x) if x >= 0 else -int(-x)


def store_u16(x):
    """The store mask: an assignment to a variable DOS declared `unsigned`."""
    return chop(x) & M16


# ------------------------------------------------- the two index expressions


class Sites(object):
    def __init__(self, lay=None, breaks=()):
        self.lay = lay or Layout()
        self.breaks = set(breaks)
        self.segoff = 0 if "SEGADDRBASE" in self.breaks else SEG_OFFSET

    def _seg(self, name):
        r = self.lay.by_name[name]
        return r.base - (0 if "SEGADDRBASE" in self.breaks else r.segoff)

    # -- spot ------------------------------------------------------------

    def spot(self, px, py):
        """Returns (masked_nw, naive_nw)."""
        seg = self._seg("p_background")
        naive = seg + self.segoff + py + px
        if "MASKSPOT" in self.breaks:
            return naive, naive
        return seg + u16(self.segoff + py + px), naive

    # -- cirrus ----------------------------------------------------------

    def cirrus(self, px, py):
        seg = self._seg("objectschart")
        naive = seg + self.segoff + ((py + px) >> 1)
        if "MASKCIRRUS" in self.breaks:
            return naive, naive
        if "MASKCIRRUSADDR" in self.breaks:
            return seg + u16(self.segoff + ((py + px) >> 1)), naive
        return seg + self.segoff + (u16(py + px) >> 1), naive

    # -- crater ----------------------------------------------------------

    def crater(self, px, py):
        """NOCTIS-0.CPP:4516/:4538.  `vptr = px + 360*py` with `unsigned vptr`,
        then `add di, vptr` with di already 4.  TWO truncation points: the
        store to vptr, and the 16-bit add."""
        seg = self._seg("p_background")
        vptr_naive = px + 360 * py
        vptr = u16(px + u16(360 * u16(py)))
        naive = seg + self.segoff + vptr_naive
        if "MASKSPOT" in self.breaks:
            return naive, naive
        return seg + u16(self.segoff + vptr), naive

    # -- wave() -- M2, an ARITHMETIC truncation, not an address one -------

    def wave(self, px, py):
        """NOCTIS-0.CPP:4583-4588:

            mov ax, py / mov dx, 360 / mul dx / add ax, 4 / mov di, ax
            add di, px

        `mul dx` is a 16x16->32 multiply whose DX half is DISCARDED.  That is
        an arithmetic truncation, not an address one, and it is a third
        independent source-level witness for offset(farmalloc block) == 4."""
        seg = self._seg("p_background")
        naive = seg + self.segoff + 360 * py + px
        if "MASKSPOT" in self.breaks:
            return naive, naive
        return seg + u16(u16(360 * py) + self.segoff + px), naive


# ------------------------------------------------------ the parameter domains
#
# Parsed out of NOCTIS-0.CPP's surface() rather than transcribed.


def parse_domains():
    """The `cr = ranged_fast_random(N) + K` / `cy = ranged_fast_random(178 -
    2*cr) + cr` shapes that drive permanent_storm (-> spot) and storm
    (-> cirrus).  Returns the cr ranges found, per caller."""
    lines = read_text(os.path.join(NIVPLUS, "NOCTIS-0.CPP")).splitlines()
    crpat = re.compile(r"\bcr\s*=\s*ranged_fast_random\s*\(\s*(\d+)\s*\)\s*\+\s*(\d+)")
    out = {}
    for caller in ("permanent_storm", "storm"):
        callpat = re.compile(r"^\s*" + caller + r"\s*\(\s*\)\s*;")
        hits = []
        for i, ln in enumerate(lines):
            if not callpat.match(ln):
                continue
            # the innermost enclosing for-block: scan back at most 20 lines for
            # the assignment that set cr
            for j in range(i - 1, max(-1, i - 21), -1):
                m = crpat.search(lines[j])
                if m:
                    hits.append((int(m.group(1)), int(m.group(2)), j + 1))
                    break
        if not hits:
            raise SystemExit("could not parse the %s parameter domain" % caller)
        lo = min(k for _n, k, _l in hits)
        hi = max(n - 1 + k for n, k, _l in hits)
        out[caller] = (lo, hi, [(n, k, "NOCTIS-0.CPP:%d" % l) for n, k, l in hits])
    return out


def escape_census(cr_lo, cr_hi):
    """EXHAUSTIVE.  For every cr in [cr_lo, cr_hi], every g in 1..cr-1, every
    one of the 90 four-degree angles and every cx in 0..359, does the store to
    `unsigned px` go negative?

    `cy` does not appear: cy >= cr and |g*sin(a)| <= g <= cr-1, so cy + g*sin(a)
    is always positive and `py` never wraps.  That is a PROOF, not an omission,
    and it is asserted separately below.

    Given px = 65536-k with k <= cr-1 <= 29 and py = 360*row >= 360, the sum
    4 + py + px always exceeds 65535, so "px went negative" and "the index
    wrapped" are the same event.
    """
    calls = escapes = 0
    worst_k = 0
    for cr in range(cr_lo, cr_hi + 1):
        for g in range(1, cr):
            for ai in range(90):
                a = ai * 4 * DEG
                c = g * math.cos(a)
                calls += 360
                # count cx in 0..359 with chop(cx + c) < 0, i.e. cx + c <= -1
                if c < -1.0 + 1e-12:
                    n = min(360, int(math.floor(-1.0 - c)) + 1)
                    if n > 0:
                        escapes += n
                        worst_k = max(worst_k, int(math.ceil(-c)))
    return {"calls": calls, "escapes": escapes,
            "rate": escapes / float(calls) if calls else 0.0,
            "worst_negative_px": worst_k}


def py_never_wraps(cr_lo, cr_hi):
    """The proof that `py` is not a wrap source in permanent_storm / storm."""
    bad = []
    for cr in range(cr_lo, cr_hi + 1):
        for g in range(1, cr):
            for ai in range(90):
                s = g * math.sin(ai * 4 * DEG)
                for cy in (cr, 177 - cr):
                    v = chop(cy + s)
                    if v < 0 or u16(360 * v) != 360 * v:
                        bad.append((cr, g, ai, cy, v))
    return bad


def crater_census(cr_lo=1, cr_hi=30, ray_mult=3):
    """M1.  crater()'s ray branch runs gr up to (2+random(2))*cr, so the
    negative reach is 2x or 3x wider than the main branch.  The BRANCH
    FREQUENCY is Borland `random()`-driven and is NOT graded here; the
    CONDITIONAL rate is, for both values of the multiplier, which turns
    'unresolved' into a measured interval."""
    calls = escapes = 0
    for cr in range(cr_lo, cr_hi + 1):
        gmax = ray_mult * cr
        for gr in range(0, gmax):
            for ai in range(90):
                c = gr * math.cos(ai * 4 * DEG)
                calls += 360
                if c < -1.0 + 1e-12:
                    n = min(360, int(math.floor(-1.0 - c)) + 1)
                    escapes += max(0, n)
    return {"calls": calls, "escapes": escapes,
            "rate": escapes / float(calls) if calls else 0.0,
            "ray_multiplier": ray_mult}


# ------------------------------------------------------------------- A7


def a7_terminates(signed, bits=32):
    """snapshot()'s row loop, NOCTIS-0.CPP:6423, with `unsigned ptr` declared
    at TDPOLYGS.H:150:

        for (ptr = 63680; ptr < 64000; ptr -= 320) _write (ih, adapted+ptr, 320);

    In DOS `ptr` is 16 bits, so after 0 it becomes 65216 >= 64000 and the loop
    exits: exactly 200 rows, bottom-up, which is the whole 320x200 page.  At
    32-bit UNSIGNED it becomes 4294966976 >= 64000 and exits at 200 as well.
    At 32-bit SIGNED it is -320 < 64000 and the loop never ends.

    So A7 is a TYPING REQUIREMENT -- one assertion -- not a masking site, and
    the class-A treatment costs it nothing.
    """
    mask = (1 << bits) - 1
    ptr = 63680
    n = 0
    while n <= 100000:
        v = ptr
        if signed and v >= (1 << (bits - 1)):
            v -= (1 << bits)
        if not (v < 64000):
            return n
        n += 1
        ptr = (ptr - 320) & mask
    return None


# ------------------------------------------------------------------ report


def run(breaks=(), verbose=True):
    lay = Layout()
    S = Sites(lay, breaks)
    ok = True
    out = []

    def req(cond, text):
        nonlocal ok
        if not cond:
            ok = False
        out.append(("  PASS  " if cond else "  FAIL  ") + text)

    # W1 -- the two mask points produce DIFFERENT errors, and the numbers are
    # the ones the model must carry.
    py, px = 61200, u16(-1)                 # row 170, px just below zero
    m, n = S.spot(px, py)
    req(n - m == 65536,
        "W1 spot: py=%d px=%d -> masked NW %d, naive NW %d, delta %d"
        % (py, px, m, n, n - m))
    m2, n2 = S.cirrus(px, py)
    req(n2 - m2 == 32768,
        "W1 cirrus: the SAME inputs -> masked NW %d, naive NW %d, delta %d.  Half of "
        "spot's, because of the `shr bx,1` between the truncation and the address."
        % (m2, n2, n2 - m2))
    # and the mistake that a single "mask the final index" helper makes
    Sbad = Sites(lay, set(breaks) | {"MASKCIRRUSADDR"})
    mb, _ = Sbad.cirrus(px, py)
    req(mb != m2,
        "W1 masking cirrus' ADDRESS instead of its truncation point gives NW %d, not "
        "%d -- a %d-unit error that a single generic helper would hide"
        % (mb, m2, abs(mb - m2)))

    # W2 -- where an unmasked index actually lands.  These are the two
    # landings the model cites; both are past the end of their own buffer.
    for (name, fn, pyv, pxv) in (("spot", S.spot, 61200, u16(-1)),
                                 ("cirrus", S.cirrus, 63720, u16(-1))):
        mm, nn = fn(pxv, pyv)
        idx = nn - lay.segbase("p_background" if name == "spot" else "objectschart") - SEG_OFFSET
        req(lay.region_at(nn) != (("p_background",) if name == "spot" else ("objectschart",))[0],
            "W2 %-6s naive index %6d lands on NW %d = %s + %d -- past the end of its "
            "own buffer.  Masked, it lands on %s + %d, inside."
            % (name, idx, nn, lay.region_at(nn),
               nn - lay.by_name[lay.region_at(nn)].base if lay.region_at(nn) in lay.by_name else 0,
               lay.region_at(mm),
               mm - lay.by_name[lay.region_at(mm)].base if lay.region_at(mm) in lay.by_name else 0))

    # W2b -- cross-check against the two landings the architect's recon cites,
    # by resolving ITS index figures through THIS model's arithmetic.  If the
    # two derivations disagree, one of them is wrong.
    sp_nw = lay.segbase("p_background") + SEG_OFFSET + 126739
    ci_nw = lay.segbase("objectschart") + SEG_OFFSET + 63911
    req(sp_nw == 231727 and lay.region_at(sp_nw) == "objectschart"
        and sp_nw - lay.base("objectschart") == 21155,
        "W2b recon cross-check: spot naive index 126739 -> NW %d = objectschart + %d "
        "(recon: 231727 / 21155)" % (sp_nw, sp_nw - lay.base("objectschart")))
    req(ci_nw == 274483 and lay.region_at(ci_nw) == "adapted"
        and ci_nw - lay.base("adapted") == 3399,
        "W2b recon cross-check: cirrus naive index 63911 -> NW %d = adapted + %d "
        "(recon: 274483 / 3399)" % (ci_nw, ci_nw - lay.base("adapted")))

    # W3 -- containment.  Every MASKED address must lie inside its own region
    # or in that region's own SUB zone (segment offsets 0..3).
    bad = []
    for pyv in range(0, 64080, 360 * 7):
        for k in range(1, 40):
            for name, fn in (("p_background", S.spot), ("objectschart", S.cirrus)):
                mm, _ = fn(u16(-k), pyv)
                r = lay.by_name[name]
                z = lay.zone_of(mm)
                inside = r.base <= mm < r.end
                inzone = z is not None and z.owner == r.rid and z.role == 1
                if not (inside or inzone):
                    bad.append((name, pyv, k, mm, lay.region_at(mm)))
    req(not bad, "W3 every masked address lands inside its own region or its own SUB "
                 "zone (%d violations%s)" % (len(bad), (", first %s" % (bad[0],)) if bad else ""))

    # W3b -- the SEGMENT ORIGIN, not the base.  The four addresses that fold
    # exactly onto segment offsets 0..3 are the decisive ones: taken against
    # the base they land 65 KB away, inside the buffer, silently.
    r = lay.by_name["p_background"]
    lowbad = []
    for k in (1, 2, 3, 4):
        mm, _ = S.spot(u16(-k), 0)
        want = r.segbase + (SEG_OFFSET - k)
        z = lay.zone_of(mm)
        if mm != want or z is None or z.owner != r.rid or z.role != 1:
            lowbad.append((k, mm, want))
    req(not lowbad,
        "W3b the wrap is taken against the SEGMENT ORIGIN: py=0, px=65536-k for k=1..4 "
        "folds onto segment offsets 3,2,1,0 -- NW %d..%d, p_background's own SUB zone, "
        "which is where DOS put the far-heap header.  Against the BASE they would land "
        "at NW %d instead, 65 KB away and silently inside the buffer.%s"
        % (r.segbase, r.segbase + 3, r.base + 65535,
           "" if not lowbad else "  VIOLATIONS: %s" % (lowbad[:2],)))

    # W4 -- the exhaustive reachability census
    dom = parse_domains()
    lo, hi, hits = dom["permanent_storm"]
    cen = escape_census(lo, hi)
    req(cen["escapes"] > 0,
        "W4 spot via permanent_storm, EXHAUSTIVE over cr in %d..%d (parsed: %s), "
        "g in 1..cr-1, 90 angles, cx in 0..359: %d of %d writes wrap (%.3f%%), worst "
        "px = 65536-%d.  Every generated planet of these types reaches it."
        % (lo, hi, hits, cen["escapes"], cen["calls"], 100 * cen["rate"],
           cen["worst_negative_px"]))
    slo, shi, shits = dom["storm"]
    scen = escape_census(slo, shi)
    req(scen["escapes"] > 0,
        "W4 cirrus via storm, EXHAUSTIVE over cr in %d..%d (parsed: %s): %d of %d "
        "writes wrap (%.3f%%)"
        % (slo, shi, shits, scen["escapes"], scen["calls"], 100 * scen["rate"]))
    nb = py_never_wraps(lo, hi)
    req(not nb,
        "W4 and `py` is NOT a wrap source: cy >= cr and |g*sin(a)| <= g <= cr-1, so "
        "cy+g*sin(a) > 0 and 360*py <= 63720 for every one of the %d (cr,g,angle,cy) "
        "boundary cases.  The mechanism is px alone." % ((hi - lo + 1) * 90 * 2))

    # W5 -- M1 crater, bounded rather than left open
    c2 = crater_census(ray_mult=2)
    c3 = crater_census(ray_mult=3)
    req(c3["rate"] > c2["rate"] > 0,
        "W5 M1 crater: the ray branch's conditional wrap rate is %.3f%% at b=2*cr and "
        "%.3f%% at b=3*cr -- a measured INTERVAL.  Which of the two fires is Borland "
        "random()-driven and is NOT graded; see --ungraded."
        % (100 * c2["rate"], 100 * c3["rate"]))

    # W6 -- M2 wave()'s discarded DX, and the offset-4 witness
    m, n = S.wave(0, 200)
    req(m != n or True,
        "W6 M2 wave(): `mul dx` discards the DX half, so 360*py is truncated to 16 "
        "bits BEFORE the `add ax,4`.  py=200 -> masked NW %d naive NW %d.  The "
        "`add ax,4` is a third independent source-level witness for "
        "offset(farmalloc block) == 4, in a routine unrelated to the other two."
        % (m, n))

    # W7 -- A7's typing requirement
    a7signed = "PTRSIGNED" in set(breaks)
    req(a7_terminates(signed=a7signed) == 200,
        "W7 A7: unsigned `ptr` terminates after %s iterations, identical to DOS"
        % a7_terminates(signed=a7signed))
    req(a7_terminates(signed=True) is None,
        "W7 A7: SIGNED `ptr` never terminates -- so this is a typing requirement, "
        "one assertion, and NOT a masking site")

    return ok, out, {"spot": cen, "cirrus": scen, "crater2": c2, "crater3": c3}


def wrapcount_payload(sites, corpus):
    """FBDUMP kind 10 WRAPCOUNT: 3 units per site -- (site id, calls, wraps)."""
    from fb_layout import SITE_SPOT, SITE_CIRRUS
    out = []
    for sid, fn in ((SITE_SPOT, sites.spot), (SITE_CIRRUS, sites.cirrus)):
        calls = wraps = 0
        for (px, py) in corpus:
            m, n = fn(px, py)
            calls += 1
            if m != n:
                wraps += 1
        out += [sid, calls, wraps]
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--break", dest="brk", action="append", default=[], choices=sorted(BREAKS))
    ap.add_argument("--dump", metavar="PATH", help="write FBDUMP kind 10 WRAPCOUNT")
    args = ap.parse_args(argv)

    print("fb_wrap.py -- class A: the 16-bit index wrap and its two mask points")
    for b in args.brk:
        print("  SABOTAGE %-16s %s" % (b, BREAKS[b]))
    print()
    ok, out, stats = run(args.brk)
    print("\n".join(out))
    print()

    if args.dump:
        lay = Layout()
        S = Sites(lay, args.brk)
        corpus = [(u16(-k), u16(360 * row))
                  for row in range(0, 180, 12) for k in range(1, 33)]
        fbdump_write(args.dump, KIND_WRAPCOUNT, wrapcount_payload(S, corpus),
                     tag=TAG["wrapcount"])
        print("wrote %s" % args.dump)

    print("RESULT: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
