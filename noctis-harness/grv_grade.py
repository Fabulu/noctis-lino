r"""grv_grade.py - Wave 7b ground-renderer comparison.  Implementer B2's side.

Grades the HPOINT bilinear height query (NOCTIS-1.CPP:63-93), the foundation
of the renderer's per-tile vertex Z, three ways:

  lino  work/walk.exe                 the L.in.oleum port, rebuilt from
                                      work/walk.txt on every run
  cref  grv_ref.exe (grv_ref.c)       C, transliterated from the same DOS
                                      text in a separate pass, on the
                                      hardware x87 (long double, control
                                      word 133Fh)
  spec  grv_spec.py                   Python, exact-rational model of the
                                      x87 (rounds to 64/24 significand bits
                                      explicitly)

All three consume the SAME corpus (noctis-harness/grv-corpus.txt) in the SAME
grammar (signed decimal integers, six per case).  Each emits py's binary32 bit
pattern per case.  E1/E2/E3 compare them pairwise, EXACT, zero tolerance.

WHY ZERO TOLERANCE IS HONEST HERE
  hpoint's only branch is `icx + icz < 16384`, an INTEGER comparison on values
  that are both < 16384, so the sum is exact and the decision carries no float
  tolerance.  Every narrowing to float32 is at a `float py = ...` store, which
  the float policy pins.  So a defect anywhere in the port moves at least one
  py bit pattern, and the three-way exact comparison catches it.  This is the
  pinned-vertex foundation fragment reads from.

Usage:  python grv_grade.py [--json]
"""

import argparse
import json
import os
import shutil
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
WORK = os.path.join(REPO, "work")
CORPUS = os.path.join(HERE, "grv-corpus.txt")
WALK_SRC = os.path.join(WORK, "walk.txt")
WALK_EXE = os.path.join(WORK, "walk.exe")
LINO_OUT = os.path.join(WORK, "grv-out.bin")
CREF_EXE = os.path.join(HERE, "grv_ref.exe")
CREF_SRC = os.path.join(HERE, "grv_ref.c")
CREF_BIN = os.path.join(HERE, "grv_ref.bin")
BUILD_PS1 = os.path.join(REPO, "lino_build.ps1")
RUN_PS1 = os.path.join(REPO, "tests", "w7arun.ps1")


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", **kw)


def build_lino():
    """Compile work/walk.txt. Returns (rc, output)."""
    # walk.exe is dumped in work/ beside the source.
    if os.path.exists(WALK_EXE):
        os.remove(WALK_EXE)
    if os.path.exists(LINO_OUT):
        os.remove(LINO_OUT)
    p = run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
             BUILD_PS1, "-Src", WALK_SRC, "-TimeoutSec", "180"])
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def run_lino():
    """Run walk.exe poll-and-kill, return the bytes it wrote, or None.

    walk.exe reads grv-corpus.txt from its own directory (work/), so stage
    the pinned corpus there before launching."""
    if os.path.exists(LINO_OUT):
        os.remove(LINO_OUT)
    shutil.copy(CORPUS, os.path.join(WORK, "grv-corpus.txt"))
    p = run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
             RUN_PS1, "-Exe", WALK_EXE, "-Out", LINO_OUT, "-TimeoutSec", "120"])
    if p.returncode != 0 or not os.path.exists(LINO_OUT):
        return None, p.stdout + p.stderr
    with open(LINO_OUT, "rb") as fh:
        return fh.read(), p.stdout + p.stderr


def build_cref():
    if os.path.exists(CREF_EXE):
        os.remove(CREF_EXE)
    p = run(["gcc", "-O2", "-fno-fast-math", "-o", CREF_EXE, CREF_SRC])
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def run_cref():
    p = run([CREF_EXE, CORPUS, CREF_BIN])
    if p.returncode != 0 or not os.path.exists(CREF_BIN):
        return None
    with open(CREF_BIN, "rb") as fh:
        return fh.read()


def parse_corpus(path):
    """Yield (px,pz,s1,s2,s3,s4) for every full row; partial rows skipped."""
    rows = []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            s = line.strip()
            if not s or s[0] == "#":
                continue
            t = s.replace(",", " ").split()
            if len(t) != 6:
                continue
            rows.append(tuple(int(x) for x in t))
    return rows


