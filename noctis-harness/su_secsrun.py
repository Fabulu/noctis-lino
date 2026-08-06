r"""su_secsrun.py - drive su_secs.search over the four secs-dependent captures
and write the result to su_secs.json.  Reported as a FIT, with the width of
the invariance interval so the reader can see how much of the candidate set
the answer actually excludes.
"""

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import su_seed
import su_secs
import su_spec

OUT = r"C:\programmieren\linoleum\tests\gen\recon_w7a\out"
TAGS = [("lane_b00_t2", True), ("lane_b03_t3", True),
        ("jrot_b00_t6", True), ("lane_b02_t5", False)]


def main():
    man = json.load(open(os.path.join(OUT, "manifest.json")))
    res = {}
    for tag, overlay_only in TAGS:
        e = [m for m in man if m["tag"] == tag][0]
        inp = su_seed.body_inputs(*e["star"], e["body"])
        ref_map = open(os.path.join(OUT, tag + ".p_background"), "rb").read()[:64800]
        ref_ovl = open(os.path.join(OUT, tag + ".objectschart"), "rb").read()[:32400]
        plwp = e["terminator"]["plwp"]
        plwp = 0 if plwp is None else plwp
        t0 = time.time()

        def prog(i, n, S, nd):
            sys.stderr.write("\r%s %d/%d S=%d nd=%d   " % (tag, i, n, S, nd))
            sys.stderr.flush()

        sites, cands, hits = su_secs.search(
            e, inp, ref_map, ref_ovl, plwp,
            overlay_only=overlay_only, progress=prog)
        sys.stderr.write("\n")
        res[tag] = dict(
            planet_type=e["planet_type"], k=sites[0][0] if sites else None,
            n_sites=len(sites), n_candidates=len(cands),
            graded_on="objectschart" if overlay_only else "p_background",
            hits=[dict(S=h[0], width=h[1]) for h in hits],
            seconds=round(time.time() - t0, 1))
        print(tag, res[tag]["hits"], "%.0fs" % res[tag]["seconds"], flush=True)
    json.dump(res, open(os.path.join(HERE, "su_secs.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
