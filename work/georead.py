"""georead.py -- decode work/geocast.bin and print it with its own labels.

Reads nothing else.  Every expected value printed alongside is recomputed
here from Python's own float arithmetic where Python can do it, and marked
"model" where it cannot (Python has no 80-bit type on win32, so the LIVE
readings are hardware-only -- that asymmetry is the whole point of the probe).
"""
import struct
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "geocast.bin")

raw = open(PATH, "rb").read()
u = list(struct.unpack("<64i", raw[:256]))
U = [x & 0xFFFFFFFF for x in u]


def f64(lo, hi):
    return struct.unpack("<d", struct.pack("<II", lo & 0xFFFFFFFF, hi & 0xFFFFFFFF))[0]


print("file        %s  %d bytes" % (PATH, len(raw)))
print("magic       %08X  %s" % (U[0], "GEOC ok" if U[0] == 0x47454F43 else "*** BAD ***"))
print("version     %d   units %d" % (u[1], u[2]))
print("cw at start %04X  (expect 033F -- 133Fh masked with 0F3Fh)" % U[3])
print("cw ambient  %04X  (what FEnter found)" % U[45])
print("fld1 guard  lo=%08X hi=%08X  %s" %
      (U[4], U[5], "ok" if (U[4], U[5]) == (0, 0x3FF00000) else "*** LAYOUT BAD ***"))
print("stack top   %d (expect 0)" % u[6])
print()

print("BATTERY 1  (long)(1.0/41.0*41.0)")
print("  live  (nothing stored)             = %d" % u[7])
print("  spill after the divide             = %d" % u[8])
print("  spill after the multiply           = %d" % u[9])
sc = f64(U[10], U[11])
print("  fl64 via the scalar route          = %.20g   bits %08X%08X" % (sc, U[11], U[10]))
print("  python 1.0/41.0*41.0               = %.20g   int() = %d" % (1.0 / 41.0 * 41.0, int(1.0 / 41.0 * 41.0)))
print()


def bat(name, n_i, nd_i, first_i, live_i, spill_i, x_i=None, shape=""):
    n = u[n_i]
    nd = u[nd_i]
    print("%s  %s" % (name, shape))
    print("  inputs %d   disagreements %d   (%.2f%%)" % (n, nd, 100.0 * nd / n if n else 0.0))
    if nd:
        print("  first at index %d :  live=%d  spill=%d" % (u[first_i], u[live_i], u[spill_i]))
        if x_i is not None:
            x = f64(U[x_i], U[x_i + 1])
            print("  x there = %.20g   bits %08X%08X" % (x, U[x_i + 1], U[x_i]))
    print()


bat("BATTERY 2", 12, 13, 14, 15, 16, 17, "K=10, x = fl64(k)/10.0")
bat("BATTERY 3", 19, 20, 21, 22, 23, 24, "K=10, x = 21.0 + fl64(r)/100.0   (:4089 orb_seed shape)")
bat("BATTERY 4", 26, 27, 28, 29, 30, 31, "K=300, x = fl64(r)/1000.0        (:4195 shape)")
bat("BATTERY 5", 33, 34, 35, 36, 37, None, "x + 10*fabs(y)                   (:4092 / :4198 shape)")

print("BATTERY 6  CONTROL, exact by construction, K=300 on a binary32 value")
print("  inputs %d   disagreements %d   %s" %
      (u[38], u[39], "ok" if u[39] == 0 else "*** CONTROL FAILED - the shape analysis is wrong ***"))
print()

print("BATTERY 7  int16 narrowing at the call boundary, sign extended")
for lbl, i, want in (("218231", 40, ((218231 & 0xFFFF) ^ 0x8000) - 0x8000),
                     ("-218231", 41, (((-218231) & 0xFFFF) ^ 0x8000) - 0x8000),
                     ("25816", 42, ((25816 & 0xFFFF) ^ 0x8000) - 0x8000)):
    print("  GeoChop16(%-8s) = %-8d   python model %-8d  %s" %
          (lbl, u[i], want, "ok" if u[i] == want else "*** MISMATCH ***"))
print()
print("BATTERY 8  __ftol is `fistp qword`; a 32-bit fistp is not the same thing")
print("  x = 3.0e9   fistp qword, low 32 = %d" % (u[46] & 0xFFFFFFFF))
print("              fistp dword         = %08X  (integer indefinite)" % (u[47] & 0xFFFFFFFF))
print("              what random() sees  = %d" % u[48])
print()
print("stack top at end %d (expect 0)   cw at end %04X (expect 033F)" % (u[43], U[44]))
