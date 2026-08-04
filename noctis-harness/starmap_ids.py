"""Characterise the id values in STARMAP.BIN and locate GUIDE.BIN's phase shift."""

import struct
import sys
import math
import collections

STARMAP = r"C:\programmieren\noctis\niv-plus\data\STARMAP.BIN"
GUIDE = r"C:\programmieren\noctis\niv-plus\data\GUIDE.BIN"


def load_starmap():
    blob = open(STARMAP, "rb").read()[4:]
    recs = []
    for i in range(len(blob) // 32):
        r = blob[i * 32:(i + 1) * 32]
        recs.append((struct.unpack_from("<d", r, 0)[0],
                     r[8:28].rstrip(b" ").decode("latin-1"),
                     chr(r[29]), r[30:32].decode("latin-1")))
    return recs


def main():
    recs = load_starmap()
    stars = [r for r in recs if r[2] == "S"]
    planets = [r for r in recs if r[2] == "P"]
    print(f"{len(recs)} records: {len(stars)} S, {len(planets)} P")

    sids = [r[0] for r in stars]
    print(f"star id min={min(sids):.10g} max={max(sids):.10g}")
    absid = sorted(abs(v) for v in sids if v != 0)
    print(f"|id| percentiles: "
          + ", ".join(f"p{p}={absid[int(len(absid)*p/100)]:.6g}"
                      for p in (0, 1, 25, 50, 75, 99)))
    print(f"|id| max={absid[-1]:.10g}  cube-root of max ~= {absid[-1] ** (1 / 3):.1f} sectors")

    # duplicate ids inside the star catalogue itself
    c = collections.Counter(sids)
    dups = [(v, n) for v, n in c.items() if n > 1]
    print(f"distinct star ids: {len(c)}; ids used by >1 star record: {len(dups)}")
    for v, n in sorted(dups, key=lambda t: -t[1])[:5]:
        names = [r[1] for r in stars if r[0] == v]
        print(f"   id {v!r} x{n}: {names[:6]}")

    # Do any two *distinct* star ids fall within the +/-1e-5 lookup epsilon of
    # each other?  That is the catalogue's own collision rate, before we even
    # bring a generator into it.
    su = sorted(c)
    near = [(su[i], su[i + 1]) for i in range(len(su) - 1)
            if su[i + 1] - su[i] < 2e-5]
    print(f"distinct star ids closer than 2*idscale (2e-5): {len(near)} pairs")
    for a, b in near[:5]:
        na = [r[1] for r in stars if r[0] == a][:2]
        nb = [r[1] for r in stars if r[0] == b][:2]
        print(f"   {a!r} {na} <-> {b!r} {nb}  delta={b - a:.3e}")

    # planet ids are star id + planet index; check that relationship
    starset = set(sids)
    hits = 0
    for pid, name, t, tail in planets:
        base = pid - round(pid - math.floor(pid)) if False else None
        for k in range(1, 21):
            if any(abs((pid - k) - s) < 1e-5 for s in ()):  # placeholder
                pass
        hits += 0
    # cheap version: bucket star ids, look for pid - k
    from bisect import bisect_left
    su2 = sorted(starset)
    def near_star(v):
        i = bisect_left(su2, v - 1e-5)
        return i < len(su2) and su2[i] < v + 1e-5
    matched = 0
    for pid, name, t, tail in planets:
        try:
            k = int(tail)
        except ValueError:
            continue
        if near_star(pid - k):
            matched += 1
    print(f"planets whose (id - tailnumber) lands on a catalogued star id: "
          f"{matched}/{len(planets)}")

    # ---- GUIDE phase ----
    g = open(GUIDE, "rb").read()
    body = g[4:]
    n = len(body) // 84
    bad = []
    for i in range(n):
        r = body[i * 84:(i + 1) * 84]
        txt = r[8:84].rstrip(b"\x00")
        if txt and not all(32 <= ch <= 126 for ch in txt):
            bad.append(i)
    print(f"\nGUIDE: {len(bad)} records with non-printable text at stride-84 phase 4: {bad}")
    if bad:
        i = bad[0]
        off = 4 + i * 84
        print(f"  first bad at file offset {off}; surrounding bytes:")
        print(f"   {g[off-16:off+40]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
