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
EVIDENCE = ROOT / "build/native-fquo-lowering-20260830"
ACCEPTED_EXE = EVIDENCE / "accepted/vhgame.exe"
CANDIDATE_EXE = EVIDENCE / "candidate/vhgame.exe"
OUTPUT = EVIDENCE / "production-layout.json"
MASK = 0xFFFFFFFF
XSCALAR_QUO_START = 0x2540F
XSCALAR_QUO_END = 0x254FC
XSCALAR_ADD = 0x254FC
PUBLIC_FQUO = 0x27EEA
PUBLIC_FQUO_END = 0x27EF7
FQUO_BODY = 0x27EF7
FQUO_BODY_END = 0x27F02
FA_DISPLACEMENT = 0x2620
XS_DISPLACEMENT = 0x2678
XREJ_DISPLACEMENT_FROM_XS = 0x30
EXPECTED_CANDIDATE_SHA256 = (
    "fcb0b008c7d05e383a7759ec6978c7189aae669811c9b4348a511e31c93c5340")
EXPECTED_CANDIDATE_COMPILER_SHA256 = (
    "07621242048e1e49ee01db07f614a6cd0f37a87aef3235139ed17f5b8e666e27")
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
assert header["code_start"] < XSCALAR_QUO_START < PUBLIC_FQUO < header[
    "physical_end"]
assert accepted[:XSCALAR_QUO_START] == candidate[:XSCALAR_QUO_START]
assert accepted[XSCALAR_QUO_END:] == candidate[XSCALAR_QUO_END:]
assert accepted[XSCALAR_QUO_START:XSCALAR_QUO_END] == ACCEPTED_SCALAR
assert candidate[XSCALAR_QUO_START:XSCALAR_QUO_END] == CANDIDATE_SCALAR
assert candidate[XSCALAR_QUO_END:XSCALAR_QUO_END + 16] == accepted[
    XSCALAR_QUO_END:XSCALAR_QUO_END + 16]
changed_offsets = [offset for offset in range(len(candidate))
                   if accepted[offset] != candidate[offset]]
assert changed_offsets
assert all(XSCALAR_QUO_START <= offset < XSCALAR_QUO_END
           for offset in changed_offsets)

accepted_island = instructions(accepted, XSCALAR_QUO_START, XSCALAR_QUO_END)
candidate_island = instructions(candidate, XSCALAR_QUO_START, XSCALAR_QUO_END)
assert candidate_island[-48].mnemonic == "ret"
assert [item.mnemonic for item in candidate_island[-47:]] == ["nop"] * 47
assert [item.mnemonic for item in candidate_island].count("fdiv") == 1
assert [item.mnemonic for item in candidate_island].count("fld") == 2
assert [item.mnemonic for item in candidate_island].count("fstp") == 2
candidate_calls = [
    (item.address, direct_target(item)) for item in candidate_island
    if item.group(CS_GRP_CALL)]
