"""GUARDS: work/brtl.txt - Borland C++ 3.1's rand / srand / random, the LCG that
lays out Noctis IV's entire planetary system. 346 call sites across the three
game modules sit downstream of it, so a wrong draw is not a wrong number, it is
a different universe that still looks entirely plausible.

WHAT THE DEFAULT RUN COVERS, AND WHAT IT DOES NOT
-------------------------------------------------
The default run takes about a minute, but it is NOT a sample of the seed space.
It checks three separate things and only the third is a subset:

  1. THE FULL 65,536-SEED SWEEP, BY HASH. Every srand argument (srand truncates
     to 16 bits, so 65,536 seeds IS every state srand can name), 16 draws deep,
     value AND state folded into one 32-bit FNV-1a running hash - computed
     independently by the lino library, by the C reference and by the Python
     reference on every invocation. 1,048,576 draws. Nothing is stored: all
     three sides recompute it, so there is no golden number to go stale.
  2. THE FULL 65,536-WIDE random() DOMAIN, BY HASH. random's argument enters the
     DOS routine sign-extended from 16 bits, so its domain is exactly 65,536
     values; all of them, at 4 seeds x 2 draws, value and state, folded the same
     way. 524,288 draws, again computed three times.
     A hash says "somewhere in the sweep", not "here" - which is what (3) is for.
  3. A LOCALISING SUBSET, record by record. 39 seeds x 16 draws and 32 int16
     arguments x 4 seeds x 2 draws, every (value, state) pair compared across
     lino, C and Python individually, so a failure names the seed and the draw.
     The selection is documented at FAST_SEEDS below and is not arbitrary: the
     boundaries of the 16-bit space, six bit patterns, and 20 seeds on a
     golden-ratio stride (40503, Knuth's 16-bit multiplicative constant).

  What the default run does NOT do is compare the full sweep RECORD BY RECORD.
  `--exhaustive` does that: it builds and runs the shipped lane programmes
  work/brtlsweep.txt and work/brtlrnd.txt in a sandbox and diffs all 1,572,864
  records against Python, so a hash collision - or a lane programme that has
  drifted from the library it includes - cannot hide. Budget a few minutes.

THREE THINGS NO RECORD CAN SEE, and how they are pinned anyway
--------------------------------------------------------------
Sweeping every seed proves less than it looks like it proves. Three properties
of this library survive deliberate corruption with every record still identical,
so each has its own dedicated check:

  * SHR vs SAR. `A > 16` and `A >> 16` produce the same records, because the
    following `A & 7FFF` keeps only bits 0..14 either way. Records cannot see it.
  * THE INITIAL STATE. Every lane calls BrtlSrand before drawing, so
    `brtlseed = 1` could read 7 and no sweep would notice. Borland's library
    starts at 1 (NOCTIS.EXE, file offset 196826, reads 01 00 00 00) and code
    that draws before seeding - which exists - depends on it.
  * WHICH REGISTERS SURVIVE. The clobber contract (A destroyed, B C D E
    preserved, including across the divide) is invisible to any comparison of
    the numbers that come out.

The first and third are pinned by MACHINE CODE: this test locates the compiled
library in the executable it just built - the imul anchor 69 C0 35 4E 5A 01
occurs exactly once - and matches all four routines against a byte template with
only the workspace displacements and the call target wildcarded. That template
is the disassembly in PINNED_BODY below, and it pins the shift direction, the
divide's signedness, the divisor, both masks and the push/pop edx that keeps D
alive. The second is pinned by reading [brtlseed] before anything is called. The
clobber contract is ALSO measured at run time with sentinels, so the byte
template and the hardware have to agree with each other.

THE ARGUMENT-NARROWING CONTRACT, pinned rather than fixed
---------------------------------------------------------
DOS random() loads its argument with `movsx edx, word [bp+6]` - a WORD load.
BrtlRandom does no such narrowing, so the two agree on exactly the 65,536 int16
arguments and disagree on everything else: random(100000) is -328 in the game
and 1055 here. That matters because computed arguments reach it - 40000 already
does. This test pins BOTH halves of the contract, on hardware, for 18 large
arguments: BrtlRandom alone diverges on every one that does not fit an int16,
and BrtlToInt16 followed by BrtlRandom reproduces the DOS answer exactly. If
BrtlRandom is ever changed to narrow internally, the divergence check fails and
forces the change to be acknowledged rather than absorbed.

NOT STALE: the Python and C oracles here are transcribed in this file from the
listing below, not imported from noctis-harness, so a mistake there cannot be
laundered into agreement here. The transcription is re-checked against the
shipped binary on every run when the reference clone is present: rand()'s body
at file offset 15970, random()'s at 82487, the seed cell at 196826, and the fact
that the bytes 35 4E occur exactly once in the image.

NEGATIVE CONTROLS. Seven mutant libraries are built and run, one per line of
brtl.txt that carries a decision. Each must be caught, and by exactly the checks
named - a control that starts being caught by MORE checks fails too, because
that means a check has started responding to something it was not measuring:

  NC1 multiplier 15A4E35h -> 15A4E34h      records, both hashes, byte template
  NC2 `A > 16` -> `A >> 16` (SAR)          byte template ONLY - and this test
                                           asserts the records stay identical,
                                           which is the blind spot made visible
  NC3 `brtlseed = 1` -> `brtlseed = 7`     the initial-state slot ONLY
  NC4 `A / BRTL SCALE` -> `A >> 15`        records, rnd hash, byte template
                                           (idiv truncates toward zero, >>15
                                           floors: they differ on negative n)
  NC5 `/` -> `'/` (unsigned divide)        records, rnd hash, byte template
  NC6 srand's `A & BRTL SEEDMASK` dropped  records, byte template
  NC7 OUTMASK 7FFFh -> FFFFh               records, both hashes, byte template

Nothing under work/ is written: brtl.txt and the two lane programmes are COPIED
into tests/gen and mutated there, so a control cannot leave a wrong library
where the delivery pipeline would pick it up.

HOW IT FAILS: a failing comparison prints the first differing unit with its
block, seed, draw and argument decoded; a failing byte template prints the
offset into the library and the bytes found there.

RUN: python tests/test_brtlrand.py               (~1min, gcc optional)
     python tests/test_brtlrand.py --exhaustive  (all 1,572,864 records)
"""

import array
import os
import re
import struct
import sys

import linoharness as L


