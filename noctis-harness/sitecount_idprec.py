# Category (d) probe. isthere() identifies a star not by its coordinates but by
# a DOUBLE-precision product:
#
#     laststar_id = (x*1e-5) * (y*1e-5) * (z*1e-5)      NOCTIS-0.CPP:5686-5698
#     accept if  star_id - 1e-5  <  laststar_id  <  star_id + 1e-5
#
# L.in.oleum's ** is MUL.f on 32-bit units, i.e. IEEE single. This script asks
# whether single precision can even represent that acceptance window, using the
# real coordinate magnitudes produced by the already-verified galaxy hash in
# work/galaxy.bin (records of 5 x int32: temp_x, temp_y, temp_z, netpos, flags).

import struct, os

BIN = r"C:\programmieren\linoleum\work\galaxy.bin"
IDSCALE = 0.00001

data = open(BIN, "rb").read()
n = len(data) // 20
recs = [struct.unpack_from("<5i", data, i * 20) for i in range(n)]
print("records in galaxy.bin: %d" % n)

ids = []
for tx, ty, tz, netpos, flags in recs:
    v = (tx * IDSCALE) * (ty * IDSCALE) * (tz * IDSCALE)
    ids.append(v)

mag = max(abs(v) for v in ids)
print("|coord| max          = %d" % max(max(abs(r[0]), abs(r[1]), abs(r[2])) for r in recs))
print("|laststar_id| max     = %.6f" % mag)

import math
def ulp_single(x):
    if x == 0:
        return 0.0
    e = math.frexp(abs(x))[1] - 1
    return 2.0 ** (e - 23)

def ulp_double(x):
    if x == 0:
        return 0.0
    e = math.frexp(abs(x))[1] - 1
    return 2.0 ** (e - 52)

print()
print("acceptance half-window = %g" % IDSCALE)
print("single ulp at max |id| = %g   -> window/ulp = %.2f"
      % (ulp_single(mag), IDSCALE / ulp_single(mag) if ulp_single(mag) else float("inf")))
print("double ulp at max |id| = %g   -> window/ulp = %.2f"
      % (ulp_double(mag), IDSCALE / ulp_double(mag) if ulp_double(mag) else float("inf")))
print()

# How many of the real ids would a single-precision recomputation push outside
# the +-1e-5 window around the double-precision value?
import ctypes
def to_single(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]

outside = 0
worst = 0.0
for tx, ty, tz, netpos, flags in recs:
    d = (tx * IDSCALE) * (ty * IDSCALE) * (tz * IDSCALE)
    s = to_single(to_single(to_single(tx * to_single(IDSCALE))
                            * to_single(ty * to_single(IDSCALE)))
                  * to_single(tz * to_single(IDSCALE)))
    err = abs(s - d)
    worst = max(worst, err)
    if err >= IDSCALE:
        outside += 1
print("sectors where a single-precision id falls outside the +-1e-5 window: %d / %d"
      % (outside, n))
print("worst single-vs-double id error: %g  (window is %g)" % (worst, IDSCALE))

# galaxy.bin only samples 7x7x7 sectors around the origin. The game STARTS at
# dzat_x = +3797120 (NOCTIS-0.CPP:780) and the galaxy runs far wider, so scale
# the same measurement up to realistic coordinates.
print()
print("extrapolation to real play coordinates:")
for coord in (377489, 3797120, 10_000_000, 50_000_000):
    idmag = (coord * IDSCALE) ** 3
    u = ulp_single(idmag)
    print("  |coord|=%-10d -> |id|~%-14.1f single ulp=%-12g window/ulp=%8.3f  %s"
          % (coord, idmag, u, IDSCALE / u,
             "OK" if IDSCALE / u > 4 else "SINGLE PRECISION TOO COARSE"))
