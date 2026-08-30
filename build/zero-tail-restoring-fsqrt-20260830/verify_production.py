from pathlib import Path
import hashlib
import json
import runpy
import struct

from capstone import Cs, CS_ARCH_X86, CS_MODE_32

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/zero-tail-restoring-fsqrt-20260830"
ACCEPTED_EXE = EVIDENCE / "accepted/vhgame.exe"
CANDIDATE_EXE = EVIDENCE / "candidate/vhgame.exe"
ACCEPTED_FP = EVIDENCE / "accepted/fpsoft.txt"
CANDIDATE_FP = EVIDENCE / "candidate/fpsoft.txt"
OUTPUT = EVIDENCE / "production-layout.json"
EXPECTED_ACCEPTED_EXE_SHA256 = (
    "e18e8eb45ac0bc03aa2ee1f51ce1ae54f6ee00a0e8a7cef24cbd3adebcdf32a0")
EXPECTED_CANDIDATE_EXE_SHA256 = (
    "f8fe4281bf27365321da5092280fe8a2a08a33b61cdef14459f8e2c6e64009dc")
EXPECTED_ACCEPTED_FP_SHA256 = (
    "063ecf40b0faab3b2779d8ff159b8fa815eec7b397de0d47e68223841e2a59cc")
EXPECTED_CANDIDATE_FP_SHA256 = (
    "da528de24ecc9bb205410a0c41f977726a3bc8edd062235b407a26ca2ee607f3")
EXPECTED_COMPILER_SHA256 = (
    "cfb39efc611dc96eab47f24c70cc7447a11f3b7cd874c49bfeb4934a42e67e87")
EXPECTED_CPU_PACK_SHA256 = (
    "1dd1433597c42e30b13bd55bfd02c19ebe465f3e020e4878906f66e7bfcdc4b7")
ROOT_START = 0x256F1
ISLAND_END = 0x25B49
SCALAR_ROOT_CALL = 0x256C7
SCALAR_TO_F64_CALL = 0x256CC
XTOF64 = 0x24EE6
XTOF64_CORE = 0x24EF3
PUBLIC_FSQRT = 0x27F02
SCALAR_SQRT = 0x2566A
RESTORING_LOOP = 0x257EB
PAIR_READY = 0x2580E
RESTORING_NEXT = 0x25995
RESTORING_COMPLETE = 0x25A0B
FUNCTIONAL_RETURN = 0x25B40
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
    assert actual == expected, (actual, expected)


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
active_fp = (ROOT / "work/fp/fpsoft.txt").read_bytes()
active_executable = (ROOT / "work/vhgame.exe").read_bytes()
assert active_fp in (accepted_fp, candidate_fp)
assert active_executable in (accepted, candidate)
assert (active_fp == accepted_fp) == (active_executable == accepted)
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

# Exact package bytes outside the established helper island prove that every
# caller, downstream routine, package table, and runtime payload retains its
# accepted address and contents.
assert accepted[:ROOT_START] == candidate[:ROOT_START]
assert accepted[ISLAND_END:] == candidate[ISLAND_END:]
differences = [
    offset for offset, (left, right) in enumerate(zip(accepted, candidate))
    if left != right
]
assert len(differences) == 897
assert differences[0] == 0x25714
assert differences[-1] == 0x25B48
assert all(ROOT_START <= offset < ISLAND_END for offset in differences)

accepted_code = instructions(
    accepted, expected_header["code_start"], expected_header["physical_end"])
candidate_code = instructions(
    candidate, expected_header["code_start"], expected_header["physical_end"])
