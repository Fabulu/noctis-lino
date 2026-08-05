#!/usr/bin/env python
"""
ba_w2.py -- WAVE 2 decoder, ROUTE 1 (Implementer 1).

    capstone, TOP-DOWN from the unique Borland-LCG multiplier bytes 35 4E.

Route (fixed by the architect's plan; the route is part of the evidence):

  1. Locate the UNIQUE `35 4E` in the image -> rand() entry, by decoding
     BACKWARDS over the register loads that feed the 32-bit multiply.
     If `35 4E` is not unique, everything downstream is abandoned and the
     decoder reports LOCATION_FAILED.  It never falls back on a remembered
     offset.
  2. Find rand's callers by resolving EVERY `9A off16 seg16` through the MZ
     relocation table, plus every `[90] 0E E8 rel16` with the target computed
     MODULO 2**16 inside the segment frame (capstone's own branch target is
     deliberately NOT used -- in 16-bit mode it truncates the address and
     silently mislocates wrap-encoded calls).  Assert exactly one caller ->
     that caller's prologue is `random`.
  3. Find `random`'s callers the same way -> the census.
  4. `zrandom` = the unique member of random's caller set whose enclosing
     function (a) is <= 64 bytes, (b) contains exactly two calls to random,
     (c) ends `fild word [bp-2] ... retf`.  Its dataflow is then reported:
     which draw is spilled, which stays live, and which reaches the minuend.
  5. FP classification: BACKWARD decode from each call site over Borland's
     NOP pad; classify by whether the instruction feeding the argument push
     is a call to __ftol.
  6. __ftol is located as the callee of those calls -- NOT by its address.
     It is confirmed by shape (fnstcw / or / fistp), never by offset.

Output: ONE JSON object on stdout, nothing else, exit 0.
On failure to locate: {"status": "LOCATION_FAILED", "failed_stage": ...}.
"""

import argparse
import collections
import datetime
import hashlib
import json
import struct
import sys

try:
    import capstone
except ImportError:                                   # pragma: no cover
    sys.stderr.write("capstone is required\n")
    raise

DECODER_ID = "ba"
ROUTE = "capstone/top-down-from-354E-anchor"


class LocationFailure(Exception):
    def __init__(self, stage, detail=""):
        Exception.__init__(self, "%s: %s" % (stage, detail))
        self.stage = stage
        self.detail = detail


# ---------------------------------------------------------------------------
# capstone wrapper that counts every instruction it decodes
# ---------------------------------------------------------------------------
class Dis(object):
    def __init__(self):
        self.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
        self.md.detail = True
        self.count = 0

    def one(self, data, off):
        """Decode exactly one instruction at file offset `off`."""
        if off < 0 or off >= len(data):
            return None
        g = list(self.md.disasm(data[off:off + 16], off, count=1))
        if not g:
            return None
        self.count += 1
        return g[0]

    def prev(self, data, boundary, maxctx=24):
        """Instruction that ENDS exactly at `boundary`.

        Backward decoding is ambiguous on x86, so we take the answer produced
        by the LONGEST self-consistent chain that lands exactly on `boundary`.
        """
        for ctx in range(maxctx, 0, -1):
            a = boundary - ctx
            if a < 0:
                continue
            last, ok = None, True
            while a < boundary:
                ins = self.one(data, a)
                if ins is None or a + ins.size > boundary:
                    ok = False
                    break
                last = ins
                a += ins.size
            if ok and last is not None:
                return last
        return None


def txt(ins):
    return "%d  %-22s %s %s" % (ins.address, ins.bytes.hex(" "), ins.mnemonic, ins.op_str)


def body_text(insns):
    return "\n".join(txt(i) for i in insns)


# ---------------------------------------------------------------------------
# MZ layout
# ---------------------------------------------------------------------------
class Image(object):
    def __init__(self, path):
        self.path = path
        self.data = open(path, "rb").read()
        d = self.data
        if d[:2] not in (b"MZ", b"ZM"):
            raise LocationFailure("mz_header", "not an MZ image")
        self.crlc = struct.unpack_from("<H", d, 6)[0]
        self.header_len = struct.unpack_from("<H", d, 8)[0] * 16
        self.e_ip = struct.unpack_from("<H", d, 20)[0]
        self.e_cs = struct.unpack_from("<H", d, 22)[0]
        self.lfarlc = struct.unpack_from("<H", d, 24)[0]
        self.ovno = struct.unpack_from("<H", d, 26)[0]
        self.reloc_targets = set()
        for i in range(self.crlc):
            off, seg = struct.unpack_from("<HH", d, self.lfarlc + 4 * i)
            self.reloc_targets.add(self.header_len + seg * 16 + off)
        self.entry_file = self.header_len + self.e_cs * 16 + self.e_ip
        self.sha256 = hashlib.sha256(d).hexdigest()

    def lin(self, seg, off):
        return self.header_len + seg * 16 + off


