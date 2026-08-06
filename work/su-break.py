r"""su-break.py -- break every check by breaking the code, and record which
check caught what.

A check nobody has broken is a check nobody has tested.  Each row below is ONE
localised edit to ONE library; the driver is regenerated only to name the
edited copy instead of the original, so a sabotage cannot accidentally also
change the harness.  Each build is then run through the same poll-and-kill
runner and graded against the same ten recon-C captures.

Every row names the detector it is expected to trip and the type(s) it should
trip on.  A row that is caught by nothing is reported as caught by nothing --
SRANDONCE exists precisely to measure a void that the plan predicted, and it
is not counted as a pass.

Two of the rows, BRTLREG and SDASEED, are not hypothetical: they are the two
real defects this port shipped with during development, reinstated verbatim.
BRTLREG is the one the palette caught and the map could not; SDASEED is the
one the map caught and the palette could not.  Having both in the table is the
point.

Usage:  python su-break.py [name ...]      (default: all)
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RECON = os.path.join(ROOT, "tests", "gen", "recon_w7a", "out")
BUILD = os.path.join(ROOT, "lino_build.ps1")

_s = importlib.util.spec_from_file_location("ck", os.path.join(HERE, "su-check.py"))
ck = importlib.util.module_from_spec(_s)
_s.loader.exec_module(ck)

# name, library, (old, new, occurrence-index or None for all), expectation
BREAKS = [
    ("TYPE3ASSIGN", "susm", [(
        "\tD + A; D & 0FFh;\t\t( add es:[di], bl - a BYTE add )",
        "\tD = A; D & 0FFh;\t\t( SABOTAGE: assign, niv-lr's bug )", None)],
     "C1 on type 3: LR assigns where vanilla adds"),

    ("TYPE3BYTE", "susm", [(
        "\t[C plus 0] = 3Eh;\n\t[C plus 1] = 0;",
        "\t[C plus 0] = 3Eh;", None)],
     "C1 on type 3: the word clamp's neighbour zero dropped"),

    ("NOISESKIP", "susm", [(
        "\t( mare: the sea floor, a flat 16 )\n\tC = [SUsp]; C + [SUsi];",
        "\t( SABOTAGE: advance the noise on the sea branch too )\n"
        "\t=> SU noise step;\n\tC = [SUsp]; C + [SUsi];", None)],
     "C1 on type 3: noise advanced on sea as well as land"),

    ("WAVEPLUS4", "supaint", [(
        "\tA + 4; A & 0FFFFh;\n\tA + [SUpx]; A & 0FFFFh; [SUoff] = A;",
        "\tA + 8; A & 0FFFFh;\n\tA + [SUpx]; A & 0FFFFh; [SUoff] = A;", None)],
     "C1 on type 6: wave's +4 read as a pixel skew on top of the segment offset"),

    ("LSSM1", "susm", [("\tNLSS\t= 64480;", "\tNLSS\t= 64479;", None)],
     "C1: niv-lr's one-fewer-pixel lssmooth"),

    ("T9PAGE", "sucase", [(
        "\t[SUval] = 1Fh;\n\t=> SU pclear;",
        "\t[SUval] = 1Fh;\n\t[SUpbase] = RADPT;\n\t=> SU pclear;\n"
        "\t[SUpbase] = RPBG;", None)],
     "C1 on type 9: pclear aimed at the offscreen page, niv-lr's bug"),

    ("PSGLANE", "susm", [(
        "\tE > 16;\n\tD = E; D & 0FFh; A + D; A & 0FFh;\n"
        "\tD = E; D > 8; D & 0FFh; A + D; A & 0FFh;\n\tA > 2;",
        "\tA > 2;", 1)],
     "C1 on type 2: psmooth_grays summing two lanes instead of four"),

    ("TRUNCPROD", "supaint", [(
        "\"SU calc px\"\n\t=> SU cos term;\n\t[SUia] = [SUcxi];",
        "\"SU calc px\"\n\t=> SU cos term;\n\t=> SU chop32;\n"
        "\t[SUia] = [SUti]; => SU f of ia; [SFtmp] = [SFtmp];\n"
        "\t{ D9 87 <dSFtmp mtp bytesperunit> }\n\t[SUia] = [SUcxi];", None)],
     "C1: the radius product truncated before cx is added (niv-lr's storm cast)"),

    ("ARGORDER", "sucase", [(
        "\tC = 3;   => SU rfr; A = C; A + 25; [SUia] = A; => SU th of;\n"
        "\tC = 350; => SU rfr; [SUia] = C; => SU kq of;\n"
        "\tC = 200; => SU rfr; [SUia] = C; => SU kt of;",
        "\tC = 200; => SU rfr; [SUia] = C; => SU kt of;\n"
        "\tC = 350; => SU rfr; [SUia] = C; => SU kq of;\n"
        "\tC = 3;   => SU rfr; A = C; A + 25; [SUia] = A; => SU th of;", None)],
     "C1 on type 5: contrast's arguments evaluated left to right"),

    ("SUBORDER", "supal", [(
        "\tC = [SUc]; => SU rnd;\n\tA = [SPt2]; A + C; [SPt2] = A;\n"
        "\tC = [SUc]; => SU rnd;\n\tA = [SPt2]; A - C; [SUti] = A;",
        "\tC = [SUc]; => SU rnd;\n\tA = [SPt2]; A - C; [SPt2] = A;\n"
        "\tC = [SUc]; => SU rnd;\n\tA = [SPt2]; A + C; [SUti] = A;", None)],
     "C3 on every type: r + random(c) - random(c) evaluated right to left"),

    ("FTOLSAT", "suseed", [(
        "\t[SUti] = [SUq0];\n\tend;\n\n      ( SU near32",
        "\tA = [SUq1]; C = [SUq0]; C >> 31;\n"
        "\t? A = C -> SU chop32 ok;\n"
        "\t[SUti] = 7FFFFFFFh;\n\tend;\n    \"SU chop32 ok\"\n"
        "\t[SUti] = [SUq0];\n\tend;\n\n      ( SU near32", None)],
     "C1 on types 2/5/6: __ftol saturating instead of keeping the low 32 bits"),

    ("SEEDTRUNC", "suseed", [(
        "\t    DD 87 <dSUsv0  mtp bytesperunit>\t(fld  qword [edi+SUsv0*4])\n"
        "\t    DC 87 <dK4112A mtp bytesperunit>\t(fadd qword [edi+K4112A*4])\n"
        "\t}\n\t=> SU chop32;",
        "\t    DD 87 <dSUsv0  mtp bytesperunit>\t(fld  qword [edi+SUsv0*4])\n"
        "\t}\n\t=> SU chop32;\n\tA = [SUti]; A + 4112; [SUti] = A;", None)],
     "C4/C1: truncating before the +4112, niv-lr's order"),

    ("LOOP91", "suseed", [(
        "\"SU a step4\"\n\t{\n"
        "\t    D9 87 <dSFa    mtp bytesperunit>\t(fld  dword [edi+SFa*4])\n"
        "\t    DC 87 <dK4DEG0 mtp bytesperunit>\t(fadd qword [edi+K4DEG0*4])\n"
        "\t    D9 9F <dSFa    mtp bytesperunit>\t(fstp dword [edi+SFa*4])\n"
        "\t}",
        "\"SU a step4\"\n\t{\n"
        "\t    DD 87 <dSUscr0 mtp bytesperunit>\t(fld  qword [edi+SUscr0*4])\n"
        "\t    DC 87 <dK4DEG0 mtp bytesperunit>\t(fadd qword [edi+K4DEG0*4])\n"
        "\t    DD 9F <dSUscr0 mtp bytesperunit>\t(fstp qword [edi+SUscr0*4])\n"
        "\t    DD 87 <dSUscr0 mtp bytesperunit>\t(fld  qword [edi+SUscr0*4])\n"
        "\t    D9 9F <dSFa    mtp bytesperunit>\t(fstp dword [edi+SFa*4])\n"
        "\t}", None),
        ("\"SU a zero\"\n\t[SFa] = 0;",
         "\"SU a zero\"\n\t[SFa] = 0; [SUscr0] = 0; [SUscr1] = 0;", None)],
     "C1: the angle accumulated in a double, so the ring runs 91 times not 90"),

    ("PUTNOMASK", "subuf", [(
        '"SU put"\n\tA = [SUoff]; A & 0FFFFh; A + [SUpseg];',
        '"SU put"\n\tA = [SUoff]; A + [SUpseg];', None)],
     "C1: the class-A 16-bit index mask removed, so band()'s run off the end of"
     " the panorama walks past the buffer instead of folding inside the segment"),

    ("RNDPATUNS", "surng", [(
        '\tD = A; D & 8000h;\n\t? D = 0 -> SU ns pos;\n\tA - 65536;\n    "SU ns pos"',
        '    "SU ns pos"', None)],
     "C1 on every type: the surface noise multiplied UNSIGNED (mul) instead of"
     " SIGNED (imul), which is the one-character difference between this fold"
     " and the galaxy hash's"),

    ("PSGDEAD", "susm", [(
        '"SU psmooth grays"\n\tA = nw; A + [SUpbase]; [SUsp] = A;',
        '"SU psmooth grays"\n\tend;\n\tA = nw; A + [SUpbase]; [SUsp] = A;', None)],
     "COVERAGE PROBE, not a defect: psmooth_grays made a no-op.  If nothing"
     " changes, no capture ever took the type-2 random(3)==0 branch and"
     " PSGLANE is not catchable on this corpus"),

    ("CRATERWRAP", "supaint", [(
        "\tA = [SUpy]; A '* CRSTEP; A & 0FFFFh; C = [SUpx]; A + C; A & 0FFFFh;\n"
        "\t[SUvptr] = A;",
        "\tA = [SUpy]; A '* CRSTEP; C = [SUpx]; A + C;\n\t[SUvptr] = A;", "all")],
     "VOID BY CONSTRUCTION, kept to show it: widening crater's vptr from 16 bits"
     " to 32 cannot move a single byte, because the truncation that matters is"
     " downstream at the segment offset and (4 + v) mod 65536 ="
     " (4 + (v mod 65536)) mod 65536.  The plan expected C1 + C7 to catch it;"
     " nothing can"),

    ("BRTLREG", "surng", [("\tC = [SUhv];\n\tend;", "\tC = A;\n\tend;", None)],
     "REAL DEFECT, reinstated: random() returning the hash scratch"),

    ("SDASEED", "sucase", [(
        "\tA = [SUseed]; [SUnax] = A;\n\t=> SU sda;",
        "\t=> SU sda;", None)],
     "REAL DEFECT, reinstated: the sda block not re-seeding ax from seed"),

    ("TERMPLUS4", "sucase", [(
        "\tA = 4; A + [SUplwp]; A + 35; A & 0FFFFh; [SUoff] = A;",
        "\tA = 8; A + [SUplwp]; A + 35; A & 0FFFFh; [SUoff] = A;", None)],
     "C1 on every type: farmalloc's offset added twice at the terminator"),

    ("SRANDONCE", "sucase", [(
        "\t( srand (seed) AGAIN, :4844.  Provably indistinguishable from not\n"
        "\t  doing it; done because the source does it. )\n"
        "\tA = [SUseed];\n\t=> SU srand;",
        "\t( SABOTAGE: the second srand deleted. )", None)],
     "EXPECTED TO BE CAUGHT BY NOTHING - this row measures a void"),
]

LIBS = ["suseed", "surng", "subuf", "susm", "supaint", "supal", "sucase"]


def apply_edits(text, edits, name):
    for old, new, occ in edits:
        n = text.count(old)
        if n == 0:
            raise SystemExit("%s: anchor not found:\n%s" % (name, old[:120]))
        if occ == "all":
            text = text.replace(old, new)
        elif occ is None:
            if n != 1:
                raise SystemExit("%s: anchor appears %d times, need an index"
                                 % (name, n))
            text = text.replace(old, new)
        else:
            parts = text.split(old)
            if len(parts) - 1 <= occ:
                raise SystemExit("%s: occurrence %d not present" % (name, occ))
            text = old.join(parts[:occ + 1]) + new + old.join(parts[occ + 1:])
    return text


def build_one(name, lib, edits):
    tag = "subrk" + name.lower()
    src = open(os.path.join(HERE, lib + ".txt"), encoding="latin-1").read()
    open(os.path.join(HERE, tag + "lib.txt"), "w", encoding="latin-1").write(
        apply_edits(src, edits, name))
    drv = open(os.path.join(HERE, "sumain.txt"), encoding="latin-1").read()
    drv = drv.replace("\n\t%s;\n" % lib, "\n\t%slib;\n" % tag)
    drv = drv.replace("program name = { sumain }", "program name = { %s }" % tag)
    open(os.path.join(HERE, tag + "main.txt"), "w", encoding="latin-1").write(drv)
    r = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File",
                        BUILD, "-Src", os.path.join(HERE, tag + "main.txt")],
                       capture_output=True, text=True)
    return tag, r.stdout.strip()


def grade(outbin, entries):
    """How many of the ten captures still match, per artefact."""
    recs = ck.read_records(outbin)
    bad_map = bad_ovl = bad_pal = 0
    bad_tail = 0
    for ci, e in enumerate(entries):
        rs = [r for r in recs if r["case"] == ci]
        m = [r for r in rs if r["kind"] == ck.KMAP]
        if not m:
            bad_map += 1
            continue
        got = ck.unpack_bytes(m[0]["body"], 64800)
        cap = open(os.path.join(RECON, e["tag"] + ".p_background"), "rb").read()[:64800]
        if got != cap:
            bad_map += 1
        o = [r for r in rs if r["kind"] == ck.KOVL]
        if o:
            go = ck.unpack_bytes(o[0]["body"], 32400)
            co = open(os.path.join(RECON, e["tag"] + ".objectschart"), "rb").read()[:32400]
            if go != co:
                bad_ovl += 1
        p = [r for r in rs if r["kind"] == ck.KPAL]
        if p:
            gp = ck.unpack_bytes(p[0]["body"], 192)
            cpb = bytes(v for t in e["palette_192_255"] for v in t)
            if gp != cpb:
                bad_pal += 1
        t = [r for r in rs if r["kind"] == ck.KTAIL]
        if t and any(ck.unpack_bytes(t[0]["body"], 752)):
            bad_tail += 1
    return bad_map, bad_ovl, bad_pal, bad_tail


def main():
    want = set(a.upper() for a in sys.argv[1:])
    man = json.load(open(os.path.join(RECON, "manifest.json")))
    seen, entries = set(), []
    for e in man:
        key = (tuple(e["star"]), e["body"])
        if key in seen:
            continue
        seen.add(key)
        entries.append(e)

    print("%-12s %-9s %-42s %s" % ("SABOTAGE", "BUILD", "CAUGHT BY", "EXPECTED"))
    print("-" * 118)
    rows = []
    for name, lib, edits, expect in BREAKS:
        if want and name not in want:
            continue
        tag, blog = build_one(name, lib, edits)
        if not blog.startswith("OK"):
            print("%-12s %-9s %s" % (name, "FAIL", blog))
            rows.append((name, "build failed"))
            continue
        exe = os.path.join(HERE, tag + "main.exe")
        r = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File",
                            os.path.join(HERE, "su-run.ps1"), "-Exe", exe,
                            "-TimeoutSec", "600"], capture_output=True, text=True)
        outbin = os.path.join(HERE, "su-out.bin")
        keep = os.path.join(HERE, "su-brk-" + name.lower() + ".bin")
        shutil.copyfile(outbin, keep)
        bm, bo, bp, bt = grade(keep, entries)
        caught = []
        if bm:
            caught.append("C1 map %d/10" % bm)
        if bo:
            caught.append("C2 overlay %d/10" % bo)
        if bp:
            caught.append("C3 palette %d/10" % bp)
        if bt:
            caught.append("C7 tail %d/10" % bt)
        label = ", ".join(caught) if caught else "*** NOTHING ***"
        print("%-12s %-9s %-42s %s" % (name, "ok", label, expect))
        rows.append((name, label))
    print()
    nothing = [n for n, l in rows if l == "*** NOTHING ***"]
    print("%d sabotages built and run; %d caught, %d caught by nothing%s"
          % (len(rows), len(rows) - len(nothing), len(nothing),
             (": " + ", ".join(nothing)) if nothing else ""))


if __name__ == "__main__":
    main()
