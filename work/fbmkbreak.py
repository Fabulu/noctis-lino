#!/usr/bin/env python3
"""fbmkbreak.py - build the ten deliberately broken Wave 5 framebuffer builds.

Each break is ONE textual substitution in ONE library.  The substitution is
asserted to match exactly once, so a sabotage that silently failed to apply -
and would then have "passed" for the wrong reason - cannot happen.

A break file is a standalone lino program: it links the OTHER libraries and
inlines the broken one's periods, with the driver's four constants merged into
the constants period.  That way the harness around a sabotage is byte-identical
to the reference harness; only the subject differs.

Usage: python fbmkbreak.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIBS = ["fbmem", "fbpal", "fbtick", "fbshell"]
FPLIBS = ["fp/fpabi", "fp/fpctl", "fp/fpx87", "fp/fpconv"]
PERIODS = ["libraries", "stockfile", "directors", "constants",
           "variables", "workspace", "programme"]

# short constants: a sabotage run has to be quick, and nothing any sabotage
# changes depends on the length of the soak except break 5, which needs
# HITCHMOD to fire at least twice inside NTICK.
DRIVER_CONSTS = """	NTICK		= 120;
	NFRAME		= 20;
	HITCHMOD	= 37;
	CALMS		= 600;
"""


def split_periods(src):
    """Return (leading_comment, {period: text}) respecting lino comments."""
    out = {}
    order = []
    depth = 0
    i = 0
    cur = None
    start = 0
    lead_end = None
    while i < len(src):
        c = src[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth = max(0, depth - 1)
        elif c == '"' and depth == 0:
            j = src.index('"', i + 1)
            name = src[i + 1:j].replace(" ", "").lower()
            if name in PERIODS:
                if cur is None:
                    lead_end = i
                else:
                    out[cur] = src[start:i]
                cur = name
                order.append(name)
                start = j + 1
            i = j
        i += 1
    if cur is not None:
        out[cur] = src[start:]
    return src[:lead_end if lead_end is not None else len(src)], out, order


BREAKS = [
    # (n, library, old, new, headline, what must fail)
    (1, "fbpal",
     """	C = [D];	  C & 63; C * 4; C < 16;
	A = [D plus 1];   A & 63; A * 4; A < 8;   C + A;
	A = [D plus 2];   A & 63; A * 4;          C + A;""",
     """	C = [D];	  C & 63; B = C; B > 4; C < 2; C | B; C < 16;
	A = [D plus 1];   A & 63; B = A; B > 4; A < 2; A | B; A < 8;  C + A;
	A = [D plus 2];   A & 63; B = A; B > 4; A < 2; A | B;         C + A;""",
     "LUT built with (v<<2)|(v>>4) instead of v*4",
     "the LUT record must stop being curpal6*4, and must differ from the "
     "reference LUT - the game's own snapshot() scales by 4, so this is the "
     "one that would silently mis-grade against the BMP palette"),

    (2, "fbpal",
     """	A = pal6; D = curpal6;
	B = [PUn]; B * 3;
	? B = 0 -> PAL up lut;
    "PAL up loop"
	C = [A]; [D] = C; A+; D+;
	B ^ PAL up loop;
    "PAL up lut"
	[PLfirst] = 0; [PLn] = [PUn];""",
     """	A = [PVfirst]; A * 3; D = A; A + pal6; D + curpal6;
	B = [PVn]; B * 3;
	? B = 0 -> PAL up lut;
    "PAL up loop"
	C = [A]; [D] = C; A+; D+;
	B ^ PAL up loop;
    "PAL up lut"
	[PLfirst] = [PVfirst]; [PLn] = [PVn];""",
     "tavola_colori uploads only its own band instead of starting at colour 0",
     "curpal6 must differ from the reference: S7 rewrote colours 0-63 without "
     "uploading them and S11's upload is what picks them up"),

    (3, "fbpal",
     "	=> FToIntChop;\n	[SHb] = [FI];",
     "	=> FToIntNear;\n	[SHb] = [FI];",
     "shade() rounds to nearest instead of chopping",
     "pal6 must differ from the reference - a C cast truncates, and S7's "
     "ramp steps by 63/64 so the two roundings disagree immediately"),

    (4, "fbtick",
     """	A = [TKnow]; A - [TKdeadline];
	? A < 0 -> TK islate no;""",
     """	? [TKnow] '< [TKdeadline] -> TK islate no;""",
     "wait predicate replaced by an unsigned timestamp compare",
     "wrap_failures must be non-zero: [Counts] wraps every ~477 s and the "
     "compare is wrong on both sides of the wrap"),

    (5, "fbtick",
     "	=> TK advance;\n	=> TK skip;\n	=> TK wait;",
     "	=> TK advance;\n	=> TK wait;",
     "no skip-to-grid after a missed deadline",
     "back-to-back fires must appear after each injected hitch - the original "
     "waits for a counter EDGE, so an overrunning frame loses a whole tick"),

    (6, "fbshell",
     "	[FBy] = 0;\n    \"FB dr y\"",
     "	[FBy] = 1;\n    \"FB dr y\"",
     "raster loop started at 1 - niv-lr's actual digit_at bug, "
     "applied to the only raster loop Wave 5 has",
     "the adapted page must differ from the reference in row 0"),

    (7, "fbmem",
     """	C = [A];
	? C = POISON -> MEM cp ok;
	[MCn]+;""",
     """	C = [A];
	-> MEM cp ok;
	[MCn]+;""",
     "canary check that can never fire",
     "canary_dirty_fired must become 0 - the shell injects a one-unit "
     "overrun on purpose and a check that cannot fail must not pass"),

    (8, "fbshell",
     "	A = nw; A + RADPT; A + 63996;",
     "	A = nw; A + RADPT; A + 64000;",
     "tinta/escrescenze relocated to 64000 - niv-lr's divergence",
     "the adapted page must differ from the reference at row 199 columns "
     "316-317: under farmalloc offset == 4 those are VISIBLE pixels"),

    (9, "fbmem",
     """	RSBG	= 40172;	ZSBG	= 64800;	( s_background     )
	RPBG	= 104988;	ZPBG	= 65552;	( p_background     )""",
     """	RPBG	= 40172;	ZPBG	= 64800;	( p_background     )
	RSBG	= 104988;	ZSBG	= 65552;	( s_background     )""",
     "layout in declaration order instead of farmalloc order",
     "the layout record must stop matching NOCTIS-D.H: p_background gets "
     "s_background's size and the sea texture's overrun no longer lands on "
     "the neighbour DOS gave it"),

    (10, "fbmem",
     '"MEM put byte"\n	A = nw; A + [MBptr];',
     '"MEM put byte"\n	A = nw; C = [MBptr]; C > 2; A + C;',
     "byte store packed four to a unit",
     "bchk must become non-zero - eight distinct byte offsets, four of them "
     "inside one would-be packed unit, must all read back what was written"),
]


