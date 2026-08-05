"""The referee for Wave 3: an exact x87 written in integers, and the oracle.

This file is the judge in test_floatcontract.py. Two things about it matter
more than anything it computes.

  * IT SHARES NO ARITHMETIC WITH THE THING IT JUDGES. The L.in.oleum side is
    x87 instructions inside ML fragments. This side is Python integers: every
    intermediate is an exact (m, e) pair meaning m * 2**e, and every x87
    operation is "form the exact rational result, then round it to p
    significant bits". No CPython float is ever created except when a
    binary64 bit pattern is finally assembled, and that is done by hand from
    the integer m and e rather than by struct.pack of a computed float.

  * IT NEVER READS AN EXPECTED VALUE OUT OF ANYTHING THIS PROJECT WROTE. The
    expected identities come out of STARMAP.BIN - 37,578 records written by
    Noctis IV between 1996 and today, by a program compiled with Borland C++
    against a 387. That file is the only place in this port where "did we get
    the floating point right" has an answer that predates the question.

WHY (m, e) AND NOT Fraction. An x87 result is always m * 2**e with m an
integer of exactly p bits, so the pair IS the machine's state, and rounding
is one divmod. Fraction would work and did work in the QA pass, but it hides
the significand, and the significand is what a one-ULP perturbation edits.

WHAT p MEANS. The x87 precision-control field rounds the significand of every
arithmetic result to 64, 53 or 24 bits while leaving the exponent range
alone. That is what `p` is here. It is NOT "the value was stored to a double":
a store to binary64 also clamps the exponent and is a second rounding. The
distinction is the whole subject of Wave 3, so the two are separate here -
`p` for precision control, `spill` for stores.

THE ACCEPTANCE WINDOW is starmapspec's, unchanged: |P - N| < 1e10 with P the
exact integer product x*y*z and N = trunc(id * 1e15) from the record's bits.
That layer is refereed by test_starcatalogue.py and is not re-argued here.
This file only decides which matched records are USABLE as an oracle, and its
rule is deliberately severe: a catalogue record counts only if the sweep
offered exactly ONE coordinate triple for it. A record with two candidates
could be scored by whichever candidate happens to reproduce it, and a score
obtained that way measures the chooser, not the arithmetic.
"""

import collections
import struct

import starmapspec as S

# x87 rounding-control encodings, in the control word's bits 11..10.
RC_NEAR, RC_DOWN, RC_UP, RC_CHOP = 0, 1, 2, 3

# and precision control, bits 9..8 -> significand bits
PC_BITS = {0: 24, 1: None, 2: 53, 3: 64}

K100000 = 100000
K1EM5_BITS = 0x3EE4F8B588E368F1     # the f64 1e-5 the lookup formula uses


# ------------------------------------------------------------------ rounding

def _round(num, den, p, rc):
    """Round num/den to p significant bits. Returns (m, e); value = m * 2**e.

    den > 0. |m| has exactly p bits unless the value is zero. This is the
    only place rounding happens, so a bug here is visible in every battery at
    once rather than in one of them.
    """
    if num == 0:
        return (0, 0)
    neg = num < 0
    n = -num if neg else num

    # First guess at the scale, then correct: bit_length differences are off
    # by at most one because they ignore the fractional part.
    #
    # `dd` is the divisor actually used, which is NOT `den` once sh goes
    # negative. Comparing the remainder against `den` instead of `dd` is a
    # real bug that was in this file and that the x87 caught: it made
    # round-to-nearest decide ties against a denominator 2**(-sh) too small,
    # which only ever bites when the scale correction is negative - i.e. at
    # PC=24 on large intermediates, on about a tenth of the catalogue.
    sh = p - (n.bit_length() - den.bit_length())
    while True:
        if sh >= 0:
            num, dd = n << sh, den
        else:
            num, dd = n, den << (-sh)
        q, r = divmod(num, dd)
        b = q.bit_length()
        if b > p:
            sh -= 1
            continue
        if b < p:
            sh += 1
            continue
        break

    if rc == RC_NEAR:
        if 2 * r > dd or (2 * r == dd and (q & 1)):
            q += 1
    elif rc == RC_CHOP:
        pass                                  # magnitude truncates: toward zero
    elif rc == RC_DOWN:                       # toward -inf
        if neg and r:
            q += 1
    elif rc == RC_UP:                         # toward +inf
        if (not neg) and r:
            q += 1
    else:
        raise ValueError("rc %r" % rc)

    if q.bit_length() > p:                    # rounded up out of the binade
        q >>= 1
        sh -= 1
    return (-q if neg else q, -sh)


def _mul_int(v, k, p, rc):
    m, e = v
    if e >= 0:
        return _round(m * k * (1 << e), 1, p, rc)
    return _round(m * k, 1 << (-e), p, rc)


def _div_int(v, k, p, rc):
    m, e = v
    if e >= 0:
        return _round(m * (1 << e), k, p, rc)
    return _round(m, k * (1 << (-e)), p, rc)


