#!/usr/bin/env python3
"""fb_compare.py -- Wave 5-corrective, implementer 2.  The grader.

Grades the lino framebuffer against the two independent references and against
the 1996 capture routes, on three tiers:

  Tier 1  against artifacts this project did not make.  Wave 5 has no
          renderer, so this is the PALETTE only -- but that grades the whole
          palette pipeline, and it is genuinely non-circular.
  Tier 2  lino vs fb_ref.c and lino vs fb_pal.py / fb_layout.py / fb_tick.py,
          byte-exact on every FBDUMP kind.
  Tier 3  properties that need no oracle: the layout by construction, the
          canary, the tick soak recomputed from raw counts, the servo.

Every comparison is exact.  Nothing is graded against a stored artifact this
project produced, and every subject has a deliberately broken build that this
script must reject.

A row is PASS, FAIL, or **NOT GRADED**.  NOT GRADED is printed, counted
separately, and never folded into the pass count -- because the Wave 5 defect
this file exists to fix was a suite that reported a bare pass for things it
could not see.

  python fb_compare.py --suite                     # everything, from scratch
  python fb_compare.py --suite --lino DIR          # ... including the lino dumps
  python fb_compare.py --ungraded                  # what this harness cannot grade
  python fb_compare.py --scenario-spec             # LINOBUF 6.1, from the doc
  python fb_compare.py A.bin B.bin                 # one pairwise compare
"""

import argparse
import collections
import glob
import hashlib
import os
import struct
import subprocess
import sys

from fb_layout import (Layout, Workspace, fbdump_read, fbdump_write, layout_payload,
                       fixture_load, fx_int, fx_float, FixtureError,
                       zones_payload, fnv1a32, KIND_NAME, TAG_NAME, TAG, KSELF_FIELD,
                       KIND_INDEXPAGE, KIND_PALETTE6, KIND_LUT, KIND_TICKLOG,
                       KIND_LAYOUT, KIND_CANARY, KIND_KSELF, KIND_KFRM, KIND_ZONES,
                       KIND_WRAPCOUNT, KIND_SERVOLOG, FBD_VERSION,
                       LAYOUT_BREAKS, WORKSPACE_BREAKS, solve_seg_offset)
import fb_pal
import fb_tick
import fb_bmp
import fb_wrap
import fb_stick
import fb_ledger

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fbout")
CAPS = os.path.abspath(os.path.join(HERE, "..", "tests", "gen", "recon_w5c", "artifacts"))
SUPPORTS = r"C:\programmieren\noctis\niv-plus\data\SUPPORTS.NCT"
LINOBUF = os.path.abspath(os.path.join(HERE, "..", "docs-notes", "LINOBUF.md"))
FIXTURE_FILE = os.path.abspath(os.path.join(HERE, "..", "docs-notes", "FIXTURE1.txt"))
# KSELF fields 80..87 carry the first 32 hex digits of the SHA-256 of the
# fixture the producer compiled its stimulus from; 88 the SOLVED far-pointer
# offset; 89 the number of solver constraints; 90 the fixture ops executed;
# 91 the fixture's byte length.  The block sits at 80 and not at 24 because the
# lino producer's KSELF stream already occupies ids 0..64.
KSELF_FIXTURE_HASH = 80
FIXTURE = fixture_load()

# KSELF ids in the normative range that two conforming producers may LEGALLY
# disagree about, with the reason.  Printed on every suite run.  Keep this map
# as close to empty as the truth allows: it is the one place in this grader
# where a real disagreement could be hidden, so every entry has to argue for
# itself in the report, not in a comment.
KSELF_NOT_COMPARABLE = {
    89: "the NUMBER OF CONSTRAINTS the far-pointer-offset solver used.  It is a "
        "property of the solver, not of Noctis, so it is not independently "
        "computable and two correct solvers legally differ -- measured today, "
        "fb_layout.py uses 4 and fb_ref.c uses 13.  The CLAIM is field 88, the "
        "SOLVED K, and that agrees: two independent solvers, one answer.  "
        "FLAGGED: either 89 is dropped or it is defined normatively.",
    90: "the number of fixture OPS EXECUTED.  Well-defined only once both "
        "producers run the same sections in the same order; kept comparable "
        "here by mirroring fb_ref.c's sequence, and reported rather than "
        "trusted until LINOBUF fixes the sequence in writing.",
}

# Every single-edit sabotage of the C reference, and the record that must
# reject it.  `target` is asserted, but the grader also prints EVERY record that
# moved, so a sabotage caught only by accident is visible.
C_BREAKS = [
    ("BREAK_SHIFTOR", "LUT via (v<<2)|(v>>4) instead of v*4", "lut"),
    ("BREAK_UPLOADFIRST", "tavola_colori uploads [first,first+n)", "kself"),
    ("BREAK_ROUNDSHADE", "shade() rounds instead of truncating", "pal6"),
    ("BREAK_NOCLAMP", "tavola_colori drops the >63 clamp", "pal6"),
    ("BREAK_NOSELF", "self-copy reloads a stale source", "pal6"),
    ("BREAK_DIV64", "the filter divides by 64 instead of 63", "pal6"),
    ("BREAK_PYFILT", "the filter uses unbounded floor division (fb_pal.py's old bug)", "pal6"),
    ("BREAK_IGNOREDST", "shade() ignores its destination buffer  [SH-IGNOREDST]", "selftest"),
    ("BREAK_SELFSOURCE", "the fade re-reads tmppal, so fades compound  [SH-COMPOUND]", "selftest"),
    ("BREAK_DIGITN1", "digit_at loop starts at n=1 (niv-lr's bug)", "glyph"),
    ("BREAK_TINTA64000", "alias 8 at 64000 (niv-lr's divergence)", "adapted"),
    ("BREAK_PACK4", "packed 4 bytes per unit", "selftest"),
    ("BREAK_QUADWORDS", "page ops hard-code 64000 bytes", "adapted"),
    ("BREAK_TICKCMP", "unsigned timestamp wait predicate", "selftest"),
    ("BREAK_SHRINKADAPTOR", "adaptor sized 64000, not a full segment", "layout"),
    ("BREAK_MASKSPOT", "drop the 16-bit store mask at spot  [S-MASK-SPOT]", "wrapcount"),
    ("BREAK_MASKCIRRUS", "drop the 16-bit store mask at cirrus", "wrapcount"),
    ("BREAK_MASKCIRRUSADDR", "mask cirrus' address, not its truncation point "
                             "[S-MASK-CIRRUS-ADDR]", "kself"),
    ("BREAK_SEGADDRBASE", "wrap taken against the base, not base-4  [S-SEGADDR-BASE]", "adapted"),
    ("BREAK_PADONEMAGIC", "one poison for both pad zones  [S-PAD-ONEMAGIC]", "zones"),
    ("BREAK_PAD9WALK", "walk 9 region pads, not 22 zones  [S-PAD-9WALK]", "canary"),
    ("BREAK_CANSTUBCHECK", "the walker never compares  [S-CAN-STUBCHECK]", "canary"),
    ("BREAK_CANSTUBPOISON", "the pads are never poisoned  [S-CAN-STUBPOISON]", "canary"),
    ("BREAK_CANCONSTACTUAL", "the canary's `actual` is a literal  [S-CAN-CONSTACTUAL]", "canary"),
    ("BREAK_LAYOUTEND", "kind 5 unit 2 is the preceding pad, not base+size", "layout"),
]

# Which reference file carries each record.
REC = {
    "layout": ("fb-ref-layout.bin", KIND_LAYOUT, "layout"),
    "zones": ("fb-ref-zones.bin", KIND_ZONES, "zones"),
    "pal6": ("fb-ref-pal6.bin", KIND_PALETTE6, "pal6"),
    "curpal6": ("fb-ref-curpal6.bin", KIND_PALETTE6, "curpal6"),
    "lut": ("fb-ref-lut.bin", KIND_LUT, "lut"),
    "adapted": ("fb-ref-adapted.bin", KIND_INDEXPAGE, "adapted"),
    "adaptor": ("fb-ref-adaptor.bin", KIND_INDEXPAGE, "adaptor"),
    "glyph": ("fb-ref-glyph.bin", KIND_INDEXPAGE, "glyph"),
    "canary": ("fb-ref-canary.bin", KIND_CANARY, "canary"),
    "wrapcount": ("fb-ref-wrapcount.bin", KIND_WRAPCOUNT, "wrapcount"),
    "kself": ("fb-ref-kself.bin", KIND_KSELF, "selfcheck"),
}

# What this harness CANNOT grade, stated rather than pretended.  Printed by
# --ungraded and by every suite run.
UNGRADED = [
    ("the farmalloc offset K", "TIER 3, NOT MEASURED",
     "RAISED FROM TIER 0 THIS WAVE, and the raise is worth stating precisely.  "
     "It WAS the literal 4, written into fb_layout.py:83 and into fb_ref.c:68 -- "
     "one number handed to both 'independent' producers, so their agreement about "
     "alias 8 measured nothing at all.  `solve_seg_offset` now treats K as an "
     "unknown and intersects four PARSED constraints: sc_bytes = 65536 + K; "
     "Stick's two branches addressing one pixel, one through the offset loaded by "
     "`les si, dword ptr adapted` and one through the literal displacement "
     "`es:[di+D]`, so K = D; wave()'s `add ax, D2` before `es:[di]`, so K = D2; "
     "and polymap's `es:[0xFA00]` having to land on the visible page.  Exactly one "
     "K survives.  Falsified by editing the Stick displacement in a sandbox copy "
     "-- fb_mutcov runs it and the solver then REFUSES.  Still NOT MEASURED: the "
     "decisive experiment is DOSBox-X + NOCTIS.SYM, reading adapted's offset word "
     "after init_FP_segments (rig at tests/gen/recon_w5c/hostshot4.ps1), and that "
     "same experiment retires the riga[] VALUES divergence below."),
    ("Stick's riga[] out-of-bounds VALUES", "DIVERGENCE",
     "fb_stick.py measures that the index escapes and by how much, but the VALUES "
     "riga[y] reads for y outside 0..199 come from whatever the DOS data segment "
     "held next to RIGA, which this project has never measured.  The adopted "
     "divergence defines riga[y] = 320*y and masks the result.  Retirement "
     "condition: extract RIGA's neighbours from NOCTIS.SYM -- the same rig as "
     "item 1."),
    ("M1 crater's wrap RATE", "BOUNDED, NOT MEASURED",
     "fb_wrap.py measures the conditional rate for both ray multipliers, which "
     "brackets it; which multiplier fires is Borland random()-driven and outside "
     "the exhaustive parameter sweep."),
    ("M3 polymap's bump branch", "OPEN",
     "`sub di,320` x(1..8) then `mov [di+640+3]` underflows in the top 8 rows.  "
     "Reachability depends on whether any Noctis material sets flag 8.  "
     "Unresolved; nothing here touches it."),
    ("Everything visual", "NO RENDERER",
     "Kinds 1/2/3 are graded as exact transformations of state the project itself "
     "built, plus the 1996 BMP palette for v*4 (Tier 1).  Nothing is eyeballed as "
     "a pass criterion."),
    ("KFRM (kind 8)", "UNGRADED BY NATURE",
     "Raw frame timing.  A defined kind with no oracle; reported, never graded."),
    ("KSELF field ids >= 100", "PORT-LOCAL",
     "Ids 1..99 are normative and independently computable, so they are graded.  "
     "100+ are port-local by definition and are printed, never compared."),
    ("the fixture as a DOCUMENT", "REPLACED BY A HASH",
     "The old row substring-hunted bare integers -- \"16\", \"32\", \"63\", \"200\" -- "
     "inside LINOBUF 6.1, a section that IS THE RECORD SET and not a fixture.  Its "
     "verdict was therefore decided by heading numbering: it flipped from NOT "
     "GRADED to FAIL because an unrelated heading took the number.  What replaces "
     "it is a BUILD IDENTITY check: docs-notes/FIXTURE1.txt is hashed and every "
     "producer must carry, in KSELF 80..87, the hash it compiled against.  A "
     "producer that did not rebuild fails; wording cannot satisfy it."),
    ("the lino leg of kinds 1/2/3", "NOT GRADED",
     "The lino build and fb_ref.c ran DIFFERENT FIXTURES.  Printing 63,988 "
     "differing units as a red row is a category error and the mirror image of "
     "Wave 5's sin; both stop here.  It becomes gradeable when the lino producer "
     "re-derives from FIXTURE1.txt, and it becomes evidence only when a lino "
     "SABOTAGE is shown to break a record while the clean build passes it."),
]

