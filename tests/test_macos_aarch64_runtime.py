#!/usr/bin/env python3
"""Structural and Mach-O tests for the native macOS AArch64 runtime."""

from __future__ import annotations

from pathlib import Path
import plistlib
import struct
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "src" / "linoleum_macos_aarch64"
WORKFLOW = ROOT / ".github" / "workflows" / "macos-aarch64-runtime.yml"
COMPILE_SCRIPT = ROOT / "build" / "compile_macos_aarch64_fixture.sh"
FIXTURE_SOURCE = ROOT / "tests" / "fixtures" / "macos_aarch64_runtime.txt"
RUN_ALL = ROOT / "tests" / "run_all.py"
sys.path.insert(0, str(ROOT / "tools"))

import finalize_macos_aarch64 as finalize  # noqa: E402
import package_noctis_macos_aarch64 as package  # noqa: E402


RUNTIME_SIZE = 0x8000
LINKEDIT_OFFSET = 0x4000
APP_WS_UNITS = 8
APP_CODE_UNITS = 4
SERVICE_UNITS = 32947
APP_SIZE = RUNTIME_SIZE + (APP_WS_UNITS + APP_CODE_UNITS) * 4
MARKER_OFFSET = 0x1000
STOCK_BYTES = b"opaque-stock-resource\x00\xff\x01"


def segment(name: bytes, vmaddr: int, vmsize: int, fileoff: int,
            filesize: int, maxprot: int, initprot: int) -> bytes:
    return finalize.SEGMENT_64.pack(
        finalize.LC_SEGMENT_64, finalize.SEGMENT_64.size,
        name + bytes(16 - len(name)), vmaddr, vmsize, fileoff, filesize,
        maxprot, initprot, 0, 0,
    )


def unsigned_image(stock: bytes = b"") -> bytes:
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
    image = bytearray(APP_SIZE + len(stock))
    image[:len(header)] = header
    image[len(header):len(header) + len(commands)] = commands

    paragraph = MARKER_OFFSET + len(finalize.MARKER)
    fields = (
        APP_WS_UNITS, APP_CODE_UNITS, 0, RUNTIME_SIZE, APP_SIZE,
        APP_WS_UNITS + SERVICE_UNITS,
        0, 0, 0, 0, 0, 0, 0, 0,
    )
    image[MARKER_OFFSET:paragraph] = finalize.MARKER
    appname = b"macOS AArch64 fixture"
    image[paragraph:paragraph + 40] = appname + bytes(40 - len(appname))
    image[paragraph + 40:paragraph + 96] = finalize.INIT_FIELDS.pack(*fields)
    image[paragraph + 96:paragraph + 104] = finalize.END_MARKER
    image[RUNTIME_SIZE:RUNTIME_SIZE + APP_WS_UNITS * 4] = bytes(
        APP_WS_UNITS * 4)
    code_start = APP_SIZE - APP_CODE_UNITS * 4
    image[code_start:APP_SIZE] = struct.pack(
        "<4I", 0xD2800020, 0xD2800041, 0xD2800062, 0xD65F03C0)
    image[APP_SIZE:] = stock
    return bytes(image)


