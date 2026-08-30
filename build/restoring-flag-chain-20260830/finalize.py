from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/restoring-flag-chain-20260830"
RESULT = EVIDENCE / "result.json"
MANIFEST = EVIDENCE / "manifest.json"
ACCEPTED_FP_SHA256 = (
    "063ecf40b0faab3b2779d8ff159b8fa815eec7b397de0d47e68223841e2a59cc")
CANDIDATE_FP_SHA256 = (
    "f6aa960d904cd9bc7c162159fac8ab8253bf4dd3c52e6c2b983dfd8af444a0c0")
ACCEPTED_EXE_SHA256 = (
    "e18e8eb45ac0bc03aa2ee1f51ce1ae54f6ee00a0e8a7cef24cbd3adebcdf32a0")
CANDIDATE_EXE_SHA256 = (
    "2dd024c214a49c94fd19dd7f9832a98f6c252a3a1bdcf363de0fbb68c33385f6")
ACCEPTED_COMPILER_SHA256 = (
    "cfb39efc611dc96eab47f24c70cc7447a11f3b7cd874c49bfeb4934a42e67e87")
CANDIDATE_COMPILER_SHA256 = (
    "78e862bd94cf80685e579e827cf5d46f2c5adfd5a437befc94396b370bfc9e35")
CPU_PACK_SHA256 = (
    "1dd1433597c42e30b13bd55bfd02c19ebe465f3e020e4878906f66e7bfcdc4b7")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def arm(name, expected_executable):
    report = load(EVIDENCE / name / "capsule/report.json")
    assert report["schema"] == 2 and report["scenario"] == "capsule"
    assert report["requested_measurement_seconds"] == 5.0
    assert report["command"][-2:] == ["clock=1344638527", "profile"]
    assert report["provenance"]["executable_sha256"] == expected_executable
    scheduling = report["provenance"]["scheduling"]
    assert scheduling["comparable"]
    assert scheduling["physical_core_index"] == 3
    assert scheduling["requested_affinity_mask"] == "0xc0"
    assert scheduling["requested_priority_class"] == "above_normal"
    assert scheduling["actual"]["process_affinity_mask"] == "0xc0"
    assert scheduling["actual"]["priority_class"] == "above_normal"
    metrics = report["metrics"]
    profile = report["profile"]
    return {
        "presentation_hz": metrics["presentation_hz"],
        "simulation_hz": metrics["simulation_hz"],
        "render_ms": metrics["average_render_ms"],
        "present_ms": metrics["average_present_ms"],
        "process_cycles_per_presentation": metrics[
            "average_process_cycles_per_presentation"],
        "missed_deadlines": profile["missed_deadlines"],
        "presentations": profile["presentations"],
        "simulation_ticks": profile["simulation_ticks"],
        "profile_origin_counter": profile["profile_origin_counter"],
    }


accepted_fp = EVIDENCE / "accepted/fpsoft.txt"
candidate_fp = EVIDENCE / "candidate/fpsoft.txt"
accepted_exe = EVIDENCE / "accepted/vhgame.exe"
candidate_exe = EVIDENCE / "candidate/vhgame.exe"
assert digest(accepted_fp) == ACCEPTED_FP_SHA256
assert digest(candidate_fp) == CANDIDATE_FP_SHA256
assert digest(accepted_exe) == ACCEPTED_EXE_SHA256
assert digest(candidate_exe) == CANDIDATE_EXE_SHA256
assert accepted_exe.stat().st_size == candidate_exe.stat().st_size == 645_966
assert digest(EVIDENCE / "accepted/compiler114m.exe") == ACCEPTED_COMPILER_SHA256
assert digest(EVIDENCE / "candidate/compiler114m.exe") == CANDIDATE_COMPILER_SHA256
assert digest(EVIDENCE / "accepted/i386m.bin") == CPU_PACK_SHA256

model = load(EVIDENCE / "model.json")
build = load(EVIDENCE / "build.json")
layout = load(EVIDENCE / "production-layout.json")
references = load(EVIDENCE / "reference-audit.json")
review = load(EVIDENCE / "semantic-review.json")
assert model["status"] == build["status"] == layout["status"] == "pass"
assert references["status"] == review["status"] == "pass"
assert review["final_review"]["status"] == "pass"
assert review["final_review"]["remaining_material_findings"] == 0
assert model["common_lino_change_is_zero_byte_marker_only"]
assert not model["raw_target_machine_block_added_to_shipping_lino"]
assert model["terminal_a_through_e_exact"]
assert model["terminal_x86_cf_pf_af_zf_sf_of_exact"]
assert model["simulation_constants"] == [18206, 60000]
assert build["compiler_three_stage_fixpoint"]
assert build["marker_only_game_matches_accepted_byte_exactly"]
assert build["private_inactive_desktop"] and not build["default_desktop"]
assert layout["package_bytes_outside_island_exact"]
assert layout["unexpected_changes"] == 0
assert layout["current_package_overwritten_label_references"] == 0
assert references["whole_program_indirect_control_transfers_reported_unresolved"] == 259
assert not references["complete_shipping_dependency_closure_audited"]

