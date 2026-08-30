from pathlib import Path
import hashlib
import json
import runpy
import shutil

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/dead-fixed-f64-fi-stores-20260830"
REQUIRED_SIMULATION_HZ = 18.206


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(relative):
    return json.loads((EVIDENCE / relative).read_text(encoding="utf-8"))


def arm_metrics(report):
    return {
        "presentation_hz": report["metrics"]["presentation_hz"],
        "simulation_hz": report["metrics"]["simulation_hz"],
        "cycles_per_presentation": report["metrics"][
            "average_process_cycles_per_presentation"],
        "render_ms": report["metrics"]["average_render_ms"],
        "missed_deadlines": report["profile"]["missed_deadlines"],
    }


def validate_arm(report, executable_sha256):
    assert report["scenario"] == "capsule"
    assert report["command"][-2:] == ["clock=1344638527", "profile"]
    assert report["requested_measurement_seconds"] == 5.0
    assert report["provenance"]["executable_sha256"] == executable_sha256
    scheduling = report["provenance"]["scheduling"]
    assert scheduling["comparable"]
    assert scheduling["physical_core_index"] == 3
    assert scheduling["requested_affinity_mask"] == "0xc0"
    assert scheduling["requested_priority_class"] == "above_normal"
    assert scheduling["actual"]["process_affinity_mask"] == "0xc0"
    assert scheduling["actual"]["priority_class"] == "above_normal"


accepted_source = EVIDENCE / "accepted/vhgame.txt"
accepted_executable = EVIDENCE / "accepted/vhgame.exe"
candidate_source = EVIDENCE / "candidate/vhgame.txt"
candidate_executable = EVIDENCE / "candidate/vhgame.exe"
accepted_source_sha256 = digest(accepted_source)
accepted_executable_sha256 = digest(accepted_executable)
candidate_source_sha256 = digest(candidate_source)
candidate_executable_sha256 = digest(candidate_executable)
assert accepted_source_sha256 == "f1af20ebd55b80e3a1439b0e30f1bb4e0bdcc8e00b7aced1a7b34d7395d3dc25"
assert accepted_executable_sha256 == "81900287fa9e19291a27667b0e23d5c0c6324e86e8b9d8da0ff82a65cc302823"
assert candidate_source_sha256 == "2e9ee626a34b2dc2ed90006e184c7a00363a5a3b29d6563dc4853db42f2c0385"
assert candidate_executable_sha256 == "faf9eac8ab68b6f18dd0d51920f7fb98446579166ffdd1e7300ab91972402227"
transform = runpy.run_path(str(EVIDENCE / "apply_candidate.py"))["transform"]
assert candidate_source.read_bytes() == transform(accepted_source.read_bytes())

model = load("model.json")
semantic_review = load("semantic-review.json")
build = load("build.json")
production_layout = load("production-layout.json")
assert model["status"] == "pass" and model["direct_fb_sites"] == 10
assert model["retained_fi_and_helper_sites"] == 1
assert model["candidate_file_equals_exact_transform"]
assert model["direct_fb_words_exact"]
assert model["first_fi_observer_preceded_by_fcmp"]
assert model["ring_terminal_fi_store_retained"]
assert semantic_review["status"] == "pass"
assert semantic_review["remaining_observable_mismatches"] == []
assert build["status"] == "pass"
assert build["private_inactive_desktop"]
assert build["entry_point"] == "lino_build.ps1"
assert build["candidate_executable_sha256"] == candidate_executable_sha256
assert production_layout["status"] == "pass"
assert production_layout["direct_fb_sites"] == 10
assert production_layout["normalized_instruction_stream_exact"]
assert production_layout["unexpected_noncontrol_instruction_changes"] == 0
assert production_layout["external_direct_entries_to_site_interiors"] == 0
assert production_layout["ring_fi_store_retained"]
assert production_layout["helper_generated_shape_exact"]

