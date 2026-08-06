r"""su_grade.py - Wave 7a, the comparison.  Implementer 2's side.

Every row below answers: could this record differ between a working mechanism
and a broken one?  Rows that cannot are not here; the ones that were
considered and rejected are listed at the bottom under NOT GRADED, with the
reason, rather than being quietly dropped.

Producers, and what each was derived FROM:

  ref   tests/gen/recon_w7a/out/*        the SHIPPED DOS BINARY's own
                                         p_background / objectschart buffers,
                                         lifted out of guest RAM by recon C,
                                         plus the palette read back out of the
                                         game's own gallery BMP.  Nothing in
                                         this project produced them.
  spec  su_spec.py                       Python, transliterated from
                                         NOCTIS-0.CPP's inline assembly.  All
                                         x87 arithmetic modelled with EXACT
                                         RATIONALS (su_fp.py) and rounded
                                         explicitly to 64/53/24 bits.
  cref  su_ref.exe (su_ref.c)            C, transliterated from the same DOS
                                         text in a separate pass, using the
                                         HARDWARE x87 - long double, fsin,
                                         fcos, fistp, control word 133Fh.
  bin   su_bin.py                        NOCTIS.EXE's bytes, compared only to
                                         constants restated in that file.
  pred  su_ledger.py                     closed-form draw counts from the loop
                                         structure; never runs a painter.

spec and cref agreeing proves the transliteration is unambiguous.  Either of
them agreeing with ref proves it is RIGHT.  Both are reported separately and
never merged into one row.

Usage:  python su_grade.py [--json]
"""

import argparse
import collections
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import numpy as np

import su_corpus
import su_ledger
import su_spec

RECON = su_corpus.RECON
REC_SZ = 64800 + 32400 + 768 + 24


def nd(a, b):
    return int((np.frombuffer(a, dtype=np.uint8)
                != np.frombuffer(b, dtype=np.uint8)).sum())


# The guest-clock secs, mirroring tests/test_surface.py (which agrees 10/10
# with the lino port) and work/su-mkcorpus.py.  su_ref.c hardcodes k.secs=0.0
# (the .spc carries no secs field), so cref's rotation is always 0 and E1e's
# rotation arm compares the spec against an independent truncating recompute,
# not against cref.  The map path uses _secs_scaled, not this secs, so feeding
# real secs here moves only rotation - C1/C2/C3 are untouched.  getsecs is
# NOCTIS-0.CPP:3931-3950.
def _getsecs(y, mo, d, h, mi, s):
    dfm = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    v = y - 1984
    v = v * 365 + v // 4
    for m in range(1, mo):
        v += dfm[m]
    if mo > 2 and y % 4 == 0:
        v += 1
    v += d - 1
    v *= 86400
    return v + 3600 * h + 60 * mi + s

SECS_BASE = _getsecs(2026, 8, 6, 12, 0, 0)
_SECS_ELAPSED = {"lane_b00_t2": 22 + 3.5 / 10, "lane_b03_t3": 20 + 0.5,
                 "lane_b02_t5": 10 + 54.5 / 60, "jrot_b00_t6": 9 + 1.5 / 60}


def _secs_for(r):
    if r["kind"] != "capture":
        return 0.0
    return float(SECS_BASE) + _SECS_ELAPSED.get(r["tag"], 0.0)


