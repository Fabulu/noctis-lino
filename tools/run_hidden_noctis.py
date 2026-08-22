"""Run Noctis until its diagnostic sentinel exits."""

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
    parser.add_argument("--default-desktop", action="store_true")
    parser.add_argument("argument", nargs="*")
    args = parser.parse_args()

    try:
        if args.default_desktop:
            result = subprocess.run(
                [str(args.executable.resolve()), *args.argument],
                cwd=args.working_directory.resolve(),
                timeout=args.timeout,
                check=False,
            )
        else:
            result = windows_hidden_process.run(
                args.executable,
                args.working_directory,
                args.timeout,
                args.argument,
            )
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f"Noctis diagnostic run failed: {error}")
        return 1
    if result.returncode:
        print(
            "Noctis diagnostic run exited with code "
            f"0x{result.returncode & 0xFFFFFFFF:08X}"
        )
        return 1
    print("Noctis sentinel run exited cleanly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
