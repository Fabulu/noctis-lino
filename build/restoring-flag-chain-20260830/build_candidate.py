from pathlib import Path
import hashlib
import json
import runpy
import shutil
import subprocess
import time

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/restoring-flag-chain-20260830"
ACCEPTED = EVIDENCE / "accepted"
CANDIDATE = EVIDENCE / "candidate"
BUILD_ENTRY = ROOT / "lino_build.ps1"
LINO_ENV = ROOT / "main"
WORK_FP = ROOT / "work/fp/fpsoft.txt"
WORK_GAME_SOURCE = ROOT / "work/vhgame.txt"
WORK_GAME = ROOT / "work/vhgame.exe"
WORK_LOG = ROOT / "work/errorlog.txt"

apply = runpy.run_path(str(EVIDENCE / "apply_candidate.py"))
ACCEPTED_COMPILER_SOURCE_SHA256 = apply["ACCEPTED_COMPILER_SOURCE_SHA256"]
ACCEPTED_COMPILER_SHA256 = apply["ACCEPTED_COMPILER_SHA256"]
CPU_PACK_SHA256 = apply["CPU_PACK_SHA256"]
ACCEPTED_FP_SHA256 = apply["ACCEPTED_FP_SHA256"]
GAME_SOURCE_SHA256 = apply["GAME_SOURCE_SHA256"]
ACCEPTED_GAME_SHA256 = apply["ACCEPTED_GAME_SHA256"]


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def digest(path):
    return sha256(path.read_bytes())


def log_summary(path):
    if not path.is_file():
        return {"present": False, "warnings": 0, "errors": 0, "lines": 0}
    text = path.read_text(encoding="cp1252", errors="replace")
    lines = text.splitlines()
    return {
        "present": True,
        "warnings": sum("warning:" in line.lower() for line in lines),
        "errors": sum(
            "error:" in line.lower() or "internal problem:" in line.lower()
            for line in lines),
        "lines": len(lines),
    }


def build(source, compiler, evidence_name):
    destination = EVIDENCE / evidence_name
    destination.mkdir(parents=True, exist_ok=True)
    command = [
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", str(BUILD_ENTRY),
        "-Src", str(source),
        "-Compiler", str(compiler),
        "-LinoEnv", str(LINO_ENV),
        "-Cpu", "i386m",
        "-StageExtension", ".lxe",
    ]
    assert "-DefaultDesktop" not in command
    started = time.monotonic()
    completed = subprocess.run(
        command, cwd=ROOT, check=False, capture_output=True, text=True)
    elapsed = time.monotonic() - started
    output = completed.stdout + completed.stderr
    (destination / "build-output.txt").write_text(output, encoding="utf-8")
    assert completed.returncode == 0, output
    assert output.lstrip().startswith("OK "), output
    source_log = source.parent / "errorlog.txt"
    summary = log_summary(source_log)
    if source_log.is_file():
        shutil.copyfile(source_log, destination / "errorlog.txt")
    assert summary["errors"] == 0, summary
    output_exe = source.with_suffix(".exe")
    assert output_exe.is_file()
    return {
        "command": command,
        "private_inactive_desktop": True,
        "default_desktop": False,
        "elapsed_seconds": elapsed,
        "log": summary,
        "output": str(output_exe.relative_to(ROOT)).replace("\\", "/"),
        "output_bytes": output_exe.stat().st_size,
        "output_sha256": digest(output_exe),
    }


assert digest(ACCEPTED / "compiler114m.txt") == ACCEPTED_COMPILER_SOURCE_SHA256
assert digest(ACCEPTED / "compiler114m.exe") == ACCEPTED_COMPILER_SHA256
assert digest(ACCEPTED / "i386m.bin") == CPU_PACK_SHA256
assert digest(ACCEPTED / "fpsoft.txt") == ACCEPTED_FP_SHA256
assert digest(ACCEPTED / "vhgame.txt") == GAME_SOURCE_SHA256
assert digest(ACCEPTED / "vhgame.exe") == ACCEPTED_GAME_SHA256
assert digest(WORK_FP) == ACCEPTED_FP_SHA256
assert digest(WORK_GAME_SOURCE) == GAME_SOURCE_SHA256
assert digest(WORK_GAME) == ACCEPTED_GAME_SHA256
model = json.loads((EVIDENCE / "model.json").read_text(encoding="utf-8"))
assert model["status"] == "pass"

