#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
sp_mkcorpus.py -- Wave 6b: the pinned corpus, written in BOTH grammars.

The two sides cannot read one file.  sp_ref.c and sp_spec.py parse
`CASE <id> <KIND> k=v ...`; the lino tokeniser understands exactly one lexeme,
a signed decimal integer.  So the corpus is necessarily a transliteration and
can never have one sha256.  Wave 6a settled what to do about that: do NOT
compare hashes (`pg_grade.py`'s FIXTURE.shared_corpus reports FAIL in the
shipped configuration and, worse, DISAPPEARS -- taking the whole grader's
exit code with it -- when its input is deleted).  Compare the pinned NUMBERS,
case by case and field by field.  That is F1, and it lives in
tests/test_sphere.py.  An absent file fails F1 instead of skipping it.

THE CORPUS IS CHOSEN, NOT SAMPLED, and its coverage is itself checked --
Wave 6a's R1e pattern.  A corpus that quietly loses a class must FAIL, not
read green.  Every parameter below was searched for once, off-line, against
the shipped GLOBES.MAP and is now a FROZEN LITERAL; nothing here is searched
at test time.

What the corpus is built to reach, and why each one is here:

  * all four gman bands, non-empty          (mag <=0.33, >0.33, >0.66, >0.99)
  * both of globe's clamps                  (<0.01 -> 0.001 ; >1.32 -> 1.32)
  * glowinglobe's clamp ORDER               (0.66 first, THEN 0.001)
  * ALL FOUR of globe's clip arms rejecting  -- otherwise "0 rejections, 0
    differences" reads as a pass exactly the way T2.LINO.MATRIX.NULL does
  * globe_saturation above AND below the tapestry's range
  * colormask in {0,64,128,192}              (`or dl,colormask` runs AFTER the
    clamp, so the order is observable only if the mask has bits)
  * start = 0 and start = 718, the unreduced maximum from NOCTIS-0.CPP:5564,
    with a marker byte in the tapestry so the far end of the cursor walk is
    observable
  * background at screenshift 0, at the nominal -643, and at the FOUR values
    that straddle the u16 boundary -- the only place where masking at the
    segment origin and masking at the buffer base differ
  * whiteglobe with a NEGATIVE fgm_factor (NOCTIS.CPP:2557 reaches -0.15) and
    a destination page pre-filled to 200, so the signed-char overflow fires
  * .NCC: VEHICLE is MANDATORY -- BIRDY's slot-3 garbage maxes at 20, so a
    BIRDY-only corpus grades the zeroing pass vacuously -- plus the synthetic
    mixed-nv model, plus a tie-rich distance set for QuickSort's instability

