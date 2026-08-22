#!/usr/bin/env python3
"""Build and execute the checked Linux AArch64 runtime bridge.

The default mode keeps the repository-wide suite useful without an installed
cross toolchain. CI and AArch64 developers use --require-execution so a missing
compiler, emulator, or execution leg is a failure.
"""

from __future__ import annotations

import os
from pathlib import Path
import platform
import re
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "src" / "linoleum_aarch64"
BUILD_SCRIPT = RUNTIME / "build.sh"
RTM_C = RUNTIME / "rtm.c"
RTM_H = RUNTIME / "rtm.h"
ISOKERNEL = RUNTIME / "isokernel.s"
README = RUNTIME / "README.md"
WORKFLOW = ROOT / ".github" / "workflows" / "linux-aarch64-runtime.yml"
RUN_ALL = ROOT / "tests" / "run_all.py"
COMPILER_SOURCE = ROOT / "main" / "lib" / "gen" / "compiler114m.txt"
COMPILER_BUILD_SCRIPT = ROOT / "build" / "build_compiler114m_linux.sh"
SYS_PACKER = ROOT / "tools" / "pack_lino_sys.py"
MARKER = b"LNLMInit"
END_MARKER = b"LNLMIend"
APP_WS_UNITS = 8
INITIAL_RAMTOP = 32
GROWN_RAMTOP = 48
UI_RAMTOP = 1
UI_ISOKERNEL_LO = 4
UI_ISOKERNEL_HI = 5
UI_CODE_ORIGIN_HI = 7
DONE = 0x646F6E65
FAIL = 0x6661696C
REGISTER_VALUES = (0x11223344, 0x89ABCDEF, 0x01020304, 0x7FFFFFFF, 0x80000000)
REQUIRE_EXECUTION = "--require-execution" in sys.argv
if REQUIRE_EXECUTION:
    sys.argv.remove("--require-execution")


COMPILER_FIXTURE_SOURCE = """\
"directors"

    unit = 32;
    program name = { AArch64 compiler fixture };

"variables"

    slot = 0;

"programme"

    A = 12345678h;
    B = A;
    [slot] = B;
    C = [slot];
    -> after skipped failure;
    fail;

"after skipped failure"

    A = [ramtop];
    isocall;
    ? failed -> failed call;
    ? ok -> successful call;
    fail;

"successful call"

    => helper;
    D = 89ABCDEFh;
    nop;
    end;

"failed call"

    fail;

"helper"

    E = 0BADF00Dh;
    leave;
"""


def all_offsets(data: bytes, needle: bytes) -> list[int]:
    offsets: list[int] = []
    start = 0
    while True:
        offset = data.find(needle, start)
        if offset < 0:
            return offsets
        offsets.append(offset)
        start = offset + 1


def unique_marker_offset(data: bytes) -> int:
    offsets = all_offsets(data, MARKER)
    if len(offsets) != 1:
        raise ValueError(f"expected one initialization marker, found {len(offsets)}")
    return offsets[0]


def words_to_bytes(words: list[int]) -> bytes:
    return b"".join(struct.pack("<I", word & 0xFFFFFFFF) for word in words)


def workspace_bytes(words: list[int]) -> bytes:
    return words_to_bytes(words)


def build_stock_image(template: bytes, code: bytes, initialized_workspace: bytes,
                      entry_unit: int, default_ramtop: int) -> bytes:
    if len(code) == 0 or len(code) % 4:
        raise ValueError("code must contain whole nonempty AArch64 instructions")
    if len(initialized_workspace) == 0 or len(initialized_workspace) % 4:
        raise ValueError("workspace must contain whole nonempty Linoleum units")

    marker = unique_marker_offset(template)
    paragraph = marker + len(MARKER)
    if paragraph + 96 > len(template):
        raise ValueError("initialization paragraph is truncated")

    app_ws_size = len(initialized_workspace) // 4
    app_code_size = len(code) // 4
    physical_workspace = len(template)
    physical_size = physical_workspace + len(initialized_workspace) + len(code)
    fields = (
        app_ws_size,
        app_code_size,
        entry_unit,
        physical_workspace,
        physical_size,
        default_ramtop,
        0, 0, 0, 0, 0, 0, 0, 0,
    )
    appname = b"AArch64 runtime fixture"
    patched = bytearray(template)
    patched[paragraph:paragraph + 40] = appname + bytes(40 - len(appname))
    patched[paragraph + 40:paragraph + 96] = struct.pack("<14i", *fields)
    return bytes(patched) + initialized_workspace + code


