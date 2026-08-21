"""Historical-x87 acceptance for the portable crater power helper.

The deep gate exhausts the independent integer operation mirror against x87;
the ordinary-Lino driver covers the pinned 4,096-case boundary corpus.
"""

from __future__ import annotations

import argparse
from decimal import Decimal, ROUND_HALF_EVEN, getcontext
import hashlib
from pathlib import Path
import shutil
import struct
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
HARNESS = HERE / "harness"
GEN = HERE / "gen" / "fractional-pow"
FP = ROOT / "work" / "fp"
IN_MAGIC = 0x46505049
OUT_MAGIC = 0x4650504F
LINO_IN_MAGIC = 0x46505056
LINO_OUT_MAGIC = 0x46505057
VERSION = 1
ORACLE_IN = struct.Struct("<5I")
ORACLE_OUT = struct.Struct("<6I")
LINO_OUT = struct.Struct("<8I")
MAX_LINO_CASES = 4096
EXPECTED_BASE_PARAMETER_COUNT = 586_183
EXPECTED_UNIQUE_BASE_COUNT = 490_424
EXPECTED_PAIR_COUNT = 9_564_210
# Filled from the deterministic parameter rules, not from generated results.
EXPECTED_ROUTINE_INPUT_SHA256 = "1e84ea9324e385321a3b97e5f6f4f0ebe2779cd0b714905949de534d6aaec831"
EXPECTED_DEEP_RESULT_SHA256 = "b3c1aef60b2f697211e33d21b9f1d3be7f2cbcb0003fa5bc88810a46708ea937"

sys.path.insert(0, str(HERE))
import linoharness as lh  # noqa: E402


def check(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"PASS {label}")


def radial_keys(radius: int) -> tuple[int, ...]:
    return tuple(sorted({
        x * x + z * z
        for x in range(-radius, radius + 1)
        for z in range(-radius, radius + 1)
        if x * x + z * z <= radius * radius
    }))


def domain_config(kind: int):
    if kind == 1:
        return range(5, 55), range(32), range(5, 25)
    if kind == 5:
        return range(5, 40), range(5), range(10, 20)
    raise ValueError(kind)


def base_parameters() -> list[tuple[int, int, int, int, int]]:
    rows: list[tuple[int, int, int, int, int]] = []
    for kind in (1, 5):
        radii, factors, exponents = domain_config(kind)
        witness_exponent = exponents.start
        for radius in radii:
            keys = radial_keys(radius)
            for factor in factors:
                rows.extend((kind, radius, factor, witness_exponent, d2)
                            for d2 in keys)
    return rows


def routine_parameters(
        bases: list[tuple[int, int, int, int, int]],
) -> list[tuple[int, int, int, int, int]]:
    selected: dict[tuple[int, int, int, int, int], None] = {}

    def add(row: tuple[int, int, int, int, int]) -> None:
        selected.setdefault(row, None)

    # The reachable d/r=1/2, radius=40, factor=0.20 profile has base exactly
    # 8.0. It exercises the helper's internal z=(m-1)/(m+1)=0 path for every
    # type-1 exponent instead of relying on the spread sampler to find it.
    for exponent in domain_config(1)[2]:
        add((1, 40, 20, exponent, 400))

    for kind in (1, 5):
        radii, factors, exponents = domain_config(kind)
        middle_radius = (radii.start + radii.stop - 1) // 2
        keys = radial_keys(middle_radius)
        near_rim = keys[-2]
        for exponent in exponents:
            add((kind, middle_radius, factors.stop - 1, exponent, 1))
            add((kind, middle_radius, factors.stop - 1, exponent, near_rim))
            add((kind, middle_radius, factors.stop - 1, exponent,
                 middle_radius * middle_radius))
        for factor in factors:
            add((kind, middle_radius, factor, exponents.start, 0))
            add((kind, middle_radius, factor, exponents.stop - 1, 1))
            add((kind, middle_radius, factor, exponents.start,
                 middle_radius * middle_radius))
        for radius in radii:
            radius_keys = radial_keys(radius)
            factor = factors.start + radius % len(factors)
            exponent = exponents.start + radius % len(exponents)
            add((kind, radius, factor, exponent, 0))
            add((kind, radius, factor, exponent, 1))
            add((kind, radius, factor, exponent, radius_keys[-2]))
            add((kind, radius, factor, exponent, radius * radius))

    remaining = MAX_LINO_CASES - len(selected)
    for index in range(remaining * 2):
        base_index = index * (len(bases) - 1) // max(1, remaining * 2 - 1)
        kind, radius, factor, _, d2 = bases[base_index]
        exponents = domain_config(kind)[2]
        exponent = exponents.start + (index * 7 + radius + factor) % len(exponents)
        add((kind, radius, factor, exponent, d2))
        if len(selected) == MAX_LINO_CASES:
            break
    if len(selected) != MAX_LINO_CASES:
        raise AssertionError(f"routine corpus has {len(selected)} records")
    return list(selected)


