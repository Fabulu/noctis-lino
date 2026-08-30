#!/usr/bin/env python3
"""Exercise native direct label editing on an inactive Windows desktop."""

from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
import struct
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from profile_noctis_desktop import (  # noqa: E402
    CLOCK_SECONDS,
    VK_ESCAPE,
    VK_R,
    finish_game_shutdown,
    scenario_checkpoint,
    stage_scenario,
    tap_key,
    wait_for_ready,
)
from windows_hidden_process import PrivateDesktopProcess  # noqa: E402


STAGE_ROOT = ROOT / "build" / "label-editing-runtime"
EXECUTABLE = ROOT / "work" / "vhgame.exe"
STARMAP_HEADER_BYTES = 4
STARMAP_RECORD_BYTES = 32
UPPER_LABEL_CROP = (27, 19, 294, 56)
CAPTURE_TIMEOUT = 90.0
FAILURES: list[str] = []
LabelState = tuple[int, int, int, int, int, int, int, int]
DIAGNOSTICS = (
    "game-vh-out.bin",
    "game-sun-out.bin",
    "game-local-out.bin",
    "game-page-out.bin",
    "game-palette-out.bin",
    "game-s-background-out.bin",
    "game-p-surfacemap-out.bin",
    "game-p-background-out.bin",
    "game-label-state-out.bin",
    "game-render-state-out.bin",
)


def check(condition: bool, label: str) -> None:
    if condition:
        print(f"  PASS {label}")
        return
    FAILURES.append(label)
    print(f"  FAIL {label}")


def stage_run(name: str, starmap: bytes) -> tuple[Path, Path]:
    stage = STAGE_ROOT / name
    staged_executable = stage_scenario(
        stage, EXECUTABLE, scenario_checkpoint("stardrifter")
    )
    (stage / "STARMAP.BIN").write_bytes(starmap)
    for filename in DIAGNOSTICS:
        path = stage / filename
        if path.exists():
            path.unlink()
    return stage, staged_executable


def wait_for_capture(
    process: PrivateDesktopProcess,
    stage: Path,
    previous_mtime_ns: int = -1,
    timeout: float = CAPTURE_TIMEOUT,
) -> tuple[int, bytes]:
    """Wait until the final sentinel marker and its 64,000-byte page are stable."""
    marker = stage / "game-render-state-out.bin"
    page_path = stage / "game-page-out.bin"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        return_code = process.poll()
        if return_code is not None:
            raise RuntimeError(
                f"game exited while waiting for a diagnostic capture with code {return_code}"
            )
        try:
            marker_before = marker.stat()
            page_before = page_path.stat()
        except FileNotFoundError:
            time.sleep(0.05)
            continue
        if (
            marker_before.st_mtime_ns <= previous_mtime_ns
            or marker_before.st_size != 24
            or page_before.st_size != 64000
            or page_before.st_mtime_ns > marker_before.st_mtime_ns
        ):
            time.sleep(0.05)
            continue
        marker_data = marker.read_bytes()
        page = page_path.read_bytes()
        try:
            marker_after = marker.stat()
            page_after = page_path.stat()
        except FileNotFoundError:
            time.sleep(0.05)
            continue
        if (
            len(marker_data) == 24
            and len(page) == 64000
            and marker_after.st_mtime_ns == marker_before.st_mtime_ns
            and marker_after.st_size == marker_before.st_size
            and page_after.st_mtime_ns == page_before.st_mtime_ns
            and page_after.st_size == page_before.st_size
        ):
            return marker_after.st_mtime_ns, page
        time.sleep(0.05)
    raise TimeoutError(
        f"game did not complete a newer render-state/page sentinel within {timeout:.0f}s"
    )


def read_label_state(stage: Path) -> LabelState:
    data = (stage / "game-label-state-out.bin").read_bytes()
    if len(data) != 32:
        raise RuntimeError(f"malformed 32-byte label state diagnostic: {len(data)} bytes")
    return struct.unpack("<8i", data)


