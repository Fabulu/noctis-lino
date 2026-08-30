from pathlib import Path
import hashlib
import itertools
import json
import random
import runpy

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/gray-split-mul128-20260830"
ACCEPTED = EVIDENCE / "accepted/fpsoft.txt"
CANDIDATE = EVIDENCE / "candidate/fpsoft.txt"
SOURCE = ROOT / "work/fp/fpsoft.txt"
FPX87 = ROOT / "work/fp/fpx87.txt"
GAME = ROOT / "work/vhgame.txt"
OUTPUT = EVIDENCE / "model.json"
EXPECTED_ACCEPTED_SHA256 = (
    "063ecf40b0faab3b2779d8ff159b8fa815eec7b397de0d47e68223841e2a59cc")
EXPECTED_CANDIDATE_SHA256 = (
    "a2f22335d2473c10b3afe6e15c7aa0bf95380f71f8ab8267445747be6f01be61")
EXPECTED_FPX87_SHA256 = (
    "21060049f054523d64518c71ffb6da54caaea2912c3ec834f5d21112d19a6eb3")
EXPECTED_GAME_SHA256 = (
    "f1af20ebd55b80e3a1439b0e30f1bb4e0bdcc8e00b7aced1a7b34d7395d3dc25")
MASK16 = (1 << 16) - 1
MASK32 = (1 << 32) - 1
MASK64 = (1 << 64) - 1
MASK128 = (1 << 128) - 1
XBIAS = 16383

PRODUCT_PAIRS = (
    ("xa0", "xa1"),
    ("xb0", "xb1"),
    ("xc0", "xc1"),
    ("xd0", "xd1"),
)
HELPER_SCRATCH = (
    "xua", "xub", "xulo", "xuhi",
    "xul0", "xuh0", "xul1", "xuh1",
    "xup0", "xup1", "xup2", "xup3", "xumid", "xutmp",
)
MUL_SCRATCH = tuple(
    name for pair in PRODUCT_PAIRS for name in pair
) + ("xp0", "xp1", "xp2", "xp3", "xcy") + HELPER_SCRATCH
REGISTERS = ("A", "B", "C", "D", "E")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def add32(left, right):
    return (left + right) & MASK32


def mul32u_suffix(state):
    state["xup0"] = state["xul0"] * state["xul1"]
    state["xup1"] = state["xul0"] * state["xuh1"]
    state["xup2"] = state["xuh0"] * state["xul1"]
    state["xup3"] = state["xuh0"] * state["xuh1"]
    assert all(0 <= state[name] <= MASK32 for name in (
        "xup0", "xup1", "xup2", "xup3"))
    state["xutmp"] = state["xup0"] >> 16
    state["xutmp"] = add32(state["xup1"] & MASK16, state["xutmp"])
    state["xumid"] = add32(state["xup2"] & MASK16, state["xutmp"])
    state["xutmp"] = (state["xumid"] & MASK16) << 16
    state["xulo"] = (state["xup0"] & MASK16) | state["xutmp"]
    high = state["xup3"]
    high = add32(high, state["xup1"] >> 16)
    high = add32(high, state["xup2"] >> 16)
    state["B"] = state["xumid"] >> 16
    high = add32(high, state["B"])
    state["xuhi"] = high
    state["A"] = high


def mul32u_full(state):
    state["A"] = state["xua"] & MASK16
    state["xul0"] = state["A"]
    state["A"] = (state["xua"] >> 16) & MASK16
    state["xuh0"] = state["A"]
    state["A"] = state["xub"] & MASK16
    state["xul1"] = state["A"]
    state["A"] = (state["xub"] >> 16) & MASK16
    state["xuh1"] = state["A"]
    mul32u_suffix(state)


def carry_tail(state):
    state["A"] = state["xa0"]
    state["xp0"] = state["A"]

    state["B"] = state["xb0"]
    state["A"] = add32(state["xa1"], state["B"])
    state["E"] = int(state["A"] < state["B"])
    state["B"] = state["xc0"]
    state["A"] = add32(state["A"], state["B"])
    state["E"] += int(state["A"] < state["B"])
    state["xp1"] = state["A"]
    state["xcy"] = state["E"]

    state["B"] = state["xc1"]
    state["A"] = add32(state["xb1"], state["B"])
    state["D"] = int(state["A"] < state["B"])
    state["B"] = state["xd0"]
    state["A"] = add32(state["A"], state["B"])
    state["D"] += int(state["A"] < state["B"])
    state["B"] = state["xcy"]
    state["A"] = add32(state["A"], state["B"])
    state["D"] += int(state["A"] < state["B"])
    state["xp2"] = state["A"]

    state["A"] = add32(state["xd1"], state["D"])
    state["xp3"] = state["A"]


