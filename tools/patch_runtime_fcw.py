#!/usr/bin/env python3
"""Install the fixed x87 control word in one compiled Win32 Lino image.

The upstream L.in.oleum runtime under main/ is licence-protected and remains
byte-for-byte pristine.  The compiler copies one of its eight runtime variants
into each output PE.  This post-link step changes only that selected copy,
replacing the inherited-control-word/chop sequence with the reviewed fixed
FCWEXT load while preserving the executable size.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


OLD_CONTROL = bytes.fromhex("66 25 FF F3 66 0D 00 0C")
FIXED_CONTROL = bytes.fromhex("66 B8 3F 13 66 90 66 90")


def patch_image(data: bytes) -> bytes:
    old_count = data.count(OLD_CONTROL)
    fixed_count = data.count(FIXED_CONTROL)
    if old_count != 1 or fixed_count != 0:
        raise ValueError(
            "expected exactly one unpatched runtime control sequence; "
            f"found old={old_count}, fixed={fixed_count}")
    patched = data.replace(OLD_CONTROL, FIXED_CONTROL, 1)
    if len(patched) != len(data):
        raise AssertionError("runtime patch changed executable size")
    return patched


def patch_file(path: Path) -> None:
    original = path.read_bytes()
    patched = patch_image(original)
    temporary = path.with_name(path.name + ".fcwtmp")
    try:
        temporary.write_bytes(patched)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    args = parser.parse_args(argv)
    try:
        patch_file(args.image)
    except (OSError, ValueError, AssertionError) as error:
        print(f"patch_runtime_fcw: {error}", file=sys.stderr)
        return 1
    print(f"patched FCWEXT runtime boundary: {args.image}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
