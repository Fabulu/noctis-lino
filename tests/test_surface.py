r"""Wave 7a: surface(), the orbital globe texture - NOCTIS-0.CPP:4766-5196.

WHAT THIS GRADES
    The 64,800-byte albedo map in p_background, the 32,400-byte cloud overlay
    in objectschart, the 64-entry palette block, the two interleaved random
    streams' per-phase draw accounting, the type-3 land-noise ADD, and the
    day/night terminator's three constants.  Nothing else: build_surface(),
    the ground terrain, the sky and SURFACE.BIN are Wave 7b and are not
    touched here.

WHAT THE ORACLE ACTUALLY IS - READ THIS BEFORE BELIEVING ANY "EXACT" BELOW
    There is NO 1996 artefact anywhere in this repository, and this test does
    not have one.  Exactly one NOCTIS.EXE exists on this machine and it is
    Noctis IV+ Release 2.3, a community fork.  The ten capture files under
    tests/gen/recon_w7a/out were lifted out of THAT binary's guest RAM by
    recon C under DOSBox-X.  So every row this file prints as EXACT means
    "byte-exact against NIV+ Release 2.3", never "against the 1996 binary".
    The argument that NIV+ 2.3's surface() is still vanilla's is documentary
    (no #ifdef, no fork marker, and WEIRDDOSHILLS defined but referenced
    nowhere) plus one confirming datum - the type-3 site really does read
    `add es:[di],bl` and not `=`.  It is not a byte-level diff against a
    stock executable, because there is nothing on this machine to diff
    against.

    noctis-iv-lr is DISQUALIFIED as an oracle for this function.  PORTPLAN
    records four divergences inside surface() itself, one of which - LR
    ASSIGNING the type-3 land noise where vanilla ADDS it - changes the
    albedo at the landing site and therefore the whole ground scenario.  This
    test grades that divergence directly (section D) instead of trusting
    either side about it.

    Consequently the strength of this wave is:  ONE binary-derived artefact
    per capture, plus THREE independent implementations agreeing on it, plus
    a per-stream draw audit.  Previous waves had more - Wave 4 was graded
    against DL.EXE's own output over 4,365 records, Wave 3 against the
    shipped STARMAP.BIN.  This one is weaker than those and the exit report
    says so.

THE THREE IMPLEMENTATIONS, AND WHERE EACH CAME FROM
    lino  work/su*.txt + work/fp/*   the DELIVERABLE.  Compiled here, from
                                     source, into tests/gen/w7a and run with
                                     the poll-and-kill runner.  Never graded
                                     from a stored .bin.
    spec  noctis-harness/su_spec.py  Python, transliterated from the DOS
                                     inline assembly, x87 modelled with exact
                                     rationals.
    cref  noctis-harness/su_ref.c    C, transliterated from the same DOS text
                                     in a separate pass, on the hardware x87.
                                     Compiled here by gcc, into the sandbox.
    All three are rebuilt and re-run on every invocation of this file.  The
    only thing read from disk that is not rebuilt is the capture set, which
    is the one thing no code in this project produced.

WHAT IS ASSUMED RATHER THAN MEASURED, stated so nobody has to guess
    plwp   - cplx_planet_viewpoint() is Wave 8.  plwp is an INPUT, recovered
             per capture by exhaustive search over all 360 values against the
             captured bytes.  "The terminator lands in the right place" would
             therefore be circular; section E instead asks whether the band's
             SHAPE (offset 35, arc 130, 179 rows) is the unique shape that
             turns the pre-terminator map into the captured bytes, over a
             100-triple search space.  That is not circular.
    secs   - the guest clock at the instant the frame fired is not recorded by
             any artefact.  Types 2, 3, 5 and 6 read it.  One integer per
             affected capture was recovered by search; this file uses that
             fitted value for all three implementations, so those four
             captures are CONSISTENT-with rather than PREDICTED-by the oracle.
             The other six types touch secs nowhere.

Usage:  python tests/test_surface.py [--quick]
        --quick skips the seventeen sabotages, which is exactly the part
        that shows the graders can fail.  It is not a pass.
"""

import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
WORK = os.path.join(REPO, "work")
HARNESS = os.path.join(REPO, "noctis-harness")
RECON = os.path.join(HERE, "gen", "recon_w7a", "out")
SAND = os.path.join(HERE, "gen", "w7a")

for p in (HERE, HARNESS):
    if p not in sys.path:
        sys.path.insert(0, p)

import linoharness as lh          # noqa: E402
import su_corpus                  # noqa: E402
import su_ledger                  # noqa: E402
import su_spec                    # noqa: E402
import sp_spec                    # noqa: E402  (Wave 6b, for the terminator)
import w5audit                    # noqa: E402

MAPB, OVLB = 64800, 32400
PB = 4                            # farmalloc's offset, BUFFERMAP section 4.1
TAILB = 752                       # 65552 - 64800
REC_SZ = MAPB + OVLB + 768 + 24   # one su_ref.exe record

# lino library set, exactly the "libraries" block of work/sumain.txt
LINO_LIBS = ("fbmem", "brtl", "mul64frag", "suseed", "surng", "subuf",
             "susm", "supaint", "supal", "sucase")
FP_LIBS = ("fpabi", "fpctl", "fpsoft", "fpx87", "fpconv")

# SUDUMP record kinds, from work/subuf.txt's "constants" block
KMAP, KOVL, KPAL, KSCAL, KLED, KTAIL, KTRL = 1, 2, 3, 4, 5, 6, 7
SUMAGIC, SUHDRU = 826622293, 16
PHASE_NAME = {0: "ENTRY", 1: "PROLOGUE", 2: "SEED", 3: "RNDPAT", 4: "CASE.ITER",
              5: "SDA", 6: "SWITCH.END", 7: "RENORM", 8: "MERGE",
              9: "TERMINATOR", 10: "POST", 11: "PALETTE", 12: "DONE"}

# The phases the two sides place at the SAME point in the source.  RENORM is
# excluded on purpose: su_spec marks it before the type-3 `rfr(2)` that picks
# lssmooth or ssmooth and the lino port marks it after, so on type 3 the two
# fast counters legitimately differ by one there.  MERGE, the very next mark,
# agrees on every case, which is what shows that difference is a label and not
# a draw.  PALETTE's map hash is excluded because the lino side does not
# recompute it after the palette (nothing in the palette touches the map).
CMP_PHASES = ("PROLOGUE", "RNDPAT", "MERGE", "TERMINATOR", "POST", "PALETTE")

# The single secs site each type reads: ((long)(k*secs) / D) % 360.
# NOCTIS-0.CPP:4890 (k=10), :4933 (k=1), :5000 (k=60), :5047 (k=60).
SECS_K = {2: 10, 3: 1, 5: 60, 6: 60}

# Types whose POST retouches do not touch the map, so the post-terminator
# buffer IS the final buffer.  2 runs extra ssmooth passes, 6 up to three, 9
# six; everything else falls straight through :5128-5146.
POST_IS_NOOP = (0, 1, 3, 4, 5, 7, 8)

# Types whose switch arm opens by writing every one of the 64,800 bytes, so
# nothing rndpat put there can survive into the final artefact.  Only type 9,
# the companion-star surface: `pclear(p_background, 0x1F)` at NOCTIS-0.CPP:5061.
PCLEAR_TYPES = (9,)

# The elapsed guest seconds recovered per secs-dependent capture, and the
# clock base.  Both are work/su-mkcorpus.py's, restated rather than imported
# because importing it would run it.  These are FITTED INPUTS, not results:
# see the header.  getsecs() is NOCTIS-0.CPP:3931-3950.
ELAPSED = {"lane_b00_t2": 22 + 3.5 / 10, "lane_b03_t3": 20 + 0.5,
           "lane_b02_t5": 10 + 54.5 / 60, "jrot_b00_t6": 9 + 1.5 / 60}


def getsecs(y, mo, d, h, mi, s):
    dfm = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    v = y - 1984
    v = v * 365 + int(v / 4)
    for m in range(1, mo):
        v += dfm[m]
    if mo > 2 and y % 4 == 0:
        v += 1
    v += d - 1
    v *= 86400
    return v + 3600 * h + 60 * mi + s


SECS_BASE = getsecs(2026, 8, 6, 12, 0, 0)


# =========================================================================
# 1.  Instrumented spec.  su_spec.py is READ, never edited: everything below
#     is a subclass.  FastTap re-hashes the RAW masked fast_random value,
#     which is the quantity work/surng.txt hashes ([SUfval], before the `%`);
#     su_spec's own Fast.h hashes the ranged result instead, so the two
#     numbers are not comparable and this one is.
# =========================================================================

