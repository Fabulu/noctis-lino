r"""su_corpus.py - the oracle-side fixture for Wave 7a.

Two disjoint kinds of case, never mixed in a grading row:

  CAPTURE cases    - one per artefact in tests/gen/recon_w7a/out.  Every input
                     is either derived from Wave 4's already-graded nearstar
                     generation (seedval, owner, nearstar rgb) or read out of
                     the artefact itself (plwp, and for the four secs-dependent
                     types the fitted (long)(k*secs) from su_secs.json).
                     These grade EXACT against the binary's own buffer.

  SYNTHETIC cases  - inputs no capture covers: colorbase 255, type 10, the
                     moon aliasing, negative cx, case 4's r>20 branch.  These
                     have NO oracle.  They exist only for three-way agreement
                     and are labelled BOUNDED wherever they are reported.

The file emitted here is read by su_ref.exe and by su_spec.py, and it is the
same file for both, so a case cannot exist on one side and not the other.
Line format:

    id type seedval_hex64 colorbase secs_scaled use_scaled plwp owner nr ng nb
"""

import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import su_seed

RECON = r"C:\programmieren\linoleum\tests\gen\recon_w7a\out"
SECSJSON = os.path.join(HERE, "su_secs.json")

# plwp and (long)(k*secs), recovered per capture.
#
# plwp: the manifest's pixel detector reports it for eight captures, declines
# for two, and is WRONG BY 8 for one - lane_b00_t2's band really starts at
# column 142, not 134, and the post-terminator ssmooth passes blur the edge
# enough to fool a threshold detector.  Every value below was instead obtained
# by exhaustive search over all 360 possibilities against the captured 64,800
# bytes, and in every case EXACTLY ONE value produces a byte-exact map.  That
# is a measurement with a stated search space, not a tolerance.
#
# secs: see su_solve.py.  For lane_b03_t3 it is SOLVED algebraically from the
# cloud geometry with no window assumed; the others are searched over the
# window that solution establishes.  All four land within 3.3 - 9.0 guest
# seconds of the guest's own `time 12:00:00`, which is an independent
# consistency check that nothing in the search enforced.
SOLVED = {
    # tag              plwp   (long)(k*secs)   k    secs implied
    "jrot_b01_t0":   (343,    None,           None),
    "jrot_b07_t1":   ( 59,    None,           None),
    "lane_b00_t2":   (107,     556778145,     10),   # 1344168003.3
    "lane_b03_t3":   (102,    1344168009,      1),   # 1344168009
    "lane_b09_t4":   ( 71,    None,           None),
    "lane_b02_t5":   (155,    -954298218,     60),   # 1344168006.77
    "jrot_b00_t6":   (148,    -954298127,     60),   # 1344168008.28
    "parsis_b09_t7": (217,    None,           None),
    "lane_b07_t8":   (274,    None,           None),
    "jrot_b02_t9":   (323,    None,           None),
}
PLWP_SOLVED = {t: v[0] for t, v in SOLVED.items()}


def capture_cases():
    man = json.load(open(os.path.join(RECON, "manifest.json")))
    secs = {}
    if os.path.exists(SECSJSON):
        secs = json.load(open(SECSJSON))
    rows = []
    for e in man:
        tag = e["tag"]
        inp = su_seed.body_inputs(*e["star"], e["body"])
        plwp = PLWP_SOLVED.get(tag, e["terminator"]["plwp"])
        ss, us = 0, 0
        if tag in SOLVED and SOLVED[tag][1] is not None:
            ss, us = SOLVED[tag][1], 1
        rows.append(dict(
            tag=tag, kind="capture", id=e["body"], type=e["planet_type"],
            seedval=inp["seedval"], colorbase=inp["colorbase"],
            secs_scaled=ss, use_scaled=us,
            plwp=-1 if plwp is None else plwp,
            owner=inp["owner"], rgb=inp["rgb"],
            manifest=e, ptype_from_ns=inp["ptype"]))
    return rows


