#!/usr/bin/env python3
"""Grade the live Lino renderer's companion-weather boundary trio."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
EXECUTABLE = ROOT / "work" / "vhgame.exe"
CAPTURE = ROOT / "tools" / "capture_noctis_scenes.ps1"
ORACLE = ROOT / "tests" / "test_habitable_multiple_weather_oracle.py"
STAGE = ROOT / "build" / "habitable-multiple-weather-runtime"
LOW = STAGE / "low232"
PAINTER = STAGE / "painter231"
FLARE = STAGE / "flare236"
TIMEOUT = 240


def capture_command(output: Path, longitude: int) -> list[str]:
    return [
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", str(CAPTURE),
        "-GameExecutable", str(EXECUTABLE),
        "-Scene", "habitablemultiple",
        "-DiagnosticOnly",
        "-ClockSeconds", "1344168020",
        "-Longitude", str(longitude),
        "-Latitude", "88",
        "-ViewAngle", "-30",
        "-ViewPitch", "-20",
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
        print("SKIP companion-weather runtime oracle requires Windows")
        return 0
    if not EXECUTABLE.is_file():
        raise FileNotFoundError(f"missing compiled game: {EXECUTABLE}")
    if not CAPTURE.is_file() or not ORACLE.is_file():
        raise FileNotFoundError("missing companion-weather capture or oracle script")

    if STAGE.exists():
        shutil.rmtree(STAGE)

    run(capture_command(LOW, 232), "companion-weather below-disc-gate capture")
    run(capture_command(PAINTER, 231), "companion-weather exact-disc-gate capture")
    run(capture_command(FLARE, 236), "companion-weather above-flare-gate capture")
    run(
        [
            sys.executable,
            str(ORACLE),
            "--low-product-directory", str(LOW),
            "--painter-product-directory", str(PAINTER),
            "--flare-product-directory", str(FLARE),
        ],
        "companion-weather oracle",
    )
    print("RESULT PASS - live companion-weather boundary trio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
