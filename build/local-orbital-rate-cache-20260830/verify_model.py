from pathlib import Path
import hashlib
import importlib.util
import json
import re

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/local-orbital-rate-cache-20260830"
ACCEPTED = EVIDENCE / "accepted/vhgame.txt"
CANDIDATE = EVIDENCE / "candidate/vhgame.txt"
SOURCE = ROOT / "work/vhgame.txt"
VHGROUND = ROOT / "work/vhground.txt"
MODEL_PATH = EVIDENCE / "model.json"

spec = importlib.util.spec_from_file_location(
    "apply_candidate", EVIDENCE / "apply_candidate.py")
apply_candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(apply_candidate)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def between(text, start, end):
    left = text.index(start) + len(start)
    right = text.index(end, left)
    return text[left:right]


def normalized_code(text):
    text = re.sub(r"\([^)]*\)", "", text, flags=re.DOTALL)
    return " ".join(text.split())


def static_record(index, owner, system):
    if owner < 0:
        mass_input = ("fload-f32", system["star_f32"])
        constant = ("raw-f64", "3E31FD9F", "0A01627EE")
    else:
        mass_input = system["rays"][owner]
        constant = ("raw-f64", "3F28284F", "1735C01D")
    mass2 = ("fmul", mass_input, mass_input)
    mass3 = ("fmul", mass2, mass_input)
    scaled_mass = ("fmul", mass3, constant)
    orbit = system["orbits"][index]
    orbit2 = ("fmul", orbit, orbit)
    root = ("fsqrt", ("fquo", scaled_mass, orbit2))
    return {
        "owner": owner,
        "mass": scaled_mass,
        "orbit": orbit,
        "root": root,
    }


def orbit_terminal(index, record, system, seconds, entry):
    angle = (
        "fquo",
        (
            "fmul",
            ("fmul", record["root"], seconds),
            ("raw-f64", "400921FB", "54442D18"),
        ),
        ("raw-f64", "40668000", "00000000"),
    )
    return {
        "FA": angle,
        "FB": ("raw-f64", "40668000", "00000000"),
        "FI": entry["FI"],
        "FS0": (
            system["star_f32"]
            if record["owner"] < 0
            else entry["FS0"]
        ),
        "FSW0": entry["FSW0"],
        "PGFi": entry["PGFi"],
        "A": index * 2,
        "B": entry["B"],
        "C": entry["C"],
        "D": entry["D"],
        "E": ("nsporbray", index * 2),
        "VHGNDvecowner": record["owner"],
        "VHGNDmass": record["mass"],
        "VHGNDorbit": record["orbit"],
        "VHGNDangle": angle,
    }


def original_orbit(index, owner, system, seconds, entry):
    return orbit_terminal(
        index, static_record(index, owner, system), system, seconds, entry)


def candidate_orbit(cache, index, owner, system, seconds, entry):
    if index < 0 or index >= 80:
        return original_orbit(index, owner, system, seconds, entry), "fallback"
    record = cache[index]
    if record is None:
        record = static_record(index, owner, system)
        # The source publishes valid only after every raw record field exists.
        cache[index] = record
        disposition = "miss"
    else:
        disposition = "hit"
    return orbit_terminal(index, record, system, seconds, entry), disposition


def body_result(index, orbit_state, system):
    # The complete post-orbit body-vector statement stream is source-identical.
    return {
        "vector": (
            "body-vector",
            index,
            orbit_state["VHGNDangle"],
            system["orbits"][index],
            system["tilts"][index],
            system["eccs"][index],
            system["orientations"][index],
        ),
        "terminal": ("identical-body-terminal", index, orbit_state),
    }


def original_body(index, owner, system, seconds, entry):
    return body_result(
        index, original_orbit(index, owner, system, seconds, entry), system)


def candidate_body(cache, index, owner, system, seconds, entry):
    orbit, disposition = candidate_orbit(
        cache, index, owner, system, seconds, entry)
    return body_result(index, orbit, system), disposition


def original_absolute(index, owners, system, seconds, entry):
    own = original_body(index, owners[index], system, seconds, entry)
    owner = owners[index]
    if owner < 0:
        return (own, None, index)
    parent = original_body(owner, owners[owner], system, seconds, entry)
    return (own, parent, owner)


def candidate_absolute(cache, index, owners, system, seconds, entry):
    if index < 0 or index >= 80:
        return original_absolute(index, owners, system, seconds, entry)
    own, _ = candidate_body(
        cache, index, owners[index], system, seconds, entry)
    owner = owners[index]
    if owner < 0:
        return (own, None, index)
    if owner >= 80:
        parent = original_body(owner, owners[owner], system, seconds, entry)
    else:
        parent, _ = candidate_body(
            cache, owner, owners[owner], system, seconds, entry)
    return (own, parent, owner)


