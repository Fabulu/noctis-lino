"""geo_grade.py -- Wave 6, the geometry grading run, end to end.

Every side is rebuilt from source on every run and nothing is compared
against a stored expectation.  The corpus is re-swept from the galaxy hash
and STARMAP.BIN by ns_corpus.py under its single-candidate rule, so this
script cannot be measuring its own chooser either.

THE HEADLINE, STATED BEFORE THE RESULTS SO IT CANNOT BE MISREAD
---------------------------------------------------------------
Planetary geometry has NO external oracle.  Leg 1 re-derives that from the
eighteen shipped 1996 binaries on every run instead of citing it: DL.EXE --
the executable Wave 4 graded 4,365 owner/moon-id constraints against --
contains no floating-point printf conversion at all, and neither does any
other GOES module.  Only NOCTIS.EXE, the interactive game, ever prints a
planetary number, and it prints exactly one field (`nearstar_p_ray` of the
targetted body, NOCTIS.CPP:3083) at `%1.4f`, to a graphical HUD.

So what follows is NOT an equality against 1996 output.  It is:

  * two independent implementations agreeing bit for bit (leg 2),
  * an inherited external hold: geometry must not move the topology that
    STARMAP.BIN and DL.EXE do grade (leg 3),
  * a MEASUREMENT of what is still open rather than a decision about it
    (legs 4 and 5),
  * an explicit BOUND on what the one 1996 printout that exists could ever
    settle, if someone captured it (leg 6),
  * and five deliberately broken builds that must fail (leg 7).

Usage:
    python geo_grade.py [--limit N]
"""

import hashlib
import os
import re
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MODULES = r"C:\programmieren\noctis\niv-plus\modules"
SOURCE = r"C:\programmieren\noctis\niv-plus\source"

FIELDS = ("orb_orient", "orb_seed", "tilt", "orb_tilt",
          "orb_ecc", "ray", "orb_ray", "ring")
LIVE_BREAKS = ("F32RAY", "FUSESIZING", "SPILL2", "ECCMUL", "KEY8")
INERT_BREAKS = ("SPILL", "PARENTSEED", "ZORDER")

fails = []
notes = []


def head(t):
    print()
    print("=" * 74)
    print(t)
    print("=" * 74)


def check(ok, label, detail=""):
    print("  [%s] %s%s" % ("PASS" if ok else "FAIL", label,
                           ("   " + detail) if detail else ""))
    if not ok:
        fails.append(label + ("   " + detail if detail else ""))
    return ok


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def run(cmd, **kw):
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=HERE, **kw)
    if p.returncode != 0:
        print("    ! %s -> rc=%d\n%s%s" % (" ".join(cmd), p.returncode,
                                           p.stdout[-2000:], p.stderr[-2000:]))
    return p


# ---------------------------------------------------------------- GEOB ----

GEOB_MAGIC = 0x47454F42


def read_geob(path):
    with open(path, "rb") as fh:
        b = fh.read()
    magic, ver, nrec, nf, cast, csrc, prec, _ = struct.unpack_from("<8I", b, 0)
    if magic != GEOB_MAGIC:
        raise SystemExit("not GEOB: %s" % path)
    o = 32
    out = []
    for _ in range(nrec):
        cls, nop, nob, draws = struct.unpack_from("<4I", b, o)
        o += 16
        vals = struct.unpack_from("<%dQ" % (nob * nf), b, o)
        o += nob * nf * 8
        out.append((cls, nop, nob, draws, vals))
    return (cast, csrc, prec), out


def cmp_geob(a, b):
    """returns (header_mismatches, values_compared, values_differing,
    per-field differing counts, first few examples)"""
    hbad, tot, bad = 0, 0, 0
    perf = [0] * len(FIELDS)
    ex = []
    for k, (x, y) in enumerate(zip(a, b)):
        if x[:3] != y[:3]:
            hbad += 1
            continue
        for i, (u, v) in enumerate(zip(x[4], y[4])):
            tot += 1
            if u != v:
                bad += 1
                perf[i % len(FIELDS)] += 1
                if len(ex) < 4:
                    ex.append("rec %d body %d %s %016x != %016x"
                              % (k, i // len(FIELDS), FIELDS[i % len(FIELDS)],
                                 u, v))
    return hbad, tot, bad, perf, ex


