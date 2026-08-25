"""Build the extended i386m and x64 CPU packs.

The protected 6,241-record i386 pack is never modified.  i386m appends the two
121-record split-multiply blocks and the 23-record exact scalar binary64 block::

    6241 existing + 121 unsigned + 121 signed + 23 binary64 = 6506 records
    48 * 6506 + 8 = 312,296 bytes

The checked-in x64 pack already contains the same first 6,483 instruction
patterns at its 145-byte alignment.  Its first 6,483 records are retained
byte-for-byte and the same 23 x87 records are appended, yielding::

    145 * 6506 + 8 = 943,378 bytes

Outputs are written under tools/ for review.  Nothing under main/cpu/ is
modified by this script.
"""

from pathlib import Path

from genf64ops import I386_PADDING, X64_PADDING, enumerate_block
import genmul
from packtool import Pack, decode, encode


ROOT = Path(__file__).resolve().parents[1]
CPU_DIR = ROOT / "main" / "cpu"
OUTPUT_DIR = ROOT / "tools"
BASE_RECORDS = 6241
MULTIPLY_RECORDS = 6483
ARITHMETIC_RECORDS = 6503
FINAL_RECORDS = 6506


def validate_pack(blob: bytes, *, alignment: int, count: int, label: str) -> Pack:
    pack = Pack(blob)
    if (pack.align, pack.ter, pack.count) != (alignment, b"++", count):
        raise SystemExit(
            f"unexpected {label} layout: alignment={pack.align}, "
            f"terminator={pack.ter!r}, count={pack.count}")
    for index in range(pack.count):
        raw = pack.raw(index)
        try:
            items, padding = decode(raw, pack.ter)
        except ValueError as exc:
            raise SystemExit(f"{label} record {index}: {exc}") from exc
        if encode(items, padding, pack.ter) != raw:
            raise SystemExit(f"{label} record {index}: decode/encode mismatch")
    return pack


def f64_block(pack: Pack, padding: bytes) -> bytes:
    return b"".join(enumerate_block(
        alignment=pack.align,
        padding=padding,
        terminator=pack.ter,
    ))


def build_i386m() -> bytes:
    stock_blob = (CPU_DIR / "i386.bin").read_bytes()
    stock = validate_pack(
        stock_blob, alignment=48, count=BASE_RECORDS, label="protected i386 pack")

    unsigned = [genmul.emit(row[4]) for row in genmul.enumerate_block(False)]
    signed = [genmul.emit(row[4]) for row in genmul.enumerate_block(True)]
    if len(unsigned) != 121 or len(signed) != 121:
        raise SystemExit("split-multiply generator did not produce 121 + 121 records")

    extended_blob = stock_blob + b"".join(unsigned + signed)
    extended = validate_pack(
        extended_blob, alignment=48, count=MULTIPLY_RECORDS,
        label="intermediate i386m pack")
    final_blob = extended_blob + f64_block(extended, I386_PADDING)
    validate_pack(
        final_blob, alignment=48, count=FINAL_RECORDS, label="final i386m pack")

    if final_blob[:len(stock_blob)] != stock_blob:
        raise SystemExit("protected i386 prefix changed")
    return final_blob


def build_x64() -> bytes:
    installed_blob = (CPU_DIR / "x64.bin").read_bytes()
    installed = Pack(installed_blob)
    if (installed.align, installed.ter) != (145, b"++"):
        raise SystemExit(
            "unexpected x64 pack layout: "
            f"alignment={installed.align}, terminator={installed.ter!r}")
    if installed.count not in (
            MULTIPLY_RECORDS, ARITHMETIC_RECORDS, FINAL_RECORDS):
        raise SystemExit(
            f"unexpected x64 record count {installed.count}; expected "
            f"{MULTIPLY_RECORDS}, {ARITHMETIC_RECORDS}, or {FINAL_RECORDS}")

    prefix_size = 8 + MULTIPLY_RECORDS * installed.align
    prefix_blob = installed_blob[:prefix_size]
    prefix = validate_pack(
        prefix_blob, alignment=145, count=MULTIPLY_RECORDS, label="x64 prefix")
    suffix = f64_block(prefix, X64_PADDING)
    if installed.count == ARITHMETIC_RECORDS:
        arithmetic_size = (ARITHMETIC_RECORDS - MULTIPLY_RECORDS) * installed.align
        if installed_blob[prefix_size:] != suffix[:arithmetic_size]:
            raise SystemExit("installed x64 arithmetic suffix is not generator-exact")
    elif installed.count == FINAL_RECORDS and installed_blob[prefix_size:] != suffix:
        raise SystemExit("installed x64 binary64 suffix is not generator-exact")

    final_blob = prefix_blob + suffix
    validate_pack(
        final_blob, alignment=145, count=FINAL_RECORDS, label="final x64 pack")
    if final_blob[:prefix_size] != prefix_blob:
        raise SystemExit("x64 6,483-record prefix changed")
    return final_blob


def main() -> None:
    outputs = (
        (OUTPUT_DIR / "i386m.bin", build_i386m()),
        (OUTPUT_DIR / "x64.bin", build_x64()),
    )
    for path, blob in outputs:
        path.write_bytes(blob)
        pack = Pack(blob)
        print(
            f"wrote {path}: {pack.count} records, {len(blob)} bytes "
            f"({pack.align} * {pack.count} + 8)")
    print("main/cpu/i386.bin, i386m.bin and x64.bin were not touched")


if __name__ == "__main__":
    main()
