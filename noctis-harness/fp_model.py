"""WAVE 3 / IMPLEMENTER 2 - an x87 stack machine defined in exact arithmetic.

Every value is a Fraction.  Every rounding is the DEFINITION of correct
rounding applied to a Fraction: choose the representable number nearest the
exact result, break ties to even.  Nothing here inherits a behaviour from the
hardware it runs on - CPython's own floats are used only to pack the final
answer into eight bytes, never to compute one.

That is the whole point.  fp_x87ref.c asks a physical 387-descendant what it
does; this file states what a 387 is SUPPOSED to do.  If the two agree, the
agreement is between an artifact and a specification, not between two copies
of the same mistake.

x87 semantics implemented, and the two that are easy to get wrong:

  * The precision-control field rounds ARITHMETIC RESULTS to 24/53/64 mantissa
    bits.  It does NOT round loads.  `fld` of a double at PC=24 keeps all 53
    bits in the register; only the next fadd/fmul/fdiv/fsqrt narrows.  Getting
    this backwards changes the PC=24 score and would make the negative control
    meaningless.
  * The precision-control field does NOT narrow the EXPONENT.  A register at
    PC=24 still has the 15-bit extended exponent range, so it is not a float.
    `fstps` is what makes a float.

Underflow is modelled properly (gradual, to the destination format's subnormal
grid) even though nothing in Noctis's generation path goes near it; leaving it
out would have been a silent assumption.

CLI:
    python fp_model.py <sched.txt> <ChainName> <fpvec.bin> <fpout.bin> [cwhex|INF]

The pseudo-control-word INF runs the schedule with NO intermediate rounding at
all - registers hold the exact rational, and the single `fstp` rounds once to
double.  That is Recon C's "exact integer product rounded once" shortcut,
expressed as the same schedule at infinite register precision instead of as a
separate hand-written formula, so the two cannot drift apart.  It exists to
MEASURE how often the shortcut and the real 64-bit chain disagree, which is
the honest limit of the STARMAP oracle.
"""

import os
import struct
import sys
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fp_sched  # noqa: E402

# rounding-control encodings, x87 CW bits 11:10
RC_NEAR, RC_DOWN, RC_UP, RC_CHOP = 0, 1, 2, 3
# precision-control encodings, x87 CW bits 9:8  ->  mantissa bits
PC_BITS = {0: 24, 1: None, 2: 53, 3: 64}

# destination formats: (mantissa bits, exponent of the least significant bit
# of the smallest subnormal, maximum finite magnitude)
FMT_F64 = (53, -1074)
FMT_F32 = (24, -149)
FMT_EXT = (64, -16445)

TWO = Fraction(2)
HALF = Fraction(1, 2)


class Overflow(Exception):
    pass


def _binade(f):
    """Largest e with 2**e <= f, for a positive Fraction."""
    e = f.numerator.bit_length() - f.denominator.bit_length()
    # bit_length arithmetic is off by at most one either way
    if TWO ** e > f:
        e -= 1
    elif TWO ** (e + 1) <= f:
        e += 1
    return e


def round_to(frac, prec, min_ulp_exp, rc):
    """Round an exact Fraction to `prec` significant bits under mode `rc`.

    `min_ulp_exp` clamps the unit-in-last-place exponent, which is what makes
    subnormals subnormal.  Returns an exact Fraction.
    """
    if frac == 0:
        return Fraction(0)
    neg = frac < 0
    f = -frac if neg else frac
    e = _binade(f)
    ulp_exp = e - prec + 1
    if ulp_exp < min_ulp_exp:
        ulp_exp = min_ulp_exp
    scale = TWO ** ulp_exp
    scaled = f / scale
    n = scaled.numerator // scaled.denominator
    rem = scaled - n
    if rem:
        if rc == RC_NEAR:
            if rem > HALF or (rem == HALF and (n & 1)):
                n += 1
        elif rc == RC_CHOP:
            pass
        elif rc == RC_DOWN:          # toward -infinity
            if neg:
                n += 1
        elif rc == RC_UP:            # toward +infinity
            if not neg:
                n += 1
        else:
            raise ValueError("rc")
    out = Fraction(n) * scale
    return -out if neg else out


def frac_to_bits64(frac):
    """Pack an exact Fraction that is already a representable double."""
    if frac == 0:
        return 0
    neg = frac < 0
    f = -frac if neg else frac
    e = _binade(f)
    ulp_exp = max(e - 52, -1074)
    q = f / (TWO ** ulp_exp)
    assert q.denominator == 1, "value is not on the double grid"
    m = q.numerator
    if ulp_exp == -1074 and m < (1 << 52):        # subnormal
        bits = m
    else:
        exp = e + 1023
        if not (1 <= exp <= 2046):
            raise Overflow("double exponent %d out of range" % exp)
        bits = (exp << 52) | (m - (1 << 52))
    return bits | ((1 << 63) if neg else 0)


