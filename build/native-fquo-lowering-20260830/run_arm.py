from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/native-fquo-lowering-20260830"
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
    "95417cf412787e6f33c773f4f7eb4d5d685f44fceff6b6e21649024b4d8d62dc")
CANDIDATE_FP_SHA256 = (
    "6681e59e64835fc25ec87ec18387e4c448208cef7fd03040768ebb5c613c7c37")
ACCEPTED_EXE_SHA256 = (
    "70c7fc0a3f97270768eb86ea3ad30d18ffb2811fe07f821aff8ade7d2f2063d4")
CANDIDATE_EXE_SHA256 = (
    "fcb0b008c7d05e383a7759ec6978c7189aae669811c9b4348a511e31c93c5340")


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
build = json.loads((EVIDENCE / "build.json").read_text(encoding="utf-8"))
layout = json.loads((EVIDENCE / "production-layout.json").read_text(
    encoding="utf-8"))
failclosed = json.loads((EVIDENCE / "failclosed-layout-shifts.json").read_text(
    encoding="utf-8"))
runtime = json.loads((EVIDENCE / "runtime-boundary.json").read_text(
    encoding="utf-8"))
review = json.loads((EVIDENCE / "semantic-review.json").read_text(
    encoding="utf-8"))
assert all(item["status"] == "pass" for item in (
    model, build, layout, failclosed, runtime, review))
assert review["final_review"]["remaining_material_findings"] == 0

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
# Keep the common source, generated compiler source, compiler executable, and
# measured game executable on one rollback-protected accepted/candidate set.
subprocess.run(
    [sys.executable, str(EVIDENCE / "switch_production.py"), kind],
    cwd=ROOT,
    check=True,
)
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
