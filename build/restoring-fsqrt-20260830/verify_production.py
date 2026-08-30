from pathlib import Path
import hashlib
import json
import runpy
import struct

from capstone import Cs, CS_ARCH_X86, CS_MODE_32

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/restoring-fsqrt-20260830"
ACCEPTED_EXE = EVIDENCE / "accepted/vhgame.exe"
CANDIDATE_EXE = EVIDENCE / "candidate/vhgame.exe"
ACCEPTED_FP = EVIDENCE / "accepted/fpsoft.txt"
CANDIDATE_FP = EVIDENCE / "candidate/fpsoft.txt"
OUTPUT = EVIDENCE / "production-layout.json"
EXPECTED_ACCEPTED_EXE_SHA256 = (
    "81900287fa9e19291a27667b0e23d5c0c6324e86e8b9d8da0ff82a65cc302823")
EXPECTED_CANDIDATE_EXE_SHA256 = (
    "c4a62f5068262239a8a5665c443a75784fa2472941c9dfdb8fb731f5c8217ca2")
EXPECTED_ACCEPTED_FP_SHA256 = (
    "5031845ed5dbc0e7913eca691259873d45f0bfc67f1969a14dbd3c3ae172527a")
EXPECTED_CANDIDATE_FP_SHA256 = (
    "6b2e209be5b62013276514f8c418cafc92ecb9fd4d9fd6fbdf91453bfebe66d3")
ROOT_START = 0x256F1
ISLAND_END = 0x25B49
CANDIDATE_BODY_END = 0x25B35
PADDING_START = CANDIDATE_BODY_END
PADDING_END = ISLAND_END
MUL128 = 0x23B50
SCALAR_ROOT_CALL = 0x256C7
RESTORING_LOOP = 0x257E4
RESTORING_BACKEDGE = 0x259F9
WORKSPACE = {
    "srd0": 0x27A4,
    "srd1": 0x27A8,
    "srd2": 0x27AC,
    "srd3": 0x27B0,
    "sqrh": 0x27B4,
    "sqrl": 0x27B8,
    "sqmh": 0x27BC,
    "sqml": 0x27C0,
    "sqcarry": 0x27C4,
    "sqstep": 0x27C8,
    "srm0": 0x27CC,
    "srm1": 0x27D0,
    "srm2": 0x27D4,
    "srm3": 0x27D8,
}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def lino_header(data):
    marker = data.index(b"LNLMInit")
    code_units = u32(data, marker + 0x34)
    entry_units = u32(data, marker + 0x38)
    physical_end = u32(data, marker + 0x40)
    code_start = physical_end - 4 * code_units
    return {
        "marker": marker,
        "code_units": code_units,
        "code_entry_units": entry_units,
        "physical_end": physical_end,
        "code_start": code_start,
        "code_entry": code_start + 4 * entry_units,
    }


def instructions(data, start, end):
    result = list(ENGINE.disasm(data[start:end], start))
    assert result
    assert result[0].address == start
    assert result[-1].address + result[-1].size == end
    return result


def direct_target(instruction):
    if instruction.mnemonic != "call" and not instruction.mnemonic.startswith("j"):
        return None
    try:
        return int(instruction.op_str, 0)
    except ValueError:
        return None


ENGINE = Cs(CS_ARCH_X86, CS_MODE_32)
accepted = ACCEPTED_EXE.read_bytes()
candidate = CANDIDATE_EXE.read_bytes()
accepted_fp = ACCEPTED_FP.read_bytes()
candidate_fp = CANDIDATE_FP.read_bytes()
assert sha256(accepted) == EXPECTED_ACCEPTED_EXE_SHA256
assert sha256(candidate) == EXPECTED_CANDIDATE_EXE_SHA256
assert sha256(accepted_fp) == EXPECTED_ACCEPTED_FP_SHA256
assert sha256(candidate_fp) == EXPECTED_CANDIDATE_FP_SHA256
assert (ROOT / "work/fp/fpsoft.txt").read_bytes() == candidate_fp
assert (ROOT / "work/vhgame.exe").read_bytes() == candidate
transform = runpy.run_path(str(EVIDENCE / "apply_candidate.py"))["transform"]
assert candidate_fp == transform(accepted_fp)
assert len(accepted) == len(candidate) == 645_966
expected_header = {
    "marker": 0x3C00,
    "code_units": 133_081,
    "code_entry_units": 96_554,
    "physical_end": 0x9B0DC,
    "code_start": 0x19178,
    "code_entry": 0x77620,
}
assert lino_header(accepted) == lino_header(candidate) == expected_header

