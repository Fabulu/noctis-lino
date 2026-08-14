"""GUARDS: the Wave 3 float contract - that generation arithmetic is still
done at 64-bit precision on an unspilled x87 stack, under a control word this
port states rather than inherits.

THE CLAIM THIS PROTECTS. Noctis's star identity is

    nearstar_identity = x/100000 * y/100000 * z/100000      NOCTIS-0.CPP:4078

and it is not a number, it is a SEED: the game truncates it to an integer and
generates a whole solar system from the result. One ULP is a different planet.
Borland compiled that expression into five x87 operations with ONE store, at
control word 133Fh - 64-bit precision, round to nearest even - so every
intermediate stayed 64 bits wide on the register stack. Reproduce the
expression but not the schedule and you get a plausible wrong galaxy.

THE ORACLE. STARMAP.BIN is 37,578 records of stars and planets that players
have charted since 1996, each storing the double the original computed. It is
the one place in this port where "did we get the floating point right" has an
answer that predates the question, produced by a machine we do not have, by a
compiler we are not running. This test recomputes the identities and demands
the bits back.

WHAT IS DELIBERATELY NOT DONE HERE:

  * NOTHING IS GRADED AGAINST A STORED ARTIFACT. work/fp/fpstarin.bin and
    work/fp/fpstarexp.txt exist and this test never opens them. The input
    coordinates are re-swept every run and the expected values are read out
    of the 1996 catalogue.
  * NO INPUT IS CHOSEN BY WHETHER IT MATCHES. The sweep offers candidate
    triples for a catalogue record; a record with two candidates could be
    scored by whichever one reproduces it, which would measure the chooser.
    Only records with exactly ONE candidate are used. That is why the number
    at K=64 is 4113 and not 4194 - the 81 ambiguous records are discarded
    unexamined.
  * WINDOW COINCIDENCES ARE REJECTED BY THEIR RESIDUE, NOT BY MATCHING.
    Noctis's acceptance window is its own tolerance for finding a star by
    name and is thousands of times looser than pairing needs. A record
    written from a triple stores a rounded binary64 of the same exact
    product, so its residue |P-N|/|P| is a few double ULPs; the test measures
    that distribution every run and requires its threshold to sit in an empty
    band. At K=64 nothing is dropped. At K=96 one record is - 'L4 LEG 5A',
    residue 2^-29.4, which NO hypothesis in the ladder reproduces.
  * THE REFEREE SHARES NO ARITHMETIC WITH THE ENGINE. fpspec.py is an x87
    written in Python integers; the engine is x87 instructions in ML
    fragments. Every battery is compared value by value, not score to score.

HOW IT FAILS. A change to the schedule, to the control word, or to the
precision shows up first as "battery N disagrees with the referee at index
i", which names the value; then as a score. A change that makes the engine
disagree with BOTH the referee and the catalogue is an engine bug; one that
makes it disagree with the referee only is a referee bug, and the test says
which by reporting both.

THE HONEST PART. A one-ULP perturbation of an EXTENDED intermediate is not
caught by this oracle and this test does not pretend otherwise - it measures
it and pins the number. The graded quantity is a binary64, so a 2^-63 nudge
survives the final rounding almost always. The oracle discriminates precision
CLASSES - 64 against 53 against 24, spilled against not - decisively, and
that is what it is used for. See docs-notes/FLOATPOLICY.md, "What remains
open".

WHAT IT DOES NOT COVER: the float-to-int cast boundary, which is UNSETTLED.
The engine has no way to truncate an unstored extended value, and this test
asserts only that nothing in the graded path depends on that gap - not that
the gap is closed. Rendering, projection and the 37 hand-written fistp sites
are work/fp/fprun.ps1's vectors, graded against a gcc-built hardware x87.

RUN: python tests/test_floatcontract.py            (~50s, no gcc needed)
     python tests/test_floatcontract.py --K 24     (fast: fewer records)
     python tests/test_floatcontract.py --K 96     (slower, more records)
"""

import math
import os
import re
import subprocess
import sys

import fpdrive as D
import fpspec as R
import linoharness as L
import starmapspec as S

K_DEFAULT = 64


