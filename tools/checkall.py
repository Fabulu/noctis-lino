"""checkall.py - verify all 121 MUL-split patterns after execution."""

import struct
import sys

sys.path.insert(0, ".")
from genmul import LINO  # noqa: E402

TAG = "mulallu" if "--unsigned" in sys.argv else "mulall"
mod = __import__(f"{TAG}_expect")
EXPECTED, NAMES = mod.EXPECTED, mod.NAMES

PATH = rf"C:\programmieren\linoleum\work\{TAG}.bin"
PERPAT = 7
SLOTS = LINO + ["m1", "m2"]

blob = open(PATH, "rb").read()
n = len(EXPECTED)
if len(blob) != n * PERPAT * 4:
    raise SystemExit(f"{PATH}: {len(blob)} bytes, expected {n * PERPAT * 4}")

got = [struct.unpack_from(f"<{PERPAT}I", blob, k * PERPAT * 4) for k in range(n)]

bad = []
for k, (g, e) in enumerate(zip(got, EXPECTED)):
    if list(g) != e:
        bad.append(k)

for k in bad[:12]:
    print(f"  FAIL  [{k:>3}] {NAMES[k]}")
    for i in range(PERPAT):
        if got[k][i] != EXPECTED[k][i]:
            print(f"          {SLOTS[i]:<3} got {got[k][i]:08X}  "
                  f"want {EXPECTED[k][i]:08X}")
if len(bad) > 12:
    print(f"  ... and {len(bad) - 12} more")

print()
if bad:
    print(f"{n - len(bad)}/{n} patterns correct, {len(bad)} FAILED")
    sys.exit(1)

print(f"all {n} patterns correct across every operand configuration:")
print("  operand 1 receives the low 32 bits")
print("  operand 2 receives the high 32 bits")
print("  every non-operand register and memory cell preserved exactly")
