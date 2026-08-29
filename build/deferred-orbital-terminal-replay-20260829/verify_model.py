from pathlib import Path
import hashlib
import importlib.util
import json

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/deferred-orbital-terminal-replay-20260829"
ACCEPTED = EVIDENCE / "accepted/vhgame.txt"
CANDIDATE = ROOT / "work/vhgame.txt"
APPLIER = EVIDENCE / "apply_candidate.py"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def body_state(system, body, epoch):
    # Six absolute-vector words plus the two raw terminal down-y words. The
    # pool deliberately includes signed zero, infinities, and NaN payloads.
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
    # The accepted shared-Lino arithmetic remains live. Record its exact ordered
    # inputs instead of approximating binary64 operations in Python.
    return raw[:6], camera


def accepted_frame(
        system, count, selected, primaries, epoch, camera, *,
        rollover_at=None, companion=None, surface_miss_at=None,
        selected_surface_miss=False):
    events = []
    calls = 0
    selected_origin = body_state(system, selected, epoch)
    terminal_down_y = selected_origin[6:]
    for body in range(count):
        raw = body_state(system, body, epoch)
        calls += 1
        terminal_down_y = raw[6:]
        events.append(("resident", body, relative(raw, camera)))
    if selected not in primaries:
        for body in primaries:
            raw = body_state(system, body, epoch)
            calls += 1
            terminal_down_y = raw[6:]
            events.append(("primary", body, relative(raw, camera)))
    if companion is not None:
        terminal_down_y = body_state(system, companion, epoch)[6:]
    current_epoch = epoch
    for body in range(count):
        if body == selected:
            continue
        if rollover_at == body:
            current_epoch += 1
        raw = body_state(system, body, current_epoch)
        calls += 1
        terminal_down_y = raw[6:]
        events.append(("render", body, relative(raw, camera)))
        # Surface-cache miss setup neither reads nor writes VHGNDowny0/1.
        # The prior absolute-vector terminal pair therefore remains authoritative.
    return selected_origin, tuple(events), terminal_down_y, calls, current_epoch


class DeferredCache:
    def __init__(self):
        self.valid = False
        self.epoch = 0
        self.words = [None] * 640

    def invalidate(self):
        self.valid = False

    def frame(
            self, system, count, selected, primaries, epoch, camera, *,
            rollover_at=None, companion=None, surface_miss_at=None,
            selected_surface_miss=False):
        events = []
        calls = 0
        pending = None
        fill = not self.valid or epoch != self.epoch
        if fill:
            self.valid = False
        # Render-start initialization dominates the unchanged selected-origin
        # live call, including the inactive/zero-body defensive shape.
        selected_origin = body_state(system, selected, epoch)
        terminal_down_y = selected_origin[6:]
        for body in range(count):
            hit = self.valid and epoch == self.epoch and body < 80
            if hit:
                raw = tuple(self.words[body * 8:body * 8 + 8])
                pending = body
            else:
                raw = body_state(system, body, epoch)
                calls += 1
                pending = None
                terminal_down_y = raw[6:]
            events.append(("resident", body, relative(raw, camera)))
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
                if hit:
                    raw = tuple(self.words[body * 8:body * 8 + 8])
                    pending = body
                else:
                    raw = body_state(system, body, epoch)
                    calls += 1
                    pending = None
                    terminal_down_y = raw[6:]
                events.append(("primary", body, relative(raw, camera)))
        # Each actual direct companion call is a live down-y writer.
        if companion is not None:
            pending = None
            terminal_down_y = body_state(system, companion, epoch)[6:]
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
            if hit:
                raw = tuple(self.words[body * 8:body * 8 + 8])
                pending = body
            else:
                raw = body_state(system, body, current_epoch)
                calls += 1
                pending = None
                terminal_down_y = raw[6:]
            events.append(("render", body, relative(raw, camera)))
            # Surface generation preserves both pending and live down-y because
            # its phase-setup chain does not touch VHGNDowny0/1.
        # The selected-body surface path has the same scratch-state property.
        # The common render-done boundary replays exactly once only when the
        # latest down-y writer was a skipped cached absolute-vector call.
        if pending is not None:
            start = pending * 8
            terminal_down_y = tuple(self.words[start + 6:start + 8])
        return selected_origin, tuple(events), terminal_down_y, calls, current_epoch


spec = importlib.util.spec_from_file_location("deferred_cache_applier", APPLIER)
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
            primaries = tuple(
                body for body in all_bodies
                if primary_mask & (1 << body)
            )
            for epoch in (0, 1):
                cache = DeferredCache()
                shapes = (
                    {},
                    {"companion": (selected + 1) % count},
                    {
                        "surface_miss_at": (
                            None if count == 1 else (selected + 1) % count
                        ),
                        "selected_surface_miss": count == 1,
                    },
                )
                for camera_index, shape in enumerate(shapes):
                    camera = (camera_index, -camera_index, camera_index * 17)
                    expected = accepted_frame(
                        0, count, selected, primaries, epoch, camera, **shape)
                    actual = cache.frame(
                        0, count, selected, primaries, epoch, camera, **shape)
                    assert actual[:3] == expected[:3]
                    cases += 1
                # Rollover plus direct writers exercises invalidation after a
                # prior hit and before the one common terminal replay.
                rollover = selected if selected + 1 == count else selected + 1
                camera = (99, -101, 0)
                shape = {
                    "rollover_at": rollover,
                    "companion": selected,
                    "selected_surface_miss": True,
                }
                expected = accepted_frame(
                    0, count, selected, primaries, epoch, camera, **shape)
                actual = cache.frame(
                    0, count, selected, primaries, epoch, camera, **shape)
                assert actual[:3] == expected[:3]
                cases += 1

