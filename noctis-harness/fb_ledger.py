#!/usr/bin/env python3
"""fb_ledger.py -- Wave 5c.  The falsification ledger.

THE RULE THIS FILE INSTALLS
---------------------------
    A graded row must name, in this file, at least one mutation that turns it
    FAIL, and it must stay PASS on a clean input.  The suite runs both halves
    every time and fails when either drifts.

Sensitivity (something breaks it) and specificity (a correct build does not
trip it) are separate failures, and Wave 5 / 5b hit both: the kind-6 canary and
`ring_sweep` had no sensitivity, and `lino_break_matrix` had no specificity --
it reported the CLEAN build as a caught sabotage.  A check with only one of the
two is void.

Three dispositions, and no fourth:

    GRADED      it is evidence.  It must name its falsifiers and it must be
                measurably broken by every one of them.
    PIN         an external literal or an arithmetic identity that no mutation
                in the set can move.  Declared, and its falsifier set must
                MEASURE EMPTY -- a pin that becomes falsifiable was not a pin.
    NOTGRADED   it carries no evidence about any port.  Printed, never counted
                as a pass.

"Reword" is not a disposition.  A check whose text is wrong is a check whose
verdict is wrong.

OWNERSHIP
---------
Each entry names its two `sides` with an owner prefix, and the owner is a
FILE-PATH property, so it cannot be forged by accident:

    imp1:      noctis-harness/fb_*.py          (the graders -- and Workspace)
    imp2:      noctis-harness/fb_ref.c, fbx_*  (the producers)
    lino:      tests/w5probe.txt and its builds (neither implementer's)
    external:  the 1996 sources, SUPPORTS.NCT, the captures, the documents

    >> No GRADED row may compare two artifacts of the same owner. <<

That single assertion is the "helper that refuses to compare two values from
the same producer", obtained without threading provenance through 1,400-line
producers.  It is also the invariant that contains this wave's one structural
hazard: implementer 1 owns both a producer (`fb_layout.Workspace`) and the
grader, so `Workspace` may be compared to `fb_ref.c`, to lino, or to a parsed
1996 source -- never to `fb_compare.py`'s own expectations.

WHAT IT DOES NOT DO
-------------------
A void check can be ACCIDENTALLY falsified by an unrelated mutation.  That is
why the sensitivity gate demands the DECLARED falsifiers, not merely "some":
the diagonal has to be named.  This is the part a reviewer must actually read.

  python fb_ledger.py            # the ledger, and its own consistency checks
"""

import os
import sys

GRADED = "GRADED"
PIN = "PIN"
NOTGRADED = "NOTGRADED"

OWNERS = ("imp1", "imp2", "lino", "external")


class Entry(object):
    __slots__ = ("cid", "kind", "sides", "falsifier", "null_ok", "why", "family")

    def __init__(self, cid, kind, sides, falsifier=(), null_ok=True, why="",
                 family=None):
        self.cid = cid
        self.kind = kind
        self.sides = tuple(sides)
        self.falsifier = tuple(falsifier)
        self.null_ok = null_ok
        self.why = why
        self.family = family

    def owners(self):
        return [s.split(":", 1)[0] for s in self.sides]

    def __repr__(self):
        return "Entry(%s, %s, %d falsifier(s))" % (self.cid, self.kind, len(self.falsifier))


LEDGER = {}


def E(cid, kind, sides, falsifier=(), null_ok=True, why="", family=None):
    if cid in LEDGER:
        raise SystemExit("fb_ledger: duplicate check id %r" % cid)
    LEDGER[cid] = Entry(cid, kind, sides, falsifier, null_ok, why, family)
    return cid


# =====================================================================
# T3 -- the layout, parsed from the 1996 sources
# =====================================================================

E("T3.LAYOUT.CHECK", GRADED,
  ("imp1:fb_layout.Layout parse of NOCTIS-D.H + NOCTIS.CPP",
   "external:the 1996 sources themselves"),
  falsifier=["ORDER", "SWAPSEA", "NOPAD", "SHRINKADAPTED", "CLAMPPBG", "SEGBASE", "ONEZONE"],
  why="the L-row block; every LAYOUT_BREAK must move at least one of its rows")

from fb_layout import LAYOUT_BREAKS, WORKSPACE_BREAKS   # noqa: E402

