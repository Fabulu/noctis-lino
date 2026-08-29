from pathlib import Path
import hashlib
import json
import runpy

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/squared-resident-selection-20260829"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def report(relative):
    return json.loads((EVIDENCE / relative).read_text(encoding="utf-8"))


accepted_source = EVIDENCE / "accepted/vhgame.txt"
accepted_executable = EVIDENCE / "accepted/vhgame.exe"
candidate_source = EVIDENCE / "candidate/vhgame.txt"
candidate_executable = EVIDENCE / "candidate/vhgame.exe"
model = report("model.json")
candidate_a = report("candidate-a/capsule/report.json")
baseline_a = report("baseline-a/capsule/report.json")
transform = runpy.run_path(str(EVIDENCE / "apply_candidate.py"))["transform"]
assert candidate_source.read_bytes() == transform(accepted_source.read_bytes())
assert model["status"] == "pass"
assert model["candidate_source_sha256"] == digest(candidate_source)
assert candidate_a["provenance"]["executable_sha256"] == digest(candidate_executable)
assert baseline_a["provenance"]["executable_sha256"] == digest(accepted_executable)
assert candidate_a["metrics"]["simulation_hz"] >= 18.206
assert candidate_a["metrics"]["presentation_hz"] < baseline_a["metrics"]["presentation_hz"]
assert candidate_a["metrics"]["average_process_cycles_per_presentation"] > baseline_a["metrics"]["average_process_cycles_per_presentation"]
assert digest(ROOT / "work/vhgame.txt") == digest(accepted_source)
assert digest(ROOT / "work/vhgame.exe") == digest(accepted_executable)
assert digest(ROOT / "main/lib/gen/compiler114m.exe") == digest(EVIDENCE / "accepted/compiler114m.exe")
assert digest(ROOT / "main/cpu/i386m.bin") == digest(EVIDENCE / "accepted/i386m.bin")

presentation_delta = (
    candidate_a["metrics"]["presentation_hz"]
    - baseline_a["metrics"]["presentation_hz"]
)
cycles_delta = (
    candidate_a["metrics"]["average_process_cycles_per_presentation"]
    - baseline_a["metrics"]["average_process_cycles_per_presentation"]
)
result = {
    "schema": 1,
    "task": 207,
    "candidate": "exact rooted-top-two selection with finite squared-distance rejection",
    "source_boundary": "one common tracked shared-Lino closure",
    "model": {
        "status": model["status"],
        "cases": model["cases"],
        "resident_indices_exact": model["resident_indices_exact"],
        "root_collision_preserved": model["root_collision_preserved"],
        "stable_ties_preserved": model["stable_ties_preserved"],
        "special_values_use_rooted_fallback": model["nan_and_infinity_use_rooted_fallback"],
        "final_full_scan_body_uses_rooted_path": model["final_full_scan_body_uses_rooted_path"],
        "moon_primary_rescan_unchanged_and_rooted": model["moon_primary_rescan_unchanged_and_rooted"],
        "representative_roots": {
            "accepted": model["representative_accepted_roots"],
            "candidate": model["representative_candidate_roots"],
        },
    },
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
    "candidate_a": {
        "presentation_hz": candidate_a["metrics"]["presentation_hz"],
        "simulation_hz": candidate_a["metrics"]["simulation_hz"],
        "cycles_per_presentation": candidate_a["metrics"]["average_process_cycles_per_presentation"],
        "render_ms": candidate_a["metrics"]["average_render_ms"],
        "missed_deadlines": candidate_a["profile"]["missed_deadlines"],
    },
    "baseline_a": {
        "presentation_hz": baseline_a["metrics"]["presentation_hz"],
        "simulation_hz": baseline_a["metrics"]["simulation_hz"],
        "cycles_per_presentation": baseline_a["metrics"]["average_process_cycles_per_presentation"],
        "render_ms": baseline_a["metrics"]["average_render_ms"],
        "missed_deadlines": baseline_a["profile"]["missed_deadlines"],
    },
    "ordering_a": {
        "presentation_delta_hz": presentation_delta,
        "cycles_per_presentation_delta": cycles_delta,
        "candidate_won_presentation": presentation_delta > 0,
        "candidate_won_cycles": cycles_delta < 0,
        "decision": "reject",
    },
    "candidate_a_simulation_gate": "pass",
    "baseline_b": None,
    "candidate_b": None,
    "ordering_b": "skipped_after_ordering_a_rejection",
    "fidelity": "skipped_after_ordering_a_rejection",
    "disposition": "rejected_after_ordering_a",
    "final_arm": "accepted",
    "accepted_restored_byte_exact": True,
    "accepted_source_sha256": digest(accepted_source),
    "accepted_executable_sha256": digest(accepted_executable),
}
(EVIDENCE / "result.json").write_text(
    json.dumps(result, indent=2) + "\n", encoding="utf-8"
)
files = (
    "apply_candidate.py",
    "verify_model.py",
    "model.json",
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
    json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps({
    "candidate_simulation_hz": result["candidate_a"]["simulation_hz"],
    "presentation_delta_hz": presentation_delta,
    "cycles_per_presentation_delta": cycles_delta,
    "disposition": result["disposition"],
    "final_arm": result["final_arm"],
}, indent=2))
