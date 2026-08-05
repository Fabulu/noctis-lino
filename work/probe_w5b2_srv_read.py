"""Read probe-w5b2-srv.bin: the five servo batteries."""
import struct, sys, statistics

path = sys.argv[1] if len(sys.argv) > 1 else \
    r"C:\programmieren\linoleum\work\probe-w5b2-srv.bin"
raw = open(path, "rb").read()
u = list(struct.unpack("<%dI" % (len(raw) // 4), raw))
h = u[:16]
b1 = u[16:76]
b2 = u[76:136]
b3 = u[136:166]
b4 = u[166:238]
b5 = u[238:262]
rep, CPMSF, NCASE, NB, NW3, NW4, REP4, WINMS, NB5, base = h[:10]
print("reported cpms %d ; fabricated true rate %d ; servo window %d ms ; "
      "sweep origins %d ; ring base %d" % (rep, CPMSF, WINMS, NB, base))

WHY = {0: "applied", 1: "window <500ms", 2: "window implausible",
       3: "rate implausible"}


def show(name, blk):
    print("\n%s" % name)
    print("  %9s %12s %9s %8s %8s   %s"
          % ("elapsed", "counts", "ms", "raw est", "applied", "why"))
    for i in range(len(blk) // 6):
        t, cnt, ms, new, out, why = blk[i * 6:i * 6 + 6]
        ms_s = ms if ms < (1 << 31) else ms - (1 << 32)
        print("  %9d %12d %9d %8d %8d   %s%s"
              % (t, cnt, ms_s, new, out, WHY[why],
                 "" if out == CPMSF else "   <-- cpms MOVED"))


show("BATTERY 1 - shipped servo, bracketed against the start of the run", b1)
show("BATTERY 2 - same arithmetic, bracketed against the previous sample", b2)

print("\nBATTERY 3 - straddle sweep, %d origins per window length" % NB)
print("  %10s %10s %10s   %s" % ("window ms", "checks", "failures", "verdict"))
for i in range(NW3):
    wl, nchk, nfail = b3[i * 3:i * 3 + 3]
    lim = (1 << 32) // CPMSF
    exp = "expected exact" if wl < lim else "PAST 2^32/cpms - expected to fail"
    print("  %10d %10d %10d   %s" % (wl, nchk, nfail, exp))
print("  (2^32 / %d = %.1f ms = %.2f s is the longest window that can work)"
      % (CPMSF, (1 << 32) / float(CPMSF), (1 << 32) / float(CPMSF) / 1000))

print("\nBATTERY 4 - real windows against the real clocks")
allr = []
for k in range(NW4):
    rows = [(b4[(k * REP4 + i) * 2], b4[(k * REP4 + i) * 2 + 1])
            for i in range(REP4)]
    est = [c / float(m) for c, m in rows]
    allr.append((rows[0][1], est))
grand = statistics.median([e for _, es in allr for e in es])
print("  reference (median of every sample) = %.4f cpms" % grand)
print("  %10s %10s %10s %10s %12s" %
      ("window ms", "min", "median", "max", "worst error"))
for wl, est in allr:
    worst = max(abs(e - grand) for e in est) / grand
    print("  %10d %10.3f %10.3f %10.3f %11.4f%%"
          % (wl, min(est), statistics.median(est), max(est), 100 * worst))

show("BATTERY 5 - the midnight discontinuity (cases 0..3)", b5)
