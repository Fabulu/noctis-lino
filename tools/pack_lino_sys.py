#!/usr/bin/env python3
"""Pack one L.in.oleum RTM into the eight-variant SYS container."""

from __future__ import annotations

import argparse
from pathlib import Path
import struct


VARIANTS = 8
HEADER_WORDS = 1 + VARIANTS + VARIANTS


def pack(runtime: bytes) -> bytes:
    if not runtime:
        raise ValueError("runtime is empty")
    offsets = [index * len(runtime) for index in range(VARIANTS)]
    sizes = [len(runtime)] * VARIANTS
    header = struct.pack(f"<{HEADER_WORDS}I", VARIANTS, *offsets, *sizes)
    return header + runtime * VARIANTS


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runtime", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    runtime = args.runtime.read_bytes()
    payload = pack(runtime)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    print(f"packed {len(runtime)}-byte RTM into {args.output} ({len(payload)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
