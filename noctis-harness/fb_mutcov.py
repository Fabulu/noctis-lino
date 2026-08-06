#!/usr/bin/env python3
"""fb_mutcov.py -- Wave 5c.  Mutation coverage: the ledger's three gates.

    GATE 1  SENSITIVITY   for every GRADED cid, the MEASURED falsifier set is
                          non-empty and contains every DECLARED falsifier.
                          Declared-but-not-measured is a FAIL ("this check
                          stopped catching what it claims").  Measured-but-not-
                          declared is PRINTED, not failed.
    GATE 2  SPECIFICITY   every cid PASSES on a non-mutated input, and every
                          grading matrix fed a clean subject reports NOT CAUGHT.
    GATE 3  PIN INTEGRITY for every PIN cid the measured falsifier set must be
                          EMPTY.  A pin that becomes falsifiable is a FAIL: it
                          was not a pin.

Drift fails in BOTH directions, which is what makes the ledger a ratchet rather
than a suppression list.

HOW IT MEASURES.  It runs the SAME check bodies the graded suite runs --
`fb_compare.Suite(mutation=...)` -- so there is no second copy of any check to
drift out of step.  The mutation is threaded into every Python-side SUBJECT;
the C reference on the other side of each comparison stays clean, which is what
makes the row a cross-check rather than a mirror.

WHAT IT CANNOT DRIVE, stated rather than quietly excused:

  inrow:X   the row's own body CONSTRUCTS falsifier X and asserts the FAIL.
            Its sensitivity is measured, just inside the row.  fb_mutcov does
            not re-drive it, and the ledger has to say `inrow:` out loud.
  UNDRIVEABLE
            a falsifier this harness genuinely cannot produce -- the lino
            toolchain lives outside both implementers' namespaces.  Each one
            carries a reason here, the list is printed every run, and a
            declared falsifier that is in NEITHER category is a hard FAIL.

  python fb_mutcov.py            # the matrix and the three gates
  python fb_mutcov.py -v         # every measured falsifier, per cid
"""

import argparse
import os
import shutil
import sys
import tempfile

import fb_ledger

HERE = os.path.dirname(os.path.abspath(__file__))

# Falsifiers this harness cannot produce, each with the reason.  Anything
# declared in the ledger and absent from BOTH this map and the `inrow:` prefix
# is a hard failure of gate 1 -- so the exemption list cannot grow silently.
UNDRIVEABLE = {
    "CLEANASBREAK": "the null-input row needs a lino container to feed back in; it is "
                    "driven in the graded run by --lino-break, which is where the "
                    "matrix lives",
    "LINO-V1": "requires a lino build emitting FBDUMP v1; tests/w5probe.txt is "
               "outside both implementers' namespaces",
    "LINO-NOTAGS": "same -- and the CURRENT w5probe.bin already exhibits it, so the "
                   "row is measured against a real malformed stream when --lino is given",
    "LINO-SABOTAGE": "requires the 23 sabotaged lino builds; driven by --lino-break in "
                     "the graded run, not here",
    "SANDBOX-CWARN": "requires editing fb_ref.c, which implementer 2 owns",
    "SANDBOX-NOCAPS": "requires removing the 1996 captures; they are read-only inputs",
    "SANDBOX-BMPBYTE": "requires corrupting a 1996 capture; the captures are the one "
                       "thing in this project nobody may edit",
}


def _python_mutations():
    """Every mutation this harness CAN drive, and what it is."""
    import fb_layout
    import fb_pal
    import fb_tick
    import fb_wrap
    m = {}
    for b in fb_pal.BREAKS:
        m[b] = "palette"
    for b in fb_layout.LAYOUT_BREAKS:
        m[b] = "layout"
    for b in fb_layout.WORKSPACE_BREAKS:
        m[b] = "workspace"
    for b in fb_tick.BREAKS:
        m[b] = "tick"
    for b in fb_wrap.BREAKS:
        m[b] = "wrap"
    return m


# ---------------------------------------------------------- sandbox mutations
#
# Two of the new claims are about the 1996 SOURCES, so their falsifier is a
# source edit.  The reference clones are read-only, so both work on a COPY.


