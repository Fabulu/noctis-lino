from pathlib import Path
import hashlib
import json

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/native-fmul-lowering-20260830"
SIMULATION_GATE = 18.206
ARMS = ("candidate-a", "baseline-a", "baseline-b", "candidate-b")
EXPECTED = {
    "accepted_fp": "063ecf40b0faab3b2779d8ff159b8fa815eec7b397de0d47e68223841e2a59cc",
    "candidate_fp": "95417cf412787e6f33c773f4f7eb4d5d685f44fceff6b6e21649024b4d8d62dc",
    "accepted_exe": "e18e8eb45ac0bc03aa2ee1f51ce1ae54f6ee00a0e8a7cef24cbd3adebcdf32a0",
    "candidate_exe": "70c7fc0a3f97270768eb86ea3ad30d18ffb2811fe07f821aff8ade7d2f2063d4",
    "vhgame_source": "f1af20ebd55b80e3a1439b0e30f1bb4e0bdcc8e00b7aced1a7b34d7395d3dc25",
    "accepted_compiler_source": "be83e4e9160497af7b3272a5f0245ce813a76927ff3807249dce5c0dd5d00e19",
    "candidate_compiler_source": "c3a185ed4539eff86ea639943e3ea103b9b3065a895ae97bd93de9ff7efb93a0",
    "accepted_compiler": "cfb39efc611dc96eab47f24c70cc7447a11f3b7cd874c49bfeb4934a42e67e87",
    "candidate_compiler": "facfb8b9373c548c569771978606fcd5d5273760ec7b1e2f0b4ee6bcc30d2e78",
    "cpu_pack": "1dd1433597c42e30b13bd55bfd02c19ebe465f3e020e4878906f66e7bfcdc4b7",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def arm_result(name):
    report = load(EVIDENCE / name / "capsule/report.json")
    kind = "candidate" if name.startswith("candidate") else "accepted"
    assert report["schema"] == 2 and report["scenario"] == "capsule"
    assert report["requested_measurement_seconds"] == 5.0
    assert report["command"][-2:] == ["clock=1344638527", "profile"]
    assert report["provenance"]["executable_sha256"] == EXPECTED[f"{kind}_exe"]
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
    }


accepted_fp = EVIDENCE / "accepted/fpsoft.txt"
candidate_fp = EVIDENCE / "candidate/fpsoft.txt"
accepted_exe = EVIDENCE / "accepted/vhgame.exe"
candidate_exe = EVIDENCE / "candidate/vhgame.exe"
accepted_compiler_source = EVIDENCE / "accepted/compiler114m.txt"
candidate_compiler_source = EVIDENCE / "candidate/compiler114m.txt"
accepted_compiler = EVIDENCE / "accepted/compiler114m.exe"
candidate_compiler = EVIDENCE / "candidate/compiler114m.exe"
assert digest(accepted_fp) == EXPECTED["accepted_fp"]
assert digest(candidate_fp) == EXPECTED["candidate_fp"]
assert digest(accepted_exe) == EXPECTED["accepted_exe"]
assert digest(candidate_exe) == EXPECTED["candidate_exe"]
assert accepted_exe.stat().st_size == candidate_exe.stat().st_size == 645_966
assert digest(accepted_compiler_source) == EXPECTED["accepted_compiler_source"]
assert digest(candidate_compiler_source) == EXPECTED["candidate_compiler_source"]
assert digest(accepted_compiler) == EXPECTED["accepted_compiler"]
assert digest(candidate_compiler) == EXPECTED["candidate_compiler"]
assert digest(EVIDENCE / "accepted/i386m.bin") == EXPECTED["cpu_pack"]
assert digest(EVIDENCE / "accepted/vhgame.txt") == EXPECTED["vhgame_source"]
assert digest(EVIDENCE / "candidate/vhgame.txt") == EXPECTED["vhgame_source"]

model = load(EVIDENCE / "model.json")
build = load(EVIDENCE / "build.json")
layout = load(EVIDENCE / "production-layout.json")
failclosed = load(EVIDENCE / "failclosed-layout-shifts.json")
runtime = load(EVIDENCE / "runtime-boundary.json")
review = load(EVIDENCE / "semantic-review.json")
fidelity = load(EVIDENCE / "fidelity.json")
assert all(item["status"] == "pass" for item in (
    model, build, layout, failclosed, runtime, review))