def find_dgroup(img, dis):
    """DGROUP from the C0 startup: the immediate that is loaded into a
    register and then moved into DS at the program entry point.  The
    immediate carries a relocation entry, which is what proves it is a
    segment value and not a constant."""
    d = img.data
    off = img.entry_file
    pend = {}
    for _ in range(40):
        ins = dis.one(d, off)
        if ins is None:
            break
        m, ops = ins.mnemonic, ins.operands
        if m == "mov" and len(ops) == 2 and ops[0].type == capstone.x86.X86_OP_REG \
                and ops[1].type == capstone.x86.X86_OP_IMM:
            immfile = ins.address + (ins.size - 2)
            pend[ins.reg_name(ops[0].reg)] = (ops[1].imm & 0xFFFF, immfile)
        if m == "mov" and len(ops) == 2 and ops[0].type == capstone.x86.X86_OP_REG \
                and ops[1].type == capstone.x86.X86_OP_REG \
                and ins.reg_name(ops[0].reg) == "ds":
            src = ins.reg_name(ops[1].reg)
            if src in pend:
                val, immfile = pend[src]
                if immfile not in img.reloc_targets:
                    raise LocationFailure("dgroup", "DS immediate at %d carries no relocation" % immfile)
                return img.header_len + val * 16
        off += ins.size
    raise LocationFailure("dgroup", "no `mov ds,<reg>` found in the startup prologue")


# ---------------------------------------------------------------------------
# STAGE 1 -- the anchor
# ---------------------------------------------------------------------------
ANCHOR = b"\x35\x4e"          # low half of Borland's 0x015A4E35 multiplier


def count_anchor(data):
    n, i = 0, 0
    while True:
        i = data.find(ANCHOR, i)
        if i < 0:
            break
        n += 1
        i += 1
    return n


def find_rand_entry(img, dis):
    d = img.data
    n = count_anchor(d)
    if n != 1:
        raise LocationFailure("anchor_354E", "expected exactly 1 occurrence, found %d" % n)
    a = d.find(ANCHOR)
    # the anchor bytes are the imm16 of `mov ax,4E35`; the opcode precedes it
    if d[a - 1] != 0xB8:
        raise LocationFailure("anchor_354E", "byte before the anchor is %02x, not B8 (mov ax,imm16)" % d[a - 1])
    mul_lo = a - 1
    ins = dis.one(d, mul_lo)
    if ins is None or ins.mnemonic != "mov" or (ins.operands[1].imm & 0xFFFF) != 0x4E35:
        raise LocationFailure("anchor_354E", "anchor does not decode as `mov ax,0x4e35`")

    # walk backwards over the loads that feed the 32-bit multiply, stopping at
    # the previous function's terminator (retf / ret / int3 / alignment nop).
    TERM = (0xCB, 0xC3, 0xCA, 0xC2, 0xCC)
    cur = mul_lo
    for _ in range(8):
        prev = dis.prev(d, cur)
        if prev is None:
            break
        if prev.mnemonic != "mov":
            break
        cur = prev.address
        if d[cur - 1] in TERM:
            break
    else:
        raise LocationFailure("rand_entry", "backward walk did not terminate")
    if d[cur - 1] not in TERM:
        raise LocationFailure("rand_entry", "byte before candidate entry %d is %02x, not a function terminator"
                              % (cur, d[cur - 1]))
    return cur