for _b in LAYOUT_BREAKS:
    E("T3.LAYOUT.SABOTAGE.%s" % _b, GRADED,
      ("imp1:fb_layout.Layout under -D%s" % _b, "external:the unsabotaged 1996 sources"),
      falsifier=["inrow:" + _b],
      why="INROW.  The row's own body constructs Layout([%s]) and asserts that "
          "check() FAILS, so the sensitivity is demonstrated where it is claimed. "
          "fb_mutcov does not re-drive it: the verdict is identical under every "
          "suite mutation, so re-running it once per mutation measures nothing." % _b,
      family="layout-sabotage")

E("T3.LAYOUT.L1.ORDER", GRADED,
  ("imp1:fb_layout.Layout constructor order",
   "external:a SECOND parse of NOCTIS.CPP's farmalloc sequence"),
  falsifier=["ORDER", "SWAPSEA"],
  why="REFOUND: `got` used to be built by iterating `want`.  Two parses now, "
      "sharing no code -- statement adjacency vs source-line gaps.")

E("T3.LAYOUT.L12C.SEGOFFSET", GRADED,
  ("imp1:fb_layout.solve_seg_offset (4 parsed constraints)",
   "external:NOCTIS-D.H sc_bytes, NOCTIS-0.CPP Stick + wave, TDPOLYGS.H polymap"),
  falsifier=["SANDBOX-STICKDISP"],
  why="the alias-8 PREMISE, raised from Tier 0.  K was the literal 4 in "
      "fb_layout.py:83 AND in fb_ref.c:68 -- one number handed to both "
      "'independent' producers.  Now solved.  Falsified by editing the Stick "
      "displacement in a SANDBOX COPY of NOCTIS-0.CPP (fb_mutcov runs it).")

E("T3.LAYOUT.L14.PTRUNSIGNED", GRADED,
  ("imp1:fb_layout executing the parsed loop under two integer semantics",
   "external:NOCTIS-0.CPP:6423 snapshot() row loop + TDPOLYGS.H `unsigned ptr`"),
  falsifier=["SANDBOX-ROWLOOP"],
  why="was `((0-320) & 0xFFFFFFFF) >= 64000` -- a Python fact with no subject. "
      "Every loop constant is parsed now, so a source edit moves the row.")

E("T3.LAYOUT.L4.DIGITSUB", GRADED,
  ("imp1:fb_layout zone model",
   "external:NOCTIS.CPP:614-628 digit_at writes txtr[-6..-1]"),
  falsifier=["NOPAD", "ONEZONE"],
  why="WEAK, and declared weak: only these two mutations move it.  It has "
      "sensitivity, so it is GRADED rather than PIN -- the plan called it a PIN "
      "with named falsifiers, which the pin-integrity gate would reject.")

E("T3.LAYOUT.L9.ZONES", GRADED,
  ("imp1:fb_layout zone model", "external:the DOS far-heap block header, 16 bytes"),
  falsifier=["NOPAD", "ONEZONE"],
  why="same shape as L4, and declared the same way.")

E("T3.LAYOUT.L8.HEAPTOTAL", GRADED,
  ("imp1:fb_layout sum over the parsed sizes", "external:NOCTIS-D.H's *_bytes literals"),
  falsifier=["SHRINKADAPTED", "CLAMPPBG"],
  why="an external total; two size mutations move it, so it is not a pin.")

# =====================================================================
# T2 -- Python vs C, the two producers
# =====================================================================

_RECNAMES = ["adapted", "adaptor", "canary", "curpal6", "glyph", "kself", "layout",
             "lut", "pal6", "wrapcount", "zones"]

