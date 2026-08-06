#!/usr/bin/env python3
"""fb_lint.py -- Wave 5c.  A static lint for checks that cannot fail.

THREE RULES, each one a shape this project actually shipped:

  R1  UNCONDITIONAL ASSERTION
      `req(True, ...)`, `rec(..., True)` with a literal, `x or True`,
      `assert 1`.  fb_stick.py:352 and :360 counted two print statements as
      passing checks; fb_wrap.py:416 read `req(m != n or True, ...)`;
      fb_compare.py:651 read `rec(T1, "capture artifacts present", True)`.

  R2  SYNTACTIC SELF-COMPARISON
      both sides of a comparison normalise to the same expression tree.
      fb_layout.py:675 read `a8["nw"] == seg_index(adapted, alias8_segoff)`
      and `alias8()`'s first statement IS that expression.

  R3  EXPECTED-SIDE PROVENANCE
      `want` and `got` produced by CALLING THE SAME FUNCTION, or `got` built by
      iterating `want`.  fb_layout.py:564's L1 built `got` from `want`;
      fb_ref.c:947 built `cmp_want` with the `#ifdef`'d filter, which is why the
      C self-test was blind to BREAK_DIV64.

THE LINT IS ITSELF GRADED.  `fbout/lintcorpus/` holds six snippets that are
deliberately void and three that are sound.  `run_corpus()` FAILS if fewer than
six of the six are flagged, and it also fails if any of the three sound ones is.
A lint that cannot be shown to catch is the same class of defect it exists to
find, and a lint that flags everything is a lint nobody will keep.

  python fb_lint.py                 # the corpus, then this harness's own files
  python fb_lint.py FILE...         # lint named files
"""

import argparse
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "fbout", "lintcorpus")

CHECK_CALLS = ("req", "rec", "sreq", "assert_", "expect")


def _is_true_literal(node):
    return isinstance(node, ast.Constant) and node.value is True


def _truthy_constant(node):
    return isinstance(node, ast.Constant) and bool(node.value) and \
        not isinstance(node.value, str)


def _norm(node):
    """Structural normal form, with all location info dropped."""
    try:
        return ast.dump(node, annotate_fields=True, include_attributes=False)
    except Exception:
        return None


def _callee(node):
    f = node.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return None


