r"""mg_spec.py - Wave 8 Impl A, the Python spec.

A second, independent transliteration of the Noctis IV main-loop numerical
kernels, run against the SAME corpus as mg_ref.exe (the C oracle) and the
lino port (mgmain.exe).  Agreement is the BOUNDED claim; for the integer and
exact-float kernels the agreement is byte-exact (EXACT).

PRODUCERS
  spec   this file           Python, x87 modelled with EXACT RATIONALS
                              (su_fp.py: ext = round to 64-bit significand,
                               f64 = round to binary64, ftol32 = chop).
  cref   mg_ref.exe          C, hardware x87 (long double, fsin/fcos, __ftol),
                              control word 133Fh.
  lino   mgmain.exe          L.in.oleum, the actual port.

The three read work/mg-corpus.txt and write a flat little-endian int32
stream; mg_grade.py compares them.  binary64 inputs arrive as the signed
decimal values of their two int32 halves (low then high); integer inputs
arrive as one token.

Kernel list (corpus opcode -> routine):
   1  vimana     ap_drive_mode      tolerant trajectory + exact status_id/pwr
   2  approach   ip_drive_mode      tolerant trajectory + exact status_id/pwr
   3  consumes   additional_consumes exact integer drain + reserve
   4  sector     sector chop        exact (FToIntChop of a double)
   5  identity   nearstar_identity  exact (the NsIdentity chain)
   6  idcmp      ap_id == ns_id     exact (two identities + bit-equal ==)
   7  landing    backup_dzat roundtrip exact (F32Narrow, the deliberate loss)
   8  keys       keyboard switch    exact integer state
"""

import os
import sys
import struct
import math

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from su_fp import fr, ext, f64, f32, ftol32  # the Wave 3 exact float model


# ---------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------
def to_i16(v):
    """i16 store: __ftol then keep low 16 bits, sign-extended."""
    v &= 0xFFFF
    return v - 0x10000 if v >= 0x8000 else v


def dhalves(x):
    """Yield the two signed-int32 halves of a Python float's binary64 image."""
    u = struct.unpack("<Q", struct.pack("<d", float(x)))[0]
    lo = u & 0xFFFFFFFF
    hi = (u >> 32) & 0xFFFFFFFF
    lo -= 0x100000000 if lo >= 0x80000000 else 0
    hi -= 0x100000000 if hi >= 0x80000000 else 0
    return lo, hi


def from_halves(lo, hi):
    u = (lo & 0xFFFFFFFF) | ((hi & 0xFFFFFFFF) << 32)
    return struct.unpack("<d", struct.pack("<Q", u))[0]


def float_bits(f):
    """The single int32 holding a binary32 bit pattern (for ap_target_ray)."""
    return struct.unpack("<i", struct.pack("<f", float(f)))[0]


def bits_to_float(i):
    return struct.unpack("<f", struct.pack("<i", i))[0]


# status ids, kept in lock-step with mg_ref.c's enum
ST = dict(NONE=0, CHARGING=1, PARKING=2, LINKING=3, DRIVING=4, IGNITION=5,
          CALIBRATED=6, TRACKING=7, WARMING=8, REFINING=9, BREAKING=10,
          APPROACH=11, STANDBY=12)


# ---------------------------------------------------------------------
# the NsIdentity chain, exact:  ((((x/100000)*y)/100000)*z)/100000
# Each op rounded to ext (64-bit significand), one final store to binary64.
# ---------------------------------------------------------------------
def ident_i(x, y, z):
    t = ext(fr(x) / fr(100000))
    t = ext(t * fr(y))
    t = ext(t / fr(100000))
    t = ext(t * fr(z))
    t = ext(t / fr(100000))
    return f64(t)


# ---------------------------------------------------------------------
# emitters: append int32 units to an output list
# ---------------------------------------------------------------------
def emit_d(out, d):
    out.extend(dhalves(d))


def emit_i(out, v):
    out.append(int(v))


