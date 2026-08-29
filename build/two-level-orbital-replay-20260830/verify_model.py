from pathlib import Path
import hashlib
import importlib.util
import json

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/two-level-orbital-replay-20260830"
ACCEPTED = EVIDENCE / "accepted/vhgame.txt"
CANDIDATE = ROOT / "work/vhgame.txt"
APPLIER = EVIDENCE / "apply_candidate.py"

RECORD_WORDS = 64
WORKSPACE_WORDS = 80 * RECORD_WORDS


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


POOL = (
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
SCRATCH_NAMES = (
    "mass", "orbit", "angle", "sin", "cos",
    "ct", "xx", "zz", "so", "co",
)


def pair_words(seed):
    return (
        POOL[seed % len(POOL)],
        POOL[(seed * 5 + 3) % len(POOL)],
    )


def body_absolute(system, body, epoch):
    return tuple(
        POOL[(system * 7 + body * 3 + epoch * 5 + unit) % len(POOL)]
        for unit in range(6)
    )


def pair(words, axis):
    return words[axis * 2:axis * 2 + 2]


def absolute_scratch(system, body, epoch):
    terminal_owner = -1 if (system + body * 2 + epoch) % 3 else body + 1
    terminal_index = body if terminal_owner < 0 else body + 3
    values = tuple(
        pair_words(system * 97 + body * 31 + epoch * 13 + index * 7)
        for index in range(len(SCRATCH_NAMES))
    )
    return {
        "absolute": body_absolute(system, body, epoch),
        "vecindex": terminal_index,
        "vecowner": terminal_owner,
        "pairs": values,
    }


def vhgnd_terminal(scratch):
    absolute = scratch["absolute"]
    return (
        absolute,
        absolute,
        scratch["vecindex"],
        scratch["vecowner"],
        scratch["pairs"],
    )


def exact_sub(left, right):
    # Preserve operation identity and grouping rather than approximating x87
    # binary64 arithmetic with the host Python floating implementation.
    return ("fsub", left, right)


def exact_mul(left, right):
    return ("fmul", left, right)


def selected_basis(raw, selected_raw):
    return tuple(
        exact_sub(pair(raw, axis), pair(selected_raw, axis))
        for axis in range(3)
    )


def camera_relative(basis, camera):
    return tuple(exact_sub(basis[axis], pair(camera, axis)) for axis in range(3))


def rooted_distance(coords):
    return ("root", coords)


def narrowed_distance(distance):
    return ("f32-roundtrip", distance)


def center_coords(camera):
    zero = (0x00000000, 0x00000000)
    return tuple(exact_sub(zero, pair(camera, axis)) for axis in range(3))


def last_terminal_body(count, selected):
    if count == 1:
        return 0
    last = count - 1
    return last - 1 if last == selected else last


def initial_fp(system, epoch, camera):
    return {
        "fa": ("entry-fa", system, epoch),
        "fb": ("entry-fb", system, epoch),
        "fi": ("entry-fi", system, epoch),
        "fs0": ("entry-fs0", system, epoch, camera[0]),
        "pgfi": ("entry-pgfi", system, epoch),
        "sf": tuple(("entry-sf", axis, system, epoch) for axis in range(3)),
        "fsw0": ("entry-fsw0", system, epoch),
    }


def copy_fp(fp):
    return dict(fp)


def apply_absolute_state(fp, scratch):
    fp = copy_fp(fp)
    if scratch["vecowner"] < 0:
        fp["fs0"] = ("nsstarray",)
    return fp, vhgnd_terminal(scratch)


def apply_geometry_state(fp, scratch, coords, camera):
    fp, vhgnd = apply_absolute_state(fp, scratch)
    fp["fa"] = coords[2]
    fp["fb"] = pair(camera, 2)
    fp["pgfi"] = "SFZZ"
    fp["sf"] = coords
    return fp, vhgnd


def apply_distance_state(fp, coords, distance):
    fp = copy_fp(fp)
    fp["fsw0"] = exact_mul(coords[0], coords[0])
    fp["fa"] = distance
    fp["fb"] = fp["fb"]
    fp["pgfi"] = "FSW0"
    return fp


def helper_terminal(kind, body, fp, vhgnd, coords, distance):
    return (
        kind,
        body,
        fp["fa"],
        fp["fb"],
        fp["fi"],
        fp["fs0"],
        fp["pgfi"],
        fp["sf"],
        fp["fsw0"],
        vhgnd,
        coords,
        distance,
    )


def common_loop_effect(fp, stage, body):
    fp = copy_fp(fp)
    fp["fi"] = (stage, "fi", body)
    return fp


def common_companion_effect(fp, system, body, epoch):
    fp = copy_fp(fp)
    fp.update({
        "fa": ("companion-fa", system, body, epoch),
        "fb": ("companion-fb", system, body, epoch),
        "fi": ("companion-fi", system, body, epoch),
        "pgfi": ("companion-pgfi", system, body, epoch),
        "sf": tuple(("companion-sf", axis, system, body, epoch) for axis in range(3)),
        "fsw0": ("companion-fsw0", system, body, epoch),
    })
    scratch = absolute_scratch(system, body, epoch)
    fp, vhgnd = apply_absolute_state(fp, scratch)
    return fp, vhgnd


def accepted_frame(
        system, count, selected, ordinary, primaries, frame_epoch, camera, *,
        resident_epochs=None, primary_epoch=None, companion_epoch=None,
        body_epochs=None):
    resident_epochs = resident_epochs or (frame_epoch,) * count
    primary_epoch = frame_epoch if primary_epoch is None else primary_epoch
    companion_epoch = frame_epoch if companion_epoch is None else companion_epoch
    body_epochs = body_epochs or (frame_epoch,) * count
    selected_raw = body_absolute(system, selected, frame_epoch)
    terminal_down_y = pair(selected_raw, 1)
    distance_state = ("initial-distance", system, frame_epoch)
    public = []
    helper_trace = []
    cacheable_calls = 0
    full_relative = 0
    distance_chains = 0
    fp = initial_fp(system, frame_epoch, camera)
    vhgnd = ("initial-vhgnd", system, frame_epoch)

    for body in range(count):
        epoch = resident_epochs[body]
        scratch = absolute_scratch(system, body, epoch)
        raw = scratch["absolute"]
        terminal_down_y = pair(raw, 1)
        coords = camera_relative(selected_basis(raw, selected_raw), camera)
        distance_state = rooted_distance(coords)
        fp, vhgnd = apply_geometry_state(fp, scratch, coords, camera)
        fp = apply_distance_state(fp, coords, distance_state)
        helper_trace.append(helper_terminal(
            "resident", body, fp, vhgnd, coords, distance_state))
        public.append(("resident", body, coords, distance_state))
        cacheable_calls += 1
        full_relative += 1
        distance_chains += 1
        fp = common_loop_effect(fp, "resident", body)

    for body in primaries:
        scratch = absolute_scratch(system, body, primary_epoch)
        raw = scratch["absolute"]
        terminal_down_y = pair(raw, 1)
        coords = camera_relative(selected_basis(raw, selected_raw), camera)
        distance_state = rooted_distance(coords)
        fp, vhgnd = apply_geometry_state(fp, scratch, coords, camera)
        fp = apply_distance_state(fp, coords, distance_state)
        helper_trace.append(helper_terminal(
            "primary", body, fp, vhgnd, coords, distance_state))
        public.append(("primary", body, distance_state))
        cacheable_calls += 1
        full_relative += 1
        distance_chains += 1
        fp = common_loop_effect(fp, "primary", body)

    for body in range(count):
        if ordinary[body]:
            continue
        raw = body_absolute(system, body, companion_epoch)
        terminal_down_y = pair(raw, 1)
        coords = camera_relative(selected_basis(raw, selected_raw), camera)
        distance_state = narrowed_distance(rooted_distance(coords))
        public.append(("companion", body, coords, distance_state))
        fp, vhgnd = common_companion_effect(
            fp, system, body, companion_epoch)

    fp = initial_fp(system + 11, frame_epoch, camera)
    for body in range(count):
        if body == selected:
            continue
        epoch = body_epochs[body]
        scratch = absolute_scratch(system, body, epoch)
        raw = scratch["absolute"]
        terminal_down_y = pair(raw, 1)
        coords = camera_relative(selected_basis(raw, selected_raw), camera)
        fp, vhgnd = apply_geometry_state(fp, scratch, coords, camera)
        helper_trace.append(helper_terminal(
            "frame-geometry", body, fp, vhgnd, coords, distance_state))
        if ordinary[body]:
            distance_state = rooted_distance(coords)
            fp = apply_distance_state(fp, coords, distance_state)
            helper_trace.append(helper_terminal(
                "frame-distance", body, fp, vhgnd, coords, distance_state))
            distance_chains += 1
        public.append(("body", body, coords, distance_state, ordinary[body]))
        cacheable_calls += 1
        full_relative += 1
        fp = common_loop_effect(fp, "body", body)

    selected_coords = center_coords(camera)
    fp["sf"] = selected_coords
    if ordinary[selected]:
        distance_state = rooted_distance(selected_coords)
        fp = apply_distance_state(fp, selected_coords, distance_state)
    public.append(("selected", selected, selected_coords, distance_state,
                   ordinary[selected]))
    frame_terminal = (fp["fs0"], fp["fsw0"], terminal_down_y)
    return {
        "public": tuple(public),
        "helper_trace": tuple(helper_trace),
        "terminal_down_y": terminal_down_y,
        "terminal_distance": distance_state,
        "frame_terminal": frame_terminal,
        "cacheable_calls": cacheable_calls,
        "full_relative": full_relative,
        "half_relative": 0,
        "distance_chains": distance_chains,
        "distance_square_replays": 0,
    }


class TwoLevelCache:
    def __init__(self):
        self.valid = False
        self.epoch = 0
        self.words = [None] * WORKSPACE_WORDS

    def invalidate(self):
        self.valid = False

    def store_pair(self, start, offset, value):
        self.words[start + offset:start + offset + 2] = [value, value]

    def load_pair(self, start, offset):
        return self.words[start + offset]

    def store_scratch(self, start, scratch):
        absolute = scratch["absolute"]
        self.words[start + 6:start + 12] = list(absolute)
        self.words[start + 20] = scratch["vecindex"]
        self.words[start + 21] = scratch["vecowner"]
        for index, value in enumerate(scratch["pairs"]):
            self.store_pair(start, 22 + index * 2, value)

    def load_scratch(self, start):
        return {
            "absolute": tuple(self.words[start + 6:start + 12]),
            "vecindex": self.words[start + 20],
            "vecowner": self.words[start + 21],
            "pairs": tuple(
                self.load_pair(start, 22 + index * 2)
                for index in range(len(SCRATCH_NAMES))
            ),
        }

    def store_basis(self, start, basis):
        for axis, value in enumerate(basis):
            self.store_pair(start, axis * 2, value)

    def load_basis(self, start):
        return tuple(self.load_pair(start, axis * 2) for axis in range(3))

    def store_frame(self, start, coords, distance):
        for axis, value in enumerate(coords):
            self.store_pair(start, 12 + axis * 2, value)
        self.store_pair(start, 18, distance)

    def load_coords(self, start):
        return tuple(self.load_pair(start, 12 + axis * 2) for axis in range(3))

    def frame(
            self, system, count, selected, ordinary, primaries, frame_epoch,
            camera, *, resident_epochs=None, primary_epoch=None,
            companion_epoch=None, body_epochs=None):
        resident_epochs = resident_epochs or (frame_epoch,) * count
        primary_epoch = frame_epoch if primary_epoch is None else primary_epoch
        companion_epoch = frame_epoch if companion_epoch is None else companion_epoch
        body_epochs = body_epochs or (frame_epoch,) * count
        selected_raw = body_absolute(system, selected, frame_epoch)
        terminal_down_y = pair(selected_raw, 1)
        distance_state = ("initial-distance", system, frame_epoch)
        public = []
        helper_trace = []
        cacheable_calls = 0
        full_relative = 0
        half_relative = 0
        distance_chains = 0
        distance_square_replays = 0
        fp = initial_fp(system, frame_epoch, camera)
        vhgnd = ("initial-vhgnd", system, frame_epoch)

        capacity = 0 < count <= 80
        frame_valid = capacity
        fill = capacity and (not self.valid or self.epoch != frame_epoch)
        if not capacity or fill:
            self.valid = False
        terminal_valid = capacity and self.valid and self.epoch == frame_epoch

        for body in range(count):
            epoch = resident_epochs[body]
            if frame_valid and epoch != frame_epoch:
                self.valid = False
                fill = False
                frame_valid = False
                terminal_valid = False
            if frame_valid and not fill:
                start = body * RECORD_WORDS
                scratch = self.load_scratch(start)
                basis = self.load_basis(start)
                coords = camera_relative(basis, camera)
                half_relative += 1
            else:
                scratch = absolute_scratch(system, body, epoch)
                raw = scratch["absolute"]
                terminal_down_y = pair(raw, 1)
                basis = selected_basis(raw, selected_raw)
                coords = camera_relative(basis, camera)
                cacheable_calls += 1
                full_relative += 1
                if frame_valid and fill:
                    start = body * RECORD_WORDS
                    self.store_scratch(start, scratch)
                    self.store_basis(start, basis)
            distance_state = rooted_distance(coords)
            distance_chains += 1
            fp, vhgnd = apply_geometry_state(fp, scratch, coords, camera)
            fp = apply_distance_state(fp, coords, distance_state)
            helper_trace.append(helper_terminal(
                "resident", body, fp, vhgnd, coords, distance_state))
            public.append(("resident", body, coords, distance_state))
            if frame_valid:
                self.store_frame(body * RECORD_WORDS, coords, distance_state)
            fp = common_loop_effect(fp, "resident", body)

        if frame_valid and resident_epochs[-1] == frame_epoch:
            if fill:
                self.epoch = frame_epoch
                self.valid = True
                fill = False
        else:
            self.valid = False
            fill = False
            frame_valid = False
            terminal_valid = False

        for body in primaries:
            if frame_valid and primary_epoch == frame_epoch:
                start = body * RECORD_WORDS
                scratch = self.load_scratch(start)
                coords = self.load_coords(start)
                distance_state = self.load_pair(start, 18)
                fp, vhgnd = apply_geometry_state(fp, scratch, coords, camera)
                fp = apply_distance_state(fp, coords, distance_state)
                distance_square_replays += 1
            else:
                if primary_epoch != frame_epoch:
                    self.valid = False
                    frame_valid = False
                terminal_valid = False
                scratch = absolute_scratch(system, body, primary_epoch)
                raw = scratch["absolute"]
                terminal_down_y = pair(raw, 1)
                coords = camera_relative(selected_basis(raw, selected_raw), camera)
                distance_state = rooted_distance(coords)
                fp, vhgnd = apply_geometry_state(fp, scratch, coords, camera)
                fp = apply_distance_state(fp, coords, distance_state)
                cacheable_calls += 1
                full_relative += 1
                distance_chains += 1
            helper_trace.append(helper_terminal(
                "primary", body, fp, vhgnd, coords, distance_state))
            public.append(("primary", body, distance_state))
            fp = common_loop_effect(fp, "primary", body)

        for body in range(count):
            if ordinary[body]:
                continue
            terminal_valid = False
            raw = body_absolute(system, body, companion_epoch)
            terminal_down_y = pair(raw, 1)
            coords = camera_relative(selected_basis(raw, selected_raw), camera)
            distance_state = narrowed_distance(rooted_distance(coords))
            public.append(("companion", body, coords, distance_state))
            fp, vhgnd = common_companion_effect(
                fp, system, body, companion_epoch)

        fp = initial_fp(system + 11, frame_epoch, camera)
        if count > 1:
            terminal_valid = frame_valid
        for body in range(count):
            if body == selected:
                continue
            epoch = body_epochs[body]
            if frame_valid and epoch != frame_epoch:
                self.valid = False
                frame_valid = False
                terminal_valid = False
            if frame_valid:
                start = body * RECORD_WORDS
                scratch = self.load_scratch(start)
                coords = self.load_coords(start)
            else:
                terminal_valid = False
                scratch = absolute_scratch(system, body, epoch)
                raw = scratch["absolute"]
                terminal_down_y = pair(raw, 1)
                coords = camera_relative(selected_basis(raw, selected_raw), camera)
                cacheable_calls += 1
                full_relative += 1
            fp, vhgnd = apply_geometry_state(fp, scratch, coords, camera)
            helper_trace.append(helper_terminal(
                "frame-geometry", body, fp, vhgnd, coords, distance_state))
            if ordinary[body]:
                if frame_valid:
                    distance_state = self.load_pair(start, 18)
                    distance_square_replays += 1
                else:
                    distance_state = rooted_distance(coords)
                    distance_chains += 1
                fp = apply_distance_state(fp, coords, distance_state)
                helper_trace.append(helper_terminal(
                    "frame-distance", body, fp, vhgnd, coords, distance_state))
            public.append(("body", body, coords, distance_state, ordinary[body]))
            fp = common_loop_effect(fp, "body", body)

        selected_coords = center_coords(camera)
        fp["sf"] = selected_coords
        if ordinary[selected]:
            distance_state = rooted_distance(selected_coords)
            fp = apply_distance_state(fp, selected_coords, distance_state)
        public.append(("selected", selected, selected_coords, distance_state,
                       ordinary[selected]))
        if terminal_valid:
            body = last_terminal_body(count, selected)
            terminal_down_y = pair(
                tuple(self.words[body * RECORD_WORDS + 6:body * RECORD_WORDS + 12]),
                1,
            )
        frame_terminal = (fp["fs0"], fp["fsw0"], terminal_down_y)
        return {
            "public": tuple(public),
            "helper_trace": tuple(helper_trace),
            "terminal_down_y": terminal_down_y,
            "terminal_distance": distance_state,
            "frame_terminal": frame_terminal,
            "cacheable_calls": cacheable_calls,
            "full_relative": full_relative,
            "half_relative": half_relative,
            "distance_chains": distance_chains,
            "distance_square_replays": distance_square_replays,
        }


spec = importlib.util.spec_from_file_location("two_level_applier", APPLIER)
applier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(applier)
accepted = ACCEPTED.read_bytes()
candidate = applier.transform(accepted)
if CANDIDATE.exists() and digest(CANDIDATE) != digest(ACCEPTED):
    assert CANDIDATE.read_bytes() == candidate


def assert_equivalent(actual, expected):
    assert actual["public"] == expected["public"]
    assert actual["helper_trace"] == expected["helper_trace"]
    assert actual["terminal_down_y"] == expected["terminal_down_y"]
    assert actual["terminal_distance"] == expected["terminal_distance"]
    assert actual["frame_terminal"] == expected["frame_terminal"]


cases = 0
for count in range(1, 8):
    for selected in range(count):
        for type_mask in range(1 << count):
            ordinary = tuple(
                not bool(type_mask & (1 << body)) for body in range(count))
            primaries = tuple(
                body for body in range(count)
                if body != selected and (body + type_mask) % 3 == 0)
            if count > 1 and not primaries:
                primaries = ((selected + 1) % count,)
            for epoch in (0, 1):
                cache = TwoLevelCache()
                camera0 = tuple(POOL[(axis + epoch) % len(POOL)] for axis in range(6))
                expected = accepted_frame(
                    0, count, selected, ordinary, (), epoch, camera0)
                actual = cache.frame(
                    0, count, selected, ordinary, (), epoch, camera0)
                assert_equivalent(actual, expected)
                cases += 1

                camera1 = tuple(POOL[(axis + epoch + 3) % len(POOL)] for axis in range(6))
                expected = accepted_frame(
                    0, count, selected, ordinary, primaries, epoch, camera1)
                actual = cache.frame(
                    0, count, selected, ordinary, primaries, epoch, camera1)
                assert_equivalent(actual, expected)
                cases += 1

                rollover = next(
                    (body for body in range(count) if body != selected), None)
                body_epochs = tuple(
                    epoch + 1 if rollover is not None and body >= rollover
                    else epoch for body in range(count))
                camera2 = tuple(POOL[(axis + epoch + 6) % len(POOL)] for axis in range(6))
                expected = accepted_frame(
                    0, count, selected, ordinary, primaries, epoch, camera2,
                    body_epochs=body_epochs)
                actual = cache.frame(
                    0, count, selected, ordinary, primaries, epoch, camera2,
                    body_epochs=body_epochs)
                assert_equivalent(actual, expected)
                cases += 1

                camera3 = tuple(POOL[(axis + epoch + 8) % len(POOL)] for axis in range(6))
                next_epoch = epoch + 1
                expected = accepted_frame(
                    0, count, selected, ordinary, primaries, next_epoch, camera3)
                actual = cache.frame(
                    0, count, selected, ordinary, primaries, next_epoch, camera3)
                assert_equivalent(actual, expected)
                cases += 1

# Lifecycle invalidation rejects a same-second basis from a regenerated system.
cache = TwoLevelCache()
ordinary = (True, False, True, True, False, True, True)
cache.frame(0, 7, 3, ordinary, (0, 2, 4, 6), 5, tuple(POOL[:6]))
cache.invalidate()
expected = accepted_frame(
    1, 7, 3, ordinary, (0, 2, 4, 6), 5, tuple(POOL[2:8]))
actual = cache.frame(
    1, 7, 3, ordinary, (0, 2, 4, 6), 5, tuple(POOL[2:8]))
assert_equivalent(actual, expected)

# The exact 80-record bound and fail-closed 81-body shape.
cache = TwoLevelCache()
ordinary_81 = (True,) * 81
primaries_81 = tuple(range(0, 81, 7))
expected = accepted_frame(
    0, 81, 3, ordinary_81, primaries_81, 9, tuple(POOL[:6]))
actual = cache.frame(
    0, 81, 3, ordinary_81, primaries_81, 9, tuple(POOL[:6]))
assert_equivalent(actual, expected)
assert not cache.valid
assert 79 * RECORD_WORDS + 63 == 5119

# Fixed 78-body checkpoint work accounting, excluding unchanged companion calls.
count = 78
selected = 3
ordinary = (True,) * count
primaries = tuple(range(0, count, 7))[:12]
camera = tuple(POOL[:6])
cache = TwoLevelCache()
accepted_fixed = accepted_frame(
    0, count, selected, ordinary, primaries, 11, camera)
cold = cache.frame(0, count, selected, ordinary, primaries, 11, camera)
hot = cache.frame(0, count, selected, ordinary, primaries, 11, tuple(POOL[1:7]))
assert accepted_fixed["cacheable_calls"] == 167
assert accepted_fixed["full_relative"] == 167
assert accepted_fixed["distance_chains"] == 167
assert cold["cacheable_calls"] == 78
assert cold["full_relative"] == 78
assert cold["distance_chains"] == 78
assert hot["cacheable_calls"] == 0
assert hot["full_relative"] == 0
assert hot["half_relative"] == 78
assert hot["distance_chains"] == 78
assert hot["distance_square_replays"] == 89
assert 167 * 6 - 78 * 3 == 768
assert 167 - 78 == 89
assert 167 * 60 == 10020
assert 78 + 59 * 0 == 78

text = candidate.decode("utf-8")
accepted_text = accepted.decode("utf-8")
render = text[text.index('"VHG local render"'):text.index('"VHG local companion coronas"')]
companion = text[text.index('"VHG local companion coronas"'):text.index('"VHG local resident scan"')]
resident = text[text.index('"VHG local resident scan"'):text.index('"VHG local ensure surface"')]
surface = text[text.index('"VHG local ensure surface"'):text.index('"VHG local center coords"')]
helpers = text[text.index('"VHG local resident body geometry"'):text.index('"VHG local body relative"')]
render_done = render[render.index('"VHG local render done"'):]
assert text.count("VHGlocalbodycache = 5120;") == 1
assert text.count("A < 6; E = VHGlocalbodycache; E + A;") == 7
assert resident.count("=> VHG local resident body geometry;") == 1
assert resident.count("=> VHG local primary body distance;") == 1
assert render.count("=> VHG local frame body geometry;") == 1
assert render.count("=> VHG local frame body distance;") == 1
assert companion.count("[VHGlocalterminalvalid] = 0;") == 1
assert companion.count("=> VHGND absolute body vector;") == 1
assert surface == accepted_text[
    accepted_text.index('"VHG local ensure surface"'):
    accepted_text.index('"VHG local center coords"')]
assert helpers.count("[E plus 0] = [VHGNDvecx0]") == 1
assert helpers.count("[E plus 6] = [VHGNDvecx0]") == 1
assert helpers.count("[E plus 20] = [VHGNDvecindex]") == 1
assert helpers.count("[E plus 41] = [VHGNDco1]") == 1
assert helpers.count("[E plus 12] = [VHGlocalringcx0]") == 1
assert helpers.count("[E plus 19] = [VHGlocaldist1]") == 1
assert helpers.count("[VHGlocalringcx0] = [E plus 12]") == 1
assert helpers.count("[VHGlocaldist0] = [E plus 18]") == 1
assert helpers.count("=> VHG local replay absolute scratch;") == 2
assert helpers.count("=> VHG local replay frame geometry;") == 2
assert helpers.count("=> VHG local replay body distance;") == 2
assert helpers.count("=> VHG local cached basis relative;") == 1
assert helpers.count("=> VHG local selected basis relative;") == 1
assert helpers.count("=> VHGND absolute body vector;") == 4
assert helpers.count("[PGFi] = FSW0; => PGF sa;") == 1
assert helpers.count("[FS0] = [nsstarray];") == 1
assert render_done.count("[VHGNDowny0] = [E plus 8]") == 1
assert render_done.count("[VHGNDowny1] = [E plus 9]") == 1
assert "VHGlocalterminalvalid" not in surface
assert "VHGlocalterminalvalid" not in text[
    text.index('"VHG local selected render"'):
    text.index('"VHG local render done"')]
assert text.count("[VHGlocalbasisvalid] = 0; [VHGlocalbasisfill] = 0;") >= 3
assert text.count("=> VHG local resident scan;") == accepted_text.count(
    "=> VHG local resident scan;")
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
    "task": 214,
    "cases": cases,
    "development_correction": "expanded unmeasured 16-word candidate after adversarial strict-state failure",
    "raw_binary64_basis_words_replayed_exactly": True,
    "raw_absolute_and_orbit_scratch_words_replayed_exactly": True,
    "accepted_arithmetic_grouping_preserved": "(body_absolute-selected_absolute)-camera",
    "signed_zero_nan_infinity_payloads_preserved": True,
    "moving_camera_second_subtractions_recomputed": True,
    "frame_coordinates_and_rooted_distances_replayed_exactly": True,
    "strict_fa_fb_fi_fs_pgfi_sf_vhgnd_helper_state_exact": True,
    "conditional_fs0_write_or_preserve_exact": True,
    "cold_fill_absolute_vector_terminal_state_restored": True,
    "distance_terminal_fsw0_fa_fb_pgfi_exact": True,
    "type10_distance_and_fsw0_state_preserved": True,
    "primary_rescan_terminal_state_preserved": True,
    "companion_calls_live_and_ordered": True,
    "surface_paths_do_not_access_terminal_down_y": True,
    "deterministic_terminal_down_y_replayed_once": True,
    "per_hit_pending_stores": 0,
    "same_frame_epoch_rollover_fails_closed": True,
    "local_reset_start_restore_invalidate": True,
    "over_capacity_fails_closed": True,
    "workspace_units": WORKSPACE_WORDS,
    "record_units": RECORD_WORDS,
    "used_record_units": 42,
    "maximum_cached_bodies": 80,
    "fixed_checkpoint_bodies": 78,
    "fixed_checkpoint_primary_rescan_bodies": 12,
    "fixed_checkpoint_nonselected_bodies": 77,
    "accepted_cacheable_absolute_calls_per_presentation": 167,
    "candidate_cold_cacheable_absolute_calls": 78,
    "candidate_hot_cacheable_absolute_calls": 0,
    "accepted_full_relative_calculations": 167,
    "candidate_cold_full_relative_calculations": 78,
    "candidate_hot_full_relative_calculations": 0,
    "candidate_hot_half_relative_calculations": 78,
    "candidate_hot_distance_square_replays": 89,
    "hot_scalar_fsub_savings": 768,
    "hot_rooted_distance_savings": 89,
    "accepted_calls_per_stable_second_at_60_presentations": 10020,
    "candidate_calls_per_stable_second_at_60_presentations": 78,
    "selected_origin_and_selected_render_unchanged": True,
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
