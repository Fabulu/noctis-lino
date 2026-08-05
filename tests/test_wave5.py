"""Wave 5: the buffer model, the framebuffer and the 54.9254 ms tick.

    python tests/test_wave5.py            everything (about 4 minutes)
    python tests/test_wave5.py --quick    skip the sabotages - NOT A PASS
    python tests/test_wave5.py --nodisp   skip the one probe that opens a window

WHAT THIS GUARDS
================
Three things, and they are graded by three different mechanisms.

1.  THE BUFFER MODEL - one Noctis byte per 32-bit lino unit, one flat
    workspace in farmalloc order, aliases kept or split by the register in
    BUFFERMODEL.md section 5, overruns classified A/B/C.  Graded by
    *construction*: tests/w5spec.py parses the nine sizes out of
    NOCTIS-D.H and the allocation order out of NOCTIS.CPP:2163-2172 and
    derives the layout, and the lino dumps the region table its own
    canary walker actually uses.  Neither derives from the other.  The
    aliases are then exercised in both directions - written through one
    name, read through the other - and every overrun class is fired at a
    known offset and the guard's answer recorded.

2.  THE FRAMEBUFFER - the index pages, the palette pipeline and the
    expand.  Graded EXACTLY, unit for unit, against a Python model of
    tavola_colori / shade / the LUT written from NOCTIS-0.CPP:179 and
    :1151.  All 768 six-bit components, all 256 LUT entries, all 64,000
    pixels of both pages and all 64,000 units of the expanded
    framebuffer, on every run.  Nothing is sampled and nothing is
    checksummed: a single wrong pixel fails.

3.  THE TICK - graded in two halves, and the split is the point.  The
    *arithmetic* half has zero tolerance: the exact rational period, the
    carried accumulator, the deadline grid and the wrap predicate are all
    integer identities and are compared exactly.  Only the *scheduling*
    half - how late a tick actually fires - is a timing measurement, and
    only that half carries a bound.

NOTHING IS GRADED AGAINST A STORED ARTIFACT.  Both sides are recomputed
on every run: the lino side is rebuilt from work/fb*.txt, and the Python
side is re-derived from the 1996 sources.  There is no golden .bin.

THE TIMING BOUNDS, AND WHY THESE
================================
Only four checks are noisy, and all four measure OVERSHOOT - how far
past its deadline a tick actually fired - never a frame cost and never a
throughput.  Overshoot is the right quantity because it is structurally
bounded for a correct implementation: the deadline sequence is exact
integer arithmetic, so the only error is the granularity of the final
spin, and it does not accumulate.  Measured on this machine over 200
ticks under a full page-build + expand load with a 60 ms hitch injected
every 37 ticks:

    p50 overshoot    0.000000 - 0.000000 ms    bound  0.50 ms
    p90 overshoot    0.000000 - 0.000111 ms    bound  1.50 ms
    max overshoot    3.10 - 11.50 ms           bound 40.0 ms
    total drift      0.00003 - 0.0105 ms       bound  5.00 ms / 200 ticks

Ranges, not points: four runs of the same binary on this machine gave the
spreads shown, which is why nothing here is set at "measured x 2".
Each bound is instead set where a real regression lands:

  * p50 0.50 ms catches using SLEEP as the tick source.  PORTPLAN
    measured SLEEP returning 62.75 ms for a 55 ms request; that is a p50
    overshoot near 7.8 ms, 15x the bound, against a measured p50 of zero
    counts.
  * p90 1.50 ms catches dropping the spin margin from 16 ms to 4 ms.
    Recon C measured that regime at 17.6 ms peak-to-peak jitter with
    60 of 120 ticks over +1 ms, so its p90 is above 2 ms.
  * max 40.0 ms is deliberately a BACKSTOP, not a discriminator.  A
    single overshoot is one Windows scheduling stall and this machine
    produced 3.10, 5.01, 8.15 and 11.50 ms on four runs, so a tight
    bound here would be flaky rather than informative.  40 ms is the
    last value below one whole period: an overshoot of a period or more
    means the grid point was consumed, and T3 catches that exactly.
    The sharp tests for the wait path are p50 and p90.
  * total drift 5.00 ms over 200 ticks is a redundant backstop.  It is
    deliberately loose, because the sharp test for drift is not a bound
    at all: T1 requires every logged deadline to sit exactly on the
    rational grid, which a re-basing implementation fails on the first
    hitch.  A bound tight enough to catch re-basing on its own would be
    below the +0.002 to +0.004 ms/tick that re-basing actually costs on
    this machine, which is inside this machine's noise.

The three *shape* facts about the tick are NOT bounds - they are exact:
every logged deadline lies on the grid, no tick ever fires early, and
every inter-fire gap is a whole number of periods in {1, 2, 3}.  A frame
that overruns loses a whole tick and re-aligns, which is fidelity, not
timing: the original busy-waits for the next EDGE of a free-running
counter (NOCTIS-0.CPP:6025-6038), so its frame rate is 18.2065/k and
never anything between.

WHAT IS NOT COVERED - stated plainly, not implied
=================================================
  * ANYTHING THAT NEEDS A RENDERER.  No polygons, no globes, no
    textures, no frame compared against DOSBox-X or against the game's
    own BMP.  txtr is modelled as an offset variable and the 16-bit
    texel address is unit-tested, but nothing is textured.  Wave 5 has
    no renderer, so there is no frame to compare.
  * WHETHER ANY CLASS-C READ-OVERRUN IS EVER REACHED WITH REAL DATA.
    This test proves the layout puts the neighbour DOS put there, and
    that a read past n_globes_map lands on s_background.  It does not
    and cannot prove that the game ever performs that read.
  * "LOOKS RIGHT".  Nothing here is eyeballed.  The one probe that opens
    a window (--nodisp turns it off) is graded on the bytes it produces,
    not on what appears on screen; a human may look, and the look is not
    evidence.  Whether the 320x200 window shows the right picture is not
    covered by anything in this suite.
  * PRESENT COST.  The raw per-present costs are printed but only a
    catastrophic bound is graded (p50 under 10 ms against 2.0 measured),
    because the figure is not reproducible: the same binary measured
    1.47 / 2.60 / 4.78 ms p50 for a frame across three runs of this
    machine.  Quote ranges, never points.
  * LONG SESSIONS.  The longest soak here is 200 ticks, 11 seconds.
  * work/fbshell.txt AND work/fbmain.txt.  This test links the three
    libraries (fbmem, fbpal, fbtick) and its own shell, w5probe.txt.
    The Wave 5 shell's own present path is not the subject; the rule it
    got wrong is (see F2).

THREE CHECKS ARE EXPECTED TO FAIL, AND ARE ASSERTED TO
======================================================
The code as shipped violates the settled model in three places.  Each is
listed in KNOWN_OPEN below with a file:line and the BUFFERMODEL.md open
item it belongs to, and each is graded XFAIL: the test requires it to
still be broken, and FAILS if it starts passing, so that fixing one
cannot silently leave the documentation stale.  They are not silently
skipped and they are not quietly passed.

THE NEGATIVE CONTROLS
=====================
Thirteen deliberately broken builds, each one edit, each generated from
the pristine source on every run and each required to be CAUGHT by a
named check.  Eleven edit a library; two edit the probe itself, because
two of the rules being guarded - the expand must not write the index
page, and tinta/escrescenze stay at 63,996 - live in the present path.
"""

