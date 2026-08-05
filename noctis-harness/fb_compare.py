#!/usr/bin/env python3
"""fb_compare.py -- Wave 5, implementer 2.  The grader.

Grades the lino framebuffer against the two independent references and against
the 1996 capture routes, on three tiers:

  Tier 1  against artifacts this project did not make.  Wave 5 has no
          renderer, so this is the PALETTE only -- but that grades the whole
          palette pipeline, and it is genuinely non-circular.
  Tier 2  lino vs fb_ref.c and lino vs fb_pal.py / fb_tick.py, byte-exact on
          every FBDUMP kind.
  Tier 3  properties that need no oracle: the layout by construction, the
          canaries, the tick soak recomputed from raw counts.

Every comparison is exact.  Nothing is graded against a stored artifact this
project produced, and every subject has a deliberately broken build that this
script must reject.

  python fb_compare.py --suite                     # everything, from scratch
  python fb_compare.py --suite --lino DIR          # ... including the lino dumps
  python fb_compare.py A.bin B.bin                 # one pairwise compare
"""

import argparse
import collections
import glob
import os
import struct
import subprocess
import sys

from fb_layout import (Layout, fbdump_read, fbdump_write, layout_payload,
                       KIND_NAME, KIND_INDEXPAGE, KIND_PALETTE6, KIND_LUT,
                       KIND_TICKLOG, KIND_LAYOUT, KIND_CANARY)
import fb_pal
import fb_tick
import fb_bmp

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fbout")
CAPS = os.path.abspath(os.path.join(HERE, "..", "tests", "gen", "recon_w5c", "artifacts"))
SUPPORTS = r"C:\programmieren\noctis\niv-plus\data\SUPPORTS.NCT"

# every single-edit sabotage of the C reference, and which check must reject it
C_BREAKS = [
    ("BREAK_SHIFTOR", "LUT via (v<<2)|(v>>4) instead of v*4", "lut"),
    ("BREAK_UPLOADFIRST", "tavola_colori uploads [first,first+n)", "lut"),
    ("BREAK_ROUNDSHADE", "shade() rounds instead of truncating", "pal6"),
    ("BREAK_NOCLAMP", "tavola_colori drops the >63 clamp", "pal6"),
    ("BREAK_NOSELF", "self-copy reloads a stale source", "pal6"),
    ("BREAK_DIGITN1", "digit_at loop starts at n=1 (niv-lr's bug)", "glyph"),
    ("BREAK_TINTA64000", "tinta/escrescenze at 64000 (niv-lr's divergence)", "adapted"),
    ("BREAK_PACK4", "packed 4 bytes per unit", "selftest"),
    ("BREAK_QUADWORDS", "page ops hard-code 64000 bytes", "adapted"),
    ("BREAK_TICKCMP", "unsigned timestamp wait predicate", "selftest"),
    ("BREAK_SHRINKADAPTOR", "adaptor sized 64000, not a full segment", "layout"),
]

KIND_OF = {
    "layout": KIND_LAYOUT, "pal6": KIND_PALETTE6, "lut": KIND_LUT,
    "adapted": KIND_INDEXPAGE, "adaptor": KIND_INDEXPAGE,
    "glyph": KIND_INDEXPAGE, "canary": KIND_CANARY,
}

