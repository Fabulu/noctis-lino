"""ns_mkbreak.py -- sabotage the reference and require the graders to notice.

A test that has never failed has never been shown to work.  This file makes
a deliberately broken ns_ref.c for each way the wave could plausibly get the
draw accounting wrong, runs the whole grading stack against it, and reports:

    where it first fails   which check class caught it (DRAW-COUNT names the
                           phase, TOPOLOGY means the counts were right and a
                           branch value was wrong, CATALOGUE/DL means only an
                           external oracle saw it)
    how hard it fails      the fraction of systems whose topology moved, and
                           the DL reproduction rate

The second number is the point.  "The mutant fails" is nearly worthless on
its own -- a mutant that fails for the wrong reason is a test that has
stopped measuring.  Recon A published divergence rates for several of these;
where a rate is quoted in the table below it is that measurement, and a
number that walks away from it is a signal even when the mutant still fails.

CONTROLS.  The four entries marked (control) are NOT bugs.  They are edits
that must change NOTHING, and a grader that reports them as failures is
keying on something it should not be looking at.  The most important is the
int16 wrap: it is a real property of the DOS build, the port implements it,
and this file measures that the wave CANNOT validate it, because it moves
only geometry.  That is stated here rather than left for a reader to
discover.

Usage:
    python ns_mkbreak.py [--only NAME] [--quick]
"""

import os
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import ns_diff as D                                             # noqa: E402
import ns_spec as N                                             # noqa: E402

SCRATCH = os.path.join(HERE, "ns_break")
SRC = os.path.join(HERE, "ns_ref.c")

