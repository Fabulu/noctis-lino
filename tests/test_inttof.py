"""Bit-exact boundary regression for the guarded native IntToF path."""

from __future__ import annotations

from pathlib import Path
import shutil
import struct
import sys


ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
HARNESS = HERE / "harness"
GEN = HERE / "gen" / "inttof"
FP = ROOT / "work" / "fp"
VECTORS = (
    -2147483648,
    2147483647,
    -16777217,
    -16777216,
    -16777215,
    -1,
    0,
    1,
    16777215,
    16777216,
    16777217,
)
FS0_SENTINEL = 0x7FC12345
CPUS = ("i386m", "x64")

sys.path.insert(0, str(HERE))
import linoharness as lh  # noqa: E402


def double_units(value: int) -> tuple[int, int]:
    return struct.unpack("<II", struct.pack("<d", float(value)))


def main() -> int:
    checks = lh.Check("guarded native IntToF")
    for cpu in CPUS:
        backend = GEN / cpu
        backend.mkdir(parents=True, exist_ok=True)
        source = backend / "inttof.txt"
        shutil.copy2(HARNESS / "inttof_main.txt", source)
        for name in ("fpabi", "fpctl", "fpconv"):
            shutil.copy2(FP / f"{name}.txt", backend / f"{name}.txt")

        output = backend / "inttof-out.bin"
        blob, _executable, note = lh.build_and_run(
            str(source), str(output), cpu=cpu)
        checks.ok(blob is not None, f"{cpu} boundary probe builds and runs", note)
        if blob is None:
            continue

        checks.eq(len(blob), len(VECTORS) * 12,
                  f"{cpu} emits one double image and FS0 image per vector")
        if len(blob) != len(VECTORS) * 12:
            continue

        records = struct.iter_unpack("<III", blob)
        for value, (low, high, fs0) in zip(VECTORS, records):
            checks.eq((low, high), double_units(value),
                      f"{cpu} IntToF({value}) is the exact binary64 integer")
            checks.eq(fs0, FS0_SENTINEL,
                      f"{cpu} IntToF({value}) preserves the private F32 carrier")

    implementation = (FP / "fpconv.txt").read_text(encoding="utf-8")
    checks.ok(
        "? A > 16777216 -> IntToF exact;" in implementation
        and "? A < C -> IntToF exact;" in implementation
        and "[CVTMP] = [FS0]; [FS0] ,= [FI]; => CV F32 to F64;" in implementation
        and '"IntToF exact"\n\t=> CV int to F64;' in implementation,
        "production keeps inclusive native bounds, FS0 preservation, and exact fallback",
    )

    return checks.done()


if __name__ == "__main__":
    raise SystemExit(main())
