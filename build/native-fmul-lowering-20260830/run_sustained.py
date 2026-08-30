from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/native-fmul-lowering-20260830"
SOURCE = EVIDENCE / "candidate/fpsoft.txt"
EXECUTABLE = EVIDENCE / "candidate/vhgame.exe"
WORK_SOURCE = ROOT / "work/fp/fpsoft.txt"
WORK_EXECUTABLE = ROOT / "work/vhgame.exe"
OUTPUT = EVIDENCE / "sustained-60s"
ASSETS = (
    "globes.map", "offsets.map", "vehicle.ncc", "mammal.ncc", "birdy.ncc",
    "digimap2.bin", "STARMAP.BIN", "GUIDE.BIN", "noctis_music.pcm",
)
EXPECTED_SOURCE = (
    "95417cf412787e6f33c773f4f7eb4d5d685f44fceff6b6e21649024b4d8d62dc")
EXPECTED_EXECUTABLE = (
    "70c7fc0a3f97270768eb86ea3ad30d18ffb2811fe07f821aff8ade7d2f2063d4")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def same_bytes(first, second):
    return (first.stat().st_size == second.stat().st_size
            and digest(first) == digest(second))


def load_arm(name):
    return json.loads((EVIDENCE / name / "capsule/report.json").read_text(
        encoding="utf-8"))["metrics"]


assert digest(SOURCE) == EXPECTED_SOURCE
assert digest(EXECUTABLE) == EXPECTED_EXECUTABLE
assert same_bytes(SOURCE, WORK_SOURCE)
assert same_bytes(EXECUTABLE, WORK_EXECUTABLE)
fidelity = json.loads((EVIDENCE / "fidelity.json").read_text(encoding="utf-8"))
assert fidelity["fidelity_verdict"]["status"] == "pass"
assert fidelity["fidelity_verdict"]["baseline_repeat_control"] == "pass"
candidate_a = load_arm("candidate-a")
baseline_a = load_arm("baseline-a")
baseline_b = load_arm("baseline-b")
candidate_b = load_arm("candidate-b")
for candidate in (candidate_a, candidate_b):
    assert candidate["simulation_hz"] >= 18.206
assert candidate_a["presentation_hz"] > baseline_a["presentation_hz"]
assert (candidate_a["average_process_cycles_per_presentation"]
        < baseline_a["average_process_cycles_per_presentation"])
assert candidate_b["presentation_hz"] > baseline_b["presentation_hz"]
assert (candidate_b["average_process_cycles_per_presentation"]
        < baseline_b["average_process_cycles_per_presentation"])

subprocess.run(
    [
        sys.executable,
        str(ROOT / "tools/profile_noctis_desktop.py"),
        "--scenario", "capsule",
        "--output-directory", str(OUTPUT),
        "--executable", str(WORK_EXECUTABLE),
        "--duration", "60",
        "--scheduling-control", "controlled",
        "--physical-core", "3",
    ],
    cwd=ROOT,
    check=True,
)
report_path = OUTPUT / "capsule/report.json"
report = json.loads(report_path.read_text(encoding="utf-8"))
assert report["requested_measurement_seconds"] == 60.0
assert report["command"][-2:] == ["clock=1344638527", "profile"]
assert report["provenance"]["executable_sha256"] == EXPECTED_EXECUTABLE
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
metrics = report["metrics"]
print(json.dumps({
    "presentation_hz": metrics["presentation_hz"],
    "simulation_hz": metrics["simulation_hz"],
    "cycles_per_presentation": metrics[
        "average_process_cycles_per_presentation"],
    "render_ms": metrics["average_render_ms"],
    "present_ms": metrics["average_present_ms"],
    "missed_deadlines": report["profile"]["missed_deadlines"],
    "presentations": report["profile"]["presentations"],
    "maximum_lateness_ms": metrics["maximum_lateness_ms"],
}, indent=2))
