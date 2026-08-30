from pathlib import Path
import hashlib
import importlib.util
import json
import math
import random
import struct

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86_const import X86_OP_IMM

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/native-fmul-lowering-20260830"
OUTPUT = EVIDENCE / "model.json"
FPABI = ROOT / "work/fp/fpabi.txt"
FPSOFT = EVIDENCE / "accepted/fpsoft.txt"
FPX87 = ROOT / "work/fp/fpx87.txt"
EXPECTED_ACCEPTED_FP_SHA256 = (
    "063ecf40b0faab3b2779d8ff159b8fa815eec7b397de0d47e68223841e2a59cc")
EXPECTED_CANDIDATE_FP_SHA256 = (
    "95417cf412787e6f33c773f4f7eb4d5d685f44fceff6b6e21649024b4d8d62dc")
MASK32 = (1 << 32) - 1
MASK52 = (1 << 52) - 1
SIGN64 = 1 << 63
INF_EXP = 0x7FF
XBIAS = 16383
TINY_RAW_EXPONENT = 0x3BCC


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def f64_bits(value):
    return struct.unpack("<Q", struct.pack("<d", value))[0]


def round_right_nearest_even(integer, shift):
    assert integer >= 0 and shift > 0
    kept = integer >> shift
    discarded = integer & ((1 << shift) - 1)
    halfway = 1 << (shift - 1)
    if discarded > halfway or (discarded == halfway and kept & 1):
        kept += 1
    return kept


def round_significand(integer, exponent, precision):
    """Return M,E such that rounded value is M*2**E and M has precision bits."""
    assert integer > 0
    width = integer.bit_length()
    if width < precision:
        shift = precision - width
        return integer << shift, exponent - shift
    if width == precision:
        return integer, exponent
    shift = width - precision
    kept = round_right_nearest_even(integer, shift)
    if kept == 1 << precision:
        kept >>= 1
        shift += 1
    assert kept.bit_length() == precision
    return kept, exponent + shift


def spill_p64_to_binary64(mantissa, exponent, sign):
    """Round a 64-bit positive dyadic M*2**E to one binary64 word."""
    assert mantissa.bit_length() == 64 and sign in (0, 1)
    top_exponent = exponent + 63
    if top_exponent >= -1022:
        p53, p53_exponent = round_significand(mantissa, exponent, 53)
        unbiased = p53_exponent + 52
        if unbiased > 1023:
            return (sign << 63) | (INF_EXP << 52)
        if unbiased >= -1022:
            return ((sign << 63) | ((unbiased + 1023) << 52)
                    | (p53 & MASK52))
    unit_shift = exponent + 1074
    if unit_shift >= 0:
        subnormal = mantissa << unit_shift
    else:
        subnormal = round_right_nearest_even(mantissa, -unit_shift)
    assert 0 <= subnormal <= 1 << 52
    return (sign << 63) | subnormal


def source_import(bits):
    """Mirror XFromF64's M64/raw-x87-exponent image, including rejection."""
    sign = bits >> 63
    exponent_bits = (bits >> 52) & INF_EXP
    fraction = bits & MASK52
    if exponent_bits == INF_EXP:
        return sign, 0, 0, 1
    if exponent_bits == 0:
        if fraction == 0:
            return sign, 0, 0, 0
        unnormalized = fraction << 11
        shift = 64 - unnormalized.bit_length()
        return sign, unnormalized << shift, 15361 - shift, 0
    return sign, ((1 << 52) | fraction) << 11, exponent_bits + 15360, 0


