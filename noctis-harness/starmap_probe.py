"""Verify the on-disk layout of STARMAP.BIN and GUIDE.BIN against the bytes.

Nothing here is taken on trust from the track brief: every field offset is
re-derived from the data and cross-checked against the reader in
niv-lr/src/noctis-0.cpp (search_id_code) and the writer in
niv-lr/src/goesnet/cast.cpp.
"""

import collections
import struct
import sys

STARMAP = r"C:\programmieren\noctis\niv-plus\data\STARMAP.BIN"
GUIDE = r"C:\programmieren\noctis\niv-plus\data\GUIDE.BIN"


def probe_starmap():
    blob = open(STARMAP, "rb").read()
    print(f"STARMAP.BIN {len(blob)} bytes")
    hdr = struct.unpack_from("<I", blob, 0)[0]
    print(f"  header dword = {hdr} (0x{hdr:08X}); file size = {len(blob)}; equal={hdr == len(blob)}")
    body = blob[4:]
    print(f"  body {len(body)} bytes, /32 = {len(body) / 32}")

    n = len(body) // 32
    types = collections.Counter()
    tomb = 0
    byte28 = collections.Counter()
    tail = collections.Counter()
    namelen = collections.Counter()
    badname = []
    ids = []

    for i in range(n):
        r = body[i * 32:(i + 1) * 32]
        if r[0:8] == b"Removed:":
            tomb += 1
            continue
        ids.append(struct.unpack_from("<d", r, 0)[0])
        types[r[29:30]] += 1
        byte28[r[28:29]] += 1
        tail[r[30:32]] += 1
        name = r[8:29]
        stripped = name.rstrip(b" ")
        namelen[len(stripped)] += 1
        if any(c < 32 or c > 126 for c in stripped) or b" " * 3 in stripped:
            if len(badname) < 10:
                badname.append((i, name))

    print(f"  records: {n}, tombstones('Removed:'): {tomb}, live: {n - tomb}")
    print(f"  byte29 (type tag) histogram: {dict(types)}")
    print(f"  byte28 histogram (top 5): {byte28.most_common(5)}")
    print(f"  bytes30-31 histogram (top 12): {tail.most_common(12)}")
    print(f"  name length (bytes 8..28 rstrip ' ') max={max(namelen)} "
          f"counts>=20: {[(k, namelen[k]) for k in sorted(namelen) if k >= 20]}")
    print(f"  suspicious names: {badname[:5]}")

    # Are the tail digits consistent with the 'S%02d'/'P%02d' sprintf in
    # update_star_label/update_planet_label?
    for t in (b"S", b"P"):
        sub = collections.Counter()
        for i in range(n):
            r = body[i * 32:(i + 1) * 32]
            if r[0:8] == b"Removed:":
                continue
            if r[29:30] == t:
                sub[r[30:32]] += 1
        print(f"  type {t.decode()}: tail values -> {sorted(sub.items())[:20]}")

    return ids, body, n


def probe_guide():
    blob = open(GUIDE, "rb").read()
    print(f"\nGUIDE.BIN {len(blob)} bytes")
    hdr = struct.unpack_from("<I", blob, 0)[0]
    print(f"  header dword = {hdr} (0x{hdr:08X}); equal to size = {hdr == len(blob)}")
    body = blob[4:]
    print(f"  body {len(body)} bytes, /84 = {len(body) / 84}")
    n = len(body) // 84
    printable = 0
    nonascii = []
    ids = []
    for i in range(n):
        r = body[i * 84:(i + 1) * 84]
        ids.append(struct.unpack_from("<d", r, 0)[0])
        txt = r[8:84].rstrip(b"\x00")
        if all(32 <= c <= 126 for c in txt):
            printable += 1
        elif len(nonascii) < 5:
            nonascii.append((i, r[8:84]))
    print(f"  records {n}; text field (8..83) fully printable after NUL-strip: "
          f"{printable}/{n} = {100.0 * printable / n:.3f}%")
    for i, t in nonascii:
        print(f"    non-printable rec {i}: {t!r}")
    uniq = len(set(ids))
    print(f"  distinct ids {uniq} (messages span multiple 84-byte records, same id repeated)")
    return ids


def main():
    ids, body, n = probe_starmap()
    guide_ids = probe_guide()

    sids = set()
    for i in range(n):
        r = body[i * 32:(i + 1) * 32]
        if r[0:8] == b"Removed:":
            continue
        sids.add(struct.unpack_from("<d", r, 0)[0])
    gset = set(guide_ids)
    print(f"\n  GUIDE ids present in STARMAP: {len(gset & sids)}/{len(gset)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
