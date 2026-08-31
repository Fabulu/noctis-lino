#!/usr/bin/env python3
"""Grade the live Lino renderer's frozen-world sunrise boundary pair."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
EXECUTABLE = ROOT / "work" / "vhgame.exe"
CAPTURE = ROOT / "tools" / "capture_noctis_scenes.ps1"
ORACLE = ROOT / "tests" / "test_frozen_sunrise_oracle.py"
STAGE = ROOT / "build" / "frozen-sunrise-runtime"
DAY = STAGE / "day74"
NIGHT = STAGE / "night75"
TIMEOUT = 240


def capture_command(output: Path, longitude: int) -> list[str]:
    return [
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", str(CAPTURE),
        "-GameExecutable", str(EXECUTABLE),
        "-Scene", "frozensun",
        "-DiagnosticOnly",
        "-ClockSeconds", "1344638527",
        "-Longitude", str(longitude),
        "-ViewPitch", "0",
        "-OutputDirectory", str(output),
    ]


def run(command: list[str], description: str) -> None:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=TIMEOUT,
    )
    print(completed.stdout, end="")
    if completed.returncode:
        raise RuntimeError(f"{description} failed with code {completed.returncode}")


def main() -> int:
    if os.name != "nt":
        print("SKIP frozen-sunrise runtime oracle requires Windows")
        return 0
    if not EXECUTABLE.is_file():
        raise FileNotFoundError(f"missing compiled game: {EXECUTABLE}")
    if not CAPTURE.is_file() or not ORACLE.is_file():
        raise FileNotFoundError("missing frozen-sunrise capture or oracle script")

    if STAGE.exists():
        shutil.rmtree(STAGE)

    run(capture_command(DAY, 74), "frozen sunrise day-74 capture")
    run(capture_command(NIGHT, 75), "frozen sunrise night-75 capture")
    run(
        [
            sys.executable,
            str(ORACLE),
            "--day-product-directory", str(DAY),
            "--night-product-directory", str(NIGHT),
        ],
        "frozen-sunrise oracle",
    )
    print("RESULT PASS - live frozen-world sunrise boundary pair")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
