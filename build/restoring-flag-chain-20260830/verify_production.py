from pathlib import Path
from collections import Counter
import hashlib
import json
import random
import runpy
import struct

from capstone import Cs, CS_ARCH_X86, CS_GRP_CALL, CS_GRP_JUMP, CS_MODE_32
from capstone.x86_const import X86_OP_IMM, X86_OP_MEM, X86_OP_REG

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/restoring-flag-chain-20260830"
ACCEPTED_EXE = EVIDENCE / "accepted/vhgame.exe"
CANDIDATE_EXE = EVIDENCE / "candidate/vhgame.exe"
OUTPUT = EVIDENCE / "production-layout.json"
MASK = 0xFFFFFFFF
ROOT_START = 0x256F1
RESTORING_LOOP = 0x25804
ISLAND_START = 0x258C5
ACCEPT_START = 0x258FD
ISLAND_END = 0x2599D
REJECT_TARGET = 0x259B9
ROOT_END = 0x25B49
WORKSPACE = {
    "sqcarry": 0x27C4,
    "srm0": 0x27CC,
    "srm1": 0x27D0,
    "srm2": 0x27D4,
}

apply = runpy.run_path(str(EVIDENCE / "apply_candidate.py"))
SCALAR_ISLAND = apply["SCALAR_ISLAND"]
CANDIDATE_ISLAND = apply["CANDIDATE_ISLAND"]
REACHABLE_CANDIDATE = apply["REACHABLE_CANDIDATE"]
EXPECTED_ACCEPTED_SHA256 = apply["ACCEPTED_GAME_SHA256"]
EXPECTED_CANDIDATE_SHA256 = (
    "2dd024c214a49c94fd19dd7f9832a98f6c252a3a1bdcf363de0fbb68c33385f6")
EXPECTED_CANDIDATE_COMPILER_SHA256 = (
    "78e862bd94cf80685e579e827cf5d46f2c5adfd5a437befc94396b370bfc9e35")

ENGINE = Cs(CS_ARCH_X86, CS_MODE_32)
ENGINE.detail = True


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def digest(path):
    return sha256(path.read_bytes())


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
    assert result and result[0].address == start
    assert result[-1].address + result[-1].size == end
    return result


def direct_target(instruction):
    if not (instruction.group(CS_GRP_CALL) or instruction.group(CS_GRP_JUMP)):
        return None
    immediate = [operand.imm for operand in instruction.operands
                 if operand.type == X86_OP_IMM]
    assert len(immediate) <= 1
    return immediate[0] & MASK if immediate else None


def parity_even_byte(value):
    return ((value & 0xFF).bit_count() & 1) == 0


def arithmetic_flags(left, right, carry, result, operation):
    left &= MASK
    right &= MASK
    result &= MASK
    if operation == "sub":
        full_right = right + carry
        cf = left < full_right
        # The standard SBB overflow relation uses the encoded source and the
        # carry-in-reflected result. No endpoint observes SBB's other flags here,
        # but keeping them makes the focused interpreter complete.
        of = bool((left ^ right) & (left ^ result) & 0x80000000)
    else:
        total = left + right + carry
        cf = total > MASK
        of = bool((~(left ^ right) & (left ^ result)) & 0x80000000)
    return {
        "CF": cf,
        "PF": parity_even_byte(result),
        "AF": bool((left ^ right ^ result) & 0x10),
        "ZF": result == 0,
        "SF": bool(result & 0x80000000),
        "OF": of,
    }


