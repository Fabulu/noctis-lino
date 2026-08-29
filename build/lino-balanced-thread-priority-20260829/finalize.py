from pathlib import Path
import hashlib
import json

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/lino-balanced-thread-priority-20260829"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def report(relative):
    return json.loads((EVIDENCE / relative).read_text(encoding="utf-8"))


candidate = report("candidate-a/capsule/report.json")
baseline = report("baseline-a/capsule/report.json")
cm = candidate["metrics"]
bm = baseline["metrics"]
assert cm["simulation_hz"] >= 18.206
presentation_delta = cm["presentation_hz"] - bm["presentation_hz"]
cycles_delta = (
    cm["average_process_cycles_per_presentation"]
    - bm["average_process_cycles_per_presentation"]
)
assert presentation_delta < 0
assert cycles_delta > 0
assert digest(ROOT / "work/vhgame.txt") == digest(
    EVIDENCE / "accepted/vhgame.txt"
)
assert digest(ROOT / "work/vhgame.exe") == digest(
    EVIDENCE / "accepted/vhgame.exe"
)
result = {
    "schema": 1,
    "task": 203,
    "candidate": "shared-Lino thread priority director 1",
    "source_boundary": "one common tracked shared-Lino closure",
    "native_gameplay_or_renderer_replacement": False,
    "model": json.loads((EVIDENCE / "model.json").read_text(encoding="utf-8")),
    "production": json.loads(
        (EVIDENCE / "production.json").read_text(encoding="utf-8")
    ),
    "host_class": "healthy_host",
    "candidate_a": {
        "startup_seconds": candidate["startup_seconds"],
        "presentation_hz": cm["presentation_hz"],
        "simulation_hz": cm["simulation_hz"],
        "cycles_per_presentation": cm[
            "average_process_cycles_per_presentation"
        ],
        "presentations": candidate["profile"]["presentations"],
        "missed_deadlines": candidate["profile"]["missed_deadlines"],
    },
    "baseline_a": {
        "startup_seconds": baseline["startup_seconds"],
        "presentation_hz": bm["presentation_hz"],
        "simulation_hz": bm["simulation_hz"],
        "cycles_per_presentation": bm[
            "average_process_cycles_per_presentation"
        ],
        "presentations": baseline["profile"]["presentations"],
        "missed_deadlines": baseline["profile"]["missed_deadlines"],
    },
    "ordering_a": {
        "candidate_minus_baseline_presentation_hz": presentation_delta,
        "candidate_minus_baseline_cycles_per_presentation": cycles_delta,
        "presentation_won": False,
        "cycles_per_presentation_won": False,
    },
    "ordering_b": "skipped_after_ordering_a_lost_both_mandatory_metrics",
    "sustained_orbital": "skipped_after_ordering_a_rejection",
    "fidelity": "skipped_after_ordering_a_rejection",
    "disposition": "rejected_after_ordering_a",
    "reason": (
        "Candidate A preserved authentic simulation and reached 59.737 Hz, but "
        "the below-normal Lino application thread lost both mandatory metrics "
        "against the 59.988-Hz Baseline A on the same healthy host."
    ),
    "final_arm": "accepted",
    "accepted_restored_byte_exact": True,
}
(EVIDENCE / "result.json").write_text(
    json.dumps(result, indent=2) + "\n", encoding="utf-8"
)
files = (
    "verify_model.py",
    "verify_production.py",
    "finalize.py",
    "model.json",
    "production.json",
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
    "disposition": result["disposition"],
    "presentation_delta": presentation_delta,
    "cycles_per_presentation_delta": cycles_delta,
    "candidate_simulation_hz": cm["simulation_hz"],
    "final_arm": result["final_arm"],
}, indent=2))
