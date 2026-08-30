from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/buffered-limb-restoring-fsqrt-20260830"
SIMULATION_GATE = 18.206
EXPECTED = {
    "accepted_fp": "6b2e209be5b62013276514f8c418cafc92ecb9fd4d9fd6fbdf91453bfebe66d3",
    "candidate_fp": "063ecf40b0faab3b2779d8ff159b8fa815eec7b397de0d47e68223841e2a59cc",
    "accepted_exe": "c4a62f5068262239a8a5665c443a75784fa2472941c9dfdb8fb731f5c8217ca2",
    "candidate_exe": "e18e8eb45ac0bc03aa2ee1f51ce1ae54f6ee00a0e8a7cef24cbd3adebcdf32a0",
    "vhgame_source": "f1af20ebd55b80e3a1439b0e30f1bb4e0bdcc8e00b7aced1a7b34d7395d3dc25",
    "compiler": "cfb39efc611dc96eab47f24c70cc7447a11f3b7cd874c49bfeb4934a42e67e87",
    "cpu_pack": "1dd1433597c42e30b13bd55bfd02c19ebe465f3e020e4878906f66e7bfcdc4b7",
}
ARMS = ("candidate-a", "baseline-a", "baseline-b", "candidate-b")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def arm_result(name):
    report = load(EVIDENCE / name / "capsule/report.json")
    kind = "candidate" if name.startswith("candidate") else "accepted"
    assert report["scenario"] == "capsule"
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
    return {
        "presentation_hz": metrics["presentation_hz"],
        "simulation_hz": metrics["simulation_hz"],
        "render_ms": metrics["average_render_ms"],
        "present_ms": metrics["average_present_ms"],
        "process_cycles_per_presentation": metrics[
            "average_process_cycles_per_presentation"],
        "missed_deadlines": report["profile"]["missed_deadlines"],
    }


accepted_fp = EVIDENCE / "accepted/fpsoft.txt"
candidate_fp = EVIDENCE / "candidate/fpsoft.txt"
accepted_exe = EVIDENCE / "accepted/vhgame.exe"
candidate_exe = EVIDENCE / "candidate/vhgame.exe"
accepted_vhgame = EVIDENCE / "accepted/vhgame.txt"
candidate_vhgame = EVIDENCE / "candidate/vhgame.txt"
if not candidate_vhgame.exists():
    shutil.copyfile(accepted_vhgame, candidate_vhgame)
assert digest(accepted_fp) == EXPECTED["accepted_fp"]
assert digest(candidate_fp) == EXPECTED["candidate_fp"]
assert digest(accepted_exe) == EXPECTED["accepted_exe"]
assert digest(candidate_exe) == EXPECTED["candidate_exe"]
assert digest(accepted_vhgame) == digest(candidate_vhgame) == EXPECTED["vhgame_source"]
assert digest(EVIDENCE / "accepted/compiler114m.exe") == EXPECTED["compiler"]
assert digest(EVIDENCE / "accepted/i386m.bin") == EXPECTED["cpu_pack"]
assert digest(ROOT / "work/fp/fpsoft.txt") == EXPECTED["candidate_fp"]
assert digest(ROOT / "work/vhgame.exe") == EXPECTED["candidate_exe"]
assert digest(ROOT / "work/vhgame.txt") == EXPECTED["vhgame_source"]

model = load(EVIDENCE / "model.json")
review = load(EVIDENCE / "semantic-review.json")
build = load(EVIDENCE / "build.json")
layout = load(EVIDENCE / "production-layout.json")
fidelity = load(EVIDENCE / "fidelity.json")
assert model["status"] == review["status"] == build["status"] == layout["status"] == "pass"
assert fidelity["fidelity_verdict"]["status"] == "pass"
assert fidelity["fidelity_verdict"]["baseline_repeat_control"] == "pass"

arms = {name: arm_result(name) for name in ARMS}
for name in ("candidate-a", "candidate-b"):
    arms[name]["simulation_gate_hz"] = SIMULATION_GATE
    arms[name]["simulation_gate_pass"] = arms[name]["simulation_hz"] >= SIMULATION_GATE
    assert arms[name]["simulation_gate_pass"]

ordering_a = {
    "presentation_hz_delta": (
        arms["candidate-a"]["presentation_hz"] - arms["baseline-a"]["presentation_hz"]),
    "cycles_per_presentation_delta": (
        arms["candidate-a"]["process_cycles_per_presentation"]
        - arms["baseline-a"]["process_cycles_per_presentation"]),
}
ordering_a["wins_both_mandatory_metrics"] = (
    ordering_a["presentation_hz_delta"] > 0
    and ordering_a["cycles_per_presentation_delta"] < 0)
