"""Wave 6a: projection, poly3d and polymap, graded against a C-from-assembly
oracle.

    python tests/test_raster.py             everything (about 35 seconds)
    python tests/test_raster.py --quick     skip the four lino sabotages -
                                            NOT A PASS, see below

WHAT THIS FILE CLAIMS, AND AT WHAT STRENGTH
===========================================
Read this list before reading a PASS.  Three strengths are used and they are
not interchangeable.

EXACT - byte or integer equality, zero tolerance, cross-owner
  R1  the rasteriser page.  Every case that both sides draw is compared byte
      for byte over all 64,000 visible pixels.  No tolerance, no hash of a
      hash, and the range compared INCLUDES the two scratch pixels at 0xFA00
      and 0xFA01, so a polymap that never ran cannot pass.
      Colour 255 is the polygon-edge sentinel: Segmento stores 255 and
      nothing else, and drawb's row loop scans for 255 with repne/repe scasb
      and fills between the runs.  A 255 that was on the page BEFORE the
      polygon is therefore indistinguishable from an edge, and R1e requires
      the five frozen cases built around that to be in the compared set.
  R2  the bounding-box gate: min_x, max_x, min_y, max_y and the count of
      gates that fired.
  R3  the span limit tables ipart[]/fpart[] over the graded interval, as
      integers.
  P1  projection topology on the joinable subset: the return gate, the
      near-plane flag word, the per-vertex near flags, the vertex count at
      every clip stage actually reached, and the screen bounding box.
  P2  the projected vertex table mp[], as integers.  See BOUNDED.
  P3  getcoords: the returned char, and the coordinates when the char says
      they are defined.

BOUNDED - a numeric envelope with the bound stated here
  P2 is DECLARED bounded at max|delta| <= 1 px, because the projection is
  floating point and FLOATPOLICY grades it inside a +-1 pixel envelope.  It
  is CHECKED at max|delta| == 0, because 0 is what this corpus measures over
  222 mp[] components and a check must be as tight as the evidence allows.
  The reason the difference matters is measured, not argued: the oracle run
  with --round=chop moves 18 of 30 cases by exactly 1, so a +-1 envelope
  would pass a systematically wrong rounding mode and an exact check does
  not.  If a future corpus genuinely produces a 1-px spread, this check must
  be relaxed to the declared bound and the relaxation recorded - not before.

NOT GRADED - stated so nobody reads coverage into a PASS
  * 20 of the 51 frozen PROJ cases.  The port hard-codes the camera
    (alfa=beta=gamma=0, cam=(0,0,0), dpp=210.0f, uneg=100.0f) and has no
    setter, so any case with a different camera has no lino counterpart.
    Section 6 counts them and names the reason for each.
  * 10 of the 14 frozen GETC cases, for the same reason (dpp=128.0f).
  * The polymap texture-gradient basis (oracle K29) and the derived row u/v
    (K2A).  The lino emits no counterpart record at all.
  * The 16-bit address truncation.  Nothing on either side exercises it -
    measured, not assumed: removing all three masks from pg_ref.c moves 0
    records, and a lino build with `MEM seg addr` bypassed is bit-identical.
    docs-notes/WAVE6A_RASTER.md section 5 item 3.
  * gamma != 0.  pgfp.txt:294 says "the port asserts gamma == 0 ... set it
    non-zero and the flag fires".  There is no such assertion: FSGAM is
    declared once, initialised to zero once, and never read.  Section 6 pins
    that absence, so the day somebody implements it this file fails and the
    claim gets re-checked instead of quietly staying wrong.
  * Anything needing the 1996 binary.  noctis-harness/pg_bin.py grades the
    clip immediates, the farmalloc offset and the instruction censuses
    against NOCTIS.EXE; that is a different owner pair and a different file.

HOW A CHECK EARNS ITS PLACE
===========================
Both sides are recomputed on every run.  The lino is rebuilt from
work/pg*.txt into tests/gen/w6a and run with the poll-and-kill runner; the
oracle is rebuilt from noctis-harness/pg_ref.c with gcc.  Nothing is compared
against a stored .bin, and in particular nothing is compared against
work/pg-out.bin, which is an artifact the code under test produced.

Every graded check is then BROKEN, in this same run, and required to fail:

  section 5   one pixel of one page flipped         -> R1 fails, 1 page
              one pixel of every page flipped       -> R1 fails, all 107
              +1 on one bbox field                  -> R2 fails
              +1 on one ipart                       -> R3 fails
              +1 on one mp component                -> P2 fails
              one topology field perturbed          -> P1 fails
              one getcoords return perturbed        -> P3 fails
              one corpus integer perturbed          -> F1 fails
              one binary32 pattern perturbed        -> F2 fails
              the ORACLE rebuilt with --round=chop  -> P2 fails, 18 of 30
              the LINO rebuilt with SEGCLOSED       -> R1 fails,  2 of 107
              the LINO rebuilt with FILLROW         -> R1 fails, 20 of 107
              the LINO rebuilt with SCRATCHOFF      -> R1 fails, 23 of 107
              the LINO rebuilt with PROJXC          -> P1 and P2 fail

The last five are not perturbations of a record.  --round=chop is the
oracle's own alternative rounding schedule, and the four lino sabotages are
real one-line defects compiled and run through the whole pipeline - one per
surface the page check claims to cover, because "the page check bites" is a
claim about a rasteriser and not about a bitmap: SEGCLOSED is Segmento's
DDA, FILLROW is poly3d's flat fill, SCRATCHOFF is the polymap span's re-read
of the scratch pair (the offset-4 trap BUFFERMAP 4.1 settled), and PROJXC is
projection.

THE FIXTURE PROBLEM, AND WHY THIS FILE DOES NOT USE A HASH
==========================================================
The two sides cannot read the same file.  The oracle parses `KEY id k=v` and
the lino tokeniser understands one lexeme, a signed decimal integer, so
work/pg-corpus.txt is necessarily a transliteration.  pg_grade.py's
FIXTURE.shared_corpus row compares the two files' sha256 and therefore can
never pass in the shipped configuration; worse, it is emitted inside an
`if os.path.exists(...)` and deleting work/pg-corpus.txt makes that grader
go green.

F1 replaces it with the thing the hash was standing in for: this file parses
BOTH grammars and compares the pinned numbers case by case, field by field -
2,285 integers across 144 cases.  That is what "the two sides consumed the
same inputs" actually means, it cannot be satisfied by an absent file, and it
is broken in section 5 by perturbing a single integer.

F2 is the same argument for the projection fixture, which this file has to
generate because no lino-grammar copy of the frozen PROJ corpus exists.  The
generated text is read BACK off the disk the lino reads and every binary32
bit pattern is compared against the frozen hex, so a transliteration slip
fails as a fixture error and not as a fake disagreement about the port.

WHAT THE ORACLE IS AND WHAT IT IS NOT
=====================================
noctis-harness/pg_ref.c is implementer 2's transliteration of TDPOLYGS.H's
inline assembly.  It is a DIFFERENT OWNER from the lino port, which is what
makes R1..R3 and P1..P3 evidence rather than self-agreement.  It is not the
1996 binary and this file never claims it is.  The oracle's own knobs
(--acc, --fst, --round) compare it to itself and are MEASUREMENTS; only
--round=chop is used here, and only as a negative control.

Prerequisites: the extended toolchain, gcc on PATH, and the four frozen
corpora under noctis-harness.  A missing prerequisite is reported as a
skipped leg with a non-zero exit, never as a pass.
"""

