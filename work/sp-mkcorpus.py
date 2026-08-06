#!/usr/bin/env python3
"""sp-mkcorpus.py - write work/sp-corpus.txt, the Wave 6b fixture.

The lino tokeniser understands exactly one lexeme: a signed decimal
integer.  So every float input is given as the signed decimal value of
its binary32 (or, for doubles, its two binary64 halves) BIT PATTERN, and
no decimal float parser exists anywhere in the port.  A shared decimal
parser would be a shared divergence.

THE CORPUS IS CHOSEN, NOT SAMPLED, and each choice is annotated with what
it is there to reach.  Coverage that a check depends on is written down
here AND checked on the emitted records, because a corpus that quietly
loses a class must fail rather than read green:

  * all four gman bands, each with a non-empty paint count;
  * each of the four globe clip arms with a NON-ZERO rejection count -
    otherwise "0 rejections, 0 differences" reads as a pass;
  * globe_saturation both above and below the tapestry's range;
  * colormask in {0, 64, 128, 192}, because "or dl,colormask" happens
    AFTER the saturation floor and the order is observable;
  * start = 0 and start = 718, the unreduced maximum from
    NOCTIS-0.CPP:5564;
  * background at screenshift 0, at the shipped -643, and at the FOUR
    values that put a paint index in 0..3 - the only place the
    segment-origin mask and the buffer-base mask disagree;
  * glowinglobe with a centre that drives riga out of range, so the OOB
    census is non-empty and the affected pages can be excluded;
  * whitesun/whiteglobe with a NEGATIVE fgm_factor (NOCTIS.CPP:2557
    passes -0.15) and a destination pre-filled above 0x3F so the signed
    char overflow fires;
  * VEHICLE in the .NCC corpus - BIRDY's slot-3 garbage maxes at 20.0,
    so a BIRDY-only corpus grades the zeroing pass vacuously.

Usage:  python work/sp-mkcorpus.py  >  work/sp-corpus.txt
"""

import struct
import sys
import os

SRC = os.path.dirname(os.path.abspath(__file__))


def f32(x):
    return struct.unpack("<i", struct.pack("<f", x))[0]


def f64(x):
    return struct.unpack("<ii", struct.pack("<d", x))


# region ids, matching spmem's rgt
RGOFF, RGGLB, RGSBG, RGPBG, RGPVF, RGADP = 0, 1, 2, 3, 4, 5
MDVEH, MDMAM, MDBRD = 0, 1, 2

out = []


def line(*vals):
    out.append(" ".join(str(v) for v in vals))


def note(s):
    out.append("# " + s)


# ----------------------------------------------------------------------
# 7 SCAL : the exact integer scale, enumerated over dy in -106..+105
# ----------------------------------------------------------------------
note("SCAL - round_half_even(int16 x float32), the whole live dy range.")
note("The clamp values, the gman thresholds, and the ADVERSARIAL set:")
note("binary32 neighbours of (k+0.5)/dy, where a float32 multiply fails.")

scal = []
for v in (0.001, 0.01, 0.33, 0.66, 0.99, 1.32, 0.5, 0.25, 0.125, 1.0):
    scal.append(f32(v))
# adversarial: exact ties (k+0.5)/dy and their two binary32 neighbours
for dy in (3, 7, 17, 87, 106):
    for k in (0, 1, 2, 5, 40):
        t = (k + 0.5) / dy
        p = f32(t)
        for q in (p - 1, p, p + 1):
            if 0 < q < 0x7F800000:
                scal.append(q)
scal = list(dict.fromkeys(scal))
for i, m in enumerate(scal):
    line(7, 700 + i, m)

# ----------------------------------------------------------------------
# 8 / 9 : the two map decoders
# ----------------------------------------------------------------------
note("MAPD/OFFD - the decode census, over the SHIPPED bytes.")
line(8, 800, RGGLB, 22586)
line(9, 900, RGOFF, 7340)

# ----------------------------------------------------------------------
# 1 GRAS : globe's integer raster
#   caseid pre pres magpat cx cy gman start cmask sat tapreg bubble
# pre / pres: 0 zero, 1 ramp, 2 carry, 3 flat 200
# ----------------------------------------------------------------------
note("GRAS - globe_raster.  Pinned mag/centre/gman: everything after the")
note("clamp ladder is integer, so these pages are byte-exact.")