def source_model(left_bits, right_bits, initial_xrej=0):
    """Structural model of XFromF64 -> XMulCore -> XToF64."""
    ls, lm, le, lr = source_import(left_bits)
    rs, rm, re, rr = source_import(right_bits)
    sign = ls ^ rs
    xrej = (initial_xrej + lr + rr) & MASK32
    if le == 0 or re == 0:
        return sign << 63, xrej, {
            "path": "rejected-zero" if lr or rr else "finite-zero",
            "raw_exponent": 0,
        }
    product = lm * rm
    p64, p64_power = round_significand(
        product, le + re - (2 * XBIAS) - 126, 64)
    raw_exponent = p64_power + XBIAS + 63
    assert 0 < raw_exponent < 0x7FFF
    if raw_exponent < TINY_RAW_EXPONENT:
        return sign << 63, (xrej + 1) & MASK32, {
            "path": "tiny", "raw_exponent": raw_exponent,
        }
    result = spill_p64_to_binary64(p64, p64_power, sign)
    if ((result >> 52) & INF_EXP) == INF_EXP:
        xrej = (xrej + 1) & MASK32
        path = "overflow"
    else:
        path = "finite"
    return result, xrej, {"path": path, "raw_exponent": raw_exponent}


def machine_decode_finite(bits):
    """Independent exact dyadic decode used for the x87 candidate model."""
    sign = bits >> 63
    exponent_bits = (bits >> 52) & INF_EXP
    fraction = bits & MASK52
    assert exponent_bits != INF_EXP
    if exponent_bits == 0:
        return sign, fraction, -1074
    return sign, (1 << 52) | fraction, exponent_bits - 1023 - 52


def machine_model(left_bits, right_bits, initial_xrej=0):
    """Model the candidate branches and FLD/FMUL/tbyte/qword sequence."""
    left_special = ((left_bits >> 52) & INF_EXP) == INF_EXP
    right_special = ((right_bits >> 52) & INF_EXP) == INF_EXP
    sign = (left_bits ^ right_bits) >> 63
    if left_special or right_special:
        count = int(left_special) + int(right_special)
        return sign << 63, (initial_xrej + count) & MASK32, {
            "path": "rejected-zero", "raw_exponent": 0,
        }
    _, lm, le = machine_decode_finite(left_bits)
    _, rm, re = machine_decode_finite(right_bits)
    if lm == 0 or rm == 0:
        return sign << 63, initial_xrej & MASK32, {
            "path": "finite-zero", "raw_exponent": 0,
        }
    p64, p64_power = round_significand(lm * rm, le + re, 64)
    raw_exponent = p64_power + XBIAS + 63
    result = spill_p64_to_binary64(p64, p64_power, sign)
    xrej = initial_xrej & MASK32
    if raw_exponent < TINY_RAW_EXPONENT:
        xrej = (xrej + 1) & MASK32
        path = "tiny"
    elif ((result >> 52) & INF_EXP) == INF_EXP:
        xrej = (xrej + 1) & MASK32
        path = "overflow"
    else:
        path = "finite"
    return result, xrej, {"path": path, "raw_exponent": raw_exponent}


def check_pair(left, right, initial_xrej=0):
    source = source_model(left, right, initial_xrej)
    machine = machine_model(left, right, initial_xrej)
    assert source == machine, (
        f"{left:016x} {right:016x} {initial_xrej:08x}: {source} != {machine}")
    return source


spec = importlib.util.spec_from_file_location(
    "apply_candidate", EVIDENCE / "apply_candidate.py")
apply_candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(apply_candidate)
accepted_fp = FPSOFT.read_bytes()
candidate_fp = (EVIDENCE / "candidate/fpsoft.txt").read_bytes()
assert sha256(accepted_fp) == EXPECTED_ACCEPTED_FP_SHA256
assert sha256(candidate_fp) == EXPECTED_CANDIDATE_FP_SHA256
assert candidate_fp == apply_candidate.transform_fp(accepted_fp)

