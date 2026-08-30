from pathlib import Path
from collections import Counter
import hashlib
import itertools
import json
import random
import runpy

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86_const import X86_OP_IMM

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/restoring-flag-chain-20260830"
ACCEPTED = EVIDENCE / "accepted"
CANDIDATE = EVIDENCE / "candidate"
MASK = 0xFFFFFFFF
ISLAND_START = 0x258C5
ISLAND_END = 0x2599D
REJECT_TARGET = 0x259B9

apply = runpy.run_path(str(EVIDENCE / "apply_candidate.py"))
SCALAR_ISLAND = apply["SCALAR_ISLAND"]
CANDIDATE_ISLAND = apply["CANDIDATE_ISLAND"]
REACHABLE_CANDIDATE = apply["REACHABLE_CANDIDATE"]


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def parity_even_byte(value):
    return ((value & 0xFF).bit_count() & 1) == 0


def sub32(left, right):
    left &= MASK
    right &= MASK
    result = (left - right) & MASK
    flags = {
        "CF": left < right,
        "PF": parity_even_byte(result),
        "AF": bool((left ^ right ^ result) & 0x10),
        "ZF": result == 0,
        "SF": bool(result & 0x80000000),
        "OF": bool((left ^ right) & (left ^ result) & 0x80000000),
    }
    return result, flags


def accepted_source(state):
    high, middle, low, trial_high, trial_middle, trial_low, incoming_e = state
    trace = []
    if high != trial_high:
        a, b = high, trial_high
        _, flags = sub32(a, b)
        if high < trial_high:
            return "reject-high", trace, (a, b, trial_middle, trial_low, incoming_e), flags
    elif middle != trial_middle:
        a, b = middle, trial_middle
        _, flags = sub32(a, b)
        if middle < trial_middle:
            return "reject-middle", trace, (a, b, trial_middle, trial_low, incoming_e), flags
    else:
        a, b = low, trial_low
        _, flags = sub32(a, b)
        if low < trial_low:
            return "reject-low", trace, (a, b, trial_middle, trial_low, incoming_e), flags

    low_borrow = int(low < trial_low)
    low_result, _ = sub32(low, trial_low)
    trace.append(("srm0", low_result))

    if middle > trial_middle:
        middle_borrow = 0
    elif middle < trial_middle:
        middle_borrow = 1
    else:
        middle_borrow = low_borrow
    middle_once, _ = sub32(middle, trial_middle)
    middle_result, _ = sub32(middle_once, low_borrow)
    trace.append(("srm1", middle_result))

    high_once, _ = sub32(high, trial_high)
    high_result, flags = sub32(high_once, middle_borrow)
    trace.append(("srm2", high_result))
    return (
        "accept", trace,
        (high_result, trial_middle, trial_middle, trial_low, middle_borrow),
        flags)


def candidate_flag_chain(state):
    high, middle, low, trial_high, trial_middle, trial_low, incoming_e = state
    trace = []
    if high != trial_high:
        a, b = high, trial_high
        _, flags = sub32(a, b)
        if high < trial_high:
            return "reject-high", trace, (a, b, trial_middle, trial_low, incoming_e), flags
    elif middle != trial_middle:
        a, b = middle, trial_middle
        _, flags = sub32(a, b)
        if middle < trial_middle:
            return "reject-middle", trace, (a, b, trial_middle, trial_low, incoming_e), flags
    else:
        a, b = low, trial_low
        _, flags = sub32(a, b)
        if low < trial_low:
            return "reject-low", trace, (a, b, trial_middle, trial_low, incoming_e), flags

    low_result, low_flags = sub32(low, trial_low)
    low_borrow = int(low_flags["CF"])
    trace.append(("srm0", low_result))

    full_middle_subtrahend = trial_middle + low_borrow
    middle_result = (middle - full_middle_subtrahend) & MASK
    middle_borrow = int(middle < full_middle_subtrahend)
    trace.append(("srm1", middle_result))

    # MOV ESI,0; ADC ESI,0 materializes the SBB carry without changing it
    # before ADC. The following two SUBs intentionally retain the source's
    # second-SUB flag image rather than full SBB flags.
    e = middle_borrow
    high_once, _ = sub32(high, trial_high)
    high_result, flags = sub32(high_once, e)
    trace.append(("srm2", high_result))
    return (
        "accept", trace,
        (high_result, trial_middle, trial_middle, trial_low, e),
        flags)


def check_case(state, coverage):
    accepted = accepted_source(state)
    candidate = candidate_flag_chain(state)
    assert accepted == candidate, (state, accepted, candidate)
    outcome, trace, registers, flags = candidate
    coverage[outcome] += 1
    assert set(flags) == {"CF", "PF", "AF", "ZF", "SF", "OF"}
    if outcome == "accept":
        high, middle, low, trial_high, trial_middle, trial_low, _ = state
        remainder = (high << 64) | (middle << 32) | low
        trial = (trial_high << 64) | (trial_middle << 32) | trial_low
        assert remainder >= trial
        result = remainder - trial
        assert trace == [
            ("srm0", result & MASK),
            ("srm1", (result >> 32) & MASK),
            ("srm2", (result >> 64) & MASK),
        ]
        low_borrow = int(low < trial_low)
        middle_borrow = int(middle < trial_middle + low_borrow)
        coverage[f"low-borrow-{low_borrow}"] += 1
        coverage[f"middle-borrow-{middle_borrow}"] += 1
        coverage[f"final-cf-{int(flags['CF'])}"] += 1
        assert registers[4] == middle_borrow
    else:
        assert trace == []


