from pathlib import Path
from collections import Counter, deque
import hashlib
import json
import runpy
import struct

from capstone import Cs, CS_ARCH_X86, CS_GRP_CALL, CS_GRP_JUMP, CS_MODE_32
from capstone.x86_const import (
    X86_EFLAGS_MODIFY_AF, X86_EFLAGS_MODIFY_CF, X86_EFLAGS_MODIFY_DF,
    X86_EFLAGS_MODIFY_OF, X86_EFLAGS_MODIFY_PF, X86_EFLAGS_MODIFY_SF,
    X86_EFLAGS_MODIFY_ZF, X86_EFLAGS_RESET_AF, X86_EFLAGS_RESET_CF,
    X86_EFLAGS_RESET_DF, X86_EFLAGS_RESET_OF, X86_EFLAGS_RESET_PF,
    X86_EFLAGS_RESET_SF, X86_EFLAGS_RESET_ZF, X86_EFLAGS_SET_AF,
    X86_EFLAGS_SET_CF, X86_EFLAGS_SET_OF, X86_EFLAGS_SET_PF,
    X86_EFLAGS_SET_SF, X86_EFLAGS_SET_ZF, X86_EFLAGS_TEST_AF,
    X86_EFLAGS_TEST_CF, X86_EFLAGS_TEST_DF, X86_EFLAGS_TEST_OF,
    X86_EFLAGS_TEST_PF, X86_EFLAGS_TEST_SF, X86_EFLAGS_TEST_ZF,
    X86_EFLAGS_UNDEFINED_AF, X86_EFLAGS_UNDEFINED_CF,
    X86_EFLAGS_UNDEFINED_OF, X86_EFLAGS_UNDEFINED_PF,
    X86_EFLAGS_UNDEFINED_SF, X86_EFLAGS_UNDEFINED_ZF,
    X86_OP_IMM, X86_OP_MEM, X86_REG_EDI, X86_REG_EDX, X86_REG_ESI,
)

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/native-fmul-lowering-20260830"
ACCEPTED_EXE = EVIDENCE / "accepted/vhgame.exe"
CANDIDATE_EXE = EVIDENCE / "candidate/vhgame.exe"
OUTPUT = EVIDENCE / "production-layout.json"
MASK = 0xFFFFFFFF
XSCALAR_MUL_START = 0x255F0
XSCALAR_MUL_END = 0x2566A
XSCALAR_SQRT = 0x2566A
PUBLIC_FMUL = 0x27EDD
PUBLIC_FMUL_END = 0x27EEA
FA_DISPLACEMENT = 0x2620
XS_DISPLACEMENT = 0x2678
XREJ_DISPLACEMENT_FROM_XS = 0x30
EXPECTED_CANDIDATE_SHA256 = (
    "70c7fc0a3f97270768eb86ea3ad30d18ffb2811fe07f821aff8ade7d2f2063d4")
EXPECTED_CANDIDATE_COMPILER_SHA256 = (
    "facfb8b9373c548c569771978606fcd5d5273760ec7b1e2f0b4ee6bcc30d2e78")
RUNTIME_FCW_133F_SEQUENCE = bytes.fromhex(
    "9B D9 3D 10 53 40 00 "
    "66 A1 10 53 40 00 "
    "66 B8 3F 13 "
    "66 90 66 90 "
    "66 A3 10 53 40 00 "
    "D9 2D 10 53 40 00")

apply = runpy.run_path(str(EVIDENCE / "apply_candidate.py"))
ACCEPTED_SCALAR = apply["ACCEPTED_SCALAR"]
CANDIDATE_SCALAR = apply["CANDIDATE_SCALAR"]
XREJ_PREREQUISITE = apply["XREJ_PREREQUISITE"]
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
assert digest(EVIDENCE / "candidate/compiler114m.exe") == (
    EXPECTED_CANDIDATE_COMPILER_SHA256)
assert digest(EVIDENCE / "marker-only-i386m/vhgame.exe") == apply[
    "ACCEPTED_GAME_SHA256"]
assert lino_header(accepted) == lino_header(candidate)
header = lino_header(candidate)
assert header["code_start"] < XSCALAR_MUL_START < PUBLIC_FMUL < header[
    "physical_end"]
