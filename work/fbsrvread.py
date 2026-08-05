#!/usr/bin/env python3
"""fbsrvread.py - read work/fbsrv.bin, the servo battery's FBDUMP v2 stream.

Every expected value below is recomputed here in Python, from the same rule the
lino computes it from, and printed beside what the lino produced.

Usage: python fbsrvread.py work/fbsrv.bin
"""
import struct
import sys
import hashlib

MAGIC = 0x46424431
WHY = {0: "applied", 1: "clamp-lo", 2: "clamp-hi", 3: "rej-short", 4: "rej-long"}
M32 = 1 << 32

SCAL = ["SVRATE", "SRVMIN", "SRVMAX", "CALMIN", "SRVLOGN",
        "round_case_truncated", "round_case_rounded",
        "clampfloor_after_1", "clampfloor_after_5", "floorless_step",
        "rebase_window_1_ms", "rebase_why_1", "rebase_window_2_ms",
        "rebase_why_2",
        "fold_at_235959_900", "fold_at_000000_100", "fold_at_000000_300",
        "fold_delta", "midnight_why", "midnight_cpms",
        "ring_cases", "ring_failures", "cpms_reported", "cpms_seed",
        "SVNW", "SVNF", "SVNO", "SVRATCH", "SVNANCH", "SVNRING",
        "servolog_overflow", "servo_firings", "rebase_counts_1",
        "rebase_counts_2"]


def records(buf):
    off = 0
    while off + 64 <= len(buf):
        h = struct.unpack_from("<16I", buf, off)
        assert h[0] == MAGIC
        n = h[5]
        yield h[8], struct.unpack_from("<%dI" % n, buf, off + 64) if n else ()
        off += 64 + 4 * n


def s32(v):
    return v - M32 if v >= (1 << 31) else v


buf = open(sys.argv[1], "rb").read()
print("%s  %d bytes  sha256 %s\n" %
      (sys.argv[1], len(buf), hashlib.sha256(buf).hexdigest()))
by = dict(records(buf))

s = by[13]
print("=== scalars ===")
for i, nm in enumerate(SCAL):
    print("  %-24s %14d" % (nm, s32(s[i])))
RATE = s[0]

print("\n=== B1  window lengths, three consecutive firings each ===")
print("  ms       fire  counts        new   cpms  why          expected")
w = by[19]
for i in range(len(w) // 8):
    ms, f, cnt, new, cp, why, base, logn = w[8 * i:8 * i + 8]
    exp = "reject-short" if ms < 4000 else ("reject-long" if ms > 60000
                                            else "accept ~%d" % RATE)
    print("  %-8d %d     %-13d %-5d %-5d %-12s %s" %
          (ms, f, cnt, new, cp, WHY.get(why, why), exp))

print("\n=== B2  the OLD servo, anchored at the run start, replayed ===")
print("  elapsed_ms   counts(mod 2^32)  cpms_naive  true  after 20 clamps")
o = by[20]
for i in range(len(o) // 4):
    el, cnt, naive, rat = o[4 * i:4 * i + 4]
    print("  %-12d %-17d %-11d %-5d %d" % (el, cnt, naive, RATE, rat))
    exp_cnt = (el * RATE) % M32
    assert cnt == exp_cnt, (cnt, exp_cnt)
    assert naive == exp_cnt // el

print("\n=== B3  rounding ===")
cnt = RATE * 14061 + 7031
print("  cnt = %d*14061 + 7031 = %d" % (RATE, cnt))
print("  truncated  lino %d   python %d" % (s[5], cnt // 14061))
print("  rounded    lino %d   python %d" % (s[6], (cnt + 14061 // 2) // 14061))

print("\n=== B4  the clamp floor ===")
print("  from cpms 99 with a correct %d sample:" % RATE)
print("    with the floor    : after 1 = %d, after 5 = %d" % (s[7], s[8]))
print("    floorless step 99/100 = %d  -> band [99,99], absorbing" % s[9])

print("\n=== B5  re-basing ===")
print("  firing 1 window %d ms  counts %d  why %s" % (s32(s[10]), s[32], WHY.get(s[11])))
print("  firing 2 window %d ms  counts %d  why %s" % (s32(s[12]), s[33], WHY.get(s[13])))
print("  re-based iff firing 2's window is small and refused")

print("\n=== B6  midnight ===")
print("  folded 23:59:59.900 -> %d" % s[14])
print("  folded 00:00:00.100 -> %d   (delta %d, expected 200)" % (s[15], s32(s[17])))
print("  folded 00:00:00.300 -> %d" % s[16])
print("  unfolded window -86,399,800 ms -> why %s, cpms unchanged at %d"
      % (WHY.get(s[18]), s[19]))

print("\n=== B7  ring sweep ===")
print("  %d cases, %d failures" % (s[20], s[21]))

print("\n=== servo log ===")
sl = by.get(11, ())
for i in range(len(sl) // 3):
    print("  tick %d  cpms %d  why %s" %
          (sl[3 * i], sl[3 * i + 1], WHY.get(sl[3 * i + 2])))
