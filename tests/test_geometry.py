"""GUARDS: Wave 6 - the float-to-int CAST BOUNDARY, the planetary GEOMETRY
values, and the DL capture set's class-0 blind spot.

READ THE NEXT THREE PARAGRAPHS BEFORE QUOTING ANY NUMBER THIS TEST PRINTS.
They say what each section is evidence FOR, and - more importantly - what it
is not. Two of the three things below are settled against a 1996 artifact.
The third is NOT, and section 4 measures exactly how far from settled it is
instead of dressing it up.

  SECTION 1 IS AN EQUALITY AGAINST THE SHIPPED 1996 MACHINE CODE. It decodes
  Borland's __ftol out of NOCTIS.EXE's bytes on every run - the MZ header
  gives the image base, so not one offset is taken on trust - and reads the
  answer to the cast boundary off the instruction stream: the rounding
  control is forced to 11 (chop) by an OR, the store is `fistp QWORD`, the
  routine reads nothing from its parameter area, and at none of the 274 call
  sites in the image is the value spilled before the call. So the operand is
  the LIVE 80-bit st(0) and the rounding is CHOP. That is `--cast chop
  --castsrc ext`, and section 2 requires both reference engines to default to
  it. This is what closes FLOATPOLICY.md 3.3 for the eleven geometry sites.

  SECTIONS 3 AND 4 ARE NOT AN ORACLE. Section 3 compares two independent
  implementations of the same reading of the 1996 source - a C transcription
  on a real x87 and an exact-rational Python with no hardware float in it -
  and requires them to agree bit for bit. That is evidence about
  TRANSCRIPTION and nothing else. NO 1996 artifact in this project's
  possession contains a planetary radius, orbital radius, tilt, eccentricity
  or ring value; section 5 re-derives that from the eighteen shipped binaries
  every run rather than citing it. Section 4 then measures the RESOLUTION of
  section 3 by perturbing it: it catches a 1-ULP change of a stored binary64
  on 100% of values, and is essentially BLIND to a perturbation of the live
  80-bit intermediate 2048 times smaller. Section 3 is therefore a statement
  about stored binary64s and nothing finer, and it is a BOUND below that.

  SECTION 5's 5e-5 IS A BOUND, NEVER AN EQUALITY. The only planetary number
  any 1996 binary ever prints is `nearstar_p_ray` at "%1.4f", on NOCTIS.EXE's
  graphical HUD (NOCTIS.CPP:3083). Even a perfect capture of it could only
  support |ours - theirs| < 5e-5. It would also settle nothing about the cast
  boundary, because phase F recomputes p_ray for every body from an
  integer-argument draw - measured here as 0 bodies moving, not argued.

WHAT ELSE IS PROTECTED

  SECTION 6 pins the float-site registry at eleven sites / 17 draws in both
  the C reference and the delivered port, so that geometry arriving in the
  port arrives as a deliberate change that fails a test first.

  SECTION 7 closes Wave 4's recorded DL blind spot. The `bclip` sabotage -
  phase B skipped when nop <= 4 - scored a perfect 4365/4365 against the
  122-capture set because that set contains no class-0 star with nop <= 4.
  Against the extended 210-capture set the same sabotage loses constraints.
  Both ports are rebuilt with the real compiler and re-run here.

  SECTION 8 records what is STILL OPEN, and fails if the tree quietly stops
  matching the record: nsrun still does not validate its NSIN payload length
  against its own header. That is probed BEHAVIOURALLY - the port is fed a
  file whose header claims eight records while the payload holds five, and
  it emits eight, generating the last three from zeroed coordinates. The
  check is an XFAIL: if someone fixes the defect, this test fails and tells
  you to update docs-notes/OPENITEMS.md.

NOTHING IS GRADED AGAINST A STORED EXPECTATION. The corpus is re-swept from
the galaxy hash and STARMAP.BIN every run, gcc rebuilds the C reference, the
Python reference recomputes from rationals, the L.in.oleum compiler rebuilds
the port, and no .geob checked in anywhere is opened. work/ and
noctis-harness/ are never written to: every build happens in a sandbox under
tests/gen holding byte-identical copies. Two exceptions, said plainly: the
shipped 1996 binaries and the DL.EXE captures are READ off disk, because they
are artifacts of the 1996 program - like STARMAP.BIN - and re-taking the
captures opens a DOSBox-X window on the user's desktop.

THE BREAKS. Every check that can be broken is broken here and observed to
fail: four byte-level mutations of an in-memory copy of NOCTIS.EXE, one flag
control on each reference engine, two source-level ULP perturbations of the C
reference built with the real compiler, one mutated registry, one synthetic
blob for the format scanner, and one single-edit sabotage of the delivered
L.in.oleum port. A grader that cannot fail is not a grader.

RUN: python tests/test_geometry.py             (~1 min, needs gcc)
     python tests/test_geometry.py --quick     (skips section 7's two lino
                                                builds - not a pass)
     python tests/test_geometry.py --limit 500 (a bigger corpus)
"""

import os
import re
import shutil
import struct
import subprocess
import sys

import linoharness as L

NOCTIS = r"C:\programmieren\noctis\niv-plus"
MODULES = os.path.join(NOCTIS, "modules")
SOURCE = os.path.join(NOCTIS, "source")
NOCTIS_EXE = os.path.join(MODULES, "NOCTIS.EXE")

FIELDS = ("orb_orient", "orb_seed", "tilt", "orb_tilt",
          "orb_ecc", "ray", "orb_ray", "ring")
GEOB_MAGIC = 0x47454F42

# Borland's __ftol, at image offset 1265h in NOCTIS.EXE. The image base is
# NOT hard-coded: it is read out of the MZ header below.
FTOL_IMAGE_OFF = 0x1265
FTOL_FARCALL = bytes((0x9A, 0x65, 0x12, 0x00, 0x00))     # lcall 0000:1265

# The first of the eleven float-argument sites, NOCTIS-0.CPP:4089
#   fld dword [108C]  (300.0f) / fmul dword [027F]  (nearstar_ray) / lcall
# Used only as an ANCHOR: the other ten are then taken as the next ten
# __ftol calls in the image, so the registry is derived from the binary
# rather than from a list of offsets someone wrote down.
SITE4089 = bytes.fromhex("9b d9 06 8c 10 9b d8 0e 7f 02") + FTOL_FARCALL