# Per-element tier statement.  Three columns now, because the old two conflated
# two different ladders that run in OPPOSITE directions:
#
#   EVIDENCE tier  (LINOBUF 7 / BUFFERMODEL 11, normative -- 1 is strongest)
#       1  graded against artifacts this project did not make
#       2  graded against a second, independent implementation
#       3  a property that needs no oracle at all
#       0  ASSERTED: zero graders, no falsifiable step
#   producers      how many independent constructions agree.  A COUNT.  It was
#                  being printed as "Tier 2", which read as stronger than
#                  "Tier 1" under the other scheme.
#   falsifiers     GENERATED FROM THE LEDGER, so a claim cannot outrun its
#                  demonstrated falsifiers.
#
# Every "corrected" line below was measured this wave, not re-argued.
TIER_TABLE = [
    ("palette filter arithmetic", "1+2", 2, ["T1.PAL.FIT", "T2.REC.PAL6.PYVSC"], ""),
    ("shade chop-vs-round", "2", 2, ["T2.REC.PAL6.PYVSC"], "first entry of step 3"),
    ("upload-from-zero", "2", 2, ["T2.REC.KSELF.PYVSC"], "trace digests; the FINAL state does not"),
    ("the self-copy", "2", 2, ["T2.REC.PAL6.PYVSC"], "step 7, NOT step 4 -- measured"),
    ("v*4 vs shift-or", "1", 2, ["T1.BMP.SCALE", "T1.PNG.SCALE"],
     "768/768 BMP bytes = 0 mod 4; shift-or falsified on two capture routes"),
    ("shade's destination buffer", "2", 2, ["T2.CSELFTEST"], "SH-COMPOUND caught"),
    ("alias 8 placement", "2", 2, ["T2.ALIAS8.PLACEMENT"], "parsed vs transcribed"),
    ("alias 8 PREMISE (offset K)", "3", 1, ["T3.LAYOUT.L12C.SEGOFFSET"],
     "WAS TIER 0.  K is now SOLVED from four parsed constraints, not written "
     "as a literal into both producers.  Still NOT MEASURED: DOSBox-X only."),
    ("the raster loop (digit_at n=0)", "2", 2, ["T3.PADPROBE.EXPECTATION"], ""),
    ("the 22-zone pad model", "2", 2, ["T3.PADPROBE.VIOLATION"], ""),
    ("the canary", "3", 2, ["T3.CANARY.V1VSV2"],
     "CORRECTED from `TIER 2, 4 caught sabotages`.  It is a property with no "
     "oracle (tier 3), two producers.  Unit 1 was VOID until this wave: "
     "replacing the read-back with the literal moved 0 of 44 units."),
    ("class-A masks", "3", 2, ["T3.CLASSA.SABOTAGE.MASKSPOT"],
     "CORRECTED from `reachability EXHAUSTIVE over the domain`, which "
     "contradicts BUFFERMODEL 10.6 verbatim: exhaustive over the parsed "
     "parameter domains of the TWO CENSUSED callers.  volcano and atm_cyclon "
     "are uncensused."),
    ("A1 Segmento", "3", 1, ["T3.STICK.A1"], "PROVEN unnecessary: poly3d's clamp, swept"),
    ("A3 mask_pixels", "3", 1, ["T3.LAYOUT.CHECK"], "PROVEN unnecessary at the steady QUADWORDS"),
    ("A7 ptr", "3", 1, ["T3.LAYOUT.L14.PTRUNSIGNED"],
     "a typing requirement.  Its row was a Python fact until this wave; the "
     "loop constants are parsed now."),
    ("A2 Stick riga[] INDEX", "3", 1, ["T3.STICK.A2CORPUS"], ""),
    ("A2 Stick riga[] VALUES", "0", 0, [], "DIVERGENCE, deliberate, named retirement condition"),
    ("the tick period", "2", 2, ["T2.TICK.ARITH"], "unbounded-integer truth vs the 32-bit form"),
    ("the tick RATE vs its header", "3", 1, ["T3.TICK.RATEPROBE"],
     "NEW.  Until K6 landed this wave, a log generated at 9900 cpms under a "
     "9000 header passed every check in fb_tick.py."),
    ("the servo", "3", 1, ["T3.SERVO.BATTERY"],
     "8 caught sabotages, and the estimator is now seeded 4% LOW -- seeded at "
     "the true rate, a do-nothing estimator passed T8a, T8f and T8h."),
    ("SRVMAX", "3", 1, ["T3.SERVO.BATTERY"],
     "CORRECTED from `MEASURED here, not asserted`, which was false: the sweep "
     "that justified it could not fail.  Bisected now, and the guard is "
     "derived from the calibrated cpms."),
    ("kinds 1/2/3 CONTENT, C vs Python", "2", 2, ["T2.REC.ADAPTED.PYVSC"],
     "CORRECTED from `pinned scenario`: no pinned scenario exists yet."),
    ("kinds 1/2/3 CONTENT, the lino leg", "0", 1, ["T2.LINO.ADAPTED.CROSSFIXTURE"],
     "NOT GRADED.  Two fixtures, zero cross-team agreement."),
    ("the index page", "0", 1, ["T2.LINO.ADAPTED.CROSSFIXTURE"],
     "PORTPLAN's `the index page is Tier 1` is DELETED.  One producer team per "
     "fixture, two fixtures; Tier 1 is unreachable by construction until a "
     "renderer exists."),
    ("kinds 1/2/3 vs a FRAME", "0", 0, [], "SCOPED OUT: no renderer exists"),
    ("KFRM (kind 8)", "0", 0, [], "UNGRADED by nature: raw timing"),
]


