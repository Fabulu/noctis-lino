from pathlib import Path
from collections import Counter
import hashlib
import json
import runpy
import struct

from capstone import Cs, CS_ARCH_X86, CS_GRP_CALL, CS_GRP_JUMP, CS_MODE_32
from capstone.x86_const import X86_OP_IMM, X86_OP_MEM, X86_REG_EDI

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/native-fsqrt-lowering-20260830"
ACCEPTED_EXE = EVIDENCE / "accepted/vhgame.exe"
CANDIDATE_EXE = EVIDENCE / "candidate/vhgame.exe"
OUTPUT = EVIDENCE / "production-layout.json"
MASK = 0xFFFFFFFF
XSCALAR_SQRT = 0x2566A
ISLAND_START = 0x256C7
ISLAND_END = 0x256D7
ZERO_START = 0x256D7
ROOT_START = 0x256F1
ROOT_END = 0x25B49
PUBLIC_FSQRT = 0x27F02
FA_DISPLACEMENT = 0x2620
ROOT_PRIVATE_DISPLACEMENTS = {
    0x27A4, 0x27A8, 0x27AC, 0x27B0, 0x27B4, 0x27B8, 0x27BC,
    0x27C0, 0x27C4, 0x27C8, 0x27CC, 0x27D0, 0x27D4, 0x27D8,
}
RUNTIME_FCW_133F_SEQUENCE = bytes.fromhex(
    "9B D9 3D 10 53 40 00 "
    "66 A1 10 53 40 00 "
    "66 B8 3F 13 "
    "66 90 66 90 "
    "66 A3 10 53 40 00 "
    "D9 2D 10 53 40 00")
EXPECTED_CANDIDATE_SHA256 = (
    "fadbad38814313b000698f591c060d91a53f3b6f701c65f67fbc5845d4d3a4c9")
EXPECTED_CANDIDATE_COMPILER_SHA256 = (
    "b2f87e8b330fbd479f0bd7b4b8bf536fe4ac06849e6e1fea1f6401930a9f5435")

apply = runpy.run_path(str(EVIDENCE / "apply_candidate.py"))
SCALAR_ISLAND = apply["SCALAR_ISLAND"]
CANDIDATE_ISLAND = apply["CANDIDATE_ISLAND"]
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
    immediate = [operand.imm & MASK for operand in instruction.operands
                 if operand.type == X86_OP_IMM]
    assert len(immediate) <= 1
    return immediate[0] if immediate else None


accepted = ACCEPTED_EXE.read_bytes()
candidate = CANDIDATE_EXE.read_bytes()
assert len(accepted) == len(candidate) == 645_966
assert sha256(accepted) == apply["ACCEPTED_GAME_SHA256"]
assert sha256(candidate) == EXPECTED_CANDIDATE_SHA256
assert digest(EVIDENCE / "candidate/compiler114m.exe") == EXPECTED_CANDIDATE_COMPILER_SHA256
assert digest(EVIDENCE / "marker-only-i386m/vhgame.exe") == apply[
    "ACCEPTED_GAME_SHA256"]
assert lino_header(accepted) == lino_header(candidate)
header = lino_header(candidate)
assert header["code_start"] < XSCALAR_SQRT < ROOT_END < header["physical_end"]
assert accepted[:ISLAND_START] == candidate[:ISLAND_START]
assert accepted[ISLAND_END:] == candidate[ISLAND_END:]
assert accepted[ISLAND_START:ISLAND_END] == SCALAR_ISLAND
assert candidate[ISLAND_START:ISLAND_END] == CANDIDATE_ISLAND
changed_offsets = [offset for offset in range(len(candidate))
                   if accepted[offset] != candidate[offset]]
assert len(changed_offsets) == 15
assert all(ISLAND_START <= offset < ISLAND_END for offset in changed_offsets)

accepted_island = instructions(accepted, ISLAND_START, ISLAND_END)
candidate_island = instructions(candidate, ISLAND_START, ISLAND_END)
assert [(item.mnemonic, item.op_str) for item in accepted_island] == [
    ("call", "0x256f1"),
    ("call", "0x24ee6"),
    ("mov", "ebp, 0x646f6e65"),
    ("ret", ""),
]
assert [item.mnemonic for item in candidate_island] == [
    "fld", "fsqrt", "fstp", "ret", "nop"]
for item in (candidate_island[0], candidate_island[2]):
    operands = item.operands
    assert len(operands) == 1 and operands[0].type == X86_OP_MEM
    memory = operands[0].mem
    assert memory.base == X86_REG_EDI and not memory.index
    assert memory.disp == FA_DISPLACEMENT and operands[0].size == 8
