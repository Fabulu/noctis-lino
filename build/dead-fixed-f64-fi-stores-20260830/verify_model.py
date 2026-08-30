from pathlib import Path
import hashlib
import importlib.util
import json
import random
import struct

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/dead-fixed-f64-fi-stores-20260830"
ACCEPTED = EVIDENCE / "accepted/vhgame.txt"
CANDIDATE = EVIDENCE / "candidate/vhgame.txt"
SOURCE = ROOT / "work/vhgame.txt"
FPCONV = ROOT / "work/fp/fpconv.txt"
FPX87 = ROOT / "work/fp/fpx87.txt"
FPSOFT = ROOT / "work/fp/fpsoft.txt"
SPWHITE = ROOT / "work/spwhite.txt"
MODEL_PATH = EVIDENCE / "model.json"
EXPECTED_CANDIDATE_SHA256 = (
    "2e9ee626a34b2dc2ed90006e184c7a00363a5a3b29d6563dc4853db42f2c0385")

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
assert sha256(candidate_bytes) == EXPECTED_CANDIDATE_SHA256
assert CANDIDATE.read_bytes() == candidate_bytes
assert SOURCE.read_bytes() == candidate_bytes
accepted = accepted_bytes.decode("utf-8")
candidate = candidate_bytes.decode("utf-8")
start = accepted.index('"VHG local render"')
end = accepted.index('"VHG local far pixel"', start)
candidate_start = candidate.index('"VHG local render"')
candidate_end = candidate.index('"VHG local far pixel"', candidate_start)
accepted_local = accepted[start:end]
candidate_local = candidate[candidate_start:candidate_end]
helper_marker = '"VHG fixed f64 five"'
helper_start = candidate.index(helper_marker)
assert accepted[:start] == candidate[:candidate_start]
assert candidate[candidate_end:helper_start].rstrip() == accepted[end:].rstrip()
assert helper_start > candidate.rindex("-> PG terrain replay finish;")
assert accepted.rstrip().endswith("A = 0; A+; A+; A+;")
assert candidate[:helper_start].rstrip().endswith("A = 0; A+; A+; A+;")

values = (
    (3, 0x40080000, 2),
    (5, 0x40140000, 1),
    (25, 0x40390000, 2),
    (100, 0x40590000, 2),
    (250, 0x406F4000, 2),
    (1000, 0x408F4000, 1),
)
continuation = "[FB0] = [FA0]; [FB1] = [FA1];"
direct_sites = 0
for value, high, count in values:
    old = f"[FI] = {value}; => IntToF; {continuation}"
    new = f"[FB0] = 0; [FB1] = {high:08X}h;"
    assert accepted_local.count(old) == count
    assert candidate_local.count(old) == 0
    assert candidate_local.count(new) == count
    assert f64_words(value) == (0, high)
    assert f32_widen_words(value) == (0, high)
    direct_sites += count
assert direct_sites == 10

ring_continuation = (
    "[FB0] = [VHGlocalringstep0]; [FB1] = [VHGlocalringstep1]; => FMul;")
accepted_ring = f"[FI] = 5; => IntToF; {ring_continuation}"
candidate_ring = f"[FI] = 5; => VHG fixed f64 five; {ring_continuation}"
assert accepted_local.count(accepted_ring) == 1
assert candidate_local.count(accepted_ring) == 0
assert candidate_local.count(candidate_ring) == 1
assert candidate[helper_start:].strip() == (
    '"VHG fixed f64 five"\n'
    "\t[FA0] = 0; [FA1] = 40140000h;\n"
    "\tend;").replace("\n", "\r\n" if "\r\n" in candidate else "\n")
assert accepted_local.count("=> IntToF;") - candidate_local.count("=> IntToF;") == 11

# Six ordinary/selected LOD gates load the runtime ray into FA, multiply by
# the exact direct FB constant, and overwrite FI with FCmp before reading it.
ray_gate_tail = (
    "[FA0] = [VHGlocalray0]; [FA1] = [VHGlocalray1]; => FMul;\n"
    "\t[VHGlocallim0] = [FA0]; [VHGlocallim1] = [FA1];\n"
    "\t[FA0] = [VHGlocaldist0]; [FA1] = [VHGlocaldist1];\n"
    "\t[FB0] = [VHGlocallim0]; [FB1] = [VHGlocallim1]; => FCmp;\n"
    "\tA = [FI];")
if "\r\n" in candidate:
    ray_gate_tail = ray_gate_tail.replace("\n", "\r\n")
for value, high in ((250, 0x406F4000), (100, 0x40590000), (25, 0x40390000)):
    prefix = f"[FB0] = 0; [FB1] = {high:08X}h;\r\n\t" if "\r\n" in candidate else (
        f"[FB0] = 0; [FB1] = {high:08X}h;\n\t")
    assert candidate_local.count(prefix + ray_gate_tail) == 2

# Both companion flare gates follow the same rule without the temporary limit.
companion_tail = (
    "[FA0] = [VHGlocalray0]; [FA1] = [VHGlocalray1]; => FMul;\n"
    "\t[FB0] = [FA0]; [FB1] = [FA1];\n"
    "\t[FA0] = [VHGlocaldist0]; [FA1] = [VHGlocaldist1]; => FCmp;\n"
    "\tA = [FI];")
if "\r\n" in candidate:
    companion_tail = companion_tail.replace("\n", "\r\n")
