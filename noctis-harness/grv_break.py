r"""grv_break.py - Wave 7b: break every hpoint check, show which catches it.

A check with no demonstrated falsifier is a claim, not a check.  This file
takes work/walk.txt, applies ONE localised edit, builds the mutated source,
runs it against the same pinned corpus, and compares the dump to the
unmutated C oracle (grv_ref) and spec (grv_spec).  The driver, corpus and
references never change.

Each row reports which check fired (E1 = lino vs cref, E2 = lino vs spec,
E3 = cref vs spec - the last is informational since cref/spec are not
mutated) and on how many of the 82 cases.  A sabotage that NOTHING catches
is printed as such and is evidence about the check set, not a pass.
"""

import os
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
WORK = os.path.join(REPO, "work")
WALK_SRC = os.path.join(WORK, "walk.txt")
CORPUS = os.path.join(HERE, "grv-corpus.txt")
BUILD_PS1 = os.path.join(REPO, "lino_build.ps1")
RUN_PS1 = os.path.join(REPO, "tests", "w7arun.ps1")

sys.path.insert(0, HERE)
import grv_spec  # noqa: E402


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", **kw)


def recs_list(blob):
    """9-word records -> list of [op, v0..v7]."""
    n = len(blob) // 4
    return [list(struct.unpack_from("<9i", blob, i * 4)) for i in range(0, n, 9)]


def parse_corpus(path):
    rows = []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            s = line.strip()
            if not s or s[0] == "#":
                continue
            t = s.replace(",", " ").split()
            if not t:
                continue
            op = int(t[0])
            if op == 1 and len(t) == 7:
                rows.append((1, tuple(int(x) for x in t[1:])))
            elif op == 2 and len(t) == 13:
                rows.append((2, tuple(int(x) for x in t[1:])))
            elif op == 5 and len(t) == 7:
                rows.append((5, tuple(int(x) for x in t[1:])))
    return rows


ROWS = parse_corpus(CORPUS)


def spec_records():
    out = []
    for op, payload in ROWS:
        if op == 1:
            out.append([1, grv_spec.hpoint_bits(*payload)] + [0] * 7)
        elif op == 2:
            out.append([2] + grv_spec.fragment_case(*payload))
        else:  # op 5
            out.append([5] + grv_spec.p_forward_case(*payload) + [0] * 6)
    return out


SPEC = spec_records()


def cref_records():
    exe = os.path.join(HERE, "grv_ref.exe")
    binf = os.path.join(HERE, "grv_ref.bin")
    if not os.path.exists(exe) or os.path.getmtime(CORPUS) > os.path.getmtime(exe):
        p = run(["gcc", "-O2", "-fno-fast-math", "-o", exe,
                 os.path.join(HERE, "grv_ref.c"), "-lm"])
        if p.returncode != 0:
            raise SystemExit("gcc failed: " + p.stdout + p.stderr)
    p = run([exe, CORPUS, binf])
    if p.returncode != 0:
        raise SystemExit("grv_ref run failed")
    with open(binf, "rb") as fh:
        return recs_list(fh.read())


CREF = cref_records()


# name -> (anchor, replacement, replace_all, what it models)
MUTS = [
    ("BRANCHFLIP",
     "W16384\t= 16384;", "W16384\t= 16383;", False,
     "move the icx+icz branch threshold: 16384 -> 16383, so the boundary "
     "cases (icx+icz==16383) flip triangles"),
    ("QIDWRONG",
     "WQIDHI\t= 3F100000h;", "WQIDHI\t= 3F080000h;", False,
     "qid = 1/4096 instead of 1/16384 (exponent off by two) - the per-"
     "tile texture/height gradient is 4x too steep"),
    ("H3CORNER",
     "A + 201; A + wsurfv; C = [A]; C & 255; C < 11;\n\tA = 0; A - C; [HPh3i] = A;",
     "A + 200; A + wsurfv; C = [A]; C & 255; C < 11;\n\tA = 0; A - C; [HPh3i] = A;",
     False,
     "read h3 from cpos+200 instead of cpos+201 - the lower triangle's "
     "(row+1,col+1) corner is swapped with (row+1,col)"),
    ("SIGNDROP",
     "C < 11;\n\tA = 0; A - C;", "C < 11;\n\tA = C;", True,
     "drop the negation in -(s<<11) for all four corners - heights become "
     "positive, py inverts"),
    ("SHRSHIFT",
     "C & 255; C < 11;", "C & 255; C < 10;", True,
     "shift surf<<10 instead of <<11 - the height scale is halved, py is "
     "halved on every non-flat case"),
    ("DEPTHCHOP",
     "=> FToIntChop;", "=> FToIntNear;", False,
     "fragment's depth cast rounds-to-nearest instead of chopping - the "
     "EXACT-REQUIRED chop #1 (WAVE7B_PLAN); moves depth whenever hpdep's "
     "fraction is >= 0.5"),
    ("DXHALF",
     "WHALFHI\t= 3FE00000h;", "WHALFHI\t= 3FF00000h;", False,
     "use 1.0 instead of 0.5 in dx/dz centering - fragment distances the "
     "tile from the wrong centre, depth diverges on every off-centre tile"),
    ("FASTSEED",
     "A = [FRh1]; A + [FRseed]; [FRfrs] = A;",
     "A = [FRseed]; [FRfrs] = A;", False,
     "fast_srand(seed) instead of fast_srand(h1+seed) - the diffuse c1 LCG "
     "seed misses the per-tile h1 term, every diffuse case diverges"),
    ("C1NOSHR",
     "A = [FRc1]; A - 33; A > 31;", "A = [FRc1]; A - 9999; A > 31;", False,
     "drop the c1>32 clamp - bright slopes keep their full surf-byte diff "
     "instead of being clamped to the 0..32 shade range"),
    ("FWZSIGN",
     "=> FAdd;\t\t\t\t\t\t( FA = pos_z + prod_z )",
     "=> FSub;\t\t\t\t\t\t( FA = pos_z + prod_z )", False,
     "p_Forward pos_z -= prod_z instead of += (walks backward in z) - the "
     "z-axis movement inverts on every p_Forward case"),
    ("FWSWAPSB",
     "[FS0] = [PFsbn];    => FLoadF32; => HP fb fa;\t( FB = sinbeta )",
     "[FS0] = [PFcbn];    => FLoadF32; => HP fb fa;\t( FB = sinbeta )", False,
     "p_Forward uses cosbeta where it should use sinbeta for the x product - "
     "x-axis movement follows the wrong trig function"),
    ("NOFENTER",
     "=> FEnter;\n", "", False,
     "MEASURED VOID (like su_break's SRANDONCE): skip FEnter/FLeave.  The "
     "chop-vs-round knob DOES bite hpoint in principle (5/82 cases move if "
     "the narrow is a chop), but this runtime's ambient control word at the "
     "fstp-dword stores is already round-to-nearest, so FEnter is REDUNDANT "
     "for this standalone programme.  Expected to be caught by nothing."),
]


