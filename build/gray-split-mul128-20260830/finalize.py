from pathlib import Path
import hashlib
import json
import runpy

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/gray-split-mul128-20260830"
RESULT = EVIDENCE / "result.json"
MANIFEST = EVIDENCE / "manifest.json"
ACCEPTED_FP_SHA256 = (
    "063ecf40b0faab3b2779d8ff159b8fa815eec7b397de0d47e68223841e2a59cc")
CANDIDATE_FP_SHA256 = (
    "a2f22335d2473c10b3afe6e15c7aa0bf95380f71f8ab8267445747be6f01be61")
ACCEPTED_EXE_SHA256 = (
    "e18e8eb45ac0bc03aa2ee1f51ce1ae54f6ee00a0e8a7cef24cbd3adebcdf32a0")
CANDIDATE_EXE_SHA256 = (
    "78dcfbc1b503494414f393f7d3b691be2f326424a42a7ae9a696d4823bb99861")
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
assert accepted_exe.stat().st_size == 645_966
assert candidate_exe.stat().st_size == 646_170
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
assert model["symbolic_all_input_schedule_equivalence"]
assert model["direct_unsigned_product_exact"]
assert model["canonical_a_b_c_d_exact"]
assert model["carry_tail_exact"]
assert model["source_terminal_a_through_e_exact"]
assert model["accepted_extraction_alu_operations_per_mul128"] == 24
assert model["candidate_extraction_alu_operations_per_mul128"] == 12
assert model["accepted_unsigned_16x16_products_per_mul128"] == 16
assert model["candidate_unsigned_16x16_products_per_mul128"] == 16
assert model["complete_shipping_dependency_closure_audited"] is False
assert model["simulation_constants"] == [18206, 60000]
assert layout["status"] == "pass"
assert layout["candidate_sha256"] == CANDIDATE_EXE_SHA256
assert layout["pre_helper_generated_code_bytes_checked_exact"] == 43_187
assert layout["xmul32u_complete_generated_bytes_exact"]
assert layout["candidate_partial_product_order"] == ["b", "a", "c", "d"]
assert layout["accepted_generated_extraction_alu_operations_per_mul128"] == 24
assert layout["candidate_generated_extraction_alu_operations_per_mul128"] == 12
assert layout["candidate_dynamic_unsigned_16x16_products_per_mul128"] == 16
assert layout["carry_continuation_bytes_exact"]
assert layout["generated_machine_emulation_cases"] == 4_352
assert layout["generated_machine_all_physical_registers_exact"]
assert layout["generated_machine_complete_workspace_exact"]
assert layout["candidate_helper_indirect_call_jump_loop_transfers"] == 0
assert layout["downstream_logical_instructions_compared"] == 86_301
assert layout["non_code_payload_exact_after_relocation"]
assert layout["package_relocation_normalization_complete"]
assert layout["unexpected_changes"] == 0
assert layout["complete_shipping_dependency_closure_audited"] is False
assert review["status"] == "pass-after-evidence-hardening"
assert review["initial_review"]["status"] == "fail-evidence-overclaim"
assert review["final_review"]["status"] == "pass"
assert review["final_review"]["remaining_material_findings"] == 0
assert build["status"] == "pass"
assert build["private_inactive_desktop"]
assert not build["default_desktop"]
assert build["build_entry"] == "lino_build.ps1"
assert build["warnings"] == 64 and build["errors"] == 0
assert build["candidate_executable_sha256"] == CANDIDATE_EXE_SHA256

candidate_a = arm(
    EVIDENCE / "candidate-a/capsule/report.json", CANDIDATE_EXE_SHA256)
baseline_a = arm(
    EVIDENCE / "baseline-a/capsule/report.json", ACCEPTED_EXE_SHA256)
assert candidate_a["profile_origin_counter"] < baseline_a["profile_origin_counter"]
candidate_a["simulation_gate_hz"] = 18.206
candidate_a["simulation_gate_pass"] = candidate_a["simulation_hz"] >= 18.206
assert candidate_a["simulation_gate_pass"]

presentation_delta = candidate_a["presentation_hz"] - baseline_a["presentation_hz"]
cycles_delta = (
    candidate_a["process_cycles_per_presentation"]
    - baseline_a["process_cycles_per_presentation"])
render_delta = candidate_a["render_ms"] - baseline_a["render_ms"]
assert presentation_delta < 0
assert cycles_delta > 0
ordering_a_wins = presentation_delta > 0 and cycles_delta < 0
assert not ordering_a_wins

# The binding discriminator stops after Ordering A loses either mandatory metric.
for path in (
        EVIDENCE / "baseline-b/capsule/report.json",
        EVIDENCE / "candidate-b/capsule/report.json",
        EVIDENCE / "fidelity.json",
        EVIDENCE / "fidelity-baseline",
        EVIDENCE / "fidelity-baseline-repeat",
        EVIDENCE / "fidelity-candidate",
        EVIDENCE / "sustained-30s/capsule/report.json"):
    assert not path.exists()

run_arm_text = (EVIDENCE / "run_arm.py").read_text(encoding="utf-8")
assert "tools/profile_noctis_desktop.py" in run_arm_text
assert '"--physical-core", "3"' in run_arm_text
assert "-DefaultDesktop" not in run_arm_text

