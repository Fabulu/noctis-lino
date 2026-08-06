r"""su-check.py -- read work/su-out.bin and diff it against the recon-C captures.

This is the LINO SIDE's own development instrument, not the wave's grader:
the wave's grader is Implementer 2's, is written independently, and joins the
two sides through tests/test_surface.py.  What this does is answer the only
question the implementer can answer alone -- does the 64,800-byte artefact the
port produced equal the 64,800-byte artefact the shipped DOS binary produced,
and if not, where.

Nothing here is compared to anything this port wrote on an earlier run.  The
right-hand side of every comparison is a file under
tests/gen/recon_w7a/out/, lifted out of the guest's RAM, or the manifest that
indexes them.

Usage:  python su-check.py [-v]
"""

import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RECON = os.path.join(ROOT, "tests", "gen", "recon_w7a", "out")

MAGIC = 826622293
KMAP, KOVL, KPAL, KSCAL, KLED, KTAIL, KTRL = 1, 2, 3, 4, 5, 6, 7
PHNAME = {0: "ENTRY", 1: "PROLOGUE", 2: "SEED", 3: "RNDPAT", 4: "CASE.ITER",
          5: "SDA", 6: "SWITCH.END", 7: "RENORM", 8: "MERGE", 9: "TERMINATOR",
          10: "POST", 11: "PALETTE", 12: "DONE"}

# Types 2/3/5/6 read the global secs (NOCTIS-0.CPP:4890/:4933/:5000/:5047).
# This formerly excused them as UNGRADED because the capture records no secs -
# which swallowed the exact niv-lr divergence (TYPE3ASSIGN, 53,373 bytes wrong)
# as "1 ungraded", i.e. the harness graded NOTHING for the wave's headline case.
# The lino corpus (work/su-corpus.txt) now carries the recovered secs, so the
# port reproduces these maps and they are graded like the rest.  No exemption.