def write_oracle_input(path: Path, rows) -> None:
    with path.open("wb") as stream:
        stream.write(struct.pack("<4I", IN_MAGIC, VERSION, len(rows), 5))
        for row in rows:
            stream.write(ORACLE_IN.pack(*row))


def run_oracle(executable: Path, rows, stem: str):
    input_path = GEN / f"{stem}-in.bin"
    output_path = GEN / f"{stem}-out.bin"
    write_oracle_input(input_path, rows)
    subprocess.run(
        [str(executable), str(input_path), str(output_path)],
        cwd=GEN, check=True, timeout=600)
    raw = output_path.read_bytes()
    if len(raw) < 16:
        raise AssertionError("short oracle output")
    magic, version, count, units = struct.unpack_from("<4I", raw)
    if (magic, version, count, units) != (OUT_MAGIC, VERSION, len(rows), 6):
        raise AssertionError("wrong oracle output header")
    if len(raw) != 16 + count * ORACLE_OUT.size:
        raise AssertionError("wrong oracle output length")
    return [ORACLE_OUT.unpack_from(raw, 16 + index * ORACLE_OUT.size)
            for index in range(count)]


def compile_oracle() -> Path:
    source = HARNESS / "fp_pow_ref.c"
    executable = GEN / "fp_pow_ref.exe"
    executable.unlink(missing_ok=True)
    command = [
        "gcc", "-O2", "-Wall", "-Wextra", "-fno-fast-math",
        "-o", str(executable), str(source), "-lm",
    ]
    result = subprocess.run(command, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    check(result.returncode == 0 and executable.is_file(),
          "hardware x87 witness compiles without a power library call")

    source_text = source.read_text(encoding="utf-8").lower()
    check("pow(" not in source_text and "powf" not in source_text and
          "powl" not in source_text,
          "witness source contains no C power routine")
    disassembly = subprocess.run(
        ["objdump", "-d", str(executable)], capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=True).stdout.lower()
    check(all(name in disassembly for name in
              ("fyl2x", "frndint", "f2xm1", "fscale")),
          "built witness contains the historical x87 transcendental sequence")
    return executable


def build_lino_driver() -> Path:
    source = GEN / "fppowmain.txt"
    shutil.copy2(HARNESS / "fp_pow_main.txt", source)
    for name in ("fpabi", "fpctl", "fpsoft", "fpx87", "fpconv"):
        shutil.copy2(FP / f"{name}.txt", GEN / f"{name}.txt")
    executable = GEN / "fppowmain.exe"
    executable.unlink(missing_ok=True)
    rc, note = lh.build(str(source), timeout_sec=240)
    check(rc == 0 and executable.is_file(),
          "ordinary-Lino XPowPositive vector driver builds")
    if rc:
        raise AssertionError(note)
    return executable


def run_lino(executable: Path, oracle_rows) -> None:
    input_path = GEN / "fppow-in.bin"
    output_path = GEN / "fppow-out.bin"
    with input_path.open("wb") as stream:
        stream.write(struct.pack(
            "<4I", LINO_IN_MAGIC, VERSION, len(oracle_rows), 2))
        for base, exponent, _expected, _model, _top0, _top1 in oracle_rows:
            stream.write(struct.pack("<2I", base, exponent))
    output_path.unlink(missing_ok=True)
    subprocess.run([str(executable)], cwd=GEN, check=True, timeout=900)
    raw = output_path.read_bytes()
    header = struct.unpack_from("<4I", raw)
    check(header == (LINO_OUT_MAGIC, VERSION, len(oracle_rows), 8),
          "Lino power driver emits the exact output schema")
    check(len(raw) == 16 + len(oracle_rows) * LINO_OUT.size,
          "Lino power driver emits one complete record per input")

    failures = []
    for index, oracle in enumerate(oracle_rows):
        actual = LINO_OUT.unpack_from(raw, 16 + index * LINO_OUT.size)
        result, top0, top1, depth0, depth1, changed, rejected, marker = actual
        if (result != oracle[2] or top0 != top1 or depth0 != depth1 or
                changed or rejected or marker != 0xF00DCAFE):
            failures.append((index, oracle, actual))
    check(not failures,
          f"compiled Lino is x87-exact with intact soft stack ({len(oracle_rows)} cases)")
    if failures:
        raise AssertionError(repr(failures[:3]))


def decimal_extended(value: Decimal) -> tuple[int, int, int]:
    exponent = 0
    normalized = value
    two = Decimal(2)
    while normalized >= two:
        normalized /= two
        exponent += 1
    while normalized < 1:
        normalized *= two
        exponent -= 1
    mantissa = int((normalized * (two ** 63)).to_integral_value(
        rounding=ROUND_HALF_EVEN))
    if mantissa == 1 << 64:
        mantissa >>= 1
        exponent += 1
    return exponent + 16383, mantissa >> 32, mantissa & 0xFFFFFFFF


def check_constants_and_structure() -> None:
    getcontext().prec = 200
    two = Decimal(2)
    constants = {
        "sqrt2": (two.sqrt(), (0x3FFF, 0xB504F333, 0xF9DE6484)),
        "ln2": (two.ln(), (0x3FFE, 0xB17217F7, 0xD1CF79AC)),
        "two/ln2": (two / two.ln(), (0x4000, 0xB8AA3B29, 0x5C17F0BC)),
    }
    check(all(decimal_extended(value) == expected
              for value, expected in constants.values()),
          "power constants are nearest-even extended images")

    zmax = (two.sqrt() - 1) / (two.sqrt() + 1)
    log_remainder = (two * (zmax ** 31) /
                     (Decimal(31) * (1 - zmax * zmax)))
    rmax = two.ln() / 2
    factorial = 1
    for number in range(1, 22):
        factorial *= number
    exp_remainder = rmax.exp() * (rmax ** 21) / Decimal(factorial)
    check(log_remainder < two ** -75 and exp_remainder < two ** -90,
          "degree-29 log and degree-20 exp truncation bounds exceed extended precision")

    soft = (FP / "fpsoft.txt").read_text(encoding="utf-8")
    ground = (ROOT / "work" / "grnd.txt").read_text(encoding="utf-8")
    helper = soft.split('"XPowPositive"', 1)[1].split(
        "( ==================================================================== )", 1)[0]
    power_path = ground.split("( y = pow(y,h_raiser).", 1)[1].split(
        '"GR sc power done"', 1)[0]
    check("XPush" not in helper and "XPop" not in helper and
          "XToF32" not in helper and "XToF64" not in helper,
          "private power helper never touches the soft stack or spills")
    check(power_path.count("XPowPositive") == 1 and
          power_path.count("XToF32") == 1 and
          all(name not in power_path for name in
              ("FToIntChop", "XPush", "XPop", "XToF64", "{")),
          "crater call site has one final F32 spill and no native or integer-power path")


def unique_bases(executable: Path, rows):
    representatives: dict[tuple[int, int], tuple[int, int, int, int, int]] = {}
    chunk_size = 100_000
    for start in range(0, len(rows), chunk_size):
        chunk = rows[start:start + chunk_size]
        outputs = run_oracle(executable, chunk, "bases")
        for parameter, output in zip(chunk, outputs):
            base, _exponent, expected, model, top0, top1 = output
            if expected != model or top0 != top1:
                raise AssertionError((parameter, output))
            representatives.setdefault((parameter[0], base), parameter)
    return representatives


def deep_audit(executable: Path, representatives) -> None:
    digest = hashlib.sha256()
    count = 0
    chunk = []

    def grade(records) -> None:
        nonlocal count
        outputs = run_oracle(executable, records, "deep")
        for parameter, output in zip(records, outputs):
            base, exponent, expected, model, top0, top1 = output
            if expected != model or top0 != top1:
                raise AssertionError((parameter, output))
            digest.update(struct.pack(
                "<4I", parameter[0], base, exponent, expected))
            count += 1

    for key in sorted(representatives):
        parameter = representatives[key]
        exponents = domain_config(parameter[0])[2]
        for exponent in exponents:
            chunk.append((parameter[0], parameter[1], parameter[2],
                          exponent, parameter[4]))
            if len(chunk) == 100_000:
                grade(chunk)
                chunk = []
    if chunk:
        grade(chunk)
    actual_digest = digest.hexdigest()
    check(count == EXPECTED_PAIR_COUNT,
          f"deep operation-mirror audit covers all {EXPECTED_PAIR_COUNT:,} reachable pairs")
    check(actual_digest == EXPECTED_DEEP_RESULT_SHA256,
          f"deep reachable result digest is pinned ({actual_digest})")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--deep", action="store_true",
                        help="exhaust the operation mirror over all deduplicated reachable input pairs")
    args = parser.parse_args(argv)
    GEN.mkdir(parents=True, exist_ok=True)

    check_constants_and_structure()
    executable = compile_oracle()
    bases = base_parameters()
    check(len(bases) == EXPECTED_BASE_PARAMETER_COUNT,
          f"parameter rules enumerate {EXPECTED_BASE_PARAMETER_COUNT:,} pre-power bases")

    routine = routine_parameters(bases)
    routine_bytes = b"".join(ORACLE_IN.pack(*row) for row in routine)
    routine_digest = hashlib.sha256(routine_bytes).hexdigest()
    check(routine_digest == EXPECTED_ROUTINE_INPUT_SHA256,
          f"routine corpus input digest is pinned ({routine_digest})")
    oracle_rows = run_oracle(executable, routine, "routine")
    check(all(row[2] == row[3] and row[4] == row[5]
              for row in oracle_rows),
          "portable operation mirror matches x87 and x87 TOP is balanced")
    lino = build_lino_driver()
    run_lino(lino, oracle_rows)

    if args.deep:
        representatives = unique_bases(executable, bases)
        check(len(representatives) == EXPECTED_UNIQUE_BASE_COUNT,
              f"reachable domain deduplicates to {EXPECTED_UNIQUE_BASE_COUNT:,} bases")
        deep_audit(executable, representatives)
    else:
        print("NOTE deep 9,564,210-pair audit skipped; pass --deep for release acceptance")

    print("fractional crater power: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