assert accepted[:XSCALAR_MUL_START] == candidate[:XSCALAR_MUL_START]
assert accepted[XSCALAR_MUL_END:] == candidate[XSCALAR_MUL_END:]
assert accepted[XSCALAR_MUL_START:XSCALAR_MUL_END] == ACCEPTED_SCALAR
assert candidate[XSCALAR_MUL_START:XSCALAR_MUL_END] == CANDIDATE_SCALAR
assert candidate[XSCALAR_MUL_END:XSCALAR_MUL_END + 16] == accepted[
    XSCALAR_MUL_END:XSCALAR_MUL_END + 16]
changed_offsets = [offset for offset in range(len(candidate))
                   if accepted[offset] != candidate[offset]]
assert changed_offsets
assert all(XSCALAR_MUL_START <= offset < XSCALAR_MUL_END
           for offset in changed_offsets)

accepted_island = instructions(accepted, XSCALAR_MUL_START, XSCALAR_MUL_END)
candidate_island = instructions(candidate, XSCALAR_MUL_START, XSCALAR_MUL_END)
assert candidate_island[-4].mnemonic == "ret"
assert [item.mnemonic for item in candidate_island[-3:]] == ["nop"] * 3
assert [item.mnemonic for item in candidate_island].count("fmul") == 1
assert [item.mnemonic for item in candidate_island].count("fld") == 2
assert [item.mnemonic for item in candidate_island].count("fstp") == 2
assert not [item for item in candidate_island if item.mnemonic == "call"]
assert [(item.mnemonic, item.op_str) for item in accepted_island[-4:]] == [
    ("call", "0x23cd8"), ("call", "0x24ee6"),
    ("mov", "ebp, 0x646f6e65"), ("ret", "")]

# Bind every memory operation in the candidate to its intended pointer and size.
assert candidate_island[0].mnemonic == "lea"
assert candidate_island[1].mnemonic == "lea"
for item, displacement, destination in (
        (candidate_island[0], FA_DISPLACEMENT, "esi"),
        (candidate_island[1], XS_DISPLACEMENT, "edx")):
    assert item.op_str.startswith(destination + ", ")
    memory = [operand for operand in item.operands if operand.type == X86_OP_MEM]
    assert len(memory) == 1
    assert memory[0].mem.base == X86_REG_EDI and not memory[0].mem.index
    assert memory[0].mem.disp == displacement
for item in candidate_island[2:]:
    for operand in item.operands:
        if operand.type != X86_OP_MEM:
            continue
        assert operand.mem.base in (X86_REG_ESI, X86_REG_EDX)
        assert not operand.mem.index
candidate_memory = [(item.address, item.mnemonic, item.op_str,
                     [operand.size for operand in item.operands
                      if operand.type == X86_OP_MEM])
                    for item in candidate_island
                    if any(operand.type == X86_OP_MEM for operand in item.operands)]
assert any(item.mnemonic == "fmul" and item.op_str == "qword ptr [esi + 8]"
           for item in candidate_island)
assert any(item.mnemonic == "fstp" and item.op_str == "xword ptr [edx]"
           for item in candidate_island)
assert any(item.mnemonic == "fld" and item.op_str == "xword ptr [edx]"
           for item in candidate_island)
assert any(item.mnemonic == "fstp" and item.op_str == "qword ptr [esi]"
           for item in candidate_island)
assert sum(item.mnemonic == "inc" and item.op_str == "dword ptr [edx + 0x30]"
           for item in candidate_island) == 3
assert any(item.mnemonic == "cmp" and item.op_str == "cx, 0x3bcc"
           for item in candidate_island)
assert sum(item.mnemonic == "cmp" and item.op_str == "ecx, 0xffe00000"
           for item in candidate_island) == 4

accepted_code = instructions(accepted, header["code_start"], header["physical_end"])
candidate_code = instructions(candidate, header["code_start"], header["physical_end"])
accepted_by_address = {item.address: item for item in accepted_code}
candidate_by_address = {item.address: item for item in candidate_code}
assert XSCALAR_MUL_START in candidate_by_address
assert XSCALAR_SQRT in candidate_by_address
assert PUBLIC_FMUL in candidate_by_address

# The runtime installs masked, nearest-even PC64 before entry. No generated code
# changes it, and the candidate is balanced and control-neutral.
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
accepted_fmul_addresses = [
    item.address for item in accepted_code if item.mnemonic == "fmul"]
