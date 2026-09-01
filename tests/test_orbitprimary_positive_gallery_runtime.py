#!/usr/bin/env python3
"""Grade the live Lino renderer's positive orbital-primary class gallery."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys

from test_orbitprimary_positive_gallery import CASES


ROOT = Path(__file__).resolve().parents[1]
EXECUTABLE = ROOT / "work" / "vhgame.exe"
CAPTURE = ROOT / "tools" / "capture_noctis_scenes.ps1"
ORACLE = ROOT / "tests" / "test_orbitprimary_positive_gallery.py"
STAGE_ROOT = ROOT / "build" / "orbitprimary-positive-gallery-runtime"
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
        print("SKIP positive orbital-primary runtime gallery requires Windows")
        return 0
    if not EXECUTABLE.is_file():
        raise FileNotFoundError(f"missing compiled game: {EXECUTABLE}")
    if not CAPTURE.is_file() or not ORACLE.is_file():
        raise FileNotFoundError("missing positive orbital capture or oracle script")

    if STAGE_ROOT.exists():
        shutil.rmtree(STAGE_ROOT)

    for index, (slug, case) in enumerate(CASES.items(), 1):
        output = STAGE_ROOT / slug
        print(f"=== positive orbital primary {index}/6: {slug} ===")
        run(
            [
                "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(CAPTURE),
                "-GameExecutable", str(EXECUTABLE),
                "-Scene", str(case["scene"]),
                "-DiagnosticOnly",
                "-OutputDirectory", str(output),
            ],
            f"{slug} capture",
        )
        run(
            [
                sys.executable,
                str(ORACLE),
                "--case", slug,
                "--product-directory", str(output),
            ],
            f"{slug} oracle",
        )

    print("RESULT PASS - live positive orbital-primary class gallery")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
