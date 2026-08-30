from pathlib import Path
import hashlib
import json
import random
import runpy
import struct

from capstone import (
    Cs, CS_ARCH_X86, CS_GRP_CALL, CS_GRP_JUMP, CS_MODE_32,
)
from capstone.x86_const import X86_OP_IMM, X86_OP_MEM, X86_OP_REG

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/gray-split-mul128-20260830"
ACCEPTED_EXE = EVIDENCE / "accepted/vhgame.exe"
CANDIDATE_EXE = EVIDENCE / "candidate/vhgame.exe"
ACCEPTED_FP = EVIDENCE / "accepted/fpsoft.txt"
CANDIDATE_FP = EVIDENCE / "candidate/fpsoft.txt"
OUTPUT = EVIDENCE / "production-layout.json"
EXPECTED_ACCEPTED_EXE_SHA256 = (
    "e18e8eb45ac0bc03aa2ee1f51ce1ae54f6ee00a0e8a7cef24cbd3adebcdf32a0")
EXPECTED_CANDIDATE_EXE_SHA256 = (
    "78dcfbc1b503494414f393f7d3b691be2f326424a42a7ae9a696d4823bb99861")
EXPECTED_ACCEPTED_FP_SHA256 = (
    "063ecf40b0faab3b2779d8ff159b8fa815eec7b397de0d47e68223841e2a59cc")
EXPECTED_CANDIDATE_FP_SHA256 = (
    "a2f22335d2473c10b3afe6e15c7aa0bf95380f71f8ab8267445747be6f01be61")
EXPECTED_VHGAME_SOURCE_SHA256 = (
    "f1af20ebd55b80e3a1439b0e30f1bb4e0bdcc8e00b7aced1a7b34d7395d3dc25")
EXPECTED_COMPILER_SHA256 = (
    "cfb39efc611dc96eab47f24c70cc7447a11f3b7cd874c49bfeb4934a42e67e87")
EXPECTED_CPU_PACK_SHA256 = (
    "1dd1433597c42e30b13bd55bfd02c19ebe465f3e020e4878906f66e7bfcdc4b7")
EXPECTED_FPX87_SHA256 = (
    "21060049f054523d64518c71ffb6da54caaea2912c3ec834f5d21112d19a6eb3")

GROWTH = 0xCC
XMUL32U = 0x23A2B
XMUL32U_SPLIT = 0x23A6D
MUL128 = 0x23B50
ACCEPTED_CARRY = 0x23C24
ACCEPTED_MUL128_END = 0x23CD8
CANDIDATE_CARRY = 0x23CF0
CANDIDATE_MUL128_END = 0x23DA4
ACCEPTED_PUBLIC_FMUL = 0x27EDD
CANDIDATE_PUBLIC_FMUL = ACCEPTED_PUBLIC_FMUL + GROWTH

WORKSPACE = {
    "XMH": 0x2680,
    "XML": 0x2684,
    "YMH": 0x2690,
    "YML": 0x2694,
    "xa0": 0x26B0,
    "xa1": 0x26B4,
    "xb0": 0x26B8,
    "xb1": 0x26BC,
    "xc0": 0x26C0,
    "xc1": 0x26C4,
    "xd0": 0x26C8,
    "xd1": 0x26CC,
    "xp0": 0x26D0,
    "xp1": 0x26D4,
    "xp2": 0x26D8,
    "xp3": 0x26DC,
    "xcy": 0x26E0,
    "xua": 0x26E4,
    "xub": 0x26E8,
    "xulo": 0x26EC,
    "xuhi": 0x26F0,
    "xul0": 0x26F4,
    "xuh0": 0x26F8,
    "xul1": 0x26FC,
    "xuh1": 0x2700,
    "xup0": 0x2704,
    "xup1": 0x2708,
    "xup2": 0x270C,
    "xup3": 0x2710,
    "xumid": 0x2714,
    "xutmp": 0x2718,
}

# The Lino package has twelve pre-code physical-offset fields for generated
# locations. Each location is downstream of Mul128 and therefore moves by the
# exact helper growth. They are not instruction-entry claims.
PRE_CODE_RELOCATIONS = (
    0xCF10, 0xCF50, 0xCF9C, 0xCFE8, 0xD040, 0xD080,
    0xD0C0, 0xD108, 0xD150, 0xD19C, 0xD1D8, 0xD21C,
)

# Five generated initializers publish physical code locations as immediate
# values. Their instructions and destinations are otherwise exact.
POINTER_INITIALIZERS = {
    0x785D9: (0x36BF8, 0x5F4D2),
    0x785E3: (0x36BFC, 0x5F4D8),
    0x785ED: (0x36C08, 0x5F777),
    0x785F7: (0x36C00, 0x5F77D),
    0x78601: (0x36C04, 0x5F7A3),
}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def digest(path):
    return sha256(path.read_bytes())


def u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def put_u32(data, offset, value):
    struct.pack_into("<I", data, offset, value)


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