def mul128_accepted(state, xml, xmh, yml, ymh):
    for low, high, left, right in (
            ("xa0", "xa1", xml, yml),
            ("xb0", "xb1", xml, ymh),
            ("xc0", "xc1", xmh, yml),
            ("xd0", "xd1", xmh, ymh)):
        state["xua"] = left
        state["xub"] = right
        mul32u_full(state)
        state[low] = state["xulo"]
        state[high] = state["xuhi"]
    carry_tail(state)


def split_word(state, word, low, high):
    state["A"] = word & MASK16
    state[low] = state["A"]
    state["A"] = (word >> 16) & MASK16
    state[high] = state["A"]


def stage_pair(state, left, right):
    state["xul0"] = state[left[0]]
    state["xuh0"] = state[left[1]]
    state["xul1"] = state[right[0]]
    state["xuh1"] = state[right[1]]


def mul128_candidate(state, xml, xmh, yml, ymh):
    split_word(state, xml, "xa0", "xa1")
    split_word(state, ymh, "xb0", "xb1")
    split_word(state, yml, "xc0", "xc1")
    split_word(state, xmh, "xd0", "xd1")

    stage_pair(state, ("xa0", "xa1"), ("xb0", "xb1"))
    mul32u_suffix(state)
    state["xua"] = state["xulo"]
    state["xub"] = state["xuhi"]

    state["xul1"] = state["xc0"]
    state["xuh1"] = state["xc1"]
    mul32u_suffix(state)
    state["xa0"] = state["xulo"]
    state["xa1"] = state["xuhi"]

    state["xul0"] = state["xd0"]
    state["xuh0"] = state["xd1"]
    mul32u_suffix(state)
    state["xc0"] = state["xulo"]
    state["xc1"] = state["xuhi"]

    state["xul1"] = state["xb0"]
    state["xuh1"] = state["xb1"]
    mul32u_suffix(state)
    state["xd0"] = state["xulo"]
    state["xd1"] = state["xuhi"]

    state["xb0"] = state["xua"]
    state["xb1"] = state["xub"]
    state["xua"] = xmh
    state["xub"] = ymh
    carry_tail(state)


def symbolic_term(operation, *operands):
    return (operation,) + operands


def symbolic_suffix(state):
    state["xup0"] = symbolic_term("mul16", state["xul0"], state["xul1"])
    state["xup1"] = symbolic_term("mul16", state["xul0"], state["xuh1"])
    state["xup2"] = symbolic_term("mul16", state["xuh0"], state["xul1"])
    state["xup3"] = symbolic_term("mul16", state["xuh0"], state["xuh1"])
    state["xutmp"] = symbolic_term("shr16", state["xup0"])
    state["xutmp"] = symbolic_term(
        "add32", symbolic_term("lo16", state["xup1"]), state["xutmp"])
    state["xumid"] = symbolic_term(
        "add32", symbolic_term("lo16", state["xup2"]), state["xutmp"])
    state["xutmp"] = symbolic_term(
        "shl16", symbolic_term("lo16", state["xumid"]))
    state["xulo"] = symbolic_term(
        "or", symbolic_term("lo16", state["xup0"]), state["xutmp"])
    state["B"] = symbolic_term("shr16", state["xumid"])
    state["xuhi"] = symbolic_term(
        "add32", state["xup3"], symbolic_term("shr16", state["xup1"]),
        symbolic_term("shr16", state["xup2"]), state["B"])
    state["A"] = state["xuhi"]


def symbolic_full(state):
    state["xul0"] = symbolic_term("lo16", state["xua"])
    state["xuh0"] = symbolic_term("hi16", state["xua"])
    state["xul1"] = symbolic_term("lo16", state["xub"])
    state["xuh1"] = symbolic_term("hi16", state["xub"])
    symbolic_suffix(state)


