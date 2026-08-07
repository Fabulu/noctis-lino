#!/usr/bin/env python3
"""fbmkbreak.py - build every deliberately broken Wave 5 build.

Each break is ONE textual substitution in ONE library.  The substitution is
asserted to match exactly once, so a sabotage that silently failed to apply -
and would then have "passed" for the wrong reason - cannot happen.

A break file is a standalone lino program: it takes a HARNESS program
(fbmain.txt, fbsrv.txt or fbshade.txt), drops the subject from its "libraries"
period, and inlines the broken library's periods instead.  The harness around a
sabotage is therefore byte-identical to the reference harness; only the subject
differs.

House standard: every check must be provably breakable, demonstrated by
breaking the thing it guards.  The "caught by" column names the observable that
must move, and it must be the observable, not a dump perturbation.

Usage: python fbmkbreak.py [name ...]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PERIODS = ["libraries", "stockfile", "directors", "constants",
           "variables", "workspace", "programme"]

# short constants: a sabotage run has to be quick.  SERVON is low enough that
# the servo fires inside the short soak - at 256 it never fired at all, which
# is how a wrapping servo reached the reviewer.
SHELL_CONSTS = """	NTICK		= 120;
	NFRAME		= 20;
	HITCHMOD	= 37;
	CALMS		= 600;
	SERVON		= 96;
