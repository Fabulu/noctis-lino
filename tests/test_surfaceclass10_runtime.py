#!/usr/bin/env python3
"""Grade the live Lino renderer's class-10 quartz-surface sun."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
EXECUTABLE = ROOT / "work" / "vhgame.exe"
CAPTURE = ROOT / "tools" / "capture_noctis_scenes.ps1"
ORACLE = ROOT / "tests" / "test_surfaceclass10_oracle.py"
STAGE = ROOT / "build" / "surfaceclass10-runtime"
TIMEOUT = 240


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
        print("SKIP class-10 surface-sun runtime oracle requires Windows")
        return 0
    if not EXECUTABLE.is_file():
        raise FileNotFoundError(f"missing compiled game: {EXECUTABLE}")
    if not CAPTURE.is_file() or not ORACLE.is_file():
        raise FileNotFoundError("missing class-10 surface capture or oracle script")

    if STAGE.exists():
        shutil.rmtree(STAGE)

    run(
        [
            "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", str(CAPTURE),
            "-GameExecutable", str(EXECUTABLE),
            "-Scene", "quartzclass10",
            "-DiagnosticOnly",
            "-ClockSeconds", "1344638527",
            "-BodyIndex", "1",
            "-Longitude", "333",
            "-Latitude", "60",
            "-ViewAngle", "270",
            "-ViewPitch", "-30",
            "-PlayerX", "1638400",
            "-PlayerY", "1",
            "-PlayerZ", "1638400",
            "-OutputDirectory", str(STAGE),
        ],
        "class-10 quartz-surface capture",
    )
    run(
        [
            sys.executable,
            str(ORACLE),
            "--product-directory", str(STAGE),
        ],
        "class-10 quartz-surface oracle",
    )
    print("RESULT PASS - live class-10 quartz-surface suppression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