assert fidelity["fidelity_verdict"]["status"] == "pass"
assert fidelity["fidelity_verdict"]["baseline_repeat_control"] == "pass"
assert model["all_finite_binary64_pair_equivalence_algebraic"]
assert model["final_spill_overflow_detection_required_and_present"]
assert model["portable_tiny_and_overflow_xrej_policy_exact"]
assert model["candidate_x87_stack_net_change"] == 0
assert model["common_lino_change_is_zero_byte_marker_only"]
assert not model["raw_target_machine_block_added_to_shipping_lino"]
assert build["compiler_three_stage_fixpoint"]
assert build["marker_only_i386m_matches_accepted_byte_exactly"]
assert build["non_i386m_outputs_byte_exact"]
assert layout["package_bytes_outside_island_exact"]
assert layout["unexpected_changes"] == 0
assert layout["public_fmul_call_sites"] == 369
assert layout["all_public_fmul_call_sites_covered_by_x87_depth_analysis"] == 369
assert layout["all_direct_fmul_callers_redefine_before_flag_observation"]
assert failclosed["both_real_i386m_layout_controls_failed_closed"]
assert runtime["checks_passed"] == 24 and runtime["checks_failed"] == 0
assert review["final_review"]["remaining_material_findings"] == 0

arms = {name: arm_result(name) for name in ARMS}
origins = [arms[name]["profile_origin_counter"] for name in ARMS]
assert origins == sorted(origins)
for name in ("candidate-a", "candidate-b"):
    arms[name]["simulation_gate_hz"] = SIMULATION_GATE
    arms[name]["simulation_gate_pass"] = (
        arms[name]["simulation_hz"] >= SIMULATION_GATE)
    assert arms[name]["simulation_gate_pass"]
ordering_a = ordering(arms["candidate-a"], arms["baseline-a"])
ordering_b = ordering(arms["candidate-b"], arms["baseline-b"])
assert ordering_a["wins_both_mandatory_metrics"]
assert ordering_b["wins_both_mandatory_metrics"]

sustained_report = load(EVIDENCE / "sustained-60s/capsule/report.json")
assert sustained_report["schema"] == 2
assert sustained_report["requested_measurement_seconds"] == 60.0
assert sustained_report["command"][-2:] == ["clock=1344638527", "profile"]
assert sustained_report["provenance"]["executable_sha256"] == EXPECTED["candidate_exe"]
scheduling = sustained_report["provenance"]["scheduling"]
assert scheduling["comparable"]
assert scheduling["physical_core_index"] == 3
assert scheduling["requested_affinity_mask"] == "0xc0"
assert scheduling["requested_priority_class"] == "above_normal"
assert scheduling["actual"]["process_affinity_mask"] == "0xc0"
assert scheduling["actual"]["priority_class"] == "above_normal"
sustained_metrics = sustained_report["metrics"]
sustained_profile = sustained_report["profile"]
sustained = {
    "duration_seconds": 60.0,
    "presentation_hz": sustained_metrics["presentation_hz"],
    "simulation_hz": sustained_metrics["simulation_hz"],
    "simulation_gate_hz": SIMULATION_GATE,
    "simulation_gate_pass": sustained_metrics["simulation_hz"] >= SIMULATION_GATE,
    "missed_deadlines": sustained_profile["missed_deadlines"],
    "presentations": sustained_profile["presentations"],
    "missed_deadline_ratio": sustained_metrics["missed_deadline_ratio"],
    "maximum_lateness_ms": sustained_metrics["maximum_lateness_ms"],
    "total_lateness_ms": sustained_metrics["total_lateness_ms"],
    "render_ms": sustained_metrics["average_render_ms"],
    "present_ms": sustained_metrics["average_present_ms"],
    "process_cycles_per_presentation": sustained_metrics[
        "average_process_cycles_per_presentation"],
    "input_detection_to_effect_ms": sustained_metrics[
        "input_detection_to_effect_ms"],
    "input_effect_to_present_ms": sustained_metrics[
        "input_effect_to_present_ms"],
    "duplicate_pose_trace_available": False,
}
sustained["presentation_gate_pass"] = sustained["presentation_hz"] >= 60.0
sustained["deadline_gate_pass"] = sustained["missed_deadlines"] == 0
sustained["input_latency_gate_evaluated"] = False
sustained["duplicate_pose_gate_evaluated"] = False
sustained["sustained_60_hz_acceptance"] = (
    sustained["presentation_gate_pass"] and sustained["simulation_gate_pass"]
    and sustained["deadline_gate_pass"]
    and sustained["input_latency_gate_evaluated"]
    and sustained["duplicate_pose_gate_evaluated"])