def verify_rand(img, dis, entry):
    """Confirm the located body really is Borland's LCG."""
    insns = disasm_function(img, dis, entry, limit=96)
    seen = {"mul_lo": False, "mul_hi": False, "inc": False, "adc": False}
    seedrefs = []
    for i in insns:
        if i.mnemonic == "mov" and len(i.operands) == 2 and i.operands[1].type == capstone.x86.X86_OP_IMM:
            v = i.operands[1].imm & 0xFFFF
            if v == 0x4E35:
                seen["mul_lo"] = True
            if v == 0x015A:
                seen["mul_hi"] = True
        if i.mnemonic == "add" and len(i.operands) == 2 and i.operands[1].type == capstone.x86.X86_OP_IMM \
                and (i.operands[1].imm & 0xFFFF) == 1:
            seen["inc"] = True
        if i.mnemonic == "adc":
            seen["adc"] = True
        for op in i.operands:
            if op.type == capstone.x86.X86_OP_MEM and op.mem.base == 0 and op.mem.index == 0:
                seedrefs.append(op.mem.disp & 0xFFFF)
    missing = [k for k, v in seen.items() if not v]
    if missing:
        raise LocationFailure("rand_verify", "LCG body missing %s" % ",".join(missing))
    seed = sorted(set(seedrefs))
    if len(seed) < 2:
        raise LocationFailure("rand_verify", "seed is not a pair of 16-bit words: %r" % seed)
    return insns, seed


def find_srand(img, dis, rand_entry):
    """The function that ends immediately before rand and stores the seed."""
    d = img.data
    best = None
    for p in range(rand_entry - 80, rand_entry):
        if p < 0:
            continue
        if not (d[p:p + 3] == b"\x55\x8b\xec" or (d[p] == 0xC8 and d[p + 3] == 0x00)):
            continue
        a, ok = p, True
        while a < rand_entry:
            ins = dis.one(d, a)
            if ins is None or a + ins.size > rand_entry:
                ok = False
                break
            a += ins.size
        if ok and d[rand_entry - 1] in (0xCB, 0xC3):
            best = p if best is None else min(best, p)
    if best is None:
        raise LocationFailure("srand_entry", "no prologue chains to rand's entry")
    return best


# ---------------------------------------------------------------------------
# STAGE 2/3 -- the census
# ---------------------------------------------------------------------------
def census(img, target):
    """Every call in the image whose callee is `target`.

    far    : 9A off16 seg16, resolved through the load-time segment arithmetic.
    pushcs : [90] 0E E8 rel16 -- Borland's same-segment far call.  The target
             is next_ip + rel16 REDUCED MODULO 2**16 INSIDE THE SEGMENT FRAME,
             which for a file offset means BOTH `next+rel16` and
             `next+rel16-65536` are legal renderings of the same encoding.
             A decoder that only does signed rel16 misses the wrap-encoded
             calls (e.g. flandom's); one that only does unsigned misses every
             backward call (e.g. all ten into zrandom).
    """
    d = img.data
    far, pushcs = [], []
    i = 0
    while True:
        i = d.find(b"\x9a", i)
        if i < 0 or i + 5 > len(d):
            break
        off, seg = struct.unpack_from("<HH", d, i + 1)
        if img.lin(seg, off) == target:
            far.append(i)
        i += 1
    i = 0
    while True:
        i = d.find(b"\x0e\xe8", i)
        if i < 0 or i + 4 > len(d):
            break
        rel = struct.unpack_from("<H", d, i + 2)[0]
        nxt = i + 4
        if nxt + rel == target or nxt + rel - 65536 == target:
            pushcs.append(i)
        i += 1
    return {"far": len(far), "pushcs": len(pushcs), "total": len(far) + len(pushcs),
            "sites": sorted(far + pushcs), "_far": far, "_pushcs": pushcs}


def insn_call_target(img, ins):
    """Callee of a DECODED call instruction, or None if it is not a call.

    Anchored on the instruction's own first byte, so Borland's `push cs`
    (0x0E) that precedes a same-segment far call is NOT itself mistaken for a
    call -- doing so double-counts every such call inside a function body and
    makes `flandom` look like it draws twice.
    """
    d = img.data
    a = ins.address
    if d[a] == 0x9A and a + 5 <= len(d):
        o, sg = struct.unpack_from("<HH", d, a + 1)
        return img.lin(sg, o)
    if d[a] == 0xE8 and ins.mnemonic in ("call", "lcall") and a + 3 <= len(d):
        return a + 3 + struct.unpack_from("<H", d, a + 1)[0]
    return None


def insn_call_site(img, ins):
    """The call's offset in the CENSUS convention: the `push cs` byte when
    Borland emitted the same-segment far-call idiom, else the call itself."""
    a = ins.address
    if img.data[a] == 0xE8 and a >= 1 and img.data[a - 1] == 0x0E:
        return a - 1
    return a


def insn_calls(img, ins, target):
    t = insn_call_target(img, ins)
    return t is not None and (t == target or t - 65536 == target)