# name, kind, one-line description, [(old, new), ...]
MUTANTS = [
    ("zrandom_one", "mutant",
     "zrandom consumes ONE draw instead of two",
     [("    ledger_site = site; b = brtl_random (range);",
       "    b = 0; /* MUTANT */")]),

    ("drop_4094_rand1000", "mutant",
     ":4094's random(1000) omitted -- 'the value only scales a ring'",
     [("double rr = (double) RANDI (4094, 1000);",
       "double rr = 0; /* MUTANT */")]),

    ("drop_4094_zrandom", "mutant",
     ":4094's zrandom elided -- 'the value is dead'",
     [("double zr = ZRANDF (4094, nearstar_p_ray[n]);",
       "double zr = 0; /* MUTANT */")]),

    ("random0_no_draw", "mutant",
     "random(0) returns without drawing (it does draw: :4213 on the first "
     "moon of every outer planet)",
     [("    long r = brtl_rand();                       /* drawn even when n == 0 */",
       "    long r; if (n == 0) return 0; r = brtl_rand(); /* MUTANT */")]),

    ("e_no_shortcircuit", "mutant",
     "phase E :4213/:4214 lose their short-circuit -- the draw fires for "
     "every planet, not only n>7 / n>9",
     [("            if (n > 7 && RANDI (4213, c)) r = 7;\n"
       "            if (n > 9 && RANDI (4214, c)) r = 7;",
       "            { int m1 = RANDI (4213, c), m2 = RANDI (4214, c); /* MUTANT */\n"
       "              if (n > 7 && m1) r = 7;\n"
       "              if (n > 9 && m2) r = 7; }")]),

    ("d_no_shortcircuit", "mutant",
     "phase D :4152 loses its short-circuit -- random(4) fires for every "
     "type-3 planet",
     [("                if ((n < 2) || (n > 6) || (nearstar_class && RANDI (4152, 4))) {\n"
       "                    if (RANDI (4153, 2))\n"
       "                        nearstar_p_type[n]++;\n"
       "                    else\n"
       "                        nearstar_p_type[n]--;\n"
       "                }",
       "                { int m3 = RANDI (4152, 4); /* MUTANT */\n"
       "                if ((n < 2) || (n > 6) || (nearstar_class && m3)) {\n"
       "                    if (RANDI (4153, 2))\n"
       "                        nearstar_p_type[n]++;\n"
       "                    else\n"
       "                        nearstar_p_type[n]--;\n"
       "                } }")]),

    ("b_skipped_when_small", "mutant",
     "phase B skipped when nop < 5 -- 'the writes land past the last planet "
     "anyway'.  They do; the DRAWS do not.",
     [("    if (!nearstar_class) {\n        if (RANDI (4112, 4) == 2)",
       "    if (!nearstar_class && nearstar_nop >= 5) { /* MUTANT */\n"
       "        if (RANDI (4112, 4) == 2)")]),

    ("seed_three_remainders", "mutant",
     "the seed as a flat product of three remainders instead of a chain",
     [("    t = x % 10000;                              /* C %: toward zero */",
       "    /* MUTANT: (x%10000)*(y%10000)*(z%10000), a flat product of\n"
       "       three remainders instead of a chain of them */\n"
       "    t = (i32)((u32)(x % 10000) * (u32)(y % 10000));\n"
       "    t = (i32)((u32)t * (u32)(z % 10000));\n"
       "    return t;\n"
       "    t = x % 10000;"),
      ]),

    ("ident_three_quotients", "mutant",
     "the identity as a product of three quotients, in binary64",
     [("    v = (ext)x;\n"
       "    v = v / (ext)100000;      /* fidiv */\n"
       "    v = v * (ext)y;           /* fmulp */\n"
       "    v = v / (ext)100000;\n"
       "    v = v * (ext)z;\n"
       "    v = v / (ext)100000;",
       "    { double a = x / 100000.0, b = y / 100000.0, c = z / 100000.0;\n"
       "      v = (ext)(double)(a * b * c); }  /* MUTANT */")]),

    ("phasec_capped", "mutant",
     "phase C given an iteration cap of 20 -- the loops have no cap at "
     "all. Measured on this corpus: up to 66 re-rolls in one system, and "
     "the recon saw 109 on a wider one.",
     [("            case 9:  while (nearstar_p_type[n] != 0 &&\n"
       "                            nearstar_p_type[n] != 6 &&\n"
       "                            nearstar_p_type[n] != 9)\n"
       "                         nearstar_p_type[n] = (char) RANDI (4134, 10);",
       "            case 9:  { int cap = 20; while (cap-- && nearstar_p_type[n] != 0 &&\n"
       "                            nearstar_p_type[n] != 6 &&\n"
       "                            nearstar_p_type[n] != 9)\n"
       "                         nearstar_p_type[n] = (char) RANDI (4134, 10); }")]),

    ("srand_sign_extended", "mutant",
     "srand's argument sign-extended instead of zero-extended.  srand takes "
     "unsigned and the DOS code explicitly zeroes the high word.",
     [("    rnd_state = (u32)(seed & 0xFFFFu);      /* c7 06 5c 39 .. ; a3 5a 39 */",
       "    rnd_state = (u32)(i32)(i16t)seed;       /* MUTANT */")]),

    ("moons_not_skipped", "mutant",
     "moons NOT skipped for classes 2/7/15.  Declared up front as the one "
     "mutant with no strong external witness: the extra bodies land past "
     "nop where no player could ever have named them.",
     [("    if (nearstar_class == 2 || nearstar_class == 7 || nearstar_class == 15)\n"
       "        goto no_moons;",
       "    /* MUTANT: the goto is gone */")]),

    # ---------------------------------------------------------- controls
    ("ctl_4199_own_seed", "control",
     ":4199 reads the moon's own orbital seed instead of its parent's. The "
     "VALUE changes; the tree cannot see it.",
     [("            nearstar_p_ray[q]        = (double) RANDF (4199, nearstar_p_orb_seed[n]) * 0.05 + 0.1;",
       "            nearstar_p_ray[q]        = (double) RANDF (4199, nearstar_p_orb_seed[q]) * 0.05 + 0.1;")]),

    ("ctl_b_clipped", "control",
     "phase B's writes clipped to n < nop, draws kept. The clipped writes "
     "were inert, so nothing may move.",
     [("        if (RANDI (4112, 4) == 2) nearstar_p_type[2] = 3;\n"
       "        if (RANDI (4113, 4) == 2) nearstar_p_type[3] = 3;\n"
       "        if (RANDI (4114, 4) == 2) nearstar_p_type[4] = 3;",
       "        if (RANDI (4112, 4) == 2 && 2 < nearstar_nop) nearstar_p_type[2] = 3;\n"
       "        if (RANDI (4113, 4) == 2 && 3 < nearstar_nop) nearstar_p_type[3] = 3;\n"
       "        if (RANDI (4114, 4) == 2 && 4 < nearstar_nop) nearstar_p_type[4] = 3;")]),

    ("ctl_4094_reversed", "control",
     ":4094's two operands evaluated right to left. Two draws either way, "
     "and neither value reaches the tree.",
     [("            double zr = ZRANDF (4094, nearstar_p_ray[n]);\n"
       "            double rr = (double) RANDI (4094, 1000);",
       "            double rr = (double) RANDI (4094, 1000);\n"
       "            double zr = ZRANDF (4094, nearstar_p_ray[n]);")]),

    ("ctl_clamp_not_wrap", "control",
     "the int16 wrap replaced by a clamp at the float sites. THIS IS THE "
     "IMPORTANT CONTROL: it must change nothing, which is exactly why this "
     "wave CANNOT validate the wrap. It is a geometry property.",
     [("    return (i16t)(u32)l;\n}", "    if (l >  32767) return  32767;\n"
       "    if (l < -32768) return -32768;\n"
       "    return (i16t)l;\n}")]),
]


