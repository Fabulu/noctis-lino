r"""Canonical 29-unit Wave 7b sky corpus.

The checked-in authority is the Python list below.  Text files are generated
inside a test/build sandbox and contain signed decimal integers only, followed
by the single-unit opcode-0 terminator.
"""

import argparse
import os
import struct

import sky_spec as S


def bits(v):
    return struct.unpack("<I", struct.pack("<f", float(v)))[0]


def base(case_id, **kw):
    d = dict(opcode=1, case_id=case_id,
             flags=S.GRADE_PALETTE | S.GRADE_SCALARS,
             ptype=3, sctype=S.OCEAN, atmosphere=1, nightzone=0,
             ip_targetted=3, nearstar_owner=-1, nearstar_class=0,
             global_surface_seed=0x12345678, albedo=40,
             rainy_bits=bits(1.25), sky_brightness_in=48,
             sky_red_filter=45, sky_grn_filter=54, sky_blu_filter=61,
             gnd_red_filter=37, gnd_grn_filter=43, gnd_blu_filter=50,
             dsd1_bits=bits(120.5), exposure_bits=bits(35.25),
             landing_pt_lat=60, quadwords_in=0x13579BDF,
             tail_mode=0, tail_seed=0, bg_start=0, bg_shift=0,
             bg_bytes=S.OFFSET_MAP_BYTES)
    d.update(kw)
    return S.normalize_case(d)


# The anchor's palette proves night.  The old generation-time RAM was not
# retained, so dsd1/exposure are deliberate finite poison values and scalar
# grading is disabled.  Varying them changes only SCALARS, never the anchored
# SBG/palette.  Filters are the corresponding night-adjusted values from the
# same deterministic filter seed; the special-night palette does not consume
# them.  sky_brightness=8 is the source night/crepzone>5 branch.  The final
# SBG distinguishes the later daytime diagnostic's albedo=40 from its own
# generation state and is exact for 31/32; source type-3 albedo quantisation
# permits only the multiple-of-eight value 32.
ANCHOR = base(
    # Inputs are reconstructed from captured outputs and deterministic source
    # constraints, not recovered as one complete contemporaneous RAM state.
    # Therefore this row deliberately does not claim LIVE_REACHABLE.
    1, flags=S.BINARY_ANCHOR | S.GRADE_PALETTE,
    ptype=3, sctype=S.OCEAN, atmosphere=1, nightzone=1,
    global_surface_seed=1029155, albedo=32, rainy_bits=bits(3.75),
    sky_brightness_in=8, sky_red_filter=19, sky_grn_filter=28,
    sky_blu_filter=24, gnd_red_filter=42, gnd_grn_filter=70,
    gnd_blu_filter=44, dsd1_bits=bits(777.25),
    exposure_bits=bits(-123.5), landing_pt_lat=60)


