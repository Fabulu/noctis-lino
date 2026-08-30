from pathlib import Path
import hashlib
import json
import runpy

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/zero-tail-restoring-fsqrt-20260830"
RESULT = EVIDENCE / "result.json"
MANIFEST = EVIDENCE / "manifest.json"
ACCEPTED_FP_SHA256 = (
    "063ecf40b0faab3b2779d8ff159b8fa815eec7b397de0d47e68223841e2a59cc")
CANDIDATE_FP_SHA256 = (
    "da528de24ecc9bb205410a0c41f977726a3bc8edd062235b407a26ca2ee607f3")
ACCEPTED_EXE_SHA256 = (
    "e18e8eb45ac0bc03aa2ee1f51ce1ae54f6ee00a0e8a7cef24cbd3adebcdf32a0")
CANDIDATE_EXE_SHA256 = (
    "f8fe4281bf27365321da5092280fe8a2a08a33b61cdef14459f8e2c6e64009dc")
COMPILER_SHA256 = (
    "cfb39efc611dc96eab47f24c70cc7447a11f3b7cd874c49bfeb4934a42e67e87")
CPU_PACK_SHA256 = (
    "1dd1433597c42e30b13bd55bfd02c19ebe465f3e020e4878906f66e7bfcdc4b7")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def digest(path):
    return sha256(path.read_bytes())


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def arm(path, expected_executable):
    report = load(path)
    assert report["schema"] == 2
    assert report["scenario"] == "capsule"
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
assert digest(EVIDENCE / "accepted/compiler114m.exe") == COMPILER_SHA256
assert digest(EVIDENCE / "accepted/i386m.bin") == CPU_PACK_SHA256
transform = runpy.run_path(str(EVIDENCE / "apply_candidate.py"))["transform"]
assert transform(accepted_fp.read_bytes()) == candidate_fp.read_bytes()

model = load(EVIDENCE / "model.json")
layout = load(EVIDENCE / "production-layout.json")
review = load(EVIDENCE / "semantic-review.json")
build = load(EVIDENCE / "build.json")
assert model["status"] == "pass"
assert model["candidate_snapshot_equals_exact_transform"]
assert model["candidate_source_sha256"] == CANDIDATE_FP_SHA256
assert model["active_source_sha256"] == ACCEPTED_FP_SHA256
assert model["integer_root_exact"]
assert model["accepted_private_residual_exact"]
assert model["accepted_p64_root_rounding_exact"]
assert model["p53_binary64_spill_exact"]
assert (model["p64_policy_differences_with_identical_p53_spill"]
        == model["pipeline_accepted_vs_mathematical_p64_differences"] > 0)
assert model["simulation_constants"] == [18206, 60000]
assert model["verifier_sha256"] == digest(EVIDENCE / "verify_model.py")
assert layout["status"] == "pass"
assert layout["candidate_sha256"] == CANDIDATE_EXE_SHA256
assert layout["package_bytes_outside_root_island_exact"]
assert layout["changed_byte_values"] == 897
assert layout["unexpected_changes"] == 0
assert layout["generated_root_and_remainder_initialization_exact"]
assert layout["generated_remainder_shift_exact"]
assert layout["generated_unsigned_trial_comparison_exact"]
assert layout["generated_borrow_subtraction_exact"]
assert layout["generated_complete_p64_tail_through_return_exact"]
assert layout["generated_post_root_xtof64_call_and_normal_spill_exact"]
assert layout["public_fsqrt_generated_pushal_call_popal_exact"]
assert layout["candidate_post_return_calibration_direct_entries"] == 0
assert layout["candidate_helper_indirect_calls_or_jumps"] == 0
assert layout["candidate_post_return_calibration_has_no_fallthrough"]
assert layout["active_production"] == "accepted"
assert layout["verifier_sha256"] == digest(EVIDENCE / "verify_production.py")
assert review["status"] == "pass-after-evidence-hardening"
assert review["implementation_semantics"] == "pass"
assert review["initial_review"]["status"] == "fail-evidence-overclaim"
assert review["final_review"]["status"] == "pass"
assert review["final_review"]["remaining_defects_in_re_reviewed_scope"] == 0
assert build["status"] == "pass"
assert build["private_inactive_desktop"]
assert build["build_entry"] == "lino_build.ps1"
assert build["absolute_build_paths"]
assert build["warnings"] == 65 and build["errors"] == 0
assert build["candidate_fpsoft_sha256"] == CANDIDATE_FP_SHA256
assert build["candidate_executable_sha256"] == CANDIDATE_EXE_SHA256