def symbolic_tail(state):
    state["A"] = state["xa0"]
    state["xp0"] = state["A"]
    state["B"] = state["xb0"]
    state["A"] = symbolic_term("add32", state["xa1"], state["B"])
    state["E"] = symbolic_term("carry32", state["xa1"], state["B"])
    first = state["A"]
    state["B"] = state["xc0"]
    state["A"] = symbolic_term("add32", first, state["B"])
    state["E"] = symbolic_term(
        "add", state["E"], symbolic_term("carry32", first, state["B"]))
    state["xp1"] = state["A"]
    state["xcy"] = state["E"]
    state["B"] = state["xc1"]
    state["A"] = symbolic_term("add32", state["xb1"], state["B"])
    state["D"] = symbolic_term("carry32", state["xb1"], state["B"])
    first = state["A"]
    state["B"] = state["xd0"]
    state["A"] = symbolic_term("add32", first, state["B"])
    state["D"] = symbolic_term(
        "add", state["D"], symbolic_term("carry32", first, state["B"]))
    first = state["A"]
    state["B"] = state["xcy"]
    state["A"] = symbolic_term("add32", first, state["B"])
    state["D"] = symbolic_term(
        "add", state["D"], symbolic_term("carry32", first, state["B"]))
    state["xp2"] = state["A"]
    state["A"] = symbolic_term("add32", state["xd1"], state["D"])
    state["xp3"] = state["A"]


def symbolic_accepted(state, xml, xmh, yml, ymh):
    for low, high, left, right in (
            ("xa0", "xa1", xml, yml),
            ("xb0", "xb1", xml, ymh),
            ("xc0", "xc1", xmh, yml),
            ("xd0", "xd1", xmh, ymh)):
        state["xua"], state["xub"] = left, right
        symbolic_full(state)
        state[low], state[high] = state["xulo"], state["xuhi"]
    symbolic_tail(state)


def symbolic_candidate(state, xml, xmh, yml, ymh):
    state["xa0"] = symbolic_term("lo16", xml)
    state["xa1"] = symbolic_term("hi16", xml)
    state["xb0"] = symbolic_term("lo16", ymh)
    state["xb1"] = symbolic_term("hi16", ymh)
    state["xc0"] = symbolic_term("lo16", yml)
    state["xc1"] = symbolic_term("hi16", yml)
    state["xd0"] = symbolic_term("lo16", xmh)
    state["xd1"] = symbolic_term("hi16", xmh)
    stage_pair(state, ("xa0", "xa1"), ("xb0", "xb1"))
    symbolic_suffix(state)
    state["xua"], state["xub"] = state["xulo"], state["xuhi"]
    state["xul1"], state["xuh1"] = state["xc0"], state["xc1"]
    symbolic_suffix(state)
    state["xa0"], state["xa1"] = state["xulo"], state["xuhi"]
    state["xul0"], state["xuh0"] = state["xd0"], state["xd1"]
    symbolic_suffix(state)
    state["xc0"], state["xc1"] = state["xulo"], state["xuhi"]
    state["xul1"], state["xuh1"] = state["xb0"], state["xb1"]
    symbolic_suffix(state)
    state["xd0"], state["xd1"] = state["xulo"], state["xuhi"]
    state["xb0"], state["xb1"] = state["xua"], state["xub"]
    state["xua"], state["xub"] = xmh, ymh
    symbolic_tail(state)


def product_from_state(state):
    return sum(state[f"xp{index}"] << (32 * index) for index in range(4))


def round_p64_product(product):
    assert 1 << 126 <= product < 1 << 128
    if product >> 127:
        kept = product >> 64
        removed = product & MASK64
        halfway = 1 << 63
        exponent_delta = 1
    else:
        kept = product >> 63
        removed = product & ((1 << 63) - 1)
        halfway = 1 << 62
        exponent_delta = 0
    if removed > halfway or (removed == halfway and kept & 1):
        kept += 1
        if kept == 1 << 64:
            kept = 1 << 63
            exponent_delta += 1
    assert 1 << 63 <= kept < 1 << 64
    return kept, exponent_delta


def spill_p53(sign, exponent, mantissa, xrej):
    if exponent == 0:
        return sign << 63, xrej
    sticky = 0
    field = exponent - 15360
    if field <= 0:
        shift = 1 - field
        if shift > 53:
            return sign << 63, xrej + 1
        removed = mantissa & ((1 << shift) - 1)
        sticky = int(removed != 0)
        mantissa >>= shift
        field = 0
    retained = mantissa >> 11
    round_bit = (mantissa >> 10) & 1
    removed = (mantissa & 0x3FF) | sticky
    if round_bit and (removed or retained & 1):
        retained += 1
        if retained == 1 << 53:
            retained >>= 1
            field += 1
    if field < 0:
        return sign << 63, xrej + 1
    if field >= 0x7FF:
        return (sign << 63) | (0x7FF << 52), xrej + 1
    return ((sign << 63) | (field << 52)
            | (retained & ((1 << 52) - 1))), xrej


