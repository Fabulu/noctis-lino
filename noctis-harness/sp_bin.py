#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
sp_bin.py -- Wave 6b, producer P4: the 1996 BINARY.

sp_ref.c and the lino port both transliterate NOCTIS-0.CPP's inline assembly.
They read the same 1996 text, so a shared misreading of one asm line survives
both.  This file answers the one question neither can: does the SHIPPED
BINARY agree with the text they transliterated?

That is not hypothetical for this wave.  `niv-lr/src/noctis-0.cpp` -- the
de-assembled C++ that a reasonable person would reach for -- has an AND where
vanilla has an OR in glowinglobe's vertical clip, and a commented-out `+4` on
background's source cursor.  Both are visible in the binary, and both are
decoded here.

Owner: bin:  (byte offsets in a 1996 artifact).  It compares NOTHING to
sp_ref.c's output and NOTHING to sp_spec.py's.  It compares the binary to
CONSTANTS RESTATED HERE, so the ledger row is always bin: vs claim:, never
cref: vs cref:.

NO BARE OFFSETS.  Every anchor carries the argument for why it is the right
bytes: an occurrence count over the whole 215,744-byte image, and where
relevant a bracketing relation to a neighbouring anchor.  An anchor that is
not unique -- or that is unique only per function -- says so and says what
brackets it.

THIS FILE RENDERS NO VERDICTS in the wave's sense.  It prints a table and
exits non-zero if any anchor fails to reproduce, so it is runnable on its
own; but the wave's PASS/FAIL rows are `linoharness.Check.ok` calls in
tests/test_sphere.py, which is inside w5audit.py's scope.

