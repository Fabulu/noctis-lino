"""w5audit.py -- Wave 5c.  The mechanical audit for checks that cannot fail.

    python tests/w5audit.py            the whole audit, standalone
    python tests/w5audit.py --findings just the analyser, over the whole tree
    python tests/w5audit.py --fingerprints   findings with the key to paste

It also runs inside tests/test_wave5.py, which is entry 17 of run_all.py, so
the suite fails when a tautological check is added.

WHY THIS FILE EXISTS
====================
Wave 5 shipped a canary in which both sides of every comparison held the same
literal.  Wave 5b was told to remove it, removed it, and then reproduced the
same defect three times over in noctis-harness/ -- once as a matrix that
reported the CLEAN build as a caught sabotage, once as a witness() returning
the very literal it was compared against, and once as a ring sweep that
recovers what it put in.  Wave 5c was told to state the rule.  The rule was
stated, in HARNESSAUDIT.md, in fb_ledger.py's docstring, and in fb_lint.py --
and the same wave that stated it shipped two more.

Stating a rule does not enforce it.  This file executes it.

THE CLASS
=========
A check that cannot fail: a comparison whose two sides are derived from the
same value, or from a stored artifact the code under test wrote.  Its record
is identical whether the mechanism works or is completely broken.  It reads
correct, reviews correct, and is worse than no check at all, because it
manufactures confidence.

THE ONE QUESTION
    "Could this record differ between a working mechanism and a broken one?"

THE MECHANISM -- WHY IT IS NOT ANOTHER fb_lint
==============================================
fb_lint.py is a NAME filter.  It looks for a local called `want` and a local
called `got` and asks whether the same function produced both.  Two checks that
are the same computation, differing only in that one calls its variables
`reference` and `subject`, are respectively caught and invisible.  That is
measured, in run_corpus() below: `LINT_BLIND` is the rename of `LINT_SEEN` and
fb_lint returns zero findings on it.  A defect detector that a rename defeats
is a detector nobody can rely on.

This audit never looks at a name.  It executes.

  1. INLINE.  Inside each function, every local that is assigned exactly once
     is substituted into the check's condition, transitively, and so are
     module-level integer constants and single-`return` module functions.  A
     `got` computed three statements above the comparison becomes part of the
     comparison's own expression tree.

  2. ATOMISE.  Whatever is left that the algebra cannot evaluate -- a call, an
     attribute, a subscript -- becomes an opaque ATOM keyed by its source text.
     Two occurrences of `filter_one(data)` are therefore ONE atom and take ONE
     value.  This is what makes "both sides came from the same producer" a
     measurement rather than a guess about variable naming.

  3. EXECUTE.  The condition is evaluated over several hundred random
     assignments of its atoms, drawn from a spread that deliberately includes
     every integer literal appearing in the condition itself, +-1 -- so a guard
     like `if bpp != 8` is sampled AT 8 and is not mistaken for a tautology.

     RULE A -- the condition is TRUE under every assignment.  It cannot fail.
     RULE B -- one side of a comparison is DERIVED from the other (its atom set
               strictly contains the other's), and the predicate's truth never
               changes when the atoms that are NOT shared vary.  Those atoms
               are the sweep: the axis the check claims to cover and does not.
     RULE C -- a TALLY (`if <pred>: fails += 1`) whose predicate is FALSE under
               every assignment.  "0 of 65,536" then means nothing, because it
               is 0 of 65,536 for a broken mechanism too.  Rule C exists
               because rule B is evaded by spelling the truth as a literal
               instead of as a variable the other side shares; the two together
               close the counting idiom.

Rule B is the shape that killed Wave 5b's third instance and that no name-based
lint can see, because the two sides are spelled `got` and `want` and really are
different expressions -- they are just not independent.

WHAT IT CANNOT DO, PLAINLY
==========================
  * It reads PYTHON.  fb_ref.c is 2,622 lines of C and is NOT analysed here.
    Its void checks have to be found by the C sabotage battery, and one is open
    at the time of writing (HARNESSAUDIT.md, E1).
  * An atom is opaque, so a check whose sides are two DIFFERENT calls that
    happen to compute the same thing reads as sound.  Rule B catches derivation
    through visible arithmetic, not through a shared implementation two modules
    away.  That is what fb_ledger.py's owner rule is for.
  * The domain is unmodelled: atoms are drawn from a spread, not from the values
    the program can actually produce.  This causes false positives, and the only
    admissible answer to one is a DEMONSTRATION -- see DISPOSITIONS.

DISPOSITIONS, AND WHY THERE IS NO "IGNORE"
==========================================
Every finding must be dispositioned, and there are exactly two dispositions:

  REFUTED  the analyser is wrong about this site, and here is a callable that
           RUNS every time the audit runs and produces BOTH outcomes from the
           real code.  If the demonstration stops discriminating, the audit
           fails.  A refutation is an experiment, not an assertion.

  OPEN     the analyser is right: the check is void.  The entry names the file
           that owns it and why it is not fixed here.  The audit asserts the
           finding is STILL PRESENT and fails if it silently disappears -- so a
           fix has to come with the entry's deletion -- and the number of OPEN
           entries is pinned.  A new one fails the run.

There is no third disposition and no suppression list.  A finding in tests/ --
this file's own territory -- cannot be OPEN at all; it is a hard failure, which
is why the four this analyser found in tests/ on its first run were deleted
rather than recorded (HARNESSAUDIT.md section 8).

THE TIER PIN
============
A claim about how strongly something is graded is a claim like any other, and
three of them are recomputed here from fb_ledger's entries on every run:

  * the T0/T1/T2/T3 prefix of every check id, against that row's own owners;
  * fb_compare.TIER_TABLE, whose two-implementation rows must have a supporting
    GRADED row with two DISTINCT non-`external` owners;
  * TIER_CLAIMS below -- fourteen sentences quoted VERBATIM out of
    tests/test_wave5.py, HARNESSAUDIT.md and LINOBUF.md, each naming the ledger
    rows it rests on.  The quote must still be in the file, the level must be
    what those rows support, and a stated producer COUNT must equal the
    recomputed one.  Any line in the four scanned files that names a level and
    is registered nowhere fails the run.

AND ALL OF IT IS PROVED BREAKABLE BY BREAKING IT
================================================
Every gate takes its inputs as arguments so self_falsification() can feed each
one a broken input and require the complaint.  Nine of this module's checks are
that battery, including the audit turned on itself: remove `!=` from the algebra
and the ring-sweep corpus entry stops being detected.

The sampler assigns values by SORTED atom key.  That is not a stylistic choice:
Python randomises string hashing per process, and before it was sorted two runs
of the same tree disagreed on the finding count.  A ratchet that reports a
different number every run is not a ratchet.
"""

import ast
import hashlib
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HARNESS = os.path.join(ROOT, "noctis-harness")
DOCS = os.path.join(ROOT, "docs-notes")


# =====================================================================
# 1.  The algebra.  Integers, the operators a buffer model uses, and
#     opaque atoms.  Anything else raises and the site is skipped.
# =====================================================================

class Unsupported(Exception):
    pass


def _fdiv(a, b):
    return a // b if b else None


def _mod(a, b):
    return a % b if b else None


def _shl(a, b):
    return a << b if 0 <= b < 96 else None


def _shr(a, b):
    return a >> b if 0 <= b < 96 else None


BINOPS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.FloorDiv: _fdiv,
    ast.Mod: _mod,
    ast.BitAnd: lambda a, b: a & b,
    ast.BitOr: lambda a, b: a | b,
    ast.BitXor: lambda a, b: a ^ b,
    ast.LShift: _shl,
    ast.RShift: _shr,
}

CMPOPS = {
    ast.Eq: lambda a, b: a == b,
    ast.NotEq: lambda a, b: a != b,
    ast.Lt: lambda a, b: a < b,
    ast.LtE: lambda a, b: a <= b,
    ast.Gt: lambda a, b: a > b,
    ast.GtE: lambda a, b: a >= b,
}


def atom_key(node):
    try:
        return ast.unparse(node)
    except Exception:
        raise Unsupported("unparse")