def shape(items):
    return [(item.mnemonic, item.op_str) for item in items]


def direct_target(instruction):
    if not (instruction.group(CS_GRP_CALL) or instruction.group(CS_GRP_JUMP)):
        return None
    immediate = [operand.imm for operand in instruction.operands
                 if operand.type == X86_OP_IMM]
    assert len(immediate) <= 1
    return immediate[0] & 0xFFFFFFFF if immediate else None


def assignment(source, destination):
    return [
        ("mov", f"ebp, dword ptr [edi + 0x{source:x}]"),
        ("mov", f"dword ptr [edi + 0x{destination:x}], ebp"),
    ]


def extraction(source, low, high):
    return [
        ("mov", f"eax, dword ptr [edi + 0x{source:x}]"),
        ("movzx", "eax, ax"),
        ("mov", f"dword ptr [edi + 0x{low:x}], eax"),
        ("mov", f"eax, dword ptr [edi + 0x{source:x}]"),
        ("shr", "eax, 0x10"),
        ("movzx", "eax, ax"),
        ("mov", f"dword ptr [edi + 0x{high:x}], eax"),
    ]


def normalize_candidate_target(target):
    if target < MUL128:
        return target
    if target == MUL128:
        return target
    assert target >= CANDIDATE_MUL128_END
    return target - GROWTH


def read_register(registers, instruction, register_id):
    name = instruction.reg_name(register_id)
    if name in registers:
        return registers[name]
    if name == "ax":
        return registers["eax"] & 0xFFFF
    raise AssertionError(f"unsupported register read: {name}")


def write_register(registers, instruction, register_id, value):
    name = instruction.reg_name(register_id)
    if name in registers:
        registers[name] = value & 0xFFFFFFFF
        return
    raise AssertionError(f"unsupported register write: {name}")


def memory_address(registers, instruction, operand):
    memory = operand.mem
    base = read_register(registers, instruction, memory.base) if memory.base else 0
    index = read_register(registers, instruction, memory.index) if memory.index else 0
    return (base + index * memory.scale + memory.disp) & 0xFFFFFFFF


def read_operand(registers, memory, instruction, operand):
    if operand.type == X86_OP_REG:
        return read_register(registers, instruction, operand.reg)
    if operand.type == X86_OP_IMM:
        return operand.imm & 0xFFFFFFFF
    if operand.type == X86_OP_MEM:
        assert operand.size == 4
        return memory.get(memory_address(registers, instruction, operand), 0)
    raise AssertionError(f"unsupported operand read: {instruction}")


def write_operand(registers, memory, instruction, operand, value):
    if operand.type == X86_OP_REG:
        write_register(registers, instruction, operand.reg, value)
        return
    if operand.type == X86_OP_MEM:
        assert operand.size == 4
        memory[memory_address(registers, instruction, operand)] = value & 0xFFFFFFFF
        return
    raise AssertionError(f"unsupported operand write: {instruction}")


def emulate_mul128(instruction_map, entry, initial_registers, initial_memory,
                   initial_cf):
    registers = dict(initial_registers)
    memory = dict(initial_memory)
    carry = bool(initial_cf)
    call_depth = 0
    pc = entry
    steps = 0
    while True:
        steps += 1
        assert steps < 1_000
        instruction = instruction_map[pc]
        operands = instruction.operands
        next_pc = instruction.address + instruction.size
        mnemonic = instruction.mnemonic
        if mnemonic == "mov":
            write_operand(registers, memory, instruction, operands[0],
                          read_operand(registers, memory, instruction, operands[1]))
        elif mnemonic == "movzx":
            assert operands[1].size == 2
            value = read_operand(registers, memory, instruction, operands[1]) & 0xFFFF
            write_operand(registers, memory, instruction, operands[0], value)
        elif mnemonic in ("shr", "shl"):
            value = read_operand(registers, memory, instruction, operands[0])
            count = read_operand(registers, memory, instruction, operands[1]) & 31
            if count:
                if mnemonic == "shr":
                    carry = bool((value >> (count - 1)) & 1)
                    value >>= count
                else:
                    carry = bool((value >> (32 - count)) & 1)
                    value = (value << count) & 0xFFFFFFFF
            write_operand(registers, memory, instruction, operands[0], value)
        elif mnemonic == "add":
            left = read_operand(registers, memory, instruction, operands[0])
            right = read_operand(registers, memory, instruction, operands[1])
            total = left + right
            carry = total > 0xFFFFFFFF
            write_operand(registers, memory, instruction, operands[0], total)
        elif mnemonic == "or":
            value = (read_operand(registers, memory, instruction, operands[0])
                     | read_operand(registers, memory, instruction, operands[1]))
            carry = False
            write_operand(registers, memory, instruction, operands[0], value)
        elif mnemonic == "cmp":
            left = read_operand(registers, memory, instruction, operands[0])
            right = read_operand(registers, memory, instruction, operands[1])
            carry = left < right
        elif mnemonic == "mul":
            left = registers["eax"]
            right = read_operand(registers, memory, instruction, operands[0])
            product = left * right
            registers["eax"] = product & 0xFFFFFFFF
            registers["edx"] = product >> 32
            carry = registers["edx"] != 0
        elif mnemonic == "push":
            registers["esp"] = (registers["esp"] - 4) & 0xFFFFFFFF
            memory[registers["esp"]] = read_operand(
                registers, memory, instruction, operands[0])
        elif mnemonic == "pop":
            value = memory[registers["esp"]]
            write_operand(registers, memory, instruction, operands[0], value)
            registers["esp"] = (registers["esp"] + 4) & 0xFFFFFFFF
        elif mnemonic == "call":
            target = direct_target(instruction)
            assert target is not None
            registers["esp"] = (registers["esp"] - 4) & 0xFFFFFFFF
            memory[registers["esp"]] = next_pc
            call_depth += 1
            pc = target
            continue
        elif mnemonic == "jae":
            if not carry:
                target = direct_target(instruction)
                assert target is not None
                pc = target
                continue
        elif mnemonic == "ret":
            if call_depth == 0:
                break
            pc = memory[registers["esp"]]
            registers["esp"] = (registers["esp"] + 4) & 0xFFFFFFFF
            call_depth -= 1
            continue
        else:
            raise AssertionError(
                f"unsupported emulated instruction {instruction.address:#x}: "
                f"{instruction.mnemonic} {instruction.op_str}")
        pc = next_pc
    assert call_depth == 0
    return registers, memory, carry, steps


