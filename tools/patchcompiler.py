"""patchcompiler.py - produce a patched copy of the L.in.oleum compiler source.

Adds a split-multiply instruction pair and fixes the relative-address sign bug
in machine-language fragments.

Reads  main/lib/gen/compiler.txt   (never modified)
Writes patched/compiler114m.txt

Every edit is anchored to a distinctive string and asserts on the number of
matches, so a wrong or ambiguous anchor fails loudly instead of silently
corrupting the source.

WHAT CHANGES

1. Two quickreference records appended after the last one (q73). Appending at
   the END matters: the pattern index is a running sum over earlier records,
   so nothing existing is renumbered. Unsigned precedes signed, following the
   /%' and /% precedent.

2. Eighteen operand-configuration records appended to the packed vector, in
   the same order. The two tables are walked in lockstep, so their orders must
   agree.

3. The pattern count 6241 -> 6483 everywhere it appears: the read buffer, the
   block size, the memory check, and the exact validity check.

4. The record count 609 -> 627 in both the declaration and the unpack length,
   and the hardcoded quickreference bound 74 -> 76.

5. The relative-address sign fix. At "ccs accept drift" the compiler always
   subtracts the drift digit, and both + and - reach it, so the sign is inert:
   <+4 dLabel> and <-4 dLabel> produce the same address.

   The fix deliberately does NOT make + add, even though the manual says it
   should. Subtracting is the useful behaviour for x86, where a relative
   displacement is measured from the END of the instruction, and the manual's
   own worked example requires it (pc 103, label 109, byte 05 = 109-103-1).
   Shipped code such as examples/lm/utils/586utils.txt depends on it. So + is
   left exactly as it is and - is made to add, which restores meaning to the
   sign without breaking anything that already works.
"""

import os
import re
import sys

SRC = r"C:\programmieren\linoleum\main\lib\gen\compiler.txt"
OUTDIR = r"C:\programmieren\linoleum\patched"
DST = os.path.join(OUTDIR, "compiler114m.txt")

OLD_PATTERNS, NEW_PATTERNS = "6241", "6483"
OLD_RECORDS, NEW_RECORDS = "609", "627"
OLD_QUICKREF, NEW_QUICKREF = "74", "76"

CONFIG_BLOCK = """
	( integer unsigned split multiply )

	register;	register;	       25;
	register;	direct; 		5;
	register;	indirect;	       25;
	direct; 	register;		5;
	direct; 	direct; 		1;
	direct; 	indirect;		5;
	indirect;	register;	       25;
	indirect;	direct; 		5;
	indirect;	indirect;	       25;

	( integer signed split multiply )

	register;	register;	       25;
	register;	direct; 		5;
	register;	indirect;	       25;
	direct; 	register;		5;
	direct; 	direct; 		1;
	direct; 	indirect;		5;
	indirect;	register;	       25;
	indirect;	direct; 		5;
	indirect;	indirect;	       25;
"""

QUICKREF_BLOCK = (
    " q74 = { *%'\t}; extend upto: 7; 121; 27;\n"
    " q75 = { *%\t}; extend upto: 7; 121; 27;"
)

DRIFT_OLD = """      "ccs accept drift"
	[po value] - c;"""

DRIFT_NEW = """      "ccs accept drift"
      (a plus sign subtracts the drift: relative addresses are measured from
       the end of the instruction, so the digit counts the bytes that follow
       the address field. a minus sign now adds, which restores meaning to the
       sign - previously both signs subtracted and - was indistinguishable
       from +.)
      ? [pces] = hyphen -> ccs drift backwards;
	[po value] - c;
	-> ccs assume scalar;
      "ccs drift backwards"
	[po value] + c;"""


def edit(text, old, new, expect, label):
    n = text.count(old)
    if n != expect:
        raise SystemExit(f"FAILED [{label}]: anchor found {n} times, expected {expect}")
    print(f"  ok  {label}  ({expect} site{'s' if expect > 1 else ''})")
    return text.replace(old, new)


def main():
    text = open(SRC, encoding="latin-1").read()
    original = text

    print("patching the compiler source (on a copy):\n")

    # -- 1. quickreference records ------------------------------------------
    m = re.search(r"^ q73 = \{.*$", text, re.M)
    if not m:
        raise SystemExit("FAILED: could not find the last quickreference record q73")
    text = text[:m.end()] + "\n" + QUICKREF_BLOCK + text[m.end():]
    print("  ok  quickreference records q74 (*%') and q75 (*%) appended after q73")

    # -- 2. operand configuration records ------------------------------------
    anchor = "( exchange values )"
    i = text.find(anchor)
    if i < 0:
        raise SystemExit("FAILED: could not find the exchange-values config block")
    j = text.find("make: units;", i)
    if j < 0:
        raise SystemExit("FAILED: could not find the end of the config vector")
    text = text[:j] + CONFIG_BLOCK.lstrip("\n") + "\n    " + text[j:]
    print("  ok  18 operand-configuration records appended (9 unsigned, 9 signed)")

    # -- 3. pattern count ----------------------------------------------------
    text = edit(text, f"cpu pack = {OLD_PATTERNS}", f"cpu pack = {NEW_PATTERNS}",
                1, "read buffer size")
    text = edit(text, f"\t  {OLD_PATTERNS}\t  (total number of patterns)",
                f"\t  {NEW_PATTERNS}\t  (total number of patterns)",
                2, "block size and memory check")
    text = edit(text, f"a * {OLD_PATTERNS};", f"a * {NEW_PATTERNS};",
                1, "pack validity check")
    text = edit(text, f"alignment * {OLD_PATTERNS} + 8", f"alignment * {NEW_PATTERNS} + 8",
                1, "validity-check comment")
    text = edit(text, f"complessively {OLD_PATTERNS}", f"complessively {NEW_PATTERNS}",
                1, "config vector comment")

    # -- 4. record counts and quickreference bound ---------------------------
    text = edit(text, f"ip records\t= {OLD_RECORDS} mtp 3;",
                f"ip records\t= {NEW_RECORDS} mtp 3;", 1, "ip records declaration")
    text = edit(text, f"[up length] = {OLD_RECORDS} mtp 3;",
                f"[up length] = {NEW_RECORDS} mtp 3;", 1, "unpack length")
    text = edit(text, f"? a < {OLD_QUICKREF} mtp 9 relating ip quickreference",
                f"? a < {NEW_QUICKREF} mtp 9 relating ip quickreference",
                1, "quickreference table bound")
    text = edit(text, f"quick reference, {OLD_QUICKREF} records",
                f"quick reference, {NEW_QUICKREF} records", 1, "quickref comment")

    # -- 5. relative-address sign fix ----------------------------------------
    text = edit(text, DRIFT_OLD, DRIFT_NEW, 1, "relative-address sign fix")

    os.makedirs(OUTDIR, exist_ok=True)
    open(DST, "w", encoding="latin-1", newline="").write(text)

    print(f"\nwrote {DST}")
    print(f"  {len(original)} -> {len(text)} bytes  ({len(text)-len(original):+d})")
    print(f"\n  {SRC}")
    print("  is unchanged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
