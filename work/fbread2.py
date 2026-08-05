#!/usr/bin/env python3
"""fbread2.py - walk an FBDUMP v2 stream and print what Wave 5-corrective added.

Reads records by header, so it does not depend on emission order; v2 puts a TAG
in header unit 8 and that is what identifies a record.

Usage: python fbread2.py work/fbmain.bin [--full]
"""
import struct
import sys
import hashlib

MAGIC = 0x46424431
KIND = {1: "PAGE", 2: "PAL6", 3: "LUT", 4: "TICK", 5: "LAY", 6: "CAN",
        7: "SELF", 8: "FRM", 9: "ZONE", 10: "WCNT", 11: "SRVL", 12: "WRAPB"}
TAG = {1: "adapted", 2: "adaptor", 3: "glyph", 4: "pal6", 5: "curpal6",
       6: "lut", 7: "layout", 8: "canary", 9: "zones", 10: "ticklog",
       11: "servolog", 12: "wrapcount", 13: "selfcheck", 14: "framecost",
       15: "wrapbat", 16: "sky", 17: "srfpal6", 18: "retpal6"}

SELFNAME = [
    "bchk", "qchk", "txchk", "txmin", "txmax",
    "canary_clean_fired", "canary_clean_n", "canary_clean_exp",
    "glyph_exp", "glyph_fired",
    "wrap_failures", "wrap_cases", "cpms_reported", "cpms_calibrated",
    "cal_ms", "cal_counts", "tk_base", "tk_subper", "skips", "sleeps",
    "ticks", "ticklog_n", "pv_range", "pvfile_polys", "esc", "luck_raw",
    "display_status", "disp_w", "disp_h", "QWSTEADY", "NWTOP", "last_key",
    "cal_why", "servolog_n", "servolog_overflow", "servo_firings",
    "wallday_ms", "SERVON", "SRVMIN", "SRVMAX", "glyph_violations",
    "containment_failures", "containment_at", "wrap_cases_differing",
    "spot_delta_min", "spot_delta_max", "cirrus_delta_min", "cirrus_delta_max",
    "maskpixels_precondition", "NWCASE", "NZONE", "NPAD",
    "SPBG", "SOBJ", "SADPT", "SADPR", "obj_unshifted_window_top",
    "guard_fired_last", "guard_n_last", "guard_exp_last",
    "MPMASK", "digit", "digit_color", "cal_seed",
]

SVWHY = {0: "applied", 1: "clamped-lo", 2: "clamped-hi",
         3: "rejected-short", 4: "rejected-long"}


