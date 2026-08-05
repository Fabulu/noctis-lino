"""ns_grade.py -- the Wave 4 reference-side grading run, end to end.

One command, from scratch, nothing read from a stored expectation:

  1  CORPUS        rebuild the corpus from the galaxy hash and STARMAP.BIN,
                   with the single-candidate rule, and check the (long)
                   shortcut on every coordinate
  2  TRANSCRIPTION ns_ref.c and ns_spec.py must agree BIT FOR BIT on the real
                   corpus, on a phase-H subset and on a synthetic sweep of
                   all twelve classes.  Reported as its own class: two
                   implementations agreeing is evidence about transcription
                   and about nothing else.
  3  LEDGER        the same, one draw at a time: site, argument and returned
                   value, in order, for every draw of every system.
  4  CATALOGUE     the six external legs against the 1996 file
  5  DL            the 1996 machine code's own output, 122 captures
  6  SUBJECT       eleven float sites, the seed's overflow spelling, and the
                   float-independence control
  7  MUTANTS       twelve sabotages and four controls

Usage:  python ns_grade.py [--quick] [--skip-mutants]
"""

import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import ns_spec as N                                             # noqa: E402
import ns_diff as D                                             # noqa: E402

EXE = os.path.join(HERE, "ns_ref.exe")
SRC = os.path.join(HERE, "ns_ref.c")


def sh(*cmd):
    r = subprocess.run(list(cmd), capture_output=True, text=True)
    if r.returncode:
        sys.stdout.write(r.stdout)
        sys.stderr.write(r.stderr)
        raise SystemExit("FAILED: %s" % " ".join(cmd))
    return r.stdout


def head(n, s):
    print("\n" + "=" * 78)
    print("%d  %s" % (n, s))
    print("=" * 78)


def stats(path):
    _h, recs = N.read_nstopo(path)
    tot = [r[11] for r in recs]
    perph = [[r[12 + p] for r in recs] for p in range(8)]
    print("  systems %d   draws: total %d, min %d, mean %.1f, max %d"
          % (len(recs), sum(tot), min(tot), sum(tot) / float(len(tot)), max(tot)))
    print("  %-8s %8s %8s %8s" % ("phase", "total", "max", "systems>0"))
    for p in range(8):
        col = perph[p]
        print("  %-8s %8d %8d %8d"
              % (N.PHASES[p], sum(col), max(col), sum(1 for v in col if v)))
    print("  draw budget is 100000; the worst system used %d (%.2f%% of it)"
          % (max(tot), 100.0 * max(tot) / 100000))
    nob = [r[6] for r in recs]
    print("  nob: max %d (maxbodies is 80), systems at the clamp: %d"
          % (max(nob), sum(1 for v in nob if v == 80)))


def main(argv):
    quick = "--quick" in argv
    skipmut = "--skip-mutants" in argv
    t0 = time.time()
    fails = []

    head(1, "CORPUS")
    print(sh(sys.executable, os.path.join(HERE, "ns_corpus.py"),
             "--out", os.path.join(HERE, "ns_corpus.nsin"),
             "--manifest", os.path.join(HERE, "ns_corpus.tsv")))

    sh("gcc", "-O2", "-fwrapv", "-Wall", "-Wextra", "-o", EXE, SRC, "-lm")
    print("built ns_ref.exe with -fwrapv, no warnings")

    head(2, "TRANSCRIPTION -- ns_ref.c vs ns_spec.py, bit for bit")
    corpus = os.path.join(HERE, "ns_corpus.nsin")
    jobs = [("the real corpus", corpus, [], [])]
    sh(sys.executable, os.path.join(HERE, "ns_corpus.py"),
       "--out", os.path.join(HERE, "ns_h200.nsin"), "--limit", "200",
       "--flags", "1", "--manifest", os.path.join(HERE, "ns_h200.tsv"))
    jobs.append(("200 systems with phase H", os.path.join(HERE, "ns_h200.nsin"),
                 [], []))
    sh(sys.executable, os.path.join(HERE, "ns_corpus.py"),
       "--out", os.path.join(HERE, "ns_synth.nsin"), "--synthetic",
       "512" if quick else "4096")
    jobs.append(("12 classes x %d seeds, digest" % (512 if quick else 4096),
                 os.path.join(HERE, "ns_synth.nsin"), ["--digest"], ["--digest"]))

    for (label, nsin, ca, pa) in jobs:
        c = nsin + ".c.out"
        p = nsin + ".py.out"
        sh(*([EXE, nsin, c] + ca))
        sh(*([sys.executable, os.path.join(HERE, "ns_spec.py"), nsin, p] + pa))
        print("\n-- %s" % label)
        f = D.compare([c, p])
        if f:
            fails.append("TRANSCRIPTION: " + label)

    print("\n-- draw accounting over the real corpus")
    stats(corpus + ".c.out")

    head(3, "LEDGER -- every draw, site by site")
    sh(sys.executable, os.path.join(HERE, "ns_corpus.py"),
       "--out", os.path.join(HERE, "ns_led.nsin"), "--limit", "400",
       "--manifest", os.path.join(HERE, "ns_led.tsv"))
    ln = os.path.join(HERE, "ns_led.nsin")
    sh(EXE, ln, ln + ".c.out", "--ledger", ln + ".c.led")
    sh(sys.executable, os.path.join(HERE, "ns_spec.py"), ln, ln + ".py.out",
       "--ledger", ln + ".py.led")
    if D.compare_ledgers(ln + ".c.led", ln + ".py.led"):
        fails.append("LEDGER")

    head(4, "CATALOGUE -- STARMAP.BIN, 1996")
    r = subprocess.run([sys.executable, os.path.join(HERE, "ns_catalogue.py")]
                       + (["--quick"] if quick else []),
                       capture_output=True, text=True)
    print(r.stdout)
    if r.returncode:
        fails.append("CATALOGUE")

    head(5, "DL -- the 1996 machine code's own output")
    r = subprocess.run([sys.executable, os.path.join(HERE, "ns_dl.py")],
                       capture_output=True, text=True)
    print(r.stdout)
    if r.returncode:
        fails.append("DL")

    head(6, "SUBJECT -- checks on the reference files themselves")
    if not D.check_sites():
        fails.append("SITES")
    if not D.check_overflow(os.path.join(HERE, "ns_h200.nsin")):
        fails.append("OVERFLOW")
    if not D.check_jitter(corpus):
        fails.append("JITTER")

    if not skipmut:
        head(7, "MUTANTS")
        r = subprocess.run([sys.executable, os.path.join(HERE, "ns_mkbreak.py")],
                           capture_output=True, text=True)
        print(r.stdout)
        if r.returncode:
            fails.append("MUTANTS")

    print("\n" + "=" * 78)
    print("elapsed %.1fs" % (time.time() - t0))
    if fails:
        print("REFERENCE SIDE: FAIL -- " + ", ".join(fails))
        return 1
    print("REFERENCE SIDE: PASS")
    print("")
    print("STILL OUTSTANDING: the L.in.oleum side.  work/ns*.txt is "
          "Implementer 1's and was not present in this session, so no NSTOPO "
          "with producer=0 has ever been compared.  Everything above grades "
          "the C and Python references only.  When the lino side produces an "
          "NSTOPO it is graded by exactly these commands -- ns_diff.py against "
          "the two references, ns_dl.py --nstopo against the captures -- with "
          "no new code.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
