from pathlib import Path
from itertools import product
import hashlib
import importlib.util
import json

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/orbital-vector-cache-20260829"
ACCEPTED = EVIDENCE / "accepted/vhgame.txt"
CANDIDATE = ROOT / "work/vhgame.txt"
APPLIER = EVIDENCE / "apply_candidate.py"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def body_state(system, body, epoch):
    # Exact vector and terminal down-y raw words include signed zero,
    # infinities, and NaN payloads.
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
    return tuple(
        pool[(system * 7 + body * 3 + epoch * 5 + unit) % len(pool)]
        for unit in range(8)
    )


def relative(raw, camera):
    # Arithmetic itself remains the accepted shared-Lino helper. The model
    # records its exact ordered inputs rather than approximating binary64 math.
    return raw[:6], camera


def accepted_frame(system, count, selected, primaries, epoch, camera, rollover_at=None):
    events = []
    calls = 0
    # Selected origin remains an unchanged live call in both implementations.
    selected_origin = body_state(system, selected, epoch)
    for body in range(count):
        raw = body_state(system, body, epoch)
        calls += 1
        events.append(("resident", body, relative(raw, camera), raw[6:]))
    if selected not in primaries:
        for body in primaries:
            raw = body_state(system, body, epoch)
            calls += 1
            events.append(("primary", body, relative(raw, camera), raw[6:]))
    current_epoch = epoch
    for body in range(count):
        if body == selected:
            continue
        if rollover_at == body:
            current_epoch += 1
        raw = body_state(system, body, current_epoch)
        calls += 1
        events.append(("render", body, relative(raw, camera), raw[6:]))
    return selected_origin, tuple(events), calls, current_epoch


class ExactCache:
    def __init__(self):
        self.valid = False
        self.epoch = 0
        self.words = [None] * 640

    def invalidate(self):
        self.valid = False

    def frame(self, system, count, selected, primaries, epoch, camera, rollover_at=None):
        events = []
        calls = 0
        fill = not self.valid or epoch != self.epoch
        if fill:
            self.valid = False
        selected_origin = body_state(system, selected, epoch)
        for body in range(count):
            hit = self.valid and epoch == self.epoch and body < 80
            raw = tuple(self.words[body * 8:body * 8 + 8]) if hit else body_state(system, body, epoch)
            calls += not hit
            events.append(("resident", body, relative(raw, camera), raw[6:]))
            if fill:
                if body < 80:
                    start = body * 8
                    self.words[start:start + 8] = raw
                else:
                    fill = False
                    self.valid = False
        if fill:
            self.epoch = epoch
            self.valid = True
            fill = False
        if selected not in primaries:
            for body in primaries:
                hit = self.valid and epoch == self.epoch and body < 80
                raw = tuple(self.words[body * 8:body * 8 + 8]) if hit else body_state(system, body, epoch)
                calls += not hit
                events.append(("primary", body, relative(raw, camera), raw[6:]))
        current_epoch = epoch
        for body in range(count):
            if body == selected:
                continue
            if rollover_at == body:
                current_epoch += 1
            hit = self.valid and current_epoch == self.epoch and body < 80
            if self.valid and current_epoch != self.epoch:
                self.valid = False
                hit = False
            raw = tuple(self.words[body * 8:body * 8 + 8]) if hit else body_state(system, body, current_epoch)
            calls += not hit
            events.append(("render", body, relative(raw, camera), raw[6:]))
        return selected_origin, tuple(events), calls, current_epoch


spec = importlib.util.spec_from_file_location("vector_cache_applier", APPLIER)
applier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(applier)
accepted = ACCEPTED.read_bytes()
candidate = applier.transform(accepted)
if CANDIDATE.exists() and digest(CANDIDATE) != digest(ACCEPTED):
    assert CANDIDATE.read_bytes() == candidate

cases = 0
for count in range(1, 8):
    for selected in range(count):
        all_bodies = tuple(range(count))
        for primary_mask in range(1 << count):
            primaries = tuple(body for body in all_bodies if primary_mask & (1 << body))
            for epoch in (0, 1):
                cache = ExactCache()
                for camera_index in range(3):
                    camera = (camera_index, -camera_index, camera_index * 17)
                    expected = accepted_frame(0, count, selected, primaries, epoch, camera)
                    actual = cache.frame(0, count, selected, primaries, epoch, camera)
                    assert actual[:2] == expected[:2]
                    cases += 1
                # A same-frame second rollover must fail closed for that and
                # every following body.
                rollover = selected if selected + 1 == count else selected + 1
                camera = (99, -101, 0)
                expected = accepted_frame(
                    0, count, selected, primaries, epoch, camera, rollover
                )
                actual = cache.frame(
                    0, count, selected, primaries, epoch, camera, rollover
                )
                assert actual[:2] == expected[:2]
                cases += 1

# Local reset/start/checkpoint restoration invalidates same-second data from a
# prior generated system before it can be observed.
cache = ExactCache()
first = cache.frame(0, 7, 3, (0, 2, 4, 6), 5, (1, 2, 3))
cache.invalidate()
second = cache.frame(1, 7, 3, (0, 2, 4, 6), 5, (1, 2, 3))
assert first[:2] != second[:2]
assert second[:2] == accepted_frame(1, 7, 3, (0, 2, 4, 6), 5, (1, 2, 3))[:2]
# The 80-record boundary is exact; a defensive 81st body disables publication
# without writing beyond the common workspace.
cache = ExactCache()
assert cache.frame(0, 81, 3, tuple(range(0, 81, 7)), 9, (0, 0, 0))[:2] == accepted_frame(
    0, 81, 3, tuple(range(0, 81, 7)), 9, (0, 0, 0)
)[:2]
assert not cache.valid
assert 79 * 8 + 7 == 639

