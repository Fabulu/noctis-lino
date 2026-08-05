#!/usr/bin/env python3
"""fb_tick.py -- Wave 5, implementer 2.  Independent tick reference + TICKLOG grader.

Two jobs.

1. Grade the PERIOD ARITHMETIC.  The port computes the tick period with a
   32-bit integer decomposition:

       period = cpms*55 - (cpms*44505 + carry) / 596591        carry = remainder

   Python has unbounded integers, so this module computes the period the
   honest way -- as the exact rational 32768000/596591 ms, i.e. 65536/1193182 s
   -- and checks that the decomposition's ACCUMULATED deadline never leaves
   the exact one by more than a count.  That is a genuinely different
   construction, not a transcription: nothing here can overflow, so a place
   where the 32-bit form does overflow shows up as a disagreement.

2. Grade a TICKLOG (FBDUMP kind 4).  The log is deliberately RAW -- three
   units per tick, absolute counts, the deadline fired against, and a flag
   word -- so periods, drift and skip behaviour are recomputed here rather
   than trusted from a lino-computed statistic.

  python fb_tick.py                      # arithmetic self-test
  python fb_tick.py --wrap-sweep         # the wrap/sign-boundary enumeration
  python fb_tick.py --grade LOG.bin      # grade a TICKLOG
  python fb_tick.py --break NAIVE        # sabotage; must fail
"""

import argparse
import struct
import sys
from fractions import Fraction

from fb_layout import fbdump_read, KIND_TICKLOG

# The true DOS period: the 8253 divisor 65536 over the 1.193182 MHz input.
PERIOD_S = Fraction(65536, 1193182)
PERIOD_MS = PERIOD_S * 1000            # = 32768000 / 596591 ms
assert PERIOD_MS == Fraction(32768000, 596591)
assert 55 - Fraction(44505, 596591) == PERIOD_MS

BREAKS = {
    "NAIVE": "period = cpms*552086/10000, the decomposition that overflows 32 bits",
    "ROUND55": "period = cpms*55, niv-lr's rounded 55 ms (noctis-d.h:174)",
    "NOCARRY": "drop the remainder carry, so the truncation never repays",
    "REBASE": "re-base the deadline on the actual fire time instead of accumulating",
    "NOSKIP": "advance by exactly one period after a miss instead of skipping to the grid",
    "UNSIGNEDCMP": "wait predicate uses an unsigned timestamp compare",
}

M32 = 0xFFFFFFFF


def s32(v):
    v &= M32
    return v - (1 << 32) if v & 0x80000000 else v


# ------------------------------------------------------- period arithmetic


class Period(object):
    """The port's 32-bit decomposition, with its carry."""

    def __init__(self, cpms, breaks=()):
        self.cpms = cpms
        self.breaks = set(breaks)
        self.carry = 0
        self.max_intermediate = 0

    def next(self):
        if "NAIVE" in self.breaks:
            # the decomposition PORTPLAN reached for first.  cpms*552086 is
            # 4.97e9 at cpms=9000 -- it does not fit in 32 bits.
            prod = self.cpms * 552086
            self.max_intermediate = max(self.max_intermediate, prod)
            return (prod & M32) // 10000
        if "ROUND55" in self.breaks:
            return self.cpms * 55
        num = self.cpms * 44505 + (0 if "NOCARRY" in self.breaks else self.carry)
        self.max_intermediate = max(self.max_intermediate, num)
        q = num // 596591
        self.carry = num - q * 596591
        return self.cpms * 55 - q


def exact_counts(cpms, n):
    """Exactly n tick periods, in counts, as a rational."""
    return Fraction(cpms) * PERIOD_MS * n