ENGINE = Cs(CS_ARCH_X86, CS_MODE_32)
ENGINE.detail = True
accepted = ACCEPTED_EXE.read_bytes()
candidate = CANDIDATE_EXE.read_bytes()
accepted_fp = ACCEPTED_FP.read_bytes()
candidate_fp = CANDIDATE_FP.read_bytes()
assert sha256(accepted) == EXPECTED_ACCEPTED_EXE_SHA256
assert sha256(candidate) == EXPECTED_CANDIDATE_EXE_SHA256
assert sha256(accepted_fp) == EXPECTED_ACCEPTED_FP_SHA256
assert sha256(candidate_fp) == EXPECTED_CANDIDATE_FP_SHA256
assert len(accepted) == 645_966
assert len(candidate) == 646_170
assert len(candidate) - len(accepted) == GROWTH
assert (ROOT / "work/fp/fpsoft.txt").read_bytes() == candidate_fp
assert (ROOT / "work/vhgame.exe").read_bytes() == candidate
assert digest(ROOT / "work/vhgame.txt") == EXPECTED_VHGAME_SOURCE_SHA256
assert digest(ROOT / "main/lib/gen/compiler114m.exe") == EXPECTED_COMPILER_SHA256
assert digest(ROOT / "main/cpu/i386m.bin") == EXPECTED_CPU_PACK_SHA256
assert digest(ROOT / "work/fp/fpx87.txt") == EXPECTED_FPX87_SHA256
transform = runpy.run_path(str(EVIDENCE / "apply_candidate.py"))["transform"]
assert candidate_fp == transform(accepted_fp)

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
    "code_units": 133_132,
    "code_entry_units": 96_605,
    "physical_end": 0x9B1A8,
    "code_start": 0x19178,
    "code_entry": 0x776EC,
}
assert candidate_header["code_units"] - accepted_header["code_units"] == GROWTH // 4
assert candidate_header["code_entry_units"] - accepted_header["code_entry_units"] == GROWTH // 4
assert candidate_header["physical_end"] - accepted_header["physical_end"] == GROWTH
assert candidate_header["code_start"] == accepted_header["code_start"]
assert candidate_header["code_entry"] - accepted_header["code_entry"] == GROWTH
assert (len(accepted) - accepted_header["physical_end"]
        == len(candidate) - candidate_header["physical_end"] == 10_866)

# Normalize only the three documented header fields and the twelve documented
# pre-code physical offsets. This accounts for every pre-code changed byte.
normalized_prefix = bytearray(candidate[:accepted_header["code_start"]])
header_fields = (
    accepted_header["marker"] + 0x34,
    accepted_header["marker"] + 0x38,
    accepted_header["marker"] + 0x40,
)
for offset in header_fields:
    put_u32(normalized_prefix, offset, u32(accepted, offset))
for offset in PRE_CODE_RELOCATIONS:
    assert u32(candidate, offset) == u32(accepted, offset) + GROWTH
    assert ACCEPTED_MUL128_END <= u32(accepted, offset) < accepted_header["physical_end"]
    put_u32(normalized_prefix, offset, u32(accepted, offset))
assert bytes(normalized_prefix) == accepted[:accepted_header["code_start"]]
pre_code_changed_byte_values = sum(
    left != right for left, right in zip(
        accepted[:accepted_header["code_start"]],
        candidate[:candidate_header["code_start"]]))
assert pre_code_changed_byte_values == 26

