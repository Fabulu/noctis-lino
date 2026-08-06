#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
sp_compare.py -- Wave 6b: the join between producers.

THIS FILE RENDERS NO VERDICTS.  It parses SPDUMPs, joins them record by
record and field by field, and returns DATA.  Every PASS/FAIL in Wave 6b is
spelled `linoharness.Check.ok` in tests/test_sphere.py, which is inside
w5audit.py's scope.  There is deliberately no sp_grade.py: Wave 6a's
`pg_grade.py` shipped two rows of the form `PASS if tot else N/A` where `tot`
can never be zero, one row that goes GREEN when its input is deleted, and
eight rows permanently N/A -- that is what a second verdict vocabulary
produces, and the analyser does not read its recorder either.

The comparison rule this wave is gated on (adopted verbatim from RECON C):

    Every check names which of FOUR sources each of its two sides comes from
    -- the shipped table/asset, the recovered formula, the 1996 binary, or an
    implementation -- and the two sides must not be the same source.
    Table-vs-table is never admissible.

So: joining sp_ref.c against sp_spec.py is implementation-vs-implementation
and is a real check on the FOUR ARITHMETIC STEPS after the decode (+centre,
xmag, clip, store).  It is NOT a check on the geometry.  Feeding GLOBES.MAP
to two implementations and getting one page proves they agree about
arithmetic and nothing about latitude.  The geometry is graded by the pinned
predictor in sp_spec.py against the shipped table, and by sp_bin.py against
NOCTIS.EXE.  Callers must not conflate the three.

Usage:
    python sp_compare.py A.dump B.dump [--pages-a DIR --pages-b DIR]
