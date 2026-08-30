from pathlib import Path
import hashlib
import json
import math
import random
import runpy
import struct

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/restoring-fsqrt-20260830"
ACCEPTED = EVIDENCE / "accepted/fpsoft.txt"
SOURCE = ROOT / "work/fp/fpsoft.txt"
FPX87 = ROOT / "work/fp/fpx87.txt"
GAME = ROOT / "work/vhgame.txt"
OUTPUT = EVIDENCE / "model.json"
EXPECTED_ACCEPTED_SHA256 = (
    "5031845ed5dbc0e7913eca691259873d45f0bfc67f1969a14dbd3c3ae172527a")
EXPECTED_CANDIDATE_SHA256 = (
    "6b2e209be5b62013276514f8c418cafc92ecb9fd4d9fd6fbdf91453bfebe66d3")
MASK32 = (1 << 32) - 1
MASK64 = (1 << 64) - 1
MASK128 = (1 << 128) - 1


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def f64_bits(value):
    return struct.unpack("<Q", struct.pack("<d", value))[0]


def xfrom_positive_f64(bits):
    exponent_bits = (bits >> 52) & 0x7FF
    fraction = bits & ((1 << 52) - 1)
    assert bits >> 63 == 0 and exponent_bits != 0x7FF
    if exponent_bits:
        mantissa = ((1 << 52) | fraction) << 11
        exponent = exponent_bits - 1023
    else:
        assert fraction
        width = fraction.bit_length()
        mantissa = fraction << (64 - width)
        exponent = width - 1 - 1074
    assert 1 << 63 <= mantissa < 1 << 64
    return mantissa, exponent


def form_radicand(mantissa, exponent):
    if exponent & 1:
        return mantissa << 64, exponent - 1
    return mantissa << 63, exponent


def trial_square_root(radicand):
    root = 0
    mask = 1 << 63
    for _ in range(64):
        candidate = root | mask
        if candidate * candidate <= radicand:
            root = candidate
        mask >>= 1
    residual = radicand - root * root
    return root, residual


def accepted_limb_residual(radicand, root):
    """Model XRootCore's accepted four-word subtraction byte-for-byte."""
    square = root * root
    source = [(radicand >> (32 * limb)) & MASK32 for limb in range(4)]
    product = [(square >> (32 * limb)) & MASK32 for limb in range(4)]
    result = [0, 0, 0, 0]

    # The accepted source uses strict unsigned greater-than here, so equality
    # incorrectly starts a borrow. Higher limbs propagate that accepted state
    # normally. This private p64 quirk is part of the compatibility target.
    borrow = int(source[0] <= product[0])
    result[0] = (source[0] - product[0]) & MASK32
    for limb in range(1, 3):
        next_borrow = int(
            source[limb] < product[limb]
            or (source[limb] == product[limb] and borrow))
        result[limb] = (
            source[limb] - product[limb] - borrow) & MASK32
        borrow = next_borrow
    result[3] = (source[3] - product[3] - borrow) & MASK32
    return sum(word << (32 * limb) for limb, word in enumerate(result))


def accepted_trial_square_root(radicand):
    root, mathematical_residual = trial_square_root(radicand)
    assert root * root + mathematical_residual == radicand
    return root, accepted_limb_residual(radicand, root)


def compatible_residual(root, mathematical_residual):
    # The fixed radicand's low word is zero. q*q has the same low word exactly
    # when q's low 16 bits are zero, which is the accepted false-borrow case.
    if root & 0xFFFF:
        return mathematical_residual
    assert mathematical_residual & MASK32 == 0
    return (mathematical_residual - (1 << 32)) & MASK128


def restoring_compatible_root(radicand):
    root, mathematical_residual = restoring_integer_root(radicand)
    return root, compatible_residual(root, mathematical_residual)


def restoring_compatible_word_root(radicand):
    root, mathematical_residual, remainder_bits = restoring_word_root(radicand)
    return (root, compatible_residual(root, mathematical_residual),
            remainder_bits)