# ---------------------------------------------------------------------
# kernel 1 - ap_drive_mode
# ---------------------------------------------------------------------
def vimana(toks, out):
    nframes = toks.pop(0)
    dzat_x = from_halves(toks.pop(0), toks.pop(0))
    dzat_y = from_halves(toks.pop(0), toks.pop(0))
    dzat_z = from_halves(toks.pop(0), toks.pop(0))
    ap_x = from_halves(toks.pop(0), toks.pop(0))
    ap_y = from_halves(toks.pop(0), toks.pop(0))
    ap_z = from_halves(toks.pop(0), toks.pop(0))
    init_d = from_halves(toks.pop(0), toks.pop(0))
    cur = from_halves(toks.pop(0), toks.pop(0))
    ray = bits_to_float(toks.pop(0))
    anti_rad = toks.pop(0)
    ap_targetted = toks.pop(0)
    pwr = toks.pop(0)

    stspeed = 1
    ap_reached = 0
    vrt = 0.01  # vimana_reaction_time, persists across frames

    for _ in range(nframes):
        sid = ST["NONE"]
        dxx = dzat_x - ap_x
        dyy = dzat_y - ap_y
        dzz = dzat_z - ap_z
        l_dsd = math.sqrt(dxx * dxx + dyy * dyy + dzz * dzz)

        if not (ap_targetted and stspeed):
            emit_d(out, dzat_x); emit_d(out, dzat_y); emit_d(out, dzat_z)
            emit_i(out, to_i16(pwr)); emit_d(out, cur)
            emit_i(out, ap_reached); emit_i(out, sid)
            continue

        if ap_targetted == -1:
            ras = 25000.0
        else:
            ras = 44.0 * ray if anti_rad else 1.5 * ray

        if l_dsd < ras:
            sid = ST["CALIBRATED"]
            ap_reached = 1
            stspeed = 0
        else:
            if l_dsd > 0.9999 * init_d:
                req = 0.001 * l_dsd; rt = 0.1; sid = ST["CHARGING"]
            elif l_dsd < 7500.0 + ras:
                req = 0.005 * l_dsd; rt = 0.01; sid = ST["PARKING"]
            elif l_dsd < 15000.0 + ras:
                req = 0.005 * l_dsd; rt = 0.0025; sid = ST["LINKING"]
            elif l_dsd < 0.9990 * init_d:
                req = 0.00001 * l_dsd; rt = 0.05; sid = ST["DRIVING"]
            else:
                req = 0.0002 * l_dsd; sid = ST["IGNITION"]
                if vrt != 0.08:
                    vrt = 0.08
                rt = vrt
            cur = cur + (req - cur) * rt
            if cur < 10.0:
                cur = 10.0
            dzat_x -= dxx / cur
            dzat_y -= dyy / cur
            dzat_z -= dzz / cur
            # pwr: ext subtraction, __ftol chop, i16 wrap
            sub = ext(fr(pwr) - ext(fr(l_dsd) * fr(1e-5)))
            pwr = to_i16(ftol32(sub))
        emit_d(out, dzat_x); emit_d(out, dzat_y); emit_d(out, dzat_z)
        emit_i(out, to_i16(pwr)); emit_d(out, cur)
        emit_i(out, ap_reached); emit_i(out, sid)


