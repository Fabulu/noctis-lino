#!/usr/bin/env python3
"""Exercise Stardrifter control ownership on an inactive Windows desktop."""

from __future__ import annotations

import os
from pathlib import Path
import struct
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from noctis_control_trace import (  # noqa: E402
    ControlState,
    TRACE_BYTES,
    TRACE_NAME,
    decode_trace,
)
from profile_noctis_desktop import (  # noqa: E402
    CLOCK_SECONDS,
    decode_profile,
    scenario_checkpoint,
    stage_scenario,
    wait_for_ready,
)
from windows_hidden_process import PrivateDesktopProcess  # noqa: E402


STAGE = ROOT / "build" / "controls-runtime"
EXECUTABLE = ROOT / "work" / "vhgame.exe"
TIMEOUT = 90.0
VK_CONTROL = 0x11
VK_ESCAPE = 0x1B
VK_DOWN = 0x28
VK_D = 0x44
VK_S = 0x53
FAILURES: list[str] = []


def check(condition: bool, label: str) -> None:
    if condition:
        print(f"  PASS {label}")
        return
    FAILURES.append(label)
    print(f"  FAIL {label}")


def v18_stardrifter_checkpoint() -> bytes:
    """Upgrade the deterministic space fixture without changing its world state."""
    checkpoint = bytearray(scenario_checkpoint("stardrifter"))
    checkpoint.extend(b"\0" * 4)
    struct.pack_into("<i", checkpoint, 1 * 4, 18)
    # Menus always on, roofspeed off, normal hosted mouselook.
    struct.pack_into("<i", checkpoint, 64 * 4, 36)
    # Complete stopped-drive, inactive-reset, fully-lit v18 state.
    struct.pack_into("<i", checkpoint, 66 * 4, 4227135)
    if len(checkpoint) != 268:
        raise AssertionError(f"v18 fixture is {len(checkpoint)} bytes, expected 268")
    return bytes(checkpoint)


def wait_for_records(
    process: PrivateDesktopProcess,
    path: Path,
    after: int,
    predicate,
    description: str,
    timeout: float = TIMEOUT,
    *,
    allow_exit: bool = False,
) -> tuple[ControlState, list[ControlState]]:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    last_records: list[ControlState] = []
    while time.monotonic() < deadline:
        return_code = process.poll()
        if return_code not in (None, 0):
            raise RuntimeError(
                f"game host exited while waiting for {description} with code {return_code}"
            )
        if path.is_file():
            try:
                last_records = decode_trace(path)
                new_records = [
                    record for record in last_records if record["sequence"] > after
                ]
                match = next((record for record in new_records if predicate(record)), None)
                if match is not None:
                    return match, new_records
            except (OSError, ValueError) as error:
                last_error = error
        if return_code == 0 and allow_exit:
            break
        time.sleep(0.03)
    suffix = f"; last trace error: {last_error}" if last_error else ""
    raise TimeoutError(
        f"timed out waiting for {description} after sequence {after}; "
        f"saw {len(last_records)} records{suffix}"
    )


def latest_record(process: PrivateDesktopProcess, path: Path, after: int = 0) -> ControlState:
    record, _records = wait_for_records(
        process, path, after, lambda _record: True, "a complete control record"
    )
    return record


def release_and_settle(
    process: PrivateDesktopProcess, handle: int, path: Path, key: int, after: int
) -> ControlState:
    process.post_key(handle, key, False)
    return latest_record(process, path, after)