def signed_image(stock: bytes = b"") -> bytes:
    image = bytearray(finalize.normalize_linkedit(unsigned_image(stock)))
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
        self.assertIn("ARM64_UI_REQUIRED_UNITS = 32947", header)
        self.assertIn('../linoleum_macos64/lino_kernel.h', header)
        self.assertIn("validate_macho_suffix", source)
        self.assertIn("handle_pending_events();", source)
        self.assertIn("krnlFileCommand", source)
        self.assertIn("krnl_system_time_command", source)
        self.assertIn("krnl_process_command", source)
        self.assertIn("ARM64_UI_COMMAND_LINE = 12", header)
        self.assertIn(
            "ARM64_UI_COMMAND_LINE_CAPACITY = mm_DisplayCommand - ARM64_UI_COMMAND_LINE",
            header,
        )
        self.assertIn("append_application_argument", source)
        self.assertIn("publish_application_command_line();", source)
        self.assertIn("pUIWorkspace[mm_ProcessCommandLine] = 0", source)
        self.assertIn(
            "pUIWorkspace[ARM64_UI_COMMAND_LINE + index]",
            source,
        )
        self.assertIn("applicationCommandLineLength", source)
        self.assertIn("lino_display_set_origin", source)
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
        self.assertIn("lino_cocoa.m", build)
        self.assertIn("lino_file.c", build)
        self.assertIn("lino_globalK.c", build)
        self.assertIn("krnl_checked_globalK_command(", source)
        self.assertIn(
            "workspace_range_is_valid(pUIWorkspace[mm_GlobalKName], 24)",
            source,
        )
        self.assertIn(
            "workspace_range_is_valid(pUIWorkspace[mm_GlobalKData], 255)",
            source,
        )
        self.assertNotIn(
            "reject_unsupported_command(mm_GlobalKCommand)", source,
        )
        self.assertIn("lino_keyboard.c", build)
        self.assertIn("soundInitializationAttempted = true;", source)
        self.assertIn("(void) lino_sound_init();", source)
        self.assertIn("krnlPCMdataCommand(", source)
        self.assertIn("lino_sound_close()", source)
        self.assertLess(
            source.index("soundInitializationAttempted = true;"),
            source.index("linoleum();"),
        )
        self.assertLess(
            source.index("if (soundInitializationAttempted)"),
            source.index("release_mappings();"),
        )
        self.assertIn("lino_sound.c", build)
        self.assertIn("-framework AudioToolbox", build)
        self.assertIn("-framework Cocoa", build)
        self.assertNotIn("pagezero_size", build)

    def test_hosted_gate_compiles_and_executes_natively(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        compile_script = COMPILE_SCRIPT.read_text(encoding="utf-8")
        fixture = FIXTURE_SOURCE.read_text(encoding="utf-8")
        run_all = RUN_ALL.read_text(encoding="utf-8")

        self.assertEqual(workflow.count("runs-on: macos-15"), 2)
        self.assertIn("workflow_call:", workflow)
        self.assertIn("tagged_release:", workflow)
        self.assertIn('branches: ["**"]', workflow)
        self.assertIn("Derive native package versions", workflow)
        self.assertIn("inputs.package_artifact_name", workflow)
        self.assertIn("Upload publishable native package", workflow)
        self.assertIn("--cpu:aarch64", compile_script)
        self.assertIn("--sys:macarm64", compile_script)
        self.assertIn("tracked-work", compile_script)
        self.assertIn("compiled_complete", compile_script)
        self.assertEqual(compile_script.count("physwsentry != len(runtime)"), 2)
        self.assertEqual(
            compile_script.count("default_ramtop < app_ws_size + 32947"), 2,
        )
        self.assertNotIn("physwsentry < len(runtime)", compile_script)
        self.assertNotIn("default_ramtop < app_ws_size + 12", compile_script)
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
        self.assertIn("src/linoleum_macos64/lino_cocoa.m", workflow)
        self.assertIn("src/linoleum_macos64/lino_globalK.c", workflow)
        self.assertIn("src/linoleum_macos64/lino_globalK.h", workflow)
        self.assertIn("/Cocoa.framework/", workflow)
        self.assertIn("/AudioToolbox.framework/", workflow)
        self.assertIn("Compiled full Noctis AArch64 image", workflow)
        self.assertIn("finalize_macos_aarch64.py --sign", workflow)
        self.assertIn("arch -arm64 \"$output\"", workflow)
        self.assertIn("--cocoa-smoke", workflow)
        self.assertIn("COCOA_SMOKE_OK", workflow)
        self.assertIn("--cocoa-quit-smoke", workflow)
        self.assertIn("COCOA_QUIT_SMOKE_OK", workflow)
        self.assertIn("LLDB CRASH DIAGNOSTIC", workflow)
        self.assertIn("thread backtrace all", workflow)
        self.assertIn("package_noctis_macos_aarch64.py", workflow)
        self.assertIn("Noctis-IV-macos-arm64.zip", workflow)
        self.assertIn("Packaged native ARM64 app retrace", workflow)
        self.assertIn("--launcher-prepare-only", workflow)
        self.assertIn("CURRENT.LIN", workflow)
        self.assertIn("tools/make_noctis_checkpoint.py", workflow)
        self.assertIn("spec.get('clock', 1344638527)", workflow)
        self.assertIn('"case": "lunar-class1-sun50"', workflow)
        self.assertIn('"case": "lunar-class3-sun75"', workflow)
        self.assertIn('"scene": "lunarclass3"', workflow)
        self.assertIn('"case": "lunar-class4-sun135"', workflow)
        self.assertIn('"scene": "lunarclass4"', workflow)
        self.assertIn('"case": "lunar-class11-sun135"', workflow)
        self.assertIn('"scene": "lunarclass11"', workflow)
        self.assertIn('"case": "dense-class8-sun0"', workflow)
        self.assertIn('"scene": "denseclass8"', workflow)
        self.assertIn('"case": "rocky-class2-sun0"', workflow)
        self.assertIn('"scene": "rockyclass2"', workflow)
        self.assertIn('"clock": 1345636830', workflow)
        self.assertIn('"clock": 1345761727', workflow)
        self.assertIn('gallery / f"{spec[\'scene\']}-{name}"', workflow)
        self.assertIn("tests/test_sun_gallery.py", workflow)
        self.assertIn('"--product-directory", str(gallery)', workflow)
        self.assertIn("Retain native sun-oracle diagnostics", workflow)
        self.assertIn("Native compiler-owned AArch64 fixture passed", workflow)
        self.assertIn('arch -arm64 "$output" arm64-fixture', workflow)
        self.assertIn("macos-aarch64-fixture-home", workflow)
        self.assertIn("ARM64_GlobalK_fixture_", workflow)
        self.assertIn("Command Line Fixture = { arm64-fixture };", fixture)
        self.assertIn("A = Command Line;", fixture)
        self.assertIn("A + 9;", fixture)
        self.assertIn("compare command line fixture", fixture)
        self.assertIn("Global K Fixture Name", fixture)
        self.assertIn("[Global K Name] = FFFFFFFFh;", fixture)
        self.assertIn("[Global K Data] = FFFFFFFFh;", fixture)
        self.assertIn("[Global K Command] = K WRITE;", fixture)
        self.assertIn("[Global K Command] = K READ;", fixture)
        self.assertIn("[Global K Command] = K DESTROY;", fixture)
        self.assertIn("compare Global K fixture data", fixture)
        self.assertIn("modular extensions = audio playback;", fixture)
        self.assertIn("[PCM data Offset] = FFFFFFFFh;", fixture)
        self.assertIn("[PCM data Command] = GET DATA OFFSET;", fixture)
        self.assertIn("? failed -> audio service failed;", fixture)
        self.assertIn("A = 646F6E65h;", fixture)
        self.assertIn("C = [PCM data Channels];", fixture)
        self.assertIn("E = [PCM data Samples Per Sec];", fixture)
        self.assertIn("end;", fixture)
        self.assertEqual(run_all.count('(\"test_macos_aarch64_runtime.py\",'), 1)

    def test_arm64_package_metadata_and_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plist = root / "Info.plist"
            package.write_plist(plist, "0.1.0", "42", "test-build")
            values = plistlib.loads(plist.read_bytes())
            self.assertEqual(values["CFBundleIdentifier"], package.BUNDLE_ID)
            self.assertEqual(values["LSArchitecturePriority"], ["arm64"])
            self.assertEqual(
                values["LSMinimumSystemVersion"],
                package.DEPLOYMENT_TARGET,
            )

            provenance = root / "build.provenance.txt"
            provenance.write_text(
                "".join(
                    f"{key}=value\n"
                    for key in sorted(package.REQUIRED_BUILD_KEYS)
                ),
                encoding="ascii",
            )
            lines, records = package.read_build_provenance(provenance)
            self.assertEqual(len(lines), len(package.REQUIRED_BUILD_KEYS))
            self.assertEqual(set(records), package.REQUIRED_BUILD_KEYS)

            arm64 = root / "arm64"
            arm64.write_bytes(struct.pack("<II", finalize.MH_MAGIC_64,
                                          package.CPU_TYPE_ARM64))
            package.validate_arm64_macho(arm64)
            arm64.write_bytes(struct.pack("<II", finalize.MH_MAGIC_64, 7))
            with self.assertRaisesRegex(ValueError, "not arm64"):
                package.validate_arm64_macho(arm64)

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
        with self.assertRaisesRegex(finalize.ImageError,
                                    "truncated before physappsize"):
            finalize.normalize_linkedit(image[:-1])

        duplicate = bytearray(image)
        duplicate[0x2000:0x2008] = finalize.MARKER
        with self.assertRaisesRegex(finalize.ImageError, "exactly one LNLMInit"):
            finalize.normalize_linkedit(bytes(duplicate))

        bad_bounds = bytearray(image)
        paragraph = MARKER_OFFSET + len(finalize.MARKER) + 40
        struct.pack_into("<i", bad_bounds, paragraph + 4 * 4, APP_SIZE - 4)
        with self.assertRaisesRegex(finalize.ImageError, "physappsize"):
            finalize.normalize_linkedit(bytes(bad_bounds))

        bad_service_space = bytearray(image)
        struct.pack_into("<i", bad_service_space, paragraph + 5 * 4,
                         APP_WS_UNITS + SERVICE_UNITS - 1)
        with self.assertRaisesRegex(finalize.ImageError,
                                    "complete service workspace"):
            finalize.normalize_linkedit(bytes(bad_service_space))

        bad_pagezero = bytearray(image)
        struct.pack_into("<Q", bad_pagezero,
                         finalize.MACH_HEADER.size + 32, 0x4000000)
        with self.assertRaisesRegex(finalize.ImageError, "low 4 GiB"):
            finalize.normalize_linkedit(bytes(bad_pagezero))

        already_signed = signed_image()
        with self.assertRaisesRegex(finalize.ImageError,
                                    "already contains a code-signature"):
            finalize.normalize_linkedit(already_signed)

    def test_stock_resources_survive_normalization_and_signing(self) -> None:
        original = unsigned_image(STOCK_BYTES)
        normalized = finalize.normalize_linkedit(original)
        self.assertEqual(normalized[APP_SIZE:], STOCK_BYTES)
        self.assertEqual(finalize.lino_fields(normalized)[4], APP_SIZE)
        _header, commands = finalize.load_commands(normalized)
        _offset, values = finalize.linkedit_command(normalized, commands)
        self.assertEqual(int(values[6]), len(normalized) - int(values[5]))

        final = signed_image(STOCK_BYTES)
        self.assertEqual(final[APP_SIZE:APP_SIZE + len(STOCK_BYTES)],
                         STOCK_BYTES)
        finalize.validate_final(final)

    def test_final_validator_rejects_non_signature_suffixes(self) -> None:
        image = bytearray(signed_image(STOCK_BYTES))
        image.append(0)
        with self.assertRaisesRegex(finalize.ImageError,
                                    "exact final file suffix"):
            finalize.validate_final(bytes(image))


if __name__ == "__main__":
    unittest.main(verbosity=2)
