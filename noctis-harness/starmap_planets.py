"""The planet records as a second, independent ground truth.

Noctis names a planet by its parent star's identity plus the planet's index
in the system: prepare_nearstar looks up search_id_code(nearstar_identity +
n, 'P') (noctis-0.cpp:3788), and the index n is the two ASCII digits sitting
in bytes 30..31 of the record. So subtracting that integer from a planet's
id should land exactly on its parent star's id.

This is worth running because it involves NO generator at all. It is a
structural relation inside STARMAP.BIN, and it does two things:

  * it confirms the record layout - the type tag at 29, the body index at
    30..31 - against 29,999 records that were never used to derive it;
  * it yields parent identities for systems whose STAR record was never
    written, which enlarges the ground truth the generator is judged
    against beyond the 7,579 'S' records.

Nothing here depends on work/, on the L.in.oleum build, or on anything this
project computed.
"""

import struct
import sys
from bisect import bisect_left

STARMAP = r"C:\programmieren\noctis\niv-plus\data\STARMAP.BIN"
IDSCALE = 1e-5


def load():
    blob = open(STARMAP, "rb").read()[4:]
    recs = []
    for i in range(len(blob) // 32):
        r = blob[i * 32:(i + 1) * 32]
        recs.append((i,
                     struct.unpack_from("<d", r, 0)[0],
                     r[8:28].rstrip(b" ").decode("latin-1"),
                     chr(r[29]),
                     r[30:32].decode("latin-1"),
                     r[0:8]))
    return recs


def usable(raw8):
    e = (struct.unpack("<II", raw8)[1] >> 20) & 0x7FF
    return 0 < e < 0x7FF


def main():
    recs = load()
    stars = [r for r in recs if r[3] == "S"]
    planets = [r for r in recs if r[3] == "P"]
    print(f"{len(recs)} records: {len(stars)} 'S', {len(planets)} 'P'")

    star_ids = sorted({r[1] for r in stars if usable(r[5])})
    star_name = {}
    for r in stars:
        star_name.setdefault(r[1], r[2])
    print(f"{len(star_ids)} distinct usable star ids")

    # index field: is it really two ASCII digits?
    badidx = [r for r in planets if not r[4].isdigit()]
    print(f"planet records whose bytes 30..31 are not two digits: {len(badidx)}")
    for r in badidx[:5]:
        print(f"   #{r[0]} {r[2]!r} tail={r[4]!r}")

    parents = {}
    for i, v, name, tag, idx, raw in planets:
        if not idx.isdigit() or not usable(raw):
            continue
        parents.setdefault(v - int(idx), []).append((name, int(idx)))

    exact = near = far = 0
    farlist = []
    new_ids = []
    for p in parents:
        j = bisect_left(star_ids, p)
        cands = star_ids[max(0, j - 1):j + 2]
        if any(c == p for c in cands):
            exact += 1
        elif any(abs(c - p) < IDSCALE for c in cands):
            near += 1
        else:
            far += 1
            farlist.append(p)
            new_ids.append(p)

    print(f"\ndistinct parent identities derived from planet records: {len(parents)}")
    print(f"  land on an 'S' record id in EXACT float equality : {exact}")
    print(f"  land within the lookup epsilon (1e-5) but not ==  : {near}")
    print(f"  no 'S' record within the epsilon at all           : {far}")
    print(f"\n{exact} exact hits out of {len(parents)} is a check of the record")
    print("layout that never touches the galaxy generator: the type tag, the")
    print("body index field and the id arithmetic all have to be read right")
    print("for a planet's id minus its index to fall exactly on a star's id.")

    combined = set(star_ids) | set(new_ids)
    print(f"\nground truth id set:")
    print(f"  from 'S' records                : {len(star_ids)}")
    print(f"  added by planet-derived parents : {len(new_ids)}")
    print(f"  combined                        : {len(combined)}")
    print("\nThose additions are systems whose STAR record was never written -")
    print("a player named the planets but not the sun. They are as real as the")
    print("'S' records and they are not in the 7577 the match rate is against.")

    print("\nexamples of planet-derived parents with no 'S' record:")
    for p in sorted(farlist, key=abs)[:8]:
        kids = sorted(parents[p], key=lambda t: t[1])[:4]
        print(f"   parent id {p!r:<22} planets " +
              ", ".join(f"{n}({i})" for n, i in kids))
    return 0


if __name__ == "__main__":
    sys.exit(main())
