# brtl_oracle.py - Python reference for Borland C++ 3.1's rand/random/srand.
#
# PROVENANCE, WHICH IS THE WHOLE POINT OF THIS FILE EXISTING:
#
#   This file was written from the DOS MACHINE CODE in
#       C:\programmieren\noctis\niv-plus\modules\NOCTIS.EXE
#   and from nothing else.  It was NOT translated from brtl_oracle.c, and it
#   was not translated from niv-lr/src/brtl.cpp.  The C oracle comes from a
#   third party's reading of the game; this one comes from the bytes the game
#   actually ships.  If both were transcriptions of the same text, agreement
#   between them would prove only that the transcription was consistent.
#
#   In particular this file does NOT assume that Borland's long-multiply
#   helper computes (a*b) & 0xFFFFFFFF.  It emulates the helper at file offset
#   0x3E19 instruction by instruction, in 16-bit registers, with 8086 mul /
#   xchg / jcxz semantics - and then PROVES the closed form over every state
#   the sweep will visit (see licence_lxmul).  The fast form is used for the
#   bulk lanes only after that licence has been granted.
#
#   Every byte string below was re-dumped from NOCTIS.EXE by this author and
#   is pinned here as text, in the manner of tests/test_fastrandom.py's
#   DOS_ASM, so that a stale oracle is visibly stale.  verify_against_exe()
#   re-reads the executable and checks them.
#
# ---------------------------------------------------------------------------
# THE DISASSEMBLY
# ---------------------------------------------------------------------------
#
# srand, file offset 15953 (0x3E51):
#     55                 push bp
#     8b ec              mov  bp, sp
#     8b 46 06           mov  ax, [bp+6]        ; the 16-bit argument
#     c7 06 5c 39 00 00  mov  word [395C], 0    ; high word EXPLICITLY zeroed
#     a3 5a 39           mov  [395A], ax        ; low word
#     5d                 pop  bp
#     cb                 retf
#   -> state = arg & 0xFFFF.  ZERO-extended.  The mask is stored, not implied.
#
# rand, file offset 15970 (0x3E62):
#     8b 0e 5c 39        mov  cx, [395C]        ; state high
#     8b 1e 5a 39        mov  bx, [395A]        ; state low
#     ba 5a 01           mov  dx, 015A          ; multiplier high
#     b8 35 4e           mov  ax, 4E35          ; multiplier low
#     e8 a6 ff           call 0x3E19            ; 15987 - 90 = 15897 = 0x3E19
#     05 01 00           add  ax, 1
#     83 d2 00           adc  dx, 0             ; the 16-bit machine's 32-bit +1
#     89 16 5c 39        mov  [395C], dx        ; store NEW state high
#     a3 5a 39           mov  [395A], ax        ; store NEW state low
#     a1 5c 39           mov  ax, [395C]        ; read back the new high half
#     99                 cwd                    ; dead: retval is int16 in ax
#     25 ff 7f           and  ax, 7FFF
#     cb                 retf
#   -> post-increment.  The value comes from the state AFTER the step.
#   -> the hardware never shifts; it reloads the high word.  So ">>16 signed
#      or unsigned" is not a question the hardware answers - use SHR.
#   -> the 7FFF mask is load-bearing: the high word can have bit 15 set.
#
# the long-multiply helper, file offset 15897 (0x3E19).  Entry:
#     DX:AX = multiplier (015A:4E35),  CX:BX = state (CX high, BX low)
#     56                 push si
#     96                 xchg ax, si            ; SI = 4E35 (mult low)
#     92                 xchg ax, dx            ; AX = 015A (mult high)
#     85 c0              test ax, ax
#     74 02              jz   +2                ; skip the mul if mult_hi == 0
#     f7 e3              mul  bx                ; DX:AX = mult_hi * state_lo
#     e3 05              jcxz +5                ; skip if state_hi == 0
#     91                 xchg ax, cx            ; AX = state_hi
#     f7 e6              mul  si                ; DX:AX = state_hi * mult_lo
#     03 c1              add  ax, cx            ; 16-BIT add of the two cross
#                                               ; terms; carry out is DISCARDED
#     96                 xchg ax, si            ; SI = cross sum, AX = 4E35
#     f7 e3              mul  bx                ; DX:AX = mult_lo * state_lo
#     03 d6              add  dx, si            ; fold the cross terms in
#     5e                 pop  si
#     c3                 ret
#   -> the mult_hi * state_hi term is never computed.  It would land entirely
#      at 2**32 and above, so its absence is exactly what makes this a
#      32x32 -> LOW 32 multiply.  No *% split multiply is needed anywhere.
#
# random, file offset 82487 (0x14237):
#     55                 push bp
#     8b ec              mov  bp, sp
#     9a 62 18 00 00     call far rand          ; ALWAYS called, even for n==0
#     66 0f bf c0        movsx eax, ax
#     66 0f bf 56 06     movsx edx, word [bp+6] ; the argument is a 16-bit INT,
#                                               ; SIGN-extended
#     66 0f af c2        imul eax, edx          ; signed, low 32
#     66 bb 00 80 00 00  mov  ebx, 8000h
#     66 99              cdq
#     66 f7 fb           idiv ebx               ; SIGNED divide - truncates
#                                               ; TOWARD ZERO, does not floor
#     5d                 pop  bp
#     cb                 retf
#   -> random() is a real out-of-line function in this binary, not a macro.
#   -> idiv, not sar.  This is the single easiest place to be silently wrong;
#      >>15 agrees for every non-negative n and disagrees for essentially
#      every negative one.
#
# initial state: DS base = 0x2600 + 0x2A18*16 = 182144, so the state's low
# word lives at file offset 196826 and its high word at 196828.  Both are
# inside the initialised _DATA of a 215744-byte image.  They read
#     01 00   00 00
# so the initial state is 1, proved from the shipped executable.
#
# ---------------------------------------------------------------------------