def pipeline(schedule, xml, xmh, yml, ymh, xs, ys, xe, ye, xrej, initial):
    state = dict(initial)
    if xe == 0 or ye == 0:
        return {
            "bits": (xs ^ ys) << 63,
            "xrej": xrej,
            "scratch": tuple(state[name] for name in MUL_SCRATCH),
            "zero_path": True,
        }
    schedule(state, xml, xmh, yml, ymh)
    product = product_from_state(state)
    mantissa, exponent_delta = round_p64_product(product)
    exponent = (xe + ye - XBIAS + exponent_delta) & MASK32
    sign = xs ^ ys
    bits, final_xrej = spill_p53(sign, exponent, mantissa, xrej)
    return {
        "bits": bits,
        "xrej": final_xrej,
        "mantissa": mantissa,
        "exponent": exponent,
        "sign": sign,
        "scratch": tuple(state[name] for name in MUL_SCRATCH),
        "registers": tuple(state[name] for name in REGISTERS),
        "zero_path": False,
    }


apply = runpy.run_path(str(EVIDENCE / "apply_candidate.py"))
transform = apply["transform"]
accepted_bytes = ACCEPTED.read_bytes()
candidate_bytes = CANDIDATE.read_bytes()
assert sha256(accepted_bytes) == EXPECTED_ACCEPTED_SHA256
assert sha256(candidate_bytes) == EXPECTED_CANDIDATE_SHA256
assert transform(accepted_bytes) == candidate_bytes
active_bytes = SOURCE.read_bytes()
assert active_bytes in (accepted_bytes, candidate_bytes)
assert sha256(FPX87.read_bytes()) == EXPECTED_FPX87_SHA256
assert sha256(GAME.read_bytes()) == EXPECTED_GAME_SHA256

accepted_text = accepted_bytes.decode("utf-8")
candidate_text = candidate_bytes.decode("utf-8")
assert accepted_text[:accepted_text.index('"programme"')] == candidate_text[
    :candidate_text.index('"programme"')]
assert accepted_text[accepted_text.index('"XMulCore"'):] == candidate_text[
    candidate_text.index('"XMulCore"'):]
assert candidate_text.count('"XMul32u split"') == 1
assert candidate_text.count("=> XMul32u split;") == 4
assert accepted_text.count("=> XMul32u;") == 4
accepted_helper = accepted_text[accepted_text.index('"XMul32u"'):
                                accepted_text.index('"Mul128"')]
candidate_helper = candidate_text[candidate_text.index('"XMul32u"'):
                                  candidate_text.index('"Mul128"')]
assert candidate_helper.replace('    "XMul32u split"\n', "") == accepted_helper
assert accepted_helper.count("A '*") == candidate_helper.count("A '*") == 4
accepted_mul = accepted_text[accepted_text.index('"Mul128"'):
                             accepted_text.index('"XMulCore"')]
candidate_mul = candidate_text[candidate_text.index('"Mul128"'):
                               candidate_text.index('"XMulCore"')]
accepted_tail = accepted_mul[accepted_mul.index("\tA = [xa0];") :]
candidate_tail = candidate_mul[candidate_mul.index("\tA = [xa0];") :]
assert accepted_tail == candidate_tail
assert candidate_mul.count("A '*") == 0
assert candidate_mul.count("=> XMul32u split;") == 4
assert candidate_mul.count("A & XM16;") == 8
assert candidate_mul.count("A > 16; A & XM16;") == 4
assert "[xb0] = [xua]; [xb1] = [xub];\n\t[xua] = [XMH]; [xub] = [YMH];" in candidate_mul
assert candidate_mul.index("[xb0] = [xua]") < candidate_mul.index("[xua] = [XMH]")
assert " C " not in candidate_mul[:candidate_mul.index("\tA = [xa0];")]
assert candidate_text.count("VHGSIMADD = 18206; VHGSIMDEN = 60000;") == 0
assert GAME.read_text(encoding="utf-8").count(
    "VHGSIMADD = 18206; VHGSIMDEN = 60000;") == 1