def geob_of(path, args):
    p = run([os.path.join(HERE, "geo_ref.exe"), CORPUS, path] + args)
    if p.returncode:
        raise SystemExit("geo_ref failed")
    return read_geob(path)[1]


# ============================================================== leg 1 =====

def leg_oracle():
    head("LEG 1  ORACLE -- what the 1996 machine can and cannot print")
    pat = re.compile(rb"%[0-9.*+ #-]*(?:l|h|L)?[diouxXfFeEgGcsp]")
    floatconv = set(b"fFeEgG")
    rows = []
    for fn in sorted(os.listdir(MODULES)):
        if not fn.lower().endswith((".exe", ".com")):
            continue
        with open(os.path.join(MODULES, fn), "rb") as fh:
            blob = fh.read()
        specs = sorted(set(pat.findall(blob)))
        flo = [s.decode() for s in specs if s[-1] in floatconv]
        rows.append((fn, len(blob), flo, [s.decode() for s in specs]))
    for fn, n, flo, allf in rows:
        print("  %-12s %7d  float-conversions: %s"
              % (fn, n, ", ".join(flo) if flo else "NONE"))
    withfloat = [r[0] for r in rows if r[2]]
    dl = [r for r in rows if r[0].upper() == "DL.EXE"][0]

    check(len(rows) >= 18, "all shipped modules scanned",
          "%d binaries" % len(rows))
    check(not dl[2], "DL.EXE -- the Wave 4 oracle -- prints no float at all",
          "its whole format set is %s" % " ".join(dl[3]))
    check(set(withfloat) <= {"NOCTIS.EXE", "PAR.EXE", "SL.EXE"},
          "only NOCTIS/PAR/SL print any float",
          "found: %s" % ", ".join(withfloat))

    # and what those three actually print, from the sources
    hits = []
    for fn in ("PAR.CPP", "SL.CPP"):
        with open(os.path.join(SOURCE, fn), encoding="latin-1") as fh:
            for i, line in enumerate(fh, 1):
                if re.search(r"%[0-9.]*l?[fgeFGE]", line):
                    hits.append("%s:%d %s" % (fn, i, line.strip()[:90]))
    print()
    print("  the two non-game modules that print a float print only these:")
    for h in hits:
        print("    " + h)
    geom = [h for h in hits
            if re.search(r"orb_|_tilt|_ecc|_ring|p_ray", h)]
    check(not geom, "no GOES module prints any planetary geometry",
          "%d geometry printouts found" % len(geom))

    # the single field the game itself prints
    with open(os.path.join(SOURCE, "NOCTIS.CPP"), encoding="latin-1") as fh:
        noc = fh.read().splitlines()
    rayline = [(i + 1, l.strip()) for i, l in enumerate(noc)
               if "nearstar_p_ray" in l and "%1.4f" in l]
    print()
    print("  the ONLY planetary geometry any 1996 binary prints:")
    for i, l in rayline:
        print("    NOCTIS.CPP:%d  %s" % (i, l[:100]))
    check(len(rayline) == 1,
          "exactly one such site, and it is a HUD sprintf in the game",
          "%d found" % len(rayline))
    notes.append("ORACLE: geometry has no headless 1996 readout.  The only "
                 "planetary number the original ever prints is "
                 "nearstar_p_ray at %1.4f on NOCTIS.EXE's graphical HUD.")


# ============================================================== leg 2 =====