# The :4092 planetary eccentricity store in geo_ref.c. Section 4 perturbs
# exactly this line; if a later wave rewrites it, the patch fails to apply
# and the section fails rather than quietly measuring nothing.
ECC_ANCHOR = "            p_orb_ecc[n] = (double)((ext)1 - STEP (v / (ext)2000));\n"
ECC_PATCH = ("#if defined(BREAK_ULP64)\n"
             "            p_orb_ecc[n] = nextafter ((double)((ext)1 - "
             "STEP (v / (ext)2000)), 2.0);\n"
             "#elif defined(BREAK_ULPEXT)\n"
             "            p_orb_ecc[n] = (double) nextafterl ((ext)1 - "
             "STEP (v / (ext)2000), 2.0L);\n"
             "#else\n" + ECC_ANCHOR + "#endif\n")


# ======================================================================
# GEOB plumbing
# ======================================================================

def read_geob(path):
    with open(path, "rb") as fh:
        b = fh.read()
    magic, _ver, nrec, nf, cast, csrc, prec, _ = struct.unpack_from("<8I", b, 0)
    if magic != GEOB_MAGIC:
        raise SystemExit("not a GEOB file: %s" % path)
    o, out = 32, []
    for _ in range(nrec):
        cls, nop, nob, draws = struct.unpack_from("<4I", b, o)
        o += 16
        vals = struct.unpack_from("<%dQ" % (nob * nf), b, o)
        o += nob * nf * 8
        out.append((cls, nop, nob, draws, vals))
    return (cast, csrc, prec), out


def cmp_geob(a, b):
    """(header mismatches, values compared, values differing, per-field, ex)"""
    hbad = tot = bad = 0
    perf = [0] * len(FIELDS)
    ex = []
    for k, (x, y) in enumerate(zip(a, b)):
        if x[:4] != y[:4]:
            hbad += 1
            continue
        for i, (u, v) in enumerate(zip(x[4], y[4])):
            tot += 1
            if u != v:
                bad += 1
                perf[i % len(FIELDS)] += 1
                if len(ex) < 3:
                    ex.append("rec %d body %d %s %016x != %016x"
                              % (k, i // len(FIELDS), FIELDS[i % len(FIELDS)],
                                 u, v))
    return hbad, tot, bad, perf, ex


def as_double(u64):
    return struct.unpack("<d", struct.pack("<Q", u64))[0]


# ======================================================================
# a 16-bit disassembler, just wide enough for __ftol
# ======================================================================

def _s8(v):
    return v - 256 if v >= 128 else v


def dis16(b, p):
    """Decode ONE instruction at p. (length, text) or None if unknown.

    Deliberately narrow: it knows the fifteen forms Borland's __ftol is
    built from plus the three forms the section-1 mutants introduce. An
    unknown byte is a decode failure, which is what makes "the body is
    exactly these instructions and nothing else" a real statement.
    """
    o = b[p]
    two = b[p:p + 2]
    if o == 0x9B:
        return 1, "fwait"
    if o == 0x90:
        return 1, "nop"
    if o == 0x55:
        return 1, "push bp"
    if o == 0x5D:
        return 1, "pop bp"
    if o == 0xCB:
        return 1, "retf"
    if two == b"\x8b\xec":
        return 2, "mov bp,sp"
    if two == b"\x8b\xe5":
        return 2, "mov sp,bp"
    if two == b"\x83\xec":
        return 3, "sub sp,%d" % b[p + 2]
    d = _s8(b[p + 2]) if p + 2 < len(b) else 0
    simple = {b"\xd9\x7e": "fnstcw word [bp%+d]",
              b"\xd9\x6e": "fldcw word [bp%+d]",
              b"\xdf\x7e": "fistp qword [bp%+d]",
              b"\xdb\x5e": "fistp dword [bp%+d]",
              b"\xdf\x5e": "fistp word [bp%+d]",
              b"\x8a\x46": "mov al,[bp%+d]",
              b"\x88\x46": "mov [bp%+d],al",
              b"\x8b\x46": "mov ax,[bp%+d]",
              b"\x8b\x56": "mov dx,[bp%+d]"}
    if two in simple:
        return 3, simple[two] % d
    if two == b"\x80\x4e":
        return 4, "or byte [bp%+d],0x%02x" % (d, b[p + 3])
    if two == b"\x80\x66":
        return 4, "and byte [bp%+d],0x%02x" % (d, b[p + 3])
    return None


def decode_ftol(blob, off, cap=64):
    """Walk from off to the first retf. (steps, error)."""
    steps, p = [], off
    while p < off + cap:
        got = dis16(blob, p)
        if got is None:
            return steps, ("undecodable byte at +%d: %s"
                           % (p - off, blob[p:p + 4].hex(" ")))
        n, text = got
        steps.append((p - off, blob[p:p + n].hex(" "), text))
        p += n
        if text == "retf":
            return steps, ""
    return steps, "no retf within %d bytes" % cap


def ftol_facts(steps):
    """The semantic reading of the decoded body."""
    texts = [t for _, _, t in steps]
    bp = [int(m.group(1)) for t in texts
          for m in [re.search(r"\[bp([+-]\d+)\]", t)] if m]
    cw = [t for t in texts if t.startswith(("or byte", "and byte"))]
    imm = None
    if cw:
        imm = int(cw[0].split(",")[1], 16)
    return {
        "n": len(steps),
        "ends_retf": texts[-1] == "retf" if texts else False,
        "reads_param": [v for v in bp if v >= 0],
        "modifiers": cw,
        "imm": imm,
        "rc_forced_chop": (len(cw) == 1 and cw[0].startswith("or byte")
                           and imm is not None and (imm & 0x0C) == 0x0C),
        "pc_untouched": imm is not None and (imm & 0x03) == 0,
        "uses_and": any(t.startswith("and byte") for t in texts),
        "fistp": [t for t in texts if t.startswith("fistp")],
        "fnstcw": len([t for t in texts if t.startswith("fnstcw")]),
        "fldcw": len([t for t in texts if t.startswith("fldcw")]),
    }


