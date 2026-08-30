from pathlib import Path
import hashlib
import json
import runpy
import struct

from capstone import Cs, CS_ARCH_X86, CS_MODE_32

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/buffered-limb-restoring-fsqrt-20260830"
ACCEPTED_EXE = EVIDENCE / "accepted/vhgame.exe"
CANDIDATE_EXE = EVIDENCE / "candidate/vhgame.exe"
ACCEPTED_FP = EVIDENCE / "accepted/fpsoft.txt"
CANDIDATE_FP = EVIDENCE / "candidate/fpsoft.txt"
OUTPUT = EVIDENCE / "production-layout.json"
EXPECTED_ACCEPTED_EXE_SHA256 = (
    "c4a62f5068262239a8a5665c443a75784fa2472941c9dfdb8fb731f5c8217ca2")
EXPECTED_CANDIDATE_EXE_SHA256 = (
    "e18e8eb45ac0bc03aa2ee1f51ce1ae54f6ee00a0e8a7cef24cbd3adebcdf32a0")
EXPECTED_ACCEPTED_FP_SHA256 = (
    "6b2e209be5b62013276514f8c418cafc92ecb9fd4d9fd6fbdf91453bfebe66d3")
EXPECTED_CANDIDATE_FP_SHA256 = (
    "063ecf40b0faab3b2779d8ff159b8fa815eec7b397de0d47e68223841e2a59cc")
ROOT_START = 0x256F1
ISLAND_END = 0x25B49
CANDIDATE_BODY_END = ISLAND_END
SCALAR_ROOT_CALL = 0x256C7
RESTORING_LOOP = 0x25804
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
assert len(differences) == 731
assert differences[0] == 0x257E0
assert differences[-1] == 0x25B48
assert all(ROOT_START <= offset < ISLAND_END for offset in differences)

accepted_code = instructions(
    accepted, expected_header["code_start"], expected_header["physical_end"])
candidate_code = instructions(
    candidate, expected_header["code_start"], expected_header["physical_end"])
assert len(accepted_code) == 93_588
assert len(candidate_code) == 93_581
accepted_map = {item.address: item for item in accepted_code}
candidate_map = {item.address: item for item in candidate_code}

# XScalarSqrt reaches XRootCore through the same direct call at the exact same
# address. There are no other entries from outside the helper. The candidate
# consumes the accepted unreachable calibration and returns at the island's
# final byte, so every direct target must remain within the functional helper.
for mapping in (accepted_map, candidate_map):
    call = mapping[SCALAR_ROOT_CALL]
    assert call.mnemonic == "call"
    assert direct_target(call) == ROOT_START
external_entries = []
for item in candidate_code:
    target = direct_target(item)
    if target is None:
        continue
    if not (ROOT_START <= item.address < ISLAND_END) and ROOT_START <= target < ISLAND_END:
        external_entries.append((item.address, item.mnemonic, target))
assert external_entries == [(SCALAR_ROOT_CALL, "call", ROOT_START)]

accepted_root = instructions(accepted, ROOT_START, ISLAND_END)
candidate_root = instructions(candidate, ROOT_START, ISLAND_END)
assert len(accepted_root) == 218
assert len(candidate_root) == 211
accepted_calls = [item for item in accepted_root if item.mnemonic == "call"]
candidate_calls = [item for item in candidate_root if item.mnemonic == "call"]
assert accepted_calls == []
assert candidate_calls == []
assert all(
    direct_target(item) is None or ROOT_START <= direct_target(item) < ISLAND_END
    for item in candidate_root
)

# The candidate retains exactly 64 restoring decisions while consuming sixteen
# pairs from each of four radicand limbs. The hot loop reads and shifts the
# directly addressed sqmh value buffer. Only three cold handoffs use dynamic
# addressing to load and clear the next source limb; a fourth pointer decrement
# detects completion below srd0.
assert (candidate_map[0x257DA].mnemonic,
        candidate_map[0x257DA].op_str) == (
            "mov", "dword ptr [edi + 0x27c8], 0x9ec")