def bits64_to_frac(bits):
    v = struct.unpack("<d", struct.pack("<Q", bits & ((1 << 64) - 1)))[0]
    if v != v or v in (float("inf"), float("-inf")):
        raise ValueError("non-finite input double")
    return Fraction(v)


class X87(object):
    """An eight-register x87 stack over exact rationals."""

    def __init__(self, cw):
        self.set_cw(cw)
        self.st = []            # st[0] is st(0); values are exact Fractions
        self.top_faults = 0

    def set_cw(self, cw):
        """cw is a 16-bit control word, or the string "INF" for a register file
        of infinite precision (no intermediate rounding whatsoever)."""
        if cw == "INF":
            self.cw, self.rc, self.prec = "INF", RC_NEAR, None
            return
        self.cw = cw & 0xFFFF
        self.rc = (cw >> 10) & 3
        pc = (cw >> 8) & 3
        bits = PC_BITS[pc]
        if bits is None:
            raise ValueError("PC field 01 is reserved (cw=%04X)" % cw)
        self.prec = bits

    # -- register-level rounding -------------------------------------------
    def _r(self, frac):
        if self.prec is None:
            return frac                      # INF: the register is exact
        return round_to(frac, self.prec, FMT_EXT[1], self.rc)

    def push(self, frac):
        if len(self.st) >= 8:
            raise Overflow("x87 stack overflow")
        self.st.insert(0, Fraction(frac))

    def pop(self):
        if not self.st:
            raise Overflow("x87 stack underflow")
        return self.st.pop(0)

    def depth(self):
        return len(self.st)


def load_vec(path):
    blob = open(path, "rb").read()
    if len(blob) < 32:
        raise ValueError("fpvec too short")
    hdr = struct.unpack_from("<8I", blob, 0)
    if hdr[0] != 0x46505643:
        raise ValueError("fpvec magic %08X != 'FPVC'" % hdr[0])
    if hdr[1] != 1:
        raise ValueError("fpvec version %d" % hdr[1])
    ncase, caseu, sid, cw = hdr[2], hdr[3], hdr[4], hdr[5]
    if caseu != 16:
        raise ValueError("fpvec CASEU %d != 16" % caseu)
    need = 32 + ncase * 64
    if len(blob) < need:
        raise ValueError("fpvec truncated: %d bytes, need %d" % (len(blob), need))
    cases = []
    for i in range(ncase):
        u = struct.unpack_from("<16I", blob, 32 + i * 64)
        f64 = [(u[2 * k] | (u[2 * k + 1] << 32)) for k in range(4)]
        i32 = [struct.unpack("<i", struct.pack("<I", u[8 + k]))[0] for k in range(4)]
        cases.append((f64, i32, u[12]))
    return sid, cw, ncase, cases


OUT_MAGIC = 0x46504F54
BACKEND_C_X87 = 4
BACKEND_PY_MODEL = 5
SENT_HDR = 0x0DEFACED
SENT_CASE = 0x5A5A5A5A


def pack_out(path, backend, cwmask, sw, results):
    """results: list of dicts with keys f64bits,chop,near,i16,cmp,flags"""
    out = bytearray()
    out += struct.pack("<8I", OUT_MAGIC, 1, len(results), 8, backend,
                       cwmask & 0x0F3F, sw, SENT_HDR)
    for r in results:
        b = r["f64bits"]
        out += struct.pack("<2I", b & 0xFFFFFFFF, (b >> 32) & 0xFFFFFFFF)
        out += struct.pack("<3i", r["chop"], r["near"], r["i16"])
        out += struct.pack("<i", r["cmp"])
        out += struct.pack("<2I", r["flags"], SENT_CASE)
    open(path, "wb").write(bytes(out))
    return len(out)