def emulate(instruction_map, initial_registers, initial_memory, initial_flags):
    registers = dict(initial_registers)
    memory = dict(initial_memory)
    flags = dict(initial_flags)
    writes = []
    pc = ISLAND_START
    steps = 0

    def read(operand):
        if operand.type == X86_OP_REG:
            return registers[ENGINE.reg_name(operand.reg)]
        if operand.type == X86_OP_IMM:
            return operand.imm & MASK
        assert operand.type == X86_OP_MEM
        base = ENGINE.reg_name(operand.mem.base)
        assert not operand.mem.index and operand.mem.scale == 1
        address = (registers[base] + operand.mem.disp) & MASK
        return memory[address]

    def write(operand, value):
        value &= MASK
        if operand.type == X86_OP_REG:
            registers[ENGINE.reg_name(operand.reg)] = value
            return
        assert operand.type == X86_OP_MEM
        base = ENGINE.reg_name(operand.mem.base)
        assert not operand.mem.index and operand.mem.scale == 1
        address = (registers[base] + operand.mem.disp) & MASK
        memory[address] = value
        writes.append((address, value))

    while pc not in (ISLAND_END, REJECT_TARGET):
        steps += 1
        assert steps < 100
        item = instruction_map[pc]
        operands = item.operands
        next_pc = item.address + item.size
        if item.mnemonic == "mov":
            write(operands[0], read(operands[1]))
        elif item.mnemonic == "cmp":
            left, right = read(operands[0]), read(operands[1])
            result = (left - right) & MASK
            flags = arithmetic_flags(left, right, 0, result, "sub")
        elif item.mnemonic in ("sub", "sbb"):
            left, right = read(operands[0]), read(operands[1])
            carry = int(flags["CF"]) if item.mnemonic == "sbb" else 0
            result = (left - right - carry) & MASK
            flags = arithmetic_flags(left, right, carry, result, "sub")
            write(operands[0], result)
        elif item.mnemonic == "adc":
            left, right = read(operands[0]), read(operands[1])
            carry = int(flags["CF"])
            result = (left + right + carry) & MASK
            flags = arithmetic_flags(left, right, carry, result, "add")
            write(operands[0], result)
        elif item.mnemonic == "ja":
            if not flags["CF"] and not flags["ZF"]:
                next_pc = read(operands[0])
        elif item.mnemonic == "jb":
            if flags["CF"]:
                next_pc = read(operands[0])
        elif item.mnemonic == "je":
            if flags["ZF"]:
                next_pc = read(operands[0])
        elif item.mnemonic == "jmp":
            next_pc = read(operands[0])
        elif item.mnemonic == "nop":
            pass
        else:
            raise AssertionError((hex(pc), item.mnemonic, item.op_str))
        pc = next_pc
    return {
        "exit": pc,
        "registers": registers,
        "memory": memory,
        "flags": flags,
        "writes": writes,
        "steps": steps,
    }


accepted = ACCEPTED_EXE.read_bytes()
candidate = CANDIDATE_EXE.read_bytes()
assert len(accepted) == len(candidate) == 645_966
assert sha256(accepted) == EXPECTED_ACCEPTED_SHA256
assert sha256(candidate) == EXPECTED_CANDIDATE_SHA256
assert digest(EVIDENCE / "candidate/compiler114m.exe") == EXPECTED_CANDIDATE_COMPILER_SHA256
assert digest(EVIDENCE / "marker-only/vhgame.exe") == EXPECTED_ACCEPTED_SHA256
assert lino_header(accepted) == lino_header(candidate)
header = lino_header(candidate)
assert header["code_start"] < ROOT_START < ROOT_END < header["physical_end"]
assert accepted[:ISLAND_START] == candidate[:ISLAND_START]
assert accepted[ISLAND_END:] == candidate[ISLAND_END:]
assert accepted[ISLAND_START:ISLAND_END] == SCALAR_ISLAND
assert candidate[ISLAND_START:ISLAND_END] == CANDIDATE_ISLAND
changed_offsets = [offset for offset in range(ISLAND_START, ISLAND_END)
                   if accepted[offset] != candidate[offset]]
assert changed_offsets
assert all(ISLAND_START <= offset < ISLAND_END for offset in changed_offsets)

accepted_island = instructions(accepted, ISLAND_START, ISLAND_END)
candidate_island = instructions(candidate, ISLAND_START, ISLAND_END)
reachable = instructions(candidate, ISLAND_START,
                         ISLAND_START + len(REACHABLE_CANDIDATE))
