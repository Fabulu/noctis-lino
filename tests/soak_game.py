"""Build and run a bounded, self-terminating copy of the integrated game.

The checked-in game is deliberately a long-lived GUI programme.  This utility
keeps the source and output in ``tests/gen/game_soak`` and makes two guarded
substitutions in a copy: the telemetry frame target and an exit immediately
after that terminal telemetry write.  It therefore exercises the real build,
flight, render and present path without changing ``work/game.txt``.
"""

from __future__ import annotations

import argparse
import math
import re
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "work" / "game.txt"
GEN = ROOT / "tests" / "gen" / "game_soak"
SANDBOX_SOURCE = GEN / "game_soak.txt"
SANDBOX_EXE = GEN / "game_soak.exe"
OUTPUT = GEN / "game-out.bin"
ERRORLOG = GEN / "errorlog.txt"
BUILD_PS1 = ROOT / "lino_build.ps1"
RUN_PS1 = ROOT / "tests" / "w7arun.ps1"
COMPILER = ROOT / "main" / "lib" / "gen" / "compiler114m.exe"

def fail(message: str) -> int:
    print(f"SOAK-FAIL {message}")
    return 1


def make_sandbox(frame_target: int) -> None:
    if not SOURCE.is_file():
        raise RuntimeError(f"source not found: {SOURCE}")
    GEN.mkdir(parents=True, exist_ok=True)
    # These are the only generated names this utility owns.
    for path in (SANDBOX_EXE, OUTPUT, ERRORLOG):
        path.unlink(missing_ok=True)

    shutil.copy2(SOURCE, SANDBOX_SOURCE)
    text = SANDBOX_SOURCE.read_text(encoding="utf-8")

    # The compiler resolves a library name relative to the source directory.
    # Mirror only the libraries declared by this programme into the sandbox;
    # no build input is redirected to work/ and no generated file is emitted
    # there.
    library_block = text.split('"libraries"', 1)[1].split('"workspace"', 1)[0]
    libraries = re.findall(r"^\s*([A-Za-z0-9_/]+);", library_block, re.MULTILINE)
    for library in libraries:
        original = SOURCE.parent / f"{library}.txt"
        if not original.is_file():
            raise RuntimeError(f"library source not found: {original}")
        destination = GEN / f"{library}.txt"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, destination)

    frame_needle = "GMSENTFRAME = 3;"
    if text.count(frame_needle) != 1:
        raise RuntimeError(
            f"guard failed: expected one {frame_needle!r}, "
            f"found {text.count(frame_needle)}"
        )
    text = text.replace(frame_needle, f"GMSENTFRAME = {frame_target};", 1)

    sentinel_needle = '\t[GMsent] = 1;\n    "GM after sent"'
    sentinel_replacement = (
        '\t[GMsent] = 1;\n'
        '\t[GMesc] = 1;\n'
        '    "GM after sent"'
    )
    if text.count(sentinel_needle) != 1:
        raise RuntimeError(
            "guard failed: expected one terminal telemetry continuation, "
            f"found {text.count(sentinel_needle)}"
        )
    text = text.replace(sentinel_needle, sentinel_replacement, 1)
    SANDBOX_SOURCE.write_text(text, encoding="utf-8", newline="")


def powershell(script: Path, *args: str, timeout: float) -> tuple[int, str]:
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
        *args,
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    return completed.returncode, output.strip()


def build() -> str:
    rc, output = powershell(
        BUILD_PS1,
        "-Src",
        str(SANDBOX_SOURCE),
        "-Compiler",
        str(COMPILER),
        "-Cpu",
        "i386m",
        timeout=300,
    )
    if rc != 0:
        raise RuntimeError(f"build rc={rc}: {output}")
    return output


def parse_telemetry(blob: bytes, target: int) -> dict[str, object]:
    if len(blob) != 24 * 4:
        raise RuntimeError(f"telemetry is {len(blob)} bytes, expected 96")
    values = struct.unpack("<24i", blob)
    initial_dzat = values[0:2]
    live_dzat = values[2:4]
    initial_pwr = values[4]
    live_pwr = values[5]
    frame = values[7]
    fb_samples = values[16:24]

    if frame != target:
        raise RuntimeError(f"terminal frame {frame}, expected {target}")
    if live_dzat == initial_dzat:
        raise RuntimeError("live dzat is unchanged from the initial snapshot")
    if live_pwr == initial_pwr:
        raise RuntimeError("live pwr did not progress from the initial snapshot")
    if not any(sample != 0 for sample in fb_samples):
        raise RuntimeError("all eight framebuffer samples are zero")

    return {
        "frame": frame,
        "initial_dzat": initial_dzat,
        "live_dzat": live_dzat,
        "initial_pwr": initial_pwr,
        "live_pwr": live_pwr,
        "fb_samples": fb_samples,
    }


def run(target: int, timeout: float) -> tuple[dict[str, object], str, float]:
    started = time.perf_counter()
    rc, output = powershell(
        RUN_PS1,
        "-Exe",
        str(SANDBOX_EXE),
        "-Out",
        str(OUTPUT),
        "-TimeoutSec",
        str(max(1, math.ceil(timeout))),
        "-RequireCleanExit",
        timeout=timeout + 30.0,
    )
    elapsed = time.perf_counter() - started
    if rc != 0:
        raise RuntimeError(f"runner rc={rc}: {output}")
    if "clean-exit" not in output.lower():
        raise RuntimeError(f"runner did not prove clean exit: {output}")
    if not OUTPUT.is_file():
        raise RuntimeError("runner succeeded without game-out.bin")
    telemetry = parse_telemetry(OUTPUT.read_bytes(), target)
    return telemetry, output, elapsed


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=60, help="terminal telemetry frame (default: 60)")
    parser.add_argument("--timeout", type=float, default=600.0, help="runner timeout in seconds (default: 600)")
    args = parser.parse_args(argv)
    if args.frames <= 0 or args.frames > 1_000_000:
        parser.error("--frames must be between 1 and 1000000")
    if not math.isfinite(args.timeout) or args.timeout <= 0 or args.timeout > 86_400:
        parser.error("--timeout must be finite, positive, and at most 86400 seconds")
    return args


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        make_sandbox(args.frames)
        build_output = build()
        telemetry, run_output, elapsed = run(args.frames, args.timeout)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        return fail(str(exc))

    fps = args.frames / elapsed if elapsed > 0 else float("inf")
    print(f"SOAK-OK frames={telemetry['frame']} bytes=96 wall={elapsed:.2f}s fps={fps:.2f}")
    print(
        "  dzat {0}->{1} pwr {2}->{3} fb-nonzero={4}/8".format(
            telemetry["initial_dzat"],
            telemetry["live_dzat"],
            telemetry["initial_pwr"],
            telemetry["live_pwr"],
            sum(sample != 0 for sample in telemetry["fb_samples"]),
        )
    )
    print(f"  build: {build_output}")
    print(f"  run:   {run_output}")
    print(f"  sandbox: {GEN}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
