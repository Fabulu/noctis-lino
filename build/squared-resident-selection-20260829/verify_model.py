from pathlib import Path
from itertools import product
import hashlib
import importlib.util
import json
import math
import struct

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/squared-resident-selection-20260829"
ACCEPTED = EVIDENCE / "accepted/vhgame.txt"
CANDIDATE = ROOT / "work/vhgame.txt"
APPLIER = EVIDENCE / "apply_candidate.py"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bits(value):
    return struct.unpack("<Q", struct.pack("<d", value))[0]


def portable_root(squared):
    # The selected portable FSqrt rejects NaN and infinity to positive zero.
    if not math.isfinite(squared):
        return 0.0
    return math.sqrt(squared)


def rooted_scan(squared, owners):
    residents = []
    roots = 0
    for index, value in enumerate(squared):
        root = portable_root(value)
        roots += 1
        if not residents:
            residents.append((index, root))
        elif root < residents[0][1]:
            residents.insert(0, (index, root))
            residents = residents[:2]
        elif len(residents) == 1:
            residents.append((index, root))
        elif root < residents[1][1]:
            residents[1] = (index, root)
    if residents and owners[residents[0][0]] >= 0:
        primary = None
        for index, value in enumerate(squared):
            if owners[index] < 0:
                root = portable_root(value)
                roots += 1
                if primary is None or root < primary[1]:
                    primary = (index, root)
        residents = residents[:1] + ([] if primary is None else [primary])
    return tuple(index for index, _ in residents), roots


def hybrid_scan(squared, owners):
    residents = []
    roots = 0
    for index, value in enumerate(squared):
        final_body = index + 1 == len(squared)
        if not residents:
            residents.append((index, portable_root(value), value))
            roots += 1
            continue
        root = None
        special_or_final = not math.isfinite(value) or final_body
        if special_or_final or value < residents[0][2]:
            root = portable_root(value)
            roots += 1
            if root < residents[0][1]:
                residents.insert(0, (index, root, value))
                residents = residents[:2]
                continue
            if len(residents) == 1:
                residents.append((index, root, value))
                continue
            if root < residents[1][1]:
                residents[1] = (index, root, value)
            continue
        if len(residents) == 1:
            residents.append((index, portable_root(value), value))
            roots += 1
        elif value < residents[1][2]:
            root = portable_root(value)
            roots += 1
            if root < residents[1][1]:
                residents[1] = (index, root, value)
    if residents and owners[residents[0][0]] >= 0:
        primary = None
        for index, value in enumerate(squared):
            if owners[index] < 0:
                root = portable_root(value)
                roots += 1
                if primary is None or root < primary[1]:
                    primary = (index, root, value)
        residents = residents[:1] + ([] if primary is None else [primary])
    return tuple(index for index, *_ in residents), roots


spec = importlib.util.spec_from_file_location("resident_applier", APPLIER)
applier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(applier)
accepted = ACCEPTED.read_bytes()
candidate = applier.transform(accepted)
if CANDIDATE.exists() and digest(CANDIDATE) != digest(ACCEPTED):
    assert CANDIDATE.read_bytes() == candidate

next_one = math.nextafter(1.0, math.inf)
assert bits(math.sqrt(1.0)) == bits(math.sqrt(next_one))
values = (0.0, 1.0, next_one, 2.0, 3.0, math.inf, math.nan)
cases = 0
for length in range(6):
    for sequence in product(values, repeat=length):
        for owners in product((-1, 0), repeat=length):
            expected, _ = rooted_scan(sequence, owners)
            actual, _ = hybrid_scan(sequence, owners)
            assert actual == expected, (sequence, owners, expected, actual)
            cases += 1