import os
import re
import shutil
import struct
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import linoharness as lh

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WORK = os.path.join(ROOT, "work")
HARNESS = os.path.join(ROOT, "noctis-harness")
SAND = os.path.join(HERE, "gen", "w6a")

LIBS = ("pgmain.txt", "pgfp.txt", "pgmem.txt", "pgrast.txt", "pgtex.txt",
        "pgproj.txt", "fbmem.txt")
FPLIBS = ("fpabi.txt", "fpctl.txt", "fpx87.txt", "fpconv.txt")
CORPORA = ("pg_corpus_raster.txt", "pg_corpus_edge.txt",
           "pg_corpus_span.txt", "pg_corpus_proj.txt")

PGMAGIC = 1346720577        # 'PGD1'
PGHDRU = 16                 # units of PGDUMP record header
PGDOFF = 4                  # farmalloc's offset - BUFFERMAP 4.1
PGNPIX = 64000
ORACLE_PAGE = 65540         # bytes per page in --pages
SCRATCH_T = 0xFA00          # the tinta scratch pixel, page-relative
SCRATCH_E = 0xFA01

# The camera the port hard-codes.  pgfp.txt "PGF constants": B32DPP=210.0f,
# B32UNEG=100.0f, alfa=beta=gamma=0, cam=(0,0,0).  A frozen PROJ/GETC case
# whose camera differs has no lino counterpart and is NOT GRADED.
DPP210 = "0x43520000"
UNEG100 = "0x42c80000"
ZERO3 = "0x00000000,0x00000000,0x00000000"

MP_BOUND_DECLARED = 1       # FLOATPOLICY's +-1 px envelope
MP_BOUND_CHECKED = 0        # what this corpus measures; see the header


# ===================================================================== setup

def sha_file(path):
    import hashlib
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def fresh_sandbox():
    """Copy every input in from source.  Nothing here survives a run."""
    if os.path.isdir(SAND):
        shutil.rmtree(SAND)
    os.makedirs(os.path.join(SAND, "fp"))
    for name in LIBS:
        shutil.copy(os.path.join(WORK, name), os.path.join(SAND, name))
    for name in FPLIBS:
        shutil.copy(os.path.join(WORK, "fp", name), os.path.join(SAND, "fp", name))
    shutil.copy(os.path.join(WORK, "pg-corpus.txt"),
                os.path.join(SAND, "pg-corpus.txt"))


def build_lino(where, tag):
    """Build <where>/pgmain.txt and return (exe, note)."""
    src = os.path.join(where, "pgmain.txt")
    rc, out = lh.build(src)
    if rc != 0:
        return None, "%s build failed: %s" % (tag, out.strip())
    return os.path.join(where, "pgmain.exe"), out.strip()


def run_lino(exe, where, tag, timeout=120):
    out = os.path.join(where, "pg-out.bin")
    if os.path.exists(out):
        os.remove(out)
    rc, note, blob = lh.run(exe, out, timeout_sec=timeout)
    if blob is None:
        return None, "%s run failed: %s" % (tag, note)
    return blob, note


