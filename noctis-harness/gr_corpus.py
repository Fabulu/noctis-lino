r"""gr_corpus.py - the fixture for Wave 7b build_surface + SURFACE.BIN.

Three kinds of case, each graded differently:

  SBBIN  - SURFACE.BIN pack/unpack round-trip cases.  Eleven field values
           packed into 40 bytes, byte-exact three-way (spec == cref == lino).
           No DOS capture exists; these are structural correctness checks.

  SEED   - global_surface_seed chop cases.  Given (ray, orb_ray, orb_orient),
           compute (long)((sum) * 4112) via the x87 chop.  Exact three-way.

  BUILD  - build_surface prologue + rockyground + smoothterrain + noise-add
           cases.  Given (gseed, ip_type, sctype, albedo, latitude) and
           painter parameters, produce p_surfacemap (40000 B) + objectschart
           (40000 B).  Byte-exact three-way on the integer-driven paths.

The file emitted here is read by gr_ref.exe (the C reference) and is the
same file for all three sides, so a case cannot exist on one side and not
the other.
"""

import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)


# ---------------------------------------------------------------------------
# SURFACE.BIN pack/unpack cases
# ---------------------------------------------------------------------------

SBBIN_CASES = [
    # (tag, lon, lat, atl_x, atl_z, atl_x2, atl_z2,
    #  pos_x, pos_y, pos_z, user_alfa, user_beta)
    ("sbb_fresh",      100,  60,   100,   100,  8192,  8192,
                       100.0*16384+8192,  -260000.0,  100.0*16384+8192,  0.0, 0.0),
    ("sbb_midwalk",     42,  37,    42,    37,  5000, 12345,
                       42.0*16384+5000,  -150000.5, 37.0*16384+12345, 1.5, -0.75),
    ("sbb_negcoord",  -100, -60,  -100,  -100,  8192,  8192,
                       -100.0*16384+8192, -260000.0, -100.0*16384+8192, 3.14159, -1.5708),
    ("sbb_zero",         0,   0,     0,     0,  8192,  8192,
                       8192.0, -0.001, 8192.0, 0.0, 0.0),
    ("sbb_large",     32000, 32000, 32000, 32000, 16383, 16383,
                       32000.0*16384+16383, -260000.0, 32000.0*16384+16383,
                       6.28318, 1.5708),
    ("sbb_edge8192",   255, 128,   255,   128,  8192,  8192,
                       255.0*16384+8192, -1.0, 128.0*16384+8192, 2.0, -2.0),
    ("sbb_tinyfloat",   1,  1,     1,     1,     1,    1,
                       16385.0, -0.0001, 16385.0, 0.001, -0.001),
    ("sbb_round",      180,  90,   180,    90, 10000, 10000,
                       180.0*16384+10000, -123456.789, 90.0*16384+10000,
                       0.123456, -0.987654),
]


# ---------------------------------------------------------------------------
# global_surface_seed chop cases
# ---------------------------------------------------------------------------

SEED_CASES = [
    # (tag, ray, orb_ray, orb_orient)
    # The chop: (long)((ray + orb_ray + orb_orient) * 4112)
    ("seed_typical",   1000.0,  500.0,   90.0),
    ("seed_small",        1.5,    0.5,    0.25),
    ("seed_large",   500000.0, 100000.0, 360.0),
    ("seed_frac",       10.1,    5.2,     3.3),
    ("seed_neg",      -100.0,  -50.0,   -25.0),
    ("seed_zero",        0.0,    0.0,    0.0),
    ("seed_near_boundar", 100.0001, 50.0001, 25.0001),
    ("seed_balastr",  7812.5,  3906.25, 2812.125),
]


# ---------------------------------------------------------------------------
# build_surface prologue + painter cases
# ---------------------------------------------------------------------------

