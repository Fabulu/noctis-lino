#!/usr/bin/env python3
"""sp-break.py - the Wave 6b sabotage battery.

One REAL one-line defect per surface the page checks claim to cover,
because "the page check bites" is a claim about a rasteriser, not about a
bitmap.  Each sabotage is a copy of ONE library carrying ONE edit, plus a
copy of the driver that links that copy instead of the original - so a
sabotage cannot accidentally also change the harness.

Every build is made from scratch on every run.  Nothing here reads a
stored .bin; the clean build is rebuilt and rerun in the same pass and
each sabotage is compared against it record by record.

THE NULL-INPUT TEST runs first and last: the CLEAN build is fed to the
same comparison and must come out NOT CAUGHT.  A matrix that reports a
catch for the unmodified program is measuring nothing, and that single
call is the whole of the lino_break_matrix defect HARNESSAUDIT 5.3 names.

Usage:  python work/sp-break.py [name ...]
"""

import hashlib
import os
import struct
import subprocess
import sys

W = os.path.dirname(os.path.abspath(__file__))
LINO = os.path.dirname(W)
BUILD = os.path.join(LINO, "lino_build.ps1")
RUN = os.path.join(LINO, "tests", "linorun.ps1")
OUT = os.path.join(W, "sp-out.bin")

