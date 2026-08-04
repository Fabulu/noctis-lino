# Rough census of C-level multiplications in the Noctis IV DOS sources, split by
# whether the operands are integer or floating. Assembly blocks are excluded --
# sitecount_scan.py covers those. The point is only to establish the ORDER OF
# MAGNITUDE of categories (b) and (d) against the handful of asm sites.
#
# Heuristic, not a parser: an asterisk is counted as a multiply when it sits
# between two value-ish tokens and is not a pointer declaration/dereference.

import re, glob, os, sys

SRC = sys.argv[1] if len(sys.argv) > 1 else r"C:\programmieren\noctis\niv-plus\source"

FLOATNAMES = set()
MUL = re.compile(r"(?<![\*/])\*(?!\*|/|=)")
DECL = re.compile(r"\b(float|double)\s+([^;]+);")


def collect_float_names(text):
    for m in DECL.finditer(text):
        for tok in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", m.group(2)):
            FLOATNAMES.add(tok)


def strip_comments(t):
    t = re.sub(r"/\*.*?\*/", " ", t, flags=re.S)
    t = re.sub(r"//[^\n]*", " ", t)
    return t


def strip_asm(t):
    # asm { ... } blocks and single-line "asm <instr>;"
    t = re.sub(r"\basm\s*\{.*?\}", " ", t, flags=re.S)
    t = re.sub(r"\basm\s+[^;\n]*", " ", t)
    return t


files = [p for p in sorted(glob.glob(os.path.join(SRC, "*")))
         if p.upper().endswith((".CPP", ".H"))]
for p in files:
    collect_float_names(strip_comments(open(p, encoding="latin-1").read()))

tot_int = tot_flt = tot_amb = 0
per = {}
for p in files:
    raw = strip_asm(strip_comments(open(p, encoding="latin-1").read()))
    i = f = a = 0
    for line in raw.split("\n"):
        if re.search(r"\b(char|int|long|short|unsigned|float|double|void|struct)\b\s*\*", line):
            continue  # pointer declaration
        for m in MUL.finditer(line):
            lhs = line[:m.start()].rstrip()
            rhs = line[m.end():].lstrip()
            if not lhs or not re.search(r"[A-Za-z0-9_\)\]]$", lhs):
                continue  # unary deref
            names = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", lhs[-40:] + " " + rhs[:40]))
            hasf = bool(names & FLOATNAMES) or re.search(r"\d\.\d|\de[-+]?\d", lhs[-20:] + rhs[:20])
            if hasf:
                f += 1
            elif re.search(r"[A-Za-z0-9_]", rhs[:1] or " "):
                i += 1
            else:
                a += 1
    per[os.path.basename(p)] = (i, f)
    tot_int += i
    tot_flt += f
    tot_amb += a

for k, v in sorted(per.items(), key=lambda kv: -(kv[1][0] + kv[1][1]))[:14]:
    print("%-16s int-ish %5d   float-ish %5d" % (k, v[0], v[1]))
print()
print("TOTAL C-level multiplies: int-ish %d, float-ish %d" % (tot_int, tot_flt))
print("(all C integer multiplies are Borland 16/32-bit TRUNCATING: low half only)")