def patch_field(image: bytes, index: int, value: int) -> bytes:
    marker = unique_marker_offset(image)
    field_offset = marker + len(MARKER) + 40 + index * 4
    patched = bytearray(image)
    struct.pack_into("<i", patched, field_offset, value)
    return bytes(patched)


def compiler_image_parts(image: bytes) -> tuple[tuple[int, ...], bytes, bytes]:
    marker = unique_marker_offset(image)
    paragraph = marker + len(MARKER)
    if paragraph + 96 > len(image):
        raise ValueError("compiler image initialization paragraph is truncated")
    fields = struct.unpack_from("<14i", image, paragraph + 40)
    app_ws_size, app_code_size, entry_unit, physical_workspace = fields[:4]
    physical_size = fields[4]
    if min(app_ws_size, app_code_size, entry_unit, physical_workspace) < 0:
        raise ValueError("compiler image contains a negative layout field")
    if entry_unit >= app_code_size or physical_size != len(image):
        raise ValueError("compiler image has inconsistent physical bounds")
    code_start = physical_workspace + app_ws_size * 4
    code_end = code_start + app_code_size * 4
    if physical_workspace > code_start or code_end != physical_size:
        raise ValueError("compiler image payload does not match its unit counts")
    return fields, image[physical_workspace:code_start], image[code_start:code_end]


def write_executable(path: Path, contents: bytes) -> None:
    path.write_bytes(contents)
    path.chmod(0o755)