# ---------------------------------------------------------------- the algorithm
#
# From niv-plus/modules/NOCTIS.EXE, 215,744 bytes, not overlaid.
#
# rand() at file offset 15970:
#     8b 0e 5c 39   mov cx,[395C]      seed high
#     8b 1e 5a 39   mov bx,[395A]      seed low
#     ba 5a 01      mov dx,015A        multiplier high
#     b8 35 4e      mov ax,4E35        multiplier low        (35 4E: unique)
#     e8 a6 ff      call 3E19          long multiply, low 32 bits only
#     05 01 00      add ax,1
#     83 d2 00      adc dx,0
#     89 16 5c 39   mov [395C],dx
#     a3 5a 39      mov [395A],ax
#     a1 5c 39      mov ax,[395C]
#     99            cwd                (dead - ax is masked next)
#     25 ff 7f      and ax,7FFF
#     cb            retf
#
# random(n) at file offset 82487:
#     55 8b ec               push bp; mov bp,sp
#     9a 62 18 00 00         call far rand
#     66 0f bf c0            movsx eax,ax
#     66 0f bf 56 06         movsx edx,word [bp+6]   <- the argument is a WORD
#     66 0f af c2            imul eax,edx
#     66 bb 00 80 00 00      mov ebx,00008000
#     66 99                  cdq
#     66 f7 fb               idiv ebx                <- truncates toward ZERO
#     5d cb                  pop bp; retf
#
# The seed cell at file offset 196826 reads 01 00 00 00: the initial state is 1.

M32 = 0xFFFFFFFF
MULT = 0x015A4E35
SCALE = 0x8000

NOCTIS_EXE = r"C:\programmieren\noctis\niv-plus\modules\NOCTIS.EXE"

PINNED_DOS = [
    (15970, "8b 0e 5c 39 8b 1e 5a 39 ba 5a 01 b8 35 4e e8 a6 ff 05 01 00 "
            "83 d2 00 89 16 5c 39 a3 5a 39 a1 5c 39 99 25 ff 7f cb", "rand()"),
    (82487, "55 8b ec 9a 62 18 00 00 66 0f bf c0 66 0f bf 56 06 66 0f af c2 "
            "66 bb 00 80 00 00 66 99 66 f7 fb 5d cb", "random()"),
    (196826, "01 00 00 00", "the seed cell"),
]


def s32(v):
    v &= M32
    return v - 0x100000000 if v & 0x80000000 else v


def to_int16(v):
    return ((v & 0xFFFF) ^ 0x8000) - 0x8000


class Brtl(object):
    """The library, in exact Python integers, straight off the listing above."""

    def __init__(self):
        self.st = 1                                  # NOCTIS.EXE offset 196826

    def srand(self, a):
        self.st = a & 0xFFFF                         # srand zero-extends 16 bits

    def rand(self):
        self.st = (self.st * MULT + 1) & M32
        return (self.st >> 16) & 0x7FFF

    def random(self, n):
        """BrtlRandom: no argument narrowing, 32-bit wrapping multiply."""
        p = s32(self.rand() * n)
        q = abs(p) // SCALE
        return (-q if p < 0 else q) & M32

    def dos_random(self, n):
        """random() as the game calls it: the argument narrowed to int16 first."""
        return self.random(to_int16(n))


# ---------------------------------------------------------------- the fast subset
#
# GOLDEN is 40503, Knuth's 16-bit golden-ratio multiplicative constant: k*40503
# mod 65536 walks the space in maximally-spread steps, so 20 of them are a
# deterministic spread rather than 20 numbers someone liked the look of.
GOLDEN = 40503

FAST_SEEDS = sorted(set(
    [0, 1, 2, 3, 32766, 32767, 32768, 32769, 65532, 65533, 65534, 65535] +
    [0x00FF, 0xFF00, 0x0F0F, 0xF0F0, 0x5555, 0xAAAA, 0x8000, 0x0001] +
    [(k * GOLDEN) & 0xFFFF for k in range(1, 21)] +
    [12345]))
N_FAST_SEEDS = 39

# The same idea for random's argument, as the UNSIGNED k the programme narrows
# with BrtlToInt16 - so 32768..65535 are the negative half, which is where a
# floor-instead-of-truncate error lives.
FAST_KS = sorted(set(
    [0, 1, 2, 3, 4, 5, 10, 100, 1000] +
    [32766, 32767, 32768, 32769] +
    [65533, 65534, 65535] +
    [0x00FF, 0xFF00, 0x5555, 0xAAAA] +
    [(k * GOLDEN) & 0xFFFF for k in range(1, 13)]))
N_FAST_KS = 32

NDRAWS = 16
RSEEDS = [0, 1, 12345, 65535]      # the four seeds the wave's lane 3 uses
RDRAWS = 2

# srand arguments that do not fit 16 bits: every one must alias to arg & FFFF.
SRAND_ARGS = [0, 1, 12345, 65535, 65536, 65537, 74565, 100000, 1000000,
              2147483647]

# Magnitudes for the narrowing contract; each is used as +m and -m. 32768 and
# 40000 are the ones that matter: both are values a plausible computed argument
# reaches and neither fits an int16. (-32768 does fit, and is the one member of
# this table that must NOT diverge.)
BIG_MAGS = [32768, 32769, 40000, 65536, 65537, 65538, 100000, 1000000,
            2000000000]

# BrtlToInt16 inputs, again as +m and -m.
TOI_MAGS = [0, 1, 32767, 32768, 32769, 65535, 65536, 65537, 0x1FFFF, 100000,
            2147483647]

HASHSEED = 0x0DEFACED
FNVPRIME = 16777619
MAGIC = 0x42525432
LAYOUT = 1
SENTINEL = 0x0DEFACED

SENT_B, SENT_C, SENT_D, SENT_E = 0x11111111, 0x22222222, 0x33333333, 0x44444444
CLOBBER_SEED, CLOBBER_N = 12345, 100

HDR = 24


def layout():
    """Unit offsets of every block. All three implementations use these."""
    a = HDR
    b = a + len(FAST_SEEDS) * NDRAWS * 2
    c = b + len(SRAND_ARGS)
    d = c + len(FAST_KS) * len(RSEEDS) * RDRAWS * 2
    e = d + len(BIG_MAGS) * 2 * 2
    last = e + len(TOI_MAGS) * 2
    return {"A": a, "B": b, "C": c, "D": d, "E": e, "last": last,
            "total": last + 1}


OFF = layout()


def fold(h, v):
    return ((h ^ (v & M32)) * FNVPRIME) & M32


def sweep_hash():
    """FNV-1a over all 65,536 seeds x 16 draws, value and state."""
    g, h = Brtl(), HASHSEED
    for seed in range(65536):
        g.srand(seed)
        for _ in range(NDRAWS):
            h = fold(h, g.rand())
            h = fold(h, g.st)
    return h


def rnd_hash():
    """FNV-1a over all 65,536 int16 arguments x 4 seeds x 2 draws."""
    g, h = Brtl(), HASHSEED
    for k in range(65536):
        n = to_int16(k)
        for seed in RSEEDS:
            g.srand(seed)
            for _ in range(RDRAWS):
                h = fold(h, g.random(n))
                h = fold(h, g.st)
    return h


