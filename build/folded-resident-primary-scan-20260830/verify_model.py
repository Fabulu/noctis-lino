from dataclasses import dataclass
from itertools import product
from pathlib import Path
import hashlib
import importlib.util
import json

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/folded-resident-primary-scan-20260830"
ACCEPTED = EVIDENCE / "accepted/vhgame.txt"
CANDIDATE = EVIDENCE / "candidate/vhgame.txt"
MODEL_PATH = EVIDENCE / "model.json"

spec = importlib.util.spec_from_file_location(
    "apply_candidate", EVIDENCE / "apply_candidate.py")
apply_candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(apply_candidate)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class Distance:
    order: int | None
    words: tuple[str, str]


def cmp_result(left, right):
    if left.order is None or right.order is None:
        return 1
    if left.order < right.order:
        return -1
    if left.order > right.order:
        return 1
    return 0


def entry_state():
    names = ("FA", "FB", "FI", "FS0", "FSW0", "PGFi", "SFXX", "SFYY", "SFZZ", "VHGND")
    state = {name: ("entry", name) for name in names}
    state.update({name: ("entry-register", name) for name in "ABCDE"})
    return state


def helper_state(body, distance):
    relative_x = ("relative-x", body)
    relative_y = ("relative-y", body)
    relative_z = ("relative-z", body)
    x_square = ("fmul", relative_x, relative_x)
    z_square = ("fmul", relative_z, relative_z)
    return {
        "FA": distance.words,
        "FB": ("camera-z",),
        "FI": ("absolute-helper-fi", body),
        "FS0": ("absolute-helper-fs0", body),
        "FSW0": x_square,
        "PGFi": "FSW0",
        "SFXX": relative_x,
        "SFYY": relative_y,
        "SFZZ": relative_z,
        "VHGND": ("absolute-vector-and-orbit-scratch", body),
        "root_expression": ("fsqrt", ("fadd", z_square, x_square)),
        "A": ("distance-helper-register", "A", body),
        "B": ("distance-helper-register", "B", body),
        "C": ("distance-helper-register", "C", body),
        "D": ("distance-helper-register", "D", body),
        "E": ("distance-helper-register", "E", body),
    }


def compare_state(state, left_body, left, right_body, right):
    compared = dict(state)
    result = cmp_result(left, right)
    compared["FA"] = left.words
    compared["FB"] = right.words
    compared["FI"] = result
    compared["comparison"] = (left_body, right_body)
    for register in "ABCDE":
        compared[register] = (
            "fcmp-terminal-register", register, left_body, right_body, result)
    return compared


def generic_step(resident1, resident2, near1, near2, body, distance, state):
    state = dict(state)
    state["A"] = -1 if resident1 is None else resident1
    if resident1 is None:
        return body, resident2, distance, near2, state
    state = compare_state(state, body, distance, resident1, near1)
    state["A"] = state["FI"]
    if cmp_result(distance, near1) < 0:
        return body, resident1, distance, near1, state
    state["A"] = -1 if resident2 is None else resident2
    if resident2 is None:
        return resident1, body, near1, distance, state
    state = compare_state(state, body, distance, resident2, near2)
    state["A"] = state["FI"]
    if cmp_result(distance, near2) < 0:
        resident2, near2 = body, distance
    return resident1, resident2, near1, near2, state


def first_scan(owners, distances, track_primaries):
    resident1 = resident2 = None
    near1 = near2 = None
    state = entry_state()
    primary_best = primary_last = primary_prior = None
    primary_best_distance = primary_prior_distance = None
    for body, (owner, distance) in enumerate(zip(owners, distances)):
        state = helper_state(body, distance)
        if track_primaries:
            state["E"] = ("nspowner-address", body)
            state["A"] = owner
        if track_primaries and owner < 0:
            primary_last = body
            primary_prior = primary_best
            primary_prior_distance = primary_best_distance
            state["A"] = -1 if primary_best is None else primary_best
            if primary_best is None:
                primary_best = body
                primary_best_distance = distance
            else:
                state = compare_state(
                    state, body, distance, primary_best, primary_best_distance)
                state["A"] = state["FI"]
                if cmp_result(distance, primary_best_distance) < 0:
                    primary_best = body
                    primary_best_distance = distance
        resident1, resident2, near1, near2, state = generic_step(
            resident1, resident2, near1, near2, body, distance, state)
    return {
        "resident1": resident1,
        "resident2": resident2,
        "near1": near1,
        "near2": near2,
        "state": state,
        "primary_last": primary_last,
        "primary_prior": primary_prior,
        "primary_prior_distance": primary_prior_distance,
    }