# ---------------------------------------------------------------------
# kernel 2 - ip_drive_mode
# ---------------------------------------------------------------------
def approach(toks, out):
    nframes = toks.pop(0)
    dzat_x = from_halves(toks.pop(0), toks.pop(0))
    dzat_y = from_halves(toks.pop(0), toks.pop(0))
    dzat_z = from_halves(toks.pop(0), toks.pop(0))
    plx = from_halves(toks.pop(0), toks.pop(0))
    ply = from_halves(toks.pop(0), toks.pop(0))
    plz = from_halves(toks.pop(0), toks.pop(0))
    init_d = from_halves(toks.pop(0), toks.pop(0))
    cur = from_halves(toks.pop(0), toks.pop(0))
    ray = bits_to_float(toks.pop(0))
    pwr = toks.pop(0)
    ip_reaching = toks.pop(0)

    ip_reached = 1 if ip_reaching == 0 else 0

    for _ in range(nframes):
        sid = ST["NONE"]
        dxx = dzat_x - plx
        dyy = dzat_y - ply
        dzz = dzat_z - plz
        l_dsd = math.sqrt(dxx * dxx + dyy * dyy + dzz * dzz)

        if not ip_reaching:
            emit_d(out, dzat_x); emit_d(out, dzat_y); emit_d(out, dzat_z)
            emit_i(out, to_i16(pwr)); emit_d(out, cur)
            emit_i(out, ip_reached); emit_i(out, sid)
            continue

        if l_dsd > 0.99999 * init_d:
            req = 25.0 * l_dsd; rt = 0.001; sid = ST["WARMING"]
        elif l_dsd < 25.0 and init_d > 500.0:
            req = 50.0 * l_dsd; rt = 0.0002; sid = ST["REFINING"]
        elif l_dsd < 100.0 and init_d > 500.0:
            req = 15.0 * l_dsd; rt = 0.0003; sid = ST["BREAKING"]
        elif l_dsd < 0.99500 * init_d:
            req = 0.05 * l_dsd; rt = 0.025; sid = ST["APPROACH"]
        else:
            req = 1.5 * l_dsd; rt = 0.05; sid = ST["IGNITION"]
        cur = cur + (req - cur) * rt
        if cur < 10.0:
            cur = 10.0
        dzat_x -= dxx / cur
        dzat_z -= dzz / cur
        dzat_y -= dyy / (0.5 * cur)
        sub = ext(fr(pwr) - ext(fr(l_dsd) * fr(0.5e-5)))
        pwr = to_i16(ftol32(sub))
        if l_dsd < 2.0 * ray:
            sid = ST["STANDBY"]
            ip_reaching = 0
            ip_reached = 1
        emit_d(out, dzat_x); emit_d(out, dzat_y); emit_d(out, dzat_z)
        emit_i(out, to_i16(pwr)); emit_d(out, cur)
        emit_i(out, ip_reached); emit_i(out, sid)


# ---------------------------------------------------------------------
# kernel 3 - additional_consumes (pure integer)
# ---------------------------------------------------------------------
def consumes(toks, out):
    nticks = toks.pop(0)
    iqsecs = toks.pop(0)
    secs = from_halves(toks.pop(0), toks.pop(0))
    ip_targetted = toks.pop(0); sync = toks.pop(0); ip_reached = toks.pop(0)
    pl_search = toks.pop(0); ilightv = toks.pop(0); field_amp = toks.pop(0)
    pwr = toks.pop(0); charge = toks.pop(0)

    for _ in range(nticks):
        secs += 1.0
        if iqsecs < int(secs):
            iqsecs = int(secs)
        if ip_targetted > -1 and pwr > 15000:
            if ip_reached and sync:
                if sync == 1 and not (iqsecs % 29): pwr -= 1; iqsecs += 1
                if sync == 2 and not (iqsecs % 18): pwr -= 1; iqsecs += 1
                if sync == 3 and not (iqsecs % 58): pwr -= 1; iqsecs += 1
                if sync == 4 and not (iqsecs % 7):  pwr -= 1; iqsecs += 1
                if sync == 5 and not (iqsecs % 33): pwr -= 1; iqsecs += 1
        if pl_search and not (iqsecs % 155): pwr -= 1; iqsecs += 1
        if ilightv == 1 and not (iqsecs % 84): pwr -= 1; iqsecs += 1
        if field_amp and not (iqsecs % 41): pwr -= 1; iqsecs += 1
        if pwr <= 15000:
            if charge > 0:
                charge -= 1; pwr = 20000
            elif charge < 0:
                pwr = 20000
            else:
                pwr = 15000
        emit_i(out, to_i16(pwr)); emit_i(out, charge); emit_i(out, iqsecs)


# ---------------------------------------------------------------------
# kernel 4 - the sector chop (exact)
# ---------------------------------------------------------------------
def sector(toks, out):
    dzat_x = from_halves(toks.pop(0), toks.pop(0))
    dzat_y = from_halves(toks.pop(0), toks.pop(0))
    dzat_z = from_halves(toks.pop(0), toks.pop(0))
    vs = toks.pop(0)
    # (dzat - vs*50000) / 100000  evaluated in ext, then __ftol chop to long
    for d in (dzat_x, dzat_y, dzat_z):
        q = ext(fr(d) - ext(fr(vs) * fr(50000)))
        q = ext(q / fr(100000))
        sx = ftol32(q)
        sx = (sx & 0xFFFFFFFF)
        sx -= 0x100000000 if sx >= 0x80000000 else 0
        emit_i(out, sx * 100000)


