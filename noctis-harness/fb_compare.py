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
import os
import struct
import subprocess
import sys

from fb_layout import (Layout, Workspace, fbdump_read, fbdump_write, layout_payload,
                       zones_payload, fnv1a32, KIND_NAME, TAG_NAME, TAG, KSELF_FIELD,
                       KIND_INDEXPAGE, KIND_PALETTE6, KIND_LUT, KIND_TICKLOG,
                       KIND_LAYOUT, KIND_CANARY, KIND_KSELF, KIND_KFRM, KIND_ZONES,
                       KIND_WRAPCOUNT, KIND_SERVOLOG, FBD_VERSION,
                       LAYOUT_BREAKS, WORKSPACE_BREAKS)
import fb_pal
import fb_tick
import fb_bmp
import fb_wrap
import fb_stick

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fbout")
CAPS = os.path.abspath(os.path.join(HERE, "..", "tests", "gen", "recon_w5c", "artifacts"))
SUPPORTS = r"C:\programmieren\noctis\niv-plus\data\SUPPORTS.NCT"
LINOBUF = os.path.abspath(os.path.join(HERE, "..", "docs-notes", "LINOBUF.md"))

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
    ("farmalloc offset == 4", "TIER 0",
     "Four independent source-level witnesses -- Stick/Segmento's `es:[di+4]`, "
     "sc_bytes = 65540, wave()'s `add ax,4`, and polymap's es:[0xFA00] into a "
     "65540-byte page -- which is documentary corroboration, not measurement.  "
     "Alias 8's PLACEMENT arithmetic reaches Tier 2 (fb_layout.py parses the asm "
     "literal, fb_ref.c transcribes it, they agree); its PREMISE does not.  "
     "Decisive experiment: DOSBox-X + NOCTIS.SYM, read adapted's offset word "
     "after init_FP_segments (rig at tests/gen/recon_w5c/hostshot4.ps1)."),
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
    ("LINOBUF 6.1 as a DOCUMENT", "SEE THE RUN",
     "The scenario is normative in LINOBUF 6.1, which the architect owns.  This "
     "harness checks whether that section exists and whether its numbers match "
     "what the two references actually ran; if the section is absent the check "
     "reports NOT GRADED rather than passing."),
]

# Per-element tier statement.  LINOBUF 7's blanket "Tier 2, lino vs C, byte
# exact on every FBDUMP kind" was true of the container and false of the
# content; this table says which is which, element by element.
TIER_TABLE = [
    ("palette filter arithmetic", "TIER 2", "C + Python, 7 caught sabotages, and TIER 1 "
                                            "against the 1996 BMP"),
    ("shade chop-vs-round", "TIER 2", "separated at the first entry of step 3"),
    ("upload-from-zero", "TIER 2", "trace digests; the FINAL state does not separate it"),
    ("the self-copy", "TIER 2", "separated by step 7, NOT by step 4 -- measured"),
    ("v*4 vs shift-or", "TIER 1", "768/768 BMP bytes = 0 mod 4, max 252; shift-or falsified"),
    ("shade's destination buffer", "TIER 2", "21 sites counted from source, SH-COMPOUND caught"),
    ("alias 8 placement", "TIER 2", "parsed vs transcribed, agree on adapted[63996]"),
    ("alias 8 PREMISE (offset==4)", "TIER 0", "four witnesses, zero measurements"),
    ("the raster loop (digit_at n=0)", "TIER 2", "glyph plane AND the 6 SUB expectation hits"),
    ("the 22-zone pad model", "TIER 2", "zones record + two-sided walk, 3 caught sabotages"),
    ("the canary", "TIER 2", "4 caught sabotages, proved by disabling"),
    ("class-A masks", "TIER 2", "4 caught sabotages; reachability EXHAUSTIVE over the domain"),
    ("A1 Segmento", "PROVEN", "unnecessary: poly3d's clamp, swept"),
    ("A3 mask_pixels", "PROVEN", "unnecessary: DI 2884..61123 at the steady QUADWORDS"),
    ("A7 ptr", "PROVEN", "a typing requirement, not a mask"),
    ("A2 Stick riga[] INDEX", "TIER 2", "reached; 400k-case corpus, mechanism identified"),
    ("A2 Stick riga[] VALUES", "DIVERG.", "deliberate, named retirement condition"),
    ("the tick period", "TIER 2", "C + Python + 1.5M-case wrap sweep"),
    ("the servo", "TIER 3", "6 caught sabotages; the shipped bracket replayed and refuted"),
    ("kinds 1/2/3 CONTENT", "TIER 2", "pinned scenario, C vs Python, exact"),
    ("kinds 1/2/3 vs a FRAME", "SCOPED OUT", "no renderer exists"),
    ("KFRM (kind 8)", "UNGRADED", "raw timing, by nature"),
]