sustained["classification"] = (
    "controlled variable/depressed-host whole-period screen; authentic simulation "
    "passed, but presentation, deadline, input-latency, and duplicate-pose acceptance did not")
assert sustained["simulation_gate_pass"]
assert not sustained["sustained_60_hz_acceptance"]

# Retention installs one coherent source/compiler/executable set. The compiler
# lowering is below the common-Lino source boundary and fails closed elsewhere.
assert digest(ROOT / "work/fp/fpsoft.txt") == EXPECTED["candidate_fp"]
assert digest(ROOT / "work/vhgame.exe") == EXPECTED["candidate_exe"]
assert digest(ROOT / "main/lib/gen/compiler114m.txt") == EXPECTED[
    "candidate_compiler_source"]
assert digest(ROOT / "main/lib/gen/compiler114m.exe") == EXPECTED[
    "candidate_compiler"]

verdict = fidelity["fidelity_verdict"]
result = {
    "schema": 1,
    "task": 235,
    "date": "2026-08-30",
    "decision": "retained-after-dual-ordering-and-fidelity",
    "reason": (
        "Both independent ABBA orderings improved presentation throughput and cycles "
        "per presentation, both candidate arms preserved authentic simulation, and "
        "synchronized authoritative fidelity passed. The private 60-second screen "
        "preserved simulation but did not establish sustained 60-Hz presentation or "
        "the deadline/input/duplicate-pose acceptance gates, so project acceptance remains open."),
    "source_boundary": {
        "common_lino_change": "zero-byte XSM exact i386m native fmul marker only",
        "shared_source": "work/fp/fpsoft.txt",
        "compiler_change": (
            "fail-closed equal-size exact-context i386m scalar FMul lowering below the shared source boundary"),
        "native_gameplay_or_renderer_code": False,
        "architecture_specific_lino_fork": False,
        "raw_target_machine_block_added_to_shipping_lino": False,
        "non_i386m_outputs_byte_exact": True,
        "complete_shipping_dependency_closure_audited_here": False,
        "closure_audit_deferred_to_release_audit": True,
    },
    "candidate": {
        "fpsoft_sha256": EXPECTED["candidate_fp"],
        "compiler_source_sha256": EXPECTED["candidate_compiler_source"],
        "compiler_sha256": EXPECTED["candidate_compiler"],
        "vhgame_source_sha256": EXPECTED["vhgame_source"],
        "executable_bytes": candidate_exe.stat().st_size,
        "executable_sha256": EXPECTED["candidate_exe"],
        "scalar_island_bytes": model["candidate_scalar_bytes"],
        "hardware_instruction": "FLD qword; FMUL qword; FSTP tbyte; FLD tbyte; FSTP qword",
        "public_fmul_call_sites": layout["public_fmul_call_sites"],
    },
    "accepted_baseline": {
        "task": 224,
        "fpsoft_sha256": EXPECTED["accepted_fp"],
        "compiler_source_sha256": EXPECTED["accepted_compiler_source"],
        "compiler_sha256": EXPECTED["accepted_compiler"],
        "executable_bytes": accepted_exe.stat().st_size,
        "executable_sha256": EXPECTED["accepted_exe"],
    },
    "focused_gates": {
        "semantic_model": "pass",
        "finite_pair_equivalence": "algebraic-all-input",
        "edge_cases": model["edge_cases"],
        "special_cases": model["special_cases"],
        "deterministic_random_finite_cases": model[
            "deterministic_random_finite_cases"],
        "final_p53_spill_overflow_detection": "pass",
        "portable_xrej_policy": "pass",
        "x87_peak": model["candidate_x87_stack_peak"],
        "x87_net_change": model["candidate_x87_stack_net_change"],
        "compiler_three_stage_fixpoint": True,
        "marker_only_accepted_compiler_output_byte_exact": True,
        "x64_outputs_byte_exact": True,
        "package_bytes_outside_scalar_island_exact": True,
        "changed_byte_values": layout["changed_byte_values"],
        "unexpected_changes": layout["unexpected_changes"],
        "public_fmul_calls_covered_by_x87_depth_analysis": layout[
            "all_public_fmul_call_sites_covered_by_x87_depth_analysis"],
        "all_public_fmul_callers_redefine_flags_before_observation": True,
        "complete_island_single_byte_mutations_failed_closed": layout[
            "exact_island_single_byte_mutations_fail_closed"],
        "fixed_prerequisite_single_byte_mutations_failed_closed": layout[
            "exact_prerequisite_single_byte_mutations_fail_closed"],
        "two_real_shifted_layout_controls": "pass",
        "runtime_boundary_checks": runtime["checks_passed"],
        "adversarial_review": review["verdict"],
        "architectural_x87_status_exact": False,
        "indexed_alias_ranges_exhaustively_proven": False,
        "indirect_transfer_targets_exhaustively_resolved": False,
        "claim_scope": "current exact selected i386m package",
    },
    "discriminator": {
        "checkpoint": 1344638527,
        "physical_core_index": 3,
        "affinity_mask": "0xc0",
        "priority": "above_normal",
        "desktop": "private inactive desktop",
        "requested_measurement_seconds": 5.0,
        "completed_order": list(ARMS),
        "profile_origin_counters_in_order": origins,
    },
    "candidate_a": arms["candidate-a"],
    "baseline_a": arms["baseline-a"],
    "ordering_a": ordering_a,
    "baseline_b": arms["baseline-b"],
    "candidate_b": arms["candidate-b"],
    "ordering_b": ordering_b,
    "combined_or_averaged_orderings_used": False,
    "fidelity": {
        "status": verdict["status"],
        "authoritative_renderer_products_exact": verdict[
            "authoritative_renderer_products_exact"],
        "game_vh_authoritative_state_bytes_0_71_exact": verdict[
            "game_vh_authoritative_state_bytes_0_71_exact"],
        "game_vh_host_timing_bytes_72_155_excluded": verdict[
            "game_vh_host_timing_bytes_72_155_excluded"],
        "game_local_exact_except_live_utc_unit_2_bytes_8_11": verdict[
            "game_local_exact_except_live_utc_unit_2_bytes_8_11"],
        "game_page_exact_outside_live_utc_telemetry_bounds_xy_74_2_92_6": verdict[
            "game_page_exact_outside_live_utc_telemetry_bounds_xy_74_2_92_6"],
        "baseline_repeat_control": verdict["baseline_repeat_control"],
    },
    "sustained_screen": sustained,
    "host_classification": (
        "controlled variable/depressed-host ABBA retention; not an absolute record"),
    "retained_healthy_absolute_record": {
        "presentation_hz": 60.15187849720224,
        "simulation_hz": 18.585131894484412,
        "evidence": "build/gui-deferred-demotions-20260829/baseline-a/capsule/report.json",
        "replaced": False,
    },
    "retained_healthy_minute_record": {
        "presentation_hz": 59.800276745077774,
        "simulation_hz": 18.255172298818,
        "evidence": "build/sustained-native-acceptance-20260829/controlled-60s/surface/report.json",
        "replaced": False,
    },
    "retained_production": {
        "fpsoft_sha256": EXPECTED["candidate_fp"],
        "compiler_source_sha256": EXPECTED["candidate_compiler_source"],
        "compiler_sha256": EXPECTED["candidate_compiler"],
        "executable_bytes": candidate_exe.stat().st_size,
        "executable_sha256": EXPECTED["candidate_exe"],
        "current_files_match_candidate": True,
    },
}
(EVIDENCE / "result.json").write_text(
    json.dumps(result, indent=2) + "\n", encoding="utf-8")

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
    "failclosed-layout-shifts.json", "runtime-boundary.json",
    "semantic-review.json", "run_arm.py", "timing-decision.json",
    "capture_fidelity.py", "compare_fidelity.py", "fidelity.json",
    "run_sustained.py", "finalize.py", "result.json",
] + [f"{name}/capsule/report.json" for name in ARMS] + [
    "sustained-60s/capsule/report.json"]
files = []
for relative in manifest_paths:
    path = EVIDENCE / relative
    assert path.is_file(), relative
    files.append({
        "path": (Path("build/native-fmul-lowering-20260830") / relative).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": digest(path),
    })
manifest = {
    "schema": 1,
    "task": 235,
    "date": "2026-08-30",
    "decision": "retained",
    "files": files,
    "active": {
        "work/fp/fpsoft.txt": EXPECTED["candidate_fp"],
        "work/vhgame.exe": EXPECTED["candidate_exe"],
        "main/lib/gen/compiler114m.txt": EXPECTED["candidate_compiler_source"],
        "main/lib/gen/compiler114m.exe": EXPECTED["candidate_compiler"],
    },
    "current_files_match_candidate": True,
    "sustained_60_hz_acceptance": False,
}
(EVIDENCE / "manifest.json").write_text(
    json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps({
    "decision": result["decision"],
    "ordering_a": ordering_a,
    "ordering_b": ordering_b,
    "fidelity": result["fidelity"]["status"],
    "sustained_screen": sustained,
    "retained_production": result["retained_production"],
}, indent=2))