class FastTap(su_spec.Fast):
    __slots__ = ("h2",)

    def __init__(self, keep=False):
        su_spec.Fast.__init__(self, keep)
        self.h2 = su_spec.FNV_OFF

    def random(self, mask):
        v = su_spec.Fast.random(self, mask)
        self.h2 = su_spec.fnv(self.h2, v)
        return v


ALOOP_N = len(su_spec.ASEQ4)       # the 4-degree ring, `for(a=0;a<2*M_PI;...)`


def _noise_step(ax, cx):
    """The self-squaring 16-bit hash sda walks: add cx, SIGNED imul, fold the
    high word back into the low, keep bits 1..5.  Same fold idiom as the galaxy
    hash at 16 bits; docs-notes/sitecount.md proved it reproducible with a
    native signed multiply plus a shift over 393,216 cases."""
    ax = (ax + cx) & 0xFFFF
    sv = ax - 0x10000 if ax & 0x8000 else ax
    p = (sv * sv) & 0xFFFFFFFF
    ax = (((p & 0xFFFF) + ((p >> 16) & 0xFFFF))) & 0xFFFF
    return ax, ax & 0x3E


class Tap(su_spec.Surface):
    """Records, at each ledger mark, what the lino port records at its own:
    the two draw counters, the two stream value-hashes and the map hash.  Also
    snapshots the map so section E can re-derive the terminator band from the
    pre-terminator bytes, and derives crater_juice's brtl budget from the LOOP
    STRUCTURE rather than echoing the observed delta.

    `lr` selects niv-lr's three departures from vanilla at the type-3 land
    noise, one at a time, as a negative control - see section D.  With lr all
    false the inherited _sda runs unmodified, which is checked, because a
    negative control that is broken in its own right detects everything.

    `stray` makes crater() store one byte past the 64,800, which is the hazard
    A5 exists for; the `*_extra_*` counts make one painter draw once more than
    the source says, which is the hazard C2 exists for.  Both default to off."""

    def __init__(self, cj_extra_brtl=0, cj_extra_fast=0, frac_extra_brtl=0,
                 cyc_extra_brtl=0, rf_extra_brtl=0, pal_extra_brtl=0,
                 lr=(0, 0, 0), stray=0):
        su_spec.Surface.__init__(self, keep_draws=True, ledger=True)
        self.F = FastTap(True)
        self.taps = {}
        self.snaps = {}
        self.cj = []
        self.lr = lr
        self.stray = stray      # bytes past the map to store one byte at
        self._x = (cj_extra_brtl, cj_extra_fast, frac_extra_brtl,
                   cyc_extra_brtl, rf_extra_brtl, pal_extra_brtl)

    def crater(self):
        su_spec.Surface.crater(self)
        if self.stray:
            self.pseg[PB + MAPB + self.stray] = 1

    # -- niv-lr's type-3 land noise, PORTPLAN's three named differences ---
    #
    #   assign    vanilla `add es:[di],bl` becomes `mov`, which also makes the
    #             following clamp unreachable
    #   bytestore vanilla clamps with `mov WORD ptr es:[di],0x3E`, zeroing the
    #             NEXT pixel too; LR stores a byte and loses that
    #   advance   vanilla advances the noise register only on the LAND branch;
    #             LR advances it on the sea branch as well
    def _sda(self):
        assign, bytestore, advance = self.lr
        if not (assign or bytestore or advance):
            return su_spec.Surface._sda(self)
        pb = self.pseg
        di, cx, ax = PB, 64000, self._seed
        gl = self.g & 0xFF
        while cx:
            if pb[di] < gl:
                pb[di] = 16
                if advance:
                    ax, _bl = _noise_step(ax, cx)
            else:
                ax, bl = _noise_step(ax, cx)
                nv = bl if assign else (pb[di] + bl) & 0xFF
                pb[di] = nv
                if nv >= 0x3E:
                    pb[di] = 0x3E
                    if not bytestore:
                        pb[(di + 1) & 0xFFFF] = 0x00
            di = (di + 1) & 0xFFFF
            cx -= 1

    def mark(self, phase):
        su_spec.Surface.mark(self, phase)
        self.taps[phase] = (self.F.n, self.B.n, self.F.h2, self.B.h,
                            su_spec.fnv_bytes(self.pseg[PB:PB + MAPB]))
        self.snaps[phase] = bytes(self.pseg[PB:PB + MAPB])

    # -- the genuinely-derived crater_juice budget -----------------------
    #
    # NOCTIS-0.CPP:4676-4696.  crater_juice draws lave and crays (2), then per
    # iteration cx, cr, cy (3), and calls crater().  crater() (:4519-4556)
    # walks ALOOP_N angles; the `crays &&` short-circuits BEFORE the draw, so
    # a zero crays costs nothing, and each angle whose random(crays) came back
    # ZERO costs one extra random(2).  Everything on the right-hand side below
    # is either a gate the OTHER stream set (r), a drawn VALUE (crays, and how
    # many ray draws were zero) or the loop's own trip count - never the
    # observed draw count.  An extra draw anywhere inside the window therefore
    # shows up; sabotage CJB in section F demonstrates exactly that.
    def crater_juice(self):
        r0, n0, l0 = self.r, self.B.n, len(self.B.log)
        su_spec.Surface.crater_juice(self)
        if self._x[0]:
            for _ in range(self._x[0]):
                self.B.random(2, 90001)
        if self._x[1]:
            for _ in range(self._x[1]):
                self.F.rfr(2, 90002)
        seg = self.B.log[l0:]
        crays = su_spec._tochar(seg[1][2] * 2)
        zeros = sum(1 for (site, _a, v) in seg if site == 4551 and v == 0)
        pred = 2 + 3 * r0 + (0 if crays == 0 else r0 * ALOOP_N + zeros)
        self.cj.append((pred, self.B.n - n0))

    def fracture(self, max_latitude):
        su_spec.Surface.fracture(self, max_latitude)
        for _ in range(self._x[2]):
            self.B.random(2, 90003)

    def atm_cyclon(self):
        su_spec.Surface.atm_cyclon(self)
        for _ in range(self._x[3]):
            self.B.random(2, 90004)

    def randoface(self, rng, upon):
        su_spec.Surface.randoface(self, rng, upon)
        for _ in range(self._x[4]):
            self.B.random(2, 90005)

    def _palette(self, logical_id, ptype, colorbase, owner, nsrgb):
        su_spec.Surface._palette(self, logical_id, ptype, colorbase, owner,
                                 nsrgb)
        for _ in range(self._x[5]):
            self.B.random(2, 90006)

    # -- the closed form, with the crater_juice term substituted ---------
    def predicted(self, ptype, colorbase):
        gates = dict(self.gates)
        if self.cj:
            gates["cj_brtl"] = sum(c[0] for c in self.cj)
        return su_ledger.predict(ptype, colorbase, gates)


def run_spec(row, **kw):
    S = Tap(**kw)
    if row["use_scaled"]:
        S._secs_scaled = row["secs_scaled"]
    out = S.run(row["id"], row["type"], row["seedval"], row["colorbase"],
                secs=row["secs"], plwp=row["plwp"], owner=row["owner"],
                nearstar_rgb=tuple(row["rgb"]))
    return S, out


# =========================================================================
# 2.  The fixture.  ONE row list, emitted in BOTH corpus formats, so a case
#     cannot exist on one side and not the other and no side can be handed a
#     different seedval from another.
# =========================================================================

def build_fixture():
    rows = []
    for r in su_corpus.capture_cases():
        tag = r["tag"]
        secs = float(SECS_BASE) + ELAPSED.get(tag, 0.0)
        k = SECS_K.get(r["type"])
        # spec and cref are HANDED (long)(k*secs) as an integer; the lino port
        # is handed the double and computes it.  So lino-vs-spec covers that
        # truncation and spec-vs-cref does not, which section C states.
        ss = su_spec.ftol32(su_spec._Fr(k) * su_spec._Fr(secs)) if k else 0
        rows.append(dict(tag=tag, kind="capture", id=r["id"], type=r["type"],
                         seedval=r["seedval"], colorbase=r["colorbase"],
                         plwp=r["plwp"], owner=r["owner"], rgb=r["rgb"],
                         secs=secs, secs_scaled=ss, use_scaled=1 if k else 0,
                         ismoon=1 if r["colorbase"] == 128 else 0,
                         manifest=r["manifest"]))
    for r in su_corpus.synth_cases():
        # secs 0.0 on all three sides: su_ref.c hardcodes k.secs = 0.0 when
        # use_scaled is 0, so this is the one value at which the C side's own
        # secs path and the other two agree without patching it.
        rows.append(dict(tag=r["tag"], kind="synthetic", id=r["id"],
                         type=r["type"], seedval=r["seedval"],
                         colorbase=r["colorbase"], plwp=r["plwp"],
                         owner=r["owner"], rgb=r["rgb"], secs=0.0,
                         secs_scaled=0, use_scaled=0,
                         ismoon=1 if r["colorbase"] == 128 else 0,
                         manifest=None))
    return rows