def expected_units():
    """The whole result buffer, as the Python reference says it should be."""
    u = [0] * OFF["total"]
    g = Brtl()

    u[0] = MAGIC
    u[1] = LAYOUT
    u[2] = len(FAST_SEEDS)
    u[3] = NDRAWS
    u[4] = len(FAST_KS)
    u[5] = len(RSEEDS)
    u[6] = RDRAWS
    u[7] = len(BIG_MAGS)
    u[8] = len(TOI_MAGS)
    u[9] = len(SRAND_ARGS)
    u[10] = g.st & M32                       # read before anything is called
    u[11] = sweep_hash()
    u[12] = rnd_hash()
    u[13], u[14], u[15], u[16] = SENT_B, SENT_C, SENT_D, SENT_E
    u[17], u[18], u[19], u[20] = SENT_B, SENT_C, SENT_D, SENT_E
    g.srand(CLOBBER_SEED)
    u[21] = g.rand()
    g.srand(CLOBBER_SEED)
    u[22] = g.random(CLOBBER_N)
    u[23] = SENTINEL

    p = OFF["A"]
    for seed in FAST_SEEDS:
        g.srand(seed)
        for _ in range(NDRAWS):
            u[p] = g.rand(); p += 1
            u[p] = g.st; p += 1

    p = OFF["B"]
    for a in SRAND_ARGS:
        g.srand(a)
        u[p] = g.st; p += 1

    p = OFF["C"]
    for k in FAST_KS:
        n = to_int16(k)
        for seed in RSEEDS:
            g.srand(seed)
            for _ in range(RDRAWS):
                u[p] = g.random(n); p += 1
                u[p] = g.st; p += 1

    p = OFF["D"]
    for sign in (1, -1):
        for m in BIG_MAGS:
            n = sign * m
            g.srand(1)
            u[p] = g.random(n) & M32; p += 1
            g.srand(1)
            u[p] = g.random(to_int16(n)) & M32; p += 1

    p = OFF["E"]
    for sign in (1, -1):
        for m in TOI_MAGS:
            u[p] = to_int16(sign * m) & M32; p += 1

    u[OFF["last"]] = SENTINEL
    return u


# ---------------------------------------------------------------- the lino side

def vec(name, values, per_line=8):
    """A lino vector declaration, wrapped so no line runs away."""
    head = " vector %s = " % name
    pad = " " * len(head)
    out = []
    for i in range(0, len(values), per_line):
        chunk = " ".join("%d;" % v for v in values[i:i + per_line])
        out.append((head if i == 0 else pad) + chunk)
    return "\n".join(out) + "\n"


