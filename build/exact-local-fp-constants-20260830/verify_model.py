from pathlib import Path
import hashlib
import importlib.util
import json
import random
import struct

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/exact-local-fp-constants-20260830"
ACCEPTED = EVIDENCE / "accepted/vhgame.txt"
CANDIDATE = EVIDENCE / "candidate/vhgame.txt"
SOURCE = ROOT / "work/vhgame.txt"
FPCONV = ROOT / "work/fp/fpconv.txt"
MODEL_PATH = EVIDENCE / "model.json"

spec = importlib.util.spec_from_file_location(
    "apply_candidate", EVIDENCE / "apply_candidate.py")
apply_candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(apply_candidate)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def f64_words(value):
    low, high = struct.unpack("<II", struct.pack("<d", float(value)))
    return low, high


def f32_widen_words(value):
    narrowed = struct.unpack("<f", struct.pack("<f", float(value)))[0]
    return f64_words(narrowed)


accepted_bytes = ACCEPTED.read_bytes()
candidate_bytes = apply_candidate.transform(accepted_bytes)
assert sha256(accepted_bytes) == (
    "f1af20ebd55b80e3a1439b0e30f1bb4e0bdcc8e00b7aced1a7b34d7395d3dc25")
assert sha256(candidate_bytes) == (
    "9b7a659facea409838199124ef2843de9de9b557fdf98ad76c9f1fded4f8721d")
assert CANDIDATE.read_bytes() == candidate_bytes
assert SOURCE.read_bytes() == candidate_bytes
accepted = accepted_bytes.decode("utf-8")
candidate = candidate_bytes.decode("utf-8")
start = accepted.index('"VHG local render"')
end = accepted.index('"VHG local far pixel"', start)
candidate_start = candidate.index('"VHG local render"')
candidate_end = candidate.index('"VHG local far pixel"', candidate_start)
assert accepted[:start] == candidate[:candidate_start]
assert accepted[end:] == candidate[candidate_end:]
accepted_local = accepted[start:end]
candidate_local = candidate[candidate_start:candidate_end]

sites = (
    (3, 0x40080000, "[FB0] = [FA0]; [FB1] = [FA1];", 2),
    (250, 0x406F4000, "[FB0] = [FA0]; [FB1] = [FA1];", 2),
    (100, 0x40590000, "[FB0] = [FA0]; [FB1] = [FA1];", 2),
    (25, 0x40390000, "[FB0] = [FA0]; [FB1] = [FA1];", 2),
    (5, 0x40140000, "[FB0] = [FA0]; [FB1] = [FA1];", 1),
    (1000, 0x408F4000, "[FB0] = [FA0]; [FB1] = [FA1];", 1),
    (
        5,
        0x40140000,
        "[FB0] = [VHGlocalringstep0]; [FB1] = [VHGlocalringstep1]; => FMul;",
        1,
    ),
)
site_count = 0
for value, high, continuation, count in sites:
    old = f"[FI] = {value}; => IntToF; {continuation}"
    new = f"[FI] = {value}; [FA0] = 0; [FA1] = {high:08X}h; {continuation}"
    assert accepted_local.count(old) == count
    assert candidate_local.count(old) == 0
    assert candidate_local.count(new) == count
    assert f64_words(value) == (0, high)
    assert f32_widen_words(value) == (0, high)
    site_count += count
assert site_count == 11
assert accepted_local.count("=> IntToF;") - candidate_local.count("=> IntToF;") == 11
assert candidate.count("VHGSIMADD = 18206; VHGSIMDEN = 60000;") == 1

# IntToF's small-integer route saves/restores FS0 and its wrapper saves/restores
# A-E. Every replacement retains the explicit FI assignment and writes the exact
# widened binary32 result to FA. The only omitted state is conversion-private CV
# scratch, declared private in fpconv and absent from every other work source.
fpconv = FPCONV.read_text(encoding="utf-8")
assert "FCWCSAV is private to this file on purpose" in fpconv
assert "CVMODE = 0; CVTMP = 0;" in fpconv
assert fpconv.count("CVTMP") == 3
assert "[CVTMP] = [FS0]; [FS0] ,= [FI]; => CV F32 to F64;" in fpconv
assert "[FS0] = [CVTMP];" in fpconv
assert '"IntToF"\n\t---->;\n\t=> IntToF body;\n\t<----;' in fpconv.replace("\r\n", "\n")

rng = random.Random(217)
visible_cases = 0
for value, high, continuation, count in sites:
    for _ in range(128):
        entry = {
            "A": rng.randrange(1 << 32),
            "B": rng.randrange(1 << 32),
            "C": rng.randrange(1 << 32),
            "D": rng.randrange(1 << 32),
            "E": rng.randrange(1 << 32),
            "FI": rng.randrange(1 << 32),
            "FS0": rng.randrange(1 << 32),
            "FB": (rng.randrange(1 << 32), rng.randrange(1 << 32)),
        }
        original = dict(entry)
        original.update({"FI": value, "FA": f32_widen_words(value)})
        candidate_state = dict(entry)
        candidate_state.update({"FI": value, "FA": (0, high)})
        assert original == candidate_state
        visible_cases += 1

# Every replacement feeds the same next multiply before a control transfer, so
# IntToF's private internal branch flags cannot reach renderer control flow.
for line in candidate_local.splitlines():
    if "[FI] = " in line and "[FA0] = 0; [FA1] = " in line:
        assert "[FB0] = " in line
assert candidate_local.count("[FA1] = 406F4000h;") == 2
assert candidate_local.count("[FA1] = 40590000h;") == 2
assert candidate_local.count("[FA1] = 40390000h;") == 2
assert candidate_local.count("[FA1] = 40080000h;") == 2
assert candidate_local.count("[FA1] = 40140000h;") == 2
assert candidate_local.count("[FA1] = 408F4000h;") == 1

result = {
    "schema": 1,
    "task": 217,
    "status": "pass",
    "candidate_file_equals_exact_transform": True,
    "replacement_sites": site_count,
    "fixed_values": [3, 5, 25, 100, 250, 1000],
    "visible_state_cases": visible_cases,
    "int_to_binary32_to_binary64_words_exact": True,
    "fi_assignments_retained": True,
    "fa_words_exact": True,
    "fs0_preserved": True,
    "a_through_e_preserved_by_original_wrapper_and_candidate": True,
    "private_conversion_scratch_unobserved": True,
    "next_multiply_and_renderer_control_flow_exact": True,
    "source_changes_confined_to_local_renderer": True,
    "simulation_constants": [18206, 60000],
    "source_boundary": "one common tracked shared-Lino closure",
    "raw_target_machine_blocks_added": False,
    "compiler_unchanged": True,
    "cpu_pack_unchanged": True,
    "accepted_source_sha256": sha256(accepted_bytes),
    "candidate_source_sha256": sha256(candidate_bytes),
    "fpconv_source_sha256": sha256(FPCONV.read_bytes()),
}
MODEL_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
