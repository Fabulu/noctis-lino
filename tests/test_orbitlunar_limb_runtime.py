#!/usr/bin/env python3
"""Grade the live Lino renderer at the IDEAL beside-primary lunar limb."""

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
STAGE = ROOT / "build" / "orbitlunar-limb-runtime"
TIMEOUT = 240


def capture_command() -> list[str]:
    return [
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", str(CAPTURE),
        "-GameExecutable", str(EXECUTABLE),
        "-Scene", "orbitlunar",
        "-DiagnosticOnly",
        "-ClockSeconds", "1344638736",
        "-ViewAngle", "67",
        "-NavigationAngle", "0",
        "-ViewPitch", "0",
        "-PlayerX", "0",
        "-PlayerY", "0",
        "-PlayerZ", "-500",
        "-OrbitalSync", "0",
        "-OrbitalLocalX", "-0.01181518607173147",
        "-OrbitalLocalY", "0.0000025128783893597895",
        "-OrbitalLocalZ", "0.005015248936280497",
        "-OutputDirectory", str(STAGE),
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
        print("SKIP lunar-limb runtime oracle requires Windows")
        return 0
    if not EXECUTABLE.is_file():
        raise FileNotFoundError(f"missing compiled game: {EXECUTABLE}")
    if not CAPTURE.is_file() or not ORACLE.is_file():
        raise FileNotFoundError("missing lunar-limb capture or oracle script")

    if STAGE.exists():
        shutil.rmtree(STAGE)

    run(capture_command(), "lunar-limb capture")
    run(
        [
            sys.executable,
            str(ORACLE),
            "--limb-product-directory", str(STAGE),
        ],
        "lunar-limb oracle",
    )
    print("RESULT PASS - live IDEAL beside-primary lunar limb")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