def build(name, edits):
    os.makedirs(SCRATCH, exist_ok=True)
    src = open(SRC).read()
    for old, new in edits:
        if old not in src:
            return None, ("the anchor text for %r is not in ns_ref.c any more; "
                          "the mutant is stale and is NOT a pass" % name)
        if src.count(old) != 1:
            return None, ("the anchor text for %r occurs %d times"
                          % (name, src.count(old)))
        src = src.replace(old, new, 1)
    cpath = os.path.join(SCRATCH, "ns_%s.c" % name)
    exe = os.path.join(SCRATCH, "ns_%s.exe" % name)
    open(cpath, "w").write(src)
    r = subprocess.run(["gcc", "-O2", "-fwrapv", "-o", exe, cpath, "-lm"],
                       capture_output=True, text=True)
    if r.returncode:
        return None, "build failed:\n" + r.stderr[:800]
    return exe, None


def topology_divergence(good, bad):
    _h, ga = N.read_nstopo(good)
    _h, gb = N.read_nstopo(bad)
    fields = [5, 6] + list(range(20, 100))
    moved = sum(1 for a, b in zip(ga, gb)
                if any(a[f] != b[f] for f in fields))
    draws = sum(1 for a, b in zip(ga, gb)
                if any(a[f] != b[f] for f in range(11, 20)))
    return moved, draws, len(ga)


def first_class(good, bad):
    fails = D.compare([good, bad], verbose=False, limit=1)
    return fails[0][0] if fails else None


def catalogue_violations(nstopo, rows):
    """The three catalogue bounds, applied straight to an NSTOPO.

    This is the EXTERNAL leg of the battery: it uses only STARMAP.BIN, so a
    mutant it catches is caught by a 1996 artifact rather than by the two
    reference implementations agreeing with each other.

      class   r3 must equal the 'S' record's class tail
      nob     every charted body index must be <= r6
      class6  a class-6 star must have r5 == 0
      ident   r9/r10 must be the exact 64 bits the record stores
    """
    import ns_catalogue as K
    import starmapspec as S
    blob = _starmap()
    _h, recs = N.read_nstopo(nstopo)
    v = 0
    for r, (rec, x, y, z, nm, tag, bodies) in zip(recs, rows):
        stored = struct.unpack_from("<Q", blob, 4 + 32 * rec)[0]
        if (r[9] | (r[10] << 32)) != stored:
            v += 1
        if nm.startswith(K.NO_LABEL):
            continue
        if tag >= 0 and r[3] != tag:
            v += 1
        if bodies and max(bodies) > r[6]:
            v += 1
        if tag == 6 and r[5]:
            v += 1
    del S
    return v


