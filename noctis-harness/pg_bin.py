#!/usr/bin/env python3
"""
pg_bin.py -- Wave 6a check C1: the third leg.

P1 is pg_ref.c (a transliteration of TDPOLYGS.H).
P2 is work/pg*.txt (a transliteration of TDPOLYGS.H).
Both read the same 1996 header text, so a shared misreading of a single asm
line survives both.  P3 answers the one question neither can: does the SHIPPED
BINARY agree with the header text they transliterated?

That is not hypothetical.  Recon B asserted that NOCTIS-0.CPP includes
tdpolygs.h with no prior #define, so the header defaults stand and the clip
rectangle is 10/310 with x_centro 160.  The binary says otherwise, and it says
so in four one-hit immediates and a six-float table.  This file decodes them.

Owner: bin: (byte offsets in a 1996 artifact).  It compares NOTHING to
pg_ref.c's own output -- it compares the binary to CONSTANTS RESTATED HERE,
and separately reports what pg_ref.exe compiled in, so the ledger row is
bin: vs cref:, never cref: vs cref:.

Usage:  python pg_bin.py [--exe NOCTIS.EXE] [--json]
Exit:   0 all checks pass, 1 otherwise.
"""

import argparse, json, os, struct, sys

NOCTIS = r"C:\programmieren\noctis\niv-plus\modules\NOCTIS.EXE"
POLYVERT = r"C:\programmieren\noctis\niv-plus\source\POLYVERT.EXE"

# What the port claims, restated here independently of pg_ref.c.
# Source: NOCTIS-D.H:122-132  (larghezza 306, altezza 180, x_centro 158,
# y_centro 100 => lbx 5, ubx 311, lby 10, uby 190).
CLAIM = dict(lbx=5, ubx=311, lby=10, uby=190, x_centro=158, y_centro=100)


def load(path):
    with open(path, "rb") as f:
        return f.read()


def find_all(buf, pat):
    out, i = [], 0
    while True:
        i = buf.find(pat, i)
        if i < 0:
            return out
        out.append(i)
        i += 1


def c706_hits(buf, imm):
    """`mov word ptr [disp16], imm16` == C7 06 dd dd ii ii."""
    return [i for i in find_all(buf, b"\xC7\x06")
            if struct.unpack_from("<H", buf, i + 4)[0] == imm]


