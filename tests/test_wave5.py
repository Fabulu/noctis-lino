"""Wave 5b: the CORRECTED buffer model, framebuffer and 54.9254 ms tick.

    python tests/test_wave5.py            everything (about 6 minutes)
    python tests/test_wave5.py --quick    skip the sabotages - NOT A PASS
    python tests/test_wave5.py --nodisp   skip the one probe that opens a window

WHY THIS FILE WAS REWRITTEN
===========================
Wave 5 shipped 109 checks around a model that had already been rejected.
The suite reported 17/17. Three of the checks asserted that a defect was
still present rather than fixing it, and one of them could not fail at
all: FBDUMP kind 6 v1 was eighteen units in which BOTH the "expected" and
the "actual" field held 0xA5A5A5A5, written by construction on both
sides, and the grader compared can[i] against can[i+1] -- two copies of
one literal. A clean run and a build with the canary deleted produced a
bit-identical record. That check passed for every build that could ever
be made, and a check that cannot fail is worse than no check.

So the rules this file now works by:

  1. NO CHECK MAY BE UNBREAKABLE. Every graded check is proved to bite,
     either by a deliberately broken BUILD (a real defect, one edit) or
     by a one-unit PERTURBATION of the reference dump, and the run
     reports which checks have neither. "every graded check is proved
     breakable" is itself a check.
  2. NO ASSERTED DEFECTS. An XFAIL is a promise to fix something later.
     Wave 5 used three of them to record defects this wave was told to
     fix; all three are now positive assertions and the evidence for
     each removal is in WAVE5B_CORRECTIONS.md. The two later XFAILs are
     closed as well: H7 covers the fast-host servo ceiling, while the
     production surface corpus covers the class-A game callers.
  3. NOTHING IS GRADED AGAINST A STORED ARTIFACT. Both sides are
     recomputed on every run: the lino is rebuilt from work/fb*.txt, the
     model is re-derived from the 1996 sources and from arithmetic.

WHAT THE SIX DEFECTS COST, AND WHERE EACH IS NOW GRADED
=======================================================
CRITICAL 1  the servo wrapped .............. H1 H2 H3 H4 H7 T4
CRITICAL 2  class A could not wrap ......... M1 M2 M3 M4 M5
MAJOR 3     the pads had two jobs .......... Z1 Z2 C2 C3 O2 O3 O3b
MAJOR 4     tier 2 for palette and LUT ..... P1 P2 P3 F1 F2 F3 (see note)
MAJOR 5     the canary passed regardless ... C1 C2 C3
MAJOR 6     shade hard-coded its buffer .... P7

THE LONG-HORIZON SERVO CHECK, AND WHY IT IS SHAPED THIS WAY
===========================================================
[Counts] is 32 bits and wraps every 2^32 counts = 477.3 s at 8999 cpms.
The old servo bracketed against the START of the run, so from about eight
minutes in the numerator aliased while the denominator grew without
bound, and the +-1% clamp turned a one-shot collapse into a permanent
ratchet. The old test asked six SINGLE questions with the elapsed time
varied. A ratchet is what a SEQUENCE of firings does to each other, so
that shape could not see it -- and the test then XFAILed the answer.

w5probe.txt now replays a whole run against a synthetic free-running
counter C(t) = (C0 + cpms*t) mod 2^32, eighty-five consecutive windows of
14,061 ms each, 19.9 simulated minutes, from EIGHT synthetic origins that
place the 2^32 crossing at eight different phases. Waiting eight minutes
is not a test; setting the origin is. Three legs run over the same
timeline: the windowed sampler with the shipped estimator, the anchored
sampler with the shipped estimator, and the anchored sampler with the
ORIGINAL estimator. The estimator is seeded 4% BELOW the true rate, so
"do nothing" scores a 4% error and the graded quantity is convergence.

H3 is the reason H2 means anything. Leg 2 alone recovers, because the upper
band refuses every stale bracket -- so a test that compared only legs 1
and 2 would report success for reasons that have nothing to do with the
wrap. Leg 3 is the defect itself, and on the same data it collapses from
8999 to 5355. That is what makes "the windowed servo holds across the
wrap" a claim that could have come out false.

WHAT IS NOT COVERED - stated plainly, not implied
=================================================
  * ANYTHING THAT NEEDS A RENDERER. No polygons, globes, textures, and
    no frame compared against DOSBox-X. Wave 5 has no renderer.
  * WHETHER THE GAME EVER PERFORMS A CLASS-A WRAP. Wave 5 itself cannot
    answer this because it has no surface renderer. The later production
    `supaint.txt` implements `spot`, `cirrus`, `crater`, `wave`, `volcano`
    and `atm_cyclon` with their site-specific truncation order, and
    `test_surface.py` runs those actual Lino painters across the complete
    surface corpus. This is no longer an open product question.
  * WHETHER THE INDEX PAGE MATCHES noctis-harness. It does not, and this
    file does not claim otherwise: w5probe's page fixture and
    fb_ref.c's are different scenarios, and LINOBUF has no section
    reconciling them. F1/F2/F3 grade the port against a Python model of
    the SAME fixture, which is Tier 2 for the palette and the LUT (three
    producers: this model, fb_pal.py and the lino) and UNGRADED for the
    page. It used to say "Tier 1 for the page", which was an over-claim
    on two counts: there is no external artifact for the page (that is
    what tier 1 MEANS), and the two producers use different fixtures, so
    the cross-comparison is NOT GRADED - fb_ledger's own
    T2.LINO.ADAPTED.CROSSFIXTURE and fb_compare's TIER_TABLE both say
    ev0 / one producer per fixture. tests/w5audit.py pins this sentence
    against the ledger and fails if the two drift apart again.
    fb_compare.py --suite is the place that disagreement lives and it is
    not silenced here.
  * "LOOKS RIGHT". Nothing here is eyeballed.
  * LONG SESSIONS. The longest real soak is 200 ticks, 11 seconds. The
    19.9 simulated minutes of the servo replay are synthetic and say
    nothing about thermal drift or a real suspend.

THE TIMING BOUNDS, AND WHY THESE
================================
Only four checks are noisy and all four measure OVERSHOOT - how far past
its deadline a tick actually fired - never a frame cost and never a
throughput. Overshoot is structurally bounded for a correct
implementation: the deadline sequence is exact integer arithmetic, so the
only error is the granularity of the final spin and it does not
accumulate. Measured on this machine over 200 ticks under a full
page-build + expand load with a 60 ms hitch every 37 ticks:

    p50 overshoot    0.000000 ms              bound  0.50 ms
    p90 overshoot    0.000000 - 0.000111 ms   bound  1.50 ms
    max overshoot    0.04 - 11.50 ms          bound 40.0 ms
    wall vs grid    -14.7 to +8.3 ms          bound 60.0 ms / 200 ticks

  * p50 0.50 ms catches using SLEEP as the tick source: PORTPLAN
    measured SLEEP returning 62.75 ms for a 55 ms request, a p50
    overshoot near 7.8 ms against a measured p50 of zero counts.
  * p90 1.50 ms catches dropping the spin margin from 16 to 4 ms.
  * max 40.0 ms is a BACKSTOP, not a discriminator - a single overshoot
    is one Windows scheduling stall. 40 ms is the last value below one
    whole period; T3 catches a consumed grid point exactly.
  * T12 60.0 ms compares READ TIME against the nominal grid: two
    INDEPENDENT clocks, so it does not depend on the servo's own
    estimate. It is a GROSS-FAILURE BACKSTOP and nothing more, and the
    reason is measured rather than assumed: four runs of one binary
    spread -14.7 to +8.3 ms, because the deadlines are laid out in
    COUNTS and the counter's rate estimate itself moved 8986..9015
    across those runs. A 55 ms period would show as +15.3 ms, INSIDE
    that noise, so this check does not discriminate the period and does
    not claim to - T5 and T6's 256 exact deadlines do, with zero
    tolerance.

    Wave 5 instead converted the counter span with [TKcpms], which
    stopped meaning anything the moment the servo began running: cpms
    then changes DURING the soak, so that formulation measured the
    servo's own correction. It read 19.8 ms against its own 5 ms bound
    on a run whose deadlines were every one of them exactly on the grid.
    The sharp test for re-basing is not a bound at all: it is T1.

T1 IS NOW PIECEWISE, and that is a consequence of fixing CRITICAL 1.
SERVON was 256 inside fbtick while the soak ran 200 ticks, so "TK servo"
had NEVER EXECUTED in a soak -- which is exactly how the wrap shipped
past a 109-check suite. It is a driver constant now and the reference run
fires it twice, so cpms CHANGES during the soak and a grid rebuilt with
one cpms is wrong. The servo log says when it changed and T1 replays
fbtick's own recurrence piecewise from the raw logs. The single-cpms
reconstruction misses 199 of 200 deadlines, which is how we know the
piecewise part is load-bearing rather than decorative.
"""

import hashlib
import os
import shutil
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import linoharness as lh          # noqa: E402
import w5audit                    # noqa: E402
import w5spec as S                # noqa: E402

SAND = os.path.join(lh.GEN, "w5")
WORK = lh.WORK
HARNESS_DIR = w5audit.HARNESS