# ----------------------------------------------------------------------
# name -> (library, [(old, new), ...], what it should move)
# ----------------------------------------------------------------------
SABOTAGE = {

    # ---- spglobe -----------------------------------------------------
    "GLOBEOFF1": ("spglobe", [(
        "\tA = [GBdi]; ? A '< 6 -> SP gr ry0;",
        "\tA = [GBdi]; ? A '< 7 -> SP gr ry0;")],
        "niv-lr's off-by-one on globe's LOW Y bound; one arm only"),

    "GMAN4": ("spglobe", [(
        '    "SP gmn b"\n'
        "\tA = spgmt; A + [GBi]; A + [SPk];\n"
        "\tC = [GBdi]; C + 4; C + [A];\n"
        "\t[SPoff] = C;\n",
        '    "SP gmn b"\n'
        "\tA = spgmt; A + [GBi]; A + [SPk];\n"
        "\tC = [GBdi]; C + 4; C + [A];\n"
        "\t[SPoff] = C;\n"
        "\tA = [GBgman]; ? A != 4 -> SP gmn nb;\n"
        "\tA = [SPk]; ? A != 15 -> SP gmn nb;\n"
        "\tA = [SPoff]; A - 4; A & 65535; [SPoff] = A;\n"
        '    "SP gmn nb"\n')],
        "gman4x4 drops farmalloc's offset on its last store"),

    "CURSORCLIP": ("spglobe", [(
        "\tA = [GBbx]; A + 1; A & 65535; [GBbx] = A;\n\t-> SP gr next;",
        "\tA = [GBbx]; A & 65535; [GBbx] = A;\n\t-> SP gr next;")],
        "clipout forgets 'add bx,1', so the tapestry cursor stalls"),

    "GLOBESAT": ("spglobe", [(
        "\tA = [GBdl]; ? A '>= [GBt] -> SP gr asis;\n"
        "\t[GBdl] = [GBt];\n"
        '    "SP gr asis"\n'
        "\tA = [GBcmask]; A & 255; C = [GBdl]; C | A; [GBdl] = C;",
        "\tA = [GBcmask]; A & 255; C = [GBdl]; C | A; [GBdl] = C;\n"
        "\tA = [GBdl]; ? A '>= [GBt] -> SP gr asis;\n"
        "\t[GBdl] = [GBt];\n"
        '    "SP gr asis"\n')],
        "the colormask OR is applied BEFORE the saturation floor"),

    # ---- spglow ------------------------------------------------------
    "GLOWCLAMP": ("spglow", [(
        "\tA = [GLdi]; ? A '>= 10 -> SP gl yhi;\n"
        "\t[GLylo]+;\n"
        "\t-> SP gl yok;\n"
        '    "SP gl yhi"\n'
        "\tA = [GLdi]; ? A '< 190 -> SP gl yok;\n"
        "\t[GLyhi]+;\n"
        '    "SP gl yok"\n',
        "\tA = [GLdi]; ? A '<= 10 -> SP gl clipout;\n"
        "\tA = [GLdi]; ? A '>= 190 -> SP gl clipout;\n"
        '    "SP gl yok"\n')],
        "niv-lr's fabricated AND-clip where vanilla has a vacuous OR"),

    "GLOWSHIFT": ("spglow", [(
        "\tA = [GLcol]; A & 63; A > 2; C = [GLcol]; C & 192; A | C; [GLbh] = A;",
        "\tA = [GLcol]; A & 63; A > 1; C = [GLcol]; C & 192; A | C; [GLbh] = A;")],
        "the dark-side colour uses >>1 instead of >>2"),

    "GLOWDEC": ("spglow", [(
        "\tA = [GLdx]; A & 3;\n\t? A = 0 -> SP gl doit;",
        "\tA = [GLsi]; A & 7;\n\t? A = 0 -> SP gl doit;")],
        "the decimation reads the RECORD index instead of the longitude"),

    # ---- spbg --------------------------------------------------------
    "BGPLUS4": ("spbg", [(
        "\tA = [BGstart]; A + 4; A & 65535; [BGbp] = A;",
        "\tA = [BGstart]; A & 65535; [BGbp] = A;")],
        "niv-lr's dropped source '+4' - the panorama shifts by one byte"),

    "BGMASK": ("spbg", [(
        "\t=> SP put;\n\t[BGi]+;",
        "\t=> SP bg putbase;\n\t[BGi]+;"),
        ('"SP bg invert"',
         '"SP bg putbase"\n'
         "\t=> SP base; [SPtmp] = C;\n"
         "\tC = [SPoff]; C - 4; C & 65535;\n"
         "\tA = nw; A + [SPtmp]; A + C;\n"
         "\tC = [SPval]; C & 255;\n"
         "\t[A] = C;\n"
         "\tend;\n\n"
         '"SP bg invert"')],
        "the class-A mask taken at the BUFFER BASE, not the segment origin"),

    "BGMASKOFF": ("spbg", [(
        "\t=> SP put;\n\t[BGi]+;",
        "\t=> SP bg putraw;\n\t[BGi]+;"),
        ('"SP bg invert"',
         '"SP bg putraw"\n'
         "\t=> SP seg; [SPtmp] = C;\n"
         "\tA = nw; A + [SPtmp]; A + [SPoff];\n"
         "\tC = [SPval]; C & 255;\n"
         "\t[A] = C;\n"
         "\tend;\n\n"
         '"SP bg invert"')],
        "no 16-bit truncation at all - every folded paint lands 65,536 high"),

    "BGBLOCK": ("spbg", [(
        "\tA = [BGi]; ? A '< 25 -> SP bg blk;",
        "\tA = [BGi]; ? A '< 16 -> SP bg blk;")],
        "a 4x4 block where the assembly writes 5x5"),

    # ---- spdark ------------------------------------------------------
    "DARKSHIFT": ("spdark", [(
        "\tC = [SPval]; C > 2; [SPval] = C;",
        "\tC = [SPval]; C > 1; [SPval] = C;")],
        "the terminator darkens by >>1 instead of >>2"),

    "DARKROWS": ("spdark", [(
        "\tDKROWS\t= 179;", "\tDKROWS\t= 180;")],
        "180 rows where the assembly says 179"),

    "DARKMOD": ("spdark", [(
        "\tA = [DKplwp]; A + 4; A + DKPHASE; A & 65535; [DKdi] = A;",
        "\tA = [DKplwp]; A + DKPHASE; A % 360; A + 4; A & 65535; [DKdi] = A;")],
        "the band start reduced mod 360, which the assembly does not do"),

    # ---- spncc -------------------------------------------------------
    "NCCZERO": ("spncc", [(
        "\tA = [SPval]; ? A != 3 -> SP lp zn;",
        "\tA = [SPval]; ? A '>= 0 -> SP lp zn;")],
        "loadpv's slot-3 zeroing skipped: the transform sees the garbage"),

    "DEPIRESET": ("spncc", [(
        "\t( phase 2 )\n\t=> SP quicksort;",
        "\t( phase 2 )\n"
        "\t[PVp] = 0;\n"
        '    "SP dw ri"\n'
        "\t[SPreg] = RGPVF; [SPf] = [PVp];\n"
        "\tA = [PVadi]; C = [PVp]; C + C; A + C; [SPidx] = A; => SP putu16;\n"
        "\t[PVp]+;\n"
        "\tA = [PVp]; ? A '< [PVn] -> SP dw ri;\n"
        "\t=> SP quicksort;")],
        "pv_dep_i re-initialised every frame instead of carried"),

    "NCCARENA": ("spncc", [(
        "\tA = [PVptr]; C = [PVn]; C '* 17; A + C; [PVay] = A;",
        "\tA = [PVptr]; C = [PVn]; C '* 20; A + C; [PVay] = A;")],
        "the Y sub-array re-laid out to a unit-aligned offset"),

    "NCCMANGLE": ("spncc", [(
        "\tA = [PVk]; A & 192; D = [PVk]; D & 63; D > 1; A | D;",
        "\tA = [PVk]; A & 192; D = [PVk]; D & 63; D > 2; A | D;")],
        "mode-1's colour mangle shifts by 2 instead of 1"),

    # ---- spscale -----------------------------------------------------
    "SCALETIE": ("spscale", [(
        "\t? A '< [SChalf] -> SP sc down;",
        "\t? A '<= [SChalf] -> SP sc down;")],
        "exact ties rounded toward zero instead of to even - which is\n"
        "         precisely the class of value a float32 multiply gets wrong"),

    "SCALESIGN": ("spscale", [(
        "\tA = 150; A - [SCexp]; [SCk] = A;",
        "\tA = 151; A - [SCexp]; [SCk] = A;")],
        "the binary32 exponent bias off by one"),
}


