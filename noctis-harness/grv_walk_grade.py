r"""grv_walk_grade.py - Wave 7b iperificie grid-walk three-way grader.

Grades the iperificie paint-order traversal (NOCTIS-1.CPP:1393-1471) three
ways on the call sequence (the ordered (x,z) fragment calls, packed x|z<<16):

  spec  grv_walk_spec.py           Python, verbatim transliteration
  cref  grv_walk_ref.exe           C, separate verbatim pass
  lino  work/walkgrid.exe          the L.in.oleum port, rebuilt every run

All three consume grv-walk-corpus.txt (ipfx ipfz beta add per case).  The
sequence is EXACT: pure integer loop logic, no float tolerance.  Then a
sabotage loop applies one-line edits to walkgrid.txt, rebuilds, and requires
each to diverge - a check with no demonstrated falsifier is a claim.

The corpus keeps loop bounds non-negative (ipfx,ipfz in 50..150, add in 0..40)
so lino's unsigned '-comparisons agree with signed for the loop bounds; the
beta<0 normalize uses a sign-bit test.  The negative-bound path (walker at the
grid edge) is out of scope.

Usage:  python grv_walk_grade.py
"""

import os
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
WG_SRC = os.path.join(REPO, "work", "walkgrid.txt")
WG_EXE = os.path.join(REPO, "work", "walkgrid.exe")
LINO_OUT = os.path.join(REPO, "work", "grv-walk.bin")
CORPUS = os.path.join(HERE, "grv-walk-corpus.txt")
CREF_SRC = os.path.join(HERE, "grv_walk_ref.c")
CREF_EXE = os.path.join(HERE, "grv_walk_ref.exe")
CREF_BIN = os.path.join(HERE, "grv_walk_ref.bin")
BUILD_PS1 = os.path.join(REPO, "lino_build.ps1")
RUN_PS1 = os.path.join(REPO, "tests", "w7arun.ps1")

sys.path.insert(0, HERE)
import grv_walk_spec  # noqa


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", **kw)


def spec_blob():
    out = b""
    with open(CORPUS, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            s = line.strip()
            if not s or s[0] == "#":
                continue
            ipfx, ipfz, beta, add = map(int, s.split())
            rec = grv_walk_spec.pack_sequence(ipfx, ipfz, beta, add)
            out += struct.pack("<%di" % len(rec), *rec)
    return out


def build_lino(src=WG_SRC):
    exe = os.path.splitext(src)[0] + ".exe"
    if os.path.exists(exe):
        os.remove(exe)
    p = run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
             BUILD_PS1, "-Src", src, "-TimeoutSec", "240"])
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def run_lino(exe, out):
    if os.path.exists(out):
        os.remove(out)
    shutil.copy(CORPUS, os.path.join(os.path.dirname(exe), "grv-walk-corpus.txt"))
    p = run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
             RUN_PS1, "-Exe", exe, "-Out", out, "-TimeoutSec", "240"])
    if p.returncode != 0 or not os.path.exists(out):
        return None
    with open(out, "rb") as fh:
        return fh.read()


def build_cref():
    p = run(["gcc", "-O2", "-o", CREF_EXE, CREF_SRC])
    return p.returncode


def run_cref():
    p = run([CREF_EXE, CORPUS, CREF_BIN])
    if p.returncode != 0 or not os.path.exists(CREF_BIN):
        return None
    with open(CREF_BIN, "rb") as fh:
        return fh.read()