def wait_for_application_shutdown(
    process: PrivateDesktopProcess, stage: Path, timeout: float = 10.0
) -> None:
    """Accept a quit already requested by the control sequence."""
    profile_path = stage / "game-profile-out.bin"
    checkpoint_paths = (stage / "CURRENT.LIN", stage / "CURRENT.BAK")
    deadline = time.monotonic() + timeout
    stable_signature: tuple[int, ...] | None = None
    stable_count = 0
    while time.monotonic() < deadline:
        return_code = process.poll()
        if return_code not in (None, 0):
            raise RuntimeError(f"game host exited with code {return_code}")
        try:
            profile_state = profile_path.stat()
            checkpoint_states = tuple(path.stat() for path in checkpoint_paths)
        except FileNotFoundError:
            stable_signature = None
            stable_count = 0
            time.sleep(0.05)
            continue
        if (
            profile_state.st_size != 128
            or any(state.st_size != 268 for state in checkpoint_states)
            or process.main_window_handle() is not None
        ):
            stable_signature = None
            stable_count = 0
            time.sleep(0.05)
            continue
        profile_data = profile_path.read_bytes()
        checkpoints = tuple(path.read_bytes() for path in checkpoint_paths)
        signature = (
            profile_state.st_size,
            profile_state.st_mtime_ns,
            *(value for state in checkpoint_states
              for value in (state.st_size, state.st_mtime_ns)),
        )
        if (
            len(profile_data) == 128
            and checkpoints[0] == checkpoints[1]
            and signature == stable_signature
        ):
            stable_count += 1
        else:
            stable_signature = signature
            stable_count = 1
        if stable_count >= 3:
            decode_profile(profile_data)
            return
        time.sleep(0.10)
    raise TimeoutError(
        "game did not complete terminal profile, checkpoint save, and window teardown"
    )


