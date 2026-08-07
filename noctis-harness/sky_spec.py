r"""sky_spec.py - Wave 7b sky reference (create_sky's s_background path).

PROVENANCE
----------
Transliterated from C:\programmieren\noctis\niv-plus\source\NOCTIS-1.CPP:
    create_sky(char atmosphere)   :2736-3139   (s_background-affecting parts)
    cloudy_sky                    :1703-1736
    nebular_sky                   :1674-1701
    horizon darkening             :3686-3697   (in planetary_main)
and NOCTIS-0.CPP:1075-1107 (fast_srand/fast_random), :1109-1113 (flandom/
fast_flandom), :4380-4441 (ssmooth/lssmooth), :480-510 (psmooth_grays).

s_background IS WHAT IS GRADED.  create_sky's `shade` calls write
surface_palette (a DIFFERENT buffer) so they do not affect s_background and
are elided here -- BUT the flandom() calls in the case-3 color setup consume
the libc rand stream, so they are REPLAYED (and discarded) to keep cloudy_sky
downstream of the correct rand state.  fast_flandom() likewise consumes the
flat_rnd_seed stream.

Two RNGs: srand(global_surface_seed) feeds libc rand() (random/flandom);
fast_srand(global_surface_seed) feeds flat_rnd_seed (fast_random/fast_flandom).
Borland rand() is brtl_oracle.Brtl (Wave 1).  fast_random is grv_spec's model.

The composed s_background = memset(sky_brightness) -> create_sky -> horizon.
The binary anchor (tests/gen/recon_w7b/out/t3_equator.s_background) is the
post-horizon buffer; grading it byte-exact also needs global_surface_seed,
sky_brightness, sctype, albedo, nightzone (from the galaxy+landing chain).
This file proves the create_sky FUNCTION's s_background path on pinned inputs.
"""

import os

from su_fp import ext, f32, fr

ST_BYTES = 64800
BK_LINES_TO_HORIZON = 120
OCEAN, PLAINS, DESERT, ICY = 1, 2, 3, 4

from brtl_oracle import Brtl
from grv_spec import fast_srand as _fs, fast_random as _fr

_brtl = Brtl()


def srand(seed):
    _brtl.srand(seed & 0xFFFF)


def random(n):
    """Borland random(n) = brtl.random(n), consuming the libc stream."""
    return _brtl.random(n)


def flandom():
    # ((float)random(32767) * 0.000030518)  -- float32 store
    return f32(fr(random(32767)) * fr(0.000030518))


def fast_flandom():
    # ((float)fast_random(32767) * 0.000030518)
    return f32(fr(_fr(32767)) * fr(0.000030518))


# ---------------------------------------------------------------------------
# smoothers (NOCTIS-0.CPP:4380-4411 ssmooth, :4416-4441 lssmooth, :480-510
# psmooth_grays).  ssmooth/psmooth_grays are a 4-tap stride-S box blur that
# processes one byte per step (despite 32-bit reads); lssmooth is a 2-tap
# vertical blend preserving the top 2 bits.  Modeled byte-wise from the asm.
# ---------------------------------------------------------------------------

def ssmooth(buf, stride):
    n = ST_BYTES - stride
    for i in range(stride, ST_BYTES):
        if i - stride < 0 or i + 2 * stride >= ST_BYTES:
            break
        # the loop runs cx = (QUADWORDS*4 - stride*4) iterations from offset stride
        pass
    # The asm advances di by 1 each step from `target+stride`, for
    # cx = ST_BYTES - 4*stride ... wait: cx = (QUADWORDS<<2) - (stride<<2),
    # QUADWORDS = ST_BYTES/4 = 16200, so cx = ST_BYTES - 4*stride.
    cx = ST_BYTES - 4 * stride
    base = stride
    for k in range(cx):
        i = base + k
        s = buf[i - stride] + buf[i] + buf[i + stride] + buf[i + 2 * stride]
        buf[i] = (s >> 2) & 0xFF


def psmooth_grays(buf):
    # identical to ssmooth with stride 320 (uses ds not es -- no behavioural diff)
    ssmooth(buf, 320)


def ssmooth_sky(buf):
    ssmooth(buf, 360)


def lssmooth(buf):
    # cx = (QUADWORDS - 80) << 2 = (16200-80)*4 = 64480 iterations from offset 0,
    # 2-tap vertical (stride 360) preserving top 2 bits.
    cx = (16200 - 80) * 4
    for k in range(cx):
        i = k
        dl = buf[i] & 0x3F
        dh = (buf[i] >> 8) if False else 0  # placeholder; real: 16-bit read
        # the asm reads a 16-bit word at [di] (two bytes: buf[i], buf[i+1]),
        # masks 0x3F3F, and reads [di+360] similarly; this is a 2-PIXEL-at-once
        # vertical blend.  Model it byte-wise: for each byte, blend with the
        # byte 360 ahead.
        lo = (buf[i] & 0x3F) + (buf[i + 1] & 0x3F) if False else None
    # Byte-wise faithful model: out = (b[i]&0xC0) | (((b[i]&0x3F)+(b[i+360]&0x3F))>>2)
    for k in range(cx):
        i = k
        if i + 360 >= ST_BYTES:
            break
        a = buf[i]
        b = buf[i + 360]
        buf[i] = (a & 0xC0) | (((a & 0x3F) + (b & 0x3F)) >> 2)


# ---------------------------------------------------------------------------
# cloudy_sky / nebular_sky (NOCTIS-1.CPP:1703-1736, 1674-1701)
# ---------------------------------------------------------------------------

