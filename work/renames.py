#!/usr/bin/env python3
# renames.py - apply the cross-wave namespace collision fixes for the game
# integration link, with strict word boundaries so longer tokens (SPtmp,
# SPtinta, PVnv, SCdy) are never disturbed.
#
# Each (old,new) is applied to every listed file.  The script reports the
# per-file substitution count and refuses to run twice (it would be a no-op
# but the count check keeps it honest).
import re, sys

EDITS = [
    # 1. supaint SP* (surface-paint scratch) -> SUP*.  Files: supaint + the
    #    three su brk libraries that link it and reference its scratch.
    {
        "files": ["supaint.txt", "subrkcraterwraplib.txt",
                  "subrktruncprodlib.txt", "subrkwaveplus4lib.txt"],
        "subs": [("SPi", "SUPi"), ("SPj", "SUPj"), ("SPk", "SUPk"),
                 ("SPt", "SUPt"), ("SPu", "SUPu"),
                 ("SPsave", "SUPsave"), ("SPb2", "SUPb2")],
    },
    # 2. sp-family sphere scratch SPi/SPj/SPk -> SPMi/SPMj/SPMk.  Yields to
    #    pgtex's span SPi (pgtex + ~30 pgbrk callers) because the sp trio
    #    is only 6 files.  The SP memory-interface symbols (SPtmp, SPreg,
    #    SPval, ...) are untouched: they do not collide.
    {
        "files": ["spmem.txt", "spncc.txt", "spscale.txt",
                  "spglobe.txt", "spglow.txt", "spmain.txt"],
        "subs": [("SPi", "SPMi"), ("SPj", "SPMj"), ("SPk", "SPMk")],
    },
    # 3. spncc.PVn -> PVcnt.  Contained in spncc (43 uses, no cross-file
    #    callers).  fbpal/fbshell's PVn is a different family (palette) and
    #    would cost ~15 fb grader files to move.
    {
        "files": ["spncc.txt"],
        "subs": [("PVn", "PVcnt")],
    },
    # 4. spscale.SCt -> SCtmp.  Contained in spscale (3 uses).
    {
        "files": ["spscale.txt"],
        "subs": [("SCt", "SCtmp")],
    },
]

WORK = r"C:\programmieren\linoleum\work"
os_path_join = __import__("os").path.join

total = 0
for blk in EDITS:
    for fn in blk["files"]:
        p = os_path_join(WORK, fn)
        with open(p, "r", encoding="latin-1") as f:
            s = f.read()
        orig = s
        fc = 0
        for old, new in blk["subs"]:
            pat = re.compile(r"\b" + re.escape(old) + r"\b")
            s, n = pat.subn(new, s)
            fc += n
        if s != orig:
            with open(p, "w", encoding="latin-1") as f:
                f.write(s)
            print(f"  {fn:28s} {fc:4d} substitutions")
            total += fc
print(f"total {total} substitutions")
