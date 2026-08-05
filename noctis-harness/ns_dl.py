"""ns_dl.py -- grade an NSTOPO against DL.EXE, the 1996 machine code.

Recon C established that `DL.EXE` can be driven headlessly under DOSBox-X and
that it prints a star's charted bodies arranged by the LIVE values of
nearstar_p_owner[] and nearstar_p_moonid[] -- exactly the two arrays whose
draw accounting is this wave's hard problem.  120 captures are on disk at
tests/gen/recon_c/dos/OUT with a manifest, they were re-captured
byte-identical in a second session, and DL.CPP's prepare_nearstar differs
from NOCTIS-0.CPP's only in ways that draw nothing from the LCG.

This file does not re-derive any of that.  It reuses the recon's parser and
its catalogue join READ-ONLY (nothing under tests/gen is written) and adds
one thing: it grades an NSTOPO FILE rather than a Python module, so the lino
side, the C side and the Python side are all graded by the same code against
the same 1996 output.

What a capture constrains, per charted body b (1-based body index):
    owner[b-1]  == -1        if b printed at the top level
    owner[b-1]  == P-1       if b printed under top-level planet P
    moonid[b-1] == NN-1      in that case
A moon's own index is not printed, but its NAME is, and STARMAP.BIN carries
the index in bytes 30..31 of the same record.  msg() truncates every line to
21 characters, so several moons of one planet can print identically; the
recon's constraints() carries the whole candidate set rather than guessing,
and this grader keeps that -- the constraint stays falsifiable, it is merely
weaker for the ambiguous ones.

Usage:
    python ns_dl.py                      build, run both references, grade
    python ns_dl.py --nstopo F.nstopo    grade an NSTOPO built from the same
                                         manifest order (this is how the lino
                                         side gets graded)
    python ns_dl.py --model spec|ref     grade only one reference
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RECON = os.path.join(os.path.dirname(HERE), "tests", "gen", "recon_c")
for p in (HERE, RECON):
    if p not in sys.path:
        sys.path.insert(0, p)

import ns_spec as N                                             # noqa: E402

MANIFESTS = [os.path.join(RECON, "batch4.manifest")]
# the ten hand-picked stars of batch 1/2 live in compare_dl.STARS/CAPTURES
# rather than in a manifest; they are folded in below.


def _recon():
    """Import the recon's parser lazily so a missing recon tree is a clear
    message rather than an import error at module load."""
    if not os.path.isdir(RECON):
        raise SystemExit("ns_dl: the recon capture tree is not at %s" % RECON)
    import compare_dl                                            # noqa: E402
    return compare_dl


def capture_rows():
    """[(capture path, name, x, y, z, class)] over every capture on disk."""
    C = _recon()
    rows = []
    seen = set()
    for m in MANIFESTS:
        if not os.path.exists(m):
            continue
        for line in open(m, encoding="utf-8"):
            fn, name, x, y, z, cls, _nb = line.rstrip("\n").split("\t")
            cap = os.path.join(C.OUT, fn)
            if os.path.exists(cap) and name not in seen:
                seen.add(name)
                rows.append((cap, name, int(x), int(y), int(z), int(cls)))
    for name, (x, y, z) in C.STARS.items():
        cap = os.path.join(C.OUT, C.CAPTURES[name])
        if os.path.exists(cap) and name not in seen:
            seen.add(name)
            rows.append((cap, name, x, y, z, -1))
    return rows


def build_nsin(rows, path):
    N.write_nsin(path, [(x, y, z, -1, -1, -1, 0, 0)
                        for (_c, _n, x, y, z, _cl) in rows])
    return path


def grade(nstopo, rows, verbose=True):
    """-> (constraints, reproduced, [failures]).

    A body word in NSTOPO is  type | (owner+1)<<8 | moonid<<16, and 0xFFFFFFFF
    for an index the model says does not exist.  A charted body that the model
    does not produce at all is a failure, not a skip.
    """
    C = _recon()
    bodies = C.catalogue_bodies()
    _hdr, recs = N.read_nstopo(nstopo)
    if len(recs) != len(rows):
        raise SystemExit("ns_dl: %s has %d records, the capture set has %d; "
                         "it was not built from this manifest order"
                         % (nstopo, len(recs), len(rows)))

    total = ok = 0
    percls = {}
    failures = []
    graded = 0
    for r, (cap, name, x, y, z, cls) in zip(recs, rows):
        if (r[0] & 0xFFFFFFFF) != (x & 0xFFFFFFFF) or \
           (r[1] & 0xFFFFFFFF) != (y & 0xFFFFFFFF):
            raise SystemExit("ns_dl: record order does not match the manifest "
                             "at %s" % name)
        nop, nob = r[5], r[6]
        # the catalogue bucket for this star, found the way the recon does:
        # nearest parent identity within 1e-4
        ident = round(_identity(x, y, z), 5)
        best, bd = None, 1e-4
        for k in bodies:
            if abs(k - ident) < bd:
                best, bd = k, abs(k - ident)
        cons, unknown = C.constraints(cap, bodies.get(best, {}))
        if not cons:
            if verbose:
                print("  no tree in %s (%s): ambiguous key or out of range"
                      % (os.path.basename(cap), name))
            continue
        graded += 1
        claimed = set()
        good = 0
        n = 0
        for cands, eo, em, bn in cons:
            cands = [b for b in cands if b - 1 < N.MAXBODIES]
            if not cands:
                continue
            total += 1
            n += 1
            hit = None
            for b in cands:
                if b in claimed:
                    continue
                w = r[20 + b - 1]
                if w == 0xFFFFFFFF:
                    continue
                got_o = ((w >> 8) & 0xFF) - 1
                got_m = (w >> 16) & 0xFF if (b - 1) >= nop else None
                if got_o == eo and (em is None or got_m == em):
                    hit = b
                    break
            if hit is not None:
                claimed.add(hit)
                good += 1
                ok += 1
            else:
                b = cands[0]
                w = r[20 + b - 1]
                failures.append((name, b, bn, eo, em,
                                 "absent" if w == 0xFFFFFFFF
                                 else "(%d,%d)" % (((w >> 8) & 0xFF) - 1,
                                                   (w >> 16) & 0xFF)))
        key = cls if cls >= 0 else r[3]
        a, bb = percls.get(key, (0, 0))
        percls[key] = (a + n, bb + good)
        if unknown and verbose and good != n:
            print("  %s: names not in the catalogue bucket: %s"
                  % (name, unknown[:3]))

    if verbose:
        print("systems graded: %d of %d captures" % (graded, len(rows)))
        print("%6s %12s %11s" % ("class", "constraints", "reproduced"))
        for c in sorted(percls):
            t, o = percls[c]
            print("%6d %12d %11d" % (c, t, o))
        print("%6s %12d %11d   (%.2f%%)"
              % ("ALL", total, ok, 100.0 * ok / max(total, 1)))
        for f in failures[:20]:
            print("  MISMATCH %s body %d %r: want owner/moonid (%s,%s), "
                  "model says %s" % (f[0], f[1], f[2][:20], f[3], f[4], f[5]))
    return total, ok, failures


def _identity(x, y, z):
    return N.to_f64(N.identity_ext(x, y, z))[0]


def main(argv):
    nstopo = None
    which = "both"
    i = 0
    while i < len(argv):
        if argv[i] == "--nstopo":
            nstopo = argv[i + 1]; i += 1
        elif argv[i] == "--model":
            which = argv[i + 1]; i += 1
        i += 1

    rows = capture_rows()
    if not rows:
        raise SystemExit("ns_dl: no captures found under %s" % RECON)
    print("DL captures on disk: %d" % len(rows))

    if nstopo:
        total, ok, fails = grade(nstopo, rows)
        return 0 if (total and ok == total) else 1

    nsin = build_nsin(rows, os.path.join(HERE, "ns_dl.nsin"))
    rc = 0
    todo = ("ref", "spec") if which == "both" else (which,)
    for m in todo:
        out = os.path.join(HERE, "ns_dl.%s.nstopo" % m)
        if m == "ref":
            exe = os.path.join(HERE, "ns_ref.exe")
            if not os.path.exists(exe):
                subprocess.run(["gcc", "-O2", "-fwrapv", "-o", exe,
                                os.path.join(HERE, "ns_ref.c"), "-lm"],
                               check=True)
            subprocess.run([exe, nsin, out], check=True)
        else:
            subprocess.run([sys.executable, os.path.join(HERE, "ns_spec.py"),
                            nsin, out], check=True)
        print("\n--- %s ---" % {"ref": "ns_ref.c (C)",
                                "spec": "ns_spec.py (Python)"}[m])
        total, ok, _f = grade(out, rows)
        if not total or ok != total:
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
