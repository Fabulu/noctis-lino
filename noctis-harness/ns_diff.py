"""ns_diff.py -- the N-way comparator for NSTOPO files.

Comparisons are made in STRICT ORDER and stop at the first class that fails,
because a desynchronised RNG stream corrupts everything downstream of it and
reporting the wreckage as a percentage hides the one address that matters:

    1  HEADER        magic, version, stride, record count
    2  DRAW-COUNT    r11 total and r12..r19 per phase.  A mismatch here names
                     the phase, and the phase names the control-flow bug.
                     No value is compared for that system.
    3  TOPOLOGY      r5 nop, r6 nob, r20..r99 the per-body words.  A mismatch
                     here with the counts agreeing is a formula or a branch
                     VALUE bug, not a stream bug.
    4  IDENTITY      r3 class, r4 seed, r7 starnop, r9/r10 identity bits.

Also here, because they are checks on the comparator's own subjects:

    ns_diff.py --sites        exactly eleven float-argument draw sites in
                              ns_ref.c and eleven in ns_spec.py, no more and
                              no fewer.  Scope creep back into geometry fails
                              the build.
    ns_diff.py --overflow NSIN  build the seed chain both the u32 way and
                              the signed-plus--fwrapv way and require the two
                              defined readings to agree, byte for byte.
    ns_diff.py --jitter NSIN  perturb nearstar_ray and require the TOPOLOGY
                              not to move.  This is the empirical proof that
                              the tree is float-free, which is what licenses
                              ns_ref.c and ns_spec.py computing geometry in
                              plain binary64 instead of on an x87 stack.
    ns_diff.py --ledger A B   compare two per-draw ledgers and print the
                              first divergence as (system, draw, site).

Usage:
    python ns_diff.py a.nstopo b.nstopo [c.nstopo ...]
    python ns_diff.py --sites
    python ns_diff.py --overflow corpus.nsin
    python ns_diff.py --jitter corpus.nsin
    python ns_diff.py --ledger a.nsled b.nsled
"""

import os
import re
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import ns_spec as N                                             # noqa: E402

PHASE = N.PHASES
PRODUCER = {0: "lino", 1: "C", 2: "python"}


def load(path):
    hdr, recs = N.read_nstopo(path)
    return hdr, recs


def compare(paths, verbose=True, limit=8):
    sides = [(p, ) + load(p) for p in paths]
    names = [os.path.basename(p) for p in paths]
    fails = []

    # ---- 1 HEADER
    ref = sides[0]
    for (p, h, r) in sides[1:]:
        if h["nrec"] != ref[1]["nrec"] or h["stride"] != ref[1]["stride"] \
           or h["mode"] != ref[1]["mode"]:
            fails.append(("HEADER", "%s %r vs %s %r"
                          % (os.path.basename(p), h,
                             os.path.basename(ref[0]), ref[1])))
    if fails:
        _report(fails, verbose)
        return fails

    if ref[1]["mode"] == 1:
        for (p, h, d) in sides[1:]:
            for c in range(N.STAR_CLASSES):
                if d[c] != ref[2][c]:
                    fails.append(("DIGEST", "class %d: %s %r vs %s %r"
                                  % (c, os.path.basename(p), d[c],
                                     os.path.basename(ref[0]), ref[2][c])))
        if fails:
            _report(fails, verbose)
        elif verbose:
            tot = sum(ref[2][c][2] for c in range(N.STAR_CLASSES))
            print("digests agree across %d sides over %d systems in 12 classes:"
                  % (len(sides), tot))
            for c in range(N.STAR_CLASSES):
                lo, hi, n = ref[2][c]
                print("  class %2d  n=%6d  %08X%08X" % (c, n, hi, lo))
        return fails

    nrec = ref[1]["nrec"]

    # ---- 2 DRAW-COUNT, 3 TOPOLOGY, 4 IDENTITY -- in that order, and the
    # first class that produces any failure at all is the only one reported
    classes = (
        ("DRAW-COUNT", list(range(11, 20))),
        ("TOPOLOGY", [5, 6] + list(range(20, 100))),
        ("IDENTITY", [3, 4, 7, 8, 9, 10]),
    )
    for cname, fields in classes:
        for i in range(nrec):
            a = ref[2][i]
            for (p, _h, rr) in sides[1:]:
                b = rr[i]
                for f in fields:
                    if a[f] != b[f]:
                        fails.append((cname, _address(cname, i, f, a, b,
                                                      os.path.basename(ref[0]),
                                                      os.path.basename(p))))
                        break
                if fails and len(fails) >= limit:
                    break
            if fails and len(fails) >= limit:
                break
        if fails:
            _report(fails, verbose)
            return fails

    if verbose:
        print("all %d systems agree bit for bit across %d sides: %s"
              % (nrec, len(sides), ", ".join(names)))
        print("  producers: %s"
              % ", ".join(PRODUCER.get(s[1]["producer"], "?") for s in sides))
    return fails


