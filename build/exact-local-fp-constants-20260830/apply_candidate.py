from pathlib import Path
import hashlib

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/exact-local-fp-constants-20260830"
SOURCE = ROOT / "work/vhgame.txt"
ACCEPTED = EVIDENCE / "accepted/vhgame.txt"
CANDIDATE = EVIDENCE / "candidate/vhgame.txt"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def transform(original):
    text = original.decode("utf-8")
    start = text.index('"VHG local render"')
    end = text.index('"VHG local far pixel"', start)
    prefix = text[:start]
    local = text[start:end]
    suffix = text[end:]
    replacements = (
        (3, "40080000h", "[FB0] = [FA0]; [FB1] = [FA1];", 2),
        (250, "406F4000h", "[FB0] = [FA0]; [FB1] = [FA1];", 2),
        (100, "40590000h", "[FB0] = [FA0]; [FB1] = [FA1];", 2),
        (25, "40390000h", "[FB0] = [FA0]; [FB1] = [FA1];", 2),
        (5, "40140000h", "[FB0] = [FA0]; [FB1] = [FA1];", 1),
        (1000, "408F4000h", "[FB0] = [FA0]; [FB1] = [FA1];", 1),
        (
            5,
            "40140000h",
            "[FB0] = [VHGlocalringstep0]; [FB1] = [VHGlocalringstep1]; => FMul;",
            1,
        ),
    )
    for value, high, continuation, count in replacements:
        old = f"[FI] = {value}; => IntToF; {continuation}"
        new = f"[FI] = {value}; [FA0] = 0; [FA1] = {high}; {continuation}"
        assert local.count(old) == count, (value, continuation, local.count(old), count)
        local = local.replace(old, new)
    candidate = (prefix + local + suffix).encode("utf-8")
    assert candidate != original
    return candidate


if __name__ == "__main__":
    accepted = ACCEPTED.read_bytes()
    assert digest(SOURCE) == digest(ACCEPTED)
    assert digest(ACCEPTED) == (
        "f1af20ebd55b80e3a1439b0e30f1bb4e0bdcc8e00b7aced1a7b34d7395d3dc25")
    candidate = transform(accepted)
    CANDIDATE.write_bytes(candidate)
    SOURCE.write_bytes(candidate)
    print(f"accepted_source_sha256={digest(ACCEPTED)}")
    print(f"candidate_source_sha256={digest(CANDIDATE)}")
