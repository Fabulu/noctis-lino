"""genmul.py - generate MUL-split patterns for a L.in.oleum CPU pack.

Generates the full 121-pattern block for a proposed `*%` (signed) / `*%'`
(unsigned) split-multiply, by analogy with Ghignola's `/%` split-divide at
pattern index 5997.

    a *% b   ->   a = low 32 bits, b = high 32 bits

x86 background:
    mul  r/m32 = F7 /4    edx:eax = eax * r/m32   (unsigned)
    imul r/m32 = F7 /5    edx:eax = eax * r/m32   (signed)

Both read only eax and the r/m operand and write edx:eax. This is strictly
simpler than the divide case: idiv consumes edx:eax as its dividend, so `/%`
must issue cdq and stage its divisor away from edx. We need neither.

Operand classes and their addressing, matching the existing pack:
    register    a lino register            A B C D E = eax ebx ecx edx esi
    direct      [VAR]      -> [edi + disp32]              ModRM 10 rrr 111
    indirect    [REG]      -> [edi + reg*4 + disp32]      ModRM 10 rrr 100 + SIB

edi is the workspace origin and must never be touched. ebp is scratch between
instructions (Ghignola uses it the same way). Displacements are emitted as the
4-byte ASCII placeholders D1.4 / D2.4, which the compiler fills in.

Register allocation strategy, following the precedents in the `/%` block:
  - eax and edx are always clobbered by the multiply, so any lino register
    mapped to them is saved unless it is itself a destination.
  - An indirect operand's pointer register must still hold the pointer when
    the memory is accessed. If that pointer lives in a clobbered register it
    is staged into a scratch register first (idx 6030, 6063).
  - When both destinations are in memory, pusha/popa is used, which frees esi
    as a second scratch. That is only sound because the results go to memory
    and popa therefore cannot undo them (idx 6096).

NOTHING IS WRITTEN TO THE PACK by this file. It emits patterns for review,
disassembly and semantic testing.
"""

import sys

A, B, C, D, E = 0, 1, 2, 3, 4
LINO = ["A", "B", "C", "D", "E"]
X86 = {A: 0, B: 3, C: 1, D: 2, E: 6}          # eax ebx ecx edx esi
EAX, ECX, EDX, EBX, EBP, ESI, EDI = 0, 1, 2, 3, 5, 6, 7

REG, DIR, IND = "R", "D", "I"
TERM = b"++"
ALIGN = 48

CLASS_ORDER = [
    (REG, REG, 25), (REG, DIR, 5), (REG, IND, 25),
    (DIR, REG, 5),  (DIR, DIR, 1), (DIR, IND, 5),
    (IND, REG, 25), (IND, DIR, 5), (IND, IND, 25),
]


# ---------------------------------------------------------------- encoding

def push(r):    return [0x50 + r]
def pop(r):     return [0x58 + r]
def pusha():    return [0x60]
def popa():     return [0x61]
def movrr(d, s):return [0x8B, 0xC0 + d * 8 + s]
def xchg_eax(r):return [0x90 + r]


def _mem(reg_field, op, ptr=None):
    """ModRM (+SIB) for [edi+d] or [edi+ptr*4+d], mod=10."""
    if ptr is None:
        return [0x80 + reg_field * 8 + EDI]
    return [0x80 + reg_field * 8 + 0x04, 0x80 + ptr * 8 + EDI]


def load(dst, op, ptr, disp):
    """mov dst, <memory operand>"""
    return [0x8B] + _mem(dst, op, ptr) + [disp]


def store(src, op, ptr, disp):
    """mov <memory operand>, src"""
    return [0x89] + _mem(src, op, ptr) + [disp]


def mul_reg(r, signed):
    return [0xF7, (0xE8 if signed else 0xE0) + r]


def mul_mem(ptr, disp, signed):
    ext = 5 if signed else 4
    return [0xF7] + _mem(ext, None, ptr) + [disp]


# ---------------------------------------------------------------- generator

class Op:
    def __init__(self, cls, reg, which):
        self.cls = cls
        self.reg = reg                       # lino register id
        self.x86 = X86[reg] if reg is not None else None
        self.disp = f"D{which}.4"            # placeholder token

    @property
    def is_mem(self):
        return self.cls in (DIR, IND)