assert len(accepted_island) == 49
assert len(reachable) == 28
assert len(candidate_island) == 125
assert [item.mnemonic for item in accepted_island].count("cmp") == 9
assert [item.mnemonic for item in reachable].count("cmp") == 3
assert [item.mnemonic for item in reachable].count("sbb") == 1
assert [item.mnemonic for item in reachable].count("adc") == 1
assert reachable[-1].mnemonic == "jmp"
assert direct_target(reachable[-1]) == ISLAND_END
assert candidate[ISLAND_START + len(REACHABLE_CANDIDATE):ISLAND_END] == bytes([0x90]) * 97

candidate_code = instructions(candidate, header["code_start"], header["physical_end"])
external_entries = []
internal_targets = []
for item in candidate_code:
    target = direct_target(item)
    if target is None or not (ISLAND_START <= target < ISLAND_END):
        continue
    record = (item.address, item.mnemonic, target)
    if ISLAND_START <= item.address < ISLAND_END:
        internal_targets.append(record)
    else:
        external_entries.append(record)
assert external_entries == []
assert internal_targets == [
    (0x258D3, "ja", ACCEPT_START),
    (0x258E5, "ja", ACCEPT_START),
]
assert not [item for item in candidate_code
            if ISLAND_START + len(REACHABLE_CANDIDATE) <= item.address < ISLAND_END
            and direct_target(item) is not None]

scalar_map = {item.address: item for item in accepted_island}
candidate_map = {item.address: item for item in candidate_island}
coverage = Counter()
rng = random.Random(0x231C0DE)
states = []
edge = [0, 1, 2, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFE, 0xFFFFFFFF]
for value in edge:
    states.extend([
        (value, value, value, value, value, value),
        ((value - 1) & MASK, value, value, value, value, value),
        ((value + 1) & MASK, value, value, value, value, value),
        (value, (value - 1) & MASK, value, value, value, value),
        (value, (value + 1) & MASK, value, value, value, value),
        (value, value, (value - 1) & MASK, value, value, value),
        (value, value, (value + 1) & MASK, value, value, value),
    ])
for _ in range(40_000):
    states.append(tuple(rng.getrandbits(32) for _ in range(6)))

for index, state in enumerate(states):
    high, middle, low, trial_high, trial_middle, trial_low = state
    edi = 0x10000000
    registers = {
        "eax": rng.getrandbits(32),
        "ebx": rng.getrandbits(32),
        "ecx": trial_middle,
        "edx": trial_low,
        "esi": rng.getrandbits(32),
        "edi": edi,
        "ebp": rng.getrandbits(32),
        "esp": (0x70000000 + 4 * index) & MASK,
    }
    memory = {
        edi + WORKSPACE["sqcarry"]: trial_high,
        edi + WORKSPACE["srm0"]: low,
        edi + WORKSPACE["srm1"]: middle,
        edi + WORKSPACE["srm2"]: high,
    }
    flags = {name: bool(rng.getrandbits(1))
             for name in ("CF", "PF", "AF", "ZF", "SF", "OF")}
    scalar = emulate(scalar_map, registers, memory, flags)
    optimized = emulate(candidate_map, registers, memory, flags)
    assert scalar["exit"] == optimized["exit"]
    assert scalar["registers"] == optimized["registers"], (state, scalar, optimized)
    assert scalar["memory"] == optimized["memory"], (state, scalar, optimized)
    assert scalar["flags"] == optimized["flags"], (state, scalar, optimized)
    assert scalar["writes"] == optimized["writes"], (state, scalar, optimized)
    key = "accept" if scalar["exit"] == ISLAND_END else "reject"
    coverage[key] += 1
    if key == "accept":
        coverage[f"accepted-writes-{len(scalar['writes'])}"] += 1
    else:
        coverage[f"rejected-writes-{len(scalar['writes'])}"] += 1
assert coverage["accept"] > 0 and coverage["reject"] > 0
assert coverage["accepted-writes-3"] == coverage["accept"]
assert coverage["rejected-writes-0"] == coverage["reject"]

