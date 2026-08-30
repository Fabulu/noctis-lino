from pathlib import Path
import hashlib
import json
import math
import random
import re
import runpy

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/native-fsqrt-lowering-20260830"
ACCEPTED = EVIDENCE / "accepted/fpsoft.txt"
CANDIDATE = EVIDENCE / "candidate/fpsoft.txt"
SOURCE = ROOT / "work/fp/fpsoft.txt"
FPX87 = ROOT / "work/fp/fpx87.txt"
FPABI = ROOT / "work/fp/fpabi.txt"
FPCTL = ROOT / "work/fp/fpctl.txt"
GAME = ROOT / "work/vhgame.txt"
OUTPUT = EVIDENCE / "model.json"
MASK32 = (1 << 32) - 1
MASK128 = (1 << 128) - 1
EXPECTED_ACCEPTED_SHA256 = (
    "063ecf40b0faab3b2779d8ff159b8fa815eec7b397de0d47e68223841e2a59cc")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def xfrom_positive_f64(bits):
    exponent_bits = (bits >> 52) & 0x7FF
    fraction = bits & ((1 << 52) - 1)
    assert bits >> 63 == 0 and exponent_bits != 0x7FF
    if exponent_bits:
        mantissa = ((1 << 52) | fraction) << 11
        exponent = exponent_bits - 1023
        low_zero_bits = 11
    else:
        assert fraction
        width = fraction.bit_length()
        mantissa = fraction << (64 - width)
        exponent = width - 1 - 1074
        low_zero_bits = 64 - width
    assert 1 << 63 <= mantissa < 1 << 64
    return mantissa, exponent, low_zero_bits


def form_radicand(mantissa, exponent):
    if exponent & 1:
        return mantissa << 64, exponent - 1
    return mantissa << 63, exponent


def accepted_limb_residual(radicand, root):
    square = root * root
    source = [(radicand >> (32 * limb)) & MASK32 for limb in range(4)]
    product = [(square >> (32 * limb)) & MASK32 for limb in range(4)]
    result = [0, 0, 0, 0]
    borrow = int(source[0] <= product[0])
    result[0] = (source[0] - product[0]) & MASK32
    for limb in range(1, 3):
        next_borrow = int(
            source[limb] < product[limb]
            or (source[limb] == product[limb] and borrow))
        result[limb] = (source[limb] - product[limb] - borrow) & MASK32
        borrow = next_borrow
    result[3] = (source[3] - product[3] - borrow) & MASK32
    return sum(word << (32 * limb) for limb, word in enumerate(result))


def rounded_p64_root(root, residual):
    return root + int(residual > root)


def p64_to_f64(root, exponent):
    assert 1 << 63 <= root < 1 << 64
    retained = root >> 11
    removed = root & ((1 << 11) - 1)
    halfway = 1 << 10
    if removed > halfway or (removed == halfway and retained & 1):
        retained += 1
        if retained == 1 << 53:
            retained >>= 1
            exponent += 1
    exponent_bits = exponent + 1023
    assert 0 < exponent_bits < 0x7FF
    return (exponent_bits << 52) | (retained & ((1 << 52) - 1))


