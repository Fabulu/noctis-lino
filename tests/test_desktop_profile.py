"""Check sustained desktop-profile schema and private-runner contracts."""

from __future__ import annotations

from pathlib import Path
import struct
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import profile_noctis_desktop as profiler  # noqa: E402


GAME = ROOT / "work" / "vhgame.txt"
GROUND = ROOT / "work" / "vhground.txt"
PROFILER = ROOT / "tools" / "profile_noctis_desktop.py"
PRIVATE_RUNNER = ROOT / "tools" / "windows_hidden_process.py"
LINO_PROGRAM_RUNNER = ROOT / "tools" / "run_lino_program_private.py"
LINO_RUN_SCRIPT = ROOT / "tests" / "linorun.ps1"
WAVE7_RUN_SCRIPT = ROOT / "tests" / "w7arun.ps1"


def main() -> int:
    failures: list[str] = []

    def check(condition: bool, message: str) -> None:
        print("PASS" if condition else "FAIL", message)
        if not condition:
            failures.append(message)

    values = [0] * profiler.PROFILE_UNITS
    values[0] = profiler.PROFILE_MAGIC
    values[1] = 1
    values[2] = 1200
    values[3] = 364
    values[4] = 3
    values[5] = 2500
    values[6] = 5000
    values[7] = 12_000_000
    values[8] = 1_200_000
    values[13] = 20_000
    values[14] = 10_000
    values[19] = 0
    values[20] = 0
    values[22] = profiler.VK_W
    values[24] = 0x00000020
    values[25] = 0x00000030
    values[26] = 0x0000A000
    values[27] = 0xFFFFFFFF
    values[31] = profiler.PROFILE_MAGIC
    data = struct.pack("<32I", *values)
    decoded = profiler.decode_profile(data)
    check(decoded["presentations"] == 1200 and decoded["final_x"] == -1,
          "profile decoder preserves unsigned counters and signed coordinates")
    check(profiler.counter_difference(0x20, 0xFFFFFFF0) == 0x30,
          "input latency subtraction crosses low-32-bit counter wrap")
    metrics = profiler.derived_metrics(decoded, 0xFFFFFFF0, 36_000_000)
    check(metrics["presentation_hz"] == 60.0 and metrics["simulation_hz"] == 18.2,
          "profile derives presentation and authoritative simulation rates")
    check(metrics["process_cycles"] == 36_000_000 and
          metrics["average_process_cycles_per_presentation"] == 30_000,
          "profile derives frequency-independent process cycles per presentation")
    check(abs(metrics["input_detection_to_effect_ms"] - 0.0016) < 1e-12 and
          abs(metrics["input_effect_to_present_ms"] - 4.0912) < 1e-12 and
          metrics["external_counter_comparable"] is False,
          "profile derives internal detection, movement-effect, and presentation latency")

    trace_values = [
        profiler.PRESENTATION_TRACE_MAGIC,
        profiler.PRESENTATION_TRACE_SCHEMA,
        3,
        profiler.PRESENTATION_TRACE_STRIDE_UNITS,
        1000,
        0,
        3,
        profiler.PRESENTATION_TRACE_MAGIC,
        0xFFFFFFF0, 0xFFFFFFFF, 2, 3, 4, 5, 0,
        0x00000020, 0xFFFFFFFF, 2, 3, 4, 5, 0,
        0x00000050, 7, 8, 9, 10, 11, 1,
    ]
    trace_data = struct.pack(f"<{len(trace_values)}I", *trace_values)
    trace = profiler.decode_presentation_trace(trace_data)
    check(trace["records"][0]["pose"]["x"] == -1 and
          trace["records"][1]["elapsed_counts"] == 0x30 and
          trace["records"][2]["simulation_ticks"] == 1,
          "presentation trace preserves signed poses, wrapped timestamps, and ticks")
    check(trace["metrics"]["unique_pose_count"] == 2 and
          trace["metrics"]["consecutive_duplicate_pose_count"] == 1 and
          trace["metrics"]["maximum_same_pose_run"] == 2 and
          abs(trace["metrics"]["maximum_interval_ms"] - 0.048) < 1e-12,
          "presentation trace diagnoses exact consecutive duplicate poses")
    surface_metrics = profiler.derived_metrics({**decoded, "mode": 1}, None)
    check(all(surface_metrics[field] == 0.0 for field in (
              "average_surface_background_ms",
              "average_surface_terrain_ms",
              "average_surface_effects_ms",
              "average_surface_smoothing_ms",
          )),
          "surface profiles expose background, terrain, effects, and smoothing costs")

    synthetic_cores = (0x03, 0x0C, 0x30, 0xC0)
    check(profiler.select_physical_core(synthetic_cores, "last") == (3, 0xC0) and
          profiler.select_physical_core(synthetic_cores, "1") == (1, 0x0C),
          "scheduler selects a complete fixed physical core")
    affinity, priority, controlled = profiler.make_scheduling_plan(
        "controlled", "last", synthetic_cores)
    check(affinity == 0xC0 and
          priority == profiler.ABOVE_NORMAL_PRIORITY_CLASS and
          controlled["policy"] == profiler.CONTROLLED_SCHEDULING and
          controlled["comparable"] is True and
          controlled["physical_core_masks"] == ["0x3", "0xc", "0x30", "0xc0"],
          "controlled profiles request one physical core at above-normal priority")
    affinity, priority, uncontrolled = profiler.make_scheduling_plan(
        "uncontrolled", "last", synthetic_cores)
    check(affinity is None and priority is None and
          uncontrolled["comparable"] is False and
          "not controlled" in uncontrolled["reason"],
          "uncontrolled profiles are unambiguously incomparable")
    try:
        profiler.select_physical_core(synthetic_cores, "4")
    except ValueError:
        bad_core_rejected = True
    else:
        bad_core_rejected = False
    check(bad_core_rejected, "scheduler rejects an unavailable physical core")

    for corrupt, description in (
        (data[:-4], "truncated profile"),
        (struct.pack("<32I", *([0] + values[1:])), "bad leading magic"),
        (struct.pack("<32I", *(values[:31] + [0])), "bad trailing magic"),
    ):
        try:
            profiler.decode_profile(corrupt)
        except ValueError:
            passed = True
        else:
            passed = False
        check(passed, f"decoder rejects {description}")

    for corrupt, description in (
        (trace_data[:-4], "truncated presentation trace"),
        (struct.pack(f"<{len(trace_values)}I", *([0] + trace_values[1:])),
         "bad presentation trace magic"),
        (struct.pack(f"<{len(trace_values)}I",
                     *(trace_values[:6] + [4] + trace_values[7:])),
         "presentation trace count mismatch"),
    ):
        try:
            profiler.decode_presentation_trace(corrupt)
        except ValueError:
            passed = True
        else:
            passed = False
        check(passed, f"decoder rejects {description}")

    surface = profiler.scenario_checkpoint("surface")
    capsule = profiler.scenario_checkpoint("capsule")
    stardrifter = profiler.scenario_checkpoint("stardrifter")
    orbital = profiler.scenario_checkpoint("orbital")
    check(all(len(item) == 264 for item in (surface, capsule, stardrifter, orbital)),
          "all profiler checkpoints retain the exact version-15 stable extent")
    check(struct.unpack_from("<i", surface, 2 * 4)[0] == 1 and
          struct.unpack_from("<i", stardrifter, 2 * 4)[0] == 0 and
          all(struct.unpack_from("<i", item, 27 * 4)[0] == 1
              for item in (surface, capsule, stardrifter, orbital)),
          "sessions preserve product modes with the 60-Hz presenter enabled")
    check(struct.unpack_from("<ii", capsule, 4 * 4)[0] == 1638400 and
          struct.unpack_from("<i", capsule, 6 * 4)[0] == 1638400,
          "capsule-return checkpoint starts exactly at the landed capsule")
    local_active, local_body = struct.unpack_from("<ii", orbital, 48 * 4)
    local_x, local_y, local_z = struct.unpack_from("<3d", orbital, 50 * 4)
    check((local_active, local_body) == (1, 3) and
          (local_x, local_y, local_z) == (0.032783, 0.0, -0.077237),
          "orbital session restores the calibrated close-approach state")

    game = GAME.read_text(encoding="utf-8")
    ground = GROUND.read_text(encoding="utf-8")
    profiler_source = PROFILER.read_text(encoding="utf-8")
    private_runner = PRIVATE_RUNNER.read_text(encoding="utf-8")
    lino_program_runner = LINO_PROGRAM_RUNNER.read_text(encoding="utf-8")
    lino_run_script = LINO_RUN_SCRIPT.read_text(encoding="utf-8")
    wave7_run_script = WAVE7_RUN_SCRIPT.read_text(encoding="utf-8")
    check('process.post_char(handle, "r")' in profiler_source and
          "tap_key(process, handle, VK_R" not in profiler_source,
          "capsule profiles inject the ASCII return command used by the game")
    check("--require-presentation-trace" in profiler_source and
          "decode_presentation_trace(raw_trace)" in profiler_source and
          '"presentation-trace.bin"' in profiler_source,
          "minute profiles can require and retain decoded per-presentation evidence")
    check("VHGSIMADD = 18206; VHGSIMDEN = 60000;" in game,
          "profile instrumentation leaves the 18.206-Hz gameplay cadence intact")
    check(all(fragment in game for fragment in (
              "vhgprofilename = { game-profile-out.bin };",
              "vhgptracename = { game-presentation-trace-out.bin };",
              "VHGPTRCAP = 4096; VHGPTRSTRIDE = 7; VHGPTRHEADER = 8;",
              "=> PGF constants; => VH view init; => GR float init;",
              "[VHGprofilepresentations]+;",
              "=> VHG interpolation apply;\n\t\t[VHGpresentx] = [VHGx];",
              "[VHGpresentbeta] = [VHGbeta];\n\t\t=> VHG render;",
              "=> VHG profile presentation trace;",
              "[D plus 0] = [VHGprofnow]; [D plus 1] = [VHGpresentx];",
              "[D plus 6] = [VHGprofilesimticks]; [VHGptracecount]+;",
              "[VHGprofilesimticks]+;",
              "[VHGprofilemissed]+;",
              "[VHGprofileinputseen] = [Counts];",
              "[VHGprofileinputeffect] = [Counts]; [VHGprofileinputpending] = 2;",
              "[VHGprofileinputpresent] = [VHGprofnow];",
              "[Block Pointer] = vhgprofile; [Block Size] = 128; isocall;",
              "[File Size] = 128; isocall;",
              "[vhgptrace plus 6] = [VHGprofilepresentations];",
              "[Block Pointer] = vhgptrace; [Block Size] = [VHGptracesize]; isocall;",
          )),
          "game records terminal timing, cadence, deadline, and input fields")
    check(game.count("=> VHG profile W effect;") == 2,
          "W effect timing covers both Stardrifter and surface movement")
    check(all(fragment in ground for fragment in (
              "A + [VHGprofspace]; [VHGprofspace] = A;",
              "A + [VHGprofcupola]; [VHGprofcupola] = A;",
              "A + [VHGprofhull]; [VHGprofhull] = A;",
              "A + [VHGprofdetail]; [VHGprofdetail] = A;",
          )),
          "surface renderer records background, terrain, effects, and smoothing phases")
    check(all(fragment in private_runner for fragment in (
              "class PrivateDesktopProcess:",
              "EnumDesktopWindows",
              "PostMessageW",
              "QueryPerformanceCounter",
              "QueryProcessCycleTime",
              "GetLogicalProcessorInformation",
              "SetProcessAffinityMask",
              "GetProcessAffinityMask",
              "GetPriorityClass",
              "TerminateProcess",
          )),
          "profiling runner controls only its private desktop process")
    check("PrivateDesktopProcess" in lino_program_runner and
          "--require-clean-exit" in lino_program_runner and
          "run_lino_program_private.py" in lino_run_script and
          "run_lino_program_private.py" in wave7_run_script and
          "System.Diagnostics.Process" not in lino_run_script and
          "System.Diagnostics.Process" not in wave7_run_script and
          "size = fresh_size(args.output, started_ns)" in
          lino_program_runner.split("if exit_code is not None:", 1)[1],
          "compiled Lino tests run only on a private inactive desktop, support "
          "clean-exit witnesses, and recheck output after process exit")

    if failures:
        print(f"desktop profile: {len(failures)} failure(s)")
        return 1
    print("desktop profile: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