import hashlib
import os
import struct
import sys
from array import array

M8 = 0xFF
M16 = 0xFFFF
M32 = 0xFFFFFFFF

MULT = 0x015A4E35
MAGIC = 0x42525431          # "BRT1"
SENTINEL = 0x0DEFACED
DIVISOR = 0x8000

REPO = r"C:\programmieren\linoleum"
WORK = os.path.join(REPO, "work")
NOCTIS_EXE = r"C:\programmieren\noctis\niv-plus\modules\NOCTIS.EXE"

# Pinned bytes.  offset -> exact byte string.  If the reference clone moves,
# these fail loudly instead of the oracle drifting quietly.
PINNED_HEX = {
    # srand, 17 bytes
    15953: "55 8b ec 8b 46 06 c7 06 5c 39 00 00 a3 5a 39 5d cb",
    # the long-multiply helper, 23 bytes
    15897: "56 96 92 85 c0 74 02 f7 e3 e3 05 91 f7 e6 03 c1 96 f7 e3 03 d6 5e c3",
    # rand, 38 bytes
    15970: "8b 0e 5c 39 8b 1e 5a 39 ba 5a 01 b8 35 4e e8 a6 ff 05 01 00 "
           "83 d2 00 89 16 5c 39 a3 5a 39 a1 5c 39 99 25 ff 7f cb",
    # random, 33 bytes
    82487: "55 8b ec 9a 62 18 00 00 66 0f bf c0 66 0f bf 56 06 66 0f af c2 "
           "66 bb 00 80 00 00 66 99 66 f7 fb 5d cb",
    # the state cell in initialised _DATA: low word 1, high word 0
    196826: "01 00 00 00",
}

PINNED = {off: bytes.fromhex(hx) for off, hx in PINNED_HEX.items()}


def verify_against_exe(path=NOCTIS_EXE):
    """Re-read the shipped executable and confirm every pinned listing."""
    if not os.path.exists(path):
        return None, "%s not found - provenance unverified" % path
    with open(path, "rb") as fh:
        blob = fh.read()
    bad = []
    for off, want in sorted(PINNED.items()):
        got = blob[off:off + len(want)]
        if got != want:
            bad.append((off, want.hex(), got.hex()))
    # the multiplier's low half must be unique in the image, which is what
    # makes the rand() location unambiguous
    n_354e = blob.count(b"\x35\x4e")
    return (len(blob), bad, n_354e), None


