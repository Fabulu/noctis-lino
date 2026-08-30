from pathlib import Path
import hashlib
import json
import runpy
import struct

from capstone import Cs, CS_ARCH_X86, CS_MODE_32

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/register-trial-restoring-fsqrt-20260830"
ACCEPTED_EXE = EVIDENCE / "accepted/vhgame.exe"
CANDIDATE_EXE = EVIDENCE / "candidate/vhgame.exe"
ACCEPTED_FP = EVIDENCE / "accepted/fpsoft.txt"
CANDIDATE_FP = EVIDENCE / "candidate/fpsoft.txt"
OUTPUT = EVIDENCE / "production-layout.json"
EXPECTED_ACCEPTED_EXE_SHA256 = (
    "e18e8eb45ac0bc03aa2ee1f51ce1ae54f6ee00a0e8a7cef24cbd3adebcdf32a0")
EXPECTED_CANDIDATE_EXE_SHA256 = (
    "33f235c60cee4852b73723830cf691bf205d21f0bd054a746705fb66a3a420c6")
EXPECTED_ACCEPTED_FP_SHA256 = (
    "063ecf40b0faab3b2779d8ff159b8fa815eec7b397de0d47e68223841e2a59cc")
EXPECTED_CANDIDATE_FP_SHA256 = (
    "8fee66095ee27f0c7da81900f34603d2bd4d7d60c356ce51a0cebcb158fc291d")
EXPECTED_COMPILER_SHA256 = (
    "cfb39efc611dc96eab47f24c70cc7447a11f3b7cd874c49bfeb4934a42e67e87")
EXPECTED_CPU_PACK_SHA256 = (
    "1dd1433597c42e30b13bd55bfd02c19ebe465f3e020e4878906f66e7bfcdc4b7")
