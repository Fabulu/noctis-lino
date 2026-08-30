from pathlib import Path
import hashlib
import json
import runpy

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/register-trial-restoring-fsqrt-20260830"
RESULT = EVIDENCE / "result.json"
MANIFEST = EVIDENCE / "manifest.json"
ACCEPTED_FP_SHA256 = (
    "063ecf40b0faab3b2779d8ff159b8fa815eec7b397de0d47e68223841e2a59cc")
CANDIDATE_FP_SHA256 = (
    "8fee66095ee27f0c7da81900f34603d2bd4d7d60c356ce51a0cebcb158fc291d")
ACCEPTED_EXE_SHA256 = (
    "e18e8eb45ac0bc03aa2ee1f51ce1ae54f6ee00a0e8a7cef24cbd3adebcdf32a0")
CANDIDATE_EXE_SHA256 = (
    "33f235c60cee4852b73723830cf691bf205d21f0bd054a746705fb66a3a420c6")
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
assert model["candidate_file_equals_exact_transform"]
assert model["candidate_source_sha256"] == CANDIDATE_FP_SHA256
assert model["integer_root_exact"]
assert model["accepted_private_residual_exact"]
assert model["accepted_p64_root_rounding_exact"]
assert model["p53_binary64_spill_exact"]
assert model["simulation_constants"] == [18206, 60000]
assert model["verifier_sha256"] == digest(EVIDENCE / "verify_model.py")
assert layout["status"] == "pass"
assert layout["candidate_sha256"] == CANDIDATE_EXE_SHA256
assert layout["package_bytes_outside_root_island_exact"]
assert layout["changed_byte_values"] == 739
assert layout["unexpected_changes"] == 0
assert layout["generated_remainder_shift_exact"]
assert layout["generated_unsigned_trial_comparison_exact"]
assert layout["generated_borrow_subtraction_exact"]
assert layout["register_odd_trial_schedule_exact"]
assert layout["final_root_decode_exact"]
assert layout["public_fsqrt_generated_pushal_call_popal_exact"]
assert layout["candidate_unreachable_padding_direct_entries"] == 0
assert review["status"] == "pass-after-evidence-hardening"
assert review["implementation_semantics"] == "pass"
assert review["final_review"]["status"] == "pass"
assert review["final_review"]["remaining_defects_in_re_reviewed_scope"] == 0
assert build["status"] == "pass"
assert build["private_inactive_desktop"]
assert build["build_entry"] == "lino_build.ps1"
assert build["errors"] == 0
assert build["candidate_executable_sha256"] == CANDIDATE_EXE_SHA256

candidate_a_report = EVIDENCE / "candidate-a/capsule/report.json"
baseline_a_report = EVIDENCE / "baseline-a/capsule/report.json"
candidate_a = arm(candidate_a_report, CANDIDATE_EXE_SHA256)
baseline_a = arm(baseline_a_report, ACCEPTED_EXE_SHA256)
candidate_a["simulation_gate_hz"] = 18.206
candidate_a["simulation_gate_pass"] = candidate_a["simulation_hz"] >= 18.206
assert candidate_a["simulation_gate_pass"]
presentation_delta = (
    candidate_a["presentation_hz"] - baseline_a["presentation_hz"])
cycles_delta = (
    candidate_a["process_cycles_per_presentation"]
    - baseline_a["process_cycles_per_presentation"])
assert presentation_delta < 0
assert cycles_delta > 0
ordering_a_wins = presentation_delta > 0 and cycles_delta < 0
assert not ordering_a_wins
assert not (EVIDENCE / "baseline-b/capsule/report.json").exists()
assert not (EVIDENCE / "candidate-b/capsule/report.json").exists()
assert not (EVIDENCE / "fidelity.json").exists()
assert not (EVIDENCE / "sustained-30s/capsule/report.json").exists()

# The strict Ordering-A rejection restored the last accepted production pair.
assert digest(ROOT / "work/fp/fpsoft.txt") == ACCEPTED_FP_SHA256
assert digest(ROOT / "work/vhgame.exe") == ACCEPTED_EXE_SHA256

result = {
    "schema": 1,
    "task": 226,
    "date": "2026-08-30",
    "decision": "rejected-after-ordering-a",
    "reason": (
        "Candidate A preserved simulation above 18.206 Hz, but it lost both "
        "mandatory Ordering-A metrics: presentation throughput decreased and "
        "cycles per presentation increased. The binding discriminator therefore "
        "stopped before Ordering B, fidelity, and sustained screening."),
    "source_boundary": {
        "implementation": (
            "odd-trial carrier T=2*q+1 in C:D within the common tracked "
            "fpsoft Lino source"),
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
            "retain the buffered radicand schedule while carrying T=2*q+1 "
            "in C:D and decoding q once after 64 restoring decisions"),
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
        "generic_normalized_mantissa_cases": model[
            "generic_normalized_mantissa_cases"],
        "binary64_pipeline_cases": model["binary64_pipeline_cases"],
        "special_dispatch_cases": model["special_dispatch_cases"],
        "integer_root_exact": True,
        "accepted_private_residual_exact": True,
        "accepted_p64_root_rounding_exact": True,
        "p53_binary64_spill_exact": True,
        "production_layout": "pass",
        "root_helper_range": [0x256F1, 0x25B49],
        "changed_byte_values": layout["changed_byte_values"],
        "unexpected_changed_bytes": layout["unexpected_changes"],
        "all_package_bytes_outside_helper_exact": True,
        "generated_remainder_comparison_subtraction_exact": True,
        "generated_public_register_wrapper_exact": True,
    },
    "discriminator": {
        "clock_seconds": 1344638527,
        "physical_core_index": 3,
        "affinity_mask": "0xc0",
        "priority": "above_normal",
        "desktop": "private inactive desktop",
        "requested_measurement_seconds": 5.0,
        "completed_order": ["candidate-a", "baseline-a"],
    },
    "candidate_a": candidate_a,
    "baseline_a": baseline_a,
    "ordering_a": {
        "presentation_hz_delta": presentation_delta,
        "cycles_per_presentation_delta": cycles_delta,
        "wins_both_mandatory_metrics": ordering_a_wins,
        "candidate_lost_presentation_hz": presentation_delta < 0,
        "candidate_lost_cycles_per_presentation": cycles_delta > 0,
    },
    "ordering_b": {
        "status": "skipped",
        "reason": "Ordering A lost both mandatory metrics",
    },
    "contradictory_orderings_averaged": False,
    "fidelity": {
        "status": "skipped",
        "reason": "Fidelity runs are permitted only after both orderings win",
    },
    "sustained_screen": {
        "status": "skipped",
        "reason": "Rejected candidate was not eligible for sustained screening",
    },
    "host_classification": "controlled depressed-host Ordering-A rejection",
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
    "task": 226,
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