accepted_compiler = (ACCEPTED / "compiler114m.txt").read_bytes()
accepted_fp = (ACCEPTED / "fpsoft.txt").read_bytes()
candidate_compiler = (CANDIDATE / "compiler114m.txt").read_bytes()
candidate_fp = (CANDIDATE / "fpsoft.txt").read_bytes()
assert apply["transform_compiler"](accepted_compiler) == candidate_compiler
assert apply["transform_fp"](accepted_fp) == candidate_fp
assert candidate_fp.replace(
    b'\t"XRoot exact i386m restoring flag chain"\n', b"") == accepted_fp
assert candidate_fp.count(b'"XRoot exact i386m restoring flag chain"') == 1
assert b"VHGSIMADD = 18206" in (ACCEPTED / "vhgame.txt").read_bytes()
assert b"VHGSIMDEN = 60000" in (ACCEPTED / "vhgame.txt").read_bytes()
assert (ACCEPTED / "vhgame.txt").read_bytes().count(b"=> FSqrt;") == 14
assert len(SCALAR_ISLAND) == len(CANDIDATE_ISLAND) == ISLAND_END - ISLAND_START
assert CANDIDATE_ISLAND.startswith(REACHABLE_CANDIDATE)
assert CANDIDATE_ISLAND[len(REACHABLE_CANDIDATE):] == bytes([0x90]) * 97
assert (ACCEPTED / "vhgame.exe").read_bytes()[ISLAND_START:ISLAND_END] == SCALAR_ISLAND

md = Cs(CS_ARCH_X86, CS_MODE_32)
md.detail = True
scalar_instructions = list(md.disasm(SCALAR_ISLAND, ISLAND_START))
candidate_instructions = list(md.disasm(CANDIDATE_ISLAND, ISLAND_START))
reachable_instructions = list(md.disasm(REACHABLE_CANDIDATE, ISLAND_START))
assert len(scalar_instructions) == 49
assert len(reachable_instructions) == 28
assert len(candidate_instructions) == 125
assert [item.mnemonic for item in reachable_instructions].count("cmp") == 3
assert [item.mnemonic for item in scalar_instructions].count("cmp") == 9
assert [item.mnemonic for item in reachable_instructions].count("sbb") == 1
assert [item.mnemonic for item in scalar_instructions].count("sbb") == 0
assert [item.mnemonic for item in reachable_instructions].count("jmp") == 1
assert reachable_instructions[-1].mnemonic == "jmp"
assert reachable_instructions[-1].operands[0].type == X86_OP_IMM
assert reachable_instructions[-1].operands[0].imm == ISLAND_END
branch_targets = [
    item.operands[0].imm
    for item in reachable_instructions
    if item.mnemonic in ("ja", "jb")
]
assert branch_targets == [
    0x258FD, REJECT_TARGET,
    0x258FD, REJECT_TARGET,
    REJECT_TARGET,
]

coverage = Counter()
edge = [
    0, 1, 2, 0x0F, 0x10, 0x7FFFFFFF, 0x80000000,
    0xFFFFFFFE, 0xFFFFFFFF,
]
# Aligned edges exercise equality and all low/middle borrow interactions.
for high, middle, low, trial_high, trial_middle, trial_low in itertools.product(
        edge[:5], edge[:5], edge[:5], edge[:3], edge[:3], edge[:3]):
    check_case((high, middle, low, trial_high, trial_middle, trial_low,
                edge[(high ^ middle ^ low) % len(edge)]), coverage)

# Construct every lexicographic exit explicitly near arithmetic boundaries.
engineered = []
for value in edge:
    lower = (value - 1) & MASK
    higher = (value + 1) & MASK
    engineered.extend([
        (lower, value, value, value, value, value, 0xA5A5A5A5),
        (higher, value, value, value, value, value, 0x5A5A5A5A),
        (value, lower, value, value, value, value, value),
        (value, higher, value, value, value, value, value),
        (value, value, lower, value, value, value, value),
        (value, value, higher, value, value, value, value),
        (value, value, value, value, value, value, value),
    ])
for state in engineered:
    check_case(state, coverage)

rng = random.Random(0x231F1A6)
for _ in range(250_000):
    state = tuple(rng.getrandbits(32) for _ in range(7))
    check_case(state, coverage)

for required in (
        "accept", "reject-high", "reject-middle", "reject-low",
        "low-borrow-0", "low-borrow-1",
        "middle-borrow-0", "middle-borrow-1",
        "final-cf-0"):
    assert coverage[required] > 0, (required, coverage)
assert coverage["final-cf-1"] == 0

report = {
    "schema": 1,
    "task": 231,
    "status": "pass",
    "source_exact_transform": True,
    "common_lino_change_is_zero_byte_marker_only": True,
    "compiler_change_scope": "i386m fail-closed exact marker lowering",
    "raw_target_machine_block_added_to_shipping_lino": False,
    "complete_shipping_dependency_closure_audited": False,
    "simulation_constants": [18206, 60000],
    "static_fsqrt_call_sites": 14,
    "cases": sum(coverage[key] for key in (
        "accept", "reject-high", "reject-middle", "reject-low")),
    "coverage": dict(sorted(coverage.items())),
    "ordered_remainder_write_trace_exact": True,
    "terminal_a_through_e_exact": True,
    "terminal_x86_cf_pf_af_zf_sf_of_exact": True,
    "accepted_final_cf_always_clear": True,
    "reject_paths_write_nothing": True,
    "accepted_96_bit_result_exact": True,
    "accepted_scalar_instructions": len(scalar_instructions),
    "candidate_reachable_instructions": len(reachable_instructions),
    "accepted_compare_instructions": 9,
    "candidate_compare_instructions": 3,
    "candidate_sbb_instructions": 1,
    "island_bytes": len(CANDIDATE_ISLAND),
    "candidate_unreachable_nop_bytes": 97,
}
(EVIDENCE / "model.json").write_text(
    json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
