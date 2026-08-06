#!/usr/bin/env python3
"""
pg_mut.py -- the Wave 6a mutation matrix.

WHY THIS EXISTS.  w5audit.py executes every check condition over random
assignments to find conditions that can never be false.  It reads PYTHON.
pg_ref.c is C, so the entire oracle side is outside its reach -- that is the
same gap that let fb_ref.c's E1 pair ship.  The gap CANNOT be closed by
naming; the only substitute is mechanical, and this is it.

Each row builds pg_ref.c with ONE -DBREAK_* edit, runs the four frozen
corpora, and diffs the record stream against the clean build.  A sabotage that
moves nothing is a check that cannot fail.  The expected surface is declared
per sabotage, so "caught" is not enough: it must be caught WHERE the design
says it will be, and a sabotage that starts being caught somewhere new is as
much a finding as one that stops being caught.

SPECIFICITY IS A SEPARATE FAILURE FROM SENSITIVITY (HARNESSAUDIT 5.3).  The
first row of the matrix feeds the CLEAN build to the matrix and requires
NOT CAUGHT.  Wave 5 hit both failure modes.

Usage:  python pg_mut.py [--only NAME] [--jobs N] [--quiet]
Exit:   0 if every sabotage is caught on its declared surfaces and the null
        row is not caught; 1 otherwise.
"""

import argparse, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pg_grade as G

CC = ["gcc", "-O2", "-std=c11", "-o"]

# name -> (expected surfaces, what it breaks)
SABOTAGE = [
 ("CONST310",     {"S2","S3","S4","S6","S7"},
  "ubx=310 x_centro=160 -- the mistake a recon agent actually made.  NOT S1: "
  "Segmento contains no constants, which is why it is graded separately"),
 ("NOFB1",        {"S3"},           "delete the single-run fallback"),
 ("BRESENHAM",    {"S1","S3"},      "round the DDA step up instead of truncating"),
 ("BYTESM1",      {"S3"},           "bytes = width+1"),
 ("NOFASTROW",    {"S3"},           "delete the min_y==max_y fast path"),
 ("DWORDONLY",    {"S3"},           "drop the `and cl,3` tail"),
 ("SEGOFF0",      {"S1","S3"},      "es:[di] instead of es:[di+4]"),
 ("SEGCLOSED",    {"S1","S3"},      "paint the greater-x endpoint column"),
 ("BBOXGT",       {"S2","S6"},      "invert the >= on ubx"),
 ("BBOXLE",       {"S2","S6"},      "invert the < on lbx"),
 ("FILLONE",      {"S3"},           "never fill past the first run"),
 ("NEIGH320",     {"S3"},           "[di-320] instead of [di-321] in flares=2"),
 ("IPARTTRUNC",   {"S4"},           "truncate bndx instead of nearest-even"),
 ("IPARTF32",     {"S4"},           "carry bndx in binary32"),
 ("IPARTPROD",    {"S4"},           "round the product, not the sum, in the top clip"),
 ("IPARTINCL",    {"S4"},           "ity <= jty instead of <"),
 ("TEXCLAMP",     {"S5"},           "saturate the accumulator instead of wrapping"),
 ("BLOCK17",      {"S5"},           "cl = min(sections,17)"),
 ("SPANINCL",     {"S5"},           "right-inclusive span"),
 ("HALFI2",       {"S5"},           "ipart[i-2] in halfscan"),
 ("HALFSKEW",     {"S5"},           "drop the -4 in halfscan"),
 ("BUMPROW",      {"S5"},           "bumper writes +320 instead of +640"),
 ("BRIGHT3F",     {"S5"},           "bright clamps at 0x3F"),
 ("SCRATCH64000", {"S5"},           "LR's relocation of the scratch pair"),
 ("NOPLUS1",      {"S6"},           "drop the +1 in trace's sample point"),
 ("NEARSTRICT",   {"S6","S3"},      "Zc > uneg instead of >= (NEAR_ATUNEG_DRAW "
  "carries it to the page)"),
 ("ZKEPS",        {"S6"},           "epsilon instead of exact equality in the zk guard"),
 ("GETCOORDINCL", {"S7"},           ">= instead of > at TDPOLYGS.H:3200"),
 ("CHOP",         {"S4","S6","S7"}, "chop at the 16 conversion sites"),
]