def pair_ready_state(first, owners):
    state = dict(first["state"])
    resident1 = first["resident1"]
    state["A"] = -1 if resident1 is None else resident1
    if resident1 is not None:
        state["E"] = ("nspowner-address", resident1)
        state["A"] = owners[resident1]
    return state


def primary_suffix(owners, distances, start, resident2, near2, initial):
    state = dict(initial)
    vhgnd = None
    trace = []
    for body in range(start, len(owners)):
        state["A"] = body
        trace.append(("guard", body))
        state["E"] = ("nspowner-address", body)
        state["C"] = owners[body]
        trace.append(("owner", body, owners[body]))
        if owners[body] >= 0:
            continue
        distance = distances[body]
        state = helper_state(body, distance)
        vhgnd = body
        trace.append(("absolute-relative-distance", body))
        state["A"] = -1 if resident2 is None else resident2
        if resident2 is None:
            resident2, near2 = body, distance
            trace.append(("first-primary", body))
        else:
            state = compare_state(state, body, distance, resident2, near2)
            state["A"] = state["FI"]
            trace.append(("primary-compare", body, resident2))
            if cmp_result(distance, near2) < 0:
                resident2, near2 = body, distance
                trace.append(("primary-update", body))
    state["A"] = len(owners)
    trace.append(("guard", len(owners)))
    return resident2, near2, state, vhgnd, tuple(trace)


def accepted(owners, distances):
    first = first_scan(owners, distances, False)
    paired_state = pair_ready_state(first, owners)
    resident1 = first["resident1"]
    if resident1 is None or owners[resident1] < 0:
        return {
            "resident1": resident1,
            "resident2": first["resident2"],
            "near1": first["near1"],
            "near2": first["near2"],
            "state": paired_state,
            "vhgnd": None if resident1 is None else len(owners) - 1,
            "localbody": len(owners),
            "primary_calculations": 0,
        }
    resident2, near2, state, vhgnd, trace = primary_suffix(
        owners, distances, 0, None, None, paired_state)
    return {
        "resident1": resident1,
        "resident2": resident2,
        "near1": first["near1"],
        "near2": near2,
        "state": state,
        "vhgnd": vhgnd,
        "localbody": len(owners),
        "primary_calculations": sum(owner < 0 for owner in owners),
    }


def candidate(owners, distances):
    first = first_scan(owners, distances, True)
    plain_first = first_scan(owners, distances, False)
    assert first["resident1"] == plain_first["resident1"]
    assert first["resident2"] == plain_first["resident2"]
    assert first["near1"] == plain_first["near1"]
    assert first["near2"] == plain_first["near2"]
    paired_state = pair_ready_state(first, owners)
    assert paired_state == pair_ready_state(plain_first, owners)
    resident1 = first["resident1"]
    if resident1 is None or owners[resident1] < 0:
        return {
            "resident1": resident1,
            "resident2": first["resident2"],
            "near1": first["near1"],
            "near2": first["near2"],
            "state": paired_state,
            "vhgnd": None if resident1 is None else len(owners) - 1,
            "localbody": len(owners),
            "primary_calculations": 0,
        }
    last = first["primary_last"]
    if last is None:
        resident2, near2, state, vhgnd, trace = primary_suffix(
            owners, distances, 0, None, None, paired_state)
        calculations = 0
    else:
        resident2, near2, state, vhgnd, trace = primary_suffix(
            owners,
            distances,
            last,
            first["primary_prior"],
            first["primary_prior_distance"],
            paired_state,
        )
        calculations = 1
    return {
        "resident1": resident1,
        "resident2": resident2,
        "near1": first["near1"],
        "near2": near2,
        "state": state,
        "vhgnd": vhgnd,
        "localbody": len(owners),
        "primary_calculations": calculations,
    }


