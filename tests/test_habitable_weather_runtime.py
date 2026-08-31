#!/usr/bin/env python3
"""Grade the live Lino renderer's habitable primary-weather boundary pair."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
EXECUTABLE = ROOT / "work" / "vhgame.exe"
CAPTURE = ROOT / "tools" / "capture_noctis_scenes.ps1"
ORACLE = ROOT / "tests" / "test_habitable_weather_oracle.py"
STAGE = ROOT / "build" / "habitable-weather-runtime"
CONTROL = STAGE / "control104"
THRESHOLD = STAGE / "threshold105"
TIMEOUT = 240


def capture_command(output: Path, longitude: int) -> list[str]:
    return [
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", str(CAPTURE),
        "-GameExecutable", str(EXECUTABLE),
        "-Scene", "habitable",
        "-DiagnosticOnly",
        "-ClockSeconds", "1344168020",
        "-Longitude", str(longitude),
        "-Latitude", "56",
        "-ViewAngle", "87",
        "-ViewPitch", "-26",
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
        print("SKIP habitable-weather runtime oracle requires Windows")
        return 0
    if not EXECUTABLE.is_file():
        raise FileNotFoundError(f"missing compiled game: {EXECUTABLE}")
    if not CAPTURE.is_file() or not ORACLE.is_file():
        raise FileNotFoundError("missing habitable-weather capture or oracle script")

    if STAGE.exists():
        shutil.rmtree(STAGE)

    run(capture_command(CONTROL, 104), "habitable weather control-104 capture")
    run(capture_command(THRESHOLD, 105), "habitable weather threshold-105 capture")
    run(
        [
            sys.executable,
            str(ORACLE),
            "--control-product-directory", str(CONTROL),
            "--threshold-product-directory", str(THRESHOLD),
        ],
        "habitable-weather oracle",
    )
    print("RESULT PASS - live habitable primary-weather boundary pair")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