# FBDUMP v1 (LINOBUF 6) pins the CONTAINER and says nothing about what state
# the machine should be in when a record is written.  For LAYOUT, CANARY and
# TICKLOG that does not matter -- they are properties of the build.  For
# PALETTE6, LUT and INDEXPAGE it decides every unit, so without an agreed
# scenario the two sides dump different pictures and the compare measures
# nothing.  This is that agreement, stated so it can be implemented from the
# text alone.  It is a TEST FIXTURE, not a claim about the game.
SCENARIO_SPEC = r"""
FBDUMP v1 -- PINNED SCENARIOS (implementer 2, fb_ref.c / fb_pal.py)
==================================================================
Emit records in this order.  All arithmetic is integer unless stated.

SCENARIO "surface"  -> kinds 2 (pal6), 2 (curpal6), 3 (lut)
  1  pal6[0..767] = 0 ; curpal6[0..767] = 0
  2  tavola_colori(range8088, first=0,   n=64,  fr=16, fg=32, fb=63)
  3  tavola_colori(SELF,      first=0,   n=256, fr=64, fg=64, fb=64)
  4  shade(pal6, 0,   64, 8.0,8.0,8.0,      40.0,52.0,63.0)
  5  tavola_colori(SELF,      first=64,  n=64,  fr=48, fg=52, fb=63)
  6  shade(pal6, 128, 16, 0.0,0.0,0.0,      3.25,5.50,7.75)
  7  shade(pal6, 144, 16, 3.25,5.50,7.75,   19.50,24.75,33.00)
  8  shade(pal6, 160, 16, 19.50,24.75,33.00, 66.25,-2.50,48.125)
  9  shade(pal6, 176, 16, 66.25,-2.50,48.125, 64.0,64.0,64.0)
 10  tavola_colori(SELF,      first=128, n=64,  fr=64, fg=64, fb=64)
 11  rebuild the LUT from curpal6:  pal[c] = (r*4)<<16 | (g*4)<<8 | (b*4)
  tavola_colori: copy n*3 from src into pal6[first*3..] (SELF = filter in
  place, no copy); then v = v*f/63 with integer truncation, clamped to 63;
  then upload curpal6[0 .. (first+n)*3) <- pal6, ALWAYS starting at colour 0.
  shade: v = trunc(from + (to-from)*i/n) per component, then the original's
  inverted clamp -- if not (v >= 0 and v < 64) then v = (v > 0) ? 63 : 0.
  range8088 is the 64-entry ramp of NOCTIS-0.CPP:166-241.
  Steps 4-5 exist to make the upload-from-zero rule observable: step 4 writes
  band 0 WITHOUT uploading, and step 5's sky call is what carries it to the DAC.

SCENARIO "page"  -> kind 1 (adapted 320x200), kind 1 (adaptor 320x200),
                    kind 1 (glyph 256x36)
  1  QUADWORDS = 16000        ; pclear(adaptor, 0)
  2  QUADWORDS = 16000 - 1440 ; pclear(adapted, 7)      <- 14560 dwords, NOT 64000 bytes
  3  seed with Borland's LCG, state = state*0x015A4E35 + 1,
     rand = (state >> 16) & 0x7FFF, srand(1996) sets state = 1996:
       n_globes_map[i]   = rand() & 63          for i in 0..32767
       s_background[i]   = 128 + (rand() & 63)  for i in 0..4095
  4  sea texture sweep, i in 0..31999:
       u = (i*517) & 0xFFFF ;  v = (i*1031) & 0xFFFF
       texel = ((v>>8) & 0xFF)*256 + ((u>>8) & 0xFF)        <- 16-bit, TDPOLYGS.H:2817
       adapted[i] = NW[n_globes_map + texel]                <- overruns, class C
  5  digit_at('A', x = 104, y = 1) with txtr based at p_surfacemap,
     INCLUDING the txtr[-6..-1] underflow -- loop from n = 0, not n = 1
  6  adapted[32000 + i] = NW[p_surfacemap - 5 + i]  for i in 0..9215
  7  adapted[63996] = 0x37 ; adapted[63997] = 0x5B        <- tinta/escrescenze,
     at 63996, NOT at 64000 (that is niv-lr's divergence)
  8  areaclear(adaptor, x=2, y=191, w=316, h=7, colour=127)
  9  QUADWORDS = 16000 ; pcopy(adaptor, adapted)
 10  the glyph record is NW[p_surfacemap - 5 + i] for i in 0..9215, as 256x36

  Pads are in the RELEASE state (zero) for every record above.  The canary
  poison must be written, checked and CLEARED only around the kind-6 record --
  5 of the 32000 texels in step 4 land in a pad, so poison left in place
  changes the adapted page.

CANARY (kind 6): poison all nine pads plus the low pad and the top pad with
  0xA5A5A5A5, then emit (expected, actual) per region.  A clean debug check is
  therefore expected == actual == 0xA5A5A5A5.
"""


# ----------------------------------------------------------- containers
#
# FBDUMP v1 describes ONE record: a 16-unit header and its payload.  It does
# not say a file holds only one, and implementer 1 concatenates every record of
# a run into a single .bin.  That is a legal reading, so the grader accepts it:
# a --lino argument may be a single multi-record file, or a directory, in which
# case every .bin inside it is read and its records pooled.


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
        if h[1] != 1:
            raise SystemExit("%s: FBDUMP version %d, expected 1" % (path, h[1]))
        cnt = h[5]
        end = off + 64 + 4 * cnt
        if end > len(d):
            raise SystemExit("%s: record at %d claims %d units but the file ends" % (path, off, cnt))
        out.append({"kind": h[2], "width": h[3], "height": h[4], "count": cnt,
                    "cpms": h[6], "ticks": h[7],
                    "payload": list(struct.unpack("<%dI" % cnt, d[off + 64:end])),
                    "raw": d[off:end], "offset": off, "path": path})
        off = end
    if off != len(d):
        raise SystemExit("%s: %d trailing bytes after the last record" % (path, len(d) - off))
    return out


def write_record(path, rec):
    """Re-emit one record from a container as a standalone FBDUMP, so the
    existing exact comparer and the tick grader can be pointed straight at it."""
    with open(path, "wb") as fh:
        fh.write(rec["raw"])
    return path


# ------------------------------------------------------------- compare core


