"""GUARDS: work/starmap_find.txt still matches generated stars against the real
STARMAP.BIN the way it did when the Tier 2 result was measured.

The claim this protects is the headline of the track: sweeping sectors with
Noctis's own hash and looking each star's identity up in twenty years of
player-charted names produces a large, exact set of hits. The test does not
grade against a stored number. It rebuilds the programme, runs it, and demands
that its hit set equal - record ordinal, x, y, z, the 96-bit product P and the
recorded |P - N| gap, every field of every hit - the set computed by
starmapspec.py, which is written against the DOS sources with Python bignums
and Fractions and shares no arithmetic with the L.in.oleum side.

Also pinned, because set equality alone cannot see them:

  * THE FOLD IS SIGNED. The same binary is re-run with mode bit 1, which
    switches FoldMul to the unsigned *%'. It must produce a DIFFERENT hit set,
    and one the referee predicts exactly. Without that leg, "the two agree"
    would also be true of a test that cannot tell signed from unsigned.
  * THE RAW FOLD. Mode bit 2 dumps the k=-3..3 galaxy in galaxy.bin's layout.
    It is compared against galaxyspec.py, the referee test_galaxy grades
    against C - not against work/galaxy.bin, because a stored artifact is
    exactly the thing that goes stale without anyone noticing.
  * THE CHANCE FLOOR. The unsigned fold is NOT an independent null: at this K
    every one of its matches is also a real match, because 10% of sectors emit
    a bit-identical star under it. The honest null is mode 3, unsigned AND
    decoy, and the test asserts the real rate beats it by more than 20x. If a
    future edit reintroduces "the unsigned rate is the chance floor", the
    subset assertion here fails.

HOW IT FAILS: a change to the window, the decoder, the 96-bit product, the
binary search or the outward scan shows up as a set difference with the
offending hits printed. A change to the fold shows up in the raw-dump leg
first, which localises it away from the catalogue machinery.

WHAT IT DOES NOT COVER: the acceptance window's boundary and the scan's
completeness are test_starwindow.py; the catalogue decoder over all 37,578
records is test_starkeys.py; the three author-written anchors are
test_staranchor.py.

RUN: python tests/test_starcatalogue.py     (~25s, no gcc needed)
"""

import os
import re
import sys

import galaxyspec as G
import linoharness as L
import starmapdrive as D
import starmapspec as S

K = 24                      # 117,649 sectors, ~1200 hit pairs, a few seconds

FIND = os.path.join(L.WORK, "starmap_find.txt")


def strip_comments(text):
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r"\([^()]*\)", " ", text)
    return text


def constants_of(text):
    body = strip_comments(text)
    m = re.search(r'"constants"(.*?)"variables"', body, re.S)
    out = {}
    for name, val in re.findall(r"(\w+)\s*=\s*([0-9A-Fa-f]+h|\d+)\s*;", m.group(1)):
        out[name] = int(val[:-1], 16) if val.endswith("h") else int(val)
    return out