import hashlib
import os
import shutil
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import linoharness as lh          # noqa: E402
import w5spec as S                # noqa: E402

SAND = os.path.join(lh.GEN, "w5")
WORK = lh.WORK

LIBS = ("fbmem.txt", "fbpal.txt", "fbtick.txt")
FPLIBS = ("fpabi.txt", "fpctl.txt", "fpx87.txt", "fpconv.txt")

# ------------------------------------------------------------- timing bounds
# See the header for why each one is where it is.
BOUND_P50_MS = 0.50
BOUND_P90_MS = 1.50
BOUND_MAX_MS = 40.0
BOUND_DRIFT_MS = 5.00
BOUND_PRESENT_P50_MS = 10.0

# ------------------------------------------------ the three known-open items
P7 = "P7 shade takes its destination buffer"

KNOWN_OPEN = {
    "O6 low pads are guarded": (
        "fbmem's MEM poison/check pads walks rtab's nine regions only, so "
        "nw[0..31] - the two pads below n_offsets_map - are guarded by "
        "nothing. BUFFERMODEL.md section 4.1, open item 1."),
    "T8 servo survives the counter wrap": (
        "fbtick.txt:196 brackets the servo against the START of the run. "
        "[Counts] is 32 bits and wraps at 2^32/cpms = 477 s, so from 7.95 "
        "minutes on it reads a wrapped difference and ratchets cpms down by "
        "1% every 14 s. BUFFERMODEL.md section 8 rule 6, open item 2."),
    P7: (
        "fbpal.txt:349 hard-codes pal6 as shade()'s destination. "
        "NOCTIS-0.CPP:1151 declares shade(unsigned char far *palette_buffer, "
        "...) and 14 of its 21 call sites pass surface_palette. "
        "BUFFERMODEL.md section 6, open item 5."),
}

