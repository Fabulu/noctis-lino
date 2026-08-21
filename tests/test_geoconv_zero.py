"""Ordinary-Lino regression for zero numerators in geometry divisions."""

from __future__ import annotations

from pathlib import Path
import shutil
import struct
import sys


ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
HARNESS = HERE / "harness"
GEN = HERE / "gen" / "geoconv-zero"
FP = ROOT / "work" / "fp"
RECORD = struct.Struct("<8I")
OUT_MAGIC = 0x475A4552

sys.path.insert(0, str(HERE))
import linoharness as lh  # noqa: E402


def main() -> int:
    checks = lh.Check("geometry zero quotients")
    GEN.mkdir(parents=True, exist_ok=True)
    source = GEN / "geozero.txt"
    shutil.copy2(HARNESS / "geoconv_zero_main.txt", source)
    for name in ("fpabi", "fpctl", "fpsoft", "fpx87", "fpconv"):
        shutil.copy2(FP / f"{name}.txt", GEN / f"{name}.txt")
    shutil.copy2(ROOT / "work" / "geoconv.txt", GEN / "geoconv.txt")

    output = GEN / "geozero-out.bin"
    blob, _executable, note = lh.build_and_run(str(source), str(output))
    checks.ok(blob is not None, "focused geometry quotient driver builds and runs",
              note)
    if blob is None:
        return checks.done()

    checks.eq(len(blob), 16 + 4 * RECORD.size,
              "geometry quotient driver emits four complete records")
    if len(blob) != 16 + 4 * RECORD.size:
        return checks.done()
    header = struct.unpack_from("<4I", blob)
    checks.eq(header, (OUT_MAGIC, 1, 4, 8),
              "geometry quotient driver emits the exact output schema")

    expected = (
        (1, 0, 0, 0x40180000, 0, 0, 0, 0x133F),
        (1, 25, 0, 0x40190000, 0, 0, 0, 0x133F),
        (2, 0, 0, 0x3FF00000, 5, 3, 0, 0x133F),
        (2, 500, 0, 0x3FE80000, 2, 6, 0, 0x133F),
    )
    actual = tuple(RECORD.unpack_from(blob, 16 + index * RECORD.size)
                   for index in range(4))
    labels = (
        "GeoSeedStore100 maps a zero numerator to exactly FC*FB",
        "GeoSeedStore100 retains a representative nonzero quotient",
        "GeoEccStore2000 maps a zero numerator to exactly binary64 one",
        "GeoEccStore2000 retains a representative nonzero quotient",
    )
    for got, want, label in zip(actual, expected, labels):
        checks.eq(got, want, label)

    source_text = (ROOT / "work" / "geoconv.txt").read_text(encoding="utf-8")
    for routine in ("GeoSeedStore100", "GeoEccStore2000"):
        body = source_text.split(f'"{routine}"', 1)[1].split("\n\tend;", 1)[0]
        checks.ok("? [FI] = 0" in body,
                  f"{routine} bypasses the normalized-only quotient core for zero")

    return checks.done()


if __name__ == "__main__":
    raise SystemExit(main())