# No code before the multiply helper moved or changed. This closes the only
# generated-code interval not covered by the helper and downstream comparisons.
pre_helper_code_bytes = XMUL32U - accepted_header["code_start"]
assert pre_helper_code_bytes == 43_187
assert accepted[accepted_header["code_start"]:XMUL32U] == candidate[
    candidate_header["code_start"]:XMUL32U]

accepted_code = instructions(
    accepted, accepted_header["code_start"], accepted_header["physical_end"])
candidate_code = instructions(
    candidate, candidate_header["code_start"], candidate_header["physical_end"])
assert len(accepted_code) == 93_581
assert len(candidate_code) == 93_621
assert len(candidate_code) - len(accepted_code) == 40
accepted_map = {item.address: item for item in accepted_code}
candidate_map = {item.address: item for item in candidate_code}

# The complete ordinary XMul32u entry, extraction prefix, shared suffix, and
# return are byte-exact. The new split label is the existing suffix boundary.
assert accepted[XMUL32U:MUL128] == candidate[XMUL32U:MUL128]
accepted_prefix = instructions(accepted, XMUL32U, XMUL32U_SPLIT)
candidate_prefix = instructions(candidate, XMUL32U, XMUL32U_SPLIT)
accepted_suffix = instructions(accepted, XMUL32U_SPLIT, MUL128)
candidate_suffix = instructions(candidate, XMUL32U_SPLIT, MUL128)
assert shape(accepted_prefix) == shape(candidate_prefix)
assert shape(accepted_suffix) == shape(candidate_suffix)
assert len(candidate_prefix) == 14
assert len(candidate_suffix) == 52
assert candidate_map[XMUL32U].mnemonic == "mov"
assert candidate_map[XMUL32U].op_str == "eax, dword ptr [edi + 0x26e4]"
assert candidate_map[XMUL32U_SPLIT].mnemonic == "mov"
assert candidate_map[XMUL32U_SPLIT].op_str == "eax, dword ptr [edi + 0x26f4]"
assert candidate_map[XMUL32U_SPLIT - 6].address + candidate_map[XMUL32U_SPLIT - 6].size == XMUL32U_SPLIT
suffix_muls = [item for item in candidate_suffix if item.mnemonic == "mul"]
assert [item.op_str for item in suffix_muls] == [
    "dword ptr [edi + 0x26fc]",
    "dword ptr [edi + 0x2700]",
    "dword ptr [edi + 0x26fc]",
    "dword ptr [edi + 0x2700]",
]
assert candidate_suffix[-2].mnemonic == "mov"
assert candidate_suffix[-2].op_str == "ebp, 0x646f6e65"
assert candidate_suffix[-1].mnemonic == "ret"

# Assert the complete accepted a,b,c,d calling schedule rather than inferring it
# from call counts alone.
accepted_schedule_expected = []
for left, right, low, high in (
        (WORKSPACE["XML"], WORKSPACE["YML"], WORKSPACE["xa0"], WORKSPACE["xa1"]),
        (WORKSPACE["XML"], WORKSPACE["YMH"], WORKSPACE["xb0"], WORKSPACE["xb1"]),
        (WORKSPACE["XMH"], WORKSPACE["YML"], WORKSPACE["xc0"], WORKSPACE["xc1"]),
        (WORKSPACE["XMH"], WORKSPACE["YMH"], WORKSPACE["xd0"], WORKSPACE["xd1"])):
    accepted_schedule_expected += assignment(left, WORKSPACE["xua"])
    accepted_schedule_expected += assignment(right, WORKSPACE["xub"])
    accepted_schedule_expected.append(("call", hex(XMUL32U)))
    accepted_schedule_expected += assignment(WORKSPACE["xulo"], low)
    accepted_schedule_expected += assignment(WORKSPACE["xuhi"], high)
accepted_schedule = instructions(accepted, MUL128, ACCEPTED_CARRY)
assert len(accepted_schedule) == 36
assert shape(accepted_schedule) == accepted_schedule_expected

# Assert the complete candidate b,a,c,d Gray schedule, including the temporary b
# image, canonical b restoration, and final accepted xua:xub operand image.
candidate_schedule_expected = []
for source, low, high in (
        (WORKSPACE["XML"], WORKSPACE["xa0"], WORKSPACE["xa1"]),
        (WORKSPACE["YMH"], WORKSPACE["xb0"], WORKSPACE["xb1"]),
        (WORKSPACE["YML"], WORKSPACE["xc0"], WORKSPACE["xc1"]),
        (WORKSPACE["XMH"], WORKSPACE["xd0"], WORKSPACE["xd1"])):
    candidate_schedule_expected += extraction(source, low, high)