# PER-RECORD falsifiers, and they are per-record for a reason.  The first
# version of this block declared EVERY Python mutation against EVERY record,
# which reads as thorough and is the opposite: nine tenths of those
# declarations were false, and a declaration that is false in the "it does not
# actually catch this" direction is exactly what gate 1 exists to find.  The
# lists below were POPULATED FROM THE MEASUREMENT -- run the mutation, see
# which records move -- and that is the only honest way to seed a ledger.
# Their value is from here on: if a record STOPS catching one of these, the
# gate fails and someone has to explain what changed.
_REC_FALSIFIERS = {
    "adapted":   ["DIGITN1", "MASKCIRRUS", "MASKCIRRUSADDR", "NOPAD", "QUADWORDS",
                  "SEGBASE", "SWAPSEA", "TINTA64000"],
    "adaptor":   ["DIGITN1", "MASKCIRRUS", "MASKCIRRUSADDR", "NOPAD", "QUADWORDS",
                  "SEGBASE", "SWAPSEA", "TINTA64000"],
    "canary":    ["CANCONSTACTUAL", "CANSTUBCHECK", "CANSTUBPOISON", "CLAMPPBG",
                  "NINEWALK", "NOPAD", "ONEZONE", "ORDER", "SHRINKADAPTED", "SWAPSEA"],
    "curpal6":   ["DIV64", "NOCLAMP", "NOSELF", "PYFILT", "ROUNDSHADE"],
    "glyph":     ["DIGITN1", "MASKSPOT"],
    "kself":     ["CANSTUBCHECK", "CLAMPPBG", "DIGITN1", "IGNOREDST", "MASKCIRRUS",
                  "MASKCIRRUSADDR", "MASKSPOT", "NINEWALK", "NOPAD", "ONEZONE", "ORDER",
                  "QUADWORDS", "SEGBASE", "SELFSOURCE", "SHRINKADAPTED", "SWAPSEA",
                  "TINTA64000", "UPLOADFIRST"],
    "layout":    ["CLAMPPBG", "NOPAD", "ORDER", "SHRINKADAPTED", "SWAPSEA"],
    "lut":       ["DIV64", "NOCLAMP", "NOSELF", "PYFILT", "ROUNDSHADE", "SHIFTOR"],
    "pal6":      ["DIV64", "NOCLAMP", "NOSELF", "PYFILT", "ROUNDSHADE"],
    "wrapcount": ["MASKCIRRUS", "MASKCIRRUSADDR", "MASKSPOT", "SEGBASE"],
    "zones":     ["CLAMPPBG", "NOPAD", "ONEZONE", "ORDER", "SHRINKADAPTED", "SWAPSEA"],
}

for _n in _RECNAMES:
    E("T2.REC.%s.PYVSC" % _n.upper(), GRADED,
      ("imp1:fb_layout.Workspace / fb_pal.py", "imp2:fb_ref.c"),
      falsifier=_REC_FALSIFIERS[_n],
      why="two producers, different owners, byte-exact.  The falsifier list is the "
          "MEASURED set of Python-side mutations that move this record -- KSELF "
          "moves under 18 of them and GLYPH under 2, and pretending otherwise was "
          "the first draft of this ledger.",
      family="py-vs-c")

E("T2.CBUILD.CLEAN", GRADED,
  ("imp2:fb_ref.c", "external:gcc -Wall -Wextra"),
  falsifier=["inrow:GCCWARNING"],
  why="INROW: the condition is gcc's own exit status plus the absence of the string "
      "`warning` in its output.  Adding a warning to fb_ref.c fails it -- and "
      "fb_ref.c is implementer 2's file, so this harness declares the falsifier "
      "rather than manufacturing it.")

E("T2.CSELFTEST", GRADED,
  ("imp2:fb_ref.c self-test", "external:the 1996 sources it cites"),
  falsifier=["inrow:BREAK_IGNOREDST", "inrow:BREAK_SELFSOURCE", "inrow:BREAK_PACK4",
             "inrow:BREAK_TICKCMP", "inrow:BREAK_DIV64"],
  why="implementer 2 owns the fix that makes BREAK_DIV64 reach this row "
      "(fb_ref.c:947/:1367 build `want` with the #ifdef'd filter).")

E("T2.ALIAS8.PLACEMENT", GRADED,
  ("imp1:fb_layout parses `mov es:[0xFA00]` out of TDPOLYGS.H",
   "imp2:fb_ref.c transcribes it"),
  falsifier=["CLAMPPBG", "NOPAD", "ORDER", "SEGBASE", "inrow:BREAK_TINTA64000"],
  why="the PLACEMENT.  Measured: TINTA64000 does NOT move it -- that is a WORKSPACE "
      "mutation and this row compares Layout.alias8() against fb_ref.c's KSELF, so "
      "it moves under LAYOUT mutations only.  The declaration said otherwise until "
      "gate 1 said so.  Its premise is T3.LAYOUT.L12C, which used to be a shared "
      "literal and is now solved.")

E("T3.CANARY.V1VSV2", GRADED,
  ("imp1:fb_layout.Workspace.canary_v1", "imp1:fb_layout.Workspace.canary_v2"),
  falsifier=["inrow:CANSTUBCHECK", "inrow:CANSTUBPOISON", "inrow:CANCONSTACTUAL",
             "inrow:NINEWALK"],
  why="INROW.  THE ONE DELIBERATE SAME-OWNER ROW.  It compares two RECORD DESIGNS, not "
      "two producers: the claim is `v1 is bit-identical under a sabotage that "
      "moves v2`, and both must come from one workspace or the comparison "
      "measures the workspace instead.  Stated here so the owner-collision "
      "assertion's exemption is visible rather than silent.")

