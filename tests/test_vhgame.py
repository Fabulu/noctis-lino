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
PGTEX = ROOT / "work" / "pgtex.txt"
PGMEM = ROOT / "work" / "pgmem.txt"
PGFP = ROOT / "work" / "pgfp.txt"
PGPROJ = ROOT / "work" / "pgproj.txt"
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
WINDOWS_HIDDEN_PROCESS = ROOT / "tools" / "windows_hidden_process.py"
CAPTURE_SCRIPT = ROOT / "tools" / "capture_noctis_scenes.ps1"


def section(text: str, start: str, end: str) -> str:
    try:
        return text.split(start, 1)[1].split(end, 1)[0]
    except IndexError as exc:
        raise AssertionError(f"missing section boundary: {start!r} / {end!r}") from exc


def contains_in_order(text: str, snippets: tuple[str, ...]) -> bool:
    cursor = 0
    for snippet in snippets:
        cursor = text.find(snippet, cursor)
        if cursor < 0:
            return False
        cursor += len(snippet)
    return True


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


def faithful_tiles(cam_x: int, cam_z: int, direction: str,
                   backspan: int) -> tuple[tuple[int, int], ...]:
    """Model the four exact painter traversals after their hoisted row guard."""
    tiles: list[tuple[int, int]] = []
    if direction in ("north", "south"):
        if direction == "north":
            z_lo, z_hi = max(0, cam_z - backspan), min(198, cam_z + 65)
            rows = range(z_hi, z_lo - 1, -1)
        else:
            z_lo, z_hi = max(0, cam_z - 65), min(198, cam_z + backspan)
            rows = range(z_lo, z_hi + 1)
        for z in rows:
            span = min(65, 90 - abs(cam_z - z))
            x_lo, x_hi = max(0, cam_x - span), min(198, cam_x + span)
            tiles.extend((x, z) for x in range(x_lo, cam_x))
            tiles.extend((x, z) for x in range(x_hi, cam_x - 1, -1))
    else:
        if direction == "east":
            x_lo, x_hi = max(0, cam_x - 65), min(198, cam_x + backspan)
            columns = range(x_lo, x_hi + 1)
        else:
            x_lo, x_hi = max(0, cam_x - backspan), min(198, cam_x + 65)
            columns = range(x_hi, x_lo - 1, -1)
        for x in columns:
            span = min(65, 90 - abs(cam_x - x))
            z_lo, z_hi = max(0, cam_z - span), min(198, cam_z + span)
            tiles.extend((x, z) for z in range(z_hi, cam_z, -1))
            tiles.extend((x, z) for z in range(z_lo, cam_z + 1))
    return tuple(tiles)


def signed_lerp(old: int, new: int, phase: int, denominator: int = 60000) -> int:
    product = (new - old) * phase
    delta = abs(product) // denominator
    return old - delta if product < 0 else old + delta


def fast_timing_deadline(deadline: int, now: int, period: int,
                         rebase_threshold: int) -> tuple[int, str]:
    """Model the bounded catch-up policy after one deadline advance."""
    advanced = deadline + period
    lateness = now - advanced
    if lateness < 0:
        return advanced, "wait"
    if lateness < rebase_threshold:
        return advanced, "catch-up"
    return now, "rebase"


def signed32(value: int) -> int:
    value &= 0xFFFFFFFF
    return value if value < 0x80000000 else value - 0x100000000


def widen_f32_image(bits: int) -> tuple[int, int]:
    """Return the exact low/high binary64 words for one binary32 image."""
    sign = bits >> 31
    exponent = (bits >> 23) & 0xFF
    fraction = bits & 0x7FFFFF
    if exponent == 0:
        if fraction == 0:
            image = sign << 63
        else:
            top = fraction.bit_length() - 1
            double_exponent = top - 149 + 1023
            double_fraction = (fraction - (1 << top)) << (52 - top)
            image = (sign << 63) | (double_exponent << 52) | double_fraction
    else:
        double_exponent = 0x7FF if exponent == 0xFF else exponent + 896
        image = (sign << 63) | (double_exponent << 52) | (fraction << 29)
    return image & 0xFFFFFFFF, image >> 32


def greenmush_store_narrowed(low: int, high: int) -> int:
    """Model VHGND store narrowed's extraction and FStoreF32 edge policy."""
    sign = high >> 31
    exponent = (high >> 20) & 0x7FF
    if exponent <= 896:
        return sign << 31
    if exponent >= 1151:
        return (sign << 31) | 0x7F800000
    return ((sign << 31) | ((exponent - 896) << 23) |
            ((high & 0xFFFFF) << 3) | (low >> 29))


def legacy_greenmush_destination(gc_x: int, gc_y: int, random_x: int,
                                 random_y: int, page: int, radpt: int) -> int:
    row = signed32(gc_y + random_y)
    offset = signed32(row * 320)
    offset = signed32(offset + signed32(gc_x + random_x))
    return signed32(signed32(page + radpt) + offset)


def hoisted_greenmush_destination(gc_x: int, gc_y: int, random_x: int,
                                  random_y: int, page: int, radpt: int) -> int:
    origin = signed32(gc_y * 320)
    origin = signed32(origin + gc_x)
    origin = signed32(origin + page)
    origin = signed32(origin + radpt)
    offset = signed32(random_y * 320)
    offset = signed32(offset + random_x)
    return signed32(origin + offset)


def terrain_depth_n_words(dx: int, dz: int) -> int:
    """Model the two square words and explicit carry used by tile depth."""
    x_squared = dx * dx
    z_squared = dz * dz
    x_low, x_high = x_squared & 0xFFFFFFFF, x_squared >> 32
    z_low, z_high = z_squared & 0xFFFFFFFF, z_squared >> 32
    low = (x_low + z_low) & 0xFFFFFFFF
    carry = int(low < z_low)
    high = (x_high + z_high + carry) & 0xFFFFFFFF
    return ((high << 4) | (low >> 28)) & 0xFFFFFFFF


def terrain_depth_root(depth_n: int, low: int, high: int, steps: int) -> int:
    """Model VHGND tile depth's fixed-iteration integer square root."""
    for _ in range(steps):
        midpoint = (low + high) >> 1
        if midpoint * midpoint <= depth_n:
            low = midpoint
        else:
            high = midpoint
    return low


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


def environment_text(gravity: int, temperature: int, pressure: int, pulse: int) -> str:
    """Source lower-visor values in milli-, tenth-, milli-, and whole units."""
    sign = "+" if temperature >= 0 else "-"
    magnitude = abs(temperature)
    return (
        f"GRAVITY {max(0, gravity) // 1000}.{max(0, gravity) % 1000:03} "
        f"FG & TEMPERATURE {sign}{magnitude // 10}.{magnitude % 10}@C & "
        f"PRESSURE {max(0, pressure) // 1000}.{max(0, pressure) % 1000:03} "
        f"ATM & PULSE {pulse:3} PPS"
    )


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


def checkpoint_preferences_word(
    autoscreen: int,
    reverse: int,
    menus_always_on: int,
    depolarize: int,
    roofspeed: int,
    mouselook: int,
) -> int:
    """Pack v18 word 64 without changing the established preference bits."""
    return (
        autoscreen
        | reverse << 1
        | menus_always_on << 2
        | depolarize << 3
        | roofspeed << 4
        | mouselook << 5
    )


def checkpoint_preferences(
    version: int, word: int
) -> tuple[int, int, int, int, int, int] | None:
    """Model version-specific validation and migration of checkpoint word 64."""
    if word < 0:
        return None
    if version in (15, 16, 17):
        if word > 15:
            return None
        roofspeed, mouselook = 0, 1
    elif version == 18:
        if word & ~127 or (word >> 5) & 3 == 3:
            return None
        roofspeed, mouselook = (word >> 4) & 1, (word >> 5) & 3
    else:
        return None
    return (
        word & 1,
        (word >> 1) & 1,
        (word >> 2) & 1,
        (word >> 3) & 1,
        roofspeed,
        mouselook,
    )


def checkpoint_drive(version: int, word66: int, approach_reached: int) -> int:
    """Model the v16 reconstruction and exact v17/v18 drive-bit contract."""
    if version >= 17:
        return (word66 >> 23) & 1
    return 1 - approach_reached


ESCAPE_OWNERS = (
    "label", "sl", "dl", "landing_selector", "landing_request", "goes",
    "browser", "fcs", "device", "preferences", "data", "graphics",
    "movie", "help", "about",
)


def gameplay_escape_step(
    held: bool, pressed: bool, active: set[str]
) -> tuple[bool, str | None]:
    """Model the one-edge, modal-first gameplay Escape dispatcher."""
    if not pressed:
        return False, None
    if held:
        return True, None
    for owner in ESCAPE_OWNERS:
        if owner in active:
            return True, owner
    if active.intersection({"drive", "approach", "lift"}):
        return True, "blocked"
    return True, "quit"


def fcs_row9_class(
    *, target_valid: bool, approaching: bool, reached: bool,
    landing_active: bool, body_type: int,
) -> str:
    """Model guarded NOCTIS fcs_commands case 4 classification."""
    if approaching or not target_valid:
        return "error"
    if not reached:
        return "clear"
    if landing_active:
        return "cancel"
    if body_type in (0, 6) or body_type >= 9:
        return "impossible"
    return "deploy"


def ctrl_edge(value: int, held: bool, pressed: bool, modulo: int = 2) -> tuple[int, bool, bool]:
    """Return value, next latch, and consumption for a toggle chord."""
    if not pressed:
        return value, False, False
    return ((value + 1) % modulo if not held else value), True, True


def landing_ctrl_step(lon: int, lat: int, key: str) -> tuple[int, int]:
    """Model accelerated native enhanced-key landing movement."""
    if key == "left":
        lon = (lon - 3) % 360
    elif key == "right":
        lon = (lon + 3) % 360
    elif key == "up":
        lat = max(1, lat - 3)
    elif key == "down":
        lat = min(119, lat + 3)
    return lon, lat


def goes_character(value: int) -> int | None:
    """Model GOES quote normalization, uppercase folding, and filtering."""
    if value == 34:
        value = 39
    if 97 <= value <= 122:
        value -= 32
    if not 32 <= value <= 90 or value in (36, 38, 60, 62):
        return None
    return value


