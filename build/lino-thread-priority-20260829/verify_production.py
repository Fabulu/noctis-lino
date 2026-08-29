from pathlib import Path
import hashlib
import json

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/lino-thread-priority-20260829"
ACCEPTED = EVIDENCE / "accepted/vhgame.exe"
CANDIDATE = EVIDENCE / "candidate/vhgame.exe"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


accepted = ACCEPTED.read_bytes()
candidate = CANDIDATE.read_bytes()
assert len(accepted) == len(candidate) == 645966
differences = [
    offset for offset, pair in enumerate(zip(accepted, candidate))
    if pair[0] != pair[1]
]
assert differences == [0x3C48]
assert accepted[0x3C48] == 2
assert candidate[0x3C48] == 3
# The byte is the application-code priority director field in the copied
# LNLMInit paragraph. No runtime code, Lino data/code, stock asset, CPU-pack,
# renderer, gameplay, or timing-loop byte changed.
assert accepted[0x3C00:0x3C08] == candidate[0x3C00:0x3C08] == b"LNLMInit"
assert accepted[:0x3C48] == candidate[:0x3C48]
assert accepted[0x3C49:] == candidate[0x3C49:]

result = {
    "schema": 1,
    "task": 202,
    "accepted_executable_sha256": digest(ACCEPTED),
    "candidate_executable_sha256": digest(CANDIDATE),
    "executable_size": len(candidate),
    "difference_offsets": [hex(offset) for offset in differences],
    "accepted_priority_director": accepted[0x3C48],
    "candidate_priority_director": candidate[0x3C48],
    "runtime_code_unchanged": True,
    "generated_lino_data_and_code_unchanged": True,
    "stock_assets_unchanged": True,
    "status": "pass",
}
(EVIDENCE / "production.json").write_text(
    json.dumps(result, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps(result, indent=2))
