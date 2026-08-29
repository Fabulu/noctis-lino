from pathlib import Path
import hashlib
import json

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/live-space-render-attribution-20260829"
ACCEPTED = EVIDENCE / "accepted/vhgame.txt"
CANDIDATE = ROOT / "work/vhgame.txt"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


accepted = ACCEPTED.read_bytes()
candidate = CANDIDATE.read_bytes()
nl = b"\r\n" if b"\r\n" in accepted else b"\n"
old_call = nl.join((
    b"\tA = [VHGlocalactive]; ? A != 0 -> VHG close star rendered;",
    b"\t=> VHT render;",
    b'    "VHG close star rendered"',
))
new_call = nl.join((
    b"\tA = [VHGlocalactive]; ? A != 0 -> VHG close star rendered;",
    b"\t( Attribution-only counter: isolate the exact live VHT render call. )",
    b"\t[Timer Command] = READ COUNTS; isocall; [VHGprofpart] = [Counts];",
    b"\t=> VHG fpu clean;",
    b"\t=> VHT render;",
    b"\t[Timer Command] = READ COUNTS; isocall; A = [Counts]; A - [VHGprofpart];",
    b"\tA + [VHGprofspace]; [VHGprofspace] = A;",
    b"\t=> VHG fpu clean;",
    b'    "VHG close star rendered"',
))
old_total = nl.join((
    b"\t=> VHG rescue render;",
    b"\t[Timer Command] = READ COUNTS; isocall; A = [Counts]; A - [VHGprofpart];",
    b"\tA + [VHGprofspace]; [VHGprofspace] = A;",
    b"\t[Timer Command] = READ COUNTS; isocall; [VHGprofpart] = [Counts];",
))
new_total = nl.join((
    b"\t=> VHG rescue render;",
    b"\t( VHGprofspace already contains only VHT render; begin the cupola counter here. )",
    b"\t[Timer Command] = READ COUNTS; isocall; [VHGprofpart] = [Counts];",
))
assert accepted.count(old_call) == 1
assert accepted.count(old_total) == 1
assert candidate.count(new_call) == 1
assert candidate.count(new_total) == 1
restored = candidate.replace(new_call, old_call, 1).replace(new_total, old_total, 1)
assert restored == accepted
assert candidate.count(b"[Timer Command] = READ COUNTS") == accepted.count(
    b"[Timer Command] = READ COUNTS"
) + 1
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
    "counter_semantics": (
        "profile space_counts contains VHT render plus the required pre-call "
        "profiling-boundary FPU reset"
    ),
    "source_boundary": "one common tracked shared-Lino closure",
    "renderer_calls_unchanged": True,
    "renderer_products_unchanged": True,
    "timer_arithmetic_unchanged": True,
    "simulation_constants": [18206, 60000],
    "fpu_clean_after_each_inserted_timer_call": True,
    "profile_schema_unchanged": True,
    "accepted_source_sha256": digest(ACCEPTED),
    "instrumented_source_sha256": digest(CANDIDATE),
    "compiler_unchanged": True,
    "cpu_pack_unchanged": True,
    "status": "pass",
}
(EVIDENCE / "model.json").write_text(
    json.dumps(result, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps(result, indent=2))
