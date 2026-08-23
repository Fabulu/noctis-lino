#!/usr/bin/env python3
"""Run the L.in.oleum GUI compiler on a private Windows desktop."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
import time

from windows_hidden_process import PrivateDesktopProcess


FATAL_PATTERN = re.compile(rb"error:|internal problem:", re.IGNORECASE)


def file_state(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    return stat.st_size, stat.st_mtime_ns


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compiler", type=Path, required=True)
    parser.add_argument("--working-directory", type=Path, required=True)
    parser.add_argument("--timeout", type=float, required=True)
    parser.add_argument("--error-log", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, action="append", required=True)
    parser.add_argument("--argument", action="append", default=[])
    parser.add_argument("--poll-milliseconds", type=int, default=250)
    parser.add_argument("--settle-polls", type=int, default=5)
    args = parser.parse_args()

    if args.timeout < 0:
        parser.error("--timeout must be nonnegative")
    if args.poll_milliseconds <= 0:
        parser.error("--poll-milliseconds must be positive")
    if args.settle_polls <= 0:
        parser.error("--settle-polls must be positive")

    deadline = time.monotonic() + args.timeout
    previous_candidate: tuple[Path, tuple[int, int]] | None = None
    previous_log: tuple[int, int] | None = None
    stable_polls = 0
    natural_exit = False

    with PrivateDesktopProcess(
        args.compiler,
        args.working_directory,
        args.argument,
    ) as process:
        while time.monotonic() < deadline:
            try:
                if FATAL_PATTERN.search(args.error_log.read_bytes()):
                    return 1
            except FileNotFoundError:
                pass

            candidate = next(
                (
                    (path, state)
                    for path in args.candidate
                    if (state := file_state(path)) is not None and state[0] > 0
                ),
                None,
            )
            log_state = file_state(args.error_log)
            if candidate is not None:
                if candidate == previous_candidate and log_state == previous_log:
                    stable_polls += 1
                else:
                    stable_polls = 1
                previous_candidate = candidate
                previous_log = log_state
                if stable_polls >= args.settle_polls:
                    print(candidate[0].resolve())
                    return 0
            else:
                stable_polls = 0
                previous_candidate = None
                previous_log = None

            return_code = process.poll()
            if return_code is not None:
                natural_exit = True
                if return_code != 0 or candidate is None:
                    return 2

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(args.poll_milliseconds / 1000.0, remaining))

    return 2 if natural_exit else 3


if __name__ == "__main__":
    sys.exit(main())
