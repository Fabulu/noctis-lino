#!/usr/bin/env python3
"""fbread.py - decode an FBDUMP v1 stream produced by the Wave 5 lino shell.

This is implementer 1's own reader.  It is NOT the grader: it recomputes the
statistics from the RAW logs so that no number quoted in a report is one the
lino program computed for itself.

Usage: python fbread.py fbmain.bin [--pal] [--page]
"""
import struct, sys, hashlib

MAGIC = 0x46424431
KIND = {1: "PAGE", 2: "PAL6", 3: "LUT", 4: "TICK", 5: "LAYOUT",
        6: "CANARY", 7: "SELF", 8: "FRAME"}

SELF_NAMES = [
    "bchk", "qchk", "txchk", "txmin", "txmax",
    "canary_clean_fired", "canary_clean_ndiff",
    "canary_dirty_fired", "canary_dirty_ndiff", "canary_dirty_at",
    "wrap_failures", "wrap_cases",
    "cpms_reported", "cpms_calibrated", "cal_ms", "cal_counts",
    "tk_base", "tk_subper", "skips", "sleeps", "ticks", "logn",
    "filter_range_flags", "pvfile_polys", "esc_seen", "luck_raw",
    "display_status", "phys_w", "phys_h", "quadwords_steady",
    "nwtop", "console_key",
]

REGIONS = ["n_offsets_map", "n_globes_map", "s_background", "p_background",
           "p_surfacemap", "objectschart", "pvfile", "adapted", "adaptor"]


def records(data):
    off = 0
    while off + 64 <= len(data):
        h = struct.unpack_from("<16I", data, off)
        assert h[0] == MAGIC, "bad magic at %d: %08X" % (off, h[0])
        assert h[1] == 1, "bad version"
        n = h[5]
        payload = struct.unpack_from("<%dI" % n, data, off + 64) if n else ()
        yield {"kind": h[2], "w": h[3], "h": h[4], "count": n,
               "cpms": h[6], "ticks": h[7], "payload": payload, "off": off}
        off += 64 + 4 * n
    assert off == len(data), "trailing bytes: %d of %d" % (off, len(data))


def pct(xs, p):
    xs = sorted(xs)
    if not xs:
        return 0
    return xs[min(len(xs) - 1, int(p * len(xs)))]


