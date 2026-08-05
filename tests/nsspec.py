"""The referee for test_nearstar.py: the 1996 catalogue, and the draw audit.

Two independent things live here, and neither shares code with the port or
with noctis-harness/ns_catalogue.py:

  1. THE CATALOGUE LEGS. STARMAP.BIN is decoded here from its raw bytes -
     32-byte records, a binary64 id at +0, a 20-byte name at +8, 'S' or 'P'
     at +29, two ASCII digits at +30..31 - and an NSTOPO is scored against
     it. For an 'S' record those digits are the star class, written by
     NOCTIS.CPP:1257 as `sprintf (star_label+21, "S%02d", random (12))`
     after `srand (ap_target_id)`; for a 'P' record they are the body index.
     Nothing here consults the port to decide what the file says.

  2. THE DRAW AUDIT. Ten invariants on the per-phase draw counters, read out
     of NOCTIS-0.CPP:4059-4376 by hand and written down as arithmetic in nop
     and nob. They are the only check in the test that can see a draw count
     without a second implementation to compare against, which is exactly
     what the last drawing phase needs - see test_nearstar's honesty note
     about phase G. AUDIT_BREAKS below carries one deliberate violation per
     invariant, so every row is demonstrated to have teeth.

WHAT THE PHASE H LEG IS AND IS NOT. It recounts using the port's OWN nob, so
it grades the port's search_id_code - the binary64 add, the strict +/-1e-5
window, the monotone key map, the two malformed records PORTPLAN names - over
every labelled body in the corpus. It does NOT independently constrain nob;
that is the NOB leg's job, and the NOB leg is an external bound because a
player named the body.

WHAT THE AUDIT IS AND IS NOT. It grades the port's OWN counters against the
source's shape. If a port both took a wrong number of draws and mis-counted
them by the same amount, the audit sees nothing and the three-way comparison
against the C and Python references does. The two checks fail in different
ways on purpose; neither is a substitute for the other.

WHAT IS NOT HERE. Geometry. Wave 4 ported prepare_nearstar's TOPOLOGY -
counts, types, owners, moon ids and the draw sequence - and deliberately
discards every value the eleven float-argument sites produce. p_orb_seed,
p_tilt, p_orb_tilt, p_orb_ecc, p_ray, p_orb_ray, p_orb_orient, p_ring and
key_radius are computed by nothing in this port yet, so nothing here can
grade them, and no check below should be read as evidence about them.
"""

import bisect
import struct
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import starmapspec as S                                          # noqa: E402

IDSCALE = 1e-5                    # NOCTIS-0.CPP:4000, search_id_code's window
MAXBODIES = 80                    # 20 * avgmoons, NOCTIS-D.H:144
STAR_CLASSES = 12
CLASS_PLANETS = (12, 18, 8, 15, 20, 3, 0, 1, 7, 20, 2, 5)   # :930

# NOCTIS.CPP:1230. update_star_label() writes this when search_id_code finds
# no player name, and only THEN sprintf's the class tag over its last three
# bytes. A record still carrying it was never named by a player, so its label
# is not evidence. The count is reported every run so the exclusion cannot
# quietly grow to cover a real failure.
NO_LABEL = "UNKNOWN STAR / CLASS"


# ------------------------------------------------------------- the catalogue

