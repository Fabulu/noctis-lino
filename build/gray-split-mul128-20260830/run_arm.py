from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/gray-split-mul128-20260830"
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

# Enforce the binding early-stop gates before permitting the next arm.
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
allowed_sources = {
    digest(EVIDENCE / "accepted/fpsoft.txt"),
    digest(EVIDENCE / "candidate/fpsoft.txt"),
}
allowed_executables = {
    digest(EVIDENCE / "accepted/vhgame.exe"),
    digest(EVIDENCE / "candidate/vhgame.exe"),
}
assert digest(WORK_FP) in allowed_sources
assert digest(WORK_EXECUTABLE) in allowed_executables
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
assert report["provenance"]["executable_sha256"] == digest(executable)
scheduling = report["provenance"]["scheduling"]
assert scheduling["comparable"]
assert scheduling["physical_core_index"] == 3
assert scheduling["requested_affinity_mask"] == "0xc0"
assert scheduling["requested_priority_class"] == "above_normal"
assert scheduling["actual"]["process_affinity_mask"] == "0xc0"
assert scheduling["actual"]["priority_class"] == "above_normal"
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
    "source_sha256": digest(source),
    "executable_sha256": digest(executable),
    "presentation_hz": report["metrics"]["presentation_hz"],
    "simulation_hz": report["metrics"]["simulation_hz"],
    "cycles_per_presentation": report["metrics"][
        "average_process_cycles_per_presentation"],
    "render_ms": report["metrics"]["average_render_ms"],
    "missed_deadlines": report["profile"]["missed_deadlines"],
}, indent=2))
