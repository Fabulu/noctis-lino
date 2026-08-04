"""genmul.py - generate MUL-split patterns for a L.in.oleum CPU pack.

Produces the register x register block of a proposed `*%` (signed) and `*%'`
(unsigned) split-multiply instruction, by direct analogy with Ghignola's
existing `/%` split-divide block at pattern index 5997.

Semantics, mirroring `/%`:   a *% b   ->   a = low 32 bits, b = high 32 bits

x86 background:
    mul  r/m32  = F7 /4   edx:eax = eax * r/m32   (unsigned)
    imul r/m32  = F7 /5   edx:eax = eax * r/m32   (signed)

Both read only eax and the r/m operand, and write edx:eax. That makes this
strictly simpler than the divide case: idiv consumes edx:eax as its dividend,
so `/%` must stage its divisor through ebp and issue cdq first. We need
neither, and several cases collapse to two bytes.

Registers: lino A B C D E map to eax ebx ecx edx esi. ebp is scratch (Ghignola
uses it the same way at idx 6000). edi is the workspace origin and untouchable.

NOTHING IS WRITTEN TO THE PACK. This emits patterns and a listing for review
and disassembly. Modifying the toolchain needs the author's authorisation.
"""

import sys

# lino register id -> x86 encoding
A, B, C, D, E = 0, 1, 2, 3, 4
LINO = ["A", "B", "C", "D", "E"]
X86 = {A: 0, B: 3, C: 1, D: 2, E: 6}      # eax ebx ecx edx esi
X86NAME = {0: "eax", 3: "ebx", 1: "ecx", 2: "edx", 6: "esi", 5: "ebp"}
EBP = 5

TERM = b"++"
ALIGN = 48


def push(r):  return [0x50 + r]
def pop(r):   return [0x58 + r]
def mov(dst, src):  # mov r32, r32  -> 8B /r
    return [0x8B, 0xC0 + dst * 8 + src]
def mul(r, signed):  # F7 /4 unsigned, F7 /5 signed
    return [0xF7, (0xE8 if signed else 0xE0) + r]
def xchg_eax(r):  return [0x90 + r]


def gen_reg_reg(r1, r2, signed):
    """Pattern for  <reg r1> *% <reg r2>  -> r1 = low, r2 = high."""
    e1, e2 = X86[r1], X86[r2]
    code, note = [], []

    # eax and edx are always clobbered; preserve them if they aren't operands.
    save_a = A not in (r1, r2)
    save_d = D not in (r1, r2)
    if save_a: code += push(0)
    if save_d: code += push(2)

    if r1 == r2:
        # Degenerate: both results want the same register. Ghignola's `/%`
        # does the same thing at idx 5997 - compute, keep the low half, drop
        # the high. Documented rather than forbidden.
        note.append("degenerate r1==r2: high half discarded, as /% does")
        if e1 != 0:
            code += mov(0, e1)
        code += mul(e1 if e1 != 0 else 0, signed)
        if e1 != 0:
            code += mov(e1, 0)
    else:
        # The multiplier must survive until the multiply issues. It only
        # breaks if the multiplier lives in eax and eax must be reloaded with
        # the multiplicand - then stage it through ebp.
        multiplier = e2
        if e2 == 0 and e1 != 0:
            code += mov(EBP, 0)
            multiplier = EBP
            note.append("op2 is A: staged through ebp before eax is reloaded")

        if e1 != 0:
            code += mov(0, e1)

        code += mul(multiplier, signed)

        # Place the results. Order matters when a destination is itself eax
        # or edx and still holds a value the other destination needs.
        if r1 == D and r2 == A:
            code += xchg_eax(2)      # low->edx, high->eax in one instruction
            note.append("results land inverted; one xchg fixes both")
        elif r1 == D:
            code += mov(e2, 2)       # read edx before overwriting it
            code += mov(2, 0)
            note.append("op1 is D: high half read out before edx is rewritten")
        else:
            if e1 != 0:
                code += mov(e1, 0)
            if e2 != 2:
                code += mov(e2, 2)

    if save_d: code += pop(2)
    if save_a: code += pop(0)
    return code, note


def emit(code):
    """Pad a pattern to the 48-byte record stride, as the pack does."""
    rec = bytes(code) + TERM
    if len(rec) > ALIGN:
        raise SystemExit(f"pattern too long: {len(rec)} > {ALIGN}")
    pad = bytearray()
    while len(rec) + len(pad) < ALIGN:
        pad += b"\x87\xdb"           # xchg ebx,ebx - the pack's filler
    return (rec + bytes(pad))[:ALIGN]


def main():
    signed = "--unsigned" not in sys.argv
    sym = "*%" if signed else "*%'"
    print(f"{sym}  register x register block, 25 patterns")
    print(f"    {'imul' if signed else 'mul'} r/m32 = F7 /{5 if signed else 4}")
    print(f"    semantics: op1 = low 32 bits, op2 = high 32 bits\n")

    longest = 0
    out = []
    for r1 in range(5):
        for r2 in range(5):
            code, note = gen_reg_reg(r1, r2, signed)
            rec = emit(code)
            out.append(rec)
            longest = max(longest, len(code) + 2)
            hexs = " ".join(f"{b:02X}" for b in code)
            print(f"  {LINO[r1]},{LINO[r2]}  {hexs:<42} ({len(code)+2} bytes)")
            for n in note:
                print(f"         ^ {n}")

    print(f"\n  longest pattern {longest} bytes, record stride {ALIGN} - fits")
    print(f"  generated {len(out)} records, {len(out)*ALIGN} bytes")

    path = "mulsplit_regreg.bin"
    with open(path, "wb") as fh:
        fh.write(b"".join(out))
    print(f"  wrote {path} for disassembly")
    print("\n  (nothing in main/cpu/ was touched)")


if __name__ == "__main__":
    main()
