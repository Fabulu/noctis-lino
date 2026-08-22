#!/usr/bin/env python3
"""Structural and Mach-O tests for the native macOS AArch64 runtime."""

from __future__ import annotations

from pathlib import Path
import struct
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "src" / "linoleum_macos_aarch64"
WORKFLOW = ROOT / ".github" / "workflows" / "macos-aarch64-runtime.yml"
COMPILE_SCRIPT = ROOT / "build" / "compile_macos_aarch64_fixture.sh"
FIXTURE_SOURCE = ROOT / "tests" / "fixtures" / "macos_aarch64_runtime.txt"
RUN_ALL = ROOT / "tests" / "run_all.py"
sys.path.insert(0, str(ROOT / "tools"))

import finalize_macos_aarch64 as finalize  # noqa: E402


RUNTIME_SIZE = 0x8000
LINKEDIT_OFFSET = 0x4000
APP_WS_UNITS = 8
APP_CODE_UNITS = 4
APP_SIZE = RUNTIME_SIZE + (APP_WS_UNITS + APP_CODE_UNITS) * 4
MARKER_OFFSET = 0x1000


def segment(name: bytes, vmaddr: int, vmsize: int, fileoff: int,
            filesize: int, maxprot: int, initprot: int) -> bytes:
    return finalize.SEGMENT_64.pack(
        finalize.LC_SEGMENT_64, finalize.SEGMENT_64.size,
        name + bytes(16 - len(name)), vmaddr, vmsize, fileoff, filesize,
        maxprot, initprot, 0, 0,
    )


def unsigned_image() -> bytes:
    commands = b"".join((
        segment(b"__PAGEZERO", 0, 0x100000000, 0, 0, 0, 0),
        segment(
            b"__TEXT", 0x100000000, 0x4000, 0, 0x4000,
            finalize.VM_PROT_READ | finalize.VM_PROT_EXECUTE,
            finalize.VM_PROT_READ | finalize.VM_PROT_EXECUTE,
        ),
        segment(
            b"__LINKEDIT", 0x100004000, 0x4000,
            LINKEDIT_OFFSET, RUNTIME_SIZE - LINKEDIT_OFFSET,
            finalize.VM_PROT_READ, finalize.VM_PROT_READ,
        ),
    ))
    header = finalize.MACH_HEADER.pack(
        finalize.MH_MAGIC_64, finalize.CPU_TYPE_ARM64, 0,
        finalize.MH_EXECUTE, 3, len(commands), 0, 0,
    )
    image = bytearray(APP_SIZE)
    image[:len(header)] = header
    image[len(header):len(header) + len(commands)] = commands

    paragraph = MARKER_OFFSET + len(finalize.MARKER)
    fields = (
        APP_WS_UNITS, APP_CODE_UNITS, 0, RUNTIME_SIZE, APP_SIZE, 32,
        0, 0, 0, 0, 0, 0, 0, 0,
    )
    image[MARKER_OFFSET:paragraph] = finalize.MARKER
    appname = b"macOS AArch64 fixture"
    image[paragraph:paragraph + 40] = appname + bytes(40 - len(appname))
    image[paragraph + 40:paragraph + 96] = finalize.INIT_FIELDS.pack(*fields)
    image[paragraph + 96:paragraph + 104] = finalize.END_MARKER
    image[RUNTIME_SIZE:RUNTIME_SIZE + APP_WS_UNITS * 4] = bytes(
        APP_WS_UNITS * 4)
    image[-APP_CODE_UNITS * 4:] = struct.pack(
        "<4I", 0xD2800020, 0xD2800041, 0xD2800062, 0xD65F03C0)
    return bytes(image)