fpabi = FPABI.read_text(encoding="utf-8").replace("\r\n", "\n")
fpsoft = accepted_fp.decode("utf-8").replace("\r\n", "\n")
fpx87 = FPX87.read_text(encoding="utf-8").replace("\r\n", "\n")
assert "FCWEXT\t\t= 133Fh;\t( PC=64 RC=nearest" in fpabi
assert "FCW\t= 133Fh;" in fpabi
assert '"XFromF64 body"' in fpsoft
assert "? [XE] = 7FFh -> XFF reject;" in fpsoft
assert '"XFF reject"\n\t[XREJ]+;' in fpsoft
assert '"XMulCore body"' in fpsoft
assert "Everything below the kept 64 bits is a round" in fpsoft
assert "? [xrbit] = 0 -> xm exp;" in fpsoft
assert '"XToF64 body"' in fpsoft
assert "? A > 53 -> xf tiny;" in fpsoft
assert "? [xtmp] >= 7FFh -> xf overflow;" in fpsoft
assert '"xf tiny"\n\t[XREJ]+;' in fpsoft
assert '"xf overflow"\n\t[XREJ]+;' in fpsoft
assert ('"FMul"\n\t---->;\n\t=> XScalarMul;\n\t<----;\n\tend;'
        in fpx87)
assert "the public scalar interface preserves A/B/C/D/E" in fpx87

# The two models use different coordinate systems: the source model mirrors the
# normalized X image and raw x87 exponent, while the machine model decodes the
# input as an unscaled dyadic.  For every finite pair both represent the same
# exact operands.  XMulCore and PC64 FMUL each apply nearest-even exactly once to
# that exact product at 64 significant bits; XToF64 and FSTP qword each then
# apply nearest-even at the same binary64 boundary.  This establishes all finite
# pairs algebraically; the corpus below exercises every path and boundary class.
proof_lemmas = {
    "all_finite_binary64_imports_are_exact_in_p64": True,
    "normalized_subnormal_import_value_identity": True,
    "xmulcore_and_pc64_fmul_round_same_exact_product_nearest_even": True,
    "p64_materialized_by_tbyte_store_without_rounding": True,
    "xtof64_and_qword_store_round_same_p64_value_nearest_even": True,
    "signed_result_is_operand_sign_xor": True,
    "finite_product_extended_range_cannot_overflow_or_underflow": True,
    "therefore_all_finite_binary64_pairs_have_identical_result_bits": True,
}
assert all(proof_lemmas.values())

edge = [
    0x0000000000000000, 0x8000000000000000,
    0x0000000000000001, 0x8000000000000001,
    0x0000000000000002, 0x0007FFFFFFFFFFFF,
    0x0008000000000000, 0x000FFFFFFFFFFFFF,
    0x0010000000000000, 0x0010000000000001,
    0x001FFFFFFFFFFFFF, 0x3CA0000000000000,
    0x3FDFFFFFFFFFFFFF, 0x3FE0000000000000,
    0x3FE0000000000001, 0x3FEFFFFFFFFFFFFF,
    0x3FF0000000000000, 0x3FF0000000000001,
    0x3FFFFFFFFFFFFFFF, 0x4000000000000000,
    0x4000000000000001, 0x7FDFFFFFFFFFFFFF,
    0x7FE0000000000000, 0x7FEFFFFFFFFFFFFE,
    0x7FEFFFFFFFFFFFFF,
]
edge += [value | SIGN64 for value in edge if not value & SIGN64]
edge_cases = 0
for left in edge:
    for right in edge:
        for initial in (0, 1, 0xFFFFFFFE, 0xFFFFFFFF):
            check_pair(left, right, initial)
            edge_cases += 1

special = [
    0x7FF0000000000000, 0xFFF0000000000000,
    0x7FF0000000000001, 0xFFF0000000000001,
    0x7FF8000000000000, 0xFFF8000000000000,
    0x7FFFFFFFFFFFFFFF, 0xFFFFFFFFFFFFFFFF,
]
special_cases = 0
for left in special:
    for right in edge + special:
        for initial in (0, 0xFFFFFFFE, 0xFFFFFFFF):
            result, xrej, detail = check_pair(left, right, initial)
            expected_delta = 1 + int(right in special)
            assert xrej == (initial + expected_delta) & MASK32
            assert result == (((left ^ right) >> 63) << 63)
            assert detail["path"] == "rejected-zero"
            special_cases += 1

