#!/usr/bin/env python3
"""Grade the live Lino renderer across the strict Stardrifter cupola boundary."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
EXECUTABLE = ROOT / "work" / "vhgame.exe"
CAPTURE = ROOT / "tools" / "capture_noctis_scenes.ps1"
ORACLE = ROOT / "tests" / "test_orbitlunar_oracle.py"
STAGE = ROOT / "build" / "orbitlunar-boundary-runtime"
INSIDE = STAGE / "inside"
ROOF = STAGE / "roof"
TIMEOUT = 240


def capture_command(output: Path, player_y: int) -> list[str]:
    return [
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", str(CAPTURE),
        "-GameExecutable", str(EXECUTABLE),
        "-Scene", "orbitlunar",
        "-DiagnosticOnly",
        "-ClockSeconds", "1344638737",
        "-ViewAngle", "180",
        "-NavigationAngle", "0",
        "-ViewPitch", "0",
        "-PlayerX", "0",
        "-PlayerY", str(player_y),
        "-PlayerZ", "-1900",
        "-OrbitalSync", "0",
        "-OrbitalLocalX", "-0.011817786847501566",
        "-OrbitalLocalY", "0.0000025128807406016307",
        "-OrbitalLocalZ", "0.005035752345708744",
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
        print("SKIP strict cupola-boundary runtime oracle requires Windows")
        return 0
    if not EXECUTABLE.is_file():
        raise FileNotFoundError(f"missing compiled game: {EXECUTABLE}")
    if not CAPTURE.is_file() or not ORACLE.is_file():
        raise FileNotFoundError("missing cupola-boundary capture or oracle script")

    if STAGE.exists():
        shutil.rmtree(STAGE)

    run(capture_command(INSIDE, -500), "inside-boundary capture")
    run(capture_command(ROOF, -501), "roof-boundary capture")
    run(
        [
            sys.executable,
            str(ORACLE),
            "--boundary-inside-product-directory", str(INSIDE),
            "--boundary-roof-product-directory", str(ROOF),
        ],
        "cupola-boundary oracle",
    )
    print("RESULT PASS - live strict Stardrifter cupola boundary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
