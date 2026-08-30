from pathlib import Path
import hashlib
import json

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/native-fsqrt-lowering-20260830"
RESULT = EVIDENCE / "result.json"
MANIFEST = EVIDENCE / "manifest.json"
ACCEPTED_FP_SHA256 = (
    "063ecf40b0faab3b2779d8ff159b8fa815eec7b397de0d47e68223841e2a59cc")
CANDIDATE_FP_SHA256 = (
    "0628995a3ea891d23737c21757e747b1540c3dc1598991cb4380e815cac5bdf0")
ACCEPTED_EXE_SHA256 = (
    "e18e8eb45ac0bc03aa2ee1f51ce1ae54f6ee00a0e8a7cef24cbd3adebcdf32a0")
CANDIDATE_EXE_SHA256 = (
    "fadbad38814313b000698f591c060d91a53f3b6f701c65f67fbc5845d4d3a4c9")
ACCEPTED_COMPILER_SOURCE_SHA256 = (
    "be83e4e9160497af7b3272a5f0245ce813a76927ff3807249dce5c0dd5d00e19")
CANDIDATE_COMPILER_SOURCE_SHA256 = (
    "be307f775701bf76d27aa34359886ad543dbc37bc97e5cc688ba8e3206919ac4")
ACCEPTED_COMPILER_SHA256 = (
    "cfb39efc611dc96eab47f24c70cc7447a11f3b7cd874c49bfeb4934a42e67e87")
CANDIDATE_COMPILER_SHA256 = (
    "b2f87e8b330fbd479f0bd7b4b8bf536fe4ac06849e6e1fea1f6401930a9f5435")
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
accepted_compiler_source = EVIDENCE / "accepted/compiler114m.txt"
candidate_compiler_source = EVIDENCE / "candidate/compiler114m.txt"
accepted_compiler = EVIDENCE / "accepted/compiler114m.exe"
candidate_compiler = EVIDENCE / "candidate/compiler114m.exe"
assert digest(accepted_fp) == ACCEPTED_FP_SHA256
assert digest(candidate_fp) == CANDIDATE_FP_SHA256
assert digest(accepted_exe) == ACCEPTED_EXE_SHA256
assert digest(candidate_exe) == CANDIDATE_EXE_SHA256
assert accepted_exe.stat().st_size == candidate_exe.stat().st_size == 645_966
assert digest(accepted_compiler_source) == ACCEPTED_COMPILER_SOURCE_SHA256
assert digest(candidate_compiler_source) == CANDIDATE_COMPILER_SOURCE_SHA256
assert digest(accepted_compiler) == ACCEPTED_COMPILER_SHA256
assert digest(candidate_compiler) == CANDIDATE_COMPILER_SHA256
assert digest(EVIDENCE / "accepted/i386m.bin") == CPU_PACK_SHA256

model = load(EVIDENCE / "model.json")
build = load(EVIDENCE / "build.json")
layout = load(EVIDENCE / "production-layout.json")
failclosed = load(EVIDENCE / "failclosed-layout-shift.json")
runtime = load(EVIDENCE / "runtime-boundary.json")
review = load(EVIDENCE / "semantic-review.json")
assert all(item["status"] == "pass" for item in (
    model, build, layout, failclosed, runtime, review))
assert review["final_review"]["status"] == "pass"
assert review["final_review"]["remaining_material_findings"] == 0
assert model["common_lino_change_is_zero_byte_marker_only"]
assert not model["raw_target_machine_block_added_to_shipping_lino"]
assert model["all_positive_finite_binary64_equivalence_integer_proof"]
assert model["public_p53_binary64_result_exact"]
assert model["positive_zero_negative_nonfinite_and_rejection_behavior_exact"]
assert model["public_a_through_e_exact_via_wrapper"]
assert model["candidate_x87_top_net_change"] == 0
assert model["simulation_constants"] == [18206, 60000]
assert build["compiler_three_stage_fixpoint"]
assert build["marker_only_i386m_matches_accepted_byte_exactly"]
assert build["non_i386m_output_comparison_run"]
assert build["non_i386m_outputs_byte_exact"]
assert build["private_inactive_desktop"] and not build["default_desktop"]
assert layout["package_bytes_outside_island_exact"]
assert layout["unexpected_changes"] == 0
assert layout["candidate_fsqrt"]
assert layout["candidate_direct_calls_to_root_core"] == 0
assert layout["exact_context_binds_fa_displacement"]
assert layout["exact_context_single_byte_mutations_fail_closed"] == 109
assert not layout["complete_shipping_dependency_closure_audited"]
assert failclosed["accepted_and_candidate_compiler_outputs_byte_exact"]
assert failclosed["generated_fsqrt_instructions"] == 0
assert failclosed["context_gate_failed_closed_on_real_i386m_build"]
assert runtime["checks_passed"] == 24 and runtime["checks_failed"] == 0

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
        EVIDENCE / "sustained-60s/capsule/report.json"):
    assert not path.exists()

# The final timing arm installed the candidate. Task #224 has already been
# restored as an exact matching source/executable pair; fail if either drifts.
assert digest(ROOT / "work/fp/fpsoft.txt") == ACCEPTED_FP_SHA256
assert digest(ROOT / "work/vhgame.exe") == ACCEPTED_EXE_SHA256
assert digest(ROOT / "main/lib/gen/compiler114m.txt") == ACCEPTED_COMPILER_SOURCE_SHA256
assert digest(ROOT / "main/lib/gen/compiler114m.exe") == ACCEPTED_COMPILER_SHA256

