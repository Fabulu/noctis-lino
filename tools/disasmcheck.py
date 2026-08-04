"""disasmcheck.py - disassemble generated patterns with an independent tool.

genmul.py emits bytes from my reasoning about x86 encoding. That reasoning
could be wrong. ndisasm has no idea what we intended, so if it reads back the
instructions we meant, the encoding is right.

This checks encoding only. It does NOT prove the patterns compute the right
thing - that needs emulation over real inputs, which is the next step.
"""

import subprocess
import sys

ALIGN = 48
TERM = b"++"
LINO = ["A", "B", "C", "D", "E"]


def code_of(record):
    i = record.find(TERM)
    return record[:i] if i >= 0 else record


def disasm(code):
    p = subprocess.run(
        ["ndisasm", "-b", "32", "-"], input=code,
        capture_output=True,
    )
    lines = []
    for raw in p.stdout.decode("utf-8", "replace").splitlines():
        parts = raw.split(None, 2)
        if len(parts) == 3:
            lines.append(parts[2].strip())
    return lines


def main(path):
    blob = open(path, "rb").read()
    n = len(blob) // ALIGN
    print(f"{n} patterns from {path}\n")

    problems = 0
    idx = 0
    for r1 in range(5):
        for r2 in range(5):
            if idx >= n:
                break
            code = code_of(blob[idx * ALIGN : (idx + 1) * ALIGN])
            ops = disasm(code)
            joined = " ; ".join(ops)
            print(f"  {LINO[r1]},{LINO[r2]}   {joined}")

            # Every pattern must contain exactly one multiply, and must never
            # touch edi (the workspace origin) or esp beyond balanced push/pop.
            muls = [o for o in ops if o.startswith(("mul ", "imul "))]
            if len(muls) != 1:
                print(f"        !! expected exactly one multiply, found {len(muls)}")
                problems += 1
            if any("edi" in o for o in ops):
                print("        !! touches edi (workspace origin)")
                problems += 1
            if any(o.startswith("db ") or "???" in o for o in ops):
                print("        !! did not decode as valid x86")
                problems += 1
            pushes = sum(1 for o in ops if o.startswith("push"))
            pops = sum(1 for o in ops if o.startswith("pop"))
            if pushes != pops:
                print(f"        !! unbalanced stack: {pushes} push, {pops} pop")
                problems += 1
            idx += 1

    print()
    if problems:
        print(f"{problems} problem(s) found")
        return 1
    print("all patterns decode as valid x86, one multiply each,")
    print("balanced stack, workspace origin untouched")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "mulsplit_regreg.bin"))