# --------------------------------------------------------------- the variants

SHORT = {"TWNTICK\t= 200;": "TWNTICK\t= 48;",
         "TWHITCH\t= 37;": "TWHITCH\t= 11;",
         "TWANCH\t= 4096;": "TWANCH\t= 256;",
         "TWCALMS\t= 2500;": "TWCALMS\t= 300;"}

DISPLAY = {"\tunit = 32;":
           "\tunit = 32;\n\tdisplay width = 320;\n\tdisplay height = 200;",
           "\t=> TW sky cycle;\n\n\t=> TW emit;":
           "\t=> TW sky cycle;\n\n\t=> TW present;\n\t=> TW emit;"}

# Each sabotage: (which file, exact old text, exact new text, the check that
# must catch it, one line saying what it models).
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
     "\t? C = POISON -> MEM cp ok;",
     "\t-> MEM cp ok;",
     "O2 class B: digit_at txtr[-6..-1]",
     "a pad canary that can never fire"),
    ("S04", "fbmem.txt",
     "ZNGLB\t= 32768;",
     "ZNGLB\t= 22586;",
     "L1 region table matches the derived layout",
     "n_globes_map sized gl_bytes, dropping gl_brest"),
    ("S05", "fbtick.txt",
     "\tA = [TKnow]; A - [TKdeadline];\n\t? A < 0 -> TK islate no;",
     "\tA = [TKnow];\n\t? A '< [TKdeadline] -> TK islate no;",
     "T7 wait predicate across the wrap",
     "an unsigned timestamp compare instead of the sign of the difference"),
    ("S06", "fbtick.txt",
     "\tA = [TKbase]; A - B;\n\t[TKdeadline] + A;",
     "\tA = [TKbase]; A - B;\n\t[Timer Command] = READ COUNTS; isocall;"
     "\n\tC = [Counts]; C + A; [TKdeadline] = C;",
     "T6 advance battery is exact",
     "a deadline re-based on the clock instead of accumulated"),
    ("S07", "fbtick.txt",
     "\t=> TK advance;\n\t=> TK skip;\n\t=> TK wait;",
     "\t=> TK advance;\n\t=> TK wait;",
     "T3 gaps are whole periods and hitches skip",
     "no skip-to-grid: an overrunning frame catches up"),
    ("S08", "fbpal.txt",
     "C & 63; C * 4; C < 16;",
     "C & 63; B = C; B > 4; C * 4; C | B; C < 16;",
     "P3 LUT is exact",
     "the LUT built with (v<<2)|(v>>4) instead of v*4"),
    ("S09", "fbpal.txt",
     "\tA = pal6; D = curpal6;\n\tB = [PUn]; B * 3;",
     "\tA = pal6; D = curpal6; C = [PVfirst]; C * 3; A + C; D + C;"
     "\n\tB = [PUn]; B - [PVfirst]; B * 3;",
     "P2 curpal6 is exact",
     "an upload that starts at `first` instead of at colour zero"),
    ("S10", "fbpal.txt",
     "\t=> FToIntChop;",
     "\t=> FToIntNear;",
     "P1 pal6 is exact",
     "shade() rounding to nearest instead of chopping"),
    ("S11", "fbpal.txt",
     "\t[SHb] = 63; -> PAL sc store;",
     "\t[SHb] = 0; -> PAL sc store;",
     "P1 pal6 is exact",
     "shade()'s inverted clamp inverted the other way"),
    ("S12", "w5probe.txt",
     "\tC = [D];\tC + pal; C = [C]; [E] = C;",
     "\tC = [D];\tB = C; B & 192; C + 1; C & 63; C + B; [D] = C;"
     "\n\t\t\tC + pal; C = [C]; [E] = C;",
     "F2 adaptor page is exact",
     "LINOBUF section 5.4's colour cycle fused into the expand"),
    ("S13", "w5probe.txt",
     "\tA = nw; A + RADPT; A + 63996;",
     "\tA = nw; A + RADPT; A + 64000;",
     "F1 adapted page is exact",
     "niv-lr's relocation of tinta/escrescenze to 64000"),
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
    for n in ("w5probe.txt", "w5shade.txt", "w5spec.py"):
        out["tests/" + n] = sha(os.path.join(HERE, n))
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