_SM = []


def _starmap():
    if not _SM:
        import starmapspec as S
        _SM.append(open(S.CATALOGUE, "rb").read())
    return _SM[0]


def main(argv):
    only = None
    quick = False
    i = 0
    while i < len(argv):
        if argv[i] == "--only":
            only = argv[i + 1]; i += 1
        elif argv[i] == "--quick":
            quick = True
        i += 1

    corpus = os.path.join(HERE, "ns_corpus.nsin")
    if not os.path.exists(corpus):
        subprocess.run([sys.executable, os.path.join(HERE, "ns_corpus.py")],
                       check=True)
    dlnsin = os.path.join(HERE, "ns_dl.nsin")

    good_exe, err = build("good", [])
    if err:
        raise SystemExit(err)
    good = os.path.join(SCRATCH, "good.nstopo")
    good_dl = os.path.join(SCRATCH, "good.dl.nstopo")
    subprocess.run([good_exe, corpus, good], check=True)
    if os.path.exists(dlnsin):
        subprocess.run([good_exe, dlnsin, good_dl], check=True)

    import ns_dl
    import ns_corpus
    rows = ns_dl.capture_rows() if os.path.exists(dlnsin) else []
    crows = ns_corpus.build("dl").rows
    base_cat = catalogue_violations(good, crows)
    print("good build: %d catalogue violations over %d systems\n"
          % (base_cat, len(crows)))

    print("%-22s %-8s %8s %8s  %-11s %9s %9s"
          % ("mutant", "kind", "topo%", "draw%", "first check", "DL", "CAT viol"))
    print("-" * 96)
    rc = 0
    for (name, kind, desc, edits) in MUTANTS:
        if only and name != only:
            continue
        exe, err = build(name, edits)
        if err:
            print("%-22s %-8s  BUILD PROBLEM: %s" % (name, kind, err))
            rc = 1
            continue
        out = os.path.join(SCRATCH, "%s.nstopo" % name)
        subprocess.run([exe, corpus, out], check=True)
        moved, dmoved, tot = topology_divergence(good, out)
        cls = first_class(good, out) or "-"

        dlrate = "-"
        if rows and not quick:
            outdl = os.path.join(SCRATCH, "%s.dl.nstopo" % name)
            subprocess.run([exe, dlnsin, outdl], check=True)
            t, o, _f = ns_dl.grade(outdl, rows, verbose=False)
            dlrate = "%.2f%%" % (100.0 * o / max(t, 1))

        cat = catalogue_violations(out, crows)
        print("%-22s %-8s %7.2f%% %7.2f%%  %-11s %9s %9d"
              % (name, kind, 100.0 * moved / tot, 100.0 * dmoved / tot,
                 cls, dlrate, cat))

        if kind == "mutant":
            external = (dlrate not in ("-", "100.00%")) or cat > base_cat
            if cls is None:
                print("     ^ SURVIVOR, nothing saw it: %s" % desc)
                rc = 1
            elif not external:
                print("     ^ caught ONLY by the two references disagreeing; "
                      "no 1996 artifact sees it. %s" % desc)
                if name not in ("moons_not_skipped", "phasec_capped",
                                "b_skipped_when_small", "ident_three_quotients"):
                    rc = 1
        if kind == "control" and (moved or dmoved):
            print("     ^ CONTROL MOVED, which means a grader is keying on "
                  "something it should not: %s" % desc)
            rc = 1

    print("-" * 96)
    print("topo%% = systems whose nop/nob/body words moved; draw%% = systems "
          "whose per-phase draw counts moved; over %d systems." % tot)
    print("DL       = reproduction rate against the 1996 binary's own output; "
          "the good build scores 100.00%.")
    print("CAT viol = STARMAP.BIN bound violations (class tag, nob bound, "
          "class-6 emptiness); the good build scores %d." % base_cat)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