def is_call_to(img, off, target):
    """True iff the instruction at `off` is a call whose callee is `target`.
    Both renderings of a same-segment rel16 (with and without the modulo-2**16
    wrap) are accepted, because a file offset cannot distinguish them."""
    t = call_target(img, off)
    return t is not None and (t == target or t - 65536 == target)


def call_target(img, off):
    """Resolve the callee of the call instruction whose FIRST byte is at `off`,
    or None if `off` is not a call.  Never uses capstone's computed target."""
    d = img.data
    if off < 0 or off + 3 > len(d):
        return None
    if d[off] == 0x9A:
        o, s = struct.unpack_from("<HH", d, off + 1)
        return img.lin(s, o)
    if d[off] == 0x0E and d[off + 1] == 0xE8:
        rel = struct.unpack_from("<H", d, off + 2)[0]
        return off + 4 + rel          # caller may also mean -65536; resolved by the caller
    if d[off] == 0xE8:
        rel = struct.unpack_from("<H", d, off + 1)[0]
        return off + 3 + rel
    return None


# ---------------------------------------------------------------------------
# function bodies
# ---------------------------------------------------------------------------
def disasm_function(img, dis, entry, limit=1024):
    """Linear sweep from `entry` to the terminating retf.  Intra-function jump
    targets are computed by hand (signed rel8/rel16) so that a return in the
    middle of a function is not mistaken for the end."""
    d = img.data
    insns, addr, maxtgt = [], entry, entry
    while addr < entry + limit:
        ins = dis.one(d, addr)
        if ins is None:
            break
        insns.append(ins)
        op = d[addr]
        if op == 0xEB or 0x70 <= op <= 0x7F:
            t = addr + 2 + struct.unpack_from("<b", d, addr + 1)[0]
            maxtgt = max(maxtgt, t)
        elif op == 0xE9:
            t = addr + 3 + struct.unpack_from("<h", d, addr + 1)[0]
            maxtgt = max(maxtgt, t)
        elif op == 0x0F and 0x80 <= d[addr + 1] <= 0x8F:
            t = addr + 4 + struct.unpack_from("<h", d, addr + 2)[0]
            maxtgt = max(maxtgt, t)
        addr += ins.size
        if ins.mnemonic in ("retf", "ret", "lret") and addr > maxtgt:
            break
    return insns


PROLOGUES = (b"\x55\x8b\xec",)


def enclosing_function(img, dis, site, back=64):
    """Nearest prologue at most `back` bytes before `site` whose linear
    disassembly lands exactly on `site`."""
    d = img.data
    for p in range(site - 1, max(0, site - back) - 1, -1):
        is_pro = d[p:p + 3] in PROLOGUES or (d[p] == 0xC8 and p + 4 <= len(d) and d[p + 3] == 0x00)
        if not is_pro:
            continue
        a, ok = p, False
        while a < site:
            ins = dis.one(d, a)
            if ins is None:
                break
            if a == site:
                break
            if a + ins.size > site:
                break
            a += ins.size
            if a == site:
                ok = True
                break
        if ok:
            return p
    return None


# ---------------------------------------------------------------------------
# STAGE 4 -- zrandom and UNKNOWN 2
# ---------------------------------------------------------------------------
def find_zrandom(img, dis, random_entry, random_sites):
    """The unique caller of random that is a <=64-byte function containing
    exactly two calls to random and returning through `fild word`."""
    d = img.data
    cands = {}
    for s in random_sites:
        e = enclosing_function(img, dis, s, back=64)
        if e is None or e in cands:
            continue
        insns = disasm_function(img, dis, e, limit=96)
        if not insns or insns[-1].mnemonic not in ("retf", "lret"):
            continue
        length = insns[-1].address + insns[-1].size - e
        if length > 64:
            continue
        ncalls = 0
        for i in insns:
            if insn_calls(img, i, random_entry):
                ncalls += 1
        if ncalls != 2:
            continue
        mn = [i.mnemonic for i in insns]
        if "fild" not in mn:
            continue
        cands[e] = (insns, length)
    if len(cands) != 1:
        raise LocationFailure("zrandom", "expected exactly 1 candidate, found %d: %r"
                              % (len(cands), sorted(cands)))
    e = list(cands)[0]
    return e, cands[e][0], cands[e][1]