def compare_dumps(pa, pb, label_a="A", label_b="B", show=6):
    """Exact unit-for-unit compare of two FBDUMPs.  Returns (ok, lines)."""
    lines = []
    try:
        a = fbdump_read(pa)
        b = fbdump_read(pb)
    except Exception as exc:
        return False, ["    ERROR %s" % exc]

    if a["kind"] != b["kind"]:
        return False, ["    kind mismatch: %s=%s %s=%s"
                       % (label_a, KIND_NAME.get(a["kind"]), label_b, KIND_NAME.get(b["kind"]))]
    if a["count"] != b["count"]:
        return False, ["    count mismatch: %s=%d %s=%d" % (label_a, a["count"], label_b, b["count"])]
    if a["kind"] == KIND_INDEXPAGE and (a["width"], a["height"]) != (b["width"], b["height"]):
        return False, ["    geometry mismatch: %dx%d vs %dx%d"
                       % (a["width"], a["height"], b["width"], b["height"])]

    pa_, pb_ = a["payload"], b["payload"]
    diff = [i for i in range(len(pa_)) if pa_[i] != pb_[i]]
    if not diff:
        lines.append("    %s == %s  (%d units of %s, exact)"
                     % (label_a, label_b, a["count"], KIND_NAME.get(a["kind"], a["kind"])))
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
            fld = ["base", "size", "padbase", "rid"][i % 4]
            lines.append("      region %d field %-7s  %s=%d  %s=%d"
                         % (i // 4, fld, label_a, pa_[i], label_b, pb_[i]))
        elif k == KIND_CANARY:
            lines.append("      region %d %s  %s=%08X  %s=%08X"
                         % (i // 2, ["expected", "actual"][i % 2], label_a, pa_[i], label_b, pb_[i]))
        else:
            lines.append("      unit %6d  %s=%d  %s=%d" % (i, label_a, pa_[i], label_b, pb_[i]))
    if len(diff) > show:
        lines.append("      ... and %d more" % (len(diff) - show))
    return False, lines


# ---------------------------------------------------------------- the suite


class Suite(object):
    def __init__(self, linosrc=None, verbose=False, linobreaks=()):
        self.linosrc = linosrc
        self.linobreaks = list(linobreaks)
        self.verbose = verbose
        self.rows = []       # (tier, name, ok, detail)

    def rec(self, tier, name, ok, detail=""):
        self.rows.append((tier, name, ok, detail))
        print("  [%s] %-56s %s%s" % (tier, name, "PASS" if ok else "FAIL",
                                     ("  " + detail) if detail and not ok else ""))
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
        if self.verbose:
            for m in msg:
                print("      " + m)
        fbdump_write(os.path.join(OUT, "fb-py-layout.bin"), KIND_LAYOUT, layout_payload(lay))

        # sabotages of the layout itself
        from fb_layout import BREAKS as LBREAKS
        for b in sorted(LBREAKS):
            bad, _ = Layout([b]).check()
            self.rec("T3", "layout sabotage %-14s is rejected" % b, not bad)
        return ok

    # -- tier 2: three-way agreement -------------------------------------

    def tier2_c_vs_py(self):
        print("\nTier 2 -- fb_ref.c vs the Python references (independent constructions)")
        ok, log = self.build_c(os.path.join(HERE, "fb_ref.exe"))
        if not self.rec("T2", "fb_ref.c builds clean with -Wall -Wextra", ok, log[:200]):
            return False
        rc, out = self.run_c(os.path.join(HERE, "fb_ref.exe"), OUT)
        self.rec("T2", "fb_ref.exe self-test passes", rc == 0,
                 "\n".join(l for l in out.splitlines() if "FAIL" in l))
        if self.verbose:
            print(out)

        # layout: C transcribes, Python parses.  They must agree.
        good, lines = compare_dumps(os.path.join(OUT, "fb-py-layout.bin"),
                                    os.path.join(OUT, "fb-ref-layout.bin"), "py", "C")
        self.rec("T2", "LAYOUT: fb_layout.py (parsed) == fb_ref.c (transcribed)", good)
        for l in lines:
            if not good or self.verbose:
                print(l)

        # palette: two implementations of tavola_colori/shade/LUT
        p = fb_pal.scenario_surface()
        fbdump_write(os.path.join(OUT, "fb-py-pal6.bin"), KIND_PALETTE6, p.pal6)
        fbdump_write(os.path.join(OUT, "fb-py-lut.bin"), KIND_LUT, p.lut())
        for what in ("pal6", "lut"):
            good, lines = compare_dumps(os.path.join(OUT, "fb-py-%s.bin" % what),
                                        os.path.join(OUT, "fb-ref-%s.bin" % what), "py", "C")
            self.rec("T2", "%s: fb_pal.py == fb_ref.c (scenario 'surface')" % what.upper(), good)
            for l in lines:
                if not good or self.verbose:
                    print(l)

        # the buffer model itself: the page scenario, computed independently in
        # Python.  This is what puts the class-C read overrun, QUADWORDS, the
        # texel address and digit_at under a two-implementation check rather
        # than only under C-versus-its-own-sabotage.
        from fb_layout import Workspace
        w = Workspace()
        w.scenario_page()
        census, padhits = w.overrun_census()
        self.rec("T3", "sea texture actually overruns n_globes_map: %d of 32000 texels "
                       "land past its end, so farmalloc order is under test" % census, census > 0)
        # LINOBUF 2.4 records the 16-unit pad as the one knowing divergence
        # from DOS, on the grounds that no audited read-overrun is proven to
        # sample it.  The 16-bit texel address reaches it directly -- texels
        # 32768..32783 ARE the pad -- so pad contents are observable, and a
        # grading run must use the release (zero) pad state, not the poisoned
        # debug one.  Leaving the poison in place is what made C and Python
        # disagree in exactly these units.
        self.rec("T3", "pad IS reachable by the texel address: %d of those %d land in the "
                       "16-unit pad, so release-state pads are load-bearing" % (padhits, census),
                 padhits > 0)
        fbdump_write(os.path.join(OUT, "fb-py-adapted.bin"), KIND_INDEXPAGE,
                     w.page("adapted"), width=320, height=200)
        fbdump_write(os.path.join(OUT, "fb-py-adaptor.bin"), KIND_INDEXPAGE,
                     w.page("adaptor"), width=320, height=200)
        fbdump_write(os.path.join(OUT, "fb-py-glyph.bin"), KIND_INDEXPAGE,
                     w.glyph_plane(), width=256, height=36)
        for what in ("adapted", "adaptor", "glyph"):
            good, lines = compare_dumps(os.path.join(OUT, "fb-py-%s.bin" % what),
                                        os.path.join(OUT, "fb-ref-%s.bin" % what), "py", "C")
            self.rec("T2", "%s: fb_layout.Workspace == fb_ref.c (page scenario)" % what.upper(), good)
            for l in lines:
                if not good or self.verbose:
                    print(l)

        # and the Python side's own sabotages of the buffer model
        for b, target in (("DIGITN1", "glyph"), ("TINTA64000", "adapted"), ("QUADWORDS", "adapted")):
            wb = Workspace(breaks=[b])
            wb.scenario_page()
            got = wb.glyph_plane() if target == "glyph" else wb.page(target)
            ref = w.glyph_plane() if target == "glyph" else w.page(target)
            self.rec("T2", "Workspace sabotage %-11s changes %s" % (b, target), got != ref)

        # palette self-test and tick self-test, in their own constructions
        pok, _ = fb_pal.selftest()
        self.rec("T2", "fb_pal.py self-test", pok)
        rc = fb_tick.main(["--wrap-sweep"])
        self.rec("T2", "fb_tick.py arithmetic + 1.5M-case wrap sweep", rc == 0)
        return True

    # -- tier 2b: the sabotages of the C reference -----------------------

    def tier2_sabotage(self):
        print("\nTier 2 -- every single-edit sabotage of fb_ref.c must be REJECTED")
        base = {}
        for what in ("layout", "pal6", "lut", "adapted", "adaptor", "glyph", "canary"):
            base[what] = os.path.join(OUT, "fb-ref-%s.bin" % what)
        allok = True
        for define, desc, target in C_BREAKS:
            exe = os.path.join(HERE, "fb_brk.exe")
            odir = os.path.join(OUT, "brk")
            bok, log = self.build_c(exe, [define])
            if not bok:
                allok &= self.rec("T2", "sabotage %-20s builds" % define, False, log[:200])
                continue
            rc, out = self.run_c(exe, odir)
            if target == "selftest":
                caught = rc != 0
                detail = "self-test still passed"
            else:
                good, _ = compare_dumps(base[target], os.path.join(odir, "fb-ref-%s.bin" % target))
                caught = (not good) or rc != 0
                detail = "%s compare still matched and self-test passed" % target
            allok &= self.rec("T2", "sabotage %-20s caught by %-8s (%s)" % (define, target, desc),
                              caught, detail)
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
                idx, pal6, pal8, info = fb_bmp.load_any(path)
                loaded[f] = (idx, pal6, pal8, info)
            except Exception as exc:
                self.rec("T1", "decode %s" % f, False, str(exc))

        # T1a -- the game's own writer scales the DAC by x4, not (v<<2)|(v>>4).
        # This grades LINOBUF's 6->8 decision against the 1996 binary.
        for f in bmps:
            a = fb_bmp.scale_audit(loaded[f][2])
            self.rec("T1", "%s: DAC scaling is x4, not shift-or (mod4 %s, max %d)"
                     % (f, a["mod4_histogram"], a["max"]),
                     a["consistent_with_x4"] and not a["consistent_with_shift_or"])
        for f in pngs:
            a = fb_bmp.scale_audit(loaded[f][2])
            self.rec("T1", "%s: DOSBox writes shift-or, so the two routes need different inverses" % f,
                     a["consistent_with_shift_or"] and not a["consistent_with_x4"])

        # T1b -- the two routes agree EXACTLY on the 6-bit DAC once each is
        # inverted correctly.  If they did not, neither could be an oracle.
        if bmps and pngs:
            a6 = loaded[bmps[0]][1]
            b6 = loaded[pngs[0]][1]
            d = [i for i in range(768) if a6[i] != b6[i]]
            raw = [i for i in range(768) if loaded[bmps[0]][2][i] != loaded[pngs[0]][2][i]]
            self.rec("T1", "snapshot BMP and DOSBox PNG agree on all 768 6-bit DAC "
                           "components (raw 8-bit bytes differ in %d)" % len(raw), not d,
                     "%d differ" % len(d))

        # T1c -- tavola_colori's filter arithmetic, fitted from the capture.
        # One integer per channel over 64 samples; the falsifiers must find
        # nothing at all.
        for f in bmps:
            fit = fb_pal.tier1_palette_audit(loaded[f][1])
            got = all(fit[c] for c in "RGB")
            self.rec("T1", "%s: band 0-63 is range8088 filtered by v*f/63 exactly, "
                           "f = (%s,%s,%s)" % (f, fit["R"], fit["G"], fit["B"]), got)
            self.rec("T1", "%s: falsifier round-to-nearest fits nothing (%s)"
                     % (f, fit["_round_to_nearest_fits"] or "none"), not fit["_round_to_nearest_fits"])
            self.rec("T1", "%s: falsifier /64 fits nothing (%s)"
                     % (f, fit["_div64_fits"] or "none"), not fit["_div64_fits"])

        # T1d -- the raw PNG really is a 2x2 doubled mode-13h plane.  Measured,
        # not assumed: every 2x2 block must be uniform.
        for f in pngs:
            self.rec("T1", "%s: 2x2 doubling verified, %d non-uniform subpixels"
                     % (f, loaded[f][3]["nonuniform_subpixels"]),
                     loaded[f][3]["nonuniform_subpixels"] == 0)

        # T1e -- state pinning.  Two snapshots from the same session differ,
        # which is why an unpinned frame is a picture and not an oracle.
        if len(bmps) >= 2:
            a, b = loaded[bmps[0]][0], loaded[bmps[1]][0]
            npx = sum(1 for i in range(len(a)) if a[i] != b[i])
            pa, pb = loaded[bmps[0]][1], loaded[bmps[1]][1]
            npal = sum(1 for i in range(768) if pa[i] != pb[i])
            self.rec("T1", "two unpinned snapshots differ in %d/64000 pixels but %d/768 "
                           "palette components -- the palette is the stable object" % (npx, npal),
                     npal == 0)
        return True

    # -- tier 3: the tick ------------------------------------------------

    def tier3_tick(self):
        print("\nTier 3 -- tick, recomputed from raw TICKLOGs")
        cpms = 9000
        exact = float(fb_tick.PERIOD_MS) * cpms
        work = [int(exact * 0.04)] * 400
        work[100] = int(exact * 1.4)
        work[250] = int(exact * 2.6)
        # NOCARRY is a ~0.7 count/tick truncation.  Against the OLD K3 -- a
        # 1 ms budget for the whole log -- it was invisible in 400 ticks and
        # needed a 20,000-tick soak.  The rewritten K3 grades the accumulation
        # inside each constant-cpms run against the exact rational with the
        # carry's own bound of ONE COUNT, which is where the truncation shows up
        # after two ticks.  The long soak is kept anyway: it is the one that
        # demonstrates the growth is LINEAR rather than a one-off.
        longwork = [int(exact * 0.04)] * 20000
        specs = [("clean", (), work)] + [(b, (b,), work) for b in ("REBASE", "NOSKIP", "ROUND55")]
        specs.append(("NOCARRY", ("NOCARRY",), longwork))
        results = {}
        for name, brk, work_ in specs:
            pay = fb_tick.run_loop(cpms, work_, brk)
            path = os.path.join(OUT, "tick-%s.bin" % name)
            fb_tick.write_ticklog(path, pay, cpms, len(pay) // 3)
            ok, msg, stats = fb_tick.grade_ticklog(path)
            results[name] = (ok, msg, stats)
        ok0, msg0, st0 = results["clean"]
        self.rec("T3", "clean tick loop passes K1..K5 (drift %.5f ms over %d grid steps)"
                 % (st0["drift_ms"], st0["grid_steps"]), ok0)
        if self.verbose or not ok0:
            for m in msg0:
                print("      " + m)
        # the former blind spot, re-measured after K3 was tightened
        shortpay = fb_tick.run_loop(cpms, work, ("NOCARRY",))
        sp = os.path.join(OUT, "tick-NOCARRY-400.bin")
        fb_tick.write_ticklog(sp, shortpay, cpms, len(shortpay) // 3)
        sok, _, sst = fb_tick.grade_ticklog(sp)
        self.rec("T3", "NOCARRY is now caught in a 400-tick log too (%.1f counts adrift; the old "
                 "1 ms/log budget missed it at %.4f ms)"
                 % (sst["drift_worst_segment_counts"], sst["drift_ms"]), not sok)

        # -- controls on the SERVO leniency ------------------------------
        # K2/K3 grade per constant-cpms run because a conforming port
        # recalibrates (LINOBUF 5.5 rule 5).  That leniency has to be fenced,
        # or "the period changed" becomes an excuse for any drift at all.
        servo = fb_tick.run_loop(cpms, work, servo={256: cpms + 1})
        svp = os.path.join(OUT, "tick-SERVO1.bin")
        fb_tick.write_ticklog(svp, servo, cpms + 1, len(servo) // 3)
        vok, _, vst = fb_tick.grade_ticklog(svp)
        self.rec("T3", "a legitimate 1-count servo step is ACCEPTED (%s, spread %.4f%%)"
                 % ("->".join(str(s["cpms"]) for s in vst["segments"]),
                    100.0 * (max(s["cpms"] for s in vst["segments"])
                             - min(s["cpms"] for s in vst["segments"])) / cpms), vok)
        # and a 5% lurch is not
        wild = fb_tick.run_loop(cpms, work, servo={256: int(cpms * 1.05)})
        wp = os.path.join(OUT, "tick-SERVOWILD.bin")
        fb_tick.write_ticklog(wp, wild, cpms, len(wild) // 3)
        wok, wmsg, _ = fb_tick.grade_ticklog(wp)
        which = [m.split()[1] for m in wmsg if m.startswith("  FAIL")]
        self.rec("T3", "a 5%% cpms lurch is REJECTED (by %s) -- the segment split is not a "
                 "licence to drift" % (",".join(which) or "-"), not wok)
        for name, _, _ in specs[1:]:
            ok, msg, _ = results[name]
            which = [m.split()[1] for m in msg if m.startswith("  FAIL")]
            self.rec("T3", "tick sabotage %-8s rejected (by %s)" % (name, ",".join(which) or "-"), not ok)
        return ok0

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
        print("      %s: %d FBDUMP records, %s"
              % (os.path.basename(self.linosrc), len(recs),
                 ", ".join("%s x%d" % (KIND_NAME.get(k, "kind%d" % k), v)
                           for k, v in sorted(collections.Counter(r["kind"] for r in recs).items()))))
        by = collections.defaultdict(list)
        for r in recs:
            by[r["kind"]].append(r)
        allok = True

        # -- LAYOUT (kind 5) : scenario-free, and the whole point of Decision 2
        if by[5]:
            allok &= self.lino_layout(by[5][0])
        else:
            allok &= self.rec("T2", "lino LAYOUT record present", False, "missing")

        # -- CANARY (kind 6) : scenario-free
        if by[6]:
            lp = os.path.join(OUT, "fb-lino-canary.bin")
            write_record(lp, by[6][0])
            good, lines = compare_dumps(lp, os.path.join(OUT, "fb-ref-canary.bin"), "lino", "C")
            allok &= self.rec("T2", "lino CANARY == fb_ref.c (all %d pads intact, "
                                    "expected==actual==A5A5A5A5)" % (len(by[6][0]["payload"]) // 2), good)
            for l in lines:
                if not good or self.verbose:
                    print(l)
        else:
            allok &= self.rec("T2", "lino CANARY record present", False, "missing")

        # -- TICKLOG (kind 4) : scenario-free
        if by[4]:
            lp = os.path.join(OUT, "fb-lino-ticklog.bin")
            write_record(lp, by[4][0])
            ok, msg, stats = fb_tick.grade_ticklog(lp)
            allok &= self.rec("T2", "lino TICKLOG passes K1..K5 (%d ticks, %d grid steps, worst "
                                    "in-run drift %.4f counts)"
                              % (stats["ticks"], stats["grid_steps"],
                                 stats["drift_worst_segment_counts"]), ok)
            for m in msg:
                if m.startswith("  FAIL") or self.verbose:
                    print("      " + m)
            print("      periods in force: %s"
                  % " -> ".join("cpms %d for %d grid steps (%.4f counts adrift)"
                                % (s["cpms"], s["grid_steps"], s["drift_counts"])
                                for s in stats["segments"]))
            print("      fps %.2f, tick multiples %s, max frame %.2f ms"
                  % (stats["implied_fps"], stats["tick_multiple_histogram"],
                     stats["measured_max_gap_ms"]))
        else:
            allok &= self.rec("T2", "lino TICKLOG record present", False, "missing")

        # -- the scenario-DEPENDENT kinds ---------------------------------
        allok &= self.lino_scenario(by)

        # -- implementer 1's own sabotaged builds -------------------------
        if self.linobreaks:
            allok &= self.lino_break_matrix(recs)

        # -- records outside FBDUMP v1 ------------------------------------
        extra = sorted(k for k in by if k not in (1, 2, 3, 4, 5, 6))
        if extra:
            print("      NOT GRADED: %s carry kinds %s, which FBDUMP v1 (LINOBUF 6) does not"
                  % (os.path.basename(self.linosrc), extra))
            print("      define.  An undefined kind has no agreed payload, so there is nothing")
            print("      to compare against; they are reported, not silently accepted.")
            for k in extra:
                print("        kind %d: %d record(s), %d units, first units %s"
                      % (k, len(by[k]), by[k][0]["count"], by[k][0]["payload"][:6]))
        return allok

    def lino_break_matrix(self, clean):
        """Implementer 1 ships ten deliberately broken builds.  A grader that
        cannot tell them from the clean one is not grading anything, so run
        every one of them through and say exactly which this grader catches --
        and, just as importantly, which it CANNOT, and why."""
        print("\n      implementer 1's sabotaged builds, through this grader:")
        cleanby = collections.defaultdict(list)
        for r in clean:
            cleanby[r["kind"]].append(r)
        allok = True
        for path in self.linobreaks:
            name = os.path.splitext(os.path.basename(path))[0]
            try:
                recs = read_container(path)
            except SystemExit as exc:
                self.rec("T2", "lino sabotage %-11s rejected (container: %s)" % (name, exc), True)
                continue
            by = collections.defaultdict(list)
            for r in recs:
                by[r["kind"]].append(r)
            caught, blind = [], []
            # the three kinds this grader can actually judge without a scenario
            if by[5]:
                ref = fbdump_read(os.path.join(OUT, "fb-ref-layout.bin"))["payload"]
                got = by[5][0]["payload"]
                n = min(len(ref), len(got)) // 4
                if len(got) != len(ref) or any(
                        (got[4 * i], got[4 * i + 1], got[4 * i + 3])
                        != (ref[4 * i], ref[4 * i + 1], ref[4 * i + 3]) for i in range(n)):
                    caught.append("LAYOUT")
            else:
                caught.append("LAYOUT missing")
            if by[6]:
                if any(by[6][0]["payload"][2 * i] != by[6][0]["payload"][2 * i + 1]
                       for i in range(len(by[6][0]["payload"]) // 2)):
                    caught.append("CANARY")
            else:
                caught.append("CANARY missing")
            if by[4]:
                p = os.path.join(OUT, "brk", "%s-ticklog.bin" % name)
                os.makedirs(os.path.dirname(p), exist_ok=True)
                write_record(p, by[4][0])
                ok, msg, _ = fb_tick.grade_ticklog(p)
                if not ok:
                    caught.append("TICKLOG(%s)" % ",".join(m.split()[1] for m in msg
                                                           if m.startswith("  FAIL")))
            # kinds 1/2/3 differ from the clean build -- a difference, but not
            # a verdict, because there is no agreed scenario to judge against
            undef = []
            for k in sorted(by):
                if k in (4, 5, 6):
                    continue
                for j, r in enumerate(by[k]):
                    if j >= len(cleanby[k]) or r["payload"] == cleanby[k][j]["payload"]:
                        continue
                    tag = "%s#%d" % (KIND_NAME.get(k, "kind%d" % k), j)
                    (blind if k in (1, 2, 3) else undef).append(tag)
            if caught:
                self.rec("T2", "lino sabotage %-11s CAUGHT by %s" % (name, ",".join(caught)), True)
            elif blind:
                allok &= self.rec(
                    "T2", "lino sabotage %-11s NOT caught -- moves %s, scenario-dependent "
                          "and so ungraded" % (name, ",".join(blind)), False, "blind spot")
            else:
                allok &= self.rec(
                    "T2", "lino sabotage %-11s NOT caught -- moves NOTHING in any FBDUMP v1 "
                          "kind; its only effect is on %s" % (name, ",".join(undef) or "no record"),
                    False, "evidence is in an undefined kind")
        print("      A 'NOT caught' row is a limit of THIS grader, never a pass for the build.")
        print("      Two distinct causes, and they need different fixes:")
        print("        - 'scenario-dependent': the sabotage does move a specified kind, but")
        print("          kinds 1/2/3 stay ungraded until both sides run the pinned scenario")
        print("          (fb_compare.py --scenario-spec).  Pinning it closes these.")
        print("        - 'evidence is in an undefined kind': the sabotage's whole visible")
        print("          effect is on a record FBDUMP v1 does not define, so no independent")
        print("          grader can read the verdict.  A self-test result that travels only")
        print("          in a private format is exactly what two implementations were")
        print("          supposed to avoid; it needs a specified kind, or a scenario that")
        print("          makes the effect show up in kinds 1/2/3/4/5/6.")
        return allok

    def lino_layout(self, rec):
        """Kind 5 is 4 units per region.  Grade the SUBSTANCE (base, size,
        region id) separately from the third column, because a disagreement in
        one of those is a different animal from a disagreement in the other."""
        ref = fbdump_read(os.path.join(OUT, "fb-ref-layout.bin"))["payload"]
        got = rec["payload"]
        if len(got) != len(ref):
            return self.rec("T2", "lino LAYOUT has %d units (ref %d)" % (len(got), len(ref)), False)
        n = len(ref) // 4
        bad_sub = [i for i in range(n)
                   if (got[4 * i], got[4 * i + 1], got[4 * i + 3])
                   != (ref[4 * i], ref[4 * i + 1], ref[4 * i + 3])]
        ok = self.rec("T2", "lino LAYOUT base/size/region-id == fb_layout.py and fb_ref.c "
                            "for all %d regions (%d of %d units exact)"
                      % (n, 3 * n - 3 * len(bad_sub), 3 * n), not bad_sub)
        if bad_sub:
            for i in bad_sub[:5]:
                print("        region %d: lino (%d,%d,rid %d) vs ref (%d,%d,rid %d)"
                      % (i, got[4 * i], got[4 * i + 1], got[4 * i + 3],
                         ref[4 * i], ref[4 * i + 1], ref[4 * i + 3]))
        # the third column
        third_ok = all(got[4 * i + 2] == ref[4 * i + 2] for i in range(n))
        as_end = all(got[4 * i + 2] == got[4 * i] + got[4 * i + 1] for i in range(n))
        ok &= self.rec("T2", "lino LAYOUT third column is the PAD BASE that FBDUMP v1 kind 5 "
                             "specifies%s"
                       % ("" if third_ok else
                          " -- it is the region END (base+size) instead, on all %d regions%s"
                          % (n, "; consistently so" if as_end else "; inconsistently")),
                       third_ok)
        if not third_ok and as_end:
            print("        Diagnosis is exact and the geometry is NOT in dispute: lino's")
            print("        end[k] equals the reference's padbase[k+1] for every k, so both")
            print("        sides describe the same nine regions and the same sixteen-unit")
            print("        pads.  It is a field-semantics defect in the writer, not a layout")
            print("        defect.  LINOBUF 6 kind 5 reads 'base, size, pad base, region id'")
            print("        and LINOBUF 2.3's table gives the pad base as the pad PRECEDING")
            print("        each region (n_offsets_map -> 16, n_globes_map -> 7372).")
        return ok

    def lino_scenario(self, by):
        """PALETTE6 / LUT / INDEXPAGE cannot be graded until the two sides run
        the SAME scenario, and FBDUMP v1 does not pin one.  Say so, prove it is
        a scenario difference rather than a substantive one where that can be
        shown, and refuse to report either a pass or a fail."""
        interesting = [k for k in (1, 2, 3) if by[k]]
        if not interesting:
            return True
        print("      NOT GRADED (blocked, not failed): kinds %s -- PALETTE6, LUT and"
              % interesting)
        print("      INDEXPAGE are functions of the SCENARIO, and FBDUMP v1 pins the")
        print("      container but no scenario.  The two sides ran different ones, so a")
        print("      compare here would measure the disagreement of the test inputs, not")
        print("      of the implementations.  Run `fb_compare.py --scenario-spec` for the")
        print("      pinned scenario this side emits; when the lino side runs it, these")
        print("      become exact compares and this text goes away.")
        for k in interesting:
            for j, r in enumerate(by[k]):
                pay = r["payload"]
                cand = {1: ["adapted", "adaptor", "glyph"], 2: ["pal6"], 3: ["lut"]}[k]
                best = None
                for c in cand:
                    p = os.path.join(OUT, "fb-ref-%s.bin" % c)
                    if not os.path.exists(p):
                        continue
                    ref = fbdump_read(p)["payload"]
                    if len(ref) != len(pay):
                        continue
                    same = sum(1 for a, b in zip(pay, ref) if a == b)
                    if best is None or same > best[1]:
                        best = (c, same, len(ref))
                if best:
                    print("        kind %d rec %d (%d units): best match is fb-ref-%s at %d/%d units"
                          % (k, j, len(pay), best[0], best[1], best[2]))
        return True

    def run(self):
        os.makedirs(OUT, exist_ok=True)
        print("fb_compare.py -- Wave 5 grader")
        print("  references : fb_ref.c (C), fb_layout.py / fb_pal.py / fb_tick.py (Python)")
        print("  captures   : %s" % CAPS)
        print("  lino       : %s" % (self.linosrc or "NOT SUPPLIED -- lino side outstanding"))
        self.tier3_layout()
        self.tier2_c_vs_py()
        self.tier2_sabotage()
        self.tier1_capture()
        self.tier3_tick()
        linoresult = self.lino()

        npass = sum(1 for r in self.rows if r[2])
        nfail = len(self.rows) - npass
        print("\n" + "=" * 74)
        for tier in ("T1", "T2", "T3"):
            rows = [r for r in self.rows if r[0] == tier]
            print("  %s  %d checks, %d failed" % (tier, len(rows), sum(1 for r in rows if not r[2])))
        print("  TOTAL %d checks, %d passed, %d failed" % (len(self.rows), npass, nfail))
        if linoresult is None:
            print("  LINO SIDE: OUTSTANDING -- not present, not graded, not claimed.")
        print("  RESULT: %s" % ("PASS" if nfail == 0 else "FAIL"))
        print("=" * 74)
        return 0 if nfail == 0 else 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("pair", nargs="*", help="two FBDUMP files to compare")
    ap.add_argument("--suite", action="store_true")
    ap.add_argument("--lino", metavar="PATH",
                    help="implementer 1's FBDUMP: a multi-record .bin, or a directory of them")
    ap.add_argument("--scenario-spec", action="store_true",
                    help="print the pinned scenario the references emit, so the lino side "
                         "can reproduce it and the scenario-dependent kinds can be graded")
    ap.add_argument("--lino-break", metavar="PATH", action="append", default=[],
                    help="a deliberately broken lino FBDUMP; repeatable, globs accepted")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    if args.scenario_spec:
        print(SCENARIO_SPEC)
        return 0
    if args.suite:
        brk = []
        for pat in args.lino_break:
            hits = sorted(glob.glob(pat))
            brk += hits if hits else [pat]
        return Suite(args.lino, args.verbose, brk).run()
    if len(args.pair) == 2:
        ok, lines = compare_dumps(args.pair[0], args.pair[1],
                                  os.path.basename(args.pair[0]), os.path.basename(args.pair[1]))
        print("\n".join(lines))
        return 0 if ok else 1
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