def write_spc(path, rows):
    with open(path, "w") as fh:
        fh.write("# id type seedval_hex64 colorbase secs_scaled use_scaled "
                 "plwp owner nr ng nb\n")
        for r in rows:
            bits = struct.unpack("<Q", struct.pack("<d", r["seedval"]))[0]
            fh.write("%d %d %016x %d %d %d %d %d %d %d %d\n" % (
                r["id"], r["type"], bits, r["colorbase"], r["secs_scaled"],
                r["use_scaled"], r["plwp"], r["owner"],
                r["rgb"][0], r["rgb"][1], r["rgb"][2]))


def write_lino_corpus(path, rows):
    """work/subuf.txt's reader: a flat stream of signed decimals, opcode 1 per
    case, opcode 0 to stop.  The two binary64 inputs arrive as their halves
    because the tokeniser knows no other lexeme."""
    with open(path, "w") as fh:
        fh.write("# built by tests/test_surface.py - do not hand-edit\n")
        for r in rows:
            slo, shi = struct.unpack("<ii", struct.pack("<d", r["seedval"]))
            clo, chi = struct.unpack("<ii", struct.pack("<d", r["secs"]))
            fh.write("1 %d %d %d %d %d %d %d %d %d %d %d %d %d 1   # %s\n" % (
                r["id"], r["type"], r["colorbase"], r["ismoon"], r["plwp"],
                r["owner"], r["rgb"][0], r["rgb"][1], r["rgb"][2],
                slo, shi, clo, chi, r["tag"]))
        fh.write("0\n")


# =========================================================================
# 3.  The lino dump reader, written from work/subuf.txt's "SUDM rec" and its
#     constants block rather than from work/su-check.py.
# =========================================================================