gras = [
    # id  pre pres mag        cx   cy  gm start cmask sat tap    bubble
    (100, 0, 1, f32(0.20), 158, 100, 1, 0, 0, 0, RGSBG, 0),
    (101, 0, 1, f32(0.50), 158, 100, 2, 0, 64, 0, RGSBG, 0),
    (102, 0, 1, f32(0.80), 158, 100, 3, 0, 128, 32, RGPBG, 0),
    (103, 0, 1, f32(1.32), 158, 100, 4, 718, 192, 63, RGSBG, 0),
    # saturation ABOVE everything the ramp can produce: the floor wins
    # on every pixel and the page becomes a single colour ORed with the
    # mask - which is what proves the floor is unsigned and comes first.
    (104, 0, 1, f32(0.50), 158, 100, 2, 0, 192, 255, RGSBG, 0),
    # the four clip arms, one at a time
    (110, 0, 1, f32(1.32), 8, 100, 4, 0, 0, 0, RGSBG, 0),   # X low
    (111, 0, 1, f32(1.32), 308, 100, 4, 0, 0, 0, RGSBG, 0),  # X high
    (112, 0, 1, f32(1.32), 158, 8, 1, 0, 0, 0, RGSBG, 0),   # Y low
    (113, 0, 1, f32(1.32), 158, 188, 1, 0, 0, 0, RGSBG, 0),  # Y high
    # the 0.001 floor: every scaled component rounds to zero
    (120, 0, 1, f32(0.001), 158, 100, 1, 0, 0, 0, RGSBG, 0),
    # CARRY: this page starts as case 120's output.  The .NCC handles are
    # not the only persistent state in the wave.
    (121, 2, 2, f32(0.20), 100, 60, 2, 0, 64, 0, RGSBG, 0),
    # the glass bubble, which only runs when glass_bubble is set
    (130, 0, 1, f32(0.80), 158, 100, 3, 0, 0, 0, RGSBG, 1),
]
for c in gras:
    line(1, *c)

# ----------------------------------------------------------------------
# 2 GLOW : caseid pre pres magpat cx cy start arc color
# ----------------------------------------------------------------------
note("GLOW - glowinglobe_raster.  Case 203 drives riga OUT OF RANGE on")
note("purpose: its page is UNGRADEABLE and its OOB census says so.")

glow = [
    (200, 0, 0, f32(0.30), 158, 100, 0, 130, 127),
    (201, 0, 0, f32(0.30), 158, 100, 45, 130, 127),   # a different phase
    (202, 0, 0, f32(0.66), 158, 100, 0, 130, 191),    # colour with bits 6-7
    (203, 0, 0, f32(0.30), 158, 250, 0, 130, 127),    # OOB riga
    (204, 0, 0, f32(0.30), 158, 100, 0, 0, 127),      # arc 0   - all lit
    (205, 0, 0, f32(0.30), 158, 100, 0, 360, 127),    # arc 360 - all dark
]
for c in glow:
    line(2, *c)

# ----------------------------------------------------------------------
# 3 BG : caseid pre pres start shift invert
# ----------------------------------------------------------------------
note("BG - background.  screenshift 0, the shipped -643, and the four")
note("values that fold a paint index into 0..3, where masking at the")
note("segment origin and masking at the buffer base disagree.")

