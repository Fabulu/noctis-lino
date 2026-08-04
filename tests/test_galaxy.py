"""GUARDS: work/galaxy2.txt - the galaxy hash rewritten on the *% instruction -
still produces Noctis IV's galaxy, bit for bit.

This is the acceptance test for the rewrite. It rebuilds both lino versions
from source, runs them, regenerates the C and Python references from source
too, and demands that all five agree on every one of the 343 sectors. Nothing
is read from a stored .bin: any of the five going stale would otherwise let a
regression hide behind a file nobody regenerated.

The five sides share no code and no multiply mechanism, which is what makes the
agreement mean something:

    galaxy2   L.in.oleum, `A *% B; A + B;`      compiler114m.exe + -Cpu i386m
    galaxy    L.in.oleum, inline { F7 EB }      stock toolchain
    oracle    C, int64_t, lifted from noctis-iv-lr, compiled here by gcc
    python    noctis-harness/oracle.py, bignum, written against the algorithm
    spec      tests/galaxyspec.py, bignum, the referee this suite carries

Also pinned, because bit-exactness alone cannot see them:

  * SIGNEDNESS AT THE BYTE LEVEL. galaxy2.exe must contain exactly two
    `F7 EB` (imul ebx) and zero `F7 E3` (mul ebx). Sector coordinates go
    negative; an unsigned product gives a different high word and therefore a
    different - perfectly plausible, entirely wrong - galaxy.
  * THE REGISTER x REGISTER FORM. Every form of *% writes the high half over
    its second operand, and in the memory forms that means clobbering the
    variable. Both operands here are read again afterwards, so the source must
    keep using `A = [v]; B = [w]; A *% B;`.
  * THE SWEEP. The C and Python references hardcode k = -3..+3 over 100000-unit
    sectors. Widening the sweep in the lino sources without updating the
    references would compare different things, so the constants are checked.

NEGATIVE CONTROL: the same file with *% changed to *%' is built and run in the
same breath. It must MISMATCH the oracle, and its binary must show F7 E3 where
the real one shows F7 EB. Without that, "all five agree" could be true of a
test that cannot tell signed from unsigned.

HOW IT FAILS: a compiler or pack change that alters *% shows up as a mismatch
against C and Python in the same run that shows galaxy.txt still matching them,
which localises the fault to the *% path immediately.

RUN: python tests/test_galaxy.py   (needs gcc on PATH for the C side)
"""

import os
import re
import subprocess
import sys

import galaxyspec as S
import linoharness as L


GALAXY = os.path.join(L.WORK, "galaxy.txt")
GALAXY2 = os.path.join(L.WORK, "galaxy2.txt")
ORACLE_C = os.path.join(L.HARNESS, "oracle.c")
ORACLE_PY = os.path.join(L.HARNESS, "oracle.py")

# The codegen for `A *% B` followed by `A + B`, as emitted by the i386m pack:
#   push edx; imul ebx; mov ebx,edx; pop edx    <- *% keeps low in eax, high in ebx
FOLD_SITE_SIGNED = bytes.fromhex("52 f7 eb 8b da 5a".replace(" ", ""))
FOLD_SITE_UNSIGNED = bytes.fromhex("52 f7 e3 8b da 5a".replace(" ", ""))
# galaxy.txt's hand-written fragment: imul ebx; add eax,edx
FRAG_SITE = bytes.fromhex("f7 eb 03 c2".replace(" ", ""))

MUL_FORM = re.compile(
    r"A\s*=\s*\[(\w+)\];\s*B\s*=\s*\[(\w+)\];\s*A\s*\*%\s*B;\s*A\s*\+\s*B;\s*\[accum\]\s*=\s*A;")


def strip_comments(text):
    """Remove ( ... ) comment regions, innermost first."""
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r"\([^()]*\)", " ", text)
    return text


def constants_of(text):
    body = strip_comments(text)
    out = {}
    for name in ("SECTORSIZE", "CUTOFF", "SPAN", "KOFFSET", "PERSECTOR"):
        m = re.search(r"\b%s\s*=\s*(\d+)\s*;" % name, body)
        out[name] = int(m.group(1)) if m else None
    return out


