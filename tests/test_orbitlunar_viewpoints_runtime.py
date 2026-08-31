#!/usr/bin/env python3
"""Grade the live Lino renderer's IDEAL exterior, interior, and roof views."""

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
STAGE = ROOT / "build" / "orbitlunar-viewpoints-runtime"
EXTERIOR = STAGE / "exterior"
INTERIOR = STAGE / "interior"
ROOF = STAGE / "roof"
TIMEOUT = 240


def capture_command(
        output: Path, clock: int, view_angle: int,
        player: tuple[str, str, str], sync: int,
        local: tuple[str, str, str], open_hud: bool = False) -> list[str]:
    command = [
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", str(CAPTURE),
        "-GameExecutable", str(EXECUTABLE),
        "-Scene", "orbitlunar",
        "-DiagnosticOnly",
        "-ClockSeconds", str(clock),
        "-ViewAngle", str(view_angle),
        "-NavigationAngle", "0",
        "-ViewPitch", "0",
        "-PlayerX", player[0],
        "-PlayerY", player[1],
        "-PlayerZ", player[2],
        "-OrbitalSync", str(sync),
        "-OrbitalLocalX", local[0],
        "-OrbitalLocalY", local[1],
        "-OrbitalLocalZ", local[2],
        "-OutputDirectory", str(output),
    ]
    if open_hud:
        command.append("-OpenHud")
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


def main() -> int:
    if os.name != "nt":
        print("SKIP lunar-viewpoint runtime oracle requires Windows")
        return 0
    if not EXECUTABLE.is_file():
        raise FileNotFoundError(f"missing compiled game: {EXECUTABLE}")
    if not CAPTURE.is_file() or not ORACLE.is_file():
        raise FileNotFoundError("missing lunar-viewpoint capture or oracle script")

    if STAGE.exists():
        shutil.rmtree(STAGE)

    common_player = ("0", "0", "-500")
    fixed_chase_local = ("0", "0", "0.012942215051003982")
    run(
        capture_command(
            EXTERIOR, 1344638736, 0, common_player, 1, fixed_chase_local,
        ),
        "exterior lunar-view capture",
    )
    run(
        capture_command(
            INTERIOR, 1344638736, -97, common_player, 1,
            fixed_chase_local, open_hud=True,
        ),
        "interior lunar-view capture",
    )
    run(
        capture_command(
            ROOF, 1344638737, 180, ("0", "-750", "-1900"), 0,
            (
                "-0.011817786847501566",
                "0.0000025128807406016307",
                "0.005035752345708744",
            ),
        ),
        "roof lunar-view capture",
    )
    run(
        [
            sys.executable,
            str(ORACLE),
            "--exterior-product-directory", str(EXTERIOR),
            "--interior-product-directory", str(INTERIOR),
            "--roof-product-directory", str(ROOF),
        ],
        "lunar-viewpoint oracle",
    )
    print("RESULT PASS - live IDEAL exterior, interior, and roof viewpoints")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
