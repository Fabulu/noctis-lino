from pathlib import Path
import hashlib
import json
import runpy

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/local-orbital-rate-cache-20260830"
REQUIRED_SIMULATION_HZ = 18.206


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(relative):
    return json.loads((EVIDENCE / relative).read_text(encoding="utf-8"))


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
assert candidate_source_sha256 == "9df0094c40c4e26179d2ff4ce9f17bf6d8015075f986e03d30989c932abcec32"
assert candidate_executable_sha256 == "5599ce2b884a2a31617f50d22e6d3f490266516c87e46e6e3497caf5f2aa9eda"
transform = runpy.run_path(str(EVIDENCE / "apply_candidate.py"))["transform"]
assert candidate_source.read_bytes() == transform(accepted_source.read_bytes())
model = load("model.json")
semantic_review = load("semantic-review.json")
build = load("build.json")
assert model["status"] == "pass" and model["cases"] == 3825
assert model["candidate_file_equals_exact_transform"]
assert model["cold_static_prefix_statement_and_grouping_exact"]
assert model["dynamic_seconds_suffix_statement_and_grouping_exact"]
assert model["a_through_e_terminal_state_exact"]
assert semantic_review["status"] == "pass"
assert semantic_review["remaining_mismatches"] == []
assert build["status"] == "pass"
assert build["private_inactive_desktop"]
assert build["entry_point"] == "lino_build.ps1"
assert build["candidate_executable_sha256"] == candidate_executable_sha256
candidate_a_report = load("candidate-a/capsule/report.json")
validate_arm(candidate_a_report, candidate_executable_sha256)
candidate_a = {
    "presentation_hz": candidate_a_report["metrics"]["presentation_hz"],
    "simulation_hz": candidate_a_report["metrics"]["simulation_hz"],
    "cycles_per_presentation": candidate_a_report["metrics"][
        "average_process_cycles_per_presentation"],
    "render_ms": candidate_a_report["metrics"]["average_render_ms"],
    "missed_deadlines": candidate_a_report["profile"]["missed_deadlines"],
}
assert candidate_a["simulation_hz"] < REQUIRED_SIMULATION_HZ
assert not (EVIDENCE / "baseline-a/capsule/report.json").exists()
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
    "task": 216,
    "candidate": "local-only cache of the static pre-time VHGND orbital-rate root",
    "source_boundary": "one common tracked shared-Lino closure",
    "model": model,
    "semantic_review": semantic_review,
    "build": build,
    "abba_order": ["candidate-a", "baseline-a", "baseline-b", "candidate-b"],
    "candidate_a": candidate_a,
    "candidate_a_simulation_gate": "fail",
    "candidate_a_simulation_margin_hz": (
        candidate_a["simulation_hz"] - REQUIRED_SIMULATION_HZ),
    "baseline_a": {"status": "skipped_after_candidate_a_simulation_failure"},
    "ordering_a": {"status": "not_reached"},
    "baseline_b": {"status": "skipped_after_candidate_a_simulation_failure"},
    "candidate_b": {"status": "skipped_after_candidate_a_simulation_failure"},
    "ordering_b": {"status": "not_reached"},
    "fidelity": {"status": "skipped_after_candidate_a_simulation_failure"},
    "sustained_candidate": {"status": "skipped_after_candidate_a_simulation_failure"},
    "sustained_native_60_hz_status": "still_open",
    "disposition": "rejected_after_candidate_a_simulation_failure",
    "host_classification": "controlled_severely_depressed_host_evidence",
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
    "candidate_a_simulation_margin_hz": result["candidate_a_simulation_margin_hz"],
    "disposition": result["disposition"],
    "final_arm": result["final_arm"],
}, indent=2))