def read_out(path):
    blob = open(path, "rb").read()
    hdr = struct.unpack_from("<8I", blob, 0)
    if hdr[0] != OUT_MAGIC:
        raise ValueError("%s: magic %08X != 'FPOT'" % (path, hdr[0]))
    if hdr[1] != 1:
        raise ValueError("%s: version %d" % (path, hdr[1]))
    ncase, caseu, backend, cw, sw, sent = hdr[2], hdr[3], hdr[4], hdr[5], hdr[6], hdr[7]
    if caseu != 8:
        raise ValueError("%s: CASEU out %d != 8" % (path, caseu))
    if sent != SENT_HDR:
        raise ValueError("%s: header sentinel %08X" % (path, sent))
    if len(blob) < 32 + ncase * 32:
        raise ValueError("%s: truncated (%d bytes, %d cases)" % (path, len(blob), ncase))
    rows = []
    for i in range(ncase):
        u = struct.unpack_from("<2I", blob, 32 + i * 32)
        s = struct.unpack_from("<4i", blob, 32 + i * 32 + 8)
        t = struct.unpack_from("<2I", blob, 32 + i * 32 + 24)
        if t[1] != SENT_CASE:
            raise ValueError("%s: case %d sentinel %08X" % (path, i, t[1]))
        rows.append({"f64bits": u[0] | (u[1] << 32), "chop": s[0], "near": s[1],
                     "i16": s[2], "cmp": s[3], "flags": t[0]})
    return {"backend": backend, "cw": cw, "sw": sw, "ncase": ncase, "rows": rows}


INT32_MIN = -(1 << 31)
INT32_MAX = (1 << 31) - 1


def _conv(frac, mode):
    """mode 'chop' = truncate toward zero (Borland __ftol), 'near' = fistp at
    RC=00, i.e. round-half-to-even.  Returns (value, overflowed)."""
    if mode == "chop":
        n = int(frac)              # Fraction -> int truncates toward zero
    else:
        n = round_to(frac, 64, 0, RC_NEAR)
        assert n.denominator == 1
        n = int(n)
    if n < INT32_MIN or n > INT32_MAX:
        return INT32_MIN, True     # x87 "integer indefinite"
    return n, False


def run_chain(chain, f64in, i32in, cw=None):
    """Execute one chain on one case.  Returns (result Fraction, stack depth)."""
    m = X87(chain.cw if cw is None else cw)
    mem = {}
    fi = 0
    ii = 0
    for nm, ty in chain.ins:
        if ty == "int32":
            mem[nm] = Fraction(i32in[ii])
            ii += 1
        else:
            mem[nm] = bits64_to_frac(f64in[fi])
            fi += 1
    for nm, ty, txt in chain.consts:
        if ty == "int32":
            mem[nm] = Fraction(int(txt, 0))
        else:
            mem[nm] = Fraction(float(txt))   # the double NEAREST the literal
    for nm, ty in chain.vars:
        mem[nm] = Fraction(0)
    mem[chain.out[0]] = Fraction(0)

    S = fp_sched
    for op, arg in chain.ops:
        if op in S.PUSH_I32 or op in S.PUSH_F64 or op in S.PUSH_F32:
            m.push(mem[arg])                       # loads are EXACT, never PC-rounded
        elif op == "fld1":
            m.push(Fraction(1))
        elif op == "fldz":
            m.push(Fraction(0))
        elif op == "fldst0":
            m.push(m.st[0])
        elif op in S.MEM_F64 or op in S.MEM_I32:
            a = m.st[0]
            b = mem[arg]
            base = op[2:] if op in S.MEM_I32 else op[1:]
            if base == "add":
                v = a + b
            elif base == "mul":
                v = a * b
            elif base == "sub":
                v = a - b
            elif base == "subr":
                v = b - a
            elif base == "div":
                if b == 0:
                    raise ZeroDivisionError("%s by zero" % op)
                v = a / b
            elif base == "divr":
                if a == 0:
                    raise ZeroDivisionError("%s by zero" % op)
                v = b / a
            else:
                raise ValueError(op)
            m.st[0] = m._r(v)
        elif op in S.POP2:
            a = m.st[0]
            b = m.st[1]
            base = op[1:-1]
            if base == "add":
                v = b + a
            elif base == "mul":
                v = b * a
            elif base == "sub":
                v = b - a          # FSUBP  ST(1),ST(0):  st1 <- st1 - st0
            elif base == "subr":
                v = a - b          # FSUBRP ST(1),ST(0):  st1 <- st0 - st1
            elif base == "div":
                if a == 0:
                    raise ZeroDivisionError("fdivp by zero")
                v = b / a
            elif base == "divr":
                if b == 0:
                    raise ZeroDivisionError("fdivrp by zero")
                v = a / b
            else:
                raise ValueError(op)
            m.pop()
            m.st[0] = m._r(v)
        elif op == "fabs":
            m.st[0] = abs(m.st[0])                 # exact, no rounding
        elif op == "fchs":
            m.st[0] = -m.st[0]                     # exact, no rounding
        elif op == "fsqrt":
            if m.prec is None:
                raise ValueError("fsqrt has no exact rational value; INF mode "
                                 "cannot run a chain containing it")
            m.st[0] = _sqrt_round(m.st[0], m.prec, m.rc)
        elif op == "frndint":
            m.st[0] = round_to(m.st[0], 64, 0, m.rc)
        elif op == "fxch":
            m.st[0], m.st[1] = m.st[1], m.st[0]
        elif op in S.STORE_F64:
            mem[arg] = round_to(m.pop(), FMT_F64[0], FMT_F64[1], m.rc)
        elif op in S.STORE_F32:
            mem[arg] = round_to(m.pop(), FMT_F32[0], FMT_F32[1], m.rc)
        elif op in S.STORE_I32:
            v = round_to(m.pop(), 64, 0, m.rc)
            mem[arg] = v
        else:
            raise ValueError("unimplemented mnemonic %r" % op)
    return mem[chain.out[0]], m.depth()