ordering_b = {
    "presentation_hz_delta": (
        arms["candidate-b"]["presentation_hz"] - arms["baseline-b"]["presentation_hz"]),
    "cycles_per_presentation_delta": (
        arms["candidate-b"]["process_cycles_per_presentation"]
        - arms["baseline-b"]["process_cycles_per_presentation"]),
}
ordering_b["wins_both_mandatory_metrics"] = (
    ordering_b["presentation_hz_delta"] > 0
    and ordering_b["cycles_per_presentation_delta"] < 0)
assert ordering_a["wins_both_mandatory_metrics"]
assert ordering_b["wins_both_mandatory_metrics"]

sustained_report = load(EVIDENCE / "sustained-30s/capsule/report.json")
assert sustained_report["requested_measurement_seconds"] == 30.0
assert sustained_report["provenance"]["executable_sha256"] == EXPECTED["candidate_exe"]
sustained_metrics = sustained_report["metrics"]
sustained = {
    "duration_seconds": 30.0,
    "presentation_hz": sustained_metrics["presentation_hz"],
    "simulation_hz": sustained_metrics["simulation_hz"],
    "simulation_gate_pass": sustained_metrics["simulation_hz"] >= SIMULATION_GATE,
    "missed_deadlines": sustained_report["profile"]["missed_deadlines"],
    "presentations": sustained_report["profile"]["presentations"],
    "maximum_lateness_ms": sustained_metrics["maximum_lateness_ms"],
    "render_ms": sustained_metrics["average_render_ms"],
    "present_ms": sustained_metrics["average_present_ms"],
    "process_cycles_per_presentation": sustained_metrics[
        "average_process_cycles_per_presentation"],
}
sustained["sustained_60_hz_acceptance"] = (
    sustained["presentation_hz"] >= 60.0 and sustained["simulation_gate_pass"]
    and sustained["missed_deadlines"] == 0)
sustained["classification"] = (
    "controlled whole-period screen; host/presentation stalls prevented sustained acceptance")
assert sustained["simulation_gate_pass"]
assert not sustained["sustained_60_hz_acceptance"]

