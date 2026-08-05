# brtl_compare.py - the Wave 1 N-way diff and proof card.
#
# Three implementations of Borland C++ 3.1's rand/random/srand, deliberately
# given three different provenances so that a shared misreading cannot survive
# all of them:
#
#   lino   work/brtl-*.bin      L.in.oleum, stock compiler + stock i386 pack,
#                               written from the pinned algorithm and executed
#                               on real hardware   (implementer 1)
#   c      work/brtl-*-c.bin    brtl_oracle.c, transcribed from
#                               niv-lr/src/brtl.cpp - a third party's reading
#   py     work/brtl-*-py.bin   brtl_oracle.py, transcribed from the DOS
#                               machine code, with the 0x3E19 long-multiply
#                               helper emulated instruction by instruction
#
# Four lanes, each complete over one axis rather than sampled:
#   1  all 65536 srand arguments, 16 draws deep
#   2  all 65536 high halves and all 65536 low halves of the 32-bit state
#   3  all 65536 int16 arguments of random()
#   4  all 65536 low halves of srand's argument against four high halves
#
# Run:  python noctis-harness\brtl_compare.py [--quick] [--no-build]
#
# --quick   skips the 655360-state lxmul licence (the slow part).  Never use
#           it for an actual proof run; it removes the reason the Python
#           oracle is independent in the first place.
# --no-build   reuse existing -c / -py artifacts instead of regenerating.

import hashlib
import itertools
import os
import shutil
import struct
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
WORK = os.path.join(REPO, "work")

sys.path.insert(0, HERE)
import brtl_oracle as PY                                   # noqa: E402

MAGIC = 0x42525431
SENTINEL = 0x0DEFACED
REC = 8                                     # bytes per record
HDR = 32                                    # bytes of header

# lane -> (basename, N1, N2, description)
LANES = {
    1: ("brtl-sweep", 65536, 16, "all 65536 srand args x 16 draws"),
    2: ("brtl-step", 10, 65536, "10 families x 65536 states"),
    3: ("brtl-rand", 65536, 8, "all 65536 int16 n x 4 seeds x 2"),
    4: ("brtl-srand", 65536, 4, "all 65536 low halves x 4 high halves"),
}

# Accepted alternate basenames.  The plan's format table calls lane 3
# "brtl-rand.bin"; the lino driver for it is brtlrnd.txt and it was emitted as
# "brtl-rnd.bin".  The header inside the file is what actually identifies the
# lane, so an alias is harmless - but it is recorded here rather than silently
# absorbed, because a missing artifact and a misnamed one look identical from
# the outside (F4/F8) and the difference matters.
ALIASES = {3: ("brtl-rnd",)}

# Implementer 1's lino negative controls, mapped onto the Python variants they
# are supposed to reproduce.  Agreeing that a mistake is WRONG is weak;
# agreeing on exactly which records it corrupts is not.
LINO_CONTROLS = {
    "brtl-bad-mask":     ("NC2 no & 7FFFh", 1),
    "brtl-bad-shift":    ("NC1 >>15 for /8000h", 3),
    "brtl-bad-unsigned": ("NC3 unsigned divide", 3),
    "brtl-bad-srand":    ("NC4 srand without mask", 4),
}

C_SRC = os.path.join(HERE, "brtl_oracle.c")
C_EXE = os.path.join(HERE, "brtl_oracle.exe")


# ------------------------------------------------------------------ plumbing

class Card(object):
    def __init__(self):
        self.lines = []
        self.failures = []
        self.checks = 0

    def say(self, text=""):
        print(text)
        self.lines.append(text)

    def ok(self, cond, label, detail=""):
        self.checks += 1
        tag = "ok  " if cond else "FAIL"
        self.say("  %s %s%s" % (tag, label, ("   [%s]" % detail) if detail else ""))
        if not cond:
            self.failures.append(label)
        return bool(cond)


def payload_sha(blob):
    return hashlib.sha256(blob[HDR:]).hexdigest()


