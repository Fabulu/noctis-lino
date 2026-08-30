from pathlib import Path
import hashlib
import json
import re
import struct
import subprocess

from capstone import Cs, CS_ARCH_X86, CS_GRP_CALL, CS_GRP_JUMP, CS_MODE_32
from capstone.x86_const import X86_OP_IMM

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/restoring-flag-chain-20260830"
SOURCE = ROOT / "work/fp/fpsoft.txt"
CANDIDATE_SOURCE = EVIDENCE / "candidate/fpsoft.txt"
CANDIDATE_EXE = EVIDENCE / "candidate/vhgame.exe"
OUTPUT = EVIDENCE / "reference-audit.json"
MASK = 0xFFFFFFFF
ISLAND_START = 0x258C5
ISLAND_END = 0x2599D

LABELS = {
    "XRoot restoring accept": 0x25909,
    "XRoot restoring low borrow": 0x25923,
    "XRoot restoring low subtract": 0x25928,
    "XRoot restoring middle borrow": 0x2595A,
    "XRoot restoring middle no borrow": 0x25974,
    "XRoot restoring high subtract": 0x25989,
}
EXPECTED_SOURCE_COUNTS = {
    "XRoot restoring accept": 3,
    "XRoot restoring low borrow": 2,
    "XRoot restoring low subtract": 2,
    "XRoot restoring middle borrow": 2,
    "XRoot restoring middle no borrow": 3,
    "XRoot restoring high subtract": 2,
}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def lino_header(data):
    marker = data.index(b"LNLMInit")
    code_units = u32(data, marker + 0x34)
    physical_end = u32(data, marker + 0x40)
    return physical_end - 4 * code_units, physical_end


def direct_target(instruction):
    if not (instruction.group(CS_GRP_CALL) or instruction.group(CS_GRP_JUMP)):
        return None
    immediate = [operand.imm for operand in instruction.operands
                 if operand.type == X86_OP_IMM]
    assert len(immediate) <= 1
    return immediate[0] & MASK if immediate else None


# Search only tracked shared-work Lino sources, explicitly excluding every
# protected named source and all temporary path patterns. Exact symbol names are
# the only query; this is a bounded reference audit, not a broad content sweep.
pattern = "XRoot restoring (accept|low borrow|low subtract|middle borrow|middle no borrow|high subtract)"
command = [
    "git", "grep", "-n", "-E", pattern, "--",
    ":(glob)work/**/*.txt",
    ":(exclude)work/vhstar.txt",
    ":(exclude)work/pgmem.txt",
    ":(exclude,glob)work/**/.tmp-*",
]
completed = subprocess.run(command, cwd=ROOT, check=True,
                           capture_output=True, text=True)
source_hits = [line for line in completed.stdout.splitlines() if line]
assert len(source_hits) == sum(EXPECTED_SOURCE_COUNTS.values())
assert all(line.startswith("work/fp/fpsoft.txt:") for line in source_hits)
for name, expected in EXPECTED_SOURCE_COUNTS.items():
    assert sum(name in line for line in source_hits) == expected

accepted_text = SOURCE.read_text(encoding="utf-8")
candidate_text = CANDIDATE_SOURCE.read_text(encoding="utf-8")
assert candidate_text.replace(
    '\t"XRoot exact i386m restoring flag chain"\n', "") == accepted_text
for name, expected in EXPECTED_SOURCE_COUNTS.items():
    assert accepted_text.count(name) == candidate_text.count(name) == expected
# Every reference/definition lies in the exact scalar island immediately before
# the marker; no tracked unprotected work source names an overwritten label.
root_slice = accepted_text[
    accepted_text.index("( Accept the next root bit iff remainder >= trial. )"):
    accepted_text.index("( Set the admitted low root bit. )")]
for name, expected in EXPECTED_SOURCE_COUNTS.items():
    assert root_slice.count(name) == expected

candidate = CANDIDATE_EXE.read_bytes()
code_start, code_end = lino_header(candidate)
engine = Cs(CS_ARCH_X86, CS_MODE_32)
engine.detail = True
instructions = list(engine.disasm(candidate[code_start:code_end], code_start))
assert instructions and instructions[-1].address + instructions[-1].size == code_end

external_direct_entries = []
all_direct_entries = []
indirect_control_transfers = []
immediate_materializations = []
for item in instructions:
    target = direct_target(item)
    if (item.group(CS_GRP_CALL) or item.group(CS_GRP_JUMP)) and target is None:
        indirect_control_transfers.append((item.address, item.mnemonic, item.op_str))
    if target in LABELS.values():
        record = (item.address, item.mnemonic, target)
        all_direct_entries.append(record)
        if not (ISLAND_START <= item.address < ISLAND_END):
            external_direct_entries.append(record)
    for operand in item.operands:
        if operand.type == X86_OP_IMM and (operand.imm & MASK) in LABELS.values():
            immediate_materializations.append(
                (item.address, item.mnemonic, operand.imm & MASK))

assert external_direct_entries == []
assert all_direct_entries == []
assert immediate_materializations == []

# Lino code-pointer initializers in this package use physical code offsets. Scan
# every byte alignment, including non-code payload, for each overwritten label's
# little-endian address. The transformed island itself is excluded because old
# scalar branch displacements are relative encodings, not absolute pointers.
raw_materializations = {}
for name, address in LABELS.items():
    needle = struct.pack("<I", address)
    offsets = [
        offset for offset in range(len(candidate) - 3)
        if candidate[offset:offset + 4] == needle
        and not (ISLAND_START <= offset < ISLAND_END)
    ]
    raw_materializations[name] = offsets
    assert offsets == []

compiler_text = (EVIDENCE / "candidate/compiler114m.txt").read_text(
    encoding="ascii")
assert compiler_text.count("xrootexacti386mrestoringflagchain") == 1
marker_dispatch = compiler_text[
    compiler_text.index('"exit label"'):
    compiler_text.index('"register code label"')]
assert "? [i386m target] != yes -> note prior code label;" in marker_dispatch
assert marker_dispatch.index("? [i386m target] != yes") < marker_dispatch.index(
    "pp xroot flag marker")

report = {
    "schema": 1,
    "task": 231,
    "status": "pass",
    "scope": (
        "current selected tracked work Lino source and generated i386m package; "
        "complete shipping dependency closure remains deferred"),
    "tracked_source_symbol_hits": len(source_hits),
    "tracked_source_hits_all_in_fpsoft_island": True,
    "protected_sources_searched": False,
    "temporary_paths_searched": False,
    "overwritten_internal_labels": {
        name: hex(address) for name, address in LABELS.items()
    },
    "external_direct_entries_to_overwritten_labels": 0,
    "all_direct_entries_to_overwritten_labels": 0,
    "instruction_immediate_materializations": 0,
    "package_raw_physical_address_materializations": 0,
    "whole_program_indirect_control_transfers_reported_unresolved": len(
        indirect_control_transfers),
    "current_package_has_reference_to_overwritten_label": False,
    "candidate_padding_current_package_unreachable": True,
    "lowering_claim_scope": "current exact selected i386m production package only",
    "non_i386m_suppression": "structurally guarded in compiler source",
    "non_i386m_output_comparison_run": False,
    "complete_shipping_dependency_closure_audited": False,
}
OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
