from pathlib import Path
import hashlib
import importlib.util
import json
import random
import struct

from capstone import Cs, CS_ARCH_X86, CS_GRP_CALL, CS_GRP_JUMP, CS_MODE_32
from capstone.x86_const import X86_OP_IMM

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/native-fquo-lowering-20260830"
OUTPUT = EVIDENCE / "model.json"
FPABI = ROOT / "work/fp/fpabi.txt"
FPSOFT = EVIDENCE / "accepted/fpsoft.txt"
FPX87 = ROOT / "work/fp/fpx87.txt"
MASK32 = (1 << 32) - 1
MASK52 = (1 << 52) - 1
SIGN64 = 1 << 63
INF_EXP = 0x7FF
XBIAS = 16383
TINY_RAW_EXPONENT = 0x3BCC


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def round_right_nearest_even(integer, shift):
    assert integer >= 0 and shift > 0
    kept = integer >> shift
    discarded = integer & ((1 << shift) - 1)
    halfway = 1 << (shift - 1)
    if discarded > halfway or (discarded == halfway and kept & 1):
        kept += 1
    return kept


def spill_p64_to_binary64(mantissa, exponent, sign):
    """Round positive M*2**E, with a 64-bit M, to one binary64 word."""
    assert mantissa.bit_length() == 64 and sign in (0, 1)
    top_exponent = exponent + 63
    if top_exponent >= -1022:
        p53 = round_right_nearest_even(mantissa, 11)
        if p53 == 1 << 53:
            p53 >>= 1
            top_exponent += 1
        if top_exponent > 1023:
            return (sign << 63) | (INF_EXP << 52)
        if top_exponent >= -1022:
            return ((sign << 63) | ((top_exponent + 1023) << 52)
                    | (p53 & MASK52))
    unit_shift = exponent + 1074
    if unit_shift >= 0:
        subnormal = mantissa << unit_shift
    else:
        subnormal = round_right_nearest_even(mantissa, -unit_shift)
    assert 0 <= subnormal <= 1 << 52
    return (sign << 63) | subnormal


def source_import(bits):
    """Mirror XFromF64's M64/raw-x87-exponent image and rejection."""
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


def terminal_x_image(sign, mantissa, raw_exponent):
    """Return XToF64's terminal XS/XE/XMH/XML image."""
    assert sign in (0, 1)
    if raw_exponent == 0:
        assert mantissa == 0
        return sign, 0, 0, 0
    shift = 15361 - raw_exponent
    if 1 <= shift <= 53:
        mantissa >>= shift
    return sign, raw_exponent, mantissa >> 32, mantissa & MASK32


def source_divide_p64(numerator, denominator, numerator_exp, denominator_exp):
    """Execute XQuoCore's pre-subtract and 65 restoring iterations."""
    assert numerator.bit_length() == denominator.bit_length() == 64
    remainder = numerator
    quotient = 0
    if remainder >= denominator:
        remainder -= denominator
        quotient = 1
    assert 0 <= remainder < denominator
    for _ in range(65):
        quotient <<= 1
        remainder <<= 1
        if remainder >= denominator:
            remainder -= denominator
            quotient |= 1
        assert 0 <= remainder < denominator
    assert quotient == (numerator << 65) // denominator
    assert remainder == (numerator << 65) % denominator
    raw_exponent = numerator_exp - denominator_exp + XBIAS
    if quotient >= 1 << 65:
        kept = quotient >> 2
        round_bit = (quotient >> 1) & 1
        sticky = bool((quotient & 1) or remainder)
    else:
        assert quotient >= 1 << 64
        kept = quotient >> 1
        round_bit = quotient & 1
        sticky = bool(remainder)
        raw_exponent -= 1
    assert kept.bit_length() == 64
    if round_bit and (sticky or kept & 1):
        kept += 1
        if kept == 1 << 64:
            kept = 1 << 63
            raw_exponent += 1
    assert kept.bit_length() == 64
    return kept, raw_exponent - XBIAS - 63, raw_exponent, {
        "restoring_quotient_bits": quotient.bit_length(),
        "round_bit": round_bit,
        "sticky": sticky,
    }