def _address(cname, i, f, a, b, na, nb):
    if cname == "DRAW-COUNT":
        if f == 11:
            what = "total draws"
        else:
            what = "phase %s draws" % PHASE[f - 12]
        return ("system %d (x=%d y=%d z=%d, class %d): %s -- %s %d vs %s %d"
                % (i, _s32(a[0]), _s32(a[1]), _s32(a[2]), a[3], what,
                   na, a[f], nb, b[f]))
    if cname == "TOPOLOGY":
        if f == 5:
            what = "nop"
        elif f == 6:
            what = "nob"
        else:
            k = f - 20
            what = ("body %d (type/owner/moonid %s vs %s)"
                    % (k, _body(a[f]), _body(b[f])))
        return ("system %d (x=%d y=%d z=%d, class %d): %s -- %s %d vs %s %d"
                % (i, _s32(a[0]), _s32(a[1]), _s32(a[2]), a[3], what,
                   na, a[f], nb, b[f]))
    what = {3: "class", 4: "seed", 7: "starnop", 8: "labeled",
            9: "identity lo", 10: "identity hi"}[f]
    return ("system %d (x=%d y=%d z=%d): %s -- %s %d vs %s %d"
            % (i, _s32(a[0]), _s32(a[1]), _s32(a[2]), what, na, a[f], nb, b[f]))


def _body(w):
    if w == 0xFFFFFFFF:
        return "absent"
    return "(%d,%d,%d)" % (w & 0xFF, ((w >> 8) & 0xFF) - 1, (w >> 16) & 0xFF)


def _s32(v):
    return v - (1 << 32) if v & 0x80000000 else v


def _report(fails, verbose):
    if not verbose:
        return
    print("FAIL: %s" % fails[0][0])
    for c, msg in fails:
        print("  %-11s %s" % (c, msg))


# ------------------------------------------------------------- the ledgers

def read_ledger(path):
    blob = open(path, "rb").read()
    n = len(blob) // 12
    out = []
    cur = None
    for i in range(n):
        a, b, c = struct.unpack_from("<3i", blob, 12 * i)
        if a == -1:
            cur = []
            out.append((b, cur))
        elif cur is not None:
            cur.append((a, b, c))
    return out


def compare_ledgers(pa, pb, verbose=True):
    la, lb = read_ledger(pa), read_ledger(pb)
    if len(la) != len(lb):
        print("FAIL LEDGER: %d systems vs %d" % (len(la), len(lb)))
        return 1
    for (ka, ra), (kb, rb) in zip(la, lb):
        if ka != kb:
            print("FAIL LEDGER: system id %d vs %d" % (ka, kb))
            return 1
        for d, (ea, eb) in enumerate(zip(ra, rb)):
            if ea != eb:
                print("FAIL LEDGER: system %d, draw %d: "
                      "%s is at NOCTIS-0.CPP:%d random(%d)->%d, "
                      "%s is at NOCTIS-0.CPP:%d random(%d)->%d"
                      % (ka, d, os.path.basename(pa), ea[0], ea[1], ea[2],
                         os.path.basename(pb), eb[0], eb[1], eb[2]))
                return 1
        if len(ra) != len(rb):
            print("FAIL LEDGER: system %d, %d draws vs %d; first extra at "
                  "NOCTIS-0.CPP:%d"
                  % (ka, len(ra), len(rb),
                     (ra if len(ra) > len(rb) else rb)[min(len(ra), len(rb))][0]))
            return 1
    if verbose:
        n = sum(len(r) for _k, r in la)
        print("ledgers identical: %d systems, %d draws, site for site, "
              "argument for argument, value for value" % (len(la), n))
    return 0


# ------------------------------------------- the checks on the subjects

def check_sites(verbose=True):
    """Exactly eleven float-argument draw sites in each reference."""
    want = set(N.FLOAT_SITES)
    ok = True

    src = open(os.path.join(HERE, "ns_ref.c")).read()
    cs = set(int(m) for m in re.findall(r"\bZ?RANDF \((\d+),", src))
    nsites = len(re.findall(r"\bZ?RANDF \(", src))
    if cs != want or nsites != 11:
        ok = False
        print("FAIL SITES: ns_ref.c has %d float sites %s, want 11 %s"
              % (nsites, sorted(cs), sorted(want)))

    spec = open(os.path.join(HERE, "ns_spec.py")).read()
    body = spec.split("class System", 1)[1]
    ps = set(int(m) for m in re.findall(r"self\._[rz]f\(\s*(\d+),", body))
    npy = len(re.findall(r"self\._[rz]f\(", body))
    if ps != want or npy != 11:
        ok = False
        print("FAIL SITES: ns_spec.py has %d float sites %s, want 11 %s"
              % (npy, sorted(ps), sorted(want)))

    if ok and verbose:
        print("float-argument draw sites: 11 in ns_ref.c and 11 in "
              "ns_spec.py, the same eleven: %s" % sorted(want))
    return ok