def period_audit(cpms, n=4096, breaks=()):
    p = Period(cpms, breaks)
    total = 0
    vals = []
    worst = Fraction(0)
    for k in range(1, n + 1):
        v = p.next()
        vals.append(v)
        total += v
        err = abs(Fraction(total) - exact_counts(cpms, k))
        worst = max(worst, err)
    return {
        "cpms": cpms,
        "total": total,
        "exact": exact_counts(cpms, n),
        "worst_abs_err_counts": worst,
        "worst_abs_err_ms": worst / cpms,
        "distinct_periods": sorted(set(vals)),
        "max_intermediate": p.max_intermediate,
        "fits_int32": p.max_intermediate < (1 << 31),
    }


# ---------------------------------------------------------- wait predicate


def expired(now, deadline, breaks=()):
    if "UNSIGNEDCMP" in breaks:
        return (now & M32) >= (deadline & M32)
    return s32((now - deadline) & M32) >= 0


def wrap_sweep(breaks=(), verbose=False):
    """Enumerate the constructed cases recon C used: every combination of a
    deadline near the 32-bit wrap and near the 2^31 sign boundary, crossed
    with a lead/lag of up to one tick.  The truth is defined by unbounded
    integer arithmetic on the SIGNED difference, which is what the hardware
    counter means.
    """
    anchors = []
    for centre in (0, 1 << 31, (1 << 32) - 1, 1 << 30, (3 << 30)):
        for d in range(-600000, 600001, 4001):
            anchors.append((centre + d) & M32)
    deltas = list(range(-500000, 500001, 997))
    fails = 0
    cases = 0
    first = None
    for dl in anchors:
        for dt in deltas:
            now = (dl + dt) & M32
            cases += 1
            want = dt >= 0
            got = expired(now, dl, breaks)
            if got != want:
                fails += 1
                if first is None:
                    first = (now, dl, dt, want, got)
    return cases, fails, first


# ------------------------------------------------------------ the tick loop


def run_loop(cpms, work_counts, breaks=(), sleep_margin_counts=None, servo=None):
    """Simulate the deadline discipline against a list of per-frame work
    durations (in counts).  Returns a TICKLOG payload, exactly the kind-4
    shape, so the grader below can be exercised on known-good input."""
    # ORDER MATTERS, and getting it wrong reproduces NOSKIP exactly.  The frame's
    # work happens BETWEEN the fire and the advance, so the skip decision must see
    # `now` AFTER the work.  An earlier version added the work at the top of the
    # next iteration, i.e. after the advance -- so an overrunning frame never
    # widened the deadline and the following frame fired immediately.  That is a
    # catch-up frame: the very thing skip-to-grid exists to prevent.  The stricter
    # K4c caught it in this simulator.
    #
    # The skip flag belongs to the tick that was ARRIVED AT by skipping, not to
    # the tick that overran.  LINOBUF 6 calls it a property of the tick's own
    # record ("the deadline it fired against"), and implementer 1's log agrees:
    # their flag rides the record whose deadline step was two periods wide.
    p = Period(cpms, breaks)
    now = 0
    deadline = (now + p.next()) & M32
    log = []
    skipped_into = False
    # `servo` = {tick_index: new_cpms}.  Swapping the Period generator mid-run
    # produces a genuinely CONTINUOUS log with two periods in it -- which is
    # what a conforming port emits, and what splicing two separate logs
    # together does NOT (the splice invents a step that is not a whole period,
    # and the grader was right to reject it).
    for ti, w in enumerate(work_counts):
        if servo and ti in servo:
            carry = p.carry
            p = Period(servo[ti], breaks)
            p.carry = carry
        # wait for the deadline
        while not expired(now, deadline, breaks):
            now = deadline
        fire = now
        flags = 0
        if sleep_margin_counts:
            flags |= 2
        if skipped_into:
            flags |= 1
        log += [fire & M32, deadline & M32, flags]
        # the frame's work
        now = (now + w) & M32
        # advance
        skipped = 0
        if "REBASE" in breaks:
            deadline = (fire + p.next()) & M32
        else:
            deadline = (deadline + p.next()) & M32
            if "NOSKIP" not in breaks:
                while expired(now, deadline, breaks):
                    deadline = (deadline + p.next()) & M32
                    skipped += 1
        skipped_into = skipped > 0
    return log