LINO = """      ( Generated by tests/test_brtlrand.py - do not edit, do not ship.

        Drives work/brtl.txt over a documented fast subset, plus a running
        hash over the FULL 65536-seed sweep and the FULL 65536-wide random
        domain, plus the three probes no sweep can see: the initial state,
        the clobber sentinels and the int16 narrowing contract.          )

"libraries"

\tbrtl;

"directors"

\tprogram name = { %(prog)s };
\tunit = 32;

"constants"

\tFNVPRIME = %(fnv)d;
\tHASHSEED = %(hashseed)s;
\tMAGIC\t = %(magic)s;
\tSENTINEL = %(sentinel)s;
\tNSEEDS\t = %(nseeds)d;
\tNDRAWS\t = %(ndraws)d;
\tNKS\t = %(nks)d;
\tNBIG\t = %(nbig)d;
\tNTOI\t = %(ntoi)d;
\tNSRAND\t = %(nsrand)d;
\tTOTAL\t = %(total)d;

"variables"

\tsi\t= 0;
\tsj\t= 0;
\tsk\t= 0;
\toptr\t= 0;
\thsh\t= 0;
\tnval\t= 0;
\tt\t= 0;

%(vectors)s
\tresult file name = { %(outfile)s };

"workspace"

\tresults = TOTAL;

"programme"

\t( ---- slot 10: the library's state before ANY call is made ---- )

\tA = [brtlseed];
\tB = results; B + 10; [B] = A;

\t( ---- slot 11: FNV-1a over all 65536 seeds x 16 draws ---- )

\t[hsh] = HASHSEED;
\t[si] = 0;

    "hash seed loop"

\tA = [si];
\t=> BrtlSrand;
\t[sj] = 0;

    "hash draw loop"

\t=> BrtlRand;
\tB = [hsh];\tB # A;\tB * FNVPRIME;
\tA = [brtlseed];\tB # A;\tB * FNVPRIME;
\t[hsh] = B;
\t[sj] +;
      ? [sj] < NDRAWS -> hash draw loop;
\t[si] +;
      ? [si] < 65536 -> hash seed loop;

\tA = [hsh];
\tB = results; B + 11; [B] = A;

\t( ---- slot 12: FNV-1a over all 65536 int16 arguments x 4 seeds x 2 ---- )

\t[hsh] = HASHSEED;
\t[sk] = 0;

    "rhash k loop"

\tA = [sk];
\t=> BrtlToInt16;
\t[nval] = A;
\t[si] = 0;

    "rhash seed loop"

\tB = vector seedtab4; B + [si];
\tA = [B];
\t=> BrtlSrand;
\t[sj] = 0;

    "rhash draw loop"

\tA = [nval];
\t=> BrtlRandom;
\tB = [hsh];\tB # A;\tB * FNVPRIME;
\tA = [brtlseed];\tB # A;\tB * FNVPRIME;
\t[hsh] = B;
\t[sj] +;
      ? [sj] < 2 -> rhash draw loop;
\t[si] +;
      ? [si] < 4 -> rhash seed loop;
\t[sk] +;
      ? [sk] < 65536 -> rhash k loop;

\tA = [hsh];
\tB = results; B + 12; [B] = A;

\t( ---- slots 13..16 and 21: what survives BrtlRand ---- )

\tA = %(cseed)d; => BrtlSrand;
\tB = %(sb)s;
\tC = %(sc)s;
\tD = %(sd)s;
\tE = %(se)s;
\t=> BrtlRand;
\t[t] = A;
\tA = results; A + 13; [A] = B;
\tA = results; A + 14; [A] = C;
\tA = results; A + 15; [A] = D;
\tA = results; A + 16; [A] = E;
\tA = results; A + 21; C = [t]; [A] = C;

\t( ---- slots 17..20 and 22: what survives BrtlRandom, divide included ---- )

\tA = %(cseed)d; => BrtlSrand;
\tB = %(sb)s;
\tC = %(sc)s;
\tD = %(sd)s;
\tE = %(se)s;
\tA = %(cn)d; => BrtlRandom;
\t[t] = A;
\tA = results; A + 17; [A] = B;
\tA = results; A + 18; [A] = C;
\tA = results; A + 19; [A] = D;
\tA = results; A + 20; [A] = E;
\tA = results; A + 22; C = [t]; [A] = C;

\t( ---- the header, and its sentinel ---- )

\t[results]\t = MAGIC;
\t[results plus 1] = %(layout)d;
\t[results plus 2] = NSEEDS;
\t[results plus 3] = NDRAWS;
\t[results plus 4] = NKS;
\t[results plus 5] = 4;
\t[results plus 6] = 2;
\t[results plus 7] = NBIG;
\t[results plus 8] = NTOI;
\t[results plus 9] = NSRAND;
\t[results plus 23] = SENTINEL;

\t( ---- block A: the documented seed subset, 16 draws each ---- )

\tA = results; A + %(offa)d; [optr] = A;
\t[si] = 0;

    "sub seed loop"

\tB = vector seedtab; B + [si];
\tA = [B];
\t=> BrtlSrand;
\t[sj] = 0;

    "sub draw loop"

\t=> BrtlRand;
\tB = [optr]; [B] = A; B +;
\tA = [brtlseed]; [B] = A; B +;
\t[optr] = B;
\t[sj] +;
      ? [sj] < NDRAWS -> sub draw loop;
\t[si] +;
      ? [si] < NSEEDS -> sub seed loop;

\t( ---- block B: srand truncates its argument to 16 bits ---- )

\tA = results; A + %(offb)d; [optr] = A;
\t[si] = 0;

    "srand alias loop"

\tB = vector srandtab; B + [si];
\tA = [B];
\t=> BrtlSrand;
\tA = [brtlseed];
\tB = [optr]; [B] = A; B +; [optr] = B;
\t[si] +;
      ? [si] < NSRAND -> srand alias loop;

\t( ---- block C: random(n) over the documented int16 subset ---- )

\tA = results; A + %(offc)d; [optr] = A;
\t[sk] = 0;

    "nsub k loop"

\tB = vector ntab; B + [sk];
\tA = [B];
\t=> BrtlToInt16;
\t[nval] = A;
\t[si] = 0;

    "nsub seed loop"

\tB = vector seedtab4; B + [si];
\tA = [B];
\t=> BrtlSrand;
\t[sj] = 0;

    "nsub draw loop"

\tA = [nval];
\t=> BrtlRandom;
\tB = [optr]; [B] = A; B +;
\tA = [brtlseed]; [B] = A; B +;
\t[optr] = B;
\t[sj] +;
      ? [sj] < 2 -> nsub draw loop;
\t[si] +;
      ? [si] < 4 -> nsub seed loop;
\t[sk] +;
      ? [sk] < NKS -> nsub k loop;

\t( ---- block D: arguments that do NOT fit an int16, raw and narrowed ---- )

\tA = results; A + %(offd)d; [optr] = A;
\t[si] = 0;

    "big pos loop"

\tB = vector bigtab; B + [si];
\tA = [B];
\t[nval] = A;
\tA = 1; => BrtlSrand;
\tA = [nval]; => BrtlRandom;
\tB = [optr]; [B] = A; B +; [optr] = B;
\tA = 1; => BrtlSrand;
\tA = [nval]; => BrtlToInt16; => BrtlRandom;
\tB = [optr]; [B] = A; B +; [optr] = B;
\t[si] +;
      ? [si] < NBIG -> big pos loop;

\t[si] = 0;

    "big neg loop"

\tB = vector bigtab; B + [si];
\tA = [B];
\tB = 0; B - A; A = B;
\t[nval] = A;
\tA = 1; => BrtlSrand;
\tA = [nval]; => BrtlRandom;
\tB = [optr]; [B] = A; B +; [optr] = B;
\tA = 1; => BrtlSrand;
\tA = [nval]; => BrtlToInt16; => BrtlRandom;
\tB = [optr]; [B] = A; B +; [optr] = B;
\t[si] +;
      ? [si] < NBIG -> big neg loop;

\t( ---- block E: the int16 narrowing helper itself ---- )

\tA = results; A + %(offe)d; [optr] = A;
\t[si] = 0;

    "toi pos loop"

\tB = vector toitab; B + [si];
\tA = [B];
\t=> BrtlToInt16;
\tB = [optr]; [B] = A; B +; [optr] = B;
\t[si] +;
      ? [si] < NTOI -> toi pos loop;

\t[si] = 0;

    "toi neg loop"

\tB = vector toitab; B + [si];
\tA = [B];
\tB = 0; B - A; A = B;
\t=> BrtlToInt16;
\tB = [optr]; [B] = A; B +; [optr] = B;
\t[si] +;
      ? [si] < NTOI -> toi neg loop;

\t( ---- completion sentinel, then out ---- )

\tA = results; A + %(offlast)d; B = SENTINEL; [A] = B;

\t[File Name]\t= result file name;
\t[File Position] = 0;
\t[File Command]\t= WRITE;
\t[Block Pointer] = results;
\t[Block Size]\t= TOTAL;
\t[Block Size]\t* BYTES PER UNIT;
\tisocall;

\t[File Name]\t= result file name;
\t[File Position] = 0;
\t[File Command]\t= SET SIZE;
\t[File Size]\t= TOTAL;
\t[File Size]\t* BYTES PER UNIT;
\tisocall;

\tend;
"""


def emit_lino(path, prog, outfile):
    vectors = (vec("seedtab", FAST_SEEDS) + "\n" +
               vec("seedtab4", RSEEDS) + "\n" +
               vec("ntab", FAST_KS) + "\n" +
               vec("srandtab", SRAND_ARGS) + "\n" +
               vec("bigtab", BIG_MAGS) + "\n" +
               vec("toitab", TOI_MAGS))
    body = LINO % {
        "prog": prog, "outfile": outfile, "vectors": vectors,
        "fnv": FNVPRIME, "hashseed": "0DEFACEDh", "magic": "42525432h",
        "sentinel": "0DEFACEDh", "layout": LAYOUT,
        "nseeds": len(FAST_SEEDS), "ndraws": NDRAWS, "nks": len(FAST_KS),
        "nbig": len(BIG_MAGS), "ntoi": len(TOI_MAGS),
        "nsrand": len(SRAND_ARGS), "total": OFF["total"],
        "cseed": CLOBBER_SEED, "cn": CLOBBER_N,
        "sb": "11111111h", "sc": "22222222h", "sd": "33333333h",
        "se": "44444444h",
        "offa": OFF["A"], "offb": OFF["B"], "offc": OFF["C"],
        "offd": OFF["D"], "offe": OFF["E"], "offlast": OFF["last"],
    }
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)


# ---------------------------------------------------------------- the C side

