"""Candidate servos, replayed on the real 19-minute stream.

Each candidate is a rule producing the integer cpms in force at each servo
epoch.  Score = the game-visible timing error that value produces, integrated
over the epoch, expressed as seconds of game time gained or lost per hour.
"""
import struct, statistics

M32 = 1 << 32
raw = open(r"C:\programmieren\linoleum\work\probe-w5b2-rate.bin", "rb").read()
u = list(struct.unpack("<%dI" % (len(raw) // 4), raw))
NS = u[1]
rawc = u[16:16 + NS]
w = u[16 + NS:16 + 2 * NS]
d = u[16 + 2 * NS:16 + 3 * NS]
rep = u[0]
truth = sum(d[1:]) / float(w[-1] - w[0])

# ---- abs-error percentiles of a single window estimate, by window length
print("SINGLE-WINDOW ESTIMATE, |error| distribution (real data)")
print("  %8s %6s %9s %9s %9s %9s" %
      ("win ms", "n", "p50", "p90", "worst", "worst s/hr"))
for k in (1, 2, 3, 4, 7, 8, 15, 30):
    es = []
    for a in range(0, NS - k, k):
        m = w[a + k] - w[a]
        if m > 0:
            es.append(abs(sum(d[a + 1:a + 1 + k]) / float(m) - truth) / truth)
    es.sort()
    if len(es) < 4:
        continue
    p50 = es[len(es) // 2]
    p90 = es[int(len(es) * 0.9)]
    print("  %8d %6d %8.4f%% %8.4f%% %8.4f%% %9.2f"
          % (k * 1900, len(es), 100 * p50, 100 * p90, 100 * es[-1],
             3600 * es[-1]))

# ---- estimator replay.  One servo epoch = SERVK samples (~14 s).
SERVK = 7


def replay(mode, seed, ema_shift=0, rnd=True):
    cpms = int(round(seed))
    hist = []
    tot_lo, tot_hi, tot_ms = 0, 0, 0
    ema = cpms << 8
    ref = 0
    for a in range(0, NS - SERVK, SERVK):
        b = a + SERVK
        cnt = sum(d[a + 1:b + 1]) % M32
        ms = w[b] - w[a]
        if mode == "none":
            hist.append((w[b], cpms))
            continue
        if mode == "start":
            cnt = (rawc[b] - rawc[0]) % M32
            ms = w[b] - w[0]
        if mode == "cum":                      # 64-bit wrap-safe accumulation
            tot_lo += cnt
            tot_ms += ms
            new = (tot_lo + tot_ms // 2) // tot_ms
        else:
            new = (cnt + ms // 2) // ms if rnd else cnt // ms
        if ema_shift:
            ema += ((new << 8) - ema) >> ema_shift
            new = (ema + 128) >> 8
        lo, hi = cpms - cpms // 100, cpms + cpms // 100
        new = max(lo, min(hi, new))
        cpms = new
        hist.append((w[b], cpms))
    # integrated timing error
    err_ms = 0.0
    prev_t = w[0]
    for t, c in hist:
        err_ms += (t - prev_t) * (c - truth) / truth
        prev_t = t
    span = (hist[-1][0] - w[0]) / 1000.0
    worst = max(abs(c - truth) for _, c in hist) / truth
    return err_ms, span, worst, hist[-1][1], sorted(set(c for _, c in hist))


print("\nCANDIDATE SERVOS, REPLAYED (epoch = %d samples = ~%d s, %d epochs)"
      % (SERVK, SERVK * 19 // 10, (NS - SERVK) // SERVK))
print("  %-40s %10s %10s %8s %s"
      % ("candidate", "drift s/hr", "worst err", "final", "cpms seen"))
cands = [
    ("reported value, no servo", "none", rep, 0, True),
    ("startup 2.5s bracket, no servo", "none", 8999, 0, True),
    ("shipped: bracket vs run start", "start", 8999, 0, True),
    ("windowed, truncating divide", "win", 8999, 0, False),
    ("windowed, rounded divide", "win", 8999, 0, True),
    ("windowed + EMA/8", "win", 8999, 3, True),
    ("windowed + EMA/16", "win", 8999, 4, True),
    ("wrap-safe cumulative (64-bit total)", "cum", 8999, 0, True),
]
for name, mode, seed, sh, rnd in cands:
    err, span, worst, fin, seen = replay(mode, seed, sh, rnd)
    print("  %-40s %10.2f %9.4f%% %8d %s"
          % (name, err / span * 3600 / 1000.0, 100 * worst, fin,
             seen if len(seen) < 9 else "%d values %d..%d"
             % (len(seen), seen[0], seen[-1])))
print("\n  truth %.4f ; 'drift s/hr' = game seconds gained(+)/lost(-) per hour"
      % truth)
