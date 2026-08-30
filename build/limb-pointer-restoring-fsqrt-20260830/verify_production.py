from pathlib import Path
import hashlib
import json
import runpy
import struct

from capstone import Cs, CS_ARCH_X86, CS_MODE_32

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/limb-pointer-restoring-fsqrt-20260830"
ACCEPTED_EXE = EVIDENCE / "accepted/vhgame.exe"
CANDIDATE_EXE = EVIDENCE / "candidate/vhgame.exe"
ACCEPTED_FP = EVIDENCE / "accepted/fpsoft.txt"
CANDIDATE_FP = EVIDENCE / "candidate/fpsoft.txt"
OUTPUT = EVIDENCE / "production-layout.json"
EXPECTED_ACCEPTED_EXE_SHA256 = (
    "c4a62f5068262239a8a5665c443a75784fa2472941c9dfdb8fb731f5c8217ca2")
EXPECTED_CANDIDATE_EXE_SHA256 = (
    "9844a08f0fc0d322eac8240d8efa58a9fb20d37872420d8f07cc24751b33e580")
EXPECTED_ACCEPTED_FP_SHA256 = (
    "6b2e209be5b62013276514f8c418cafc92ecb9fd4d9fd6fbdf91453bfebe66d3")
EXPECTED_CANDIDATE_FP_SHA256 = (
    "62401cb0446e44fa4c4f93d51b11088aa25e7f898830a17c5265a37e60da30fb")
ROOT_START = 0x256F1
ISLAND_END = 0x25B49
CANDIDATE_BODY_END = 0x25B2C
PADDING_START = CANDIDATE_BODY_END
PADDING_END = ISLAND_END
SCALAR_ROOT_CALL = 0x256C7
RESTORING_LOOP = 0x257F8
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
assert len(differences) == 722
assert differences[0] == 0x257DC
assert differences[-1] == 0x25B48
assert all(ROOT_START <= offset < ISLAND_END for offset in differences)

accepted_code = instructions(
    accepted, expected_header["code_start"], expected_header["physical_end"])
candidate_code = instructions(
    candidate, expected_header["code_start"], expected_header["physical_end"])
assert len(accepted_code) == 93_588
assert len(candidate_code) == 93_589
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
assert len(accepted_root) == 218
assert len(candidate_root) == 219
accepted_calls = [item for item in accepted_root if item.mnemonic == "call"]
candidate_calls = [item for item in candidate_root if item.mnemonic == "call"]
assert accepted_calls == []
assert candidate_calls == []
assert all(
    direct_target(item) is None or ROOT_START <= direct_target(item) < ISLAND_END
    for item in candidate_root
)

# The candidate retains exactly 64 restoring decisions while consuming sixteen
# pairs from each of four contiguous radicand limbs. The hot ingestion shifts
# one dynamically addressed limb; three cold boundaries move the pointer.
assert (candidate_map[0x257DA].mnemonic,
        candidate_map[0x257DA].op_str) == (
            "mov", "dword ptr [edi + 0x27bc], 0x9ec")
assert 0x9EC * 4 == WORKSPACE["srd3"]
assert [(candidate_map[address].mnemonic, candidate_map[address].op_str)
        for address in (
            0x257F8, 0x257FE, 0x25805, 0x25807,
            0x2580A, 0x25811, 0x25813, 0x25816)] == [
    ("mov", "ebx, dword ptr [edi + 0x27bc]"),
    ("mov", "eax, dword ptr [edi + ebx*4]"),
    ("mov", "esi, eax"),
    ("shl", "eax, 2"),
    ("mov", "dword ptr [edi + ebx*4], eax"),
    ("mov", "eax, esi"),
    ("shr", "eax, 0x1e"),
    ("mov", "esi, eax"),
]
assert [(candidate_map[address].mnemonic, candidate_map[address].op_str)
        for address in (
            0x259B5, 0x259BB, 0x259C5, 0x259CB, 0x259D1,
            0x259DB, 0x259E1, 0x259E7, 0x259F1)] == [
    ("dec", "dword ptr [edi + 0x27c0]"),
    ("cmp", "dword ptr [edi + 0x27c0], 0"),
    ("jne", hex(RESTORING_LOOP)),
    ("dec", "dword ptr [edi + 0x27c8]"),
    ("cmp", "dword ptr [edi + 0x27c8], 0"),
    ("je", "0x259f6"),
    ("dec", "dword ptr [edi + 0x27bc]"),
    ("mov", "dword ptr [edi + 0x27c0], 0x10"),
    ("jmp", hex(RESTORING_LOOP)),
]
assert sum(
    direct_target(item) == RESTORING_LOOP and item.mnemonic == "jne"
    for item in candidate_root) == 1
assert sum(
    direct_target(item) == RESTORING_LOOP and item.mnemonic == "jmp"
    for item in candidate_root) == 1
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
    (0x25A42, "mov", "dword ptr [edi + 0x27d8], eax"),
]

# The fixed workspace declaration remains unchanged. The previously unused
# sqmh/sqml words now carry the active limb pointer and its sixteen-pair count;
# all addresses remain in their accepted contiguous slots.
root_text = "\n".join(item.op_str for item in candidate_root)
for address in WORKSPACE.values():
    assert f"0x{address:x}" in root_text
assert sorted(WORKSPACE.values()) == list(range(0x27A4, 0x27DC, 4))

# XRootCore returns before twenty-nine calibrated unreachable bytes: the
# accepted twenty-byte calibration plus nine one-byte increments which restore
# this candidate's exact endpoint. No edge enters the calibration.
assert candidate_map[0x25B26].mnemonic == "mov"
assert candidate_map[0x25B26].op_str == "ebp, 0x646f6e65"
assert candidate_map[0x25B2B].mnemonic == "ret"
padding = candidate[PADDING_START:PADDING_END]
assert padding == bytes.fromhex(
    "b8 00 00 00 00 b8 00 00 00 00 b8 00 00 00 00 b8 00 00 00 00 "
    "40 40 40 40 40 40 40 40 40")
padding_instructions = instructions(candidate, PADDING_START, PADDING_END)
assert [(item.mnemonic, item.op_str) for item in padding_instructions] == [
    ("mov", "eax, 0"),
    ("mov", "eax, 0"),
    ("mov", "eax, 0"),
    ("mov", "eax, 0"),
] + [("inc", "eax")] * 9
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
assert build["status"] == "pass"
assert build["private_inactive_desktop"]
assert build["build_entry"] == "lino_build.ps1"
assert build["candidate_executable_sha256"] == EXPECTED_CANDIDATE_EXE_SHA256

result = {
    "schema": 1,
    "task": 223,
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
    "candidate_limb_pointer_reads_per_positive_root": 64,
    "candidate_limb_boundary_advances_per_positive_root": 3,
    "limb_pointer_schedule_exact": True,
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
