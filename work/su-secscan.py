r"""su-secscan.py -- recover the guest clock for the four secs-dependent types.

READ THIS BEFORE READING THE NUMBERS IT PRINTS.

surface() reads the global "secs" at four sites, and only for planet types
2, 3, 5 and 6 (NOCTIS-0.CPP:4890, :4933, :5000, :5047).  secs is the number of
seconds since 1984-01-01 at the instant the frame ran.  recon C pins the guest
clock to 2000-01-01 12:00:00 and turns host synchronisation off, so the
INTEGER BASE is known exactly - 504,964,800 - but the seconds the run had been
executing when surface() fired are not recorded by any artefact.

So this script SOLVES FOR ONE SCALAR PER CAPTURE.  That is recon C's option
(c), the weakest of the three it offered, and it is used here loudly rather
than quietly.  What makes it worth doing anyway, and what it is and is not
evidence for:

  * The search space is one integer over a bracket of a few hundred, and the
    acceptance test is that all 64,800 map bytes AND all 32,400 overlay bytes
    match.  A wrong implementation does not acquire a 64,800-byte match by
    being handed a few hundred tries at one parameter: the probability of a
    spurious hit is not small, it is nil.  What the search cannot do is
    distinguish "the port is right and the clock was T" from "the port is
    right and the clock was T" - which is to say, it tells you nothing about
    the clock that you could check independently.

  * Therefore a hit here is reported as CONSISTENT, never as EXACT, and the
    six secs-free types remain the wave's only unconditional map evidence.
    A capture that produces exactly one hit and captures that produce none
    are both reported as measurements.

  * The honest alternative is recon extension CAP-2: poll the mmap'd guest
    RAM while the capture runs and bracket secs from the outside.  That
    converts every hit below into a prediction with no free parameter.  It is
    Implementer 2's, and until it exists these four are UNGRADED.

HOW THE CANDIDATES ARE BUILT.  secs is a double: an integer second plus the
sub-second fraction fps/gl_fps.  The four sites do not read secs, they read
(long)(k*secs) for k in {1, 10, 60}, so the only thing that matters is that
integer.  Candidates are therefore chosen to make k*secs land on a half
integer, one candidate per reachable value of the truncated product:

    type 3   k = 1    secs = N + 0.5                     N over the bracket
    type 2   k = 10   secs = N + (m + 0.5)/10            m = 0..9
    types 5,6 k = 60  secs = N + (m + 0.5)/60            m = 0..59

Usage:
    python su-secscan.py <tag> [--lo 0] [--hi 200] [--chunk 2200]
"""

import json
import os
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RECON = os.path.join(ROOT, "tests", "gen", "recon_w7a", "out")
CORPUS = os.path.join(HERE, "su-corpus.txt")
# the scan OVERWRITES su-corpus.txt, so the base line is read from the stable
# copy su-mkcorpus.py leaves behind rather than from the file being rewritten
CORPMAIN = os.path.join(HERE, "su-corpus-main.txt")
OUTBIN = os.path.join(HERE, "su-out.bin")
RUNPS1 = os.path.join(HERE, "su-run.ps1")

sys.path.insert(0, HERE)
import importlib.util
_spec = importlib.util.spec_from_file_location("su_mk",
                                               os.path.join(HERE, "su-mkcorpus.py"))
mk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mk)
_spec2 = importlib.util.spec_from_file_location("su_ck",
                                                os.path.join(HERE, "su-check.py"))
ck = importlib.util.module_from_spec(_spec2)
_spec2.loader.exec_module(ck)

FNVOFF, FNVPR, M32 = 2166136261, 16777619, 0xFFFFFFFF


def fnv(data):
    h = FNVOFF
    for b in data:
        h = ((h ^ b) * FNVPR) & M32
    return h


def base_line(tag):
    """The corpus line su-mkcorpus.py produced for this tag, minus secs."""
    for ln in open(CORPMAIN):
        if ln.strip().startswith("#"):
            continue
        if ln.rstrip().endswith("# " + tag):
            return ln.split("#")[0].split()
    raise SystemExit("no corpus line for %s; run su-mkcorpus.py first" % tag)


def main():
    tag = sys.argv[1]
    lo = int(sys.argv[sys.argv.index("--lo") + 1]) if "--lo" in sys.argv else 0
    hi = int(sys.argv[sys.argv.index("--hi") + 1]) if "--hi" in sys.argv else 200
    chunk = int(sys.argv[sys.argv.index("--chunk") + 1]) if "--chunk" in sys.argv else 2200

    fields = base_line(tag)
    ptype = int(fields[2])
    k = {2: 10, 3: 1, 5: 60, 6: 60}.get(ptype)
    if k is None:
        raise SystemExit("type %d does not read secs" % ptype)

    cap = open(os.path.join(RECON, tag + ".p_background"), "rb").read()[:64800]
    ovl = open(os.path.join(RECON, tag + ".objectschart"), "rb").read()[:32400]
    want_map, want_ovl = fnv(cap), fnv(ovl)

    cands = []
    for n in range(lo, hi + 1):
        for m in range(k):
            cands.append(mk.SECS_BASE + n + (m + 0.5) / k)

    print("%s type %d: %d candidates, want map_fnv=%08X ovl_fnv=%08X"
          % (tag, ptype, len(cands), want_map, want_ovl))

    hits = []
    for start in range(0, len(cands), chunk):
        part = cands[start:start + chunk]
        lines = ["# su-secscan %s" % tag]
        for sv in part:
            clo, chi = mk.halves(sv)
            f = list(fields)
            f[12], f[13], f[14] = str(clo), str(chi), "0"
            lines.append(" ".join(f))
        lines.append("0")
        open(CORPUS, "w").write("\n".join(lines) + "\n")
        subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File",
                        RUNPS1, "-TimeoutSec", "1800"],
                       check=True, capture_output=True)
        recs = ck.read_records(OUTBIN)
        scal = [r for r in recs if r["kind"] == ck.KSCAL]
        for i, r in enumerate(scal):
            if r["body"][13] == want_map:
                hits.append((part[i], r["body"][14] == want_ovl))
        print("  %d..%d done, %d hits so far"
              % (start, start + len(part) - 1, len(hits)))

    print()
    if not hits:
        print("NO HIT for %s over secs in [%d, %d] -- reported as UNGRADED"
              % (tag, mk.SECS_BASE + lo, mk.SECS_BASE + hi))
    for sv, ovlok in hits:
        print("HIT %s  secs = %.6f  (base + %.6f s)  overlay %s"
              % (tag, sv, sv - mk.SECS_BASE, "MATCHES" if ovlok else "DIFFERS"))
    print("(%d hit%s; a hit is CONSISTENT, not EXACT -- one scalar was solved"
          " for)" % (len(hits), "" if len(hits) == 1 else "s"))


if __name__ == "__main__":
    main()
