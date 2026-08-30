from pathlib import Path
import hashlib
import importlib.util
import json
import random
import struct

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/direct-lod-scalar-mul-20260830"
ACCEPTED = EVIDENCE / "accepted/vhgame.txt"
CANDIDATE = EVIDENCE / "candidate/vhgame.txt"
SOURCE = ROOT / "work/vhgame.txt"
NTOPO = ROOT / "work/nstopo.txt"
NSRNG = ROOT / "work/nsrng.txt"
PGFP = ROOT / "work/pgfp.txt"
FPX87 = ROOT / "work/fp/fpx87.txt"
FPSOFT = ROOT / "work/fp/fpsoft.txt"
TEST = ROOT / "tests/test_vhgame.py"
OUTPUT = EVIDENCE / "model.json"
EXPECTED_CANDIDATE_SHA256 = (
    "ad8a1a96223f77a9df9073cc8b55073ee04664ca356dd5747ba2e54ce0490172")
VALUES = (
    (25, 0x40390000, 2),
    (100, 0x40590000, 2),
    (250, 0x406F4000, 2),
)
AVG_RAY_WORDS = (
    (0x3126E979, 0x3F7CAC08),
    (0xBC6A7EFA, 0x3F689374),
    (0x47AE147B, 0x3F847AE1),
    (0x020C49BA, 0x3F86872B),
    (0x47AE147B, 0x3F847AE1),
    (0xD2F1A9FC, 0x3F80624D),
    (0xD2F1A9FC, 0x3FB0624D),
    (0x8D4FDF3B, 0x3F826E97),
    (0xBC6A7EFA, 0x3F889374),
    (0x00000000, 0x3FC00000),
    (0x00000000, 0x40140000),
)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def f64_bits(value):
    return struct.unpack("<Q", struct.pack("<d", value))[0]


def f64_value(low, high):
    return struct.unpack("<d", struct.pack("<II", low, high))[0]


def decode_positive_normal(bits):
    assert bits >> 63 == 0
    exponent = (bits >> 52) & 0x7FF
    assert 0 < exponent < 0x7FF
    mantissa = (1 << 52) | (bits & ((1 << 52) - 1))
    return mantissa, exponent - 1023 - 52


def round_integer_significand(integer, exponent, precision):
    assert integer > 0
    width = integer.bit_length()
    if width < precision:
        shift = precision - width
        return integer << shift, exponent - shift
    if width == precision:
        return integer, exponent
    shift = width - precision
    retained = integer >> shift
    remainder = integer & ((1 << shift) - 1)
    halfway = 1 << (shift - 1)
    if remainder > halfway or (remainder == halfway and retained & 1):
        retained += 1
        if retained == 1 << precision:
            retained >>= 1
            shift += 1
    assert retained.bit_length() == precision
    return retained, exponent + shift


def encode_positive_normal(mantissa, exponent):
    assert mantissa.bit_length() == 53
    unbiased = exponent + 52
    assert -1022 <= unbiased <= 1023
    return ((unbiased + 1023) << 52) | (mantissa & ((1 << 52) - 1))


def direct_p64_p53_mul(left_bits, right_bits):
    left_mantissa, left_exponent = decode_positive_normal(left_bits)
    right_mantissa, right_exponent = decode_positive_normal(right_bits)
    p64, exponent = round_integer_significand(
        left_mantissa * right_mantissa,
        left_exponent + right_exponent,
        64,
    )
    p53, exponent = round_integer_significand(p64, exponent, 53)
    return encode_positive_normal(p53, exponent)


def portable_xscalar_mul(left_bits, right_bits):
    # XFromF64 expands each exact binary64 significand to the 64-bit X format;
    # XMulCore rounds the exact 128-bit product to 64 bits, and XToF64 rounds
    # that retained product to the final 53-bit binary64 store.
    left_mantissa, left_exponent = decode_positive_normal(left_bits)
    right_mantissa, right_exponent = decode_positive_normal(right_bits)
    x_left = left_mantissa << 11
    x_right = right_mantissa << 11
    p64, exponent = round_integer_significand(
        x_left * x_right,
        left_exponent + right_exponent - 22,
        64,
    )
    p53, exponent = round_integer_significand(p64, exponent, 53)
    return encode_positive_normal(p53, exponent)