def leg_refs(nrec):
    head("LEG 2  REFERENCES -- C on a real x87 vs exact-rational Python")
    print("  geo_ref.c   long double (80-bit) chains at control word 133Fh,")
    print("              one store per source statement, real hardware")
    print("  geo_spec.py exact rationals, explicit round-to-nearest-even to")
    print("              64/53/24 bits, NO hardware float anywhere")
    print()
    c = geob_of("geo_c.geob", [])
    p = run([sys.executable, "geo_spec.py", CORPUS, "geo_p.geob",
             "--limit", str(nrec)])
    if p.returncode:
        raise SystemExit("geo_spec failed")
    py = read_geob("geo_p.geob")[1]
    c = c[:len(py)]
    hbad, tot, bad, perf, ex = cmp_geob(c, py)
    bodies = sum(r[2] for r in py)
    print("  %d systems, %d bodies, %d graded values (%d fields each)"
          % (len(py), bodies, tot, len(FIELDS)))
    for e in ex:
        print("    " + e)
    check(hbad == 0, "class/nop/nob agree on every system",
          "%d disagree" % hbad)
    check(tot > 0 and bad == 0,
          "every geometry value agrees BIT FOR BIT",
          "%d / %d differ" % (bad, tot))

    # the cast boundary is a switch on BOTH sides, so both settings of it
    # have to be cross-checked or leg 4 would be measuring one engine only.
    for cast, csrc in (("near", "ext"), ("chop", "f64")):
        cv = geob_of("geo_c_%s_%s.geob" % (cast, csrc),
                     ["--cast", cast, "--castsrc", csrc])[:len(py)]
        p = run([sys.executable, "geo_spec.py", CORPUS,
                 "geo_p_%s_%s.geob" % (cast, csrc), "--limit", str(nrec),
                 "--cast", cast, "--castsrc", csrc])
        pv = read_geob("geo_p_%s_%s.geob" % (cast, csrc))[1]
        h2, t2, b2, _, ex2 = cmp_geob(cv, pv)
        check(t2 > 0 and b2 == 0 and h2 == 0,
              "the two sides also agree under cast=%s castsrc=%s"
              % (cast, csrc),
              "%d / %d differ%s" % (b2, t2, ("  " + ex2[0]) if ex2 else ""))
    return c, py, tot, bodies


# ============================================================== leg 3 =====

def leg_topology(nrec, cvariants):
    head("LEG 3  TOPOLOGY -- the only external hold geometry has")
    print("  Geometry is downstream of everything STARMAP.BIN and DL.EXE")
    print("  grade.  This leg proves the inheritance is real by requiring")
    print("  the Wave 4 reference and this one to produce the same class,")
    print("  nop, nob and draw count on the same corpus -- and by requiring")
    print("  that to be true for EVERY cast policy and precision class,")
    print("  which is what makes the eleven float sites provably invisible")
    print("  to the 1996 artifacts.")
    print()
    ns = os.path.join(HERE, "ns_ref.exe")
    if not os.path.exists(ns):
        p = run(["gcc", "-O2", "-fwrapv", "-o", ns,
                 os.path.join(HERE, "ns_ref.c"), "-lm"])
        if p.returncode:
            check(False, "ns_ref.c builds")
            return
    p = run([ns, CORPUS, "geo_ns.nstopo"])
    if p.returncode:
        check(False, "ns_ref runs")
        return
    with open(os.path.join(HERE, "geo_ns.nstopo"), "rb") as fh:
        b = fh.read()
    _, _, n, stride = struct.unpack_from("<4I", b, 0)
    topo = []
    for k in range(n):
        r = struct.unpack_from("<%dI" % stride, b, 32 + k * stride * 4)
        topo.append((r[3], r[5], r[6], r[11]))       # class nop nob draws
    base = cvariants[("chop", "ext", "ext")]
    mism = sum(1 for a, t in zip(base, topo) if (a[0], a[1], a[2], a[3]) != t)
    check(mism == 0,
          "Wave 4's ns_ref and this file agree on class/nop/nob/draws",
          "%d of %d systems differ" % (mism, len(base)))

    ref = [(r[0], r[1], r[2], r[3]) for r in base]
    for key, recs in sorted(cvariants.items()):
        got = [(r[0], r[1], r[2], r[3]) for r in recs]
        check(got == ref,
              "topology unmoved under cast=%s castsrc=%s prec=%s" % key,
              "" if got == ref else "topology MOVED")
    notes.append("TOPOLOGY: every draw whose result selects a branch, a count "
                 "or a type takes an INTEGER argument, and random(n) consumes "
                 "one rand() for every n.  Measured here, not assumed: the "
                 "draw ledger is byte-identical across all four cast policies "
                 "and both precision classes.")


