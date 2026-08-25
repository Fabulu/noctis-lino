#!/usr/bin/env python3
"""Repair and audit x64 CPU-pack branches that restore flags incorrectly.

The x64 pack replaces each unavailable 32-bit ``pop`` with a load followed by
``add rsp, 4``.  Floating branches restore one to three saved registers after
``sahf``; those ADDs overwrite the x87 comparison flags before the Jcc.  Use an
equivalent LEA cleanup, which does not change flags, in all 792 floating-branch
records.

Usage:
    python tools/fix_x64_pack_flags.py [pack]
    python tools/fix_x64_pack_flags.py --write [pack]

Without --write, the command audits an already repaired pack.  With --write,
it deterministically repairs the historical broken pack in place and then
re-audits it.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from genf64ops import X64_PADDING, enumerate_block
from packtool import Pack, decode, encode


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACK = ROOT / "main" / "cpu" / "x64.bin"
FIRST_FLOAT_BRANCH = 4819
LAST_FLOAT_BRANCH = 5610
EXPECTED_RECORDS = LAST_FLOAT_BRANCH - FIRST_FLOAT_BRANCH + 1
EXPECTED_CLEANUPS = 1236
EXPECTED_PACK_RECORDS = 6510
BINARY64_RECORDS = 27
OLD_CLEANUP = [
    ("op", 0x48), ("op", 0x83), ("op", 0xC4), ("op", 0x04),
]
NEW_CLEANUP = [
    ("op", 0x48), ("op", 0x8D), ("op", 0x64), ("op", 0x24),
    ("op", 0x04),
]


def sequence_count(items: list[tuple[str, int | str]], sequence: list[tuple[str, int]]) -> int:
    width = len(sequence)
    return sum(items[index:index + width] == sequence
               for index in range(len(items) - width + 1))


def branch_window(items: list[tuple[str, int | str]], index: int) -> tuple[int, int]:
    sahf = [position for position, item in enumerate(items)
            if item == ("op", 0x9E)]
    if len(sahf) != 1:
        raise ValueError(f"record {index}: expected one SAHF, found {len(sahf)}")
    branches = [position for position in range(sahf[0] + 1, len(items) - 1)
                if (items[position] == ("op", 0x0F)
                    and items[position + 1][0] == "op"
                    and 0x80 <= int(items[position + 1][1]) <= 0x8F)]
    if len(branches) != 1:
        raise ValueError(
            f"record {index}: expected one near Jcc after SAHF, found {len(branches)}")
    return sahf[0] + 1, branches[0]


def replace_cleanup(items: list[tuple[str, int | str]], start: int, stop: int) -> tuple[list[tuple[str, int | str]], int]:
    result = items[:start]
    index = start
    replacements = 0
    while index < stop:
        if items[index:index + len(OLD_CLEANUP)] == OLD_CLEANUP:
            result.extend(NEW_CLEANUP)
            index += len(OLD_CLEANUP)
            replacements += 1
        else:
            result.append(items[index])
            index += 1
    result.extend(items[stop:])
    return result, replacements


def transform(blob: bytes) -> tuple[bytes, int]:
    pack = Pack(blob)
    if (pack.align, pack.ter, pack.count) != (
            145, b"++", EXPECTED_PACK_RECORDS):
        raise ValueError(
            "unexpected x64 pack layout: "
            f"alignment={pack.align}, terminator={pack.ter!r}, count={pack.count}")

    binary64_suffix = b"".join(enumerate_block(
        alignment=pack.align, padding=X64_PADDING, terminator=pack.ter))
    if len(binary64_suffix) != BINARY64_RECORDS * pack.align:
        raise ValueError("binary64 suffix record coverage mismatch")
    if blob[-len(binary64_suffix):] != binary64_suffix:
        raise ValueError("x64 binary64 suffix is not generator-exact")

    records = []
    repaired = 0
    audited_cleanups = 0
    for index in range(pack.count):
        items, padding = decode(pack.raw(index), pack.ter)
        if FIRST_FLOAT_BRANCH <= index <= LAST_FLOAT_BRANCH:
            start, stop = branch_window(items, index)
            old_count = sequence_count(items[start:stop], OLD_CLEANUP)
            new_count = sequence_count(items[start:stop], NEW_CLEANUP)
            if old_count and new_count:
                raise ValueError(f"record {index}: mixed broken and repaired cleanups")
            if old_count:
                items, changed = replace_cleanup(items, start, stop)
                if changed != old_count:
                    raise ValueError(f"record {index}: cleanup replacement mismatch")
                if len(padding) < changed:
                    raise ValueError(f"record {index}: insufficient record padding")
                padding = padding[changed:]
                repaired += changed
                new_count = changed
            if not 1 <= new_count <= 3:
                raise ValueError(
                    f"record {index}: expected 1..3 flag-preserving cleanups, "
                    f"found {new_count}")
            audited_cleanups += new_count
        record = encode(items, padding, pack.ter)
        if len(record) != pack.align:
            raise ValueError(
                f"record {index}: rebuilt size {len(record)}, expected {pack.align}")
        records.append(record)

    if len(records) != pack.count or EXPECTED_RECORDS != 792:
        raise ValueError("floating-branch record coverage mismatch")
    if audited_cleanups != EXPECTED_CLEANUPS:
        raise ValueError(
            f"expected {EXPECTED_CLEANUPS} repaired cleanups, found {audited_cleanups}")
    fixed = blob[:8] + b"".join(records)
    if len(fixed) != len(blob):
        raise ValueError(f"pack size changed from {len(blob)} to {len(fixed)}")
    if fixed[-len(binary64_suffix):] != binary64_suffix:
        raise ValueError("x64 binary64 suffix changed during branch audit")
    return fixed, repaired


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pack", nargs="?", type=Path, default=DEFAULT_PACK)
    parser.add_argument(
        "--write", action="store_true",
        help="repair the pack in place before auditing it")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    path = args.pack.resolve()
    original = path.read_bytes()
    fixed, repaired = transform(original)
    if repaired:
        if not args.write:
            print(
                f"{path}: BROKEN: {repaired} ADD cleanups overwrite floating "
                "comparison flags; rerun with --write",
                file=sys.stderr,
            )
            return 1
        path.write_bytes(fixed)
        reread, remaining = transform(path.read_bytes())
        if remaining or reread != path.read_bytes():
            raise RuntimeError("written x64 pack failed its post-write audit")
        print(f"{path}: repaired {repaired} flag-clobbering stack cleanups")
    else:
        if fixed != original:
            raise RuntimeError("audit unexpectedly changed an already repaired pack")
        print(
            f"{path}: PASS: {EXPECTED_RECORDS} floating-branch records use "
            f"{EXPECTED_CLEANUPS} flag-preserving LEA cleanups")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