assert candidate_island[1].op_str == ""
assert candidate_island[3].address == ISLAND_END - 2
assert candidate_island[4].address == ISLAND_END - 1

accepted_code = instructions(accepted, header["code_start"], header["physical_end"])
candidate_code = instructions(candidate, header["code_start"], header["physical_end"])
accepted_by_address = {item.address: item for item in accepted_code}
candidate_by_address = {item.address: item for item in candidate_code}
assert candidate_by_address[XSCALAR_SQRT].address == XSCALAR_SQRT

# The post-link Windows runtime installs masked, nearest-even p64 (133Fh) before
# application entry. The generated Lino body contains no later control-word
# operation, and the candidate island itself is balanced and control-neutral.
assert accepted.count(RUNTIME_FCW_133F_SEQUENCE) == 1
assert candidate.count(RUNTIME_FCW_133F_SEQUENCE) == 1
assert candidate.index(RUNTIME_FCW_133F_SEQUENCE) == 0x2661
control_word_mnemonics = {
    "fldcw", "fnstcw", "fstcw", "fldenv", "fnstenv", "fstenv",
    "frstor", "fnsave", "fsave", "fxrstor", "fxsave", "ldmxcsr",
    "stmxcsr",
}
assert not [item for item in candidate_code
            if item.mnemonic in control_word_mnemonics]
assert [item.address for item in candidate_code
        if item.mnemonic == "fsqrt"] == [candidate_island[1].address]

# FSQRT may set sticky x87 status bits. Every generated status read is a local
# compare sequence: FCOMP first overwrites the condition bits, SAHF consumes only
# AH, and POP restores the saved EAX (including the discarded exception bits in
# AL). Thus no selected-package observer can consume status left by FSQRT.
status_readers = [index for index, item in enumerate(candidate_code)
                  if item.mnemonic == "fnstsw"]
assert len(status_readers) == 11
for index in status_readers:
    window = candidate_code[index - 4:index + 3]
    assert [item.mnemonic for item in window] == [
        "push", "fld", "fcomp", "wait", "fnstsw", "sahf", "pop"]
    assert window[0].op_str == window[-1].op_str == "eax"
    assert window[4].op_str == "ax"
assert not [item for item in candidate_code
            if item.mnemonic in {"fnstenv", "fstenv", "fnsave", "fsave"}]

# The fourteen restoring-root words are exactly the no-index EDI displacements
# unique to the now-unreachable root region. No instruction outside that region
# names one of those exact displacements; dynamic indexed-range aliasing is
# recorded separately and deliberately not claimed as exhaustively resolved.
root_displacements = Counter()
outside_displacements = Counter()
for item in candidate_code:
    for operand in item.operands:
        if operand.type != X86_OP_MEM or operand.mem.base != X86_REG_EDI:
            continue
        displacement = operand.mem.disp & MASK
        if ROOT_START <= item.address < ROOT_END and not operand.mem.index:
            root_displacements[displacement] += 1
        elif not (ROOT_START <= item.address < ROOT_END):
            outside_displacements[displacement] += 1
assert set(root_displacements) - set(outside_displacements) == (
    ROOT_PRIVATE_DISPLACEMENTS)
assert not ROOT_PRIVATE_DISPLACEMENTS.intersection(outside_displacements)

# Code-label addresses are absent in the package's four common offset forms.
# This supplements the ordinary source/direct-call proof, but deliberately does
# not claim that every target of the package's external-service indirect ABI was
# statically resolved.
materialized_address_hits = {}
for name, address in {
        "xscalar_sqrt": XSCALAR_SQRT,
        "root_core": ROOT_START,
        "public_fsqrt": PUBLIC_FSQRT}.items():
    forms = {
        "absolute": address,
        "code_relative": address - header["code_start"],
        "marker_relative": address - header["marker"],
        "physical_end_relative": (address - header["physical_end"]) & MASK,
    }
    materialized_address_hits[name] = {}
    for form_name, value in forms.items():
        packed = struct.pack("<I", value & MASK)
        hits = [offset for offset in range(len(candidate) - 3)
                if candidate[offset:offset + 4] == packed]
        materialized_address_hits[name][form_name] = hits
        assert hits == []

indexed_edi_operands_outside_root = sum(
    1 for item in candidate_code
    if not (ROOT_START <= item.address < ROOT_END)
    for operand in item.operands
    if (operand.type == X86_OP_MEM and operand.mem.base == X86_REG_EDI
        and operand.mem.index))
indirect_transfers = [
    item for item in candidate_code
    if (item.group(CS_GRP_CALL) or item.group(CS_GRP_JUMP))
    and direct_target(item) is None]