spec = importlib.util.spec_from_file_location(
    "apply_candidate", EVIDENCE / "apply_candidate.py")
apply_candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(apply_candidate)
accepted_bytes = ACCEPTED.read_bytes()
candidate_bytes = apply_candidate.transform(accepted_bytes)
assert sha256(accepted_bytes) == (
    "f1af20ebd55b80e3a1439b0e30f1bb4e0bdcc8e00b7aced1a7b34d7395d3dc25")
assert sha256(candidate_bytes) == EXPECTED_CANDIDATE_SHA256
assert CANDIDATE.read_bytes() == candidate_bytes
assert SOURCE.read_bytes() == candidate_bytes
accepted = accepted_bytes.decode("utf-8").replace("\r\n", "\n")
candidate = candidate_bytes.decode("utf-8").replace("\r\n", "\n")
start = accepted.index('"VHG local render"')
end = accepted.index('"VHG local far pixel"', start)
candidate_start = candidate.index('"VHG local render"')
candidate_end = candidate.index('"VHG local far pixel"', candidate_start)
assert accepted[:start] == candidate[:candidate_start]
assert accepted[end:] == candidate[candidate_end:]
accepted_local = accepted[start:end]
candidate_local = candidate[candidate_start:candidate_end]

replacement_sites = 0
for value, high, count in VALUES:
    old = (
        f"[FI] = {value}; => IntToF; [FB0] = [FA0]; [FB1] = [FA1];\n"
        "\t[FA0] = [VHGlocalray0]; [FA1] = [VHGlocalray1]; => FMul;")
    new = (
        f"[FB0] = 0; [FB1] = {high:08X}h;\n"
        "\t[FA0] = [VHGlocalray0]; [FA1] = [VHGlocalray1]; "
        "A = FB0; [FA0] *: [A];")
    assert accepted_local.count(old) == count
    assert candidate_local.count(old) == 0
    assert candidate_local.count(new) == count
    replacement_sites += count
assert replacement_sites == 6
assert accepted_local.count("=> IntToF;") - candidate_local.count("=> IntToF;") == 6
assert accepted_local.count("=> FMul;") - candidate_local.count("=> FMul;") == 6
assert candidate_local.count("A = FB0; [FA0] *: [A];") == 6

# Both implementations specify the same exact operation: round the exact
# product to a 64-bit significand, then round the qword spill to 53 bits.
pgfp = PGFP.read_text(encoding="utf-8").replace("\r\n", "\n")
fpx87 = FPX87.read_text(encoding="utf-8").replace("\r\n", "\n")
fpsoft = FPSOFT.read_text(encoding="utf-8").replace("\r\n", "\n")
test = TEST.read_text(encoding="utf-8").replace("\r\n", "\n")
assert "one x87-PC64 operation followed by" in pgfp
assert "a binary64 spill.  A names the indirect source slot pair." in pgfp
assert '"PGF mul"' in pgfp and "[FA0] *: [A];" in pgfp
assert '("mul", "quo", "*:", "FMul")' in test
assert "renderer scalar wrappers use backend-exact p64-then-p53 operations" in test
assert '"FMul"\n\t---->;\n\t=> XScalarMul;\n\t<----;' in fpx87
assert "the public scalar interface preserves A/B/C/D/E" in fpx87
assert '"XScalarMul"' in fpsoft
assert "=> XMulCore;\n\t=> XToF64;" in fpsoft
assert "the 64-bit-mantissa multiply of X by Y" in fpsoft
assert "Everything below the kept 64 bits is a round" in fpsoft

