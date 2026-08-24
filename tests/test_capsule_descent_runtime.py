#!/usr/bin/env python3
"""Exercise capsule descent through its authoritative surface settlement."""

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
CAPTURE_TIMEOUT = 420.0
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
    stage = STAGE_ROOT / "descent"
    executable = stage_scenario(stage, EXECUTABLE, scenario_checkpoint("orbital"))
    for filename in ("game-capsule-state-out.bin", "game-capsule-pages-out.bin"):
        path = stage / filename
        if path.exists():
            path.unlink()
    return stage, executable


def trace_status(stage: Path) -> tuple[int, CapsuleRecord] | None:
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
    with state_path.open("rb") as stream:
        stream.seek(-RECORD_BYTES, 2)
        final = struct.unpack("<16i", stream.read(RECORD_BYTES))
    return count, final


def read_trace(stage: Path) -> tuple[list[CapsuleRecord], list[bytes]]:
    state_path = stage / "game-capsule-state-out.bin"
    pages_path = stage / "game-capsule-pages-out.bin"
    state_data = state_path.read_bytes()
    page_data = pages_path.read_bytes()
    if not state_data or len(state_data) % RECORD_BYTES:
        raise RuntimeError(f"capsule state trace has invalid size {len(state_data)}")
    count = len(state_data) // RECORD_BYTES
    if len(page_data) != count * PAGE_BYTES:
        raise RuntimeError(
            f"capsule page trace has size {len(page_data)}, expected {count * PAGE_BYTES}"
        )
    records = [
        struct.unpack_from("<16i", state_data, index * RECORD_BYTES)
        for index in range(count)
    ]
    pages = [
        page_data[index * PAGE_BYTES:(index + 1) * PAGE_BYTES]
        for index in range(count)
    ]
    return records, pages


def request_landing(
    process: PrivateDesktopProcess,
    handle: int,
    stage: Path,
) -> None:
    # The reached-local checkpoint needs one L to open the source landing map
    # and a second L to confirm its default site. Retry only until tracing starts.
    for attempt in range(1, 6):
        process.post_char(handle, "l")
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(
                    f"game exited while requesting capsule descent with code {process.poll()}"
                )
            if trace_status(stage) is not None:
                print(f"  INFO capsule descent accepted after {attempt} L event(s)", flush=True)
                return
            time.sleep(0.05)
    raise TimeoutError("landing selector did not start the capsule trace")


