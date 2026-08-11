"""Lean integration checks for the live Stardrifter game.

This deliberately stays small: it pins the interactive regressions found
during playtesting (roof-lift timing, the landed-coordinate escape, and GUI
repaint behavior) plus the original 18.2 Hz synchronizer.  It does not rebuild
historical wave oracles or run a mutation matrix.
"""

from __future__ import annotations

import os
import re
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
IGUI = ROOT / "work" / "igui.txt"
STICK = ROOT / "work" / "vhstick.txt"
SAVE = ROOT / "work" / "vhsave.txt"
AUDIO = ROOT / "work" / "vhaudio.txt"
FLARE = ROOT / "work" / "vhflare.txt"
STAR = ROOT / "work" / "vhstar.txt"
REFERENCE_ROOT = Path(os.environ.get(
    "NOCTIS_REFERENCE_ROOT",
    r"C:\programmieren\noctis\niv-plus\source",
))
ORIGINAL = REFERENCE_ROOT / "NOCTIS.CPP"
ORIGINAL0 = REFERENCE_ROOT / "NOCTIS-0.CPP"
ORIGINAL1 = REFERENCE_ROOT / "NOCTIS-1.CPP"


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
    igui = IGUI.read_text(encoding="utf-8")
    stick = STICK.read_text(encoding="utf-8")
    save = SAVE.read_text(encoding="utf-8")
    audio = AUDIO.read_text(encoding="utf-8")
    flare = FLARE.read_text(encoding="utf-8")
    star = STAR.read_text(encoding="utf-8")
    original = ORIGINAL.read_text(encoding="latin-1")
    original0 = ORIGINAL0.read_text(encoding="latin-1")
    original1 = ORIGINAL1.read_text(encoding="latin-1")

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
    shade = section(ground, '"VHGND tile shade"', '"VHGND vload"')
    check(
        "[SUfmask] = 7; => SU frnd;" in shade
        and "A = [VHGNDh1]; A + [VHGNDseed]; => SU fast srand;" in shade
        and "=> FAdd; => FSqrt; => FToIntChop;" in shade
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
        and "=> VH polycupola;" not in settled_capsule
        and moving_capsule.count("=> VH polycupola; => VH cupola grid;") == 2
        and "A + 1415" in capsule and "A + 385" in capsule and "A + 900" in capsule
        and capsule.count("=> VH stick3d;") == 3
        and "A # 80000000h" in cupola
        and '"VHC capsule view"' in cupola
        and "A = 500; A - [FI]" in cupola
        and "A < 2; A * [VHCyor]" in cupola,
        "landed view keeps both capsule support grids, detailed moving panels, and beacon",
    )
    check(
        all(token in original1 for token in (
            "pos_y = hpoint (pos_x, pos_z) - 3.2E5;",
            "gravity = - 0.32 * gravity;",
            "gravity < 250", "compdist < 512 || bounces > 10",
            "opencapcount > 32", "opencapcount > 250",
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
            "? A '<= 250 -> VHGC ascent done;", "=> VHG return ship;",
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
        and "[VHGCsubsteps] = 32;" in capsule_physics,
        "landing validates the body, reports rejection, and batches descent visibly",
    )
    post = section(ground, '"VHGND post surface"', '"VHGND flandom"')
    objects = section(ground, '"VHGND tile objects"', '"VHGND veget"')
    rocks = section(ground, '"VHGND rock"', '"VHGND rock height"')
    check(
        '"VHGND felisian line"' in post
        and "A & 0FCh; A | [VHGNDoval]" in post
        and "A = [MBval]; A & 3; [VHGNDocount] = A;" in objects
        and "[SUfmask] = [VHGNDrockdensity]" in rocks
        and rocks.count("=> PG poly3d;") == 3,
        "source post-surface counts drive deterministic nearby tetrahedral rocks",
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
        )),
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
            "A + [VHTphase]; A % 360; [VHTphase] = A;",
        ))
        and "[VHTphase] = [VHGframe];" not in game
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
        and "[VHGnoticeptr] = VHGreturnfartext;" in surface_input,
        "surface return requires the visible capsule and explains an out-of-range refusal",
    )

    check(
        "INITIAL WIDTH = 642; INITIAL HEIGHT = 426;" in game
        and "defstyle;" in game
        and "[Work Area Manager] = service VHG repaint;" in game,
        "iGUI chrome opens with an exact 2x 640x400 initial work area",
    )
    check(
        "[Previous display height] = [Display Height]; [Fold Is Active] = NO;" in game
        and game.index("[Fold Is Active] = NO;") < game.index("=> Enter Integrated GUI;"),
        "the first client frame starts unfolded and later fold/unfold restores the live height",
    )
    run = section(game, '"VHG run"', '"service VHG repaint"')
    close_action = section(igui, '"service Exit Button Action"', '"Update Slep Button Appearence"')
    check(
        run.index("=> Enter Integrated GUI;") < run.index("=> VHSV save;") < run.index("=> VHA stop;")
        and "[Quit Now] = YES;" in close_action
        and '"service KD Quit hook"' in igui
        and "? [KEY ALTERNATE] = OFF" in igui
        and "A = [KEY F4]; ? A = OFF -> VHG GUI loop frame;" in game
        and "A = [KEY ALTERNATE]; ? A = OFF -> VHG GUI loop frame;" in game
        and "[VHGesc] = 1; [Quit Now] = YES; -> VHG GUI loop done;" in game,
        "red close button and Alt+F4 return through checkpoint/audio cleanup",
    )
    gui_loop = section(game, '"service VHG GUI loop"', '"service VHG GUI sleepy"')
    check(
        "[Source Layer] = Backdrop Layer; [Destination Layer] = Primary Display; => Copy L2L;" in gui_loop
        and "[Display Command] = RETRACE; [Display Live Region] = WHOLE DISPLAY; isocall;" in gui_loop
        and "=> Update Area;" not in gui_loop
        and "[Do Not Retrace Arrow Region] = YES;" not in gui_loop
        and "=> VHG copy page;" in game,
        "GUI explicitly publishes the complete 3-D backdrop before the outer cursor pass",
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
            "VHGhelpmenu = { F10:GAME-MENU / ARROWS+ENTER };",
            "[Text Display Origin] = VHGUIframe;", "[VHGhelpline] = VHGhelpfuel;",
            "[VHGhelpline] = VHGhelpview;", "=> VHG help draw line;",
            "[Rectangle Gradients] = vector Standard Black Gradients;", "[Ink] = FFFFFFh;",
            "[Text Effect] = service FX Raw;",
        ))
        and all(token in original for token in (
            "if (c==0x3B) { // F1 - help & about", "ShowAboutPage",
            "SHORTCUT KEYS (WHEN IN SPACE):",
        )),
        "question-mark/F9 restore Noctis help with a repaint-safe resizable control card",
    )
    info_overlay = section(game, '"VHG info overlay"', '"VHG help overlay"')
    info_key = section(game, '"VHG info key"', '"VHG help key"')
    check(
        all(token in original for token in (
            'command (2, "remote target data");',
            'command (3, "local target data");',
            'command (4, "environment data");',
            'case 1: // remote target data',
            'case 2: // local target data',
            'case 3: // environment data',
        ))
        and all(token in game for token in (
            'VHGinfotitle1 = { REMOTE TARGET DATA };',
            'VHGinfotitle2 = { LOCAL TARGET DATA };',
            'VHGinfotitle3 = { EXTERNAL ENVIRONMENT };',
            'VHGhelpview = { F4:FPS F5:60HZ F8:MUSIC I:DATA };',
        ))
        and all(token in info_overlay for token in (
            '[Rectangle Bounds] = vector VHGUIregion;',
            '[Rectangle Target Layer] = VHGUIframe;',
            '"VHG info remote"', '"VHG info page local"',
            '"VHG info environment"', '"VHG info format common"',
            '"VHG info format local"', '"VHG info name copy"',
            '[VHGinfonamesrc] = vhcatstarlabel;',
            '[VHGinfonamesrc] = vhcatbodylabel;',
            'E = nspowner;', 'E = nspmoonid;', 'E = nspray;',
            '[VHGinfoline] = VHGsurfacetext;',
            '[VHGinfoline] = [VHGfcsline];',
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
            '[VHGinfo]+;', '? A <= 3 -> VHG info key selected;',
            '[VHGinfo] = 0;',
        ))
        and game.count("=> VHG info overlay;") == 2
        and "A = [VHGinfo]; ? A != 0 -> VHG input done;" in game,
        "I cycles original-shaped remote, local, and environment data pages without moving the player",
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
            flare, '"VH halogen flare"', '"VH surface flare"'
        )
        and "-50000, 2, hud_closed, 0, 1, 1" in section(
            original, "void alogena ()", "/* Quadranti"
        )
        and all(token in game for token in (
            '[VHGstarclass] = [VHTclass];', '? A = 8 -> VHG star palette inner8;',
            '[FBSHfirst] = 64; [FBSHn] = 24;', '[FBSHfirst] = 88; [FBSHn] = 16;',
            '[FBSHfirst] = 104; [FBSHn] = 24;',
            '[PVself] = 1; [PVfirst] = 64; [PVn] = 64;',
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
        and '[vhsvbuf plus 38] = [VHGilight];' in save,
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
            '"VHG surface telemetry update"', '"VHG surface smooth field"',
            "D = VHGsurfgravdisp; C = 4;", "D = VHGsurftempdisp; C = 20;",
            "D = VHGsurfpressdisp; C = 50;", "D = VHGsurfpulsedisp; C = 100;",
        ))
        and "=> VHG text both;" not in surface_overlay
        and "=> VHG UTC timestamp; => VHG visor advance; => VHG surface telemetry update;" in game
        and game.count("=> VHG surface telemetry overlay;") == 2
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
            '"VHG surface vertical"', "A = 0; A - 500; [VHGsurfvy] = A;",
            "E = KEY A; E + 64;", "A = [VHGsurfvy]; A - 50;",
            "A = [VHGsurfvy]; A + [VHGsurfaccel];",
            "[VHGy] = [VHGsurfground]; [VHGsurfvy] = 0;",
        ))
        and "A = [VHGsurfgravm]; A '* 2000; A '/ 38260;" in surface_telemetry
        and "VHGhelpjump = { SURFACE:J JUMP / HOLD SPACE JETPACK };" in game
        and "[VHGhelpline] = VHGhelpjump;" in game
        and jump_ticks > 1 and jump_apex < jump_ground
        and jet_ticks > jump_ticks and jet_apex < jump_apex and jet_ground == jump_ground,
        "surface jump and hold-to-thrust jetpack follow body gravity and land cleanly",
    )
    check(
        all(token in game for token in (
            '"VHG fast key"', "[KEY F5]", '"VHG cadence"',
            "VHGSIMADD = 18206", '"VHG timing step"',
        ))
        and "VHGfast = 0; VHGfastheld = 0; VHGsimacc = 0;" in game
        and "A = [VHGfast]; ? A != 0 -> VHG timing fast;" in game
        and "=> TK step;" in section(game, '"VHG timing step"', '"VHG timing rebase"')
        and "[TKdeadline] = [TKnow]; [TKacc] = 0;" in game
        and "[VHGNDdosim] = [VHGdosim]; => VHGND render;" in game
        and ground.count("A = [VHGNDdosim]; ? A = 0") >= 3,
        "original presentation is default and F5 opts into 60 FPS without changing simulation cadence",
    )
    check(
        all(token in game for token in (
            '"VHG interpolation advance"', '"VHG interpolation apply"',
            '"VHG interpolation restore"', '"VHG interpolation snapshot"',
            '=> VHG interpolation apply; => VHG render; => VHGND surrounding frame; => VHG interpolation restore;',
            'A = [VHGmode]; ? A = 0 -> VHG interpolation apply eligible;',
            'A = [VHGlanded]; ? A = 0 -> VHG interpolation apply done;',
            'A = [VHGdosim]; ? A != 0 -> VHG interpolation advance finish;',
            "A = [VHGinterpdelta]; A '* [VHGinterpacc]; A / VHGSIMDEN;",
            'A = [VHGx]; A - [VHGinterprenderx]; [VHGinterpeffectx] = A;',
            'A = [VHGz]; A - [VHGinterprenderz]; [VHGinterpeffectz] = A;',
            'A = [VHGalpha]; A - [VHGinterprenderalpha]; [VHGinterpeffectalpha] = A;',
            '[VHGinterpok] = 0; => VHG load success notice;',
        ))
        and '[VHGinterpok] = 0;' in CAPSULE.read_text(encoding="utf-8")
        and [signed_lerp(0, 80, phase) for phase in (0, 18206, 36412, 54618, 60000)]
        == [0, 24, 48, 72, 80]
        and [signed_lerp(0, -80, phase) for phase in (0, 18206, 36412, 54618, 60000)]
        == [0, -24, -48, -72, -80],
        "60-Hz ship and settled-surface presentation interpolate without mutating simulation state",
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
        ))
        and all(token in save for token in (
            "[VHSVok] = 0;", "[File Command] = SET SIZE; [File Size] = 192;",
            "[File Command] = TEST;", "? [File Size] != 192 -> VHSV save done;",
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
            "[VHGdev] = 0; [VHGfcsopen] = 0; [VHGinfo] = 0;",
        )),
        "ordinary play uses the indexed/source HUD and X clears onboard overlays",
    )
    check(
        all(token in game for token in (
            '"VHG next star"', '"VHG flight retarget"', '"VHG parse coordinate"',
            "A '% [VHScount]", "=> VHG target world; => VHG flight retarget;",
            "[VHGnoticeptr] = VHGunknowntext; [VHGnoticeframes] = 75; => VHG command;",
        ))
        and all(token in save for token in (
            "VHSVVERSION = 13;", "[vhsvbuf plus 24] = [VHTtx];",
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
            '"VHG console overlay"', "VHGconsoletitle = { GOES COMMAND CONSOLE };",
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
            "[vhcatraw] = VHCATHDRBYTES;", "A = [vhcatraw]; ? A != [VHCATbytes]",
            '"VHCAT write record ready"', "[Block Size] = VHCATHDRBYTES;",
        )),
        "GOES consumes one character per physical press and creates a valid empty starmap",
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
            '"VH GOES output line"', "vhpout = 672;", '"VH GOES output window"',
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
        ))
        and "[MgPwr] = 30000" not in section(game, '"VHG flight retarget"', '"VHG flight step"')
        and "[MgPwr] = 20000; [MgCharge] = 3;" in section(game, '"VHG flight init"', '"VHG target world"')
        and all(token in original for token in (
            "if (lithium_collector)", "ir = random (50);", "ir -= 125 / dsd;",
            "ir -= 25 / dsd;", "if (charge < 120)", "charge++;",
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
        "live and closed-game lithium collection are source-shaped, visible, and persistent",
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
        ))
        and all(token in original for token in (
            "if (pwr <= 15000 && !charge)", "if (!stz&&charge<3) charge = 3;",
            "other_vehicle_at ((stz + 16000) * cos (secs / 10)",
        )),
        "depleted ships receive the original three-unit reserve from a visible rescue fly-by",
    )
    check(
        all(token in save for token in (
            "? A = 144 -> VHSV load size ok; ? A = 152 -> VHSV load size ok;",
            "? A = 156 -> VHSV load size ok; ? A = 160 -> VHSV load size ok;",
            "? A = 168 -> VHSV load size ok; ? A = 180 -> VHSV load size ok;",
            "? A = 188 -> VHSV load size ok; ? A != 192 -> VHSV load done;",
            '"VHSV load version two"', '"VHSV load version three"', '"VHSV load version four"',
            '"VHSV load version five"', '"VHSV load version six"', '"VHSV load version seven"',
            '"VHSV load version eight"', '"VHSV load version nine"', '"VHSV load version ten"',
            '"VHSV load version eleven"', '"VHSV load version twelve"',
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
            "[Block Pointer] = vhsvbuf; [Block Size] = 192; isocall;",
            "[vhsvbuf plus 47] = C;", "A = [VHSVsize]; ? A != 192 -> VHSV load graphics done;",
            "A - 1; [VHGlensmode] = A;", "[VHGdrawhud] = A;", "[VHGseamless] = A;",
            "A = 1; A - [VHGhudclosed]; A '* 16;", "[VHGhudclosed] = 0; [VHGhudcount] = 0;",
            "? A < MINIMUM WIDTH -> VHSV load done;", "? A > MAXIMUM HEIGHT -> VHSV load done;",
            "[VHSVmusic] = [VHAwanted];", "[VHAwanted] = [VHSVmusic];",
        ))
        and all(token in game for token in (
            '"VHG load original cadence"', "[VHGNDcaptures] = [VHSVcaptures];",
            '"VHG load stored capsule"', "[VHGNDdropx] = [VHGx]; [VHGNDdropz] = [VHGz];",
            "[VHGNDcamx] = [VHGx]; [VHGNDcamz] = [VHGz]; => VHGND eye height;",
            "[VHGNDdropx] = [VHSVdropx]; [VHGNDdropy] = [VHSVdropy];",
            "[VHGNDdropz] = [VHSVdropz];",
            '"VHG restore window"', "[New Display Width] = [VHSVwindoww];",
            "=> Resize Display;", "=> VHG restore window;", "=> VHA apply;",
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
        "version-13 checkpoints retain visual settings and safely migrate v1-v12 progress",
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
    check(
        all(token in tree for token in (
            '"VHGND tree limb"', '"VHGND tree leaves"',
            "[VHGNDtreebranches] = 3;", "[VHGNDtreeside] = 0;",
            "[PJnrv] = 4; => PG poly3d;", "[PJnrv] = 3; => PG poly3d;",
            "C + 192; [VHGNDtreecol] = C;", "C + 64; [VHGNDtreecol] = C;",
        ))
        and "crossed trunk" not in tree
        and "crossed leafy crown" not in tree,
        "trees use bounded source-shaped tapered limbs and terminal leaf fans",
    )
    check(
        all(token in ground for token in (
            '"VHGND generate desert"', '"VHGND generate icy"',
            '"VHGND icy snowfield"', '"VHGND icy bare"',
            '"VHGND icy hills"', '"VHGND icy bergs"',
            '"VHGND texture random"',
            "[VHGNDtscale] = 128; [VHGNDtexn] = 32;",
            "[VHGNDrockscale] = 0; [VHGNDrockpeak] = 0; [VHGNDrockdensity] = 0;",
            "C + 200; [VHGNDrockscale] = C;",
            "C + 150; [VHGNDrockpeak] = C;",
        )),
        "desert and icy habitable worlds have distinct source-shaped terrain and textures",
    )
    check(
        all(token in ground for token in (
            '"VHGND generate type1"', '"VHGND generate type5"',
            '"VHGND generate type7"', "? A = 1 -> VHGND generate type1;",
            "? A = 5 -> VHGND generate type5;", "? A = 7 -> VHGND generate type7;",
            '"VHGND type1 craters"', '"VHGND type5 craters"',
            '"VHGND type7 surface line loop"',
        ))
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
        ))
        and all(token in ruins for token in (
            '"VHGND ruins Balas"', '"VHGND ruins Fenia"', '"VHGND ruins Ylas"',
            '"VHGND ruin tower"', '"VHGND ruin walls"', '"VHGND ruin plaza"',
            '"VHGND ruin palace"', '"VHGND ruin cross"', '"VHGND ruin dome"',
            "[VHGNDruinmarks]+;",
        ))
        and all(token in ground for token in (
            "VHGNDruins = 40000;", '"VHGND render ruins"', "[FI] = 512; => IntToF;",
            "A = [VHGNDshade]; A & 63; A + 64;",
        )),
        "the three historical systems carry all six terrain-built ruin styles",
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
    animals = section(ground, '"VHGND render animals"', '"VHGND capsule"')
    check(
        all(token in original_animals for token in (
            "nearstar_p_type[ip_targetted] != 3", "case PLAINS:",
            "loadpv (mamm_base, mammal_ncc", "loadpv (mamm_result, mammal_ncc",
        ))
        and all(token in game for token in (
            "[PVh] = 2; [PVmodel] = MDMAM;", "[PVh] = 3; [PVmodel] = MDMAM;",
            "[PVcol] = 64; [PVreq] = 1;", "[PVcol] = 128; [PVreq] = 1;",
        ))
        and all(token in ground for token in (
            '"VHGND animals setup"', "? A = 1 -> VHGND animals setup done;",
            "? A > 150000 -> VHGND animal next;", "? A '<= 250000 -> VHGND animal ranged;",
        ))
        and all(token in animals for token in (
            "[PVh] = 3; [PVk] = 2; => SP copypv;", "=> SP modpv;",
            "A '* 6; A + VHGNDanidata;", "[VHGNDanimtype] = [C plus 4];",
            "[MOpid] = 16; [MOvid] = 2;", "=> VHGND mamm rear list;",
            "[DWmode] = 0; [DWuds] = 1;", "=> SP drawpv;", "=> VH join mode0;",
        ))
        and all(token in ground for token in (
            '"VHGND mamm rear list"', "[A plus 0] = 0C007h;",
            '"VHGND mamm tail list"', "[A plus 4] = 7030h;",
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
            "A '* 7; A + VHGNDbirddata;", "[VHGNDbirdlcount] = [C plus 6];",
            '"VHGND bird near 3000"', '"VHGND bird catch range"',
            "[VHGNDplayerstep]", "? A '<= 250", "? A '<= 100",
            "? A '>= 500 -> VHGND bird habits;",
            '"VHGND bird reaction speed"', "A = 250; A '/ [VHGNDtmp];",
            "[MOpid] = 1; [MOvid] = 0;", "=> VHGND bird wing one list;",
            "=> VHGND bird wing two list;", "=> VHGND bird legs list;",
            "[VHGNDgroundbirds]+;", "[VHGNDcaptures]+;",
            "C '* 15; [VHGNDbirdflap] = C;",
            "=> SP drawpv;", "=> VH join mode0;",
        ))
        and all(token in ground for token in (
            "VHGNDSTALK = 80;", "VHGNDplayerstep = 0;",
            '"VHGND restore captures"', '"VHGND restore capture one"',
            "[VHGNDcaptures] = [VHGNDbirds];", "[C plus 6] = A;",
            '"VHGND bird legs list"', "[A plus 0] = 4012h;",
            '"VHGND bird wing one list"', "[A plus 0] = 7000h;",
            '"VHGND bird wing two list"', "[A plus 0] = 7002h;",
        ))
        and all(token in game for token in (
            "[KEY CONTROL]", "[VHGstepv] = VHGNDSTALK;",
            "[VHGNDplayerstep] = [VHGstepv];",
            "CTRL:STALK", "RMB/ARROWS:LOOK / WASD / CTRL:STALK",
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
