"""Wave 2, ROUTE C - the regression suite's own decoder of NOCTIS.EXE.

Neither implementer owns this file. It exists so that `test_wave2.py` never has
to take ba_w2.py's or bx_w2.py's word for anything: every number the two
delivered decoders report is recomputed here, from the bytes, by a third method
that shares no code with either of them.

Why a third route at all
------------------------
Wave 2's subject is a binary that will never change again. A test that only
re-reads it would pass forever whatever the decoders did - including doing
nothing and printing a remembered answer. The decoders are therefore the
subject, and grading a decoder needs an oracle that is not the decoder.

  ba_w2.py   capstone       top-down from the unique 35 4E LCG anchor
  bx_w2.py   ndisasm        Borland symbol names in DL/ST, transferred as
                            masked signatures
  w2spec.py  no disassembler at all

Route C in one line: **named-field byte templates, plus suffix-anchored
backward pattern matching.** There is no linear sweep and no third-party
disassembler. Function bodies are matched against templates in which the only
free fields are the things that genuinely vary (segment values, frame
displacements, DGROUP-relative data addresses), and every semantic answer is
read out of a captured field. Argument pushes are found by matching backwards
from the call site over the closed set of byte forms Borland can emit there.

Two things route C checks that neither delivered decoder does, both recorded
as blind spots by Wave 2's QA pass:

  * rand's RETURN path. `mov ax,[<high seed word>]; cwd; and ax,0x7FFF; retf`
    is what makes random()'s 0x8000 divisor correct. Mutating the mask, or
    returning the low seed word instead, is invisible to ba and bx.
  * FWAIT between an argument push and its call. 49 of the 385 call sites have
    a 0x9B there and both delivered decoders stop walking at it, so a float
    planted at one of those sites is invisible to them.

Output shape is the Wave 2 verdict contract (see w2v_verdict.py), so the same
mechanical diff can compare all three routes.
"""

import hashlib
import struct

# ---------------------------------------------------------------------------
# failure
# ---------------------------------------------------------------------------


class Located(Exception):
    """Raised the moment route C cannot honestly locate something.

    Route C never falls back on a remembered offset. Everything it reports is
    reached from the bytes of the file it was handed, or it reports nothing.
    """

    def __init__(self, stage, detail=""):
        Exception.__init__(self, "%s: %s" % (stage, detail))
        self.stage = stage
        self.detail = detail


# ---------------------------------------------------------------------------
# named-field byte templates
# ---------------------------------------------------------------------------
#   "8b 0e hi:2"    literal bytes, plus a 2-byte little-endian capture named hi
#   "e8 ?? ??"      two bytes of don't-care
# A name that appears twice must capture the same value both times, which is
# how `mov [seed_hi],dx` is tied to `mov cx,[seed_hi]` without naming either
# address.


def _parse(template):
    out = []
    for tok in template.split():
        if tok == "??":
            out.append(("skip", 1, None))
        elif ":" in tok:
            name, width = tok.split(":")
            out.append(("cap", int(width), name))
        else:
            out.append(("lit", 1, int(tok, 16)))
    return out


def match(data, at, template):
    """Match `template` at file offset `at`.

    Returns (fields, length). Raises Located on the first byte that disagrees,
    naming the offset - a template failure is a real finding, not a shrug.
    """
    items = _parse(template)
    fields, p = {}, at
    for kind, width, arg in items:
        if p + width > len(data):
            raise Located("template", "ran off the end of the image at %d" % p)
        if kind == "lit":
            if data[p] != arg:
                raise Located("template", "byte %d is %02x, template wants %02x "
                                          "(field so far: %r)" % (p, data[p], arg, fields))
        elif kind == "cap":
            v = int.from_bytes(data[p:p + width], "little")
            if arg in fields and fields[arg] != v:
                raise Located("template", "field %r is %d at %d but was %d earlier"
                              % (arg, v, p, fields[arg]))
            fields[arg] = v
        p += width
    return fields, p - at


def try_match(data, at, template):
    try:
        return match(data, at, template)
    except Located:
        return None, 0


