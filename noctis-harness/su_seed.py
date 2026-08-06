r"""su_seed.py - the seedval that surface() is called with, built on the x87
stack the way NOCTIS-0.CPP:5376-5418 builds it.

    surface (n, nearstar_p_type[n],
             1000000 * nearstar_p_type[n]
                     * nearstar_p_orb_seed[n]
                     * nearstar_p_orb_tilt[n]
                     * nearstar_p_orb_ecc[n]
                     * nearstar_p_orb_orient[n],
             192);

`1000000 * nearstar_p_type[n]` is long * int -> long (16-bit int promoted).
Everything after that is a chain of double multiplies which Borland keeps on
the x87 stack with NO intermediate store, so each product is rounded to the
64-bit extended significand and the ONE rounding to binary64 is the parameter
push (surface's parameter is `double`).  Wave 3 measured what a single spill
costs: 1050 of 4113 catalogue records.

The four orbital doubles and nearstar_ray come from Wave 4's ns_spec.System,
which was graded 4365/4365 against DL.EXE.  Nothing is regenerated here.
"""

import os
import sys
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from su_fp import ext, f64, fr

CLASS_RGB = [
    (63, 58, 40), (30, 50, 63), (63, 63, 63), (63, 30, 20),
    (63, 55, 32), (32, 16, 10), (32, 28, 24), (10, 20, 63),
    (63, 32, 16), (48, 32, 63), (40, 10, 10), (0, 63, 63),
]


def chain(*terms):
    """Left-associative product evaluated in x87 extended, rounded to
    binary64 exactly once, at the end."""
    acc = ext(fr(terms[0]))
    for t in terms[1:]:
        acc = ext(acc * fr(t))
    return f64(acc)


def system(x, y, z):
    import ns_spec
    return ns_spec.System(x, y, z)


def body_inputs(x, y, z, n):
    """Everything surface() needs for body n of the star at (x, y, z)."""
    sysm = system(x, y, z)
    ptype = sysm.p_type[n]
    owner = sysm.p_owner[n]
    is_moon = owner > -1
    colorbase = 128 if is_moon else 192
    ray = sysm.ray                      # nearstar_ray, a float32
    if is_moon:
        if ptype:
            seedval = chain(1000000 * ptype, ray, sysm.p_orb_orient[n])
        else:
            seedval = chain(2000000 * n, ray, sysm.p_orb_orient[n])
    else:
        if ptype:
            seedval = chain(1000000 * ptype,
                            sysm.p_orb_seed[n], sysm.p_orb_tilt[n],
                            sysm.p_orb_ecc[n], sysm.p_orb_orient[n])
        else:
            seedval = chain(2000000 * n,
                            sysm.p_orb_seed[n], sysm.p_orb_tilt[n],
                            sysm.p_orb_ecc[n], sysm.p_orb_orient[n])
    rgb = CLASS_RGB[sysm.cls]
    return dict(ptype=ptype, owner=owner, colorbase=colorbase,
                seedval=seedval, ray=ray, rgb=rgb, cls=sysm.cls,
                nob=sysm.nob, nop=sysm.nop, is_moon=is_moon,
                orb=(sysm.p_orb_seed[n], sysm.p_orb_tilt[n],
                     sysm.p_orb_ecc[n], sysm.p_orb_orient[n]))


if __name__ == "__main__":
    x, y, z, n = (float(sys.argv[1]), float(sys.argv[2]),
                  float(sys.argv[3]), int(sys.argv[4]))
    d = body_inputs(x, y, z, n)
    for k in sorted(d):
        print("%-10s %r" % (k, d[k]))
