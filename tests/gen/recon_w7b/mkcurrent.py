r"""Build a ..\DATA\Current.BIN that parks the Stardrifter at a chosen
planet or an untargeted primary-star pose without interactive navigation.

The layout is not guessed.  NOCTIS-0.CPP:735-800 declares the continuity
block starting at `sync` with the byte offset of every field written in the
source as a trailing comment, and NOCTIS.CPP:452-466 (freeze) writes exactly
`old_currentbin_length` = 245 bytes from &sync followed by the GOES fields.
Offsets below are copied from those comments.

Why no navigation is needed
---------------------------
NOCTIS.CPP:3271-3316: every frame, if ip_targetted != -1 and pwr > 15000 and
ip_reached and sync, the ship is dragged onto a fixed offset from the target
planet:

    hold_z = 1.8 + 0.1 * ray          (sync == 3, synchronous orbit)
    dxx += hold_z*ray*sin(ang) ...    then dzat -= dxx*0.05  (or dxx if slow)

so the ship converges to ~2 planet radii regardless of where it starts.
NOCTIS-0.CPP:5339-5345 then sets surfacemap = 1 because d3 < 25*ray, and
NOCTIS-0.CPP:5376-5418 calls surface() for the two "resident" bodies.
Untargeted `--target -1` poses instead preserve the explicitly supplied local
star vector.
"""

from pathlib import Path
import struct
import sys

# --- the continuity block, offsets straight from NOCTIS-0.CPP -------------
OFF = {
    "sync": 0, "anti_rad": 1, "pl_search": 2, "field_amplificator": 3,
    "ilight": 4, "ilightv": 5, "charge": 6, "revcontrols": 7,
    "ap_targetting": 8, "ap_targetted": 9, "ip_targetting": 10,
    "ip_targetted": 11, "ip_reaching": 12, "ip_reached": 13,
    "ap_target_spin": 14, "ap_target_r": 15, "ap_target_g": 16,
    "ap_target_b": 17, "nearstar_spin": 18, "nearstar_r": 19,
    "nearstar_g": 20, "nearstar_b": 21, "gburst": 22, "menusalwayson": 23,
    "depolarize": 24, "sys": 25, "pwr": 27, "dev_page": 29,
    "ap_target_class": 31, "f_ray_elapsed": 33, "nearstar_class": 35,
    "nearstar_nop": 37, "pos_x": 39, "pos_y": 43, "pos_z": 47,
    "user_alfa": 51, "user_beta": 55, "navigation_beta": 59,
    "ap_target_ray": 63, "nearstar_ray": 67,
    "dzat_x": 71, "dzat_y": 79, "dzat_z": 87,
    "ap_target_x": 95, "ap_target_y": 103, "ap_target_z": 111,
    "nearstar_x": 119, "nearstar_y": 127, "nearstar_z": 135,
    "helptime": 143, "ip_target_initial_d": 151,
    "requested_approach_coefficient": 159,
    "current_approach_coefficient": 167, "reaction_time": 175,
    "fcs_status": 183, "fcs_status_delay": 194, "psys": 196,
    "ap_target_initial_d": 198, "requested_vimana_coefficient": 206,
    "current_vimana_coefficient": 214, "vimana_reaction_time": 222,
    "lithium_collector": 230, "autoscreenoff": 231, "ap_reached": 232,
    "lifter": 233, "secs": 235, "data": 243, "surlight": 244,
}
BLOCK = 245

CLASS_RGB = [
    (63, 58, 40), (30, 50, 63), (63, 63, 63), (63, 30, 20),
    (63, 55, 32), (32, 16, 10), (32, 28, 24), (10, 20, 63),
    (63, 32, 16), (48, 32, 63), (40, 10, 10), (0, 63, 63),
]
CLASS_RAY = [5000, 15000, 300, 20000, 15000, 1000, 3000,
             2000, 4000, 1500, 30000, 250]
CLASS_RAYVAR = [2000, 10000, 200, 15000, 5000, 1000, 3000,
                500, 5000, 10000, 1000, 10]

ROOT = Path(__file__).resolve().parents[3]
HARNESS = ROOT / "noctis-harness"
if str(HARNESS) not in sys.path:
    sys.path.insert(0, str(HARNESS))


def star_infos(x, y, z):
    """extract_ap_target_infos + prepare_nearstar via the tracked model."""
    import ns_spec
    system = ns_spec.System(x, y, z)
    r, gg, b = CLASS_RGB[system.cls]
    return dict(
        cls=system.cls, ray=system.ray, spin=system.ap_spin,
        r=r, g=gg, b=b, nop=system.nop, nob=system.nob,
        owner=system.p_owner, ptype=system.p_type,
    )