def restoring_integer_root(radicand):
    root = 0
    residual = 0
    for step in range(64):
        pair = (radicand >> (126 - 2 * step)) & 3
        residual = (residual << 2) | pair
        root <<= 1
        trial = (root << 1) | 1
        if residual >= trial:
            residual -= trial
            root += 1
    return root, residual


def restoring_word_root(radicand):
    srd0 = radicand & MASK32
    srd1 = (radicand >> 32) & MASK32
    srd2 = (radicand >> 64) & MASK32
    srd3 = (radicand >> 96) & MASK32
    sqrh = 0
    sqrl = 0
    srm0 = 0
    srm1 = 0
    srm2 = 0
    max_remainder_bits = 0
    for _ in range(64):
        pair = srd3 >> 30
        srd3 = ((srd3 << 2) | (srd2 >> 30)) & MASK32
        srd2 = ((srd2 << 2) | (srd1 >> 30)) & MASK32
        srd1 = ((srd1 << 2) | (srd0 >> 30)) & MASK32
        srd0 = (srd0 << 2) & MASK32

        srm2 = ((srm2 << 2) | (srm1 >> 30)) & MASK32
        srm1 = ((srm1 << 2) | (srm0 >> 30)) & MASK32
        srm0 = ((srm0 << 2) | pair) & MASK32

        carry = sqrl >> 31
        sqrh = ((sqrh << 1) | carry) & MASK32
        sqrl = (sqrl << 1) & MASK32
        sqcarry = sqrh >> 31
        sqmh = ((sqrh << 1) | (sqrl >> 31)) & MASK32
        sqml = ((sqrl << 1) | 1) & MASK32

        if (srm2, srm1, srm0) >= (sqcarry, sqmh, sqml):
            borrow = int(srm0 < sqml)
            srm0 = (srm0 - sqml) & MASK32
            next_borrow = int(srm1 < sqmh or (srm1 == sqmh and borrow))
            srm1 = (srm1 - sqmh - borrow) & MASK32
            srm2 = (srm2 - sqcarry - next_borrow) & MASK32
            sqrl = (sqrl + 1) & MASK32
            if sqrl == 0:
                sqrh = (sqrh + 1) & MASK32

        residual = (srm2 << 64) | (srm1 << 32) | srm0
        max_remainder_bits = max(max_remainder_bits, residual.bit_length())

    assert srd0 == srd1 == srd2 == srd3 == 0
    root = (sqrh << 32) | sqrl
    residual = (srm2 << 64) | (srm1 << 32) | srm0
    return root, residual, max_remainder_bits


def rounded_p64_root(root, residual):
    rounded = root + int(residual > root)
    return rounded


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