E("T3.OVERRUN.CENSUS", GRADED,
  ("imp1:fb_layout.Workspace.overrun_census",
   "external:TDPOLYGS.H:2817 texel address + NOCTIS-D.H gl_bytes"),
  falsifier=["NOPAD"],
  why="class-C reachability.  THIS ROW WAS VOID until this wave: overrun_census "
      "tested the pad hit against the MODULE constant PAD instead of the layout's "
      "own pad, so a padless layout still reported pad hits and no mutation could "
      "move the row.  It reads lay.pad now.  DECLARED WEAK, measured: SWAPSEA and "
      "SHRINKADAPTED do NOT move it, because the census is about the texel address "
      "and gl_bytes and no mutation in the set touches either.")

E("T3.PADPROBE.EXPECTATION", GRADED,
  ("imp1:fb_layout.Workspace.pad_probe_expectation",
   "external:NOCTIS.CPP:614-628, six underflow units"),
  falsifier=["DIGITN1", "NOPAD", "ONEZONE"],
  why="the count is what the program DID; a build with no underflow reports 0.")

E("T3.PADPROBE.VIOLATION", GRADED,
  ("imp1:fb_layout.Workspace.pad_probe_violation",
   "external:the 22-zone model's TAIL/SUB split"),
  falsifier=["NOPAD"],
  why="one write past n_globes_map, one TAIL hit.  DECLARED WEAK, and measured: "
      "ONEZONE and NINEWALK do NOT move it -- under ONEZONE the single zone is still "
      "a TAIL, and pad 3 lies inside NINEWALK's 1..9 window.  Declaring falsifiers "
      "that do not falsify is precisely the defect this gate exists to find, so they "
      "are named here as NOT falsifying rather than left in the list.")

for _b in sorted(WORKSPACE_BREAKS):
    E("T2.WORKSPACE.SABOTAGE.%s" % _b, GRADED,
      ("imp1:fb_layout.Workspace under %s" % _b, "imp2:fb_ref.c's clean records"),
      falsifier=["inrow:" + _b],
      why="INROW: the row builds python_records([%s]) itself and requires a graded "
          "record to MOVE." % _b,
      family="workspace-sabotage")

E("T2.PAL.SELFTEST", GRADED,
  ("imp1:fb_pal.py", "external:the 1996 palette routines it parses"),
  falsifier=["inrow:ROUNDSHADE", "inrow:NOCLAMP", "inrow:DIV64"],
  why="INROW: fb_pal.selftest runs its own sabotage battery and reports the aggregate.")

E("T2.TICK.ARITH", GRADED,
  ("imp1:fb_tick.py 32-bit decomposition", "external:the exact rational 32768000/596591"),
  falsifier=["NAIVE", "ROUND55", "NOCARRY", "UNSIGNEDCMP"],
  why="unbounded-integer truth vs a 32-bit construction: genuinely independent")

E("T2.WRAP.CLASSA", GRADED,
  ("imp1:fb_wrap.py", "external:NOCTIS-0.CPP:4485 / :4715 index expressions"),
  falsifier=["MASKSPOT", "MASKCIRRUS", "MASKCIRRUSADDR", "SEGADDRBASE", "PTRSIGNED"])

for _d, _desc, _t in ():
    pass

# =====================================================================
# T2 -- the C sabotage matrix
# =====================================================================

_C_BREAKS = [
    "BREAK_SHIFTOR", "BREAK_UPLOADFIRST", "BREAK_ROUNDSHADE", "BREAK_NOCLAMP",
    "BREAK_NOSELF", "BREAK_DIV64", "BREAK_PYFILT", "BREAK_IGNOREDST",
    "BREAK_SELFSOURCE", "BREAK_DIGITN1", "BREAK_TINTA64000", "BREAK_PACK4",
    "BREAK_QUADWORDS", "BREAK_TICKCMP", "BREAK_SHRINKADAPTOR", "BREAK_MASKSPOT",
    "BREAK_MASKCIRRUS", "BREAK_MASKCIRRUSADDR", "BREAK_SEGADDRBASE",
    "BREAK_PADONEMAGIC", "BREAK_PAD9WALK", "BREAK_CANSTUBCHECK",
    "BREAK_CANSTUBPOISON", "BREAK_CANCONSTACTUAL", "BREAK_LAYOUTEND",
]
for _b in _C_BREAKS:
    E("T2.CSABOTAGE.%s" % _b, GRADED,
      ("imp2:fb_ref.c under -D%s" % _b, "imp1:the Python records + fb_ref.c's clean dump"),
      falsifier=["inrow:" + _b],
      why="INROW: tier2_sabotage COMPILES fb_ref.c with -D%s and requires the named "
          "record to move.  Measured by gcc in the graded run." % _b,
      family="c-sabotage")