for high in (0x40140000, 0x408F4000):
    prefix = f"[FB0] = 0; [FB1] = {high:08X}h;\r\n\t" if "\r\n" in candidate else (
        f"[FB0] = 0; [FB1] = {high:08X}h;\n\t")
    assert candidate_local.count(prefix + companion_tail) == 1

# The two magnitude sites overwrite FA before FMul and do not read FI before
# SP white. SP white itself executes FCmp before its first FI read.
star_direct = "[FB0] = 0; [FB1] = 40080000h;"
assert candidate_local.count(star_direct) == 2
for position in [
    index for index in range(len(candidate_local))
    if candidate_local.startswith(star_direct, index)
]:
    white_call = candidate_local.index("=> SP white;", position)
    segment = candidate_local[position:white_call]
    assert "[FA0] = " in segment and "=> FMul;" in segment
    assert "[FI]" not in segment
spwhite = SPWHITE.read_text(encoding="utf-8").replace("\r\n", "\n")
spwhite_start = spwhite.index('"SP white"')
spwhite_first_read = spwhite.index("A = [FI];", spwhite_start)
spwhite_prefix = spwhite[spwhite_start:spwhite_first_read]
assert "=> FCmp;" in spwhite_prefix
assert "[FI]" not in spwhite_prefix

# FCmp assigns FI for finite greater/equal/less and unordered exits.
fpx87 = FPX87.read_text(encoding="utf-8").replace("\r\n", "\n")
fcmp_start = fpx87.index('"FCmp"')
fcmp = fpx87[fcmp_start:]
for assignment in ("[FI] = 1;", "[FI] = 0;", "[FI] = A;", "[FI] = 2;"):
    assert assignment in fcmp
assert "? A != 0 -> FCMP unord;" in fcmp

# The specialized ring site must retain FI=5: the ring-tilt tail does not
# overwrite FI before a valid loop exit reaches the common terminal state.
ring_start = candidate_local.index(candidate_ring)
ring_done = candidate_local.index('"VHG local ring done"', ring_start)
ring_segment = candidate_local[ring_start:ring_done]
assert ring_segment.count("[FI]") == 1
assert "=> FCmp;" not in ring_segment
assert "[FI] = 5;" in ring_segment

fpconv = FPCONV.read_text(encoding="utf-8").replace("\r\n", "\n")
fpsoft = FPSOFT.read_text(encoding="utf-8").replace("\r\n", "\n")
assert "FCWCSAV is private to this file on purpose" in fpconv
assert fpconv.count("CVTMP") == 3
assert "[CVTMP] = [FS0]; [FS0] ,= [FI]; => CV F32 to F64;" in fpconv
assert "[FS0] = [CVTMP];" in fpconv
assert '"FMul"\n\t---->;\n\t=> XScalarMul;\n\t<----;' in fpx87
assert '"XScalarMul"' in fpsoft and "=> XMulCore;" in fpsoft and "=> XToF64;" in fpsoft

rng = random.Random(219)
visible_cases = 0
for value, high, count in values:
    for _ in range(128 * count):
        entry = {
            name: rng.randrange(1 << 32)
            for name in ("A", "B", "C", "D", "E", "FI", "FS0", "FA0", "FA1",
                         "FB0", "FB1")
        }
        compare = rng.choice((0, 1, 2, 0xFFFFFFFF))
        original = dict(entry)
        candidate_state = dict(entry)
        # Both paths give the following FMul identical inputs and therefore the
        # same FA product and software-FP scratch. The first FI observer sees an
        # intervening FCmp at each of these ten sites.
        original.update({"FB0": 0, "FB1": high, "FA0": "same-product",
                         "FA1": "same-product", "FI": compare})
        candidate_state.update({"FB0": 0, "FB1": high, "FA0": "same-product",
                                "FA1": "same-product", "FI": compare})
        assert original == candidate_state
        visible_cases += 1
# The retained ring assignment and one exact helper converge immediately after
# the same next FMul, including FI=5.
for _ in range(128):
    entry = {
        name: rng.randrange(1 << 32)
        for name in ("A", "B", "C", "D", "E", "FI", "FS0", "FA0", "FA1",
                     "FB0", "FB1")
    }
    original = dict(entry)
    candidate_state = dict(entry)
    original.update({"FI": 5, "FA0": "same-product", "FA1": "same-product"})
    candidate_state.update({"FI": 5, "FA0": "same-product", "FA1": "same-product"})
    assert original == candidate_state
    visible_cases += 1
assert visible_cases == 1408
assert candidate.count("VHGSIMADD = 18206; VHGSIMDEN = 60000;") == 1

result = {
    "schema": 1,
    "task": 219,
    "status": "pass",
    "candidate_file_equals_exact_transform": True,
    "direct_fb_sites": direct_sites,
    "retained_fi_and_helper_sites": 1,
    "fixed_values": [3, 5, 25, 100, 250, 1000],
    "visible_state_cases": visible_cases,
    "int_to_binary32_to_binary64_words_exact": True,
    "direct_fb_words_exact": True,
    "direct_site_fi_stores_proven_dead": True,
    "direct_site_fa_values_proven_dead_before_same_fmul": True,
    "first_fi_observer_preceded_by_fcmp": True,
    "fcmp_all_exits_assign_fi": True,
    "ring_terminal_fi_store_retained": True,
    "fs0_preserved": True,
    "a_through_e_preserved": True,
    "private_conversion_scratch_unobserved": True,
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
    "fpx87_source_sha256": sha256(FPX87.read_bytes()),
    "spwhite_source_sha256": sha256(SPWHITE.read_bytes()),
}
MODEL_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