def analyse_zrandom(img, dis, entry, insns, random_entry):
    """Symbolic execution of the 36-byte body: which draw reaches the minuend."""
    regs = {}
    stack = []
    ndraw = 0
    out = {"call_files": [], "spilled_draw": None, "live_draw": None}
    sub_seen = None
    for ins in insns:
        m, ops = ins.mnemonic, ins.operands
        if img.data[ins.address] == 0x0E and img.data[ins.address + 1] == 0xE8:
            # `push cs` belonging to Borland's same-segment far-call idiom: the
            # slot is consumed by the callee's RETF, so it is NOT a stack slot
            # the caller can pop.  Modelling it shifts every later pop by one.
            continue
        if insn_calls(img, ins, random_entry):
            ndraw += 1
            regs["ax"] = "draw%d" % ndraw
            out["call_files"].append(insn_call_site(img, ins))
            continue
        if m == "push" and ops and ops[0].type == capstone.x86.X86_OP_REG:
            r = ins.reg_name(ops[0].reg)
            v = regs.get(r)
            stack.append(v)
            if v is not None and out["spilled_draw"] is None:
                out["spilled_draw"] = v
            continue
        if m == "pop" and ops and ops[0].type == capstone.x86.X86_OP_REG:
            r = ins.reg_name(ops[0].reg)
            regs[r] = stack.pop() if stack else None
            continue
        if m in ("sub", "cmp") and len(ops) == 2 and ops[0].type == capstone.x86.X86_OP_REG \
                and ops[1].type == capstone.x86.X86_OP_REG and m == "sub":
            dst = ins.reg_name(ops[0].reg)
            src = ins.reg_name(ops[1].reg)
            sub_seen = {
                "op": m, "sub_file": ins.address, "sub_dst": dst, "sub_src": src,
                "minuend": regs.get(dst), "subtrahend": regs.get(src),
                "result_width_bits": ops[0].size * 8,
            }
            regs[dst] = "diff"
            continue
        if m == "mov" and len(ops) == 2 and ops[0].type == capstone.x86.X86_OP_MEM \
                and ops[1].type == capstone.x86.X86_OP_REG and sub_seen is not None \
                and out.get("stored_reg") is None:
            src = ins.reg_name(ops[1].reg)
            if regs.get(src) == "diff":
                out["stored_reg"] = src
                out["store_width_bits"] = ops[0].size * 8
                out["store_disp"] = ops[0].mem.disp
            continue
        if m in ("fild", "fld") and ops:
            out["return_load"] = "%s_%s" % (m, {1: "byte", 2: "word", 4: "dword",
                                                8: "qword", 10: "tword"}.get(ops[0].size, "?"))
            out["return_load_width_bits"] = ops[0].size * 8
            continue
    if sub_seen is None:
        raise LocationFailure("zrandom_dataflow", "no register/register subtraction in the body")
    if ndraw != 2:
        raise LocationFailure("zrandom_dataflow", "expected 2 draws, tracked %d" % ndraw)
    out.update(sub_seen)
    # the draw that was never spilled is the one that stayed live in ax
    other = {"draw1": "draw2", "draw2": "draw1"}
    out["live_draw"] = other.get(out["spilled_draw"])
    if out["minuend"] == "draw1":
        out["verdict"] = "LEFT_TO_RIGHT"
    elif out["minuend"] == "draw2":
        out["verdict"] = "RIGHT_TO_LEFT"
    else:
        out["verdict"] = "INDETERMINATE"
    out.setdefault("return_load", None)
    out.setdefault("stored_reg", None)
    return out


# ---------------------------------------------------------------------------
# STAGE 5/6 -- __ftol, the FP argument sites, and UNKNOWN 1
# ---------------------------------------------------------------------------
def arg_push(img, dis, site):
    """The instruction that pushes the last argument of the call at `site`,
    skipping Borland's 0x90 alignment pad, and the instruction before it."""
    b = site
    p = dis.prev(img.data, b)
    if p is not None and p.mnemonic == "nop":
        b = p.address
        p = dis.prev(img.data, b)
    if p is None or p.mnemonic != "push":
        return None, None
    before = dis.prev(img.data, p.address)
    return p, before


def looks_like_ftol(img, dis, entry):
    if entry is None or entry < 0 or entry >= len(img.data):
        return False
    insns = disasm_function(img, dis, entry, limit=128)
    mn = [i.mnemonic for i in insns]
    return "fnstcw" in mn and "fistp" in mn and "fldcw" in mn