def wait_for_starmap(
    process: PrivateDesktopProcess,
    path: Path,
    predicate,
    description: str,
    timeout: float = 10.0,
) -> bytes:
    deadline = time.monotonic() + timeout
    last = b""
    while time.monotonic() < deadline:
        return_code = process.poll()
        if return_code is not None:
            raise RuntimeError(
                f"game exited while waiting for {description} with code {return_code}"
            )
        if path.is_file():
            last = path.read_bytes()
            if predicate(last):
                return last
        time.sleep(0.05)
    raise TimeoutError(
        f"timed out waiting for {description}; last STARMAP size was {len(last)} bytes"
    )


def post_char(process: PrivateDesktopProcess, handle: int, value: str | int) -> None:
    process.post_char(handle, value)
    # Interior rendering can be slower than the 18.206-Hz simulation cadence.
    # Keep one character owned until at least one complete heavy frame can consume it.
    time.sleep(2.0)


def open_star_action(process: PrivateDesktopProcess, handle: int) -> None:
    tap_key(process, handle, VK_R, 0.20)
    time.sleep(0.20)
    post_char(process, handle, "8")
    post_char(process, handle, "6")


def open_body_action(process: PrivateDesktopProcess, handle: int) -> None:
    tap_key(process, handle, VK_R, 0.20)
    time.sleep(0.20)
    post_char(process, handle, "8")
    post_char(process, handle, "7")