def x87_before(blob, call_off):
    """Classify the instruction that ends exactly where a far call begins.

    Borland emits a 9Bh fwait in front of every x87 instruction in this
    build, which gives an unambiguous anchor for the one instruction before
    the call. Returns None if the call is not fed directly by an x87
    instruction, else (mnemonic-ish tuple, is_store).
    """
    if call_off < 6 or blob[call_off - 5] != 0x9B:
        return None
    op = blob[call_off - 4]
    if not 0xD8 <= op <= 0xDF:
        return None
    modrm = blob[call_off - 3]
    mod, reg, rm = modrm >> 6, (modrm >> 3) & 7, modrm & 7
    if mod == 3:
        ln = 2
    elif mod == 0:
        ln = 4 if rm == 6 else 2
    elif mod == 1:
        ln = 3
    else:
        ln = 4
    if call_off - 4 + ln != call_off:
        return None                       # the 9Bh was a coincidence
    store = ((op in (0xD9, 0xDD) and reg in (2, 3))
             or (op in (0xDB, 0xDF) and reg in (2, 3, 7)))
    return (op, reg, mod, rm), store


def registry_sites(blob):
    """The eleven float-argument call sites, located from the binary.

    The :4089 shape is unique in the image; the other ten are the next ten
    __ftol calls after it. No offset is stored anywhere in this file.
    """
    calls = [m.start() for m in re.finditer(re.escape(FTOL_FARCALL), blob)]
    anchors = [m.start() for m in re.finditer(re.escape(SITE4089), blob)]
    if len(anchors) != 1:
        return calls, anchors, []
    first = anchors[0] + len(SITE4089) - len(FTOL_FARCALL)
    i = calls.index(first)
    return calls, anchors, calls[i:i + 11]


# ======================================================================
# build / run helpers
# ======================================================================

def gcc_build(src, exe, defines=()):
    if shutil.which("gcc") is None:
        return False, "gcc is not on PATH"
    cmd = (["gcc", "-O2", "-fwrapv", "-Wall"] + ["-D" + d for d in defines]
           + ["-o", exe, src, "-lm"])
    p = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode == 0, ((p.stdout or "") + (p.stderr or "")).strip()


def run_tool(cmd, cwd=None):
    p = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=cwd)
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


# ======================================================================
# 1. THE SHIPPED BINARY - the cast boundary, decoded this run
# ======================================================================

def section_binary(c):
    if not c.ok(os.path.exists(NOCTIS_EXE),
                "the shipped 1996 NOCTIS.EXE is where the reference clone "
                "puts it", NOCTIS_EXE):
        return
    with open(NOCTIS_EXE, "rb") as fh:
        blob = fh.read()

    # -- the image base, derived, so no offset below is taken on trust ----
    hdrpar = struct.unpack_from("<H", blob, 8)[0]
    base = hdrpar * 16
    c.ok(blob[:2] == b"MZ", "NOCTIS.EXE is an MZ image", "%d bytes" % len(blob))
    c.note("MZ header: %d paragraphs -> the load image starts at file %d, so "
           "image 0x%04X is file %d" % (hdrpar, base, FTOL_IMAGE_OFF,
                                        base + FTOL_IMAGE_OFF))

    steps, err = decode_ftol(blob, base + FTOL_IMAGE_OFF)
    for off, hx, text in steps:
        c.note("  __ftol+%-3d  %-14s %s" % (off, hx, text))
    c.ok(not err, "__ftol decodes completely, every byte accounted for",
         err or "%d instructions, ends in retf" % len(steps))
    f = ftol_facts(steps)

    c.eq(f["reads_param"], [],
         "__ftol reads NOTHING from its parameter area - every frame access "
         "is a negative displacement - so its operand can only be st(0), the "
         "LIVE top of the x87 stack")
    c.ok(f["rc_forced_chop"],
         "it forces the rounding control to 11 = CHOP",
         "modifier(s): %s" % (f["modifiers"] or "none"))
    c.ok(f["pc_untouched"],
         "...and leaves the precision control alone, so the 64-bit chain the "
         "caller built is chopped at 64-bit precision",
         "imm 0x%02x, PC mask 0x03" % (f["imm"] or 0))
    c.ok(not f["uses_and"],
         "it ORs 0Ch in and does not clear RC first - a port that 'tidies' "
         "this into AND/OR has changed the instruction")
    c.eq(f["fistp"], ["fistp qword [bp-10]"],
         "the store is fistp QWORD (only the low 32 bits are returned); a "
         "32-bit fistp would give the integer indefinite instead")
    c.eq((f["fnstcw"], f["fldcw"]), (1, 2),
         "the control word is read once and restored twice - the caller's "
         "word is put back exactly")

    # -- the call sites -------------------------------------------------
    calls, anchors, reg = registry_sites(blob)
    c.eq(len(anchors), 1,
         "the :4089 site shape (fld 300.0f / fmul nearstar_ray / lcall "
         "__ftol) occurs exactly once in the image, so it anchors the "
         "registry without a stored offset")
    c.eq(len(reg), 11,
         "the eleven float-argument sites are the anchor plus the next ten "
         "__ftol calls")
    if reg:
        c.note("registry sites at file offsets: %s (span %d bytes)"
               % (" ".join(str(s) for s in reg), reg[-1] - reg[0]))
    fed = [(s, x87_before(blob, s)) for s in reg]
    undec = [s for s, r in fed if r is None]
    stores = [s for s, r in fed if r is not None and r[1]]
    c.eq(undec, [],
         "every one of the eleven is fed directly by an x87 instruction")
    c.eq(stores, [],
         "and NOT ONE of them stores the value first - there is no fstp "
         "between the last arithmetic and the call, so what __ftol chops is "
         "the live 80-bit intermediate")

    allfed = [(s, x87_before(blob, s)) for s in calls]
    nfed = [r for _s, r in allfed if r is not None]
    nstore = [r for r in nfed if r[1]]
    c.eq(len(nstore), 0,
         "the same holds at EVERY __ftol call site in the whole image: of "
         "%d calls, %d are fed directly by an x87 instruction and %d of "
         "those spill first" % (len(calls), len(nfed), len(nstore)))

    c.note("SETTLED, from the 1996 machine code and nothing else: the "
           "float-to-int cast boundary is CHOP applied to the LIVE 80-bit "
           "st(0), i.e. --cast chop --castsrc ext.")

    # -- and now break it -----------------------------------------------
    c.note("breaking section 1 on an in-memory copy - the file on disk is "
           "never touched:")

    def mutate(off, old, new):
        b = bytearray(blob)
        assert bytes(b[off:off + len(old)]) == old, "mutation anchor moved"
        b[off:off + len(new)] = new
        return bytes(b)

    fo = base + FTOL_IMAGE_OFF
    orpos = blob.index(bytes((0x80, 0x4E, 0xFF, 0x0C)), fo, fo + 64)
    m = mutate(orpos, bytes((0x80, 0x4E, 0xFF, 0x0C)),
               bytes((0x80, 0x4E, 0xFF, 0x00)))
    s2, _ = decode_ftol(m, fo)
    c.ok(not ftol_facts(s2)["rc_forced_chop"],
         "BREAK rc: with `or byte [bp-1],0` the chop check FAILS",
         "as it must")

    m = mutate(orpos, bytes((0x80, 0x4E, 0xFF, 0x0C)),
               bytes((0x80, 0x66, 0xFF, 0x0C)))
    s2, _ = decode_ftol(m, fo)
    c.ok(ftol_facts(s2)["uses_and"],
         "BREAK and: an AND in place of the OR is SEEN by the check")

    fipos = blob.index(bytes((0xDF, 0x7E, 0xF6)), fo, fo + 64)
    m = mutate(fipos, bytes((0xDF, 0x7E, 0xF6)), bytes((0xDB, 0x5E, 0xF6)))
    s2, _ = decode_ftol(m, fo)
    c.ok(ftol_facts(s2)["fistp"] != ["fistp qword [bp-10]"],
         "BREAK width: a 32-bit fistp is caught",
         "decoded as %s" % ftol_facts(s2)["fistp"])

    alpos = blob.index(bytes((0x8A, 0x46, 0xFF)), fo, fo + 64)
    m = mutate(alpos, bytes((0x8A, 0x46, 0xFF)), bytes((0x8A, 0x46, 0x06)))
    s2, _ = decode_ftol(m, fo)
    c.ok(ftol_facts(s2)["reads_param"] == [6],
         "BREAK param: a read from [bp+6] is caught, so the 'takes no "
         "parameter' check is a measurement and not a formality")

    # DD /0 is `fld qword`; DD /3 at the same modrm is `fstp qword`, which is
    # exactly the spill the LIVE reading says is not there. One byte.
    ddsite = [s for s, r in fed if r is not None and r[0][0] == 0xDD]
    if ddsite:
        site = ddsite[0]
        old = blob[site - 4:site - 2]
        m = mutate(site - 4, old, bytes((old[0], old[1] | 0x18)))
        r = x87_before(m, site)
        c.ok(r is not None and r[1],
             "BREAK spill: turning the `fld qword` before a call into an "
             "`fstp qword` (one byte) is caught by the store check",
             "site %d" % site)


