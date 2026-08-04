# Scans the Noctis IV DOS sources for every multiply, including ones hidden
# inside hand-encoded "db 0x.." byte lists that carry no mnemonic. The point is
# to find sites that consume the HIGH half of a product, because only those
# cannot be expressed with L.in.oleum's native 32-bit * / '*.
#
# Two passes:
#   pass 1  textual mnemonics: mul / imul, with or without a 0x66 prefix
#   pass 2  raw opcode bytes in db lists: F7 /4, F7 /5, 0F AF, 69, 6B
# Pass 2 is what catches an author who encoded the instruction by hand because
# Borland's 16-bit assembler refused the 32-bit form.

import os, re, sys, glob

_args = [a for a in sys.argv[1:] if not a.startswith("-")]
SRC = _args[0] if _args else r"C:\programmieren\noctis\niv-plus\source"

BYTE = re.compile(r"0x([0-9A-Fa-f]{2})|\b([0-9A-Fa-f]{2})h\b")
DBLINE = re.compile(r"\bdb\b(.*)")
MNEM = re.compile(r"(?<![A-Za-z_])(i?mul)(?![A-Za-z_0-9])")
FNDEF = re.compile(r"^[A-Za-z_][A-Za-z0-9_ \*]*?\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")


def db_bytes(line):
    """Byte values written literally on a db line, in order."""
    m = DBLINE.search(line)
    if not m:
        return []
    tail = m.group(1).split("//")[0].split(";")[0]
    out = []
    for a, b in BYTE.findall(tail):
        out.append(int(a or b, 16))
    return out


def scan_opcodes(bs):
    """Report multiply opcodes found in a literal byte run. Handles the 0x66
    operand-size prefix, which in 16-bit real mode promotes to 32-bit."""
    hits = []
    i = 0
    while i < len(bs):
        o32 = False
        if bs[i] == 0x66:
            o32 = True
            i += 1
            if i >= len(bs):
                break
        b = bs[i]
        if b == 0xF7 and i + 1 < len(bs):
            reg = (bs[i + 1] >> 3) & 7
            if reg == 4:
                hits.append(("MUL r/m%d -> 2x width" % (32 if o32 else 16), o32))
            elif reg == 5:
                hits.append(("IMUL r/m%d -> 2x width" % (32 if o32 else 16), o32))
        elif b == 0x0F and i + 1 < len(bs) and bs[i + 1] == 0xAF:
            hits.append(("IMUL r,r/m (low half only)", o32))
        elif b in (0x69, 0x6B):
            hits.append(("IMUL r,r/m,imm (low half only)", o32))
        i += 1
    return hits


def enclosing(lines, idx):
    for j in range(idx, -1, -1):
        s = lines[j]
        if s.startswith(("//", " ", "\t")):
            continue
        m = FNDEF.match(s)
        if m and "define" not in s and "return" not in s:
            return m.group(1)
    return "(file scope)"


rows = []
for path in sorted(glob.glob(os.path.join(SRC, "*"))):
    if not path.upper().endswith((".CPP", ".H")):
        continue
    lines = open(path, encoding="latin-1").read().split("\n")
    name = os.path.basename(path)
    for i, line in enumerate(lines):
        code = line.split("//")[0]
        if "define" in code:
            continue
        found = []
        if MNEM.search(code):
            pre32 = "0x66" in code or "66h" in code
            for m in MNEM.finditer(code):
                # two-operand imul (has a comma) keeps only the low half
                rest = code[m.end():]
                two = "," in rest.split("//")[0]
                width = 32 if pre32 else 16
                kind = "IMUL r,r/m (low half only)" if two else \
                       ("%s r/m%d -> 2x width" % (m.group(1).upper(), width))
                found.append((kind, pre32))
        for h in scan_opcodes(db_bytes(code)):
            if h not in found:
                found.append(h)
        for kind, wide in found:
            rows.append((name, i + 1, enclosing(lines, i), kind, wide, line.strip()))

wide64 = [r for r in rows if r[4] and "2x width" in r[3]]

# --------------------------------------------------------------------------
# --check turns the inventory from prose into a regression test. If either
# reference clone is ever updated, the census silently changing underneath the
# recommendation is exactly the failure this catches.
#
# The expected set is the four-tuple (file, line, function, kind) for every
# 32-bit-operand widening multiply, plus the totals, plus the independent
# corroboration from niv-lr: exactly five int64_t/uint64_t multiplies in the
# whole de-assembled tree, written by a different author.