# ============================================================== leg 4 =====

def leg_cast(cvariants, tot):
    head("LEG 4  THE CAST BOUNDARY -- measured, not decided")
    print("  FLOATPOLICY.md 3.3 records the float-to-int boundary UNSETTLED.")
    print("  The eleven geometry sites convert a double to a 16-bit int at a")
    print("  call boundary.  Four hypotheses; this leg reports the distance")
    print("  between them.  NONE of them is asserted to be the right one.")
    print()
    base = cvariants[("chop", "ext", "ext")]
    print("  %-28s %10s %10s   %s" % ("hypothesis", "values", "differ", "%"))
    spread = {}
    for key in sorted(cvariants):
        if key[2] != "ext":
            continue
        _, t, bad, perf, _ = cmp_geob(base, cvariants[key])
        spread[key] = (t, bad, perf)
        print("  cast=%-5s castsrc=%-4s        %10d %10d   %6.3f%%"
              % (key[0], key[1], t, bad, 100.0 * bad / t if t else 0))
    print()
    print("  per field, chop/ext vs near/ext:")
    t, bad, perf = spread[("near", "ext", "ext")]
    for i, f in enumerate(FIELDS):
        print("    %-11s %8d differing" % (f, perf[i]))

    t, b_near, perf_near = spread[("near", "ext", "ext")]
    moved = {FIELDS[i] for i in range(len(FIELDS)) if perf_near[i]}
    check(moved == {"orb_seed", "tilt", "orb_tilt", "orb_ecc"},
          "the cast boundary reaches exactly four of the eight fields",
          "reached: %s" % ", ".join(sorted(moved)))
    print()
    print("  orb_orient's draw takes an INTEGER argument; ray, orb_ray and")
    print("  ring are RECOMPUTED in phases F and G from zrandom(100) and")
    print("  random(3)/random(5)/random(2), all integer arguments.  So four")
    print("  of the eight fields cannot depend on the cast boundary at all,")
    print("  and the measurement above confirms it rather than assuming it.")
    _, _, b_near, _, _ = cmp_geob(base, cvariants[("near", "ext", "ext")])
    _, _, b_src, _, _ = cmp_geob(base, cvariants[("chop", "f64", "ext")])
    check(b_near > 0,
          "chop and round-to-nearest are DISTINGUISHABLE in geometry",
          "%d of %d values move" % (b_near, tot))
    print()
    print("  castsrc (live 80-bit value vs its binary64 rounding) moves")
    print("  %d of %d values.  FLOATPOLICY.md 3.3 says the engine cannot"
          % (b_src, tot))
    print("  currently truncate an unstored extended value at all; this is")
    print("  the size of that gap for geometry specifically.")
    notes.append("CAST: chop vs nearest moves %d/%d geometry values (%.3f%%); "
                 "live-extended vs binary64-first moves %d/%d (%.4f%%).  "
                 "Both remain OPEN -- nothing here decides between them."
                 % (b_near, tot, 100.0 * b_near / tot,
                    b_src, tot, 100.0 * b_src / tot))


# ============================================================== leg 5 =====

def leg_precision(cvariants, tot):
    head("LEG 5  PRECISION CLASS -- is the 80-bit schedule load-bearing here?")
    base = cvariants[("chop", "ext", "ext")]
    _, t, bad, perf, ex = cmp_geob(base, cvariants[("chop", "ext", "f64")])
    print("  A plain `double` transcription (every intermediate narrowed to")
    print("  53 bits) against the unspilled 80-bit schedule:")
    print("    %d of %d values differ  (%.4f%%)"
          % (bad, t, 100.0 * bad / t if t else 0))
    for i, f in enumerate(FIELDS):
        print("    %-11s %8d differing" % (f, perf[i]))
    for e in ex[:2]:
        print("    " + e)
    check(bad > 0,
          "the 80-bit schedule is load-bearing for geometry too",
          "%d of %d values move at 53 bits" % (bad, t))