# ======================================================================
# 2. THE DEFAULTS ARE THE BINARY'S ANSWER
# ======================================================================

def section_defaults(c, sb, corpus, limit, harness):
    """Both engines must DEFAULT to what section 1 read off the binary."""
    exe = sb("georef.exe")
    out = sb("defc.geob")
    rc, msg = run_tool([exe, corpus, out])
    if not c.ok(rc == 0, "the C reference runs with NO cast flags", msg):
        return
    hdr, _ = read_geob(out)
    c.eq(hdr, (0, 0, 0),
         "geo_ref DEFAULTS to cast=chop castsrc=ext prec=ext - the reading "
         "section 1 took off NOCTIS.EXE. This is the check the wave's own "
         "geo_grade.py does not make")

    outp = sb("defp.geob")
    rc, msg = run_tool([sys.executable, os.path.join(harness, "geo_spec.py"),
                        corpus, outp, "--limit", str(limit)], cwd=harness)
    if c.ok(rc == 0, "the Python reference runs with NO cast flags", msg):
        hp, _ = read_geob(outp)
        c.eq(hp, (0, 0, 0),
             "geo_spec DEFAULTS to the same thing - both engines agree with "
             "the binary, not merely with each other")

    # the header is a measurement of the flag, not a constant
    outn = sb("flagc.geob")
    rc, _ = run_tool([exe, corpus, outn, "--cast", "near", "--castsrc", "f64"])
    hn, _ = read_geob(outn)
    c.eq(hn, (1, 1, 0),
         "CONTROL: with the flags flipped the header reports (1,1,0), so the "
         "(0,0,0) above is a reading and not a hard-coded zero")


# ======================================================================
# 3. THE TWO ENGINES, BIT FOR BIT  (transcription evidence, NOT an oracle)
# ======================================================================