def main():
    c = L.Check("test_starcatalogue - the sweep's hit set, refereed exactly")
    if not c.ok(os.path.exists(S.CATALOGUE),
                "the real STARMAP.BIN is where the reference clone puts it",
                S.CATALOGUE):
        return c.done()
    src = open(FIND, "r", encoding="utf-8", errors="replace").read()

    # --------------------------------------------- 1. the referee's own footing
    # starmapspec only adds the unsigned fold to galaxyspec; if its signed path
    # ever drifted from the referee test_galaxy grades against C, every
    # comparison below would be graded by the wrong judge.
    same = all(S.hash_sector(*co) == G.hash_sector(*co) for co in G.cube())
    c.ok(same, "starmapspec's signed hash is galaxyspec's, sector for sector")
    diff = sum(1 for co in G.cube()
               if S.hash_sector(*co, fold=S.fold_unsigned) != G.hash_sector(*co))
    c.ok(diff > 0, "its unsigned fold differs from it - the control is a control",
         "%d of 343 sectors differ" % diff)

    # --------------------------------------------- 2. constants the referee assumes
    k = constants_of(src)
    c.eq(k.get("SECTORSIZE"), S.SECTORSIZE, "SECTORSIZE")
    c.eq(k.get("CUTOFF"), G.CUTOFF, "CUTOFF")
    c.eq(k.get("MAPBYTES"), 4 + 32 * 37578, "MAPBYTES is the real catalogue's size")
    c.eq(k.get("WIN1", 0) * (1 << 32) + k.get("WIN0", 0), S.WINDOW,
         "WIN1:WIN0 is the 1e10 acceptance window")
    c.eq(k.get("E15HI", 0) * (1 << 32) + k.get("E15LO", 0), S.SCALE,
         "E15HI:E15LO is 1e15")
    c.eq(k.get("DEC1", 0) * (1 << 32), S.DECOY, "DEC1 is the decoy's 2^40 shift")
    c.eq(k.get("EMAX"), S.EMAX, "EMAX - the exponent above which a key rejects")
    c.eq(k.get("MAGIC"), S.MAGIC, "MAGIC")
    c.eq((k.get("MODEDECOY"), k.get("MODEUNS"), k.get("MODERAW")),
         (D.MODE_DECOY, D.MODE_UNSIGNED, D.MODE_RAW), "the mode bits")

    # --------------------------------------------- 3. signedness in the source
    body = strip_comments(src)
    c.eq(len(re.findall(r"\*%(?!')", body)), 1,
         "exactly one SIGNED *% in the file - the galaxy fold")
    c.eq(len(re.findall(r"\*%'", body)), 8,
         "eight unsigned *%' - the control fold, Mul96's three, Decode's four")
    fold = re.search(r'"FoldMul"(.*?)"HashSector"', body, re.S).group(1)
    c.ok(re.search(r"\?\s*\[uflag\]\s*!=\s*0\s*->\s*fold unsigned", fold)
         and fold.index("*%'") > fold.index("*% B"),
         "FoldMul's default path is the signed one; the unsigned form is "
         "behind the runtime uflag branch")

    # --------------------------------------------- 4. build the localised copy
    f = D.Find(stem="tscat", sbox_name="tscat")
    c.eq(f.nsubs, f.want_subs,
         "the sandbox copy rewrote every file-name literal (work/ untouched)")
    ok, msg = f.build()
    if not c.ok(ok, "starmap_find.txt builds on the extended toolchain", msg):
        return c.done()
    blob, imul = L.opcode_sites(f.exe, L.IMUL_EBX)
    _, mul = L.opcode_sites(f.exe, L.MUL_EBX)
    c.eq(len(imul), 1, "the binary carries one signed imul ebx (F7 EB)")
    c.eq(len(mul), 8, "...and eight unsigned mul ebx (F7 E3)")

    cat = f.real_catalogue()
    c.eq(len(cat), k.get("MAPBYTES"), "the real STARMAP.BIN is MAPBYTES long")
    recs = S.load_catalogue()

    # --------------------------------------------- 5. the fold, before the catalogue
    _, raw, failed, msg = f.run(3, D.MODE_RAW, timeout=120)
    if c.ok(raw is not None and not failed, "raw dump runs", msg):
        want = G.pack(G.records(G.cube()))
        c.eq(len(raw), len(want), "raw dump is 343 sectors x 5 units")
        c.ok(raw == want,
             "starmap_find's fold reproduces galaxyspec's galaxy byte for byte",
             "sha %s vs %s" % (L.sha(raw)[:16], L.sha(want)[:16]))

    # --------------------------------------------- 6. the real sweep
    h, hits, failed, msg = f.run(K, 0)
    if not c.ok(h is not None and not failed, "the K=%d sweep runs" % K, msg):
        return c.done()

    rhits, counts, stars = S.run(K, recs=recs)
    c.eq(h["magic"], S.MAGIC, "output carries the STMP magic")
    c.eq((h["K"], h["nsect"]), (K, (2 * K + 1) ** 3), "K and sector count")
    c.eq(h["nlive"] + h["ndead"], h["nsect"], "every sector is live or dead")
    c.eq(h["nlive"], len(stars), "live sector count agrees with the referee")
    c.eq((h["nkeys"], h["nrejkey"], h["nbigkey"]),
         (counts["nkeys"], counts["nrejkey"], counts["nbigkey"]),
         "key table: usable, rejected, over the 2^94 ceiling")
    c.eq(h["unsorted"], 0, "the sort verified itself")
    c.eq(h["overflow"], 0, "no hit-table overflow")
    c.eq(h["anchors"], 7, "all three author-written anchors pass")

    mine = {(r, x, y, z, P, abs(P - N)) for (r, x, y, z, P, N) in rhits}
    theirs = set(hits)
    c.eq(len(hits), h["nhits"], "header hit count matches the records written")
    c.ok(mine == theirs,
         "every hit agrees: ordinal, x, y, z, P and the recorded |P - N|",
         "%d referee, %d lino, %d referee-only, %d lino-only"
         % (len(mine), len(theirs), len(mine - theirs), len(theirs - mine)))
    for e in list(mine - theirs)[:3]:
        c.note("referee-only %r" % (e,))
    for e in list(theirs - mine)[:3]:
        c.note("lino-only    %r" % (e,))

    real_ids = {t[0] for t in theirs}
    c.note("K=%d: %d live sectors, %d hit pairs, %d distinct catalogue records, "
           "%.3f%% of %d keys"
           % (K, h["nlive"], len(theirs), len(real_ids),
              100.0 * len(real_ids) / h["nkeys"], h["nkeys"]))

    # --------------------------------------------- 7. the controls, same binary
    ctl = {}
    for tag, mode, kw in (("decoy", D.MODE_DECOY, dict(decoy=True)),
                          ("unsigned", D.MODE_UNSIGNED, dict(unsigned=True)),
                          ("uns+decoy", D.MODE_UNSIGNED | D.MODE_DECOY,
                           dict(unsigned=True, decoy=True))):
        ch, chits, cfailed, cmsg = f.run(K, mode)
        if not c.ok(ch is not None and not cfailed, "%s control runs" % tag, cmsg):
            continue
        rh, _cnt, _st = S.run(K, recs=recs, **kw)
        cm = {(r, x, y, z, P, abs(P - N)) for (r, x, y, z, P, N) in rh}
        c.ok(cm == set(chits), "%s control agrees with the referee exactly" % tag,
             "%d referee, %d lino" % (len(cm), len(chits)))
        ctl[tag] = ({t[0] for t in chits}, ch)

    if "unsigned" in ctl:
        uids, uh = ctl["unsigned"]
        c.ok(uids != real_ids,
             "the unsigned fold produces a DIFFERENT result - the comparison "
             "can see the signedness of the fold",
             "%d distinct vs %d real" % (len(uids), len(real_ids)))
        c.eq(uh["anchors"], 0, "no anchor survives the unsigned fold")
        # Why mode 2 alone is not the chance floor: it is not an independent
        # galaxy. Roughly a tenth of sectors emit a bit-identical star under
        # it, so its matches are a subset of the real ones rather than a
        # sample of what a wrong generator would hit.
        c.ok(uids <= real_ids,
             "every unsigned-control match is ALSO a real match - so the "
             "unsigned rate is not a chance floor",
             "%d of %d inside the real set" % (len(uids & real_ids), len(uids)))
    if "decoy" in ctl:
        c.eq(ctl["decoy"][1]["anchors"], 7,
             "the decoy shifts keys only, so the anchors still pass")
    if "uns+decoy" in ctl:
        nids, nh = ctl["uns+decoy"]
        c.eq(nh["anchors"], 0, "the honest null fails every anchor")
        signal = len(real_ids) / max(len(nids), 1)
        c.ok(signal > 20,
             "the real rate beats the honest null (mode 3, unsigned AND decoy) "
             "by more than 20x",
             "%d vs %d distinct records = %.0fx" % (len(real_ids), len(nids), signal))

    return c.done()


if __name__ == "__main__":
    sys.exit(main())
