#!/usr/bin/env python3
"""Measure sustained Noctis rendering and input on a private Windows desktop."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from make_noctis_checkpoint import build_landed_checkpoint  # noqa: E402
from windows_hidden_process import (  # noqa: E402
    ABOVE_NORMAL_PRIORITY_CLASS,
    PrivateDesktopProcess,
    physical_core_affinity_masks,
)


CLOCK_SECONDS = 1344638527
PROFILE_MAGIC = 0x56504731
PROFILE_UNITS = 32
ASSETS = (
    "globes.map",
    "offsets.map",
    "vehicle.ncc",
    "mammal.ncc",
    "birdy.ncc",
    "digimap2.bin",
    "STARMAP.BIN",
    "GUIDE.BIN",
    "noctis_music.pcm",
)
VK_ESCAPE = 0x1B
VK_5 = 0x35
VK_R = 0x52
VK_W = 0x57

PROFILE_FIELDS = (
    "magic",
    "schema",
    "presentations",
    "simulation_ticks",
    "missed_deadlines",
    "maximum_lateness_counts",
    "total_lateness_counts",
    "render_counts",
    "present_counts",
    "space_counts",
    "cupola_counts",
    "hull_counts",
    "detail_counts",
    "wall_milliseconds",
    "counts_per_millisecond",
    "sleep_calls",
    "gui_loop_calls",
    "timing_calls",
    "current_fps",
    "mode",
    "landed",
    "capsule_state",
    "profiled_virtual_key",
    "profile_origin_counter",
    "input_detected_counter",
    "input_effect_counter",
    "input_presented_counter",
    "final_x",
    "final_z",
    "fcs_open",
    "fast_presentation",
    "trailing_magic",
)
SIGNED_FIELDS = {"mode", "landed", "capsule_state", "final_x", "final_z"}
CONTROLLED_SCHEDULING = "physical-core-above-normal"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def select_physical_core(core_masks: tuple[int, ...],
                         requested: str | int) -> tuple[int, int]:
    if not core_masks:
        raise ValueError("no physical processor cores are available")
    if requested == "last":
        index = len(core_masks) - 1
    else:
        try:
            index = int(requested)
        except (TypeError, ValueError) as error:
            raise ValueError("physical core must be 'last' or a nonnegative index") from error
        if index < 0:
            raise ValueError("physical core index must be nonnegative")
    if index >= len(core_masks):
        raise ValueError(
            f"physical core {index} is unavailable; valid range is "
            f"0..{len(core_masks) - 1}")
    return index, core_masks[index]


def make_scheduling_plan(control: str, physical_core: str | int,
                         core_masks: tuple[int, ...]
                         ) -> tuple[int | None, int | None, dict[str, object]]:
    topology = [f"0x{mask:x}" for mask in core_masks]
    if control == "uncontrolled":
        return None, None, {
            "policy": "uncontrolled",
            "comparable": False,
            "reason": "process affinity and priority were not controlled",
            "physical_core_masks": topology,
        }
    if control != "controlled":
        raise ValueError(f"unknown scheduling control {control!r}")
    index, affinity_mask = select_physical_core(core_masks, physical_core)
    return affinity_mask, ABOVE_NORMAL_PRIORITY_CLASS, {
        "policy": CONTROLLED_SCHEDULING,
        "comparable": True,
        "physical_core_index": index,
        "requested_affinity_mask": f"0x{affinity_mask:x}",
        "requested_priority_class": "above_normal",
        "physical_core_masks": topology,
    }


def counter_difference(end: int, start: int) -> int:
    """Return an elapsed low-32-bit performance-counter interval."""
    return (end - start) & 0xFFFFFFFF


def decode_profile(data: bytes) -> dict[str, int]:
    if len(data) != PROFILE_UNITS * 4:
        raise ValueError(f"profile is {len(data)} bytes, expected 128")
    unsigned = struct.unpack("<32I", data)
    signed = struct.unpack("<32i", data)
    profile = {
        name: (signed[index] if name in SIGNED_FIELDS else unsigned[index])
        for index, name in enumerate(PROFILE_FIELDS)
    }
    if profile["magic"] != PROFILE_MAGIC or profile["trailing_magic"] != PROFILE_MAGIC:
        raise ValueError("profile magic is incomplete or corrupt")
    if profile["schema"] != 1:
        raise ValueError(f"unsupported profile schema {profile['schema']}")
    if profile["counts_per_millisecond"] == 0:
        raise ValueError("profile has no performance-counter calibration")
    return profile


def _space_checkpoint(*, orbital: bool) -> bytes:
    checkpoint = bytearray(build_landed_checkpoint(
        star_x=1463568,
        star_y=-4728350,
        star_z=-437812,
        body=3,
        longitude=0,
        latitude=60,
        beta=23,
        pitch=0,
        player_x=2813,
        player_y=0,
        player_z=-1397,
        mode=0,
        fast=True,
    ))
    if orbital:
        local = (0.032783, 0.0, -0.077237)
        distance = math.sqrt(sum(component * component for component in local))
        struct.pack_into("<i", checkpoint, 39 * 4, 4)
        struct.pack_into("<ii", checkpoint, 48 * 4, 1, 3)
        struct.pack_into("<5d", checkpoint, 50 * 4, *local, distance, distance)
        struct.pack_into("<4i", checkpoint, 60 * 4, 0, 1, 0, 0)
    else:
        distance = 200.0
        beta = math.radians(23)
        galactic = (
            1463568 - (-math.sin(beta) * distance),
            -4728350.0,
            -437812 - (math.cos(beta) * distance),
        )
        struct.pack_into("<3d", checkpoint, 12 * 4, *galactic)
    return bytes(checkpoint)


def scenario_checkpoint(scenario: str) -> bytes:
    if scenario in {"stardrifter", "fcs"}:
        return _space_checkpoint(orbital=False)
    if scenario == "orbital":
        return _space_checkpoint(orbital=True)
    at_capsule = scenario == "capsule"
    return build_landed_checkpoint(
        star_x=1463568,
        star_y=-4728350,
        star_z=-437812,
        body=3,
        longitude=0,
        latitude=60,
        beta=65,
        pitch=-10,
        player_x=1638400 if at_capsule else 1598248,
        player_y=-600,
        player_z=1638400 if at_capsule else 2251369,
        capsule_x=1638400 if at_capsule else 131072,
        capsule_z=1638400 if at_capsule else 131072,
        fast=True,
    )


def stage_scenario(stage: Path, executable: Path, checkpoint: bytes) -> Path:
    stage.mkdir(parents=True, exist_ok=True)
    staged_executable = stage / "Noctis-IV.exe"
    shutil.copy2(executable, staged_executable)
    for name in ASSETS:
        source = ROOT / "work" / name
        if not source.is_file():
            raise FileNotFoundError(f"missing runtime asset: {source}")
        shutil.copy2(source, stage / name)
    (stage / "CURRENT.LIN").write_bytes(checkpoint)
    (stage / "CURRENT.BAK").write_bytes(checkpoint)
    for name in (
        "game-vh-out.bin",
        "game-sun-out.bin",
        "game-local-out.bin",
        "game-palette-out.bin",
        "game-page-out.bin",
        "game-profile-out.bin",
        "profile.bin",
        "report.json",
    ):
        path = stage / name
        if path.exists():
            path.unlink()
    return staged_executable


def wait_for_ready(process: PrivateDesktopProcess, stage: Path,
                   timeout: float) -> tuple[int, tuple[int, int, int, int]]:
    deadline = time.monotonic() + timeout
    sentinel = stage / "game-vh-out.bin"
    while time.monotonic() < deadline:
        return_code = process.poll()
        if return_code is not None:
            raise RuntimeError(f"game exited during initialization with code {return_code}")
        handle = process.main_window_handle()
        if handle is not None and sentinel.is_file() and sentinel.stat().st_size == 156:
            return handle, process.window_rectangle(handle)
        time.sleep(0.1)
    raise TimeoutError("game did not emit its first-frame sentinel")


def tap_key(process: PrivateDesktopProcess, handle: int, key: int,
            hold_seconds: float = 0.08) -> int:
    injected = process.performance_counter() & 0xFFFFFFFF
    process.post_key(handle, key, True)
    time.sleep(hold_seconds)
    if process.poll() is None:
        try:
            process.post_key(handle, key, False)
        except OSError:
            if key != VK_ESCAPE and process.poll() is None:
                raise
    return injected


def finish_game_shutdown(
        process: PrivateDesktopProcess, stage: Path, timeout: float = 10.0,
) -> bool:
    """Wait for application shutdown, without calling host linger a clean exit.

    The historical GUI host remains resident after the Lino programme has left
    iGUI.  A fresh terminal profile, both settled checkpoint copies, and removal
    of the private-desktop window prove that the application's quit/save path
    completed.  The context manager may then terminate the lingering host.  The
    return value records whether the host happened to exit naturally as well.
    """
    profile_path = stage / "game-profile-out.bin"
    checkpoint_paths = (stage / "CURRENT.LIN", stage / "CURRENT.BAK")
    if profile_path.exists():
        raise RuntimeError("terminal profile exists before shutdown request")
    checkpoint_mtimes = tuple(path.stat().st_mtime_ns for path in checkpoint_paths)
    deadline = time.monotonic() + timeout
    next_escape = 0.0
    stable_signature: tuple[int, ...] | None = None
    stable_count = 0

    while time.monotonic() < deadline:
        return_code = process.poll()
        if return_code not in (None, 0):
            raise RuntimeError(f"game host exited with code {return_code}")

        now = time.monotonic()
        if now >= next_escape and not profile_path.exists() and return_code is None:
            current_handle = process.main_window_handle()
            if current_handle is not None:
                tap_key(process, current_handle, VK_ESCAPE, 0.20)
            next_escape = now + 3.0

        try:
            profile_state = profile_path.stat()
            checkpoint_states = tuple(path.stat() for path in checkpoint_paths)
        except FileNotFoundError:
            stable_signature = None
            stable_count = 0
            time.sleep(0.05)
            continue

        if (
            profile_state.st_size != PROFILE_UNITS * 4
            or any(state.st_size != 268 for state in checkpoint_states)
            or any(state.st_mtime_ns <= previous
                   for state, previous in zip(checkpoint_states, checkpoint_mtimes))
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
            len(profile_data) == PROFILE_UNITS * 4
            and checkpoints[0] == checkpoints[1]
            and signature == stable_signature
        ):
            stable_count += 1
        else:
            stable_signature = signature
            stable_count = 1
        if stable_count >= 3:
            decode_profile(profile_data)
            return process.poll() == 0
        time.sleep(0.10)

    raise TimeoutError(
        "game did not complete terminal profile, checkpoint save, and window teardown"
    )


def derived_metrics(profile: dict[str, int], _injected_counter: int | None,
                    process_cycles: int | None = None
                    ) -> dict[str, float | int | bool | None]:
    counts_per_ms = profile["counts_per_millisecond"]
    presentations = profile["presentations"]
    wall_ms = profile["wall_milliseconds"]

    def average(field: str) -> float | None:
        if not presentations:
            return None
        return profile[field] / counts_per_ms / presentations

    metrics: dict[str, float | int | None] = {
        "presentation_hz": presentations * 1000.0 / wall_ms if wall_ms else None,
        "simulation_hz": profile["simulation_ticks"] * 1000.0 / wall_ms if wall_ms else None,
        "missed_deadline_ratio": (
            profile["missed_deadlines"] / presentations if presentations else None
        ),
        "maximum_lateness_ms": profile["maximum_lateness_counts"] / counts_per_ms,
        "total_lateness_ms": profile["total_lateness_counts"] / counts_per_ms,
        "average_render_ms": average("render_counts"),
        "average_present_ms": average("present_counts"),
        "average_space_ms": average("space_counts"),
        "average_cupola_ms": average("cupola_counts"),
        "average_hull_ms": average("hull_counts"),
        "average_detail_ms": average("detail_counts"),
        "input_detection_to_effect_ms": None,
        "input_effect_to_present_ms": None,
        "input_detection_to_present_ms": None,
        "external_counter_comparable": False,
        "process_cycles": process_cycles,
        "average_process_cycles_per_presentation": (
            process_cycles / presentations
            if process_cycles is not None and presentations else None
        ),
    }
    if profile["mode"] != 0:
        metrics.update({
            "average_surface_background_ms": average("space_counts"),
            "average_surface_terrain_ms": average("cupola_counts"),
            "average_surface_effects_ms": average("hull_counts"),
            "average_surface_smoothing_ms": average("detail_counts"),
        })
    detected = profile["input_detected_counter"]
    effect = profile["input_effect_counter"]
    presented = profile["input_presented_counter"]
    if detected and effect:
        metrics["input_detection_to_effect_ms"] = (
            counter_difference(effect, detected) / counts_per_ms)
    if effect and presented:
        metrics["input_effect_to_present_ms"] = (
            counter_difference(presented, effect) / counts_per_ms)
    if detected and presented:
        metrics["input_detection_to_present_ms"] = (
            counter_difference(presented, detected) / counts_per_ms)
    return metrics


def run_scenario(scenario: str, output_directory: Path, executable: Path,
                 duration: float, readiness_timeout: float, *,
                 scheduling_control: str = "controlled",
                 physical_core: str | int = "last") -> Path:
    core_masks = physical_core_affinity_masks()
    affinity_mask, priority_class, scheduling = make_scheduling_plan(
        scheduling_control, physical_core, core_masks)
    executable_hash = file_sha256(executable)
    stage = output_directory / scenario
    staged_executable = stage_scenario(
        stage, executable, scenario_checkpoint(scenario))
    started = time.monotonic()
    injected_counter: int | None = None
    process_cycles = 0
    with PrivateDesktopProcess(
            staged_executable, stage,
            (f"clock={CLOCK_SECONDS}", "profile"),
            affinity_mask=affinity_mask,
            priority_class=priority_class) as process:
        actual_scheduling = process.scheduling_state()
        handle, rectangle = wait_for_ready(process, stage, readiness_timeout)
        ready = time.monotonic()
        cycle_start = process.process_cycle_count()
        time.sleep(1.0)
        if scenario == "fcs":
            tap_key(process, handle, VK_5, 1.0)
        elif scenario == "capsule":
            process.post_char(handle, "r")
        else:
            injected_counter = process.performance_counter() & 0xFFFFFFFF
            process.post_key(handle, VK_W, True)
            time.sleep(min(5.0, duration / 3.0))
            process.post_key(handle, VK_W, False)
        remaining = duration - (time.monotonic() - ready)
        if remaining > 0:
            time.sleep(remaining)
        process_cycles = process.process_cycle_count() - cycle_start
        host_exited_naturally = finish_game_shutdown(process, stage)

    profile_path = stage / "game-profile-out.bin"
    if not profile_path.is_file():
        raise FileNotFoundError("game did not emit terminal profile")
    raw_profile = profile_path.read_bytes()
    profile = decode_profile(raw_profile)
    (stage / "profile.bin").write_bytes(raw_profile)
    scheduling["actual"] = actual_scheduling
    if scheduling["policy"] == CONTROLLED_SCHEDULING:
        scheduling["comparable"] = (
            actual_scheduling["process_affinity_mask"] ==
            scheduling["requested_affinity_mask"]
            and actual_scheduling["priority_class"] ==
            scheduling["requested_priority_class"]
        )
        if not scheduling["comparable"]:
            scheduling["reason"] = (
                "actual process scheduling did not match the requested control")
    report = {
        "schema": 2,
        "scenario": scenario,
        "command": [str(staged_executable), f"clock={CLOCK_SECONDS}", "profile"],
        "provenance": {
            "executable_path": str(executable.resolve()),
            "executable_sha256": executable_hash,
            "scheduling": scheduling,
        },
        "window_rectangle": rectangle,
        "startup_seconds": ready - started,
        "requested_measurement_seconds": duration,
        "shutdown": {
            "application_completed": True,
            "host_exited_naturally": host_exited_naturally,
        },
        "injected_counter": injected_counter,
        "profile": profile,
        "metrics": derived_metrics(profile, injected_counter, process_cycles),
    }
    report_path = stage / "report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario", choices=("surface", "capsule", "stardrifter", "orbital", "fcs"),
        action="append", required=True,
    )
    parser.add_argument(
        "--output-directory", type=Path,
        default=ROOT / "build" / "desktop-profiles",
    )
    parser.add_argument(
        "--executable", type=Path, default=ROOT / "work" / "vhgame.exe")
    parser.add_argument("--duration", type=float, default=20.0)
    parser.add_argument("--readiness-timeout", type=float, default=90.0)
    parser.add_argument(
        "--scheduling-control", choices=("controlled", "uncontrolled"),
        default="controlled",
        help=("pin the game to one physical core at above-normal priority "
              "(default), or retain an explicitly incomparable uncontrolled run"),
    )
    parser.add_argument(
        "--physical-core", default="last", metavar="INDEX|last",
        help="physical core used by controlled profiling (default: last)",
    )
    parser.add_argument("--force", action="store_true",
                        help="replace an already retained scenario report")
    args = parser.parse_args()
    if not 5.0 <= args.duration <= 120.0:
        parser.error("--duration must be between 5 and 120 seconds")

    executable = args.executable.resolve()
    if not executable.is_file():
        parser.error(f"missing executable: {executable}")
    try:
        make_scheduling_plan(
            args.scheduling_control, args.physical_core,
            physical_core_affinity_masks())
    except (OSError, ValueError) as error:
        parser.error(str(error))
    output_directory = args.output_directory.resolve()
    for scenario in args.scenario:
        retained = output_directory / scenario / "report.json"
        if retained.is_file() and not args.force:
            report = json.loads(retained.read_text(encoding="utf-8"))
            scheduling = report.get("provenance", {}).get("scheduling", {})
            status = ("COMPARABLE" if scheduling.get("comparable")
                      else "INCOMPARABLE")
            print(f"RETAINED {status} {scenario}: {retained}")
            continue
        report_path = run_scenario(
            scenario, output_directory, executable,
            args.duration, args.readiness_timeout,
            scheduling_control=args.scheduling_control,
            physical_core=args.physical_core,
        )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        metrics = report["metrics"]
        comparable = report["provenance"]["scheduling"]["comparable"]
        print(
            f"PROFILE {'COMPARABLE' if comparable else 'INCOMPARABLE'} {scenario}: "
            f"{report['profile']['presentations']} presentations, "
            f"{metrics['presentation_hz']:.2f} Hz, "
            f"{metrics['simulation_hz']:.3f} simulation Hz, "
            f"{report['profile']['missed_deadlines']} missed deadlines -> {report_path}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
