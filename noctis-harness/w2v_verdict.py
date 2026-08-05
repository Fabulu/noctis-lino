#!/usr/bin/env python
"""
w2v_verdict.py -- Wave 2 verdict contract, mechanical diff, and mutation pin.

NEUTRAL GROUND.  Owned by neither implementer.
  Implementer 1 owns  noctis-harness/ba_*.py   (capstone route)
  Implementer 2 owns  noctis-harness/bx_*.py   (ndisasm route)
This file imports NEITHER.  It runs them as subprocesses and compares stdout JSON.

Decoder contract
----------------
    python <decoder> --binary <PATH> [--dl <PATH>] [--st <PATH>]
        -> single JSON object on stdout, nothing else, exit 0
        -> on failure to LOCATE anything: still emit JSON with
           {"status": "LOCATION_FAILED", "failed_stage": "<what>"} and exit 0.
           Never emit a cached/hardcoded answer.  Never read a binary path
           that was not passed on the command line.

Subcommands
-----------
    python w2v_verdict.py schema                 print the semantic core key list
    python w2v_verdict.py check  V.json          validate one verdict
    python w2v_verdict.py diff   A.json B.json   mechanical diff (exit 1 on mismatch)
    python w2v_verdict.py mutants OUTDIR         materialise the mutation set
    python w2v_verdict.py pin "<ba cmd>" "<bx cmd>" OUTDIR
                                                 full regression pin
Nothing here is graded against a stored answer: every number is recomputed
from the bytes on every run.  The only stored constants are (a) the input
binaries' hashes, which pin the INPUT, and (b) the mutation offsets, which are
re-validated against the pristine bytes before use.
"""

import hashlib
import json
import os
import random as _pyrandom
import shutil
import subprocess
import sys

# --------------------------------------------------------------------------
# 0.  Input identity.  Pins the INPUT, never the answer.
# --------------------------------------------------------------------------
MODULES = r"C:\programmieren\noctis\niv-plus\modules"
BINARIES = {
    "NOCTIS.EXE": ("5e64d532091c9be1f91d7e0bc57719df24020ba38b0662f225f65d3c55e579ac", 215744),
    "DL.EXE":     ("e4a78485e49a7af151c626cd5157589ab2e951ac4087e016900550941fd7bfe2", 46004),
    "ST.EXE":     ("22318f8def371c7756620edab166de3b7708804cfd5b8f8b5bdb442bd82f7a4c", 41615),
}

# --------------------------------------------------------------------------
# 1.  The semantic core.  ONLY these keys are diffed.  All of them are
#     engine-neutral (ints, enums, lists of ints) -- never disassembler text,
#     because capstone and ndisasm legitimately print differently.
# --------------------------------------------------------------------------
SEMANTIC_CORE = [
    "status",
    "binary.sha256", "binary.size",
    "layout.header_len", "layout.dgroup_file",
    "anchors.rand_entry", "anchors.srand_entry", "anchors.random_entry",
    "anchors.zrandom_entry", "anchors.zrandom_len", "anchors.ftol_entry",
    "anchors.zrandom_body_sha256", "anchors.random_body_sha256",
    "census.rand.far", "census.rand.pushcs", "census.rand.total", "census.rand.sites",
    "census.random.far", "census.random.pushcs", "census.random.total", "census.random.sites",
    "census.zrandom.far", "census.zrandom.pushcs", "census.zrandom.total", "census.zrandom.sites",
    "census.ftol.total",
    "unknown1.verdict", "unknown1.random_is_macro", "unknown1.random_param_width_bits",
    "unknown1.random_param_signextended", "unknown1.random_divisor",
    "unknown1.random_div_is_signed", "unknown1.random_mul_width_bits",
    "unknown1.ftol.cw_or_immediate", "unknown1.ftol.rounding",
    "unknown1.ftol.store_width_bits", "unknown1.ftol.return_width_bits",
    "unknown1.fp_sites", "unknown1.fp_sites_total",
    "unknown1.nonftol_fp_arg_sites",
    "unknown2.verdict", "unknown2.minuend", "unknown2.spilled_draw", "unknown2.live_draw",
    "unknown2.sub_dst", "unknown2.sub_src", "unknown2.sub_file", "unknown2.op",
    "unknown2.stored_reg", "unknown2.result_width_bits", "unknown2.return_load",
    "unknown2.call_files",
    "selfcheck.anchor_354e_count",
    "selfcheck.far_sites_with_reloc", "selfcheck.far_sites_total",
    "selfcheck.pushcs_sites_with_nop_pad", "selfcheck.pushcs_sites_total",
]