Usage:  python sp_bin.py [--exe NOCTIS.EXE] [--json]
"""

import argparse
import json
import os
import struct
import sys

NOCTIS = r"C:\programmieren\noctis\niv-plus\modules\NOCTIS.EXE"
EXPECT_SIZE = 215744

# --------------------------------------------------------------------------
# What the port claims, RESTATED HERE, independently of sp_ref.c.
# Source: NOCTIS-0.CPP:3100-3170 (globe), :3230-3296 (glowinglobe),
#         :2704-2748 (background), :3021-3041 (the fill managers),
#         :5109-5124 (surface's day/night band), TDPOLYGS.H:130-137 (riga).
# --------------------------------------------------------------------------

CLAIM = dict(
    globe_y_lo=6, globe_y_hi=191,        # cmp di,6 / jb ; cmp di,191 / jnb
    globe_x_lo=6, globe_x_hi=311,        # cmp ax,6 / jb ; cmp ax,311 / jnb
    glow_y_a=10, glow_y_b=190,           # cmp di,10 / jnb ; cmp di,190 / jb
    glow_x_lo=9, glow_x_hi=310,          # cmp ax,9 / jb ; cmp ax,310 / jnb
    bg_sentinel=64000,                   # cmp word ptr [si],64000 / jnb
    map_sentinel=100,                    # cmp byte ptr [si],100 / jne
    riga_dgroup=0x435C,                  # mov di, gs:riga[di]
    dark_start=35, dark_rows=179, dark_cols=130, dark_stride_back=230,
    dark_shift=2,
)


def load(path):
    with open(path, "rb") as f:
        return f.read()


def find_all(buf, pat):
    out, i = [], 0
    while True:
        i = buf.find(pat, i)
        if i < 0:
            return out
        out.append(i)
        i += 1


def rel8(buf, at):
    """`jcc rel8` / `jmp rel8` at `at` -> its absolute file target."""
    d = buf[at + 1]
    if d >= 128:
        d -= 256
    return at + 2 + d


class Anchors:
    def __init__(self):
        self.rows = []
        self.ok = True

    def add(self, aid, what, passed, detail, why):
        self.rows.append(dict(id=aid, what=what, passed=bool(passed),
                              detail=detail, why=why))
        if not passed:
            self.ok = False

    def report(self):
        w = max(len(r["id"]) for r in self.rows)
        for r in self.rows:
            print("%-*s  %-4s  %-46s  %s"
                  % (w, r["id"], "ok" if r["passed"] else "FAIL",
                     r["what"], r["detail"]))
        print()
        for r in self.rows:
            print("  %-*s  %s" % (w, r["id"], r["why"]))
        print()
        n = len(self.rows)
        bad = sum(1 for r in self.rows if not r["passed"])
        print("sp_bin: %d anchors, %d reproduce, %d do not" % (n, n - bad, bad))
        return 0 if self.ok else 1


def analyse(E):
    A = Anchors()
    A.add("SIZE", "NOCTIS.EXE is the 215,744-byte build",
          len(E) == EXPECT_SIZE, "%d bytes" % len(E),
          "Every offset below is only meaningful for this image.  Wave 6a's "
          "pg_bin.py decoded the MZ header of the same file: 608 header "
          "paragraphs -> image base at file 9728.")

    # ---- X3: the map sentinel, TWO hits, and they BRACKET the two spheres --
    sent = find_all(E, bytes.fromhex("803C6475"))     # cmp byte [si],100 / jne
    A.add("X3.SENTINEL",
          "cmp byte ptr [si],%d / jne  (the GLOBES.MAP skip marker)"
          % CLAIM["map_sentinel"],
          sent == [54079, 54876], "hits %s" % sent,
          "NOT unique in the image -- it is unique PER FUNCTION, and that is "
          "the point: the two hits are globe's and glowinglobe's record "
          "loops, and everything else in this file at 54079..54210 and "
          "54876..54990 lies between them.  The sentinel is compared against "
          "the FIRST byte of the pair, which is what makes 'first byte = Y' "
          "a binary fact rather than a reading of the comment at "
          "NOCTIS-0.CPP:3030.")

    # ---- X4/X5: globe's clip, and all four arms going to ONE clipout ------
    g_y = find_all(E, bytes.fromhex("83FF06724081FFBF00733A"))
    A.add("X4.GLOBE_Y",
          "globe: cmp di,%d / jb ; cmp di,%d / jnb  (accept 6..190)"
          % (CLAIM["globe_y_lo"], CLAIM["globe_y_hi"]),
          g_y == [54107], "hits %s" % g_y,
          "Unique in 215,744 bytes.  The compares are UNSIGNED (jb/jnb), so a "
          "negative sum wraps to a large u16 and is rejected by the HIGH arm, "
          "not the low one.  niv-lr uses `pos > 6`, which is off by one on "
          "the low bound.")
    g_x = find_all(E, bytes.fromhex("3D0600 7218 3D3701 7313".replace(" ", "")))
    A.add("X5.GLOBE_X",
          "globe: cmp ax,%d / jb ; cmp ax,%d / jnb  (accept 6..310)"
          % (CLAIM["globe_x_lo"], CLAIM["globe_x_hi"]),
          g_x == [54147], "hits %s" % g_x,
          "Unique.  Note 311 = 0x0137 and 191 = 0x00BF: neither is the "
          "tdpolygs.h clip rectangle, so globe does NOT share poly3d's "
          "clipper.")
    tgt = [rel8(E, 54110), rel8(E, 54116), rel8(E, 54150), rel8(E, 54155)]
    A.add("X6.ONE_CLIPOUT",
          "globe's four clip arms all branch to ONE clipout",
          tgt == [54176, 54176, 54176, 54176], "targets %s" % tgt,
          "Decoded from the rel8 displacements, not asserted.  54176 is "
          "`83 C3 01` = add bx,1 -- so the TAPESTRY CURSOR ADVANCES ON "
          "CLIPPED RECORDS TOO.  A rasteriser that advances only on drawn "
          "records desynchronises the texture from the map.")
    A.add("X6b.CLIPOUT_BODY",
          "clipout at 54176 is `add bx,1 / add si,2 / dec cx`",
          E[54176:54183] == bytes.fromhex("83C30183C60249"),
          E[54176:54183].hex(),
          "The `add bx,1` is what X6 is about; `add si,2` is the record "
          "stride, which is 2 and not 4 -- the int16 reading of GLOBES.MAP "
          "would need 4.")

    # ---- X7: the unsigned skip advance ------------------------------------
    sk = find_all(E, bytes.fromhex("30E401C3"))       # xor ah,ah / add bx,ax
    A.add("X7.SKIP_UNSIGNED",
          "globe blanket: xor ah,ah / add bx,ax  (skip advance is UNSIGNED)",
          sk == [54190], "hits %s" % sk,
          "Unique, and it is the ONLY admissible evidence for the unsigned "
          "read.  Every one of the 513 skip bytes in the shipped GLOBES.MAP "
          "is <= 100, so signed and unsigned decoders produce the IDENTICAL "
          "cursor stream and IDENTICAL predictor scores (10,780/10,780 "
          "both ways -- measured).  A check of the form 'the shipped map "
          "decodes correctly with an unsigned advance' cannot fail and is "
          "REFUSED.  `xor ah,ah` zero-extends; a signed read would be `cbw`.")
    A.add("X7b.SKIP_NOT_CBW",
          "the skip path does NOT sign-extend (no cbw at 54190)",
          E[54189:54190] != b"\x98" and E[54190:54192] == b"\x30\xE4",
          "byte at 54189 = %02x, at 54190..1 = %s"
          % (E[54189], E[54190:54192].hex()),
          "The DRAW path two instructions earlier DOES use cbw (54088 and "
          "54123), so the binary distinguishes the two readings in three "
          "places within 110 bytes.")

    # ---- X8: glowinglobe's vertical clip is a DISJUNCTION ------------------
    gl_y = find_all(E, bytes.fromhex("83FF0A730881FFBE007202EB38"))
    jnb_t = rel8(E, 54915)
    jb_t = rel8(E, 54921)
    jmp_t = rel8(E, 54923)
    A.add("X8.GLOW_Y_OR",
          "glowinglobe: (di>=%d) OR (di<%d) -- true for EVERY di"
          % (CLAIM["glow_y_a"], CLAIM["glow_y_b"]),
          gl_y == [54912] and jnb_t == 54925 and jb_t == 54925
          and jmp_t == 54981,
          "hits %s ; jnb->%d jb->%d jmp->%d" % (gl_y, jnb_t, jb_t, jmp_t),
          "Decoded, not argued.  BOTH conditional branches land on 54925, "
          "which is `8A 44 01` = mov al,[si+1] -- the y_ok label.  The "
          "`jmp` at 54923 targets 54981, the clipout, and NOTHING reaches "
          "it: the vertical clip NEVER REJECTS and the jump is dead code.  "
          "niv-lr's `pos > 10 && pos < 190` is an AND where vanilla has an "
          "OR; it is a KNOWN WRONG ANSWER and it also silently removes every "
          "out-of-range riga[] read.")
    A.add("X8b.GLOW_YOK",
          "54925 is y_ok: mov al,[si+1] / add di,di / cbw",
          E[54925:54931] == bytes.fromhex("8A440101FF98"),
          E[54925:54931].hex(),
          "`add di,di` runs BEFORE the `cbw`, so riga is indexed by the "
          "DOUBLED di and the byte offset is 2*di.  Getting that order wrong "
          "reads a different scanline.")
    A.add("X8c.GLOW_CLIPOUT",
          "54981 is clipout: add dx,1 / cmp dx,360 / jb",
          E[54981:54990] == bytes.fromhex("83C20181FA6801 7202".replace(" ", "")),
          E[54981:54990].hex(),
          "The longitude counter advances on EVERY non-skip record, drawn or "
          "decimated -- `test dx,3 / jz` jumps to this same label.")
    gl_x = find_all(E, bytes.fromhex("3D0900 7216 3D3601 7311".replace(" ", "")))
    A.add("X9.GLOW_X",
          "glowinglobe: cmp ax,%d / jb ; cmp ax,%d / jnb  (accept 9..309)"
          % (CLAIM["glow_x_lo"], CLAIM["glow_x_hi"]),
          gl_x == [54954], "hits %s" % gl_x,
          "Unique, and DIFFERENT from globe's 6..310 (X5).  The four sphere "
          "renderers disagree about their clip rectangles in the original, "
          "and niv-lr parameterised only globe -- so following LR makes the "
          "four agree, which is wrong.")

    # ---- X10: riga at DS:435Ch, exactly twice -----------------------------
    rg = find_all(E, bytes.fromhex("658BBD5C43"))
    A.add("X10.RIGA",
          "mov di, gs:[di+%04Xh]  -- riga[200], TDPOLYGS.H:130"
          % CLAIM["riga_dgroup"],
          rg == [54124, 54931], "hits %s" % rg,
          "Exactly two: globe (inside 54079..54202) and glowinglobe (inside "
          "54876..54990).  globe's Y clip bounds DI to [6,190] so its index "
          "2*DI stays inside the 400-byte table; glowinglobe's does not "
          "clip at all (X8), so it reads DGROUP at 435Ch +- 2*DI.  The "
          "INDEX SEQUENCE is graded exactly; the VALUE read is NOT GRADED, "
          "because reproducing it needs the loaded DGROUP image and that is "
          "not recoverable statically with confidence.")

    # ---- X11: the four fill managers --------------------------------------
    gm = {
        "gman1x1 es:[di+4],dl": ("26885504", [53516]),
        "gman3x3 es:[di+6],dl": ("26885506", [53543]),
        "gman3x3 es:[di+646],dl": ("2688958602", [53562]),
        "gman4x4 es:[di+964],dx": ("268995C403", [53600]),
        "gman4x4 es:[di+966],dx": ("268995C603", [53605]),
    }
    gmok = True
    gmdet = []
    for nm, (pat, exp) in gm.items():
        h = find_all(E, bytes.fromhex(pat))
        gmdet.append("%s=%s" % (nm.split()[0], h))
        if h != exp:
            gmok = False
    A.add("X11.GMAN", "the four fill managers carry the +4 as a LITERAL",
          gmok, " ".join(gmdet),
          "53516..53610 is one contiguous run of four tiny far functions, in "
          "declaration order.  The displacements are 4, 5, 6, 7 / 324..327 / "
          "644..647 / 964..967 -- i.e. 320*row + col + 4.  That 4 is "
          "farmalloc's offset (BUFFERMAP.md 4.1), which globe's prologue "
          "loads into AX from `les ax,target` and then DISCARDS.  There is "
          "no second +4 anywhere in the sphere path, and adding one is the "
          "SCRATCHOFF-class defect Wave 6a measured at 23 moved pages.")

    # ---- X12: background --------------------------------------------------
    bs = find_all(E, bytes.fromhex("813C00FA73"))     # cmp word [si],64000/jnb
    A.add("X12.BG_SENTINEL",
          "background: cmp word ptr [si],%d / jnb" % CLAIM["bg_sentinel"],
          bs == [52514], "hits %s" % bs,
          "Unique.  A WORD compare, so OFFSETS.MAP is uint16 little endian, "
          "and `jnb` makes 64000 itself a skip.  The blanket path is "
          "`mov bx,[si] / sub bx,64000 / add bp,bx`, and BP is the SOURCE "
          "cursor -- so the skip is in the panorama, not a screen wrap.")
    bgst = [("66 26 89 05", 52542, "32-bit store es:[di]"),
            ("26 88 45 04", 52546, "byte es:[di+4]"),
            ("66 26 89 85 40 01", 52550, "32-bit es:[di+320]"),
            ("26 88 85 44 01", 52556, "byte es:[di+324]"),
            ("66 26 89 85 00 05", 52583, "32-bit es:[di+1280]"),
            ("26 88 85 04 05", 52589, "byte es:[di+1284]")]
    bok, bdet = True, []
    for pat, exp, nm in bgst:
        h = find_all(E, bytes.fromhex(pat.replace(" ", "")))
        bdet.append("%s@%s" % (nm.split()[0], h[:2]))
        if exp not in h:
            bok = False
    A.add("X12b.BG_BLOCK", "background paints a 5x5 block, NOT 4x4 or 6x6",
          bok, " ".join(bdet),
          "Five rows at 0/320/640/960/1280 and five columns per row: a "
          "32-bit store covers four bytes and a byte store the fifth.  Note "
          "the displacements are 0,320,... with NO +4 -- because "
          "`add screenshift,ax` folded offset(target) into the shift.  "
          "That asymmetry with X11 is the whole of the farmalloc-offset "
          "story and it is visible in the binary.")

    # ---- X13: surface()'s day/night band -----------------------------------
    dark = E[70071:70104]
    want = bytes.fromhex("C43E") + dark[2:4] + bytes.fromhex(
        "037EFE" "83C723" "B9B300" "51" "B98200" "26C02D02" "47" "49" "75F8"
        "59" "81C7E600" "49" "75EC")
    A.add("X13.DARK_BAND",
          "surface: +%d, %d rows, %d cols, shr 2, +%d"
          % (CLAIM["dark_start"], CLAIM["dark_rows"], CLAIM["dark_cols"],
             CLAIM["dark_stride_back"]),
          dark[:len(want)] == want, dark.hex(),
          "`les di,[p_background] / add di,[bp-2] (plwp) / add di,23h (35) / "
          "mov cx,B3h (179)` then an inner `mov cx,82h (130)` over "
          "`shr byte ptr es:[di],2 / inc di`, closing with `add di,E6h "
          "(230)`.  130 + 230 = 360, the texture stride.  There is NO "
          "mod-360 reduction on `add di,plwp / add di,35`, so the band "
          "starts at an UNREDUCED offset -- and 179, not 180, so the last "
          "row of the 360x180 map is never darkened.  This is the whole of "
          "the planet lighting model: it is BAKED INTO THE TEXTURE and there "
          "is no N-dot-L anywhere in the path.")

    # ---- X14: __ftol chops ------------------------------------------------
    ftol = E[14437:14437 + 40]
    A.add("X14.FTOL_CHOP",
          "__ftol at file 14437 ORs 0Ch into the control word (RC <- chop)",
          E[14452:14456] == bytes.fromhex("804EFF0C"),
          "14452..55 = %s  (prologue %s)"
          % (E[14452:14456].hex(), ftol[:24].hex()),
          "Re-derived here rather than cited: FLOATPOLICY.md 3.3 settled "
          "this in Wave 6 and tests/test_geometry.py re-derives it every "
          "run.  It matters to Wave 6b because globe's and glowinglobe's "
          "centres are C CASTS -- chop on the LIVE 80-bit st(0) -- while "
          "project3d's two conversions are hand-written `fistp` at RC=00, "
          "round half even, and whiteglobe adds 0.5 and never casts at all.  "
          "Three different roundings across four functions.")
    return A


# --------------------------------------------------------------------------
# Every anchor broken, by breaking it.  A byte-identity check against a 1996
# artifact is trivially true unless someone shows what makes it false, so
# --selfbreak perturbs ONE byte of an in-memory copy per anchor and reports
# which anchors notice.  The row that must be read carefully is the one where
# a perturbation moves MORE than its own anchor: that is coverage, not noise.
# --------------------------------------------------------------------------

BREAKS = [
    ("X4.GLOBE_Y", 54109, "globe's Y low bound 6 -> 7 (niv-lr's `pos > 6`)", 0x07),
    ("X5.GLOBE_X", 54148, "globe's X low bound 6 -> 10", 0x0A),
    ("X6.ONE_CLIPOUT", 54111, "one clip arm branches somewhere else", 0x3E),
    ("X6b.CLIPOUT_BODY", 54178, "clipout advances the cursor by 2, not 1", 0x02),
    ("X7.SKIP_UNSIGNED", 54190, "xor ah,ah -> cbw: the skip read becomes SIGNED",
     0x98),
    ("X8.GLOW_Y_OR", 54915, "jnb -> jb: the disjunction becomes a real clip",
     0x72),
    ("X8b.GLOW_YOK", 54928, "add di,di removed: riga indexed UNdoubled", 0x90),
    ("X8c.GLOW_CLIPOUT", 54985, "the longitude wrap becomes 361", 0x69),
    ("X9.GLOW_X", 54955, "glowinglobe's X low bound 9 -> 6 (unified with globe)",
     0x06),
    ("X10.RIGA", 54127, "riga moves to DS:435Dh", 0x5D),
    ("X11.GMAN", 53519, "gman1x1 drops the +4 (writes es:[di+0])", 0x00),
    ("X12.BG_SENTINEL", 52516, "background's sentinel 64000 -> 63999", 0xFF),
    ("X12b.BG_BLOCK", 52549, "background's 5th column moves to +5", 0x05),
    ("X13.DARK_BAND", 70091, "shr byte es:[di],2 -> shr 1", 0x01),
    ("X13.DARK_BAND", 70082, "179 rows -> 180", 0xB4),
    ("X14.FTOL_CHOP", 14455, "__ftol ORs 00h: the cast stops chopping", 0x00),
]


def selfbreak(E):
    print("%-18s %-8s %-52s %s"
          % ("ANCHOR", "byte", "the defect", "anchors that notice"))
    allok = True
    for aid, off, what, val in BREAKS:
        b = bytearray(E)
        if b[off] == val:
            print("%-18s %-8d %-52s SKIPPED (byte already %02x)"
                  % (aid, off, what, val))
            allok = False
            continue
        b[off] = val
        A = analyse(bytes(b))
        moved = [r["id"] for r in A.rows if not r["passed"]]
        hit = aid in moved
        if not hit:
            allok = False
        print("%-18s %-8d %-52s %s%s"
              % (aid, off, what, moved, "" if hit else "   <-- NOT CAUGHT"))
    print()
    A = analyse(E)
    clean = [r["id"] for r in A.rows if not r["passed"]]
    print("NULL-INPUT (the unmodified image): %s"
          % (clean if clean else "nothing fires -- correct"))
    if clean:
        allok = False
    return 0 if allok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default=NOCTIS)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selfbreak", action="store_true")
    a = ap.parse_args()
    if not os.path.exists(a.exe):
        print("sp_bin: %s not found" % a.exe, file=sys.stderr)
        return 2
    E = load(a.exe)
    if a.selfbreak:
        return selfbreak(E)
    A = analyse(E)
    if a.json:
        json.dump(dict(exe=a.exe, size=len(E), claim=CLAIM, rows=A.rows),
                  sys.stdout, indent=1)
        print()
        return 0 if A.ok else 1
    return A.report()


if __name__ == "__main__":
    sys.exit(main())