def page_differences(first: bytes, second: bytes) -> list[tuple[int, int]]:
    if len(first) != 64000 or len(second) != 64000:
        raise ValueError("page comparisons require two complete 64,000-byte pages")
    return [
        (offset % 320, offset // 320)
        for offset, (left, right) in enumerate(zip(first, second))
        if left != right
    ]


def difference_bounds(points: list[tuple[int, int]]) -> tuple[int, int, int, int] | None:
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def point_in_bounds(point: tuple[int, int], bounds: tuple[int, int, int, int]) -> bool:
    x, y = point
    x0, y0, x1, y1 = bounds
    return x0 <= x <= x1 and y0 <= y <= y1


def exercise_assignment_and_removal() -> bytes:
    stage, staged_executable = stage_run(
        "player-local", struct.pack("<I", STARMAP_HEADER_BYTES)
    )
    starmap_path = stage / "STARMAP.BIN"
    with PrivateDesktopProcess(
        staged_executable,
        stage,
        (f"clock={CLOCK_SECONDS}", "capture", "freeze", "profile"),
    ) as process:
        handle, _rectangle = wait_for_ready(process, stage, CAPTURE_TIMEOUT)
        capture_mtime, _opening_page = wait_for_capture(process, stage)

        open_star_action(process, handle)
        for value in ("a", "b", "c", "z", 8, "d", "e"):
            post_char(process, handle, value)
        before_edit_capture = (stage / "game-render-state-out.bin").stat().st_mtime_ns
        capture_mtime, editing_page = wait_for_capture(
            process, stage, max(capture_mtime, before_edit_capture)
        )
        editing_label_state = read_label_state(stage)
        phase_samples = [(editing_page, editing_label_state)]
        for _phase in range(4):
            capture_mtime, page = wait_for_capture(process, stage, capture_mtime)
            phase_samples.append((page, read_label_state(stage)))

        distinct_page, _distinct_label_state, blink_differences = max(
            (
                (page, state, page_differences(editing_page, page))
                for page, state in phase_samples[1:4]
            ),
            key=lambda sample: len(sample[2]),
        )
        recurrence_page, recurrence_label_state = phase_samples[4]

        before_cursor_move = (stage / "game-render-state-out.bin").stat().st_mtime_ns
        post_char(process, handle, " ")
        moved_samples: list[tuple[bytes, LabelState]] = []
        for _phase in range(4):
            capture_mtime, page = wait_for_capture(
                process, stage, max(capture_mtime, before_cursor_move)
            )
            state = read_label_state(stage)
            moved_samples.append((page, state))
            before_cursor_move = capture_mtime
        matching_moved_sample = next(
            (
                (page, state)
                for page, state in moved_samples
                if state[:4] == (1, 0, 6, 0)
                and state[4] % 32 == editing_label_state[4] % 32
            ),
            None,
        )
        if matching_moved_sample is None:
            moved_cursor_page, moved_cursor_label_state = moved_samples[-1]
        else:
            moved_cursor_page, moved_cursor_label_state = matching_moved_sample
        post_char(process, handle, 8)

        post_char(process, handle, 13)
        assigned = wait_for_starmap(
            process,
            starmap_path,
            lambda data: len(data) == STARMAP_HEADER_BYTES + STARMAP_RECORD_BYTES,
            "one appended 32-byte player-local label record",
        )
        _post_mtime, committed_page = wait_for_capture(process, stage, capture_mtime)

        check(len(assigned) == 36, "Return appends exactly one 32-byte STARMAP record")
        boundary = struct.unpack_from("<I", assigned)[0]
        identity, name, suffix = struct.unpack_from("<d20s4s", assigned, 4)
        check(
            boundary == STARMAP_HEADER_BYTES and math.isfinite(identity),
            "the player-local record retains a finite target identity after the 4-byte boundary",
        )
        expected_name = b"ABCDE" + b" " * 15
        if name != expected_name:
            print(f"  INFO committed name bytes: {name!r}; expected {expected_name!r}")
        check(
            name == expected_name,
            "lowercase input, Backspace, and additional text commit as uppercase padded name bytes",
        )
        check(
            suffix[:2] == b" S"
            and suffix[2:3].isdigit()
            and suffix[3:4].isdigit(),
            "the record carries the native space/star/two-digit suffix",
        )

        blink_bounds = difference_bounds(blink_differences)
        recurrence_differences = page_differences(editing_page, recurrence_page)
        movement_differences = page_differences(editing_page, moved_cursor_page)
        movement_bounds = difference_bounds(movement_differences)
        old_cursor_points = (
            {
                point
                for point in movement_differences
                if point_in_bounds(point, blink_bounds)
            }
            if blink_bounds is not None
            else set()
        )
        new_cursor_points = set(movement_differences) - old_cursor_points
        translated_cursor_points = {
            (x + 11, y) for x, y in old_cursor_points
        }
        phase_states = [state for _page, state in phase_samples]

        editing_page_sha256 = hashlib.sha256(editing_page).hexdigest()
        distinct_page_sha256 = hashlib.sha256(distinct_page).hexdigest()
        recurrence_page_sha256 = hashlib.sha256(recurrence_page).hexdigest()
        moved_cursor_page_sha256 = hashlib.sha256(moved_cursor_page).hexdigest()
        committed_page_sha256 = hashlib.sha256(committed_page).hexdigest()
        print(
            "  INFO editing page SHA-256: "
            f"{editing_page_sha256}\n"
            "  INFO distinct blink-phase page SHA-256: "
            f"{distinct_page_sha256}\n"
            "  INFO same-phase recurrence page SHA-256: "
            f"{recurrence_page_sha256}\n"
            "  INFO same-phase moved-cursor page SHA-256: "
            f"{moved_cursor_page_sha256}\n"
            "  INFO committed page SHA-256: "
            f"{committed_page_sha256}\n"
            "  INFO complete-page cursor blink difference: "
            f"{len(blink_differences)} pixels, bounds {blink_bounds}\n"
            "  INFO complete-page same-phase recurrence difference: "
            f"{len(recurrence_differences)} pixels\n"
            "  INFO complete-page same-phase cursor movement difference: "
            f"{len(movement_differences)} pixels, bounds {movement_bounds}"
        )
        check(
            all(state[:4] == (1, 0, 5, 0) for state in phase_states)
            and all(
                state[5] == 127 - 2 * (state[4] % 32)
                for state in phase_states
            )
            and all(
                current[4] == previous[4] + 8
                for previous, current in zip(phase_states, phase_states[1:])
            ),
            "five frozen captures retain editor ownership and exact native blink phases",
        )
        check(
            recurrence_label_state[4] == editing_label_state[4] + 32
            and not recurrence_differences,
            "a complete modulo-32 cursor cycle reproduces all 64,000 indexed pixels byte-for-byte",
        )
        check(
            1 <= len(blink_differences) <= 256
            and blink_bounds is not None
            and blink_bounds[2] - blink_bounds[0] < 12
            and blink_bounds[3] - blink_bounds[1] < 6
            and UPPER_LABEL_CROP[0] <= blink_bounds[0] <= blink_bounds[2] < UPPER_LABEL_CROP[2]
            and UPPER_LABEL_CROP[1] <= blink_bounds[1] <= blink_bounds[3] <= UPPER_LABEL_CROP[1] + 20,
            "a distinct phase changes only the small underscore raster across the complete indexed page",
        )
        check(
            matching_moved_sample is not None
            and moved_cursor_label_state[:4] == (1, 0, 6, 0)
            and moved_cursor_label_state[4] % 32 == editing_label_state[4] % 32
            and moved_cursor_label_state[5]
            == 127 - 2 * (moved_cursor_label_state[4] % 32),
            "cursor movement is compared at the same native blink phase with editor ownership intact",
        )
        check(
            bool(old_cursor_points)
            and new_cursor_points == translated_cursor_points
            and len(movement_differences) == 2 * len(old_cursor_points),
            "an invisible trailing space translates only the cursor raster by one fixed HUD position",
        )

        post_char(process, handle, "6")
        removed = wait_for_starmap(
            process,
            starmap_path,
            lambda data: len(data) == 36 and data[4:12] == b"Removed:",
            "player-local identity tombstone",
        )
        check(
            removed[:4] == assigned[:4]
            and removed[4:12] == b"Removed:"
            and removed[12:] == assigned[12:],
            "player-local removal replaces only the eight identity bytes with Removed:",
        )
        finish_game_shutdown(process, stage)
    return assigned[4:]


def exercise_body_assignment_and_removal() -> None:
    stage, staged_executable = stage_run(
        "player-local-body", struct.pack("<I", STARMAP_HEADER_BYTES)
    )
    starmap_path = stage / "STARMAP.BIN"
    with PrivateDesktopProcess(
        staged_executable,
        stage,
        (f"clock={CLOCK_SECONDS}", "capture", "freeze", "profile"),
    ) as process:
        handle, _rectangle = wait_for_ready(process, stage, CAPTURE_TIMEOUT)
        wait_for_capture(process, stage)

        open_body_action(process, handle)
        for value in "planet":
            post_char(process, handle, value)
        post_char(process, handle, 13)
        assigned = wait_for_starmap(
            process,
            starmap_path,
            lambda data: len(data) == STARMAP_HEADER_BYTES + STARMAP_RECORD_BYTES,
            "one appended body-label record",
        )
        boundary = struct.unpack_from("<I", assigned)[0]
        identity, name, suffix = struct.unpack_from("<d20s4s", assigned, 4)
        check(
            boundary == STARMAP_HEADER_BYTES and math.isfinite(identity),
            "the body editor retains a finite player-local target identity",
        )
        check(
            name == b"PLANET" + b" " * 14
            and suffix[:2] == b" P"
            and suffix[2:3].isdigit()
            and suffix[3:4].isdigit(),
            "lowercase body input commits as an uppercase padded Pnn record",
        )

        post_char(process, handle, "7")
        removed = wait_for_starmap(
            process,
            starmap_path,
            lambda data: len(data) == 36 and data[4:12] == b"Removed:",
            "player-local body identity tombstone",
        )
        check(
            removed[:4] == assigned[:4]
            and removed[4:12] == b"Removed:"
            and removed[12:] == assigned[12:],
            "player-local body removal replaces only the eight identity bytes",
        )
        finish_game_shutdown(process, stage)


def exercise_cancel_and_cap() -> None:
    initial_starmap = struct.pack("<I", STARMAP_HEADER_BYTES)
    stage, staged_executable = stage_run("cancel-and-cap", initial_starmap)
    starmap_path = stage / "STARMAP.BIN"
    with PrivateDesktopProcess(
        staged_executable,
        stage,
        (f"clock={CLOCK_SECONDS}", "capture", "freeze", "profile"),
    ) as process:
        handle, _rectangle = wait_for_ready(process, stage, CAPTURE_TIMEOUT)
        capture_mtime, _opening_page = wait_for_capture(process, stage)

        open_star_action(process, handle)
        for value in "cancel":
            post_char(process, handle, value)
        active_mtime = capture_mtime
        active_label_state = read_label_state(stage)
        for _capture in range(3):
            active_mtime, _active_page = wait_for_capture(
                process, stage, active_mtime
            )
            active_label_state = read_label_state(stage)
            if active_label_state[:4] == (1, 0, 6, 0):
                break
        if not (
            active_label_state[:4] == (1, 0, 6, 0)
            and active_label_state[6] == 0
            and active_label_state[7] == 0
        ):
            print(f"  INFO pre-Escape label state: {active_label_state!r}")
        check(
            active_label_state[:4] == (1, 0, 6, 0)
            and active_label_state[6] == 0
            and active_label_state[7] == 0,
            "the star editor is active at position six before physical Escape",
        )

        latest_held_mtime = active_mtime
        cancelled_label_state: LabelState | None = None
        process.post_key(handle, VK_ESCAPE, True)
        try:
            for _capture in range(2):
                latest_held_mtime, _held_page = wait_for_capture(
                    process, stage, latest_held_mtime
                )
                state = read_label_state(stage)
                if state[:2] == (0, 0):
                    cancelled_label_state = state
                    break
            check(
                process.poll() is None
                and cancelled_label_state is not None
                and cancelled_label_state[7] == 1
                and starmap_path.read_bytes() == initial_starmap,
                "held physical Escape cancels the active editor without mutating STARMAP or exiting",
            )
            latest_held_mtime, _latched_page = wait_for_capture(
                process, stage, latest_held_mtime
            )
            latched_label_state = read_label_state(stage)
            check(
                process.poll() is None
                and latched_label_state[:2] == (0, 0)
                and latched_label_state[7] == 1
                and starmap_path.read_bytes() == initial_starmap,
                "held Escape remains owned after cancellation instead of falling through to quit",
            )
        finally:
            if process.poll() is None:
                process.post_key(handle, VK_ESCAPE, False)

        _released_mtime, _released_page = wait_for_capture(
            process, stage, latest_held_mtime
        )
        released_label_state = read_label_state(stage)
        check(
            process.poll() is None
            and released_label_state[:2] == (0, 0)
            and released_label_state[7] == 0
            and starmap_path.read_bytes() == initial_starmap,
            "released physical Escape clears its observed latch and leaves the game running",
        )

        post_char(process, handle, "6")
        for value in "abcdefghijklmnopqrstu":
            post_char(process, handle, value)
        post_char(process, handle, 13)
        assigned = wait_for_starmap(
            process,
            starmap_path,
            lambda data: len(data) == STARMAP_HEADER_BYTES + STARMAP_RECORD_BYTES,
            "one capped star-label record",
        )
        _identity, name, suffix = struct.unpack_from("<d20s4s", assigned, 4)
        check(
            name == b"ABCDEFGHIJKLMNOPQRST" and suffix[:2] == b" S",
            "the direct editor consumes but does not store characters beyond its 20-byte cap",
        )
        finish_game_shutdown(process, stage)


def exercise_case_insensitive_duplicate(record: bytes) -> None:
    lowercase_record = (
        record[:8] + b"abcde" + b" " * 15 + record[28:]
    )
    seeded_starmap = struct.pack("<I", STARMAP_HEADER_BYTES) + lowercase_record
    stage, staged_executable = stage_run("case-insensitive-duplicate", seeded_starmap)
    starmap_path = stage / "STARMAP.BIN"
    with PrivateDesktopProcess(
        staged_executable,
        stage,
        (f"clock={CLOCK_SECONDS}", "capture", "freeze", "profile"),
    ) as process:
        handle, _rectangle = wait_for_ready(process, stage, CAPTURE_TIMEOUT)
        capture_mtime, _opening_page = wait_for_capture(process, stage)

        open_body_action(process, handle)
        for value in "ABCDE":
            post_char(process, handle, value)
        editing_mtime = capture_mtime
        editing_label_state = read_label_state(stage)
        for _capture in range(3):
            editing_mtime, _editing_page = wait_for_capture(
                process, stage, editing_mtime
            )
            editing_label_state = read_label_state(stage)
            if editing_label_state[:4] == (0, 1, 0, 5):
                break
        if not (
            editing_label_state[:4] == (0, 1, 0, 5)
            and editing_label_state[6] == 0
        ):
            print(f"  INFO pre-duplicate label state: {editing_label_state!r}")
        check(
            editing_label_state[:4] == (0, 1, 0, 5)
            and editing_label_state[6] == 0,
            "the body editor owns all five characters before duplicate-name Return",
        )
        post_char(process, handle, 13)
        _result_mtime, _result_page = wait_for_capture(
            process, stage, editing_mtime
        )
        result_label_state = read_label_state(stage)
        check(
            process.poll() is None
            and result_label_state[:2] == (0, 0)
            and result_label_state[6] == 2
            and starmap_path.read_bytes() == seeded_starmap,
            "a case-insensitive duplicate reaches native EXTANT and leaves STARMAP unchanged",
        )
        finish_game_shutdown(process, stage)


def exercise_consolidated_denial(record: bytes) -> None:
    protected_starmap = struct.pack("<I", 36) + record
    stage, staged_executable = stage_run("consolidated", protected_starmap)
    starmap_path = stage / "STARMAP.BIN"
    with PrivateDesktopProcess(
        staged_executable,
        stage,
        (f"clock={CLOCK_SECONDS}", "capture", "freeze", "profile"),
    ) as process:
        handle, _rectangle = wait_for_ready(process, stage, CAPTURE_TIMEOUT)
        capture_mtime, _page = wait_for_capture(process, stage)
        check(
            starmap_path.read_bytes() == protected_starmap,
            "the consolidated seed loads unchanged before removal",
        )
        open_star_action(process, handle)
        _capture_mtime, _page = wait_for_capture(process, stage, capture_mtime)
        denied_label_state = read_label_state(stage)
        check(
            process.poll() is None
            and denied_label_state[:2] == (0, 0)
            and denied_label_state[6] == 4
            and starmap_path.read_bytes() == protected_starmap,
            "consolidated-label removal reaches native DENIED and leaves every STARMAP byte unchanged",
        )
        finish_game_shutdown(process, stage)


def main() -> int:
    if os.name != "nt":
        print("SKIP label editing runtime requires Windows")
        return 0
    if not EXECUTABLE.is_file():
        raise FileNotFoundError(f"missing compiled game: {EXECUTABLE}")

    record = exercise_assignment_and_removal()
    exercise_body_assignment_and_removal()
    exercise_cancel_and_cap()
    exercise_case_insensitive_duplicate(record)
    exercise_consolidated_denial(record)
    if FAILURES:
        print("RESULT FAIL - " + "; ".join(FAILURES))
        return 1
    print("RESULT PASS - native label editing runtime")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
