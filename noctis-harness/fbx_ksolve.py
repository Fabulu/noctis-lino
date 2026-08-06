#!/usr/bin/env python3
r"""fbx_ksolve.py -- an INDEPENDENT re-derivation of the far-pointer offset K.

WHAT IT IS FOR.  `#define SEG_OFFSET 4` was an unparsed literal in fb_ref.c and
an unparsed literal in fb_layout.py.  Two files agreeing on a constant that
neither derived is one transcription copied twice, and every check downstream
inherits the premise instead of testing it.  BUFFERMAP 4.1 calls the placement
SETTLED and argues it in prose; prose is not a grader.

fb_ref.c now solves K by parsing five anchors.  This file solves it again, in a
different language, by a different method, over a WIDER corpus:

  * fb_ref.c anchors on five known token sequences and reads the displacement
    that follows each.
  * this file CENSUSES the whole 1996 tree -- every `es:[reg]` and `es:[reg+d]`
    in every .CPP and .H -- classifies each site by how ES was established in
    its own function, and then requires the two conventions to agree.  A site
    that fb_ref.c never looks at can therefore contradict it.
  * and it decodes the hand-assembled forms GENERICALLY: every
    `db 0x66, 0x26, 0xC7, <modrm> [, <disp>]` sequence is run through a real
    16-bit ModRM decoder rather than matched against two known byte strings.

WHAT IS STILL SHARED, stated because it is the limit of the claim.  Both
solvers use the SAME MODEL: `segment offset = pixel_index + o*K + D`, with the
two addressing conventions of BUFFERMAP 4.1.  They are two independent PARSES,
not two independent derivations of the model.  The model itself is settled by
one argument from one document, and the only thing that would make it TIER 1 is
the DOSBox-X experiment BUFFERMAP 4.1 names: break after init_FP_segments and
read the offset word of `adapted`.  Until then: derived and graded from source,
never measured.

usage:
    python fbx_ksolve.py [srcdir] [--census] [--cross <fb_ref.exe>]
exit 0 if a unique K was solved, 1 if the constraints refuse, 2 on a read error.
"""

import os
import re
import subprocess
import sys

DEFAULT_SRC = r"C:\programmieren\noctis\niv-plus\source"

# 16-bit ModRM: mod/rm -> the effective address expression.
RM16 = ["bx+si", "bx+di", "bp+si", "bp+di", "si", "di", "bp", "bx"]

# statements that establish ES with the far pointer's OWN OFFSET in a register
RE_LES = re.compile(r"\bles\s+(ax|bx|cx|dx|si|di)\s*,\s*dword\s+ptr\s+(\w+)", re.I)
# statements that establish ES from a SEGMENT ONLY
RE_MOVSEG = re.compile(r"\bmov\s+es\s*,\s*seg_(\w+)", re.I)
# a memory reference through ES with an optional displacement
RE_ESREF = re.compile(r"es:\[\s*(si|di|bx|bp)\s*(?:\+\s*(0x[0-9a-fA-F]+|\d+)\s*)?\]")
# `add di, word ptr riga[bx]` -- the index is built from riga alone
RE_RIGA = re.compile(r"\badd\s+(si|di)\s*,\s*word\s+ptr\s+riga\[", re.I)
# a hand-assembled 0xC7 store with a 0x66 operand-size and 0x26 ES prefix
RE_DB = re.compile(r"\bdb\s+((?:0x[0-9a-fA-F]{2}\s*,\s*)*0x[0-9a-fA-F]{2})", re.I)
# A function DEFINITION at column 0: header, then an opening brace.
#
# Two failures were measured while writing this and both are the same class as
# the one the wave exists to kill -- a parse that silently returns a plausible
# answer.  `\([^;]*\)` let the greedy class run over dozens of lines and merged
# several functions into one body, so `wave()` vanished from the census;
# tightening it to `[^;{}\n]*` then dropped `Stick`, whose parameter list spans
# two lines, and attributed Stick's sites to the function above it.  Requiring
# the brace, and allowing the list to wrap, pins both ends.  A misattributed
# site is not a cosmetic defect: it would compare two conventions from two
# different functions, which is not the same pixel and therefore not the same
# equation.
RE_FUNC = re.compile(
    r"^[A-Za-z_][\w \t\*]*\b(\w+)\s*\([^;{}]{0,400}\)\s*\r?\n?\s*\{", re.M)


def strip_comments(text):
    out, i, n = [], 0, len(text)
    while i < n:
        if text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def split_functions(text):
    """Cut the file into (name, body) at column-0 function headers.

    Deliberately crude and deliberately DIFFERENT from fb_ref.c's
    distance-window approach: a site is attributed to the function it is
    lexically inside, not to the nearest preceding token."""
    marks = [(m.start(), m.group(1)) for m in RE_FUNC.finditer(text)]
    if not marks:
        return [("<file>", text)]
    out = []
    for k, (pos, name) in enumerate(marks):
        end = marks[k + 1][0] if k + 1 < len(marks) else len(text)
        out.append((name, text[pos:end]))
    return out