reports = {
    "candidate-a": EVIDENCE / "candidate-a/capsule/report.json",
    "baseline-a": EVIDENCE / "baseline-a/capsule/report.json",
    "baseline-b": EVIDENCE / "baseline-b/capsule/report.json",
    "candidate-b": EVIDENCE / "candidate-b/capsule/report.json",
}
measurements = {
    "candidate-a": arm(reports["candidate-a"], CANDIDATE_EXE_SHA256),
    "baseline-a": arm(reports["baseline-a"], ACCEPTED_EXE_SHA256),
    "baseline-b": arm(reports["baseline-b"], ACCEPTED_EXE_SHA256),
    "candidate-b": arm(reports["candidate-b"], CANDIDATE_EXE_SHA256),
}
completed_order = ["candidate-a", "baseline-a", "baseline-b", "candidate-b"]
origin_counters = [measurements[name]["profile_origin_counter"]
                   for name in completed_order]
assert all(left < right for left, right in zip(origin_counters, origin_counters[1:]))
measurements["candidate-a"]["simulation_gate_hz"] = 18.206
measurements["candidate-a"]["simulation_gate_pass"] = (
    measurements["candidate-a"]["simulation_hz"] >= 18.206)
measurements["candidate-b"]["simulation_gate_hz"] = 18.206
measurements["candidate-b"]["simulation_gate_pass"] = (
    measurements["candidate-b"]["simulation_hz"] >= 18.206)
assert measurements["candidate-a"]["simulation_gate_pass"]
assert measurements["candidate-b"]["simulation_gate_pass"]

ordering_a_presentation = (
    measurements["candidate-a"]["presentation_hz"]
    - measurements["baseline-a"]["presentation_hz"])
ordering_a_cycles = (
    measurements["candidate-a"]["process_cycles_per_presentation"]
    - measurements["baseline-a"]["process_cycles_per_presentation"])
ordering_b_presentation = (
    measurements["candidate-b"]["presentation_hz"]
    - measurements["baseline-b"]["presentation_hz"])
ordering_b_cycles = (
    measurements["candidate-b"]["process_cycles_per_presentation"]
    - measurements["baseline-b"]["process_cycles_per_presentation"])
assert ordering_a_presentation > 0 and ordering_a_cycles < 0
assert ordering_b_presentation < 0 and ordering_b_cycles < 0
ordering_a_wins = ordering_a_presentation > 0 and ordering_a_cycles < 0
ordering_b_wins = ordering_b_presentation > 0 and ordering_b_cycles < 0
assert ordering_a_wins and not ordering_b_wins

# Both downstream gates are forbidden after contradictory timing orderings.
for path in (
        EVIDENCE / "fidelity.json",
        EVIDENCE / "fidelity",
        EVIDENCE / "sustained-30s/capsule/report.json",
        EVIDENCE / "sustained",
        EVIDENCE / "sustained-screen"):
    assert not path.exists()

run_arm_text = (EVIDENCE / "run_arm.py").read_text(encoding="utf-8")
assert "tools/profile_noctis_desktop.py" in run_arm_text
assert '"--physical-core", "3"' in run_arm_text
assert "-DefaultDesktop" not in run_arm_text

# The contradictory Ordering-B rejection restored the last accepted pair.
assert digest(ROOT / "work/fp/fpsoft.txt") == ACCEPTED_FP_SHA256
assert digest(ROOT / "work/vhgame.exe") == ACCEPTED_EXE_SHA256

