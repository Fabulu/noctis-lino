#!/usr/bin/env python3
"""Capture a hosted Windows startup exception with CDB on a private desktop."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from windows_hidden_process import PrivateDesktopProcess  # noqa: E402


CDB_COMMANDS = """\
.echo NOCTIS_CDB_INITIAL_BREAK
g
.echo NOCTIS_CDB_EXCEPTION
.exr -1
.ecxr
r
kv
ln @eip
u @eip-20 @eip+20
lm
!address @eip
.dump /ma "{dump}"
q
"""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def capture(cdb: Path, package: Path, output: Path, timeout: float) -> Path:
    if os.name != "nt":
        raise OSError("the CDB startup diagnostic requires Windows")
    cdb = cdb.resolve()
    package = package.resolve()
    output = output.resolve()
    require(cdb.is_file(), f"missing x86 CDB executable: {cdb}")
    require(package.is_dir(), f"missing package directory: {package}")
    require((package / "Noctis-IV.exe").is_file(), "package lacks Noctis-IV.exe")

    output.mkdir(parents=True, exist_ok=True)
    diagnostic_package = output / "package"
    require(not diagnostic_package.exists(),
            f"diagnostic package already exists: {diagnostic_package}")
    shutil.copytree(package, diagnostic_package)
    commands = output / "cdb-commands.txt"
    log = output / "cdb-startup.txt"
    dump = output / "cdb-startup.dmp"
    commands.write_text(
        CDB_COMMANDS.format(dump=dump), encoding="ascii", newline="\r\n"
    )

    target = diagnostic_package / "Noctis-IV.exe"
    with PrivateDesktopProcess(
        cdb,
        diagnostic_package,
        ("-cf", str(commands), "-logo", str(log), str(target)),
    ) as process:
        return_code = process.wait(timeout)
        require(return_code is not None,
                f"CDB did not finish within {timeout:.0f} seconds")

    require(log.is_file(), "CDB did not produce its startup log")
    require(dump.is_file(), "CDB did not produce its startup dump")
    text = log.read_text(encoding="utf-8", errors="replace")
    print(text)
    folded = text.lower()
    require("c0000005" in folded and "exceptionaddress" in folded,
            "CDB did not capture an access-violation exception address")
    print(f"PASS CDB captured the private-desktop startup fault: {log}")
    return log


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cdb", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()
    try:
        capture(args.cdb, args.package, args.output, args.timeout)
    except (OSError, RuntimeError) as error:
        print(f"FAIL CDB startup diagnostic: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
