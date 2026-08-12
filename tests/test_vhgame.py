"""Lean integration checks for the live Stardrifter game.

This deliberately stays small: it pins the interactive regressions found
during playtesting (roof-lift timing, the landed-coordinate escape, and GUI
repaint behavior) plus the original 18.2 Hz synchronizer.  It does not rebuild
historical wave oracles or run a mutation matrix.
"""

from __future__ import annotations

import math
import os
import re
import struct
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / "work" / "vhgame.txt"
GROUND = ROOT / "work" / "vhground.txt"
GRND = ROOT / "work" / "grnd.txt"
CUPOLA = ROOT / "work" / "vhcupola.txt"
CAPSULE = ROOT / "work" / "vhcapsule.txt"
GUI = ROOT / "work" / "vhgui.txt"
VIEW = ROOT / "work" / "vhview.txt"
PANELS = ROOT / "work" / "vhpanels.txt"
CATALOG = ROOT / "work" / "vhcatalog.txt"
GUIDE_SOURCE = ROOT / "work" / "vhguide.txt"
GUIDE_DATA = ROOT / "work" / "GUIDE.BIN"
PACKAGE_SCRIPT = ROOT / "package_noctis.ps1"
IGUI = ROOT / "work" / "igui.txt"
STICK = ROOT / "work" / "vhstick.txt"
SAVE = ROOT / "work" / "vhsave.txt"
AUDIO = ROOT / "work" / "vhaudio.txt"
FLARE = ROOT / "work" / "vhflare.txt"
STAR = ROOT / "work" / "vhstar.txt"
SPACE = ROOT / "work" / "vhspace.txt"
REFERENCE_ROOT = Path(os.environ.get(
    "NOCTIS_REFERENCE_ROOT",
    r"C:\programmieren\noctis\niv-plus\source",
))
ORIGINAL = REFERENCE_ROOT / "NOCTIS.CPP"
ORIGINAL0 = REFERENCE_ROOT / "NOCTIS-0.CPP"
ORIGINAL1 = REFERENCE_ROOT / "NOCTIS-1.CPP"
ORIGINAL_WHERE = REFERENCE_ROOT / "WHERE.CPP"
ORIGINAL_SL = REFERENCE_ROOT / "SL.CPP"
ORIGINAL_DL = REFERENCE_ROOT / "DL.CPP"
ORIGINAL_PAR = REFERENCE_ROOT / "PAR.CPP"
ORIGINAL_ST = REFERENCE_ROOT / "ST.CPP"
ORIGINAL_CAT = REFERENCE_ROOT / "CAT.CPP"
ORIGINAL_PRI = REFERENCE_ROOT / "PRI.CPP"
ORIGINAL_CAST = REFERENCE_ROOT / "CAST.CPP"
ORIGINAL_REP = REFERENCE_ROOT / "REP.CPP"
ORIGINAL_DELE = REFERENCE_ROOT / "DELE.CPP"
ORIGINAL_CLEAN = REFERENCE_ROOT / "CLEAN.CPP"
ORIGINAL_OUTBOX = REFERENCE_ROOT / "OUTBOX.CPP"
ORIGINAL_INBOX = REFERENCE_ROOT / "INBOX.CPP"
ORIGINAL_HELP = REFERENCE_ROOT.parent / "modules" / "N_Help_3.asm"
ORIGINAL_REPAIR = REFERENCE_ROOT.parent / "modules" / "REPAIR.EXE"


def section(text: str, start: str, end: str) -> str:
    try:
        return text.split(start, 1)[1].split(end, 1)[0]
    except IndexError as exc:
        raise AssertionError(f"missing section boundary: {start!r} / {end!r}") from exc


def check(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"  PASS {label}")


def aspect_fit(width: int, height: int) -> tuple[int, int, int, int]:
    draw_width = width
    draw_height = draw_width * 5 // 8
    if draw_height > height:
        draw_height = height
        draw_width = draw_height * 8 // 5
    return draw_width, draw_height, (width - draw_width) // 2, (height - draw_height) // 2


def signed_lerp(old: int, new: int, phase: int, denominator: int = 60000) -> int:
    product = (new - old) * phase
    delta = abs(product) // denominator
    return old - delta if product < 0 else old + delta


def signed32(value: int) -> int:
    value &= 0xFFFFFFFF
    return value if value < 0x80000000 else value - 0x100000000


def par_foldmul(left: int, right: int) -> int:
    product = signed32(left) * signed32(right)
    return signed32(signed32(product) + signed32(product >> 32))


def par_candidate(sector_x: int, sector_y: int, sector_z: int) -> tuple[int, int, int]:
    """Independent form of PAR.CPP's procedural sector hash."""
    sum_xz = signed32(sector_x + sector_z)
    x = signed32((sum_xz & 0x1FFFF) + sector_x - 50000)
    accumulator = par_foldmul(x, sum_xz)
    identity_key = signed32(sum_xz + accumulator)
    y = signed32((accumulator & 0x1FFFF) + sector_y - 50000)
    accumulator = par_foldmul(y, identity_key)
    z = signed32((accumulator & 0x1FFFF) + sector_z - 50000)
    return x, y, z


def guide_wrap(message: str, width: int = 21) -> list[str]:
    lines: list[str] = []
    line = ""
    for word in message.split(" "):
        candidate = word if not line else f"{line} {word}"
        if line and len(candidate) > width:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines


def repair_duplicates(
    records: list[tuple[float, bytes]], require_payload: bool
) -> list[int]:
    """Independent model of the shipped REPAIR utility's first-record rule."""
    removed: set[int] = set()
    for outer, (subject, payload) in enumerate(records):
        if outer in removed or not math.isfinite(subject):
            continue
        for inner in range(outer + 1, len(records)):
            candidate, candidate_payload = records[inner]
            if inner in removed or not math.isfinite(candidate):
                continue
            if abs(candidate - subject) < 0.00001 and (
                not require_payload or candidate_payload == payload
            ):
                removed.add(inner)
    return sorted(removed)


def pod_hint(dx: int, dz: int, beta: int) -> str:
    """Independent model of the HUD's integer eight-sector return bearing."""
    ax, az = abs(dx), abs(dz)
    if ax * 2 < az:
        bearing = 0 if dz >= 0 else 180
    elif az * 2 < ax:
        bearing = 90 if dx < 0 else 270
    elif dx < 0:
        bearing = 45 if dz >= 0 else 135
    else:
        bearing = 315 if dz >= 0 else 225
    delta = (bearing - beta) % 360
    if delta <= 45 or delta >= 315:
        return "F"
    if delta < 135:
        return "L"
    if delta < 225:
        return "B"
    return "R"