def make_system(identity):
    indices = range(-3, 97)
    return {
        "star_f32": ("star-f32", identity),
        "rays": {index: ("ray", identity, index) for index in indices},
        "orbits": {index: ("orbit", identity, index) for index in indices},
        "tilts": {index: ("tilt", identity, index) for index in indices},
        "eccs": {index: ("ecc", identity, index) for index in indices},
        "orientations": {
            index: ("orientation", identity, index) for index in indices
        },
    }


accepted_bytes = ACCEPTED.read_bytes()
candidate_bytes = apply_candidate.transform(accepted_bytes)
assert sha256(accepted_bytes) == (
    "f1af20ebd55b80e3a1439b0e30f1bb4e0bdcc8e00b7aced1a7b34d7395d3dc25")
assert sha256(candidate_bytes) == (
    "9df0094c40c4e26179d2ff4ce9f17bf6d8015075f986e03d30989c932abcec32")
assert CANDIDATE.read_bytes() == candidate_bytes
assert SOURCE.read_bytes() == candidate_bytes
accepted_text = accepted_bytes.decode("utf-8").replace("\r\n", "\n")
candidate_text = candidate_bytes.decode("utf-8").replace("\r\n", "\n")
vhground_text = VHGROUND.read_text(encoding="utf-8").replace("\r\n", "\n")

# The full time-dependent body-vector suffix is copied statement-for-statement.
original_body_code = "=> VHGND orbit angle;" + between(
    vhground_text, "=> VHGND orbit angle;", '"VHGND absolute body vector"')
candidate_body_code = "=> VHG local orbit angle;" + between(
    candidate_text,
    "=> VHG local orbit angle;",
    '"VHG local absolute body vector"',
)
candidate_body_code = candidate_body_code.replace(
    "=> VHG local orbit angle;", "=> VHGND orbit angle;")
assert normalized_code(candidate_body_code) == normalized_code(original_body_code)

# The cold static prefix keeps every source operation and grouping exactly.
original_static = "\tE = nspowner; E + [VHGNDvecindex];" + between(
    vhground_text,
    "\tE = nspowner; E + [VHGNDvecindex];",
    "\t[FB0] = [SUsec0];",
)
candidate_static = "\tE = nspowner; E + [VHGNDvecindex];" + between(
    candidate_text,
    "\tE = nspowner; E + [VHGNDvecindex];",
    "\tA = [VHGNDvecindex]; A '* 8; E = VHGlocalorbitcache; E + A;",
)
for local, original in (
    ("VHG local orbit body mass", "VHGND orbit body mass"),
    ("VHG local orbit radius mass", "VHGND orbit radius mass"),
    ("VHG local orbit body constant", "VHGND orbit body constant"),
    ("VHG local orbit mass ready", "VHGND orbit mass ready"),
):
    candidate_static = candidate_static.replace(local, original)
assert normalized_code(candidate_static) == normalized_code(original_static)

original_orbit_code = between(
    vhground_text, '"VHGND orbit angle"', '"VHGND body vector"')
original_dynamic = "\t[FB0] = [SUsec0];" + between(
    original_orbit_code,
    "\t[FB0] = [SUsec0];",
    "\n\tend;",
)
local_orbit_code = between(
    candidate_text, '"VHG local orbit angle"', '"VHG local body vector"')
candidate_dynamic = "\t[FB0] = [SUsec0];" + between(
    local_orbit_code,
    "\t[FB0] = [SUsec0];",
    '\n\tend;\n    "VHG local orbit angle original"',
)
assert normalized_code(candidate_dynamic) == normalized_code(original_dynamic)

assert candidate_text.count("=> VHG local absolute body vector;") == 6
assert candidate_text.count("=> VHGND absolute body vector;") == 3
assert accepted_text.count("=> VHGND absolute body vector;") == 8
assert candidate_text.count("=> VHG local orbit cache clear;") == 2
assert candidate_text.count("VHGlocalorbitcache = 640;") == 1
assert candidate_text.count("[E plus 6] = [FA0]; [E plus 7] = [FA1]; [E] = 1;") == 1
assert candidate_text.count("E = VHGlocalorbitcache; E + A; [E] = 0;") == 1
assert candidate_text.count("=> NsResetAll; => NsPrepare;") == 1
assert candidate_text.index("=> VHG local orbit cache clear;") < candidate_text.index(
    "[VHGNDvecindex] = [VHGplanet]; => VHG local absolute body vector;")
restore_start = candidate_text.index('"VHG restore local checkpoint"')
restore_end = candidate_text.index('"VHG restore local inactive"', restore_start)
restore_code = candidate_text[restore_start:restore_end]
assert restore_code.index("=> VHG local orbit cache clear;") < restore_code.index(
    "A = [VHGlocalactive]")