def main() -> int:
    game = GAME.read_text(encoding="utf-8")
    ground = GROUND.read_text(encoding="utf-8")
    pgtex = PGTEX.read_text(encoding="utf-8")
    pgmem = PGMEM.read_text(encoding="utf-8")
    pgfp = PGFP.read_text(encoding="utf-8")
    pgproj = PGPROJ.read_text(encoding="utf-8")
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
    capture_script = CAPTURE_SCRIPT.read_text(encoding="utf-8")
    original_repair = ORIGINAL_REPAIR.read_bytes()
    windows_hidden_process = WINDOWS_HIDDEN_PROCESS.read_text(encoding="utf-8")

    held, owner = gameplay_escape_step(False, True, {"preferences", "help"})
    held_again, repeated = gameplay_escape_step(held, True, {"help"})
    released, release_owner = gameplay_escape_step(held_again, False, {"help"})
    blocked_held, blocked = gameplay_escape_step(False, True, {"drive"})
    still_held, delayed = gameplay_escape_step(blocked_held, True, set())
    fresh_held, fresh = gameplay_escape_step(False, True, set())
    check(
        (owner, repeated, released, release_owner, blocked, delayed, fresh)
        == ("preferences", None, False, None, "blocked", None, "quit")
        and held and held_again and blocked_held and still_held and fresh_held
        and all(token in game for token in (
            '"VHG gameplay escape"', '"VHG gameplay escape SL"',
            '"VHG gameplay escape landing"', '"VHG gameplay escape GOES"',
            '"VHG gameplay escape browser"', '"VHG gameplay escape safety"',
            'A = [VHGgameescheld]; ? A != 0 -> VHG input done;',
            'A = [VHGbrowseorigin]; [VHGbrowseorigin] = 0;',
            '? A = VHGBROWSEFCS -> VHG browse restore FCS;',
        )),
        "one gameplay Escape edge closes one modal, blocks safely, and restores browser callers",
    )
    roof, roof_latch, roof_used = ctrl_edge(0, False, True)
    roof_held, roof_latch_held, roof_used_held = ctrl_edge(roof, roof_latch, True)
    roof_released, roof_latch_released, roof_used_released = ctrl_edge(roof_held, roof_latch_held, False)
    mouse_modes = []
    mouse, latch = 0, False
    for _ in range(3):
        mouse, latch, used = ctrl_edge(mouse, latch, True, 3)
        mouse_modes.append((mouse, used))
        mouse, latch, _ = ctrl_edge(mouse, latch, False, 3)
    check(
        (roof, roof_held, roof_released) == (1, 1, 1)
        and (roof_latch, roof_latch_held, roof_latch_released)
        == (True, True, False)
        and (roof_used, roof_used_held, roof_used_released)
        == (True, True, False)
        and mouse_modes == [(1, True), (2, True), (0, True)]
        and landing_ctrl_step(1, 2, "left") == (358, 2)
        and landing_ctrl_step(358, 118, "right") == (1, 118)
        and landing_ctrl_step(0, 2, "up") == (0, 1)
        and landing_ctrl_step(0, 118, "down") == (0, 119)
        and all(token in game for token in (
            '=> VHG modifier input; A = [VHGctrlused]; ? A != 0 -> VHG input done;',
            'A = [VHGlandinglon]; A - 3;', 'A = [VHGlandinglat]; A + 3;',
            '[VHPoutview] = 0;', 'A = [VHPoutrows]; A - 7;',
            'A = 1; A - [VHGroofspeed]; [VHGroofspeed] = A;',
            'A = [VHGmouselook]; A + 1;', '[VHGdevaccess] = 1; => VHG preferences open;',
            'A = [VHGroofspeed]; ? A = 0 -> VHG present timing wait;',
            'A = [VHGonroof]; ? A != 0 -> VHG present timing done;',
            'A = [VHGmouselook]; ? A = 0 -> VHG hosted mouse look release;',
            'C = [VHGmouselook]; ? C = 2 -> VHG hosted mouse look inverted Y;',
        )),
        "Ctrl aliases consume held chords, accelerate owned contexts, and preserve ordinary keys",
    )
    fcs_cases = {
        fcs_row9_class(target_valid=False, approaching=False, reached=False, landing_active=False, body_type=3),
        fcs_row9_class(target_valid=True, approaching=True, reached=False, landing_active=False, body_type=3),
        fcs_row9_class(target_valid=True, approaching=False, reached=False, landing_active=False, body_type=3),
        fcs_row9_class(target_valid=True, approaching=False, reached=True, landing_active=True, body_type=3),
        fcs_row9_class(target_valid=True, approaching=False, reached=True, landing_active=False, body_type=0),
        fcs_row9_class(target_valid=True, approaching=False, reached=True, landing_active=False, body_type=6),
        fcs_row9_class(target_valid=True, approaching=False, reached=True, landing_active=False, body_type=9),
        fcs_row9_class(target_valid=True, approaching=False, reached=True, landing_active=False, body_type=3),
    }
    check(
        fcs_cases == {"error", "clear", "cancel", "impossible", "deploy"}
        and all(token in original for token in (
            'case 4: if (!ip_reaching&&ip_targetted!=-1)',
            'if (!ip_reached)', 'landing_point = 1 - landing_point;',
            'nearstar_p_type[ip_targetted] == 0',
            'nearstar_p_type[ip_targetted] == 6',
            'nearstar_p_type[ip_targetted] >= 9',
        )),
        "FCS row 9 classifies every guarded native transition without invalid target access",
    )
    check(
        goes_character(34) == 39
        and goes_character(39) == 39
        and goes_character(ord("a")) == ord("A")
        and goes_character(36) is None
        and all(token in panels for token in (
            '? A = 34 -> VHP key quote;', 'A = 39; [VHPkey] = A;',
        ))
        and all(token in game for token in (
            'A = [KEY HOME]; ? A = OFF -> VHG console Home released;',
            '[VHGhomeheld] = 1; [VHGascii] = 0; => VH GOES clear;',
        )),
        "GOES normalizes quotes and gives command-screen Home one clear edge",
    )

    physical_pages = {
        "fcs": section(game, '"VHG onboard prepare FCS"', '"VHG onboard prepare root"'),
        "root": section(game, '"VHG onboard prepare root"', '"VHG onboard prepare nav"'),
        "navigation": section(game, '"VHG onboard prepare nav"', '"VHG onboard prepare misc"'),
        "miscellaneous": section(game, '"VHG onboard prepare misc"', '"VHG onboard prepare cart"'),
        "cartography": section(game, '"VHG onboard prepare cart"', '"VHG onboard prepare emergency"'),
        "emergency": section(game, '"VHG onboard prepare emergency"', '"VHG onboard prepare browser"'),
        "browser": section(game, '"VHG onboard prepare browser"', '"VHG onboard prepare done"'),
        "preferences": section(game, '"VHG onboard prepare"', '"VHG onboard prepare devices"'),
    }
    accessible_pages = {
        "fcs": section(game, '"VHG FCS menu overlay"', '"VHG preferences overlay"'),
        "root": section(game, '"VHG device root overlay"', '"VHG device navigation overlay"'),
        "navigation": section(game, '"VHG device navigation overlay"', '"VHG device miscellaneous overlay"'),
        "miscellaneous": section(game, '"VHG device miscellaneous overlay"', '"VHG device cartography overlay"'),
        "cartography": section(game, '"VHG device cartography overlay"', '"VHG device emergency overlay"'),
        "emergency": section(game, '"VHG device emergency overlay"', '"VHG device target browser overlay"'),
        "browser": section(game, '"VHG device target browser overlay"', '"VHG device overlay done"'),
        "preferences": section(game, '"VHG preferences overlay"', '"VHG browse format rows"'),
    }
    dispatch_pages = {
        "fcs": section(game, '"VHG FCS menu key"', '"VHG preference key"'),
        "root": section(game, '"VHG device root key"', '"VHG device open navigation"'),
        "navigation": section(game, '"VHG device navigation key"', '"VHG device miscellaneous key"'),
        "miscellaneous": section(game, '"VHG device miscellaneous key"', '"VHG device cartography key"'),
        "cartography": section(game, '"VHG device cartography key"', '"VHG device emergency key"'),
        "emergency": section(game, '"VHG device emergency key"', '"VHG device browser key"'),
        "browser": section(game, '"VHG device browser key"', '"VHG device toggle"'),
        "preferences": section(game, '"VHG preference key"', '"VHG hull cache apply"'),
    }
    control_rows = (
        ("fcs", 6, "VHGfcsmremote", "VHGfcsmremote", "VHG FCS remote action"),
        ("fcs", 7, "VHGfcsmstart", "VHGfcsmstart", "VHG FCS flight action"),
        ("fcs", 8, "VHGfcsmlocal", "VHGfcsmlocal", "VHG FCS local action"),
        ("fcs", 9, "=> VHG FCS row9 label", "=> VHG FCS row9 label", "=> VHG FCS row9 action"),
        ("root", 6, "VHGsrcdevnav", "VHGdevnav", "VHG device open navigation"),
        ("root", 7, "VHGsrcdevmisc", "VHGdevmisc", "VHG device open miscellaneous"),
        ("root", 8, "VHGsrcdevcart", "VHGdevcart", "VHG device open cartography"),
        ("root", 9, "VHGsrcdevemergency", "VHGdevemergency", "VHG device open emergency"),
        ("navigation", 6, "VHGsrcampoff", "VHGnavampoff", "VHG device amplifier"),
        ("navigation", 7, "VHGsrcfinderoff", "VHGnavfinderoff", "VHG device finder"),
        ("navigation", 8, "VHGsrctrackoff", "VHGnavtrackoff", "VHG device tracking"),
        ("navigation", 9, "VHGsrcradoff", "VHGnavradoff", "VHG device radiation"),
        ("miscellaneous", 6, "VHGsrclightoff", "VHGdevlightoff", "VHG device light"),
        ("miscellaneous", 7, "VHGsrcremote", "VHGdevremote", "VHG device remote"),
        ("miscellaneous", 8, "VHGsrclocal", "VHGdevlocal", "VHG device local"),
        ("miscellaneous", 9, "VHGsrcenvironment", "VHGdevenvironment", "[VHGinfo] = 3"),
        ("cartography", 6, "VHGsrccartstar", "VHGcartstar", "VHG device name star"),
        ("cartography", 7, "VHGsrccartplanet", "VHGcartplanet", "VHG device name planet"),
        ("cartography", 8, "VHGsrccarttargets", "VHGcartnext", "VHG device next target"),
        ("cartography", 9, "VHGsrccartparsis", "VHGcartmanual", "VHG device manual target"),
        ("emergency", 6, "VHGsrcreset", "VHGemergencyreset", "VHG device emergency reset"),
        ("emergency", 7, "VHGsrchelp", "VHGemergencyhelp", "VHG device emergency help"),
        ("emergency", 8, "VHGsrclithiumoff", "VHGemergencylithiumoff", "VHG device emergency collector"),
        ("emergency", 9, "VHGsrcclear", "VHGemergencyclear", "VHG device emergency clear"),
        ("browser", 6, "VHGbrowseprev", "VHGbrowseprev", "VHG device browser previous"),
        ("browser", 7, "VHGbrowsenext", "VHGbrowsenext", "VHG device browser next"),
        ("browser", 8, "VHGbrowseselect", "VHGbrowseselect", "VHG device browser select"),
        ("browser", 9, "VHGbrowseback", "VHGbrowseback", "VHG device browser back"),
        ("preferences", 6, "VHGprefautooff", "VHGprefmautooff", "VHG preference auto"),
        ("preferences", 7, "VHGprefnormal", "VHGprefmnormal", "VHG preference reverse"),
        ("preferences", 8, "VHGprefhidden", "VHGprefmhidden", "VHG preference menus"),
        ("preferences", 9, "VHGprefdepolarize", "VHGprefmdepolarize", "VHG preference hull"),
    )
    missing_rows = [
        f"{page}:{key}"
        for page, key, physical, accessible, action in control_rows
        if physical not in physical_pages[page]
        or accessible not in accessible_pages[page]
        or action not in dispatch_pages[page]
    ]
    menu_mouse = section(game, '"VHG menu mouse"', '"VHG onboard select"')
    check(
        len(control_rows) == 32
        and not missing_rows
        and all({key for candidate_page, key, *_ in control_rows if candidate_page == page} == {6, 7, 8, 9}
                for page in physical_pages)
        and all(token in menu_mouse for token in (
            'A = [VHGmenuy]; ? A < 30 -> VHG menu mouse back row;',
            '? A >= 118 -> VHG menu mouse back row; A - 30; A \'/ 22;',
            'A = C; A + 54; [VHGmenukey] = A;',
            'A = [VHGmenuy]; ? A < 96 -> VHG menu mouse button;',
            '? A >= 184 -> VHG menu mouse button; A - 96; A \'/ 22;',
        ))
        and all(token in game for token in (
            '[VHGgazecontrol] = A;', '[VHGgazecommand] = A;',
            '[VHPoncontrol] = [VHGgazecontrol]; [VHPoncommand] = [VHGgazecommand];',
        )),
        "all 32 onboard rows share complete physical, accessibility, geometry, and action contracts",
    )
    check(
        all(token in game for token in (
            '`controltrace` appends one versioned state record after each input pass.',
            '=> VHG input; => VHG control trace;',
            '[vhgcontrolstate plus 0] = 56484354h; [vhgcontrolstate plus 1] = 1;',
            '[vhgcontrolstate plus 2] = [VHGcontroltracecount];',
            '[vhgcontrolstate plus 3] = [VHGesc]; [vhgcontrolstate plus 4] = [VHGgameescheld];',
            '[vhgcontrolstate plus 8] = [VHGbrowseorigin];',
            '[vhgcontrolstate plus 10] = [VHGroofspeed];',
            '[vhgcontrolstate plus 11] = [VHGmouselook];',
            '[vhgcontrolstate plus 22] = [VHGfcs9class];',
            '[Block Pointer] = vhgcontrolstate; [Block Size] = 104; isocall;',
        )),
        "controltrace is inert by default and publishes complete versioned post-input records",
    )

    binary64_wrappers = (
        ("add", "sub", "+:", "FAdd"),
        ("sub", "mul", "-:", "FSub"),
        ("mul", "quo", "*:", "FMul"),
        ("quo", "rsub", "/:", "FQuo"),
    )
    check(
        all(
            "A = [PGFi]; A + A; A + fw;" in
            section(pgfp, f'"PGF {name}"', f'"PGF {following}"')
            and f"[FA0] {operation} [A];" in
            section(pgfp, f'"PGF {name}"', f'"PGF {following}"')
            and "=> PGF b;" not in
            section(pgfp, f'"PGF {name}"', f'"PGF {following}"')
            and old_operation not in
            section(pgfp, f'"PGF {name}"', f'"PGF {following}"')
            for name, following, operation, old_operation in binary64_wrappers
        ),
        "renderer scalar wrappers use backend-exact p64-then-p53 operations",
    )
    reverse_sub = section(pgfp, '"PGF rsub"', '"PGF rquo"')
    reverse_quo = section(pgfp, '"PGF rquo"', '"PGF int"')
    narrow = section(pgfp, '"PGF narrow"', '"PGF add"')
    to_int = section(pgfp, '"PGF int"', '"PGF fromint"')
    from_int = section(pgfp, '"PGF fromint"', '( the pinned constants')
    check(
        "[FT0] = [FA0]; [FT1] = [FA1];" in reverse_sub
        and "=> PGF a;" in reverse_sub
        and "A = FT0; [FA0] -: [A];" in reverse_sub
        and "FSubR" not in reverse_sub
        and "[FT0] = [FA0]; [FT1] = [FA1];" in reverse_quo
        and "=> PGF a;" in reverse_quo
        and "A = FT0; [FA0] /: [A];" in reverse_quo
        and "FQuoR" not in reverse_quo,
        "reverse scalar wrappers reuse the backend-exact arithmetic path",
    )
    check(
        "~: [FA0];" in narrow
        and narrow.index("~: [FA0];") < narrow.index("=> PGF sa;")
        and "F32Narrow" not in narrow
        and "[FI] =: [FA0];" in to_int
        and "FToIntNear" not in to_int
        and "[FA0] := [FI];" in from_int
        and "IntToF" not in from_int,
        "renderer conversions use the backend-exact direct operators",
    )
    getcoords = section(pgproj, '"PG getcoords"', '"PG facing"')
    check(
        "=> PJ rotate;" not in getcoords
        and "=> PGF " not in getcoords
        and getcoords.count("~: [FA0];") == 7
        and getcoords.count("[FI] =: [FA0];") == 2
        and getcoords.count("-:") == 5
        and getcoords.count("*:") == 10
        and getcoords.count("+:") == 4
        and getcoords.count("/:") == 1
        and all(token in getcoords for token in (
            "[PJnrv] = 1; [PJmode] = 1; [PJvr] = 0; [PJdoflag] = 0;",
            "[FA0] = [fw plus 520]; [FA1] = [fw plus 521];",
            "[FA0] = [fw plus 504]; [FA1] = [fw plus 505];",
            "[FA0] = [fw plus 512]; [FA1] = [fw plus 513];",
            "[fw plus 498] = [FA0]; [fw plus 499] = [FA1];",
            "[FB0] = [fw plus 54]; [FB1] = [fw plus 55];",
            "=> FCmp;",
            "[fw plus 502] = [FA0]; [fw plus 503] = [FA1];",
            "[FI] =: [FA0]; [GCx] = [FI];",
            "[FI] =: [FA0]; [GCy] = [FI]; [PGFi] = FSYC;",
        )),
        "one-point getcoords uses the exact direct scalar schedule",
    )
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
    lift = section(game, '"VHG lift tick"', '"VHG lift move"')
    lift_trace = section(game, '"VHG lift trace"', '"VHG lift move"')
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
        and "=> VHG fpu clean; => VHG lift postrender; => VHG lift trace; => VHG capsule trace; => VHG input;" in game
        and "A = [VHGdosim]; ? A = 0 -> VHG lift postrender done;" in game
        and "=> VHG lift tick;\n\t( p_Forward(step) is clamped" in game
        and "=> VHG clamp position;\n    \"VHG skip ship ticks\"" in game
        and "A = [VHGx]; A * 3; A / 4; [VHGx] = A;" in game
        and "A = [VHGz]; A + 3100; A / 4;" in game,
        "lift preserves source trigger, movement, clamp, render, and restraint ordering",
    )
    check(
        "VHGsentinellifttrace = 0;" in game
        and "VHGlifttraceactive = 0; VHGlifttracecount = 0; VHGlifttraceindex = 0;" in game
        and "vhgliftstatename = { game-lift-state-out.bin };" in game
        and "vhgliftpagesname = { game-lift-pages-out.bin };" in game
        and "vhgliftstate = 8;" in game
        and all(token in lift_trace for token in (
            "A = [VHGsentinellifttrace]; ? A = 0 -> VHG lift trace done;",
            "A = [VHGdosim]; ? A = 0 -> VHG lift trace done;",
            "A = [VHGlifttraceactive]; ? A != 0 -> VHG lift trace capture;",
            "A = [VHGlifter]; ? A = 0 -> VHG lift trace done;",
            "[VHGlifttraceactive] = 1;",
            "[vhgliftstate plus 0] = [VHGy]; [vhgliftstate plus 1] = [VHGlifter];",
            "[vhgliftstate plus 2] = [VHGonroof]; [vhgliftstate plus 3] = [VHGliftstep];",
            "[vhgliftstate plus 4] = [VHGx]; [vhgliftstate plus 5] = [VHGz];",
            "[vhgliftstate plus 6] = [VHGalpha]; [vhgliftstate plus 7] = [VHGbeta];",
            "[SPpreg] = RGADP; [SPpn] = NPIX; => SP packpage;",
            "A = [VHGlifttracecount]; [VHGlifttraceindex] = A; A * 32;",
            "[Block Pointer] = vhgliftstate; [Block Size] = 32; isocall;",
            "A = [VHGlifttraceindex]; A * 64000;",
            "[Block Pointer] = sppack; [Block Size] = 64000; isocall;",
            "[VHGlifttracecount]+;",
            "[VHGlifttraceactive] = 0;",
        ))
        and lift_trace.index("A = [VHGsentinellifttrace];")
        < lift_trace.index("[SPpreg] = RGADP;")
        < lift_trace.index("[VHGlifttracecount]+;"),
        "opt-in lift trace records one post-restraint page and scalar state per simulation tick",
    )
    capsule_trace = section(game, '"VHG capsule trace"', '"VHG lift move"')
    check(
        "VHGsentinelcapsuletrace = 0;" in game
        and "VHGcapsuletraceactive = 0; VHGcapsuletracecount = 0; VHGcapsuletraceindex = 0;" in game
        and "vhgcapsulestatename = { game-capsule-state-out.bin };" in game
        and "vhgcapsulepagesname = { game-capsule-pages-out.bin };" in game
        and "vhgcapsulestate = 16;" in game
        and all(token in capsule_trace for token in (
            "A = [VHGsentinelcapsuletrace]; ? A = 0 -> VHG capsule trace done;",
            "A = [VHGdosim]; ? A = 0 -> VHG capsule trace done;",
            "A = [VHGcapsuletraceactive]; ? A != 0 -> VHG capsule trace capture;",
            "A = [VHGCstate]; ? A = 2 -> VHG capsule trace ascent start;",
            "? A != 1 -> VHG capsule trace done;",
            "[VHGcapsuletraceactive] = 3;",
            "[VHGcapsuletraceactive] = 1;",
            "[vhgcapsulestate plus 0] = [VHGCstate];",
            "[vhgcapsulestate plus 5] = [VHGcapsulereturnpending];",
            "[vhgcapsulestate plus 6] = [VHGx];",
            "[vhgcapsulestate plus 15] = [VHGdosim];",
            "[SPpreg] = RGADP; [SPpn] = NPIX; => SP packpage;",
            "A = [VHGcapsuletracecount]; [VHGcapsuletraceindex] = A; A * 64;",
            "[Block Pointer] = vhgcapsulestate; [Block Size] = 64; isocall;",
            "A = [VHGcapsuletraceindex]; A * 64000;",
            "[Block Pointer] = sppack; [Block Size] = 64000; isocall;",
            "[VHGcapsuletracecount]+;",
            "A = [VHGcapsuletraceactive]; ? A = 3 -> VHG capsule trace descent complete;",
            "? A = 2 -> VHG capsule trace complete;",
            "A = [VHGcapsulereturnpending]; ? A = 0 -> VHG capsule trace complete;",
            "[VHGcapsuletraceactive] = 2;",
            '"VHG capsule trace descent complete"',
            "A = [VHGlanded]; ? A = 0 -> VHG capsule trace done;",
            "[VHGcapsuletraceactive] = 0;",
        ))
        and capsule_trace.index("A = [VHGsentinelcapsuletrace];")
        < capsule_trace.index("[SPpreg] = RGADP;")
        < capsule_trace.index("[VHGcapsuletracecount]+;")
        < capsule_trace.index("[VHGcapsuletraceactive] = 2;"),
        "opt-in capsule trace records authoritative descent, ascent, and clean handoffs",
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
        and "A - 100; [VHGlifter] = A;" in platform
        and "A - 70; [VHGlifter] = A;" not in platform
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
    mouse_look = section(game, '"VHG hosted mouse look"', '"VHG return key"')
    menu_mouse = section(game, '"VHG menu mouse"', '"VHG systems reset action"')
    check(
        "=> VHG hosted mouse look;" in game
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
            "[FI] = VHPTX; => IntToF; [PGFi] = FSTX; => PGF sa;",
            "[FI] = VHPTY; => IntToF; [PGFi] = FSTY; => PGF sa;",
            "A = [VHPonc]; A '* 30;", "A = [VHPonp]; A '* 50;",
            "A = [VHPonp]; A '* 46; A + 12; C = A;",
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
            "A = VHGsrccartstarremove;", "[VHPoncmd0] = VHGsrcreset;",
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
    capsule_tile_gate = section(
        tile,
        "( fragment() paints the settled capsule",
        '"VHGND tile capsule done"',
    )
    check(
        tile.count("=> VHGND terrain mapped;") == 2
        and tile.count("=> PG poly3d;") == 2
        and tile.count("-> VHGND tile first textured;") == 1
        and tile.count("-> VHGND tile second textured;") == 1
        and '"VHGND tile first flat"' in tile
        and '"VHGND tile second flat"' in tile
        and "[PGtexf] = 5" in ground
        and '"VHGND terrain mapped"' in ground
        and "[PJpreproject] = 1; [PJnrv] = 3; => PG polymap;" in ground
        and '"PG tex 5"' in (ROOT / "work" / "pgmem.txt").read_text(encoding="utf-8"),
        "faithful terrain triangles remain texture mapped on foot and during capsule flight",
    )
    uv_float = section(pgtex, '"PG uv float"', '"PG texel"')
    uv_steps = (
        "[FA0] = [fw plus 30]; [FA1] = [fw plus 31];",
        "[FA0] +: [fw plus 22];",
        "[fw plus 496] = [FA0]; [fw plus 497] = [FA1];",
        "~: [FA0]; [fw plus 30] = [FA0]; [fw plus 31] = [FA1];",
        "[FA0] = [fw plus 26]; [FA1] = [fw plus 27];",
        "[FA0] +: [fw plus 18];",
        "[fw plus 498] = [FA0]; [fw plus 499] = [FA1];",
        "~: [FA0]; [fw plus 26] = [FA0]; [fw plus 27] = [FA1];",
        "[FA0] = [fw plus 28]; [FA1] = [fw plus 29];",
        "[FA0] +: [fw plus 20];",
        "[fw plus 500] = [FA0]; [fw plus 501] = [FA1];",
        "~: [FA0]; [fw plus 28] = [FA0]; [fw plus 29] = [FA1];",
        "[FA0] = [fw plus 496]; [FA1] = [fw plus 497];",
        "[FT0] = [FA0]; [FT1] = [FA1];",
        "[FA0] = [fw plus 36]; [FA1] = [fw plus 37];",
        "[FA0] /: [FT0];",
        "~: [FA0]; [fw plus 24] = [FA0]; [fw plus 25] = [FA1];",
        "[FA0] = [fw plus 498]; [FA1] = [fw plus 499];",
        "[FA0] *: [fw plus 32];",
        "[FA0] *: [fw plus 24];",
        "[FI] =: [FA0]; [SPun] = [FI];",
        "[FA0] = [fw plus 500]; [FA1] = [fw plus 501];",
        "[FA0] *: [fw plus 34];",
        "[FA0] *: [fw plus 24];",
        "[FI] =: [FA0]; [SPvn] = [FI];",
    )
    check(
        contains_in_order(uv_float, uv_steps)
        and uv_float.count("[FA0] +:") == 3
        and uv_float.count("[FA0] *:") == 4
        and uv_float.count("~: [FA0];") == 4
        and uv_float.count("[FI] =: [FA0];") == 2
        and "=> PGF " not in uv_float
        and "[PGFi]" not in uv_float,
        "live texture spans preserve the exact fixed-slot arithmetic and spill schedule",
    )
    merger7_dispatch = section(pgtex, '"PG row mode"', '"PG px terrain begin"')
    merger7_generic = section(pgtex, '"PG px merger7 begin"', '"PG px merger7 zero begin"')
    merger7_zero = section(pgtex, '"PG px merger7 zero begin"', '"PG px merger7 tail"')
    merger7_tail = section(pgtex, '"PG px merger7 tail"', '"PG px merger"')
    cupola_merger = section(cupola, '"VHC draw textured panel"', '"VHC draw panel done"')

    def merger7_pair_visits(count: int) -> list[int]:
        visited: list[int] = []
        position = 0
        if count & 1:
            visited.append(position)
            position += 1
        while position < count:
            visited.extend((position, position + 1))
            position += 2
        return visited

    merger7_zero_formula_exact = all(
        ((old & 192) | ((((old & 63) + 0) & 255) >> 1))
        == ((old & 192) | ((old & 63) >> 1))
        for old in range(256)
    )
    check(
        contains_in_order(merger7_dispatch, (
            '"PG px merger select"',
            "A = [PGtexf]; ? A = 7 -> PG px merger7 begin;",
            "-> PG px merger;",
        ))
        and "A = [CSpix]; C = [SPcl]; A + C; [CSpix] = A; [PGm7n] = [SPcl];" in merger7_generic
        and "A = [SPtinta]; ? A = 0 -> PG px merger7 zero begin;" in merger7_generic
        and "B = [PGSCRT plus PGDOFF plus SADPT plus nw]; B & 255;" in merger7_generic
        and "E + B; E & 255; E > 1;" in merger7_generic
        and "PGSCRT" not in merger7_zero
        and "A = [SPcl]; A & 1; ? A = 0 -> PG px merger7 zero pair begin;" in merger7_zero
        and merger7_zero.count("D = [A]; D & 255; E = D; E & 63; E > 1;") == 3
        and "C = [SPdi]; C + 2; C & 65535; [SPdi] = C;" in merger7_zero
        and "C = [SPcl]; C - 2; [SPcl] = C;" in merger7_zero
        and all(merger7_pair_visits(count) == list(range(count)) for count in range(1, 17))
        and merger7_zero_formula_exact
        and 190 * 320 + 311 + 3 < 63996
        and contains_in_order(merger7_tail, (
            "B = [PGm7n]; B-;",
            "[PGtexi] = A; [PGtmp] = A; [PGtexv] = 0;",
            "C + [SPbp]; C & 65535; [SPax] = C;",
            "D + [SPsi]; D & 65535; [SPdx] = D;",
            "A = [SPdi]; A + 3; A & 65535; [SPt] = A; [PGdi] = A;",
            "A + SADPT plus nw; D = [A]; D & 255; [SPch] = D; [PGval] = D;",
            "-> PG row;",
        ))
        and contains_in_order(cupola_merger, (
            "[PGtexf] = 7; [SPtinta] = 0; [SPescr] = 0; [SPflar] = 4;",
            "[SPcull] = 0; [SPhalf] = 0; => PG polymap;",
            "[PGtexf] = 0; [SPflar] = 0;",
        )),
        "live zero-TEX7 merger keeps generic scratch semantics and exact paired pixel order",
    )
    terrain_pixel = section(pgtex, '"PG px terrain begin"', '"PG px terrain record begin"')
    terrain_cpixel = section(pgtex, '"PG cpx terrain begin"', '"PG cpx terrain record begin"')
    tex5_row = section(pgtex, '"PG tex5 row"', '"PG row"')
    terrain_row_control = section(pgtex, '"PG row"', '"PG px terrain begin"')
    terrain_crow_control = section(pgtex, '"PG crow"', '"PG cpx terrain begin"')
    tree_plain_dispatch = (
        "A = [SPterrain]; ? A != 0 -> PG px terrain begin;",
        "A = [SPflar]; A & 15;",
        "? A != 0 -> PG row mode;",
        "A = [SPpixfast]; ? A = 0 -> PG px internal;",
        "A = [PGtexf]; ? A = 5 -> PG px terrain begin;",
        "-> PG px internal;",
        '"PG row mode"',
        "A = [SPflar]; A & 1;  ? A != 0 -> PG px transp;",
    )
    tex5_row_schedule = (
        "? [SPsec] <= 0 -> PG row end;",
        "A = [SPsec]; ? A > 16 -> PG tex5 row full;",
        "[SPcl] = A;",
        "-> PG tex5 row ready;",
        '"PG tex5 row full"',
        "[SPcl] = 16;",
        '"PG tex5 row ready"',
        "A = [SPsec]; A - 16; [SPsec] = A;",
        "=> PG uv float;",
        "C = [SPv]; A = C; A & 65535; [SPdx] = A;",
        "D = [SPvn]; A = D; A - C; A >> 4; A & 65535; [SPsi] = A; [SPv] = D;",
        "C = [SPu]; A = C; A & 65535; [SPax] = A;",
        "D = [SPun]; A = D; A - C; A >> 4; A & 65535; [SPbp] = A; [SPu] = D;",
        "-> PG px terrain begin;",
    )
    retained_uv_setup = (
        "C = [SPv]; A = C; A & 65535; [SPdx] = A;\n"
        "\tD = [SPvn]; A = D; A - C; A >> 4; A & 65535; [SPsi] = A; [SPv] = D;\n"
        "\tC = [SPu]; A = C; A & 65535; [SPax] = A;\n"
        "\tD = [SPun]; A = D; A - C; A >> 4; A & 65535; [SPbp] = A; [SPu] = D;"
    )
    def terrain_unroll_visits(count: int) -> list[int]:
        position = 0
        checked = bool(count & 1)
        visited: list[int] = []
        while position < count:
            if not checked:
                position += 1
                visited.append(position)
            position += 1
            visited.append(position)
            if position == count:
                break
            checked = False
        return visited

    terrain_unroll_schedule_exact = all(
        terrain_unroll_visits(count) == list(range(1, count + 1))
        for count in range(1, 17)
    )
    culling_pair_counts: set[int] = set()
    for span in range(1, 307):
        remaining = span
        while remaining > 0:
            raw_count = 32 if remaining > 32 else (remaining + 2) & 255
            remaining -= 32
            if raw_count >= 2:
                culling_pair_counts.add(raw_count >> 1)
    terrain_culling_unroll_schedule_exact = (
        culling_pair_counts == set(range(1, 18))
        and all(
            terrain_unroll_visits(count) == list(range(1, count + 1))
            for count in culling_pair_counts
        )
    )
    terrain_culling_destination_hoist_exact = True
    framebuffer_base = 0x179AF2
    for start_x in range(5, 312):
        for count in range(1, 18):
            if start_x + 2 * count + 3 > 316:
                continue
            visits = terrain_unroll_visits(count)
            logical = start_x
            old_writes: list[tuple[int, int, int]] = []
            for position in visits:
                logical = (logical + 2) & 65535
                old_writes.extend((
                    (framebuffer_base + ((logical + 2) & 65535), position, 0),
                    (framebuffer_base + ((logical + 3) & 65535), position, 1),
                ))
            physical = framebuffer_base + start_x
            physical_endpoint = physical + 2 * count
            new_writes: list[tuple[int, int, int]] = []
            for position in visits:
                physical += 2
                new_writes.extend((
                    (physical + 2, position, 0),
                    (physical + 3, position, 1),
                ))
            terrain_culling_destination_hoist_exact &= (
                old_writes == new_writes
                and physical == physical_endpoint
                and logical == start_x + 2 * count
                and logical + 3 == start_x + 2 * count + 3
            )
    terrain_culling_uv_state_exact = True
    for initial in (0, 0xFF, 0x100, 0x7FFF, 0xFFFF):
        for step in (0, 1, 0xFF, 0x100, 0x7FFF, 0xFFFF):
            for count in culling_pair_counts:
                actual = initial
                for _ in terrain_unroll_visits(count):
                    actual = (actual + step) & 65535
                terrain_culling_uv_state_exact &= (
                    actual == (initial + count * step) & 65535
                )
    terrain_tint_mask_exact = all(
        ((((loaded & 255) + tint) & 0xFFFFFFFF) & 255)
        == (((loaded + tint) & 0xFFFFFFFF) & 255)
        for low in range(256)
        for high in (0, 0x100, 0x7FFFFF00, 0xFFFFFF00)
        for loaded in (high | low,)
        for tint in (0, 1, 255, 256, 0x7FFFFFFF, 0xFFFFFFFF)
    )
    check(
        "A = [CSpix]; C = [SPcl]; A + C; [CSpix] = A;" in terrain_pixel
        and "A = [SPcl]; A + A; C = [CSpix]; A + C; [CSpix] = A;" in terrain_cpixel
        and "[SPcl] = 16;" in terrain_row_control
        and "A = [SPcl]; ? A = 0 -> PG row;" in terrain_row_control
        and contains_in_order(terrain_row_control, tree_plain_dispatch)
        and contains_in_order(tex5_row, tex5_row_schedule)
        and "=> PG uv next;" not in tex5_row
        and "[SPsrc]" not in tex5_row
        and "[SPterrain]" not in tex5_row
        and "[SPflar]" not in tex5_row
        and "[SPpixfast]" not in tex5_row
        and "[PGtexf]" not in tex5_row
        and "A & 255; [SPcl] = A;" not in tex5_row
        and "A = [SPcl]; ? A = 0 -> PG row;" not in tex5_row
        and "-> PG tex5 row;" in terrain_pixel
        and "[SPpixfast]" not in terrain_crow_control
        and "[PGtexf]" not in terrain_crow_control
        and "[SPcl] = 32;" in terrain_crow_control
        and "A > 1; [SPcl] = A;" in terrain_crow_control
        and retained_uv_setup in terrain_row_control
        and retained_uv_setup in terrain_crow_control
        and "[SPu] = [SPun]; [SPv] = [SPvn];" not in terrain_row_control
        and "[SPu] = [SPun]; [SPv] = [SPvn];" not in terrain_crow_control
        and "A = [SPdi]; D = A; D + [SPcl]; [SPdi] = D;" in terrain_pixel
        and (
            "A = [SPdi]; A + SADPT plus nw;\n"
            "\tD = [SPcl]; D + D; D + A; [SPdi] = D;"
        ) in terrain_cpixel
        and "B = [SPdx]; C = [SPax];" in terrain_pixel
        and "B = [SPdx]; C = [SPax];" in terrain_cpixel
        and terrain_unroll_schedule_exact
        and terrain_culling_unroll_schedule_exact
        and terrain_culling_destination_hoist_exact
        and terrain_culling_uv_state_exact
        and terrain_tint_mask_exact
        and "D = [SPcl]; D & 1; ? D != 0 -> PG px terrain;" in terrain_pixel
        and '"PG px terrain unchecked"' in terrain_pixel
        and "-> PG px terrain unchecked;" in terrain_pixel
        and "D = [SPcl]; D & 1; ? D != 0 -> PG cpx terrain;" in terrain_cpixel
        and '"PG cpx terrain unchecked"' in terrain_cpixel
        and "-> PG cpx terrain unchecked;" in terrain_cpixel
        and "A + 1; ? A = [SPdi] -> PG px terrain final;" in terrain_pixel
        and "A + 2; ? A = [SPdi] -> PG cpx terrain final;" in terrain_cpixel
        and terrain_pixel.count("[SPcl]-;") == 0
        and terrain_cpixel.count("[SPcl]-;") == 0
        and terrain_pixel.count("[SPcl] = 0;") == 1
        and terrain_cpixel.count("[SPcl] = 0;") == 1
        and "[SPdi] = A;" not in terrain_pixel
        and "[SPdi] = A;" not in terrain_cpixel
        and "D = B; D & 65280;" in terrain_pixel
        and "D = B; D & 65280;" in terrain_cpixel
        and "E = C; E > 8; D | E;" in terrain_pixel
        and "E = C; E > 8; D | E;" in terrain_cpixel
        and terrain_pixel.count("D + [PGtexoff]; D + RPBG plus nw; E = [D];") == 3
        and terrain_cpixel.count("D + [PGtexoff]; D + RPBG plus nw; E = [D];") == 3
        and terrain_pixel.count("E = [D]; E & 255;") == 1
        and terrain_cpixel.count("E = [D]; E & 255;") == 1
        and terrain_pixel.count("E + [SPtinta]; E & 255;") == 3
        and terrain_cpixel.count("E + [SPtinta]; E & 255;") == 3
        and terrain_pixel.count("[A plus 3 plus SADPT plus nw] = E;") == 3
        and "D = A; D + 3 plus SADPT plus nw; [D] = E;" not in terrain_pixel
        and "D + SADPT plus nw; [D] = E;" not in terrain_pixel
        and terrain_cpixel.count("[A plus 2] = E;") == 3
        and terrain_cpixel.count("[A plus 3] = E;") == 3
        and "D = A; D + 2; [D] = E;" not in terrain_cpixel
        and "D = A; D + 3; [D] = E;" not in terrain_cpixel
        and "D + SADPT plus nw; [D] = E;" not in terrain_cpixel
        and "A + 2; A & 65535;" not in terrain_cpixel
        and "D = A; D + 2; D & 65535;" not in terrain_cpixel
        and "D = A; D + 3; D & 65535;" not in terrain_cpixel
        and "D = [SPcl]; D + D; D + [SPsave]; D + 2; [PGdi] = D; [PGval] = E;" in terrain_cpixel
        and "[PGdi]+;" in terrain_cpixel
        and "D + RPBG; D + nw;" not in terrain_pixel
        and "D + RPBG; D + nw;" not in terrain_cpixel
        and "D + SADPT; D + nw;" not in terrain_pixel
        and "D + SADPT; D + nw;" not in terrain_cpixel
        and "E + [SPtinta]; E & 255;" in terrain_pixel
        and "E + [SPtinta]; E & 255;" in terrain_cpixel
        and "=> PG texel;" not in terrain_pixel
        and "=> PG texel;" not in terrain_cpixel
        and "=> PG store;" not in terrain_pixel
        and "=> PG store;" not in terrain_cpixel
        and "=> PG scrtinta;" not in terrain_pixel
        and "=> PG scrtinta;" not in terrain_cpixel
        and "[CSpix]+;" not in terrain_pixel
        and "[CSpix]+;" not in terrain_cpixel,
        "faithful terrain blocks use exact endpoints and folded bases while retaining pixel state",
    )
    terrain_edges = section(pgtex, '"PG ol init"', "( S5 - the span engine")
    edge_step = section(pgtex, '"PG ew intfor"', '"PG ew next"')
    terrain_clip = section(pgproj, '"PG pm projected"', '"PG pm basis"')
    terrain_basis_entry = section(pgproj, '"PG pm basis"', '"PG pm k generic"')
    terrain_trace = section(pgproj, '"PG trace"', '"PG polymap"')
    check(
        contains_in_order(edge_step, (
            "[PGFi] = FSBNDX; => PGF a;",
            "[FI] =: [FA0];",
            "[EWax] = [FI];",
            "[PGFi] = FSKX; => PGF add;",
            "A = [EWnarrow]; ? A = 0 -> PG ew wide;",
            "=> F32Narrow;",
            "[PGFi] = FSBNDX; => PGF sa;",
            "[EWh]+;",
            "[EWcx]-;",
            "? [EWcx] != 0 -> PG ew intfor;",
        ))
        and edge_step.count("[PGFi] = FSBNDX; => PGF a;") == 1
        and "=> PGF int;" not in edge_step,
        "edge walk keeps wide bndx live through its integer-only row body",
    )
    terrain_live_u = (
        "~: [FA0]; [fw plus 26] = [FA0]; [fw plus 27] = [FA1];\n\n"
        "\t( u from the live narrow x )\n"
        "\t[FA0] *: [fw plus 32];\n"
        "\t[FA0] *: [fw plus 24];\n"
        "\t[FI] =: [FA0]; [SPu] = [FI];"
    )
    terrain_live_v = (
        "~: [FA0]; [fw plus 28] = [FA0]; [fw plus 29] = [FA1];\n\n"
        "\t( v from the live narrow y )\n"
        "\t[FA0] *: [fw plus 34];\n"
        "\t[FA0] *: [fw plus 24];\n"
        "\t[FI] =: [FA0]; [SPv] = [FI];"
    )
    maximum_terrain_destination = 190 * 320 + 311 + 3
    maximum_culling_destination = 190 * 320 + 311 + 5
    maximum_culling_tail_destination = 190 * 320 + 342
    check(
        all(token in pgmem for token in (
            "PGLBX\t= 5;",
            "PGUBX\t= 311;",
            "PGLBY\t= 10;",
            "PGUBY\t= 190;",
        ))
        and "[C] = PGLBX;" in terrain_edges
        and "[C] = PGUBX;" in terrain_edges
        and "? A >= PGUBX -> PG ew ct2n;" in terrain_edges
        and "? A <= PGLBX -> PG ew ct4n;" in terrain_edges
        and "[C] = A;" in terrain_edges
        and "[BXminy] = PGLBY;" in terrain_clip
        and "[BXmaxy] = PGUBY;" in terrain_clip
        and "D - E; [SPsec] = D;" in terrain_trace
        and "C = [SPi]; => PG riga; C + E; C & 65535; [SPdi] = C;" in terrain_trace
        and terrain_trace.count("[FI] = [SPi]; [FA0] := [FI];") == 1
        and terrain_trace.count("[FA0] -: [fw plus 40];") == 1
        and "[fw plus 500] = [FA0]; [fw plus 501] = [FA1];" in terrain_trace
        and terrain_trace.count(
            "[FA0] = [fw plus 500]; [FA1] = [fw plus 501];"
        ) == 2
        and terrain_live_u in terrain_trace
        and terrain_live_v in terrain_trace
        and "[FA0] = [fw plus 26]; [FA1] = [fw plus 27];" not in terrain_trace
        and "[FA0] = [fw plus 28]; [FA1] = [fw plus 29];" not in terrain_trace
        and maximum_terrain_destination == 61114
        and maximum_terrain_destination < 65536
        and maximum_culling_destination == 61116
        and maximum_culling_destination < 65536
        and maximum_culling_tail_destination == 61142
        and maximum_culling_tail_destination < 65536
        and "A + 1; A & 65535;" not in terrain_pixel
        and "D = A; D + 3; D & 65535;" not in terrain_pixel
        and terrain_pixel.count("C + [SPbp]; C & 65535;") == 3
        and terrain_pixel.count("B + [SPsi]; B & 65535;") == 3,
        "clipped terrain destinations drop only provably inactive masks",
    )
    depth_root_build = section(
        ground,
        '"VHGND terrain half depth roots build"',
        '"VHGND tile depth x row"',
    )
    depth = section(ground, '"VHGND tile depth x row"', '"VHGND tile shade"')
    shade = section(ground, '"VHGND tile shade"', '"VHGND vload"')
    vload = ground[ground.index('"VHGND vload"'):]
    packed_half_words: list[int] = []
    packed_build_words: list[int] = []
    square_build_words = [0] * 128
    build_q = 0
    build_next = 1
    build_word = 0
    for block in range(512):
        depth_n = block << 5
        while depth_n >= build_next:
            build_q += 1
            square_build_words[build_q] = build_next
            build_next = (build_q + 1) * (build_q + 1)
        build_word |= build_q << ((block & 3) * 8)
        if block & 3 == 3:
            packed_build_words.append(build_word)
            build_word = 0
    square_words = [root * root for root in range(128)]
    for word_index in range(128):
        word = 0
        for lane in range(4):
            block = word_index * 4 + lane
            word |= math.isqrt(block << 5) << (lane * 8)
        packed_half_words.append(word)
    packed_half_roots_exact = packed_build_words == packed_half_words
    square_words_exact = square_build_words == square_words
    packed_half_terminal_exact = True
    minimum_two_square_gaps = (2 * math.isqrt(64) + 1) + (2 * (math.isqrt(64) + 1) + 1)
    for depth_n in range(16384):
        if depth_n < 64:
            low = 0
            high = 64
            midpoint = 0
            for _ in range(6):
                midpoint = (low + high) >> 1
                if midpoint * midpoint <= depth_n:
                    low = midpoint
                else:
                    high = midpoint
        else:
            block = depth_n >> 5
            word = packed_half_words[block >> 2]
            low = word >> ((block & 3) * 8) & 255
            next_square = square_words[low] + (low << 1) + 1
            if depth_n >= next_square:
                low += 1
                next_square += (low << 1) + 1
                if depth_n >= next_square:
                    low += 1
            high = low + 1
            midpoint = low | 1
        packed_half_terminal_exact &= (
            low == math.isqrt(depth_n)
            and (low, high, midpoint, 0)
            == (math.isqrt(depth_n), math.isqrt(depth_n) + 1, math.isqrt(depth_n) | 1, 0)
        )
    maximum_tile_root = 0
    bounded_roots_exact = True
    for lod_step in (1, 8, 16):
        for tile_dx in range(-90, 91):
            for tile_dz in range(-90 + abs(tile_dx), 91 - abs(tile_dx)):
                for fraction_x in (0, 16383):
                    for fraction_z in (0, 16383):
                        dx = (tile_dx << 14) + (lod_step << 13) - fraction_x
                        dz = (tile_dz << 14) + (lod_step << 13) - fraction_z
                        squared = dx * dx + dz * dz
                        depth_n = squared >> 28
                        expected = math.isqrt(squared) >> 14
                        root_low = 0 if depth_n < 4096 else 64
                        actual = terrain_depth_root(depth_n, root_low, root_low + 64, 6)
                        maximum_tile_root = max(maximum_tile_root, expected)
                        bounded_roots_exact &= (
                            terrain_depth_n_words(dx, dz) == depth_n
                            and actual == expected
                        )
    check(
        bounded_roots_exact and maximum_tile_root < 128,
        "full-width square words and split roots cover every accepted offset exactly",
    )
    check(
        packed_half_roots_exact
        and square_words_exact
        and packed_half_terminal_exact
        and minimum_two_square_gaps == 36
        and ground.count("=> VHGND terrain half depth roots build;") == 1
        and ground.index("=> VHGND terrain half depth roots build;")
        < ground.index("[VHGNDtick] = 0; [VHGNDptr] = 0; [VHGNDplayerstep] = 0;")
        and "VHGNDhalfdepthroots = 128; VHGNDdepthsquares = 128;" in ground
        and all(token in depth_root_build for token in (
            "[VHGNDdepthrootblock] = 0; [VHGNDdepthrootq] = 0;",
            "[VHGNDdepthrootnext] = 1; [VHGNDdepthrootshift] = 0;",
            "[VHGNDdepthsquares] = 0;",
            "A = [VHGNDdepthrootblock]; A < 5;",
            "? A < [VHGNDdepthrootnext] -> VHGND terrain half depth root pack;",
            "[VHGNDdepthrootq]+;",
            "D = VHGNDdepthsquares; D + [VHGNDdepthrootq]; A = [VHGNDdepthrootnext]; [D] = A;",
            "C = [VHGNDdepthrootq]; C + 1; C '* C; [VHGNDdepthrootnext] = C;",
            "A = [VHGNDdepthrootq]; C = [VHGNDdepthrootshift]; A < C;",
            "C = VHGNDhalfdepthroots; C + [VHGNDdepthrootp];",
            "? A >= 128 -> VHGND terrain half depth roots ready;",
            "[VHGNDdepthrootready] = 1;",
        ))
        and all(call not in depth_root_build for call in (
            "=> SU rnd;", "=> VHGND render random;", "=> FMul;", "=> FSqrt;",
        ))
        and all(token in depth for token in (
            "A = [VHGNDdepthrootready]; ? A = 0 -> VHGND tile depth root setup;",
            "A = [VHGNDdepthn]; ? A < 64 -> VHGND tile depth root setup;",
            "? A '>= 16384 -> VHGND tile depth root setup;",
            "C = A; A > 7; A + VHGNDhalfdepthroots; D = [A];",
            "A = C; A > 5; A & 3; A < 3; C = A; A = D; A > C; A & 255;",
            "[VHGNDdepthlo] = A;",
            "C = VHGNDdepthsquares; C + A; C = [C]; A < 1; A + 1; C + A;",
            "A = [VHGNDdepthlo]; A < 1; A + 1; C + A;",
            "A = [VHGNDdepthn]; ? A < C -> VHGND tile depth square terminal;",
            "A | 1; [VHGNDdepthmid] = A; [VHGNDdepthstep] = 0;",
            "-> VHGND tile depth root result;",
        ))
        and depth.count("? A < C -> VHGND tile depth square terminal;") == 2
        and depth.count("[VHGNDdepthlo]+;") == 2
        and "C '* C;" not in depth.split('"VHGND tile depth root setup"', 1)[0],
        "half-KiB terrain roots use exact square lookup corrections",
    )
    check(
        "A = [VHGNDh1]; A + [VHGNDseed]; A | 3; [SUfseed] = A;" in shade
        and all(token in shade for token in (
            "[m64a] = A; [m64b] = A; [SUfmask] = 7;",
            "B = A; A *%' B; [m64lo] = A; [m64hi] = B;",
            "C = A; C & 0FFh; B & 0FFh; C + B; C & 0FFh;",
            "A & 0FFFFFF00h; A | C; [SUfeax] = A;",
            "B = [SUfseed]; B + A; [SUfseed] = B;",
            "A & 7; [SUfval] = A; C = A;",
        ))
        and "=> SU fast srand;" not in shade
        and "=> VHGND render random;" not in shade
        and shade.count("C + 8; [VHGNDshade] = C;") == 1
        and "=> VHGND tile depth;" in tile
        and "A = [VHGNDrawdepth]; ? A > VHGNDFAR -> VHGND tile done;" in tile
        and "C = [VHGNDslo]; C + A;" in depth
        and '"VHGND tile depth x row"' in ground
        and all(token in depth for token in (
            '"VHGND tile depth z row"',
            "A + 8192; A - [VHGNDcamx];",
            "A + 8192; A - [VHGNDcamz];",
            "A - [VHGNDcamx]; B = A; A *% B; [VHGNDslo] = A; [VHGNDshi] = B;",
            "A - [VHGNDcamz]; B = A; A *% B;",
            "C = [VHGNDslo]; C + A;",
            "? C '>= A -> VHGND tile depth x sum ready; B + 1;",
            "B + [VHGNDshi]; -> VHGND tile depth sum ready;",
            "C = [VHGNDdlo]; C + A;",
            "? C '>= A -> VHGND tile depth z sum ready; B + 1;",
            "B + [VHGNDdhi];",
            "C > 28; A = B; A < 4; A | C; [VHGNDdepthn] = A;",
        ))
        and "[VHGNDdx] =" not in depth
        and "[VHGNDdz] =" not in depth
        and "[VHGNDdepthlo] = 0; [VHGNDdepthhi] = 64; [VHGNDdepthstep] = 6;" in depth
        and "A = [VHGNDdepthn]; ? A < 4096 -> VHGND tile depth root;" in depth
        and "[VHGNDdepthlo] = 64; [VHGNDdepthhi] = 128;" in depth
        and "A '* A; ? A <= [VHGNDdepthn] -> VHGND tile depth root low;" in depth
        and "[VHGNDdepthsq]" not in depth
        and all(call not in depth for call in (
            "=> IntToF;", "=> FMul;", "=> FAdd;", "=> FSqrt;", "=> FToIntChop;"
        ))
        and "? C '<= 32" in shade
        and all(token in vload for token in (
            "[FI] = [VHGNDvv]; [FA0] := [FI];",
            "A = [VHGNDvslot]; A + [VHGNDvi]; A + A; A + fw;",
            "[A] = [FA0]; [A plus 1] = [FA1];",
        ))
        and "=> PGF fromint;" not in vload
        and "=> PGF sa;" not in vload
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
            "VHCCULLBACK = 0C6000000h;", '"VHC capsule cull"',
            "[PJnrv] = 1; [PJmode] = 1; => PJ rotate;",
            "? A = 0 -> VHC render done;",
        ))
        and all(token in stick for token in (
            "VHSflare = 0; VHSphase = 0;", '"VHS luminous point"',
            "A = [VHSphase]; A & 1;", "C & 63; C + 8;",
            "A + RADPT; A + nw; D = A;", "[D] = 0;",
            "C = [VHScolor]; C & 255; [D plus 1] = C;",
            "A = [D]; A & 255;", "A & 192; C | A; [D] = C;",
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
            "=> service VHGND eye height;", '"VHGC slope scan loop"',
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
    object_view_setup = section(
        ground, '"VHGND object view setup"', '"VHGND object view cull"'
    )
    object_view_cull = section(
        ground, '"VHGND object view cull"', '"VHGND fauna view cull"'
    )
    tile_detail = section(tile, '"VHGND tile detail visible"', '"VHGND tile done"')
    fauna_tile = section(
        ground, '"VHGND render tile fauna"', '"VHGND fauna tiles build"'
    )
    fauna_tiles_build = section(
        ground, '"VHGND fauna tiles build"', '"VHGND fauna tile key store"'
    )
    fauna_tile_key = section(
        ground, '"VHGND fauna tile key store"', '"VHGND tile objects"'
    )
    rocks = section(ground, '"VHGND rock"', '"VHGND rock height"')
    object_cull_stamps: dict[int, int] = {}
    object_cull_payloads: dict[int, bool] = {}

    def object_cull_step(generation: int, frame_hit: bool, index: int,
                         count: int, computed: bool) -> tuple[str, bool]:
        if count == 0:
            return "empty", False
        if frame_hit and object_cull_stamps.get(index) == generation:
            return "hit", object_cull_payloads[index]
        object_cull_payloads[index] = computed
        object_cull_stamps[index] = generation
        return "fill", computed

    object_cull_empty = object_cull_step(1, False, 20001, 0, True)
    object_cull_fill1 = object_cull_step(1, False, 20001, 2, True)
    object_cull_hit1 = object_cull_step(1, True, 20001, 2, False)
    object_cull_fill2 = object_cull_step(2, False, 20001, 2, False)
    object_cull_hit2 = object_cull_step(2, True, 20001, 2, True)
    object_cull_stamps.clear()
    object_cull_wrap = object_cull_step(1, True, 20001, 2, True)
    object_cull_model_exact = (
        object_cull_empty == ("empty", False)
        and object_cull_fill1 == ("fill", True)
        and object_cull_hit1 == ("hit", True)
        and object_cull_fill2 == ("fill", False)
        and object_cull_hit2 == ("hit", False)
        and object_cull_wrap == ("fill", True)
    )

    fauna_types = (
        "mammal", "reptile", "bird", "mammal",
        "bird", "reptile", "mammal", "bird",
    )
    fauna_positions = (
        (10 * 16384, 10 * 16384), (-16384, -16384),
        (10 * 16384, 10 * 16384), (11 * 16384, 10 * 16384),
        (-3 * 16384, -2 * 16384), (50 * 16384, 50 * 16384),
        (203 * 16384, 205 * 16384), (-2 * 16384, -4 * 16384),
    )
    fauna_tiles = ((10, 10), (11, 10), (0, 0), (199, 199))
    fauna_relocations = {
        0: ((10 * 16384 + 123, 10 * 16384 + 456),),
        2: ((11 * 16384 + 7, 10 * 16384 + 8),
            (11 * 16384 + 77, 10 * 16384 + 88)),
        3: ((10 * 16384 + 3, 10 * 16384 + 4),),
        4: ((202 * 16384, 205 * 16384),
            (199 * 16384 + 1, 199 * 16384 + 2)),
        6: ((-3 * 16384, -4 * 16384),),
        7: ((-16384, -2 * 16384),),
    }

    def fauna_coord_tile(value: int) -> int:
        quotient = abs(value) // 16384
        if value < 0:
            quotient = -quotient
        return min(199, max(0, quotient))

    def fauna_key(record: dict[str, int]) -> int:
        return fauna_coord_tile(record["z"]) * 200 + fauna_coord_tile(record["x"])

    def fauna_records() -> dict[str, list[dict[str, int]]]:
        records: dict[str, list[dict[str, int]]] = {"mammal": [], "bird": []}
        for source_id, kind in enumerate(fauna_types):
            if kind in records:
                x, z = fauna_positions[source_id]
                records[kind].append({"id": source_id, "x": x, "z": z})
        return records

    def fauna_render(records: dict[str, list[dict[str, int]]],
                     counts: dict[int, int], source_id: int, kind: str,
                     compact_index: int) -> None:
        count = counts.get(source_id, 0)
        moves = fauna_relocations.get(source_id, ())
        if count < len(moves):
            records[kind][compact_index]["x"], records[kind][compact_index]["z"] = moves[count]
        counts[source_id] = count + 1

    def fauna_baseline_model() -> tuple[list[tuple[tuple[int, int], int, str, int]],
                                        dict[str, list[dict[str, int]]]]:
        records = fauna_records()
        rendered: list[tuple[tuple[int, int], int, str, int]] = []
        counts: dict[int, int] = {}
        for tile_xy in fauna_tiles:
            compact = {"mammal": 0, "bird": 0}
            while (compact["mammal"] < len(records["mammal"])
                   or compact["bird"] < len(records["bird"])):
                mammal_id = (records["mammal"][compact["mammal"]]["id"]
                              if compact["mammal"] < len(records["mammal"])
                              else 2147483647)
                bird_id = (records["bird"][compact["bird"]]["id"]
                            if compact["bird"] < len(records["bird"])
                            else 2147483647)
                kind = "mammal" if mammal_id < bird_id else "bird"
                compact_index = compact[kind]
                source_id = records[kind][compact_index]["id"]
                if fauna_key(records[kind][compact_index]) == tile_xy[1] * 200 + tile_xy[0]:
                    rendered.append((tile_xy, source_id, kind, compact_index))
                    fauna_render(records, counts, source_id, kind, compact_index)
                compact[kind] += 1
        return rendered, records

    def fauna_indexed_model() -> tuple[list[tuple[tuple[int, int], int, str, int]],
                                       dict[str, list[dict[str, int]]]]:
        records = fauna_records()
        keys: dict[int, int] = {}
        compact = {"mammal": 0, "bird": 0}
        for source_id, kind in enumerate(fauna_types):
            if kind in compact:
                keys[source_id] = fauna_key(records[kind][compact[kind]])
                compact[kind] += 1
        rendered: list[tuple[tuple[int, int], int, str, int]] = []
        counts: dict[int, int] = {}
        for tile_xy in fauna_tiles:
            compact = {"mammal": 0, "bird": 0}
            for source_id, kind in enumerate(fauna_types):
                if kind not in compact:
                    continue
                compact_index = compact[kind]
                if keys[source_id] == tile_xy[1] * 200 + tile_xy[0]:
                    rendered.append((tile_xy, source_id, kind, compact_index))
                    fauna_render(records, counts, source_id, kind, compact_index)
                    keys[source_id] = fauna_key(records[kind][compact_index])
                compact[kind] += 1
        return rendered, records

    fauna_baseline = fauna_baseline_model()
    fauna_indexed = fauna_indexed_model()
    fauna_expected_dispatch = [
        ((10, 10), 0, "mammal", 0), ((10, 10), 2, "bird", 0),
        ((11, 10), 2, "bird", 0), ((11, 10), 3, "mammal", 1),
        ((0, 0), 4, "bird", 1), ((0, 0), 7, "bird", 2),
        ((199, 199), 4, "bird", 1), ((199, 199), 6, "mammal", 2),
    ]
    fauna_model_exact = (
        fauna_baseline == fauna_indexed
        and fauna_indexed[0] == fauna_expected_dispatch
    )
    check(
        fauna_model_exact
        and "VHGNDfaunatiles = 100;" in ground
        and "VHGNDfaunamid" not in ground
        and "VHGNDfaunabid" not in ground
        and "=> VHGND fauna tile match;" not in ground
        and "A / VHGNDTS;" not in fauna_tile
        and contains_in_order(fauna_tile, (
            "[VHGNDfaunaid] = 0; [VHGNDmii] = 0; [VHGNDbii] = 0;",
            "C = VHGNDfaunatypes; C + A; A = [C];",
            "? A = 1 -> VHGND tile fauna bird; ? A = 5 -> VHGND tile fauna mammal;",
        ))
        and contains_in_order(section(
            fauna_tile, '"VHGND tile fauna bird"', '"VHGND tile fauna bird next"'
        ), (
            "C = VHGNDfaunatiles; C + [VHGNDfaunaid]; A = [C];",
            "[VHGNDanii] = [VHGNDbii]; => VHGND render birds;",
            "A = [VHGNDbii]; A '* 12; A + VHGNDbirddata; [VHGNDfaunap] = A;",
            "=> VHGND fauna tile key store;",
        ))
        and contains_in_order(section(
            fauna_tile, '"VHGND tile fauna mammal"', '"VHGND tile fauna mammal next"'
        ), (
            "C = VHGNDfaunatiles; C + [VHGNDfaunaid]; A = [C];",
            "[VHGNDanii] = [VHGNDmii]; => VHGND render animals;",
            "A = [VHGNDmii]; A '* 10; A + VHGNDanidata; [VHGNDfaunap] = A;",
            "=> VHGND fauna tile key store;",
        ))
        and contains_in_order(fauna_tiles_build, (
            "[VHGNDfaunaid] = 0; [VHGNDmii] = 0; [VHGNDbii] = 0;",
            "C = VHGNDfaunatypes; C + A; A = [C];",
            "? A = 1 -> VHGND fauna tile build bird; ? A = 5 -> VHGND fauna tile build mammal;",
            "A = [VHGNDbii]; A '* 12; A + VHGNDbirddata; [VHGNDfaunap] = A;",
            "=> VHGND fauna tile key store; [VHGNDbii]+;",
            "A = [VHGNDmii]; A '* 10; A + VHGNDanidata; [VHGNDfaunap] = A;",
            "=> VHGND fauna tile key store; [VHGNDmii]+;",
        ))
        and fauna_tile_key.count("A / VHGNDTS;") == 2
        and contains_in_order(fauna_tile_key, (
            "C = [VHGNDfaunap]; A = [C]; A / VHGNDTS;",
            "? A >= 0 -> VHGND fauna tile key x high; A = 0;",
            "? A '<= 199 -> VHGND fauna tile key x ready; A = 199;",
            "[VHGNDfaunatilex] = A;",
            "A = [C plus 1]; A / VHGNDTS;",
            "? A >= 0 -> VHGND fauna tile key z high; A = 0;",
            "? A '<= 199 -> VHGND fauna tile key z ready; A = 199;",
            "A '* VHGNDMAP; A + [VHGNDfaunatilex];",
            "C = VHGNDfaunatiles; C + [VHGNDfaunaid]; [C] = A;",
        )),
        "mutable fauna tile keys preserve source order, clamping, and same-frame migration",
    )
    check(
        '"VHGND felisian line"' in post
        and "A & 0FCh; A | [VHGNDoval]" in post
        and object_cull_model_exact
        and "[VHGNDobjbyte] = A; A & 3; [VHGNDocount] = A;" in tile_detail
        and tile_detail.index("=> VHGND render tile fauna;")
        < tile_detail.index("[VHGNDobjbyte] = A; A & 3; [VHGNDocount] = A;")
        < tile_detail.index("? A = 0 -> VHGND tile done;")
        < tile_detail.index("A = [VHGNDvcframehit]; ? A = 0 -> VHGND tile object view cache miss;")
        and "A = [VHGNDvcgen]; ? A != C -> VHGND tile object view cache miss;" in tile_detail
        and "A = VHGNDvcobjvisible; A + [VHGNDh1]; A = [A]; [VHGNDviewrz] = A;" in tile_detail
        and "=> VHGND object view cull;" in tile_detail
        and tile_detail.index(
            "A = VHGNDvcobjvisible; A + [VHGNDh1]; C = [VHGNDviewrz]; [A] = C;"
        ) < tile_detail.index(
            "A = VHGNDvcobjstamp; A + [VHGNDh1]; C = [VHGNDvcgen]; [A] = C;"
        )
        and "A = [VHGNDviewrz]; ? A = 0 -> VHGND tile done;" in tile_detail
        and "ROBJ" not in objects
        and (
            '"VHGND object view cache clear"\n'
            "\tA = VHGNDvcobjstamp; A + [VHGNDptr]; [A] = 0;"
        ) in ground
        and '"VHGND type3 done"' in ground
        and "C = 5; => SU rnd; ? C != 0 -> VHGND build surface done;" in ground
        and "[SUfmask] = [VHGNDrockdensity]" in rocks
        and rocks.count("=> PG facing;") == 4
        and rocks.count("=> PG poly3d;") == 2
        and rocks.count("=> PG polymap;") == 1
        and rocks.index("( base point 0:") < rocks.index("[SUfmask] = 63;")
        < rocks.index("( apex height =")
        and all(token in rocks for token in (
            "A = [VHGNDdepth]; ? A > 2 -> VHGND rock distant;",
            '"VHGND rock distant"', "[SUfmask] = 71; => VHGND render random; [DBcol] = C;",
            "=> PG facing; A = [FCret]; ? A = 0 -> VHGND rock done;",
            '"VHGND rock repeat"', "A '* 5; [VHGNDrockworkscale] = A;",
            "[SPflar] = [VHGNDquartz]; [DBflar] = [VHGNDquartz];",
            "A = [VHGNDdepth]; ? A >= 2 -> VHGND rock draw solid;",
            "[PJnrv] = 4; => PG polymap;", "[PJnrv] = 3; => PG poly3d;",
            "A '* 1000; A '* [VHGNDcdown];", "A '/ 2; [VHGNDrockworkscale] = A;",
            "[VHGNDcdown]-; A = [VHGNDcdown]; ? A > 0 -> VHGND rock repeat;",
        )),
        "rocks retain source RNG order, facing, quartz mapping, and distant triangles",
    )
    traversal = section(ground, '"VHGND render"', '"VHGND tile"')
    faithful = section(ground, '"VHGND traverse faithful"',
                       '"VHGND object view setup"')
    terrain_cache = section(ground, '"VHGND terrain cache frame"',
                            '"VHGND terrain vertex index"')
    terrain_vertex_ensure = section(
        ground,
        '"VHGND terrain vertex ensure"',
        '"VHGND terrain vertex load"',
    )
    terrain_project_one = section(
        pgproj,
        '"PJ terrain project one"',
        '"PJ emit1"',
    )
    terrain_common = section(
        ground,
        '"VHGND terrain common input"',
        '"VHGND terrain common input fallback"',
    )
    terrain_common_fallback = section(
        ground,
        '"VHGND terrain common input fallback"',
        '"VHGND terrain remaining input"',
    )
    terrain_remaining = section(
        ground,
        '"VHGND terrain remaining input"',
        '"VHGND terrain cache frame"',
    )
    terrain_mapped = section(ground, '"VHGND terrain mapped"',
                             '"VHGND terrain facing"')
    terrain_raster = section(
        ground,
        '"VHGND terrain mapped basis ready"',
        '"VHGND terrain facing"',
    )
    terrain_raster_replay = section(
        pgtex,
        '"PG terrain replay"',
        '"PG terrain state save"',
    )
    terrain_culling_replay = game.split('"PG terrain replay culling"', 1)[1]
    terrain_culling_scratch = section(
        terrain_culling_replay,
        '"PG terrain replay culling scratch"',
        '"PG terrain replay culling pair"',
    )
    terrain_culling_pair = terrain_culling_replay.split(
        '"PG terrain replay culling pair"', 1
    )[1]
    terrain_state_save = section(
        pgtex,
        '"PG terrain state save"',
        '"PG terrain state load"',
    )
    terrain_state_load = section(
        pgtex,
        '"PG terrain state load"',
        "( ==================================================================== )",
    )
    terrain_px_record = section(
        pgtex,
        '"PG px terrain record begin"',
        '"PG px internal"',
    )
    terrain_cpx_record = section(
        pgtex,
        '"PG cpx terrain record begin"',
        '"PG cpx internal"',
    )
    terrain_basis_hoist = section(
        terrain_mapped,
        "[SPterrain] = 0;",
        '"VHGND terrain mapped cache select"',
    )
    terrain_basis_second = section(
        terrain_basis_hoist,
        '"VHGND terrain mapped basis second"',
        '"VHGND terrain mapped cache select"',
    )
    terrain_pair = section(
        terrain_mapped,
        '"VHGND terrain mapped cache second select"',
        '"VHGND terrain mapped cache second"',
    )
    terrain_behind = section(
        terrain_mapped,
        '"VHGND terrain mapped cache first behind"',
        '"VHGND terrain mapped ensure begin"',
    )
    terrain_first_load = section(
        terrain_mapped,
        '"VHGND terrain mapped load begin"',
        '"VHGND terrain mapped load generic begin"',
    )
    terrain_generic_load = section(
        terrain_mapped,
        '"VHGND terrain mapped load generic begin"',
        '"VHGND terrain mapped bounds"',
    )
    terrain_facing = section(ground, '"VHGND terrain facing"',
                             '"VHGND secondary sun setup"')
    vertex_load = section(
        ground,
        '"VHGND terrain vertex load"',
        '"VHGND terrain cached bounds"',
    )
    terrain_basis_hit = section(
        pgproj,
        '"PJ vectors terrain"',
        '"PJ vectors terrain build"',
    )
    tree_basis_dispatch = section(
        pgproj,
        '"PJ vectors"',
        '"PJ vectors generic"',
    )
    tree_basis_entry = section(
        pgproj,
        '"PJ vectors tree triangle"',
        '"PJ vectors generic"',
    )
    three_basis_build = section(
        pgproj,
        '"PJ vectors three build"',
        '"PJ vc scale"',
    )
    tree_rotate = section(
        pgproj,
        '"PJ rotate fixed map"',
        '"PJ zemit"',
    )
    tree_rotate_dispatch = section(
        pgproj,
        '"PG pm r"',
        '"PG pm duplicate rotated generic"',
    )
    leaf_front_dispatch = section(
        pgproj,
        '"PG pm rotated"',
        '"PG pm clip"',
    )
    leaf_front_project = section(
        pgproj,
        '"PJ leaf front projectmap"',
        '"PJ terrain project one"',
    )
    leaf_trace_control = section(
        pgproj,
        '"PG trace"',
        '"PG polymap"',
    )
    leaf_trace_dispatch = section(
        pgproj,
        '"PG pm traced"',
        '"PG pm out"',
    )
    tree_leaf_scope = section(
        ground,
        '"VHGND tree leaves"',
        '"VHGND tree leaf tip vertex"',
    )
    terrain_basis_build = section(
        pgproj,
        '"PJ vectors terrain build"',
        '"PJ vc scale"',
    )
    terrain_pair_indices_exact = all(
        0 <= index < 40000
        for x in (0, 1, 99, 198)
        for z in (0, 1, 99, 198)
        for h1 in (z * 200 + x,)
        for index in (h1, h1 + 1, h1 + 200, h1 + 201)
    )
    terrain_pair_layout_exact = all(
        (first[1], vertex_words(h1 + 201), first[2])
        == tuple(vertex_words(index) for index in (h1 + 1, h1 + 201, h1 + 200))
        for h1 in (0, 1, 198, 19900, 39798)
        for vertex_words in (
            lambda index: tuple(
                (index * 0x9E3779B1 + word * 0x7F4A7C15) & 0xFFFFFFFF
                for word in range(8)
            ),
        )
        for first in ((
            vertex_words(h1), vertex_words(h1 + 1), vertex_words(h1 + 200)
        ),)
    )
    terrain_behind_cache_copies_exact = all(
        f"A = {source}; A + D; C = [A]; [fw plus {destination + slot * 2}] = C;"
        in terrain_behind
        for source, destination in (
            ("VHGNDvcrx0", 64), ("VHGNDvcrx1", 65),
            ("VHGNDvcry0", 72), ("VHGNDvcry1", 73),
            ("VHGNDvcrz0", 80), ("VHGNDvcrz1", 81),
        )
        for slot in range(3)
    )
    terrain_first_load_copies_exact = all(
        f"A = {source}; A + D; C = [A]; [{destination}] = C;"
        in terrain_first_load
        for source, destination in (
            ("VHGNDvcrx0", "fw plus 64"),
            ("VHGNDvcrx1", "fw plus 65"),
            ("VHGNDvcry0", "fw plus 72"),
            ("VHGNDvcry1", "fw plus 73"),
            ("VHGNDvcrz0", "fw plus 80"),
            ("VHGNDvcrz1", "fw plus 81"),
            ("VHGNDvcpx", "mp"),
            ("VHGNDvcpy", "mp plus 1"),
            ("VHGNDvcrx0", "fw plus 66"),
            ("VHGNDvcrx1", "fw plus 67"),
            ("VHGNDvcry0", "fw plus 74"),
            ("VHGNDvcry1", "fw plus 75"),
            ("VHGNDvcrz0", "fw plus 82"),
            ("VHGNDvcrz1", "fw plus 83"),
            ("VHGNDvcpx", "mp plus 2"),
            ("VHGNDvcpy", "mp plus 3"),
            ("VHGNDvcrx0", "fw plus 68"),
            ("VHGNDvcrx1", "fw plus 69"),
            ("VHGNDvcry0", "fw plus 76"),
            ("VHGNDvcry1", "fw plus 77"),
            ("VHGNDvcrz0", "fw plus 84"),
            ("VHGNDvcrz1", "fw plus 85"),
            ("VHGNDvcpx", "mp plus 4"),
            ("VHGNDvcpy", "mp plus 5"),
        )
    )
    terrain_basis_indices_exact = all(
        0 <= index < 80000
        and 0 <= index * 18
        and index * 18 + 17 < 1440000
        for x in range(199)
        for z in range(199)
        for h1 in (z * 200 + x,)
        for tri in (0, 1)
        for index in (h1 * 2 + tri,)
    )
    terrain_basis_hit_copies_exact = all(
        (
            f"[fw{' plus ' + str(word) if word else ''}] = "
            f"[D{' plus ' + str(word) if word else ''}];"
        ) in terrain_basis_hit
        for word in range(18)
    )
    terrain_basis_store_copies_exact = all(
        (
            f"[D{' plus ' + str(word) if word else ''}] = "
            f"[fw{' plus ' + str(word) if word else ''}];"
        ) in terrain_mapped
        for word in range(18)
    )

    basis_stamps: dict[int, int] = {}
    basis_payload: dict[int, tuple[int, ...]] = {}

    def terrain_basis_step(generation: int, frame_hit: bool, index: int,
                           built: tuple[int, ...]) -> tuple[tuple[int, ...], str]:
        if frame_hit and basis_stamps.get(index) == generation:
            return basis_payload[index], "hit"
        if frame_hit:
            basis_payload[index] = built
            basis_stamps[index] = generation
            return built, "fill"
        return built, "bypass"

    basis_index = 39798 * 2 + 1
    basis_words1 = tuple(
        (0x13579BDF + word * 0x10203041) & 0xFFFFFFFF
        for word in range(18)
    )
    basis_words2 = tuple(word ^ 0xFFFFFFFF for word in basis_words1)
    basis_words3 = tuple((word + 0x76543210) & 0xFFFFFFFF for word in basis_words1)
    basis_bypass, basis_bypass_mode = terrain_basis_step(
        1, False, basis_index, basis_words1
    )
    basis_fill1, basis_fill1_mode = terrain_basis_step(
        1, True, basis_index, basis_words1
    )
    basis_hit1, basis_hit1_mode = terrain_basis_step(
        1, True, basis_index, basis_words2
    )
    basis_move, basis_move_mode = terrain_basis_step(
        2, False, basis_index, basis_words2
    )
    basis_fill2, basis_fill2_mode = terrain_basis_step(
        2, True, basis_index, basis_words2
    )
    basis_hit2, basis_hit2_mode = terrain_basis_step(
        2, True, basis_index, basis_words3
    )
    basis_surface, basis_surface_mode = terrain_basis_step(
        3, False, basis_index, basis_words3
    )
    basis_fill3, basis_fill3_mode = terrain_basis_step(
        3, True, basis_index, basis_words3
    )
    basis_stamps.clear()
    basis_wrap, basis_wrap_mode = terrain_basis_step(
        1, True, basis_index, basis_words1
    )
    terrain_basis_cache_model_exact = (
        basis_bypass_mode == "bypass"
        and basis_fill1_mode == "fill"
        and basis_hit1_mode == "hit"
        and basis_move_mode == "bypass"
        and basis_fill2_mode == "fill"
        and basis_hit2_mode == "hit"
        and basis_surface_mode == "bypass"
        and basis_fill3_mode == "fill"
        and basis_wrap_mode == "fill"
        and basis_bypass == basis_fill1 == basis_hit1 == basis_words1
        and basis_move == basis_fill2 == basis_hit2 == basis_words2
        and basis_surface == basis_fill3 == basis_words3
        and basis_wrap == basis_words1
    )

    state_save_words = {
        int(offset or 0): source
        for offset, source in re.findall(
            r"\[D(?: plus (\d+))?\] = \[([^\]]+)\];",
            terrain_state_save,
        )
    }
    state_load_words = {
        int(offset or 0): destination
        for destination, offset in re.findall(
            r"\[([^\]]+)\] = \[D(?: plus (\d+))?\];",
            terrain_state_load,
        )
    }
    terrain_state_layout_exact = (
        len(state_save_words) == 118
        and tuple(sorted(state_save_words)) == tuple(range(118))
        and state_load_words == state_save_words
    )

    def replay_culling_commands(packed: tuple[int, ...]) -> tuple[tuple[int, int], ...]:
        replayed = [
            (command >> 16, command & 0xFFFF)
            for command in packed[:2]
        ]
        for index in range(2, len(packed), 2):
            first = packed[index]
            second = packed[index + 1]
            assert second == first + 0x10000
            offset = first >> 16
            value = first & 0xFFFF
            replayed.extend(((offset, value), (offset + 1, value)))
        return tuple(replayed)

    culling_replay_model_exact = all(
        replay_culling_commands(tuple(
            (offset << 16) | value for offset, value in commands
        )) == commands
        for pair_count in (0, 1, 2, 17, 255)
        for first_offset in (0, 31_000, 61_113)
        for commands in ((
            ((63_996, 17), (63_997, 29))
            + tuple(
                command
                for pair in range(pair_count)
                for command in (
                    (first_offset + 2 * pair, (pair * 73 + 255) & 255),
                    (first_offset + 2 * pair + 1, (pair * 73 + 255) & 255),
                )
            )
        ),)
        if not pair_count or first_offset + 2 * pair_count - 1 < 65_536
    )

    raster_stamps: dict[int, int] = {}
    raster_records: dict[int, tuple[tuple[int, ...], tuple[int, ...]]] = {}
    raster_stream_words = 0

    def terrain_raster_step(
        generation: int,
        frame_hit: bool,
        index: int,
        pixels: tuple[tuple[int, int], ...],
        terminal: tuple[int, ...],
        capacity_words: int = 2_000_000,
    ) -> tuple[str, tuple[tuple[int, int], ...], tuple[int, ...], int]:
        nonlocal raster_stream_words
        scratch = ((63_996, 17), (63_997, 29))
        if not frame_hit:
            return "bypass", scratch + pixels, terminal, len(pixels)
        if raster_stamps.get(index) == generation:
            packed_commands, recorded_terminal = raster_records[index]
            commands = tuple(
                (command >> 16, command & 0xFFFF)
                for command in packed_commands
            )
            return "hit", commands, recorded_terminal, len(commands) - 2
        reserve = 60_118
        if raster_stream_words + reserve > capacity_words:
            return "overflow", scratch + pixels, terminal, len(pixels)
        commands = scratch + pixels
        assert all(0 <= offset <= 0xFFFF and 0 <= value <= 0xFF
                   for offset, value in commands)
        packed_commands = tuple(
            (offset << 16) | value for offset, value in commands
        )
        raster_stream_words += len(packed_commands) + 118
        raster_records[index] = (packed_commands, terminal)
        raster_stamps[index] = generation
        return ("empty-fill" if not pixels else "fill"), commands, terminal, len(pixels)

    raster_pixels = ((0x2004, 41), (0x2005, 42), (0x2004, 43))
    raster_terminal = tuple((word * 0x10203 + 7) & 0xFFFFFFFF for word in range(118))
    raster_bypass = terrain_raster_step(1, False, 123, raster_pixels, raster_terminal)
    raster_bypass_unpublished = 123 not in raster_stamps
    raster_fill = terrain_raster_step(1, True, 123, raster_pixels, raster_terminal)
    raster_hit = terrain_raster_step(1, True, 123, (), tuple(reversed(raster_terminal)))
    raster_empty_fill = terrain_raster_step(1, True, 124, (), raster_terminal)
    raster_empty_hit = terrain_raster_step(1, True, 124, raster_pixels, raster_terminal)
    raster_overflow = terrain_raster_step(
        1, True, 125, raster_pixels, raster_terminal, raster_stream_words
    )
    raster_stream_words = 0
    raster_generation_fill = terrain_raster_step(2, True, 123, raster_pixels, raster_terminal)
    raster_stamps.clear()
    raster_stream_words = 0
    raster_wrap_fill = terrain_raster_step(1, True, 123, raster_pixels, raster_terminal)
    terrain_raster_cache_model_exact = (
        raster_bypass[0] == "bypass"
        and raster_bypass_unpublished
        and raster_fill[0] == "fill"
        and raster_hit == ("hit", raster_fill[1], raster_terminal, 3)
        and raster_hit[1][2:] == raster_pixels
        and raster_empty_fill[0] == "empty-fill"
        and raster_empty_hit[0] == "hit"
        and raster_empty_hit[1:] == (raster_empty_fill[1], raster_terminal, 0)
        and raster_overflow[0] == "overflow"
        and 125 not in raster_stamps
        and raster_generation_fill[0] == "fill"
        and raster_wrap_fill[0] == "fill"
    )
    faithful_cases = tuple(
        (cam_x, cam_z, faithful_tiles(cam_x, cam_z, direction, backspan))
        for cam_x, cam_z in ((0, 0), (0, 198), (100, 100), (198, 0), (198, 198))
        for direction in ("north", "south", "east", "west")
        for backspan in (1, 4)
    )
    faithful_guard_exact = all(
        tiles
        and all(0 <= x <= 198 and 0 <= z <= 198
                and abs(x - cam_x) + abs(z - cam_z) <= 90
                for x, z in tiles)
        for cam_x, cam_z, tiles in faithful_cases
    )
    lod_rows = ((1, 200), (8, 1600), (16, 3200))
    check(
        all(step * 200 == row for step, row in lod_rows)
        and "VHGNDlodstep = 1; VHGNDlodrow = 200;" in ground
        and ground.count(
            "[VHGNDlodstep] = 1; [VHGNDlodrow] = 200;"
        ) == 3
        and "[VHGNDlodstep] = 8; [VHGNDlodrow] = 1600;" in ground
        and "[VHGNDlodstep] = 16; [VHGNDlodrow] = 3200;" in ground
        and "C = [VHGNDlodrow];" in tile
        and tile.count("A = [VHGNDlodrow];") == 2
        and "C = [VHGNDlodstep]; C '* VHGNDMAP;" not in tile
        and "A = [VHGNDlodstep]; A '* VHGNDMAP;" not in tile,
        "terrain caches each exact LOD map-row stride",
    )
    check(
        "VHGNDdroptx = 0; VHGNDdroptz = 0;" in ground
        and all(token in faithful for token in (
            "A = [VHGNDdropx]; A / VHGNDTS; [VHGNDdroptx] = A;",
            "A = [VHGNDdropz]; A / VHGNDTS; [VHGNDdroptz] = A;",
        ))
        and all(token in capsule_tile_gate for token in (
            "A = [VHGNDdroptx]; ? A != [VHGNDx] -> VHGND tile capsule done;",
            "A = [VHGNDdroptz]; ? A != [VHGNDz] -> VHGND tile capsule done;",
        ))
        and "A / VHGNDTS;" not in capsule_tile_gate,
        "settled-capsule tile coordinates are cached outside faithful traversal",
    )
    check(
        "VHGNDFAR = 64" in ground
        and "iperficie (1);" in original1
        and "iperficie (4);" in original1
        and all(token in traversal for token in (
            "=> VHGND traverse faithful;", "[VHGNDlodstep] = 1; [VHGNDlodrow] = 200; [VHGNDlodradius] = 65;",
            "[VHGNDbackspan] = 1;", "[VHGNDbackspan] = 4;",
            "A - [VHGNDbackspan]; [VHGNDzlo] = A;",
            "A + [VHGNDbackspan]; [VHGNDzhi] = A;",
            "A + [VHGNDbackspan]; [VHGNDxhi] = A;",
            "A - [VHGNDbackspan]; [VHGNDxlo] = A;",
            '"VHGND faithful x row bounds"', '"VHGND faithful z row bounds"',
            "A = 90; A - [VHGNDtmp]; [VHGNDtmp] = A;",
            "? A <= 65 -> VHGND faithful x row span ready;",
            "? A <= 65 -> VHGND faithful z row span ready;",
            "=> VHGND faithful x row bounds; [VHGNDx] = [VHGNDxlo];",
            "=> VHGND faithful z row bounds; [VHGNDz] = [VHGNDzhi];",
            "A = [VHGNDz]; A < 14; A + 8192; C = [VHGNDcamz]; C - A; [VHGNDdz] = C;",
            "A = [VHGNDx]; A < 14; A + 8192; C = [VHGNDcamx]; C - A; [VHGNDdx] = C;",
            '"VHGND faithful north"', '"VHGND faithful east"',
            '"VHGND faithful south"', '"VHGND faithful west"',
        ))
        and faithful_guard_exact
        and faithful.count("=> VHGND tile source x row ready;") == 4
        and faithful.count("=> VHGND tile source z row ready;") == 4
        and "=> VHGND tile source range ready;" not in faithful
        and "=> VHGND tile;" not in faithful
        and "? A > 90 -> VHGND tile done;" in tile
        and "[SPcull] = 1" in tile
        and "A > [VHGNDmaxdepth]" in tile,
        "surface renderer hoists exact row bounds and one depth square while retaining painter order and depth-64 gates",
    )
    check(
        all(token in pgfp for token in (
            "FSDPP\t= 25;", "FSXC\t= 19;", "FSYC\t= 20;",
            "FSUX\t= 48;", "FSUY\t= 56;", "FSUZ\t= 64;",
            "FSW0\t= 248;\tFSW1\t= 249;\tFSW2\t= 250;\tFSW3\t= 251;",
        ))
        and contains_in_order(terrain_project_one, (
            "[FA0] = [fw plus 50]; [FA1] = [fw plus 51];",
            "[FA0] /: [fw plus 128];",
            "[fw plus 502] = [FA0]; [fw plus 503] = [FA1];",
            "[FA0] *: [fw plus 96];",
            "[FA0] +: [fw plus 38];",
            "[FI] =: [FA0]; [mp] = [FI];",
            "[FA0] = [fw plus 502]; [FA1] = [fw plus 503];",
            "[FA0] *: [fw plus 112];",
            "[FA0] +: [fw plus 40];",
            "[FI] =: [FA0]; [mp plus 1] = [FI];",
        ))
        and terrain_project_one.count("/: [fw plus 128];") == 1
        and terrain_project_one.count("*: [fw plus") == 2
        and terrain_project_one.count("+: [fw plus") == 2
        and terrain_project_one.count("[FI] =: [FA0];") == 2
        and "=> PGF" not in terrain_project_one
        and "PJminx" not in terrain_project_one
        and "PJmaxx" not in terrain_project_one
        and "BXminy" not in terrain_project_one
        and "BXmaxy" not in terrain_project_one
        and "=> PJ terrain project one;" in terrain_vertex_ensure
        and "=> PJ projectmap;" not in terrain_vertex_ensure,
        "terrain cache misses project one fixed-slot vertex without discarded bounds",
    )
    check(
        "D = [VHGNDvi]; D + D; D + FSRXF plus FSRXF plus fw;" in vertex_load
        and vertex_load.count("D + 8;") == 2
        and "A = [VHGNDvi]; A + FSRYF;" not in vertex_load
        and "A = [VHGNDvi]; A + FSRZF;" not in vertex_load,
        "terrain cache loads walk contiguous rotated carrier slots",
    )
    check(
        "VHGNDvcbasisstamp = 80000; VHGNDvcbasis = 1440000;" in ground
        and terrain_basis_indices_exact
        and terrain_basis_hit_copies_exact
        and terrain_basis_store_copies_exact
        and terrain_basis_cache_model_exact
        and all(token in terrain_basis_hit for token in (
            "[PJdx] = 3;",
            "A = [PJterrainbasisreuse]; ? A = 0 -> PJ vectors terrain build;",
            "D = [PJterrainbasisp];",
            "[PJvr] = 3; [PJvv] = 2;",
        ))
        and not any(operator in terrain_basis_hit for operator in (
            "++", "--", "**", "//", "+:", "-:", "*:", "/:", "=:", ":=", "~:"
        ))
        and "[PJterrainbasisbuilt] = 1;" in terrain_basis_build
        and all(token in terrain_mapped for token in (
            "[PJterrainbasisreuse] = 0; [PJterrainbasisbuilt] = 0;",
            "A = [VHGNDvcframehit]; ? A = 0 -> VHGND terrain mapped cache select;",
            "A = VHGNDvcbasisstamp; A + [VHGNDnormindex]; C = [A];",
            "A = [VHGNDvcgen]; ? A != C -> VHGND terrain mapped cache select;",
            "A = [VHGNDnormindex]; A '* 18; A + VHGNDvcbasis; [PJterrainbasisp] = A;",
            "[PJterrainbasisreuse] = 1;",
            "A = [PJterrainbasisreuse]; ? A != 0 -> VHGND terrain mapped done;",
            "A = [PJterrainbasisbuilt]; ? A = 0 -> VHGND terrain mapped done;",
            "A = [VHGNDnormindex]; A '* 18; A + VHGNDvcbasis; D = A;",
            "A = VHGNDvcbasisstamp; A + [VHGNDnormindex]; C = [VHGNDvcgen]; [A] = C;",
        ))
        and contains_in_order(terrain_basis_hoist, (
            "A = [VHGNDmirror]; ? A != 0 -> VHGND terrain mapped generic;",
            "[PJterrainbasisreuse] = 0; [PJterrainbasisbuilt] = 0;",
            "A = [VHGNDvcframehit]; ? A = 0 -> VHGND terrain mapped cache select;",
            "A = VHGNDvcbasisstamp; A + [VHGNDnormindex]; C = [A];",
            "A = [VHGNDvcgen]; ? A != C -> VHGND terrain mapped cache select;",
            "A = [VHGNDnormindex]; A '* 18; A + VHGNDvcbasis; [PJterrainbasisp] = A;",
            "[PJterrainbasisreuse] = 1;",
            "A = [VHGNDvctri]; ? A != 0 -> VHGND terrain mapped basis second;",
            "-> VHGND terrain mapped load first;",
        ))
        and contains_in_order(terrain_basis_second, (
            "A = [VHGNDvcpairready]; ? A = 0 -> VHGND terrain mapped load generic begin;",
            "D = [VHGNDh1]; D + 201; -> VHGND terrain mapped cache second payload;",
        ))
        and terrain_mapped.count(
            "A = VHGNDvcbasisstamp; A + [VHGNDnormindex]; C = [A];"
        ) == 1
        and terrain_mapped.index(
            "A = VHGNDvcbasisstamp; A + [VHGNDnormindex]; C = [A];"
        ) < terrain_mapped.index("A = VHGNDvcstamp;")
        and terrain_mapped.index("=> VHGND terrain cached bounds;")
        < terrain_mapped.index('"VHGND terrain mapped basis ready"')
        and terrain_mapped.index("[PJterrainbasisreuse] = 1;")
        < terrain_mapped.index('"VHGND terrain mapped cache select"')
        and terrain_mapped.index("[D plus 17] = [fw plus 17];")
        < terrain_mapped.index(
            "A = VHGNDvcbasisstamp; A + [VHGNDnormindex]; C = [VHGNDvcgen]; [A] = C;"
        )
        and all(token in terrain_cache for token in (
            '"VHGND terrain basis cache clear"',
            "A = VHGNDvcbasisstamp; A + [VHGNDptr]; [A] = 0;",
            "? A < 80000 -> VHGND terrain basis cache clear;",
        ))
        and contains_in_order(terrain_clip, (
            '"PG pm terrain edges"',
            "=> PG edges;",
            "A = [PJterrainbasisreuse]; ? A != 0 -> PG pm basis;",
            "[SPi] = [BXminy];",
            '"PG pm terrain span"',
            "? D > 0 -> PG pm basis;",
        ))
        and "=> PJ vectors;" in terrain_basis_entry,
        "generation-stamped terrain bases hoist proof ahead of vertex ladders",
    )
    check(
        "PGTRCAP = 2000000;" in pgtex
        and "PGTRSTATE = 118;" in pgtex
        and "PGtrcommands = 2000000;" in pgtex
        and "VHGNDvcrasterstamp = 80000;" in ground
        and "VHGNDvcrasterstarts = 80000; VHGNDvcrastercounts = 80000;" in ground
        and terrain_state_layout_exact
        and terrain_raster_cache_model_exact
        and culling_replay_model_exact
        and contains_in_order(terrain_raster_replay, (
            "B = [PGtrstart]; E = [PGtrcount];",
            "A = [SPcull]; A & 1; ? A != 0 -> PG terrain replay culling;",
            "A = PGtrcommands; A + B; D = [A]; C = D; C & 65535; D > 16;",
            "[D plus SADPT plus nw] = C;",
            "B+; E-; ? E != 0 -> PG terrain replay write;",
            "A = B;",
            '"PG terrain replay finish"',
            "[PGtrp] = B; [PGtrn] = E;",
            "A+; A-; A+; A-;",
            "A = [PGtrcount]; A - 2; C = [CSpix]; A + C; [CSpix] = A;",
            "=> PG terrain state load;",
        ))
        and terrain_raster_replay.count("[PGtrp] = B; [PGtrn] = E;") == 1
        and terrain_raster_replay.count(
            "A = PGtrcommands; A + B; D = [A]; C = D; C & 65535; D > 16;"
        ) == 1
        and contains_in_order(terrain_culling_scratch, (
            "A = PGtrcommands; A + B; D = [A]; C = D; C & 65535; D > 16;",
            "[D plus SADPT plus nw] = C;",
            "B+; E-; ? E != 0 -> PG terrain replay culling scratch;",
            "A = B;",
            "E = [PGtrcount]; E > 1; E-;",
            "? E = 0 -> PG terrain replay finish;",
        ))
        and terrain_culling_scratch.count(
            "A = PGtrcommands; A + B; D = [A]; C = D; C & 65535; D > 16;"
        ) == 1
        and contains_in_order(terrain_culling_pair, (
            "D = [B relating PGtrcommands]; C = D; C & 65535; D > 16;",
            "[D plus SADPT plus nw] = C;",
            "[D plus 1 plus SADPT plus nw] = C;",
            "B+; B+; E-; ? E != 0 -> PG terrain replay culling pair;",
            "-> PG terrain replay finish;",
            "A = B;",
            "A = 0; A+; A+; A+;",
        ))
        and terrain_culling_pair.count(
            "D = [B relating PGtrcommands]; C = D; C & 65535; D > 16;"
        ) == 1
        and "A = PGtrcommands; A + B;" not in terrain_culling_pair
        and terrain_culling_pair.count("[D plus SADPT plus nw] = C;") == 1
        and terrain_culling_pair.count(
            "[D plus 1 plus SADPT plus nw] = C;"
        ) == 1
        and "D+;" not in terrain_culling_pair
        and "[A plus 1]" not in terrain_culling_pair
        and terrain_culling_pair.strip().endswith("A = 0; A+; A+; A+;")
        and game.rfind('"PG terrain replay culling"') > game.rfind('"VHG write sentinel"')
        and contains_in_order(tile, (
            "[SPcull] = 0; A = [VHGNDsctype]; ? A != 3 -> VHGND tile cull normal;",
            "A = [VHGNDdepth]; ? A '>= 4 -> VHGND tile cull ready; [SPcull] = 1;",
            '"VHGND tile cull normal"',
            "A = [VHGNDdepth]; ? A < 4 -> VHGND tile cull ready; [SPcull] = 1;",
            '"VHGND tile cull ready"',
            "A = [VHGNDmirror]; ? A = 0 -> VHGND tile mirror cull ready; [SPcull] = 0;",
        ))
        and "[SPcull] =" not in terrain_mapped
        and "A + [PGtrp]" not in terrain_raster_replay
        and "[PGtrn]-" not in terrain_raster_replay
        and not any(token in terrain_raster_replay for token in (
            "PG edges", "PG pm terrain span", "PG trace", "PG uv next", "PG texel"
        ))
        and terrain_px_record.count("[PGtrval] = E;") == 3
        and terrain_px_record.count(
            "E = A; E + 3; E < 16; E | [PGtrval]; [D] = E;"
        ) == 3
        and terrain_px_record.count(
            "E = [PGtrused]; E+; [PGtrused] = E; [PGtrcount]+;"
        ) == 3
        and terrain_px_record.count("D + 0; D + 0; D+; D+; D+;") == 3
        and "E < 16; [PGtrval] = E;" not in terrain_px_record
        and terrain_cpx_record.count("[PGtrval] = E;") == 3
        and terrain_cpx_record.count("E - SADPT plus nw;") == 3
        and terrain_cpx_record.count(
            "E + 2; E < 16; E | [PGtrval]; [D] = E;"
        ) == 3
        and terrain_cpx_record.count("E + 65536; [D plus 1] = E;") == 3
        and terrain_cpx_record.count(
            "E = [PGtrused]; E + 2; [PGtrused] = E; [PGtrcount]+; [PGtrcount]+;"
        ) == 3
        and terrain_cpx_record.count(
            "D + 0; D+; D+; D+; D+; D+;"
        ) == 3
        and "E < 16; [PGtrval] = E;" not in terrain_cpx_record
        and contains_in_order(terrain_raster, (
            "A = [VHGNDvcframehit]; ? A = 0 -> VHGND terrain mapped raster direct;",
            "A = VHGNDvcrasterstamp; A + [VHGNDnormindex]; C = [A];",
            "A = [VHGNDvcgen]; ? A != C -> VHGND terrain mapped raster record select;",
            "[VHGNDvcrastercount] = A; [PGtrcount] = A;",
            "[VHGNDvcrasterstart] = A; [PGtrstart] = A;",
            "[SPterrain] = 1; => PG terrain replay;",
            '"VHGND terrain mapped raster record select"',
            "A = [PGtrused]; A + 60118; ? A > PGTRCAP -> VHGND terrain mapped raster direct;",
            "[PGtrstart] = [PGtrused]; [PGtrcount] = 2;",
            "C = [SPtinta]; C & 255;",
            "A = PGSCRT; A + PGDOFF; A < 16; A | C; [D] = A;",
            "C = [SPescr]; C & 255;",
            "A = PGSCRE; A + PGDOFF; A < 16; A | C; [D plus 1] = A;",
            "A = [PGtrused]; A + 2; [PGtrused] = A; [PGtractive] = 1;",
            "A + 0; A + 0; A+; A-; A+; A-;",
            "[SPterrain] = 1; [PJpreproject] = 1; [PJnrv] = 3; => PG polymap;",
            "A = [PGtractive]; [PGtractive] = 0; [SPterrain] = 0;",
            "A = [PJgate]; ? A != 0 -> VHGND terrain mapped raster discard;",
            "=> PG terrain state save;",
            "A = VHGNDvcrasterstarts; A + [VHGNDnormindex]; C = [PGtrstart]; [A] = C;",
            "A = VHGNDvcrastercounts; A + [VHGNDnormindex]; C = [PGtrcount]; [A] = C;",
            '"VHGND terrain mapped raster stamp"',
            "A = VHGNDvcrasterstamp; A + [VHGNDnormindex]; C = [VHGNDvcgen]; [A] = C;",
        ))
        and "[PGtrused] = [PGtrstart];" in terrain_raster
        and "VHGND terrain mapped empty replay" not in terrain_raster
        and all(token in terrain_state_save for token in (
            "[D plus 116] = [PGi];",
            "[D plus 117] = [PGj];",
            "A = [PGtrused]; A + PGTRSTATE; [PGtrused] = A;",
        ))
        and all(token in terrain_state_load for token in (
            "[PGi] = [D plus 116];",
            "[PGj] = [D plus 117];",
        ))
        and "[VHGNDvcframehit] = 0; [PGtrused] = 0; [PGtractive] = 0;" in terrain_cache
        and all(token in terrain_cache for token in (
            '"VHGND terrain raster cache clear"',
            "A = VHGNDvcrasterstamp; A + [VHGNDptr]; [A] = 0;",
            "? A < 80000 -> VHGND terrain raster cache clear;",
        )),
        "exact-camera terrain replay publishes complete ordered records and restores exact terminal state",
    )
    check(
        terrain_first_load_copies_exact
        and contains_in_order(terrain_first_load, (
            "A = [VHGNDvctri]; ? A != 0 -> VHGND terrain mapped load generic begin;",
            "D = [VHGNDh1];",
            "A = VHGNDvcpy; A + D; C = [A]; [mp plus 1] = C;",
            "D + 1;",
            "A = VHGNDvcpy; A + D; C = [A]; [mp plus 3] = C;",
            "D + 199;",
            "A = VHGNDvcpy; A + D; C = [A]; [mp plus 5] = C;",
            "[rwf] = 1; [rwf plus 1] = 1; [rwf plus 2] = 1;",
            "[VHGNDvi] = 3; [VHGNDvcindex] = D; [VHGNDvcpairready] = 1;",
            "-> VHGND terrain mapped bounds;",
        ))
        and "=> " not in terrain_first_load
        and not any(operator in terrain_first_load for operator in (
            "++", "--", "**", "//", "+:", "-:", "*:", "/:", "=:", ":=", "~:"
        ))
        and all(token in terrain_generic_load for token in (
            "[VHGNDvi] = 0;",
            '"VHGND terrain mapped load"',
            "=> VHGND terrain vertex load;",
            "[VHGNDvi]+; A = [VHGNDvi]; ? A < 3 -> VHGND terrain mapped load;",
        ))
        and terrain_generic_load.count("=> VHGND terrain vertex load;") == 1,
        "first terrain triangle restores exact cache words without indexed calls",
    )
    terrain_common_skip_cases = {
        (frame_hit, mirror, lod_step)
        for frame_hit in (0, 1)
        for mirror in (0, 1)
        for lod_step in (1, 8, 16)
        if frame_hit == 1 and mirror == 0 and lod_step == 1
    }
    check(
        terrain_common_skip_cases == {(1, 0, 1)}
        and contains_in_order(tile, (
            "[VHGNDtilepolys] = 0; [VHGNDvcpairready] = 0;",
            "A = [VHGNDvcframehit]; ? A = 0 -> VHGND tile common input;",
            "A = [VHGNDmirror]; ? A != 0 -> VHGND tile common input;",
            "A = [VHGNDlodstep]; ? A != 1 -> VHGND tile common input;",
            "-> VHGND tile common input ready;",
            '"VHGND tile common input"',
            "=> VHGND terrain common input;",
            '"VHGND tile common input ready"',
            "[VHGNDinputready] = 0; [VHGNDvctri] = 0; => VHGND terrain facing;",
        ))
        and tile.count("=> VHGND terrain common input;") == 1
        and all(token in terrain_common for token in (
            "[VHGNDvi] = 2;",
            "[fw plus 508] = [FA0]; [fw plus 509] = [FA1];",
            "[fw plus 516] = [FA0]; [fw plus 517] = [FA1];",
            "[fw plus 524] = [FA0]; [fw plus 525] = [FA1];",
        ))
        and contains_in_order(terrain_common_fallback, (
            "A = [VHGNDvcframehit]; ? A = 0 -> VHGND terrain common input fallback done;",
            "A = [VHGNDmirror]; ? A != 0 -> VHGND terrain common input fallback done;",
            "A = [VHGNDlodstep]; ? A != 1 -> VHGND terrain common input fallback done;",
            "=> VHGND terrain common input;",
            '"VHGND terrain common input fallback done"',
        ))
        and terrain_common_fallback.count("=> VHGND terrain common input;") == 1
        and terrain_remaining.index("=> VHGND terrain common input fallback;")
        < terrain_remaining.index("[VHGNDvi] = 0;")
        and "=> VHGND terrain remaining input;" in terrain_facing
        and "=> VHGND terrain remaining input;" in terrain_mapped,
        "repeated unit terrain lazily restores shared raw input only on generic fallback",
    )
    check(
        "VHGNDvcpairready = 0;" in ground
        and "A = [VHGNDvctri]; ? A != 0 -> VHGND terrain mapped cache second select;" in terrain_mapped
        and "A = [VHGNDvcpairready]; ? A = 0 -> VHGND terrain mapped cache second;" in terrain_pair
        and terrain_pair.count("VHGNDvcstamp") == 1
        and terrain_pair.count("VHGNDvcvisible") == 1
        and all(token in terrain_pair for token in (
            "[fw plus 64] = [fw plus 66]; [fw plus 65] = [fw plus 67];",
            "[fw plus 72] = [fw plus 74]; [fw plus 73] = [fw plus 75];",
            "[fw plus 80] = [fw plus 82]; [fw plus 81] = [fw plus 83];",
            "[mp] = [mp plus 2]; [mp plus 1] = [mp plus 3];",
            "A = VHGNDvcrx0; A + D; C = [A]; [fw plus 66] = C;",
            "A = VHGNDvcrx1; A + D; C = [A]; [fw plus 67] = C;",
            "A = VHGNDvcry0; A + D; C = [A]; [fw plus 74] = C;",
            "A = VHGNDvcry1; A + D; C = [A]; [fw plus 75] = C;",
            "A = VHGNDvcrz0; A + D; C = [A]; [fw plus 82] = C;",
            "A = VHGNDvcrz1; A + D; C = [A]; [fw plus 83] = C;",
            "A = VHGNDvcpx; A + D; C = [A]; [mp plus 2] = C;",
            "A = VHGNDvcpy; A + D; C = [A]; [mp plus 3] = C;",
            "[rwf] = 1; [rwf plus 1] = 1; [rwf plus 2] = 1;",
            "[VHGNDvi] = 3; A = [VHGNDh1]; A + 200; [VHGNDvcindex] = A;",
            "-> VHGND terrain mapped bounds;",
        ))
        and "=> " not in terrain_pair
        and not any(operator in terrain_pair for operator in (
            "++", "--", "**", "//", "+:", "-:", "*:", "/:", "=:", ":=", "~:"
        ))
        and "[VHGNDvi] = 3; [VHGNDvcindex] = D; [VHGNDvcpairready] = 1;" in terrain_first_load
        and terrain_pair_indices_exact
        and terrain_pair_layout_exact,
        "paired terrain triangles hand exact shared vertex slots to the second mapper",
    )
    check(
        terrain_mapped.count(
            "? A = 0 -> VHGND terrain mapped cache first behind;"
        ) == 1
        and terrain_mapped.count(
            "? A = 0 -> VHGND terrain mapped cache second behind;"
        ) == 1
        and terrain_behind.count(
            "A = VHGNDvcstamp; A + D; C = [A];"
        ) == 3
        and terrain_behind.count(
            "A = [VHGNDvcgen]; ? A != C -> VHGND terrain mapped ensure begin;"
        ) == 3
        and terrain_behind.count(
            "A = VHGNDvcvisible; A + D; A = [A];"
        ) == 3
        and terrain_behind.count(
            "? A != 0 -> VHGND terrain mapped behind partial;"
        ) == 3
        and terrain_behind_cache_copies_exact
        and contains_in_order(terrain_behind, (
            "A = [VHGNDinputready]; ? A != 0 -> VHGND terrain mapped behind input ready;",
            "=> VHGND terrain remaining input;",
            '"VHGND terrain mapped behind input ready"',
            "A = [VHGNDvctri]; ? A != 0 -> VHGND terrain mapped behind second payload;",
            "[fw plus 510] = [fw plus 508]; [fw plus 511] = [fw plus 509];",
            "[fw plus 518] = [fw plus 516]; [fw plus 519] = [fw plus 517];",
            "[fw plus 526] = [fw plus 524]; [fw plus 527] = [fw plus 525];",
            "[fw plus 70] = [fw plus 68]; [fw plus 71] = [fw plus 69];",
            "[fw plus 78] = [fw plus 76]; [fw plus 79] = [fw plus 77];",
            "[fw plus 86] = [fw plus 84]; [fw plus 87] = [fw plus 85];",
            "[rwf] = 0; [rwf plus 1] = 0; [rwf plus 2] = 0; [rwf plus 3] = 0;",
            "[PGFi] = FSRZF plus 2; [PGFj] = FSRZF plus 3;",
            "[PJgate] = 1; [PJmode] = 1; [PJdx] = 3; [PJnrv] = 4; [PJvr] = 4;",
            "[PJdoflag] = 0; [PJpreproject] = 0; [SPterrain] = 0;",
            "end;",
            '"VHGND terrain mapped behind partial"',
            "-> VHGND terrain mapped generic;",
        ))
        and "=> PG polymap;" not in terrain_behind
        and all(token not in ground and token not in game for token in (
            "VHGNDbehind", "vhgbehind", "game-behind-cull-out.bin",
        )),
        "exact cached all-behind terrain skips only dead polymap work and restores shared state",
    )
    check(
        "VHGNDvcfacing = 80000;" in ground
        and "[VHGNDvccacheok] = 0;" in ground
        and all(token in terrain_cache for token in (
            "[VHGNDvcframehit] = 1;",
            "A = [VHGNDvccacheok]; ? A = 0 -> VHGND terrain cache invalidate;",
            "A = [VHGNDcamx]; ? A != [VHGNDvccamx] -> VHGND terrain cache invalidate;",
            "A = [VHGNDcamy]; ? A != [VHGNDvccamy] -> VHGND terrain cache invalidate;",
            "A = [VHGNDcamz]; ? A != [VHGNDvccamz] -> VHGND terrain cache invalidate;",
            "A = [VHGNDalpha]; ? A != [VHGNDvcalpha] -> VHGND terrain cache invalidate;",
            "A = [VHGNDbeta]; ? A != [VHGNDvcbeta] -> VHGND terrain cache invalidate;",
            '"VHGND terrain cache invalidate"', "[VHGNDvcframehit] = 0;",
            "[VHGNDvcbeta] = [VHGNDbeta]; [VHGNDvccacheok] = 1;",
            "[VHGNDvcgen]+;",
        ))
        and terrain_cache.index("[VHGNDvcframehit] = 1;")
        < terrain_cache.index('"VHGND terrain cache invalidate"')
        < terrain_cache.index("[VHGNDvcframehit] = 0;")
        and all(token in terrain_facing for token in (
            "A = [VHGNDmirror]; ? A != 0 -> VHGND terrain facing generic;",
            "A = [VHGNDh1]; A + A; A + [VHGNDvctri]; [VHGNDnormindex] = A;",
            "A = [VHGNDvcframehit]; ? A = 0 -> VHGND terrain facing cache miss;",
            "A = VHGNDvcfacing; A + [VHGNDnormindex]; A = [A]; [FCret] = A; end;",
            '"VHGND terrain facing cache miss"',
            "=> PG facing dot; -> VHGND terrain facing cache store;",
            '"VHGND terrain facing cache store"',
            "A = VHGNDvcfacing; A + [VHGNDnormindex]; C = [FCret]; [A] = C;",
            '"VHGND terrain facing generic"', "=> VHGND terrain remaining input; => PG facing; end;",
        )),
        "bit-identical camera frames reuse only the exact preceding terrain-facing booleans",
    )
    check(
        "if (depth > 40) return;" in original1
        and "VHGNDOBJECTFAR = 40;" in ground
        and all(token in tile for token in (
            "A = [VHGNDdepth]; ? A > VHGNDOBJECTFAR -> VHGND tile done;",
            "A = [VHGNDtilepolys]; ? A = 0 -> VHGND tile done;",
            "=> VHGND capsule;", "=> VHGND render tile fauna;",
            "=> VHGND object view cull;", "=> VHGND tile objects;",
        ))
        and contains_in_order(traversal, (
            "=> VHGND terrain cache frame;",
            "=> VHGND object view setup;",
            "=> VHGND fauna tiles build;",
            "[VHGNDanimorphs] = 0; [VHGNDgroundbirds] = 0;",
            "=> VHGND traverse faithful;",
        ))
        and ground.count("=> VHGND fauna tiles build;") == 1
        and ground.count("=> VHGND object view setup;") == 1
        and ground.count("=> VHGND object view cull;") == 1
        and contains_in_order(tile_detail, (
            "=> VHGND render tile fauna;",
            "=> VHGND object view cull;",
            "A = [VHGNDviewrz]; ? A = 0 -> VHGND tile done;",
            "=> VHGND tile objects;",
        ))
        and "SUfseed" not in object_view_setup
        and "SUfseed" not in object_view_cull
        and object_view_cull.count("A / 256;") == 2
        and object_view_cull.count("A / 32768;") == 3
        and "A / 4; A + 128;" in object_view_cull
        and "'/" not in object_view_cull
        and "C = VHGNDobjcacheseed; C + A; [SUfseed] = [C];" in objects
        and tile.index("=> VHGND capsule;")
        < tile.index("=> VHGND render tile fauna;")
        < tile.index("=> VHGND object view cull;")
        < tile.index("=> VHGND tile objects;")
        and "=> VHGND render distant objects;" not in traversal,
        "surface detail keeps source painter order and culls only wholly hidden cached objects through depth 40",
    )
    check(
        "grnd; sky;" in game and "spglobe; spglow; spbg;" in game
        and "=> GRSK create; => GRSK horizon;" in ground
        and ground.count("[SPpreg] = RGADP; [SPpn] = NPIX; [SPval] = 0; => SP fill page;") == 2
        and '"VHGND guard band"' not in ground
        and "=> VHGND background direct;\n\t=> VHGND background cache save;" in ground
        and "[BGdstreg] = RGADP; => SP background;" not in ground
        and '"VHGND background direct"' in ground
        and '"VHGND background cache save"' in ground
        and '"VHGND background cache restore"' in ground
        and "VHGNDskycache = 64000" in ground
        and all(token in ground for token in (
            '"VHGND bg record"', '"VHGND bg row"',
            '"VHGND bg row wrapped"', '"VHGND bg row contiguous"',
            '"VHGND bg consume"', '"VHGND bg skip"',
            "A = [BGbp]; A + 1; A & 65535; [BGbp] = A;",
        ))
        and "VHGNDbgstart = 0; VHGNDbgshift = 0; VHGNDbgangle = 0;" in ground
        and "A = [VHGNDbeta]; ? A >= 0 -> VHGND background angle ready; A + 360;" in ground
        and "C = [VHGNDbgangle]; C % 360; A - C; [VHGNDbgstart] = A;" in ground
        and "A = [VHGNDbgangle]; A '/ 72; A '* 320; C = A;" in ground
        and "A = 0; A - 643; A - C;" in ground
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
            "[FI] = 150; => PGF fromint; => FQuo; => FToIntChop;",
            "A % 3; A + 1;", "A % 64; A + 64;",
            "C '* [VHGNDflashgain]; C '/ 63;",
            "[VHGNDflashactive] = [VHGNDflashpending]; [VHGNDflashpending] = 0;",
            '"VHGND background lightning invert"',
            '"VHGND background lightning invert one"',
            "C = 63; C - A; [D] = C;",
            "[VHGNDflashskyp] = 40000;",
        ))
        and "[VHGNDplayerrefx] = [VHGsurfrefx]; [VHGNDplayerrefz] = [VHGsurfrefz];" in game
        and ground.index("=> VHGND weather lightning begin;")
        < ground.index("[VHGNDruindrawn] = 0; => VHGND background;")
        and "? A '<= 5 -> VHGND weather density ready;" not in ground,
        "live landings cache the generated panorama through a direct wrapping mapper",
    )
    local_sun = section(ground, '"VHGND local sun"', '"VHGND surrounding frame"')
    secondary_sun = section(ground, '"VHGND secondary sun setup"', '"VHGND local sun"')
    opening_sky = section(ground, '"VHGND sky"', '"VHGND general sky"')
    general_sky = section(ground, '"VHGND general sky"', '"VHGND UTC seconds"')
    utc_seconds = section(ground, '"VHGND UTC seconds"', '"VHGND orbital phase"')
    sun_zero_view = "[VHVcamxi] = 0; [VHVcamyi] = 0; [VHVcamzi] = 0;"
    surface_world_view = (
        "[VHVcamxi] = [VHGNDcamx]; [VHVcamyi] = [VHGNDcamy]; "
        "[VHVcamzi] = [VHGNDcamz];"
    )
    check(
        '"VHGND pinned seconds"' in utc_seconds
        and "A = [VHGNDclocksecs]; [VHGNDsecs] = A;" in utc_seconds
        and "=> VHG fpu clean; => SU fp init;" in utc_seconds
        and "-> VHGND convert seconds;" in utc_seconds
        and '"VHGND convert seconds"' in utc_seconds
        and "A = [VHGNDsecs]; [FI] = A; => PGF fromint;" in utc_seconds
        and utc_seconds.count("[FI] = A; => PGF fromint;") == 1,
        "pinned surface time survives floating-point initialization",
    )
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
        and "[GRSKatmosphere] = [VHGNDatmosphere];" in ground
        and "[GRSKnightzone] = 0; [VHGNDsunxf] = 1;" in opening_sky
        and "[GRSKnightzone] = 0; [VHGNDsunxf] = 1;" not in general_sky
        and "[VHGNDcrep] = A; A = 0; A - 1; [VHGNDsunxf] = A;" in ground
        and traversal.index(sun_zero_view)
        < traversal.index("=> VHGND local sun;")
        < traversal.index("=> VHT mask page;", traversal.index("=> VHGND local sun;"))
        < traversal.index(surface_world_view, traversal.index("=> VHGND local sun;"))
        < traversal.index("( Source fragment()")
        and all(token in original1 for token in (
            "cam_x = 0; cam_y = 0; cam_z = 0;",
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
        "=> VHGND render tile fauna;" in ground
        and "=> VHGND sun flares;" in ground
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
            "A = [SPval]; ? A < 64 -> VHF done; ? A > 127 -> VHF done;",
            "[FI] = 1000; => IntToF; => FMul;",
            "[FS0] = [VHFdist]; => FLoadF32; [VHFdist0] = [FA0]; [VHFdist1] = [FA1];",
            "=> VHF positive k;",
            "=> VHF surface added;",
        ))
        and all(token in flare for token in (
            '"VHF surface added"', "[FB0] = D2F1A9FCh; [FB1] = 3F60624Dh; => FMul;",
            '"VHF space added"', "[FB0] = D2F1A9FCh; [FB1] = 3F50624Dh; => FMul;",
        ))
        and all(token in original1 for token in (
            "if (!nightzone && rainy < 1.2)",
            "if (nearstar_class!=5&&nearstar_class!=6&&nearstar_class!=10)",
            "if (dsd1<1000*nray1&&dsd1>=10*nray1)",
            "(10 * nray1) / dsd1, 1 + (0.002 * dsd1), hud_closed, 2, 1, 1",
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
            "[VHFdist0] = [VHTdist0]; [VHFdist1] = [VHTdist1]; => VH space flare;", '"VHT smooth grays"',
            "[SUsi] = 320;", '"VHT smooth gray pixel"',
            "E & 0FCFCFCFCh; E > 2;", "B = 56960;",
            "[FI] = 100; => IntToF;", "[FI] = 8; => IntToF;",
            "[FI] = 1550; => IntToF;", "[FI] = 1600; => IntToF;",
            '"VHT far pixel"', "=> VHT far spread; => VHT far spread; => VHT far spread;",
            '"VHT far spread"', "A = [VHTfarcolour]; A > 4;",
            '"VHT texture cycle"', '"VHT texture cycle texel"',
            "C = [A]; C & 255; D = C; D & 192; C + 1; C & 63; C | D; [A] = C;",
            "? A < 64800 -> VHT texture cycle texel;",
            '"VHT mask page"', "=> VHT mask page common;",
            '"VHT mask page common"', "-> VHT mask page pixel;",
            '"VHT mask page pixel"',
            "C = [A]; C & 63; C + 64; [A] = C;",
            "? A < 58240 -> VHT mask page pixel;",
        ))
        and "A = [MgApreached]; ? A = 0 -> VHT render done;" not in star
        and all(token in game for token in (
            "=> VHT visibility; A = [VHTwhiteok]; ? A = 0 -> VHG local star premask;",
            "=> VHG local companion coronas;",
            "=> VHG local star coords; => VHT premask; => VHT mask page;",
            "A = [VHTglobeok]; ? A = 0 -> VHG local star far;",
            "[GBcmask] = 64; [GBsat] = [VHTglobesat];",
            "A = [VHTfarok]; ? A = 0 -> VHG local planet render; => VHT far pixel;",
            '"VHG local companion coronas"',
            "=> VHG local body relative; => VHG local body distance;",
            "[FA0] = [VHGlocaldist0]; [FA1] = [VHGlocaldist1]; => F32Narrow; => FLoadF32;",
            "A = [VHGlocalbody]; A + [VHTtx]; => SU fast srand;",
            "=> VHG local fast flandom;",
            "[FB0] = 33333333h; [FB1] = 3FD33333h; => FMul;",
            "[FA0] = 33333333h; [FA1] = 3FC33333h; => FSub; => F32Narrow;",
            "[FI] = 5; => IntToF;", "[FI] = 1000; => IntToF;",
            "[VHFdist0] = [VHGlocaldist0]; [VHFdist1] = [VHGlocaldist1]; => VH space flare;",
            "=> VHS stars; => VHG finder render;",
        ))
        and all(token in flare for token in (
            '"VH space flare"', "=> VHF space added; => VHF space positive k; [VHFok] = 0;",
            '"VHF space positive k"', "[FA0] = [VHFspaceray0]; [FA1] = [VHFspaceray1];",
            "[PGFi] = SFRX; => PGF a; [PGFi] = SFRZ; => PGF quo; => FToIntChop;",
            "A = [FI]; A + 3;", "? A >= 90 -> VHF done; A + 100; [VHFcy] = A;",
        ))
        and game.index("=> VHS stars; => VHG finder render;") > game.index("=> VH set view; [VHLpower] = [VHGilight]; [VHLemergency] = [VHGelight]; => VH alogena;")
        and all(token in space for token in (
            "C '* 320; C + A; C + 4; [SPoff] = C;",
            "C = [SPval]; A = [VHSsurface]; ? A != 0 -> VHS draw surface gate;",
            "? C = 68 -> VHS draw next; ? C < 64 -> VHS draw next; ? C > 92 -> VHS draw next;",
            '"VHS draw surface gate"', "? C > 62 -> VHS draw next;",
            "D = C; D & 192; C & 63; C + [VHScolour];",
            "? C > 92 -> VHS replay next;",
            '"VHS fade"', "C + 2876; [VHSfadebase] = C;",
            "? C >= 8 -> VHS fade subtract;", "? A < 57920 -> VHS fade pixel;",
        ))
        and all(token in game for token in (
            "A = [MgStspeed]; ? A != 0 -> VHG render space fade;",
            '"VHG render space clear"', "=> VHG space clear;",
            '"VHG space clear"', "A = nw; A + RADPT; A + 2880; B = 7280; C = 0;",
            "B ^ VHG space clear eight;", "=> VHS fade;",
        ))
        and "VHGspacevalid" not in game
        and "[VHTphase] = [VHGframe];" not in game
        and "A = [VHGframe]; A % 360; [GBstart] = A;" not in game
        and game.count("=> VHT phase advance;") >= 1
        and all(token in game for token in (
            "[VHTdosim] = [VHGdosim]; [VHTfast] = [VHGfast];",
            "[VHTinterpok] = [VHGinterpok]; [VHTinterpacc] = [VHGinterpacc];",
            "A = [TKtmp]; A / 360; A % 360; [VHTclockphase] = A;",
            "[MgApreached] = 1; [MgStspeed] = 0;",
            "[VHPfcsstatus] = 13;",
            "[VHPfcsstatus] = 14;",
        ))
        and all(token in original0 for token in (
            "if (ap_target_class==11) ap_target_spin = random (30) + 1;",
            "if (ap_target_class==7) ap_target_spin = random (12) + 1;",
            "if (ap_target_class==2) ap_target_spin = random (4) + 1;",
        )),
        "resolved stars retain their source class-specific spin instead of universal rotation",
    )
    original_outer_hud = section(
        original,
        "if (active_screen != -1 || draw_hud != 1) goto nohud_1;",
        "// Messaggio di reset, lampeggiante.",
    )
    telemetry_prepare = section(
        game, '"VHG HUD telemetry prepare"', '"VHG interior smooth64"'
    )
    telemetry_draw = section(
        panels, '"VH HUD telemetry"', '"VH HUD FCS"'
    )
    interior_details = section(
        game, '"VHG interior details"', '"VHG source status ready"'
    )
    check(
        all(token in original_outer_hud for token in (
            "dxx = dzat_x - ap_target_x;",
            "dyy = dzat_y - ap_target_y;",
            "dzz = dzat_z - ap_target_z;",
            "* 5E-5;",
            "if (ap_reached && ap_target_id == nearstar_identity) l_dsd *= 0.01;",
            'sprintf (temp_distance_buffer, "%01.2f", l_dsd);',
            "cam_x = 450; cam_y = -180; cam_z = -750;",
            "digit_at ('L', -6, -15, 5, 112, 1);",
            "digit_at ('Y', -6, -15, 5, 112, 1);",
            "planet_xyz (ip_targetted);",
            "* 1E-2;",
            "cam_x = 450; cam_y = -250; cam_z = -750;",
            "digit_at ('D', -6, -15, 5, 105, 1);",
            "digit_at ('S', -6, -15, 5, 105, 1);",
        ))
        and all(token in telemetry_prepare for token in (
            "A = [MgAptgt]; ? A = 0 -> VHG HUD telemetry local;",
            "[FA0] = [MgDzatX0]; [FA1] = [MgDzatX1];",
            "[FB0] = [MgApX0]; [FB1] = [MgApX1]; => FSub;",
            "[FB0] = VHGK5EM50; [FB1] = VHGK5EM51; => FMul;",
            "[FB0] = VHGK0010; [FB1] = VHGK0011; => FMul;",
            "[FI] = 100; => IntToF;",
            "=> FMul; => FToIntNear;",
            "[VHGinfofixeddigits] = 2;",
            "A = [VHGlocaltarget]; ? A = 0FFFFFFFFh -> VHG HUD telemetry prepared;",
            "? A '>= [nsnob] -> VHG HUD telemetry prepared;",
            "[FA0] = [VHGlocaldist0]; [FA1] = [VHGlocaldist1];",
        ))
        and "VHGK5EM50 = 0EB1C432Dh; VHGK5EM51 = 03F0A36E2h;" in game
        and "VHGK0010 = 047AE147Bh; VHGK0011 = 03F847AE1h;" in game
        and "vhpstarunit = { L.Y. };" in panels
        and "vhpbodyunit = { DYAMS };" in panels
        and all(token in telemetry_draw for token in (
            "[VHVcamxi] = 450; A = 0; A - 180; [VHVcamyi] = A;",
            "[VHVcamxi] = 450; A = 0; A - 250; [VHVcamyi] = A;",
            "[VHPtelemetrycolour] = 127;",
            "[VHPtelemetrycolour] = 112;",
            "[VHPtelemetrycolour] = 120;",
            "[VHPtelemetrycolour] = 105;",
            "A = [VHVcamxi]; A - 40; [VHVcamxi] = A; => VH set view;",
            "[DGdigit] = [VHPchar]; [DGcolor] = [VHPtelemetrycolour]; [DGshader] = [VHPtelemetryshader]; => FB digit at;",
            "[vhcpoly plus 0] = 1096810496; [vhcpoly plus 1] = 3251109888;",
            "[vhcpoly plus 6] = 3243769856; [vhcpoly plus 7] = 1103626240;",
        ))
        and all(token in interior_details for token in (
            "A = [VHGscreen]; ? A != 0FFFFFFFFh -> VHG source outer HUD done;",
            "A = [VHGdrawhud]; ? A != 1 -> VHG source outer HUD done;",
            "=> VHG HUD telemetry prepare; => VH HUD telemetry;",
            "=> VHG interior smooth64; => VHG interior smooth64;",
        ))
        and interior_details.index("=> VHG HUD telemetry prepare; => VH HUD telemetry;")
        < interior_details.index("=> VHG interior smooth64; => VHG interior smooth64;"),
        "inside Stardrifter restores source-shaped two-decimal L.Y. and DYAMS range rows",
    )
    label_prepare = section(
        game, '"VHG HUD labels prepare"', '"VHG HUD telemetry prepare"'
    )
    catalog_labels = section(
        catalog, '"VHCAT default labels"', '"VHCAT refresh"'
    )
    check(
        all(token in original_outer_hud for token in (
            "if (ap_targetting || ap_targetted)",
            "cam_x = 450; cam_y = 250; cam_z = -750;",
            "for (c = 0; c < 24; c++)",
            "digit_at (star_label[c], -6, -15, 5, 127, 1);",
            "if (ip_targetted!=-1)",
            "update_planet_label ();",
            "cam_x = 450; cam_y = 180; cam_z = -750;",
            "digit_at (planet_label[c], -6, -15, 5, 112, 1);",
        ))
        and "VHGhudstardefault = { UNKNOWN STAR / CLASS };" in game
        and "VHGhudplanetdefault = { NAMELESS PLANET / N. };" in game
        and "VHGhudmoondefault = { NAMELESS MOON # };" in game
        and "VHGhudstarlabel = 25;" in game
        and "VHGhudbodylabel = 25;" in game
        and all(token in catalog_labels for token in (
            "[VHCATstarok] = 0; [VHCATbodyok] = 0;",
            "[VHCATstarok] = 1; => VHCAT copy label;",
            "[VHCATbodyok] = 1; => VHCAT copy label;",
        ))
        and all(token in label_prepare for token in (
            "A = vhcatstarlabel; A + 1; [VHGhudlabelsrc] = A; [VHGhudlabellen] = 20;",
            "E = VHGhudstarlabel; [E plus 20] = 32; [E plus 21] = 83;",
            "[E plus 23] = B; [E plus 24] = 0;",
            "A = vhcatbodylabel; A + 1; [VHGhudlabelsrc] = A; [VHGhudlabellen] = 20;",
            "[VHGhudlabelsrc] = VHGhudplanetdefault; [VHGhudlabellen] = 20;",
            "[VHGhudlabelsrc] = VHGhudmoondefault; [VHGhudlabellen] = 15;",
            "[E plus 15] = A; B '% 10; B + 48; [E plus 16] = B;",
            "[E plus 17] = 47; C = nspowner;",
            "[E plus 20] = 38;",
            "[E plus 21] = 80;",
            "[VHPtelemetrystarlabel] = VHGhudstarlabel;",
            "[VHPtelemetrybodylabel] = VHGhudbodylabel;",
        ))
        and "=> VHG HUD labels prepare; => VHG fpu clean;" in telemetry_prepare
        and all(token in telemetry_draw for token in (
            "[VHVcamxi] = 450; [VHVcamyi] = 250;",
            "[VHPtelemetryptr] = [VHPtelemetrystarlabel]; [VHPtelemetrycolour] = 127;",
            "[VHVcamxi] = 450; [VHVcamyi] = 180;",
            "[VHPtelemetryptr] = [VHPtelemetrybodylabel]; [VHPtelemetrycolour] = 112;",
            "? A = 0 -> VHP HUD telemetry text done;",
        ))
        and telemetry_draw.index("[VHPtelemetrystarlabel]")
        < telemetry_draw.index("[VHPtelemetrystar]")
        < telemetry_draw.index("[VHPtelemetrybodylabel]")
        < telemetry_draw.index("[VHPtelemetrybody]")
        and interior_details.index("=> VHG HUD telemetry prepare; => VH HUD telemetry;")
        < interior_details.index("=> VHG interior smooth64; => VHG interior smooth64;"),
        "inside Stardrifter restores native 24-character catalogue and fallback target labels",
    )
    original_label_commands = section(
        original,
        "case 3: // galactic cartography commands",
        "case 4: switch (s_command)",
    )
    label_input = section(
        game, '"VHG label input"', '"VHG navigation steering input"'
    )
    label_actions = section(
        game, '"VHG device name star"', '"VHG device next target"'
    )
    catalog_add = section(
        catalog, '"VHCAT folded name character"', '"VHCAT remove"'
    )
    catalog_remove = section(
        catalog, '"VHCAT remove"', '"VHCAT repair"'
    )
    telemetry_text = section(
        panels, '"VHP HUD telemetry text"', '"VH HUD FCS"'
    )
    physical_cart_commands = section(
        game, '"VHG onboard prepare cart"', '"VHG onboard prepare emergency"'
    )
    accessible_cart_commands = section(
        game, '"VHG device cartography overlay"', '"VHG device emergency overlay"'
    )
    check(
        all(token in original_label_commands for token in (
            "if (ap_targetted==1 && !ap_targetting && !labplanet)",
            "if (ip_targetted!=-1 && !labstar)",
            "labstar_char = 0;", "labplanet_char = 0;",
            "for (n = 0; n < 21; n++)", "star_id = ap_target_id;",
            "planet_id = nearstar_identity + ip_targetted + 1;",
            "star_label_pos >= sm_consolidated",
            "planet_label_pos >= sm_consolidated",
            "!memicmp (comp_data+8, star_label, 20)",
            "!memicmp (comp_data+8, planet_label, 20)",
            'status ("PROMPT", 50);', 'status ("ASSIGNED", 50);',
            'status ("EXTANT", 50);', 'status ("REMOVED", 50);',
            'status ("DENIED", 50);', 'status ("CONFLICT", 50);',
            'status ("INT. ERROR", 50);',
        ))
        and all(token in original for token in (
            "if (c >= 32 && c <= 126 && labstar_char < 20)",
            "if (c >= 'a' && c <= 'z') c -= 32;",
            "star_label[labstar_char] = c;", "star_label[labstar_char] = 32;",
            "planet_label[labplanet_char] = c;", "planet_label[labplanet_char] = 32;",
            "if (c == 13)", "dev_commands ();", "goto endmain;",
        )),
        "native direct label gates, mutation, persistence, and statuses remain pinned",
    )
    check(
        all(token in label_actions for token in (
            "A = [MgAptgt]; ? A != 1 -> VHG label conflict;",
            "A = [VHGlabelbody]; ? A != 0 -> VHG label conflict;",
            "[VHGlabelid0] = [VHTid0]; [VHGlabelid1] = [VHTid1];",
            "A = [VHGplanet]; ? A '>= [nsnob] -> VHG label conflict;",
            "A = [VHGlabelstar]; ? A != 0 -> VHG label conflict;",
            "[nsid0] = [VHTid0]; [nsid1] = [VHTid1]; => NsIdentAddInt;",
            "[VHGlabelstar] = 1; [VHGlabelstarpos] = 0;",
            "[VHGlabelbody] = 1; [VHGlabelbodypos] = 0;",
            "A < 21 -> VHG label begin clear;",
            "[E plus 21] = A;", "[E plus 22] = A;", "[E plus 23] = B;",
            "=> VHCAT remove;", "? A = 1 -> VHG label removed;",
            "? A = 2 -> VHG label denied;", "[VHGlabelresult] = 0;",
            "[VHGlabelresult] = 3;", "[VHGlabelresult] = 4;",
            "[VHGlabelresult] = 5;", "VHGlabelerrortext",
            "VHGlabelconflicttext",
        ))
        and "=> VHG console prefill;" not in label_actions
        and all(token in catalog_add for token in (
            "[E plus 2] = 20202020h;", "[VHCATshift] = A; B < A;",
            "C = FFh; C < [VHCATshift]; ! C;",
            "A = [E]; A & C; A | B; [E] = A;",
            "B = [VHCATi]; C = B; B / 4;",
            "? A < 97 -> VHCAT folded name character done;",
            "? A > 122 -> VHCAT folded name character done; A - 32;",
            "[VHCATptr] = E; [VHCATi] = 0;",
            "E = [VHCATptr]; => VHCAT folded name character; [VHCATchar] = A;",
            "E = [VHCATfoundptr]; => VHCAT folded name character;",
            "? A != [VHCATchar] -> VHCAT duplicate next;",
            "? A < 20 -> VHCAT duplicate name loop;",
        ))
        and "A = [E plus 2]; ? A != [C plus 2]" not in catalog_add
        and all(token in catalog_remove for token in (
            "A = [VHCATrecno]; A '* VHCATRECBYTES; A + VHCATHDRBYTES;",
            "? A < [vhcatraw] -> VHCAT remove protected;",
            "[File Position] = [VHCATremovepos]", "[Block Size] = 8; isocall;",
            "[VHCATstatus] = 1;", "[VHCATstatus] = 2;",
        ))
        and catalog_remove.index("[File Command] = WRITE;")
        < catalog_remove.index("E = [VHCATfoundptr];")
        and all(text in game for text in (
            "VHGlabelprompttext = { PROMPT };",
            "VHGlabelassignedtext = { ASSIGNED };",
            "VHGlabelextanttext = { EXTANT };",
            "VHGlabelremovedtext = { REMOVED };",
            "VHGlabeldeniedtext = { DENIED };",
            "VHGlabelconflicttext = { CONFLICT };",
            "VHGlabelerrortext = { INT. ERROR };",
        )),
        "cartography actions retain identities, case-insensitive names, local removal, and native results",
    )
    check(
        all(token in label_input for token in (
            "[VHGlabelused] = 1;", "A = [KEY ESCAPE];",
            "? A = 27 -> VHG label cancel;", "? A = 8 -> VHG label backspace;",
            "? A = 13 -> VHG label commit;", "? A < 32 -> VHG label input done;",
            "? A > 126 -> VHG label input done;", "? A >= 20 -> VHG label input done;",
            "A = [VHGascii]; [VHGlabelchar] = A; [VHGascii] = 0; A = [VHGlabelchar];",
            "-> VHG label lowercase character;",
            "[VHGlabelchar] - 32;", "[E] = [VHGlabelchar];", "[E] = 32;",
            "[VHCATlen] = 20;", "=> VHCAT add;",
            "[VHGlabelresult] = 6;", "[VHGlabelresult] = 1;", "[VHGlabelresult] = 2;",
            "[VHGlabelstar] = 0;", "[VHGlabelbody] = 0;", "=> VHCAT refresh;",
        ))
        and game.index("=> VHG return key;")
        < game.index("=> VHG label input; A = [VHGlabelused]")
        < game.index("=> VHG fps key;")
        < game.index("=> VHG raw snapshot key;")
        < game.index("=> VHG movie character;")
        < game.index("=> VHG graphics character;")
        < game.index("=> VHG menu mouse;")
        < game.index("=> VHG device key;")
        and all(token in game for token in (
            "VHGgameescheld = 0;",
            "A = [KEY ESCAPE]; ? A = OFF -> VHG input escape released;",
            "A = [VHGgameescheld]; ? A != 0 -> VHG input done;",
            "[VHGgameescheld] = 1; [Console Command] = CLEAR CONSOLE BUFFER; isocall;",
            "=> VHG gameplay escape; -> VHG input done;",
            "[VHGgameescheld] = 0;",
            "A = [VHGlabelstar]; A | [VHGlabelbody]; ? A = 0 -> VHG gameplay escape SL;",
            "[VHGascii] = 0; [VHGlabelstar] = 0; [VHGlabelbody] = 0; => VHCAT refresh; end;",
        ))
        and game.index("A = [KEY ESCAPE]; ? A = OFF -> VHG input escape released;")
        < game.index("=> VHG return key;")
        and game.index("=> VHG gameplay escape; -> VHG input done;")
        < game.index("=> VHG label input; A = [VHGlabelused]")
        and all(token in physical_cart_commands for token in (
            "VHGsrccartstarassign", "VHGsrccartstarremove",
            "VHGsrccartplanetassign", "VHGsrccartplanetremove",
        ))
        and all(token in accessible_cart_commands for token in (
            "VHGcartstarassign", "VHGcartstarremove",
            "VHGcartplanetassign", "VHGcartplanetremove",
        )),
        "direct editor owns text through cancel, edit, commit, and dynamic cartography wording",
    )
    check(
        all(token in original_outer_hud for token in (
            "if (labstar && c == labstar_char) digit_at ('_', -6, -15, 5, 127 - 2 * (clock()%32), 0);",
            "if (labplanet && c == labplanet_char) digit_at ('_', -6, -15, 5, 127 - 2 * (clock()%32), 0);",
        ))
        and all(token in label_prepare for token in (
            "[VHPtelemetrystaredit] = 0; [VHPtelemetrybodyedit] = 0;",
            "[VHPtelemetrystaredit] = 1;",
            "[VHPtelemetrystarcursor] = [VHGlabelstarpos];",
            "[VHPtelemetrybodyedit] = 1;",
            "[VHPtelemetrybodycursor] = [VHGlabelbodypos];",
        ))
        and all(token in telemetry_text for token in (
            "A = [VHPtelemetryi]; ? A != [VHPtelemetrycursor] -> VHP HUD telemetry character;",
            "A = [VHPtelemetryclock]; A % 32; A '* 2; C = 127; C - A;",
            "[VHPchar] = 95; [VHPtelemetryshader] = 0; => VHP HUD telemetry digit;",
            "[VHPtelemetrycolour] = [VHPtelemetrysavedcolour]; [VHPtelemetryshader] = 1;",
            "A = [VHPchar]; ? A <= 32 -> VHP HUD telemetry digit done;",
            "? A > 96 -> VHP HUD telemetry digit done;",
            "[DGshader] = [VHPtelemetryshader]; => FB digit at;",
        ))
        and telemetry_text.index("[VHPchar] = 95;")
        < telemetry_text.index('"VHP HUD telemetry character"')
        < telemetry_text.index("A = [VHVcamxi]; A - 40;")
        and "[VHVcamxi]" not in section(
            telemetry_text,
            "[VHPchar] = 95;",
            '"VHP HUD telemetry character"',
        ),
        "editing cursor blinks before the fixed-position glyph with native shader ownership",
    )
    repeat_sentinel = section(
        game, '"VHG repeat sentinel option"', '"VHG freeze diagnostic option"'
    )
    freeze_diagnostic = section(
        game, '"VHG freeze diagnostic option"', '"VHG lift trace option"'
    )
    lift_trace_option = section(
        game, '"VHG lift trace option"', '"VHG capsule trace option"'
    )
    capsule_trace_option = section(
        game, '"VHG capsule trace option"', '"VHG profile option"'
    )
    cadence = section(game, '"VHG cadence"', '"VHG timing step"')
    interpolation_advance = section(
        game, '"VHG interpolation advance"', '"VHG interpolation apply"'
    )
    sentinel_schedule = section(
        game, "[VHGsentframes]+;", "( Surface input samples"
    )
    check(
        "VHGsentinelrepeat = 0;" in game
        and all(token in repeat_sentinel for token in (
            "A = Command Line;",
            "? C != 99 -> VHG repeat sentinel next;",
            "? C != 97 -> VHG repeat sentinel next;",
            "? C != 112 -> VHG repeat sentinel next;",
            "? C != 116 -> VHG repeat sentinel next;",
            "? C != 117 -> VHG repeat sentinel next;",
            "? C != 114 -> VHG repeat sentinel next;",
            "? C != 101 -> VHG repeat sentinel next;",
            "? C = 0 -> VHG repeat sentinel found;",
            "? C = 32 -> VHG repeat sentinel found;",
            "[VHGsentinelrepeat] = 1;",
        ))
        and "VHGsentinelfreeze = 0;" in game
        and all(token in freeze_diagnostic for token in (
            "? C != 102 -> VHG freeze next;",
            "? C != 114 -> VHG freeze next;",
            "? C != 101 -> VHG freeze next;",
            "? C != 122 -> VHG freeze next;",
            "[VHGsentinelfreeze] = 1;",
        ))
        and all(token in lift_trace_option for token in (
            "A = Command Line;",
            "? C != 108 -> VHG lift trace next;",
            "? C != 105 -> VHG lift trace next;",
            "? C != 102 -> VHG lift trace next;",
            "? C != 116 -> VHG lift trace next;",
            "? C != 114 -> VHG lift trace next;",
            "? C != 97 -> VHG lift trace next;",
            "? C != 99 -> VHG lift trace next;",
            "? C != 101 -> VHG lift trace next;",
            "? C = 0 -> VHG lift trace found;",
            "? C = 32 -> VHG lift trace found;",
            "[VHGsentinellifttrace] = 1;",
        ))
        and all(token in capsule_trace_option for token in (
            "A = Command Line;",
            "? C != 99 -> VHG capsule trace next;",
            "? C != 97 -> VHG capsule trace next;",
            "? C != 112 -> VHG capsule trace next;",
            "? C != 115 -> VHG capsule trace next;",
            "? C != 117 -> VHG capsule trace next;",
            "? C != 108 -> VHG capsule trace next;",
            "? C != 101 -> VHG capsule trace next;",
            "? C != 116 -> VHG capsule trace next;",
            "? C != 114 -> VHG capsule trace next;",
            "? C = 0 -> VHG capsule trace found;",
            "? C = 32 -> VHG capsule trace found;",
            "[VHGsentinelcapsuletrace] = 1;",
        ))
        and all(token in cadence for token in (
            "A = [VHGsentinelfreeze]; ? A = 0 -> VHG cadence unfrozen;",
            "[VHGdosim] = 0;",
        ))
        and contains_in_order(interpolation_advance, (
            "A = [VHGsentinelfreeze]; ? A = 0 -> VHG interpolation advance live;",
            "[VHGinterpacc] = VHGSIMDEN; -> VHG interpolation advance done;",
            '"VHG interpolation advance live"',
            "A = [VHGfast]; ? A = 0 -> VHG interpolation advance done;",
        ))
        and interpolation_advance.count("[VHGinterpacc] = VHGSIMDEN;") == 1
        and "[VHGframe] = 0; [VHGfreezebrtl] = [brtlseed]; [VHGfreezesuf] = [SUfseed];" in game
        and "[brtlseed] = [VHGfreezebrtl]; [SUfseed] = [VHGfreezesuf];" in game
        and 'A = [VHGsentinelfreeze]; ? A != 0 -> VHG render live;' in game
        and 'A = [VHGsentinelfreeze]; ? A != 0 -> VHG render space clear;' in game
        and 'A = [VHGsentinelfreeze]; ? A != 0 -> VHG render clock frozen;' in game
        and '[VHTclockphase] = 0;' in game
        and "vhglabelname = { game-label-state-out.bin };" in game
        and "vhglabelstate = 8;" in game
        and all(token in game for token in (
            "[vhglabelstate plus 0] = [VHGlabelstar];",
            "[vhglabelstate plus 2] = [VHGlabelstarpos];",
            "[vhglabelstate plus 4] = [VHPtelemetryclock];",
            "[VHPtelemetryclock] = [VHGframe];",
            "[VHPtelemetryclock] = [VHGfreezeblink];",
            "[VHGfreezeblink] + 8;",
            "C = 127; C - A; [vhglabelstate plus 5] = C;",
            "[vhglabelstate plus 6] = [VHGlabelresult];",
            "[vhglabelstate plus 7] = [VHGgameescheld];",
            "[Block Pointer] = vhglabelstate; [Block Size] = 32; isocall;",
            "[File Size] = 32; isocall;",
        ))
        and "=> VHG capture clock option; => VHG repeat sentinel option; => VHG freeze diagnostic option;\n\t=> VHG lift trace option; => VHG capsule trace option; => VHG control trace option; => VHG profile option;" in game
        and all(token in sentinel_schedule for token in (
            "A = [VHGsent]; ? A = 0 -> VHG sentinel frame ready;",
            "A = [VHGsentinelrepeat]; ? A = 0 -> VHG no sentinel;",
            "A = [VHGsentframes]; ? A < 60 -> VHG no sentinel;",
            "=> VHG write sentinel; [VHGsent] = 1; [VHGsentframes] = 0;",
        ))
        and sentinel_schedule.index("A = [VHGsent];")
        < sentinel_schedule.index("A = [VHGsentinelrepeat];")
        < sentinel_schedule.index('"VHG sentinel frame ready"')
        < sentinel_schedule.index("A = [VHGsentframes];")
        < sentinel_schedule.index("=> VHG write sentinel;"),
        "capture opt-in repeats complete diagnostics every 60 rendered frames",
    )
    check(
        "WM_CHAR = 0x0102" in windows_hidden_process
        and all(token in windows_hidden_process for token in (
            "def post_char(self, handle: int, character: str | int) -> None:",
            "codepoint = ord(character) if isinstance(character, str) else character",
            'raise ValueError("post_char accepts one ASCII character")',
            "self.user32.PostMessageW(handle, WM_CHAR, codepoint, 1)",
            "ctypes.set_last_error(0)",
            "raise ctypes.WinError(ctypes.get_last_error())",
        ))
        and "if not 0 <= codepoint <= 0x7F:" in windows_hidden_process,
        "private-desktop input posts one validated ASCII WM_CHAR",
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

    # The unit traversal clamps x/z so every tile's +1 corner stays inside
    # the 200x200 map, including both walking-clamp endpoints.
    for tile_coord in (7, 100, 192):
        lo = max(0, tile_coord - 65)
        hi = min(198, tile_coord + 65)
        coords = list(range(lo, hi + 1))
        check(
            bool(coords) and coords[0] >= 0 and coords[-1] + 1 < 200,
            f"unit terrain range is in bounds at tile {tile_coord}",
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
        "[L2L Region] = vector Work Area; => Update Area Fast;" in gui_loop
        and "[Display Command] = RETRACE; [Display Live Region] = WHOLE DISPLAY; isocall;" not in gui_loop
        and "[Do Not Retrace Arrow Region] = YES;" not in gui_loop
        and "=> VHG copy page;" not in game,
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
            "VHGhelpmenu = { F10:MENU F1:ABOUT CTRL+D:PREFS };",
            "VHGhelpmove = { RMB/ARROWS:LOOK WASD:MOVE CTRL+DOWN:MLOOK };",
            "VHGhelpsave = { F6:SAVE F7:LOAD M/B:SHOT CTRL+S:ROOF };",
            "VHGhelpview = { F4:FPS F5:60HZ F8:MUSIC I:DATA };",
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
        and section(game, '"VHG star palette shades"', '"VHG star palette update done"').count(
            '[PFden] = 1;'
        ) == 3
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
            '[VHGshipoldr] = A; [VHGshipoldg] = A; [VHGshipoldb] = A;',
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
            "[MgStspeed]; A '* 8388608;", 'C + A; [vhsvbuf plus 66] = C;',
            'A / 8388608; A & 1; [MgStspeed] = A;', 'A & 63; [VHGilightlevel] = A;',
            'A & 1; [VHGelight] = A;', '[VHGresetcount] = A;', '[VHGgburst] = A;',
        )),
        "R and 6-9 restore onboard navigation/miscellaneous devices with live powered effects",
    )
    base_palette = section(game, '"VHG palette"', '"VHG star palette"')
    globe_palette = section(ground, '"VHGND globe surface"', '"VHGND general phase setup"')
    check(
        all(token in original for token in (
            "tavola_colori (range8088, 0, 64, 16, 32, 63);",
            "tavola_colori (tmppal, 0, 256, 64, 64, 64);",
        ))
        and "=> PAL zero; => PAL range;" in base_palette
        and "[PVfirst] = 128;" not in base_palette
        and all(token in globe_palette for token in (
            "[SUcbase] = 192; [VHGNDcbase] = 192; => SU select planet;",
            "[SUcbase] = 128; [VHGNDcbase] = 128; => SU select moon;",
            "A = sutmppal; A + C; D = pal6; D + C;",
            '"VHGND globe palette copy"',
        )),
        "an absent moon leaves palette band 128 black until a moon surface owns it",
    )
    resident_scan = section(game, '"VHG local resident scan"', '"VHG local ensure surface"')
    external_camera = section(game, '"VHG render"', '"VHG close star rendered"')
    local_render = section(game, '"VHG local render"', '"VHG local ring"')
    check(
        resident_scan.count("A = [FI]; ? A >= 0") == 3
        and "A = [FI]; ? A '>= 0" not in resident_scan
        and "A = [VHGbeta]; A + [VHGnavbeta]; A + 180; A % 360;" in external_camera
        and "beta = user_beta + navigation_beta + 180;" in original0
        and local_render.index("[VHGNDvecindex] = [VHGplanet]; => VHGND absolute body vector;")
        < local_render.index("=> VHG local resident scan;"),
        "orbital renderer selects the nearest resident maps with signed distances and the native exterior pose",
    )
    fcs_menu_overlay = section(game, '"VHG FCS menu overlay"', '"VHG browse format rows"')
    fcs_row9 = section(game, '"VHG FCS row9 classify"', '"VHG FCS menu key"')
    fcs_menu_key = section(game, '"VHG FCS menu key"', '"VHG device key"')
    check(
        "case '5': sys = 1; dev_page = 0; break;" in original
        and "case '6': s_command = 1; commands (); break;" in original
        and "case '9': s_command = 4; commands (); break;" in original
        and all(token in fcs_menu_overlay for token in (
            '[VHGinfoline] = VHGfcsmenutitle;', 'VHGfcsmremote',
            'VHGfcsmstart', 'VHGfcsmstop', 'VHGfcsmlocal',
            'VHGfcsmcancel', 'VHGfcsmrestart', '=> VHG FCS row9 label;',
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
            '=> VHG FCS row9 action;',
        ))
        and all(token in fcs_row9 for token in (
            'VHGFCS9CLEAR', 'VHGFCS9CANCEL', 'VHGFCS9DEPLOY',
            'VHGFCS9IMPOSSIBLE', 'VHGFCS9ERROR',
            '? A \'< 0 -> VHG FCS row9 classify done;',
            "? A '>= [nsnob] -> VHG FCS row9 classify done;",
            'E = nsptype; E + A; A = [E];',
            '"VHG FCS row9 label"', 'VHGfcsm9clear', 'VHGfcsm9cancel',
            'VHGfcsmcapsule', 'VHGfcsm9impossible', 'VHGfcsm9error',
            '"VHG FCS row9 action"', '=> VHG landing selector start;',
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
    environment_overlay = section(
        ground, '"VHGND environment HUD"', '"VHGND HUD draw string"')
    check(
        environment_text(1000, 220, 1000, 118) ==
        "GRAVITY 1.000 FG & TEMPERATURE +22.0@C & PRESSURE 1.000 ATM & PULSE 118 PPS"
        and all(token in original0 for token in (
            'sprintf (outhudbuffer, "GRAVITY %2.3f FG & TEMPERATURE %+3.1f@C & PRESSURE %2.3f ATM & PULSE %3.0f PPS"',
            "pp_delta = (pp_temp - tp_temp) * 0.05;",
            "pp_delta = (pp_pressure - tp_pressure) * 0.02;",
            "pp_delta = (pp_pulse - tp_pulse) * 0.01;",
            "smootharound_64 (adapted, 9, 188, 5, 1);",
            "if (draw_hud == 0 && about == 0 && taking_snapshot == 0",
            "wrouthud (2, 192, NULL, outhudbuffer);",
        ))
        and "pp_gravity = gravity * 38.26;" in original1
        and 'VHGsurfacetext = { G 0.000FG T +000.0C P 00.000ATM HR 000 };' in game
        and "VHGsurfgravm = 1000; VHGsurftempt = 220; VHGsurfpressm = 1000;" in game
        and "VHGsurftempnow = 220;" in game
        and all(token in surface_telemetry for token in (
            "E = nspray;", "[FI] = 38260;", "[GRSKbasetemp]",
            "[GRSKbasepressure]", "A = [VHGy]; A / 4000;",
            "[VHGsurftiredq]", "A '* 118; A / 10000; A + 118;",
            "A = [VHGutcsecs]; A '/ 2; => SU fast srand;",
            "[SUfmask] = 32767; => SU fast raw;",
            "A '* 8; A '/ 32768;", "[VHGsurfpulsejitter]",
            '"VHG surface telemetry update"', '"VHG surface telemetry smooth"',
            "A = [VHGmode]; ? A = 0 -> VHG surface telemetry smooth;",
            '"VHG surface smooth field"',
            "D = VHGsurfgravdisp; C = 4;", "D = VHGsurftempdisp; C = 20;",
            "D = VHGsurfpressdisp; C = 50;", "D = VHGsurfpulsedisp; C = 100;",
        ))
        and "=> VHG text both;" not in surface_overlay
        and "=> VHG UTC timestamp; => VHG visor advance; => VHG surface telemetry update;" in game
        and game.count("=> VHG surface telemetry overlay;") == 1
        and game.count("=> VHG surface telemetry init;") == 2,
        "shared visor HUD retains source defaults and live surface gravity, temperature, pressure, and pulse telemetry",
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
            '"VHGND HUD lamp smooth"',
            "[VHGNDsmoothcx] = 9; [VHGNDsmoothcy] = 188; => VHGND HUD lamp smooth;",
            "[VHGNDsmoothcx] = 308; [VHGNDsmoothcy] = 188; => VHGND HUD lamp smooth;",
            "A = [VHGNDsmoothpx]; C = A; A '* C; [VHGNDsmoothsum] = A;",
            "? A >= 25 -> VHGND HUD lamp smooth next;",
            "A & 63;", "A & 192; A + [VHGNDsmoothavg]; [D] = A;",
            '"VHGND surface coordinate HUD"', "A = [VHGlandinglon]; => VHGND HUD append number;",
            "A = [VHGx]; A / VHGNDTS; A - 100; => VHGND HUD append number;",
            '"VHGND HUD append number"', '"VHGND HUD row mask"',
            '"VHGND epoch HUD"', "A = [VHGutcsecs]; A / 1000000000; A + 6011;",
            "A = [VHGutcsecs]; A / 1000000; A % 1000; => VHGND HUD append triad;",
            '"VHGND HUD append triad"', "[VHGNDhudsource] = VHGNDepoctext;",
            "? A < 1000 -> VHGND HUD number hundreds;",
            "A / 1000; A + 48; => VHGND HUD append;",
            '"VHGND environment HUD"', "[VHGNDhudy] = 192;",
            "A = [VHGdrawhud]; ? A = 0 -> VHGND environment HUD done;",
            "A = VHGNDenvgravity; => VHGND HUD append text; A = 32; => VHGND HUD append;",
            "A = [VHGsurfgravdisp]; => VHGND HUD append fixed three; A = 32; => VHGND HUD append;",
            "A = [VHGsurftempdisp]; => VHGND HUD append signed fixed one;",
            "A = [VHGsurfpressdisp]; => VHGND HUD append fixed three; A = 32; => VHGND HUD append;",
            "A = [VHGsurfpulsedisp]; => VHGND HUD append width three; A = 32; => VHGND HUD append;",
            'VHGNDenvgravity = { GRAVITY }; VHGNDenvfg = { FG };',
            'VHGNDenvtemperature = { TEMPERATURE }; VHGNDenvdegree = { @C };',
            'VHGNDenvpressure = { PRESSURE }; VHGNDenvatm = { ATM };',
            'VHGNDenvpulse = { PULSE }; VHGNDenvpps = { PPS };',
            'VHGNDshiphints = {  & 5\\FLIGHTCTR R\\DEVICES F2\\PREFS X\\SCREEN OFF };',
            "A = [VHGmode]; ? A != 0 -> VHGND epoch HUD terminate;",
            "A = [VHGonroof]; ? A != 0 -> VHGND epoch HUD terminate;",
            "A = VHGNDshiphints; => VHGND HUD append text;",
            "? A = 92 -> VHGND HUD glyph backslash;", "[VHGNDhudpacked] = 6105;",
        ))
        and environment_overlay.count("A = 32; => VHGND HUD append;") == 13
        and environment_overlay.count("A = 38; => VHGND HUD append;") == 3
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
    timing_step = section(game, '"VHG timing step"', '"VHG timing rebase"')
    check(
        all(token in game for token in (
            '"VHG fast key"', "[KEY F5]", '"VHG cadence"',
            "VHGSIMADD = 18206", '"VHG timing step"',
            "[Timer Command] = READ COUNTS; isocall; [TKnow] = [Counts];",
            "A = [VHGsimcountelapsed]; A '/ [TKcpms]; [VHGsimwhole] = A;",
            "A = [VHGsimrem]; A '* VHGSIMADD; A + [VHGsimfrac];",
            "A = [VHGsiminc]; A + [VHGsimacc]; [VHGsimacc] = A;",
            "? A '< 1000000 -> VHG cadence done;",
            "[VHGsimcountprev] = [TKnow]; [VHGsimcountok] = 1; [VHGdosim] = 1;",
        ))
        and "VHGfast = 1; VHGfastheld = 0; VHGsimacc = 0;" in game
        and game.count("[VHGsimacc] = 1000000;") == 0
        and "A = [VHGfast]; ? A != 0 -> VHG timing fast;" in game
        and "=> TK step;" in timing_step
        and "A = E; ? A < [TKbase] -> VHG timing done;" in timing_step
        and "[TKdeadline] = [TKnow]; [TKacc] = 0;" in timing_step
        and timing_step.index("A = [TKnow]; A - [TKdeadline]; E = A;")
            < timing_step.index("A = [VHGprofileactive];")
            < timing_step.index('"VHG timing miss counted"')
            < timing_step.index("A = E; ? A < [TKbase] -> VHG timing done;")
        and fast_timing_deadline(1000, 1015, 17, 17) == (1017, "wait")
        and fast_timing_deadline(1000, 1020, 17, 17) == (1017, "catch-up")
        and fast_timing_deadline(1000, 1034, 17, 17) == (1034, "rebase")
        and "[VHGNDdosim] = [VHGdosim];" in game
        and "[VHGNDinterpacc] = [VHGinterpacc];" in game
        and ground.count("A = [VHGNDdosim]; ? A = 0") >= 3,
        "60 FPS presentation is default and F5 retains classic presentation without changing simulation cadence",
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
        ))
        and "A = [VHGdrawhud]; ? A = 0 -> VHGND environment HUD done;" in ground
        and "A = [VHGmode]; ? A = 0 -> VHGND environment HUD done;" not in ground
        and all(token in flare for token in (
            '"VHF ghost reflections"', "A = [VHFang]; A % 8;",
            "A = [VHFgdx]; A '* 4;", "[FS0] = [VHFgfx]; => FLoadF32;",
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
    tracking_t_raw = (
        {(x, y) for y in range(169, 172) for x in range(209, 218)}
        | {(x, 172) for x in range(212, 215)}
        | {(213, y) for y in range(173, 187)}
    )
    tracking_sampler_index = ((297 >> 8) << 8) | ((6917 >> 8) & 255)
    tracking_t_closed = {
        point for point in tracking_t_raw
        if not (10 <= point[0] < 310 and point[1] in range(186, 190))
    }
    tex4 = section(pgmem, '"PG tex 4"', '"PG tex 5"')
    hud_digit = section(panels, '"VHP HUD digit"', '"VHP draw quad"')
    surrounding_border = section(
        ground, '"VHGND surrounding border"', '"VHGND HUD lamps"'
    )
    check(
        tracking_sampler_index == 283
        and tracking_sampler_index - 4 == 279
        and "A = RPSM; A - 4; A + [PGtexoff]; A + [PGtmp];" in tex4
        and all(token in hud_digit for token in (
            "[vhcpoly plus 0] = 1099956224; [vhcpoly plus 1] = 3252158464; [vhcpoly plus 2] = 0;",
            "[vhcpoly plus 3] = 1099956224; [vhcpoly plus 4] = 1107558400; [vhcpoly plus 5] = 0;",
            "[vhcpoly plus 6] = 3245342720; [vhcpoly plus 7] = 1107558400; [vhcpoly plus 8] = 0;",
            "[vhcpoly plus 9] = 3245342720; [vhcpoly plus 10] = 3252158464; [vhcpoly plus 11] = 0;",
        ))
        and len(tracking_t_raw) == 44
        and tracking_t_raw - tracking_t_closed == {(213, 186)}
        and len(tracking_t_closed) == 43
        and "A = [VHGhudcount]; A + 9; A - [VHGNDframei];" in surrounding_border
        and "[VHGNDframecount] = 300;" in surrounding_border
        and "=> VHG interpolation apply; => VHG render; => VHGND surrounding frame;" in game
        and original.index("digit_at (fcs_status_extended[c], -6, -15, 6, 120, 1);")
        < original.index("surrounding (0, openhudcount);"),
        "TRACKING T uses the native segment-origin window and closed-visor final mask",
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
            "VHSVVERSION = 18;", "[vhsvbuf plus 24] = [VHTtx];",
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
            "[VHGslactive] = 0; [VHGslphase] = 0;", "=> VHG SL advance; => VHG DL advance; => VHG fpu clean;",
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
            '"VHP status tracking"', "[VHPstatbase] = 54; [VHPstatlen] = 8;",
            '"VHP status moviemaker"', "[VHPstatbase] = 62; [VHPstatlen] = 10;",
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
    normal_preferences = checkpoint_preferences_word(0, 0, 1, 0, 0, 1)
    check(
        normal_preferences == 36
        and checkpoint_preferences(15, 4) == (0, 0, 1, 0, 0, 1)
        and checkpoint_preferences(16, 15) == (1, 1, 1, 1, 0, 1)
        and checkpoint_preferences(17, 4) == (0, 0, 1, 0, 0, 1)
        and checkpoint_preferences(18, normal_preferences) == (0, 0, 1, 0, 0, 1)
        and checkpoint_preferences(18, checkpoint_preferences_word(1, 1, 0, 1, 1, 2))
        == (1, 1, 0, 1, 1, 2)
        and checkpoint_preferences(18, 96) is None
        and checkpoint_preferences(18, 128) is None
        and checkpoint_preferences(17, 16) is None
        and checkpoint_drive(16, 1 << 23, 1) == 0
        and checkpoint_drive(17, 0, 0) == 0
        and checkpoint_drive(17, 1 << 23, 1) == 1
        and checkpoint_drive(18, 0, 0) == 0
        and checkpoint_drive(18, 1 << 23, 1) == 1
        and all(token in save for token in (
            "VHSVVERSION = 18;", "VHSVUNITS = 67;",
            "? A = 16 -> VHSV load version ok; ? A = 17 -> VHSV load version ok;",
            "A = [VHGroofspeed]; A '* 16;", "A = [VHGmouselook]; A '* 32;",
            "[VHGroofspeed] = 0; [VHGmouselook] = 1;",
            "? A = 3 -> VHSV load done;", "[VHGmouselook] = A;",
            "A = [vhsvbuf plus 1]; ? A '< 17 -> VHSV load light fields;",
        ))
        and all(token in capture_script for token in (
            "[ValidateSet(18)]", "[int]$CheckpointVersion = 18,",
            "$u = New-Object 'System.Int32[]' 67", "$u[64] = 36",
            "$u[66] = 4227135", "$byteCount = 268",
        )),
        "v18 preferences preserve v15-v17 defaults, v17 drive bits, and the 67-word fixture",
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
            "[MgStspeed]; A '* 8388608;", "C + A; [vhsvbuf plus 66] = C;",
            "A = 1; A - [MgApreached]; [MgStspeed] = A;",
            "A / 8388608; A & 1; [MgStspeed] = A;", "[VHGilightlevel] = A;",
            "[VHGelight] = A;", "[VHGresetcount] = A;", "[VHGgburst] = A;",
            "[VHGautoscreenoff] = A;", "[VHGdepolarize] = A;", "[VHGnavbeta] = A;",
            "? A < MINIMUM WIDTH -> VHSV load done;", "? A > MAXIMUM HEIGHT -> VHSV load done;",
            "[VHSVmusic] = [VHAwanted];", "[VHAwanted] = [VHSVmusic];",
        ))
        and all(token in game for token in (
            '"VHG load original cadence"', "[VHGNDcaptures] = [VHSVcaptures];",
            '"VHG load stored capsule"', "[VHGNDdropx] = [VHGx]; [VHGNDdropz] = [VHGz];",
            "[VHGNDcamx] = [VHGx]; [VHGNDcamz] = [VHGz]; => service VHGND eye height;",
            "[VHGNDdropx] = [VHSVdropx]; [VHGNDdropz] = [VHSVdropz];",
            "[VHGNDcamx] = [VHGNDdropx]; [VHGNDcamz] = [VHGNDdropz]; => service VHGND eye height;",
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
        "version-17 checkpoints retain drive and lighting state and safely migrate v1-v16 progress",
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
    tree_build = section(ground, '"VHGND tree"', '"VHGND bush"')
    tree_cache = section(
        ground, '"VHGND tree cache advance"', '"VHGND tree"'
    )
    tree_cache_replay = section(
        tree_cache, '"VHGND tree cache replay"', '"VHGND tree cache begin"'
    )
    leaf_cull_frame = section(
        tree_cache, '"VHGND cached leaf cull frame"', '"VHGND cached leaf near cull"'
    )
    leaf_cull = section(
        tree_cache, '"VHGND cached leaf near cull"', '"VHGND tree cache begin"'
    )
    tree_cache_records = section(
        tree_cache, '"VHGND tree cache begin"', '"VHGND tree cache publish"'
    )
    tree_cache_publish = section(
        tree_cache, '"VHGND tree cache publish"', '"VHGND tree cache publish payload"'
    )
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
            "A = VHGNDtsx; A + [VHGNDtreelevel]; [VHGNDtreebxf] = [A];",
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
            "[FS0] = [VHGNDtreebzf]; => FLoadF32;",
            "[XIN] = [VHGNDh1]; => XFromInt; => XAddCore; => XChop32;",
            '"VHGND tree polar vertex"', "A + 72; [VHGNDtreeangle] = A;",
            "A - 36; [VHGNDtreeangle] = A;",
            "[VHVangle] = [VHGNDtreeangle]; => VHV sincos;", '"VHGND tree trig init"',
            "=> VHGND tree direction build; => VHGND tree direction index;",
            "A = VHTdirang; A + [VHTdirindex]; [VHGNDtreeangle] = [A];",
            "A = [VHTdirindex]; A '* 2; C = VHTdircos; C + A;",
            '"VHGND tree leaf tip vertex"', '"VHGND tree polar point"',
            '"VHGND tree wind"', "[VHGNDtreewindx] = [FS0];",
            "[VHGNDtreewindz] = [FS0];",
            "[VHGNDtreelevel]+;", "[VHGNDtreelevel]-;",
            "[VHGNDtreecx] = [VHGNDtreebxf];", "[VHGNDtreecx] = [VHGNDtreeexf];",
            "[FI] = 768; => PGF fromint; [PGFi] = FSTX; => PGF sa;",
            "[FI] = 2048; => PGF fromint; [PGFi] = FSTY; => PGF sa;",
            "[FI] = 256; => PGF fromint; [PGFi] = FSTX; => PGF sa;",
            "[FI] = 768; => PGF fromint; [PGFi] = FSTY; => PGF sa;",
            "[PGtexf] = 5; A = 0; A - 4; [PGtexoff] = A;",
            "[SPterrain] = 0; [SPmapfast] = 1; [SPpixfast] = 0; [SPtrifast] = 0;",
            "[SPterrain] = 0; [SPmapfast] = 1; [SPpixfast] = 0; [SPtrifast] = 1;",
            "A = [DBflar]; A & 15; ? A = 0 -> VHGND tree limb pixel fast;",
            "A = [DBflar]; A & 15; ? A = 0 -> VHGND tree leaf pixel fast;",
            "[PJnrv] = 4; => PG polymap;", "[PJnrv] = 3; => PG polymap;",
            '"VHGND tree root height"', "=> service VHGND eye height;",
            "A = [PGtexoff]; A + 48; [PGtexoff] = A;",
            "[VHGNDmushmask1] = 15; [VHGNDmushmask2] = 3;",
            "[VHGNDmushxf] = [VHGNDtreepx]; [VHGNDmushyf] = [VHGNDtreeleafdrop];",
            "[VHGNDmushzf] = [VHGNDtreepz]; [VHGNDmushfloat] = 1;",
        ))
        and contains_in_order(tree_basis_dispatch, (
            "A = [SPterrain]; ? A != 0 -> PJ vectors terrain;",
            "A = [SPtrifast]; ? A != 0 -> PJ vectors tree triangle;",
            "-> PJ vectors generic;",
            '"PJ vectors tree triangle"',
            "[PJdx] = 3;",
            "-> PJ vectors three build;",
        ))
        and "PJterrainbasisreuse" not in tree_basis_entry
        and "PJterrainbasisbuilt" not in tree_basis_entry
        and '"PJ vectors three build"' in terrain_basis_build
        and "[PJvr] = 3; [PJvv] = 2;" in three_basis_build
        and "=> PJ vc cross;" not in three_basis_build
        and contains_in_order(tree_rotate_dispatch, (
            "[PJmode] = 1;",
            "[PJdx] = [PJnrv];",
            "A = [SPmapfast]; ? A != 0 -> PG pm rotate fixed map;",
            "A = [PJdx]; ? A != 3 -> PG pm rotate four;",
            "[PJnrv] = 3;",
            "=> PJ rotate;",
            "-> PG pm duplicate rotated generic;",
            '"PG pm rotate fixed map"',
            "=> PJ rotate fixed map;",
            "A = [PJdx]; ? A = 3 -> PG pm duplicate rotated generic;",
            "-> PG pm preloaded;",
        ))
        and contains_in_order(leaf_front_dispatch, (
            "A = [PJdoflag];",
            "? A != 4 -> PG pm clip;",
            "A = [SPtrifast]; ? A = 0 -> PG pm front generic;",
            "A = [SPmapfast]; ? A = 0 -> PG pm front generic;",
            "A = [SPterrain]; ? A != 0 -> PG pm front generic;",
            "A = [PJdx]; ? A != 3 -> PG pm front generic;",
            "=> PJ leaf front projectmap;",
            "-> PG pm projected;",
            '"PG pm front generic"',
            "=> PJ zload;",
            "-> PG pm 2d;",
        ))
        and contains_in_order(leaf_front_project, (
            "[fw plus 96] = [fw plus 64]; [fw plus 97] = [fw plus 65];",
            "[fw plus 112] = [fw plus 72]; [fw plus 113] = [fw plus 73];",
            "[fw plus 128] = [fw plus 80]; [fw plus 129] = [fw plus 81];",
            "[fw plus 102] = [fw plus 70]; [fw plus 103] = [fw plus 71];",
            "[fw plus 118] = [fw plus 78]; [fw plus 119] = [fw plus 79];",
            "[fw plus 134] = [fw plus 86]; [fw plus 135] = [fw plus 87];",
            "A = FSRZF; A + 3; [PGFi] = A;",
            "A = FSUZ; A + 3; [PGFj] = A;",
            "[PJvr] = 4; [PJvr2] = 4; [PJvr22] = 8;",
            "[PJvr] = 0;",
            "[PJminx] = PGUBX; [PJmaxx] = PGLBX;",
            "[BXminy] = PGUBY; [BXmaxy] = PGLBY;",
            "[FA0] /: [fw plus 128];",
            "[FI] =: [FA0]; [mp] = [FI];",
            "[FA0] /: [fw plus 134];",
            "[FI] =: [FA0]; [mp plus 7] = [FI];",
            "[PGFi] = FSYC;",
        ))
        and leaf_front_project.count("[fw plus 502] = [FA0];") == 4
        and leaf_front_project.count("/:") == 4
        and leaf_front_project.count("*:") == 8
        and leaf_front_project.count("+:") == 8
        and leaf_front_project.count("=:") == 8
        and leaf_front_project.count("[PJvr]+;") == 4
        and "=> PGF" not in leaf_front_project
        and "PJ zclip" not in leaf_front_project
        and "VHGNDleaftracefan" not in ground
        and "[PJleaftrace]" not in tree_leaf_scope
        and contains_in_order(leaf_trace_dispatch, (
            "[SPsrc] = 1; [PJleaftrace] = 0;",
            "A = [SPtrifast]; ? A = 0 -> PG pm trace call;",
            "A = [SPmapfast]; ? A = 0 -> PG pm trace call;",
            "A = [SPpixfast]; ? A = 0 -> PG pm trace call;",
            "A = [SPterrain]; ? A != 0 -> PG pm trace call;",
            "A = [SPflar]; A & 15; ? A != 0 -> PG pm trace call;",
            "A = [PGtexf]; ? A != 5 -> PG pm trace call;",
            "A = [SPcull]; ? A != 0 -> PG pm trace call;",
            "A = [SPhalf]; ? A != 0 -> PG pm trace call;",
            "[PJleaftrace] = 1;",
            '"PG pm trace call"',
            "=> PG trace;",
            "[PJleaftrace] = 0;",
            "[PJgate] = 0;",
        ))
        and contains_in_order(leaf_trace_control, (
            "D - E; [SPsec] = D;",
            "A = [PJleaftrace]; ? A = 0 -> PG tr generic scanline;",
            "C = [SPi]; C '* 320; C & 65535; C + E; C & 65535; [SPdi] = C;",
            "=> PG tex5 row;",
            "[SPi]+;",
            "A = [BXmaxy]; ? A < [SPi] -> PG tr end;",
            "-> PG tr row;",
            '"PG tr generic scanline"',
            "C = [SPi]; => PG riga; C + E; C & 65535; [SPdi] = C;",
            "=> PG scanline;",
            "A = [SPhalf]; A & 1;",
        ))
        and leaf_trace_control.count("[PJleaftrace]") == 1
        and leaf_trace_control.count("=> PG tex5 row;") == 1
        and leaf_trace_control.count("=> PG scanline;") == 1
        and contains_in_order(tree_rotate, (
            "[PJvr] = 0; [PJdoflag] = 0;",
            '"PJ rotate fixed map vertex"',
            "A = [PJvr]; A + A; D = A;",
            "A = fw plus 520; A + D;",
            "A = fw plus 504; A + D;",
            "A = fw plus 512; A + D;",
            "[FA0] +: [fw plus 496];",
            "~: [FA0]; A = fw plus 64; A + D;",
            "~: [FA0]; A = fw plus 80; A + D;",
            "[FA0] = [fw plus 498]; [FA1] = [fw plus 499];",
            "[FB0] = [fw plus 54]; [FB1] = [fw plus 55]; => FCmp;",
            '"PJ rotate fixed map behind"',
            "A = rwf; A + [PJvr]; [A] = C;",
            "~: [FA0]; A = fw plus 72; A + D;",
            "A = [PJvr]; ? A < [PJnrv] -> PJ rotate fixed map vertex;",
        ))
        and tree_rotate.count("-:") == 5
        and tree_rotate.count("*:") == 8
        and tree_rotate.count("+:") == 2
        and tree_rotate.count("~:") == 7
        and "=> PGF" not in tree_rotate
        and "[PJmode]" not in tree_rotate
        and "VHTdirang = 10; VHTdircos = 20; VHTdirsin = 20;" in ground
        and all(token not in tree for token in (
            "=> FToIntChop; [VHGNDtreebx] = [FI];",
            "=> FToIntChop; [VHGNDtreeby] = [FI];",
            "=> FToIntChop; [VHGNDtreebz] = [FI];",
            "=> FToIntChop; [VHGNDtreescale] = [FI];",
            "=> FToIntChop; [VHGNDtreerange] = [FI];",
            "=> FToIntChop; [VHGNDtreeex] = [FI];",
            "=> FToIntChop; [VHGNDtreeey] = [FI];",
            "=> FToIntChop; [VHGNDtreeez] = [FI];",
            "=> FToIntChop; [VHTnextsc] = [FI];",
        ))
        and "[VHGNDtreeex] = [VHGNDtreebx];" not in tree
        and "crossed trunk" not in tree
        and "crossed leafy crown" not in tree,
        "trees retain binary32 world parameters and execute the source branch stack safely",
    )
    check(
        all(token in ground for token in (
            "VHGNDTREERECORD = 16;", "VHGNDTREECACHEWORDS = 262144;",
            "VHGNDtreecachestamps = 120000; VHGNDtreecachedepths = 120000;",
            "VHGNDtreecachestarts = 120000; VHGNDtreecachecounts = 120000;",
            "VHGNDtreecache0 = 262144; VHGNDtreecache1 = 262144;",
            "A = [VHGNDh1]; A '* 3; A + [VHGNDobjid]; [VHGNDobjcachep] = A;",
        ))
        and contains_in_order(ground, (
            '"VHGND generate"',
            "[VHGNDtick] = 0; [VHGNDptr] = 0; [VHGNDplayerstep] = 0;",
            "=> VHGND tree cache advance;",
            "=> VHGND terrain cache frame;",
            "=> VHGND object view setup;",
            "=> VHGND fauna tiles build;",
            "=> VHGND tree cache frame;",
            "=> VHGND traverse faithful;",
        ))
        and contains_in_order(tree_cache, (
            "[VHGNDtreecachegen]+;",
            '"VHGND tree cache stamps clear"',
            "[VHGNDtreecachegen] = 1;",
            '"VHGND tree cache frame"',
            "=> VHGND tree cache advance;",
            "[VHGNDtreecachecursor] = 0;",
            "A = VHGNDtreecache1; [VHGNDtreecachewritebase] = A;",
            "A = VHGNDtreecache0; [VHGNDtreecachereadbase] = A;",
            '"VHGND tree cache frame even"',
            "A = VHGNDtreecache0; [VHGNDtreecachewritebase] = A;",
            "A = VHGNDtreecache1; [VHGNDtreecachereadbase] = A;",
            '"VHGND tree cache lookup"',
            "A = VHGNDtreecachestamps; A + [VHGNDobjcachep]; C = [A];",
            "A = [VHGNDtreecachegen]; A - 1; ? A != C -> VHGND tree cache lookup done;",
            "A = VHGNDtreecachedepths; A + [VHGNDobjcachep]; C = [A];",
            "A = [VHGNDdepth]; ? A != C -> VHGND tree cache lookup done;",
            "[VHGNDtreecachehit] = 1;",
        ))
        and contains_in_order(tree_cache_replay, (
            "[VHGNDtreecachecopy] = 1;",
            "A = [VHGNDtreecachecount]; A '* VHGNDTREERECORD; A + [VHGNDtreecachecursor];",
            "? A '<= VHGNDTREECACHEWORDS -> VHGND tree cache replay capacity ready;",
            "[VHGNDtreecachecopy] = 0;",
            "[VHGNDtreecachestart] = [VHGNDtreecachecursor];",
            '"VHGND tree cache replay record"',
            "A = [VHGNDtreecachereadbase]; A + [VHGNDtreecachep]; [VHGNDtreecacherecordp] = A;",
            "A = [VHGNDtreecachecopy]; ? A = 0 -> VHGND tree cache replay load;",
            "B = [C]; [A] = B; B = [C plus 1]; [A plus 1] = B;",
            "B = [C plus 14]; [A plus 14] = B; B = [C plus 15]; [A plus 15] = B;",
            "A = [VHGNDtreecachecursor]; A + VHGNDTREERECORD; [VHGNDtreecachecursor] = A;",
            '"VHGND tree cache replay load"',
            "A = [C plus 1]; [SUfseed] = A;",
            "A = [C]; ? A = 2 -> VHGND tree cache replay leaf;",
            "=> VHGND tree limb;",
            '"VHGND tree cache replay leaf"',
            "=> VHGND tree leaves;",
            "A = [C plus 15]; [SUfseed] = A;",
            "=> VHGND tree cache publish payload;",
        ))
        and all(token in tree_cache_replay for token in (
            "[SPcull] = 0; [DBent] = 0; [VHGNDtreefloat] = 1;",
            "A = [C plus 2]; [VHGNDtreebxf] = A;",
            "A = [C plus 4]; [VHGNDtreebzf] = A;",
            "A = [C plus 8]; [VHGNDtreebr] = A;",
            "A = [C plus 11]; [VHTfacebase] = A;",
            "A = [C plus 13]; [DBflar] = A;",
            "A = [C plus 5]; [VHGNDtreeexf] = A;",
            "A = [C plus 10]; [VHGNDtreeisroot] = A;",
            "A = [C plus 5]; [VHGNDtreeleafx] = A;",
            "A = [C plus 9]; [VHGNDtreerangef] = A;",
        ))
        and contains_in_order(tree_cache_records, (
            "[VHGNDtreecachestart] = [VHGNDtreecachecursor];",
            '"VHGND tree cache reserve"',
            "A = [VHGNDtreecachecursor]; A + VHGNDTREERECORD;",
            "? A '<= VHGNDTREECACHEWORDS -> VHGND tree cache reserve ready;",
            "[VHGNDtreecachecursor] = [VHGNDtreecachestart]; [VHGNDtreecacherecording] = 0;",
            '"VHGND tree cache reserve ready"',
            "[VHGNDtreecachecount]+; [VHGNDtreecacherecordok] = 1;",
            '"VHGND tree cache record limb"',
            "[C] = 1; A = [SUfseed]; [C plus 1] = A;",
            "A = [VHGNDtreeisroot]; [C plus 10] = A;",
            '"VHGND tree cache record leaf"',
            "[C] = 2; A = [SUfseed]; [C plus 1] = A;",
            "A = [VHGNDtreerangef]; [C plus 9] = A;",
            '"VHGND tree cache record finish"',
            "A = [SUfseed]; [C plus 15] = A;",
        ))
        and contains_in_order(tree_cache_publish, (
            "A = [VHGNDtreecachecount]; ? A <= 0 -> VHGND tree cache publish rollback;",
            "=> VHGND tree cache publish payload;",
            '"VHGND tree cache publish rollback"',
            "[VHGNDtreecachecursor] = [VHGNDtreecachestart];",
        ))
        and contains_in_order(tree_cache, (
            '"VHGND tree cache publish payload"',
            "A = VHGNDtreecachestarts; A + [VHGNDobjcachep]; C = [VHGNDtreecachestart]; [A] = C;",
            "A = VHGNDtreecachecounts; A + [VHGNDobjcachep]; C = [VHGNDtreecachecount]; [A] = C;",
            "A = VHGNDtreecachedepths; A + [VHGNDobjcachep]; C = [VHGNDdepth]; [A] = C;",
            "A = VHGNDtreecachestamps; A + [VHGNDobjcachep]; C = [VHGNDtreecachegen]; [A] = C;",
        ))
        and contains_in_order(tree_build, (
            "=> VHGND tree cache lookup;",
            "=> VHGND tree cache replay; -> VHGND tree done;",
            '"VHGND tree configured"',
            "A = VHGNDtsocc; [A] = 0;",
            "=> VHGND tree cache begin;",
            "=> VHGND tree cache record limb; => VHGND tree limb; => VHGND tree cache record finish;",
            "=> VHGND tree cache record leaf; => VHGND tree leaves; => VHGND tree cache record finish;",
            '"VHGND tree done"',
            "=> VHGND tree cache publish;",
        ))
        and "tree cache" not in bush,
        "configured tall trees cache exact ordered draw commands with atomic fallback and RNG replay",
    )
    check(
        "=> VHGND cached leaf cull frame;" in ground
        and contains_in_order(tree_cache_replay, (
            '"VHGND tree cache replay leaf"',
            "A = [C plus 7]; [VHGNDtreeleafdrop] = A; A = [C plus 9]; [VHGNDtreerangef] = A;",
            "=> VHGND cached leaf near cull;",
            "? A = 0 -> VHGND tree cache replay leaf render;",
            "[SPterrain] = 0; [SPmapfast] = 0; [SPpixfast] = 0; [SPtrifast] = 0;",
            "[VHGNDmushouter] = 0; [VHGNDmushinner] = 0; [SUfmask] = 1023;",
            "[PJnrv] = 1; [PJmode] = 1; [PJvr] = 0; [PJdx] = 3; [PJdoflag] = 0;",
            "-> VHGND tree cache replay record done;",
            '"VHGND tree cache replay leaf render"',
            "=> VHGND tree leaves;",
            '"VHGND tree cache replay record done"',
            "A = [C plus 15]; [SUfseed] = A;",
        ))
        and all(token in leaf_cull_frame for token in (
            "A = [fw plus 429]; A & 7FF00000h;",
            "A = [fw plus 55]; A & 7FF00000h;",
            "[FI] = 32; => PGF fromint;",
            "[FI] = 1056; => PGF fromint;",
            "[FA0] +: [FB0];",
            "[FA0] *: [FB0];",
            "[VHGNDleafcullframeok] = 1;",
        ))
        and all(token in leaf_cull for token in (
            "A = [VHGNDleafcullframeok]; ? A = 0 -> VHGND cached leaf near cull done;",
            "Every record input stays below 2^27 in magnitude before this shortcut.",
            "A = [C plus 2]; A & 7FFFFFFFh; ? A >= 4D000000h",
            "A = [C plus 9]; A & 7FFFFFFFh; ? A >= 4D000000h",
            "A = [VHGNDtreewindx]; A & 7FFFFFFFh; ? A >= 4D000000h",
            "A = [VHGNDtreewindz]; A & 7FFFFFFFh; ? A >= 4D000000h",
            "[FB0] = [VHGNDleafcullsupport0]; [FB1] = [VHGNDleafcullsupport1]; [FA0] +: [FB0];",
            "[VHGNDleafcullret] = 1;",
        ))
        and leaf_cull.count(
            "A & 7FFFFFFFh; ? A >= 4D000000h -> VHGND cached leaf near cull done;"
        ) == 10
        and "7F800000h" not in leaf_cull
        and leaf_cull.count("[PJnrv] = 1; => PJ rotate fixed map;") == 2
        and leaf_cull.count("[FB0] = [fw plus 54]; [FB1] = [fw plus 55]; => FCmp;") == 2
        and leaf_cull.count("? A >= 0 -> VHGND cached leaf near cull done;") == 2
        and "Timer Command" not in leaf_cull_frame
        and "Timer Command" not in leaf_cull,
        "cached leaf replay rejects only conservative all-behind fan and greenmush envelopes",
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
            "C - A; C / 8; [VHGNDooy] = C;",
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
            "[VHGNDgrassfaces] = 6;", "[SUfmask] = 7; => VHGND render random; C + 1;",
            '"VHGND veget distant"', "[VHGNDmushscale] = 1023;",
            "[VHGNDmushbase] = 216;", "=> VHGND greenmush;",
            "A '* 1000; A '/ 32767;", "[VHGNDgrassby] = A;",
            "[VHGNDgrasstotal]-; -> VHGND veget blade;",
        ))
        and all(token in greenmush for token in (
            "[SUfmask] = [VHGNDmushmask1]; => VHGND render random;",
            "[SUfmask] = [VHGNDmushmask2]; => VHGND render random;",
            '"VHGND greenmush inner"',
            "A = [SUfseed]; [m64a] = A; [m64b] = A;",
            "B = A; A *%' B; [m64lo] = A; [m64hi] = B;",
            "C = A; C & 0FFh; B & 0FFh; C + B; C & 0FFh;",
            "A & 0FFFFFF00h; A | C; [SUfeax] = A;",
            "B = [SUfseed]; B + A; [SUfseed] = B;",
            "A & [SUfmask]; [SUfval] = A; C = A;",
            "A = [VHGNDmushfloat]; ? A = 0 -> VHGND greenmush integer z;",
            "A = [VHGNDmushfloat]; ? A = 0 -> VHGND greenmush integer y;",
            "A = [VHGNDmushfloat]; ? A = 0 -> VHGND greenmush integer x;",
            "=> PG getcoords;",
            "A = [GCy]; A '* 320; A + [GCx]; A + nw; A + RADPT; [VHGNDmushorigin] = A;",
            "[SUfmask] = 7; => VHGND render random; A = C; A '* 320; [VHGNDmushoff] = A;",
            "=> VHGND render random; A = C; C = [VHGNDmushoff]; C + A; [VHGNDmushoff] = C;",
            "[SUfmask] = [VHGNDmushcolmask]; => VHGND render random; C + [VHGNDmushbase];",
            "D = [VHGNDmushorigin]; D + [VHGNDmushoff];",
            "[D] = C; [D plus 1] = C; [D minus 1] = C; [D plus 320] = C;",
            "[D minus 320] = C; [D minus 640] = C;",
            "[VHGNDmushinner] ^ VHGND greenmush inner;",
            "[VHGNDmushouter] ^ VHGND greenmush outer;",
        )),
        "grass tufts restore source depth visibility, density, scale, and distant foliage",
    )
    stamp_points = (
        (6, 11), (160, 100), (310, 189),
        (0x7FFFFFFF, -0x80000000), (-0x80000000, 0x7FFFFFFF),
    )
    check(
        all(
            legacy_greenmush_destination(x, y, rx, ry, page, radpt) ==
            hoisted_greenmush_destination(x, y, rx, ry, page, radpt)
            for x, y in stamp_points
            for rx in range(8)
            for ry in range(8)
            for page, radpt in ((0, 0), (0x12345678, 0x76543210),
                                (-0x80000000, 0x7FFFFFFF))
        )
        and ground.count("[VHGNDmushorigin]") == 2,
        "foliage hoists the fixed screen origin without changing wrapped destinations",
    )
    check(
        greenmush.count("[FI] = [VHGNDtmp];") == 3
        and greenmush.count(
            "[FB0] = [FA0]; [FB1] = [FA1]; [FA0] := [FI];") == 3
        and greenmush.count(
            "[FA0] +: [FB0]; ~: [FA0]; => VHGND store narrowed;") == 3
        and all(greenmush.count(token) == 2 for token in (
            "[PGFt] = [VHGNDmushxf];",
            "[PGFt] = [VHGNDmushyf];",
            "[PGFt] = [VHGNDmushzf];",
        ))
        and all(token in greenmush for token in (
            "[FI] = C; [FB0] := [FI]; [PGFt] = [VHGNDmushzf]; [FS0] = [VHGNDmushzf]; => FLoadF32;",
            "[FI] = C; [FB0] := [FI]; [PGFt] = [VHGNDmushyf]; [FS0] = [VHGNDmushyf]; => FLoadF32;",
            "[FI] = C; [FB0] := [FI]; [PGFt] = [VHGNDmushxf]; [FS0] = [VHGNDmushxf]; => FLoadF32;",
            "[PGFi] = FSINX; [PGFt] = [VHGNDmushpxf]; [FS0] = [VHGNDmushpxf]; => FLoadF32; [fw plus 504] = [FA0]; [fw plus 505] = [FA1];",
            "[PGFi] = FSINY; [PGFt] = [VHGNDmushpyf]; [FS0] = [VHGNDmushpyf]; => FLoadF32; [fw plus 512] = [FA0]; [fw plus 513] = [FA1];",
            "[PGFi] = FSINZ; [PGFt] = [VHGNDmushpzf]; [FS0] = [VHGNDmushpzf]; => FLoadF32; [fw plus 520] = [FA0]; [fw plus 521] = [FA1];",
        ))
        and greenmush.count(
            "[FA0] -: [FB0]; ~: [FA0]; => VHGND store narrowed;") == 3
        and "=> PGF fromint; => VHGND fb fa;" not in greenmush
        and "=> PGF setf32;" not in greenmush,
        "floating foliage expands exact scalar wrappers into fixed slots",
    )
    narrowed_store = section(
        greenmush, '"VHGND store narrowed"', '"VHGND render random"'
    )
    check(
        contains_in_order(narrowed_store, (
            "A = [FA1]; A > 20; A & 7FFh;",
            "? A <= 896 -> VHGND store narrowed underflow;",
            "? A >= 1151 -> VHGND store narrowed overflow;",
            "A - 896; C = A; C < 23;",
            "A = [FA1]; A & 0FFFFFh; A < 3;",
            "B = [FA0]; B > 29; A | B; A | C;",
            "B = [FA1]; B > 31; B < 31; A | B; [FS0] = A;",
            '"VHGND store narrowed underflow"',
            "A = [FA1]; A > 31; A < 31; [FS0] = A;",
            '"VHGND store narrowed overflow"',
            "A = 7F800000h; B = [FA1]; B > 31; B < 31; A | B; [FS0] = A;",
        ))
        and "=> FStoreF32;" not in greenmush,
        "foliage extracts an already-narrowed value without a second converter",
    )
    store_cases = []
    fractions = (0, 1, 0x155555, 0x3FFFFF, 0x400000, 0x7FFFFF)
    for sign in (0, 1):
        for exponent in range(256):
            store_cases.extend(
                (sign << 31) | (exponent << 23) | fraction
                for fraction in fractions
            )
    check(
        all(
            greenmush_store_narrowed(*widen_f32_image(bits)) == (
                (bits & 0x80000000)
                if ((bits >> 23) & 0xFF) == 0 else
                ((bits & 0x80000000) | 0x7F800000)
                if ((bits >> 23) & 0xFF) == 0xFF else bits
            )
            for bits in store_cases
        ),
        "narrowed foliage extraction matches FStoreF32 across every exponent class",
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
            'Every level applies the source value >= abs(level) cutoff',
            '"GR sc power done"',
            "=> FSqrt;", "=> FCos;", "=> FSin;",
            "=> XMulCore; => XToF32;",
        ))
        and not re.search(r"^\s*\{", grnd, re.MULTILINE)
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
        and water.count("=> PG polymap;") == 0
        and all(token in water for token in (
            '"VHGND water backdrop"',
            "A = [VHGNDalpha]; A '* 5; C = 100; C - A;",
            "[VHGNDwaterbase] = 128;",
            "A + 144; [VHGNDwaterbase] = A;",
            "A = [VHGNDwatery]; A '* 320; A + 5; A + RADPT; A + nw;",
            "? A '< 191 -> VHGND water backdrop row;",
        )),
        "open-ocean worlds render a clipped stable sea backdrop, rare islands, and no floating objects",
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
            "VHGNDruins = 40000;", '"VHGND render ruins"', "[FI] = 512; => PGF fromint;",
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
    original_surface_blur = section(
        original1,
        "if (waveblur) {",
        "if (moviestat)",
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
        and "waveblur = 1 + random (3);" in original1
        and "while (ptr)" in original_surface_blur
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
            '"VHGND wave impact finish"',
            "[VHGNDblurpasses] = A; [VHGNDblursize] = 57920;",
            "A = [VHGNDdosim]; ? A = 0 -> VHGND wave next;",
        ))
        and "[VHGNDalpha] = [VHGalpha]; [VHGNDbeta] = [VHGbeta]; [VHGNDdosim] = [VHGdosim];" in game
        and "[VHGalpha] = A; => VHGND wave impact finish;" in game
        and waves.count("=> PG polymap;") == 1,
        "open oceans carry paced wind crests, wakes, and wet-lens wave impacts",
    )
    check(
        original_surface_blur.count("psmooth_64 (adapted, 160);") == 3
        and "QUADWORDS = 160 + openhudcount * 80;" in original_surface_blur
        and all(token in ground for token in (
            '"VHGND ordinary surface blur"',
            "A = [VHGNDwaveblur]; ? A <= 0 -> VHGND ordinary surface blur;",
            "[VHGNDblurpasses] = 2;",
            "A = [VHGNDhudcount]; A '* 320; A + 320;",
            "A + 2556; [VHGNDblurp] = A;",
            "C = E; C + 321; C = [C]; C & 63; A + C;",
            "A > 2; C = [VHGNDblurval]; C & 192; A | C; [D] = A;",
        ))
        and "[VHGNDhudcount] = [VHGhudcount];" in game,
        "ordinary surface frames restore both exact source smoothing passes",
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
            '"VHGND animal distance"', "=> FSqrt; => PGF int;",
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
            "[FB0] = 54442D18h; [FB1] = 400921FBh; => FQuo; => PGF int;",
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
            "CTRL:STALK", "RMB/ARROWS:LOOK WASD:MOVE CTRL+DOWN:MLOOK",
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
        and "C = [VHScolor]; C & 255; [D plus 1] = C;" in stick,
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
            '"VHGUI 1x row"', '"VHGUI maybe 2x"', '"VHGUI scaled"',
            '"VHGUI compose row"', '"VHGUI compose pixel"',
            '"VHGUI 2x row"', '"VHGUI 2x pixel"',
            '"VHGUI row"', '"VHGUI pixel"',
            '"VHGUI x advance"', '"VHGUI y advance"',
        )),
        "portable Lino presenter has 1x, 2x, and arbitrary 8:5 aspect-fit paths",
    )
    check(
        "=> FB expand;" not in gui_loop
        and "C + nw; C + RADPT;" in gui
        and "A = [C]; A + pal; [D] = [A];" in gui
        and "D + Backdrop Layer" in gui
        and "[VHGUIpublished] = 0;" in gui
        and "=> Update Area Fast;" in game
        and "[D] = A" in gui,
        "GUI presenter composes and scales the logical page in portable Lino",
    )
    eye = section(ground, '"service VHGND eye height"', '"VHGND render"')
    check(
        "VHGNDQIDHI" in eye
        and eye.count("=> XSubCore;") == 4
        and eye.count("=> XAddCore;") == 4
        and eye.count("=> XToF32;") == 4
        and "[FS0] = [VHGNDpy]; => FLoadF32; => FToIntChop;" in eye
        and not re.search(r"^\s*\{", eye, re.MULTILINE)
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
        and "A = [VHGNDalpha]; A + 51; A '* 360;" in ground
        and "C = [VHGNDbgangle]; C % 360; A - C; [VHGNDbgstart] = A;" in ground
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