def decode_modrm(bytes_):
    """Decode `0x66 0x26 0xC7 <modrm> [disp]` -> (regexpr, disp) or None."""
    b = [int(x, 16) for x in bytes_]
    # skip 0x66 (operand size) and 0x26 (ES segment override) prefixes
    i = 0
    saw_es = False
    while i < len(b) and b[i] in (0x66, 0x26, 0x64, 0x67):
        if b[i] == 0x26:
            saw_es = True
        i += 1
    if i >= len(b) or b[i] != 0xC7:      # MOV r/m16, imm16
        return None
    i += 1
    if i >= len(b):
        return None
    modrm = b[i]
    i += 1
    mod, rm = (modrm >> 6) & 3, modrm & 7
    if mod == 3:
        return None
    expr = RM16[rm]
    if mod == 0:
        if rm == 6:
            return None                  # [disp16], no base
        disp = 0
    elif mod == 1:
        if i >= len(b):
            return None
        disp = b[i]
        if disp > 127:
            disp -= 256
    else:
        if i + 1 >= len(b):
            return None
        disp = b[i] | (b[i + 1] << 8)
    return (expr, disp, saw_es)


class Solver(object):
    def __init__(self):
        self.eq = []          # (K, why)
        self.sites = []       # (file, func, o, disp, text)
        self.conflicts = []   # functions whose two conventions disagree

    def add(self, k, why):
        self.eq.append((k, why))

    def census(self, path, text):
        fname = os.path.basename(path)
        for func, body in split_functions(text):
            les = {}                       # reg -> pointer name
            for m in RE_LES.finditer(body):
                les[m.group(1).lower()] = m.group(2)
            segonly = set(m.group(1) for m in RE_MOVSEG.finditer(body))
            riga_regs = set(m.group(1).lower() for m in RE_RIGA.finditer(body))

            # only functions that address `adapted` are in scope: the model is
            # about ONE pointer, and mixing pointers would compare offsets of
            # different blocks
            touches_adapted = ("adapted" in les.values()) or ("adapted" in segonly)
            if not touches_adapted:
                continue

            for m in RE_ESREF.finditer(body):
                reg = m.group(1).lower()
                disp = int(m.group(2), 0) if m.group(2) else 0
                if les.get(reg) == "adapted":
                    o = 1                  # the pointer's own offset is in reg
                elif reg in riga_regs:
                    # the index was built from riga[] alone, so whatever ES
                    # holds, the pointer's offset was NOT added
                    o = 0
                else:
                    continue               # not one of the two conventions
                self.sites.append((fname, func, o, disp, m.group(0)))

    def modrm(self, path, text):
        fname = os.path.basename(path)
        for func, body in split_functions(text):
            les = {}
            for m in RE_LES.finditer(body):
                les[m.group(1).lower()] = m.group(2)
            segonly = set(m.group(1) for m in RE_MOVSEG.finditer(body))
            if "adapted" not in les.values() and "adapted" not in segonly:
                continue
            for m in RE_DB.finditer(body):
                bs = [x.strip() for x in m.group(1).split(",")]
                d = decode_modrm(bs)
                if not d:
                    continue
                expr, disp, saw_es = d
                if not saw_es or expr not in ("si", "di"):
                    continue
                if les.get(expr) == "adapted":
                    o = 1
                elif "adapted" in segonly:
                    o = 0
                else:
                    continue
                self.sites.append((fname, func + " [db]", o, disp, m.group(0)[:40]))

    def solve(self):
        """One equation per FUNCTION that uses both conventions.

        The comparison is between BASE writes only, and the base write of a
        drawing routine is the one with the smallest displacement: a routine
        that lights a 2x2 dot writes +0, +1, +320, +321 off the same base, and
        pairing a neighbour offset from one convention against a base offset
        from the other compares two different pixels.  Taking the minimum per
        (file, function, convention) is what makes the two sides the same
        pixel, which is the entire content of the argument."""
        byfn = {}
        for f, fn, o, d, _t in self.sites:
            key = (f, fn)
            byfn.setdefault(key, {0: [], 1: []})[o].append(d)
        used = 0
        for (f, fn), m in sorted(byfn.items()):
            if not m[0] or not m[1]:
                continue                   # only one convention here
            s1, s0 = sorted(set(m[1])), sorted(set(m[0]))
            k = min(s0) - min(s1)
            # CONGRUENCE, not merely equal minima.  A drawing routine writes
            # the same SHAPE through both conventions -- Segmento lights a dot
            # at +0/+1/+319/+321 either way -- so the two displacement sets
            # must be translates of one another by exactly K.
            #
            # Taking only the minima was measured to be WRONG, by this file's
            # own falsification run: with one of Stick's six `es:[di+4]` sites
            # moved to +8 the minimum was still 4 and the solver happily
            # answered K = 4 while fb_ref.c refused.  A solver that absorbs a
            # single divergent site is a solver that cannot report a
            # divergence, which is the whole job.
            if set(s0) != set(d + k for d in s1):
                self.conflicts.append(
                    "%s:%s  the two conventions are not translates of one "
                    "another by any offset: with the pointer %s, without it %s"
                    % (f, fn, s1, s0))
                continue
            self.add(k, "%s:%s  base es:[+%d] WITH the pointer's offset  vs  "
                        "base es:[+%d] WITHOUT it%s"
                        % (f, fn, min(s1), min(s0),
                           "" if len(s1) == 1 else
                           "  (and the whole shape %s -> %s agrees)" % (s1, s0)))
            used += 1
        if self.conflicts:
            return None, "; ".join(self.conflicts)
        if not used:
            return None, "no function in the corpus uses both conventions"
        return "ok", ""