def compass_window(beta: int) -> tuple[int, str]:
    """Original surrounding() compass window and sub-character x offset."""
    heading = (360 - beta) % 360
    position = heading // 9
    x = 200 - ((heading * 4 // 9) % 4)
    cardinal = "NESW"
    chars = []
    for index in range(position, position + 28):
        chars.append(cardinal[(index // 10) % 4] if index % 10 == 0 else ".")
    return x, "".join(chars)


def sqc_text(longitude: int, latitude: int, x: int, z: int) -> str:
    """Surface-coordinate suffix emitted by surrounding(1)."""
    return f"SQC {longitude}.{latitude}:{x // 16384 - 100}.{z // 16384 - 100}"


def epoc_text(seconds: int) -> str:
    """Noctis EPOC plus its three sub-billion zero-padded triads."""
    epoc = 6011 + seconds // 1_000_000_000
    return f"EPOC {epoc} & {seconds // 1_000_000 % 1000:03}.{seconds // 1000 % 1000:03}.{seconds % 1000:03}"


def surface_arc(gravity_mfg: int, thrust_ticks: int = 0) -> tuple[int, int, int]:
    """Independent integer model of the port's source-shaped surface arc."""
    ground = 0
    y = ground
    velocity = -500
    acceleration = max(1, gravity_mfg * 2000 // 38260)
    lowest = y
    for tick in range(2000):
        if tick < thrust_ticks:
            velocity = max(-1200, velocity - 50)
        y += velocity
        velocity += acceleration
        lowest = min(lowest, y)
        if y >= ground:
            return tick + 1, lowest, ground
    raise AssertionError("surface arc did not return to terrain")


def surface_cruise(current: int, digit: int) -> int:
    selected = digit * 80
    return 0 if current == selected else selected


def capsule_recovery_trigger(samples: list[tuple[int, int, int]]) -> int | None:
    """Independent model of the original walk-away/re-enter recovery gate."""
    armed = False
    for index, (dx, dy, dz) in enumerate(samples):
        if dx * dx + dy * dy + dz * dz < 1600 * 1600:
            if armed:
                return index
        else:
            armed = True
    return None


def surface_forward_trace(input_step: int, ticks: int) -> tuple[list[int], int]:
    """Port-scaled model of source input accumulation and 1/1.25 friction."""
    velocity = 0
    displacements = []
    for _ in range(ticks):
        velocity += input_step
        displacements.append(velocity)
        velocity = int(velocity * 4 / 5)
        if abs(velocity) < 4:
            velocity = 0
    return displacements, velocity


def surface_level_trace(alpha: int, port_step: int, ticks: int) -> list[int]:
    """Quantized port model of NIV+'s walking pitch-to-level recurrence."""
    error = 0
    speed = abs(port_step)
    denominator = 125000 + speed
    result: list[int] = []
    for _ in range(ticks):
        if alpha and speed:
            error += abs(alpha) * speed
            drop, error = divmod(error, denominator)
            if alpha > 0:
                alpha = max(0, alpha - drop)
            else:
                alpha = min(0, alpha + drop)
        result.append(alpha)
    return result


def cupola_panel_drop(horizontal_distance: int) -> int:
    """Independent model of NOCTIS-0.CPP's roof-panel displacement."""
    return min(600, max(0, 1000 - horizontal_distance))


def lift_vertical_trace(start_y: int, lifter: int) -> list[tuple[int, int, bool]]:
    """Independent model of the original lift's vertical state transitions."""
    trace: list[tuple[int, int, bool]] = []
    while lifter:
        start_y += lifter
        lifter += -1 if lifter > 0 else 1
        if start_y > 0:
            start_y, lifter = 0, 0
        if start_y < -750:
            start_y, lifter = -750, 0
        trace.append((start_y, lifter, start_y < -500))
    return trace


def lift_ascent_route(
    start_z_from_center: int, forward_sign: int, impulse: int = 100
) -> list[tuple[int, int, int, int]]:
    """Source-order ascent along beta=0, including momentum and restraint."""
    y, lifter, step = 0, -impulse, 0
    trace: list[tuple[int, int, int, int]] = []
    while lifter:
        y += lifter
        lifter += 1
        if -715 < y < -325:
            step = -y
        if y < -750:
            y, lifter = -750, 0
        start_z_from_center += forward_sign * step
        step = step * 4 // 5
        if lifter:
            start_z_from_center = int(start_z_from_center * 3 / 4)
        trace.append((y, lifter, start_z_from_center, step))
    return trace


def main() -> int:
    game = GAME.read_text(encoding="utf-8")
    ground = GROUND.read_text(encoding="utf-8")
    grnd = GRND.read_text(encoding="utf-8")
    cupola = CUPOLA.read_text(encoding="utf-8")
    capsule_physics = CAPSULE.read_text(encoding="utf-8")
    gui = GUI.read_text(encoding="utf-8")
    view = VIEW.read_text(encoding="utf-8")
    panels = PANELS.read_text(encoding="utf-8")
    catalog = CATALOG.read_text(encoding="utf-8")
    guide_source = GUIDE_SOURCE.read_text(encoding="utf-8")
    package_script = PACKAGE_SCRIPT.read_text(encoding="utf-8")
    igui = IGUI.read_text(encoding="utf-8")
    stick = STICK.read_text(encoding="utf-8")
    save = SAVE.read_text(encoding="utf-8")
    audio = AUDIO.read_text(encoding="utf-8")
    flare = FLARE.read_text(encoding="utf-8")
    star = STAR.read_text(encoding="utf-8")
    space = SPACE.read_text(encoding="utf-8")
    original = ORIGINAL.read_text(encoding="latin-1")
    original0 = ORIGINAL0.read_text(encoding="latin-1")
    original1 = ORIGINAL1.read_text(encoding="latin-1")
    original_where = ORIGINAL_WHERE.read_text(encoding="latin-1")
    original_sl = ORIGINAL_SL.read_text(encoding="latin-1")
    original_dl = ORIGINAL_DL.read_text(encoding="latin-1")
    original_par = ORIGINAL_PAR.read_text(encoding="latin-1")
    original_st = ORIGINAL_ST.read_text(encoding="latin-1")
    original_cat = ORIGINAL_CAT.read_text(encoding="latin-1")
    original_pri = ORIGINAL_PRI.read_text(encoding="latin-1")
    original_cast = ORIGINAL_CAST.read_text(encoding="latin-1")
    original_rep = ORIGINAL_REP.read_text(encoding="latin-1")
    original_dele = ORIGINAL_DELE.read_text(encoding="latin-1")
    original_clean = ORIGINAL_CLEAN.read_text(encoding="latin-1")
    original_outbox = ORIGINAL_OUTBOX.read_text(encoding="latin-1")
    original_inbox = ORIGINAL_INBOX.read_text(encoding="latin-1")
    original_help = ORIGINAL_HELP.read_text(encoding="latin-1")
    original_repair = ORIGINAL_REPAIR.read_bytes()

    original_lift = section(original, "pos_y += lifter;", "//\n\t\t// Risposta al reset")
    check(
        all(token in original_lift for token in (
            "if (pos_y < -500)", "if (pos_y < -750)",
            "if (pos_y < -325 && pos_y > -715)", "lifter = + 75",
            "step = - pos_y", "step = 0.5 * lifter",
            "DfCoS + step < 1100",
        )),
        "original lift motion, thresholds, and automatic return remain pinned",
    )

    ascent = lift_vertical_trace(0, -100)
    descent = lift_vertical_trace(-750, 75)
    check(
        [state[0] for state in ascent] == [-100, -199, -297, -394, -490, -585, -679, -750]
        and ascent[-1] == (-750, 0, True)
        and descent[-1] == (0, 0, False),
        "independent lift model reaches both exact endpoints and flips roof state below -500",
    )
    ascent_route = lift_ascent_route(0, -1)
    check(
        ascent_route[-1] == (-750, 0, -1711, 434)
        and ascent_route[-2] == (-679, -93, -1168, 543)
        and abs(ascent_route[-1][2]) > 1100,
        "source-order ascent momentum carries a centered rider clear of automatic return",
    )
    calibrated_route = lift_ascent_route(0, -1, 70)
    check(
        len(calibrated_route) == 12
        and calibrated_route[-1] == (-750, 0, -1827, 335)
        and abs(calibrated_route[-1][2]) < abs(lift_ascent_route(0, -1, 75)[-1][2]),
        "calibrated ascent slows the opening without adding the nearby impulse's roof overshoot",
    )

    lift = section(game, '"VHG lift tick"', '"VHG lift move"')
    check(
        all(token in lift for token in (
            "? A > 0 -> VHG lift descending;",
            "? A <= 0FFFFFEBBh -> VHG lift rise middle;",
            "? A <= 0FFFFFD35h -> VHG lift hold centre;",
            "? A >= 0FFFFFEBBh -> VHG lift hold centre;",
            "? A <= 0 -> VHG lift upper ok;",
            "? A >= 0FFFFFD12h -> VHG lift roof flag;",
            "? A >= 0FFFFFE0Ch -> VHG lift done;",
            "A = [VHGalpha]; A - 40; A * 12; A / 100;",
        )) and all(token not in lift for token in (
            "? A '>", "? A '<", " A '*", " A '/",
        )),
        "live lift uses signed original camera and roof boundaries",
    )
    check(
        lift.count("=> VHG lift move;") == 1
        and "0FFFFFD35h" in lift
        and "A = [VHGlifter]; A / 2; [VHGliftstep] = A;" in lift
        and "A = [VHGliftstep]; A * 4; A / 5;" in lift
        and lift.index("[VHGonroof] = 1;") < lift.index("=> VHG lift move;")
        and "A = [VHGdist]; A + [VHGliftstep]; ? A >= 1100" in lift
        and "[VHGlifter] = 75;" in lift
        and "=> VHG lift distance;" in lift
        and '"VHG lift postrender"' in game
        and "=> VHG fpu clean; => VHG lift postrender; => VHG input;" in game
        and "A = [VHGdosim]; ? A = 0 -> VHG lift postrender done;" in game
        and "=> VHG lift tick;\n\t( p_Forward(step) is clamped" in game
        and "=> VHG clamp position;\n    \"VHG skip ship ticks\"" in game
        and "A = [VHGx]; A * 3; A / 4; [VHGx] = A;" in game
        and "A = [VHGz]; A + 3100; A / 4;" in game,
        "lift preserves source trigger, movement, clamp, render, and restraint ordering",
    )
    platform = section(game, '"VHG platform"', '"VHG lift tick"')
    ship_input = section(game, '"VHG normal input"', '"VHG surface input"')
    check(
        "E = KEY A; E + 4; A = [E];" in ship_input
        and "A = [KEY UP]" in ship_input
        and "A = [VHGalpha]; A - 2;" in ship_input
        and "[VHGupheld]" in ship_input
        and "[VHGuprequest] = 1;" in ship_input
        and "[VHGuprequest]" in platform
        and "A - 70; [VHGlifter] = A;" in platform
        and "1210000" not in platform
        and "[VHGlifter] = 75;" not in platform
        and "[VHGnoticeptr] = VHGliftdecktext;" in lift
        and "[VHGnoticeptr] = VHGliftrooftext;" in lift
        and "[VHGuprequest] = 0;" in platform,
        "E maps the original direct ascent event, Up looks up, and roof return is not a second key state machine",
    )
    walk_input = section(game, '"VHG look input"', '"VHG landing selector input"')
    check(
        "[VHGlifter]; ? A != 0 -> VHG input done;" not in walk_input
        and "The source continues sampling player movement during a lift" in walk_input,
        "ship movement remains controllable during the source-shaped lift restraint",
    )

    lift_move = section(game, '"VHG lift move"', '"VHG land"')
    check(
        "[VHValpha] = [VHGalpha]; [VHVbeta] = [VHGbeta]; => VH set view;" in lift_move
        and "A - 180" not in lift_move
        and "beta = user_beta;" in original0
        and "p_Forward (step);" in original,
        "lift camera and source forward push share one player heading",
    )
    mouse_look = section(game, '"VHG mouse look"', '"VHG return key"')
    menu_mouse = section(game, '"VHG menu mouse"', '"VHG systems reset action"')
    check(
        "=> VHG mouse look;" in game
        and all(token in mouse_look for token in (
            "[Client Owns Mouse Pointer]", "PD RIGHT BUTTON DOWN",
            "[VHGconsole]", "[VHGhelpshow]", "[VHGlifter]",
            "[VHGUIleft]", "[VHGUItop]", "[VHGUIdw]", "[VHGUIdh]",
            "A = [VHGmousedx]; A * 320; A / [VHGUIdw]; A / 3;",
            "A = [VHGmousedy]; A * 200; A / [VHGUIdh]; A / 4;",
            "[VHGmouseheld] = 0;",
        ))
        and "A '* 320" not in mouse_look
        and "A '* 200" not in mouse_look,
        "right-drag mouselook respects iGUI ownership and uses signed resize-stable deltas",
    )
    check(
        "=> VHG menu mouse;" in game
        and all(token in menu_mouse for token in (
            "[Client Owns Mouse Pointer]", "PD LEFT BUTTON DOWN",
            "[VHGUIleft]", "[VHGUItop]", "[VHGUIdw]", "[VHGUIdh]",
            "A - [VHGUIleft]; A '* 320; A '/ [VHGUIdw];",
            "A - [VHGUItop]; A '* 200; A '/ [VHGUIdh];",
            "A = [VHGdev]; ? A != 6 -> VHG menu mouse regular rows;",
            "[VHGascii] = A;", "[VHGmenuheld] = 1;",
            "A = [VHGdevaccess]; ? A = 0 -> VHG menu mouse release;",
        ))
        and "[Ink] = FFFFFFh;" in section(
            game, '"VHG info draw line"', '"VHG graphics overlay"'
        ),
        "onboard and FCS pages expose resize-stable clickable command rows with hover feedback",
    )
    panels = PANELS.read_text(encoding="utf-8")
    physical_onboard = section(panels, '"VH onboard screen"', '"VHP GOES selector"')
    onboard_prepare = section(game, '"VHG onboard prepare"', '"VHG device overlay"')
    onboard_gaze = section(game, '"VHG onboard gaze"', '"VHG onboard gaze forward"')
    onboard_select = section(game, '"VHG onboard select"', '"VHG systems reset action"')
    original_screen = section(original, "void screen ()", "/* Disegna la mappa")
    original_gaze = section(original, "// Controllo gestore", "if (select && pwr")
    check(
        all(token in original_screen for token in (
            "for (p=-2; p<2; p++)", "for (c=-64; c<64; c++)",
            "cam_x = x - c*30;", "cam_y = y - p*50;",
            "digit_at (ctb[t], -6, -16, 4, screencolor, 1);",
        ))
        and all(token in physical_onboard for token in (
            "at z=0", "[VHPonc] = 0FFFFFFC0h", "[VHPonc] = 0FFFFFFD4h",
            "[VHPonc] = 0FFFFFFEFh", "[VHPonc] = 10", "[VHPonc] = 37",
            "[VHPonp] = 0FFFFFFFEh", "[VHPonp] = 0FFFFFFFFh",
            "A = [VHPonc]; A '* 30;", "A = [VHPonp]; A '* 50;",
            "A - 12; [VHPonx0] = A;", "C + 10; [VHPonx1] = C;",
            "A - 24; [VHPony0] = A;", "C + 16; [VHPony1] = C;",
            "[vhcpoly plus 2] = 0;", "[DGshader] = 1; => FB digit at;",
        ))
        and all(token in onboard_prepare for token in (
            "[VHPonsys] = 0;", '"VHG onboard prepare FCS"',
            '"VHG onboard prepare root"', '"VHG onboard prepare nav"',
            '"VHG onboard prepare misc"', '"VHG onboard prepare cart"',
            '"VHG onboard prepare emergency"', '"VHG onboard prepare browser"',
            "[VHPoncmd0] = VHGsrcdevnav;", "[VHPoncmd1] = VHGsrcdevmisc;",
            "A = VHGsrcampoff;", "A = VHGsrcfinderoff;",
            "A = VHGsrctrackoff;", "A = VHGsrcradoff;",
            "[VHPoncmd0] = VHGsrccartstar;", "[VHPoncmd0] = VHGsrcreset;",
            "[VHPoninfo2] = VHGdevselect;", "=> VHG browse format rows;",
        ))
        and all(token in original_gaze for token in (
            "Forward (zz/2);", "while (zz>25&&xx<3000);",
            "if (cam_x<-44*30)", "if (cam_x>-68*30)",
            "s_control = (cam_y + 25) / 50 + 3;",
            "s_command = (cam_x + 44*30) / (27*30) + 1;",
        ))
        and all(token in onboard_gaze for token in (
            "[VHGgazestep] = A; => VHG onboard gaze forward;",
            "? A <= 25 -> VHG onboard gaze hit;",
            "? A >= 3000 -> VHG onboard gaze done;",
            "A >= 0FFFFFAD8h -> VHG onboard gaze command;",
            "? A <= 0FFFFF808h -> VHG onboard gaze done;",
            "A = [VHGgazey]; A + 25; A / 50; A + 3;",
            "A + 1320; A / 810; A + 1;",
        ))
        and all(token in onboard_select for token in (
            "PD LEFT BUTTON DOWN", "[VHGgazeheld] = 1;",
            '"VHG onboard select FCS"', '"VHG onboard select devices"',
            '"VHG onboard select prefs"', '"VHG onboard select off"',
            "A + 53; [VHGascii] = A;",
        ))
        and all(token in physical_onboard for token in (
            '"VHP onboard selection"', "[VHPoncommand]", "A '* 810; A - 2160;",
            "[VHPsz0] = 0FFFFFFFEh;", "=> VHP integer stick;",
        ))
        and all(token in game for token in (
            "VHGsrcdevnav = { navigation instruments };",
            "VHGsrcampoff = { starfield amplificator };",
            "VHGsrctracksync = { syncrone orbit };",
            "VHGsrccartparsis = { set target to parsis };",
            "VHGsrclithiumoff = { scope for lithium };",
        ))
        and "=> VHG onboard prepare; => VH onboard screen;" in game
        and "A = [VHGdevaccess]; ? A = 0 -> VHG device overlay done;" in game
        and "A = [VHGdevaccess]; ? A = 0 -> VHG FCS menu overlay done;" in game,
        "source z=0 onboard computer uses the original control, command, and information grid",
    )
    original_prefs = section(original, "void prefs ()", "/* Comandi di impostazione")
    original_pfs = section(original, "void pfs_commands ()", "/* Comandi impartiti")
    preference_step = section(game, '"VHG preference step"', '"VHG tracking apply"')
    preference_key = section(game, '"VHG preference key"', '"VHG device key"')
    preference_overlay = section(game, '"VHG preferences overlay"', '"VHG browse format rows"')
    accessibility_release = section(game, '"VHG accessibility release"', '"VHG onboard select"')
    check(
        all(token in original_prefs for token in (
            'command (1, "auto screen sleep on");',
            'command (2, "reverse pitch controls");',
            'command (3, "menus always onscreen");',
            'command (4, "depolarize");',
        ))
        and all(token in original_pfs for token in (
            "toggle_option (&autoscreenoff);", "toggle_option (&revcontrols);",
            "toggle_option (&menusalwayson);", "toggle_option (&depolarize);",
        ))
        and all(token in onboard_prepare for token in (
            "[VHPonsys] = 3;", "VHGprefautooff", "VHGprefnormal",
            "VHGprefhidden", "VHGprefdepolarize",
        ))
        and all(token in preference_step for token in (
            "[VHGautoscreentick]-;", "[VHGautoscreentick] = 100;",
            "[VHGnavfrac]", "[VHGnavvel]", "A '* 10; A / 11;",
        ))
        and all(token in preference_key for token in (
            '"VHG preference auto"', '"VHG preference reverse"',
            '"VHG preference menus"', '"VHG preference hull"',
            "=> VHG hull cache apply;", "[VHRcacheexpected] = 2880; C = 3;",
        ))
        and all(token in physical_onboard for token in (
            "[VHPalwayson]", "[VHPoninfoarea]", '"VHP onboard ctl2 ready"',
        ))
        and all(token in preference_overlay for token in (
            "VHGprefmenutitle", "VHGprefmautooff", "VHGprefmreverse",
            "VHGprefmalways", "VHGprefmpolarize", "VHGprefmenuhint",
        ))
        and all(token in accessibility_release for token in (
            "A = [VHGdev]; A | [VHGfcsopen]; A | [VHGprefs];",
            "[VHGdevaccess] = 0;",
        ))
        and all(token in (ROOT / "work" / "vhrmap.txt").read_text(encoding="utf-8") for token in (
            "VHRCCAP = 2880;", "VHRcacheexpected = 720;", "vhrcache = 28800;",
        )),
        "physical Preferences restore source toggles, menu sleep, steering, and depolarized hulls",
    )
    original_fcs = section(original, "void fcs ()", "/* Comandi dell'FCS. */")
    onboard_fcs = section(
        game, '"VHG onboard FCS information"', '"VHG onboard prepare"'
    )
    check(
        all(token in original_fcs for token in (
            'cline (1, "local target: ");', 'other ("moon #");',
            'other (ord[n + 1]);', 'other (planet_description[nearstar_p_type[ip_targetted]]);',
            'cline (2, "remote target: class ");', 'other (star_description[ap_target_class]);',
            'cline (3, "current range: elapsed ");', 'other (alphavalue(charge));',
        ))
        and all(token in onboard_fcs for token in (
            '[VHGonrowdst] = VHGonboardrow0;', '[VHGlocaltarget]',
            'E = nspowner;', 'E = nspmoonid;', '=> VHG onboard select ordinal;',
            'E = nsptype;', '=> VHG onboard select planet description;',
            '[VHGonrowdst] = VHGonboardrow1;', '[MgAptgt]', '[VHTclass]',
            '=> VHG onboard select star description;',
            '[VHGonrowdst] = VHGonboardrow2;', '[MgPwr]', '[MgCharge]',
        ))
        and all(token in game for token in (
            'VHGfcslocalprefix = { local target: };',
            'VHGfcsremoteprefix = { remote target: class };',
            'VHGfcsrangeprefix = { current range: elapsed };',
            'VHGstardesc0 = { medium size, yellow star, suitable for planets having indigenous lifeforms. };',
            'VHGplanetdesc3 = { medium size, felisian, breathable atmosphere, suitable for life. };',
            '[VHPoninfo0] = VHGonboardrow0;', '[VHPoninfo1] = VHGonboardrow1;',
            '[VHPoninfo2] = VHGonboardrow2;',
        )),
        "physical FCS shows the original live local, remote, range, and lithium rows",
    )
    original_devices = section(
        original, "void devices ()", "/* Comandi dei dispositivi di bordo. */"
    )
    onboard_nav = section(
        game, '"VHG onboard navigation information"', '"VHG onboard FCS information"'
    )
    catalog_count = section(
        catalog, '"VHCAT count system bodies"', '"VHCAT add"'
    )
    check(
        all(token in original_devices for token in (
            'cline (1, "starfield amplification active, ");',
            'other ("high-radiation fields are avoided.");',
            'cline (2, "tracking status: disconnected.");',
            'cline (3, "planet finder report: system has ");',
            'other (alphavalue(nearstar_labeled));',
            'other (" labeled out of ");',
        ))
        and all(token in onboard_nav for token in (
            '[VHGonrowsrc] = VHGnavampactive;', '[VHGantirad]',
            '[VHGonrowsrc] = VHGnavtrackdisconnected;', '[MgIpreached]',
            '[VHGonrowsrc] = VHGnavfinderprefix;', '[nsnop]', '[nsnob]',
            '[VHGonrowvalue] = [VHCATlabeled];',
            '[MgDzatX0]', '[MgDzatY0]', '[MgDzatZ0]', '=> FSqrt;',
            '? A >= 20000 -> VHG onboard nav finder far;',
        ))
        and all(token in catalog_count for token in (
            '[VHCATlabeled] = 0;', '[VHCATbodyi] = 1;',
            '? A > [nsnob] -> VHCAT count system bodies done;',
            '[nsid0] = [VHTid0];', '=> NsIdentAddInt;',
            '[VHCATtype] = VHCATP;', '=> VHCAT find;', '[VHCATlabeled]+;',
        ))
        and '=> VHG onboard navigation information;' in onboard_prepare
        and '=> VHCAT count system bodies; => VHCAT refresh;' in game,
        "physical navigation page restores live source status and finder rows",
    )
    onboard_cart = section(
        game, '"VHG onboard cartography information"',
        '"VHG onboard navigation information"',
    )
    check(
        all(token in original_devices for token in (
            'cline (1, "epoc ");', 'other (" triads ");',
            'other (formatTriad(lsecs));',
            'cline (2, "parsis universal coordinates: ");',
            'fld dzat_x', 'fld dzat_y', 'fld dzat_z', 'frndint',
            'cline (3, "heading pitch: ");',
            'sin(deg*navigation_beta)*+100', 'cos(deg*navigation_beta)*-100',
        ))
        and all(token in onboard_cart for token in (
            '[VHGutcsecs]', 'A + 6011;', '=> VHG onboard row append triad;',
            '[MgDzatX0]', '[MgDzatY0]', '[MgDzatZ0]', '=> FToIntNear;',
            '[VHVangle] = [VHGnavbeta]; => VHV sincos;',
            '[FS0] = [VHVsin];', '[FS0] = [VHVcos];',
            '[FI] = 100;', 'A - 100;', '=> FToIntChop;',
        ))
        and '=> VHG onboard cartography information;' in onboard_prepare
        and all(token in game for token in (
            '[VHPoninfo0] = VHGonboardrow0;',
            '[VHPoninfo1] = VHGonboardrow1;',
            '[VHPoninfo2] = VHGonboardrow2;',
        )),
        "physical cartography page restores live EPOC, Parsis, and heading rows",
    )
    onboard_emergency = section(
        game, '"VHG onboard emergency information"',
        '"VHG onboard cartography information"',
    )
    check(
        all(token in original_devices for token in (
            'if (gburst == -1)',
            'cline (1, "NOTE: there are no emergencies at the moment.");',
            'cline (2, "help request not sent.");',
        ))
        and all(token in onboard_emergency for token in (
            '[VHGonrowdst] = VHGonboardrow0;',
            '[VHGonrowdst] = VHGonboardrow1;',
            '[VHGonrowdst] = VHGonboardrow2;',
            '[VHGgburst]', '[VHGonrowsrc] = VHGemerquiet;',
            '[VHGonrowsrc] = VHGemernotsent;',
        ))
        and '=> VHG onboard emergency information;' in onboard_prepare,
        "physical emergency page restores the original quiet-state report",
    )
    check(
        "=> TK seed; => TK start;" in game and "=> TK step;" in game,
        "live loop uses the original 54.925 ms synchronizer",
    )

    original_cupola = section(original0, "void polycupola", "void sync_start")
    check(
        "dd = 1000 - sqrt (d1*d1 + d2*d2);" in original_cupola
        and "if (dd > 600) dd = 600;" in original_cupola
        and "cam_y += dd;" in original_cupola,
        "original local cupola aperture formula remains pinned",
    )
    roof = section(cupola, '"VHC roof view"', '"VHC generate"')
    check(
        "A = 1000; A - [FI]" in roof
        and "[VHCdd] = 600" in roof
        and "? A >= 0 -> VHC roof dd nonnegative;" in roof
        and "? A >= 0 -> VHC capsule dd nonnegative;" in roof
        and "A = [VHCcamybase]; A + [VHCdd]" in roof,
        "port applies the same local 1000-radius/600-clamp displacement",
    )
    roof_midpoints = section(cupola, '"VHC roof view"', '"VHC capsule view"')
    capsule_midpoints = section(cupola, '"VHC capsule view"', '"VHC generate"')
    check(
        roof_midpoints.count("[PGFi] = FSW3; [PGFt] = VHCHALF; => PGF setf32;") == 1
        and capsule_midpoints.count("[PGFi] = FSW3; [PGFt] = VHCHALF; => PGF setf32;") == 1
        and roof_midpoints.count("=> PGF add;\n\t[PGFi] = FSW3; => PGF mul;") == 2
        and capsule_midpoints.count("=> PGF add;\n\t[PGFi] = FSW3; => PGF mul;") == 3
        and "=> PGF add;\n\t[PGFi] = FSW1; [PGFt] = VHCHALF" not in roof
        and "=> PGF add;\n\t[PGFi] = FSW2; [PGFt] = VHCHALF" not in roof,
        "cupola midpoint sums survive the 0.5 load and track each real panel",
    )
    check(
        [cupola_panel_drop(distance) for distance in (0, 399, 400, 401, 999, 1000, 1200)]
        == [600, 600, 600, 599, 1, 0, 0],
        "cupola aperture model pins the capped, sloped, and closed distance regions",
    )
    grid = section(cupola, '"VHC render grid"', '"VHC render next"')
    check(
        "=> VHC roof view;" not in grid and "=> VHC draw grid;" in grid,
        "cupola support grid stays fixed like original cupola()",
    )
    upper_order = section(game, "Exact vehicle() order", '"VHG interior details"')
    check(
        "[VHGonroof]" in upper_order
        and "[VHGlifter]" not in upper_order
        and "0FFFFFEBBh" not in upper_order,
        "upper cupola aperture is armed only by the original ontheroof state",
    )

    tile = section(ground, '"VHGND tile"', '"VHGND tile objects"')
    check(
        tile.count("=> PG polymap;") == 2
        and tile.count("=> PG poly3d;") == 2
        and tile.count("[VHGNDdepth]; ? A '<= 1") == 2
        and '"VHGND tile first flat"' in tile
        and '"VHGND tile second flat"' in tile
        and "[PGtexf] = 5" in ground
        and '"PG tex 5"' in (ROOT / "work" / "pgmem.txt").read_text(encoding="utf-8"),
        "landing textures the nearest ground triangles and flat-shades coarse LOD",
    )
    depth = section(ground, '"VHGND tile depth"', '"VHGND tile shade"')
    shade = section(ground, '"VHGND tile shade"', '"VHGND vload"')
    check(
        "[SUfmask] = 7; => SU frnd;" in shade
        and "A = [VHGNDh1]; A + [VHGNDseed]; => SU fast srand;" in shade
        and "=> VHGND tile depth;" in shade
        and "=> FAdd; => FSqrt; => FToIntChop;" in depth
        and "? C '<= 32" in shade
        and "A = [VHGNDshade]; [SPtinta] = A; [DBcol] = A;" in tile
        and "=> VHGND palette" not in game,
        "landing terrain uses the original diffuse shade and ground-palette band",
    )
    check(
        all(token in ground for token in (
            '"VHGND generate type8"', '"VHGND generate type4"',
            '"VHGND similar texture"', '"VHGND texture darkline"',
            "[GRscmap] = [VHGNDtexbase]", "[VHGNDtscale] = 32",
            '"VHGND globe surface"', '"VHGND globe palette copy"',
            "[VHGNDpalcount] = 192;", "[PUn] = 256; => PAL upload;",
        ))
        and "=> VHGND generate;" not in section(
            game, '"VHG local ensure surface"', '"VHG local center coords"'
        ),
        "live type-8/type-4 branches build their source terrain textures",
    )
    original_capsule = section(original1, "if (landed&&atl_x==x&&atl_z==z)", "else {")
    capsule = section(ground, '"VHGND capsule"', '"VHGND traverse"')
    settled_capsule = section(ground, '"VHGND capsule"', '"VHGND moving capsule"')
    moving_capsule = section(ground, '"VHGND moving capsule"', '"VHGND render ruins"')
    check(
        "polycupola (-1, 1)" in original_capsule
        and "polycupola (+1, 1)" in original_capsule
        and original_capsule.count("stick3d") == 3
        and "[VHCyor] = 0FFFFFFFFh" in capsule
        and settled_capsule.count("=> VH cupola grid;") == 2
        and settled_capsule.count("=> VH polycupola; => VH cupola grid;") == 2
        and moving_capsule.count("=> VH polycupola; => VH cupola grid;") == 2
        and "A + 1415" in capsule and "A + 385" in capsule and "A + 900" in capsule
        and capsule.count("=> VH stick3d;") == 3
        and "A # 80000000h" in cupola
        and '"VHC capsule view"' in cupola
        and "A = 500; A - [FI]" in cupola
        and "A = [VHCyor]; ? A >= 0 -> VHC capsule shift positive;" in cupola
        and "A = [VHCdd]; A + A; A + A;" in cupola
        and "A + [VHCcamybase]; [FI] = A;" in cupola
        and "? A != 0 -> VHC draw panel done;" not in cupola
        and '"VHC draw textured panel"' in cupola
        and all(token in cupola for token in (
            "[VHCvi] = [VHCi];", "A = [VHCi]; A - 1;",
            '"VHC panel source capsule"', '"VHC draw grid"',
            "[VHSflare] = 0;", '"VHC polycupola render"',
            "[PGFi] = FSZERO;", "[VHCtexx] = [FS0];", "[VHCtexy] = [FS0];",
        ))
        and all(token in stick for token in (
            "VHSflare = 0; VHSphase = 0;", '"VHS luminous point"',
            "A = [VHSphase]; A & 1;", "C & 63; C + 8;",
            "[SPval] = 0; => SP put;", "[SPoff]+; [SPval] = [VHScolor]; => SP put;",
            '"VHS endpoints ordered"', "? A >= [VHSpx0] -> VHS endpoints ordered;",
        ))
        and all(token in settled_capsule for token in (
            '"VHGND capsule beacon"', "[VHSflare] = 1;",
            "[VHSy1] = 3388220416;", "[VHSy0] = 3305119744;",
            "? A < 6 -> VHGND capsule beacon;", "[VHSflare] = 0;",
        ))
        and "[PGtexf] = 7;" in cupola and "[SPflar] = 4;" in cupola
        and '"PG tex 7"' in (ROOT / "work" / "pgmem.txt").read_text(encoding="utf-8")
        and "[PGtexv] = 0;" in (ROOT / "work" / "pgmem.txt").read_text(encoding="utf-8"),
        "landed and moving capsule views keep both animated shells, support grids, and beacon",
    )
    check(
        all(token in original1 for token in (
            "pos_y = hpoint (pos_x, pos_z) - 3.2E5;",
            "gravity = - 0.32 * gravity;",
            "gravity < 250", "compdist < 512 || bounces > 10",
            "opencapcount > 32", "opencapcount > 250",
            "if (sqrt(drop_x*drop_x+drop_y*drop_y+drop_z*drop_z)<1600)",
            "if (recover)", "recover = 1;",
        )),
        "original capsule fall, settle, seal, and ascent thresholds remain pinned",
    )
    check(
        all(token in capsule_physics for token in (
            "A - 320000; [VHGy] = A;",
            "[VHGCgravity] = 3096; [VHGCaccel] = 99;",
            "[VHGCgravity] = 1752; [VHGCaccel] = 56;",
            "A '* 32; A / 100", "? A > 10 -> VHGC settle;",
            "? A '>= 2500 -> VHGC bounce;", "=> VHGC slope scan;",
            "? A '< 512 -> VHGC settle;", "? A '> 32 -> VHGC lift off;",
            "? A '<= 250 -> VHGC ascent done;", "[VHGcapsulereturnpending] = 1;",
            '"VHGC wind init"', '"VHGC wind step"',
            "A = [VHGNDatmosphere]; ? A = 0 -> VHGC wind done;",
            "[VHGCwindrngsave] = [brtlseed]", "[brtlseed] = [VHGCwindrngsave]",
            '"VHGC wind evolve"', "A = [GRalbedo]; => BrtlRandom;",
            "A '* 512; A / 25;", "A '* [VHGCwindrequired]; A / 1024;",
            "A '* 917; A / 10240;",
            "A = [VHGx]; A - [FI]; [VHGx] = A;",
            "A = [VHGz]; A + [FI]; [VHGz] = A;",
            "=> VHGND eye height;", '"VHGC slope scan loop"',
            "[FB0] = 9999999Ah; [FB1] = 3F999999h; => FAdd;",
            "=> FSin;", "=> FCos;", "[VHGCslopedir] = [VHGCslopet];",
        ))
        and "[VHGCsubsteps] = 1;" in capsule_physics
        and "[VHGCstate] = 2; [VHGCcapcount] = 0;" in capsule_physics
        and capsule_physics.count("A / 8;") >= 2
        and "C / 8; A = [VHGy];" in capsule_physics
        and "=> VHG return ship;" not in capsule_physics
        and "A + 724;" not in capsule_physics
        and "=> VHGC tick;" in game
        and "=> VHGND moving capsule;" in game,
        "live capsule visibly descends, bounces, settles, seals, and returns",
    )
    land = section(game, '"VHG land"', '"VHG prepare planet"')
    check(
        "? A '< [nsnob] -> VHG land target valid;" in land
        and "[VHGnoticeptr] = VHGdescenttext" in land
        and "[VHGnoticeptr] = VHGlandfailtext" in land
        and "[VHGCsubsteps] = 1;" in capsule_physics,
        "landing validates the body and advances descent at the original visible rate",
    )
    post = section(ground, '"VHGND post surface"', '"VHGND flandom"')
    cache_objects = section(
        ground, '"VHGND cache objects"', '"VHGND animals setup"'
    )
    objects = section(ground, '"VHGND tile objects"', '"VHGND veget"')
    rocks = section(ground, '"VHGND rock"', '"VHGND rock height"')
    check(
        '"VHGND felisian line"' in post
        and "A & 0FCh; A | [VHGNDoval]" in post
        and "[VHGNDobjbyte] = A; A & 3; [VHGNDocount] = A;" in objects
        and "[SUfmask] = [VHGNDrockdensity]" in rocks
        and rocks.count("=> PG poly3d;") == 4
        and all(token in rocks for token in (
            "A = [VHGNDdepth]; ? A >= 8 -> VHGND rock done;",
            "A = [VHGNDdepth]; ? A > 2 -> VHGND rock distant;",
            '"VHGND rock distant"', "[SUfmask] = 71; => VHGND render random; [DBcol] = C;",
            '"VHGND rock repeat"', "A '* 5; [VHGNDrockworkscale] = A;",
            "A '* 1000; A '* [VHGNDcdown];", "A '/ 2; [VHGNDrockworkscale] = A;",
            "[VHGNDcdown]-; A = [VHGNDcdown]; ? A > 0 -> VHGND rock repeat;",
        )),
        "rocks retain source distant triangles and complete close tetrahedral groups",
    )
    traversal = section(ground, '"VHGND render"', '"VHGND tile"')
    check(
        all(token in ground for token in ("VHGNDFAR = 64", "VHGNDMID = 24"))
        and all(token in traversal for token in (
            "[VHGNDlodstep] = 32", "[VHGNDlodstep] = 8",
            "[VHGNDlodstep] = 1", "=> VHGND traverse;",
        ))
        and "[SPcull] = 1" in tile
        and "A > [VHGNDmaxdepth]" in tile,
        "landed renderer covers the source 64-tile radius with distance-aware rings",
    )
    distant_objects = section(
        ground, '"VHGND render distant objects"', '"VHGND tile"'
    )
    check(
        "if (depth > 40) return;" in original1
        and "VHGNDOBJECTFAR = 40;" in ground
        and all(token in distant_objects for token in (
            "[VHGNDlodstep] = 1;", "A = nw; A + ROBJ; A + [VHGNDh1];",
            "? A = 0 -> VHGND distant object next;",
            "=> VHGND object view cull;", "A '* 3; A '/ 4; A + 128;",
            "? A '>= 7225344 -> VHGND object view hidden;",
            "=> VHGND tile depth;",
            "A = [VHGNDdepth]; ? A <= 3 -> VHGND distant object next;",
            "? A > VHGNDOBJECTFAR -> VHGND distant object next;",
            "=> VHGND tile objects;",
        )),
        "surface objects retain the original depth-40 horizon with empty cells rejected early",
    )
    check(
        "grnd; sky;" in game and "spglobe; spglow; spbg;" in game
        and "=> GRSK create; => GRSK horizon;" in ground
        and "[SPval] = 0; => SP fill page;" in ground
        and '"VHGND guard band"' in ground
        and "=> VHGND background direct;\n\t=> VHGND guard band;" in ground
        and "[BGdstreg] = RGADP; => SP background;" not in ground
        and '"VHGND background direct"' in ground
        and '"VHGND background cache save"' in ground
        and '"VHGND background cache restore"' in ground
        and "VHGNDskycache = 64000" in ground
        and "A & 65535; [BGdi] = A;" in ground
        and '"VHGND surrounding frame"' in ground
        and "A = 64; A + [VHGNDsurlight]; A - [VHGNDframei];" in ground
        and "A = 190; A + [VHGNDframei]; A '* 320;" in ground
        and "C = 310; C + [VHGNDframei];" in ground
        and "=> VHGND dense atmosphere; -> VHGND render finish;" in ground
        and all(token in ground for token in (
            "[GRSKseed] = 149130", "[GRSKalbedo] = 32",
            "[GRSKseed] = 293154", "[GRSKalbedo] = 20",
        ))
        and "A = [VHGNDstormflashes];" in ground
        and "A '* 25; [VHGNDflashtries] = A;" in ground
        and all(token in original1 for token in (
            "wdirsin -= (pos_z - refz) * 0.333;",
            "wdircos -= (pos_x - refx) * 0.333;",
            "setfx (1);", "Forward (-1000);",
            "ptr = random(3) + 1", "flash = random (150 / rainy);",
            "w = random (64) + 64;",
            "s_background[ptr] = 63 - s_background[ptr];",
        ))
        and all(token in ground for token in (
            "A = [VHGNDcamx]; A - [VHGNDplayerrefx]; A '* 333; A / 1000;",
            "A = [VHGNDcamz]; A - [VHGNDplayerrefz]; A '* 333; A / 1000;",
            "A = [VHGNDcamx]; A + [FI]; [VHVcamxi] = A;",
            "A = [VHGNDcamz]; A - [FI]; [VHVcamzi] = A;",
            "A = [VHGNDcamy]; A - [FI]; [VHVcamyi] = A;",
            "=> FMul; [FB0] = [FA0]; [FB1] = [FA1];",
            "[VHSflare] = 1;", "[VHSflare] = 0;",
            "[FI] = 150; => IntToF; => FQuo; => FToIntChop;",
            "A % 3; A + 1;", "A % 64; A + 64;",
            "C '* [VHGNDflashgain]; C '/ 63;",
            "[VHGNDflashactive] = [VHGNDflashpending]; [VHGNDflashpending] = 0;",
            '"VHGND background lightning invert"',
            "A = [D]; C = 63; C - A; [D] = C;",
        ))
        and "[VHGNDplayerrefx] = [VHGsurfrefx]; [VHGNDplayerrefz] = [VHGsurfrefz];" in game
        and ground.index("=> VHGND weather lightning begin;")
        < ground.index("[VHGNDruindrawn] = 0; => VHGND background;")
        and "? A '<= 5 -> VHGND weather density ready;" not in ground,
        "live landings cache the generated panorama through a direct wrapping mapper",
    )
    local_sun = section(ground, '"VHGND local sun"', '"VHGND surrounding frame"')
    secondary_sun = section(ground, '"VHGND secondary sun setup"', '"VHGND local sun"')
    check(
        all(token in local_sun for token in (
            "A = [GRSKnightzone]; ? A != 0 -> VHGND local primary done;",
            "A = [GRSKrainy]; ? A '>= 40200000h -> VHGND local primary done;",
            "[FS0] = [GRSKdsd1]; => FLoadF32;",
            "A = [VHGNDsunxf]; ? A >= 0 -> VHGND sun x ready; => FNeg;",
            "E = nsptype; E + A; C = [E]; ? C != 10 -> VHGND sun radius ready;",
            "[WHshape] = 1; [WHsun] = 1; [WHdstreg] = RGADP; => SP white;",
            "=> F32Narrow; [VHGNDsuncoord] = [FS0]; [FS0] = [VHGNDsuncoord]; => FLoadF32;",
        ))
        and "[GRSKatmosphere] = [VHGNDatmosphere]; [GRSKnightzone] = 0; [VHGNDsunxf] = 1;" in ground
        and "[VHGNDcrep] = A; A = 0; A - 1; [VHGNDsunxf] = A;" in ground
        and traversal.index("=> VH set view;")
        < traversal.index("=> VHGND local sun;")
        < traversal.index("( Source fragment()")
        and all(token in original1 for token in (
            "sun_x = -dsd1 * cos(beta) * sun_x_factor;",
            "sun_y = -dsd1 * sin(beta) * sin(alfa);",
            "sun_z = +dsd1 * sin(beta) * cos(alfa);",
            "if (!nightzone && rainy < 2.5)",
        )),
        "surface daylight draws the source-positioned active sun before terrain",
    )
    check(
        "=> VHGND secondary sun setup;" in ground
        and all(token in secondary_sun for token in (
            "A = [VHGNDseci]; ? A >= [nsnob] -> VHGND secondary scan done;",
            "E = nsptype; E + A; C = [E]; ? C != 10 -> VHGND secondary scan next;",
            "E = nspowner; E + [VHGNDplanet]; A = [E];",
            "[VHGNDsecdist] = [VHGNDsecbest];",
            "[VHGNDsecray] = [nsstarray];",
            "=> VHGND secondary latitude;",
            "[VHGNDsecnight] = 1;",
            "[VHGNDseccrep] = A; A = 0; A - 1; [VHGNDsecxf] = A;",
        ))
        and all(token in local_sun for token in (
            "=> VHGND secondary sun;",
            "A = [GRSKrainy]; ? A '>= 40000000h -> VHGND secondary sun done;",
            "[FS0] = [VHGNDsecray]; => FLoadF32; => FMul; => F32Narrow;",
        ))
        and all(token in original1 for token in (
            "if (nearstar_p_type[w] == 10)",
            "if (nearstar_p_qsortdist[w] < compdist)",
            "nray2 = nearstar_p_ray[w];",
            "if (secondarysun)",
            "if (!pri_nightzone && rainy < 2.0)",
        )),
        "multiple systems restore the source secondary-sun role and terminator path",
    )
    surface_flare = section(flare, '"VH surface flare"', '"VHF draw"')
    check(
        "=> VHGND render birds;\n\t=> VHGND sun flares;" in ground
        and all(token in local_sun for token in (
            '"VHGND sun flares"', '"VHGND flare project"',
            "A = [GRSKrainy]; ? A '>= 3F99999Ah -> VHGND primary flare done;",
            "? A = 6 -> VHGND primary flare done; ? A = 10 -> VHGND primary flare done;",
            "A = [GRSKrainy]; ? A '>= 40066666h -> VHGND sun flares done;",
            "[VHFdist] = [GRSKdsd1]; [VHFray] = [VHGNDsunray]; => VH surface flare;",
            "[VHFdist] = [VHGNDsecdist]; [VHFray] = [VHGNDsecray]; => VH surface flare;",
        ))
        and all(token in surface_flare for token in (
            "[SPoff] = A; [SPreg] = RGADP; => SP get;",
            "A = [SPval]; ? A < 64 -> VHF done;",
            "[FI] = 1000; => IntToF; => FMul;",
            "[FI] = 10; => IntToF; => FQuo;",
        ))
        and all(token in original1 for token in (
            "if (!nightzone && rainy < 1.2)",
            "if (nearstar_class!=5&&nearstar_class!=6&&nearstar_class!=10)",
            "if (dsd1<1000*nray1&&dsd1>=10*nray1)",
            "if (!pri_nightzone && rainy < 2.1)",
        )),
        "surface suns restore source-gated center-occluded lens flares",
    )
    check(
        all(token in star for token in (
            "VHTphase = 0; VHTspin = 0;", '"VHT spin class11"',
            '"VHT spin class7"', '"VHT spin class2"',
            '"VHT phase advance"', "[VHTprevphase] = [VHTphase];",
            "A = [VHTspin]; A + [VHTphase]; A % 360; [VHTphase] = A;",
            "A = [VHTspin]; A '* [VHTinterpacc]; A / 60000;",
            "[VHTrenderphase] = [VHTclockphase];",
            '"VHT visibility"', "[VHTwhiteok] = 0; [VHTglobeok] = 0;",
            "[FI] = 1; => IntToF;", '"VHT saturation"',
            "[SUfmask] = 31; => SU fast raw;", "A + 29;",
            '"VHT palette saturation"', "[VHTpalfar] = 1; [VHTpalsat] = 0;",
            '"VHT premask"', "[FI] = 6; => IntToF;",
            "? A = 6 -> VHT premask smooth; ? A = 10 -> VHT premask smooth;",
            "A = [VHTphase]; A % 360; ? A >= 90 -> VHT premask smooth;",
            "[VHFk] = [FS0]; => VH space flare;", '"VHT smooth grays"',
            "[SUsi] = 320; B = 56960;", "B ^ VHT smooth gray pixel;",
            "[FI] = 100; => IntToF;", "[FI] = 8; => IntToF;",
            "[FI] = 1550; => IntToF;", "[FI] = 1600; => IntToF;",
            '"VHT far pixel"', "=> VHT far spread; => VHT far spread; => VHT far spread;",
            '"VHT far spread"', "A = [VHTfarcolour]; A > 4;",
            '"VHT texture cycle"', "? A < 64800 -> VHT texture cycle texel;",
            "C = [A]; C & 255; D = C; D & 192; C + 1; C & 63; C | D; [A] = C;",
            '"VHT mask page"', "C = [A]; C & 63; C + 64; [A] = C;",
            "? A < 58240 -> VHT mask page pixel;",
        ))
        and "A = [MgApreached]; ? A = 0 -> VHT render done;" not in star
        and all(token in game for token in (
            "=> VHT visibility; A = [VHTwhiteok]; ? A = 0 -> VHG local star premask;",
            "=> VHG local companion coronas; => VHT premask; => VHT mask page;",
            "A = [VHTglobeok]; ? A = 0 -> VHG local star far;",
            "[GBcmask] = 64; [GBsat] = [VHTglobesat];",
            "A = [VHTfarok]; ? A = 0 -> VHG local planet render; => VHT far pixel;",
            '"VHG local companion coronas"',
            "=> VHG local body relative; => VHG local body distance;",
            "[FA0] = [VHGlocaldist0]; [FA1] = [VHGlocaldist1]; => F32Narrow; => FLoadF32;",
            "[FI] = 5; => IntToF;", "[FI] = 1000; => IntToF;",
            "[VHFk] = [FS0]; => VH space flare;",
            "=> VHS stars; => VHG finder render;",
        ))
        and all(token in flare for token in (
            '"VH space flare"', "[VHFadd] = 3; [VHFok] = 0;",
            "[PGFi] = SFRX; => PGF a; [PGFi] = SFRZ; => PGF quo; => FToIntChop;",
            "A = [FI]; A + 3;", "? A >= 90 -> VHF done; A + 100; [VHFcy] = A;",
        ))
        and game.index("=> VHS stars; => VHG finder render;") > game.index("=> VH set view; [VHLpower] = [VHGilight]; [VHLemergency] = [VHGelight]; => VH alogena;")
        and all(token in space for token in (
            "C '* 320; C + A; C + 4; [SPoff] = C;",
            "C = [SPval]; ? C < 64 -> VHS draw next; ? C > 92 -> VHS draw next;",
            "D = C; D & 192; C & 63; C + [VHScolour];",
            "? C > 92 -> VHS replay next;",
            '"VHS fade"', "C + 2876; [VHSfadebase] = C;",
            "? C >= 8 -> VHS fade subtract;", "? A < 57920 -> VHS fade pixel;",
        ))
        and all(token in game for token in (
            "A = [MgStspeed]; ? A != 0 -> VHG render space fade;",
            "=> VHS fade;", "[VHGspacevalid] = 1;",
        ))
        and "[VHTphase] = [VHGframe];" not in game
        and "A = [VHGframe]; A % 360; [GBstart] = A;" not in game
        and game.count("=> VHT phase advance;") >= 1
        and all(token in game for token in (
            "[VHTdosim] = [VHGdosim]; [VHTfast] = [VHGfast];",
            "[VHTinterpok] = [VHGinterpok]; [VHTinterpacc] = [VHGinterpacc];",
            "A = [TKtmp]; A / 360; A % 360; [VHTclockphase] = A;",
        ))
        and all(token in original0 for token in (
            "if (ap_target_class==11) ap_target_spin = random (30) + 1;",
            "if (ap_target_class==7) ap_target_spin = random (12) + 1;",
            "if (ap_target_class==2) ap_target_spin = random (4) + 1;",
        )),
        "resolved stars retain their source class-specific spin instead of universal rotation",
    )
    check(
        all(token in original1 for token in (
            "global_surface_seed = (nearstar_p_ray[ip_targetted]",
            "+ nearstar_p_orb_ray[ip_targetted]",
            "+ nearstar_p_orb_orient[ip_targetted]) * 4112;",
        ))
        and all(token in game for token in (
            "[GRiptype] = [VHGptype];", "[VHGNDseed] = 149130;",
            "[VHGNDseed] = 293154;", "[VHGNDseed] = 569446;",
            '"VHG land general seed"', "E = nsporbray;", "E = nspororient;",
            "=> GeoSurfaceSeedChop;",
        ))
        and all(token in (ROOT / "work" / "nstopo.txt").read_text(encoding="utf-8") for token in (
            "nspray", "nsporbray", "nsporideg", "nspororient", "nspring", "[nsstarray]",
            '"Ns geo store ray"', '"Ns geo store orbit"',
        ))
        and "[GRSKseed] = 149130" in ground
        and "[GRSKseed] = 293154" in ground,
        "opening seeds remain exact and general destinations use retained Noctis geometry",
    )
    check(
        all(token in original0 for token in (
            "nearstar_p_rotation[logical_id] = secs / nearstar_p_rtperiod[logical_id];",
            "plwp = 89 - cplx_planet_viewpoint (logical_id);",
            "nearstar_p_term_start[logical_id] = plwp + 35;",
            "nearstar_p_term_end[logical_id] = nearstar_p_term_start[logical_id] + 130;",
        ))
        and all(token in ground for token in (
            '"VHGND general sky"', '"VHGND UTC seconds"',
            '"VHGND orbital phase"', '"VHGND terminator"',
            "[Timer Command] = READ UTC TIME; isocall;",
            "=> VHG fpu clean; => SU fp init;",
            "[VHGNDtermstart] = A; A + 130;",
            "[GRSKnightzone] = 0;",
        )),
        "general landings derive source-shaped UTC orbital daylight and a 130-degree terminator",
    )

    # Every ring clamps its origin so the far corner x/z + step stays inside
    # the 200x200 map, including both walking-clamp endpoints.
    for tile_coord in (7, 100, 192):
        for radius, step in ((64, 32), (24, 8), (3, 1)):
            lo = max(0, tile_coord - radius)
            hi = min(199 - step, tile_coord + radius)
            coords = list(range(lo, hi + 1, step))
            check(
                bool(coords) and coords[0] >= 0 and coords[-1] + step < 200,
                f"terrain ring r{radius}/s{step} is in range at tile {tile_coord}",
            )

    surface_input = section(game, '"VHG surface input"', '"VHG quit"')
    check(
        "[VHGsurfground] = [VHGNDheight]; => VHG surface vertical;" in surface_input
        and '"VHG surface input done"' in surface_input
        and "-> VHG input done;" not in surface_input.split('"VHG surface look"', 1)[1],
        "landed input never falls through the ship-interior coordinate clamp",
    )
    check(
        "[VHGNDdropx]" in surface_input and "[VHGNDdropz]" in surface_input
        and surface_input.count("? A > 1600 -> VHG return too far;") == 2
        and "[VHGnoticeptr] = VHGreturnfartext;" in surface_input
        and '"VHG surface capsule proximity"' in surface_input
        and "? A '>= 2560000 -> VHG surface capsule arm;" in surface_input
        and "[VHGCrecover] = 1;" in surface_input
        and "A = [VHGx]; A - [VHGNDdropx]; A / 8;" in capsule_physics
        and "=> VHG surface capsule proximity;" in surface_input
        and "A = [VHGCstate]; ? A = 0 -> VHG surface motion available;" in surface_input
        and "[VHGsurfstep] = 0; [VHGsurfshift] = 0;" in surface_input
        and capsule_recovery_trigger([(0, 0, 0), (1600, 0, 0), (1599, 0, 0)]) == 2
        and capsule_recovery_trigger([(1200, 0, 1200), (1000, 0, 1000)]) == 1,
        "surface capsule recovery arms outside and starts automatically on spherical re-entry",
    )
    check(
        all(token in original1 for token in (
            "step += fixed_step;", "if (w >= 48 && w <= 57)",
            "if (fixed_step == (w * 10))", "fixed_step = (w * 10);",
        ))
        and all(token in surface_input for token in (
            '"VHG surface pace key"', "A - 48; A '* VHGNDSTALK; C = A;",
            "A = [VHGsurfacefixed]; ? A = C -> VHG surface pace cancel;",
            "A = [VHGsurfstep]; A + [VHGsurfacefixed]; [VHGsurfstep] = A;",
            '"VHG surface cruise moved"', "A = [VHGsurfstep]; A + [VHGstepv];",
            "A = [VHGsurfstep]; A - [VHGstepv];",
            '"VHG surface speed absolute"', "[VHGNDplayerstep] = A;",
        ))
        and "[VHGsurfacefixed] = 0; [VHGsurfstep] = 0; [VHGsurfshift] = 0;" in capsule_physics
        and [surface_cruise(0, digit) for digit in range(10)]
        == [0, 80, 160, 240, 320, 400, 480, 560, 640, 720]
        and surface_cruise(720, 9) == 0,
        "surface digits feed the retained source fixed-step velocity",
    )
    check(
        all(token in original1 for token in (
            "mouse_input ();", "if (mpul&1) step += 75 * landed;",
            "if (sctype == ICY)", "if (mpul&1) step += 150 * landed;",
            "if (sctype == PLAINS)", "if (mpul&1) step += 50 * landed;",
            "if (mpul&1) step += 125 * landed;",
            "if (w == 83)", "snapshot (0, 0);",
        ))
        and all(token in surface_input for token in (
            "A = [Client Owns Mouse Pointer]; ? A = NO -> VHG surface mouse moved;",
            "A = [Pointer Status]; ? A - PD LEFT BUTTON DOWN -> VHG surface mouse moved;",
            "A = [GRiptype]; ? A = 3 -> VHG surface mouse habitable;",
            "[VHGstepv] = 1000; -> VHG surface mouse apply;",
            "A = [VHGNDsctype]; ? A = 4 -> VHG surface mouse ice;",
            "[VHGstepv] = 400; -> VHG surface mouse apply;",
            "[VHGstepv] = 1200;", "A = [VHGsurfstep]; A + [VHGstepv];",
            "A = [VHGsurfshift]; A - [VHGstepv]; [VHGsurfshift] = A;",
        ))
        and all(token in game for token in (
            "A = [KEY DELETE]; ? A = OFF -> VHG raw snapshot delete released;",
            "[VHGdeleteheld] = 1; A = [VHGmode]; ? A != 0 -> VHG raw snapshot key pressed;",
            '"VHG raw snapshot delete released"', "[VHGdeleteheld] = 0;",
        )),
        "surface left-click walking restores source terrain pace and Delete raw snapshots",
    )
    surface_motion = section(game, '"VHG surface motion"', '"VHG quit"')
    surface_level = section(game, '"VHG surface level pitch"', '"VHG quit"')
    surface_clamp = section(game, '"VHG surface clamp"', '"VHG fps init"')
    held_steps, held_velocity = surface_forward_trace(600, 20)
    check(
        all(token in original1 for token in (
            "alfa = 0; beta = directional_beta - 90;", "p_Forward (shift);",
            "alfa = 0; beta = directional_beta;", "p_Forward (step);",
            "shift /= 1.5;", "step /= 1.25;",
            "drop_x *= hpoint (refx, refz) - hpoint (pos_x, pos_z);",
            "shift *= 1 - drop_x;", "step *= 1 - drop_x;",
            "drop_x = pos_x - 1.6384E6;", "maxdfc = 1.5000E6;",
            "maxdfc = 0.7500E6;", "drop_y *= 0.000001;",
        ))
        and all(token in surface_motion for token in (
            "[VHGsurfbeta] = [VHGbeta];", "[VHGstepv] = [VHGsurfshift]; => VHG strafe;",
            "[VHGstepv] = [VHGsurfstep]; => VHG forward;",
            "A = [VHGsurfjet]; ? A = 0 -> VHG surface heading ready;",
            "A = [VHGsurfshift]; A '* 2; A / 3;",
            "A = [VHGsurfstep]; A '* 4; A / 5;",
            "[VHGsurfoldground]", "[VHGsurfnewground]", "A - 24000;",
            "A = [VHGsurfjumping]; ? A != 0 -> VHG surface slope done;",
            "A '* C; A / 10000; [VHGsurfshift] = A;",
            "A '* C; A / 10000; [VHGsurfstep] = A;",
        ))
        and all(token in surface_clamp for token in (
            "A - 1638400; [VHGdx] = A;", "[VHGsurfradius] = 1500000;",
            "C = 1000000; C - A;",
            "=> FQuo;", "A + 1638400; [VHGx] = A;",
            "A + 1638400; [VHGz] = A;",
        ))
        and "[VHGsurfradius] = 750000;" not in surface_clamp
        and held_steps[:4] == [600, 1080, 1464, 1771]
        and 2350 <= held_velocity <= 2400,
        "surface traversal restores retained momentum, friction, slope resistance, and radial bounds",
    )
    level_positive = surface_level_trace(40, 600, 182)
    level_negative = surface_level_trace(-40, 600, 182)
    check(
        "user_alfa /= 1 + fabs(step) * 0.000064;" in original1
        and all(token in surface_level for token in (
            "A = [VHGsurfground]; A - 1200;",
            "C = 125000; C + [VHGstepv]; A '/ C;",
            "A = [VHGsurflevelacc]; A '% C;",
            "C - A; ? C >= 0 -> VHG surface level store;",
            "C + A; ? C <= 0 -> VHG surface level store;",
        ))
        and "=> VHG surface level pitch;" in surface_motion
        and level_positive[0] == 40
        and [level_positive[index] for index in (54, 109, 181)] == [31, 24, 17]
        and all(value >= following for value, following in zip(level_positive, level_positive[1:]))
        and level_negative == [-value for value in level_positive],
        "surface walking gradually levels positive and negative pitch at the source rate",
    )

    brightness = section(game, '"VHG HUD brightness key"', '"VHG surface input"')
    check(
        "if (c=='+' && surlight < 63 && !moviestat) surlight++;" in original
        and "if (c=='-' && surlight > 10 && !moviestat) surlight--;" in original
        and "A = [VHGascii]; ? A = 43 -> VHG HUD brightness raise;" in brightness
        and "? A != 45 -> VHG HUD brightness done;" in brightness
        and "? A <= 10 -> VHG HUD brightness done;" in brightness
        and "? A >= 63 -> VHG HUD brightness done;" in brightness
        and "[VHGNDsurlight]-;" in brightness
        and "[VHGNDsurlight]+;" in brightness
        and game.index("A = [VHGconsole]; ? A != 0 -> VHG console input;")
        < game.index("=> VHG HUD brightness key;")
        < game.index("A = [VHGmode]; ? A != 0 -> VHG surface input;"),
        "plus and minus restore source-clamped HUD brightness without stealing console input",
    )

    check(
        "INITIAL WIDTH = 642; INITIAL HEIGHT = 426;" in game
        and "defstyle;" in game
        and "[Work Area Manager] = service VHG repaint;" in game
        and '"VHGUI resize"' in gui
        and "=> VHGUI resize;" not in section(game, '"service VHG repaint"', '"service VHG GUI loop"')
        and "=> VHGUI prepare;" not in section(game, '"service VHG repaint"', '"service VHG GUI loop"')
        and "=> VHGUI present;" not in section(game, '"service VHG repaint"', '"service VHG GUI loop"'),
        "iGUI chrome opens with an exact 2x 640x400 initial work area",
    )
    check(
        "[Previous display height] = [Display Height]; [Fold Is Active] = NO;" in game
        and game.index("[Fold Is Active] = NO;") < game.index("=> Enter Integrated GUI;"),
        "the first client frame starts unfolded and later fold/unfold restores the live height",
    )
    run = section(game, '"VHG run"', '"service VHG repaint"')
    capsule_collapse = section(game, '"VHG capsule checkpoint collapse"', '"service VHG menu controls"')
    close_action = section(igui, '"service Exit Button Action"', '"Update Slep Button Appearence"')
    check(
        run.index("=> Enter Integrated GUI;") < run.index("=> VHSV save;") < run.index("=> VHA stop;")
        and "[Quit Now] = YES;" in close_action
        and '"service KD Quit hook"' in igui
        and "? [KEY ALTERNATE] = OFF" in igui
        and "A = [KEY F4]; ? A = OFF -> VHG GUI loop frame;" in game
        and "A = [KEY ALTERNATE]; ? A = OFF -> VHG GUI loop frame;" in game
        and "[Client Exit Action] = service VHG GUI exit;" in run
        and "[VHGesc] = 1; => VHG capsule checkpoint collapse;" in game
        and all(token in capsule_collapse for token in (
            "A = [VHGCstate]; A | [VHGcapsulestartpending]; A | [VHGcapsulereturnpending];",
            "? A = 0 -> VHG capsule checkpoint collapse done;",
            "[VHGCstate] = 0; [VHGCcapcount] = 0; [VHGCrecover] = 0;",
            "[VHGcapsulestartpending] = 0;",
            "[VHGcapsulereturnpending] = 0;",
            "[VHGmode] = 1; [VHGlanded] = 1;",
            "[VHGx] = [VHGNDdropx]; [VHGz] = [VHGNDdropz];",
        )),
        "red close button and Alt+F4 return through checkpoint/audio cleanup",
    )
    gui_loop = section(game, '"service VHG GUI loop"', '"service VHG GUI sleepy"')
    check(
        "[L2L Region] = vector Work Area; => Update Area;" in gui_loop
        and "[Display Command] = RETRACE; [Display Live Region] = WHOLE DISPLAY; isocall;" not in gui_loop
        and "[Do Not Retrace Arrow Region] = YES;" not in gui_loop
        and "=> VHG copy page;" in game,
        "GUI publishes the complete 3-D backdrop through iGUI's focus-safe update path",
    )
    check(
        "A = [Display Status]; ? A - ACTIVE -> VHG GUI loop done;" in gui_loop,
        "inactive windows retain the last completed client frame until focus returns",
    )
    check(
        "A = 0; A - 500; [VHGz] = A; [VHGbeta] = 180;" in game
        and "[VHGalpha] = 0; [VHGbeta] = 180; [VHGmode] = 0;" in game,
        "clean start and capsule return face into the visible Stardrifter interior",
    )
    check(
        all(token in game for token in (
            '"VHG help key"', "A = [VHGascii]; ? A = 63 -> VHG help key pressed;",
            "A = [KEY F9]; ? A = OFF -> VHG help key released;", '"VHG help overlay"',
            "[Rectangle Bounds] = vector VHGUIregion;", "[Rectangle Target Layer] = VHGUIframe;",
            "VHGhelpmenu = { F10:MENU / F1:ORIGINAL-ABOUT };",
            "[Text Display Origin] = VHGUIframe;", "[VHGhelpline] = VHGhelpfuel;",
            "[VHGhelpline] = VHGhelpview;", "=> VHG help draw line;",
            "[Rectangle Gradients] = vector Standard Black Gradients;", "[Ink] = FFFFFFh;",
            "[Text Effect] = service FX Raw;",
        )),
        "question-mark/F9 retain the repaint-safe current-port control card",
    )
    check(
        all(token in original for token in (
            "if (c==0x3B) { // F1 - help & about", "void ShowAboutPage(char surface)",
            "areaclear(adapted, 5, 5, 315, 195, 0, 0, 0);",
            "areaclear(adapted, 11, 10, 310, 32, 0, 0, 80);",
            'wrouthud (14, 37, NULL, "SHORTCUT KEYS (WHEN IN SPACE):");',
            'wrouthud (14,180, NULL, "RELEASE 2.3");',
        ))
        and all(token in game for token in (
            '"VHG about key"', "A = [KEY F1]; ? A = OFF -> VHG about key released;",
            'vector VHGaboutwhole = 5; 5; 315; 195;',
            'vector VHGaboutheader = 11; 10; 310; 32;',
            'vector VHGaboutbody = 11; 45; 310; 168;',
            'VHGaboutspacehead = { SHORTCUT_KEYS_(WHEN_IN_SPACE): };',
            'VHGaboutsurfacehead = { SHORTCUT_KEYS_(WHEN_ON_THE_SURFACE): };',
            'VHGaboutrelease = { RELEASE_2.3 };', '"VHG about overlay"',
            "=> VHGND HUD row mask;", "[VHGaboutsrc] = VHGaboutsurface6;",
        ))
        and all(token in ground for token in (
            "? A = 66 -> VHGND HUD glyph letter B;",
            "? A = 87 -> VHGND HUD glyph letter W;",
            "[VHGNDhudpacked] = 31471;", "[VHGNDhudpacked] = 24557;",
        )),
        "F1 restores the source-framed ship/surface About page with complete 3x5 text",
    )
    info_overlay = section(game, '"VHG source info overlay"', '"VHG onboard row begin"')
    info_slide = section(game, '"VHG info slide advance"', '"VHG source info overlay"')
    info_source_values = section(game, '"VHG info append fixed"', '"VHG info format common"')
    info_format = section(game, '"VHG info format common"', '"VHG graphics overlay"')
    info_key = section(game, '"VHG info key"', '"VHG help key"')
    check(
        all(token in original for token in (
            'command (2, "remote target data");',
            'command (3, "local target data");',
            'command (4, "environment data");',
            'case 1: // remote target data',
            'case 2: // local target data',
            'case 3: // environment data',
            'areaclear (adapted, 11, 85, 0, 0, 1 + datasheetscroll, 9, 72);',
            'areaclear (adapted, 11, 95, 0, 0, 1 + datasheetscroll, 40, 112);',
            'c = (datasheetscroll / 4) - 1;',
            'datasheetscroll +=',
            'tmp_float = 1e-3 * qt_M_PI * ap_target_ray * ap_target_ray * ap_target_ray;',
            'tmp_float /= 0.38e-4 * ap_target_ray;',
            'wrouthud (14, 97, c, "PERIOD OF ROTATION:");',
            'tmp_float = rtp (ip_targetted);',
            'tmp_float = 16 - dsd * 0.044;',
            'sprintf (outhudbuffer, "LI+ IONS: %ld MTPD EST.", ir);',
            'sprintf (outhudbuffer, "RADIATION: %1.1f KR", tmp_float);',
        ))
        and all(token in game for token in (
            'VHGinfotitle1 = { REMOTE TARGET DATA };',
            'VHGinfotitle2 = { LOCAL TARGET DATA };',
            'VHGinfotitle3 = { EXTERNAL ENVIRONMENT };',
            'VHGinfonoremote = { REMOTE TARGET NOT SET };',
            'VHGinfodirect = { DIRECT PARSIS TARGET };',
            'VHGinfonolocal = { LOCAL TARGET NOT SET };',
            'VHGinfomajort = { MAJOR BODIES: 00 EST. };',
            'VHGhelpview = { F4:FPS F5:60HZ F8:MUSIC I:DATA };',
            '=> VHG info slide advance;',
            '=> VHG source info overlay;',
        ))
        and all(token in info_slide for token in (
            'A = [VHGinfoscroll]; A + [VHGinfodelta];',
            'A = 100; [VHGinfodelta] = 0;',
            'A = 0; [VHGinfo] = 0; [VHGinfodelta] = 0;',
            '=> VHGND HUD draw string;',
        ))
        and all(token in info_overlay for token in (
            '"VHG source info remote"', '"VHG source info local"',
            '"VHG source info environment"',
            '[VHGinfodrawx] = 11; [VHGinfodrawy] = 85;',
            '[VHGinfofillbottom] = 94;',
            '[VHGinfodrawy] = 95; [VHGinfofillbottom] = 135;',
            '[VHGinfofillcolour] = 72;',
            '[VHGinfofillcolour] = 112;',
            'A = [VHGinfoscroll]; A \'/ 4; A - 1;',
            '[VHGinfonamesrc] = vhcatstarlabel;',
            '[VHGinfonamesrc] = vhcatbodylabel;',
            'A = [MgAptgt]; ? A = 0 -> VHG source info no remote;',
            'A = [VHGlocaltarget]; ? A = 0FFFFFFFFh -> VHG source info no local;',
            '[VHGinfodrawsrc] = VHGinfomajor; [VHGinfodrawy] = 129;',
            '[VHGinfodrawsrc] = VHGinforemotevalues; [VHGinfodrawy] = 103;',
            '[VHGinfodrawsrc] = VHGinforotationvalues; [VHGinfodrawy] = 103;',
            '[VHGinfodrawsrc] = VHGinforevolutionvalues; [VHGinfodrawy] = 116;',
            '[VHGinfodrawsrc] = VHGinfoenvtempk; [VHGinfodrawy] = 97;',
            '[VHGinfodrawsrc] = VHGinfoenvions; [VHGinfodrawy] = 119;',
            '[VHGinfodrawsrc] = VHGinfoenvradiation; [VHGinfodrawy] = 126;',
        ))
        and all(token in info_source_values for token in (
            '"VHG info format remote source"', 'VHGstarmasscorr',
            '[FB0] = D2F1A9FCh; [FB1] = 3F50624Dh; => FMul;',
            '[FB0] = 54442D18h; [FB1] = 400921FBh; => FMul;',
            '[FA0] = 0ED80A18h; [FA1] = 3F03EC46h;',
            '"VHG info format local source"', '=> VHGND rotation seed;',
            'C = 50; => SU rfr;', 'C = 25; => SU rfr;', 'C = 250; => SU rfr;',
            '[FB0] = E826D695h; [FB1] = 3E112E0Bh; => FMul;',
            '[FB0] = 7CFA26A2h; [FB1] = 3F071194h; => FMul;',
            '"VHG info format environment source"',
            '=> VHG info environment geometry;',
            '"VHG info environment geometry"',
            'A = [VHGinfogeometryvalid]; ? A = 0 -> VHG info environment geometry refresh;',
            'A = [VHGdosim]; ? A = 0 -> VHG info environment geometry done;',
            '[VHGNDvecindex] = A; => VHGND absolute body vector;',
            '[VHGinfoshipx0] = [FA0]; [VHGinfoshipx1] = [FA1];',
            '[VHGinfoeclipse0] = 0; [VHGinfoeclipse1] = 0;',
            '[FI] = 200; => IntToF;',
            '[VHGinforap0] = [FA0]; [VHGinforap1] = [FA1];',
            '[FB0] = [VHGinfoeclipse0]; [FB1] = [VHGinfoeclipse1]; => FMul;',
            '[FB0] = 020C49BAh; [FB1] = 3FA6872Bh; => FMul;',
            '[VHGinfoions] = 0; A = [VHTclass];',
            'A = 10; => BrtlRandom; C = A; A = 10; => BrtlRandom;',
            'A = [VHGutcsecs]; => BrtlSrand; A = 100; => BrtlRandom;',
        ))
        and all(token in info_format for token in (
            '"VHG info format local"', '"VHG info name copy"',
            'E = nspowner;', 'E = nspmoonid;', 'E = nspray;',
            '"VHG info row copy"',
            '[VHGinfosrc] = VHGinfoclasst;',
            '[VHGinfodst] = VHGinfoclass;',
            'E = [VHGinfonamesrc]; E + 1;',
            '[VHGinfoname plus 20] = 0;',
            '[VHGinfoclass plus 22] = 0;',
            '[VHGinfoenergy plus 32] = 0;',
            '[VHGinforadius plus 25] = 0;',
        ))
        and all(token in info_key for token in (
            'E = KEY A; E + 8; A = [E]; ? A = ON -> VHG info physical key;',
            '[VHGinfoheld] = 0;',
            'A = [VHGascii]; ? A = 73 -> VHG info key pressed;',
            '? A != 105 -> VHG info key done;',
            '[VHGinfoheld] = 1;',
            '[VHGinfogeometryvalid] = 0;',
            '[VHGinfoscroll] = 0; [VHGinfo] = 1; [VHGinfodelta] = 4;',
            '? A >= 3 -> VHG info key close; [VHGinfo]+; [VHGinfodelta] = 0;',
            '[VHGinfodelta] = 0FFFFFFFCh;',
        ))
        and game.count("=> VHG info overlay;") == 1
        and game.count("=> VHG source info overlay;") == 1
        and '[Rectangle Bounds] = vector VHGUIregion;' not in section(
            game, '"VHG info overlay"', '"VHG help overlay"'
        )
        and "A = [VHGinfo]; ? A != 0 -> VHG input done;" in game,
        "I slides indexed data sheets with live source remote, local, and environment fields without moving the player",
    )
    device_overlay = section(game, '"VHG device overlay"', '"VHG info format common"')
    device_key = section(game, '"VHG device key"', '"VHG info key"')
    light = section(game, '"VHG light step"', '"VHG rescue advance"')
    check(
        all(token in original for token in (
            'command (1, "internal light on");',
            'command (1, "internal light off");',
            'case 1: ilightv = -ilightv;',
            "case 'r': sys = 2; dev_page = 0; break;",
            "case '6': s_command = 1; commands (); break;",
            "case '9': s_command = 4; commands (); break;",
        ))
        and all(token in device_overlay for token in (
            '[VHGinfoline] = VHGdevroot;', 'VHGdevnav', 'VHGdevmisc',
            'VHGdevcart', 'VHGdevemergency', '[VHGinfoline] = VHGnavtitle;',
            'VHGnavampon', 'VHGnavfinderon', 'VHGnavtrackorbit', 'VHGnavradon',
            '[VHGinfoline] = VHGcarttitle;', 'VHGcartstar', 'VHGcartplanet',
            'VHGcartnext', 'VHGcartmanual',
            '[VHGinfoline] = VHGemergencytitle;', 'VHGemergencyreset',
            'VHGemergencyhelp', 'VHGemergencylithiumon', 'VHGemergencyclear',
            '"VHG device target browser overlay"', '=> VHG browse format rows;',
            'VHGbrowserowx', 'VHGbrowseprev', 'VHGbrowseselect',
            '[VHGinfoline] = VHGdevtitle;',
            'VHGdevlighton', 'VHGdevlightoff', 'VHGdevremote',
            'VHGdevlocal', 'VHGdevenvironment', 'VHGdevhint',
        ))
        and 'Standard Black Gradients' not in device_overlay
        and all(token in device_key for token in (
            '=> VHG device physical poll;', '"VHG device physical poll"',
            'E = KEY A; E + 17;', 'E = KEY A; E + 32;',
            'E = KEY A; E + 35;', '[VHGdeviceheld] = 1;',
            '? A = 82 -> VHG device toggle;', '? A = 114 -> VHG device toggle;',
            '? A = 54 -> VHG device open navigation;',
            '? A = 55 -> VHG device open miscellaneous;',
            '"VHG device amplifier"', '"VHG device finder"',
            '"VHG device tracking"', '"VHG device radiation"',
            '"VHG device cartography key"', '"VHG device emergency key"',
            '=> VHG console prefill;', '=> VHG browse open;',
            '"VHG device browser key"', '=> VHG browse seek;',
            '[VHTtx] = [VHGbrowsex];', '=> VHG activate target;',
            '=> VHG help action;', '=> VHG collector action;',
            '=> VHG systems reset action;',
            '? A = 54 -> VHG device light;', '? A = 55 -> VHG device remote;',
            '? A = 56 -> VHG device local;', '[VHGinfo] = 3;',
            '[VHGilight] = A; [VHLpower] = A;',
        ))
        and all(token in light for token in (
            'A = [VHGilightlevel]; A + [VHGilight];',
            '[VHGilightlevel] = A;',
            'A = [VHGilight]; ? A != 1 -> VHG light step done;',
            '[VHGlighttick]+;', '? A < 1529 -> VHG light step done;', '[MgPwr]-;',
            '"VHG navigation step"', '? A < 746 -> VHG navigation amplifier off;',
            '? A < 2822 -> VHG navigation finder off;', '=> VHG tracking apply;',
        ))
        and 'VHGdevtitle = { MISCELLANEOUS DEVICES };' in game
        and all(token in VIEW.parent.joinpath("vhlight.txt").read_text(encoding="utf-8") for token in (
            'A = [VHVcamzi]; [VHLdistance] = A;',
            'A <= 1500 -> VHL distance ready;',
            "A '* 36; A / 1500; [VHLstep] = A;",
            'A = 72; A + [VHLpower]; [VHLcol] = A;',
            '? A <= 100 -> VHL segment; [VHLcol] = 100;',
            'A = [VHLangle]; ? A < [VHLlimit] -> VHL segment;',
        ))
        and '[SPreg] = RGADP; => SP get;' not in section(
            flare, '"VH halogen flare"', '"VH rescue flare"'
        )
        and "-50000, 2, hud_closed, 0, 1, 1" in section(
            original, "void alogena ()", "/* Quadranti"
        )
        and all(token in game for token in (
            '[VHGstarclass] = [VHTclass];', '? A = 8 -> VHG star palette inner8;',
            '"VHG star palette update"', '[VHGstartargetR] = 48;',
            '[VHGstartargetinnerR] = 24;', '[VHGstarpaletteok] = 0;',
            '[VHGstarcurrentR]+;', '[VHGstarcurrentinnerB]-;',
            'A = [VHGdosim]; ? A = 0 -> VHG star palette frame done;',
            '[FBSHfirst] = 64; [FBSHn] = 24;', '[FBSHfirst] = 88; [FBSHn] = 16;',
            '[FBSHfirst] = 104; [FBSHn] = 24;',
            '[PVself] = 1; [PVfirst] = 64; [PVn] = 64;',
        ))
        and all(token in original for token in (
            "l_dsd = sqrt (dxx*dxx + dyy*dyy + dzz*dzz) + 1;",
            "satur = (12 * dsd) / nearstar_ray;", "ir = fast_random(31) + 29;",
            "satur = (6.4 * dsd) / nearstar_ray;",
            "if (ire < ir) ire++; if (ire > ir) ire--;",
            "if (l_dsd > 6 * nearstar_ray)",
            "nearstar_class!=5&&nearstar_class!=6&&nearstar_class!=10",
            "l_dsd>5*nearstar_ray&&l_dsd<1000*nearstar_ray",
            "psmooth_grays (adapted+2880);",
        ))
        and all(token in game for token in (
            '[VHGlocalmask] = 128;', '[VHGlocalbubble] = 1;',
            '=> VHG prepare planet; => VHG fpu clean; => VHGND globe surface;',
            '[GBtapreg] = [VHGlocaltapreg];', '[GBcmask] = [VHGlocalmask];',
            '[GBbubble] = [VHGlocalbubble];',
            '=> VHG local resident scan;', '=> VHG local ensure surface;',
            '[VHGlocalpmapbody] = [VHGlocalringbody];',
            '[VHGlocalmmapbody] = [VHGlocalringbody];',
            '[VHGNDtexbase] = RPBG;', '[VHGNDtexbase] = RSBG;',
            'A = [VHGlocalringstart]; A + [VHGNDrotation]; A % 360;',
            'A = 124; A - [VHGlocalbodyview]; A % 360;',
            '[VHGNDvecindex] = [VHGplanet]; => VHGND absolute body vector;',
            '[FB0] = [VHGlocalty0]; [FB1] = [VHGlocalty1]; => FSub;',
            '[FA0] = [MgDzatX0]; [FA1] = [MgDzatX1]; [FI] = [VHTtx]; => IntToF;',
            '[FB0] = [VHGlocaltz0]; [FB1] = [VHGlocaltz1]; => FSub;',
            '[FB0] = [MgK1000]; [FB1] = [MgK1001]; => FMul;',
            'A = [VHGlocalactive]; ? A != 0 -> VHG close star rendered;',
            "A = [VHGlocalbody]; ? A '>= [nsnob] -> VHG local selected render;",
            '=> VHG local far pixel;', '[FI] = 250; => IntToF;',
            'E = nspring;', '=> VHG local ring viewpoint;',
            '=> VHG local ring;', '[GLarc] = 130; [GLcol] = 127;',
        ))
        and all(token in game for token in (
            '"VHG ship palette update"', '=> VHG info environment geometry;',
            '[PVsrc] = range8088;', '[PVfirst] = 0; [PVn] = 64;',
            '[PVfr] = [VHGshipr]; [PVfg] = [VHGshipg]; [PVfb] = [VHGshipb];',
            '[VHGelight]', '[VHGgburst]', '[TKtmp]', '[VHGshped]',
            '"VHG reset step"', '[VHGresetcount] = 150;',
            '"VHG emergency step"', '[VHGelight] = 1;',
            '[VHPblackout] = [VHGelight];', '[VHLemergency] = [VHGelight];',
        ))
        and all(token in original for token in (
            'stz = dzz * cos (deg * navigation_beta)', 'ilight += ilightv;',
            'ir3 = ilight / 4 + l_dsd;', 'ig3 = ilight / 2 + l_dsd;',
            'ib3 = ilight + l_dsd;',
            'tavola_colori (range8088, 0, 64, ir3, ig3, ib3);',
        ))
        and '[vhsvbuf plus 38] = [VHGilight];' in save
        and all(token in save for token in (
            '[VHGgburst]; A + 1; A \'* 32768;',
            '[VHGresetcount]; A \'* 128;', '[VHGelight]; A \'* 64;',
            'C + 4194304; [vhsvbuf plus 66] = C;', 'A & 63; [VHGilightlevel] = A;',
            'A & 1; [VHGelight] = A;', '[VHGresetcount] = A;', '[VHGgburst] = A;',
        )),
        "R and 6-9 restore onboard navigation/miscellaneous devices with live powered effects",
    )
    fcs_menu_overlay = section(game, '"VHG FCS menu overlay"', '"VHG browse format rows"')
    fcs_menu_key = section(game, '"VHG FCS menu key"', '"VHG device key"')
    check(
        "case '5': sys = 1; dev_page = 0; break;" in original
        and "case '6': s_command = 1; commands (); break;" in original
        and "case '9': s_command = 4; commands (); break;" in original
        and all(token in fcs_menu_overlay for token in (
            '[VHGinfoline] = VHGfcsmenutitle;', 'VHGfcsmremote',
            'VHGfcsmstart', 'VHGfcsmstop', 'VHGfcsmlocal',
            'VHGfcsmcancel', 'VHGfcsmrestart', 'VHGfcsmcapsule',
        ))
        and 'Standard Black Gradients' not in fcs_menu_overlay
        and all(token in fcs_menu_key for token in (
            '? A = 53 -> VHG FCS menu toggle;',
            '? A = 54 -> VHG FCS remote action;',
            '? A = 55 -> VHG FCS flight action;',
            '? A = 56 -> VHG FCS local action;',
            '? A = 57 -> VHG FCS capsule action;',
            '[MgStspeed] = 0;', '[MgStspeed] = 1;',
            '=> VHG browse open;', '=> VHG local start;', '=> VHG local reset;',
            '[VHGfcsopen] = 0; [VHGascii] = 76;',
        ))
        and '? A = 53 -> VHG select body 5;' not in game
        and 'VHGhelpnav = { 5:FCS / R:DEVICES / G:GOES };' in game,
        "5 and 6-9 restore the original interactive flight-control computer",
    )
    check(
        all(token in game for token in (
            '"VHG fps init"', '"VHG fps tick"', '"VHG fps overlay"',
            '"VHG fps key"', "[KEY F4]", "=> TK read wall; [VHGfpsnow] = [TKtmp];",
            "C = 1000; C '* [VHGfpsframes];", "=> STD Write;",
        )),
        "F4-toggled FPS counter is driven by the normalized millisecond clock",
    )
    body_overlay = section(game, '"VHG body overlay"', '"VHG landing overlay"')
    check(
        "[VHGbodytext plus 21] = 0;" in body_overlay
        and 'VHGbodytext = { P00 T00 LAND UNCLASSX };' in game
        and '"VHG body kind copy"' in body_overlay
        and "? A '>= 10 -> VHG body no land;" in body_overlay
        and "E = nspowner;" in body_overlay
        and "[VHGbodykind] = VHGkind10;" in body_overlay
        and body_overlay.count("=> VHG text both;") == 0
        and '"VHG text both"' in game,
        "body data identifies planets/moons without placing a permanent host-font row over play",
    )
    pod_overlay = section(game, '"VHG pod overlay"', '"VHG FCS overlay"')
    bearings = [
        ((0, 10), 0), ((-10, 10), 45), ((-10, 0), 90), ((-10, -10), 135),
        ((0, -10), 180), ((10, -10), 225), ((10, 0), 270), ((10, 10), 315),
    ]
    check(
        all(pod_hint(dx, dz, bearing) == "F" for (dx, dz), bearing in bearings)
        and pod_hint(-10000, 0, 0) == "L"
        and pod_hint(10000, 0, 0) == "R"
        and pod_hint(0, -10000, 0) == "B"
        and 'VHGpodtext = { POD 000000 F BIRDS 0 CTRL:STALK R@POD };' in game
        and all(token in pod_overlay for token in (
            '"VHG pod direction"', "[VHGpodtext plus 11] = 70;",
            "[VHGpodtext plus 11] = 76;", "[VHGpodtext plus 11] = 66;",
            "[VHGpodtext plus 11] = 82;", "[VHGpodtext plus 37] = 0;",
        ))
        and pod_overlay.count("=> VHG text both;") == 0,
        "capsule guidance remains correct without a permanent host-font surface row",
    )
    surface_telemetry = section(game, '"VHG surface telemetry init"', '"VHG FCS overlay"')
    surface_overlay = section(game, '"VHG surface telemetry overlay"', '"VHG FCS overlay"')
    check(
        all(token in original0 for token in (
            'sprintf (outhudbuffer, "GRAVITY %2.3f FG & TEMPERATURE %+3.1f@C & PRESSURE %2.3f ATM & PULSE %3.0f PPS"',
            "pp_delta = (pp_temp - tp_temp) * 0.05;",
            "pp_delta = (pp_pressure - tp_pressure) * 0.02;",
            "pp_delta = (pp_pulse - tp_pulse) * 0.01;",
        ))
        and "pp_gravity = gravity * 38.26;" in original1
        and 'VHGsurfacetext = { G 0.000FG T +000.0C P 00.000ATM HR 000 };' in game
        and all(token in surface_telemetry for token in (
            "E = nspray;", "[FI] = 38260;", "[GRSKbasetemp]",
            "[GRSKbasepressure]", "A = [VHGy]; A / 4000;",
            "[VHGsurftiredq]", "A '* 118; A / 10000; A + 118;",
            "A = [VHGutcsecs]; A '/ 2; => SU fast srand;",
            "[SUfmask] = 32767; => SU fast raw;",
            "A '* 8; A '/ 32768;", "[VHGsurfpulsejitter]",
            '"VHG surface telemetry update"', '"VHG surface smooth field"',
            "D = VHGsurfgravdisp; C = 4;", "D = VHGsurftempdisp; C = 20;",
            "D = VHGsurfpressdisp; C = 50;", "D = VHGsurfpulsedisp; C = 100;",
        ))
        and "=> VHG text both;" not in surface_overlay
        and "=> VHG UTC timestamp; => VHG visor advance; => VHG surface telemetry update;" in game
        and game.count("=> VHG surface telemetry overlay;") == 1
        and game.count("=> VHG surface telemetry init;") == 2,
        "surface HUD restores live gravity, temperature, pressure, and pulse telemetry",
    )
    check(
        compass_window(0)[1].startswith("N.........E")
        and compass_window(90)[1].startswith("W.........N")
        and compass_window(180)[1].startswith("S.........W")
        and compass_window(270)[1].startswith("E.........S")
        and all(197 <= compass_window(beta)[0] <= 200 for beta in range(360))
        and sqc_text(8, 54, 122880, 3145728) == "SQC 8.54:-93.92"
        and epoc_text(1_342_123_456) == "EPOC 6012 & 342.123.456"
        and "=> VHG UTC timestamp; => VHG visor advance;" in game
        and all(token in ground for token in (
            '"VHGND compass"', "A = [VHGbeta]; A % 360;",
            "A = [VHGNDcompassrem]; A '* 4; A / 9;",
            "[VHGNDcompassi]+; A = [VHGNDcompassi]; ? A < 28 -> VHGND compass character;",
            '"VHGND compass row north"', '"VHGND compass row east"',
            '"VHGND compass row south"', '"VHGND compass row west"',
            '"VHGND HUD lamps"', "[VHGNDlampsize] = 4;",
            "A = [VHGsurfjet]; ? A = 0 -> VHGND HUD lamp positions ready;",
            "[VHGNDlampsize] = 5; [VHGNDframecol] = 127;",
            '"VHGND surface coordinate HUD"', "A = [VHGlandinglon]; => VHGND HUD append number;",
            "A = [VHGx]; A / VHGNDTS; A - 100; => VHGND HUD append number;",
            '"VHGND HUD append number"', '"VHGND HUD row mask"',
            '"VHGND epoch HUD"', "A = [VHGutcsecs]; A / 1000000000; A + 6011;",
            "A = [VHGutcsecs]; A / 1000000; A % 1000; => VHGND HUD append triad;",
            '"VHGND HUD append triad"', "[VHGNDhudsource] = VHGNDepoctext;",
            "? A < 1000 -> VHGND HUD number hundreds;",
            "A / 1000; A + 48; => VHGND HUD append;",
            '"VHGND environment HUD"', "[VHGNDhudy] = 192;",
            "A = VHGNDenvgravity; => VHGND HUD append text;",
            "A = [VHGsurfgravdisp]; => VHGND HUD append fixed three;",
            "A = [VHGsurftempdisp]; => VHGND HUD append signed fixed one;",
            "A = [VHGsurfpressdisp]; => VHGND HUD append fixed three;",
            "A = [VHGsurfpulsedisp]; => VHGND HUD append width three;",
            'VHGNDenvgravity = { GRAVITY };', 'VHGNDenvtemp = {  FG & TEMPERATURE };',
            'VHGNDenvpress = { @C & PRESSURE };', 'VHGNDenvpulse = {  ATM & PULSE };',
            'VHGNDenvpps = {  PPS };',
            'VHGNDshiphints = {  & 5\\FLIGHTCTR R\\DEVICES F2\\PREFS X\\SCREEN OFF };',
            "A = [VHGmode]; ? A != 0 -> VHGND epoch HUD terminate;",
            "A = [VHGonroof]; ? A != 0 -> VHGND epoch HUD terminate;",
            "A = VHGNDshiphints; => VHGND HUD append text;",
            "? A = 92 -> VHGND HUD glyph backslash;", "[VHGNDhudpacked] = 6105;",
        ))
        and all(token in original0 for token in (
            "cpos = ccom / 9; crem = ccom * 0.44444;",
            "wrouthud (200 - (crem % 4), 2, 28, compass + cpos);",
            "areaclear (adapted, 9, 9, 0, 0, 4, 4, lptr);",
            "strcat (outhudbuffer, alphavalue(landing_pt_lon));",
            "strcat (outhudbuffer, alphavalue((((long)(pos_x)) >> 14) - 100));",
            'sprintf (outhudbuffer, "EPOC %d & ", epoc);',
            "epoc = 6011 + secs / 1e9;",
            r'5\\FLIGHTCTR R\\DEVICES    D\\PREFS      X\\SCREEN OFF',
        )),
        "visor restores source EPOC/SQC data, compass strip, and reactive corner lamps",
    )
    jump_ticks, jump_apex, jump_ground = surface_arc(118)
    jet_ticks, jet_apex, jet_ground = surface_arc(118, thrust_ticks=12)
    surface_motion = section(game, '"VHG surface input"', '"VHG quit"')
    check(
        all(token in original1 for token in (
            "gravity = nearstar_p_ray[ip_targetted];",
            "planet_grav = gravity * 2000;",
            "gravity -= gravity + 500;",
            "gravity = gravity - 50;",
            "if (pos_y > crcy)",
        ))
        and all(token in surface_motion for token in (
            '"VHG surface jump request"', '"VHG surface jet request"',
            '"VHG surface descend request"', '"VHG surface vertical"',
            "A = 0; A - 500; [VHGsurfvy] = A;",
            "E = KEY A; E + 64;", "A = [VHGsurfvy]; A - 50;",
            "A = [VHGsurfvy]; A + 400; [VHGsurfvy] = A;",
            "C - [VHGsurfground]; C '* [VHGsurfaccel]; C / 300;",
            "A = [VHGsurfvy]; A + [VHGsurfaccel];",
            "[VHGsurfbkstep] = [VHGsurfstep]; [VHGsurfbkshift] = [VHGsurfshift];",
            "[VHGsurfstep] = [VHGsurfbkstep]; [VHGsurfshift] = [VHGsurfbkshift];",
            "[VHGy] = [VHGsurfground]; [VHGsurfvy] = 0;",
        ))
        and "0FFFFFB50h" not in surface_motion
        and "A = [VHGsurfgravm]; A '* 2000; A '/ 38260;" in surface_telemetry
        and "VHGhelpjump = { SURFACE:CTRL:STALK / J:JUMP / SPACE:JET };" in game
        and "[VHGhelpline] = VHGhelpjump;" in game
        and jump_ticks > 1 and jump_apex < jump_ground
        and jet_ticks > jump_ticks and jet_apex < jump_apex and jet_ground == jump_ground,
        "surface jump and hold-to-thrust jetpack follow body gravity and land cleanly",
    )
    check(
        all(token in game for token in (
            '"VHG fast key"', "[KEY F5]", '"VHG cadence"',
            "VHGSIMADD = 18206", '"VHG timing step"', "=> TK read wall;",
            "A '* VHGSIMADD; A + [VHGsimacc];", "? A '< 1000000 -> VHG cadence done;",
            "[VHGsimwallprev] = [TKtmp]; [VHGdosim] = 1;",
        ))
        and "VHGfast = 0; VHGfastheld = 0; VHGsimacc = 0;" in game
        and game.count("[VHGsimacc] = 1000000;") == 0
        and "A = [VHGfast]; ? A != 0 -> VHG timing fast;" in game
        and "=> TK step;" in section(game, '"VHG timing step"', '"VHG timing rebase"')
        and "[TKdeadline] = [TKnow]; [TKacc] = 0;" in game
        and "[VHGNDdosim] = [VHGdosim];" in game
        and "[VHGNDinterpacc] = [VHGinterpacc];" in game
        and ground.count("A = [VHGNDdosim]; ? A = 0") >= 3,
        "original presentation is default and F5 opts into 60 FPS without changing simulation cadence",
    )
    one_frame = section(game, '"VHG one frame"', '"VHG flight init"')
    check(
        all(token in game for token in (
            '"VHG interpolation advance"', '"VHG interpolation apply"',
            '"VHG interpolation restore"', '"VHG interpolation snapshot"',
            '=> VHG interpolation apply; => VHG render; => VHGND surrounding frame;',
            '=> VHG source info overlay; => VHG interpolation restore;',
            'A = [VHGmode]; ? A = 0 -> VHG interpolation apply eligible;',
            'A = [VHGlanded]; ? A != 0 -> VHG interpolation apply eligible;',
            'A = [VHGCstate]; ? A = 0 -> VHG interpolation apply done;',
            'A = [VHGCstate]; ? A = 0 -> VHG interpolation advance done;',
            'A = [VHGCstate]; ? A = 0 -> VHG interpolation snapshot done;',
            'A = [VHGsimacc]; ? A >= 0 -> VHG interpolation phase positive;',
            "A '* VHGSIMDEN; A / 1000000;",
            '? A <= VHGSIMDEN -> VHG interpolation advance store; A = VHGSIMDEN;',
            "A = [VHGinterpdelta]; A '* [VHGinterpacc]; A / VHGSIMDEN;",
            'A = [VHGx]; A - [VHGinterprenderx]; [VHGinterpeffectx] = A;',
            'A = [VHGz]; A - [VHGinterprenderz]; [VHGinterpeffectz] = A;',
            'A = [VHGalpha]; A - [VHGinterprenderalpha]; [VHGinterpeffectalpha] = A;',
            '[VHGinterpok] = 0; => VHG load success notice;',
        ))
        and all(token in ground for token in (
            '"VHGND animal snapshot"', '"VHGND animal interpolate"',
            '"VHGND bird snapshot"', '"VHGND bird interpolate"',
            '"VHGND mammal half phase"', '"VHGND bird flap interpolate"',
            '"VHGND wave snapshot"', '"VHGND wave interpolate"',
            "A = [VHGNDanix]; A - [VHGNDaniprevx]; A '* [VHGNDinterpacc]; A / 60000;",
            "A = [VHGNDbirdquote]; A - [VHGNDaniprevquote]; A '* [VHGNDinterpacc]; A / 60000;",
            "A = [VHGNDtick]; A '% 18; A '* 60000; C = A;",
            "A = [VHGNDbirdflapcurr]; A - [VHGNDbirdflapprev]; A '* [VHGNDinterpacc]; A / 60000;",
            "A = [VHGNDwaveauthradius]; A - [VHGNDwaveprevr]; A '* [VHGNDinterpacc]; A / 60000;",
        ))
        and one_frame.count('=> VHG interpolation snapshot;') == 1
        and one_frame.index('"VHG landing commit done"')
        < one_frame.index('"VHG capsule return commit done"')
        < one_frame.index('=> VHG interpolation snapshot;')
        and "[VHGcapsulereturnpending] = 0; => VHG return ship; => VHG fpu clean;" in one_frame
        and one_frame.index('=> VHG interpolation snapshot;')
        < one_frame.index('=> VHG flight step;')
        < one_frame.index('=> VHG interpolation apply;')
        and one_frame.index('=> VHG interpolation snapshot;')
        < one_frame.index('=> VHGC tick;')
        and '[VHGinterpacc] = 0; [VHGinterpok] = 1;' not in section(
            game, '"VHG interpolation snapshot"', '"VHG interpolation reset"'
        )
        and '[VHGinterpok] = 0;' in section(capsule_physics, '"VHGC settle"', '"VHGC slope scan"')
        and [signed_lerp(0, 80, phase) for phase in (0, 18206, 36412, 54618, 60000)]
        == [0, 24, 48, 72, 80]
        and [signed_lerp(0, -80, phase) for phase in (0, 18206, 36412, 54618, 60000)]
        == [0, -24, -48, -72, -80],
        "60-Hz ship, lift, capsule, surface, and fauna poses interpolate without mutating simulation state",
    )
    check(
        (lambda run: (
            run.index("=> TK seed; => TK start;")
            < run.index("=> VHG load checkpoint;")
            < run.index("=> Enter Integrated GUI;")
        ))(section(game, '"VHG run"', '"service VHG repaint"'))
        and '"VHG startup state ready"' in game
        and "A = [VHSVok]; ? A = 0 -> VHG startup state ready;" in game
        and
        all(token in game for token in (
            '"VHG checkpoint keys"', "[KEY F6]", "[KEY F7]",
            '"VHG save checkpoint action"', '"VHG load checkpoint action"',
            "A = [VHGCstate]; ? A != 0 -> VHG save checkpoint busy;",
            "A = [VHGCstate]; ? A != 0 -> VHG load checkpoint busy;",
            '"VHG notice overlay"', "[VHGnoticeptr] = VHGsavedtext;",
            "=> VHG load checkpoint;", "=> VHG prepare planet; => VHGND generate;",
            "=> VHGND sky; => VHG fpu clean; => VHG surface telemetry init;",
            "=> VHG surface motion reset; -> VHG load checkpoint done;",
            '"VHG capsule checkpoint ready"',
            "A = [VHGmode]; ? A = 0 -> VHG capsule checkpoint ready;",
            "A = [VHGlanded]; ? A != 0 -> VHG capsule checkpoint ready;",
            "A = [VHGCstate]; ? A != 0 -> VHG capsule checkpoint ready;",
            "[VHGx] = [VHGNDdropx]; [VHGz] = [VHGNDdropz]; [VHGlanded] = 1;",
        ))
        and all(token in save for token in (
            "[VHSVok] = 0;", "[File Command] = SET SIZE; [File Size] = 268;",
            "[File Command] = TEST;", "? [File Size] != 268 -> VHSV save done;",
            "[VHSVok] = 1;",
        )),
        "startup resume and F6/F7 cover stable ship/surface checkpoints with fallback",
    )
    save_body = section(save, '"VHSV save"', '"VHSV load"')
    load_wrapper = section(save, '"VHSV load"', '"VHSV select load file"')
    load_one = save.split('"VHSV load one"', 1)[1]
    check(
        save_body.index("[File Name] = vhsvname; [File Command] = TEST; isocall;")
        < save_body.index("[VHSVok] = 1;")
        < save_body.index("[File Name] = vhsvbackup; [File Position] = 0; [File Command] = WRITE;")
        and all(token in load_wrapper for token in (
            "[VHSVusebackup] = 0; [VHSVrecovered] = 0;",
            "=> VHSV load one;", "[File Name] = vhsvname; [File Command] = TEST; isocall;",
            "? [File Status] + ERROR -> VHSV load wrapper done;",
            "[VHSVusebackup] = 1; => VHSV load one;", "[VHSVrecovered] = 1;",
        ))
        and load_one.index("[VHSVofflinestored] = 1;")
        < load_one.index('"VHSV load capsule done"')
        < load_one.index("=> VHG offline restore;")
        and all(token in game for token in (
            "VHGbackuptext = { CHECKPOINT RECOVERED FROM BACKUP };",
            '"VHG load success notice"', "A = [VHSVrecovered];",
            "[VHGnoticeptr] = VHGbackuptext; [VHGnoticeframes] = 300;",
        )),
        "checkpoint saves retain a last-known-good backup and visibly recover corrupt primaries",
    )
    check(
        all(token in game for token in (
            "MAX MENU OPTIONS = 12; MAX ONSCREEN OPTIONS = 12;",
            "VHGmenucaption = { GAME };", "VHGmenu = { NOCTIS_IV };",
            "{ Controls }; service VHG menu controls;",
            "{ GOES_console }; service VHG menu console;",
            "{ Save_checkpoint }; service VHG menu save;",
            "{ Load_checkpoint }; service VHG menu load;",
            "{ Toggle_FPS_counter }; service VHG menu fps;",
            "{ Toggle_60_Hz }; service VHG menu fast;",
            "{ Toggle_music }; service VHG menu music;",
            "{ Visual_effects }; service VHG menu graphics;",
            "{ Flight_control }; service VHG menu fcs;",
            "{ Onboard_devices }; service VHG menu devices;",
            "{ Preferences }; service VHG menu prefs;",
            "{ Save_and_quit }; service VHG menu quit;",
            "[Menu To Install] = VHGmenu; => Install Menu;",
            "=> VHG save checkpoint action;", "=> VHG load checkpoint action;",
            "=> VHG toggle fps action;", "=> VHG toggle fast action;",
            "=> VHG toggle music action;", "[VHGdevaccess] = 1;", "[Quit Now] = YES;",
        ))
        and (
            section(game, '"VHG run"', '"service VHG repaint"').index(
                "[Window Title] = VHGcaption; => Update Title Bar;"
            )
            < section(game, '"VHG run"', '"service VHG repaint"').index(
                "[Menu To Install] = VHGmenu; => Install Menu;"
            )
        )
        and "=> Update Title Bar;\n\t[Menu Caption] = VHGmenucaption; => Update Menu Button Appearence;" in game,
        "native iGUI menu exposes the existing gameplay, persistence, and presentation actions",
    )
    check(
        all(token in game for token in (
            '"VHG graphics overlay"', "[KEY F2]", '"VHG graphics character"',
            "? A = 70 -> VHG graphics flare key;", "? A = 84 -> VHG graphics hud key;",
            "? A = 66 -> VHG graphics border key;", "[VHGlensmode] = 1;",
            "A = 0; A - 1; [VHGlensmode] = A;", "[VHGdrawhud] = 0;",
            "[VHGseamless] = 1;", "A = [VHGdrawhud]; ? A = 0 -> VHG energy overlay done;",
            '"VHG visor keys"', "[KEY PGUP]", "[KEY PGDN]",
            "A = 0; A - 5; [VHGhuddelta] = A; [VHGhudclosed] = 0;",
            '"VHG visor advance"', "[VHGhudcount] = 180; [VHGhuddelta] = 0; [VHGhudclosed] = 1;",
        ))
        and all(token in game for token in (
            '"VHG visor flare mode"', "A = [VHGhudclosed]; ? A = 0 -> VHG visor flare done;",
            "[VHFghost] = 1;",
        ))
        and all(token in ground for token in (
            "A = [VHGseamless]; ? A != 0 -> VHGND surrounding seamless;",
            "C = 310; C + [VHGNDframei];", "C = 200; C - A; [VHGNDframecount] = C;",
            '"VHGND surrounding moving row"', "A = [VHGhudcount]; A + 9; A - [VHGNDframei];",
            "[VHGNDframei]+; A = [VHGNDframei]; ? A < 4 -> VHGND surrounding moving row;",
            "A = [VHGdrawhud]; ? A = 0 -> VHGND environment HUD done;",
        ))
        and all(token in flare for token in (
            '"VHF ghost reflections"', "A = [VHFang]; A % 8;",
            "A = [VHFgdx]; A '* 4;", "A = [VHFgx]; A '* 3;",
            "[VHFgr]+; A = [VHFgr]; ? A < 3 -> VHF ghost reflection;",
        ))
        and all(token in original0 for token in (
            "lens_flare_mode == 1", "if (on_hud_forced && !(c%8))",
            "dx *= 4; dy *= 4;", "xr *= 3; yr *= 3;",
        ))
        and all(token in original1 for token in (
            "if (lens_flare_mode == 0) lens_flare_mode = 1;",
            "else if (lens_flare_mode == 1) lens_flare_mode = -1;",
            "if (seamless_border == 0) seamless_border = 1;",
            "if (draw_hud == 0) draw_hud = 1;",
            "openhuddelta = -5;", "hud_closed = 0;", "openhuddelta = +5;",
        )),
        "F2 and Page Up/Down restore the original HUD, flare, border, and visor behavior",
    )
    check(
        all(
            "=> VHG text both;" not in section(game, start, end)
            for start, end in (
                ('"VHG energy overlay"', '"VHG pod overlay"'),
                ('"VHG pod overlay"', '"VHG FCS overlay"'),
                ('"VHG FCS overlay"', '"VHG body overlay"'),
                ('"VHG body overlay"', '"VHG landing overlay"'),
            )
        )
        and all(token in game for token in (
            '"VHG FCS source HUD draw"', "=> VH HUD FCS;",
            "A = [VHGdrawhud]; ? A != 0 -> VHG FCS source HUD draw;",
            "A = [VHGgraphics]; ? A = 0 -> VHG FCS source HUD done;",
            '"VHG screen off key"', "[KEY X]",
            "[VHGdev] = 0; [VHGfcsopen] = 0; [VHGprefs] = 0;",
        )),
        "ordinary play uses the indexed/source HUD and X clears onboard overlays",
    )
    check(
        all(token in game for token in (
            '"VHG next star"', '"VHG flight retarget"', '"VHG parse coordinate"',
            "A '% [VHScount]", "=> VHG target world; => VHG flight retarget;",
            "A = [VHGcmddigits]; ? A >= 10 -> VHG parse done;",
            "? A > 214748364 -> VHG parse done;",
            "E = [VHGcmdsign]; ? E = 0 -> VHG parse last digit ready; A = 8;",
            "[VHGcmdsilent] = 0; [VHGnoticeptr] = VHGunknowntext; [VHGnoticeframes] = 75; => VHG command;",
        ))
        and all(token in save for token in (
            "VHSVVERSION = 16;", "[vhsvbuf plus 24] = [VHTtx];",
            "[VHTtx] = [vhsvbuf plus 24];",
        )),
        "GOES NEXT/STAR retarget real Vimana travel and persist the selected star",
    )
    new_game = section(game, '"VHG new game"', '"VHG return ship"')
    check(
        all(token in game for token in (
            '"VHG command maybe new"', "? A = 87 -> VHG command maybe new;",
            "=> VHG new game; -> VHG command done;",
            "VHGhelpnav = { 5:FCS / R:DEVICES / G:GOES };",
        ))
        and all(token in new_game for token in (
            "[VHGmode] = 0; [VHGlanded] = 0;", "[VHGz] = A;",
            "[VHGalpha] = 0; [VHGbeta] = 180;",
            "[VHGplanet] = 0;", "[VHGNDcaptures] = 0;",
            "[VHTtx] = 3979984;", "=> VHG target world; => VHG flight init;",
            "=> VHSV save;", "[VHGnoticeptr] = VHGnewtext;",
        )),
        "GOES NEW replaces resumed progress with a persisted opening flight",
    )
    check(
        all(token in game for token in (
            '"VHG console overlay"', "VHGconsoletitle = { GOES_COMMAND_CONSOLE };",
            "[VHGascii] = 0; [Console Command] = GET CONSOLE INPUT; isocall;",
            "? failed -> VHG console ring ready;", "CLEAR CONSOLE BUFFER",
            "? A = 71 -> VHG activate console shortcut;",
            "? A != 9 -> VHG console key ready; [VHPkey] = 13;",
            "A = [VHGconsole]; ? A != 0 -> VHG device key done;",
            "A = [VHGconsole]; ? A != 0 -> VHG info key done;",
            "[Client Return Action] = service VHG GUI return;",
        ))
        and "Client Return Action = 1;" in igui
        and "? [Menu On] = NO -> KDMA Client Return;" in igui
        and all(token in catalog for token in (
            '"VHCAT load missing"', "[VHCATbytes] = VHCATHDRBYTES;",
            "[vhcatraw] = VHCATHDRBYTES;", "A = [vhcatraw]; ? A < VHCATHDRBYTES",
            "? A > [VHCATbytes] -> VHCAT load bad;",
            '"VHCAT write record ready"', "[Block Size] = VHCATHDRBYTES;",
        )),
        "GOES consumes one character per physical press and creates a valid empty starmap",
    )
    help_output = section(game, '"VHG GOES HELP"', '"VHG load checkpoint"')
    check(
        all(token in original_help for token in (
            'db\t"ST   SL   DL    PAR  "', 'db\t"WHERE     CLEAN      "',
            'db\t"CAST CAT  REP   DELE "', 'db\t"PRI       PRIF       "',
            'db\t"INBOX     OUTBOX     "', 'db\t"IMPORTGD             "',
            'db\t"REPAIR    X          "',
        ))
        and all(token in game for token in (
            '"VHG command maybe help"', "A = [vhptext plus 45]; ? A != 80 -> VHG command done;",
            '"VHG command help ready"', "[VHGcmdsilent] = 1; => VHG GOES HELP;",
            "VHGgoeshelp0 = { ST___SL___DL____PAR__ };",
            "VHGgoeshelp3 = { PRI_______PRIF_______ };",
            "VHGgoeshelp5 = { IMPORTGD_____________ };",
            "VHGgoeshelp6 = { REPAIR____X__________ };",
        ))
        and help_output.count("=> VH GOES output line;") == 7,
        "GOES HELP restores the original seven-row resident module directory",
    )
    starmap = (ROOT / "work" / "STARMAP.BIN").read_bytes()
    records = []
    for offset in range(4, len(starmap), 32):
        identity = struct.unpack_from("<d", starmap, offset)[0]
        raw_label = starmap[offset + 8:offset + 32]
        if starmap[offset:offset + 8] == b"Removed:":
            continue
        records.append((
            identity,
            raw_label[:20].decode("latin-1").rstrip(),
            chr(raw_label[21]),
            int(raw_label[22:24]),
        ))
    titania = next(record for record in records if record[1] == "TITANIA")
    titania_parent = next(
        record for record in records
        if record[2] == "S" and abs(record[0] - (titania[0] - titania[3])) < 0.00001
    )
    check(
        all(token in original for token in (
            'if (!memcmp (goesnet_command, "CLR", 3))',
            "remove (goesoutputfile);",
        ))
        and all(token in original_where for token in (
            'msg ("  GOES GALACTIC MAP  ");',
            'msg ("AMBIGUOUS SEARCH KEY:");',
            'msg ("THIS OBJECT IS A STAR");',
            'msg ("IS PART OF THE");',
            "subject_id -= (object_label[22]-'0') * 10;",
            "subject_id -= (object_label[23]-'0');",
        ))
        and all(token in game for token in (
            '"VHG command maybe clear"', "=> VH GOES output clear;",
            '"VHG command maybe where"', '"VHG WHERE"',
            '"VHG WHERE record match"', '"VHG WHERE output label"',
            "[VHGwherematches]+;", "[VHGwhereexact] = 1;",
            "A = 0; A - [VHGwherecode]; [FI] = A; => NsIdentAddInt;",
            "[VHCATtype] = VHCATS;", "=> VHCAT find;",
        ))
        and all(token in panels for token in (
            '"VH GOES output clear"', "[VHPouti]+; A = [VHPouti]; ? A < VHPHISTORYCELLS",
            "[VHPoutrows] = 0; [VHPoutview] = 0;",
        ))
        and titania[2:] == ("P", 1)
        and titania_parent[1:3] == ("FAIRY", "S")
        and sum(name.startswith("F") for _, name, _, _ in records) > 1,
        "GOES CLR and WHERE restore resident output clearing and real catalogue parent lookup",
    )
    sl_section = section(game, '"VHG SL"', '"VHG SL ranged start"')
    output_line = section(panels, '"VH GOES output line"', '"VH GOES output window"')
    star_labels = [
        starmap[offset + 8:offset + 28].decode("latin-1")
        for offset in range(4, len(starmap), 32)
        if starmap[offset:offset + 8] != b"Removed:"
        and starmap[offset + 29:offset + 30] == b"S"
    ]
    check(
        all(token in original_sl for token in (
            'msg ("SL (OPTIONAL RANGE)");', 'msg ("GLOBAL STARS LISTING:");',
            'msg ("RANGED STARS LISTING:");', "if (sts <= 2 || sts > 10000)",
            'memcmp (&object_id, "Removed:", 8)', "object_label[21] == 'S'",
            'sprintf (textbuffer, "*%s", object_label);', 'msg ("STARS LISTING END.");',
            "retval = isthere (object_id);", 'sprintf (textbuffer, "$D=%1.2f L.Y.",',
            'msg ("INTERRUPTED!");',
        ))
        and all(token in game for token in (
            '"VHG command maybe sl"', '"VHG command sl range ready"', '"VHG SL"',
            'VHGslglobal = { GLOBAL_STARS_LISTING: };', '"VHG SL catalogue loop"',
            "? C = VHCATTOMB1 -> VHG SL catalogue next;", "? A != VHCATS -> VHG SL catalogue next;",
            "[VHGslline plus 0] = 42;", "? A < 20 -> VHG SL label copy;",
            '"VHG SL ranged start"', '"VHG SL advance"', "[VHGslbudget] = 65536;",
            '"VHG SL scan candidate"', '"VHG SL output distance"', '"VHG SL cancel"',
            "[VHGslcancelheld] = 1;", "=> VHG SL advance; => VHG DL advance; => VHG fpu clean;",
        ))
        and "=> VHCAT identity valid;" not in sl_section
        and "? A = 95" not in output_line
        and all(token in panels for token in (
            "VHPHISTORYROWS = 8192;", "VHPHISTORYCELLS = 172032;",
            "vhpout = 172032;", "? A < VHPHISTORYROWS -> VHP output row available;",
        ))
        and len(star_labels) == 7579
        and star_labels[0].rstrip() == "FENIA"
        and star_labels[-1].rstrip() == "GM-E01-51",
        "GOES SL preserves the global catalogue and frame-batches the source ranged scan",
    )
    elraine = next(record for record in records if record[1] == "ELRAINE" and record[2] == "S")
    par_range = 14
    opening_dzat = (3979984 + 100, -43407 + 100, -43984 + 100)
    par_base = tuple(
        int((coordinate - par_range * 50000) / 100000) * 100000
        for coordinate in opening_dzat
    )
    par_xyz = par_candidate(
        par_base[0] + 6 * 100000,
        par_base[1],
        par_base[2] + 5 * 100000,
    )
    par_identity = ((par_xyz[0] / 100000) * par_xyz[1] / 100000) * par_xyz[2] / 100000
    check(
        all(token in original_par for token in (
            "sect_x = (dzat_x - visible_sectors_x*50000) / 100000;",
            "db 0x66; imul dx",
            "fmul idscale",
            "if (isthere (star_id))",
            'sprintf (textbuffer, "Y=%1.0f", -laststar_y);',
            "if (sts <= 2 || sts > 10000)",
        ))
        and all(token in game for token in (
            '"VHG command maybe par"', '"VHG PAR"', '"VHG PAR sector base"',
            "A = [VHGparrange]; A '* 50000;", "=> VHS foldmul;",
            "[FJ0] = [VHStempx]; [FJ1] = [VHStempy]; [FJ2] = [VHStempz]; => NsIdentityD;",
            "A = 0; A - [VHStempy]; [VHGparcoord] = A;",
            "VHGparhead = { GOES_STARMAP_ANALYSIS };",
            "=> VH GOES output window;", '"VHG console output row"',
        ))
        and par_base == (3200000, -700000, -700000)
        and par_xyz == (3811056, -707894, -212149)
        and abs(par_identity - elraine[0]) < 0.00001,
        "GOES PAR regenerates a catalogued star and reports source-convention coordinates",
    )
    fenhome = next(record for record in records if record[1] == "FENHOME" and record[2] == "P")
    check(
        all(token in original_dl for token in (
            'msg ("DEPENDENCIES LISTING:");', "if (!isthere (star_id))",
            "prepare_nearstar ();", 'sprintf (textbuffer, "*%s", subjectname);',
            'sprintf (textbuffer, "$%02d&%s", planet_nr, object_label);',
            'sprintf (textbuffer, "[%02d&%s", planet_nr, object_label);',
            "nearstar_p_owner[planet_nr - 1]", "nearstar_p_moonid[planet_nr - 1]",
            "notesabout (object_id)", 'msg ("PLANETS LISTING END.");',
            'msg ("MOONS LISTING END.");',
        ))
        and all(token in game for token in (
            '"VHG command dl parse"', '"VHG DL"', '"VHG DL bar fill"',
            '"VHG DL advance"', "[VHGdlbudget] = 65536;", '"VHG DL output tree"',
            "[VHTtx] = [VHStempx]; [VHTty] = [VHStempy]; [VHTtz] = [VHStempz];",
            "[VHTtx] = [VHGdlsavex]; [VHTty] = [VHGdlsavey]; [VHTtz] = [VHGdlsavez];",
            "VHGdlfindindex = 0;", "[VHGdlfindindex] = [VHGdlmoon];",
            "E = nspowner;", "E = nspmoonid;", '"VHG DL output notes"',
            'VHGdlplanetsend = { PLANETS_LISTING_END. };',
            'VHGdlmoonsend = { MOONS_LISTING_END. };',
        ))
        and fenhome[3] == 3
        and abs((fenhome[0] - fenhome[3]) - elraine[0]) < 0.00001,
        "GOES DL regenerates and restores a source-ordered planet and moon dependency tree",
    )
    check(
        all(token in original_st for token in (
            'msg ("LOOKING FOR TARGET...");', "void settarget ()",
            'msg ("REM. TARGET DATA SENT");', 'msg ("STARTING VIMANA DRIVE");',
            "if (laststar_x < nearstar_x - idscale || laststar_x > nearstar_x + idscale)",
            'msg ("LOC. TARGET DATA SENT");', 'msg ("BEGIN IN-SYSTEM DRIVE");',
        ))
        and all(token in game for token in (
            '"VHG command starts st"', "[VHGparaction] = 1;", '"VHG ST scan hit"',
            "[VHTtx] = [VHStempx]; [VHTty] = [VHStempy]; [VHTtz] = [VHStempz];",
            "=> VHG activate target;", '"VHG ST local hit"',
            "A = [MgApreached]; ? A = 0 -> VHG ST local missing;",
            "? A '>= [nsnob] -> VHG ST local missing; [VHGplanet] = A;",
            "=> VHCAT refresh; => VHG local reset; => VHG local start;",
        ))
        and fenhome[3] == 3
        and abs((fenhome[0] - fenhome[3]) - elraine[0]) < 0.00001,
        "GOES ST targets a named star and starts local drive only for its reached-system planet",
    )
    guide = GUIDE_DATA.read_bytes()
    guide_records = (len(guide) - 4) // 84
    first_guide_identity = struct.unpack_from("<d", guide, 4)[0]
    first_guide_message = guide[12:88].split(b"\0", 1)[0].decode("latin-1")
    second_guide_message = guide[96:172].split(b"\0", 1)[0].decode("latin-1")
    suricrasia = next(record for record in records if record[1] == "SURICRASIA")
    check(
        all(token in original_cat for token in (
            'msg (" GOES GALACTIC GUIDE ");', 'msg ("CAT OBJECTNAME:X..Y");',
            "rec_start = atoi (parbuffer + is);", "rec_end = atoi (parbuffer + i + 2);",
            "if (mblock_subject > subject_id - idscale && mblock_subject < subject_id + idscale)",
            'sprintf (textbuffer, "(%d)", rec);', "if (pre >= 21)",
        ))
        and all(token in guide_source for token in (
            "VHGDBMAX = 8388608;", 'VHGDBfile = { GUIDE.BIN };',
            '"VHGDB load"', "A '% VHGDBREC;", "[VHGDBloaded] = 1;",
        ))
        and all(token in game for token in (
            '"VHG command maybe cat"', '"VHG CAT"', '"VHG CAT guide loop"',
            '"VHG CAT output record"', '"VHG CAT message word length"',
            "? A > 21 -> VHG CAT message break space;",
        ))
        and "Name = 'GUIDE.BIN';         Size = -3" in package_script
        and len(guide) == 4063588
        and struct.unpack_from("<I", guide, 0)[0] == len(guide)
        and guide_records == 48376
        and suricrasia[1:] == ("SURICRASIA", "P", 4)
        and abs(first_guide_identity - suricrasia[0]) < 0.00001
        and guide_wrap(first_guide_message) == [
            "SURICRASIA: ONE OF", "THE MOST BEAUTIFUL", "PLANETS IN THE WHOLE", "GALAXY, AT",
        ]
        and guide_wrap(second_guide_message) == [
            "LEAST FROM MY POINT", "OF VIEW. NOBODY", "SHOULD MISS THE", "SURICRASIAN SKY AT",
        ],
        "GOES CAT reads the original Galactic Guide with ranged 21-column records",
    )
    check(
        all(token in original_pri for token in (
            'msg ("PRI OBJECTNAME:X..Y");', 'int COLS = 72;',
            'pmsg ("GOES GALACTIC GUIDE DATA SNIPPET");',
            "if (rec >= rec_start && rec <= rec_end)", "if (pre >= COLS)",
            'pmsg ("- END OF DATA -");',
        ))
        and all(token in game for token in (
            'VHGprifile = { GUIDE-PRINT.TXT };', '"VHG command maybe pri"',
            '[VHGcataction] = 1; -> VHG command cat parse;', '"VHG PRI"',
            '"VHG PRI guide loop"', '"VHG PRI message word length"',
            "? A <= 72 -> VHG PRI message reread;", '"VHG PRI flush line"',
            "[Block Pointer] = VHGpriline; [Block Size] = [VHGpricol]; isocall;",
            "[VHGpricrlf] = 00000A0Dh;", "[File Size] = [VHGpripos]; isocall;",
            "[VHGpricleari] = 0;", "? A < 18 -> VHG PRI clear line loop;",
        )),
        "GOES PRI exports source-ranged Guide text with independent 72-column line packing",
    )
    check(
        all(token in game for token in (
            'VHGprifusage1 = { PRIF_OBJECTNAME };',
            'VHGprifusage2 = { PRIF_OBJECTNAME:X..Y };',
            'VHGpriffile = { GDOUTPUT.TXT };',
            '"VHG command maybe prif"', '"VHG command prif parse"',
            '[VHGcataction] = 2; -> VHG command cat spaces;',
            '? A != 0 -> VHG command pri ready;',
            '[VHGprioutput] = VHGpriffile; [VHGpriexportname] = VHGprifexport1;',
            '[File Name] = [VHGprioutput]; [File Position] = [VHGpripos]; [File Command] = WRITE;',
        )),
        "GOES PRIF shares PRI selection and writes the historical GDOUTPUT.TXT destination",
    )
    check(
        all(token in game for token in (
            'VHGxfile = { X.TXT };', 'VHGxbufferfile = { XBUFF.TXT };',
            '"VHG command x parse"', '=> VHG X queue; -> VHG command done;',
            '"VHG X queue"', '"VHG X append buffer"', '"VHG X promote"',
            '[File Name] = VHGxbufferfile; [File Command] = DESTROY; isocall; end;',
            '"VHG X get byte"', '"VHG X put byte"',
            'A = FFh; A < B; A !; C = [E]; C & A;',
            '"VHG command maybe importgd"',
            'VHGimportold0 = { IMPORTGD_NOT_REQUIRED. };',
            'VHGimportold1 = { GUIDE.BIN_IS_THE_NATIVE };',
        )),
        "GOES X restores the source file queue while IMPORTGD refuses an incompatible conversion",
    )
    check(
        all(token in original0 for token in (
            "void snapshot (int forcenumber, char showdata)",
            'sprintf (snapfilename, "..\\\\GALLERY\\\\%08d.BMP", prog);',
            "if (showdata) {",
            "_write (ih, t, 54);",
            "for (ptr=63680; ptr<64000; ptr-=320) _write (ih, adapted+ptr, 320);",
        ))
        and "snapshot (0, 0);" in original
        and all(token in game for token in (
            'VHGsnapshotfile = { GALLERY\\\\00000000.BMP };',
            '"VHG snapshot key"', "? A = 109 -> VHG snapshot key pressed;",
            '"VHG raw snapshot key"', "? A != 98 -> VHG raw snapshot key done;",
            "A = [VHGgraphics]; ? A != 0 -> VHG raw snapshot key done;",
            '"VHG raw snapshot pending"', "[VHGsnapshotbase] = VHGUIframe;",
            "[VHGsnapshotready] = 1;", "[VHGsnapshotheader plus 0] = E8364D42h;",
            "[Block Pointer] = VHGsnapshotheader; [Block Size] = 54; isocall;",
            "A = 199; A - [VHGsnapshotrow]; A '* 320; A + [VHGsnapshotbase];",
            '"VHG snapshot assemble pixel"',
            "[Block Pointer] = VHGmovieoutput; [Block Size] = 256000; isocall;",
            "[File Size] = 256054; isocall;",
        ))
        and '"VHG snapshot row loop"' not in game
        and "=> VHGUI prepare;\n\t\t=> VHG raw snapshot pending;\n\t\t=> VHG wide raw pending;\n\t\t=> VHG movie capture pending;\n\t\t=> VHG fps overlay;" in game,
        "M or * writes a composed snapshot while B or surface Delete captures before port overlays",
    )
    movie = section(game, '"VHG movie capture pending"', '"VHG snapshot key"')
    movie_input = section(game, '"VHG movie key"', '"VHG visor keys"')
    check(
        all(token in original0 for token in (
            "void ShowMovieSetup(int moviefsec, char movieflashoff, int moviedeck)",
            'sprintf (outhudbuffer, "MOVIEDECK %3i                 (CTRL +/-)"',
            'sprintf (outhudbuffer, "CAPTURE EVERY %3i FRAMES           (+/-)"',
            'sprintf (snapfilename, "..\\\\MOVIES\\\\%03i\\\\%08d.BMP", moviedeck, movienr);',
        ))
        and all(token in original for token in (
            "if (movie) {", "moviedelay = moviedelay - 1;",
            "snapshot (0, 0);", "moviedelay = moviefsec;",
            "if (c=='+' && moviestat && moviefsec < 999 && !movie)",
            "if (c == 'p' && !(labstar || labplanet))",
        ))
        and all(token in movie_input for token in (
            "A = [KEY F3];", "A = [KEY CROSS];", "A = [KEY HYPHEN];",
            "A = [KEY CONTROL]; ? A = ON -> VHG movie deck higher;",
            "? A = 43 -> VHG movie increase key; ? A = 45 -> VHG movie decrease key;",
            "[VHGmovieinterval]+;", "[VHGmovieinterval]-;",
            '"VHG movie pause recording"', '"VHG movie stop"',
            '"VHG movie check deck"', "[VHGmoviefile plus 18] = 49;",
        ))
        and all(token in movie for token in (
            "A = [VHGdosim]; ? A = 0 -> VHG movie capture pending done;",
            "[VHGmoviedelay] = [VHGmovieinterval];",
            '"VHG movie write"', "A = 199; A - [VHGmovierow];",
            "[Block Pointer] = VHGmovieoutput; [Block Size] = 256000; isocall;",
            "[File Size] = 256054; isocall;",
        ))
        and 'VHGmoviefile = { MOVIES\\\\001\\\\00000001.BMP };' in game,
        "F3 restores the source moviemaker UI, controls, cadence, and numbered raw BMP decks",
    )
    check(
        all(token in original1 for token in (
            "const int widesnappingangle = 71;",
            "if ((w == '/' || w == 'n') && !widesnapping)",
            "if ((w == 'v' || w == '.') && !widesnapping)",
            "user_beta += widesnappingangle;",
            "user_beta -= 2 * widesnappingangle;",
            "line*916L + 1078L + 309L", "adapted + 10, 299",
            "line*916L + 1078L + 608L", "adapted + 10, 308",
        ))
        and all(token in game for token in (
            '"VHG wide snapshot key"', "? A = 110 -> VHG wide snapshot data;",
            "? A = 118 -> VHG wide snapshot raw;", "VHGwideframes = 192000;",
            '"VHG wide capture"', "A '* 64000; A + VHGwideframes;",
            "A = [VHGwideoriginalbeta]; A + 71;",
            "A = [VHGwideoriginalbeta]; A - 71;",
            '"VHG wide write"', "[VHGsnapshotheader plus 4] = 03940000h;",
            '"VHG wide assemble left"', "? A < 309 -> VHG wide assemble left;",
            '"VHG wide assemble center"', "? A < 299 -> VHG wide assemble center;",
            '"VHG wide assemble right"', "? A < 308 -> VHG wide assemble right;",
            "[Block Pointer] = VHGwideoutput; [Block Size] = 732800; isocall;",
            "[File Size] = 732854;", "[VHGbeta] = [VHGwideoriginalbeta];",
        ))
        and "=> VHGUI prepare;\n\t\t=> VHG raw snapshot pending;\n\t\t=> VHG wide raw pending;" in game
        and "=> VHG about overlay;\n\t\t=> VHG wide data pending;\n\t\t=> VHG wide advance;" in game
        and 309 + 299 + 308 == 916
        and 54 + 916 * 200 * 4 == 732854,
        "surface wide snapshots restore the source three-panel 71-degree composite",
    )
    check(
        all(token in original_cast for token in (
            'msg ("CAST OBJECTNAME:NOTES");', 'msg ("MISSING COLON BETWEEN");',
            'msg ("TRANSFER SUCCEDED:");', 'msg ("MESSAGE SENT;");',
            "lseek (gh, 0, SEEK_END);", "_write (gh, &subject_id, 8);",
            "_write (gh, parbuffer + i + 1, mlen);", 'msg ("MESSAGE ACCEPTED.");',
        ))
        and all(token in game for token in (
            '"VHG command maybe cast"', '"VHG command cast message length"',
            '"VHG CAST"', '"VHG CAST syntax result"', '"VHG CAST void result"',
            "[VHGDBmsgptr] = [VHGcastmsgptr]; [VHGDBmsglen] = [VHGcastmsglen]; => VHGDB add;",
        ))
        and all(token in guide_source for token in (
            '"VHGDB add"', "? A > 76 -> VHGDB add done;",
            "? B != 95 -> VHGDB pack character ready; B = 32;",
            "[File Position] = [VHGDBbytes]; [File Command] = WRITE;",
            "[VHGDBrecs]+; [VHGDBstatus] = 1;",
            "A = [vhguidedata]; ? A < VHGDBHDR -> VHGDB load bad;",
            "? A > [VHGDBbytes] -> VHGDB load bad;",
        ))
        and "$consolidated -lt 4 -or $consolidated -gt $bytes.Length" in package_script
        and "($consolidated - 4) % 84 -ne 0" in package_script,
        "GOES CAST appends reloadable player notes after the consolidated guide boundary",
    )
    check(
        all(token in original_rep for token in (
            'msg ("REP OBJNAME:X:NOTES");', 'msg ("CORRECTION SENT;");',
            "rec == rectorep", "tell(gh) >= guide_consolidated",
            'msg ("CORRECTION ACCEPTED.");', 'msg ("MESSAGE IS PROTECTED.");',
            'msg ("NO SUCH RECORD!");',
        ))
        and all(token in game for token in (
            '"VHG command maybe rep"', '"VHG command rep record digits"',
            '"VHG command rep message length"', '"VHG REP"',
            '"VHG REP guide loop"', '"VHG REP protected result"',
            "[VHGDBrecordno] = [VHGcatrecno]",
            "[VHGDBmsgptr] = [VHGrepmsgptr]; [VHGDBmsglen] = [VHGrepmsglen]; => VHGDB replace;",
        ))
        and all(token in guide_source for token in (
            '"VHGDB replace"', "? A >= [vhguidedata] -> VHGDB replace local;",
            "[VHGDBstatus] = 2;", "A = [VHGDBrecordno]; A '* VHGDBREC;",
            "[File Position] = [VHGDBpos]; [File Command] = WRITE;",
            "[Block Size] = VHGDBREC; isocall;", "[VHGDBstatus] = 1;",
        )),
        "GOES REP corrects local guide notes while protecting consolidated records",
    )
    check(
        all(token in original_dele for token in (
            'msg ("DELE OBJECTNAME:X..Y");', "rec >= rec_start && rec <= rec_end",
            "round >= guide_consolidated", '_write (gh, "Removed:", 8);',
            'sprintf (outbuffer, "TOTAL RECORDS: %d", tmessages);',
            'sprintf (outbuffer, "PROTECTED: %d", tmessages - rmessages);',
        ))
        and all(token in game for token in (
            '"VHG command maybe dele"', '"VHG command dele range last digits"',
            '"VHG DELE"', '"VHG DELE guide match"', '"VHG DELE summary"',
            "[VHGDBrecordno] = [VHGcatrecno]; => VHGDB remove;",
        ))
        and all(token in guide_source for token in (
            '"VHGDB remove"', "[A] = 6F6D6552h; [A plus 1] = 3A646576h;",
            "[Block Pointer] = [VHGDBptr]; [Block Size] = 8; isocall;",
            "? A >= [vhguidedata] -> VHGDB remove local;",
        )),
        "GOES DELE tombstones only ranged local guide records and reports protected totals",
    )
    check(
        all(token in original_clean for token in (
            'msg ("CLEANING STARMAP...");', 'msg ("CLEANING GUIDE...");',
            'memcmp(&object_id, "Removed:", 8)', 'memcmp(&mblock_subject, "Removed:", 8)',
            "cleaned_starmap_consolidated -= 32;", "cleaned_guide_consolidated -= 84;",
            'msg ("END");',
        ))
        and all(token in game for token in (
            '"VHG command maybe clean"', '"VHG CLEAN"',
            "=> VHCAT clean;", "=> VHGDB clean;", '"VHG CLEAN output count"',
        ))
        and all(token in catalog for token in (
            '"VHCAT clean"', "[VHCATcleanboundary] - VHCATRECBYTES;",
            "[Block Pointer] = vhcatraw; [Block Size] = [VHCATbytes]; isocall;",
            "[VHCATrecs] = [VHCATcleanout]; [VHCATstatus] = 1;",
        ))
        and all(token in guide_source for token in (
            '"VHGDB clean"', "[VHGDBcleanboundary] - VHGDBREC;",
            "[Block Pointer] = vhguidedata; [Block Size] = [VHGDBbytes]; isocall;",
            "[VHGDBrecs] = [VHGDBcleanout]; [VHGDBstatus] = 1;",
        ))
        and "$consolidated -lt 4 -or $consolidated -gt $bytes.Length" in package_script
        and "($consolidated - 4) % 32 -ne 0" in package_script,
        "GOES CLEAN compacts both tombstone databases while preserving consolidated boundaries",
    )
    check(
        all(token in original_repair for token in (
            b" GOES REPAIR UTILITY ", b"(PROCESSING STARMAP)",
            b"(PROCESSING GUIDE)", b"ERRORS FOUND:",
            b"PLEASE RUN ", b"CLEAN", b"TO REMOVE GARGABE.",
        ))
        and repair_duplicates([
            (1.0, b"ALPHA"), (2.0, b"ALPHA"),
            (1.000005, b"BETA"), (1.00002, b"GAMMA"),
        ], require_payload=False) == [2]
        and repair_duplicates([
            (10.0, b"same comment"), (10.000005, b"same comment"),
            (10.0, b"SAME COMMENT"), (11.0, b"same comment"),
        ], require_payload=True) == [1]
        and all(token in game for token in (
            '"VHG command maybe repair"', '"VHG command repair ready"',
            '"VHG REPAIR"', "=> VHCAT repair;", "=> VHGDB repair;",
            "VHGrepairgarbage = { TO_REMOVE_GARGABE. };",
        ))
        and all(token in catalog for token in (
            '"VHCAT repair"', '"VHCAT repair duplicate"', "=> VHCAT bounds;",
            "[E] = VHCATTOMB0; [E plus 1] = VHCATTOMB1;",
            "[Block Pointer] = vhcatraw; [Block Size] = [VHCATbytes]; isocall;",
        ))
        and all(token in guide_source for token in (
            '"VHGDB repair"', '"VHGDB repair compare word"',
            "? A < 19 -> VHGDB repair compare word;", "=> VHCAT bounds;",
            "[Block Pointer] = vhguidedata; [Block Size] = [VHGDBbytes]; isocall;",
        )),
        "GOES REPAIR keeps first identities and tombstones only source-equivalent duplicates",
    )
    check(
        all(token in original_outbox for token in (
            '_write (ph, "STARMAP_", 8);', "lseek (fh, starmap_size, SEEK_SET);",
            'memcmp (&object_id, "Removed:", 8)', '_write (ph, "GUIDE___", 8);',
            "lseek (gh, guide_size, SEEK_SET);", 'memcmp (&mblock_subject, "Removed:", 8)',
            'msg ("OUTGOING LABELS:");', 'msg ("OUTGOING COMMENTS:");',
        ))
        and all(token in game for token in (
            '"VHG command maybe outbox"', '"VHG OUTBOX"',
            "[VHGoutboxmarker plus 0] = 52415453h; [VHGoutboxmarker plus 1] = 5F50414Dh;",
            "A = [vhcatraw]; A - VHCATHDRBYTES; A / VHCATRECBYTES;",
            "[Block Pointer] = [VHGoutboxptr]; [Block Size] = VHCATRECBYTES; isocall;",
            "[VHGoutboxmarker plus 0] = 44495547h; [VHGoutboxmarker plus 1] = 5F5F5F45h;",
            "A = [vhguidedata]; A - VHGDBHDR; A / VHGDBREC;",
            "[Block Pointer] = [VHGoutboxptr]; [Block Size] = VHGDBREC; isocall;",
            '"VHG OUTBOX output count"', "[File Size] = [VHGoutboxpos]; isocall;",
        )),
        "GOES OUTBOX exports only live local labels and Guide notes in source packet order",
    )
    check(
        all(token in original_inbox for token in (
            'memcmp (&object_id, "STARMAP_", 8)', 'memcmp (&object_id, "GUIDE___", 8)',
            "lseek (fh, starmap_size, SEEK_SET);", "chsize (fh, starmap_size);",
            "s_object_id >= object_id - idscale", '_write (fh2, "Removed:", 8);',
            "lseek (gh, guide_size, SEEK_SET);", "chsize (gh, guide_size);",
            "!strcmp (s_mblock_message, mblock_message)", '_write (gh2, "Removed:", 8);',
            'msg ("IMPORTED LABELS:");', 'msg ("IMPORTED COMMENTS:");',
        ))
        and all(token in game for token in (
            '"VHG command maybe inbox"', '"VHG INBOX"', '"VHG INBOX preflight labels"',
            "? A > VHGINBOXMAX -> VHG INBOX invalid;", '"VHG INBOX capacity"',
            '"VHG INBOX scan source label"', '"VHG INBOX scan imported labels"',
            '"VHG INBOX scan source comment"', '"VHG INBOX scan imported comments"',
            '"VHG INBOX identity match"', '"VHG INBOX record match"',
            "[VHGinheader] = [VHGinnewboundary]; [File Name] = vhcatfile;",
            "[VHGinheader] = [VHGinnewboundary]; [File Name] = VHGDBfile;",
            '"VHG INBOX rollback"', "[Block Pointer] = vhcatraw; [Block Size] = [VHGinoldcatbytes];",
            "[Block Pointer] = vhguidedata; [Block Size] = [VHGinoldguidebytes];",
            "=> VHCAT load; => VHGDB load;", 'VHGincomplete = { ARCHIVES_UPDATED. };',
        )),
        "GOES INBOX validates, merges, deduplicates, and can roll back source-format packets",
    )
    check(
        all(token in game for token in (
            '"VHG screen poll"', "A = [VHGbeta]; ? A <= VHGN135 -> VHG screen poll changed;",
            "A = [VHGz]; A + 1560; C = 0; C - 810; A / C; [VHGscreen] = A;",
            "[VHPactive] = [VHGscreen];", '"VHG activate wall console"',
            "[VHGconsole] = 1; [VHGconsoleview] = 0;",
            "A = [VHGscreen]; ? A = 2 -> VHG request landing;",
            "A = [VHGconsoleview]; ? A = 0 -> VHG physical console overlay;",
            '"VHG physical console overlay"',
            "A = [VHGscreen]; ? A != 0FFFFFFFFh -> VHG energy overlay done;",
            "A = [VHGscreen]; ? A != 0FFFFFFFFh -> VHG FCS overlay done;",
            "A = [VHGscreen]; ? A != 0FFFFFFFFh -> VHG body overlay done;",
            '"VHG physical landing overlay"', "[VHGlandingview] = 0;",
        ))
        and "=> VHG text both;" not in section(game, '"VHG physical console overlay"', '"VHG console overlay done"')
        and "=> VHG text both;" not in section(game, '"VHG physical landing overlay"', '"VHG landing overlay done"')
        and all(token in panels for token in (
            '"VHP selector zero active"', '"VHP selector one active"',
            '"VHP selector two active"', "A = [VHPcamz]; A + 1620;",
            '"VHP GOES output text"', "A - 2385; A '* 4; [VHPxbase4] = A;",
            "[vhcpoly plus 0] = VHPGR; [vhcpoly plus 3] = VHPGR;",
            "[vhcpoly plus 6] = VHPGL; [vhcpoly plus 9] = VHPGL;",
            "[vhcpoly plus 1] = 3280764928; [vhcpoly plus 4] = 3277979648;",
            "[vhcpoly plus 7] = 3277979648; [vhcpoly plus 10] = 3280764928;",
            '"VH GOES output line"', "vhpout = 172032;", '"VH GOES output window"',
            '"VHP status message length"', "[VHPstatptr] = A;", "[VHPmessage]",
        )),
        "source-ordered nondegenerate glyph quads keep physical GOES input on all three wall faces",
    )
    check(
        all(token in game for token in (
            '"VHG output scroll"', "A = [VHGscreen]; ? A != 1 -> VHG output scroll away;",
            "A = [KEY HOME]; ? A = ON -> VHG output scroll pressed;",
            "A = [KEY END]; ? A = ON -> VHG output scroll pressed;",
            "A = [KEY PGUP]; ? A = ON -> VHG output scroll pressed;",
            "A = [KEY PGDN]; ? A = ON -> VHG output scroll pressed;",
            "[VHPoutptr] = [VHGnoticeptr]; => VH GOES output line;",
            '"VHG output overlay"',
        ))
        and "=> VHG text both;" not in section(game, '"VHG output overlay"', '"VHG console overlay"')
        and all(token in panels for token in (
            '"VHP GOES output text"', "A = [VHPoutview]; A '* 21;",
            "A = [VHPfi]; ? A < 147 -> VHP output text loop;",
        )),
        "second GOES face retains scrolling output directly on its physical 3D display",
    )
    check(
        all(token in catalog for token in (
            "VHCATEMAX = 1068;", "VHCATTOMB0 = 6F6D6552h;",
            '"VHCAT identity valid"', "? A = 0 -> VHCAT identity valid done;",
            "? A = 7FFh -> VHCAT identity valid done;",
            "? A >= VHCATEMAX -> VHCAT identity valid done;",
            "? A = 0 -> VHCAT find next;", "? A = 0 -> VHCAT duplicate next;",
            "? A = 0 -> VHCAT add done;",
        )),
        "live starmap lookup and naming skip malformed identities and tombstones",
    )
    check(
        all(token in game for token in (
            '"VHG local start"', '"VHG local step"', '"VHG local render"',
            '"VHG local substep"', "[VHGlocalbatch] = 32;",
            "=> MGD reset; [MgNframes] = 1; => MG approach loop;",
            "A = [MgIpreached]; ? A != 0 -> VHG landing local ready;",
            "[VHGnoticeptr] = VHGapproachtext;", "=> VHG local render;",
            "VHGfcsapproach = { FCS APPROACH };",
            '"VHG landing selector input"', '"VHG landing overlay"',
            'VHGlandingstatus = { LQ 000:060 };', '"VHG landing status format"',
            "=> VHG landing status format; [VHPmessage] = VHGlandingstatus;",
            "[VHGlandingselect] = 0; [VHGlandingview] = 1; [VHGlandpending] = 1;", '"VHG landing commit done"',
            "[VHGNDlon] = [VHGlandinglon]; [VHGNDlat] = [VHGlandinglat];",
            "=> VHG prepare planet; => VHG fpu clean;",
            "=> VHGND generate; => VHG fpu clean;",
            "=> VHGND sky; => VHG fpu clean;",
        ))
        and all(token in original for token in (
            "if (ip_reaching)", "current_approach_coefficient +=",
            "if (l_dsd < 2*nearstar_p_ray[ip_targetted])",
            "landing_pt_lon++;", "landing_pt_lat--;", "land_now = 1;",
            'sprintf (short_text, "LQ %03d:%03d", landing_pt_lon, landing_pt_lat);',
            "status (short_text, 10);",
        )),
        "selected bodies expose active approach and a visible source-shaped landing-site selector",
    )
    check(
        all(token in game for token in (
            '"VHG collector step"', '"VHG power reserve"', '"VHG energy overlay"',
            "? A = 67 -> VHG collector shortcut;", '"VHG collector action"',
            "A = 50; => BrtlRandom;",
            "[FI] = 125;", "[FI] = 25;", "[MgCharge]-; [MgPwr] = 20000;",
            "[MgPwr] = 15001; [MgCharge]+;", "VHGenergytext = { PWR 00000 LI 003 OFF };",
            "C = [VHTclass]; ? C != 5 -> VHG collector rate ready;",
            "? A > 0 -> VHG collector rate ready; [VHGcollectrate] = 1; A = 1;",
            "[VHGnoticeptr] = VHGcollecttext; [VHGnoticeframes] = 25;",
            "A = [MgAptgt]; ? A != 1 -> VHG collector needs calibration;",
            "[MgLdsd0] = [FA0]; [MgLdsd1] = [FA1]; [FI] = 1; => IntToF;",
        ))
        and "A = [VHGlocalactive]; ? A != 0 -> VHG collector stop;" not in game
        and "A = [VHGlocalactive]; ? A != 0 -> VHG collector needs calibration;" not in game
        and "[MgPwr] = 30000" not in section(game, '"VHG flight retarget"', '"VHG flight step"')
        and "[MgPwr] = 20000; [MgCharge] = 3;" in section(game, '"VHG flight init"', '"VHG target world"')
        and all(token in original for token in (
            "if (lithium_collector)", "ir = random (50);", "ir -= 125 / dsd;",
            "ir -= 25 / dsd;", "if (ir <= 0) ir = 1;", 'SCOPING...',
            "if (charge < 120)", "charge++;",
        ))
        and all(token in save for token in (
            "[vhsvbuf plus 31] = [MgCharge];", "[vhsvbuf plus 32] = [VHGcollector];",
            "A = [vhsvbuf plus 31];", "[MgCharge] = A;", "[VHGcollector] = A;",
            "[vhsvbuf plus 35] = [VHGutcsecs];", "=> VHG offline restore;",
        ))
        and all(token in game for token in (
            '"VHG UTC timestamp"', '"VHG offline restore"',
            "A = [VHGelapsed]; A '/ 30;", "A = 5000; => BrtlRandom; A + 15000;",
            '"VHG offline collector full"', "[MgPwr] = 20000;",
        )),
        "live and closed-game lithium collection use exact source gates, minimum yield, feedback, and persistence",
    )
    check(
        all(token in game for token in (
            "? A = 72 -> VHG help shortcut;", '"VHG help action"',
            "A = [MgPwr]; ? A > 15000 -> VHG help not required;",
            "A = [MgCharge]; ? A != 0 -> VHG help not required;",
            "[VHGrescueactive] = 1; [VHGrescuetick] = 0; [VHGrescueacc] = 0;", '"VHG rescue advance"',
            "A = [VHGrescueacc]; A + 1000;", "? A < 18206 -> VHG rescue tick done;",
            "A = [VHGrescuedelay]; ? A <= 0 -> VHG rescue flyby second;",
            "? A = 20 -> VHG rescue transfer;", "? A < 120 -> VHG rescue tick done;",
            "[Timer Command] = READ COUNTS; isocall; A = [Counts]; => SU fast srand;",
            "A = 32767; => BrtlRandom; A '* [VHGrescuedist]; A / 32767;",
            "A = [MgCharge]; ? A >= 3", "[MgCharge] = 3;", '"VHG rescue render"',
            "C '* 2000; C + 16000;", "=> VH polycupola; => VH cupola grid;",
            '"VHG rescue near upper done"', '"VHG rescue near lower done"',
            "[PVh] = 0; [DWmode] = 0; [DWuds] = 1; => SP drawpv;",
            "=> VH join mode0;", '"VHG rescue far upper done"',
            '"VHG rescue far lower done"', "=> VHG visor flare mode;",
            "[VHFpx] = 3225; [VHFpy] = 0; [VHFpz] = 0; => VH rescue flare;",
            "A - 6150; [VHFpz] = A; => VH rescue flare;",
        ))
        and all(token in flare for token in (
            '"VH rescue flare"', "[VHFadd] = 3;", "[FI] = 500000; => IntToF;",
            "[SPoff] = A; [SPreg] = RGADP; => SP get;",
            "A = [VHFang]; A + [VHFadd];",
        ))
        and all(token in original for token in (
            "if (pwr <= 15000 && !charge)", "if (!stz&&charge<3) charge = 3;",
            "other_vehicle_at ((stz + 16000) * cos (secs / 10)",
            "drawpv (vehicle_handle, 0, 0, ovhx, ovhy, ovhz, 1);",
            "lens_flares_for (cam_x, cam_y, cam_z, 3225, 0, 0, -5e5, 3, hud_closed, 1, 1, 1);",
            "lens_flares_for (cam_x, cam_y, cam_z, -3225, 0, -6150, -5e5, 3, hud_closed, 1, 1, 1);",
        )),
        "depleted ships receive the original reserve from a complete lit rescue fly-by",
    )
    check(
        all(token in save for token in (
            "? A = 144 -> VHSV load size ok; ? A = 152 -> VHSV load size ok;",
            "? A = 156 -> VHSV load size ok; ? A = 160 -> VHSV load size ok;",
            "? A = 168 -> VHSV load size ok; ? A = 180 -> VHSV load size ok;",
            "? A = 188 -> VHSV load size ok; ? A = 192 -> VHSV load size ok;",
            "? A = 256 -> VHSV load size ok; ? A = 264 -> VHSV load size ok;",
            "? A != 268 -> VHSV load done;",
            '"VHSV load version two"', '"VHSV load version three"', '"VHSV load version four"',
            '"VHSV load version five"', '"VHSV load version six"', '"VHSV load version seven"',
            '"VHSV load version eight"', '"VHSV load version nine"', '"VHSV load version ten"',
            '"VHSV load version eleven"', '"VHSV load version twelve"',
            '"VHSV load version thirteen"', '"VHSV load version fourteen"',
            '"VHSV load version fifteen"',
            "[vhsvbuf plus 27] = [VHGfast];",
            "[vhsvbuf plus 28] = [VHGfpsshow];", "[vhsvbuf plus 29] = [VHAwanted];",
            "[vhsvbuf plus 30] = [VHGNDcaptures];", "[VHSVcaptures] = A;",
            "[vhsvbuf plus 33] = [VHGrescueactive];", "[VHGrescuetick] = A;",
            "[vhsvbuf plus 45] = [VHGrescuedelay];", "[vhsvbuf plus 46] = [VHGrescueacc];",
            "[vhsvbuf plus 36] = A;", "[vhsvbuf plus 37] = A;",
            "[vhsvbuf plus 38] = [VHGilight];", "[VHGilight] = A;",
            "[vhsvbuf plus 39] = C;", "[VHGsync] = A;", "[VHGantirad] = A;",
            "[vhsvbuf plus 40] = [VHGlandinglon];", "[VHGlandinglat] = A;",
            "[vhsvbuf plus 42] = [VHGNDdropx];", "[vhsvbuf plus 43] = [VHGNDdropy];",
            "[vhsvbuf plus 44] = [VHGNDdropz];", "[VHSVdropstored] = 1;",
            "[Block Pointer] = vhsvbuf; [Block Size] = 268; isocall;",
            "[vhsvbuf plus 47] = C;", "A = [VHSVsize]; ? A = 192 -> VHSV load graphics stored;",
            "A - 1; [VHGlensmode] = A;", "[VHGdrawhud] = A;", "[VHGseamless] = A;",
            "A = 1; A - [VHGhudclosed]; A '* 16;", "[VHGhudclosed] = 0; [VHGhudcount] = 0;",
            "[vhsvbuf plus 48] = [VHGlocalactive];", "[vhsvbuf plus 49] = [VHGlocaltarget];",
            "A = [vhsvbuf plus 49]; ? A < 0 -> VHSV load local inactive target;",
            "[vhsvbuf plus 50] = [VHGlocalx0];", "[vhsvbuf plus 61] = [MgIpreached];",
            "[vhsvbuf plus 62] = [VHGlocalacc];", "[vhsvbuf plus 63] = [VHGlocalphasetick];",
            "[VHSVlocalstored] = 1;",
            "[vhsvbuf plus 64] = C;", "[vhsvbuf plus 65] = [VHGnavbeta];",
            "C + 4194304; [vhsvbuf plus 66] = C;", "[VHGilightlevel] = A;",
            "[VHGelight] = A;", "[VHGresetcount] = A;", "[VHGgburst] = A;",
            "[VHGautoscreenoff] = A;", "[VHGdepolarize] = A;", "[VHGnavbeta] = A;",
            "? A < MINIMUM WIDTH -> VHSV load done;", "? A > MAXIMUM HEIGHT -> VHSV load done;",
            "[VHSVmusic] = [VHAwanted];", "[VHAwanted] = [VHSVmusic];",
        ))
        and all(token in game for token in (
            '"VHG load original cadence"', "[VHGNDcaptures] = [VHSVcaptures];",
            '"VHG load stored capsule"', "[VHGNDdropx] = [VHGx]; [VHGNDdropz] = [VHGz];",
            "[VHGNDcamx] = [VHGx]; [VHGNDcamz] = [VHGz]; => VHGND eye height;",
            "[VHGNDdropx] = [VHSVdropx]; [VHGNDdropz] = [VHSVdropz];",
            "[VHGNDcamx] = [VHGNDdropx]; [VHGNDcamz] = [VHGNDdropz]; => VHGND eye height;",
            "A = [VHGNDheight]; A + 600; [VHGNDdropy] = A;",
            '"VHG restore window"', "[New Display Width] = [VHSVwindoww];",
            "=> Resize Display;", "=> VHG restore window;", "=> VHA apply;",
            '"VHG restore local checkpoint"', "A = [VHSVlocalstored]; ? A = 0 -> VHG load legacy local;",
            "A = [VHGlocaltarget]; ? A < 0 -> VHG restore local invalid;",
            "[VHGplanet] = A;", "[MgStatus] = 5;",
        ))
        and all(token in igui for token in (
            "Unfull display width", "Unfull display height",
            '"Restore Unfull Window"', "=> Restore Unfull Window;",
        ))
        and all(token in save for token in (
            "? A - EXCLUSIVE -> VHSV save windowed width;",
            "A = [Unfull display width]; -> VHSV save width ready;",
            "A = [Unfull display height]; -> VHSV save height ready;",
        ))
        and all(token in audio for token in (
            "VHAwanted = 1;", '"VHA apply"',
            "[VHAwanted] = 0; => VHA apply;",
            "[VHAwanted] = 1; => VHA apply;",
        ))
        and "PLAY CONTINUOUSLY" not in section(audio, '"VHA init"', '"VHA apply"')
        and (lambda run: (
            run.index("=> VHA init;")
            < run.index("=> VHG load checkpoint;")
            < run.index("=> VHA apply;")
            < run.index("=> Enter Integrated GUI;")
        ))(section(game, '"VHG run"', '"service VHG repaint"')),
        "version-16 checkpoints retain PFS/light fade and safely migrate v1-v15 progress",
    )
    check(
        all(token in ground for token in (
            '"VHGND generate type3"', '"VHGND type3 object classes"',
            "A = 80;", "A = 144;", "A = 160;", "A = 168;",
            '"VHGND veget"', '"VHGND tree"',
            "=> VHGND veget;", "=> VHGND tree;",
        ))
        and '"VHG land general seed"' in game
        and "A = [VHTtx]; A '* 31" not in game,
        "general destinations get source-derived surface seeds and live plains vegetation/trees",
    )
    tree = section(ground, '"VHGND tree"', '"VHGND rock"')
    bush = section(ground, '"VHGND bush"', '"VHGND tree direction"')
    grass = section(ground, '"VHGND veget"', '"VHGND tree"')
    greenmush = section(ground, '"VHGND greenmush"', '"VHGND tree"')
    check(
        all(token in original1 for token in (
            "fast_srand (x+y+z+3);", "int treetype = fast_random(511);",
            "if (treetype == GIANT_TREE)", "layers - 1, divisions",
            "fast_srand (lseed);", "lseed += 3;",
        ))
        and all(token in grnd for token in (
            "GRtreepeak", "GRtreescale", "GRtreespread", "GRbranchwidth",
            "GRrootheight", "GRrootshade", "GRtreeflares", "GRleafflares",
            '"GR prol tree params done"',
        ))
        and all(token in tree for token in (
            '"VHGND tree node enter"', '"VHGND tree node branch"',
            '"VHGND tree terminal"', '"VHGND tree node pop"',
            "[SUfmask] = 511; => VHGND render random; [VHTkind] = C;",
            "A = [VHTkind]; ? A = 333 -> VHGND tree giant;",
            "A = [VHGNDdepth]; ? A > 20 -> VHGND tree far;",
            "? A > 10 -> VHGND tree middle;", "? A > 3 -> VHGND tree distant;",
            "? A > 11 -> VHGND tree giant mush;", "? A > 7 -> VHGND tree giant middle;",
            "? A > 4 -> VHGND tree giant near;",
            "[VHGNDmushmask1] = 15; [VHGNDmushmask2] = 31;",
            "[VHGNDtreelayers] = 4; [VHTforks] = 3; [VHGNDtreefaces] = 5;",
            "A = VHGNDtslseed;", "C + 3; [A] = C;",
            "[VHGNDtreelevel]+;", "[VHGNDtreelevel]-;",
            "[PJnrv] = 4; => PG poly3d;", "[PJnrv] = 3; => PG poly3d;",
        ))
        and "crossed trunk" not in tree
        and "crossed leafy crown" not in tree,
        "trees retain world parameters and execute the full source branch stack",
    )
    check(
        "if (y > -15000)" in original1
        and "cespuglio (x, y, z, depth);" in original1
        and all(token in ground for token in (
            "A = [VHGNDooy]; C = 0; C - 15000;",
            "? A <= C -> VHGND object tall tree;", "=> VHGND bush;",
        ))
        and all(token in cache_objects for token in (
            '"VHGND cache object height upper"',
            '"VHGND cache object height ready"',
            "C - A; C '/ 8; [VHGNDooy] = C;",
            "C = VHGNDobjcachex; C + A; [C] = [VHGNDoox];",
            "C = VHGNDobjcachey; C + A; [C] = [VHGNDooy];",
            "C = VHGNDobjcachez; C + A; [C] = [VHGNDooz];",
            "C = VHGNDobjcacheseed; C + A; [C] = [SUfseed];",
        ))
        and all(token in objects for token in (
            "C = VHGNDobjcachex; C + A; [VHGNDoox] = [C];",
            "C = VHGNDobjcachey; C + A; [VHGNDooy] = [C];",
            "C = VHGNDobjcachez; C + A; [VHGNDooz] = [C];",
            "C = VHGNDobjcacheseed; C + A; [SUfseed] = [C];",
        ))
        and all(token in bush for token in (
            "[VHGNDtreescale] = 3000; [VHGNDtreerange] = 2250;",
            "[VHGNDtreebr] = 450; [VHGNDtreeer] = 337;",
            '"VHGND bush mask one"', '"VHGND bush mask two"',
            "A '* 750; A '/ 32767; A + 187;",
            "[VHGNDtreeleafrad] = 337;", "A '* 1687; A '/ 32767;",
            "A '* 2250; A '/ 32767; [VHGNDtreeleafdrop] = A;",
            "[VHGNDtreefaces] = 2;",
            "[VHGNDmushmask1] = 7; [VHGNDmushmask2] = 7;",
            "[VHGNDmushbase] = 209;", "=> VHGND greenmush;",
        )),
        "low-ground tree objects restore source-shaped depth-dependent bushes",
    )
    check(
        all(token in original1 for token in (
            "if (depth >= 4) return;", "greenmush (x, y, z, 3, 7, 1023, 216, 31, 0);",
            "1000, 1.00, 0.25, 0, 0, 1.0", "1000, 1.00, 0.25, 0, 7, 1.0",
        ))
        and all(token in grass for token in (
            "A = [VHGNDdepth]; ? A >= 4 -> VHGND veget done;",
            "[VHGNDgrassfaces] = 3;", "[VHGNDgrassfaces] = 4;",
            "[VHGNDgrassfaces] = 6;", "[SUfmask] = 7; => SU frnd; C + 1;",
            '"VHGND veget distant"', "[VHGNDmushscale] = 1023;",
            "[VHGNDmushbase] = 216;", "=> VHGND greenmush;",
            "A '* 1000; A '/ 32767;", "[VHGNDgrassby] = A;",
            "[VHGNDgrasstotal]-; -> VHGND veget blade;",
        ))
        and all(token in greenmush for token in (
            "[SUfmask] = [VHGNDmushmask1]; => VHGND render random;",
            "[SUfmask] = [VHGNDmushmask2]; => VHGND render random;",
            "[SUfmask] = 7; => VHGND render random;",
            "[SUfmask] = [VHGNDmushcolmask]; => VHGND render random;",
            "A = [SUfseed]; { F7 E0 }",
            "C = A; C & 0FFh; B = D; B & 0FFh; C + B; C & 0FFh;",
            "A & 0FFFFFF00h; A | C; [SUfeax] = A;",
            "B = [SUfseed]; B + A; [SUfseed] = B;",
            "A & [SUfmask]; [SUfval] = A; C = A;",
            "[VHGNDvv] = [VHGNDmushpx]; [VHGNDvslot] = FSINX; => VHGND vload;",
            "[VHGNDvv] = [VHGNDmushpy]; [VHGNDvslot] = FSINY; => VHGND vload;",
            "[VHGNDvv] = [VHGNDmushpz]; [VHGNDvslot] = FSINZ; => VHGND vload;",
            "=> PG getcoords;",
            "D = nw; D + RADPT; D + [VHGNDmushoff];",
            "[D plus 4] = C; [D plus 5] = C; [D plus 3] = C; [D plus 324] = C;",
            "A = D; A - 316; [A] = C; A = D; A - 636; [A] = C;",
        )),
        "grass tufts restore source depth visibility, density, scale, and distant foliage",
    )
    check(
        all(token in ground for token in (
            '"VHGND generate desert"', '"VHGND generate icy"',
            '"VHGND icy snowfield"', '"VHGND icy bare"',
            '"VHGND icy hills"', '"VHGND icy bergs"',
            '"VHGND texture random"',
            "C = 50; => SU rnd; C + 50; [VHGNDgenn] = C;",
            "[VHGNDtscale] = 128; [VHGNDtexn] = 32;",
            "[VHGNDrockscale] = 0; [VHGNDrockpeak] = 0; [VHGNDrockdensity] = 0;",
            "C + 200; [VHGNDrockscale] = C;",
            "C + 150; [VHGNDrockpeak] = C;",
        ))
        and "[VHGNDgenn] = 24;" not in section(
            ground, '"VHGND icy hills"', '"VHGND icy bergs"'
        ),
        "desert and icy habitable worlds have distinct source-shaped terrain and textures",
    )
    check(
        all(token in ground for token in (
            '"VHGND generate type1"', '"VHGND generate type5"',
            '"VHGND generate type7"', "? A = 1 -> VHGND generate type1;",
            "? A = 5 -> VHGND generate type5;", "? A = 7 -> VHGND generate type7;",
            '"VHGND type1 craters"', '"VHGND type5 craters"',
            '"VHGND type7 surface line loop"',
            "? A '<= 30 -> VHGND type1 crater count ready; A = 30;",
        ))
        and "VHGND type1 texture count ready" not in ground
        and "VHGND type1 line count ready" not in ground
        and "VHGND type7 texture count ready" not in ground
        and "VHGND type7 small count ready" not in ground
        and all(token in grnd for token in (
            '"GR rg positive start"', '"GR sc power done"',
            "D9 F1", "D9 F0", "D9 FD",
        ))
        and "FLAGGED GAP" not in grnd,
        "all accepted landable classes have distinct terrain and powered crater profiles",
    )
    original_surface = section(original1, "void build_surface ()", "void create_sky")
    original_ocean = section(original_surface, "case OCEAN:", "case PLAINS:")
    ocean = section(ground, '"VHGND generate ocean"', '"VHGND generate type4"')
    water = section(ground, '"VHGND water"', '"VHGND waves init"')
    check(
        all(token in original_ocean for token in (
            "waves_in = 1;", "waves_out = 1;", "liquid_water = 1;",
            "T_SCALE = 128;",
        ))
        and all(token in ground for token in (
            '"VHGND water clear objects"', "A & 0FCh; [MBval] = A;",
            "A = [VHGNDs1]; A + [VHGNDs2]; A + [VHGNDs3]; A + [VHGNDs4];",
            "? A = 0 -> VHGND tile done;",
        ))
        and all(token in ocean for token in (
            "[VHGNDtscale] = 128;",
            '"VHGND type3 island test"',
            "C = 3; => SU rnd; ? C != 0 -> VHGND type3 full ocean;",
            "[VHGNDwaswet] = 1;", "=> GR round hill;",
        ))
        and water.count("=> PG polymap;") == 2
        and all(token in water for token in (
            "[SPtinta] = 128;", "[SPflar] = 1;", "[VHGNDwaterphase]",
        )),
        "open-ocean worlds render sea level, shimmer, rare islands, and no floating objects",
    )
    original_horizon = section(
        original1,
        "// mare, per liquido o ghiacciato che sia.",
        "// tracciamento onde in arrivo (onde del mare)",
    )
    reflection = section(ground, '"VHGND reflection"', '"VHGND waves init"')
    check(
        all(token in original_horizon for token in (
            "if (!waves_in)", "mirror = 1;", "halfscan_needed = 1;",
            "iperficie (0);",
        ))
        and all(token in ground for token in (
            "VHGNDmirror = 0; VHGNDwavesin = 0; VHGNDreflected = 0;",
            '"VHGND water render"', "? A != 4 -> VHGND water render done;",
            "A = 0; A - [VHGNDs1]; [VHGNDs1] = A;",
            "A = [VHGNDmirror]; ? A != 0 -> VHGND tile done;",
        ))
        and all(token in reflection for token in (
            "[VHGNDmirror] = 1; [SPhalf] = 1;",
            "A = [VHGNDwavesin]; ? A != 0 -> VHGND reflection done;",
            "[VHGNDmirror] = 0; [SPhalf] = 0;",
        )),
        "calm oceans and ice render a half-scan terrain-only mirror pass",
    )
    original_ruins = section(original1, "void make_ruins", "void build_surface")
    original_history = section(
        original1,
        "// INIZIO MODIFICHE STORICHE",
        "// FINE MODIFICHE STORICHE",
    )
    ruins = section(ground, '"VHGND historical ruins"', '"VHGND type3 object classes"')
    check(
        all(token in original_ruins for token in (
            "case 0:", "case 1:", "case 2:", "case 3:", "case 4:", "case 5:",
            "ruinschart[pt] = AF1;",
        ))
        and all(token in original_history for token in (
            "-37828", "1599551984L", "-11543634L",
            "make_ruins (0,1,1,2,2, 3);",
            "make_ruins (2,4,5,5,5, 2);",
            "landing_pt_lon == 18 && landing_pt_lat == 60",
            "ptr = 112; ptr < 112 + 25", "ptr1 = 103; ptr1 < 103 + 25",
        ))
        and all(token in ruins for token in (
            '"VHGND ruins Balas"', '"VHGND ruins Fenia"', '"VHGND ruins Ylas"',
            '"VHGND ruin tower"', '"VHGND ruin walls"', '"VHGND ruin plaza"',
            '"VHGND ruin palace"', '"VHGND ruin cross"', '"VHGND ruin dome"',
            '"VHGND Suricrasian cube x"', '"VHGND Suricrasian cube z"',
            "[VHGNDruinvalue] = 127", "? A = 131 -> VHGND Suricrasian cube marked;",
            "[VHGNDruinmarks]+;",
        ))
        and all(token in ground for token in (
            "VHGNDruins = 40000;", '"VHGND render ruins"', "[FI] = 512; => IntToF;",
            "A = [VHGNDshade]; A & 63; A + 64;",
        )),
        "the three historical systems carry all six ruin styles and the restored Cube",
    )
    check(
        all(token in ground for token in (
            "? A >= 0 -> VHGND traverse xlo ready;",
            "? A >= 0 -> VHGND traverse zlo ready;",
            "? A < 0 -> VHGND tile depth accepted;",
        ))
        and "? A '>= 0 -> VHGND traverse xlo ready;" not in ground,
        "signed terrain bounds retain the near ring and clamp map-edge traversal",
    )
    original_incoming_waves = section(
        original1,
        "// tracciamento onde in arrivo (onde del mare)",
        "// qui disegna tutto il landscape.",
    )
    original_outgoing_waves = section(
        original1,
        "// tracciamento onde in partenza (acqua smossa)",
        "// tracciamento dell'alone del \"sole\"",
    )
    waves = section(ground, '"VHGND waves init"', '"VHGND render animals"')
    check(
        all(token in original_incoming_waves for token in (
            "w = 10;", "wr[w] = 15E5;", "wr[w] += wd[w];",
            "drop_z = 18 * deg;", "polymap (xx, yy, zz, 4, 128);",
        ))
        and all(token in original_outgoing_waves for token in (
            "while (w >= 10)", "wr[w] += wd[w];", "wh[w] /= 1.025;",
            "if (hpoint (xx[0], zz[0]) == 0)",
        ))
        and all(token in original1 for token in (
            "waveblur = 1 + random (3);", "psmooth_64 (adapted, 160);",
        ))
        and "VHGNDwavedata = 175;" in ground
        and all(token in waves for token in (
            "[VHGNDwavei] = 0; [VHGNDwavelw] = 10;",
            "? A < 10 -> VHGND wave init incoming;",
            "? A < 25 -> VHGND wave init outgoing;",
            '"VHGND wave incoming"', "[VHGNDwaveradius] = 1500000;",
            '"VHGND wave spawn"', "A '% 10;",
            '"VHGND wave water point"', "[VHGNDwavewet] = 1;",
            "[VHGNDwaveseg] = 0;", "A '* 18;",
            "? A < 20 -> VHGND wave segment;",
            "A '* 40; A / 41;", "[C plus 3] = 0;",
            '"VHGND wave impact check"', "[VHGNDwavehits]+;",
            '"VHGND wave impact tick"', "[VHGNDimpactx] = A;",
            '"VHGND wave impact finish"', "[VHGNDblurp] = 2560;",
            "? A < 60480 -> VHGND wave blur pixel;",
            "A = [VHGNDdosim]; ? A = 0 -> VHGND wave next;",
        ))
        and "[VHGNDalpha] = [VHGalpha]; [VHGNDbeta] = [VHGbeta]; [VHGNDdosim] = [VHGdosim];" in game
        and "[VHGalpha] = A; => VHGND wave impact finish;" in game
        and waves.count("=> PG polymap;") == 1,
        "open oceans carry paced wind crests, wakes, and wet-lens wave impacts",
    )
    original_animals = section(original1, "void setup_animals ()", "void add_height")
    original_live_animal = section(original1, "void live_animal (int n)", "void add_height")
    animals = section(ground, '"VHGND render animals"', '"VHGND capsule"')
    check(
        all(token in original_animals for token in (
            "nearstar_p_type[ip_targetted] != 3", "case PLAINS:",
            "animals = LFS/5  + random (LFS-LFS/5)",
            "animals = LFS/2  + random (LFS-LFS/2)",
            "x = random (3);", "p = random (18);",
            "loadpv (mamm_base, mammal_ncc", "loadpv (mamm_result, mammal_ncc",
        ))
        and all(token in game for token in (
            "[PVh] = 2; [PVmodel] = MDMAM;", "[PVh] = 3; [PVmodel] = MDMAM;",
            "[PVcol] = 64; [PVreq] = 1;", "[PVcol] = 128; [PVreq] = 1;",
        ))
        and all(token in ground for token in (
            '"VHGND animals setup"', "? A != 3 -> VHGND animals setup done;",
            "VHGNDfaunatypes = 100;",
            "[VHGNDfaunabase] = 20; [VHGNDfaunarange] = 80;",
            "[VHGNDfaunabase] = 50; [VHGNDfaunarange] = 50;",
            "[VHGNDfaunabase] = 10; [VHGNDfaunarange] = 20;",
            "[VHGNDfaunabase] = 10; [VHGNDfaunarange] = 50;",
            "A = 3; => BrtlRandom; [VHGNDfaunatype] = A;",
            "A = 18; => BrtlRandom; [VHGNDfaunachance] = A;",
            '"VHGND fauna relocate nearby"',
            "? A > 150000 -> VHGND animal next;", "? A '<= 250000 -> VHGND animal ranged;",
            '"VHGND fauna relocation draw"', "A '* 1699; A '/ 32767;",
            "[VHGNDbirdquote] = 0; A = [VHGNDfaunatype]; ? A != 1 -> VHGND fauna relocate done;",
            "A = [VHGNDanidist]; ? A '<= 250000 -> VHGND animal ranged;",
            "A = [VHGNDdosim]; ? A = 0 -> VHGND animal ranged;",
            "A = [VHGNDdosim]; ? A = 0 -> VHGND bird ranged;",
            '"VHGND mammal behavior"', "[SUfmask] = 31; => SU frnd; C + 3;",
            "[VHGNDanitickbase] = [VHGNDtick];",
            "A '* 800; A '/ 32767; [VHGNDanitendency] = A;",
            "A '* 350; A '/ 32767; A + 350;",
            "A '* 200; A '/ 32767; A + 200;",
            "A '* 100; A '/ 32767; A + 400;",
            '=> VHGND mammal motion vector;', '=> VHGND mammal cosine motion;',
        ))
        and all(token in original_live_animal for token in (
            "update_ratio = fast_random (31) + 3;",
            "tendence_to_stop = fast_flandom () * 0.8;",
            "velocity = 350 + fast_flandom() * 350;",
            "velocity = 200 + fast_flandom() * 200;",
            "velocity = 400 + fast_flandom() * 100;",
            "ani_speed[n] += 3 * reaction * dx;",
            "ani_pitch[n] += 2 * reaction * dz;",
            "ani_x[n] -= ani_speed[n] * sin (deg * ani_pitch[n]);",
            "ani_z[n] -= ani_speed[n] * cos (deg * ani_pitch[n]);",
            "ani_x[n] = pos_x + 100000 * fast_flandom() - 100000 * fast_flandom();",
            "ani_z[n] = pos_z + 100000 * fast_flandom() - 100000 * fast_flandom();",
            "ani_quote[n] = 25000 * fast_flandom();",
            "dy = 1 - (ani_quote[n] * reaction); if (dy < 0) dy = 0;",
            "if (ay < 0 || sctype != OCEAN)",
            "0, +45*dy, +75*dy, bird_wing1",
            "0, -45*dy, -75*dy, bird_wing2",
            "stick3d (ax, ay, az, pos_x,      pos_y - 50, pos_z);",
            "stick3d (ax, ay, az, pos_x - 50, pos_y - 50, pos_z);",
            "stick3d (ax, ay, az, pos_x + 50, pos_y - 50, pos_z);",
            "stick3d (ax, ay, az, pos_x,      pos_y - 50, pos_z + 50);",
            "stick3d (ax, ay, az, pos_x,      pos_y - 50, pos_z - 50);",
            "if (ani_lcount[n] < -1) {",
            "step += 2 * ani_lcount[n];",
            "ani_lcount[n]++;",
            "if (ay > -10 && sctype == OCEAN)",
            "modpv (mamm_result, -1, -1, 1, 0.7, 1, 0, 0, 0, NULL);",
            "modpv (mamm_result, -1, -1, 1, 0.0, 1, 0, 0, 0, mamm_legs);",
            "period = fabs (fsecs - 0.5);",
            "incl /= an_incl_prec;", "if (incl < -1) incl = -1;",
            "if (incl > +1) incl = +1;",
            "incl = ((double)180 * atan(incl)) / M_PI;",
            "fast_srand (4*n);", "if (fast_random(1))",
            "period = 45;", "period = 60;", "period = 22;",
            "period /= ani_scale[n];",
            "modpv (mamm_result, -1, -1, 1, 1, 1, 15, 0, 50 * period, NULL);",
        ))
        and "A '* 7919; A + [VHGNDseed];" not in ground
        and "A = [VHGNDtick]; A / 18; A '* 18; [VHGNDanitickbase] = A;" not in ground
        and all(token in animals for token in (
            "[PVh] = 3; [PVk] = 2; => SP copypv;", "=> SP modpv;",
            "A '* 10; A + VHGNDanidata;", "[VHGNDanimtype] = [C plus 4];",
            "[VHGNDaniscale] = [C plus 6];",
            "[MOpid] = 16; [MOvid] = 2;", "=> VHGND mamm rear list;",
            "[DWmode] = 1; [DWuds] = [VHGNDdepthsort];",
            "[PGtexf] = 5; [SPsrc] = 1;", "=> SP drawpv;", "=> VH join mode1;",
        ))
        and all(token in ground for token in (
            '"VHGND animal distance"', "=> FSqrt; => FToIntNear;",
            "? A '>= 75000 -> VHGND animal draw sort ready;",
            '"VHGND animal land shape"', '"VHGND mammal half phase"',
            "[MOxs] = 3F800000h; [MOys] = 3F333333h; [MOzs] = 3F800000h;",
            "=> VHGND mamm legs list; [MOlist] = pvlst; [PVh] = 3; => SP modpv;",
            "A '/ 1200; [VHGNDswimphase] = A;",
            "A = [VHGNDaniindex]; A '* 4; => SU fast srand;",
            "[SUfmask] = 1; => SU fast raw; A = [SUfval]; ? A = 0 -> VHGND animal animated;",
            "A = [VHGNDmammphase]; A '/ 250; A - 60;",
            "A '* [VHGNDmammphase]; A '* 1000;",
            "A = [VHGNDaniperiod]; A '* 50;", "A = [VHGNDaniperiod]; A '* 100;",
            '"VHGND animal incl clamped"', "[FB0] = 0; [FB1] = 40490000h; => FAtan2;",
            "[FB0] = 0; [FB1] = 40668000h; => FMul;",
            "[FB0] = 54442D18h; [FB1] = 400921FBh; => FQuo; => FToIntNear;",
            '"VHGND mamm rear list"', "[A plus 0] = 0C007h;",
            '"VHGND mamm tail list"', "[A plus 4] = 7030h;",
            '"VHGND mamm legs list"', "[A plus 0] = 0F000h;",
            "[A plus 13] = 0F00Bh; [A plus 14] = 0FFFh;",
        )),
        "habitable land carries source-model feline, rabbit, and kangaroo deformation",
    )
    birds = section(ground, '"VHGND render birds"', '"VHGND capsule"')
    check(
        all(token in original_animals for token in (
            "loadpv (bird_base, birdy_ncc", "loadpv (bird_result, birdy_ncc",
        ))
        and all(token in game for token in (
            "[PVh] = 4; [PVmodel] = MDBRD;", "[PVh] = 5; [PVmodel] = MDBRD;",
        ))
        and all(token in birds for token in (
            "[PVh] = 5; [PVk] = 4; => SP copypv;",
            "A '* 12; A + VHGNDbirddata;", "[VHGNDbirdlcount] = [C plus 6];",
            "[VHGNDaniscale] = [C plus 7];",
            '"VHGND bird near 3000"', '"VHGND bird catch range"',
            "[VHGNDplayerstep]", "? A '<= 250", "? A '<= 100",
            "A = 250; A '/ [VHGNDtmp]; [VHGNDanitargetspeed] = A;",
            "[MOpid] = 1; [MOvid] = 0;", "=> VHGND bird wing one list;",
            "=> VHGND bird wing two list;", "=> VHGND bird legs list;",
            "[VHGNDgroundbirds]+;", "[VHGNDcaptures]+;",
            "=> VHGND bird flap interpolate;",
            '"VHGND bird ground fold ready"',
            "A = [VHGNDsctype]; ? A != 1 -> VHGND bird ground pose;",
            "A = [VHGNDroy]; A - [VHGNDbirdquote]; ? A >= 0 -> VHGND bird flight pose;",
            "A = [VHGNDbirdquote]; A '* 500; A '/ [VHGNDaniscale];",
            "C = 1000; C - A; ? C >= 0 -> VHGND bird ground fold ready; C = 0;",
            "A = C; A '* 45; [VHGNDaniperiod] = A;",
            "C '* 75; [VHGNDbirdflap] = C;",
            "A = [VHGNDcamx]; A - 50;", "A = [VHGNDcamx]; A + 50;",
            "A = [VHGNDcamz]; A + 50;", "A = [VHGNDcamz]; A - 50;",
            "A = [VHGNDbirdlcount]; A + A; C = [VHGsurfstep]; C + A; [VHGsurfstep] = C;",
            "? A '>= 12500 -> VHGND bird draw mode ready;",
            "A = [VHGNDaniindex]; A & 1; A + 1; [VHGNDdrawmode] = A;",
            "[DWmode] = [VHGNDdrawmode]; [DWuds] = [VHGNDdepthsort];",
            "[VHRiters] = 3; => VH join mode2;", "=> VH join mode1;", "=> VH join mode0;",
            "=> SP drawpv;", "=> VH join mode0;",
        ))
        and all(token in ground for token in (
            "VHGNDSTALK = 80;", "VHGNDplayerstep = 0;",
            '"VHGND restore captures"', '"VHGND restore capture one"',
            "[VHGNDcaptures] = [VHGNDbirds];", "[C plus 6] = A;",
            '"VHGND bird behavior"', "C / 10; A + C; => SU fast srand;",
            "A = [VHGNDanimtick]; A '% 6; C = 3; C - A;",
            "A = [VHGNDanimtick]; A '% 20; C = 10; C - A;",
            "[VHGNDanitargetspeed] = 800;", "[VHGNDanitargetspeed] = 400;",
            "A '* 1000; A '/ 32767; A + 1500;",
            "A = [VHGNDanidir]; => VHGND mammal cosine motion;",
            '"VHGND bird legs list"', "[A plus 0] = 4012h;",
            '"VHGND bird wing one list"', "[A plus 0] = 7000h;",
            '"VHGND bird wing two list"', "[A plus 0] = 7002h;",
            "C '* 15; [VHGNDbirdflap] = C;",
        ))
        and all(token in original_live_animal for token in (
            "if (quote >= 1500)", "velocity = 800;",
            "if (quote > 750)", "velocity = 400;", "quote   *= 0.5;",
            "if (quote > 250)", "velocity = 0;", "quote    = 0;",
            "fast_srand (n + (tick / 10));", "tick = 18 * secs;",
            "fabs(10 - (tick % 20))", "fabs(3 - (tick % 6))",
            "if (fast_random(7) == 3)", "quote = 1500 + 1000 * fast_flandom();",
            "ani_quote[n] += 1 * reaction * dy;",
            "animal_distance = sqrt (dx*dx + dy*dy + dz*dz);",
            "if (animal_distance <  75000) perform_depth_sort = 1;",
            "if (animal_distance <  12500) texture_skin_map   = 1 + (n % 2);",
            "drawpv (bird_result, texture_skin_map, 3, ax, ay",
            "drawpv (mamm_result, 1, 0, ax, ay, az, perform_depth_sort);",
        ))
        and "A = [VHGNDanimtick]; A + [VHGNDaniphase];" not in ground
        and all(token in (ROOT / "work" / "vhjoin.txt").read_text(encoding="utf-8") for token in (
            '"VH join mode1"', "[SPtinta] = [C plus 5];", "=> PG polymap;",
        ))
        and all(token in game for token in (
            "[KEY CONTROL]", "[VHGstepv] = VHGNDSTALK;",
            "A = [VHGsurfstep]; A + [VHGstepv]; [VHGsurfstep] = A;",
            "CTRL:STALK", "RMB/ARROWS:LOOK / WASD / 0-9:CRUISE",
            "[VHGNDcaptures] = [VHSVcaptures];", "=> VHGND restore captures;",
        )),
        "habitable birds react to speed and support discoverable close stalking/capture",
    )
    check(
        all(token in panels for token in (
            '"VHP system orbits"', "? A <= 24 -> VHP orbit segment;",
            "A = [VHPcamx]; ? A < 2000 -> VHP system orbit detail done;",
            '"VHP moon dots"', "[VHPsysn] = [nsnop];",
            '"VHP orbit score"', "E = nsporbray;", "E = nsporideg;",
            "A & 7FFh;", "E = nspowner;", "E = VHPbodyy;", "E = VHPbodyz;",
            "[VHPdotsize] = 45; [VHScolor] = 63;",
        ))
        and "[VHPradius] = 70; [VHPangle] = 151;" not in panels
        and "A = [VHGdosim]; ? A = 0 -> VHG frame count done; [VHGframe]+;" in game
        and "[VHPsysphase] = [VHGframe];" in game
        and "[SPval] = [VHScolor];" in stick,
        "planetary console draws retained system orbits, orientations, selection, and owned moons",
    )
    check(
        all(token in game for token in (
            "? A = 91 -> VHG select previous body;",
            "? A = 93 -> VHG select next body;",
            '"VHG select previous body"', '"VHG select next body"',
            "A = [nsnob]; A - 1;", "? A '< [nsnob] -> VHG next body ready; A = 0;",
            "A = [VHGplanet]; ? A '< [nsnob] -> VHG load target valid;",
        )),
        "bracket controls cycle and persist every generated planet or moon",
    )
    check(
        all(token in gui for token in (
            "A '* 5; A '/ 8", "A '* 8; A '/ 5",
            '"VHGUI 1x row"', '"VHGUI scaled"',
        )),
        "presenter has a fast 1x path and an 8:5 aspect-fit path",
    )
    check(
        "=> FB expand;" not in gui_loop
        and "C + nw; C + RADPT" in gui
        and "D + VHGUIframe" in gui
        and "A + VHGUIframe" in gui
        and "D + Backdrop Layer" in gui
        and "E + Primary Display" not in gui
        and "[D] = A" in gui,
        "GUI presenter composes one logical RGB page and writes only the authoritative backdrop",
    )
    eye = section(ground, '"VHGND eye height"', '"VHGND render"')
    check(
        "VHGNDQIDHI" in eye and eye.count("=> F32Narrow; => FStoreF32;") == 4
        and "A / VHGNDTS" not in eye,
        "terrain eye height follows the rendered float triangles without integer loss",
    )
    check(
        aspect_fit(320, 200) == (320, 200, 0, 0)
        and aspect_fit(640, 400) == (640, 400, 0, 0)
        and aspect_fit(800, 600) == (800, 500, 0, 50)
        and aspect_fit(600, 800) == (600, 375, 0, 212),
        "independent aspect-fit examples preserve 8:5 with centered bars",
    )
    check(
        "vhvsintab = 360; vhvcostab = 360; vhvtrigvalid = 360;" in view
        and '"VH view init"' in view
        and "A = vhvtrigvalid; B = 360; C = 0;" in view
        and "=> PGF constants; => VH view init;" in game
        and '"VHV trig build"' in view
        and "A % 360; ? A >= 0 -> VHV angle normalized;" in view
        and "A = [VHGbeta]; A % 360; ? A >= 0 -> VHG pod view ready;" in game
        and "A = [VHGCwindangle]; A + 8; A / 16;" in capsule_physics
        and "A = [FI]; A % 360; ? A >= 0 -> VHGND orbital phase ready;" in ground
        and "A = [SUti]; A % 360;" in ground
        and "A + [VHGNDrotation]; A % 360;" in ground
        and "A = [VHGNDbeta]; A + 51; A % 360;" in ground
        and "A '% 360; ? A '>= 0 -> VHV angle normalized;" not in view,
        "camera trig cache is initialized before exact integral-angle reuse",
    )

    print("RESULT PASS - lean vhgame correctness checks")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, OSError) as exc:
        print(f"RESULT FAIL - {exc}")
        raise SystemExit(1)
