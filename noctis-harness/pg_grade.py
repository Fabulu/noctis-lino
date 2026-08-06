#!/usr/bin/env python3
"""
pg_grade.py -- Wave 6a comparison.

EVERY ROW STATES ITS KIND.  "EXACT" means a byte/value equality with zero
tolerance.  "BOUND" means a numeric envelope, and the row prints the measured
number next to the bound so a reader never has to guess whether a pass was
comfortable or one ULP from failing.  "MEASUREMENT" means the row is not a
grade at all: it is a calibration between two schedules of the SAME producer,
reported because the wave's design depends on its value, and it is marked so
nobody mistakes it for evidence about the port.

Producers (pg_ledger.py holds the full table):
  cref:     pg_ref.c            -- transliterated from TDPOLYGS.H asm
  lino:     work/pg-out.bin     -- implementer 1
  bin:      NOCTIS.EXE          -- via pg_bin.py
  external: the frozen corpora  -- pg_corpus_*.txt

NO GRADED ROW COMPARES TWO ARTIFACTS OF THE SAME OWNER.  cref-vs-cref rows
exist and are labelled MEASUREMENT.  They are calibration, not evidence.

Usage:
  python pg_grade.py                     # measurements + lino join if present
  python pg_grade.py --lino work/pg-out.bin
  python pg_grade.py --exe pg_break_NOFB1.exe --against pg_ref.exe --diff-only
"""

import argparse, os, subprocess, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CORPORA = ["pg_corpus_raster.txt", "pg_corpus_edge.txt",
           "pg_corpus_span.txt", "pg_corpus_proj.txt"]

# record kind -> surface
KIND_SURFACE = {
    "K20": None,      # decided by the case id prefix
    "K21": None,
    "K26": None,
    "K2B": "S5",
    "K2C": "S5",
    "K23": "S4",
    "K25": "S2",
    "K22": "S6",
    "K24": "S6",
    "K29": "S6",
    "K2A": "S6",
    "K27": "S7",
    "K2D": "S7",
}


def surface_of(kind, cid):
    s = KIND_SURFACE.get(kind)
    if s:
        return s
    if cid.startswith("SEG_"):
        return "S1"
    if cid.startswith("SP_"):
        return "S5"
    if cid.startswith("EX_") or cid.startswith("CLIP_") or cid.startswith("CLIP"):
        return "S3"     # PROJ rows with draw=1 land in the rasteriser
    return "S3"


