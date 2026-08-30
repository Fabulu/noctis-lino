from pathlib import Path
import hashlib
import json
import struct

from capstone import Cs, CS_ARCH_X86, CS_MODE_32

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/dead-fixed-f64-fi-stores-20260830"
ACCEPTED = EVIDENCE / "accepted/vhgame.exe"
CANDIDATE = EVIDENCE / "candidate/vhgame.exe"
OUTPUT = EVIDENCE / "production-layout.json"

EXPECTED_ACCEPTED_SHA256 = (
    "81900287fa9e19291a27667b0e23d5c0c6324e86e8b9d8da0ff82a65cc302823")
EXPECTED_CANDIDATE_SHA256 = (
    "faf9eac8ab68b6f18dd0d51920f7fb98446579166ffdd1e7300ab91972402227")
INT_TO_F = 0x2820D
ACCEPTED_APPEND_START = 0x9B0DA
CANDIDATE_APPEND_START = 0x9B01C
ACCEPTED_RING_CALL = 0x7CCFD
CANDIDATE_RING_CALL = 0x7CC3F
DIRECT_SITES = (
    (0x7AE4B, 0x7AE4B, 3, 0x40080000),
    (0x7B04A, 0x7B037, 250, 0x406F4000),
    (0x7B188, 0x7B162, 100, 0x40590000),
    (0x7B239, 0x7B200, 25, 0x40390000),
    (0x7B695, 0x7B649, 250, 0x406F4000),
    (0x7B7C9, 0x7B76A, 100, 0x40590000),
    (0x7B875, 0x7B803, 25, 0x40390000),
    (0x7BDF4, 0x7BD6F, 3, 0x40080000),
    (0x7BE84, 0x7BDEC, 5, 0x40140000),
    (0x7BF26, 0x7BE7B, 1000, 0x408F4000),
)


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


def instructions(data, header):
    engine = Cs(CS_ARCH_X86, CS_MODE_32)
    result = list(engine.disasm(
        data[header["code_start"]:header["physical_end"]],
        header["code_start"],
    ))
    assert result
    assert result[-1].address + result[-1].size == header["physical_end"]
    return result


def range_instructions(mapping, start, end):
    result = []
    address = start
    while address < end:
        instruction = mapping[address]
        result.append(instruction)
        address += instruction.size
    assert address == end
    return result


def is_direct_control(instruction):
    return instruction.mnemonic == "call" or instruction.mnemonic.startswith("j")


def direct_target(instruction):
    if not is_direct_control(instruction):
        return None
    try:
        return int(instruction.op_str, 0)
    except ValueError:
        return None


def outside_ranges(instruction, ranges):
    return not any(start <= instruction.address < end for start, end in ranges)


accepted = ACCEPTED.read_bytes()
candidate = CANDIDATE.read_bytes()
assert sha256(accepted) == EXPECTED_ACCEPTED_SHA256
assert sha256(candidate) == EXPECTED_CANDIDATE_SHA256
assert len(accepted) == 645_966
assert len(candidate) == 645_802
accepted_header = lino_header(accepted)
candidate_header = lino_header(candidate)
assert accepted_header == {
    "marker": 0x3C00,
    "code_units": 133_081,
    "code_entry_units": 96_554,
    "physical_end": 0x9B0DC,
    "code_start": 0x19178,
    "code_entry": 0x77620,
}
assert candidate_header == {
    "marker": 0x3C00,
    "code_units": 133_040,
    "code_entry_units": 96_554,
    "physical_end": 0x9B038,
    "code_start": 0x19178,
    "code_entry": 0x77620,
}
assert accepted_header["physical_end"] - candidate_header["physical_end"] == 164
assert accepted_header["code_units"] - candidate_header["code_units"] == 41
assert len(accepted) - len(candidate) == 164
assert accepted[accepted_header["physical_end"]:] == candidate[
    candidate_header["physical_end"]:]

header_allowed = set(range(0x3C34, 0x3C38)) | set(range(0x3C40, 0x3C44))
prefix_differences = {
    offset for offset, (left, right) in enumerate(zip(
        accepted[:accepted_header["code_start"]],
        candidate[:candidate_header["code_start"]],
    )) if left != right
}
assert prefix_differences
assert prefix_differences <= header_allowed

accepted_instructions = instructions(accepted, accepted_header)
candidate_instructions = instructions(candidate, candidate_header)
accepted_map = {instruction.address: instruction for instruction in accepted_instructions}
candidate_map = {instruction.address: instruction for instruction in candidate_instructions}
assert len(accepted_instructions) == 93_575
assert len(candidate_instructions) == 93_539

accepted_ranges = [(start, start + 39) for start, _, _, _ in DIRECT_SITES]
candidate_ranges = [(start, start + 20) for _, start, _, _ in DIRECT_SITES]
accepted_exclusions = accepted_ranges + [
    (accepted_header["physical_end"] - 2, accepted_header["physical_end"])]