def build(n, lib, old, new, headline, must):
    src = open(os.path.join(HERE, lib + ".txt"), encoding="utf-8").read()
    cnt = src.count(old)
    if cnt != 1:
        sys.exit("break %d: pattern matches %d times in %s.txt, not 1"
                 % (n, cnt, lib))
    broken = src.replace(old, new)
    _lead, per, _order = split_periods(broken)

    others = [l for l in LIBS if l != lib]
    body = []
    body.append("      ( *** fbbreak%d - DELIBERATELY BROKEN ***\n" % n)
    body.append("\tsubject : %s.txt\n" % lib)
    body.append("\tsabotage: %s\n" % headline)
    body.append("\tmust fail: %s\n\n" % must)
    body.append("\tGenerated by fbmkbreak.py, which asserts the substitution\n"
                "\tmatched exactly once.  Everything except the one edit is a\n"
                "\tverbatim copy of %s.txt, and the harness around it is the\n"
                "\tsame libraries the reference build links. )\n\n" % lib)

    body.append('"libraries"\n\n')
    for l in FPLIBS:
        body.append("\t%s;\n" % l)
    body.append("\n")
    for l in others:
        body.append("\t%s;\n" % l)
    body.append("\n")

    body.append('"directors"\n\n')
    body.append("\tprogram name = { fbbreak%d };\n" % n)
    body.append("\tunit = 32;\n")
    body.append("\tdisplay width = 320;\n")
    body.append("\tdisplay height = 200;\n\n")

    body.append('"constants"\n\n')
    body.append(DRIVER_CONSTS)
    body.append(per.get("constants", "\n"))

    body.append('"variables"\n')
    body.append(per.get("variables", "\n"))

    body.append('"workspace"\n')
    body.append(per.get("workspace", "\n"))

    body.append('"programme"\n\n')
    body.append("\t=> FB run;\n\tend;\n\n")
    body.append(per.get("programme", "\n"))

    out = os.path.join(HERE, "fbbreak%d.txt" % n)
    open(out, "w", encoding="utf-8", newline="").write("".join(body))
    return out


if __name__ == "__main__":
    for spec in BREAKS:
        p = build(*spec)
        print("wrote %s  (subject %s.txt: %s)" %
              (os.path.basename(p), spec[1], spec[4]))
