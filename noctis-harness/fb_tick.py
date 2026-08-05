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

from fb_layout import fbdump_read, KIND_TICKLOG, KIND_SERVOLOG

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
    # -- wave 5-corrective: the SERVO ------------------------------------
    "SRVRUNSTART": "the servo brackets against the RUN START instead of the "
                   "previous firing -- the shipped Wave 5 defect  [S-SRV-RUNSTART]",
    "SRVWIDEMAX": "SRVMAX = 600000 ms, past the counter's own wrap  [S-SRV-WIDEMAX]",
    "SRVUNSIGNEDBAND": "the window-length band is an UNSIGNED compare  [S-SRV-UNSIGNEDBAND]",
    "SRVTRUNC": "the servo divide truncates instead of rounding  [S-SRV-TRUNC]",
    "SRVCLAMPFLOOR": "the +-1% clamp step has no floor of 1  [S-SRV-CLAMPFLOOR]",
    "WALLNOFOLD": "the wall clock is used raw, so midnight is a discontinuity  [S-WALL-NOFOLD]",
}

M32 = 0xFFFFFFFF
DAY_MS = 86400000


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


# =====================================================================
# THE SERVO -- windowed, re-based-first, rounded, signed-band
# =====================================================================
#
# CRITICAL 1.  The Wave 5 servo recalibrated by dividing (Counts - Counts_at_TK_start)
# by wall-clock ms since TK start.  [Counts] is 32 bits and wraps every
# 2^32 counts = 477.3 s at 8999 cpms, while the wall-clock denominator grows
# without bound, so from ~8 minutes in the numerator aliases and the ratio is
# nonsense.  The +-1% clamp does not save it: it converts a one-shot collapse
# into a PERMANENT ratchet.
#
# Note what is and is not wrong.  UNSIGNED SUBTRACTION ACROSS THE WRAP GIVES A
# CORRECT DELTA.  The bug is the BRACKET, not the subtraction.  So the fix is a
# WINDOW: measure between consecutive firings, re-base unconditionally, and
# refuse any window long enough for the counter to alias.
#
# Everything below is measured by `--servo-evidence`, not quoted.

SRVMIN = 4000        # ms; a window shorter than this is refused (why = 3)
SRVMAX = 60000       # ms; a window longer than this is refused (why = 4).
                     # 2^32 / 8999 cpms = 477271 ms, so this is 7.95x under the
                     # counter's own aliasing limit -- measured, see ring_sweep.

WHY = {0: "applied", 1: "clamped-lo", 2: "clamped-hi",
       3: "rejected-short", 4: "rejected-long"}


class WallFold(object):
    """`TK read wall` returns ms since midnight, and it is used as an INTERVAL
    reference.  Rather than special-case midnight at each consumer, fold it
    once.  Monotone for 49 days at 32-bit unsigned -- state the limit.

    Kept as a separate object precisely so a probe can drive it with synthetic
    raw values (23:59:59.900 -> 00:00:00.100) instead of waiting for midnight.
    """

    def __init__(self, breaks=()):
        self.breaks = set(breaks)
        self.prev = 0
        self.day = 0

    def fold(self, raw):
        if "WALLNOFOLD" in self.breaks:
            return raw
        if raw < self.prev:
            self.day += DAY_MS
        self.prev = raw
        return (raw + self.day) & M32