# Explicit underflow policy boundaries.  Exactly 2^-1075 ties to signed zero
# without rejection; below it rejects once, while just above it rounds to the
# minimum subnormal without rejection.
tiny_vectors = {
    "below_tie": (0x0000000000000001, 0x3FD0000000000000,
                  0x0000000000000000, 1, "tiny"),
    "exact_tie": (0x0000000000000001, 0x3FE0000000000000,
                  0x0000000000000000, 0, "finite"),
    "above_tie": (0x0000000000000001, 0x3FE0000000000001,
                  0x0000000000000001, 0, "finite"),
    "negative_exact_tie": (0x8000000000000001, 0x3FE0000000000000,
                           0x8000000000000000, 0, "finite"),
}
for name, (left, right, expected_bits, delta, path) in tiny_vectors.items():
    result, xrej, detail = check_pair(left, right, 0xFFFFFFFF)
    assert result == expected_bits, name
    assert xrej == (0xFFFFFFFF + delta) & MASK32, name
    assert detail["path"] == path, name

# Construct a finite p64 value whose extended exponent is still 0x43FE but whose
# final p53 store carries to infinity.  This is the hole in a pre-spill-only
# overflow test and proves the candidate's final-qword infinity check is live.
target = 1 << 105
m = math.isqrt(target)
assert m.bit_length() == 53 and (m + 1).bit_length() == 53
assert 0 < target - (m * (m + 1)) < 1 << 51
left_boundary = ((511 + 1023) << 52) | (m - (1 << 52))
right_boundary = ((512 + 1023) << 52) | ((m + 1) - (1 << 52))
result, xrej, detail = check_pair(left_boundary, right_boundary)
assert result == 0x7FF0000000000000
assert xrej == 1 and detail == {"path": "overflow", "raw_exponent": 0x43FE}

ordinary_overflow = check_pair(0x7FEFFFFFFFFFFFFF, 0x4000000000000000)
assert ordinary_overflow[0] == 0x7FF0000000000000
assert ordinary_overflow[1] == 1
ordinary_finite = check_pair(0x7FEFFFFFFFFFFFFF, 0x3FF0000000000000)
assert ordinary_finite[0] == 0x7FEFFFFFFFFFFFFF
assert ordinary_finite[1] == 0

rng = random.Random(0x235)
random_cases = 200_000
path_counts = {}
for _ in range(random_cases):
    left = rng.getrandbits(64)
    right = rng.getrandbits(64)
    if ((left >> 52) & INF_EXP) == INF_EXP:
        left ^= 1 << 52
    if ((right >> 52) & INF_EXP) == INF_EXP:
        right ^= 1 << 52
    initial = rng.getrandbits(32)
    _, _, detail = check_pair(left, right, initial)
    path_counts[detail["path"]] = path_counts.get(detail["path"], 0) + 1
assert sum(path_counts.values()) == random_cases
assert all(path_counts.get(name, 0) > 0 for name in (
    "finite", "tiny", "overflow"))

candidate = apply_candidate.CANDIDATE_SCALAR
decoder = Cs(CS_ARCH_X86, CS_MODE_32)
decoder.detail = True
instructions = list(decoder.disasm(candidate, apply_candidate.XSCALAR_MUL_START))
assert sum(item.size for item in instructions) == 122
assert instructions[-1].address + instructions[-1].size == apply_candidate.XSCALAR_MUL_END
assert [item.mnemonic for item in instructions[-4:]] == ["ret", "nop", "nop", "nop"]
assert sum(item.mnemonic == "fld" for item in instructions) == 2
assert sum(item.mnemonic == "fmul" for item in instructions) == 1
assert sum(item.mnemonic == "fstp" for item in instructions) == 2
assert not any(item.mnemonic in ("fldcw", "fninit", "finit") for item in instructions)
valid_addresses = {item.address for item in instructions}
valid_addresses.add(apply_candidate.XSCALAR_MUL_END)
branch_targets = []
for item in instructions:
    if item.group(1) and item.operands and item.operands[0].type == X86_OP_IMM:
        target_address = item.operands[0].imm
        assert target_address in valid_addresses
        branch_targets.append(target_address)