verdict = fidelity["fidelity_verdict"]
result = {
    "schema": 1,
    "task": 224,
    "date": "2026-08-30",
    "decision": "retained-after-dual-ordering-and-fidelity",
    "reason": (
        "Both independent ABBA orderings improved presentation throughput and cycles per "
        "presentation, both candidate arms preserved simulation above 18.206 Hz, and "
        "synchronized authoritative fidelity passed. The separate 30-second whole-period "
        "screen did not establish sustained 60 Hz, so that project acceptance remains open."),
    "source_boundary": {
        "implementation": (
            "one direct active-limb value buffer with three cold dynamic handoffs in the "
            "common tracked fpsoft Lino source"),
        "shared_lino_source_changed": True,
        "shared_source": "work/fp/fpsoft.txt",
        "native_gameplay_or_renderer_code": False,
        "architecture_specific_lino_fork": False,
        "raw_target_machine_block": False,
        "compiler_changed": False,
        "cpu_pack_changed": False,
    },
    "candidate": {
        "description": (
            "retain 64 restoring decisions while shifting one direct buffered 32-bit "
            "radicand limb per pair and loading the next fixed limb only at cold boundaries"),
        "fpsoft_sha256": EXPECTED["candidate_fp"],
        "vhgame_source_sha256": EXPECTED["vhgame_source"],
        "executable_bytes": candidate_exe.stat().st_size,
        "executable_sha256": EXPECTED["candidate_exe"],
    },
    "accepted_baseline": {
        "fpsoft_sha256": EXPECTED["accepted_fp"],
        "vhgame_source_sha256": EXPECTED["vhgame_source"],
        "executable_bytes": accepted_exe.stat().st_size,
        "executable_sha256": EXPECTED["accepted_exe"],
    },
    "toolchain": {
        "compiler_sha256": EXPECTED["compiler"],
        "cpu_pack_sha256": EXPECTED["cpu_pack"],
        "build_entry": "lino_build.ps1",
        "private_inactive_desktop": True,
        "warnings": build["warnings"],
        "errors": build["errors"],
        "preliminary_relative_path_invocation": build[
            "preliminary_relative_path_invocation"],
    },
    "focused_gates": {
        "semantic_model": model["status"],
        "adversarial_semantic_review": review["status"],
        "generic_normalized_mantissa_cases": model["generic_normalized_mantissa_cases"],
        "binary64_pipeline_cases": model["binary64_pipeline_cases"],
        "special_dispatch_cases": model["special_dispatch_cases"],
        "public_state_cases": model["public_state_cases"],
        "accepted_private_residual_exact": model["accepted_private_residual_exact"],
        "accepted_p64_root_rounding_exact": model["accepted_p64_root_rounding_exact"],
        "p53_binary64_spill_exact": model["p53_binary64_spill_exact"],
        "accepted_restoring_iterations": model[
            "baseline_restoring_iterations_per_positive_root"],
        "candidate_restoring_iterations": model[
            "candidate_restoring_iterations_per_positive_root"],
        "accepted_radix_limb_shifts": model[
            "baseline_radix_limb_shifts_per_positive_root"],
        "candidate_radix_limb_shifts": model[
            "candidate_radix_limb_shifts_per_positive_root"],
        "candidate_hot_dynamic_pointer_reads": model[
            "candidate_hot_dynamic_pointer_reads_per_positive_root"],
        "candidate_direct_buffer_reads": model[
            "candidate_direct_buffer_reads_per_positive_root"],
        "candidate_dynamic_limb_handoffs": model[
            "candidate_dynamic_limb_handoffs_per_positive_root"],
        "production_layout": layout["status"],
        "root_helper_range": [
            int(layout["root_helper_start"], 16), int(layout["root_helper_island_end"], 16)],
        "candidate_body_end": int(layout["candidate_executable_body_end"], 16),
        "accepted_calibration_bytes_consumed": layout[
            "accepted_unreachable_calibration_bytes"],
        "changed_byte_values": layout["changed_byte_values"],
        "unexpected_changed_bytes": layout["unexpected_changes"],
        "all_package_bytes_outside_helper_exact": layout[
            "package_bytes_outside_root_island_exact"],
        "entry_and_downstream_addresses_exact": (
            layout["helper_entry_and_endpoint_preserved"]
            and layout["downstream_addresses_and_bytes_exact"]),
    },
    "discriminator": {
        "clock_seconds": 1344638527,
        "physical_core_index": 3,
        "affinity_mask": "0xc0",
        "priority": "above_normal",
        "desktop": "private inactive desktop",
        "requested_measurement_seconds": 5.0,
        "completed_order": list(ARMS),
    },
    "candidate_a": arms["candidate-a"],
    "baseline_a": arms["baseline-a"],
    "ordering_a": ordering_a,
    "baseline_b": arms["baseline-b"],
    "candidate_b": arms["candidate-b"],
    "ordering_b": ordering_b,
    "contradictory_orderings_averaged": False,
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
    "host_classification": "controlled variable/depressed-host ABBA retention; not an absolute record",
    "retained_absolute_record": {
        "presentation_hz": 60.15187849720224,
        "simulation_hz": 18.585131894484412,
        "evidence": "build/gui-deferred-demotions-20260829/baseline-a/capsule/report.json",
        "replaced": False,
    },
    "retained_production": {
        "fpsoft_sha256": EXPECTED["candidate_fp"],
        "executable_bytes": candidate_exe.stat().st_size,
        "executable_sha256": EXPECTED["candidate_exe"],
        "current_files_match_candidate": True,
    },
}
result_path = EVIDENCE / "result.json"
result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

manifest_paths = [
    "accepted/fpsoft.txt", "accepted/vhgame.txt", "accepted/vhgame.exe",
    "accepted/compiler114m.exe", "accepted/i386m.bin",
    "candidate/fpsoft.txt", "candidate/vhgame.txt", "candidate/vhgame.exe",
    "apply_candidate.py", "verify_model.py", "model.json", "semantic-review.json",
    "build.json", "verify_production.py", "production-layout.json", "run_arm.py",
    "capture_fidelity.py", "compare_fidelity.py", "fidelity.json",
    "run_sustained.py", "finalize.py", "result.json",
] + [f"{name}/capsule/report.json" for name in ARMS] + [
    "sustained-30s/capsule/report.json"]
files = []
for relative in manifest_paths:
    path = EVIDENCE / relative
    assert path.is_file()
    files.append({
        "path": (Path("build/buffered-limb-restoring-fsqrt-20260830") / relative).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": digest(path),
    })
manifest = {
    "schema": 1,
    "task": 224,
    "date": "2026-08-30",
    "decision": "retained",
    "files": files,
    "active": {
        "work/fp/fpsoft.txt": EXPECTED["candidate_fp"],
        "work/vhgame.exe": EXPECTED["candidate_exe"],
    },
    "current_files_match_candidate": True,
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