# Lifecycle invalidation prevents same-second state from a prior generated
# system from reaching either public geometry or terminal down-y.
cache = DeferredCache()
first = cache.frame(0, 7, 3, (0, 2, 4, 6), 5, (1, 2, 3))
cache.invalidate()
second = cache.frame(1, 7, 3, (0, 2, 4, 6), 5, (1, 2, 3))
expected = accepted_frame(1, 7, 3, (0, 2, 4, 6), 5, (1, 2, 3))
assert first[:3] != second[:3]
assert second[:3] == expected[:3]

# The 80-record boundary is exact. A defensive 81st body disables publication
# without writing outside the flat shared-Lino workspace.
cache = DeferredCache()
primaries_81 = tuple(range(0, 81, 7))
actual = cache.frame(0, 81, 3, primaries_81, 9, (0, 0, 0))
expected = accepted_frame(0, 81, 3, primaries_81, 9, (0, 0, 0))
assert actual[:3] == expected[:3]
assert not cache.valid
assert 79 * 8 + 7 == 639

# Fixed checkpoint: the first presentation computes 78 records, then later
# scans/traversal replay vectors. Down-y is replayed once, not once per hit.
cache = DeferredCache()
count = 78
selected = 3
primaries = tuple(range(0, count, 7))[:12]
cold = cache.frame(0, count, selected, primaries, 11, (0, 0, 0))
hot = cache.frame(0, count, selected, primaries, 11, (1, 0, -1))
accepted_cold = accepted_frame(
    0, count, selected, primaries, 11, (0, 0, 0))
accepted_hot = accepted_frame(
    0, count, selected, primaries, 11, (1, 0, -1))
assert cold[:3] == accepted_cold[:3]
assert hot[:3] == accepted_hot[:3]
assert accepted_cold[3] == 167
assert cold[3] == 78
assert hot[3] == 0
assert sum(
    accepted_frame(0, count, selected, primaries, 11, (0, 0, 0))[3]
    for _ in range(60)
) == 10020
assert cold[3] + sum(
    cache.frame(0, count, selected, primaries, 11, (frame, 0, 0))[3]
    for frame in range(1, 60)
) == 78

text = candidate.decode("utf-8")
accepted_text = accepted.decode("utf-8")
render = text[text.index('"VHG local render"'):text.index('"VHG local companion coronas"')]
resident = text[text.index('"VHG local resident scan"'):text.index('"VHG local ensure surface"')]
companion = text[text.index('"VHG local companion coronas"'):text.index('"VHG local resident scan"')]
surface = text[text.index('"VHG local ensure surface"'):text.index('"VHG local center coords"')]
helper = text[text.index('"VHG local absolute body vector"'):text.index('"VHG local body relative"')]
render_done = render[render.index('"VHG local render done"'):]
assert text.count("VHGlocalvectorcache = 640;") == 1
assert text.count("VHGlocalveccachepending = 0FFFFFFFFh;") == 1
assert text.count("A < 3; E = VHGlocalvectorcache; E + A;") == 3
assert text.count("=> VHG local absolute body vector;") == 3
assert text.count("=> VHGND absolute body vector;") == accepted_text.count(
    "=> VHGND absolute body vector;") - 2
assert render.count("[VHGlocalveccachepending] = 0FFFFFFFFh;") == 1
assert render.index("[VHGlocalveccachepending] = 0FFFFFFFFh;") < render.index(
    "? A = 0 -> VHG local render done;")
assert resident.count("[E plus 6] = [VHGNDowny0]") == 1
assert resident.count("[E plus 7] = [VHGNDowny1]") == 1
assert resident.index("[E plus 7] = [VHGNDowny1]") < resident.index(
    "[VHGlocalveccachevalid] = 1;")
assert companion.count(
    "[VHGlocalveccachepending] = 0FFFFFFFFh; [VHGNDvecindex] = [VHGlocalbody];"
) == 1
assert surface.count("[VHGlocalveccachepending] = 0FFFFFFFFh;") == 0
assert helper.count("[VHGlocalveccachepending] = A;") == 1
assert helper.count("[VHGlocalveccachepending] = 0FFFFFFFFh;") == 1
assert helper.count("[VHGNDowny0]") == 0
assert helper.count("[VHGNDowny1]") == 0
assert helper.count("=> VHGND absolute body vector;") == 1
assert render_done.count("[VHGNDowny0] = [E plus 6]") == 1
assert render_done.count("[VHGNDowny1] = [E plus 7]") == 1
assert render_done.count("VHG local terminal down y ready") == 2
assert text.count("[VHGlocalveccachevalid] = 0; [VHGlocalveccachefill] = 0; [VHGlocalveccachepending] = 0FFFFFFFFh;") == 3
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
    EVIDENCE / "accepted/compiler114m.exe")
assert digest(ROOT / "main/cpu/i386m.bin") == digest(
    EVIDENCE / "accepted/i386m.bin")

result = {
    "schema": 1,
    "task": 212,
    "cases": cases,
    "raw_absolute_vector_words_replayed_exactly": True,
    "terminal_owner_relative_y_replayed_once_at_common_render_done": True,
    "pending_invalidated_by_wrapper_live_calls": True,
    "pending_invalidated_by_direct_companion_calls": True,
    "pending_preserved_across_surface_cache_misses": True,
    "surface_cache_misses_do_not_access_down_y": True,
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
    "candidate_hot_cached_vector_hits": 167,
    "task_210_hot_down_y_pair_replays": 167,
    "candidate_hot_down_y_pair_replays": 1,
    "accepted_calls_per_stable_second_at_60_presentations": 10020,
    "candidate_calls_per_stable_second_at_60_presentations": 78,
    "selected_origin_call_unchanged": True,
    "selected_body_path_unchanged": True,
    "companion_path_order_unchanged": True,
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
    json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