def build_and_run(path, tag, timeout=90):
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

    need = {S.KLAY: 1, S.KCAN: 1, S.TWKSLF: 1, S.KPAL6: 2, S.KLUT: 1,
            S.TWKADV: 1, S.TWKSRV: 1, S.TWKSKY: 1, S.TWKFRM: 1,
            S.KTICK: 1, S.KPAGE: 2, S.TWKFB: 1}
    missing = [k for k, n in need.items() if len(D.get(k, [])) < n]
    if missing:
        ck("D1 all records present", False, "missing kinds %s" % missing)
        return out
    ck("D1 all records present", True)

    sf = D[S.TWKSLF][0]
    lay, can = D[S.KLAY][0], D[S.KCAN][0]
    pal6, curpal6, lut = D[S.KPAL6][0], D[S.KPAL6][1], D[S.KLUT][0]
    adv, srv, sky, frm = D[S.TWKADV][0], D[S.TWKSRV][0], D[S.TWKSKY][0], D[S.TWKFRM][0]
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

    # ------------------------------------------------------ the overruns
    ck("O1 canary clean before anything is broken",
       (sf[22], sf[23]) == (0, 0), "fired %d, %d units differ" % (sf[22], sf[23]))
    ck("O1b canary table dumped clean",
       all(can[i] == can[i + 1] for i in range(0, 18, 2)),
       "%d of 9 regions mismatch" % sum(1 for i in range(0, 18, 2) if can[i] != can[i + 1]))
    pbg = L["p_background"]
    ck("O2 class B: digit_at txtr[-6..-1]",
       (sf[26], sf[27], sf[28]) == (pbg["id"] + 1, 6, L["p_surfacemap"]["base"] - 6),
       "fired %d, %d units, at %d (want %d, 6, %d)"
       % (sf[26], sf[27], sf[28], pbg["id"] + 1, L["p_surfacemap"]["base"] - 6))
    pvf = L["pvfile"]
    ck("O3 class B: one unit past pvfile",
       (sf[29], sf[30], sf[31]) == (pvf["id"] + 1, 1, pvf["end"]),
       "fired %d, %d units, at %d (want %d, 1, %d)"
       % (sf[29], sf[30], sf[31], pvf["id"] + 1, pvf["end"]))
    ck("O4 class C: the sea texture reads its DOS neighbour",
       (sf[32], sf[33]) == (0, 123),
       "texel 32768 (pad) %d, texel 32784 (s_background[0]) %d" % (sf[32], sf[33]))
    ck("O5 class A: adapted is a full segment plus four",
       (sf[34], sf[35], sf[36]) == (65, 68, 0),
       "adapted[65536] %d, adapted[65539] %d, the unit above %d"
       % (sf[34], sf[35], sf[36]))
    ck("O6 low pads are guarded", (sf[24], sf[25]) == (1, 2),
       "corrupting nw[3] and nw[20] after poisoning gave fired=%d n=%d; "
       "a guard covering all eleven pads gives fired>=1 n=2" % (sf[24], sf[25]))

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

    ck("T4 cpms is constant through the soak", sf[50] == 1,
       "%d servo log entries; the soak is %d ticks and the servo interval "
       "is %d" % (sf[50], sf[59], sf[51]))

    n = len(tlog) // 3
    now = [tlog[3 * i] for i in range(n)]
    dl = [tlog[3 * i + 1] for i in range(n)]
    if n < 8:
        ck("T1 every deadline is on the rational grid", False, "only %d ticks" % n)
        return out
    B = (dl[0] - S.grid(cpms, 1)) & S.M32
    ks, kbad, k = [], 0, 1
    for i in range(n):
        while ((B + S.grid(cpms, k)) & S.M32) != dl[i] and k < 6 * n + 16:
            k += 1
        if ((B + S.grid(cpms, k)) & S.M32) != dl[i]:
            kbad = n - i
            break
        ks.append(k)
    ck("T1 every deadline is on the rational grid", kbad == 0,
       "%d of %d deadlines are off the grid" % (kbad, n))
    if kbad:
        return out

    per = S.period_ms(cpms)
    over = [S.s32(now[i] - dl[i]) / float(cpms) for i in range(n)]
    mult = [ks[i] - ks[i - 1] for i in range(1, n)]
    ck("T2 no tick ever fires early", min(over) >= 0, "min overshoot %.6f ms" % min(over))
    ck("T3 gaps are whole periods and hitches skip",
       all(1 <= m <= 3 for m in mult) and sf[47] >= 3,
       "multiples %s, %d skips over %d ticks"
       % (sorted(set(mult)), sf[47], n))

    drift = (S.s32(now[-1] - now[0]) / float(cpms)) - (ks[-1] - ks[0]) * per
    ck("T9 median overshoot", pct(over, 0.50) <= BOUND_P50_MS,
       "p50 %.6f ms, bound %.2f" % (pct(over, 0.50), BOUND_P50_MS))
    ck("T10 p90 overshoot", pct(over, 0.90) <= BOUND_P90_MS,
       "p90 %.6f ms, bound %.2f" % (pct(over, 0.90), BOUND_P90_MS))
    ck("T11 worst overshoot", max(over) <= BOUND_MAX_MS,
       "max %.4f ms over %d ticks, bound %.1f" % (max(over), n, BOUND_MAX_MS))
    ck("T12 total drift", abs(drift) <= BOUND_DRIFT_MS,
       "%.6f ms over %d ticks (%d grid steps), bound %.2f"
       % (drift, n, ks[-1] - ks[0], BOUND_DRIFT_MS))

    # ---------------------------------------------------------- the servo
    srvbad = []
    for i in range(6):
        elapsed, cnt, ms, cin, new, cout = srv[i * 6: i * 6 + 6]
        if abs(S.s32(cout) - 8999) > 3:
            srvbad.append((elapsed, cnt, ms, cout))
    ck("T8 servo survives the counter wrap", not srvbad,
       "%d of 6 synthetic elapsed times drove cpms away from 8999: %s"
       % (len(srvbad), ["%dms -> %d" % (b[0], b[3]) for b in srvbad]))

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