# fp_sites element shape (list of dicts, sorted by "call"):
#   {"call": int, "callee": "random"|"zrandom", "ftol": int,
#    "push": int, "push_reg": "ax"|"dx"|..., "narrowing": "LOW16_OF_FTOL"|other}

# Liveness fields: present, excluded from the diff, asserted non-empty and
# asserted to CHANGE between pristine and mutant runs.
LIVENESS = ["evidence.zrandom_text", "evidence.random_text", "evidence.ftol_text"]

# Provenance: present, excluded from the diff.
PROVENANCE = ["decoder.id", "decoder.engine", "decoder.engine_version",
              "decoder.route", "decoder.insns_decoded", "decoder.run_utc"]


def get(d, path, missing=KeyError):
    cur = d
    for k in path.split("."):
        if not isinstance(cur, dict) or k not in cur:
            if missing is KeyError:
                raise KeyError(path)
            return missing
        cur = cur[k]
    return cur


def canon(v):
    """Semantic core only, normalised: hex lowercased, site lists sorted."""
    out = {}
    for p in SEMANTIC_CORE:
        val = get(v, p, missing="<<MISSING>>")
        if isinstance(val, str):
            val = val.strip().lower()
        elif isinstance(val, list) and val and isinstance(val[0], int):
            val = sorted(val)
        elif isinstance(val, list) and val and isinstance(val[0], dict):
            val = sorted((dict(sorted(e.items())) for e in val), key=lambda e: e.get("call", -1))
        out[p] = val
    return out