records = {}
try:
    # The common tracked Lino change is a zero-byte marker. The accepted compiler
    # must produce the retained game byte-for-byte when it sees that marker.
    shutil.copyfile(CANDIDATE / "fpsoft.txt", WORK_FP)
    records["marker_only_game"] = build(
        WORK_GAME_SOURCE, ACCEPTED / "compiler114m.exe", "marker-only")
    assert records["marker_only_game"]["output_sha256"] == ACCEPTED_GAME_SHA256
    shutil.copyfile(WORK_GAME, EVIDENCE / "marker-only/vhgame.exe")
    shutil.copyfile(ACCEPTED / "fpsoft.txt", WORK_FP)
    shutil.copyfile(ACCEPTED / "vhgame.exe", WORK_GAME)

    # Three private self-host stages establish a candidate-compiler fixpoint.
    compiler = ACCEPTED / "compiler114m.exe"
    for stage in range(1, 4):
        stage_dir = EVIDENCE / f"compiler-stage{stage}"
        stage_dir.mkdir(parents=True, exist_ok=True)
        stage_source = stage_dir / "compiler114m.txt"
        shutil.copyfile(CANDIDATE / "compiler114m.txt", stage_source)
        for library in ("bits.txt", "bytes.txt"):
            shutil.copyfile(ROOT / "main/lib/gen" / library, stage_dir / library)
        records[f"compiler_stage{stage}"] = build(
            stage_source, compiler, f"compiler-stage{stage}")
        compiler = stage_dir / "compiler114m.exe"
    assert digest(EVIDENCE / "compiler-stage1/compiler114m.exe") == digest(
        EVIDENCE / "compiler-stage2/compiler114m.exe")
    assert digest(EVIDENCE / "compiler-stage2/compiler114m.exe") == digest(
        EVIDENCE / "compiler-stage3/compiler114m.exe")
    shutil.copyfile(EVIDENCE / "compiler-stage3/compiler114m.exe",
                    CANDIDATE / "compiler114m.exe")

    # Build the actual candidate from the common work/vhgame.txt closure while
    # only the marker-bearing fpsoft source is active.
    shutil.copyfile(CANDIDATE / "fpsoft.txt", WORK_FP)
    records["candidate_game"] = build(
        WORK_GAME_SOURCE, CANDIDATE / "compiler114m.exe", "candidate-game")
    shutil.copyfile(WORK_GAME, CANDIDATE / "vhgame.exe")
finally:
    # Production remains the retained Task #224 pair until every gate passes.
    shutil.copyfile(ACCEPTED / "fpsoft.txt", WORK_FP)
    shutil.copyfile(ACCEPTED / "vhgame.exe", WORK_GAME)

assert digest(WORK_FP) == ACCEPTED_FP_SHA256
assert digest(WORK_GAME) == ACCEPTED_GAME_SHA256
assert records["candidate_game"]["log"]["errors"] == 0

report = {
    "schema": 1,
    "task": 231,
    "status": "pass",
    "build_entry": "lino_build.ps1",
    "private_inactive_desktop": True,
    "default_desktop": False,
    "cpu_pack_sha256": CPU_PACK_SHA256,
    "accepted_compiler_sha256": ACCEPTED_COMPILER_SHA256,
    "candidate_compiler_source_sha256": digest(CANDIDATE / "compiler114m.txt"),
    "candidate_compiler_sha256": digest(CANDIDATE / "compiler114m.exe"),
    "compiler_fixpoint_sha256": digest(
        EVIDENCE / "compiler-stage3/compiler114m.exe"),
    "compiler_three_stage_fixpoint": True,
    "marker_only_game_matches_accepted_byte_exactly": True,
    "candidate_fp_sha256": digest(CANDIDATE / "fpsoft.txt"),
    "candidate_game_bytes": (CANDIDATE / "vhgame.exe").stat().st_size,
    "candidate_game_sha256": digest(CANDIDATE / "vhgame.exe"),
    "production_restored": True,
    "records": records,
}
(EVIDENCE / "build.json").write_text(
    json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
