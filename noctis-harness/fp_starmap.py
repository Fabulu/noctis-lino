"""WAVE 3 / IMPLEMENTER 2 - the killer oracle, applied to anybody's fpout.bin.

STARMAP.BIN was written in 1996 by Borland C++ 3.1 on a 387.  Its stored
doubles are therefore an externally-produced, pre-existing answer key for the
question "what precision was the arithmetic done at".  This grader applies it
to any engine that can produce the interchange format - the C x87 reference,
the exact-rational model, or Implementer 1's lino backends - with no engine
getting different treatment.

SCORING RULE, fixed before any engine runs (see fp_vectors.py for why):
    a catalogue record counts as REPRODUCED when at least one of its candidate
    coordinate triples yields, bit for bit, the double stored in the file.
There is no candidate selection, so there is nothing for an engine to be
lucky about, and the negative controls are scored identically.

WHAT THIS ORACLE CAN AND CANNOT DECIDE.  It rules out 53-bit-per-operation,
24-bit-per-operation, the isthere() right-associative formula, and any spilled
intermediate.  It does NOT distinguish the true x87 chain from an exact-integer
product rounded once: those two agree on roughly 3383 of every 3384 stars, so
on 4194 rows they are expected to differ about once and observing zero
disagreements is unremarkable.  Any claim that this file "proves 80-bit chains"
is overreach.  The galaxy-scale hardware differential is what decides that.

Usage:
    python fp_starmap.py <fpout.bin> [<fpout.bin> ...]
"""

import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fp_model   # noqa: E402
import fp_sched   # noqa: E402

MANIFEST = os.path.join(fp_sched.OUTDIR, "fpcases_starmap.tsv")


def load_manifest(path=MANIFEST):
    rows = []
    nrec = 0
    for line in open(path):
        if line.startswith("#"):
            if "records=" in line:
                nrec = int(line.split("records=")[1].split()[0])
            continue
        c, r, nm, hx, x, y, z = line.rstrip("\n").split("\t")
        rows.append((int(c), int(r), nm, int(hx, 16), int(x), int(y), int(z)))
    if not rows:
        raise SystemExit("empty manifest %s - run fp_vectors.py starmap first" % path)
    return rows, nrec


BACKEND_NAME = {1: "lino X87", 2: "lino SOFT", 3: "lino NATIVE",
                4: "C x87 hardware", 5: "Python exact-rational"}


def grade(outpath, rows, nrec, verbose=True):
    d = fp_model.read_out(outpath)
    if d["ncase"] != len(rows):
        raise SystemExit("%s: NCASE %d but manifest has %d cases - HARD ERROR"
                         % (outpath, d["ncase"], len(rows)))
    hit = [False] * nrec
    firsthit = [False] * nrec
    seen = set()
    nrej = 0
    for (c, r, nm, want, x, y, z) in rows:
        got = d["rows"][c]
        if got["flags"] & 1:
            nrej += 1
        ok = got["f64bits"] == want
        if ok:
            hit[r] = True
        if r not in seen:
            seen.add(r)
            firsthit[r] = ok
    score = sum(hit)
    if verbose:
        print("%-46s backend=%-22s cw=%04X sw=%04X TOP=%d"
              % (os.path.basename(outpath),
                 BACKEND_NAME.get(d["backend"], "id %d" % d["backend"]),
                 d["cw"], d["sw"], (d["sw"] >> 11) & 7))
        print("    STARMAP oracle: %d/%d records reproduced bit-exactly"
              " (%d cases, %d rejected, %d unbalanced)"
              % (score, nrec, len(rows), nrej,
                 sum(1 for rr in d["rows"] if rr["flags"] & 2)))
        # The older harness kept only the first candidate it found per record
        # and then hand-corrected six of them.  Reporting that number too is
        # what makes this grader comparable with the recon figures instead of
        # looking like a regression: at 0x103F it is 66 there and 67 here, and
        # the extra record is LI+, whose second candidate happens to survive
        # 24-bit rounding.  Neither number is wrong; they answer different
        # questions, and only the any-candidate one is free of selection.
        print("    (first-candidate-only, comparable with the old harness: %d/%d)"
              % (sum(firsthit), nrec))
    return score, hit, d


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    rows, nrec = load_manifest()
    print("manifest: %d cases over %d catalogue records (%d collision extras)"
          % (len(rows), nrec, len(rows) - nrec))
    results = []
    for p in sys.argv[1:]:
        results.append((p,) + grade(p, rows, nrec))
    if len(results) > 1:
        print("\nrecord-level differences between the first file and the rest:")
        base = results[0]
        for p, score, hit, d in results[1:]:
            diff = sum(1 for a, b in zip(base[2], hit) if a != b)
            print("  %-40s %d/%d   differs from %s on %d records"
                  % (os.path.basename(p), score, nrec,
                     os.path.basename(base[0]), diff))
    return 0


if __name__ == "__main__":
    sys.exit(main())
