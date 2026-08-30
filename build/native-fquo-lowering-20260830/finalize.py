from pathlib import Path
import hashlib
import json

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/native-fquo-lowering-20260830"
RESULT = EVIDENCE / "result.json"
MANIFEST = EVIDENCE / "manifest.json"
ACCEPTED_FP_SHA256 = (
    "95417cf412787e6f33c773f4f7eb4d5d685f44fceff6b6e21649024b4d8d62dc")
CANDIDATE_FP_SHA256 = (
    "6681e59e64835fc25ec87ec18387e4c448208cef7fd03040768ebb5c613c7c37")
ACCEPTED_EXE_SHA256 = (
    "70c7fc0a3f97270768eb86ea3ad30d18ffb2811fe07f821aff8ade7d2f2063d4")
CANDIDATE_EXE_SHA256 = (
    "fcb0b008c7d05e383a7759ec6978c7189aae669811c9b4348a511e31c93c5340")
ACCEPTED_COMPILER_SOURCE_SHA256 = (
    "c3a185ed4539eff86ea639943e3ea103b9b3065a895ae97bd93de9ff7efb93a0")
CANDIDATE_COMPILER_SOURCE_SHA256 = (
    "1d424fd70b0aeccf689acbc527419c566895c3e591eb3646b1db6e438f15d4c2")
ACCEPTED_COMPILER_SHA256 = (
    "facfb8b9373c548c569771978606fcd5d5273760ec7b1e2f0b4ee6bcc30d2e78")
CANDIDATE_COMPILER_SHA256 = (
    "07621242048e1e49ee01db07f614a6cd0f37a87aef3235139ed17f5b8e666e27")
CPU_PACK_SHA256 = (
    "1dd1433597c42e30b13bd55bfd02c19ebe465f3e020e4878906f66e7bfcdc4b7")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(relative):
    return json.loads((EVIDENCE / relative).read_text(encoding="utf-8"))


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

model = load("model.json")
build = load("build.json")
layout = load("production-layout.json")
failclosed = load("failclosed-layout-shifts.json")
runtime = load("runtime-boundary.json")
review = load("semantic-review.json")
timing = load("timing-decision.json")
assert all(item["status"] == "pass" for item in (
    model, build, layout, failclosed, runtime, review, timing))
assert review["final_review"]["remaining_material_findings"] == 0
assert model["common_lino_change_is_zero_byte_marker_only"]
assert not model["raw_target_machine_block_added_to_shipping_lino"]
assert model["all_finite_nonzero_binary64_pair_equivalence_algebraic"]
assert model["terminal_x_image_matches_portable_all_paths"]
assert model["portable_tiny_and_overflow_xrej_policy_exact"]
assert model["candidate_x87_stack_net_change"] == 0
assert model["simulation_constants"] == [18206, 60000]
assert build["compiler_three_stage_fixpoint"]
assert build["marker_only_i386m_matches_accepted_byte_exactly"]
assert build["non_i386m_output_comparison_run"]
assert build["non_i386m_outputs_byte_exact"]
assert build["private_inactive_desktop"] and not build["default_desktop"]
assert layout["package_bytes_outside_island_exact"]
assert layout["unexpected_changes"] == 0
assert layout["candidate_xscratch_terminal_state_equals_portable"]
assert layout["all_generated_transfer_boundaries_have_empty_x87_stack"]
assert layout["x87_entry_induction_complete_for_decoded_package"]
assert not layout["complete_shipping_dependency_closure_audited"]
assert failclosed["both_real_i386m_layout_controls_failed_closed"]
assert failclosed["private_inactive_desktop"] and not failclosed["default_desktop"]
assert runtime["checks_passed"] == 24 and runtime["checks_failed"] == 0

assert timing["decision"] == "rejected-candidate-a-simulation"
assert timing["completed_order"] == ["candidate-a"]
assert not timing["candidate_a"]["simulation_gate_pass"]
assert timing["candidate_a"]["simulation_hz"] < 18.206
assert timing["baseline_a"] is None
assert timing["baseline_b"] is None
assert timing["candidate_b"] is None
assert timing["ordering_a"] is None and timing["ordering_b"] is None
assert not timing["combined_or_averaged_orderings_used"]
assert not timing["fidelity_permitted"]
for path in (
        EVIDENCE / "baseline-a/capsule/report.json",
        EVIDENCE / "baseline-b/capsule/report.json",
        EVIDENCE / "candidate-b/capsule/report.json",
        EVIDENCE / "fidelity.json",
        EVIDENCE / "sustained-60s/capsule/report.json"):
    assert not path.exists()

# Candidate A installed the candidate set. The early-stop path restored the
# retained Task #235 source/compiler/executable set before finalization.
assert digest(ROOT / "work/fp/fpsoft.txt") == ACCEPTED_FP_SHA256
assert digest(ROOT / "work/vhgame.exe") == ACCEPTED_EXE_SHA256
assert digest(ROOT / "main/lib/gen/compiler114m.txt") == (
    ACCEPTED_COMPILER_SOURCE_SHA256)
assert digest(ROOT / "main/lib/gen/compiler114m.exe") == ACCEPTED_COMPILER_SHA256

