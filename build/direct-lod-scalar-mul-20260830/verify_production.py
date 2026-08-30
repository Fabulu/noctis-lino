from pathlib import Path
import hashlib
import json
import struct

from capstone import Cs, CS_ARCH_X86, CS_MODE_32

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/direct-lod-scalar-mul-20260830"
ACCEPTED = EVIDENCE / "accepted/vhgame.exe"
CANDIDATE = EVIDENCE / "candidate/vhgame.exe"
OUTPUT = EVIDENCE / "production-layout.json"
EXPECTED_ACCEPTED_SHA256 = (
    "81900287fa9e19291a27667b0e23d5c0c6324e86e8b9d8da0ff82a65cc302823")
EXPECTED_CANDIDATE_SHA256 = (
    "948343858dfa58d163e0459f56b59c33ff731642af26bb2960a61ddcd6f1d3c1")
INT_TO_F = 0x2820D
F_MUL = 0x27EDD
SITES = (
    (0x7B04A, 250, 0x406F4000),
    (0x7B188, 100, 0x40590000),
    (0x7B239, 25, 0x40390000),
    (0x7B695, 250, 0x406F4000),
    (0x7B7C9, 100, 0x40590000),
    (0x7B875, 25, 0x40390000),
)
SITE_BYTES = 68


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
accepted = ACCEPTED.read_bytes()
candidate = CANDIDATE.read_bytes()
assert sha256(accepted) == EXPECTED_ACCEPTED_SHA256
assert sha256(candidate) == EXPECTED_CANDIDATE_SHA256
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

ranges = [(start, start + SITE_BYTES) for start, _, _ in SITES]
cursor = 0
for start, end in ranges:
    assert accepted[cursor:start] == candidate[cursor:start]
    cursor = end
assert accepted[cursor:] == candidate[cursor:]
differences = [
    offset for offset, (left, right) in enumerate(zip(accepted, candidate))
    if left != right
]
assert len(differences) == 330
assert all(any(start <= offset < end for start, end in ranges)
           for offset in differences)

accepted_code = instructions(
    accepted, expected_header["code_start"], expected_header["physical_end"])
candidate_code = instructions(
    candidate, expected_header["code_start"], expected_header["physical_end"])
assert len(accepted_code) == 93_575
assert len(candidate_code) == 93_569
accepted_map = {instruction.address: instruction for instruction in accepted_code}
candidate_map = {instruction.address: instruction for instruction in candidate_code}

