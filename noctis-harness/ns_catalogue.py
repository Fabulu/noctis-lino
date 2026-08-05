"""ns_catalogue.py -- grade the Wave 4 model against STARMAP.BIN.

STARMAP.BIN was written by the shipped 1996 executable, by real players, over
about twenty years.  Nothing in this repository produced it, tuned anything
against it, or can change it.  That is what makes it worth grading against,
and it is why every leg below recomputes both sides from the galaxy hash and
the file every run -- nothing is compared to a stored expectation.

WHAT IS IN A RECORD.  32 bytes: a binary64 id at +0, a 20-byte name at +8,
a space at +28, 'S' or 'P' at +29, and two ASCII digits at +30..31.  For a
'P' record those digits are the body index.  For an 'S' record they are the
STAR CLASS, and here is the provenance of that claim, which matters because
this file leans on it hard:

    NOCTIS.CPP:1244   ap_target_id = x/100000*y/100000*z/100000;
    NOCTIS.CPP:1257   srand (ap_target_id);
                      sprintf (star_label+21, "S%02d", random (star_classes));

star_label is the 24 bytes written at record offset +8, so star_label[21] is
record offset +29 -- the 'S' -- and [22..23] are the two digits.  The tag is
literally `random(12)` seeded from the identity.  All 7,579 'S' records carry
a tail in 00..11 and no other value appears, which is the arithmetic the
model has to reproduce.

THE SIX LEGS

  CLASS      srand(chop(identity)); random(12) must equal the 'S' tail.
             Scored under every plausible float-to-int rule, because the
             records where they disagree are exactly the evidence about the
             cast boundary that FLOATPOLICY.md leaves open.  Note the two
             sites chop DIFFERENT things: extract_ap_target_infos
             (NOCTIS-0.CPP:3970) chops a live extended value, while the
             label path above stores into a double first.  The catalogue can
             only speak about the label path, and this file says so.
             Negative control: permute the labels across records.

  SEED       nop = random(class_planets[class]+1) after srand(seed).  On
             class-2 and class-7 systems phase E is skipped entirely, so
             nob == nop exactly, and the highest charted body index is a
             hard upper bound on nop.  Four spellings of the seed are scored
             against a live random-seed control.

  NOB        the same bound with the full model, every class.

  CLASS6     class_planets[6] == 0, so a class-6 star has no planets and no
             body a player could ever have named.  Any named planet under a
             class-6 star refutes the model outright.

  IDENTITY   the computed identity must be BIT-IDENTICAL to the double the
             catalogue stores.  Scored under the Wave-3 extended schedule,
             under binary64, under the three-quotients regrouping and under
             isthere()'s different formula.

  PLUSN      NOCTIS.CPP:1263 writes a planet's id as id + ip + 1 (two adds);
             NOCTIS-0.CPP:4367 looks it up as id + n (one add).  They can
             differ in the last bit.  Both are scored against the stored 'P'
             doubles so the answer is measured rather than argued.

Usage:  python ns_catalogue.py [--box dl|cK] [--trials N] [--quick]
"""

import os
import random as pyrandom
import struct
import sys
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS = os.path.join(os.path.dirname(HERE), "tests")
for p in (HERE, TESTS):
    if p not in sys.path:
        sys.path.insert(0, p)

import ns_corpus as C                                           # noqa: E402
import ns_spec as N                                             # noqa: E402
import starmapspec as S                                         # noqa: E402
from brtl_oracle import Brtl                                    # noqa: E402

M16 = 0xFFFF
M32 = 0xFFFFFFFF

# NOCTIS.CPP:1230.  update_star_label() copies this over star_label when
# search_id_code finds no name, and THEN sprintf's the class tag over its
# last three bytes.  A catalogue record still carrying it was not written by
# a player naming a star, so its label field is not evidence about anything.
# There is exactly ONE such record in the DL-box corpus and the count is
# printed every run, so this exclusion cannot quietly grow to cover a real
# failure.
NO_LABEL = "UNKNOWN STAR / CLASS"


# ------------------------------------------------------- the float rules