def find_ftol(img, dis, sites):
    """__ftol is whichever callee sits immediately before the argument push at
    the float-argument call sites AND has the fnstcw/or/fldcw/fistp shape.
    Its address is never assumed."""
    hits = collections.Counter()
    for s in sites:
        push, before = arg_push(img, dis, s)
        if push is None or before is None:
            continue
        t = call_target(img, before.address)
        if t is None:
            continue
        for cand in (t, t - 65536):
            if 0 <= cand < len(img.data):
                hits[cand] += 1
    good = [c for c in hits if looks_like_ftol(img, dis, c)]
    if len(good) != 1:
        raise LocationFailure("ftol", "expected exactly 1 float->int helper among %d call "
                                      "predecessors, found %d: %r" % (len(hits), len(good), good))
    return good[0]


RC = {0: "NEAREST", 1: "DOWN", 2: "UP", 3: "CHOP"}


def analyse_ftol(img, dis, entry):
    insns = disasm_function(img, dis, entry, limit=128)
    out = {"cw_or_immediate": None, "rounding": None,
           "store_width_bits": None, "return_width_bits": None}
    loads = []
    for ins in insns:
        m, ops = ins.mnemonic, ins.operands
        if m in ("or", "and") and len(ops) == 2 and ops[1].type == capstone.x86.X86_OP_IMM \
                and out["cw_or_immediate"] is None:
            imm = ops[1].imm & 0xFF
            out["cw_or_immediate"] = imm
            # the control word's RC field is bits 10-11 of the word == bits 2-3
            # of the high byte, which is the byte this instruction ORs.
            out["rounding"] = RC[(imm >> 2) & 3]
        if m == "fistp" and ops:
            out["store_width_bits"] = ops[0].size * 8
        if m == "mov" and len(ops) == 2 and ops[0].type == capstone.x86.X86_OP_REG \
                and ops[1].type == capstone.x86.X86_OP_MEM:
            r = ins.reg_name(ops[0].reg)
            if r in ("ax", "dx"):
                loads.append(r)
    out["return_width_bits"] = 16 * len(set(loads) & {"ax", "dx"})
    if out["cw_or_immediate"] is None or out["store_width_bits"] is None:
        raise LocationFailure("ftol_analyse", "body at %d is not the expected chop helper" % entry)
    return out, insns


NARROW = {"ax": "LOW16_OF_FTOL", "dx": "HIGH16_OF_FTOL"}

X87_INT_STORE = ("fistp", "fist", "fbstp")


def mem_key(op):
    return (op.mem.base, op.mem.index, op.mem.scale, op.mem.disp, op.size)


def stores_to(ins, key):
    """True iff `ins` writes the memory operand identified by `key`."""
    ops = ins.operands
    if not ops or ops[0].type != capstone.x86.X86_OP_MEM:
        return False
    if mem_key(ops[0]) != key:
        return False
    return ins.mnemonic in X87_INT_STORE or ins.mnemonic in ("mov", "fstp", "fst",
                                                             "pop", "add", "sub",
                                                             "or", "and", "xor", "inc", "dec")


def fp_bypasses_ftol(img, dis, push, depth=16):
    """Does the pushed argument come from an x87 integer store rather than
    from the chop helper?

    x87 cannot write a general register, so a `push <reg>` argument can only
    carry a float through a helper call -- which the caller has already tested
    for.  The only other route is `fistp <slot>` followed by `push <slot>`, so
    that is what this looks for: the FIRST writer of the pushed slot, walking
    backwards.  Mere ADJACENCY to x87 code proves nothing -- Borland routinely
    schedules an unrelated 80-bit `fstp xword [bp-N]` spill immediately before
    a call whose argument is a plain `push 0x64`.
    """
    if not push.operands or push.operands[0].type != capstone.x86.X86_OP_MEM:
        return False
    key = mem_key(push.operands[0])
    a = push.address
    for _ in range(depth):
        q = dis.prev(img.data, a)
        if q is None:
            return False
        a = q.address
        if stores_to(q, key):
            return q.mnemonic in X87_INT_STORE
    return False


def classify_sites(img, dis, sites, callee_name, ftol_entry):
    fp, nonftol = [], []
    for s in sites:
        push, before = arg_push(img, dis, s)
        if push is None or before is None:
            continue
        t = call_target(img, before.address)
        is_ftol = is_call_to(img, before.address, ftol_entry)
        if is_ftol:
            reg = push.reg_name(push.operands[0].reg) if push.operands[0].type == capstone.x86.X86_OP_REG else "?"
            fp.append({"call": s, "callee": callee_name, "ftol": before.address,
                       "push": push.address, "push_reg": reg,
                       "narrowing": NARROW.get(reg, "OTHER_REG_AFTER_FTOL")})
        elif fp_bypasses_ftol(img, dis, push):
            # a float reaching the argument WITHOUT the chop helper: would mean
            # a second, unmodelled narrowing path into random()
            nonftol.append(s)
    return fp, nonftol


