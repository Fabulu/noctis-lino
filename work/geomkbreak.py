"""geomkbreak.py -- build a DELIBERATELY BROKEN geoconv, and the probe that
uses it.

The rule this wave inherits: every test builds a broken version of its subject
and requires that to fail.  A probe that reports "0 disagreements" is
indistinguishable from a probe that is not measuring anything, so the
measurement needs its own controls.

Five single-edit mutations, each of which is a mistake a reader could actually
make:

  nochop   GeoKMulChopLive loses its `fldcw chop`.  The fistp then rounds to
           nearest under 133Fh instead of truncating.  This is FLOATPOLICY
           3.3's "genfp will happily emit a bare fistp with no fldcw bracket".

  spilled  GeoQuoMulChopLive gains an fstp qword / fld qword pair.  This is
           the hole itself, re-opened: the "live" reading silently becomes the
           spilled one and battery 1 stops being able to tell them apart.

  nospill  GeoKMulChopSpill loses its fstp/fld pair, so both readings are the
           live one.  Every disagreement count collapses to zero and the probe
           reports, plausibly and wrongly, that the cast boundary does not
           matter.  This is the most dangerous of the five because its output
           looks like good news.

  chopd32  GeoPlainChop uses a 32-bit fistp instead of __ftol's 64-bit one.
           This is what fpconv's FToIntChop does today, and on anything
           outside int32 it stores the integer indefinite 80000000h where the
           original lets the low half through.

  nosext   GeoChop16 stops sign extending.  The int16 wrap at the call
           boundary -- the NORMAL path for star classes 1, 3, 4 and 9 --
           becomes an unsigned value.

Usage: python geomkbreak.py <name>
Writes work/geoconvbrk.txt and work/geocastbrk.txt.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "geoconv.txt")
DST = os.path.join(HERE, "geoconvbrk.txt")
PSRC = os.path.join(HERE, "geocast.txt")
PDST = os.path.join(HERE, "geocastbrk.txt")

TAB = "\t"
FLDCW_CHOP = TAB + "    D9 AF <dgcchop mtp bytesperunit>" + TAB + "(fldcw [edi+gcchop*4])\n"
SPILL = (TAB + "    DD 9F <dgcT0 mtp bytesperunit>" + TAB + "(fstp  qword [edi+gcT0*4])\n"
         + TAB + "    DD 87 <dgcT0 mtp bytesperunit>" + TAB + "(fld   qword [edi+gcT0*4])\n")
FISTPQ = TAB + "    DF BF <dgcQ0 mtp bytesperunit>" + TAB + "(fistp qword [edi+gcQ0*4])\n"
FISTPD = TAB + "    DB 9F <dFI mtp bytesperunit>" + TAB + "(fistp dword [edi+FI*4])\n"
TAKELOW = TAB + "A = [gcQ0]; [FI] = A;\n"
SEXT = ("      ? [FI] '< 8000h -> gc16done;\n"
        + TAB + "A = [FI]; A - 65536; [FI] = A;\n")


def routine(text, name):
    """return (start, end) character offsets of one "Name" ... end; block."""
    m = re.search(r'^"%s"\s*$' % re.escape(name), text, re.M)
    if not m:
        raise SystemExit("geomkbreak: no routine %r in geoconv.txt" % name)
    e = text.index("\n" + TAB + "end;", m.end())
    return m.start(), e


def edit(text, name, fn):
    a, b = routine(text, name)
    body = text[a:b]
    new = fn(body)
    if new == body:
        raise SystemExit("geomkbreak: mutation %r changed nothing in %s" % (sys.argv[1], name))
    return text[:a] + new + text[b:]


BREAKS = {
    "nochop": lambda t: edit(t, "GeoKMulChopLive", lambda b: b.replace(FLDCW_CHOP, "")),
    "spilled": lambda t: edit(
        t, "GeoQuoMulChopLive",
        lambda b: b.replace(TAB + "    D9 AF <dgcchop", SPILL + TAB + "    D9 AF <dgcchop")),
    "nospill": lambda t: edit(t, "GeoKMulChopSpill", lambda b: b.replace(SPILL, "")),
    "chopd32": lambda t: edit(
        t, "GeoPlainChop",
        lambda b: b.replace(FISTPQ, FISTPD).replace(TAKELOW, "")),
    "nosext": lambda t: edit(t, "GeoChop16", lambda b: b.replace(SEXT, "")),
}

if len(sys.argv) != 2 or sys.argv[1] not in BREAKS:
    raise SystemExit("usage: geomkbreak.py <%s>" % "|".join(sorted(BREAKS)))

name = sys.argv[1]
src = open(SRC, encoding="utf-8", newline="").read()
out = BREAKS[name](src)
banner = ("      ( *** GENERATED - DO NOT EDIT.  geoconv.txt with the %r\n"
          + TAB + "mutation applied by geomkbreak.py.  This file is WRONG on\n"
          + TAB + "purpose and exists only so the probe can be required to\n"
          + TAB + "notice. *** )\n\n") % name
open(DST, "w", encoding="utf-8", newline="").write(banner + out)

p = open(PSRC, encoding="utf-8", newline="").read()
for a, b in ((TAB + "geoconv;", TAB + "geoconvbrk;"),
             ("program name = { geocast };", "program name = { geocastbrk };"),
             ("{ geocast.bin }", "{ geocastbrk.bin }")):
    if a not in p:
        raise SystemExit("geomkbreak: geocast.txt no longer contains %r" % a)
    p = p.replace(a, b)
open(PDST, "w", encoding="utf-8", newline="").write(p)
print("geomkbreak: wrote geoconvbrk.txt (%s) and geocastbrk.txt" % name)
