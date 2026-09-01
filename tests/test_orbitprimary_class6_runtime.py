#!/usr/bin/env python3
"""Grade the live Lino renderer's class-6 orbital primary."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
EXECUTABLE = ROOT / "work" / "vhgame.exe"
CAPTURE = ROOT / "tools" / "capture_noctis_scenes.ps1"
ORACLE = ROOT / "tests" / "test_orbitprimary_class6_oracle.py"
STAGE = ROOT / "build" / "orbitprimary-class6-runtime"
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
        print("SKIP class-6 orbital-primary runtime oracle requires Windows")
        return 0
    if not EXECUTABLE.is_file():
        raise FileNotFoundError(f"missing compiled game: {EXECUTABLE}")
    if not CAPTURE.is_file() or not ORACLE.is_file():
        raise FileNotFoundError("missing class-6 orbital capture or oracle script")

    if STAGE.exists():
        shutil.rmtree(STAGE)

    run(
        [
            "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", str(CAPTURE),
            "-GameExecutable", str(EXECUTABLE),
            "-Scene", "stardrifterclass6",
            "-DiagnosticOnly",
            "-OutputDirectory", str(STAGE),
        ],
        "class-6 orbital-primary capture",
    )
    run(
        [
            sys.executable,
            str(ORACLE),
            "--product-directory", str(STAGE),
        ],
        "class-6 orbital-primary oracle",
    )
    print("RESULT PASS - live class-6 orbital-primary suppression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
