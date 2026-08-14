#!/usr/bin/env python3
"""genfp.py - turn x87 SCHEDULES into a L.in.oleum library.

    python genfp.py <schedule.txt> <out.txt> [--backend x87]

The schedule format is frozen in the Wave 3 architecture note and is read
independently by Implementer 2, on purpose: two independent readers of the
same spec catch an ambiguity that a shared parser would hide.

Why a generator at all, when the output is checked in?  Because the thing
being transcribed from NOCTIS.EXE is an instruction schedule, and a schedule
has to survive the trip from the disassembler to the binary without anybody
re-deriving what it computes.  Here the transcription IS the input file and
the emitter is a table lookup, so there is no step at which a spill can be
optimised away by accident.

BACKENDS.  --backend x87 emits the bytes literally.  --backend soft emits calls
into fpsoft's explicit 8-entry stack of 64-bit-mantissa values, and refuses
any mnemonic it has no primitive for.  --backend native is refused outright
for a chain marked `exact`: L.in.oleum's own float instructions narrow to 24
bits after every operation, so compiling an exact chain through them would
produce a plausible wrong answer, which is worse than an error.

    --only NAME[,NAME...]   emit just these chains
"""

import json
import re
import sys

# ---------------------------------------------------------------- opcodes
#
# modrm for [edi + disp32] is mod=10 rm=111, i.e. 0x87 | (reg << 3):
#     reg 0 -> 87   reg 1 -> 8F   reg 2 -> 97   reg 3 -> 9F
#     reg 4 -> A7   reg 5 -> AF   reg 6 -> B7   reg 7 -> BF

MEM = {
    # mnemonic : (escape byte, modrm byte, operand kind)
    'fild':   ('DB', '87', 'i32'),
    'fistp':  ('DB', '9F', 'i32'),
    'fist':   ('DB', '97', 'i32'),
    'fiadd':  ('DA', '87', 'i32'),
    'fimul':  ('DA', '8F', 'i32'),
    'fisub':  ('DA', 'A7', 'i32'),
    'fisubr': ('DA', 'AF', 'i32'),
    'fidiv':  ('DA', 'B7', 'i32'),
    'fidivr': ('DA', 'BF', 'i32'),

    'fld':    ('DD', '87', 'f64'),
    'fst':    ('DD', '97', 'f64'),
    'fstp':   ('DD', '9F', 'f64'),
    'fadd':   ('DC', '87', 'f64'),
    'fmul':   ('DC', '8F', 'f64'),
    'fsub':   ('DC', 'A7', 'f64'),
    'fsubr':  ('DC', 'AF', 'f64'),
    'fdiv':   ('DC', 'B7', 'f64'),
    'fdivr':  ('DC', 'BF', 'f64'),

    'fld32':  ('D9', '87', 'f32'),
    'fstp32': ('D9', '9F', 'f32'),
}

# No-operand forms.  The reversed-operand pairs are spelled out because
# getting one of them backwards produces a number, not a crash.
NOARG = {
    'faddp':  ('DE C1', 'faddp  st1,st0'),
    'fmulp':  ('DE C9', 'fmulp  st1,st0'),
    'fsubp':  ('DE E9', 'fsubp  st1,st0   st1 = st1 - st0'),
    'fsubrp': ('DE E1', 'fsubrp st1,st0   st1 = st0 - st1'),
    'fdivp':  ('DE F9', 'fdivp  st1,st0   st1 = st1 / st0'),
    'fdivrp': ('DE F1', 'fdivrp st1,st0   st1 = st0 / st1'),
    'fchs':   ('D9 E0', 'fchs'),
    'fabs':   ('D9 E1', 'fabs'),
    'fsqrt':  ('D9 FA', 'fsqrt'),
    'fsin':   ('D9 FE', 'fsin'),
    'fcos':   ('D9 FF', 'fcos'),
    'fpatan': ('D9 F3', 'fpatan'),
    'frndint':('D9 FC', 'frndint'),
    'fxch':   ('D9 C9', 'fxch st1'),
    'fld1':   ('D9 E8', 'fld1'),
    'fldz':   ('D9 EE', 'fldz'),
}