# The square prefilter must retain the earlier body when distinct squares have
# the same rounded root, exactly matching the accepted rooted comparison.
collision = (next_one, 1.0, 3.0)
assert rooted_scan(collision, (-1, -1, -1))[0] == (0, 1)
assert hybrid_scan(collision, (-1, -1, -1))[0] == (0, 1)
# Equal values remain stable by generated index.
assert hybrid_scan((1.0, 1.0, 1.0, 1.0), (-1,) * 4)[0] == (0, 1)
# An increasing 78-body primary system roots only the first, second, and final
# candidates instead of all 78, while preserving the exact selected pair.
representative = tuple(float(index + 1) for index in range(78))
owners = (-1,) * 78
expected_pair, accepted_roots = rooted_scan(representative, owners)
actual_pair, candidate_roots = hybrid_scan(representative, owners)
assert actual_pair == expected_pair == (0, 1)
assert accepted_roots == 78
assert candidate_roots == 3

text = candidate.decode("utf-8")
accepted_text = accepted.decode("utf-8")
resident = text[text.index('"VHG local resident scan"'):text.index('"VHG local ensure surface"')]
primary = resident[resident.index('"VHG local resident primary body"'):]
squared_helper = text[text.index('"VHG local body distance squared"'):text.index('"VHG local body distance root"')]
root_helper = text[text.index('"VHG local body distance root"'):text.index('"VHG local body distance"', text.index('"VHG local body distance root"') + 1)]
public_helper = text[text.index('"VHG local body distance"', text.index('"VHG local body distance root"') + 1):text.index('"VHG local far pixel"')]
assert resident.count("=> VHG local body distance squared;") == 1
assert primary.count("=> VHG local body distance;") == 1
assert resident.count("=> VHG local body distance root;") == 3
assert resident.count("=> FSqrt;") == 0
assert squared_helper.count("=> PGF mul;") == 3
assert squared_helper.count("=> PGF add;") == 2
assert "FSqrt" not in squared_helper
assert "VHGlocaldist" not in squared_helper
assert root_helper.count("=> FSqrt;") == 1
assert root_helper.count("VHGlocaldist0") == 1
assert root_helper.count("VHGlocaldist1") == 1
assert public_helper.count("=> VHG local body distance squared;") == 1
assert public_helper.count("=> VHG local body distance root;") == 1
assert text.count("=> VHG local body distance;") == accepted_text.count("=> VHG local body distance;") - 1
assert text.count("=> VHG local body distance squared;") == 2
assert "A = [VHGlocalsqcand1]; A > 20; A & 7FFh; ? A = 7FFh -> VHG local resident compare first root;" in resident
assert "A = [VHGlocalbody]; A + 1; ? A = [nsnob] -> VHG local resident compare first root;" in resident
assert resident.count("A = [FI]; ? A >= 0 ->") == 5
assert primary.count("A = [FI]; ? A >= 0 ->") == 1
assert "VHGSIMADD = 18206; VHGSIMDEN = 60000;" in text
assert digest(ROOT / "main/lib/gen/compiler114m.exe") == digest(EVIDENCE / "accepted/compiler114m.exe")
assert digest(ROOT / "main/cpu/i386m.bin") == digest(EVIDENCE / "accepted/i386m.bin")

result = {
    "schema": 1,
    "task": 207,
    "cases": cases,
    "root_collision_preserved": True,
    "stable_ties_preserved": True,
    "nan_and_infinity_use_rooted_fallback": True,
    "final_full_scan_body_uses_rooted_path": True,
    "moon_primary_rescan_unchanged_and_rooted": True,
    "resident_indices_exact": True,
    "selected_distance_terminal_meaning_preserved": True,
    "representative_accepted_roots": accepted_roots,
    "representative_candidate_roots": candidate_roots,
    "source_boundary": "one common tracked shared-Lino closure",
    "simulation_constants": [18206, 60000],
    "accepted_source_sha256": digest(ACCEPTED),
    "candidate_source_sha256": hashlib.sha256(candidate).hexdigest(),
    "compiler_unchanged": True,
    "cpu_pack_unchanged": True,
    "status": "pass",
}
(EVIDENCE / "model.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
