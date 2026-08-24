#!/usr/bin/env python3
"""Exercise capsule recovery through its clean Stardrifter handoff."""

from __future__ import annotations

import hashlib
from pathlib import Path
import struct
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from profile_noctis_desktop import (  # noqa: E402
    CLOCK_SECONDS,
    VK_ESCAPE,
    scenario_checkpoint,
    stage_scenario,
    tap_key,
    wait_for_ready,
)
from windows_hidden_process import PrivateDesktopProcess  # noqa: E402


STAGE_ROOT = ROOT / "build" / "capsule-runtime"
EXECUTABLE = ROOT / "work" / "vhgame.exe"
CAPTURE_TIMEOUT = 240.0
RECORD_BYTES = 64
PAGE_BYTES = 64000
FAILURES: list[str] = []
CapsuleRecord = tuple[
    int, int, int, int, int, int, int, int,
    int, int, int, int, int, int, int, int,
]

STATE = 0
COUNT = 1
RECOVER = 2
LANDED = 3
MODE = 4
RETURN_PENDING = 5
X = 6
Y = 7
Z = 8
GROUND = 9
GRAVITY = 10
WIND_ANGLE = 11
WIND_POWER = 12
FRAME = 13
INTERPOLATION_OK = 14
DO_SIMULATION = 15


def check(condition: bool, label: str) -> None:
    if condition:
        print(f"  PASS {label}")
        return
    FAILURES.append(label)
    print(f"  FAIL {label}")


def stage_run() -> tuple[Path, Path]:
    stage = STAGE_ROOT / "return"
    executable = stage_scenario(stage, EXECUTABLE, scenario_checkpoint("capsule"))
    for filename in ("game-capsule-state-out.bin", "game-capsule-pages-out.bin"):
        path = stage / filename
        if path.exists():
            path.unlink()
    return stage, executable


def read_trace(stage: Path) -> tuple[list[CapsuleRecord], list[bytes]] | None:
    state_path = stage / "game-capsule-state-out.bin"
    pages_path = stage / "game-capsule-pages-out.bin"
    try:
        state_size = state_path.stat().st_size
        pages_size = pages_path.stat().st_size
    except FileNotFoundError:
        return None
    if state_size == 0 or state_size % RECORD_BYTES:
        return None
    count = state_size // RECORD_BYTES
    if pages_size != count * PAGE_BYTES:
        return None
    state_data = state_path.read_bytes()
    page_data = pages_path.read_bytes()
    if len(state_data) != state_size or len(page_data) != pages_size:
        return None
    records = [
        struct.unpack_from("<16i", state_data, index * RECORD_BYTES)
        for index in range(count)
    ]
    pages = [
        page_data[index * PAGE_BYTES:(index + 1) * PAGE_BYTES]
        for index in range(count)
    ]
    return records, pages


def wait_for_trace(
    process: PrivateDesktopProcess,
    stage: Path,
    timeout: float = CAPTURE_TIMEOUT,
) -> tuple[list[CapsuleRecord], list[bytes]]:
    deadline = time.monotonic() + timeout
    stable: tuple[int, int, int, int] | None = None
    while time.monotonic() < deadline:
        return_code = process.poll()
        if return_code is not None:
            raise RuntimeError(
                f"game exited while tracing capsule recovery with code {return_code}"
            )
        trace = read_trace(stage)
        if trace is None:
            stable = None
            time.sleep(0.05)
            continue
        records, pages = trace
        final = records[-1]
        if not (
            final[STATE] == 0
            and final[COUNT] == 0
            and final[MODE] == 0
            and final[RETURN_PENDING] == 0
        ):
            stable = None
            time.sleep(0.05)
            continue
        state_path = stage / "game-capsule-state-out.bin"
        pages_path = stage / "game-capsule-pages-out.bin"
        signature = (
            state_path.stat().st_size,
            state_path.stat().st_mtime_ns,
            pages_path.stat().st_size,
            pages_path.stat().st_mtime_ns,
        )
        if signature == stable:
            return records, pages
        stable = signature
        time.sleep(0.10)
    raise TimeoutError(f"capsule trace did not reach the ship within {timeout:.0f}s")


def exit_cleanly(process: PrivateDesktopProcess, handle: int) -> None:
    for _attempt in range(3):
        if process.poll() is not None:
            break
        tap_key(process, handle, VK_ESCAPE, 0.20)
        if process.wait(3.0) is not None:
            break
    return_code = process.poll()
    if return_code is None:
        raise TimeoutError("game did not exit cleanly after three Escape presses")
    if return_code != 0:
        raise RuntimeError(f"game exited with code {return_code}")


def page_difference_count(left: bytes, right: bytes) -> int:
    return sum(a != b for a, b in zip(left, right))


def page_band_difference_count(left: bytes, right: bytes) -> int:
    return sum((a & 0xC0) != (b & 0xC0) for a, b in zip(left, right))