def build(x, y, z, target, sync=3, secs=1344094201.0, dist=6.0,
          charge=3, power=20000, lens_mode=0, draw_hud=1,
          pos=(0.0, 0.0, -500.0), angles=(0.0, 0.0, 0.0), local=None):
    st = star_infos(x, y, z)
    b = bytearray(BLOCK)

    def i8(k, v):
        b[OFF[k]] = v & 0xFF

    def i16(k, v):
        struct.pack_into("<h", b, OFF[k], v)

    def f32(k, v):
        struct.pack_into("<f", b, OFF[k], v)

    def f64(k, v):
        struct.pack_into("<d", b, OFF[k], v)

    i8("sync", sync)
    i8("anti_rad", 1)
    i8("pl_search", 0)
    i8("field_amplificator", 0)
    i8("ilight", 63)
    i8("ilightv", 1)
    i8("charge", charge)
    i8("revcontrols", 0)
    i8("ap_targetting", 0)
    i8("ap_targetted", 1)
    i8("ip_targetting", 0)
    i8("ip_targetted", target)
    i8("ip_reaching", 0)
    i8("ip_reached", int(target >= 0))
    i8("ap_target_spin", st["spin"])
    i8("ap_target_r", st["r"])
    i8("ap_target_g", st["g"])
    i8("ap_target_b", st["b"])
    i8("nearstar_spin", st["spin"])
    i8("nearstar_r", st["r"])
    i8("nearstar_g", st["g"])
    i8("nearstar_b", st["b"])
    i8("gburst", 0)
    i8("menusalwayson", 0)
    i8("depolarize", 0)
    i16("sys", 4)
    i16("pwr", power)
    i16("dev_page", 0)
    i16("ap_target_class", st["cls"])
    i16("f_ray_elapsed", 0)
    i16("nearstar_class", st["cls"])
    i16("nearstar_nop", st["nop"])
    f32("pos_x", pos[0])
    f32("pos_y", pos[1])
    f32("pos_z", pos[2])
    f32("user_alfa", angles[0])
    f32("user_beta", angles[1])
    f32("navigation_beta", angles[2])
    f32("ap_target_ray", st["ray"])
    f32("nearstar_ray", st["ray"])
    if local is None:
        local = (dist, 0.0, dist)
    f64("dzat_x", x + local[0])
    f64("dzat_y", y + local[1])
    f64("dzat_z", z + local[2])
    f64("ap_target_x", float(x))
    f64("ap_target_y", float(y))
    f64("ap_target_z", float(z))
    f64("nearstar_x", float(x))
    f64("nearstar_y", float(y))
    f64("nearstar_z", float(z))
    f64("helptime", 0.0)
    f64("ip_target_initial_d", 1e8)
    f64("requested_approach_coefficient", 1.0)
    f64("current_approach_coefficient", 1.0)
    f64("reaction_time", 0.01)
    b[OFF["fcs_status"]:OFF["fcs_status"] + 11] = b"STANDBY\0\0\0\0"
    i16("fcs_status_delay", 0)
    i16("psys", 4)
    f64("ap_target_initial_d", 1e8)
    f64("requested_vimana_coefficient", 1.0)
    f64("current_vimana_coefficient", 1.0)
    f64("vimana_reaction_time", 0.01)
    i8("lithium_collector", 0)
    i8("autoscreenoff", 0)
    i8("ap_reached", 1)
    i16("lifter", 0)
    f64("secs", secs)
    i8("data", 0)
    i8("surlight", 16)

    tail = bytearray()
    tail += b"\x01"                      # gnc_pos
    tail += struct.pack("<l", 0)         # goesfile_pos
    tail += b"_" + b"\0" * 119           # goesnet_command
    tail += struct.pack("<l", -1)        # lastSnapshot
    tail += b"\x00"                      # option_mouseLook
    tail += struct.pack("<h", 0)         # roofspeed
    tail += struct.pack("<h", 0)         # hud_closed
    tail += struct.pack("<h", draw_hud)  # draw_hud
    tail += struct.pack("<h", lens_mode) # lens_flare_mode
    tail += struct.pack("<h", 0)         # seamless_border
    return bytes(b) + bytes(tail), st


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--x", type=float, required=True)
    ap.add_argument("--y", type=float, required=True)
    ap.add_argument("--z", type=float, required=True)
    ap.add_argument(
        "--target", type=int, required=True,
        help="zero-based body index, or -1 for an untargeted primary-star pose",
    )
    ap.add_argument("--sync", type=int, default=3)
    ap.add_argument("--charge", type=int, default=3,
                    help="Li+ cells; high values keep long headless captures "
                         "from dropping their restored target")
    ap.add_argument("--power", type=int, default=20000,
                    help="restored system power; use 30000 for landed captures")
    ap.add_argument("--lens-mode", type=int, choices=(-1, 0, 1), default=0)
    ap.add_argument("--draw-hud", type=int, choices=(0, 1), default=1,
                    help="restored draw_hud continuity flag")
    ap.add_argument("--secs", type=float, default=1344094201.0,
                    help="restored NIV+ seconds-since-1984 value")
    ap.add_argument("--pos-x", type=float, default=0.0)
    ap.add_argument("--pos-y", type=float, default=0.0)
    ap.add_argument("--pos-z", type=float, default=-500.0)
    ap.add_argument("--pitch", type=float, default=0.0)
    ap.add_argument("--view-angle", type=float, default=0.0)
    ap.add_argument("--navigation-angle", type=float, default=0.0)
    ap.add_argument("--local-x", type=float)
    ap.add_argument("--local-y", type=float)
    ap.add_argument("--local-z", type=float)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.target < -1:
        ap.error("--target must be -1 or a zero-based body index")
    local_values = (a.local_x, a.local_y, a.local_z)
    if any(value is not None for value in local_values):
        if any(value is None for value in local_values):
            ap.error("--local-x, --local-y and --local-z must be supplied together")
        local = local_values
    else:
        local = None
    data, st = build(
        a.x, a.y, a.z, a.target, sync=a.sync, secs=a.secs,
        charge=a.charge, power=a.power, lens_mode=a.lens_mode,
        draw_hud=a.draw_hud,
        pos=(a.pos_x, a.pos_y, a.pos_z),
        angles=(a.pitch, a.view_angle, a.navigation_angle), local=local)
    if a.target >= st["nob"]:
        ap.error("--target is outside the generated planetary system")
    open(a.out, "wb").write(data)
    print("star class=%d ray=%.6f nop=%d nob=%d" %
          (st["cls"], st["ray"], st["nop"], st["nob"]))
    if a.target >= 0:
        print("target body %d  owner=%d  type=%d" %
              (a.target, st["owner"][a.target], st["ptype"][a.target]))
    else:
        print("untargeted primary-star pose")
    print("wrote %s, %d bytes" % (a.out, len(data)))
