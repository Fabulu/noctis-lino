r"""grv_spec.py - Python reference for Noctis IV's hpoint(), Wave 7b renderer.

PROVENANCE
----------
Transliterated from the DOS sources only:
    C:\programmieren\noctis\niv-plus\source\NOCTIS-1.CPP  hpoint :63-93
    C:\programmieren\noctis\niv-plus\source\NOCTIS-0.CPP  m200[200] :1029, qid :1042
    C:\programmieren\noctis\niv-plus\source\NOCTIS.CPP    m200 init :2156 (m200[i]=i*200)

NOT derived from work/walk.txt (the lino port) and NOT from grv_ref.c (the C
oracle).  Both are written from the same DOS text in separate passes.

FLOAT MODEL (FLOATPOLICY: CW 133Fh, 64-bit mantissa, round to nearest even)
---------------------------------------------------------------------------
hpoint's arithmetic runs on the x87 at extended precision.  Narrowing to
float32 happens ONLY on assignment to a `float` variable: h1..h4, icx, icz,
and py.  Of those, h1..h4 and icx,icz are integer->float conversions of
values that fit exactly in 24 bits (|val| <= 522240 for the heights, < 16384
for icx/icz), so their narrowings are exact.  The two stores to `py` are the
only narrowings that can lose information, and they are modelled with f32().

`qid` is a DOUBLE in the source, so `icx * qid` promotes icx to double; the
whole RHS of the py assignment is double-typed and stays at extended precision
until the py store.  ext() rounds every intermediate op to 64 significand
bits, exactly what the x87 does under PC=11.

The branch test `icx + icz < 16384` is float+float compared to int; both
operands are integers < 16384 so the sum is exact and the decision carries no
float tolerance.  This is what makes hpoint three-way byte-exact.
"""

import struct
from decimal import Decimal, getcontext
from fractions import Fraction

from su_fp import ext, f32, fr, ftol32, round_to_bits

QID = Fraction(1, 16384)                     # double qid = 1.0/16384
getcontext().prec = 80                       # ample for an 80-bit fsqrt


def _sqrt_ext(v):
    """sqrt at extended (64-bit significand), mirroring the x87 fsqrt under
    PC=64.  Computed via Decimal at high precision then rounded to 64 bits."""
    d = Decimal(v.numerator) / Decimal(v.denominator)
    return round_to_bits(Fraction(d.sqrt()), 64)


# ---- fast_random LCG (NOCTIS-0.CPP:1075-1107), exact unsigned model -------
_flat_seed = 0


def fast_srand(seed):
    global _flat_seed
    s = seed & 0xFFFFFFFF
    _flat_seed = (s & 0xFFFF0000) | ((s & 0xFFFF) | 3)


def fast_random(mask):
    global _flat_seed
    s = _flat_seed
    p = s * s
    eax = p & 0xFFFFFFFF
    edx = (p >> 32) & 0xFFFFFFFF
    al = (eax + edx) & 0xFF
    eax = (eax & 0xFFFFFF00) | al
    _flat_seed = (s + eax) & 0xFFFFFFFF
    return eax & mask

M16 = 0xFFFF


def _i32_bits(f32val):
    """The binary32 bit pattern of a (already float32) value, as signed int32."""
    b = struct.pack("<f", f32val)
    u = struct.unpack("<I", b)[0]
    return u - 0x100000000 if u & 0x80000000 else u


def hpoint_bits(px, pz, s1, s2, s3, s4):
    """Return py's binary32 bit pattern (signed int32), exactly as hpoint does.

    s1..s4 are the four surfacemap bytes hpoint reads:
        s1 = p_surfacemap[cpos]       (h1, row z,   col x  )
        s2 = p_surfacemap[cpos+1]     (h2, row z,   col x+1)
        s3 = p_surfacemap[cpos+201]   (h3, row z+1, col x+1)
        s4 = p_surfacemap[cpos+200]   (h4, row z+1, col x  )
    cpos = m200[pz>>14] + (px>>14) = (pz>>14)*200 + (px>>14).
    """
    QID = Fraction(1, 16384)                 # double qid = 1.0/16384

    # h1..h4 are float; (long)<<11 is exact and so is the (float) cast for
    # surf<=255.  Carry them as exact rationals thereafter.
    h1 = fr(-(s1 << 11))
    h2 = fr(-(s2 << 11))
    h3 = fr(-(s3 << 11))
    h4 = fr(-(s4 << 11))

    # icx, icz are float (assigned from `px & 16383`, a long) -> exact.
    icx = fr(px & 16383)
    icz = fr(pz & 16383)

    # The chain is extended (64-bit) throughout; narrow ONLY at the py stores.
    if icx + icz < 16384:
        a = ext(icx * QID)
        b = ext(h2 - h1)
        c = ext(b * a)
        d = ext(h1 + c)
        py = f32(d)                          # py = ...
        e = ext(icz * QID)
        g = ext(ext(h4 - h1) * e)
        h = ext(fr(py) + g)                  # py += ...
        py = f32(h)
    else:
        a = ext((16384 - icx) * QID)
        b = ext(h4 - h3)
        c = ext(b * a)
        d = ext(h3 + c)
        py = f32(d)
        e = ext((16384 - icz) * QID)
        g = ext(ext(h2 - h3) * e)
        h = ext(fr(py) + g)
        py = f32(h)

    return _i32_bits(py)