def expected_ascent_y(count: int, sealed_y: int) -> int:
    if count <= 32:
        return sealed_y
    highest_offset = count - 31
    offset_sum = highest_offset * (highest_offset + 1) // 2 - 1
    return sealed_y - 20 * offset_sum


def run_return() -> tuple[list[CapsuleRecord], list[bytes]]:
    stage, executable = stage_run()
    with PrivateDesktopProcess(
        executable,
        stage,
        (f"clock={CLOCK_SECONDS}", "capture", "capsuletrace"),
    ) as process:
        handle, _rectangle = wait_for_ready(process, stage, CAPTURE_TIMEOUT)
        process.post_char(handle, "r")
        records, pages = wait_for_trace(process, stage)
        exit_cleanly(process, handle)
    return records, pages


def main() -> int:
    if sys.platform != "win32":
        print("capsule runtime: skipped (requires Windows private desktop)")
        return 0
    if not EXECUTABLE.is_file():
        print(f"capsule runtime: missing {EXECUTABLE}")
        return 1

    records, pages = run_return()
    active = records[:250]
    surface_handoff = records[250] if len(records) > 250 else None
    ship_handoff = records[251] if len(records) > 251 else None

    check(
        len(records) == 252 and len(pages) == 252,
        "trace retains 250 recovery ticks plus surface and ship handoff frames",
    )
    check(
        len(active) == 250
        and tuple(record[COUNT] for record in active) == tuple(range(1, 251))
        and all(record[STATE] == 2 and record[RECOVER] == 1 for record in active),
        "authoritative recovery state advances through every source count 1-250",
    )
    check(
        len(active) == 250
        and all(record[LANDED] == 1 for record in active[:32])
        and all(record[LANDED] == 0 for record in active[32:]),
        "the first 32 sealing ticks stay landed and count 33 lifts off",
    )
    if active:
        sealed_y = active[0][Y]
        check(
            tuple(record[Y] for record in active)
            == tuple(expected_ascent_y(count, sealed_y) for count in range(1, 251)),
            "live ascent applies the cumulative -(count-31)*20 source displacement",
        )
        check(
            all(
                record[X] == active[0][X]
                and record[Z] == active[0][Z]
                and record[GROUND] == active[0][GROUND]
                and record[GRAVITY] == active[0][GRAVITY]
                for record in active
            ),
            "capsule ascent retains its authoritative lateral pose, ground, and gravity",
        )
    else:
        check(False, "live ascent applies the cumulative source displacement")
        check(False, "capsule ascent retains its authoritative scalar pose")

    check(
        surface_handoff is not None
        and surface_handoff[STATE] == 0
        and surface_handoff[COUNT] == 0
        and surface_handoff[RECOVER] == 0
        and surface_handoff[LANDED] == 0
        and surface_handoff[MODE] == 1
        and surface_handoff[RETURN_PENDING] == 1,
        "count 251 renders one complete cleared surface frame with return pending",
    )
    check(
        ship_handoff is not None
        and ship_handoff[STATE] == 0
        and ship_handoff[COUNT] == 0
        and ship_handoff[RECOVER] == 0
        and ship_handoff[LANDED] == 0
        and ship_handoff[MODE] == 0
        and ship_handoff[RETURN_PENDING] == 0,
        "the following complete frame commits the clean Stardrifter handoff",
    )
    check(
        all(record[DO_SIMULATION] == 1 for record in records)
        and all(
            later[FRAME] == earlier[FRAME] + 1
            for earlier, later in zip(records, records[1:])
        ),
        "every retained state is one consecutive authoritative simulation tick",
    )
    check(
        len(pages) == len(records)
        and all(len(page) == PAGE_BYTES for page in pages),
        "every scalar state retains one complete 64,000-byte indexed page",
    )

    if len(pages) == 252:
        lift_difference = page_difference_count(pages[31], pages[32])
        surface_difference = page_difference_count(pages[249], pages[250])
        ship_difference = page_difference_count(pages[250], pages[251])
        ship_band_difference = page_band_difference_count(pages[250], pages[251])
        check(
            lift_difference > 0 and surface_difference > 0,
            "indexed pages expose both lift-off and count-251 surface transitions",
        )
        check(
            ship_difference > 1000 and ship_band_difference > 100,
            "surface-to-ship handoff substantially changes indexed geometry and bands",
        )
        print(
            "  INFO transition differences: "
            f"lift={lift_difference} surface={surface_difference} "
            f"ship={ship_difference} ship-bands={ship_band_difference}"
        )
        for index in (0, 31, 32, 249, 250, 251):
            print(
                f"  INFO record {index}: {records[index]} "
                f"page={hashlib.sha256(pages[index]).hexdigest()[:16]}"
            )
    else:
        check(False, "indexed pages expose the lift-off and surface transitions")
        check(False, "surface-to-ship handoff substantially changes indexed geometry")

    if FAILURES:
        print(f"capsule runtime: {len(FAILURES)} failure(s)")
        return 1
    print("capsule runtime: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
