from pathlib import Path
import hashlib

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/dead-fixed-f64-fi-stores-20260830"
SOURCE = ROOT / "work/vhgame.txt"
ACCEPTED = EVIDENCE / "accepted/vhgame.txt"
CANDIDATE = EVIDENCE / "candidate/vhgame.txt"

VALUES = (
    (3, "40080000h", 2),
    (5, "40140000h", 1),
    (25, "40390000h", 2),
    (100, "40590000h", 2),
    (250, "406F4000h", 2),
    (1000, "408F4000h", 1),
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def transform(original):
    text = original.decode("utf-8")
    nl = "\r\n" if "\r\n" in text else "\n"
    start = text.index('"VHG local render"')
    end = text.index('"VHG local far pixel"', start)
    prefix = text[:start]
    local = text[start:end]
    suffix = text[end:]
    continuation = "[FB0] = [FA0]; [FB1] = [FA1];"
    for value, high, count in VALUES:
        old = f"[FI] = {value}; => IntToF; {continuation}"
        new = f"[FB0] = 0; [FB1] = {high};"
        assert local.count(old) == count, (value, local.count(old), count)
        local = local.replace(old, new)
    ring_continuation = (
        "[FB0] = [VHGlocalringstep0]; [FB1] = [VHGlocalringstep1]; => FMul;")
    old = f"[FI] = 5; => IntToF; {ring_continuation}"
    new = f"[FI] = 5; => VHG fixed f64 five; {ring_continuation}"
    assert local.count(old) == 1
    local = local.replace(old, new)
    helper = nl.join((
        '"VHG fixed f64 five"',
        "\t[FA0] = 0; [FA1] = 40140000h;",
        "\tend;",
    )) + nl
    candidate_text = prefix + local + suffix
    if not candidate_text.endswith(("\n", "\r")):
        candidate_text += nl
    candidate_text += nl + helper
    candidate = candidate_text.encode("utf-8")
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
