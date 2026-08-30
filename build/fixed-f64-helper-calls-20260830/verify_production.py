from pathlib import Path
import hashlib
import json
import struct

from capstone import Cs, CS_ARCH_X86, CS_MODE_32

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/fixed-f64-helper-calls-20260830"
ACCEPTED = EVIDENCE / "accepted/vhgame.exe"
CANDIDATE = EVIDENCE / "candidate/vhgame.exe"
OUTPUT = EVIDENCE / "production-layout.json"

EXPECTED_ACCEPTED_SHA256 = (
    "81900287fa9e19291a27667b0e23d5c0c6324e86e8b9d8da0ff82a65cc302823")
EXPECTED_CANDIDATE_SHA256 = (
    "511dec34c189499504ccd86ec94f2f838fb34ad192450317ac0aaec943a6f67a")
INT_TO_F = 0x2820D
APPEND_START = 0x9B0DA
HELPERS = (
    (0x9B0DA, 0x40080000, 3),
    (0x9B0F4, 0x40140000, 5),
    (0x9B10E, 0x40390000, 25),
    (0x9B128, 0x40590000, 100),
    (0x9B142, 0x406F4000, 250),
    (0x9B15C, 0x408F4000, 1000),
)
CALL_TARGETS = {
    0x7AE55: 0x9B0DA,
    0x7B054: 0x9B142,
    0x7B192: 0x9B128,
    0x7B243: 0x9B10E,
    0x7B69F: 0x9B142,
    0x7B7D3: 0x9B128,
    0x7B87F: 0x9B10E,
    0x7BDFE: 0x9B0DA,
    0x7BE8E: 0x9B0F4,
    0x7BF30: 0x9B15C,
    0x7CCFD: 0x9B0F4,
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


def instruction_map(data, header):
    engine = Cs(CS_ARCH_X86, CS_MODE_32)
    instructions = list(engine.disasm(
        data[header["code_start"]:header["physical_end"]],
        header["code_start"],
    ))
    assert instructions
    assert instructions[-1].address + instructions[-1].size == header["physical_end"]
    return {instruction.address: instruction for instruction in instructions}


def instruction_signature(instruction):
    return instruction.mnemonic, instruction.op_str, instruction.bytes


def direct_target(instruction):
    if instruction.mnemonic == "call" or instruction.mnemonic.startswith("j"):
        try:
            return int(instruction.op_str, 0)
        except ValueError:
            return None
    return None


accepted = ACCEPTED.read_bytes()
candidate = CANDIDATE.read_bytes()
assert sha256(accepted) == EXPECTED_ACCEPTED_SHA256
assert sha256(candidate) == EXPECTED_CANDIDATE_SHA256
assert len(accepted) == 645_966
assert len(candidate) == 646_122

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
    "code_units": 133_120,
    "code_entry_units": 96_554,
    "physical_end": 0x9B178,
    "code_start": 0x19178,
    "code_entry": 0x77620,
}
assert candidate_header["physical_end"] - accepted_header["physical_end"] == 156
assert candidate_header["code_units"] - accepted_header["code_units"] == 39
assert len(candidate) - len(accepted) == 156

# The package payload following generated code is shifted by exactly the helper
# appendix size and is otherwise byte-identical.
assert accepted[accepted_header["physical_end"]:] == candidate[
    candidate_header["physical_end"]:]

# Before generated code, only the code-unit and physical-end header words move.
header_allowed = set(range(0x3C34, 0x3C38)) | set(range(0x3C40, 0x3C44))
prefix_differences = {
    offset for offset, (left, right) in enumerate(zip(
        accepted[:accepted_header["code_start"]],
        candidate[:candidate_header["code_start"]],
    )) if left != right
}
assert prefix_differences
assert prefix_differences <= header_allowed

accepted_map = instruction_map(accepted, accepted_header)
candidate_map = instruction_map(candidate, candidate_header)
assert len(accepted_map) == 93_575
assert len(candidate_map) == 93_599

# The old meaningful code ends at 0x9b0da. Its final two bytes were alignment
# zeros, and the appendix consumes exactly that padding before growing the code.
assert accepted[APPEND_START:accepted_header["physical_end"]] == b"\0\0"
assert candidate[candidate_header["physical_end"] - 2:
                 candidate_header["physical_end"]] == b"\0\0"
