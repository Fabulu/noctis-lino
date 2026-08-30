from pathlib import Path
import hashlib
import json
import runpy

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/exact-local-fp-constants-20260830"
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
assert candidate_source_sha256 == "9b7a659facea409838199124ef2843de9de9b557fdf98ad76c9f1fded4f8721d"
assert candidate_executable_sha256 == "9030ab6eaa7635d6727f4e91492f266691377f56124866ba146bc261610482a9"
transform = runpy.run_path(str(EVIDENCE / "apply_candidate.py"))["transform"]
assert candidate_source.read_bytes() == transform(accepted_source.read_bytes())
model = load("model.json")
semantic_review = load("semantic-review.json")
build = load("build.json")
assert model["status"] == "pass" and model["replacement_sites"] == 11
assert model["candidate_file_equals_exact_transform"]
assert model["int_to_binary32_to_binary64_words_exact"]
assert model["a_through_e_preserved_by_original_wrapper_and_candidate"]
assert semantic_review["status"] == "pass"
assert semantic_review["remaining_mismatches"] == []
assert build["status"] == "pass"
assert build["private_inactive_desktop"]
assert build["entry_point"] == "lino_build.ps1"
assert build["candidate_executable_sha256"] == candidate_executable_sha256
candidate_a_report = load("candidate-a/capsule/report.json")
baseline_a_report = load("baseline-a/capsule/report.json")
validate_arm(candidate_a_report, candidate_executable_sha256)
validate_arm(baseline_a_report, accepted_executable_sha256)
candidate_a = arm_metrics(candidate_a_report)
baseline_a = arm_metrics(baseline_a_report)
assert candidate_a["simulation_hz"] >= REQUIRED_SIMULATION_HZ
assert baseline_a["simulation_hz"] >= REQUIRED_SIMULATION_HZ
ordering_a = {
    "status": "loss",
    "presentation_gain_hz": (
        candidate_a["presentation_hz"] - baseline_a["presentation_hz"]),
    "cycles_per_presentation_removed": (
        baseline_a["cycles_per_presentation"] -
        candidate_a["cycles_per_presentation"]),
}
assert ordering_a["presentation_gain_hz"] < 0
assert ordering_a["cycles_per_presentation_removed"] < 0
assert not (EVIDENCE / "baseline-b/capsule/report.json").exists()
assert not (EVIDENCE / "candidate-b/capsule/report.json").exists()
assert not (EVIDENCE / "fidelity").exists()
assert digest(ROOT / "work/vhgame.txt") == accepted_source_sha256
assert digest(ROOT / "work/vhgame.exe") == accepted_executable_sha256
assert digest(ROOT / "main/lib/gen/compiler114m.exe") == digest(
    EVIDENCE / "accepted/compiler114m.exe")
assert digest(ROOT / "main/cpu/i386m.bin") == digest(
    EVIDENCE / "accepted/i386m.bin")

result = {
    "schema": 1,
    "task": 217,
    "candidate": "exact raw binary64 words for eleven fixed local-renderer IntToF sites",
    "source_boundary": "one common tracked shared-Lino closure",
    "model": model,
    "semantic_review": semantic_review,
    "build": build,
    "abba_order": ["candidate-a", "baseline-a", "baseline-b", "candidate-b"],
    "candidate_a": candidate_a,
    "baseline_a": baseline_a,
    "candidate_a_simulation_gate": "pass",
    "candidate_a_simulation_margin_hz": (
        candidate_a["simulation_hz"] - REQUIRED_SIMULATION_HZ),
    "ordering_a": ordering_a,
    "baseline_b": {"status": "skipped_after_ordering_a_performance_failure"},
    "candidate_b": {"status": "skipped_after_ordering_a_performance_failure"},
    "ordering_b": {"status": "not_reached"},
    "fidelity": {"status": "skipped_after_ordering_a_performance_failure"},
    "sustained_candidate": {"status": "skipped_after_ordering_a_performance_failure"},
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
    "model.json",
    "semantic-review.json",
    "build.json",
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
    "candidate_a": candidate_a,
    "baseline_a": baseline_a,
    "ordering_a": ordering_a,
    "disposition": result["disposition"],
    "final_arm": result["final_arm"],
}, indent=2))