def main():
    path = sys.argv[1]
    data = open(path, "rb").read()
    print("file      %s" % path)
    print("bytes     %d" % len(data))
    print("sha256    %s" % hashlib.sha256(data).hexdigest())
    recs = list(records(data))
    print("records   %d" % len(recs))
    print()

    seen = {}
    for i, r in enumerate(recs):
        k = KIND.get(r["kind"], "?%d" % r["kind"])
        idx = seen.get(k, 0)
        seen[k] = idx + 1
        print("  rec %d  %-6s #%d  count=%-6d w=%d h=%d" %
              (i, k, idx, r["count"], r["w"], r["h"]))
    print()

    by = {}
    for r in recs:
        by.setdefault(r["kind"], []).append(r)

    cpms_cal = None

    # ---- LAYOUT ----
    lay = by[5][0]["payload"]
    print("LAYOUT (farmalloc order)")
    prev_end = None
    ok = True
    for i in range(9):
        base, size, padbase, rid = lay[4 * i:4 * i + 4]
        gap = "" if prev_end is None else "  pad=%d" % (base - prev_end)
        if prev_end is not None and base - prev_end != 16:
            ok = False
            gap += "  <-- NOT 16"
        print("  %-14s base=%-7d size=%-6d padbase=%-7d id=%d%s" %
              (REGIONS[rid], base, size, padbase, rid, gap))
        prev_end = base + size
        if rid != i:
            ok = False
    print("  top=%d   order+pads consistent: %s" % (prev_end + 16, ok))
    print()

    # ---- SELF ----
    slf = by[7][0]["payload"]
    print("SELF-CHECKS")
    for i, nm in enumerate(SELF_NAMES):
        print("  %-22s %d" % (nm, slf[i]))
    cpms_cal = slf[13]
    srv = [(slf[32+2*i], slf[33+2*i]) for i in range(8) if slf[33+2*i]]
    print("  servo updates          %s" % (srv if srv else "none"))
    rng = slf[48:48 + 192]
    rng_ok = all(rng[3 * k + j] == k for k in range(64) for j in range(3))
    print("  range8088 correct      %s" % rng_ok)
    print()

    # ---- CANARY ----
    can = by[6][0]["payload"]
    bad = [(REGIONS[i], hex(can[2 * i]), hex(can[2 * i + 1]))
           for i in range(9) if can[2 * i] != can[2 * i + 1]]
    print("CANARY (clean check)  regions differing: %d %s" % (len(bad), bad))
    print()

    # ---- PALETTE ----
    pal6 = by[2][0]["payload"]
    cur6 = by[2][1]["payload"]
    lut = by[3][0]["payload"]
    print("PALETTE")
    print("  pal6 range        %d..%d" % (min(pal6), max(pal6)))
    print("  curpal6 range     %d..%d" % (min(cur6), max(cur6)))
    diff = [c for c in range(256)
            if pal6[3 * c:3 * c + 3] != cur6[3 * c:3 * c + 3]]
    print("  colours where pal6 differs from curpal6: %d" % len(diff))
    if diff:
        print("    first=%d last=%d  (stale bands: %s)" %
              (diff[0], diff[-1], ranges(diff)))
    lut_ok = all(lut[c] == ((cur6[3 * c] & 63) * 4 << 16)
                 + ((cur6[3 * c + 1] & 63) * 4 << 8)
                 + (cur6[3 * c + 2] & 63) * 4 for c in range(256))
    print("  LUT == curpal6 * 4 for all 256: %s" % lut_ok)
    print("  LUT[0..3]  %s" % [hex(x) for x in lut[:4]])
    print("  LUT[63]    %s   LUT[255] %s" % (hex(lut[63]), hex(lut[255])))
    print()

    # ---- PAGES ----
    for i, r in enumerate(by[1]):
        p = r["payload"]
        name = "adapted (hidden)" if i == 0 else "adaptor (visible)"
        hist = [0] * 256
        for v in p:
            hist[v] += 1
        used = sum(1 for h in hist if h)
        exp_ok = all(p[320 * y + x] == (x * y + x + y) & 255
                     for y in range(0, 200, 7) for x in range(0, 320, 11))
        print("PAGE %d  %s" % (i, name))
        print("  distinct indices  %d / 256" % used)
        print("  pattern matches (x*y+x+y)&255 on a sampled grid: %s" % exp_ok)
        print("  sha256            %s" %
              hashlib.sha256(struct.pack("<%dI" % len(p), *p)).hexdigest())
        if i == 1:
            poke = p[320 * 100 + 128: 320 * 100 + 192]
            print("  type-9 visible-page poke row100 col128..191 all 255: %s"
                  % all(v == 255 for v in poke))
        print()

    # ---- FRAME COSTS ----
    fr = by[8][0]["payload"]
    cpms = cpms_cal
    frames = [fr[2 * i] / cpms for i in range(len(fr) // 2)]
    exps = [fr[2 * i + 1] / cpms for i in range(len(fr) // 2)]
    print("FRAME COST  (ms, %d samples, calibrated cpms=%d)" % (len(frames), cpms))
    for nm, xs in (("full frame", frames), ("expand only", exps)):
        print("  %-12s min=%.4f p50=%.4f p90=%.4f max=%.4f" %
              (nm, min(xs), pct(xs, .5), pct(xs, .9), max(xs)))
    print("  full frame as %% of a 54.9254 ms tick: p50 %.2f%%  max %.2f%%" %
          (100 * pct(frames, .5) / 54.9254012, 100 * max(frames) / 54.9254012))
    print()

    # ---- TICK ----
    tk = by[4][0]["payload"]
    srvlog = [(slf[32 + 2 * i], slf[33 + 2 * i]) for i in range(8)
              if slf[33 + 2 * i]]
    n = len(tk) // 3
    fire = [tk[3 * i] for i in range(n)]
    dead = [tk[3 * i + 1] for i in range(n)]
    flag = [tk[3 * i + 2] for i in range(n)]
    print("TICK  %d ticks logged" % n)
    print("  servo log (tick, cpms in force from there): %s" % srvlog)
    if n > 1:
        def sdiff(a, b):
            d = (a - b) & 0xFFFFFFFF
            return d - 0x100000000 if d >= 0x80000000 else d

        # The servo changes cpms mid-run, which changes the period in COUNTS.
        # Converting the whole log with one factor gets the drift wrong, so
        # each tick is converted with the cpms that was in force at it.
        cpms_at = [0] * n
        cur = srvlog[0][1] if srvlog else cpms_cal
        j2 = 0
        for i in range(n):
            while j2 < len(srvlog) and srvlog[j2][0] <= i:
                cur = srvlog[j2][1]; j2 += 1
            cpms_at[i] = cur

        target = 54.9254012
        per = [sdiff(fire[i], fire[i - 1]) / cpms_at[i] for i in range(1, n)]
        dperc = [sdiff(dead[i], dead[i - 1]) for i in range(1, n)]
        dper = [dperc[i - 1] / cpms_at[i] for i in range(1, n)]
        lat = [sdiff(fire[i], dead[i]) / cpms_at[i] for i in range(n)]
        nskip = sum(1 for f in flag if f & 1)
        nsleep = sum(1 for f in flag if f & 2)
        print("  cpms in force  %d .. %d" % (cpms_at[0], cpms_at[-1]))
        print("  fire-to-fire   min=%.4f p50=%.4f p90=%.4f max=%.4f mean=%.4f ms"
              % (min(per), pct(per, .5), pct(per, .9), max(per),
                 sum(per) / len(per)))
        clean = [p for p, f in zip(per, flag[1:]) if not (f & 1)]
        if clean:
            print("  clean ticks    n=%d mean=%.5f ms  vs %.5f -> %+.5f ms/tick"
                  % (len(clean), sum(clean) / len(clean), target,
                     sum(clean) / len(clean) - target))
        print("  deadline step  min=%.5f p50=%.5f max=%.5f ms"
              % (min(dper), pct(dper, .5), max(dper)))
        print("  lateness       min=%.4f p50=%.4f p90=%.4f max=%.4f ms"
              % (min(lat), pct(lat, .5), pct(lat, .9), max(lat)))
        # exactness of the accumulated deadline, in COUNTS, per segment
        print("  deadline exactness, per cpms segment:")
        segstart = 1
        for si in range(len(srvlog)):
            segend = srvlog[si + 1][0] if si + 1 < len(srvlog) else n
            c = srvlog[si][1]
            ideal = c * 32768000 / 596591.0
            steps = [(dperc[i - 1], round(dperc[i - 1] / ideal))
                     for i in range(max(segstart, 1), segend)]
            if not steps:
                continue
            got = sum(x for x, _ in steps)
            want = sum(k for _, k in steps) * ideal
            gp = sum(k for _, k in steps)
            print("    ticks %4d..%-4d cpms=%d  %d grid points  "
                  "accumulated error %+.4f counts = %+.6f ms"
                  % (segstart, segend - 1, c, gp, got - want, (got - want) / c))
            segstart = segend
        print("  skips=%d sleeps=%d" % (nskip, nsleep))
        bb = [i for i in range(1, n) if per[i - 1] < target * 0.5]
        print("  back-to-back fires (< half a period): %d %s"
              % (len(bb), bb[:10]))
        big = [(i, round(dper[i - 1] / target)) for i in range(1, n)
               if round(dper[i - 1] / target) != 1]
        print("  ticks whose deadline skipped a grid point: %d %s"
              % (len(big), big[:12]))


def ranges(xs):
    out = []
    s = p = xs[0]
    for v in xs[1:]:
        if v == p + 1:
            p = v
        else:
            out.append((s, p)); s = p = v
    out.append((s, p))
    return out


if __name__ == "__main__":
    main()
