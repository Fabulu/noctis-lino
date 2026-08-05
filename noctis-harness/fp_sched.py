"""WAVE 3 / IMPLEMENTER 2 - schedule descriptions and an independent reader.

The schedule format is the one frozen in the architecture decision, section 2.
This file is the REFERENCE SIDE's own reader; Implementer 1 writes theirs
separately and on purpose, so that an ambiguity in the format shows up as a
disagreement rather than being hidden by a shared parser.

Format, one mnemonic per line, in the order the binary has them:

    chain <Name>
      sid   <n>              stable numeric id, echoed into fpvec.bin unit 4
      cw    <hex>            control word the chain is defined at
      exact                  optional: NATIVE backend must refuse this chain
      in    int32 x, y, z    binds to the int32 case slots, in order
      in    f64   a, b       binds to the f64 case slots, in order
      out   f64   id
      var   f64   mid        scratch memory (a deliberate spill target)
      const K100000 = int32 100000
      const KIS     = f64 1e-05
      <mnemonic> [operand]

`fstp` is the only store.  An `fstp` followed by an `fld` of the same slot is
how a DELIBERATE SPILL is expressed, so a transcription that finds one in
NOCTIS.EXE can say so.

Mnemonics understood by both readers (C: fp_x87ref.c, Python: fp_model.py):

  push   fild <i32>  fld <f64>  flds <f32>  fld1  fldz  fldst0
  mem    fadd/fsub/fsubr/fmul/fdiv/fdivr <f64>
         fiadd/fisub/fisubr/fimul/fidiv/fidivr <i32>
  pop2   faddp fsubp fsubrp fmulp fdivp fdivrp     (st1 op= st0, then pop)
  unary  fsqrt fabs fchs frndint
  store  fstp <f64>   fstps <f32>   fistp <i32>    (all pop)
  misc   fxch

fsin/fcos/fpatan are deliberately ABSENT.  The exact-rational model cannot
represent them, and no chain marked `exact` needs them; see section 6(iii) of
the decision - whether Borland's sin() is even fsin-based is still open.
"""

import os
import re
import sys