def section_engines(c, sb, corpus, limit, harness, variants):
    cbase = variants[("chop", "ext", "ext")]
    outp = sb("specp.geob")
    rc, msg = run_tool([sys.executable, os.path.join(harness, "geo_spec.py"),
                        corpus, outp, "--limit", str(limit)], cwd=harness)
    if not c.ok(rc == 0, "geo_spec.py recomputes the corpus from rationals",
                msg):
        return None, None
    py = read_geob(outp)[1]
    cc = cbase[:len(py)]
    hbad, tot, bad, _perf, ex = cmp_geob(cc, py)
    bodies = sum(r[2] for r in py)
    planets = sum(r[1] for r in py)
    c.note("%d systems, %d planets, %d bodies, %d graded values (%d fields "
           "each)" % (len(py), planets, bodies, tot, len(FIELDS)))
    for e in ex:
        c.note("  " + e)
    c.eq(hbad, 0, "class / nop / nob / draw count agree on every system")
    c.ok(tot > 0 and bad == 0,
         "TRANSCRIPTION: every geometry value agrees BIT FOR BIT between an "
         "80-bit hardware x87 chain and exact rational arithmetic. This is "
         "NOT agreement with the 1996 machine - see section 5",
         "%d / %d differ" % (bad, tot))

    # The hole a later wave could fall into: agreement is not evidence about
    # WHICH hypothesis is right, because the two engines agree under all four.
    outn = sb("specn.geob")
    rc, _ = run_tool([sys.executable, os.path.join(harness, "geo_spec.py"),
                      corpus, outn, "--limit", str(limit),
                      "--cast", "near", "--castsrc", "f64"], cwd=harness)
    if rc == 0:
        pn = read_geob(outn)[1]
        cn = variants[("near", "f64", "ext")][:len(pn)]
        _h, t2, b2, _p, _e = cmp_geob(cn, pn)
        c.ok(t2 > 0 and b2 == 0,
             "the two engines ALSO agree bit for bit under the hypothesis "
             "furthest from the binary's answer (near/f64), which is exactly "
             "why section 2's default check is load-bearing and this "
             "section is not", "%d / %d differ" % (b2, t2))
    return py, planets


# ======================================================================
# 4. THE RESOLUTION OF SECTION 3 - measured by perturbation, and it is a BOUND
# ======================================================================