def read_dump(path):
    raw = open(path, "rb").read()
    u = struct.unpack("<%dI" % (len(raw) // 4), raw)
    recs, i = [], 0
    while i < len(u):
        if u[i] != SUMAGIC:
            raise SystemExit("su dump: bad magic at unit %d of %s" % (i, path))
        bc = u[i + 5]
        recs.append(dict(kind=u[i + 2], w=u[i + 3], h=u[i + 4],
                         case=u[i + 6], tag=u[i + 7],
                         body=u[i + SUHDRU:i + SUHDRU + bc]))
        i += SUHDRU + bc
    return recs


def unpack4(units, n):
    out = bytearray()
    for v in units:
        out += bytes((v & 255, (v >> 8) & 255, (v >> 16) & 255,
                      (v >> 24) & 255))
    return bytes(out[:n])


def s32(v):
    return v - 0x100000000 if v & 0x80000000 else v


def index_dump(recs, ncases):
    """{case: {"map":bytes, "ovl":bytes, "pal":bytes, "tail":bytes,
               "scal":tuple, "phases":{name: body}}}"""
    out = {}
    for ci in range(ncases):
        rs = [r for r in recs if r["case"] == ci and r["kind"] != KTRL]
        d = {"map": None, "ovl": None, "pal": None, "tail": None,
             "scal": None, "phases": {}}
        for r in rs:
            if r["kind"] == KMAP:
                d["map"] = unpack4(r["body"], MAPB)
            elif r["kind"] == KOVL:
                d["ovl"] = unpack4(r["body"], OVLB)
            elif r["kind"] == KPAL:
                d["pal"] = unpack4(r["body"], 192)
            elif r["kind"] == KTAIL:
                d["tail"] = unpack4(r["body"], TAILB)
            elif r["kind"] == KSCAL:
                d["scal"] = tuple(r["body"])
            elif r["kind"] == KLED:
                d["phases"].setdefault(
                    PHASE_NAME.get(r["body"][0], r["body"][0]), []).append(
                        r["body"])
        out[ci] = d
    return out


# =========================================================================
# 4.  The terminator band, parameterised.  NOCTIS-0.CPP:5106-5124 is
#     `add di,plwp / add di,35`, then 179 rows of 130 `shr byte ptr [di],2`
#     with a stride of 360.  Wave 6b's sp_spec.surface_band is the SAME code
#     written for the sphere renderers; this one takes the three constants as
#     arguments so section E can search for them instead of asserting them.
# =========================================================================

def band(buf, plwp, off, arc, rows):
    seg = bytearray(65536)
    seg[PB:PB + len(buf)] = buf
    di = (PB + plwp + off) & 0xFFFF
    for _ in range(rows):
        for _c in range(arc):
            seg[di] >>= 2
            di = (di + 1) & 0xFFFF
        di = (di + 360 - arc) & 0xFFFF
    return bytes(seg[PB:PB + len(buf)])


BAND_OFF, BAND_ARC, BAND_ROWS = 35, 130, 179
SWEEP_OFF = (33, 34, 35, 36, 37)
SWEEP_ARC = (128, 129, 130, 131, 132)
SWEEP_ROWS = (177, 178, 179, 180)


# =========================================================================
# 5.  Plumbing
# =========================================================================

def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def read_sources():
    """Everything this test reads but must never write.  Re-hashed at the end:
    a grader that edits its own subject is the stored-artifact defect in its
    most direct form."""
    out = {}
    for n in LINO_LIBS + ("sumain",):
        out["work/%s.txt" % n] = sha(os.path.join(WORK, n + ".txt"))
    for n in FP_LIBS:
        out["work/fp/%s.txt" % n] = sha(os.path.join(WORK, "fp", n + ".txt"))
    out["work/su-corpus.txt"] = sha(os.path.join(WORK, "su-corpus.txt"))
    for n in sorted(os.listdir(HARNESS)):
        if n.startswith("su_") and (n.endswith(".py") or n.endswith(".c")):
            out["noctis-harness/" + n] = sha(os.path.join(HARNESS, n))
    out["noctis-harness/sp_spec.py"] = sha(os.path.join(HARNESS, "sp_spec.py"))
    for n in sorted(os.listdir(RECON)):
        if n.endswith((".p_background", ".objectschart")) or n == "manifest.json":
            out["recon/" + n] = sha(os.path.join(RECON, n))
    return out


def pristine_state():
    path = os.path.join(REPO, "PRISTINE.sha256")
    ok = bad = 0
    for line in open(path, "r", encoding="utf-8-sig"):
        parts = line.split()
        if len(parts) != 3:
            continue
        want, size, rel = parts
        full = os.path.join(REPO, rel.replace("/", os.sep))
        if (os.path.exists(full) and sha(full).upper() == want.upper()
                and os.path.getsize(full) == int(size)):
            ok += 1
        else:
            bad += 1
    return ok, bad


def fresh_sandbox():
    if os.path.isdir(SAND):
        shutil.rmtree(SAND)
    os.makedirs(os.path.join(SAND, "fp"))
    for n in LINO_LIBS + ("sumain",):
        shutil.copy(os.path.join(WORK, n + ".txt"), os.path.join(SAND, n + ".txt"))
    for n in FP_LIBS:
        shutil.copy(os.path.join(WORK, "fp", n + ".txt"),
                    os.path.join(SAND, "fp", n + ".txt"))
    shutil.copy(os.path.join(HARNESS, "su_ref.c"),
                os.path.join(SAND, "su_ref.c"))


def apply_anchor(text, old, new, where):
    n = text.count(old)
    if n != 1:
        raise SystemExit("%s: anchor occurs %d times, expected 1:\n  %r"
                         % (where, n, old[:110]))
    return text.replace(old, new)


def run_lino(main_src, out_name, timeout=600):
    """Build in the sandbox and run with the poll-and-kill pattern.  A
    compiled lino programme is a subsystem-2 binary: it is never waited on and
    never launched in the foreground."""
    exe = os.path.splitext(main_src)[0] + ".exe"
    out = os.path.join(SAND, "su-out.bin")
    keep = os.path.join(SAND, out_name)
    for stale in (exe, out, keep):
        if os.path.exists(stale):
            os.remove(stale)
    rc, note = lh.build(main_src, timeout_sec=240)
    if rc != 0:
        return None, "BUILD FAILED: " + note.strip().replace("\n", " | ")
    started = time.time()
    ps = os.path.join(HERE, "w7arun.ps1")
    p = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy",
                        "Bypass", "-File", ps, "-Exe", exe, "-Out", out,
                        "-TimeoutSec", str(timeout)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    note = ((p.stdout or "") + (p.stderr or "")).strip()
    if p.returncode != 0 or not os.path.exists(out):
        return None, "RUN FAILED: " + note
    if os.path.getmtime(out) < started:
        return None, "RUN FAILED: stale output file"
    shutil.move(out, keep)
    return keep, note


def build_cref(c_src, exe_name):
    exe = os.path.join(SAND, exe_name)
    if os.path.exists(exe):
        os.remove(exe)
    p = subprocess.run(["gcc", "-O2", "-fno-fast-math", "-o", exe, c_src],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=SAND)
    if p.returncode != 0:
        return None, "gcc failed: " + (p.stdout or "") + (p.stderr or "")
    return exe, "ok"


def run_cref(exe, spc, out_name, ncases):
    out = os.path.join(SAND, out_name)
    if os.path.exists(out):
        os.remove(out)
    p = subprocess.run([exe, spc, out], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=SAND)
    if not os.path.exists(out):
        return None, "no output: " + (p.stdout or "") + (p.stderr or "")
    blob = open(out, "rb").read()
    if len(blob) != ncases * REC_SZ:
        return None, "%d bytes, expected %d" % (len(blob), ncases * REC_SZ)
    return blob, "ok"


def cref_case(blob, ci):
    o = ci * REC_SZ
    return dict(map=blob[o:o + MAPB], ovl=blob[o + MAPB:o + MAPB + OVLB],
                pal=blob[o + MAPB + OVLB:o + MAPB + OVLB + 768],
                cnt=struct.unpack_from("<6i", blob, o + MAPB + OVLB + 768))


def nd(a, b):
    if a is None or b is None:
        return -1
    return sum(1 for x, y in zip(a, b) if x != y) + abs(len(a) - len(b))


# =========================================================================
# 6.  The test
# =========================================================================

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true",
                    help="skip the seventeen sabotages - NOT a pass")
    a = ap.parse_args(argv)

    chk = lh.Check("WAVE 7a - surface(): the orbital globe texture, "
                   "byte-exact against NIV+ 2.3 and three ways internally")
    chk.note("ORACLE: ten recon-C captures out of Noctis IV+ Release 2.3's "
             "own guest RAM. NO 1996 binary exists on this machine, so no "
             "row below is 1996-anchored. niv-iv-lr is disqualified here.")

    ok, bad = pristine_state()
    chk.ok(bad == 0 and ok > 0, "G1 PRISTINE.sha256: the toolchain is untouched",
           "%d ok, %d bad" % (ok, bad))
    before = read_sources()
    chk.note("%d source/oracle files hashed; re-checked at the end" % len(before))

    # ---- rebuild every side ------------------------------------------
    fresh_sandbox()
    rows = build_fixture()
    ncases = len(rows)
    spc = os.path.join(SAND, "fix.spc")
    write_spc(spc, rows)
    write_lino_corpus(os.path.join(SAND, "su-corpus.txt"), rows)
    caps = [r for r in rows if r["kind"] == "capture"]
    chk.ok(len(caps) == 10 and ncases > len(caps),
           "R0 fixture: %d cases, %d of them capture-anchored, %d synthetic"
           % (ncases, len(caps), ncases - len(caps)),
           "types " + ",".join(str(r["type"]) for r in rows))

    cexe, note = build_cref(os.path.join(SAND, "su_ref.c"), "suref.exe")
    chk.ok(cexe is not None, "R1 cref rebuilt from noctis-harness/su_ref.c by gcc",
           note if cexe is None else os.path.basename(cexe))
    cblob = None
    if cexe:
        cblob, note = run_cref(cexe, spc, "cref.bin", ncases)
        chk.ok(cblob is not None, "R2 cref produced %d complete records" % ncases,
               note)

    lino_main = os.path.join(SAND, "sumain.txt")
    dump_path, note = run_lino(lino_main, "lino.bin")
    chk.ok(dump_path is not None,
           "R3 the lino port rebuilt from work/*.txt and run poll-and-kill", note)
    lino = None
    if dump_path:
        recs = read_dump(dump_path)
        trl = [r for r in recs if r["kind"] == KTRL]
        t = trl[-1]["body"] if trl else (0, 99, 99, 0, 0, 0)
        chk.ok(t[0] == ncases and t[1] == 0 and t[2] == 0,
               "R4 lino trailer: all %d cases ran, no bad opcode, no corpus IO "
               "error" % ncases,
               "cases=%d bad=%d corpus_io=%d" % (t[0], t[1], t[2]))
        lino = index_dump(recs, ncases)

    if cblob is None or lino is None:
        chk.ok(False, "R5 all three implementations available", "aborting")
        return chk.done()

    # ---- run the spec on every case ----------------------------------
    spec = {}
    for ci, r in enumerate(rows):
        S, out = run_spec(r)
        spec[ci] = (S, out)

    # ==================================================================
    # A.  THE ARTEFACT, against the DOS binary's own buffers
    # ==================================================================
    chk.note("--- A: the 64,800-byte artefact against recon_w7a/out ---")
    a_map = {"spec": 0, "cref": 0, "lino": 0}
    a_ovl = {"spec": 0, "cref": 0, "lino": 0}
    a_pal = {"spec": 0, "cref": 0, "lino": 0}
    worst = []
    for ci, r in enumerate(rows):
        if r["kind"] != "capture":
            continue
        S, out = spec[ci]
        C = cref_case(cblob, ci)
        L = lino[ci]
        cap = open(os.path.join(RECON, r["tag"] + ".p_background"), "rb").read()
        capo = open(os.path.join(RECON, r["tag"] + ".objectschart"), "rb").read()
        cb = r["colorbase"]
        wantpal = b"".join(bytes(t) for t in r["manifest"]["palette_192_255"])
        sides = (("spec", S.map_bytes(), S.ovl_bytes(),
                  bytes(S.tmppal)[3 * cb:3 * cb + 192]),
                 ("cref", C["map"], C["ovl"], C["pal"][3 * cb:3 * cb + 192]),
                 ("lino", L["map"], L["ovl"], L["pal"]))
        for name, m, o, p in sides:
            a_map[name] += (m == cap[:MAPB])
            a_ovl[name] += (o == capo[:OVLB])
            a_pal[name] += (p == wantpal)
            if m != cap[:MAPB]:
                worst.append("%s %s map %d bytes" % (r["tag"], name, nd(m, cap[:MAPB])))
    for name in ("spec", "cref", "lino"):
        chk.ok(a_map[name] == len(caps),
               "A1.%s p_background byte-exact on all %d captures (64,800 B "
               "each)" % (name, len(caps)),
               "%d/%d%s" % (a_map[name], len(caps),
                            "" if not worst else "  " + "; ".join(worst[:3])))
        chk.ok(a_ovl[name] == len(caps),
               "A2.%s objectschart 32,400-byte prefix byte-exact" % name,
               "%d/%d" % (a_ovl[name], len(caps)))
        chk.ok(a_pal[name] == len(caps),
               "A3.%s the 64 palette triples match the gallery BMP" % name,
               "%d/%d" % (a_pal[name], len(caps)))

    # A4: the corpus is not degenerate.  If every capture were the same body,
    # A1-A3 would be one comparison repeated ten times.
    distinct = len(set(open(os.path.join(RECON, r["tag"] + ".p_background"),
                            "rb").read()[:MAPB] for r in caps))
    chk.ok(distinct == len(caps),
           "A4 the %d captures are %d DISTINCT maps, one per planet type "
           "0..9, so A1-A3 are ten comparisons and not one" % (len(caps), distinct),
           "distinct=%d" % distinct)

    # A5: nothing escapes the 64,800 bytes.  crater()'s vptr is a 16-bit
    # quantity; a 32-bit one would splatter into the tail.
    tail_bad = sum(1 for ci, r in enumerate(rows)
                   if r["kind"] == "capture"
                   and lino[ci]["tail"] is not None and any(lino[ci]["tail"]))
    spec_tail = sum(sum(spec[ci][0].pseg[PB + MAPB:PB + MAPB + TAILB])
                    for ci, r in enumerate(rows) if r["kind"] == "capture")
    ref_tail = sum(sum(open(os.path.join(RECON, r["tag"] + ".p_background"),
                            "rb").read()[MAPB:]) for r in caps)
    chk.ok(tail_bad == 0 and spec_tail == 0 and ref_tail == 0,
           "A5 the 752 bytes past the map are zero in the capture, in the spec "
           "segment and in the lino dump",
           "lino %d captures with a nonzero tail, spec sum %d, capture sum %d"
           % (tail_bad, spec_tail, ref_tail))

    # A6: the two early returns.  Both leave the caller's buffer alone; rndpat
    # writes every one of the 64,800 bytes, so "unchanged" really does
    # distinguish returning from not returning.
    for ci, r in enumerate(rows):
        if r["type"] != 10:
            continue
        S, out = spec[ci]
        C = cref_case(cblob, ci)
        L = lino[ci]
        untouched = (S.map_bytes() == bytes(MAPB) and C["map"] == bytes(MAPB)
                     and L["map"] == bytes(MAPB))
        chk.ok(untouched,
               "A6 type 10: all three return before rndpat, so the 64,800 "
               "bytes stay as the caller left them",
               "%s: spec %d, cref %d, lino %d nonzero"
               % (r["tag"], sum(S.map_bytes()), sum(C["map"]), sum(L["map"])))

    # ==================================================================
    # B.  THREE-WAY AGREEMENT on every case, capture and synthetic alike
    # ==================================================================
    chk.note("--- B: spec == cref == lino on all %d cases ---" % ncases)
    b_sc = b_ls = b_ovl = b_pal = 0
    b_pal_n = 0
    bad_b = []
    for ci, r in enumerate(rows):
        S, out = spec[ci]
        C = cref_case(cblob, ci)
        L = lino[ci]
        sm, so = S.map_bytes(), S.ovl_bytes()
        b_sc += (sm == C["map"] and so == C["ovl"] and bytes(S.tmppal) == C["pal"])
        b_ls += (L["map"] == sm)
        b_ovl += (L["ovl"] == so)
        cb = r["colorbase"]
        if cb != 255:
            b_pal_n += 1
            b_pal += (L["pal"] == bytes(S.tmppal)[3 * cb:3 * cb + 192])
        if L["map"] != sm:
            bad_b.append("%s %d bytes" % (r["tag"], nd(L["map"], sm)))
    chk.ok(b_sc == ncases,
           "B1 spec == cref on map, overlay and the whole 768-byte palette",
           "%d/%d" % (b_sc, ncases))
    chk.ok(b_ls == ncases,
           "B2 lino == spec on the 64,800-byte map, including the 14 "
           "synthetic cases no capture covers (moons, colorbase 255, type 10, "
           "case 4's r>20 branch, knot1==1, the seed flip)",
           "%d/%d%s" % (b_ls, ncases, "  " + "; ".join(bad_b[:3]) if bad_b else ""))
    chk.ok(b_ovl == ncases, "B3 lino == spec on the 32,400-byte overlay",
           "%d/%d" % (b_ovl, ncases))
    chk.ok(b_pal == b_pal_n,
           "B4 lino == spec on the 64 palette triples", "%d/%d" % (b_pal, b_pal_n))

    # ==================================================================
    # C.  DRAW ACCOUNTING - the two interleaved streams
    # ==================================================================
    chk.note("--- C: per-stream draw accounting ---")
    c_tot = c_pred = c_phase = c_rt = 0
    c_n = c_phase_n = 0
    tot_fast = tot_brtl = 0
    bad_c = []
    for ci, r in enumerate(rows):
        S, out = spec[ci]
        C = cref_case(cblob, ci)
        L = lino[ci]
        if r["type"] == 10:
            continue        # UNGRADED: see the NOT GRADED list at the end
        c_n += 1
        sf, sb = out.get("fast_n", 0), out.get("brtl_n", 0)
        tot_fast += sf
        tot_brtl += sb
        agree = (L["scal"][9] == sf == C["cnt"][0]
                 and L["scal"][10] == sb == C["cnt"][1])
        c_tot += agree
        if not agree:
            bad_c.append("%s lino=(%d,%d) spec=(%d,%d) cref=(%d,%d)"
                         % (r["tag"], L["scal"][9], L["scal"][10], sf, sb,
                            C["cnt"][0], C["cnt"][1]))
        c_pred += (S.predicted(r["type"], r["colorbase"]) == (sf, sb))
        c_rt += (L["scal"][3] == out.get("rtperiod")
                 and s32(L["scal"][4]) == out.get("rotation")
                 and C["cnt"][2] == out.get("rtperiod"))
        for ph in CMP_PHASES:
            if ph not in S.taps and ph not in L["phases"]:
                continue
            c_phase_n += 1
            if ph not in S.taps or ph not in L["phases"]:
                continue
            st, lt = S.taps[ph], L["phases"][ph][-1]
            same = (st[0], st[1], st[2], st[3]) == (lt[2], lt[3], lt[4], lt[5])
            if ph != "PALETTE":
                same = same and st[4] == lt[6]
            c_phase += same
    chk.ok(c_tot == c_n,
           "C1 per-stream draw totals agree lino == spec == cref on every case",
           "%d/%d%s" % (c_tot, c_n, "  " + "; ".join(bad_c[:3]) if bad_c else ""))
    chk.ok(tot_fast > 0 and tot_brtl > 0 and tot_fast != tot_brtl,
           "C1b both streams really run: %d ranged_fast_random draws and %d "
           "Borland random() draws over the corpus" % (tot_fast, tot_brtl),
           "fast=%d brtl=%d" % (tot_fast, tot_brtl))
    chk.ok(c_pred == c_n,
           "C2 the closed form from su_ledger.py predicts both counters, with "
           "crater_juice's brtl term derived from (r, crays, ray-zeros, %d "
           "angles) instead of echoed from the observation" % ALOOP_N,
           "%d/%d" % (c_pred, c_n))
    chk.ok(c_phase == c_phase_n,
           "C3 per-phase, per-stream: draw counters, the two stream VALUE "
           "hashes and the map hash all agree lino == spec at %s"
           % "/".join(CMP_PHASES),
           "%d/%d phase records" % (c_phase, c_phase_n))
    chk.ok(c_rt == c_n,
           "C4 nearstar_p_rtperiod agrees three ways and nearstar_p_rotation "
           "agrees lino == spec (cref is handed secs=0 and is not asked)",
           "%d/%d" % (c_rt, c_n))

    # C5: rotation is a truncating C `%`, not Python's flooring one.  Five of
    # the ten captures land on a negative dividend, where the two differ.
    trunc_only = 0
    for ci, r in enumerate(rows):
        S, out = spec[ci]
        if r["type"] == 10 or not out.get("rtperiod"):
            continue
        raw = su_spec.ftol32(su_spec._Fr(r["secs"]) / out["rtperiod"])
        flooring = su_spec.i16(su_spec.i16(raw) % 360)
        if flooring != s32(lino[ci]["scal"][4]):
            trunc_only += 1
    chk.ok(trunc_only >= 5,
           "C5 rotation: on %d cases a flooring `%%` would give a different "
           "answer from the truncating one, and the lino port gives the "
           "truncating one" % trunc_only,
           "cases where the two models disagree: %d" % trunc_only)

    # C6: the two independent seedval derivations.  su_seed.py builds the
    # product on the x87 stack with one rounding (Wave 3); work/su-mkcorpus.py
    # builds it in plain binary64, spilling at every step.  Only two numbers
    # derived from it can reach the map - the two __ftol truncations - so
    # those, not the doubles, are what must agree.
    other = {}
    for line in open(os.path.join(WORK, "su-corpus.txt")):
        head, _, cm = line.partition("#")
        if not head.strip() or not cm.strip():
            continue
        v = head.split()
        if len(v) >= 15:
            other[cm.strip()] = struct.unpack(
                "<d", struct.pack("<ii", int(v[10]), int(v[11])))[0]
    seed_ok = seed_n = dbl_diff = 0
    for r in caps:
        if r["tag"] not in other:
            continue
        seed_n += 1
        mine, theirs = r["seedval"], other[r["tag"]]
        dbl_diff += (mine != theirs)
        a1 = (su_spec.ftol32(su_spec._Fr(mine) + 4112),
              su_spec.ftol32(su_spec._Fr(mine) * 10))
        a2 = (su_spec.ftol32(su_spec._Fr(theirs) + 4112),
              su_spec.ftol32(su_spec._Fr(theirs) * 10))
        seed_ok += (a1 == a2)
    chk.ok(seed_n > 0 and seed_ok == seed_n,
           "C6 the two independent seedval derivations agree on BOTH __ftol "
           "truncations - the only two numbers surface() can see",
           "%d/%d agree; the raw doubles differ on %d of %d"
           % (seed_ok, seed_n, dbl_diff, seed_n))

    # ==================================================================
    # D.  TYPE 3: vanilla ADDS the land noise, niv-lr ASSIGNS it
    # ==================================================================
    chk.note("--- D: the type-3 divergence that disqualified niv-lr ---")
    t3 = [ci for ci, r in enumerate(rows)
          if r["kind"] == "capture" and r["type"] == 3]
    chk.ok(len(t3) > 0,
           "D0 the corpus contains a type-3 capture, so section D is reachable",
           "%d of %d captures" % (len(t3), len(caps)))
    # D1 first: the control with every LR flag off must reproduce the
    # inherited _sda exactly.  A negative control that is itself broken
    # "detects" everything and proves nothing.
    ctrl_ok = 0
    for ci in t3:
        S, _o = run_spec(rows[ci], lr=(0, 0, 0))
        ctrl_ok += (S.map_bytes() == spec[ci][0].map_bytes())
    chk.ok(ctrl_ok == len(t3),
           "D1 the LR control harness with all three flags OFF reproduces the "
           "unmodified spec, so a difference below is the flag and not the "
           "harness", "%d/%d" % (ctrl_ok, len(t3)))
    LRFLAGS = [((1, 0, 0), "ASSIGN the land noise instead of ADDing it"),
               ((0, 1, 0), "clamp with a BYTE store, losing the word store's "
                           "zeroing of the neighbouring pixel"),
               ((0, 0, 1), "advance the noise register on the SEA branch too")]
    for k, (flags, why) in enumerate(LRFLAGS):
        seen = []
        for ci in t3:
            S, _o = run_spec(rows[ci], lr=flags)
            cap = open(os.path.join(RECON, rows[ci]["tag"] + ".p_background"),
                       "rb").read()[:MAPB]
            seen.append(nd(S.map_bytes(), cap))
        chk.ok(all(d > 0 for d in seen),
               "D2%d the capture DISTINGUISHES vanilla from niv-lr's choice to "
               "%s" % (k + 1, why),
               "byte-diff against the capture per type-3 capture: %s of %d"
               % (seen, MAPB))

    # ==================================================================
    # E.  THE TERMINATOR - shape, not position
    # ==================================================================
    chk.note("--- E: the day/night band, and Wave 6b's copy of its constants ---")
    e_const = e_band = e_lino = 0
    e_const_n = e_band_n = e_lino_n = 0
    for ci, r in enumerate(rows):
        S, out = spec[ci]
        if out.get("term_start") is None:
            continue
        tc = sp_spec.terminator_constants(r["plwp"], 0)
        e_const_n += 1
        e_const += (tc["term_start"] == out["term_start"]
                    and tc["term_end"] == out["term_end"]
                    and tc["glow_arc"] == BAND_ARC)
        e_lino_n += 1
        e_lino += (lino[ci]["scal"][6] == out["term_start"]
                   and lino[ci]["scal"][7] == out["term_end"])
        # Wave 6b's own surface_band, over the spec's pre-terminator bytes.
        # Skipped on type 2 when psmooth_grays ran between the two marks.
        if "MERGE" in S.snaps and "TERMINATOR" in S.snaps and not out.get("knot1"):
            e_band_n += 1
            e_band += (sp_spec.surface_band(S.snaps["MERGE"], r["plwp"])["out"]
                       == S.snaps["TERMINATOR"])
    chk.ok(e_const == e_const_n,
           "E1 sp_spec.terminator_constants (Wave 6b, glowinglobe's crescent) "
           "gives the same term_start/term_end as surface(), and the same "
           "arc of %d" % BAND_ARC, "%d/%d" % (e_const, e_const_n))
    chk.ok(e_lino == e_lino_n,
           "E2 the lino port's own term_start/term_end agree with the spec's",
           "%d/%d" % (e_lino, e_lino_n))
    chk.ok(e_band == e_band_n and e_band_n > 0,
           "E3 Wave 6b's surface_band() reproduces the spec's post-terminator "
           "map byte for byte from its pre-terminator map",
           "%d/%d" % (e_band, e_band_n))

    # E4: the sharp one.  plwp was recovered from the capture, so "the band is
    # in the right place" is circular; its SHAPE is not.  Search 5 x 5 x 4 =
    # 100 (offset, arc, rows) triples against the CAPTURED bytes on the seven
    # capture types whose POST does nothing, and intersect.
    inter = None
    per_case = []
    for ci, r in enumerate(rows):
        if r["kind"] != "capture" or r["type"] not in POST_IS_NOOP:
            continue
        S, _out = spec[ci]
        cap = open(os.path.join(RECON, r["tag"] + ".p_background"), "rb").read()
        hits = set()
        for off in SWEEP_OFF:
            for arc in SWEEP_ARC:
                for nr in SWEEP_ROWS:
                    if band(S.snaps["MERGE"], r["plwp"], off, arc, nr) == cap[:MAPB]:
                        hits.add((off, arc, nr))
        per_case.append((r["tag"], len(hits)))
        inter = hits if inter is None else (inter & hits)
    chk.ok(inter == {(BAND_OFF, BAND_ARC, BAND_ROWS)},
           "E4 over %d (offset, arc, rows) triples on %d captures, exactly ONE "
           "shape turns the pre-terminator map into the captured bytes on all "
           "of them, and it is (%d, %d, %d)"
           % (len(SWEEP_OFF) * len(SWEEP_ARC) * len(SWEEP_ROWS), len(per_case),
              BAND_OFF, BAND_ARC, BAND_ROWS),
           "intersection %s; per-case hit counts %s"
           % (sorted(inter or []), per_case))

    # ==================================================================
    # F.  BREAK EVERY CHECK BY BREAKING THE CODE
    # ==================================================================
    if a.quick:
        chk.note("--- F: SKIPPED (--quick). This is not a pass. ---")
    else:
        chk.note("--- F: sabotages. A check nobody has broken is untested. ---")
        run_sabotages(chk, rows, spec, cblob, lino, spc, ncases, caps, t3)

    # ==================================================================
    # G.  HYGIENE
    # ==================================================================
    after = read_sources()
    moved = sorted(k for k in before if before[k] != after.get(k))
    chk.ok(not moved,
           "G2 this test wrote to none of the %d source or oracle files it "
           "read" % len(before), ", ".join(moved) if moved else "all unchanged")

    findings = w5audit.analyze_file(os.path.abspath(__file__), samples=300)
    chk.ok(not findings,
           "G3 tests/w5audit.py finds no unfalsifiable check in this file",
           "; ".join("%s:%s %s" % (f.line, f.rule, f.key) for f in findings)
           if findings else "0 findings over 300 random assignments")

    # w5audit's scope does not include noctis-harness/su_*.py.  Measured, not
    # claimed: run it over them here and REPORT, without failing this suite on
    # another wave's file.
    ext = []
    for n in sorted(os.listdir(HARNESS)):
        if n.startswith("su_") and n.endswith(".py"):
            try:
                ext.extend(w5audit.analyze_file(os.path.join(HARNESS, n),
                                                samples=300))
            except SyntaxError:
                pass
    chk.note("w5audit over the %d Wave 7a python files in noctis-harness "
             "(NOT in its scope_files(), NOT graded here): %d finding(s)%s"
             % (len([n for n in os.listdir(HARNESS)
                     if n.startswith("su_") and n.endswith(".py")]),
                len(ext),
                "" if not ext else " - " + "; ".join(
                    "%s:%s" % (os.path.basename(f.path), f.line) for f in ext)))

    print("""
NOT GRADED, item by item, rather than dropped
  N1  cplx_planet_viewpoint / plwp.  Wave 8.  plwp is an INPUT here, recovered
      per capture by exhaustive search against the captured bytes.  E4 grades
      the band's SHAPE, which that search does not determine.
  N2  the elapsed guest seconds for types 2/3/5/6.  A declared unknown, fitted
      per capture against the artefact.  Those four captures are therefore
      CONSISTENT-with, not PREDICTED-by, the oracle.  The other six are
      unconditional.  Both implementers fitted this independently and landed
      on different integers inside the same invariance plateau, which is why
      one value is used here for all three sides rather than two being
      compared.
  N3  the second srand(seed) at :4844.  Nothing between the two calls draws
      and Borland's srand is idempotent, so NO check can distinguish them.
      Both are executed because the source executes both.
  N4  type 10's scalars.  In DOS the early return leaves the nearstar_p_*
      globals at their previous values; spec and cref reset per-case counters
      and the lino port does not.  That is a harness lifetime difference, not
      a game one, and no row claims to grade it.  A6 grades the buffer, which
      IS comparable.
  N5  fast_srand(seedval + 4112).  Reseeded before anything touches the map,
      so its ONLY observable is rtperiod, and rtperiod is compared spec-to-
      cref-to-lino and never to the binary.  No artefact in this wave anchors
      that bridge to the DOS binary.
  N6  a moon's last 41 lssmooth bytes.  On a moon s_background's block is
      64,800 bytes exactly and lssmooth reads 41 past it, into DOS heap slack
      this port zeroes.  No capture in the set is a moon, so the two synthetic
      moons are three-way agreement only.
  N7  BrtlToInt16 narrowing at work/surng.txt's call site.  The largest brtl
      argument in this corpus is 380, far below where a 16-bit narrowing could
      bite.  Latent, not exercised.
  N8  build_surface(), the ground terrain, sky and SURFACE.BIN.  Wave 7b.

DEFECTIVE HARNESS PATTERNS THIS FILE DOES NOT REPRODUCE
  No row here passes on a nonzero tally; no row compares an artefact to
  itself; there is no `inrow`-style per-type exemption, so a type-3 capture
  cannot be excused the way work/su-check.py's SECS_TYPES excuses it; and the
  crater_juice draw budget in C2 is derived from the loop structure rather
  than read back out of the observation, which is the shape su_ledger.py's
  own docstring promises and its predict_switch() does not deliver.""")

    return chk.done()


# =========================================================================
# 7.  The sabotages
# =========================================================================

C_MUTANTS = [
    ("CT3ASSIGN", "nv = (unsigned char)(pseg[di] + bl);",
     "nv = (unsigned char)(bl);",
     "niv-lr's type-3 defect: ASSIGN the land noise instead of ADDing it"),
    ("CFRACDRAW", "g_a = (float)((ld)brandom(360) * (ld)DEGD);",
     "(void)brandom(2); g_a = (float)((ld)brandom(360) * (ld)DEGD);",
     "one extra brtl draw per fracture() - a pure draw-count defect"),
    ("CTERM36", "{ u16 di = (u16)(PB + plwp + 35);",
     "{ u16 di = (u16)(PB + plwp + 36);",
     "the terminator band shifted one column east"),
    ("CSEEDTRUNC", "fast_srand(ftol32((ld)k->seedval + 4112));",
     "fast_srand((i32)(ftol32((ld)k->seedval) + 4112));",
     "niv-lr's order at the first bridge: truncate seedval BEFORE adding "
     "4112, which is invisible unless the sign flips across the addition"),
]

LINO_MUTANTS = [
    ("LT3ASSIGN", "susm",
     "\tD + A; D & 0FFh;\t\t( add es:[di], bl - a BYTE add )",
     "\tD = A; D & 0FFh;\t\t( SABOTAGE: assign, niv-lr's bug )",
     "the same type-3 defect, in the deliverable"),
    ("LSUBORDER", "supal",
     "\tC = [SUc]; => SU rnd;\n\tA = [SPt2]; A + C; [SPt2] = A;\n"
     "\tC = [SUc]; => SU rnd;\n\tA = [SPt2]; A - C; [SUti] = A;",
     "\tC = [SUc]; => SU rnd;\n\tA = [SPt2]; A - C; [SPt2] = A;\n"
     "\tC = [SUc]; => SU rnd;\n\tA = [SPt2]; A + C; [SUti] = A;",
     "`x + random(c) - random(c)` evaluated right to left: the same draws, in "
     "the same order, combined the other way round"),
    ("LRNDPATUNS", "surng",
     "\tD = A; D & 8000h;\n\t? D = 0 -> SU ns pos;\n\tA - 65536;\n"
     "    \"SU ns pos\"",
     "    \"SU ns pos\"",
     "the surface noise folded with an UNSIGNED multiply instead of a SIGNED "
     "one - the one-character difference between this hash and the galaxy "
     "hash's - which moves the map while consuming NO draw at all"),
    # lib None: the edit goes in the DRIVER, because the hazard A5 exists for
    # is "some painter stored past the 64,800 bytes" and it does not matter
    # which one.  One byte at region index 64,800 is exactly that.
    ("LSTRAY", None,
     "\t[SDcase] = [MNcases];\n\t=> SU surface;\n",
     "\t[SDcase] = [MNcases];\n\t=> SU surface;\n"
     "\tA = nw; A + [SUpbase]; A + 64800; C = 1; [A] = C;"
     "\t( SABOTAGE: one store past the map )\n",
     "one byte written past the end of the 64,800, the way a 32-bit vptr in "
     "crater() would"),
]


def run_sabotages(chk, rows, spec, cblob, lino, spc, ncases, caps, t3):
    capidx = [ci for ci, r in enumerate(rows) if r["kind"] == "capture"]

    # ---- C-side --------------------------------------------------------
    src0 = open(os.path.join(SAND, "su_ref.c"), encoding="latin-1").read()
    for name, old, new, why in C_MUTANTS:
        path = os.path.join(SAND, "suref" + name.lower() + ".c")
        open(path, "w", encoding="latin-1").write(
            apply_anchor(src0, old, new, "su_ref.c/" + name))
        exe, note = build_cref(path, "suref" + name.lower() + ".exe")
        if exe is None:
            chk.ok(False, "F.%s built" % name, note)
            continue
        blob, note = run_cref(exe, spc, "cref" + name.lower() + ".bin", ncases)
        if blob is None:
            chk.ok(False, "F.%s ran" % name, note)
            continue
        moved = drawn = 0
        for ci in capidx:
            r = rows[ci]
            cap = open(os.path.join(RECON, r["tag"] + ".p_background"),
                       "rb").read()[:MAPB]
            M = cref_case(blob, ci)
            moved += (M["map"] != cap)
            drawn += (M["cnt"][:2] != cref_case(cblob, ci)["cnt"][:2])
        t3moved = sum(1 for ci in t3
                      if cref_case(blob, ci)["map"]
                      != open(os.path.join(RECON, rows[ci]["tag"]
                                           + ".p_background"), "rb").read()[:MAPB])
        if name == "CT3ASSIGN":
            d = nd(cref_case(blob, t3[0])["map"],
                   open(os.path.join(RECON, rows[t3[0]]["tag"]
                                     + ".p_background"), "rb").read()[:MAPB])
            chk.ok(t3moved == len(t3) and moved == t3moved,
                   "F.%s caught: %s - and ONLY the type-3 captures move, "
                   "which is what makes it that defect and not noise" % (name, why),
                   "type-3 captures wrong %d/%d, all captures wrong %d/%d, "
                   "lane_b03_t3 differs by %d of %d bytes"
                   % (t3moved, len(t3), moved, len(capidx), d, MAPB))
        elif name == "CFRACDRAW":
            chk.ok(drawn > 0 and moved > 0,
                   "F.%s caught: %s" % (name, why),
                   "draw totals moved on %d captures, maps on %d"
                   % (drawn, moved))
        elif name == "CSEEDTRUNC":
            # The truncation only commutes with the +4112 when the sign does
            # not flip across it, which needs |seedval| < 4112 and a fraction.
            # Every capture has |seedval| >> 4112, so this defect is invisible
            # on the captures and is caught ONLY by the synthetic seed-flip
            # case, through rtperiod.  That is the C4 row, and it is why the
            # synthetic corpus exists.
            rt = sum(1 for ci in range(ncases)
                     if cref_case(blob, ci)["cnt"][2]
                     != cref_case(cblob, ci)["cnt"][2])
            chk.ok(rt > 0 and moved == 0,
                   "F.%s caught: %s" % (name, why),
                   "rtperiod moved on %d of %d cases and on NO capture map "
                   "(%d) - only the synthetic corpus can see it"
                   % (rt, ncases, moved))
        else:
            chk.ok(moved == len(capidx) and drawn == 0,
                   "F.%s caught: %s - every capture moves and NO draw count "
                   "does, so C1 alone would have missed it" % (name, why),
                   "maps wrong %d/%d, draw totals wrong %d"
                   % (moved, len(capidx), drawn))

    # ---- lino side -----------------------------------------------------
    drv0 = open(os.path.join(SAND, "sumain.txt"), encoding="latin-1").read()
    for name, lib, old, new, why in LINO_MUTANTS:
        tag = "subrk" + name.lower()
        if lib is None:
            drv = apply_anchor(drv0, old, new, "sumain/" + name)
        else:
            libsrc = open(os.path.join(SAND, lib + ".txt"),
                          encoding="latin-1").read()
            open(os.path.join(SAND, tag + "lib.txt"), "w",
                 encoding="latin-1").write(
                     apply_anchor(libsrc, old, new, lib + "/" + name))
            drv = apply_anchor(drv0, "\n\t%s;\n" % lib, "\n\t%slib;\n" % tag,
                               "sumain/" + name)
        drv = apply_anchor(drv, "program name = { sumain };",
                           "program name = { %s };" % (tag + "main"),
                           "sumain/" + name)
        mpath = os.path.join(SAND, tag + "main.txt")
        open(mpath, "w", encoding="latin-1").write(drv)
        dump, note = run_lino(mpath, tag + ".bin")
        if dump is None:
            chk.ok(False, "F.%s built and ran" % name, note)
            continue
        L = index_dump(read_dump(dump), ncases)
        moved = palmoved = drawn = phmoved = 0
        for ci in capidx:
            r = rows[ci]
            cap = open(os.path.join(RECON, r["tag"] + ".p_background"),
                       "rb").read()[:MAPB]
            wantpal = b"".join(bytes(t) for t in r["manifest"]["palette_192_255"])
            moved += (L[ci]["map"] != cap)
            palmoved += (L[ci]["pal"] != wantpal)
            drawn += (L[ci]["scal"][9:11] != lino[ci]["scal"][9:11])
            for ph in CMP_PHASES:
                if ph in L[ci]["phases"] and ph in lino[ci]["phases"]:
                    # (fast_n, brtl_n, fast value hash, brtl value hash, map
                    # hash) - exactly the tuple C3 compares across the two
                    # implementations, compared here across two builds.
                    phmoved += (L[ci]["phases"][ph][-1][2:7]
                                != lino[ci]["phases"][ph][-1][2:7])
        tailmoved = sum(1 for ci in range(ncases)
                        if L[ci]["tail"] is not None and any(L[ci]["tail"]))
        if name == "LSTRAY":
            chk.ok(tailmoved > 0 and moved == 0 and drawn == 0,
                   "F.%s caught by A5's tail arm alone: %s" % (name, why),
                   "nonzero tails %d of %d planet cases, maps wrong %d, draw "
                   "totals wrong %d - only the tail sees it"
                   % (tailmoved, sum(1 for ci in range(ncases)
                                     if L[ci]["tail"] is not None),
                      moved, drawn))
        elif name == "LT3ASSIGN":
            d = nd(L[t3[0]]["map"],
                   open(os.path.join(RECON, rows[t3[0]]["tag"]
                                     + ".p_background"), "rb").read()[:MAPB])
            chk.ok(moved == len(t3) and moved > 0,
                   "F.%s caught: %s" % (name, why),
                   "maps wrong %d/%d (the %d type-3 captures), "
                   "lane_b03_t3 differs by %d of %d bytes"
                   % (moved, len(capidx), len(t3), d, MAPB))
        elif name == "LRNDPATUNS":
            # rndpat consumes NO draw, so at the RNDPAT mark the two builds
            # must differ in the MAP hash and in nothing else.  Further down
            # the damage propagates INTO the brtl stream on the types whose
            # consumption is data-dependent (randoface draws twice per pixel
            # that passes its gate); that is the interleaving hazard this wave
            # exists for, so it is reported, not asserted away.
            rp = rponly = 0
            for ci in range(ncases):
                x = L[ci]["phases"].get("RNDPAT")
                y = lino[ci]["phases"].get("RNDPAT")
                if not x or not y:
                    continue
                rp += 1
                rponly += (x[-1][2:6] == y[-1][2:6] and x[-1][6] != y[-1][6])
            # Type 9's switch arm opens with pclear(0x1F), which writes all
            # 64,800 bytes, so rndpat's noise cannot survive into ITS final
            # artefact - and the per-phase record catches there what the
            # artefact alone cannot.  That is the whole argument for C3.
            exempt = [ci for ci in capidx if rows[ci]["type"] in PCLEAR_TYPES]
            chk.ok(rp > 0 and rponly == rp
                   and moved == len(capidx) - len(exempt),
                   "F.%s caught by C3's per-phase MAP hash on EVERY case - at "
                   "RNDPAT the sabotaged build differs in the map hash and in "
                   "nothing else, no draw having happened yet - and by A1 on "
                   "every capture except the one type-9, whose pclear(0x1F) "
                   "overwrites all 64,800 bytes: %s" % (name, why),
                   "RNDPAT map-hash-only on %d of %d cases; maps wrong %d, "
                   "expected %d (%d exempt); draw totals move downstream on "
                   "%d captures - the data-dependent types"
                   % (rponly, rp, moved, len(capidx) - len(exempt),
                      len(exempt), drawn))
        else:
            chk.ok(palmoved == len(capidx) and moved == 0 and drawn == 0
                   and phmoved == 0,
                   "F.%s caught by the palette bytes ALONE - not by any draw "
                   "count and not by either stream's value hash, because the "
                   "draws themselves are unchanged: %s" % (name, why),
                   "palettes wrong %d/%d, maps wrong %d, draw totals wrong "
                   "%d, phase records wrong %d"
                   % (palmoved, len(capidx), moved, drawn, phmoved))

    # ---- the spec-side predictor.  These do not need a build: the painter
    # ---- is subclassed and made to draw once more than the source says.
    # The type set beside each is the set of planet types whose switch arm
    # calls that painter, read off NOCTIS-0.CPP's switch and not off any run;
    # one case per type is exercised, and a type that does not actually reach
    # the painter is reported as not reached rather than silently skipped.
    inject = [("cj_extra_brtl", (1, 4), "crater_juice draws one extra random(2)"),
              ("cj_extra_fast", (1, 4), "crater_juice draws one extra rfr(2)"),
              ("frac_extra_brtl", (0, 4, 7), "fracture draws one extra random(2)"),
              ("cyc_extra_brtl", (3,), "atm_cyclon draws one extra random(2)"),
              ("rf_extra_brtl", (5, 7), "randoface draws one extra random(2)"),
              ("pal_extra_brtl", tuple(range(10)),
               "the palette draws a nineteenth random()")]
    for kw, types, why in inject:
        caught = reached = 0
        picked = []
        for ty in types:
            hit = [ci for ci, r in enumerate(rows) if r["type"] == ty
                   and r["colorbase"] != 255]
            if hit:
                picked.append(hit[0])
        for ci in picked:
            r = rows[ci]
            base = spec[ci][0]
            S, out = run_spec(r, **{kw: 1})
            obs = (out.get("fast_n", 0), out.get("brtl_n", 0))
            if obs == (base.F.n, base.B.n):
                continue                # this painter never ran on this case
            reached += 1
            caught += (S.predicted(r["type"], r["colorbase"]) != obs)
        chk.ok(reached == len(picked) and caught == reached,
               "F.PRED[%s] caught on every type that reaches it: %s" % (kw, why),
               "types %s, reached %d of %d, predictor disagreed on %d"
               % (list(types), reached, len(picked), caught))

    # ---- the terminator sweep's own falsifier -------------------------
    ci = capidx[0]
    r = rows[ci]
    S = spec[ci][0]
    cap = open(os.path.join(RECON, r["tag"] + ".p_background"), "rb").read()[:MAPB]
    off_by_one = sum(1 for d in (-1, 1)
                     if band(S.snaps["MERGE"], (r["plwp"] + d) % 360,
                             BAND_OFF, BAND_ARC, BAND_ROWS) != cap)
    chk.ok(off_by_one == 2,
           "F.BAND caught: a band placed one column either side of plwp does "
           "not reproduce the captured bytes, so E3/E4 are not satisfied by "
           "any band at all", "%d of 2 neighbours rejected" % off_by_one)

    # ---- A5's spec arm, and A6, both build-free ------------------------
    # crater() is the painter whose vptr A5's comment names, and it runs on
    # types 1 and 4 only, so the stray store is modelled where it belongs.
    ccap = [ci for ci in capidx if rows[ci]["type"] in (1, 4)][0]
    S, _o = run_spec(rows[ccap], stray=100)
    chk.ok(sum(S.pseg[PB + MAPB:PB + MAPB + TAILB]) > 0,
           "F.SSTRAY caught by A5's spec arm: one byte stored 100 past the map "
           "makes the 752-byte tail nonzero",
           "tail sum %d" % sum(S.pseg[PB + MAPB:PB + MAPB + TAILB]))

    t10 = [ci for ci, r in enumerate(rows) if r["type"] == 10]
    forced = dict(rows[t10[0]])
    forced["type"] = 3          # the same inputs, without the early return
    S, _o = run_spec(forced)
    chk.ok(sum(S.map_bytes()) > 0,
           "F.NOEARLY caught: with the type-10 early return not taken, rndpat "
           "fills all 64,800 bytes - so A6's `unchanged` really does separate "
           "returning from not returning",
           "map sum with type forced to 3: %d" % sum(S.map_bytes()))


if __name__ == "__main__":
    lh.main_guard(main)