def build_mut(name, anchor, new, all_):
    tmp = tempfile.mkdtemp(prefix="grvbrk_")
    src = os.path.join(tmp, "walk.txt")
    shutil.copy(WALK_SRC, src)
    # the fp libraries resolve relative to the source file's directory
    # (fp/fpabi; etc.), so the temp build needs the same fp/ tree.
    shutil.copytree(os.path.join(WORK, "fp"), os.path.join(tmp, "fp"))
    s = open(src, encoding="utf-8").read()
    hits = s.count(anchor)
    if hits == 0:
        return None, "anchor not found", tmp
    if not all_ and hits != 1:
        return None, "anchor appears %d times, expected 1" % hits, tmp
    if all_:
        s = s.replace(anchor, new)
    else:
        s = s.replace(anchor, new, 1)
    open(src, "w", encoding="utf-8").write(s)
    # build
    if os.path.exists(os.path.join(tmp, "walk.exe")):
        os.remove(os.path.join(tmp, "walk.exe"))
    p = run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
             BUILD_PS1, "-Src", src, "-TimeoutSec", "180"])
    if p.returncode != 0:
        return None, "build failed: " + (p.stdout + p.stderr).strip()[:120], tmp
    # run
    shutil.copy(CORPUS, os.path.join(tmp, "grv-corpus.txt"))
    out = os.path.join(tmp, "grv-out.bin")
    if os.path.exists(out):
        os.remove(out)
    p = run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
             RUN_PS1, "-Exe", os.path.join(tmp, "walk.exe"),
             "-Out", out, "-TimeoutSec", "120"])
    if p.returncode != 0 or not os.path.exists(out):
        return None, "run failed: " + (p.stdout + p.stderr).strip()[:120], tmp
    with open(out, "rb") as fh:
        return recs_list(fh.read()), "built+ran", tmp


def verdict(L):
    n = min(len(L), len(CREF), len(SPEC))
    e1 = sum(1 for i in range(n) if L[i] != CREF[i])
    e2 = sum(1 for i in range(n) if L[i] != SPEC[i])
    return e1, e2, n


EXPECTED_VOID = {"NOFENTER"}


def main():
    print("%-12s %-22s %s" % ("sabotage", "caught by", "modelled defect"))
    print("-" * 104)
    uncaught = []
    for name, anchor, new, all_, why in MUTS:
        L, note, tmp = build_mut(name, anchor, new, all_)
        try:
            if L is None:
                print("%-12s %-22s %s" % (name, "NO BUILD/RUN (" + note + ")", why))
                continue
            e1, e2, n = verdict(L)
            fired = []
            if e1:
                fired.append("E1 %d/%d" % (e1, n))
            if e2:
                fired.append("E2 %d/%d" % (e2, n))
            if not fired:
                if name not in EXPECTED_VOID:
                    uncaught.append(name)
                print("%-12s %-22s %s" % (name,
                      "VOID (expected)" if name in EXPECTED_VOID
                      else "*** NOTHING ***", why))
            else:
                print("%-12s %-22s %s" % (name, ", ".join(fired), why))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    print("\nuncaught (unexpected):", uncaught or "none")
    return 1 if uncaught else 0


if __name__ == "__main__":
    sys.exit(main())
