"""Read probe-w5b2-rate.bin and answer: does the rate drift, and what happens
at the wrap.  Everything here is recomputed from the raw pairs."""
import struct, sys, statistics

M32 = 1 << 32
DAY = 86400000

path = sys.argv[1] if len(sys.argv) > 1 else \
    r"C:\programmieren\linoleum\work\probe-w5b2-rate.bin"
raw = open(path, "rb").read()
u = list(struct.unpack("<%dI" % (len(raw) // 4), raw))
head = u[:16]
NS = head[1]
rawc = u[16:16 + NS]
wal = u[16 + NS:16 + 2 * NS]
dele = u[16 + 2 * NS:16 + 3 * NS]

rep_cpms, dwell, calms = head[0], head[2], head[3]
calcnt, calmsm = head[8], head[9]
print("reported [Counts Per Millisecond] = %d" % rep_cpms)
print("startup bracket: %d counts / %d ms = %.3f cpms  (target %d ms of spin)"
      % (calcnt, calmsm, calcnt / float(calmsm), calms))
print("samples %d, dwell %d ms" % (NS, dwell))

# ---- wall clock, repaired for a midnight crossing (reported, not hidden)
w = []
addday = 0
for i, x in enumerate(wal):
    if i and x + addday < w[-1]:
        addday += DAY
        print("!! wall clock went backwards at sample %d -> midnight crossing" % i)
    w.append(x + addday)

# ---- the wrap, observed
decreases = [i for i in range(1, NS) if rawc[i] < rawc[i - 1]]
print("\nRAW counter decreased %d times in %.1f s" %
      (len(decreases), (w[-1] - w[0]) / 1000.0))

# unwrapped counts from the unsigned differences the probe stored
tot = 0
unw = []
for i in range(NS):
    tot += dele[i]
    unw.append(tot)
# cross-check: the probe's stored delta must equal the unsigned difference of
# the raw values it also stored.  Two independent routes to the same number.
bad = 0
for i in range(1, NS):
    if (rawc[i] - rawc[i - 1]) % M32 != dele[i]:
        bad += 1
print("stored delta vs recomputed unsigned difference: %d mismatches of %d"
      % (bad, NS - 1))

span_ms = w[-1] - w[0]
span_ct = unw[-1] - unw[0]
rate_all = span_ct / float(span_ms)
print("whole run: %d counts / %d ms = %.4f cpms" % (span_ct, span_ms, rate_all))
print("2^32 / rate = %.2f s  (predicted wrap period)" % (M32 / rate_all / 1000.0))
print("predicted wraps in the run: %.2f" % (span_ct / float(M32)))

# wall time between observed wraps
if len(decreases) >= 2:
    gaps = [(w[decreases[i]] - w[decreases[i - 1]]) / 1000.0
            for i in range(1, len(decreases))]
    print("observed wall time between wraps: %s s" %
          ["%.2f" % g for g in gaps])

# per-sample rate
rates, idle, busy = [], [], []
for i in range(1, NS):
    dt = w[i] - w[i - 1]
    if dt <= 0:
        continue
    r = dele[i] / float(dt)
    rates.append((w[i] - w[0], r, i))
    (idle if i % 2 == 0 else busy).append(r)


def stat(name, xs):
    if not xs:
        return
    mn, mx = min(xs), max(xs)
    print("  %-22s n=%3d  min %.3f  median %.3f  max %.3f  spread %.4f%%"
          % (name, len(xs), mn, statistics.median(xs), mx,
             100.0 * (mx - mn) / statistics.median(xs)))


print("\nper-sample rate (window = one dwell, ~%d ms):" % dwell)
stat("all", [r for _, r, _ in rates])
stat("idle samples (SLEEP)", idle)
stat("busy samples (spin)", busy)
print("  idle median - busy median = %+.4f cpms (%.4f%%)"
      % (statistics.median(idle) - statistics.median(busy),
         100.0 * (statistics.median(idle) - statistics.median(busy))
         / statistics.median(busy)))

# drift: rate of the first minute vs each later minute
print("\nrate by 60 s bucket (drift test):")
buckets = {}
for t, r, i in rates:
    buckets.setdefault(int(t // 60000), []).append((r, dele[i], w[i] - w[i - 1]))
ks = sorted(buckets)
ref = None
for k in ks:
    c = sum(b[1] for b in buckets[k])
    m = sum(b[2] for b in buckets[k])
    r = c / float(m)
    if ref is None:
        ref = r
    print("  t=%4d-%4ds  %d counts / %d ms = %.4f cpms  (%+.4f%% vs first)"
          % (k * 60, k * 60 + 60, c, m, r, 100.0 * (r - ref) / ref))

print("\nWHAT A NON-SERVOED ESTIMATE WOULD HAVE COST")
for name, est in (("runtime's reported value", float(rep_cpms)),
                  ("startup %d ms bracket" % calms, calcnt / float(calmsm))):
    err = (est - rate_all) / rate_all
    print("  %-26s %.4f cpms  error %+.4f%%  = %+.3f ms per 55 ms tick, "
          "%+.1f s per hour"
          % (name, est, 100 * err, 54.9254012 * err, 3600 * err))

# What the wave-5 servo would have computed at each sample, from the REAL data
print("\nTHE SHIPPED SERVO, REPLAYED ON THIS RUN'S REAL COUNTER")
c0 = rawc[0]
w0 = w[0]
shown = 0
for i in range(1, NS):
    ms = w[i] - w0
    cnt = (rawc[i] - c0) % M32
    est = cnt // ms
    if (ms > 400000 and shown < 24 and (i % 10 == 0 or abs(est - rate_all) >
                                        0.002 * rate_all and shown < 24)):
        print("  t=%7.1f s  cnt=%10d  ms=%7d  est=%6d  (true %.0f)"
              % (ms / 1000.0, cnt, ms, est, rate_all))
        shown += 1

print("\nA WINDOWED SERVO, REPLAYED ON THE SAME DATA (window = one dwell)")
ests = [dele[i] / float(w[i] - w[i - 1]) for i in range(1, NS)
        if w[i] > w[i - 1]]
print("  min %.2f  median %.2f  max %.2f  (true %.2f)"
      % (min(ests), statistics.median(ests), max(ests), rate_all))
print("  worst single-sample error %+.4f%%"
      % (100 * max(abs(e - rate_all) for e in ests) / rate_all))