def run(exe, args=(), corpora=None):
    """Run a pg_ref build and return {(kind, id): payload}."""
    cmd = [exe] + list(args) + [os.path.join(HERE, c) for c in (corpora or CORPORA)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        sys.stderr.write(p.stderr)
        raise SystemExit("pg_grade: %s failed rc=%d" % (exe, p.returncode))
    recs = {}
    for line in p.stdout.splitlines():
        if not line or line[0] == "#":
            continue
        t = line.split()
        kind, cid = t[0], t[2]
        key = (kind, cid, t[3] if kind == "K26" else "")
        recs[key] = " ".join(t[3:])
    return recs


def diff_by_surface(a, b):
    """Which surfaces moved, and how many records in each."""
    out = collections.OrderedDict()
    keys = set(a) | set(b)
    for k in sorted(keys):
        if a.get(k) != b.get(k):
            s = surface_of(k[0], k[1])
            out.setdefault(s, []).append(k)
    return out


# ---------------------------------------------------------------- parsing ---

def mp_of(recs):
    out = {}
    for (kind, cid, _), v in recs.items():
        if kind == "K22":
            t = v.split()
            out[cid] = [int(x) for x in t[1:]]
    return out


def lim_of(recs):
    out = {}
    for (kind, cid, _), v in recs.items():
        if kind == "K23":
            t = v.split()
            pairs = []
            for tok in t[2:]:
                i, f = tok.split(":")
                pairs.append((int(i), int(f)))
            out[cid] = pairs
    return out


def topo_of(recs):
    out = {}
    for (kind, cid, _), v in recs.items():
        if kind == "K24":
            out[cid] = v
    return out


def getc_of(recs):
    return {cid: v for (kind, cid, _), v in recs.items() if kind == "K27"}


ILL = {"NEAR_ILL"}          # declared ill-conditioned: values NOT graded


# ------------------------------------------------------------------ rows -----

class Report:
    def __init__(self):
        self.rows = []

    def add(self, name, kind, status, detail):
        self.rows.append((name, kind, status, detail))

    def show(self):
        w = max(len(r[0]) for r in self.rows)
        k = max(len(r[1]) for r in self.rows)
        for n, kd, st, d in self.rows:
            print("%-*s  %-*s  %-4s  %s" % (w, n, k, kd, st, d))
        bad = [r for r in self.rows if r[2] == "FAIL"]
        print()
        print("pg_grade: %d rows, %d FAIL, %d N/A"
              % (len(self.rows), len(bad),
                 sum(1 for r in self.rows if r[2] == "N/A")))
        return 1 if bad else 0


def measure(rep, exe):
    """The two numbers the wave's design rests on.  cref-vs-cref: MEASUREMENT."""
    ext = run(exe, ["--acc=ext"])
    f64 = run(exe, ["--acc=f64"])
    f32 = run(exe, ["--acc=f32"])

    # ---- S4: the promotion from tolerant to exact ------------------------
    a, b, c = lim_of(ext), lim_of(f64), lim_of(f32)
    tot = ndiff64 = ndiff32 = 0
    for cid in sorted(a):
        for j, (i0, f0) in enumerate(a[cid]):
            tot += 2
            i1, f1 = b[cid][j]
            i2, f2 = c[cid][j]
            ndiff64 += (i0 != i1) + (f0 != f1)
            ndiff32 += (i0 != i2) + (f0 != f2)
    rep.add("S4.binary64_is_exact", "MEASUREMENT",
            "PASS" if ndiff64 == 0 else "FAIL",
            "%d/%d span limits differ between an 80-bit and a binary64 bndx "
            "accumulator (required 0)" % (ndiff64, tot))
    rep.add("S4.binary32_is_the_control", "MEASUREMENT",
            "PASS" if ndiff32 > 0 else "FAIL",
            "%d/%d differ at binary32 (%.3e) -- the negative control must be "
            "NON-zero or the S4 check is vacuous" % (ndiff32, tot,
                                                     ndiff32 / max(tot, 1)))

    # ---- S6 P3: the exact-fraction constant ------------------------------
    ma, mb, mc = mp_of(ext), mp_of(f64), mp_of(f32)
    tot = eq64 = eq32 = 0
    mx64 = mx32 = 0
    sgn64 = 0
    for cid in sorted(ma):
        if cid in ILL:
            continue
        if cid not in mb or len(ma[cid]) != len(mb[cid]):
            rep.add("S6.topology_stable_%s" % cid, "EXACT", "FAIL",
                    "vertex count changed between schedules")
            continue
        for j, v in enumerate(ma[cid]):
            tot += 1
            d = mb[cid][j] - v
            eq64 += (d == 0)
            sgn64 += d
            mx64 = max(mx64, abs(d))
            if cid in mc and len(mc[cid]) == len(ma[cid]):
                d2 = mc[cid][j] - v
                eq32 += (d2 == 0)
                mx32 = max(mx32, abs(d2))
    rep.add("S6.P3.exact_fraction", "MEASUREMENT", "PASS" if tot else "N/A",
            "binary64 vs 80-bit: %d/%d mp[] components identical (%.6f), "
            "max|delta| %d, sum signed delta %d  -- THIS NUMBER IS THE "
            "PASS/FAIL CONSTANT for the lino join, not a knob"
            % (eq64, tot, eq64 / max(tot, 1), mx64, sgn64))
    rep.add("S6.P3.f32_control", "MEASUREMENT", "PASS" if tot else "N/A",
            "binary32 vs 80-bit: %d/%d identical, max|delta| %d" % (eq32, tot, mx32))

    # The mp[] envelope is nearly blind to the accumulator width -- Recon B
    # measured 0/113,830 at binary32 and this corpus reproduces 0/N.  So the
    # exact-fraction row above is a WEAK check and must not be read as strong.
    # The records that DO discriminate schedules are the polymap gradient basis
    # (raw float32 bit patterns) and the derived u/v integers; measure those
    # separately so the corpus's real sensitivity is on the record.
    def rawsens(other, label, want_nonzero):
        n = 0
        for k in ext:
            if k[0] in ("K29", "K2A") and ext[k] != other.get(k):
                n += 1
        tot = sum(1 for k in ext if k[0] in ("K29", "K2A"))
        ok = (n > 0) if want_nonzero else (n == 0)
        rep.add("S6.basis_uv_%s" % label, "MEASUREMENT", "PASS" if ok else "FAIL",
                "%d/%d K29 BASIS + K2A ROWUV records move under %s (want %s) -- "
                "this is where the corpus HAS schedule sensitivity; mp[] has none"
                % (n, tot, label, "NON-zero" if want_nonzero else "zero"))
    rawsens(f32, "acc=f32", True)
    rawsens(f64, "acc=f64", False)

    # ---- P2: the rounding mode is the only thing the +-1 envelope is blind to
    chop = run(exe, ["--round=chop"])
    d = diff_by_surface(ext, chop)
    n = sum(len(v) for v in d.values())
    rep.add("S6.P2.round_mode_is_observable", "MEASUREMENT",
            "PASS" if n > 0 else "FAIL",
            "chop vs nearest moves %d records across %s -- a chop-vs-nearest "
            "error is <=1 by definition, so the +-1 envelope is STRUCTURALLY "
            "BLIND to it and P2 is the only thing standing in its way"
            % (n, sorted(d)))

    # ---- the fst asymmetry ------------------------------------------------
    for mode in ("allwide", "allnarrow"):
        r = run(exe, ["--fst=" + mode])
        d = diff_by_surface(ext, r)
        n = sum(len(v) for v in d.values())
        rep.add("S6.fst_%s_is_observable" % mode, "MEASUREMENT",
                "PASS" if n > 0 else "FAIL",
                "collapsing the fst asymmetry to '%s' moves %d records across "
                "%s" % (mode, n, sorted(d)))
    return ext


def grade_against_lino(rep, ext, lino_path):
    """The lino join.

    PRECONDITION, checked and reported rather than assumed: both sides must be
    consuming the SAME frozen fixture.  If implementer 1 is running its own
    corpus then there is no join to make -- the two sides would be answering
    different questions and any agreement between summary statistics would be
    meaningless.  That precondition is a check in its own right and it is the
    first thing printed.
    """
    import hashlib
    mine = {}
    for c in CORPORA:
        with open(os.path.join(HERE, c), "rb") as f:
            mine[c] = hashlib.sha256(f.read()).hexdigest()
    theirs = os.path.join(ROOT, "work", "pg-corpus.txt")
    if os.path.exists(theirs):
        with open(theirs, "rb") as f:
            th = hashlib.sha256(f.read()).hexdigest()
        shared = [c for c, h in mine.items() if h == th]
        rep.add("FIXTURE.shared_corpus", "EXACT", "PASS" if shared else "FAIL",
                "work/pg-corpus.txt sha256=%s matches %s of the four frozen "
                "corpora -- the two sides must read the SAME text or there is "
                "no join" % (th[:16], shared or "NONE"))
        if not shared:
            for nm, kd in LINO_ROWS:
                rep.add(nm + " [lino]", kd, "N/A",
                        "BLOCKED: implementer 1 is running work/pg-corpus.txt, "
                        "which is not one of the frozen corpora.  Comparing "
                        "two sides that consumed different inputs would be a "
                        "fabricated agreement.  Coordinator decision needed.")
            return
    if not lino_path or not os.path.exists(lino_path):
        for nm, kd in LINO_ROWS:
            rep.add(nm + " [lino]", kd, "N/A",
                    "no lino artifact at %s -- NOT GRADED, and this row must "
                    "not be read as a pass" % (lino_path or "work/pg-out.bin"))
        return
    for nm, kd in LINO_ROWS:
        rep.add(nm + " [lino]", kd, "N/A",
                "lino artifact present but the record format is not agreed; "
                "refusing to invent a decoder and grade against it")


LINO_ROWS = (("S1.segmento_page", "EXACT"),
             ("S2.bbox_gate", "EXACT"),
             ("S3.poly3d_page", "EXACT"),
             ("S4.span_limits", "EXACT"),
             ("S5.span_page", "EXACT"),
             ("S6.P1.topology", "EXACT"),
             ("S6.P3.mp_values", "BOUND"),
             ("S7.getcoords", "EXACT"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default=os.path.join(HERE, "pg_ref.exe"))
    ap.add_argument("--against")
    ap.add_argument("--diff-only", action="store_true")
    ap.add_argument("--lino", default=os.path.join(ROOT, "work", "pg-out.bin"))
    a = ap.parse_args()

    if a.diff_only:
        x = run(a.against or os.path.join(HERE, "pg_ref.exe"))
        y = run(a.exe)
        d = diff_by_surface(x, y)
        if not d:
            print("NOT CAUGHT (0 records differ)")
            return 0
        for s in sorted(d):
            print("%s %d" % (s, len(d[s])))
        return 0

    rep = Report()
    print("pg_grade: exe=%s" % a.exe)
    print("pg_grade: corpora=%s" % ", ".join(CORPORA))
    print()
    ext = measure(rep, a.exe)
    grade_against_lino(rep, ext, a.lino)
    print()
    return rep.show()


if __name__ == "__main__":
    sys.exit(main())