# --------------------------------------------------------------------------
# 2.  Mutation set.  Each mutant is derived from the pristine bytes at run
#     time; nothing is stored.  `orig` is re-verified before patching, so a
#     stale offset fails loudly instead of silently mutating nothing.
# --------------------------------------------------------------------------
MUTANTS = [
    dict(
        id="M1_ORDER_FLIP", target="NOCTIS.EXE",
        why="make zrandom genuinely return draw2-draw1",
        patch=[(60774, "2bd0", "2bc2"), (60776, "8956fe", "8946fe")],
        expect={"unknown2.verdict": "RIGHT_TO_LEFT", "unknown2.minuend": "draw2",
                "unknown2.sub_dst": "ax", "unknown2.sub_src": "dx",
                "unknown2.stored_reg": "ax"},
        for_decoders=["ba", "bx"],
    ),
    dict(
        id="M2_PUSH_SWAP", target="NOCTIS.EXE",
        why="line-4089 site no longer pushes the low half of __ftol's result",
        patch=[(61560, "50", "52")],
        expect={"__fp_site__": (61562, {"push_reg": "dx"})},
        expect_not={"__fp_site_narrowing__": (61562, "LOW16_OF_FTOL")},
        for_decoders=["ba", "bx"],
    ),
    dict(
        id="M3_RC_BITS", target="NOCTIS.EXE",
        why="__ftol forces round-down instead of chop",
        patch=[(14455, "0c", "04")],
        expect={"unknown1.ftol.cw_or_immediate": 4, "unknown1.ftol.rounding": "DOWN"},
        for_decoders=["ba", "bx"],
    ),
    dict(
        id="M4_WRAP_CALL", target="NOCTIS.EXE",
        why="kill flandom's WRAP-ENCODED near call; catches rel16 arithmetic "
            "that is not done modulo 2**16 inside the frame",
        patch=[(37112, "3db1", "0000")],
        expect={"census.random.total": 374, "census.random.pushcs": 76},
        expect_absent_site=("census.random.sites", 37110),
        for_decoders=["ba", "bx"],
    ),
    dict(
        id="M5_FAR_CALL", target="NOCTIS.EXE",
        why="repoint one relocated far call away from random",
        patch=[("__first_far_random_segword__", None, "0000")],
        expect={"census.random.total": 374, "census.random.far": 297},
        for_decoders=["ba", "bx"],
    ),
    dict(
        id="M6_ANCHOR_KILL", target="NOCTIS.EXE",
        why="destroy the unique 35 4E LCG anchor; ba's route depends on it",
        patch=[(15982, "354e", "364e")],
        expect={"status": "LOCATION_FAILED", "selfcheck.anchor_354e_count": 0},
        for_decoders=["ba"],           # per-decoder liveness, NOT cross-diffed
    ),
    dict(
        id="M7_SYMTAB_KILL", target="DL.EXE",
        why="rename @zrandom$qi in the Borland symbol table; bx's route depends on it",
        patch=[(42265, "407a72616e646f6d24716900", "407a72426e646f6d24716900")],
        expect={"status": "LOCATION_FAILED"},
        for_decoders=["bx"],           # per-decoder liveness, NOT cross-diffed
    ),
]


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def gate_inputs():
    bad = []
    for name, (want, size) in BINARIES.items():
        p = os.path.join(MODULES, name)
        got = sha256_file(p)
        sz = os.path.getsize(p)
        if got != want or sz != size:
            bad.append("%s sha=%s size=%d (expected %s / %d)" % (name, got, sz, want, size))
    if bad:
        print("INPUT GATE FAILED -- reference binaries are not pristine:")
        for b in bad:
            print("   " + b)
        return False
    print("input gate OK: NOCTIS.EXE/DL.EXE/ST.EXE pristine")
    return True


def _first_far_random_segword(data):
    """File offset of the segment word of the lowest-addressed relocated
    far call to random.  Recomputed from bytes, never stored."""
    import struct
    hdr = struct.unpack_from("<H", data, 8)[0] * 16
    # random's entry is itself recomputed: unique 35 4E -> rand entry -> its
    # unique caller.  Kept deliberately simple here: rand entry is the start of
    # the 8B 0E .. 8B 1E .. BA .. B8 35 4E sequence.
    a = data.find(b"\x35\x4e")
    assert data.find(b"\x35\x4e", a + 1) < 0, "35 4E is not unique"
    rand_entry = a - 12
    i, sites = 0, []
    while True:
        i = data.find(b"\x9a", i)
        if i < 0 or i + 5 > len(data):
            break
        off, seg = struct.unpack_from("<HH", data, i + 1)
        if hdr + seg * 16 + off == rand_entry:
            sites.append(i)
        i += 1
    assert len(sites) == 1, "rand must have exactly one caller, got %d" % len(sites)
    random_entry = sites[0] - 3          # push bp; mov bp,sp
    i, far = 0, []
    while True:
        i = data.find(b"\x9a", i)
        if i < 0 or i + 5 > len(data):
            break
        off, seg = struct.unpack_from("<HH", data, i + 1)
        if hdr + seg * 16 + off == random_entry:
            far.append(i)
        i += 1
    assert far, "no far callers of random"
    return far[0] + 3