# L.in.oleum reserves these as compound-expression tags and rejects ANY
# symbol containing one as a substring, anywhere, case-insensitively.  The
# manual says so in one sentence in error_qr.htm and it is easy to miss:
# a routine called FDiv will not compile, and the message you get is
# "declaration error: illegal compound or symbol name" pointing at the
# label, which does not obviously mean "your name contains the word div".
# Checked here so a schedule that names a chain badly fails in Python with
# an explanation, rather than 200 lines later in the compiler.
LINO_RESERVED = ('plus', 'minus', 'relating', 'multiplied', 'mtp',
                 'divided', 'div')


def check_name(sym, what):
    low = sym.lower()
    for r in LINO_RESERVED:
        if r in low:
            raise SystemExit(
                'genfp: %s %r is not a legal L.in.oleum symbol: it contains '
                'the reserved compound tag %r. L.in.oleum rejects the word '
                'anywhere inside a name, spaces or not.' % (what, sym, r))
    if sym[:1].isdigit():
        raise SystemExit('genfp: %s %r may not start with a digit' % (what, sym))
    if not re.match(r'^[A-Za-z][A-Za-z0-9]*$', sym):
        raise SystemExit('genfp: %s %r has a character L.in.oleum will not '
                         'accept in a symbol' % (what, sym))


INT_SLOTS = ['FJ0', 'FJ1', 'FJ2', 'FJ3']
F64_SLOTS = ['FA0', 'FB0', 'FC0', 'FD0']

# how the x87 stack depth moves, so the generator can prove balance
PUSH = {'fild', 'fld', 'fld32', 'fld1', 'fldz'}
POP = {'fistp', 'fstp', 'fstp32', 'faddp', 'fmulp', 'fsubp', 'fsubrp',
       'fdivp', 'fdivrp', 'fpatan'}


class Chain:
    def __init__(self, name):
        self.name = name
        self.cw = None
        self.exact = False
        self.notes = []
        self.ints = []          # [(name, slot)]
        self.f64s = []
        self.out = None
        self.consts = []        # [(name, kind, value)]
        self.temps = []
        self.ops = []           # [(mnemonic, operand-or-None, srcline)]

    def resolve(self, chain_prefix):
        """name -> (lino symbol, kind).  Built once, used by the emitter."""
        env = {}
        for nm, slot in self.ints:
            env[nm] = (slot, 'i32')
        for nm, slot in self.f64s:
            env[nm] = (slot, 'f64')
        if self.out:
            env[self.out] = ('FA0', 'f64')
        for nm, kind, _ in self.consts:
            # an f64 lives in an adjacent PAIR and is addressed by its low
            # half, because that is where fld qword starts reading
            env[nm] = (chain_prefix + nm + ('0' if kind == 'f64' else ''), kind)
        for nm in self.temps:
            env[nm] = (chain_prefix + nm + '0', 'f64')
        return env


def strip_comments(text):
    """L.in.oleum comments are ( ... ) and they nest and span lines.

    Done character by character rather than with a regex: a regex that
    handles the single-line case silently eats the wrong thing when a
    comment wraps, and this file's whole job is to not silently eat things.
    Newlines are preserved so line numbers in errors stay true.
    """
    out = []
    depth = 0
    for c in text:
        if c == '(':
            depth += 1
            continue
        if c == ')':
            if depth:
                depth -= 1
                continue
        if depth:
            out.append('\n' if c == '\n' else ' ')
        else:
            out.append(c)
    if depth:
        raise SyntaxError('unterminated ( comment')
    return ''.join(out)


