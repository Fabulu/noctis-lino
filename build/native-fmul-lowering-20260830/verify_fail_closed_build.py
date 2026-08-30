from pathlib import Path
import hashlib
import json
import shutil
import subprocess

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/native-fmul-lowering-20260830"
WORK_FPABI = ROOT / "work/fp/fpabi.txt"
WORK_FP = ROOT / "work/fp/fpsoft.txt"
WORK_GAME = ROOT / "work/vhgame.exe"
WORK_SOURCE = ROOT / "work/vhgame.txt"
ACCEPTED_FPABI_SHA256 = (
    "0c2f2602a82b9619d0bb909098857f804482456c504c2667874046be0598c7fd")
ACCEPTED_FP_SHA256 = (
    "063ecf40b0faab3b2779d8ff159b8fa815eec7b397de0d47e68223841e2a59cc")
CANDIDATE_FP_SHA256 = (
    "95417cf412787e6f33c773f4f7eb4d5d685f44fceff6b6e21649024b4d8d62dc")
ACCEPTED_GAME_SHA256 = (
    "e18e8eb45ac0bc03aa2ee1f51ce1ae54f6ee00a0e8a7cef24cbd3adebcdf32a0")
ACCEPTED_COMPILER_SHA256 = (
    "cfb39efc611dc96eab47f24c70cc7447a11f3b7cd874c49bfeb4934a42e67e87")
CANDIDATE_COMPILER_SHA256 = (
    "facfb8b9373c548c569771978606fcd5d5273760ec7b1e2f0b4ee6bcc30d2e78")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def run_case(name, fpabi, fpsoft):
    accepted_directory = EVIDENCE / f"failclosed-{name}-accepted"
    candidate_directory = EVIDENCE / f"failclosed-{name}-candidate"
    WORK_FPABI.write_bytes(fpabi)
    WORK_FP.write_bytes(fpsoft)
    accepted_record = build(
        EVIDENCE / "accepted/compiler114m.exe", accepted_directory)
    candidate_record = build(
        EVIDENCE / "candidate/compiler114m.exe", candidate_directory)
    accepted_output = accepted_directory / "vhgame.exe"
    candidate_output = candidate_directory / "vhgame.exe"
    assert accepted_output.read_bytes() == candidate_output.read_bytes()
    assert candidate_output.read_bytes().count(CANDIDATE_SCALAR) == 0
    return {
        "accepted_compiler": accepted_record,
        "candidate_compiler": candidate_record,
        "outputs_byte_exact": True,
        "output_sha256": digest(candidate_output),
        "output_bytes": candidate_output.stat().st_size,
        "generated_candidate_scalar_islands": 0,
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
candidate_fp = (EVIDENCE / "candidate/fpsoft.txt").read_bytes()
CANDIDATE_SCALAR = __import__("runpy").run_path(
    str(EVIDENCE / "apply_candidate.py"))["CANDIDATE_SCALAR"]

# Shift FA and every following ABI variable. This changes every operand-layout
# displacement in the accepted scalar island, so the complete-island gate fails.
fa_point = b"\tFA0\t= 0;"
fa_mutation = b"\tXSMFAILCLOSEFASHIFT = 0;\n" + fa_point
assert accepted_fpabi.count(fa_point) == 1
fa_shift_fpabi = accepted_fpabi.replace(fa_point, fa_mutation)
assert len(fa_shift_fpabi) > len(accepted_fpabi)
fa_fixture = EVIDENCE / "failclosed-fa-shift"
fa_fixture.mkdir(parents=True, exist_ok=True)
(fa_fixture / "fpabi.txt").write_bytes(fa_shift_fpabi)

# Keep FA/FB/XS/XU and the complete 122-byte island fixed, but insert one word
# after XU1 and before XREJ. Only the independently bound XREJ displacement in
# the fixed-back reject tail changes; this specifically exercises prerequisite 2.
xrej_point = (b"\tXU0 = 0; XU1 = 0;\t\t( binary64 input image, low/high )\n"
              b"\tXREJ = 0;")
xrej_mutation = (
    b"\tXU0 = 0; XU1 = 0;\t\t( binary64 input image, low/high )\n"
    b"\tXSMFAILCLOSEXREJSHIFT = 0;\n"
    b"\tXREJ = 0;")
assert candidate_fp.count(xrej_point) == 1
xrej_shift_fp = candidate_fp.replace(xrej_point, xrej_mutation)
assert len(xrej_shift_fp) > len(candidate_fp)
xrej_fixture = EVIDENCE / "failclosed-xrej-shift"
xrej_fixture.mkdir(parents=True, exist_ok=True)
(xrej_fixture / "fpsoft.txt").write_bytes(xrej_shift_fp)

records = {}
try:
    records["fa_shift"] = run_case("fa-shift", fa_shift_fpabi, candidate_fp)
    # Restore the ABI before the isolated XREJ-only shift.
    records["xrej_shift"] = run_case(
        "xrej-shift", accepted_fpabi, xrej_shift_fp)
finally:
    WORK_FPABI.write_bytes(accepted_fpabi)
    WORK_FP.write_bytes(accepted_fp)
    WORK_GAME.write_bytes(accepted_game)

assert digest(WORK_FPABI) == ACCEPTED_FPABI_SHA256
assert digest(WORK_FP) == ACCEPTED_FP_SHA256
assert digest(WORK_GAME) == ACCEPTED_GAME_SHA256
report = {
    "schema": 1,
    "task": 235,
    "status": "pass",
    "cases": {
        "fa_shift": {
            "mutation": "insert one fpabi variable before FA0",
            "complete_scalar_island_displacements_shifted": True,
            "accepted_and_candidate_compiler_outputs_byte_exact": True,
            "generated_candidate_scalar_islands": 0,
        },
        "xrej_shift": {
            "mutation": "insert one fpsoft variable between XU1 and XREJ",
            "fa_fb_xs_xu_and_scalar_island_layout_unchanged": True,
            "xrej_displacement_and_fixed_back_prerequisite_shifted": True,
            "accepted_and_candidate_compiler_outputs_byte_exact": True,
            "generated_candidate_scalar_islands": 0,
        },
    },
    "marker_bearing_common_fpsoft_used": True,
    "both_real_i386m_layout_controls_failed_closed": True,
    "private_inactive_desktop": True,
    "default_desktop": False,
    "production_restored": True,
    "records": records,
}
(EVIDENCE / "failclosed-layout-shifts.json").write_text(
    json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
