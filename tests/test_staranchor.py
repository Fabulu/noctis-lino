"""GUARDS: the three anchor stars - the only part of Tier 2 that owes nothing
to STARMAP.BIN or to any player.

Alessandro Ghignola hard-coded three identities into his own NOCTIS-1.CPP so
the game could recognise particular stars:

    (long)(nearstar_identity * 1E6) == -37828        Balastrackonastreya
    (long)(nearstar_identity * 1E5) == 1599551984    Fenia
    (long)(nearstar_identity * 1E8) == -11543634     Ylastravenia

work/starmap_find.txt claims one sector for each and checks it before the
catalogue is even opened. This test re-derives the whole chain:

  1  the three conditions are READ OUT OF NOCTIS-1.CPP, not restated here, so
     a wrong constant cannot survive by being wrong in both places;
  2  the 18 hex limbs of the abnd table in work/starmap_find.txt are decoded
     and required to be EXACTLY the 96-bit intervals those conditions imply;
  3  the asec table is required to be the sectors this suite names;
  4  each of those sectors, hashed by the referee, lands inside its interval;
  5  brute force over 1,030,301 sectors finds EXACTLY ONE sector for each
     condition - the one the file claims. Three constants written for a
     different purpose twenty years ago, each satisfied by a unique sector of
     a galaxy this port regenerates from scratch, is the part of Tier 2 that
     no amount of catalogue statistics can substitute for;
  6  under the unsigned fold - the same code, one instruction different - NO
     sector in that box satisfies ANY of the three. The anchors are not a
     property of the shape of the arithmetic; they are a property of this
     galaxy.

NEGATIVE CONTROL: a second copy of the programme is built with one limb of the
abnd table moved so Balastrackonastreya's window no longer contains its P. It
must report anchors = 6 instead of 7. Without that leg, "anchors = 7" could be
a constant the programme prints regardless.

HOW IT FAILS: a change to the fold, to the identity, or to the sector
convention moves P and the brute force stops finding the claimed sector. A
change to abnd fails against the C source's own constants.

RUN: python tests/test_staranchor.py     (~30s; the brute force is 12s of it)
"""

import os
import re
import sys

import linoharness as L
import starmapdrive as D
import starmapspec as S

NOCTIS1 = r"C:\programmieren\noctis\niv-plus\source\NOCTIS-1.CPP"
FIND = os.path.join(L.WORK, "starmap_find.txt")

BOX = 50            # sectors -50..50 on each axis; Fenia is at 43,-46,-8

COND = re.compile(r"\(long\)\s*\(\s*nearstar_identity\s*\*\s*1E(\d+)\s*\)\s*==\s*(-?\d+)L?")


def interval(scale, want):
    """The exact P interval for (long)(P/1e15 * scale) == want.

    The C cast truncates toward zero, so for want < 0 the interval sits on the
    other side of the multiple. Both ends inclusive, which is how the port
    compares them.
    """
    step = S.SCALE // scale
    if want >= 0:
        return want * step, want * step + step - 1
    return want * step - step + 1, want * step


def strip_comments(text):
    """Lino comments are ( ... ) and the anchor tables have one per line."""
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r"\([^()]*\)", " ", text)
    return text


def _table(text, name, head, cont, conv, count):
    """Read a `name = V; no label = V; ...` table, stopping at the first entry
    that is not another `no label` - so a table that shrinks is caught rather
    than silently padded from whatever follows it."""
    m = re.search(re.escape(name) + head, text)
    if not m:
        return []
    vals = [conv(m)]
    pos = m.end()
    while len(vals) < count:
        mm = re.compile(cont).match(text, pos)
        if not mm:
            break
        vals.append(conv(mm))
        pos = mm.end()
    return vals


def limbs_of(text, name, count):
    """The `name = Xh; no label = Yh; ...` form, hex."""
    return _table(text, name, r"\s*=\s*([0-9A-Fa-f]+)h\s*;",
                  r"\s*no label\s*=\s*([0-9A-Fa-f]+)h\s*;",
                  lambda m: int(m.group(1), 16), count)


def signed_of(text, name, count):
    """The same shape, decimal, with lino's `minus N` for negatives."""
    return _table(text, name, r"\s*=\s*(minus\s+)?(\d+)\s*;",
                  r"\s*no label\s*=\s*(minus\s+)?(\d+)\s*;",
                  lambda m: (-1 if m.group(1) else 1) * int(m.group(2)), count)