assert accepted_map[0x9B0CB].mnemonic == candidate_map[0x9B0CB].mnemonic == "jmp"
assert accepted_map[0x9B0CB].op_str == candidate_map[0x9B0CB].op_str == "0x2f97a"
assert accepted[0x9B0D0:APPEND_START] == candidate[0x9B0D0:APPEND_START]

# Every pre-existing instruction retains its address and encoding. The eleven
# hot calls retain their five-byte shape; only each rel32 target changes.
meaningful_addresses = [
    address for address in accepted_map if address < APPEND_START
]
assert meaningful_addresses == [
    address for address in candidate_map if address < APPEND_START
]
for address in meaningful_addresses:
    left = accepted_map[address]
    right = candidate_map[address]
    if address in CALL_TARGETS:
        assert left.mnemonic == right.mnemonic == "call"
        assert left.size == right.size == 5
        assert left.op_str == hex(INT_TO_F)
        assert right.op_str == hex(CALL_TARGETS[address])
        assert left.bytes[0] == right.bytes[0] == 0xE8
    else:
        assert instruction_signature(left) == instruction_signature(right)

changed_existing_bytes = {
    offset for offset in range(accepted_header["code_start"], APPEND_START)
    if accepted[offset] != candidate[offset]
}
expected_changed_existing_bytes = {
    offset
    for call in CALL_TARGETS
    for offset in range(call + 1, call + 5)
}
assert changed_existing_bytes == expected_changed_existing_bytes

# Each generated helper is exactly two immediate FA stores, the compiler's
# standard end marker, and a return. No helper shifts any existing hot address.
helper_instruction_count = 0
for index, (start, high, value) in enumerate(HELPERS):
    end = HELPERS[index + 1][0] if index + 1 < len(HELPERS) else 0x9B176
    instructions = []
    address = start
    while address < end:
        instruction = candidate_map[address]
        instructions.append(instruction)
        address += instruction.size
    assert address == end
    assert len(instructions) == 4
    assert instruction_signature(instructions[0]) == (
        "mov", "dword ptr [edi + 0x2620], 0", bytes.fromhex(
            "c7 87 20 26 00 00 00 00 00 00"))
    assert instruction_signature(instructions[1]) == (
        "mov", f"dword ptr [edi + 0x2624], {hex(high)}",
        b"\xc7\x87\x24\x26\x00\x00" + struct.pack("<I", high))
    assert instruction_signature(instructions[2]) == (
        "mov", "ebp, 0x646f6e65", bytes.fromhex("bd 65 6e 6f 64"))
    assert instruction_signature(instructions[3]) == ("ret", "", b"\xc3")
    helper_instruction_count += len(instructions)

append_targets = []
for instruction in candidate_map.values():
    target = direct_target(instruction)
    if target is not None and APPEND_START <= target < 0x9B176:
        append_targets.append((instruction.address, instruction.mnemonic, target))
assert append_targets == [
    (address, "call", CALL_TARGETS[address]) for address in sorted(CALL_TARGETS)
]
assert {target for _, _, target in append_targets} == {
    start for start, _, _ in HELPERS
}

result = {
    "schema": 1,
    "task": 218,
    "status": "pass",
    "accepted_sha256": sha256(accepted),
    "candidate_sha256": sha256(candidate),
    "accepted_executable_size": len(accepted),
    "candidate_executable_size": len(candidate),
    "code_start": candidate_header["code_start"],
    "accepted_code_end": accepted_header["physical_end"],
    "candidate_code_end": candidate_header["physical_end"],
    "code_growth_bytes": 156,
    "package_suffix_shift_exact": True,
    "preexisting_instruction_addresses_preserved": True,
    "preexisting_instruction_encodings_preserved_except_call_rel32": True,
    "hot_call_sites": len(CALL_TARGETS),
    "hot_call_offsets": [hex(address) for address in sorted(CALL_TARGETS)],
    "accepted_call_target": hex(INT_TO_F),
    "changed_existing_code_bytes": len(changed_existing_bytes),
    "unexpected_changed_existing_code_bytes": 0,
    "append_start": hex(APPEND_START),
    "helpers": [
        {"value": value, "offset": hex(start), "high_word": hex(high)}
        for start, high, value in HELPERS
    ],
    "helper_count": len(HELPERS),
    "helper_instruction_count": helper_instruction_count,
    "helper_generated_shape_exact": True,
    "appendix_direct_entries": len(append_targets),
    "appendix_direct_entries_all_explicit_calls": True,
    "prior_unreachable_padding_preserved": True,
    "compiler_alignment_padding_relocated": True,
    "source_boundary": "shared Lino only",
}
OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