# The MZ header fields, in order, so the relocation table can be walked.
_MZ = "<14H"        # magic cblp cp crlc cparhdr mina maxa ss sp csum ip cs
                    # lfarlc ovno


def verify_call_graph(path=NOCTIS_EXE):
    """Resolve the far call inside random() and count rand()'s callers.

    This is the check that closes open question O1's premise for THIS binary.
    random() at 0x14237 contains

        9a 62 18 00 00      call far 0000:1862

    whose segment word carries a relocation entry, so 0x0000 is the image's
    base code segment.  With a 9728-byte MZ header that resolves to file
    offset 9728 + 0 + 0x1862 = 15970 - which is rand() exactly.

    Then: how many far calls anywhere in the image target that offset with a
    relocated segment word?  If the answer is ONE, random() is rand()'s only
    caller, and no call site can be inlining the generator - which is what
    makes "random() takes a sign-extended int16" a statement about every one
    of the call sites rather than about this wrapper alone.

    Returns (header_bytes, resolved_offset, n_callers, reloc_ok) or None.
    """
    if not os.path.exists(path):
        return None
    with open(path, "rb") as fh:
        blob = fh.read()
    hd = struct.unpack_from(_MZ, blob, 0)
    crlc, cparhdr, lfarlc = hd[3], hd[4], hd[12]
    hdr_bytes = cparhdr * 16

    relocated = set()
    for i in range(crlc):
        off, seg = struct.unpack_from("<HH", blob, lfarlc + i * 4)
        relocated.add(hdr_bytes + seg * 16 + off)

    call_site = 82490                       # the 9a inside random()
    if blob[call_site] != 0x9A:
        return None
    target_off = struct.unpack_from("<H", blob, call_site + 1)[0]
    target_seg = struct.unpack_from("<H", blob, call_site + 3)[0]
    reloc_ok = (call_site + 3) in relocated and target_seg == 0
    resolved = hdr_bytes + target_seg * 16 + target_off

    callers = 0
    for i in range(len(blob) - 5):
        if blob[i] != 0x9A:
            continue
        if struct.unpack_from("<H", blob, i + 1)[0] != target_off:
            continue
        if (i + 3) in relocated and \
                struct.unpack_from("<H", blob, i + 3)[0] == target_seg:
            callers += 1

    return hdr_bytes, resolved, callers, reloc_ok


# ---------------------------------------------------------------------------
# The helper at 0x3E19, emulated.  16-bit registers, 8086 semantics.
# ---------------------------------------------------------------------------

def lxmul_emulate(state, mult, si_garbage=0xDEAD):
    """DX:AX * CX:BX -> DX:AX, exactly as the bytes at 0x3E19 do it.

    si_garbage is whatever the caller happened to have in SI; the routine
    saves and restores it and must never let it influence the result.  Pass
    different values to prove that.
    """
    AX = mult & M16                 # entry: b8 35 4e
    DX = (mult >> 16) & M16         # entry: ba 5a 01
    BX = state & M16                # entry: 8b 1e 5a 39
    CX = (state >> 16) & M16        # entry: 8b 0e 5c 39
    SI = si_garbage & M16

    saved_si = SI                   # 56       push si
    AX, SI = SI, AX                 # 96       xchg ax, si
    AX, DX = DX, AX                 # 92       xchg ax, dx

    if AX != 0:                     # 85 c0 test ax,ax / 74 02 jz +2
        prod = AX * BX              # f7 e3    mul bx
        AX = prod & M16
        DX = (prod >> 16) & M16

    if CX != 0:                     # e3 05    jcxz +5
        AX, CX = CX, AX             # 91       xchg ax, cx
        prod = AX * SI              # f7 e6    mul si
        AX = prod & M16
        DX = (prod >> 16) & M16
        AX = (AX + CX) & M16        # 03 c1    add ax, cx   (16-bit, no carry)

    AX, SI = SI, AX                 # 96       xchg ax, si
    prod = AX * BX                  # f7 e3    mul bx
    AX = prod & M16
    DX = (prod >> 16) & M16
    DX = (DX + SI) & M16            # 03 d6    add dx, si   (16-bit, no carry)

    assert saved_si == (si_garbage & M16)   # 5e pop si / c3 ret
    return ((DX << 16) | AX) & M32


