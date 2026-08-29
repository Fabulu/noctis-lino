from pathlib import Path
import hashlib
import json

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/fast-presenter-dual-zero-yield-20260829"
ACCEPTED = EVIDENCE / "accepted"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


accepted = (ACCEPTED / "vhgame.txt").read_text(encoding="utf-8")
candidate = (ROOT / "work/vhgame.txt").read_text(encoding="utf-8")
old = '    "VHG timing fast wait"\n\t=> TK wait;'
new = (
    '    "VHG timing fast wait"\n'
    "\t( Yield two scheduler opportunities after publication, then retain the exact deadline spin. )\n"
    "\t[Sleep Timeout] = 0; [Process Command] = SLEEP; isocall; isocall;\n"
    "\t=> TK wait;"
)
assert new in candidate
assert candidate.replace(new, old, 1) == accepted
assert candidate.count("[Sleep Timeout] = 0; [Process Command] = SLEEP; isocall; isocall;") == 1
assert "VHGSIMADD = 18206; VHGSIMDEN = 60000;" in candidate
assert "A = [TKlate]; ? A = 0 -> VHG timing fast wait;" in candidate
assert "A = E; ? A < [TKbase] -> VHG timing done;" in candidate
assert digest(ROOT / "main/lib/gen/compiler114m.exe") == digest(
    ACCEPTED / "compiler114m.exe"
)
assert digest(ROOT / "main/cpu/i386m.bin") == digest(ACCEPTED / "i386m.bin")
result = {
    "schema": 1,
    "task": 205,
    "candidate": "two consecutive post-publication Sleep(0) yields",
    "source_boundary": "one common tracked shared-Lino closure",
    "native_gameplay_or_renderer_replacement": False,
    "accepted_source_sha256": digest(ACCEPTED / "vhgame.txt"),
    "candidate_source_sha256": digest(ROOT / "work/vhgame.txt"),
    "zero_timeout": True,
    "scheduler_yields_per_fast_presentation": 2,
    "deadline_wait_retained": True,
    "deadline_arithmetic_unchanged": True,
    "simulation_constants": [18206, 60000],
    "compiler_unchanged": True,
    "cpu_pack_unchanged": True,
    "status": "pass",
}
(EVIDENCE / "model.json").write_text(
    json.dumps(result, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps(result, indent=2))