LIBS = ("fbmem.txt", "fbpal.txt", "fbtick.txt")
FPLIBS = ("fpabi.txt", "fpctl.txt", "fpsoft.txt", "fpx87.txt", "fpconv.txt")

# ------------------------------------------------------------- timing bounds
BOUND_P50_MS = 0.50
BOUND_P90_MS = 1.50
BOUND_MAX_MS = 40.0
BOUND_DRIFT_MS = 60.0
BOUND_PRESENT_P50_MS = 10.0

# --------------------------------------------------------------- open items
#
# Wave 5's three xfails asserted defects this wave was told to fix. All three
# are gone and each removal is justified by evidence, recorded beside the
# check that replaced it:
#
#   O6 "low pads are guarded"      -> C3. fbmem builds an eleven-pad ZONE
#      table with its own pad-base function instead of deriving the pads from
#      rtab's nine regions. Corrupting nw[3] and nw[20] after poisoning now
#      reports fired=1, n=2, at=3. Sabotage S-ZTAB-FROM-RTAB proves C3 bites.
#   T8 "servo survives the counter wrap" -> H1/H2/H3. The servo is windowed
#      and re-bases unconditionally before the band test. Eight synthetic
#      origins, 85 firings each, 2-3 wrap-straddling windows per scenario,
#      converged exactly with worst error 0 -- while the ORIGINAL estimator
#      on the identical data collapses to 5355.
#   P7 "shade takes its destination buffer" -> P7 positive. fbpal computes
#      3*[FBSHfirst] + [SHdstb]; "PAL zero" defaults it to pal6 so the seven
#      tmppal sites need no change. Sabotage S-SHADE-IGNOREDST proves it.
#
H7 = "H7 the rate-derived servo ceiling prevents fast-host counter aliasing"

KNOWN_OPEN = {}

# --------------------------------------------------------------- the variants

SHORT = {"TWNTICK\t= 200;": "TWNTICK\t= 48;",
         "TWHITCH\t= 37;": "TWHITCH\t= 11;",
         "TWANCH\t= 4096;": "TWANCH\t= 256;",
         "TWCALMS\t= 2500;": "TWCALMS\t= 300;"}
# NOTE the short variant's 48-tick soak is BELOW SERVON, so the servo cannot
# fire in it at all. T4 knows that and asserts nothing there; if it did, it
# would appear to "catch" every sabotage regardless of what was broken.

DISPLAY = {"\tunit = 32;":
           "\tunit = 32;\n\tdisplay width = 320;\n\tdisplay height = 200;",
           "\t=> TW sky cycle;\n\n\t=> TW emit;":
           "\t=> TW sky cycle;\n\n\t=> TW present;\n\t=> TW emit;"}

# Each sabotage: (tag, file, exact old text, exact new text, the check that
# must catch it, one line saying what real defect it models).
#
# Eleven of these edit a library and three edit the probe, because three of
# the rules being guarded live in the present path or at the call site rather
# than inside a library.
SABOTAGE = [
    ("S01", "fbmem.txt",
     "\tC = [MBval]; C & 255;",
     "\tC = [MBval];",
     "B1 char store wraps",
     "a byte store that does not truncate to 8 bits"),
    ("S02", "fbmem.txt",
     '"MEM put byte"\n\tA = nw; A + [MBptr];',
     '"MEM put byte"\n\tA = nw; C = [MBptr]; C > 2; A + C;',
     "B2 one item per unit",
     "four Noctis bytes packed into one lino unit"),
    ("S03", "fbmem.txt",
     '"MEM check pads"\n\t[MCfired] = 0;',
     '"MEM check pads"\n\tend;\n\t[MCfired] = 0;',
     "C1 the canary record is what the walker produced",
     "THE CANARY DELETED. Under FBDUMP v1 this produced a BIT-IDENTICAL "
     "dump - it is the defect this wave was told to fix"),
    ("S04", "fbmem.txt",
     "ZNGLB\t= 32768;",
     "ZNGLB\t= 22586;",
     "L1 region table matches the derived layout",
     "n_globes_map sized gl_bytes, dropping gl_brest"),
    ("S05", "fbmem.txt",
     '"MEM build ztab"\n\t[MEMi] = 0;',
     '"MEM build ztab"\n\t[MEMi] = 2;',
     "C3 the two low pads are guarded",
     "a zone table derived from rtab's nine regions, which is what left "
     "nw[0..31] guarded by nothing"),
    ("S06", "fbmem.txt",
     '"MEM zone allow"\n\t[ZAmask] = 0;',
     '"MEM zone allow"\n\t[ZAmask] = 0; end;',
     "O2 digit_at's six units are counted, not flagged",
     "the guard band and the allowance merged back into one job, so the "
     "first cockpit glyph fires the canary and halts"),
    ("S07", "fbmem.txt",
     "\t[ZAmask] = 1;",
     "\t[ZAmask] = 255;",
     "O3b one unit further IS a violation",
     "the allowance swallowing the guard - the other way the two jobs "
     "can be merged, and the reason O2 alone is not enough"),
    ("S08", "fbmem.txt",
     '"MEM u16"\n\tC & 65535;',
     '"MEM u16"',
     "M2 spot folds at the 16-bit DI",
     "class A back to allocation-size-as-wrap for SPOT: the mask deleted, "
     "so the index walks linearly past the region end"),
    ("S23", "fbmem.txt",
     '"MEM u16s nw"\n\tC & 65535;',
     '"MEM u16s nw"',
     "M3 cirrus folds one step earlier, in BX",
     "the same deletion at the EARLY truncation point, which is the one "
     "cirrus depends on - two masks, two sites, two separate sabotages"),
    ("S09", "fbtick.txt",
     "\tA = [TKnow]; A - [TKdeadline];\n\t? A < 0 -> TK islate no;",
     "\tA = [TKnow];\n\t? A '< [TKdeadline] -> TK islate no;",
     "T7 wait predicate across the wrap",
     "an unsigned timestamp compare instead of the sign of the difference"),
    ("S10", "fbtick.txt",
     "\tA = [TKbase]; A - B;\n\t[TKdeadline] + A;",
     "\tA = [TKbase]; A - B;\n\t[Timer Command] = READ COUNTS; isocall;"
     "\n\tC = [Counts]; C + A; [TKdeadline] = C;",
     "T6 advance battery is exact",
     "a deadline re-based on the clock instead of accumulated"),
    ("S11", "fbtick.txt",
     "\t=> TK advance;\n\t=> TK skip;\n\t=> TK wait;",
     "\t=> TK advance;\n\t=> TK wait;",
     "T3 gaps are whole periods and hitches skip",
     "no skip-to-grid: an overrunning frame catches up"),
    ("S12", "fbtick.txt",
     "\tB = [TKsrvms]; C = B; C '/ 2;\n"
     "\tA = [TKsrvcnt]; A + C; A '/ B; [TKsrvnew] = A;",
     "\tB = [TKsrvms];\n\tA = [TKsrvcnt]; A '/ B; [TKsrvnew] = A;",
     "H1 the whole servo replay matches the independent model",
     "a TRUNCATING servo divide - rule d, worth about 0.2 s/hour"),
    ("S13", "fbtick.txt",
     "\tB = 1;\t\t\t\t\t( clamp step floor )",
     "\tB = 0;\t\t\t\t\t( clamp step floor )",
     "H6 the clamp step has a floor, so no state is absorbing",
     "the clamp step with no floor, which is what turns a collapse into "
     "an ABSORBING state no sample can leave"),
    ("S14", "fbtick.txt",
     "\tA = [TKsrvms]; ? A < SRVMIN -> TK sv short;\t( SIGNED )",
     "\tA = [TKsrvms]; ? A '< SRVMIN -> TK sv short;\t( SIGNED )",
     "H5 the acceptance band is signed and two-sided",
     "the acceptance band unsigned again, which reads a -86,395,000 ms "
     "window as 4.2e9 and applies a permanent -1%"),
    ("S15", "fbpal.txt",
     "C & 63; C * 4; C < 16;",
     "C & 63; B = C; B > 4; C * 4; C | B; C < 16;",
     "P3 LUT is exact",
     "the LUT built with (v<<2)|(v>>4) instead of v*4"),
    ("S16", "fbpal.txt",
     "\tA = pal6; D = curpal6;\n\tB = [PUn]; B * 3;",
     "\tA = pal6; D = curpal6; C = [PVfirst]; C * 3; A + C; D + C;"
     "\n\tB = [PUn]; B - [PVfirst]; B * 3;",
     "P2 curpal6 is exact",
     "an upload that starts at `first` instead of at colour zero"),
    ("S17", "fbpal.txt",
     "\t=> FToIntChop;",
     "\t=> FToIntNear;",
     "P1 pal6 is exact",
     "shade() rounding to nearest instead of chopping"),
    ("S18", "fbpal.txt",
     "\t[SHb] = 63; -> PAL sc store;",
     "\t[SHb] = 0; -> PAL sc store;",
     "P1 pal6 is exact",
     "shade()'s inverted clamp inverted the other way"),
    ("S19", "fbpal.txt",
     "\tA = [FBSHfirst]; A * 3; A + [SHdstb]; [SHdst] = A;",
     "\tA = [FBSHfirst]; A * 3; A + pal6; [SHdst] = A;",
     "P7 shade writes the buffer it was handed",
     "shade ignoring its destination parameter - MAJOR 6, which made "
     "srfpal6 and retpal6 dead weight no test touched"),
    ("S20", "w5probe.txt",
     "\tC = [D];\tC + pal; C = [C]; [E] = C;",
     "\tC = [D];\tB = C; B & 192; C + 1; C & 63; C + B; [D] = C;"
     "\n\t\t\tC + pal; C = [C]; [E] = C;",
     "F2 adaptor page is exact",
     "LINOBUF section 5.4's colour cycle fused into the expand"),
    ("S21", "w5probe.txt",
     "\tA = nw; A + RADPT; A + 63996;",
     "\tA = nw; A + RADPT; A + 64000;",
     "F1 adapted page is exact",
     "niv-lr's relocation of tinta/escrescenze to 64000"),
    ("S22", "w5probe.txt",
     "\tC = [TWmpy]; C + [TWmpx];\n\t=> MEM u16 site;\n\tC > 1; C + 4;",
     "\tC = [TWmpy]; C + [TWmpx];\n\tC > 1; C + 4;\n\t=> MEM u16 site;",
     "M3 cirrus folds one step earlier, in BX",
     "one 'mask the final index' helper serving both sites, which is "
     "right for spot and wrong for cirrus"),
]


