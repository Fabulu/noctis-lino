from pathlib import Path
import hashlib
import json
import runpy

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/orbital-vector-cache-20260829"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def report(relative):
    return json.loads((EVIDENCE / relative).read_text(encoding="utf-8"))


def metrics(arm):
    return {
        "presentation_hz": arm["metrics"]["presentation_hz"],
        "simulation_hz": arm["metrics"]["simulation_hz"],
        "cycles_per_presentation": arm["metrics"]["average_process_cycles_per_presentation"],
        "render_ms": arm["metrics"]["average_render_ms"],
        "missed_deadlines": arm["profile"]["missed_deadlines"],
    }


def ordering(candidate, baseline):
    presentation_delta = (
        candidate["metrics"]["presentation_hz"]
        - baseline["metrics"]["presentation_hz"]
    )
    cycles_delta = (
        candidate["metrics"]["average_process_cycles_per_presentation"]
        - baseline["metrics"]["average_process_cycles_per_presentation"]
    )
    result = {
        "presentation_delta_hz": presentation_delta,
        "cycles_per_presentation_delta": cycles_delta,
        "candidate_won_presentation": presentation_delta > 0,
        "candidate_won_cycles": cycles_delta < 0,
    }
    result["decision"] = "win" if (
        result["candidate_won_presentation"] and result["candidate_won_cycles"]
    ) else "loss"
    return result


accepted_source = EVIDENCE / "accepted/vhgame.txt"
accepted_executable = EVIDENCE / "accepted/vhgame.exe"
candidate_source = EVIDENCE / "candidate/vhgame.txt"
candidate_executable = EVIDENCE / "candidate/vhgame.exe"
model = report("model.json")
semantic_review = report("semantic-review.json")
candidate_a = report("candidate-a/capsule/report.json")
baseline_a = report("baseline-a/capsule/report.json")
baseline_b = report("baseline-b/capsule/report.json")
candidate_b = report("candidate-b/capsule/report.json")
transform = runpy.run_path(str(EVIDENCE / "apply_candidate.py"))["transform"]
assert candidate_source.read_bytes() == transform(accepted_source.read_bytes())
assert model["status"] == "pass"
assert semantic_review["status"] == "pass"
assert model["candidate_source_sha256"] == digest(candidate_source)
for arm, executable in (
    (candidate_a, candidate_executable),
    (baseline_a, accepted_executable),
    (baseline_b, accepted_executable),
    (candidate_b, candidate_executable),
):
    assert arm["provenance"]["executable_sha256"] == digest(executable)
    scheduling = arm["provenance"]["scheduling"]
    assert scheduling["comparable"]
    assert scheduling["physical_core_index"] == 3
    assert scheduling["requested_affinity_mask"] == "0xc0"
    assert scheduling["actual"]["process_affinity_mask"] == "0xc0"
    assert scheduling["actual"]["priority_class"] == "above_normal"
assert candidate_a["metrics"]["simulation_hz"] >= 18.206
assert candidate_b["metrics"]["simulation_hz"] < 18.206
ordering_a = ordering(candidate_a, baseline_a)
ordering_b = ordering(candidate_b, baseline_b)
assert ordering_a["decision"] == "win"
assert ordering_b["decision"] == "loss"
assert digest(ROOT / "work/vhgame.txt") == digest(accepted_source)
assert digest(ROOT / "work/vhgame.exe") == digest(accepted_executable)
assert digest(ROOT / "main/lib/gen/compiler114m.exe") == digest(
    EVIDENCE / "accepted/compiler114m.exe"
)
assert digest(ROOT / "main/cpu/i386m.bin") == digest(EVIDENCE / "accepted/i386m.bin")

result = {
    "schema": 1,
    "task": 210,
    "candidate": "same-second exact absolute orbital body-state cache",
    "source_boundary": "one common tracked shared-Lino closure",
    "development_corrections": [
        {
            "issue": "initial four-unit shift overlapped six-unit records",
            "action": "discarded reports and replaced abstract records with a flat workspace model",
        },
        {
            "issue": "six-unit replay omitted terminal VHGNDowny0/1 state",
            "action": "discarded performance/fidelity evidence and expanded final records to eight units",
        },
    ],
    "final_addressing": "exact body_index_times_8 in a flat 640-unit workspace",
    "model": {
        "status": model["status"],
        "cases": model["cases"],
        "raw_absolute_vector_words_replayed_exactly": model["raw_absolute_vector_words_replayed_exactly"],
        "terminal_owner_relative_y_words_replayed_exactly": model["terminal_owner_relative_y_words_replayed_exactly"],
        "moving_camera_relative_geometry_recomputed": model["moving_camera_relative_geometry_recomputed"],
        "same_frame_epoch_rollover_fails_closed": model["same_frame_epoch_rollover_fails_closed"],
        "local_reset_start_restore_invalidate": model["local_reset_start_restore_invalidate"],
        "over_capacity_fails_closed": model["over_capacity_fails_closed"],
        "accepted_calls_per_stable_second": model["accepted_calls_per_stable_second_at_60_presentations"],
        "candidate_calls_per_stable_second": model["candidate_calls_per_stable_second_at_60_presentations"],
    },
    "semantic_review": semantic_review,
    "build": {
        "private_inactive_desktop": True,
        "entry_point": "lino_build.ps1",
        "warnings": 62,
        "errors": 0,
        "candidate_executable_bytes": candidate_executable.stat().st_size,
        "candidate_executable_sha256": digest(candidate_executable),
        "compiler_unchanged": True,
        "cpu_pack_unchanged": True,
        "raw_target_machine_blocks_added": False,
    },
    "candidate_a": metrics(candidate_a),
    "baseline_a": metrics(baseline_a),
    "baseline_b": metrics(baseline_b),
    "candidate_b": metrics(candidate_b),
    "candidate_a_simulation_gate": "pass",
    "candidate_b_simulation_gate": "fail",
    "ordering_a": ordering_a,
    "ordering_b": ordering_b,
    "fidelity": {"status": "skipped_after_candidate_b_gate_failure"},
    "sustained_candidate": {"status": "skipped_after_candidate_b_gate_failure"},
    "sustained_native_60_hz_status": "still_open",
    "disposition": "rejected_after_candidate_b_simulation_and_ordering_b",
    "host_classification": "controlled_severely_depressed_and_variable_host_evidence",
    "orderings_averaged": False,
    "final_arm": "accepted_baseline",
    "candidate_retained_byte_exact": False,
    "accepted_restored_byte_exact": True,
    "accepted_source_sha256": digest(accepted_source),
    "accepted_executable_sha256": digest(accepted_executable),
    "candidate_source_sha256": digest(candidate_source),
    "candidate_executable_sha256": digest(candidate_executable),
}
(EVIDENCE / "result.json").write_text(
    json.dumps(result, indent=2) + "\n", encoding="utf-8"
)
files = (
    "apply_candidate.py",
    "verify_model.py",
    "model.json",
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
    json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps({
    "candidate_a_simulation_hz": result["candidate_a"]["simulation_hz"],
    "candidate_b_simulation_hz": result["candidate_b"]["simulation_hz"],
    "ordering_a": ordering_a,
    "ordering_b": ordering_b,
    "disposition": result["disposition"],
    "final_arm": result["final_arm"],
}, indent=2))
