#!/usr/bin/env python3
"""fbx_mutmatrix.py -- implementer 2's own mutation-coverage gate for fb_ref.c.

WHY THIS EXISTS, in one sentence: a check that names a falsifier and is not
actually falsified by it is the same defect as a check that names none.

It is NOT the wave's ledger tool -- that is fb_mutcov.py, implementer 1's file,
covering the whole harness.  This one covers exactly the artifact implementer 2
owns, runs in its own namespace (fbx_*), and exists so that fb_ref.c arrives
already proved rather than arriving with a promise.

WHAT IT DOES.  fb_ref.c writes fb-ref-checks.tsv on every run: one row per
check, with a stable id, a KIND and the sabotages the row DECLARES must break
it.  This tool builds fb_ref.c once clean and once per -DBREAK_*, collects the
tables, and applies three gates:

  SENSITIVITY  every GRADED row must be FAILED by every sabotage it declared.
               "Some mutation broke it" is satisfied by accident; the diagonal
               has to be named.  Declared-but-not-measured is a FAIL.
  SPECIFICITY  every row must PASS on the clean build.  A check that fires on
               a correct build is not evidence, it is noise -- and it is
               exactly how lino_break_matrix came to report the clean build as
               a caught sabotage.
  PIN          every PIN row must be failed by NOTHING.  A pin that becomes
               falsifiable was never a pin, and the exemption list has drifted.

Undeclared catches are PRINTED, not failed: a row that catches more than it
promised is a bonus, not a defect.

usage:  python fbx_mutmatrix.py [--jobs N] [--only BREAK_X,...]
"""

import os
import re
import subprocess
import sys
import tempfile
import shutil
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "fb_ref.c")
SUPPORTS = r"C:\programmieren\noctis\niv-plus\data\SUPPORTS.NCT"
NOCTIS_SRC = r"C:\programmieren\noctis\niv-plus\source"
FIXTURE = os.path.abspath(os.path.join(HERE, "..", "docs-notes", "FIXTURE1.txt"))


def discover_breaks(path):
    """The sabotage set is READ OUT OF THE SUBJECT, not typed here.

    Typing the list would let a sabotage be silently retired by deleting its
    #ifdef: the list and the code would drift apart and the matrix would keep
    reporting a clean sweep over a shrinking set."""
    text = open(path, encoding="utf-8", errors="replace").read()
    names = sorted(set(re.findall(r"\bBREAK_([A-Z0-9]+)\b", text)))
    # BREAK_OVERRUN takes a value, not a bare -D; it is not a boolean sabotage.
    return ["BREAK_" + n for n in names if n != "OVERRUN"]


def parse_tsv(path):
    rows = {}
    meta = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            if line.startswith("#"):
                p = line[1:].split("\t")
                if len(p) >= 4 and p[0] == "producer":
                    meta["producer"] = p[1]
                    meta["fixture_sha256"] = p[3]
                continue
            p = line.split("\t")
            if len(p) < 4:
                continue
            cid, kind, verdict, fals = p[0], p[1], p[2], p[3]
            # comma-separated only: an external falsifier is a single
            # space-free token (EXT_*), so splitting on whitespace would
            # shred it into several imaginary sabotages
            rows[cid] = (kind, verdict,
                         [x.strip() for x in fals.split(",") if x.strip()])
    return rows, meta


def build_and_run(tag, defines, workroot):
    d = os.path.join(workroot, tag)
    os.makedirs(d, exist_ok=True)
    exe = os.path.join(d, "fb_ref_%s.exe" % tag)
    cmd = ["gcc", "-std=c99", "-O2", "-w", "-o", exe]
    for m in defines:
        cmd.append("-D" + m)
    cmd.append(SRC)
    cp = subprocess.run(cmd, capture_output=True, text=True)
    if cp.returncode != 0:
        return None, "BUILD FAILED: " + cp.stderr.strip()[:300]
    cp = subprocess.run([exe, d, SUPPORTS, NOCTIS_SRC, FIXTURE],
                        capture_output=True, text=True)
    tsv = os.path.join(d, "fb-ref-checks.tsv")
    if not os.path.exists(tsv):
        return None, "NO LEDGER (exit %d): %s" % (cp.returncode,
                                                  (cp.stdout + cp.stderr)[-300:])
    rows, meta = parse_tsv(tsv)
    return (rows, meta, cp.returncode), None


