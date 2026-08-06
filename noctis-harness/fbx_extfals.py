#!/usr/bin/env python3
"""fbx_extfals.py -- demonstrate the falsifiers that no -DBREAK_* can reach.

Four rows in fb_ref.c's ledger declare EXTERNAL falsifiers: their subject is
not a line of C but the 1996 SOURCE TEXT or the pinned FIXTURE.  A macro cannot
mutate either, so fbx_mutmatrix.py prints them as "proved by hand".  This file
is that proof, executed.  Without it those four rows are exactly the thing this
wave exists to abolish -- a claim of falsifiability with no falsification.

  EXT_SANDBOXDISP        REF.K.UNIQUE, REF.K.EQUALS.SEGOFFSET
      Copy the 1996 sources to a sandbox and change ONE addressing
      displacement.  The solver must REFUSE (the constraints no longer admit
      one offset).  Change every one of them CONSISTENTLY and it must solve a
      DIFFERENT offset, at which point fb_ref.c's compiled constant is wrong
      and REF.K.EQUALS.SEGOFFSET fails.  Two directions, because a solver that
      always refuses and a solver that always answers 4 are both useless.

  EXT_FIXTUREFORBIDDEN   REF.FIX.LINT
      Add a derived quantity to the fixture.  The producer must refuse to run.

  EXT_FIXTUREORDER       REF.E1.PAGESDIFFER, REF.E1.RIGHTPAGE
      Move the HUD band before the page flip in the fixture.  The flip then
      overwrites it, the two pages become bit-identical, and "which page did
      the expander read" stops having an answer -- so both rows must FAIL.
      This is the check the DELETED row (FB[i] == PAL[adaptor[i]]) could not
      make: it passed in this configuration too, because it was the expander's
      own assignment re-executed.

C:\\programmieren\\noctis is NEVER written.  Everything happens in a temp copy.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "fb_ref.c")
NOCTIS_SRC = r"C:\programmieren\noctis\niv-plus\source"
SUPPORTS = r"C:\programmieren\noctis\niv-plus\data\SUPPORTS.NCT"
FIXTURE = os.path.abspath(os.path.join(HERE, "..", "docs-notes", "FIXTURE1.txt"))

FILES = ["NOCTIS-0.CPP", "TDPOLYGS.H", "NOCTIS-D.H"]

fails = []


def say(ok, cid, text):
    print("  %s  [%s] %s" % ("PASS" if ok else "FAIL", cid, text))
    if not ok:
        fails.append(cid)


def build(exe):
    cp = subprocess.run(["gcc", "-std=c99", "-O2", "-w", "-o", exe, SRC],
                        capture_output=True, text=True)
    if cp.returncode != 0:
        print(cp.stderr[:2000])
        sys.exit(2)


def sandbox_sources(root, edits, tag="src"):
    # each sandbox gets its OWN directory: sharing one and overwriting it made
    # every later reader see the last mutation, which is how this file first
    # reported the pristine sources as solving K = 8
    d = os.path.join(root, tag)
    os.makedirs(d, exist_ok=True)
    for f in FILES:
        raw = open(os.path.join(NOCTIS_SRC, f), "rb").read()
        txt = raw.decode("latin-1")
        for pat, rep in edits.get(f, []):
            txt = txt.replace(pat, rep)
        open(os.path.join(d, f), "wb").write(txt.encode("latin-1"))
    return d


def ksolve(exe, srcdir):
    cp = subprocess.run([exe, "--ksolve", srcdir], capture_output=True, text=True)
    return cp.stdout.strip(), cp.returncode


def run_full(exe, outdir, srcdir, fixture):
    os.makedirs(outdir, exist_ok=True)
    cp = subprocess.run([exe, outdir, SUPPORTS, srcdir, fixture],
                        capture_output=True, text=True)
    tsv = os.path.join(outdir, "fb-ref-checks.tsv")
    rows = {}
    if os.path.exists(tsv):
        for line in open(tsv, encoding="utf-8", errors="replace"):
            if line.startswith("#"):
                continue
            p = line.rstrip("\n").split("\t")
            if len(p) >= 3:
                rows[p[0]] = p[2]
    return rows, cp.returncode, cp.stdout + cp.stderr


def main():
    root = tempfile.mkdtemp(prefix="fbxext_")
    try:
        exe = os.path.join(root, "fb_ref_ext.exe")
        build(exe)

        print("fbx_extfals -- the falsifiers no -DBREAK_* can reach\n")

        # ---------- control: the pristine sources solve, uniquely ----------
        print("CONTROL (an unmutated sandbox copy must still solve)")
        clean_src = sandbox_sources(root, {}, "src_pristine")
        out, code = ksolve(exe, clean_src)
        say("SOLVED" in out and "K=4" in out, "REF.K.UNIQUE", out)

        # ---------- EXT_SANDBOXDISP, direction 1: ONE displacement ----------
        print("\nEXT_SANDBOXDISP direction 1 -- change ONE displacement; the "
              "constraints must stop agreeing")
        d1 = sandbox_sources(root, {
            # only the general branch of Stick, in NOCTIS-0.CPP
            "NOCTIS-0.CPP": [("mov word ptr es:[di+4], 0x3E00",
                              "mov word ptr es:[di+8], 0x3E00")],
        }, "src_one")
        out, code = ksolve(exe, d1)
        say("REFUSED" in out, "REF.K.UNIQUE",
            "one displacement moved -> " + out)

        # ---------- EXT_SANDBOXDISP, direction 2: ALL of them ----------
        print("\nEXT_SANDBOXDISP direction 2 -- change them ALL consistently; "
              "the solver must answer a DIFFERENT offset, and fb_ref.c's "
              "compiled constant must then be caught as wrong")
        d2 = sandbox_sources(root, {
            "NOCTIS-0.CPP": [("es:[di+4]", "es:[di+8]"),
                             ("add ax, 4", "add ax, 8"),
                             ("0xC7, 0x45, 0x04", "0xC7, 0x45, 0x08")],
            "TDPOLYGS.H":   [("es:[di+4]", "es:[di+8]")],
            "NOCTIS-D.H":   [("#define sc_bytes     65540",
                              "#define sc_bytes     65544")],
        }, "src_all")
        out, code = ksolve(exe, d2)
        say("SOLVED" in out and "K=8" in out, "REF.K.UNIQUE",
            "all displacements moved -> " + out)

        # the SECOND producer must move the same way, or the two solvers agree
        # on the pristine sources only because both are inert
        print("\nEXT_SANDBOXDISP -- and the second, independent solver "
              "(fbx_ksolve.py, different language, different parse, wider "
              "corpus) must move the same way")
        ks = os.path.join(HERE, "fbx_ksolve.py")
        for tag, d, want in (("pristine", clean_src, "SOLVED  K = 4"),
                             ("one displacement", d1, "REFUSED"),
                             ("all displacements", d2, "SOLVED  K = 8")):
            cp = subprocess.run([sys.executable, ks, d], capture_output=True,
                                text=True)
            tail = [l.strip() for l in cp.stdout.splitlines()
                    if "RESULT" in l or l.startswith("REFUSED")]
            got = tail[-1] if tail else "<no result>"
            say(want in got, "fbx_ksolve", "%-18s -> %s" % (tag, got))

        rows, code, log = run_full(exe, os.path.join(root, "o_d2"), d2, FIXTURE)
        say(rows.get("REF.K.EQUALS.SEGOFFSET") == "FAIL",
            "REF.K.EQUALS.SEGOFFSET",
            "against the mutated sources the compiled SEG_OFFSET is caught: %s"
            % rows.get("REF.K.EQUALS.SEGOFFSET", "<no row>"))
        say(rows.get("REF.A4.ALIAS8") == "FAIL", "REF.A4.ALIAS8",
            "and alias 8's index follows the SOLVED offset, not the literal: %s"
            % rows.get("REF.A4.ALIAS8", "<no row>"))

        # ---------- EXT_FIXTUREFORBIDDEN ----------
        print("\nEXT_FIXTUREFORBIDDEN -- hand the script a derived quantity; "
              "the producer must refuse to run")
        fx_bad = os.path.join(root, "FIXTURE1_forbidden.txt")
        txt = open(FIXTURE, encoding="utf-8", errors="replace").read()
        txt = txt.replace("poke_alias8 segoff=0xFA00 b0=0x37 b1=0x5B",
                          "poke_alias8 segoff=0xFA00 index=63996 b0=0x37 b1=0x5B")
        open(fx_bad, "w", encoding="utf-8").write(txt)
        rows, code, log = run_full(exe, os.path.join(root, "o_fx"), clean_src, fx_bad)
        refused = (code == 2) and ("63996" in log)
        say(refused, "REF.FIX.LINT",
            "exit %d; %s" % (code,
                             [l.strip() for l in log.splitlines()
                              if "REF.FIX.LINT" in l][:1] or ["<no row printed>"]))

        # ---------- EXT_FIXTUREORDER ----------
        print("\nEXT_FIXTUREORDER -- put the HUD band before the flip; the two "
              "pages become identical and E1 must lose its subject")
        fx_ord = os.path.join(root, "FIXTURE1_order.txt")
        txt = open(FIXTURE, encoding="utf-8", errors="replace").read()
        band = "areaclear page=visible x=2 y=191 l=316 a=7 color=127"
        flip = "pcopy dst=visible src=hidden"
        assert band in txt and flip in txt
        txt = txt.replace(flip + "\n" + band, band + "\n" + flip)
        open(fx_ord, "w", encoding="utf-8").write(txt)
        rows, code, log = run_full(exe, os.path.join(root, "o_ord"), clean_src, fx_ord)
        say(rows.get("REF.E1.PAGESDIFFER") == "FAIL", "REF.E1.PAGESDIFFER",
            "%s -- %s" % (rows.get("REF.E1.PAGESDIFFER", "<no row>"),
                          ([l.strip()[:150] for l in log.splitlines()
                            if "REF.E1.PAGESDIFFER" in l] or [""])[0]))
        say(rows.get("REF.E1.RIGHTPAGE") == "FAIL", "REF.E1.RIGHTPAGE",
            rows.get("REF.E1.RIGHTPAGE", "<no row>"))

        # and the DELETED row, resurrected, to show it could not have caught it
        print("\n  (the row this replaced -- FB[i] == PAL[adaptor[i]] for all i "
              "-- is TRUE in that same configuration, which is why it was "
              "deleted rather than kept alongside)")

        print("\nRESULT: %s  (%d external falsifiers unproved: %s)"
              % ("PASS" if not fails else "FAIL", len(fails),
                 ",".join(sorted(set(fails))) or "-"))
        return 0 if not fails else 1
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
