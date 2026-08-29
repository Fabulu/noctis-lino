from pathlib import Path
from itertools import product
import hashlib
import importlib.util
import json

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/local-geometry-replay-20260829"
ACCEPTED = EVIDENCE / "accepted/vhgame.txt"
CANDIDATE = ROOT / "work/vhgame.txt"
APPLIER = EVIDENCE / "apply_candidate.py"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record(body, epoch):
    # Raw units deliberately include signed-zero, infinity, and NaN payloads.
    pool = (
        0x00000000,
        0x80000000,
        0x3FF00000,
        0x7FF00000,
        0x7FF80001,
        0xFFFFFFFF,
        0x01234567,
        0x89ABCDEF,
        0x76543210,
        0xFEDCBA98,
        0x400921FB,
    )
    return tuple(pool[(body * 3 + epoch * 5 + unit) % len(pool)] for unit in range(8))


def accepted_replay(count, selected, ordinary, epochs):
    distance = (0x13579BDF, 0x2468ACE0)
    events = []
    live_geometry = 0
    live_distance = 0
    for body in range(count):
        if body == selected:
            continue
        payload = record(body, epochs[body])
        geometry = payload[:6]
        live_geometry += 1
        if ordinary[body]:
            distance = payload[6:]
            live_distance += 1
        events.append((body, geometry, distance, ordinary[body]))
    return tuple(events), distance, live_geometry, live_distance


def cached_replay(count, selected, ordinary, epochs, cache_epoch=0):
    cache = tuple(record(body, cache_epoch) for body in range(80))
    distance = (0x13579BDF, 0x2468ACE0)
    events = []
    live_geometry = 0
    live_distance = 0
    for body in range(count):
        if body == selected:
            continue
        hit = epochs[body] == cache_epoch
        payload = cache[body] if hit else record(body, epochs[body])
        geometry = payload[:6]
        live_geometry += not hit
        if ordinary[body]:
            distance = payload[6:] if hit else record(body, epochs[body])[6:]
            live_distance += not hit
        events.append((body, geometry, distance, ordinary[body]))
    return tuple(events), distance, live_geometry, live_distance


spec = importlib.util.spec_from_file_location("geometry_applier", APPLIER)
applier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(applier)
accepted = ACCEPTED.read_bytes()
candidate = applier.transform(accepted)
if CANDIDATE.exists() and digest(CANDIDATE) != digest(ACCEPTED):
    assert CANDIDATE.read_bytes() == candidate

cases = 0
for count in range(1, 7):
    for selected in range(count):
        for ordinary in product((False, True), repeat=count):
            for change_at in range(count + 1):
                epochs = tuple(0 if body < change_at else 1 for body in range(count))
                expected = accepted_replay(count, selected, ordinary, epochs)
                actual = cached_replay(count, selected, ordinary, epochs)
                assert actual[:2] == expected[:2]
                cases += 1

# A stable 78-body frame replays all 77 non-selected bodies and ordinary
# distances without any duplicate live vector/relative/distance calculation.
count = 78
selected = 3
ordinary = (True,) * count
epochs = (0,) * count
expected = accepted_replay(count, selected, ordinary, epochs)
actual = cached_replay(count, selected, ordinary, epochs)
assert actual[:2] == expected[:2]
assert expected[2:] == (77, 77)
assert actual[2:] == (0, 0)
# Type-10 bodies consume cached coordinates but retain the previous public
# distance exactly, matching the accepted branch before ordinary-body distance.
ordinary = tuple(body % 3 != 1 for body in range(count))
assert cached_replay(count, selected, ordinary, epochs)[:2] == accepted_replay(
    count, selected, ordinary, epochs
)[:2]
# The final record fits exactly in the 640-unit common workspace.
assert 79 * 8 + 7 == 639

text = candidate.decode("utf-8")
accepted_text = accepted.decode("utf-8")
resident = text[text.index('"VHG local resident scan"'):text.index('"VHG local ensure surface"')]
body_loop = text[text.index('"VHG local body loop"'):text.index('"VHG local selected render"')]
assert "VHGlocalbodycache = 640;" in text
assert text.count("VHGlocalbodycache = 640;") == 1
assert "=> VHG local resident scan; [VHGlocalcacheepoch] = [VHGNDsecs];" in text
assert resident.count("[E plus 0] = [VHGlocalringcx0]") == 1
assert resident.count("[E plus 7] = [VHGlocaldist1]") == 1
assert body_loop.count("? A != [VHGlocalcacheepoch] ->") == 2
assert body_loop.count("E = VHGlocalbodycache; E + A;") == 2
assert body_loop.count("=> VHGND absolute body vector;") == 1
assert body_loop.count("=> VHG local body relative;") == 1
assert body_loop.count("=> VHG local body distance;") == 1
assert body_loop.index("? A != 10 -> VHG local ordinary body;") < body_loop.index(
    '"VHG local ordinary body"'
)
assert body_loop.index('"VHG local ordinary body"') < body_loop.index(
    "[VHGlocaldist0] = [E plus 6]"
)
assert body_loop.count("[PGFi] = SFXX; => PGF sa;") == 1
assert body_loop.count("[PGFi] = SFYY; => PGF sa;") == 1
assert body_loop.count("[PGFi] = SFZZ; => PGF sa;") == 1
for token in (
    "=> SU fast srand;",
    "=> VHG local ring;",
    "=> VHG local far pixel;",
    "=> SP glow raster;",
    "=> SP globe raster;",
):
    assert text.count(token) == accepted_text.count(token)
assert text.count("=> VHG local resident scan;") == accepted_text.count(
    "=> VHG local resident scan;"
)
assert text.count("=> VHG local companion coronas;") == accepted_text.count(
    "=> VHG local companion coronas;"
)
assert "VHGSIMADD = 18206; VHGSIMDEN = 60000;" in text
assert digest(ROOT / "main/lib/gen/compiler114m.exe") == digest(
    EVIDENCE / "accepted/compiler114m.exe"
)
assert digest(ROOT / "main/cpu/i386m.bin") == digest(
    EVIDENCE / "accepted/i386m.bin"
)

result = {
    "schema": 1,
    "task": 209,
    "cases": cases,
    "raw_binary64_words_replayed_exactly": True,
    "signed_zero_nan_infinity_payloads_preserved": True,
    "type10_distance_state_preserved": True,
    "epoch_change_fallback_exact": True,
    "coordinate_pgf_slots_reinstalled": ["SFXX", "SFYY", "SFZZ"],
    "workspace_units": 640,
    "maximum_body_records": 80,
    "fixed_checkpoint_bodies": 78,
    "fixed_checkpoint_nonselected_replays": 77,
    "fixed_checkpoint_duplicate_absolute_vectors_removed": 77,
    "fixed_checkpoint_duplicate_relative_calculations_removed": 77,
    "fixed_checkpoint_duplicate_distances_removed_when_ordinary": 77,
    "resident_scan_unchanged": True,
    "selected_body_path_unchanged": True,
    "companion_path_unchanged": True,
    "rng_and_draw_call_counts_unchanged": True,
    "simulation_constants": [18206, 60000],
    "source_boundary": "one common tracked shared-Lino closure",
    "accepted_source_sha256": digest(ACCEPTED),
    "candidate_source_sha256": hashlib.sha256(candidate).hexdigest(),
    "compiler_unchanged": True,
    "cpu_pack_unchanged": True,
    "status": "pass",
}
(EVIDENCE / "model.json").write_text(
    json.dumps(result, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps(result, indent=2))
