r"""su_ledger.py - draw accounting for surface(), and the closed-form predictor.

surface() runs BOTH generators interleaved.  ranged_fast_random owns the type
switch (105 sites) and Borland's random() owns the modular painters (20 sites),
and the two are coupled in four shapes:

  V3/V5/V8   a FAST draw sets a BRTL COUNT
             case 0:  r = 100+rfr(100) fractures, each doing 1+2*(gr+1) brtl
                      draws where gr = rfr(100)
             case 1/4: r sets crater_juice()'s loop trip count
             case 3:  g = rfr(5)+7 and cr = rfr(10)+10 set atm_cyclon()'s
                      step count g*cr, hence 3*g*cr brtl draws
  V6         a BRTL draw selects which FAST draws happen
             case 2:  switch(random(2)) picks storm (3 fast draws) or band
                      (3 fast draws, different ranges) - the branch is chosen
                      by the OTHER generator

Totals cannot localise a fault in any of those, so the ledger is per phase and
the predictor below is derived from the loop structure rather than from either
implementation's execution.

PREDICT() never calls a painter.  It takes the observed GATE values - the
draws that decide loop trip counts and branches - and computes what the counts
must be.  A painter that draws once too often or too seldom therefore shows up
as predictor-vs-observed, not as spec-vs-ref.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# --------------------------------------------------------------------------
# Per-painter draw arithmetic, restated from NOCTIS-0.CPP and from nothing
# else.  fast = ranged_fast_random calls, brtl = random() calls.
# --------------------------------------------------------------------------

ALOOP_N = 90          # for (a=0; a<2*M_PI; a+=4*deg) with `a` a float32
                      # global round-tripped through memory.  Keeping `a` in a
                      # double or a register gives 91 - the LOOP91 hazard.


def n_spot(): return (0, 0)
def n_cirrus(): return (0, 0)


def n_permanent_storm(cr):
    """cr-1 rings x ALOOP_N spots, no draws."""
    return (0, 0)


def n_storm(cr):
    return (0, 0)


def n_volcano(cr):
    return (0, 0)


def n_band():
    return (0, 0)


def n_wave():
    return (0, 0)


def n_negate():
    return (0, 0)


def n_fracture(gr):
    """1 draw for the initial bearing plus 2 per step, gr+1 steps."""
    return (0, 1 + 2 * (gr + 1))


def n_crater(crays, ray_hits):
    """crays==0 -> no draw at all (the && short-circuits BEFORE the draw).
    Otherwise one random(crays) per angle, plus one random(2) for each angle
    whose draw came back zero.  ray_hits is that observed count."""
    if not crays:
        return (0, 0)
    return (0, ALOOP_N + ray_hits)


def n_crater_juice(r, per_crater):
    """2 + 3 per crater, plus whatever each crater() itself drew."""
    return (0, 2 + 3 * r + sum(per_crater))


def n_atm_cyclon(g, cr):
    """the while(cr>0) loop runs g*cr times; 3 draws each."""
    return (0, 3 * g * cr)


def n_randoface(hits):
    """two draws per pixel that passes the gate; `hits` is observed."""
    return (0, 2 * hits)


def n_contrast():
    return (0, 0)


# --------------------------------------------------------------------------
# The switch.  `gates` is a dict of the observed gate values; everything else
# is arithmetic.
# --------------------------------------------------------------------------

def predict_switch(ptype, gates):
    """(fast, brtl) consumed inside the switch, from the gate values alone."""
    G = gates
    if ptype == 0:
        fast = 1 + 1 + 1 + 4 * G["r_volc"] + 1 + 1 + 3 * G["r_frac"]
        brtl = sum(1 + 2 * (gr + 1) for gr in G["frac_gr"])
    elif ptype == 1:
        fast = 1 + 1 + 1
        brtl = G["cj_brtl"]
    elif ptype == 2:
        # per iteration: cr, cy, then either (cx-divisor, gr) for the storm
        # branch or (gr, g) for the band branch - four FAST draws either way,
        # which is exactly why a totals-only check cannot see V6.
        fast = 1 + 4 * len(G["t2_branch"]) + 1
        brtl = len(G["t2_branch"])
    elif ptype == 3:
        # per cyclone: gr, cr, gate, cy (1 if the gate fired, else 2),
        # cx-divisor, g, a-start  ->  7 or 8
        fast = 1 + 2 + 1 + sum(7 if gate else 8 for gate in G["t3_cygate"])
        brtl = sum(3 * g * cr for g, cr in G["t3_gcr"])
    elif ptype == 4:
        fast = 1 + 1 + 1 + 1 + 3 * G["r_frac"] + 1 + 1
        brtl = sum(1 + 2 * (gr + 1) for gr in G["frac_gr"]) + G["cj_brtl"]
    elif ptype == 5:
        # the 10000-iteration spot loop draws FIVE times per iteration:
        # gr, px, py, px, py  (:4983-4987)
        fast = (1 + 3 + 2 + 1 + 4 * G["r_volc"] + 1 + 4 * G["r_pstorm"]
                + 5 * 10000 + 1)
        brtl = 2 * G["rf_hits"]
    elif ptype == 6:
        # band branch: cr, cy, gate, gr, g = 5.  wave branch: cr, cy, gate,
        # a = 4.  Here the branch DOES change the FAST count.
        fast = (1 + 1 + sum(4 if w else 5 for w in G["t6_wave"])
                + 1 + 5 * G["r_storm"] + 1)
        brtl = 0
    elif ptype == 7:
        fast = 1 + 3 + 3 * G["r_frac"] + 1 + 1 + 1
        brtl = sum(1 + 2 * (gr + 1) for gr in G["frac_gr"]) + 2 * G["rf_hits"]
    elif ptype == 8:
        fast = 1 + 1 + 4 * G["r_pstorm"] + 1
        brtl = 0
    elif ptype == 9:
        fast = 0
        brtl = 0
    else:
        return None
    return fast, brtl


# The parts outside the switch are fixed and tiny, so they are stated whole.
PROLOGUE_FAST = 3          # rtperiod's three ranged_fast_random draws
BRIDGE_FAST = 1            # seed = fast_random(0xFFFF)
PALETTE_BRTL = 18          # nine `x + random(c) - random(c)` lines


def predict_outside(ptype, gates, colorbase):
    fast = PROLOGUE_FAST + BRIDGE_FAST
    brtl = 0
    if ptype == 3:
        fast += 1                              # :5079  lssmooth or ssmooth
    if ptype == 2:
        brtl += 1                              # :5098  if (!random(3))
        if not gates.get("knot1"):
            fast += 1                          # :5134  r = 3 + rfr(5)
    if ptype == 6:
        fast += 3                              # :5141  three rfr(2)
    if colorbase != 255 and ptype != 10:
        brtl += PALETTE_BRTL
    return fast, brtl


def predict(ptype, colorbase, gates):
    if ptype == 10:
        return 0, 0
    f1, b1 = predict_outside(ptype, gates, colorbase)
    sw = predict_switch(ptype, gates)
    if sw is None:
        return None
    return f1 + sw[0], b1 + sw[1]
