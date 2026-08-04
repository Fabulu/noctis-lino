"""GUARDS: the census this whole track rests on - Noctis IV contains exactly 20
integer multiply sites, 13 of them with 32-bit operands taking the high half,
and only 5 of those are inside the game NOCTIS.MAK actually links. Those 5 are
two algorithms and no more: fast_random (MUL, unsigned) and sky/isthere (IMUL,
signed).

Everything downstream is sized by that number. Two entry points rather than one
signed/unsigned routine, three interchangeable backends, a language extension
proposed and then found unnecessary - all of it is a response to "there are two
of these, one of each signedness". If the census is wrong or drifts, the port
solves the wrong problem and nothing else in the suite notices.

THE SCANNER IS A SECOND IMPLEMENTATION, not a call into
noctis-harness/sitecount_scan.py. It exists because that tool's db decoder
splits its line on ';' - which is Borland's inline-asm STATEMENT SEPARATOR, not
a comment marker - so a multiply hand-encoded as `db 0x66; db 0xf7; db 0xe3` is
invisible to it. That form is live in this codebase (defs.h:168 spells REP_MOVSD
exactly that way), so the headline negative result "no multiply is hidden in raw
opcode bytes" was, as shipped, asserted rather than demonstrated. The decoder
here joins consecutive `db` statements into one instruction and decodes it, and
NEGATIVE CONTROL 1 proves it by planting that very form and finding it.

Pinned here, each as a tuple set rather than a count, so drift names itself:

  * all 20 sites, by file, line, mnemonic, operand width and whether the site
    consumes the high half;
  * the 13 widening 32-bit sites;
  * the linked-game subset, derived from NOCTIS.MAK's EXE_dependencies rather
    than hardcoded, so adding a TU to the game is caught;
  * that no widening site hides in a header, which is what makes a per-TU count
    meaningful at all;
  * NOCTIS-0.CPP:2823 `imul ecx, edx` is low-half-only AND dead - ecx is
    overwritten two instructions later, keyed on the surrounding text rather
    than on line numbers;
  * the independent corroboration from noctis-iv-lr, where a different author
    de-assembled the same game and needed int64 in exactly five places.

NEGATIVE CONTROLS, all by mutating the source text IN MEMORY (the reference
clones are never written to):
  1. a multiply hidden as `db 0x66; db 0xf7; db 0xe3` is found;
  2. deleting fast_random's `db 0x66; mul dx` is detected as a missing site;
  3. flipping that MUL to IMUL is detected as a changed site - a census that
     could not see signedness would be useless here, because the signedness is
     the reason there are two entry points;
  4. text full of `db 0x66; mov ...` prefixes and wide hex constants yields no
     sites, so the scanner is not just matching everything it sees.

HOW IT FAILS: if either reference clone is updated, the failing check prints the
unexpected and missing site tuples side by side, so it is immediately clear
whether a multiply appeared, moved or changed signedness.

RUN: python tests/test_sitecensus.py   (needs the two reference clones)
"""

import os
import re
import subprocess
import sys

import linoharness as L


NIV_PLUS = r"C:\programmieren\noctis\niv-plus\source"
NIV_LR = r"C:\programmieren\noctis\niv-lr\src"

# (file, line, mnemonic, operand width, consumes the high half)
EXPECTED_SITES = [
    ("DL.CPP",       460, "IMUL", 32, True),
    ("DL.CPP",       468, "IMUL", 32, True),
    ("NOCTIS-0.CPP", 1093, "MUL",  32, True),
    ("NOCTIS-0.CPP", 2823, "IMUL", 32, False),
    ("NOCTIS-0.CPP", 2835, "IMUL", 32, True),
    ("NOCTIS-0.CPP", 2846, "IMUL", 32, True),
    ("NOCTIS-0.CPP", 4585, "MUL",  16, True),
    ("NOCTIS-0.CPP", 4823, "IMUL", 16, True),
    ("NOCTIS-0.CPP", 4914, "IMUL", 16, True),
    ("NOCTIS-0.CPP", 5673, "IMUL", 32, True),
    ("NOCTIS-0.CPP", 5681, "IMUL", 32, True),
    ("NOCTIS-0.CPP", 6054, "IMUL", 16, True),
    ("NOCTIS-1.CPP", 1686, "IMUL", 16, True),
    ("NOCTIS.CPP",    357, "MUL",  16, True),
    ("PAR.CPP",       398, "IMUL", 32, True),
    ("PAR.CPP",       409, "IMUL", 32, True),
    ("SL.CPP",        345, "IMUL", 32, True),
    ("SL.CPP",        353, "IMUL", 32, True),
    ("ST.CPP",        458, "IMUL", 32, True),
    ("ST.CPP",        466, "IMUL", 32, True),
]