class Servo(object):
    """The replacement `TK servo`.  Four properties, each independently
    sabotageable:

      1. RE-BASE BEFORE THE BAND.  A rejected sample costs one update instead
         of doubling the next window.
      2. THE BAND IS SIGNED.  Signed is what refuses the midnight step, a
         resume from suspend, and any window long enough to alias the counter.
      3. THE DIVIDE IS ROUNDED.  One added term; truncation costs a systematic
         drift.
      4. THE CLAMP STEP HAS A FLOOR OF 1.  `cpms / 100` truncates to 0 below
         cpms 100, which is what turns a collapse into an ABSORBING STATE.
    """

    def __init__(self, cpms, breaks=(), srvmin=SRVMIN, srvmax=SRVMAX):
        self.cpms = cpms
        self.seed = cpms
        self.breaks = set(breaks)
        self.srvmin = srvmin
        self.srvmax = 600000 if "SRVWIDEMAX" in self.breaks else srvmax
        self.ref_counts = None
        self.ref_wall = None
        self.run_counts = None      # only used by the SRVRUNSTART sabotage
        self.run_wall = None
        self.log = []               # (tick, cpms in force, why)
        self.overflow = 0
        self.capacity = 64

    def start(self, counts, wall):
        self.ref_counts = counts & M32
        self.ref_wall = wall & M32
        self.run_counts = counts & M32
        self.run_wall = wall & M32

    def fire(self, tick, counts, wall):
        counts &= M32
        wall &= M32
        if "SRVRUNSTART" in self.breaks:
            cnt = (counts - self.run_counts) & M32
            ms = (wall - self.run_wall) & M32
        else:
            cnt = (counts - self.ref_counts) & M32     # correct across the wrap
            ms = (wall - self.ref_wall) & M32
        # RE-BASE FIRST, unconditionally -- before any test can bail out
        self.ref_counts = counts
        self.ref_wall = wall

        if "SRVUNSIGNEDBAND" in self.breaks:
            short, long_ = ms < 500, False
        else:
            short, long_ = s32(ms) < self.srvmin, s32(ms) > self.srvmax
        if short:
            self._log(tick, 3)
            return self.cpms, 3
        if long_:
            self._log(tick, 4)
            return self.cpms, 4

        if "SRVTRUNC" in self.breaks:
            new = cnt // ms
        else:
            new = (cnt + ms // 2) // ms               # ROUNDED

        step = self.cpms // 100
        if "SRVCLAMPFLOOR" not in self.breaks:
            step = max(1, step)
        why = 0
        if new < self.cpms - step:
            new, why = self.cpms - step, 1
        elif new > self.cpms + step:
            new, why = self.cpms + step, 2
        self.cpms = new
        self._log(tick, why)
        return self.cpms, why

    def _log(self, tick, why):
        if len(self.log) >= self.capacity:
            self.overflow += 1
            return
        self.log.append((tick, self.cpms, why))

    def payload(self):
        """FBDUMP kind 11 SERVOLOG: 3 units per firing."""
        out = []
        for t, c, w in self.log:
            out += [t & M32, c & M32, w & M32]
        return out


def cal_end(counts0, counts1, wall0, wall1, seed, breaks=()):
    """`TK cal end`, with the clamp the reviewer's finding B shows it never had.

    A bracket that straddles midnight or a suspend currently sets cpms = 0 and
    the period to ZERO COUNTS -- and a zero period means the tick fires
    continuously, forever.  Returns (cpms, why).
    """
    cnt = (counts1 - counts0) & M32
    ms = (wall1 - wall0) & M32
    if "SRVUNSIGNEDBAND" in breaks:
        if ms < 500:
            return seed, 3
    else:
        if s32(ms) < SRVMIN:
            return seed, 3
        if s32(ms) > SRVMAX:
            return seed, 4
    got = cnt // ms if "SRVTRUNC" in breaks else (cnt + ms // 2) // ms
    if "NOCALCLAMP" in breaks:
        return got, 0
    if got == 0 or got < seed // 4 or got > 4 * seed:
        return seed, 5
    return got, 0


def ring_sweep(cpms=8999, lengths=(500, 4000, 14061, 60000, 120000, 240000,
                                   470000, 477271, 500000),
               origins=65536, stride=65537):
    """Sweep the WINDOW END across the whole 32-bit counter ring with an odd
    stride, for each window length.  The truth is the unbounded-integer
    product cpms*ms; the subject is the 32-bit unsigned difference.

    This is what makes SRVMAX a MEASURED limit rather than an asserted one:
    the sweep is exact at 470000 ms and fails on every origin at 500000 ms.
    """
    out = []
    for L in lengths:
        want = cpms * L
        fails = 0
        for i in range(origins):
            end = (i * stride) & M32
            start = (end - want) & M32
            got = (end - start) & M32
            if got != (want & M32) or want > M32:
                fails += 1
        out.append({"ms": L, "exact_counts": want, "cases": origins,
                    "fails": fails, "fits_32": want <= M32})
    return out


def servo_replay(true_cpms=8999, minutes=20, period_s=14.0, breaks=(),
                 wall0=0, counts0=0):
    """Replay a windowed servo against a PERFECTLY CONSTANT true rate, over a
    session long enough for the 32-bit counter to wrap several times, and
    report the worst cpms error and the implied drift.

    The point is not that the rate moves -- it does not.  The point is that the
    Wave 5 bracket ALIASES, so it reports a rate that is not there.
    """
    n = int(minutes * 60 / period_s)
    s = Servo(true_cpms, breaks)
    s.capacity = 1 << 30          # keep the whole replay for the report
    fold = WallFold(breaks)
    s.start(counts0, fold.fold(wall0))
    worst = 0.0
    seen = set()
    raw = []                      # the UNCLAMPED ratio the bracket computes
    for k in range(1, n + 1):
        wall_ms = wall0 + int(k * period_s * 1000)
        counts = (counts0 + int(round(true_cpms * k * period_s * 1000))) & M32
        if "SRVRUNSTART" in set(breaks):
            dn = (counts - s.run_counts) & M32
            dm = (fold.fold(wall_ms) - s.run_wall) & M32
            fold.prev = wall_ms if "WALLNOFOLD" not in set(breaks) else fold.prev
            raw.append((int(k * period_s), dn // dm if dm else 0))
        c, _why = s.fire(k, counts, fold.fold(wall_ms))
        seen.add(c)
        worst = max(worst, abs(c - true_cpms) / float(true_cpms))
    # drift a game would accumulate at the final cpms, per hour of wall clock
    drift_s_per_hour = 3600.0 * (s.cpms - true_cpms) / float(true_cpms)
    return {"firings": n, "final_cpms": s.cpms, "distinct_cpms": len(seen),
            "min_cpms": min(seen), "max_cpms": max(seen),
            "worst_rel_err": worst, "drift_s_per_hour": drift_s_per_hour,
            "why_hist": _why_hist(s.log), "raw_ratio": raw}


def _why_hist(log):
    h = {}
    for _t, _c, w in log:
        h[w] = h.get(w, 0) + 1
    return dict(sorted(h.items()))


def grade_servolog(path_or_payload, seed_cpms=None):
    """Grade an FBDUMP kind 11 SERVOLOG.  Three units per firing, and it logs
    REJECTIONS too, so it is a value derived from what the program did rather
    than from construction."""
    if isinstance(path_or_payload, str):
        d = fbdump_read(path_or_payload)
        if d["kind"] != KIND_SERVOLOG:
            raise SystemExit("%s: kind %d, not SERVOLOG(11)" % (path_or_payload, d["kind"]))
        pay = d["payload"]
        seed_cpms = seed_cpms or d["cpms"]
    else:
        pay = list(path_or_payload)
    msg, ok = [], True

    def req(cond, text):
        nonlocal ok
        if not cond:
            ok = False
        msg.append(("  PASS  " if cond else "  FAIL  ") + text)

    req(len(pay) % 3 == 0, "S1 payload is a multiple of 3 units (%d)" % len(pay))
    n = len(pay) // 3
    rows = [(pay[3 * i], pay[3 * i + 1], pay[3 * i + 2]) for i in range(n)]
    req(n >= 1, "S1 the servo actually fired at least once (%d firings).  A soak whose "
                "SERVON exceeds its tick count never executes the servo at all -- which "
                "is exactly how CRITICAL 1 shipped." % n)
    bad_why = [i for i, r in enumerate(rows) if r[2] not in WHY]
    req(not bad_why, "S2 every `why` is one of %s (%d bad)" % (sorted(WHY), len(bad_why)))
    ticks = [r[0] for r in rows]
    req(all(b > a for a, b in zip(ticks, ticks[1:])),
        "S3 tick numbers strictly increase")
    cp = [r[1] for r in rows]
    step_bad = []
    for a, b in zip(cp, cp[1:]):
        if abs(b - a) > max(1, a // 100):
            step_bad.append((a, b))
    req(not step_bad, "S4 no single firing moved cpms by more than max(1, cpms/100) "
                      "(%d violations%s)" % (len(step_bad), (" first %s" % (step_bad[0],))
                                             if step_bad else ""))
    if seed_cpms:
        req(all(seed_cpms // 4 <= c <= 4 * seed_cpms for c in cp),
            "S5 cpms never left [seed/4, 4*seed] = [%d, %d] (min %d max %d)"
            % (seed_cpms // 4, 4 * seed_cpms, min(cp), max(cp)))
    req(all(c > 0 for c in cp), "S6 cpms never reached 0 (a zero period fires forever)")
    return ok, msg, {"firings": n, "why": _why_hist(rows), "cpms": cp}


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
    ap.add_argument("--servo", action="store_true",
                    help="the windowed-servo battery: window lengths, the ring sweep, "
                         "midnight, rounding, the clamp floor, and the shipped bracket "
                         "replayed")
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

    if args.servo:
        smsg = []
        sok = True

        def sreq(cond, text):
            nonlocal sok
            if not cond:
                sok = False
            smsg.append(("  PASS  " if cond else "  FAIL  ") + text)

        TRUE = 8999

        # -- T8a the window-length battery.  CASES ARE WINDOW LENGTHS, not
        # elapsed-since-start, and each fires THREE consecutive times with the
        # synthetic clock advanced by the window.  A single firing cannot
        # detect a missing re-base; three can.
        for L, expect_why in ((500, 3), (4000, 0), (14061, 0), (60000, 0),
                              (470000, 4), (500000, 4)):
            s = Servo(TRUE, brk)
            f = WallFold(brk)
            wall, counts = 0, 0x12345678
            s.start(counts, f.fold(wall))
            whys, cps = [], []
            for k in range(3):
                wall += L
                counts = (counts + TRUE * L) & M32
                c, w = s.fire(k, counts, f.fold(wall))
                whys.append(w)
                cps.append(c)
            good = (whys == [expect_why] * 3
                    and (expect_why != 0 or all(abs(c - TRUE) <= 1 for c in cps)))
            sreq(good, "T8a window %6d ms -> why %s cpms %s (want why %d%s)"
                 % (L, whys, cps, expect_why,
                    ", cpms within 1 of %d" % TRUE if expect_why == 0 else ""))

        # -- T8b the ring sweep.  SRVMAX is MEASURED here, not asserted.
        sw = ring_sweep(TRUE)
        exact = [r for r in sw if r["fails"] == 0]
        broken = [r for r in sw if r["fails"] == r["cases"]]
        sreq(all(r["fails"] == 0 for r in sw if r["ms"] <= 470000),
             "T8b unsigned subtraction across the wrap is EXACT for every window up to "
             "470000 ms, on all %d ring origins (%d lengths x %d origins)"
             % (sw[0]["cases"], len(sw), sw[0]["cases"]))
        sreq(any(r["ms"] == 500000 and r["fails"] == r["cases"] for r in sw),
             "T8b and it fails on %d of %d origins at 500000 ms -- so SRVMAX = %d is "
             "%.2fx under the counter's own aliasing limit 2^32/%d = %d ms"
             % (sw[-1]["fails"], sw[-1]["cases"], SRVMAX,
                (M32 + 1) / TRUE / SRVMAX, TRUE, int((M32 + 1) / TRUE)))

        # -- T8c the midnight case, against the fold
        s = Servo(TRUE, brk)
        f = WallFold(brk)
        raw0 = 86399900          # 23:59:59.900
        s.start(0, f.fold(raw0))
        raw1 = 100               # 00:00:00.100, 200 ms later
        c_mid, w_mid = s.fire(1, TRUE * 200, f.fold(raw1))
        sreq(w_mid == 3 and c_mid == TRUE,
             "T8c a midnight-straddling 200 ms window is REFUSED (why %d, cpms %d).  "
             "The fold removes the discontinuity; the SIGNED band refuses the short "
             "window that remains." % (w_mid, c_mid))
        # and the fold itself is monotone across the step
        f2 = WallFold(brk)
        a, b = f2.fold(raw0), f2.fold(raw1)
        sreq(b > a and b - a == 200,
             "T8c the wall fold is monotone across midnight: %d -> %d, delta %d ms "
             "(49-day limit at 32-bit unsigned)" % (a, b, b - a))

        # -- T8d the rounding case, constructed so truncation and rounding
        # differ by exactly 1 cpms
        ms, cnt = 14061, TRUE * 14061 + 7031
        s = Servo(TRUE, brk)
        f = WallFold(brk)
        s.start(0, f.fold(0))
        c_round, _ = s.fire(1, cnt, f.fold(ms))
        s2 = Servo(TRUE, set(brk) | {"SRVTRUNC"})
        f2 = WallFold(brk)
        s2.start(0, f2.fold(0))
        c_trunc, _ = s2.fire(1, cnt, f2.fold(ms))
        sreq(c_round == TRUE + 1 and c_trunc == TRUE,
             "T8d ms=%d cnt=%d: rounded -> %d, truncated -> %d, exactly one cpms apart"
             % (ms, cnt, c_round, c_trunc))

        # -- T8e the clamp step floor.  Without it, cpms/100 truncates to 0
        # below cpms 100 and the collapse becomes an ABSORBING STATE.
        s = Servo(99, brk)
        f = WallFold(brk)
        s.start(0, f.fold(0))
        wall, counts = 0, 0
        for k in range(50):
            wall += 5000
            counts = (counts + TRUE * 5000) & M32
            s.fire(k, counts, f.fold(wall))
        sreq(s.cpms > 99,
             "T8e from cpms 99 against a true %d, the servo climbs (reached %d in 50 "
             "firings).  With no floor on the clamp step it is FROZEN at 99 = %.0fx "
             "speed, forever." % (TRUE, s.cpms, TRUE / 99.0))

        # -- T8f the run-start bracket, replayed.  This is CRITICAL 1 itself,
        # measured rather than quoted.
        good = servo_replay(TRUE, minutes=20, breaks=brk)
        # THE SHIPPED SERVO: run-start bracket plus the unsigned `'< 500` band
        # and no upper limit at all.  Those three go together -- the band is
        # what would otherwise refuse the aliased window, which is precisely
        # why the fix needs all of them.
        shipped = set(brk) | {"SRVRUNSTART", "SRVUNSIGNEDBAND"}
        bad = servo_replay(TRUE, minutes=20, breaks=shipped)
        sreq(abs(good["drift_s_per_hour"]) <= 1.0 and good["worst_rel_err"] <= 0.001,
             "T8f windowed servo over 20 min at a PERFECTLY CONSTANT %d cpms: "
             "%d firings, cpms %d..%d, worst error %.4f%%, %.2f s/hour"
             % (TRUE, good["firings"], good["min_cpms"], good["max_cpms"],
                100 * good["worst_rel_err"], good["drift_s_per_hour"]))
        r600 = next((r for t, r in bad["raw_ratio"] if t >= 600), None)
        r900 = next((r for t, r in bad["raw_ratio"] if t >= 900), None)
        sreq(bad["worst_rel_err"] > 0.05,
             "T8f the SHIPPED run-start bracket over the SAME input: cpms %d..%d "
             "(%d distinct), worst error %.2f%%, %.2f s/hour.  Its UNCLAMPED ratio "
             "reads %s cpms at t=600 s and %s at t=900 s against a true %d.  The rate "
             "never moved; the bracket aliased, and the 1%% clamp turned a one-shot "
             "collapse into a permanent ratchet."
             % (bad["min_cpms"], bad["max_cpms"], bad["distinct_cpms"],
                100 * bad["worst_rel_err"], bad["drift_s_per_hour"], r600, r900, TRUE))

        # -- T8g `TK cal end`'s missing clamp
        ok0, _ = cal_end(0, TRUE * 10000, 0, 10000, TRUE, brk)[0], None
        sreq(ok0 == TRUE, "T8g a clean 10 s calibration bracket returns %d" % ok0)
        # a bracket that straddles midnight: wall1 < wall0 in RAW ms
        c_bad, why_bad = cal_end(0, TRUE * 200, 86399900, 100, TRUE, brk)
        sreq(c_bad == TRUE and why_bad in (3, 4, 5),
             "T8g a midnight-straddling calibration bracket is REFUSED (cpms %d, why %d).  "
             "Unclamped it yields cpms = 0, hence a period of ZERO COUNTS, hence a tick "
             "that fires continuously and forever." % (c_bad, why_bad))
        c_zero, why_zero = cal_end(0, 3, 0, 10000, TRUE, brk)
        sreq(c_zero == TRUE and why_zero == 5,
             "T8g a bracket that computes cpms = 0 is REFUSED and the seed is kept "
             "(cpms %d, why %d)" % (c_zero, why_zero))

        # -- T8h the servolog is gradeable and logs rejections
        s = Servo(TRUE, brk)
        f = WallFold(brk)
        s.start(0, f.fold(0))
        wall, counts = 0, 0
        for k in range(12):
            step = 300 if k % 4 == 0 else 5000       # some windows too short
            wall += step
            counts = (counts + TRUE * step) & M32
            s.fire(k, counts, f.fold(wall))
        gok, gmsg, gst = grade_servolog(s.payload(), TRUE)
        sreq(gok and 3 in gst["why"],
             "T8h the servolog grades clean and CONTAINS rejections (why histogram %s) "
             "-- a value derived from what the program did" % gst["why"])
        for m in gmsg:
            if m.startswith("  FAIL"):
                smsg.append("    " + m)

        print("servo:")
        print("\n".join(smsg))
        print()
        ok = ok and sok

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