def main():
    only = None
    jobs = min(8, (os.cpu_count() or 4))
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--only":
            only = set(args[i + 1].split(","))
            i += 2
        elif args[i] == "--jobs":
            jobs = int(args[i + 1])
            i += 2
        else:
            i += 1

    breaks = discover_breaks(SRC)
    if only:
        breaks = [b for b in breaks if b in only]

    workroot = tempfile.mkdtemp(prefix="fbxmut_")
    try:
        clean, err = build_and_run("clean", [], workroot)
        if err:
            print("clean build: " + err)
            return 2
        crows, cmeta, ccode = clean
        print("fbx_mutmatrix -- fb_ref.c mutation coverage")
        print("  producer      %s" % cmeta.get("producer", "?"))
        print("  fixture sha   %s" % cmeta.get("fixture_sha256", "?"))
        print("  ledger rows   %d" % len(crows))
        print("  sabotages     %d (discovered from the subject, not typed here)"
              % len(breaks))
        print()

        # ---- SPECIFICITY: the clean build must pass everything ----
        clean_fail = [c for c, (k, v, f) in crows.items() if v == "FAIL"]
        print("SPECIFICITY (the clean build must trip nothing)")
        if clean_fail:
            for c in clean_fail:
                print("  FAIL  %s fails on a CLEAN build" % c)
        else:
            print("  PASS  0 of %d rows fire on the clean build" % len(crows))
        print()

        results = {}
        with ThreadPoolExecutor(max_workers=jobs) as ex:
            futs = {ex.submit(build_and_run, b, [b], workroot): b for b in breaks}
            for fu, b in futs.items():
                pass
            for fu in futs:
                b = futs[fu]
                r, e = fu.result()
                results[b] = (r, e)

        # measured[cid] = set of sabotages that FAILED it
        measured = {c: set() for c in crows}
        broken_builds = []
        for b in breaks:
            r, e = results[b]
            if e:
                broken_builds.append((b, e))
                continue
            rows, _meta, code = r
            if len(rows) != len(crows):
                print("  ----  %-24s ledger row COUNT differs (%d vs clean %d)"
                      " -- positional UNLEDGERED ids are not comparable for"
                      " this build" % (b, len(rows), len(crows)))
            for cid, (kind, verdict, fals) in rows.items():
                if verdict == "FAIL":
                    measured.setdefault(cid, set()).add(b)

        if broken_builds:
            print("BUILDS THAT DID NOT PRODUCE A LEDGER")
            for b, e in broken_builds:
                print("  ----  %-24s %s" % (b, e))
            print()

        # ---- SENSITIVITY ----
        print("SENSITIVITY (every GRADED row must be failed by every falsifier"
              " it declares)")
        sens_fail = 0
        for cid in sorted(crows):
            kind, verdict, declared = crows[cid]
            if kind != "GRADED":
                continue
            # external falsifiers are named with a parenthesised note and are
            # demonstrated by hand, outside the -D matrix; they are listed so
            # a reader can see the row is not exempt, only differently proved
            dmac = [d for d in declared if d.startswith("BREAK_")]
            dext = [d for d in declared if d.startswith("EXT_")]
            junk = [d for d in declared if d not in dmac and d not in dext]
            if junk:
                print("  FAIL  %-28s falsifier names outside the vocabulary:"
                      " %s" % (cid, ",".join(junk)))
                sens_fail += 1
            miss = [d for d in dmac if d not in measured.get(cid, set())]
            extra = sorted(measured.get(cid, set()) - set(dmac))
            if not dmac and not dext:
                print("  FAIL  %-28s declares no falsifier" % cid)
                sens_fail += 1
                continue
            if miss:
                print("  FAIL  %-28s declared but did NOT bite: %s"
                      % (cid, ",".join(miss)))
                sens_fail += 1
            elif not dmac:
                print("  ----  %-28s only EXTERNAL falsifiers (%s) -- proved by"
                      " hand, see the report" % (cid, ",".join(dext)))
            else:
                print("  PASS  %-28s %d/%d declared falsifiers bite%s"
                      % (cid, len(dmac), len(dmac),
                         ("; also caught " + ",".join(extra)) if extra else ""))
        print()

        # ---- PIN INTEGRITY ----
        print("PIN INTEGRITY (a pin that becomes falsifiable was never a pin)")
        pin_fail = 0
        pins = [c for c in sorted(crows) if crows[c][0] == "PIN"]
        if not pins:
            print("  ----  no PIN rows")
        for cid in pins:
            m = sorted(measured.get(cid, set()))
            if m:
                print("  FAIL  %-28s falsified by %s -- reclassify as GRADED"
                      % (cid, ",".join(m)))
                pin_fail += 1
            else:
                print("  PASS  %-28s falsified by nothing in the set" % cid)
        print()

        # ---- the OTHER direction: sabotages this ledger does not catch ----
        #
        # The row-side view ("which rows does nothing break") is only half of
        # it.  A sabotage that no row in this file catches is a hole in the
        # SUBJECT's self-test, and it is invisible from the row side because
        # every row can still be busy passing.  Printed, not failed: some
        # sabotages are correctly the grader's job rather than the producer's
        # -- BREAK_PROBEMOD16 changes which pad unit is probed, which only a
        # CROSS-PRODUCER comparison of the canary record can see.  Saying
        # which, out loud, is the point.
        caught_by_any = {}
        for b in breaks:
            r, e = results[b]
            if e:
                continue
            caught_by_any[b] = any(v == "FAIL" for (_k, v, _f) in r[0].values())
        blind = sorted(b for b, ok in caught_by_any.items() if not ok)
        print("SABOTAGES NO ROW IN THIS LEDGER CATCHES (a hole in the "
              "PRODUCER's self-test, printed not failed)")
        if blind:
            for b in blind:
                print("  ----  %s" % b)
        else:
            print("  ----  none: every sabotage in the set moves at least one row")
        print()

        # ---- UNLEDGERED: the rows this wave did not reach ----
        unl = [c for c in sorted(crows) if crows[c][0] == "UNLEDGERED"]
        if unl:
            inert = [c for c in unl if not measured.get(c)]
            print("UNLEDGERED (rows that predate the ledger; NOT a pass, NOT a"
                  " failure -- a stated hole)")
            print("  ----  %d rows carry no declared falsifier; %d of them are"
                  " reached by NOTHING in the sabotage set" % (len(unl),
                                                               len(inert)))
            if inert:
                print("        inert: %s" % ",".join(inert))
            print()

        # ---- rows nothing catches, printed whatever their kind ----
        dead = [c for c in sorted(crows)
                if crows[c][0] == "GRADED" and not measured.get(c)]
        if dead:
            print("GRADED ROWS NO SABOTAGE IN THE SET REACHES")
            for c in dead:
                print("  ----  %-28s (declared: %s)" % (c, ",".join(crows[c][2])))
            print()

        ok = not clean_fail and not sens_fail and not pin_fail and not broken_builds
        print("RESULT: %s   specificity %s, sensitivity %d bad, pins %d bad, "
              "builds %d bad"
              % ("PASS" if ok else "FAIL",
                 "ok" if not clean_fail else "BROKEN",
                 sens_fail, pin_fail, len(broken_builds)))
        return 0 if ok else 1
    finally:
        shutil.rmtree(workroot, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