EXPECTED_TOTAL = 20
EXPECTED_WIDE = 13

EXPECTED_WIDE_SITES = [
    ("DL.CPP", 460, "isthere", "IMUL"),
    ("DL.CPP", 468, "isthere", "IMUL"),
    ("NOCTIS-0.CPP", 1093, "fast_random", "MUL"),
    ("NOCTIS-0.CPP", 2835, "sky", "IMUL"),
    ("NOCTIS-0.CPP", 2846, "sky", "IMUL"),
    ("NOCTIS-0.CPP", 5673, "isthere", "IMUL"),
    ("NOCTIS-0.CPP", 5681, "isthere", "IMUL"),
    ("PAR.CPP", 398, "isthere", "IMUL"),
    ("PAR.CPP", 409, "isthere", "IMUL"),
    ("SL.CPP", 345, "isthere", "IMUL"),
    ("SL.CPP", 353, "isthere", "IMUL"),
    ("ST.CPP", 458, "isthere", "IMUL"),
    ("ST.CPP", 466, "isthere", "IMUL"),
]

# The five in the linked game are these; the other eight are copies of the
# same isthere() living in standalone GOES-Net tools, which NOCTIS.MAK does
# not build into NOCTIS.EXE.
EXPECTED_GAME_FILES = ("NOCTIS-0.CPP",)
EXPECTED_GAME_COUNT = 5

NIVLR = r"C:\programmieren\noctis\niv-lr\src"
EXPECTED_INT64_LINES = [834, 2390, 2407, 5298, 5311]


def nivlr_int64_multiplies():
    """Lines in niv-lr/src/noctis-0.cpp with an int64_t/uint64_t multiply."""
    path = os.path.join(NIVLR, "noctis-0.cpp")
    if not os.path.exists(path):
        return None
    hits = []
    for i, line in enumerate(open(path, encoding="latin-1").read().split("\n")):
        if "int64_t" in line and "*" in line.split("int64_t", 1)[0] + line:
            # a multiply, not a declaration: needs a '*' used as an operator
            stripped = line.split("//")[0]
            if "int64_t" in stripped and re.search(r"\)\s*\*|\*\s*\(", stripped):
                hits.append(i + 1)
    return hits


def check():
    ok = True

    def note(good, msg):
        nonlocal ok
        print("%-5s %s" % ("ok" if good else "DRIFT", msg))
        if not good:
            ok = False

    note(len(rows) == EXPECTED_TOTAL,
         "total multiply sites: %d (expected %d)" % (len(rows), EXPECTED_TOTAL))
    note(len(wide64) == EXPECTED_WIDE,
         "32-bit-operand widening sites: %d (expected %d)" % (len(wide64), EXPECTED_WIDE))

    got = sorted((r[0], r[1], r[2], r[3].split()[0]) for r in wide64)
    want = sorted(EXPECTED_WIDE_SITES)
    note(got == want, "widening site file/line/function/kind tuples match")
    if got != want:
        for row in sorted(set(got) - set(want)):
            print("        unexpected: %s" % (row,))
        for row in sorted(set(want) - set(got)):
            print("        missing:    %s" % (row,))

    game = [r for r in wide64 if r[0] in EXPECTED_GAME_FILES]
    note(len(game) == EXPECTED_GAME_COUNT,
         "widening sites inside the linked game: %d (expected %d)"
         % (len(game), EXPECTED_GAME_COUNT))

    lr = nivlr_int64_multiplies()
    if lr is None:
        print("skip  niv-lr not present, cannot corroborate")
    else:
        note(lr == EXPECTED_INT64_LINES,
             "niv-lr noctis-0.cpp int64 multiplies at lines %s (expected %s)"
             % (lr, EXPECTED_INT64_LINES))

    return ok


if "--check" in sys.argv:
    sys.exit(0 if check() else 1)

print("total multiply sites: %d" % len(rows))
print("of which 32-bit-operand widening (edx:eax, candidate 64-bit): %d" % len(wide64))
print()
for r in rows:
    print("%-14s %5d  %-16s %-32s %s" % (r[0], r[1], r[2], r[3], r[5]))