# The widening 32-bit sites inside the linked game, and the algorithm each
# belongs to. fast_random is the ONLY unsigned one in the whole game.
EXPECTED_GAME_SITES = [
    ("NOCTIS-0.CPP", 1093, "MUL"),    # fast_random
    ("NOCTIS-0.CPP", 2835, "IMUL"),   # sky
    ("NOCTIS-0.CPP", 2846, "IMUL"),   # sky
    ("NOCTIS-0.CPP", 5673, "IMUL"),   # isthere
    ("NOCTIS-0.CPP", 5681, "IMUL"),   # isthere
]

EXPECTED_INT64_LINES = [834, 2390, 2407, 5298, 5311]


# --------------------------------------------------------------- the scanner

MNEM = re.compile(r"(?<![A-Za-z0-9_])(i?mul)(?![A-Za-z0-9_])")
BYTE_TOKEN = re.compile(r"0x([0-9A-Fa-f]{1,2})$|([0-9A-Fa-f]{1,2})h$")
# a statement may carry a label, the `asm` keyword and an opening brace before
# its `db`:   i_while:asm {  db 0x66, 0xBB, ...
DBSTMT = re.compile(r"^(?:[A-Za-z_][A-Za-z0-9_]*\s*:)?\s*(?:asm\b)?\s*\{?\s*db\b(.*)$",
                    re.I)


def strip_comments(line):
    return line.split("//")[0].split("/*")[0]


def db_runs(text):
    """Byte runs from the `db` statements of a whole file, as (line, [bytes]).

    Consecutive db statements are JOINED into one run - across the ';'
    separator AND across line breaks - because `db 0x66; db 0xf7; db 0xe3` is
    one instruction written three times, and nothing stops an author from
    putting the three on three lines. Anything that is not a db statement, and
    any db carrying something other than a plain one-byte literal (a symbol, a
    16-bit constant), ends the run, so a wide constant like 0xFF00 can never be
    mistaken for a byte. The run is attributed to the line its first byte is on.
    """
    runs, cur, start = [], [], 0

    def flush():
        if cur:
            runs.append((start, list(cur)))
        del cur[:]

    for n, line in enumerate(text.split("\n"), 1):
        for stmt in [s.strip() for s in strip_comments(line).split(";")]:
            m = DBSTMT.match(stmt)
            if not m:
                flush()
                continue
            clean = True
            for tok in m.group(1).replace("{", " ").replace("}", " ").split(","):
                tok = tok.strip()
                if not tok:
                    continue
                mm = BYTE_TOKEN.match(tok)
                if mm:
                    if not cur:
                        start = n
                    cur.append(int(mm.group(1) or mm.group(2), 16))
                else:
                    clean = False
            if not clean:
                flush()
    flush()
    return runs


def decode_run(bs):
    """(mnemonic, operand width, consumes high half) for every multiply in a
    literal byte run. 0x66 in 16-bit real mode promotes the next instruction to
    32-bit operands."""
    hits, i = [], 0
    while i < len(bs):
        wide = False
        if bs[i] == 0x66:
            wide = True
            i += 1
            if i >= len(bs):
                break
        b = bs[i]
        if b == 0xF7 and i + 1 < len(bs):
            reg = (bs[i + 1] >> 3) & 7
            if reg == 4:
                hits.append(("MUL", 32 if wide else 16, True))
            elif reg == 5:
                hits.append(("IMUL", 32 if wide else 16, True))
        elif b == 0x0F and i + 1 < len(bs) and bs[i + 1] == 0xAF:
            hits.append(("IMUL", 32 if wide else 16, False))
        elif b in (0x69, 0x6B):
            hits.append(("IMUL", 32 if wide else 16, False))
        i += 1
    return hits