"""


def split_periods(src):
    out, order = {}, []
    depth, i, cur, start, lead_end = 0, 0, None, 0, None
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
    # (name, harness, library, old, new, headline, must be caught by)

    # ---------------- the original ten ----------------
    ("fbbreak1", "fbmain", "fbpal",
     """	C = [D];	  C & 63; C * 4; C < 16;
	A = [D plus 1];   A & 63; A * 4; A < 8;   C + A;
	A = [D plus 2];   A & 63; A * 4;          C + A;""",
     """	C = [D];	  C & 63; B = C; B > 4; C < 2; C | B; C < 16;
	A = [D plus 1];   A & 63; B = A; B > 4; A < 2; A | B; A < 8;  C + A;
	A = [D plus 2];   A & 63; B = A; B > 4; A < 2; A | B;         C + A;""",
     "LUT built with (v<<2)|(v>>4) instead of v*4",
     "the LUT record must stop being curpal6*4"),

    ("fbbreak2", "fbmain", "fbpal",
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
    "PAL up lut"
	[PLfirst] = [PVfirst]; [PLn] = [PVn];""",
     "tavola_colori uploads only its own band instead of starting at colour 0",
     "curpal6 must differ: scenario step 3 rewrote colours 0-63 without "
     "uploading them and step 5's upload is what picks them up"),

    ("fbbreak3", "fbmain", "fbpal",
     "	=> FToIntChop;\n	[SHb] = [FI];",
     "	=> FToIntNear;\n	[SHb] = [FI];",
     "shade() rounds to nearest instead of chopping",
     "pal6 must differ - scenario step 3's ramp steps by 63/64 so chop and "
     "round disagree at the very first colour"),

    ("fbbreak4", "fbmain", "fbtick",
     """	A = [TKnow]; A - [TKdeadline];
	? A < 0 -> TK islate no;""",
     """	? [TKnow] '< [TKdeadline] -> TK islate no;""",
     "wait predicate replaced by an unsigned timestamp compare",
     "wrap_failures must be non-zero"),

    ("fbbreak5", "fbmain", "fbtick",
     "	=> TK advance;\n	=> TK skip;\n	=> TK wait;",
     "	=> TK advance;\n	=> TK wait;",
     "no skip-to-grid after a missed deadline",
     "back-to-back fires must appear after each injected hitch"),

    ("fbbreak6", "fbmain", "fbshell",
     "	[FBy] = 0;\n    \"FB dr y\"",
     "	[FBy] = 1;\n    \"FB dr y\"",
     "raster loop started at 1 - niv-lr's digit_at bug applied to FB draw",
     "the adapted page must differ from the reference in row 0"),

    ("fbbreak7", "fbmain", "fbmem",
     "	A = [MCap]; C = [A];\n	? C = [MEMtmp] -> MEM cp next;",
     "	A = [MCap]; C = [A];\n	-> MEM cp next;",
     "guard check that can never fire",
     "canary kind 6 v2 unit 2 must go to 0 on every pad, and the glyph "
     "expectation count must go to 0 as well"),

    ("fbbreak8", "fbmain", "fbshell",
     "	A = nw; A + RADPT; A + 63996;",
     "	A = nw; A + RADPT; A + 64000;",
     "tinta/escrescenze relocated to 64000 - niv-lr's divergence",
     "the adapted page must differ at row 199 columns 316-317"),

    ("fbbreak9", "fbmain", "fbmem",
     """	RSBG	= 40172;	ZSBG	= 64800;	( s_background     )
	RPBG	= 104988;	ZPBG	= 65552;	( p_background     )""",
     """	RPBG	= 40172;	ZPBG	= 64800;	( p_background     )
	RSBG	= 104988;	ZSBG	= 65552;	( s_background     )""",
     "layout in declaration order instead of farmalloc order",
     "the layout record must stop matching NOCTIS-D.H"),

    ("fbbreak10", "fbmain", "fbmem",
     '"MEM put byte"\n	A = nw; A + [MBptr];',
     '"MEM put byte"\n	A = nw; C = [MBptr]; C > 2; A + C;',
     "byte store packed four to a unit",
     "bchk must become non-zero"),

    # ---------------- the servo, defect 1 ----------------
    ("fbsrvrunstart", "fbsrv", "fbtick",
     "	[TKsrv0c] = [Counts];			( RE-BASE FIRST )",
     "	( re-base deleted )",
     "S-SRV-RUNSTART: the counts anchor is never re-based",
     "fbsrv B5: firing 2 must stop seeing a fresh window"),

    ("fbsrvunsigned", "fbsrv", "fbtick",
     "	A = [TKsrvms]; ? A < SRVMIN -> TK sv short;	( SIGNED )",
     "	A = [TKsrvms]; ? A '< SRVMIN -> TK sv short;	( UNSIGNED )",
     "S-SRV-UNSIGNEDBAND: the acceptance band is unsigned again",
     "fbsrv B6: the -86,399,800 ms midnight window must stop being refused"),

    ("fbsrvwidemax", "fbsrv", "fbtick",
     "	SRVMAX	= 60000;",
     "	SRVMAX	= 600000;",
     "S-SRV-WIDEMAX: the window ceiling is above the counter wrap",
     "fbsrv B1 case 6: the 500,000 ms aliased window must stop being refused"),

    ("fbsrvtrunc", "fbsrv", "fbtick",
     "	B = [TKsrvms]; C = B; C '/ 2;\n	A = [TKsrvcnt]; A + C; A '/ B; [TKsrvnew] = A;	( ROUNDED )",
     "	B = [TKsrvms];\n	A = [TKsrvcnt]; A '/ B; [TKsrvnew] = A;	( TRUNCATED )",
     "S-SRV-TRUNC: the divide truncates",
     "fbsrv B3: the rounding case must return 8999 instead of 9000"),

    ("fbsrvclampfl", "fbsrv", "fbtick",
     "	B = [TKcpms]; B '/ 100; ? B != 0 -> TK sv step;\n	B = 1;					( clamp step floor )",
     "	B = [TKcpms]; B '/ 100;			( no floor )",
     "S-SRV-CLAMPFLOOR: the clamp step can be zero, an absorbing state",
     "fbsrv B4: cpms must stay at 99 forever instead of climbing"),

    ("fbsrvnofold", "fbsrv", "fbtick",
     "	A = [TKwraw]; ? A '>= [TKwallprev] -> TK wf same;\n	[TKwallday] + MSPERDAY;",
     "	A = [TKwraw]; ? A '>= [TKwallprev] -> TK wf same;",
     "S-WALL-NOFOLD: the wall clock steps backwards at midnight",
     "fbsrv B6: the fold delta must stop being +200"),

    # ---------------- the 16-bit mask, defect 2 ----------------
    ("fbmaskspot", "fbmain", "fbshell",
     "	C = [FBpy]; C + [FBpx]; C + 4;\n	=> MEM u16 site;",
     "	C = [FBpy]; C + [FBpx]; C + 4;",
     "S-MASK-SPOT: spot's 16-bit truncation is deleted",
     "the spot wrap counter must go to 0 AND the masked index must stop "
     "differing from the naive one"),

    ("fbmaskcirrus", "fbmain", "fbshell",
     "	C = [FBpy]; C + [FBpx];\n	=> MEM u16 site;\n	C > 1; C + 4;",
     "	C = [FBpy]; C + [FBpx];\n	C > 1; C + 4;\n	=> MEM u16 site;",
     "S-MASK-CIRRUS-ADDR: cirrus masked at the address, not at the truncation "
     "point",
     "cirrus's failure delta must change from 32,768 to 65,536"),

    ("fbsegbase", "fbmain", "fbmem",
     "	SPBG	= 104984;",
     "	SPBG	= 104988;",
     "S-SEGADDR-BASE: the mask is taken against the buffer base, not the "
     "segment origin",
     "the containment assertion must fire on every low-offset spot case"),

    # ---------------- the zones, defects 3 and 5 ----------------
    ("fbpadonemagic", "fbmain", "fbmem",
     "	PALLOW	= 1515870810;",
     "	PALLOW	= 2779096485;",
     "S-PAD-ONEMAGIC: one poison for both zones",
     "a legitimate write becomes indistinguishable from a violation - the "
     "canary v2 clean reads must stop separating TAIL from SUB"),

    ("fbpadnodigit", "fbmain", "fbshell",
     "	[DGn] = 0;\n    \"FB dg n\"",
     "	[DGn] = 1;\n    \"FB dg n\"",
     "S-PAD-NODIGIT: digit_at's loop starts at n = 1, niv-lr's actual bug",
     "the glyph expectation count must go 6 -> 0 AND the glyph plane must "
     "differ - two independent places"),

    ("fbpad9walk", "fbmain", "fbmem",
     "	A = [MCzi]; ? A '< NZONE -> MEM cp zone;",
     "	A = [MCzi]; ? A '< 8 -> MEM cp zone;",
     "S-PAD-9WALK: the walker stops before the high pads",
     "canary v2 must fail on every pad above 3"),

    ("fbcanstubpoison", "fbmain", "fbmem",
     '"MEM poison pads"\n	[MCzi] = 0;',
     '"MEM poison pads"\n	end;\n	[MCzi] = 0;',
     "S-CAN-STUBPOISON: the pads are never poisoned",
     "canary v2 unit 0 must stop reading back the magic"),

    ("fbcanconst", "fbmain", "fbshell",
     "	A = [FBap]; C = [A];\n	D = [FBcp];\n	[D plus 1] = C;",
     "	D = [FBcp];\n	C = 3235774464; C + [FBi];\n	[D plus 1] = C;",
     "S-CAN-CONSTACTUAL: the dirty read is a literal, not a read",
     "the v1 defect exactly: unit 1 becomes a value written by construction "
     "on both sides.  It must be caught by pairing it with unit 2 or 3"),

    # ---------------- shade, defect 6 ----------------
    ("fbshdst", "fbshade", "fbpal",
     "	A = [FBSHfirst]; A * 3; A + [SHdstb]; [SHdst] = A;",
     "	A = [FBSHfirst]; A * 3; A + pal6; [SHdst] = A;",
     "SH-IGNOREDST: shade ignores its destination parameter",
     "fbshade: srfpal6 must stay zero and pal6's sentinel must be destroyed - "
     "a RUNNING check, because this one still compiles"),

    # ---------------- the present path, S12 ----------------
    ("fbs12", "fbmain", "fbshell",
     """    "FB ex loop"
	C = [D];	 C + pal; C = [C]; [E] = C;
	C = [D plus 1];  C + pal; C = [C]; [E plus 1] = C;
	C = [D plus 2];  C + pal; C = [C]; [E plus 2] = C;
	C = [D plus 3];  C + pal; C = [C]; [E plus 3] = C;""",
     """    "FB ex loop"
	C = [D];	 B = C; B & 192; C + 1; C & 63; C + B; [D] = C;
			 C + pal; C = [C]; [E] = C;
	C = [D plus 1];  B = C; B & 192; C + 1; C & 63; C + B; [D plus 1] = C;
			 C + pal; C = [C]; [E plus 1] = C;
	C = [D plus 2];  B = C; B & 192; C + 1; C & 63; C + B; [D plus 2] = C;
			 C + pal; C = [C]; [E plus 2] = C;
	C = [D plus 3];  B = C; B & 192; C + 1; C & 63; C + B; [D plus 3] = C;
			 C + pal; C = [C]; [E plus 3] = C;""",
     "S12: the colour cycle re-fused into the expand - the shipped Wave 5 "
     "shell's actual state",
     "the adaptor page must differ.  This was UNCATCHABLE before, because the "
     "shell rebuilt the page immediately before dumping it"),
]