def evaluate(node, env):
    """Value of `node` under `env` (atom text -> int).  Unsupported means the
    site is outside the algebra and is not judged at all."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            return node.value
        if isinstance(node.value, int):
            return node.value
        raise Unsupported("non-integer constant")
    if isinstance(node, ast.BinOp):
        f = BINOPS.get(type(node.op))
        if f is None:
            raise Unsupported("binop")
        r = f(evaluate(node.left, env), evaluate(node.right, env))
        if r is None:
            raise Unsupported("domain")
        return r
    if isinstance(node, ast.UnaryOp):
        v = evaluate(node.operand, env)
        if isinstance(node.op, ast.USub):
            return -v
        if isinstance(node.op, ast.UAdd):
            return v
        if isinstance(node.op, ast.Invert):
            return ~v
        if isinstance(node.op, ast.Not):
            return not v
        raise Unsupported("unaryop")
    if isinstance(node, ast.Compare):
        if len(node.ops) != 1:
            raise Unsupported("chained comparison")
        f = CMPOPS.get(type(node.ops[0]))
        if f is None:
            raise Unsupported("comparison operator")
        return f(evaluate(node.left, env), evaluate(node.comparators[0], env))
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            r = True
            for v in node.values:
                r = r and evaluate(v, env)
            return r
        r = False
        for v in node.values:
            r = r or evaluate(v, env)
        return r
    if isinstance(node, ast.IfExp):
        return evaluate(node.body, env) if evaluate(node.test, env) \
            else evaluate(node.orelse, env)
    key = atom_key(node)
    if key not in env:
        raise Unsupported("unbound atom")
    return env[key]


def atoms_of(node, out):
    if isinstance(node, ast.Constant):
        return
    if isinstance(node, (ast.BinOp, ast.UnaryOp, ast.Compare, ast.BoolOp, ast.IfExp)):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.expr):
                atoms_of(child, out)
        return
    try:
        out.add(atom_key(node))
    except Unsupported:
        pass


# =====================================================================
# 2.  Inlining.  This is the step that makes the analysis independent
#     of what the author called the two sides.
# =====================================================================

class _Subst(ast.NodeTransformer):
    def __init__(self, sub):
        self.sub = sub

    def visit_Name(self, node):
        return self.sub.get(node.id, node)


def _subst(expr, sub):
    import copy
    return _Subst(sub).visit(copy.deepcopy(expr))


def _clone_with(node, fn):
    kw = {}
    for field in node._fields:
        v = getattr(node, field)
        if isinstance(v, list):
            kw[field] = [fn(x) if isinstance(x, ast.expr) else x for x in v]
        elif isinstance(v, ast.expr):
            kw[field] = fn(v)
        else:
            kw[field] = v
    return type(node)(**kw)


class Inliner(object):
    """Substitutes single-assignment locals, module constants and single-return
    module functions into an expression.  Bounded, and cycle-safe."""

    def __init__(self, defs, funcs, budget=600):
        self.defs = defs
        self.funcs = funcs
        self.budget = budget
        self.spent = 0

    def run(self, node, seen=()):
        self.spent += 1
        if self.spent > self.budget:
            raise Unsupported("inline budget")
        if isinstance(node, ast.Name):
            d = self.defs.get(node.id)
            if d is not None and node.id not in seen:
                return self.run(d, seen + (node.id,))
            return node
        if isinstance(node, ast.Call):
            f = node.func
            name = f.id if isinstance(f, ast.Name) else None
            sig = self.funcs.get(name)
            if sig is not None and name not in seen and not node.keywords:
                params, body = sig
                if len(params) == len(node.args):
                    sub = dict(zip(params, [self.run(a, seen) for a in node.args]))
                    return self.run(_subst(body, sub), seen + (name,))
            return ast.copy_location(
                ast.Call(func=node.func,
                         args=[self.run(a, seen) for a in node.args],
                         keywords=node.keywords), node)
        if isinstance(node, (ast.BinOp, ast.UnaryOp, ast.Compare, ast.BoolOp, ast.IfExp)):
            return ast.copy_location(_clone_with(node, lambda ch: self.run(ch, seen)), node)
        return node


def single_return_funcs(tree):
    out = {}
    for fn in [n for n in tree.body if isinstance(n, ast.FunctionDef)]:
        body = [s for s in fn.body
                if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))]
        if len(body) != 1 or not isinstance(body[0], ast.Return) or body[0].value is None:
            continue
        a = fn.args
        if a.posonlyargs or a.vararg or a.kwarg or a.kwonlyargs:
            continue
        out[fn.name] = ([p.arg for p in a.args], body[0].value)
    return out


def module_consts(tree):
    out = {}
    for s in tree.body:
        if isinstance(s, ast.Assign) and len(s.targets) == 1 and \
                isinstance(s.targets[0], ast.Name) and \
                isinstance(s.value, (ast.Constant, ast.BinOp, ast.UnaryOp)):
            out[s.targets[0].id] = s.value
    return out


def local_defs(fn):
    """name -> expression, for locals that are assigned once (or always
    identically) and are never augmented, never a loop target, never global.
    Anything else is left as an atom, which is the conservative direction."""
    exprs, banned = {}, set()
    for sub in ast.walk(fn):
        if isinstance(sub, ast.Assign):
            for t in sub.targets:
                if isinstance(t, ast.Name):
                    dumped = ast.dump(sub.value)
                    prev = exprs.get(t.id)
                    if prev is not None and prev[0] != dumped:
                        banned.add(t.id)
                    exprs[t.id] = (dumped, sub.value)
                else:
                    for n in ast.walk(t):
                        if isinstance(n, ast.Name):
                            banned.add(n.id)
        elif isinstance(sub, ast.AugAssign):
            for n in ast.walk(sub.target):
                if isinstance(n, ast.Name):
                    banned.add(n.id)
        elif isinstance(sub, (ast.For, ast.AsyncFor)):
            for n in ast.walk(sub.target):
                if isinstance(n, ast.Name):
                    banned.add(n.id)
        elif isinstance(sub, (ast.Global, ast.Nonlocal)):
            banned.update(sub.names)
        elif isinstance(sub, ast.NamedExpr) and isinstance(sub.target, ast.Name):
            banned.add(sub.target.id)
    return dict((k, v[1]) for k, v in exprs.items() if k not in banned)


# =====================================================================
# 3.  Judgement positions and the two rules.
# =====================================================================

CHECK_CALLS = ("req", "rec", "sreq", "assert_", "expect", "ok", "eq")

SPREAD = [0, 1, 2, 3, 7, 8, 63, 64, 255, 256, 320, 360, 400, 64000, 65535,
          65536, 0xFFFFFFFF, 0x100000000, 0x7FFFFFFF, -1, -320, 8999, 402196]


def _is_tally(stmts):
    """A tally is `fails += 1`, `bad.append(...)`, `flag = False`, `return
    False`.  An `if` whose body is a tally is COUNTING CASES, which is a
    judgement; an `if` that raises or returns a parsed value is a guard, and
    guards are not judged here."""
    if not stmts:
        return False
    for s in stmts:
        if isinstance(s, ast.AugAssign):
            continue
        if isinstance(s, ast.Expr) and isinstance(s.value, ast.Call):
            f = s.value.func
            if isinstance(f, ast.Attribute) and f.attr in ("append", "add", "update"):
                continue
            return False
        if isinstance(s, ast.Return) and isinstance(s.value, ast.Constant) and \
                isinstance(s.value.value, bool):
            continue
        if isinstance(s, ast.Assign) and len(s.targets) == 1 and \
                isinstance(s.targets[0], ast.Name) and isinstance(s.value, ast.Constant):
            continue
        return False
    return True


def judgement_exprs(fn):
    out = []
    for sub in ast.walk(fn):
        if isinstance(sub, ast.Call):
            f = sub.func
            name = f.id if isinstance(f, ast.Name) else \
                (f.attr if isinstance(f, ast.Attribute) else None)
            if name in CHECK_CALLS:
                for a in sub.args:
                    out.append(("call:%s" % name, sub, a))
        elif isinstance(sub, ast.Assert):
            out.append(("assert", sub, sub.test))
        elif isinstance(sub, ast.If):
            if _is_tally(sub.body) and not sub.orelse:
                out.append(("tally", sub, sub.test))
    return out


def const_pool(node):
    """Every integer literal in the condition, and its neighbours.  Sampling AT
    the values the condition talks about is what stops a format guard reading as
    a tautology."""
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Constant) and isinstance(n.value, int) and \
                not isinstance(n.value, bool):
            out.update((n.value, n.value + 1, n.value - 1))
    return sorted(out)


def sample_env(keys, rnd, pool):
    # SORTED, always.  `keys` is a set of strings and Python randomises string
    # hashing per process, so iterating it unsorted made the whole audit
    # non-reproducible: two runs of the same tree disagreed on whether a
    # borderline condition had ever come out false.  A ratchet that reports a
    # different number every run is not a ratchet.
    env = {}
    for k in sorted(keys):
        r = rnd.random()
        if pool and r < 0.40:
            env[k] = rnd.choice(pool)
        elif r < 0.70:
            env[k] = rnd.choice(SPREAD)
        else:
            env[k] = rnd.randrange(-(1 << 20), 1 << 34)
    return env


def truth_profile(expr, keys, rnd, pool, n):
    """The set of truth values the condition takes.  None if it left the
    algebra, in which case nothing is claimed about the site at all."""
    if not keys:
        try:
            return set([bool(evaluate(expr, {}))])
        except Exception:
            return None
    vals = set()
    for _ in range(n):
        try:
            vals.add(bool(evaluate(expr, sample_env(keys, rnd, pool))))
        except Exception:
            return None
        if len(vals) > 1:
            return vals
    return vals


class Finding(object):
    __slots__ = ("rule", "path", "line", "func", "where", "detail", "text", "key")

    def __init__(self, rule, path, line, func, where, detail, text):
        self.rule = rule
        self.path = path
        self.line = line
        self.func = func
        self.where = where
        self.detail = detail
        self.text = text
        self.key = fingerprint(rule, os.path.basename(path), func, text)

    def __repr__(self):
        return "%s %s:%d %s()  %s" % (self.rule, os.path.basename(self.path),
                                      self.line, self.func, self.text)


def fingerprint(rule, base, func, text):
    """Stable across line-number drift and reformatting of anything but the
    condition itself.  A disposition keyed by this cannot silently transfer to
    a different check."""
    h = hashlib.sha1(("%s|%s|%s|%s" % (rule, base, func, text)).encode("utf-8"))
    return h.hexdigest()[:12]


def analyze_source(src, path="<str>", samples=300, seed=20260806):
    tree = ast.parse(src)
    consts = module_consts(tree)
    funcs = single_return_funcs(tree)
    out = []
    for fn in [n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        defs = dict(consts)
        defs.update(local_defs(fn))
        for where, node, expr in judgement_exprs(fn):
            rnd = random.Random(seed)
            try:
                inl = Inliner(defs, funcs).run(expr)
            except Unsupported:
                continue
            keys = set()
            atoms_of(inl, keys)
            pool = const_pool(inl)
            prof = truth_profile(inl, keys, rnd, pool, samples)
            if prof is None:
                continue
            text = ast.unparse(expr)
            if prof == set([True]):
                out.append(Finding(
                    "A", path, node.lineno, fn.name, where,
                    "TRUE under every one of %d assignments of %d atom(s)%s -- it "
                    "cannot fail" % (samples, len(keys),
                                     (": " + ", ".join(sorted(keys)[:4])) if keys else
                                     " (the condition is a constant)"),
                    text))
                continue
            if where == "tally" and prof == set([False]):
                # RULE C -- the counting idiom.  `if <pred>: fails += 1` inside a
                # sweep, where <pred> is FALSE under every assignment, is a
                # sweep that can never register a case.  It reports "0 of N" for
                # a working mechanism and "0 of N" for a broken one.  Only a
                # tally is judged this way: an equality between two opaque calls
                # is naturally false under random atoms, and that is a check, not
                # a defect.
                out.append(Finding(
                    "C", path, node.lineno, fn.name, where,
                    "FALSE under every one of %d assignments of %d atom(s)%s -- "
                    "the sweep counts a constant, so `0 failures` is not a result"
                    % (samples, len(keys),
                       (": " + ", ".join(sorted(keys)[:4])) if keys else
                       " (the condition is a constant)"),
                    text))
                continue
            if not (isinstance(expr, ast.Compare) and len(expr.ops) == 1):
                continue
            try:
                left = Inliner(defs, funcs).run(expr.left)
                right = Inliner(defs, funcs).run(expr.comparators[0])
            except Unsupported:
                continue
            la, ra = set(), set()
            atoms_of(left, la)
            atoms_of(right, ra)
            for big, small, side in ((la, ra, "left"), (ra, la, "right")):
                if not small or not (small < big):
                    continue
                witness = big - small
                rnd2 = random.Random(seed + 7)
                dead = True
                for _ in range(40):
                    base = sample_env(big | small, rnd2, pool)
                    vals = set()
                    for _ in range(24):
                        env = dict(base)
                        env.update(sample_env(witness, rnd2, pool))
                        try:
                            vals.add(bool(evaluate(inl, env)))
                        except Exception:
                            dead = False
                            break
                    if len(vals) > 1 or not dead:
                        dead = False
                        break
                if dead:
                    out.append(Finding(
                        "B", path, node.lineno, fn.name, where,
                        "the %s side is DERIVED from the other (it contains %s), and the "
                        "predicate's value never changes when %s vary -- the axis this "
                        "check sweeps carries no information"
                        % (side, ", ".join(sorted(small)[:3]),
                           ", ".join(sorted(witness)[:4])),
                        text))
                    break
    return out


def analyze_file(path, **kw):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return analyze_source(fh.read(), path, **kw)


# =====================================================================
# 4.  The analyser's own grade.  It has to catch, and it has to not
#     flag sound work, and both halves are executed here.
# =====================================================================

# Every void snippet is a shape this project actually shipped.
VOID_CORPUS = {
    "kind6_canary": ('''
CANARY = 0xA5A5A5A5
def check(req, can):
    """WAVE 5.  Both fields written by construction, then compared."""
    expected = CANARY
    actual = CANARY
    req(expected == actual, "the canary survived the walker")
''', "the rejected Wave 5 canary: one literal, twice"),

    "ring_sweep": ('''
M32 = 0xFFFFFFFF
def sweep(cpms, lengths, origins, stride):
    """WAVE 5b instance 3, verbatim.  `got` recovers what `start` hid."""
    out = []
    for L in lengths:
        want = cpms * L
        fails = 0
        for i in range(origins):
            end = (i * stride) & M32
            start = (end - want) & M32
            got = (end - start) & M32
            if got != want:
                fails += 1
        out.append(fails)
    return out
''', "instance 3: the 65,536-origin sweep whose origins do not matter"),

    "ring_sweep_renamed": ('''
MASK = 0xFFFFFFFF
def sweep(rate, spans, phases, step):
    """The SAME computation with every name changed.  fb_lint sees nothing."""
    out = []
    for span in spans:
        reference = rate * span
        tally = 0
        for phase in range(phases):
            tail = (phase * step) & MASK
            head = (tail - reference) & MASK
            subject = (tail - head) & MASK
            if subject != reference:
                tally += 1
        out.append(tally)
    return out
''', "instance 3 renamed: proof the audit is not a name filter"),

    "witness_literal": ('''
def witness(i):
    return 0xC0DE0000 | i
def check(req, can):
    """WAVE 5b instance 2.  The canary reads back the literal it wrote."""
    req(witness(0) == 0xC0DE0000, "the dirty read is READ BACK, not written")
''', "instance 2: a witness compared against its own literal"),

    "same_producer": ('''
def check(req, filter_one, data):
    """fb_ref.c:947.  Both sides built with the function under test."""
    want = filter_one(data)
    got = filter_one(data)
    req(want == got, "the filter agrees with itself")
''', "one producer, invoked twice"),

    "same_producer_renamed": ('''
def check(req, filter_one, data):
    """The same, with the names a reviewer looks for removed."""
    reference = filter_one(data)
    subject = filter_one(data)
    req(reference == subject, "the filter agrees with itself")
''', "one producer renamed: fb_lint returns zero findings on this"),

    "literal_true": ('''
def check(req, census):
    """fb_stick.py:352.  A print statement wearing a check's clothes."""
    req(True, "A2 escape corpus: %d cases enumerated" % census)