def main():
    args = [a for a in sys.argv[1:]]
    srcdir = DEFAULT_SRC
    census = "--census" in args
    cross = None
    if "--cross" in args:
        cross = args[args.index("--cross") + 1]
    pos = [a for a in args if not a.startswith("--")
           and (cross is None or a != cross)]
    if pos:
        srcdir = pos[0]

    if not os.path.isdir(srcdir):
        print("cannot read %s" % srcdir)
        return 2

    s = Solver()
    files = [f for f in sorted(os.listdir(srcdir))
             if f.upper().endswith((".CPP", ".H"))]
    for f in files:
        raw = open(os.path.join(srcdir, f), "rb").read().decode("latin-1")
        text = strip_comments(raw)
        s.census(os.path.join(srcdir, f), text)
        s.modrm(os.path.join(srcdir, f), text)

    ok, why = s.solve()
    if ok is None:
        print("REFUSED: " + why)
        return 1

    # ---- independent constraint: sc_bytes = 65536 + K -------------------
    dh = os.path.join(srcdir, "NOCTIS-D.H")
    if os.path.exists(dh):
        t = strip_comments(open(dh, "rb").read().decode("latin-1"))
        m = re.search(r"#define\s+sc_bytes\s+(\d+)", t)
        if m:
            s.add(int(m.group(1)) - 65536,
                  "sc_bytes %s = 65536 + K (NOCTIS-D.H:47-54, "
                  "\"estesa a 64Kb+4bytes\")" % m.group(1))

    # ---- independent constraint: wave() discards the offset it loaded ----
    n0 = os.path.join(srcdir, "NOCTIS-0.CPP")
    if os.path.exists(n0):
        t = strip_comments(open(n0, "rb").read().decode("latin-1"))
        for func, body in split_functions(t):
            if func != "wave":
                continue
            if not RE_LES.search(body):
                continue
            m = re.search(r"add\s+ax\s*,\s*(\d+)[\s\S]{0,120}?mov\s+di\s*,\s*ax", body)
            w = RE_ESREF.search(body)
            if m and w and not w.group(2):
                s.add(int(m.group(1)),
                      "wave() loads p_background's offset into DI with `les`, "
                      "throws it away (`mov di, ax`) and adds the literal %s to "
                      "the index instead -- the literal must be the offset it "
                      "replaced" % m.group(1))

    ks = sorted(set(k for k, _ in s.eq))
    print("fbx_ksolve -- an independent re-derivation of the far-pointer offset")
    print("  corpus        %s (%d files)" % (srcdir, len(files)))
    print("  sites         %d addressing sites censused over the whole tree"
          % len(s.sites))
    print("  constraints   %d" % len(s.eq))
    if census:
        print("\n  censused sites (file, function, offset-loaded?, displacement):")
        for f, fn, o, d, t in s.sites:
            print("    %-14s %-22s o=%d  disp=%-3d  %s" % (f, fn, o, d, t))
        print()
        for k, why in s.eq:
            print("    K = %-3d  %s" % (k, why))
        print()
    if len(ks) != 1:
        print("  RESULT: REFUSED -- %d constraints imply %d different offsets %s"
              % (len(s.eq), len(ks), ks))
        return 1
    k = ks[0]
    print("  RESULT: SOLVED  K = %d  (%d constraints, one solution)" % (k, len(s.eq)))

    if cross:
        cp = subprocess.run([cross, "--ksolve", srcdir],
                            capture_output=True, text=True)
        out = cp.stdout.strip()
        m = re.search(r"K=(-?\d+)", out)
        other = int(m.group(1)) if m else None
        agree = (other == k)
        print("  CROSS-CHECK   %s: %s" % (os.path.basename(cross), out))
        print("  %s  two producers, two parses, %s" %
              ("PASS" if agree else "FAIL",
               "one constant" if agree else "DISAGREEMENT -- %s vs %s" % (k, other)))
        if not agree:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