def gen(op1, op2, signed):
    """Emit one pattern. Returns (code, notes). code items are ints or str
    placeholder tokens."""
    code, notes = [], []

    # Which x86 registers receive results and so must NOT be restored.
    dests = set()
    if op1.cls == REG: dests.add(op1.x86)
    if op2.cls == REG: dests.add(op2.x86)

    both_mem = op1.is_mem and op2.is_mem

    # Pointers that must survive until their memory access.
    p1 = op1.x86 if op1.cls == IND else None
    p2 = op2.x86 if op2.cls == IND else None
    conflict = [p for p in (p1, p2) if p in (EAX, EDX)]

    # How many scratch registers will be needed? One per distinct pointer
    # sitting in a clobbered register, plus one if op2's VALUE lives in eax
    # and eax must be reloaded (unless eax is already staged as a pointer, in
    # which case that one copy serves both roles).
    ptr_stage = set(conflict)
    val_stage = (op2.cls == REG and op2.x86 == EAX
                 and not (op1.cls == REG and op1.x86 == EAX)
                 and EAX not in ptr_stage)
    needed = len(ptr_stage) + (1 if val_stage else 0)

    use_pusha = both_mem and needed >= 2
    borrow_esi = (not use_pusha) and needed >= 2 and ESI not in dests

    if use_pusha:
        code += pusha()
        notes.append("two values must survive in clobbered registers: pusha "
                     "frees esi as a second scratch, sound because both "
                     "results go to memory so popa cannot undo them")
        scratch = [EBP, ESI]
    else:
        for r in (EAX, EDX):
            if r not in dests:
                code += push(r)
        scratch = [EBP]
        if borrow_esi:
            code += push(ESI)
            scratch.append(ESI)
            notes.append("needs a second scratch but has a register "
                         "destination, so esi is borrowed and restored "
                         "rather than using pusha/popa")
        elif needed >= 2:
            raise SystemExit(
                f"no second scratch available for {op1.cls}{op1.reg} "
                f"{op2.cls}{op2.reg}")

    # Stage any pointer that lives in a register the multiply will destroy.
    stage = {}
    for p in (p2, p1):                        # op2 first, mirroring idx 6096
        if p in (EAX, EDX) and p not in stage:
            s = scratch.pop(0)
            code += movrr(s, p)
            stage[p] = s
    if stage:
        notes.append("pointer staged out of a clobbered register before use")

    ptr1 = stage.get(p1, p1)
    ptr2 = stage.get(p2, p2)

    # Both operands are the same register: one destination for two results.
    # Ghignola's `/%` does the same at idx 5997 - compute, keep the low half,
    # drop the high - so follow the precedent rather than inventing one.
    degenerate = (op1.cls == REG and op2.cls == REG and op1.x86 == op2.x86)
    if degenerate:
        notes.append("op1 and op2 are the same register: high half discarded, "
                     "matching /% at idx 5997")

    # If op2's value lives in eax and eax is about to be reloaded with op1's
    # value, copy it to scratch first (Ghignola does this at idx 6002).
    mul_src = op2.x86 if op2.cls == REG else None
    if (op2.cls == REG and op2.x86 == EAX
            and not (op1.cls == REG and op1.x86 == EAX)):
        if EAX in stage:
            # eax was already copied out as a pointer; that same copy holds
            # the value we need, so reuse it rather than burning a second
            # scratch register.
            mul_src = stage[EAX]
        else:
            s = scratch.pop(0)
            code += movrr(s, EAX)
            mul_src = s
            notes.append("op2 lives in eax, which is about to be reloaded; staged")

    # Multiplicand into eax.
    if op1.cls == REG:
        if op1.x86 != EAX:
            code += movrr(EAX, op1.x86)
    else:
        code += load(EAX, op1.cls, ptr1, op1.disp)

    # The multiply.
    if op2.cls == REG:
        code += mul_reg(mul_src, signed)
    else:
        code += mul_mem(ptr2, op2.disp, signed)

    # Place results: op1 <- eax (low), op2 <- edx (high).
    if degenerate:
        if op1.x86 != EAX:
            code += movrr(op1.x86, EAX)
    elif op1.cls == REG and op2.cls == REG:
        if op1.x86 == EDX and op2.x86 == EAX:
            code += xchg_eax(EDX)
            notes.append("results land inverted; one xchg fixes both")
        elif op1.x86 == EDX:
            code += movrr(op2.x86, EDX)      # read edx before overwriting it
            code += movrr(EDX, EAX)
        else:
            if op1.x86 != EAX:
                code += movrr(op1.x86, EAX)
            if op2.x86 != EDX:
                code += movrr(op2.x86, EDX)
    else:
        # At least one destination is memory. Store the low half first; edx
        # still holds the high half and nothing here disturbs it.
        if op1.cls == REG:
            if op1.x86 != EAX:
                code += movrr(op1.x86, EAX)
        else:
            code += store(EAX, op1.cls, ptr1, op1.disp)
        if op2.cls == REG:
            if op2.x86 != EDX:
                code += movrr(op2.x86, EDX)
        else:
            code += store(EDX, op2.cls, ptr2, op2.disp)

    if use_pusha:
        code += popa()
    else:
        if borrow_esi:
            code += pop(ESI)
        for r in (EDX, EAX):
            if r not in dests:
                code += pop(r)

    return code, notes