def main():
    checks = []

    def ok(cid, cond, got, want, note=""):
        checks.append((cid, cond, got, want, note))
        return cond

    ok("F0", os.path.exists(CORPUS), "present", "missing", "corpus")
    with open(CORPUS) as fh:
        n = sum(1 for l in fh if l.strip() and l.strip()[0] in "-0123456789")
    ok("F1", n >= 20, "%d cases" % n, ">=20", "covers all quadrants + boundaries")

    rc, out = build_lino()
    ok("B0", rc == 0, "lino rc=%d" % rc, "0", out.strip()[:120])
    ok("B1", build_cref() == 0, "gcc rc", "0", "")

    lblob = run_lino(WG_EXE, LINO_OUT)
    ok("R0", lblob is not None, "lino ran", "no out", "")
    cblob = run_cref()
    ok("R1", cblob is not None, "cref ran", "no out", "")
    sblob = spec_blob()

    if lblob and cblob:
        ok("N0", len(lblob) == len(cblob) == len(sblob),
           (len(lblob), len(cblob), len(sblob)), "all equal", "")
        ok("E1", lblob == cblob, "%d bytes" % len(lblob), "byte-exact",
           "lino vs cref")
        ok("E2", lblob == sblob, "%d bytes" % len(lblob), "byte-exact",
           "lino vs spec")
        ok("E3", cblob == sblob, "%d bytes" % len(cblob), "byte-exact",
           "cref vs spec (the two-readings witness)")
        # quadrant coverage: at least one case per quadrant fired calls
        nq = 0
        with open(CORPUS) as fh:
            for line in fh:
                s = line.strip()
                if not s or s[0] == "#":
                    continue
                ipfx, ipfz, beta, add = map(int, s.split())
                if len(grv_walk_spec.iperificie_calls(ipfx, ipfz, beta, add)) > 0:
                    nq += 1
        ok("COV", nq >= 4, "%d non-empty cases" % nq, ">=4", "all quadrants")

    # ---- sabotage ----
    print("\n-- sabotage (one-line defects, rebuilt and required to diverge) --")
    MUTS = [
        ("Q1ZFLIP",
         "[IGz] = WGRIGHT;\n    \"IG Q1 z\"",
         "[IGz] = WGLEFT;\n    \"IG Q1 z\"",
         "Q1 z walks 0->up instead of 199->down (near tiles paint before far)"),
        ("XSKIP2",
         "[IGx] = WGRIGHT;\n    \"IG Q1 xb loop\"",
         "end;\n    \"IG Q1 xb loop\"",
         "drop Q1's second x-pass (x=199..ipfx): half the columns vanish"),
        ("IPFXFIX",
         "A = [IGipfz]; A - [IGadd]; [IGbound] = A;\t( bug: ipfz )",
         "A = [IGipfx]; A - [IGadd]; [IGbound] = A;\t( bug: ipfz )",
         "'fix' the source's ipfz->ipfx bug at Q4's x-bound - diverges because "
         "the spec reproduces the bug verbatim (iprognosticated)"),
        ("BETAUNSIG",
         "A = [IGb]; A > 31; ? A = 0 -> IG bpos;",
         "A = [IGb]; ? A '>= 0 -> IG bpos;",
         "use UNSIGNED '>=0' for the beta<0 normalize - beta in [-359,-1] "
         "no longer adds 360, so the quadrant checks misroute"),
    ]
    sab_ok = True
    for name, old, new, why in MUTS:
        tmp = tempfile.mkdtemp(prefix="grvwbrk_")
        src = os.path.join(tmp, "walkgrid.txt")
        shutil.copy(WG_SRC, src)
        shutil.copytree(os.path.join(REPO, "work", "fp"), os.path.join(tmp, "fp"))
        txt = open(src, encoding="utf-8").read()
        if old not in txt:
            print("  %-10s ANCHOR NOT FOUND: %s" % (name, why)); sab_ok = False
            shutil.rmtree(tmp, ignore_errors=True); continue
        open(src, "w", encoding="utf-8").write(txt.replace(old, new, 1))
        rc, _ = build_lino(src)
        exe = os.path.splitext(src)[0] + ".exe"
        out = os.path.join(tmp, "grv-walk.bin")
        blob = run_lino(exe, out) if rc == 0 else None
        diverges = blob is not None and blob != sblob
        ok("S:" + name, diverges, "diverges" if diverges else "NO DIFF",
           "diverge from spec", why)
        if not diverges:
            sab_ok = False
        shutil.rmtree(tmp, ignore_errors=True)

    bad = [c for c, cond, *_ in checks if not cond]
    for cid, cond, got, want, note in checks:
        print("%-4s %-10s %-30s want=%s" % ("ok " if cond else "FAIL", cid, got[:30], want))
    print("\n%d checks, %d failing" % (len(checks), len(bad)))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