def main():
    c = L.Check("test_staranchor - three of the author's own constants")

    # ------------------------------------------------ 1. the conditions, from C
    if not c.ok(os.path.exists(NOCTIS1) and os.path.exists(S.CATALOGUE),
                "the niv-plus reference clone is present", NOCTIS1):
        return c.done()
    cpp = open(NOCTIS1, "r", encoding="latin-1").read()
    found = [(10 ** int(e), int(v)) for e, v in COND.findall(cpp)]
    c.eq(len(found), 3, "NOCTIS-1.CPP carries exactly three identity constants")
    c.eq(found, [(sc, wa) for (_n, _s, sc, wa) in S.ANCHORS],
         "...and they are the three this suite names, scale and value")

    want_bounds = [interval(sc, wa) for (sc, wa) in found]
    for (name, sect, sc, wa), (lo, hi) in zip(S.ANCHORS, want_bounds):
        c.note("%-20s (long)(id*1E%d)==%d  ->  P in [%d, %d]"
               % (name, len(str(sc)) - 1, wa, lo, hi))

    # ------------------------------------------------ 2. the abnd table
    src = strip_comments(open(FIND, "r", encoding="utf-8", errors="replace").read())
    limbs = limbs_of(src, "abnd", 18)
    c.eq(len(limbs), 18, "abnd is 18 hex limbs - six 96-bit bounds")
    if len(limbs) == 18:
        got = [S.s96(limbs[3 * i] | (limbs[3 * i + 1] << 32) | (limbs[3 * i + 2] << 64))
               for i in range(6)]
        flat = [b for pair in want_bounds for b in pair]
        c.eq(got, flat, "every abnd bound is exactly what the C condition implies")

    # ------------------------------------------------ 3. the asec table
    sects = signed_of(src, "asec", 9)
    c.eq([tuple(sects[3 * i:3 * i + 3]) for i in range(3)],
         [a[1] for a in S.ANCHORS], "asec names the three sectors this suite tests")

    # ------------------------------------------------ 4. the referee agrees
    for (name, sect, sc, wa), (lo, hi) in zip(S.ANCHORS, want_bounds):
        tx, ty, tz, _net, flags = S.hash_sector(*[k * S.SECTORSIZE for k in sect])
        P = S.s32(tx) * S.s32(ty) * S.s32(tz)
        c.ok(flags == 0 and lo <= P <= hi,
             "%s: sector %s generates a live star inside its window" % (name, sect),
             "P=%d" % P)

    # ------------------------------------------------ 5/6. brute force, both folds
    c.note("sweeping %d sectors under both folds..." % ((2 * BOX + 1) ** 3))
    sfound = [[] for _ in range(3)]
    ufound = [[] for _ in range(3)]
    for ix in range(-BOX, BOX + 1):
        sx = ix * S.SECTORSIZE
        for iy in range(-BOX, BOX + 1):
            sy = iy * S.SECTORSIZE
            for iz in range(-BOX, BOX + 1):
                sz = iz * S.SECTORSIZE
                for fold, bucket in ((None, sfound), (S.fold_unsigned, ufound)):
                    tx, ty, tz, _n, fl = (S.hash_sector(sx, sy, sz) if fold is None
                                          else S.hash_sector(sx, sy, sz, fold=fold))
                    if fl:
                        continue
                    P = S.s32(tx) * S.s32(ty) * S.s32(tz)
                    for k, (lo, hi) in enumerate(want_bounds):
                        if lo <= P <= hi:
                            bucket[k].append((ix, iy, iz))

    for k, (name, sect, _sc, _wa) in enumerate(S.ANCHORS):
        c.eq(sfound[k], [tuple(sect)],
             "%s is the UNIQUE sector satisfying its condition in the box" % name)
        c.eq(ufound[k], [],
             "...and the unsigned-fold galaxy puts nothing in that window at all")

    # ------------------------------------------------ 7. through the binary
    f = D.Find(stem="tsanc", sbox_name="tsanc")
    ok, msg = f.build()
    if not c.ok(ok, "starmap_find builds", msg):
        return c.done()
    f.real_catalogue()

    h, _hits, failed, msg = f.run(0, 0, timeout=120)
    if c.ok(h is not None and not failed, "K=0 run (the anchors precede the sweep)", msg):
        c.eq(h["anchors"], 7, "the programme passes all three anchors")
    h, _hits, failed, msg = f.run(0, D.MODE_UNSIGNED, timeout=120)
    if c.ok(h is not None and not failed, "K=0 unsigned-fold run", msg):
        c.eq(h["anchors"], 0, "and none of them under the unsigned fold")

    # ------------------------------------------------ 8. negative control
    # Move Balastrackonastreya's LOW bound up onto its high bound: P is below
    # it, so anchor 0 must now fail while the other two still pass.
    m = D.Find(stem="tsancm", sbox_name="tsancm")
    text = open(m.src, "r", encoding="utf-8").read()
    lo0 = "%08X" % limbs[0]
    hi0 = "%08X" % limbs[3]
    mutated, n = re.subn(r"abnd(\s*)=(\s*)%sh;" % lo0,
                         lambda mo: "abnd%s=%s%sh;" % (mo.group(1), mo.group(2), hi0),
                         text, flags=re.I)
    c.eq(n, 1, "negative control: abnd's first limb moved onto the upper bound")
    open(m.src, "w", encoding="utf-8").write(mutated)
    ok, msg = m.build()
    if c.ok(ok, "the mutant builds", msg):
        m.real_catalogue()
        h, _hits, failed, msg = m.run(0, 0, timeout=120)
        if c.ok(h is not None and not failed, "the mutant runs", msg):
            c.eq(h["anchors"], 6,
                 "anchors = 6, not 7 - the bits are computed from abnd, not "
                 "printed regardless")

    return c.done()


if __name__ == "__main__":
    sys.exit(main())
