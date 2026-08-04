"""GUARDS: the acceptance test in work/starmap_find.txt is exactly
|P - N| < 1e10, and the outward scan around the insertion point finds every
key inside that window and nothing outside it.

Everything Tier 2 reports is a count of things that passed this one
inequality, so it is worth pinning to the last unit rather than inferring from
a rate. The catalogue is not used as evidence here - it is used as a probe.
Each run installs a STARMAP.BIN of the correct length whose only 'S' records
are keys this test placed at chosen distances from the single star the K=0
sweep generates, so the expected answer is known exactly before the programme
runs.

  1  BOUNDARY. Keys at |P - N| = 0, 1e10-1, 1e10 and 1e10+1, on both sides.
     The first two must match and the last two must not, and the |P - N| the
     programme records must be the offset that was planted.
  2  SCAN. Forty-five keys in deliberately unsorted file order, some inside one
     window (including exact duplicates, which is how a permutation collision
     presents), some outside. Exactly the inside ones must come back, with
     unsorted = 0 - the programme's own check that its Shellsort worked.
  3  HIT CAP. With cap = 1 and three keys in the window, the overflow flag
     must be set and exactly one hit recorded, so an overflowing run can never
     be mistaken for a small one.

NEGATIVE CONTROL: a second copy is built with WinTest's `'>=` changed to `'>`,
which makes the window inclusive and nothing else. It must return 5 boundary
hits where the real programme returns 3. An off-by-one at the window edge is
the most plausible silent regression here and this is the leg that catches it.

HOW IT FAILS: a widened or narrowed window changes which boundary keys come
back; a scan that stops at the insertion point loses the duplicates; a broken
sort shows up as unsorted != 0 and as missing hits.

RUN: python tests/test_starwindow.py     (~25s)
"""

import os
import random
import sys

import linoharness as L
import starmapdrive as D
import starmapspec as S

W = S.WINDOW


def star_at_origin():
    """The one star the K=0 sweep generates, and its exact P."""
    tx, ty, tz, _net, flags = S.hash_sector(0, 0, 0)
    x, y, z = S.s32(tx), S.s32(ty), S.s32(tz)
    return (x, y, z), x * y * z, flags


def plant_keys(f, keys):
    """Install a catalogue whose 'S' records are exactly these N, in order."""
    with open(S.CATALOGUE, "rb") as fh:
        blob = fh.read()
    cat, ords = S.craft_catalogue(blob, keys)
    f.catalogue(cat)
    return ords


def plant(f, base, offsets):
    return plant_keys(f, [base + o for o in offsets])