# ---------------------------------------------------------------------------
# MZ layout
# ---------------------------------------------------------------------------
class Image(object):
    def __init__(self, path):
        self.path = path
        with open(path, "rb") as fh:
            self.data = fh.read()
        d = self.data
        if d[:2] not in (b"MZ", b"ZM"):
            raise Located("mz_header", "not an MZ image")
        self.nreloc = struct.unpack_from("<H", d, 6)[0]
        self.header_len = struct.unpack_from("<H", d, 8)[0] * 16
        self.e_ip = struct.unpack_from("<H", d, 20)[0]
        self.e_cs = struct.unpack_from("<H", d, 22)[0]
        self.reloff = struct.unpack_from("<H", d, 24)[0]
        self.entry_file = self.header_len + self.e_cs * 16 + self.e_ip
        self.reloc_targets = set()
        for i in range(self.nreloc):
            off, seg = struct.unpack_from("<HH", d, self.reloff + 4 * i)
            self.reloc_targets.add(self.header_len + seg * 16 + off)
        self.sha256 = hashlib.sha256(d).hexdigest()

    def lin(self, seg, off):
        return self.header_len + seg * 16 + off


def find_dgroup(img):
    """Borland's C0 startup opens `mov dx,DGROUP`. The immediate must carry a
    relocation entry - that is what proves it is a segment and not a constant."""
    f, _n = try_match(img.data, img.entry_file, "ba seg:2")
    if f is None:
        raise Located("dgroup", "startup at %d does not open with `mov dx,imm16`" % img.entry_file)
    if img.entry_file + 1 not in img.reloc_targets:
        raise Located("dgroup", "the DGROUP immediate at %d carries no relocation"
                      % (img.entry_file + 1))
    return img.header_len + f["seg"] * 16


# ---------------------------------------------------------------------------
# STAGE 1 - rand, from the unique multiplier, INCLUDING its return path
# ---------------------------------------------------------------------------
ANCHOR = b"\x35\x4e"

# seed_lo / seed_hi are the two 16-bit halves of Borland's long seed. They are
# never named by address: the template ties the loads to the stores.
RAND_T = ("8b 0e seed_hi:2 8b 1e seed_lo:2 ba 5a 01 b8 35 4e e8 ?? ?? "
          "05 01 00 83 d2 00 89 16 seed_hi:2 a3 seed_lo:2 "
          "a1 ret_word:2 99 25 mask:2 cb")

SRAND_T = "55 8b ec 8b 46 arg:1 c7 06 seed_hi:2 0000:2 a3 seed_lo:2 5d cb"


def count_anchor(data):
    n, i = 0, 0
    while True:
        i = data.find(ANCHOR, i)
        if i < 0:
            return n
        n += 1
        i += 1


def find_rand(img):
    d = img.data
    n = count_anchor(d)
    if n != 1:
        raise Located("anchor_354E", "expected exactly 1 occurrence of 35 4E, found %d" % n)
    a = d.find(ANCHOR)
    if d[a - 1] != 0xB8:
        raise Located("anchor_354E", "byte before the anchor is %02x, not B8" % d[a - 1])
    entry = a - 12                       # back over the two seed loads and mov dx,015A
    fields, length = match(d, entry, RAND_T)
    if d[entry - 1] not in (0xCB, 0xC3, 0xCA, 0xC2, 0xCC):
        raise Located("rand_entry", "byte before %d is %02x, not a function terminator"
                      % (entry, d[entry - 1]))
    lo, hi, ret = fields["seed_lo"], fields["seed_hi"], fields["ret_word"]
    if hi != lo + 2:
        raise Located("rand_verify", "seed halves are not adjacent words: lo=%d hi=%d" % (lo, hi))
    if ret == hi:
        returns = "HIGH_SEED_WORD"
    elif ret == lo:
        returns = "LOW_SEED_WORD"
    else:
        returns = "OTHER_WORD_%d" % ret
    return entry, length, {
        "rand_seed_disps": sorted([lo, hi]),
        "rand_returns": returns,
        "rand_mask": fields["mask"],
    }