candidate_report = load("candidate-a/capsule/report.json")
baseline_report = load("baseline-a/capsule/report.json")
validate_arm(candidate_report, candidate_executable_sha256)
validate_arm(baseline_report, accepted_executable_sha256)
metrics = {
    "candidate-a": arm_metrics(candidate_report),
    "baseline-a": arm_metrics(baseline_report),
}
assert metrics["candidate-a"]["simulation_hz"] >= REQUIRED_SIMULATION_HZ
assert metrics["baseline-a"]["simulation_hz"] >= REQUIRED_SIMULATION_HZ
ordering_a = {
    "status": "loss",
    "presentation_gain_hz": (
        metrics["candidate-a"]["presentation_hz"] -
        metrics["baseline-a"]["presentation_hz"]),
    "cycles_per_presentation_removed": (
        metrics["baseline-a"]["cycles_per_presentation"] -
        metrics["candidate-a"]["cycles_per_presentation"]),
}
assert ordering_a["presentation_gain_hz"] < 0
assert ordering_a["cycles_per_presentation_removed"] < 0
assert not (EVIDENCE / "baseline-b").exists()
assert not (EVIDENCE / "candidate-b").exists()
assert not (EVIDENCE / "fidelity").exists()

work_source = ROOT / "work/vhgame.txt"
work_executable = ROOT / "work/vhgame.exe"
assert digest(work_source) in {accepted_source_sha256, candidate_source_sha256}
assert digest(work_executable) in {accepted_executable_sha256, candidate_executable_sha256}
shutil.copyfile(accepted_source, work_source)
shutil.copyfile(accepted_executable, work_executable)
assert digest(work_source) == accepted_source_sha256
assert digest(work_executable) == accepted_executable_sha256
assert digest(ROOT / "main/lib/gen/compiler114m.exe") == digest(
    EVIDENCE / "accepted/compiler114m.exe")
assert digest(ROOT / "main/cpu/i386m.bin") == digest(
    EVIDENCE / "accepted/i386m.bin")

result = {
    "schema": 1,
    "task": 219,
    "candidate": "remove ten dead fixed-F64 FI/conversion/FA-copy sequences and retain the ring FI store",
    "source_boundary": "one common tracked shared-Lino closure",
    "model": model,
    "semantic_review": semantic_review,
    "build": build,
    "production_layout": production_layout,
    "required_abba_order": ["candidate-a", "baseline-a", "baseline-b", "candidate-b"],
    "performed_arms": ["candidate-a", "baseline-a"],
    "candidate_a": metrics["candidate-a"],
    "baseline_a": metrics["baseline-a"],
    "candidate_a_simulation_gate": "pass",
    "candidate_a_simulation_margin_hz": (
        metrics["candidate-a"]["simulation_hz"] - REQUIRED_SIMULATION_HZ),
    "ordering_a": ordering_a,
    "ordering_b": {"status": "skipped_after_ordering_a_performance_failure"},
    "fidelity": {"status": "skipped_after_ordering_a_performance_failure"},
    "sustained_candidate": {
        "status": "skipped_after_ordering_a_performance_failure"},
    "sustained_native_60_hz_status": "still_open",
    "disposition": "rejected_after_ordering_a_performance_failure",
    "host_classification": "controlled_depressed_host_evidence",
    "orderings_averaged": False,
    "final_arm": "accepted_baseline",
    "candidate_retained_byte_exact": False,
    "accepted_restored_byte_exact": True,
    "accepted_source_sha256": accepted_source_sha256,
    "accepted_executable_sha256": accepted_executable_sha256,
    "candidate_source_sha256": candidate_source_sha256,
    "candidate_executable_sha256": candidate_executable_sha256,
}
(EVIDENCE / "result.json").write_text(
    json.dumps(result, indent=2) + "\n", encoding="utf-8")
files = (
    "apply_candidate.py",
    "verify_model.py",
    "verify_production.py",
    "model.json",
    "semantic-review.json",
    "build.json",
    "production-layout.json",
    "run_arm.py",
    "finalize.py",
    "accepted/vhgame.txt",
    "accepted/vhgame.exe",
    "accepted/compiler114m.exe",
    "accepted/i386m.bin",
    "candidate/vhgame.txt",
    "candidate/vhgame.exe",
    "candidate-a/capsule/report.json",
    "baseline-a/capsule/report.json",
    "result.json",
)
manifest = {
    "schema": 1,
    "files": {
        relative: {
            "bytes": (EVIDENCE / relative).stat().st_size,
            "sha256": digest(EVIDENCE / relative),
        }
        for relative in files
    },
}
(EVIDENCE / "manifest.json").write_text(
    json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps({
    "candidate_a": metrics["candidate-a"],
    "baseline_a": metrics["baseline-a"],
    "ordering_a": ordering_a,
    "disposition": result["disposition"],
    "final_arm": result["final_arm"],
}, indent=2))
