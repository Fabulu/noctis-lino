from pathlib import Path
import hashlib

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/fixed-f64-helper-calls-20260830"
SOURCE = ROOT / "work/vhgame.txt"
ACCEPTED = EVIDENCE / "accepted/vhgame.txt"
CANDIDATE = EVIDENCE / "candidate/vhgame.txt"

VALUES = (
    (3, "VHG fixed f64 three", "40080000h"),
    (5, "VHG fixed f64 five", "40140000h"),
    (25, "VHG fixed f64 twenty five", "40390000h"),
    (100, "VHG fixed f64 one hundred", "40590000h"),
    (250, "VHG fixed f64 two fifty", "406F4000h"),
    (1000, "VHG fixed f64 one thousand", "408F4000h"),
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
    common_counts = {3: 2, 5: 1, 25: 2, 100: 2, 250: 2, 1000: 1}
    labels = {value: label for value, label, _ in VALUES}
    for value, count in common_counts.items():
        continuation = "[FB0] = [FA0]; [FB1] = [FA1];"
        old = f"[FI] = {value}; => IntToF; {continuation}"
        new = f"[FI] = {value}; => {labels[value]}; {continuation}"
        assert local.count(old) == count, (value, local.count(old), count)
        local = local.replace(old, new)
    ring_continuation = (
        "[FB0] = [VHGlocalringstep0]; [FB1] = [VHGlocalringstep1]; => FMul;")
    old = f"[FI] = 5; => IntToF; {ring_continuation}"
    new = f"[FI] = 5; => {labels[5]}; {ring_continuation}"
    assert local.count(old) == 1
    local = local.replace(old, new)
    helpers = []
    for _, label, high in VALUES:
        helpers.extend((
            f'"{label}"',
            f"\t[FA0] = 0; [FA1] = {high};",
            "\tend;",
            "",
        ))
    helper_text = nl.join(helpers).rstrip() + nl
    candidate_text = prefix + local + suffix
    if not candidate_text.endswith(("\n", "\r")):
        candidate_text += nl
    candidate_text += nl + helper_text
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