''', "an unconditional pass"),

    "or_true": ('''
def check(req, m, n):
    """fb_wrap.py:416.  The disjunction cannot be false."""
    req(m != n or True, "W6 the two multipliers differ")
''', "a disjunction with a true arm"),

    "constant_arithmetic": ('''
def check(req):
    """Two literals compared.  True before the program was written."""
    naive = 9000 * 552086
    req(naive > (1 << 31), "the overflow is real")
''', "an inequality between two compile-time constants"),

    "dead_sweep": ('''
M32 = 0xFFFFFFFF
def sweep(origins, stride):
    """The counting idiom with the truth spelled as a LITERAL instead of a
    shared variable, which is how rule B is evaded.  Reports 0 of 65,536 for a
    working mechanism and 0 of 65,536 for a broken one."""
    lost = 0
    for i in range(origins):
        seed = (i * stride) & M32
        hidden = (seed - 4096) & M32
        back = (seed - hidden) & M32
        if back != 4096:
            lost += 1
    return lost
''', "a sweep whose predicate is false for every case it enumerates"),

    "recovered_offset": ('''
BASE = 402196
def check(req, alloc, size):
    """A round trip through a reversible transform, swept over `alloc`."""
    off = (alloc + BASE) - size
    back = (off + size) - BASE
    if back != alloc:
        return False
    return True