def parse(path):
    chains = []
    cur = None
    src = strip_comments(open(path, encoding='latin-1').read())
    for ln, raw in enumerate(src.split('\n'), 1):
        line = raw.strip()
        if not line:
            continue
        parts = line.split()
        key = parts[0]

        if key == 'chain':
            cur = Chain(parts[1])
            chains.append(cur)
            continue
        if cur is None:
            raise SyntaxError('%s:%d: directive outside a chain' % (path, ln))
        if key == 'end':
            cur = None
            continue
        if key == 'cw':
            cur.cw = int(parts[1], 16)
            continue
        if key == 'exact':
            cur.exact = True
            continue
        if key == 'note':
            cur.notes.append(' '.join(parts[1:]))
            continue
        if key == 'in':
            kind = parts[1]
            names = [n.strip(' ,') for n in ' '.join(parts[2:]).split(',')]
            names = [n for n in names if n]
            for n in names:
                if kind == 'int32':
                    if len(cur.ints) >= 4:
                        raise SyntaxError('%s:%d: more than 4 int inputs' % (path, ln))
                    cur.ints.append((n, INT_SLOTS[len(cur.ints)]))
                elif kind == 'f64':
                    if len(cur.f64s) >= 4:
                        raise SyntaxError('%s:%d: more than 4 f64 inputs' % (path, ln))
                    cur.f64s.append((n, F64_SLOTS[len(cur.f64s)]))
                else:
                    raise SyntaxError('%s:%d: unknown input kind %r' % (path, ln, kind))
            continue
        if key == 'out':
            if parts[1] != 'f64':
                raise SyntaxError('%s:%d: only f64 outputs' % (path, ln))
            cur.out = parts[2]
            continue
        if key == 'temp':
            cur.temps.append(parts[1])
            continue
        if key == 'const':
            # const NAME = kind value
            m = re.match(r'const\s+(\w+)\s*=\s*(\w+)\s+(\S+)', line)
            if not m:
                raise SyntaxError('%s:%d: bad const' % (path, ln))
            nm, kind, val = m.group(1), m.group(2), m.group(3)
            if kind == 'int32':
                cur.consts.append((nm, 'i32', int(val, 0)))
            elif kind == 'f64':
                if len(val) != 16:
                    raise SyntaxError('%s:%d: f64 const needs 16 hex digits' % (path, ln))
                cur.consts.append((nm, 'f64', int(val, 16)))
            else:
                raise SyntaxError('%s:%d: unknown const kind %r' % (path, ln, kind))
            continue

        # otherwise: an instruction
        if key in NOARG:
            if len(parts) != 1:
                raise SyntaxError('%s:%d: %s takes no operand' % (path, ln, key))
            cur.ops.append((key, None, ln))
        elif key in MEM:
            if len(parts) != 2:
                raise SyntaxError('%s:%d: %s takes one operand' % (path, ln, key))
            cur.ops.append((key, parts[1], ln))
        else:
            raise SyntaxError('%s:%d: unknown mnemonic %r' % (path, ln, key))
    return chains


def check(ch, env, path):
    """Static checks that catch a mistranscription before it becomes a number."""
    depth = 0
    peak = 0
    stores = 0
    for mn, op, ln in ch.ops:
        if mn in ('fistp', 'fist'):
            raise SyntaxError(
                '%s: chain %s line %d: bare %s is forbidden; integer '
                'conversion must be a hand-checked fragment that names its '
                'rounding-control bracket and live-value reading'
                % (path, ch.name, ln, mn))
        if op is not None:
            if op not in env:
                raise SyntaxError('%s: chain %s line %d: undeclared operand %r'
                                  % (path, ch.name, ln, op))
            want = MEM[mn][2]
            got = env[op][1]
            if want != got:
                raise SyntaxError('%s: chain %s line %d: %s wants %s, %r is %s'
                                  % (path, ch.name, ln, mn, want, op, got))
        if mn in PUSH:
            depth += 1
            peak = max(peak, depth)
        if mn in POP:
            depth -= 1
        if mn in ('fstp', 'fst', 'fistp', 'fist', 'fstp32'):
            stores += 1
        if depth < 0:
            raise SyntaxError('%s: chain %s line %d: x87 stack underflow'
                              % (path, ch.name, ln))
        if depth > 8:
            raise SyntaxError('%s: chain %s line %d: x87 stack overflow (>8)'
                              % (path, ch.name, ln))
    if depth != 0:
        raise SyntaxError('%s: chain %s: stack ends at depth %d, not 0'
                          % (path, ch.name, depth))
    if ch.out and stores == 0:
        raise SyntaxError('%s: chain %s: declares an output but never stores'
                          % (path, ch.name))
    return peak, stores


