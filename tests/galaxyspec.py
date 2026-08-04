"""The Noctis IV star-position hash, written out in arbitrary-precision Python.

This is the referee the L.in.oleum implementations are graded against. It is
deliberately written against the algorithm rather than transcribed from any of
the implementations under test, and Python's bignums make the 64-bit product
exact by construction, so there is no hardware behaviour here to get wrong.

The one detail everything turns on: the multiply is SIGNED. Sector coordinates
go negative either side of the galactic centre, and an unsigned product yields
a different high word - a perfectly plausible galaxy that is not this one.

A record is 5 little-endian uint32: temp_x, temp_y, temp_z, netpos, flags.
Cutoff hits are recorded as flag bits rather than skipping the sector, so the
arithmetic is exercised on every coordinate fed in.

These constants are a PIN, not a lookup: work/galaxy.txt and work/galaxy2.txt
are checked against them by test_galaxy.py. Widening the sweep in the lino
sources without updating them here is meant to fail the suite.
"""

import struct

M32 = 0xFFFFFFFF
CUTOFF = 50000
SECTORSIZE = 100000
SPAN = 7
KOFFSET = 3
PERSECTOR = 5
REC = PERSECTOR * 4


def s32(v):
    """Reinterpret the low 32 bits of v as signed two's complement."""
    v &= M32
    return v - 0x100000000 if v & 0x80000000 else v


def fold_mul(a, b):
    """Signed 32x32 -> 64 multiply with the high half folded into the low.

    The original's `imul ebx` followed by `add eax, edx`. galaxy.txt spells it
    as an inline { F7 EB } fragment; galaxy2.txt spells it `A *% B; A + B;`.
    """
    p = s32(a) * s32(b)
    return (((p >> 32) & M32) + (p & M32)) & M32


def hash_sector(sect_x, sect_y, sect_z):
    sect_x &= M32
    sect_y &= M32
    sect_z &= M32

    sum_xz = (sect_x + sect_z) & M32
    flags = 0

    temp_x = ((sum_xz & 0x0001FFFF) + sect_x) & M32
    if temp_x == CUTOFF:
        flags |= 1
    temp_x = (temp_x - CUTOFF) & M32

    accum = fold_mul(temp_x, sum_xz)
    idk = (sum_xz + accum) & M32

    temp_y = ((accum & 0x0001FFFF) + sect_y) & M32
    if temp_y == CUTOFF:
        flags |= 2
    temp_y = (temp_y - CUTOFF) & M32

    accum = fold_mul(temp_y, idk)

    temp_z = ((accum & 0x0001FFFF) + sect_z) & M32
    if temp_z == CUTOFF:
        flags |= 4
    temp_z = (temp_z - CUTOFF) & M32

    netpos = (temp_x + temp_y + temp_z) & M32
    return temp_x, temp_y, temp_z, netpos, flags


def cube(span=SPAN, koffset=KOFFSET, sectorsize=SECTORSIZE):
    """The acceptance sweep: k = -koffset .. span-1-koffset on each axis."""
    for kx in range(span):
        for ky in range(span):
            for kz in range(span):
                yield ((kx - koffset) * sectorsize,
                       (ky - koffset) * sectorsize,
                       (kz - koffset) * sectorsize)


def records(coords):
    return [hash_sector(*c) for c in coords]


def pack(recs):
    return b"".join(struct.pack("<5I", *r) for r in recs)


def unpack(blob):
    if len(blob) % REC:
        raise ValueError("%d bytes is not a multiple of %d" % (len(blob), REC))
    return [struct.unpack_from("<5I", blob, i * REC) for i in range(len(blob) // REC)]
