#!/usr/bin/env python3
# symcollide.py - find declared-symbol collisions across the game's libraries.
#
# L.in.oleum has no linker namespacing: every constant, variable, workspace
# label and quoted programme label is global across all linked libraries. This
# extracts every declared identifier from each library and reports the ones
# claimed by two or more libraries, so the integration driver can prefix them.
#
# It models the compiler's own check (the thing that aborted at spmem.txt:277),
# so what it reports is exactly the set of remaining collisions to resolve.

import re, sys, os
from collections import defaultdict

WORK = r"C:\programmieren\linoleum\work"

# The exact library set linked by work/game.txt, in link order.
LIBS = [
    "fp/fpabi", "fp/fpctl", "fp/fpx87", "fp/fpconv", "fp/fpchains",
    "fbmem", "fbpal", "fbtick", "fbshell",
    "pgfp", "pgmem", "pgrast", "pgtex", "pgproj",
    "spmem", "spscale", "spmap", "spglobe", "spglow", "spbg", "spwhite", "spdark", "spncc",
    "mul64frag", "brtl",
    "suseed", "surng", "subuf", "susm", "supaint", "supal", "sucase",
    "grnd",
    "nsident", "mgloop", "mgnav", "mgin",
    # svsave/svstarmap/clconsole are standalone graders (program name =),
    # not pure libraries; excluded from the pure-library link.
]

# A declaration line in constants/variables/workspace looks like
#   NAME = expr ;     or   NAME mtp expr ;   (mtp = multiply to power)
# Names are uppercase tokens possibly with digits/underscores.  Skip comment
# lines and the section headers themselves.
DECL_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_]*)\s*(?:=|\bmtp\b)")

# A quoted programme label:  "Label name"   at the start of a programme block.
LABEL_RE = re.compile(r'^\s*"([^"]+)"\s*$')

def sections(path):
    """Yield (section_kind, text_lines) for constants/variables/workspace/programme."""
    sec = None
    buf = []
    for line in open(path, encoding="latin-1", errors="replace"):
        stripped = line.strip()
        m = re.match(r'^"([a-zA-Z ]+)"\s*$', line)
        if m:
            name = m.group(1).strip()
            if name in ("constants", "variables", "workspace", "programme", "directors"):
                if sec:
                    yield sec, buf
                sec = name
                buf = []
                continue
        buf.append(line.rstrip("\n"))
    if sec:
        yield sec, buf

def extract(lib):
    path = os.path.join(WORK, lib + ".txt")
    consts, vars_, work, labels = set(), set(), set(), set()
    # a declaration is "NAME = ..." or "NAME mtp ..."; lines often carry
    # several separated by ';'.  Split each line on ';' and match each part.
    PART_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_]*)\s*(?:=|\bmtp\b)")
    for sec, lines in sections(path):
        if sec == "programme":
            for ln in lines:
                m = LABEL_RE.match(ln)
                if m:
                    labels.add(m.group(1).strip())
            continue
        for ln in lines:
            # strip trailing '(' comment so a part like "NAME = 0  ( note )" is clean
            for part in re.split(r";", ln):
                m = PART_RE.match(part)
                if m:
                    name = m.group(1)
                    if sec == "constants":
                        consts.add(name)
                    elif sec == "variables":
                        vars_.add(name)
                    elif sec == "workspace":
                        work.add(name)
    return consts, vars_, work, labels

def main():
    # lino is CASE-INSENSITIVE, so fold every symbol to lowercase before
    # comparing.  Report the collision in the original casing each lib used.
    owners_const = defaultdict(set)
    owners_var = defaultdict(set)
    owners_work = defaultdict(set)
    owners_label = defaultdict(set)
    unified = defaultdict(set)   # compiler sees one namespace for c/v/w
    casing = {}                   # lower -> set of original spellings
    for lib in LIBS:
        c, v, w, l = extract(lib)
        for s in c:
            owners_const[s.lower()].add(lib); unified[s.lower()].add(lib + "(c)")
            casing.setdefault(s.lower(), set()).add(s)
        for s in v:
            owners_var[s.lower()].add(lib); unified[s.lower()].add(lib + "(v)")
            casing.setdefault(s.lower(), set()).add(s)
        for s in w:
            owners_work[s.lower()].add(lib); unified[s.lower()].add(lib + "(w)")
            casing.setdefault(s.lower(), set()).add(s)
        for s in l:
            owners_label[s.lower()].add(lib)

    def report(title, owners):
        coll = {s: ls for s, ls in owners.items() if len(ls) > 1}
        print(f"\n===== {title}: {len(coll)} collisions =====")
        for s in sorted(coll):
            spell = "/".join(sorted(casing.get(s, {s})))
            print(f"  {s} [{spell}] <- {', '.join(sorted(coll[s]))}")

    report("CONSTANTS", owners_const)
    report("VARIABLES", owners_var)
    report("WORKSPACE", owners_work)
    report("LABELS", owners_label)
    ucoll = {s: ls for s, ls in unified.items() if len(ls) > 1}
    print(f"\n===== UNIFIED (const+var+workspace): {len(ucoll)} collisions =====")
    for s in sorted(ucoll):
        spell = "/".join(sorted(casing.get(s, {s})))
        print(f"  {s} [{spell}] <- {', '.join(sorted(ucoll[s]))}")

if __name__ == "__main__":
    main()