assert len(accepted_code) == 93_581
assert len(candidate_code) == 93_587
accepted_map = {item.address: item for item in accepted_code}
candidate_map = {item.address: item for item in candidate_code}
for mapping in (accepted_map, candidate_map):
    exact(mapping,
          [PUBLIC_FSQRT, PUBLIC_FSQRT + 1, PUBLIC_FSQRT + 6],
          [("pushal", ""), ("call", hex(SCALAR_SQRT)), ("popal", "")])
    call = mapping[SCALAR_ROOT_CALL]
    assert call.mnemonic == "call" and direct_target(call) == ROOT_START
    exact(mapping,
          [SCALAR_ROOT_CALL, SCALAR_TO_F64_CALL, 0x256D1, 0x256D6],
          [("call", hex(ROOT_START)), ("call", hex(XTOF64)),
           ("mov", "ebp, 0x646f6e65"), ("ret", "")])
    exact(mapping,
          [XTOF64, XTOF64 + 1, XTOF64 + 6, 0x24EED, 0x24EF2],
          [("pushal", ""), ("call", hex(XTOF64_CORE)), ("popal", ""),
           ("mov", "ebp, 0x646f6e65"), ("ret", "")])
    exact(mapping,
          [0x250B6, 0x250BC, 0x250C2, 0x250C8, 0x250CE, 0x250D1,
           0x250D3, 0x250D9, 0x250DC, 0x250DE, 0x250E4, 0x250E9],
          [("mov", "eax, dword ptr [edi + 0x26b4]"),
           ("mov", "dword ptr [edi + 0x2620], eax"),
           ("mov", "eax, dword ptr [edi + 0x26b0]"),
           ("mov", "ebx, dword ptr [edi + 0x2748]"),
           ("shl", "ebx, 0x14"), ("or", "eax, ebx"),
           ("mov", "ebx, dword ptr [edi + 0x2678]"),
           ("shl", "ebx, 0x1f"), ("or", "eax, ebx"),
           ("mov", "dword ptr [edi + 0x2624], eax"),
           ("mov", "ebp, 0x646f6e65"), ("ret", "")])

accepted_root = instructions(accepted, ROOT_START, ISLAND_END)
candidate_root = instructions(candidate, ROOT_START, ISLAND_END)
assert len(accepted_root) == 211
assert len(candidate_root) == 217
assert not [item for item in accepted_root if item.mnemonic == "call"]
assert not [item for item in candidate_root if item.mnemonic == "call"]
external_entries = []
for item in candidate_code:
    target = direct_target(item)
    if target is None:
        continue
    if not (ROOT_START <= item.address < ISLAND_END) and ROOT_START <= target < ISLAND_END:
        external_entries.append((item.address, item.mnemonic, target))
assert external_entries == [(SCALAR_ROOT_CALL, "call", ROOT_START)]
assert all(
    direct_target(item) is None or ROOT_START <= direct_target(item) < ISLAND_END
    for item in candidate_root)

# Odd and even radicand paths converge before the two lower limbs are cleared.
# The model independently proves the binary64-derived XML low-zero invariant.
exact(candidate_map,
      [0x25712, 0x25718, 0x2571E, 0x25724, 0x2572A, 0x25741,
       0x25746, 0x2574C, 0x2574F, 0x25755, 0x2575B, 0x2575E,
       0x25764, 0x25766, 0x2576C, 0x25772, 0x25775,
       0x2577B, 0x25785],
      [("je", "0x25746"),
       ("mov", "eax, dword ptr [edi + 0x2684]"),
       ("mov", "dword ptr [edi + 0x27ac], eax"),
       ("mov", "eax, dword ptr [edi + 0x2680]"),
       ("mov", "dword ptr [edi + 0x27b0], eax"),
       ("jmp", "0x2577b"),
       ("mov", "eax, dword ptr [edi + 0x2684]"),
       ("shr", "eax, 1"),
       ("mov", "dword ptr [edi + 0x27ac], eax"),
       ("mov", "eax, dword ptr [edi + 0x2680]"),
       ("shl", "eax, 0x1f"),
       ("mov", "ebx, dword ptr [edi + 0x27ac]"),
       ("or", "eax, ebx"),
       ("mov", "dword ptr [edi + 0x27ac], eax"),
       ("mov", "eax, dword ptr [edi + 0x2680]"),
       ("shr", "eax, 1"),
       ("mov", "dword ptr [edi + 0x27b0], eax"),
       ("mov", "dword ptr [edi + 0x27a4], 0"),
       ("mov", "dword ptr [edi + 0x27a8], 0")])
exact(candidate_map,
      [0x2578F, 0x25799, 0x257A3, 0x257AD, 0x257B7],
      [("mov", "dword ptr [edi + 0x27b4], 0"),
       ("mov", "dword ptr [edi + 0x27b8], 0"),
       ("mov", "dword ptr [edi + 0x27cc], 0"),
       ("mov", "dword ptr [edi + 0x27d0], 0"),
       ("mov", "dword ptr [edi + 0x27d4], 0")])

