"""Ordinary-Lino regression for zero numerators in surface contrast divisions."""

from __future__ import annotations

from pathlib import Path
import shutil
import struct
import sys


ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
HARNESS = HERE / "harness"
GEN = HERE / "gen" / "suseed-zero"
FP = ROOT / "work" / "fp"
RECORD = struct.Struct("<8I")
OUT_MAGIC = 0x535A4552
MARKER = 0x51A7E001

sys.path.insert(0, str(HERE))
import linoharness as lh  # noqa: E402


def main() -> int:
    checks = lh.Check("surface zero quotients")
    GEN.mkdir(parents=True, exist_ok=True)
    source = GEN / "suzero.txt"
    shutil.copy2(HARNESS / "suseed_zero_main.txt", source)
    for name in ("fpabi", "fpctl", "fpsoft", "fpx87", "fpconv"):
        shutil.copy2(FP / f"{name}.txt", GEN / f"{name}.txt")
    shutil.copy2(ROOT / "work" / "suseed.txt", GEN / "suseed.txt")

    output = GEN / "suzero-out.bin"
    blob, _executable, note = lh.build_and_run(str(source), str(output))
    checks.ok(blob is not None, "focused surface quotient driver builds and runs",
              note)
    if blob is None:
        return checks.done()

    checks.eq(len(blob), 16 + 4 * RECORD.size,
              "surface quotient driver emits four complete records")
    if len(blob) != 16 + 4 * RECORD.size:
        return checks.done()
    header = struct.unpack_from("<4I", blob)
    checks.eq(header, (OUT_MAGIC, 1, 4, 8),
              "surface quotient driver emits the exact output schema")

    expected = (
        (1, 0, 0x3F19999A, 5, 3, 0, 0x133F, MARKER),
        (1, 900, 0x3FCCCCCD, 2, 6, 0, 0x133F, MARKER),
        (2, 0, 0x40800000, 7, 1, 0, 0x133F, MARKER),
        (2, 100, 0x40A00000, 4, 7, 0, 0x133F, MARKER),
    )
    actual = tuple(RECORD.unpack_from(blob, 16 + index * RECORD.size)
                   for index in range(4))
    labels = (
        "SU kt of maps a zero random result to binary32 0.6",
        "SU kt of retains a representative nonzero quotient",
        "SU kq of maps a zero random result to binary32 4.0",
        "SU kq of retains a representative nonzero quotient",
    )
    for got, want, label in zip(actual, expected, labels):
        checks.eq(got, want, label)

    source_text = (ROOT / "work" / "suseed.txt").read_text(encoding="utf-8")
    for routine in ("SU kt of", "SU kq of"):
        body = source_text.split(f'"{routine}"', 1)[1].split("\n\tend;", 1)[0]
        checks.ok("? [SUia] = 0" in body,
                  f"{routine} bypasses the normalized-only quotient core for zero")

    return checks.done()


if __name__ == "__main__":
    raise SystemExit(main())