def shade_probe(chk):
    """P7: does shade() write the buffer it was handed?

    A build failure is the RESULT, not a harness problem: w5shade.txt asks
    for [SHdstb], which is the parameter NOCTIS-0.CPP:1151 declares, and a
    library that has no such parameter cannot compile it.
    """
    src = os.path.join(SAND, "w5shade.txt")
    out = os.path.join(SAND, "fb-out.bin")
    for stale in (out, os.path.splitext(src)[0] + ".exe"):
        if os.path.exists(stale):
            os.remove(stale)
    rc, note = lh.build(src, timeout_sec=120)
    if rc != 0:
        log = [l.strip() for l in lh.errorlog_for(src).strip().splitlines() if l.strip()]
        return (P7, False, "w5shade.txt does not compile: %s"
                % (log[-1] if log else note.strip().replace("\n", " | ")))
    rc, note, blob = lh.run(os.path.splitext(src)[0] + ".exe", out, timeout_sec=60)
    if blob is None:
        return (P7, False, note)
    D = S.by_kind(S.read_fbdump(blob))
    pal6, srf = D[S.KPAL6][0], D[S.KPAL6][1]
    model = S.Palette()
    model.shade(0, 16, (0, 0, 0), (60, 40, 20))
    wrote = [i for i in range(48) if srf[i] != model.pal6[i]]
    kept = (pal6[0], pal6[1], pal6[2]) == (41, 42, 43)
    return (P7, (not wrote) and kept,
            "srfpal6 differs from the model in %d of 48 components; pal6's "
            "sentinel reads %s" % (len(wrote), (pal6[0], pal6[1], pal6[2])))