def analyse_random(img, dis, entry, rand_entry):
    insns = disasm_function(img, dis, entry, limit=128)
    # `random` is a compiled out-of-line function, not Borland's textual
    # macro: it has its own prologue, its own RETF, and it is the sole caller
    # of rand() in the image.  A macro would inline rand()'s call at every use
    # site, giving rand hundreds of callers instead of one.
    out = {"random_is_macro": False, "random_param_width_bits": None,
           "random_param_signextended": None, "random_divisor": None,
           "random_div_is_signed": None, "random_mul_width_bits": None}
    imms = {}
    calls_rand = 0
    for ins in insns:
        m, ops = ins.mnemonic, ins.operands
        if insn_calls(img, ins, rand_entry):
            calls_rand += 1
        if m in ("movsx", "movzx") and len(ops) == 2 and ops[1].type == capstone.x86.X86_OP_MEM \
                and ops[1].mem.base != 0 and out["random_param_width_bits"] is None:
            out["random_param_width_bits"] = ops[1].size * 8
            out["random_param_signextended"] = (m == "movsx")
        if m in ("imul", "mul") and len(ops) == 2 and out["random_mul_width_bits"] is None:
            out["random_mul_width_bits"] = ops[0].size * 8
        if m == "mov" and len(ops) == 2 and ops[0].type == capstone.x86.X86_OP_REG \
                and ops[1].type == capstone.x86.X86_OP_IMM:
            imms[ins.reg_name(ops[0].reg)] = ops[1].imm
        if m in ("idiv", "div") and ops:
            out["random_div_is_signed"] = (m == "idiv")
            if ops[0].type == capstone.x86.X86_OP_REG:
                out["random_divisor"] = imms.get(ins.reg_name(ops[0].reg))
            elif ops[0].type == capstone.x86.X86_OP_IMM:
                out["random_divisor"] = ops[0].imm
    if calls_rand != 1:
        raise LocationFailure("random_analyse", "random's body calls rand %d times" % calls_rand)
    if insns[-1].mnemonic not in ("retf", "lret"):
        raise LocationFailure("random_analyse", "random's body does not end in RETF -- "
                                                "it is not an out-of-line function")
    for k, v in out.items():
        if v is None:
            raise LocationFailure("random_analyse", "could not determine %s" % k)
    length = insns[-1].address + insns[-1].size - entry
    return out, insns, length