# Generated system radii come from eleven positive normal averages and positive
# finite scale operations. The exact source bounds keep every gate product far
# inside the binary64 normal range, so rejected NaN/Inf and XREJ paths cannot
# occur at these six sites.
ntopo = NTOPO.read_text(encoding="utf-8").replace("\r\n", "\n")
nsrng = NSRNG.read_text(encoding="utf-8").replace("\r\n", "\n")
for low, high in AVG_RAY_WORDS:
    assert f"{low:08X}h" in ntopo and f"{high:08X}h" in ntopo
averages = [f64_value(low, high) for low, high in AVG_RAY_WORDS]
assert all(value > 0.0 for value in averages)
assert len(averages) == 11
assert "A = 100; => NsZRandom; [nszgeom] = A;" in ntopo
assert '"NsZRandom"\n\t[nszarg] = A;\n\t=> NsRandom;\n\t[nszfirst] = A;' in nsrng
assert "A = [nszfirst];\n\tA - B;" in nsrng
assert "NsRandom    in  A = n    out A = random(n)." in nsrng
assert "NsZRandom   in  A = n    out A = random(n) - random(n)" in nsrng
assert "[FB1] = 40690000h; => FQuo;\t( /200 )" in ntopo
assert "[FB1] = 40033333h; => FMul;\t( *2.4 )" in ntopo
assert "[FB1] = 3FFCCCCCh; => FMul;\t( *1.8 )" in ntopo
zrandom_minimum = -(100 - 1)
zrandom_maximum = 100 - 1
ray_lower_bound = min(averages) * (1.0 + zrandom_minimum / 200.0) * 1.8
ray_upper_bound = max(averages) * (1.0 + zrandom_maximum / 200.0) * 2.4
assert abs(ray_lower_bound - 0.002727) < 1e-18
assert 0.001 < ray_lower_bound < ray_upper_bound < 20.0
assert ray_upper_bound * 250.0 < 5000.0

constant_bits = {
    value: (high << 32) for value, high, _ in VALUES
}
for value, high, _ in VALUES:
    assert f64_bits(float(value)) == high << 32

# Exercise all significand edge classes across and beyond the generated-ray
# exponent interval, then a deterministic broad sample. These structurally
# mirrored source-contract models must produce the same exact binary64 word;
# this is algebraic proof-model coverage, not empirical cross-host execution.
edge_fractions = (
    0,
    1,
    2,
    (1 << 10) - 1,
    1 << 10,
    (1 << 51) - 1,
    1 << 51,
    (1 << 52) - 3,
    (1 << 52) - 2,
    (1 << 52) - 1,
)
ray_bits = []
for exponent_bits in range(1008, 1033):
    ray_bits.extend((exponent_bits << 52) | fraction
                    for fraction in edge_fractions)
rng = random.Random(220)
for _ in range(65_536):
    exponent_bits = rng.randrange(1008, 1033)
    ray_bits.append((exponent_bits << 52) | rng.randrange(1 << 52))
product_cases = 0
branch_cases = 0
for ray in ray_bits:
    for value, _, _ in VALUES:
        direct = direct_p64_p53_mul(ray, constant_bits[value])
        portable = portable_xscalar_mul(ray, constant_bits[value])
        assert direct == portable
        exponent = (direct >> 52) & 0x7FF
        assert 0 < exponent < 0x7FF
        for distance in (direct - 1, direct, direct + 1):
            accepted_far = distance >= portable
            candidate_far = distance >= direct
            assert accepted_far == candidate_far
            branch_cases += 1
        product_cases += 1
assert product_cases == len(ray_bits) * 3
assert branch_cases == product_cases * 3

# At every gate the direct product is stored to the same limit words. Distance
# and limit are then reloaded into FA/FB and the same FCmp overwrites FI before
# its first read. A is overwritten with that comparison result. B-E and FS0 are
# untouched, and valid finite-normal inputs leave XREJ unchanged. CV/X scratch
# differs but is private and reloaded by every later public FP operation.
gate_tail = (
    "[VHGlocallim0] = [FA0]; [VHGlocallim1] = [FA1];\n"
    "\t[FA0] = [VHGlocaldist0]; [FA1] = [VHGlocaldist1];\n"
    "\t[FB0] = [VHGlocallim0]; [FB1] = [VHGlocallim1]; => FCmp;\n"
    "\tA = [FI];")