''', "a reversible transform checked against its own input"),
}

# Sound snippets.  A detector that flags these is a detector nobody keeps.
SOUND_CORPUS = {
    "two_parses": ('''
def check(req, parse_a, parse_b, text):
    want = parse_a(text)
    got = parse_b(text)
    req(want == got, "layout order, two independent parses")
''', "two structurally different producers"),

    "mask_vs_truth": ('''
def check(req, mask32, cpms, ms, measured):
    """The subject is masked and the truth is an INDEPENDENT input."""
    got = mask32(measured)
    req(got == cpms * ms, "the recovered window equals the unbounded truth")
''', "a lossy subject against an independently produced truth"),

    "format_guard": ('''
def read(bpp, planes, depth):
    if bpp != 8 or planes != 1:
        return False
    if depth != 8:
        return False
    return True
''', "a guard comparing parsed fields against format constants"),

    "bounded_property": ('''
def check(req, lo, hi, n):
    req(lo <= n <= hi or n == 0, "n is inside the window")
''', "a real interval predicate"),

    "cross_owner": ('''
def check(req, lino_records, c_records):
    for a, b in zip(lino_records, c_records):
        if a != b:
            return False
    return True
''', "two producers compared element by element"),

    "difference_of_sets": ('''
def check(req, clean_passes, sabotage_fails):
    caught = clean_passes & sabotage_fails
    req(bool(caught), "the sabotage failed a record the clean build passes")