def run_spec(r):
    S = su_spec.Surface(ledger=True)
    if r["use_scaled"]:
        S._secs_scaled = r["secs_scaled"]
    out = S.run(r["id"], r["type"], r["seedval"], r["colorbase"],
                secs=_secs_for(r), plwp=r["plwp"], owner=r["owner"],
                nearstar_rgb=r["rgb"])
    return S, out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    rows = []
    rowsets = collections.Counter()

    def add(cid, case, claim, got, want, ok, note=""):
        rows.append(dict(check=cid, case=case, claim=claim, got=str(got),
                         want=str(want), ok=bool(ok), note=note))
        rowsets[claim] += 1
        return bool(ok)

    su_corpus.write(os.path.join(HERE, "su_corpus.spc"), su_corpus.all_cases())
    cbin = open(os.path.join(HERE, "su_ref.bin"), "rb").read()
    rows_c = su_corpus.all_cases()
    if len(cbin) != len(rows_c) * REC_SZ:
        print("su_ref.bin is stale: %d bytes, expected %d.  Re-run "
              "su_ref.exe su_corpus.spc su_ref.bin" % (len(cbin),
                                                       len(rows_c) * REC_SZ))
        return 2

    all_ok = True
    for i, r in enumerate(rows_c):
        o = i * REC_SZ
        cmap = cbin[o:o + 64800]
        covl = cbin[o + 64800:o + 97200]
        cpal = cbin[o + 97200:o + 97968]
        cnt = struct.unpack_from("<6i", cbin, o + 97968)

        S, out = run_spec(r)
        smap, sovl = S.map_bytes(), S.ovl_bytes()
        spal = bytes(S.tmppal)
        tag = r["tag"]

        # -- E1  spec == cref, on every case, capture and synthetic alike.
        all_ok &= add("E1a", tag, "BOUNDED", nd(smap, cmap), 0,
                      smap == cmap,
                      "two independent transliterations, one with exact "
                      "rationals and one with hardware x87")
        all_ok &= add("E1b", tag, "BOUNDED", nd(sovl, covl), 0, sovl == covl)
        all_ok &= add("E1c", tag, "BOUNDED",
                      sum(1 for x, y in zip(spal, cpal) if x != y), 0,
                      spal == cpal)
        all_ok &= add("E1d", tag, "BOUNDED",
                      (out.get("fast_n", 0), out.get("brtl_n", 0)),
                      (cnt[0], cnt[1]),
                      out.get("fast_n", 0) == cnt[0] and
                      out.get("brtl_n", 0) == cnt[1],
                      "per-stream draw totals")
        # -- E1e  nearstar_p_rtperiod / _rotation.  These come from the FIRST
        #    fast_srand bridge, fast_srand(seedval + 4112), which is RESEEDED
        #    before anything touches the map - so they are the ONLY outputs
        #    that can see a defect in that bridge.  No artefact in out/ exposes
        #    them (that needed recon C's CAP-1 DGROUP dump, which does not
        #    exist), so this row is BOUNDED, and C4/C5 stay UNGRADED.
        # rtperiod vs cref (secs-independent).  rotation vs an INDEPENDENT
        # truncating recompute, NOT cnt[3]: su_ref.c hardcodes k.secs=0.0, so
        # cref's rotation is always 0.  With real secs (_secs_for) the spec's
        # rotation is non-zero and negative on 5/10 captures, where a flooring
        # % (the rotmod mutation) diverges from crem.  test_surface.py C5 grades
        # rotation against the lino port; this is the spec-side modulus guard.
        rt = out.get("rtperiod", 0)
        if rt:
            _raw = su_spec.ftol32(su_spec._Fr(_secs_for(r)) / rt)
            exp_rot = su_spec.i16(su_spec.crem(su_spec.i16(_raw), 360))
        else:
            exp_rot = 0
        all_ok &= add("E1e", tag, "BOUNDED",
                      (out.get("rtperiod"), out.get("rotation")),
                      (cnt[2], exp_rot),
                      out.get("rtperiod", 0) == cnt[2] and
                      out.get("rotation", 0) == exp_rot,
                      "rtperiod vs cref; rotation vs truncating recompute "
                      "(cref secs=0 so cnt[3] is unused)")
        # -- E1f  term_start / term_end.  The REPORTER (out["term_start"], from
        #    ts = i16(plwp+35) at su_spec.py:759) and the PAINTING (di =
        #    PB+plwp+35 at :767) are SEPARATE expressions, so a mutation of
        #    :759 moves the reporter on every capture WITHOUT touching a single
        #    map byte - invisible to C1/C2/C3/C6u.  su_ref.c writes ts/te as
        #    cnt[4]/cnt[5] (its own derivation of the same NOCTIS-0.CPP text),
        #    so this is a genuine spec-vs-cref oracle, ANDed into all_ok.
        # term_start exists only when surface() did not early-return (type 10
        # at su_spec.py:664, colorbase 255 at :799); cref leaves ts/te
        # uninitialised on those same early returns, so compare only when the
        # reporter actually ran.
        if "term_start" in out:
            all_ok &= add("E1f", tag, "BOUNDED",
                          (out.get("term_start"), out.get("term_end")),
                          (cnt[4], cnt[5]),
                          out.get("term_start", 0) == cnt[4] and
                          out.get("term_end", 0) == cnt[5],
                          "term_start/term_end reporter, spec vs cref")

        # -- D2  observed counts == the closed-form prediction
        if r["type"] != 10:
            pr = su_ledger.predict(r["type"], r["colorbase"], S.gates)
            all_ok &= add("D2", tag, "EXACT(3-way)",
                          (out.get("fast_n"), out.get("brtl_n")), pr,
                          pr == (out.get("fast_n"), out.get("brtl_n")),
                          "closed form from the gate values only; never runs "
                          "a painter, so it cannot inherit a painter's bug")

        if r["kind"] != "capture":
            continue

        # -- C1/C2/C3  the binary's own buffers
        ref = open(os.path.join(RECON, tag + ".p_background"), "rb").read()
        refov = open(os.path.join(RECON, tag + ".objectschart"), "rb").read()
        man = r["manifest"]
        want_pal = b"".join(bytes(t) for t in man["palette_192_255"])

        all_ok &= add("C1", tag, "EXACT", nd(smap, ref[:64800]), 0,
                      smap == ref[:64800],
                      "spec vs the DOS binary's p_background, 64,800 bytes")
        all_ok &= add("C1c", tag, "EXACT", nd(cmap, ref[:64800]), 0,
                      cmap == ref[:64800], "cref vs the same buffer")
        all_ok &= add("C2", tag, "EXACT", nd(sovl, refov[:32400]), 0,
                      sovl == refov[:32400],
                      "the 32,400-byte cloud overlay")
        cb = r["colorbase"]
        all_ok &= add("C3", tag, "EXACT",
                      sum(1 for x, y in zip(spal[3 * cb:3 * cb + 192],
                                            want_pal) if x != y), 0,
                      spal[3 * cb:3 * cb + 192] == want_pal,
                      "64 palette triples from the gallery BMP / 4.  This is "
                      "the ONLY capture-anchored check on the brtl stream and "
                      "it survives a wholly wrong fast_random stream")
        # -- C6  plwp is an INPUT (U4), so "the terminator matches" is only
        #    worth something as a UNIQUENESS statement: no other value of plwp
        #    reproduces the bytes.  Recon C measured that a one-column shift
        #    moves 356 bytes, so the neighbourhood sweep below is the sharp
        #    part; the manifest comparison after it is informational and its
        #    three disagreements are defects in the DETECTOR, not in the port,
        #    because C1 above is byte-exact and a misplaced band cannot be.
        worst = None
        for dp in (-3, -2, -1, 1, 2, 3):
            alt = (r["plwp"] + dp) % 360
            A = su_spec.Surface(ledger=False)
            if r["use_scaled"]:
                A._secs_scaled = r["secs_scaled"]
            A.run(r["id"], r["type"], r["seedval"], r["colorbase"], secs=0.0,
                  plwp=alt, owner=r["owner"], nearstar_rgb=r["rgb"])
            d = nd(A.map_bytes(), ref[:64800])
            worst = d if worst is None else min(worst, d)
        all_ok &= add("C6u", tag, "EXACT", worst, ">0 for all 6 neighbours",
                      worst is not None and worst > 0,
                      "smallest byte-diff over plwp +-1..3; the band cannot be "
                      "in two places at once")
        mt = man["terminator"]
        agree = (out["term_start"] == mt["term_start"]
                 and out["term_end"] == mt["term_end"])
        add("C6m", tag, "meta", (out["term_start"], out["term_end"]),
            (mt["term_start"], mt["term_end"]), True,
            "INFORMATIONAL only - manifest pixel detector, known wrong on 3/10 "
            "captures; not a check and not in all_ok.  term_start/term_end is "
            "graded by E1f above (spec vs cref).  Detector %s" %
            ("agrees" if agree else "DISAGREES"))
        # -- C7  no write escapes the 64,800-byte map
        tail = ref[64800:]
        all_ok &= add("C7", tag, "EXACT",
                      "%d nonzero in ref tail, %d in spec seg" %
                      (sum(tail), sum(S.pseg[4 + 64800:4 + 65552])),
                      "0 / 0",
                      sum(tail) == 0 and sum(S.pseg[4 + 64800:4 + 65552]) == 0,
                      "bytes 64800..65551 are zero on both the binary's buffer "
                      "and the spec's segment; the map is the low 64800 bytes of "
                      "a 65536-byte segment and every store is &M16, so a vptr "
                      "wider than 16 bits is unrepresentable here (su_break.py)")

    # -------- the set-partition check: nothing falls out of all three sets --
    kinds = collections.Counter(r["kind"] for r in rows_c)
    claims = collections.Counter(x["claim"] for x in rows)
    add("PART", "-", "meta",
        dict(claims), "every row is EXACT, EXACT(3-way) or BOUNDED",
        set(claims) <= {"EXACT", "EXACT(3-way)", "BOUNDED", "meta"},
        "Wave 6b's U1c pattern: a component that is in none of the three sets "
        "is invisible")

    bad = [x for x in rows if not x["ok"]]
    w = 26
    for x in rows:
        if x["ok"] and x["check"] not in ("PART",):
            continue
        print("%-5s %-16s %-13s got=%-22s want=%-14s %s" %
              (x["check"], x["case"], x["claim"], x["got"][:22],
               x["want"][:14], "ok" if x["ok"] else "FAIL"))
    print()
    per = collections.Counter((x["check"], x["ok"]) for x in rows)
    checks = sorted(set(x["check"] for x in rows))
    for c in checks:
        n_ok, n_bad = per[(c, True)], per[(c, False)]
        print("  %-5s %3d ok  %3d fail" % (c, n_ok, n_bad))
    print("\n%d rows, %d failing" % (len(rows), len(bad)))

    print("""
NOT GRADED, and why - stated item by item rather than dropped
  U1  the `colorbase == 255` early return  : UNREACHABLE in the shipped build.
      The only live call sites (NOCTIS-0.CPP:5380-5413) pass 128 or 192, and
      TGTPVIEW.CPP is not in NOCTIS.MAK.  Exercised in the synthetic corpus
      (syn_cb255_t3), claimed for nothing.
  U2  the `type == 10` early return        : same reason.  syn_type10 runs it.
  U3  the second srand(seed) at :4844      : nothing between the two calls
      draws and Borland's srand is idempotent, so NO check can distinguish
      them.  Both are executed because the source executes both; no row claims
      to detect the difference.
  U4  cplx_planet_viewpoint / plwp         : NOT computed here.  plwp is an
      INPUT, recovered per capture by exhaustive search over all 360 values
      against the captured bytes.  Saying "the terminator matches" while
      having been told where it goes is honest only if stated, so it is.
  U5  the sub-second fps/gl_fps fraction   : the map sees only
      (long)(k*secs); the fraction below that resolution is unobservable.
  U6  provenance                           : every EXACT row above says
      "byte-exact against NIV+ Release 2.3", NOT "against the 1996 binary".
      No stock NOCTIS.EXE exists on this machine.
  U7  build_surface, ground, sky, SURFACE.BIN : Wave 7b, out of scope.

DEFECTIVE HARNESS PATTERNS THIS FILE DOES NOT USE
  fb_tick.py's self-recovering ring sweep, T2.LINO.MATRIX.NULL's vacuous
  pass, fb_ref.c's indistinguishable E1 pair, the `inrow:` escape hatch, and
  pg_grade.py's two PASS-if-tally-nonzero rows are all on paths this wave does
  not touch.  No row here passes on a nonzero tally, and no row compares an
  artefact to itself.""")

    if a.json:
        print(json.dumps(rows, indent=1))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