# Sabotages that are PROVABLY NULL and are recorded as such.  Each is expected
# to move NOTHING; if one ever starts being caught, the port has changed what
# it reads and that is a finding in its own right.
NULL_BY_CONSTRUCTION = [
 ("UV32", "32-bit u/v accumulators.  `add ax,bp` is a 16-bit add; the texel "
          "index is (dh<<8)|ah, i.e. bits 8..15 of EDX and EAX.  Addition mod "
          "2**32 and mod 2**16 agree on bits 0..15, and bits 16+ are never "
          "read, so widening the accumulator is UNOBSERVABLE.  The plan lists "
          "this as an S5 catcher; it cannot be one.  TEXCLAMP (saturate "
          "instead of wrap) is the sabotage that actually probes the wrap."),
]

# flag-driven schedule sabotages: same matrix, no rebuild
SCHEDULE = [
 ("acc=f32",       {"S4","S6"}, "carry the accumulator at binary32"),
 ("fst=allwide",   {"S6"},      "collapse the fst asymmetry wide"),
 ("fst=allnarrow", {"S6"},      "collapse the fst asymmetry narrow"),
 ("round=chop",    {"S4","S6","S7"}, "chop via the flag rather than -D"),
]


def build(name):
    exe = os.path.join(HERE, "pg_break_%s.exe" % name)
    cmd = CC + [exe, os.path.join(HERE, "pg_ref.c"),
                "-DBREAK_%s" % name, '-DPGBREAK="%s"' % name]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode:
        sys.stderr.write(p.stderr)
        raise SystemExit("pg_mut: build of %s failed" % name)
    return exe


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    clean = os.path.join(HERE, "pg_ref.exe")
    p = subprocess.run(CC + [clean, os.path.join(HERE, "pg_ref.c")],
                       capture_output=True, text=True)
    if p.returncode:
        sys.stderr.write(p.stderr); return 2
    base = G.run(clean)
    print("pg_mut: clean build produced %d records over %d corpora"
          % (len(base), len(G.CORPORA)))
    print()

    rows, bad = [], 0

    # ---- the null row: specificity ---------------------------------------
    base2 = G.run(clean)
    d = G.diff_by_surface(base, base2)
    ok = not d
    rows.append(("(null: clean vs clean)", "-", "NOT CAUGHT" if ok else "CAUGHT",
                 "PASS" if ok else "FAIL",
                 "specificity: the matrix must not flag a working build"))
    if not ok:
        bad += 1

    todo = [s for s in SABOTAGE if not a.only or s[0] == a.only]
    for name, want, why in todo:
        t0 = time.time()
        exe = build(name)
        got = G.run(exe)
        d = G.diff_by_surface(base, got)
        surf = set(d)
        n = sum(len(v) for v in d.values())
        hit = bool(want & surf)
        exact = (surf == want)
        status = "PASS" if hit else "FAIL"
        if not hit:
            bad += 1
        note = "%d records on %s" % (n, sorted(surf) or "NOTHING")
        if hit and not exact:
            note += "  [declared %s -- collateral %s, missing %s]" % (
                sorted(want), sorted(surf - want) or "-", sorted(want - surf) or "-")
        rows.append((name, "%.1fs" % (time.time() - t0),
                     "CAUGHT" if n else "NOT CAUGHT", status, note + " :: " + why))
        os.remove(exe)

    if not a.only:
        for name, why in NULL_BY_CONSTRUCTION:
            exe = build(name)
            got = G.run(exe)
            d = G.diff_by_surface(base, got)
            n = sum(len(v) for v in d.values())
            ok = (n == 0)
            if not ok:
                bad += 1
            rows.append((name + " (null)", "-", "CAUGHT" if n else "NOT CAUGHT",
                         "PASS" if ok else "FAIL",
                         "%d records, EXPECTED 0 :: %s" % (n, why)))
            os.remove(exe)
        for flag, want, why in SCHEDULE:
            got = G.run(clean, ["--" + flag])
            d = G.diff_by_surface(base, got)
            surf = set(d)
            n = sum(len(v) for v in d.values())
            hit = bool(want & surf)
            if not hit:
                bad += 1
            rows.append(("--" + flag, "-", "CAUGHT" if n else "NOT CAUGHT",
                         "PASS" if hit else "FAIL",
                         "%d records on %s :: %s" % (n, sorted(surf) or "NOTHING", why)))

    w = max(len(r[0]) for r in rows)
    for nm, tm, caught, st, note in rows:
        print("%-*s  %-6s  %-10s  %-4s  %s" % (w, nm, tm, caught, st, note))
    print()
    print("pg_mut: %d rows, %d FAIL" % (len(rows), bad))
    print("pg_mut: every row above is a sabotage that was BUILT AND RUN.  A row")
    print("        reading NOT CAUGHT is a check this wave cannot make.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