# --- the soft backend -------------------------------------------------
#
# fpsoft implements the x87 as an explicit 8-entry stack of 64-bit-mantissa
# values, so a schedule maps onto it one mnemonic at a time.  Only the
# mnemonics fpsoft actually HAS a primitive for are listed.  Anything else
# is REFUSED rather than approximated: a soft emitter that quietly turned
# an unsupported mnemonic into something structurally similar would produce
# a plausible wrong answer, and a plausible wrong answer is the failure mode
# this whole wave exists to avoid.
#
# XFiquo, not XFidiv: L.in.oleum rejects any symbol containing "div".
SOFT_INT = {'fild': 'XFild', 'fidiv': 'XFiquo'}
SOFT_NOARG = {'fmulp': 'XFmulp'}
SOFT_STORE = {'fstp': 'XFstpQ'}


def emit_soft(ch, env):
    out = ['\t=> XReset;']
    for mn, op, ln in ch.ops:
        if mn in SOFT_INT:
            sym, _ = env[op]
            out.append('\tA = [%s]; [XIN] = A;  => %s;\t(%s %s)'
                       % (sym, SOFT_INT[mn], mn, op))
        elif mn in SOFT_NOARG:
            out.append('\t=> %s;\t\t\t\t(%s)' % (SOFT_NOARG[mn], mn))
        elif mn in SOFT_STORE:
            sym, _ = env[op]
            if sym != 'FA0':
                raise SystemExit(
                    'genfp: the soft backend cannot store to %r. It has one '
                    'store primitive, XFstpQ, which stores the chain result '
                    'to FA. A schedule with a deliberate mid-chain spill is '
                    'not expressible on this backend and must not be faked.'
                    % op)
            out.append('\t=> %s;\t\t\t\t(%s %s)' % (SOFT_STORE[mn], mn, op))
        else:
            raise SystemExit(
                'genfp: the soft backend has no primitive for %r (chain %s, '
                'schedule line %d). fpsoft implements fild, fidiv, fmulp and '
                'fstp; extend fpsoft before extending this table.'
                % (mn, ch.name, ln))
    return out