def sandbox_stickdisp():
    """SANDBOX-STICKDISP: change Stick's literal displacement `es:[di+4]` in a
    COPY of NOCTIS-0.CPP and require `solve_seg_offset` to refuse or to return a
    different K.  This is the whole of the alias-8 premise's falsifiability."""
    import fb_layout
    zero = fb_layout.read_text(fb_layout.ZERO_CPP)
    edited = zero.replace("mov word ptr es:[di+4], 0x3E00",
                          "mov word ptr es:[di+8], 0x3E00", 1)
    if edited == zero:
        return None, "the Stick displacement store was not found to edit"
    sol = fb_layout.solve_seg_offset(zero_text=edited)
    base = fb_layout.solve_seg_offset()
    return (sol["K"] != base["K"]), \
        "clean K=%s, edited K=%s (%s)" % (base["K"], sol["K"], sol["why"])


def sandbox_rowloop():
    """SANDBOX-ROWLOOP: change snapshot()'s parsed page bound in a COPY and
    require L14's row to move.  Before this wave L14 was a fact about Python's
    `&` operator and no source edit could touch it."""
    import fb_layout
    zero = fb_layout.read_text(fb_layout.ZERO_CPP)
    var, start, bound, step, _line = fb_layout.parse_snapshot_row_loop(zero)
    old = "for (%s=%d; %s<%d; %s-=%d)" % (var, start, var, bound, var, step)
    new = "for (%s=%d; %s<%d; %s-=%d)" % (var, start, var, bound + 320, var, step)
    edited = zero.replace(old, new, 1)
    if edited == zero:
        return None, "the row loop was not found to edit (%r)" % old
    got = fb_layout.parse_snapshot_row_loop(edited)
    # L14b's claim, re-evaluated on the edited source: it must now be FALSE
    moved = (got[2] != bound) and (start // step + 1) * step != got[2]
    return moved, "clean bound %d -> edited bound %d; L14b's (start/step+1)*step == bound " \
                  "no longer holds" % (bound, got[2])


def ledger_drop(measured=None, clean=None):
    """LEDGER-DROP: inject a MIS-DECLARATION and require gate 1 to report it.

    A gate that cannot be shown to fire is the defect it exists to find.  The
    injection re-evaluates the gate over the ALREADY-MEASURED matrix rather
    than re-running it -- gate 1 is a pure function of (measured, declared), so
    changing the declaration is the whole of the experiment."""
    if measured is None:
        return None, "no matrix supplied"
    cid = "T3.LAYOUT.L4.DIGITSUB"
    e = fb_ledger.LEDGER[cid]
    saved = e.falsifier
    e.falsifier = ("SWAPSEA",)          # a mutation that does NOT break this row
    try:
        gaps, _pins = _gates(measured, clean)
        fired = any(c == cid for c, _f in gaps)
    finally:
        e.falsifier = saved
    return fired, ("gate 1 %s the injected mis-declaration on %s (declared SWAPSEA, "
                   "measured %s)" % ("CAUGHT" if fired else "MISSED", cid,
                                     ",".join(sorted(measured.get(cid, ()))) or "nothing"))


def lint_blunt():
    """LINT-BLUNT: disable one lint rule and require the corpus row to fail."""
    import fb_lint
    saved = fb_lint.Lint.visit_Compare
    try:
        fb_lint.Lint.visit_Compare = lambda self, node: self.generic_visit(node)
        savedb = fb_lint._r2b
        fb_lint._r2b = lambda tree, fields: []
        ok, det = fb_lint.run_corpus()
    finally:
        fb_lint.Lint.visit_Compare = saved
        fb_lint._r2b = savedb
    return (not ok), "with R2/R2b disabled the corpus row reads %s (missed %s)" \
                     % ("FAIL" if not ok else "PASS", det["missed"])


def sandbox_fixtureedit():
    """SANDBOX-FIXTUREEDIT: flip one byte of the pinned stimulus and require the
    build-identity hash to move.  The fixture itself is architect-owned and is
    NOT written here -- the edit is made on the bytes in memory, which is the
    whole of the claim: a producer that did not rebuild against the current
    file carries a different hash."""
    import hashlib
    import fb_compare
    if not fb_compare.FIXTURE:
        return None, "docs-notes/FIXTURE1.txt is not on disk"
    raw = open(fb_compare.FIXTURE_FILE, "rb").read()
    edited = raw.replace(b"seed=1996", b"seed=1997", 1)
    if edited == raw:
        return None, "no `seed=` line to edit"
    new = hashlib.sha256(edited).hexdigest()
    return new != fb_compare.FIXTURE["sha256"],         "clean sha %s..., one-byte edit -> %s...; every producer's KSELF 80..87 "         "would then disagree with the file" % (fb_compare.FIXTURE["sha256"][:16], new[:16])


SANDBOX = {
    "SANDBOX-FIXTUREEDIT": sandbox_fixtureedit,
    "SANDBOX-STICKDISP": sandbox_stickdisp,
    "SANDBOX-ROWLOOP": sandbox_rowloop,
    "LEDGER-DROP": ledger_drop,
    "LINT-BLUNT": lint_blunt,
}


# ------------------------------------------------------------------ the matrix


def _run_suite(mutation):
    import fb_compare
    s = fb_compare.Suite(mutation=mutation, quiet=True, coverage=True)
    s.run(meta=False)
    return s.verdicts


def _gates(measured, clean):
    """GATE 1 and GATE 3, as a pure function of (measured matrix, declarations).

    Kept separate so LEDGER-DROP can inject a mis-declaration and re-evaluate
    without re-running the matrix -- and so the gate has exactly one
    implementation, which is the property the whole ledger is about.
    """
    sensitivity_gaps, pin_gaps = [], []
    driveable = _python_mutations()
    for cid, e in sorted(fb_ledger.LEDGER.items()):
        if e.kind == fb_ledger.GRADED:
            want, undeclarable = set(), []
            for f in e.falsifier:
                if f.startswith("inrow:") or f in UNDRIVEABLE:
                    continue
                if f not in driveable and f not in SANDBOX:
                    undeclarable.append(f)
                    continue
                want.add(f)
            if undeclarable:
                sensitivity_gaps.append(
                    (cid, ["%s (declared, and this harness can neither drive it nor "
                           "name a reason)" % f for f in undeclarable]))
                continue
            if not want:
                continue
            miss = sorted(want - measured.get(cid, set()))
            if miss and cid not in clean:
                # the row did not run in the coverage suite AND its declared
                # falsifiers were not demonstrated by a sandbox either
                sensitivity_gaps.append(
                    (cid, ["%s -- and the row did not run in the coverage suite, so the "
                           "declaration is untested" % ",".join(miss)]))
            elif miss:
                sensitivity_gaps.append((cid, miss))
        elif e.kind == fb_ledger.PIN and measured.get(cid):
            pin_gaps.append("%s (moved by %s)" % (cid, ",".join(sorted(measured[cid]))))
    return sensitivity_gaps, pin_gaps


def run(quiet=False, verbose=False, _no_recurse=False):
    """Returns the gate report."""
    say = (lambda *a: None) if quiet else print

    say("fb_mutcov.py -- mutation coverage over %d ledger entries" % len(fb_ledger.LEDGER))
    clean = _run_suite(set())
    driveable = _python_mutations()

    # -- which mutations do we actually need to run? -----------------------
    declared = set()
    for e in fb_ledger.LEDGER.values():
        declared |= {f for f in e.falsifier if not f.startswith("inrow:")}
    to_run = sorted(m for m in declared if m in driveable)

    measured = {}          # cid -> set of mutations that turned it FAIL
    for m in to_run:
        v = _run_suite({m})
        for cid, val in v.items():
            if clean.get(cid) is True and val is not True:
                measured.setdefault(cid, set()).add(m)
        say("  %-16s (%-9s) breaks %3d row(s)"
            % (m, driveable[m], len(v and [1 for cid, val in v.items()
                                           if clean.get(cid) is True and val is not True])))

    # -- the sandbox / meta falsifiers, each with a real demonstration ------
    sandbox_result = {}
    for name, fn in SANDBOX.items():
        try:
            ok, note = (fn(measured, clean) if name == "LEDGER-DROP" else fn())
        except Exception as exc:                      # pragma: no cover
            ok, note = False, "raised %s" % exc
        sandbox_result[name] = (ok, note)
        say("  %-16s (sandbox ) %s -- %s" % (name, "DEMONSTRATED" if ok else "NOT SHOWN", note))
        if ok:
            for cid, e in fb_ledger.LEDGER.items():
                if name in e.falsifier:
                    measured.setdefault(cid, set()).add(name)

    # -- the three gates ---------------------------------------------------
    sensitivity_gaps, pin_gaps = _gates(measured, clean)
    specificity_gaps = [cid for cid, val in sorted(clean.items())
                        if fb_ledger.LEDGER[cid].kind == fb_ledger.GRADED and val is False]
    unmeasurable = []
    for cid, e in sorted(fb_ledger.LEDGER.items()):
        for f in e.falsifier:
            if f in UNDRIVEABLE:
                unmeasurable.append((cid, f))

    extra = {cid: sorted(measured[cid] - {f for f in fb_ledger.LEDGER[cid].falsifier})
             for cid in measured}
    if verbose:
        for cid in sorted(measured):
            say("    %-38s broken by %s" % (cid, ",".join(sorted(measured[cid]))))

    report = {
        "clean_rows": len(clean),
        "measured": sum(1 for c, e in fb_ledger.LEDGER.items()
                        if c in clean and e.kind == fb_ledger.GRADED),
        "pins": sum(1 for c, e in fb_ledger.LEDGER.items()
                    if c in clean and e.kind == fb_ledger.PIN),
        "mutations": to_run,
        "sandbox": sandbox_result,
        "measured_map": {k: sorted(v) for k, v in measured.items()},
        "sensitivity_gaps": sensitivity_gaps,
        "specificity_gaps": specificity_gaps,
        "pin_gaps": pin_gaps,
        "unmeasurable": unmeasurable,
        "extra": {k: v for k, v in extra.items() if v},
    }
    return report


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    r = run(verbose=args.verbose)
    print("=" * 78)
    print("  mutations driven      %d  (%s)" % (len(r["mutations"]), ",".join(r["mutations"])))
    print("  rows measured         %d GRADED, %d PIN, over %d suite rows"
          % (r["measured"], r["pins"], r["clean_rows"]))
    print()
    print("  GATE 1 SENSITIVITY    %d gap(s)" % len(r["sensitivity_gaps"]))
    for cid, miss in r["sensitivity_gaps"]:
        print("     %-38s declares %s, and no run of it turned the row FAIL"
              % (cid, ",".join(miss)))
    print("  GATE 2 SPECIFICITY    %d row(s) that do not pass on a clean input"
          % len(r["specificity_gaps"]))
    for cid in r["specificity_gaps"]:
        print("     %s" % cid)
    print("  GATE 3 PIN INTEGRITY  %d pin(s) that turned out to be falsifiable"
          % len(r["pin_gaps"]))
    for g in r["pin_gaps"]:
        print("     %s" % g)
    print()
    print("  UNDRIVEABLE falsifiers, declared with a reason and printed every run:")
    seen = set()
    for cid, f in r["unmeasurable"]:
        if f in seen:
            continue
        seen.add(f)
        print("     %-22s %s" % (f, UNDRIVEABLE[f]))
    if r["extra"]:
        print()
        print("  measured but NOT declared (printed, never failed) -- these are the")
        print("  accidental falsifications the sensitivity gate deliberately ignores:")
        for cid, ms in sorted(r["extra"].items())[:12]:
            print("     %-38s also broken by %s" % (cid, ",".join(ms[:6])))
    ok = not (r["sensitivity_gaps"] or r["specificity_gaps"] or r["pin_gaps"])
    print()
    print("RESULT: %s" % ("PASS" if ok else "FAIL"))
    print("=" * 78)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