# Model the compiler's exact suffix gate independently. The actual positive
# production substitution above proves dispatch; these adversarial variants
# prove the accepted vector is the sole replacement authority.
def lower(blob, marker_present=True, i386m=True):
    if not marker_present or not i386m or len(blob) < len(SCALAR_ISLAND):
        return blob, False
    if blob[-len(SCALAR_ISLAND):] != SCALAR_ISLAND:
        return blob, False
    return blob[:-len(SCALAR_ISLAND)] + CANDIDATE_ISLAND, True

prefix = bytes(range(32))
positive, changed = lower(prefix + SCALAR_ISLAND)
assert changed and positive == prefix + CANDIDATE_ISLAND
assert lower(prefix + SCALAR_ISLAND, marker_present=False) == (
    prefix + SCALAR_ISLAND, False)
assert lower(prefix + SCALAR_ISLAND, i386m=False) == (
    prefix + SCALAR_ISLAND, False)
for offset in range(len(SCALAR_ISLAND)):
    altered = bytearray(SCALAR_ISLAND)
    altered[offset] ^= 1
    result, changed = lower(prefix + altered)
    assert not changed and result == prefix + altered

model = json.loads((EVIDENCE / "model.json").read_text(encoding="utf-8"))
build = json.loads((EVIDENCE / "build.json").read_text(encoding="utf-8"))
references = json.loads((EVIDENCE / "reference-audit.json").read_text(encoding="utf-8"))
assert model["status"] == build["status"] == references["status"] == "pass"
assert model["terminal_a_through_e_exact"]
assert model["terminal_x86_cf_pf_af_zf_sf_of_exact"]
assert build["compiler_three_stage_fixpoint"]
assert build["marker_only_game_matches_accepted_byte_exactly"]
assert build["candidate_game_sha256"] == EXPECTED_CANDIDATE_SHA256

report = {
    "schema": 1,
    "task": 231,
    "status": "pass",
    "accepted_sha256": EXPECTED_ACCEPTED_SHA256,
    "candidate_sha256": EXPECTED_CANDIDATE_SHA256,
    "executable_bytes": len(candidate),
    "header_and_code_boundaries_exact": True,
    "package_bytes_outside_island_exact": True,
    "changed_byte_values": len(changed_offsets),
    "unexpected_changes": 0,
    "root_helper_start": hex(ROOT_START),
    "root_helper_end": hex(ROOT_END),
    "restoring_loop": hex(RESTORING_LOOP),
    "island_start": hex(ISLAND_START),
    "island_end": hex(ISLAND_END),
    "island_bytes": len(CANDIDATE_ISLAND),
    "accepted_instructions": len(accepted_island),
    "candidate_reachable_instructions": len(reachable),
    "accepted_compare_instructions": 9,
    "candidate_compare_instructions": 3,
    "candidate_sbb_instructions": 1,
    "candidate_adc_instructions": 1,
    "candidate_unreachable_nop_bytes": 97,
    "candidate_padding_current_package_has_no_direct_entries": True,
    "external_direct_entries_to_island_interiors": 0,
    "generated_machine_cases": len(states),
    "generated_machine_all_eight_gprs_exact": True,
    "generated_machine_all_six_flags_exact": True,
    "generated_machine_workspace_exact": True,
    "generated_machine_ordered_write_trace_exact": True,
    "exact_suffix_positive_gate": True,
    "exact_suffix_absent_marker_fail_closed": True,
    "exact_suffix_non_i386m_model_fail_closed": True,
    "non_i386m_suppression_structurally_guarded": True,
    "non_i386m_output_comparison_run": False,
    "exact_suffix_single_byte_mutations_fail_closed": len(SCALAR_ISLAND),
    "marker_only_accepted_compiler_output_exact": True,
    "compiler_three_stage_fixpoint": True,
    "current_package_overwritten_label_reference_audit": "pass",
    "current_package_overwritten_label_references": 0,
    "whole_program_indirect_control_transfers_reported_unresolved": references[
        "whole_program_indirect_control_transfers_reported_unresolved"],
    "lowering_claim_scope": "current exact selected i386m production package only",
    "complete_shipping_dependency_closure_audited": False,
}
OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