# One active-buffer zero test guards the extraction shift. A zero buffer branches
# directly to pair-ready with ESI already zero; nonzero buffers preserve the
# accepted high-pair extraction exactly.
exact(candidate_map,
      [0x257C1, 0x257CB, 0x257D1, 0x257D7, 0x257E1,
       0x257EB, 0x257F1, 0x257F3, 0x257F8, 0x257FE, 0x25801,
       0x25807, 0x25809, 0x2580C],
      [("mov", "dword ptr [edi + 0x27c8], 0x9ec"),
       ("mov", "eax, dword ptr [edi + 0x27b0]"),
       ("mov", "dword ptr [edi + 0x27bc], eax"),
       ("mov", "dword ptr [edi + 0x27b0], 0"),
       ("mov", "dword ptr [edi + 0x27c0], 0x10"),
       ("mov", "eax, dword ptr [edi + 0x27bc]"),
       ("mov", "esi, eax"),
       ("cmp", "eax, 0"),
       ("je", hex(PAIR_READY)),
       ("shl", "eax, 2"),
       ("mov", "dword ptr [edi + 0x27bc], eax"),
       ("mov", "eax, esi"),
       ("shr", "eax, 0x1e"),
       ("mov", "esi, eax")])
assert 0x9EC * 4 == WORKSPACE["srd3"]

