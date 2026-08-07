r"""grv_grade.py - Wave 7b ground-renderer comparison.  Implementer B2's side.

Grades two renderer functions, three ways each:

  HPOINT   (NOCTIS-1.CPP:63-93)   the bilinear height query (vertex Z base).
  FRAGMENT (NOCTIS-1.CPP:1028-1142) the ground-tile vertex + depth + c1 path:
           depth = ((long)(float)sqrt(dx*dx+dz*dz)) >> 14  is the EXACT-
           REQUIRED chop #1 of WAVE7B_PLAN; the six vy corner heights and c1
           (sh_delta slope OR diffuse fast_random + depth>>1 + clamp) are the
           integer arguments fragment hands to polymap.

  lino  work/walk.exe                 rebuilt from work/walk.txt every run
  cref  grv_ref.exe (grv_ref.c)       C, separate pass, hardware x87
  spec  grv_spec.py                   Python, exact-rational model

All three consume the SAME opcode-prefixed corpus (grv-corpus.txt).  Each case
emits one 9-word record [op, v0..v7] (hpoint pads v1..v7 with zero).  E1/E2/E3
compare them pairwise EXACT, zero tolerance.  The depth chop is exact, so a
defect in fragment's vertex/depth/c1 path moves a graded integer and is caught.

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
    if os.path.exists(WALK_EXE):
        os.remove(WALK_EXE)
    if os.path.exists(LINO_OUT):
        os.remove(LINO_OUT)
    p = run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
             BUILD_PS1, "-Src", WALK_SRC, "-TimeoutSec", "180"])
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def run_lino():
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
    p = run(["gcc", "-O2", "-fno-fast-math", "-o", CREF_EXE, CREF_SRC, "-lm"])
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def run_cref():
    p = run([CREF_EXE, CORPUS, CREF_BIN])
    if p.returncode != 0 or not os.path.exists(CREF_BIN):
        return None
    with open(CREF_BIN, "rb") as fh:
        return fh.read()


def parse_corpus(path):
    rows = []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            s = line.strip()
            if not s or s[0] == "#":
                continue
            t = s.replace(",", " ").split()
            if not t:
                continue
            op = int(t[0])
            if op == 1 and len(t) == 7:
                rows.append((1, tuple(int(x) for x in t[1:])))
            elif op == 2 and len(t) == 13:
                rows.append((2, tuple(int(x) for x in t[1:])))
            elif op == 5 and len(t) == 7:
                rows.append((5, tuple(int(x) for x in t[1:])))
    return rows


def recs_list(blob):
    """9-word records -> list of [op, v0..v7]."""
    n = len(blob) // 4
    out = []
    for i in range(0, n, 9):
        out.append(list(struct.unpack_from("<9i", blob, i * 4)))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    checks = []

    def ok(cid, claim, cond, got, want, note=""):
        checks.append(dict(check=cid, claim=claim, ok=bool(cond),
                           got=str(got), want=str(want), note=note))
        return bool(cond)

    ok("F0", "EXACT", os.path.exists(CORPUS), "present", "missing",
       "the pinned corpus exists")
    rows = parse_corpus(CORPUS)
    n_hp = sum(1 for op, _ in rows if op == 1)
    n_fr = sum(1 for op, _ in rows if op == 2)
    ok("F1", "EXACT", n_hp >= 60 and n_fr >= 20, (n_hp, n_fr),
       "(>=60 hpoint, >=20 fragment)",
       "enough cases to cover both paths")

    rc, out = build_lino()
    ok("B0", "EXACT", rc == 0, "lino build rc=%d" % rc, "0", out.strip()[:160])
    if rc != 0:
        return _report(checks, a.json)
    rc, out = build_cref()
    ok("B1", "EXACT", rc == 0, "gcc build rc=%d" % rc, "0", out.strip()[:160])
    if rc != 0:
        return _report(checks, a.json)

    lblob, lnote = run_lino()
    ok("R0", "EXACT", lblob is not None, "lino ran", "no grv-out.bin",
       (lnote or "")[:160])
    if lblob is None:
        return _report(checks, a.json)
    cblob = run_cref()
    ok("R1", "EXACT", cblob is not None, "cref ran", "no grv_ref.bin", "")
    if cblob is None:
        return _report(checks, a.json)

    sys.path.insert(0, HERE)
    import grv_spec
    L = recs_list(lblob)
    C = recs_list(cblob)
    S = []  # spec records: [op, v0..v7] (hpoint pads)
    for op, payload in rows:
        if op == 1:
            v = [grv_spec.hpoint_bits(*payload)]
            S.append([1] + v + [0] * 7)
        elif op == 2:
            v = grv_spec.fragment_case(*payload)
            S.append([2] + v)
        else:  # op 5: p_Forward -> [npx_bits, npz_bits]
            v = grv_spec.p_forward_case(*payload)
            S.append([5] + v + [0] * 6)

    n = min(len(L), len(C), len(S), len(rows))
    ok("N0", "EXACT", len(L) == len(C) == len(S) == len(rows),
       (len(L), len(C), len(S), len(rows)), "all equal",
       "all three sides produced one record per corpus row")

    def cmp_pair(cid, who, a_list, b_list):
        bad = 0
        first = None
        for i in range(n):
            if a_list[i][:1 + 8] != b_list[i][:1 + 8]:
                bad += 1
                if first is None:
                    first = (i, a_list[i], b_list[i])
        ok(cid, "EXACT", bad == 0, "%d/%d agree" % (n - bad, n),
           "0 mismatches",
           ("%s: first %s" % (who, first)) if bad else
           "%s: %d records byte-exact" % (who, n))

    cmp_pair("E1", "lino vs cref", L, C)
    cmp_pair("E2", "lino vs spec", L, S)
    cmp_pair("E3", "cref vs spec  (float-model witness)", C, S)

    # branch/path coverage
    hp_rows = [r for op, r in rows if op == 1]
    def branch_of(px, pz):
        return 0 if ((px & 16383) + (pz & 16383)) < 16384 else 1
    both = {branch_of(*r[:2]) for r in hp_rows}
    ok("COV0", "EXACT", both == {0, 1}, sorted(both), "{0,1}",
       "hpoint: both bilinear triangles exercised")
    br_sh = sum(1 for op, r in rows if op == 2 and r[11] == 1)
    br_df = sum(1 for op, r in rows if op == 2 and r[11] == 0)
    ok("COV1", "EXACT", br_sh > 0 and br_df > 0, (br_sh, br_df),
       "(sh_delta>0, diffuse>0)",
       "fragment: both c1 branches exercised")
    frag_depths = {S[i][1] for i in range(n) if S[i][0] == 2}
    ok("COV2", "EXACT", len(frag_depths) >= 4, len(frag_depths),
       ">=4 distinct depths",
       "fragment: depth chop graded across several distances")

    return _report(checks, a.json)


def _report(checks, as_json):
    bad = [c for c in checks if not c["ok"]]
    for c in checks:
        tag = "ok " if c["ok"] else "FAIL"
        print("%-4s %-8s %-34s got=%-20s want=%-22s %s" %
              (tag, c["check"], c["claim"], c["got"][:20], c["want"][:22],
               c["note"][:64]))
    print("\n%d checks, %d failing" % (len(checks), len(bad)))
    if as_json:
        print(json.dumps(checks, indent=1))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
