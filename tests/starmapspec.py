"""The catalogue-matching layer of Tier 2, written out in exact Python.

This is the referee for work/starmap_find.txt and work/starmap_read.txt. Like
galaxyspec it is written against the algorithm as the DOS sources define it,
not transcribed from the L.in.oleum programmes under test, and it uses Python
bignums and Fractions so there is no rounding of its own to get wrong.

Where every rule here comes from, in the Noctis IV Plus sources under
C:\\programmieren\\noctis\\niv-plus\\source:

  * the star hash            NOCTIS-0.CPP sky(), the 0x66-prefixed 16-bit asm.
                             Not repeated here - galaxyspec.py is that referee
                             and test_galaxy.py grades it against C. This file
                             only adds the UNSIGNED fold, which exists solely
                             as a negative control.
  * the record layout        NOCTIS-0.CPP search_id_code: a 4-byte header, then
                             32-byte records; double id at +0, name at +8..27,
                             20h at +28, 'S'/'P' at +29, two ASCII digits at
                             +30..31.
  * the identity             NOCTIS-0.CPP: id = x/1e5 * y/1e5 * z/1e5, i.e.
                             P / 1e15 with P = x*y*z an exact integer.
  * the acceptance window    idscale = 1e-5 in search_id_code, multiplied
                             through by 1e15: |P - trunc(id*1e15)| < 1e10.

Two rules that look like details and are not:

  * exponent 0 is REJECTED, not treated as zero. Two catalogue records land
    there and a key of N = 0 would claim every generated star with |P| < 1e10.
  * |N| must stay below 2^94 so that P - N cannot overflow the port's 96-bit
    difference. Nothing real trips it; it is checked, not assumed.
"""

import bisect
import struct
from fractions import Fraction

import galaxyspec as G

M32 = 0xFFFFFFFF
M96 = (1 << 96) - 1

SECTORSIZE = G.SECTORSIZE          # 100000
WINDOW = 10 ** 10                  # idscale 1e-5, scaled by 1e15
SCALE = 10 ** 15
BIGKEY = 1 << 94                   # the |N| ceiling the key builder enforces
DECOY = 1 << 40                    # the decoy control's perturbation
EMAX = 1068                        # biased exponents at or above this reject
STAR = ord("S")

CATALOGUE = r"C:\programmieren\noctis\niv-plus\data\STARMAP.BIN"

# The author's three hard-coded stars, from NOCTIS-1.CPP. Each entry is
# (name, sector, scale, wanted) meaning (long)(identity * scale) == wanted.
# The sectors are not from the C source - they are what the port claims, and
# test_staranchor.py re-derives them by brute force.
ANCHORS = [
    ("BALASTRACKONASTREYA", (0, -1, -1), 10 ** 6, -37828),
    ("FENIA", (43, -46, -8), 10 ** 5, 1599551984),
    ("YLASTRAVENYA", (-1, 0, -2), 10 ** 8, -11543634),
]


def s32(v):
    v &= M32
    return v - 0x100000000 if v & 0x80000000 else v


def s96(v):
    v &= M96
    return v - (1 << 96) if v & (1 << 95) else v


def limbs96(v):
    v &= M96
    return v & M32, (v >> 32) & M32, (v >> 64) & M32


# ------------------------------------------------------------------ the fold

def fold_unsigned(a, b):
    """The negative control: the same fold with an UNSIGNED product.

    A different high word, therefore a different galaxy - a perfectly
    plausible one that is not this one.
    """
    p = (a & M32) * (b & M32)
    return (((p >> 32) & M32) + (p & M32)) & M32


def hash_sector(sx, sy, sz, fold=G.fold_mul):
    """galaxyspec.hash_sector with the fold left open, for the control.

    With the default fold this must agree with galaxyspec exactly; the tests
    assert that rather than assume it.
    """
    sx &= M32
    sy &= M32
    sz &= M32
    sum_xz = (sx + sz) & M32
    flags = 0

    tx = ((sum_xz & 0x1FFFF) + sx) & M32
    if tx == G.CUTOFF:
        flags |= 1
    tx = (tx - G.CUTOFF) & M32

    accum = fold(tx, sum_xz)
    idk = (sum_xz + accum) & M32

    ty = ((accum & 0x1FFFF) + sy) & M32
    if ty == G.CUTOFF:
        flags |= 2
    ty = (ty - G.CUTOFF) & M32

    accum = fold(ty, idk)

    tz = ((accum & 0x1FFFF) + sz) & M32
    if tz == G.CUTOFF:
        flags |= 4
    tz = (tz - G.CUTOFF) & M32

    return tx, ty, tz, (tx + ty + tz) & M32, flags


def sweep(K, fold=G.fold_mul):
    """Every live sector of the (2K+1)^3 box, as (tx, ty, tz, P) signed.

    A sector whose flags are non-zero is dead - a coordinate landed exactly on
    the cutoff, which in Noctis means there is no star there.
    """
    out = []
    for ix in range(-K, K + 1):
        sx = ix * SECTORSIZE
        for iy in range(-K, K + 1):
            sy = iy * SECTORSIZE
            for iz in range(-K, K + 1):
                tx, ty, tz, _net, flags = hash_sector(sx, sy, iz * SECTORSIZE, fold)
                if flags:
                    continue
                x, y, z = s32(tx), s32(ty), s32(tz)
                out.append((x, y, z, x * y * z))
    return out


# -------------------------------------------------------------- the catalogue

