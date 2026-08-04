"""checkpat.py - verify the register file after each generated pattern ran."""

import struct
import sys

sys.path.insert(0, ".")
from mulpat_expect import EXPECTED  # noqa: E402
from genmul import LINO             # noqa: E402

PATH = r"C:\programmieren\linoleum\work\mulpat.bin"

blob = open(PATH, "rb").read()
if len(blob) != 25 * 5 * 4:
    raise SystemExit(f"{PATH}: {len(blob)} bytes, expected {25 * 5 * 4}")

got = [struct.unpack_from("<5I", blob, k * 20) for k in range(25)]

bad = 0
for k, (g, e) in enumerate(zip(got, EXPECTED)):
    r1, r2 = divmod(k, 5)
    if list(g) == e:
        continue
    bad += 1
    print(f"  FAIL  {LINO[r1]} *% {LINO[r2]}")
    for i in range(5):
        if g[i] != e[i]:
            role = "op1" if i == r1 else ("op2" if i == r2 else "PRESERVED")
            print(f"        {LINO[i]} ({role:<9}) got {g[i]:08X}  want {e[i]:08X}")

print()
if bad:
    print(f"{25 - bad}/25 patterns correct, {bad} FAILED")
    sys.exit(1)

print("all 25 patterns correct:")
print("  operand 1 receives the low 32 bits")
print("  operand 2 receives the high 32 bits")
print("  every non-operand register preserved exactly")
print()
# A *% D is pattern index 3 (r1=A=0, r2=D=3); its high half lands in D.
lo, hi = got[3][0], got[3][3]
print(f"  A *% D  ->  low = {lo:08X}   high = {hi:08X}")
print(f"    12345678 * -1 = -12345678, so signed (imul) gives high FFFFFFFF;")
print(f"    unsigned (mul) would have given 12345677.")