C_SRC = r"""/* Generated by tests/test_brtlrand.py - the third implementation.
   Written from the NOCTIS.EXE listing in that file, not from the lino source. */
#include <stdio.h>
#include <string.h>

typedef unsigned int u32;
typedef int i32;

static u32 st = 1;                        /* NOCTIS.EXE file offset 196826 */

static void bsrand(u32 a) { st = a & 0xFFFFu; }
static u32  brand(void)   { st = st * 0x015A4E35u + 1u; return (st >> 16) & 0x7FFFu; }
static i32  toi16(u32 x)  { return (i32)(short)(unsigned short)(x & 0xFFFFu); }

static i32 brandom(i32 n)
{
    u32 r = brand();
    i32 p = (i32)(r * (u32)n);      /* 32-bit wrapping multiply, as lino does */
    return p / 0x8000;              /* C division truncates toward zero */
}

#define FNVPRIME 16777619u
#define HASHSEED 0x0DEFACEDu
static u32 fold(u32 h, u32 v) { return (h ^ v) * FNVPRIME; }

static const u32 seeds[]  = { %(seeds)s };
static const u32 ks[]     = { %(ks)s };
static const u32 rseeds[] = { %(rseeds)s };
static const u32 sargs[]  = { %(sargs)s };
static const u32 bigs[]   = { %(bigs)s };
static const u32 tois[]   = { %(tois)s };
#define NSEEDS  (sizeof seeds  / sizeof seeds[0])
#define NKS     (sizeof ks     / sizeof ks[0])
#define NRSEEDS (sizeof rseeds / sizeof rseeds[0])
#define NSARGS  (sizeof sargs  / sizeof sargs[0])
#define NBIG    (sizeof bigs   / sizeof bigs[0])
#define NTOI    (sizeof tois   / sizeof tois[0])

#define NDRAWS %(ndraws)d
#define RDRAWS %(rdraws)d
#define TOTAL  %(total)d

int main(void)
{
    static u32 u[TOTAL];
    u32 h;
    size_t i, j, k;
    long q;
    int p;
    FILE *f;

    memset(u, 0, sizeof u);

    u[0]  = 0x42525432u;
    u[1]  = %(layout)d;
    u[2]  = (u32)NSEEDS;
    u[3]  = NDRAWS;
    u[4]  = (u32)NKS;
    u[5]  = (u32)NRSEEDS;
    u[6]  = RDRAWS;
    u[7]  = (u32)NBIG;
    u[8]  = (u32)NTOI;
    u[9]  = (u32)NSARGS;
    u[10] = st;                            /* before anything is called */

    h = HASHSEED;
    for (q = 0; q < 65536; q++) {
        bsrand((u32)q);
        for (j = 0; j < NDRAWS; j++) { h = fold(h, brand()); h = fold(h, st); }
    }
    u[11] = h;

    h = HASHSEED;
    for (q = 0; q < 65536; q++) {
        i32 n = toi16((u32)q);
        for (i = 0; i < NRSEEDS; i++) {
            bsrand(rseeds[i]);
            for (j = 0; j < RDRAWS; j++) {
                h = fold(h, (u32)brandom(n));
                h = fold(h, st);
            }
        }
    }
    u[12] = h;

    u[13] = u[17] = 0x11111111u;
    u[14] = u[18] = 0x22222222u;
    u[15] = u[19] = 0x33333333u;
    u[16] = u[20] = 0x44444444u;
    bsrand(%(cseed)d); u[21] = brand();
    bsrand(%(cseed)d); u[22] = (u32)brandom(%(cn)d);
    u[23] = 0x0DEFACEDu;

    p = %(offa)d;
    for (i = 0; i < NSEEDS; i++) {
        bsrand(seeds[i]);
        for (j = 0; j < NDRAWS; j++) { u[p++] = brand(); u[p++] = st; }
    }

    p = %(offb)d;
    for (i = 0; i < NSARGS; i++) { bsrand(sargs[i]); u[p++] = st; }

    p = %(offc)d;
    for (k = 0; k < NKS; k++) {
        i32 n = toi16(ks[k]);
        for (i = 0; i < NRSEEDS; i++) {
            bsrand(rseeds[i]);
            for (j = 0; j < RDRAWS; j++) {
                u[p++] = (u32)brandom(n);
                u[p++] = st;
            }
        }
    }

    p = %(offd)d;
    for (k = 0; k < 2; k++)
        for (i = 0; i < NBIG; i++) {
            i32 n = (k == 0) ? (i32)bigs[i] : -(i32)bigs[i];
            bsrand(1); u[p++] = (u32)brandom(n);
            bsrand(1); u[p++] = (u32)brandom(toi16((u32)n));
        }

    p = %(offe)d;
    for (k = 0; k < 2; k++)
        for (i = 0; i < NTOI; i++) {
            i32 v = (k == 0) ? (i32)tois[i] : -(i32)tois[i];
            u[p++] = (u32)toi16((u32)v);
        }

    u[%(offlast)d] = 0x0DEFACEDu;

    f = fopen("%(outfile)s", "wb");
    if (!f) return 1;
    fwrite(u, 4, TOTAL, f);
    fclose(f);
    printf("%%u units\n", (unsigned)TOTAL);
    return 0;
}
"""


def emit_c(path, outfile):
    def lst(v):
        return ", ".join("%uu" % x for x in v)
    body = C_SRC % {
        "seeds": lst(FAST_SEEDS), "ks": lst(FAST_KS), "rseeds": lst(RSEEDS),
        "sargs": lst(SRAND_ARGS), "bigs": lst(BIG_MAGS), "tois": lst(TOI_MAGS),
        "total": OFF["total"], "layout": LAYOUT, "ndraws": NDRAWS,
        "rdraws": RDRAWS, "cseed": CLOBBER_SEED, "cn": CLOBBER_N,
        "offa": OFF["A"], "offb": OFF["B"], "offc": OFF["C"], "offd": OFF["D"],
        "offe": OFF["E"], "offlast": OFF["last"], "outfile": outfile,
    }
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)


# ------------------------------------------------------- the compiled library
#
# The library compiles to four contiguous routines. Every byte below is a
# decision; W is a wildcard, and the only wildcards are workspace displacements
# (which depend on the including programme's variable layout) and the relative
# call target.
W = None
PINNED_BODY = [
    # BrtlSrand
    0x25, 0xFF, 0xFF, 0x00, 0x00,                    # and  eax, 0000FFFF
    0x89, 0x87, W, W, W, W,                          # mov  [edi+brtlseed], eax
    0xC3,                                            # ret
    # BrtlRand
    0x8B, 0x87, W, W, W, W,                          # mov  eax, [edi+brtlseed]
    0x69, 0xC0, 0x35, 0x4E, 0x5A, 0x01,              # imul eax, eax, 015A4E35
    0x05, 0x01, 0x00, 0x00, 0x00,                    # add  eax, 1
    0x89, 0x87, W, W, W, W,                          # mov  [edi+brtlseed], eax
    0xC1, 0xE8, 0x10,                                # shr  eax, 16   (NOT sar)
    0x25, 0xFF, 0x7F, 0x00, 0x00,                    # and  eax, 00007FFF
    0xC3,                                            # ret
    # BrtlRandom
    0x89, 0x87, W, W, W, W,                          # mov  [edi+brtln], eax
    0xE8, W, W, W, W,                                # call BrtlRand
    0x0F, 0xAF, 0x87, W, W, W, W,                    # imul eax, [edi+brtln]
    0x52,                                            # push edx    (D survives)
    0xBD, 0x00, 0x80, 0x00, 0x00,                    # mov  ebp, 00008000
    0x99,                                            # cdq
    0xF7, 0xFD,                                      # idiv ebp    (NOT div)
    0x5A,                                            # pop  edx
    0xC3,                                            # ret
    # BrtlToInt16
    0x25, 0xFF, 0xFF, 0x00, 0x00,                    # and  eax, 0000FFFF
    0x35, 0x00, 0x80, 0x00, 0x00,                    # xor  eax, 00008000
    0x2D, 0x00, 0x80, 0x00, 0x00,                    # sub  eax, 00008000
    0xC3,                                            # ret
]
ANCHOR = bytes([0x69, 0xC0, 0x35, 0x4E, 0x5A, 0x01])
ANCHOR_AT = 18                       # its offset within PINNED_BODY