SCHEDULE_TEXT = r"""
# ---------------------------------------------------------------------------
# THE chain.  NOCTIS-0.CPP:4078
#     nearstar_identity = star_x / 100000 * star_y / 100000 * star_z / 100000;
# Left-associative, every intermediate resident in st(0), one store at the end.
# ---------------------------------------------------------------------------
chain NsIdentity
  sid   1
  cw    133F
  exact
  in    int32 x, y, z
  out   f64   id
  const K100000 = int32 100000
  fild  x
  fidiv K100000
  fild  y
  fmulp
  fidiv K100000
  fild  z
  fmulp
  fidiv K100000
  fstp  id

# ---------------------------------------------------------------------------
# NEGATIVE CONTROL - one intermediate spilled to a double and reloaded.  This
# is the transcription error a port makes by accident.  Expected 3139/4194.
# ---------------------------------------------------------------------------
chain NsIdentitySpill
  sid   2
  cw    133F
  in    int32 x, y, z
  out   f64   id
  var   f64   mid
  const K100000 = int32 100000
  fild  x
  fidiv K100000
  fild  y
  fmulp
  fidiv K100000
  fstp  mid
  fld   mid
  fild  z
  fmulp
  fidiv K100000
  fstp  id

# ---------------------------------------------------------------------------
# NEGATIVE CONTROL - the isthere() LOOKUP formula, (x*is)*((y*is)*(z*is)) with
# is = the double nearest 1e-5.  Same mathematical value, different schedule
# and a different divisor representation.  Expected 0/4194.
# ---------------------------------------------------------------------------
chain NsIdentityIsThere
  sid   3
  cw    133F
  in    int32 x, y, z
  out   f64   id
  const KIS = f64 1e-05
  fild  x
  fmul  KIS
  fild  y
  fmul  KIS
  fild  z
  fmul  KIS
  fmulp
  fmulp
  fstp  id

# ---------------------------------------------------------------------------
# NEGATIVE CONTROL that MUST STILL PASS - operands permuted z,y,x.  Same value,
# same schedule shape.  Expected 4194/4194.  A test that fails this one is
# keying on operand order instead of on arithmetic.
# ---------------------------------------------------------------------------
chain NsIdentityPermuted
  sid   4
  cw    133F
  in    int32 x, y, z
  out   f64   id
  const K100000 = int32 100000
  fild  z
  fidiv K100000
  fild  y
  fmulp
  fidiv K100000
  fild  x
  fmulp
  fidiv K100000
  fstp  id

# ---------------------------------------------------------------------------
# NEGATIVE CONTROL - the same chain narrowed through a 32-bit float at the end.
# This is what F32Narrow does, applied where it does not belong.
# ---------------------------------------------------------------------------
chain NsIdentityF32
  sid   5
  cw    133F
  in    int32 x, y, z
  out   f64   id
  var   f32   nar
  const K100000 = int32 100000
  fild  x
  fidiv K100000
  fild  y
  fmulp
  fidiv K100000
  fild  z
  fmulp
  fidiv K100000
  fstps nar
  flds  nar
  fstp  id

# ---------------------------------------------------------------------------
# Level-2 SCALAR exercisers.  These are the shapes where the original also
# stored to a declared variable, so a per-operation routine is faithful.
# ---------------------------------------------------------------------------
chain ScalarAdd
  sid   10
  cw    133F
  in    f64 a, b
  out   f64 r
  fld   a
  fadd  b
  fstp  r

chain ScalarSub
  sid   11
  cw    133F
  in    f64 a, b
  out   f64 r
  fld   a
  fsub  b
  fstp  r

chain ScalarMul
  sid   12
  cw    133F
  in    f64 a, b
  out   f64 r
  fld   a
  fmul  b
  fstp  r

chain ScalarDiv
  sid   13
  cw    133F
  in    f64 a, b
  out   f64 r
  fld   a
  fdiv  b
  fstp  r

chain ScalarSqrt
  sid   14
  cw    133F
  in    f64 a
  out   f64 r
  fld   a
  fsqrt
  fstp  r

# A three-deep register chain with no store in the middle: (a+b)*(a-b).
# The point is that a backend which spills either half still gets the right
# answer most of the time, so this one is a WEAK test on purpose - it exists
# to show that only the identity chain has the resolving power.
chain ScalarDiffSq
  sid   15
  cw    133F
  in    f64 a, b
  out   f64 r
  fld   a
  fadd  b
  fld   a
  fsub  b
  fmulp
  fstp  r
"""

# ---------------------------------------------------------------------------

PUSH_I32 = {"fild"}
PUSH_F64 = {"fld"}
PUSH_F32 = {"flds"}
PUSH_NONE = {"fld1", "fldz", "fldst0"}
MEM_F64 = {"fadd", "fsub", "fsubr", "fmul", "fdiv", "fdivr"}
MEM_I32 = {"fiadd", "fisub", "fisubr", "fimul", "fidiv", "fidivr"}
POP2 = {"faddp", "fsubp", "fsubrp", "fmulp", "fdivp", "fdivrp"}
UNARY = {"fsqrt", "fabs", "fchs", "frndint"}
STORE_F64 = {"fstp"}
STORE_F32 = {"fstps"}
STORE_I32 = {"fistp"}
MISC = {"fxch"}

ALL_OPS = (PUSH_I32 | PUSH_F64 | PUSH_F32 | PUSH_NONE | MEM_F64 | MEM_I32
           | POP2 | UNARY | STORE_F64 | STORE_F32 | STORE_I32 | MISC)

NO_OPERAND = PUSH_NONE | POP2 | UNARY | MISC


class Chain(object):
    def __init__(self, name):
        self.name = name
        self.sid = None
        self.cw = 0x133F
        self.exact = False
        self.ins = []          # [(name, 'int32'|'f64'), ...] in declaration order
        self.out = None        # (name, type)
        self.vars = []         # [(name, type), ...]
        self.consts = []       # [(name, type, textvalue), ...]
        self.ops = []          # [(mnemonic, operand-or-None), ...]

    def types(self):
        t = {}
        for n, ty in self.ins:
            t[n] = ty
        for n, ty in self.vars:
            t[n] = ty
        for n, ty, _ in self.consts:
            t[n] = ty
        if self.out:
            t[self.out[0]] = self.out[1]
        return t

    def __repr__(self):
        return "<Chain %s sid=%d cw=%04X ops=%d%s>" % (
            self.name, self.sid, self.cw, len(self.ops),
            " EXACT" if self.exact else "")


