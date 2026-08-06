r"""su_secs.py - resolving the one runtime input the capture cannot show.

Recon C's honest limit: `secs`, the double the game holds when surface() runs,
is not in the artefact.  It reaches the map through exactly four expressions,
all of the same shape (NOCTIS-0.CPP:4890, 4929, 4978, 5018):

        cx = ((long)(k * secs) / (ranged_fast_random(R) + c)) % 360

so the ONLY thing the 64,800 bytes can see is the single integer

        S = (long)(k * secs)          k in {1, 10, 60}

and the divisors D_i are drawn from the FAST stream, which is already pinned
by the six secs-free captures.  Therefore:

  * the search space is the INTEGERS, not the reals;
  * S -> (cx_1 .. cx_m) is a step function.  Two values of S that give the
    same cx vector give the same map, byte for byte.  So the real candidate
    set is the set of DISTINCT cx VECTORS over the plausible interval, which
    is a few hundred, not tens of thousands.

This is a search, and a search that succeeds is a FIT.  It is reported as
one.  What makes the fit worth anything is the ratio: ONE integer chosen out
of an enumerated candidate set, against 64,800 (or 32,400) bytes of residual
constraint that were in no way used to choose it, plus the requirement that a
single S satisfy 5..60 independent storm/cyclone placements simultaneously.
If more than one candidate matches, that is reported too - the interval over
which the output is invariant is exactly recon C's CAP-2 acceptance rule
without needing a second RAM snapshot.

FINDING - THE GUEST CLOCK IS ONLY HALF PINNED
--------------------------------------------
recon C states that `[dosbox] synchronize time=false` plus `date 01-01-2000` /
`time 12:00:00.00` in [autoexec] pins the guest clock, and offers the byte
identity of repeat runs as evidence.  That evidence is consistent with a
weaker fact, and the weaker fact is the true one.

su_solve.py recovered (long)secs = 1,344,168,009 for lane_b03_t3 ALGEBRAICALLY,
from the cloud geometry alone, with no window assumed.  Running that back
through getsecs() (NOCTIS-0.CPP:3931-3950):

    2000-01-01 12:00:00  ->    504,964,800     (off by 839,203,209)
    2026-08-06 12:00:00  ->  1,344,168,000     (off by 9)

2026-08-06 is the HOST date on which out/ was captured (every artefact's mtime
is 2026-08-06 16:11-16:21 local).  So the `time` line took effect and the
`date` line did NOT: the guest runs on the host's DATE at 12:00:00 + about
nine seconds of boot.  Repeat runs on the same day agree, which is why the
determinism check passed; a capture taken on a different day will NOT
reproduce these ten artefacts, and any future capture batch has to record the
host date or it cannot be graded at all.

BASE below is therefore derived from the artefacts' own capture date, and it
is a MEASURED input to the search, not an assumption.  The window is 90 guest
seconds against a capture budget of 20 s settle + 20 s tail.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import numpy as np

import su_seed
import su_spec

BASE = 1344168000           # getsecs() at 2026-08-06 12:00:00 - the capture day
WINDOW = 90                 # guest seconds allowed to elapse before surface()


def divisors(entry, inputs, plwp=0):
    """One cheap run whose only purpose is to harvest the D_i.  The divisors
    come from the FAST stream and do not depend on secs at all, so any S
    works here."""
    S = su_spec.Surface(ledger=False)
    S.stop_after_switch = True
    S._secs_scaled = 0
    S.run(entry["body"], entry["planet_type"], inputs["seedval"],
          inputs["colorbase"], secs=0.0, plwp=plwp, owner=inputs["owner"],
          nearstar_rgb=inputs["rgb"])
    return S.secs_sites


def candidates(sites):
    """Distinct (cx_1..cx_m) vectors over the plausible interval, each with the
    lowest S that produces it and the count of S values that share it."""
    if not sites:
        return []
    k = sites[0][0]
    ds = [d for _, d in sites]
    lo = k * BASE
    hi = k * (BASE + WINDOW)
    seen = {}
    order = []
    for Sraw in range(lo, hi + 1):
        # (long) is 32 bits.  k*secs for k = 10 and k = 60 overflows it, and
        # __ftol does not saturate: it keeps the low 32 bits, sign-interpreted.
        # 60*504964800 = 30297888000 -> 233116928 after the wrap, so a search
        # that forgets this divides by the wrong dividend entirely.
        S = Sraw & 0xFFFFFFFF
        if S & 0x80000000:
            S -= 0x100000000
        vec = tuple(su_spec.crem(su_spec.cdiv(S, d), 360) for d in ds)
        if vec not in seen:
            seen[vec] = [S, 0]
            order.append(vec)
        seen[vec][1] += 1
    return [(seen[v][0], seen[v][1], v) for v in order]


def search(entry, inputs, ref_map, ref_ovl, plwp, overlay_only=False,
           progress=None):
    sites = divisors(entry, inputs, plwp)
    cands = candidates(sites)
    hits = []
    for i, (S, width, vec) in enumerate(cands):
        M = su_spec.Surface(ledger=False)
        M._secs_scaled = S
        M.stop_after_switch = overlay_only
        M.run(entry["body"], entry["planet_type"], inputs["seedval"],
              inputs["colorbase"], secs=0.0, plwp=plwp,
              owner=inputs["owner"], nearstar_rgb=inputs["rgb"])
        if overlay_only:
            ok = M.ovl_bytes() == ref_ovl
            nd = 0 if ok else _nd(M.ovl_bytes(), ref_ovl)
        else:
            ok = M.map_bytes() == ref_map
            nd = 0 if ok else _nd(M.map_bytes(), ref_map)
        if progress and i % 25 == 0:
            progress(i, len(cands), S, nd)
        if ok:
            hits.append((S, width, vec))
    return sites, cands, hits


def _nd(a, b):
    return int((np.frombuffer(a, dtype=np.uint8)
                != np.frombuffer(b, dtype=np.uint8)).sum())