def sqrt_pipeline(bits, root_function):
    mantissa, exponent = xfrom_positive_f64(bits)
    radicand, adjusted_exponent = form_radicand(mantissa, exponent)
    root, residual = root_function(radicand)[:2]
    root = rounded_p64_root(root, residual)
    assert root < 1 << 64
    return p64_to_f64(root, adjusted_exponent // 2), root, residual


def special_sqrt(bits, xrej, root_function):
    sign = bits >> 63
    exponent = (bits >> 52) & 0x7FF
    fraction = bits & ((1 << 52) - 1)
    if exponent == 0x7FF:
        return 0, xrej + 1
    if exponent == 0 and fraction == 0:
        return 0, xrej
    if sign:
        return 0, xrej + 1
    return sqrt_pipeline(bits, root_function)[0], xrej


apply = runpy.run_path(str(EVIDENCE / "apply_candidate.py"))
transform = apply["transform"]
accepted_bytes = ACCEPTED.read_bytes()
candidate_bytes = transform(accepted_bytes)
assert sha256(accepted_bytes) == EXPECTED_ACCEPTED_SHA256
assert sha256(candidate_bytes) == EXPECTED_CANDIDATE_SHA256
assert SOURCE.read_bytes() == candidate_bytes
accepted = accepted_bytes.decode("utf-8").replace("\r\n", "\n")
candidate = candidate_bytes.decode("utf-8").replace("\r\n", "\n")
assert accepted.count('"XRootCore"') == candidate.count('"XRootCore"') == 1
accepted_start = accepted.index('"XRootCore"')
accepted_end = accepted.index("      ( XChop32 - truncate", accepted_start)
candidate_start = candidate.index('"XRootCore"')
candidate_end = candidate.index("      ( XChop32 - truncate", candidate_start)
accepted_root = accepted[accepted_start:accepted_end]
candidate_root = candidate[candidate_start:candidate_end]
assert accepted_root.count("=> Mul128;") == 2
assert "=> Mul128;" not in candidate_root
assert '"XRoot bit loop"' in accepted_root
assert '"XRoot restoring loop"' in candidate_root
assert candidate_root.count("[sqstep]+;") == 1
assert "? [sqstep] < 64 -> XRoot restoring loop;" in candidate_root
assert "[srm0] = 0; [srm1] = 0; [srm2] = 0;\n\t[sqstep] = 0;" in candidate_root
assert "[srm2] = 0; [srm3] = 0;" not in candidate_root
assert "A = [sqrl]; A & XM16;" in candidate_root
assert "[srm1]-;\n\t? [srm1] != 0FFFFFFFFh" in candidate_root
assert "[srm2]-;\n\t? [srm2] != 0FFFFFFFFh" in candidate_root
assert "E = 0FFFFFFFFh;\n    \"XRoot residual compatible\"" in candidate_root
assert "A = E; [srm3] = A;" in candidate_root
assert "A | B; C = A;" in candidate_root
assert "A | 1; D = A;" in candidate_root
assert "A = [srm0]; B = D;" in candidate_root
assert "A = [srm1]; A - C; A - E;" in candidate_root
assert candidate_root.endswith(
    "\tend;\n\t( Unreachable footprint calibration: preserve downstream "
    "addresses. )\n\tA = 0; A = 0; A = 0; A = 0;\n\n")
assert all(name in candidate_root for name in (
    "srd0", "srd1", "srd2", "srd3", "sqrh", "sqrl", "sqcarry",
    "sqstep", "srm0", "srm1", "srm2", "srm3",
))
assert "[sqmh]" not in candidate_root and "[sqml]" not in candidate_root
assert accepted[:accepted.index("\t( square-root state:")] == candidate[
    :candidate.index("\t( square-root state:")]
assert accepted[accepted_end:] == candidate[candidate_end:]

# Exercise generic normalized mantissas for both exponent parities, including
# exact squares and residual rounding boundaries. The source-shaped 32-bit
# implementation must agree with both the trial-square algorithm and isqrt.
rng = random.Random(222)
mantissas = {
    1 << 63,
    (1 << 63) + 1,
    (1 << 63) + (1 << 31),
    (1 << 64) - 3,
    (1 << 64) - 2,
    (1 << 64) - 1,
}
for _ in range(32_768):
    mantissas.add((1 << 63) | rng.randrange(1 << 63))
generic_cases = 0
accepted_false_borrow_cases = 0
accepted_vs_mathematical_p64_differences = 0
max_remainder_bits = 0
for mantissa in mantissas:
    for exponent in (0, 1):
        radicand, _ = form_radicand(mantissa, exponent)
        old_root, mathematical_residual = trial_square_root(radicand)
        direct_root, direct_residual = restoring_integer_root(radicand)
        word_root, word_residual, remainder_bits = restoring_word_root(radicand)
        assert old_root == direct_root == word_root == math.isqrt(radicand)
        assert mathematical_residual == direct_residual == word_residual
        assert word_root * word_root + word_residual == radicand
        assert word_residual < 2 * word_root + 1

        accepted_private = accepted_limb_residual(radicand, old_root)
        direct_private = compatible_residual(direct_root, direct_residual)
        word_private = compatible_residual(word_root, word_residual)
        assert accepted_private == direct_private == word_private
        accepted_rounded = rounded_p64_root(old_root, accepted_private)
        candidate_rounded = rounded_p64_root(word_root, word_private)
        mathematical_rounded = rounded_p64_root(old_root, mathematical_residual)
        assert accepted_rounded == candidate_rounded
        if not old_root & 0xFFFF:
            accepted_false_borrow_cases += 1
        if accepted_rounded != mathematical_rounded:
            accepted_vs_mathematical_p64_differences += 1
        max_remainder_bits = max(max_remainder_bits, remainder_bits)
        generic_cases += 1

# Pin the adversarial exact-square case which exposed the accepted false borrow.
one_radicand, _ = form_radicand(1 << 63, 0)
one_root, one_math_residual = trial_square_root(one_radicand)
one_accepted_residual = accepted_limb_residual(one_radicand, one_root)
assert one_root == 1 << 63 and one_math_residual == 0
assert one_accepted_residual == (-(1 << 32)) & MASK128
assert rounded_p64_root(one_root, one_accepted_residual) == one_root + 1
assert accepted_false_borrow_cases > 0
assert accepted_vs_mathematical_p64_differences > 0

# Cover every binary64 exponent class with difficult fraction patterns, all
# positive subnormal edge classes, and a deterministic broad sample.
edge_fractions = (
    0,
    1,
    2,
    3,
    (1 << 10) - 1,
    1 << 10,
    (1 << 31) - 1,
    1 << 31,
    (1 << 51) - 1,
    1 << 51,
    (1 << 52) - 3,
    (1 << 52) - 2,
    (1 << 52) - 1,
)
f64_cases = set()
for exponent_bits in range(1, 0x7FF):
    f64_cases.update((exponent_bits << 52) | fraction
                     for fraction in edge_fractions)
subnormal_fractions = {
    1,
    2,
    3,
    (1 << 10) - 1,
    1 << 10,
    (1 << 31) - 1,
    1 << 31,
    (1 << 51) - 1,
    1 << 51,
    (1 << 52) - 3,
    (1 << 52) - 2,
    (1 << 52) - 1,
}
f64_cases.update(subnormal_fractions)
for _ in range(65_536):
    exponent_bits = rng.randrange(0x7FF)
    fraction = rng.randrange(1 << 52)
    if exponent_bits == 0 and fraction == 0:
        fraction = 1
    f64_cases.add((exponent_bits << 52) | fraction)

pipeline_cases = 0
pipeline_accepted_vs_mathematical_p64_differences = 0
for bits in f64_cases:
    accepted_pipeline = sqrt_pipeline(bits, accepted_trial_square_root)
    restored = sqrt_pipeline(bits, restoring_compatible_word_root)
    mathematical = sqrt_pipeline(bits, trial_square_root)
    reference_mantissa, reference_exponent = xfrom_positive_f64(bits)
    radicand, _ = form_radicand(reference_mantissa, reference_exponent)
    assert accepted_pipeline == restored
    assert accepted_pipeline[0] == mathematical[0]
    assert restored[1] == rounded_p64_root(
        math.isqrt(radicand), accepted_limb_residual(
            radicand, math.isqrt(radicand)))
    if accepted_pipeline[1] != mathematical[1]:
        pipeline_accepted_vs_mathematical_p64_differences += 1
    pipeline_cases += 1

# The unchanged scalar dispatch preserves all zero/sign/rejection behavior.
special_inputs = (
    0x0000000000000000,
    0x8000000000000000,
    0x8000000000000001,
    0xBFF0000000000000,
    0xFFF0000000000000,
    0x7FF0000000000000,
    0x7FF8000000000001,
    0xFFF8000000000001,
)
special_cases = 0
for bits in special_inputs:
    for xrej in (0, 1, MASK32):
        accepted_special = special_sqrt(
            bits, xrej, accepted_trial_square_root)
        candidate_special = special_sqrt(
            bits, xrej, restoring_compatible_word_root)
        assert accepted_special == candidate_special
        special_cases += 1

# Source-ground the public state boundary and hot local-render usage.
fpx87 = FPX87.read_text(encoding="utf-8").replace("\r\n", "\n")
game = GAME.read_text(encoding="utf-8").replace("\r\n", "\n")
assert '"FSqrt"\n\t---->;\n\t=> XScalarSqrt;\n\t<----;' in fpx87
assert "the public scalar interface preserves A/B/C/D/E" in fpx87
assert accepted.count('"XScalarSqrt"') == candidate.count('"XScalarSqrt"') == 1
scalar = candidate[candidate.index('"XScalarSqrt"'):candidate.index(
    '"XRootCore"')]
assert "? [XE] = 0 -> XSS zero;" in scalar
assert "? [XS] = 0 -> XSS positive;" in scalar
assert "[XREJ]+; [FA0] = 0; [FA1] = 0;" in scalar
assert "=> XRootCore;\n\t=> XToF64;" in scalar
assert game.count("=> VHG local body distance;") == 5
body_distance = game[game.index('"VHG local body distance"'):game.index(
    '"VHG local far pixel"')]
assert "=> FSqrt; [VHGlocaldist0] = [FA0]; [VHGlocaldist1] = [FA1];" in body_distance
assert "? A '>= [nsnob] -> VHG local resident pair ready;" in game
assert "[VHGlocalbody]+; -> VHG local body loop;" in game
assert game.count("VHGSIMADD = 18206; VHGSIMDEN = 60000;") == 1

state_cases = 0
rng = random.Random(0x222)
case_list = tuple(f64_cases)
for _ in range(4_096):
    bits = case_list[rng.randrange(len(case_list))]
    entry = {name: rng.randrange(1 << 32) for name in (
        "A", "B", "C", "D", "E", "FB0", "FB1", "FI", "FFLG", "FS0",
        "XTOP", "XDEPTH", "XREJ",
    )}
    output = sqrt_pipeline(bits, restoring_compatible_word_root)[0]
    accepted_state = dict(entry)
    candidate_state = dict(entry)
    converged = {
        "FA0": output & MASK32,
        "FA1": output >> 32,
        "XREJ": entry["XREJ"],
    }
    accepted_state.update(converged)
    candidate_state.update(converged)
    assert accepted_state == candidate_state
    state_cases += 1

result = {
    "schema": 1,
    "task": 222,
    "status": "pass",
    "candidate_file_equals_exact_transform": True,
    "generic_normalized_mantissa_cases": generic_cases,
    "binary64_pipeline_cases": pipeline_cases,
    "special_dispatch_cases": special_cases,
    "public_state_cases": state_cases,
    "max_restoring_remainder_bits": max_remainder_bits,
    "accepted_false_low_limb_borrow_cases": accepted_false_borrow_cases,
    "generic_accepted_vs_mathematical_p64_differences": (
        accepted_vs_mathematical_p64_differences),
    "pipeline_accepted_vs_mathematical_p64_differences": (
        pipeline_accepted_vs_mathematical_p64_differences),
    "trial_square_mul128_calls_per_positive_root": 65,
    "candidate_mul128_calls_per_positive_root": 0,
    "restoring_iterations_per_positive_root": 64,
    "integer_root_exact": True,
    "mathematical_residual_exact_before_compatibility": True,
    "accepted_private_residual_exact": True,
    "accepted_p64_root_rounding_exact": True,
    "p53_binary64_spill_exact": True,
    "accepted_false_borrow_compatibility": (
        "subtract 2^32 modulo 2^128 when q low16 is zero"),
    "sqrt_one_accepted_p64_is_0x8000000000000001": True,
    "sqrt_one_public_binary64_exact": True,
    "positive_zero_negative_and_rejection_behavior_exact": True,
    "public_a_through_e_exact": True,
    "fb_fi_fflg_fs0_exact": True,
    "xtop_xdepth_stack_exact": True,
    "xrej_delta_exact": True,
    "accepted_srm0_through_srm3_exact": True,
    "other_private_root_scratch_unobserved": True,
    "rooted_distance_and_renderer_control_exact": True,
    "simulation_constants": [18206, 60000],
    "source_boundary": "one common tracked shared-Lino closure",
    "raw_target_machine_blocks_added": False,
    "compiler_unchanged": True,
    "cpu_pack_unchanged": True,
    "accepted_source_sha256": sha256(accepted_bytes),
    "candidate_source_sha256": sha256(candidate_bytes),
    "vhgame_source_sha256": sha256(GAME.read_bytes()),
    "fpx87_source_sha256": sha256(FPX87.read_bytes()),
}
OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