def scan_text(text):
    """(line, mnemonic, width, consumes_high) for every multiply in one file.

    Two passes, because either one alone has a blind spot: the mnemonic pass
    cannot see an instruction written as bytes, and the byte pass cannot see
    `db 0x66; imul dx`, where the 32-bit prefix is bytes but the instruction
    is a mnemonic.
    """
    lines = text.split("\n")
    per_line = {}

    for n, line in enumerate(lines, 1):
        code = strip_comments(line)
        if "define" in code:
            continue          # a macro body is a site only where it is used
        for m in MNEM.finditer(code):
            wide = 32 if re.search(r"0x66|66h", code) else 16
            # a two-operand imul (there is a comma after it) keeps the low
            # half only; the one-operand form writes edx:eax
            per_line.setdefault(n, []).append(
                (m.group(1).upper(), wide, "," not in code[m.end():]))

    for start, run in db_runs(text):
        if "define" in strip_comments(lines[start - 1]):
            continue
        for hit in decode_run(run):
            if hit not in per_line.get(start, []):
                per_line.setdefault(start, []).append(hit)

    return [(n,) + hit for n in sorted(per_line) for hit in per_line[n]]


def scan_tree(src):
    rows = []
    for name in sorted(os.listdir(src)):
        if not name.upper().endswith((".CPP", ".H")):
            continue
        with open(os.path.join(src, name), encoding="latin-1") as fh:
            text = fh.read()
        for row in scan_text(text):
            rows.append((name,) + row)
    return rows


def linked_translation_units(src):
    """The .CPP files NOCTIS.MAK actually builds into NOCTIS.EXE."""
    with open(os.path.join(src, "NOCTIS.MAK"), encoding="latin-1") as fh:
        text = fh.read()
    m = re.search(r"EXE_dependencies\s*=(.*?)(?<!\\)\n\s*\n", text, re.S)
    if not m:
        return []
    return sorted({o.upper() + ".CPP"
                   for o in re.findall(r"([A-Za-z0-9_\-]+)\.obj", m.group(1))})


def nivlr_int64_multiply_lines():
    """Lines in the de-assembled reference that need a 64-bit product.

    A multiply, not a declaration: an int64 cast on both sides of a '*'.
    """
    hits = {}
    for root, _, names in os.walk(NIV_LR):
        for name in names:
            if not name.endswith((".cpp", ".h")):
                continue
            path = os.path.join(root, name)
            with open(path, encoding="latin-1") as fh:
                text = fh.read()
            for n, line in enumerate(text.split("\n"), 1):
                code = line.split("//")[0]
                if re.search(r"\(\s*u?int64_t\s*\)[^;]*\*[^;]*\(\s*u?int64_t\s*\)",
                             code):
                    hits.setdefault(os.path.relpath(path, NIV_LR), []).append(n)
    return hits


# ------------------------------------------------------------------- the test

