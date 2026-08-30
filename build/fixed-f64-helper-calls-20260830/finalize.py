from pathlib import Path
import hashlib
import json
import runpy
import shutil

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/fixed-f64-helper-calls-20260830"
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
assert candidate_source_sha256 == "1ba39ef3675d95d338ae94117dba36fb71570f392ed8d53931b05642d7391e5d"
assert candidate_executable_sha256 == "511dec34c189499504ccd86ec94f2f838fb34ad192450317ac0aaec943a6f67a"
transform = runpy.run_path(str(EVIDENCE / "apply_candidate.py"))["transform"]
assert candidate_source.read_bytes() == transform(accepted_source.read_bytes())

model = load("model.json")
semantic_review = load("semantic-review.json")
build = load("build.json")
production_layout = load("production-layout.json")
assert model["status"] == "pass" and model["replacement_sites"] == 11
assert model["candidate_file_equals_exact_transform"]
assert model["int_to_binary32_to_binary64_words_exact"]
assert model["a_through_e_preserved"] and model["fs0_preserved"]
assert semantic_review["status"] == "pass"
assert semantic_review["remaining_mismatches"] == []
assert build["status"] == "pass"
assert build["private_inactive_desktop"]
assert build["entry_point"] == "lino_build.ps1"
assert build["candidate_executable_sha256"] == candidate_executable_sha256
assert production_layout["status"] == "pass"
assert production_layout["hot_call_sites"] == 11
assert production_layout["preexisting_instruction_addresses_preserved"]
assert production_layout["unexpected_changed_existing_code_bytes"] == 0
assert production_layout["helper_count"] == 6
assert production_layout["helper_generated_shape_exact"]

reports = {
    arm: load(f"{arm}/capsule/report.json")
    for arm in ("candidate-a", "baseline-a", "baseline-b", "candidate-b")
}
validate_arm(reports["candidate-a"], candidate_executable_sha256)
validate_arm(reports["baseline-a"], accepted_executable_sha256)
validate_arm(reports["baseline-b"], accepted_executable_sha256)
validate_arm(reports["candidate-b"], candidate_executable_sha256)
metrics = {arm: arm_metrics(report) for arm, report in reports.items()}
assert all(item["simulation_hz"] >= REQUIRED_SIMULATION_HZ for item in metrics.values())
ordering_a = {
    "status": "win",
    "presentation_gain_hz": (
        metrics["candidate-a"]["presentation_hz"] -
        metrics["baseline-a"]["presentation_hz"]),
    "cycles_per_presentation_removed": (
        metrics["baseline-a"]["cycles_per_presentation"] -
        metrics["candidate-a"]["cycles_per_presentation"]),
}
ordering_b = {
    "status": "loss",
    "presentation_gain_hz": (
        metrics["candidate-b"]["presentation_hz"] -
        metrics["baseline-b"]["presentation_hz"]),
    "cycles_per_presentation_removed": (
        metrics["baseline-b"]["cycles_per_presentation"] -
        metrics["candidate-b"]["cycles_per_presentation"]),
}
assert ordering_a["presentation_gain_hz"] > 0
assert ordering_a["cycles_per_presentation_removed"] > 0
assert ordering_b["presentation_gain_hz"] < 0
assert ordering_b["cycles_per_presentation_removed"] < 0
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
    "task": 218,
    "candidate": "same-footprint calls to six exact fixed-F64 shared-Lino helpers",
    "source_boundary": "one common tracked shared-Lino closure",
    "model": model,
    "semantic_review": semantic_review,
    "build": build,
    "production_layout": production_layout,
    "abba_order": ["candidate-a", "baseline-a", "baseline-b", "candidate-b"],
    "candidate_a": metrics["candidate-a"],
    "baseline_a": metrics["baseline-a"],
    "baseline_b": metrics["baseline-b"],
    "candidate_b": metrics["candidate-b"],
    "all_simulation_gates": "pass",
    "candidate_a_simulation_margin_hz": (
        metrics["candidate-a"]["simulation_hz"] - REQUIRED_SIMULATION_HZ),
    "candidate_b_simulation_margin_hz": (
        metrics["candidate-b"]["simulation_hz"] - REQUIRED_SIMULATION_HZ),
    "ordering_a": ordering_a,
    "ordering_b": ordering_b,
    "fidelity": {"status": "skipped_after_ordering_b_performance_failure"},
    "sustained_candidate": {
        "status": "skipped_after_ordering_b_performance_failure"},
    "sustained_native_60_hz_status": "still_open",
    "disposition": "rejected_after_ordering_b_performance_failure",
    "host_classification": "controlled_depressed_host_evidence",
    "contradictory_orderings": True,
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
    "baseline-b/capsule/report.json",
    "candidate-b/capsule/report.json",
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
    "baseline_b": metrics["baseline-b"],
    "candidate_b": metrics["candidate-b"],
    "ordering_b": ordering_b,
    "disposition": result["disposition"],
    "final_arm": result["final_arm"],
}, indent=2))
