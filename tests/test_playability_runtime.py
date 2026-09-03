#!/usr/bin/env python3
"""Run the retained Noctis product-playability acceptance phases."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from playtest_noctis_acceptance import (  # noqa: E402
    DEFAULT_EXECUTABLE,
    OUTPUT_ROOT,
    run_phase,
)


PHASES = ("menus", "journey", "guide")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=PHASES, action="append")
    parser.add_argument("--executable", type=Path, default=DEFAULT_EXECUTABLE)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if os.name != "nt":
        print("SKIP Noctis playability runtime requires Windows")
        return 0
    executable = args.executable.resolve()
    if not executable.is_file():
        parser.error(f"missing executable: {executable}")
    phases = tuple(dict.fromkeys(args.phase or PHASES))
    results = [
        run_phase(phase, executable, args.output_root.resolve(), force=args.force)
        for phase in phases
    ]
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
