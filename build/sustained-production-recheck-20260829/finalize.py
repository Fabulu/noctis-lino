from pathlib import Path
import hashlib
import json

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/sustained-production-recheck-20260829"
PRE_HEALTH = ROOT / (
    "build/lino-balanced-thread-priority-20260829/"
    "baseline-a/capsule/report.json"
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


orbital = json.loads((EVIDENCE / "orbital/report.json").read_text(encoding="utf-8"))
post = json.loads(
    (EVIDENCE / "post-health/capsule/report.json").read_text(encoding="utf-8")
)
pre = json.loads(PRE_HEALTH.read_text(encoding="utf-8"))
assert orbital["provenance"]["executable_sha256"] == (
    "81900287fa9e19291a27667b0e23d5c0c6324e86e8b9d8da0ff82a65cc302823"
)
assert post["provenance"]["executable_sha256"] == orbital["provenance"][
    "executable_sha256"
]
assert pre["metrics"]["presentation_hz"] >= 59.9
assert post["metrics"]["presentation_hz"] < 59.7
assert orbital["metrics"]["simulation_hz"] >= 18.206
result = {
    "schema": 1,
    "task": 204,
    "candidate": "unchanged accepted production sustained recheck",
    "source_boundary": "one common tracked shared-Lino closure",
    "executable_sha256": orbital["provenance"]["executable_sha256"],
    "pre_run_health_reference": {
        "path": (
            "build/lino-balanced-thread-priority-20260829/"
            "baseline-a/capsule/report.json"
        ),
        "startup_seconds": pre["startup_seconds"],
        "presentation_hz": pre["metrics"]["presentation_hz"],
        "simulation_hz": pre["metrics"]["simulation_hz"],
        "cycles_per_presentation": pre["metrics"][
            "average_process_cycles_per_presentation"
        ],
    },
    "orbital_60_seconds": {
        "startup_seconds": orbital["startup_seconds"],
        "presentation_hz": orbital["metrics"]["presentation_hz"],
        "simulation_hz": orbital["metrics"]["simulation_hz"],
        "presentations": orbital["profile"]["presentations"],
        "missed_deadlines": orbital["profile"]["missed_deadlines"],
        "maximum_lateness_ms": orbital["metrics"]["maximum_lateness_ms"],
        "cycles_per_presentation": orbital["metrics"][
            "average_process_cycles_per_presentation"
        ],
        "average_space_ms": orbital["metrics"]["average_space_ms"],
    },
    "post_run_health": {
        "startup_seconds": post["startup_seconds"],
        "presentation_hz": post["metrics"]["presentation_hz"],
        "simulation_hz": post["metrics"]["simulation_hz"],
        "cycles_per_presentation": post["metrics"][
            "average_process_cycles_per_presentation"
        ],
    },
    "disposition": "depressed_host_no_acceptance_conclusion",
    "reason": (
        "The accepted baseline was at 59.988 Hz immediately before the minute, "
        "but the orbital run collapsed to 28.438 Hz and the immediate capsule "
        "control remained depressed at 56.080 Hz. The run preserves simulation "
        "but cannot replace healthy sustained evidence."
    ),
    "production_changed": False,
}
(EVIDENCE / "result.json").write_text(
    json.dumps(result, indent=2) + "\n", encoding="utf-8"
)
files = (
    "finalize.py",
    "orbital/report.json",
    "post-health/capsule/report.json",
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
    "orbital_presentation_hz": orbital["metrics"]["presentation_hz"],
    "orbital_simulation_hz": orbital["metrics"]["simulation_hz"],
    "post_health_presentation_hz": post["metrics"]["presentation_hz"],
}, indent=2))