def signed_image() -> bytes:
    image = bytearray(finalize.normalize_linkedit(unsigned_image()))
    header = list(finalize.MACH_HEADER.unpack_from(image))
    command_offset = finalize.MACH_HEADER.size + header[5]
    signature_offset = finalize.align_up(len(image), 16) + 16
    signature = b"synthetic-adhoc-signature"
    command = finalize.LINKEDIT_DATA.pack(
        finalize.LC_CODE_SIGNATURE, finalize.LINKEDIT_DATA.size,
        signature_offset, len(signature),
    )
    image[command_offset:command_offset + len(command)] = command
    header[4] += 1
    header[5] += len(command)
    finalize.MACH_HEADER.pack_into(image, 0, *header)
    image.extend(bytes(signature_offset - len(image)))
    image.extend(signature)

    _header, commands = finalize.load_commands(image)
    linkedit_offset, values = finalize.linkedit_command(image, commands)
    fileoff = int(values[5])
    filesize = len(image) - fileoff
    struct.pack_into(
        "<QQQ", image, linkedit_offset + 32,
        finalize.align_up(filesize, finalize.ARM64_PAGE_SIZE),
        fileoff, filesize,
    )
    return bytes(image)


class MacOSAArch64RuntimeTests(unittest.TestCase):
    def test_runtime_uses_checked_darwin_abi(self) -> None:
        source = (RUNTIME / "rtm.c").read_text(encoding="utf-8")
        header = (RUNTIME / "rtm.h").read_text(encoding="utf-8")
        assembly = (RUNTIME / "isokernel.s").read_text(encoding="utf-8")
        build = (RUNTIME / "build.sh").read_text(encoding="utf-8")

        self.assertIn("sizeof(struct LNLMINIT) == 96", header)
        self.assertIn("ARM64_UI_REQUIRED_UNITS = 12", header)
        self.assertIn("validate_macho_suffix", source)
        self.assertIn("mprotect(pCode, pCodeMapBytes, PROT_READ | PROT_EXEC)", source)
        self.assertIn("publish_runtime_pointers();", source)
        for forbidden in ("MAP_FIXED", "realloc(", "PROT_WRITE | PROT_EXEC"):
            self.assertNotIn(forbidden, source)
        self.assertIn(".globl _isokernel", assembly)
        self.assertIn("_pWorkspace@PAGEOFF", assembly)
        self.assertNotIn("x18", "\n".join(
            line for line in assembly.splitlines() if not line.lstrip().startswith("*")))
        self.assertEqual(assembly.count("sub     sp, sp, #80"), 1)
        self.assertEqual(assembly.count("add     sp, sp, #80"), 1)
        self.assertIn("-arch arm64", build)
        self.assertIn("-Wl,-no_adhoc_codesign", build)
        self.assertNotIn("pagezero_size", build)

    def test_hosted_gate_compiles_and_executes_natively(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        compile_script = COMPILE_SCRIPT.read_text(encoding="utf-8")
        fixture = FIXTURE_SOURCE.read_text(encoding="utf-8")
        run_all = RUN_ALL.read_text(encoding="utf-8")

        self.assertEqual(workflow.count("runs-on: macos-15"), 2)
        self.assertIn("--cpu:aarch64", compile_script)
        self.assertIn("--sys:macarm64", compile_script)
        self.assertIn("tracked-work", compile_script)
        self.assertIn("compiled_complete", compile_script)
        self.assertIn("physwsentry < len(runtime)", compile_script)
        self.assertIn("physappsize > len(image)", compile_script)
        self.assertIn('"$source_mode" != tracked-work', compile_script)
        self.assertIn("compiler changed immutable runtime bytes", compile_script)
        self.assertIn('git -C "$repo" archive', compile_script)
        self.assertIn("'work/**/*.txt'", compile_script)
        self.assertIn("'work/*.tga'", compile_script)
        self.assertNotIn('cp -R "$repo/work', compile_script)
        self.assertIn("build_compiler114m_linux.sh", workflow)
        self.assertIn("work/vhgame.txt", workflow)
        self.assertIn("build/macos-aarch64-noctis.unsigned", workflow)
        self.assertIn("service_units = 32947", workflow)
        self.assertIn("Compiled full Noctis AArch64 image", workflow)
        self.assertIn("finalize_macos_aarch64.py --sign", workflow)
        self.assertIn("arch -arm64 \"$output\"", workflow)
        self.assertIn("Native compiler-owned AArch64 fixture passed", workflow)
        self.assertIn("A = 1;", fixture)
        self.assertIn("E = 5;", fixture)
        self.assertIn("end;", fixture)
        self.assertEqual(run_all.count('(\"test_macos_aarch64_runtime.py\",'), 1)

    def test_normalizer_extends_only_linkedit(self) -> None:
        original = unsigned_image()
        normalized = finalize.normalize_linkedit(original)
        self.assertEqual(len(normalized), len(original))
        self.assertEqual(
            normalized[:finalize.MACH_HEADER.size],
            original[:finalize.MACH_HEADER.size],
        )
        _header, commands = finalize.load_commands(normalized)
        _offset, values = finalize.linkedit_command(normalized, commands)
        self.assertEqual(int(values[5]), LINKEDIT_OFFSET)
        self.assertEqual(int(values[6]), APP_SIZE - LINKEDIT_OFFSET)
        self.assertEqual(
            int(values[4]),
            finalize.align_up(APP_SIZE - LINKEDIT_OFFSET,
                              finalize.ARM64_PAGE_SIZE),
        )
        self.assertIsNone(finalize.signature_command(normalized, commands))
        self.assertEqual(finalize.lino_fields(normalized)[4], APP_SIZE)

    def test_final_validator_accepts_exact_signature_suffix(self) -> None:
        image = signed_image()
        finalize.validate_final(image)

    def test_normalizer_rejects_wrong_payload_and_signature_state(self) -> None:
        image = unsigned_image()
        with self.assertRaisesRegex(finalize.ImageError, "beyond physappsize"):
            finalize.normalize_linkedit(image + b"unexpected")

        duplicate = bytearray(image)
        duplicate[0x2000:0x2008] = finalize.MARKER
        with self.assertRaisesRegex(finalize.ImageError, "exactly one LNLMInit"):
            finalize.normalize_linkedit(bytes(duplicate))

        bad_bounds = bytearray(image)
        paragraph = MARKER_OFFSET + len(finalize.MARKER) + 40
        struct.pack_into("<i", bad_bounds, paragraph + 4 * 4, APP_SIZE - 4)
        with self.assertRaisesRegex(finalize.ImageError, "physappsize"):
            finalize.normalize_linkedit(bytes(bad_bounds))

        bad_pagezero = bytearray(image)
        struct.pack_into("<Q", bad_pagezero,
                         finalize.MACH_HEADER.size + 32, 0x4000000)
        with self.assertRaisesRegex(finalize.ImageError, "low 4 GiB"):
            finalize.normalize_linkedit(bytes(bad_pagezero))

        already_signed = signed_image()
        with self.assertRaisesRegex(finalize.ImageError, "beyond physappsize"):
            finalize.normalize_linkedit(already_signed)

    def test_final_validator_rejects_non_signature_suffixes(self) -> None:
        image = bytearray(signed_image())
        image.append(0)
        with self.assertRaisesRegex(finalize.ImageError, "exact final file suffix"):
            finalize.validate_final(bytes(image))

        image = bytearray(signed_image())
        _header, commands = finalize.load_commands(image)
        signature = finalize.signature_command(image, commands)
        self.assertIsNotNone(signature)
        signature_offset, _signature_size = signature or (0, 0)
        image[APP_SIZE:signature_offset] = b"\x01" * (signature_offset - APP_SIZE)
        with self.assertRaisesRegex(finalize.ImageError, "nonzero bytes"):
            finalize.validate_final(bytes(image))


if __name__ == "__main__":
    unittest.main(verbosity=2)
