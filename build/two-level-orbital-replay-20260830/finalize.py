from pathlib import Path
import hashlib
import json
import runpy

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/two-level-orbital-replay-20260830"
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
assert candidate_source_sha256 == "9dfdbf16b7efb84f6770f9c2466e861aec9e4e0103a01ed65b6adacb05f2fd3a"
assert candidate_executable_sha256 == "f6d837436d436483051f80c7615c4b5c2d07a557b8406c2ace749100c6ecb677"

model = load("model.json")
semantic_initial = load("semantic-review-initial.json")
semantic_review = load("semantic-review.json")
transform = runpy.run_path(str(EVIDENCE / "apply_candidate.py"))["transform"]
assert candidate_source.read_bytes() == transform(accepted_source.read_bytes())
assert model["status"] == "pass" and model["cases"] == 12304
assert semantic_initial["status"] == "fail"
assert not semantic_initial["timing_admitted"]
assert semantic_review["status"] == "pass"
assert semantic_review["remaining_mismatches"] == []
assert model["candidate_source_sha256"] == candidate_source_sha256
assert model["accepted_source_sha256"] == accepted_source_sha256
assert semantic_review["candidate_source_sha256"] == candidate_source_sha256
assert semantic_review["accepted_source_sha256"] == accepted_source_sha256

reports = {
    name: load(f"{name}/capsule/report.json")
    for name in ("candidate-a", "baseline-a", "baseline-b", "candidate-b")
}
for name, report in reports.items():
    executable_sha256 = (
        candidate_executable_sha256 if name.startswith("candidate")
        else accepted_executable_sha256)
    validate_arm(report, executable_sha256)
metrics = {name: arm_metrics(report) for name, report in reports.items()}

assert metrics["candidate-a"]["simulation_hz"] >= REQUIRED_SIMULATION_HZ
assert metrics["baseline-a"]["simulation_hz"] >= REQUIRED_SIMULATION_HZ
assert metrics["baseline-b"]["simulation_hz"] >= REQUIRED_SIMULATION_HZ
assert metrics["candidate-b"]["simulation_hz"] < REQUIRED_SIMULATION_HZ
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
assert digest(ROOT / "work/vhgame.txt") == accepted_source_sha256
assert digest(ROOT / "work/vhgame.exe") == accepted_executable_sha256
assert digest(ROOT / "main/lib/gen/compiler114m.exe") == digest(
    EVIDENCE / "accepted/compiler114m.exe")
assert digest(ROOT / "main/cpu/i386m.bin") == digest(
    EVIDENCE / "accepted/i386m.bin")

result = {
    "schema": 1,
    "task": 214,
    "candidate": "two-level exact selected-relative orbital basis and current-frame geometry replay",
    "source_boundary": "one common tracked shared-Lino closure",
    "development_corrections": semantic_review["development_corrections"],
    "record": {
        "workspace_units": model["workspace_units"],
        "record_units": model["record_units"],
        "used_record_units": model["used_record_units"],
        "maximum_cached_bodies": model["maximum_cached_bodies"],
        "maximum_used_address": semantic_review["record"]["maximum_used_address"],
        "workspace_final_address": semantic_review["record"]["workspace_final_address"],
    },
    "model": model,
    "semantic_review": semantic_review,
    "build": {
        "private_inactive_desktop": True,
        "entry_point": "lino_build.ps1",
        "warnings": 62,
        "errors": 0,
        "candidate_executable_bytes": candidate_executable.stat().st_size,
        "candidate_executable_sha256": candidate_executable_sha256,
        "compiler_unchanged": True,
        "cpu_pack_unchanged": True,
        "raw_target_machine_blocks_added": False,
    },
    "abba_order": ["candidate-a", "baseline-a", "baseline-b", "candidate-b"],
    "candidate_a": metrics["candidate-a"],
    "baseline_a": metrics["baseline-a"],
    "baseline_b": metrics["baseline-b"],
    "candidate_b": metrics["candidate-b"],
    "candidate_a_simulation_gate": "pass",
    "candidate_b_simulation_gate": "fail",
    "candidate_b_simulation_required_hz": REQUIRED_SIMULATION_HZ,
    "candidate_b_simulation_shortfall_hz": (
        REQUIRED_SIMULATION_HZ - metrics["candidate-b"]["simulation_hz"]),
    "ordering_a": ordering_a,
    "ordering_b": ordering_b,
    "fidelity": {
        "status": "skipped_after_ordering_b_simulation_and_performance_failure"},
    "sustained_candidate": {
        "status": "skipped_after_ordering_b_simulation_and_performance_failure"},
    "sustained_native_60_hz_status": "still_open",
    "disposition": "rejected_after_ordering_b_simulation_and_performance_failure",
    "host_classification": "controlled_depressed_and_variable_host_evidence",
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
    "semantic-review-initial.json",
    "semantic-review.json",
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
    "ordering_a": ordering_a,
    "ordering_b": ordering_b,
    "candidate_b_simulation_shortfall_hz": result[
        "candidate_b_simulation_shortfall_hz"],
    "disposition": result["disposition"],
    "final_arm": result["final_arm"],
}, indent=2))