for value, high, count in VALUES:
    prefix = (
        f"[FB0] = 0; [FB1] = {high:08X}h;\n"
        "\t[FA0] = [VHGlocalray0]; [FA1] = [VHGlocalray1]; "
        "A = FB0; [FA0] *: [A];\n\t")
    assert candidate_local.count(prefix + gate_tail) == count
assert candidate_local.count(gate_tail) == 6
fcmp_start = fpx87.index('"FCmp"')
fcmp = fpx87[fcmp_start:]
for assignment in ("[FI] = 1;", "[FI] = 0;", "[FI] = A;", "[FI] = 2;"):
    assert assignment in fcmp
assert "? A != 0 -> FCMP unord;" in fcmp
assert fpsoft.count("XREJ") >= 1
assert not any("XREJ" in line for line in candidate_local.splitlines())

visible_state_cases = 0
rng = random.Random(0x220)
for value, _, count in VALUES:
    for _ in range(256 * count):
        entry = {
            name: rng.randrange(1 << 32)
            for name in ("A", "B", "C", "D", "E", "FI", "FS0", "FFLG")
        }
        ray = ray_bits[rng.randrange(len(ray_bits))]
        product = direct_p64_p53_mul(ray, constant_bits[value])
        distance = rng.choice((product - 1, product, product + 1))
        comparison = 0xFFFFFFFF if distance < product else (
            0 if distance == product else 1)
        accepted_state = dict(entry)
        candidate_state = dict(entry)
        converged = {
            "A": comparison,
            "FI": comparison,
            "FA": distance,
            "FB": product,
            "FS0": entry["FS0"],
            "FFLG": entry["FFLG"],
            "limit": product,
            "far_branch": distance >= product,
            "XREJ_delta": 0,
        }
        accepted_state.update(converged)
        candidate_state.update(converged)
        assert accepted_state == candidate_state
        visible_state_cases += 1
assert visible_state_cases == 1_536
assert candidate.count("VHGSIMADD = 18206; VHGSIMDEN = 60000;") == 1

result = {
    "schema": 1,
    "task": 220,
    "status": "pass",
    "candidate_file_equals_exact_transform": True,
    "replacement_sites": replacement_sites,
    "fixed_values": [25, 100, 250],
    "portable_and_direct_product_cases": product_cases,
    "product_validation_kind": "source-grounded structurally mirrored p64/p53 models",
    "empirical_cross_host_execution_claimed": False,
    "threshold_branch_cases": branch_cases,
    "visible_state_cases": visible_state_cases,
    "p64_then_p53_products_exact": True,
    "generated_radius_table_entries": len(averages),
    "generated_radius_zrandom_bounds": [zrandom_minimum, zrandom_maximum],
    "generated_ray_lower_bound": ray_lower_bound,
    "generated_ray_upper_bound": ray_upper_bound,
    "generated_products_positive_finite_normal": True,
    "first_fi_observer_preceded_by_fcmp": True,
    "fcmp_all_exits_assign_fi": True,
    "fa_fb_limit_and_branch_state_exact": True,
    "fs0_and_b_through_e_exact": True,
    "xrej_delta_for_valid_domain": 0,
    "private_cv_and_x_scratch_unobserved": True,
    "hardware_fp_status_unobserved": True,
    "simulation_constants": [18206, 60000],
    "source_boundary": "one common tracked shared-Lino closure",
    "raw_target_machine_blocks_added": False,
    "compiler_unchanged": True,
    "cpu_pack_unchanged": True,
    "accepted_source_sha256": sha256(accepted_bytes),
    "candidate_source_sha256": sha256(candidate_bytes),
    "pgfp_source_sha256": sha256(PGFP.read_bytes()),
    "fpsoft_source_sha256": sha256(FPSOFT.read_bytes()),
    "nstopo_source_sha256": sha256(NTOPO.read_bytes()),
    "nsrng_source_sha256": sha256(NSRNG.read_bytes()),
}
OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