def battery_models(header):
    """The referee's prediction for each battery, in order.

    Battery 2 is predicted from the control word the probe REPORTED finding,
    not from what win32 is supposed to do. If the runtime ever stops forcing
    chop, this test says so instead of failing for a reason it cannot name.
    """
    pa, ra = R.cw_fields(header["cwsaved"])
    return [
        ("NsIdentity, CW 133F",
         lambda t: R.ns_identity(*t), "exact"),
        ("NsIdentity, operands permuted",
         lambda t: R.ns_identity(*t, order=(2, 1, 0)), "exact"),
        ("NsIdentity, ambient word %04X (p=%d rc=%d)" % (header["cwsaved"], pa, ra),
         lambda t: R.ns_identity(*t, p=pa, rc=ra), "break"),
        ("NsIdentity, CW 123F  PC=53",
         lambda t: R.ns_identity(*t, p=53), "break"),
        ("NsIdentity, CW 103F  PC=24",
         lambda t: R.ns_identity(*t, p=24), "break"),
        ("NsIdentity, CW 1F3F  RC=chop",
         lambda t: R.ns_identity(*t, rc=R.RC_CHOP), "break"),
        ("NsIdentitySpill3, one store mid-chain",
         lambda t: R.ns_identity(*t, spill={3}), "break"),
        ("NsIdentitySpillAll, a store per operation",
         lambda t: R.ns_identity(*t, spill={1, 2, 3, 4, 5}), "break"),
        ("IsThereIdentity, the lookup formula",
         lambda t: R.isthere_identity(*t), "break"),
        ("TBYTE round trip after op 1, no flip",
         lambda t: R.ns_identity(*t), "exact"),
        ("one binary64 ULP (ext bit 11) after op 1",
         lambda t: R.ns_identity(*t, flip=(1, 11)), "break"),
        ("one EXTENDED ULP (ext bit 0) after op 1",
         lambda t: R.ns_identity(*t, flip=(1, 0)), "measured"),
        ("one ULP of the final binary64",
         lambda t: R.ns_identity(*t) ^ 1, "break"),
        ("NsIdentity again, after an isocall",
         lambda t: R.ns_identity(*t), "exact"),
    ]