def parse(text):
    """Parse schedule text into an ordered dict of Chain objects."""
    chains = {}
    cur = None
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split(None, 1)
        head = parts[0]
        rest = parts[1].strip() if len(parts) > 1 else ""

        if head == "chain":
            cur = Chain(rest)
            if cur.name in chains:
                raise ValueError("line %d: duplicate chain %s" % (lineno, rest))
            chains[cur.name] = cur
            continue
        if cur is None:
            raise ValueError("line %d: %r outside a chain" % (lineno, line))

        if head == "sid":
            cur.sid = int(rest, 0)
        elif head == "cw":
            cur.cw = int(rest, 16)
        elif head == "exact":
            cur.exact = True
        elif head in ("in", "var"):
            m = re.match(r"(int32|f64|f32)\s+(.*)$", rest)
            if not m:
                raise ValueError("line %d: bad %s decl %r" % (lineno, head, rest))
            ty = m.group(1)
            for nm in [s.strip() for s in m.group(2).split(",") if s.strip()]:
                (cur.ins if head == "in" else cur.vars).append((nm, ty))
        elif head == "out":
            m = re.match(r"(f64)\s+(\w+)$", rest)
            if not m:
                raise ValueError("line %d: bad out decl %r" % (lineno, rest))
            cur.out = (m.group(2), m.group(1))
        elif head == "const":
            m = re.match(r"(\w+)\s*=\s*(int32|f64)\s+(\S+)$", rest)
            if not m:
                raise ValueError("line %d: bad const %r" % (lineno, rest))
            cur.consts.append((m.group(1), m.group(2), m.group(3)))
        elif head in ALL_OPS:
            if head in NO_OPERAND:
                if rest:
                    raise ValueError("line %d: %s takes no operand" % (lineno, head))
                cur.ops.append((head, None))
            else:
                if not rest:
                    raise ValueError("line %d: %s needs an operand" % (lineno, head))
                cur.ops.append((head, rest))
        else:
            raise ValueError("line %d: unknown directive %r" % (lineno, head))

    for c in chains.values():
        if c.sid is None:
            raise ValueError("chain %s has no sid" % c.name)
        if c.out is None:
            raise ValueError("chain %s has no out" % c.name)
        t = c.types()
        for op, arg in c.ops:
            if arg is None:
                continue
            if arg not in t:
                raise ValueError("chain %s: %s references undeclared %r"
                                 % (c.name, op, arg))
            want = ("int32" if op in (PUSH_I32 | MEM_I32 | STORE_I32) else
                    "f32" if op in (PUSH_F32 | STORE_F32) else "f64")
            if t[arg] != want:
                raise ValueError("chain %s: %s %s is %s, wants %s"
                                 % (c.name, op, arg, t[arg], want))
    sids = {}
    for c in chains.values():
        if c.sid in sids:
            raise ValueError("sid %d used by %s and %s" % (c.sid, sids[c.sid], c.name))
        sids[c.sid] = c.name
    return chains


CHAINS = parse(SCHEDULE_TEXT)
BY_SID = {c.sid: c for c in CHAINS.values()}

OUTDIR = r"C:\programmieren\linoleum\work\w3i2"
SCHED_TXT = os.path.join(OUTDIR, "fpsched.txt")


def emit(path=SCHED_TXT):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="\n") as fh:
        fh.write(SCHEDULE_TEXT)
    return path


def main():
    p = emit()
    print("wrote %s" % p)
    for name, c in CHAINS.items():
        print("  %-22s sid=%-3d cw=%04X ops=%-3d in=%s out=%s%s"
              % (name, c.sid, c.cw, len(c.ops),
                 ",".join("%s:%s" % t for t in c.ins), c.out[0],
                 "  EXACT" if c.exact else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