def _mul_pair(v, w, p, rc):
    (m, e), (n, f) = v, w
    g = e + f
    if g >= 0:
        return _round(m * n * (1 << g), 1, p, rc)
    return _round(m * n, 1 << (-g), p, rc)


def _unpair_f64(bits):
    """(m, e) of a binary64 bit pattern, exactly. Normals only."""
    sgn = bits >> 63
    ex = (bits >> 52) & 0x7FF
    frac = bits & ((1 << 52) - 1)
    if ex == 0 or ex == 0x7FF:
        raise ValueError("not a normal double: %016X" % bits)
    m = frac | (1 << 52)
    return (-m if sgn else m, ex - 1075)


def f64_bits(v, rc=RC_NEAR):
    """The bit pattern an `fstp qword` writes for the extended value v.

    Rounds the significand to 53 bits under rc and then assembles the fields
    by hand. Nothing here goes through a CPython float, so a Python rounding
    quirk cannot make the referee agree with the port by luck.
    """
    m, e = _round(v[0] * (1 << v[1]), 1, 53, rc) if v[1] >= 0 \
        else _round(v[0], 1 << (-v[1]), 53, rc)
    if m == 0:
        return 0
    neg = m < 0
    a = -m if neg else m
    be = e + 52 + 1023
    if not (0 < be < 2047):
        raise ValueError("binary64 exponent out of range: %d" % be)
    return (int(neg) << 63) | (be << 52) | (a - (1 << 52))


def flip_ext(v, bit):
    """XOR one bit of the 64-bit extended significand, as the probe does.

    The probe stores the intermediate as a 10-byte TBYTE, XORs a dword of it
    and reloads. In a value already rounded to p=64 the significand IS m, so
    the model is the same edit on the integer.
    """
    m, e = v
    if m == 0:
        return v
    neg = m < 0
    a = -m if neg else m
    if a.bit_length() != 64:
        raise ValueError("not a 64-bit significand: %d bits" % a.bit_length())
    a ^= (1 << bit)
    return (-a if neg else a, e)


# -------------------------------------------------------------- the schedules

def ns_identity(x, y, z, p=64, rc=RC_NEAR, spill=(), flip=None, order=(0, 1, 2)):
    """NOCTIS-0.CPP:4078, as an instruction schedule.

        fild x / fidiv 1e5 / fild y / fmulp / fidiv 1e5
                            / fild z / fmulp / fidiv 1e5 / fstp id

    Five operations and ONE store. `spill` is a set of 1-based operation
    numbers after which the running value is additionally narrowed to
    binary64 - i.e. an fstp/fld pair a compiler would insert. `flip` is
    (op, bit): XOR one bit of the extended significand after that operation,
    which is the perturbation the probe performs with a TBYTE round trip.
    `order` permutes which input each fild reads, which changes nothing
    mathematically and must change nothing here.
    """
    v = [x, y, z]
    a, b, c = v[order[0]], v[order[1]], v[order[2]]
    cur = (a, 0)                                       # fild: exact
    ops = (("d", K100000), ("m", b), ("d", K100000), ("m", c), ("d", K100000))
    for i, (kind, k) in enumerate(ops, 1):
        cur = _div_int(cur, k, p, rc) if kind == "d" else _mul_int(cur, k, p, rc)
        if i in spill:
            cur = _unpair_f64(f64_bits(cur, rc))
        if flip and flip[0] == i:
            cur = flip_ext(cur, flip[1])
    return f64_bits(cur, rc)


def isthere_identity(x, y, z, p=64, rc=RC_NEAR):
    """The lookup formula, which is a real formula in the game and is NOT the
    one that wrote the catalogue: (x*1e-5) * ((y*1e-5) * (z*1e-5)).

    Its required score is zero. A grader that scores it above zero is not
    grading arithmetic, it is grading "did a number come out".
    """
    k = _unpair_f64(K1EM5_BITS)
    a = _mul_pair((x, 0), k, p, rc)
    b = _mul_pair((y, 0), k, p, rc)
    c = _mul_pair((z, 0), k, p, rc)
    d = _mul_pair(b, c, p, rc)                 # fmulp: st1 <- st1*st0
    return f64_bits(_mul_pair(a, d, p, rc), rc)


def cw_fields(cw):
    """(precision bits, rounding control) of an x87 control word."""
    p = PC_BITS[(cw >> 8) & 3]
    if p is None:
        raise ValueError("control word %04X selects the reserved PC 01" % cw)
    return p, (cw >> 10) & 3


# --------------------------------------------------------------- the oracle