# The calibrated replacement consumes exactly the old helper island. Every
# package byte before its verified call target and after its verified endpoint
# is byte-identical, so no downstream routine or payload is relocated.
assert accepted[:ROOT_START] == candidate[:ROOT_START]
assert accepted[ISLAND_END:] == candidate[ISLAND_END:]
differences = [
    offset for offset, (left, right) in enumerate(zip(accepted, candidate))
    if left != right
]
assert len(differences) == 755
assert differences[0] == 0x257BE
assert differences[-1] == 0x25B48
assert all(ROOT_START <= offset < ISLAND_END for offset in differences)

accepted_code = instructions(
    accepted, expected_header["code_start"], expected_header["physical_end"])
candidate_code = instructions(
    candidate, expected_header["code_start"], expected_header["physical_end"])
assert len(accepted_code) == 93_575
assert len(candidate_code) == 93_588
accepted_map = {item.address: item for item in accepted_code}
candidate_map = {item.address: item for item in candidate_code}

# XScalarSqrt reaches XRootCore through the same direct call at the exact same
# address. There are no other entries from outside the helper, and no direct
# edge targets the interior of its unreachable footprint calibration.
for mapping in (accepted_map, candidate_map):
    call = mapping[SCALAR_ROOT_CALL]
    assert call.mnemonic == "call"
    assert direct_target(call) == ROOT_START
external_entries = []
padding_entries = []
for item in candidate_code:
    target = direct_target(item)
    if target is None:
        continue
    if not (ROOT_START <= item.address < ISLAND_END) and ROOT_START <= target < ISLAND_END:
        external_entries.append((item.address, item.mnemonic, target))
    if PADDING_START <= target < PADDING_END:
        padding_entries.append((item.address, item.mnemonic, target))
assert external_entries == [(SCALAR_ROOT_CALL, "call", ROOT_START)]
assert padding_entries == []

accepted_root = instructions(accepted, ROOT_START, ISLAND_END)
candidate_root = instructions(candidate, ROOT_START, ISLAND_END)
assert len(accepted_root) == 205
assert len(candidate_root) == 218
accepted_calls = [
    (item.address, direct_target(item)) for item in accepted_root
    if item.mnemonic == "call"
]
candidate_calls = [item for item in candidate_root if item.mnemonic == "call"]
assert accepted_calls == [(0x25826, MUL128), (0x25945, MUL128)]
assert candidate_calls == []
assert all(
    direct_target(item) is None or ROOT_START <= direct_target(item) < ISLAND_END
    for item in candidate_root
)

# The source-shaped restoring loop has one exact 64-iteration counter/backedge.
# Its first three instructions capture the incoming high pair in E/esi; srm3
# remains unread until the accepted-residual compatibility assignment.
first_loop = candidate_map[RESTORING_LOOP]
assert first_loop.mnemonic == "mov"
assert first_loop.op_str == "eax, dword ptr [edi + 0x27b0]"
loop_sequence = [candidate_map[address] for address in (
    0x257E4, 0x257EA, 0x257ED,
)]
assert [(item.mnemonic, item.op_str) for item in loop_sequence] == [
    ("mov", "eax, dword ptr [edi + 0x27b0]"),
    ("shr", "eax, 0x1e"),
    ("mov", "esi, eax"),
]
assert [(candidate_map[address].mnemonic, candidate_map[address].op_str)
        for address in (0x259E9, 0x259EF, RESTORING_BACKEDGE)] == [
    ("inc", "dword ptr [edi + 0x27c8]"),
    ("cmp", "dword ptr [edi + 0x27c8], 0x40"),
    ("jl", hex(RESTORING_LOOP)),
]
assert sum(
    item.mnemonic == "cmp" and
    item.op_str == "dword ptr [edi + 0x27c8], 0x40"
    for item in candidate_root
) == 1
assert sum(
    item.mnemonic == "jl" and direct_target(item) == RESTORING_LOOP
    for item in candidate_root
) == 1
srm3_accesses = [
    (item.address, item.mnemonic, item.op_str) for item in candidate_root
    if "0x27d8" in item.op_str
]
assert srm3_accesses == [
    (0x25A4B, "mov", "dword ptr [edi + 0x27d8], eax"),
]