def _sqrt_round(frac, prec, rc):
    """Correctly-rounded square root of an exact non-negative Fraction.

    Computed by integer isqrt on a scaled numerator, so the result is the exact
    mathematical root rounded once - which is the IEEE definition of fsqrt.
    """
    import math
    if frac < 0:
        raise ValueError("fsqrt of a negative")
    if frac == 0:
        return Fraction(0)
    e = _binade(frac)
    # want ~prec+2 good bits: scale so that the root has >= prec+2 integer bits
    sh = 2 * (prec + 4) - e
    if sh % 2:
        sh += 1
    n = frac * (TWO ** sh)
    num = n.numerator // n.denominator
    root = math.isqrt(num)
    # remember whether we lost anything, so ties are broken on the true value
    exact = (root * root == num) and (n.denominator == 1 or
                                      n.numerator % n.denominator == 0)
    approx = Fraction(root, 1) / (TWO ** (sh // 2))
    r = round_to(approx if exact else approx + Fraction(1, 1 << 200),
                 prec, FMT_EXT[1], rc)
    if not exact:
        # the +tiny above only breaks exact ties away from a false "exactly
        # representable" verdict; verify by comparing r*r against frac
        lo = round_to(approx, prec, FMT_EXT[1], rc)
        if lo != r:
            # ambiguous - decide by exact comparison of the two candidates
            cand = sorted({lo, r})
            best = min(cand, key=lambda c: abs(c * c - frac))
            r = best
    return r


def main():
    if len(sys.argv) < 5:
        print(__doc__)
        return 2
    schedpath, chainname, vecpath, outpath = sys.argv[1:5]
    cwover = None
    if len(sys.argv) > 5:
        cwover = "INF" if sys.argv[5].upper() == "INF" else int(sys.argv[5], 16)
    chains = fp_sched.parse(open(schedpath).read())
    if chainname not in chains:
        print("no chain %r in %s; have %s" % (chainname, schedpath, list(chains)))
        return 2
    chain = chains[chainname]
    sid, cw, ncase, cases = load_vec(vecpath)
    if sid != chain.sid:
        print("WARNING: fpvec schedule id %d != chain %s sid %d"
              % (sid, chain.name, chain.sid))
    use_cw = cwover if cwover is not None else cw

    # REJECT, defined identically here and in fp_x87ref.c: a result that is
    # zero, subnormal, infinite or NaN cannot discriminate one engine from
    # another, and the two sides legitimately represent such results
    # differently (this model raises where silicon produces an infinity).  The
    # flag itself is still compared; only the value slots are skipped, and
    # fp_diff.py is what does the skipping.
    TINY = Fraction(1) / (TWO ** 1022)
    rows = []
    nrej = 0
    for f64in, i32in, mask in cases:
        flags = 0
        try:
            v, depth = run_chain(chain, f64in, i32in, use_cw)
            if depth != 0:
                flags |= 2
            if v == 0 or abs(v) < TINY:
                flags |= 1
            bits = frac_to_bits64(v)
            chop, ovc = _conv(v, "chop")
            near, ovn = _conv(v, "near")
            i16 = struct.unpack("<h", struct.pack("<H", chop & 0xFFFF))[0]
            cmp = (0 if v == 0 else (1 if v > 0 else -1))
        except (Overflow, ZeroDivisionError, ValueError):
            flags |= 1
            bits = chop = near = i16 = cmp = 0
        if flags & 1:
            nrej += 1
        rows.append({"f64bits": bits, "chop": chop, "near": near, "i16": i16,
                     "cmp": cmp, "flags": flags})
    cwfield = 0x0F3F if use_cw == "INF" else use_cw
    n = pack_out(outpath, BACKEND_PY_MODEL, cwfield, 0x0000, rows)
    print("fp_model: chain=%s cw=%s cases=%d rejects=%d -> %s (%d bytes)"
          % (chain.name, use_cw if use_cw == "INF" else "%04X" % use_cw,
             len(rows), nrej, outpath, n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