def find_srand(img, rand_entry):
    """srand is the function that ends exactly where rand begins."""
    d = img.data
    for p in range(rand_entry - 40, rand_entry):
        f, n = try_match(d, p, SRAND_T)
        if f is not None and p + n == rand_entry:
            return p
    raise Located("srand_entry", "no srand body ends at rand's entry %d" % rand_entry)


# ---------------------------------------------------------------------------
# STAGE 2 - the census, by raw scan
# ---------------------------------------------------------------------------
def census(img, target):
    """Every call in the image whose callee is `target`.

    far    `9A off16 seg16`, resolved through the load-time segment arithmetic.
    pushcs `0E E8 rel16`, Borland's same-segment far call. The target is
           computed inside a 16-bit segment frame, so a file offset cannot
           distinguish `next+rel16` from `next+rel16-65536`: both renderings are
           accepted. Taking only one of them loses either every backward call
           (all ten into zrandom) or every wrap-encoded one.
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
        if i + 4 + rel == target or i + 4 + rel - 65536 == target:
            pushcs.append(i)
        i += 1
    return {"far": len(far), "pushcs": len(pushcs), "total": len(far) + len(pushcs),
            "sites": sorted(far + pushcs), "_far": far, "_pushcs": pushcs}


def call_at(img, off):
    """(target, length) of the call whose first byte is at `off`, or (None, 0).

    Both wrap renderings of a same-segment rel16 are returned as a pair so the
    caller can accept either.
    """
    d = img.data
    if off < 0 or off + 3 > len(d):
        return None, 0
    if d[off] == 0x9A and off + 5 <= len(d):
        o, s = struct.unpack_from("<HH", d, off + 1)
        return (img.lin(s, o),), 5
    if d[off] == 0x0E and d[off + 1] == 0xE8 and off + 4 <= len(d):
        rel = struct.unpack_from("<H", d, off + 2)[0]
        return (off + 4 + rel, off + 4 + rel - 65536), 4
    if d[off] == 0xE8:
        rel = struct.unpack_from("<H", d, off + 1)[0]
        return (off + 3 + rel, off + 3 + rel - 65536), 3
    return None, 0


def calls_to(img, off, target):
    t, _n = call_at(img, off)
    return t is not None and target in t


# ---------------------------------------------------------------------------
# STAGE 3 - random
# ---------------------------------------------------------------------------
#   push bp; mov bp,sp
#   call far <rand>
#   movsx eax,ax
#   movsx edx,word [bp+6]     <- the parameter, read as a WORD
#   imul eax,edx
#   mov ebx,0x00008000
#   cdq
#   idiv ebx
#   pop bp; retf
RANDOM_T = ("55 8b ec 9a roff:2 rseg:2 66 0f wx1:1 c0 66 0f wx2:1 56 pdisp:1 "
            "66 0f af c2 66 bb div:4 66 99 66 f7 dv:1 5d cb")

WIDEN = {0xBF: True, 0xB7: False}        # 0F BF movsx r32,r/m16 ; 0F B7 movzx


def analyse_random(img, entry, rand_entry):
    f, length = match(img.data, entry, RANDOM_T)
    if img.lin(f["rseg"], f["roff"]) != rand_entry:
        raise Located("random_analyse", "the call inside random goes to %d, not rand at %d"
                      % (img.lin(f["rseg"], f["roff"]), rand_entry))
    if f["wx2"] not in WIDEN:
        raise Located("random_analyse", "parameter is widened by opcode 0f %02x, "
                                        "neither movsx nor movzx" % f["wx2"])
    if f["pdisp"] != 6:
        raise Located("random_analyse", "parameter is at [bp+%d]; the far-model first "
                                        "argument is [bp+6]" % f["pdisp"])
    dv = f["dv"]
    if (dv & 0xC0) != 0xC0:
        raise Located("random_analyse", "the divide operand is memory, not a register")
    ext = (dv >> 3) & 7
    if ext not in (6, 7):
        raise Located("random_analyse", "F7 /%d is not a divide" % ext)
    return {
        "random_is_macro": False,        # it has its own prologue and its own RETF
        "random_param_width_bits": 16,   # 0F BF/B7 /r reads r/m16
        "random_param_signextended": WIDEN[f["wx2"]],
        "random_divisor": f["div"],
        "random_div_is_signed": ext == 7,
        "random_mul_width_bits": 32,     # 66 0F AF is imul r32,r/m32
    }, length


# ---------------------------------------------------------------------------
# STAGE 4 - zrandom and UNKNOWN 2
# ---------------------------------------------------------------------------
# A mini 16-bit decoder over exactly the opcodes a 36-byte Borland leaf can
# contain. Anything outside the set stops the decode - route C would rather
# fail loudly than guess at a body it does not understand.
R16 = ["ax", "cx", "dx", "bx", "sp", "bp", "si", "di"]


def _modrm_len(mb):
    mod, rm = mb >> 6, mb & 7
    if mod == 0:
        return 1 + (2 if rm == 6 else 0)
    if mod == 1:
        return 2
    if mod == 2:
        return 3
    return 1


def decode_one(d, p):
    """(mnemonic, operands, length) at p, or (None, None, 0)."""
    op = d[p]
    if op == 0xC8:
        return "enter", (int.from_bytes(d[p + 1:p + 3], "little"), d[p + 3]), 4
    if 0x50 <= op <= 0x57:
        return "push", (R16[op - 0x50],), 1
    if 0x58 <= op <= 0x5F:
        return "pop", (R16[op - 0x58],), 1
    if op == 0x0E:
        return "pushcs", (), 1
    if op == 0x90:
        return "nop", (), 1
    if op == 0x9B:
        return "fwait", (), 1
    if op == 0xC9:
        return "leave", (), 1
    if op in (0xCB, 0xC3):
        return "ret", (), 1
    if op == 0xE8:
        return "call", ("rel16",), 3
    if op == 0x9A:
        return "call", ("far",), 5
    if op in (0x88, 0x89, 0x8A, 0x8B, 0x00, 0x01, 0x02, 0x03, 0x28, 0x29, 0x2A, 0x2B):
        mb = d[p + 1]
        n = 1 + _modrm_len(mb)
        reg = R16[(mb >> 3) & 7]
        mod, rm = mb >> 6, mb & 7
        if mod == 3:
            place = ("reg", R16[rm])
        elif rm == 6 and mod == 0:
            place = ("abs", int.from_bytes(d[p + 2:p + 4], "little"))
        else:
            disp = 0
            if mod == 1:
                disp = struct.unpack_from("<b", d, p + 2)[0]
            elif mod == 2:
                disp = struct.unpack_from("<h", d, p + 2)[0]
            place = ("mem", rm, disp)
        mne = {0x88: "mov", 0x89: "mov", 0x8A: "mov", 0x8B: "mov",
               0x00: "add", 0x01: "add", 0x02: "add", 0x03: "add",
               0x28: "sub", 0x29: "sub", 0x2A: "sub", 0x2B: "sub"}[op]
        to_reg = op in (0x8A, 0x8B, 0x02, 0x03, 0x2A, 0x2B)
        width = 8 if op in (0x88, 0x8A, 0x00, 0x02, 0x28, 0x2A) else 16
        return mne, ("to_reg" if to_reg else "to_rm", reg, place, width), n
    if 0xD8 <= op <= 0xDF:
        mb = d[p + 1]
        return "x87", (op, (mb >> 3) & 7, mb), 1 + _modrm_len(mb)
    return None, None, 0


X87_LOADS = {(0xDF, 0): "fild_word", (0xDF, 5): "fild_qword",
             (0xDB, 0): "fild_dword", (0xD9, 0): "fld_dword",
             (0xDD, 0): "fld_qword"}
X87_INT_STORES = {(0xDF, 2), (0xDF, 3), (0xDF, 6), (0xDF, 7),
                  (0xDB, 2), (0xDB, 3), (0xD9, 2), (0xD9, 3)}


def decode_body(d, entry, limit=96):
    """Linear decode from `entry` to its terminating ret. None if any byte in
    the way is outside the closed opcode set."""
    out, p = [], entry
    while p < entry + limit:
        mne, ops, n = decode_one(d, p)
        if mne is None:
            return None
        out.append((p, mne, ops, n))
        p += n
        if mne == "ret":
            return out
    return None


PROLOGUE = (b"\x55\x8b\xec",)


def enclosing(d, site, back=64):
    """Nearest prologue at most `back` bytes before `site` whose linear decode
    lands exactly on `site`."""
    for p in range(site - 1, max(0, site - back) - 1, -1):
        if not (d[p:p + 3] in PROLOGUE or (d[p] == 0xC8 and d[p + 3] == 0x00)):
            continue
        a = p
        while a < site:
            _m, _o, n = decode_one(d, a)
            if n == 0 or a + n > site:
                a = -1
                break
            a += n
        if a == site:
            return p
    return None


def find_zrandom(img, random_entry, random_sites):
    """The unique <=64-byte caller of random that draws exactly twice and
    returns through `fild word`."""
    d = img.data
    cands = {}
    for s in random_sites:
        e = enclosing(d, s, back=64)
        if e is None or e in cands:
            continue
        body = decode_body(d, e)
        if body is None:
            continue
        length = body[-1][0] + body[-1][3] - e
        if length > 64:
            continue
        ncall = sum(1 for p, m, o, n in body if m == "call" and calls_to(img, p, random_entry))
        if ncall != 2:
            continue
        if not any(m == "x87" and X87_LOADS.get((o[0], o[1]), "").startswith("fild")
                   for p, m, o, n in body):
            continue
        cands[e] = (body, length)
    if len(cands) != 1:
        raise Located("zrandom", "expected exactly 1 candidate, found %d: %r"
                      % (len(cands), sorted(cands)))
    e = sorted(cands)[0]
    return e, cands[e][0], cands[e][1]


def analyse_zrandom(img, body, random_entry):
    """Symbolic execution of the body: which draw reaches the minuend.

    `push cs` is deliberately NOT modelled as a stack slot. It is consumed by
    the callee's RETF, so treating it as pushable shifts every later pop by one
    and reads the answer off by a draw.
    """
    d = img.data
    regs, stack = {}, []
    ndraw = 0
    call_files, sub, store, retload = [], None, None, None
    spilled = None
    for p, mne, ops, n in body:
        if mne == "call":
            if not calls_to(img, p, random_entry):
                raise Located("zrandom_dataflow", "call at %d does not go to random" % p)
            ndraw += 1
            regs["ax"] = "draw%d" % ndraw
            call_files.append(p - 1 if p >= 1 and d[p - 1] == 0x0E else p)
        elif mne == "pushcs":
            continue
        elif mne == "push":
            v = regs.get(ops[0])
            stack.append(v)
            if v is not None and spilled is None:
                spilled = v
        elif mne == "pop":
            regs[ops[0]] = stack.pop() if stack else None
        elif mne in ("sub", "add") and ops[0] == "to_reg" and ops[2][0] == "reg":
            if sub is None:
                sub = {"op": mne, "sub_file": p, "sub_dst": ops[1], "sub_src": ops[2][1],
                       "minuend": regs.get(ops[1]), "subtrahend": regs.get(ops[2][1]),
                       "result_width_bits": ops[3]}
                regs[ops[1]] = "diff"
        elif mne in ("sub", "add") and ops[0] == "to_rm" and ops[2][0] == "reg":
            if sub is None:
                sub = {"op": mne, "sub_file": p, "sub_dst": ops[2][1], "sub_src": ops[1],
                       "minuend": regs.get(ops[2][1]), "subtrahend": regs.get(ops[1]),
                       "result_width_bits": ops[3]}
                regs[ops[2][1]] = "diff"
        elif mne == "mov" and ops[0] == "to_rm" and ops[2][0] == "mem" and sub is not None \
                and store is None and regs.get(ops[1]) == "diff":
            store = {"stored_reg": ops[1], "store_width_bits": ops[3]}
        elif mne == "x87":
            nm = X87_LOADS.get((ops[0], ops[1]))
            if nm and retload is None:
                retload = nm
    if ndraw != 2:
        raise Located("zrandom_dataflow", "expected 2 draws, tracked %d" % ndraw)
    if sub is None:
        raise Located("zrandom_dataflow", "no register/register subtraction in the body")
    if sub["op"] != "sub":
        raise Located("zrandom_dataflow", "the two draws are combined with %s, not sub"
                      % sub["op"])
    if store is None:
        raise Located("zrandom_dataflow", "the difference is never stored to the frame")
    other = {"draw1": "draw2", "draw2": "draw1"}
    minuend = sub["minuend"]
    return {
        "verdict": {"draw1": "LEFT_TO_RIGHT", "draw2": "RIGHT_TO_LEFT"}.get(minuend, "INDETERMINATE"),
        "minuend": minuend, "spilled_draw": spilled, "live_draw": other.get(spilled),
        "sub_dst": sub["sub_dst"], "sub_src": sub["sub_src"], "sub_file": sub["sub_file"],
        "op": sub["op"], "stored_reg": store["stored_reg"],
        "result_width_bits": store["store_width_bits"],
        "return_load": retload, "call_files": call_files,
    }


# ---------------------------------------------------------------------------
# STAGE 5 - __ftol
# ---------------------------------------------------------------------------
FTOL_T = ("55 8b ec 83 ec fsz:1 9b d9 7e cw:1 90 9b 8a 46 hib:1 80 4e hib:1 cwimm:1 "
          "9b d9 6e cw:1 9b df fm:1 out:1 88 46 hib:1 9b d9 6e cw:1 "
          "8b 46 out:1 8b 56 out2:1 8b e5 5d cb")

RC = {0: "NEAREST", 1: "DOWN", 2: "UP", 3: "CHOP"}
FISTP_WIDTH = {(0xDF, 7): 64, (0xDF, 3): 16, (0xDB, 3): 32}


def analyse_ftol(img, entry):
    f, length = match(img.data, entry, FTOL_T)
    if (f["fm"] & 0xC7) != 0x46:
        raise Located("ftol_analyse", "the integer store is not `[bp+disp8]`")
    width = FISTP_WIDTH.get((0xDF, (f["fm"] >> 3) & 7))
    if width is None:
        raise Located("ftol_analyse", "DF /%d is not an integer store" % ((f["fm"] >> 3) & 7))
    if f["out2"] != (f["out"] + 2) & 0xFF:
        raise Located("ftol_analyse", "the two return halves are not adjacent words")
    return {
        "cw_or_immediate": f["cwimm"],
        # the control word's RC field is bits 10-11 of the word, i.e. bits 2-3
        # of the high byte - which is the byte this OR touches.
        "rounding": RC[(f["cwimm"] >> 2) & 3],
        "store_width_bits": width,
        "return_width_bits": 32,          # dx:ax, both loaded above
    }, length


# ---------------------------------------------------------------------------
# STAGE 6 - argument pushes, and UNKNOWN 1
# ---------------------------------------------------------------------------
# The forms Borland can emit for the last argument of a call, longest first.
# Longest-first matters: `68 xx 50` is `push imm16`, not a stray `push ax`.
PUSH_FORMS = [
    (5, lambda d, p: d[p] == 0x66 and d[p + 1] == 0x68, "imm32"),
    (4, lambda d, p: d[p] == 0xFF and d[p + 1] in (0x36, 0xB6), "mem"),
    (3, lambda d, p: d[p] == 0xFF and d[p + 1] == 0x76, "mem"),
    (3, lambda d, p: d[p] == 0x68, "imm16"),
    (2, lambda d, p: d[p] == 0x6A, "imm8"),
    (1, lambda d, p: 0x50 <= d[p] <= 0x57, "reg"),
]

# Skipped when walking back from a call to its argument push. Borland pads with
# 0x90 for alignment and emits 0x9B (FWAIT) around x87 code; both delivered
# decoders stop at the 0x9B, which blinds them at 49 of the 385 call sites.
PAD = (0x90, 0x9B)


def arg_push(img, site):
    """(push_offset, kind, register_or_None) for the call at `site`."""
    d = img.data
    p = site
    while p - 1 >= 0 and d[p - 1] in PAD:
        p -= 1
    for length, test, kind in PUSH_FORMS:
        q = p - length
        if q >= 0 and test(d, q):
            reg = R16[d[q] - 0x50] if kind == "reg" else None
            return q, kind, reg
    return None, None, None


def x87_ending_at(d, p):
    """The x87 instruction that ends exactly at `p`, or None. Exact, because
    x87 length is fully determined by the opcode plus the modrm."""
    for length in (2, 3, 4):
        q = p - length
        if q < 1:
            continue
        if 0xD8 <= d[q] <= 0xDF and 1 + _modrm_len(d[q + 1]) == length:
            mb = d[q + 1]
            return {"at": q, "op": d[q], "ext": (mb >> 3) & 7, "modrm": mb,
                    "is_int_store": (d[q], (mb >> 3) & 7) in X87_INT_STORES}
    return None


def call_ending_at(img, p):
    """(offset, targets) of the call that ends exactly at `p`, or (None, ())."""
    for length in (5, 4, 3):
        q = p - length
        if q < 0:
            continue
        t, n = call_at(img, q)
        if t is not None and n == length:
            return q, t
    return None, ()


def find_ftol(img, sites):
    """__ftol is whichever callee sits immediately before an argument push AND
    has the fnstcw / or / fldcw / fistp shape. Its address is never assumed."""
    seen = {}
    for s in sites:
        push, kind, _reg = arg_push(img, s)
        if push is None:
            continue
        q, targets = call_ending_at(img, push)
        if q is None:
            continue
        for t in targets:
            if 0 <= t < len(img.data):
                seen[t] = seen.get(t, 0) + 1
    good = [t for t in seen if try_match(img.data, t, FTOL_T)[0] is not None]
    if len(good) != 1:
        raise Located("ftol", "expected exactly 1 float->int helper among %d call "
                              "predecessors, found %d: %r" % (len(seen), len(good), sorted(good)))
    return good[0]


NARROW = {"ax": "LOW16_OF_FTOL", "dx": "HIGH16_OF_FTOL"}


def classify_sites(img, sites, callee_name, ftol_entry):
    """Split the call sites into

      fp        - the argument came out of the chop helper (and which half),
      nonftol   - a float reached the argument WITHOUT the chop helper, which
                  would mean a second, unmodelled narrowing into random(),
      x87_adj   - an x87 instruction sits immediately before a REGISTER push.
                  x87 cannot write a general register, so this is not by itself
                  a float argument; it is reported because it is the shape a
                  planted float takes, and it is exactly what the delivered
                  decoders' 0x9B blind spot hides.
    """
    fp, nonftol, adj = [], [], []
    d = img.data
    for s in sites:
        push, kind, reg = arg_push(img, s)
        if push is None:
            continue
        q, targets = call_ending_at(img, push)
        if q is not None and ftol_entry in targets:
            fp.append({"call": s, "callee": callee_name, "ftol": q,
                       "push": push, "push_reg": reg or "?",
                       "narrowing": NARROW.get(reg, "OTHER_REG_AFTER_FTOL")})
            continue
        x = x87_ending_at(d, push)
        if x is None:
            continue
        if kind == "mem" and x["is_int_store"]:
            nonftol.append(s)             # fistp <slot> ; push <slot>
        elif kind == "reg":
            adj.append(s)
    return fp, nonftol, adj


# ---------------------------------------------------------------------------
# the whole route
# ---------------------------------------------------------------------------
def decode(path):
    """Route C's Wave 2 verdict for the image at `path`. Same key shape as the
    two delivered decoders, so w2v_verdict's mechanical diff applies."""
    out = {"decoder": {"id": "cs", "engine": "none (byte templates)",
                       "engine_version": "w2spec/1",
                       "route": "named-field byte templates + suffix-anchored backward match"}}
    img = None
    anchor_n = None
    try:
        img = Image(path)
        out["binary"] = {"sha256": img.sha256, "size": len(img.data)}
        anchor_n = count_anchor(img.data)

        rand_entry, rand_len, rand_info = find_rand(img)
        srand_entry = find_srand(img, rand_entry)
        dgroup = find_dgroup(img)

        c_rand = census(img, rand_entry)
        if c_rand["total"] != 1:
            raise Located("random_entry", "rand must have exactly one caller, found %d at %r"
                          % (c_rand["total"], c_rand["sites"]))
        # A textual macro would inline `call rand` at every use site and give
        # rand hundreds of callers. One caller means random() is a compiled
        # out-of-line function, which is what forces the parameter through a
        # 16-bit stack slot.
        random_entry = enclosing(img.data, c_rand["sites"][0], back=32)
        if random_entry is None:
            raise Located("random_entry", "no prologue precedes rand's only call site %d"
                          % c_rand["sites"][0])
        r_info, random_len = analyse_random(img, random_entry, rand_entry)

        c_random = census(img, random_entry)
        if not c_random["total"]:
            raise Located("random_census", "random has no callers")

        z_entry, z_body, z_len = find_zrandom(img, random_entry, c_random["sites"])
        c_zrandom = census(img, z_entry)
        u2 = analyse_zrandom(img, z_body, random_entry)

        ftol_entry = find_ftol(img, c_random["sites"] + c_zrandom["sites"])
        f_info, ftol_len = analyse_ftol(img, ftol_entry)
        c_ftol = census(img, ftol_entry)

        fp_r, nf_r, ad_r = classify_sites(img, c_random["sites"], "random", ftol_entry)
        fp_z, nf_z, ad_z = classify_sites(img, c_zrandom["sites"], "zrandom", ftol_entry)
        fp = sorted(fp_r + fp_z, key=lambda e: e["call"])

        u1_verdict = ("NARROWED_AT_CALL_BOUNDARY"
                      if r_info["random_param_width_bits"] == 16 and not (nf_r or nf_z)
                      else "FP_SURVIVES_INTO_RAND")

        def body(a, n):
            return hashlib.sha256(img.data[a:a + n]).hexdigest()

        out.update({
            "status": "OK",
            "layout": {"header_len": img.header_len, "dgroup_file": dgroup,
                       "entry_file": img.entry_file, "reloc_count": img.nreloc},
            "anchors": {
                "rand_entry": rand_entry, "srand_entry": srand_entry,
                "random_entry": random_entry, "zrandom_entry": z_entry,
                "zrandom_len": z_len, "ftol_entry": ftol_entry,
                "random_len": random_len, "rand_len": rand_len, "ftol_len": ftol_len,
                "zrandom_body_sha256": body(z_entry, z_len),
                "random_body_sha256": body(random_entry, random_len),
            },
            "census": {
                "rand": {k: c_rand[k] for k in ("far", "pushcs", "total", "sites")},
                "random": {k: c_random[k] for k in ("far", "pushcs", "total", "sites")},
                "zrandom": {k: c_zrandom[k] for k in ("far", "pushcs", "total", "sites")},
                "ftol": {"total": c_ftol["total"]},
            },
            "unknown1": dict(r_info, verdict=u1_verdict, ftol=f_info, fp_sites=fp,
                             fp_sites_total=len(fp),
                             nonftol_fp_arg_sites=sorted(nf_r + nf_z)),
            "unknown2": u2,
            "randtail": rand_info,
            "x87_adjacent_reg_pushes": sorted(ad_r + ad_z),
            "selfcheck": {
                "anchor_354e_count": anchor_n,
                "far_sites_with_reloc": sum(1 for s in c_random["_far"]
                                            if (s + 3) in img.reloc_targets),
                "far_sites_total": c_random["far"],
                "pushcs_sites_with_nop_pad": sum(1 for s in c_random["_pushcs"]
                                                 if img.data[s - 1] == 0x90),
                "pushcs_sites_total": c_random["pushcs"],
            },
        })
    except Located as e:
        out["status"] = "LOCATION_FAILED"
        out["failed_stage"] = e.stage
        out["failure_detail"] = e.detail
        out["selfcheck"] = {"anchor_354e_count": anchor_n}
        if img is not None:
            out.setdefault("binary", {"sha256": img.sha256, "size": len(img.data)})
    return out