# Baseline A left the accepted Task #224 source/executable pair active.
assert digest(ROOT / "work/fp/fpsoft.txt") == ACCEPTED_FP_SHA256
assert digest(ROOT / "work/vhgame.exe") == ACCEPTED_EXE_SHA256

result = {
    "schema": 1,
    "task": 229,
    "date": "2026-08-30",
    "decision": "rejected-after-ordering-a",
    "reason": (
        "Candidate A preserved the authentic simulation gate but lost both "
        "mandatory Ordering-A metrics: presentation throughput fell and process "
        "cycles per presentation increased. The binding discriminator therefore "
        "stopped before Ordering B, fidelity, or sustained screening, with the "
        "retained Task #224 pair left active byte-exactly."),
    "candidate_change_scope": {
        "implementation": (
            "single-split b,a,c,d Mul128 schedule in common work/fp/fpsoft.txt Lino"),
        "shared_lino_source_changed_experimentally": True,
        "native_gameplay_or_renderer_code": False,
        "architecture_specific_lino_fork": False,
        "candidate_transform_raw_target_machine_block_added": False,
        "complete_shipping_dependency_closure_audited_here": False,
        "closure_audit_deferred_to_release_audit": True,
    },
    "candidate": {
        "description": (
            "split XML, YMH, YML, and XMH once; invoke the exact XMul32u suffix "
            "in b,a,c,d Gray order; restore canonical b and terminal d scratch"),
        "fpsoft_sha256": CANDIDATE_FP_SHA256,
        "executable_bytes": candidate_exe.stat().st_size,
        "executable_sha256": CANDIDATE_EXE_SHA256,
        "generated_growth_bytes": candidate_exe.stat().st_size - accepted_exe.stat().st_size,
    },
    "accepted_baseline": {
        "task": 224,
        "description": "retained buffered-limb restoring-root production",
        "fpsoft_sha256": ACCEPTED_FP_SHA256,
        "executable_bytes": accepted_exe.stat().st_size,
        "executable_sha256": ACCEPTED_EXE_SHA256,
    },
    "selected_toolchain": {
        "compiler_sha256": COMPILER_SHA256,
        "cpu_pack_sha256": CPU_PACK_SHA256,
        "build_entry": "lino_build.ps1",
        "private_inactive_desktop": True,
        "warnings": build["warnings"],
        "errors": build["errors"],
    },
    "focused_gates": {
        "semantic_model": "pass",
        "adversarial_review": "pass-after-evidence-hardening",
        "concrete_mul128_cases": model["concrete_mul128_cases"],
        "pipeline_cases": model["pipeline_cases"],
        "generated_machine_cases": layout["generated_machine_emulation_cases"],
        "direct_unsigned_product_exact": True,
        "terminal_registers_and_workspace_exact": True,
        "generated_extraction_movzx_shr": {"accepted": 24, "candidate": 12},
        "dynamic_unsigned_16x16_products": {"accepted": 16, "candidate": 16},
        "production_layout": "pass",
        "generated_growth_bytes": layout["generated_growth_bytes"],
        "pre_helper_code_bytes_exact": layout[
            "pre_helper_generated_code_bytes_checked_exact"],
        "downstream_logical_instructions_exact": layout[
            "downstream_logical_instructions_compared"],
        "package_unexpected_changes": layout["unexpected_changes"],
        "complete_shipping_dependency_closure_audited_here": False,
    },
    "discriminator": {
        "checkpoint": 1344638527,
        "physical_core_index": 3,
        "affinity_mask": "0xc0",
        "priority": "above_normal",
        "desktop": "private inactive desktop",
        "requested_measurement_seconds": 5.0,
        "completed_order": ["candidate-a", "baseline-a"],
        "profile_origin_counters_in_order": [
            candidate_a["profile_origin_counter"],
            baseline_a["profile_origin_counter"],
        ],
    },
    "candidate_a": candidate_a,
    "baseline_a": baseline_a,
    "ordering_a": {
        "presentation_hz_delta": presentation_delta,
        "cycles_per_presentation_delta": cycles_delta,
        "render_ms_delta": render_delta,
        "wins_both_mandatory_metrics": ordering_a_wins,
        "candidate_lost_presentation_hz": presentation_delta < 0,
        "candidate_added_cycles_per_presentation": cycles_delta > 0,
    },
    "ordering_b": {
        "status": "skipped",
        "evidence_absent": True,
        "reason": "Ordering A lost both mandatory metrics",
    },
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
    "accepted/vhgame.txt",
    "accepted/compiler114m.exe",
    "accepted/i386m.bin",
    "candidate/fpsoft.txt",
    "candidate/vhgame.exe",
    "apply_candidate.py",
    "verify_model.py",
    "model.json",
    "build.json",
    "verify_production.py",
    "production-layout.json",
    "semantic-review.json",
    "run_arm.py",
    "finalize.py",
    "result.json",
    "candidate-a/capsule/report.json",
    "baseline-a/capsule/report.json",
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
    "task": 229,
    "date": "2026-08-30",
    "decision": "rejected-after-ordering-a",
    "files": files,
    "active": {
        "work/fp/fpsoft.txt": digest(ROOT / "work/fp/fpsoft.txt"),
        "work/vhgame.exe": digest(ROOT / "work/vhgame.exe"),
    },
    "current_files_match_accepted": True,
}
MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
