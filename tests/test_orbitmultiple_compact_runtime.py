#!/usr/bin/env python3
"""Grade the live Lino renderer's compact companion/eclipse pair."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
EXECUTABLE = ROOT / "work" / "vhgame.exe"
CAPTURE = ROOT / "tools" / "capture_noctis_scenes.ps1"
ORACLE = ROOT / "tests" / "test_orbitmultiple_compact_oracle.py"
STAGE = ROOT / "build" / "orbitmultiple-compact-runtime"
POSITIVE = STAGE / "positive162"
ECLIPSE = STAGE / "eclipse144"
TIMEOUT = 240


def capture_command(output: Path, eclipse: bool) -> list[str]:
    command = [
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", str(CAPTURE),
        "-GameExecutable", str(EXECUTABLE),
        "-Scene", "orbitmultiplecompact",
        "-DiagnosticOnly",
        "-ClockSeconds", "1345723227" if eclipse else "1345723228",
    ]
    if eclipse:
        command.extend([
            "-NavigationAngle", "144",
            "-OrbitalLocalX", "-0.010680956489873435",
            "-OrbitalLocalY", "0",
            "-OrbitalLocalZ", "-0.014488518504713672",
        ])
    command.extend(["-OutputDirectory", str(output)])
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
        print("SKIP compact companion runtime oracle requires Windows")
        return 0
    if not EXECUTABLE.is_file():
        raise FileNotFoundError(f"missing compiled game: {EXECUTABLE}")
    if not CAPTURE.is_file() or not ORACLE.is_file():
        raise FileNotFoundError("missing compact companion capture or oracle script")

    if STAGE.exists():
        shutil.rmtree(STAGE)

    run(capture_command(POSITIVE, False), "compact companion positive capture")
    run(capture_command(ECLIPSE, True), "compact parent-eclipse capture")
    run(
        [
            sys.executable,
            str(ORACLE),
            "--product-directory", str(POSITIVE),
            "--eclipse-product-directory", str(ECLIPSE),
        ],
        "compact companion oracle",
    )
    print("RESULT PASS - live compact companion/eclipse pair")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