def make_unsigned_mutant(path):
    """galaxy2.txt with *% swapped for *%' - the negative control."""
    with open(GALAXY2, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    mutated, n = re.subn(r"A \*% B;", "A *%' B;", text)
    mutated = mutated.replace("{ galaxy2 }", "{ tguns }")
    mutated = mutated.replace("{ galaxy2.bin }", "{ tguns.bin }")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(mutated)
    return n


def main():
    c = L.Check("test_galaxy - the *% rewrite reproduces Noctis IV's galaxy")
    gen = L.gen_dir()

    # ------------------------------------------------------ 1. source contracts
    with open(GALAXY2, "r", encoding="utf-8", errors="replace") as fh:
        g2 = fh.read()
    with open(GALAXY, "r", encoding="utf-8", errors="replace") as fh:
        g1 = fh.read()

    k2, k1 = constants_of(g2), constants_of(g1)
    want = {"SECTORSIZE": S.SECTORSIZE, "CUTOFF": S.CUTOFF, "SPAN": S.SPAN,
            "KOFFSET": S.KOFFSET, "PERSECTOR": S.PERSECTOR}
    c.eq(k2, want, "galaxy2.txt constants match the sweep the references assume")
    c.eq(k1, want, "galaxy.txt constants match the sweep the references assume")

    body2 = strip_comments(g2)
    sites = MUL_FORM.findall(body2)
    c.eq(sites, [("tempx", "sumxz"), ("tempy", "idk")],
         "galaxy2.txt uses exactly two register x register *% folds")
    c.eq(len(re.findall(r"\*%'", body2)), 0,
         "galaxy2.txt contains no unsigned *%' anywhere in code")
    c.eq(len(re.findall(r"\*%(?!')", body2)), 2,
         "galaxy2.txt contains no *% outside those two folds")

    body1 = strip_comments(g1)
    c.eq(len(re.findall(r"F7\s+EB", body1)), 1,
         "galaxy.txt still carries exactly one { F7 EB } fragment")
    c.eq(len(re.findall(r"F7\s+E3", body1)), 0,
         "galaxy.txt carries no unsigned { F7 E3 } fragment")

    # ------------------------------------------------------ 2. build and run both
    sets = {}

    blob, exe2, note = L.build_and_run(GALAXY2, os.path.join(L.WORK, "galaxy2.bin"),
                                       L.EXT_COMPILER, L.EXT_CPU)
    if not c.ok(blob is not None, "galaxy2.txt builds and runs (extended toolchain)", note):
        return c.done()
    sets["galaxy2"] = S.unpack(blob)
    c.note("galaxy2.bin  %d bytes  sha256 %s" % (len(blob), L.sha(blob)))

    blob, exe1, note = L.build_and_run(GALAXY, os.path.join(L.WORK, "galaxy.bin"),
                                       L.STOCK_COMPILER, L.STOCK_CPU)
    if not c.ok(blob is not None, "galaxy.txt builds and runs (stock toolchain)", note):
        return c.done()
    sets["galaxy"] = S.unpack(blob)

    # ------------------------------------------------------ 3. references, fresh
    blob, note = L.gcc_build_and_run(ORACLE_C, "oracle.exe", "oracle.bin", cwd=gen)
    if not c.ok(blob is not None, "C oracle compiles with gcc and runs", note or ""):
        return c.done()
    sets["oracle"] = S.unpack(blob)

    p = subprocess.run([sys.executable, ORACLE_PY], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=gen)
    pyout = (p.stdout or "").strip()
    c.ok(p.returncode == 0 and "agree on all" in pyout,
         "noctis-harness/oracle.py runs and agrees with the C oracle",
         pyout.replace("\n", " / "))
    with open(os.path.join(gen, "python.bin"), "rb") as fh:
        sets["python"] = S.unpack(fh.read())

    sets["spec"] = S.records(S.cube())

    # ------------------------------------------------------ 4. five-way agreement
    L.compare_records(c, sets, "implementations")

    flags = {}
    for r in sets["spec"]:
        flags[r[4]] = flags.get(r[4], 0) + 1
    c.note("flag histogram over the acceptance sweep: %s" % sorted(flags.items()))
    c.note("no cutoff branch fires anywhere on the sector grid - that is what "
           "test_galaxy_stress.py exists to cover")

    # ------------------------------------------------------ 5. signedness in bytes
    blob2, imul2 = L.opcode_sites(exe2, L.IMUL_EBX)
    _, mul2 = L.opcode_sites(exe2, L.MUL_EBX)
    c.eq(len(imul2), 2, "galaxy2.exe contains two signed imul ebx (F7 EB)")
    c.eq(len(mul2), 0, "galaxy2.exe contains no unsigned mul ebx (F7 E3)")
    c.ok(all(blob2[o - 1:o + 5] == FOLD_SITE_SIGNED for o in imul2),
         "both sites are the expected *% codegen (push edx; imul ebx; mov ebx,edx; pop edx)",
         " ".join(blob2[o - 1:o + 7].hex(" ") for o in imul2))

    blob1, imul1 = L.opcode_sites(exe1, L.IMUL_EBX)
    _, mul1 = L.opcode_sites(exe1, L.MUL_EBX)
    c.eq(len(imul1), 1, "galaxy.exe contains one signed imul ebx (F7 EB)")
    c.eq(len(mul1), 0, "galaxy.exe contains no unsigned mul ebx (F7 E3)")
    c.ok(all(blob1[o:o + 4] == FRAG_SITE for o in imul1),
         "its site is the hand-written fragment (imul ebx; add eax,edx)",
         " ".join(blob1[o:o + 4].hex(" ") for o in imul1))

    # ------------------------------------------- 6. negative control: unsigned *%'
    mutant = os.path.join(gen, "tguns.txt")
    n = make_unsigned_mutant(mutant)
    c.eq(n, 2, "negative control derived from galaxy2.txt by swapping both *% for *%'")
    blob, exeu, note = L.build_and_run(mutant, os.path.join(gen, "tguns.bin"),
                                       L.EXT_COMPILER, L.EXT_CPU)
    if c.ok(blob is not None, "unsigned mutant builds and runs", note):
        mrecs = S.unpack(blob)
        bad = [i for i in range(len(mrecs)) if mrecs[i] != sets["oracle"][i]]
        c.ok(len(bad) > 0,
             "unsigned mutant DISAGREES with the oracle - the comparison can "
             "tell signed from unsigned",
             "%d/%d sectors differ" % (len(bad), len(mrecs)))
        blobu, imulu = L.opcode_sites(exeu, L.IMUL_EBX)
        _, mulu = L.opcode_sites(exeu, L.MUL_EBX)
        c.eq(len(mulu), 2, "unsigned mutant's binary shows two F7 E3")
        c.eq(len(imulu), 0, "unsigned mutant's binary shows no F7 EB")
        c.ok(all(blobu[o - 1:o + 5] == FOLD_SITE_UNSIGNED for o in mulu),
             "  ...in the same wrapper - so the byte scan discriminates on one opcode",
             " ".join(blobu[o - 1:o + 7].hex(" ") for o in mulu))

    return c.done()


if __name__ == "__main__":
    sys.exit(main())