Usage: python sp_mkcorpus.py [--out-dir DIR]
"""

import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sp_spec as S


def f32b(x):
    return struct.unpack("<I", struct.pack("<f", x))[0]


def f64b(x):
    return struct.unpack("<Q", struct.pack("<d", x))[0]


# --------------------------------------------------------------------------
# The frozen parameters.  Each comment says what it reaches.
# --------------------------------------------------------------------------

MAG_1X1 = f32b(0.20)      # <= 0.33  -> gman1x1
MAG_2X2 = f32b(0.50)      # > 0.33   -> gman2x2
MAG_3X3 = f32b(0.80)      # > 0.66   -> gman3x3
MAG_4X4 = f32b(1.20)      # > 0.99   -> gman4x4
MAG_LOCLAMP = f32b(0.001)  # the value the < 0.01 clamp produces
MAG_HICLAMP = f32b(1.32)   # the value the > 1.32 clamp produces
MAG_GLOWCLAMP = f32b(0.66)  # glowinglobe's high clamp, applied FIRST

# mag 1.32 with centre (100,100) is the case that rejects on ALL FOUR arms:
# measured 407 / 2418 / 244 / 1206 over the shipped 10,780 draws.  Without a
# case like this, S2's four counts are all zero and the check is void.
ALLARM = dict(mag=MAG_HICLAMP, cx=100, cy=100)

TAPFILL_RAMP = 1          # buf[i] = i & 0x3F   -- spans the saturation range
TAPFILL_ZERO = 0
TAPFILL_3F = 2            # all 0x3F: every texel is ABOVE any saturation
TAPFILL_C8 = 3            # all 200: the signed-char trap for whiteglobe
TAPFILL_PRNG = 4

BG_SHIFT_NOMINAL = 64893  # (u16)(-643), NOCTIS-1.CPP:3941 at alfa=beta=0
BG_START_NOMINAL = 18360  # 360*(int)(0+51), NOCTIS-1.CPP:3942
# The four shifts where the segment-origin mask and the buffer-base mask
# disagree: they put (w + shift) mod 65536 into {65532..65535} for the
# smallest paint word, 2258.
BG_BOUNDARY = [(65532 - 2258) & 0xFFFF, (65533 - 2258) & 0xFFFF,
               (65534 - 2258) & 0xFFFF, (65535 - 2258) & 0xFFFF]

KIND_CODE = dict(GLOBE=1, GLOW=2, BG=3, DARK=4, WHITE=5, PRE=6,
                 NCC=7, SORT=8, PVL=9)


def build():
    """Returns [(id, KIND, ordered [(key, value)])] in RUN ORDER.

    Order is part of the fixture: pages are per-case here, but the arena
    cases are stateful (loadpv appends) and SORT is stateful by design --
    pv_dep_i is persistent and every frame permutes the previous frame's
    array, so replaying them out of order is a different program.
    """
    C = []

    def add(cid, kind, **kw):
        C.append((cid, kind, sorted(kw.items())))

    # ---- globe: the four fill managers, each non-empty ------------------
    for nm, mag, gm in (("G1X1", MAG_1X1, 1), ("G2X2", MAG_2X2, 2),
                        ("G3X3", MAG_3X3, 3), ("G4X4", MAG_4X4, 4)):
        add(nm, "GLOBE", mag=mag, cx=158, cy=100, gman=gm, start=0,
            colormask=0, sat=0, tapfill=TAPFILL_RAMP, tapseed=7,
            tapmark=-1, pre=0)
    # ---- globe: both clamps ---------------------------------------------
    add("GLOCLAMP", "GLOBE", mag=MAG_LOCLAMP, cx=158, cy=100, gman=1, start=0,
        colormask=0, sat=0, tapfill=TAPFILL_RAMP, tapseed=7, tapmark=-1, pre=0)
    add("GHICLAMP", "GLOBE", mag=MAG_HICLAMP, cx=158, cy=100, gman=4, start=0,
        colormask=0, sat=0, tapfill=TAPFILL_RAMP, tapseed=7, tapmark=-1, pre=0)
    # ---- globe: all four clip arms reject -------------------------------
    add("GARMS", "GLOBE", mag=ALLARM["mag"], cx=ALLARM["cx"], cy=ALLARM["cy"],
        gman=4, start=0, colormask=0, sat=0, tapfill=TAPFILL_RAMP,
        tapseed=7, tapmark=-1, pre=0)
    # ---- globe: saturation above and below the tapestry's range ---------
    add("GSATLO", "GLOBE", mag=MAG_2X2, cx=158, cy=100, gman=2, start=0,
        colormask=0, sat=0, tapfill=TAPFILL_RAMP, tapseed=7, tapmark=-1, pre=0)
    add("GSATHI", "GLOBE", mag=MAG_2X2, cx=158, cy=100, gman=2, start=0,
        colormask=0, sat=63, tapfill=TAPFILL_RAMP, tapseed=7, tapmark=-1, pre=0)
    add("GSATMID", "GLOBE", mag=MAG_2X2, cx=158, cy=100, gman=2, start=0,
        colormask=0, sat=32, tapfill=TAPFILL_RAMP, tapseed=7, tapmark=-1, pre=0)
    # ---- globe: the colour mask, all four values ------------------------
    for cm in (0, 64, 128, 192):
        add("GCM%d" % cm, "GLOBE", mag=MAG_2X2, cx=158, cy=100, gman=2,
            start=0, colormask=cm, sat=17, tapfill=TAPFILL_RAMP, tapseed=7,
            tapmark=-1, pre=0)
    # ---- globe: start 0 and the unreduced maximum 718 -------------------
    #   NOCTIS-0.CPP:5564 passes `plwp + nearstar_p_rotation[n]`, both in
    #   [0,359], so start reaches 718 with NO reduction.  A decoder that
    #   reduces start mod 360 reads a different tapestry row; the marker byte
    #   at the far end of the walk makes that observable.
    add("GSTART0", "GLOBE", mag=MAG_2X2, cx=158, cy=100, gman=2, start=0,
        colormask=0, sat=0, tapfill=TAPFILL_PRNG, tapseed=101,
        tapmark=4, pre=0)
    add("GSTART718", "GLOBE", mag=MAG_2X2, cx=158, cy=100, gman=2, start=718,
        colormask=0, sat=0, tapfill=TAPFILL_PRNG, tapseed=101,
        tapmark=718 + 4 + 42844, pre=0)
    # ---- globe: a non-zero pre-state, so the page is not "everything the
    #      rasteriser wrote" but "the rasteriser over what was there" ------
    add("GPRE", "GLOBE", mag=MAG_2X2, cx=158, cy=100, gman=3, start=13,
        colormask=64, sat=5, tapfill=TAPFILL_RAMP, tapseed=7, tapmark=-1,
        pre=0x2B)

    # ---- globe: ADVERSARIAL mag_factor values ---------------------------
    #   The pixel loop is `fild / fmul dword / fistp`, and the product needs
    #   at most 33 significand bits, so at PC=64 the FMUL rounds NOTHING and
    #   the only rounding is the FISTP.  An implementation that does a
    #   FLOAT32 multiply instead rounds twice and is wrong -- but it passes
    #   on ordinary magnifications.  These three were searched for once:
    #   each is the first pattern above the middle of its gman band at which
    #   a float32 multiply moves at least one of the 212 live map values.
    #   Without them S1 is insensitive to the SCALEF32 defect and only the
    #   glowinglobe pages catch it.
    for nm, mag, gm in (("GADV2", 0x3F013B14, 2),     # 0.504807711
                        ("GADV3", 0x3F547AE1, 3),     # 0.829999983
                        ("GADV4", 0x3F94813E, 4)):    # 1.160194159
        add(nm, "GLOBE", mag=mag, cx=158, cy=100, gman=gm, start=0,
            colormask=0, sat=0, tapfill=TAPFILL_RAMP, tapseed=7,
            tapmark=-1, pre=0)

    # ---- glowinglobe -----------------------------------------------------
    #   colour 127 is what NOCTIS-0.CPP:5593 passes; the derived pair is
    #   light 127 and dark ((127&0x3F)>>2)|(127&0xC0) = 79.
    for nm, st, ts, arc in (("LW0", 0, 0, 130), ("LWTS", 89, 124, 130),
                            ("LWWRAP", 350, 5, 130), ("LWARC0", 0, 0, 0),
                            ("LWARC359", 0, 0, 359)):
        add(nm, "GLOW", mag=MAG_GLOWCLAMP, cx=158, cy=100, start=st,
            tstart=ts, arc=arc, color=127, pre=0)
    add("LWLOCLAMP", "GLOW", mag=MAG_LOCLAMP, cx=158, cy=100, start=0,
        tstart=0, arc=130, color=127, pre=0)
    add("LWCOL", "GLOW", mag=f32b(0.30), cx=158, cy=100, start=17,
        tstart=3, arc=200, color=0xAB, pre=0)
    #   The centre that drives the vertical counter out of riga[]: the Y test
    #   is a disjunction that never rejects, so a centre near the top of the
    #   page sends (temp+center_y) negative, DI wraps, and the read lands in
    #   DGROUP.  The index sequence is graded exactly; the VALUE is NOT
    #   GRADED (see the NOT-GRADED list) and the declared filler is what
    #   makes the page comparable at all.
    add("LWOOB", "GLOW", mag=MAG_GLOWCLAMP, cx=158, cy=8, start=0,
        tstart=0, arc=130, color=127, pre=0)
    add("LWOOBHI", "GLOW", mag=MAG_GLOWCLAMP, cx=158, cy=250, start=0,
        tstart=0, arc=130, color=127, pre=0)

    # ---- background ------------------------------------------------------
    add("BG0", "BG", start=0, shift=0, srcfill=TAPFILL_RAMP, srcseed=11, pre=0)
    add("BGNOM", "BG", start=BG_START_NOMINAL, shift=BG_SHIFT_NOMINAL,
        srcfill=TAPFILL_PRNG, srcseed=11, pre=0)
    for k, s in enumerate(BG_BOUNDARY):
        add("BGB%d" % k, "BG", start=BG_START_NOMINAL, shift=s,
            srcfill=TAPFILL_PRNG, srcseed=11, pre=0)
    add("BGPRE", "BG", start=101, shift=64893, srcfill=TAPFILL_RAMP,
        srcseed=11, pre=0x11)

    # ---- surface()'s day/night band --------------------------------------
    for plwp in (0, 35, 179, 325, 359):
        add("DK%d" % plwp, "DARK", plwp=plwp, fill=TAPFILL_PRNG, seed=13)
    add("DK3F", "DARK", plwp=200, fill=2, seed=13)

    # ---- whiteglobe / whitesun -------------------------------------------
    #   Three parameterised differences, and the one that is ordering
    #   sensitive (xsun_onscreen written BEFORE the reject tests) is in the
    #   PRE cases below, because it lives in the preamble.
    for nm, sun, mag, fgm, pre in (
            ("WG",    0, f32b(0.30), f32b(0.30), 0),
            ("WS",    1, f32b(0.30), f32b(0.30), 0),
            ("WGNEG", 0, f32b(0.30), f32b(-0.15), 0),   # NOCTIS.CPP:2557
            ("WSNEG", 1, f32b(0.30), f32b(-0.15), 0),
            ("WGSAT", 0, f32b(0.20), f32b(0.30), TAPFILL_C8),  # dst 200: the
            ("WSSAT", 1, f32b(0.20), f32b(0.30), TAPFILL_C8),  # signed-char trap
            ("WGBIG", 0, f32b(2.99), f32b(0.50), 0),
            ("WSBIG", 1, f32b(2.99), f32b(0.50), 0)):
        add(nm, "WHITE", cx=f64b(158.5), cy=f64b(100.5), mag=mag, fgm=fgm,
            sun=sun, pre=pre, seed=17)

    # ---- the shared preamble --------------------------------------------
    #   variant 0 globe, 1 glowinglobe, 2 whiteglobe, 3 whitesun.
    #   The camera is the engine's own: dpp = 210 at NOCTIS.CPP:2214, folded
    #   into opt_pcosbeta and opt_pcosalfa, alfa = beta = 0.  X1 joins these
    #   against Wave 6a's project3d for the same (x,y,z).
    CAMK = dict(pcb=f32b(210.0), psb=f32b(0.0), tcb=f32b(1.0), tsb=f32b(0.0),
                tca=f32b(1.0), tsa=f32b(0.0), pca=f32b(210.0), psa=f32b(0.0))
    for nm, x, y, z, mag, var in (
            # PGCHOP/PLCHOP are the cases that make B-CENTRE's control
            # non-vacuous.  __ftol CHOPS the live extended value
            # (FLOATPOLICY.md 3.3, settled from NOCTIS.EXE file 14437); the
            # 37 hand-written fistp sites round half to even.  At
            # rx = 1.68, ry = 4.83 the two disagree on BOTH components --
            # chop gives (159,104), round gives (160,105) -- so running the
            # oracle with --cast=near moves them.  Without a case like this
            # the +-1 envelope on the centre would pass a systematically
            # wrong rounding mode and nobody would know.
            ("PGCHOP", 8.0, 23.0, 1000.0, f32b(1000.0), 0),
            ("PLCHOP", 8.0, 23.0, 1000.0, f32b(600.0), 1),
            ("PG0",  100.0, 50.0, 1000.0, f32b(1000.0), 0),
            ("PG1",  -700.0, 300.0, 900.0, f32b(1000.0), 0),
            ("PGREJ", 0.0, 0.0, -10.0, f32b(1000.0), 0),
            ("PL0",  100.0, 50.0, 1000.0, f32b(600.0), 1),
            ("PW0",  100.0, 50.0, 1000.0, f32b(400.0), 2),
            ("PS0",  100.0, 50.0, 1000.0, f32b(400.0), 3),
            ("PSREJ", 9000.0, 0.0, 10.0, f32b(400.0), 3)):
        k = dict(CAMK)
        k.update(dzx=f64b(0.0), dzy=f64b(0.0), dzz=f64b(0.0),
                 x=f64b(x), y=f64b(y), z=f64b(z), mag=mag, variant=var)
        add(nm, "PRE", **k)

    # ---- .NCC ------------------------------------------------------------
    #   VEHICLE FIRST and MANDATORY: 150 nonzero slot-3 cells of 156, 26
    #   finite above 1e6 and 2 non-finite, max 2.986e38.  BIRDY has 55 nonzero
    #   cells but its maximum is 20, so a magnitude test on BIRDY is vacuous.
    add("NCCVEH", "NCC", model="VEHICLE", handle=0, reset=1,
        xs=f32b(15.0), ys=f32b(15.0), zs=f32b(15.0),
        xm=f32b(0.0), ym=f32b(0.0), zm=f32b(0.0), base=0, ds=1)
    #   The four surface handles, in the order NOCTIS-1.CPP:3247-3261 loads
    #   them: mamm_base 2, mamm_result 3, bird_base 0, bird_result 1.  The
    #   arena offsets that come out are the DOS numbers and E-ARENA pins them.
    add("NCCMB", "NCC", model="MAMMAL", handle=2, reset=1,
        xs=f32b(1.0), ys=f32b(0.75), zs=f32b(1.0),
        xm=f32b(0.0), ym=f32b(0.0), zm=f32b(0.0), base=0x40, ds=1)
    add("NCCMR", "NCC", model="MAMMAL", handle=3, reset=0,
        xs=f32b(1.0), ys=f32b(1.0), zs=f32b(1.0),
        xm=f32b(0.0), ym=f32b(0.0), zm=f32b(0.0), base=0x80, ds=1)
    add("NCCBB", "NCC", model="BIRDY", handle=0, reset=0,
        xs=f32b(1.0), ys=f32b(0.8), zs=f32b(1.25),
        xm=f32b(0.0), ym=f32b(0.0), zm=f32b(0.0), base=0x40, ds=1)
    add("NCCBR", "NCC", model="BIRDY", handle=1, reset=0,
        xs=f32b(1.0), ys=f32b(1.0), zs=f32b(1.0),
        xm=f32b(0.0), ym=f32b(0.0), zm=f32b(0.0), base=0x80, ds=1)
    #   The synthetic mixed-nv model: the ONLY place the mode-2 `p`-vs-`c`
    #   defect at NOCTIS-0.CPP:2516 is observable, because BIRDY is 20/20
    #   triangles and VEHICLE's mode-2 calls pass use_depth_sort = 0.
    add("NCCSYN", "NCC", model="sp_synth_mixed.ncc", handle=5, reset=1,
        xs=f32b(2.0), ys=f32b(2.0), zs=f32b(2.0),
        xm=f32b(1.0), ym=f32b(-1.0), zm=f32b(0.5), base=0x0C, ds=1)

    # ---- QuickSort -------------------------------------------------------
    #   TIES ARE THE POINT.  The sort is Hoare-partitioned with a mid-element
    #   pivot and is NOT stable, so a tie-free corpus cannot distinguish it
    #   from `sorted()`.  The presence of ties is itself checked.
    add("SORTTIE", "SORT", n=8, frames=1, reset=1,
        **{("d%d" % i): f32b(v) for i, v in
           enumerate([5.0, 5.0, 5.0, 1.0, 9.0, 1.0, 9.0, 5.0])})
    #   Persistence: three frames over the SAME handle, each permuting the
    #   PREVIOUS frame's array.  reset=0 on frames 2 and 3.
    add("SORTP1", "SORT", n=6, frames=1, reset=1,
        **{("d%d" % i): f32b(v) for i, v in
           enumerate([3.0, 1.0, 4.0, 1.0, 5.0, 9.0])})
    add("SORTP2", "SORT", n=6, frames=1, reset=0,
        **{("d%d" % i): f32b(v) for i, v in
           enumerate([2.0, 7.0, 1.0, 8.0, 2.0, 8.0])})
    add("SORTP3", "SORT", n=6, frames=1, reset=0,
        **{("d%d" % i): f32b(v) for i, v in
           enumerate([1.0, 1.0, 1.0, 1.0, 1.0, 1.0])})

    # ---- the pvlist bitfield walk ---------------------------------------
    #   Borland packs `unsigned polygon_id:12` from the LOW bits up, so the
    #   word is id | f0<<12 | f1<<13 | f2<<14 | f3<<15.  The nv=0 entry is
    #   there because modpv's loop is a DO-WHILE and executes once anyway.
    add("PVL1", "PVL",
        list=",".join(str(S.pack_pvlist(*t)) for t in
                      [(0, 1, 1, 1, 0), (1, 1, 1, 1, 0), (0xFFF, 0, 0, 0, 0)]),
        nv="3,3,4,4")
    add("PVL0", "PVL",
        list=",".join(str(S.pack_pvlist(*t)) for t in
                      [(2, 0, 0, 1, 0), (0xFFF, 0, 0, 0, 0)]),
        nv="0,0,0")
    add("PVLALL", "PVL",
        list=",".join(str(S.pack_pvlist(*t)) for t in
                      [(3, 1, 1, 1, 1), (0xFFF, 0, 0, 0, 0)]),
        nv="4,4,4,4")
    return C


def write_keyed(C, path):
    with open(path, "w", newline="\n") as f:
        f.write("# sp_mkcorpus.py -- Wave 6b pinned corpus, keyed grammar.\n")
        f.write("# Regenerated every run.  Never edited by hand.\n")
        for cid, kind, kv in C:
            f.write("CASE %s %s" % (cid, kind))
            for k, v in kv:
                if isinstance(v, str):
                    f.write(" %s=%s" % (k, v))
                elif k in ("mag", "fgm", "pcb", "psb", "tcb", "tsb", "tca",
                           "tsa", "pca", "psa") or k.startswith("d") and k[1:].isdigit() \
                        or k in ("xs", "ys", "zs", "xm", "ym", "zm"):
                    f.write(" %s=%08x" % (k, v & 0xFFFFFFFF))
                elif k in ("cx", "cy", "x", "y", "z", "dzx", "dzy", "dzz") \
                        and kind in ("WHITE", "PRE"):
                    f.write(" %s=%016x" % (k, v & 0xFFFFFFFFFFFFFFFF))
                else:
                    f.write(" %s=%d" % (k, v))
            f.write("\n")


LINO_FIELDS = {
    "GLOBE": ["mag", "cx", "cy", "gman", "start", "colormask", "sat",
              "tapfill", "tapseed", "tapmark", "pre"],
    "GLOW":  ["mag", "cx", "cy", "start", "tstart", "arc", "color", "pre"],
    "BG":    ["start", "shift", "srcfill", "srcseed", "pre"],
    "DARK":  ["plwp", "fill", "seed"],
    "WHITE": ["cx", "cy", "mag", "fgm", "sun", "pre", "seed"],
}


def i32(v):
    v &= 0xFFFFFFFF
    return v - (1 << 32) if v >= (1 << 31) else v


def write_lino(C, path):
    """The lino tokeniser understands exactly one lexeme: a signed decimal
    integer.  Float bit patterns therefore go across as signed 32-bit
    integers, and doubles as two of them (low half first)."""
    nums = []
    emitted = []
    for cid, kind, kv in C:
        if kind not in LINO_FIELDS:
            continue                       # PRE/NCC/SORT/PVL have no lino side
        d = dict(kv)
        emitted.append((cid, kind))
        nums.append(KIND_CODE[kind])
        for k in LINO_FIELDS[kind]:
            v = d[k]
            if kind == "WHITE" and k in ("cx", "cy"):
                nums.append(i32(v & 0xFFFFFFFF))
                nums.append(i32(v >> 32))
            else:
                nums.append(i32(v))
    with open(path, "w", newline="\n") as f:
        f.write("%d\n" % len(emitted))
        for n in nums:
            f.write("%d\n" % n)
    return emitted, nums


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=os.path.dirname(os.path.abspath(__file__)))
    a = ap.parse_args()
    C = build()
    keyed = os.path.join(a.out_dir, "sp_corpus.spc")
    lino = os.path.join(a.out_dir, "sp_corpus.lino")
    write_keyed(C, keyed)
    em, nums = write_lino(C, lino)
    synth = os.path.join(a.out_dir, "sp_synth_mixed.ncc")
    with open(synth, "wb") as f:
        f.write(S.synthetic_ncc_mixed())
    stab = os.path.join(a.out_dir, "sp_synth_skip.map")
    with open(stab, "wb") as f:
        f.write(S.synthetic_globes_table())
    print("cases (keyed)  %d  -> %s" % (len(C), keyed))
    print("cases (lino)   %d  -> %s   (%d integers)" % (len(em), lino, len(nums)))
    print("synthetic mixed-nv model  -> %s  (%d bytes)"
          % (synth, len(S.synthetic_ncc_mixed())))
    print("synthetic skip>=128 table -> %s  (%d bytes)"
          % (stab, len(S.synthetic_globes_table())))
    kinds = {}
    for _, k, _ in C:
        kinds[k] = kinds.get(k, 0) + 1
    print("by kind:", ", ".join("%s=%d" % kv for kv in sorted(kinds.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
