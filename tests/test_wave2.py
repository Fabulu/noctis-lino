"""GUARDS: Wave 2's two answers - the type of a random() argument, and the
operand order inside zrandom - and, because the subject is a binary that will
never change again, the DECODERS that produce them.

    UNKNOWN 1  the double never survives. random() is a compiled out-of-line
               function whose parameter is a 16-bit stack slot, so the argument
               is chopped by __ftol and narrowed to int16 AT THE CALL BOUNDARY,
               with a real wrap.
    UNKNOWN 2  zrandom returns (float)(int16)(FIRST draw - SECOND draw). No
               sign flip. The shipped binary agrees with noctis-iv-lr.

Why this test is shaped the way it is
-------------------------------------
NOCTIS.EXE is a 1996 artifact. It cannot regress. A test that merely re-read it
would pass forever no matter what the decoders did - including printing a
remembered answer and never looking at a byte. So the subject here is not the
binary, it is the decoding, and the test is built to fail in the two ways that
actually threaten the finding:

  * a decoder stops decoding - caught by the MUTATION BATTERY. Every load
    bearing byte is flipped in a private copy and the decoders must report the
    changed answer. A decoder that hardcodes its verdict fails.
  * the recorded answer drifts from the evidence - caught by leg 6. Every
    claim in docs-notes/WAVE2_ANSWERS.md is parsed out of the document and
    required to equal what the routes decode TODAY. Editing the write-up
    without the bytes changing fails the test.

Three independent routes, none of which is graded against a stored artifact:

    ba_w2.py   capstone, top-down from the unique 35 4E LCG anchor
    bx_w2.py   ndisasm, Borland symbol names in DL.EXE/ST.EXE transferred as
               masked byte signatures
    w2spec.py  this suite's own: named-field byte templates and suffix-anchored
               backward matching, no disassembler at all

Route C exists because two decoders agreeing is only evidence if a third party
can check them, and because Wave 2's QA pass recorded two blind spots shared by
both delivered decoders: rand's return path (mask and which seed word), and the
0x9B FWAIT that hides 49 of the 385 call sites. Route C covers both, and the
battery contains mutants that ONLY route C catches - recorded as such, so the
test stays honest about who sees what and still passes when a decoder is fixed.

NEGATIVE CONTROLS (both must fail, or the test fails):
  1. A LIAR DECODER is generated at run time. It ignores --binary entirely and
     replays the pristine answer. It passes the pristine cross-diff perfectly -
     that is the point - and the mutation battery must catch it on every single
     mutant. If the battery ever clears the liar, the battery is not checking.
  2. A corrupted claim is fed to the document comparator, which must reject it.

Nothing under main/, and nothing under C:\\programmieren\\noctis, is ever
written. Mutants are built from an in-memory copy into tests/gen/w2 and deleted
again; the reference clones' hashes are re-verified after the battery.

RUN: python tests/test_wave2.py        (~40s)
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

import linoharness as L
import w2spec

sys.path.insert(0, L.HARNESS)
import w2v_verdict as V                                        # noqa: E402

MODULES = V.MODULES
NOCTIS = os.path.join(MODULES, "NOCTIS.EXE")
DL = os.path.join(MODULES, "DL.EXE")
ST = os.path.join(MODULES, "ST.EXE")
BA = os.path.join(L.HARNESS, "ba_w2.py")
BX = os.path.join(L.HARNESS, "bx_w2.py")
ANSWERS = os.path.join(L.REPO, "docs-notes", "WAVE2_ANSWERS.md")

SANDBOX = os.path.join(L.GEN, "w2")

# Claims parsed out of the write-up. Values are ints, booleans, bare words, or
# [a, b] lists. Keys are dotted paths into a verdict.
CLAIM = re.compile(r"^\s*([A-Za-z0-9_.]+)\s*=\s*(.+?)\s*$")

# Headline numbers that must also appear in the document's PROSE, so the table
# cannot quietly drift away from the paragraphs around it.
HEADLINE = ["anchors.rand_entry", "anchors.random_entry", "anchors.zrandom_entry",
            "anchors.ftol_entry", "unknown2.sub_file", "unknown1.random_divisor",
            "census.random.total"]


# ---------------------------------------------------------------------- routes

def run_subprocess_decoder(argv):
    p = subprocess.run(argv, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if p.returncode != 0:
        return {"status": "DECODER_CRASHED", "failed_stage": "exit %d" % p.returncode,
                "failure_detail": (p.stderr or "")[-400:]}
    try:
        return json.loads(p.stdout)
    except Exception as e:
        return {"status": "DECODER_UNPARSEABLE", "failed_stage": str(e),
                "failure_detail": (p.stdout or "")[:400]}


def route_ba(binary):
    return run_subprocess_decoder([sys.executable, BA, "--binary", binary,
                                   "--dl", DL, "--st", ST])


def route_bx(binary):
    return run_subprocess_decoder([sys.executable, BX, "--binary", binary,
                                   "--dl", DL, "--st", ST])


def route_cs(binary):
    return w2spec.decode(binary)


ROUTES = {"ba": route_ba, "bx": route_bx, "cs": route_cs}
ROUTE_BLURB = {
    "ba": "capstone, top-down from the unique 35 4E anchor",
    "bx": "ndisasm, Borland symbol names transferred as masked signatures",
    "cs": "byte templates, no disassembler (this suite's own)",
}


# --------------------------------------------------------------- the mutants
# Every patch states the bytes it expects to replace. A stale offset therefore
# fails loudly instead of silently mutating nothing. Nothing is stored: each
# mutant is rebuilt from the pristine bytes on every run.
#
#   facts        must hold for every route in `catchers`
#   route_facts  must additionally hold for the named route
#   catchers     the routes REQUIRED to notice. Routes outside this list are
#                run anyway and their blindness is reported, never asserted -
#                so fixing a decoder cannot turn this test red.
#   crossdiff    all catchers must still agree on the 57 semantic-core keys

MUTANTS = [
    dict(id="Z_ORDER_FLIP",
         why="make zrandom genuinely compute draw2 - draw1",
         patch=[(60774, "2bd0", "2bc2"), (60776, "8956fe", "8946fe")],
         facts={"unknown2.verdict": "RIGHT_TO_LEFT", "unknown2.minuend": "draw2",
                "unknown2.sub_dst": "ax", "unknown2.sub_src": "dx",
                "unknown2.stored_reg": "ax"},
         catchers=["ba", "bx", "cs"], crossdiff=True),
    dict(id="Z_VIA_BX",
         why="same flip through a DIFFERENT register, so no route can be keying on 'dx'",
         patch=[(60773, "5a", "5b"), (60774, "2bd0", "2bc3"), (60776, "8956fe", "8946fe")],
         facts={"unknown2.verdict": "RIGHT_TO_LEFT", "unknown2.minuend": "draw2",
                "unknown2.sub_src": "bx"},
         catchers=["ba", "bx", "cs"], crossdiff=True),
    dict(id="Z_SUB_TO_ADD",
         why="the two draws are ADDED; no honest route can name a minuend",
         patch=[(60774, "2bd0", "03d0")],
         facts={"status": "LOCATION_FAILED"},
         catchers=["ba", "bx", "cs"], crossdiff=False),
    dict(id="Z_CALL_REPOINT",
         why="zrandom's SECOND draw is aimed one byte into random's prologue",
         patch=[(60769, "e8d354", "e8d454")],
         facts={"status": "LOCATION_FAILED"},
         catchers=["ba", "cs"], crossdiff=False),
    dict(id="R_DIVISOR",
         why="random divides by 0x4000 instead of 0x8000",
         patch=[(82510, "0080", "0040")],
         facts={"unknown1.random_divisor": 16384},
         catchers=["ba", "bx", "cs"], crossdiff=True),
    dict(id="R_MOVZX",
         why="the 16-bit parameter is zero-extended, not sign-extended",
         patch=[(82501, "bf", "b7")],
         facts={"unknown1.random_param_signextended": False},
         catchers=["ba", "bx", "cs"], crossdiff=True),
    dict(id="R_PARAM32",
         why="random reads its parameter as a 32-bit slot; UNKNOWN 1 would be undecided",
         patch=[(82499, "660fbf5606", "668b569090")],
         facts={"status": "LOCATION_FAILED"},
         catchers=["ba", "bx", "cs"], crossdiff=False),
    dict(id="F_RCBITS",
         why="__ftol forces round-DOWN instead of chop",
         patch=[(14455, "0c", "04")],
         facts={"unknown1.ftol.cw_or_immediate": 4, "unknown1.ftol.rounding": "DOWN"},
         catchers=["ba", "bx", "cs"], crossdiff=True),
    dict(id="F_PUSHDX",
         why="line 4089 pushes __ftol's HIGH half, not its low half",
         patch=[(61560, "50", "52")],
         facts={"fp_site.61562.push_reg": "dx",
                "fp_site.61562.narrowing": "HIGH16_OF_FTOL"},
         catchers=["ba", "bx", "cs"], crossdiff=True),
    dict(id="X_ANCHOR",
         why="destroy the unique 35 4E multiplier: no route may still find rand",
         patch=[(15982, "354e", "364e")],
         facts={"status": "LOCATION_FAILED"},
         route_facts={"ba": {"selfcheck.anchor_354e_count": 0},
                      "cs": {"selfcheck.anchor_354e_count": 0}},
         catchers=["ba", "bx", "cs"], crossdiff=False),
    dict(id="X_WRAPCALL",
         why="kill one WRAP-ENCODED near call to random; rel16 arithmetic not "
             "reduced modulo 2**16 inside the segment frame would miss this",
         patch=[(37112, "3db1", "0000")],
         facts={"census.random.total": 374},
         catchers=["ba", "bx", "cs"], crossdiff=True),
    dict(id="T_RANDMASK",
         why="rand masks its result to 14 bits, which would make random's 0x8000 "
             "divisor wrong - a blind spot of both delivered decoders",
         patch=[(16004, "25ff7f", "25ff3f")],
         facts={"randtail.rand_mask": 16383},
         catchers=["cs"], crossdiff=False),
    dict(id="T_RANDLOW",
         why="rand returns the LOW seed word instead of the high one - the same "
             "blind spot, and a completely different generator",
         patch=[(16000, "a15c39", "a15a39")],
         facts={"randtail.rand_returns": "LOW_SEED_WORD"},
         catchers=["cs"], crossdiff=False),
    dict(id="P_FWAITFLOAT",
         why="plant x87 code immediately before an argument push behind an FWAIT: "
             "49 of the 385 call sites are hidden from both delivered decoders by "
             "exactly that byte",
         patch=[(62845, "6a0a909b90", "d9ee509b90")],
         facts={"x87_adjacent_reg_pushes": [62850]},
         catchers=["cs"], crossdiff=False),
    dict(id="P_FISTPPUSH",
         why="line 4089's argument reaches random through fistp/push instead of "
             "the chop helper - a float bypassing __ftol",
         patch=[(61555, "9a651200005090", "df5eeeff76ee90")],
         facts={"unknown1.fp_sites_total": 11},
         route_facts={"ba": {"unknown1.nonftol_fp_arg_sites": [61562],
                             "unknown1.verdict": "FP_SURVIVES_INTO_RAND"},
                      "cs": {"unknown1.nonftol_fp_arg_sites": [61562],
                             "unknown1.verdict": "FP_SURVIVES_INTO_RAND"}},
         catchers=["ba", "bx", "cs"], crossdiff=False),
]


def apply_patch(base, patch):
    b = bytearray(base)
    for off, orig, new in patch:
        ob, nb = bytes.fromhex(orig), bytes.fromhex(new)
        if bytes(b[off:off + len(ob)]) != ob:
            raise AssertionError("stale mutation at %d: found %s, expected %s"
                                 % (off, b[off:off + len(ob)].hex(), orig))
        if len(nb) != len(ob):
            raise AssertionError("mutation at %d is not length preserving" % off)
        b[off:off + len(nb)] = nb
    return bytes(b)


def fact_of(verdict, key):
    """Read one fact out of a verdict. `fp_site.<call>.<field>` reaches into
    the unknown1.fp_sites list, which is a list of dicts rather than a path."""
    if key.startswith("fp_site."):
        _, call, field = key.split(".", 2)
        for s in V.get(verdict, "unknown1.fp_sites", missing=[]):
            if s.get("call") == int(call):
                return s.get(field, "<<MISSING>>")
        return "<<NO SUCH SITE>>"
    return V.get(verdict, key, missing="<<MISSING>>")


def same(a, b):
    if isinstance(a, str) and isinstance(b, str):
        return a.lower() == b.lower()
    return a == b


def check_facts(verdict, facts):
    """The facts a route got wrong, as printable strings."""
    bad = []
    for k, want in sorted(facts.items()):
        got = fact_of(verdict, k)
        if not same(got, want):
            bad.append("%s = %r, expected %r" % (k, got, want))
    return bad


def battery(routes, mutants, base_bytes, sandbox, quiet=False):
    """Run every mutant past every route. Returns
    {mutant_id: {route: [facts the route got wrong]}}.

    The mutant is written under a name that carries no hint of what was
    changed, so a decoder cannot key on the filename.
    """
    results = {}
    for m in mutants:
        data = apply_patch(base_bytes, m["patch"])
        tag = hashlib.sha256(m["id"].encode()).hexdigest()[:10]
        path = os.path.join(sandbox, "bin%s.exe" % tag)
        with open(path, "wb") as fh:
            fh.write(data)
        per = {}
        for name, fn in routes.items():
            v = fn(path)
            facts = dict(m["facts"])
            facts.update(m.get("route_facts", {}).get(name, {}))
            per[name] = (check_facts(v, facts), v)
        results[m["id"]] = per
        os.remove(path)
    return results


# ------------------------------------------------------------------ the claims

def parse_claims(text):
    """The `key = value` block of the write-up, between its CLAIMS fences."""
    m = re.search(r"<!--\s*CLAIMS\s*-->(.*?)<!--\s*/CLAIMS\s*-->", text, re.S)
    if not m:
        return None, ""
    out = {}
    for line in m.group(1).splitlines():
        line = line.split("#")[0]
        if not line.strip() or line.strip().startswith("```"):
            continue
        mm = CLAIM.match(line)
        if not mm:
            continue
        k, raw = mm.group(1), mm.group(2)
        if raw in ("True", "False"):
            val = raw == "True"
        elif re.match(r"^-?\d+$", raw):
            val = int(raw)
        elif raw.startswith("["):
            inner = raw.strip("[]").strip()
            val = [int(x) for x in inner.split(",")] if inner else []
        else:
            val = raw
        out[k] = val
    return out, text[:m.start()] + text[m.end():]


def compare_claims(claims, verdicts):
    """Every claim, against every route that can compute it. Returns
    (failures, coverage) where coverage counts routes that answered."""
    bad, covered = [], 0
    for k, want in sorted(claims.items()):
        answering = []
        for name, v in verdicts.items():
            got = fact_of(v, k)
            if got == "<<MISSING>>":
                continue
            answering.append(name)
            if not same(got, want):
                bad.append("%s: the write-up says %r, route %s decodes %r"
                           % (k, want, name, got))
        if not answering:
            bad.append("%s: no route computes this key at all" % k)
        else:
            covered += 1
    return bad, covered


# ------------------------------------------------------------------- the liar

LIAR = '''"""Generated negative control. Ignores --binary and replays a stored
answer, which is exactly the failure mode the mutation battery exists to catch."""
import argparse, json, sys
ap = argparse.ArgumentParser()
ap.add_argument("--binary", required=True)
ap.add_argument("--dl"); ap.add_argument("--st")
ap.parse_args()
sys.stdout.write(%r)
'''


def write_liar(path, pristine_verdict):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(LIAR % json.dumps(pristine_verdict))


# ---------------------------------------------------------------------- main

def main():
    c = L.Check("test_wave2 - the random() argument type and zrandom's operand order")

    for p in (NOCTIS, DL, ST, BA, BX):
        if not c.ok(os.path.exists(p), "present: %s" % os.path.basename(p), p):
            return c.done()
    if os.path.isdir(SANDBOX):
        shutil.rmtree(SANDBOX, ignore_errors=True)
    os.makedirs(SANDBOX, exist_ok=True)

    # ------------------------------------------------- 1. the input, not the answer
    # The hashes are READ OUT OF the harness's own gate table rather than
    # restated here, so a wrong hash cannot survive by being wrong in both
    # places. This pins the INPUT. It pins nothing about the finding.
    for name, (want, size) in sorted(V.BINARIES.items()):
        p = os.path.join(MODULES, name)
        c.ok(V.sha256_file(p) == want and os.path.getsize(p) == size,
             "%s is the pristine reference clone" % name, want[:16] + "...")
    base = open(NOCTIS, "rb").read()

    # ------------------------------------------------- 2. three routes, recomputed
    verdicts = {}
    for name, fn in sorted(ROUTES.items()):
        v = fn(NOCTIS)
        verdicts[name] = v
        c.ok(v.get("status") == "OK", "route %s decodes NOCTIS.EXE  (%s)"
             % (name, ROUTE_BLURB[name]),
             v.get("failed_stage", "") + " " + str(v.get("failure_detail", ""))[:80])
    if any(v.get("status") != "OK" for v in verdicts.values()):
        return c.done()

    core = V.SEMANTIC_CORE                       # read from the harness, not restated
    c.ok(len(core) >= 50, "the verdict contract has %d semantic-core keys" % len(core))
    for a, b in (("ba", "bx"), ("ba", "cs"), ("bx", "cs")):
        bad = V.diff(verdicts[a], verdicts[b], a, b)
        c.ok(not bad, "%s == %s on all %d semantic-core keys" % (a, b, len(core)),
             "%d mismatches" % len(bad))

    # the contract's own schema/liveness check, per route
    for name in sorted(ROUTES):
        if name == "cs":
            continue                              # route C emits no disassembly text
        errs = V.check_one(verdicts[name])
        c.ok(not errs, "route %s satisfies the verdict contract" % name, "; ".join(errs[:2]))

    # ------------------------------------------------- 3. what the routes decoded
    ref = verdicts["ba"]
    c.note("rand      %d   srand %d   random %d   zrandom %d   __ftol %d"
           % (V.get(ref, "anchors.rand_entry"), V.get(ref, "anchors.srand_entry"),
              V.get(ref, "anchors.random_entry"), V.get(ref, "anchors.zrandom_entry"),
              V.get(ref, "anchors.ftol_entry")))
    c.note("census    rand %d   random %d   zrandom %d   __ftol %d"
           % (V.get(ref, "census.rand.total"), V.get(ref, "census.random.total"),
              V.get(ref, "census.zrandom.total"), V.get(ref, "census.ftol.total")))
    c.note("UNKNOWN 1 %s  (param %d bits, signed %s, divisor %d, %s)"
           % (V.get(ref, "unknown1.verdict"), V.get(ref, "unknown1.random_param_width_bits"),
              V.get(ref, "unknown1.random_param_signextended"),
              V.get(ref, "unknown1.random_divisor"), V.get(ref, "unknown1.ftol.rounding")))
    c.note("UNKNOWN 2 %s  (%s - %s, sub at %d)"
           % (V.get(ref, "unknown2.verdict"), V.get(ref, "unknown2.minuend"),
              V.get(ref, "unknown2.live_draw"), V.get(ref, "unknown2.sub_file")))

    # rand has ONE caller. A textual macro would inline the call at every use
    # site; one caller is what proves random() is a compiled function, and that
    # is what forces the double through a 16-bit stack slot.
    c.eq(V.get(ref, "census.rand.total"), 1,
         "rand() has exactly one caller - random() is compiled, not a macro")
    c.eq(V.get(ref, "unknown1.random_param_width_bits"), 16,
         "...and that one function reads its argument as a 16-bit word")
    c.eq(V.get(ref, "unknown2.minuend"), V.get(ref, "unknown2.spilled_draw"),
         "the minuend is the draw that was SPILLED, i.e. the first one")
    c.eq(V.get(ref, "unknown1.nonftol_fp_arg_sites"), [],
         "no float reaches random() without passing through the chop helper")

    # ------------------------------------------------- 4. the routes' self-checks
    for name in sorted(ROUTES):
        sc = verdicts[name].get("selfcheck", {})
        c.eq(sc.get("far_sites_with_reloc"), sc.get("far_sites_total"),
             "%s: every far call site's segment word carries a relocation" % name)
        c.eq(sc.get("pushcs_sites_with_nop_pad"), sc.get("pushcs_sites_total"),
             "%s: every push-cs call site carries Borland's 0x90 pad" % name)

    # ------------------------------------------------- 5. route C's extra ground
    cs = verdicts["cs"]
    c.eq(V.get(cs, "randtail.rand_returns"), "HIGH_SEED_WORD",
         "rand returns the HIGH seed word - what makes the 0x8000 divisor right")
    c.eq(V.get(cs, "randtail.rand_mask"), 0x7FFF, "...masked to 15 bits")
    c.eq(V.get(cs, "x87_adjacent_reg_pushes"), [],
         "no register argument push is fed by x87 code, at any of the 385 sites")

    # ------------------------------------------------- 6. the write-up vs the bytes
    if not c.ok(os.path.exists(ANSWERS), "the write-up exists", ANSWERS):
        return c.done()
    text = open(ANSWERS, "r", encoding="utf-8").read()
    claims, prose = parse_claims(text)
    if not c.ok(claims is not None, "the write-up carries a CLAIMS block", ANSWERS):
        return c.done()
    c.ok(len(claims) >= 30, "the write-up states %d machine-checkable claims" % len(claims))
    bad, covered = compare_claims(claims, verdicts)
    c.ok(not bad, "every claim in the write-up matches what the routes decode today",
         "; ".join(bad[:3]))
    c.eq(covered, len(claims), "...and every claim was actually answered by a route")
    missing = [k for k in HEADLINE
               if k in claims and str(claims[k]) not in prose]
    c.eq(missing, [], "the headline offsets appear in the prose, not only in the table")

    # NEGATIVE CONTROL 2: a corrupted claim must be rejected. Without this,
    # "every claim matches" could be an empty statement about an empty parse.
    spoiled = dict(claims)
    spoiled["unknown2.verdict"] = "RIGHT_TO_LEFT"
    bad2, _ = compare_claims(spoiled, verdicts)
    c.ok(bool(bad2), "the claim comparator REJECTS a flipped unknown-2 verdict",
         (bad2[0] if bad2 else "it accepted it"))

    # ------------------------------------------------- 7. the mutation battery
    # Each expectation is first required to DIFFER from the pristine answer, so
    # no mutant can pass by asserting something that was already true.
    vacuous = []
    for m in MUTANTS:
        for k, want in m["facts"].items():
            for r in m["catchers"]:
                if same(fact_of(verdicts[r], k), want):
                    vacuous.append("%s/%s/%s" % (m["id"], r, k))
    c.eq(vacuous, [], "every mutant expectation differs from the pristine answer")

    c.note("running %d mutants past %d routes..." % (len(MUTANTS), len(ROUTES)))
    try:
        res = battery(ROUTES, MUTANTS, base, SANDBOX)
    except AssertionError as e:
        # a patch that no longer describes the bytes it replaces is a broken
        # test, not a finding, and must say so rather than mutate nothing.
        c.ok(False, "every mutant patch still describes the bytes it replaces", str(e))
        return c.done()
    for m in MUTANTS:
        per = res[m["id"]]
        for r in m["catchers"]:
            wrong, _v = per[r]
            c.ok(not wrong, "%-14s %s reports the mutated answer" % (m["id"], r),
                 "; ".join(wrong[:2]))
        blind = [r for r in ROUTES if r not in m["catchers"]]
        if blind:
            saw = [r for r in blind if not per[r][0]]
            c.note("%-14s not required of %s%s" % (
                m["id"], ",".join(blind),
                (" - but %s noticed anyway" % ",".join(saw)) if saw else " - and none noticed"))
        if m.get("crossdiff"):
            ok_all = True
            for a, b in zip(m["catchers"], m["catchers"][1:]):
                if V.diff(per[a][1], per[b][1], a, b):
                    ok_all = False
            c.ok(ok_all, "%-14s the routes still agree on the mutant" % m["id"])

    # ------------------------------------------------- 8. the liar
    # A decoder that stopped decoding looks perfect on the pristine binary.
    # The battery is the only thing that can tell it apart, so the battery is
    # what gets tested here.
    liar_path = os.path.join(SANDBOX, "liar.py")
    write_liar(liar_path, verdicts["ba"])
    liar = {"liar": lambda b: run_subprocess_decoder([sys.executable, liar_path,
                                                      "--binary", b])}
    lv = liar["liar"](NOCTIS)
    c.ok(not V.diff(lv, verdicts["ba"], "liar", "ba"),
         "the liar passes the pristine cross-diff perfectly - as it must, "
         "or it would not be a useful control")

    lres = battery(liar, MUTANTS, base, SANDBOX)
    caught = [m["id"] for m in MUTANTS if lres[m["id"]]["liar"][0]]
    escaped = [m["id"] for m in MUTANTS if not lres[m["id"]]["liar"][0]]
    c.eq(escaped, [], "the battery catches the liar on EVERY mutant "
                      "(%d/%d)" % (len(caught), len(MUTANTS)))

    # ------------------------------------------------- 9. nothing was written to
    for name, (want, _size) in sorted(V.BINARIES.items()):
        p = os.path.join(MODULES, name)
        c.ok(V.sha256_file(p) == want,
             "%s is still pristine after the battery" % name)
    shutil.rmtree(SANDBOX, ignore_errors=True)
    c.ok(not os.path.isdir(SANDBOX), "the mutant sandbox is gone")

    return c.done()


if __name__ == "__main__":
    sys.exit(main())
