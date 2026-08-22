"""Run Noctis on a private Windows desktop until its sentinel exits."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

import windows_hidden_process


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--working-directory", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("argument", nargs="*")
    args = parser.parse_args()

    try:
        result = windows_hidden_process.run(
            args.executable,
            args.working_directory,
            args.timeout,
            args.argument,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f"private Noctis run failed: {error}")
        return 1
    if result.returncode:
        print(f"private Noctis run exited with code 0x{result.returncode:08X}")
        return 1
    print("private Noctis sentinel run exited cleanly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
