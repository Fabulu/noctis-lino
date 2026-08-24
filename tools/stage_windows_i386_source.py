#!/usr/bin/env python3
"""Stage portable Noctis source with the win32/i386m native renderer."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_NAME = "windows-i386-source.provenance.txt"
SOURCE_RELATIVE = Path("work/vhgame.txt")
OVERRIDES = {
    "fpx87.txt": Path("work/fp/fpx87.txt"),
    "fpconv.txt": Path("work/fp/fpconv.txt"),
    "mul64frag.txt": Path("work/mul64frag.txt"),
    "pgproj.txt": Path("work/pgproj.txt"),
    "pgtex.txt": Path("work/pgtex.txt"),
    "vhgame.txt": SOURCE_RELATIVE,
    "vhground.txt": Path("work/vhground.txt"),
    "vhspace.txt": Path("work/vhspace.txt"),
}


def tracked_source_paths(root: Path) -> list[Path]:
    output = subprocess.check_output(
        [
            "git", "-C", str(root), "ls-files", "-z", "--",
            "work/*.txt", "work/**/*.txt", "work/*.tga",
        ]
    )
    return sorted({Path(item.decode("utf-8")) for item in output.split(b"\0") if item})


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def backend_provenance_key(name: str) -> str:
    return f"i386_{Path(name).stem}_sha256"


def override_provenance_key(name: str) -> str:
    if OVERRIDES[name] == SOURCE_RELATIVE:
        return "source_sha256"
    return backend_provenance_key(name)


def write_manifest(root: Path, output: Path, source: Path) -> Path:
    records = [("source_sha256", sha256(source))]
    records.extend(
        (override_provenance_key(name), sha256(output / relative))
        for name, relative in sorted(OVERRIDES.items())
        if relative != SOURCE_RELATIVE
    )
    records.append((
        "source_staging_script_sha256",
        sha256(root / "tools" / "stage_windows_i386_source.py"),
    ))
    manifest = output / MANIFEST_NAME
    manifest.write_text(
        "".join(f"{key}={value}\n" for key, value in records),
        encoding="ascii", newline="\n")
    return manifest


def stage_source(root: Path, output: Path) -> Path:
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"staging directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)

    paths = tracked_source_paths(root)
    if SOURCE_RELATIVE not in paths:
        raise ValueError(f"tracked {SOURCE_RELATIVE.as_posix()} is missing")
    for relative in paths:
        source = root / relative
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    backend = root / "src" / "linoleum_i386"
    for name, relative in OVERRIDES.items():
        source = backend / name
        if not source.is_file():
            raise FileNotFoundError(f"missing i386 backend source: {source}")
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    staged_source = output / SOURCE_RELATIVE
    write_manifest(root, output, staged_source)
    return staged_source


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    source = stage_source(args.root.resolve(), args.output.resolve())
    print(source)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