candidate_a = timing["candidate_a"]
result = {
    "schema": 1,
    "task": 237,
    "date": "2026-08-30",
    "decision": "rejected-candidate-a-simulation",
    "reason": (
        "Candidate A measured 18.174308137133416-Hz simulation, below the binding "
        "18.206-Hz authentic-simulation gate. The candidate was rejected immediately; "
        "no baseline, second ordering, fidelity capture, or sustained screen was "
        "permitted, and retained Task #235 production was restored byte-exactly."),
    "candidate_change_scope": {
        "common_lino_change": "zero-byte XSQ exact i386m native quo marker only",
        "compiler_change": (
            "fail-closed exact-island i386m p64 FDIV lowering with portable XToF64 spill below the shared source boundary"),
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
        "instruction_bytes": model["candidate_instruction_bytes"],
        "unreachable_nop_bytes": model["candidate_nop_padding_bytes"],
        "changed_byte_values": layout["changed_byte_values"],
    },
    "accepted_baseline": {
        "task": 235,
        "description": "retained exact native FMul lowering",
        "fpsoft_sha256": ACCEPTED_FP_SHA256,
        "compiler_source_sha256": ACCEPTED_COMPILER_SOURCE_SHA256,
        "compiler_sha256": ACCEPTED_COMPILER_SHA256,
        "executable_bytes": accepted_exe.stat().st_size,
        "executable_sha256": ACCEPTED_EXE_SHA256,
    },
    "focused_gates": {
        "source_and_binary64_model": "pass",
        "edge_cases": model["edge_cases"],
        "special_and_zero_cases": model["special_and_zero_cases"],
        "deterministic_random_finite_cases": model[
            "deterministic_random_finite_cases"],
        "terminal_x_image_exact": True,
        "public_a_through_e_exact": True,
        "candidate_x87_stack_net_zero": True,
        "architectural_x87_status_exact": False,
        "selected_package_status_readers_observe_candidate_status": False,
        "runtime_boundary_checks": runtime["checks_passed"],
        "compiler_three_stage_fixpoint": True,
        "marker_only_i386m_output_byte_exact": True,
        "non_i386m_x64_outputs_byte_exact": True,
        "package_bytes_outside_237_byte_island_exact": True,
        "package_unexpected_changes": 0,
        "all_island_single_byte_mutations_fail_closed": True,
        "both_real_shifted_layout_builds_failed_closed": True,
        "adversarial_review": "pass-after-evidence-hardening",
        "claim_scope": "current exact selected i386m candidate package only",
        "indexed_alias_ranges_exhaustively_proven": False,
        "indirect_transfer_targets_exhaustively_resolved": False,
    },
    "discriminator": {
        "checkpoint": timing["checkpoint"],
        "physical_core_index": timing["physical_core_index"],
        "affinity_mask": timing["affinity_mask"],
        "priority": timing["priority"],
        "desktop": timing["desktop"],
        "requested_measurement_seconds": timing[
            "requested_measurement_seconds"],
        "completed_order": timing["completed_order"],
        "early_stop_gate": "candidate-a simulation >= 18.206 Hz",
    },
    "candidate_a": candidate_a,
    "baseline_a": None,
    "ordering_a": None,
    "baseline_b": None,
    "candidate_b": None,
    "ordering_b": None,
    "combined_interpretation": {
        "status": "not-applicable",
        "averaging_used": False,
        "reason": "The binding Candidate-A simulation gate stopped the experiment.",
    },
    "fidelity": {
        "status": "skipped",
        "evidence_absent": True,
        "reason": "Fidelity is permitted only after two independent timing wins.",
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
        "task": 235,
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
    "accepted/compiler114m.txt", "accepted/compiler114m.exe",
    "accepted/i386m.bin", "accepted/fpsoft.txt", "accepted/fpabi.txt",
    "accepted/vhgame.txt", "accepted/vhgame.exe",
    "candidate/compiler114m.txt", "candidate/compiler114m.exe",
    "candidate/fpsoft.txt", "candidate/vhgame.txt", "candidate/vhgame.exe",
    "apply_candidate.py", "prepared-source.json", "verify_model.py",
    "model.json", "build_candidate.py", "build.json",
    "marker-only-i386m/vhgame.exe", "accepted-compiler-x64/vhgame.exe",
    "candidate-compiler-x64/vhgame.exe", "verify_production.py",
    "production-layout.json", "verify_fail_closed_build.py",
    "failclosed-layout-shifts.json", "failclosed-fa-shift/fpabi.txt",
    "failclosed-fa-shift-accepted/vhgame.exe",
    "failclosed-fa-shift-candidate/vhgame.exe",
    "failclosed-xrej-shift/fpsoft.txt",
    "failclosed-xrej-shift-accepted/vhgame.exe",
    "failclosed-xrej-shift-candidate/vhgame.exe", "runtime-boundary.json",
    "semantic-review.json", "run_arm.py", "evaluate_timing.py",
    "timing-decision.json", "capture_fidelity.py", "compare_fidelity.py",
    "run_sustained.py", "switch_production.py", "finalize.py", "result.json",
    "candidate-a/capsule/report.json",
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
    "task": 237,
    "date": "2026-08-30",
    "decision": "rejected-candidate-a-simulation",
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