def build_oracle():
    """gcc the C-from-assembly oracle into the sandbox."""
    if shutil.which("gcc") is None:
        return None, "gcc is not on PATH"
    exe = os.path.join(SAND, "pgref.exe")
    p = subprocess.run(["gcc", "-O2", "-std=c11", "-o", exe,
                        os.path.join(HARNESS, "pg_ref.c")],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if p.returncode != 0:
        return None, "gcc failed: " + (p.stdout or "") + (p.stderr or "")
    return exe, "built"


def run_oracle(exe, args=(), corpora=CORPORA, pages=None):
    cmd = [exe] + list(args)
    if pages:
        cmd.append("--pages=" + pages)
    cmd += [os.path.join(HARNESS, c) for c in corpora]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if p.returncode != 0:
        raise SystemExit("pg_ref failed rc=%d: %s" % (p.returncode, p.stderr))
    recs = {}
    for line in p.stdout.splitlines():
        t = line.split()
        if t and t[0] and t[0][0] == "K":
            recs.setdefault((t[0], t[2]), []).append(t[3:])
    return recs


def kv(tokens):
    out = {}
    for t in tokens:
        if "=" in t:
            k, v = t.split("=", 1)
            out[k] = v
    return out


# ============================================================ the two grammars

def parse_frozen(path):
    """The oracle's grammar: `DIR id key=value ...`, in file order."""
    rows = []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            s = line.strip()
            if not s or s[0] == "#":
                continue
            t = s.split()
            rows.append((t[0], t[1], kv(t[2:])))
    return rows


def parse_lino_corpus(path):
    """The lino grammar: a flat stream of signed decimal integers, '#' to EOL.

    Returns [(op, caseid, name, [field, ...])] in file order.  The name comes
    from the `# NAME case N` comment the transliterator writes; it is not a
    lexeme the tokeniser sees, so a name that does not match its row is a
    defect this reader can see and the lino cannot.
    """
    names, nums = {}, []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.lstrip().startswith("#"):
                w = line.split()
                if len(w) >= 4 and w[2] == "case":
                    names[int(w[3])] = w[1]
                continue
            nums += [int(x) for x in re.findall(r"-?\d+", line)]
    rows, i = [], 0
    while i < len(nums):
        op = nums[i]
        if op == 0:
            break
        cid, pre = nums[i + 1], nums[i + 2]
        j = i + 3
        if op == 1:                                  # SEG
            body = nums[j:j + 4]; j += 4
        elif op == 2:                                # BBOX
            n = nums[j]; body = nums[j:j + 1 + 2 * n]; j += 1 + 2 * n
        elif op == 3:                                # FILL
            n = nums[j]; body = nums[j:j + 1 + 2 * n + 7]; j += 1 + 2 * n + 7
        elif op == 4:                                # EDGE
            vr22 = nums[j]; body = nums[j:j + 1 + vr22 + 2]; j += 1 + vr22 + 2
        elif op == 5:                                # SPAN
            nblk = nums[j + 10]
            body = nums[j:j + 11 + 2 * (nblk + 1)]
            j += 11 + 2 * (nblk + 1)
        elif op in (6, 7, 8):                        # PROJ / PMAP / GCOORD
            raise SystemExit("test_raster: op %d in %s; the reader for it "
                             "is section 4, not this one" % (op, path))
        else:
            raise SystemExit("test_raster: unknown opcode %d in %s" % (op, path))
        rows.append((op, cid, names.get(cid, "?case%d" % cid), pre, body))
        i = j
    return rows


PRE = {"PRE0": 0, "PRE1": 1, "PRE2": 2, "PRE3": 3}
TEX = {"TEX0": 0, "TEX1": 1, "TEX2": 2, "TEX3": 3}


def ilist(s):
    return [int(x) for x in re.split(r"[,;]", s) if x.strip()]


def frozen_as_lino(kind, d):
    """Re-derive the lino row for one frozen case, from the frozen keys only.

    This is the transliteration written out a SECOND time, from the other
    grammar, so F1 compares two independent readings of one fixture rather
    than a file against its own hash.
    """
    pre = PRE[d.get("pre", "PRE0")]
    if kind == "SEG":
        return 1, pre, [int(d["xp"]), int(d["yp"]), int(d["xa"]), int(d["ya"])]
    if kind == "BBOX":
        n = int(d["n"])
        return 2, pre, [n] + ilist(d["mp"])
    if kind == "FILL":
        n = int(d["n"])
        return 3, pre, ([n] + ilist(d["mp"]) + ilist(d["bbox"])
                        + [int(d.get("colore", 1)), int(d.get("flares", 0)),
                           int(d.get("entity", 1))])
    if kind == "EDGE":
        mp = ilist(d["mp"])
        return 4, pre, [len(mp)] + mp + [int(d["miny"]), int(d["maxy"])]
    if kind == "SPAN":
        uv = ilist(d["uv"])
        nblk = len(uv) // 2 - 1
        return 5, pre, [TEX[d.get("tex", "TEX0")], int(d["i"]),
                        int(d["ipart"]), int(d["fpart"]), int(d["tinta"]),
                        int(d["escr"]), int(d["flares"]), int(d["cull"]),
                        int(d["half"]), int(d["maxy"]), nblk] + uv
    return None, None, None


# ============================================================ the lino records

def lino_records(blob):
    """[(kind, tag, caseid, payload)] in file order."""
    u = struct.unpack("<%di" % (len(blob) // 4), blob)
    out, i = [], 0
    while i + PGHDRU <= len(u):
        if u[i] != PGMAGIC:
            raise SystemExit("test_raster: PGDUMP magic lost at unit %d" % i)
        cnt = u[i + 5]
        out.append((u[i + 2], u[i + 8], u[i + 6],
                    list(u[i + PGHDRU:i + PGHDRU + cnt])))
        i += PGHDRU + cnt
    return out


def unpack_page(payload):
    """16,000 packed units -> 64,000 bytes, 4 pixels per unit little-endian."""
    b = bytearray()
    for v in payload:
        b += bytes((v & 255, (v >> 8) & 255, (v >> 16) & 255, (v >> 24) & 255))
    return bytes(b)


def oracle_pages(path):
    """{name: bytes} from --pages: 32-byte name then 65,540 page bytes."""
    out = {}
    with open(path, "rb") as fh:
        d = fh.read()
    i = 0
    while i + 32 + ORACLE_PAGE <= len(d):
        nm = d[i:i + 32].split(b"\0")[0].decode("ascii", "replace")
        out[nm] = d[i + 32:i + 32 + ORACLE_PAGE]
        i += 32 + ORACLE_PAGE
    return out


# ================================================== the projection fixture (4)

def joinable_proj(rows):
    """The frozen PROJ/GETC cases whose camera is the one the port hard-codes.

    Returns (joinable, skipped) where skipped carries the reason, so section 6
    can report the ungraded remainder by name instead of by silence.
    """
    keep, skip = [], []
    for kind, name, d in rows:
        if kind not in ("PROJ", "GETC"):
            skip.append((kind, name, "no lino opcode for %s" % kind))
            continue
        why = []
        if d.get("cam", ZERO3) != ZERO3:
            why.append("cam!=0")
        if d.get("ang", ZERO3) != ZERO3:
            why.append("ang!=0")
        if d.get("dpp") != DPP210:
            why.append("dpp!=210.0f")
        if kind == "PROJ" and d.get("uneg") != UNEG100:
            why.append("uneg!=100.0f")
        if why:
            skip.append((kind, name, ",".join(why)))
        else:
            keep.append((kind, name, d))
    return keep, skip


def i32(hexstr):
    b = int(hexstr, 16) & 0xFFFFFFFF
    return b - (1 << 32) if b >= (1 << 31) else b


def hexlist(s):
    return [i32(x) for x in re.split(r"[,;]", s) if x.strip()]


def read_proj_corpus(path):
    """Read the generated projection fixture BACK off disk, independently.

    write_proj_corpus serialises; this parses.  F2 compares what the lino
    actually consumed against the frozen hex, so a transliteration slip is a
    failure here rather than a silent disagreement in the join.
    """
    nums, names = [], {}
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.lstrip().startswith("#"):
                w = line.split()
                if len(w) >= 4 and w[2] == "case":
                    names[int(w[3])] = w[1]
                continue
            nums += [int(x) for x in re.findall(r"-?\d+", line)]
    out, i = [], 0
    while i < len(nums) and nums[i] != 0:
        op, cid, _pre = nums[i], nums[i + 1], nums[i + 2]
        if op == 6:
            nrv = nums[i + 3]
            v = nums[i + 7:i + 7 + 3 * nrv]
            i += 7 + 3 * nrv
        elif op == 7:
            nrv = nums[i + 4]
            v = nums[i + 10:i + 10 + 3 * nrv]
            i += 10 + 3 * nrv
        elif op == 8:
            nrv = nums[i + 3]
            v = nums[i + 4:i + 4 + 3 * nrv]
            i += 4 + 3 * nrv
        else:
            raise SystemExit("test_raster: opcode %d in the projection "
                             "fixture, which carries only 6, 7 and 8" % op)
        out.append((op, cid, names.get(cid, "?case%d" % cid), v))
    return out


def write_proj_corpus(where, joinable):
    """Transliterate the joinable subset into the lino integer grammar.

    Floats cross as the signed decimal value of their binary32 BIT PATTERN,
    so no decimal float parser is shared between the two sides and a
    rounding difference in a parser cannot masquerade as agreement.
    """
    lines = ["# Wave 6a projection fixture, transliterated by "
             "tests/test_raster.py from noctis-harness/pg_corpus_proj.txt.",
             "# Only cases whose camera matches the port's hard-coded one "
             "appear here; see joinable_proj()."]
    cases, cid = [], 0
    for kind, name, d in joinable:
        cid += 1
        lines.append("# %s case %d" % (name, cid))
        if kind == "GETC":
            lines.append("8 %d 0 1 %s"
                         % (cid, " ".join(str(x) for x in hexlist(d["p"]))))
            cases.append((cid, name, "getcoords", 1))
            continue
        nrv = int(d["nrv"])
        v = " ".join(str(x) for x in hexlist(d["v"]))
        which = d.get("which", "poly3d")
        if which == "poly3d":
            lines.append("6 %d 0 %d %s %s %s %s"
                         % (cid, nrv, d.get("colore", 1), d.get("flares", 0),
                            d.get("entity", 1), v))
        else:
            # PMAP: tex, nv, tinta, escr, flares, cull, half.  Only the
            # projection half of polymap is graded here, and it reads none of
            # the span parameters, so they are pinned at zero.
            lines.append("7 %d 0 0 %d 0 0 %s 0 0 %s"
                         % (cid, nrv, d.get("flares", 0), v))
        cases.append((cid, name, which, nrv))
    lines.append("0")
    os.makedirs(where, exist_ok=True)
    with open(os.path.join(where, "pg-corpus.txt"), "w", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    return cases


# ========================================================== the joins, as data

def join_pages(lino, pages, names):
    """[(name, lino_bytes, oracle_bytes)] for every case both sides drew."""
    out = []
    for kind, tag, case, payload in lino:
        if kind != 20:
            continue
        nm = names.get(case)
        if nm in pages:
            out.append((nm, unpack_page(payload), pages[nm]))
    return out


def page_diff(pair):
    """Indices where a compared page disagrees.  0 <= i < 64,000.

    The fast path is a whole-slice equality; the index walk runs only when
    that has already said the two differ, so the returned list is never the
    thing that decides the verdict on an agreeing page.
    """
    mine = pair[1]
    theirs = pair[2][PGDOFF:PGDOFF + PGNPIX]
    if mine[:PGNPIX] == theirs:
        return []
    return [i for i in range(PGNPIX) if mine[i] != theirs[i]]


def join_bbox(lino, orc, names):
    """[(name, lino5, oracle5)] over K22 vs the oracle's K25 BBOX."""
    out = []
    for kind, tag, case, b in lino:
        if kind != 22:
            continue
        nm = names.get(case)
        o = orc.get(("K25", nm))
        if not o:
            continue
        d = kv(o[0])
        out.append((nm, (b[0], b[1], b[2], b[3], b[4]),
                    (int(d["minx"]), int(d["maxx"]), int(d["miny"]),
                     int(d["maxy"]), int(d["si"]))))
    return out


def join_limits(lino, orc, names):
    """[(name, lino_pairs, oracle_pairs)] over K23 vs the oracle's K23 LIM."""
    out = []
    for kind, tag, case, b in lino:
        if kind != 23:
            continue
        nm = names.get(case)
        o = orc.get(("K23", nm))
        if not o:
            continue
        d = kv(o[0][:2])
        y0, y1 = int(d["y0"]), int(d["y1"])
        theirs = [tuple(int(x) for x in tok.split(":")) for tok in o[0][2:]]
        mine = [(b[2 + 2 * k], b[3 + 2 * k]) for k in range(y0, y1 + 1)]
        out.append((nm, mine, theirs))
    return out


def join_topo(lino, orc, cases):
    """The projection join.

    WHICH FIELDS ARE COMPARED, AND WHY NOT ALL OF THEM.  A record slot that
    one side never wrote for this case is not a disagreement; comparing it
    would be comparing stale state.  Three slots are conditional and each
    condition is read out of the code, not fitted to the data:

      rwf[k]  both sides loop k < nrv (pg_ref.c:1222, pgproj.txt:196-197), so
              for a triangle rwf[3] is untouched: zero on the oracle's
              zeroed TOPO, and whatever the previous case left on the lino.
              It describes a vertex neither side has.
      vr2     pgproj.txt:680 assigns [PJvr2] = [PJvr6] once the whole 2-D
              clip chain succeeds.  So the lino's slot 2 holds vr6 exactly
              when the chain ran (gsi != 0) and returned success (ret == 0),
              and holds the near-clip count otherwise.
      min_x   polymap has no 2-D clipper and its projectmap searches only Y
      max_x   (pgproj.txt:395-403), so X is never written on that path.

    Returns (rows, mp_rows) where each row is (name, field, got, want).
    """
    rows, mp_rows = [], []
    byid = {c[0]: c for c in cases}
    for kind, tag, case, b in lino:
        if kind != 24 or tag != 5:
            continue
        cid, name, which, nrv = byid[case]
        o = orc.get(("K24", name))
        if not o:
            continue
        d = kv(o[0])
        ret, doflag, gsi = int(d["ret"]), int(d["doflag"]), int(d["gsi"])
        rows.append((name, "ret/doflag", (b[0], b[1]), (ret, doflag)))
        rows.append((name, "rwf", tuple(b[8:8 + nrv]),
                     tuple(int(c) for c in d["rwf"][:nrv])))
        if doflag == 0:
            continue                      # nothing past the near plane exists
        vr2 = int(d["vr6"]) if (gsi and ret == 0) else int(d["vr2"])
        got, want = [b[2]], [vr2]
        if gsi:
            for k, key in enumerate(("vr3", "vr4", "vr5", "vr6")):
                got.append(b[3 + k])
                want.append(int(d[key]))
                if int(d[key]) < 3:       # this stage bailed; later ones never ran
                    break
        rows.append((name, "stages", tuple(got), tuple(want)))
        bb = tuple(int(x) for x in d["bbox"].split(","))
        mine = (b[12], b[13], b[14], b[15])
        if which == "polymap":
            bb, mine = bb[2:], mine[2:]
        rows.append((name, "bbox", mine, bb))
        om = orc.get(("K22", name))
        if om:
            n = int(om[0][0].split("=")[1])
            theirs = [int(x) for x in om[0][1:]]
            mp_rows.append((name, b[16:16 + 2 * n], theirs))
    return rows, mp_rows


def join_getc(lino, orc, cases):
    """[(name, got, want)] over the lino's tag-7 K24 vs the oracle's K27.

    The returned char is graded unconditionally.  x and y are graded only
    when the char is non-zero: getcoords compares its four bounds with STRICT
    < and >, and a point it rejects leaves the coordinates undefined on both
    sides (pgmain.txt:282-285).
    """
    out = []
    byid = {c[0]: c for c in cases}
    for kind, tag, case, b in lino:
        if kind != 24 or tag != 7:
            continue
        cid, name, which, nrv = byid[case]
        o = orc.get(("K27", name))
        if not o:
            continue
        d = kv(o[0])
        r = int(d["ret"])
        if r:
            out.append((name, (b[0], b[1], b[2]), (r, int(d["x"]), int(d["y"]))))
        else:
            out.append((name, (b[0],), (r,)))
    return out


# ================================================================== the report

def modal_free_bytes(page):
    """How many bytes of a page differ from its most common value.

    A page whose every byte is the modal value drew nothing distinguishable,
    and comparing two such pages is agreement about nothing.
    """
    import collections
    c = collections.Counter(page)
    return len(page) - c.most_common(1)[0][1]


def n_page_mismatches(pairs):
    return sum(1 for p in pairs if page_diff(p))


def n_tuple_mismatches(rows):
    return sum(1 for r in rows if r[-2] != r[-1])


def mp_worst(mp_rows):
    """(max |delta| over every component, number of cases that moved)."""
    worst, moved = 0, 0
    for name, mine, theirs in mp_rows:
        d = max([abs(mine[k] - theirs[k]) for k in range(len(theirs))] or [0])
        worst = max(worst, d)
        moved += (d > 0)
    return worst, moved


def mp_components(mp_rows):
    return sum(len(r[2]) for r in mp_rows)


# ================================================================ the sabotages

SABOTAGE = {
    # name        library      one line, replaced by one line
    "SEGCLOSED": ("pgrast.txt",
                  "\t? C '< [SGt] -> PG seg do;",
                  "\t? C '<= [SGt] -> PG seg do;",
                  "Segmento's DDA closes the half-open x interval, so the "
                  "greater-x endpoint gets painted"),
    "FILLROW":   ("pgrast.txt",
                  "\t? C '<= [DBlimy] -> PG db c0 row;",
                  "\t? C '< [DBlimy] -> PG db c0 row;",
                  "poly3d's flat fill stops one row short of its own limit"),
    "SCRATCHOFF": ("pgtex.txt",
                   "\tA = PGSCRT; A + PGDOFF; [PGdi] = A; => PG load; end;",
                   "\tA = PGSCRT; [PGdi] = A; => PG load; end;",
                   "the span's tinta re-read drops farmalloc's offset 4 - the "
                   "trap BUFFERMAP 4.1 settled"),
    "PROJXC":    ("pgproj.txt",
                  "\t[PGFi] = FSXC; => PGF add;\n"
                  "\t[PGFi] = FSW0; => PGF sa;\t\t\t( the WIDE value )",
                  "\t[PGFi] = FSYC; => PGF add;\n"
                  "\t[PGFi] = FSW0; => PGF sa;\t\t\t( the WIDE value )",
                  "project3d adds the vertical screen centre to the "
                  "HORIZONTAL coordinate"),
}


def build_sabotage(name):
    """A fresh sandbox with exactly one line changed.  Returns (dir, note)."""
    lib, old, new, _why = SABOTAGE[name]
    where = os.path.join(SAND, "brk" + name.lower())
    if os.path.isdir(where):
        shutil.rmtree(where)
    os.makedirs(os.path.join(where, "fp"))
    for f in LIBS:
        shutil.copy(os.path.join(SAND, f), os.path.join(where, f))
    for f in FPLIBS:
        shutil.copy(os.path.join(SAND, "fp", f), os.path.join(where, "fp", f))
    path = os.path.join(where, lib)
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    hits = text.count(old)
    if hits != 1:
        return None, "anchor for %s appears %d times in %s, expected 1" % (
            name, hits, lib)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text.replace(old, new))
    return where, "one line changed in " + lib


# ======================================================================= main

def main():
    quick = "--quick" in sys.argv
    chk = lh.Check("Wave 6a - projection, poly3d and polymap "
                   "(tests/test_raster.py)")

    missing = [c for c in CORPORA if not os.path.exists(os.path.join(HARNESS, c))]
    chk.ok(not missing, "the four frozen corpora are present",
           "missing: %s" % missing)
    if missing:
        return chk.done()

    # ---------------------------------------------------- 1. both sides fresh
    print("\n-- 1. both sides recomputed from source ------------------------")
    fresh_sandbox()
    for f in LIBS:
        chk.note("lino %-12s %s" % (f, sha_file(os.path.join(SAND, f))[:16]))
    chk.note("oracle pg_ref.c  %s" % sha_file(os.path.join(HARNESS, "pg_ref.c"))[:16])

    exe, note = build_lino(SAND, "clean")
    chk.ok(exe is not None, "the lino port builds from work/pg*.txt", note)
    if exe is None:
        return chk.done()
    blob, note = run_lino(exe, SAND, "clean")
    chk.ok(blob is not None, "the lino port runs and writes a PGDUMP", note)
    if blob is None:
        return chk.done()

    oref, note = build_oracle()
    chk.ok(oref is not None, "the C-from-assembly oracle builds with gcc", note)
    if oref is None:
        return chk.done()

    lino = lino_records(blob)
    trailer = [r for r in lino if r[0] == 25]
    chk.ok(len(trailer) == 1, "the PGDUMP carries exactly one trailer record",
           "found %d" % len(trailer))
    tr = trailer[0][3]
    chk.ok(tr[1] == 0, "the driver rejected no corpus row", "bad=%d" % tr[1])
    chk.ok(tr[4] == tr[2], "the tokeniser consumed every token it produced",
           "consumed %d of %d" % (tr[4], tr[2]))
    chk.ok(tr[5] == 0x033F, "the x87 control word is still 033F at exit",
           "cw=%04X" % tr[5])

    pages_bin = os.path.join(SAND, "oracle-pages.bin")
    orc = run_oracle(oref, pages=pages_bin)
    pages = oracle_pages(pages_bin)
    chk.ok(len(pages) > 0, "the oracle emitted pages", "%d" % len(pages))

    # -------------------------------------------- 2. F1: the two sides' inputs
    print("\n-- 2. F1  the two sides read the same pinned numbers ------------")
    frozen_rows = []
    for c in CORPORA[:3]:
        frozen_rows += parse_frozen(os.path.join(HARNESS, c))
    lino_rows = parse_lino_corpus(os.path.join(SAND, "pg-corpus.txt"))
    fz = [(k, n, d) for (k, n, d) in frozen_rows
          if k in ("SEG", "BBOX", "FILL", "EDGE", "SPAN")]

    chk.ok(len(lino_rows) == len(fz),
           "F1a the lino corpus has one row per frozen raster case",
           "lino %d, frozen %d" % (len(lino_rows), len(fz)))
    order_bad, field_bad, nfields = [], [], 0
    for k in range(min(len(lino_rows), len(fz))):
        op, cid, name, pre, body = lino_rows[k]
        fkind, fname, fd = fz[k]
        if name != fname:
            order_bad.append((k, name, fname))
            continue
        wop, wpre, wbody = frozen_as_lino(fkind, fd)
        nfields += 2 + len(wbody)
        if (op, pre, body) != (wop, wpre, wbody):
            field_bad.append((name, (op, pre, body), (wop, wpre, wbody)))
    chk.ok(not order_bad, "F1b the two corpora agree on case order",
           "%d out of order, first %s" % (len(order_bad), order_bad[:1]))
    chk.ok(not field_bad,
           "F1c every pinned integer agrees, re-derived from both grammars",
           "%d rows differ over %d fields, first %s"
           % (len(field_bad), nfields, field_bad[:1]))
    chk.note("F1 compared %d pinned integers across %d cases"
             % (nfields, len(lino_rows)))

    names = {cid: name for (_op, cid, name, _p, _b) in lino_rows}

    # -------------------------------------------------- 3. the exact rasteriser
    print("\n-- 3. R1..R3  the rasteriser, exact ------------------------------")
    pairs = join_pages(lino, pages, names)
    chk.ok(len(pairs) > 0, "R1a at least one page joins", "%d" % len(pairs))
    blank = [p[0] for p in pairs if modal_free_bytes(p[1]) == 0]
    chk.ok(not blank,
           "R1b every compared page drew something distinguishable",
           "%d all-modal pages: %s" % (len(blank), blank[:3]))
    bad_pages = [p[0] for p in pairs if page_diff(p)]
    chk.ok(not bad_pages,
           "R1c every joined page is byte-identical over all %d pixels" % PGNPIX,
           "%d differ: %s" % (len(bad_pages), bad_pages[:3]))
    # R1d: the scratch pair at 0xFA00/0xFA01 is BUFFERMAP 2.6's free canary -
    # a span that never ran did not write them.  Saying "the compared range
    # includes them" would be arithmetic between two constants, so what is
    # checked instead is that live scratch content actually reached the
    # comparison: pages on which BOTH sides carry the same NON-zero byte
    # there.  Zero of those and the canary is decorative.
    live = [p[0] for p in pairs
            if p[1][SCRATCH_T - PGDOFF] and
            p[1][SCRATCH_T - PGDOFF] == p[2][SCRATCH_T]]
    chk.ok(len(live) > 0,
           "R1d the 0xFA00 scratch pixel is inside the compared range and "
           "carries live non-zero content on both sides, so a span that never "
           "wrote it cannot pass R1c",
           "%d of %d pages carry a non-zero agreed tinta scratch: %s"
           % (len(live), len(pairs), live[:3]))

    # R1e: colour 255 is the polygon-edge sentinel, and this is where it comes
    # from and what consumes it.  Segmento stores 255 and nothing else
    # (pgrast.txt:194 vertical branch, :245 general branch); drawb's row loop
    # then scans the row for 255 with repne/repe scasb and fills BETWEEN the
    # runs it finds (pgrast.txt:616-648).  So a 255 pixel that was already on
    # the page before the polygon was drawn is indistinguishable from an edge
    # this polygon just laid, and the fill brackets the wrong span.  Five
    # frozen cases exist for exactly that, and R1c grades them byte for byte -
    # but only if they are actually in the compared set, which is what this
    # counts.  A corpus that lost them would still pass R1c and mean less.
    SENTINEL_CASES = ("PRE255MID", "PRE255RIGHT", "ADJ255",
                      "COL255_A", "COL255_B")
    have = [n for n in SENTINEL_CASES if n in [p[0] for p in pairs]]
    chk.ok(len(have) == len(SENTINEL_CASES),
           "R1e all %d cases that put colour 255 on the page BEFORE the fill "
           "are in the compared set, so the sentinel scan is graded and not "
           "merely present" % len(SENTINEL_CASES),
           "have %s, missing %s"
           % (have, [n for n in SENTINEL_CASES if n not in have]))

    bbrows = join_bbox(lino, orc, names)
    chk.ok(len(bbrows) > 0, "R2a the bbox gate joins", "%d cases" % len(bbrows))
    chk.ok(n_tuple_mismatches(bbrows) == 0,
           "R2b every bbox gate result is exact",
           "%d of %d differ" % (n_tuple_mismatches(bbrows), len(bbrows)))

    limrows = join_limits(lino, orc, names)
    nvals = sum(2 * len(r[2]) for r in limrows)
    chk.ok(len(limrows) > 0, "R3a the span limits join", "%d cases" % len(limrows))
    chk.ok(n_tuple_mismatches(limrows) == 0,
           "R3b every ipart/fpart pair is exact over %d integers" % nvals,
           "%d of %d cases differ" % (n_tuple_mismatches(limrows), len(limrows)))

    # ------------------------------------------------------- 4. the projection
    print("\n-- 4. P1..P3  the projection -------------------------------------")
    proj_rows = parse_frozen(os.path.join(HARNESS, "pg_corpus_proj.txt"))
    keep, skipped = joinable_proj(proj_rows)
    pdir = os.path.join(SAND, "proj")
    pcases = write_proj_corpus(pdir, keep)

    # F2: the fixture the lino will read, re-parsed off disk and compared
    # against the frozen hex.  Without this, a transliteration slip would
    # show up only as a disagreement in the join, where it would be
    # indistinguishable from a defect in the port.
    reread = read_proj_corpus(os.path.join(pdir, "pg-corpus.txt"))
    f2_bad, f2_vals = [], 0
    for k, (op, cid, nm, v) in enumerate(reread):
        kind, name, d = keep[k]
        want = hexlist(d["p"] if kind == "GETC" else d["v"])
        if nm != name or len(v) != len(want):
            f2_bad.append((nm, name, len(v), len(want)))
            continue
        for j in range(len(want)):
            f2_vals += 1
            if v[j] != want[j]:
                f2_bad.append((nm, j, v[j], want[j]))
    chk.ok(not f2_bad,
           "F2 every float in the projection fixture is the frozen binary32 "
           "bit pattern, re-parsed off the disk the lino reads",
           "%d of %d cases differ over %d patterns, first %s"
           % (len(f2_bad), len(reread), f2_vals, f2_bad[:1]))

    shutil.copy(exe, os.path.join(pdir, "pgmain.exe"))
    pblob, note = run_lino(os.path.join(pdir, "pgmain.exe"), pdir, "proj")
    chk.ok(pblob is not None, "P0 the port runs the projection fixture", note)
    if pblob is None:
        return chk.done()
    plino = lino_records(pblob)
    ptr = [r for r in plino if r[0] == 25][0][3]
    chk.ok(ptr[0] == len(pcases) and ptr[1] == 0,
           "P0b the port ran every transliterated projection case",
           "ran %d of %d, bad %d" % (ptr[0], len(pcases), ptr[1]))

    porc = run_oracle(oref, corpora=("pg_corpus_proj.txt",))
    trows, mprows = join_topo(plino, porc, pcases)
    gcrows = join_getc(plino, porc, pcases)

    chk.ok(len(trows) > 0, "P1a the topology joins", "%d field groups" % len(trows))
    chk.ok(n_tuple_mismatches(trows) == 0,
           "P1b every joined topology field is exact",
           "%d of %d differ, first %s"
           % (n_tuple_mismatches(trows), len(trows),
              [r for r in trows if r[-2] != r[-1]][:1]))

    ncomp = mp_components(mprows)
    worst, moved = mp_worst(mprows)
    chk.ok(ncomp > 0, "P2a the projected vertex table joins",
           "%d components over %d cases" % (ncomp, len(mprows)))
    chk.ok(worst <= MP_BOUND_DECLARED,
           "P2b mp[] is inside the DECLARED +-%d px envelope" % MP_BOUND_DECLARED,
           "max|delta| %d over %d components" % (worst, ncomp))
    chk.ok(worst <= MP_BOUND_CHECKED,
           "P2c mp[] is exact, which is tighter than the envelope and is what "
           "closes the chop hole",
           "max|delta| %d, %d of %d cases moved" % (worst, moved, len(mprows)))

    chk.ok(len(gcrows) > 0, "P3a getcoords joins", "%d cases" % len(gcrows))
    chk.ok(n_tuple_mismatches(gcrows) == 0,
           "P3b every getcoords result is exact",
           "%d of %d differ" % (n_tuple_mismatches(gcrows), len(gcrows)))

    # ----------------------------------------------- 5. break every one of them
    print("\n-- 5. every graded check, broken --------------------------------")

    # 5.1 one pixel of one page
    hurt = list(pairs)
    victim = bytearray(hurt[0][1])
    victim[12345] ^= 1
    hurt[0] = (hurt[0][0], bytes(victim), hurt[0][2])
    chk.ok(n_page_mismatches(hurt) == 1,
           "B1 flipping ONE bit of ONE pixel makes R1c fail on exactly 1 page",
           "%d pages differ" % n_page_mismatches(hurt))

    # 5.2 one pixel of every page
    hurt = []
    for nm, mine, theirs in pairs:
        v = bytearray(mine)
        v[12345] ^= 1
        hurt.append((nm, bytes(v), theirs))
    chk.ok(n_page_mismatches(hurt) == len(pairs),
           "B2 one flipped pixel per page makes R1c fail on every page, so no "
           "page is passing for a reason other than its own content",
           "%d of %d pages differ" % (n_page_mismatches(hurt), len(pairs)))

    # 5.3 the tuple joins
    hurt = list(bbrows)
    hurt[0] = (hurt[0][0], (hurt[0][1][0] + 1,) + hurt[0][1][1:], hurt[0][2])
    chk.ok(n_tuple_mismatches(hurt) == 1, "B3 +1 on one bbox min_x makes R2b fail",
           "%d of %d cases differ" % (n_tuple_mismatches(hurt), len(hurt)))

    hurt = list(limrows)
    m = list(limrows[0][1])
    m[0] = (m[0][0] + 1, m[0][1])
    hurt[0] = (hurt[0][0], m, hurt[0][2])
    chk.ok(n_tuple_mismatches(hurt) == 1, "B4 +1 on one ipart makes R3b fail",
           "%d of %d cases differ" % (n_tuple_mismatches(hurt), len(hurt)))

    hurt = list(trows)
    hurt[0] = (hurt[0][0], hurt[0][1], (hurt[0][2][0] + 1,) + hurt[0][2][1:],
               hurt[0][3])
    chk.ok(n_tuple_mismatches(hurt) == 1,
           "B5 perturbing one topology field makes P1b fail",
           "%d of %d field groups differ" % (n_tuple_mismatches(hurt), len(hurt)))

    hurt = list(gcrows)
    hurt[0] = (hurt[0][0], (hurt[0][1][0] + 1,) + hurt[0][1][1:], hurt[0][2])
    chk.ok(n_tuple_mismatches(hurt) == 1,
           "B6 perturbing one getcoords return makes P3b fail",
           "%d of %d cases differ" % (n_tuple_mismatches(hurt), len(hurt)))

    hurt = [(nm, [v + 1 for v in mine], theirs) for nm, mine, theirs in mprows]
    w2, moved2 = mp_worst(hurt)
    chk.ok(w2 > MP_BOUND_CHECKED and w2 <= MP_BOUND_DECLARED,
           "B7 +1 on every mp[] component fails the exact check and PASSES the "
           "declared envelope - which is exactly why P2c is the one that counts",
           "max|delta| %d, checked bound %d, declared bound %d"
           % (w2, MP_BOUND_CHECKED, MP_BOUND_DECLARED))
    hurt = [(nm, [v + 2 for v in mine], theirs) for nm, mine, theirs in mprows]
    w3, _ = mp_worst(hurt)
    chk.ok(w3 > MP_BOUND_DECLARED,
           "B8 +2 on every mp[] component fails the declared envelope too, so "
           "the envelope is not vacuous either",
           "max|delta| %d > %d" % (w3, MP_BOUND_DECLARED))

    # 5.4 F1, broken by perturbing one pinned integer
    hurt_rows = list(lino_rows)
    op, cid, name, pre, body = hurt_rows[0]
    hurt_rows[0] = (op, cid, name, pre, [body[0] + 1] + list(body[1:]))
    nbad = 0
    for k in range(min(len(hurt_rows), len(fz))):
        o2, c2, n2, p2, b2 = hurt_rows[k]
        wop, wpre, wbody = frozen_as_lino(fz[k][0], fz[k][2])
        nbad += ((o2, p2, b2) != (wop, wpre, wbody))
    chk.ok(nbad == 1, "B9 +1 on one pinned corpus integer makes F1c fail",
           "%d of %d rows differ" % (nbad, len(hurt_rows)))

    # 5.4b F2, broken by perturbing one binary32 bit pattern
    nbad2 = 0
    for k, (op, cid, nm, v) in enumerate(reread):
        kind, name, d = keep[k]
        want = hexlist(d["p"] if kind == "GETC" else d["v"])
        mine = ([v[0] + 1] + list(v[1:])) if k == 0 else v
        for j in range(len(want)):
            if mine[j] != want[j]:
                nbad2 += 1
    chk.ok(nbad2 == 1,
           "B9b +1 on one binary32 bit pattern in the projection fixture "
           "makes F2 fail",
           "%d of %d patterns differ" % (nbad2, f2_vals))

    # 5.5 the oracle's own alternative rounding schedule
    chop = run_oracle(oref, args=("--round=chop",), corpora=("pg_corpus_proj.txt",))
    ctrows, cmprows = join_topo(plino, chop, pcases)
    cworst, cmoved = mp_worst(cmprows)
    chk.ok(cworst > MP_BOUND_CHECKED,
           "B10 the oracle rebuilt with --round=chop fails P2c, so P2c really "
           "does discriminate the rounding mode the port must reproduce",
           "max|delta| %d, %d of %d cases moved"
           % (cworst, cmoved, len(cmprows)))
    chk.ok(cworst <= MP_BOUND_DECLARED,
           "B11 ... and a chop error is invisible to the DECLARED envelope, "
           "measured rather than argued",
           "chop max|delta| %d <= declared %d" % (cworst, MP_BOUND_DECLARED))
    chk.ok(n_tuple_mismatches(ctrows) > 0,
           "B12 --round=chop also moves the topology bbox, so P1b bites too",
           "%d of %d field groups differ"
           % (n_tuple_mismatches(ctrows), len(ctrows)))

    # 5.6 four real one-line defects, compiled and run through the pipeline.
    # One per surface R1c and P1b claim to cover, because "the page check
    # bites" is a claim about a rasteriser, not about a bitmap: SEGCLOSED is
    # Segmento's DDA, FILLROW is poly3d's flat fill, SCRATCHOFF is the
    # polymap span's re-read of the scratch pair, PROJXC is the projection.
    RASTER_BREAKS = ("SEGCLOSED", "FILLROW", "SCRATCHOFF")
    if quick:
        chk.note("--quick: the four lino sabotages were NOT built.  This run "
                 "does not show that R1c and P1b bite on a real defect.")
        chk.ok(False, "B13/B14 the lino sabotages ran",
               "skipped by --quick, which is not a pass")
    else:
        for tag in RASTER_BREAKS:
            where, note = build_sabotage(tag)
            chk.ok(where is not None,
                   "B13 %-11s is exactly one line: %s"
                   % (tag, SABOTAGE[tag][3]), note)
            if not where:
                continue
            sexe, note = build_lino(where, tag)
            chk.ok(sexe is not None, "B13 %-11s builds" % tag, note)
            if not sexe:
                continue
            shutil.copy(os.path.join(SAND, "pg-corpus.txt"),
                        os.path.join(where, "pg-corpus.txt"))
            sblob, note = run_lino(sexe, where, tag)
            chk.ok(sblob is not None, "B13 %-11s runs" % tag, note)
            if not sblob:
                continue
            sp = join_pages(lino_records(sblob), pages, names)
            n = n_page_mismatches(sp)
            chk.ok(n > 0,
                   "B13 %-11s makes R1c fail on a real build" % tag,
                   "%d of %d pages differ" % (n, len(sp)))

        where, note = build_sabotage("PROJXC")
        chk.ok(where is not None,
               "B14a PROJXC is exactly one line: " + SABOTAGE["PROJXC"][3], note)
        if where:
            sexe, note = build_lino(where, "PROJXC")
            chk.ok(sexe is not None, "B14b PROJXC builds", note)
            if sexe:
                shutil.copy(os.path.join(pdir, "pg-corpus.txt"),
                            os.path.join(where, "pg-corpus.txt"))
                sblob, note = run_lino(sexe, where, "PROJXC")
                chk.ok(sblob is not None, "B14c PROJXC runs", note)
                if sblob:
                    st, sm = join_topo(lino_records(sblob), porc, pcases)
                    sw, smoved = mp_worst(sm)
                    chk.ok(n_tuple_mismatches(st) > 0,
                           "B14d PROJXC - project3d adding the vertical screen "
                           "centre to x - makes P1b fail on a real build",
                           "%d of %d field groups differ"
                           % (n_tuple_mismatches(st), len(st)))
                    chk.ok(sw > MP_BOUND_DECLARED,
                           "B14e ... and blows the declared mp[] envelope",
                           "max|delta| %d over %d cases" % (sw, smoved))

    # -------------------------------------- 6. what is NOT graded, as a number
    print("\n-- 6. the ungraded remainder, counted ---------------------------")
    from collections import Counter
    why = Counter(s[2] for s in skipped)
    for reason, n in sorted(why.items()):
        chk.note("NOT GRADED  %-42s %d frozen cases" % (reason, n))
    chk.ok(len(keep) + len(skipped) == len(proj_rows),
           "N1 every frozen projection row is either graded or counted as "
           "ungraded, with a reason",
           "%d graded + %d ungraded = %d rows"
           % (len(keep), len(skipped), len(proj_rows)))

    # N2 pins the SHAPE of the lino dump.  The oracle has records this port
    # has no counterpart for - K29 BASIS and K2A ROWUV, the polymap texture
    # gradient basis and the derived row u/v - and the only honest way to say
    # "not graded" is to show there is nothing to join.  If somebody adds an
    # emitter, a new (kind, tag) appears, this check fails, and the ungraded
    # list in the header has to be revisited instead of quietly going stale.
    SHAPES = ((20, 1), (21, 2), (22, 3), (23, 4), (24, 5), (24, 7), (25, 6))
    got_shapes = tuple(sorted(set((r[0], r[1]) for r in lino + plino)))
    n_basis = sum(len(v) for (k, _n), v in orc.items() if k in ("K29", "K2A"))
    n_basis += sum(len(v) for (k, _n), v in porc.items() if k in ("K29", "K2A"))
    chk.ok(got_shapes == SHAPES,
           "N2 the lino dump emits exactly the %d record shapes this file "
           "grades; the oracle's %d K29 BASIS / K2A ROWUV records have no "
           "counterpart and are NOT GRADED" % (len(SHAPES), n_basis),
           "shapes %s" % (got_shapes,))
    chk.ok(n_basis > 0,
           "N2b ... and the thing that is not graded actually exists on the "
           "other side, so N2 is a gap and not an empty set",
           "%d oracle basis/rowuv records" % n_basis)

    src = open(os.path.join(SAND, "pgfp.txt"), "r", encoding="utf-8",
               errors="replace").read()
    gam_uses = re.findall(r"^.*FSGAM.*$", src, re.M)
    gam_decl = [l for l in gam_uses if re.search(r"\bFSGAM\s*=", l)]
    gam_init = [l for l in gam_uses if "[PGFi] = FSGAM" in l]
    gam_read = [l for l in gam_uses if l not in gam_decl and l not in gam_init]
    chk.ok(not gam_read,
           "N3 gamma != 0 is NOT asserted, contrary to pgfp.txt:294 ('the "
           "port asserts gamma == 0 ... set it non-zero and the flag fires'): "
           "FSGAM is declared, initialised and never read, so there is no "
           "flag and nothing fires",
           "%d lines mention FSGAM: %d declaration, %d init, %d read %s"
           % (len(gam_uses), len(gam_decl), len(gam_init), len(gam_read),
              [l.strip() for l in gam_read[:2]]))

    chk.note("graded projection cases: %d of %d frozen PROJ/GETC rows"
             % (len(keep), sum(1 for k, n, d in proj_rows if k in ("PROJ", "GETC"))))
    chk.note("graded rasteriser pages: %d; bbox cases: %d; span cases: %d"
             % (len(pairs), len(bbrows), len(limrows)))
    chk.note("mp[] components compared: %d, declared bound %d, measured %d"
             % (ncomp, MP_BOUND_DECLARED, worst))

    return chk.done()


if __name__ == "__main__":
    lh.main_guard(main)