# ----------------------------------------------------------------- plumbing

def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def source_hashes():
    """Everything this test reads but must never write."""
    out = {}
    for n in LIBS:
        out["work/" + n] = sha(os.path.join(WORK, n))
    for n in FPLIBS:
        out["work/fp/" + n] = sha(os.path.join(WORK, "fp", n))
    for n in ("w5probe.txt", "w5shade.txt", "w5spec.py", "w5audit.py"):
        out["tests/" + n] = sha(os.path.join(HERE, n))
    # The audit reads every fb_*.py in noctis-harness and must not write one.
    # Re-hashed here for the same reason work/ is: a grader that edits its
    # subject is the stored-artifact defect in its most direct form.
    for n in sorted(os.listdir(HARNESS_DIR)):
        if (n.startswith("fb_") or n.startswith("fbx_")) and n.endswith(".py"):
            out["noctis-harness/" + n] = sha(os.path.join(HARNESS_DIR, n))
    return out


def pristine_state():
    """The toolchain digests. Rule 3 of this project: main/ never changes."""
    path = os.path.join(lh.REPO, "PRISTINE.sha256")
    if not os.path.exists(path):
        return None
    ok = bad = 0
    # the file carries a UTF-8 BOM, which is why a naive `sha256sum -c` on it
    # reports line 1 malformed rather than a mismatch
    for line in open(path, "r", encoding="utf-8-sig"):
        parts = line.split()
        if len(parts) != 3:
            continue
        want, size, rel = parts
        full = os.path.join(lh.REPO, rel.replace("/", os.sep))
        if os.path.exists(full) and sha(full).upper() == want.upper() \
                and os.path.getsize(full) == int(size):
            ok += 1
        else:
            bad += 1
    return ok, bad


def fresh_sandbox():
    """Copy every input in from source. Nothing here survives between runs."""
    if os.path.isdir(SAND):
        shutil.rmtree(SAND)
    os.makedirs(os.path.join(SAND, "fp"))
    for name in LIBS:
        shutil.copy(os.path.join(WORK, name), os.path.join(SAND, name))
    for name in FPLIBS:
        shutil.copy(os.path.join(WORK, "fp", name), os.path.join(SAND, "fp", name))
    for name in ("w5probe.txt", "w5shade.txt"):
        shutil.copy(os.path.join(HERE, name), os.path.join(SAND, name))


def edit(text, old, new, where):
    if text.count(old) != 1:
        raise SystemExit("sabotage anchor appears %d times in %s, expected 1:\n%r"
                         % (text.count(old), where, old))
    return text.replace(old, new)


def write_variant(name, subs, src="w5probe.txt"):
    """Write <name>.txt from the pristine probe with `subs` applied."""
    text = open(os.path.join(HERE, src), "r", encoding="utf-8").read()
    text = edit(text, "program name = { %s };" % os.path.splitext(src)[0],
                "program name = { %s };" % name, src)
    for old, new in subs:
        text = edit(text, old, new, src)
    path = os.path.join(SAND, name + ".txt")
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    return path


def build_and_run(path, tag, timeout=120):
    """Build in the sandbox, run with the poll-and-kill runner, return the dump.

    The output name is fixed by fbmem's [fbdumpname], so the file is
    collected and renamed per variant rather than parameterised.
    """
    out = os.path.join(SAND, "fb-out.bin")
    keep = os.path.join(SAND, tag + ".bin")
    for stale in (out, keep, os.path.splitext(path)[0] + ".exe"):
        if os.path.exists(stale):
            os.remove(stale)
    rc, note = lh.build(path, timeout_sec=120)
    if rc != 0:
        return None, "BUILD FAILED: " + note.strip().replace("\n", " | ")
    exe = os.path.splitext(path)[0] + ".exe"
    rc, note, blob = lh.run(exe, out, timeout_sec=timeout)
    if blob is None:
        return None, "RUN FAILED: " + note
    shutil.move(out, keep)
    return blob, note


def pct(seq, p):
    seq = sorted(seq)
    return seq[min(len(seq) - 1, int(p * len(seq)))]


# ------------------------------------------------------------------ grading

P7 = "P7 shade writes the buffer it was handed"
P7B = "P7b the destination parameter exists at all"

HOR_FIELDS = ("c0", "true", "win", "winerr", "wraps", "sub", "why", "seed",
              "anc", "ancerr", "old", "olderr", "n", "w", "t", "hit",
              "bias", "jit")


