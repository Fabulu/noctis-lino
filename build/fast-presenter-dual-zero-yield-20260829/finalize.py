from pathlib import Path
import hashlib
import json

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/fast-presenter-dual-zero-yield-20260829"
REPORT = EVIDENCE / "health-screen/capsule/report.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


report = json.loads(REPORT.read_text(encoding="utf-8"))
metrics = report["metrics"]
assert report["startup_seconds"] > 8.0
assert metrics["presentation_hz"] < 59.7
assert metrics["simulation_hz"] >= 18.206
assert digest(ROOT / "work/vhgame.txt") == digest(EVIDENCE / "accepted/vhgame.txt")
assert digest(ROOT / "work/vhgame.exe") == digest(EVIDENCE / "accepted/vhgame.exe")
result = {
    "schema": 1,
    "task": 205,
    "candidate": "two consecutive post-publication Sleep(0) yields",
    "source_boundary": "one common tracked shared-Lino closure",
    "native_gameplay_or_renderer_replacement": False,
    "model": json.loads((EVIDENCE / "model.json").read_text(encoding="utf-8")),
    "health_screen": {
        "startup_seconds": report["startup_seconds"],
        "presentation_hz": metrics["presentation_hz"],
        "simulation_hz": metrics["simulation_hz"],
        "presentations": report["profile"]["presentations"],
        "missed_deadlines": report["profile"]["missed_deadlines"],
        "cycles_per_presentation": metrics[
            "average_process_cycles_per_presentation"
        ],
        "status": "depressed_host",
    },
    "sustained_orbital": "deferred_after_depressed_health_screen",
    "abba": "deferred_after_depressed_health_screen",
    "fidelity": "deferred_after_depressed_health_screen",
    "disposition": "deferred_without_candidate_conclusion",
    "reason": (
        "the candidate launched with an 8.6699-second startup and a 52.5035-Hz "
        "health screen immediately after an independently depressed production "
        "control; the host state cannot admit a candidate conclusion"
    ),
    "final_arm": "accepted",
    "accepted_restored_byte_exact": True,
}
(EVIDENCE / "result.json").write_text(
    json.dumps(result, indent=2) + "\n", encoding="utf-8"
)
files = (
    "verify_model.py",
    "finalize.py",
    "model.json",
    "accepted/vhgame.txt",
    "accepted/vhgame.exe",
    "accepted/compiler114m.exe",
    "accepted/i386m.bin",
    "candidate/vhgame.txt",
    "candidate/vhgame.exe",
    "health-screen/capsule/report.json",
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
    "startup_seconds": report["startup_seconds"],
    "presentation_hz": metrics["presentation_hz"],
    "simulation_hz": metrics["simulation_hz"],
    "final_arm": result["final_arm"],
}, indent=2))