def enc_movz_w(register: int, immediate: int, shift: int = 0) -> int:
    return 0x52800000 | ((shift // 16) << 21) | ((immediate & 0xFFFF) << 5) | register


def enc_movk_w(register: int, immediate: int, shift: int = 0) -> int:
    return 0x72800000 | ((shift // 16) << 21) | ((immediate & 0xFFFF) << 5) | register


def enc_ldr_w(target: int, base: int, byte_offset: int) -> int:
    if byte_offset % 4 or not 0 <= byte_offset // 4 <= 4095:
        raise ValueError("W load offset is not encodable")
    return 0xB9400000 | ((byte_offset // 4) << 10) | (base << 5) | target


def enc_str_w(source: int, base: int, byte_offset: int) -> int:
    if byte_offset % 4 or not 0 <= byte_offset // 4 <= 4095:
        raise ValueError("W store offset is not encodable")
    return 0xB9000000 | ((byte_offset // 4) << 10) | (base << 5) | source


def enc_ldr_w_indexed(target: int) -> int:
    return 0xB8695B20 | target


def enc_str_w_indexed(source: int) -> int:
    return 0xB8295B20 | source


def enc_ldr_x(target: int, base: int, byte_offset: int) -> int:
    if byte_offset % 8 or not 0 <= byte_offset // 8 <= 4095:
        raise ValueError("X load offset is not encodable")
    return 0xF9400000 | ((byte_offset // 8) << 10) | (base << 5) | target


def enc_str_x(source: int, base: int, byte_offset: int) -> int:
    if byte_offset % 8 or not 0 <= byte_offset // 8 <= 4095:
        raise ValueError("X store offset is not encodable")
    return 0xF9000000 | ((byte_offset // 8) << 10) | (base << 5) | source


def enc_orr_lsl_x(destination: int, left: int, right: int, shift: int) -> int:
    if not 0 <= shift <= 63:
        raise ValueError("logical shift is not encodable")
    return (0xAA000000 | (right << 16) | (shift << 10) |
            (left << 5) | destination)


def enc_lsr_x(destination: int, source: int, shift: int) -> int:
    if not 1 <= shift <= 63:
        raise ValueError("right shift is not encodable")
    return (0xD3400000 | (shift << 16) | (63 << 10) |
            (source << 5) | destination)


def enc_cmp_w(left: int, right: int) -> int:
    return 0x6B00001F | (right << 16) | (left << 5)


def enc_cmp_x(left: int, right: int) -> int:
    return 0xEB00001F | (right << 16) | (left << 5)


def enc_blr(register: int) -> int:
    return 0xD63F0000 | (register << 5)


class Program:
    def __init__(self) -> None:
        self.words: list[int] = []
        self.labels: dict[str, int] = {}
        self.fixups: list[tuple[int, str, int, str]] = []

    def emit(self, word: int) -> None:
        self.words.append(word)

    def load_w(self, register: int, value: int) -> None:
        value &= 0xFFFFFFFF
        self.emit(enc_movz_w(register, value & 0xFFFF))
        if value >> 16:
            self.emit(enc_movk_w(register, value >> 16, 16))

    def label(self, name: str) -> None:
        if name in self.labels:
            raise ValueError(f"duplicate label {name}")
        self.labels[name] = len(self.words)

    def b_cond(self, condition: int, label: str) -> None:
        index = len(self.words)
        self.words.append(0)
        self.fixups.append((index, "condition", condition, label))

    def cbz_w(self, register: int, label: str) -> None:
        index = len(self.words)
        self.words.append(0)
        self.fixups.append((index, "cbz", register, label))

    def cbnz_w(self, register: int, label: str) -> None:
        index = len(self.words)
        self.words.append(0)
        self.fixups.append((index, "cbnz", register, label))

    def finish(self) -> list[int]:
        for index, kind, operand, label in self.fixups:
            if label not in self.labels:
                raise ValueError(f"undefined label {label}")
            delta = self.labels[label] - index
            if not -(1 << 18) <= delta < (1 << 18):
                raise ValueError("conditional branch is out of range")
            immediate = (delta & 0x7FFFF) << 5
            if kind == "condition":
                self.words[index] = 0x54000000 | immediate | operand
            elif kind == "cbz":
                self.words[index] = 0x34000000 | immediate | operand
            else:
                self.words[index] = 0x35000000 | immediate | operand
        return self.words


def return_fixture() -> tuple[bytes, int]:
    program = Program()
    program.emit(0xD4200000)  # BRK before the nonzero entry point.
    entry = len(program.words)
    for register, value in zip(range(19, 24), REGISTER_VALUES):
        program.load_w(register, value)
    program.load_w(24, 0x55667788)
    program.emit(0xD65F03C0)  # RET x30.
    return words_to_bytes(program.finish()), entry


def growth_fixture() -> tuple[bytes, int]:
    program = Program()
    program.emit(0xD4200000)
    entry = len(program.words)

    for register, value in zip(range(19, 24), REGISTER_VALUES):
        program.load_w(register, value)

    # Preserve the original full-width WS in initialized application units 4-5.
    program.emit(enc_str_x(25, 25, 4 * 4))
    program.load_w(9, GROWN_RAMTOP)
    program.emit(enc_str_w(9, 25, (APP_WS_UNITS + UI_RAMTOP) * 4))

    # Reconstruct and call the full-width isokernel pointer in UI units 4-5.
    program.emit(enc_ldr_w(9, 25, (APP_WS_UNITS + UI_ISOKERNEL_LO) * 4))
    program.emit(enc_ldr_w(10, 25, (APP_WS_UNITS + UI_ISOKERNEL_HI) * 4))
    program.emit(enc_orr_lsl_x(9, 9, 10, 32))
    program.emit(0xA9BF7BFD)  # STP x29,x30,[sp,#-16]!
    program.emit(enc_blr(9))
    program.emit(0xA8C17BFD)  # LDP x29,x30,[sp],#16

    # A real continuation marker also catches a lost or token-skipping LR.
    program.load_w(9, 0x13579BDF)
    program.emit(enc_str_w(9, 25, 3 * 4))

    # Relocation must change WS while preserving the old pointer and seed units.
    program.emit(enc_ldr_x(9, 25, 4 * 4))
    program.emit(enc_cmp_x(25, 9))
    program.b_cond(0, "fail")  # EQ
    program.emit(enc_ldr_w(9, 25, 2 * 4))
    program.load_w(10, 0x12345678)
    program.emit(enc_cmp_w(9, 10))
    program.b_cond(1, "fail")  # NE
    program.emit(enc_ldr_w(9, 25, 3 * 4))
    program.load_w(10, 0x13579BDF)
    program.emit(enc_cmp_w(9, 10))
    program.b_cond(1, "fail")

    # The designated Lino registers A-E survive the C boundary exactly.
    for register, value in zip(range(19, 24), REGISTER_VALUES):
        program.load_w(9, value)
        program.emit(enc_cmp_w(register, 9))
        program.b_cond(1, "fail")

    # Every newly added unit must be zero, not allocator residue.
    for index in range(INITIAL_RAMTOP, GROWN_RAMTOP):
        program.emit(enc_ldr_w(9, 25, index * 4))
        program.cbnz_w(9, "fail")

    # Both code and replacement workspace must actually exercise 64-bit addresses.
    program.emit(enc_ldr_w(9, 25,
                           (APP_WS_UNITS + UI_CODE_ORIGIN_HI) * 4))
    program.cbz_w(9, "fail")
    program.emit(enc_lsr_x(9, 25, 32))
    program.cbz_w(9, "fail")

    program.load_w(24, DONE)
    program.emit(0xD65F03C0)
    program.label("fail")
    program.load_w(24, FAIL)
    program.emit(0xD65F03C0)
    return words_to_bytes(program.finish()), entry


def find_tool(environment_name: str, candidates: tuple[str, ...]) -> str | None:
    configured = os.environ.get(environment_name)
    if configured:
        return shutil.which(configured) or configured
    for candidate in candidates:
        found = shutil.which(candidate)
        if found:
            return found
    return None


class StaticContractTests(unittest.TestCase):
    def test_disk_layout_and_full_width_slots(self) -> None:
        header = RTM_H.read_text(encoding="utf-8")
        self.assertIn("sizeof(struct LNLMINIT) == 96", header)
        self.assertIn("offsetof(struct LNLMINIT, app_ws_size) == 40", header)
        self.assertIn("ARM64_UI_ISOKERNEL_LO = 4", header)
        self.assertIn("ARM64_UI_CODE_ORIGIN_HI = 7", header)
        self.assertIn("ARM64_UI_REQUIRED_UNITS = 8", header)

    def test_memory_and_loader_policy(self) -> None:
        source = RTM_C.read_text(encoding="utf-8")
        self.assertNotIn("MAP_FIXED", source)
        self.assertNotIn("realloc(", source)
        self.assertNotIn("PROT_READ | PROT_WRITE | PROT_EXEC", source)
        self.assertIn("mprotect(pCode, pCodeMapBytes, PROT_READ | PROT_EXEC)", source)
        self.assertIn("memset(&new_workspace[old_ramtop], 0", source)
        self.assertIn("publish_runtime_pointers();", source)
        self.assertIn("expected_size != file_size", source)
        self.assertNotRegex(source, r"\(unit\)\s*\([^\n]*pCode")

    def test_assembly_abi_is_balanced(self) -> None:
        source = ISOKERNEL.read_text(encoding="utf-8")
        self.assertNotRegex(source, r"\bx18\b")
        self.assertEqual(source.count("stp     x29, x30, [sp, #-16]!"), 1)
        self.assertEqual(source.count("ldp     x29, x30, [sp], #16"), 1)
        self.assertIn("bl      ISOKRNLCALL", source)
        self.assertIsNotNone(re.search(
            r"bl\s+ISOKRNLCALL.*?ldr\s+x25, \[x9, :lo12:pWorkspace\]",
            source,
            re.DOTALL,
        ))
        self.assertIn("sub     sp, sp, #80", source)
        self.assertIn("add     sp, sp, #80", source)
        for register in range(19, 26):
            self.assertRegex(source, rf"\bx{register}\b")
        self.assertIn('.section .note.GNU-stack,"",%progbits', source)

    def test_build_and_documented_scope(self) -> None:
        build = BUILD_SCRIPT.read_text(encoding="utf-8")
        readme = README.read_text(encoding="utf-8")
        workflow = WORKFLOW.read_text(encoding="utf-8")
        run_all = RUN_ALL.read_text(encoding="utf-8")
        self.assertIn("-static -no-pie", build)
        self.assertIn("-Wl,-z,noexecstack", build)
        self.assertIn("aarch64-linux-gnu-gcc", build)
        self.assertIn("PR #10", readme)
        self.assertIn("not a full RTM", readme)
        self.assertIn("no Lino compiler emitter", readme)
        self.assertIn("gcc-aarch64-linux-gnu", workflow)
        self.assertIn("libc6-dev-arm64-cross qemu-user", workflow)
        self.assertIn("libc6:i386 libx11-6:i386", workflow)
        self.assertIn("build/build_compiler114m_linux.sh", workflow)
        self.assertIn("tools/pack_lino_sys.py", workflow)
        self.assertIn("test_aarch64_runtime.py --require-execution -v", workflow)
        self.assertEqual(run_all.count('(\"test_aarch64_runtime.py\",'), 1)

    def test_compiler_owns_the_minimal_aarch64_slice(self) -> None:
        source = COMPILER_SOURCE.read_text(encoding="utf-8")
        self.assertIn("aarch64 target = 1;", source)
        self.assertIn("? [aarch64 target] = yes -> cpu target ready;", source)
        self.assertGreaterEqual(
            source.count("? [aarch64 target] = yes -> pp aarch64;"), 2)
        self.assertIn("(always emits MOVZ+MOVK", source)
        for word in (
            "52800000h", "72A00000h", "2A0003E0h",
            "B8695B20h", "B8295B20h", "94000000h",
            "AA0B8149h", "D63F0120h", "D65F03C0h",
        ):
            self.assertIn(word, source)

    def test_instruction_encoders_pin_known_words(self) -> None:
        self.assertEqual(enc_movz_w(0, 1), 0x52800020)
        self.assertEqual(enc_blr(9), 0xD63F0120)
        self.assertEqual(enc_ldr_w(9, 25, 48), 0xB9403329)
        self.assertEqual(enc_str_x(25, 25, 16), 0xF9000B39)
        self.assertEqual(enc_lsr_x(9, 25, 32), 0xD360FF29)

    def test_fixture_builder_requires_one_marker(self) -> None:
        with self.assertRaisesRegex(ValueError, "found 0"):
            unique_marker_offset(b"no marker")
        with self.assertRaisesRegex(ValueError, "found 2"):
            unique_marker_offset(MARKER + b"gap" + MARKER)

        template = b"ELF" + MARKER + bytes(104)
        code, entry = return_fixture()
        workspace = workspace_bytes([0] * APP_WS_UNITS)
        image = build_stock_image(template, code, workspace, entry,
                                  INITIAL_RAMTOP)
        marker = unique_marker_offset(image)
        fields = struct.unpack_from("<14i", image, marker + 8 + 40)
        self.assertEqual(fields[0], APP_WS_UNITS)
        self.assertEqual(fields[2], entry)
        self.assertEqual(fields[3], len(template))
        self.assertEqual(fields[4], len(image))
        self.assertEqual(fields[5], INITIAL_RAMTOP)


class AArch64ExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.compiler = find_tool("AARCH64_CC", ("aarch64-linux-gnu-gcc",))
        cls.readelf = find_tool(
            "AARCH64_READELF",
            ("aarch64-linux-gnu-readelf", "readelf"),
        )
        cls.objdump = find_tool(
            "AARCH64_OBJDUMP",
            ("aarch64-linux-gnu-objdump", "objdump"),
        )
        cls.xvfb_run = find_tool("XVFB_RUN", ("xvfb-run",))
        cls.setarch = find_tool("SETARCH", ("setarch",))
        native = (platform.system() == "Linux" and
                  platform.machine().lower() in {"aarch64", "arm64"})
        cls.qemu = None if native else find_tool("QEMU_AARCH64", ("qemu-aarch64",))
        missing = []
        if cls.compiler is None:
            missing.append("aarch64-linux-gnu-gcc")
        if cls.readelf is None:
            missing.append("AArch64 readelf")
        if cls.objdump is None:
            missing.append("AArch64 objdump")
        if cls.xvfb_run is None:
            missing.append("xvfb-run")
        if cls.setarch is None:
            missing.append("setarch")
        if not native and cls.qemu is None:
            missing.append("qemu-aarch64")
        if missing:
            message = "AArch64 execution tools unavailable: " + ", ".join(missing)
            if REQUIRE_EXECUTION:
                raise AssertionError(message)
            raise unittest.SkipTest(message)

        cls.temporary = tempfile.TemporaryDirectory(prefix="lino-aarch64-test-")
        cls.temp = Path(cls.temporary.name)
        cls.runtime = cls.temp / "rtm-aarch64"
        environment = os.environ.copy()
        environment["CC"] = cls.compiler
        environment["BUILD_DIR"] = str(cls.temp / "build")
        environment["OUTPUT"] = str(cls.runtime)
        build = subprocess.run(
            ["bash", str(BUILD_SCRIPT)],
            cwd=ROOT,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=120,
        )
        if build.returncode != 0:
            raise AssertionError("AArch64 runtime build failed:\n" + build.stdout)
        cls.template = cls.runtime.read_bytes()
        if len(all_offsets(cls.template, MARKER)) != 1:
            raise AssertionError("built runtime does not contain one patch marker")

        cls.lino_compiler = cls.temp / "compiler114m-linux"
        compiler_build = subprocess.run(
            ["bash", str(COMPILER_BUILD_SCRIPT), str(cls.lino_compiler)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=180,
        )
        if compiler_build.returncode != 0:
            raise AssertionError(
                "AArch64 emitter compiler bootstrap failed:\n" +
                compiler_build.stdout)

        cls.lino_environment = cls.temp / "lino-environment"
        for directory in ("cpu", "lib", "sys"):
            shutil.copytree(ROOT / "main" / directory,
                            cls.lino_environment / directory)
        sys_directory = cls.lino_environment / "sys"
        cls.aarch64_sys = sys_directory / "aarch64.bin"
        packing = subprocess.run(
            [sys.executable, str(SYS_PACKER),
             str(cls.runtime), str(cls.aarch64_sys)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=30,
        )
        if packing.returncode != 0:
            raise AssertionError("AArch64 SYS packing failed:\n" + packing.stdout)

    @classmethod
    def tearDownClass(cls) -> None:
        temporary = getattr(cls, "temporary", None)
        if temporary is not None:
            temporary.cleanup()

    @classmethod
    def run_fixture(cls, path: Path) -> subprocess.CompletedProcess[str]:
        command = [str(path)] if cls.qemu is None else [cls.qemu, str(path)]
        return subprocess.run(
            command,
            cwd=cls.temp,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
        )

    @staticmethod
    def parse_result(stdout: str) -> dict[str, str]:
        lines = [line for line in stdout.splitlines()
                 if line.startswith("AARCH64_RUNTIME_RESULT ")]
        if len(lines) != 1:
            raise AssertionError(f"expected one runtime result, got {stdout!r}")
        return dict(field.split("=", 1) for field in lines[0].split()[1:])

    @classmethod
    def compile_lino_source(cls, name: str, source_text: str) -> bytes:
        source = cls.temp / f"{name}.txt"
        output = source.with_suffix(".bin")
        error_log = source.parent / "errorlog.txt"
        source.write_text(source_text, encoding="ascii", newline="\n")
        output.unlink(missing_ok=True)
        error_log.unlink(missing_ok=True)

        argument = (
            f"--sys:aarch64--cpu:aarch64--ext:.bin"
            f"--env:{cls.lino_environment}--src:{source}"
        )
        process = subprocess.Popen(
            [cls.xvfb_run, "-a", cls.setarch, platform.machine(), "-X",
             str(cls.lino_compiler), argument],
            cwd=source.parent,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        previous: tuple[tuple[int, int], tuple[int, int] | None] | None = None
        stable = 0
        fatal_log = ""
        settled = False
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            log_state = None
            if error_log.exists():
                log_stat = error_log.stat()
                log_state = (log_stat.st_size, log_stat.st_mtime_ns)
                fatal_log = error_log.read_text(
                    encoding="utf-8", errors="replace")
                if re.search(r"error:|internal problem:", fatal_log,
                             re.IGNORECASE):
                    break
            if output.exists() and output.stat().st_size:
                output_stat = output.stat()
                current = ((output_stat.st_size, output_stat.st_mtime_ns),
                           log_state)
                stable = stable + 1 if current == previous else 1
                previous = current
                if stable >= 5:
                    settled = True
                    break
            else:
                previous = None
                stable = 0
            if process.poll() is not None and not output.exists():
                break
            time.sleep(0.25)

        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
        compiler_output = process.communicate()[0]
        if not settled:
            raise AssertionError(
                "AArch64 Lino compilation did not settle "
                f"(returncode={process.returncode}, "
                f"output={output}, output_exists={output.exists()}, "
                f"sys_bytes={cls.aarch64_sys.stat().st_size}):\n" +
                compiler_output + fatal_log)
        return output.read_bytes()

    def make_fixture(self, name: str, code: bytes, entry: int,
                     workspace: bytes, ramtop: int) -> Path:
        path = self.temp / name
        image = build_stock_image(self.template, code, workspace, entry, ramtop)
        write_executable(path, image)
        return path

    def test_elf_is_static_nonpie_aarch64_with_nonexec_stack(self) -> None:
        header = subprocess.run(
            [self.readelf, "-h", str(self.runtime)], check=True,
            text=True, stdout=subprocess.PIPE,
        ).stdout
        segments = subprocess.run(
            [self.readelf, "-lW", str(self.runtime)], check=True,
            text=True, stdout=subprocess.PIPE,
        ).stdout
        dynamic = subprocess.run(
            [self.readelf, "-d", str(self.runtime)],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        ).stdout
        disassembly = subprocess.run(
            [self.objdump, "-d", str(self.runtime)], check=True,
            text=True, stdout=subprocess.PIPE,
        ).stdout

        self.assertRegex(header, r"Machine:\s+AArch64")
        self.assertRegex(header, r"Type:\s+EXEC")
        self.assertNotIn("INTERP", segments)
        stack_lines = [line for line in segments.splitlines()
                       if "GNU_STACK" in line]
        self.assertEqual(len(stack_lines), 1)
        self.assertRegex(stack_lines[0], r"\bRW\b")
        self.assertNotIn("RWE", stack_lines[0])
        self.assertIn("There is no dynamic section", dynamic)
        self.assertIn("<isokernel>", disassembly)
        self.assertIn("<linoleum>", disassembly)
        bridge_bodies = []
        for symbol in ("isokernel", "linoleum"):
            match = re.search(
                rf"(?m)^[0-9a-f]+ <{symbol}>:\n(?P<body>.*?)(?=^[0-9a-f]+ <|\Z)",
                disassembly,
                re.DOTALL,
            )
            self.assertIsNotNone(match, f"missing disassembly body for {symbol}")
            bridge_bodies.append(match.group("body"))
        self.assertNotRegex("\n".join(bridge_bodies), r"\bx18\b")

    def test_compiler_produced_image_executes_full_integer_slice(self) -> None:
        image = self.compile_lino_source(
            "compiler-aarch64-fixture", COMPILER_FIXTURE_SOURCE)
        fields, initialized_workspace, code = compiler_image_parts(image)
        app_ws_size, app_code_size, entry_unit = fields[:3]
        default_ramtop = fields[5]
        self.assertGreaterEqual(app_ws_size, 2)
        self.assertEqual(len(initialized_workspace), app_ws_size * 4)
        self.assertEqual(len(code), app_code_size * 4)
        self.assertEqual(entry_unit, 0)
        self.assertGreater(default_ramtop, app_ws_size + 7)

        code_words = list(struct.unpack(f"<{app_code_size}I", code))
        immediate_a = [
            enc_movz_w(19, 0x5678),
            enc_movk_w(19, 0x1234, 16),
        ]
        self.assertIn(words_to_bytes(immediate_a), code)
        self.assertIn(0x2A0003E0 | (19 << 16) | 20, code_words)
        self.assertIn(words_to_bytes([
            enc_movz_w(9, 0), enc_movk_w(9, 0, 16),
            enc_str_w_indexed(20),
        ]), code)
        self.assertIn(words_to_bytes([
            enc_movz_w(9, 0), enc_movk_w(9, 0, 16),
            enc_ldr_w_indexed(21),
        ]), code)

        isocall_words = [
            enc_movz_w(9, app_ws_size + UI_ISOKERNEL_LO),
            enc_movk_w(9, 0, 16),
            enc_ldr_w_indexed(10),
            enc_movz_w(9, app_ws_size + UI_ISOKERNEL_HI),
            enc_movk_w(9, 0, 16),
            enc_ldr_w_indexed(11),
            enc_orr_lsl_x(9, 10, 11, 32),
            0xA9BF7BFD,
            enc_blr(9),
            0xA8C17BFD,
        ]
        self.assertIn(words_to_bytes(isocall_words), code)
        self.assertTrue(any(
            code_words[index] == 0xA9BF7BFD and
            code_words[index + 1] & 0xFC000000 == 0x94000000 and
            code_words[index + 2] == 0xA8C17BFD
            for index in range(len(code_words) - 2)
        ), "compiler call did not preserve x29/x30 around BL")

        fixture = self.temp / "compiler-produced-aarch64"
        write_executable(fixture, image)
        run = self.run_fixture(fixture)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertEqual(run.stderr, "")
        result = self.parse_result(run.stdout)
        self.assertEqual(result["status"], "0")
        self.assertEqual(result["A"], f"{default_ramtop:08X}")
        self.assertEqual(result["B"], "12345678")
        self.assertEqual(result["C"], "12345678")
        self.assertEqual(result["D"], "89ABCDEF")
        self.assertEqual(result["E"], "0BADF00D")
        self.assertEqual(result["X"], f"{DONE:08X}")
        self.assertEqual(result["ramtop"], f"{default_ramtop:08X}")
        self.assertGreater(int(result["code"], 16), 0xFFFFFFFF)
        self.assertGreater(int(result["workspace"], 16), 0xFFFFFFFF)

    def test_nonzero_entry_returns_exact_registers(self) -> None:
        code, entry = return_fixture()
        fixture = self.make_fixture(
            "return-fixture", code, entry,
            workspace_bytes([0] * APP_WS_UNITS), INITIAL_RAMTOP,
        )
        run = self.run_fixture(fixture)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertEqual(run.stderr, "")
        result = self.parse_result(run.stdout)
        self.assertEqual(result["status"], "0")
        for name, value in zip("ABCDE", REGISTER_VALUES):
            self.assertEqual(result[name], f"{value:08X}")
        self.assertEqual(result["X"], "55667788")
        self.assertGreater(int(result["code"], 16), 0xFFFFFFFF)
        self.assertGreater(int(result["workspace"], 16), 0xFFFFFFFF)
        self.assertEqual(result["ramtop"], f"{INITIAL_RAMTOP:08X}")

    def test_isocall_relocates_and_zeroes_workspace(self) -> None:
        code, entry = growth_fixture()
        initial = [0] * APP_WS_UNITS
        initial[2] = 0x12345678
        fixture = self.make_fixture(
            "growth-fixture", code, entry, workspace_bytes(initial),
            INITIAL_RAMTOP,
        )
        run = self.run_fixture(fixture)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertEqual(run.stderr, "")
        result = self.parse_result(run.stdout)
        self.assertEqual(result["status"], "0")
        for name, value in zip("ABCDE", REGISTER_VALUES):
            self.assertEqual(result[name], f"{value:08X}")
        self.assertEqual(result["X"], f"{DONE:08X}")
        self.assertEqual(result["ramtop"], f"{GROWN_RAMTOP:08X}")
        self.assertGreater(int(result["code"], 16), 0xFFFFFFFF)
        self.assertGreater(int(result["workspace"], 16), 0xFFFFFFFF)

    def test_malformed_images_fail_before_entry(self) -> None:
        code, entry = return_fixture()
        workspace = workspace_bytes([0] * APP_WS_UNITS)
        valid = build_stock_image(self.template, code, workspace, entry,
                                  INITIAL_RAMTOP)
        code_units = len(code) // 4
        cases = {
            "truncated": valid[:-4],
            "negative-workspace": patch_field(valid, 0, -1),
            "negative-code": patch_field(valid, 1, -1),
            "entry-outside-code": patch_field(valid, 2, code_units),
            "impossible-payload-origin": patch_field(valid, 3, 0x7FFFFFFF),
            "wrong-physical-size": patch_field(valid, 4, len(valid) - 4),
            "insufficient-ui": patch_field(valid, 5,
                                             APP_WS_UNITS + 7),
        }
        for name, image in cases.items():
            with self.subTest(name=name):
                path = self.temp / f"malformed-{name}"
                write_executable(path, image)
                run = self.run_fixture(path)
                self.assertNotEqual(run.returncode, 0, run.stdout + run.stderr)
                self.assertNotIn("AARCH64_RUNTIME_RESULT", run.stdout)
                self.assertIn("AARCH64_RUNTIME_ERROR:", run.stderr)


def main() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    verbosity = 2 if "-v" in sys.argv or "--verbose" in sys.argv else 1
    result = unittest.TextTestRunner(verbosity=verbosity).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