SYNTH = [
    # (tag, type, seedval, colorbase, plwp, owner, rgb)   -- no oracle exists
    ("syn_cb255_t3",  3, 66679905.168462224, 255,  10, -1, (63, 30, 20)),
    ("syn_type10",   10, 1.0,                192,   0, -1, (63, 63, 63)),
    ("syn_moon_t1",   1, 45123.5,            128, 200,  3, (30, 50, 63)),
    ("syn_moon_t0",   0, -8123.75,           128,   0,  2, (40, 10, 10)),
    ("syn_t4_big",    4, 7.0,                192, 359, -1, (32, 32, 32)),
    ("syn_t2_neg",    2, -1234567.25,        192, 325, -1, (63, 58, 40)),
    ("syn_t6_wrap",   6, 999999.5,           192, 340, -1, (10, 20, 63)),
    ("syn_t5_edge",   5, 3.0,                192,   1, -1, (48, 32, 63)),
    ("syn_t9_zero",   9, 0.0,                192, 180, 19, (0, 63, 63)),
    ("syn_t8_neg",    8, -0.5,               192,  90, -1, (63, 32, 16)),
    ("syn_t7_tiny",   7, 1e-9,               192,  45, -1, (32, 40, 32)),
    ("syn_t3_neg",    3, -66679905.5,        192, 137, -1, (63, 30, 20)),
    # COV-5 witness: a type 2 whose random(3) fires, so psmooth_grays runs.
    # No capture in out/ has knot1 == 1, found by search over seedvals.
    ("syn_t2_knot1",  2, 3703.5,              192, 100, -1, (63, 58, 40)),
    # COV-6 witness, and a REFINEMENT of it.  SEEDTRUNC (truncate seedval
    # before adding 4112) is invisible unless the sign FLIPS across the
    # addition, i.e. unless seedval is in (-4112, 0) and non-integral.  Four
    # of the ten captures do have negative fractional seedvals, but all four
    # have |seedval| >> 4112, so truncation commutes and none of them can see
    # the defect.  "negative fractional seedval" is not a sharp enough
    # coverage criterion; this is.
    ("syn_seedflip",  1, -2000.5,             192,  70, -1, (30, 50, 63)),
]


def synth_cases():
    rows = []
    for tag, ty, sv, cb, plwp, owner, rgb in SYNTH:
        rows.append(dict(tag=tag, kind="synthetic", id=max(owner, 0) + 1,
                         type=ty, seedval=sv, colorbase=cb,
                         secs_scaled=1234567, use_scaled=1, plwp=plwp,
                         owner=owner, rgb=rgb))
    return rows


def all_cases(with_synth=True):
    rows = capture_cases()
    if with_synth:
        rows += synth_cases()
    return rows


def write(path, rows):
    with open(path, "w") as fh:
        fh.write("# id type seedval_hex64 colorbase secs_scaled use_scaled "
                 "plwp owner nr ng nb\n")
        for r in rows:
            bits = struct.unpack("<Q", struct.pack("<d", r["seedval"]))[0]
            fh.write("%d %d %016x %d %d %d %d %d %d %d %d\n" % (
                r["id"], r["type"], bits, r["colorbase"], r["secs_scaled"],
                r["use_scaled"], r["plwp"], r["owner"],
                r["rgb"][0], r["rgb"][1], r["rgb"][2]))
    return path


if __name__ == "__main__":
    rows = all_cases()
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "su_corpus.spc")
    write(out, rows)
    for r in rows:
        print("%-16s %-9s type=%-2d cb=%-3d plwp=%-4d owner=%-3d ss=%d" % (
            r["tag"], r["kind"], r["type"], r["colorbase"], r["plwp"],
            r["owner"], r["secs_scaled"]))
    print("wrote", out, len(rows), "cases")