def fixture_identity():
    """WAVE 5c, disposition REFOUND.

    The row this replaces substring-hunted bare integers -- "16", "32", "63",
    "200" -- inside LINOBUF 6.1, a section that IS THE RECORD SET, not a
    fixture.  Its verdict was therefore decided by heading numbering: it flipped
    from NOT GRADED to FAIL because an unrelated heading took the number.  A
    document check that grades text is not a check.

    What a fixture check can honestly do is grade a BUILD IDENTITY: hash the
    architect-owned stimulus file and require every producer to carry the hash
    it compiled against.  That is falsifiable (edit the fixture, every producer
    that did not rebuild fails) and it cannot be satisfied by wording.

    Returns (sha256 hex or None, note).
    """
    if not os.path.exists(FIXTURE_FILE):
        return None, ("docs-notes/FIXTURE1.txt does not exist.  The pinned stimulus is "
                      "the ARCHITECT'S deliverable and is deliberately outside both "
                      "implementers' namespaces -- an implementer who can edit the "
                      "stimulus can make any comparison pass.  Until it lands, the "
                      "fixture leg is NOT GRADED, and the two references agree with "
                      "each other while nothing pins either to a document.")
    with open(FIXTURE_FILE, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest(), ""


def linobuf_section(anchor):
    """Locate a LINOBUF section by an EXPLICIT ANCHOR LINE, never by a heading
    number.  `read_linobuf_61` scanned for the string "6.1", which is why an
    unrelated heading could take the number and flip the verdict."""
    if not os.path.exists(LINOBUF):
        return None, "LINOBUF.md not found at %s" % LINOBUF
    with open(LINOBUF, "r", encoding="utf-8", errors="replace") as fh:
        lines = fh.read().splitlines()
    start = None
    for i, ln in enumerate(lines):
        if anchor.lower() in ln.lower():
            start = i
            break
    if start is None:
        return None, "LINOBUF.md carries no line matching the anchor %r" % anchor
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("#"):
            end = j
            break
    return "\n".join(lines[start:end]), ""


# ----------------------------------------------------------- containers


def read_container(path):
    """Every FBDUMP record in a file (or in every .bin of a directory)."""
    if os.path.isdir(path):
        out = []
        for name in sorted(os.listdir(path)):
            if name.lower().endswith(".bin"):
                out += read_container(os.path.join(path, name))
        return out
    with open(path, "rb") as fh:
        d = fh.read()
    out, off = [], 0
    while off + 64 <= len(d):
        h = struct.unpack("<16I", d[off:off + 64])
        if h[0] != 0x46424431:
            raise SystemExit("%s: bad FBDUMP magic %08X at offset %d" % (path, h[0], off))
        if h[1] not in (1, 2):
            raise SystemExit("%s: FBDUMP version %d, expected 1 or 2" % (path, h[1]))
        cnt = h[5]
        end = off + 64 + 4 * cnt
        if end > len(d):
            raise SystemExit("%s: record at %d claims %d units but the file ends" % (path, off, cnt))
        out.append({"kind": h[2], "version": h[1], "width": h[3], "height": h[4],
                    "count": cnt, "cpms": h[6], "ticks": h[7],
                    "tag": h[8] if h[1] >= 2 else 0,
                    "payload": list(struct.unpack("<%dI" % cnt, d[off + 64:end])),
                    "raw": d[off:end], "offset": off, "path": path})
        off = end
    if off != len(d):
        raise SystemExit("%s: %d trailing bytes after the last record" % (path, len(d) - off))
    return out


def write_record(path, rec):
    with open(path, "wb") as fh:
        fh.write(rec["raw"])
    return path


# ------------------------------------------------------------- compare core


# `diff_payload` lived here.  DELETED: no caller, and dead code in a grader is
# a check nobody runs.


def compare_keyed(a, b, label_a, label_b, kind):
    """KSELF (kind 7) and WRAPCOUNT (kind 10) are KEYED records, not positional
    ones: KSELF is (field id, value) pairs and WRAPCOUNT is (site id, calls,
    wraps) rows.  Two conforming implementations may legally carry different
    SETS -- KSELF ids >= 100 are port-local by definition, and a port that
    instruments more class-A sites than this reference has more rows.

    So compare on the INTERSECTION of the normative keys, and report the rest
    rather than failing on a length mismatch.  A straight payload compare here
    would turn "the other side instruments more" into a failure, which is
    exactly the kind of false verdict the container-vs-content confusion
    produced in v1.
    """
    lines = []
    if kind == KIND_KSELF:
        stride, keyname = 2, "field"
        # ids 1..99 are normative BECAUSE they are independently computable.
        # A field that is not is a field two conforming producers may legally
        # disagree about, and grading it turns an implementation detail into a
        # red row.  The exclusions are listed here, with the reason, and
        # PRINTED on every run -- an exemption nobody can see is a suppression
        # list, which is the failure mode this whole wave is about.
        pass
        da = {a[i]: tuple(a[i + 1:i + 2]) for i in range(0, len(a) - 1, 2)}
        db = {b[i]: tuple(b[i + 1:i + 2]) for i in range(0, len(b) - 1, 2)}
        normative = lambda k: 1 <= k < 100 and k not in KSELF_NOT_COMPARABLE
        name = lambda k: KSELF_FIELD.get(k, "port-local")
    else:
        stride, keyname = 3, "site"
        da = {a[i]: (a[i + 1], a[i + 2]) for i in range(0, len(a) - 2, 3)}
        db = {b[i]: (b[i + 1], b[i + 2]) for i in range(0, len(b) - 2, 3)}
        normative = lambda k: True
        name = lambda k: {1: "spot", 2: "cirrus", 3: "crater", 4: "alias8"}.get(k, "?")
    if kind == KIND_KSELF:
        # SHAPE diagnostic.  A record read as (field id, value) pairs whose ids
        # are not a strictly increasing set of small integers is almost
        # certainly a POSITIONAL dump instead -- a different reading of "KSELF's
        # field list", and a format divergence rather than a value disagreement.
        # Say which it is; the two need different fixes.
        for lbl, raw in ((label_a, a), (label_b, b)):
            ids = [raw[i] for i in range(0, len(raw) - 1, 2)]
            increasing = all(y > x for x, y in zip(ids, ids[1:]))
            if not increasing:
                return False, [
                    "    SHAPE MISMATCH, not a value disagreement: %s does not read as "
                    "(field id, value) pairs" % lbl,
                    "      its even-indexed units are %s..., which is not a strictly "
                    "increasing id set" % ids[:8],
                    "      FBDUMP v2 kind 7 is 2 units per field, (id, value), ids 1..99 "
                    "normative and 100+ port-local.  A positional dump carries the same",
                    "      information but cannot be compared across implementations with "
                    "different field sets, which is the whole reason for the id.",
                ]
    shared = sorted(k for k in da if k in db and normative(k))
    bad = [k for k in shared if da[k] != db[k]]
    only_a = sorted(k for k in da if k not in db and normative(k))
    only_b = sorted(k for k in db if k not in da and normative(k))
    extra_a = sorted(k for k in da if not normative(k))
    ok = not bad and not only_a and not only_b
    if ok:
        lines.append("    %s == %s on all %d normative %ss%s"
                     % (label_a, label_b, len(shared), keyname,
                        "" if not extra_a else
                        "; %d port-local %s(s) reported, never compared: %s"
                        % (len(extra_a), keyname, extra_a[:8])))
        return True, lines
    for k in bad[:8]:
        lines.append("      %s %-3d (%-20s)  %s=%s  %s=%s"
                     % (keyname, k, name(k), label_a, da[k], label_b, db[k]))
    if only_a:
        lines.append("      %ss only in %s: %s" % (keyname, label_a, only_a[:12]))
    if only_b:
        lines.append("      %ss only in %s: %s" % (keyname, label_b, only_b[:12]))
    if extra_a:
        lines.append("      port-local %ss in %s (not graded): %s"
                     % (keyname, label_a, extra_a[:12]))
    return False, lines


def compare_dumps(pa, pb, label_a="A", label_b="B", show=6):
    lines = []
    try:
        a = fbdump_read(pa)
        b = fbdump_read(pb)
    except Exception as exc:
        return False, ["    ERROR %s" % exc]

    if a["kind"] != b["kind"]:
        return False, ["    kind mismatch: %s=%s %s=%s"
                       % (label_a, KIND_NAME.get(a["kind"]), label_b, KIND_NAME.get(b["kind"]))]
    if a["kind"] in (KIND_KSELF, KIND_WRAPCOUNT):
        return compare_keyed(a["payload"], b["payload"], label_a, label_b, a["kind"])
    if a["count"] != b["count"]:
        return False, ["    count mismatch: %s=%d %s=%d" % (label_a, a["count"], label_b, b["count"])]
    if a["kind"] == KIND_INDEXPAGE and (a["width"], a["height"]) != (b["width"], b["height"]):
        return False, ["    geometry mismatch: %dx%d vs %dx%d"
                       % (a["width"], a["height"], b["width"], b["height"])]
    if a["version"] >= 2 and b["version"] >= 2 and a["tag"] != b["tag"]:
        return False, ["    tag mismatch: %s=%s %s=%s"
                       % (label_a, TAG_NAME.get(a["tag"]), label_b, TAG_NAME.get(b["tag"]))]

    pa_, pb_ = a["payload"], b["payload"]
    diff = [i for i in range(len(pa_)) if pa_[i] != pb_[i]]
    if not diff:
        lines.append("    %s == %s  (%d units of %s%s, exact)"
                     % (label_a, label_b, a["count"], KIND_NAME.get(a["kind"], a["kind"]),
                        "/" + TAG_NAME.get(a["tag"], "?") if a["tag"] else ""))
        return True, lines

    lines.append("    %s != %s  (%d of %d units differ)" % (label_a, label_b, len(diff), a["count"]))
    k = a["kind"]
    for i in diff[:show]:
        if k == KIND_INDEXPAGE and a["width"]:
            w = a["width"]
            lines.append("      unit %6d  (x=%3d y=%3d)  %s=%d  %s=%d"
                         % (i, i % w, i // w, label_a, pa_[i], label_b, pb_[i]))
        elif k == KIND_PALETTE6:
            lines.append("      unit %6d  (colour %3d %s)  %s=%d  %s=%d"
                         % (i, i // 3, "RGB"[i % 3], label_a, pa_[i], label_b, pb_[i]))
        elif k == KIND_LUT:
            lines.append("      colour %3d  %s=%08X  %s=%08X" % (i, label_a, pa_[i], label_b, pb_[i]))
        elif k == KIND_LAYOUT:
            fld = ["base", "size", "base+size", "rid"][i % 4]
            lines.append("      region %d field %-9s  %s=%d  %s=%d"
                         % (i // 4, fld, label_a, pa_[i], label_b, pb_[i]))
        elif k == KIND_ZONES:
            fld = ["base", "len", "owner", "role"][i % 4]
            lines.append("      zone %d field %-6s  %s=%d  %s=%d"
                         % (i // 4, fld, label_a, pa_[i], label_b, pb_[i]))
        elif k == KIND_CANARY:
            fld = ["clean_read", "dirty_read", "fired", "at"][i % 4]
            lines.append("      pad %d %-11s  %s=%08X  %s=%08X"
                         % (i // 4, fld, label_a, pa_[i], label_b, pb_[i]))
        elif k == KIND_WRAPCOUNT:
            fld = ["site", "calls", "wraps"][i % 3]
            lines.append("      site row %d %-6s  %s=%d  %s=%d"
                         % (i // 3, fld, label_a, pa_[i], label_b, pb_[i]))
        elif k == KIND_KSELF:
            fid = pa_[i - 1] if i % 2 else pa_[i]
            lines.append("      field %d (%s)  %s=%d  %s=%d"
                         % (fid, KSELF_FIELD.get(fid, "port-local"), label_a, pa_[i],
                            label_b, pb_[i]))
        else:
            lines.append("      unit %6d  %s=%d  %s=%d" % (i, label_a, pa_[i], label_b, pb_[i]))
    if len(diff) > show:
        lines.append("      ... and %d more" % (len(diff) - show))
    return False, lines


# ------------------------------------------------- the Python-side records


def run_fixture_palette(fx, section, breaks=(), pal=None):
    """The palette half of the fixture interpreter.  Lives here rather than in
    fb_layout.py only because fb_pal imports fb_layout and not the reverse.

    Same rule as the page half: the script supplies the STIMULUS (which source,
    which window, which filter arguments) and this side supplies every
    MECHANISM (the DOS-16 filter, the upload extent, the clamp, the 6->8
    expansion, the destination-buffer semantics).
    """
    p = pal or fb_pal.Palette(breaks)
    r8 = None
    marks = 0
    snapshot = None
    n = 0
    for op, kv in fx["sections"][section]:
        n += 1
        if op == "reset_palettes":
            p.__init__(breaks)
        elif op == "load_range8088":
            r8 = fb_pal.range8088_generated()
        elif op == "mark":
            marks += 1
            p.mark(str(marks))
        elif op == "tavola_colori":
            src = fb_pal.SELF if kv["src"] == "self" else r8
            if src is None:
                raise FixtureError("tavola_colori src=range8088 before load_range8088")
            p.tavola_colori(src, fx_int(kv, "first"), fx_int(kv, "n"),
                            fx_int(kv, "fr"), fx_int(kv, "fg"), fx_int(kv, "fb"))
        elif op == "shade":
            dst = fb_pal.SRFPAL6 if kv["dst"] == "surface" else fb_pal.PAL6
            p.shade(dst, fx_int(kv, "first"), fx_int(kv, "n"),
                    fx_float(kv, "sr"), fx_float(kv, "sg"), fx_float(kv, "sb"),
                    fx_float(kv, "fr"), fx_float(kv, "fg"), fx_float(kv, "fb"))
        elif op == "snapshot_surface":
            snapshot = list(p.srfpal6)
        elif op == "fade_from":
            src = {"surface": fb_pal.SRFPAL6, "return": fb_pal.RETPAL6}[kv["src"]]
            p.fade_from(src, fx_int(kv, "first"), fx_int(kv, "n"),
                        fx_int(kv, "fr"), fx_int(kv, "fg"), fx_int(kv, "fb"))
        elif op == "lut_rebuild":
            p.lut()
        else:
            raise SystemExit("unknown fixture op %r in SECTION %s" % (op, section))
    return p, snapshot, n


def python_records(breaks=(), fx=None):
    """Build every record from the Python references, independently of the C."""
    lb = [b for b in breaks if b in LAYOUT_BREAKS]
    lay = Layout(lb)
    w = Workspace(lay, breaks=breaks)
    pbreaks = [b for b in breaks if b in fb_pal.BREAKS]
    fx = FIXTURE if fx is None else fx
    ops = 0
    if fx:
        # The SAME section sequence fb_ref.c runs -- surface, compound, then
        # surface again before page -- so that KSELF's `fixture ops executed`
        # field is comparable between the two producers.  A count that depended
        # on the producer's own call order would be a field that always differs
        # and therefore grades nothing.
        p, _snap, n1 = run_fixture_palette(fx, "surface", pbreaks)
        ops += n1
        pc, _snap2, n2 = run_fixture_palette(fx, "compound", pbreaks)
        ops += n2
        ladder = _snap2 or []
        _p2, _s3, n3 = run_fixture_palette(fx, "surface", pbreaks)
        ops += n3
        w.scenario_page(fx)
        ops += w.fixture_ops
        ref = fb_pal.Palette()
        want = [ref.filter_one(v, 24) for v in ladder]
    else:
        w.scenario_page()
        p = fb_pal.scenario_surface(pbreaks)
        pc, want, ladder = fb_pal.scenario_compound(pbreaks)
    probe_viol, probe_exp, _ = w.pad_probe_expectation()
    _can = w.canary_v2()
    extra = {
        4: probe_viol, 5: probe_exp,
        15: p.curpal6_trace_fnv(),
        16: sum(1 for v in ladder if v),
        # over however many pads the LAYOUT has -- 11 normally, 0 under NOPAD.
        # This read `range(11)` and raised IndexError the first time coverage
        # mode built a workspace on a padless layout.
        20: sum(1 for i in range(len(_can) // 4) if _can[4 * i + 2] == 0),
        21: fnv1a32(pc.pal6),
        22: p.pal6_trace_fnv(),
        23: p.upload_spans_fnv(),
    }
    if fx:
        # BUILD IDENTITY, fields 80..91.  Implementer 2 reserved this block in
        # fb_ref.c because the lino producer's KSELF stream already occupies
        # 0..64; a field-id collision between two producers is a comparison of
        # two different quantities that reads as a disagreement about one.
        for i in range(8):
            extra[80 + i] = int(fx["sha256"][8 * i:8 * i + 8], 16)
        seg = solve_seg_offset()
        extra[88] = seg["K"] if seg["K"] is not None else 0xFFFFFFFF
        extra[89] = len(seg["constraints"])
        extra[90] = ops
        extra[91] = fx["len"]
    recs = {
        "layout": (KIND_LAYOUT, layout_payload(lay), 0, 0, TAG["layout"]),
        "zones": (KIND_ZONES, zones_payload(lay), 0, 0, TAG["zones"]),
        "pal6": (KIND_PALETTE6, p.pal6, 0, 0, TAG["pal6"]),
        "curpal6": (KIND_PALETTE6, p.curpal6, 0, 0, TAG["curpal6"]),
        "lut": (KIND_LUT, p.lut(), 0, 0, TAG["lut"]),
        "adapted": (KIND_INDEXPAGE, w.page("adapted"), 320, 200, TAG["adapted"]),
        "adaptor": (KIND_INDEXPAGE, w.page("adaptor"), 320, 200, TAG["adaptor"]),
        "glyph": (KIND_INDEXPAGE, w.glyph_plane(), 256, 36, TAG["glyph"]),
        "canary": (KIND_CANARY, w.canary_v2(), 0, 0, TAG["canary"]),
        "wrapcount": (KIND_WRAPCOUNT, w.wrapcount_payload(), 0, 0, TAG["wrapcount"]),
        "kself": (KIND_KSELF, w.kself_payload(extra), 0, 0, TAG["selfcheck"]),
    }
    return recs, w, p


def write_python_records(recs, prefix="fb-py-"):
    for name, (kind, pay, wdt, hgt, tag) in recs.items():
        fbdump_write(os.path.join(OUT, "%s%s.bin" % (prefix, name)), kind, pay,
                     width=wdt, height=hgt, tag=tag)


# ---------------------------------------------------------------- the suite


class Suite(object):
    def __init__(self, linosrc=None, verbose=False, linobreaks=(), fast=False,
                 mutation=(), quiet=False, coverage=False):
        self.linosrc = linosrc
        self.linobreaks = list(linobreaks)
        self.verbose = verbose
        self.fast = fast
        self.rows = []       # (cid, tier, name, ok|None, detail)
        # WAVE 5c: coverage mode.  `mutation` is a break set threaded into every
        # PYTHON-SIDE SUBJECT; the check bodies are the same ones the graded run
        # uses, so fb_mutcov measures the real rows rather than a copy of them.
        self.mutation = set(mutation)
        self.quiet = quiet
        # Coverage mode skips the rows whose SUBJECT is a fixed sabotage rather
        # than the mutation under test -- `Layout([ORDER]).check()` produces the
        # same verdict for every suite mutation, so re-running it 30 times
        # measures nothing.  Those rows demonstrate their own falsifier inside
        # their own body, and the ledger marks them `inrow:` so the omission is
        # declared rather than assumed.
        self.coverage = coverage or bool(mutation)
        self.verdicts = {}   # cid -> True/False/None
        self.seen = set()

    def rec(self, cid, tier, name, ok, detail=""):
        """A row cannot exist without a ledger entry.  Unknown or duplicate cid
        raises; a cid the ledger declares NOTGRADED is FORCED to NOT GRADED, so
        a self-test cannot inflate the pass count by being reworded."""
        entry = fb_ledger.get(cid)
        if cid in self.seen:
            raise SystemExit("fb_compare: check id %r used twice in one run" % cid)
        self.seen.add(cid)
        if entry.kind == fb_ledger.NOTGRADED and ok is not None:
            detail = (detail + "  " if detail else "") + \
                     "[ledger: NOTGRADED -- %s]" % entry.why.split(".")[0]
            ok = None
        self.rows.append((cid, tier, name, ok, detail))
        self.verdicts[cid] = ok
        if not self.quiet:
            tagtxt = "PASS" if ok is True else ("FAIL" if ok is False else "NOT GRADED")
            print("  [%s] %-62s %s%s" % (tier, name, tagtxt,
                                         ("  " + detail) if detail and ok is not True else ""))
        return ok

    def say(self, *args):
        if not self.quiet:
            print(*args)

    def hush(self):
        """Silence a sub-module's own stdout in coverage mode.  fb_tick.main and
        friends print their own batteries; a 40-mutation sweep would otherwise
        emit 40 copies of them."""
        import contextlib
        import io
        return contextlib.redirect_stdout(io.StringIO()) if self.quiet \
            else contextlib.nullcontext()

    def mut(self, *names):
        """Python-side subjects take this as their break list."""
        return sorted(self.mutation)

    # -- build helpers ---------------------------------------------------

    def build_c(self, exe, defines=()):
        cmd = ["gcc", "-std=c99", "-O2", "-Wall", "-Wextra", "-o", exe]
        cmd += ["-D" + d for d in defines]
        cmd += [os.path.join(HERE, "fb_ref.c")]
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=HERE)
        return r.returncode == 0, (r.stdout + r.stderr)

    def run_c(self, exe, outdir):
        os.makedirs(outdir, exist_ok=True)
        r = subprocess.run([exe, outdir, SUPPORTS], capture_output=True, text=True, cwd=HERE)
        return r.returncode, r.stdout + r.stderr

    # -- tier 3: layout by construction ----------------------------------

    def tier3_layout(self):
        self.say("\nTier 3 -- layout by construction (fb_layout.py parses the 1996 sources)")
        mut = [b for b in self.mutation if b in LAYOUT_BREAKS]
        lay = Layout(mut)
        ok, msg = lay.check()
        self.rec("T3.LAYOUT.CHECK", "T3",
                 "fb_layout.py structural assertions (%d checks)" % len(msg), ok)
        if self.verbose or not ok:
            for m in msg:
                if not ok or self.verbose:
                    self.say("      " + m)
        # the individual rows the audit named, so their falsifiers are measured
        # separately rather than hidden inside one aggregate verdict
        def row(cid, prefix):
            hit = [m for m in msg if m[8:].startswith(prefix)]
            self.rec(cid, "T3", "%s (%d row(s))" % (prefix, len(hit)),
                     bool(hit) and all(m.startswith("  PASS") for m in hit))
        row("T3.LAYOUT.L1.ORDER", "L1")
        row("T3.LAYOUT.L4.DIGITSUB", "L4")
        row("T3.LAYOUT.L8.HEAPTOTAL", "L8")
        row("T3.LAYOUT.L9.ZONES", "L9")
        row("T3.LAYOUT.L12C.SEGOFFSET", "L12c")
        row("T3.LAYOUT.L14.PTRUNSIGNED", "L14")
        if not self.coverage:
            for b in LAYOUT_BREAKS:
                bad, _ = Layout([b]).check()
                self.rec("T3.LAYOUT.SABOTAGE.%s" % b, "T3",
                         "layout sabotage %-14s is rejected" % b, not bad)
        return ok

    # -- tier 2: three-way agreement -------------------------------------

    def tier2_c_vs_py(self):
        self.say("\nTier 2 -- fb_ref.c vs the Python references (independent constructions)")
        if self.mutation:
            # Coverage mode: the C side is the CLEAN dump already on disk, and
            # comparing a MUTATED Python producer against an UNMUTATED C one is
            # exactly the cross-check the row claims to be.  The two C rows are
            # then not re-run -- but they are not passed a literal `True`
            # either, which is the shape this wave exists to delete.  What is
            # asserted is what is actually known here: the clean artifacts the
            # rest of the run consumes are present.
            have = [os.path.join(HERE, "fb_ref.exe")] + \
                   [os.path.join(OUT, REC[n][0]) for n in REC]
            present = [p for p in have if os.path.exists(p)]
            self.rec("T2.CBUILD.CLEAN", "T2",
                     "the clean fb_ref.c build and its %d record(s) are on disk to compare "
                     "against" % (len(present) - 1), len(present) == len(have),
                     "coverage mode does not rebuild the C; missing %s"
                     % [os.path.basename(p) for p in have if p not in present])
            self.rec("T2.CSELFTEST", "T2", "fb_ref.exe self-test", None,
                     "coverage mode: not re-run.  The C matrix is measured by "
                     "tier2_sabotage in the graded run, not here.")
        else:
            ok, log = self.build_c(os.path.join(HERE, "fb_ref.exe"))
            if not self.rec("T2.CBUILD.CLEAN", "T2", "fb_ref.c builds clean with -Wall -Wextra",
                            ok and "warning" not in log, log[:300]):
                return False
            rc, out = self.run_c(os.path.join(HERE, "fb_ref.exe"), OUT)
            self.rec("T2.CSELFTEST", "T2", "fb_ref.exe self-test passes", rc == 0,
                     "\n".join(l for l in out.splitlines() if "FAIL" in l))
            if self.verbose:
                print(out)

        recs, w, p = python_records(self.mut())
        write_python_records(recs)
        for name in sorted(REC):
            fn = REC[name][0]
            good, lines = compare_dumps(os.path.join(OUT, "fb-py-%s.bin" % name),
                                        os.path.join(OUT, fn), "py", "C")
            self.rec("T2.REC.%s.PYVSC" % name.upper(), "T2",
                     "%-9s : Python == fb_ref.c, exact" % name.upper(), good)
            for l in lines:
                if not good or self.verbose:
                    self.say(l)

        # the two independent derivations of alias 8
        a8 = Layout(self.mut()).alias8()
        kself = {}
        pay = fbdump_read(os.path.join(OUT, "fb-ref-kself.bin"))["payload"]
        for i in range(0, len(pay), 2):
            kself[pay[i]] = pay[i + 1]
        self.rec("T2.ALIAS8.PLACEMENT", "T2",
                 "alias 8: fb_layout.py PARSES `mov es:[0x%04X]` out of TDPOLYGS.H, "
                 "fb_ref.c TRANSCRIBES it; both give adapted[%d] = row %d col %d"
                 % (a8["segoff"], a8["index"], a8["row"], a8["col"]),
                 (kself.get(7), kself.get(8), kself.get(9)) == (a8["nw"], a8["row"], a8["col"]))
        seg = solve_seg_offset()
        self.rec("T0.ALIAS8.PREMISE", "T0",
                 "alias 8's PREMISE: the farmalloc segment offset is SOLVED, not asserted "
                 "-- K = %s, unique over %d parsed constraints" % (seg["K"], len(seg["constraints"])),
                 None,
                 "RAISED FROM TIER 0 TO TIER 3 this wave.  It was the literal 4 in "
                 "fb_layout.py AND in fb_ref.c: one number handed to both 'independent' "
                 "producers, so their agreement measured nothing.  It is now derived "
                 "from source (see T3.LAYOUT.L12C) -- and it is still NOT MEASURED, "
                 "which is why this row is NOT GRADED rather than a pass.")

        # the raster loop, visible in two independent places
        census, padhits = w.overrun_census()
        self.rec("T3.OVERRUN.CENSUS", "T3",
                 "sea texture actually overruns n_globes_map: %d of 32000 texels land past "
                 "its end (%d of them in the 16-unit pad), so farmalloc order is under test"
                 % (census, padhits), census > 0 and padhits > 0)
        pv, pe, _ = w.pad_probe_expectation()
        self.rec("T3.PADPROBE.EXPECTATION", "T3",
                 "the raster loop is visible in TWO places: the 256x36 glyph plane, and "
                 "EXACTLY %d expectation hits in p_surfacemap's SUB zone" % pe,
                 (pv, pe) == (0, 6))
        vio, _, first = w.pad_probe_violation()
        self.rec("T3.PADPROBE.VIOLATION", "T3",
                 "and a real overrun is a VIOLATION, not an expectation: 1 unit past "
                 "n_globes_map fires once, at NW %s, in pad %s TAIL"
                 % (first, vio[0][1] if vio else "-"),
                 len(vio) == 1 and vio[0][2] == "TAIL")

        # MAJOR 5, demonstrated rather than argued: v1's kind 6 is BLIND to the
        # very sabotages v2 catches.  Both records are computed from the same
        # workspace under the same sabotage, so this is a like-for-like
        # comparison of the two record designs.
        self.say("      canary v1 vs v2, proof by disabling (same workspace, same sabotage):")
        base_v1 = Workspace().canary_v1()
        base_v2 = Workspace().canary_v2()
        blind = []
        for b in ([] if self.coverage else
                  ("CANSTUBCHECK", "CANSTUBPOISON", "CANCONSTACTUAL", "NINEWALK")):
            ww = Workspace(breaks=[b])
            v1 = ww.canary_v1()
            ww2 = Workspace(breaks=[b])
            v2 = ww2.canary_v2()
            d1 = sum(1 for x, y in zip(v1, base_v1) if x != y)
            d2 = sum(1 for x, y in zip(v2, base_v2) if x != y)
            # unit 1 is the WITNESS field.  Wave 5b's harness wrote the bare
            # literal 0xC0DE0000|i there, so unit 1 moved under NO mechanism
            # sabotage; it now folds in the poison the walker wrote.
            w1 = sum(1 for j in range(1, len(v2), 4) if v2[j] != base_v2[j])
            self.say("        %-15s v1 fnv %08X (%2d units differ)   v2 fnv %08X "
                     "(%2d units differ, %2d of them WITNESS fields)"
                     % (b, fnv1a32(v1), d1, fnv1a32(v2), d2, w1))
            if d1 == 0:
                blind.append(b)
        if not self.coverage:
            self.rec("T3.CANARY.V1VSV2", "T3",
                     "kind 6 v2 catches %d sabotages that v1 is BIT-IDENTICAL under (%s) "
                     "-- a clean run and a stubbed mechanism produced the same v1 dump"
                     % (len(blind), ",".join(blind)),
                     len(blind) >= 1 and all(
                         sum(1 for x, y in zip(Workspace(breaks=[b]).canary_v2(), base_v2)
                             if x != y) > 0 for b in blind))

        # the Python side's own sabotages of the buffer model
        for b in ([] if self.coverage else sorted(WORKSPACE_BREAKS)):
            try:
                bad, _, _ = python_records([b])
            except Exception as exc:
                self.rec("T2.WORKSPACE.SABOTAGE.%s" % b, "T2",
                         "Workspace sabotage %-15s changes a graded record" % b, False, str(exc))
                continue
            moved = [n for n in sorted(REC) if bad[n][1] != recs[n][1]]
            self.rec("T2.WORKSPACE.SABOTAGE.%s" % b, "T2",
                     "Workspace sabotage %-15s moves %s" % (b, ",".join(moved) or "NOTHING"),
                     bool(moved))

        # palette self-test, tick self-test, wrap and stick, in their own
        # constructions
        pok, pmsg = fb_pal.selftest()
        self.rec("T2.PAL.SELFTEST", "T2", "fb_pal.py self-test (%d checks)" % len(pmsg), pok)
        if not pok:
            for m in pmsg:
                if m.startswith("  FAIL"):
                    self.say("      " + m)
        with self.hush():
            trc = fb_tick.main(["--wrap-sweep"] + sum((["--break", b] for b in self.mut()
                                                       if b in fb_tick.BREAKS), []))
        self.rec("T2.TICK.ARITH", "T2",
                 "fb_tick.py arithmetic, the K6 rate probe and the 1.5M-case wrap sweep",
                 trc == 0)
        wok, wmsg, wstats = fb_wrap.run([b for b in self.mut() if b in fb_wrap.BREAKS])
        self.rec("T2.WRAP.CLASSA", "T2",
                 "fb_wrap.py class-A arithmetic, containment and the reachability census "
                 "over the two CENSUSED callers' parsed domains (%d checks)" % len(wmsg), wok)
        for m in wmsg:
            if m.startswith("  PASS  W4") or m.startswith("  PASS  W5") or self.verbose or not wok:
                self.say("      " + m.strip())
        return True

    # -- tier 2b: the sabotages of the C reference -----------------------

    def tier2_sabotage(self):
        if self.mutation:
            return True          # coverage mode does not rebuild the C
        print("\nTier 2 -- every single-edit sabotage of fb_ref.c must be REJECTED")
        base = {n: os.path.join(OUT, REC[n][0]) for n in REC}
        self.cmatrix = {}
        allok = True
        for define, desc, target in C_BREAKS:
            exe = os.path.join(HERE, "fb_brk.exe")
            odir = os.path.join(OUT, "brk")
            bok, log = self.build_c(exe, [define])
            if not bok:
                allok &= bool(self.rec("T2.CSABOTAGE.%s" % define, "T2",
                                       "sabotage %-22s builds" % define, False, log[:200]))
                continue
            rc, out = self.run_c(exe, odir)
            moved = []
            for n in sorted(REC):
                p = os.path.join(odir, REC[n][0])
                if not os.path.exists(p):
                    moved.append(n + "(missing)")
                    continue
                good, _ = compare_dumps(base[n], p)
                if not good:
                    moved.append(n)
            if rc != 0:
                moved.append("selftest")
            caught = bool(moved)
            hit_target = target in moved
            self.cmatrix[define] = moved
            allok &= bool(self.rec(
                "T2.CSABOTAGE.%s" % define, "T2",
                "sabotage %-22s caught by %s" % (define, ",".join(moved) or "NOTHING"),
                caught and hit_target,
                "expected %s to move; it did not" % target if caught else "caught NOTHING"))
            if self.verbose:
                print("      %s" % desc)
        return allok

    # -- tier 1: the 1996 artifacts --------------------------------------

    def tier1_capture(self):
        print("\nTier 1 -- against artifacts this project did not make")
        bmps = sorted(f for f in os.listdir(CAPS) if f.lower().endswith(".bmp")) if os.path.isdir(CAPS) else []
        pngs = sorted(f for f in os.listdir(CAPS) if f.lower().endswith(".raw1.png")) if os.path.isdir(CAPS) else []
        # ONE row here, not two.  The pair used to read
        #     if not bmps and not pngs: rec(..., False)
        #     rec("capture artifacts present (...)", True)
        # -- the second call passed the literal `True`, so on the only path that
        # reached it the answer was already known.  The first line is the check;
        # the second was a print statement being counted as evidence.
        self.rec("T1.CAPTURE.PRESENT", "T1",
                 "capture artifacts present in %s (%d BMP, %d raw PNG)"
                 % (CAPS, len(bmps), len(pngs)), bool(bmps or pngs), "none found")
        if not bmps and not pngs:
            return False

        loaded = {}
        for f in bmps + pngs:
            path = os.path.join(CAPS, f)
            loaded[f] = fb_bmp.load_any(path)

        # aggregated over EVERY capture, so a second artifact cannot dilute the
        # verdict and every file is still named in the message
        ba = {f: fb_bmp.scale_audit(loaded[f][2]) for f in bmps}
        self.rec("T1.BMP.SCALE", "T1",
                 "all %d snapshot BMP(s): DAC scaling is x4, not shift-or (%s)"
                 % (len(bmps), "; ".join("%s mod4 %s max %d"
                                         % (f, ba[f]["mod4_histogram"], ba[f]["max"])
                                         for f in bmps)),
                 bool(bmps) and all(ba[f]["consistent_with_x4"]
                                    and not ba[f]["consistent_with_shift_or"] for f in bmps))
        pa_ = {f: fb_bmp.scale_audit(loaded[f][2]) for f in pngs}
        self.rec("T1.PNG.SCALE", "T1",
                 "all %d DOSBox raw PNG(s) write shift-or, so the two capture routes need "
                 "DIFFERENT inverses (%s)" % (len(pngs), ", ".join(pngs)),
                 bool(pngs) and all(pa_[f]["consistent_with_shift_or"]
                                    and not pa_[f]["consistent_with_x4"] for f in pngs))

        if bmps and pngs:
            a6 = loaded[bmps[0]][1]
            b6 = loaded[pngs[0]][1]
            d = [i for i in range(768) if a6[i] != b6[i]]
            raw = [i for i in range(768) if loaded[bmps[0]][2][i] != loaded[pngs[0]][2][i]]
            self.rec("T1.CAPTURE.AGREE", "T1",
                     "snapshot BMP and DOSBox PNG agree on all 768 6-bit DAC components "
                     "(raw 8-bit bytes differ in %d)" % len(raw), not d, "%d differ" % len(d))

        fits = {f: fb_pal.tier1_palette_audit(loaded[f][1]) for f in bmps}
        self.rec("T1.PAL.FIT", "T1",
                 "all %d BMP(s): band 0-63 is range8088 filtered by v*f/63 exactly (%s)"
                 % (len(bmps), "; ".join("%s f=(%s,%s,%s)" % (f, fits[f]["R"], fits[f]["G"],
                                                              fits[f]["B"]) for f in bmps)),
                 bool(bmps) and all(all(fits[f][c] for c in "RGB") for f in bmps))
        self.rec("T1.PAL.NOROUND", "T1",
                 "falsifier round-to-nearest fits NO capture (%s)"
                 % ("; ".join("%s:%s" % (f, fits[f]["_round_to_nearest_fits"] or "none")
                              for f in bmps)),
                 bool(bmps) and not any(fits[f]["_round_to_nearest_fits"] for f in bmps))
        self.rec("T1.PAL.NODIV64", "T1",
                 "falsifier /64 fits NO capture (%s)"
                 % ("; ".join("%s:%s" % (f, fits[f]["_div64_fits"] or "none") for f in bmps)),
                 bool(bmps) and not any(fits[f]["_div64_fits"] for f in bmps))

        self.rec("T1.PNG.DOUBLING", "T1",
                 "all %d raw PNG(s): 2x2 doubling verified (%s non-uniform subpixels)"
                 % (len(pngs), ",".join(str(loaded[f][3]["nonuniform_subpixels"]) for f in pngs)),
                 bool(pngs) and all(loaded[f][3]["nonuniform_subpixels"] == 0 for f in pngs))

        if len(bmps) >= 2:
            a, b = loaded[bmps[0]][0], loaded[bmps[1]][0]
            npx = sum(1 for i in range(len(a)) if a[i] != b[i])
            pa, pb = loaded[bmps[0]][1], loaded[bmps[1]][1]
            npal = sum(1 for i in range(768) if pa[i] != pb[i])
            self.rec("T1.CAPTURE.PALSTABLE", "T1",
                     "two unpinned snapshots differ in %d/64000 pixels but %d/768 palette "
                     "components -- the palette is the stable object" % (npx, npal), npal == 0)
        return True

    # -- tier 3: the tick and the servo ----------------------------------

    def tier3_tick(self):
        self.say("\nTier 3 -- tick, recomputed from raw TICKLOGs")
        cpms = 9000
        exact = float(fb_tick.PERIOD_MS) * cpms
        work = [int(exact * 0.04)] * 400
        work[100] = int(exact * 1.4)
        work[250] = int(exact * 2.6)
        longwork = [int(exact * 0.04)] * 20000
        specs = [("clean", (), work)] + [(b, (b,), work) for b in ("REBASE", "NOSKIP", "ROUND55")]
        specs.append(("NOCARRY", ("NOCARRY",), longwork))
        results = {}
        for name, brk, work_ in specs:
            pay = fb_tick.run_loop(cpms, work_, brk)
            path = os.path.join(OUT, "tick-%s.bin" % name)
            fb_tick.write_ticklog(path, pay, cpms, len(pay) // 3)
            results[name] = fb_tick.grade_ticklog(path)
        ok0, msg0, st0 = results["clean"]
        # WAVE 5c: NOT GRADED.  This is fb_tick's own simulator feeding
        # fb_tick's own grader -- one owner on both sides.  It passes for any
        # pair of them that agree with each other, including a pair that agree
        # about the wrong thing, so it carries no evidence about any port.  It
        # was being counted as a T3 pass.  The SOUND instance is the lino
        # TICKLOG row in `lino()`, which grades a log this project did not
        # generate.
        self.rec("T3.TICK.SELFGRADE", "T3",
                 "fb_tick's simulator, graded by fb_tick (drift %.5f ms over %d grid steps, "
                 "verdict %s)" % (st0["drift_ms"], st0["grid_steps"], "clean" if ok0 else "FAILS"),
                 None,
                 "GRADER SELF-TEST -- carries no evidence about any port.  Kept because a "
                 "grader that rejects its own producer is worth knowing about; no longer "
                 "counted as a pass.")
        if self.verbose or not ok0:
            for m in msg0:
                self.say("      " + m)

        # the row that DOES grade something: one log, four header rates, and
        # exactly one of them may pass.  K6.
        probe = fb_tick.rate_probe()
        self.rec("T3.TICK.RATEPROBE", "T3",
                 "K6: one 9000-cpms log stamped with headers %s -- exactly the TRUE one "
                 "passes (%s).  Before K6 all four passed, i.e. the grader never read the "
                 "header at all, and a port whose clock ran 10%% fast shipped green."
                 % ([h for h, _o, _f in probe],
                    ", ".join("%d:%s" % (h, "PASS" if o else "FAIL " + ",".join(f))
                              for h, o, f in probe)),
                 [h for h, o, _f in probe if o] == [9000])

        if self.coverage:
            return ok0
        shortpay = fb_tick.run_loop(cpms, work, ("NOCARRY",))
        sp = os.path.join(OUT, "tick-NOCARRY-400.bin")
        fb_tick.write_ticklog(sp, shortpay, cpms, len(shortpay) // 3)
        sok, _, sst = fb_tick.grade_ticklog(sp)
        self.rec("T3.TICK.NOCARRY400", "T3",
                 "NOCARRY is caught in a 400-tick log too (%.1f counts adrift)"
                 % sst["drift_worst_segment_counts"], not sok)
        servo = fb_tick.run_loop(cpms, work, servo={256: cpms + 1})
        svp = os.path.join(OUT, "tick-SERVO1.bin")
        fb_tick.write_ticklog(svp, servo, cpms + 1, len(servo) // 3)
        vok, _, vst = fb_tick.grade_ticklog(svp)
        self.rec("T3.TICK.SERVOSTEP", "T3", "a legitimate 1-count servo step is ACCEPTED (%s)"
                 % "->".join(str(s["cpms"]) for s in vst["segments"]), vok)
        wild = fb_tick.run_loop(cpms, work, servo={256: int(cpms * 1.05)})
        wp = os.path.join(OUT, "tick-SERVOWILD.bin")
        fb_tick.write_ticklog(wp, wild, cpms, len(wild) // 3)
        wok, wmsg, _ = fb_tick.grade_ticklog(wp)
        which = [m.split()[1] for m in wmsg if m.startswith("  FAIL")]
        self.rec("T3.TICK.SERVOWILD", "T3", "a 5%% cpms lurch is REJECTED (by %s)"
                 % (",".join(which) or "-"), not wok)
        for name, _, _ in specs[1:]:
            ok, msg, _ = results[name]
            which = [m.split()[1] for m in msg if m.startswith("  FAIL")]
            self.rec("T3.TICK.SABOTAGE.%s" % name, "T3",
                     "tick sabotage %-8s rejected (by %s)" % (name, ",".join(which) or "-"),
                     not ok)
        return ok0

    def tier3_servo(self):
        self.say("\nTier 3 -- the SERVO (CRITICAL 1), windowed and re-based-first")
        args = ["--servo"] + sum((["--break", b] for b in self.mut()
                                  if b in fb_tick.BREAKS), [])
        with self.hush():
            rc = fb_tick.main(args)
        self.rec("T3.SERVO.BATTERY", "T3",
                 "fb_tick.py windowed-servo battery T8a..T8i (estimator seeded 4%% LOW)",
                 rc == 0)
        # The one PIN in the ledger, exercised as a row so gate 3 has something
        # to measure.  T8d is the same function with a flag flipped -- but the
        # EXPECTED PAIR is independent arithmetic on an input constructed so
        # that rounding and truncation differ by exactly one cpms.  No mutation
        # in the set moves it, and if one ever does, it was not a pin.
        ms, cnt = 14061, 8999 * 14061 + 7031
        sr = fb_tick.Servo(8999, self.mut())
        sr.start(0, 0)
        c_round, _ = sr.fire(1, cnt, ms)
        st = fb_tick.Servo(8999, set(self.mut()) | {"SRVTRUNC"})
        st.start(0, 0)
        c_trunc, _ = st.fire(1, cnt, ms)
        self.rec("T3.SERVO.T8D.ROUNDING", "T3",
                 "PIN: ms=%d cnt=%d -> rounded %d, truncated %d, exactly one cpms apart"
                 % (ms, cnt, c_round, c_trunc), c_round == 9000 and c_trunc == 8999,
                 "declared a PIN in the ledger: an arithmetic identity no mutation in the "
                 "set can move.  Gate 3 FAILS if one ever does.")
        for b in ([] if self.coverage else ("SRVRUNSTART", "SRVWIDEMAX", "SRVUNSIGNEDBAND",
                                            "SRVTRUNC", "SRVCLAMPFLOOR", "WALLNOFOLD",
                                            "DONOTHING", "NOREBASE")):
            with self.hush():
                rc = fb_tick.main(["--servo", "--break", b])
            self.rec("T3.SERVO.SABOTAGE.%s" % b, "T3",
                     "servo sabotage %-16s is rejected" % b, rc != 0)
        return True

    def tier3_classA(self):
        self.say("\nTier 3 -- class A (CRITICAL 2): the mask, and the two verdicts")
        for b in ([] if self.coverage else sorted(fb_wrap.BREAKS)):
            rc = fb_wrap.run([b])[0]
            self.rec("T3.CLASSA.SABOTAGE.%s" % b, "T3",
                     "class-A sabotage %-16s is rejected" % b, not rc)
        with self.hush():
            rc = fb_stick.main(["--quick", "--quiet"])
        self.rec("T3.STICK.A1", "T3", "fb_stick.py A1 bbox proof (poly3d clamp, swept)", rc == 0)
        with self.hush():
            rc = 1 if self.coverage else fb_stick.main(["--quick", "--quiet",
                                                        "--break", "CLIPSTAGE"])
        if not self.coverage:
            self.rec("T3.STICK.CLIPSTAGE", "T3", "A1 sabotage CLIPSTAGE is rejected", rc != 0)
        if not self.fast and not self.coverage:
            with self.hush():
                rc = fb_stick.main(["--quiet"])
            self.rec("T3.STICK.A2CORPUS", "T3",
                     "fb_stick.py A2 escape corpus (400k deterministic cases)", rc == 0)
        else:
            self.rec("T3.STICK.A2CORPUS", "T3", "fb_stick.py A2 escape corpus", None,
                     "--fast / coverage mode: skipped")
        return True

    # -- the pinned fixture, as a BUILD IDENTITY ---------------------------

    def scenario_doc(self):
        self.say("\nTier 3 -- the pinned fixture (docs-notes/FIXTURE1.txt), by HASH")
        digest, note = fixture_identity()
        if digest is None:
            self.rec("T3.FIXTURE.IDENTITY", "T3",
                     "every producer compiled against the SAME pinned stimulus", None, note)
            return None
        # every producer must carry the hash it compiled against, in KSELF
        # fields 80..87 -- eight words, the first 32 hex digits of the SHA-256.
        carried = {}
        for label, path in (("C", "fb-ref-kself.bin"), ("py", "fb-py-kself.bin")):
            p = os.path.join(OUT, path)
            if not os.path.exists(p):
                continue
            pay = fbdump_read(p)["payload"]
            f = {pay[i]: pay[i + 1] for i in range(0, len(pay) - 1, 2)}
            if all(KSELF_FIXTURE_HASH + i in f for i in range(8)):
                carried[label] = "".join("%08x" % f[KSELF_FIXTURE_HASH + i] for i in range(8))
            else:
                carried[label] = None
        want = digest[:64]
        self.rec("T3.FIXTURE.IDENTITY", "T3",
                 "every producer compiled against docs-notes/FIXTURE1.txt, sha256 %s... "
                 "(%d byte(s); KSELF %d..%d carries %s)"
                 % (digest[:24], os.path.getsize(FIXTURE_FILE), KSELF_FIXTURE_HASH,
                    KSELF_FIXTURE_HASH + 7,
                    {k: (v[:16] + "..." if v else None) for k, v in sorted(carried.items())}),
                 bool(carried) and all(v == want for v in carried.values()),
                 "a producer that did not rebuild against the CURRENT fixture fails here, "
                 "and that is the whole content of the check: it grades a build identity, "
                 "not a wording.  It replaces the LINOBUF 6.1 marker row, whose verdict "
                 "was decided by a heading number.")
        if KSELF_NOT_COMPARABLE:
            self.say("      KSELF ids in the normative range that are NOT compared, and why:")
            for k, why in sorted(KSELF_NOT_COMPARABLE.items()):
                for i, chunk in enumerate(_wrap(why, 62)):
                    self.say("        %-4s %s" % (k if i == 0 else "", chunk))
        return True

    # -- the lino side ---------------------------------------------------

    def lino(self):
        print("\nTier 2 -- the lino framebuffer (implementer 1)")
        if not self.linosrc:
            self.say("      OUTSTANDING: no --lino path given.  The lino side has not")
            self.say("      been graded.  Every reference above stands on its own; nothing")
            self.say("      here should be read as evidence about the lino build.")
            return None
        if not os.path.exists(self.linosrc):
            self.rec("T2", "lino dump %s exists" % self.linosrc, False)
            return False

        recs = read_container(self.linosrc)
        vers = sorted(set(r["version"] for r in recs))
        print("      %s: %d FBDUMP records, version(s) %s, %s"
              % (os.path.basename(self.linosrc), len(recs), vers,
                 ", ".join("%s x%d" % (KIND_NAME.get(k, "kind%d" % k), v)
                           for k, v in sorted(collections.Counter(r["kind"] for r in recs).items()))))
        self.rec("T2.LINO.V2", "T2", "lino dump is FBDUMP v2 (version(s) %s)" % vers,
                 1 not in vers,
                 "v1 record(s) present.  v1 has no tag and pins no scenario, so kinds "
                 "1/2/3 in it CANNOT be graded.")

        # -- THE TAG REGRESSION DETECTOR, 1.6 item 6 ------------------------
        #
        # w5probe.bin announces v2 and ships every record with tag = 0.  The old
        # guard was `if 1 in vers`, which this stream passes, so grading went
        # ahead and produced eleven `FAIL ... missing` rows -- each of which
        # named the wrong cause.  A v2 stream in which NO record carries a
        # non-zero tag is MALFORMED: the version word must not promise what the
        # payload does not carry.
        v2recs = [r for r in recs if r["version"] >= 2]
        tagged = [r for r in v2recs if r["tag"]]
        tags_ok = not v2recs or bool(tagged)
        self.rec("T2.LINO.TAGSPRESENT", "T2",
                 "the v2 stream carries tags: %d of %d v2 record(s) have a non-zero tag"
                 % (len(tagged), len(v2recs)), tags_ok,
                 "MALFORMED v2 STREAM.  Every tag-keyed row below is NOT GRADED, and the "
                 "reason is this, not `missing`.  The producing fix is in "
                 "tests/w5probe.txt, which is outside both implementers' namespaces -- "
                 "FLAGGED TO THE COORDINATOR.")

        by_tag = collections.defaultdict(list)
        by_kind = collections.defaultdict(list)
        for r in recs:
            by_kind[r["kind"]].append(r)
            if r["version"] >= 2 and r["tag"]:
                by_tag[TAG_NAME.get(r["tag"], "tag%d" % r["tag"])].append(r)

        allok = True
        self.clean_lino_verdicts = {}
        # every v2 record with a known tag is graded against BOTH references
        for name in sorted(REC):
            cid = "T2.LINO.REC.%s" % name.upper()
            tagname = REC[name][2]
            if not by_tag.get(tagname):
                self.rec(cid, "T2", "lino %-9s (tag %s)" % (name.upper(), tagname), None,
                         "no record carries this tag -- and the stream is a MALFORMED v2 "
                         "(no tags at all), so this is NOT GRADED, not a failure of the "
                         "record" if not tags_ok else "no v2 record carries this tag")
                self.clean_lino_verdicts[name] = None
                continue
            lp = os.path.join(OUT, "fb-lino-%s.bin" % name)
            write_record(lp, by_tag[tagname][0])
            gc, lc = compare_dumps(lp, os.path.join(OUT, REC[name][0]), "lino", "C")
            gp, lpn = compare_dumps(lp, os.path.join(OUT, "fb-py-%s.bin" % name), "lino", "py")
            if name in ("adapted", "adaptor", "glyph", "kself"):
                # 3.1: w5probe's fixture and fb_ref.c's fixture are DIFFERENT
                # SCENARIOS.  Printing that as a red row is a category error.
                self.rec("T2.LINO.ADAPTED.CROSSFIXTURE" if name == "adapted" else cid,
                         "T2", "lino %-9s vs the references" % name.upper(), None,
                         "NOT GRADED: the lino build and fb_ref.c ran DIFFERENT FIXTURES, "
                         "each internally correct.  No document reconciles them, so no "
                         "oracle exists for this record; %d unit(s) differ and the number "
                         "means nothing until docs-notes/FIXTURE1.txt exists and both "
                         "producers re-derive from it."
                         % (0 if gc else len([1 for l in lc if l.strip().startswith("unit")])))
                self.clean_lino_verdicts[name] = None
                continue
            v = gc and gp
            self.clean_lino_verdicts[name] = v
            allok &= bool(self.rec(cid, "T2",
                                   "lino %-9s == fb_ref.c AND == the Python reference"
                                   % name.upper(), v))
            for l in (lc if not gc else []) + (lpn if not gp else []):
                print(l)

        # TICKLOG and SERVOLOG are scenario-free
        if by_kind[KIND_TICKLOG]:
            lp = os.path.join(OUT, "fb-lino-ticklog.bin")
            write_record(lp, by_kind[KIND_TICKLOG][0])
            ok, msg, stats = fb_tick.grade_ticklog(lp)
            self.clean_lino_verdicts["ticklog"] = ok
            allok &= bool(self.rec("T2.LINO.TICKLOG", "T2",
                                   "lino TICKLOG passes K1..K6 (%d ticks, %d grid steps, "
                                   "worst in-run drift %.4f counts, header %d cpms)"
                                   % (stats["ticks"], stats["grid_steps"],
                                      stats["drift_worst_segment_counts"], stats["cpms"]), ok))
            for m in msg:
                if m.startswith("  FAIL") or self.verbose:
                    print("      " + m)
        else:
            allok &= bool(self.rec("T2.LINO.TICKLOG", "T2", "lino TICKLOG record present",
                                   False, "missing"))

        if by_kind[KIND_SERVOLOG]:
            pay = by_kind[KIND_SERVOLOG][0]["payload"]
            ok, msg, st = fb_tick.grade_servolog(pay, by_kind[KIND_SERVOLOG][0]["cpms"])
            allok &= bool(self.rec("T2.LINO.SERVOLOG", "T2",
                                   "lino SERVOLOG passes S1..S6 (%d firings, why %s).  "
                                   "grade_servolog is BLIND to a do-nothing estimator by "
                                   "construction -- see fb_tick T8i" % (st["firings"], st["why"]),
                                   ok))
            for m in msg:
                if m.startswith("  FAIL"):
                    print("      " + m)
        else:
            self.rec("T2.LINO.SERVOLOG", "T2", "lino SERVOLOG (kind 11) present", None,
                     "missing.  CRITICAL 1 shipped precisely because SERVON > the soak's "
                     "tick count, so the servo never executed.  Without this record the "
                     "servo is not graded at all.")

        if by_kind[KIND_KFRM]:
            print("      KFRM (kind 8): %d record(s), %d units -- raw timing, UNGRADED BY "
                  "NATURE, reported not compared"
                  % (len(by_kind[KIND_KFRM]), by_kind[KIND_KFRM][0]["count"]))

        if self.linobreaks:
            allok &= bool(self.lino_break_matrix(recs))

        extra = sorted(k for k in by_kind if k not in KIND_NAME)
        if extra:
            print("      lino emits kind(s) %s, which FBDUMP v2 does not define." % extra)
            print("      KIND and TAG are SEPARATE namespaces.  KINDS run 1..11 (1 "
                  "INDEXPAGE, 2 PALETTE6, 3 LUT, 4 TICKLOG, 5 LAYOUT, 6 CANARY, 7 KSELF, "
                  "8 KFRM, 9 ZONES, 10 WRAPCOUNT, 11 SERVOLOG); TAGS run 1..14 and 12 is "
                  "`wrapcount`.  A record carrying the wrap counters is kind 10, tag 12. "
                  "This is the most likely interop break between the two implementers.")
            for k in extra:
                print("        kind %d: %d record(s), %d units, tag %s, first units %s"
                      % (k, len(by_kind[k]), by_kind[k][0]["count"],
                         by_kind[k][0]["tag"], by_kind[k][0]["payload"][:6]))
        return allok

    # -- the rebuilt sabotage matrix (plan 1.6) ---------------------------
    #
    # WHAT WAS THERE, and why it had to go rather than be reworded.
    #
    # The old criterion was "does this sabotage's record differ from
    # fbout/fb-ref-*.bin".  The CLEAN lino build already differs from those
    # references -- it ran a different fixture -- so every one of the 19 rows
    # read identically whether the sabotage was caught or not, and feeding the
    # matrix the CLEAN DUMP produced `CAUGHT`.  A criterion that reports a
    # correct build as a caught sabotage has no specificity, and a criterion
    # whose output does not depend on its input has no sensitivity.  There was
    # nothing in it to keep.
    #
    # The replacement, in the plan's order:
    #   1  PRECONDITION GATE.  Compute the clean build's verdict set FIRST.  Any
    #      record the clean build fails is excluded from grading for every row,
    #      and the exclusion is printed by name.
    #   2  DIFFERENTIAL CRITERION.  CAUGHT iff a record the CLEAN build PASSES
    #      is failed by the sabotage.  A catcher set equal to the clean build's
    #      failure set is by definition not a catch.
    #   3  `moved` is promoted to a first-class signal: sabotage-vs-CLEAN-LINO
    #      needs no external oracle and is the soundest thing here.
    #   4  TICKLOG leaves the payload-equality matrix -- it is raw timing, and
    #      it moved in all 23 builds including against the clean run.  It is
    #      graded by K1..K6 only.
    #   5  THE NULL-INPUT ROW is mandatory: the clean dump, fed in as a
    #      sabotage, must read NOT CAUGHT.

    def lino_break_matrix(self, clean):
        print("\n      implementer 1's sabotaged builds, through this grader:")
        # Key by (kind, tag, ORDINAL).  Keying by (kind, tag) alone made the
        # clean container "move" against ITSELF: w5probe ships three PALETTE6
        # records all carrying tag 0, so every one after the first was compared
        # to the first and reported as different.  The null-input row then
        # never fired, which is precisely the row that exists to catch this
        # class of mistake -- so it caught one on its first run.
        def keyed(recs):
            out, seen = {}, {}
            for r in recs:
                k = (r["kind"], r["tag"])
                i = seen.get(k, 0)
                seen[k] = i + 1
                out[(r["kind"], r["tag"], i)] = r
            return out

        cleanby = keyed(clean)

        # -- 1: the precondition gate --------------------------------------
        gradeable = sorted(n for n, v in self.clean_lino_verdicts.items() if v is True)
        excluded = sorted(n for n, v in self.clean_lino_verdicts.items() if v is not True)
        print("      PRECONDITION GATE: the clean lino build PASSES %s" % (gradeable or "NOTHING"))
        print("      EXCLUDED from grading for every row below, by name: %s"
              % (", ".join("%s(%s)" % (n, "FAILS" if self.clean_lino_verdicts[n] is False
                                       else "NOT GRADED") for n in excluded) or "none"))
        # If the clean build passes nothing BECAUSE its own stream is malformed
        # or ran another fixture, that is not a verdict this row can reach: the
        # defect is named by T2.LINO.TAGSPRESENT and by the cross-fixture rows,
        # and repeating it here as a second red row would double-count one
        # cause.  A well-formed, same-fixture clean build that still fails
        # records IS this row's business, and then it is a FAIL.
        blocked = any(v is None for v in self.clean_lino_verdicts.values())
        self.rec("T2.LINO.MATRIX.GATE", "T2",
                 "the sabotage matrix grades only the %d record(s) the CLEAN build passes"
                 % len(gradeable), (None if (not gradeable and blocked) else bool(gradeable)),
                 "the clean build passes NO record this grader has an oracle for, so EVERY "
                 "row in this matrix is NOT GRADED.  There is no oracle for a sabotage to "
                 "be graded against.  ONE defect -- the two fixtures, plus a v2 stream "
                 "with no tags -- not nineteen, and it is counted once, above.")

        rows = []
        for path in self.linobreaks:
            name = os.path.splitext(os.path.basename(path))[0]
            try:
                recs = read_container(path)
            except SystemExit as exc:
                rows.append((name, "MALFORMED", str(exc), [], []))
                continue
            # -- 3: moved against the CLEAN LINO, which needs no oracle
            moved = []
            for k, r in sorted(keyed(recs).items()):
                if r["kind"] == KIND_TICKLOG:
                    continue                       # -- 4: raw timing, never here
                peer = cleanby.get(k)
                if peer is None:
                    moved.append("%s(new)" % KIND_NAME.get(r["kind"], r["kind"]))
                elif r["payload"] != peer["payload"]:
                    moved.append(TAG_NAME.get(r["tag"]) or "%s#%d"
                                 % (KIND_NAME.get(r["kind"], r["kind"]), k[2]))
            # -- 2: judged ONLY on records the clean build passes
            judged = []
            for r in recs:
                if not (r["tag"] and TAG_NAME.get(r["tag"]) in [REC[n][2] for n in REC]):
                    continue
                nm = [n for n in REC if REC[n][2] == TAG_NAME.get(r["tag"])][0]
                if nm not in gradeable:
                    continue
                lp = os.path.join(OUT, "brk", "%s-%s.bin" % (name, nm))
                os.makedirs(os.path.dirname(lp), exist_ok=True)
                write_record(lp, r)
                g, _ = compare_dumps(lp, os.path.join(OUT, REC[nm][0]))
                if not g:
                    judged.append(nm)
            rows.append((name, None, None, judged, sorted(set(moved))))

        # -- 5: the mandatory null-input row -------------------------------
        nullname = None
        for name, bad, _why, judged, moved in rows:
            if bad is None and not moved:
                nullname = name
                break
        null_rows = [r for r in rows if r[0] == nullname] if nullname else []
        if null_rows:
            n, _b, _w, judged, moved = null_rows[0]
            self.rec("T2.LINO.MATRIX.NULL", "T2",
                     "NULL INPUT: %s moves nothing against the clean build and is judged "
                     "CAUGHT by %s" % (n, judged or "NOTHING"), not judged,
                     "A grading matrix that reports a NOT-sabotaged input as CAUGHT has no "
                     "specificity.  This row is the whole of recon A 2.1.")
        else:
            self.rec("T2.LINO.MATRIX.NULL", "T2",
                     "NULL INPUT: a clean dump fed in as a sabotage must read NOT CAUGHT",
                     None,
                     "no null input was supplied.  Pass the clean dump in --lino-break as "
                     "well; without it the matrix's specificity is untested and this row "
                     "is NOT GRADED rather than assumed.")

        allok = True
        caught = notcaught = ungraded = 0
        for name, bad, why, judged, moved in rows:
            if name == nullname:
                continue
            if bad:
                print("        %-11s MALFORMED container: %s" % (name, why))
                continue
            if not gradeable:
                print("        %-11s NOT GRADED -- moves %s against the clean lino build, but "
                      "the precondition gate excluded every record"
                      % (name, ",".join(moved) or "NOTHING"))
                ungraded += 1
            elif judged:
                print("        %-11s CAUGHT by %s (records the clean build PASSES)"
                      % (name, ",".join(sorted(set(judged)))))
                caught += 1
            elif moved:
                print("        %-11s NOT CAUGHT -- it moves %s against the clean lino build, "
                      "so this grader has a BLIND SPOT there" % (name, ",".join(moved)))
                notcaught += 1
            else:
                print("        %-11s NOT CAUGHT -- moves NOTHING in any record" % name)
                notcaught += 1
        allok &= bool(self.rec(
            "T2.LINO.MATRIX.ROW", "T2",
            "sabotage matrix over %d build(s): %d CAUGHT, %d NOT CAUGHT, %d NOT GRADED"
            % (len(rows) - (1 if nullname else 0), caught, notcaught, ungraded),
            None if ungraded else (notcaught == 0),
            "NOT GRADED, with the reason printed above verbatim: the clean build fails "
            "every record this grader has a reference for, so no sabotage can be graded "
            "against one.  The closure criterion is FALSIFICATION, not agreement -- a "
            "lino sabotage must make a record FAIL while the clean build PASSES.  w5s21 "
            "(alias 8 relocated to 64000) is the first witness; until that demonstration "
            "exists this is NOT GRADED, not Tier 2."))
        print("      A 'NOT CAUGHT' row is a limit of THIS grader, never a pass for the build.")
        return allok

    # -- the report ------------------------------------------------------

    def run(self, meta=True):
        os.makedirs(OUT, exist_ok=True)
        lok, lmsg = fb_ledger.validate()
        self.say("fb_compare.py -- Wave 5c grader   (FBDUMP v%d, ledger %d entries)"
                 % (FBD_VERSION, len(fb_ledger.LEDGER)))
        self.say("  references : fb_ref.c (C); fb_layout.py / fb_pal.py / fb_tick.py /")
        self.say("               fb_wrap.py / fb_stick.py (Python)")
        self.say("  captures   : %s" % CAPS)
        self.say("  lino       : %s" % (self.linosrc or "NOT SUPPLIED -- lino side outstanding"))
        if self.mutation:
            self.say("  MUTATION   : %s   (coverage mode)" % ",".join(sorted(self.mutation)))
        if not lok:
            for m in lmsg:
                print(m)
            raise SystemExit("fb_ledger did not validate; refusing to grade")
        self.tier3_layout()
        self.tier2_c_vs_py()
        self.tier2_sabotage()
        self.tier1_capture()
        self.tier3_tick()
        self.tier3_servo()
        self.tier3_classA()
        self.scenario_doc()
        linoresult = self.lino()
        if meta and not self.mutation:
            self.meta_gates()

        npass = sum(1 for r in self.rows if r[3] is True)
        nfail = sum(1 for r in self.rows if r[3] is False)
        nng = sum(1 for r in self.rows if r[3] is None)
        if self.quiet:
            return 0 if nfail == 0 else 1
        print("\n" + "=" * 78)
        for tier in ("T0", "T1", "T2", "T3", "META"):
            rows = [r for r in self.rows if r[1] == tier]
            if not rows:
                continue
            print("  %-4s %d checks, %d failed, %d NOT GRADED"
                  % (tier, len(rows), sum(1 for r in rows if r[3] is False),
                     sum(1 for r in rows if r[3] is None)))
        print("  TOTAL %d checks, %d passed, %d failed, %d NOT GRADED"
              % (len(self.rows), npass, nfail, nng))
        unrun = sorted(set(fb_ledger.LEDGER) - self.seen)
        if unrun:
            print("  LEDGER  %d entr(ies) declared but not exercised in this run: %s"
                  % (len(unrun), ", ".join(unrun[:6]) + (" ..." if len(unrun) > 6 else "")))
        if nng:
            print("\n  NOT GRADED rows, in full -- with the reason, verbatim:")
            for r in self.rows:
                if r[3] is None:
                    print("    - [%s] %s" % (r[0], r[2]))
                    if r[4]:
                        print("      %s" % r[4])
        print("\n  TIER PER ELEMENT.  EVIDENCE tier (1 strongest, 0 = asserted) / producers")
        print("  (a COUNT, not a tier) / falsifiers DEMONSTRATED, generated from the ledger:")
        for elem, tier, nprod, cids, note in TIER_TABLE:
            fals = sorted(set(sum((list(fb_ledger.LEDGER[c].falsifier)
                                   for c in cids if c in fb_ledger.LEDGER), [])))
            print("    %-36s ev%-4s prod %d  falsifiers %d %s"
                  % (elem, tier, nprod, len(fals),
                     "(%s)" % ",".join(fals[:3]) + ("..." if len(fals) > 3 else "") if fals else ""))
            if note:
                for chunk in _wrap(note, 68):
                    print("        %s" % chunk)
        print("\n  What this harness cannot grade at all (run --ungraded for detail):")
        for title, status, _why in UNGRADED:
            print("    %-38s %s" % (title, status))
        if linoresult is None:
            print("\n  LINO SIDE: OUTSTANDING -- not present, not graded, not claimed.")
        print("  RESULT: %s" % ("PASS" if nfail == 0 else "FAIL"))
        print("=" * 78)
        return 0 if nfail == 0 else 1

    def meta_gates(self):
        """The three gates and the lint, run as suite rows.  Imported late so
        fb_mutcov can drive `Suite` without a circular import."""
        self.say("\nMETA -- the falsification ledger's own gates")
        import fb_lint
        import fb_mutcov
        lok, ldet = fb_lint.run_corpus()
        self.rec("META.LINT", "META",
                 "fb_lint catches all %d deliberately void snippets in fbout/lintcorpus "
                 "and clears the %d sound ones" % (ldet["void_total"], ldet["clean_total"]),
                 lok, ldet["summary"])
        cov = fb_mutcov.run(quiet=not self.verbose)
        self.rec("META.MUTCOV.SENSITIVITY", "META",
                 "GATE 1 sensitivity: every GRADED cid is measurably broken by every "
                 "falsifier it declares (%d cid(s) measured, %d gap(s))"
                 % (cov["measured"], len(cov["sensitivity_gaps"])),
                 not cov["sensitivity_gaps"],
                 "; ".join("%s not broken by %s" % (c, ",".join(f))
                           for c, f in cov["sensitivity_gaps"][:6]))
        self.rec("META.MUTCOV.SPECIFICITY", "META",
                 "GATE 2 specificity: every cid PASSES on a non-mutated input (%d row(s) "
                 "checked, %d that do not)" % (cov["clean_rows"], len(cov["specificity_gaps"])),
                 not cov["specificity_gaps"], ", ".join(cov["specificity_gaps"][:8]))
        self.rec("META.MUTCOV.PINS", "META",
                 "GATE 3 pin integrity: every PIN cid measures an EMPTY falsifier set "
                 "(%d pin(s), %d that became falsifiable)"
                 % (cov["pins"], len(cov["pin_gaps"])),
                 not cov["pin_gaps"], ", ".join(cov["pin_gaps"][:8]))


def _wrap(text, width):
    out, line = [], ""
    for w in text.split():
        if len(line) + len(w) + 1 > width:
            out.append(line)
            line = w
        else:
            line = (line + " " + w).strip()
    if line:
        out.append(line)
    return out


def print_ungraded():
    print("What this harness does NOT grade, stated rather than pretended")
    print("=" * 78)
    for title, status, why in UNGRADED:
        print("\n%s   [%s]" % (title, status))
        for line in why.split("  "):
            if line.strip():
                print("  " + line.strip())
    print("\n" + "=" * 78)
    print("Everything else in the six defects reaches two independent implementations")
    print("plus a caught sabotage.  Run `fb_compare.py --suite` for the matrix.")


def print_scenario_spec():
    digest, note = fixture_identity()
    if digest:
        print("docs-notes/FIXTURE1.txt  sha256 %s" % digest)
        print("=" * 78)
        with open(FIXTURE_FILE, "r", encoding="utf-8", errors="replace") as fh:
            print(fh.read())
        return 0
    print("THE PINNED FIXTURE -- NOT ON DISK")
    print("=" * 78)
    print(note)
    print()
    text, _err = linobuf_section("the pinned page fixture")
    if text:
        print("LINOBUF's normative prose for it, located by ANCHOR LINE (never by a")
        print("heading number -- the old check scanned for the string \"6.1\" and its")
        print("verdict changed when an unrelated heading took the number):")
        print(text)
        print()
    print("This file may not carry its own copy of the normative scenario -- that is")
    print("exactly the defect that made kinds 1/2/3 ungradeable in Wave 5, where the")
    print("reference invented a scenario after the fact and never handed it to")
    print("implementer 1.  What follows is NOT a spec.  It is a report of what")
    print("implementer 2's two independent references ACTUALLY RAN, generated from")
    print("the code, so the architect can lift the numbers into LINOBUF 6.1 and so")
    print("implementer 1 is not blocked.")
    print()
    print("SCENARIO \"surface\"  (fb_pal.py scenario_surface, fb_ref.c scenario_surface)")
    for lbl, why in fb_pal.SURFACE_STEPS:
        print("  %-58s  %s" % (lbl, why))
    p = fb_pal.scenario_surface()
    print("  -> uploads %s" % (p.uploads,))
    print("  -> fnv pal6 %08X curpal6 %08X lut %08X"
          % (fnv1a32(p.pal6), fnv1a32(p.curpal6), fnv1a32(p.lut())))
    print()
    print("SCENARIO \"page\"  (fb_layout.Workspace.scenario_page, fb_ref.c scenario_page)")
    lay = Layout()
    for line in [
        "  1  pads in the RELEASE state (zero)",
        "  2  QUADWORDS = %d ; pclear(adaptor, 0)" % lay.qw_declared,
        "     QUADWORDS = %d ; pclear(adapted, 7)   <- DERIVED from `QUADWORDS -= 1440`"
        % lay.qw_steady,
        "  3  Borland LCG srand(1996): n_globes_map[i] = rand()&63 for i<32768;",
        "     s_background[i] = 128 + (rand()&63) for i<4096",
        "  4  sea texture i<32000: u=(i*517)&0xFFFF, v=(i*1031)&0xFFFF,",
        "     texel = ((v>>8)&0xFF)*256 + ((u>>8)&0xFF), adapted[i] = NW[globes+texel]",
        "  5  digit_at('A', colour 104, shader 1), txtr = p_surfacemap, LOOP FROM n = 0;",
        "     then adapted[32000+i] = NW[p_surfacemap-5+i] for i<9216",
        "  6  alias 8 through seg_index(adapted, 0x%04X) -> adapted[%d] = row %d col %d"
        % (lay.alias8_segoff, lay.alias8()["index"], lay.alias8()["row"], lay.alias8()["col"]),
        "  7  the class-A wrap battery (spot and cirrus, masked at the truncation point)",
        "  8  QUADWORDS = %d ; pcopy(adaptor, adapted)      <- CORRECTION 5: flip BEFORE"
        % lay.qw_declared,
        "  9  areaclear(adaptor, x=2, y=191, w=316, h=7, colour=127)",
    ]:
        print(line)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("pair", nargs="*", help="two FBDUMP files to compare")
    ap.add_argument("--suite", action="store_true")
    ap.add_argument("--lino", metavar="PATH",
                    help="implementer 1's FBDUMP: a multi-record .bin, or a directory of them")
    ap.add_argument("--scenario-spec", action="store_true",
                    help="print the pinned fixture from the doc, or say why it cannot")
    ap.add_argument("--ledger", action="store_true", help="the falsification ledger")
    ap.add_argument("--no-meta", action="store_true",
                    help="skip the three ledger gates and the lint (they are suite rows)")
    ap.add_argument("--ungraded", action="store_true",
                    help="what this harness cannot grade, and why")
    ap.add_argument("--lino-break", metavar="PATH", action="append", default=[],
                    help="a deliberately broken lino FBDUMP; repeatable, globs accepted")
    ap.add_argument("--fast", action="store_true", help="skip the slowest corpora")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    if args.ledger:
        return fb_ledger.main()
    if args.ungraded:
        print_ungraded()
        return 0
    if args.scenario_spec:
        return print_scenario_spec()
    if args.suite:
        brk = []
        for pat in args.lino_break:
            hits = sorted(glob.glob(pat))
            brk += hits if hits else [pat]
        return Suite(args.lino, args.verbose, brk, args.fast).run(meta=not args.no_meta)
    if len(args.pair) == 2:
        ok, lines = compare_dumps(args.pair[0], args.pair[1],
                                  os.path.basename(args.pair[0]), os.path.basename(args.pair[1]))
        print("\n".join(lines))
        return 0 if ok else 1
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
