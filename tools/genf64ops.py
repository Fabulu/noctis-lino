#!/usr/bin/env python3
"""Generate exact scalar binary64 records for x87 CPU packs.

The arithmetic operations accept a direct binary64 destination and an indirect
binary64 source::

    [destination] +: [A]

The conversion operations accept only their one exact shape: binary64-to-int32
and int32-to-binary64 use direct/direct operands, while binary32 narrowing is an
in-place direct unary operation.  Every x87 arithmetic result is spilled so the
backend reproduces the original p64-then-p53 schedule rather than substituting
SSE binary64 arithmetic.
"""

from __future__ import annotations

import argparse
from pathlib import Path


LINO_TO_X86 = (0, 3, 1, 2, 6)  # A, B, C, D, E -> eax, ebx, ecx, edx, esi
OPERATIONS = (
    ("+:", 0x84),
    ("-:", 0xA4),
    ("*:", 0x8C),
    ("/:", 0xB4),
)
CONVERSIONS = ("=:", ":=", "~:")
TERMINATOR = b"++"
I386_PADDING = b"\x87\xdb"  # xchg ebx, ebx
X64_PADDING = b"\x00"


def finish_record(body: bytearray, *, alignment: int, padding: bytes,
                  terminator: bytes) -> bytes:
    if not padding:
        raise ValueError("CPU-pack padding must not be empty")
    body.extend(terminator)
    remaining = alignment - len(body)
    if remaining < 0:
        raise ValueError(
            f"binary64 pattern is {len(body)} bytes, exceeds alignment {alignment}")
    repeats = (remaining + len(padding) - 1) // len(padding)
    body.extend((padding * repeats)[:remaining])
    if len(body) != alignment:
        raise AssertionError("binary64 CPU-pack record has the wrong size")
    return bytes(body)


def pattern(pointer_register: int, memory_operation: int, *, alignment: int,
            padding: bytes, terminator: bytes = TERMINATOR) -> bytes:
    """Return one direct-destination/indirect-source arithmetic record."""
    if not 0 <= pointer_register < len(LINO_TO_X86):
        raise ValueError(f"invalid L.in.oleum pointer register {pointer_register}")
    if memory_operation not in {operation for _, operation in OPERATIONS}:
        raise ValueError(f"invalid x87 memory operation 0x{memory_operation:02X}")

    source_sib = 0x80 + LINO_TO_X86[pointer_register] * 8 + 7
    body = bytearray((0xDD, 0x87))       # fld qword [edi + D1]
    body.extend(b"D1.4")
    body.extend((0xDC, memory_operation, source_sib))
    body.extend(b"D2.4")                # op qword [edi + reg*4 + D2]
    body.extend((0xDD, 0x9F))            # fstp qword [edi + D1]
    body.extend(b"D1.4")
    return finish_record(body, alignment=alignment, padding=padding,
                         terminator=terminator)


def conversion_pattern(symbol: str, *, alignment: int, padding: bytes,
                       terminator: bytes = TERMINATOR) -> bytes:
    """Return one direct conversion or in-place narrowing record."""
    if symbol not in CONVERSIONS:
        raise ValueError(f"invalid exact conversion operation {symbol!r}")

    if symbol == "=:":                  # int32 destination <- binary64 source
        body = bytearray((0xDD, 0x87))   # fld qword [edi + D2]
        body.extend(b"D2.4")
        body.extend((0xDB, 0x9F))        # fistp dword [edi + D1]
        body.extend(b"D1.4")
    elif symbol == ":=":                # binary64 destination <- int32 source
        body = bytearray((0xDB, 0x87))   # fild dword [edi + D2]
        body.extend(b"D2.4")
        body.extend((0xDD, 0x9F))        # fstp qword [edi + D1]
        body.extend(b"D1.4")
    else:                                # binary64 <- (double)(float)binary64
        body = bytearray((0xDD, 0x87))   # fld qword [edi + D1]
        body.extend(b"D1.4")
        body.extend((0xD9, 0x9F))        # fstp dword [edi + D1]
        body.extend(b"D1.4")
        body.extend((0xD9, 0x87))        # fld dword [edi + D1]
        body.extend(b"D1.4")
        body.extend((0xDD, 0x9F))        # fstp qword [edi + D1]
        body.extend(b"D1.4")
    return finish_record(body, alignment=alignment, padding=padding,
                         terminator=terminator)


def enumerate_block(*, alignment: int, padding: bytes,
                    terminator: bytes = TERMINATOR) -> list[bytes]:
    """Return arithmetic then conversions in quick-reference order."""
    records = [
        pattern(register, operation, alignment=alignment, padding=padding,
                terminator=terminator)
        for _symbol, operation in OPERATIONS
        for register in range(len(LINO_TO_X86))
    ]
    records.extend(
        conversion_pattern(symbol, alignment=alignment, padding=padding,
                           terminator=terminator)
        for symbol in CONVERSIONS
    )
    if len(records) != 23 or len(set(records)) != 23:
        raise AssertionError("binary64 CPU-pack block must contain 23 unique records")
    return records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--backend", choices=("i386", "x64"), default="i386")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.backend == "i386":
        alignment, padding = 48, I386_PADDING
    else:
        alignment, padding = 145, X64_PADDING
    records = enumerate_block(alignment=alignment, padding=padding)
    args.output.write_bytes(b"".join(records))
    print(
        f"wrote {len(records)} exact binary64 records "
        f"({len(records) * alignment} bytes) to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
