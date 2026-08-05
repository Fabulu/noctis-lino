"""WAVE 3 / IMPLEMENTER 2 - the diff harness.

Reads two or more files in the fpout.bin interchange format, whoever produced
them - the C x87 hardware reference, the exact-rational model, or Implementer
1's X87 / SOFT / NATIVE lino backends - and reports per-slot disagreement
counts against the first file named.

WHAT AGREEMENT BETWEEN WHICH PAIRS ACTUALLY PROVES.  State this plainly,
because it is the part a later reader is most likely to overstate:

  C-x87  vs  Python-exact-rational
      NON-CIRCULAR on arithmetic.  One asks silicon, the other applies the
      definition of correct rounding to exact rationals.  They share only the
      schedule text.

  lino-X87  vs  lino-SOFT
      NON-CIRCULAR on arithmetic, CIRCULAR ON THE SCHEDULE.  Both consume the
      same schedule description, so a wrong schedule agrees with itself
      perfectly.  This pair catches implementation bugs; it cannot catch a
      transcription error in the schedule and must never be cited as if it
      could.

  anything  vs  STARMAP.BIN
      The only comparison against an artifact this project did not make.
      Use fp_starmap.py.

Usage:
    python fp_diff.py <ref.bin> <other.bin> [<other.bin> ...] [--sample N]
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fp_model  # noqa: E402

SLOTS = ("f64bits", "chop", "near", "i16", "cmp", "flags")


def main():
    argv = sys.argv[1:]
    nsample = 6
    args = []
    i = 0
    while i < len(argv):
        if argv[i] == "--sample":
            nsample = int(argv[i + 1])
            i += 2
            continue
        if argv[i].startswith("--"):
            i += 1
            continue
        args.append(argv[i])
        i += 1
    if len(args) < 2:
        print(__doc__)
        return 2

    ref = fp_model.read_out(args[0])
    print("reference %-40s backend=%d cw=%04X sw=%04X ncase=%d"
          % (os.path.basename(args[0]), ref["backend"], ref["cw"], ref["sw"],
             ref["ncase"]))
    if (ref["sw"] >> 11) & 7:
        print("  *** reference x87 TOP=%d - stack was NOT balanced ***"
              % ((ref["sw"] >> 11) & 7))

    worst = 0
    for path in args[1:]:
        d = fp_model.read_out(path)
        print("\nvs %-40s backend=%d cw=%04X sw=%04X ncase=%d"
              % (os.path.basename(path), d["backend"], d["cw"], d["sw"], d["ncase"]))
        if d["ncase"] != ref["ncase"]:
            print("  NCASE MISMATCH %d vs %d - HARD ERROR, not a truncation"
                  % (d["ncase"], ref["ncase"]))
            worst = max(worst, 2)
            continue
        if (d["sw"] >> 11) & 7:
            print("  *** x87 TOP=%d - stack NOT balanced ***" % ((d["sw"] >> 11) & 7))
            worst = max(worst, 2)
        counts = dict((s, 0) for s in SLOTS)
        examples = []
        total = 0
        nskip = 0
        for i, (a, b) in enumerate(zip(ref["rows"], d["rows"])):
            # A rejected result (zero / subnormal / infinite / NaN) has no
            # comparable value - the two sides represent it differently on
            # purpose.  The FLAG is still compared; the values are not.
            rejected = (a["flags"] | b["flags"]) & 1
            check = ("flags",) if rejected else SLOTS
            if rejected:
                nskip += 1
            bad = [s for s in check if a[s] != b[s]]
            for s in bad:
                counts[s] += 1
            if bad:
                total += 1
                if len(examples) < nsample:
                    examples.append((i, bad, a, b))
        for s in SLOTS:
            flag = "" if counts[s] == 0 else "   <-- differs"
            print("  %-8s %6d / %-6d%s" % (s, counts[s], ref["ncase"], flag))
        print("  cases differing in any compared slot: %d / %d (%.4f%%)"
              "   [%d rejected, values not compared]"
              % (total, ref["ncase"], 100.0 * total / max(ref["ncase"], 1), nskip))
        if total:
            worst = max(worst, 1)
        for i, bad, a, b in examples:
            print("    case %-8d %s" % (i, ",".join(bad)))
            print("        ref  f64=%016x chop=%d near=%d i16=%d cmp=%d fl=%d"
                  % (a["f64bits"], a["chop"], a["near"], a["i16"], a["cmp"], a["flags"]))
            print("        oth  f64=%016x chop=%d near=%d i16=%d cmp=%d fl=%d"
                  % (b["f64bits"], b["chop"], b["near"], b["i16"], b["cmp"], b["flags"]))
    return worst


if __name__ == "__main__":
    sys.exit(main())