def chop_modes(x, y, z):
    """srand's argument under every plausible float-to-int rule.

    'ext'   chop the live extended value          (NOCTIS-0.CPP:3970)
    'f64'   round to binary64 first, then chop    (NOCTIS.CPP:1244 + :1257)
    'floor' / 'ceil' / 'near'  the three rules a port might reach for by
            mistake.  They are here as discriminators: they agree with chop
            on positive and negative values in different places, and the
            records where they disagree are the whole evidence.
    """
    ext = N.identity_ext(x, y, z)
    d64 = Fraction(N.to_f64(ext)[0])
    out = {}
    out["ext"] = int(ext)
    out["f64"] = int(d64)
    out["floor"] = ext.numerator // ext.denominator
    out["ceil"] = -((-ext.numerator) // ext.denominator)
    q, r = divmod(ext.numerator, ext.denominator)
    if 2 * r > ext.denominator or (2 * r == ext.denominator and (q & 1)):
        q += 1
    out["near"] = q
    return {k: v & M16 for k, v in out.items()}


def identity_modes(x, y, z):
    """The stored 64-bit pattern under each reading of NOCTIS-0.CPP:4078."""
    out = {}
    out["ext"] = N.to_f64(N.identity_ext(x, y, z))[1]

    def bits(v):
        return struct.unpack("<Q", struct.pack("<d", v))[0]

    # every operation rounded to binary64 -- a compiler that spills
    out["f64"] = bits(((float(x) / 100000 * float(y)) / 100000 * float(z)) / 100000)
    # the three-quotients regrouping, the natural misreading
    out["quot64"] = bits((float(x) / 100000) * (float(y) / 100000) *
                         (float(z) / 100000))
    # the same regrouping done in extended
    v = Fraction(int(x), 100000)
    v = N._round_sig(v, 64)
    w = N._round_sig(Fraction(int(y), 100000), 64)
    u = N._round_sig(Fraction(int(z), 100000), 64)
    out["quotext"] = N.to_f64(N._round_sig(N._round_sig(v * w, 64) * u, 64))[1]
    # isthere()'s formula, which is a real formula in the game and is NOT the
    # one that wrote the catalogue.  It must score far below the real one; a
    # grader that scores it near 100% is measuring "did a number come out".
    out["isthere"] = bits((float(x) * 1e-5) * ((float(y) * 1e-5) *
                                               (float(z) * 1e-5)))
    # 1e-5 reaches the x87 as an 8-byte double literal, so it is the BINARY64
    # 1e-5 widened, not the extended-rounded one.  fpspec.py's K1EM5_BITS
    # makes the same point.
    k = Fraction(1e-5)
    a = N._round_sig(Fraction(int(x)) * k, 64)
    b = N._round_sig(Fraction(int(y)) * k, 64)
    c = N._round_sig(Fraction(int(z)) * k, 64)
    out["isthere_ext"] = N.to_f64(N._round_sig(a * N._round_sig(b * c, 64), 64))[1]
    return out


# ------------------------------------------------------- the seed spellings

def _crem(a, b):
    q = abs(a) // abs(b)
    q = -q if (a < 0) != (b < 0) else q
    return a - q * b


def _i32(v):
    v &= M32
    return v - 0x100000000 if v & 0x80000000 else v


def seed_spellings(x, y, z):
    x, y, z = int(x), int(y), int(z)
    out = {}
    # the source: *, / and % share a precedence level, left to right
    t = _crem(x, 10000)
    t = _crem(_i32(t * y), 10000)
    t = _crem(_i32(t * z), 10000)
    out["ltr"] = t & M16
    # the natural misreading: a flat product of three remainders
    out["three"] = _i32(_i32(_crem(x, 10000) * _crem(y, 10000)) *
                        _crem(z, 10000)) & M16
    # left to right, but with x and z swapped
    t = _crem(z, 10000)
    t = _crem(_i32(t * y), 10000)
    t = _crem(_i32(t * x), 10000)
    out["swap"] = t & M16
    # no modulus at all
    out["nomod"] = _i32(_i32(x * y) * z) & M16
    return out


def nop_for(seed, cls):
    g = Brtl()
    g.srand(seed & M16)
    return g.random(N.i16(N.CLASS_PLANETS[cls] + 1))


# =========================================================================


def run(box="dl", trials=30, quick=False, verbose=True):
    corpus = C.build(box)
    rows = corpus.rows
    if quick:
        rows = rows[:400]
    out = {}

    P = (lambda *a: print(*a)) if verbose else (lambda *a: None)

    P("corpus: %d single-candidate star records from box %r "
      "(%d discarded for multiple candidates)"
      % (len(rows), box, corpus.stats["multi_candidate_records"]))
    P("        %d of them carry at least one charted planet record"
      % sum(1 for r in rows if r[6]))
    P("")

    # ------------------------------------------------------------ CLASS
    P("=== CLASS  srand(chop(identity)); random(12) == the 'S' tail ===")
    modes = ("ext", "f64", "floor", "ceil", "near")
    hit = dict((m, 0) for m in modes)
    tot = 0
    placeholders = 0
    real_miss = []
    disagree = 0          # ext vs f64: the only pair the wave has to choose
                          # between.  floor/ceil differ from chop on every
                          # non-integer, so counting THAT would say nothing.
    percls_hit, percls_tot = {}, {}
    seeds_cache = []
    for (_rec, x, y, z, _nm, tag, _b) in rows:
        if tag < 0:
            continue
        if _nm.startswith(NO_LABEL):
            placeholders += 1
            continue
        tot += 1
        ch = chop_modes(x, y, z)
        seeds_cache.append((x, y, z, tag, ch))
        if ch["ext"] != ch["f64"]:
            disagree += 1
        for m in modes:
            g = Brtl()
            g.srand(ch[m])
            v = g.random(N.i16(N.STAR_CLASSES))
            if v == tag:
                hit[m] += 1
                if m == "ext":
                    percls_hit[tag] = percls_hit.get(tag, 0) + 1
            elif m == "ext":
                real_miss.append((_rec, _nm, tag, v))
        percls_tot[tag] = percls_tot.get(tag, 0) + 1
    for m in modes:
        P("  %-6s %6d / %6d   %6.2f%%" % (m, hit[m], tot, 100.0 * hit[m] / tot))
    P("  excluded: %d record(s) still carrying the engine's own placeholder "
      "name %r" % (placeholders, NO_LABEL))
    for (rc, nm, tg, gv) in real_miss[:10]:
        P("  MISMATCH record %d %r: tail says %d, the model says %d"
          % (rc, nm, tg, gv))
    P("  records where chopping the LIVE EXTENDED value and chopping its")
    P("  binary64 rounding give different seeds: %d" % disagree)
    P("  -> the catalogue can rank chop against floor/ceil/near, but it")
    P("     cannot separate 'ext' from 'f64'. FLOATPOLICY.md 3.3's open")
    P("     question stays open, and this is the measurement of how much")
    P("     that costs on real data rather than a shrug.")
    out["class"] = (hit, tot, disagree)
    out["class_miss"] = real_miss
    out["class_placeholders"] = placeholders

    # negative control: permute the labels
    tags = [t for (_r, _x, _y, _z, _n, t, _b) in rows if t >= 0]
    rng = pyrandom.Random(20260805)
    perm = tags[:]
    rng.shuffle(perm)
    ctl = 0
    for (x, y, z, _tag, ch), t in zip(seeds_cache, perm):
        g = Brtl()
        g.srand(ch["ext"])
        if g.random(N.i16(N.STAR_CLASSES)) == t:
            ctl += 1
    P("  CONTROL, labels permuted across records: %d / %d  %.2f%%"
      " (a grader with no power scores about 1/12 = 8.3%%)"
      % (ctl, tot, 100.0 * ctl / tot))
    out["class_control"] = ctl
    P("")

    # --------------------------------------------------------- IDENTITY
    P("=== IDENTITY  computed bits == the stored double, exactly ===")
    blob = open(S.CATALOGUE, "rb").read()
    imodes = ("ext", "f64", "quot64", "quotext", "isthere", "isthere_ext")
    ihit = dict((m, 0) for m in imodes)
    itot = 0
    for (rec, x, y, z, _nm, _tag, _b) in rows:
        stored = struct.unpack_from("<Q", blob, 4 + 32 * rec)[0]
        got = identity_modes(x, y, z)
        itot += 1
        for m in imodes:
            if got[m] == stored:
                ihit[m] += 1
    for m in imodes:
        P("  %-11s %6d / %6d   %6.2f%%"
          % (m, ihit[m], itot, 100.0 * ihit[m] / itot))
    out["identity"] = (ihit, itot)
    if ihit["quotext"] == ihit["ext"] == itot:
        P("  NOTE, and it corrects the wave plan: the three-quotients")
        P("  REGROUPING is not refuted here.  At 64-bit precision it rounds")
        P("  to the same binary64 as the source's left-to-right chain on")
        P("  every record in the corpus -- the eleven guard bits swallow the")
        P("  difference.  What this leg actually discriminates is EXTENDED")
        P("  vs BINARY64 (100% vs ~53%), which is Wave 3's claim, plus")
        P("  isthere()'s genuinely different formula (0%). A port that")
        P("  regroups the identity is NOT caught by the catalogue.")
    P("")

    # ------------------------------------------------------------- SEED
    # Isolated on purpose: the class comes from the catalogue tag, not from
    # the model, so the only thing under test here is the seed expression.
    P("=== SEED  nop bound on class-2 and class-7 systems (nob == nop) ===")
    sub = [r for r in rows if r[5] in (2, 7) and r[6]]
    P("  systems: %d class-2/7 with at least one charted body" % len(sub))
    spellings = ("ltr", "three", "swap", "nomod")
    ref = dict((s, 0) for s in spellings)
    exact = 0
    for (_rec, x, y, z, _nm, tag, bodies) in sub:
        mx = max(bodies)
        sp = seed_spellings(x, y, z)
        for s in spellings:
            if nop_for(sp[s], tag) < mx:
                ref[s] += 1
        if nop_for(sp["ltr"], tag) == mx:
            exact += 1
    for s in spellings:
        P("  %-6s refuted on %4d of %4d systems" % (s, ref[s], len(sub)))
    P("  ltr pins nop EXACTLY (max index == nop) on %d of %d" % (exact, len(sub)))
    lo, hi, tot_t = 10 ** 9, -1, 0
    for _t in range(trials):
        bad = 0
        for (_rec, _x, _y, _z, _nm, tag, bodies) in sub:
            if nop_for(rng.randrange(65536), tag) < max(bodies):
                bad += 1
        lo, hi, tot_t = min(lo, bad), max(hi, bad), tot_t + bad
    P("  CONTROL, a random 16-bit seed, %d trials: min %d, mean %.1f, max %d"
      % (trials, lo, tot_t / float(trials), hi))
    out["seed"] = (ref, len(sub), exact, (lo, tot_t / float(max(trials, 1)), hi))
    P("")

    # -------------------------------------------------------------- NOB
    # The full model end to end: its own class, its own seed, its own moons.
    P("=== NOB  every charted body index must exist in the model ===")
    viol = 0
    n_with = 0
    pinned = 0
    clsmis = 0
    for (_rec, x, y, z, _nm, tag, bodies) in rows:
        if not bodies:
            continue
        n_with += 1
        s = N.System(x, y, z)
        if tag >= 0 and s.cls != tag and not _nm.startswith(NO_LABEL):
            clsmis += 1
        mx = max(bodies)
        if mx > s.nob:
            viol += 1
        elif mx == s.nob:
            pinned += 1
    P("  systems with charted bodies: %d" % n_with)
    P("  charted index above the model's nob: %d  (must be 0)" % viol)
    P("  charted index lands EXACTLY on nob: %d" % pinned)
    P("  model class disagrees with the 'S' tail: %d" % clsmis)
    out["nob"] = (viol, n_with, pinned, clsmis)
    P("")

    # ----------------------------------------------------------- CLASS6
    P("=== CLASS6  class_planets[6] == 0, so no class-6 star has a planet ===")
    c6 = [r for r in rows if r[5] == 6]
    c6named = [r for r in c6 if r[6]]
    c6model = 0
    for (_rec, x, y, z, _nm, _tag, _b) in c6[:600]:
        if N.System(x, y, z).nop:
            c6model += 1
    P("  catalogued class-6 stars in the corpus: %d" % len(c6))
    P("  of those, carrying a named planet record: %d  (must be 0)"
      % len(c6named))
    P("  model produces a planet for: %d of %d sampled  (must be 0)"
      % (c6model, min(600, len(c6))))
    out["class6"] = (len(c6), len(c6named), c6model)
    P("")

    # ------------------------------------------------------------ PLUSN
    P("=== PLUSN  id+ip+1 (naming, two adds) vs id+n (phase H, one add) ===")
    _stars, planets, _cn = C.catalogue_records()
    pby = {}
    for (i, n, _nm, idx) in planets:
        pby.setdefault(n - idx * C.SCALE, []).append((i, idx))
    keys = sorted(pby)
    import bisect
    a_hit = b_hit = e_hit = ptot = 0
    diff = 0
    for (_rec, x, y, z, _nm, _tag, _b) in rows:
        Pv = int(x) * int(y) * int(z)
        j = bisect.bisect_left(keys, Pv - C.WINDOW + 1)
        got = []
        while j < len(keys) and keys[j] - Pv < C.WINDOW:
            got.extend(pby[keys[j]])
            j += 1
        if not got:
            continue
        ident = N.to_f64(N.identity_ext(x, y, z))[0]
        # nearstar_identity is a DOUBLE variable, so the naming path reloads
        # the stored binary64; the extended chain does not reach this far.
        identq = Fraction(ident)
        for (i, m) in got:
            stored = struct.unpack_from("<Q", blob, 4 + 32 * i)[0]
            ptot += 1
            a = struct.unpack("<Q", struct.pack("<d", (ident + (m - 1)) + 1))[0]
            b = struct.unpack("<Q", struct.pack("<d", ident + m))[0]
            e = N.to_f64(N._round_sig(N._round_sig(identq + (m - 1), 64) + 1, 64))[1]
            a_hit += (a == stored)
            b_hit += (b == stored)
            e_hit += (e == stored)
            diff += (a != b)
    P("  charted planet records under a corpus star: %d" % ptot)
    P("  fl(fl(id+ip)+1) matches the stored double: %d  %.2f%%"
      % (a_hit, 100.0 * a_hit / max(ptot, 1)))
    P("  fl(id+n)         matches the stored double: %d  %.2f%%"
      % (b_hit, 100.0 * b_hit / max(ptot, 1)))
    P("  ext(ext(id+ip)+1) rounded once            : %d  %.2f%%"
      % (e_hit, 100.0 * e_hit / max(ptot, 1)))
    P("  records where the first two disagree in the last bit: %d" % diff)
    P("  (all three sit far inside search_id_code's 1e-5 window, so phase H's")
    P("   COUNT is unaffected either way; this leg settles which value the")
    P("   port must WRITE when the player names a body.)")
    out["plusn"] = (ptot, a_hit, b_hit, e_hit, diff)
    return out


def verdict(out):
    """The pass/fail reading of run()'s numbers."""
    bad = []
    hit, tot, _dis = out["class"]
    if out["class_miss"]:
        bad.append("CLASS: %d player-named records disagree with the model, "
                   "first %r" % (len(out["class_miss"]), out["class_miss"][0]))
    for m in ("floor", "ceil", "near"):
        if hit[m] >= hit["ext"]:
            bad.append("CLASS: rounding rule %r scores as well as chop "
                       "(%d vs %d) -- the leg has no discriminating power"
                       % (m, hit[m], hit["ext"]))
    if out["class_control"] > 0.25 * tot:
        bad.append("CLASS control scored %d/%d -- the leg has lost its power"
                   % (out["class_control"], tot))
    ihit, itot = out["identity"]
    if ihit["ext"] < itot:
        bad.append("IDENTITY: the extended schedule is not bit-exact "
                   "(%d/%d)" % (ihit["ext"], itot))
    # quotext is DELIBERATELY absent from this list.  Measured below: at
    # 64-bit precision the three-quotients regrouping and the source's
    # left-to-right chain round to the SAME binary64 on every record in the
    # corpus, so the catalogue cannot tell them apart and it would be a lie
    # to have this leg claim it does.  See the exit note in run().
    for m in ("isthere", "isthere_ext", "f64", "quot64"):
        if ihit[m] > 0.90 * itot:
            bad.append("IDENTITY: the %r reading scored %d/%d; this grader is "
                       "measuring 'did a number come out', not arithmetic"
                       % (m, ihit[m], itot))
    ref, nsub, _ex, ctl = out["seed"]
    if ref["ltr"] != 0:
        bad.append("SEED: the left-to-right spelling is refuted %d times"
                   % ref["ltr"])
    for s in ("three", "swap", "nomod"):
        if ref[s] == 0:
            bad.append("SEED: misreading %r is not refuted at all -- the leg "
                       "has no discriminating power" % s)
    if ctl[0] == 0:
        bad.append("SEED: the random-seed control was never refuted")
    viol, _nw, _pin, clsmis = out["nob"]
    if viol:
        bad.append("NOB: %d systems have a charted body the model never "
                   "generates" % viol)
    if clsmis:
        bad.append("NOB: the model's class disagrees with the catalogue tail "
                   "on %d systems" % clsmis)
    _n6, named6, model6 = out["class6"]
    if named6 or model6:
        bad.append("CLASS6: %d catalogued and %d modelled planets around "
                   "class-6 stars" % (named6, model6))
    return bad


def main(argv):
    box, trials, quick = "dl", 30, False
    i = 0
    while i < len(argv):
        if argv[i] == "--box":
            box = argv[i + 1]; i += 1
        elif argv[i] == "--trials":
            trials = int(argv[i + 1]); i += 1
        elif argv[i] == "--quick":
            quick = True
        i += 1
    out = run(box=box, trials=trials, quick=quick)
    bad = verdict(out)
    print("")
    if bad:
        print("CATALOGUE: FAIL")
        for b in bad:
            print("  " + b)
        return 1
    print("CATALOGUE: PASS -- every leg met its criterion and every control "
          "kept its power")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
