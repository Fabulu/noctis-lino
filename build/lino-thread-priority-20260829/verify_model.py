from pathlib import Path
import hashlib
import json
import struct

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/lino-thread-priority-20260829"
ACCEPTED = EVIDENCE / "accepted"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


accepted = (ACCEPTED / "vhgame.txt").read_text(encoding="utf-8")
candidate = (ROOT / "work/vhgame.txt").read_text(encoding="utf-8")
director = "\tthread priority = 3;\n"
assert candidate.count(director) == 1
assert candidate.replace(director, "", 1) == accepted
assert "VHGSIMADD = 18206; VHGSIMDEN = 60000;" in candidate
assert digest(ROOT / "main/lib/gen/compiler114m.exe") == digest(
    ACCEPTED / "compiler114m.exe"
)
assert digest(ROOT / "main/cpu/i386m.bin") == digest(ACCEPTED / "i386m.bin")

# Win32 RTM's five valid Lino priority-director indices map directly to
# THREAD_PRIORITY_LOWEST..HIGHEST. Index 3 is ABOVE_NORMAL (+1).
sys_pack = (ROOT / "main/sys/win32.bin").read_bytes()
variant_count = struct.unpack_from("<I", sys_pack, 0)[0]
header_size = 4 * (1 + 2 * variant_count)
offset = struct.unpack_from("<I", sys_pack, 4 + 4 * 2)[0]
size = struct.unpack_from("<I", sys_pack, 4 + 4 * variant_count + 4 * 2)[0]
variant = sys_pack[header_size + offset:header_size + offset + size]
priority_table = struct.unpack_from("<5i", variant, 0x3C95)
assert priority_table == (-2, -1, 0, 1, 2)
assert priority_table[3] == 1

result = {
    "schema": 1,
    "task": 202,
    "candidate": "shared-Lino thread priority director 3",
    "source_boundary": "one common tracked shared-Lino closure",
    "native_gameplay_or_renderer_replacement": False,
    "accepted_source_sha256": digest(ACCEPTED / "vhgame.txt"),
    "candidate_source_sha256": digest(ROOT / "work/vhgame.txt"),
    "compiler_unchanged": True,
    "cpu_pack_unchanged": True,
    "win32_priority_table": list(priority_table),
    "director_index": 3,
    "windows_thread_priority_value": priority_table[3],
    "windows_thread_priority_name": "THREAD_PRIORITY_ABOVE_NORMAL",
    "simulation_constants": [18206, 60000],
    "status": "pass",
}
(EVIDENCE / "model.json").write_text(
    json.dumps(result, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps(result, indent=2))
