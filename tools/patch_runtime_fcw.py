#!/usr/bin/env python3
"""Install the reviewed boundaries in one compiled Win32 Lino image.

The upstream L.in.oleum runtime under main/ is licence-protected and remains
byte-for-byte pristine.  The compiler copies one of its eight runtime variants
into each output PE.  This post-link step changes only that selected copy: it
installs the fixed x87 control word and marks the loaded generated-code region
executable before the runtime starts its worker thread.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import struct
import sys


OLD_CONTROL = bytes.fromhex("66 25 FF F3 66 0D 00 0C")
FIXED_CONTROL = bytes.fromhex("66 B8 3F 13 66 90 66 90")
OLD_PROTECT_IMPORT = b"SetPriorityClass\0"
NEW_PROTECT_IMPORT = b"VirtualProtect\0\0\0"
CODE_ALLOCATION = re.compile(
    rb"\x8b\x1d(?P<size>.{4})\xc1\xe3\x02\x0f\x84.{4}"
    rb"\x53\x6a\x42\xe8.{4}\xa3(?P<handle>.{4})"
    rb"\xff\x35(?P=handle)\xe8.{4}\xa3(?P<base>.{4})",
    re.DOTALL,
)
THREAD_START = re.compile(
    rb"\x33\xc0\x68(?P<thread_id>.{4})\x50\x50"
    rb"\x68(?P<trampoline>.{4})\x50\x50\xe8(?P<create_rel>.{4})",
    re.DOTALL,
)
PRIORITY_CALL = re.compile(
    rb"\xa3(?P<thread_handle>.{4})\x6a\x20"
    rb"\xff\x35(?P=thread_handle)\xe8(?P<protect_rel>.{4})",
    re.DOTALL,
)


def patch_image(data: bytes) -> bytes:
    old_count = data.count(OLD_CONTROL)
    fixed_count = data.count(FIXED_CONTROL)
    if old_count != 1 or fixed_count != 0:
        raise ValueError(
            "expected exactly one unpatched runtime control sequence; "
            f"found old={old_count}, fixed={fixed_count}")
    patched = data.replace(OLD_CONTROL, FIXED_CONTROL, 1)
    if len(patched) != len(data):
        raise AssertionError("runtime patch changed executable size")
    return patched


def _unique(pattern: re.Pattern[bytes], data: bytes, description: str):
    matches = list(pattern.finditer(data))
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one {description}; found {len(matches)}")
    return matches[0]


def _pe_section(data: bytes, name: bytes) -> tuple[int, int, int, int, int, int]:
    if len(data) < 0x40 or data[:2] != b"MZ":
        raise ValueError("runtime image is not a PE executable")
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if pe + 24 > len(data) or data[pe:pe + 4] != b"PE\0\0":
        raise ValueError("runtime image has no valid PE header")
    sections = struct.unpack_from("<H", data, pe + 6)[0]
    optional_size = struct.unpack_from("<H", data, pe + 20)[0]
    optional = pe + 24
    if optional + optional_size > len(data):
        raise ValueError("runtime image has a truncated optional header")
    if struct.unpack_from("<H", data, optional)[0] != 0x10B:
        raise ValueError("runtime image is not PE32")
    image_base = struct.unpack_from("<I", data, optional + 28)[0]
    table = optional + optional_size
    matches = []
    for index in range(sections):
        header = table + 40 * index
        if header + 40 > len(data):
            raise ValueError("runtime image has a truncated section table")
        if data[header:header + 8].rstrip(b"\0") == name:
            matches.append(header)
    if len(matches) != 1:
        decoded = name.decode("ascii", errors="replace")
        raise ValueError(f"expected exactly one {decoded} section; found {len(matches)}")
    header = matches[0]
    virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from(
        "<IIII", data, header + 8)
    if raw_offset + raw_size > len(data):
        decoded = name.decode("ascii", errors="replace")
        raise ValueError(f"runtime {decoded} section exceeds the image")
    return (header, image_base, virtual_address, virtual_size,
            raw_offset, raw_size)


def _pe_text(data: bytes) -> tuple[int, int, int, int, int, int]:
    section = _pe_section(data, b".text")
    characteristics = struct.unpack_from("<I", data, section[0] + 36)[0]
    if not characteristics & 0x20000000:
        raise ValueError("runtime .text section is not executable")
    return section


def _relative_call(source_va: int, target_va: int) -> bytes:
    displacement = target_va - (source_va + 5)
    return b"\xe8" + struct.pack("<i", displacement)


def patch_executable_code(data: bytes) -> bytes:
    if len(OLD_PROTECT_IMPORT) != len(NEW_PROTECT_IMPORT):
        raise AssertionError("runtime import replacement changes image size")
    old_imports = data.count(OLD_PROTECT_IMPORT)
    new_imports = data.count(NEW_PROTECT_IMPORT)
    if old_imports != 1 or new_imports != 0:
        raise ValueError(
            "expected one unpatched process-priority import; "
            f"found old={old_imports}, new={new_imports}")

    allocation = _unique(CODE_ALLOCATION, data, "generated-code allocation")
    thread = _unique(THREAD_START, data, "generated-code thread start")
    priority = _unique(PRIORITY_CALL, data, "process-priority call")
    text = _pe_text(data)
    _, image_base, text_va, _, text_raw_offset, text_raw_size = text

    def image_va(file_offset: int) -> int:
        if not text_raw_offset <= file_offset < text_raw_offset + text_raw_size:
            raise ValueError("runtime patch site is outside .text")
        return image_base + text_va + file_offset - text_raw_offset

    thread_va = image_va(thread.start())
    priority_call_offset = priority.end() - 5
    priority_wrapper = image_va(priority.end()) + struct.unpack(
        "<i", priority.group("protect_rel"))[0]
    create_wrapper = thread_va + len(thread.group(0)) + struct.unpack(
        "<i", thread.group("create_rel"))[0]

    # Most variants have enough executable .text padding.  Compact variants
    # use verified padding in an existing mapped section, which gains execute
    # permission only for that image page; the generated allocation itself is
    # still the only heap region changed to executable-writable.
    stub_size = 61
    injection = None
    candidates = (
        text,
        _pe_section(data, b".rdata"),
        _pe_section(data, b".rsrc"),
    )
    for section in candidates:
        _, _, _, section_virtual_size, section_raw_offset, section_raw_size = section
        section_stub_offset = (section_virtual_size + 3) & ~3
        section_stub_file = section_raw_offset + section_stub_offset
        section_stub_end = section_stub_file + stub_size
        if (section_stub_offset + stub_size <= section_raw_size and
                not any(data[section_raw_offset + section_virtual_size:
                             section_stub_end])):
            injection = section
            break
    if injection is None:
        raise ValueError("runtime image has no verified section padding for stub")
    (injection_header, _, injection_va, injection_virtual_size,
     injection_raw_offset, _) = injection
    stub_offset = (injection_virtual_size + 3) & ~3
    stub_file = injection_raw_offset + stub_offset
    stub_va = image_base + injection_va + stub_offset

    stub = bytearray()
    stub += b"\x83\xec\x04\x8b\xc4\x50\x6a\x40"
    stub += b"\xa1" + allocation.group("size") + b"\xc1\xe0\x02\x50"
    stub += b"\xff\x35" + allocation.group("base")
    stub += _relative_call(stub_va + len(stub), priority_wrapper)
    stub += b"\x83\xc4\x04\x85\xc0\x74\x16"
    stub += b"\x33\xc0\x68" + thread.group("thread_id") + b"\x50\x50"
    stub += b"\x68" + thread.group("trampoline") + b"\x50\x50"
    stub += _relative_call(stub_va + len(stub), create_wrapper) + b"\xc3"
    stub += b"\x83\xc8\xff\xc3"
    if len(stub) != stub_size:
        raise AssertionError("generated executable-code stub has changed size")
    new_virtual_size = stub_offset + len(stub)

    patched = bytearray(data)
    import_offset = data.index(OLD_PROTECT_IMPORT)
    patched[import_offset:import_offset + len(NEW_PROTECT_IMPORT)] = (
        NEW_PROTECT_IMPORT)
    patched[thread.start():thread.end()] = (
        _relative_call(thread_va, stub_va) + b"\x90" * (len(thread.group(0)) - 5))
    patched[priority_call_offset - 8:priority.end()] = b"\x90" * 13
    patched[stub_file:stub_file + len(stub)] = stub
    struct.pack_into("<I", patched, injection_header + 8, new_virtual_size)
    characteristics = struct.unpack_from(
        "<I", patched, injection_header + 36)[0]
    struct.pack_into(
        "<I", patched, injection_header + 36,
        characteristics | 0x20000000,
    )
    return bytes(patched)


def patch_runtime_image(data: bytes) -> bytes:
    patched = patch_image(data)
    patched = patch_executable_code(patched)
    if len(patched) != len(data):
        raise AssertionError("runtime patch changed executable size")
    return patched


def patch_file(path: Path) -> None:
    original = path.read_bytes()
    patched = patch_runtime_image(original)
    temporary = path.with_name(path.name + ".fcwtmp")
    try:
        temporary.write_bytes(patched)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    args = parser.parse_args(argv)
    try:
        patch_file(args.image)
    except (OSError, ValueError, AssertionError) as error:
        print(f"patch_runtime_fcw: {error}", file=sys.stderr)
        return 1
    print(f"patched Win32 FCW and executable-code boundaries: {args.image}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