def main():
    c = L.Check("test_starwindow - the acceptance window and the outward scan")
    if not c.ok(os.path.exists(S.CATALOGUE),
                "the real STARMAP.BIN is present (its bytes are the carrier "
                "for the crafted probes)", S.CATALOGUE):
        return c.done()

    (x, y, z), P, flags = star_at_origin()
    c.eq(flags, 0, "sector (0,0,0) generates a live star")
    c.note("K=0 star: x=%d y=%d z=%d  P=%d" % (x, y, z, P))

    # Every planted key must be exactly representable, or the probe is
    # measuring the double grid rather than the window.
    for delta in (0, W - 1, -(W - 1), W, -W, W + 1, -(W + 1)):
        raw = S.double_for_N(P + delta)
        c.eq(S.decode_exact(raw), (P + delta, 0),
             "a double exists whose trunc(d*1e15) is exactly P%+d" % delta)

    f = D.Find(stem="tswin", sbox_name="tswin")
    ok, msg = f.build()
    if not c.ok(ok, "starmap_find builds", msg):
        return c.done()

    # ------------------------------------------------------------ 1. boundary
    offsets = [0, W - 1, -(W - 1), W, -W, W + 1, -(W + 1)]
    plant(f, P, offsets)
    h, hits, failed, msg = f.run(0, 0, timeout=120)
    if not c.ok(h is not None and not failed, "boundary probe runs", msg):
        return c.done()

    c.eq(h["nkeys"], len(offsets), "all %d planted keys were accepted" % len(offsets))
    want = {i for i, o in enumerate(offsets) if abs(o) < W}
    got = {t[0] for t in hits}
    c.eq(got, want, "matched exactly the keys strictly inside the window")
    c.eq(len(hits), len(want), "one hit per matching key, no duplicates invented")
    gaps = {t[0]: t[5] for t in hits}
    c.eq(gaps, {i: abs(offsets[i]) for i in want},
         "the recorded |P - N| is the planted offset, to the unit")
    for i, o in enumerate(offsets):
        c.ok((i in got) == (abs(o) < W),
             "offset %+d: %s" % (o, "inside" if abs(o) < W else "outside"))

    # ------------------------------------------------------------ 2. the scan
    rnd = random.Random(20260804)          # fixed: the test must be reproducible
    inside = [0, 1, -1, 12345, -12345, W - 1, -(W - 1), W // 2, -(W // 2),
              W - 2, -(W - 2), 7, -7]
    inside += [W // 3, -(W // 3), 999999999, -999999999]
    inside += inside[:8]                   # exact duplicates: distinct records,
    inside += [0, 0]                       # identical keys
    outside = [W, -W, W + 1, -(W + 1), 2 * W, -2 * W, 37 * W, -37 * W,
               10 ** 13, -10 ** 13, 5 * W + 3, -(5 * W + 3)]
    outside += outside[:6]
    mix = inside + outside
    rnd.shuffle(mix)
    plant(f, P, mix)
    h, hits, failed, msg = f.run(0, 0, timeout=120)
    if c.ok(h is not None and not failed, "scan probe runs (%d keys)" % len(mix), msg):
        c.eq(h["nkeys"], len(mix), "every planted key entered the table")
        c.eq(h["unsorted"], 0, "the Shellsort verified itself on unsorted input")
        c.eq(h["overflow"], 0, "no overflow")
        want = {i for i, o in enumerate(mix) if abs(o) < W}
        got = {t[0] for t in hits}
        c.eq(len(hits), len(want), "hit count equals the number of keys inside")
        c.ok(got == want, "the outward scan found every key inside the window "
                          "and nothing outside it",
             "%d missed, %d spurious" % (len(want - got), len(got - want)))
        badgap = [t for t in hits if t[5] != abs(mix[t[0]])]
        c.ok(not badgap, "every recorded gap is the planted offset",
             "%d wrong, first %r" % (len(badgap), badgap[:1]))
        dups = len(mix) - len(set(mix))
        c.ok(dups > 0 and all(i in got for i, o in enumerate(mix)
                              if abs(o) < W and mix.count(o) > 1),
             "duplicate keys are all reported, not collapsed to the first",
             "%d duplicated offsets planted" % dups)

    # ------------------------------------------------------------ 3. the cap
    plant(f, P, [0, 1, -1])
    h, hits, failed, msg = f.run(0, 0, cap=1, timeout=120)
    if c.ok(h is not None and not failed, "hit-cap probe runs", msg):
        c.eq(h["nhits"], 1, "cap = 1 records exactly one hit")
        c.eq(h["overflow"], 1, "...and says so, so a capped run is not read as a small one")

    # ------------------------------------------------- 4. borrows on purpose
    # Gap96 subtracts 96 bits by hand, and its borrow tests must be UNSIGNED
    # compares. A signed one is wrong exactly when the two limbs being
    # compared straddle bit 31 - which a sweep reaches only by luck, and then
    # only in a handful of hits. These offsets straddle it deliberately, in
    # both borrow directions, at gaps still inside the window: a signed
    # compare then either loses the hit or records a |P - N| off by 2^32.
    # Which direction the mistake goes depends on the sign bit of the star's
    # own low limb, so this needs two stars - the K=1 box has both.
    B31 = 1 << 31
    stars1 = S.sweep(1)
    pick = {}
    for s in stars1:
        if abs(s[3]) < 10 ** 15:            # keeps every planted N representable
            pick.setdefault((s[3] & 0xFFFFFFFF) >> 31, s)
    c.eq(sorted(pick), [0, 1],
         "the K=1 box offers a star on each side of bit 31 of its low limb")

    offs = [B31, -B31, B31 + 1, -(B31 + 1), 3 * B31, -3 * B31]
    c.ok(all(abs(o) < W for o in offs), "the planted offsets are inside the window")
    keys, kinds = [], {True: 0, False: 0}
    for _bit, s in sorted(pick.items()):
        t0 = s[3] & 0xFFFFFFFF
        for o in offs:
            if ((t0 ^ ((s[3] + o) & 0xFFFFFFFF)) >> 31):
                kinds[t0 >= (s[3] + o) & 0xFFFFFFFF] += 1
            keys.append(s[3] + o)
    c.ok(kinds[True] and kinds[False],
         "...and they straddle bit 31 in BOTH borrow directions",
         "%d spurious-borrow, %d missing-borrow" % (kinds[True], kinds[False]))

    plant_keys(f, keys)
    h, hits, failed, msg = f.run(1, 0, timeout=120)
    if c.ok(h is not None and not failed, "borrow probe runs", msg):
        want = {(r, x, y, z, PP, abs(PP - N)) for (r, x, y, z, PP, N)
                in S.match(stars1, sorted((n, i) for i, n in enumerate(keys)))}
        c.ok(want == set(hits),
             "every straddling key is found with an exact |P - N| - the "
             "borrows are unsigned compares",
             "%d referee, %d lino, %d referee-only, %d lino-only"
             % (len(want), len(hits), len(want - set(hits)), len(set(hits) - want)))

    # ------------------------------------------- 5. negative control: off by one
    m = D.Find(stem="tswinm", sbox_name="tswinm")
    text = open(m.src, "r", encoding="utf-8").read()
    mutated = text.replace("? A '>= WIN0 -> wintest done;", "? A '> WIN0 -> wintest done;")
    c.ok(mutated != text, "negative control: WinTest's window made inclusive")
    open(m.src, "w", encoding="utf-8").write(mutated)
    ok, msg = m.build()
    if c.ok(ok, "the mutant builds", msg):
        plant(m, P, offsets)
        h, hits, failed, msg = m.run(0, 0, timeout=120)
        if c.ok(h is not None and not failed, "the mutant runs", msg):
            got = {t[0] for t in hits}
            c.eq(got, {i for i, o in enumerate(offsets) if abs(o) <= W},
                 "the mutant admits |P-N| = 1e10 exactly - so this probe can "
                 "see a one-unit change in the window")

    return c.done()


if __name__ == "__main__":
    sys.exit(main())