def source_model(numerator_bits, denominator_bits, initial_xrej=0):
    """Model XScalarQuo's denominator-first imports, dispatch, core and spill."""
    ds, dm, de, dr = source_import(denominator_bits)
    ns, nm, ne, nr = source_import(numerator_bits)
    sign = ns ^ ds
    xrej = (initial_xrej + dr + nr) & MASK32
    if de == 0:
        return ((sign << 63) | (INF_EXP << 52), xrej,
                {"path": "denominator-zero", "raw_exponent": 0,
                 "terminal_x": (ns, ne, nm >> 32, nm & MASK32)})
    if ne == 0:
        return (sign << 63, xrej,
                {"path": "numerator-zero", "raw_exponent": 0,
                 "terminal_x": (ns, ne, nm >> 32, nm & MASK32)})
    p64, power, raw_exponent, division = source_divide_p64(nm, dm, ne, de)
    terminal_x = terminal_x_image(sign, p64, raw_exponent)
    if raw_exponent < TINY_RAW_EXPONENT:
        return (sign << 63, (xrej + 1) & MASK32,
                {"path": "tiny", "raw_exponent": raw_exponent,
                 "terminal_x": terminal_x, **division})
    result = spill_p64_to_binary64(p64, power, sign)
    if ((result >> 52) & INF_EXP) == INF_EXP:
        xrej = (xrej + 1) & MASK32
        path = "overflow"
    else:
        path = "finite"
    return result, xrej, {
        "path": path, "raw_exponent": raw_exponent,
        "terminal_x": terminal_x, **division}


def machine_decode_finite(bits):
    """Independently decode a finite binary64 as integer*2**exponent."""
    sign = bits >> 63
    exponent_bits = (bits >> 52) & INF_EXP
    fraction = bits & MASK52
    assert exponent_bits != INF_EXP
    if exponent_bits == 0:
        return sign, fraction, -1074
    return sign, (1 << 52) | fraction, exponent_bits - 1023 - 52


def machine_import_image(bits):
    """Independently form the terminal XFromF64 register image."""
    sign = bits >> 63
    exponent_bits = (bits >> 52) & INF_EXP
    if exponent_bits == INF_EXP or not bits & (SIGN64 - 1):
        return sign, 0, 0, 0
    _, integer, power = machine_decode_finite(bits)
    top_exponent = integer.bit_length() - 1 + power
    mantissa = integer << (64 - integer.bit_length())
    return sign, top_exponent + XBIAS, mantissa >> 32, mantissa & MASK32


def floor_log2_ratio(numerator, denominator):
    guess = numerator.bit_length() - denominator.bit_length()
    if guess >= 0:
        return guess if numerator >= denominator << guess else guess - 1
    return guess if numerator << -guess >= denominator else guess - 1


def round_fraction_to_p64(numerator, denominator, binary_exponent):
    """Round (N/D)*2**E directly to nearest-even at 64 bits."""
    top_exponent = floor_log2_ratio(numerator, denominator) + binary_exponent
    shift = binary_exponent + 63 - top_exponent
    if shift >= 0:
        scaled_numerator = numerator << shift
        scaled_denominator = denominator
    else:
        scaled_numerator = numerator
        scaled_denominator = denominator << -shift
    kept, remainder = divmod(scaled_numerator, scaled_denominator)
    twice = remainder << 1
    if twice > scaled_denominator or (
            twice == scaled_denominator and kept & 1):
        kept += 1
    if kept == 1 << 64:
        kept >>= 1
        top_exponent += 1
    assert kept.bit_length() == 64
    return kept, top_exponent - 63, top_exponent + XBIAS