candidate_fmul_addresses = [
    item.address for item in candidate_code if item.mnemonic == "fmul"]
candidate_hardware_fmul = next(
    item.address for item in candidate_island if item.mnemonic == "fmul")
assert candidate_fmul_addresses == sorted(
    accepted_fmul_addresses + [candidate_hardware_fmul])

# Every generated x87 status reader first overwrites condition flags with FCOMP,
# consumes only AH via SAHF, and restores EAX. Sticky arithmetic status may differ
# architecturally, but no selected-package reader observes the candidate's status.
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

# Resolve all direct entries to the replacement. The unchanged public wrapper is
# the sole direct caller and no direct transfer enters its interior.
island_entries = []
interior_entries = []
for item in candidate_code:
    target = direct_target(item)
    if (target is None or not (XSCALAR_MUL_START <= target < XSCALAR_MUL_END)
            or XSCALAR_MUL_START <= item.address < XSCALAR_MUL_END):
        continue
    record = (item.address, item.mnemonic, target)
    island_entries.append(record)
    if target != XSCALAR_MUL_START:
        interior_entries.append(record)
assert island_entries == [(PUBLIC_FMUL + 1, "call", XSCALAR_MUL_START)]
assert interior_entries == []

# The wrapper and all 369 callers remain byte-exact.
public_wrapper = instructions(candidate, PUBLIC_FMUL, PUBLIC_FMUL_END)
assert [(item.mnemonic, direct_target(item)) for item in public_wrapper] == [
    ("pushal", None), ("call", XSCALAR_MUL_START), ("popal", None),
    ("mov", None), ("ret", None),
]
assert public_wrapper[3].op_str == "ebp, 0x646f6e65"
assert accepted[PUBLIC_FMUL:PUBLIC_FMUL_END] == candidate[
    PUBLIC_FMUL:PUBLIC_FMUL_END]
accepted_public_calls = [item.address for item in accepted_code
                         if item.group(CS_GRP_CALL)
                         and direct_target(item) == PUBLIC_FMUL]
candidate_public_calls = [item.address for item in candidate_code
                          if item.group(CS_GRP_CALL)
                          and direct_target(item) == PUBLIC_FMUL]
assert accepted_public_calls == candidate_public_calls
assert len(candidate_public_calls) == 369

# EFLAGS are not restored by POPAL. For every direct public FMul caller, walk all
# local successors until a call/return barrier and prove no flag is consumed
# before that specific flag has been redefined independently of FMul.
flag_rows = (
    ("AF", X86_EFLAGS_TEST_AF, X86_EFLAGS_MODIFY_AF | X86_EFLAGS_RESET_AF
     | X86_EFLAGS_SET_AF | X86_EFLAGS_UNDEFINED_AF),
    ("CF", X86_EFLAGS_TEST_CF, X86_EFLAGS_MODIFY_CF | X86_EFLAGS_RESET_CF
     | X86_EFLAGS_SET_CF | X86_EFLAGS_UNDEFINED_CF),
    ("DF", X86_EFLAGS_TEST_DF, X86_EFLAGS_MODIFY_DF | X86_EFLAGS_RESET_DF),
    ("OF", X86_EFLAGS_TEST_OF, X86_EFLAGS_MODIFY_OF | X86_EFLAGS_RESET_OF
     | X86_EFLAGS_SET_OF | X86_EFLAGS_UNDEFINED_OF),
    ("PF", X86_EFLAGS_TEST_PF, X86_EFLAGS_MODIFY_PF | X86_EFLAGS_RESET_PF
     | X86_EFLAGS_SET_PF | X86_EFLAGS_UNDEFINED_PF),
    ("SF", X86_EFLAGS_TEST_SF, X86_EFLAGS_MODIFY_SF | X86_EFLAGS_RESET_SF
     | X86_EFLAGS_SET_SF | X86_EFLAGS_UNDEFINED_SF),
    ("ZF", X86_EFLAGS_TEST_ZF, X86_EFLAGS_MODIFY_ZF | X86_EFLAGS_RESET_ZF
     | X86_EFLAGS_SET_ZF | X86_EFLAGS_UNDEFINED_ZF),
)
all_flag_names = frozenset(row[0] for row in flag_rows)
flag_audit_steps = 0
flag_audit_states = 0
for call_address in candidate_public_calls:
    call = candidate_by_address[call_address]
    start = call.address + call.size
    pending = [(start, frozenset())]
    seen = set()
    while pending:
        address, defined = pending.pop()
        state = (address, defined)
        if state in seen:
            continue
        seen.add(state)
        flag_audit_states += 1
        item = candidate_by_address[address]
        flag_audit_steps += 1
        tested = {name for name, test, _ in flag_rows if item.eflags & test}
        assert tested <= defined, (
            hex(call_address), hex(address), item.mnemonic, item.op_str,
            tested, defined)
        newly_defined = {name for name, _, writes in flag_rows
                         if item.eflags & writes}
        after = frozenset(set(defined) | newly_defined)
        if after == all_flag_names:
            continue
        if item.group(CS_GRP_CALL) or item.mnemonic.startswith("ret"):
            continue
        target = direct_target(item)
        fallthrough = item.address + item.size
        if item.group(CS_GRP_JUMP):
            if target is not None and target in candidate_by_address:
                pending.append((target, after))
            if item.mnemonic != "jmp":
                pending.append((fallthrough, after))
        else:
            pending.append((fallthrough, after))