def emit(chains, backend, sched_path):
    if backend not in ('x87', 'soft', 'native'):
        raise SystemExit('genfp: unknown backend %r' % backend)
    if backend == 'native':
        bad = [c.name for c in chains if c.exact]
        if bad:
            raise SystemExit(
                'genfp: the native backend is refused for exact-marked '
                'chains: %s\n'
                'L.in.oleum float instructions narrow to 24 bits after EVERY '
                'operation, so compiling an exact chain through them produces '
                'a plausible wrong answer, which is worse than an error.'
                % ', '.join(bad))

    out = []
    w = out.append
    w('      ( *** fpchains - GENERATED, do not edit ***')
    w('')
    w('\tgenerated by tools/genfp.py from %s' % sched_path)
    w('\tbackend: %s' % backend)
    w('')
    w('\tChecked in on purpose, so a reviewer reads bytes rather than a')
    w('\tgenerator.  Every routine below is ONE fragment: the intermediate')
    w('\tnever leaves the x87 register stack, which is the whole point.')
    w('\tA scalar route through fpx87 would store - and round - after each')
    w('\toperation, and one such store costs about a quarter of the')
    w('\tSTARMAP records.')
    w('')
    w('\tEach routine reads the fpabi slots named in its header and leaves')
    w('\tits result in FA0/FA1.  None of them touches A/B/C/D/E or edi.')
    w('\tNone of them sets the control word: call FEnter first. )')
    w('')

    # ---- variables period: constants and temps for every chain
    w('"variables"')
    w('')
    for ch in chains:
        pre = 'FK' + ch.name
        decls = []
        for nm, kind, val in ch.consts:
            if kind == 'i32':
                decls.append('\t%s%s\t= %d;' % (pre, nm, val))
            else:
                lo = val & 0xFFFFFFFF
                hi = (val >> 32) & 0xFFFFFFFF
                decls.append('\t%s%s0\t= %08Xh;\t( low half )' % (pre, nm, lo))
                decls.append('\t%s%s1\t= %08Xh;\t( high half; together %016X )'
                             % (pre, nm, hi, val))
        for nm in ch.temps:
            decls.append('\t%s%s0\t= 0;\t( spill slot, low half )' % (pre, nm))
            decls.append('\t%s%s1\t= 0;\t( spill slot, high half )' % (pre, nm))
        if decls:
            w('\t( %s )' % ch.name)
            out.extend(decls)
            w('')

    w('"programme"')
    w('')

    manifest = []
    for idx, ch in enumerate(chains, 1):
        check_name(ch.name, 'chain name')
        for nm, kind, _ in ch.consts:
            check_name('FK' + ch.name + nm, 'constant')
        for nm in ch.temps:
            check_name('FK' + ch.name + nm + '0', 'temp slot')
        env = ch.resolve('FK' + ch.name)
        peak, stores = check(ch, env, sched_path)
        w('( -------------------------------------------------------------------- )')
        w('')
        w('      ( %s' % ch.name)
        for n in ch.notes:
            w('\t%s' % n)
        w('')
        if ch.ints:
            w('\tint32 in : ' + ', '.join('%s=%s' % (n, s) for n, s in ch.ints))
        if ch.f64s:
            w('\tf64   in : ' + ', '.join('%s=%s' % (n, s) for n, s in ch.f64s))
        w('\tf64   out: %s = FA0/FA1' % ch.out)
        w('\tcontrol  : %04Xh' % ch.cw if ch.cw else '\tcontrol  : ambient')
        w('\texact    : %s' % ('YES' if ch.exact else 'no'))
        w('\tx87 depth: peak %d, stores %d' % (peak, stores))
        w('\tchain id : %d )' % idx)
        w('')
        w('"%s"' % ch.name)
        if backend == 'soft':
            for line in emit_soft(ch, env):
                w(line)
        else:
            w('\t{')
            for mn, op, ln in ch.ops:
                if op is None:
                    by, cmt = NOARG[mn]
                    w('\t    %-38s(%s)' % (by, cmt))
                else:
                    esc, modrm, kind = MEM[mn]
                    sym, _ = env[op]
                    ref = '%s %s <d%s mtp bytesperunit>' % (esc, modrm, sym)
                    w('\t    %-38s(%-7s %s)' % (ref, mn, op))
            w('\t}')
        w('\tend;')
        w('')
        manifest.append({
            'id': idx, 'name': ch.name, 'exact': ch.exact,
            'cw': ch.cw, 'peak': peak, 'stores': stores,
            'ints': [n for n, _ in ch.ints],
            'f64s': [n for n, _ in ch.f64s],
            'notes': ch.notes,
        })
    return '\n'.join(out) + '\n', manifest


def main():
    args = [a for a in sys.argv[1:]]
    backend = 'x87'
    only = None
    if '--backend' in args:
        i = args.index('--backend')
        backend = args[i + 1]
        del args[i:i + 2]
    if '--only' in args:
        i = args.index('--only')
        only = args[i + 1]
        del args[i:i + 2]
    if len(args) != 2:
        raise SystemExit(__doc__)
    sched, dest = args
    chains = parse(sched)
    if only:
        want = set(only.split(','))
        missing = want - set(c.name for c in chains)
        if missing:
            raise SystemExit('genfp: no such chain: %s' % ', '.join(missing))
        chains = [c for c in chains if c.name in want]
    text, manifest = emit(chains, backend, sched)
    open(dest, 'w', encoding='latin-1', newline='\n').write(text)
    open(dest.rsplit('.', 1)[0] + 'man.json', 'w').write(
        json.dumps(manifest, indent=2) + '\n')
    print('genfp: %d chains -> %s (%d bytes)' % (len(chains), dest, len(text)))
    for m in manifest:
        print('  %2d  %-24s exact=%-5s depth=%d stores=%d'
              % (m['id'], m['name'], m['exact'], m['peak'], m['stores']))


if __name__ == '__main__':
    main()
