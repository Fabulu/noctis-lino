from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/native-fsqrt-lowering-20260830"
WORK_FP = ROOT / "work/fp/fpsoft.txt"
WORK_EXECUTABLE = ROOT / "work/vhgame.exe"
ARMS = ("candidate-a", "baseline-a", "baseline-b", "candidate-b")
ASSETS = (
    "globes.map",
    "offsets.map",
    "vehicle.ncc",
    "mammal.ncc",
    "birdy.ncc",
    "digimap2.bin",
    "STARMAP.BIN",
    "GUIDE.BIN",
    "noctis_music.pcm",
)
ACCEPTED_FP_SHA256 = (
    "063ecf40b0faab3b2779d8ff159b8fa815eec7b397de0d47e68223841e2a59cc")
CANDIDATE_FP_SHA256 = (
    "0628995a3ea891d23737c21757e747b1540c3dc1598991cb4380e815cac5bdf0")
ACCEPTED_EXE_SHA256 = (
    "e18e8eb45ac0bc03aa2ee1f51ce1ae54f6ee00a0e8a7cef24cbd3adebcdf32a0")
CANDIDATE_EXE_SHA256 = (
    "fadbad38814313b000698f591c060d91a53f3b6f701c65f67fbc5845d4d3a4c9")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def same_bytes(first, second):
    return (first.stat().st_size == second.stat().st_size
            and digest(first) == digest(second))


def load_report(arm):
    path = EVIDENCE / arm / "capsule/report.json"
    assert path.is_file()
    return json.loads(path.read_text(encoding="utf-8"))


def metrics(report):
    return report["metrics"]


parser = argparse.ArgumentParser()
parser.add_argument("arm", choices=ARMS)
args = parser.parse_args()
arm_index = ARMS.index(args.arm)
report_paths = [EVIDENCE / arm / "capsule/report.json" for arm in ARMS]
assert not report_paths[arm_index].exists()
assert all(path.is_file() for path in report_paths[:arm_index])
assert all(not path.exists() for path in report_paths[arm_index + 1:])

model = json.loads((EVIDENCE / "model.json").read_text(encoding="utf-8"))
layout = json.loads((EVIDENCE / "production-layout.json").read_text(
    encoding="utf-8"))
runtime = json.loads((EVIDENCE / "runtime-boundary.json").read_text(
    encoding="utf-8"))
review = json.loads((EVIDENCE / "semantic-review.json").read_text(
    encoding="utf-8"))
assert (model["status"] == layout["status"] == runtime["status"]
        == review["status"] == "pass")

# Enforce every binding early-stop gate before permitting a successor arm.
if arm_index >= 1:
    candidate_a = load_report("candidate-a")
    assert metrics(candidate_a)["simulation_hz"] >= 18.206
if arm_index >= 2:
    baseline_a = load_report("baseline-a")
    assert (metrics(candidate_a)["presentation_hz"]
            > metrics(baseline_a)["presentation_hz"])
    assert (metrics(candidate_a)["average_process_cycles_per_presentation"]
            < metrics(baseline_a)["average_process_cycles_per_presentation"])

kind = "candidate" if args.arm.startswith("candidate") else "accepted"
source = EVIDENCE / kind / "fpsoft.txt"
executable = EVIDENCE / kind / "vhgame.exe"
assert source.is_file() and executable.is_file()
expected_source = (CANDIDATE_FP_SHA256 if kind == "candidate"
                   else ACCEPTED_FP_SHA256)
expected_executable = (CANDIDATE_EXE_SHA256 if kind == "candidate"
                       else ACCEPTED_EXE_SHA256)
assert digest(source) == expected_source
assert digest(executable) == expected_executable
assert digest(WORK_FP) in {ACCEPTED_FP_SHA256, CANDIDATE_FP_SHA256}
assert digest(WORK_EXECUTABLE) in {ACCEPTED_EXE_SHA256, CANDIDATE_EXE_SHA256}
shutil.copyfile(source, WORK_FP)
shutil.copyfile(executable, WORK_EXECUTABLE)
assert same_bytes(source, WORK_FP)
assert same_bytes(executable, WORK_EXECUTABLE)

subprocess.run(
    [
        sys.executable,
        str(ROOT / "tools/profile_noctis_desktop.py"),
        "--scenario", "capsule",
        "--output-directory", str(EVIDENCE / args.arm),
        "--executable", str(WORK_EXECUTABLE),
        "--duration", "5",
        "--scheduling-control", "controlled",
        "--physical-core", "3",
    ],
    cwd=ROOT,
    check=True,
)
report_path = EVIDENCE / args.arm / "capsule/report.json"
report = json.loads(report_path.read_text(encoding="utf-8"))
assert report["schema"] == 2
assert report["scenario"] == "capsule"
assert report["requested_measurement_seconds"] == 5.0
assert report["command"][-2:] == ["clock=1344638527", "profile"]
assert report["provenance"]["executable_sha256"] == expected_executable
scheduling = report["provenance"]["scheduling"]
assert scheduling["comparable"]
assert scheduling["physical_core_index"] == 3
assert scheduling["requested_affinity_mask"] == "0xc0"
assert scheduling["requested_priority_class"] == "above_normal"
assert scheduling["actual"]["process_affinity_mask"] == "0xc0"
assert scheduling["actual"]["priority_class"] == "above_normal"

# Keep retained reports while hard-linking duplicated large canonical assets.
stage = report_path.parent
for name in ASSETS:
    canonical = ROOT / "work" / name
    duplicate = stage / name
    assert same_bytes(canonical, duplicate)
    duplicate.unlink()
    os.link(canonical, duplicate)
    assert same_bytes(canonical, duplicate)

print(json.dumps({
    "arm": args.arm,
    "kind": kind,
    "source_sha256": expected_source,
    "executable_sha256": expected_executable,
    "presentation_hz": report["metrics"]["presentation_hz"],
    "simulation_hz": report["metrics"]["simulation_hz"],
    "cycles_per_presentation": report["metrics"][
        "average_process_cycles_per_presentation"],
    "render_ms": report["metrics"]["average_render_ms"],
    "missed_deadlines": report["profile"]["missed_deadlines"],
}, indent=2))