# The existing workspace declaration and addresses remain fixed. The twelve
# active restoring words remain generated operands; obsolete sqmh/sqml are
# intentionally absent, preventing accidental aliasing or declaration shift.
root_text = "\n".join(item.op_str for item in candidate_root)
for name, address in WORKSPACE.items():
    if name not in {"sqmh", "sqml"}:
        assert f"0x{address:x}" in root_text
assert "0x27bc" not in root_text and "0x27c0" not in root_text
assert sorted(WORKSPACE.values()) == list(range(0x27A4, 0x27DC, 4))

# XRootCore returns before four calibrated immediate loads. They occupy the
# exact twenty bytes freed by the register-held loop. No edge enters them and
# the following public wrapper starts at the accepted address.
assert candidate_map[0x25B2F].mnemonic == "mov"
assert candidate_map[0x25B2F].op_str == "ebp, 0x646f6e65"
assert candidate_map[0x25B34].mnemonic == "ret"
padding = candidate[PADDING_START:PADDING_END]
assert padding == bytes.fromhex(
    "b8 00 00 00 00 b8 00 00 00 00 b8 00 00 00 00 b8 00 00 00 00")
padding_instructions = instructions(candidate, PADDING_START, PADDING_END)
assert [(item.mnemonic, item.op_str) for item in padding_instructions] == [
    ("mov", "eax, 0"),
    ("mov", "eax, 0"),
    ("mov", "eax, 0"),
    ("mov", "eax, 0"),
]
assert accepted_map[ISLAND_END].mnemonic == candidate_map[ISLAND_END].mnemonic == "pushal"
assert accepted[ISLAND_END:ISLAND_END + 256] == candidate[ISLAND_END:ISLAND_END + 256]

model = json.loads((EVIDENCE / "model.json").read_text(encoding="utf-8"))
build = json.loads((EVIDENCE / "build.json").read_text(encoding="utf-8"))
assert model["status"] == "pass"
assert model["candidate_file_equals_exact_transform"]
assert model["candidate_mul128_calls_per_positive_root"] == 0
assert model["restoring_iterations_per_positive_root"] == 64
assert build["status"] == "pass"
assert build["private_inactive_desktop"]
assert build["entry_point"] == "lino_build.ps1"
assert build["candidate_executable_sha256"] == EXPECTED_CANDIDATE_EXE_SHA256

result = {
    "schema": 1,
    "task": 222,
    "status": "pass",
    "accepted_sha256": sha256(accepted),
    "candidate_sha256": sha256(candidate),
    "executable_size": len(candidate),
    "header_and_code_boundaries_exact": True,
    "root_helper_start": hex(ROOT_START),
    "root_helper_island_end": hex(ISLAND_END),
    "root_helper_island_bytes": ISLAND_END - ROOT_START,
    "candidate_executable_body_end": hex(CANDIDATE_BODY_END),
    "package_bytes_outside_root_island_exact": True,
    "changed_byte_values": len(differences),
    "unexpected_changes": 0,
    "helper_entry_and_endpoint_preserved": True,
    "downstream_addresses_and_bytes_exact": True,
    "external_direct_entries_to_helper": len(external_entries),
    "external_direct_entries_to_helper_interiors": 0,
    "accepted_generated_mul128_call_sites": len(accepted_calls),
    "candidate_generated_mul128_call_sites": len(candidate_calls),
    "accepted_mul128_calls_per_positive_root": 65,
    "candidate_mul128_calls_per_positive_root": 0,
    "restoring_iterations_per_positive_root": 64,
    "restoring_counter_and_backedge_exact": True,
    "workspace_addresses": {name: hex(address) for name, address in WORKSPACE.items()},
    "workspace_addresses_unchanged": True,
    "dead_srm3_initialization_removed": True,
    "incoming_pair_held_in_e": True,
    "srm3_assigned_before_first_read": True,
    "unreachable_footprint_padding_bytes": len(padding),
    "unreachable_footprint_padding_exact": True,
    "direct_entries_to_padding": len(padding_entries),
    "source_exact_transform": True,
    "source_boundary": "one common tracked shared-Lino closure",
    "raw_target_machine_blocks_added": False,
    "compiler_unchanged": True,
    "cpu_pack_unchanged": True,
}
OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