candidate_schedule_expected += assignment(WORKSPACE["xa0"], WORKSPACE["xul0"])
candidate_schedule_expected += assignment(WORKSPACE["xa1"], WORKSPACE["xuh0"])
candidate_schedule_expected += assignment(WORKSPACE["xb0"], WORKSPACE["xul1"])
candidate_schedule_expected += assignment(WORKSPACE["xb1"], WORKSPACE["xuh1"])
candidate_schedule_expected.append(("call", hex(XMUL32U_SPLIT)))
candidate_schedule_expected += assignment(WORKSPACE["xulo"], WORKSPACE["xua"])
candidate_schedule_expected += assignment(WORKSPACE["xuhi"], WORKSPACE["xub"])
candidate_schedule_expected += assignment(WORKSPACE["xc0"], WORKSPACE["xul1"])
candidate_schedule_expected += assignment(WORKSPACE["xc1"], WORKSPACE["xuh1"])
candidate_schedule_expected.append(("call", hex(XMUL32U_SPLIT)))
candidate_schedule_expected += assignment(WORKSPACE["xulo"], WORKSPACE["xa0"])
candidate_schedule_expected += assignment(WORKSPACE["xuhi"], WORKSPACE["xa1"])
candidate_schedule_expected += assignment(WORKSPACE["xd0"], WORKSPACE["xul0"])
candidate_schedule_expected += assignment(WORKSPACE["xd1"], WORKSPACE["xuh0"])
candidate_schedule_expected.append(("call", hex(XMUL32U_SPLIT)))
candidate_schedule_expected += assignment(WORKSPACE["xulo"], WORKSPACE["xc0"])
candidate_schedule_expected += assignment(WORKSPACE["xuhi"], WORKSPACE["xc1"])
candidate_schedule_expected += assignment(WORKSPACE["xb0"], WORKSPACE["xul1"])
candidate_schedule_expected += assignment(WORKSPACE["xb1"], WORKSPACE["xuh1"])
candidate_schedule_expected.append(("call", hex(XMUL32U_SPLIT)))
candidate_schedule_expected += assignment(WORKSPACE["xulo"], WORKSPACE["xd0"])
candidate_schedule_expected += assignment(WORKSPACE["xuhi"], WORKSPACE["xd1"])
candidate_schedule_expected += assignment(WORKSPACE["xua"], WORKSPACE["xb0"])
candidate_schedule_expected += assignment(WORKSPACE["xub"], WORKSPACE["xb1"])
candidate_schedule_expected += assignment(WORKSPACE["XMH"], WORKSPACE["xua"])
candidate_schedule_expected += assignment(WORKSPACE["YMH"], WORKSPACE["xub"])
candidate_schedule = instructions(candidate, MUL128, CANDIDATE_CARRY)
assert len(candidate_schedule) == 76
assert shape(candidate_schedule) == candidate_schedule_expected
candidate_split_calls = [item for item in candidate_schedule if item.mnemonic == "call"]
assert [(item.address, direct_target(item)) for item in candidate_split_calls] == [
    (0x23C04, XMUL32U_SPLIT),
    (0x23C39, XMUL32U_SPLIT),
    (0x23C6E, XMUL32U_SPLIT),
    (0x23CA3, XMUL32U_SPLIT),
]

# The compiler lowers each low-half mask to MOVZX and each high-half extraction
# to SHR+MOVZX. Accepted Mul128 executes the six extraction ALU instructions in
# the ordinary prefix four times; candidate Mul128 executes twelve once-only
# extraction ALU instructions and bypasses the prefix on all four suffix calls.
prefix_extraction_alu = sum(
    item.mnemonic in ("movzx", "shr") for item in candidate_prefix)
candidate_extraction_alu = sum(
    item.mnemonic in ("movzx", "shr") for item in candidate_schedule)
assert prefix_extraction_alu == 6
assert candidate_extraction_alu == 12
accepted_dynamic_extraction_alu = len(accepted_schedule) // 9 * prefix_extraction_alu
assert accepted_dynamic_extraction_alu == 24
assert len(candidate_split_calls) * len(suffix_muls) == 16
assert len([item for item in accepted_schedule if item.mnemonic == "call"]) * len(suffix_muls) == 16

# The complete accepted carry/reconstruction continuation is byte-exact at the
# relocation delta, including all internal branch displacements and the return.
assert ACCEPTED_MUL128_END - ACCEPTED_CARRY == CANDIDATE_MUL128_END - CANDIDATE_CARRY == 180
assert accepted[ACCEPTED_CARRY:ACCEPTED_MUL128_END] == candidate[
    CANDIDATE_CARRY:CANDIDATE_MUL128_END]
accepted_carry = instructions(accepted, ACCEPTED_CARRY, ACCEPTED_MUL128_END)
candidate_carry = instructions(candidate, CANDIDATE_CARRY, CANDIDATE_MUL128_END)
assert len(accepted_carry) == len(candidate_carry) == 39
assert all(new.address == old.address + GROWTH
           for old, new in zip(accepted_carry, candidate_carry))
assert candidate_carry[-1].mnemonic == "ret"