candidate_a = arm("candidate-a", CANDIDATE_EXE_SHA256)
baseline_a = arm("baseline-a", ACCEPTED_EXE_SHA256)
baseline_b = arm("baseline-b", ACCEPTED_EXE_SHA256)
candidate_b = arm("candidate-b", CANDIDATE_EXE_SHA256)
arms = [candidate_a, baseline_a, baseline_b, candidate_b]
assert [item["profile_origin_counter"] for item in arms] == sorted(
    item["profile_origin_counter"] for item in arms)
for item in (candidate_a, candidate_b):
    item["simulation_gate_hz"] = 18.206
    item["simulation_gate_pass"] = item["simulation_hz"] >= 18.206
    assert item["simulation_gate_pass"]


def ordering(candidate, baseline):
    presentation_delta = candidate["presentation_hz"] - baseline["presentation_hz"]
    cycles_delta = (candidate["process_cycles_per_presentation"]
                    - baseline["process_cycles_per_presentation"])
    render_delta = candidate["render_ms"] - baseline["render_ms"]
    return {
        "presentation_hz_delta": presentation_delta,
        "cycles_per_presentation_delta": cycles_delta,
        "render_ms_delta": render_delta,
        "wins_both_mandatory_metrics": (
            presentation_delta > 0 and cycles_delta < 0),
        "candidate_lost_presentation_hz": presentation_delta < 0,
        "candidate_added_cycles_per_presentation": cycles_delta > 0,
    }


ordering_a = ordering(candidate_a, baseline_a)
ordering_b = ordering(candidate_b, baseline_b)
assert ordering_a["wins_both_mandatory_metrics"]
assert not ordering_b["wins_both_mandatory_metrics"]
assert ordering_b["candidate_lost_presentation_hz"]
assert ordering_b["candidate_added_cycles_per_presentation"]
for path in (
        EVIDENCE / "fidelity.json",
        EVIDENCE / "fidelity-baseline",
        EVIDENCE / "fidelity-baseline-repeat",
        EVIDENCE / "fidelity-candidate",
        EVIDENCE / "sustained-30s/capsule/report.json"):
    assert not path.exists()

# Candidate B is the final timing arm; restore retained Task #224 atomically as a
# matching source/executable pair before producing the final evidence.
shutil.copyfile(accepted_fp, ROOT / "work/fp/fpsoft.txt")
shutil.copyfile(accepted_exe, ROOT / "work/vhgame.exe")
assert digest(ROOT / "work/fp/fpsoft.txt") == ACCEPTED_FP_SHA256
assert digest(ROOT / "work/vhgame.exe") == ACCEPTED_EXE_SHA256