def star_ids(recs=None):
    """Every id bit pattern stored under an 'S' record in the real catalogue.

    Membership in this set is the weakest possible claim about a computed
    value - "this exact 64-bit pattern is somewhere in the 1996 file" - and
    it is worth making separately, because it survives every mistake the
    pairing of inputs to expecteds could contain.
    """
    recs = S.load_catalogue() if recs is None else recs
    out = set()
    for (_i, raw, _tail, typ, _name) in recs:
        if typ != S.STAR or raw == S.TOMB:
            continue
        out.add(struct.unpack("<Q", raw)[0])
    return out


Oracle = collections.namedtuple(
    "Oracle", "K trip exp names ords rel slack nrec nuniq nambig dropped maxrel")

# The pairing residue a record may show and still be believed. See below.
MAXREL = 2.0 ** -36


def build_oracle(K, recs=None, maxrel=MAXREL):
    """The unbiased input set, and the two rules that make it unbiased.

    Returns coordinate triples and, in the same order, the 64-bit pattern the
    catalogue stores for the record each triple was found for.

    RULE 1 - NO CHOICE. Only records the sweep offered exactly ONE candidate
    triple for are used. A record with two candidates could be scored by
    whichever one reproduces it, and a set assembled that way measures the
    chooser rather than the arithmetic. The ambiguous records are discarded
    unexamined; nothing here ever asks "does this candidate reproduce the
    record", because that question is what the test is for.

    RULE 2 - NO COINCIDENCES. Noctis's acceptance window is |P - N| < 1e10,
    which is idscale 1e-5 scaled by 1e15. That is the game's own tolerance
    for FINDING a star by name, and it is far looser than what PAIRING a
    record with a triple for bit-exactness requires: a record genuinely
    written from this triple stores a rounded binary64 of the same exact
    integer product P, so its residue |P - N| / |P| is a few binary64 ULPs.
    A record whose residue is thousands of times larger is a different star
    that happened to land inside the window.

    That is measured, not assumed, and the test asserts it every run: the
    believable population runs from 2**-55 to about 2**-43 and stops, and the
    threshold above sits in an empty band with clearance on both sides. At
    K=64 the rule drops nothing at all, so the headline number does not
    depend on it; at K=96 it drops one record, 'L4 LEG 5A' at 2**-29.4, which
    no hypothesis in the whole ladder reproduces - not 64, 53 or 24 bits, not
    chopped, not spilled at any point, not the lookup formula.

    Stated plainly, because it is the one place this rule could mislead: a
    catalogue written at 24-bit precision would show residues around 2**-24
    and would be discarded wholesale by rule 2. It is not; the test reports
    the median residue so that stays visible rather than assumed, and the
    K=64 run needs no filtering to reach the same verdict.
    """
    recs = S.load_catalogue() if recs is None else recs
    hits, _counts, _stars = S.run(K, recs=recs)
    cand = collections.defaultdict(set)
    resid, permit = {}, {}
    for (o, x, y, z, P, N) in hits:
        cand[o].add((x, y, z))
        mag = float(max(abs(P), 1))
        resid[(o, (x, y, z))] = abs(P - N) / mag
        # what Noctis's own window permits at this magnitude, as a relative
        # slack. The ratio of this to maxrel is how much the pairing rule
        # actually tightens, and the test asserts it rather than trusting it.
        permit[(o, (x, y, z))] = S.WINDOW / mag
    byord = {r[0]: r for r in recs}
    trip, exp, names, ords, rel, slack, dropped = [], [], [], [], [], [], []
    for o in sorted(cand):
        if len(cand[o]) != 1:
            continue
        t = next(iter(cand[o]))
        r = resid[(o, t)]
        if r > maxrel:
            dropped.append((o, byord[o][4], r, t,
                            struct.unpack("<Q", byord[o][1])[0]))
            continue
        trip.append(t)
        exp.append(struct.unpack("<Q", byord[o][1])[0])
        names.append(byord[o][4])
        ords.append(o)
        rel.append(r)
        slack.append(permit[(o, t)])
    return Oracle(K, trip, exp, names, ords, rel, slack, len(recs), len(trip),
                  sum(1 for o in cand if len(cand[o]) != 1), dropped, maxrel)


def score(vals, exp):
    return sum(1 for a, b in zip(vals, exp) if a == b)


# -------------------------------------------------------------- the artifact

HDR_FIELDS = ("one0 one1 cwambient cwsaved cwentered cwbeforeiso cwafteriso "
              "top fflg nstar nbat sentinel r12 r13 r14 r15").split()
HDR = len(HDR_FIELDS)
SENTINEL = 0x0DEFACED


def read_out(blob):
    """(header dict, [battery][star] -> u64) from the probe's output file."""
    u = struct.unpack("<%dI" % (len(blob) // 4), blob)
    h = dict(zip(HDR_FIELDS, u[:HDR]))
    bats = []
    n, nb = h["nstar"], h["nbat"]
    for b in range(nb):
        base = HDR + b * n * 2
        bats.append([(u[base + 2 * i + 1] << 32) | u[base + 2 * i]
                     for i in range(n)])
    return h, bats