# Generated remainder shift: srm2:srm1:srm0 = remainder*4 + ESI pair.
exact(candidate_map,
      [0x2580E, 0x25814, 0x25817, 0x2581D, 0x25820, 0x25822,
       0x25828, 0x2582E, 0x25831, 0x25837, 0x2583A, 0x2583C,
       0x25842, 0x25848, 0x2584B, 0x2584D, 0x2584F],
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

# Root shift and 65-bit trial formation remain the accepted word schedule.
exact(candidate_map,
      [0x25855, 0x2585B, 0x2585E, 0x25860, 0x25866, 0x25869,
       0x2586B, 0x2586D, 0x25873, 0x25879, 0x2587C,
       0x25882, 0x25888, 0x2588B, 0x25891, 0x25897, 0x2589A,
       0x258A0, 0x258A3, 0x258A5, 0x258A7, 0x258AD, 0x258B0,
       0x258B5],
      [("mov", "eax, dword ptr [edi + 0x27b8]"),
       ("shr", "eax, 0x1f"), ("mov", "esi, eax"),
       ("mov", "eax, dword ptr [edi + 0x27b4]"),
       ("shl", "eax, 1"), ("mov", "ebx, esi"), ("or", "eax, ebx"),
       ("mov", "dword ptr [edi + 0x27b4], eax"),
       ("mov", "eax, dword ptr [edi + 0x27b8]"),
       ("shl", "eax, 1"), ("mov", "dword ptr [edi + 0x27b8], eax"),
       ("mov", "eax, dword ptr [edi + 0x27b4]"),
       ("shr", "eax, 0x1f"),
       ("mov", "dword ptr [edi + 0x27c4], eax"),
       ("mov", "eax, dword ptr [edi + 0x27b4]"),
       ("shl", "eax, 1"),
       ("mov", "ebx, dword ptr [edi + 0x27b8]"),
       ("shr", "ebx, 0x1f"), ("or", "eax, ebx"), ("mov", "ecx, eax"),
       ("mov", "eax, dword ptr [edi + 0x27b8]"),
       ("shl", "eax, 1"), ("or", "eax, 1"), ("mov", "edx, eax")])

# Unsigned lexicographic comparison implements remainder >= trial.
exact(candidate_map,
      [0x258B7, 0x258BD, 0x258C3, 0x258C5, 0x258CB, 0x258CD,
       0x258D3, 0x258D9, 0x258DB, 0x258DD, 0x258E3, 0x258E5,
       0x258EB, 0x258F1, 0x258F3, 0x258F5],
      [("mov", "eax, dword ptr [edi + 0x27d4]"),
       ("mov", "ebx, dword ptr [edi + 0x27c4]"), ("cmp", "eax, ebx"),
       ("ja", "0x258fb"), ("cmp", "eax, ebx"), ("jb", hex(RESTORING_NEXT)),
       ("mov", "eax, dword ptr [edi + 0x27d0]"), ("mov", "ebx, ecx"),
       ("cmp", "eax, ebx"), ("ja", "0x258fb"), ("cmp", "eax, ebx"),
       ("jb", hex(RESTORING_NEXT)),
       ("mov", "eax, dword ptr [edi + 0x27cc]"), ("mov", "ebx, edx"),
       ("cmp", "eax, ebx"), ("jb", hex(RESTORING_NEXT))])

# Accepted subtraction propagates unsigned borrows low-to-high. Its root update
# is one low-word increment immediately followed by the shared next label; the
# removed carry branch is impossible because the preceding root shift made it even.
exact(candidate_map,
      [0x258FB, 0x25901, 0x25903, 0x25905, 0x2590B, 0x25910,
       0x25915, 0x2591A, 0x25920, 0x25922,
       0x25928, 0x2592E, 0x25930, 0x25932, 0x25938, 0x2593A,
       0x25940, 0x25946, 0x2594C, 0x25952, 0x25954, 0x25956,
       0x2595C, 0x25961, 0x25966, 0x2596C, 0x2596E, 0x25970,
       0x25976, 0x2597B, 0x25981, 0x25987, 0x25989, 0x2598F,
       0x25995],
      [("mov", "eax, dword ptr [edi + 0x27cc]"), ("mov", "ebx, edx"),
       ("cmp", "eax, ebx"), ("jb", "0x25915"), ("mov", "esi, 0"),
       ("jmp", "0x2591a"), ("mov", "esi, 1"),
       ("mov", "eax, dword ptr [edi + 0x27cc]"), ("sub", "eax, edx"),
       ("mov", "dword ptr [edi + 0x27cc], eax"),
       ("mov", "eax, dword ptr [edi + 0x27d0]"), ("mov", "ebx, ecx"),
       ("cmp", "eax, ebx"), ("ja", "0x25966"), ("cmp", "eax, ebx"),
       ("jb", "0x2594c"), ("cmp", "esi, 0"), ("je", "0x25966"),
       ("mov", "eax, dword ptr [edi + 0x27d0]"), ("sub", "eax, ecx"),
       ("sub", "eax, esi"), ("mov", "dword ptr [edi + 0x27d0], eax"),
       ("mov", "esi, 1"), ("jmp", "0x2597b"),
       ("mov", "eax, dword ptr [edi + 0x27d0]"), ("sub", "eax, ecx"),
       ("sub", "eax, esi"), ("mov", "dword ptr [edi + 0x27d0], eax"),
       ("mov", "esi, 0"), ("mov", "eax, dword ptr [edi + 0x27d4]"),
       ("sub", "eax, dword ptr [edi + 0x27c4]"), ("sub", "eax, esi"),
       ("mov", "dword ptr [edi + 0x27d4], eax"),
       ("inc", "dword ptr [edi + 0x27b8]"),
       ("dec", "dword ptr [edi + 0x27c0]")])
assert not any(
    item.address > 0x2598F and item.address < RESTORING_NEXT
    for item in candidate_root)

# Exactly one direct srd2 handoff is followed by one cold transition that counts
# the two lower pointer steps and installs a 32-decision zero phase. The final
# phase exit decrements sqstep from srd0 to srd0-1 before completion.
exact(candidate_map,
      [0x25995, 0x2599B, 0x259A5, 0x259AB, 0x259B1, 0x259BB,
       0x259C1, 0x259C7, 0x259CD, 0x259D7, 0x259E1,
       0x259E6, 0x259F0, 0x259F6, 0x259FC, 0x25A06],
      [("dec", "dword ptr [edi + 0x27c0]"),
       ("cmp", "dword ptr [edi + 0x27c0], 0"), ("jne", hex(RESTORING_LOOP)),
       ("dec", "dword ptr [edi + 0x27c8]"),
       ("cmp", "dword ptr [edi + 0x27c8], 0x9eb"), ("jl", "0x259e6"),
       ("mov", "eax, dword ptr [edi + 0x27ac]"),
       ("mov", "dword ptr [edi + 0x27bc], eax"),
       ("mov", "dword ptr [edi + 0x27ac], 0"),
       ("mov", "dword ptr [edi + 0x27c0], 0x10"), ("jmp", hex(RESTORING_LOOP)),
       ("cmp", "dword ptr [edi + 0x27c8], 0x9e9"),
       ("jl", hex(RESTORING_COMPLETE)),
       ("dec", "dword ptr [edi + 0x27c8]"),
       ("mov", "dword ptr [edi + 0x27c0], 0x20"),
       ("jmp", hex(RESTORING_LOOP))])
assert 0x9EB * 4 == WORKSPACE["srd2"]
assert 0x9E9 * 4 == WORKSPACE["srd0"]
assert not [item for item in candidate_root if "edi + ebx*4" in item.op_str]
assert sum(item.op_str == "eax, dword ptr [edi + 0x27bc]"
           for item in candidate_root) == 1
assert sum(item.op_str == "dword ptr [edi + 0x27bc], eax"
           for item in candidate_root) == 3
assert sum(item.op_str == "dword ptr [edi + 0x27ac], 0"
           for item in candidate_root) == 1

# The accepted residual compatibility and p64 rounding tail remain generated,
# with srm3 assigned once before its first possible observation.
srm3_accesses = [(item.address, item.mnemonic, item.op_str)
                 for item in candidate_root if "0x27d8" in item.op_str]
assert srm3_accesses == [(0x25A57, "mov", "dword ptr [edi + 0x27d8], eax")]
exact(candidate_map,
      [0x25A0B, 0x25A10, 0x25A16, 0x25A19, 0x25A1E,
       0x25A24, 0x25A2A, 0x25A34, 0x25A3A, 0x25A40, 0x25A4A,
       0x25A50, 0x25A55, 0x25A57],
      [("mov", "esi, 0"),
       ("mov", "eax, dword ptr [edi + 0x27b8]"), ("movzx", "eax, ax"),
       ("cmp", "eax, 0"), ("jne", "0x25a55"),
       ("dec", "dword ptr [edi + 0x27d0]"),
       ("cmp", "dword ptr [edi + 0x27d0], 0xffffffff"), ("jne", "0x25a55"),
       ("dec", "dword ptr [edi + 0x27d4]"),
       ("cmp", "dword ptr [edi + 0x27d4], 0xffffffff"), ("jne", "0x25a55"),
       ("mov", "esi, 0xffffffff"), ("mov", "eax, esi"),
       ("mov", "dword ptr [edi + 0x27d8], eax")])

# The complete generated p64 comparison, root increment/carry normalization,
# XMH/XML publication, exponent finalization, and functional return are exact.
exact(candidate_map,
      [0x25A5D, 0x25A63, 0x25A69, 0x25A73, 0x25A79, 0x25A7F,
       0x25A85, 0x25A87, 0x25A8D, 0x25A8F, 0x25A95, 0x25A9B,
       0x25AA1, 0x25AA3, 0x25AA9, 0x25AAE, 0x25AB4, 0x25ABE,
       0x25AC4, 0x25ACA, 0x25AD4, 0x25ADA, 0x25ADF, 0x25AE9,
       0x25AF3, 0x25AF9, 0x25AFE, 0x25B04, 0x25B0A, 0x25B10,
       0x25B16, 0x25B1C, 0x25B1D, 0x25B22, 0x25B23, 0x25B25,
       0x25B26, 0x25B2B, 0x25B31, 0x25B3B, 0x25B40],
      [("cmp", "esi, 0"), ("jne", "0x25aae"),
       ("cmp", "dword ptr [edi + 0x27d4], 0"), ("jne", "0x25aae"),
       ("mov", "eax, dword ptr [edi + 0x27d0]"),
       ("mov", "ebx, dword ptr [edi + 0x27b4]"), ("cmp", "eax, ebx"),
       ("ja", "0x25aae"), ("cmp", "eax, ebx"), ("jb", "0x25afe"),
       ("mov", "eax, dword ptr [edi + 0x27cc]"),
       ("mov", "ebx, dword ptr [edi + 0x27b8]"), ("cmp", "eax, ebx"),
       ("ja", "0x25aae"), ("jmp", "0x25afe"),
       ("inc", "dword ptr [edi + 0x27b8]"),
       ("cmp", "dword ptr [edi + 0x27b8], 0"), ("jne", "0x25afe"),
       ("inc", "dword ptr [edi + 0x27b4]"),
       ("cmp", "dword ptr [edi + 0x27b4], 0"), ("jne", "0x25adf"),
       ("jmp", "0x25afe"),
       ("mov", "dword ptr [edi + 0x2680], 0x80000000"),
       ("mov", "dword ptr [edi + 0x2684], 0"),
       ("inc", "dword ptr [edi + 0x2748]"), ("jmp", "0x25b16"),
       ("mov", "eax, dword ptr [edi + 0x27b4]"),
       ("mov", "dword ptr [edi + 0x2680], eax"),
       ("mov", "eax, dword ptr [edi + 0x27b8]"),
       ("mov", "dword ptr [edi + 0x2684], eax"),
       ("mov", "eax, dword ptr [edi + 0x2748]"), ("push", "edx"),
       ("mov", "ebp, 2"), ("cdq", ""), ("idiv", "ebp"), ("pop", "edx"),
       ("add", "eax, 0x3fff"), ("mov", "dword ptr [edi + 0x267c], eax"),
       ("mov", "dword ptr [edi + 0x2678], 0"),
       ("mov", "ebp, 0x646f6e65"), ("ret", "")])

root_text = "\n".join(item.op_str for item in candidate_root)
for address in WORKSPACE.values():
    assert f"0x{address:x}" in root_text
assert sorted(WORKSPACE.values()) == list(range(0x27A4, 0x27DC, 4))

# The functional return precedes exactly eight post-return calibration bytes. The
# generated helper has no indirect call/jump and no direct edge enters the bytes;
# the RET also prevents ordinary fallthrough. Outside indirect dispatch is not
# treated as statically resolved evidence.
assert (candidate_map[0x25B3B].mnemonic,
        candidate_map[0x25B3B].op_str) == ("mov", "ebp, 0x646f6e65")
assert candidate_map[FUNCTIONAL_RETURN].mnemonic == "ret"
padding = candidate[FUNCTIONAL_RETURN + 1:ISLAND_END]
assert padding == b"\x40" * 8
padding_instructions = instructions(candidate, FUNCTIONAL_RETURN + 1, ISLAND_END)
assert [(item.mnemonic, item.op_str) for item in padding_instructions] == [
    ("inc", "eax")] * 8
padding_entries = [
    (item.address, direct_target(item)) for item in candidate_root
    if direct_target(item) is not None
    and FUNCTIONAL_RETURN < direct_target(item) < ISLAND_END
]
helper_indirect_calls_or_jumps = [
    (item.address, item.mnemonic, item.op_str) for item in candidate_root
    if item.mnemonic in ("call", "jmp") and direct_target(item) is None
]
assert padding_entries == []
assert helper_indirect_calls_or_jumps == []
assert accepted_map[0x25B48].mnemonic == "ret"
assert accepted_map[ISLAND_END].mnemonic == candidate_map[ISLAND_END].mnemonic == "pushal"
assert accepted[ISLAND_END:ISLAND_END + 256] == candidate[ISLAND_END:ISLAND_END + 256]

model = json.loads((EVIDENCE / "model.json").read_text(encoding="utf-8"))
build = json.loads((EVIDENCE / "build.json").read_text(encoding="utf-8"))
assert model["status"] == "pass"
assert model["verifier_sha256"] == sha256((EVIDENCE / "verify_model.py").read_bytes())
assert model["candidate_snapshot_equals_exact_transform"]
assert model["active_source_is_accepted_or_candidate"]
assert model["active_source_sha256"] == sha256(active_fp)
assert model["accepted_source_sha256"] == EXPECTED_ACCEPTED_FP_SHA256
assert model["candidate_source_sha256"] == EXPECTED_CANDIDATE_FP_SHA256
assert model["binary64_srd1_srd0_zero_invariant_exact"]
assert model["minimum_binary64_mantissa_low_zero_bits"] >= 11
assert model["candidate_restoring_decisions_per_positive_root"] == 64
assert model["candidate_zero_tail_decisions_per_positive_root"] == 32
assert model["candidate_zero_tail_transitions_per_positive_root"] == 1
assert model["candidate_minimum_skipped_buffer_shifts_per_positive_root"] >= 32
assert model["candidate_maximum_performed_buffer_shifts_per_positive_root"] <= 32
assert model["candidate_direct_limb_handoffs_per_positive_root"] == 1
assert model["candidate_dynamic_limb_handoffs_per_positive_root"] == 0
assert model["candidate_pointer_decrements_per_positive_root"] == 4
assert model["candidate_accepted_bit_increment_carry_impossible"]
assert model["terminal_srd0_srd1_srd2_srd3_exact"]
assert model["terminal_sqstep_sqml_sqmh_exact"]
assert model["terminal_root_remainder_words_exact"]
assert model["integer_root_exact"]
assert model["mathematical_residual_exact_before_compatibility"]
assert model["accepted_private_residual_exact"]
assert model["accepted_p64_root_rounding_exact"]
assert model["p53_binary64_spill_exact"]
assert (model["p64_policy_differences_with_identical_p53_spill"]
        == model["pipeline_accepted_vs_mathematical_p64_differences"] > 0)
assert model["candidate_zero_test_is_in_shared_restoring_header"]
assert model["candidate_uses_one_shared_restoring_decision_core"]
assert model["positive_zero_negative_and_rejection_behavior_exact"]
assert model["candidate_changes_confined_to_xrootcore"]
assert model["public_register_save_restore_source_wrapper_exact"]
assert model["non_root_fpsoft_source_exact"]
assert model["rooted_distance_and_renderer_control_source_exact"]
assert model["synchronized_runtime_state_fidelity_required_after_timing"]
assert model["simulation_constants"] == [18206, 60000]
assert build["status"] == "pass"
assert build["private_inactive_desktop"]
assert build["build_entry"] == "lino_build.ps1"
assert build["absolute_build_paths"]
assert build["warnings"] == 65 and build["errors"] == 0
assert build["build_seconds"] == 11.0
assert build["candidate_fpsoft_sha256"] == EXPECTED_CANDIDATE_FP_SHA256
assert build["candidate_executable_bytes"] == len(candidate)
assert build["candidate_executable_sha256"] == EXPECTED_CANDIDATE_EXE_SHA256
assert build["accepted_executable_sha256"] == EXPECTED_ACCEPTED_EXE_SHA256

result = {
    "schema": 1,
    "task": 228,
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
    "generated_binary64_lower_limb_initialization_exact": True,
    "generated_root_and_remainder_initialization_exact": True,
    "generated_zero_buffer_branch_exact": True,
    "generated_remainder_shift_exact": True,
    "generated_root_trial_exact": True,
    "generated_unsigned_trial_comparison_exact": True,
    "generated_borrow_subtraction_exact": True,
    "generated_accepted_increment_no_carry_branch_exact": True,
    "generated_direct_upper_handoff_exact": True,
    "generated_32_decision_zero_tail_transition_exact": True,
    "generated_complete_p64_tail_through_return_exact": True,
    "generated_post_root_xtof64_call_and_normal_spill_exact": True,
    "accepted_restoring_decisions_per_positive_root": 64,
    "candidate_restoring_decisions_per_positive_root": 64,
    "candidate_zero_tail_decisions_per_positive_root": 32,
    "candidate_minimum_skipped_buffer_shifts_per_positive_root": model[
        "candidate_minimum_skipped_buffer_shifts_per_positive_root"],
    "candidate_maximum_performed_buffer_shifts_per_positive_root": model[
        "candidate_maximum_performed_buffer_shifts_per_positive_root"],
    "candidate_direct_limb_handoffs_per_positive_root": 1,
    "candidate_dynamic_limb_handoffs_per_positive_root": 0,
    "candidate_pointer_decrements_per_positive_root": 4,
    "candidate_accepted_bit_increment_carry_impossible": True,
    "buffered_zero_tail_schedule_exact": True,
    "workspace_addresses": {name: hex(address) for name, address in WORKSPACE.items()},
    "workspace_addresses_unchanged": True,
    "srm3_assigned_before_first_read": True,
    "candidate_post_return_calibration_bytes": len(padding),
    "candidate_post_return_increments": 8,
    "candidate_post_return_calibration_direct_entries": len(padding_entries),
    "candidate_helper_indirect_calls_or_jumps": len(helper_indirect_calls_or_jumps),
    "candidate_post_return_calibration_has_no_fallthrough": True,
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
    "active_production": "accepted" if active_fp == accepted_fp else "candidate",
    "active_source_and_executable_match": True,
    "model_verifier_sha256": model["verifier_sha256"],
    "verifier_sha256": sha256(Path(__file__).resolve().read_bytes()),
}
OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