candidate_exclusions = candidate_ranges + [
    (CANDIDATE_APPEND_START, candidate_header["physical_end"])]
accepted_normal = [
    instruction for instruction in accepted_instructions
    if outside_ranges(instruction, accepted_exclusions)
]
candidate_normal = [
    instruction for instruction in candidate_instructions
    if outside_ranges(instruction, candidate_exclusions)
]
assert len(accepted_normal) == len(candidate_normal) == 93_514
accepted_index = {
    instruction.address: index for index, instruction in enumerate(accepted_normal)}
candidate_index = {
    instruction.address: index for index, instruction in enumerate(candidate_normal)}
accepted_special_targets = {
    accepted_start: index
    for index, (accepted_start, _, _, _) in enumerate(DIRECT_SITES)
}
candidate_special_targets = {
    candidate_start: index
    for index, (_, candidate_start, _, _) in enumerate(DIRECT_SITES)
}


def expected_candidate_address(accepted_address):
    removed = sum(
        19 for accepted_start, _, _, _ in DIRECT_SITES
        if accepted_address >= accepted_start + 39
    )
    return accepted_address - removed


def semantic_target(target, normal_index, special_targets):
    if target in normal_index:
        return "normal", normal_index[target]
    if target in special_targets:
        return "direct-site", special_targets[target]
    return "external", target


control_encoding_changes = 0
relocated_control_targets = 0
for index, (left, right) in enumerate(zip(accepted_normal, candidate_normal)):
    assert right.address == expected_candidate_address(left.address), (index, left, right)
    assert left.mnemonic == right.mnemonic, (index, left, right)
    assert left.size == right.size, (index, left, right)
    if left.address == ACCEPTED_RING_CALL:
        assert right.address == CANDIDATE_RING_CALL
        assert left.bytes[0] == right.bytes[0] == 0xE8
        assert left.op_str == hex(INT_TO_F)
        assert right.op_str == hex(CANDIDATE_APPEND_START)
        control_encoding_changes += left.bytes != right.bytes
        relocated_control_targets += 1
        continue
    if is_direct_control(left):
        assert is_direct_control(right)
        left_target = direct_target(left)
        right_target = direct_target(right)
        if left_target is None or right_target is None:
            assert left.op_str == right.op_str
        else:
            assert semantic_target(
                left_target, accepted_index, accepted_special_targets
            ) == semantic_target(
                right_target, candidate_index, candidate_special_targets
            ), (index, left, right)
            relocated_control_targets += left_target != right_target
        control_encoding_changes += left.bytes != right.bytes
    else:
        assert left.op_str == right.op_str, (index, left, right)
        assert left.bytes == right.bytes, (index, left, right)
assert relocated_control_targets == 3_592

# Each old 39-byte conversion/copy sequence is replaced by two exact immediate
# FB stores totaling 20 bytes. The next accepted instruction maps immediately
# after each replacement, so every site removes exactly 19 generated bytes.
for index, (accepted_start, candidate_start, value, high) in enumerate(DIRECT_SITES):
    assert candidate_start == accepted_start - 19 * index
    old = range_instructions(accepted_map, accepted_start, accepted_start + 39)
    new = range_instructions(candidate_map, candidate_start, candidate_start + 20)
    assert len(old) == 6
    assert old[0].mnemonic == "mov"
    assert old[0].bytes == (
        bytes.fromhex("c7 87 50 26 00 00") + struct.pack("<I", value))
    assert old[1].mnemonic == "call" and old[1].op_str == hex(INT_TO_F)
    assert [(item.mnemonic, item.op_str) for item in old[2:]] == [
        ("mov", "ebp, dword ptr [edi + 0x2620]"),
        ("mov", "dword ptr [edi + 0x2628], ebp"),
        ("mov", "ebp, dword ptr [edi + 0x2624]"),
        ("mov", "dword ptr [edi + 0x262c], ebp"),
    ]
    assert len(new) == 2
    assert new[0].bytes == bytes.fromhex(
        "c7 87 28 26 00 00 00 00 00 00")
    assert new[0].op_str == "dword ptr [edi + 0x2628], 0"
    assert new[1].bytes == (
        bytes.fromhex("c7 87 2c 26 00 00") + struct.pack("<I", high))
    assert new[1].op_str == f"dword ptr [edi + 0x262c], {hex(high)}"
    accepted_next = accepted_map[accepted_start + 39]
    candidate_next = candidate_map[candidate_start + 20]
    assert candidate_next.address == expected_candidate_address(accepted_next.address)
    assert accepted_next.mnemonic == candidate_next.mnemonic
    assert accepted_next.op_str == candidate_next.op_str
    assert accepted_next.bytes == candidate_next.bytes

# No branch enters the interior of a replacement. Four existing gates target
# the starts of two sites; all other direct sites are entered by fallthrough.
incoming_special = []
for instruction in candidate_normal:
    target = direct_target(instruction)
    if target in candidate_special_targets:
        incoming_special.append((instruction.address, target))