# =====================================================================
# T1 -- the 1996 captures
# =====================================================================

E("T1.CAPTURE.PRESENT", GRADED,
  ("imp1:fb_compare directory scan", "external:tests/gen/recon_w5c/artifacts"),
  falsifier=["inrow:EMPTYDIR"],
  why="INROW: the row's condition is bool(bmps or pngs) and it FAILS on an empty "
      "capture directory -- which is exactly what the deleted rec(..., True) row "
      "could not do.  The row that PASSED on a literal True is deleted; this is the one that "
      "already did the work, at :650.")
E("T1.BMP.SCALE", GRADED, ("imp1:fb_bmp.scale_audit", "external:the 1996 snapshot BMP"),
  falsifier=["inrow:SHIFTOR"], family="t1",
  why="INROW: the row computes the shift-or hypothesis on the same bytes and requires "
      "it to FAIL while v*4 fits.  Two hypotheses, one artifact -- and the artifact "
      "is one nobody in this project made.")
E("T1.PNG.SCALE", GRADED, ("imp1:fb_bmp.scale_audit", "external:a DOSBox-X raw PNG"),
  falsifier=["inrow:X4"], family="t1",
  why="INROW: the v*4 hypothesis is computed on the same bytes and must FAIL here, "
      "the mirror image of T1.BMP.SCALE.  Two capture routes, opposite verdicts, "
      "one piece of code.")
E("T1.PAL.FIT", GRADED, ("imp1:fb_pal.tier1_palette_audit", "external:the 1996 BMP palette"),
  falsifier=["inrow:ROUNDTONEAREST", "inrow:DIV64"], family="t1",
  why="INROW: T1.PAL.NOROUND and T1.PAL.NODIV64 are the falsifier rows -- one audit, "
      "two rival hypotheses, both required to fit NOTHING.")
E("T1.PAL.NOROUND", GRADED, ("imp1:fb_pal round-to-nearest falsifier",
                             "external:the 1996 BMP palette"),
  falsifier=["inrow:ROUNDTONEAREST"],
  why="INROW: this row IS a falsification -- it fits a rival hypothesis to the capture "
      "and requires it to fail.")
E("T1.PAL.NODIV64", GRADED, ("imp1:fb_pal /64 falsifier", "external:the 1996 BMP palette"),
  falsifier=["inrow:DIV64"], why="INROW: as T1.PAL.NOROUND, with /64 as the rival.")
E("T1.PNG.DOUBLING", GRADED, ("imp1:fb_bmp 2x2 audit", "external:a DOSBox-X raw PNG"),
  falsifier=["inrow:NONUNIFORM"],
  why="INROW: the row counts non-uniform 2x2 subpixels in the capture and requires "
      "ZERO.  A capture that was not 2x2-doubled reports a non-zero count -- the "
      "measurement is the falsification.")
E("T1.CAPTURE.AGREE", GRADED, ("external:the 1996 snapshot BMP", "external:a DOSBox-X raw PNG"),
  falsifier=["inrow:RAWBYTES"],
  why="two capture routes, neither of them ours.  INROW: the row measures that the "
      "RAW 8-bit bytes DIFFER while the 6-bit DAC components agree, so it cannot be "
      "satisfied by two copies of one file.")
E("T1.CAPTURE.PALSTABLE", PIN, ("external:snapshot BMP #1", "external:snapshot BMP #2"),
  why="both sides are external and that is the point: two UNPINNED 1996 "
      "captures, taken at different moments, agree on 768/768 palette bytes "
      "while differing in pixels.  Neither artifact is ours.")

# =====================================================================
# T3 -- tick and servo
# =====================================================================

E("T3.TICK.SELFGRADE", NOTGRADED,
  ("imp1:fb_tick.run_loop", "imp1:fb_tick.grade_ticklog"),
  why="GRADER SELF-TEST.  fb_tick's simulator feeding fb_tick's grader: one "
      "owner on both sides, so it carries no evidence about any port.  The "
      "sound instance is the lino TICKLOG row.")
E("T3.TICK.RATEPROBE", GRADED,
  ("imp1:fb_tick.grade_ticklog", "external:a header rate the log did not produce"),
  falsifier=["inrow:RATEOFF"],
  why="K6.  The highest-value single fix in fb_tick.py: before it, a log "
      "generated at 9900 cpms under a 9000 header passed K1..K5.")