def _build(flags, exe):
    cmd = ["gcc", "-O2"] + flags + ["-o", exe,
                                    os.path.join(HERE, "ns_ref.c"), "-lm"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError("build failed: %s\n%s" % (" ".join(cmd), r.stderr))
    return exe


def check_overflow(nsin, verbose=True):
    """The seed's 32-bit wrap is the answer, not an accident.

    NOCTIS-0.CPP:4080 runs its remainder chain through a signed long that
    overflows on most real stars.  Recon A found that gcc -O2 is entitled to
    miscompile the naive signed spelling into a plausible wrong galaxy, so
    ns_ref.c ships the u32 spelling, which the standard defines.

    This check builds BOTH and requires them to agree:
        default            u32 multiply, reinterpreted -- no UB, no flags
        -DSEED_SIGNED -fwrapv   the naive spelling with wrapping guaranteed
    Agreement is the real claim: the two defined readings of the expression
    are the same reading.

    It also builds -DSEED_SIGNED WITHOUT -fwrapv and reports whether that
    differs.  It is not required to differ -- whether it does is a property
    of today's gcc, not of Noctis -- but a silent change there is worth
    seeing, so the number is printed either way.
    """
    outs = {}
    for tag, flags in (("u32", ["-fwrapv"]),
                       ("signed_wrapv", ["-fwrapv", "-DSEED_SIGNED"]),
                       ("signed_ub", ["-DSEED_SIGNED"])):
        exe = _build(flags, os.path.join(HERE, "ns_ovf_%s.exe" % tag))
        out = os.path.join(HERE, "ns_ovf_%s.nstopo" % tag)
        subprocess.run([exe, nsin, out], check=True)
        outs[tag] = open(out, "rb").read()

    if outs["u32"] != outs["signed_wrapv"]:
        print("FAIL OVERFLOW: the u32 spelling of the seed chain and the "
              "signed spelling under -fwrapv disagree. One of them is not "
              "the expression at NOCTIS-0.CPP:4080.")
        return False
    if verbose:
        print("seed overflow: u32 spelling == signed spelling under -fwrapv, "
              "byte for byte (%d bytes)" % len(outs["u32"]))
        same = outs["signed_ub"] == outs["u32"]
        print("  informational: -DSEED_SIGNED WITHOUT -fwrapv %s on this "
              "toolchain (gcc %s). Undefined behaviour that happens to "
              "agree today is still undefined behaviour, which is why the "
              "shipped spelling is the u32 one."
              % ("AGREES" if same else "DIFFERS", _gccver()))
    return True


def _gccver():
    r = subprocess.run(["gcc", "-dumpversion"], capture_output=True, text=True)
    return r.stdout.strip()


def check_jitter(nsin, verbose=True):
    """The tree must be float-free.  Perturb nearstar_ray; the topology,
    the draw counts and the identity must all be untouched."""
    exe = _build(["-fwrapv"], os.path.join(HERE, "ns_ref.exe"))
    a = os.path.join(HERE, "ns_jit_a.nstopo")
    b = os.path.join(HERE, "ns_jit_b.nstopo")
    subprocess.run([exe, nsin, a], check=True)
    subprocess.run([exe, nsin, b, "--jitter", "1e-7"], check=True)
    fails = compare([a, b], verbose=False)
    if fails:
        print("FAIL JITTER: perturbing nearstar_ray by 1e-7 changed the "
              "topology. Either the tree is not float-free after all, or "
              "the port reads a geometry value it should not:")
        for c, m in fails[:6]:
            print("  %-11s %s" % (c, m))
        return False
    if verbose:
        _h, ra = N.read_nstopo(a)
        _h, rb = N.read_nstopo(b)
        print("float independence: nearstar_ray perturbed by 1e-7, all %d "
              "systems identical in draw counts, topology and identity"
              % len(ra))
    return True


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    if argv[0] == "--sites":
        return 0 if check_sites() else 1
    if argv[0] == "--overflow":
        return 0 if check_overflow(argv[1]) else 1
    if argv[0] == "--jitter":
        return 0 if check_jitter(argv[1]) else 1
    if argv[0] == "--ledger":
        return compare_ledgers(argv[1], argv[2])
    return 1 if compare(argv) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