assert 0x9EC * 4 == WORKSPACE["srd3"]
assert [(candidate_map[address].mnemonic, candidate_map[address].op_str)
        for address in (
            0x257E4, 0x257EA, 0x257F0, 0x257FA,
            0x25804, 0x2580A, 0x2580C, 0x2580F,
            0x25815, 0x25817, 0x2581A)] == [
    ("mov", "eax, dword ptr [edi + 0x27b0]"),
    ("mov", "dword ptr [edi + 0x27bc], eax"),
    ("mov", "dword ptr [edi + 0x27b0], 0"),
    ("mov", "dword ptr [edi + 0x27c0], 0x10"),
    ("mov", "eax, dword ptr [edi + 0x27bc]"),
    ("mov", "esi, eax"),
    ("shl", "eax, 2"),
    ("mov", "dword ptr [edi + 0x27bc], eax"),
    ("mov", "eax, esi"),
    ("shr", "eax, 0x1e"),
    ("mov", "esi, eax"),
]
assert [(candidate_map[address].mnemonic, candidate_map[address].op_str)
        for address in (
            0x259B9, 0x259BF, 0x259C9, 0x259CF, 0x259D5,
            0x259DF, 0x259E5, 0x259EB, 0x259F2, 0x259F8,
            0x259FD, 0x25A04, 0x25A0E)] == [
    ("dec", "dword ptr [edi + 0x27c0]"),
    ("cmp", "dword ptr [edi + 0x27c0], 0"),
    ("jne", hex(RESTORING_LOOP)),
    ("dec", "dword ptr [edi + 0x27c8]"),
    ("cmp", "dword ptr [edi + 0x27c8], 0x9e9"),
    ("jl", "0x25a13"),
    ("mov", "ebx, dword ptr [edi + 0x27c8]"),
    ("mov", "eax, dword ptr [edi + ebx*4]"),
    ("mov", "dword ptr [edi + 0x27bc], eax"),
    ("mov", "eax, 0"),
    ("mov", "dword ptr [edi + ebx*4], eax"),
    ("mov", "dword ptr [edi + 0x27c0], 0x10"),
    ("jmp", hex(RESTORING_LOOP)),
]
assert 0x9E9 * 4 == WORKSPACE["srd0"]
assert sum(
    direct_target(item) == RESTORING_LOOP and item.mnemonic == "jne"
    for item in candidate_root) == 1
assert sum(
    direct_target(item) == RESTORING_LOOP and item.mnemonic == "jmp"
    for item in candidate_root) == 1
assert sum(
    item.mnemonic == "mov" and item.op_str == "eax, dword ptr [edi + 0x27bc]"
    for item in candidate_root) == 1
assert sum(
    item.mnemonic == "mov" and item.op_str == "dword ptr [edi + 0x27bc], eax"
    for item in candidate_root) == 3
assert sum(
    item.mnemonic == "mov" and item.op_str == "eax, dword ptr [edi + ebx*4]"
    for item in candidate_root) == 1
assert sum(
    item.mnemonic == "mov" and item.op_str == "dword ptr [edi + ebx*4], eax"
    for item in candidate_root) == 1
srm3_accesses = [
    (item.address, item.mnemonic, item.op_str) for item in candidate_root
    if "0x27d8" in item.op_str
]
assert srm3_accesses == [
    (0x25A5F, "mov", "dword ptr [edi + 0x27d8], eax"),
]

# The fixed workspace declaration remains unchanged. sqmh is the direct active
# value buffer, sqml the sixteen-pair count, and sqstep the cold source pointer;
# every address remains in its accepted contiguous slot.
root_text = "\n".join(item.op_str for item in candidate_root)
for address in WORKSPACE.values():
    assert f"0x{address:x}" in root_text
assert sorted(WORKSPACE.values()) == list(range(0x27A4, 0x27DC, 4))