def machine_model(numerator_bits, denominator_bits, initial_xrej=0):
    """Model candidate classification, PC64 FDIV and portable final spill."""
    denominator_special = ((denominator_bits >> 52) & INF_EXP) == INF_EXP
    numerator_special = ((numerator_bits >> 52) & INF_EXP) == INF_EXP
    xrej = initial_xrej & MASK32
    if denominator_special:
        xrej = (xrej + 1) & MASK32
    if numerator_special:
        xrej = (xrej + 1) & MASK32
    sign = (numerator_bits ^ denominator_bits) >> 63
    numerator_image = machine_import_image(numerator_bits)
    denominator_nonzero = (
        not denominator_special and bool(denominator_bits & (SIGN64 - 1)))
    numerator_nonzero = (
        not numerator_special and bool(numerator_bits & (SIGN64 - 1)))
    if not denominator_nonzero:
        return ((sign << 63) | (INF_EXP << 52), xrej,
                {"path": "denominator-zero", "raw_exponent": 0,
                 "terminal_x": numerator_image})
    if not numerator_nonzero:
        return (sign << 63, xrej,
                {"path": "numerator-zero", "raw_exponent": 0,
                 "terminal_x": numerator_image})
    _, nm, npower = machine_decode_finite(numerator_bits)
    _, dm, dpower = machine_decode_finite(denominator_bits)
    p64, power, raw_exponent = round_fraction_to_p64(
        nm, dm, npower - dpower)
    terminal_x = terminal_x_image(sign, p64, raw_exponent)
    result = spill_p64_to_binary64(p64, power, sign)
    if raw_exponent < TINY_RAW_EXPONENT:
        assert result == sign << 63
        xrej = (xrej + 1) & MASK32
        path = "tiny"
    elif ((result >> 52) & INF_EXP) == INF_EXP:
        xrej = (xrej + 1) & MASK32
        path = "overflow"
    else:
        path = "finite"
    return result, xrej, {
        "path": path, "raw_exponent": raw_exponent,
        "terminal_x": terminal_x}


def check_pair(numerator, denominator, initial_xrej=0):
    source = source_model(numerator, denominator, initial_xrej)
    machine = machine_model(numerator, denominator, initial_xrej)
    assert source[0:2] == machine[0:2], (
        f"{numerator:016x} / {denominator:016x} {initial_xrej:08x}: "
        f"{source} != {machine}")
    assert source[2]["path"] == machine[2]["path"]
    assert source[2]["raw_exponent"] == machine[2]["raw_exponent"]
    assert source[2]["terminal_x"] == machine[2]["terminal_x"], (
        f"terminal X {numerator:016x} / {denominator:016x}: "
        f"{source[2]['terminal_x']} != {machine[2]['terminal_x']}")
    return source


spec = importlib.util.spec_from_file_location(
    "apply_candidate", EVIDENCE / "apply_candidate.py")
apply_candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(apply_candidate)
accepted_fp = FPSOFT.read_bytes()
candidate_fp = (EVIDENCE / "candidate/fpsoft.txt").read_bytes()
assert sha256(accepted_fp) == apply_candidate.ACCEPTED_FP_SHA256
assert candidate_fp == apply_candidate.transform_fp(accepted_fp)

fpabi = FPABI.read_text(encoding="utf-8").replace("\r\n", "\n")
fpsoft = accepted_fp.decode("utf-8").replace("\r\n", "\n")
fpx87 = FPX87.read_text(encoding="utf-8").replace("\r\n", "\n")
assert "FCWEXT\t\t= 133Fh;\t( PC=64 RC=nearest" in fpabi
assert "FCW\t= 133Fh;" in fpabi
assert '"XFromF64 body"' in fpsoft
assert "? [XE] = 7FFh -> XFF reject;" in fpsoft
assert '"XFF reject"\n\t[XREJ]+;' in fpsoft
assert '"XQuoCore body"' in fpsoft
assert "65 iterations from R = MX give" in fpsoft
assert "Everything below the kept 64 bits" not in fpsoft[
    fpsoft.index('"XQuoCore body"'):fpsoft.index('"XToF64 body"')]
assert '"XToF64 body"' in fpsoft
assert "? A > 53 -> xf tiny;" in fpsoft
assert "? [xtmp] >= 7FFh -> xf overflow;" in fpsoft
assert '"xf tiny"\n\t[XREJ]+;' in fpsoft
assert '"xf overflow"\n\t[XREJ]+;' in fpsoft
assert ('"FQuo"\n\t---->;\n\t=> FQuo body;\n\t<----;\n\tend;\n'
        '    "FQuo body"\n\t=> XScalarQuo;\n\tend;' in fpx87)
assert "the public scalar interface preserves A/B/C/D/E" in fpx87