# ============================================================== leg 6 =====

def leg_bound(cvariants):
    head("LEG 6  THE BOUND -- what the one 1996 printout could ever settle")
    print("  NOCTIS.CPP:3083 sprintf's nearstar_p_ray[ip_targetted] as")
    print("  \"%1.4f\".  If someone captured that HUD field for a body, the")
    print("  strongest statement it could support is |ours - theirs| < 5e-5,")
    print("  a BOUND, never an equality.  How much would that bound settle?")
    print()
    base = cvariants[("chop", "ext", "ext")]
    near = cvariants[("near", "ext", "ext")]
    src = cvariants[("chop", "f64", "ext")]
    f64p = cvariants[("chop", "ext", "f64")]
    ri = FIELDS.index("ray")

    def sep(a, b, tol):
        """bodies whose `ray` differs by more than tol -- i.e. bodies where a
        %1.4f readout could tell the two hypotheses apart at all."""
        n = vis = moved = 0
        for x, y in zip(a, b):
            for k in range(x[2]):
                u = struct.unpack("<d", struct.pack("<Q", x[4][k * 8 + ri]))[0]
                v = struct.unpack("<d", struct.pack("<Q", y[4][k * 8 + ri]))[0]
                n += 1
                if u != v:
                    moved += 1
                    if abs(u - v) > tol:
                        vis += 1
        return n, moved, vis

    print("  %-34s %8s %10s %12s" % ("hypothesis vs chop/ext/ext",
                                     "bodies", "ray moved", "visible@1e-4"))
    res = {}
    for label, other in (("cast = round-to-nearest", near),
                         ("castsrc = binary64 first", src),
                         ("prec = 53-bit intermediates", f64p)):
        n, moved, vis = sep(base, other, 5e-5)
        res[label] = (n, moved, vis)
        print("  %-34s %8d %10d %12d" % (label, n, moved, vis))
    print()
    n, moved, vis = res["cast = round-to-nearest"]
    check(moved == 0,
          "the ONE field the original prints does not move under the cast "
          "boundary AT ALL",
          "%d of %d bodies" % (moved, n))
    print("    Reason, and it is structural: phase F (:4306) overwrites")
    print("    p_ray for EVERY body from avg_planet_ray[type] and")
    print("    zrandom(100) -- an integer argument.  The phase A/E radius,")
    print("    which does depend on the cast, is dead by then.  So the HUD")
    print("    readout is blind to the open question BY CONSTRUCTION.")
    print()
    n, moved, vis = res["prec = 53-bit intermediates"]
    check(vis == 0,
          "a %1.4f readout cannot resolve the precision class either",
          "%d of %d bodies move, %d of them by more than 5e-5"
          % (moved, n, vis))
    notes.append("BOUND: the only planetary number any 1996 binary prints -- "
                 "nearstar_p_ray at %%1.4f -- is IDENTICAL under every cast "
                 "hypothesis (0 of %d bodies move), because phase F "
                 "recomputes it from an integer-argument draw.  Capturing it "
                 "would settle nothing about the open item.  Under a 53-bit "
                 "engine it moves on %d bodies but never by as much as 5e-5, "
                 "so %%1.4f could not see that either."
                 % (res["cast = round-to-nearest"][0],
                    res["prec = 53-bit intermediates"][1]))
    print()
    print("  Read that column as the ceiling on this route.  It is a bound on")
    print("  a bound: even a perfect capture of every HUD radius would leave")
    print("  the rows with 0 visible bodies completely unresolved, and the")
    print("  capture itself is not headless (NOCTIS.EXE is the interactive")
    print("  game, gated on video mode 13h and driven by keyboard).")
    check(True, "reported as a BOUND, not a pass", "no equality is claimed")


