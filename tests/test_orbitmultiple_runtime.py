#!/usr/bin/env python3
"""Grade the live Lino renderer's ROTOR IGNE companion visibility pair."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
EXECUTABLE = ROOT / "work" / "vhgame.exe"
CAPTURE = ROOT / "tools" / "capture_noctis_scenes.ps1"
ORACLE = ROOT / "tests" / "test_orbitmultiple_oracle.py"
STAGE = ROOT / "build" / "orbitmultiple-runtime"
NEGATIVE = STAGE / "negative120"
VISIBLE = STAGE / "visible300"
TIMEOUT = 240


def capture_command(output: Path, navigation: int) -> list[str]:
    return [
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", str(CAPTURE),
        "-GameExecutable", str(EXECUTABLE),
        "-Scene", "orbitmultiple",
        "-DiagnosticOnly",
        "-ClockSeconds", "1344638526",
        "-NavigationAngle", str(navigation),
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
        print("SKIP ROTOR IGNE runtime oracle requires Windows")
        return 0
    if not EXECUTABLE.is_file():
        raise FileNotFoundError(f"missing compiled game: {EXECUTABLE}")
    if not CAPTURE.is_file() or not ORACLE.is_file():
        raise FileNotFoundError("missing ROTOR IGNE capture or oracle script")

    if STAGE.exists():
        shutil.rmtree(STAGE)

    run(capture_command(NEGATIVE, 120), "ROTOR IGNE behind-camera capture")
    run(capture_command(VISIBLE, 300), "ROTOR IGNE front-facing capture")
    run(
        [
            sys.executable,
            str(ORACLE),
            "--product-directory", str(NEGATIVE),
            "--visible-product-directory", str(VISIBLE),
        ],
        "ROTOR IGNE oracle",
    )
    print("RESULT PASS - live ROTOR IGNE companion visibility pair")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