def horizon_rows(rec):
    """The kind-22 record, unpacked into one dict per scenario."""
    out = []
    for s in range(len(rec) // 20):
        r = rec[s * 20: s * 20 + 20]
        d = dict(zip(HOR_FIELDS, r))
        d["bias"] = S.s32(d["bias"])
        out.append(d)
    return out


def grade(blob):
    """Every check, as an ordered list of (name, ok, detail).

    One function, used identically for the reference run and for every
    sabotage, so "the sabotage was caught" means the same thing as "the
    reference passed", by construction.
    """
    out = []

    def ck(name, ok, detail=""):
        out.append((name, bool(ok), detail))

    try:
        recs = S.read_fbdump(blob)
    except Exception as exc:
        ck("D0 dump parses", False, str(exc))
        return out
    ck("D0 dump parses", True, "%d records" % len(recs))
    D = S.by_kind(recs)

    need = {S.KLAY: 1, S.KCAN: 1, S.KZONE: 1, S.TWKSLF: 1, S.KPAL6: 3,
            S.KLUT: 1, S.TWKADV: 1, S.TWKHOR: 1, S.TWKMSK: 1, S.TWKSKY: 1,
            S.KSRVL: 1, S.TWKFRM: 1, S.KTICK: 1, S.KPAGE: 2, S.TWKFB: 1,
            S.TWKBND: 1}
    missing = [k for k, n in need.items() if len(D.get(k, [])) < n]
    if missing:
        ck("D1 all records present", False, "missing kinds %s" % missing)
        return out
    ck("D1 all records present", True)

    sf = D[S.TWKSLF][0]
    lay, can, zon = D[S.KLAY][0], D[S.KCAN][0], D[S.KZONE][0]
    pal6, curpal6, srf = D[S.KPAL6][0], D[S.KPAL6][1], D[S.KPAL6][2]
    lut, bnd = D[S.KLUT][0], D[S.TWKBND][0]
    adv, hor, msk = D[S.TWKADV][0], D[S.TWKHOR][0], D[S.TWKMSK][0]
    sky, frm, srvlog = D[S.TWKSKY][0], D[S.TWKFRM][0], D[S.KSRVL][0]
    tlog = D[S.KTICK][0]
    ga, gr, gf = D[S.KPAGE][0], D[S.KPAGE][1], D[S.TWKFB][0]

    ck("D2 probe identifies itself", sf[0] == 0x54545501, hex(sf[0]))

    # ---------------------------------------------------------- the layout
    sizes = S.parse_sizes()
    if sizes is None:
        ck("L0 NOCTIS-D.H is readable", False,
           "no %s - the layout leg cannot run" % S.NOCTIS_SRC)
        return out
    ck("L0 NOCTIS-D.H is readable", True, "%d #defines" % len(sizes))
    order = S.parse_farmalloc_order()
    want = [n for n, _ in S.FARMALLOC][:-1]
    got = [n for n, _ in (order or [])]
    ck("L2 farmalloc order matches NOCTIS.CPP", got == want,
       "%s vs %s" % (got, want))

    L = S.Layout(sizes)
    bad = []
    for r in L.regions:
        g = lay[r["id"] * 4: r["id"] * 4 + 4]
        w = (r["base"], r["size"], r["pad"], r["id"])
        if tuple(g) != w:
            bad.append((r["name"], tuple(g), w))
    ck("L1 region table matches the derived layout", not bad,
       "%d of 9 regions differ: %s" % (len(bad), bad[:2]))
    ck("L3 workspace top matches", sf[1] == L.top, "%d vs %d" % (sf[1], L.top))
    ck("L4 pad and region count", sf[56] == S.PAD and sf[57] == len(L.regions),
       "PADU %d NREG %d" % (sf[56], sf[57]))
    ck("L5 pvfile still holds 409 polygons", sf[58] == 20480 // 50, str(sf[58]))

    # ----------------------------------------------- DEFECT 3: the zone table
    ez = S.expected_zones(L)
    dz = [i for i in range(min(len(ez), len(zon))) if zon[i] != ez[i]]
    ck("Z1 the zone table matches the derived one",
       len(zon) == len(ez) and not dz,
       "%d units, %d differ, first %s" % (len(zon), len(dz),
                                          ("%d: %d vs %d" % (dz[0], zon[dz[0]], ez[dz[0]]))
                                          if dz else "-"))
    # the separation itself: guarded units and allowance units are disjoint,
    # every unit of the workspace's eleven pads belongs to exactly one zone,
    # and nw[0..31] is covered.
    guarded = allowed = 0
    for z in L.zones:
        m = z["mask"]
        allowed += bin(m).count("1")
        guarded += S.ZHALF - bin(m).count("1")
    covered = sorted(set(o for z in L.zones
                         for o in range(z["base"], z["base"] + z["length"])))
    ck("Z2 guard and allowance are disjoint and cover every pad unit",
       guarded + allowed == len(L.pads) * S.PAD and
       covered[:32] == list(range(32)) and
       sf[78] == len(L.zones) and sf[79] == len(L.pads),
       "%d guarded + %d allowance = %d units over %d zones / %d pads; "
       "nw[0..31] covered: %s" % (guarded, allowed, guarded + allowed,
                                  sf[78], sf[79], covered[:32] == list(range(32))))

    # -------------------------------------------------- one item per unit
    ck("B1 char store wraps", sf[2] == 0,
       "failure mask %d; bits 256/512 are the RAW unit after storing 300 and "
       "-1, which is where a store that forgot to truncate shows - reading it "
       "back through MEM get byte masks with 255 and hides it" % sf[2])
    ck("B2 one item per unit", sf[3] == 0, "mask %d" % sf[3])
    ck("B3 8 to 32 sign extension",
       [S.s32(sf[i]) for i in range(5, 9)] == [S.sx8(v) for v in (192, 63, 128, 127)],
       str([S.s32(sf[i]) for i in range(5, 9)]))
    ck("Q1 quadrant bitfields", sf[4] == 0, "mask %d" % sf[4])

    # ------------------------------------------------------- the aliases
    ck("A1 objectschart is ruinschart",
       (sf[9], sf[10], sf[11], sf[12]) == (64, S.quad_get(131, 0), S.quad_get(64, 3), 255),
       "byte %d, nr before %d, obj2 after %d, neighbour %d" % (sf[9], sf[10], sf[11], sf[12]))
    seatex = S.texel(0x2A00, 0x1300)
    ck("A2 globes.map is the sea texture",
       (sf[13], sf[14], sf[15]) == (200, (1000 >> 8) & 63, (seatex >> 8) & 63),
       "texel %d: pre %d, globe byte after fill %d, texel after fill %d"
       % (seatex, sf[13], sf[14], sf[15]))
    ck("A3 digimap2 is split and survives",
       sf[16] == 0x12345678 and sf[17] == ((22586 + 28) >> 8) & 63,
       "digimap2[7] %08X, n_globes_map[gl_bytes+28] %d" % (sf[16], sf[17]))
    ck("A4 p_background becomes s_background", (sf[18], sf[19]) == (7, 9),
       "%d and %d" % (sf[18], sf[19]))
    ck("A5 txtr re-bases by a byte amount", (sf[20], sf[21]) == (5, 99),
       "%d and %d" % (sf[20], sf[21]))

    # ---------------------------------- DEFECT 5: the canary that can fail
    ec = S.expected_canary(L)
    dc = [i for i in range(min(len(ec), len(can))) if can[i] != ec[i]]
    ck("C1 the canary record is what the walker produced",
       len(can) == len(ec) and not dc,
       "%d of %d units differ%s. v1 was 18 units of 0xA5A5A5A5 on BOTH "
       "sides and could not fail; these four fields per pad are the clean "
       "read-back, the witness read-back, the pad the walker named and the "
       "offset it named, none of them a literal"
       % (len(dc), len(ec),
          (", first at unit %d (pad %d field %d): %08X vs %08X"
           % (dc[0], dc[0] // 4, dc[0] % 4, can[dc[0]], ec[dc[0]])) if dc else ""))
    ck("C2 the clean workspace produces no violation and no expectation",
       (sf[22], sf[23], sf[67]) == (0, 0, 0),
       "fired %d, %d violating units, %d allowance units - a canary that "
       "always fires cannot pass, so the clean pass runs FIRST"
       % (sf[22], sf[23], sf[67]))
    ck("C3 the two low pads are guarded",
       (sf[24], sf[25], sf[68]) == (1, 2, 3),
       "corrupting nw[3] and nw[20] after poisoning gave fired=%d n=%d at=%d "
       "(want 1, 2, 3). A walker derived from rtab's nine regions gives "
       "0, 0, 0 - which is what Wave 5 shipped and XFAILed as O6"
       % (sf[24], sf[25], sf[68]))

    # ---------------------------------- DEFECT 3: expectation vs violation
    psm = L["p_surfacemap"]
    ck("O2 digit_at's six units are counted, not flagged",
       (sf[26], sf[27], sf[28]) == (0, 0, 6),
       "txtr[-6..-1] at nw[%d..%d] gave fired=%d n=%d exp=%d (want 0, 0, 6). "
       "Under one magic this fired the canary and halted, so the first "
       "cockpit glyph of a debug build was indistinguishable from an overrun"
       % (psm["base"] - 6, psm["base"] - 1, sf[26], sf[27], sf[28]))
    pvf = L["pvfile"]
    ck("O3 loadpv's one unit past pvfile is counted, not flagged",
       (sf[29], sf[30], sf[31]) == (0, 0, 1),
       "nw[%d] gave fired=%d n=%d exp=%d (want 0, 0, 1)"
       % (pvf["end"], sf[29], sf[30], sf[31]))
    ck("O3b one unit further IS a violation",
       (sf[69], sf[70], sf[71], sf[72]) == (9, 1, pvf["end"] + 1, 0),
       "nw[%d] gave fired=%d n=%d at=%d exp=%d (want 9, 1, %d, 0). Without "
       "this, an allowance covering the whole pad would still pass O2 and "
       "O3 - the guard would have been swallowed rather than separated"
       % (pvf["end"] + 1, sf[69], sf[70], sf[71], sf[72], pvf["end"] + 1))
    ck("O4 class C: the sea texture reads its DOS neighbour",
       (sf[32], sf[33]) == (0, 123),
       "texel 32768 (pad) %d, texel 32784 (s_background[0]) %d" % (sf[32], sf[33]))
    ck("O5 class A: adapted is a full segment plus four",
       (sf[34], sf[35], sf[36]) == (65, 68, 0),
       "adapted[65536] %d, adapted[65539] %d, the unit above %d. This is the "
       "SIZE half only: a size cannot fold an index, which was CRITICAL 2"
       % (sf[34], sf[35], sf[36]))

    # ------------------------------- CRITICAL 2: the 16-bit index wrap, for real
    em = S.expected_mask(L)
    gcalls = (msk[0], msk[2])
    gwraps = (msk[1], msk[3])
    ck("M1 the mask is reached exactly as often as the model says",
       gcalls == (em["calls"], em["calls"]) and
       gwraps == (em["spot_wraps"], em["cirrus_wraps"]),
       "calls %s (model %d), wraps %s (model %d, %d)"
       % (list(gcalls), em["calls"], list(gwraps),
          em["spot_wraps"], em["cirrus_wraps"]))
    ck("M2 spot folds at the 16-bit DI",
       (msk[12], msk[13]) == em["spot_delta"],
       "delta min %d max %d, model %s - min == max is the point: the fold is "
       "a single constant 65,536, not an average" % (msk[12], msk[13], em["spot_delta"]))
    ck("M3 cirrus folds one step earlier, in BX",
       (msk[14], msk[15]) == em["cirrus_delta"],
       "delta min %d max %d, model %s - HALF spot's, because cirrus "
       "truncates in BX before the shift" % (msk[14], msk[15], em["cirrus_delta"]))
    ck("M4 the two deltas differ, so one mask point cannot serve both",
       msk[12] != msk[14] and msk[12] == 2 * msk[14],
       "spot %d, cirrus %d" % (msk[12], msk[14]))
    ck("M5 every masked address is contained",
       msk[17] == 0 and em["oob"] == 0,
       "%d containment failures over %d cases (model %d). STATED PLAINLY: "
       "this is a property of the constants - SPBG+m spans RPBG-4..RPBG+65531 "
       "against a window of RPBG-8..RPBG+65551 - so it holds for EVERY input "
       "and the 340-case battery is not what makes it true"
       % (msk[17], msk[0], em["oob"]))

    # ------------------------------------------------------- the palette
    p, flags = S.expected_palette()
    d1 = [i for i in range(768) if pal6[i] != p.pal6[i]]
    ck("P1 pal6 is exact", not d1, "%d of 768 components differ, first at %s"
       % (len(d1), "%d: %d vs %d" % (d1[0], pal6[d1[0]], p.pal6[d1[0]]) if d1 else "-"))
    d2 = [i for i in range(768) if curpal6[i] != p.curpal6[i]]
    ck("P2 curpal6 is exact", not d2, "%d of 768 components differ, first at %s"
       % (len(d2), "%d: %d vs %d" % (d2[0], curpal6[d2[0]], p.curpal6[d2[0]]) if d2 else "-"))
    d3 = [i for i in range(256) if lut[i] != p.pal[i]]
    ck("P3 LUT is exact", not d3, "%d of 256 entries differ, first at %s"
       % (len(d3), "%d: %06X vs %06X" % (d3[0], lut[d3[0]], p.pal[d3[0]]) if d3 else "-"))
    stale = sum(1 for i in range(192 * 3, 768) if pal6[i] != curpal6[i])
    ck("P4 upload-from-zero leaves a stale band", stale > 0,
       "%d of 192 components of colours 192..255 are written in pal6 but "
       "not uploaded" % stale)
    ck("P5 an out-of-range filter is recorded", sf[37] == flags,
       "PVrange %d, model %d" % (sf[37], flags))
    # MAJOR 6, graded in the MAIN dump. A sabotage of the library is applied
    # to a renamed copy that w5shade.txt does not link, so grading this only
    # in the separate probe let a shade that ignores [SHdstb] go uncaught.
    ms = S.Palette()
    ms.shade(0, 16, (0, 0, 0), (60, 40, 20))
    dw = [i for i in range(48) if srf[i] != ms.pal6[i]]
    tail = [i for i in range(48, 768) if srf[i] != 0]
    ck(P7, not dw and not tail,
       "shade() pointed at srfpal6: %d of the 48 written components differ "
       "from the model and %d of the 720 untouched ones are non-zero. "
       "NOCTIS-0.CPP:1151 takes the destination as its FIRST parameter and "
       "14 of its 21 call sites pass surface_palette; a shade that could "
       "only write pal6 would leave srfpal6 zero here and clobber pal6, so "
       "P1 fires too" % (len(dw), len(tail)))
    esky = S.expected_sky()
    d4 = [i for i in range(len(esky)) if sky[i] != esky[i]]
    ck("P6 the background colour cycle", not d4,
       "%d of %d differ" % (len(d4), len(esky)))

    # --------------------------------------------------- the framebuffer
    eadapted, eadaptor, efb = S.expected_pages(p.pal)
    d5 = [i for i in range(64000) if ga[i] != eadapted[i]]
    ck("F1 adapted page is exact", not d5, "%d of 64000 pixels differ, first %s"
       % (len(d5), "x=%d y=%d %d vs %d" % (d5[0] % 320, d5[0] // 320,
                                           ga[d5[0]], eadapted[d5[0]]) if d5 else "-"))
    d6 = [i for i in range(64000) if gr[i] != eadaptor[i]]
    ck("F2 adaptor page is exact", not d6, "%d of 64000 pixels differ, first %s"
       % (len(d6), "x=%d y=%d %d vs %d" % (d6[0] % 320, d6[0] // 320,
                                           gr[d6[0]], eadaptor[d6[0]]) if d6 else "-"))
    d7 = [i for i in range(64000) if gf[i] != efb[i]]
    ck("F3 expanded framebuffer is exact", not d7,
       "%d of 64000 units differ, first %s"
       % (len(d7), "x=%d y=%d %06X vs %06X" % (d7[0] % 320, d7[0] // 320,
                                               gf[d7[0]], efb[d7[0]]) if d7 else "-"))

    # ---------------------------------------- CRITICAL 1: the servo, long horizon
    ehor = S.expected_horizon()
    ghor = horizon_rows(hor)
    hbad = []
    for i, (g, e) in enumerate(zip(ghor, ehor)):
        for k in HOR_FIELDS:
            if g[k] != e[k]:
                hbad.append((i, k, g[k], e[k]))
    ck("H1 the whole servo replay matches the independent model",
       len(ghor) == len(ehor) and not hbad,
       "%d scenarios x %d fields, %d differ%s"
       % (len(ghor), len(HOR_FIELDS), len(hbad),
          (", first %s" % (hbad[0],)) if hbad else ""))

    good = [g for g in ghor if g["true"] < 71583]
    # a scenario can only straddle 2^32 if the counter actually gets that far
    wrappy = [g for g in good if g["true"] * g["t"] > 2 * (1 << 32)]
    conv = [g for g in good if g["win"] != g["true"] or g["winerr"] > 1
            or g["hit"] > 8]
    conv += [g for g in wrappy if g["wraps"] < 2]
    ck("H2 the windowed servo converges and holds across the wrap",
       good and wrappy and not conv,
       "%d scenarios under the aliasing boundary, %d of them long enough to "
       "cross 2^32: seeded 4%% low, converged in %s firings, final %s "
       "against true %s, worst error after settling %s, wrap-straddling "
       "windows %s%s"
       % (len(good), len(wrappy), [g["hit"] for g in good],
          [g["win"] for g in good], [g["true"] for g in good],
          [g["winerr"] for g in good], [g["wraps"] for g in good],
          ("; FAILED: %s" % conv[:1]) if conv else ""))

    ctl = [g for g in wrappy if g["olderr"] * 4 < g["true"]]
    ck("H3 THE CONTROL: the original estimator is destroyed by the same data",
       wrappy and not ctl,
       "the pre-correction arithmetic - unsigned band, truncating divide, "
       "clamp step with no floor - anchored at the run start over the same "
       "timeline ends at %s against true %s, worst error %s. Without this "
       "H2 would be a statement about the upper band rejecting long brackets, not "
       "about the wrap%s"
       % ([g["old"] for g in wrappy], [g["true"] for g in wrappy],
          [g["olderr"] for g in wrappy], ("; FAILED: %s" % ctl[:1]) if ctl else ""))

    jit = [g for g in ghor if g["jit"]]
    nset = (jit[0]["n"] - 16) if jit else 0
    ck("H4 the rounded divide leaves no systematic bias",
       jit and abs(jit[0]["bias"]) <= nset // 4,
       "jittered scenario: signed error sum %s over %d firings, bound %d. A "
       "truncating divide biases every estimate downwards and this goes "
       "sharply negative; nothing else in this suite grades rule d"
       % ([g["bias"] for g in jit], nset, nset // 4))

    eb = S.expected_band()
    db = [i for i in range(min(len(eb), len(bnd))) if bnd[i] != eb[i]]
    whyb = [bnd[4 * i + 2] for i in range(len(bnd) // 4)]
    ck("H5 the acceptance band is signed and two-sided",
       len(bnd) == len(eb) and not db and
       sorted(set(whyb)) == [S.SVWAPPLY, S.SVWSHORT, S.SVWLONG],
       "six windows, why-codes %s: a -86,395,000 ms straddle of midnight is "
       "REFUSED as short (unsigned it reads 4,208,572,296 and would be "
       "divided into), 3999 refused, 4000 and 60000 accepted, 60001 and "
       "600000 refused. %d of %d units differ from the model. Three "
       "acceptances and three refusals, because a band that accepts "
       "everything and one that refuses everything both pass a battery made "
       "of one kind" % (whyb, len(db), len(eb)))

    slow = [g for g in ghor if g["true"] < 100]
    ck("H6 the clamp step has a floor, so no state is absorbing",
       slow and all(g["win"] == g["true"] for g in slow),
       "at %s counts/ms the step cpms/100 truncates to ZERO, so without the "
       "floor of 1 the estimator can never leave its seed: seeded %s, "
       "converged to %s against true %s in %s firings. This is the only "
       "configuration in the suite that reaches rule e"
       % ([g["true"] for g in slow], [g["seed"] for g in slow],
          [g["win"] for g in slow], [g["true"] for g in slow],
          [g["hit"] for g in slow]))

    sched = S.cpms_schedule(srvlog)
    whys = [srvlog[3 * i + 2] for i in range(len(srvlog) // 3)]
    # A soak shorter than SERVON cannot fire the servo at all, and the short
    # variant the sabotage builds use is exactly that. Asserting the servo ran
    # in a run too short to run it would make T4 "catch" every sabotage
    # regardless of what it broke, which is the failure mode this whole wave
    # is about. So T4 asserts a property of a run long enough to have it, and
    # says which run it is looking at.
    due = sf[46] // sf[51] if sf[51] else 0
    ck("T4 the servo actually ran in the soak, and every sample was accepted",
       (sf[73] >= 1 and len(sched) >= 2 and set(whys) == {S.SVWAPPLY}
        and sf[74] == 0) if due else True,
       "%d firings over %d ticks at SERVON=%d (%d due), %d log entries %s, "
       "why-codes %s, %d overflowed.%s Wave 5 set SERVON=256 with a 200-tick "
       "soak, so TK servo had NEVER RUN in a soak - which is how CRITICAL 1 "
       "shipped"
       % (sf[73], sf[46], sf[51], due, len(sched), sched, sorted(set(whys)),
          sf[74],
          "" if due else " THIS VARIANT'S SOAK IS TOO SHORT TO FIRE IT, so "
          "nothing is asserted here -"))

    # ---------------------------------------------------------- the tick
    cpms = sf[41]
    base, subper = S.period_parts(cpms)
    ck("T5 period decomposition", (sf[44], sf[45]) == (base, subper),
       "55*%d = %d/%d, 44505*%d = %d/%d" % (cpms, sf[44], base, cpms, sf[45], subper))

    badadv = []
    for ci, c in enumerate((8984, 8999, 9000, 9023)):
        for s in range(64):
            if adv[ci * 64 + s] != (S.grid(c, s + 1) & S.M32):
                badadv.append((c, s))
    ck("T6 advance battery is exact", not badadv,
       "%d of 256 deadlines differ, first %s" % (len(badadv), badadv[:1]))

    anchors = S.probe_anchors(sf[62])
    ncases = sum(1 for _ in S.wrap_cases(anchors))
    ck("T7 wait predicate across the wrap", sf[38] == 0 and sf[39] == ncases,
       "%d failures over %d cases (model enumerates %d)" % (sf[38], sf[39], ncases))

    n = len(tlog) // 3
    now = [tlog[3 * i] for i in range(n)]
    dl = [tlog[3 * i + 1] for i in range(n)]
    if n < 8:
        ck("T1 every deadline is on the rational grid", False, "only %d ticks" % n)
        return out
    mult, kbad = S.replay_grid(dl, sched)
    # the same reconstruction with ONE cpms, which is what Wave 5 did. It is
    # printed so that "piecewise" is a measured requirement, not a claim.
    _, kbad1 = S.replay_grid(dl, [(0, cpms)])
    ck("T1 every deadline is on the rational grid", kbad == 0,
       "%d of %d deadlines cannot be reproduced by replaying fbtick's own "
       "recurrence piecewise across the %d cpms values the servo log records. "
       "The SINGLE-cpms reconstruction misses %d of %d, which is why the "
       "piecewise part is load-bearing" % (kbad, n, len(sched), kbad1, n))
    if kbad:
        return out

    over = [S.s32(now[i] - dl[i]) / float(S.cpms_at(sched, i)) for i in range(n)]
    ck("T2 no tick ever fires early", min(over) >= 0, "min overshoot %.6f ms" % min(over))
    ck("T3 gaps are whole periods and hitches skip",
       all(1 <= m <= 3 for m in mult) and sf[47] >= 3,
       "multiples %s, %d skips over %d ticks"
       % (sorted(set(mult)), sf[47], n))

    # T12 is now measured against THE OTHER CLOCK. Converting the counter
    # span with [TKcpms] stopped meaning anything the moment the servo began
    # running: cpms changes during the soak, so that conversion measures the
    # servo's own correction and not any drift -- it read 19.8 ms against a
    # 5 ms bound on a run whose deadlines were all exactly on the grid. The
    # soak is bracketed by READ TIME, a different clock from the
    # high-performance counter, so what is compared now is two independent
    # clocks against the nominal grid.
    # sum(mult), not sum(mult[1:]): the bracket opens BEFORE "TK start", and
    # TK start sets the deadline to now, so tick 0 fires one whole period
    # later. The span is every advance the soak performed, skips included.
    steps = sum(mult)
    nominal = steps * (S.PERIOD_NUM * 1000.0 / S.PERIOD_DEN)
    wall = S.s32(sf[87] - sf[86])
    drift = wall - nominal
    ck("T9 median overshoot", pct(over, 0.50) <= BOUND_P50_MS,
       "p50 %.6f ms, bound %.2f" % (pct(over, 0.50), BOUND_P50_MS))
    ck("T10 p90 overshoot", pct(over, 0.90) <= BOUND_P90_MS,
       "p90 %.6f ms, bound %.2f" % (pct(over, 0.90), BOUND_P90_MS))
    ck("T11 worst overshoot", max(over) <= BOUND_MAX_MS,
       "max %.4f ms over %d ticks, bound %.1f" % (max(over), n, BOUND_MAX_MS))
    ck("T12 the wall clock agrees with the grid", abs(drift) <= BOUND_DRIFT_MS,
       "READ TIME says the soak took %d ms; %d grid steps of the exact "
       "rational period are %.3f ms; difference %+.3f ms, bound %.1f. WHAT "
       "THIS CANNOT DO: discriminate a 55 ms period from 54.9254, which "
       "would show as %+.1f ms and is INSIDE the noise - four runs of this "
       "binary spread -14.7 to +8.3 ms, because the deadlines are laid out "
       "in COUNTS and the counter's own rate estimate moved 8986..9015 "
       "across those runs. The period is graded EXACTLY by T5 and by T6's "
       "256 deadlines instead. This is a gross-failure backstop"
       % (wall, steps, nominal, drift, BOUND_DRIFT_MS,
          steps * (55.0 - S.PERIOD_NUM * 1000.0 / S.PERIOD_DEN)))

    # ------------------------------------------ the fast-host alias boundary
    fast = [g for g in ghor if g["true"] >= 71583]
    ck(H7, bool(fast) and all(
           S.srvmax_for(g["seed"]) < S.HOR_WIN
           and g["win"] == g["seed"]
           and g["winerr"] == g["true"] - g["seed"]
           and g["why"] == (1 << S.SVWLONG)
           for g in fast),
       "at cpms %s, the derived maximum is %s ms against %d-ms samples; "
       "all samples were rejected-long, final rates remained at safe runtime "
       "seeds %s instead of ratcheting, worst errors %s"
       % ([g["true"] for g in fast],
          [S.srvmax_for(g["seed"]) for g in fast], S.HOR_WIN,
          [g["win"] for g in fast], [g["winerr"] for g in fast]))

    # --------------------------------------------------------- the present
    costs = [c for c in frm if c]
    if sf[63]:
        ck("D3 present ran", len(costs) == sf[63],
           "%d presents, %d cost samples" % (sf[63], len(costs)))
        ck("D4 present cost is not catastrophic",
           pct(costs, 0.50) / float(cpms) <= BOUND_PRESENT_P50_MS,
           "min %.4f p50 %.4f p90 %.4f max %.4f ms, bound %.1f"
           % (min(costs) / float(cpms), pct(costs, 0.50) / float(cpms),
              pct(costs, 0.90) / float(cpms), max(costs) / float(cpms),
              BOUND_PRESENT_P50_MS))
    return out


def shade_probe():
    """MAJOR 6, the OTHER half: does the parameter exist to be passed?

    NOCTIS-0.CPP:1151 is shade(unsigned char far *palette_buffer, ...) and 14
    of its 21 call sites pass surface_palette, not tmppal -- so a shade that
    can only write pal6 cannot express two thirds of the game's calls, and
    srfpal6/retpal6, the buffers whose whole purpose is to stop fades
    COMPOUNDING, are dead weight no test touches.

    A build failure is the RESULT, not a harness problem: w5shade.txt asks
    for [SHdstb], and a library with no such parameter cannot compile it.
    """
    src = os.path.join(SAND, "w5shade.txt")
    out = os.path.join(SAND, "fb-out.bin")
    for stale in (out, os.path.splitext(src)[0] + ".exe"):
        if os.path.exists(stale):
            os.remove(stale)
    rc, note = lh.build(src, timeout_sec=120)
    if rc != 0:
        log = [l.strip() for l in lh.errorlog_for(src).strip().splitlines() if l.strip()]
        return (P7B, False, "w5shade.txt does not compile: %s"
                % (log[-1] if log else note.strip().replace("\n", " | ")))
    rc, note, blob = lh.run(os.path.splitext(src)[0] + ".exe", out, timeout_sec=60)
    if blob is None:
        return (P7B, False, note)
    D = S.by_kind(S.read_fbdump(blob))
    pal6, srf = D[S.KPAL6][0], D[S.KPAL6][1]
    model = S.Palette()
    model.shade(0, 16, (0, 0, 0), (60, 40, 20))
    wrote = [i for i in range(48) if srf[i] != model.pal6[i]]
    kept = (pal6[0], pal6[1], pal6[2]) == (41, 42, 43)
    return (P7B, (not wrote) and kept,
            "srfpal6 differs from the model in %d of 48 components; pal6's "
            "sentinel reads %s (want (41, 42, 43) - untouched)"
            % (len(wrote), (pal6[0], pal6[1], pal6[2])))


# ------------------------------------------------------------- sensitivity
# Every check must be provably breakable, and the proof is one of two kinds.
#
#   A deliberately broken BUILD is the strong kind: a real defect, one edit,
#   and the named check has to notice. Twenty-two of those are built.
#
#   A one-unit PERTURBATION of the reference dump is the cheap kind: it shows
#   the grader is not blind to the field it claims to read. It costs no build
#   and runs on every pass, including --quick.
#
# A check with NEITHER is reported by name and fails the run. That is the
# rule Wave 5's canary check would have died on.

def _units(blob):
    u = list(struct.unpack("<%dI" % (len(blob) // 4), blob))
    idx, i = [], 0
    while i < len(u):
        idx.append((u[i + 2], i + 16, u[i + 5]))
        i += 16 + u[i + 5]
    return u, idx


def _at(idx, kind, nth=0):
    hits = [e for e in idx if e[0] == kind]
    return hits[nth][1]


def _repack(u):
    return struct.pack("<%dI" % len(u), *[x & S.M32 for x in u])


def perturbations(blob):
    """(check that must fail, description, mutated blob), one unit each."""
    u0, idx = _units(blob)
    sf = _at(idx, S.TWKSLF)
    cpms = u0[sf + 41]
    tick = _at(idx, S.KTICK)
    ntick = [e for e in idx if e[0] == S.KTICK][0][2] // 3
    hor = _at(idx, S.TWKHOR)
    msk = _at(idx, S.TWKMSK)
    srv = _at(idx, S.KSRVL)

    def bump(where, delta=1):
        u = list(u0)
        u[where] = (u[where] + delta) & S.M32
        return _repack(u)

    def setv(where, value):
        u = list(u0)
        u[where] = value & S.M32
        return _repack(u)

    def kindfield(kind, nth=0):
        """The header's `kind` unit for the nth record of that kind."""
        return _at(idx, kind, nth) - 16 + 2

    return [
        ("D0 dump parses", "the first record's magic corrupted", setv(0, 0)),
        ("D1 all records present", "the zone record re-labelled as kind 99",
         setv(kindfield(S.KZONE), 99)),
        ("D2 probe identifies itself", "the probe's self-magic zeroed",
         setv(sf, 0)),
        ("L4 pad and region count", "PADU misreported", bump(sf + 56)),
        ("L1 region table matches the derived layout",
         "one unit of the region table +1", bump(_at(idx, S.KLAY) + 5)),
        ("L3 workspace top matches", "NWTOP +1", bump(sf + 1)),
        ("L5 pvfile still holds 409 polygons", "polygon count +1", bump(sf + 58)),
        ("Z1 the zone table matches the derived one",
         "one zone's owner +1", bump(_at(idx, S.KZONE) + 22)),
        ("Z2 guard and allowance are disjoint and cover every pad unit",
         "the zone count misreported", bump(sf + 78)),
        ("B1 char store wraps", "one byte-semantics bit set", bump(sf + 2)),
        ("B2 one item per unit", "the one-per-unit flag set", setv(sf + 3, 1)),
        ("B3 8 to 32 sign extension", "sx8(192) off by one", bump(sf + 5)),
        ("Q1 quadrant bitfields", "one quadrant bit set", setv(sf + 4, 1)),
        ("A1 objectschart is ruinschart", "the shared byte +1", bump(sf + 9)),
        ("A2 globes.map is the sea texture", "the texel read +1", bump(sf + 15)),
        ("A3 digimap2 is split and survives", "digimap2[7] +1", bump(sf + 16)),
        ("A4 p_background becomes s_background", "the swapped read +1", bump(sf + 18)),
        ("A5 txtr re-bases by a byte amount", "the re-based read +1", bump(sf + 21)),
        ("C1 the canary record is what the walker produced",
         "ONE UNIT of the witness read-back +1", bump(_at(idx, S.KCAN) + 5)),
        ("C2 the clean workspace produces no violation and no expectation",
         "the clean pass reports one violating unit", setv(sf + 23, 1)),
        ("C3 the two low pads are guarded",
         "the low-pad probe reports one hit instead of two", setv(sf + 25, 1)),
        ("O2 digit_at's six units are counted, not flagged",
         "five of the six legitimate units counted", setv(sf + 28, 5)),
        ("O3 loadpv's one unit past pvfile is counted, not flagged",
         "the allowance not counted", setv(sf + 31, 0)),
        ("O3b one unit further IS a violation",
         "the violation reported one unit off", bump(sf + 71)),
        ("O4 class C: the sea texture reads its DOS neighbour",
         "the neighbour's marker +1", bump(sf + 33)),
        ("O5 class A: adapted is a full segment plus four",
         "adapted[65536] +1", bump(sf + 34)),
        ("M1 the mask is reached exactly as often as the model says",
         "one wrap not counted", bump(msk + 1, -1)),
        ("M2 spot folds at the 16-bit DI", "spot's delta +1", bump(msk + 12)),
        ("M3 cirrus folds one step earlier, in BX",
         "cirrus's delta +1", bump(msk + 14)),
        ("M4 the two deltas differ, so one mask point cannot serve both",
         "cirrus's delta set equal to spot's", setv(msk + 14, 65536)),
        ("M5 every masked address is contained",
         "one containment failure", setv(msk + 17, 1)),
        ("P1 pal6 is exact", "one six-bit component +1",
         bump(_at(idx, S.KPAL6, 0) + 500)),
        ("P2 curpal6 is exact", "one uploaded component +1",
         bump(_at(idx, S.KPAL6, 1) + 74)),
        ("P3 LUT is exact", "one LUT entry +1", bump(_at(idx, S.KLUT) + 13)),
        ("P5 an out-of-range filter is recorded", "PVrange +1", bump(sf + 37)),
        ("P6 the background colour cycle", "one cycled unit +1",
         bump(_at(idx, S.TWKSKY) + 100)),
        ("F1 adapted page is exact", "ONE PIXEL of the hidden page +1",
         bump(_at(idx, S.KPAGE, 0) + 12345)),
        ("F2 adaptor page is exact", "ONE PIXEL of the visible page +1",
         bump(_at(idx, S.KPAGE, 1) + 12345)),
        ("F3 expanded framebuffer is exact", "ONE UNIT of the framebuffer +1",
         bump(_at(idx, S.TWKFB) + 12345)),
        ("H1 the whole servo replay matches the independent model",
         "ONE scenario's converged cpms +1", bump(hor + 2)),
        ("H2 the windowed servo converges and holds across the wrap",
         "scenario 0 never straddles the wrap", setv(hor + 4, 0)),
        ("H3 THE CONTROL: the original estimator is destroyed by the same data",
         "the original estimator survives scenario 0", setv(hor + 11, 0)),
        ("H4 the rounded divide leaves no systematic bias",
         "the jittered scenario's error sum driven negative",
         setv(hor + 7 * 20 + 16, (-1000) & S.M32)),
        ("H5 the acceptance band is signed and two-sided",
         "the midnight straddle accepted instead of refused",
         setv(_at(idx, S.TWKBND) + 2, S.SVWAPPLY)),
        ("H6 the clamp step has a floor, so no state is absorbing",
         "the slow-counter scenario never leaves its seed",
         setv(hor + 8 * 20 + 2, 58)),
        (P7, "ONE component of surface_palette +1",
         bump(_at(idx, S.KPAL6, 2) + 7)),
        (H7, "the fast-host rejection evidence is falsified",
         setv(hor + 6 * 20 + 3, 0)),
        ("T4 the servo actually ran in the soak, and every sample was accepted",
         "one servo sample rejected as too long", setv(srv + 5, S.SVWLONG)),
        ("T5 period decomposition", "55*cpms off by one", bump(sf + 44)),
        ("T6 advance battery is exact", "one synthetic deadline +1",
         bump(_at(idx, S.TWKADV) + 77)),
        ("T7 wait predicate across the wrap", "one predicate failure", setv(sf + 38, 1)),
        ("T1 every deadline is on the rational grid", "one logged deadline +1",
         bump(tick + 3 * (ntick // 2) + 1)),
        # set the fire time from that tick's OWN deadline rather than nudging
        # it by -1: an overshoot that was already a count or two positive
        # absorbs a -1 and the perturbation silently stops perturbing.
        ("T2 no tick ever fires early", "one tick fires one count early",
         setv(tick + 3 * (ntick // 2), u0[tick + 3 * (ntick // 2) + 1] - 1)),
        ("T3 gaps are whole periods and hitches skip", "the skip count zeroed",
         setv(sf + 47, 0)),
        ("T9 median overshoot", "every tick 1 ms late",
         _repack([v + cpms if (i >= tick and i < tick + 3 * ntick
                               and (i - tick) % 3 == 0) else v
                  for i, v in enumerate(u0)])),
        # T9's perturbation puts every tick 1 ms late, which leaves p90 at
        # 0.998 and INSIDE its 1.5 ms bound - so T9 does not prove T10. Every
        # fifth tick 2 ms late moves p90 and not p50, which is the whole
        # reason the two bounds are separate.
        ("T10 p90 overshoot", "every fifth tick 2 ms late",
         _repack([v + 2 * cpms if (i >= tick and i < tick + 3 * ntick
                                   and (i - tick) % 3 == 0
                                   and ((i - tick) // 3) % 5 == 0) else v
                  for i, v in enumerate(u0)])),
        ("T11 worst overshoot", "one tick 45 ms late",
         bump(tick + 3 * (ntick // 2), 45 * cpms)),
        ("T12 the wall clock agrees with the grid",
         "the wall clock says the soak took 200 ms longer", bump(sf + 87, 200)),
    ]


# Checks that no perturbation and no sabotage can reach, with the reason.
# Each one is a property of the 1996 sources or of the harness rather than of
# the port, or is a bound whose sabotage would be a timing manipulation.
NOT_PERTURBED = {
    "D3 present ran":
        "display variant only - not present in the reference dump",
    "D4 present cost is not catastrophic": "display variant only",
    "L0 NOCTIS-D.H is readable":
        "reads the 1996 clone, not the dump; there is no unit to perturb",
    "L2 farmalloc order matches NOCTIS.CPP":
        "reads NOCTIS.CPP, not the dump; S04 moves a size and L1 catches it",
    "P4 upload-from-zero leaves a stale band":
        "proved by sabotage S16, an upload starting at `first`",
    "P7b the destination parameter exists at all":
        "a BUILD failure is its result - a library with no [SHdstb] cannot "
        "compile w5shade.txt, and that is the finding, not a broken harness",
}


def sensitivity(chk, blob):
    """Every check in grade() is either sabotaged by a build or broken here."""
    base = dict((n, ok) for n, ok, _ in grade(blob))
    covered = set(want for _, _, _, _, want, _ in SABOTAGE)
    proved = set()
    for want, what, mutated in perturbations(blob):
        res = dict((n, (ok, d)) for n, ok, d in grade(mutated))
        if want not in res:
            chk.ok(False, "sensitivity: %s" % want, "the check did not run")
            continue
        ok, detail = res[want]
        also = sorted(n for n, (o, _) in res.items()
                      if not o and n != want and base.get(n, True))
        chk.ok(not ok, "sensitivity: %s notices [%s]" % (want, what),
               "%s%s" % (detail, ("; so does %s" % also) if also else ""))
        proved.add(want)
    missed = sorted(n for n, ok in base.items()
                    if ok and n not in proved and n not in covered
                    and n not in NOT_PERTURBED)
    chk.ok(not missed, "every graded check is proved breakable",
           "unproved: %s" % missed)
    unreached = sorted(n for n in NOT_PERTURBED if n not in base)
    chk.note("not perturbable, with the reason for each: %s"
             % "; ".join("%s (%s)" % (k, v) for k, v in sorted(NOT_PERTURBED.items())
                         if k in base or k in unreached))
    # and the original still grades exactly as it did before any of that
    after = dict((n, ok) for n, ok, _ in grade(blob))
    chk.ok(after == base, "the reference dump grades identically afterwards",
           "%d checks, %d changed"
           % (len(base), sum(1 for n in base if base[n] != after.get(n))))


# --------------------------------------------------------------------- main

def main():
    quick = "--quick" in sys.argv
    nodisp = "--nodisp" in sys.argv
    chk = lh.Check("WAVE 5b - the CORRECTED buffer model, framebuffer and tick")

    # ---------------------------------------------- the mechanical audit
    # Runs FIRST, needs nothing built, and takes about two seconds. Wave 5
    # shipped a check that could not fail; Wave 5b was told to remove it and
    # reproduced it three times; Wave 5c stated the rule in three documents
    # and shipped two more. This is the rule executed rather than stated: it
    # inlines every check condition in noctis-harness/ and tests/, evaluates
    # it over random assignments, and fails when one of them cannot come out
    # false. See tests/w5audit.py.
    w5audit.run(chk)

    if not os.path.isdir(S.NOCTIS_SRC):
        chk.ok(False, "the 1996 source clone is present",
               "%s is missing; the layout is derived from it, so this test "
               "cannot run" % S.NOCTIS_SRC)
        return chk.done()

    before = source_hashes()
    pri = pristine_state()
    if pri is None:
        chk.note("PRISTINE.sha256 is missing - the toolchain was not verified")
    else:
        chk.ok(pri[1] == 0, "toolchain PRISTINE before any build",
               "%d digests match, %d do not" % pri)

    fresh_sandbox()
    chk.note("sandbox rebuilt from work/fb*.txt and tests/w5probe.txt: %s" % SAND)

    # ------------------------------------------------ the reference build
    path = write_variant("w5probe", [])
    blob, note = build_and_run(path, "w5probe", timeout=180)
    # ONE call, with the real condition in it. This used to be an ok(False)
    # early-out followed by an ok(True), and the ok(True) was an unconditional
    # pass -- tests/w5audit.py rule A, the same shape as fb_stick.py:352.
    if not chk.ok(blob is not None, "reference probe builds and runs", note):
        return chk.done()

    results = grade(blob)
    results.append(shade_probe())

    names = [n for n, _, _ in results]
    for name, ok, detail in results:
        if name in KNOWN_OPEN:
            # XFAIL. Asserted to be STILL BROKEN, with the boundary at which
            # it breaks, so that fixing one cannot leave the documentation
            # stale. A check that starts passing FAILS here and says what to
            # delete. Two remain, and neither was in scope for this wave to
            # close on the evidence available.
            chk.ok(ok, "XFAIL %s" % name,
                   ("STILL OPEN, and here is the measurement: %s" % detail) if ok else
                   ("NO LONGER REPRODUCIBLE - remove it from KNOWN_OPEN and "
                    "from BUFFERMODEL.md's open items. %s" % detail))
        else:
            chk.ok(ok, name, detail)

    for name, why in sorted(KNOWN_OPEN.items()):
        if name not in names:
            chk.ok(False, "XFAIL %s" % name, "the check did not run at all")
        else:
            chk.note("still open: %s" % why)

    # ------------------------------------------------- prove the checks bite
    sensitivity(chk, blob)

    # -------------------------------------------------------- the display
    if nodisp:
        chk.note("--nodisp: the on-screen present was not exercised at all")
    else:
        subs = [(k, v) for k, v in DISPLAY.items()] + [(k, v) for k, v in SHORT.items()]
        dpath = write_variant("w5disp", subs)
        dblob, dnote = build_and_run(dpath, "w5disp", timeout=120)
        if chk.ok(dblob is not None, "display probe builds and runs", dnote):
            for name, ok, detail in grade(dblob):
                if name.startswith(("D3", "D4", "F3")):
                    chk.ok(ok, "display: " + name, detail)

    # ------------------------------------------------------ the sabotages
    if quick:
        chk.note("--quick: the %d negative controls were NOT built. That is "
                 "the part that shows the graders can fail against a real "
                 "defect rather than against a mutated dump, so this run is "
                 "NOT A PASS." % len(SABOTAGE))
        return finish(chk, before, pri)

    chk.note("building %d deliberately broken variants, one edit each" % len(SABOTAGE))
    for tag, target, old, new, want, what in SABOTAGE:
        if target == "w5probe.txt":
            spath = write_variant("w5" + tag.lower(),
                                  [(old, new)] + list(SHORT.items()))
        else:
            # edit a COPY of the pristine source, never the source: finish()
            # re-hashes work/ afterwards and fails if this slipped.
            pristine = open(os.path.join(WORK, target), "r", encoding="utf-8").read()
            broken = edit(pristine, old, new, target)
            libname = target[:-4] + tag
            with open(os.path.join(SAND, libname + ".txt"), "w",
                      encoding="utf-8", newline="") as fh:
                fh.write(broken)
            spath = write_variant("w5" + tag.lower(),
                                  [("\t%s;\n" % target[:-4], "\t%s;\n" % libname)]
                                  + list(SHORT.items()))
        blob, note = build_and_run(spath, "w5" + tag.lower(), timeout=120)
        label = "%s caught by [%s]" % (tag, want)
        # ONE verdict per sabotage, computed. The three branches used to end in
        # ok(True) / ok(False) / ok(not ok), and the first of those was an
        # unconditional pass in the count (w5audit rule A).
        if blob is None:
            caught, detail = True, "%s -- did not even produce a dump (%s)" % (
                what, note.split(":")[0])
        elif want not in (res := dict((n, (ok, d)) for n, ok, d in grade(blob))):
            caught, detail = False, "%s -- the grader never reached [%s]" % (what, want)
        else:
            ok, why = res[want]
            also = [n for n, (o, _) in res.items()
                    if not o and n != want and n not in KNOWN_OPEN]
            caught = not ok
            detail = "%s -- %s%s" % (what, why,
                                     ("; also caught by %s" % also) if also else "")
        chk.ok(caught, label, detail)

    return finish(chk, before, pri)


def finish(chk, before, pri):
    """Restore-and-confirm: nothing this test read may have changed.

    Every sabotage was generated by copying a pristine source and editing the
    copy. If any of them had edited the original instead, the next run would
    grade a corrupted library and call it correct. So the inputs are re-hashed
    here, and main/ is re-verified against PRISTINE.sha256.
    """
    after = source_hashes()
    moved = sorted(k for k in before if before[k] != after.get(k))
    chk.ok(not moved, "every source this test read is byte-identical afterwards",
           "%d files re-hashed, moved: %s" % (len(before), moved))
    same = [n for n in LIBS
            if os.path.exists(os.path.join(SAND, n))
            and sha(os.path.join(SAND, n)) == sha(os.path.join(WORK, n))]
    chk.ok(len(same) == len(LIBS),
           "the sandbox copies still match work/ exactly",
           "%d of %d" % (len(same), len(LIBS)))
    if pri is not None:
        now = pristine_state()
        chk.ok(now == pri and now[1] == 0, "toolchain PRISTINE after every build",
               "%d match / %d do not (was %d / %d)" % (now + pri))
    return chk.done()


if __name__ == "__main__":
    lh.main_guard(main)