class Lint(ast.NodeVisitor):
    def __init__(self, path):
        self.path = path
        self.hits = []            # (rule, line, text)

    def hit(self, rule, node, text):
        self.hits.append((rule, getattr(node, "lineno", 0), text))

    # -- R1 ---------------------------------------------------------------

    def visit_Call(self, node):
        name = _callee(node)
        if name in CHECK_CALLS:
            args = list(node.args)
            for a in args:
                if _truthy_constant(a):
                    self.hit("R1", node,
                             "%s(...) is passed the constant %r as a condition -- it "
                             "cannot fail" % (name, a.value))
                    break
                if isinstance(a, ast.BoolOp) and isinstance(a.op, ast.Or):
                    if any(_truthy_constant(v) for v in a.values):
                        self.hit("R1", node,
                                 "%s(...)'s condition is `... or <true constant>` -- the "
                                 "disjunction is always true" % name)
                        break
            for kw in node.keywords:
                if kw.arg in ("ok", "cond") and _truthy_constant(kw.value):
                    self.hit("R1", node, "%s(%s=%r) cannot fail" % (name, kw.arg, kw.value.value))
        self.generic_visit(node)

    def visit_Assert(self, node):
        if _truthy_constant(node.test):
            self.hit("R1", node, "assert of a true constant")
        self.generic_visit(node)

    # -- R2 ---------------------------------------------------------------

    def visit_Compare(self, node):
        if len(node.ops) == 1 and isinstance(node.ops[0], (ast.Eq, ast.NotEq,
                                                           ast.LtE, ast.GtE)):
            a, b = _norm(node.left), _norm(node.comparators[0])
            if a is not None and a == b:
                self.hit("R2", node, "both sides of the comparison are the same expression: %s"
                         % ast.unparse(node.left)[:70])
        self.generic_visit(node)

    # -- R3 ---------------------------------------------------------------

    def visit_FunctionDef(self, node):
        produced = {}             # variable name -> callee that produced it
        iterated = {}             # variable name -> the name it was built from
        for sub in ast.walk(node):
            if isinstance(sub, ast.Assign) and len(sub.targets) == 1 and \
                    isinstance(sub.targets[0], ast.Name):
                tgt = sub.targets[0].id
                val = sub.value
                if isinstance(val, ast.Call):
                    c = _callee(val)
                    if c:
                        produced[tgt] = c
                if isinstance(val, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
                    srcs = set()
                    for g in val.generators:
                        for n2 in ast.walk(g.iter):
                            if isinstance(n2, ast.Name):
                                srcs.add(n2.id)
                    iterated[tgt] = srcs
        pairs = [("want", "got"), ("expected", "actual"), ("expect", "actual"),
                 ("wanted", "measured")]
        for wname, gname in pairs:
            if wname in produced and gname in produced and produced[wname] == produced[gname]:
                self.hit("R3", node,
                         "`%s` and `%s` are BOTH produced by %s() -- the expected side "
                         "comes from the subject" % (wname, gname, produced[wname]))
            if gname in iterated and wname in iterated.get(gname, ()):
                self.hit("R3", node,
                         "`%s` is built by iterating `%s` -- constructor identity"
                         % (gname, wname))
            if wname in iterated and gname in iterated.get(wname, ()):
                self.hit("R3", node,
                         "`%s` is built by iterating `%s` -- constructor identity"
                         % (wname, gname))
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef


def _returned_fields(tree):
    """For every function in the module, the normalised expression it assigns to
    each local name that it then returns in a dict literal.

        def alias8(self):
            nw = self.seg_index("adapted", self.alias8_segoff)
            return {"nw": nw, ...}

    gives {"alias8": {"nw": <norm of self.seg_index(...)>}}.  R2b uses it.
    """
    out = {}
    for fn in [n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        local = {}
        for sub in ast.walk(fn):
            if isinstance(sub, ast.Assign) and len(sub.targets) == 1 and \
                    isinstance(sub.targets[0], ast.Name):
                local[sub.targets[0].id] = _norm(sub.value)
        fields = {}
        for sub in ast.walk(fn):
            if isinstance(sub, ast.Return) and isinstance(sub.value, ast.Dict):
                for k, v in zip(sub.value.keys, sub.value.values):
                    if isinstance(k, ast.Constant) and isinstance(v, ast.Name):
                        if v.id in local:
                            fields[k.value] = local[v.id]
                    elif isinstance(k, ast.Constant):
                        fields[k.value] = _norm(v)
        if fields:
            out[fn.name] = fields
    return out


def _r2b(tree, fields):
    """R2b -- CROSS-FUNCTION self-comparison.

    `x = obj.F(); req(x["k"] == <expr>)` where F's own body computes field `k`
    as exactly `<expr>`.  This is fb_layout.py:675's L12b, and a purely
    syntactic R2 cannot see it: the two sides are spelled differently and are
    the same computation.
    """
    hits = []
    for fn in [n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module))]:
        src_of = {}
        for sub in ast.walk(fn):
            if isinstance(sub, ast.Assign) and len(sub.targets) == 1 and \
                    isinstance(sub.targets[0], ast.Name) and isinstance(sub.value, ast.Call):
                c = _callee(sub.value)
                if c in fields:
                    src_of[sub.targets[0].id] = c
        if not src_of:
            continue
        for cmp_ in [n for n in ast.walk(fn) if isinstance(n, ast.Compare)]:
            sides = [cmp_.left] + list(cmp_.comparators)
            for i, s in enumerate(sides):
                if not (isinstance(s, ast.Subscript) and isinstance(s.value, ast.Name)
                        and s.value.id in src_of):
                    continue
                key = s.slice.value if isinstance(s.slice, ast.Constant) else None
                if key is None:
                    continue
                want = fields[src_of[s.value.id]].get(key)
                for j, other in enumerate(sides):
                    if i != j and want is not None and _norm(other) == want:
                        hits.append(("R2b", cmp_.lineno,
                                     "`%s[%r]` is compared against the very expression "
                                     "%s() computes it with -- x == x across a function "
                                     "boundary" % (s.value.id, key, src_of[s.value.id])))
    return hits


def lint_source(src, path="<str>"):
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return [("PARSE", getattr(exc, "lineno", 0), str(exc))]
    v = Lint(path)
    v.visit(tree)
    hits = v.hits + _r2b(tree, _returned_fields(tree))
    return sorted(set(hits), key=lambda h: (h[1], h[0]))