def wait_for_trace(
    process: PrivateDesktopProcess,
    stage: Path,
    timeout: float = CAPTURE_TIMEOUT,
) -> tuple[list[CapsuleRecord], list[bytes]]:
    deadline = time.monotonic() + timeout
    next_progress = time.monotonic() + 10.0
    stable: tuple[int, int, int, int] | None = None
    while time.monotonic() < deadline:
        return_code = process.poll()
        if return_code is not None:
            raise RuntimeError(
                f"game exited while tracing capsule descent with code {return_code}"
            )
        status = trace_status(stage)
        now = time.monotonic()
        if status is None:
            stable = None
            time.sleep(0.05)
            continue
        count, final = status
        if now >= next_progress:
            print(
                "  INFO descent progress: "
                f"records={count} state={final[STATE]} y={final[Y]} "
                f"ground={final[GROUND]} gravity={final[GRAVITY]}",
                flush=True,
            )
            next_progress = now + 10.0
        if not (
            final[STATE] == 0
            and final[LANDED] == 1
            and final[MODE] == 1
            and final[GRAVITY] == 0
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
            return read_trace(stage)
        stable = signature
        time.sleep(0.10)
    raise TimeoutError(f"capsule trace did not settle on the surface within {timeout:.0f}s")


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


def signed_div(value: int, divisor: int) -> int:
    quotient = abs(value) // abs(divisor)
    return -quotient if (value < 0) != (divisor < 0) else quotient


def descent_step_matches(earlier: CapsuleRecord, later: CapsuleRecord) -> bool:
    tentative_y = earlier[Y] + signed_div(earlier[GRAVITY], 10)
    if tentative_y > earlier[GROUND]:
        return (
            later[Y] == earlier[GROUND]
            and later[GRAVITY] == -signed_div(earlier[GRAVITY] * 32, 100)
        )
    return (
        later[Y] == tentative_y
        and later[GRAVITY] == earlier[GRAVITY] + 65
    )


def page_difference_count(left: bytes, right: bytes) -> int:
    return sum(a != b for a, b in zip(left, right))


def page_band_difference_count(left: bytes, right: bytes) -> int:
    return sum((a & 0xC0) != (b & 0xC0) for a, b in zip(left, right))


def run_descent() -> tuple[list[CapsuleRecord], list[bytes]]:
    stage, executable = stage_run()
    with PrivateDesktopProcess(
        executable,
        stage,
        (f"clock={CLOCK_SECONDS}", "capture", "capsuletrace"),
    ) as process:
        handle, _rectangle = wait_for_ready(process, stage, CAPTURE_TIMEOUT)
        request_landing(process, handle, stage)
        records, pages = wait_for_trace(process, stage)
        exit_cleanly(process, handle)
    return records, pages


def main() -> int:
    if sys.platform != "win32":
        print("capsule descent runtime: skipped (requires Windows private desktop)")
        return 0
    if not EXECUTABLE.is_file():
        print(f"capsule descent runtime: missing {EXECUTABLE}")
        return 1

    records, pages = run_descent()
    active = records[:-1]
    settled = records[-1]

    check(
        len(records) == 601 and len(active) == 600,
        "trace retains exactly 600 source descent ticks and one settlement tick",
    )
    check(
        bool(active)
        and all(
            record[STATE] == 1
            and record[COUNT] == 0
            and record[RECOVER] == 0
            and record[LANDED] == 0
            and record[MODE] == 1
            and record[RETURN_PENDING] == 0
            for record in active
        ),
        "every airborne record retains authoritative capsule-descent state",
    )
    check(
        settled[STATE] == 0
        and settled[COUNT] == 0
        and settled[RECOVER] == 0
        and settled[LANDED] == 1
        and settled[MODE] == 1
        and settled[RETURN_PENDING] == 0
        and settled[GRAVITY] == 0
        and settled[Y] == settled[GROUND] - 600,
        "the final rendered tick atomically snaps to the landed walking pose",
    )
    check(
        bool(active)
        and active[0][GRAVITY] == 2081
        and active[0][Y] < active[0][GROUND] - 300000,
        "the selected source moon starts 320,000 units high with gravity 2016+65",
    )
    check(
        all(
            descent_step_matches(earlier, later)
            for earlier, later in zip(active, active[1:])
        ),
        "every airborne Y/gravity pair follows acceleration or 32-percent bounce",
    )

    impacts = [
        index
        for index, (earlier, later) in enumerate(zip(active, active[1:]), 1)
        if later[Y] == earlier[GROUND] and later[GRAVITY] < 0
    ]
    check(
        bool(impacts)
        and any(record[GRAVITY] < 0 for record in active)
        and any(record[GRAVITY] > 0 for record in active),
        "the complete trace retains impact, rebound, and renewed descent",
    )
    check(
        len({record[X] for record in active}) > 1
        and len({record[Z] for record in active}) > 1
        and len({record[GROUND] for record in active}) > 1
        and len({record[WIND_ANGLE] for record in active}) > 1
        and len({record[WIND_POWER] for record in active}) > 1,
        "atmospheric wind evolves the lateral pose and sampled terrain height",
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

    if len(pages) == len(records) and active and impacts:
        impact = impacts[0]
        high_difference = page_difference_count(pages[0], pages[max(1, impact - 1)])
        impact_difference = page_difference_count(pages[impact - 1], pages[impact])
        settle_difference = page_difference_count(pages[-2], pages[-1])
        settle_band_difference = page_band_difference_count(pages[-2], pages[-1])
        check(
            high_difference > 100 and impact_difference > 0,
            "indexed pages expose high descent and first-impact geometry changes",
        )
        check(
            settle_difference > 1000 and settle_band_difference > 100,
            "airborne-to-walking settlement substantially changes geometry and bands",
        )
        print(
            "  INFO transition differences: "
            f"high={high_difference} impact={impact_difference} "
            f"settle={settle_difference} settle-bands={settle_band_difference}",
        )
        sample_indices = sorted({0, impact - 1, impact, len(records) - 2, len(records) - 1})
        for index in sample_indices:
            print(
                f"  INFO record {index}: {records[index]} "
                f"page={hashlib.sha256(pages[index]).hexdigest()[:16]}"
            )
    else:
        check(False, "indexed pages expose high descent and first-impact geometry changes")
        check(False, "airborne-to-walking settlement substantially changes geometry")

    if FAILURES:
        print(f"capsule descent runtime: {len(FAILURES)} failure(s)")
        return 1
    print("capsule descent runtime: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