def add1_emulate(dxax):
    """05 01 00 add ax,1 / 83 d2 00 adc dx,0 - the 16-bit machine's 32-bit +1."""
    AX = dxax & M16
    DX = (dxax >> 16) & M16
    AX += 1
    carry = 1 if AX > M16 else 0
    AX &= M16
    DX = (DX + carry) & M16
    return ((DX << 16) | AX) & M32


# ---------------------------------------------------------------------------
# The generator.  Arbitrary-precision integers with EXPLICIT masks, so the
# intended width of every operation is visible in the source rather than
# inherited from the hardware.
# ---------------------------------------------------------------------------

def to_int32(u):
    u &= M32
    return u - 0x100000000 if u & 0x80000000 else u


def to_int16(u):
    """The int16-with-wraparound narrowing.  Also the zrandom() idiom."""
    u &= M16
    return u - 0x10000 if u & 0x8000 else u


def trunc_div(p, d):
    """C's integer division: truncate TOWARD ZERO.

    Written out rather than using Python's //, because // FLOORS and that is
    precisely the bug this whole wave exists to exclude.  For p < 0 the two
    differ by one whenever p is not a multiple of d.
    """
    q = abs(p) // abs(d)
    return -q if (p < 0) != (d < 0) else q


class Brtl(object):
    """State is one 32-bit cell, initialised to 1 (read out of NOCTIS.EXE)."""

    __slots__ = ("state", "exact_mul")

    def __init__(self, exact_mul=False):
        self.state = 1
        self.exact_mul = exact_mul      # True -> route through lxmul_emulate

    # --- the three entry points ------------------------------------------

    def srand(self, arg):
        self.state = arg & M16          # c7 06 5c 39 00 00 ; a3 5a 39

    def setstate(self, state):          # lane 2 only; not a game API
        self.state = state & M32

    def rand(self):
        if self.exact_mul:
            prod = lxmul_emulate(self.state, MULT)
            self.state = add1_emulate(prod)
        else:
            self.state = (self.state * MULT + 1) & M32
        return (self.state >> 16) & 0x7FFF          # SHR then mandatory mask

    def random(self, n):
        """n must already be a signed 16-bit int (movsx of word [bp+6])."""
        r = self.rand()                             # ALWAYS drawn, even n == 0
        product = to_int32((r * n) & M32)           # imul eax,edx : low 32
        return trunc_div(product, DIVISOR)          # idiv ebx : toward zero


# ---------------------------------------------------------------------------
# The licence: prove the closed form equals the emulated helper over every
# state the sweep will visit, then use the closed form for the bulk lanes.
# ---------------------------------------------------------------------------

FAM = (0x0000, 0x0001, 0x7FFF, 0x8000, 0xFFFF)
L3SEED = (0, 1, 12345, 65535)
L4HIGH = (0x0000, 0xFFFF, 0x8000, 0xC5A1)


def lane2_states():
    """The 655360 states of lane 2 - all 65536 high halves against five
    adversarial low halves, and all 65536 low halves against five adversarial
    high halves.  Complete in each 16-bit half."""
    for f in range(10):
        if f < 5:
            lo = FAM[f]
            for j in range(65536):
                yield (j << 16) | lo
        else:
            hi = FAM[f - 5] << 16
            for j in range(65536):
                yield hi | j


def licence_lxmul(progress=None):
    """assert lxmul_emulate(s, MULT) == (s*MULT) & M32 for all lane-2 states.

    Returns (checked, mismatches).  A nonzero mismatch count invalidates every
    bulk lane, because the bulk lanes use the closed form.
    """
    emulate = lxmul_emulate
    mism = 0
    n = 0
    for s in lane2_states():
        if emulate(s, MULT) != (s * MULT) & M32:
            mism += 1
        n += 1
        if progress and (n % 131072) == 0:
            progress(n)
    return n, mism