def library_bytes(exe_path):
    """(hits, block) - the compiled library, located by its unique imul."""
    with open(exe_path, "rb") as fh:
        blob = fh.read()
    hits = [m.start() for m in re.finditer(re.escape(ANCHOR), blob)]
    if len(hits) != 1 or hits[0] < ANCHOR_AT:
        return hits, None
    start = hits[0] - ANCHOR_AT
    return hits, blob[start:start + len(PINNED_BODY)]


def template_diff(block):
    """Byte indices where the compiled library departs from PINNED_BODY."""
    if block is None or len(block) != len(PINNED_BODY):
        return None
    return [i for i, want in enumerate(PINNED_BODY)
            if want is not None and block[i] != want]


# ---------------------------------------------------------------- reporting

HDR_NAMES = {
    0: "MAGIC", 1: "layout version", 2: "nseeds", 3: "ndraws", 4: "nks",
    5: "nrseeds", 6: "nrdraws", 7: "nbig", 8: "ntoi", 9: "nsrand",
    10: "initial [brtlseed]", 11: "full sweep hash",
    12: "full random-domain hash", 13: "B after BrtlRand",
    14: "C after BrtlRand", 15: "D after BrtlRand", 16: "E after BrtlRand",
    17: "B after BrtlRandom", 18: "C after BrtlRandom",
    19: "D after BrtlRandom", 20: "E after BrtlRandom", 21: "rand() witness",
    22: "random() witness", 23: "header sentinel",
}


