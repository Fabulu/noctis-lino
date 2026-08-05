import struct, statistics
M32 = 1 << 32
raw = open(r"C:\programmieren\linoleum\work\probe-w5b2-rate.bin", "rb").read()
u = list(struct.unpack("<%dI" % (len(raw) // 4), raw))
NS = u[1]
rawc = u[16:16 + NS]
wal = u[16 + NS:16 + 2 * NS]
dele = u[16 + 2 * NS:16 + 3 * NS]
rep = u[0]
w = wal
truth_c = sum(dele[1:])
truth_m = w[-1] - w[0]
truth = truth_c / float(truth_m)
print("TRUE RATE over the whole run: %d counts / %d ms = %.4f cpms"
      % (truth_c, truth_m, truth))

# aggregate idle vs busy (each kind's own total counts over its own total ms)
for name, sel in (("idle (SLEEP dwell)", 0), ("busy (spin dwell)", 1)):
    c = sum(dele[i] for i in range(1, NS) if i % 2 == sel)
    m = sum(w[i] - w[i - 1] for i in range(1, NS) if i % 2 == sel)
    print("  %-20s %12d counts / %8d ms = %.4f cpms  (%+.4f%% vs whole run)"
          % (name, c, m, c / float(m), 100 * (c / float(m) - truth) / truth))

# the wrap, and whether the bucket containing it is anomalous
dec = [i for i in range(1, NS) if rawc[i] < rawc[i - 1]]
print("\nwraps at samples %s, wall t = %s s"
      % (dec, ["%.1f" % ((w[i] - w[0]) / 1000.0) for i in dec]))
for i in dec:
    print("  sample %3d: raw %10d -> %10d, unsigned delta %d, "
          "neighbours %d / %d"
          % (i, rawc[i - 1], rawc[i], dele[i], dele[i - 1], dele[i + 1]))
    dt = w[i] - w[i - 1]
    print("            implied rate across the wrap = %.3f cpms "
          "(%+.4f%% vs true)"
          % (dele[i] / float(dt), 100 * (dele[i] / float(dt) - truth) / truth))

# windowed estimates at several window lengths, built from the real samples
print("\nWINDOWED ESTIMATE vs WINDOW LENGTH, from the real stream")
print("  %8s %6s %10s %10s %10s %12s" %
      ("win ms", "n", "min", "median", "max", "worst error"))
for k in (1, 2, 4, 7, 15, 30):
    est = []
    for a in range(0, NS - k, k):
        c = sum(dele[a + 1:a + 1 + k])
        m = w[a + k] - w[a]
        if m > 0:
            est.append(c / float(m))
    if not est:
        continue
    worst = max(abs(e - truth) for e in est) / truth
    print("  %8d %6d %10.3f %10.3f %10.3f %11.4f%%"
          % (k * 1900, len(est), min(est), statistics.median(est), max(est),
             100 * worst))

print("\nHOW BIG IS EACH ERROR IN GAME TERMS (55 ms tick, per hour)")
for name, est in (("reported %d" % rep, float(rep)),
                  ("truth (integer) %d" % round(truth), float(round(truth)))):
    e = (est - truth) / truth
    print("  %-22s %+.4f%%  %+.4f ms/tick  %+.2f s/hour"
          % (name, 100 * e, 54.9254012 * e, 3600 * e))
print("  one integer cpms step   %+.4f%%  %+.4f ms/tick  %+.2f s/hour"
      % (100.0 / truth, 54.9254012 / truth, 3600.0 / truth))