def main() -> int:
    if os.name != "nt":
        print("SKIP Stardrifter controls runtime requires Windows")
        return 0
    if not EXECUTABLE.is_file():
        raise FileNotFoundError(f"missing compiled game: {EXECUTABLE}")

    staged_executable = stage_scenario(
        STAGE, EXECUTABLE, v18_stardrifter_checkpoint()
    )
    trace_path = STAGE / TRACE_NAME
    if trace_path.exists():
        trace_path.unlink()

    with PrivateDesktopProcess(
        staged_executable,
        STAGE,
        (f"clock={CLOCK_SECONDS}", "controltrace", "profile"),
    ) as process:
        handle, _rectangle = wait_for_ready(process, STAGE, TIMEOUT)
        opening = latest_record(process, trace_path)
        check(
            opening["mode"] == 0
            and opening["roofspeed"] == 0
            and opening["mouselook"] == 1
            and opening["preferences"] == 0
            and opening["fast_presentation"] == 1
            and opening["star_drive"] == 0
            and opening["star_reached"] == 1
            and opening["quit"] == 0,
            "a deterministic v18 Stardrifter fixture starts with normal controls and 60-Hz presentation",
        )

        process.post_key(handle, VK_S, True)
        moved, _ = wait_for_records(
            process,
            trace_path,
            opening["sequence"],
            lambda record: (record["x"], record["z"]) != (opening["x"], opening["z"]),
            "unmodified S movement",
        )
        after_s = release_and_settle(
            process, handle, trace_path, VK_S, moved["sequence"]
        )
        check(
            (moved["x"], moved["z"]) != (opening["x"], opening["z"])
            and moved["roofspeed"] == opening["roofspeed"],
            "unmodified S retains ordinary Stardrifter movement",
        )

        process.post_key(handle, VK_DOWN, True)
        pitched, _ = wait_for_records(
            process,
            trace_path,
            after_s["sequence"],
            lambda record: record["alpha"] != after_s["alpha"],
            "unmodified Down look",
        )
        after_down = release_and_settle(
            process, handle, trace_path, VK_DOWN, pitched["sequence"]
        )
        check(
            pitched["alpha"] != after_s["alpha"]
            and pitched["mouselook"] == after_s["mouselook"],
            "unmodified Down retains ordinary Stardrifter pitch",
        )

        roof_before = after_down
        process.post_key(handle, VK_CONTROL, True)
        process.post_key(handle, VK_S, True)
        roof_changed, _ = wait_for_records(
            process,
            trace_path,
            roof_before["sequence"],
            lambda record: record["roofspeed"] == 1,
            "Ctrl+S roofspeed edge",
        )
        time.sleep(1.0)
        roof_held = decode_trace(trace_path)
        roof_samples = [
            record
            for record in roof_held
            if record["sequence"] >= roof_changed["sequence"]
        ]
        check(
            len(roof_samples) >= 2
            and all(record["roofspeed"] == 1 for record in roof_samples)
            and all(
                (record["x"], record["z"]) == (roof_before["x"], roof_before["z"])
                for record in roof_samples
            ),
            "held Ctrl+S toggles roofspeed once and never leaks into movement",
        )
        process.post_key(handle, VK_S, False)
        process.post_key(handle, VK_CONTROL, False)
        after_roof = latest_record(process, trace_path, roof_samples[-1]["sequence"])

        mouse_before = after_roof
        process.post_key(handle, VK_CONTROL, True)
        process.post_key(handle, VK_DOWN, True)
        mouse_changed, _ = wait_for_records(
            process,
            trace_path,
            mouse_before["sequence"],
            lambda record: record["mouselook"] == 2,
            "Ctrl+Down mouselook edge",
        )
        time.sleep(1.0)
        mouse_held = decode_trace(trace_path)
        mouse_samples = [
            record
            for record in mouse_held
            if record["sequence"] >= mouse_changed["sequence"]
        ]
        check(
            len(mouse_samples) >= 2
            and all(record["mouselook"] == 2 for record in mouse_samples)
            and all(record["alpha"] == mouse_before["alpha"] for record in mouse_samples),
            "held Ctrl+Down advances one mouselook mode and never leaks into pitch",
        )
        process.post_key(handle, VK_DOWN, False)
        process.post_key(handle, VK_CONTROL, False)
        after_mouse = latest_record(process, trace_path, mouse_samples[-1]["sequence"])

        prefs_before = after_mouse
        process.post_key(handle, VK_CONTROL, True)
        process.post_key(handle, VK_D, True)
        prefs_open, _ = wait_for_records(
            process,
            trace_path,
            prefs_before["sequence"],
            lambda record: record["preferences"] == 1,
            "Ctrl+D Preferences opener",
        )
        time.sleep(1.0)
        prefs_held = decode_trace(trace_path)
        prefs_samples = [
            record
            for record in prefs_held
            if record["sequence"] >= prefs_open["sequence"]
        ]
        check(
            len(prefs_samples) >= 2
            and all(record["preferences"] == 1 for record in prefs_samples)
            and all(
                (record["x"], record["z"]) == (prefs_before["x"], prefs_before["z"])
                for record in prefs_samples
            ),
            "held Ctrl+D opens Preferences once and never leaks into strafe",
        )
        process.post_key(handle, VK_D, False)
        process.post_key(handle, VK_CONTROL, False)
        prefs_ready = latest_record(process, trace_path, prefs_samples[-1]["sequence"])

        process.post_key(handle, VK_ESCAPE, True)
        prefs_closed, _ = wait_for_records(
            process,
            trace_path,
            prefs_ready["sequence"],
            lambda record: record["preferences"] == 0
            and record["escape_held"] == 1,
            "modal Escape close",
        )
        time.sleep(1.0)
        escape_held = decode_trace(trace_path)
        held_samples = [
            record
            for record in escape_held
            if record["sequence"] >= prefs_closed["sequence"]
        ]
        check(
            len(held_samples) >= 2
            and all(record["preferences"] == 0 for record in held_samples)
            and all(record["escape_held"] == 1 for record in held_samples)
            and all(record["quit"] == 0 for record in held_samples),
            "held Escape closes only Preferences and cannot become delayed quit",
        )

        process.post_key(handle, VK_ESCAPE, False)
        released, _ = wait_for_records(
            process,
            trace_path,
            held_samples[-1]["sequence"],
            lambda record: record["escape_held"] == 0 and record["quit"] == 0,
            "Escape latch release",
        )
        check(
            released["preferences"] == 0 and process.poll() is None,
            "Escape release clears the gameplay latch while the game remains active",
        )

        process.post_key(handle, VK_ESCAPE, True)
        quitting, _ = wait_for_records(
            process,
            trace_path,
            released["sequence"],
            lambda record: record["quit"] == 1 and record["escape_held"] == 1,
            "fresh Escape quit edge",
            allow_exit=True,
        )
        if process.poll() is None:
            process.post_key(handle, VK_ESCAPE, False)
        check(
            quitting["preferences"] == 0,
            "a released-and-repressed Escape reaches ordinary quit exactly once",
        )
        wait_for_application_shutdown(process, STAGE)

    if FAILURES:
        print("RESULT FAIL - " + "; ".join(FAILURES))
        return 1
    print("RESULT PASS - compiled Stardrifter control ownership")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
