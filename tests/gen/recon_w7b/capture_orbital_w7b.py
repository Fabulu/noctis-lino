"""Capture one native orbital frame without retaining DOS sandbox changes."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import struct
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DOS = HERE / "dos"
DATA = DOS / "data"
GALLERY = DOS / "gallery"
GODOS = HERE / "godos_w7b.ps1"
BACKUP = ROOT / "build" / "recon-w7b-orbital-sandbox-backup"
ROTOR_PARTIAL = DATA / "ROTOR.PRT"
ROTOR_FINAL = DATA / "ROTOR.BIN"


def decoded_bmp_page(blob: bytes) -> bytes:
    if len(blob) < 54 or blob[:2] != b"BM":
        raise RuntimeError("snapshot is not a BMP")
    pixel_offset = struct.unpack_from("<I", blob, 10)[0]
    width = struct.unpack_from("<i", blob, 18)[0]
    height = struct.unpack_from("<i", blob, 22)[0]
    bits = struct.unpack_from("<H", blob, 28)[0]
    if width != 320 or abs(height) != 200 or bits != 8:
        raise RuntimeError(
            "snapshot is %dx%d at %d bits, expected 320x200x8"
            % (width, height, bits))
    stride = (width + 3) & ~3
    pixels = blob[pixel_offset:pixel_offset + stride * abs(height)]
    if len(pixels) != stride * abs(height):
        raise RuntimeError("snapshot has a truncated pixel array")
    rows = [pixels[row * stride:row * stride + width]
            for row in range(abs(height))]
    if height > 0:
        rows.reverse()
    return b"".join(rows)


def stage(current: Path) -> list[tuple[Path, Path]]:
    if BACKUP.exists():
        raise RuntimeError(
            "sandbox backup already exists; restore it before capturing: %s"
            % BACKUP)
    BACKUP.mkdir(parents=True)
    saved = []
    for source in (
            DATA / "CURRENT.BIN", DATA / "SURFACE.BIN",
            ROTOR_PARTIAL, ROTOR_FINAL, GALLERY):
        if source.exists():
            destination = BACKUP / source.name
            source.replace(destination)
            saved.append((destination, source))
    try:
        shutil.copy2(current, DATA / "CURRENT.BIN")
        GALLERY.mkdir()
    except Exception:
        restore(saved)
        raise
    return saved


def restore(saved: list[tuple[Path, Path]]) -> None:
    for temporary in (
            DATA / "CURRENT.BIN", DATA / "SURFACE.BIN",
            ROTOR_PARTIAL, ROTOR_FINAL):
        if temporary.exists():
            temporary.unlink()
    if GALLERY.exists():
        shutil.rmtree(GALLERY)
    for source, destination in saved:
        source.replace(destination)
    if BACKUP.exists():
        BACKUP.rmdir()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--command", type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--poll-milliseconds", type=int, default=1)
    parser.add_argument("--cycles", default="max")
    parser.add_argument(
        "--stop-artifact", choices=("gallery-bmp", "rotor-bin"),
        default="gallery-bmp",
        help="file whose completed publication stops the native runner",
    )
    args = parser.parse_args()

    current = args.current.resolve()
    command = args.command.resolve()
    if not current.is_file() or current.stat().st_size != 385:
        parser.error("--current must name a complete 385-byte CURRENT.BIN")
    if not command.is_file():
        parser.error("--command does not exist")
    if not args.name or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for c in args.name):
        parser.error("--name must contain only lowercase letters, digits, hyphens and underscores")

    mem_path = HERE / "mem" / (args.name + ".mem")
    shot_path = HERE / "out" / (args.name + ".shot.BMP")
    adapted_path = HERE / "out" / (args.name + ".adapted")
    rotor_path = HERE / "out" / (args.name + ".ROTOR.BIN")
    snapshot_path = GALLERY / "00000000.BMP"
    if args.stop_artifact == "rotor-bin":
        stop_path = ROTOR_FINAL
        stop_size = 192_062
    else:
        stop_path = snapshot_path
        stop_size = 65_078
    outputs = [mem_path, shot_path, adapted_path]
    if args.stop_artifact == "rotor-bin":
        outputs.append(rotor_path)
    for output in outputs:
        if output.exists():
            parser.error("refusing to overwrite %s" % output)

    saved = stage(current)
    try:
        process = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", str(GODOS), "-CmdFile", str(command),
             "-TimeoutSec", str(args.timeout), "-MemFile", str(mem_path),
             "-StopAfterFile", str(stop_path), "-StopPollMilliseconds",
             str(args.poll_milliseconds), "-Cycles", args.cycles],
            text=True, encoding="utf-8", errors="replace",
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        print(process.stdout, end="")
        if process.returncode:
            raise RuntimeError("godos_w7b exited with %d" % process.returncode)
        if not stop_path.is_file() or stop_path.stat().st_size != stop_size:
            raise RuntimeError(
                "%s did not reach exactly %d bytes" % (stop_path.name, stop_size))
        if (not snapshot_path.is_file()
                or snapshot_path.stat().st_size != 65_078):
            raise RuntimeError("native snapshot did not reach 65,078 bytes")
        if not mem_path.is_file() or mem_path.stat().st_size != 16 * 1024 * 1024:
            raise RuntimeError("native RAM image is absent or incomplete")
        shutil.copy2(snapshot_path, shot_path)
        if args.stop_artifact == "rotor-bin":
            shutil.copy2(ROTOR_FINAL, rotor_path)
    finally:
        restore(saved)

    sys.path.insert(0, str(HERE))
    import memfind

    memory = mem_path.read_bytes()
    regions, problems = memfind.locate(memory)
    if problems:
        raise RuntimeError("invalid far-heap chain: %s" % "; ".join(problems))
    adapted = regions["adapted"]
    page = memory[adapted["addr"]:adapted["addr"] + adapted["size"]]
    adapted_path.write_bytes(page)
    bmp_page = decoded_bmp_page(shot_path.read_bytes())
    mismatches = sum(a != b for a, b in zip(bmp_page, page[:64000]))

    print("captured %s" % shot_path)
    if args.stop_artifact == "rotor-bin":
        print("captured %s" % rotor_path)
    print("captured %s" % mem_path)
    print("captured %s" % adapted_path)
    if mismatches:
        print("BMP page differs from the post-snapshot guest page at %d indices"
              % mismatches)
    else:
        print("BMP page exactly equals the frozen 64,000-byte guest page")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
