#!/usr/bin/env python3
"""Capture and grade bounded groups from the live surface-sun gallery."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys

from test_sun_gallery import CASES


ROOT = Path(__file__).resolve().parents[1]
EXECUTABLE = ROOT / "work" / "vhgame.exe"
CAPTURE = ROOT / "tools" / "capture_noctis_scenes.ps1"
ORACLE = ROOT / "tests" / "test_sun_gallery.py"
STAGE_ROOT = ROOT / "build" / "sun-gallery-runtime"
TIMEOUT = 240
DEFAULT_CLOCK = 1344638527


def capture_command(case_name: str, output: Path) -> list[str]:
    case = CASES[case_name]
    checkpoint = case["checkpoint"]
    assert isinstance(checkpoint, dict)
    command = [
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", str(CAPTURE),
        "-GameExecutable", str(EXECUTABLE),
        "-Scene", str(case["scene"]),
        "-DiagnosticOnly",
        "-ClockSeconds", str(case.get("clock", DEFAULT_CLOCK)),
        "-BodyIndex", str(checkpoint["body"]),
        "-Longitude", str(checkpoint["longitude"]),
        "-Latitude", str(checkpoint["latitude"]),
        "-ViewAngle", str(checkpoint["beta"]),
        "-ViewPitch", str(checkpoint["pitch"]),
        "-PlayerX", str(checkpoint["player_x"]),
        "-PlayerZ", str(checkpoint["player_z"]),
        "-OutputDirectory", str(output),
    ]
    if "player_y" in checkpoint:
        command.extend(("-PlayerY", str(checkpoint["player_y"])))
    return command


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


def run_group(group_name: str, case_names: tuple[str, ...]) -> int:
    if os.name != "nt":
        print(f"SKIP surface-sun {group_name} runtime oracle requires Windows")
        return 0
    if not EXECUTABLE.is_file():
        raise FileNotFoundError(f"missing compiled game: {EXECUTABLE}")
    if not CAPTURE.is_file() or not ORACLE.is_file():
        raise FileNotFoundError("missing surface-sun capture or oracle script")
    if len(case_names) != 4 or any(name not in CASES for name in case_names):
        raise ValueError(f"surface-sun {group_name} must name four retained cases")

    stage = STAGE_ROOT / group_name
    if stage.exists():
        shutil.rmtree(stage)

    for index, case_name in enumerate(case_names, 1):
        output = stage / case_name
        print(f"=== surface-sun {group_name} {index}/4: {case_name} ===")
        run(capture_command(case_name, output), f"{case_name} capture")
        run(
            [
                sys.executable,
                str(ORACLE),
                "--case", case_name,
                "--product-directory", str(output),
            ],
            f"{case_name} oracle",
        )

    print(f"RESULT PASS - live surface-sun {group_name} gallery")
    return 0