class Sky(object):
    """STARMAP.BIN, decoded here and nowhere else in this test."""

    def __init__(self, path=None):
        path = path or S.CATALOGUE
        with open(path, "rb") as fh:
            self.blob = fh.read()
        self.n = (len(self.blob) - 4) // 32
        self.pids = []
        self.nstar = 0
        for i in range(self.n):
            off = 4 + 32 * i
            t = self.blob[off + 29]
            if t == ord("P"):
                self.pids.append(struct.unpack_from("<d", self.blob, off)[0])
            elif t == ord("S"):
                self.nstar += 1
        self.pids.sort()

    def bits(self, ordinal):
        return struct.unpack_from("<Q", self.blob, 4 + 32 * ordinal)[0]

    def labeled(self, idbits, nob):
        """phase H recomputed: how many of id+1 .. id+nob a 'P' record sits
        inside 1e-5 of. NOCTIS-0.CPP:4364-4369 with search_id_code's strict
        window at :4021."""
        ident = struct.unpack("<d", struct.pack("<Q", idbits))[0]
        hits = 0
        arr = self.pids
        for n in range(1, nob + 1):
            code = ident + n
            lo, hi = code - IDSCALE, code + IDSCALE
            j = bisect.bisect_right(arr, lo)
            if j < len(arr) and arr[j] < hi:
                hits += 1
        return hits


# ---------------------------------------------------------------- the legs

def grade(recs, rows, sky, tag_perm=None):
    """Score an NSTOPO's first len(rows) records against the 1996 catalogue.

    rows are ns_corpus's accepted pairings: (ordinal, x, y, z, name, tag,
    charted body indices). tag_perm, when given, replaces every record's
    class tag with a permuted one - the negative control that shows the CLASS
    leg is scoring arithmetic and not scoring "a number came out".
    """
    out = dict(class_hit=0, class_tot=0, class_miss=[], placeholders=0,
               ident_hit=0, ident_tot=0, ident_miss=[],
               nob_viol=[], nob_tot=0, nob_pinned=0,
               c6_stars=0, c6_named=0, c6_modelled=0,
               h_agree=0, h_dis=[], h_bodies=0, coord_bad=[])
    for k, (rec, x, y, z, name, tag, bodies) in enumerate(rows):
        r = recs[k]
        if _s32(r[0]) != x or _s32(r[1]) != y or _s32(r[2]) != z:
            out["coord_bad"].append((k, rec))
            continue

        want = tag if tag_perm is None else tag_perm[k]
        if tag >= 0 and not name.startswith(NO_LABEL):
            out["class_tot"] += 1
            if r[3] == want:
                out["class_hit"] += 1
            else:
                out["class_miss"].append((rec, name, want, r[3]))
        elif name.startswith(NO_LABEL):
            out["placeholders"] += 1

        out["ident_tot"] += 1
        if (r[10] << 32) | r[9] == sky.bits(rec):
            out["ident_hit"] += 1
        else:
            out["ident_miss"].append((rec, name))

        if bodies:
            out["nob_tot"] += 1
            mx = max(bodies)
            if mx > r[6]:
                out["nob_viol"].append((rec, name, mx, r[6]))
            elif mx == r[6]:
                out["nob_pinned"] += 1

        if tag == 6:
            out["c6_stars"] += 1
            out["c6_named"] += 1 if bodies else 0
            out["c6_modelled"] += 1 if r[5] else 0

        if r[8] != 0xFFFFFFFF:                 # phase H ran for this row
            got = sky.labeled((r[10] << 32) | r[9], r[6])
            out["h_bodies"] += got
            if got == r[8]:
                out["h_agree"] += 1
            else:
                out["h_dis"].append((rec, name, r[8], got))
    return out


# ----------------------------------------------------------- the draw audit
# Read out of NOCTIS-0.CPP:4059-4376 by hand. Each entry is
# (label, predicate(class, nop, nob, phase counters, total)).
#
#   prelude  :4082  one draw, always
#   A        :4086-4107  per planet: 4088, 4089, 4090x2, 4091x2, 4092, 4093,
#            4094x2, 4094(1000) = 11, plus the type draw = 12. Class 8 alone
#            can take a 13th, at :4103, when the :4098 draw came out 0.
#   B        :4111-4115  three draws iff the class is 0, nothing short-circuits
#   C        :4120-4139  unbounded while-loops, but ONLY for classes 2, 5, 9
#            and 11; class 7 assigns and draws nothing; every other class
#            falls through
#   D        :4145-4168  no loops, at most two draws per planet
#   E        :4172-4260  classes 2, 7 and 15 goto no_moons: zero draws AND
#            nob == nop
#   F        :4300-4341  exactly four draws per body
#   G        :4345-4361  exactly two draws per planet
#   total    the eight counters must add up to the reported total