# The entire tail containing both non-local calls remains byte-identical.
non_local_tail = '"VHG info environment geometry"'
assert candidate_text[candidate_text.index(non_local_tail):] == accepted_text[
    accepted_text.index(non_local_tail):]

systems = [make_system(identity) for identity in range(3)]
entry_variants = [
    {
        "FI": ("entry-fi", variant),
        "FS0": ("entry-fs0", variant),
        "FSW0": ("entry-fsw0", variant),
        "PGFi": ("entry-pgfi", variant),
        "B": ("entry-b", variant),
        "C": ("entry-c", variant),
        "D": ("entry-d", variant),
    }
    for variant in range(3)
]
owner_variants = (-1, 0, 1, 79, 80)
cases = 0
hits = 0
misses = 0
fallbacks = 0

for system_id, system in enumerate(systems):
    owners = {index: -1 for index in range(-3, 97)}
    for index in range(-2, 83):
        for owner in owner_variants:
            owners[index] = owner
            if owner >= 0:
                owners[owner] = -1
            for entry in entry_variants:
                seconds0 = ("seconds", system_id, index, owner, 0)
                seconds1 = ("seconds", system_id, index, owner, 1)
                cache = [None] * 80
                expected0 = original_orbit(
                    index, owner, system, seconds0, entry)
                actual0, disposition0 = candidate_orbit(
                    cache, index, owner, system, seconds0, entry)
                assert actual0 == expected0
                expected1 = original_orbit(
                    index, owner, system, seconds1, entry)
                actual1, disposition1 = candidate_orbit(
                    cache, index, owner, system, seconds1, entry)
                assert actual1 == expected1
                assert expected0["FSW0"] == entry["FSW0"]
                assert expected0["PGFi"] == entry["PGFi"]
                assert expected0["FI"] == entry["FI"]
                if owner < 0:
                    assert expected0["FS0"] == system["star_f32"]
                else:
                    assert expected0["FS0"] == entry["FS0"]
                if 0 <= index < 80:
                    assert disposition0 == "miss"
                    assert disposition1 == "hit"
                    misses += 1
                    hits += 1
                else:
                    assert disposition0 == "fallback"
                    assert disposition1 == "fallback"
                    fallbacks += 2
                assert candidate_absolute(
                    [None] * 80,
                    index,
                    owners,
                    system,
                    seconds0,
                    entry,
                ) == original_absolute(
                    index, owners, system, seconds0, entry)
                cases += 1

# A clear between generated systems makes every formerly valid record miss.
invalidation_cases = 0
for index in range(80):
    cache = [None] * 80
    entry = entry_variants[index % len(entry_variants)]
    first, first_disposition = candidate_orbit(
        cache, index, -1, systems[0], ("seconds", "old"), entry)
    assert first_disposition == "miss"
    cache = [None] * 80
    second, second_disposition = candidate_orbit(
        cache, index, 0, systems[1], ("seconds", "new"), entry)
    assert second_disposition == "miss"
    assert second == original_orbit(
        index, 0, systems[1], ("seconds", "new"), entry)
    invalidation_cases += 1

result = {
    "schema": 1,
    "task": 216,
    "status": "pass",
    "cases": cases,
    "invalidation_cases": invalidation_cases,
    "cache_hits_modeled": hits,
    "cache_misses_modeled": misses,
    "fallbacks_modeled": fallbacks,
    "candidate_file_equals_exact_transform": True,
    "body_vector_suffix_statement_exact": True,
    "cold_static_prefix_statement_and_grouping_exact": True,
    "dynamic_seconds_suffix_statement_and_grouping_exact": True,
    "raw_owner_mass_orbit_root_replay_exact": True,
    "primary_fs0_and_moon_fs0_behavior_exact": True,
    "fa_fb_fi_fsw0_pgfi_terminal_state_exact": True,
    "a_through_e_terminal_state_exact": True,
    "vhgnd_vector_and_orbit_scratch_exact": True,
    "moon_owner_in_range_uses_exact_cached_body_vector": True,
    "out_of_range_body_and_owner_fallback_exact": True,
    "valid_published_last": True,
    "local_start_and_checkpoint_restore_clear_before_use": True,
    "only_generated_system_replacement_site_identified": True,
    "cache_words": 640,
    "record_words": 8,
    "records": 80,
    "highest_used_word": 639,
    "local_absolute_call_sites_replaced": 6,
    "non_local_absolute_call_sites_unchanged": 2,
    "simulation_constants": [18206, 60000],
    "source_boundary": "one common tracked shared-Lino closure",
    "raw_target_machine_blocks_added": False,
    "compiler_unchanged": True,
    "cpu_pack_unchanged": True,
    "accepted_source_sha256": sha256(accepted_bytes),
    "candidate_source_sha256": sha256(candidate_bytes),
    "vhground_source_sha256": sha256(VHGROUND.read_bytes()),
}
MODEL_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