site_details = []
for start, value, high in SITES:
    old = instructions(accepted, start, start + SITE_BYTES)
    new = instructions(candidate, start, start + SITE_BYTES)
    assert len(old) == 11
    assert len(new) == 10
    assert old[0].bytes == (
        bytes.fromhex("c7 87 50 26 00 00") + struct.pack("<I", value))
    assert old[0].op_str.startswith("dword ptr [edi + 0x2650], ")
    assert old[1].mnemonic == "call" and old[1].op_str == hex(INT_TO_F)
    assert [(item.mnemonic, item.op_str) for item in old[2:6]] == [
        ("mov", "ebp, dword ptr [edi + 0x2620]"),
        ("mov", "dword ptr [edi + 0x2628], ebp"),
        ("mov", "ebp, dword ptr [edi + 0x2624]"),
        ("mov", "dword ptr [edi + 0x262c], ebp"),
    ]
    assert [(item.mnemonic, item.op_str) for item in old[6:10]] == [
        ("mov", "ebp, dword ptr [edi + 0x7798]"),
        ("mov", "dword ptr [edi + 0x2620], ebp"),
        ("mov", "ebp, dword ptr [edi + 0x779c]"),
        ("mov", "dword ptr [edi + 0x2624], ebp"),
    ]
    assert old[10].mnemonic == "call" and old[10].op_str == hex(F_MUL)
    assert old[10].address == start + 63 and old[10].size == 5

    assert new[0].bytes == bytes.fromhex(
        "c7 87 28 26 00 00 00 00 00 00")
    assert new[0].op_str == "dword ptr [edi + 0x2628], 0"
    assert new[1].bytes == (
        bytes.fromhex("c7 87 2c 26 00 00") + struct.pack("<I", high))
    assert new[1].op_str == f"dword ptr [edi + 0x262c], {hex(high)}"
    assert [(item.mnemonic, item.op_str) for item in new[2:6]] == [
        ("mov", "ebp, dword ptr [edi + 0x7798]"),
        ("mov", "dword ptr [edi + 0x2620], ebp"),
        ("mov", "ebp, dword ptr [edi + 0x779c]"),
        ("mov", "dword ptr [edi + 0x2624], ebp"),
    ]
    assert new[6].bytes == bytes.fromhex("b8 8a 09 00 00")
    assert new[6].mnemonic == "mov" and new[6].op_str == "eax, 0x98a"
    assert new[7].bytes == bytes.fromhex("dd 87 20 26 00 00")
    assert new[7].mnemonic == "fld"
    assert new[7].op_str == "qword ptr [edi + 0x2620]"
    assert new[8].bytes == bytes.fromhex("dc 8c 87 00 00 00 00")
    assert new[8].mnemonic == "fmul"
    assert new[8].op_str == "qword ptr [edi + eax*4]"
    assert new[9].bytes == bytes.fromhex("dd 9f 20 26 00 00")
    assert new[9].mnemonic == "fstp"
    assert new[9].op_str == "qword ptr [edi + 0x2620]"
    assert new[-1].address + new[-1].size == start + SITE_BYTES

    # The common post-product stores, exact distance/limit reload, FCmp call,
    # and first FI observer begin at the same address and remain byte-exact.
    common = instructions(accepted, start + SITE_BYTES, start + SITE_BYTES + 83)
    assert accepted[start + SITE_BYTES:start + SITE_BYTES + 83] == candidate[
        start + SITE_BYTES:start + SITE_BYTES + 83]
    assert [(item.mnemonic, item.op_str) for item in common] == [
        ("mov", "ebp, dword ptr [edi + 0x2620]"),
        ("mov", "dword ptr [edi + 0x77a8], ebp"),
        ("mov", "ebp, dword ptr [edi + 0x2624]"),
        ("mov", "dword ptr [edi + 0x77ac], ebp"),
        ("mov", "ebp, dword ptr [edi + 0x77a0]"),
        ("mov", "dword ptr [edi + 0x2620], ebp"),
        ("mov", "ebp, dword ptr [edi + 0x77a4]"),
        ("mov", "dword ptr [edi + 0x2624], ebp"),
        ("mov", "ebp, dword ptr [edi + 0x77a8]"),
        ("mov", "dword ptr [edi + 0x2628], ebp"),
        ("mov", "ebp, dword ptr [edi + 0x77ac]"),
        ("mov", "dword ptr [edi + 0x262c], ebp"),
        ("call", "0x27f7e"),
        ("mov", "eax, dword ptr [edi + 0x2650]"),
    ]
    site_details.append({
        "offset": hex(start),
        "value": value,
        "accepted_instructions": len(old),
        "candidate_instructions": len(new),
        "bytes": SITE_BYTES,
    })

# Every byte outside the six islands is exact, so all common instructions and
# control edges are exact. Four existing gates enter the starts of the two
# 100x islands; no edge enters any transformed interior.
starts = {start for start, _, _ in SITES}
interiors = {address for start, end in ranges for address in range(start + 1, end)}
incoming_starts = []
for instruction in candidate_code:
    target = direct_target(instruction)
    if target in starts:
        incoming_starts.append((instruction.address, instruction.mnemonic, target))
    assert target not in interiors
assert incoming_starts == [
    (0x7B0E6, "jge", 0x7B188),
    (0x7B10F, "je", 0x7B188),
    (0x7B731, "jge", 0x7B7C9),
    (0x7B75A, "je", 0x7B7C9),
]

result = {
    "schema": 1,
    "task": 220,
    "status": "pass",
    "accepted_sha256": sha256(accepted),
    "candidate_sha256": sha256(candidate),
    "executable_size": len(candidate),
    "header_and_code_boundaries_exact": True,
    "package_bytes_outside_six_islands_exact": True,
    "changed_byte_values": len(differences),
    "replacement_sites": len(SITES),
    "site_bytes": SITE_BYTES,
    "site_endpoints_preserved": True,
    "accepted_site_instructions": 11,
    "candidate_site_instructions": 10,
    "generated_instructions_removed": 6,
    "int_to_f_calls_removed": 6,
    "portable_fmul_calls_removed": 6,
    "direct_x87_p64_spill_sequences": 6,
    "direct_sequence_shape_exact": True,
    "common_post_product_gate_bytes_exact": True,
    "external_direct_entries_to_site_starts": len(incoming_starts),
    "external_direct_entries_to_site_interiors": 0,
    "unexpected_changes": 0,
    "sites": site_details,
    "source_boundary": "shared Lino only",
}
OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
