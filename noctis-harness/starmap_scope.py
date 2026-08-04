"""Bound the sector volume a sweep would have to cover.

Two independent estimates:
  1. cube-root of the catalogue id magnitudes (crude, since one axis can dominate);
  2. parsis coordinates that players typed into GUIDE.BIN entries (ground truth).
"""

import re
import struct
import sys
import collections

STARMAP = r"C:\programmieren\noctis\niv-plus\data\STARMAP.BIN"
GUIDE = r"C:\programmieren\noctis\niv-plus\data\GUIDE.BIN"


def guide_texts():
    body = open(GUIDE, "rb").read()[4:]
    n = len(body) // 84
    cur_id = None
    buf = []
    out = []
    for i in range(n):
        r = body[i * 84:(i + 1) * 84]
        oid = struct.unpack_from("<d", r, 0)[0]
        txt = r[8:84].rstrip(b"\x00").decode("latin-1")
        if oid != cur_id:
            if buf:
                out.append((cur_id, "".join(buf)))
            cur_id, buf = oid, [txt]
        else:
            buf.append(txt)
    if buf:
        out.append((cur_id, "".join(buf)))
    return out


def main():
    texts = guide_texts()
    print(f"GUIDE: {len(texts)} messages reassembled from 48376 records")

    joined = "\n".join(t for _, t in texts)
    print(f"total guide text {len(joined)} chars")

    for kw in ("PARSIS", "SECTOR", "COORD"):
        n = joined.count(kw)
        print(f"  occurrences of {kw!r}: {n}")

    # Player-typed parsis coordinates, e.g. "1234567;-987654;123456" or
    # "X 1234567 Y -987654 Z 123456".
    pat = re.compile(r"(-?\d{4,9})\s*[;,/ ]\s*(-?\d{4,9})\s*[;,/ ]\s*(-?\d{4,9})")
    coords = []
    for _, t in texts:
        for m in pat.finditer(t):
            v = tuple(int(g) for g in m.groups())
            if all(abs(x) < 100_000_000 for x in v):
                coords.append(v)
    print(f"\ncoordinate-like triples found in guide text: {len(coords)}")
    if coords:
        for axis, name in enumerate("XYZ"):
            vals = [c[axis] for c in coords]
            vals.sort()
            print(f"  {name}: min={vals[0]} max={vals[-1]} "
                  f"p5={vals[len(vals)//20]} p95={vals[-len(vals)//20]}  "
                  f"sector range {vals[0]//100000}..{vals[-1]//100000}")
        for c in coords[:15]:
            print(f"    {c}  -> sector {tuple(x//100000 for x in c)}"
                  f"  id~{(c[0]/1e5)*(c[1]/1e5)*(c[2]/1e5):.6g}")

    # Landmark ids hard-coded in noctis-1.cpp
    blob = open(STARMAP, "rb").read()[4:]
    recs = []
    for i in range(len(blob) // 32):
        r = blob[i * 32:(i + 1) * 32]
        recs.append((struct.unpack_from("<d", r, 0)[0],
                     r[8:28].rstrip(b" ").decode("latin-1"), chr(r[29])))
    print("\nlandmark ids hard-coded in niv-lr/src/noctis-1.cpp:")
    for label, scale, target in (("L3164", 1e6, -37828),
                                 ("L3187", 1e5, 1599551984),
                                 ("L3208", 1e8, -11543634)):
        got = [r for r in recs if int(r[0] * scale) == target]
        print(f"  {label}: identity*{scale:g} == {target} -> id {target/scale!r} "
              f"-> {[(r[1], r[2]) for r in got][:6]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
