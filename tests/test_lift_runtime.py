#!/usr/bin/env python3
"""Exercise the source-shaped Stardrifter lift on an inactive desktop."""

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


STAGE_ROOT = ROOT / "build" / "lift-runtime"
EXECUTABLE = ROOT / "work" / "vhgame.exe"
CAPTURE_TIMEOUT = 90.0
VK_E = 0x45
RECORD_BYTES = 32
PAGE_BYTES = 64000
FAILURES: list[str] = []
LiftRecord = tuple[int, int, int, int, int, int, int, int]


def check(condition: bool, label: str) -> None:
    if condition:
        print(f"  PASS {label}")
        return
    FAILURES.append(label)
    print(f"  FAIL {label}")


def lift_checkpoint(y: int) -> bytes:
    checkpoint = bytearray(scenario_checkpoint("stardrifter"))
    struct.pack_into("<5i", checkpoint, 4 * 4, 0, y, -3100, 0, 0)
    return bytes(checkpoint)


def stage_run(name: str, y: int) -> tuple[Path, Path]:
    stage = STAGE_ROOT / name
    executable = stage_scenario(stage, EXECUTABLE, lift_checkpoint(y))
    for filename in ("game-lift-state-out.bin", "game-lift-pages-out.bin"):
        path = stage / filename
        if path.exists():
            path.unlink()
    return stage, executable


def read_trace(stage: Path) -> tuple[list[LiftRecord], list[bytes]] | None:
    state_path = stage / "game-lift-state-out.bin"
    pages_path = stage / "game-lift-pages-out.bin"
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
        struct.unpack_from("<8i", state_data, index * RECORD_BYTES)
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
    final_y: int,
    timeout: float = CAPTURE_TIMEOUT,
) -> tuple[list[LiftRecord], list[bytes]]:
    deadline = time.monotonic() + timeout
    stable: tuple[int, int, int, int] | None = None
    while time.monotonic() < deadline:
        return_code = process.poll()
        if return_code is not None:
            raise RuntimeError(f"game exited while tracing the lift with code {return_code}")
        trace = read_trace(stage)
        if trace is None:
            stable = None
            time.sleep(0.05)
            continue
        records, pages = trace
        if records[-1][0] != final_y or records[-1][1] != 0:
            stable = None
            time.sleep(0.05)
            continue
        state_path = stage / "game-lift-state-out.bin"
        pages_path = stage / "game-lift-pages-out.bin"
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
    raise TimeoutError(f"lift trace did not reach y={final_y} within {timeout:.0f}s")


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


def crop_band_difference_count(
    left: bytes,
    right: bytes,
    box: tuple[int, int, int, int],
) -> int:
    x0, y0, x1, y1 = box
    return sum(
        left[y * 320 + x] >> 6 != right[y * 320 + x] >> 6
        for y in range(y0, y1)
        for x in range(x0, x1)
    )


def run_ascent() -> tuple[list[LiftRecord], list[bytes]]:
    stage, executable = stage_run("ascent", 0)
    with PrivateDesktopProcess(
        executable,
        stage,
        (f"clock={CLOCK_SECONDS}", "capture", "lifttrace"),
    ) as process:
        handle, _rectangle = wait_for_ready(process, stage, CAPTURE_TIMEOUT)
        tap_key(process, handle, VK_E, 2.0)
        records, pages = wait_for_trace(process, stage, -750)
        exit_cleanly(process, handle)
    return records, pages


def run_descent() -> tuple[list[LiftRecord], list[bytes]]:
    stage, executable = stage_run("descent", -750)
    with PrivateDesktopProcess(
        executable,
        stage,
        (f"clock={CLOCK_SECONDS}", "capture", "lifttrace"),
    ) as process:
        handle, _rectangle = wait_for_ready(process, stage, CAPTURE_TIMEOUT)
        records, pages = wait_for_trace(process, stage, 0)
        exit_cleanly(process, handle)
    return records, pages


