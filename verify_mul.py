"""Diff L.in.oleum's software 64-bit multiply against Python's exact arithmetic.

Reads work/mulout.bin, which mulcheck.exe writes as 32-bit little-endian
units in the order (lo, hi, fold) per test vector.
"""
import struct
import sys

VECTORS = [
    (0x00000000, 0x00000000, "0 x 0"),
    (0x00000001, 0x00000001, "1 x 1"),
    (0xFFFFFFFF, 0xFFFFFFFF, "max x max"),
    (0x00010000, 0x00010000, "2^16 x 2^16 = 2^32 exactly"),
    (0x12345678, 0x76543210, "known-good vector"),
    (0xDEADBEEF, 0xCAFEBABE, "both above 2^31"),
    (0x7FFFFFFF, 0x7FFFFFFF, "largest positive signed"),
    (0x000186A0, 0x00030D40, "100000 x 200000, Noctis sector scale"),
]

MASK = 0xFFFFFFFF
PATH = sys.argv[1] if len(sys.argv) > 1 else r"C:\programmieren\linoleum\work\mulout.bin"

data = open(PATH, "rb").read()
expected_len = len(VECTORS) * 3 * 4
if len(data) != expected_len:
    print(f"SIZE MISMATCH: got {len(data)} bytes, expected {expected_len}")
    sys.exit(2)

got = struct.unpack("<" + "I" * (len(data) // 4), data)

failures = 0
for i, (a, b, label) in enumerate(VECTORS):
    lo_g, hi_g, fold_g = got[i * 3 : i * 3 + 3]

    product = a * b
    lo_e = product & MASK
    hi_e = (product >> 32) & MASK
    fold_e = (hi_e + lo_e) & MASK

    ok = (lo_g, hi_g, fold_g) == (lo_e, hi_e, fold_e)
    mark = "ok  " if ok else "FAIL"
    if not ok:
        failures += 1

    print(f"[{mark}] {a:#010x} * {b:#010x}   ({label})")
    if not ok:
        print(f"         lo   got {lo_g:#010x}  want {lo_e:#010x}")
        print(f"         hi   got {hi_g:#010x}  want {hi_e:#010x}")
        print(f"         fold got {fold_g:#010x}  want {fold_e:#010x}")

print()
print(f"{len(VECTORS) - failures}/{len(VECTORS)} vectors correct")
sys.exit(1 if failures else 0)