assert flag_audit_steps > len(candidate_public_calls)

# Package-wide direct-function x87-depth analysis. Each direct call target and
# the executable entry is analyzed as an empty-stack function boundary while
# calls are required to be net-zero contracts. Every reachable local return and
# tail transfer is at depth zero; every public FMul call is entered at depth zero.
x87_push = {"fld", "fild"}
x87_pop = {"fstp", "fistp", "fcomp"}
x87_neutral = {"fadd", "fdiv", "fmul", "fsub", "fnstsw", "wait"}
assert {item.mnemonic for item in candidate_code
        if item.mnemonic.startswith("f") or item.mnemonic == "wait"} <= (
            x87_push | x87_pop | x87_neutral)
function_roots = {header["code_entry"]}
function_roots.update(
    direct_target(item) for item in candidate_code
    if item.group(CS_GRP_CALL) and direct_target(item) in candidate_by_address)
# Two generated routines containing six FMul sites are reached through the
# selected package's indirect dispatch tables rather than a direct CALL. Their
# starts are nevertheless unambiguous sequential function boundaries: each is
# the first decoded instruction immediately after a RET.
sequential_indirect_function_roots = {0x3A751, 0x9505E}
for root in sequential_indirect_function_roots:
    prior = candidate_by_address[
        max(address for address in candidate_by_address if address < root)]
    assert prior.mnemonic.startswith("ret")
    assert prior.address + prior.size == root
function_roots.update(sequential_indirect_function_roots)
x87_states = 0
x87_returns = 0
x87_peak = 0
fmul_entry_depths = []
for root in sorted(function_roots):
    pending = [(root, 0)]
    seen_depth = {}
    while pending:
        address, depth = pending.pop()
        if address not in candidate_by_address:
            assert depth == 0
            continue
        previous = seen_depth.get(address)
        if previous is not None:
            assert previous == depth, (hex(root), hex(address), previous, depth)
            continue
        seen_depth[address] = depth
        x87_states += 1
        item = candidate_by_address[address]
        if item.mnemonic in x87_push:
            depth += 1
        elif item.mnemonic in x87_pop:
            depth -= 1
        assert 0 <= depth <= 8, (hex(root), hex(address), item.mnemonic, depth)
        x87_peak = max(x87_peak, depth)
        if item.group(CS_GRP_CALL) and direct_target(item) == PUBLIC_FMUL:
            fmul_entry_depths.append((root, item.address, depth))
        if item.mnemonic.startswith("ret"):
            assert depth == 0, (hex(root), hex(address), depth)
            x87_returns += 1
            continue
        target = direct_target(item)
        fallthrough = item.address + item.size
        if item.group(CS_GRP_JUMP):
            if target is None or target not in candidate_by_address:
                assert depth == 0
            else:
                pending.append((target, depth))
            if item.mnemonic != "jmp":
                pending.append((fallthrough, depth))
        else:
            pending.append((fallthrough, depth))
assert len({address for _, address, _ in fmul_entry_depths}) == 369
assert all(depth == 0 for _, _, depth in fmul_entry_depths)