fpx87 = FPX87.read_text(encoding="utf-8")
assert "the public scalar interface preserves A/B/C/D/E" in fpx87
assert '"FMul"\n\t---->;\n\t=> XScalarMul;\n\t<----;' in fpx87
assert '"XScalarMul"' in candidate_text
assert "=> XMulCore;\n\t=> XToF64;" in candidate_text[
    candidate_text.index('"XScalarMul"'):candidate_text.index('"XScalarSqrt"')]

symbolic_initial = {
    name: symbolic_term("initial", name) for name in MUL_SCRATCH + REGISTERS
}
symbolic_inputs = tuple(symbolic_term("input", name) for name in (
    "XML", "XMH", "YML", "YMH"))
symbolic_left = dict(symbolic_initial)
symbolic_right = dict(symbolic_initial)
symbolic_accepted(symbolic_left, *symbolic_inputs)
symbolic_candidate(symbolic_right, *symbolic_inputs)
assert symbolic_left == symbolic_right
assert symbolic_left["C"] == symbolic_initial["C"]

rng = random.Random(0x229)
edge_words = (
    0, 1, 0xFFFF, 0x10000, 0x10001, 0x7FFFFFFF, 0x80000000,
    0xFFFFFFFE, 0xFFFFFFFF,
)
cases = list(itertools.product(edge_words, repeat=4))
cases.extend((
    (0x22221111, 0x44443333, 0x66665555, 0x88887777),
    (0xFFFF0000, 0x0000FFFF, 0xFFFF0001, 0x0001FFFF),
    (0xAAAAAAAA, 0x55555555, 0x13579BDF, 0x2468ACE0),
    (0x00010001, 0xFFFF0001, 0x0001FFFF, 0xFFFFFFFF),
))
for _ in range(65_536):
    cases.append(tuple(rng.randrange(1 << 32) for _ in range(4)))

concrete_cases = 0
carry_zero_cases = 0
carry_one_cases = 0
carry_two_cases = 0
for case_index, (xml, xmh, yml, ymh) in enumerate(cases):
    initial = {name: rng.randrange(1 << 32) for name in MUL_SCRATCH + REGISTERS}
    initial["C"] = (case_index * 0x9E3779B9) & MASK32
    accepted_state = dict(initial)
    candidate_state = dict(initial)
    mul128_accepted(accepted_state, xml, xmh, yml, ymh)
    mul128_candidate(candidate_state, xml, xmh, yml, ymh)
    assert accepted_state == candidate_state
    expected = (((xmh << 32) | xml) * ((ymh << 32) | yml)) & MASK128
    assert product_from_state(accepted_state) == expected
    partials = (
        xml * yml, xml * ymh, xmh * yml, xmh * ymh,
    )
    for (low, high), partial in zip(PRODUCT_PAIRS, partials):
        assert accepted_state[low] == partial & MASK32
        assert accepted_state[high] == partial >> 32
    final_helper = dict(initial)
    final_helper["xua"] = xmh
    final_helper["xub"] = ymh
    mul32u_full(final_helper)
    for name in HELPER_SCRATCH:
        assert accepted_state[name] == final_helper[name]
    assert accepted_state["C"] == initial["C"]
    assert accepted_state["A"] == accepted_state["xp3"]
    assert accepted_state["B"] == accepted_state["E"] == accepted_state["xcy"]
    carry_zero_cases += accepted_state["D"] == 0
    carry_one_cases += accepted_state["D"] == 1
    carry_two_cases += accepted_state["D"] == 2
    assert accepted_state["D"] <= 2
    concrete_cases += 1

assert carry_zero_cases and carry_one_cases and carry_two_cases

# Exercise the two XMulCore normalization paths and every nearest-even relation
# directly at their valid product boundaries, including p64 rollover.
round_products = []
for shift, base in ((64, 1 << 127), (63, 1 << 126)):
    halfway = 1 << (shift - 1)
    for kept in ((1 << 63), (1 << 63) | 1, (1 << 64) - 1):
        for removed in (halfway - 1, halfway, halfway + 1):
            product = (kept << shift) | removed
            if base <= product < (1 << 128):
                round_products.append(product)
round_results = [round_p64_product(product) for product in round_products]
assert any(product >> 127 for product in round_products)
assert any(not product >> 127 for product in round_products)
assert any(result == (1 << 63, 2) for result in round_results)