def bits_list(blob):
    return [struct.unpack_from("<i", blob, i * 4)[0]
            for i in range(len(blob) // 4)]


def branch_of(px, pz):
    """Which bilinear triangle hpoint takes for this case (0=upper,1=lower)."""
    return 0 if ((px & 16383) + (pz & 16383)) < 16384 else 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    rows = []
    notes = []
    checks = []  # (id, claim, ok, got, want, note)

    def ok(cid, claim, cond, got, want, note=""):
        checks.append(dict(check=cid, claim=claim, ok=bool(cond),
                           got=str(got), want=str(want), note=note))
        return bool(cond)

    # ---- 0. fixture -------------------------------------------------------
    ok("F0", "EXACT", os.path.exists(CORPUS), "present", "missing",
       "the pinned corpus exists")
    rows = parse_corpus(CORPUS)
    ok("F1", "EXACT", len(rows) >= 60, len(rows), ">=60 cases",
       "enough cases to cover both branches and the boundary")
    has_boundary = any(((px & 16383) + (pz & 16383)) in (16383, 16384, 16385)
                       for px, pz, *_ in rows)
    both = {branch_of(px, pz) for px, pz, *_ in rows}
    ok("F2", "EXACT", has_boundary, sorted({(px & 16383) + (pz & 16383)
                                            for px, pz, *_ in rows
                                            if (px & 16383) + (pz & 16383)
                                            in (16383, 16384, 16385)}),
       "the icx+icz = 16383/16384/16385 boundary is in the corpus",
       "without it the branch test is ungraded")
    ok("F3", "EXACT", both == {0, 1}, sorted(both), "{0,1}",
       "both bilinear triangles are exercised")

    # ---- 1. build all three sides ----------------------------------------
    rc, out = build_lino()
    ok("B0", "EXACT", rc == 0, "lino build rc=%d" % rc, "0", out.strip()[:160])
    if rc != 0:
        return _report(checks, a.json)
    rc, out = build_cref()
    ok("B1", "EXACT", rc == 0, "gcc build rc=%d" % rc, "0", out.strip()[:160])
    if rc != 0:
        return _report(checks, a.json)

    lblob, lnote = run_lino()
    ok("R0", "EXACT", lblob is not None, "lino ran",
       "no grv-out.bin", (lnote or "")[:160])
    if lblob is None:
        return _report(checks, a.json)
    cblob = run_cref()
    ok("R1", "EXACT", cblob is not None, "cref ran", "no grv_ref.bin", "")
    if cblob is None:
        return _report(checks, a.json)

    # spec
    sys.path.insert(0, HERE)
    import grv_spec
    spec = [grv_spec.hpoint_bits(px, pz, s1, s2, s3, s4)
            for px, pz, s1, s2, s3, s4 in rows]

    L = bits_list(lblob)
    C = bits_list(cblob)
    n = min(len(L), len(C), len(spec), len(rows))
    ok("N0", "EXACT", len(L) == len(rows) == len(C) == len(spec),
       (len(L), len(C), len(spec), len(rows)), "all equal",
       "all three sides produced one record per corpus row")

    # ---- 2. the three pairwise exact comparisons -------------------------
    def cmp(cid, claim, a_list, b_list, who):
        bad = [(i, a_list[i], b_list[i]) for i in range(n)
               if a_list[i] != b_list[i]]
        ok(cid, claim, not bad, "%d/%d agree" % (n - len(bad), n),
           "0 mismatches",
           "%s: first mismatch %s" % (who, bad[:1]) if bad else
           "%s: %d cases byte-exact" % (who, n))

    cmp("E1", "EXACT", L, C, "lino vs cref")
    cmp("E2", "EXACT", L, spec, "lino vs spec")
    cmp("E3", "EXACT", C, spec, "cref vs spec  (the float-model witness)")

    # ---- 3. branch-stratified coverage of the exact claim ----------------
    # A defect in only one triangle must still fail E1/E2/E3; verify each
    # branch contributes cases so neither side is vacuously agreeable.
    for br, name in ((0, "upper"), (1, "lower")):
        idx = [i for i in range(n) if branch_of(*rows[i][:2]) == br]
        ok("COV%d" % br, "EXACT", len(idx) > 0, len(idx), ">0 cases",
           "%s triangle has %d cases" % (name, len(idx)))

    return _report(checks, a.json)


def _report(checks, as_json):
    bad = [c for c in checks if not c["ok"]]
    for c in checks:
        tag = "ok " if c["ok"] else "FAIL"
        print("%-4s %-8s %-22s got=%-20s want=%-14s %s" %
              (tag, c["check"], c["claim"], c["got"][:20], c["want"][:14],
               c["note"][:70]))
    print("\n%d checks, %d failing" % (len(checks), len(bad)))
    if as_json:
        print(json.dumps(checks, indent=1))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