def sh(cmd):
    r = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File"] + cmd,
                       capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def build_and_run(mainsrc, tag):
    if os.path.exists(OUT):
        os.remove(OUT)
    rc, o = sh([BUILD, "-Src", mainsrc])
    if rc != 0:
        return None, "BUILD-FAIL " + o.strip().replace("\n", " | ")
    exe = mainsrc[:-4] + ".exe"
    rc, o = sh([RUN, "-Exe", exe, "-Out", OUT, "-TimeoutSec", "300"])
    if rc != 0 or not os.path.exists(OUT):
        return None, "RUN-FAIL " + o.strip()
    d = open(OUT, "rb").read()
    keep = os.path.join(W, "sp-%s.bin" % tag)
    open(keep, "wb").write(d)
    return d, "ok %d bytes sha256 %s" % (len(d), hashlib.sha256(d).hexdigest())


def parse(d):
    """-> {(kind, tag, case): payload bytes}, in file order."""
    o = 0
    out = {}
    order = []
    while o + 64 <= len(d):
        h = struct.unpack("<16i", d[o:o + 64])
        o += 64
        kind, bcnt, case, tag = h[2], h[5], h[6], h[8]
        pay = d[o:o + 4 * bcnt]
        o += 4 * bcnt
        k = (kind, tag, case)
        while k in out:
            k = k + (0,)
        out[k] = pay
        order.append(k)
    return out, order


KIND = {48: "PAGE", 49: "CEN", 50: "MAP", 51: "CLIP", 52: "GLOW", 53: "BG",
        54: "ARENA", 55: "DEPI", 56: "F32", 57: "SCALE", 58: "CALL",
        59: "TRL", 60: "OFF", 61: "SETUP"}


def compare(clean, other):
    a, ao = parse(clean)
    b, bo = parse(other)
    moved = {}
    if ao != bo:
        return {"RECORD-SET": 1}
    for k in ao:
        if a[k] != b[k]:
            n = KIND.get(k[0], str(k[0]))
            moved[n] = moved.get(n, 0) + 1
    return moved


def mkmain(name, lib, edits):
    src = open(os.path.join(W, lib + ".txt"), encoding="latin-1").read()
    for old, new in edits:
        if old not in src:
            raise SystemExit("sabotage %s: anchor not found in %s:\n%r" % (name, lib, old))
        src = src.replace(old, new, 1)
    blib = "spbrk" + name.lower()
    open(os.path.join(W, blib + ".txt"), "w", encoding="latin-1", newline="").write(src)

    m = open(os.path.join(W, "spmain.txt"), encoding="latin-1").read()
    m = m.replace("\t" + lib + ";", "\t" + blib + ";", 1)
    m = m.replace("program name = { spmain };",
                  "program name = { spmain%s };" % name.lower())
    mn = os.path.join(W, "spmain%s.txt" % name.lower())
    open(mn, "w", encoding="latin-1", newline="").write(m)
    return mn


def main():
    want = sys.argv[1:] or list(SABOTAGE)
    print("== rebuilding the CLEAN driver ==")
    clean, msg = build_and_run(os.path.join(W, "spmain.txt"), "clean")
    print("   clean:", msg)
    if clean is None:
        return 2

    print("\n== NULL-INPUT TEST: the clean build against itself ==")
    m = compare(clean, clean)
    print("   %s  (must be NOT CAUGHT)" % ("NOT CAUGHT" if not m else "CAUGHT %s" % m))
    nullbad = bool(m)

    rows = []
    for name in want:
        lib, edits, why = SABOTAGE[name]
        mn = mkmain(name, lib, edits)
        d, msg = build_and_run(mn, name.lower())
        if d is None:
            rows.append((name, lib, why, msg, None))
            print("%-12s %-9s %s" % (name, lib, msg))
            continue
        moved = compare(clean, d)
        rows.append((name, lib, why, msg, moved))
        print("%-12s %-9s %s" % (name, lib,
              ("CAUGHT   " + ", ".join("%s x%d" % kv for kv in sorted(moved.items())))
              if moved else "NOT CAUGHT  <-- the sabotage moved nothing"))

    print("\n== summary ==")
    caught = sum(1 for r in rows if r[4])
    print("%d sabotages, %d caught, %d NOT caught, null-input %s"
          % (len(rows), caught, len(rows) - caught,
             "FAILED" if nullbad else "passed"))
    for name, lib, why, msg, moved in rows:
        print("  %-12s %-9s %s" % (name, lib, why.split("\n")[0]))
    return 0 if caught == len(rows) and not nullbad else 1


if __name__ == "__main__":
    sys.exit(main())