def main():
    K = K_DEFAULT
    if "--K" in sys.argv:
        K = int(sys.argv[sys.argv.index("--K") + 1])

    c = L.Check("test_floatcontract - the float contract, graded by STARMAP.BIN")
    if not c.ok(os.path.exists(S.CATALOGUE),
                "the real STARMAP.BIN is where the reference clone puts it",
                S.CATALOGUE):
        return c.done()

    # ------------------------------------------------- 1. the engine's sources
    good = D.Probe(0, D.BREAK_NONE)          # nstar filled in below
    same, _n = good.install_sources()
    c.ok(same,
         "tools/genfp.py regenerates work/fp/fpchains.txt byte for byte from "
         "fpsched.txt - the checked-in library IS the schedule",
         "sandbox %s" % good.dir)

    sched = open(os.path.join(D.FPWORK, D.SCHED), "r",
                 encoding="utf-8", errors="replace").read()
    chains = open(os.path.join(good.dir, D.CHAINS), "r",
                  encoding="utf-8", errors="replace").read()

    # The schedule is the transcription; the absence of an fstp in it is the
    # absence of an fstp in NOCTIS.EXE. Check the one that is graded still
    # has exactly one store and is still marked exact.
    ns = re.search(r"^chain NsIdentity\b(.*?)^end", sched, re.S | re.M).group(1)
    c.eq(len(re.findall(r"^\s*fstp\b", ns, re.M)), 1,
         "the graded schedule still has exactly ONE fstp")
    c.eq(len(re.findall(r"^\s*fld\b", ns, re.M)), 0,
         "...and no reload: no intermediate leaves the register stack")
    c.ok(re.search(r"^\s*exact\s*$", ns, re.M) and re.search(r"^\s*cw\s+133F\s*$", ns, re.M),
         "...and is still marked `exact` at cw 133F")

    # ---------------------------------- 2. the generator's refusals, which are
    #                                       the only thing stopping a plausible
    #                                       wrong answer being emitted silently
    def genfp(args, cwd):
        p = subprocess.run([sys.executable, D.GENFP] + args, cwd=cwd,
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        return p.returncode, (p.stdout or "") + (p.stderr or "")

    rc, msg = genfp(["--backend", "native", D.SCHED, "natout.tmp"], good.dir)
    c.ok(rc != 0,
         "genfp REFUSES to compile an `exact` chain through L.in.oleum's own "
         "float instructions - 24 bits would be a plausible wrong answer",
         msg.strip().splitlines()[-1] if msg.strip() else "rc %d" % rc)

    bad = os.path.join(good.dir, "intout.tmp")
    with open(bad, "w", encoding="utf-8") as fh:
        fh.write("chain CastMe\n  in int32 x,n\n  fild x\n"
                 "  fistp n\nend\n")
    rc, msg = genfp(["intout.tmp", "intout2.tmp"], good.dir)
    c.ok(rc != 0 and "bare fistp is forbidden" in msg,
         "genfp REFUSES a bare fistp even when it targets a declared integer "
         "input slot, so a schedule cannot bypass the f64-only output rule",
         msg.strip().splitlines()[-1] if msg.strip() else "rc %d" % rc)

    # fistp encodings: DB /3 dword, DB /2 fist, DF /7 qword, DF /3 word.
    fistp = [p for p in ("DB 9F", "DB 97", "DF BF", "DF 9F") if p in chains]
    c.ok(not fistp,
         "no generated chain contains an fistp - nothing in the GRADED path "
         "depends on the cast boundary this wave left unsettled",
         "found %r" % fistp if fistp else "")

    # ------------------------------------------------------- 3. build the oracle
    recs = S.load_catalogue()
    orc = R.build_oracle(K, recs=recs)
    ids = R.star_ids(recs)
    N = orc.nuniq
    c.note("catalogue: %d records, %d distinct 'S' identities" % (orc.nrec, len(ids)))
    c.note("sweep K=%d: %d records usable, %d ambiguous and DISCARDED "
           "unexamined, %d dropped as window coincidences"
           % (K, N, orc.nambig, len(orc.dropped)))
    if not c.ok(N >= 500, "the unbiased oracle has enough records to be sharp",
                "%d records" % N):
        return c.done()

    # The pairing rule, checked against its own data rather than tuned. A
    # genuine record stores a rounded binary64 of the same exact integer
    # product, so its residue is a few double ULPs; a coincidence inside
    # Noctis's own 1e-5 lookup window is orders of magnitude worse. The
    # threshold has to sit in an EMPTY band or it is a knob.
    rel = sorted(orc.rel)
    med, worst = rel[len(rel) // 2], rel[-1]
    c.note("pairing residue |P-N|/|P|: median 2^%.1f, worst kept 2^%.1f, "
           "threshold 2^%.0f" % (math.log2(med), math.log2(worst),
                                 math.log2(orc.maxrel)))
    c.ok(med < 2.0 ** -50,
         "the catalogue's own residues say its writer stored a rounded "
         "binary64 of the exact product - which is what makes a residue "
         "thousands of times larger an accident rather than a data point",
         "median 2^%.1f" % math.log2(med))
    c.ok(worst < orc.maxrel / 16,
         "the pairing threshold sits in an empty band above every believed "
         "record - it is describing the data, not tuned to it",
         "worst kept 2^%.1f vs threshold 2^%.0f"
         % (math.log2(worst), math.log2(orc.maxrel)))
    perm = sorted(orc.slack)
    c.note("window slack 1e10/|P|: median 2^%.1f - the pairing rule is what "
           "closes the gap between that and 2^%.0f"
           % (math.log2(perm[len(perm) // 2]), math.log2(orc.maxrel)))

    # EVERY DROP IS JUSTIFIED, not assumed. A dropped record is a claim that
    # this triple did not produce it; the claim is checked by trying the whole
    # ladder - every precision, both roundings, every spill point, and the
    # lookup formula - and requiring all of them to fail. If any hypothesis
    # reproduced a dropped record, the pairing rule threw away real evidence
    # and this test must say so.
    #
    # The band check above can only bite where a coincidence exists; a
    # threshold that is too LOOSE is caught the other way, by the coincidence
    # it lets through failing THE CLAIM below. Both directions are covered,
    # and neither needs a tuned margin.
    ladder = [("p=%d rc=%d" % (p, rc), dict(p=p, rc=rc))
              for p in (64, 53, 24) for rc in (R.RC_NEAR, R.RC_CHOP)]
    ladder += [("spill %s" % sorted(s), dict(spill=s))
               for s in ({1}, {2}, {3}, {4}, {5}, {1, 2, 3, 4, 5})]
    for (o, name, r, t, want) in orc.dropped:
        hit = [tag for tag, kw in ladder if R.ns_identity(*t, **kw) == want]
        if R.isthere_identity(*t) == want:
            hit.append("isthere")
        c.ok(not hit,
             "coincidence dropped: record #%d %r at residue 2^%.1f - and NO "
             "hypothesis in the ladder reproduces it, so the drop threw away "
             "nothing" % (o, name, math.log2(r)),
             "reproduced by %r" % hit if hit else "%d hypotheses tried"
             % (len(ladder) + 1))
    c.ok(all(x and y and z for (x, y, z) in orc.trip),
         "no input coordinate is zero, so no identity is a signed zero and "
         "the referee's normal-numbers-only model is in range")
    c.eq(len(set(orc.trip)), N, "every input triple is distinct")

    # --------------------------------------------------- 4. build and run the probe
    good.nstar = N
    good.write_input(orc.trip)
    with open(good.src, "w", encoding="utf-8") as fh:
        fh.write(D.source(N))
    ok, msg = good.build()
    if not c.ok(ok, "the probe builds against the delivered engine sources", msg):
        return c.done()
    blob, msg = good.run()
    if not c.ok(blob is not None, "the probe runs and leaves a fresh output", msg):
        return c.done()
    c.note(msg)

    h, bats = R.read_out(blob)
    c.eq((h["one0"], h["one1"]), (0x00000000, 0x3FF00000),
         "fld1 lands low-half-first: the register file is still laid out for "
         "an 8-byte fstp")
    c.eq(h["sentinel"], R.SENTINEL, "tail sentinel - the whole file was written")
    c.eq((h["nstar"], h["nbat"]), (N, D.NBAT), "star and battery counts")
    c.eq(len(blob), 4 * (R.HDR + D.NBAT * N * 2), "output is exactly its header plus its batteries")
    c.eq(h["top"], 0, "x87 stack TOP is 0 after %d chained fragments - nothing leaked"
         % (D.NBAT * N))
    c.eq(h["fflg"], 0, "no unordered compare and no stack fault")

    amb = h["cwambient"]
    c.note("control word: ambient %04X, FEnter saved %04X, installed %04X"
           % (amb, h["cwsaved"], h["cwentered"]))
    c.eq(h["cwentered"], 0x133F & 0x0F3F, "FEnter installed 133Fh (masked 033Fh)")
    c.ok(amb != (0x133F & 0x0F3F),
         "the AMBIENT word is not the original's - stating it is load-bearing, "
         "not decoration",
         "ambient %04X: PC=%d bits, RC=%d" % ((amb,) + R.cw_fields(h["cwsaved"])))
    c.eq((h["cwbeforeiso"], h["cwafteriso"]), (0x033F, 0x033F),
         "the control word survives an isocall performed inside the bracket")

    # ------------------------------------ 5. every battery, value by value
    models = battery_models(h)
    c.eq(len(models), D.NBAT, "the referee models every battery the probe ran")
    scores, agree = [], []
    for i, (name, fn, _kind) in enumerate(models):
        want = [fn(t) for t in orc.trip]
        got = bats[i]
        badj = [j for j in range(N) if want[j] != got[j]]
        agree.append(not badj)
        scores.append((R.score(got, orc.exp), sum(1 for q in got if q in ids)))
        c.ok(not badj,
             "battery %-2d == the referee bit for bit" % i,
             name if not badj else "%s: %d/%d differ, first at %d: %016X vs %016X"
             % (name, len(badj), N, badj[0], got[badj[0]], want[badj[0]]))

    c.note("")
    c.note("  #  battery                                    exact  in STARMAP")
    c.note("  -- ------------------------------------------ ------ ----------")
    for i, (name, _fn, kind) in enumerate(models):
        s, m = scores[i]
        c.note("  %-2d %-42s %4d/%d %5d      %s" % (i, name[:42], s, N, m, kind))
    c.note("")

    # ------------------------- 5b. a third engine, on the same silicon
    # Two implementations that agree can be wrong in the same way, and a
    # Python model of rounding is exactly the kind of thing that is wrong in
    # a way only hardware notices. During development this leg caught a
    # round-to-nearest bug in fpspec._round that only appeared at PC=24.
    cbats, cmsg = good.cref()
    if cbats is None:
        c.note("third engine SKIPPED: %s" % cmsg)
    else:
        for ci, b, tag in ((0, 0, "133F"), (1, 3, "123F"), (2, 4, "103F")):
            cb = cbats[ci]
            bad = [j for j in range(N) if cb[j] != bats[b][j]]
            c.ok(not bad,
                 "battery %-2d == a gcc-built hardware x87 at CW %s" % (b, tag),
                 "%d/%d differ" % (len(bad), N) if bad else cmsg)
        c.eq(R.score(cbats[0], orc.exp), N,
             "...and the gcc witness reproduces the catalogue on its own")

    # ------------------------------------------------- 6. what each score must be
    s0 = scores[0][0]
    c.eq(s0, N,
         "THE CLAIM: the exact chain at CW 133F reproduces every one of the %d "
         "catalogue identities, bit for bit" % N)
    c.eq(scores[0][1], N,
         "...and every value it produced occurs verbatim as a stored star id "
         "in the 1996 binary")
    c.eq(scores[1][0], N,
         "the permuted chain scores the same - the test grades arithmetic, "
         "not operand order")
    c.ok(bats[1] == bats[0], "...and is bit-identical to the unpermuted one")

    c.ok(bats[9] == bats[0],
         "the TBYTE round trip is lossless - so the two flips below are the "
         "bit, not the store")
    c.ok(bats[13] == bats[0],
         "the chain after the isocall is bit-identical to the chain before it")

    broken = 0
    for i, (name, _fn, kind) in enumerate(models):
        if kind != "break":
            continue
        s = scores[i][0]
        if not c.ok(s < s0, "battery %-2d FAILS the oracle, as it must" % i,
                    "%s: %d/%d vs %d" % (name[:42], s, N, s0)):
            broken += 1
    c.eq(broken, 0, "BREAKS THAT FAILED TO FAIL")

    c.ok(0 < scores[3][0] < N,
         "PC=53 - every IEEE double engine, including noctis-iv-lr - is a "
         "partial, not a wipeout: it is exactly the kind of wrong that a "
         "tolerance-based test would call correct",
         "%d/%d = %.1f%%" % (scores[3][0], N, 100.0 * scores[3][0] / N))
    c.ok(scores[4][0] < N // 50,
         "PC=24 - the precision L.in.oleum's own float instructions provide - "
         "reproduces essentially nothing",
         "%d/%d = %.2f%%" % (scores[4][0], N, 100.0 * scores[4][0] / N))
    c.eq(scores[8][0], 0,
         "the game's isthere() lookup formula scores ZERO - the honest null, "
         "a real formula from the same program that did not write the file")
    c.eq(scores[8][1], 0, "...and none of its values is anywhere in STARMAP.BIN")
    c.eq(scores[12][0], 0,
         "one ULP of the FINAL binary64 scores zero - the oracle's floor")
    c.eq(scores[12][1], 0, "...and lands outside the catalogue every time")

    # ------------------------- 7. the honest measurement: what the oracle CANNOT see
    s11 = scores[11][0]
    c.ok(s11 > (9 * N) // 10,
         "MEASURED, NOT A POLICY: one EXTENDED ULP (2^-63) in an intermediate "
         "is NOT caught - the graded quantity is a binary64, ten bits coarser. "
         "Pinned so the oracle cannot be overclaimed as last-bit certification",
         "%d/%d = %.1f%% survive the flip" % (s11, N, 100.0 * s11 / N))
    c.ok(scores[10][0] < s11,
         "the same flip one binary64 ULP up (ext bit 11) IS caught - which "
         "locates the oracle's resolution between bit 0 and bit 11",
         "bit 11: %d/%d   bit 0: %d/%d" % (scores[10][0], N, s11, N))

    # -------------------------------- 8. the same probe, built against a broken engine
    for flavour, label, predict in (
            (D.BREAK_NOCW,
             "fpctl with every `fldcw [FCW]` removed - the control word "
             "documented instead of stated",
             lambda t, pa, ra: R.ns_identity(t[0], t[1], t[2], p=pa, rc=ra)),
            (D.BREAK_SPILL,
             "fpchains with ONE fstp/fld qword pair inserted into NsIdentity "
             "after the first fidiv",
             lambda t, pa, ra: R.ns_identity(t[0], t[1], t[2], spill={1}))):
        p = D.Probe(N, flavour)
        _same, nmut = p.install_sources()
        c.ok(nmut > 0, "the %s break edited the source it claims to" % flavour,
             "%d substitution(s)" % nmut)
        p.write_input(orc.trip)
        ok, msg = p.build()
        if not c.ok(ok, "the %s build compiles - it is wrong, not broken" % flavour, msg):
            continue
        bblob, msg = p.run()
        if not c.ok(bblob is not None, "the %s build runs" % flavour, msg):
            continue
        bh, bbats = R.read_out(bblob)
        bpa, bra = R.cw_fields(bh["cwsaved"])
        bs = R.score(bbats[0], orc.exp)
        c.ok(bs < s0, "BREAK %s fails the oracle: %s" % (flavour, label),
             "%d/%d vs %d/%d" % (bs, N, s0, N))
        want = [predict(t, bpa, bra) for t in orc.trip]
        badj = [j for j in range(N) if want[j] != bbats[0][j]]
        c.ok(not badj,
             "...and the referee PREDICTED what it would produce instead - the "
             "break is graded, not merely observed",
             "%d/%d differ" % (len(badj), N) if badj else "")
        if flavour == D.BREAK_NOCW:
            c.eq(bh["cwentered"], bh["cwambient"],
                 "...the broken build ran on the word the runtime handed it "
                 "(%04X), which is what removing the fldcw means" % bh["cwambient"])

    return c.done()


if __name__ == "__main__":
    sys.exit(main())