def decode_unit(i):
    """Say what unit i of the buffer is, so a diff names something."""
    if i < HDR:
        return "header slot %d (%s)" % (i, HDR_NAMES.get(i, "?"))
    if i < OFF["B"]:
        r = (i - OFF["A"]) // 2
        return "block A seed %d draw %d %s" % (
            FAST_SEEDS[r // NDRAWS], r % NDRAWS,
            "value" if (i - OFF["A"]) % 2 == 0 else "state")
    if i < OFF["C"]:
        return "block B srand(%d)" % SRAND_ARGS[i - OFF["B"]]
    if i < OFF["D"]:
        r = (i - OFF["C"]) // 2
        return "block C n=%d seed=%d draw %d %s" % (
            to_int16(FAST_KS[r // (RDRAWS * len(RSEEDS))]),
            RSEEDS[(r // RDRAWS) % len(RSEEDS)], r % RDRAWS,
            "value" if (i - OFF["C"]) % 2 == 0 else "state")
    if i < OFF["E"]:
        r = (i - OFF["D"]) // 2
        sign = -1 if r >= len(BIG_MAGS) else 1
        return "block D n=%d %s" % (
            sign * BIG_MAGS[r % len(BIG_MAGS)],
            "raw" if (i - OFF["D"]) % 2 == 0 else "narrowed")
    if i < OFF["last"]:
        r = i - OFF["E"]
        sign = -1 if r >= len(TOI_MAGS) else 1
        return "block E BrtlToInt16(%d)" % (sign * TOI_MAGS[r % len(TOI_MAGS)])
    return "trailing sentinel"


def first_diff(a, b):
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            return i
    return None if len(a) == len(b) else min(len(a), len(b))


def units_of(blob):
    return list(struct.unpack("<%dI" % (len(blob) // 4), blob))


# ---------------------------------------------------------------- build helpers

def install_library(gen, text=None):
    """Put brtl.txt into the sandbox: the real one, or a mutant of it."""
    with open(os.path.join(L.WORK, "brtl.txt"), encoding="latin-1") as fh:
        src = fh.read()
    with open(os.path.join(gen, "brtl.txt"), "w", encoding="utf-8") as fh:
        fh.write(src if text is None else text)
    return src


def build_driver(gen, prog="tbrtl"):
    src = os.path.join(gen, prog + ".txt")
    emit_lino(src, prog, prog + ".bin")
    blob, exe, note = L.build_and_run(src, os.path.join(gen, prog + ".bin"),
                                      L.STOCK_COMPILER, L.STOCK_CPU)
    return blob, exe, note


def valid(blob):
    """A buffer of the right size with magic and both sentinels in place."""
    if blob is None or len(blob) != OFF["total"] * 4:
        return False, "size %s want %d" % (
            "None" if blob is None else len(blob), OFF["total"] * 4)
    u = units_of(blob)
    if u[0] != MAGIC:
        return False, "magic %08X" % u[0]
    if u[23] != SENTINEL or u[OFF["last"]] != SENTINEL:
        return False, "sentinels %08X %08X" % (u[23], u[OFF["last"]])
    return True, ""


# ---------------------------------------------------------------- exhaustive

LANES = [
    ("brtlsweep.txt", "brtlsweep", "brtl-sweep.bin", "tbsweep", "tb-sweep.bin",
     65536 * 16, "all 65536 seeds x 16 draws"),
    ("brtlrnd.txt", "brtlrnd", "brtl-rnd.bin", "tbrnd", "tb-rnd.bin",
     65536 * 8, "all 65536 int16 arguments x 4 seeds x 2 draws"),
]


def lane_expected(which):
    """A lane's payload as a little-endian byte string."""
    g = Brtl()
    out = array.array("I")
    if which == 0:
        for seed in range(65536):
            g.srand(seed)
            for _ in range(NDRAWS):
                out.append(g.rand())
                out.append(g.st)
    else:
        for k in range(65536):
            n = to_int16(k)
            for seed in RSEEDS:
                g.srand(seed)
                for _ in range(RDRAWS):
                    out.append(g.random(n))
                    out.append(g.st)
    if sys.byteorder != "little":
        out.byteswap()
    return out.tobytes()


def run_exhaustive(c, gen):
    c.note("exhaustive: building and running the shipped lane programmes in "
           "the sandbox, then diffing every record")
    for idx, lane in enumerate(LANES):
        fname, prog, outname, sprog, soutname, nrec, blurb = lane
        with open(os.path.join(L.WORK, fname), encoding="latin-1") as fh:
            text = fh.read()
        n1 = text.count("{ %s }" % prog)
        n2 = text.count("{ %s }" % outname)
        if not c.ok(n1 == 1 and n2 == 1,
                    "%s: the sandbox copy can rewrite both file-name literals"
                    % fname, "prog %d out %d" % (n1, n2)):
            continue
        text = text.replace("{ %s }" % prog, "{ %s }" % sprog)
        text = text.replace("{ %s }" % outname, "{ %s }" % soutname)
        src = os.path.join(gen, sprog + ".txt")
        with open(src, "w", encoding="utf-8") as fh:
            fh.write(text)
        blob, _exe, note = L.build_and_run(src, os.path.join(gen, soutname),
                                           L.STOCK_COMPILER, L.STOCK_CPU)
        if not c.ok(blob is not None, "%s builds and runs" % fname, note):
            continue
        hdr = struct.unpack("<8I", blob[:32]) if len(blob) >= 32 else ()
        if not c.ok(len(blob) == 32 + nrec * 8 and hdr and
                    hdr[0] == 0x42525431 and hdr[4] == nrec and
                    hdr[7] == SENTINEL,
                    "%s: header, length and completion sentinel" % fname,
                    "%d bytes, header %r" % (len(blob), hdr)):
            continue
        want = lane_expected(idx)
        got = blob[32:]
        if got == want:
            c.ok(True, "%s: all %d records (%s) are bit-exact with the Python "
                       "reference" % (fname, nrec, blurb))
        else:
            gw = struct.unpack("<%dI" % (len(got) // 4), got)
            ww = struct.unpack("<%dI" % (len(want) // 4), want)
            i = first_diff(gw, ww)
            bad = sum(1 for a, b in zip(gw, ww) if a != b)
            c.ok(False, "%s: all %d records (%s) are bit-exact with the Python "
                        "reference" % (fname, nrec, blurb),
                 "%d units differ, first at unit %d: %d vs %d"
                 % (bad, i, gw[i], ww[i]))


# ---------------------------------------------------------------- the controls

CONTROLS = [
    ("NC1 multiplier 15A4E35h -> 15A4E34h",
     "BRTL MULTIPLIER = 15A4E35h;", "BRTL MULTIPLIER = 15A4E34h;",
     ("records", "sweep hash", "rnd hash", "bytes")),
    ("NC2 `A > 16` -> `A >> 16` (arithmetic shift)",
     "\tA > 16;\n", "\tA >> 16;\n", ("bytes",)),
    ("NC3 initial state 1 -> 7",
     "brtlseed = 1;", "brtlseed = 7;", ("initial",)),
    ("NC4 `A / BRTL SCALE` -> `A >> 15` (shift instead of divide)",
     "\tA / BRTL SCALE;\n", "\tA >> 15;\n", ("records", "rnd hash", "bytes")),
    ("NC5 `/` -> `'/` (unsigned divide)",
     "\tA / BRTL SCALE;\n", "\tA '/ BRTL SCALE;\n",
     ("records", "rnd hash", "bytes")),
    ("NC6 srand's 16-bit mask dropped",
     "\"BrtlSrand\"\n\n\tA & BRTL SEEDMASK;\n", "\"BrtlSrand\"\n\n",
     ("records", "bytes")),
    ("NC7 OUTMASK 7FFFh -> FFFFh",
     "BRTL OUTMASK\t= 7FFFh;", "BRTL OUTMASK\t= FFFFh;",
     ("records", "sweep hash", "rnd hash", "bytes")),
]


def caught_by(good, bad, good_block, bad_block):
    """Which of this test's checks notice the difference, and where."""
    seen = set()
    if bad[10] != good[10]:
        seen.add("initial")
    if bad[11] != good[11]:
        seen.add("sweep hash")
    if bad[12] != good[12]:
        seen.add("rnd hash")
    rest = [i for i in range(min(len(good), len(bad)))
            if i not in (10, 11, 12) and good[i] != bad[i]]
    if rest:
        seen.add("records")
    if bad_block is None or (good_block is not None and good_block != bad_block):
        seen.add("bytes")
    return seen, rest


# ---------------------------------------------------------------- main

def main():
    exhaustive = "--exhaustive" in sys.argv
    c = L.Check("test_brtlrand - Borland's rand/srand/random, the LCG under "
                "Noctis IV's whole galaxy")
    gen = L.gen_dir()

    # ------------------------------------------- 0. the oracles are not stale
    if os.path.exists(NOCTIS_EXE):
        with open(NOCTIS_EXE, "rb") as fh:
            image = fh.read()
        c.eq(len(image), 215744,
             "NOCTIS.EXE is the 215,744-byte non-overlaid build the listings "
             "in this file were read from")
        for off, hexs, what in PINNED_DOS:
            want = bytes(int(x, 16) for x in hexs.split())
            got = image[off:off + len(want)]
            c.ok(got == want,
                 "%s is still at file offset %d, byte for byte" % (what, off),
                 "got %s" % " ".join("%02x" % b for b in got))
        c.eq(len(re.findall(re.escape(b"\x35\x4e"), image)), 1,
             "the multiplier's low half 35 4E occurs exactly once in the "
             "image, so rand()'s location is unique rather than guessed")
        c.eq(len(re.findall(re.escape(b"\x66\x0f\xbf\x56\x06"), image)), 1,
             "and `movsx edx, word [bp+6]` - random()'s WORD argument load, "
             "which is the whole narrowing question - occurs exactly once")
    else:
        c.note("niv-plus not present - the transcription cannot be re-checked "
               "against the shipped binary this run")

    # ------------------------------------------- 1. build and run the library
    install_library(gen)
    blob, exe, note = build_driver(gen)
    if not c.ok(blob is not None,
                "the brtl driver builds and runs on the STOCK compiler and "
                "STOCK i386 pack - this wave needs no extended toolchain",
                note):
        return c.done()
    ok, why = valid(blob)
    if not c.ok(ok, "it wrote a complete %d-unit buffer: magic, both "
                    "sentinels, exact length" % OFF["total"], why):
        return c.done()
    lino = units_of(blob)

    hits, good_block = library_bytes(exe)
    c.eq(len(hits), 1,
         "the imul anchor 69 C0 35 4E 5A 01 occurs exactly once in the "
         "executable, so the block examined below is the library itself and "
         "not something that resembles it")

    # ------------------------------------------- 2. three implementations
    want = expected_units()
    sets = {"lino": lino, "python": want}

    cpath = os.path.join(gen, "tbrtlc.c")
    emit_c(cpath, "tbrtlc.bin")
    cblob, cnote = L.gcc_build_and_run(cpath, "tbrtlc.exe", "tbrtlc.bin", gen)
    if cblob is not None:
        sets["c"] = units_of(cblob)
    else:
        c.note("C reference unavailable (%s) - two implementations instead of "
               "three" % cnote.split("\n")[0])

    L.compare_records(c, sets, "implementations")
    i = first_diff(lino, want)
    if i is not None:
        c.note("first difference is %s: lino %d, python %d"
               % (decode_unit(i), lino[i], want[i]))

    # ------------------------------------------- 3. the coverage claims
    c.eq(lino[11], sweep_hash(),
         "FULL SWEEP: the same FNV-1a hash over all 65,536 srand seeds x 16 "
         "draws, value and state - 1,048,576 draws, recomputed on both sides "
         "this run, nothing stored")
    c.eq(lino[12], rnd_hash(),
         "FULL random() DOMAIN: the same hash over all 65,536 int16 arguments "
         "x 4 seeds x 2 draws - 524,288 draws")
    if "c" in sets:
        c.ok(sets["c"][11] == lino[11] and sets["c"][12] == lino[12],
             "...and the C reference, written from the DOS listing "
             "independently, computes both of those hashes too")
    c.eq(len(FAST_SEEDS), N_FAST_SEEDS,
         "the localising subset is the documented %d seeds (the 16-bit "
         "boundaries, six bit patterns, 20 on the 40503 stride, and 12345)"
         % N_FAST_SEEDS)
    c.eq(len(FAST_KS), N_FAST_KS,
         "...and the documented %d int16 arguments" % N_FAST_KS)
    nneg = sum(1 for k in FAST_KS if to_int16(k) < 0)
    c.ok(nneg >= 10,
         "...of which enough are negative to see a floor-instead-of-truncate "
         "error in the subset as well as in the hash",
         "%d of %d are negative" % (nneg, len(FAST_KS)))

    # ------------------------------------------- 4. what no record can see
    c.eq(lino[10], 1,
         "the library's state before ANY call is 1 - Borland's initial seed, "
         "read out of NOCTIS.EXE at file offset 196826. No sweep can see "
         "this: every lane srands before it draws")

    for reg, slot, sent in (("B", 13, SENT_B), ("C", 14, SENT_C),
                            ("D", 15, SENT_D), ("E", 16, SENT_E)):
        c.eq(lino[slot], sent, "BrtlRand leaves %s untouched" % reg)
    for reg, slot, sent in (("B", 17, SENT_B), ("C", 18, SENT_C),
                            ("D", 19, SENT_D), ("E", 20, SENT_E)):
        c.eq(lino[slot], sent,
             "BrtlRandom leaves %s untouched, the divide included" % reg)

    bad = template_diff(good_block)
    if good_block is None:
        c.ok(False, "the compiled library matches its pinned disassembly",
             "the library block could not be located in %s" % exe)
    else:
        c.ok(bad == [],
             "the compiled library matches its pinned disassembly byte for "
             "byte - shr not sar, idiv not div, divisor 8000h, both masks, "
             "and the push/pop edx that keeps D alive",
             "" if not bad else "%d bytes differ, first at library offset "
             "+%d: found %s" % (len(bad), bad[0],
                                " ".join("%02x" % b for b in
                                         good_block[bad[0]:bad[0] + 4])))

    # ------------------------------------------- 5. the narrowing contract
    g = Brtl()
    g.srand(1)
    witness = g.rand()
    raw_bad, narrow_ok, oor = [], 0, []
    for r, i in enumerate(range(OFF["D"], OFF["E"], 2)):
        sign = -1 if r >= len(BIG_MAGS) else 1
        n = sign * BIG_MAGS[r % len(BIG_MAGS)]
        g.srand(1)
        dos = g.dos_random(n) & M32
        if lino[i + 1] == dos:
            narrow_ok += 1
        if to_int16(n) != n:
            oor.append(n)
            if lino[i] != dos:
                raw_bad.append(n)
    c.eq(narrow_ok, len(BIG_MAGS) * 2,
         "BrtlToInt16 then BrtlRandom reproduces the DOS answer for all %d "
         "large arguments, on hardware - this is the idiom every call site "
         "with a computed argument has to use" % (len(BIG_MAGS) * 2))
    c.eq(len(raw_bad), len(oor),
         "BrtlRandom ALONE disagrees with the game for all %d of those "
         "arguments that do not fit an int16 - the gap is pinned, not fixed, "
         "so a future library that narrows internally fails here and has to "
         "be noticed" % len(oor))
    g.srand(1)
    dos40000 = s32(g.dos_random(40000))
    j = OFF["D"] + 2 * BIG_MAGS.index(40000)
    c.ok(s32(lino[j]) != dos40000,
         "worked example: after srand(1), rand() = %d and random(40000) is %d "
         "in the game but %d here - 40000 fits an unsigned word, so this is "
         "not an exotic argument" % (witness, dos40000, s32(lino[j])))

    # ------------------------------------------- 6. srand truncates
    aliased = [a for i, a in enumerate(SRAND_ARGS)
               if lino[OFF["B"] + i] != (a & 0xFFFF)]
    c.ok(not aliased,
         "srand(n) leaves exactly n & FFFF for all %d arguments, 65536 and "
         "2147483647 included - which is why 65,536 seeds is the WHOLE space "
         "and not a sample of it" % len(SRAND_ARGS),
         "" if not aliased else "wrong for %r" % aliased)

    # ------------------------------------------- 7. negative controls
    original = install_library(gen)
    for label, old, new, expect in CONTROLS:
        tag = label.split()[0]
        if not c.ok(original.count(old) == 1,
                    "%s: the line it mutates occurs exactly once in brtl.txt"
                    % tag, repr(old)):
            continue
        install_library(gen, original.replace(old, new))
        mblob, mexe, mnote = build_driver(gen, "tbrtlbad")
        mok, mwhy = valid(mblob)
        if not c.ok(mok, "%s builds, runs and writes a full-length file - "
                         "nothing complains" % label, mnote or mwhy):
            continue
        mutant = units_of(mblob)
        _mhits, mblock = library_bytes(mexe)
        seen, rest = caught_by(lino, mutant, good_block, mblock)
        c.eq(sorted(seen), sorted(expect),
             "%s is caught by exactly: %s" % (label, ", ".join(sorted(expect))))
        if rest:
            c.note("   %s: %d payload units differ, first is %s (%d vs %d)"
                   % (tag, len(rest), decode_unit(rest[0]),
                      lino[rest[0]], mutant[rest[0]]))
        if tag == "NC2":
            c.eq(rest, [],
                 "NC2 ...and every single record is IDENTICAL, which is the "
                 "point: the 7FFF mask keeps only bits 0..14, so no sweep of "
                 "any depth can tell shr from sar. Only the byte template can")
        if tag == "NC3":
            c.eq(rest, [],
                 "NC3 ...and every record is identical too, because every "
                 "lane srands before it draws. Only reading [brtlseed] before "
                 "the first call sees a wrong initial state")

    install_library(gen)

    # ------------------------------------------- 8. optional exhaustive pass
    if exhaustive:
        run_exhaustive(c, gen)
    else:
        c.note("record-by-record over the full sweep was NOT run; the two "
               "full-domain hashes above cover the same draws. Use "
               "--exhaustive for all 1,572,864 records.")

    return c.done()


if __name__ == "__main__":
    sys.exit(main())