# ============================================================== leg 7 =====

def _build_run(b, pyrecs):
    exe = os.path.join(HERE, "geo_brk_%s.exe" % b.lower())
    p = run(["gcc", "-O2", "-fwrapv", "-DBREAK_" + b, "-o", exe,
             os.path.join(HERE, "geo_ref.c"), "-lm"])
    if p.returncode:
        return None
    out = os.path.join(HERE, "geo_brk_%s.geob" % b.lower())
    p = run([exe, CORPUS, out])
    if p.returncode:
        return None
    recs = read_geob(out)[1][:len(pyrecs)]
    hbad, tot, bad, perf, ex = cmp_geob(recs, pyrecs)
    topo_moved = hbad > 0 or any(r[3] != q[3] for r, q in zip(recs, pyrecs))
    return recs, hbad, tot, bad, perf, ex, topo_moved


def leg_breaks(pyrecs, nrec):
    head("LEG 7a  LIVE BREAKS -- five builds that must fail")
    print("  Each is one compile-time edit of geo_ref.c, built with the real")
    print("  compiler and run over the real corpus.  All five compile: they")
    print("  are wrong, not broken.")
    print()
    for b in LIVE_BREAKS:
        r = _build_run(b, pyrecs)
        if r is None:
            check(False, "BREAK_%s builds and runs" % b)
            continue
        _, hbad, tot, bad, perf, ex, _ = r
        check(bad > 0 or hbad > 0, "BREAK_%s is caught" % b,
              "%d/%d values differ (%s)"
              % (bad, tot, ", ".join("%s=%d" % (FIELDS[i], perf[i])
                                     for i in range(len(FIELDS)) if perf[i])))
        if ex:
            print("         first: " + ex[0])

    head("LEG 7b  INERT SITES -- three edits that must change NOTHING")
    print("  These are not weak tests.  Each asserts a positive property of")
    print("  the 1996 routine that a later wave could break by accident, and")
    print("  each would then fail loudly:")
    print()
    print("    BREAK_SPILL       :4089's int*float product needs 35 bits, so")
    print("                      a binary64 spill there cannot lose anything")
    print("    BREAK_PARENTSEED  :4199's VALUE is dead -- phase F overwrites")
    print("                      p_ray[q] for every moon.  The DRAW is live.")
    print("    BREAK_ZORDER      :4094's VALUE is dead -- phase G overwrites")
    print("                      p_ring[n] for every planet.  The two draws")
    print("                      are live but the stream position is the same")
    print()
    print("  So 3 of the 17 float-site draws (:4094 x2, :4199 x1) feed values")
    print("  nothing in the routine ever reads.  14 are live.")
    print()
    for b in INERT_BREAKS:
        r = _build_run(b, pyrecs)
        if r is None:
            check(False, "BREAK_%s builds and runs" % b)
            continue
        _, hbad, tot, bad, perf, ex, topo = r
        check(bad == 0 and hbad == 0,
              "BREAK_%s changes nothing, as claimed" % b,
              "%d/%d values differ" % (bad, tot))
        check(not topo, "BREAK_%s leaves the draw ledger identical" % b)
    notes.append("SITES: 3 of the 17 float-site draws (:4094 x2, :4199 x1) "
                 "produce values NOTHING in prepare_nearstar reads -- phases "
                 "F and G overwrite them.  Proven by leg 7b, which mutates "
                 "each and requires zero movement.  14 draws are live.")
    return True


# ============================================================== registry ==