def load_catalogue(path=CATALOGUE):
    """[(ordinal, raw8, tail_u32, type_byte, name)] over the whole file."""
    blob = open(path, "rb").read()
    if (len(blob) - 4) % 32:
        raise ValueError("%s is not 4 + 32n bytes" % path)
    recs = []
    body = blob[4:]
    for i in range(len(body) // 32):
        r = body[i * 32:(i + 1) * 32]
        recs.append((i, r[0:8], struct.unpack_from("<I", r, 28)[0], r[29],
                     r[8:28].rstrip(b" \x00").decode("latin-1")))
    return recs


def decode_exact(raw8):
    """N = trunc(value * 1e15) from the bits, exactly. Returns (N, rejcode).

    rejcode matches the port's Decode: 1 exponent 0, 2 inf/NaN, 3 exponent too
    large, 0 usable.
    """
    (bits,) = struct.unpack("<Q", raw8)
    sgn = bits >> 63
    e = (bits >> 52) & 0x7FF
    m = bits & ((1 << 52) - 1)
    if e == 0:
        return None, 1
    if e == 0x7FF:
        return None, 2
    if e >= EMAX:
        return None, 3
    v = Fraction(m | (1 << 52)) * Fraction(2) ** (e - 1075) * SCALE
    n = v.numerator // v.denominator        # v >= 0, so floor == trunc
    return (-n if sgn else n), 0


TOMB = b"Removed:"


def build_keys(recs, decoy=False):
    """The sorted key table the port builds: 'S' records only, no tombstones,
    no rejects, |N| < 2^94. Returns (sorted [(N, ordinal)], counts dict)."""
    keys = []
    counts = {"nkeys": 0, "nrejkey": 0, "nbigkey": 0}
    for (i, raw, _tail, typ, _name) in recs:
        if typ != STAR:
            continue
        if raw == TOMB:
            continue
        n, rej = decode_exact(raw)
        if rej:
            counts["nrejkey"] += 1
            continue
        if abs(n) >= BIGKEY:
            counts["nbigkey"] += 1
            continue
        if decoy:
            n = s96(n + DECOY)
        keys.append((n, i))
    counts["nkeys"] = len(keys)
    keys.sort()
    return keys, counts


def match(stars, keys):
    """Every (ordinal, x, y, z, P, N) pair with |P - N| < WINDOW.

    Every candidate is a hit, not just the nearest: the identity is symmetric
    in x, y, z and near-equal catalogue ids sit inside one another's windows.
    """
    kn = [k[0] for k in keys]
    hits = []
    for (x, y, z, P) in stars:
        j = bisect.bisect_left(kn, P - WINDOW + 1)
        while j < len(kn) and kn[j] - P < WINDOW:
            hits.append((keys[j][1], x, y, z, P, kn[j]))
            j += 1
    return hits


def run(K, decoy=False, unsigned=False, recs=None):
    """The whole referee: (hits, counts, stars). hits as match() returns."""
    recs = load_catalogue() if recs is None else recs
    keys, counts = build_keys(recs, decoy=decoy)
    stars = sweep(K, fold_unsigned if unsigned else G.fold_mul)
    return match(stars, keys), counts, stars


# ------------------------------------------------------- crafted catalogues

def double_for_N(N):
    """The bytes of a double d with trunc(d * 1e15) exactly N.

    Near the identities this suite pokes at, consecutive doubles are far
    closer together than one scaled unit, so every integer N in range is
    reachable; the search is here to prove it for the N actually used rather
    than to assume it. Raises if N is not reachable.
    """
    import math
    d = N / 1e15
    for cand in (d, math.nextafter(d, 0.0), math.nextafter(d, math.copysign(math.inf, d or 1.0)),
                 math.nextafter(math.nextafter(d, 0.0), 0.0)):
        if cand == 0.0 or math.isinf(cand) or math.isnan(cand):
            continue
        raw = struct.pack("<d", cand)
        n, rej = decode_exact(raw)
        if rej == 0 and n == N:
            return raw
    raise ValueError("no double truncates to %d" % N)


def craft_catalogue(source_bytes, keys):
    """A STARMAP.BIN of the SAME length whose only 'S' records are `keys`.

    keys is a list of N values (or of raw 8-byte doubles). Every other record
    is retyped 'P' so it cannot become a catalogue key. Same length matters:
    the port checks the file size against MAPBYTES and refuses anything else.
    """
    buf = bytearray(source_bytes)
    nrec = (len(buf) - 4) // 32
    if len(keys) > nrec:
        raise ValueError("%d keys will not fit in %d records" % (len(keys), nrec))
    for i in range(nrec):
        buf[4 + 32 * i + 29] = ord("P")
    ords = []
    for j, k in enumerate(keys):
        off = 4 + 32 * j
        buf[off:off + 8] = k if isinstance(k, (bytes, bytearray)) else double_for_N(k)
        buf[off + 29] = ord("S")
        ords.append(j)
    return bytes(buf), ords


# ---------------------------------------------------------------- the artifact

HDR = ("magic K mode nsect nlive ndead nkeys nrejkey nbigkey nhits "
       "overflow anchors unsorted r13 r14 r15").split()
MAGIC = 0x53544D50


def read_find(blob):
    """Unpack starmap_find.bin: (header dict, [(ordinal,x,y,z,P,gap)])."""
    h = dict(zip(HDR, struct.unpack_from("<16I", blob, 0)))
    hits = []
    for i in range(h["nhits"]):
        rec, x, y, z, p0, p1, p2, g0, g1 = struct.unpack_from("<9I", blob, 64 + 36 * i)
        hits.append((rec, s32(x), s32(y), s32(z),
                     s96(p0 | (p1 << 32) | (p2 << 64)), g0 | (g1 << 32)))
    return h, hits