def lint_file(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return lint_source(fh.read(), path)


# ------------------------------------------------------------ the corpus

VOID_CORPUS = {
    "void1_literal_true.py": '''
def check(req):
    """R1: fb_stick.py:352 -- a print statement counted as a passing check."""
    req(True, "A2 escape corpus: 400000 cases enumerated")
''',
    "void2_or_true.py": '''
def check(req, m, n):
    """R1: fb_wrap.py:416 -- the disjunction cannot be false."""
    req(m != n or True, "W6 the two multipliers differ")
''',
    "void3_selfcompare.py": '''
def alias8(self):
    """R2b: fb_layout.py:675's L12b.  alias8() COMPUTES nw this way, and the
    check below compares its result against the same expression."""
    nw = self.seg_index("adapted", self.alias8_segoff)
    return {"nw": nw, "index": nw - 4}


def check(self, req):
    a8 = self.alias8()
    req(a8["nw"] == self.seg_index("adapted", self.alias8_segoff),
        "L12b alias 8 resolves through the SAME seg_index primitive")
''',
    "void4_want_from_got.py": '''
def check(req, parse, alloc):
    """R3: fb_layout.py:564 -- got was built by iterating want."""
    want = parse(alloc)
    got = [r for r in want]
    req(want == got, "L1 layout order == farmalloc order")
''',
    "void5_same_producer.py": '''
def check(req, filter_one, data):
    """R3: fb_ref.c:947 -- want built with the very function under test."""
    want = filter_one(data)
    got = filter_one(data)
    req(want == got, "S2 the filter agrees with itself")
''',
    "void6_rec_true.py": '''
def check(rec, caps):
    """R1: fb_compare.py:651 -- the row above it did the work."""
    rec("T1", "capture artifacts present (%d)" % len(caps), True)
''',
}

SOUND_CORPUS = {
    "sound1_two_parses.py": '''
def check(req, parse_a, parse_b, text):
    """Two structurally different parses of one source: a real claim."""
    want = parse_a(text)
    got = parse_b(text)
    req(want == got, "L1 layout order, two independent parses")
''',
    "sound2_unbounded_truth.py": '''
def check(req, mask32, cpms, ms):
    """The subject is masked, the truth is not: the mask cannot cancel."""
    got = mask32(cpms * ms)
    req(got == cpms * ms, "the recovered window equals the unbounded truth")
''',
    "sound3_external.py": '''
def check(req, measured, bmp_bytes):
    """Graded against an artifact this project did not make."""
    req(all(b % 4 == 0 for b in bmp_bytes) and measured, "v*4, not shift-or")
''',
}


def write_corpus():
    os.makedirs(CORPUS, exist_ok=True)
    for name, src in list(VOID_CORPUS.items()) + list(SOUND_CORPUS.items()):
        with open(os.path.join(CORPUS, name), "w", encoding="utf-8") as fh:
            fh.write(src.lstrip())
    return CORPUS


def run_corpus(quiet=True):
    """Returns (ok, detail).  The lint's own grade."""
    write_corpus()
    caught, missed, false_pos = [], [], []
    for name in sorted(VOID_CORPUS):
        hits = lint_file(os.path.join(CORPUS, name))
        (caught if hits else missed).append((name, hits))
    for name in sorted(SOUND_CORPUS):
        hits = lint_file(os.path.join(CORPUS, name))
        if hits:
            false_pos.append((name, hits))
    ok = not missed and not false_pos
    detail = {
        "void_total": len(VOID_CORPUS), "clean_total": len(SOUND_CORPUS),
        "caught": [n for n, _ in caught], "missed": [n for n, _ in missed],
        "false_positives": [n for n, _ in false_pos],
        "summary": "caught %d/%d void; %d false positive(s) on %d sound%s"
                   % (len(caught), len(VOID_CORPUS), len(false_pos), len(SOUND_CORPUS),
                      "" if ok else "  MISSED %s  FALSE %s"
                      % ([n for n, _ in missed], [n for n, _ in false_pos])),
    }
    if not quiet:
        for name, hits in caught:
            print("  CAUGHT  %-28s %s" % (name, "; ".join("%s:%d %s" % h for h in hits)))
        for name, _ in missed:
            print("  MISSED  %-28s -- this snippet is void and the lint did not see it" % name)
        for name, hits in false_pos:
            print("  FALSE   %-28s %s" % (name, hits))
    return ok, detail


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--corpus", action="store_true", help="only the corpus")
    args = ap.parse_args(argv)

    print("fb_lint.py -- checks that cannot fail")
    print("=" * 78)
    ok, detail = run_corpus(quiet=False)
    print("  corpus: %s" % detail["summary"])
    print()

    files = args.files
    if not files and not args.corpus:
        files = sorted(os.path.join(HERE, f) for f in os.listdir(HERE)
                       if f.startswith("fb_") and f.endswith(".py"))
    total = 0
    for f in files:
        hits = lint_file(f)
        total += len(hits)
        if hits:
            print("%s" % os.path.basename(f))
            for rule, line, text in hits:
                print("  %s  line %-5d %s" % (rule, line, text))
    print()
    print("%d finding(s) across %d file(s)" % (total, len(files)))
    print("RESULT: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