# The scenario constants LINOBUF 6.1 must carry if it is to pin what the two
# references implemented.  Checked against the doc, not against each other.
SCENARIO_MARKERS = [
    "range8088", "16", "32", "63",          # step 2
    "0.984375",                              # step 3's delta, the chop/round split
    "192", "50",                             # step 4
    "64", "60", "55",                        # step 5
    "160", "19.5", "24.75", "66.25",         # step 6
    "200",                                   # step 7, the signed-char filter
    "14560", "63996", "1996", "517", "1031",  # page scenario
]


def read_linobuf_61():
    """LINOBUF 6.1 is the architect's, and this file may not carry a copy of it.
    Read it off disk; if it is not there, say so."""
    if not os.path.exists(LINOBUF):
        return None, "LINOBUF.md not found at %s" % LINOBUF
    with open(LINOBUF, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    lines = text.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if ln.strip().lower().startswith("### 6.1") or \
           ("6.1" in ln and "PINNED SCENARIO" in ln.upper()):
            start = i
            break
    if start is None:
        return None, ("LINOBUF.md has no section 6.1.  The pinned scenario is the "
                      "architect's deliverable and it is not on disk yet.")
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("## ") or (lines[j].startswith("### ") and j > start):
            end = j
            break
    return "\n".join(lines[start:end]), None


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


def diff_payload(a, b):
    n = min(len(a), len(b))
    return [i for i in range(n) if a[i] != b[i]] + \
           ([len(a)] if len(a) != len(b) else [])


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
        da = {a[i]: tuple(a[i + 1:i + 2]) for i in range(0, len(a) - 1, 2)}
        db = {b[i]: tuple(b[i + 1:i + 2]) for i in range(0, len(b) - 1, 2)}
        normative = lambda k: 1 <= k < 100
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


def python_records(breaks=()):
    """Build every record from the Python references, independently of the C."""
    lb = [b for b in breaks if b in LAYOUT_BREAKS]
    lay = Layout(lb)
    w = Workspace(lay, breaks=breaks)
    w.scenario_page()
    p = fb_pal.scenario_surface([b for b in breaks if b in fb_pal.BREAKS])
    pc, want, ladder = fb_pal.scenario_compound([b for b in breaks if b in fb_pal.BREAKS])
    probe_viol, probe_exp, _ = w.pad_probe_expectation()
    extra = {
        4: probe_viol, 5: probe_exp,
        15: p.curpal6_trace_fnv(),
        16: sum(1 for v in ladder if v),
        20: sum(1 for i in range(11) if w.canary_v2()[4 * i + 2] == 0),
        21: fnv1a32(pc.pal6),
        22: p.pal6_trace_fnv(),
        23: p.upload_spans_fnv(),
    }
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
    def __init__(self, linosrc=None, verbose=False, linobreaks=(), fast=False):
        self.linosrc = linosrc
        self.linobreaks = list(linobreaks)
        self.verbose = verbose
        self.fast = fast
        self.rows = []       # (tier, name, ok|None, detail)

    def rec(self, tier, name, ok, detail=""):
        self.rows.append((tier, name, ok, detail))
        tagtxt = "PASS" if ok is True else ("FAIL" if ok is False else "NOT GRADED")
        print("  [%s] %-62s %s%s" % (tier, name, tagtxt,
                                     ("  " + detail) if detail and ok is not True else ""))
        return ok

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
        print("\nTier 3 -- layout by construction (fb_layout.py parses the 1996 sources)")
        lay = Layout()
        ok, msg = lay.check()
        self.rec("T3", "fb_layout.py structural assertions (%d checks)" % len(msg), ok)
        if self.verbose or not ok:
            for m in msg:
                if not ok or self.verbose:
                    print("      " + m)
        for b in LAYOUT_BREAKS:
            bad, _ = Layout([b]).check()
            self.rec("T3", "layout sabotage %-14s is rejected" % b, not bad)
        return ok

    # -- tier 2: three-way agreement -------------------------------------

    def tier2_c_vs_py(self):
        print("\nTier 2 -- fb_ref.c vs the Python references (independent constructions)")
        ok, log = self.build_c(os.path.join(HERE, "fb_ref.exe"))
        if not self.rec("T2", "fb_ref.c builds clean with -Wall -Wextra", ok and "warning" not in log,
                        log[:300]):
            return False
        rc, out = self.run_c(os.path.join(HERE, "fb_ref.exe"), OUT)
        self.rec("T2", "fb_ref.exe self-test passes", rc == 0,
                 "\n".join(l for l in out.splitlines() if "FAIL" in l))
        if self.verbose:
            print(out)

        recs, w, p = python_records()
        write_python_records(recs)
        for name in sorted(REC):
            fn = REC[name][0]
            good, lines = compare_dumps(os.path.join(OUT, "fb-py-%s.bin" % name),
                                        os.path.join(OUT, fn), "py", "C")
            self.rec("T2", "%-9s : Python == fb_ref.c, exact" % name.upper(), good)
            for l in lines:
                if not good or self.verbose:
                    print(l)

        # the two independent derivations of alias 8
        a8 = Layout().alias8()
        kself = {}
        pay = fbdump_read(os.path.join(OUT, "fb-ref-kself.bin"))["payload"]
        for i in range(0, len(pay), 2):
            kself[pay[i]] = pay[i + 1]
        self.rec("T2", "alias 8: fb_layout.py PARSES `mov es:[0x%04X]` out of TDPOLYGS.H, "
                       "fb_ref.c TRANSCRIBES it; both give adapted[%d] = row %d col %d"
                 % (a8["segoff"], a8["index"], a8["row"], a8["col"]),
                 (kself.get(7), kself.get(8), kself.get(9)) == (a8["nw"], a8["row"], a8["col"]))
        self.rec("T0", "...but alias 8's PREMISE (farmalloc offset == 4) is Tier 0: four "
                       "source-level witnesses, zero measurements", None,
                 "see --ungraded item 1")

        # the raster loop, visible in two independent places
        census, padhits = w.overrun_census()
        self.rec("T3", "sea texture actually overruns n_globes_map: %d of 32000 texels land "
                       "past its end, so farmalloc order is under test" % census, census > 0)
        self.rec("T3", "the 16-unit pad IS reachable by the texel address (%d of those %d), "
                       "so grading runs must use the release pad state" % (padhits, census),
                 padhits > 0)
        pv, pe, _ = w.pad_probe_expectation()
        self.rec("T3", "the raster loop is visible in TWO places: the 256x36 glyph plane, and "
                       "EXACTLY %d expectation hits in p_surfacemap's SUB zone" % pe,
                 (pv, pe) == (0, 6))
        vio, _, first = w.pad_probe_violation()
        self.rec("T3", "and a real overrun is a VIOLATION, not an expectation: 1 unit past "
                       "n_globes_map fires once, at NW %s, in pad %s TAIL"
                 % (first, vio[0][1] if vio else "-"),
                 len(vio) == 1 and vio[0][2] == "TAIL")

        # MAJOR 5, demonstrated rather than argued: v1's kind 6 is BLIND to the
        # very sabotages v2 catches.  Both records are computed from the same
        # workspace under the same sabotage, so this is a like-for-like
        # comparison of the two record designs.
        print("      canary v1 vs v2, proof by disabling (same workspace, same sabotage):")
        base_v1 = Workspace().canary_v1()
        base_v2 = Workspace().canary_v2()
        blind = []
        for b in ("CANSTUBCHECK", "CANSTUBPOISON", "CANCONSTACTUAL", "NINEWALK"):
            ww = Workspace(breaks=[b])
            v1 = ww.canary_v1()
            ww2 = Workspace(breaks=[b])
            v2 = ww2.canary_v2()
            d1 = sum(1 for x, y in zip(v1, base_v1) if x != y)
            d2 = sum(1 for x, y in zip(v2, base_v2) if x != y)
            print("        %-15s v1 fnv %08X (%2d units differ)   v2 fnv %08X (%2d units differ)"
                  % (b, fnv1a32(v1), d1, fnv1a32(v2), d2))
            if d1 == 0:
                blind.append(b)
        self.rec("T3", "kind 6 v2 catches %d sabotages that v1 is BIT-IDENTICAL under (%s) "
                       "-- a clean run and a stubbed mechanism produced the same v1 dump"
                 % (len(blind), ",".join(blind)),
                 len(blind) >= 1 and all(
                     sum(1 for x, y in zip(Workspace(breaks=[b]).canary_v2(), base_v2)
                         if x != y) > 0 for b in blind))

        # the Python side's own sabotages of the buffer model
        for b in sorted(WORKSPACE_BREAKS):
            try:
                bad, _, _ = python_records([b])
            except Exception as exc:
                self.rec("T2", "Workspace sabotage %-15s changes a graded record" % b, False, str(exc))
                continue
            moved = [n for n in sorted(REC)
                     if bad[n][1] != recs[n][1]]
            self.rec("T2", "Workspace sabotage %-15s moves %s"
                     % (b, ",".join(moved) or "NOTHING"), bool(moved))

        # palette self-test, tick self-test, wrap and stick, in their own
        # constructions
        pok, pmsg = fb_pal.selftest()
        self.rec("T2", "fb_pal.py self-test (%d checks)" % len(pmsg), pok)
        if not pok:
            for m in pmsg:
                if m.startswith("  FAIL"):
                    print("      " + m)
        self.rec("T2", "fb_tick.py arithmetic + 1.5M-case wrap sweep",
                 fb_tick.main(["--wrap-sweep"]) == 0)
        wok, wmsg, wstats = fb_wrap.run()
        self.rec("T2", "fb_wrap.py class-A arithmetic, containment and the exhaustive "
                       "reachability census (%d checks)" % len(wmsg), wok)
        for m in wmsg:
            if m.startswith("  PASS  W4") or m.startswith("  PASS  W5") or self.verbose or not wok:
                print("      " + m.strip())
        return True

    # -- tier 2b: the sabotages of the C reference -----------------------

    def tier2_sabotage(self):
        print("\nTier 2 -- every single-edit sabotage of fb_ref.c must be REJECTED")
        base = {n: os.path.join(OUT, REC[n][0]) for n in REC}
        allok = True
        for define, desc, target in C_BREAKS:
            exe = os.path.join(HERE, "fb_brk.exe")
            odir = os.path.join(OUT, "brk")
            bok, log = self.build_c(exe, [define])
            if not bok:
                allok &= bool(self.rec("T2", "sabotage %-22s builds" % define, False, log[:200]))
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
            allok &= bool(self.rec(
                "T2", "sabotage %-22s caught by %s" % (define, ",".join(moved) or "NOTHING"),
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
        if not bmps and not pngs:
            return self.rec("T1", "capture artifacts present in %s" % CAPS, False, "none found")
        self.rec("T1", "capture artifacts present (%d BMP, %d raw PNG)" % (len(bmps), len(pngs)), True)

        loaded = {}
        for f in bmps + pngs:
            path = os.path.join(CAPS, f)
            try:
                loaded[f] = fb_bmp.load_any(path)
            except Exception as exc:
                self.rec("T1", "decode %s" % f, False, str(exc))

        for f in bmps:
            a = fb_bmp.scale_audit(loaded[f][2])
            self.rec("T1", "%s: DAC scaling is x4, not shift-or (mod4 %s, max %d)"
                     % (f, a["mod4_histogram"], a["max"]),
                     a["consistent_with_x4"] and not a["consistent_with_shift_or"])
        for f in pngs:
            a = fb_bmp.scale_audit(loaded[f][2])
            self.rec("T1", "%s: DOSBox writes shift-or, so the two routes need different inverses" % f,
                     a["consistent_with_shift_or"] and not a["consistent_with_x4"])

        if bmps and pngs:
            a6 = loaded[bmps[0]][1]
            b6 = loaded[pngs[0]][1]
            d = [i for i in range(768) if a6[i] != b6[i]]
            raw = [i for i in range(768) if loaded[bmps[0]][2][i] != loaded[pngs[0]][2][i]]
            self.rec("T1", "snapshot BMP and DOSBox PNG agree on all 768 6-bit DAC "
                           "components (raw 8-bit bytes differ in %d)" % len(raw), not d,
                     "%d differ" % len(d))

        for f in bmps:
            fit = fb_pal.tier1_palette_audit(loaded[f][1])
            got = all(fit[c] for c in "RGB")
            self.rec("T1", "%s: band 0-63 is range8088 filtered by v*f/63 exactly, "
                           "f = (%s,%s,%s)" % (f, fit["R"], fit["G"], fit["B"]), got)
            self.rec("T1", "%s: falsifier round-to-nearest fits nothing (%s)"
                     % (f, fit["_round_to_nearest_fits"] or "none"), not fit["_round_to_nearest_fits"])
            self.rec("T1", "%s: falsifier /64 fits nothing (%s)"
                     % (f, fit["_div64_fits"] or "none"), not fit["_div64_fits"])

        for f in pngs:
            self.rec("T1", "%s: 2x2 doubling verified, %d non-uniform subpixels"
                     % (f, loaded[f][3]["nonuniform_subpixels"]),
                     loaded[f][3]["nonuniform_subpixels"] == 0)

        if len(bmps) >= 2:
            a, b = loaded[bmps[0]][0], loaded[bmps[1]][0]
            npx = sum(1 for i in range(len(a)) if a[i] != b[i])
            pa, pb = loaded[bmps[0]][1], loaded[bmps[1]][1]
            npal = sum(1 for i in range(768) if pa[i] != pb[i])
            self.rec("T1", "two unpinned snapshots differ in %d/64000 pixels but %d/768 "
                           "palette components -- the palette is the stable object" % (npx, npal),
                     npal == 0)
        return True

    # -- tier 3: the tick and the servo ----------------------------------

    def tier3_tick(self):
        print("\nTier 3 -- tick, recomputed from raw TICKLOGs")
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
        self.rec("T3", "clean tick loop passes K1..K5 (drift %.5f ms over %d grid steps)"
                 % (st0["drift_ms"], st0["grid_steps"]), ok0)
        if self.verbose or not ok0:
            for m in msg0:
                print("      " + m)
        shortpay = fb_tick.run_loop(cpms, work, ("NOCARRY",))
        sp = os.path.join(OUT, "tick-NOCARRY-400.bin")
        fb_tick.write_ticklog(sp, shortpay, cpms, len(shortpay) // 3)
        sok, _, sst = fb_tick.grade_ticklog(sp)
        self.rec("T3", "NOCARRY is caught in a 400-tick log too (%.1f counts adrift)"
                 % sst["drift_worst_segment_counts"], not sok)
        servo = fb_tick.run_loop(cpms, work, servo={256: cpms + 1})
        svp = os.path.join(OUT, "tick-SERVO1.bin")
        fb_tick.write_ticklog(svp, servo, cpms + 1, len(servo) // 3)
        vok, _, vst = fb_tick.grade_ticklog(svp)
        self.rec("T3", "a legitimate 1-count servo step is ACCEPTED (%s)"
                 % "->".join(str(s["cpms"]) for s in vst["segments"]), vok)
        wild = fb_tick.run_loop(cpms, work, servo={256: int(cpms * 1.05)})
        wp = os.path.join(OUT, "tick-SERVOWILD.bin")
        fb_tick.write_ticklog(wp, wild, cpms, len(wild) // 3)
        wok, wmsg, _ = fb_tick.grade_ticklog(wp)
        which = [m.split()[1] for m in wmsg if m.startswith("  FAIL")]
        self.rec("T3", "a 5%% cpms lurch is REJECTED (by %s)" % (",".join(which) or "-"), not wok)
        for name, _, _ in specs[1:]:
            ok, msg, _ = results[name]
            which = [m.split()[1] for m in msg if m.startswith("  FAIL")]
            self.rec("T3", "tick sabotage %-8s rejected (by %s)" % (name, ",".join(which) or "-"),
                     not ok)
        return ok0

    def tier3_servo(self):
        print("\nTier 3 -- the SERVO (CRITICAL 1), windowed and re-based-first")
        rc = fb_tick.main(["--servo"])
        self.rec("T3", "fb_tick.py windowed-servo battery T8a..T8h", rc == 0)
        for b in ("SRVRUNSTART", "SRVWIDEMAX", "SRVUNSIGNEDBAND", "SRVTRUNC",
                  "SRVCLAMPFLOOR", "WALLNOFOLD"):
            rc = fb_tick.main(["--servo", "--break", b])
            self.rec("T3", "servo sabotage %-16s is rejected" % b, rc != 0)
        return True

    def tier3_classA(self):
        print("\nTier 3 -- class A (CRITICAL 2): the mask, and the two verdicts")
        for b in sorted(fb_wrap.BREAKS):
            rc = fb_wrap.run([b])[0]
            self.rec("T3", "class-A sabotage %-16s is rejected" % b, not rc)
        rc = fb_stick.main(["--quick", "--quiet"])
        self.rec("T3", "fb_stick.py A1 bbox proof (poly3d clamp, swept)", rc == 0)
        rc = fb_stick.main(["--quick", "--quiet", "--break", "CLIPSTAGE"])
        self.rec("T3", "A1 sabotage CLIPSTAGE is rejected", rc != 0)
        if not self.fast:
            rc = fb_stick.main(["--quiet"])
            self.rec("T3", "fb_stick.py A2 escape corpus (400k deterministic cases)", rc == 0)
        else:
            self.rec("T3", "fb_stick.py A2 escape corpus", None, "--fast: skipped")
        return True

    # -- LINOBUF 6.1 conformance ------------------------------------------

    def scenario_doc(self):
        print("\nTier 3 -- the pinned scenario as a DOCUMENT (LINOBUF 6.1)")
        text, err = read_linobuf_61()
        if text is None:
            self.rec("T3", "LINOBUF 6.1 exists and pins the scenario", None,
                     err + "  Until it lands, the two references agree with each "
                           "other but nothing pins them to a document implementer 1 can read.")
            return None
        missing = [m for m in SCENARIO_MARKERS if m not in text]
        self.rec("T3", "LINOBUF 6.1 carries every scenario constant the references ran "
                       "(%d markers, %d missing)" % (len(SCENARIO_MARKERS), len(missing)),
                 not missing, ",".join(missing[:8]))
        return not missing

    # -- the lino side ---------------------------------------------------

    def lino(self):
        print("\nTier 2 -- the lino framebuffer (implementer 1)")
        if not self.linosrc:
            print("      OUTSTANDING: no --lino path given.  The lino side has not")
            print("      been graded.  Every reference above stands on its own; nothing")
            print("      here should be read as evidence about the lino build.")
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
        if 1 in vers:
            self.rec("T2", "lino dump is FBDUMP v2", False,
                     "v1 record(s) present.  v1 has no tag and pins no scenario, so "
                     "kinds 1/2/3 in it CANNOT be graded -- that is the defect v2 exists "
                     "to fix, not a property of the build.")

        by_tag = collections.defaultdict(list)
        by_kind = collections.defaultdict(list)
        for r in recs:
            by_kind[r["kind"]].append(r)
            if r["version"] >= 2 and r["tag"]:
                by_tag[TAG_NAME.get(r["tag"], "tag%d" % r["tag"])].append(r)

        allok = True
        # every v2 record with a known tag is graded against BOTH references
        for name in sorted(REC):
            tagname = REC[name][2]
            if not by_tag.get(tagname):
                if 2 in vers:
                    allok &= bool(self.rec("T2", "lino %-9s (tag %s) present" % (name.upper(), tagname),
                                           False, "missing"))
                else:
                    self.rec("T2", "lino %-9s (tag %s)" % (name.upper(), tagname), None,
                             "no v2 record carries this tag")
                continue
            lp = os.path.join(OUT, "fb-lino-%s.bin" % name)
            write_record(lp, by_tag[tagname][0])
            gc, lc = compare_dumps(lp, os.path.join(OUT, REC[name][0]), "lino", "C")
            gp, lpn = compare_dumps(lp, os.path.join(OUT, "fb-py-%s.bin" % name), "lino", "py")
            allok &= bool(self.rec("T2", "lino %-9s == fb_ref.c AND == the Python reference"
                                   % name.upper(), gc and gp))
            for l in (lc if not gc else []) + (lpn if not gp else []):
                print(l)

        # TICKLOG and SERVOLOG are scenario-free
        if by_kind[KIND_TICKLOG]:
            lp = os.path.join(OUT, "fb-lino-ticklog.bin")
            write_record(lp, by_kind[KIND_TICKLOG][0])
            ok, msg, stats = fb_tick.grade_ticklog(lp)
            allok &= bool(self.rec("T2", "lino TICKLOG passes K1..K5 (%d ticks, %d grid steps, "
                                         "worst in-run drift %.4f counts)"
                                   % (stats["ticks"], stats["grid_steps"],
                                      stats["drift_worst_segment_counts"]), ok))
            for m in msg:
                if m.startswith("  FAIL") or self.verbose:
                    print("      " + m)
        else:
            allok &= bool(self.rec("T2", "lino TICKLOG record present", False, "missing"))

        if by_kind[KIND_SERVOLOG]:
            pay = by_kind[KIND_SERVOLOG][0]["payload"]
            ok, msg, st = fb_tick.grade_servolog(pay, by_kind[KIND_SERVOLOG][0]["cpms"])
            allok &= bool(self.rec("T2", "lino SERVOLOG passes S1..S6 (%d firings, why %s)"
                                   % (st["firings"], st["why"]), ok))
            for m in msg:
                if m.startswith("  FAIL"):
                    print("      " + m)
        else:
            self.rec("T2", "lino SERVOLOG (kind 11) present", None,
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
            self.rec("T2", "lino emits kind(s) %s, which FBDUMP v2 does not define" % extra,
                     None,
                     "KIND and TAG are SEPARATE namespaces and the plan's two lists "
                     "read as if they were one.  KINDS run 1..11 (1 INDEXPAGE, 2 "
                     "PALETTE6, 3 LUT, 4 TICKLOG, 5 LAYOUT, 6 CANARY, 7 KSELF, 8 KFRM, "
                     "9 ZONES, 10 WRAPCOUNT, 11 SERVOLOG); TAGS run 1..14 and 12 is "
                     "`wrapcount`.  A record carrying the wrap counters is kind 10, "
                     "tag 12.  This is the single most likely interop break between the "
                     "two implementers and it needs one line in LINOBUF 6.")
            for k in extra:
                print("        kind %d: %d record(s), %d units, tag %s, first units %s"
                      % (k, len(by_kind[k]), by_kind[k][0]["count"],
                         by_kind[k][0]["tag"], by_kind[k][0]["payload"][:6]))
        return allok

    def lino_break_matrix(self, clean):
        print("\n      implementer 1's sabotaged builds, through this grader:")
        cleanby = collections.defaultdict(list)
        for r in clean:
            key = (r["kind"], r["tag"])
            cleanby[key].append(r)
        allok = True
        for path in self.linobreaks:
            name = os.path.splitext(os.path.basename(path))[0]
            try:
                recs = read_container(path)
            except SystemExit as exc:
                self.rec("T2", "lino sabotage %-11s rejected (container: %s)" % (name, exc), True)
                continue
            moved = []
            for r in recs:
                key = (r["kind"], r["tag"])
                peers = cleanby.get(key, [])
                if not peers:
                    moved.append("%s(new)" % KIND_NAME.get(r["kind"], r["kind"]))
                    continue
                if r["payload"] != peers[0]["payload"]:
                    moved.append(TAG_NAME.get(r["tag"]) or KIND_NAME.get(r["kind"], r["kind"]))
            # and the records this grader can judge on its own terms
            judged = []
            for r in recs:
                if r["tag"] and TAG_NAME.get(r["tag"]) in [REC[n][2] for n in REC]:
                    nm = [n for n in REC if REC[n][2] == TAG_NAME.get(r["tag"])][0]
                    lp = os.path.join(OUT, "brk", "%s-%s.bin" % (name, nm))
                    os.makedirs(os.path.dirname(lp), exist_ok=True)
                    write_record(lp, r)
                    g, _ = compare_dumps(lp, os.path.join(OUT, REC[nm][0]))
                    if not g:
                        judged.append(nm)
                if r["kind"] == KIND_TICKLOG:
                    lp = os.path.join(OUT, "brk", "%s-ticklog.bin" % name)
                    os.makedirs(os.path.dirname(lp), exist_ok=True)
                    write_record(lp, r)
                    ok, msg, _ = fb_tick.grade_ticklog(lp)
                    if not ok:
                        judged.append("TICKLOG(%s)" % ",".join(m.split()[1] for m in msg
                                                               if m.startswith("  FAIL")))
            if judged:
                self.rec("T2", "lino sabotage %-11s CAUGHT by %s" % (name, ",".join(sorted(set(judged)))),
                         True)
            elif moved:
                allok &= bool(self.rec(
                    "T2", "lino sabotage %-11s moves %s but this grader has no reference "
                          "for it" % (name, ",".join(sorted(set(moved)))), False, "blind spot"))
            else:
                allok &= bool(self.rec(
                    "T2", "lino sabotage %-11s moves NOTHING in any FBDUMP v2 record"
                          % name, False, "not caught"))
        print("      A 'not caught' row is a limit of THIS grader, never a pass for the build.")
        return allok

    # -- the report ------------------------------------------------------

    def run(self):
        os.makedirs(OUT, exist_ok=True)
        print("fb_compare.py -- Wave 5-corrective grader   (FBDUMP v%d)" % FBD_VERSION)
        print("  references : fb_ref.c (C); fb_layout.py / fb_pal.py / fb_tick.py /")
        print("               fb_wrap.py / fb_stick.py (Python)")
        print("  captures   : %s" % CAPS)
        print("  lino       : %s" % (self.linosrc or "NOT SUPPLIED -- lino side outstanding"))
        self.tier3_layout()
        self.tier2_c_vs_py()
        self.tier2_sabotage()
        self.tier1_capture()
        self.tier3_tick()
        self.tier3_servo()
        self.tier3_classA()
        self.scenario_doc()
        linoresult = self.lino()

        npass = sum(1 for r in self.rows if r[2] is True)
        nfail = sum(1 for r in self.rows if r[2] is False)
        nng = sum(1 for r in self.rows if r[2] is None)
        print("\n" + "=" * 78)
        for tier in ("T0", "T1", "T2", "T3"):
            rows = [r for r in self.rows if r[0] == tier]
            if not rows:
                continue
            print("  %s  %d checks, %d failed, %d NOT GRADED"
                  % (tier, len(rows), sum(1 for r in rows if r[2] is False),
                     sum(1 for r in rows if r[2] is None)))
        print("  TOTAL %d checks, %d passed, %d failed, %d NOT GRADED"
              % (len(self.rows), npass, nfail, nng))
        if nng:
            print("\n  NOT GRADED rows, in full:")
            for r in self.rows:
                if r[2] is None:
                    print("    - %s" % r[1])
                    if r[3]:
                        print("      %s" % r[3])
        print("\n  TIER PER ELEMENT -- replacing the blanket claim:")
        for elem, tier, note in TIER_TABLE:
            print("    %-34s %-7s %s" % (elem, tier, note))
        print("\n  What this harness cannot grade at all (run --ungraded for detail):")
        for title, status, _why in UNGRADED:
            print("    %-38s %s" % (title, status))
        if linoresult is None:
            print("\n  LINO SIDE: OUTSTANDING -- not present, not graded, not claimed.")
        print("  RESULT: %s" % ("PASS" if nfail == 0 else "FAIL"))
        print("=" * 78)
        return 0 if nfail == 0 else 1


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
    text, err = read_linobuf_61()
    if text:
        print(text)
        return 0
    print("LINOBUF 6.1 -- NOT ON DISK")
    print("=" * 78)
    print(err)
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
                    help="print LINOBUF 6.1 from the doc, or say why it cannot")
    ap.add_argument("--ungraded", action="store_true",
                    help="what this harness cannot grade, and why")
    ap.add_argument("--lino-break", metavar="PATH", action="append", default=[],
                    help="a deliberately broken lino FBDUMP; repeatable, globs accepted")
    ap.add_argument("--fast", action="store_true", help="skip the slowest corpora")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

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
        return Suite(args.lino, args.verbose, brk, args.fast).run()
    if len(args.pair) == 2:
        ok, lines = compare_dumps(args.pair[0], args.pair[1],
                                  os.path.basename(args.pair[0]), os.path.basename(args.pair[1]))
        print("\n".join(lines))
        return 0 if ok else 1
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