# Only the intended four calls enter the split suffix. XMul32u's ordinary entry
# remains an exact boundary (currently with no live generated direct caller), and
# XMulCore is the sole external direct caller of Mul128.
external_xmul_entries = []
external_mul128_entries = []
for item in candidate_code:
    target = direct_target(item)
    if target is None:
        continue
    if not (XMUL32U <= item.address < MUL128) and XMUL32U <= target < MUL128:
        external_xmul_entries.append((item.address, item.mnemonic, target))
    if (not (MUL128 <= item.address < CANDIDATE_MUL128_END)
            and MUL128 <= target < CANDIDATE_MUL128_END):
        external_mul128_entries.append((item.address, item.mnemonic, target))
assert external_xmul_entries == [
    (0x23C04, "call", XMUL32U_SPLIT),
    (0x23C39, "call", XMUL32U_SPLIT),
    (0x23C6E, "call", XMUL32U_SPLIT),
    (0x23CA3, "call", XMUL32U_SPLIT),
]
assert external_mul128_entries == [(0x23DD1, "call", MUL128)]
assert sum(direct_target(item) == XMUL32U for item in candidate_code) == 0
assert sum(direct_target(item) == XMUL32U_SPLIT for item in candidate_code) == 4
assert sum(direct_target(item) == MUL128 for item in candidate_code) == 1
assert all(item.mnemonic != "call" or direct_target(item) is not None
           for item in candidate_schedule)

# Bridge the source-level symbolic schedule proof to the actual generated x86.
# A focused interpreter executes the accepted and candidate helper bytes from
# arbitrary A-E/EBP/flag images and arbitrary initialized multiply workspace.
# EDI and ESP vary over separated valid base/stack regions. Every physical
# register, terminal flag, and declared multiply word must agree at return.
accepted_helper = instructions(accepted, XMUL32U, ACCEPTED_MUL128_END)
candidate_helper = instructions(candidate, XMUL32U, CANDIDATE_MUL128_END)
for helper in (accepted_helper, candidate_helper):
    written = {
        item.reg_name(register)
        for item in helper
        for register in item.regs_access()[1]
    }
    assert "ecx" not in written
    assert "edi" not in written
candidate_helper_indirect_transfers = [
    item.address for item in candidate_helper
    if (item.group(CS_GRP_CALL) or item.group(CS_GRP_JUMP))
    and direct_target(item) is None
]
assert candidate_helper_indirect_transfers == []