E("T3.TICK.NOCARRY400", GRADED, ("imp1:fb_tick.grade_ticklog", "imp1:fb_tick.run_loop NOCARRY"),
  falsifier=["inrow:NOCARRY"],
  why="INROW: the row generates the NOCARRY log and requires grade_ticklog to reject it.")
E("T3.TICK.SERVOSTEP", GRADED, ("imp1:fb_tick.grade_ticklog", "imp1:fb_tick.run_loop servo"),
  falsifier=["inrow:SRVWILD"],
  why="INROW, and it is the SPECIFICITY half: a legitimate 1-count servo step must be "
      "ACCEPTED.  Its sensitivity partner is T3.TICK.SERVOWILD.")
E("T3.TICK.SERVOWILD", GRADED, ("imp1:fb_tick.grade_ticklog", "imp1:fb_tick.run_loop servo"),
  falsifier=["inrow:SRVWILD"],
  why="INROW: the row generates a 5% cpms lurch and requires the rejection.")
for _b in ("REBASE", "NOSKIP", "ROUND55", "NOCARRY"):
    E("T3.TICK.SABOTAGE.%s" % _b, GRADED,
      ("imp1:fb_tick.grade_ticklog", "imp1:fb_tick.run_loop under %s" % _b),
      falsifier=["inrow:" + _b], family="tick-sabotage",
      why="same owner on both sides, and deliberately: the claim is that the "
          "GRADER rejects a log the SIMULATOR generated wrong.  It is a "
          "sensitivity measurement of the grader, not evidence about a port, "
          "and it is only meaningful in the FAIL direction.")
E("T3.SERVO.BATTERY", GRADED,
  ("imp1:fb_tick.Servo", "external:the 8253 counter's 32-bit ring"),
  falsifier=["SRVRUNSTART", "SRVWIDEMAX", "SRVUNSIGNEDBAND", "SRVTRUNC",
             "SRVCLAMPFLOOR", "WALLNOFOLD", "DONOTHING", "NOREBASE"],
  why="T8a..T8i.  DONOTHING is declared because T8a and T8f used to seed the "
      "estimator AT the true rate, where a do-nothing estimator passed both.")
for _b in ("SRVRUNSTART", "SRVWIDEMAX", "SRVUNSIGNEDBAND", "SRVTRUNC",
           "SRVCLAMPFLOOR", "WALLNOFOLD", "DONOTHING", "NOREBASE"):
    E("T3.SERVO.SABOTAGE.%s" % _b, GRADED,
      ("imp1:fb_tick.Servo under %s" % _b, "external:the 8253 counter's 32-bit ring"),
      falsifier=["inrow:" + _b], family="servo-sabotage",
      why="INROW: the row runs the whole servo battery under --break %s and requires "
          "a non-zero exit." % _b)

# =====================================================================
# T3 -- class A
# =====================================================================

for _b in ("MASKSPOT", "MASKCIRRUS", "MASKCIRRUSADDR", "SEGADDRBASE", "PTRSIGNED"):
    E("T3.CLASSA.SABOTAGE.%s" % _b, GRADED,
      ("imp1:fb_wrap.py under %s" % _b, "external:NOCTIS-0.CPP's index expressions"),
      falsifier=["inrow:" + _b], family="classa-sabotage",
      why="INROW: the row runs fb_wrap under %s and requires the FAIL." % _b)
E("T3.STICK.A1", GRADED, ("imp1:fb_stick.py", "external:TDPOLYGS.H:746-761 poly3d clamp"),
  falsifier=["inrow:CLIPSTAGE"])
E("T3.STICK.CLIPSTAGE", GRADED, ("imp1:fb_stick.py under CLIPSTAGE",
                                 "external:TDPOLYGS.H:746-761"),
  falsifier=["inrow:CLIPSTAGE"],
  why="INROW: the row runs fb_stick under CLIPSTAGE and requires the non-zero exit.")
E("T3.STICK.A2CORPUS", GRADED, ("imp1:fb_stick.py", "external:NOCTIS-0.CPP:1296 riga[] index"),
  falsifier=["inrow:CLAMPRIGA"],
  why="INROW: the 400k-case corpus reports the escape and the CLAMPRIGA divergence "
      "inside its own battery.")

# =====================================================================
# The fixture, the lino side, and the meta-rows
# =====================================================================

E("T3.FIXTURE.IDENTITY", GRADED,
  ("imp1:the SHA-256 of docs-notes/FIXTURE1.txt",
   "external:the hash each producer embedded in its KSELF record"),
  falsifier=["SANDBOX-FIXTUREEDIT"],
  why="REFOUND from a doc check that hunted bare integers in LINOBUF 6.1 -- a "
      "section that IS the record set, not a fixture, so the row's verdict was "
      "decided by heading numbering.  A build-identity check grades a hash.")

