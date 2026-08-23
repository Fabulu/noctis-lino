"""Check sustained desktop-profile schema and private-runner contracts."""

from __future__ import annotations

from pathlib import Path
import struct
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import profile_noctis_desktop as profiler  # noqa: E402


GAME = ROOT / "work" / "vhgame.txt"
PRIVATE_RUNNER = ROOT / "tools" / "windows_hidden_process.py"


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
    metrics = profiler.derived_metrics(decoded, 0xFFFFFFF0)
    check(metrics["presentation_hz"] == 60.0 and metrics["simulation_hz"] == 18.2,
          "profile derives presentation and authoritative simulation rates")
    check(abs(metrics["input_detection_to_effect_ms"] - 0.0016) < 1e-12 and
          abs(metrics["input_effect_to_present_ms"] - 4.0912) < 1e-12 and
          metrics["external_counter_comparable"] is False,
          "profile derives internal detection, movement-effect, and presentation latency")

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
    check(struct.unpack_from("<ii", capsule, 4 * 4)[0] == 131072 and
          struct.unpack_from("<i", capsule, 6 * 4)[0] == 131072,
          "capsule-return checkpoint starts exactly at the landed capsule")
    local_active, local_body = struct.unpack_from("<ii", orbital, 48 * 4)
    local_x, local_y, local_z = struct.unpack_from("<3d", orbital, 50 * 4)
    check((local_active, local_body) == (1, 3) and
          (local_x, local_y, local_z) == (0.032783, 0.0, -0.077237),
          "orbital session restores the calibrated close-approach state")

    game = GAME.read_text(encoding="utf-8")
    private_runner = PRIVATE_RUNNER.read_text(encoding="utf-8")
    check("VHGSIMADD = 18206; VHGSIMDEN = 60000;" in game,
          "profile instrumentation leaves the 18.206-Hz gameplay cadence intact")
    check(all(fragment in game for fragment in (
              "vhgprofilename = { game-profile-out.bin };",
              "=> PGF constants; => VH view init; => GR float init;",
              "[VHGprofilepresentations]+;",
              "[VHGprofilesimticks]+;",
              "[VHGprofilemissed]+;",
              "[VHGprofileinputseen] = [Counts];",
              "[VHGprofileinputeffect] = [Counts]; [VHGprofileinputpending] = 2;",
              "[VHGprofileinputpresent] = [VHGprofnow];",
              "[Block Pointer] = vhgprofile; [Block Size] = 128; isocall;",
              "[File Size] = 128; isocall;",
          )),
          "game records terminal timing, cadence, deadline, and input fields")
    check(game.count("=> VHG profile W effect;") == 2,
          "W effect timing covers both Stardrifter and surface movement")
    check(all(fragment in private_runner for fragment in (
              "class PrivateDesktopProcess:",
              "EnumDesktopWindows",
              "PostMessageW",
              "QueryPerformanceCounter",
              "TerminateProcess",
          )),
          "profiling runner controls only its private desktop process")

    if failures:
        print(f"desktop profile: {len(failures)} failure(s)")
        return 1
    print("desktop profile: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
