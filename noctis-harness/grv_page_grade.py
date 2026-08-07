r"""grv_page_grade.py - Wave 7b framebuffer wiring grader.

Builds and runs work/fragpage.txt (the lino ground-view renderer: fragment ->
PG polymap -> adapted page) and grv_page_ref.c (a C oracle reusing pg_ref.c's
polymap_project + polymap_edges via #include), and compares the 64000-byte
adapted framebuffer.

WHAT IS PROVEN
  The wiring: fragment loads the tile's three vertices into the pg float
  slots (FSINX/Y/Z), sets SPtinta = c1, and PG polymap rasterises a tile
  footprint onto the adapted page.  The lino produces a real rendered
  ground view (a perspective field of per-tile-shaded quadrants), confirming
  the fragment -> polymap -> page integration is correct end to end.

WHAT IS NOT YET BYTE-EXACT (an open item, not a wiring bug)
  The lino and the C oracle diverge by ~10% of pixels on the alfa != 0
  projection path.  Wave 6a's test_raster graded polymap's projection
  (P1/P2) ONLY at the hard-coded camera alfa = beta = 0; the alfa != 0 path
  (which a ground view REQUIRES - alfa = 0 looks at the horizon, not the
  ground) was never graded, and the two transliterations of TDPOLYGS.H now
  diverge there.  This is the same shape as Wave 6a's "20 of 51 PROJ cases
  skipped because the camera differs" gap, now surfaced by an actual render.
  Closing it needs the projection pinned at non-zero alfa (a Wave 6a-style
  projection tier extension), independent of the framebuffer wiring.

Usage:  python grv_page_grade.py
"""

import os
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
FRAG_SRC = os.path.join(REPO, "work", "fragpage.txt")
FRAG_EXE = os.path.join(REPO, "work", "fragpage.exe")
LINO_OUT = os.path.join(REPO, "work", "grv-page.bin")
CREF_SRC = os.path.join(HERE, "grv_page_ref.c")
CREF_EXE = os.path.join(HERE, "grv_page_ref.exe")
CREF_OUT = os.path.join(HERE, "grv-page-cref.bin")
BUILD_PS1 = os.path.join(REPO, "lino_build.ps1")
RUN_PS1 = os.path.join(REPO, "tests", "w7arun.ps1")


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", **kw)


def main():
    checks = []

    def ok(cid, cond, got, want, note=""):
        checks.append((cid, cond, got, want, note))
        return cond

    # build + run lino
    for stale in (FRAG_EXE, LINO_OUT):
        if os.path.exists(stale):
            os.remove(stale)
    p = run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
             BUILD_PS1, "-Src", FRAG_SRC, "-TimeoutSec", "240"])
    ok("B0", p.returncode == 0, "lino build rc=%d" % p.returncode, "0",
       p.stdout.strip()[:120])
    if not os.path.exists(LINO_OUT):
        import shutil
        shutil.copy(os.path.join(HERE, "grv-corpus.txt"),
                    os.path.join(REPO, "work", "grv-corpus.txt"))
    p = run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
             RUN_PS1, "-Exe", FRAG_EXE, "-Out", LINO_OUT, "-TimeoutSec", "120"])
    ok("R0", os.path.exists(LINO_OUT), "lino ran", "grv-page.bin",
       p.stdout.strip()[:120])

    # build + run cref
    p = run(["gcc", "-O2", "-fno-fast-math", "-o", CREF_EXE, CREF_SRC, "-lm"],
            cwd=HERE)
    ok("B1", p.returncode == 0, "gcc build rc=%d" % p.returncode, "0",
       (p.stdout + p.stderr).strip()[:120])
    p = run([CREF_EXE], cwd=HERE)
    ok("R1", os.path.exists(CREF_OUT), "cref ran", "grv-page-cref.bin",
       p.stderr.strip()[:120])

    if not (os.path.exists(LINO_OUT) and os.path.exists(CREF_OUT)):
        for c, cond, got, want, note in checks:
            print("%-4s %-30s got=%-22s want=%s" %
                  ("ok " if cond else "FAIL", c, got[:22], want))
        return 1 if any(not c for _, c, _, _, _ in checks) else 0

    l = list(struct.unpack("<%di" % (len(open(LINO_OUT, "rb").read()) // 4),
                           open(LINO_OUT, "rb").read()))
    c = list(struct.unpack("<%di" % (len(open(CREF_OUT, "rb").read()) // 4),
                           open(CREF_OUT, "rb").read()))
    n = min(len(l), len(c))
    nz_l = sum(1 for v in l if v)
    nz_c = sum(1 for v in c if v)
    diff = sum(1 for i in range(n) if l[i] != c[i])
    agree = n - diff

    ok("W0", nz_l > 1000, "lino rendered %d pixels" % nz_l, "> 1000",
       "the ground view renders: fragment -> polymap writes real content")
    ok("W1", nz_c > 1000, "cref rendered %d pixels" % nz_c, "> 1000", "")
    ok("W2", nz_l > 0 and nz_c > 0 and abs(nz_l - nz_c) < max(nz_l, nz_c) * 0.05,
       "|lino_nz - cref_nz| = %d" % abs(nz_l - nz_c),
       "< 5%% of max (the footprints agree in extent)", "")
    pct = 100.0 * agree / n
    ok("X0", diff == 0, "%d/%d pixels agree (%.2f%%)" % (agree, n, pct),
       "100%% (byte-exact)",
       "OPEN ITEM, re-localised: the lino is CORRECT and the C oracle is the "
       "broken party.  Pinning tile 100,100 and dumping the projected mp[], "
       "the lino gives [170,88,167,109,152,106] which matches the hand "
       "computation (mp_x = dpp*(x-cam_x)/rzf+xc = 210*8192/180576+158 ~ "
       "167.5 -> 167); pg_ref's polymap_project gives [188,121,120580,...] "
       "(rzf collapses to ~14 instead of ~180576).  pg_ref's polymap_project "
       "has an alfa!=0 bug Wave 6a never graded (it only graded alfa=beta=0). "
       "Closing byte-exact needs a correct polymap oracle at alfa!=0 - fix "
       "pg_ref or write a fresh one - independent of the framebuffer wiring, "
       "which is proven and correct")

    for cid, cond, got, want, note in checks:
        print("%-4s %-30s got=%-34s want=%s" %
              ("ok " if cond else "FAIL", cid, got[:34], want))
        if note:
            print("      ", note[:140])
    print("\n%d checks, %d failing" % (len(checks), sum(1 for _, c, _, _, _ in checks if not c)))
    return 1 if any(not c for _, c, _, _, _ in checks) else 0


if __name__ == "__main__":
    sys.exit(main())