# ------------------------------------------------------------- sensitivity
# The thirteen sabotages prove that thirteen checks can fail. Everything else
# in grade() is proved the same way the reviewer proved the Wave 5 grader was
# blind: take the reference dump, change ONE unit, and require the named check
# to notice. A framebuffer check that survives a single wrong pixel is not a
# check. This costs no builds, so it runs on every pass.

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

    def bump(where, delta=1):
        u = list(u0)
        u[where] = (u[where] + delta) & S.M32
        return _repack(u)

    def setv(where, value):
        u = list(u0)
        u[where] = value & S.M32
        return _repack(u)

    P = [
        ("L1 region table matches the derived layout",
         "one unit of the region table +1", bump(_at(idx, S.KLAY) + 5)),
        ("L3 workspace top matches", "NWTOP +1", bump(sf + 1)),
        ("L5 pvfile still holds 409 polygons", "polygon count +1", bump(sf + 58)),
        ("B1 char store wraps", "one byte-semantics bit set", bump(sf + 2)),
        ("B2 one item per unit", "the one-per-unit flag set", setv(sf + 3, 1)),
        ("B3 8 to 32 sign extension", "sx8(192) off by one", bump(sf + 5)),
        ("Q1 quadrant bitfields", "one quadrant bit set", setv(sf + 4, 1)),
        ("A1 objectschart is ruinschart", "the shared byte +1", bump(sf + 9)),
        ("A2 globes.map is the sea texture", "the texel read +1", bump(sf + 15)),
        ("A3 digimap2 is split and survives", "digimap2[7] +1", bump(sf + 16)),
        ("A4 p_background becomes s_background", "the swapped read +1", bump(sf + 18)),
        ("A5 txtr re-bases by a byte amount", "the re-based read +1", bump(sf + 21)),
        ("O1 canary clean before anything is broken",
         "the clean check reports one unit differing", setv(sf + 23, 1)),
        ("O1b canary table dumped clean",
         "one canary actual != expected", bump(_at(idx, S.KCAN) + 3)),
        ("O2 class B: digit_at txtr[-6..-1]",
         "the overrun reported one unit off", bump(sf + 28)),
        ("O3 class B: one unit past pvfile",
         "the overrun reported one unit off", bump(sf + 31)),
        ("O4 class C: the sea texture reads its DOS neighbour",
         "the neighbour's marker +1", bump(sf + 33)),
        ("O5 class A: adapted is a full segment plus four",
         "adapted[65536] +1", bump(sf + 34)),
        ("O6 low pads are guarded",
         "the low-pad probe reports a hit (this one must PASS)",
         _repack([v if i != sf + 24 else 1 for i, v in
                  enumerate([w if j != sf + 25 else 2 for j, w in enumerate(u0)])])),
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
        ("T5 period decomposition", "55*cpms off by one", bump(sf + 44)),
        ("T6 advance battery is exact", "one synthetic deadline +1",
         bump(_at(idx, S.TWKADV) + 77)),
        ("T7 wait predicate across the wrap", "one predicate failure", setv(sf + 38, 1)),
        ("T4 cpms is constant through the soak", "two servo log entries",
         setv(sf + 50, 2)),
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
        ("T11 worst overshoot", "one tick 45 ms late",
         bump(tick + 3 * (ntick // 2), 45 * cpms)),
        ("T12 total drift", "the last tick 10 ms late",
         bump(tick + 3 * (ntick - 1), 10 * cpms)),
        ("T8 servo survives the counter wrap",
         "every synthetic servo case returns 8999 (this one must PASS)",
         _repack([8999 if (i >= _at(idx, S.TWKSRV)
                           and i < _at(idx, S.TWKSRV) + 36
                           and (i - _at(idx, S.TWKSRV)) % 6 == 5) else v
                  for i, v in enumerate(u0)])),
    ]
    return P


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
        expect_pass = want in KNOWN_OPEN     # these are broken already
        also = sorted(n for n, (o, _) in res.items()
                      if not o and n != want and base.get(n, True))
        chk.ok(ok == expect_pass, "sensitivity: %s notices [%s]" % (want, what),
               "%s%s" % (detail, ("; so does %s" % also) if also else ""))
        proved.add(want)
    missed = sorted(n for n, ok in base.items()
                    if ok and n not in proved and n not in covered
                    and not n.startswith(("D0", "D1", "D2", "D3", "D4", "L0", "L2",
                                          "L4", "P4", "T10")))
    chk.ok(not missed, "every graded check is proved breakable",
           "unproved: %s" % missed)
    chk.note("L0/L2/L4 are properties of the 1996 sources, not of the port, and "
             "are proved by the sabotage that changes a size (S04); P4 and T10 "
             "are proved by S09 and S07; D0-D4 fail by construction if the dump "
             "is missing or malformed.")
    # and the original still grades exactly as it did before any of that
    after = dict((n, ok) for n, ok, _ in grade(blob))
    chk.ok(after == base, "the reference dump grades identically afterwards",
           "%d checks, %d changed"
           % (len(base), sum(1 for n in base if base[n] != after.get(n))))


# --------------------------------------------------------------------- main

def main():
    quick = "--quick" in sys.argv
    nodisp = "--nodisp" in sys.argv
    chk = lh.Check("WAVE 5 - buffer model, framebuffer and the 54.9254 ms tick")

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
    blob, note = build_and_run(path, "w5probe", timeout=120)
    if blob is None:
        chk.ok(False, "reference probe builds and runs", note)
        return chk.done()
    chk.ok(True, "reference probe builds and runs", note)

    results = grade(blob)
    results.append(shade_probe(chk))

    names = [n for n, _, _ in results]
    for name, ok, detail in results:
        if name in KNOWN_OPEN:
            # XFAIL. Asserted to be broken, so that fixing one cannot leave
            # BUFFERMODEL.md's open list quietly out of date. A check that
            # starts passing FAILS here and says what to delete.
            chk.ok(not ok, "XFAIL %s is still open" % name,
                   ("STILL OPEN: %s" % detail) if not ok else
                   ("NOW PASSES - remove it from KNOWN_OPEN and from "
                    "BUFFERMODEL.md's open items. %s" % detail))
        else:
            chk.ok(ok, name, detail)

    for name, why in sorted(KNOWN_OPEN.items()):
        if name not in names:
            chk.ok(False, "XFAIL %s is still open" % name,
                   "the check did not run at all")
        else:
            chk.note("open: %s" % why)

    # ------------------------------------------------- prove the checks bite
    sensitivity(chk, blob)

    # -------------------------------------------------------- the display
    if nodisp:
        chk.note("--nodisp: the on-screen present was not exercised at all")
    else:
        subs = [(k, v) for k, v in DISPLAY.items()] + [(k, v) for k, v in SHORT.items()]
        dpath = write_variant("w5disp", subs)
        dblob, dnote = build_and_run(dpath, "w5disp", timeout=90)
        if dblob is None:
            chk.ok(False, "display probe builds and runs", dnote)
        else:
            chk.ok(True, "display probe builds and runs", dnote)
            for name, ok, detail in grade(dblob):
                if name.startswith(("D3", "D4", "F3")):
                    chk.ok(ok, "display: " + name, detail)

    # ------------------------------------------------------ the sabotages
    if quick:
        chk.note("--quick: the 13 negative controls were NOT built. "
                 "That is the part that shows the graders can fail, so this "
                 "run is not a pass.")
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
        blob, note = build_and_run(spath, "w5" + tag.lower(), timeout=90)
        label = "%s caught by [%s]" % (tag, want)
        if blob is None:
            chk.ok(True, label, "%s -- did not even produce a dump (%s)"
                   % (what, note.split(":")[0]))
            continue
        res = dict((n, (ok, d)) for n, ok, d in grade(blob))
        if want not in res:
            chk.ok(False, label, "%s -- the grader never reached [%s]" % (what, want))
            continue
        ok, detail = res[want]
        also = [n for n, (o, _) in res.items()
                if not o and n != want and n not in KNOWN_OPEN]
        chk.ok(not ok, label,
               "%s -- %s%s" % (what, detail,
                               ("; also caught by %s" % also) if also else ""))

    return finish(chk, before, pri)


def finish(chk, before, pri):
    """Restore-and-confirm: nothing this test read may have changed.

    Thirteen sabotages were generated during the run, every one of them by
    copying a pristine source and editing the copy. If any of them had edited
    the original instead, the next run would grade a corrupted library and
    call it correct. So the inputs are re-hashed here, and main/ is
    re-verified against PRISTINE.sha256.
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