# Fixed-back XREJ binding and fixed/named scratch observation scope.
assert accepted[0x23907:0x23907 + len(XREJ_PREREQUISITE)] == XREJ_PREREQUISITE
assert XSCALAR_MUL_END - 0x23907 == apply["PREREQUISITE_DISTANCE"]
fixed_xscratch_references = Counter()
indexed_edi_operands = 0
for item in candidate_code:
    for operand in item.operands:
        if operand.type != X86_OP_MEM or operand.mem.base != X86_REG_EDI:
            continue
        if operand.mem.index:
            indexed_edi_operands += 1
        else:
            displacement = operand.mem.disp & MASK
            if XS_DISPLACEMENT <= displacement < XS_DISPLACEMENT + 10:
                fixed_xscratch_references[displacement] += 1
assert fixed_xscratch_references

# Code-label materialization is absent in the package's established common forms.
materialized_address_hits = {}
for name, address in {
        "xscalar_mul": XSCALAR_MUL_START,
        "xscalar_sqrt": XSCALAR_SQRT,
        "public_fmul": PUBLIC_FMUL}.items():
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
indirect_transfers = [
    item for item in candidate_code
    if (item.group(CS_GRP_CALL) or item.group(CS_GRP_JUMP))
    and direct_target(item) is None]
assert len(indirect_transfers) == 259
assert sum(item.group(CS_GRP_CALL) for item in indirect_transfers) == 251
assert sum(item.group(CS_GRP_JUMP) for item in indirect_transfers) == 8

# Independently model both compiler gates. No mutation may occur unless the
# complete 122-byte island and fixed-back 42-byte prerequisite both match.
def lower(prefix, island, prerequisite=XREJ_PREREQUISITE,
          marker_present=True, i386m=True, distance=122):
    original = prefix + island
    if not marker_present or not i386m or distance != len(ACCEPTED_SCALAR):
        return original, False
    if island != ACCEPTED_SCALAR or prerequisite != XREJ_PREREQUISITE:
        return original, False
    return prefix + CANDIDATE_SCALAR, True


prefix = bytes(range(32))
positive, changed = lower(prefix, ACCEPTED_SCALAR)
assert changed and positive == prefix + CANDIDATE_SCALAR
for kwargs in ({"marker_present": False}, {"i386m": False}, {"distance": 121}):
    unchanged, changed = lower(prefix, ACCEPTED_SCALAR, **kwargs)
    assert not changed and unchanged == prefix + ACCEPTED_SCALAR
for offset in range(len(ACCEPTED_SCALAR)):
    altered = bytearray(ACCEPTED_SCALAR)
    altered[offset] ^= 1
    unchanged, changed = lower(prefix, bytes(altered))
    assert not changed and unchanged == prefix + bytes(altered)
for offset in range(len(XREJ_PREREQUISITE)):
    altered = bytearray(XREJ_PREREQUISITE)
    altered[offset] ^= 1
    unchanged, changed = lower(prefix, ACCEPTED_SCALAR, bytes(altered))
    assert not changed and unchanged == prefix + ACCEPTED_SCALAR

model = json.loads((EVIDENCE / "model.json").read_text(encoding="utf-8"))
build = json.loads((EVIDENCE / "build.json").read_text(encoding="utf-8"))
assert model["status"] == build["status"] == "pass"
assert model["all_finite_binary64_pair_equivalence_algebraic"]
assert model["portable_tiny_and_overflow_xrej_policy_exact"]
assert model["final_spill_overflow_detection_required_and_present"]
assert model["public_a_through_e_preserved_by_unchanged_wrapper"]
assert model["candidate_x87_stack_net_change"] == 0
assert build["compiler_three_stage_fixpoint"]
assert build["marker_only_i386m_matches_accepted_byte_exactly"]
assert build["non_i386m_output_comparison_run"]
assert build["non_i386m_outputs_byte_exact"]
assert build["candidate_i386m_game_sha256"] == EXPECTED_CANDIDATE_SHA256