def main():
    c = L.Check("test_sitecensus - the 64-bit-product site count of Noctis IV")

    if not c.ok(os.path.isdir(NIV_PLUS), "niv-plus reference clone present", NIV_PLUS):
        return c.done()

    rows = scan_tree(NIV_PLUS)
    got = sorted(rows)
    want = sorted(EXPECTED_SITES)

    c.eq(len(rows), len(EXPECTED_SITES), "total integer multiply sites")
    detail = ""
    if got != want:
        detail = "unexpected=%s missing=%s" % (sorted(set(got) - set(want)),
                                               sorted(set(want) - set(got)))
    c.ok(got == want, "every site matches by file, line, mnemonic, width and "
                      "whether it takes the high half", detail)

    wide = [r for r in rows if r[3] == 32 and r[4]]
    c.eq(len(wide), 13, "32-bit-operand widening sites (candidate 64-bit)")

    hdr = [r for r in wide if r[0].upper().endswith(".H")]
    c.ok(not hdr, "no widening site hides in a header, so a per-TU count is "
                  "meaningful", repr(hdr))

    # ------------------------------------------------ the linked game only
    tus = linked_translation_units(NIV_PLUS)
    c.eq(tus, ["NOCTIS-0.CPP", "NOCTIS-1.CPP", "NOCTIS.CPP"],
         "NOCTIS.MAK links exactly these translation units")

    game = sorted((r[0], r[1], r[2]) for r in wide if r[0] in tus)
    c.eq(game, sorted(EXPECTED_GAME_SITES),
         "widening sites inside the linked game")
    c.note("the other %d are copies of isthere() in standalone GOES-Net tools "
           "that NOCTIS.MAK does not build" % (len(wide) - len(game)))

    signedness = sorted(set(s[2] for s in game))
    c.eq(signedness, ["IMUL", "MUL"],
         "both signednesses occur, which is why there are two entry points")
    c.eq(sum(1 for s in game if s[2] == "MUL"), 1,
         "exactly one unsigned site in the game (fast_random)")

    # ------------------------------------------ the low-half site is dead
    with open(os.path.join(NIV_PLUS, "NOCTIS-0.CPP"), encoding="latin-1") as fh:
        lines = fh.read().split("\n")
    idx = [i for i, s in enumerate(lines) if "0xAF, 0xCA" in s]
    if c.eq(len(idx), 1, "exactly one hand-encoded `imul ecx, edx` in sky()"):
        i = idx[0]
        after = " ".join(lines[i + 1:i + 3])
        c.ok("mov cx, ax" in after,
             "sky()'s `imul ecx, edx` is DEAD - ecx is overwritten two "
             "instructions later, before any read", after.strip()[:70])

    # -------------------------------- independent corroboration from niv-lr
    if c.ok(os.path.isdir(NIV_LR), "niv-lr reference clone present", NIV_LR):
        lr = nivlr_int64_multiply_lines()
        c.eq(sorted(lr), ["noctis-0.cpp"],
             "the whole de-assembled tree needs int64 products in one file")
        c.eq(lr.get("noctis-0.cpp"), EXPECTED_INT64_LINES,
             "and at exactly these five lines - a different author reached "
             "the same count")

    # ----------------------------------------------- negative control 1
    planted = ("void f(void) {\n"
               "\tasm {\tdb 0x66; db 0xf7; db 0xe3\n"
               "\t\tdb 0x66; mov ax, dx }\n}\n")
    hits = scan_text(planted)
    c.eq(hits, [(2, "MUL", 32, True)],
         "NC1 a multiply hidden as `db 0x66; db 0xf7; db 0xe3` is decoded "
         "(the form the shipped scanner's ';' split cannot see)")

    # ----------------------------------------------- negative control 2
    with open(os.path.join(NIV_PLUS, "NOCTIS-0.CPP"), encoding="latin-1") as fh:
        n0 = fh.read()
    assert "db 0x66; mul dx" in n0
    removed = scan_text(n0.replace("db 0x66; mul dx", "db 0x66; nop", 1))
    c.ok((1093, "MUL", 32, True) not in removed and
         len(removed) == len([r for r in rows if r[0] == "NOCTIS-0.CPP"]) - 1,
         "NC2 deleting fast_random's `mul dx` is detected as a missing site",
         "%d sites without it, %d with"
         % (len(removed), len([r for r in rows if r[0] == "NOCTIS-0.CPP"])))

    # ----------------------------------------------- negative control 3
    flipped = scan_text(n0.replace("db 0x66; mul dx", "db 0x66; imul dx", 1))
    c.ok((1093, "IMUL", 32, True) in flipped and
         (1093, "MUL", 32, True) not in flipped,
         "NC3 flipping fast_random's MUL to IMUL changes the census - the "
         "scanner can see signedness, which is the whole point")

    # ----------------------------------------------- negative control 4
    innocent = ("asm {\tdb 0x66; mov ax, word ptr seed\n"
                "\tdb 0x66; and ax, 0xFF00\n"
                "\tdb 0x66, 0xBB, 0x50, 0xC3, 0x00, 0x00 // mov ebx, 50000\n"
                "\tshl ax, 1 }\n"
                "#define IMUL_EDX db 0x66; db 0xf7; db 0xea\n")
    c.eq(scan_text(innocent), [],
         "NC4 prefixes, wide constants and a macro DEFINITION yield no sites")

    # -------------------------------- the shipped inventory tool still agrees
    tool = os.path.join(L.HARNESS, "sitecount_scan.py")
    p = subprocess.run([sys.executable, tool, "--check"], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    c.ok(p.returncode == 0,
         "noctis-harness/sitecount_scan.py --check agrees (two independent "
         "scanners, one census)", (p.stdout or "").strip().split("\n")[-1])

    return c.done()


if __name__ == "__main__":
    sys.exit(main())