assert candidate_calls == [
    (0x25474, 0x254AD),
    (0x25479, 0x24EE6),
    (0x25487, 0x254AD),
]
assert [(item.mnemonic, item.op_str) for item in accepted_island[-10:]] == [
    ("ret", ""), ("mov", "eax, dword ptr [edi + 0x2678]"),
    ("mov", "ebx, dword ptr [edi + 0x2688]"), ("xor", "eax, ebx"),
    ("shl", "eax, 0x1f"), ("or", "eax, 0x7ff00000"),
    ("mov", "dword ptr [edi + 0x2624], eax"),
    ("mov", "dword ptr [edi + 0x2620], 0"),
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
assert any(item.mnemonic == "fdiv" and item.op_str == "qword ptr [esi + 8]"
           for item in candidate_island)
assert sum(item.mnemonic == "fstp" and item.op_str == "xword ptr [edx]"
           for item in candidate_island) == 2
assert not [item for item in candidate_island
            if item.mnemonic == "fld" and item.op_str == "xword ptr [edx]"]
assert not [item for item in candidate_island
            if item.mnemonic == "fstp" and item.op_str == "qword ptr [esi]"]
assert sum(item.mnemonic == "inc" and item.op_str == "dword ptr [edx + 0x30]"
           for item in candidate_island) == 2
assert sum(item.mnemonic == "cmp" and item.op_str == "ecx, 0xffe00000"
           for item in candidate_island) == 2

accepted_code = instructions(accepted, header["code_start"], header["physical_end"])
candidate_code = instructions(candidate, header["code_start"], header["physical_end"])
accepted_by_address = {item.address: item for item in accepted_code}
candidate_by_address = {item.address: item for item in candidate_code}
assert XSCALAR_QUO_START in candidate_by_address
assert XSCALAR_ADD in candidate_by_address
assert PUBLIC_FQUO in candidate_by_address

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
accepted_fdiv_addresses = [
    item.address for item in accepted_code if item.mnemonic == "fdiv"]
candidate_fdiv_addresses = [
    item.address for item in candidate_code if item.mnemonic == "fdiv"]
candidate_hardware_fdiv = next(
    item.address for item in candidate_island if item.mnemonic == "fdiv")
assert candidate_fdiv_addresses == sorted(
    accepted_fdiv_addresses + [candidate_hardware_fdiv])

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
    if (target is None or not (XSCALAR_QUO_START <= target < XSCALAR_QUO_END)
            or XSCALAR_QUO_START <= item.address < XSCALAR_QUO_END):
        continue
    record = (item.address, item.mnemonic, target)
    island_entries.append(record)
    if target != XSCALAR_QUO_START:
        interior_entries.append(record)
assert island_entries == [(FQUO_BODY, "call", XSCALAR_QUO_START)]
assert interior_entries == []

# The public wrapper, its body, and all 85 callers remain byte-exact.
public_wrapper = instructions(candidate, PUBLIC_FQUO, PUBLIC_FQUO_END)
assert [(item.mnemonic, direct_target(item)) for item in public_wrapper] == [
    ("pushal", None), ("call", FQUO_BODY), ("popal", None),
    ("mov", None), ("ret", None),
]
assert public_wrapper[3].op_str == "ebp, 0x646f6e65"
fquo_body = instructions(candidate, FQUO_BODY, FQUO_BODY_END)
assert [(item.mnemonic, direct_target(item)) for item in fquo_body] == [
    ("call", XSCALAR_QUO_START), ("mov", None), ("ret", None)]
assert fquo_body[1].op_str == "ebp, 0x646f6e65"
assert accepted[PUBLIC_FQUO:FQUO_BODY_END] == candidate[
    PUBLIC_FQUO:FQUO_BODY_END]
accepted_public_calls = [item.address for item in accepted_code
                         if item.group(CS_GRP_CALL)
                         and direct_target(item) == PUBLIC_FQUO]
candidate_public_calls = [item.address for item in candidate_code
                          if item.group(CS_GRP_CALL)
                          and direct_target(item) == PUBLIC_FQUO]
assert accepted_public_calls == candidate_public_calls
assert len(candidate_public_calls) == 85

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

# Prove the package x87 invariant compositionally instead of assuming selected
# indirect-only routine entries are empty. Partition the decoded package at the
# executable entry, every direct transfer target, and every sequential block
# after RET/JMP. Analyze each block from depth zero, then require every generated
# call, jump, return, and physical exit itself to occur at depth zero. Those
# transfer results establish the entry premise for every successor block,
# including all unresolved indirect dispatches.
x87_push = {"fld", "fild"}
x87_pop = {"fstp", "fistp", "fcomp"}
x87_neutral = {"fadd", "fdiv", "fmul", "fsub", "fnstsw", "wait"}
assert {item.mnemonic for item in candidate_code
        if item.mnemonic.startswith("f") or item.mnemonic == "wait"} <= (
            x87_push | x87_pop | x87_neutral)
direct_transfer_roots = {
    direct_target(item) for item in candidate_code
    if (item.group(CS_GRP_CALL) or item.group(CS_GRP_JUMP))
    and direct_target(item) in candidate_by_address}
post_terminator_roots = set()
for index, item in enumerate(candidate_code[:-1]):
    successor = candidate_code[index + 1]
    if ((item.mnemonic.startswith("ret") or item.mnemonic == "jmp")
            and item.address + item.size == successor.address):
        post_terminator_roots.add(successor.address)
control_flow_roots = ({header["code_entry"]} | direct_transfer_roots
                      | post_terminator_roots)
x87_states = 0
x87_returns = 0
x87_peak = 0
covered_x87_instructions = set()
transfer_depths = {}
fquo_entry_depths = []
for root in sorted(control_flow_roots):
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
        covered_x87_instructions.add(address)
        x87_states += 1
        item = candidate_by_address[address]
        if item.mnemonic in x87_push:
            depth += 1
        elif item.mnemonic in x87_pop:
            depth -= 1
        assert 0 <= depth <= 8, (hex(root), hex(address), item.mnemonic, depth)
        x87_peak = max(x87_peak, depth)
        target = direct_target(item)
        is_transfer = (item.group(CS_GRP_CALL) or item.group(CS_GRP_JUMP)
                       or item.mnemonic.startswith("ret"))
        if is_transfer:
            transfer_depths.setdefault(item.address, set()).add(depth)
        if item.group(CS_GRP_CALL) and target == PUBLIC_FQUO:
            fquo_entry_depths.append((root, item.address, depth))
        if item.mnemonic.startswith("ret"):
            assert depth == 0, (hex(root), hex(address), depth)
            x87_returns += 1
            continue
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
assert covered_x87_instructions == set(candidate_by_address)
package_transfer_addresses = {
    item.address for item in candidate_code
    if item.group(CS_GRP_CALL) or item.group(CS_GRP_JUMP)
    or item.mnemonic.startswith("ret")}
assert set(transfer_depths) == package_transfer_addresses
assert all(depths == {0} for depths in transfer_depths.values())
package_call_addresses = {
    item.address for item in candidate_code if item.group(CS_GRP_CALL)}
package_indirect_transfer_addresses = {
    item.address for item in candidate_code
    if (item.group(CS_GRP_CALL) or item.group(CS_GRP_JUMP))
    and direct_target(item) is None}
assert package_call_addresses <= set(transfer_depths)
assert package_indirect_transfer_addresses <= set(transfer_depths)
covered_fquo_calls = {address for _, address, _ in fquo_entry_depths}
assert covered_fquo_calls == set(candidate_public_calls)
assert all(depth == 0 for _, _, depth in fquo_entry_depths)
# These four FQuo-containing routines have no direct entry and follow a RET, so
# any package-generated entry is necessarily one of the proven-empty indirect
# transfers. The fifth historical root, 0x9505E, is a direct branch target.
indirect_only_fquo_roots = {0x2905A, 0x3A751, 0x461AC, 0x461E9}
for root in indirect_only_fquo_roots:
    prior = candidate_code[candidate_code.index(candidate_by_address[root]) - 1]
    assert prior.mnemonic.startswith("ret")
    assert prior.address + prior.size == root
    assert root not in direct_transfer_roots
assert 0x9505E in direct_transfer_roots

# Fixed-back XREJ binding and complete fixed-address inventory for the full
# 16-byte XS/XE/XMH/XML image. The candidate now reproduces the portable
# terminal image exactly, so correctness no longer depends on proving that this
# package cannot observe the scratch registers.
assert accepted[0x23907:0x23907 + len(XREJ_PREREQUISITE)] == XREJ_PREREQUISITE
assert XSCALAR_QUO_END - 0x23907 == apply["PREREQUISITE_DISTANCE"]
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
            if XS_DISPLACEMENT <= displacement < XS_DISPLACEMENT + 16:
                fixed_xscratch_references[displacement] += 1
assert set(fixed_xscratch_references) == {
    XS_DISPLACEMENT, XS_DISPLACEMENT + 4,
    XS_DISPLACEMENT + 8, XS_DISPLACEMENT + 12}

# Code-label materialization is absent in the package's established common forms.
materialized_address_hits = {}
for name, address in {
        "xscalar_quo": XSCALAR_QUO_START,
        "xscalar_add": XSCALAR_ADD,
        "public_fquo": PUBLIC_FQUO,
        "fquo_body": FQUO_BODY}.items():
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
        accepted_hits = [offset for offset in range(len(accepted) - 3)
                         if accepted[offset:offset + 4] == packed]
        materialized_address_hits[name][form_name] = hits
        assert hits == accepted_hits
        if hits:
            # These three unchanged byte-pattern coincidences are the rel32
            # displacements of conditional jumps, not materialized addresses.
            assert (name, form_name, hits) == (
                "xscalar_add", "code_relative", [0x4C063, 0x4C0B3, 0x82FBD])
            for offset in hits:
                containing = candidate_by_address[offset - 1]
                assert containing.group(CS_GRP_JUMP)
                assert containing.address + 1 == offset
indirect_transfers = [
    item for item in candidate_code
    if (item.group(CS_GRP_CALL) or item.group(CS_GRP_JUMP))
    and direct_target(item) is None]
assert len(indirect_transfers) == 259
assert sum(item.group(CS_GRP_CALL) for item in indirect_transfers) == 251
assert sum(item.group(CS_GRP_JUMP) for item in indirect_transfers) == 8

# Independently model both compiler gates. No mutation may occur unless the
# complete 237-byte island, 44-byte prior-label distance, and fixed-back
# 42-byte prerequisite all match.
def lower(prefix, island, prerequisite=XREJ_PREREQUISITE,
          marker_present=True, i386m=True, distance=44):
    original = prefix + island
    if not marker_present or not i386m or distance != apply["PRIOR_LABEL_DISTANCE"]:
        return original, False
    if island != ACCEPTED_SCALAR or prerequisite != XREJ_PREREQUISITE:
        return original, False
    return prefix + CANDIDATE_SCALAR, True


prefix = bytes(range(32))
positive, changed = lower(prefix, ACCEPTED_SCALAR)
assert changed and positive == prefix + CANDIDATE_SCALAR
for kwargs in ({"marker_present": False}, {"i386m": False}, {"distance": 43}):
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
assert model["all_finite_nonzero_binary64_pair_equivalence_algebraic"]
assert model["portable_tiny_and_overflow_xrej_policy_exact"]
assert model["final_spill_overflow_detection_present"]
assert model["final_spill_uses_unchanged_portable_xtof64"]
assert model["terminal_x_image_matches_portable_all_paths"]
assert model["source_grounded_proof_lemmas"][
    "terminal_x_image_matches_after_every_path"]
assert model["public_a_through_e_preserved_by_unchanged_wrapper"]
assert model["candidate_x87_stack_net_change"] == 0
assert build["compiler_three_stage_fixpoint"]
assert build["marker_only_i386m_matches_accepted_byte_exactly"]
assert build["non_i386m_output_comparison_run"]
assert build["non_i386m_outputs_byte_exact"]
assert build["candidate_i386m_game_sha256"] == EXPECTED_CANDIDATE_SHA256

report = {
    "schema": 1,
    "task": 237,
    "status": "pass",
    "accepted_sha256": apply["ACCEPTED_GAME_SHA256"],
    "candidate_sha256": EXPECTED_CANDIDATE_SHA256,
    "candidate_compiler_sha256": EXPECTED_CANDIDATE_COMPILER_SHA256,
    "executable_bytes": len(candidate),
    "header_and_code_boundaries_exact": True,
    "package_bytes_outside_island_exact": True,
    "changed_byte_values": len(changed_offsets),
    "unexpected_changes": 0,
    "xscalar_quo_start": hex(XSCALAR_QUO_START),
    "xscalar_quo_end": hex(XSCALAR_QUO_END),
    "xscalar_add_unchanged_start": hex(XSCALAR_ADD),
    "island_bytes": len(CANDIDATE_SCALAR),
    "accepted_island_instructions": len(accepted_island),
    "candidate_island_instructions": len(candidate_island),
    "candidate_hardware_fdiv": True,
    "candidate_p64_tbyte_materialization": True,
    "candidate_direct_p53_qword_spill": False,
    "candidate_final_spill_uses_portable_xtof64": True,
    "candidate_internal_unpack_calls": 2,
    "candidate_portable_xtof64_calls": 1,
    "candidate_unreachable_nop_bytes": 47,
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
    "public_fquo_wrapper": hex(PUBLIC_FQUO),
    "public_fquo_wrapper_byte_exact": True,
    "fquo_body": hex(FQUO_BODY),
    "fquo_body_byte_exact": True,
    "public_fquo_call_sites": len(candidate_public_calls),
    "xscalar_quo_direct_callers": len(island_entries),
    "public_integer_register_save_restore_exact": True,
    "public_ebp_terminal_state_exact": True,
    "caller_eflags_successor_states": flag_audit_states,
    "caller_eflags_successor_steps": flag_audit_steps,
    "all_direct_fquo_callers_redefine_before_flag_observation": True,
    "package_control_flow_roots_analyzed": len(control_flow_roots),
    "package_direct_transfer_roots_analyzed": len(direct_transfer_roots),
    "package_post_terminator_roots_analyzed": len(post_terminator_roots),
    "indirect_only_fquo_roots_analyzed": [
        hex(value) for value in sorted(indirect_only_fquo_roots)],
    "all_public_fquo_call_sites_covered_by_x87_depth_analysis": len(
        covered_fquo_calls),
    "package_x87_cfg_states": x87_states,
    "package_x87_instructions_covered": len(covered_x87_instructions),
    "package_x87_returns": x87_returns,
    "package_x87_peak": x87_peak,
    "package_calls_proven_at_empty_x87_depth": len(package_call_addresses),
    "package_indirect_transfers_proven_at_empty_x87_depth": len(
        package_indirect_transfer_addresses),
    "all_public_fquo_calls_enter_with_empty_x87_stack": True,
    "all_generated_transfer_boundaries_have_empty_x87_stack": True,
    "x87_entry_induction_complete_for_decoded_package": True,
    "xrej_fixed_back_prerequisite_bytes": len(XREJ_PREREQUISITE),
    "xrej_fixed_back_prerequisite_distance": apply["PREREQUISITE_DISTANCE"],
    "xscratch_fixed_reference_range_bytes": 16,
    "xscratch_fixed_references": dict(fixed_xscratch_references),
    "candidate_xscratch_terminal_state_equals_portable": True,
    "terminal_x_identity_proven_for_all_modeled_paths": True,
    "scratch_observer_absence_required_for_correctness": False,
    "indexed_edi_operands": indexed_edi_operands,
    "indexed_alias_ranges_exhaustively_proven": False,
    "materialized_code_label_address_hits": materialized_address_hits,
    "checked_materialized_address_forms_with_byte_pattern_hits": 1,
    "materialized_code_label_operands_found": 0,
    "unchanged_rel32_jump_false_positive_hits": [0x4C063, 0x4C0B3, 0x82FBD],
    "indirect_calls_present": 251,
    "indirect_jumps_present": 8,
    "indirect_transfer_targets_exhaustively_resolved": False,
    "all_finite_nonzero_binary64_pair_equivalence_algebraic": True,
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