BUILD_CASES = [
    # (tag, gseed, ip_type, sctype, albedo, latitude,
    #  roughness, rounding, level, do_plains_noise)
    #
    # gseed is the already-chopped global_surface_seed value.
    # sctype: 0=none, 1=OCEAN, 2=PLAINS, 3=DESERT, 4=ICY
    ("build_t1_moon",   123456, 1, 0,  20,  30,  25, 4,  0, 0),
    ("build_t1_rocky",  999999, 1, 0,  10,  45,  10, 1,  1, 0),
    ("build_t1_smooth",     42, 1, 0,   5,  10,   5, 2, -3, 0),
    ("build_t2_venus",   555555, 2, 0,  80,   0,  10, 1,  0, 0),
    ("build_t3_plains",  777777, 3, 2,  30,  20,  50, 0,  0, 1),
    ("build_t3_ocean",   333333, 3, 1,  15,  10,  10, 2, -5, 0),
    ("build_t4_boulder",  11111, 4, 0,  40,  60,  15, 3, -2, 0),
    ("build_t5_mars",    888888, 5, 0,  45,  35,  10, 1, -10, 0),
    ("build_t7_frozen",  444444, 7, 0,  60,  80,  10, 0, 20, 0),
    ("build_t8_quartz",   66666, 8, 0,  15,  50,  10, 1,  0, 0),
    ("build_plains_noise", 314159, 3, 2, 25, 15, 0, 0, 0, 1),
    ("build_zero_gseed",      0, 1, 0,   0,   0,   3, 1,  0, 0),
]


def all_cases():
    """Return a list of all cases as dicts."""
    rows = []
    for tag, lon, lat, ax, az, ax2, az2, px, py, pz, ua, ub in SBBIN_CASES:
        rows.append(dict(kind="sbbin", tag=tag,
                         landing_pt_lon=lon, landing_pt_lat=lat,
                         atl_x=ax, atl_z=az, atl_x2=ax2, atl_z2=az2,
                         pos_x=px, pos_y=py, pos_z=pz,
                         user_alfa=ua, user_beta=ub))
    for tag, ray, orbray, orb in SEED_CASES:
        rows.append(dict(kind="seed", tag=tag,
                         ray=ray, orb_ray=orbray, orb_orient=orb))
    for tag, gs, ity, sc, alb, lat, rough, rnd, lvl, pn in BUILD_CASES:
        rows.append(dict(kind="build", tag=tag,
                         gseed=gs, ip_type=ity, sctype=sc, albedo=alb,
                         latitude=lat, roughness=rough, rounding=rnd,
                         level=lvl, plains_noise=pn))
    return rows


def write_spc(path, rows):
    """Write the corpus for gr_ref.exe (the C reference).

    Line format depends on kind:
      sbbin:  1 lon lat atl_x atl_z atl_x2 atl_z2 pos_x pos_y pos_z user_alfa user_beta
      seed:   2 ray orb_ray orb_orient
      build:  3 gseed ip_type sctype albedo latitude roughness rounding level plains_noise
    """
    with open(path, "w") as fh:
        for r in rows:
            if r["kind"] == "sbbin":
                fh.write("1 %d %d %d %d %d %d %.17g %.17g %.17g %.17g %.17g   # %s\n" % (
                    i16(r["landing_pt_lon"]), i16(r["landing_pt_lat"]),
                    r["atl_x"], r["atl_z"], r["atl_x2"], r["atl_z2"],
                    r["pos_x"], r["pos_y"], r["pos_z"],
                    r["user_alfa"], r["user_beta"], r["tag"]))
            elif r["kind"] == "seed":
                fh.write("2 %.17g %.17g %.17g   # %s\n" % (
                    r["ray"], r["orb_ray"], r["orb_orient"], r["tag"]))
            elif r["kind"] == "build":
                fh.write("3 %d %d %d %d %d %d %d %d %d   # %s\n" % (
                    r["gseed"], r["ip_type"], r["sctype"], r["albedo"],
                    r["latitude"], r["roughness"], r["rounding"],
                    r["level"], r["plains_noise"], r["tag"]))
    return path


def i16(v):
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


if __name__ == "__main__":
    rows = all_cases()
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "gr_corpus.spc")
    write_spc(out, rows)
    for r in rows:
        print("%-20s %-6s tag=%s" % (r["tag"], r["kind"], r["tag"]))
    print("wrote", out, len(rows), "cases")