# ------------------------------------------------------------ TICKLOG grader


def grade_ticklog(path, cpms=None, max_drift_ms=1.0, ticks_expected=None):
    d = fbdump_read(path)
    if d["kind"] != KIND_TICKLOG:
        raise SystemExit("%s: kind %d, not TICKLOG(4)" % (path, d["kind"]))
    pay = d["payload"]
    if len(pay) % 3:
        raise SystemExit("%s: %d payload units is not a multiple of 3" % (path, len(pay)))
    n = len(pay) // 3
    cpms = cpms or d["cpms"]
    if not cpms:
        raise SystemExit("%s: no cpms in the header and none supplied" % path)

    fires = [pay[3 * i + 0] for i in range(n)]
    deads = [pay[3 * i + 1] for i in range(n)]
    flags = [pay[3 * i + 2] for i in range(n)]

    # every statistic below is RECOMPUTED here from the raw counts
    gaps = [s32((fires[i + 1] - fires[i]) & M32) for i in range(n - 1)]
    dgaps = [s32((deads[i + 1] - deads[i]) & M32) for i in range(n - 1)]
    lateness = [s32((fires[i] - deads[i]) & M32) for i in range(n)]

    exact_period_counts = float(Fraction(cpms) * PERIOD_MS)
    multiples = [round(g / exact_period_counts) for g in gaps]

    # -- SEGMENTS ---------------------------------------------------------
    #
    # The header's cpms is "the CALIBRATED counts-per-ms AT WRITE TIME"
    # (LINOBUF 6), and LINOBUF 5.5 rule 5 REQUIRES the port to re-calibrate
    # after the asset-load phase and then servo every 256 ticks.  So a long log
    # legitimately contains several different integer periods, and grading the
    # whole log against the single header cpms measures the CALIBRATION, not
    # the tick discipline -- it would fail a port that is behaving exactly as
    # specified.  (Measured: implementer 1's 400-tick log holds two periods,
    # 494218/9 then 494273/4, a servo step of one count per ms.)
    #
    # So: recover the period actually in force at each step, split the log into
    # runs of constant period, and grade the ACCUMULATION inside each run --
    # where the carry's guarantee (error bounded by one count, never growing)
    # is the thing under test.  The servo itself is graded separately, as a
    # bound on how far cpms is allowed to move.
    steps = []                       # (k, base_period_float) per deadline step
    for g in dgaps:
        k = max(1, round(g / exact_period_counts))
        steps.append((k, g / k))
    segs = []                        # [start_index, end_index, implied_cpms]
    for i, (k, base) in enumerate(steps):
        icpms = base * float(1 / PERIOD_MS)
        if segs and abs(icpms - segs[-1][2]) < 0.5:
            segs[-1][1] = i
        else:
            segs.append([i, i, icpms])
    seg_report = []
    worst_seg_counts = 0.0
    for a, b, icpms in segs:
        rc = round(icpms)
        exact = float(Fraction(rc) * PERIOD_MS)
        span = s32((deads[b + 1] - deads[a]) & M32)
        gsteps = sum(k for k, _ in steps[a:b + 1])
        dc = span - gsteps * exact
        seg_report.append({"first_tick": a, "last_tick": b + 1, "cpms": rc,
                           "grid_steps": gsteps, "drift_counts": dc,
                           "drift_ms": dc / rc})
        worst_seg_counts = max(worst_seg_counts, abs(dc))

    # whole-log drift, still reported, but against the per-segment periods
    grid_steps = sum(k for k, _ in steps)
    drift_counts = sum(s["drift_counts"] for s in seg_report)
    drift_ms = drift_counts / cpms

    msg = []
    ok = True

    def req(cond, text):
        nonlocal ok
        if not cond:
            ok = False
        msg.append(("  PASS  " if cond else "  FAIL  ") + text)

    req(n >= 2, "K1 log has at least two ticks (%d)" % n)
    if ticks_expected:
        req(n == ticks_expected, "K1 %d ticks as requested (got %d)" % (ticks_expected, n))

    # K2 -- every deadline step is a whole number of the period IN FORCE, and
    # that period is within one count of the exact rational for the cpms the
    # port was using.  One count is the carry's own guarantee, so this is a
    # far tighter statement than the old +-2% window.
    bad_grid = []
    for a, b, icpms in segs:
        exact = float(Fraction(round(icpms)) * PERIOD_MS)
        for i in range(a, b + 1):
            k, base = steps[i]
            if k < 1 or abs(base - exact) > 1.0:
                bad_grid.append(i)
    req(not bad_grid, "K2 every deadline step is a whole number of the exact period in force, "
                      "within 1 count (%d violations, %d segment(s))" % (len(bad_grid), len(segs)))

    # K3 -- the accumulation.  Graded INSIDE each constant-cpms run, against
    # the exact rational, with the carry's bound of one count.  Not a
    # milliseconds-per-log budget: a bound that does not grow with the log
    # length is the whole point of carrying the remainder.
    req(worst_seg_counts <= 1.0,
        "K3 accumulated deadline stays within 1 count of the exact period in every "
        "constant-cpms run (worst %.4f counts = %.6f ms over %d grid steps, %d run(s))"
        % (worst_seg_counts, worst_seg_counts / cpms, grid_steps, len(segs)))

    # K3b -- the servo is allowed to move cpms, but LINOBUF 5.5 rule 5 bounds
    # the correction to +-1%.  A log that re-calibrates further than that is
    # not servoing, it is chasing noise.
    cpms_seen = [round(s["cpms"]) for s in seg_report]
    spread = (max(cpms_seen) - min(cpms_seen)) / min(cpms_seen) if cpms_seen else 0.0
    req(spread <= 0.01, "K3b cpms recalibration stayed within 1%% (%s, spread %.4f%%)"
        % ("->".join(str(c) for c in cpms_seen), spread * 100))

    # K4 -- skip-to-grid, stated as the property it actually is.
    #
    # NOT "every fire-to-fire gap is at least one period": after a frame that
    # overruns by 0.4 of a tick, the next grid point is only 0.6 of a tick
    # away, so a short gap there is CORRECT.  The real property is that the
    # next deadline is the smallest grid point STRICTLY AFTER the fire that
    # just happened -- the system re-aligns to the grid instead of carrying
    # its lateness forward (which is REBASE) or falling behind it (NOSKIP).
    # The MINIMALITY of a skip is NOT checkable from this log, and the old
    # version of this check pretended otherwise.  The port decides how far to
    # skip at the top of the next iteration -- AFTER the frame's work -- and
    # the log records the fire instant, which is BEFORE it.  So a k=2 step is
    # justified by a work time this log never observes, and demanding
    # `deadline[i+1] - period <= fire[i]` fails a correct implementation.
    # (Measured: it produced 10 false failures against implementer 1's log,
    # every one of them a genuine 109.84 ms frame.)  What IS checkable:
    bad_skip = []
    for i in range(n - 1):
        k, _ = steps[i]
        # K4a the next deadline is strictly in the future of the fire it followed
        if s32((deads[i + 1] - fires[i]) & M32) <= 0:
            bad_skip.append((i, "next deadline is not strictly after the fire"))
        # K4b the skip flag and the behaviour agree -- bit 0 is set exactly
        #     when a grid point was passed over
        elif bool(flags[i + 1] & 1) != (k > 1):
            bad_skip.append((i, "skip flag %d disagrees with k=%d" % (flags[i + 1] & 1, k)))
    req(not bad_skip, "K4 next deadline strictly future, and the skip flag agrees with the "
                      "grid step (%d violations%s)"
        % (len(bad_skip), ("; first at tick %d: %s" % bad_skip[0]) if bad_skip else ""))

    # K4c -- the property the whole skip-to-grid rule exists to produce, and
    # the one that separates it from plain accumulation: after a frame that
    # overran its tick, the NEXT frame is not a catch-up frame.  Under
    # skip-to-grid every fire-to-fire gap is a whole period or more; under bare
    # accumulate the deadline is already in the past and the next fire is
    # immediate.  Tolerance is 1% of a period (0.55 ms) for wake jitter --
    # implementer 1's tightest real gap ran 0.081 ms early.
    floor_counts = 0.99 * exact_period_counts
    catchup = [i for i, g in enumerate(gaps) if g < floor_counts]
    req(not catchup, "K4c no back-to-back fire after a hitch: every fire-to-fire gap is a "
                     "whole period or more (%d violations%s)"
        % (len(catchup), (", shortest %.4f ms vs %.4f" % (min(gaps) / cpms, exact_period_counts / cpms))
           if catchup else ""))

    # K5 -- a fire never precedes the deadline it fired against
    early = [i for i, l in enumerate(lateness) if l < 0]
    req(not early, "K5 no fire precedes its own deadline (%d violations)" % len(early))

    hist = {}
    for m in multiples:
        hist[m] = hist.get(m, 0) + 1
    mean_mult = sum(multiples) / len(multiples) if multiples else 0

    return ok, msg, {
        "ticks": n,
        "cpms": cpms,
        "exact_period_counts": exact_period_counts,
        "exact_period_ms": float(PERIOD_MS),
        "measured_mean_gap_ms": (sum(gaps) / len(gaps) / cpms) if gaps else 0,
        "measured_min_gap_ms": (min(gaps) / cpms) if gaps else 0,
        "measured_max_gap_ms": (max(gaps) / cpms) if gaps else 0,
        "drift_ms": drift_ms,
        "drift_worst_segment_counts": worst_seg_counts,
        "segments": seg_report,
        "grid_steps": grid_steps,
        "tick_multiple_histogram": dict(sorted(hist.items())),
        "mean_tick_multiple": mean_mult,
        "implied_fps": (1000.0 / (mean_mult * float(PERIOD_MS))) if mean_mult else 0,
        "late_ticks": sum(1 for l in lateness if l > exact_period_counts * 0.05),
        "flag_skipped": sum(1 for f in flags if f & 1),
        "flag_slept": sum(1 for f in flags if f & 2),
    }