def run_corpus(path):
    """Yield (opcode, payload_tuple, values_list) for every case.

    opcode 1 (hpoint): payload (px,pz,s1,s2,s3,s4), values [py_bits].
    opcode 2 (fragment): payload (x,z,posx,posz,s1..s4,shd,ssh,seed,branch),
                         values [depth, vy0..vy5, c1].
    """
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            s = line.strip()
            if not s or s[0] == "#":
                continue
            t = [int(x) for x in s.replace(",", " ").split()]
            if not t:
                continue
            op = t[0]
            if op == 1 and len(t) == 7:
                _px, _pz, _s1, _s2, _s3, _s4 = t[1], t[2], t[3], t[4], t[5], t[6]
                yield (1, (_px, _pz, _s1, _s2, _s3, _s4),
                       [hpoint_bits(_px, _pz, _s1, _s2, _s3, _s4)])
            elif op == 2 and len(t) == 13:
                vals = fragment_case(*t[1:])
                yield (2, tuple(t[1:]), vals)
            elif op == 5 and len(t) == 7:
                vals = p_forward_case(*t[1:])
                yield (5, tuple(t[1:]), vals)


def fragment_case(x, z, posx_bits, posz_bits,
                  s1, s2, s3, s4, shd, ssh, seed, branch):
    """Return [depth, vy0..vy5, c1] as integers.

    FAITHFUL surf model: s1..s4 are placed at cpos, cpos+1, cpos+201, cpos+200
    (in that order), then ssh at cpos+sh_delta (LAST, so it overwrites a corner
    when sh_delta coincides - exactly what the real fragment sees).  vy and c1
    read back from this placement.  depth is the exact-required chop.
    """
    posx = fr(struct.unpack("<f", struct.pack("<i", posx_bits))[0])
    posz = fr(struct.unpack("<f", struct.pack("<i", posz_bits))[0])

    fvx0 = f32(x << 14)
    fvx1 = f32((x + 1) << 14)
    fvz0 = f32(z << 14)
    fvz2 = f32((z + 1) << 14)

    half_x = ext(ext(fr(fvx0) + fr(fvx1)) * fr(0.5))
    dx = f32(fr(posx) - half_x)
    half_z = ext(ext(fr(fvz0) + fr(fvz2)) * fr(0.5))
    dz = f32(fr(posz) - half_z)

    dd = ext(fr(dx) * fr(dx)) + ext(fr(dz) * fr(dz))
    hpdep = f32(_sqrt_ext(dd))
    depth = (ftol32(hpdep) >> 14)
    depth -= 1
    if depth < 0:
        depth = 0

    h1 = x + z * 200
    surf = {}                       # last-write-wins placement
    surf[h1] = s1 & 255
    surf[h1 + 1] = s2 & 255
    surf[h1 + 201] = s3 & 255
    surf[h1 + 200] = s4 & 255
    surf[h1 + shd] = ssh & 255
    b1 = surf[h1]
    b2 = surf[h1 + 1]
    b3 = surf[h1 + 201]
    b4 = surf[h1 + 200]
    bsh = surf[h1 + shd]
    vy = [-(b1 << 11), -(b2 << 11), -(b4 << 11),
          -(b2 << 11), -(b3 << 11), -(b4 << 11)]

    if branch == 0:
        fast_srand(h1 + seed)
        c1 = 8 + fast_random(7)
    else:
        c1 = b1 - bsh
    if c1 < 0:
        c1 = 0
    c1 += depth >> 1
    if c1 > 32:
        c1 = 32

    return [depth] + vy + [c1]


def p_forward_case(delta_bits, sbn_bits, cbn_bits, calf_bits, px_bits, pz_bits):
    """NOCTIS-0.CPP:1388-1392 p_Forward.  Returns [new_pos_x_bits, new_pos_z_bits].
    pos_x -= delta*opt_tsinbeta*opt_tcosalfa; pos_z += delta*opt_tcosbeta*opt_tcosalfa.
    The multiply chain is float-typed (extended eval); narrowing to float32
    happens ONLY at the pos_x/pos_z stores."""
    def ld(b):
        return fr(struct.unpack("<f", struct.pack("<i", b))[0])
    delta, sbn, cbn, calf, px, pz = (ld(delta_bits), ld(sbn_bits), ld(cbn_bits),
                                     ld(calf_bits), ld(px_bits), ld(pz_bits))
    prodx = ext(ext(delta * sbn) * calf)
    prodz = ext(ext(delta * cbn) * calf)
    npx = f32(fr(px) - prodx)
    npz = f32(fr(pz) + prodz)
    return [_i32_bits(npx), _i32_bits(npz)]


if __name__ == "__main__":
    import os
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "grv-corpus.txt"
    n = 0
    for op, _payload, vals in run_corpus(path):
        print(op, " ".join(str(v) for v in vals))
        n += 1
    sys.stderr.write("grv_spec: %d cases from %s\n" % (n, os.path.basename(path)))