rng = random.Random(0x2296A7)
directed_words = (
    0, 1, 0xFFFF, 0x10000, 0x10001,
    0x7FFFFFFF, 0x80000000, 0xFFFFFFFE, 0xFFFFFFFF,
)
machine_cases = []
for index in range(256):
    machine_cases.append((
        directed_words[index % len(directed_words)],
        directed_words[(index // len(directed_words)) % len(directed_words)],
        directed_words[(index * 5 + 1) % len(directed_words)],
        directed_words[(index * 7 + 3) % len(directed_words)],
    ))
for _ in range(4_096):
    machine_cases.append(tuple(rng.randrange(1 << 32) for _ in range(4)))

physical_registers = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
max_accepted_steps = 0
max_candidate_steps = 0
for case_index, (xml, xmh, yml, ymh) in enumerate(machine_cases):
    data_base = 0x10000000 + (case_index % 256) * 0x10000
    stack_base = 0x70000000 - (case_index % 256) * 0x10000
    initial_registers = {
        name: rng.randrange(1 << 32) for name in physical_registers
    }
    initial_registers["edi"] = data_base
    initial_registers["esp"] = stack_base
    initial_memory = {
        (data_base + offset) & 0xFFFFFFFF: rng.randrange(1 << 32)
        for offset in WORKSPACE.values()
    }
    for name, value in (("XML", xml), ("XMH", xmh), ("YML", yml), ("YMH", ymh)):
        initial_memory[data_base + WORKSPACE[name]] = value
    initial_cf = bool(rng.randrange(2))
    old_registers, old_memory, old_cf, old_steps = emulate_mul128(
        accepted_map, MUL128, initial_registers, initial_memory, initial_cf)
    new_registers, new_memory, new_cf, new_steps = emulate_mul128(
        candidate_map, MUL128, initial_registers, initial_memory, initial_cf)
    max_accepted_steps = max(max_accepted_steps, old_steps)
    max_candidate_steps = max(max_candidate_steps, new_steps)
    assert old_registers == new_registers
    assert old_cf == new_cf
    for offset in WORKSPACE.values():
        address = data_base + offset
        assert old_memory[address] == new_memory[address]
    expected_product = (((xmh << 32) | xml) * ((ymh << 32) | yml)) & ((1 << 128) - 1)
    product = sum(
        old_memory[data_base + WORKSPACE[name]] << shift
        for name, shift in (("xp0", 0), ("xp1", 32), ("xp2", 64), ("xp3", 96)))
    assert product == expected_product
    assert old_registers["eax"] == old_memory[data_base + WORKSPACE["xp3"]]
    assert old_registers["ebx"] == old_registers["esi"] == old_memory[
        data_base + WORKSPACE["xcy"]]
    assert old_registers["ecx"] == initial_registers["ecx"]
    assert old_registers["edx"] <= 2
    assert old_registers["edi"] == data_base
    assert old_registers["ebp"] == 0x646F6E65
    assert old_registers["esp"] == stack_base

all_candidate_indirect_transfers = [
    (item.address, item.mnemonic, item.op_str) for item in candidate_code
    if (item.group(CS_GRP_CALL) or item.group(CS_GRP_JUMP))
    and direct_target(item) is None
]

# Everything after the grown helper has exactly one accepted logical
# instruction. Normalize direct targets by the one relocation delta, and admit
# only the five explicitly source-shaped physical-pointer initializers.
accepted_downstream = instructions(
    accepted, ACCEPTED_MUL128_END, accepted_header["physical_end"])
candidate_downstream = instructions(
    candidate, CANDIDATE_MUL128_END, candidate_header["physical_end"])
assert len(accepted_downstream) == len(candidate_downstream) == 86_301
raw_changed_downstream_instructions = 0
raw_changed_downstream_calls = 0
relocated_pointer_initializers = []
for old, new in zip(accepted_downstream, candidate_downstream):
    assert new.address == old.address + GROWTH
    assert new.mnemonic == old.mnemonic
    assert new.size == old.size
    old_target = direct_target(old)
    new_target = direct_target(new)
    if old_target is not None:
        assert new_target is not None
        assert normalize_candidate_target(new_target) == old_target
    else:
        assert new_target is None
        if new.op_str != old.op_str:
            assert old.address in POINTER_INITIALIZERS
            destination, value = POINTER_INITIALIZERS[old.address]
            assert old.mnemonic == new.mnemonic == "mov"
            assert old.op_str == f"dword ptr [edi + 0x{destination:x}], {hex(value)}"
            assert new.op_str == (
                f"dword ptr [edi + 0x{destination:x}], {hex(value + GROWTH)}")
            relocated_pointer_initializers.append(old.address)
    if old.bytes != new.bytes:
        raw_changed_downstream_instructions += 1
        if old.mnemonic == "call":
            raw_changed_downstream_calls += 1
assert relocated_pointer_initializers == list(POINTER_INITIALIZERS)
assert raw_changed_downstream_instructions == 325
assert raw_changed_downstream_calls == 320
aligned_downstream_changed_byte_values = sum(
    left != right for left, right in zip(
        accepted[ACCEPTED_MUL128_END:accepted_header["physical_end"]],
        candidate[CANDIDATE_MUL128_END:candidate_header["physical_end"]]))
assert aligned_downstream_changed_byte_values == 578

# The non-code package payload is bit-exact after its one physical relocation.
assert accepted[accepted_header["physical_end"]:] == candidate[
    candidate_header["physical_end"]:]

# Public FMul is among the normalized downstream instructions. Its pushal/call/
# popal boundary remains exact, preserving public A-E around the relocated but
# otherwise identical XScalarMul target.
accepted_fmul = instructions(accepted, ACCEPTED_PUBLIC_FMUL, ACCEPTED_PUBLIC_FMUL + 13)
candidate_fmul = instructions(candidate, CANDIDATE_PUBLIC_FMUL, CANDIDATE_PUBLIC_FMUL + 13)
assert shape(accepted_fmul) == [
    ("pushal", ""),
    ("call", "0x255f0"),
    ("popal", ""),
    ("mov", "ebp, 0x646f6e65"),
    ("ret", ""),
]
assert shape(candidate_fmul) == [
    ("pushal", ""),
    ("call", "0x256bc"),
    ("popal", ""),
    ("mov", "ebp, 0x646f6e65"),
    ("ret", ""),
]
assert direct_target(candidate_fmul[1]) - direct_target(accepted_fmul[1]) == GROWTH

model = json.loads((EVIDENCE / "model.json").read_text(encoding="utf-8"))
build = json.loads((EVIDENCE / "build.json").read_text(encoding="utf-8"))
assert model["status"] == "pass"
assert model["candidate_snapshot_equals_exact_transform"]
assert model["active_production"] == "candidate"
assert model["symbolic_all_input_schedule_equivalence"]
assert model["direct_unsigned_product_exact"]
assert model["canonical_a_b_c_d_exact"]
assert model["carry_tail_exact"]
assert model["terminal_high_high_helper_scratch_exact"]
assert model["source_terminal_a_through_e_exact"]
assert model["incoming_c_preserved"]
assert model["accepted_extraction_alu_operations_per_mul128"] == 24
assert model["candidate_extraction_alu_operations_per_mul128"] == 12
assert model["accepted_unsigned_16x16_products_per_mul128"] == 16
assert model["candidate_unsigned_16x16_products_per_mul128"] == 16
assert model["simulation_constants"] == [18206, 60000]
assert build["status"] == "pass"
assert build["private_inactive_desktop"]
assert not build["default_desktop"]
assert build["build_entry"] == "lino_build.ps1"
assert build["warnings"] == 64 and build["errors"] == 0
assert build["candidate_executable_sha256"] == EXPECTED_CANDIDATE_EXE_SHA256

result = {
    "schema": 1,
    "task": 229,
    "status": "pass",
    "accepted_sha256": sha256(accepted),
    "candidate_sha256": sha256(candidate),
    "accepted_executable_bytes": len(accepted),
    "candidate_executable_bytes": len(candidate),
    "generated_growth_bytes": GROWTH,
    "header_fields_changed": 3,
    "header_growth_units": GROWTH // 4,
    "code_start_exact": True,
    "entry_and_physical_end_relocated_bytes": GROWTH,
    "pre_code_physical_offset_fields_relocated": len(PRE_CODE_RELOCATIONS),
    "pre_code_changed_byte_values": pre_code_changed_byte_values,
    "pre_code_unexpected_changes": 0,
    "pre_helper_generated_code_bytes_checked_exact": pre_helper_code_bytes,
    "xmul32u_entry": hex(XMUL32U),
    "xmul32u_split_entry": hex(XMUL32U_SPLIT),
    "xmul32u_complete_generated_bytes_exact": True,
    "xmul32u_split_exact_instruction_boundary": True,
    "ordinary_xmul32u_generated_direct_callers": 0,
    "mul128_entry": hex(MUL128),
    "accepted_mul128_end": hex(ACCEPTED_MUL128_END),
    "candidate_mul128_end": hex(CANDIDATE_MUL128_END),
    "accepted_schedule_instructions": len(accepted_schedule),
    "candidate_schedule_instructions": len(candidate_schedule),
    "candidate_suffix_call_addresses": [hex(item.address) for item in candidate_split_calls],
    "candidate_suffix_calls_per_mul128": len(candidate_split_calls),
    "candidate_partial_product_order": ["b", "a", "c", "d"],
    "candidate_final_suffix_product": "d = XMH * YMH",
    "canonical_b_restored_before_terminal_xua_xub": True,
    "terminal_xua_xub_restored_to_xmh_ymh": True,
    "accepted_source_decompositions_per_mul128": 8,
    "candidate_source_decompositions_per_mul128": 4,
    "accepted_generated_extraction_alu_operations_per_mul128": accepted_dynamic_extraction_alu,
    "candidate_generated_extraction_alu_operations_per_mul128": candidate_extraction_alu,
    "accepted_dynamic_unsigned_16x16_products_per_mul128": 16,
    "candidate_dynamic_unsigned_16x16_products_per_mul128": 16,
    "carry_continuation_bytes": CANDIDATE_MUL128_END - CANDIDATE_CARRY,
    "carry_continuation_bytes_exact": True,
    "generated_machine_emulation_cases": len(machine_cases),
    "generated_machine_all_physical_registers_exact": True,
    "generated_machine_terminal_carry_flag_exact": True,
    "generated_machine_complete_workspace_exact": True,
    "generated_machine_direct_unsigned_product_exact": True,
    "generated_machine_incoming_ecx_preserved": True,
    "generated_machine_max_accepted_steps": max_accepted_steps,
    "generated_machine_max_candidate_steps": max_candidate_steps,
    "workspace_addresses": {name: hex(address) for name, address in WORKSPACE.items()},
    "workspace_addressing_unchanged": True,
    "external_direct_entries_to_xmul32u_split": len(external_xmul_entries),
    "external_direct_entries_to_mul128": len(external_mul128_entries),
    "external_direct_entries_to_unintended_helper_interiors": 0,
    "candidate_helper_indirect_call_jump_loop_transfers": len(
        candidate_helper_indirect_transfers),
    "whole_program_indirect_call_jump_loop_transfers_reported": len(
        all_candidate_indirect_transfers),
    "downstream_logical_instructions_compared": len(candidate_downstream),
    "downstream_logical_instruction_semantics_exact": True,
    "downstream_raw_changed_instructions_explained": raw_changed_downstream_instructions,
    "downstream_relocated_direct_calls": raw_changed_downstream_calls,
    "downstream_physical_pointer_initializers_relocated": len(relocated_pointer_initializers),
    "downstream_aligned_changed_byte_values": aligned_downstream_changed_byte_values,
    "downstream_unexpected_changes": 0,
    "non_code_payload_bytes": len(candidate) - candidate_header["physical_end"],
    "non_code_payload_exact_after_relocation": True,
    "public_fmul_pushal_call_popal_exact": True,
    "public_a_through_e_preserved": True,
    "package_relocation_normalization_complete": True,
    "unexpected_changes": 0,
    "active_production": "candidate",
    "source_exact_transform": True,
    "candidate_change_scope": "shared work/fp/fpsoft.txt Lino helper island only",
    "complete_shipping_dependency_closure_audited": False,
    "candidate_transform_raw_target_machine_blocks_added": False,
    "selected_compiler_artifact_matches_recorded_hash": True,
    "selected_cpu_pack_artifact_matches_recorded_hash": True,
    "verifier_sha256": digest(Path(__file__)),
}
OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
