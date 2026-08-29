from pathlib import Path
import hashlib
import json
import runpy

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/deferred-orbital-terminal-replay-20260829"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def report(relative):
    return json.loads((EVIDENCE / relative).read_text(encoding="utf-8"))


def metrics(arm):
    return {
        "presentation_hz": arm["metrics"]["presentation_hz"],
        "simulation_hz": arm["metrics"]["simulation_hz"],
        "cycles_per_presentation": arm["metrics"][
            "average_process_cycles_per_presentation"],
        "render_ms": arm["metrics"]["average_render_ms"],
        "missed_deadlines": arm["profile"]["missed_deadlines"],
    }


accepted_source = EVIDENCE / "accepted/vhgame.txt"
accepted_executable = EVIDENCE / "accepted/vhgame.exe"
candidate_source = EVIDENCE / "candidate/vhgame.txt"
candidate_executable = EVIDENCE / "candidate/vhgame.exe"
model = report("model.json")
semantic_review = report("semantic-review.json")
candidate_a = report("candidate-a/capsule/report.json")
transform = runpy.run_path(str(EVIDENCE / "apply_candidate.py"))["transform"]
assert candidate_source.read_bytes() == transform(accepted_source.read_bytes())
assert model["status"] == "pass"
assert semantic_review["status"] == "pass"
assert model["candidate_source_sha256"] == digest(candidate_source)
assert semantic_review["candidate_source_sha256"] == digest(candidate_source)
assert candidate_a["provenance"]["executable_sha256"] == digest(candidate_executable)
scheduling = candidate_a["provenance"]["scheduling"]
assert scheduling["comparable"]
assert scheduling["physical_core_index"] == 3
assert scheduling["requested_affinity_mask"] == "0xc0"
assert scheduling["actual"]["process_affinity_mask"] == "0xc0"
assert scheduling["actual"]["priority_class"] == "above_normal"
assert candidate_a["metrics"]["simulation_hz"] < 18.206
assert not (EVIDENCE / "baseline-a/capsule/report.json").exists()
assert not (EVIDENCE / "baseline-b/capsule/report.json").exists()
assert not (EVIDENCE / "candidate-b/capsule/report.json").exists()
assert digest(ROOT / "work/vhgame.txt") == digest(accepted_source)
assert digest(ROOT / "work/vhgame.exe") == digest(accepted_executable)
assert digest(ROOT / "main/lib/gen/compiler114m.exe") == digest(
    EVIDENCE / "accepted/compiler114m.exe")
assert digest(ROOT / "main/cpu/i386m.bin") == digest(
    EVIDENCE / "accepted/i386m.bin")

candidate_metrics = metrics(candidate_a)
result = {
    "schema": 1,
    "task": 212,
    "candidate": "deferred exact orbital terminal down-y replay",
    "source_boundary": "one common tracked shared-Lino closure",
    "development_corrections": semantic_review["development_corrections"],
    "record": {
        "addressing": "exact body_index_times_8",
        "workspace_units": 640,
        "maximum_bodies": 80,
        "cold_record_words": 8,
        "hot_vector_replay_words": 6,
        "hot_terminal_down_y_pair_replays": 1,
        "task_210_hot_terminal_down_y_pair_replays": 167,
    },
    "model": {
        "status": model["status"],
        "cases": model["cases"],
        "raw_absolute_vector_words_replayed_exactly": model[
            "raw_absolute_vector_words_replayed_exactly"],
        "terminal_owner_relative_y_replayed_once_at_common_render_done": model[
            "terminal_owner_relative_y_replayed_once_at_common_render_done"],
        "pending_preserved_across_surface_cache_misses": model[
            "pending_preserved_across_surface_cache_misses"],
        "same_frame_epoch_rollover_fails_closed": model[
            "same_frame_epoch_rollover_fails_closed"],
        "local_reset_start_restore_invalidate": model[
            "local_reset_start_restore_invalidate"],
        "over_capacity_fails_closed": model["over_capacity_fails_closed"],
        "accepted_calls_per_stable_second": model[
            "accepted_calls_per_stable_second_at_60_presentations"],
        "candidate_calls_per_stable_second": model[
            "candidate_calls_per_stable_second_at_60_presentations"],
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
    "candidate_a": candidate_metrics,
    "candidate_a_simulation_gate": "fail",
    "candidate_a_simulation_required_hz": 18.206,
    "candidate_a_simulation_shortfall_hz": (
        18.206 - candidate_metrics["simulation_hz"]),
    "baseline_a": {"status": "skipped_after_candidate_a_gate_failure"},
    "baseline_b": {"status": "skipped_after_candidate_a_gate_failure"},
    "candidate_b": {"status": "skipped_after_candidate_a_gate_failure"},
    "ordering_a": {"status": "not_reached"},
    "ordering_b": {"status": "not_reached"},
    "fidelity": {"status": "skipped_after_candidate_a_gate_failure"},
    "sustained_candidate": {
        "status": "skipped_after_candidate_a_gate_failure"},
    "sustained_native_60_hz_status": "still_open",
    "disposition": "rejected_after_candidate_a_simulation_gate",
    "host_classification": "controlled_depressed_host_evidence",
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
    json.dumps(result, indent=2) + "\n", encoding="utf-8")
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
    "candidate_a": candidate_metrics,
    "simulation_shortfall_hz": result["candidate_a_simulation_shortfall_hz"],
    "disposition": result["disposition"],
    "final_arm": result["final_arm"],
}, indent=2))