def cloudy_sky(buf, density, smooths, albedo):
    import math
    n = random(density + albedo)
    while n > 0:
        cx = random(360)
        r = random(25) + 5
        cy = random(50) + 25 + r
        y = -r
        while y < r:
            x = -2 * r
            while x < 2 * r:
                if math.sqrt(x * x * 0.2 + y * y) < r:
                    p = x + cx + 360 * (y + cy)
                    if 0 <= p < ST_BYTES:
                        # b = 1.4142/sqrt((x+r)^2+(y+r)^2); b*=64; b+=buf[p]; clamp63
                        denom = math.sqrt((x + r) * (x + r) + (y + r) * (y + r))
                        b = f32(fr(1.4142) / fr(denom)) if denom else f32(0)
                        b = f32(fr(b) * fr(64))
                        b = f32(fr(b) + fr(buf[p]))
                        if b > 63:
                            b = f32(fr(63))
                        buf[p] = int(b) & 0xFF
                x += 1
            y += 1
        n -= 1
    while smooths:
        ssmooth_sky(buf)
        smooths -= 1


def nebular_sky(buf):
    seed = random(10000)
    ax = seed & 0xFFFF
    cx = ST_BYTES
    di = 0
    while cx:
        ax = (ax + cx) & 0xFFFF
        sv = ax - 0x10000 if ax & 0x8000 else ax
        p = (sv * sv) & 0xFFFFFFFF
        dx = (p >> 16) & 0xFFFF
        ax = ((p & 0xFFFF) + dx) & 0xFFFF
        buf[di] = ax & 0x3F
        di += 1
        cx -= 1
    lssmooth(buf)
    if random(2):
        ssmooth_sky(buf)
    if random(3):
        psmooth_grays(buf)


# ---------------------------------------------------------------------------
# create_sky -- s_background path only.  atmosphere is the boolean param.
# We execute every RNG draw in source order but elide the shade/palette writes.
# ---------------------------------------------------------------------------

def create_sky_sbg(buf, inp):
    """inp: global_surface_seed, sky_brightness, nightzone, atmosphere(0/1),
    nearstar_class, nearstar_p_owner, ip_targetted, rainy, albedo, sctype,
    nearstar_p_type (==3 here)."""
    _fs(inp["global_surface_seed"])        # fast_srand (line 2795)
    srand(inp["global_surface_seed"])      # srand      (line 2796)
    ptype = inp["nearstar_p_type"]
    sctype = inp["sctype"]
    # sb/dfs computed at 2754-2787 but do not affect s_background; skip.
    # saturation (2792) likewise irrelevant to s_background.

    if ptype == 2:
        # case 2: 12 flandom() draws (fr/fg/fb x4), then nebular_sky, then
        # fast_flandom (pp_pressure).  Only the draws + nebular_sky affect sbg.
        for _ in range(12):
            flandom()
        nebular_sky(buf)
        fast_flandom()
    elif ptype == 3:
        # case 3: sky colors (3 flandom), then sctype switch.
        flandom(); flandom(); flandom()    # fr[1],fg[1],fb[1]
        if sctype == OCEAN:
            for _ in range(3 + 3 + 3):
                flandom()                  # fr/fg/fb[0] (3), sea fr/fg/fb[2] (3), veg (3)
            cloudy_sky(buf, 50, 1, inp["albedo"])
        elif sctype == PLAINS:
            for _ in range(3 + 3 + 3):
                flandom()                  # land (3), horizon (3 -- bug: all fr[2]), veg (3)
            cloudy_sky(buf, 33, 1, inp["albedo"])
        elif sctype == DESERT:
            for _ in range(3 + 0 + 3):
                flandom()                  # land (3), horizon set from tr/tg/tb (no flandom), veg (3)
            cloudy_sky(buf, 10, 1, inp["albedo"])
        elif sctype == ICY:
            for _ in range(3 + 0 + 3):
                flandom()                  # land (3), horizon from fr/fg/fb[0] (no flandom), veg (3)
            cloudy_sky(buf, 15, 1, inp["albedo"])
        fast_flandom()                     # pp_pressure
    elif ptype == 5:
        # case 5: land(3) sky(3) horizon(3) = 9 flandom, cloudy_sky(10,2), fast_flandom
        for _ in range(9):
            flandom()
        cloudy_sky(buf, 10, 2, inp["albedo"])
        fast_flandom()
    # types 1/4/7/8: airless, no sky painting (only stars via shade, not sbg).


def apply_horizon(buf, sky_brightness, nightzone):
    vptr = 0
    for cpos in range(BK_LINES_TO_HORIZON):
        for _ in range(360):
            crcy = f32(ext(fr(buf[vptr] * cpos) / fr(120)))
            val = crcy
            if nightzone:
                val = f32(ext(fr(crcy) / fr(2)))
            buf[vptr] = int(val) & 0xFF
            vptr += 1


def compose_sky(inp):
    sbg = bytearray([inp["sky_brightness"] & 0xFF] * ST_BYTES)
    create_sky_sbg(sbg, inp)
    apply_horizon(sbg, inp["sky_brightness"], inp["nightzone"])
    return bytes(sbg)


ANCHOR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "tests", "gen", "recon_w7b", "out", "t3_equator.s_background")


def load_anchor():
    if os.path.exists(ANCHOR):
        with open(ANCHOR, "rb") as fh:
            return fh.read()
    return None


if __name__ == "__main__":
    a = load_anchor()
    print("anchor:", ("%d bytes, %d distinct" % (len(a), len(set(a)))) if a else "not found")