pipeline_vectors = (
    # normal shift-63/64 and both signs
    (0x00000000, 0x80000000, 0x00000000, 0x80000000, 0, 0, XBIAS, XBIAS),
    (0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 1, 0, XBIAS, XBIAS),
    (0x00000800, 0x80000000, 0xFFFFF800, 0x80000000, 1, 1, XBIAS, XBIAS),
    # p53 subnormal/underflow and overflow boundaries
    (0, 0x80000000, 0, 0x80000000, 0, 0, 15361, 15361),
    (MASK32, MASK32, MASK32, MASK32, 0, 0, 17406, 17406),
    # zero path must retain all multiply scratch
    (0x12345678, 0x80000000, 0x9ABCDEF0, 0x90000000, 1, 0, 0, XBIAS),
)
pipeline_cases = 0
for vector_index, vector in enumerate(pipeline_vectors):
    for xrej in (0, 1, MASK32):
        initial = {name: rng.randrange(1 << 32) for name in MUL_SCRATCH + REGISTERS}
        accepted_result = pipeline(
            mul128_accepted, *vector, xrej, initial)
        candidate_result = pipeline(
            mul128_candidate, *vector, xrej, initial)
        assert accepted_result == candidate_result
        if vector[6] == 0 or vector[7] == 0:
            assert accepted_result["zero_path"]
            assert accepted_result["scratch"] == tuple(
                initial[name] for name in MUL_SCRATCH)
        pipeline_cases += 1

for _ in range(16_384):
    xml = rng.randrange(1 << 32)
    xmh = (1 << 31) | rng.randrange(1 << 31)
    yml = rng.randrange(1 << 32)
    ymh = (1 << 31) | rng.randrange(1 << 31)
    xs, ys = rng.randrange(2), rng.randrange(2)
    xe, ye = rng.randrange(15361, 17407), rng.randrange(15361, 17407)
    xrej = rng.randrange(1 << 32)
    initial = {name: rng.randrange(1 << 32) for name in MUL_SCRATCH + REGISTERS}
    accepted_result = pipeline(
        mul128_accepted, xml, xmh, yml, ymh, xs, ys, xe, ye, xrej, initial)
    candidate_result = pipeline(
        mul128_candidate, xml, xmh, yml, ymh, xs, ys, xe, ye, xrej, initial)
    assert accepted_result == candidate_result
    pipeline_cases += 1

active_kind = "candidate" if active_bytes == candidate_bytes else "accepted"
result = {
    "schema": 1,
    "task": 229,
    "status": "pass",
    "candidate_snapshot_equals_exact_transform": True,
    "active_production": active_kind,
    "symbolic_all_input_schedule_equivalence": True,
    "symbolic_scope": (
        "accepted XMul32u suffix assumed; schedule aliases, canonical partials, "
        "carry-tail inputs, terminal helper scratch, and A-E proved identical"),
    "concrete_mul128_cases": concrete_cases,
    "pipeline_cases": pipeline_cases,
    "direct_unsigned_product_exact": True,
    "canonical_a_b_c_d_exact": True,
    "carry_tail_exact": True,
    "terminal_high_high_helper_scratch_exact": True,
    "source_terminal_a_through_e_exact": True,
    "incoming_c_preserved": True,
    "standalone_xmul32u_source_exact": True,
    "xmulcore_source_exact": True,
    "xscalarmul_and_public_fmul_source_exact": True,
    "p64_normalization_and_nearest_even_cases": len(round_products),
    "p53_normal_subnormal_overflow_and_zero_dispatch_covered": True,
    "accepted_source_decompositions_per_mul128": 8,
    "candidate_source_decompositions_per_mul128": 4,
    "accepted_extraction_alu_operations_per_mul128": 24,
    "candidate_extraction_alu_operations_per_mul128": 12,
    "accepted_unsigned_16x16_products_per_mul128": 16,
    "candidate_unsigned_16x16_products_per_mul128": 16,
    "candidate_suffix_calls_per_mul128": 4,
    "workspace_declarations_unchanged": True,
    "simulation_constants": [18206, 60000],
    "candidate_change_scope": "shared work/fp/fpsoft.txt Lino helper island only",
    "complete_shipping_dependency_closure_audited": False,
    "candidate_transform_raw_target_machine_blocks_added": False,
    "accepted_source_sha256": sha256(accepted_bytes),
    "candidate_source_sha256": sha256(candidate_bytes),
    "active_source_sha256": sha256(active_bytes),
    "vhgame_source_sha256": sha256(GAME.read_bytes()),
    "fpx87_source_sha256": sha256(FPX87.read_bytes()),
}
OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