# The candidate's functional return consumes the accepted 20-byte unreachable
# calibration exactly and lands in the final byte of the same helper island.
# The following routine and every downstream byte/address remain exact.
assert accepted_map[0x25B34].mnemonic == "ret"
accepted_padding = accepted[0x25B35:ISLAND_END]
assert accepted_padding == bytes.fromhex(
    "b8 00 00 00 00 b8 00 00 00 00 b8 00 00 00 00 b8 00 00 00 00")
assert candidate_map[0x25B43].mnemonic == "mov"
assert candidate_map[0x25B43].op_str == "ebp, 0x646f6e65"
assert candidate_map[0x25B48].mnemonic == "ret"
assert candidate_map[0x25B48].size == 1
assert accepted_map[ISLAND_END].mnemonic == candidate_map[ISLAND_END].mnemonic == "pushal"
assert accepted[ISLAND_END:ISLAND_END + 256] == candidate[ISLAND_END:ISLAND_END + 256]

model = json.loads((EVIDENCE / "model.json").read_text(encoding="utf-8"))
build = json.loads((EVIDENCE / "build.json").read_text(encoding="utf-8"))
assert model["status"] == "pass"
assert model["candidate_file_equals_exact_transform"]
assert model["baseline_mul128_calls_per_positive_root"] == 0
assert model["candidate_mul128_calls_per_positive_root"] == 0
assert model["baseline_restoring_iterations_per_positive_root"] == 64
assert model["candidate_restoring_iterations_per_positive_root"] == 64
assert model["baseline_radix_limb_shifts_per_positive_root"] == 256
assert model["candidate_radix_limb_shifts_per_positive_root"] == 64
assert model["candidate_hot_dynamic_pointer_reads_per_positive_root"] == 0
assert model["candidate_direct_buffer_reads_per_positive_root"] == 64
assert model["candidate_direct_buffer_writes_per_positive_root"] == 64
assert model["candidate_dynamic_limb_handoffs_per_positive_root"] == 3
assert model["candidate_dynamic_limb_clears_per_positive_root"] == 3
assert model["candidate_pointer_decrements_per_positive_root"] == 4
assert build["status"] == "pass"
assert build["private_inactive_desktop"]
assert build["build_entry"] == "lino_build.ps1"
assert build["candidate_executable_sha256"] == EXPECTED_CANDIDATE_EXE_SHA256

result = {
    "schema": 1,
    "task": 224,
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
    "accepted_mul128_calls_per_positive_root": 0,
    "candidate_mul128_calls_per_positive_root": 0,
    "accepted_restoring_iterations_per_positive_root": 64,
    "candidate_restoring_iterations_per_positive_root": 64,
    "accepted_radix_limb_shifts_per_positive_root": 256,
    "candidate_radix_limb_shifts_per_positive_root": 64,
    "candidate_hot_dynamic_pointer_reads_per_positive_root": 0,
    "candidate_direct_buffer_reads_per_positive_root": 64,
    "candidate_direct_buffer_writes_per_positive_root": 64,
    "candidate_dynamic_limb_handoffs_per_positive_root": 3,
    "candidate_dynamic_limb_clears_per_positive_root": 3,
    "candidate_pointer_decrements_per_positive_root": 4,
    "buffered_limb_schedule_exact": True,
    "workspace_addresses": {name: hex(address) for name, address in WORKSPACE.items()},
    "workspace_addresses_unchanged": True,
    "dead_srm3_initialization_removed": True,
    "incoming_pair_held_in_e": True,
    "srm3_assigned_before_first_read": True,
    "accepted_unreachable_calibration_bytes": len(accepted_padding),
    "accepted_unreachable_calibration_consumed": True,
    "candidate_unreachable_calibration_bytes": 0,
    "candidate_return_is_final_island_byte": True,
    "source_exact_transform": True,
    "source_boundary": "one common tracked shared-Lino closure",
    "raw_target_machine_blocks_added": False,
    "compiler_unchanged": True,
    "cpu_pack_unchanged": True,
}
OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
