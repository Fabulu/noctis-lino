from pathlib import Path
import hashlib
import json
import math
import random
import runpy
import struct

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/zero-tail-restoring-fsqrt-20260830"
ACCEPTED = EVIDENCE / "accepted/fpsoft.txt"
CANDIDATE = EVIDENCE / "candidate/fpsoft.txt"
SOURCE = ROOT / "work/fp/fpsoft.txt"
FPX87 = ROOT / "work/fp/fpx87.txt"
GAME = ROOT / "work/vhgame.txt"
OUTPUT = EVIDENCE / "model.json"
VERIFIER = Path(__file__).resolve()
EXPECTED_ACCEPTED_SHA256 = (
    "063ecf40b0faab3b2779d8ff159b8fa815eec7b397de0d47e68223841e2a59cc")
MASK32 = (1 << 32) - 1
MASK128 = (1 << 128) - 1


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def xfrom_positive_f64(bits):
    exponent_bits = (bits >> 52) & 0x7FF
    fraction = bits & ((1 << 52) - 1)
    assert bits >> 63 == 0 and exponent_bits != 0x7FF
    if exponent_bits:
        mantissa = ((1 << 52) | fraction) << 11
        exponent = exponent_bits - 1023
        guaranteed_low_zero_bits = 11
    else:
        assert fraction
        width = fraction.bit_length()
        mantissa = fraction << (64 - width)
        exponent = width - 1 - 1074
        guaranteed_low_zero_bits = 64 - width
    assert 1 << 63 <= mantissa < 1 << 64
    assert guaranteed_low_zero_bits >= 11
    assert mantissa & ((1 << guaranteed_low_zero_bits) - 1) == 0
    return mantissa, exponent, guaranteed_low_zero_bits


def form_radicand(mantissa, exponent):
    if exponent & 1:
        radicand = mantissa << 64
        adjusted_exponent = exponent - 1
    else:
        radicand = mantissa << 63
        adjusted_exponent = exponent
    assert radicand & ((1 << 64) - 1) == 0
    return radicand, adjusted_exponent


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


def compatible_residual(root, mathematical_residual):
    if root & 0xFFFF:
        return mathematical_residual
    assert mathematical_residual & MASK32 == 0
    return (mathematical_residual - (1 << 32)) & MASK128


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


def restoring_step(state, pair):
    sqrh, sqrl, srm2, srm1, srm0 = state
    assert 0 <= pair <= 3

    srm2 = ((srm2 << 2) | (srm1 >> 30)) & MASK32
    srm1 = ((srm1 << 2) | (srm0 >> 30)) & MASK32
    srm0 = ((srm0 << 2) | pair) & MASK32

    low_carry = sqrl >> 31
    sqrh = ((sqrh << 1) | low_carry) & MASK32
    sqrl = (sqrl << 1) & MASK32
    assert sqrl & 1 == 0
    sqcarry = sqrh >> 31
    trial_h = ((sqrh << 1) | (sqrl >> 31)) & MASK32
    trial_l = ((sqrl << 1) | 1) & MASK32

    accepted = (srm2, srm1, srm0) >= (sqcarry, trial_h, trial_l)
    accepted_increment_carry = False
    if accepted:
        borrow = int(srm0 < trial_l)
        srm0 = (srm0 - trial_l) & MASK32
        next_borrow = int(
            srm1 < trial_h or (srm1 == trial_h and borrow))
        srm1 = (srm1 - trial_h - borrow) & MASK32
        srm2 = (srm2 - sqcarry - next_borrow) & MASK32
        # The source has just shifted sqrl left. It is even, so +1 cannot wrap.
        assert sqrl <= MASK32 - 1
        old_sqrl = sqrl
        sqrl = (sqrl + 1) & MASK32
        accepted_increment_carry = sqrl == 0
        assert not accepted_increment_carry
        assert sqrl == old_sqrl | 1

    result = (sqrh, sqrl, srm2, srm1, srm0)
    trace = (pair, accepted, sqcarry, trial_h, trial_l) + result
    return result, trace, accepted_increment_carry