def read_records(path):
    raw = open(path, "rb").read()
    u = struct.unpack("<%dI" % (len(raw) // 4), raw)
    recs, i = [], 0
    while i < len(u):
        if u[i] != MAGIC:
            raise SystemExit("bad magic at unit %d" % i)
        hdr = u[i:i + 16]
        bc = hdr[5]
        body = u[i + 16:i + 16 + bc]
        recs.append(dict(kind=hdr[2], w=hdr[3], h=hdr[4], case=hdr[6],
                         tag=hdr[7], body=body))
        i += 16 + bc
    return recs


def unpack_bytes(units, n):
    out = bytearray()
    for v in units:
        out += bytes(((v) & 255, (v >> 8) & 255, (v >> 16) & 255, (v >> 24) & 255))
    return bytes(out[:n])


def diff_report(a, b, label, width=360, limit=6):
    if a == b:
        return "%s: IDENTICAL (%d bytes)" % (label, len(a))
    d = [i for i in range(min(len(a), len(b))) if a[i] != b[i]]
    lines = ["%s: %d of %d bytes differ" % (label, len(d), len(a))]
    lines.append("    first at %d (row %d col %d) port=%d capture=%d"
                 % (d[0], d[0] // width, d[0] % width, a[d[0]], b[d[0]]))
    lines.append("    last  at %d (row %d col %d) port=%d capture=%d"
                 % (d[-1], d[-1] // width, d[-1] % width, a[d[-1]], b[d[-1]]))
    rows = sorted(set(i // width for i in d))
    lines.append("    %d distinct rows, %d distinct columns"
                 % (len(rows), len(set(i % width for i in d))))
    for i in d[:limit]:
        lines.append("      [%5d] r%03d c%03d  port %3d  capture %3d"
                     % (i, i // width, i % width, a[i], b[i]))
    return "\n".join(lines)


def main():
    verbose = "-v" in sys.argv
    recs = read_records(os.path.join(HERE, "su-out.bin"))
    man = json.load(open(os.path.join(RECON, "manifest.json")))
    seen, entries = set(), []
    for e in man:
        key = (tuple(e["star"]), e["body"])
        if key in seen:
            continue
        seen.add(key)
        entries.append(e)

    bycase = {}
    for r in recs:
        bycase.setdefault(r["case"], []).append(r)

    trailer = [r for r in recs if r["kind"] == KTRL]
    if trailer:
        t = trailer[-1]["body"]
        print("TRAILER cases=%d bad=%d corpus_io=%d tokens=%d cw=%04X flags=%d"
              % (t[0], t[1], t[2], t[3], t[4], t[5]))
    print()

    ncase = len(entries)
    passmap = failmap = 0
    passpal = failpal = 0

    for ci in range(ncase):
        e = entries[ci]
        rs = bycase.get(ci, [])
        mapr = [r for r in rs if r["kind"] == KMAP]
        ovlr = [r for r in rs if r["kind"] == KOVL]
        palr = [r for r in rs if r["kind"] == KPAL]
        tailr = [r for r in rs if r["kind"] == KTAIL]
        scalr = [r for r in rs if r["kind"] == KSCAL]
        ledr = [r for r in rs if r["kind"] == KLED]
        if not mapr:
            print("case %d %s: NO MAP RECORD" % (ci, e["tag"]))
            continue

        got = unpack_bytes(mapr[0]["body"], 64800)
        capfile = os.path.join(RECON, e["tag"] + ".p_background")
        cap = open(capfile, "rb").read()[:64800]

        s = scalr[0]["body"] if scalr else [0] * 16
        print("=== case %d  %s  type %d  colorbase %d  plwp %d"
              % (ci, e["tag"], s[1], s[2], s[5]))
        print("    rtperiod=%d rotation=%d term_start=%d term_end=%d seed=%d brt=%d"
              % (s[3], s[4], s[6], s[7], s[8],
                 s[15] - 0x100000000 if s[15] & 0x80000000 else s[15]))
        print("    draws: fast=%d brtl=%d   fast_fnv=%08X brtl_fnv=%08X"
              % (s[9], s[10], s[11], s[12]))
        print("    map_fnv=%08X  ovl_fnv=%08X  ledger phases=%d"
              % (s[13], s[14], len(ledr)))

        r = diff_report(got, cap, "    MAP")
        print(r)
        if got == cap:
            passmap += 1
        else:
            failmap += 1
            if verbose:
                bisect(ledr, got, cap)

        if tailr:
            tail = unpack_bytes(tailr[0]["body"], 752)
            print("    TAIL 64800..65551: %s"
                  % ("all zero" if not any(tail) else
                     "NON-ZERO at %d" % tail.index(next(b for b in tail if b))))

        if ovlr:
            go = unpack_bytes(ovlr[0]["body"], 32400)
            co = open(os.path.join(RECON, e["tag"] + ".objectschart"),
                      "rb").read()[:32400]
            print(diff_report(go, co, "    OVERLAY", width=180))

        if palr:
            gp = unpack_bytes(palr[0]["body"], 192)
            cp = e["palette_192_255"]
            cpb = bytes(v for t in cp for v in t)
            if gp == cpb:
                print("    PALETTE: IDENTICAL (64 triples)")
                passpal += 1
            else:
                bad = [i for i in range(192) if gp[i] != cpb[i]]
                print("    PALETTE: %d of 192 components differ, first entry %d"
                      " (%d,%d,%d) vs (%d,%d,%d)"
                      % (len(bad), bad[0] // 3,
                         gp[bad[0] // 3 * 3], gp[bad[0] // 3 * 3 + 1],
                         gp[bad[0] // 3 * 3 + 2],
                         cpb[bad[0] // 3 * 3], cpb[bad[0] // 3 * 3 + 1],
                         cpb[bad[0] // 3 * 3 + 2]))
                failpal += 1
        print()

    print("MAP      %d exact, %d FAILED, of %d"
          % (passmap, failmap, ncase))
    print("PALETTE  %d exact, %d FAILED, of %d" % (passpal, failpal, ncase))


def bisect(ledr, got, cap):
    print("    ledger phases (phase, tag, fast_n, brtl_n, fast_fnv, brtl_fnv):")
    for r in ledr[:8] + ledr[-4:]:
        b = r["body"]
        print("      %-11s tag=%-6d fast=%-7d brtl=%-7d f=%08X b=%08X m=%08X"
              % (PHNAME.get(b[0], b[0]), b[1], b[2], b[3], b[4], b[5], b[6]))


if __name__ == "__main__":
    main()