class Checks:
    def __init__(self):
        self.rows = []
        self.ok = True

    def add(self, name, kind, passed, detail):
        # kind is EXACT or BOUND, printed so a reader never has to guess which.
        self.rows.append((name, kind, bool(passed), detail))
        if not passed:
            self.ok = False

    def report(self):
        w = max(len(r[0]) for r in self.rows)
        for name, kind, passed, detail in self.rows:
            print("%-*s  %-5s  %-4s  %s"
                  % (w, name, kind, "PASS" if passed else "FAIL", detail))
        print()
        print("C1 result: %s (%d checks, %d failed)"
              % ("PASS" if self.ok else "FAIL", len(self.rows),
                 sum(1 for r in self.rows if not r[2])))
        return 0 if self.ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default=NOCTIS)
    ap.add_argument("--polyvert", default=POLYVERT)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if not os.path.exists(a.exe):
        print("pg_bin: %s missing" % a.exe)
        return 2
    d = load(a.exe)
    C = Checks()

    # ---- C1.a  the four ranged1..ranged4 clamp immediates -------------------
    # TDPOLYGS.H:749/753/757/761 compile to `mov word ptr [max_x], ubx` etc.
    # Each value has EXACTLY ONE C7 06 hit in the whole 215,744-byte image, and
    # they sit 14 bytes apart in ubx, uby, lbx, lby order.
    hits = {k: c706_hits(d, v) for k, v in
            (("ubx", CLAIM["ubx"]), ("uby", CLAIM["uby"]),
             ("lbx", CLAIM["lbx"]), ("lby", CLAIM["lby"]))}
    for k in ("ubx", "uby", "lbx", "lby"):
        C.add("C1.a.%s_unique" % k, "EXACT", len(hits[k]) == 1,
              "value %d -> %d hit(s) %s"
              % (CLAIM[k], len(hits[k]), [hex(x) for x in hits[k]]))
    if all(len(hits[k]) == 1 for k in hits):
        offs = [hits[k][0] for k in ("ubx", "uby", "lbx", "lby")]
        deltas = [offs[i + 1] - offs[i] for i in range(3)]
        C.add("C1.a.spacing", "EXACT", deltas == [14, 14, 14],
              "offsets %s deltas %s (ranged1..ranged4)"
              % ([hex(o) for o in offs], deltas))

        # C1.b  the two jump conditions ARE the >= / < asymmetry.
        # ranged1/ranged2 are `jl` (7C): fire when max >= bound.
        # ranged3/ranged4 are `jge` (7D): fire when min <  bound.
        # layout per clamp: <cmp 5 bytes> <jcc 2 bytes> <inc si 1 byte> <C7 06 ...>
        # so the jcc opcode sits 3 bytes before the C7, and `inc si` (0x46) 1.
        jcc = [d[offs[i] - 3] for i in range(4)]
        inc = [d[offs[i] - 1] for i in range(4)]
        C.add("C1.b.asymmetry", "EXACT",
              jcc == [0x7C, 0x7C, 0x7D, 0x7D] and inc == [0x46] * 4,
              "jcc bytes %s (expect 7C 7C 7D 7D = jl jl jge jge), "
              "inc si %s (expect 46 x4)"
              % ([hex(b) for b in jcc], [hex(b) for b in inc]))

    # ---- C1.c  the counter-hypothesis leaves no trace -----------------------
    # If Recon B had been right the image would carry ubx=310 and lbx=10 in the
    # same encoding.  310 must have zero hits or the whole reading is wrong.
    for bad, why in ((310, "ubx if larghezza were 300/x_centro 160"),
                     (285, "ubx of the POLYVERT build"),
                     (35, "lbx of the POLYVERT build")):
        h = c706_hits(d, bad)
        C.add("C1.c.no_%d" % bad, "EXACT", len(h) == 0, "%s -> %d hit(s)" % (why, len(h)))

    # ---- C1.d  the float and long tables, contiguous ------------------------
    # long lbxl,ubxl,lbyl,ubyl  then  float lbxf,ubxf,lbyf,ubyf,x_centro_f,
    # y_centro_f  (TDPOLYGS.H:337-348) land as one 40-byte block in DATA.
    lq = struct.pack("<llll", CLAIM["lbx"], CLAIM["ubx"], CLAIM["lby"], CLAIM["uby"])
    fq = struct.pack("<ffffff", CLAIM["lbx"], CLAIM["ubx"], CLAIM["lby"],
                     CLAIM["uby"], CLAIM["x_centro"], CLAIM["y_centro"])
    lp = find_all(d, lq)
    C.add("C1.d.long_quad", "EXACT", len(lp) == 1,
          "lbxl,ubxl,lbyl,ubyl as 4 int32 -> %s" % [hex(x) for x in lp])
    fp = find_all(d, fq)
    C.add("C1.d.float_sextet", "EXACT", len(fp) == 1,
          "lbxf..y_centro_f as 6 float32 -> %s" % [hex(x) for x in fp])
    if len(lp) == 1 and len(fp) == 1:
        C.add("C1.d.adjacent", "EXACT", fp[0] - lp[0] == 16,
              "float table follows long table by %d bytes (expect 16)"
              % (fp[0] - lp[0]))

    # ---- C1.e  the offset-4 settlement, straight out of the image -----------
    # Segmento's general branch writes `mov byte ptr es:[di+4], 255`
    # == 26 C6 45 04 FF.  Exactly one, and NO es:[di],255 (26 C6 05 FF)
    # anywhere.  BUFFERMAP 4.1 says the 4 is farmalloc's offset; this is the
    # byte that proves the port must reproduce it.
    n_off4 = len(find_all(d, b"\x26\xC6\x45\x04\xFF"))
    C.add("C1.e.segmento_di4", "EXACT", n_off4 == 1,
          "`mov es:[di+4],255` occurrences = %d (expect 1)" % n_off4)
    n_vert = len(find_all(d, b"\x26\xC6\x04\xFF"))
    C.add("C1.e.segmento_si", "EXACT", n_vert == 1,
          "`mov es:[si],255` (vertical branch) occurrences = %d (expect 1)" % n_vert)

    # ---- C1.f  the two polymap scratch pixels -------------------------------
    for off, nm in ((b"\x26\xA2\x00\xFA", "es:[0xFA00] tinta"),
                    (b"\x26\xA2\x01\xFA", "es:[0xFA01] escrescenze")):
        n = len(find_all(d, off))
        C.add("C1.f.%s" % nm.split(":")[1].split()[0].strip("[]"), "EXACT", n == 1,
              "`mov %s, al` occurrences = %d (expect 1)" % (nm, n))
    # LR relocates these to adapted[64000] == es:[0xFA04]; that must be absent.
    n_lr = len(find_all(d, b"\x26\xA2\x04\xFA"))
    C.add("C1.f.not_relocated", "EXACT", n_lr == 0,
          "`mov es:[0xFA04], al` (LR's relocation) occurrences = %d (expect 0)" % n_lr)

    # ---- C1.g  instruction census ------------------------------------------
    # These are constant-free, so POLYVERT.EXE corroborates them even though it
    # is a DIFFERENT BUILD with a different clip rectangle (see C1.c).
    pv = load(a.polyvert) if os.path.exists(a.polyvert) else None
    census = (("dword_store", b"\x26\x66\x89\x05", 2,
               "mov es:[di],eax -- poly3d case 0 and case 4"),
              ("repe_scasb", b"\xF3\xAE", 8, "two per fill arm x four arms"),
              ("texel_add", b"\x64\x02\x2F", 12,
               "add ch,fs:[bx] -- 5 combine variants + bumper's second add, x2 detail levels"))
    for nm, pat, want, why in census:
        n = len(find_all(d, pat))
        extra = ""
        if pv is not None:
            extra = "  POLYVERT=%d" % len(find_all(pv, pat))
        C.add("C1.g.%s" % nm, "EXACT", n == want,
              "%d (expect %d)%s -- %s" % (n, want, extra, why))

    if pv is not None:
        # POLYVERT.CPP:76 does #define larghezza 250 and never includes
        # noctis-d.h, so its rectangle is 35/285/10/190 and x_centro is 160.
        # Recording this stops anyone using it to corroborate a CONSTANT.
        pvh = {k: c706_hits(pv, v) for k, v in
               (("ubx285", 285), ("lbx35", 35), ("uby190", 190), ("lby10", 10))}
        C.add("C1.h.polyvert_is_a_different_build", "EXACT",
              all(len(v) == 1 for v in pvh.values()),
              "POLYVERT clamps = 285/190/35/10 %s -- ADMISSIBLE ONLY FOR "
              "CONSTANT-FREE CODE" % {k: [hex(x) for x in v] for k, v in pvh.items()})

    # ---- what the C oracle actually compiled in -----------------------------
    # Reported, not compared here: comparing pg_bin's expectations to pg_ref's
    # compiled constants would be a same-owner row.  The grader owns that join.
    print("pg_bin: image=%s (%d bytes)" % (a.exe, len(d)))
    print("pg_bin: claim  lbx=%(lbx)d ubx=%(ubx)d lby=%(lby)d uby=%(uby)d "
          "x_centro=%(x_centro)d y_centro=%(y_centro)d" % CLAIM)
    print()
    rc = C.report()
    if a.json:
        print(json.dumps([{"name": n, "kind": k, "pass": p, "detail": dd}
                          for n, k, p, dd in C.rows], indent=1))
    return rc


if __name__ == "__main__":
    sys.exit(main())