def build_mutant(m, outdir, tag):
    src = os.path.join(MODULES, m["target"])
    data = bytearray(open(src, "rb").read())
    for off, orig, new in m["patch"]:
        if off == "__first_far_random_segword__":
            off = _first_far_random_segword(bytes(data))
            orig = None
        nb = bytes.fromhex(new)
        if orig is not None:
            ob = bytes.fromhex(orig)
            if bytes(data[off:off + len(ob)]) != ob:
                raise SystemExit("STALE MUTATION %s at %d: found %s expected %s"
                                 % (m["id"], off, data[off:off + len(ob)].hex(), orig))
            if len(nb) != len(ob):
                raise SystemExit("mutation must be length-preserving")
        data[off:off + len(nb)] = nb
    # opaque name: the decoder must not be able to key on the filename
    dst = os.path.join(outdir, "bin_%s.exe" % tag)
    with open(dst, "wb") as f:
        f.write(data)
    return dst


def run_decoder(cmd, binpath):
    full = cmd.split() + ["--binary", binpath,
                          "--dl", os.path.join(MODULES, "DL.EXE"),
                          "--st", os.path.join(MODULES, "ST.EXE")]
    r = subprocess.run(full, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("decoder failed (%d): %s\n%s" % (r.returncode, " ".join(full), r.stderr[-2000:]))
    try:
        return json.loads(r.stdout)
    except Exception as e:
        raise SystemExit("decoder did not emit clean JSON: %s\n%s" % (e, r.stdout[:600]))


def check_one(v):
    errs = []
    for p in SEMANTIC_CORE:
        if get(v, p, missing="<<MISSING>>") == "<<MISSING>>":
            if v.get("status") == "LOCATION_FAILED":
                continue
            errs.append("missing core key: " + p)
    for p in LIVENESS:
        t = get(v, p, missing="")
        if not isinstance(t, str) or len(t) < 40:
            errs.append("liveness field empty/too short: " + p)
    for p in PROVENANCE[:3]:
        if get(v, p, missing="<<MISSING>>") == "<<MISSING>>":
            errs.append("missing provenance: " + p)
    if get(v, "decoder.insns_decoded", missing=0) < 200:
        errs.append("decoder.insns_decoded implausibly low -- did it actually disassemble?")
    return errs


def diff(a, b, label_a="A", label_b="B"):
    ca, cb = canon(a), canon(b)
    bad = []
    for k in SEMANTIC_CORE:
        if ca[k] != cb[k]:
            bad.append((k, ca[k], cb[k]))
    for k, x, y in bad:
        sx, sy = repr(x), repr(y)
        if len(sx) > 300:
            sx = sx[:300] + "..."
        if len(sy) > 300:
            sy = sy[:300] + "..."
        print("  MISMATCH %-42s %s=%s  %s=%s" % (k, label_a, sx, label_b, sy))
    return bad


def check_expect(v, m):
    bad = []
    for k, want in m.get("expect", {}).items():
        if k == "__fp_site__":
            call, fields = want
            site = next((s for s in get(v, "unknown1.fp_sites", missing=[]) if s.get("call") == call), None)
            if site is None:
                bad.append("fp site %d vanished" % call)
            else:
                for fk, fv in fields.items():
                    if str(site.get(fk, "")).lower() != str(fv).lower():
                        bad.append("fp site %d.%s = %r, expected %r" % (call, fk, site.get(fk), fv))
            continue
        got = get(v, k, missing="<<MISSING>>")
        if isinstance(got, str):
            got = got.lower()
        if isinstance(want, str):
            want = want.lower()
        if got != want:
            bad.append("%s = %r, expected %r" % (k, got, want))
    for k, want in m.get("expect_not", {}).items():
        if k == "__fp_site_narrowing__":
            call, forbidden = want
            site = next((s for s in get(v, "unknown1.fp_sites", missing=[]) if s.get("call") == call), None)
            if site is not None and str(site.get("narrowing", "")).lower() == forbidden.lower():
                bad.append("fp site %d still classified %s after the push was mutated" % (call, forbidden))
    if "expect_absent_site" in m:
        path, off = m["expect_absent_site"]
        if off in get(v, path, missing=[]):
            bad.append("%s still contains %d" % (path, off))
    return bad


def cmd_pin(ba_cmd, bx_cmd, outdir):
    ok = True
    os.makedirs(outdir, exist_ok=True)
    if not gate_inputs():
        return 2
    pristine = os.path.join(MODULES, "NOCTIS.EXE")

    print("\n== pristine ==")
    va = run_decoder(ba_cmd, pristine)
    vb = run_decoder(bx_cmd, pristine)
    for name, v in (("ba", va), ("bx", vb)):
        e = check_one(v)
        if e:
            ok = False
            print("  %s schema/liveness errors:" % name)
            for x in e:
                print("    " + x)
    if diff(va, vb, "ba", "bx"):
        ok = False
    else:
        print("  ba == bx on all %d semantic-core keys" % len(SEMANTIC_CORE))
    # invariants that must hold for BOTH, recomputed by each decoder
    for name, v in (("ba", va), ("bx", vb)):
        sc = v.get("selfcheck", {})
        if sc.get("far_sites_with_reloc") != sc.get("far_sites_total"):
            ok = False
            print("  %s: far call sites without a relocation on the segment word "
                  "-> byte-pattern false positives" % name)
        if sc.get("pushcs_sites_with_nop_pad") != sc.get("pushcs_sites_total"):
            ok = False
            print("  %s: push-cs sites without Borland's 0x90 pad" % name)

    base = {"ba": va, "bx": vb}
    seq = list(MUTANTS)
    _pyrandom.Random(20260805).shuffle(seq)
    for m in seq:
        tag = hashlib.sha256(m["id"].encode()).hexdigest()[:12]
        path = build_mutant(m, outdir, tag)
        print("\n== %s (%s) ==" % (m["id"], m["why"]))
        outs = {}
        for who, cmd in (("ba", ba_cmd), ("bx", bx_cmd)):
            if who not in m["for_decoders"]:
                continue
            v = run_decoder(cmd, path if m["target"] == "NOCTIS.EXE" else pristine)
            outs[who] = v
            bad = check_expect(v, m)
            if bad:
                ok = False
                print("  %s FAILED expectation:" % who)
                for x in bad:
                    print("    " + x)
            else:
                print("  %s reported the mutated answer" % who)
            for p in LIVENESS:
                if get(v, p, missing="") == get(base[who], p, missing="?") and m["id"] in ("M1_ORDER_FLIP", "M3_RC_BITS"):
                    ok = False
                    print("  %s LIVENESS FAIL: %s identical to pristine run" % (who, p))
        if len(outs) == 2 and m["id"] not in ("M6_ANCHOR_KILL", "M7_SYMTAB_KILL"):
            if diff(outs["ba"], outs["bx"], "ba", "bx"):
                ok = False
            else:
                print("  ba == bx on the mutant too")
        os.remove(path)
    print("\nPIN %s" % ("PASSED" if ok else "FAILED"))
    return 0 if ok else 1


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    c = argv[1]
    if c == "schema":
        print("\n".join(SEMANTIC_CORE))
        print("\n-- liveness (not diffed) --\n" + "\n".join(LIVENESS))
        print("\n-- provenance (not diffed) --\n" + "\n".join(PROVENANCE))
        return 0
    if c == "check":
        v = json.load(open(argv[2]))
        e = check_one(v)
        print("\n".join(e) if e else "verdict OK")
        return 1 if e else 0
    if c == "diff":
        a = json.load(open(argv[2]))
        b = json.load(open(argv[3]))
        bad = diff(a, b, os.path.basename(argv[2]), os.path.basename(argv[3]))
        print("IDENTICAL" if not bad else "%d MISMATCHES" % len(bad))
        return 1 if bad else 0
    if c == "mutants":
        os.makedirs(argv[2], exist_ok=True)
        for m in MUTANTS:
            tag = hashlib.sha256(m["id"].encode()).hexdigest()[:12]
            print(m["id"], "->", build_mutant(m, argv[2], tag))
        return 0
    if c == "pin":
        return cmd_pin(argv[2], argv[3], argv[4])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
