from pathlib import Path
import hashlib
import json

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/native-fquo-lowering-20260830"
OUTPUT = EVIDENCE / "timing-decision.json"
ARMS = ("candidate-a", "baseline-a", "baseline-b", "candidate-b")
ACCEPTED_EXE_SHA256 = (
    "70c7fc0a3f97270768eb86ea3ad30d18ffb2811fe07f821aff8ade7d2f2063d4")
CANDIDATE_EXE_SHA256 = (
    "fcb0b008c7d05e383a7759ec6978c7189aae669811c9b4348a511e31c93c5340")


def load_arm(name):
    path = EVIDENCE / name / "capsule/report.json"
    if not path.is_file():
        return None
    report = json.loads(path.read_text(encoding="utf-8"))
    expected = (CANDIDATE_EXE_SHA256 if name.startswith("candidate")
                else ACCEPTED_EXE_SHA256)
    assert report["schema"] == 2 and report["scenario"] == "capsule"
    assert report["requested_measurement_seconds"] == 5.0
    assert report["command"][-2:] == ["clock=1344638527", "profile"]
    assert report["provenance"]["executable_sha256"] == expected
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
        "presentations": report["profile"]["presentations"],
        "simulation_ticks": report["profile"]["simulation_ticks"],
        "profile_origin_counter": report["profile"]["profile_origin_counter"],
    }


def ordering(candidate, baseline):
    presentation_delta = candidate["presentation_hz"] - baseline[
        "presentation_hz"]
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


arms = {name: load_arm(name) for name in ARMS}
present = [name for name in ARMS if arms[name] is not None]
assert present == list(ARMS[:len(present)])
assert present
origin_counters = [arms[name]["profile_origin_counter"] for name in present]
assert origin_counters == sorted(origin_counters)

candidate_a = arms["candidate-a"]
candidate_a["simulation_gate_hz"] = 18.206
candidate_a["simulation_gate_pass"] = candidate_a["simulation_hz"] >= 18.206
ordering_a = None
ordering_b = None
if not candidate_a["simulation_gate_pass"]:
    assert present == ["candidate-a"]
    decision = "rejected-candidate-a-simulation"
    reason = "Candidate A failed the authentic 18.206-Hz simulation gate."
elif arms["baseline-a"] is None:
    decision = "incomplete-awaiting-baseline-a"
    reason = "Candidate A passed simulation; Ordering A is not complete."
else:
    ordering_a = ordering(candidate_a, arms["baseline-a"])
    if not ordering_a["wins_both_mandatory_metrics"]:
        assert present == ["candidate-a", "baseline-a"]
        decision = "rejected-ordering-a"
        reason = (
            "Ordering A did not independently improve presentation and reduce "
            "cycles per presentation.")
    elif arms["candidate-b"] is None:
        decision = "incomplete-awaiting-ordering-b"
        reason = "Ordering A won; Ordering B is not complete."
    else:
        candidate_b = arms["candidate-b"]
        candidate_b["simulation_gate_hz"] = 18.206
        candidate_b["simulation_gate_pass"] = (
            candidate_b["simulation_hz"] >= 18.206)
        ordering_b = ordering(candidate_b, arms["baseline-b"])
        if not candidate_b["simulation_gate_pass"]:
            decision = "rejected-candidate-b-simulation"
            reason = "Candidate B failed the authentic 18.206-Hz simulation gate."
        elif not ordering_b["wins_both_mandatory_metrics"]:
            decision = "rejected-ordering-b"
            reason = (
                "Ordering A won but Ordering B did not independently improve "
                "presentation and reduce cycles per presentation; combining or "
                "averaging contradictory orderings is forbidden.")
        else:
            decision = "eligible-for-fidelity"
            reason = (
                "Both independent orderings preserved simulation and won both "
                "mandatory timing metrics. Authoritative fidelity is now permitted.")

result = {
    "schema": 1,
    "task": 237,
    "status": "pass",
    "decision": decision,
    "reason": reason,
    "completed_order": present,
    "checkpoint": 1344638527,
    "requested_measurement_seconds": 5.0,
    "physical_core_index": 3,
    "affinity_mask": "0xc0",
    "priority": "above_normal",
    "desktop": "private inactive desktop",
    "candidate_a": candidate_a,
    "baseline_a": arms["baseline-a"],
    "ordering_a": ordering_a,
    "baseline_b": arms["baseline-b"],
    "candidate_b": arms["candidate-b"],
    "ordering_b": ordering_b,
    "combined_or_averaged_orderings_used": False,
    "fidelity_permitted": decision == "eligible-for-fidelity",
}
OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