result = {
    "schema": 1,
    "task": 231,
    "date": "2026-08-30",
    "decision": "rejected-contradictory-orderings",
    "reason": (
        "Ordering A improved both mandatory metrics, but Ordering B independently "
        "lost presentation throughput and increased process cycles per presentation. "
        "The binding discriminator forbids averaging contradictory orderings, so the "
        "candidate was rejected before fidelity or sustained screening and Task #224 "
        "was restored byte-exactly."),
    "candidate_change_scope": {
        "common_lino_change": "zero-byte XRoot exact i386m marker only",
        "compiler_change": (
            "fail-closed exact 216-byte i386m flag-chain lowering below the shared source boundary"),
        "native_gameplay_or_renderer_code": False,
        "architecture_specific_lino_fork": False,
        "raw_target_machine_block_added_to_shipping_lino": False,
        "complete_shipping_dependency_closure_audited_here": False,
        "closure_audit_deferred_to_release_audit": True,
    },
    "candidate": {
        "fpsoft_sha256": CANDIDATE_FP_SHA256,
        "compiler_sha256": CANDIDATE_COMPILER_SHA256,
        "executable_bytes": candidate_exe.stat().st_size,
        "executable_sha256": CANDIDATE_EXE_SHA256,
        "island_bytes": layout["island_bytes"],
        "reachable_instructions": layout["candidate_reachable_instructions"],
        "compare_instructions": layout["candidate_compare_instructions"],
    },
    "accepted_baseline": {
        "task": 224,
        "description": "retained buffered-limb restoring-root production",
        "fpsoft_sha256": ACCEPTED_FP_SHA256,
        "compiler_sha256": ACCEPTED_COMPILER_SHA256,
        "executable_bytes": accepted_exe.stat().st_size,
        "executable_sha256": ACCEPTED_EXE_SHA256,
        "reachable_instructions": layout["accepted_instructions"],
        "compare_instructions": layout["accepted_compare_instructions"],
    },
    "focused_gates": {
        "source_model": "pass",
        "source_model_cases": model["cases"],
        "generated_machine_cases": layout["generated_machine_cases"],
        "all_eight_gprs_exact": True,
        "all_six_flags_exact": True,
        "workspace_and_ordered_writes_exact": True,
        "compiler_three_stage_fixpoint": True,
        "marker_only_output_byte_exact": True,
        "package_bytes_outside_216_byte_island_exact": True,
        "package_unexpected_changes": 0,
        "current_package_overwritten_label_references": 0,
        "whole_program_indirect_transfers_reported_unresolved": 259,
        "adversarial_review": "pass-after-evidence-hardening",
        "claim_scope": "current exact selected i386m production package only",
    },
    "discriminator": {
        "checkpoint": 1344638527,
        "physical_core_index": 3,
        "affinity_mask": "0xc0",
        "priority": "above_normal",
        "desktop": "private inactive desktop",
        "requested_measurement_seconds": 5.0,
        "completed_order": ["candidate-a", "baseline-a", "baseline-b", "candidate-b"],
        "profile_origin_counters_in_order": [
            item["profile_origin_counter"] for item in arms],
    },
    "candidate_a": candidate_a,
    "baseline_a": baseline_a,
    "ordering_a": ordering_a,
    "baseline_b": baseline_b,
    "candidate_b": candidate_b,
    "ordering_b": ordering_b,
    "combined_interpretation": {
        "status": "forbidden",
        "reason": "The two independent orderings disagree; do not average them.",
    },
    "fidelity": {
        "status": "skipped",
        "evidence_absent": True,
        "reason": "Fidelity is permitted only after both orderings independently win.",
    },
    "sustained_screen": {
        "status": "skipped",
        "evidence_absent": True,
        "reason": "Rejected candidate was not eligible for sustained screening.",
    },
    "retained_minute_record": {
        "presentation_hz": 59.800276745077774,
        "simulation_hz": 18.255172298818,
        "replaced": False,
    },
    "restored_production": {
        "task": 224,
        "fpsoft_sha256": ACCEPTED_FP_SHA256,
        "executable_bytes": accepted_exe.stat().st_size,
        "executable_sha256": ACCEPTED_EXE_SHA256,
        "current_files_match_accepted": True,
    },
}
RESULT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

manifest_paths = [
    "accepted/compiler114m.txt", "accepted/compiler114m.exe", "accepted/i386m.bin",
    "accepted/fpsoft.txt", "accepted/vhgame.txt", "accepted/vhgame.exe",
    "candidate/compiler114m.txt", "candidate/compiler114m.exe",
    "candidate/fpsoft.txt", "candidate/vhgame.exe", "apply_candidate.py",
    "prepared-source.json", "verify_model.py", "model.json", "build_candidate.py",
    "build.json", "marker-only/vhgame.exe", "verify_production.py",
    "production-layout.json",
    "verify_references.py", "reference-audit.json", "semantic-review.json",
    "run_arm.py", "finalize.py", "result.json",
    "candidate-a/capsule/report.json", "baseline-a/capsule/report.json",
    "baseline-b/capsule/report.json", "candidate-b/capsule/report.json",
]
files = []
for relative in manifest_paths:
    path = EVIDENCE / relative
    assert path.is_file(), relative
    files.append({
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": digest(path),
    })
manifest = {
    "schema": 1,
    "task": 231,
    "date": "2026-08-30",
    "decision": "rejected-contradictory-orderings",
    "files": files,
    "active": {
        "work/fp/fpsoft.txt": digest(ROOT / "work/fp/fpsoft.txt"),
        "work/vhgame.exe": digest(ROOT / "work/vhgame.exe"),
    },
    "current_files_match_accepted": True,
}
MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