CASES = [
    ("anchor_ocean_night_pixels", ANCHOR),
    ("smoke_airless_type1", base(2, flags=S.GRADE_PALETTE | S.GRADE_SCALARS |
                                  S.LIVE_REACHABLE, ptype=1, sctype=0,
                                  atmosphere=0, nightzone=0,
                                  sky_brightness_in=0, albedo=12)),
    ("ocean_11draw_a", base(3, global_surface_seed=0x00010203, albedo=0)),
    # This row's cloud ledger contains radius 5, so it executes the tight
    # reachable denominator witness r=5,x=-5,y=-4 => denominator 1.  A zero
    # denominator is mathematically outside cloudy_sky's paint predicate.
    ("ocean_11draw_b_min_denominator", base(4, global_surface_seed=0x00010203,
                                             albedo=63)),
    ("ocean_night", base(5, nightzone=1, sky_brightness_in=8)),
    ("ocean_airless_pair", base(6, atmosphere=0)),
    ("plains_undefined", base(7, flags=S.GRADE_SCALARS | S.PALETTE_UNDEFINED |
                               S.LIVE_REACHABLE, sctype=S.PLAINS)),
    ("desert_albedo0", base(8, sctype=S.DESERT, albedo=0,
                             flags=S.GRADE_PALETTE | S.GRADE_SCALARS |
                             S.LIVE_REACHABLE)),
    ("desert_albedo63", base(9, sctype=S.DESERT, albedo=63)),
    ("icy_reachable", base(10, sctype=S.ICY, albedo=60,
                            rainy_bits=bits(0.2), flags=S.GRADE_PALETTE |
                            S.GRADE_SCALARS | S.LIVE_REACHABLE)),
    ("venus_tail_zero", base(11, ptype=2, sctype=0, albedo=23,
                              global_surface_seed=0x76543210,
                              flags=S.GRADE_PALETTE | S.GRADE_SCALARS |
                              S.LIVE_REACHABLE)),
    ("venus_tail_hostile", base(12, ptype=2, sctype=0, albedo=23,
                                 global_surface_seed=0x76543210, tail_mode=1,
                                 tail_seed=0x2468ACE1, flags=S.GRADE_PALETTE |
                                 S.GRADE_SCALARS | S.TAIL_SENSITIVE |
                                 S.LIVE_REACHABLE)),
    ("rocky_type4", base(13, ptype=4, sctype=0, atmosphere=0,
                          sky_brightness_in=0, flags=S.GRADE_PALETTE |
                          S.GRADE_SCALARS | S.LIVE_REACHABLE)),
    ("thin_type5_sixdraw", base(14, ptype=5, sctype=0, albedo=63,
                                 sky_brightness_in=40, flags=S.GRADE_PALETTE |
                                 S.GRADE_SCALARS | S.LIVE_REACHABLE)),
    ("ice_type7", base(15, ptype=7, sctype=0, atmosphere=0,
                        sky_brightness_in=0, flags=S.GRADE_PALETTE |
                        S.GRADE_SCALARS | S.LIVE_REACHABLE)),
    ("milky_type8", base(16, ptype=8, sctype=0, atmosphere=1,
                          flags=S.GRADE_PALETTE | S.GRADE_SCALARS |
                          S.LIVE_REACHABLE)),
    ("undefined_type0", base(17, ptype=0, sctype=0,
                              flags=S.GRADE_SCALARS | S.PALETTE_UNDEFINED)),
    ("undefined_type6", base(18, ptype=6, sctype=0,
                              flags=S.GRADE_SCALARS | S.PALETTE_UNDEFINED)),
    ("zero_colour_scale", base(19, ptype=1, sctype=0, atmosphere=0,
                                nearstar_owner=20, flags=S.GRADE_PALETTE |
                                S.GRADE_SCALARS)),
    ("nearzero_colour_scale", base(20, ptype=1, sctype=0, atmosphere=0,
                                    nearstar_owner=19, flags=S.GRADE_PALETTE |
                                    S.GRADE_SCALARS)),
    ("page_shifted", base(21, ptype=1, sctype=0, atmosphere=0,
                           flags=S.GRADE_PALETTE | S.GRADE_SCALARS |
                           S.GRADE_PAGE, bg_start=37, bg_shift=0xFFFFFD7D,
                           bg_bytes=S.OFFSET_MAP_BYTES)),
    # Venus/nebular optional smoother gates after random(10000): seed1 takes
    # both random(2) ssmooth and random(3) psmooth; 9 isolates psmooth; 24
    # isolates ssmooth.  Together they make both stride families attributable.
    ("venus_both_optional_smoothers", base(23, ptype=2, sctype=0, albedo=23,
                                            global_surface_seed=1,
                                            flags=S.GRADE_PALETTE |
                                            S.GRADE_SCALARS | S.LIVE_REACHABLE)),
    ("venus_psmooth_only", base(24, ptype=2, sctype=0, albedo=23,
                                 global_surface_seed=9,
                                 flags=S.GRADE_PALETTE | S.GRADE_SCALARS |
                                 S.LIVE_REACHABLE)),
    ("venus_ssmooth_only", base(25, ptype=2, sctype=0, albedo=23,
                                 global_surface_seed=24,
                                 flags=S.GRADE_PALETTE | S.GRADE_SCALARS |
                                 S.LIVE_REACHABLE)),
    # Source-float spill witness.  dfs=0.8, sb=2.5, owner scaling, and the
    # class-10 factor must each narrow at the assignment boundary.  Retaining
    # those locals as binary64 changes palette byte 267 from the required 24
    # to 23, while over-rounding individual subexpressions is a separate bug.
    ("float_store_palette_witness", base(
        26, ptype=1, sctype=0, atmosphere=1, nightzone=0,
        nearstar_owner=4, nearstar_class=10, sky_brightness_in=60,
        sky_red_filter=-85, sky_grn_filter=103, sky_blu_filter=64,
        gnd_red_filter=-85, gnd_grn_filter=103, gnd_blu_filter=64,
        flags=S.GRADE_PALETTE | S.GRADE_SCALARS)),
    # Genuine double-expression assignment-boundary witness.  The Venus
    # random-symmetric colour chains contain double literals, so helper-level
    # binary32 spills inside the expression are wrong.  One final store gives
    # PALETTE byte462=53; the old spill-after-every-helper path gives 52.
    ("double_expression_spill_witness", base(
        27, ptype=2, sctype=0, atmosphere=1, nightzone=0,
        nearstar_owner=1, nearstar_class=0,
        global_surface_seed=1543543989, sky_brightness_in=48,
        gnd_red_filter=16, gnd_grn_filter=16, gnd_blu_filter=16,
        flags=S.GRADE_PALETTE | S.GRADE_SCALARS)),
    ("anchor_repeat", dict(ANCHOR, case_id=22)),
]

SMOKE_CASES = [CASES[1]]
SYNTHETIC_CASES = [(name, case) for name, case in CASES
                   if not case["flags"] & S.BINARY_ANCHOR]


def case_units(case):
    c = S.normalize_case(case)
    return [S.u32(c[k]) for k in S.FIELD_NAMES]


def signed_token(v):
    return str(S.i32(v))


