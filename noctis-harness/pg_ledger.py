#!/usr/bin/env python3
"""
pg_ledger.py -- Wave 6a producer ledger.

There are exactly THREE producers and no fourth.  A Python re-implementation
of a rasteriser would be a second reading of the same 1996 text by the same
person and buys nothing, so there isn't one.

  external:  the four frozen corpora + the 1996 sources    (inputs)
  cref:      pg_ref.c -> pg_ref.exe                        (implementer 2)
  lino:      work/pg*.txt -> work/pg-out.bin               (implementer 1)
  bin:       NOCTIS.EXE                                    (the 1996 artifact)

RULE.  No GRADED row may compare two artifacts of the SAME owner.
STRUCTURAL HAZARD, stated rather than hidden: implementer 2 owns BOTH pg_ref.c
and pg_grade.py.  The C oracle may therefore be compared to lino or to the
binary -- never to the grader's own expectations.  Every cref-vs-cref row in
pg_grade.py is labelled MEASUREMENT and is calibration, not evidence.

Usage: python pg_ledger.py [--check]
"""

import argparse, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

OWNER = {
    "external": ["pg_corpus_raster.txt", "pg_corpus_edge.txt",
                 "pg_corpus_span.txt", "pg_corpus_proj.txt",
                 r"noctis\niv-plus\source\TDPOLYGS.H",
                 r"noctis\niv-plus\source\NOCTIS-D.H"],
    "cref":     ["pg_ref.c", "pg_ref.exe", "pg_break_*.exe"],
    "lino":     [r"work\pg*.txt", r"work\pg-out.bin"],
    "bin":      [r"noctis\niv-plus\modules\NOCTIS.EXE"],
}

# (row, kind, left owner, right owner, note)
ROWS = [
 ("C1.a  clip immediates",        "GRADED",      "bin", "external",
  "four one-hit C7 06 imm16 in NOCTIS.EXE vs NOCTIS-D.H:122-132"),
 ("C1.b  >=/< asymmetry",         "GRADED",      "bin", "external",
  "the jcc opcodes 7C 7C 7D 7D decoded from the image"),
 ("C1.c  counter-hypothesis",     "GRADED",      "bin", "external",
  "310/285/35 must have ZERO hits"),
 ("C1.d  long+float tables",      "GRADED",      "bin", "external",
  "40 contiguous bytes at 0x2c931"),
 ("C1.e  Segmento es:[di+4]",     "GRADED",      "bin", "external",
  "the offset-4 settlement, one opcode"),
 ("C1.f  scratch pixel offsets",  "GRADED",      "bin", "external",
  "0xFA00/0xFA01 present, LR's 0xFA04 absent"),
 ("C1.g  instruction census",     "GRADED",      "bin", "external",
  "constant-free, so POLYVERT.EXE corroborates"),
 ("FIXTURE.shared_corpus",        "GRADED",      "lino", "external",
  "implementer 1 must consume the frozen text, not its own"),
 ("S1  Segmento page",            "GRADED",      "lino", "cref",  "byte-exact"),
 ("S2  bbox gate",                "GRADED",      "lino", "cref",  "exact"),
 ("S3  poly3d page",              "GRADED",      "lino", "cref",  "byte-exact"),
 ("S4  ipart/fpart",              "GRADED",      "lino", "cref",  "exact"),
 ("S5  span page",                "GRADED",      "lino", "cref",  "byte-exact"),
 ("S6.P1 topology",               "GRADED",      "lino", "cref",  "exact"),
 ("S6.P3 mp[] values",            "GRADED",      "lino", "cref",
  "BOUND: max|delta|<=1 AND exact-fraction >= the measured constant"),
 ("S7  getcoords",                "GRADED",      "lino", "cref",  "exact"),
 ("S4.binary64_is_exact",         "MEASUREMENT", "cref", "cref",
  "--acc=f64 vs --acc=ext.  Calibration: fixes S4's promotion from bounded to "
  "exact.  NOT evidence about the port."),
 ("S4.binary32_is_the_control",   "MEASUREMENT", "cref", "cref",
  "the negative control that makes the row above non-vacuous"),
 ("S6.P3.exact_fraction",         "MEASUREMENT", "cref", "cref",
  "fixes the pass/fail constant used by the S6.P3 GRADED row"),
 ("S6.P2 round mode",             "MEASUREMENT", "cref", "cref",
  "--round=chop.  The +-1 envelope is structurally blind to a chop error."),
 ("S6 fst asymmetry",             "MEASUREMENT", "cref", "cref",
  "--fst=allwide/allnarrow"),
 ("MUT.* (35 rows)",              "MECHANICAL",  "cref", "cref",
  "sabotage vs clean.  Same owner BY DESIGN: it measures the CHECKS, not the "
  "port.  w5audit reads Python only, so pg_ref.c is outside its reach and "
  "this matrix is its only substitute."),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    print("Wave 6a producers")
    for o, fs in OWNER.items():
        print("  %-9s %s" % (o + ":", ", ".join(fs)))
    print()
    w = max(len(r[0]) for r in ROWS)
    bad = 0
    for name, kind, l, r, note in ROWS:
        flag = ""
        if kind == "GRADED" and l == r:
            flag = "  <-- SAME-OWNER GRADED ROW, FORBIDDEN"
            bad += 1
        print("%-*s  %-11s  %-8s  %s%s" % (w, name, kind, "%s vs %s" % (l, r),
                                           note, flag))
    print()
    ng = sum(1 for r in ROWS if r[1] == "GRADED")
    print("pg_ledger: %d rows, %d GRADED, %d same-owner violations" % (len(ROWS), ng, bad))
    print("pg_ledger: the 8 lino-vs-cref GRADED rows are the wave's actual")
    print("           evidence.  They are N/A until implementer 1 consumes the")
    print("           frozen corpora; see FIXTURE.shared_corpus.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