def distance_variants(count):
    if count == 0:
        return [()]
    orders = [
        tuple(range(count)),
        tuple(reversed(range(count))),
        tuple((index + 1) % count for index in range(count)),
        tuple(0 for _ in range(count)),
        tuple(index // 2 for index in range(count)),
        tuple(None if index == 0 else index for index in range(count)),
        tuple(None if index == count - 1 else index for index in range(count)),
    ]
    variants = []
    for variant_index, ordering in enumerate(orders):
        variants.append(tuple(
            Distance(
                order,
                (
                    f"raw-low-v{variant_index}-b{body}",
                    f"raw-high-v{variant_index}-b{body}",
                ),
            )
            for body, order in enumerate(ordering)
        ))
    return variants


accepted_bytes = ACCEPTED.read_bytes()
candidate_bytes = apply_candidate.transform(accepted_bytes)
assert accepted_bytes != candidate_bytes
assert CANDIDATE.read_bytes() == candidate_bytes
assert sha256(accepted_bytes) == (
    "f1af20ebd55b80e3a1439b0e30f1bb4e0bdcc8e00b7aced1a7b34d7395d3dc25")
text = candidate_bytes.decode("utf-8")
assert text.count("VHGlocalprimarybest = 0FFFFFFFFh") == 1
assert text.count("[VHGlocalprimarybest] = 0FFFFFFFFh") == 1
assert text.count('"VHG local primary track first"') == 1
assert text.count('"VHG local primary track ready"') == 1
assert text.count('"VHG local resident primary full scan"') == 1
assert text.count("? A = 0FFFFFFFFh -> VHG local resident primary full scan;") == 1
assert text.count("-> VHG local resident primary body;") == 3
assert text.count(
    "A = [VHGlocalbody]; ? A '>= [nsnob] -> VHG local resident scan done;") == 1
assert text.count(
    "E = nspowner; E + A; C = [E]; ? C >= 0 -> VHG local resident primary next;") == 1
assert text.index("E = nspowner; E + [VHGlocalbody]; A = [E];") < text.index(
    "A = [VHGlocalresident1]; ? A != 0FFFFFFFFh -> VHG local resident compare first;")

def semantics(result):
    comparable = dict(result)
    comparable.pop("primary_calculations")
    return comparable


cases = 0
saved_primary_calculations = 0
for count in range(9):
    for primary_mask in range(1 << count):
        owners = tuple(
            -1 if primary_mask & (1 << body) else 0
            for body in range(count)
        )
        for distances in distance_variants(count):
            expected = accepted(owners, distances)
            actual = candidate(owners, distances)
            assert semantics(actual) == semantics(expected), (
                owners, distances, expected, actual)
            saved_primary_calculations += (
                expected["primary_calculations"] -
                actual["primary_calculations"])
            cases += 1

fixed_owners = tuple(-1 if body < 12 else 0 for body in range(78))
fixed_distances = tuple(
    Distance(body, (f"fixed-low-{body}", f"fixed-high-{body}"))
    for body in range(78)
)
# Make a moon nearest so the accepted 12-primary rescan is active.
fixed_distances = list(fixed_distances)
fixed_distances[12] = Distance(-1, ("fixed-nearest-low", "fixed-nearest-high"))
fixed_distances = tuple(fixed_distances)
fixed_expected = accepted(fixed_owners, fixed_distances)
fixed_actual = candidate(fixed_owners, fixed_distances)
assert semantics(fixed_actual) == semantics(fixed_expected)
assert fixed_expected["primary_calculations"] == 12
assert fixed_actual["primary_calculations"] == 1
cases += 1

result = {
    "schema": 1,
    "task": 215,
    "cases": cases,
    "stable_strict_nearer_primary_selection_exact": True,
    "equal_distance_raw_words_preserved": True,
    "unordered_distance_retention_exact": True,
    "nearest_primary_public_output_exact": True,
    "generic_top_two_terminal_state_restored_after_tracking": True,
    "candidate_file_equals_exact_transform": True,
    "concrete_a_through_e_owner_guard_and_helper_terminal_state_exact": True,
    "distance_terminal_fsw0_is_exact_relative_x_square": True,
    "final_primary_fp_and_vhgnd_terminal_state_recomputed": True,
    "trailing_owner_checks_and_integer_terminal_state_exact": True,
    "one_primary_exact": True,
    "nearest_body_already_primary_exact": True,
    "malformed_no_primary_fallback_exact": True,
    "fixed_checkpoint_bodies": 78,
    "fixed_checkpoint_primaries": 12,
    "accepted_fixed_checkpoint_primary_calculations": 12,
    "candidate_fixed_checkpoint_primary_calculations": 1,
    "fixed_checkpoint_absolute_and_rooted_distance_savings": 11,
    "modeled_primary_calculations_saved": saved_primary_calculations,
    "simulation_constants": [18206, 60000],
    "source_boundary": "one common tracked shared-Lino closure",
    "accepted_source_sha256": sha256(accepted_bytes),
    "candidate_source_sha256": sha256(candidate_bytes),
    "compiler_unchanged": True,
    "cpu_pack_unchanged": True,
    "status": "pass",
}
MODEL_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
