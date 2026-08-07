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
from fractions import Fraction

from su_fp import ext, f32, fr

QID = Fraction(1, 16384)                     # double qid = 1.0/16384

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
    """Yield (px,pz,s1,s2,s3,s4,bits) for every case in the corpus text."""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            s = line.strip()
            if not s or s[0] == "#":
                continue
            t = [int(x) for x in s.replace(",", " ").split()]
            if len(t) != 6:
                continue
            px, pz, s1, s2, s3, s4 = t
            yield px, pz, s1, s2, s3, s4, hpoint_bits(px, pz, s1, s2, s3, s4)


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "grv-corpus.txt"
    n = 0
    for _px, _pz, _s1, _s2, _s3, _s4, bits in run_corpus(path):
        print(bits)
        n += 1
    import os
    sys.stderr.write("grv_spec: %d cases from %s\n" % (n, os.path.basename(path)))
