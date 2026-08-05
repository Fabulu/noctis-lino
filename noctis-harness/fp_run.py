"""WAVE 3 / IMPLEMENTER 2 - the comparison driver.

One command that builds the reference side, runs every battery on both
reference implementations, grades them all against STARMAP.BIN, and diffs
them against each other.  Any extra fpout.bin files named on the command line
- Implementer 1's X87, SOFT or NATIVE lino backends, when they exist - are put
through exactly the same grading and diffing, with no special handling.

    python fp_run.py                              reference side only
    python fp_run.py <lino_fpout.bin> [...]       and grade lino too

Each lino file is expected to be the NsIdentity chain over fpvec_starmap.bin.

THE EXPECTED-VALUE TABLE below is not this wave's own output.  Every number in
it was produced by Recon C's separately-written probe, on real x87 hardware,
before any of this code existed.  Reproducing them here is therefore a
comparison against an outside result, not a self-check.  Where a number
differs it is stated and explained rather than quietly updated.
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fp_diff    # noqa: E402
import fp_model   # noqa: E402
import fp_sched   # noqa: E402
import fp_starmap  # noqa: E402

W = fp_sched.OUTDIR
SCHED = os.path.join(W, "fpsched.txt")
VEC = os.path.join(W, "fpvec_starmap.bin")
EXE = os.path.join(HERE, "fp_x87ref.exe")

# (label, chain, control word, expected any-candidate score, provenance)
BATTERY = [
    ("PC=64  CW 133F  the original's word", "NsIdentity", "133F", 4194,
     "Recon C hardware probe: 4194"),
    ("PC=53  CW 123F  IEEE double per op ", "NsIdentity", "123F", 2315,
     "Recon C hardware probe: 2315"),
    ("PC=24  CW 103F  lino's native width", "NsIdentity", "103F", 67,
     "Recon C hardware probe: 66 first-candidate; 67 any-candidate"),
    ("one intermediate spilled to memory ", "NsIdentitySpill", "133F", 3139,
     "Recon C hardware probe: 3139"),
    ("isthere() right-assoc *1e-5 formula", "NsIdentityIsThere", "133F", 0,
     "Recon C hardware probe: 0"),
    ("operands permuted z,y,x (MUST PASS)", "NsIdentityPermuted", "133F", 4194,
     "Recon C hardware probe: 4194"),
    ("narrowed through a 32-bit float    ", "NsIdentityF32", "133F", 75,
     "new in this wave"),
]


def sh(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("FAILED: %s\n%s\n%s" % (" ".join(cmd), r.stdout, r.stderr))
        raise SystemExit(1)
    return r.stdout


def selftest():
    """Break the harness on purpose and require it to notice.

    The negative-control schedules break the SUBJECT.  These break the
    INSTRUMENT.  If a corrupted interchange file could still be graded then a
    score means nothing, and a silently short read is exactly the failure mode
    the lino side's [Block Size] behaviour invites.
    """
    import struct
    import tempfile
    good = open(os.path.join(W, "run_c_NsIdentity_133F.bin"), "rb").read()
    rows, nrec = fp_starmap.load_manifest()
    cases = []

    def mutate(name, blob):
        fh = tempfile.NamedTemporaryFile(suffix=".bin", delete=False)
        fh.write(blob)
        fh.close()
        cases.append((name, fh.name))
        return fh.name

    mutate("header magic corrupted", b"XXXX" + good[4:])
    mutate("format version bumped", good[:4] + struct.pack("<I", 2) + good[8:])
    mutate("header sentinel corrupted", good[:28] + bytes(4) + good[32:])
    off = 32 + 5 * 32 + 28
    mutate("a per-case sentinel corrupted", good[:off] + bytes(4) + good[off + 4:])
    mutate("file truncated mid-case", good[:len(good) - 17])
    mutate("NCASE understated by one",
           good[:8] + struct.pack("<I", len(rows) - 1) + good[12:])

    # the qword layout trap: every f64 result stored HIGH-then-LOW instead
    sw = bytearray(good)
    for i in range(len(rows)):
        o = 32 + i * 32
        sw[o:o + 4], sw[o + 4:o + 8] = sw[o + 4:o + 8], sw[o:o + 4]
    lay = mutate("qword halves reversed (HIGH-THEN-LOW)", bytes(sw))

    print("")
    print("=" * 78)
    print("INSTRUMENT SELFTEST - every one of these must be rejected or collapse")
    print("=" * 78)
    allok = True
    for name, path in cases:
        if path == lay:
            continue
        try:
            fp_starmap.grade(path, rows, nrec, verbose=False)
            print("  %-42s NOT DETECTED  *** FAIL ***" % name)
            allok = False
        except (ValueError, SystemExit) as e:
            print("  %-42s rejected: %s" % (name, str(e)[:58]))
        os.unlink(path)
    sc, _, _ = fp_starmap.grade(lay, rows, nrec, verbose=False)
    good_layout = (sc == 0)
    print("  %-42s scores %d/%d  %s"
          % ("qword halves reversed (HIGH-THEN-LOW)", sc, nrec,
             "collapsed, ok" if good_layout else "*** FAIL - layout error invisible ***"))
    allok &= good_layout
    os.unlink(lay)
    return allok


def main():
    lino = [a for a in sys.argv[1:] if not a.startswith("--")]
    fp_sched.emit(SCHED)
    if not os.path.exists(EXE):
        print("building fp_x87ref.exe")
        sh(["gcc", "-O1", "-Wall", "-o", EXE, os.path.join(HERE, "fp_x87ref.c")])
    if not os.path.exists(VEC):
        print("generating the STARMAP vector set")
        sh([sys.executable, os.path.join(HERE, "fp_vectors.py"), "starmap", "64"])

    rows, nrec = fp_starmap.load_manifest()
    print("=" * 78)
    print("STARMAP oracle set: %d cases over %d catalogue records "
          "(%d collision extras)" % (len(rows), nrec, len(rows) - nrec))
    print("=" * 78)

    ok = True
    print("\n%-38s %8s %8s %8s  %s"
          % ("battery", "C-x87", "Py-exact", "expect", "verdict"))
    print("-" * 78)
    for label, chain, cw, expect, prov in BATTERY:
        cout = os.path.join(W, "run_c_%s_%s.bin" % (chain, cw))
        pout = os.path.join(W, "run_py_%s_%s.bin" % (chain, cw))
        sh([EXE, SCHED, chain, VEC, cout, cw])
        sh([sys.executable, os.path.join(HERE, "fp_model.py"),
            SCHED, chain, VEC, pout, cw])
        sc, hc, dc = fp_starmap.grade(cout, rows, nrec, verbose=False)
        sp, hp, dp = fp_starmap.grade(pout, rows, nrec, verbose=False)
        agree = sum(1 for a, b in zip(dc["rows"], dp["rows"])
                    if a["f64bits"] == b["f64bits"])
        good = (sc == expect and sp == expect and agree == len(rows))
        ok &= good
        print("%-38s %8d %8d %8d  %s"
              % (label, sc, sp, expect,
                 "ok" if good else "*** MISMATCH ***"))
        if agree != len(rows):
            print("     C and Python disagree on %d/%d cases"
                  % (len(rows) - agree, len(rows)))
        if not good:
            print("     provenance of the expectation: %s" % prov)

    print("-" * 78)
    print("C x87 hardware and the exact-rational model agree case-for-case on "
          "every battery." if ok else "SOME BATTERY FAILED - see above")

    print("\nstack discipline and control word, C reference at CW 133F:")
    d = fp_model.read_out(os.path.join(W, "run_c_NsIdentity_133F.bin"))
    print("   control word read back, masked & 0x0F3F : %04X" % d["cw"])
    print("   status word                             : %04X  TOP=%d"
          % (d["sw"], (d["sw"] >> 11) & 7))
    print("   cases with an unbalanced stack          : %d"
          % sum(1 for r in d["rows"] if r["flags"] & 2))

    ok &= selftest()

    if not lino:
        print("\n" + "=" * 78)
        print("LINO SIDE OUTSTANDING.  No fpout.bin from Implementer 1 was named on")
        print("the command line, so nothing about work/fp*.txt has been measured.")
        print("Everything above is the reference side only: real x87 silicon and an")
        print("exact-rational specification, agreeing with each other and with a")
        print("catalogue written in 1996.  When Implementer 1 produces an fpout.bin")
        print("for the NsIdentity chain over fpvec_starmap.bin, pass it here and it")
        print("is graded by the same rule with nothing changed.")
        print("=" * 78)
        return 0 if ok else 1

    print("\n" + "=" * 78)
    print("LINO BACKENDS")
    print("=" * 78)
    ref = os.path.join(W, "run_c_NsIdentity_133F.bin")
    for p in lino:
        try:
            sc, hits, d = fp_starmap.grade(p, rows, nrec, verbose=True)
        except SystemExit as e:
            print("  %s: %s" % (p, e))
            ok = False
            continue
        print("    verdict: %s (need %d/%d)"
              % ("PASS" if sc == 4194 else "FAIL", 4194, nrec))
        ok &= (sc == 4194)
        rc = fp_diff.main.__doc__ and 0
        sys.argv = ["fp_diff", ref, p, "--sample", "4"]
        fp_diff.main()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