def section_resolution(c, sb, corpus, refsrc, py, planets):
    with open(refsrc, "r", encoding="utf-8") as fh:
        src = fh.read()
    n = src.count(ECC_ANCHOR)
    if not c.eq(n, 1,
                "the :4092 eccentricity store is still spelled the way this "
                "section perturbs it - if it is not, this section measures "
                "nothing and says so"):
        return
    pert = sb("pertgeo.c")
    with open(pert, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(src.replace(ECC_ANCHOR, ECC_PATCH))

    c.note("orb_ecc is a TERMINAL field: nothing downstream reads it, so a "
           "perturbation there cannot cascade and the counts below are the "
           "grading's raw resolution.")
    got = {}
    for tag, blurb in (("ULP64", "1 ULP of the STORED binary64"),
                       ("ULPEXT", "1 ULP of the LIVE 80-bit intermediate "
                                  "(2048x smaller)")):
        exe = sb("pert%s.exe" % tag.lower())
        ok, msg = gcc_build(pert, exe, ["BREAK_" + tag])
        if not c.ok(ok, "BREAK_%s builds with the real compiler" % tag, msg):
            continue
        out = sb("pert%s.geob" % tag.lower())
        rc, msg = run_tool([exe, corpus, out])
        if not c.ok(rc == 0, "BREAK_%s runs over the real corpus" % tag, msg):
            continue
        recs = read_geob(out)[1][:len(py)]
        _h, tot, bad, perf, _e = cmp_geob(recs, py)
        got[tag] = (tot, bad, perf)
        c.note("  %-7s %-52s %5d of %5d values move (%.3f%%)"
               % (tag, blurb, bad, tot, 100.0 * bad / max(tot, 1)))

    if "ULP64" in got:
        tot, bad, perf = got["ULP64"]
        c.eq(perf[FIELDS.index("orb_ecc")], planets,
             "a 1-ULP change of the stored double is caught on EVERY one of "
             "the %d planetary orb_ecc values - the grading is exact to one "
             "binary64 ULP" % planets)
        c.eq([FIELDS[i] for i in range(len(FIELDS))
              if perf[i] and FIELDS[i] != "orb_ecc"], [],
             "...and it moves nothing else, confirming orb_ecc really is "
             "terminal and the count above is not inflated by a cascade")
    if "ULPEXT" in got:
        tot, bad, _perf = got["ULPEXT"]
        c.ok(bad * 100 <= max(planets, 1),
             "BOUND, NOT AN EQUALITY: a perturbation of the live 80-bit "
             "intermediate 2048x smaller is essentially INVISIBLE to this "
             "grading (%d of %d planetary values, %.3f%%). Section 3 is "
             "evidence about STORED binary64 values and nothing finer"
             % (bad, planets, 100.0 * bad / max(planets, 1)),
             "%d caught" % bad)
        c.ok("ULP64" in got and got["ULP64"][1] > bad,
             "the two perturbations are ordered as the arithmetic requires: "
             "the coarser one is caught far more often than the finer one")


# ======================================================================
# 5. THE ORACLE THAT DOES NOT EXIST, AND THE ONE BOUND THAT COULD
# ======================================================================

FMT = re.compile(rb"%[0-9.*+ #-]*(?:l|h|L)?[diouxXfFeEgGcsp]")
FLOATCONV = set(b"fFeEgG")


def float_formats(blob):
    return sorted({s.decode() for s in FMT.findall(blob) if s[-1] in FLOATCONV})


def section_oracle(c, variants):
    if not c.ok(os.path.isdir(MODULES), "the eighteen shipped GOES modules "
                "are present", MODULES):
        return
    rows = []
    for fn in sorted(os.listdir(MODULES)):
        if not fn.lower().endswith((".exe", ".com")):
            continue
        with open(os.path.join(MODULES, fn), "rb") as fh:
            b = fh.read()
        rows.append((fn, len(b), float_formats(b),
                     sorted({s.decode() for s in FMT.findall(b)})))
    c.ok(len(rows) >= 18, "all shipped modules scanned",
         "%d binaries" % len(rows))
    dl = [r for r in rows if r[0].upper() == "DL.EXE"]
    c.ok(len(dl) == 1, "DL.EXE - the Wave 4 oracle - is one of them")
    if dl:
        c.eq(dl[0][2], [],
             "DL.EXE contains NO floating-point printf conversion at all, so "
             "it cannot print a geometry value however it is driven; its "
             "whole format set is %s" % " ".join(dl[0][3]))
    withfloat = sorted(r[0] for r in rows if r[2])
    c.ok(set(withfloat) <= {"NOCTIS.EXE", "PAR.EXE", "SL.EXE"},
         "only NOCTIS/PAR/SL print any float at all",
         "found: %s" % ", ".join(withfloat))

    # the scanner has to be able to see one
    c.ok(float_formats(b"junk %d more junk %1.4f tail") == ["%1.4f"],
         "CONTROL: the format scanner does find a float conversion when one "
         "is there")

    hits = []
    for fn in ("PAR.CPP", "SL.CPP"):
        p = os.path.join(SOURCE, fn)
        if not os.path.exists(p):
            continue
        with open(p, encoding="latin-1") as fh:
            for i, line in enumerate(fh, 1):
                if re.search(r"%[0-9.]*l?[fgeFGE]", line):
                    hits.append("%s:%d %s" % (fn, i, line.strip()[:80]))
    geom = [h for h in hits if re.search(r"orb_|_tilt|_ecc|_ring|p_ray", h)]
    for h in hits:
        c.note("  " + h)
    c.eq(geom, [], "no GOES module prints any planetary geometry")

    noc = os.path.join(SOURCE, "NOCTIS.CPP")
    if os.path.exists(noc):
        with open(noc, encoding="latin-1") as fh:
            lines = fh.read().splitlines()
        ray = [(i + 1, l.strip()) for i, l in enumerate(lines)
               if "nearstar_p_ray" in l and "%1.4f" in l]
        for i, l in ray:
            c.note("  the ONLY planetary number any 1996 binary prints: "
                   "NOCTIS.CPP:%d  %s" % (i, l[:80]))
        c.eq(len(ray), 1,
             "exactly one such site, and it is a HUD sprintf inside the "
             "interactive game")

    # what that one printout could ever settle
    base = variants[("chop", "ext", "ext")]
    ri = FIELDS.index("ray")

    def moved(a, b, tol):
        nb = mv = vis = 0
        for x, y in zip(a, b):
            for k in range(x[2]):
                u = as_double(x[4][k * 8 + ri])
                v = as_double(y[4][k * 8 + ri])
                nb += 1
                if u != v:
                    mv += 1
                    if abs(u - v) > tol:
                        vis += 1
        return nb, mv, vis

    nb, mv, _v = moved(base, variants[("near", "ext", "ext")], 5e-5)
    c.eq(mv, 0,
         "the one field the original prints does not move under the cast "
         "boundary AT ALL (%d bodies) - phase F overwrites p_ray for every "
         "body from an integer-argument draw, so a HUD capture is blind to "
         "the open question BY CONSTRUCTION" % nb)
    nb, mv, _v = moved(base, variants[("chop", "f64", "ext")], 5e-5)
    c.eq(mv, 0, "...and it does not move under the castsrc axis either")
    nb, mv, vis = moved(base, variants[("chop", "ext", "f64")], 5e-5)
    c.eq(vis, 0,
         "a %%1.4f readout could not resolve the precision class either: "
         "%d of %d bodies move at 53 bits, none by as much as 5e-5" % (mv, nb))
    c.note("SO: the strongest statement a capture of NOCTIS.EXE's HUD could "
           "ever support is |ours - theirs| < 5e-5 - a BOUND, never an "
           "equality - and on this evidence it would settle nothing. "
           "Planetary geometry remains UNGRADED against the 1996 machine.")


# ======================================================================
# 6. THE COST OF THE CAST BOUNDARY, AND THE SITE REGISTRY
# ======================================================================

def section_cost(c, variants, refsrc):
    base = variants[("chop", "ext", "ext")]
    rows = []
    for key in sorted(variants):
        _h, tot, bad, perf, _e = cmp_geob(base, variants[key])
        rows.append((key, tot, bad, perf))
        c.note("  cast=%-5s castsrc=%-4s prec=%-4s %8d values %8d differ "
               "%7.3f%%" % (key[0], key[1], key[2], tot, bad,
                            100.0 * bad / max(tot, 1)))
    _h, tot, bnear, pnear, _e = cmp_geob(base, variants[("near", "ext", "ext")])
    c.ok(bnear > 0,
         "getting the cast boundary wrong is EXPENSIVE, which is what makes "
         "section 1 worth having: %d of %d geometry values (%.3f%%) move "
         "between chop and round-to-nearest"
         % (bnear, tot, 100.0 * bnear / max(tot, 1)))
    reached = {FIELDS[i] for i in range(len(FIELDS)) if pnear[i]}
    c.eq(reached, {"orb_seed", "tilt", "orb_tilt", "orb_ecc"},
         "and it reaches exactly four of the eight fields - the other four "
         "are drawn or recomputed from INTEGER arguments, measured here "
         "rather than assumed")
    _h, _t, bsrc, _p, _e = cmp_geob(base, variants[("chop", "f64", "ext")])
    c.note("the castsrc axis alone (live 80-bit vs its binary64 rounding) "
           "moves %d of %d values, %.4f%%"
           % (bsrc, tot, 100.0 * bsrc / max(tot, 1)))
    _h, _t, bp64, _p, _e = cmp_geob(base, variants[("chop", "ext", "f64")])
    c.ok(bp64 > 0,
         "the 80-bit schedule is load-bearing for geometry too: a plain "
         "double transcription moves %d of %d values" % (bp64, tot))

    # -- the registry, in both implementations --------------------------
    with open(refsrc, encoding="utf-8") as fh:
        rsrc = fh.read()
    sites = re.findall(r"^\s*\*\s+FSITE (\d+)\s+(random|zrandom)", rsrc, re.M)
    draws = sum(2 if k == "zrandom" else 1 for _, k in sites)
    c.eq((len(sites), draws), (11, 17),
         "the C reference still declares eleven float-argument sites / 17 "
         "draws")
    cut = re.sub(r"^\s*\*\s+FSITE 4093.*\n", "", rsrc, count=1, flags=re.M)
    c.eq(len(re.findall(r"^\s*\*\s+FSITE (\d+)\s+(random|zrandom)", cut,
                        re.M)), 10,
         "CONTROL: the registry counter sees a site disappear")

    topo = os.path.join(L.WORK, "nstopo.txt")
    if os.path.exists(topo):
        with open(topo, encoding="utf-8", errors="replace") as fh:
            prog = fh.read().split('"programme"', 1)[1]
        c.eq((len(re.findall(r"SITE \d+", prog)),
              prog.count("=> NsDrawOnly"), prog.count("=> NsZDrawOnly")),
             (11, 5, 6),
             "and the DELIVERED PORT still discards all eleven: 5 single "
             "draws + 6 zrandoms = 17. Geometry arriving in the port must "
             "fail here first")


# ======================================================================
# 7. THE DL BLIND SPOT - bclip, caught
# ======================================================================

def section_bclip(c):
    try:
        import nsdrive as D
        sys.path.insert(0, L.HARNESS)
        import ns_dl as DL
    except Exception as e:                                  # noqa: BLE001
        c.ok(False, "the Wave 4 driver and DL grader import", repr(e))
        return

    b4 = os.path.join(L.GEN, "recon_c", "batch4.manifest")
    b5 = os.path.join(L.GEN, "recon_c", "batch5.manifest")
    if not (os.path.exists(b4) and os.path.exists(b5)):
        c.note("SKIPPED: the DL.EXE capture manifests are not in the tree. "
               "This leg is reported as SKIPPED, not as a pass.")
        return

    def rows_for(mans):
        keep = DL.MANIFESTS
        DL.MANIFESTS = mans
        try:
            return DL.capture_rows()
        finally:
            DL.MANIFESTS = keep

    old, new = rows_for([b4]), rows_for([b4, b5])
    c.note("capture sets: Wave 4 = %d captures, extended = %d captures"
           % (len(old), len(new)))
    c.ok(len(new) > len(old),
         "the extended capture set is strictly larger than Wave 4's")

    res = {}
    for name in (None, "bclip"):
        mut = D.MUT_BY_NAME[name] if name else None
        drv = D.Driver("tgeobc", mut)
        nedits, same = drv.install()
        c.eq(nedits, 0 if mut is None else len(mut.edits),
             "the %s sandbox applies %s" % (name or "unmutated",
                                            "no mutation" if mut is None
                                            else "exactly its edits"))
        nsame = len(drv.unmodified(same))
        c.eq(nsame, len(same),
             "every unmutated source in the %s sandbox is byte-identical to "
             "work/ - what gets compiled IS the delivered port"
             % (name or "unmutated"))
        ok, msg = drv.build()
        if not c.ok(ok, "the %s port compiles" % (name or "unmutated"), msg):
            return
        for label, rows in (("w4", old), ("ext", new)):
            nsin = [(x, y, z, -1, -1, -1, 0, 0)
                    for (_cf, _nm, x, y, z, _cl) in rows]
            recs, _diag, msg = drv.run(nsin, timeout=300)
            if recs is None:
                c.ok(False, "the %s port runs on the %s set"
                     % (name or "unmutated", label), msg)
                return
            tot, good, fails = DL.grade(drv.out, rows, verbose=False)
            res[(name, label)] = (tot, good)
            c.note("  %-10s vs %-3s  %5d / %-5d  %6.2f%%%s"
                   % (name or "unmutated", label, good, tot,
                      100.0 * good / max(tot, 1),
                      "" if good == tot else "   <== CAUGHT"))
            for f in fails[:2]:
                c.note("      MISMATCH %s body %d %r: want owner/moonid "
                       "(%s,%s), port says %s"
                       % (f[0], f[1], f[2][:20], f[3], f[4], f[5]))

    g4, ge = res[(None, "w4")], res[(None, "ext")]
    m4, me = res[("bclip", "w4")], res[("bclip", "ext")]
    c.eq(g4[1], g4[0],
         "the unmutated port reproduces every constraint on Wave 4's set")
    c.eq(ge[1], ge[0],
         "...and every constraint on the extended set, so the extension did "
         "not simply add captures the port gets wrong")
    c.eq(m4[1], m4[0],
         "bclip is STILL invisible to the 122-capture set - the blind spot "
         "Wave 4 recorded is real and is reproduced here, not asserted")
    c.ok(me[1] < me[0],
         "and bclip IS CAUGHT by the extended set: %d of %d constraints "
         "lost. OPEN ITEM 3 was a gap in the capture set, not in the method"
         % (me[0] - me[1], me[0]))


# ======================================================================
# 8. WHAT IS STILL OPEN
# ======================================================================

def section_open(c, harness, quick):
    """Honest record. An XFAIL here fails when the tree stops matching it.

    The NSIN length gap is probed BEHAVIOURALLY, not by grepping for a
    comparison: a text search for "does this source validate X" is exactly
    the kind of check that passes for the wrong reason. The port is built
    and fed a file whose header claims more records than the payload holds.
    """
    nsrun = os.path.join(L.WORK, "nsrun.txt")
    if os.path.exists(nsrun):
        with open(nsrun, encoding="utf-8", errors="replace") as fh:
            txt = fh.read()
        c.ok("[nrfilebytes] = A" in txt,
             "nsrun still reads the NSIN file size into nrfilebytes - the "
             "raw material for a length check is there; it surfaces only in "
             "the failure path's diag block")

    if quick:
        c.note("the NSIN-length XFAIL needs a build and is SKIPPED by "
               "--quick. That is not a pass.")
    else:
        try:
            import nsdrive as D
            sys.path.insert(0, L.HARNESS)
            import ns_spec as N
        except Exception as e:                              # noqa: BLE001
            c.ok(False, "the Wave 4 driver imports", repr(e))
            return
        drv = D.Driver("tgeons")
        drv.install()
        ok, msg = drv.build()
        if not c.ok(ok, "the delivered port builds for the NSIN-length probe",
                    msg.splitlines()[0] if msg else ""):
            return
        rows = [(100000 * (i + 1), -200000, 300000, -1, -1, -1, 0, 0)
                for i in range(8)]

        def go():
            for stale in (drv.out, drv.diag):
                if os.path.exists(stale):
                    os.remove(stale)
            _rc, _m, blob = L.run(drv.exe, drv.out, timeout_sec=180)
            if blob is None:
                return None
            return N.read_nstopo(drv.out)[1]

        N.write_nsin(drv.nsin, rows)
        full = go()
        c.ok(full is not None and len(full) == 8,
             "CONTROL: on an intact 8-record NSIN the port emits 8 records",
             "%s" % (None if full is None else len(full)))
        with open(drv.nsin, "rb") as fh:
            blob = fh.read()
        with open(drv.nsin, "wb") as fh:
            fh.write(blob[:16 + 5 * 32])            # header says 8, holds 5
        cut = go()
        zeroed = (cut is not None and len(cut) == 8
                  and all(r[0] == 0 and r[1] == 0 and r[2] == 0
                          for r in cut[5:]))
        c.ok(zeroed,
             "XFAIL (recorded OPEN in docs-notes/OPENITEMS.md): fed a file "
             "whose header claims 8 records while the payload holds 5, the "
             "port does NOT refuse it - it emits 8 records and generates the "
             "last three from zeroed coordinates. If this check ever FAILS "
             "the defect was fixed: update OPENITEMS.md and delete it",
             "%s records, tail zero-filled: %s"
             % (None if cut is None else len(cut), zeroed))
        if cut is not None and full is not None:
            c.ok(cut[5:] != full[5:],
                 "...and those three records really are different from the "
                 "intact run, so the probe measured the truncation and not "
                 "a stale output file")

    spec = os.path.join(harness, "geo_spec.py")
    if os.path.exists(spec):
        with open(spec, encoding="utf-8") as fh:
            s = fh.read()
        c.ok("NSIN header claims" in s,
             "the Python reference DOES validate the NSIN payload length "
             "against the header - one of the three readers has the check")
    c.note("STILL OPEN, with the route recorded in docs-notes/OPENITEMS.md: "
           "(a) planetary geometry has no 1996 oracle - section 5 shows the "
           "only candidate readout is structurally blind; (b) nsrun's NSIN "
           "length validation.")


# ======================================================================

def main():
    quick = "--quick" in sys.argv
    limit = 200
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    c = L.Check("test_geometry - the cast boundary (settled against the 1996 "
                "machine code), the geometry values (two implementations, "
                "NOT an oracle) and the DL blind spot")

    print()
    print("-- 1. THE SHIPPED BINARY: what __ftol actually does " + "-" * 20)
    section_binary(c)

    sbdir = os.path.join(L.gen_dir(), "tgeo")
    os.makedirs(sbdir, exist_ok=True)

    def sb(name):
        return os.path.join(sbdir, name)

    harness = L.HARNESS
    print()
    print("-- 2. THE REFERENCE ENGINES, REBUILT " + "-" * 35)
    if shutil.which("gcc") is None:
        c.ok(False, "gcc is on PATH - the C reference cannot be built "
                    "without it and sections 2-6 depend on it")
        return c.done()

    # the sandbox copy is byte-identical to the delivered reference
    ref = os.path.join(harness, "geo_ref.c")
    if not c.ok(os.path.exists(ref), "noctis-harness/geo_ref.c is present"):
        return c.done()
    refsrc = sb("georef.c")
    shutil.copyfile(ref, refsrc)
    c.ok(L.sha(open(ref, "rb").read()) == L.sha(open(refsrc, "rb").read()),
         "the sandbox copy of geo_ref.c is byte-identical to the delivered "
         "one - what is graded IS the reference")
    ok, msg = gcc_build(refsrc, sb("georef.exe"))
    if not c.ok(ok, "gcc rebuilds it with -fwrapv -Wall", msg or "clean"):
        return c.done()
    c.ok(not msg, "...without a single diagnostic", msg)

    rc, msg = run_tool([sys.executable, os.path.join(harness, "geo_spec.py"),
                        "--selftest"], cwd=harness)
    c.ok(rc == 0 and "PASS" in msg, "geo_spec.py's rounding self-test", msg)

    # the corpus, re-swept this run from the galaxy hash and STARMAP.BIN
    corpus = sb("corpus.nsin")
    rc, msg = run_tool([sys.executable, os.path.join(harness, "ns_corpus.py"),
                        "--box", "dl", "--limit", str(limit),
                        "--out", corpus, "--manifest", sb("corpus.tsv")],
                       cwd=harness)
    swept = rc == 0 and os.path.exists(corpus)
    if not c.ok(swept,
                "the corpus is re-swept from the galaxy hash and STARMAP.BIN "
                "this run - no stored corpus is opened",
                "" if swept else msg[-400:]):
        return c.done()
    for line in msg.strip().splitlines()[-3:]:
        c.note("  " + line.strip())

    section_defaults(c, sb, corpus, limit, harness)

    variants = {}
    for cast in ("chop", "near"):
        for csrc in ("ext", "f64"):
            for prec in ("ext", "f64"):
                if prec == "f64" and (cast, csrc) != ("chop", "ext"):
                    continue
                out = sb("v%s%s%s.geob" % (cast, csrc, prec))
                rc, msg = run_tool([sb("georef.exe"), corpus, out,
                                    "--cast", cast, "--castsrc", csrc,
                                    "--prec", prec])
                if rc != 0:
                    c.ok(False, "geo_ref runs at %s/%s/%s"
                         % (cast, csrc, prec), msg)
                    return c.done()
                variants[(cast, csrc, prec)] = read_geob(out)[1]

    print()
    print("-- 3. TWO IMPLEMENTATIONS, BIT FOR BIT (not an oracle) " + "-" * 17)
    py, planets = section_engines(c, sb, corpus, limit, harness, variants)

    print()
    print("-- 4. HOW FINE IS THAT? A MEASURED BOUND " + "-" * 31)
    if py is not None:
        section_resolution(c, sb, corpus, refsrc, py, planets)

    print()
    print("-- 5. THE ORACLE THAT DOES NOT EXIST " + "-" * 35)
    section_oracle(c, variants)

    print()
    print("-- 6. THE COST OF THE BOUNDARY, AND THE SITE REGISTRY " + "-" * 18)
    section_cost(c, variants, refsrc)

    print()
    print("-- 7. THE DL BLIND SPOT: bclip " + "-" * 41)
    if quick:
        c.note("SKIPPED by --quick. This is NOT a pass: --quick skips the "
               "two L.in.oleum builds that show the graders can fail.")
    else:
        section_bclip(c)

    print()
    print("-- 8. STILL OPEN " + "-" * 55)
    section_open(c, harness, quick)

    print()
    return c.done()


if __name__ == "__main__":
    L.main_guard(main)