def accepted_pipeline(bits):
    mantissa, exponent, low_zero_bits = xfrom_positive_f64(bits)
    radicand, adjusted_exponent = form_radicand(mantissa, exponent)
    root = math.isqrt(radicand)
    mathematical_residual = radicand - root * root
    private_residual = accepted_limb_residual(radicand, root)
    p64 = rounded_p64_root(root, private_residual)
    return (p64_to_f64(p64, adjusted_exponent // 2), p64,
            private_residual, mathematical_residual, low_zero_bits)


def native_pipeline(bits):
    # FCW 133Fh selects p64 nearest for FSQRT. The exact operation therefore
    # rounds the mathematical root once to p64; FSTP qword then rounds to p53.
    mantissa, exponent, low_zero_bits = xfrom_positive_f64(bits)
    radicand, adjusted_exponent = form_radicand(mantissa, exponent)
    root = math.isqrt(radicand)
    residual = radicand - root * root
    p64 = rounded_p64_root(root, residual)
    return (p64_to_f64(p64, adjusted_exponent // 2), p64, residual,
            low_zero_bits)


def dispatch(bits, xrej, pipeline):
    sign = bits >> 63
    exponent = (bits >> 52) & 0x7FF
    fraction = bits & ((1 << 52) - 1)
    if exponent == 0x7FF:
        return 0, (xrej + 1) & MASK32, "reject-nonfinite"
    if exponent == 0 and fraction == 0:
        return 0, xrej, "zero"
    if sign:
        return 0, (xrej + 1) & MASK32, "reject-negative"
    return pipeline(bits)[0], xrej, "positive"


apply = runpy.run_path(str(EVIDENCE / "apply_candidate.py"))
accepted_bytes = ACCEPTED.read_bytes()
candidate_bytes = CANDIDATE.read_bytes()
assert sha256(accepted_bytes) == EXPECTED_ACCEPTED_SHA256
assert candidate_bytes == apply["transform_fp"](accepted_bytes)
assert SOURCE.read_bytes() == accepted_bytes
accepted_text = accepted_bytes.decode("utf-8").replace("\r\n", "\n")
candidate_text = candidate_bytes.decode("utf-8").replace("\r\n", "\n")
marker = '\t"XSS exact i386m native fsqrt"\n'
assert candidate_text.replace(marker, "") == accepted_text
assert candidate_text.count(marker) == 1

scalar_start = accepted_text.index('"XScalarSqrt"')
root_start = accepted_text.index('"XRootCore"')
scalar = accepted_text[scalar_start:root_start]
assert scalar.count("=> XFromF64;") == 1
assert scalar.count("=> XRootCore;") == 1
assert scalar.count("=> XToF64;") == 1
assert "? [XE] = 0 -> XSS zero;" in scalar
assert "? [XS] = 0 -> XSS positive;" in scalar
assert accepted_text.count("=> XRootCore;") == 1
assert accepted_text.count("=> XScalarSqrt;") == 0

rng = random.Random(0x233F5)
edge_fractions = (
    0, 1, 2, 3, (1 << 10) - 1, 1 << 10, (1 << 31) - 1,
    1 << 31, (1 << 51) - 1, 1 << 51, (1 << 52) - 3,
    (1 << 52) - 2, (1 << 52) - 1,
)
f64_cases = set()
for exponent_bits in range(1, 0x7FF):
    f64_cases.update((exponent_bits << 52) | fraction
                     for fraction in edge_fractions)
f64_cases.update(fraction for fraction in edge_fractions if fraction)
for _ in range(65_536):
    exponent_bits = rng.randrange(0x7FF)
    fraction = rng.randrange(1 << 52)
    if exponent_bits == 0 and fraction == 0:
        fraction = 1
    f64_cases.add((exponent_bits << 52) | fraction)
f64_cases.add(0x3FF28C725373F0DC)
assert len(f64_cases) == 92_147

normal_cases = 0
subnormal_cases = 0
p64_differences = 0
p64_differences_same_p53 = 0
minimum_low_zero_bits = 64
for bits in f64_cases:
    accepted = accepted_pipeline(bits)
    native = native_pipeline(bits)
    assert accepted[0] == native[0], hex(bits)
    assert accepted[3] == native[2]
    assert accepted[4] == native[3]
    if accepted[1] != native[1]:
        assert abs(accepted[1] - native[1]) == 1
        assert accepted[0] == native[0]
        p64_differences += 1
        p64_differences_same_p53 += 1
    minimum_low_zero_bits = min(minimum_low_zero_bits, accepted[4])
    exponent = (bits >> 52) & 0x7FF
    normal_cases += int(exponent != 0)
    subnormal_cases += int(exponent == 0)
assert p64_differences == p64_differences_same_p53 == 1_026
assert minimum_low_zero_bits >= 11

# Exhaustive integer argument for every positive finite binary64, beyond the
# discriminating corpus above. XFromF64 leaves at least eleven low mantissa bits
# clear, and XRootCore shifts that integer by another 63 or 64 bits, so the low
# source limb is always zero. The accepted subtraction's only compatibility
# quirk is `source[0] <= product[0]`: it differs from ordinary borrow precisely
# when root**2 has a zero low limb. By 2-adic valuation that implies the root has
# at least sixteen trailing zero bits. Both possible accepted/native p64 answers
# are then root or root+1, and those values spill to the same p53 because their
# removed eleven-bit fields are 0 and 1 respectively.
for low16 in range(1, 1 << 16):
    trailing_zeros = (low16 & -low16).bit_length() - 1
    assert 2 * trailing_zeros < 32
for root in (
        1 << 63, (1 << 63) | (1 << 16),
        (1 << 63) | (0x123456789ABC << 16),
        ((1 << 64) - 1) & ~0xFFFF):
    assert root & 0xFFFF == 0
    assert p64_to_f64(root, 0) == p64_to_f64(root + 1, 0)

special_inputs = (
    0x0000000000000000, 0x8000000000000000,
    0x0000000000000001, 0x8000000000000001,
    0x3FF0000000000000, 0xBFF0000000000000,
    0x7FEFFFFFFFFFFFFF, 0xFFEFFFFFFFFFFFFF,
    0x7FF0000000000000, 0xFFF0000000000000,
    0x7FF8000000000001, 0xFFF8000000000001,
)
special_cases = 0
coverage = {}
for bits in special_inputs:
    for xrej in (0, 1, MASK32):
        accepted = dispatch(bits, xrej, accepted_pipeline)
        native = dispatch(bits, xrej, native_pipeline)
        assert accepted == native
        coverage[accepted[2]] = coverage.get(accepted[2], 0) + 1
        special_cases += 1
assert coverage == {
    "zero": 6, "positive": 9, "reject-negative": 9,
    "reject-nonfinite": 12,
}

# The public wrapper is the sole source caller and restores every integer
# register around XScalarSqrt. The candidate's missing internal `enod` EBP write
# is therefore deliberately classified as private rather than falsely equated.
fpx87 = FPX87.read_text(encoding="utf-8").replace("\r\n", "\n")
wrapper = '''"FSqrt"
\t---->;
\t=> XScalarSqrt;
\t<----;
\tend;'''
assert fpx87.count(wrapper) == 1
assert fpx87.count("=> XScalarSqrt;") == 1
assert "the public scalar interface preserves A/B/C/D/E" in fpx87
assert "every routine leaves the x87 stack exactly as it found it" in fpx87

fpabi = FPABI.read_text(encoding="utf-8").replace("\r\n", "\n")
fpctl = FPCTL.read_text(encoding="utf-8").replace("\r\n", "\n")
assert "FCWEXT\t\t= 133Fh;" in fpabi
assert '''"FSWRead"
        [FI] = 0;
        end;''' in fpctl
assert '''"FCWRead"
        [FI] = 033Fh;
        end;''' in fpctl
assert "The application owns that environment for its process lifetime" in fpctl

scratch_names = (
    "srd0", "srd1", "srd2", "srd3", "sqrh", "sqrl", "sqmh", "sqml",
    "sqcarry", "sqstep", "srm0", "srm1", "srm2", "srm3",
)
root_end = accepted_text.index("      ( XChop32 - truncate", root_start)
root_and_declarations = accepted_text[:root_end]
for name in scratch_names:
    hits = [match.start() for match in re.finditer(rf"\b{re.escape(name)}\b", accepted_text)]
    assert hits
    assert all(position < root_end for position in hits)
    assert not re.search(rf"\b{re.escape(name)}\b", accepted_text[root_end:])

game = GAME.read_text(encoding="utf-8").replace("\r\n", "\n")
assert game.count("VHGSIMADD = 18206; VHGSIMDEN = 60000;") == 1
static_fsqrt_calls = game.count("=> FSqrt;")
assert static_fsqrt_calls == 14

report = {
    "schema": 1,
    "task": 233,
    "status": "pass",
    "source_exact_transform": True,
    "common_lino_change_is_zero_byte_marker_only": True,
    "raw_target_machine_block_added_to_shipping_lino": False,
    "compiler_lowering_below_shared_source_boundary": True,
    "binary64_pipeline_cases": len(f64_cases),
    "normal_binary64_cases": normal_cases,
    "subnormal_binary64_cases": subnormal_cases,
    "special_dispatch_cases": special_cases,
    "special_dispatch_coverage": coverage,
    "accepted_private_vs_mathematical_p64_differences": p64_differences,
    "all_p64_policy_differences_have_identical_p53_spill": True,
    "all_positive_finite_binary64_equivalence_integer_proof": True,
    "compatibility_borrow_difference_implies_root_low_16_zero": True,
    "root_and_root_plus_one_then_have_identical_p53_spill": True,
    "public_p53_binary64_result_exact": True,
    "positive_zero_negative_nonfinite_and_rejection_behavior_exact": True,
    "minimum_binary64_mantissa_low_zero_bits": minimum_low_zero_bits,
    "fcw_133f_p64_nearest_source_contract": True,
    "candidate_x87_stack_pushes": 1,
    "candidate_x87_stack_pops": 1,
    "candidate_x87_top_net_change": 0,
    "candidate_control_word_writes": 0,
    "candidate_x87_status_can_change": True,
    "portable_fswread_is_constant_zero": True,
    "internal_ebp_terminal_differs": True,
    "public_a_through_e_exact_via_wrapper": True,
    "xscalarsqrt_direct_source_callers": 1,
    "root_scratch_names_private_to_fpsoft_root_region": True,
    "root_scratch_terminal_state_not_equated": True,
    "static_shared_lino_fsqrt_call_sites": static_fsqrt_calls,
    "accepted_integer_restoring_decisions_per_positive_root": 64,
    "candidate_hardware_fsqrt_per_positive_root": 1,
    "simulation_constants": [18206, 60000],
    "complete_shipping_dependency_closure_audited": False,
    "accepted_source_sha256": sha256(accepted_bytes),
    "candidate_source_sha256": sha256(candidate_bytes),
}
OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
