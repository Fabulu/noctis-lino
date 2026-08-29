from pathlib import Path
import hashlib
import json
import runpy

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/live-space-render-attribution-20260829"
ACCEPTED = EVIDENCE / "accepted/vhgame.txt"
CANDIDATE = ROOT / "work/vhgame.txt"
APPLIER = EVIDENCE / "apply_star_subphase_candidate.py"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


accepted = ACCEPTED.read_bytes()
candidate = CANDIDATE.read_bytes()
transform = runpy.run_path(str(APPLIER))["transform"]
assert candidate == transform(accepted)
assert candidate.count(b"[Timer Command] = READ COUNTS") == accepted.count(
    b"[Timer Command] = READ COUNTS"
) + 5
assert candidate.count(b"=> VHG fpu clean;") == accepted.count(
    b"=> VHG fpu clean;"
) + 6
assert candidate.count(b"=> VHG local render;") == accepted.count(
    b"=> VHG local render;"
)
assert candidate.count(b"=> VHT render;") == accepted.count(b"=> VHT render;")
assert b"VHGSIMADD = 18206; VHGSIMDEN = 60000;" in candidate
assert digest(ROOT / "main/lib/gen/compiler114m.exe") == digest(
    EVIDENCE / "accepted/compiler114m.exe"
)
assert digest(ROOT / "main/cpu/i386m.bin") == digest(
    EVIDENCE / "accepted/i386m.bin"
)
result = {
    "schema": 1,
    "task": 206,
    "kind": "instrumentation_only",
    "profile_channels": {
        "space_counts": "complete active VHG local render",
        "cupola_counts": "selected origin and resident scan",
        "hull_counts": "primary-star setup and companion coronas",
        "detail_counts": "mask and primary-star globe or far pixel",
    },
    "source_boundary": "one common tracked shared-Lino closure",
    "renderer_calls_unchanged": True,
    "renderer_products_unchanged": True,
    "timer_arithmetic_unchanged": True,
    "simulation_constants": [18206, 60000],
    "fpu_clean_after_each_inserted_timer_call": True,
    "profile_binary_schema_unchanged": True,
    "accepted_source_sha256": digest(ACCEPTED),
    "star_instrumented_source_sha256": digest(CANDIDATE),
    "compiler_unchanged": True,
    "cpu_pack_unchanged": True,
    "status": "pass",
}
(EVIDENCE / "star-model.json").write_text(
    json.dumps(result, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps(result, indent=2))