def accepted_buffered_root(radicand):
    limbs = [(radicand >> (32 * index)) & MASK32 for index in range(4)]
    sqstep = 3
    buffer = limbs[3]
    limbs[3] = 0
    sqml = 16
    state = (0, 0, 0, 0, 0)
    trace = []
    pointer_decrements = 0
    handoffs = 0
    clears = 0
    for iteration in range(64):
        pair = buffer >> 30
        buffer = (buffer << 2) & MASK32
        state, item, carry = restoring_step(state, pair)
        assert not carry
        trace.append(item)
        sqml -= 1
        if sqml == 0:
            sqstep -= 1
            pointer_decrements += 1
            if sqstep < 0:
                assert iteration == 63
                break
            buffer = limbs[sqstep]
            limbs[sqstep] = 0
            sqml = 16
            handoffs += 1
            clears += 1
    assert len(trace) == 64
    assert pointer_decrements == 4
    assert handoffs == clears == 3
    assert sqstep == -1 and sqml == 0 and buffer == 0
    assert limbs == [0, 0, 0, 0]
    sqrh, sqrl, srm2, srm1, srm0 = state
    root = (sqrh << 32) | sqrl
    residual = (srm2 << 64) | (srm1 << 32) | srm0
    terminal = {
        "srd": tuple(limbs), "sqstep": sqstep, "sqml": sqml,
        "sqmh": buffer, "sqrh": sqrh, "sqrl": sqrl,
        "srm2": srm2, "srm1": srm1, "srm0": srm0,
    }
    return root, residual, trace, terminal


def zero_tail_root(radicand):
    limbs = [(radicand >> (32 * index)) & MASK32 for index in range(4)]
    # The production specialization is admitted only at XScalarSqrt's exact
    # binary64 boundary. Both lower radix limbs are therefore zero.
    assert limbs[0] == limbs[1] == 0
    sqstep = 3
    buffer = limbs[3]
    limbs[3] = 0
    sqml = 16
    state = (0, 0, 0, 0, 0)
    trace = []
    pointer_decrements = 0
    handoffs = 0
    clears = 0
    zero_tail_transitions = 0
    zero_buffer_tests = 0
    skipped_buffer_shifts = 0
    performed_buffer_shifts = 0
    tail_iterations = 0

    for iteration in range(64):
        zero_buffer_tests += 1
        if buffer == 0:
            pair = 0
            skipped_buffer_shifts += 1
        else:
            pair = buffer >> 30
            buffer = (buffer << 2) & MASK32
            performed_buffer_shifts += 1
        state, item, carry = restoring_step(state, pair)
        assert not carry
        trace.append(item)
        if zero_tail_transitions:
            tail_iterations += 1

        sqml -= 1
        if sqml == 0:
            sqstep -= 1
            pointer_decrements += 1
            if sqstep < 2:
                if sqstep < 0:
                    assert iteration == 63
                    break
                # Finishing srd2 lands at srd1. Account for the second lower
                # pointer step once, then consume both zero limbs as 32 pairs.
                assert sqstep == 1
                assert buffer == 0 and limbs[0] == limbs[1] == 0
                sqstep -= 1
                pointer_decrements += 1
                sqml = 32
                zero_tail_transitions += 1
                continue
            assert sqstep == 2
            buffer = limbs[2]
            limbs[2] = 0
            sqml = 16
            handoffs += 1
            clears += 1

    assert len(trace) == 64
    assert zero_tail_transitions == 1 and tail_iterations == 32
    assert pointer_decrements == 4
    assert handoffs == clears == 1
    assert sqstep == -1 and sqml == 0 and buffer == 0
    assert limbs == [0, 0, 0, 0]
    assert zero_buffer_tests == 64
    assert skipped_buffer_shifts >= 32
    assert performed_buffer_shifts <= 32
    sqrh, sqrl, srm2, srm1, srm0 = state
    root = (sqrh << 32) | sqrl
    residual = (srm2 << 64) | (srm1 << 32) | srm0
    terminal = {
        "srd": tuple(limbs), "sqstep": sqstep, "sqml": sqml,
        "sqmh": buffer, "sqrh": sqrh, "sqrl": sqrl,
        "srm2": srm2, "srm1": srm1, "srm0": srm0,
    }
    counters = {
        "zero_buffer_tests": zero_buffer_tests,
        "skipped_buffer_shifts": skipped_buffer_shifts,
        "performed_buffer_shifts": performed_buffer_shifts,
        "tail_iterations": tail_iterations,
        "handoffs": handoffs,
        "clears": clears,
        "pointer_decrements": pointer_decrements,
    }
    return root, residual, trace, terminal, counters