# ---------------------------------------------------------------------
# kernel 5/6 - identity (exact)
# ---------------------------------------------------------------------
def identity(toks, out):
    x = toks.pop(0); y = toks.pop(0); z = toks.pop(0)
    emit_d(out, ident_i(x, y, z))


def idcmp(toks, out):
    ap = (toks.pop(0), toks.pop(0), toks.pop(0))
    ns = (toks.pop(0), toks.pop(0), toks.pop(0))
    ap_id = ident_i(*ap)
    ns_id = ident_i(*ns)
    emit_d(out, ap_id); emit_d(out, ns_id)
    emit_i(out, 1 if ap_id == ns_id else 0)


# ---------------------------------------------------------------------
# kernel 7 - the landing roundtrip (exact, deliberate precision loss)
# ---------------------------------------------------------------------
def landing(toks, out):
    dzat_x = from_halves(toks.pop(0), toks.pop(0))
    dzat_y = from_halves(toks.pop(0), toks.pop(0))
    dzat_z = from_halves(toks.pop(0), toks.pop(0))
    out.extend(dhalves(float(f32(fr(dzat_x)))))
    out.extend(dhalves(float(f32(fr(dzat_y)))))
    out.extend(dhalves(float(f32(fr(dzat_z)))))


# ---------------------------------------------------------------------
# kernel 8 - keyboard switch (exact integer)
# ---------------------------------------------------------------------
def keys(toks, out):
    nkeys = toks.pop(0)
    sys_ = toks.pop(0); dev_page = toks.pop(0); s_command = toks.pop(0)
    about = toks.pop(0); gms = toks.pop(0); mlook = toks.pop(0)
    surlight = toks.pop(0); revcontrols = toks.pop(0)
    dlt_nav_beta = 0
    lifter = 0
    for _ in range(nkeys):
        c = toks.pop(0)
        ext_ = 0
        sid = ST["NONE"]
        if c == 0:
            c = toks.pop(0); ext_ = 1
        if ext_:
            if c == 0x3B:
                about = 0 if about else 1
                if about: gms = 0
            elif c == 0x3C:
                gms = 0 if gms else 1
                if gms: about = 0
            elif c == 75: dlt_nav_beta += 15
            elif c == 77: dlt_nav_beta -= 15
            elif c == 72: lifter = -100
            elif c == 80: mlook = (mlook + 1) % 3
        else:
            if c == ord('5'): sys_ = 1; dev_page = 0
            elif c == ord('r'): sys_ = 2; dev_page = 0
            elif c == ord('d'): sys_ = 3; dev_page = 0
            elif c == ord('x'): sys_ = 4; dev_page = 0
            elif c == ord('6'): s_command = 1
            elif c == ord('7'): s_command = 2
            elif c == ord('8'): s_command = 3
            elif c == ord('9'): s_command = 4
            elif c == ord('+') and surlight < 63: surlight += 1
            elif c == ord('-') and surlight > 10: surlight -= 1
        emit_i(out, sys_); emit_i(out, dev_page); emit_i(out, s_command)
        emit_i(out, about); emit_i(out, gms); emit_i(out, mlook)
        emit_i(out, surlight); emit_i(out, dlt_nav_beta); emit_i(out, lifter)
        emit_i(out, sid)


DISPATCH = {1: vimana, 2: approach, 3: consumes, 4: sector,
            5: identity, 6: idcmp, 7: landing, 8: keys}


def run(toks):
    """Run every case in the token list; return the int32 output stream."""
    out = []
    while toks:
        kind = toks.pop(0)
        fn = DISPATCH.get(kind)
        if fn is None:
            break
        fn(toks, out)
    return out


def to_bytes(int32_list):
    return struct.pack("<%di" % len(int32_list), *int32_list)