assert incoming_special == [
    (0x7B0C0, 0x7B162),
    (0x7B0E9, 0x7B162),
    (0x7B6D2, 0x7B76A),
    (0x7B6FB, 0x7B76A),
]
for start, end in candidate_ranges:
    interior = set(range(start + 1, end))
    assert not any(direct_target(instruction) in interior
                   for instruction in candidate_normal)

# The ring site retains its FI immediate store and five-byte call shape; only
# the rel32 call target changes to the one appended exact-FA helper.
accepted_ring = range_instructions(
    accepted_map, ACCEPTED_RING_CALL - 10, ACCEPTED_RING_CALL + 5)
candidate_ring = range_instructions(
    candidate_map, CANDIDATE_RING_CALL - 10, CANDIDATE_RING_CALL + 5)
assert len(accepted_ring) == len(candidate_ring) == 2
assert accepted_ring[0].bytes == candidate_ring[0].bytes == bytes.fromhex(
    "c7 87 50 26 00 00 05 00 00 00")
assert accepted_ring[1].mnemonic == candidate_ring[1].mnemonic == "call"
assert accepted_ring[1].size == candidate_ring[1].size == 5
assert accepted_ring[1].op_str == hex(INT_TO_F)
assert candidate_ring[1].op_str == hex(CANDIDATE_APPEND_START)

# The previous unreachable EOF padding is shifted by the ten reductions but is
# byte-exact. One 26-byte helper consumes the old alignment padding and moves
# the final two zero alignment bytes to the new physical end.
assert accepted[0x9B0D0:ACCEPTED_APPEND_START] == candidate[
    0x9B012:CANDIDATE_APPEND_START]
assert accepted_map[0x9B0CB].mnemonic == candidate_map[0x9B00D].mnemonic == "jmp"
assert accepted_map[0x9B0CB].op_str == candidate_map[0x9B00D].op_str == "0x2f97a"
assert accepted[ACCEPTED_APPEND_START:accepted_header["physical_end"]] == b"\0\0"
assert candidate[candidate_header["physical_end"] - 2:
                 candidate_header["physical_end"]] == b"\0\0"
helper = range_instructions(
    candidate_map, CANDIDATE_APPEND_START,
    candidate_header["physical_end"] - 2)
assert len(helper) == 4
assert helper[0].bytes == bytes.fromhex(
    "c7 87 20 26 00 00 00 00 00 00")
assert helper[0].op_str == "dword ptr [edi + 0x2620], 0"
assert helper[1].bytes == bytes.fromhex(
    "c7 87 24 26 00 00 00 00 14 40")
assert helper[1].op_str == "dword ptr [edi + 0x2624], 0x40140000"
assert helper[2].bytes == bytes.fromhex("bd 65 6e 6f 64")
assert helper[2].op_str == "ebp, 0x646f6e65"
assert helper[3].bytes == b"\xc3" and helper[3].mnemonic == "ret"
helper_entries = [
    (instruction.address, direct_target(instruction))
    for instruction in candidate_normal
    if direct_target(instruction) == CANDIDATE_APPEND_START
]
assert helper_entries == [(CANDIDATE_RING_CALL, CANDIDATE_APPEND_START)]

result = {
    "schema": 1,
    "task": 219,
    "status": "pass",
    "accepted_sha256": sha256(accepted),
    "candidate_sha256": sha256(candidate),
    "accepted_executable_size": len(accepted),
    "candidate_executable_size": len(candidate),
    "code_start": candidate_header["code_start"],
    "accepted_code_end": accepted_header["physical_end"],
    "candidate_code_end": candidate_header["physical_end"],
    "code_shrink_bytes": 164,
    "direct_site_shrink_bytes": 190,
    "helper_append_bytes": 26,
    "package_suffix_shift_exact": True,
    "normalized_preexisting_instructions": len(candidate_normal),
    "normalized_instruction_stream_exact": True,
    "relocated_control_targets": relocated_control_targets,
    "control_encoding_changes": control_encoding_changes,
    "unexpected_noncontrol_instruction_changes": 0,
    "direct_fb_sites": len(DIRECT_SITES),
    "accepted_direct_site_bytes": 39,
    "candidate_direct_site_bytes": 20,
    "direct_site_bytes_removed": 19,
    "external_direct_entries_to_site_starts": len(incoming_special),
    "external_direct_entries_to_site_interiors": 0,
    "ring_fi_store_retained": True,
    "ring_call_shape_retained": True,
    "helper_offset": hex(CANDIDATE_APPEND_START),
    "helper_generated_shape_exact": True,
    "helper_direct_entries": len(helper_entries),
    "prior_unreachable_padding_preserved": True,
    "compiler_alignment_padding_relocated": True,
    "source_boundary": "shared Lino only",
}
OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
