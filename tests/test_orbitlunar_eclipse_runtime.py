#!/usr/bin/env python3
"""Grade the live Lino renderer's IDEAL globe-before-primary ordering pair."""

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
STAGE = ROOT / "build" / "orbitlunar-eclipse-runtime"
ECLIPSE = STAGE / "eclipsed"
CONTROL = STAGE / "control"
TIMEOUT = 240


def capture_command(output: Path, clock: int,
                    local: tuple[str, str, str]) -> list[str]:
    return [
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", str(CAPTURE),
        "-GameExecutable", str(EXECUTABLE),
        "-Scene", "orbitlunar",
        "-DiagnosticOnly",
        "-ClockSeconds", str(clock),
        "-ViewAngle", "0",
        "-NavigationAngle", "97",
        "-ViewPitch", "0",
        "-PlayerX", "0",
        "-PlayerY", "0",
        "-PlayerZ", "-500",
        "-OrbitalSync", "0",
        "-OrbitalLocalX", local[0],
        "-OrbitalLocalY", local[1],
        "-OrbitalLocalZ", local[2],
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
        print("SKIP lunar eclipse runtime oracle requires Windows")
        return 0
    if not EXECUTABLE.is_file():
        raise FileNotFoundError(f"missing compiled game: {EXECUTABLE}")
    if not CAPTURE.is_file() or not ORACLE.is_file():
        raise FileNotFoundError("missing lunar eclipse capture or oracle script")

    if STAGE.exists():
        shutil.rmtree(STAGE)

    run(
        capture_command(
            ECLIPSE,
            1344638737,
            (
                "-0.012742310308063054",
                "0.0000025128783893600334",
                "-0.0015451078402124452",
            ),
        ),
        "globe-before-primary capture",
    )
    run(
        capture_command(
            CONTROL,
            1344638740,
            (
                "-0.011825589247429491",
                "0.0000025128783893600334",
                "0.00509726245594333",
            ),
        ),
        "beside-primary control capture",
    )
    run(
        [
            sys.executable,
            str(ORACLE),
            "--eclipse-product-directory", str(ECLIPSE),
            "--eclipse-control-product-directory", str(CONTROL),
        ],
        "globe-before-primary oracle",
    )
    print("RESULT PASS - live IDEAL globe-before-primary ordering pair")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
