from pathlib import Path
import hashlib
import json
import shutil
import struct
import subprocess

from capstone import Cs, CS_ARCH_X86, CS_MODE_32

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/native-fsqrt-lowering-20260830"
WORK_FPABI = ROOT / "work/fp/fpabi.txt"
WORK_FP = ROOT / "work/fp/fpsoft.txt"
WORK_GAME = ROOT / "work/vhgame.exe"
WORK_SOURCE = ROOT / "work/vhgame.txt"
ACCEPTED_FPABI_SHA256 = (
    "0c2f2602a82b9619d0bb909098857f804482456c504c2667874046be0598c7fd")
ACCEPTED_FP_SHA256 = (
    "063ecf40b0faab3b2779d8ff159b8fa815eec7b397de0d47e68223841e2a59cc")
CANDIDATE_FP_SHA256 = (
    "0628995a3ea891d23737c21757e747b1540c3dc1598991cb4380e815cac5bdf0")
ACCEPTED_GAME_SHA256 = (
    "e18e8eb45ac0bc03aa2ee1f51ce1ae54f6ee00a0e8a7cef24cbd3adebcdf32a0")
ACCEPTED_COMPILER_SHA256 = (
    "cfb39efc611dc96eab47f24c70cc7447a11f3b7cd874c49bfeb4934a42e67e87")
CANDIDATE_COMPILER_SHA256 = (
    "b2f87e8b330fbd479f0bd7b4b8bf536fe4ac06849e6e1fea1f6401930a9f5435")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def lino_code(data):
    marker = data.index(b"LNLMInit")
    units = u32(data, marker + 0x34)
    end = u32(data, marker + 0x40)
    start = end - 4 * units
    return data[start:end], start


def build(compiler, directory):
    directory.mkdir(parents=True, exist_ok=True)
    command = [
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", str(ROOT / "lino_build.ps1"),
        "-Src", str(WORK_SOURCE),
        "-Compiler", str(compiler),
        "-LinoEnv", str(ROOT / "main"),
        "-Cpu", "i386m",
        "-StageExtension", ".lxe",
    ]
    assert "-DefaultDesktop" not in command
    completed = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, check=False)
    output = completed.stdout + completed.stderr
    (directory / "build-output.txt").write_text(output, encoding="utf-8")
    assert completed.returncode == 0, output
    assert output.lstrip().startswith("OK "), output
    shutil.copyfile(WORK_GAME, directory / "vhgame.exe")
    return {
        "command": command,
        "private_inactive_desktop": True,
        "default_desktop": False,
        "output_bytes": WORK_GAME.stat().st_size,
        "output_sha256": digest(WORK_GAME),
    }


assert digest(WORK_FPABI) == ACCEPTED_FPABI_SHA256
assert digest(WORK_FP) == ACCEPTED_FP_SHA256
assert digest(WORK_GAME) == ACCEPTED_GAME_SHA256
assert digest(EVIDENCE / "accepted/compiler114m.exe") == ACCEPTED_COMPILER_SHA256
assert digest(EVIDENCE / "candidate/compiler114m.exe") == CANDIDATE_COMPILER_SHA256
assert digest(EVIDENCE / "candidate/fpsoft.txt") == CANDIDATE_FP_SHA256

accepted_fpabi = WORK_FPABI.read_bytes()
accepted_fp = WORK_FP.read_bytes()
accepted_game = WORK_GAME.read_bytes()
mutation_point = b"\tFA0\t= 0;"
mutation = b"\tXSSFAILCLOSESHIFT = 0;\n" + mutation_point
assert accepted_fpabi.count(mutation_point) == 1
mutated_fpabi = accepted_fpabi.replace(mutation_point, mutation)
assert len(mutated_fpabi) > len(accepted_fpabi)
fixture = EVIDENCE / "failclosed-layout-shift"
fixture.mkdir(parents=True, exist_ok=True)
(EVIDENCE / "accepted/fpabi.txt").write_bytes(accepted_fpabi)
(fixture / "fpabi.txt").write_bytes(mutated_fpabi)

records = {}
try:
    WORK_FPABI.write_bytes(mutated_fpabi)
    shutil.copyfile(EVIDENCE / "candidate/fpsoft.txt", WORK_FP)
    records["accepted_compiler"] = build(
        EVIDENCE / "accepted/compiler114m.exe",
        EVIDENCE / "failclosed-layout-shift-accepted")
    records["candidate_compiler"] = build(
        EVIDENCE / "candidate/compiler114m.exe",
        EVIDENCE / "failclosed-layout-shift-candidate")
finally:
    WORK_FPABI.write_bytes(accepted_fpabi)
    WORK_FP.write_bytes(accepted_fp)
    WORK_GAME.write_bytes(accepted_game)

assert digest(WORK_FPABI) == ACCEPTED_FPABI_SHA256
assert digest(WORK_FP) == ACCEPTED_FP_SHA256
assert digest(WORK_GAME) == ACCEPTED_GAME_SHA256
accepted_shift = EVIDENCE / "failclosed-layout-shift-accepted/vhgame.exe"
candidate_shift = EVIDENCE / "failclosed-layout-shift-candidate/vhgame.exe"
assert accepted_shift.read_bytes() == candidate_shift.read_bytes()
code, base = lino_code(candidate_shift.read_bytes())
instructions = list(Cs(CS_ARCH_X86, CS_MODE_32).disasm(code, base))
assert instructions[-1].address + instructions[-1].size == base + len(code)
assert not [item for item in instructions if item.mnemonic == "fsqrt"]

report = {
    "schema": 1,
    "task": 233,
    "status": "pass",
    "mutation": "insert one fpabi variable before FA0",
    "fa_and_following_variable_layout_shifted": True,
    "marker_bearing_common_fpsoft_used": True,
    "accepted_and_candidate_compiler_outputs_byte_exact": True,
    "output_sha256": digest(candidate_shift),
    "output_bytes": candidate_shift.stat().st_size,
    "generated_fsqrt_instructions": 0,
    "context_gate_failed_closed_on_real_i386m_build": True,
    "private_inactive_desktop": True,
    "default_desktop": False,
    "production_restored": True,
    "records": records,
}
(EVIDENCE / "failclosed-layout-shift.json").write_text(
    json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