"""

import argparse
import hashlib
import os
import sys

# Record shapes.  key = (kind, case-id [, index]); value = the ordered fields.
# Anything not listed is carried as an UNJOINED record and counted, so a
# producer that starts emitting something new cannot slip past unnoticed.

KEYED_ONE = {
    "GLOBE": ["cursor", "drawn", "ylo", "yhi", "xlo", "xhi", "tapmin", "tapmax"],
    "GLOW": ["counter", "drawn", "decim", "rejy", "xlo", "xhi", "oobn",
             "oobmin", "oobmax", "oobw", "light", "dark"],
    "BG": ["src", "paints", "skips", "wrapped", "smin", "smax", "boundary"],
    "DARK": ["first", "last"],
    "WHITE": ["writes", "clipped"],
    "PRE": ["rej", "rz", "rx", "ry", "mag", "gman", "cx", "cy", "xsunw"],
    "ARENA": ["h", "n", "ptr", "nvtx", "x", "y", "z", "c", "mx", "my", "mz",
              "md", "di", "len", "top", "mid"],
    "NONFIN": None,       # positional
}

POSITIONAL = {
    "PAGE": 1,      # <cid> <sha256>
    "NONFIN": 1,
    "XSUN": 1,
    "WCENTRE": 2,
    "SLOT3": 3,     # <cid> <idx> <x> <y> <z>   -> keyed by (cid, idx)
    "MID": 3,
    "SCALE": None,  # <magbits> <dy> <value>
    "MANGLE": None,
    "GLOWCOL": None,
    "GCOL": None,
    "WSTORE": None,
    "GMAN": None,
    "SORT": None,
    "SWAP": None,
    "PVL": None,
    "OOB": None,
    "NCCERR": None,
}


def parse(path):
    """Returns dict: kind -> list of (key, fields).  Order is preserved,
    because order is part of the fixture for the stateful kinds."""
    out = {}
    hdr = {}
    with open(path) as f:
        for ln in f:
            ln = ln.rstrip("\n").rstrip("\r")
            if not ln:
                continue
            p = ln.split()
            k = p[0]
            if k == "SPDUMP":
                hdr = dict(t.split("=", 1) for t in p[2:] if "=" in t)
                hdr["_v"] = p[1]
                continue
            if k == "ASSET":
                hdr["asset_" + p[1]] = p[2]
                continue
            out.setdefault(k, []).append(p[1:])
    return hdr, out


def _kv(fields):
    d, pos = {}, []
    for t in fields:
        if "=" in t:
            a, b = t.split("=", 1)
            d[a] = b
        else:
            pos.append(t)
    return d, pos


def join_keyed(A, B, kind):
    """Field-by-field join of a `KIND cid k=v ...` record set.

    Element by element, NEVER a predicate over two whole tuples: the audit's
    Rule A reads a comparison of two aggregates as always-true.
    """
    ra = {f[0]: _kv(f[1:])[0] for f in A.get(kind, [])}
    rb = {f[0]: _kv(f[1:])[0] for f in B.get(kind, [])}
    diffs, compared = [], 0
    for cid in sorted(set(ra) & set(rb)):
        for fld in KEYED_ONE.get(kind) or sorted(set(ra[cid]) | set(rb[cid])):
            va, vb = ra[cid].get(fld), rb[cid].get(fld)
            compared += 1
            if va != vb:
                diffs.append((cid, fld, va, vb))
    return dict(kind=kind, cases_a=len(ra), cases_b=len(rb),
                joined=len(set(ra) & set(rb)),
                only_a=sorted(set(ra) - set(rb)),
                only_b=sorted(set(rb) - set(ra)),
                compared=compared, diffs=diffs)


def join_positional(A, B, kind, nkey):
    ra, rb = {}, {}
    for f in A.get(kind, []):
        ra.setdefault(tuple(f[:nkey]), []).append(tuple(f[nkey:]))
    for f in B.get(kind, []):
        rb.setdefault(tuple(f[:nkey]), []).append(tuple(f[nkey:]))
    diffs, compared = [], 0
    for k in sorted(set(ra) & set(rb)):
        la, lb = ra[k], rb[k]
        n = min(len(la), len(lb))
        if len(la) != len(lb):
            diffs.append((k, "COUNT", len(la), len(lb)))
        for i in range(n):
            for j in range(max(len(la[i]), len(lb[i]))):
                va = la[i][j] if j < len(la[i]) else None
                vb = lb[i][j] if j < len(lb[i]) else None
                compared += 1
                if va != vb:
                    diffs.append((k, "f%d[%d]" % (j, i), va, vb))
    return dict(kind=kind, keys_a=len(ra), keys_b=len(rb),
                joined=len(set(ra) & set(rb)),
                only_a=sorted(set(ra) - set(rb))[:8],
                only_b=sorted(set(rb) - set(ra))[:8],
                compared=compared, diffs=diffs)


def join_sequence(A, B, kind):
    """For records whose whole POINT is the sequence: OOB indices, QuickSort
    swaps.  Compared element by element with the length as its own field."""
    sa, sb = {}, {}
    for f in A.get(kind, []):
        sa.setdefault(f[0], []).append(tuple(f[1:]))
    for f in B.get(kind, []):
        sb.setdefault(f[0], []).append(tuple(f[1:]))
    diffs, compared = [], 0
    for cid in sorted(set(sa) | set(sb)):
        la, lb = sa.get(cid, []), sb.get(cid, [])
        compared += 1
        if len(la) != len(lb):
            diffs.append((cid, "LEN", len(la), len(lb)))
        for i in range(min(len(la), len(lb))):
            for j in range(len(la[i])):
                compared += 1
                if j >= len(lb[i]) or la[i][j] != lb[i][j]:
                    diffs.append((cid, "i%d.f%d" % (i, j), la[i][j],
                                  lb[i][j] if j < len(lb[i]) else None))
    return dict(kind=kind, cases=len(set(sa) | set(sb)),
                compared=compared, diffs=diffs,
                lengths={c: len(sa.get(c, [])) for c in sorted(set(sa) | set(sb))})


def compare_pages(A, B, dira=None, dirb=None):
    """The PAGE record carries a sha256, which is enough to say IF two pages
    differ.  When the page directories are present the comparison is done on
    the 64,000 BYTES, so a difference is reported as a byte count and a first
    offset rather than as an opaque hash mismatch."""
    ha = {f[0]: f[1] for f in A.get("PAGE", [])}
    hb = {f[0]: f[1] for f in B.get("PAGE", [])}
    rows = []
    for cid in sorted(set(ha) & set(hb)):
        same = ha[cid] == hb[cid]
        nd, first = 0, -1
        if not same and dira and dirb:
            pa = os.path.join(dira, cid + ".page")
            pb = os.path.join(dirb, cid + ".page")
            if os.path.exists(pa) and os.path.exists(pb):
                a = open(pa, "rb").read()
                b = open(pb, "rb").read()
                for i in range(min(len(a), len(b))):
                    if a[i] != b[i]:
                        nd += 1
                        if first < 0:
                            first = i
        rows.append(dict(case=cid, same=same, ndiff=nd, first=first,
                         sha_a=ha[cid], sha_b=hb[cid]))
    return dict(joined=len(set(ha) & set(hb)),
                only_a=sorted(set(ha) - set(hb)),
                only_b=sorted(set(hb) - set(ha)),
                rows=rows, ndiff=sum(1 for r in rows if not r["same"]))


def page_bytes(pagedir, cid):
    p = os.path.join(pagedir, cid + ".page")
    return open(p, "rb").read() if os.path.exists(p) else None


def full_compare(patha, pathb, dira=None, dirb=None):
    hda, A = parse(patha)
    hdb, B = parse(pathb)
    out = dict(header_a=hda, header_b=hdb, kinds_a=sorted(A), kinds_b=sorted(B))
    out["keyed"] = {k: join_keyed(A, B, k) for k in KEYED_ONE
                    if k in A and k in B and KEYED_ONE[k]}
    out["slot3"] = join_positional(A, B, "SLOT3", 2)
    out["mid"] = join_positional(A, B, "MID", 2)
    out["nonfin"] = join_positional(A, B, "NONFIN", 1)
    out["xsun"] = join_positional(A, B, "XSUN", 1)
    out["wcentre"] = join_positional(A, B, "WCENTRE", 1)
    out["oob"] = join_sequence(A, B, "OOB")
    out["bgb"] = join_sequence(A, B, "BGB")
    out["bgidx"] = join_positional(A, B, "BGIDX", 1)
    out["swap"] = join_sequence(A, B, "SWAP")
    out["sort"] = join_sequence(A, B, "SORT")
    out["pvl"] = join_sequence(A, B, "PVL")
    out["pages"] = compare_pages(A, B, dira, dirb)
    out["scale"] = join_positional(A, B, "SCALE", 2)
    # graded + ungraded == everything: a record kind that falls out of BOTH
    # sets silently is exactly the hole N1 exists to close.
    covered = set(out["keyed"]) | {"SLOT3", "MID", "NONFIN", "XSUN", "WCENTRE",
                                   "OOB", "SWAP", "SORT", "PVL", "PAGE",
                                   "SCALE", "BGB", "BGIDX"}
    out["unjoined_kinds_a"] = sorted(set(A) - covered)
    out["unjoined_kinds_b"] = sorted(set(B) - covered)
    out["total_compared"] = (
        sum(v["compared"] for v in out["keyed"].values())
        + sum(out[k]["compared"] for k in ("slot3", "mid", "nonfin", "xsun",
                                           "wcentre", "bgidx", "oob", "bgb",
                                           "swap", "sort", "pvl", "scale")))
    out["total_diffs"] = (
        sum(len(v["diffs"]) for v in out["keyed"].values())
        + sum(len(out[k]["diffs"]) for k in ("slot3", "mid", "nonfin", "xsun",
                                             "wcentre", "bgidx", "oob", "bgb",
                                             "swap", "sort", "pvl", "scale")))
    return out


def report(r, limit=12):
    print("A: %s" % r["header_a"])
    print("B: %s" % r["header_b"])
    print()
    print("%-10s %8s %8s %10s %8s  %s" % ("KIND", "joinedA", "joinedB",
                                          "compared", "differ", "only-in"))
    for k in sorted(r["keyed"]):
        v = r["keyed"][k]
        print("%-10s %8d %8d %10d %8d  a:%s b:%s"
              % (k, v["cases_a"], v["cases_b"], v["compared"], len(v["diffs"]),
                 v["only_a"][:3], v["only_b"][:3]))
    for k in ("slot3", "mid", "nonfin", "xsun", "wcentre", "bgidx", "scale"):
        v = r[k]
        print("%-10s %8d %8d %10d %8d  a:%s b:%s"
              % (k.upper(), v["keys_a"], v["keys_b"], v["compared"],
                 len(v["diffs"]), v["only_a"][:2], v["only_b"][:2]))
    for k in ("oob", "bgb", "swap", "sort", "pvl"):
        v = r[k]
        print("%-10s %8d %8s %10d %8d"
              % (k.upper(), v["cases"], "-", v["compared"], len(v["diffs"])))
    p = r["pages"]
    print("%-10s %8d %8s %10d %8d  a:%s b:%s"
          % ("PAGE", p["joined"], "-", p["joined"], p["ndiff"],
             p["only_a"][:3], p["only_b"][:3]))
    print()
    print("total compared %d, total differ %d"
          % (r["total_compared"], r["total_diffs"]))
    if r["unjoined_kinds_a"] or r["unjoined_kinds_b"]:
        print("UNJOINED record kinds  a:%s  b:%s"
              % (r["unjoined_kinds_a"], r["unjoined_kinds_b"]))
    shown = 0
    for k in sorted(r["keyed"]):
        for d in r["keyed"][k]["diffs"]:
            if shown < limit:
                print("  DIFF %-8s %s" % (k, d))
                shown += 1
    for k in ("slot3", "mid", "nonfin", "xsun", "wcentre", "bgidx", "oob",
              "bgb", "swap", "sort", "pvl", "scale"):
        for d in r[k]["diffs"]:
            if shown < limit:
                print("  DIFF %-8s %s" % (k.upper(), d))
                shown += 1
    for row in p["rows"]:
        if not row["same"] and shown < limit:
            print("  DIFF PAGE     %s  %d bytes differ, first at %d"
                  % (row["case"], row["ndiff"], row["first"]))
            shown += 1


# --------------------------------------------------------------------------
# Corpus coverage.  Wave 6a's R1e pattern: a corpus that quietly loses a class
# must FAIL, not read green.  These are the numbers tests/test_sphere.py needs
# in order to assert that the compared set actually contains what the wave
# claims it contains -- most importantly that all four of globe's clip arms
# REJECT SOMETHING, because "0 rejections, 0 differences" reads as a pass
# exactly the way T2.LINO.MATRIX.NULL does.
# --------------------------------------------------------------------------

def coverage(dump_path, corpus_path=None):
    _, D = parse(dump_path)
    C = {}
    if corpus_path and os.path.exists(corpus_path):
        with open(corpus_path) as f:
            for ln in f:
                p = ln.split()
                if len(p) >= 3 and p[0] == "CASE":
                    C[p[1]] = (p[2], dict(t.split("=", 1) for t in p[3:]
                                          if "=" in t))
    G = {f[0]: _kv(f[1:])[0] for f in D.get("GLOBE", [])}
    L = {f[0]: _kv(f[1:])[0] for f in D.get("GLOW", [])}
    B = {f[0]: _kv(f[1:])[0] for f in D.get("BG", [])}
    A = {f[0]: _kv(f[1:])[0] for f in D.get("ARENA", [])}
    out = {}
    # the four fill managers, each with a NON-EMPTY compared page
    gm = {}
    for cid, r in G.items():
        k = C.get(cid, ("", {}))[1].get("gman")
        if k:
            gm.setdefault(int(k), 0)
            gm[int(k)] += int(r["drawn"])
    out["gman_bands_nonempty"] = {k: gm.get(k, 0) for k in (1, 2, 3, 4)}
    # each of globe's four clip arms rejecting SOMETHING, summed and per case
    arms = {a: sum(int(r[a]) for r in G.values())
            for a in ("ylo", "yhi", "xlo", "xhi")}
    out["clip_arm_rejections"] = arms
    out["clip_arms_all_nonzero"] = all(v > 0 for v in arms.values())
    out["clip_arms_in_one_case"] = sorted(
        cid for cid, r in G.items()
        if all(int(r[a]) > 0 for a in ("ylo", "yhi", "xlo", "xhi")))
    # the pinned mag_factor values actually exercised
    out["globe_mags"] = sorted({C.get(c, ("", {}))[1].get("mag")
                                for c in G if c in C} - {None})
    out["globe_colormasks"] = sorted({int(C[c][1].get("colormask", 0))
                                      for c in G if c in C})
    out["globe_saturations"] = sorted({int(C[c][1].get("sat", 0))
                                       for c in G if c in C})
    out["globe_starts"] = sorted({int(C[c][1].get("start", 0))
                                  for c in G if c in C})
    # the out-of-range riga[] reads: the whole point of glowinglobe's dead clip
    out["glow_oob_cases"] = {c: int(r["oobn"]) for c, r in L.items()
                             if int(r["oobn"]) > 0}
    out["glow_oob_total"] = sum(int(r["oobn"]) for r in L.values())
    out["glow_decimated_total"] = sum(int(r["decim"]) for r in L.values())
    # background: the u16 boundary must actually be straddled
    out["bg_boundary_hits"] = {c: int(r.get("boundary", 0)) for c, r in B.items()
                               if int(r.get("boundary", 0)) > 0}
    out["bg_wrapped_total"] = sum(int(r["wrapped"]) for r in B.values())
    out["bg_shifts"] = sorted({int(C[c][1].get("shift", 0)) for c in B if c in C})
    # QuickSort must see TIES, or it cannot be told apart from sorted()
    ties = {}
    for cid, (kind, kv) in C.items():
        if kind != "SORT":
            continue
        n = int(kv.get("n", 0))
        ds = [kv.get("d%d" % i) for i in range(n)]
        ties[cid] = len(ds) - len(set(ds))
    out["sort_ties"] = ties
    out["sort_has_ties"] = any(v > 0 for v in ties.values())
    # .NCC: VEHICLE is mandatory.  A BIRDY-only corpus grades the zeroing pass
    # vacuously -- BIRDY's slot-3 garbage maxes at 20.
    out["ncc_models"] = sorted({C[c][1].get("model") for c in A if c in C}
                               - {None})
    out["ncc_has_vehicle"] = "VEHICLE" in out["ncc_models"]
    out["ncc_has_synthetic_mixed"] = any(
        m and m.endswith("sp_synth_mixed.ncc") for m in out["ncc_models"])
    out["pages"] = len(D.get("PAGE", []))
    out["record_kinds"] = sorted(D)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b", nargs="?")
    ap.add_argument("--coverage", action="store_true")
    ap.add_argument("--corpus")
    ap.add_argument("--pages-a")
    ap.add_argument("--pages-b")
    ap.add_argument("--limit", type=int, default=12)
    x = ap.parse_args()
    if x.coverage:
        import pprint
        pprint.pprint(coverage(x.a, x.corpus))
        return 0
    r = full_compare(x.a, x.b, x.pages_a, x.pages_b)
    report(r, x.limit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
