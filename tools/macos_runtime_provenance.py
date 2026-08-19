#!/usr/bin/env python3
"""Record and verify provenance for an unsigned macOS x86_64 Lino RTM."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import platform
import struct
import subprocess


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SOURCE = ROOT / "src" / "linoleum_macos64"
DEPLOYMENT_TARGET = "10.15"
REQUIRED_KEYS = {
    "runtime_provenance_format",
    "commit",
    "runtime_sha256",
    "runtime_mode",
    "runtime_build_script_sha256",
    "runtime_source_tree_sha256",
    "runtime_architecture",
    "runtime_deployment_target",
    "runtime_host_arch",
    "runtime_macos_version",
    "runtime_xcode_version",
    "runtime_sdk_version",
    "runtime_clang_version",
    "runtime_signing",
    "runtime_provenance",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tracked_tree_sha256(directory: Path) -> str:
    prefix = directory.relative_to(ROOT).as_posix()
    listed = subprocess.check_output(
        ["git", "-C", str(ROOT), "ls-files", "-z", "--", prefix]
    )
    relatives = sorted(item.decode("utf-8") for item in listed.split(b"\0") if item)
    if not relatives:
        raise ValueError(f"no tracked files found under {prefix}")
    digest = hashlib.sha256()
    for relative_text in relatives:
        path = ROOT / relative_text
        if not path.is_file():
            raise ValueError(f"tracked runtime input is not a file: {relative_text}")
        relative = relative_text.encode("utf-8")
        payload = path.read_bytes()
        digest.update(len(relative).to_bytes(4, "little"))
        digest.update(relative)
        digest.update(len(payload).to_bytes(8, "little"))
        digest.update(payload)
    return digest.hexdigest()


def command_line(*command: str) -> str:
    output = subprocess.check_output(command, text=True).strip()
    return " / ".join(part.strip() for part in output.splitlines() if part.strip())


def validate_macho(path: Path) -> None:
    data = path.read_bytes()
    if len(data) < 1024 or data[:4] != b"\xcf\xfa\xed\xfe":
        raise ValueError(f"{path} is not a thin little-endian 64-bit Mach-O")
    if struct.unpack_from("<I", data, 4)[0] != 0x01000007:
        raise ValueError(f"{path} is not x86_64")


def read_provenance(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="ascii").splitlines():
        if not line or "=" not in line:
            raise ValueError(f"invalid runtime provenance line: {line!r}")
        key, value = line.split("=", 1)
        if not key or key in values:
            raise ValueError(f"invalid or duplicate runtime provenance key: {key!r}")
        values[key] = value
    missing = REQUIRED_KEYS - values.keys()
    extra = values.keys() - REQUIRED_KEYS
    if missing or extra:
        raise ValueError(
            f"runtime provenance schema differs: missing={sorted(missing)!r}, "
            f"extra={sorted(extra)!r}"
        )
    return values


def expected_commit(requested: str | None) -> str:
    checkout = command_line("git", "-C", str(ROOT), "rev-parse", "HEAD")
    commit = requested or os.environ.get("GITHUB_SHA") or checkout
    if commit != checkout:
        raise ValueError(f"requested commit {commit} differs from checkout {checkout}")
    if not all(character in "0123456789abcdef" for character in commit) or len(commit) != 40:
        raise ValueError(f"invalid commit hash: {commit!r}")
    return commit


def expected_values(runtime: Path, mode: str, commit: str) -> dict[str, str]:
    return {
        "runtime_provenance_format": "1",
        "commit": commit,
        "runtime_sha256": sha256(runtime),
        "runtime_mode": mode,
        "runtime_build_script_sha256": sha256(RUNTIME_SOURCE / "build.sh"),
        "runtime_source_tree_sha256": tracked_tree_sha256(RUNTIME_SOURCE),
        "runtime_architecture": "x86_64",
        "runtime_deployment_target": DEPLOYMENT_TARGET,
        "runtime_signing": "unsigned before the Lino image is appended",
    }


def write_provenance(runtime: Path, output: Path, mode: str, commit: str) -> None:
    validate_macho(runtime)
    if output.exists():
        raise FileExistsError(f"refusing to replace existing provenance: {output}")
    values = expected_values(runtime, mode, commit)
    values.update(
        {
            "runtime_host_arch": platform.machine(),
            "runtime_macos_version": command_line("sw_vers", "-productVersion"),
            "runtime_xcode_version": command_line("xcodebuild", "-version"),
            "runtime_sdk_version": command_line(
                "xcrun", "--sdk", "macosx", "--show-sdk-version"
            ),
            "runtime_clang_version": command_line(
                "xcrun", "--sdk", "macosx", "clang", "--version"
            ),
            "runtime_provenance": (
                "recorded from the exact unsigned RTM bytes, tracked runtime inputs, "
                "and Apple toolchain on the macOS build host"
            ),
        }
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "".join(f"{key}={value}\n" for key, value in values.items()),
        encoding="ascii",
        newline="\n",
    )


def verify_provenance(runtime: Path, provenance: Path, mode: str, commit: str) -> None:
    validate_macho(runtime)
    values = read_provenance(provenance)
    expected = expected_values(runtime, mode, commit)
    mismatches = {
        key: (values.get(key), value)
        for key, value in expected.items()
        if values.get(key) != value
    }
    if mismatches:
        raise ValueError(f"runtime provenance mismatch: {mismatches!r}")
    if values["runtime_host_arch"] != "arm64":
        raise ValueError(
            f"runtime was not recorded on the Apple Silicon host: "
            f"{values['runtime_host_arch']!r}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "verify"))
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    parser.add_argument("--mode", choices=("headless", "cocoa"), required=True)
    parser.add_argument("--commit")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runtime = args.runtime.resolve()
    provenance = args.provenance.resolve()
    commit = expected_commit(args.commit)
    if args.action == "write":
        write_provenance(runtime, provenance, args.mode, commit)
    else:
        verify_provenance(runtime, provenance, args.mode, commit)
    print(f"{args.action.upper()} {args.mode} runtime provenance: {provenance}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