# ---------------------------------------------------------------------
# corpus generation
# ---------------------------------------------------------------------
# a handful of real NIV+ star coordinates (x,y,z) from STARMAP.BIN, used so
# the exact identity site is graded against the real catalogue.
REAL_STARS = [
    (-5497488, 5077519, 2856581),
    (4867504, 2585957, -5646997),
    (4254608, -4294361, 3882927),
    (2568176, -4269415, 6430277),
    (3716752, -4366451, 4158316),
    (3816752, -4301085, 4034419),
    (4360720, 2538280, -5709743),
    (2358544, -6213718, 4159543),
    (3858544, -5745947, 2575799),
    (3534256, -4285443, 3413977),
    (0, 100000000, 0),          # the ap_target default (1E8)
    (3797120, -4352112, -925018),  # the dzat initial
]


def _d(x):
    """two decimal tokens for a double's halves"""
    lo, hi = dhalves(x)
    return "%d %d" % (lo, hi)


def gen_corpus(path):
    """Write the corpus: a flat signed-decimal stream with '#' comments."""
    lines = []

    def w(s=""): lines.append(s)

    w("# Wave 8 Impl A corpus.  Flat signed decimals; '#' = comment to EOL.")
    w("# Doubles arrive as their two int32 halves, low then high.")
    w()

    # ---- kernel 1: vimana trajectories -------------------------------
    w("# --- vimana (ap_drive_mode). opcode nframes dzat(3d) ap(3d)")
    w("#     init_d cur_coef ray_bits anti_rad ap_targetted pwr")
    # a long flight: dzat far from target, init_d = current distance.
    dzat = (3797120.0, -4352112.0, -925018.0)
    tgt = (4867504.0, 2585957.0, -5646997.0)
    d0 = math.sqrt(sum((a - b) ** 2 for a, b in zip(dzat, tgt)))
    w("1 40 %s %s %s %s %s %s %s %s %d 0 1 19700" %
      (_d(dzat[0]), _d(dzat[1]), _d(dzat[2]),
       _d(tgt[0]), _d(tgt[1]), _d(tgt[2]),
       _d(d0), _d(1000.0 * d0), float_bits(1000.0)))
    # a short hop where CALIBRATED is hit immediately (target within ras).
    w("1 8 %s %s %s %s %s %s %s %s %d 0 1 19800" %
      (_d(100.0), _d(0.0), _d(0.0), _d(110.0), _d(0.0), _d(0.0),
       _d(10.0), _d(100.0), float_bits(1000.0)))
    # anti_rad path -> ras = 44*ray
    w("1 25 %s %s %s %s %s %s %s %s %d 1 1 19900" %
      (_d(0.0), _d(0.0), _d(0.0), _d(50000.0), _d(0.0), _d(0.0),
       _d(50000.0), _d(100.0), float_bits(100.0)))
    w()

    # ---- kernel 2: approach trajectories -----------------------------
    w("# --- approach (ip_drive_mode). opcode nframes dzat(3d) pl(3d)")
    w("#     init_d cur_coef ray_bits pwr ip_reaching")
    dzat = (4360720.0, 2538280.0, -5709743.0)
    pl = (4360720.0 + 80000.0, 2538280.0, -5709743.0)
    d0 = math.sqrt(sum((a - b) ** 2 for a, b in zip(dzat, pl)))
    w("2 30 %s %s %s %s %s %s %s %s %d %d 1" %
      (_d(dzat[0]), _d(dzat[1]), _d(dzat[2]),
       _d(pl[0]), _d(pl[1]), _d(pl[2]),
       _d(d0), _d(1000.0 * d0), float_bits(5000.0), 19900))
    # very close start so REFINING/BREAKING windows fire
    pl2 = (dzat[0] + 60.0, dzat[1], dzat[2])
    w("2 20 %s %s %s %s %s %s %s %s %d %d 1" %
      (_d(dzat[0]), _d(dzat[1]), _d(dzat[2]),
       _d(pl2[0]), _d(pl2[1]), _d(pl2[2]),
       _d(1000.0), _d(100.0), float_bits(50.0), 19900))
    w()

    # ---- kernel 3: additional_consumes -------------------------------
    w("# --- consumes. opcode nticks iqsecs secs(1d) ip_t sync ip_reached")
    w("#     pl_search ilightv field_amp pwr charge")
    # normal cruise drain with sync=4 (vimana orbit, %7)
    w("3 40 1000 %s 0 4 1 0 1 0 19500 3" % _d(1000.0))
    # OMEGA: charge negative -> never power loss
    w("3 30 1000 %s 0 0 0 0 0 0 14000 -1" % _d(1000.0))
    # charge>0 reserve: pwr dips below 15000, charge tops it up
    w("3 20 1000 %s 0 0 0 0 0 0 15001 2" % _d(1000.0))
    # pl_search + ilightv + field_amp all on (the slow drains)
    w("3 60 1000 %s -1 0 0 1 1 1 20000 5" % _d(1000.0))
    w()

    # ---- kernel 4: the sector chop -----------------------------------
    w("# --- sector chop. opcode dzat(3d) visible_sectors")
    # exactly on a sector boundary (vs=9): the chop-toward-zero edge
    w("4 %s %s %s 9" % (_d(3797120.0), _d(-4352112.0), _d(-925018.0)))
    # negative dzat just past a multiple of 100000 (chop direction matters)
    w("4 %s %s %s 9" % (_d(-3797199.5), _d(4352112.25), _d(925018.9)))
    # field_amplificator: visible_sectors = 14
    w("4 %s %s %s 14" % (_d(3797120.0), _d(-4352112.0), _d(-925018.0)))
    # a value with a large negative fractional part
    w("4 %s %s %s 9" % (_d(-1.5), _d(-0.5), _d(0.5)))
    w()

    # ---- kernel 5: nearstar_identity (exact) -------------------------
    w("# --- identity. opcode x y z  (int32 coords)")
    for (x, y, z) in REAL_STARS:
        w("5 %d %d %d" % (x, y, z))
    w()

    # ---- kernel 6: ap_target_id == nearstar_identity -----------------
    w("# --- identity compare. opcode ap(3) ns(3)")
    # equal: identical coords -> identities bit-equal
    x, y, z = REAL_STARS[0]
    w("6 %d %d %d %d %d %d" % (x, y, z, x, y, z))
    # not equal: a one-unit difference in z
    w("6 %d %d %d %d %d %d" % (x, y, z, x, y, z + 1))
    # not equal: totally different star
    w("6 %d %d %d %d %d %d" % (REAL_STARS[1] + REAL_STARS[2]))
    w()

    # ---- kernel 7: the landing roundtrip -----------------------------
    w("# --- landing roundtrip (F32Narrow). opcode dzat(3d)")
    # the real initial dzat (~3.8e6, where binary32 ULP is 0.25)
    w("7 %s %s %s" % (_d(3797120.0), _d(-4352112.0), _d(-925018.0)))
    # a value already exactly representable in binary32 -> unchanged
    w("7 %s %s %s" % (_d(1.0), _d(1024.0), _d(-0.125)))
    # fractional double that binary32 must round
    w("7 %s %s %s" % (_d(0.1), _d(0.2), _d(0.3)))
    w()

    # ---- kernel 8: the keyboard switch -------------------------------
    w("# --- keyboard switch. opcode nkeys sys dev_page s_command")
    w("#     about gms mlook surlight revcontrols  then the press stream")
    w("#     (code 0 = extended: next token is the extended code)")
    # each press is a tuple of codes; (0, ext) is one extended press.
    presses = [ord('5'), (0, 0x3B), ord('r'), ord('6'), (0, 75), ord('d'),
               ord('7'), (0, 80), ord('x'), ord('+'), ord('+'), ord('-'),
               (0, 72), (0, 0x3C), ord('8'), (0, 77), ord('9'), ord('-')]
    flat = []
    for p in presses:
        flat.extend(p if isinstance(p, tuple) else (p,))
    w("8 %d 4 0 0 0 0 0 20 0 %s" % (len(presses),
                                    " ".join(str(c) for c in flat)))
    w()

    with open(path, "w") as f:
        f.write("\n".join(lines))
    return lines


if __name__ == "__main__":
    corp = os.path.join(HERE, "mg_corpus.txt")
    gen_corpus(corp)
    print("wrote", corp)
    toks = []
    for line in open(corp):
        line = line.split("#", 1)[0].split()
        for t in line:
            toks.append(int(t))
    out = run(toks)
    print("model produced %d int32 units" % len(out))
