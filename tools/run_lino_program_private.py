#!/usr/bin/env python3
"""Run one compiled L.in.oleum test program on a private desktop."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys
import time

from windows_hidden_process import PrivateDesktopProcess


def fresh_size(path: Path, started_ns: int) -> int | None:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    if stat.st_mtime_ns <= started_ns:
        return None
    return stat.st_size


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--working-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, required=True)
    parser.add_argument("--expected-bytes", type=int, default=0)
    args = parser.parse_args()

    if args.timeout < 0:
        parser.error("--timeout must be nonnegative")
    if args.expected_bytes < 0:
        parser.error("--expected-bytes must be nonnegative")

    started_ns = time.time_ns()
    started = time.monotonic()
    # NTFS timestamps can be coarse. Keep stale output unambiguously older than
    # anything written by the process this invocation owns.
    time.sleep(1.1)
    deadline = time.monotonic() + args.timeout
    got = False
    size_error: str | None = None

    with PrivateDesktopProcess(args.executable, args.working_directory) as process:
        while time.monotonic() < deadline:
            time.sleep(min(0.5, max(0.0, deadline - time.monotonic())))
            size = fresh_size(args.output, started_ns)
            if size is not None:
                if args.expected_bytes and size > args.expected_bytes:
                    size_error = (
                        f"output grew to {size} bytes, "
                        f"expected {args.expected_bytes}"
                    )
                    break
                if not args.expected_bytes or size == args.expected_bytes:
                    time.sleep(0.5)
                    settled_size = fresh_size(args.output, started_ns)
                    if settled_size == size:
                        got = True
                        break
            if process.poll() is not None:
                # The final LastWriteTime update can become observable only as
                # the process closes its output handle. Re-stat after observing
                # exit so a completed write cannot lose the polling race above.
                size = fresh_size(args.output, started_ns)
                if size is not None:
                    if args.expected_bytes and size > args.expected_bytes:
                        size_error = (
                            f"output grew to {size} bytes, "
                            f"expected {args.expected_bytes}"
                        )
                    elif not args.expected_bytes or size == args.expected_bytes:
                        got = True
                break

    elapsed = round(time.monotonic() - started, 1)
    if got:
        data = args.output.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        print(
            f"RAN-OK {args.output} {len(data)} bytes {elapsed}s "
            f"sha256 {digest}"
        )
        return 0

    if size_error:
        print(f"RUN-FAIL {size_error}")
    elif args.expected_bytes:
        try:
            actual = args.output.stat().st_size
        except FileNotFoundError:
            actual = 0
        print(
            f"RUN-FAIL no complete {args.output} after {elapsed}s "
            f"({actual}/{args.expected_bytes} bytes)"
        )
    else:
        print(f"RUN-FAIL no fresh {args.output} after {elapsed}s")
    return 3


if __name__ == "__main__":
    sys.exit(main())