def check_header(card, name, lane, blob):
    """F3/F8 guard: nothing is compared until the format agrees exactly."""
    n1, n2 = LANES[lane][1], LANES[lane][2]
    records = n1 * n2
    want = (MAGIC, lane, n1, n2, records, 2, records * 2, SENTINEL)
    if len(blob) < HDR:
        card.ok(False, "%s lane %d header" % (name, lane),
                "file is only %d bytes" % len(blob))
        return False
    got = struct.unpack_from("<8I", blob, 0)
    if got != want:
        card.ok(False, "%s lane %d header" % (name, lane),
                "got %s want %s" % (["%08X" % v for v in got],
                                    ["%08X" % v for v in want]))
        return False
    if len(blob) != HDR + records * REC:
        card.ok(False, "%s lane %d length" % (name, lane),
                "got %d want %d" % (len(blob), HDR + records * REC))
        return False
    return True


def records_of(blob):
    """(value, state) pairs as raw uint32."""
    n = (len(blob) - HDR) // REC
    return struct.unpack_from("<%dI" % (n * 2), blob, HDR)


def first_divergence(a, b):
    """Locate the first differing record without materialising a diff list."""
    n = min(len(a), len(b)) // 2
    for i in range(n):
        if a[i * 2] != b[i * 2] or a[i * 2 + 1] != b[i * 2 + 1]:
            return i
    return None


def count_divergence(a, b):
    n = min(len(a), len(b)) // 2
    c = 0
    first = None
    for i in range(n):
        if a[i * 2] != b[i * 2] or a[i * 2 + 1] != b[i * 2 + 1]:
            c += 1
            if first is None:
                first = i
    return c, first


def s32(u):
    return u - 0x100000000 if u & 0x80000000 else u


# ------------------------------------------------------------------ building