E("T2.LINO.V2", GRADED, ("lino:the FBDUMP container", "external:LINOBUF 6 v2 format"),
  falsifier=["LINO-V1"], why="format conformance, which CAN pass")
E("T2.LINO.TAGSPRESENT", GRADED, ("lino:the FBDUMP container", "external:LINOBUF 6.1 clause"),
  falsifier=["LINO-NOTAGS"],
  why="a v2 stream in which NO record carries a non-zero tag is MALFORMED: the "
      "version word must not promise what the payload does not carry.  Today's "
      "guard was `if 1 in vers`, which let w5probe.bin through and produced "
      "eleven `FAIL ... missing` rows that misdescribed their own cause.")
for _n in _RECNAMES:
    E("T2.LINO.REC.%s" % _n.upper(), GRADED,
      ("lino:tests/w5probe.txt", "imp2:fb_ref.c + imp1:fb_layout.Workspace"),
      falsifier=["LINO-SABOTAGE"], family="lino-rec")
E("T2.LINO.TICKLOG", GRADED, ("lino:tests/w5probe.txt", "imp1:fb_tick.grade_ticklog"),
  falsifier=["LINO-SABOTAGE"], why="the SOUND instance of the ticklog grade")
E("T2.LINO.SERVOLOG", GRADED, ("lino:tests/w5probe.txt", "imp1:fb_tick.grade_servolog"),
  falsifier=["LINO-SABOTAGE"], why="the SOUND instance of the servolog grade")
E("T2.LINO.MATRIX.GATE", GRADED,
  ("imp1:the clean lino's verdict set", "imp2:fb_ref.c's records"),
  falsifier=["LINO-SABOTAGE"],
  why="the precondition gate.  Any record the CLEAN build fails is excluded "
      "from grading for every sabotage row, by name.")
E("T2.LINO.MATRIX.NULL", GRADED,
  ("lino:the clean dump fed in as a sabotage", "imp1:the differential criterion"),
  falsifier=["CLEANASBREAK"], null_ok=False,
  why="THE MANDATORY NULL-INPUT ROW.  It must read NOT CAUGHT.  The old matrix "
      "read CAUGHT for the clean build, which is the whole of recon A 2.1.")
E("T2.LINO.MATRIX.ROW", GRADED,
  ("lino:a sabotaged build", "imp1:the records the clean build passes"),
  falsifier=["LINO-SABOTAGE"], family="lino-matrix",
  why="CAUGHT iff (a record the clean build PASSES) is failed by the sabotage.")

E("META.MUTCOV.SENSITIVITY", GRADED,
  ("imp1:fb_mutcov measured falsifier sets", "imp1:this ledger's declarations"),
  falsifier=["LEDGER-DROP"],
  why="GATE 1, sensitivity.  Both sides are imp1 and neither is a producer: one "
      "is a MEASUREMENT (which mutations actually break each cid) and the other "
      "is a DECLARATION (which ones were claimed).  Comparing a measurement to a "
      "claim is the job; they cannot be the same artifact.")
E("META.MUTCOV.SPECIFICITY", GRADED,
  ("imp1:fb_mutcov clean run", "imp1:this ledger"), falsifier=["LEDGER-DROP"],
  why="GATE 2, specificity.  Every cid must PASS on a non-mutated input, and "
      "every grading matrix fed a clean subject must report NOT CAUGHT.  This "
      "is the gate that kills lino_break_matrix by construction.")
E("META.MUTCOV.PINS", GRADED,
  ("imp1:fb_mutcov measured falsifier sets", "imp1:this ledger's PIN rows"),
  falsifier=["LEDGER-DROP"],
  why="GATE 3, pin integrity.  A PIN whose measured falsifier set is NON-empty "
      "fails: it was not a pin.  Drift fails in BOTH directions, which is what "
      "makes the ledger a ratchet rather than a suppression list.")
E("META.LINT", GRADED,
  ("imp1:fb_lint.py", "external:fbout/lintcorpus, six deliberately void snippets"),
  falsifier=["LINT-BLUNT"],
  why="a lint that cannot be shown to catch is the same class of defect it "
      "exists to find.")

# -- PINs.  Declared, and their measured falsifier set must be EMPTY. ----