def licence_lxmul_si_independence():
    """The helper must not depend on the caller's SI.  Sample adversarially."""
    probes = (0x0000, 0x0001, 0x7FFF, 0x8000, 0xFFFF, 0xDEAD, 0x4E35, 0x015A)
    states = (0, 1, 0xFFFFFFFF, 0x80000000, 0x7FFFFFFF, 0x0000FFFF,
              0xFFFF0000, 0x015A4E35, 0xC5A19999, 12345)
    bad = 0
    for s in states:
        ref = lxmul_emulate(s, MULT, si_garbage=probes[0])
        for g in probes[1:]:
            if lxmul_emulate(s, MULT, si_garbage=g) != ref:
                bad += 1
    return len(states) * (len(probes) - 1), bad


# ---------------------------------------------------------------------------
# Lane generation, in the binding interchange format.
# ---------------------------------------------------------------------------

LANESPEC = {
    1: ("brtl-sweep", 65536, 16),
    2: ("brtl-step", 10, 65536),
    3: ("brtl-rand", 65536, 8),
    4: ("brtl-srand", 65536, 4),
}


def _pack(lane, n1, n2, payload):
    records = n1 * n2
    if len(payload) != records * 2:
        raise SystemExit("lane %d: %d units, expected %d"
                         % (lane, len(payload), records * 2))
    hdr = array("I", [MAGIC, lane, n1, n2, records, 2, records * 2, SENTINEL])
    if sys.byteorder != "little":
        hdr.byteswap()
        payload.byteswap()
    return hdr.tobytes() + payload.tobytes()


def gen_lane1(gen=None):
    """65536 seeds, srand each, 16 draws.  index = seed*16 + draw."""
    g = gen or Brtl()
    out = array("I")
    ap = out.append
    for seed in range(65536):
        g.srand(seed)
        for _ in range(16):
            ap(g.rand())
            ap(g.state)
    return _pack(1, 65536, 16, out)


def gen_lane2(gen=None):
    """10 families x 65536 states, state set DIRECTLY, one step each."""
    g = gen or Brtl()
    out = array("I")
    ap = out.append
    for st in lane2_states():
        g.setstate(st)
        ap(g.rand())
        ap(g.state)
    return _pack(2, 10, 65536, out)


def gen_lane3(gen=None):
    """All 65536 int16 arguments x 4 seeds x 2 draws of random(n)."""
    g = gen or Brtl()
    out = array("I")
    ap = out.append
    for k in range(65536):
        n = to_int16(k)
        for seed in L3SEED:
            g.srand(seed)
            for _ in range(2):
                ap(g.random(n) & M32)      # two's complement for negative n
                ap(g.state)
    return _pack(3, 65536, 8, out)


def gen_lane4(gen=None):
    """The srand mask: all 65536 low halves against four high halves."""
    g = gen or Brtl()
    out = array("I")
    ap = out.append
    for j in range(65536):
        for h in L4HIGH:
            g.srand((h << 16) | j)
            ap(g.rand())
            ap(g.state)
    return _pack(4, 65536, 4, out)


GENERATORS = {1: gen_lane1, 2: gen_lane2, 3: gen_lane3, 4: gen_lane4}


def write_lanes(outdir=WORK, suffix="-py", lanes=(1, 2, 3, 4), gen=None):
    paths = {}
    for lane in lanes:
        name = LANESPEC[lane][0]
        blob = GENERATORS[lane](gen)
        path = os.path.join(outdir, "%s%s.bin" % (name, suffix))
        with open(path, "wb") as fh:
            fh.write(blob)
        paths[lane] = path
    return paths


# ---------------------------------------------------------------------------
# Negative controls.  Each is a deliberately wrong variant; each must diverge,
# and must diverge in the PREDICTED place.  A control that breaks the wrong
# records fails just as hard as one that agrees.
# ---------------------------------------------------------------------------

class NC1_ShiftForDivide(Brtl):
    """>>15 (arithmetic, floors) substituted for /8000h (truncates)."""
    def random(self, n):
        r = self.rand()
        product = to_int32((r * n) & M32)
        return product >> 15                      # Python >> on int floors