AUDIT = [
    ("prelude == 1",
     lambda c, nop, nob, p, t: p[0] == 1),
    ("A == 12 per planet (12..13 for class 8's else branch)",
     lambda c, nop, nob, p, t: (12 * nop <= p[1] <= 13 * nop) if c == 8
     else p[1] == 12 * nop),
    ("B == 3 draws exactly when the class is 0",
     lambda c, nop, nob, p, t: p[2] == (3 if c == 0 else 0)),
    ("C draws only for classes 2, 5, 9 and 11",
     lambda c, nop, nob, p, t: p[3] == 0 or c in (2, 5, 9, 11)),
    ("D within 0..2 per planet",
     lambda c, nop, nob, p, t: 0 <= p[4] <= 2 * nop),
    ("E == 0 and nob == nop for classes 2, 7 and 15",
     lambda c, nop, nob, p, t: c not in (2, 7, 15) or (p[5] == 0 and nob == nop)),
    ("F == 4 per body, exactly",
     lambda c, nop, nob, p, t: p[6] == 4 * nob),
    ("G == 2 per planet, exactly",
     lambda c, nop, nob, p, t: p[7] == 2 * nop),
    ("the phase counters sum to the reported total",
     lambda c, nop, nob, p, t: t == sum(p)),
    ("nop within 0..class_planets[class] and nob within nop..80",
     lambda c, nop, nob, p, t: (0 <= nop <= CLASS_PLANETS[c]
                                and nop <= nob <= MAXBODIES)),
]


def audit(recs):
    """-> {label: [(record index, class, nop, nob, counters, total)]}."""
    bad = {}
    for i, r in enumerate(recs):
        cls, nop, nob, tot = r[3], r[5], r[6], r[11]
        ph = r[12:20]
        for label, fn in AUDIT:
            if not fn(cls, nop, nob, ph, tot):
                bad.setdefault(label, []).append((i, cls, nop, nob, ph, tot))
    return bad


# ---------------------------------------------- the audit's own controls
# An invariant nobody has seen fail is a comment. AUDIT_BASE is a synthetic
# record that satisfies all ten - a class-0 star with 3 planets and 5 bodies,
# arithmetic done by hand - and AUDIT_BREAKS perturbs exactly one quantity
# per invariant. The test requires the base to pass and every perturbation to
# be flagged BY NAME, so each row of the table above is demonstrated to have
# teeth rather than assumed to.

def base_record():
    r = [0] * 100
    r[3] = 0                    # class
    r[5], r[6] = 3, 5           # nop, nob
    ph = [1, 36, 3, 0, 2, 0, 20, 6]     # 1, 12*3, 3, 0, <=6, -, 4*5, 2*3
    r[11] = sum(ph)
    r[12:20] = ph
    return r


def _with(field, value):
    def f():
        r = base_record()
        r[field] = value
        return r
    return f


AUDIT_BREAKS = [
    ("prelude == 1", _with(12, 2)),
    ("A == 12 per planet (12..13 for class 8's else branch)", _with(13, 37)),
    ("B == 3 draws exactly when the class is 0", _with(14, 2)),
    ("C draws only for classes 2, 5, 9 and 11", _with(15, 1)),
    ("D within 0..2 per planet", _with(16, 7)),
    ("E == 0 and nob == nop for classes 2, 7 and 15", _with(3, 2)),
    ("F == 4 per body, exactly", _with(18, 21)),
    ("G == 2 per planet, exactly", _with(19, 7)),
    ("the phase counters sum to the reported total", _with(11, 69)),
    ("nop within 0..class_planets[class] and nob within nop..80",
     _with(6, 81)),
]


def _s32(v):
    return v - (1 << 32) if v & 0x80000000 else v