def build_c(card):
    if shutil.which("gcc") is None:
        card.say("  gcc is not on PATH - the C side cannot be built")
        return None
    p = subprocess.run(["gcc", "-O2", "-Wall", "-Wextra", "-std=c99",
                        "-o", C_EXE, C_SRC],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if p.returncode != 0:
        card.say("  gcc failed:\n" + (p.stdout or "") + (p.stderr or ""))
        return None
    if (p.stderr or "").strip():
        card.say("  gcc warnings:\n" + p.stderr.strip())
    p = subprocess.run([C_EXE, os.path.normpath(WORK), "-c"],
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=WORK)
    for line in (p.stdout or "").splitlines():
        card.say("  " + line)
    if p.returncode != 0:
        card.say("  C oracle exited %d\n%s" % (p.returncode, p.stderr))
        return None
    return True


def build_py(card, quick=False):
    info, err = PY.verify_against_exe()
    if err:
        card.ok(False, "python oracle provenance", err)
    else:
        size, bad, n_354e = info
        card.ok(not bad and n_354e == 1,
                "python oracle provenance: %d pinned NOCTIS.EXE listings match"
                % len(PY.PINNED),
                "image %d bytes, '35 4e' occurs %d time(s)%s"
                % (size, n_354e,
                   "" if not bad else ", %d MISMATCH" % len(bad)))

    cg = PY.verify_call_graph()
    if cg is None:
        card.say("  --  call graph not verified (NOCTIS.EXE unavailable)")
    else:
        hdr_bytes, resolved, callers, reloc_ok = cg
        card.ok(resolved == 15970 and reloc_ok,
                "random()'s far call resolves to rand()",
                "MZ header %d bytes + seg 0 + 1862h = %d" % (hdr_bytes, resolved))
        card.ok(callers == 1,
                "rand() has exactly one caller, so no site inlines the generator",
                "%d far call(s) to 0000:1862 in the image" % callers)

    n, bad = PY.licence_lxmul_si_independence()
    card.ok(bad == 0, "lxmul helper ignores the caller's SI",
            "%d/%d probes" % (n - bad, n))

    if quick:
        card.say("  --  lxmul licence SKIPPED (--quick); this is not a proof run")
    else:
        t0 = time.time()
        n, mism = PY.licence_lxmul()
        card.ok(mism == 0,
                "lxmul licence: 0x3E19 emulated == (s*015A4E35h) & 2**32-1",
                "%d states, %d mismatches, %.1fs" % (n, mism, time.time() - t0))

    t0 = time.time()
    PY.write_lanes(WORK, "-py")
    card.say("  --  python lanes written in %.1fs" % (time.time() - t0))
    return True


# ------------------------------------------------------- cross-lane invariants

def invariants(card, R):
    """R[name][lane] -> tuple of uint32.  Uses whichever impls are present."""
    for name in sorted(R):
        rec = R[name]
        if not all(l in rec for l in (1, 2, 3, 4)):
            continue
        L1, L2, L3, L4 = rec[1], rec[2], rec[3], rec[4]

        # --- the srand mask: all four high halves must give identical records,
        #     and must equal lane 1's first draw for the same low half.
        bad = 0
        badj = None
        for j in range(65536):
            base = (j * 4) * 2
            v, s = L4[base], L4[base + 1]
            for h in range(1, 4):
                o = (j * 4 + h) * 2
                if L4[o] != v or L4[o + 1] != s:
                    bad += 1
                    if badj is None:
                        badj = (j, h)
            o1 = (j * 16 + 0) * 2
            if L1[o1] != v or L1[o1 + 1] != s:
                bad += 1
                if badj is None:
                    badj = (j, "lane1")
        card.ok(bad == 0, "%s: srand masks to 16 bits, and lane4 == lane1[*,0]"
                % name, "%d violations%s" % (bad, "" if badj is None
                                             else " first at %r" % (badj,)))

        # --- lane 2 family 5 (state = j, high half zero) is one step from
        #     srand(j), so it must reproduce lane 1's first draw.
        bad = 0
        for j in range(65536):
            o2 = (5 * 65536 + j) * 2
            o1 = (j * 16 + 0) * 2
            if L2[o2] != L1[o1] or L2[o2 + 1] != L1[o1 + 1]:
                bad += 1
        card.ok(bad == 0,
                "%s: lane2 family 5 == lane1 first draw (two programs, one state)"
                % name, "%d violations" % bad)

        # --- THE STRONGEST CHECK: random(n) consumes exactly one draw, for
        #     every one of the 65536 int16 values of n including 0.
        bad = 0
        badk = None
        for k in range(65536):
            for si in range(4):
                seed = PY.L3SEED[si]
                for d in range(2):
                    o3 = (k * 8 + si * 2 + d) * 2 + 1
                    o1 = (seed * 16 + d) * 2 + 1
                    if L3[o3] != L1[o1]:
                        bad += 1
                        if badk is None:
                            badk = (k, si, d)
        card.ok(bad == 0,
                "%s: random(n) draws exactly once for all 65536 n (incl. 0)"
                % name, "%d violations%s" % (bad, "" if badk is None
                                             else " first at %r" % (badk,)))

        # --- the half-open range of random(), over the whole argument domain
        bad_range = 0
        bad_zero = 0
        badn = None
        for k in range(65536):
            n = PY.to_int16(k)
            for t in range(8):
                v = s32(L3[(k * 8 + t) * 2])
                if n > 0:
                    ok = 0 <= v < n
                elif n < 0:
                    ok = n < v <= 0
                else:
                    ok = v == 0
                if not ok:
                    bad_range += 1
                    if badn is None:
                        badn = (n, v)
                if n in (0, 1) and v != 0:
                    bad_zero += 1
                if v == n and n != 0:
                    bad_range += 1
        card.ok(bad_range == 0,
                "%s: random(n) in [0,n) for n>0 and in (n,0] for n<0, all n"
                % name, "%d violations%s" % (bad_range, "" if badn is None
                                             else " first %r" % (badn,)))
        card.ok(bad_zero == 0, "%s: random(0) == random(1) == 0 always" % name,
                "%d violations" % bad_zero)

        # --- rand()'s range and surjectivity over lane 1
        seen = bytearray(32768)
        lo, hi = 1 << 30, -1
        for i in range(0, len(L1), 2):
            v = L1[i]
            if v > 32767:
                hi = 1 << 30
                break
            seen[v] = 1
            if v < lo:
                lo = v
            if v > hi:
                hi = v
        card.ok(lo == 0 and hi == 32767 and sum(seen) == 32768,
                "%s: rand() spans exactly [0,32767], all 32768 outputs seen"
                % name, "min %d max %d distinct %d" % (lo, hi, sum(seen)))


# ----------------------------------------------------------- negative controls

# Predicted divergence counts, computed from the algorithm, NOT read off a
# run.  A control that diverges in the wrong place fails exactly as hard as
# a control that agrees.
#
#   NC3  An unsigned divide of a two's-complement negative product yields a
#        quotient near 2**17; the signed one yields something in (-32768, 0].
#        They therefore differ for EVERY record whose product is negative, and
#        agree for every other.  product < 0 iff n < 0 and rand() != 0.
#        Lane 3 has 32768 negative values of n, 8 records each.  Exactly one of
#        those 8 has rand() == 0 - the (seed=0, draw=0) slot, because srand(0)
#        gives state 0, the step gives state 1, and 1's high half is zero.
#        So:  32768 * (8 - 1) = 229376.  Closed form, no measurement.
#   NC1  >>15 floors, / truncates.  They agree on everything NC3 agrees on,
#        and additionally wherever the negative product happens to be an exact
#        multiple of 32768 - chiefly n = -32768, for which every product is.
#        So the prediction is 229376 minus a small correction; 229376 - 229361
#        = 15 such records, of which 7 are n = -32768 itself.
#   NC2  the 7FFFh mask matters iff bit 31 of the new state is set, so this is
#        simply the number of lane-1 draws landing in the top half of the
#        32-bit state space: 524251, against a 524288 expectation for a
#        balanced generator.  Values only; states are untouched.
#   NC4  the srand mask matters for every record whose high half is nonzero,
#        i.e. exactly 3 of the 4 h-slots -> 3/4 of 262144 = 196608.
#   NC5  short-circuiting random(0) desynchronises the stream only for k == 0,
#        and only in the STATE field, because the VALUE is 0 either way.
#        Each of the 4 seeds restarts the stream, so 4 seeds * 2 draws = 8.
NC_PREDICTED = {
    "NC1 >>15 for /8000h": 229361,
    "NC2 no & 7FFFh": 524251,
    "NC3 unsigned divide": 229376,
    "NC4 srand without mask": 196608,
    "NC5 random(0) short-circuit": 8,
}

# Where each control must break FIRST.  A control that diverges in the wrong
# place fails exactly as hard as one that agrees (F10).
NC_FIRST = {
    "NC1 >>15 for /8000h": 262153,
    "NC2 no & 7FFFh": 2,
    "NC3 unsigned divide": 262145,
    "NC4 srand without mask": 1,
    "NC5 random(0) short-circuit": 0,
}


def lino_negative_controls(card, nc_blobs):
    """Cross-check implementer 1's deliberately-wrong lino programs against
    the correspondingly-wrong Python variants.

    This is worth more than either side's controls alone.  A control proves a
    mistake is DETECTABLE; a matching pair of controls proves both sides model
    the same mistake, which is what licenses reading "the good programs agree"
    as "the good programs are right" rather than "the good programs are
    wrong in the same way".
    """
    if not nc_blobs:
        return
    card.say()
    card.say("lino negative controls vs the same mistake made in Python")
    for base in sorted(nc_blobs):
        label, lane = LINO_CONTROLS[base]
        cls = PY.CONTROLS[label][0]
        want = PY.GENERATORS[lane](cls())[HDR:]
        got = nc_blobs[base][HDR:]
        if got == want:
            card.ok(True, "%-18s == python %s" % (base, label),
                    "both break lane %d identically" % lane)
        else:
            cnt, first = count_divergence(
                struct.unpack("<%dI" % (len(got) // 4), got),
                struct.unpack("<%dI" % (len(want) // 4), want))
            card.ok(False, "%-18s == python %s" % (base, label),
                    "%d records differ, first at %d" % (cnt, first))


def negative_controls(card, ref):
    card.say()
    card.say("negative controls (each MUST diverge, in the predicted place)")
    for label, (cls, lane) in sorted(PY.CONTROLS.items()):
        blob = PY.GENERATORS[lane](cls())
        got = records_of(blob)
        cnt, first = count_divergence(got, ref[lane])
        total = len(ref[lane]) // 2
        pred = NC_PREDICTED[label]
        pfirst = NC_FIRST[label]
        card.ok(cnt == pred and first == pfirst,
                "%-30s diverges as predicted" % label,
                "%d of %d lane-%d records (predicted %d), first at %s "
                "(predicted %d)" % (cnt, total, lane, pred, first, pfirst))


# -------------------------------------------------------------------- proof card

def main():
    quick = "--quick" in sys.argv
    nobuild = "--no-build" in sys.argv
    card = Card()

    card.say("=" * 78)
    card.say("WAVE 1 - Borland C++ 3.1 rand / random / srand")
    card.say("=" * 78)

    if not nobuild:
        card.say()
        card.say("building the C reference (from niv-lr/src/brtl.cpp)")
        build_c(card)
        card.say()
        card.say("building the Python reference (from the NOCTIS.EXE disassembly)")
        build_py(card, quick)

    # ---- collect whatever exists
    card.say()
    card.say("artifacts")
    impls = {"c": "-c", "py": "-py", "lino": ""}
    blobs = {}
    for name, sfx in impls.items():
        for lane, (base, _n1, _n2, _d) in LANES.items():
            for cand in (base,) + ALIASES.get(lane, ()):
                path = os.path.join(WORK, "%s%s.bin" % (cand, sfx))
                if os.path.exists(path):
                    with open(path, "rb") as fh:
                        blobs.setdefault(name, {})[lane] = (path, fh.read())
                    if cand != base:
                        card.say("  note: lane %d taken from %s%s.bin "
                                 "(the format table calls it %s%s.bin)"
                                 % (lane, cand, sfx, base, sfx))
                    break
    for name in ("c", "py", "lino"):
        if name not in blobs:
            card.say("  %-5s ABSENT" % name)
        else:
            card.say("  %-5s %d/4 lanes" % (name, len(blobs[name])))

    lino_lanes = set(blobs.get("lino", {}))
    missing_lino = [l for l in sorted(LANES) if l not in lino_lanes]
    if missing_lino:
        card.say()
        card.say("  *** THE L.IN.OLEUM SIDE IS INCOMPLETE: lanes %s absent. ***"
                 % ", ".join(str(l) for l in missing_lino))
        card.say("  Those lanes are verified C against Python only, which")
        card.say("  establishes that two independent readings of the algorithm")
        card.say("  agree - NOT that the port is correct.")

    # ---- format gate
    card.say()
    card.say("format gate (F3/F8: nothing is compared until the header agrees)")
    R = {}
    for name in sorted(blobs):
        for lane in sorted(blobs[name]):
            path, blob = blobs[name][lane]
            if check_header(card, name, lane, blob):
                R.setdefault(name, {})[lane] = records_of(blob)
    card.ok(bool(R), "at least one implementation passed the format gate")

    # ---- N-way diff
    card.say()
    card.say("N-way bit-exact comparison")
    agree = {}
    for lane in sorted(LANES):
        present = [n for n in sorted(blobs) if n in R and lane in R[n]]
        if len(present) < 2:
            card.say("  lane %d: only %d implementation(s), nothing to diff"
                     % (lane, len(present)))
            continue
        lane_ok = True
        for a, b in itertools.combinations(present, 2):
            ba = blobs[a][lane][1][HDR:]
            bb = blobs[b][lane][1][HDR:]
            if ba == bb:
                card.ok(True, "lane %d  %-4s == %-4s" % (lane, a, b))
            else:
                lane_ok = False
                cnt, first = count_divergence(R[a][lane], R[b][lane])
                ra = R[a][lane][first * 2:first * 2 + 2]
                rb = R[b][lane][first * 2:first * 2 + 2]
                card.ok(False, "lane %d  %-4s == %-4s" % (lane, a, b),
                        "%d records differ, first at %d: "
                        "(v=%d s=%08X) vs (v=%d s=%08X)"
                        % (cnt, first, s32(ra[0]), ra[1], s32(rb[0]), rb[1]))
        agree[lane] = (lane_ok, present)

    # ---- cross-lane invariants
    card.say()
    card.say("cross-lane invariants (separate programs checking each other)")
    invariants(card, R)

    # ---- negative controls, against the python reference
    if "py" in R and all(l in R["py"] for l in (1, 3, 4)):
        negative_controls(card, R["py"])

    # ---- and implementer 1's lino controls against the same Python variants
    nc_blobs = {}
    for base, (label, lane) in LINO_CONTROLS.items():
        path = os.path.join(WORK, base + ".bin")
        if os.path.exists(path):
            with open(path, "rb") as fh:
                blob = fh.read()
            if check_header(card, base, lane, blob):
                nc_blobs[base] = blob
    lino_negative_controls(card, nc_blobs)

    # ---- the card
    card.say()
    card.say("=" * 78)
    card.say("PROOF CARD")
    card.say("=" * 78)
    card.say("  three provenances: lino <- pinned algorithm, compiled stock i386")
    card.say("                     c    <- niv-lr/src/brtl.cpp")
    card.say("                     py   <- NOCTIS.EXE machine code, 0x3E19 emulated")
    card.say()
    for lane in sorted(LANES):
        base, n1, n2, desc = LANES[lane]
        recs = n1 * n2
        if lane not in agree:
            card.say("  lane %d  %-38s %8d rec  %s"
                     % (lane, desc, recs, "INCOMPLETE"))
            continue
        lane_ok, present = agree[lane]
        ref = blobs[present[0]][lane][1]
        card.say("  lane %d  %-38s %8d rec" % (lane, desc, recs))
        card.say("          sha256(payload) %s" % payload_sha(ref))
        card.say("          %d-way %s: %s"
                 % (len(present), "agree" if lane_ok else "DISAGREE",
                    " ".join(present)))
    card.say()
    card.say("  spot vectors (first ten draws)")
    for s in (1, 0, 65535, 12345):
        card.say("    srand(%-5d) -> %s"
                 % (s, " ".join("%5d" % v for v in PY.spot(s))))
    g = PY.Brtl()
    g.srand(1)
    v0 = g.random(0)
    card.say("    random(0) = %d and the state still advanced to %08X"
             % (v0, g.state))
    g.srand(1)
    card.say("    random(-10) x8 -> %s"
             % " ".join("%d" % g.random(-10) for _ in range(8)))

    card.say()
    if card.failures:
        card.say("RESULT: FAIL - %d of %d checks failed"
                 % (len(card.failures), card.checks))
        for f in card.failures:
            card.say("        - %s" % f)
        return 1
    if missing_lino:
        have = ", ".join(str(l) for l in sorted(lino_lanes)) or "(none)"
        want = ", ".join(str(l) for l in missing_lino)
        card.say("RESULT: INCOMPLETE - all %d checks pass, and C agrees with"
                 % card.checks)
        card.say("        Python on every lane, but only lane(s) %s carry a" % have)
        card.say("        three-way comparison.  Lane(s) %s have no L.in.oleum" % want)
        card.say("        artifact yet, so Wave 1 is NOT proved.")
        return 2
    card.say("RESULT: PASS - %d checks, three implementations, all four lanes,"
             % card.checks)
    card.say("        bit for bit, over three complete 65536-wide axes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