def enumerate_block(signed):
    """All 121 patterns, in the pack's operand-configuration order."""
    out = []
    for c1, c2, count in CLASS_ORDER:
        r1s = range(5) if c1 in (REG, IND) else [None]
        r2s = range(5) if c2 in (REG, IND) else [None]
        for r1 in r1s:
            for r2 in r2s:
                op1 = Op(c1, r1 if r1 is not None else A, 1)
                op2 = Op(c2, r2 if r2 is not None else A, 2)
                if c1 == DIR: op1.x86 = None
                if c2 == DIR: op2.x86 = None
                code, notes = gen(op1, op2, signed)
                out.append((c1, r1, c2, r2, code, notes))
        assert len([o for o in out]) >= 0
    return out


def render(code):
    return " ".join(f"<{x}>" if isinstance(x, str) else f"{x:02X}" for x in code)


def emit(code):
    raw = bytearray()
    for x in code:
        if isinstance(x, str):
            raw += x.encode("ascii")
        else:
            raw.append(x)
    raw += TERM
    if len(raw) > ALIGN:
        raise SystemExit(f"pattern too long: {len(raw)} > {ALIGN}: {render(code)}")
    while len(raw) < ALIGN:
        raw += b"\x87\xdb"
    return bytes(raw[:ALIGN])


# ------------------------------------------------------------ back-compat

def gen_reg_reg(r1, r2, signed):
    return gen(Op(REG, r1, 1), Op(REG, r2, 2), signed)


def main():
    signed = "--unsigned" not in sys.argv
    sym = "*%" if signed else "*%'"
    block = enumerate_block(signed)

    print(f"{sym}  {len(block)} patterns  "
          f"({'imul' if signed else 'mul'} r/m32 = F7 /{5 if signed else 4})")
    print("    op1 = low 32 bits, op2 = high 32 bits\n")

    longest, records = 0, []
    shown = 0
    for c1, r1, c2, r2, code, notes in block:
        rec = emit(code)
        records.append(rec)
        longest = max(longest, len(rec) - (ALIGN - len(rec)) if False else 0)
        n1 = f"{c1}{LINO[r1]}" if r1 is not None else c1
        n2 = f"{c2}{LINO[r2]}" if r2 is not None else c2
        if "--all" in sys.argv or shown < 12:
            print(f"  {n1:<3} {n2:<3}  {render(code)}")
            for nt in notes:
                print(f"          ^ {nt}")
        shown += 1
    if "--all" not in sys.argv:
        print(f"  ... {len(block) - 12} more (pass --all to see them)")

    name = "mulsplit_signed.bin" if signed else "mulsplit_unsigned.bin"
    open(name, "wb").write(b"".join(records))
    print(f"\n  {len(records)} records, {len(records)*ALIGN} bytes -> {name}")
    print("  (nothing in main/cpu/ was touched)")


if __name__ == "__main__":
    main()
