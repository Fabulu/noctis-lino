#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
sp_spec.py -- Wave 6b, producer P3: an independent Python model built from the
              ASSET BYTES and the 1996 SOURCES.

DERIVED FROM (and from nothing else):
  C:\programmieren\noctis\niv-plus\source\GLOBES.MAP      (22,586 bytes)
  C:\programmieren\noctis\niv-plus\source\OFFSETS.MAP     ( 7,340 bytes)
  C:\programmieren\noctis\niv-plus\source\NCC\*.NCC
  C:\programmieren\noctis\niv-plus\source\NOCTIS-0.CPP    (the inline assembly of
        background():2697, globe():3043, glowinglobe():3173, whiteglobe():3298,
        whitesun():3535, gman1x1..gman4x4:3021-3041, smootharound_64():607,
        loadpv():2303, QuickSort():2421, drawpv():2461, copypv():2574,
        modpv():2593, and the day/night band at :5109-:5124)
  C:\programmieren\noctis\niv-plus\source\NOCTIS-D.H      (x_centro 158, y_centro 100,
        gl_bytes 22586, om_bytes 7340, pv_bytes 20480, the handle numbers,
        struct pvlist)
  C:\programmieren\noctis\niv-plus\source\TDPOLYGS.H:130-137  (riga[200] = 320*c)

