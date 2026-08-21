"""Production ground-prologue regression for zero tree random quotients."""

from __future__ import annotations

from pathlib import Path
import shutil
import struct
import sys


ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
HARNESS = HERE / "harness"
GEN = HERE / "gen" / "grnd-zero"
WORK = ROOT / "work"
FP = WORK / "fp"
RECORD = struct.Struct("<9I")
OUT_MAGIC = 0x475A4552
MARKER = 0x0475A001

sys.path.insert(0, str(HERE))
import linoharness as lh  # noqa: E402


def main() -> int:
    checks = lh.Check("ground tree zero quotients")
    GEN.mkdir(parents=True, exist_ok=True)
    source = GEN / "grzero.txt"
    shutil.copy2(HARNESS / "grnd_zero_main.txt", source)
    for name in ("fpabi", "fpctl", "fpsoft", "fpx87", "fpconv"):
        shutil.copy2(FP / f"{name}.txt", GEN / f"{name}.txt")
    for name in ("fbmem", "brtl", "mul64frag", "surng", "suseed", "grnd"):
        shutil.copy2(WORK / f"{name}.txt", GEN / f"{name}.txt")

    output = GEN / "grzero-out.bin"
    blob, _executable, note = lh.build_and_run(str(source), str(output))
    checks.ok(blob is not None, "focused ground quotient driver builds and runs",
              note)
    if blob is None:
        return checks.done()

    checks.eq(len(blob), 16 + 2 * RECORD.size,
              "ground quotient driver emits two complete records")
    if len(blob) != 16 + 2 * RECORD.size:
        return checks.done()
    header = struct.unpack_from("<4I", blob)
    checks.eq(header, (OUT_MAGIC, 1, 2, 9),
              "ground quotient driver emits the exact output schema")

    expected = (
        (22022, 0x453B7FFE, 1840, 5, 3, 0, 0x133F, 12, MARKER),
        (5963, 0x453B8001, 5861, 2, 6, 0, 0x133F, 24, MARKER),
    )
    actual = tuple(RECORD.unpack_from(blob, 16 + index * RECORD.size)
                   for index in range(2))
    labels = (
        "zero first tree draw retains the historical scale and FP state",
        "zero second tree draw retains the historical scale and FP state",
    )
    for got, want, label in zip(actual, expected, labels):
        checks.eq(got, want, label)

    source_text = (WORK / "grnd.txt").read_text(encoding="utf-8")
    prologue = source_text.split('"GR prologue"', 1)[1].split(
        '\n\t"GR prol done"', 1)[0]
    zero_guard = "A = [GRtreefl]; A & 7FFFFFFFh; ? A = 0 -> GR tree quotient"
    checks.eq(prologue.count(zero_guard), 2,
              "both tree schedules bypass the normalized-only quotient core for zero")

    return checks.done()


if __name__ == "__main__":
    raise SystemExit(main())