assert len(indirect_transfers) == 259
assert sum(item.group(CS_GRP_CALL) for item in indirect_transfers) == 251
assert sum(item.group(CS_GRP_JUMP) for item in indirect_transfers) == 8

# All direct entries and calls are resolved for this current package. The only
# entry to the replacement is the existing positive-dispatch branch at its start.
island_entries = []
interior_entries = []
root_external_entries = []
for item in candidate_code:
    target = direct_target(item)
    if target is None:
        continue
    if ISLAND_START <= target < ISLAND_END:
        record = (item.address, item.mnemonic, target)
        island_entries.append(record)
        if target != ISLAND_START:
            interior_entries.append(record)
    if ROOT_START <= target < ROOT_END and not (ROOT_START <= item.address < ROOT_END):
        root_external_entries.append((item.address, item.mnemonic, target))
assert island_entries == [(0x256A1, "je", ISLAND_START)]
assert interior_entries == []
assert root_external_entries == []

accepted_root_calls = [
    item.address for item in accepted_code
    if item.group(CS_GRP_CALL) and direct_target(item) == ROOT_START]
candidate_root_calls = [
    item.address for item in candidate_code
    if item.group(CS_GRP_CALL) and direct_target(item) == ROOT_START]
assert accepted_root_calls == [ISLAND_START]
assert candidate_root_calls == []
assert accepted[ROOT_START:ROOT_END] == candidate[ROOT_START:ROOT_END]

# The public wrapper remains byte-exact, has one pushal/call/popal boundary, and
# every one of its 31 direct whole-program call sites remains unchanged.
public_wrapper = instructions(candidate, PUBLIC_FSQRT, PUBLIC_FSQRT + 13)
assert [(item.mnemonic, direct_target(item)) for item in public_wrapper] == [
    ("pushal", None), ("call", XSCALAR_SQRT), ("popal", None),
    ("mov", None), ("ret", None),
]
assert accepted[PUBLIC_FSQRT:PUBLIC_FSQRT + 13] == candidate[
    PUBLIC_FSQRT:PUBLIC_FSQRT + 13]
accepted_public_calls = [item.address for item in accepted_code
                         if item.group(CS_GRP_CALL)
                         and direct_target(item) == PUBLIC_FSQRT]
candidate_public_calls = [item.address for item in candidate_code
                          if item.group(CS_GRP_CALL)
                          and direct_target(item) == PUBLIC_FSQRT]
assert accepted_public_calls == candidate_public_calls
assert len(candidate_public_calls) == 31
scalar_calls = [item.address for item in candidate_code
                if item.group(CS_GRP_CALL)
                and direct_target(item) == XSCALAR_SQRT]
assert scalar_calls == [PUBLIC_FSQRT + 1]

# Model the compiler's complete exact-context and exact-vector gates
# independently. Every one-byte context mutation (including every FA operand),
# absent marker, or non-i386m target fails closed.
XSCALAR_CONTEXT = apply["XSCALAR_CONTEXT"]
assert accepted[XSCALAR_SQRT:ISLAND_END] == XSCALAR_CONTEXT
assert XSCALAR_CONTEXT.endswith(SCALAR_ISLAND)


def lower(blob, marker_present=True, i386m=True):
    if not marker_present or not i386m or len(blob) < len(XSCALAR_CONTEXT):
        return blob, False
    if blob[-len(XSCALAR_CONTEXT):] != XSCALAR_CONTEXT:
        return blob, False
    start = len(blob) - len(SCALAR_ISLAND)
    return blob[:start] + CANDIDATE_ISLAND, True


prefix = bytes(range(32))
positive, changed = lower(prefix + XSCALAR_CONTEXT)
assert changed and positive == (
    prefix + XSCALAR_CONTEXT[:-len(SCALAR_ISLAND)] + CANDIDATE_ISLAND)
assert lower(prefix + XSCALAR_CONTEXT, marker_present=False) == (
    prefix + XSCALAR_CONTEXT, False)
assert lower(prefix + XSCALAR_CONTEXT, i386m=False) == (
    prefix + XSCALAR_CONTEXT, False)
for offset in range(len(XSCALAR_CONTEXT)):
    altered = bytearray(XSCALAR_CONTEXT)
    altered[offset] ^= 1
    result, changed = lower(prefix + altered)
    assert not changed and result == prefix + altered