om = open(os.path.join(SRC, "offsets.map"), "rb").read()
words = struct.unpack("<%dH" % (len(om) // 2), om)
wmin = min(w for w in words if w < 64000)
note("smallest paint word in OFFSETS.MAP: %d" % wmin)

bg = [(300, 0, 1, 0, 0, 0),
      (301, 0, 1, 0, (-643) & 0xFFFF, 0),
      (302, 0, 1, 18360, (-643) & 0xFFFF, 0)]
for k in range(4):
    sh = (k - 4 - wmin) & 0xFFFF
    bg.append((310 + k, 0, 1, 0, sh, 0))
# a screenshift that pushes the LARGEST paint word to the top of the
# segment, so a 5x5 block straddles the 16-bit boundary and the last rows
# of it fold to the start of the page.  Without a mask those rows land
# 65,536 units high instead.
wmax = max(w for w in words if w < 64000)
note("largest paint word: %d ; shift %d puts it at DI = 65530"
     % (wmax, (65530 - 4 - wmax) & 0xFFFF))
bg.append((330, 0, 1, 0, (65530 - 4 - wmax) & 0xFFFF, 0))
# the lightning inversion runs on s_background, not on the framebuffer
bg.append((320, 0, 1, 0, (-643) & 0xFFFF, 1))
for c in bg:
    line(3, *c)

# ----------------------------------------------------------------------
# 4 DARK : caseid pre pres view rot
# ----------------------------------------------------------------------
note("DARK - surface()'s terminator band, and both derivations.")
note("view=100,rot=0 drives plwp negative before the sign correction,")
note("which is the only place C's truncating %% is observable.")
dark = [(400, 1, 0, 0, 0),
        (401, 1, 0, 0, 270),
        (402, 1, 0, 100, 0),
        (403, 1, 0, 0, 359),
        (404, 1, 0, 300, 300)]
for c in dark:
    line(4, *c)

# ----------------------------------------------------------------------
# 5/6 WGLB / WSUN : caseid pre pres magpat fgmpat xx(2) yy(2) zz(2)
# with alfa=beta=0 and dzat=0 the nucleus reduces to rx=210x, ry=210y,
# rz=z, so a centred body is (0, 0, z).
# ----------------------------------------------------------------------
note("WGLB/WSUN.  fgm_factor -0.15 is the value NOCTIS.CPP:2557 passes;")
note("pre-state 3 fills the page with 200 so that pix += target[] wraps")
note("the signed char and the 0x3F clamp does NOT fire.")


def whitecase(op, cid, pre, mag, fgm, x, y, z):
    xl, xh = f64(x)
    yl, yh = f64(y)
    zl, zh = f64(z)
    line(op, cid, pre, 0, f32(mag), f32(fgm), xl, xh, yl, yh, zl, zh)


whitecase(5, 500, 0, 60.0, 0.5, 0.0, 0.0, 1000.0)
whitecase(5, 501, 3, 60.0, 0.5, 0.0, 0.0, 1000.0)      # the char overflow
whitecase(5, 502, 0, 300.0, -0.15, 0.0, 0.0, 1000.0)   # negative fgm
whitecase(5, 503, 0, 60.0, 0.5, 0.15, -0.1, 1000.0)    # off-centre
whitecase(5, 504, 0, 60.0, 0.5, 0.0, 3000.0, 1000.0)   # ry rejected
whitecase(6, 600, 0, 60.0, 0.5, 0.0, 0.0, 1000.0)
whitecase(6, 601, 3, 60.0, 0.5, 0.0, 0.0, 1000.0)
whitecase(6, 602, 0, 300.0, -0.15, 0.0, 0.0, 1000.0)
# a sun that is OFF SCREEN: whitesun still writes xsun_onscreen first
whitecase(6, 603, 0, 60.0, 0.5, 3000.0, 0.0, 1000.0)

# ----------------------------------------------------------------------
# 14 SETU : caseid which magpat xx(2) yy(2) zz(2)
# ----------------------------------------------------------------------
note("SETU - the float preambles.  which=0 globe, which=1 glowinglobe.")
note("The same inputs go to both, so the clamp-order and reject-window")
note("differences are measured rather than asserted.")


def setu(cid, which, mag, x, y, z):
    xl, xh = f64(x)
    yl, yh = f64(y)
    zl, zh = f64(z)
    line(14, cid, which, f32(mag), xl, xh, yl, yh, zl, zh)


for i, (mag, x, y, z) in enumerate([
        (2000.0, 0.0, 0.0, 1000.0),      # mag 2.0   -> gman4, clamp 1.32
        (900.0, 0.0, 0.0, 1000.0),       # mag 0.9   -> gman3
        (500.0, 0.0, 0.0, 1000.0),       # mag 0.5   -> gman2
        (200.0, 0.0, 0.0, 1000.0),       # mag 0.2   -> gman1
        (5.0, 0.0, 0.0, 1000.0),         # mag 0.005 -> the 0.001 floor
        (700.0, 0.3, -0.2, 1000.0),      # off-centre, both centres move
        (700.0, 1200.0, 0.0, 1000.0),    # rx = 252: globe accepts (292),
                                         # glowinglobe rejects (226)
        (700.0, 0.0, 0.0, -5.0)]):       # rz < 0.001: both return early
    setu(1400 + i, 0, mag, x, y, z)
    setu(1450 + i, 1, mag, x, y, z)

# ----------------------------------------------------------------------
# the .NCC sequence.  ORDER IS THE FIXTURE: pv_dep_i is persistent state.
# ----------------------------------------------------------------------
note("NCC.  The animals are loaded in the SHIPPED ORDER - mamm_base,")
note("mamm_result, bird_base, bird_result - so the arena offsets must")
note("come out 0 / 3740 / 7480 / 8840 with datatop 10200.  A re-laid-out")
note("arena fails on every one of them.")

line(15, 1000)                                   # unloadallpv
line(10, 1010, 2, MDMAM, f32(1.0), f32(0.75), f32(1.0),
     f32(0.0), f32(0.0), f32(0.0), 0x40, 1)      # mamm_base
line(10, 1011, 3, MDMAM, f32(1.0), f32(1.0), f32(1.0),
     f32(0.0), f32(0.0), f32(0.0), 0x80, 1)      # mamm_result
line(10, 1012, 0, MDBRD, f32(1.0), f32(0.8), f32(1.25),
     f32(0.0), f32(0.0), f32(0.0), 0x40, 1)      # bird_base
line(10, 1013, 1, MDBRD, f32(1.0), f32(1.0), f32(1.0),
     f32(0.0), f32(0.0), f32(0.0), 0x80, 1)      # bird_result
line(16, 1020, 2)
line(16, 1021, 0)

note("modpv with a real pvlist - mamm_ears from NOCTIS-1.CPP:586.")
note("polygon_id in bits 0..11, vtxflag_0..3 in bits 12..15, terminator")
note("0xFFF: Borland packs bitfields LOW BITS FIRST.")


def pvw(pid, f0, f1, f2, f3):
    return pid | (f0 << 12) | (f1 << 13) | (f2 << 14) | (f3 << 15)


ears = [pvw(42, 0, 1, 0, 0), pvw(45, 0, 0, 1, 0),
        pvw(43, 1, 0, 0, 0), pvw(44, 0, 0, 1, 0), 0xFFF]
line(13, 1030, 2, -1, -1, f32(1.7), f32(0.9), f32(1.3),
     f32(30.0), f32(0.0), f32(0.0), len(ears), *ears)
line(16, 1031, 2)

note("copypv resets mamm_result from mamm_base INCLUDING pv_dep_i;")
note("three DRAW frames then show the permutation evolving.")
line(12, 1040, 3, 2)
line(16, 1041, 3)
for i in range(3):
    line(11, 1050 + i, 3, 1, 1,
         f32(0.0), f32(0.0), f32(0.0),
         f32(0.0), f32(0.0), f32(3.0 + i))
line(16, 1060, 3)
# depth sort DISABLED at the call site even though the handle has it
line(11, 1061, 3, 0, 0, f32(0.0), f32(0.0), f32(0.0),
     f32(0.0), f32(0.0), f32(3.0))

note("VEHICLE, on its own arena.  It is the only shipped model whose")
note("slot-3 garbage can overflow - 26 components above 1e6 and 2 that")
note("are not finite - so it is the only one that grades the zeroing.")
line(15, 1100)
line(10, 1110, 0, MDVEH, f32(15.0), f32(15.0), f32(15.0),
     f32(0.0), f32(0.0), f32(0.0), 0, 1)
line(16, 1120, 0)
note("the vehicle is never copypv'd, so its pv_dep_i sorts INCREMENTALLY")
note("across frames - four frames, four different permutations.")
for i in range(4):
    line(11, 1130 + i, 0, 0, 1,
         f32(0.0), f32(0.0), f32(0.0),
         f32(0.0), f32(1.0 * i), f32(4.0))
line(16, 1140, 0)

line(0)

sys.stdout.write("\n".join(out) + "\n")