NOT derived from: work/sp*.txt (implementer 1's lino), noctis-harness/sp_ref.c
  (implementer 2's C transliteration -- a *different* producer that reads the
  assembly, not this file), or C:\programmieren\noctis\niv-lr (the de-assembled
  C++, which is a KNOWN WRONG ANSWER on glowinglobe's Y clip and on
  background's source offset).  None of those was opened while writing this.

THIS FILE RENDERS NO VERDICTS.  It computes numbers.  Every PASS/FAIL in
Wave 6b is spelled `linoharness.Check.ok` in tests/test_sphere.py, which is
inside w5audit.py's scope.  There is deliberately no sp_grade.py -- see
docs-notes/WAVE6A_RASTER.md O1 for what a second verdict vocabulary produced
last wave.

Usage:  python sp_spec.py                 # print every measurement
        python sp_spec.py --json          # the same, machine readable
        python sp_spec.py --dump OUT [..] # emit an SPDUMP in the shared grammar
"""

import argparse
import json
import math
import os
import struct
import sys

# ---------------------------------------------------------------------------
# 0.  Assets
# ---------------------------------------------------------------------------

SRC = os.environ.get("NOCTIS_SRC", r"C:\programmieren\noctis\niv-plus\source")
NCCDIR = os.path.join(SRC, "NCC")

GL_BYTES = 22586        # NOCTIS-D.H:27
OM_BYTES = 7340         # NOCTIS-D.H:25
PV_BYTES = 20480        # NOCTIS-D.H:55
ST_BYTES = 64800        # NOCTIS-D.H:36   s_background
PL_BYTES = 65552        # NOCTIS-D.H:40   p_background
SC_BYTES = 65540        # NOCTIS-D.H:47   adapted
X_CENTRO = 158          # NOCTIS-D.H:126  (NOT tdpolygs.h's 160: noctis-d.h is
Y_CENTRO = 100          # NOCTIS-D.H:127   included first, NOCTIS-0.CPP:41/720)

# BUFFERMAP.md 4.1: farmalloc returns offset 4.  Every far pointer in this
# wave therefore has offset 4, and the literal `es:[di+4]` in the fill
# managers IS that offset -- it is not an extra constant to add.
FARMALLOC_OFF = 4

RIGA_DGROUP = 0x435C    # NOCTIS.EXE 54124/54931: `mov di, gs:[di+435Ch]`


def asset(name):
    with open(os.path.join(SRC, name), "rb") as f:
        return f.read()


def ncc(name):
    with open(os.path.join(NCCDIR, name + ".NCC"), "rb") as f:
        return f.read()


# ---------------------------------------------------------------------------
# 1.  GLOBES.MAP  --  the decoder, and eleven wrong decoders
# ---------------------------------------------------------------------------
#
# NOCTIS-0.CPP:3030-3041 (the comment above glowinglobe) says it in words:
# "primo byte = Y, secondo byte = X.  Quando la Y e' 100 significa che
#  l'offset originario era 64000 ... una serie di avanzamenti consecutivi
#  lungo il segmento della tappezzeria, indicati ... dal byte X."
#
# The assembly says it in instructions (globe, NOCTIS-0.CPP:3100-3170):
#   cmp byte ptr [si],100 / jne pixel        <- sentinel is the FIRST byte
#   mov al,[si]   / cbw                      <- Y sign-extended 8->16
#   mov al,[si+1] / cbw                      <- X sign-extended 8->16
#   blanket: mov al,[si+1] / xor ah,ah / add bx,ax   <- skip advance UNSIGNED
#   clipout: add bx,1                        <- cursor advances on clipped
#                                               records too
# The int16 reading of this file is an artifact of a constant Y byte sitting
# in the high position.

SENTINEL = 100


def decode_globes(buf,
                  sentinel=SENTINEL,
                  swap_bytes=False,
                  y_signed=True,
                  x_signed=True,
                  skip_unsigned=True,
                  skip_fixed=None,
                  cursor_origin=0):
    """Walk the record stream.  Returns (draws, skips, final_cursor, maxskip).

    `draws` is a list of (cursor, dx, dy).  Every keyword is a decoding
    hypothesis; the shipped reading is the default and each departure is one
    of the negative controls in NEGATIVE_CONTROLS below.
    """
    n = len(buf) // 2
    cur = cursor_origin
    draws, skips, maxskip = [], 0, 0
    for i in range(n):
        a, b = buf[2 * i], buf[2 * i + 1]
        y, x = (b, a) if swap_bytes else (a, b)
        if y == sentinel:
            if skip_fixed is not None:
                adv = skip_fixed
            elif skip_unsigned:
                adv = x
            else:
                adv = x - 256 if x >= 128 else x
            cur += adv
            skips += 1
            maxskip = max(maxskip, adv)
        else:
            dy = (y - 256 if y >= 128 else y) if y_signed else y
            dx = (x - 256 if x >= 128 else x) if x_signed else x
            draws.append((cur, dx, dy))
            cur += 1
    return draws, skips, cur, maxskip


def globes_runs(buf):
    """The draw records grouped into maximal runs between skips.

    Used by the dedup invariant, which needs no predictor at all: MAPS.EXE
    walks a continuous arc, so no (dx,dy) pair may repeat inside one run.
    """
    n = len(buf) // 2
    runs, run = [], []
    for i in range(n):
        y, x = buf[2 * i], buf[2 * i + 1]
        if y == SENTINEL:
            if run:
                runs.append(run)
                run = []
        else:
            run.append(((x - 256 if x >= 128 else x),
                        (y - 256 if y >= 128 else y)))
    if run:
        runs.append(run)
    return runs


def dedup_stats(buf):
    runs = globes_runs(buf)
    repeats, allpairs = 0, set()
    for r in runs:
        seen = set()
        for p in r:
            if p in seen:
                repeats += 1
            seen.add(p)
        allpairs |= seen
    return dict(runs=len(runs), in_run_repeats=repeats,
                distinct_pairs=len(allpairs),
                total=sum(len(r) for r in runs))


# ---------------------------------------------------------------------------
# 2.  The recovered predictor.  PINNED LITERALS -- never refitted at test time.
# ---------------------------------------------------------------------------
#
# A refit would be table-vs-table and is forbidden.  These six numbers were
# fitted once, off-line, and are now frozen source text.  The predictor's
# value is NOT that it fits (it was fitted, so of course it does) -- it is
# that feeding this FIXED function a differently DECODED record stream
# collapses the score.  The predictor grades the DECODER.

P_FX = 250.8530
P_FY = 200.6760
P_D = 2.50666
P_LAT0 = -59.7960
P_DLAT = +1.000740
P_DLON = -1.000960
P_I0 = 5.7350
P_STRIDE = 360


def predict(i, Fx=P_FX, Fy=P_FY, D=P_D, lat0=P_LAT0, dlat=P_DLAT,
            dlon=P_DLON, i0=P_I0, stride=P_STRIDE, ortho=False):
    k = round((i - i0) / stride)
    s = i - i0 - stride * k
    lat = math.radians(lat0 + dlat * k)
    lon = math.radians(dlon * s)
    cl, sl = math.cos(lat), math.sin(lat)
    co, so = math.cos(lon), math.sin(lon)
    if ortho:
        return (Fx * cl * so / D, Fy * sl / D)
    den = D - cl * co
    return (Fx * cl * so / den, Fy * sl / den)


def predictor_stats(draws, pf=predict):
    """GP1..GP4.  |d| <= 1 alone leaks, so four statistics, not one."""
    n = len(draws)
    w1r = w1c = ex = 0
    sx = sy = 0.0
    worst_comp = worst_eu = 0.0
    ss = 0.0
    for (i, dx, dy) in draws:
        px, py = pf(i)
        rx, ry = round(px), round(py)
        if abs(rx - dx) <= 1 and abs(ry - dy) <= 1:
            w1r += 1
        if abs(px - dx) <= 1 and abs(py - dy) <= 1:
            w1c += 1
        if rx == dx and ry == dy:
            ex += 1
        sx += px - dx
        sy += py - dy
        worst_comp = max(worst_comp, abs(px - dx), abs(py - dy))
        worst_eu = max(worst_eu, math.hypot(px - dx, py - dy))
        ss += (px - dx) ** 2 + (py - dy) ** 2
    return dict(
        n=n,
        gp1_within1_rounded=w1r,
        within1_continuous=w1c,          # NOT 10780 -- see the note below
        gp2_mean_dx=sx / n, gp2_mean_dy=sy / n,
        gp3_exact=ex, gp3_frac=ex / n,
        gp4_worst_component=worst_comp,
        worst_euclidean=worst_eu,
        rms_per_component=math.sqrt(ss / (2 * n)),
        rms_per_record=math.sqrt(ss / n),
    )


# GP1 must be written on the ROUNDED difference.  The CONTINUOUS residual has
# 15 exceptions on correct code (10,765/10,780 within 1 px, worst euclidean
# 1.2986), so a "zero exceptions" check on the continuous residual is FALSE on
# a working decoder.  Both sides of GP1 are integers.

def negative_controls(buf):
    """Twelve wrong answers somebody could implement, plus two declared
    resolution rows and one REFUSED row.  Each returns (within1, n)."""
    base, _, _, _ = decode_globes(buf)

    def w1(draws, pf=predict):
        c = 0
        for (i, dx, dy) in draws:
            px, py = pf(i)
            if abs(round(px) - dx) <= 1 and abs(round(py) - dy) <= 1:
                c += 1
        return (c, len(draws))

    out = {}
    out["baseline"] = w1(base)
    out["bytes swapped (x,y)"] = w1(decode_globes(buf, swap_bytes=True)[0])
    out["cursor origin +1"] = w1(decode_globes(buf, cursor_origin=1)[0])
    out["y read unsigned"] = w1(decode_globes(buf, y_signed=False)[0])
    out["x read unsigned"] = w1(decode_globes(buf, x_signed=False)[0])
    out["skip advances by 1"] = w1(decode_globes(buf, skip_fixed=1)[0])
    out["texture stride 256"] = w1(base, lambda i: predict(i, stride=256))
    out["Fx/Fy swapped"] = w1(base, lambda i: predict(i, Fx=P_FY, Fy=P_FX))
    out["isotropic dpp=210"] = w1(base, lambda i: predict(i, Fx=210.0, Fy=210.0))
    out["isotropic dpp=200"] = w1(base, lambda i: predict(i, Fx=200.0, Fy=200.0))
    out["latitude sign flipped"] = w1(base, lambda i: predict(i, lat0=-P_LAT0,
                                                              dlat=-P_DLAT))
    out["longitude sign flipped"] = w1(base, lambda i: predict(i, dlon=-P_DLON))
    out["orthographic"] = w1(base, lambda i: predict(i, ortho=True))
    # Two declared rows: the resolution floor of GP1, printed rather than
    # implied away.
    out["one record dx += 1 (DECLARED: passes)"] = w1(
        [(i, dx + (1 if j == 0 else 0), dy) for j, (i, dx, dy) in enumerate(base)])
    out["one record dx += 2"] = w1(
        [(i, dx + (2 if j == 0 else 0), dy) for j, (i, dx, dy) in enumerate(base)])
    # REFUSED.  Signed and unsigned agree on all 513 skip bytes of the shipped
    # file (max 100), so this control CANNOT distinguish the hypotheses and a
    # check built on it is void.  It is printed with its score so the refusal
    # is a measurement and not an assertion.  The unsigned read is graded
    # against NOCTIS.EXE's `30 E4` at 54190 (sp_bin.py) and against the
    # synthetic table below (synthetic_globes_table), or not at all.
    out["skip read SIGNED (REFUSED: cannot fail)"] = w1(
        decode_globes(buf, skip_unsigned=False)[0])
    return out


def synthetic_globes_table():
    r"""A table the unsigned-skip hypothesis can be graded on.

    The shipped file's largest skip byte is 100, so signed and unsigned agree
    everywhere in it.  This table carries skip bytes 0xC8 (200) and 0xFF
    (255).  Read unsigned the final cursor is 461; read signed it is 6.
    """
    recs = []
    recs.append((0, 5))                 # draw dy=0 dx=5
    recs.append((SENTINEL, 200))        # skip 200 unsigned / -56 signed
    recs.append((-3, -7))               # draw
    recs.append((SENTINEL, 255))        # skip 255 unsigned / -1 signed
    recs.append((10, 10))               # draw
    recs.append((SENTINEL, 4))          # skip 4, agrees under both
    recs.append((-1, 1))                # draw
    b = bytearray()
    for y, x in recs:
        b.append(y & 0xFF)
        b.append(x & 0xFF)
    return bytes(b)


# ---------------------------------------------------------------------------
# 3.  OFFSETS.MAP
# ---------------------------------------------------------------------------
#
# background(), NOCTIS-0.CPP:2712-2745:
#   cmp word ptr [si],64000 / jnb blanket   <- word, little endian, u16
#   blanket: mov bx,[si] / sub bx,64000 / add bp,bx
# so a word >= 64000 advances the SOURCE cursor and paints nothing.  It is a
# skip in the panorama, not a screen wrap: 3,620 paints could otherwise only
# cover ten source rows, and the 48 bands demonstrably cover 48.

def decode_offsets(buf):
    w = list(struct.unpack("<%dH" % (len(buf) // 2), buf))
    segs, i = [], 0
    while i < len(w):
        if w[i] >= 64000:
            segs.append(("SKIP", w[i] - 64000, None))
            i += 1
        else:
            j = i
            while j < len(w) and w[j] < 64000:
                j += 1
            segs.append(("PAINT", j - i, w[i]))
            i = j
    return w, segs


def offsets_structure(buf):
    w, segs = decode_offsets(buf)
    src, bands = 0, []
    for kind, cnt, first in segs:
        if kind == "PAINT":
            bands.append(dict(i=len(bands), src_start=src, width=cnt,
                              src_row=src // 360, src_phase=src % 360,
                              first_off=first,
                              scr_row=first // 320, scr_col=first % 320))
        src += cnt
    paints = [x for x in w if x < 64000]
    widths = [b["width"] for b in bands]
    phases = [b["src_phase"] for b in bands]
    scols = [b["scr_col"] for b in bands]
    # `pixels + skip == 360` is NOT an invariant -- it fails on the real bytes.
    # The +-1/+-2 deviations are deliberate column-phase adjustments.  Ship the
    # thing that IS true instead.
    ps = []
    for k in range(len(segs) - 1):
        if segs[k][0] == "PAINT":
            nxt = segs[k + 1][1] if segs[k + 1][0] == "SKIP" else 0
            ps.append(segs[k][1] + nxt)
    return dict(
        words=len(w), paints=len(paints), skips=len(w) - len(paints),
        segments=len(segs),
        lead_in_skip=segs[0][1] if segs[0][0] == "SKIP" else None,
        trailing_pads=[c for (k, c, _) in segs[-2:] if k == "SKIP"],
        bands=len(bands),
        src_advance=src,
        min_paint=min(paints), max_paint=max(paints),
        max_touched=max(paints) + 1284,
        src_row_invariant=sum(1 for b in bands if b["src_row"] == b["i"] + 2),
        width_palindrome=(widths == widths[::-1]),
        phase_palindrome=(phases == phases[::-1]),
        scr_col_palindrome=(scols == scols[::-1]),
        widths=widths, phases=phases,
        pixels_plus_skip_360=sum(1 for x in ps if x == 360),
        pixels_plus_skip_n=len(ps),
        pixels_plus_skip_devs=sorted(set(x for x in ps if x != 360)),
        band_rows=[b["src_row"] for b in bands],
    )


# ---------------------------------------------------------------------------
# 4.  The exact integer scaler.  NO FLOAT MULTIPLY ANYWHERE IN HERE.
# ---------------------------------------------------------------------------
#
# The whole float content of the sphere pixel loop is
#     fild word ptr temp        ; sign-extended map byte, int16
#     fmul dword ptr mag_factor ; float32
#     fistp word ptr temp       ; CW 133Fh -> round half to EVEN
# dy is 8 bits with sign, dx is 9 bits with sign, mag_factor has a 24-bit
# significand: the exact product needs at most 33 significand bits, which is
# representable at PC=64, so the FMUL rounds NOTHING and the only rounding in
# the chain is the FISTP.  The result is therefore a pure integer function of
# (dy:int16, mag_factor:uint32), and the sphere rasteriser leaves the float
# engine entirely.  A float32 multiply here would pass a casual test and fail
# on the adversarial set -- so it is forbidden, and EX1 proves it by
# enumeration rather than asserting it.

def f32_parts(bits):
    """(sign, mantissa24, exponent) with value = (-1)^s * m * 2^e, exact."""
    s = (bits >> 31) & 1
    e = (bits >> 23) & 0xFF
    m = bits & 0x7FFFFF
    if e == 0xFF:
        return None                    # inf/nan: not reachable from the clamps
    if e == 0:
        return (s, m, -149)            # subnormal (or zero)
    return (s, m | 0x800000, e - 150)


def rhe_scale(v, bits):
    """round_half_even(int16 v * float32 bits), returned as the int16 the
    `fistp word ptr` stores.  Pure integer arithmetic."""
    p = f32_parts(bits)
    if p is None:
        raise ValueError("mag_factor is inf/nan; unreachable through the clamps")
    s, m, e = p
    neg = (s == 1) != (v < 0)
    mag = abs(v) * m
    if e >= 0:
        q = mag << e
    else:
        n = -e
        q = mag >> n
        r = mag & ((1 << n) - 1)
        half = 1 << (n - 1)
        if r > half or (r == half and (q & 1)):
            q += 1
    q = -q if neg else q
    if q < -32768 or q > 32767:
        return -32768                  # x87 integer indefinite, 16-bit store
    return q


def f32(x):
    return struct.unpack("<I", struct.pack("<f", x))[0]


def f32v(bits):
    return struct.unpack("<f", struct.pack("<I", bits))[0]


def adversarial_mags(dys, per=4):
    """The float32 neighbours of (k+0.5)/dy -- the ties, where a float32
    multiply and the exact chain disagree.  This is what makes EX1 a check."""
    out = set()
    for dy in dys:
        if dy == 0:
            continue
        for k in range(-140, 141):
            t = (k + 0.5) / dy
            if not (0.0009 <= abs(t) <= 1.33):
                continue
            b = f32(t)
            for d in range(-per, per + 1):
                nb = b + d
                if 0 < (nb >> 23 & 0xFF) < 0xFF:
                    out.add(nb & 0xFFFFFFFF)
    return sorted(out)


# ---------------------------------------------------------------------------
# 5.  The four fill managers, the colour rule, the mangle, the store rule
# ---------------------------------------------------------------------------
#
# NOCTIS-0.CPP:3021-3041.  The offsets are relative to DI; the +4 is
# farmalloc's offset for `target` (BUFFERMAP 4.1), which globe's prologue
# DISCARDS from AX (`les ax,target` then AX is clobbered) precisely because
# the fill managers carry it as a literal.  There is no second +4.

GMAN_OFFSETS = {
    1: (4,),
    2: (4, 5, 324, 325),
    3: (4, 5, 6, 324, 325, 326, 644, 645, 646),
    4: (4, 5, 6, 7, 324, 325, 326, 327, 644, 645, 646, 647, 964, 965, 966, 967),
}


def globe_colour(tex, sat, colormask):
    """`cmp dl,globe_saturation / jnb asis / mov dl,globe_saturation` then
    `or dl,colormask`.  UNSIGNED compare, and the OR is AFTER the clamp."""
    dl = tex if tex >= sat else sat
    return (dl | colormask) & 0xFF


def mode1_mangle(k):
    """drawpv mode 1, NOCTIS-0.CPP:2500-2506 / :2539-2545:
       mov ax,k / and ax,0x3F / and k,0xC0 / shr ax,1 / or k,ax"""
    return (k & 0xC0) | ((k & 0x3F) >> 1)


def glow_colours(color):
    """glowinglobe, NOCTIS-0.CPP:3202-3208:
       bl=color; bh=color; and bh,0x3F; shr bh,2; or bh,bl&0xC0"""
    return (color & 0xFF, ((color & 0x3F) >> 2) | (color & 0xC0))


def white_store(pix, dst):
    """whiteglobe/whitesun, NOCTIS-0.CPP:3365-3367 / :3595-3599.

    `char pix` is SIGNED (Borland default), `target[pixptr]` is unsigned char,
    the sum is computed in int and truncated back into a signed char, and only
    THEN compared with 0x3F.  Destination 200 with pix 63 therefore stores 7,
    not 63.  Typing pix unsigned is the defect this rule exists to catch.
    """
    v = (pix + dst) & 0xFF
    if v >= 0x80:
        v -= 256                        # (signed char)
    return 0x3F if v > 0x3F else (v & 0xFF)


# ---------------------------------------------------------------------------
# 6.  riga[] and the DGROUP image
# ---------------------------------------------------------------------------
#
# TDPOLYGS.H:130-137 -- `unsigned riga[200]`, riga[c] = 320*c, 400 bytes.
# Both sphere rasterisers reach it as `mov di, gs:riga[di]` with DI ALREADY
# DOUBLED (`add di,di` precedes the `cbw`), so the word index is DI and the
# byte offset is 2*DI.  globe's Y clip guarantees DI in [6,190] and can never
# leave the table.  glowinglobe's Y test is a DISJUNCTION that is true for
# every DI (see sp_bin.py), so it reads outside riga[] and the value it gets
# is whatever DGROUP holds at DS:435Ch +- 2*DI.
#
# That value is NOT RECOVERABLE statically and is declared NOT GRADED.  What
# IS graded is the INDEX SEQUENCE, exactly.  The filler below is a declared
# convention shared by every producer so the pages still compare byte for
# byte; running two different fillers identifies precisely which page bytes
# depend on it, which is the honest boundary of the claim.

def dgroup_image(filler="zeros", seed=0x6B):
    img = bytearray(65536)
    if filler == "ff":
        for i in range(65536):
            img[i] = 0xFF
    elif filler.startswith("prng:"):
        s = int(filler.split(":", 1)[1], 0) & 0xFFFFFFFF
        for i in range(65536):
            s = (s * 1103515245 + 12345) & 0xFFFFFFFF
            img[i] = (s >> 16) & 0xFF
    for c in range(200):
        struct.pack_into("<H", img, RIGA_DGROUP + 2 * c, 320 * c)
    return bytes(img)


def riga_word(dg, di):
    """`mov di, gs:[di + 435Ch]` -- 16-bit effective address, wraps."""
    a = (di + RIGA_DGROUP) & 0xFFFF
    return dg[a] | (dg[(a + 1) & 0xFFFF] << 8)


def riga_in_range(di):
    return 0 <= di <= 398 and (di % 2 == 0)


# ---------------------------------------------------------------------------
# 7.  globe_raster -- pure integer, pinned inputs
# ---------------------------------------------------------------------------
#
# The whole point of the split.  Everything after center_x/center_y/mag_factor
# is integer, so this is byte-comparable with zero tolerance instead of
# envelope-bounded.  The entry takes nothing but its arguments.
#
# The page model is a 65,536-byte SEGMENT, not a 64,000-byte framebuffer:
# every effective address in the original is 16 bits and wraps, and the
# visible page sits at segment offsets 4..64003 because farmalloc returned 4.

class Seg:
    __slots__ = ("b",)

    def __init__(self, fill=0):
        self.b = bytearray([fill]) * 65536

    def w8(self, a, v):
        self.b[a & 0xFFFF] = v & 0xFF

    def r8(self, a):
        return self.b[a & 0xFFFF]

    def page(self):
        return bytes(self.b[FARMALLOC_OFF:FARMALLOC_OFF + 64000])


def globe_raster(table, total_map_bytes, tapestry, start, mag_bits,
                 center_x, center_y, gman, colormask, saturation,
                 seg=None, dg=None):
    """globe()'s asm body, NOCTIS-0.CPP:3100-3170.  Returns a record dict."""
    if seg is None:
        seg = Seg()
    if dg is None:
        dg = dgroup_image()
    cx = total_map_bytes >> 1
    bx = (start + FARMALLOC_OFF) & 0xFFFF        # `add start,ax` : ax=offset(tapestry)
    si = 0
    rej = [0, 0, 0, 0]                            # ylo yhi xlo xhi
    drawn = 0
    tap_min, tap_max = None, None
    while cx:
        if table[si] == SENTINEL:
            adv = table[si + 1]                   # xor ah,ah  -> UNSIGNED
            bx = (bx + adv) & 0xFFFF
            si += 2
            cx -= 1
            continue
        dyv = table[si] - 256 if table[si] >= 128 else table[si]
        di = (rhe_scale(dyv, mag_bits) + center_y) & 0xFFFF
        if di < 6:
            rej[0] += 1
        elif di >= 191:
            rej[1] += 1
        else:
            dxv = table[si + 1] - 256 if table[si + 1] >= 128 else table[si + 1]
            di2 = (di + di) & 0xFFFF              # add di,di BEFORE cbw
            di3 = riga_word(dg, di2)
            ax = (rhe_scale(dxv, mag_bits) + center_x) & 0xFFFF
            if ax < 6:
                rej[2] += 1
            elif ax >= 311:
                rej[3] += 1
            else:
                addr = (di3 + ax) & 0xFFFF
                tex = seg_read_tapestry(tapestry, bx)
                tap_min = bx if tap_min is None else min(tap_min, bx)
                tap_max = bx if tap_max is None else max(tap_max, bx)
                dl = globe_colour(tex, saturation & 0xFF, colormask & 0xFF)
                for o in GMAN_OFFSETS[gman]:
                    seg.w8(addr + o, dl)
                drawn += 1
        bx = (bx + 1) & 0xFFFF                    # clipout: add bx,1
        si += 2
        cx -= 1
    return dict(seg=seg, page=seg.page(), cursor=bx, drawn=drawn,
                rej_ylo=rej[0], rej_yhi=rej[1], rej_xlo=rej[2], rej_xhi=rej[3],
                tap_min=tap_min, tap_max=tap_max)


def seg_read_tapestry(tap, bx):
    """`mov dl, fs:[bx]` -- FS is the tapestry segment, offset 4 is folded
    into BX by `add start,ax`.  The tapestry array here is indexed from the
    SEGMENT ORIGIN, so index bx directly."""
    return tap[bx & 0xFFFF] if (bx & 0xFFFF) < len(tap) else 0


def glow_raster(table, total_map_bytes, start_in, terminator_start,
                terminator_arc, mag_bits, center_x, center_y, color,
                seg=None, dg=None):
    """glowinglobe()'s asm body, NOCTIS-0.CPP:3230-3296.

    The Y test is REPRODUCED AS WRITTEN:
        cmp di,10 / jnb y_ok / cmp di,190 / jb y_ok / jmp clipout
    (di >= 10) OR (di < 190) is true for every 16-bit di, so the clip never
    fires and the `jmp clipout` is unreachable code.  niv-lr replaced it with
    `pos > 10 && pos < 190`, an AND where vanilla has an OR; that is a KNOWN
    WRONG ANSWER and it also empties the OOB index list.
    """
    if seg is None:
        seg = Seg()
    if dg is None:
        dg = dgroup_image()
    light, dark = glow_colours(color)
    start = start_in - terminator_start
    while start < 0:
        start += 360
    dx = start & 0xFFFF
    cx = total_map_bytes >> 1
    si = 0
    oob = []            # the graded index sequence
    oob_writes = []     # page addresses whose value came from an OOB read
    counter = []
    rej = [0, 0, 0]     # y (never), xlo, xhi
    drawn = decim = 0
    while cx:
        if table[si] == SENTINEL:
            dx = (dx + table[si + 1]) & 0xFFFF    # xor ah,ah -> UNSIGNED
            while dx >= 360:
                dx -= 360                          # repeated SUB, not a modulo
            si += 2
            cx -= 1
            counter.append(dx)
            continue
        if dx & 3:
            decim += 1
        else:
            dyv = table[si] - 256 if table[si] >= 128 else table[si]
            di = (rhe_scale(dyv, mag_bits) + center_y) & 0xFFFF
            # the disjunction: (di>=10) or (di<190) -- always true
            if not (di >= 10 or di < 190):
                rej[0] += 1
            else:
                dxv = table[si + 1] - 256 if table[si + 1] >= 128 else table[si + 1]
                di2 = (di + di) & 0xFFFF
                if not riga_in_range(di2):
                    oob.append(di2)
                di3 = riga_word(dg, di2)
                ax = (rhe_scale(dxv, mag_bits) + center_x) & 0xFFFF
                if ax < 9:
                    rej[1] += 1
                elif ax >= 310:
                    rej[2] += 1
                else:
                    addr = ((di3 + ax) + 4) & 0xFFFF
                    seg.w8(addr, dark if dx < terminator_arc else light)
                    if not riga_in_range(di2):
                        oob_writes.append(addr)
                    drawn += 1
        dx = (dx + 1) & 0xFFFF
        if dx >= 360:
            dx = 0
        si += 2
        cx -= 1
        counter.append(dx)
    return dict(seg=seg, page=seg.page(), counter_end=dx, drawn=drawn,
                decimated=decim, rej_y=rej[0], rej_xlo=rej[1], rej_xhi=rej[2],
                oob=oob, oob_n=len(oob),
                oob_min=(min(oob) if oob else -1),
                oob_max=(max(oob) if oob else -1),
                oob_writes=oob_writes,      # a LIST: one entry per
                                            # write, not per distinct address
                light=light, dark=dark, counter=counter)


# ---------------------------------------------------------------------------
# 8.  background()
# ---------------------------------------------------------------------------

def background_raster(offsets, total_map_bytes, source, start, screenshift,
                      seg=None):
    """background()'s asm body, NOCTIS-0.CPP:2704-2748.

    Two things the offset-4 story turns on, both read out of the prologue:
      * DESTINATION: `les ax,target / add screenshift,ax / mov dx,screenshift`
        folds offset(target)==4 INTO the screenshift, and every store is a
        bare es:[di+k].  There is no separate +4.
      * SOURCE: `mov bp,start / add bp,4` carries the literal 4 while
        offset(background) is discarded by `mov bx,es`.
    Under farmalloc offset 4 both collapse to base+index in the flat
    workspace.  niv-lr's commented-out /*+4*/ is a bug in ITS model, not a
    constant we inherit.

    DI = (u16)(word + offset(target) + screenshift).  At the nominal
    screenshift -643 the smallest paint word 2258 gives 67155, which WRAPS to
    1619: this is the first GAME call site of the class-A 16-bit mask, and it
    must be applied at the SEGMENT ORIGIN (base-4), not at the buffer base.
    The two differ only when (screenshift+w) mod 65536 is in {65532..65535}.
    """
    if seg is None:
        seg = Seg()
    dx = (screenshift + FARMALLOC_OFF) & 0xFFFF
    bp = (start + 4) & 0xFFFF
    cx = total_map_bytes >> 1
    si = 0
    paints = skips = 0
    src_min, src_max = None, None
    wrapped = 0
    di_seq = bytearray()
    boundary = []
    while cx:
        w = offsets[si] | (offsets[si + 1] << 8)
        if w >= 64000:
            bp = (bp + (w - 64000)) & 0xFFFF
            skips += 1
        else:
            di = (w + dx) & 0xFFFF
            di_seq += struct.pack("<H", di)
            # The four-value boundary: masking at the SEGMENT ORIGIN and
            # masking at the BUFFER BASE differ exactly when
            # (w + screenshift) mod 65536 lands in {65532..65535}.  Neither
            # defect is expressible in a faithful 16-bit machine -- every
            # effective address wraps by construction -- so the INDEX
            # SEQUENCE is what the flat-workspace port is graded against.
            if (w + screenshift) % 65536 >= 65532:
                boundary.append((w, di))
            if w + dx >= 65536:
                wrapped += 1
            al = source[bp] if bp < len(source) else 0
            src_min = bp if src_min is None else min(src_min, bp)
            src_max = bp if src_max is None else max(src_max, bp)
            for row in (0, 320, 640, 960, 1280):
                for col in range(5):
                    seg.w8(di + row + col, al)
            bp = (bp + 1) & 0xFFFF
            paints += 1
        si += 2
        cx -= 1
    return dict(seg=seg, page=seg.page(), src_cursor=bp, paints=paints,
                skips=skips, wrapped=wrapped, src_min=src_min, src_max=src_max,
                di_seq=bytes(di_seq), boundary=boundary)


# ---------------------------------------------------------------------------
# 9.  surface()'s day/night band, and glowinglobe's terminator derivation
# ---------------------------------------------------------------------------
#
# NOCTIS-0.CPP:5109-5124.  Lighting is BAKED INTO THE TEXTURE.  There is no
# N-dot-L anywhere in the planet path: surface() shifts a 130-degree
# longitude band right by 2 across 179 of the 180 rows, starting plwp+35
# UNREDUCED (there is no mod 360 on `add di,plwp / add di,35`), stride 360.
# Row 179 is never touched.

def surface_band(buf_in, plwp, seg=None):
    if seg is None:
        seg = Seg()
        seg.b[FARMALLOC_OFF:FARMALLOC_OFF + len(buf_in)] = buf_in
    di = (FARMALLOC_OFF + plwp + 35) & 0xFFFF
    lo = hi = di
    for _ in range(179):
        for _c in range(130):
            seg.b[di & 0xFFFF] >>= 2
            hi = max(hi, di)
            di = (di + 1) & 0xFFFF
        di = (di + 230) & 0xFFFF
    return dict(seg=seg, first=lo, last=hi, end=di,
                out=bytes(seg.b[FARMALLOC_OFF:FARMALLOC_OFF + len(buf_in)]))


def terminator_constants(plwp, viewpoint):
    """NOCTIS-0.CPP:5106-5109 (surface) and :5588-5593 (glowinglobe).

    surface stores  term_start = plwp + 35        (reduced mod 360 by hand)
                    term_end   = term_start + 130 (ditto)
    glowinglobe is handed ts = (89+35) - cplx_planet_viewpoint(n) and an arc
    of 130 -- the SAME 35 and the SAME 130 -- so the crescent matches the
    band that was burned into the texture.  Change either constant in one
    place and the two stop agreeing.
    """
    ts = plwp + 35
    if ts >= 360:
        ts -= 360
    te = ts + 130
    if te >= 360:
        te -= 360
    gt = (89 + 35) - viewpoint
    if gt < 0:
        gt += 360
    if gt > 359:
        gt -= 360
    return dict(term_start=ts, term_end=te, glow_ts=gt, glow_arc=130)


# ---------------------------------------------------------------------------
# 10.  .NCC parsing, the pvfile arena, loadpv, QuickSort, drawpv
# ---------------------------------------------------------------------------
#
# Format, read off loadpv (NOCTIS-0.CPP:2323-2351): 2 + 50n bytes --
#   uint16 npolygs, n bytes vertices-per-polygon, then X,Y,Z as float32[4n]
#   each, then n colour bytes.  1 + 16 + 16 + 16 + 1 = 50 per polygon.
# TRAP: for triangles the fourth vertex slot holds UNINITIALISED GARBAGE from
# POLYVERT's editor.  loadpv zeroes it BEFORE the scale pass (:2357-2361);
# reorder those two and the transform produces infinities.

def parse_ncc(buf):
    n = struct.unpack_from("<H", buf, 0)[0]
    if len(buf) != 2 + 50 * n:
        raise ValueError("bad .NCC: %d bytes, header says %d polygons"
                         % (len(buf), n))
    nv = list(buf[2:2 + n])
    ox, oy, oz = 2 + n, 2 + n + 16 * n, 2 + n + 32 * n
    oc = 2 + n + 48 * n
    X = list(struct.unpack_from("<%dI" % (4 * n), buf, ox))
    Y = list(struct.unpack_from("<%dI" % (4 * n), buf, oy))
    Z = list(struct.unpack_from("<%dI" % (4 * n), buf, oz))
    C = list(buf[oc:oc + n])
    return dict(n=n, nv=nv, X=X, Y=Y, Z=Z, C=C,
                off_nv=2, off_x=ox, off_y=oy, off_z=oz, off_c=oc)


def ncc_slot3_stats(m):
    nz = huge = nonfin = 0
    mx = 0.0
    tri = 0
    for p in range(m["n"]):
        if m["nv"][p] != 3:
            continue
        tri += 1
        for arr in (m["X"], m["Y"], m["Z"]):
            b = arr[4 * p + 3]
            if b != 0:
                nz += 1
            v = f32v(b)
            if math.isinf(v) or math.isnan(v):
                nonfin += 1
            else:
                if abs(v) > 1e6:
                    huge += 1
                mx = max(mx, abs(v))
    return dict(triangles=tri, cells=3 * tri, nonzero=nz,
                finite_gt_1e6=huge, nonfinite=nonfin, max_finite=mx)


def arena_layout(loads):
    r"""Reproduce loadpv's pointer arithmetic exactly (NOCTIS-0.CPP:2320-2375).

    `loads` is [(handle, npolygs, depth_sort), ...] in CALL ORDER.

    OVERRULE of BUFFERMODEL 5 alias 9, recorded here and in
    docs-notes/WAVE6B_SPHERES.md: pvfile stays ONE NOCTIS BYTE PER UNIT like
    every other region, and the float sub-arrays are reached through a 4-unit
    assemble/disassemble pair (the pattern alias 7 already uses for the
    STARMAP doubles).  Re-laying the arena out so every float is unit-aligned
    would move every DOS byte offset and would make the 4n-into-n colour
    overrun land somewhere DOS never put it.  Keeping the DOS offsets makes
    that overrun faithfully dead (it lands inside pv_mid_x, which is zeroed
    before any read) instead of conditionally dead.  E-ARENA is the check
    that tells you which layout is in the tree.
    """
    top = 0
    out = {}
    for (h, n, ds) in loads:
        ptr = top
        rec = dict(handle=h, npolygs=n, dataptr=ptr)
        rec["pv_n_vtx"] = top
        top += 1 * n
        rec["pvfile_x"] = top
        top += 16 * n
        rec["pvfile_y"] = top
        top += 16 * n
        rec["pvfile_z"] = top
        top += 16 * n
        rec["pvfile_c"] = top
        top += 1 * n
        rec["mid"] = None
        if ds:
            rec["mid"] = {}
            for nm, sz in (("pv_mid_x", 4), ("pv_mid_y", 4), ("pv_mid_z", 4),
                           ("pv_mid_d", 4), ("pv_dep_i", 2)):
                rec["mid"][nm] = top
                top += sz * n
        rec["datalen"] = top - ptr
        rec["datatop_after"] = top
        # the 4n-into-n colour overrun: `for c<4*npolygs: pvfile_c[c]+=base`
        rec["colour_overrun_lo"] = rec["pvfile_c"] + n
        rec["colour_overrun_hi"] = rec["pvfile_c"] + 4 * n - 1
        rec["overrun_inside_pv_mid_x"] = bool(
            ds and rec["mid"]["pv_mid_x"] <= rec["colour_overrun_lo"]
            and rec["colour_overrun_hi"] < rec["mid"]["pv_mid_x"] + 4 * n)
        out[h] = rec
    return dict(handles=out, datatop=top, pv_bytes=PV_BYTES, fits=top <= PV_BYTES)


def quicksort_trace(index, mdist):
    """NOCTIS-0.CPP:2421-2447 verbatim: Hoare partition, MID-ELEMENT pivot,
    `>` and `<` so it sorts DESCENDING, and the recursion order is
    (start,jq) then (iq,end).  It is NOT stable and it is NOT `sorted()`:
    `pv_dep_i` is PERSISTENT STATE and every frame permutes the previous
    frame's array, so "any correct sort" is a different program."""
    idx = list(index)
    swaps = []

    def qs(start, end):
        jq, iq = end, start
        xq = mdist[idx[(start + end) // 2]]
        while iq <= jq:
            while mdist[idx[iq]] > xq:
                iq += 1
            while mdist[idx[jq]] < xq:
                jq -= 1
            if iq <= jq:
                idx[iq], idx[jq] = idx[jq], idx[iq]
                swaps.append((iq, jq))
                iq += 1
                jq -= 1
        if start < jq:
            qs(start, jq)
        if iq < end:
            qs(iq, end)

    if len(idx) > 0:
        qs(0, len(idx) - 1)
    return idx, swaps


def pvlist_decode(entries):
    """struct pvlist { unsigned polygon_id:12; vtxflag_0..3:1; }  --
    NOCTIS-D.H:180.  Borland packs bitfields from the LOW bits up, so the
    16-bit word is  id | f0<<12 | f1<<13 | f2<<14 | f3<<15.  0xFFF terminates.
    """
    out = []
    for w in entries:
        pid = w & 0x0FFF
        if pid == 0xFFF:
            break
        out.append((pid, (w >> 12) & 1, (w >> 13) & 1,
                    (w >> 14) & 1, (w >> 15) & 1))
    return out


def pvlist_walk(entries, nv_of):
    """modpv's `do { ... } while (v < pv_n_vtx[c]);` -- a DO-WHILE, so the
    body executes ONCE even when the polygon has zero vertices.  A `while`
    loop here is a different program on a degenerate model."""
    touched = []
    for (pid, f0, f1, f2, f3) in pvlist_decode(entries):
        i = 4 * pid
        v = 0
        flags = (f0, f1, f2, f3)
        while True:
            if v < 4 and flags[v]:
                touched.append(i + v)
            v += 1
            if not (v < nv_of(pid)):
                break
    return touched


def pack_pvlist(pid, f0, f1, f2, f3):
    return (pid & 0xFFF) | (f0 << 12) | (f1 << 13) | (f2 << 14) | (f3 << 15)


def synthetic_ncc_mixed():
    """A model with BOTH triangles and quads whose colour bytes and vertex
    counts make the mode-2 `p`-vs-`c` defect (NOCTIS-0.CPP:2516) observable.

    With the three shipped models it is not: BIRDY is 20/20 triangles, and
    VEHICLE's mode-2 calls pass use_depth_sort = 0 so the sorted branch (the
    one carrying the defect) is never entered.  The defect is ported AS
    WRITTEN and graded only here.
    """
    nv = [3, 4, 4, 3, 4, 3]
    n = len(nv)
    b = bytearray(struct.pack("<H", n))
    b += bytes(nv)
    for axis in range(3):
        for p in range(n):
            for v in range(4):
                if v == 3 and nv[p] == 3:
                    val = 1e30 * (p + 1) * (axis + 1)      # garbage slot
                else:
                    val = (p + 1) * 10.0 + v + axis * 0.5
                b += struct.pack("<f", val)
    b += bytes([(p * 7 + 3) & 0x3F for p in range(n)])
    assert len(b) == 2 + 50 * n
    return bytes(b)


# ---------------------------------------------------------------------------
# 11.  whiteglobe / whitesun -- the one BOUNDED surface
# ---------------------------------------------------------------------------
#
# One body, three parameterised differences (NOCTIS-0.CPP:3298 vs :3535):
#   step        whiteglobe 2 / 2.4        whitesun 1 / 1.2
#   store       whiteglobe 2x2 via FS     whitesun 1x1 via target[]
#   xsun        whiteglobe none           whitesun writes xsun_onscreen
#                                          BEFORE the rx/ry reject tests
# The last one is ordering-sensitive: the surface renderer reads
# xsun_onscreen even on frames where the sun is rejected.

def white_body(seg, center_x, center_y, mag_factor, fgm_factor, sun, dg):
    """The double loop, in Python binary64.  This is the ONE BOUNDED surface
    of the wave: sp_ref.c runs the same arithmetic on the live 80-bit x87 and
    the two are compared inside a declared envelope, with a control that
    proves the envelope is not decoration.

    mag <= 300.5 (mag_factor is clamped at 2.99), so whitesun is up to about
    361,000 iterations per call.  The TEST can afford exactness at any speed.
    """
    mag = mag_factor * 100 + 1.5
    fgm = fgm_factor * mag
    shade = mag - fgm
    if shade < 1:
        shade = 1.0
    ise = 0x3F / shade
    magsq = mag * mag
    fgmsq = fgm * fgm
    xstep = 1.0 if sun else 2.0
    ystep = 1.0 if sun else 2.0
    yastep = 1.2 if sun else 2.4
    ya = -mag * 1.2
    yb = center_y + mag
    yy = center_y - mag
    writes = clipped = 0
    while yy < yb:
        xa = -mag
        xb = center_x + mag
        xx = center_x - mag
        while xx < xb:
            if 9 < xx < 313 and 9 < yy < 190:
                zz = xa * xa + ya * ya
                if zz < magsq:
                    if zz > fgmsq:
                        pf = 0x3F - (math.sqrt(zz) - fgm) * ise
                    else:
                        pf = float(0x3F)
                    pix = int(pf)                          # __ftol: chop
                    pix = ((pix & 0xFF) ^ 0x80) - 0x80     # (char)
                    yi = int(yy) & 0xFFFF
                    xi = int(xx) & 0xFFFF
                    ptr = (riga_word(dg, (2 * yi) & 0xFFFF) + xi) & 0xFFFF
                    v = white_store(pix, seg.r8(ptr + FARMALLOC_OFF))
                    seg.w8(ptr + FARMALLOC_OFF, v)
                    if not sun:                            # 2x2, via FS
                        seg.w8(ptr + FARMALLOC_OFF + 1, v)
                        seg.w8(ptr + FARMALLOC_OFF + 320, v)
                        seg.w8(ptr + FARMALLOC_OFF + 321, v)
                    writes += 1
            else:
                clipped += 1
            xa += xstep
            xx += xstep
        ya += yastep
        yy += ystep
    return writes, clipped


def preamble(cam, x, y, z, magbits, variant):
    r"""The five lines every one of the four sphere functions opens with, and
    they are character for character project3d's rotation nucleus.  So
    globe's CENTRE is project3d's projection of the body centre and shares
    dpp -- while the GLOBES.MAP table's focal length is a baked ASSET
    constant that must NOT be derived from dpp.  X1 pins that split.

    The four differ only at the end, and the three roundings are three
    falsifiers:
        project3d    fistp             round half even
        globe        (int)             __ftol: CHOP on the live extended value
        glowinglobe  (unsigned)        ditto
        whiteglobe   + 0.5, no cast    stays a double
    variant: 0 globe, 1 glowinglobe, 2 whiteglobe, 3 whitesun.
    """
    dzx, dzy, dzz = cam["dz"]
    pcb, psb, tcb, tsb, tca, tsa, pca, psa = cam["opt"]
    xx, yy, zz = x - dzx, y - dzy, z - dzz
    rx = xx * pcb + zz * psb
    z2 = zz * tcb - xx * tsb
    rz = z2 * tca + yy * tsa
    ry = yy * pca - z2 * psa
    o = dict(rejected=0, rz=rz, rx=0.0, ry=0.0, mag_out=0, gman=1,
             cx=0, cy=0, cx_d=0.0, cy_d=0.0, xsun=None)
    if rz < 0.001:
        o["rejected"] = 1
        return o
    mf = f32v(magbits)
    mf = f32v(f32(mf / rz))
    if variant == 0:
        if mf < 0.01:
            mf = f32v(f32(0.001))
        if mf > 0.33:
            o["gman"] = 2
        if mf > 0.66:
            o["gman"] = 3
        if mf > 0.99:
            o["gman"] = 4
        if mf > 1.32:
            mf = f32v(f32(1.32))
    elif variant == 1:
        if mf > 0.66:                      # 0.66 FIRST ...
            mf = f32v(f32(0.66))
        if mf < 0.01:                      # ... then 0.001
            mf = f32v(f32(0.001))
    else:
        if mf > 2.99:
            mf = f32v(f32(2.99))
        if mf < 0.01:
            mf = f32v(f32(0.01))
    o["mag_out"] = f32(mf)
    rx = rx / rz
    ry = ry / rz
    o["rx"], o["ry"] = rx, ry
    if variant == 3:
        o["xsun"] = rx + float(X_CENTRO)   # written BEFORE the reject tests
    lim = (292, 232) if variant == 0 else (226, 166) if variant == 1 else (460, 400)
    if rx < -lim[0] or rx > lim[0] or ry < -lim[1] or ry > lim[1]:
        o["rejected"] = 1
        return o
    if variant <= 1:
        o["cx"] = ftol16(rx + float(X_CENTRO))
        o["cy"] = ftol16(ry + float(Y_CENTRO))
        o["cx_d"], o["cy_d"] = float(o["cx"]), float(o["cy"])
    else:
        o["cx_d"] = rx + float(X_CENTRO) + 0.5
        o["cy_d"] = ry + float(Y_CENTRO) + 0.5
        o["cx"], o["cy"] = int(o["cx_d"]), int(o["cy_d"])
    return o


def ftol16(v):
    """Borland __ftol: chop, 64-bit result, C `int` keeps the low 16 bits.
    Settled from NOCTIS.EXE file 14437 -- FLOATPOLICY.md 3.3."""
    if v != v:
        return -32768
    t = int(v) if v >= 0 else -int(-v)
    t &= 0xFFFF
    return t - 65536 if t >= 32768 else t


# ---------------------------------------------------------------------------
# 11b.  loadpv, in the same arithmetic the original uses
# ---------------------------------------------------------------------------
#
# `pvfile_x[c] *= xscale; pvfile_x[c] += xmove;` -- both operands are float32
# and the destination is float32, so the exact product needs at most 48
# significand bits and there is exactly ONE rounding.  Python's float32
# round-trip reproduces it exactly, and that is why N3 is an EXACT check
# rather than a bounded one.  `pv_mid_x[p] /= c` is the one site where the
# 80-bit path and a binary64 path could in principle diverge (double
# rounding); the number of divergences is MEASURED, not assumed.

def _f32(x):
    """`fstp dword ptr` at CW 133Fh: overflow stores +-inf, it does not trap
    (TDPOLYGS.H:139 calls _control87(MCW_EM,MCW_EM), masking every exception).
    Python's struct raises instead, so the saturation is explicit here.  It is
    reached only by the NCCZERO control -- zeroing the slot-3 garbage AFTER
    the scale pass sends VEHICLE's 2.986e38 straight past float32's range,
    which is the whole reason the original zeroes it first."""
    try:
        return struct.unpack("<f", struct.pack("<f", x))[0]
    except OverflowError:
        return math.inf if x > 0 else -math.inf


def loadpv(arena, handle, model, xs, ys, zs, xm, ym, zm, base_color,
           depth_sort, nozero=False, zero_after_scale=False):
    n = model["n"]
    ptr = arena["top"]
    L = {}
    L["nvtx"] = arena["top"]; arena["top"] += 1 * n
    L["x"] = arena["top"]; arena["top"] += 16 * n
    L["y"] = arena["top"]; arena["top"] += 16 * n
    L["z"] = arena["top"]; arena["top"] += 16 * n
    L["c"] = arena["top"]; arena["top"] += 1 * n
    L["has_mid"] = False
    if arena["top"] > PV_BYTES:
        arena["top"] = ptr
        return None
    buf = arena["buf"]
    buf[L["nvtx"]:L["nvtx"] + n] = bytes(model["nv"])
    for nm, arr in (("x", model["X"]), ("y", model["Y"]), ("z", model["Z"])):
        for k, b in enumerate(arr):
            struct.pack_into("<I", buf, L[nm] + 4 * k, b)
    buf[L["c"]:L["c"] + n] = bytes(model["C"])

    def zero_slot3():
        for p in range(n):
            if buf[L["nvtx"] + p] == 3:
                for nm in ("x", "y", "z"):
                    struct.pack_into("<f", buf, L[nm] + 4 * (4 * p + 3), 0.0)

    if not nozero and not zero_after_scale:
        zero_slot3()
    if depth_sort:
        for nm, sz in (("mx", 4), ("my", 4), ("mz", 4), ("md", 4), ("di", 2)):
            L[nm] = arena["top"]
            arena["top"] += sz * n
        L["has_mid"] = True
        if arena["top"] > PV_BYTES:
            arena["top"] = ptr
            return None
    for c in range(4 * n):
        for nm, sc, mv in (("x", xs, xm), ("y", ys, ym), ("z", zs, zm)):
            v = struct.unpack_from("<f", buf, L[nm] + 4 * c)[0]
            v = _f32(v * sc)
            v = _f32(v + mv)
            struct.pack_into("<f", buf, L[nm] + 4 * c, v)
        if L["c"] + c < len(buf):
            buf[L["c"] + c] = (buf[L["c"] + c] + base_color) & 0xFF
    if zero_after_scale and not nozero:
        zero_slot3()
    if depth_sort:
        for p in range(n):
            struct.pack_into("<H", buf, L["di"] + 2 * p, p)
            for nm in ("md", "mx", "my", "mz"):
                struct.pack_into("<f", buf, L[nm] + 4 * p, 0.0)
            v = buf[L["nvtx"] + p]
            if v:
                for nm, src in (("mx", "x"), ("my", "y"), ("mz", "z")):
                    acc = 0.0
                    for c in range(v):
                        acc = _f32(acc + struct.unpack_from(
                            "<f", buf, L[src] + 4 * (4 * p + c))[0])
                    struct.pack_into("<f", buf, L[nm] + 4 * p, acc)
                for nm in ("mx", "my", "mz"):
                    a = struct.unpack_from("<f", buf, L[nm] + 4 * p)[0]
                    struct.pack_into("<f", buf, L[nm] + 4 * p, _f32(a / v))
    L["dataptr"] = ptr
    L["datalen"] = arena["top"] - ptr
    L["n"] = n
    arena["h"][handle] = L
    return L


def new_arena():
    return dict(buf=bytearray(PV_BYTES + 4096), top=0, h={})


# ---------------------------------------------------------------------------
# 12.  Report
# ---------------------------------------------------------------------------

def measure_all():
    gm = asset("GLOBES.MAP")
    om = asset("OFFSETS.MAP")
    sup = asset("SUPPORTS.NCT")
    draws, skips, cur, maxskip = decode_globes(gm)
    dxs = [d[1] for d in draws]
    dys = [d[2] for d in draws]
    x100 = sum(1 for i in range(len(gm) // 2)
               if gm[2 * i] != SENTINEL and gm[2 * i + 1] == SENTINEL)
    st = predictor_stats(draws)
    R = {}
    R["globes"] = dict(
        bytes=len(gm), records=len(gm) // 2, draws=len(draws), skips=skips,
        final_cursor=cur, max_skip_byte=maxskip,
        draw_x_byte_eq_100=x100,
        dy_min=min(dys), dy_max=max(dys),
        dx_min=min(dxs), dx_max=max(dxs),
        skip_total=cur - len(draws),
        sentinel_margin=SENTINEL - max(abs(min(dys)), abs(max(dys))),
        is_tail_of_supports=(sup[-len(gm):] == gm),
        last_draw_cursor=draws[-1][0],
    )
    R["predictor"] = st
    R["negative_controls"] = negative_controls(gm)
    R["dedup"] = dedup_stats(gm)
    R["offsets"] = offsets_structure(om)
    R["ncc"] = {}
    for nm in ("VEHICLE", "MAMMAL", "BIRDY"):
        m = parse_ncc(ncc(nm))
        s = ncc_slot3_stats(m)
        s["n"] = m["n"]
        s["nv_set"] = sorted(set(m["nv"]))
        s["quads"] = sum(1 for v in m["nv"] if v == 4)
        s["colour_min"] = min(m["C"])
        s["colour_max"] = max(m["C"])
        s["size"] = 2 + 50 * m["n"]
        R["ncc"][nm] = s
    R["arena_vehicle"] = arena_layout([(0, 116, 1)])
    R["arena_surface"] = arena_layout([(2, 55, 1), (3, 55, 1),
                                       (0, 20, 1), (1, 20, 1)])
    R["terminator"] = terminator_constants(89, 0)
    R["gman_offsets"] = {k: list(v) for k, v in GMAN_OFFSETS.items()}
    R["glow_colours_127"] = list(glow_colours(127))
    syn = synthetic_globes_table()
    du, _, cu, _ = decode_globes(syn)
    dsg, _, cs, _ = decode_globes(syn, skip_unsigned=False)
    R["synthetic_skip_table"] = dict(bytes=len(syn), cursor_unsigned=cu,
                                     cursor_signed=cs, draws=len(du))
    return R


# ---------------------------------------------------------------------------
# 13.  The SPDUMP driver -- the SAME record grammar sp_ref.c emits
# ---------------------------------------------------------------------------
#
# Two producers, disjoint owners in the sense that matters here: this one is
# written from the ASSET BYTES and the C source text, sp_ref.c is written from
# the INLINE ASSEMBLY, and neither reads the other's output.  Joining their
# dumps field by field is what turns "the table decodes" into a check on the
# four arithmetic steps that follow it (+centre, xmag, clip, store).
#
# It is NOT a check on the geometry -- feeding GLOBES.MAP to two
# implementations and getting one page proves they agree about arithmetic and
# nothing about latitude.  That is what the predictor is for, and the wave
# report must say so with a count rather than let a reader infer it.

import hashlib


def _fill(buf, n, which, seed):
    if which == 0:
        return bytes(n)
    if which == 1:
        return bytes((i & 0x3F) for i in range(n))
    if which == 2:
        return b"\x3f" * n
    if which == 3:
        return b"\xc8" * n
    out = bytearray(n)
    s = seed if seed else 1
    for i in range(n):
        s = (s * 1103515245 + 12345) & 0xFFFFFFFF
        out[i] = (s >> 16) & 0xFF
    return bytes(out)


def parse_corpus(path):
    cases = []
    with open(path) as f:
        for ln in f:
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            parts = ln.split()
            if len(parts) < 3 or parts[0] != "CASE":
                continue
            cid, kind = parts[1], parts[2]
            kv = {}
            for tok in parts[3:]:
                if "=" in tok:
                    k, v = tok.split("=", 1)
                    kv[k] = v
            cases.append((cid, kind, kv))
    return cases


def _i(kv, k, d=0):
    return int(kv[k], 0) if k in kv else d


def _h32(kv, k, d=0):
    return int(kv[k], 16) if k in kv else d


def _h64f(kv, k, d=0.0):
    if k not in kv:
        return d
    return struct.unpack("<d", struct.pack("<Q", int(kv[k], 16)))[0]


def run_dump(corpus_path, out, pagedir=None, dgfill="zeros",
             nozero=False, zero_after=False):
    cases = parse_corpus(corpus_path)
    gm = asset("GLOBES.MAP")
    om = asset("OFFSETS.MAP")
    dg = dgroup_image(dgfill)
    here = os.path.dirname(os.path.abspath(corpus_path))
    out.write("SPDUMP 1 producer=sp_spec.py cast=chop castsrc=f64 "
              "scalemul=int nozero=%d dgroup=%s\n" % (int(nozero), dgfill))
    out.write("ASSET globes bytes=%d\n" % len(gm))
    out.write("ASSET offsets bytes=%d\n" % len(om))
    arena = new_arena()
    sort_idx = {}

    def page_out(cid, seg):
        p = seg.page()
        out.write("PAGE %s %s\n" % (cid, hashlib.sha256(p).hexdigest()))
        if pagedir:
            with open(os.path.join(pagedir, cid + ".page"), "wb") as f:
                f.write(p)

    for cid, kind, kv in cases:
        if kind == "GLOBE":
            seg = Seg(_i(kv, "pre"))
            tap = bytearray(_fill(None, 65536, _i(kv, "tapfill", 1),
                                  _i(kv, "tapseed", 7)))
            mk = _i(kv, "tapmark", -1)
            if 0 <= mk < 65536:
                tap[mk] = 0x2A
            r = globe_raster(gm, len(gm), bytes(tap), _i(kv, "start"),
                             _h32(kv, "mag"), _i(kv, "cx"), _i(kv, "cy"),
                             _i(kv, "gman", 1), _i(kv, "colormask"),
                             _i(kv, "sat"), seg=seg, dg=dg)
            out.write("GLOBE %s cursor=%d drawn=%d ylo=%d yhi=%d xlo=%d xhi=%d "
                      "tapmin=%d tapmax=%d\n"
                      % (cid, r["cursor"], r["drawn"], r["rej_ylo"],
                         r["rej_yhi"], r["rej_xlo"], r["rej_xhi"],
                         -1 if r["tap_min"] is None else r["tap_min"],
                         -1 if r["tap_max"] is None else r["tap_max"]))
            page_out(cid, seg)
        elif kind == "GLOW":
            seg = Seg(_i(kv, "pre"))
            r = glow_raster(gm, len(gm), _i(kv, "start"), _i(kv, "tstart"),
                            _i(kv, "arc", 130), _h32(kv, "mag"),
                            _i(kv, "cx") & 0xFFFF, _i(kv, "cy") & 0xFFFF,
                            _i(kv, "color", 127), seg=seg, dg=dg)
            for v in r["oob"]:
                out.write("OOB %s %d\n" % (cid, v))
            out.write("GLOW %s counter=%d drawn=%d decim=%d rejy=%d xlo=%d "
                      "xhi=%d oobn=%d oobmin=%d oobmax=%d oobw=%d light=%d dark=%d\n"
                      % (cid, r["counter_end"], r["drawn"], r["decimated"],
                         r["rej_y"], r["rej_xlo"], r["rej_xhi"], r["oob_n"],
                         r["oob_min"], r["oob_max"], len(r["oob_writes"]),
                         r["light"], r["dark"]))
            page_out(cid, seg)
        elif kind == "BG":
            seg = Seg(_i(kv, "pre"))
            src = _fill(None, 65536, _i(kv, "srcfill", 1), _i(kv, "srcseed", 11))
            r = background_raster(om, len(om), src, _i(kv, "start"),
                                  _i(kv, "shift"), seg=seg)
            for (w, di) in r["boundary"]:
                out.write("BGB %s %d %d\n" % (cid, w, di))
            out.write("BG %s src=%d paints=%d skips=%d wrapped=%d smin=%d "
                      "smax=%d boundary=%d\n"
                      % (cid, r["src_cursor"], r["paints"], r["skips"],
                         r["wrapped"], r["src_min"], r["src_max"],
                         len(r["boundary"])))
            out.write("BGIDX %s %d %s\n"
                      % (cid, r["paints"], hashlib.sha256(r["di_seq"]).hexdigest()))
            page_out(cid, seg)
        elif kind == "DARK":
            seg = Seg(0)
            seg.b[FARMALLOC_OFF:FARMALLOC_OFF + 64800] = _fill(
                None, 64800, _i(kv, "fill", 1), _i(kv, "seed", 13))
            di = (FARMALLOC_OFF + _i(kv, "plwp") + 35) & 0xFFFF
            first, last = di, di
            for _r in range(179):
                for _c in range(130):
                    seg.b[di] >>= 2
                    last = max(last, di)
                    di = (di + 1) & 0xFFFF
                di = (di + 230) & 0xFFFF
            out.write("DARK %s first=%d last=%d\n" % (cid, first, last))
            page_out(cid, seg)
        elif kind == "WHITE":
            seg = Seg(0)
            seg.b[FARMALLOC_OFF:FARMALLOC_OFF + 64000] = _fill(
                None, 64000, _i(kv, "pre", 0), _i(kv, "seed", 17))
            w, cl = white_body(seg, _h64f(kv, "cx", 160.0), _h64f(kv, "cy", 100.0),
                               f32v(_h32(kv, "mag")), f32v(_h32(kv, "fgm")),
                               _i(kv, "sun"), dg)
            out.write("WHITE %s writes=%d clipped=%d\n" % (cid, w, cl))
            page_out(cid, seg)
        elif kind == "PRE":
            cam = dict(dz=(_h64f(kv, "dzx"), _h64f(kv, "dzy"), _h64f(kv, "dzz")),
                       opt=tuple(f32v(_h32(kv, k, f32(d))) for k, d in
                                 (("pcb", 210.0), ("psb", 0.0), ("tcb", 1.0),
                                  ("tsb", 0.0), ("tca", 1.0), ("tsa", 0.0),
                                  ("pca", 210.0), ("psa", 0.0))))
            r = preamble(cam, _h64f(kv, "x"), _h64f(kv, "y"), _h64f(kv, "z"),
                         _h32(kv, "mag"), _i(kv, "variant"))
            b = lambda v: struct.unpack("<Q", struct.pack("<d", v))[0]
            out.write("PRE %s rej=%d rz=%016x rx=%016x ry=%016x mag=%08x "
                      "gman=%d cx=%d cy=%d xsunw=%d\n"
                      % (cid, r["rejected"], b(r["rz"]), b(r["rx"]), b(r["ry"]),
                         r["mag_out"], r["gman"], r["cx"], r["cy"],
                         1 if r["xsun"] is not None else 0))
            if r["xsun"] is not None:
                out.write("XSUN %s %016x\n" % (cid, b(r["xsun"])))
            if _i(kv, "variant") >= 2:
                out.write("WCENTRE %s %016x %016x\n"
                          % (cid, b(r["cx_d"]), b(r["cy_d"])))
        elif kind == "NCC":
            name = kv.get("model", "")
            if _i(kv, "reset"):
                arena.clear()
                arena.update(new_arena())
            path = os.path.join(NCCDIR, name + ".NCC")
            if not os.path.exists(path):
                path = os.path.join(here, name)
            if not os.path.exists(path):
                out.write("NCCERR %s %s\n" % (cid, name))
                continue
            with open(path, "rb") as f:
                model = parse_ncc(f.read())
            h = _i(kv, "handle")
            L = loadpv(arena, h, model,
                       f32v(_h32(kv, "xs", f32(1.0))), f32v(_h32(kv, "ys", f32(1.0))),
                       f32v(_h32(kv, "zs", f32(1.0))), f32v(_h32(kv, "xm", 0)),
                       f32v(_h32(kv, "ym", 0)), f32v(_h32(kv, "zm", 0)),
                       _i(kv, "base"), _i(kv, "ds", 1),
                       nozero=nozero, zero_after_scale=zero_after)
            if L is None:
                out.write("NCCERR %s %s\n" % (cid, name))
                continue
            out.write("ARENA %s h=%d n=%d ptr=%d nvtx=%d x=%d y=%d z=%d c=%d "
                      "mx=%d my=%d mz=%d md=%d di=%d len=%d top=%d mid=%d\n"
                      % (cid, h, L["n"], L["dataptr"], L["nvtx"], L["x"],
                         L["y"], L["z"], L["c"], L.get("mx", 0), L.get("my", 0),
                         L.get("mz", 0), L.get("md", 0), L.get("di", 0),
                         L["datalen"], arena["top"], int(L["has_mid"])))
            buf = arena["buf"]
            nonfin = 0
            for k in range(L["n"]):
                if buf[L["nvtx"] + k] != 3:
                    continue
                vals = tuple(struct.unpack_from("<I", buf,
                                                L[nm] + 4 * (4 * k + 3))[0]
                             for nm in ("x", "y", "z"))
                out.write("SLOT3 %s %d %08x %08x %08x\n" % ((cid, k) + vals))
            for k in range(4 * L["n"]):
                for nm in ("x", "y", "z"):
                    v = struct.unpack_from("<f", buf, L[nm] + 4 * k)[0]
                    if math.isinf(v) or math.isnan(v):
                        nonfin += 1
                        break
            out.write("NONFIN %s %d\n" % (cid, nonfin))
            if L["has_mid"]:
                for k in range(L["n"]):
                    out.write("MID %s %d %08x %08x %08x\n"
                              % (cid, k,
                                 struct.unpack_from("<I", buf, L["mx"] + 4 * k)[0],
                                 struct.unpack_from("<I", buf, L["my"] + 4 * k)[0],
                                 struct.unpack_from("<I", buf, L["mz"] + 4 * k)[0]))
        elif kind == "SORT":
            n = _i(kv, "n")
            if n <= 0:
                continue
            if _i(kv, "reset", 1) or "cur" not in sort_idx:
                sort_idx["cur"] = list(range(n))
            if len(sort_idx["cur"]) != n:
                sort_idx["cur"] = list(range(n))
            dist = [f32v(_h32(kv, "d%d" % i, f32(float(i)))) for i in range(n)]
            idx = sort_idx["cur"]
            for fr in range(_i(kv, "frames", 1)):
                idx, swaps = quicksort_trace(idx, dist)
                for (a, b2) in swaps:
                    out.write("SWAP %s %d %d\n" % (cid, a, b2))
                out.write("SORT %s %d %s\n"
                          % (cid, fr, " ".join(str(v) for v in idx)))
            sort_idx["cur"] = idx
        elif kind == "PVL":
            ent = [int(t) for t in kv.get("list", "").split(",") if t]
            nv = [int(t) for t in kv.get("nv", "").split(",") if t]

            def nv_of(p):
                return nv[p] if p < len(nv) else 0
            out.write("PVL %s %s\n"
                      % (cid, " ".join(str(v) for v in pvlist_walk(ent, nv_of))))
    return len(cases)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--corpus")
    ap.add_argument("--out")
    ap.add_argument("--pages")
    ap.add_argument("--dgroup", default="zeros")
    ap.add_argument("--nozero", action="store_true")
    ap.add_argument("--zero-after-scale", action="store_true",
                    help="the NCCZERO sabotage: zero slot 3 AFTER the scale pass")
    a = ap.parse_args()
    if a.corpus:
        f = open(a.out, "w", newline="\n") if a.out else sys.stdout
        if a.pages:
            os.makedirs(a.pages, exist_ok=True)
        n = run_dump(a.corpus, f, a.pages, a.dgroup, a.nozero, a.zero_after_scale)
        if a.out:
            f.close()
            print("sp_spec.py: %d cases -> %s" % (n, a.out))
        return 0
    R = measure_all()
    if a.json:
        json.dump(R, sys.stdout, indent=1, sort_keys=True, default=str)
        print()
        return 0
    g = R["globes"]
    print("=== GLOBES.MAP (%d bytes, tail of SUPPORTS.NCT: %s) ==="
          % (g["bytes"], g["is_tail_of_supports"]))
    print("  records %d = draws %d + skips %d" % (g["records"], g["draws"], g["skips"]))
    print("  final cursor %d   (skip total %d, max skip byte %d)"
          % (g["final_cursor"], g["skip_total"], g["max_skip_byte"]))
    print("  dy %d..%d  dx %d..%d   sentinel margin %d"
          % (g["dy_min"], g["dy_max"], g["dx_min"], g["dx_max"], g["sentinel_margin"]))
    print("  draw records whose X byte is 100: %d" % g["draw_x_byte_eq_100"])
    p = R["predictor"]
    print("=== predictor (pinned literals, never refitted) ===")
    print("  GP1 within-1 ROUNDED    %d / %d" % (p["gp1_within1_rounded"], p["n"]))
    print("      within-1 continuous %d / %d   <-- 15 exceptions on CORRECT code"
          % (p["within1_continuous"], p["n"]))
    print("  GP2 mean signed         %+.4f  %+.4f" % (p["gp2_mean_dx"], p["gp2_mean_dy"]))
    print("  GP3 exact fraction      %.4f  (%d)" % (p["gp3_frac"], p["gp3_exact"]))
    print("  GP4 worst component     %.4f   (worst euclid %.4f)"
          % (p["gp4_worst_component"], p["worst_euclidean"]))
    print("  RMS %.4f per component / %.4f per record"
          % (p["rms_per_component"], p["rms_per_record"]))
    print("=== negative controls (within-1 out of 10780) ===")
    for k, (c, n) in R["negative_controls"].items():
        print("  %-42s %6d / %d" % (k, c, n))
    d = R["dedup"]
    print("=== dedup (formula-free) ===")
    print("  %d runs, %d in-run repeated pairs, %d distinct pairs globally"
          % (d["runs"], d["in_run_repeats"], d["distinct_pairs"]))
    o = R["offsets"]
    print("=== OFFSETS.MAP ===")
    print("  %d words = %d paints + %d skips; %d segments; %d bands"
          % (o["words"], o["paints"], o["skips"], o["segments"], o["bands"]))
    print("  source advance %d; paint offsets %d..%d; max touched %d"
          % (o["src_advance"], o["min_paint"], o["max_paint"], o["max_touched"]))
    print("  src_row(band i)==i+2 : %d/%d   width palindrome %s   phase palindrome %s"
          % (o["src_row_invariant"], o["bands"], o["width_palindrome"],
             o["phase_palindrome"]))
    print("  pixels+skip==360     : %d/%d  <-- NOT an invariant; deviations %s"
          % (o["pixels_plus_skip_360"], o["pixels_plus_skip_n"],
             o["pixels_plus_skip_devs"]))
    print("=== .NCC ===")
    for nm, s in R["ncc"].items():
        print("  %-8s n=%3d nv=%s  slot3: %d/%d nonzero, %d finite>1e6, %d nonfinite, max %.4g"
              % (nm, s["n"], s["nv_set"], s["nonzero"], s["cells"],
                 s["finite_gt_1e6"], s["nonfinite"], s["max_finite"]))
    for nm, key in (("vehicle", "arena_vehicle"), ("surface", "arena_surface")):
        A = R[key]
        print("=== pvfile arena (%s) datatop %d / %d  fits=%s ==="
              % (nm, A["datatop"], A["pv_bytes"], A["fits"]))
        for h, rec in sorted(A["handles"].items()):
            print("    h%-2d n=%-4d dataptr %-6d x@%-6d c@%-6d len %-5d overrun in pv_mid_x: %s"
                  % (h, rec["npolygs"], rec["dataptr"], rec["pvfile_x"],
                     rec["pvfile_c"], rec["datalen"], rec["overrun_inside_pv_mid_x"]))
    s = R["synthetic_skip_table"]
    print("=== synthetic skip table (the only place unsigned-skip is gradeable) ===")
    print("  %d bytes, %d draws, cursor unsigned %d vs signed %d"
          % (s["bytes"], s["draws"], s["cursor_unsigned"], s["cursor_signed"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