def build(name, harness, lib, old, new, headline, must):
    src = open(os.path.join(HERE, lib + ".txt"), encoding="utf-8").read()
    cnt = src.count(old)
    if cnt != 1:
        sys.exit("%s: pattern matches %d times in %s.txt, not 1"
                 % (name, cnt, lib))
    broken = src.replace(old, new)
    _l, blib, _o = split_periods(broken)

    hsrc = open(os.path.join(HERE, harness + ".txt"), encoding="utf-8").read()
    _l2, hper, _o2 = split_periods(hsrc)

    libs = []
    for line in hper.get("libraries", "").split("\n"):
        t = line.strip().rstrip(";").strip()
        if t and t != lib:
            libs.append("\t%s;" % t)

    dirs = []
    for line in hper.get("directors", "").split("\n"):
        s = line.strip()
        if s.lower().startswith("program name"):
            dirs.append("\tprogram name = { %s };" % name)
        elif s:
            dirs.append("\t" + s)

    body = []
    body.append("      ( *** %s - DELIBERATELY BROKEN ***\n" % name)
    body.append("\tharness : %s.txt\n" % harness)
    body.append("\tsubject : %s.txt\n" % lib)
    body.append("\tsabotage: %s\n" % headline)
    body.append("\tmust be caught by: %s\n\n" % must)
    body.append("\tGenerated by fbmkbreak.py, which asserts the substitution\n"
                "\tmatched exactly once.  Everything except the one edit is a\n"
                "\tverbatim copy of %s.txt, and the harness around it is the\n"
                "\tsame one the reference build uses. )\n\n" % lib)

    body.append('"libraries"\n\n' + "\n".join(libs) + "\n\n")
    body.append('"directors"\n\n' + "\n".join(dirs) + "\n\n")

    body.append('"constants"\n')
    if harness == "fbmain":
        body.append("\n" + SHELL_CONSTS)
    else:
        body.append(hper.get("constants", "\n"))
    body.append(blib.get("constants", "\n"))

    body.append('"variables"\n')
    body.append(hper.get("variables", "\n"))
    body.append(blib.get("variables", "\n"))

    body.append('"workspace"\n')
    body.append(hper.get("workspace", "\n"))
    body.append(blib.get("workspace", "\n"))

    body.append('"programme"\n')
    body.append(hper.get("programme", "\n"))
    body.append(blib.get("programme", "\n"))

    out = os.path.join(HERE, name + ".txt")
    open(out, "w", encoding="utf-8", newline="").write("".join(body))
    return out


if __name__ == "__main__":
    want = sys.argv[1:]
    for spec in BREAKS:
        if want and spec[0] not in want:
            continue
        p = build(*spec)
        print("%-16s harness %-8s subject %-8s %s"
              % (spec[0], spec[1], spec[2] + ".txt", spec[5]))
