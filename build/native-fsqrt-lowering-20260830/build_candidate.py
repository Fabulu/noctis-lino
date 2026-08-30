from pathlib import Path
import hashlib
import json
import runpy
import shutil
import subprocess
import time

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/native-fsqrt-lowering-20260830"
ACCEPTED = EVIDENCE / "accepted"
CANDIDATE = EVIDENCE / "candidate"
BUILD_ENTRY = ROOT / "lino_build.ps1"
LINO_ENV = ROOT / "main"
WORK_FP = ROOT / "work/fp/fpsoft.txt"
WORK_GAME_SOURCE = ROOT / "work/vhgame.txt"
WORK_GAME = ROOT / "work/vhgame.exe"

apply = runpy.run_path(str(EVIDENCE / "apply_candidate.py"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def build(source, compiler, cpu, evidence_name):
    destination = EVIDENCE / evidence_name
    destination.mkdir(parents=True, exist_ok=True)
    command = [
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", str(BUILD_ENTRY),
        "-Src", str(source),
        "-Compiler", str(compiler),
        "-LinoEnv", str(LINO_ENV),
        "-Cpu", cpu,
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
        "cpu": cpu,
        "private_inactive_desktop": True,
        "default_desktop": False,
        "elapsed_seconds": elapsed,
        "log": summary,
        "output_bytes": output_exe.stat().st_size,
        "output_sha256": digest(output_exe),
    }


assert digest(ACCEPTED / "compiler114m.txt") == apply[
    "ACCEPTED_COMPILER_SOURCE_SHA256"]
assert digest(ACCEPTED / "compiler114m.exe") == apply["ACCEPTED_COMPILER_SHA256"]
assert digest(ACCEPTED / "i386m.bin") == apply["I386M_PACK_SHA256"]
assert digest(ACCEPTED / "i386.bin") == apply["I386_PACK_SHA256"]
assert digest(ACCEPTED / "x64.bin") == apply["X64_PACK_SHA256"]
assert digest(ACCEPTED / "fpsoft.txt") == apply["ACCEPTED_FP_SHA256"]
assert digest(ACCEPTED / "vhgame.txt") == apply["GAME_SOURCE_SHA256"]
assert digest(ACCEPTED / "vhgame.exe") == apply["ACCEPTED_GAME_SHA256"]
assert digest(WORK_FP) == apply["ACCEPTED_FP_SHA256"]
assert digest(WORK_GAME_SOURCE) == apply["GAME_SOURCE_SHA256"]
assert digest(WORK_GAME) == apply["ACCEPTED_GAME_SHA256"]
model = json.loads((EVIDENCE / "model.json").read_text(encoding="utf-8"))
assert model["status"] == "pass"

records = {}
try:
    # The accepted compiler must ignore the zero-byte marker byte-exactly.
    shutil.copyfile(CANDIDATE / "fpsoft.txt", WORK_FP)
    records["marker_only_i386m"] = build(
        WORK_GAME_SOURCE, ACCEPTED / "compiler114m.exe", "i386m",
        "marker-only-i386m")
    assert records["marker_only_i386m"]["output_sha256"] == apply[
        "ACCEPTED_GAME_SHA256"]
    shutil.copyfile(WORK_GAME, EVIDENCE / "marker-only-i386m/vhgame.exe")
    shutil.copyfile(ACCEPTED / "fpsoft.txt", WORK_FP)
    shutil.copyfile(ACCEPTED / "vhgame.exe", WORK_GAME)

    # Three self-host stages establish the candidate compiler fixpoint.
    compiler = ACCEPTED / "compiler114m.exe"
    for stage in range(1, 4):
        stage_dir = EVIDENCE / f"compiler-stage{stage}"
        stage_dir.mkdir(parents=True, exist_ok=True)
        stage_source = stage_dir / "compiler114m.txt"
        shutil.copyfile(CANDIDATE / "compiler114m.txt", stage_source)
        for library in ("bits.txt", "bytes.txt"):
            shutil.copyfile(ROOT / "main/lib/gen" / library, stage_dir / library)
        records[f"compiler_stage{stage}"] = build(
            stage_source, compiler, "i386m", f"compiler-stage{stage}")
        compiler = stage_dir / "compiler114m.exe"
    stage_hashes = [digest(EVIDENCE / f"compiler-stage{stage}/compiler114m.exe")
                    for stage in range(1, 4)]
    assert len(set(stage_hashes)) == 1
    shutil.copyfile(EVIDENCE / "compiler-stage3/compiler114m.exe",
                    CANDIDATE / "compiler114m.exe")

    # Build the selected i386m candidate from the common tracked closure.
    shutil.copyfile(CANDIDATE / "fpsoft.txt", WORK_FP)
    records["candidate_i386m"] = build(
        WORK_GAME_SOURCE, CANDIDATE / "compiler114m.exe", "i386m",
        "candidate-i386m")
    shutil.copyfile(WORK_GAME, CANDIDATE / "vhgame.exe")

    # Empirically prove suppression on the non-i386m x64 target. Both compilers
    # see the exact same marker-bearing common source and CPU pack.
    records["accepted_compiler_x64"] = build(
        WORK_GAME_SOURCE, ACCEPTED / "compiler114m.exe", "x64",
        "accepted-compiler-x64")
    shutil.copyfile(WORK_GAME, EVIDENCE / "accepted-compiler-x64/vhgame.exe")
    records["candidate_compiler_x64"] = build(
        WORK_GAME_SOURCE, CANDIDATE / "compiler114m.exe", "x64",
        "candidate-compiler-x64")
    shutil.copyfile(WORK_GAME, EVIDENCE / "candidate-compiler-x64/vhgame.exe")
    assert records["accepted_compiler_x64"]["output_sha256"] == records[
        "candidate_compiler_x64"]["output_sha256"]
    assert (EVIDENCE / "accepted-compiler-x64/vhgame.exe").read_bytes() == (
        EVIDENCE / "candidate-compiler-x64/vhgame.exe").read_bytes()
finally:
    shutil.copyfile(ACCEPTED / "fpsoft.txt", WORK_FP)
    shutil.copyfile(ACCEPTED / "vhgame.exe", WORK_GAME)

assert digest(WORK_FP) == apply["ACCEPTED_FP_SHA256"]
assert digest(WORK_GAME) == apply["ACCEPTED_GAME_SHA256"]
report = {
    "schema": 1,
    "task": 233,
    "status": "pass",
    "build_entry": "lino_build.ps1",
    "private_inactive_desktop": True,
    "default_desktop": False,
    "accepted_compiler_sha256": apply["ACCEPTED_COMPILER_SHA256"],
    "candidate_compiler_source_sha256": digest(CANDIDATE / "compiler114m.txt"),
    "candidate_compiler_sha256": digest(CANDIDATE / "compiler114m.exe"),
    "compiler_fixpoint_sha256": stage_hashes[-1],
    "compiler_three_stage_fixpoint": True,
    "marker_only_i386m_matches_accepted_byte_exactly": True,
    "candidate_fp_sha256": digest(CANDIDATE / "fpsoft.txt"),
    "candidate_i386m_game_bytes": (CANDIDATE / "vhgame.exe").stat().st_size,
    "candidate_i386m_game_sha256": digest(CANDIDATE / "vhgame.exe"),
    "non_i386m_output_comparison_run": True,
    "non_i386m_cpu": "x64",
    "non_i386m_output_bytes": (EVIDENCE / "candidate-compiler-x64/vhgame.exe").stat().st_size,
    "non_i386m_output_sha256": digest(
        EVIDENCE / "candidate-compiler-x64/vhgame.exe"),
    "non_i386m_outputs_byte_exact": True,
    "production_restored": True,
    "records": records,
}
(EVIDENCE / "build.json").write_text(
    json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
