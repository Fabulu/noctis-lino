#!/usr/bin/env python3
"""Finalize and ad-hoc sign a compiler-appended macOS arm64 Lino image."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import shutil
import struct
import subprocess
import sys


MH_MAGIC_64 = 0xFEEDFACF
CPU_TYPE_ARM64 = 0x0100000C
MH_EXECUTE = 2
LC_SEGMENT_64 = 0x19
LC_CODE_SIGNATURE = 0x1D
VM_PROT_READ = 1
VM_PROT_WRITE = 2
VM_PROT_EXECUTE = 4
ARM64_PAGE_SIZE = 0x4000
MARKER = b"LNLMInit"
END_MARKER = b"LNLMIend"
MACH_HEADER = struct.Struct("<IiiIIIII")
LOAD_COMMAND = struct.Struct("<II")
SEGMENT_64 = struct.Struct("<II16sQQQQiiII")
LINKEDIT_DATA = struct.Struct("<IIII")
INIT_FIELDS = struct.Struct("<14i")


class ImageError(ValueError):
    """The input is not a safe compiler-appended arm64 Lino image."""


def align_up(value: int, alignment: int) -> int:
    if value < 0 or alignment <= 0 or alignment & (alignment - 1):
        raise ValueError("alignment requires a nonnegative value and power of two")
    return (value + alignment - 1) & -alignment


def unique_marker(data: bytes, marker: bytes) -> int:
    offset = data.find(marker)
    if offset < 0 or data.find(marker, offset + 1) >= 0:
        raise ImageError(f"expected exactly one {marker.decode('ascii')} marker")
    return offset


def lino_fields(data: bytes) -> tuple[int, ...]:
    marker = unique_marker(data, MARKER)
    end_marker = unique_marker(data, END_MARKER)
    paragraph = marker + len(MARKER)
    paragraph_end = paragraph + 40 + INIT_FIELDS.size
    if paragraph_end > len(data) or end_marker != paragraph_end:
        raise ImageError("Lino initialization paragraph is truncated or displaced")
    appname = data[paragraph:paragraph + 40]
    if b"\0" not in appname:
        raise ImageError("Lino application name is not terminated")
    return INIT_FIELDS.unpack_from(data, paragraph + 40)


def load_commands(data: bytes) -> tuple[tuple[int, ...], list[tuple[int, int, int]]]:
    if len(data) < MACH_HEADER.size:
        raise ImageError("Mach-O header is truncated")
    header = MACH_HEADER.unpack_from(data)
    magic, cpu_type, _cpu_subtype, file_type, ncmds, sizeofcmds, _flags, _reserved = header
    if magic != MH_MAGIC_64 or cpu_type != CPU_TYPE_ARM64 or file_type != MH_EXECUTE:
        raise ImageError("image is not a thin little-endian arm64 Mach-O executable")
    commands_end = MACH_HEADER.size + sizeofcmds
    if commands_end > len(data):
        raise ImageError("Mach-O load-command table is truncated")

    commands = []
    offset = MACH_HEADER.size
    for _index in range(ncmds):
        if commands_end - offset < LOAD_COMMAND.size:
            raise ImageError("Mach-O load-command count exceeds its table")
        command, command_size = LOAD_COMMAND.unpack_from(data, offset)
        if command_size < LOAD_COMMAND.size or command_size > commands_end - offset:
            raise ImageError("Mach-O load command has an invalid size")
        commands.append((command, offset, command_size))
        offset += command_size
    if offset != commands_end:
        raise ImageError("Mach-O load-command count does not cover its table")
    return header, commands


def application_size(data: bytes) -> tuple[int, int]:
    fields = lino_fields(data)
    app_ws_size, app_code_size, app_code_entry = fields[:3]
    physwsentry, physappsize, default_ramtop = fields[3:6]
    if app_ws_size <= 0 or app_code_size <= 0:
        raise ImageError("Lino workspace and code sizes must be positive")
    if not 0 <= app_code_entry < app_code_size:
        raise ImageError("Lino code entry is outside the code payload")
    if physwsentry <= 0 or physappsize <= 0:
        raise ImageError("Lino physical offsets must be positive")
    if default_ramtop < app_ws_size + 32947:
        raise ImageError("Lino RAMtop leaves no complete service workspace")
    expected = physwsentry + (app_ws_size + app_code_size) * 4
    if expected != physappsize:
        raise ImageError("Lino payload bounds do not match physappsize")
    return physwsentry, physappsize


def segment(data: bytes, offset: int, size: int) -> tuple[object, ...]:
    if size < SEGMENT_64.size:
        raise ImageError("Mach-O segment command is truncated")
    return SEGMENT_64.unpack_from(data, offset)


def signature_command(data: bytes, commands: list[tuple[int, int, int]]) -> tuple[int, int] | None:
    signatures = []
    for command, offset, size in commands:
        if command == LC_CODE_SIGNATURE:
            if size != LINKEDIT_DATA.size:
                raise ImageError("Mach-O code-signature command has an invalid size")
            _command, _size, data_offset, data_size = LINKEDIT_DATA.unpack_from(data, offset)
            signatures.append((data_offset, data_size))
    if len(signatures) > 1:
        raise ImageError("Mach-O contains multiple code-signature commands")
    return signatures[0] if signatures else None


def validate_pagezero(data: bytes, commands: list[tuple[int, int, int]]) -> None:
    matches = []
    for command, offset, size in commands:
        if command != LC_SEGMENT_64:
            continue
        values = segment(data, offset, size)
        if values[2].split(b"\0", 1)[0] == b"__PAGEZERO":
            matches.append(values)
    if len(matches) != 1:
        raise ImageError("Mach-O must contain exactly one __PAGEZERO segment")
    values = matches[0]
    if (
        int(values[3]) != 0
        or int(values[4]) != 0x100000000
        or int(values[5]) != 0
        or int(values[6]) != 0
        or int(values[7]) != 0
        or int(values[8]) != 0
    ):
        raise ImageError("arm64 __PAGEZERO must reserve the complete low 4 GiB")


def linkedit_command(data: bytes, commands: list[tuple[int, int, int]]) -> tuple[int, tuple[object, ...]]:
    matches = []
    segments = []
    for command, offset, size in commands:
        if command != LC_SEGMENT_64:
            continue
        values = segment(data, offset, size)
        segments.append(values)
        name = values[2].split(b"\0", 1)[0]
        if name == b"__LINKEDIT":
            matches.append((offset, values))
    if len(matches) != 1:
        raise ImageError("Mach-O must contain exactly one __LINKEDIT segment")

    _offset, linkedit = matches[0]
    link_vmaddr, link_fileoff = int(linkedit[3]), int(linkedit[5])
    for values in segments:
        if values is linkedit:
            continue
        vmaddr, vmsize = int(values[3]), int(values[4])
        fileoff, filesize = int(values[5]), int(values[6])
        if vmaddr + vmsize > link_vmaddr or fileoff + filesize > link_fileoff:
            raise ImageError("__LINKEDIT is not the final Mach-O segment")
    return matches[0]


def normalize_linkedit(data: bytes) -> bytes:
    """Extend unsigned __LINKEDIT over payload and opaque stock resources."""
    _header, commands = load_commands(data)
    validate_pagezero(data, commands)
    runtime_size, physical_size = application_size(data)
    if len(data) < physical_size:
        raise ImageError("unsigned image is truncated before physappsize")
    if signature_command(data, commands) is not None:
        raise ImageError("unsigned image already contains a code-signature command")

    command_offset, values = linkedit_command(data, commands)
    fileoff, old_filesize = int(values[5]), int(values[6])
    vmaddr = int(values[3])
    if fileoff % ARM64_PAGE_SIZE or vmaddr % ARM64_PAGE_SIZE:
        raise ImageError("arm64 __LINKEDIT geometry is not 16 KiB aligned")
    if fileoff + old_filesize != runtime_size:
        raise ImageError("__LINKEDIT does not end at the compiler-recorded RTM boundary")
    new_filesize = len(data) - fileoff
    new_vmsize = align_up(new_filesize, ARM64_PAGE_SIZE)
    if new_filesize <= 0:
        raise ImageError("compiler payload does not extend __LINKEDIT")

    patched = bytearray(data)
    struct.pack_into("<QQ", patched, command_offset + 32, new_vmsize, fileoff)
    struct.pack_into("<Q", patched, command_offset + 48, new_filesize)
    return bytes(patched)


def validate_final(data: bytes) -> None:
    """Validate exact post-signing geometry and the permitted signature suffix."""
    _header, commands = load_commands(data)
    validate_pagezero(data, commands)
    _runtime_size, physical_size = application_size(data)
    signature = signature_command(data, commands)
    if signature is None:
        raise ImageError("final image has no code-signature command")
    data_offset, data_size = signature
    if data_size <= 0 or data_offset < physical_size or data_offset + data_size != len(data):
        raise ImageError("code signature is not the exact final file suffix")

    _command_offset, values = linkedit_command(data, commands)
    vmsize, fileoff, filesize = int(values[4]), int(values[5]), int(values[6])
    if fileoff + filesize != len(data):
        raise ImageError("signed __LINKEDIT does not cover the complete file")
    if vmsize < filesize or vmsize % ARM64_PAGE_SIZE:
        raise ImageError("signed __LINKEDIT virtual size is not 16 KiB rounded")
    maxprot, initprot = int(values[7]), int(values[8])
    if maxprot & VM_PROT_WRITE or initprot & (VM_PROT_WRITE | VM_PROT_EXECUTE):
        raise ImageError("signed __LINKEDIT has writable or executable protections")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finalize(source: Path, output: Path, sign: bool) -> None:
    original = source.read_bytes()
    patched = normalize_linkedit(original)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(patched)
    output.chmod(source.stat().st_mode)

    if not sign:
        print(f"normalized unsigned arm64 Mach-O {output}")
        return
    if sys.platform != "darwin" or shutil.which("codesign") is None:
        raise RuntimeError("--sign requires macOS codesign")
    subprocess.run(
        ["codesign", "--force", "--sign", "-", "--timestamp=none", str(output)],
        check=True,
    )
    subprocess.run(
        ["codesign", "--verify", "--strict", "--verbose=2", str(output)],
        check=True,
    )
    validate_final(output.read_bytes())
    print(f"finalized {output} sha256={sha256(output)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="unsigned compiler-appended image")
    parser.add_argument("output", type=Path, help="normalized output image")
    parser.add_argument("--sign", action="store_true", help="ad-hoc sign and verify on macOS")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.source.resolve() == args.output.resolve():
        raise SystemExit("source and output must be different paths")
    try:
        finalize(args.source, args.output, args.sign)
    except (ImageError, OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"macOS AArch64 finalization failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