def write_ticklog(path, payload, cpms, ticks):
    from fb_layout import fbdump_write
    fbdump_write(path, KIND_TICKLOG, payload, cpms=cpms, ticks=ticks)


# -------------------------------------------------------------------- main


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--wrap-sweep", action="store_true")
    ap.add_argument("--grade", metavar="LOG.bin")
    ap.add_argument("--cpms", type=int, default=None)
    ap.add_argument("--emit", metavar="LOG.bin", help="simulate a loop and write a TICKLOG")
    ap.add_argument("--break", dest="brk", action="append", default=[], choices=sorted(BREAKS))
    args = ap.parse_args(argv)
    brk = set(args.brk)

    print("fb_tick.py -- independent tick reference")
    print("  exact period  %s ms = %.7f ms = 65536/1193182 s"
          % (PERIOD_MS, float(PERIOD_MS)))
    for b in brk:
        print("  SABOTAGE %-12s %s" % (b, BREAKS[b]))
    print()

    ok = True
    msg = []

    def req(cond, text):
        nonlocal ok
        if not cond:
            ok = False
        msg.append(("  PASS  " if cond else "  FAIL  ") + text)

    # A1 -- the decomposition tracks the exact rational, across the whole
    # range of counts-per-ms recon C saw reported (8984..9023) and beyond.
    # The accumulated error is bounded by ONE COUNT, forever, because the
    # remainder carry repays every truncation on the following tick.
    CEIL = ((1 << 31) - 1 - 596590) // 44505
    for cpms in (1000, 2997, 8984, 9000, 9023, 10000, CEIL):
        a = period_audit(cpms, 4096, brk)
        req(a["worst_abs_err_counts"] <= 1,
            "A1 cpms=%-6d accumulated error <= 1 count over 4096 ticks (worst %.4f counts, %.6f ms)"
            % (cpms, float(a["worst_abs_err_counts"]), float(a["worst_abs_err_ms"])))
        req(a["fits_int32"],
            "A2 cpms=%-6d largest intermediate %d fits int32" % (cpms, a["max_intermediate"]))
        if cpms == 9000:
            req(len(a["distinct_periods"]) <= 2,
                "A3 cpms=9000 period takes at most two adjacent values %s" % a["distinct_periods"])

    # A2b -- the decomposition is NOT unconditionally overflow-free, and the
    # ceiling should be stated rather than implied.  cpms*44505 + carry must
    # stay under 2^31, so cpms <= (2^31 - 1 - 596590) / 44505.
    ceiling = CEIL
    under = period_audit(ceiling, 4096, brk)
    over = period_audit(ceiling + 1, 4096, brk)
    req(under["fits_int32"] and not over["fits_int32"],
        "A2b overflow ceiling is exactly cpms <= %d (%.1fx the observed ~9000): "
        "%d fits (max %d), %d does not (max %d).  NOT unconditional."
        % (ceiling, ceiling / 9000.0, ceiling, under["max_intermediate"],
           ceiling + 1, over["max_intermediate"]))

    # A4 -- the naive decomposition really does overflow, so the sabotage is
    # not a straw man
    naive = 9000 * 552086
    req(naive > (1 << 31), "A4 cpms*552086 = %d exceeds 2^31 (%d) -- the overflow is real"
        % (naive, 1 << 31))

    # A5 -- what the carry actually buys.  It is NOT a large per-tick effect:
    # the truncation is under one count, i.e. 0.00011 ms at cpms=9000.  What
    # it buys is that the error stays BOUNDED instead of growing LINEARLY.
    # Measure the growth rather than asserting a magnitude.
    with_carry = [period_audit(9000, n, brk)["worst_abs_err_counts"] for n in (8192, 65536)]
    no_carry = [period_audit(9000, n, set(brk) | {"NOCARRY"})["worst_abs_err_counts"]
                for n in (8192, 65536)]
    req(with_carry[1] <= 1,
        "A5 with carry: error at 65536 ticks is %.4f counts -- bounded, not growing"
        % float(with_carry[1]))
    req(no_carry[1] > 4 * no_carry[0],
        "A5 without carry: error grows %.1f counts -> %.1f counts as ticks go 8192 -> 65536 (linear)"
        % (float(no_carry[0]), float(no_carry[1])))
    req(float(no_carry[1]) / 9000 > 0.5,
        "A5 without carry that is %.3f ms adrift after 65536 ticks (~1 hour of play)"
        % (float(no_carry[1]) / 9000))

    print("period arithmetic:")
    print("\n".join(msg))
    print()

    if args.wrap_sweep:
        cases, fails, first = wrap_sweep(brk)
        print("wrap / sign-boundary sweep:")
        print("  %d constructed cases, %d disagreements with unbounded-integer truth" % (cases, fails))
        if first:
            print("  first: now=%08X deadline=%08X delta=%+d want=%s got=%s" % first)
        print("  %s" % ("PASS" if fails == 0 else "FAIL"))
        if fails:
            ok = False
        print()

    if args.emit:
        cpms = args.cpms or 9000
        exact = float(Fraction(cpms) * PERIOD_MS)
        # 400 frames of ~2 ms work with two deliberate hitches of 1.4 ticks
        work = [int(exact * 0.04)] * 400
        work[100] = int(exact * 1.4)
        work[250] = int(exact * 2.6)
        pay = run_loop(cpms, work, brk)
        write_ticklog(args.emit, pay, cpms, len(pay) // 3)
        print("wrote %s (%d ticks)" % (args.emit, len(pay) // 3))
        print()

    if args.grade:
        gok, gmsg, stats = grade_ticklog(args.grade, args.cpms)
        print("TICKLOG %s:" % args.grade)
        for k in sorted(stats):
            print("    %-28s %s" % (k, stats[k]))
        print("\n".join(gmsg))
        ok = ok and gok
        print()

    print("RESULT: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