ROOT_START = 0x256F1
ISLAND_END = 0x25B49
SCALAR_ROOT_CALL = 0x256C7
PUBLIC_FSQRT = 0x27F02
SCALAR_SQRT = 0x2566A
RESTORING_LOOP = 0x257FA
FINAL_DECODE = 0x259BA
FUNCTIONAL_RETURN = 0x25B17
WORKSPACE = {
    "srd0": 0x27A4,
    "srd1": 0x27A8,
    "srd2": 0x27AC,
    "srd3": 0x27B0,
    "sqrh": 0x27B4,
    "sqrl": 0x27B8,
    "sqmh": 0x27BC,
    "sqml": 0x27C0,
    "sqcarry": 0x27C4,
    "sqstep": 0x27C8,
    "srm0": 0x27CC,
    "srm1": 0x27D0,
    "srm2": 0x27D4,
    "srm3": 0x27D8,
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


def instructions(data, start, end):
    result = list(ENGINE.disasm(data[start:end], start))
    assert result
    assert result[0].address == start
    assert result[-1].address + result[-1].size == end
    return result


def direct_target(instruction):
    if instruction.mnemonic != "call" and not instruction.mnemonic.startswith("j"):
        return None
    try:
        return int(instruction.op_str, 0)
    except ValueError:
        return None


def exact(mapping, addresses, expected):
    actual = [(mapping[address].mnemonic, mapping[address].op_str)
              for address in addresses]
    assert actual == expected


ENGINE = Cs(CS_ARCH_X86, CS_MODE_32)
accepted = ACCEPTED_EXE.read_bytes()
candidate = CANDIDATE_EXE.read_bytes()
accepted_fp = ACCEPTED_FP.read_bytes()
candidate_fp = CANDIDATE_FP.read_bytes()
assert sha256(accepted) == EXPECTED_ACCEPTED_EXE_SHA256
assert sha256(candidate) == EXPECTED_CANDIDATE_EXE_SHA256
assert sha256(accepted_fp) == EXPECTED_ACCEPTED_FP_SHA256
assert sha256(candidate_fp) == EXPECTED_CANDIDATE_FP_SHA256
for path in (EVIDENCE / "accepted/compiler114m.exe",
             ROOT / "main/lib/gen/compiler114m.exe"):
    assert sha256(path.read_bytes()) == EXPECTED_COMPILER_SHA256
for path in (EVIDENCE / "accepted/i386m.bin", ROOT / "main/cpu/i386m.bin"):
    assert sha256(path.read_bytes()) == EXPECTED_CPU_PACK_SHA256
assert (ROOT / "work/fp/fpsoft.txt").read_bytes() == candidate_fp
assert (ROOT / "work/vhgame.exe").read_bytes() == candidate
transform = runpy.run_path(str(EVIDENCE / "apply_candidate.py"))["transform"]
assert candidate_fp == transform(accepted_fp)
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

# The transform remains inside the established root-helper island. Exact bytes
# before and after it prove that the package header, all callers, every later
# routine address, and every payload remain unchanged.
assert accepted[:ROOT_START] == candidate[:ROOT_START]
assert accepted[ISLAND_END:] == candidate[ISLAND_END:]
differences = [
    offset for offset, (left, right) in enumerate(zip(accepted, candidate))
    if left != right
]
assert len(differences) == 739
assert differences[0] == 0x257A8
assert differences[-1] == 0x25B48
assert all(ROOT_START <= offset < ISLAND_END for offset in differences)

accepted_code = instructions(
    accepted, expected_header["code_start"], expected_header["physical_end"])
candidate_code = instructions(
    candidate, expected_header["code_start"], expected_header["physical_end"])
assert len(accepted_code) == 93_581
assert len(candidate_code) == 93_594
accepted_map = {item.address: item for item in accepted_code}
candidate_map = {item.address: item for item in candidate_code}

# The public FSqrt entry remains an exact save/call/restore wrapper around
# XScalarSqrt. pushal/popal preserve every public A/B/C/D/E register while the
# helper privately uses C:D:E for its recurrence.
for mapping in (accepted_map, candidate_map):
    exact(mapping,
          [PUBLIC_FSQRT, PUBLIC_FSQRT + 1, PUBLIC_FSQRT + 6],
          [("pushal", ""), ("call", hex(SCALAR_SQRT)), ("popal", "")])

# XScalarSqrt still has one external direct entry to XRootCore, exactly at the
# helper start. There are no calls in the helper and no external entries to an
# interior instruction.
for mapping in (accepted_map, candidate_map):
    call = mapping[SCALAR_ROOT_CALL]
    assert call.mnemonic == "call"
    assert direct_target(call) == ROOT_START
external_entries = []
for item in candidate_code:
    target = direct_target(item)
    if target is None:
        continue
    if not (ROOT_START <= item.address < ISLAND_END) and ROOT_START <= target < ISLAND_END:
        external_entries.append((item.address, item.mnemonic, target))
assert external_entries == [(SCALAR_ROOT_CALL, "call", ROOT_START)]

accepted_root = instructions(accepted, ROOT_START, ISLAND_END)
candidate_root = instructions(candidate, ROOT_START, ISLAND_END)
assert len(accepted_root) == 211
assert len(candidate_root) == 224
assert not [item for item in accepted_root if item.mnemonic == "call"]
assert not [item for item in candidate_root if item.mnemonic == "call"]
assert all(
    direct_target(item) is None or ROOT_START <= direct_target(item) < ISLAND_END
    for item in candidate_root
)

# The buffered radicand schedule is byte-for-byte represented by one direct
# sqmh load/store in the hot loop, a sixteen-pair counter, and one cold dynamic
# load/clear site. Runtime loop counts are proved by the model: 64 direct shifts,
# three handoffs, three clears, and four pointer decrements.
exact(candidate_map,
      [0x257A8, 0x257AD, 0x257B2, 0x257BC, 0x257C6,
       0x257D0, 0x257DA, 0x257E0, 0x257E6, 0x257F0,
       0x257FA, 0x25800, 0x25802, 0x25805, 0x2580B, 0x2580D, 0x25810],
      [("mov", "ecx, 0"),
       ("mov", "edx, 1"),
       ("mov", "dword ptr [edi + 0x27cc], 0"),
       ("mov", "dword ptr [edi + 0x27d0], 0"),
       ("mov", "dword ptr [edi + 0x27d4], 0"),
       ("mov", "dword ptr [edi + 0x27c8], 0x9ec"),
       ("mov", "eax, dword ptr [edi + 0x27b0]"),
       ("mov", "dword ptr [edi + 0x27bc], eax"),
       ("mov", "dword ptr [edi + 0x27b0], 0"),
       ("mov", "dword ptr [edi + 0x27c0], 0x10"),
       ("mov", "eax, dword ptr [edi + 0x27bc]"),
       ("mov", "esi, eax"),
       ("shl", "eax, 2"),
       ("mov", "dword ptr [edi + 0x27bc], eax"),
       ("mov", "eax, esi"),
       ("shr", "eax, 0x1e"),
       ("mov", "esi, eax")])
assert 0x9EC * 4 == WORKSPACE["srd3"]
exact(candidate_map,
      [0x25960, 0x25966, 0x25970, 0x25976, 0x2597C, 0x25986,
       0x2598C, 0x25992, 0x25999, 0x2599F, 0x259A4, 0x259AB, 0x259B5],
      [("dec", "dword ptr [edi + 0x27c0]"),
       ("cmp", "dword ptr [edi + 0x27c0], 0"),
       ("jne", hex(RESTORING_LOOP)),
       ("dec", "dword ptr [edi + 0x27c8]"),
       ("cmp", "dword ptr [edi + 0x27c8], 0x9e9"),
       ("jl", hex(FINAL_DECODE)),
       ("mov", "ebx, dword ptr [edi + 0x27c8]"),
       ("mov", "eax, dword ptr [edi + ebx*4]"),
       ("mov", "dword ptr [edi + 0x27bc], eax"),
       ("mov", "eax, 0"),
       ("mov", "dword ptr [edi + ebx*4], eax"),
       ("mov", "dword ptr [edi + 0x27c0], 0x10"),
       ("jmp", hex(RESTORING_LOOP))])
assert 0x9E9 * 4 == WORKSPACE["srd0"]

# The generated three-word remainder shift consumes the buffered high pair in
# ESI, preserving the source order srm2:srm1:srm0 = remainder*4 + pair.
exact(candidate_map,
      [0x25812, 0x25818, 0x2581B, 0x25821, 0x25824, 0x25826,
       0x2582C, 0x25832, 0x25835, 0x2583B, 0x2583E, 0x25840,
       0x25846, 0x2584C, 0x2584F, 0x25851, 0x25853],
      [("mov", "eax, dword ptr [edi + 0x27d4]"),
       ("shl", "eax, 2"),
       ("mov", "ebx, dword ptr [edi + 0x27d0]"),
       ("shr", "ebx, 0x1e"),
       ("or", "eax, ebx"),
       ("mov", "dword ptr [edi + 0x27d4], eax"),
       ("mov", "eax, dword ptr [edi + 0x27d0]"),
       ("shl", "eax, 2"),
       ("mov", "ebx, dword ptr [edi + 0x27cc]"),
       ("shr", "ebx, 0x1e"),
       ("or", "eax, ebx"),
       ("mov", "dword ptr [edi + 0x27d0], eax"),
       ("mov", "eax, dword ptr [edi + 0x27cc]"),
       ("shl", "eax, 2"),
       ("mov", "ebx, esi"),
       ("or", "eax, ebx"),
       ("mov", "dword ptr [edi + 0x27cc], eax")])

# The root prefix never touches sqrh/sqrl in the restoring loop. C:D carries
# T=2*q+1. Each decision forms trial=2*T-1, and acceptance updates T by two.
exact(candidate_map,
      [0x25859, 0x2585B, 0x2585E, 0x25864, 0x25866, 0x25869,
       0x2586B, 0x2586D, 0x25870, 0x25872, 0x25874,
       0x25876, 0x25878, 0x2587B, 0x25880],
      [("mov", "eax, ecx"),
       ("shr", "eax, 0x1f"),
       ("mov", "dword ptr [edi + 0x27c4], eax"),
       ("mov", "eax, edx"),
       ("shr", "eax, 0x1f"),
       ("mov", "esi, eax"),
       ("mov", "eax, ecx"),
       ("shl", "eax, 1"),
       ("mov", "ebx, esi"),
       ("or", "eax, ebx"),
       ("mov", "ecx, eax"),
       ("mov", "eax, edx"),
       ("shl", "eax, 1"),
       ("sub", "eax, 1"),
       ("mov", "edx, eax")])
# Unsigned lexicographic comparison admits exactly remainder >= trial.
exact(candidate_map,
      [0x25882, 0x25888, 0x2588E, 0x25890, 0x25896, 0x25898,
       0x2589E, 0x258A4, 0x258A6, 0x258A8, 0x258AE, 0x258B0,
       0x258B6, 0x258BC, 0x258BE, 0x258C0],
      [("mov", "eax, dword ptr [edi + 0x27d4]"),
       ("mov", "ebx, dword ptr [edi + 0x27c4]"),
       ("cmp", "eax, ebx"),
       ("ja", "0x258c6"),
       ("cmp", "eax, ebx"),
       ("jb", "0x25960"),
       ("mov", "eax, dword ptr [edi + 0x27d0]"),
       ("mov", "ebx, ecx"),
       ("cmp", "eax, ebx"),
       ("ja", "0x258c6"),
       ("cmp", "eax, ebx"),
       ("jb", "0x25960"),
       ("mov", "eax, dword ptr [edi + 0x27cc]"),
       ("mov", "ebx, edx"),
       ("cmp", "eax, ebx"),
       ("jb", "0x25960")])

# The admitted path performs an exact low-to-high three-word subtraction. ESI
# carries each unsigned borrow; the middle equality case propagates an incoming
# borrow, and sqcarry supplies the trial's 65th bit to the high word.
exact(candidate_map,
      [0x258C6, 0x258CC, 0x258CE, 0x258D0, 0x258D6, 0x258DB,
       0x258E0, 0x258E5, 0x258EB, 0x258ED,
       0x258F3, 0x258F9, 0x258FB, 0x258FD, 0x25903, 0x25905,
       0x2590B, 0x25911, 0x25917, 0x2591D, 0x2591F, 0x25921,
       0x25927, 0x2592C, 0x25931, 0x25937, 0x25939, 0x2593B,
       0x25941, 0x25946, 0x2594C, 0x25952, 0x25954],
      [("mov", "eax, dword ptr [edi + 0x27cc]"),
       ("mov", "ebx, edx"),
       ("cmp", "eax, ebx"),
       ("jb", "0x258e0"),
       ("mov", "esi, 0"),
       ("jmp", "0x258e5"),
       ("mov", "esi, 1"),
       ("mov", "eax, dword ptr [edi + 0x27cc]"),
       ("sub", "eax, edx"),
       ("mov", "dword ptr [edi + 0x27cc], eax"),
       ("mov", "eax, dword ptr [edi + 0x27d0]"),
       ("mov", "ebx, ecx"),
       ("cmp", "eax, ebx"),
       ("ja", "0x25931"),
       ("cmp", "eax, ebx"),
       ("jb", "0x25917"),
       ("cmp", "esi, 0"),
       ("je", "0x25931"),
       ("mov", "eax, dword ptr [edi + 0x27d0]"),
       ("sub", "eax, ecx"),
       ("sub", "eax, esi"),
       ("mov", "dword ptr [edi + 0x27d0], eax"),
       ("mov", "esi, 1"),
       ("jmp", "0x25946"),
       ("mov", "eax, dword ptr [edi + 0x27d0]"),
       ("sub", "eax, ecx"),
       ("sub", "eax, esi"),
       ("mov", "dword ptr [edi + 0x27d0], eax"),
       ("mov", "esi, 0"),
       ("mov", "eax, dword ptr [edi + 0x27d4]"),
       ("sub", "eax, dword ptr [edi + 0x27c4]"),
       ("sub", "eax, esi"),
       ("mov", "dword ptr [edi + 0x27d4], eax")])
assert (candidate_map[0x2595A].mnemonic,
        candidate_map[0x2595A].op_str) == ("add", "edx, 2")
hot_root = instructions(candidate, RESTORING_LOOP, FINAL_DECODE)
assert not [item for item in hot_root
            if "0x27b4" in item.op_str or "0x27b8" in item.op_str]
assert sum(item.op_str == "eax, dword ptr [edi + 0x27bc]"
           for item in candidate_root) == 1
assert sum(item.op_str == "dword ptr [edi + 0x27bc], eax"
           for item in candidate_root) == 3
assert sum(item.op_str == "eax, dword ptr [edi + ebx*4]"
           for item in candidate_root) == 1
assert sum(item.op_str == "dword ptr [edi + ebx*4], eax"
           for item in candidate_root) == 1

# Decode q=T>>1 exactly once after all 64 decisions. sqcarry is the 65th trial
# bit from the final decision; the two root words each receive one final store.
exact(candidate_map,
      [0x259BA, 0x259BC, 0x259BF, 0x259C1, 0x259C4, 0x259C6,
       0x259CC, 0x259D2, 0x259D5, 0x259D7, 0x259DA, 0x259DC],
      [("mov", "eax, ecx"),
       ("shl", "eax, 0x1f"),
       ("mov", "ebx, edx"),
       ("shr", "ebx, 1"),
       ("or", "eax, ebx"),
       ("mov", "dword ptr [edi + 0x27b8], eax"),
       ("mov", "eax, dword ptr [edi + 0x27c4]"),
       ("shl", "eax, 0x1f"),
       ("mov", "ebx, ecx"),
       ("shr", "ebx, 1"),
       ("or", "eax, ebx"),
       ("mov", "dword ptr [edi + 0x27b4], eax")])
assert sum(item.op_str == "dword ptr [edi + 0x27b8], eax"
           for item in candidate_root) == 1
assert sum(item.op_str == "dword ptr [edi + 0x27b4], eax"
           for item in candidate_root) == 1
srm3_accesses = [(item.address, item.mnemonic, item.op_str)
                 for item in candidate_root if "0x27d8" in item.op_str]
assert srm3_accesses == [(0x25A2E, "mov", "dword ptr [edi + 0x27d8], eax")]

# The fixed scratch declaration remains contiguous and unchanged.
root_text = "\n".join(item.op_str for item in candidate_root)
for address in WORKSPACE.values():
    assert f"0x{address:x}" in root_text
assert sorted(WORKSPACE.values()) == list(range(0x27A4, 0x27DC, 4))

# Nine unreachable zero moves plus four increments calibrate the helper endpoint.
# The functional return precedes them; the next routine and all downstream bytes
# begin at the same 0x25b49 address as the accepted executable.
assert (candidate_map[0x25B12].mnemonic,
        candidate_map[0x25B12].op_str) == ("mov", "ebp, 0x646f6e65")
assert candidate_map[FUNCTIONAL_RETURN].mnemonic == "ret"
padding = candidate[FUNCTIONAL_RETURN + 1:ISLAND_END]
assert padding == bytes.fromhex(
    "b8 00 00 00 00 " * 9 + "40 40 40 40")
padding_instructions = instructions(candidate, FUNCTIONAL_RETURN + 1, ISLAND_END)
assert [(item.mnemonic, item.op_str) for item in padding_instructions] == (
    [("mov", "eax, 0")] * 9 + [("inc", "eax")] * 4)
padding_entries = [
    (item.address, direct_target(item)) for item in candidate_root
    if direct_target(item) is not None
    and FUNCTIONAL_RETURN < direct_target(item) < ISLAND_END
]
assert padding_entries == []
assert accepted_map[0x25B48].mnemonic == "ret"
assert accepted_map[ISLAND_END].mnemonic == candidate_map[ISLAND_END].mnemonic == "pushal"
assert accepted[ISLAND_END:ISLAND_END + 256] == candidate[ISLAND_END:ISLAND_END + 256]

model = json.loads((EVIDENCE / "model.json").read_text(encoding="utf-8"))
build = json.loads((EVIDENCE / "build.json").read_text(encoding="utf-8"))
assert model["status"] == "pass"
assert model["verifier_sha256"] == sha256(
    (EVIDENCE / "verify_model.py").read_bytes())
assert model["candidate_file_equals_exact_transform"]
assert model["accepted_source_sha256"] == EXPECTED_ACCEPTED_FP_SHA256
assert model["candidate_source_sha256"] == EXPECTED_CANDIDATE_FP_SHA256
assert model["integer_root_exact"]
assert model["mathematical_residual_exact_before_compatibility"]
assert model["accepted_private_residual_exact"]
assert model["accepted_p64_root_rounding_exact"]
assert model["p53_binary64_spill_exact"]
assert model["positive_zero_negative_and_rejection_behavior_exact"]
assert model["candidate_changes_confined_to_xrootcore"]
assert model["public_register_save_restore_source_wrapper_exact"]
assert model["non_root_fpsoft_source_exact"]
assert model["rooted_distance_and_renderer_control_source_exact"]
assert model["synchronized_runtime_state_fidelity_required_after_timing"]
assert model["simulation_constants"] == [18206, 60000]
assert model["baseline_restoring_iterations_per_positive_root"] == 64
assert model["candidate_restoring_iterations_per_positive_root"] == 64
assert model["baseline_hot_root_word_reads_per_positive_root"] == 448
assert model["candidate_hot_root_word_reads_per_positive_root"] == 0
assert model["baseline_hot_root_word_writes_per_positive_root"] == 128
assert model["candidate_hot_root_word_writes_per_positive_root"] == 0
assert model["candidate_root_trial_subtracts_per_positive_root"] == 64
assert model["candidate_final_decode_shifts"] == 4
assert model["candidate_final_decode_ors"] == 2
assert model["candidate_final_decode_root_writes"] == 2
assert model["candidate_low_trial_subtract_borrow_impossible"]
assert model["candidate_accepted_plus_two_carry_impossible"]
assert model["candidate_hot_dynamic_pointer_reads_per_positive_root"] == 0
assert model["candidate_direct_buffer_reads_per_positive_root"] == 64
assert model["candidate_direct_buffer_writes_per_positive_root"] == 64
assert model["candidate_dynamic_limb_handoffs_per_positive_root"] == 3
assert model["candidate_dynamic_limb_clears_per_positive_root"] == 3
assert model["candidate_pointer_decrements_per_positive_root"] == 4
assert build["status"] == "pass"
assert build["private_inactive_desktop"]
assert build["build_entry"] == "lino_build.ps1"
assert build["absolute_build_paths"]
assert build["warnings"] == 64
assert build["errors"] == 0
assert build["build_seconds"] == 9.5
assert build["candidate_fpsoft_sha256"] == EXPECTED_CANDIDATE_FP_SHA256
assert build["accepted_executable_sha256"] == EXPECTED_ACCEPTED_EXE_SHA256
assert build["candidate_executable_bytes"] == len(candidate)
assert build["candidate_executable_sha256"] == EXPECTED_CANDIDATE_EXE_SHA256

result = {
    "schema": 1,
    "task": 226,
    "status": "pass",
    "accepted_sha256": sha256(accepted),
    "candidate_sha256": sha256(candidate),
    "executable_size": len(candidate),
    "header_and_code_boundaries_exact": True,
    "root_helper_start": hex(ROOT_START),
    "root_helper_island_end": hex(ISLAND_END),
    "root_helper_island_bytes": ISLAND_END - ROOT_START,
    "functional_return": hex(FUNCTIONAL_RETURN),
    "package_bytes_outside_root_island_exact": True,
    "changed_byte_values": len(differences),
    "first_changed_byte": hex(differences[0]),
    "last_changed_byte": hex(differences[-1]),
    "unexpected_changes": 0,
    "helper_entry_and_endpoint_preserved": True,
    "downstream_addresses_and_bytes_exact": True,
    "external_direct_entries_to_helper": len(external_entries),
    "external_direct_entries_to_helper_interiors": 0,
    "accepted_generated_helper_calls": 0,
    "candidate_generated_helper_calls": 0,
    "public_fsqrt_generated_pushal_call_popal_exact": True,
    "generated_remainder_shift_exact": True,
    "generated_unsigned_trial_comparison_exact": True,
    "generated_borrow_subtraction_exact": True,
    "accepted_restoring_iterations_per_positive_root": 64,
    "candidate_restoring_iterations_per_positive_root": 64,
    "baseline_hot_root_word_reads_per_positive_root": 448,
    "candidate_hot_root_word_reads_per_positive_root": 0,
    "baseline_hot_root_word_writes_per_positive_root": 128,
    "candidate_hot_root_word_writes_per_positive_root": 0,
    "candidate_root_trial_subtracts_per_positive_root": 64,
    "candidate_final_decode_shifts": 4,
    "candidate_final_decode_ors": 2,
    "candidate_final_decode_root_writes": 2,
    "candidate_low_trial_subtract_borrow_impossible": True,
    "candidate_accepted_plus_two_carry_impossible": True,
    "candidate_hot_dynamic_pointer_reads_per_positive_root": 0,
    "candidate_direct_buffer_reads_per_positive_root": 64,
    "candidate_direct_buffer_writes_per_positive_root": 64,
    "candidate_dynamic_limb_handoffs_per_positive_root": 3,
    "candidate_dynamic_limb_clears_per_positive_root": 3,
    "candidate_pointer_decrements_per_positive_root": 4,
    "register_odd_trial_schedule_exact": True,
    "buffered_limb_schedule_exact": True,
    "final_root_decode_exact": True,
    "workspace_addresses": {name: hex(address) for name, address in WORKSPACE.items()},
    "workspace_addresses_unchanged": True,
    "srm3_assigned_before_first_read": True,
    "candidate_unreachable_calibration_bytes": len(padding),
    "candidate_unreachable_zero_moves": 9,
    "candidate_unreachable_increments": 4,
    "candidate_unreachable_padding_direct_entries": len(padding_entries),
    "model_bound_to_current_verifier": True,
    "integer_root_exact": True,
    "accepted_private_residual_exact": True,
    "accepted_p64_root_rounding_exact": True,
    "p53_binary64_spill_exact": True,
    "source_exact_transform": True,
    "source_boundary": "one common tracked shared-Lino closure",
    "raw_target_machine_blocks_added": False,
    "compiler_unchanged": True,
    "compiler_sha256": EXPECTED_COMPILER_SHA256,
    "cpu_pack_unchanged": True,
    "cpu_pack_sha256": EXPECTED_CPU_PACK_SHA256,
}
OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