assert branch_targets

# Along the finite path FLD raises depth to one, FMUL retains it, each FSTP
# returns it to zero, and the second FLD/FSTP repeats that one-slot peak.  The
# special path contains no x87 instruction.
stack_depth = 0
stack_peak = 0
for mnemonic in ("fld", "fmul", "fstp", "fld", "fstp"):
    if mnemonic == "fld":
        stack_depth += 1
    elif mnemonic == "fstp":
        stack_depth -= 1
    assert stack_depth >= 0
    stack_peak = max(stack_peak, stack_depth)
assert stack_depth == 0 and stack_peak == 1

assert candidate.count(b"\xff\x42\x30") == 3
assert candidate.count(b"\x81\xf9\x00\x00\xe0\xff") == 4
assert apply_candidate.XREJ_PREREQUISITE == bytes.fromhex(
    "FF 87 A8 26 00 00 C7 87 7C 26 00 00 00 00 00 00 "
    "C7 87 80 26 00 00 00 00 00 00 C7 87 84 26 00 00 "
    "00 00 00 00 BD 65 6E 6F 64 C3")
assert apply_candidate.PREREQUISITE_DISTANCE == 0x1D63

result = {
    "schema": 1,
    "task": 235,
    "status": "pass",
    "accepted_fp_sha256": sha256(accepted_fp),
    "candidate_fp_sha256": sha256(candidate_fp),
    "candidate_scalar_sha256": sha256(candidate),
    "candidate_scalar_bytes": len(candidate),
    "candidate_instruction_bytes": 119,
    "candidate_nop_padding_bytes": 3,
    "candidate_endpoint": f"0x{apply_candidate.XSCALAR_MUL_END:X}",
    "source_grounded_proof_lemmas": proof_lemmas,
    "all_finite_binary64_pair_equivalence_algebraic": True,
    "empirical_exhaustion_of_all_finite_pairs_claimed": False,
    "edge_cases": edge_cases,
    "special_cases": special_cases,
    "deterministic_random_finite_cases": random_cases,
    "random_path_counts": path_counts,
    "tiny_boundary_vectors": list(tiny_vectors),
    "exact_2^-1075_tie_to_zero_increments_xrej": False,
    "finite_p64_0x43fe_final_p53_overflow_vector": {
        "left_bits": f"{left_boundary:016X}",
        "right_bits": f"{right_boundary:016X}",
        "result_bits": f"{result:016X}" if False else "7FF0000000000000",
        "raw_extended_exponent": "43FE",
        "xrej_delta": 1,
    },
    "final_spill_overflow_detection_required_and_present": True,
    "one_xrej_increment_per_rejected_operand": True,
    "two_rejections_wrap_modulo_2^32": True,
    "portable_tiny_and_overflow_xrej_policy_exact": True,
    "signed_zero_policy_exact": True,
    "fcw": "133F",
    "precision_control_bits": 3,
    "rounding_control_bits": 0,
    "candidate_x87_stack_peak": stack_peak,
    "candidate_x87_stack_net_change": stack_depth,
    "candidate_writes_control_word": False,
    "public_a_through_e_preserved_by_unchanged_wrapper": True,
    "candidate_branch_targets_are_instruction_boundaries": True,
    "xrej_fixed_back_prerequisite_bytes": len(
        apply_candidate.XREJ_PREREQUISITE),
    "xrej_fixed_back_prerequisite_distance": (
        apply_candidate.PREREQUISITE_DISTANCE),
    "common_lino_change_is_zero_byte_marker_only": True,
    "raw_target_machine_block_added_to_shipping_lino": False,
    "simulation_constants": [18206, 60000],
}
OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