def main() -> int:
    if sys.platform != "win32":
        print("lift runtime: skipped (requires Windows private desktop)")
        return 0
    if not EXECUTABLE.is_file():
        print(f"lift runtime: missing {EXECUTABLE}")
        return 1

    ascent, ascent_pages = run_ascent()
    descent, descent_pages = run_descent()

    expected_ascent = (
        (-100, -99, 0, 0, 0, -3100),
        (-199, -98, 0, 0, 0, -3100),
        (-297, -97, 0, 0, 0, -3100),
        (-394, -96, 0, 315, 0, -2813),
        (-490, -95, 0, 392, 0, -2528),
        (-585, -94, 1, 468, 0, -2245),
        (-679, -93, 1, 543, 0, -1964),
        (-750, 0, 1, 434, 0, -1437),
    )
    check(
        tuple(record[:6] for record in ascent) == expected_ascent,
        "live ascent retains all eight source y/lifter/roof/momentum/restraint states",
    )
    check(
        tuple(record[6:] for record in ascent) ==
        ((-4, 0), (-9, 0), (-14, 0), (-14, 0),
         (-14, 0), (-14, 0), (-14, 0), (-14, 0)),
        "live ascent retains the source-ordered camera pitch transition",
    )
    check(
        len(ascent_pages) == len(ascent)
        and all(len(page) == PAGE_BYTES for page in ascent_pages)
        and all(page_difference_count(left, right) > 0
                for left, right in zip(ascent_pages, ascent_pages[1:])),
        "every authoritative ascent state retains one complete distinct rendered page",
    )

    print("  INFO ascent records:")
    for index, record in enumerate(ascent):
        print(f"    {index}: {record} page={hashlib.sha256(ascent_pages[index]).hexdigest()[:16]}")
    print("  INFO descent records:")
    for index, record in enumerate(descent):
        print(f"    {index}: {record} page={hashlib.sha256(descent_pages[index]).hexdigest()[:16]}")

    expected_descent = (
        (-750, 75, 1, 0, 0, -3100, 0, 0),
        (-675, 74, 1, 29, 0, -3072, 4, 0),
        (-601, 73, 1, 28, 0, -3052, 7, 0),
        (-528, 72, 1, 28, 0, -3037, 10, 0),
        (-456, 71, 0, 28, 0, -3027, 13, 0),
        (-385, 70, 0, 28, 0, -3019, 15, 0),
        (-315, 69, 0, 27, 0, -3014, 17, 0),
        (-246, 68, 0, 27, 0, -3011, 19, 0),
        (-178, 67, 0, 26, 0, -3010, 21, 0),
        (-111, 66, 0, 26, 0, -3010, 23, 0),
        (-45, 65, 0, 25, 0, -3010, 18, 0),
        (0, 0, 0, 25, 0, -2979, 14, 0),
    )
    check(
        tuple(descent) == expected_descent,
        "automatic aperture return retains all twelve +75-to-deck source states",
    )
    check(
        len(descent_pages) == len(descent)
        and all(len(page) == PAGE_BYTES for page in descent_pages)
        and all(page_difference_count(left, right) > 0
                for left, right in zip(descent_pages, descent_pages[1:])),
        "every authoritative descent state retains one complete distinct rendered page",
    )

    ascent_transition = next(index for index, record in enumerate(ascent) if record[2])
    descent_transition = next(index for index, record in enumerate(descent) if not record[2])
    check(
        ascent_transition == 5
        and descent_transition > 0
        and crop_band_difference_count(
            ascent_pages[ascent_transition - 1],
            ascent_pages[ascent_transition],
            (10, 10, 310, 124),
        ) > 0
        and crop_band_difference_count(
            descent_pages[descent_transition - 1],
            descent_pages[descent_transition],
            (10, 10, 310, 124),
        ) > 0,
        "live pages cross the strict y < -500 cupola branch in both directions",
    )

    if FAILURES:
        print(f"lift runtime: {len(FAILURES)} failure(s)")
        return 1
    print("lift runtime: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