''', "the differential criterion a sabotage matrix needs"),
}


def run_corpus(samples=300):
    """(ok, detail).  Executed on every run: a detector that cannot be shown to
    catch is the same class of defect it exists to find."""
    caught, missed, false_pos = [], [], []
    for name in sorted(VOID_CORPUS):
        src, why = VOID_CORPUS[name]
        hits = analyze_source(src, "<corpus:%s>" % name, samples=samples)
        (caught if hits else missed).append((name, why, hits))
    for name in sorted(SOUND_CORPUS):
        src, why = SOUND_CORPUS[name]
        hits = analyze_source(src, "<corpus:%s>" % name, samples=samples)
        if hits:
            false_pos.append((name, why, hits))
    ok = not missed and not false_pos
    rules = {}
    for name, _why, hits in caught:
        for h in hits:
            rules.setdefault(h.rule, []).append(name)
    return ok, {"caught": caught, "missed": missed, "false_positives": false_pos,
                "n_void": len(VOID_CORPUS), "n_sound": len(SOUND_CORPUS),
                "rules": rules}


def lint_blindness():
    """The measurement that says why this file exists rather than another rule
    in fb_lint.py.  Returns (ok, detail): fb_lint must catch the named shape and
    MISS its rename, and this audit must catch both."""
    try:
        sys.path.insert(0, HARNESS)
        import fb_lint
    except Exception as exc:                                  # pragma: no cover
        return None, "fb_lint.py could not be imported: %s" % exc
    pairs = [("same_producer", "same_producer_renamed"),
             ("ring_sweep", "ring_sweep_renamed")]
    rows = []
    ok = True
    for seen, blind in pairs:
        a = fb_lint.lint_source(VOID_CORPUS[seen][0])
        b = fb_lint.lint_source(VOID_CORPUS[blind][0])
        mine_a = analyze_source(VOID_CORPUS[seen][0], "<a>")
        mine_b = analyze_source(VOID_CORPUS[blind][0], "<b>")
        rows.append("%s: fb_lint %d finding(s), renamed %d; this audit %d and %d"
                    % (seen, len(a), len(b), len(mine_a), len(mine_b)))
        if not (len(b) == 0 and mine_b):
            ok = False
    return ok, "; ".join(rows)


# =====================================================================
# 5.  Dispositions.  REFUTED carries an experiment; OPEN carries an
#     owner and is pinned.
# =====================================================================

class Disposition(object):
    __slots__ = ("kind", "owner", "why", "demo")

    def __init__(self, kind, owner, why, demo=None):
        self.kind = kind
        self.owner = owner
        self.why = why
        self.demo = demo


def _demo_stateless_grader():
    """tests/test_wave5.py's `after == base`.  Both sides call grade() on the
    same bytes, so the analyser folds them to one atom.  What the check asserts
    is that grade() is a PURE function -- that the thirty-odd grades run in
    between left no state.  Demonstrated on a stand-in: a stateful grader makes
    the identical comparison read False."""
    def stateful():
        calls = []

        def grade(_blob):
            calls.append(1)
            return [("R", len(calls) == 1, "")]
        base = dict((n, ok) for n, ok, _ in grade(b"x"))
        after = dict((n, ok) for n, ok, _ in grade(b"x"))
        return after == base

    def pure():
        def grade(blob):
            return [("R", len(blob) == 1, "")]
        base = dict((n, ok) for n, ok, _ in grade(b"x"))
        after = dict((n, ok) for n, ok, _ in grade(b"x"))
        return after == base

    return (pure() and not stateful(),
            "pure grader -> %s, stateful grader -> %s" % (pure(), stateful()))


def _demo_ring_sweep_is_void():
    """fb_tick.py's ring sweep, measured rather than argued.  For every window
    length the 65,536 origins produce ONE outcome, and `got` equals `want & M32`
    at every one of them.  This is the OPEN entry's evidence, recomputed."""
    sys.path.insert(0, HARNESS)
    import fb_tick
    m32 = fb_tick.M32
    rows, exceptions = [], 0
    for L in (500, 60000, 470000, 500000):
        want = 8999 * L
        outcomes = set()
        for i in range(0, 65536, 7):
            end = (i * 65537) & m32
            start = (end - want) & m32
            got = (end - start) & m32
            outcomes.add(got != want)
            if got != (want & m32):
                exceptions += 1
        rows.append("%d ms: %d distinct outcome(s) over the origin axis"
                    % (L, len(outcomes)))
    return (all(r.split(": ")[1].startswith("1 ") for r in rows) and exceptions == 0,
            "%s; got == want & M32 in every sampled case (%d exceptions)"
            % ("; ".join(rows), exceptions))


DISPOSITIONS = {
    # ---- REFUTED: the analyser is wrong, and here is the experiment. -----
    "29bb3f13140a": Disposition(
        "REFUTED", "tests/test_wave5.py",
        "sensitivity(): `after == base`.  The two sides ARE one atom -- both "
        "are grade(blob) on the same bytes -- and the analyser is right about "
        "that.  What the check asserts is that grade() is PURE across the "
        "thirty-odd perturbation grades run between them, which is a real "
        "property with a real failure mode.  The demonstration builds a "
        "stateful grader and shows the identical comparison reading False.",
        _demo_stateless_grader),

    # ---- OPEN: the analyser is right.  Owner named, presence asserted. ---
    "888189881a7e": Disposition(
        "OPEN", "noctis-harness/fb_tick.py",
        "ring_sweep, Wave 5b instance 3, REFOUND.  The docstring was rewritten "
        "and the predicate was not: `got` is `want & M32` at every origin, so "
        "`got != want` is `want > M32` -- and 589,824 'cases' are nine "
        "inequalities between a product and 2^32-1.  The LENGTH axis is real; "
        "the ORIGIN axis carries nothing.  Owned by implementer 1.",
        _demo_ring_sweep_is_void),
    "e6c82ffa096b": Disposition(
        "OPEN", "noctis-harness/fb_stick.py",
        "req(True, ...) at fb_stick.py:352 AND :360 -- both sites have the "
        "identical condition in the identical function, so one fingerprint "
        "covers them.  A corpus census and recon B's 0.22%% printed through "
        "the check channel.  fb_lint.py reports both and exits PASS anyway, "
        "because fb_lint's verdict is its own corpus, not the tree it scanned."),
    "73226b9bcb91": Disposition(
        "OPEN", "noctis-harness/fb_wrap.py",
        "req(m != n or True, ...) at fb_wrap.py:416.  The `or True` is there "
        "so a note about the offset-4 witness could be printed as a check."),
    "58c3d8da1e13": Disposition(
        "OPEN", "noctis-harness/fb_tick.py",
        "req(naive > (1 << 31), ...) at fb_tick.py:941 compares two compile-"
        "time constants (9000 * 552086 against 2^31).  By fb_ledger's own "
        "vocabulary that is a PIN, not a GRADED row, and it is counted in the "
        "passing total."),
}

# The ratchet.  This many OPEN fingerprints existed when the audit was written;
# the number may fall and may never rise.  Raising it is a source change in
# front of a reviewer, which is the entire point.
OPEN_BUDGET = 4


# =====================================================================
# 6.  The ledger gate.  fb_ledger validates its own shape; this checks
#     the two things a hand-forged row walks straight through.
# =====================================================================

def _tree_text():
    """Every source in the tree except the ledger itself.  A falsifier the
    ledger declares must be MENTIONED somewhere that is not the declaration."""
    parts = []
    for d in (HARNESS, HERE, os.path.join(ROOT, "work")):
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if f == "fb_ledger.py" or not f.endswith((".py", ".c", ".h", ".txt")):
                continue
            try:
                with open(os.path.join(d, f), "r", encoding="utf-8",
                          errors="replace") as fh:
                    parts.append(fh.read())
            except OSError:
                pass
    return "\n".join(parts)


TIER_RULES = {
    "T0": "asserted: must be NOTGRADED",
    "T1": "external: at least one side must be owned by `external`",
    "T2": "two independent implementations: two DISTINCT non-external owners",
    "T3": "property: GRADED or PIN, and a declared falsifier",
}


def tier_violations(ledger):
    """Recomputed from the entries every run.  The cid's T-prefix is a TIER
    CLAIM, and this is that claim measured against the row's own owners."""
    bad = []
    for cid in sorted(ledger.LEDGER):
        e = ledger.LEDGER[cid]
        t = cid.split(".")[0]
        own = e.owners()
        if t == "T0" and e.kind != ledger.NOTGRADED:
            bad.append((cid, "T0 claims 'asserted' but the row is %s" % e.kind))
        elif t == "T1" and "external" not in own:
            bad.append((cid, "T1 claims an external oracle, owners are %s" % own))
        elif t == "T2":
            nonext = [o for o in own if o != "external"]
            if "external" in own:
                bad.append((cid, "T2 claims two implementations, but one side is "
                                 "`external` (%s) -- that is Tier 1 or Tier 3" % own))
            elif len(set(nonext)) < 2:
                bad.append((cid, "T2 claims two implementations and has ONE "
                                 "producer: %s" % own))
        elif t == "T3" and e.kind == ledger.NOTGRADED:
            bad.append((cid, "T3 claims a graded property and is NOT GRADED"))
    return bad


def unconstructible_falsifiers(ledger, text):
    """A GRADED row whose declared falsifiers are named NOWHERE in the tree.
    Nothing constructs them, so the sensitivity gate can never drive the row and
    the declaration is unfalsifiable in the literal sense."""
    out = []
    for cid in sorted(ledger.LEDGER):
        e = ledger.LEDGER[cid]
        if e.kind != ledger.GRADED:
            continue
        if not any((f.split(":", 1)[-1] or "") in text for f in e.falsifier):
            out.append((cid, list(e.falsifier)))
    return out


# Pinned, as measured on 2026-08-06.  Same ratchet as OPEN_BUDGET.
TIER_VIOLATION_BUDGET = 8
UNCONSTRUCTIBLE_BUDGET = 9


def forged_row_is_rejected(ledger):
    """The gate's own falsification, from the QA report that produced this file.

    A GRADED Entry is constructed by hand with a falsifier no body builds and a
    second side relabelled `external:` so the same-owner rule cannot see it.
    fb_ledger.validate() passes it.  The two gates above must not."""
    forged = ledger.Entry(
        "T2.AUDIT.FORGED", ledger.GRADED,
        ("imp1:the ring sweep", "external:the 8253 counter's 32-bit ring"),
        falsifier=("inrow:W5AUDITNOSUCHSABOTAGE%d" % 0,),
        why="constructed by tests/w5audit.py to prove the gate bites")
    base_ok, _ = ledger.validate()
    saved = dict(ledger.LEDGER)
    try:
        ledger.LEDGER[forged.cid] = forged
        upstream_ok, _ = ledger.validate()
        tiers = tier_violations(ledger)
        uncon = unconstructible_falsifiers(ledger, _tree_text())
        caught_tier = any(cid == forged.cid for cid, _ in tiers)
        caught_uncon = any(cid == forged.cid for cid, _ in uncon)
    finally:
        ledger.LEDGER.clear()
        ledger.LEDGER.update(saved)
    return (caught_tier or caught_uncon), {
        "fb_ledger.validate() before": base_ok,
        "fb_ledger.validate() with the forgery": upstream_ok,
        "tier gate caught it": caught_tier,
        "falsifier gate caught it": caught_uncon,
    }


# =====================================================================
# 7.  Tier claims in the documents.
# =====================================================================

class TierClaim(object):
    __slots__ = ("path", "quote", "tier", "cids", "producers", "why")

    def __init__(self, path, quote, tier, cids, producers=None, why=""):
        self.path = path
        self.quote = quote
        self.tier = tier
        self.cids = tuple(cids)
        self.producers = producers
        self.why = why


TIER_CLAIMS = [
    TierClaim(
        "tests/test_wave5.py",
        "the SAME fixture, which is Tier 2 for the palette and the LUT (three",
        2, ["T2.REC.PAL6.PYVSC", "T2.LINO.REC.PAL6",
            "T2.REC.LUT.PYVSC", "T2.LINO.REC.LUT"], producers=3,
        why="three producers: w5spec's model (imp1), fb_ref.c (imp2), the lino"),
    TierClaim(
        "tests/test_wave5.py",
        "producers: this model, fb_pal.py and the lino) and UNGRADED for the",
        0, ["T2.LINO.ADAPTED.CROSSFIXTURE"],
        why="the page has NO graded two-producer row: w5probe's fixture and "
            "fb_ref.c's are different scenarios, so the cross row is NOT "
            "GRADED.  This sentence said `Tier 1 for the page' until Wave 5c; "
            "fb_compare's own TIER_TABLE had already deleted that claim."),
    TierClaim(
        "tests/test_wave5.py",
        "MAJOR 4     tier 2 for palette and LUT ..... P1 P2 P3 F1 F2 F3 (see note)",
        2, ["T2.REC.PAL6.PYVSC", "T2.LINO.REC.PAL6",
            "T2.REC.LUT.PYVSC", "T2.LINO.REC.LUT"], producers=3,
        why="the Wave 5b defect list.  It read `palette/LUT/page' until Wave "
            "5c and the page was never at tier 2."),
    # tier=None: the line MENTIONS a tier and asserts none.  Registered so that
    # the completeness gate below cannot be satisfied by prose nobody read.
    TierClaim(
        "tests/test_wave5.py",
        'page. It used to say "Tier 1 for the page", which was an over-claim',
        None, [], why="a record of a DELETED claim, not a claim"),
    TierClaim(
        "tests/test_wave5.py",
        "what tier 1 MEANS), and the two producers use different fixtures, so",
        None, [], why="the definition of tier 1, quoted while deleting a claim"),
    TierClaim(
        "docs-notes/HARNESSAUDIT.md",
        "ok  BREAKS: a Tier 2 claim resting on a ONE-PRODUCER row is reported",
        None, [], why="quoted OUTPUT of this file's own falsification battery, "
                      "section 8.7; it is a check name, not a claim about any "
                      "part of the port"),
    TierClaim(
        "docs-notes/HARNESSAUDIT.md",
        "**premise `SEG_OFFSET==4` is shared by both sides** (Tier 0, declared) |",
        0, ["T0.ALIAS8.PREMISE"],
        why="asserted, never measured; must stay NOT GRADED"),
    TierClaim(
        "docs-notes/HARNESSAUDIT.md",
        "| 531 | Tier 0 declaration | -- | -- | NOT GRADED, correctly |",
        0, ["T0.ALIAS8.PREMISE"], why="the same premise, printed not counted"),
    TierClaim(
        "docs-notes/HARNESSAUDIT.md",
        "| 663-669 | BMP is ×4-scaled, PNG is shift-or-scaled, mutually exclusive "
        "| 1996/DOSBox artifact | arithmetic predicate | **SOUND** -- Tier 1, external |",
        1, ["T1.BMP.SCALE", "T1.PNG.SCALE"],
        why="graded against captures this project did not make"),
    TierClaim(
        "docs-notes/HARNESSAUDIT.md",
        "| 670 | **L12a** alias 8 == `adapted[63996]` row 199 col 316 | SOUND as a "
        "pin; rests on the Tier-0 `SEG_OFFSET` |",
        0, ["T0.ALIAS8.PREMISE"], why="the pin's premise, again"),
    TierClaim(
        "docs-notes/HARNESSAUDIT.md",
        "| 237-239 | `consistent_with_x4` / `consistent_with_shift_or`, both reported "
        "| **SOUND** -- falsifiable in both directions, which is why the Tier 1 row "
        "means something |",
        1, ["T1.BMP.SCALE", "T1.PNG.SCALE"], why="same pair, stated from fb_bmp"),
    TierClaim(
        "docs-notes/HARNESSAUDIT.md",
        "* `fb_pal.py` and `fb_bmp.py` are clean. The Tier 1 palette evidence against the",
        1, ["T1.PAL.FIT", "T1.PAL.NOROUND", "T1.PAL.NODIV64"],
        why="the palette against the 1996 BMP"),
    TierClaim(
        "docs-notes/LINOBUF.md", "### Tier 1 -- exact, against artifacts this project did not make",
        1, ["T1.PAL.FIT", "T1.BMP.SCALE"], why="the section that DEFINES tier 1"),
    TierClaim(
        "docs-notes/LINOBUF.md", "### Tier 2 -- exact, two independent implementations",
        2, ["T2.REC.PAL6.PYVSC", "T2.LINO.REC.PAL6"], producers=3,
        why="the section that DEFINES tier 2"),
    TierClaim(
        "docs-notes/LINOBUF.md", "### Tier 3 -- properties that need no oracle",
        3, ["T3.LAYOUT.CHECK", "T3.OVERRUN.CENSUS"],
        why="the section that DEFINES tier 3"),
]

TIER_TEXT = re.compile(r"\b[Tt]ier[- ][0-3]\b|\bTIER [0-3]\b")

TIER_SCAN = ("tests/test_wave5.py", "docs-notes/HARNESSAUDIT.md",
             "docs-notes/LINOBUF.md", "docs-notes/BUFFERMODEL.md")


def tier_table_overclaims(compare, ledger):
    """fb_compare.py publishes TIER_TABLE: (element, evidence tier, producer
    COUNT, supporting cids, note).  LINOBUF 7 defines tier 2 as "exact, two
    independent implementations", and fb_ledger owns the word "independent":
    it is the OWNER of each side, and `external` -- a parsed 1996 source, a
    capture, an exact rational -- is not an implementation.

    So a row whose evidence tier contains a 2 must have at least one supporting
    GRADED cid with two DISTINCT non-external owners.  This is the check the
    brief asked for in one sentence: a document that says Tier 2 while the code
    has one producer fails."""
    bad = []
    for elem, tier, nprod, cids, _note in compare.TIER_TABLE:
        if "2" not in str(tier):
            continue
        ok = False
        seen = []
        for c in cids:
            e = ledger.LEDGER.get(c)
            if e is None or e.kind != ledger.GRADED:
                continue
            own = [o for o in e.owners() if o != "external"]
            seen.append("%s=%s" % (c, "|".join(e.owners())))
            if len(set(own)) >= 2:
                ok = True
        if not ok:
            bad.append((elem, "claims evidence tier %s (two independent "
                              "implementations) and no supporting row compares "
                              "two owners: %s" % (tier, ", ".join(seen) or "no GRADED cid")))
    return bad


# Pinned, as measured on 2026-08-06.  Ratchet: may fall, may not rise.
TIER_TABLE_BUDGET = 4


def derived_tier(ledger, cids):
    """What the CODE supports for this set of rows, computed from the entries.

    2  some GRADED row compares two DISTINCT non-external owners
    1  some GRADED row has an external side
    3  some GRADED row exists and neither of the above
    0  nothing graded
    """
    graded = [ledger.LEDGER[c] for c in cids
              if c in ledger.LEDGER and ledger.LEDGER[c].kind == ledger.GRADED]
    for e in graded:
        own = [o for o in e.owners() if o != "external"]
        if len(set(own)) >= 2:
            return 2
    for e in graded:
        if "external" in e.owners():
            return 1
    return 3 if graded else 0


def producer_count(ledger, cids):
    prod = set()
    for c in cids:
        e = ledger.LEDGER.get(c)
        if e is None or e.kind != ledger.GRADED:
            continue
        prod.update(o for o in e.owners() if o != "external")
    return len(prod)


# =====================================================================
# 8.  The audit, as suite checks.
# =====================================================================

SCOPE_DIRS = (HARNESS, HERE)


def scope_files():
    out = []
    for f in sorted(os.listdir(HARNESS)):
        if (f.startswith("fb_") or f.startswith("fbx_") or
                f.startswith("su_")) and f.endswith(".py"):
            out.append(os.path.join(HARNESS, f))
    for f in sorted(os.listdir(HERE)):
        if f.endswith(".py") and (f.startswith(("test_wave5", "test_raster",
                                                "test_spheres", "test_surface",
                                                "w5", "lino"))):
            out.append(os.path.join(HERE, f))
    return out


def all_findings(samples=300):
    out = []
    for path in scope_files():
        try:
            out.extend(analyze_file(path, samples=samples))
        except SyntaxError as exc:
            raise SystemExit("w5audit: %s does not parse: %s" % (path, exc))
    return out


# --- the gates, as predicates.  Every one of them takes its inputs as
# --- arguments, so self_falsification() below can feed each a broken input and
# --- require the complaint.  A gate whose failure path is never executed is the
# --- very thing this file exists to prevent.

def undispositioned(findings, dispositions):
    return sorted(set(f.key for f in findings if f.key not in dispositions))


def stale_dispositions(findings, dispositions):
    have = set(f.key for f in findings)
    return sorted(k for k in dispositions if k not in have)


def open_in_tests(findings, dispositions):
    return sorted(set(f.key for f in findings
                      if os.path.dirname(f.path) == HERE
                      and f.key in dispositions
                      and dispositions[f.key].kind == "OPEN"))


def claim_quote_problems(claims):
    out = []
    for c in claims:
        path = os.path.join(ROOT, c.path.replace("/", os.sep))
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                body = fh.read()
        except OSError:
            out.append("%s is not readable" % c.path)
            continue
        if c.quote not in body:
            out.append("%s no longer contains %r" % (c.path, c.quote[:52]))
    return out


def claim_support_problems(ledger, claims):
    out = []
    for c in claims:
        if c.tier is None:
            if not c.why:
                out.append("%s registers a tier MENTION with no reason" % c.path)
            continue
        got = derived_tier(ledger, c.cids)
        if c.tier == 2 and got != 2:
            out.append("%s claims Tier 2, the ledger rows %s support Tier %d"
                       % (c.path, list(c.cids), got))
        if c.tier == 1 and got == 2:
            out.append("%s claims Tier 1 and the rows now support Tier 2 -- "
                       "raise the document" % c.path)
        if c.tier == 0 and got != 0:
            out.append("%s claims Tier 0 (asserted) and %s is GRADED"
                       % (c.path, list(c.cids)))
        if c.producers is not None:
            n = producer_count(ledger, c.cids)
            if n != c.producers:
                out.append("%s says %d producers, the ledger has %d for %s"
                           % (c.path, c.producers, n, list(c.cids)))
    return out


def unregistered_tier_lines(claims, scan, texts=None):
    """Every line in `scan` that names a tier must be registered in `claims`.
    `texts` overrides the files, which is how the gate is falsified below."""
    quoted = {}
    for c in claims:
        quoted.setdefault(c.path, []).append(c.quote)
    out = []
    for rel in scan:
        if texts is not None:
            body = texts.get(rel, "")
        else:
            path = os.path.join(ROOT, rel.replace("/", os.sep))
            if not os.path.exists(path):
                continue
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                body = fh.read()
        for i, line in enumerate(body.splitlines(), 1):
            if not TIER_TEXT.search(line):
                continue
            if any(q in line for q in quoted.get(rel, ())):
                continue
            out.append("%s:%d %s" % (rel, i, line.strip()[:70]))
    return out


def self_falsification(chk, findings, ledger):
    """PROVE EACH CHECK BREAKABLE BY BREAKING IT.

    Each gate above is fed a deliberately broken input and must complain.  A
    green audit whose failure paths have never executed is indistinguishable
    from an audit with no failure paths, and that is this project's entire
    recent history."""
    fake = Finding("A", os.path.join(HARNESS, "fb_nonexistent.py"), 1,
                   "invented", "call:req", "invented", "1 == 1")
    chk.ok(bool(undispositioned(findings + [fake], DISPOSITIONS)),
           "BREAKS: an undispositioned finding is reported",
           "injected %s -> %s" % (fake.key,
                                  undispositioned(findings + [fake], DISPOSITIONS)))
    chk.ok(not undispositioned(findings, DISPOSITIONS),
           "and the real tree has none", "")

    bogus = dict(DISPOSITIONS)
    bogus["ffffffffffff"] = Disposition("OPEN", "nowhere", "invented")
    chk.ok(bool(stale_dispositions(findings, bogus)),
           "BREAKS: a disposition with no finding behind it is reported",
           "%s" % stale_dispositions(findings, bogus))

    intests = dict(DISPOSITIONS)
    tf = [f for f in findings if os.path.dirname(f.path) == HERE]
    if tf:
        intests[tf[0].key] = Disposition("OPEN", "tests/", "invented")
        chk.ok(bool(open_in_tests(findings, intests)),
               "BREAKS: a finding under tests/ disposed OPEN is reported",
               "%s" % open_in_tests(findings, intests))
    else:                                                     # pragma: no cover
        chk.note("no finding under tests/ to re-disposition; gate not exercised")

    moved = TierClaim(TIER_CLAIMS[0].path, TIER_CLAIMS[0].quote + " (moved)",
                      TIER_CLAIMS[0].tier, TIER_CLAIMS[0].cids)
    chk.ok(bool(claim_quote_problems([moved])),
           "BREAKS: a pinned tier claim whose text has drifted is reported",
           "%s" % claim_quote_problems([moved]))

    over = TierClaim("tests/test_wave5.py", TIER_CLAIMS[0].quote, 2,
                     ["T2.PAL.SELFTEST"], producers=2)
    chk.ok(bool(claim_support_problems(ledger, [over])),
           "BREAKS: a Tier 2 claim resting on a ONE-PRODUCER row is reported",
           "%s" % claim_support_problems(ledger, [over]))

    miscount = TierClaim(TIER_CLAIMS[0].path, TIER_CLAIMS[0].quote, 2,
                         list(TIER_CLAIMS[0].cids), producers=9)
    chk.ok(bool(claim_support_problems(ledger, [miscount])),
           "BREAKS: a producer COUNT that the ledger does not support is reported",
           "%s" % claim_support_problems(ledger, [miscount]))

    injected = {TIER_SCAN[0]: "a line that says Tier 2 and is in no table\n"}
    chk.ok(bool(unregistered_tier_lines(TIER_CLAIMS, TIER_SCAN[:1], injected)),
           "BREAKS: an unregistered tier claim in a scanned file is reported",
           "%s" % unregistered_tier_lines(TIER_CLAIMS, TIER_SCAN[:1], injected))

    # Reproducibility.  Before this was sorted, two runs of the SAME tree
    # disagreed on the finding count (6 or 7) because Python randomises string
    # hashing per process and the sampler walked an unsorted set of atom keys.
    fwd = sample_env(["alpha", "beta", "gamma"], random.Random(1), [7])
    rev = sample_env(["gamma", "beta", "alpha"], random.Random(1), [7])
    chk.ok(fwd == rev,
           "the sampler assigns by SORTED atom key, so the audit is "
           "reproducible across processes", "%s vs %s" % (fwd, rev))

    blunt = dict((k, v) for k, v in VOID_CORPUS.items() if k == "ring_sweep")
    hits = analyze_source(blunt["ring_sweep"][0], "<blunt>", samples=300)
    saved_cmp = CMPOPS.pop(ast.NotEq)
    try:
        blind = analyze_source(blunt["ring_sweep"][0], "<blunt>", samples=300)
    finally:
        CMPOPS[ast.NotEq] = saved_cmp
    chk.ok(bool(hits) and not blind,
           "BREAKS: with `!=` removed from the algebra the analyser goes blind, "
           "so the corpus gate is what keeps it sharp",
           "intact %d finding(s), crippled %d" % (len(hits), len(blind)))


def run(chk, samples=300):
    """Every check this module contributes to the Wave 5 suite."""
    chk.note("MECHANICAL AUDIT: checks that cannot fail (tests/w5audit.py)")

    # -- 1.  the analyser's own grade, before it is believed about anything
    ok, det = run_corpus(samples=samples)
    chk.ok(not det["missed"],
           "the audit catches all %d void shapes in its own corpus" % det["n_void"],
           "missed: %s" % ([n for n, _, _ in det["missed"]] or "none"))
    chk.ok(not det["false_positives"],
           "and flags none of the %d sound shapes" % det["n_sound"],
           "false positives: %s"
           % ([n for n, _, _ in det["false_positives"]] or "none"))
    # A rule with no corpus entry behind it is a rule nobody has shown to fire.
    chk.ok(set(det["rules"]) >= set("ABC"),
           "every rule the analyser implements is exercised by the corpus",
           "; ".join("%s <- %s" % (r, ", ".join(det["rules"][r]))
                     for r in sorted(det["rules"])))
    for name in ("ring_sweep_renamed", "same_producer_renamed"):
        hits = analyze_source(VOID_CORPUS[name][0], "<%s>" % name, samples=samples)
        chk.ok(bool(hits), "the audit is not a name filter: %s is caught" % name,
               "; ".join("%s %s" % (h.rule, h.detail[:80]) for h in hits) or "MISSED")
    lok, ldet = lint_blindness()
    if lok is None:
        chk.ok(False, "fb_lint.py comparison ran", ldet)
    else:
        chk.ok(lok, "fb_lint.py MISSES the renamed shapes this audit catches", ldet)

    # -- 2.  the tree
    findings = all_findings(samples=samples)
    by_key = {}
    for f in findings:
        by_key.setdefault(f.key, []).append(f)

    unknown = undispositioned(findings, DISPOSITIONS)
    chk.ok(not unknown,
           "every check that cannot fail is dispositioned (%d finding(s) over "
           "%d file(s))" % (len(findings), len(scope_files())),
           "UNDISPOSITIONED: %s"
           % ("; ".join("%s %s:%d %s() `%s`  key %s"
                        % (by_key[k][0].rule, os.path.basename(by_key[k][0].path),
                           by_key[k][0].line, by_key[k][0].func,
                           by_key[k][0].text[:60], k) for k in unknown) or "none"))

    stale = stale_dispositions(findings, DISPOSITIONS)
    chk.ok(not stale,
           "every disposition still names a check that is really there",
           "STALE (the code moved; re-audit and delete these): %s"
           % ("; ".join("%s [%s] %s" % (k, DISPOSITIONS[k].kind, DISPOSITIONS[k].owner)
                        for k in stale) or "none"))

    mine = open_in_tests(findings, DISPOSITIONS)
    chk.ok(not mine,
           "no check under tests/ is disposed OPEN -- this file's own territory "
           "is not allowed a backlog",
           "%s" % (mine or "none"))

    # -- 3.  every REFUTED disposition is an experiment, and it runs
    for key in sorted(k for k in DISPOSITIONS if DISPOSITIONS[k].kind == "REFUTED"):
        d = DISPOSITIONS[key]
        if key not in by_key:
            continue
        try:
            good, detail = d.demo()
        except Exception as exc:                              # pragma: no cover
            good, detail = False, "the demonstration raised %r" % (exc,)
        chk.ok(good, "REFUTED %s (%s) is demonstrated, not asserted"
               % (key, os.path.basename(d.owner)), detail)

    # -- 4.  every OPEN disposition is still void, measured, and pinned
    opens = sorted(k for k in DISPOSITIONS if DISPOSITIONS[k].kind == "OPEN")
    chk.ok(len(opens) <= OPEN_BUDGET,
           "the number of checks that cannot fail is at or under the pinned "
           "budget of %d" % OPEN_BUDGET,
           "%d open: %s" % (len(opens),
                            ", ".join("%s %s" % (k, os.path.basename(DISPOSITIONS[k].owner))
                                      for k in opens)))
    for key in opens:
        d = DISPOSITIONS[key]
        if d.demo is None:
            continue
        try:
            good, detail = d.demo()
        except Exception as exc:                              # pragma: no cover
            good, detail = False, "the measurement raised %r" % (exc,)
        chk.ok(good, "OPEN %s (%s) is STILL void, measured this run"
               % (key, os.path.basename(d.owner)), detail)
    for key in opens:
        chk.note("OPEN %s  %s -- %s" % (key, DISPOSITIONS[key].owner,
                                        DISPOSITIONS[key].why))

    # -- 5.  the ledger gate
    sys.path.insert(0, HARNESS)
    try:
        import fb_ledger
    except Exception as exc:                                  # pragma: no cover
        chk.ok(False, "fb_ledger.py imports", repr(exc))
        return
    lok, lmsg = fb_ledger.validate()
    chk.ok(lok, "fb_ledger.validate() passes on the shipped ledger",
           "; ".join(m.strip() for m in lmsg if m.strip().startswith("FAIL")) or "clean")

    good, det2 = forged_row_is_rejected(fb_ledger)
    chk.ok(good,
           "a hand-forged GRADED row is REJECTED by this audit's gates",
           "%s" % det2)

    tv = tier_violations(fb_ledger)
    chk.ok(len(tv) <= TIER_VIOLATION_BUDGET,
           "ledger tier claims: %d row(s) whose T-prefix their owners do not "
           "support, budget %d (%s)"
           % (len(tv), TIER_VIOLATION_BUDGET,
              "; ".join("%s %s" % (k, TIER_RULES[k]) for k in sorted(TIER_RULES))),
           "; ".join("%s: %s" % r for r in tv[:9]) or "none")
    try:
        import fb_compare
        tt = tier_table_overclaims(fb_compare, fb_ledger)
        chk.ok(len(tt) <= TIER_TABLE_BUDGET,
               "fb_compare.TIER_TABLE: %d element(s) claim evidence tier 2 with "
               "one producer, budget %d" % (len(tt), TIER_TABLE_BUDGET),
               "; ".join("%s -- %s" % r for r in tt) or "none")
    except Exception as exc:                                  # pragma: no cover
        chk.ok(False, "fb_compare.TIER_TABLE could be graded", repr(exc))

    uf = unconstructible_falsifiers(fb_ledger, _tree_text())
    chk.ok(len(uf) <= UNCONSTRUCTIBLE_BUDGET,
           "ledger falsifiers: %d GRADED row(s) name a falsifier no source in "
           "the tree mentions, budget %d" % (len(uf), UNCONSTRUCTIBLE_BUDGET),
           "; ".join("%s %s" % (c, f) for c, f in uf[:10]) or "none")

    # -- 6.  tier claims in the documents
    missing = claim_quote_problems(TIER_CLAIMS)
    chk.ok(not missing,
           "every pinned tier claim is still present verbatim in its document",
           "; ".join(missing) or "%d claim(s)" % len(TIER_CLAIMS))

    wrong = claim_support_problems(fb_ledger, TIER_CLAIMS)
    chk.ok(not wrong,
           "every pinned tier claim is supported by the ledger rows it rests on",
           "; ".join(wrong) or "%d claim(s), producer counts recomputed"
           % len(TIER_CLAIMS))

    unregistered = unregistered_tier_lines(TIER_CLAIMS, TIER_SCAN)
    chk.ok(not unregistered,
           "no unregistered tier claim in %d scanned file(s)" % len(TIER_SCAN),
           "; ".join(unregistered) or "none")

    # -- 7.  the one item the ledger says is not gradeable, held open
    e = fb_ledger.LEDGER.get("T2.LINO.ADAPTED.CROSSFIXTURE")
    chk.ok(e is not None and e.kind == fb_ledger.NOTGRADED
           and "FIXTURE1" in (e.why or ""),
           "the cross-fixture page comparison is still NOT GRADED and still "
           "names the document that would make it gradeable",
           "kind %s; names FIXTURE1: %s"
           % (e.kind if e else "MISSING", "FIXTURE1" in ((e.why if e else "") or "")))
    chk.ok(os.path.exists(os.path.join(DOCS, "FIXTURE1.txt")),
           "docs-notes/FIXTURE1.txt exists, so the reconciliation has a subject",
           os.path.join(DOCS, "FIXTURE1.txt"))

    # -- 8.  and every gate above, broken on purpose
    self_falsification(chk, findings, fb_ledger)


# =====================================================================
# 9.  Standalone
# =====================================================================

def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.path.insert(0, HERE)
    import linoharness as lh

    if "--findings" in argv or "--fingerprints" in argv:
        show_key = "--fingerprints" in argv
        for f in all_findings():
            print("%-2s %-22s:%-5d %-22s %s"
                  % (f.rule, os.path.basename(f.path), f.line, f.func, f.text[:70]))
            print("     %s" % f.detail)
            if show_key:
                d = DISPOSITIONS.get(f.key)
                print("     key %s   %s" % (f.key, ("[%s %s]" % (d.kind, d.owner))
                                            if d else "*** UNDISPOSITIONED ***"))
        return 0

    chk = lh.Check("WAVE 5c - the mechanical audit for checks that cannot fail")
    run(chk)
    return chk.done()


if __name__ == "__main__":
    sys.exit(main())