# ---------------------------------------------------------------------------
def run(binary, unused_dl, unused_st):
    dis = Dis()
    started = datetime.datetime.now(datetime.timezone.utc).replace(
        microsecond=0, tzinfo=None).isoformat() + "Z"
    verdict = {
        "decoder": {"id": DECODER_ID, "engine": "capstone",
                    "engine_version": str(capstone.__version__),
                    "route": ROUTE, "insns_decoded": 0, "run_utc": started},
        "evidence": {},
    }
    img = None
    anchor_n = None
    try:
        img = Image(binary)
        verdict["binary"] = {"sha256": img.sha256, "size": len(img.data)}
        anchor_n = count_anchor(img.data)

        rand_entry = find_rand_entry(img, dis)
        rand_insns, seed_words = verify_rand(img, dis, rand_entry)
        srand_entry = find_srand(img, dis, rand_entry)
        dgroup = find_dgroup(img, dis)

        c_rand = census(img, rand_entry)
        if c_rand["total"] != 1:
            raise LocationFailure("random_entry",
                                  "rand must have exactly one caller, found %d at %r"
                                  % (c_rand["total"], c_rand["sites"]))
        callsite = c_rand["sites"][0]
        random_entry = enclosing_function(img, dis, callsite, back=32)
        if random_entry is None:
            raise LocationFailure("random_entry", "no prologue precedes rand's only call site %d" % callsite)
        r_info, random_insns, random_len = analyse_random(img, dis, random_entry, rand_entry)

        c_random = census(img, random_entry)
        if not c_random["total"]:
            raise LocationFailure("random_census", "random has no callers")

        z_entry, z_insns, z_len = find_zrandom(img, dis, random_entry, c_random["sites"])
        c_zrandom = census(img, z_entry)
        u2 = analyse_zrandom(img, dis, z_entry, z_insns, random_entry)

        ftol_entry = find_ftol(img, dis, c_random["sites"] + c_zrandom["sites"])
        f_info, ftol_insns = analyse_ftol(img, dis, ftol_entry)
        c_ftol = census(img, ftol_entry)

        fp_r, nf_r = classify_sites(img, dis, c_random["sites"], "random", ftol_entry)
        fp_z, nf_z = classify_sites(img, dis, c_zrandom["sites"], "zrandom", ftol_entry)
        fp = sorted(fp_r + fp_z, key=lambda e: e["call"])

        # self-checks: byte-pattern census validation
        far_reloc = sum(1 for s in c_random["_far"] if (s + 3) in img.reloc_targets)
        pad = sum(1 for s in c_random["_pushcs"] if img.data[s - 1] == 0x90)

        u1_verdict = ("NARROWED_AT_CALL_BOUNDARY"
                      if r_info["random_param_width_bits"] == 16 and not nf_r and not nf_z
                      else "FP_SURVIVES_INTO_RAND")

        body = lambda a, n: hashlib.sha256(img.data[a:a + n]).hexdigest()
        verdict.update({
            "status": "OK",
            "layout": {"header_len": img.header_len, "dgroup_file": dgroup,
                       "entry_file": img.entry_file, "reloc_count": img.crlc,
                       "overlay_no": img.ovno},
            "anchors": {
                "rand_entry": rand_entry, "srand_entry": srand_entry,
                "random_entry": random_entry, "zrandom_entry": z_entry,
                "zrandom_len": z_len, "ftol_entry": ftol_entry,
                "random_len": random_len,
                "zrandom_body_sha256": body(z_entry, z_len),
                "random_body_sha256": body(random_entry, random_len),
                "rand_seed_disps": seed_words,
            },
            "census": {
                "rand": {k: c_rand[k] for k in ("far", "pushcs", "total", "sites")},
                "random": {k: c_random[k] for k in ("far", "pushcs", "total", "sites")},
                "zrandom": {k: c_zrandom[k] for k in ("far", "pushcs", "total", "sites")},
                "ftol": {k: c_ftol[k] for k in ("far", "pushcs", "total")},
            },
            "unknown1": dict(r_info, verdict=u1_verdict, ftol=f_info, fp_sites=fp,
                             fp_sites_total=len(fp),
                             nonftol_fp_arg_sites=sorted(nf_r + nf_z)),
            "unknown2": {
                "verdict": u2["verdict"], "minuend": u2["minuend"],
                "spilled_draw": u2["spilled_draw"], "live_draw": u2["live_draw"],
                "sub_dst": u2["sub_dst"], "sub_src": u2["sub_src"],
                "sub_file": u2["sub_file"], "op": u2["op"],
                "stored_reg": u2["stored_reg"],
                "result_width_bits": u2.get("store_width_bits") or u2["result_width_bits"],
                "return_load": u2["return_load"], "call_files": u2["call_files"],
            },
            "selfcheck": {
                "anchor_354e_count": anchor_n,
                "far_sites_with_reloc": far_reloc,
                "far_sites_total": c_random["far"],
                "pushcs_sites_with_nop_pad": pad,
                "pushcs_sites_total": c_random["pushcs"],
            },
        })
        verdict["evidence"] = {
            "rand_text": body_text(rand_insns),
            "random_text": body_text(random_insns),
            "zrandom_text": body_text(z_insns),
            "ftol_text": body_text(ftol_insns),
        }
    except LocationFailure as e:
        verdict["status"] = "LOCATION_FAILED"
        verdict["failed_stage"] = e.stage
        verdict["failure_detail"] = e.detail
        verdict["selfcheck"] = {"anchor_354e_count": anchor_n}
        if img is not None:
            verdict.setdefault("binary", {"sha256": img.sha256, "size": len(img.data)})
            verdict["layout"] = {"header_len": img.header_len, "entry_file": img.entry_file}
            diag = body_text(disasm_function(img, dis, img.entry_file, limit=64))
            verdict["evidence"] = {"rand_text": diag, "random_text": diag,
                                   "zrandom_text": diag, "ftol_text": diag}
    verdict["decoder"]["insns_decoded"] = dis.count
    return verdict


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--binary", required=True)
    ap.add_argument("--dl", default=None, help="unused by route 1 (symbol tables are route 2)")
    ap.add_argument("--st", default=None, help="unused by route 1")
    a = ap.parse_args(argv[1:])
    sys.stdout.write(json.dumps(run(a.binary, a.dl, a.st), sort_keys=True))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