# Fixed checkpoint: first presentation computes the 78-record resident scan
# once, then both the primary rescan and later non-selected traversal replay it.
cache = ExactCache()
count = 78
selected = 3
primaries = tuple(range(0, count, 7))[:12]
cold = cache.frame(0, count, selected, primaries, 11, (0, 0, 0))
hot = cache.frame(0, count, selected, primaries, 11, (1, 0, -1))
accepted_cold = accepted_frame(0, count, selected, primaries, 11, (0, 0, 0))
accepted_hot = accepted_frame(0, count, selected, primaries, 11, (1, 0, -1))
assert cold[:2] == accepted_cold[:2]
assert hot[:2] == accepted_hot[:2]
assert accepted_cold[2] == 167
assert cold[2] == 78
assert hot[2] == 0
assert sum(accepted_frame(0, count, selected, primaries, 11, (0, 0, 0))[2] for _ in range(60)) == 10020
assert cold[2] + sum(
    cache.frame(0, count, selected, primaries, 11, (frame, 0, 0))[2]
    for frame in range(1, 60)
) == 78

text = candidate.decode("utf-8")
accepted_text = accepted.decode("utf-8")
render = text[text.index('"VHG local render"'):text.index('"VHG local render done"')]
resident = text[text.index('"VHG local resident scan"'):text.index('"VHG local ensure surface"')]
helper = text[text.index('"VHG local absolute body vector"'):text.index('"VHG local body relative"')]
assert text.count("VHGlocalvectorcache = 640;") == 1
assert text.count("A < 3; E = VHGlocalvectorcache; E + A;") == 2
assert text.count("=> VHG local absolute body vector;") == 3
assert text.count("=> VHGND absolute body vector;") == accepted_text.count(
    "=> VHGND absolute body vector;"
) - 2
assert render.count("[VHGlocalveccachefill] = 1;") == 1
assert resident.count("[E plus 0] = [VHGNDvecx0]") == 1
assert resident.count("[E plus 5] = [VHGNDvecz1]") == 1
assert resident.count("[E plus 6] = [VHGNDowny0]") == 1
assert resident.count("[E plus 7] = [VHGNDowny1]") == 1
assert resident.index("[E plus 7] = [VHGNDowny1]") < resident.index(
    "[VHGlocalveccachevalid] = 1;"
)
assert resident.count("? A < 80 -> VHG local resident vector store;") == 1
assert helper.count("[VHGNDvecx0] = [E plus 0]") == 1
assert helper.count("[VHGNDvecz1] = [E plus 5]") == 1
assert helper.count("[VHGNDowny0] = [E plus 6]") == 1
assert helper.count("[VHGNDowny1] = [E plus 7]") == 1
assert helper.count("[VHGlocalveccachevalid] = 0;") == 1
assert helper.count("=> VHGND absolute body vector;") == 1
assert text.count("[VHGlocalveccachevalid] = 0; [VHGlocalveccachefill] = 0;") == 3
# The selected origin remains an accepted live call before resident selection.
origin = render[:render.index("=> VHG local resident scan;")]
assert origin.count("=> VHGND absolute body vector;") == 1
assert origin.count("=> VHG local absolute body vector;") == 0
for token in (
    "=> SU fast srand;",
    "=> VHG local ring;",
    "=> VHG local far pixel;",
    "=> SP glow raster;",
    "=> SP globe raster;",
    "=> VHG local companion coronas;",
    "=> VHG local ensure surface;",
):
    assert text.count(token) == accepted_text.count(token)
assert "VHGSIMADD = 18206; VHGSIMDEN = 60000;" in text
assert digest(ROOT / "main/lib/gen/compiler114m.exe") == digest(
    EVIDENCE / "accepted/compiler114m.exe"
)
assert digest(ROOT / "main/cpu/i386m.bin") == digest(EVIDENCE / "accepted/i386m.bin")

result = {
    "schema": 1,
    "task": 210,
    "cases": cases,
    "raw_absolute_vector_words_replayed_exactly": True,
    "terminal_owner_relative_y_words_replayed_exactly": True,
    "signed_zero_nan_infinity_payloads_preserved": True,
    "moving_camera_relative_geometry_recomputed": True,
    "same_frame_epoch_rollover_fails_closed": True,
    "local_reset_start_restore_invalidate": True,
    "over_capacity_fails_closed": True,
    "workspace_units": 640,
    "maximum_cached_bodies": 80,
    "fixed_checkpoint_bodies": 78,
    "fixed_checkpoint_primary_rescan_bodies": 12,
    "fixed_checkpoint_nonselected_bodies": 77,
    "accepted_absolute_vector_calls_per_presentation": 167,
    "candidate_cold_absolute_vector_calls": 78,
    "candidate_hot_absolute_vector_calls": 0,
    "accepted_calls_per_stable_second_at_60_presentations": 10020,
    "candidate_calls_per_stable_second_at_60_presentations": 78,
    "selected_origin_call_unchanged": True,
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
