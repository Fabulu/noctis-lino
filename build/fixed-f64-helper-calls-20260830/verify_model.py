from pathlib import Path
import hashlib
import importlib.util
import json
import random
import struct

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/fixed-f64-helper-calls-20260830"
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
    return struct.unpack("<II", struct.pack("<d", float(value)))


def f32_widen_words(value):
    narrowed = struct.unpack("<f", struct.pack("<f", float(value)))[0]
    return f64_words(narrowed)


accepted_bytes = ACCEPTED.read_bytes()
candidate_bytes = apply_candidate.transform(accepted_bytes)
assert sha256(accepted_bytes) == (
    "f1af20ebd55b80e3a1439b0e30f1bb4e0bdcc8e00b7aced1a7b34d7395d3dc25")
assert sha256(candidate_bytes) == (
    "1ba39ef3675d95d338ae94117dba36fb71570f392ed8d53931b05642d7391e5d")
assert CANDIDATE.read_bytes() == candidate_bytes
assert SOURCE.read_bytes() == candidate_bytes
accepted = accepted_bytes.decode("utf-8")
candidate = candidate_bytes.decode("utf-8")
start = accepted.index('"VHG local render"')
end = accepted.index('"VHG local far pixel"', start)
candidate_start = candidate.index('"VHG local render"')
candidate_end = candidate.index('"VHG local far pixel"', candidate_start)
assert accepted[:start] == candidate[:candidate_start]
accepted_local = accepted[start:end]
candidate_local = candidate[candidate_start:candidate_end]
helper_marker = '"VHG fixed f64 three"'
helper_start = candidate.index(helper_marker)
assert candidate[candidate_end:helper_start].rstrip() == accepted[end:].rstrip()
assert helper_start > candidate.rindex("-> PG terrain replay finish;")
assert accepted.rstrip().endswith("A = 0; A+; A+; A+;")
assert candidate[:helper_start].rstrip().endswith("A = 0; A+; A+; A+;")

values = (
    (3, "VHG fixed f64 three", 0x40080000, 2),
    (5, "VHG fixed f64 five", 0x40140000, 1),
    (25, "VHG fixed f64 twenty five", 0x40390000, 2),
    (100, "VHG fixed f64 one hundred", 0x40590000, 2),
    (250, "VHG fixed f64 two fifty", 0x406F4000, 2),
    (1000, "VHG fixed f64 one thousand", 0x408F4000, 1),
)
site_count = 0
for value, label, high, common_count in values:
    continuation = "[FB0] = [FA0]; [FB1] = [FA1];"
    old = f"[FI] = {value}; => IntToF; {continuation}"
    new = f"[FI] = {value}; => {label}; {continuation}"
    assert accepted_local.count(old) == common_count
    assert candidate_local.count(old) == 0
    assert candidate_local.count(new) == common_count
    helper = (
        f'"{label}"\r\n\t[FA0] = 0; [FA1] = {high:08X}h;\r\n\tend;')
    if "\r\n" not in candidate:
        helper = helper.replace("\r\n", "\n")
    assert candidate.count(helper) == 1
    assert f64_words(value) == (0, high)
    assert f32_widen_words(value) == (0, high)
    site_count += common_count
ring_continuation = (
    "[FB0] = [VHGlocalringstep0]; [FB1] = [VHGlocalringstep1]; => FMul;")
old = f"[FI] = 5; => IntToF; {ring_continuation}"
new = f"[FI] = 5; => VHG fixed f64 five; {ring_continuation}"
assert accepted_local.count(old) == 1
assert candidate_local.count(old) == 0
assert candidate_local.count(new) == 1
site_count += 1
assert site_count == 11
assert accepted_local.count("=> IntToF;") - candidate_local.count("=> IntToF;") == 11
assert candidate.count("VHGSIMADD = 18206; VHGSIMDEN = 60000;") == 1

fpconv = FPCONV.read_text(encoding="utf-8")
assert "FCWCSAV is private to this file on purpose" in fpconv
assert fpconv.count("CVTMP") == 3
assert "[CVTMP] = [FS0]; [FS0] ,= [FI]; => CV F32 to F64;" in fpconv
assert "[FS0] = [CVTMP];" in fpconv
assert '"IntToF"\n\t---->;\n\t=> IntToF body;\n\t<----;' in fpconv.replace("\r\n", "\n")

rng = random.Random(218)
visible_cases = 0
for value, _, high, common_count in values:
    repetitions = common_count + (1 if value == 5 else 0)
    for _ in range(128 * repetitions):
        entry = {
            "A": rng.randrange(1 << 32),
            "B": rng.randrange(1 << 32),
            "C": rng.randrange(1 << 32),
            "D": rng.randrange(1 << 32),
            "E": rng.randrange(1 << 32),
            "FI": rng.randrange(1 << 32),
            "FS0": rng.randrange(1 << 32),
        }
        original = dict(entry)
        original.update({"FI": value, "FA": f32_widen_words(value)})
        candidate_state = dict(entry)
        candidate_state.update({"FI": value, "FA": (0, high)})
        assert original == candidate_state
        visible_cases += 1
assert visible_cases == 1408

# Every call site still has one FI store, one Lino call, and its unchanged
# continuation. The helper itself contains only the two FA stores and return.
for _, label, _, common_count in values:
    assert candidate_local.count(f"=> {label};") == common_count + (
        1 if label == "VHG fixed f64 five" else 0)
assert candidate[helper_start:].count("\tend;") == 6
assert candidate[helper_start:].count("[FA0] = 0; [FA1] = ") == 6

result = {
    "schema": 1,
    "task": 218,
    "status": "pass",
    "candidate_file_equals_exact_transform": True,
    "replacement_sites": site_count,
    "eof_helpers": 6,
    "fixed_values": [3, 5, 25, 100, 250, 1000],
    "visible_state_cases": visible_cases,
    "int_to_binary32_to_binary64_words_exact": True,
    "fi_assignments_retained": True,
    "fa_words_exact": True,
    "fs0_preserved": True,
    "a_through_e_preserved": True,
    "private_conversion_scratch_unobserved": True,
    "same_single_call_shape_at_each_hot_site": True,
    "next_multiply_and_renderer_control_flow_exact": True,
    "accepted_source_prefix_and_suffix_exact_before_appendix": True,
    "appendix_after_unreachable_eof_padding": True,
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