result = {
    "schema": 1,
    "task": 233,
    "date": "2026-08-30",
    "decision": "rejected-contradictory-orderings",
    "reason": (
        "Ordering A improved both mandatory metrics, but Ordering B independently "
        "lost presentation throughput and increased process cycles per presentation. "
        "The binding discriminator forbids averaging contradictory orderings, so the "
        "candidate was rejected before fidelity or sustained screening and Task #224 "
        "was restored byte-exactly."),
    "candidate_change_scope": {
        "common_lino_change": "zero-byte XSS exact i386m native fsqrt marker only",
        "compiler_change": (
            "fail-closed exact-context i386m FLD/FSQRT/FSTP lowering below the shared source boundary"),
        "native_gameplay_or_renderer_code": False,
        "architecture_specific_lino_fork": False,
        "raw_target_machine_block_added_to_shipping_lino": False,
        "complete_shipping_dependency_closure_audited_here": False,
        "closure_audit_deferred_to_release_audit": True,
    },
    "candidate": {
        "fpsoft_sha256": CANDIDATE_FP_SHA256,
        "compiler_source_sha256": CANDIDATE_COMPILER_SOURCE_SHA256,
        "compiler_sha256": CANDIDATE_COMPILER_SHA256,
        "executable_bytes": candidate_exe.stat().st_size,
        "executable_sha256": CANDIDATE_EXE_SHA256,
        "island_bytes": layout["island_bytes"],
        "changed_byte_values": layout["changed_byte_values"],
        "hardware_fsqrt_per_positive_root": model[
            "candidate_hardware_fsqrt_per_positive_root"],
    },
    "accepted_baseline": {
        "task": 224,
        "description": "retained buffered-limb restoring-root production",
        "fpsoft_sha256": ACCEPTED_FP_SHA256,
        "compiler_source_sha256": ACCEPTED_COMPILER_SOURCE_SHA256,
        "compiler_sha256": ACCEPTED_COMPILER_SHA256,
        "executable_bytes": accepted_exe.stat().st_size,
        "executable_sha256": ACCEPTED_EXE_SHA256,
        "integer_restoring_decisions_per_positive_root": model[
            "accepted_integer_restoring_decisions_per_positive_root"],
    },
    "focused_gates": {
        "source_and_binary64_model": "pass",
        "binary64_pipeline_cases": model["binary64_pipeline_cases"],
        "special_dispatch_cases": model["special_dispatch_cases"],
        "positive_finite_all_input_integer_argument": "pass",
        "accepted_private_p64_policy_differences": model[
            "accepted_private_vs_mathematical_p64_differences"],
        "all_policy_differences_spill_to_identical_p53": True,
        "public_a_through_e_exact": True,
        "candidate_x87_stack_net_zero": True,
        "architectural_x87_status_exact": False,
        "selected_package_status_readers_observe_fsqrt_status": False,
        "runtime_boundary_checks": runtime["checks_passed"],
        "compiler_three_stage_fixpoint": True,
        "marker_only_i386m_output_byte_exact": True,
        "non_i386m_x64_outputs_byte_exact": True,
        "package_bytes_outside_16_byte_island_exact": True,
        "package_unexpected_changes": 0,
        "exact_context_bytes": layout["exact_context_bytes"],
        "all_context_single_byte_mutations_fail_closed": True,
        "real_shifted_fa_layout_build_failed_closed": True,
        "adversarial_review": "pass-after-evidence-hardening",
        "claim_scope": "current exact selected i386m production package only",
        "indexed_alias_ranges_exhaustively_proven": False,
        "indirect_transfer_targets_exhaustively_resolved": False,
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
        "compiler_source_sha256": ACCEPTED_COMPILER_SOURCE_SHA256,
        "compiler_sha256": ACCEPTED_COMPILER_SHA256,
        "executable_bytes": accepted_exe.stat().st_size,
        "executable_sha256": ACCEPTED_EXE_SHA256,
        "current_files_match_accepted": True,
    },
}
RESULT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

manifest_paths = [
    "accepted/compiler114m.txt", "accepted/compiler114m.exe", "accepted/i386m.bin",
    "accepted/fpsoft.txt", "accepted/fpabi.txt", "accepted/vhgame.txt",
    "accepted/vhgame.exe", "candidate/compiler114m.txt",
    "candidate/compiler114m.exe", "candidate/fpsoft.txt", "candidate/vhgame.txt",
    "candidate/vhgame.exe", "apply_candidate.py", "prepared-source.json",
    "verify_model.py", "model.json", "build_candidate.py", "build.json",
    "marker-only-i386m/vhgame.exe", "accepted-compiler-x64/vhgame.exe",
    "candidate-compiler-x64/vhgame.exe", "verify_production.py",
    "production-layout.json", "verify_fail_closed_build.py",
    "failclosed-layout-shift.json", "failclosed-layout-shift/fpabi.txt",
    "failclosed-layout-shift-accepted/vhgame.exe",
    "failclosed-layout-shift-candidate/vhgame.exe", "runtime-boundary.json",
    "semantic-review.json", "run_arm.py", "capture_fidelity.py",
    "compare_fidelity.py", "run_sustained.py", "finalize.py", "result.json",
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
    "task": 233,
    "date": "2026-08-30",
    "decision": "rejected-contradictory-orderings",
    "files": files,
    "active": {
        "work/fp/fpsoft.txt": digest(ROOT / "work/fp/fpsoft.txt"),
        "work/vhgame.exe": digest(ROOT / "work/vhgame.exe"),
        "main/lib/gen/compiler114m.txt": digest(
            ROOT / "main/lib/gen/compiler114m.txt"),
        "main/lib/gen/compiler114m.exe": digest(
            ROOT / "main/lib/gen/compiler114m.exe"),
    },
    "current_files_match_accepted": True,
}
MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