E("T3.SERVO.T8D.ROUNDING", GRADED,
  ("imp1:fb_tick.Servo rounded divide", "imp1:the same function with SRVTRUNC set"),
  falsifier=["SRVTRUNC", "DONOTHING"],
  why="DECLARED A PIN AND REFUTED BY GATE 3, in this wave's own run.  The plan called "
      "it a pin -- same function, flag flipped, expected pair independent -- and the "
      "pin-integrity gate measured SRVTRUNC and DONOTHING moving it, so it was never "
      "a pin: it is a weak GRADED row with two real falsifiers.  Left here with its "
      "history because this is the gate working, not the gate being worked around.")

E("T0.ALIAS8.PREMISE", NOTGRADED,
  ("external:four parsed source constraints", "external:nothing has measured it"),
  why="the K-solver raises this from Tier 0 (asserted) to Tier 3 (derived and "
      "graded from source).  It is still NOT MEASURED: only DOSBox-X + "
      "NOCTIS.SYM measures it, and that experiment also retires the riga[] "
      "VALUES divergence.  Printed as NOT GRADED, never as a pass.")
E("T2.LINO.ADAPTED.CROSSFIXTURE", NOTGRADED,
  ("lino:w5probe's fixture", "imp2:fb_ref.c's fixture"),
  why="TWO DIFFERENT SCENARIOS, each internally correct.  The cross-comparison "
      "is a category error, and printing it as a red row is the mirror image of "
      "Wave 5's sin.  It becomes gradeable when docs-notes/FIXTURE1.txt exists "
      "and both producers re-derive from it; it becomes TIER 2 when a lino "
      "sabotage is shown to break it while the clean build passes.")


# =====================================================================
# consistency of the ledger itself
# =====================================================================


def validate():
    """Returns (ok, [messages]).  Run on every import path that grades."""
    msg, ok = [], True

    def bad(t):
        nonlocal ok
        ok = False
        msg.append("  FAIL  " + t)

    for cid, e in sorted(LEDGER.items()):
        if e.kind not in (GRADED, PIN, NOTGRADED):
            bad("%s: disposition %r is not one of the three" % (cid, e.kind))
        for s in e.sides:
            if s.split(":", 1)[0] not in OWNERS:
                bad("%s: side %r has no recognised owner prefix %s" % (cid, s, OWNERS))
        if e.kind == GRADED:
            if not e.falsifier:
                bad("%s: GRADED with no declared falsifier.  A claim with no named "
                    "falsifier is a PIN or it is not graded." % cid)
            own = e.owners()
            if len(own) >= 2 and own[0] == own[1] and not e.why:
                bad("%s: both sides are owned by %r and the entry gives no reason.  "
                    "No GRADED row may compare two artifacts of the same owner "
                    "unless the entry says why in `why`." % (cid, own[0]))
        if e.kind == PIN and e.falsifier:
            bad("%s: PIN with declared falsifiers -- if a mutation moves it, it is "
                "not a pin, it is a weak GRADED row.  Say which." % cid)
    same_owner = [cid for cid, e in LEDGER.items()
                  if e.kind == GRADED and len(e.owners()) >= 2 and e.owners()[0] == e.owners()[1]]
    msg.append("  NOTE  %d GRADED row(s) compare two artifacts of ONE owner, each with a "
               "stated reason: %s" % (len(same_owner), ", ".join(sorted(same_owner))))
    msg.append("  PASS  %d entries: %d GRADED, %d PIN, %d NOT GRADED"
               % (len(LEDGER),
                  sum(1 for e in LEDGER.values() if e.kind == GRADED),
                  sum(1 for e in LEDGER.values() if e.kind == PIN),
                  sum(1 for e in LEDGER.values() if e.kind == NOTGRADED)))
    return ok, msg


def declared_falsifiers():
    out = set()
    for e in LEDGER.values():
        out |= set(e.falsifier)
    return sorted(out)


def get(cid):
    e = LEDGER.get(cid)
    if e is None:
        raise SystemExit(
            "fb_ledger: no entry for check id %r.  A check cannot exist without a "
            "ledger entry -- add one, with its falsifiers, or mark it NOTGRADED." % cid)
    return e


def main(argv=None):
    ok, msg = validate()
    print("fb_ledger.py -- the falsification ledger")
    print("=" * 78)
    for cid in sorted(LEDGER):
        e = LEDGER[cid]
        print("%-38s %-9s %s" % (cid, e.kind, "|".join(e.sides)))
        if e.falsifier:
            print("%-38s falsified by: %s" % ("", ", ".join(e.falsifier)))
        if e.why:
            print("%-38s %s" % ("", e.why.replace("\n", " ")[:160]))
    print("=" * 78)
    print("\n".join(msg))
    print("distinct declared falsifiers: %d" % len(declared_falsifiers()))
    print("RESULT: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