def records(buf):
    off = 0
    while off + 64 <= len(buf):
        h = struct.unpack_from("<16I", buf, off)
        if h[0] != MAGIC:
            raise SystemExit("bad magic at unit %d" % (off // 4))
        n = h[5]
        pay = struct.unpack_from("<%dI" % n, buf, off + 64) if n else ()
        yield dict(ver=h[1], kind=h[2], w=h[3], h=h[4], n=n, cpms=h[6],
                   ticks=h[7], tag=h[8]), pay
        off += 64 + 4 * n


def main():
    path = sys.argv[1]
    buf = open(path, "rb").read()
    print("%s  %d bytes  sha256 %s" %
          (path, len(buf), hashlib.sha256(buf).hexdigest()))
    recs = list(records(buf))
    print("%d records" % len(recs))
    by_tag = {}
    for hdr, pay in recs:
        by_tag[hdr["tag"]] = (hdr, pay)
        print("  ver %d kind %-5s tag %-10s n=%-6d w=%d h=%d  fnv=%08X" %
              (hdr["ver"], KIND.get(hdr["kind"], hdr["kind"]),
               TAG.get(hdr["tag"], hdr["tag"]), hdr["n"], hdr["w"], hdr["h"],
               fnv(pay)))

    if 13 in by_tag:
        _, s = by_tag[13]
        print("\n--- self-check words ---")
        for i, nm in enumerate(SELFNAME):
            v = s[i]
            sv = v - (1 << 32) if v >= (1 << 31) else v
            print("  %-28s %12d%s" % (nm, v, "" if sv == v else "  (%d)" % sv))
        print("  range8088 ok:",
              all(s[64 + 3 * k + j] == k for k in range(64) for j in range(3)))

    if 9 in by_tag:
        _, z = by_tag[9]
        print("\n--- zones (kind 9): 22 zones over 11 pads ---")
        for i in range(len(z) // 4):
            b, ln, ow, ro = z[4 * i:4 * i + 4]
            ow = ow - (1 << 32) if ow >= (1 << 31) else ow
            print("  zone %2d pad %2d %-4s base %7d len %2d owner %2d" %
                  (i, i // 2, "TAIL" if ro == 0 else "SUB", b, ln, ow))

    if 8 in by_tag:
        _, c = by_tag[8]
        print("\n--- canary kind 6 v2: 4 units x 11 pads ---")
        print("  pad  clean_read  dirty_read   fired  at      expect fired/at")
        padbase = [0, 16, 7372, 40156, 104972, 170540, 210556, 250572,
                   271068, 336624, 402180]
        ok = True
        for i in range(11):
            cr, dr, fi, at = c[4 * i:4 * i + 4]
            slot = (7 * i + 1) % 12
            exp_clean = 0xA5A5A5A5 if slot < 8 else 0x5A5A5A5A
            exp_dirty = 0xC0DE0000 + i + (exp_clean & 15)
            exp_at = padbase[i] + slot
            good = (cr == exp_clean and dr == exp_dirty and fi == i + 1
                    and at == exp_at)
            ok = ok and good
            print("  %3d  %08X    %08X    %5d  %-7d %5d/%-7d %s" %
                  (i, cr, dr, fi, at, i + 1, exp_at, "OK" if good else "BAD"))
        print("  ALL 11 PADS:", "OK" if ok else "BAD")

    if 12 in by_tag:
        _, w = by_tag[12]
        names = ["spot", "cirrus", "crater", "wave", "stick", "spare"]
        print("\n--- wrap counters (kind 10) ---")
        for i in range(len(w) // 3):
            print("  site %d %-7s calls %8d  wraps %8d" %
                  (w[3 * i], names[w[3 * i]] if w[3 * i] < 6 else "?",
                   w[3 * i + 1], w[3 * i + 2]))

    if 11 in by_tag:
        _, sl = by_tag[11]
        print("\n--- servo log (kind 11): tick, cpms in force, why ---")
        for i in range(len(sl) // 3):
            t, cp, why = sl[3 * i:3 * i + 3]
            print("  tick %6d  cpms %6d  why %d %s" %
                  (t, cp, why, SVWHY.get(why, "?")))

    if 15 in by_tag:
        _, wb = by_tag[15]
        print("\n--- synthetic class-A wrap battery (kind 12), %d cases ---"
              % (len(wb) // 6))
        sd, cd = set(), set()
        nw_s = nw_c = 0
        for i in range(len(wb) // 6):
            py, px, sn, sm, cn, cm = wb[6 * i:6 * i + 6]
            if sn != sm:
                sd.add(sn - sm)
                nw_s += 1
            if cn != cm:
                cd.add(cn - cm)
                nw_c += 1
        print("  spot   : %d of %d cases relocated, deltas %s" %
              (nw_s, len(wb) // 6, sorted(sd)))
        print("  cirrus : %d of %d cases relocated, deltas %s" %
              (nw_c, len(wb) // 6, sorted(cd)))
        for i in (0, 3, 4, 64, 68, 132):
            py, px, sn, sm, cn, cm = wb[6 * i:6 * i + 6]
            print("  case %3d py=%5d px=%5d  spot naive %6d masked %6d | "
                  "cirrus naive %6d masked %6d" % (i, py, px, sn, sm, cn, cm))

    if 16 in by_tag:
        _, sk = by_tag[16]
        print("\n--- sky windows (kind 1 tag 16) ---")
        print("  first 16 of window 0:", list(sk[:16]))
        print("  first 16 of window 1:", list(sk[256:272]))
        # v = ir & 255 -> ((v+1)%64) + ((v>>6)<<6)
        exp0 = [((((ir & 255) + 1) % 64) + (((ir & 255) >> 6) << 6))
                for ir in range(256)]
        exp1 = [((((ir & 255) + 1) % 64) + (((ir & 255) >> 6) << 6))
                for ir in range(64800 - 256, 64800)]
        print("  window 0 matches the cycle:", list(sk[:256]) == exp0)
        print("  window 1 matches the cycle:", list(sk[256:]) == exp1)

    if 10 in by_tag:
        hdr, tl = by_tag[10]
        n = len(tl) // 3
        cpms = by_tag[13][1][13] if 13 in by_tag else hdr["cpms"]
        gaps = []
        for i in range(1, n):
            gaps.append(tl[3 * i + 1] - tl[3 * (i - 1) + 1])
        per = 55 * cpms - (cpms * 44505) / 596591
        print("\n--- tick log (kind 4): %d ticks, cpms %d ---" % (n, cpms))
        if gaps:
            q = sorted(set(round(g / per, 4) for g in gaps))
            print("  deadline gaps in periods:", q[:8], "..." if len(q) > 8 else "")
        over = sorted((tl[3 * i] - tl[3 * i + 1]) / cpms for i in range(n))
        if over:
            print("  overshoot ms: p50 %.6f  p90 %.6f  max %.6f" %
                  (over[n // 2], over[int(n * 0.9)], over[-1]))
        skips = sum(1 for i in range(n) if tl[3 * i + 2] & 1)
        print("  ticks that skipped a grid point:", skips)


def fnv(units):
    h = 0x811C9DC5
    for u in units:
        for b in u.to_bytes(4, "little"):
            h = ((h ^ b) * 0x01000193) & 0xFFFFFFFF
    return h


main()