def encode_text(named_cases=CASES):
    rows = []
    seen = set()
    for name, case in named_cases:
        c = S.normalize_case(case)
        if c["case_id"] in seen:
            raise ValueError("duplicate case_id %d (%s)" % (c["case_id"], name))
        seen.add(c["case_id"])
        rows.append(" ".join(signed_token(v) for v in case_units(c)))
    rows.append("0")
    return "\n".join(rows) + "\n"


def malformed_matrix():
    """Canonical producer-wide rejection inputs, each malformed one way."""
    vals = case_units(SMOKE_CASES[0][1])
    row = " ".join(signed_token(v) for v in vals)
    bad = {}
    bad["truncated"] = " ".join(signed_token(v) for v in vals[:-1]) + "\n0\n"
    overflow = [signed_token(v) for v in vals]
    overflow[12] = "2147483648"
    bad["int32_overflow"] = " ".join(overflow) + "\n0\n"
    bad["duplicate_id"] = row + "\n" + row + "\n0\n"
    page = next(case for _, case in CASES if case["flags"] & S.GRADE_PAGE)
    bg = case_units(page); bg[28] = S.OFFSET_MAP_BYTES + 1
    bad["invalid_bg_bytes"] = " ".join(signed_token(v) for v in bg) + "\n0\n"
    flags = list(vals); flags[2] = S.GRADE_PALETTE | S.PALETTE_UNDEFINED
    bad["contradictory_flags"] = \
        " ".join(signed_token(v) for v in flags) + "\n0\n"
    bad["trailing_tokens"] = encode_text(SMOKE_CASES) + "7\n"
    return bad


def parse_text(text):
    toks = text.split()
    cases = []
    p = 0
    terminated = False
    seen = set()
    while p < len(toks):
        try:
            op = int(toks[p], 10)
        except ValueError:
            raise ValueError("non-decimal corpus token at %d" % p)
        p += 1
        if op == 0:
            terminated = True
            if p != len(toks):
                raise ValueError("tokens after terminator")
            break
        if op != 1:
            raise ValueError("unknown opcode %d" % op)
        if len(toks) - p < 28:
            raise ValueError("truncated 29-unit sky record")
        vals = [op]
        for _ in range(28):
            try:
                v = int(toks[p], 10)
            except ValueError:
                raise ValueError("non-decimal corpus token at %d" % p)
            if v < -0x80000000 or v > 0x7FFFFFFF:
                raise ValueError("corpus token outside signed-u32 spelling at %d" % p)
            vals.append(v)
            p += 1
        # Signed decimal grammar denotes raw little-endian u32 units.
        raw = [S.u32(v) for v in vals]
        d = {}
        for k, v in zip(S.FIELD_NAMES, raw):
            d[k] = S.i32(v) if k in S.SIGNED_FIELDS else v
        d = S.normalize_case(d)
        if d["case_id"] in seen:
            raise ValueError("duplicate case_id %d" % d["case_id"])
        seen.add(d["case_id"])
        cases.append(d)
    if not terminated:
        raise ValueError("missing corpus terminator")
    return cases


def validate_canonical(named_cases=CASES):
    text = encode_text(named_cases)
    parsed = parse_text(text)
    expected = [S.normalize_case(c) for _, c in named_cases]
    if parsed != expected:
        raise ValueError("corpus round-trip drift")
    # Required exact repetition ignores only the stable case id.
    a, z = expected[0], expected[-1]
    if any(a[k] != z[k] for k in S.FIELD_NAMES if k != "case_id"):
        raise ValueError("final anchor row is not an exact repeat")
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--case", choices=[name for name, _ in CASES])
    ap.add_argument("--malformed", choices=sorted(malformed_matrix()))
    ap.add_argument("--output")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if sum(bool(x) for x in
           (args.smoke, args.synthetic, args.case, args.malformed)) > 1:
        ap.error("--smoke, --synthetic, --case, and --malformed are mutually exclusive")
    if args.malformed:
        if not args.output:
            ap.error("--malformed requires --output")
        text = malformed_matrix()[args.malformed]
        with open(args.output, "w", encoding="ascii", newline="\n") as fh:
            fh.write(text)
        print("wrote malformed %s: %s" %
              (args.malformed, os.path.abspath(args.output)))
        return
    selected = ([next(row for row in CASES if row[0] == args.case)]
                if args.case else SMOKE_CASES if args.smoke else
                SYNTHETIC_CASES if args.synthetic else CASES)
    text = validate_canonical(selected) if not (args.smoke or args.synthetic) else encode_text(selected)
    if parse_text(text) != [S.normalize_case(c) for _, c in selected]:
        raise SystemExit("round-trip failure")
    if args.output:
        with open(args.output, "w", encoding="ascii", newline="\n") as fh:
            fh.write(text)
        print("wrote %s: %d cases, 29 units each" %
              (os.path.abspath(args.output), len(selected)))
    else:
        print(text, end="")
    if args.check:
        print("schema PASS: %d cases, terminator exact" % len(selected))


if __name__ == "__main__":
    main()
