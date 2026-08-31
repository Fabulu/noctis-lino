#!/usr/bin/env python3
"""Grade the live Lino renderer's dual-companion roof view."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
EXECUTABLE = ROOT / "work" / "vhgame.exe"
CAPTURE = ROOT / "tools" / "capture_noctis_scenes.ps1"
ORACLE = ROOT / "tests" / "test_orbitmultiple_triple_oracle.py"
STAGE = ROOT / "build" / "orbitmultiple-triple-roof-runtime"
ROOF = STAGE / "roof"
TIMEOUT = 240


def capture_command() -> list[str]:
    return [
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", str(CAPTURE),
        "-GameExecutable", str(EXECUTABLE),
        "-Scene", "orbitmultipletripleroof",
        "-DiagnosticOnly",
        "-ClockSeconds", "1345723229",
        "-OutputDirectory", str(ROOF),
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
        print("SKIP dual-companion roof runtime oracle requires Windows")
        return 0
    if not EXECUTABLE.is_file():
        raise FileNotFoundError(f"missing compiled game: {EXECUTABLE}")
    if not CAPTURE.is_file() or not ORACLE.is_file():
        raise FileNotFoundError("missing dual-companion roof capture or oracle script")

    if STAGE.exists():
        shutil.rmtree(STAGE)

    run(capture_command(), "dual-companion roof capture")
    run(
        [
            sys.executable,
            str(ORACLE),
            "--roof-product-directory", str(ROOF),
        ],
        "dual-companion roof oracle",
    )
    print("RESULT PASS - live dual-companion roof view")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