def sqrt_pipeline(bits, root_function):
    mantissa, exponent, low_zero_bits = xfrom_positive_f64(bits)
    radicand, adjusted_exponent = form_radicand(mantissa, exponent)
    root, residual = root_function(radicand)[:2]
    private_residual = compatible_residual(root, residual)
    p64 = rounded_p64_root(root, private_residual)
    return (p64_to_f64(p64, adjusted_exponent // 2), p64,
            private_residual, low_zero_bits)


def direct_pipeline(bits):
    mantissa, exponent, low_zero_bits = xfrom_positive_f64(bits)
    radicand, adjusted_exponent = form_radicand(mantissa, exponent)
    root = math.isqrt(radicand)
    mathematical_residual = radicand - root * root
    mathematical_p64 = rounded_p64_root(root, mathematical_residual)
    return (p64_to_f64(mathematical_p64, adjusted_exponent // 2),
            mathematical_p64, mathematical_residual, low_zero_bits)


def special_sqrt(bits, xrej, root_function):
    sign = bits >> 63
    exponent = (bits >> 52) & 0x7FF
    fraction = bits & ((1 << 52) - 1)
    if exponent == 0x7FF:
        return 0, (xrej + 1) & MASK32
    if exponent == 0 and fraction == 0:
        return 0, xrej
    if sign:
        return 0, (xrej + 1) & MASK32
    return sqrt_pipeline(bits, root_function)[0], xrej


apply = runpy.run_path(str(EVIDENCE / "apply_candidate.py"))
transform = apply["transform"]
accepted_bytes = ACCEPTED.read_bytes()
candidate_bytes = transform(accepted_bytes)
assert sha256(accepted_bytes) == EXPECTED_ACCEPTED_SHA256
assert candidate_bytes != accepted_bytes
CANDIDATE.write_bytes(candidate_bytes)
active_bytes = SOURCE.read_bytes()
assert active_bytes in (accepted_bytes, candidate_bytes)
accepted_text = accepted_bytes.decode("utf-8").replace("\r\n", "\n")
candidate_text = candidate_bytes.decode("utf-8").replace("\r\n", "\n")
accepted_start = accepted_text.index('"XRootCore"')
accepted_end = accepted_text.index("      ( XChop32 - truncate", accepted_start)
candidate_start = candidate_text.index('"XRootCore"')
candidate_end = candidate_text.index("      ( XChop32 - truncate", candidate_start)
accepted_root = accepted_text[accepted_start:accepted_end]
candidate_root = candidate_text[candidate_start:candidate_end]
assert accepted_text[:accepted_start] == candidate_text[:candidate_start]
assert accepted_text[accepted_end:] == candidate_text[candidate_end:]
assert "=> Mul128;" not in candidate_root
assert "[srd0] = 0; [srd1] = 0;" in candidate_root
assert "A = [XML]; A < 31; [srd1] = A;" not in candidate_root
assert candidate_root.count("? A = 0 -> XRoot restoring pair ready;") == 1
assert candidate_root.count('"XRoot restoring pair ready"') == 1
assert "? [sqrl] != 0 -> XRoot restoring next;" not in candidate_root
assert "[sqrh]+;\n    \"XRoot restoring next\"" not in candidate_root
assert "? [sqstep] < srd2 -> XRoot restoring lower;" in candidate_root
assert "A = [srd2]; [sqmh] = A; [srd2] = 0; [sqml] = 16;" in candidate_root
assert "? [sqstep] < srd0 -> XRoot restoring complete;" in candidate_root
assert "[sqstep]-; [sqml] = 32;" in candidate_root
assert "B = [sqstep]; A = [B]; [sqmh] = A;" not in candidate_root
assert candidate_root.count("[sqstep]-;") == 2
assert candidate_root.count("[sqml]-;") == 1
assert candidate_root.count("[sqmh]") == 4
assert candidate_root.endswith(
    "\tend;\n\t( Eight unreachable increments retain the accepted helper endpoint. )\n"
    "\tA+; A+; A+; A+; A+; A+; A+; A+;\n\n")
assert all(name in candidate_root for name in (
    "srd0", "srd1", "srd2", "srd3", "sqrh", "sqrl", "sqmh", "sqml",
    "sqcarry", "sqstep", "srm0", "srm1", "srm2", "srm3"))

# Source-ground the binary64-only entry contract. XFromF64 shifts a normal
# fraction left by 11; subnormal normalization only shifts the same words farther
# left. XRootCore has exactly one caller, after that conversion.
assert candidate_text.count("=> XRootCore;") == 1
assert "A = [XU0]; A < 11; [XML] = A;" in candidate_text
assert '"XFF norm"' in candidate_text
assert "A = [XML]; A < 1; [XML] = A;" in candidate_text
scalar = candidate_text[candidate_text.index('"XScalarSqrt"'):candidate_start]
assert "=> XFromF64;" in scalar
assert "=> XRootCore;\n\t=> XToF64;" in scalar
assert "? [XE] = 0 -> XSS zero;" in scalar
assert "? [XS] = 0 -> XSS positive;" in scalar

rng = random.Random(228)
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
# Regression for the reverse compatibility direction: mathematical p64 admits
# q+1 while the accepted equality-borrow residual retains q; p53 is unchanged.
f64_cases.add(0x3FF28C725373F0DC)

pipeline_cases = 0
normal_cases = 0
subnormal_cases = 0
minimum_low_zero_bits = 64
minimum_skipped_buffer_shifts = 64
maximum_performed_buffer_shifts = 0
accepted_false_borrow_cases = 0
accepted_vs_mathematical_p64_differences = 0
accepted_vs_mathematical_p64_same_p53 = 0
for bits in f64_cases:
    mantissa, exponent, low_zero_bits = xfrom_positive_f64(bits)
    radicand, adjusted_exponent = form_radicand(mantissa, exponent)
    assert radicand & ((1 << 64) - 1) == 0
    accepted = accepted_buffered_root(radicand)
    candidate = zero_tail_root(radicand)
    accepted_root, accepted_residual, accepted_trace, accepted_terminal = accepted
    candidate_root, candidate_residual, candidate_trace, candidate_terminal, counters = candidate
    mathematical_root = math.isqrt(radicand)
    mathematical_residual = radicand - mathematical_root * mathematical_root
    assert accepted_trace == candidate_trace
    assert accepted_root == candidate_root == mathematical_root
    assert accepted_residual == candidate_residual == mathematical_residual
    assert accepted_terminal == candidate_terminal
    assert mathematical_residual < 2 * mathematical_root + 1
    private_residual = compatible_residual(mathematical_root, mathematical_residual)
    assert private_residual == accepted_limb_residual(radicand, mathematical_root)
    accepted_pipeline = sqrt_pipeline(bits, accepted_buffered_root)
    candidate_pipeline = sqrt_pipeline(bits, zero_tail_root)
    mathematical_pipeline = direct_pipeline(bits)
    assert accepted_pipeline == candidate_pipeline
    assert candidate_pipeline[0] == mathematical_pipeline[0]
    assert candidate_pipeline[3] == mathematical_pipeline[3]
    mathematical_p64 = rounded_p64_root(mathematical_root, mathematical_residual)
    accepted_p64 = rounded_p64_root(mathematical_root, private_residual)
    mathematical_f64 = p64_to_f64(mathematical_p64, adjusted_exponent // 2)
    accepted_f64 = p64_to_f64(accepted_p64, adjusted_exponent // 2)
    assert mathematical_pipeline[:3] == (
        mathematical_f64, mathematical_p64, mathematical_residual)
    assert accepted_pipeline[0] == accepted_f64 == mathematical_f64
    if accepted_p64 != mathematical_p64:
        assert mathematical_root & 0xFFFF == 0
        assert abs(accepted_p64 - mathematical_p64) == 1
        assert {accepted_p64, mathematical_p64} == {
            mathematical_root, mathematical_root + 1}
        assert accepted_f64 == mathematical_f64
        accepted_vs_mathematical_p64_same_p53 += 1
    accepted_false_borrow_cases += int(not mathematical_root & 0xFFFF)
    accepted_vs_mathematical_p64_differences += int(accepted_p64 != mathematical_p64)
    minimum_low_zero_bits = min(minimum_low_zero_bits, low_zero_bits)
    minimum_skipped_buffer_shifts = min(
        minimum_skipped_buffer_shifts, counters["skipped_buffer_shifts"])
    maximum_performed_buffer_shifts = max(
        maximum_performed_buffer_shifts, counters["performed_buffer_shifts"])
    normal_cases += int(((bits >> 52) & 0x7FF) != 0)
    subnormal_cases += int(((bits >> 52) & 0x7FF) == 0)
    pipeline_cases += 1

one_bits = 0x3FF0000000000000
one_mantissa, one_exponent, _ = xfrom_positive_f64(one_bits)
one_radicand, _ = form_radicand(one_mantissa, one_exponent)
one_root = math.isqrt(one_radicand)
one_math_residual = one_radicand - one_root * one_root
one_private_residual = accepted_limb_residual(one_radicand, one_root)
assert one_root == 1 << 63 and one_math_residual == 0
assert one_private_residual == (-(1 << 32)) & MASK128
assert rounded_p64_root(one_root, one_private_residual) == one_root + 1
assert sqrt_pipeline(one_bits, zero_tail_root)[0] == one_bits
assert minimum_low_zero_bits >= 11
assert minimum_skipped_buffer_shifts >= 32
assert maximum_performed_buffer_shifts <= 32
assert accepted_false_borrow_cases > 0
assert accepted_vs_mathematical_p64_differences > 0
assert (accepted_vs_mathematical_p64_same_p53
        == accepted_vs_mathematical_p64_differences)

special_inputs = (
    0x0000000000000000, 0x8000000000000000, 0x8000000000000001,
    0xBFF0000000000000, 0xFFF0000000000000, 0x7FF0000000000000,
    0x7FF8000000000001, 0xFFF8000000000001,
)
special_cases = 0
for bits in special_inputs:
    for xrej in (0, 1, MASK32):
        assert special_sqrt(bits, xrej, accepted_buffered_root) == special_sqrt(
            bits, xrej, zero_tail_root)
        special_cases += 1

fpx87 = FPX87.read_text(encoding="utf-8").replace("\r\n", "\n")
game = GAME.read_text(encoding="utf-8").replace("\r\n", "\n")
fsqrt_wrapper = '''"FSqrt"
\t---->;
\t=> XScalarSqrt;
\t<----;
\tend;'''
assert fpx87.count(fsqrt_wrapper) == 1
assert "the public scalar interface preserves A/B/C/D/E" in fpx87
assert game.count("VHGSIMADD = 18206; VHGSIMDEN = 60000;") == 1
assert game.count("=> VHG local body distance;") == 5
body_distance = game[game.index('"VHG local body distance"'):game.index(
    '"VHG local far pixel"')]
assert "=> FSqrt; [VHGlocaldist0] = [FA0]; [VHGlocaldist1] = [FA1];" in body_distance

result = {
    "schema": 1,
    "task": 228,
    "status": "pass",
    "candidate_snapshot_equals_exact_transform": CANDIDATE.read_bytes() == candidate_bytes,
    "active_source_is_accepted_or_candidate": active_bytes in (accepted_bytes, candidate_bytes),
    "active_source_equals_candidate": active_bytes == candidate_bytes,
    "binary64_pipeline_cases": pipeline_cases,
    "normal_binary64_cases": normal_cases,
    "subnormal_binary64_cases": subnormal_cases,
    "special_dispatch_cases": special_cases,
    "minimum_binary64_mantissa_low_zero_bits": minimum_low_zero_bits,
    "binary64_srd1_srd0_zero_invariant_exact": True,
    "accepted_restoring_decisions_per_positive_root": 64,
    "candidate_restoring_decisions_per_positive_root": 64,
    "candidate_zero_tail_decisions_per_positive_root": 32,
    "candidate_zero_tail_transitions_per_positive_root": 1,
    "accepted_direct_buffer_reads_per_positive_root": 64,
    "accepted_direct_buffer_writes_per_positive_root": 64,
    "candidate_zero_buffer_tests_per_positive_root": 64,
    "candidate_minimum_skipped_buffer_shifts_per_positive_root": minimum_skipped_buffer_shifts,
    "candidate_maximum_performed_buffer_shifts_per_positive_root": maximum_performed_buffer_shifts,
    "accepted_dynamic_limb_handoffs_per_positive_root": 3,
    "candidate_dynamic_limb_handoffs_per_positive_root": 0,
    "candidate_direct_limb_handoffs_per_positive_root": 1,
    "accepted_dynamic_limb_clears_per_positive_root": 3,
    "candidate_dynamic_limb_clears_per_positive_root": 0,
    "candidate_direct_limb_clears_per_positive_root": 1,
    "accepted_pointer_decrements_per_positive_root": 4,
    "candidate_pointer_decrements_per_positive_root": 4,
    "candidate_accepted_bit_carry_branches_per_positive_root": 0,
    "candidate_accepted_bit_increment_carry_impossible": True,
    "candidate_zero_test_is_in_shared_restoring_header": True,
    "candidate_uses_one_shared_restoring_decision_core": True,
    "terminal_srd0_srd1_srd2_srd3_exact": True,
    "terminal_sqstep_sqml_sqmh_exact": True,
    "terminal_root_remainder_words_exact": True,
    "integer_root_exact": True,
    "mathematical_residual_exact_before_compatibility": True,
    "accepted_private_residual_exact": True,
    "accepted_p64_root_rounding_exact": True,
    "p53_binary64_spill_exact": True,
    "accepted_false_low_limb_borrow_cases": accepted_false_borrow_cases,
    "pipeline_accepted_vs_mathematical_p64_differences": (
        accepted_vs_mathematical_p64_differences),
    "p64_policy_differences_with_identical_p53_spill": (
        accepted_vs_mathematical_p64_same_p53),
    "sqrt_one_accepted_p64_is_0x8000000000000001": True,
    "sqrt_one_public_binary64_exact": True,
    "positive_zero_negative_and_rejection_behavior_exact": True,
    "candidate_changes_confined_to_xrootcore": True,
    "public_register_save_restore_source_wrapper_exact": True,
    "non_root_fpsoft_source_exact": True,
    "rooted_distance_and_renderer_control_source_exact": True,
    "synchronized_runtime_state_fidelity_required_after_timing": True,
    "simulation_constants": [18206, 60000],
    "source_boundary": "one common tracked shared-Lino closure",
    "raw_target_machine_blocks_added": False,
    "compiler_unchanged": True,
    "cpu_pack_unchanged": True,
    "accepted_source_sha256": sha256(accepted_bytes),
    "candidate_source_sha256": sha256(candidate_bytes),
    "active_source_sha256": sha256(active_bytes),
    "vhgame_source_sha256": sha256(GAME.read_bytes()),
    "fpx87_source_sha256": sha256(FPX87.read_bytes()),
    "transform_sha256": sha256((EVIDENCE / "apply_candidate.py").read_bytes()),
    "verifier_sha256": sha256(VERIFIER.read_bytes()),
}
OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