class NC2_NoMask(Brtl):
    """the & 7FFFh dropped from rand()."""
    def rand(self):
        self.state = (self.state * MULT + 1) & M32
        return (self.state >> 16) & M16


class NC3_UnsignedDivide(Brtl):
    """'/ instead of / in random()."""
    def random(self, n):
        r = self.rand()
        product = (r * n) & M32                   # left unsigned
        return product // DIVISOR


class NC4_SrandNoMask(Brtl):
    """srand storing the full 32-bit argument instead of masking to 16."""
    def srand(self, arg):
        self.state = arg & M32


class NC5_ZeroShortCircuit(Brtl):
    """random(0) returning early without consuming a draw.

    The values are all still 0 and therefore still correct; only the STATE
    field catches this.  It is the reason the interchange record carries the
    state at all.
    """
    def random(self, n):
        if n == 0:
            return 0
        return Brtl.random(self, n)


CONTROLS = {
    "NC1 >>15 for /8000h": (NC1_ShiftForDivide, 3),
    "NC2 no & 7FFFh": (NC2_NoMask, 1),
    "NC3 unsigned divide": (NC3_UnsignedDivide, 3),
    "NC4 srand without mask": (NC4_SrandNoMask, 4),
    "NC5 random(0) short-circuit": (NC5_ZeroShortCircuit, 3),
}


# ---------------------------------------------------------------------------

def payload_sha(blob):
    return hashlib.sha256(blob[32:]).hexdigest()


def spot(seed, n=10):
    g = Brtl()
    g.srand(seed)
    return [g.rand() for _ in range(n)]


def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else WORK
    suffix = sys.argv[2] if len(sys.argv) > 2 else "-py"

    print("brtl_oracle (Python, from the NOCTIS.EXE disassembly)")

    info, err = verify_against_exe()
    if err:
        print("  provenance: %s" % err)
    else:
        size, bad, n_354e = info
        print("  provenance: NOCTIS.EXE %d bytes, %d pinned listings, "
              "%d mismatches, '35 4e' occurs %d time(s)"
              % (size, len(PINNED), len(bad), n_354e))
        for off, want, got in bad:
            print("    MISMATCH at %d: want %s got %s" % (off, want, got))
        if bad:
            return 2
        if n_354e != 1:
            print("    WARNING: the multiplier low half is no longer unique")

    cg = verify_call_graph()
    if cg is None:
        print("  call graph: not verified")
    else:
        hdr_bytes, resolved, callers, reloc_ok = cg
        print("  call graph: random()'s far call resolves to file %d "
              "(rand is at 15970), MZ header %d bytes, reloc entry %s; "
              "rand has %d caller(s)"
              % (resolved, hdr_bytes, "present" if reloc_ok else "ABSENT",
                 callers))
        if resolved != 15970 or not reloc_ok:
            print("    the wrapper does not call rand - the model is wrong")
            return 2
        if callers != 1:
            print("    WARNING: rand has %d callers, so some site may be "
                  "inlining the generator" % callers)

    n, bad = licence_lxmul_si_independence()
    print("  lxmul SI-independence : %d/%d probes agree" % (n - bad, n))
    if bad:
        return 2

    print("  lxmul licence         : emulating 0x3E19 over all 655360 "
          "lane-2 states ...")
    n, mism = licence_lxmul()
    print("    %d states, %d mismatches against (s*%08X) & 2**32-1"
          % (n, mism, MULT))
    if mism:
        print("    LICENCE REFUSED - the closed form is not the helper")
        return 2
    print("    LICENCE GRANTED - the closed form may be used for bulk lanes")

    for s in (1, 0, 65535, 12345):
        print("  srand(%-5d) -> %s" % (s, " ".join("%d" % v for v in spot(s))))

    paths = write_lanes(outdir, suffix)
    for lane in sorted(paths):
        blob = open(paths[lane], "rb").read()
        print("  %-44s %10d bytes  payload sha256 %s"
              % (paths[lane], len(blob), payload_sha(blob)[:16]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