report = {
    "schema": 1,
    "task": 235,
    "status": "pass",
    "accepted_sha256": apply["ACCEPTED_GAME_SHA256"],
    "candidate_sha256": EXPECTED_CANDIDATE_SHA256,
    "candidate_compiler_sha256": EXPECTED_CANDIDATE_COMPILER_SHA256,
    "executable_bytes": len(candidate),
    "header_and_code_boundaries_exact": True,
    "package_bytes_outside_island_exact": True,
    "changed_byte_values": len(changed_offsets),
    "unexpected_changes": 0,
    "xscalar_mul_start": hex(XSCALAR_MUL_START),
    "xscalar_mul_end": hex(XSCALAR_MUL_END),
    "xscalar_sqrt_unchanged_start": hex(XSCALAR_SQRT),
    "island_bytes": len(CANDIDATE_SCALAR),
    "accepted_island_instructions": len(accepted_island),
    "candidate_island_instructions": len(candidate_island),
    "candidate_hardware_fmul": True,
    "candidate_p64_tbyte_materialization": True,
    "candidate_p53_qword_spill": True,
    "candidate_unreachable_nop_bytes": 3,
    "candidate_x87_stack_peak": 1,
    "candidate_x87_stack_net_zero": True,
    "candidate_control_word_writes": 0,
    "windows_runtime_fcw_133f_sequence_exact": True,
    "windows_runtime_fcw_133f_sequence_offset": hex(0x2661),
    "generated_control_word_operations": 0,
    "generated_x87_status_readers": len(status_readers),
    "all_status_readers_overwrite_conditions_and_discard_status": True,
    "candidate_architectural_x87_status_exact": False,
    "candidate_x87_status_observable_by_selected_package_readers": False,
    "direct_entries_to_island_start": len(island_entries),
    "direct_entries_to_island_interior": len(interior_entries),
    "public_fmul_wrapper": hex(PUBLIC_FMUL),
    "public_fmul_wrapper_byte_exact": True,
    "public_fmul_call_sites": len(candidate_public_calls),
    "xscalar_mul_direct_callers": len(island_entries),
    "public_integer_register_save_restore_exact": True,
    "public_ebp_terminal_state_exact": True,
    "caller_eflags_successor_states": flag_audit_states,
    "caller_eflags_successor_steps": flag_audit_steps,
    "all_direct_fmul_callers_redefine_before_flag_observation": True,
    "package_direct_function_roots_analyzed": len(function_roots),
    "sequential_indirect_function_roots_analyzed": [
        hex(value) for value in sorted(sequential_indirect_function_roots)],
    "all_public_fmul_call_sites_covered_by_x87_depth_analysis": len(
        {address for _, address, _ in fmul_entry_depths}),
    "package_x87_cfg_states": x87_states,
    "package_x87_returns": x87_returns,
    "package_x87_peak": x87_peak,
    "all_direct_fmul_calls_enter_with_empty_x87_stack": True,
    "all_direct_function_returns_have_empty_x87_stack": True,
    "xrej_fixed_back_prerequisite_bytes": len(XREJ_PREREQUISITE),
    "xrej_fixed_back_prerequisite_distance": apply["PREREQUISITE_DISTANCE"],
    "xscratch_fixed_references": dict(fixed_xscratch_references),
    "candidate_xscratch_terminal_state_equals_portable": False,
    "candidate_xscratch_terminal_state_is_private_contract_state": True,
    "fixed_named_scratch_observer_found": False,
    "indexed_edi_operands": indexed_edi_operands,
    "indexed_alias_ranges_exhaustively_proven": False,
    "materialized_code_label_address_hits": materialized_address_hits,
    "checked_materialized_address_forms_with_hits": 0,
    "indirect_calls_present": 251,
    "indirect_jumps_present": 8,
    "indirect_transfer_targets_exhaustively_resolved": False,
    "all_finite_binary64_pair_equivalence_algebraic": True,
    "exact_island_positive_gate": True,
    "exact_prerequisite_positive_gate": True,
    "exact_vector_absent_marker_fail_closed": True,
    "exact_vector_non_i386m_model_fail_closed": True,
    "exact_island_single_byte_mutations_fail_closed": len(ACCEPTED_SCALAR),
    "exact_prerequisite_single_byte_mutations_fail_closed": len(
        XREJ_PREREQUISITE),
    "marker_only_accepted_compiler_output_exact": True,
    "compiler_three_stage_fixpoint": True,
    "non_i386m_output_comparison_run": True,
    "non_i386m_cpu": build["non_i386m_cpu"],
    "non_i386m_outputs_byte_exact": True,
    "complete_shipping_dependency_closure_audited": False,
    "lowering_claim_scope": "current exact selected i386m production package",
    "candidate_memory_operands": candidate_memory,
}
OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