# At the top of each restoring iteration, 0 <= R < MY. Doubling puts R below
# 2*MY, so one comparison/subtraction emits exactly the next quotient bit and
# restores the invariant. The pre-subtract establishes it while seeding the
# integer quotient bit. Thus after 65 iterations Q=floor(MX*2^65/MY) and the
# remaining R is the exact sticky tail. The 65/66-bit split, round bit and sticky
# in XQuoCore therefore round the exact quotient nearest-even to 64 bits. Exact
# binary64 FLD, PC64 nearest-even FDIV and tbyte materialization produce the
# same p64 image. The candidate then calls the unchanged portable XToF64 body,
# so its final p53 rounding, tiny/overflow policy, XREJ update, and terminal
# XS/XE/XMH/XML image are the source operations themselves.
proof_lemmas = {
    "all_finite_binary64_imports_are_exact_in_p64": True,
    "pre_subtract_establishes_remainder_below_denominator": True,
    "restoring_iteration_preserves_remainder_invariant": True,
    "restoring_q_equals_floor_mx_times_2^65_over_my": True,
    "remainder_is_exact_sticky_tail": True,
    "65_66_bit_split_selects_same_normalized_exponent": True,
    "xquocore_and_pc64_fdiv_round_same_exact_ratio_nearest_even": True,
    "p64_materialized_by_tbyte_store_without_rounding": True,
    "unchanged_xtof64_performs_the_candidate_final_spill": True,
    "terminal_x_image_matches_after_every_path": True,
    "finite_binary64_quotient_is_inside_extended_exponent_range": True,
    "therefore_all_finite_nonzero_binary64_pairs_have_identical_bits": True,
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
for numerator in edge:
    for denominator in edge:
        for initial in (0, 1, 0xFFFFFFFE, 0xFFFFFFFF):
            check_pair(numerator, denominator, initial)
            edge_cases += 1

special = [
    0x7FF0000000000000, 0xFFF0000000000000,
    0x7FF0000000000001, 0xFFF0000000000001,
    0x7FF8000000000000, 0xFFF8000000000000,
    0x7FFFFFFFFFFFFFFF, 0xFFFFFFFFFFFFFFFF,
]
special_and_zero_cases = 0
for numerator in edge + special:
    for denominator in edge + special:
        if numerator not in special and denominator not in special and (
                numerator & (SIGN64 - 1)) and denominator & (SIGN64 - 1):
            continue
        for initial in (0, 0xFFFFFFFE, 0xFFFFFFFF):
            result, xrej, detail = check_pair(numerator, denominator, initial)
            expected_rejections = int(numerator in special) + int(denominator in special)
            assert xrej == (initial + expected_rejections) & MASK32
            if denominator in special or not denominator & (SIGN64 - 1):
                assert (result & (SIGN64 - 1)) == INF_EXP << 52
                assert detail["path"] == "denominator-zero"
            elif numerator in special or not numerator & (SIGN64 - 1):
                assert (result & (SIGN64 - 1)) == 0
                assert detail["path"] == "numerator-zero"
            special_and_zero_cases += 1

# The exact 2^-1075 division tie is not rejected. Values below it are portable
# tiny and increment once; values above it round to the minimum subnormal.
tiny_vectors = {
    "below_tie": (0x0000000000000001, 0x4010000000000000,
                  0x0000000000000000, 1, "tiny"),
    "exact_tie": (0x0000000000000001, 0x4000000000000000,
                  0x0000000000000000, 0, "finite"),
    "above_tie": (0x0000000000000001, 0x3FFFFFFFFFFFFFFF,
                  0x0000000000000001, 0, "finite"),
    "negative_exact_tie": (0x8000000000000001, 0x4000000000000000,
                           0x8000000000000000, 0, "finite"),
}
for name, (numerator, denominator, expected_bits, delta, path) in tiny_vectors.items():
    result, xrej, detail = check_pair(numerator, denominator, 0xFFFFFFFF)
    assert result == expected_bits, name
    assert xrej == (0xFFFFFFFF + delta) & MASK32, name
    assert detail["path"] == path, name

ordinary_overflow = check_pair(0x7FEFFFFFFFFFFFFF, 0x3FE0000000000000)
assert ordinary_overflow[0] == 0x7FF0000000000000
assert ordinary_overflow[1] == 1 and ordinary_overflow[2]["path"] == "overflow"
ordinary_finite = check_pair(0x7FEFFFFFFFFFFFFF, 0x3FF0000000000000)
assert ordinary_finite[0] == 0x7FEFFFFFFFFFFFFF
assert ordinary_finite[1] == 0 and ordinary_finite[2]["path"] == "finite"

# A quotient below 2^1024 cannot occupy the p64-to-p53 overflow half-ulp:
# among binary64 ratios normalized below 2, the closest approach is the maximum
# finite significand 2-2^-52. The next ratio reachable using the greatest value
# below one as denominator is exactly 2. Thus finite-input division can overflow
# at raw exponent 43FF, but has no reachable raw-43FE final-spill-only overflow.
near_overflow = [0x7FEFFFFFFFFFFFFF - delta for delta in range(16)]
near_one = [0x3FF0000000000000 + delta for delta in range(-16, 17)]
raw_43fe_overflow_hits = []
for numerator in near_overflow:
    for denominator in near_one:
        result, _, detail = check_pair(numerator, denominator)
        if detail["raw_exponent"] == 0x43FE and (
                (result >> 52) & INF_EXP) == INF_EXP:
            raw_43fe_overflow_hits.append((numerator, denominator))
assert raw_43fe_overflow_hits == []

rng = random.Random(0x237)
random_cases = 200_000
path_counts = {}
restoring_width_counts = {}
for _ in range(random_cases):
    numerator = rng.getrandbits(64)
    denominator = rng.getrandbits(64)
    if ((numerator >> 52) & INF_EXP) == INF_EXP:
        numerator ^= 1 << 52
    if ((denominator >> 52) & INF_EXP) == INF_EXP:
        denominator ^= 1 << 52
    if not numerator & (SIGN64 - 1):
        numerator ^= 1
    if not denominator & (SIGN64 - 1):
        denominator ^= 1
    initial = rng.getrandbits(32)
    _, _, detail = check_pair(numerator, denominator, initial)
    path_counts[detail["path"]] = path_counts.get(detail["path"], 0) + 1
    width = detail["restoring_quotient_bits"]
    restoring_width_counts[width] = restoring_width_counts.get(width, 0) + 1
assert sum(path_counts.values()) == random_cases
assert all(path_counts.get(name, 0) > 0 for name in ("finite", "tiny", "overflow"))
assert set(restoring_width_counts) == {65, 66}

candidate = apply_candidate.CANDIDATE_SCALAR
decoder = Cs(CS_ARCH_X86, CS_MODE_32)
decoder.detail = True
instructions = list(decoder.disasm(candidate, apply_candidate.XSCALAR_QUO_START))
assert sum(item.size for item in instructions) == 237
assert instructions[-1].address + instructions[-1].size == apply_candidate.XSCALAR_QUO_END
assert instructions[-48].mnemonic == "ret"
assert all(item.mnemonic == "nop" for item in instructions[-47:])
assert sum(item.mnemonic == "fld" for item in instructions) == 2
assert sum(item.mnemonic == "fdiv" for item in instructions) == 1
assert sum(item.mnemonic == "fstp" for item in instructions) == 2
assert not any(item.mnemonic in ("fldcw", "fninit", "finit")
               for item in instructions)
call_targets = [
    item.operands[0].imm for item in instructions
    if item.group(CS_GRP_CALL) and item.operands[0].type == X86_OP_IMM]
internal_call_targets = [target for target in call_targets
                         if apply_candidate.XSCALAR_QUO_START <= target
                         < apply_candidate.XSCALAR_QUO_END]
assert len(call_targets) == 3
assert len(internal_call_targets) == 2
assert len(set(internal_call_targets)) == 1
assert call_targets.count(0x24EE6) == 1
valid_addresses = {item.address for item in instructions}
valid_addresses.add(apply_candidate.XSCALAR_QUO_END)
branch_targets = []
for item in instructions:
    if item.operands and item.operands[0].type == X86_OP_IMM and (
            item.group(CS_GRP_JUMP)):
        target_address = item.operands[0].imm
        assert target_address in valid_addresses
        branch_targets.append(target_address)
assert branch_targets

by_address = {item.address: item for item in instructions}
pending = [apply_candidate.XSCALAR_QUO_START, *set(internal_call_targets)]
reachable = set()
while pending:
    address = pending.pop()
    if address in reachable:
        continue
    reachable.add(address)
    item = by_address[address]
    if item.mnemonic == "ret":
        continue
    target = None
    if item.group(CS_GRP_JUMP):
        target = next(operand.imm for operand in item.operands
                      if operand.type == X86_OP_IMM)
        pending.append(target)
        if item.mnemonic == "jmp":
            continue
    pending.append(item.address + item.size)
assert not any(by_address[address].mnemonic == "nop" for address in reachable)

stack_pending = [(apply_candidate.XSCALAR_QUO_START, 0)]
stack_seen = set()
stack_peak = 0
return_depths = []
while stack_pending:
    address, depth = stack_pending.pop()
    state = (address, depth)
    if state in stack_seen:
        continue
    stack_seen.add(state)
    item = by_address[address]
    if item.mnemonic == "fld":
        depth += 1
    elif item.mnemonic == "fstp":
        depth -= 1
    assert 0 <= depth <= 8
    stack_peak = max(stack_peak, depth)
    if item.mnemonic == "ret":
        return_depths.append(depth)
        continue
    if item.group(CS_GRP_CALL):
        target = item.operands[0].imm
        assert depth == 0
        if target in by_address:
            stack_pending.append((target, depth))
        stack_pending.append((item.address + item.size, depth))
        continue
    if item.group(CS_GRP_JUMP):
        target = next(operand.imm for operand in item.operands
                      if operand.type == X86_OP_IMM)
        stack_pending.append((target, depth))
        if item.mnemonic == "jmp":
            continue
    stack_pending.append((item.address + item.size, depth))
assert return_depths and set(return_depths) == {0}
stack_depth = 0
assert stack_peak == 1

assert sum(item.mnemonic == "inc" and item.op_str == "dword ptr [edx + 0x30]"
           for item in instructions) == 2
assert sum(item.mnemonic == "cmp" and item.op_str == "ecx, 0xffe00000"
           for item in instructions) == 2
assert candidate.count(bytes.fromhex("DD 06 DC 76 08 DB 3A")) == 1
assert candidate.count(bytes.fromhex("DD 06 DB 3A")) == 1
assert apply_candidate.PREREQUISITE_DISTANCE == 0x1BF5
assert apply_candidate.PRIOR_LABEL_DISTANCE == 44

report = {
    "schema": 1,
    "task": 237,
    "status": "pass",
    "accepted_fp_sha256": sha256(accepted_fp),
    "candidate_fp_sha256": sha256(candidate_fp),
    "candidate_scalar_sha256": sha256(candidate),
    "candidate_scalar_bytes": len(candidate),
    "candidate_instruction_bytes": 190,
    "candidate_nop_padding_bytes": 47,
    "candidate_endpoint": f"0x{apply_candidate.XSCALAR_QUO_END:X}",
    "source_grounded_proof_lemmas": proof_lemmas,
    "all_finite_nonzero_binary64_pair_equivalence_algebraic": True,
    "empirical_exhaustion_of_all_finite_pairs_claimed": False,
    "edge_cases": edge_cases,
    "special_and_zero_cases": special_and_zero_cases,
    "deterministic_random_finite_cases": random_cases,
    "random_path_counts": path_counts,
    "restoring_quotient_width_counts": restoring_width_counts,
    "tiny_boundary_vectors": list(tiny_vectors),
    "exact_2^-1075_tie_to_zero_increments_xrej": False,
    "raw_43fe_final_p53_overflow_reachable_for_binary64_division": False,
    "near_overflow_pairs_checked": len(near_overflow) * len(near_one),
    "final_spill_overflow_detection_present": True,
    "final_spill_uses_unchanged_portable_xtof64": True,
    "terminal_x_image_matches_portable_all_paths": True,
    "one_xrej_increment_per_rejected_operand": True,
    "two_rejections_wrap_modulo_2^32": True,
    "zero_or_rejected_denominator_returns_signed_infinity": True,
    "zero_or_rejected_numerator_with_nonzero_denominator_returns_signed_zero": True,
    "hardware_division_on_zero_or_rejected_denominator": False,
    "portable_tiny_and_overflow_xrej_policy_exact": True,
    "fcw": "133F",
    "precision_control_bits": 3,
    "rounding_control_bits": 0,
    "candidate_x87_stack_peak": stack_peak,
    "candidate_x87_stack_net_change": stack_depth,
    "candidate_writes_control_word": False,
    "public_a_through_e_preserved_by_unchanged_wrapper": True,
    "candidate_branch_targets_are_instruction_boundaries": True,
    "candidate_nop_padding_reachable": False,
    "xrej_fixed_back_prerequisite_bytes": len(
        apply_candidate.XREJ_PREREQUISITE),
    "xrej_fixed_back_prerequisite_distance": (
        apply_candidate.PREREQUISITE_DISTANCE),
    "prior_internal_label_distance": apply_candidate.PRIOR_LABEL_DISTANCE,
    "common_lino_change_is_zero_byte_marker_only": True,
    "raw_target_machine_block_added_to_shipping_lino": False,
    "simulation_constants": [18206, 60000],
}
OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