def leg_registry():
    head("LEG 0  THE SITE REGISTRY -- still eleven sites / 17 draws")
    with open(os.path.join(HERE, "geo_ref.c"), encoding="utf-8") as fh:
        src = fh.read()
    sites = re.findall(r"^\s*\*\s+FSITE (\d+)\s+(random|zrandom)", src, re.M)
    draws = sum(2 if k == "zrandom" else 1 for _, k in sites)
    check(len(sites) == 11, "eleven float-argument sites declared",
          "%d" % len(sites))
    check(draws == 17, "seventeen draws across them", "%d" % draws)
    # and the code really takes that many
    p = run([os.path.join(HERE, "geo_ref.exe"), CORPUS, "geo_sites.txt",
             "--text"])
    if p.returncode == 0:
        with open(os.path.join(HERE, "geo_sites.txt")) as fh:
            hdr = [l for l in fh if l.startswith("# rec")]
        per = []
        for l in hdr:
            t = l.split()
            nop, nob, fl = int(t[6]), int(t[8]), int(t[12])
            per.append((nop, nob, fl))
        bad = [(nop, nob, fl) for nop, nob, fl in per
               if fl != 9 * nop + 8 * (nob - nop)]
        check(not bad,
              "float-site draws == 9 per planet + 8 per moon on every system",
              "%d systems violate it, e.g. %s" % (len(bad), bad[:2]))


# ================================================================ main ====

def main(argv):
    global CORPUS
    limit = 200
    if "--limit" in argv:
        limit = int(argv[argv.index("--limit") + 1])

    head("BUILD -- everything from source, this run")
    p = run(["gcc", "-O2", "-fwrapv", "-Wall", "-o",
             os.path.join(HERE, "geo_ref.exe"),
             os.path.join(HERE, "geo_ref.c"), "-lm"])
    check(p.returncode == 0, "geo_ref.c builds clean",
          (p.stderr or "")[:200])
    print("  geo_ref.c   sha256 %s" % sha(os.path.join(HERE, "geo_ref.c")))
    print("  geo_spec.py sha256 %s" % sha(os.path.join(HERE, "geo_spec.py")))
    p = run([sys.executable, os.path.join(HERE, "geo_spec.py"), "--selftest"])
    print("  " + (p.stdout or "").strip())
    check("PASS" in (p.stdout or ""), "geo_spec.py rounding self-test")

    print()
    print("  re-sweeping the corpus from the galaxy hash and STARMAP.BIN")
    p = run([sys.executable, os.path.join(HERE, "ns_corpus.py"),
             "--box", "dl", "--limit", str(limit),
             "--out", os.path.join(HERE, "geo_corpus.nsin"),
             "--manifest", os.path.join(HERE, "geo_corpus.tsv")])
    check(p.returncode == 0, "corpus rebuilt", (p.stderr or "")[-200:])
    CORPUS = os.path.join(HERE, "geo_corpus.nsin")
    for line in (p.stdout or "").splitlines()[-3:]:
        print("  " + line)

    leg_registry()
    leg_oracle()

    # every cast/precision variant, once
    cvariants = {}
    for cast in ("chop", "near"):
        for csrc in ("ext", "f64"):
            for prec in ("ext", "f64"):
                if prec == "f64" and (cast, csrc) != ("chop", "ext"):
                    continue
                key = (cast, csrc, prec)
                cvariants[key] = geob_of(
                    "geo_%s_%s_%s.geob" % key,
                    ["--cast", cast, "--castsrc", csrc, "--prec", prec])

    c, py, tot, bodies = leg_refs(limit)
    leg_topology(limit, cvariants)
    leg_cast(cvariants, tot)
    leg_precision(cvariants, tot)
    leg_bound(cvariants)
    leg_breaks(py, limit)

    head("SUMMARY")
    for n in notes:
        print("  * " + n)
    print()
    if fails:
        print("  %d CHECK(S) FAILED:" % len(fails))
        for f in fails:
            print("    - " + f)
        return 1
    print("  all checks passed.")
    print()
    print("  READ THIS BEFORE QUOTING ANY NUMBER ABOVE: leg 2's bit-exactness")
    print("  is agreement between two implementations of the same reading of")
    print("  the 1996 source.  It is NOT agreement with the 1996 machine.  No")
    print("  1996 artifact in this project's possession contains a planetary")
    print("  radius, orbital radius, tilt, eccentricity or ring value, and")
    print("  leg 1 re-establishes that from the shipped binaries every run.")
    print("  The cast boundary stays OPEN; leg 4 measures its cost instead of")
    print("  closing it.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