model = json.loads((EVIDENCE / "model.json").read_text(encoding="utf-8"))
build = json.loads((EVIDENCE / "build.json").read_text(encoding="utf-8"))
assert model["status"] == build["status"] == "pass"
assert model["public_p53_binary64_result_exact"]
assert model["all_positive_finite_binary64_equivalence_integer_proof"]
assert model["compatibility_borrow_difference_implies_root_low_16_zero"]
assert model["root_and_root_plus_one_then_have_identical_p53_spill"]
assert model["public_a_through_e_exact_via_wrapper"]
assert model["candidate_x87_top_net_change"] == 0
assert build["compiler_three_stage_fixpoint"]
assert build["marker_only_i386m_matches_accepted_byte_exactly"]
assert build["non_i386m_output_comparison_run"]
assert build["non_i386m_outputs_byte_exact"]
assert build["candidate_i386m_game_sha256"] == EXPECTED_CANDIDATE_SHA256

report = {
    "schema": 1,
    "task": 233,
    "status": "pass",
    "accepted_sha256": apply["ACCEPTED_GAME_SHA256"],
    "candidate_sha256": EXPECTED_CANDIDATE_SHA256,
    "executable_bytes": len(candidate),
    "header_and_code_boundaries_exact": True,
    "package_bytes_outside_island_exact": True,
    "changed_byte_values": len(changed_offsets),
    "unexpected_changes": 0,
    "xscalar_sqrt": hex(XSCALAR_SQRT),
    "island_start": hex(ISLAND_START),
    "island_end": hex(ISLAND_END),
    "island_bytes": len(CANDIDATE_ISLAND),
    "accepted_island_instructions": len(accepted_island),
    "candidate_island_instructions": len(candidate_island),
    "candidate_fld_qword_fa": True,
    "candidate_fsqrt": True,
    "candidate_fstp_qword_fa": True,
    "candidate_x87_stack_net_zero": True,
    "candidate_control_word_writes": 0,
    "windows_runtime_fcw_133f_sequence_exact": True,
    "windows_runtime_fcw_133f_sequence_offset": hex(0x2661),
    "generated_control_word_operations": 0,
    "generated_x87_status_readers": len(status_readers),
    "all_status_readers_overwrite_conditions_and_discard_status": True,
    "candidate_architectural_x87_status_exact": False,
    "candidate_x87_status_observable_by_selected_package_readers": False,
    "candidate_unreachable_nop_bytes": 1,
    "direct_entries_to_island_start": 1,
    "direct_entries_to_island_interior": 0,
    "accepted_direct_calls_to_root_core": len(accepted_root_calls),
    "candidate_direct_calls_to_root_core": len(candidate_root_calls),
    "candidate_external_direct_entries_to_root_core_region": 0,
    "root_core_bytes_retained_exact_but_unreachable_by_direct_transfer": True,
    "root_private_scratch_words": len(ROOT_PRIVATE_DISPLACEMENTS),
    "root_private_scratch_fixed_references_outside_root_region": 0,
    "root_private_scratch_named_observer_found": False,
    "indexed_edi_operands_outside_root_region": indexed_edi_operands_outside_root,
    "indexed_alias_ranges_exhaustively_proven": False,
    "root_scratch_terminal_state_is_private_contract_state": True,
    "materialized_code_label_address_hits": materialized_address_hits,
    "checked_materialized_address_forms_with_hits": 0,
    "indirect_calls_present": 251,
    "indirect_jumps_present": 8,
    "indirect_transfer_targets_exhaustively_resolved": False,
    "public_fsqrt_wrapper": hex(PUBLIC_FSQRT),
    "public_fsqrt_wrapper_byte_exact": True,
    "public_fsqrt_call_sites": len(candidate_public_calls),
    "xscalar_sqrt_direct_callers": len(scalar_calls),
    "public_integer_register_save_restore_exact": True,
    "internal_ebp_at_public_fsqrt_boundary_exact": True,
    "internal_ebp_terminal_state_inside_xscalarsqrt_not_equated": True,
    "all_positive_finite_binary64_equivalence_integer_proof": True,
    "exact_context_bytes": len(XSCALAR_CONTEXT),
    "exact_context_binds_fa_displacement": True,
    "exact_context_positive_gate": True,
    "exact_vector_positive_gate": True,
    "exact_vector_absent_marker_fail_closed": True,
    "exact_vector_non_i386m_model_fail_closed": True,
    "exact_context_single_byte_mutations_fail_closed": len(XSCALAR_CONTEXT),
    "marker_only_accepted_compiler_output_exact": True,
    "compiler_three_stage_fixpoint": True,
    "non_i386m_output_comparison_run": True,
    "non_i386m_cpu": build["non_i386m_cpu"],
    "non_i386m_outputs_byte_exact": True,
    "complete_shipping_dependency_closure_audited": False,
    "lowering_claim_scope": "current exact selected i386m production package",
}
OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