result = {
    "schema": 1,
    "task": 228,
    "date": "2026-08-30",
    "decision": "rejected-after-contradictory-ordering-b",
    "reason": (
        "Ordering A improved both mandatory metrics, but Ordering B reversed "
        "presentation throughput while retaining only the cycles improvement. "
        "The binding discriminator forbids averaging contradictory orderings, "
        "so fidelity and sustained screening were skipped and Task #224 was "
        "restored byte-exactly."),
    "source_boundary": {
        "implementation": (
            "binary64 zero-tail specialization in the common tracked fpsoft "
            "Lino source"),
        "shared_lino_source_changed_experimentally": True,
        "shared_source": "work/fp/fpsoft.txt",
        "native_gameplay_or_renderer_code": False,
        "architecture_specific_lino_fork": False,
        "raw_target_machine_block": False,
        "compiler_changed": False,
        "cpu_pack_changed": False,
    },
    "candidate": {
        "description": (
            "process srd3/srd2, cold-transition to 32 known-zero lower pairs, "
            "and skip active-buffer shifts after each limb becomes zero"),
        "fpsoft_sha256": CANDIDATE_FP_SHA256,
        "executable_bytes": candidate_exe.stat().st_size,
        "executable_sha256": CANDIDATE_EXE_SHA256,
    },
    "accepted_baseline": {
        "description": "retained Task #224 buffered-limb restoring root",
        "fpsoft_sha256": ACCEPTED_FP_SHA256,
        "executable_bytes": accepted_exe.stat().st_size,
        "executable_sha256": ACCEPTED_EXE_SHA256,
    },
    "toolchain": {
        "compiler_sha256": COMPILER_SHA256,
        "cpu_pack_sha256": CPU_PACK_SHA256,
        "build_entry": "lino_build.ps1",
        "private_inactive_desktop": True,
        "warnings": build["warnings"],
        "errors": build["errors"],
    },
    "focused_gates": {
        "semantic_model": "pass",
        "adversarial_semantic_review": "pass-after-evidence-hardening",
        "binary64_pipeline_cases": model["binary64_pipeline_cases"],
        "special_dispatch_cases": model["special_dispatch_cases"],
        "minimum_binary64_mantissa_low_zero_bits": model[
            "minimum_binary64_mantissa_low_zero_bits"],
        "minimum_skipped_buffer_shifts_per_root": model[
            "candidate_minimum_skipped_buffer_shifts_per_positive_root"],
        "maximum_performed_buffer_shifts_per_root": model[
            "candidate_maximum_performed_buffer_shifts_per_positive_root"],
        "integer_root_exact": True,
        "accepted_private_residual_exact": True,
        "accepted_p64_root_rounding_exact": True,
        "p53_binary64_spill_exact": True,
        "p64_policy_differences_with_identical_p53_spill": model[
            "p64_policy_differences_with_identical_p53_spill"],
        "production_layout": "pass",
        "root_helper_range": [0x256F1, 0x25B49],
        "changed_byte_values": layout["changed_byte_values"],
        "unexpected_changed_bytes": layout["unexpected_changes"],
        "all_package_bytes_outside_helper_exact": True,
        "generated_complete_p64_tail_exact": True,
        "generated_xtof64_call_and_normal_spill_exact": True,
        "post_return_calibration_direct_entries": 0,
        "helper_indirect_calls_or_jumps": 0,
    },
    "discriminator": {
        "checkpoint": 1344638527,
        "physical_core_index": 3,
        "affinity_mask": "0xc0",
        "priority": "above_normal",
        "desktop": "private inactive desktop",
        "requested_measurement_seconds": 5.0,
        "completed_order": completed_order,
        "profile_origin_counters_in_order": origin_counters,
    },
    "candidate_a": measurements["candidate-a"],
    "baseline_a": measurements["baseline-a"],
    "baseline_b": measurements["baseline-b"],
    "candidate_b": measurements["candidate-b"],
    "ordering_a": {
        "presentation_hz_delta": ordering_a_presentation,
        "cycles_per_presentation_delta": ordering_a_cycles,
        "wins_both_mandatory_metrics": ordering_a_wins,
    },
    "ordering_b": {
        "presentation_hz_delta": ordering_b_presentation,
        "cycles_per_presentation_delta": ordering_b_cycles,
        "wins_both_mandatory_metrics": ordering_b_wins,
        "candidate_lost_presentation_hz": ordering_b_presentation < 0,
        "candidate_improved_cycles_per_presentation": ordering_b_cycles < 0,
    },
    "contradictory_orderings": True,
    "contradictory_orderings_averaged": False,
    "fidelity": {
        "status": "skipped",
        "evidence_absent": True,
        "reason": "Fidelity is permitted only after both orderings win",
    },
    "sustained_screen": {
        "status": "skipped",
        "evidence_absent": True,
        "reason": "Rejected candidate was not eligible for sustained screening",
    },
    "retained_absolute_record": {
        "presentation_hz": 60.15187849720224,
        "simulation_hz": 18.585131894484412,
        "evidence": (
            "build/gui-deferred-demotions-20260829/baseline-a/capsule/report.json"),
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
    "accepted/fpsoft.txt",
    "accepted/vhgame.exe",
    "accepted/compiler114m.exe",
    "accepted/i386m.bin",
    "candidate/fpsoft.txt",
    "candidate/vhgame.exe",
    "apply_candidate.py",
    "verify_model.py",
    "model.json",
    "semantic-review.json",
    "build.json",
    "verify_production.py",
    "production-layout.json",
    "run_arm.py",
    "finalize.py",
    "result.json",
    "candidate-a/capsule/report.json",
    "baseline-a/capsule/report.json",
    "baseline-b/capsule/report.json",
    "candidate-b/capsule/report.json",
]
files = []
for relative in manifest_paths:
    path = EVIDENCE / relative
    assert path.is_file()
    files.append({
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": digest(path),
    })
manifest = {
    "schema": 1,
    "task": 228,
    "date": "2026-08-30",
    "decision": "rejected-after-contradictory-ordering-b",
    "files": files,
    "active": {
        "work/fp/fpsoft.txt": digest(ROOT / "work/fp/fpsoft.txt"),
        "work/vhgame.exe": digest(ROOT / "work/vhgame.exe"),
    },
    "current_files_match_accepted": True,
}
MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
