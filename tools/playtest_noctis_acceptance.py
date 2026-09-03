#!/usr/bin/env python3
"""Run release-level Noctis playability routes on a private desktop."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import struct
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from noctis_control_trace import (  # noqa: E402
    ControlState,
    TRACE_NAME,
    TraceReader,
)
from profile_noctis_desktop import (  # noqa: E402
    CLOCK_SECONDS,
    PROFILE_UNITS,
    decode_profile,
    file_sha256,
    scenario_checkpoint,
    stage_scenario,
    wait_for_ready,
)
from windows_hidden_process import PrivateDesktopProcess  # noqa: E402


OUTPUT_ROOT = ROOT / "build" / "v1-playability"
DEFAULT_EXECUTABLE = ROOT / "work" / "vhgame.exe"
GAME_SOURCE = ROOT / "work" / "vhgame.txt"
TRACKED_GUIDE = ROOT / "work" / "GUIDE.BIN"
TRACKED_STARMAP = ROOT / "work" / "STARMAP.BIN"
TRACE_POINTER_NAME = "game-controls-pointer-in.bin"
TRACE_POINTER_MAGIC = 0x56484D50
REPORT_SCHEMA = 1
CHECKPOINT_SCHEMA = 18
CHECKPOINT_BYTES = 268
GUIDE_RECORD_BYTES = 84
STARMAP_RECORD_BYTES = 32
READINESS_TIMEOUT = 120.0
INPUT_TIMEOUT = 30.0
JOURNEY_TIMEOUT = 900.0

VK_ESCAPE = 0x1B
VK_RETURN = 0x0D
VK_DOWN = 0x28
VK_LEFT = 0x25
VK_RIGHT = 0x27
VK_UP = 0x26
VK_F1 = 0x70
VK_F2 = 0x71
VK_F3 = 0x72
VK_F5 = 0x74
VK_F6 = 0x75
VK_F7 = 0x76
VK_F9 = 0x78
VK_F10 = 0x79
VK_W = 0x57
VK_S = 0x53

LANDABLE_TYPES = frozenset(range(10)) - {0, 6, 9}
LAUNCH_OUTPUTS = (
    TRACE_NAME,
    TRACE_POINTER_NAME,
    "game-vh-out.bin",
    "game-sun-out.bin",
    "game-local-out.bin",
    "game-palette-out.bin",
    "game-page-out.bin",
    "game-profile-out.bin",
)
STATE_EVIDENCE_FIELDS = (
    "sequence", "quit", "preferences", "device", "browser_valid",
    "browser_origin", "fcs_open", "roofspeed", "mouselook", "x", "y",
    "z", "alpha", "beta", "landing_select", "landing_pending",
    "landing_longitude", "landing_latitude", "output_view", "mode", "screen",
    "console", "console_view", "info", "graphics", "movie_view",
    "movie_recording", "help", "about", "fast_presentation", "fps_show",
    "draw_hud", "lens_mode", "seamless", "landed", "capsule_state",
    "capsule_count", "capsule_recover", "capsule_start_pending",
    "capsule_return_pending", "planet", "planet_type", "system_body_count",
    "local_active", "local_target", "local_approaching", "local_reached",
    "star_drive", "star_reached", "drive_status", "target_x", "target_y",
    "target_z", "current_x_low", "current_x_high", "current_y_low",
    "current_y_high", "current_z_low", "current_z_high", "frame",
    "autoscreen_off", "reverse_controls", "menus_always_on", "depolarize",
    "amplifier", "finder", "sync", "antirad", "interior_light",
    "exterior_light", "reset_count", "gburst", "menu_hover", "menu_key",
    "device_access", "info_scroll", "notice_frames",
)

# Full-frame hashes are limited to pages whose complete pixels repeated exactly.
MENU_BASELINES = {
    "controls": "6ef97f7b24c6e687b4c4fb3c455d8bb607a511aa5407040178d823d1a40d0e5b",
    "goes-console": "a1249ea6334e37c3e25a4e1cb8a8ebed06055a3b6a7a035f8df37e649962598e",
    "landing-selector": "bb09e14045e4a4dcacd7c88abdc25aae1242896973256dd44e6936e266d8f5b8",
}

# Live-background pages pin the exact menu-colour mask. This checks every glyph
# and its placement without treating stars, EPOC, or environmental values as UI.
MENU_MASK_BASELINES = {
    "about": ((0, 0, 320, 200), (252, 248, 216),
              "b723d4ee2db9d20ba7bac2633d6fe309ffb64cb769c67ea64d3ccd6d1c05f704"),
    "visual-effects": ((0, 0, 320, 200), (128, 255, 255),
                       "32f7922c068b60d13e1e25a0f738f8e75c664f914f0ccfd309d9a4298959d03b"),
    "flight-control": ((0, 0, 320, 200), (128, 255, 255),
                       "dd72e5bd880bb412eb285af8f45110263b9ac3c9804299ee7bdb1cc04a149dd4"),
    "target-browser": ((0, 0, 320, 200), (128, 255, 255),
                       "d80182b6393a198694107d4954e6207ef2db311f4468f5f14978edb439d45b98"),
    "devices-root": ((0, 0, 320, 200), (128, 255, 255),
                     "d3979d4e6f6072eccf59519a7eac1583d00b882be4b047749e0bfe7397ca2ec2"),
    "navigation-devices": ((0, 0, 320, 200), (128, 255, 255),
                           "3329f18ffe52a4abe69ed5387a08894f38a2c5df2ae8072b11ff2e6ef63c5729"),
    "miscellaneous-devices": ((0, 0, 320, 200), (128, 255, 255),
                              "c0be6f041706b903f4048b6d01a26b9dd9fa110c6710a9e6608feeebdb5787d1"),
    "cartography-devices": ((0, 0, 320, 200), (128, 255, 255),
                            "127ceed1a267b5ee77f3acc2701b16b4cc3b32f70671474804f2697abc2a6f07"),
    "emergency-devices": ((0, 0, 320, 200), (128, 255, 255),
                          "09391f59ec77815f84a4c185cb6b760636bcff692cda5c8027b7b3b495c01925"),
    "preferences": ((0, 0, 320, 200), (128, 255, 255),
                    "182d9cf932750976d440d96f676a17bb33e6173bdbb9e56987e675218029a5e2"),
    "data-sheet-1": ((0, 45, 100, 130), (212, 240, 252),
                     "ad1b6c9f2de08121f742ebe457765a255851bd894135396253ca175099da97f3"),
    "data-sheet-2": ((0, 45, 100, 130), (212, 240, 252),
                     "4f667a2ac4c5a6e89a4ddf4d5c9fc51b4d6c37a86a1951f670e6f18f22d29af7"),
}

# Opaque cards can use an exact RGB crop. The environment card is limited to
# its stable heading because its live temperature and radiation values vary.
MENU_REGION_BASELINES = {
    "moviemaker": ((0, 130, 170, 186),
                   "5b66c9cd93d59554aed5ec5e921e0dd069e3d70a7fc85d8f6682a0b94ea64b08"),
    "data-sheet-3": ((0, 55, 100, 65),
                     "5efb659530eb569a054600ba2bc56112cb063b39974f0ec8a1099f13fbe07c2a"),
}


class AcceptanceFailure(AssertionError):
    pass


class AcceptanceBlocked(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AcceptanceFailure(message)


def exact_state(state: ControlState) -> dict[str, int]:
    return {name: state[name] for name in STATE_EVIDENCE_FIELDS}


def v18_checkpoint(scenario: str) -> bytes:
    checkpoint = bytearray(scenario_checkpoint(scenario))
    if len(checkpoint) == CHECKPOINT_BYTES - 4:
        checkpoint.extend(b"\0" * 4)
    require(
        len(checkpoint) == CHECKPOINT_BYTES,
        f"{scenario} fixture is {len(checkpoint)} bytes, expected {CHECKPOINT_BYTES}",
    )
    struct.pack_into("<i", checkpoint, 1 * 4, CHECKPOINT_SCHEMA)
    struct.pack_into("<i", checkpoint, 64 * 4, 36)
    struct.pack_into("<i", checkpoint, 66 * 4, 4227135)
    return bytes(checkpoint)


def decode_checkpoint(data: bytes) -> dict[str, Any]:
    if len(data) != CHECKPOINT_BYTES:
        raise ValueError(f"checkpoint is {len(data)} bytes, expected {CHECKPOINT_BYTES}")
    words = struct.unpack("<67i", data)
    if words[1] != CHECKPOINT_SCHEMA:
        raise ValueError(f"unsupported checkpoint schema {words[1]}")
    return {
        "schema": words[1],
        "mode": words[2],
        "planet": words[3],
        "x": words[4],
        "y": words[5],
        "z": words[6],
        "alpha": words[7],
        "beta": words[8],
        "galactic": struct.unpack_from("<3d", data, 12 * 4),
        "star_reached": words[19],
        "landed": words[22],
        "target": tuple(words[24:27]),
        "fast_presentation": words[27],
        "capsule": tuple(words[40:45]),
        "local_active": words[48],
        "local_target": words[49],
        "local": struct.unpack_from("<5d", data, 50 * 4),
        "local_approaching": words[60],
        "local_reached": words[61],
        "preferences_word": words[64],
        "runtime_word": words[66],
    }


def clear_launch_outputs(stage: Path) -> None:
    for name in LAUNCH_OUTPUTS:
        path = stage / name
        if path.exists():
            path.unlink()


def stage_product(stage: Path, executable: Path, checkpoint: bytes | None) -> Path:
    staged = stage_scenario(stage, executable, checkpoint or v18_checkpoint("stardrifter"))
    if checkpoint is None:
        for name in ("CURRENT.LIN", "CURRENT.BAK"):
            path = stage / name
            if path.exists():
                path.unlink()
    clear_launch_outputs(stage)
    return staged


def wait_for_checkpoint(stage: Path, previous: tuple[int, int] | None = None,
                        timeout: float = 20.0) -> bytes:
    paths = (stage / "CURRENT.LIN", stage / "CURRENT.BAK")
    deadline = time.monotonic() + timeout
    stable: tuple[int, int, int, int] | None = None
    stable_count = 0
    while time.monotonic() < deadline:
        try:
            stats = tuple(path.stat() for path in paths)
            payloads = tuple(path.read_bytes() for path in paths)
        except (FileNotFoundError, OSError):
            stable = None
            stable_count = 0
            time.sleep(0.05)
            continue
        signature = tuple(value for item in stats for value in (item.st_size, item.st_mtime_ns))
        changed = previous is None or all(
            item.st_mtime_ns > old for item, old in zip(stats, previous)
        )
        if (
            changed
            and all(item.st_size == CHECKPOINT_BYTES for item in stats)
            and payloads[0] == payloads[1]
            and signature == stable
        ):
            stable_count += 1
        else:
            stable = signature
            stable_count = 1
        if stable_count >= 3:
            decode_checkpoint(payloads[0])
            return payloads[0]
        time.sleep(0.10)
    raise AcceptanceBlocked("checkpoint primary and backup did not settle identically")


def checkpoint_mtimes(stage: Path) -> tuple[int, int] | None:
    paths = (stage / "CURRENT.LIN", stage / "CURRENT.BAK")
    try:
        return tuple(path.stat().st_mtime_ns for path in paths)  # type: ignore[return-value]
    except FileNotFoundError:
        return None


def wait_for_requested_shutdown(process: PrivateDesktopProcess, stage: Path,
                                timeout: float = 20.0) -> dict[str, Any]:
    profile_path = stage / "game-profile-out.bin"
    checkpoint_paths = (stage / "CURRENT.LIN", stage / "CURRENT.BAK")
    deadline = time.monotonic() + timeout
    stable: tuple[int, ...] | None = None
    stable_count = 0
    while time.monotonic() < deadline:
        return_code = process.poll()
        if return_code not in (None, 0):
            raise AcceptanceFailure(f"game host exited with code {return_code}")
        try:
            profile_stat = profile_path.stat()
            checkpoint_stats = tuple(path.stat() for path in checkpoint_paths)
            profile_data = profile_path.read_bytes()
            checkpoints = tuple(path.read_bytes() for path in checkpoint_paths)
        except (FileNotFoundError, OSError):
            stable = None
            stable_count = 0
            time.sleep(0.05)
            continue
        signature = (
            profile_stat.st_size,
            profile_stat.st_mtime_ns,
            *(value for item in checkpoint_stats for value in (item.st_size, item.st_mtime_ns)),
        )
        valid = (
            profile_stat.st_size == PROFILE_UNITS * 4
            and all(item.st_size == CHECKPOINT_BYTES for item in checkpoint_stats)
            and checkpoints[0] == checkpoints[1]
            and process.main_window_handle() is None
        )
        if valid and signature == stable:
            stable_count += 1
        else:
            stable = signature
            stable_count = 1
        if valid and stable_count >= 3:
            return {
                "host_exited_naturally": process.poll() == 0,
                "profile": decode_profile(profile_data),
                "checkpoint": decode_checkpoint(checkpoints[0]),
                "checkpoint_sha256": file_sha256(checkpoint_paths[0]),
            }
        time.sleep(0.10)
    raise AcceptanceBlocked(
        "game did not complete terminal profile, checkpoint save, and window teardown"
    )


def double_from_words(low: int, high: int) -> float:
    return struct.unpack("<d", struct.pack("<II", low & 0xFFFFFFFF, high & 0xFFFFFFFF))[0]


def current_star(state: ControlState) -> tuple[float, float, float]:
    return (
        double_from_words(state["current_x_low"], state["current_x_high"]),
        double_from_words(state["current_y_low"], state["current_y_high"]),
        double_from_words(state["current_z_low"], state["current_z_high"]),
    )


def validate_bmp(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    require(len(data) == 256054, f"{path.name} is {len(data)} bytes, expected 256054")
    require(data[:2] == b"BM", f"{path.name} is not a BMP")
    file_size, pixel_offset = struct.unpack_from("<IxxxxI", data, 2)
    dib_size, width, height, planes, bpp, compression, image_size = struct.unpack_from(
        "<IiiHHII", data, 14
    )
    require(
        (file_size, pixel_offset, dib_size, width, height, planes, bpp,
         compression, image_size)
        == (256054, 54, 40, 320, 200, 1, 32, 0, 256000),
        f"{path.name} has a malformed 320x200 32-bit BMP header",
    )
    return {
        "path": str(path),
        "bytes": len(data),
        "width": width,
        "height": height,
        "bits_per_pixel": bpp,
        "sha256": file_sha256(path),
    }


def bmp_region_rgb(path: Path, box: tuple[int, int, int, int]) -> bytes:
    data = path.read_bytes()
    _dib_size, width, height, _planes, _bpp, _compression, _image_size = (
        struct.unpack_from("<IiiHHII", data, 14)
    )
    x0, y0, x1, y1 = box
    require(
        width == 320 and height == 200 and 0 <= x0 < x1 <= width
        and 0 <= y0 < y1 <= height,
        f"invalid BMP oracle region {box} for {path.name}",
    )
    region = bytearray()
    for y in range(y0, y1):
        offset = 54 + (height - 1 - y) * width * 4 + x0 * 4
        for _x in range(x0, x1):
            blue, green, red, _reserved = data[offset:offset + 4]
            region.extend((red, green, blue))
            offset += 4
    return bytes(region)


def validate_menu_visual(label: str, path: Path) -> dict[str, Any] | None:
    mask = MENU_MASK_BASELINES.get(label)
    if mask is not None:
        box, rgb, expected = mask
        pixels = bmp_region_rgb(path, box)
        matched = bytes(
            pixels[offset:offset + 3] == bytes(rgb)
            for offset in range(0, len(pixels), 3)
        )
        actual = hashlib.sha256(matched).hexdigest()
        require(actual == expected, f"{label} glyph/layout mask changed")
        return {
            "mode": "exact-colour-mask",
            "box": list(box),
            "rgb": list(rgb),
            "matching_pixels": sum(matched),
            "sha256": actual,
            "expected_sha256": expected,
        }

    region = MENU_REGION_BASELINES.get(label)
    if region is not None:
        box, expected = region
        actual = hashlib.sha256(bmp_region_rgb(path, box)).hexdigest()
        require(actual == expected, f"{label} fixed raster region changed")
        return {
            "mode": "exact-rgb-region",
            "box": list(box),
            "sha256": actual,
            "expected_sha256": expected,
        }
    return None


class PhaseReport:
    def __init__(self, phase: str, stage: Path, executable: Path, *, force: bool) -> None:
        self.phase = phase
        self.stage = stage
        self.path = stage / "acceptance-report.json"
        if self.path.is_file() and not force:
            retained = json.loads(self.path.read_text(encoding="utf-8"))
            if retained.get("status") in {"PASS", "FAIL", "BLOCKED"}:
                raise FileExistsError(
                    f"retained {retained.get('status')} {phase} evidence exists: {self.path}; "
                    "use --force to replace it"
                )
        stage.mkdir(parents=True, exist_ok=True)
        self.started = time.monotonic()
        self.data: dict[str, Any] = {
            "schema": REPORT_SCHEMA,
            "phase": phase,
            "status": "RUNNING",
            "started_utc": utc_now(),
            "command": [],
            "provenance": {
                "executable_path": str(executable.resolve()),
                "executable_sha256": file_sha256(executable),
                "game_source_sha256": file_sha256(GAME_SOURCE),
                "tracked_guide_sha256": file_sha256(TRACKED_GUIDE),
                "tracked_starmap_sha256": file_sha256(TRACKED_STARMAP),
            },
            "launches": [],
            "events": [],
            "transitions": [],
            "captures": [],
            "checks": [],
        }
        self.flush()

    def flush(self) -> None:
        self.path.write_text(json.dumps(self.data, indent=2) + "\n", encoding="utf-8")

    def event(self, kind: str, **details: Any) -> None:
        self.data["events"].append({
            "elapsed_seconds": round(time.monotonic() - self.started, 6),
            "kind": kind,
            **details,
        })
        self.flush()

    def transition(self, label: str, state: ControlState) -> None:
        print(f"  STATE {label}: sequence {state['sequence']}")
        self.data["transitions"].append({"label": label, "state": exact_state(state)})
        self.flush()

    def check(self, label: str, evidence: Any = True) -> None:
        print(f"  PASS {label}")
        self.data["checks"].append({"label": label, "evidence": evidence})
        self.flush()

    def launch(self, arguments: tuple[str, ...], rectangle: tuple[int, int, int, int],
               stage: Path) -> None:
        command = [str(stage / "Noctis-IV.exe"), *arguments]
        self.data["command"] = command
        self.data["launches"].append({
            "command": command,
            "window_rectangle": rectangle,
            "private_desktop": True,
        })
        self.flush()

    def capture(self, label: str, evidence: dict[str, Any]) -> None:
        expected = MENU_BASELINES.get(label)
        visual_oracle = validate_menu_visual(label, Path(evidence["path"]))
        evidence["label"] = label
        evidence["expected_sha256"] = expected
        evidence["exact_hash_pinned"] = expected is not None
        evidence["visual_oracle_pinned"] = expected is not None or visual_oracle is not None
        evidence["visual_oracle"] = visual_oracle
        if expected is not None:
            require(evidence["sha256"] == expected, f"{label} raster hash changed")
        self.data["captures"].append(evidence)
        self.flush()

    def finish(self, status: str, *, error: BaseException | None = None) -> None:
        self.data["status"] = status
        self.data["finished_utc"] = utc_now()
        self.data["elapsed_seconds"] = round(time.monotonic() - self.started, 3)
        if error is not None:
            self.data["error"] = {"type": type(error).__name__, "message": str(error)}
        self.data["provenance"]["tracked_guide_sha256_after"] = file_sha256(TRACKED_GUIDE)
        self.data["provenance"]["tracked_starmap_sha256_after"] = file_sha256(TRACKED_STARMAP)
        self.flush()


class InputDriver:
    def __init__(self, process: PrivateDesktopProcess, handle: int, stage: Path,
                 report: PhaseReport) -> None:
        self.process = process
        self.handle = handle
        self.stage = stage
        self.report = report
        self.reader = TraceReader(stage / TRACE_NAME)
        self._write_control_pointer(1, 25, False)

    @property
    def state(self) -> ControlState:
        if self.reader.last is None:
            return self.wait(0, lambda _state: True, "initial control state")
        return self.reader.last

    def _progress(self, description: str) -> Callable[[float, ControlState | None], None]:
        def show(remaining: float, state: ControlState | None) -> None:
            sequence = state["sequence"] if state is not None else 0
            print(f"  WAIT {description}: sequence {sequence}, {remaining:.0f}s remain")
        return show

    def wait(self, after: int, predicate: Callable[[ControlState], bool],
             description: str, timeout: float = INPUT_TIMEOUT,
             *, allow_exit: bool = False) -> ControlState:
        try:
            state = self.reader.wait(
                self.process, after, predicate, description, timeout,
                allow_exit=allow_exit, progress=self._progress(description),
            )
        except TimeoutError as error:
            raise AcceptanceBlocked(str(error)) from error
        return state

    def next(self, description: str = "next control state") -> ControlState:
        return self.wait(self.state["sequence"] if self.reader.last else 0,
                         lambda _state: True, description)

    def tap_key(self, key: int, description: str,
                predicate: Callable[[ControlState], bool] | None = None,
                timeout: float = INPUT_TIMEOUT, hold: float = 0.08) -> ControlState:
        self.reader.drain()
        before = self.state["sequence"]
        self.process.post_key(self.handle, key, True)
        try:
            state = self.wait(
                before, predicate or (lambda _state: True), description,
                timeout, allow_exit=key == VK_ESCAPE,
            )
            if predicate is None and hold > 0:
                time.sleep(hold)
        finally:
            if self.process.poll() is None:
                try:
                    self.process.post_key(self.handle, key, False)
                except OSError:
                    if key != VK_ESCAPE and self.process.poll() is None:
                        raise
        self.report.event("key", virtual_key=key, description=description,
                          before_sequence=before, after_sequence=state["sequence"])
        return state

    def char(self, character: str | int, description: str,
             predicate: Callable[[ControlState], bool] | None = None,
             timeout: float = INPUT_TIMEOUT) -> ControlState:
        self.reader.drain()
        before = self.state["sequence"]
        ascii_value = ord(character) if isinstance(character, str) else character
        self.process.post_char(self.handle, character)
        state = self.wait(
            before,
            (lambda value: value["ascii"] == ascii_value)
            if predicate is None else predicate,
            description,
            timeout,
        )
        self.report.event(
            "character", ascii=ascii_value, description=description,
            before_sequence=before, after_sequence=state["sequence"],
        )
        return state

    def hold_key(self, key: int, description: str,
                 predicate: Callable[[ControlState], bool],
                 timeout: float = INPUT_TIMEOUT) -> ControlState:
        self.reader.drain()
        before = self.state["sequence"]
        after = before
        deadline = time.monotonic() + timeout
        reached: ControlState | None = None
        last_timeout: TimeoutError | None = None
        try:
            while reached is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise AcceptanceBlocked(str(last_timeout) if last_timeout else
                                            f"timed out waiting for {description}")
                # A posted letter key can occasionally arrive before the private
                # window has installed its next input sample. Repeating key-down
                # while it is meant to remain held is harmless and prevents one
                # missed message from consuming the entire journey timeout.
                self.process.post_key(self.handle, key, True)
                try:
                    reached = self.reader.wait(
                        self.process, after, predicate, description,
                        min(2.0, remaining),
                    )
                except TimeoutError as error:
                    last_timeout = error
                    if self.reader.last is not None:
                        after = self.reader.last["sequence"]
        finally:
            if self.process.poll() is None:
                self.process.post_key(self.handle, key, False)
        settled = self.wait(reached["sequence"], lambda _state: True,
                            f"{description} key release")
        self.report.event("held-key", virtual_key=key, description=description,
                          before_sequence=before, reached_sequence=reached["sequence"],
                          after_sequence=settled["sequence"])
        return reached

    def command(self, text: str, timeout: float = 180.0) -> ControlState:
        require(text and all(32 <= ord(char) <= 126 for char in text),
                f"command is not printable ASCII: {text!r}")
        opened = self.char("g", "open GOES console", lambda state: state["console"] == 1)
        before = opened["sequence"]
        for character in text:
            ascii_value = ord(character)
            self.process.post_char(self.handle, character)
            before = self.wait(
                before,
                lambda state, expected=ascii_value: state["ascii"] == expected,
                f"accept GOES character {character!r}",
            )["sequence"]
        self.process.post_char(self.handle, 9)
        result = self.wait(
            before,
            lambda state: state["console"] == 0,
            f"complete GOES command {text}",
            timeout,
        )
        self.report.event("goes-command", command=text, submit_ascii=9,
                          normalized_submit_ascii=13, before_sequence=opened["sequence"],
                          after_sequence=result["sequence"])
        return result

    def raw_tap_key(self, key: int, hold: float = 0.25) -> None:
        self.process.post_key(self.handle, key, True)
        time.sleep(hold)
        if self.process.poll() is None:
            self.process.post_key(self.handle, key, False)
        time.sleep(hold)

    def open_game_menu(self) -> int:
        for _attempt in range(3):
            self.settle_frames(2, "GAME menu pre-open")
            self.reader.drain()
            before = self.state["sequence"]
            self.raw_tap_key(VK_F10)
            paused = self.reader.drain()
            require(paused is not None, "GAME menu opener lost its control trace")
            time.sleep(0.60)
            after_pause = self.reader.drain()
            require(after_pause is not None, "GAME menu pause lost its control trace")
            if after_pause["sequence"] == paused["sequence"]:
                return before
        raise AcceptanceBlocked("F10 did not open and pause the shipping GAME menu")

    def invoke_game_option(self, index: int, description: str,
                           predicate: Callable[[ControlState], bool] | None = None,
                           timeout: float = INPUT_TIMEOUT) -> ControlState:
        require(0 <= index < 12, f"GAME menu index {index} is invalid")
        before = self.open_game_menu()
        for _row in range(index):
            self.raw_tap_key(VK_DOWN)
        self.raw_tap_key(VK_RETURN)
        state = self.wait(
            before, predicate or (lambda _state: True),
            f"invoke GAME row {index}: {description}", timeout,
        )
        self.report.event("game-menu-option", index=index, description=description,
                          before_sequence=before, after_sequence=state["sequence"],
                          input=[VK_F10, *([VK_DOWN] * index), VK_RETURN])
        return state

    def invoke_game_quit(self) -> None:
        before = self.open_game_menu()
        for _row in range(11):
            self.raw_tap_key(VK_DOWN)
        self.raw_tap_key(VK_RETURN)
        self.report.event(
            "game-menu-option", index=11, description="Save and quit",
            before_sequence=before, after_sequence=None,
            input=[VK_F10, *([VK_DOWN] * 11), VK_RETURN],
        )

    def _write_control_pointer(self, x: int, y: int, down: bool) -> None:
        require(0 <= x < 642 and 0 <= y < 426,
                f"control pointer coordinate is outside the game window: {x},{y}")
        path = self.stage / TRACE_POINTER_NAME
        path.write_bytes(struct.pack(
            "<5i", TRACE_POINTER_MAGIC, 1, x, y, int(down),
        ))

    def click_row(self, logical_y: int, key: int, description: str,
                  predicate: Callable[[ControlState], bool],
                  timeout: float = INPUT_TIMEOUT) -> ControlState:
        x = 1 + 160 * 2
        y = 25 + logical_y * 2
        self.reader.drain()
        before = self.state["sequence"]
        self._write_control_pointer(x, y, False)
        hovered = self.wait(
            before,
            lambda state: state["menu_key"] == key and (
                state["menu_hover"] != 0 or logical_y >= 168
            ),
            f"hover {description}",
            timeout,
        )
        self._write_control_pointer(x, y, True)
        pressed = self.wait(
            hovered["sequence"], predicate,
            f"press {description}", timeout,
        )
        self._write_control_pointer(x, y, False)
        result = self.wait(
            pressed["sequence"], predicate,
            f"release {description}", timeout,
        )
        self._write_control_pointer(1, 25, False)
        idle = self.wait(
            result["sequence"], predicate,
            f"reset pointer after {description}", timeout,
        )
        result = idle
        self.report.event(
            "mouse-row", description=description, client_x=x, client_y=y,
            logical_y=logical_y, menu_key=key, input_source="controltrace-pointer",
            before_sequence=before, hover_sequence=hovered["sequence"],
            pressed_sequence=pressed["sequence"], after_sequence=result["sequence"],
        )
        return result

    def settle_frames(self, count: int, description: str) -> ControlState:
        require(count > 0, "settle frame count must be positive")
        self.reader.drain()
        state = self.state
        for index in range(count):
            state = self.wait(
                state["sequence"], lambda _state: True,
                f"{description} settle frame {index + 1}/{count}",
            )
        return state

    def settle_visual(self, description: str) -> ControlState:
        self.reader.drain()
        state = self.state
        ready = lambda value: (
            value["notice_frames"] == 0
            and (value["info"] == 0 or value["info_scroll"] == 100)
        )
        if not ready(state):
            state = self.wait(
                state["sequence"], ready,
                f"{description} unobstructed visual state", timeout=INPUT_TIMEOUT,
            )
        return self.settle_frames(2, description)

    def snapshot(self, label: str, timeout: float = 20.0, *,
                 character: str = "m") -> Path:
        self.settle_visual(label)
        gallery = self.stage / "GALLERY"
        gallery.mkdir(exist_ok=True)
        before = {path.name for path in gallery.glob("*.BMP")}
        self.char(
            character,
            f"capture {label}",
            lambda value: value["notice_frames"] > 0,
        )
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            candidates = sorted(
                (path for path in gallery.glob("*.BMP") if path.name not in before),
                key=lambda path: path.name,
            )
            if candidates:
                evidence = validate_bmp(candidates[0])
                self.report.capture(label, evidence)
                print(f"  BMP {label}: {evidence['sha256']}")
                return candidates[0]
            if self.process.poll() not in (None, 0):
                raise AcceptanceFailure(f"game exited while capturing {label}")
            time.sleep(0.05)
        raise AcceptanceBlocked(f"no Gallery BMP appeared for {label}")

def open_driver(process: PrivateDesktopProcess, stage: Path, report: PhaseReport,
                arguments: tuple[str, ...]) -> InputDriver:
    handle, rectangle = wait_for_ready(process, stage, READINESS_TIMEOUT)
    report.launch(arguments, rectangle, stage)
    driver = InputDriver(process, handle, stage, report)
    opening = driver.state
    report.transition("launch-ready", opening)
    require(opening["fast_presentation"] == 1,
            "desktop launch did not retain the 60-Hz presentation default")
    report.check("desktop launch defaults to 60-Hz presentation", 1)
    return driver


def run_menus(report: PhaseReport, executable: Path) -> None:
    stage = report.stage
    staged = stage_product(stage, executable, v18_checkpoint("orbital"))
    arguments = (f"clock={CLOCK_SECONDS}", "controltrace", "profile")
    with PrivateDesktopProcess(staged, stage, arguments) as process:
        driver = open_driver(process, stage, report, arguments)
        require(driver.state["mode"] == 0 and driver.state["local_reached"] == 1,
                "menu fixture is not a reached orbital ship state")
        driver.snapshot("ship-main")
        driver.settle_visual("ship snapshot notice")

        state = driver.tap_key(VK_F1, "open About", lambda value: value["about"] == 1)
        report.transition("about-open", state)
        driver.snapshot("about")
        driver.tap_key(VK_F1, "close About", lambda value: value["about"] == 0)

        state = driver.tap_key(VK_F2, "open visual effects",
                               lambda value: value["graphics"] == 1)
        report.transition("graphics-open", state)
        driver.snapshot("visual-effects")
        original_lens = driver.state["lens_mode"]
        changed = driver.char(
            "f", "change visual effect lens_mode",
            lambda value: value["lens_mode"] != original_lens,
        )
        report.transition("graphics-lens_mode-changed", changed)
        for attempt in range(2):
            prior_lens = driver.state["lens_mode"]
            restored = driver.char(
                "f", f"cycle visual effect lens_mode toward original {attempt + 1}",
                lambda value, prior_lens=prior_lens: value["lens_mode"] != prior_lens,
            )
            if restored["lens_mode"] == original_lens:
                break
        require(driver.state["lens_mode"] == original_lens,
                "visual effect lens mode did not cycle back to its original state")
        for character, field in (("t", "draw_hud"), ("b", "seamless")):
            original = driver.state[field]
            changed = driver.char(
                character, f"change visual effect {field}",
                lambda value, field=field, original=original: value[field] != original,
            )
            report.transition(f"graphics-{field}-changed", changed)
            driver.char(
                character, f"restore visual effect {field}",
                lambda value, field=field, original=original: value[field] == original,
            )
        driver.tap_key(VK_F2, "close visual effects",
                       lambda value: value["graphics"] == 0)

        state = driver.tap_key(VK_F3, "open moviemaker",
                               lambda value: value["movie_view"] == 1)
        report.transition("moviemaker-open", state)
        driver.snapshot("moviemaker")
        driver.tap_key(VK_F3, "close moviemaker",
                       lambda value: value["movie_view"] == 0)

        state = driver.invoke_game_option(
            0, "Controls", lambda value: value["help"] == 1
        )
        report.transition("controls-open", state)
        driver.snapshot("controls")
        driver.tap_key(VK_F9, "close Controls", lambda value: value["help"] == 0)

        state = driver.invoke_game_option(
            1, "GOES console", lambda value: value["console"] == 1
        )
        report.transition("goes-open", state)
        driver.snapshot("goes-console", character="*")
        driver.tap_key(VK_ESCAPE, "close GOES console",
                       lambda value: value["console"] == 0 and value["quit"] == 0)

        before_save = checkpoint_mtimes(stage)
        driver.invoke_game_option(2, "Save checkpoint")
        saved = wait_for_checkpoint(stage, before_save)
        report.check("GAME Save checkpoint writes identical v18 primary and backup",
                     file_sha256(stage / "CURRENT.LIN"))
        before_load_hash = file_sha256(stage / "CURRENT.LIN")
        state = driver.invoke_game_option(3, "Load checkpoint")
        require(file_sha256(stage / "CURRENT.LIN") == before_load_hash,
                "GAME Load checkpoint changed the saved checkpoint")
        report.transition("checkpoint-loaded", state)
        report.check("GAME Load checkpoint preserves the staged save", before_load_hash)

        original_fps = driver.state["fps_show"]
        changed = driver.invoke_game_option(
            4, "Toggle FPS counter",
            lambda value: value["fps_show"] != original_fps,
        )
        report.transition("fps-counter-changed", changed)
        driver.invoke_game_option(
            4, "restore FPS counter",
            lambda value: value["fps_show"] == original_fps,
        )

        changed = driver.invoke_game_option(
            5, "Toggle 60 Hz", lambda value: value["fast_presentation"] == 0
        )
        report.transition("desktop-presentation-18hz", changed)
        restored = driver.tap_key(
            VK_F5, "restore desktop 60 Hz", lambda value: value["fast_presentation"] == 1
        )
        report.transition("desktop-presentation-restored", restored)

        driver.invoke_game_option(6, "Toggle music")
        report.check("GAME music option remains invokable through the shipping menu")

        state = driver.invoke_game_option(
            7, "Visual effects", lambda value: value["graphics"] == 1
        )
        report.transition("visual-effects-menu-open", state)
        driver.char("x", "close menu-opened visual effects",
                    lambda value: value["graphics"] == 0)

        state = driver.invoke_game_option(
            8, "Flight control", lambda value: value["fcs_open"] == 1
        )
        report.transition("fcs-open", state)
        driver.snapshot("flight-control")
        state = driver.click_row(
            41, 54, "FCS remote target browser",
            lambda value: value["device"] == 6 and value["browser_origin"] == 2,
        )
        report.transition("target-browser-from-fcs", state)
        driver.snapshot("target-browser")
        driver.click_row(
            129, 55, "target browser next",
            lambda value: value["device"] == 6 and value["browser_valid"] == 1,
        )
        state = driver.click_row(
            173, 57, "target browser back to FCS",
            lambda value: value["fcs_open"] == 1 and value["device"] == 0,
        )
        report.transition("target-browser-returned-fcs", state)
        driver.click_row(
            180, 53, "FCS back",
            lambda value: value["fcs_open"] == 0 and value["device_access"] == 0,
        )

        state = driver.invoke_game_option(
            9, "Onboard devices", lambda value: value["device"] == 1
        )
        report.transition("devices-root", state)
        driver.snapshot("devices-root")
        for row, page, label in (
            (41, 2, "navigation-devices"),
            (63, 3, "miscellaneous-devices"),
            (85, 4, "cartography-devices"),
            (107, 5, "emergency-devices"),
        ):
            state = driver.click_row(
                row, 52 + page, f"open {label}",
                lambda value, page=page: value["device"] == page,
            )
            report.transition(f"{label}-open", state)
            driver.snapshot(label)
            if page == 2:
                original = driver.state["amplifier"]
                driver.click_row(
                    41, 54, "toggle gravitational amplifier",
                    lambda value, original=original: value["amplifier"] != original,
                )
                driver.click_row(
                    41, 54, "restore gravitational amplifier",
                    lambda value, original=original: value["amplifier"] == original,
                )
            elif page == 3:
                original = driver.state["interior_light"]
                driver.click_row(
                    41, 54, "toggle interior lights",
                    lambda value, original=original: value["interior_light"] != original,
                )
                driver.click_row(
                    41, 54, "restore interior lights",
                    lambda value, original=original: value["interior_light"] == original,
                )
            elif page == 4:
                browser = driver.click_row(
                    85, 56, "cartography next target",
                    lambda value: value["device"] == 6 and value["browser_origin"] == 1,
                )
                report.transition("target-browser-from-cartography", browser)
                driver.click_row(
                    173, 57, "target browser back to cartography",
                    lambda value: value["device"] == 4,
                )
            else:
                before_reset = driver.state["reset_count"]
                reset = driver.click_row(
                    41, 54, "start emergency reset",
                    lambda value, before_reset=before_reset: value["reset_count"] > before_reset,
                )
                report.transition("emergency-reset-started", reset)
            state = driver.click_row(
                180, 82, f"back from {label}",
                lambda value: value["device"] == 1,
            )
            report.transition(f"{label}-returned", state)
        driver.click_row(
            180, 82, "close onboard devices",
            lambda value: value["device"] == 0 and value["device_access"] == 0,
        )
        reset_finished = driver.wait(
            driver.state["sequence"],
            lambda value: value["reset_count"] == 0,
            "complete emergency reset",
            timeout=60.0,
        )
        report.transition("emergency-reset-completed", reset_finished)

        state = driver.invoke_game_option(
            10, "Preferences", lambda value: value["preferences"] == 1
        )
        report.transition("preferences-open", state)
        driver.snapshot("preferences")
        for row, field, label in (
            (41, "autoscreen_off", "automatic computer deactivation"),
            (63, "reverse_controls", "reverse controls"),
            (85, "menus_always_on", "menus always on"),
            (107, "depolarize", "depolarized hull"),
        ):
            original = driver.state[field]
            driver.click_row(
                row, 54 + ((row - 41) // 22), f"toggle {label}",
                lambda value, field=field, original=original: value[field] != original,
            )
            driver.click_row(
                row, 54 + ((row - 41) // 22), f"restore {label}",
                lambda value, field=field, original=original: value[field] == original,
            )
        driver.click_row(
            180, 88, "close Preferences",
            lambda value: value["preferences"] == 0 and value["device_access"] == 0,
        )

        for page in (1, 2, 3):
            state = driver.char("i", f"open data sheet {page}",
                                lambda value, page=page: value["info"] == page)
            report.transition(f"data-sheet-{page}", state)
            driver.snapshot(f"data-sheet-{page}")
        driver.char("i", "close data sheets", lambda value: value["info"] == 0)

        state = driver.tap_key(
            VK_F7, "restore orbital state for landing selector",
            lambda value: value["local_reached"] == 1 and value["star_reached"] == 1,
        )
        report.transition("landing-selector-orbit-restored", state)
        state = driver.char(
            "l", "open landing selector", lambda value: value["landing_select"] == 1
        )
        report.transition("landing-selector-open", state)
        driver.snapshot("landing-selector")
        longitude = state["landing_longitude"]
        moved = driver.tap_key(
            VK_RIGHT, "move landing longitude",
            lambda value: value["landing_longitude"] != longitude,
        )
        report.transition("landing-selector-moved", moved)
        driver.tap_key(
            VK_ESCAPE, "cancel landing selector",
            lambda value: value["landing_select"] == 0
            and value["landing_pending"] == 0
            and value["quit"] == 0,
        )

        driver.invoke_game_quit()
        shutdown = wait_for_requested_shutdown(process, stage)
        report.data["shutdown"] = shutdown
        report.check("GAME Save and quit completes clean v18 persistence",
                     shutdown["checkpoint_sha256"])

    require(saved == (stage / "CURRENT.LIN").read_bytes() or
            decode_checkpoint((stage / "CURRENT.LIN").read_bytes())["schema"] == 18,
            "menu phase did not finish with a valid v18 checkpoint")


def find_landable(driver: InputDriver, excluded: set[tuple[tuple[int, int, int], int]],
                  timeout: float = 120.0) -> ControlState | None:
    deadline = time.monotonic() + timeout
    seen: set[int] = set()
    while time.monotonic() < deadline:
        state = driver.state
        target = (state["target_x"], state["target_y"], state["target_z"])
        identity = (target, state["planet"])
        if (
            state["planet"] >= 0
            and state["planet"] < state["system_body_count"]
            and state["planet_type"] in LANDABLE_TYPES
            and identity not in excluded
        ):
            return state
        if state["planet"] in seen and len(seen) >= max(1, state["system_body_count"]):
            return None
        seen.add(state["planet"])
        driver.char("]", "cycle generated body")
    return None


def wait_star_reached(driver: InputDriver, after: int, label: str) -> ControlState:
    state = driver.wait(
        after,
        lambda value: value["star_reached"] == 1
        and value["star_drive"] == 0
        and value["drive_status"] == 6,
        label,
        JOURNEY_TIMEOUT,
    )
    current = current_star(state)
    require(all(math.isfinite(value) for value in current),
            "current star contains non-finite data")
    return state


def travel_to_next_star(driver: InputDriver, report: PhaseReport,
                        label: str) -> ControlState:
    previous_target = (
        driver.state["target_x"], driver.state["target_y"],
        driver.state["target_z"],
    )
    command = driver.command("NEXT")
    retargeted = driver.wait(
        command["sequence"],
        lambda value: (
            value["target_x"], value["target_y"], value["target_z"]
        ) != previous_target and value["star_drive"] == 1,
        f"{label} retarget and Vimana start",
        120.0,
    )
    report.transition(f"{label}-vimana-started", retargeted)
    arrived = wait_star_reached(
        driver, retargeted["sequence"], f"reach {label} Vimana target"
    )
    report.transition(f"{label}-vimana-reached", arrived)
    return arrived


def find_landable_system(
    driver: InputDriver,
    report: PhaseReport,
    excluded: set[tuple[tuple[int, int, int], int]],
    label: str,
    *,
    max_next_systems: int = 64,
) -> ControlState | None:
    """Search the current and subsequent generated systems for a body."""
    visited_targets: set[tuple[int, int, int]] = set()
    for attempt in range(max_next_systems + 1):
        target = (
            driver.state["target_x"], driver.state["target_y"],
            driver.state["target_z"],
        )
        if target in visited_targets:
            return None
        visited_targets.add(target)
        selected = find_landable(driver, excluded)
        if selected is not None:
            return selected
        if attempt < max_next_systems:
            travel_to_next_star(driver, report, f"{label}-system-{attempt + 1}")
    return None


def land_selected_body(driver: InputDriver, report: PhaseReport,
                       label: str) -> ControlState:
    selected = driver.state
    planet = selected["planet"]
    require(selected["planet_type"] in LANDABLE_TYPES,
            f"{label} selected non-landable type {selected['planet_type']}")
    approach = driver.char(
        "l", f"start {label} fine approach",
        lambda value: value["local_active"] == 1
        and value["local_target"] == planet,
    )
    report.transition(f"{label}-approach-started", approach)
    reached = driver.wait(
        approach["sequence"],
        lambda value: value["local_reached"] == 1
        and value["local_approaching"] == 0,
        f"complete {label} fine approach",
        JOURNEY_TIMEOUT,
    )
    report.transition(f"{label}-approach-reached", reached)
    selector = driver.char(
        "l", f"open {label} landing selector",
        lambda value: value["landing_select"] == 1,
    )
    report.transition(f"{label}-landing-selector", selector)
    driver.snapshot(f"{label}-landing-selector")
    descent = driver.char(
        "l", f"confirm {label} landing",
        lambda value: value["mode"] == 1 and value["capsule_state"] == 1,
        60.0,
    )
    report.transition(f"{label}-descent-started", descent)
    settled = driver.wait(
        descent["sequence"],
        lambda value: value["mode"] == 1
        and value["landed"] == 1
        and value["capsule_state"] == 0,
        f"complete natural {label} capsule descent",
        JOURNEY_TIMEOUT,
    )
    require(settled["planet"] == planet, f"{label} descent changed selected body")
    report.transition(f"{label}-surface-settled", settled)
    driver.snapshot(f"{label}-surface")
    return settled


def return_saved_excursion(driver: InputDriver, report: PhaseReport,
                           label: str) -> ControlState:
    returning = driver.hold_key(
        VK_S, f"walk saved route back to capsule on {label}",
        lambda value: value["capsule_state"] == 2,
        180.0,
    )
    report.transition(f"{label}-capsule-sealing", returning)
    ship = driver.wait(
        returning["sequence"],
        lambda value: value["mode"] == 0
        and value["capsule_state"] == 0
        and value["capsule_return_pending"] == 0,
        f"complete {label} capsule ascent and ship handoff",
        JOURNEY_TIMEOUT,
    )
    report.transition(f"{label}-ship-return", ship)
    driver.snapshot(f"{label}-ship-return")
    return ship


def surface_excursion_and_return(driver: InputDriver, report: PhaseReport,
                                 label: str, *, persist: bool) -> ControlState:
    settled = driver.state
    beta = settled["beta"]
    looked = driver.tap_key(
        VK_LEFT, f"look on {label}", lambda value: value["beta"] != beta
    )
    report.transition(f"{label}-looked", looked)
    origin = (looked["x"], looked["z"])
    excursion = driver.hold_key(
        VK_W, f"walk away on {label}",
        lambda value: value["capsule_recover"] == 1
        and (value["x"], value["z"]) != origin,
        180.0,
    )
    report.transition(f"{label}-capsule-recovery-armed", excursion)
    driver.snapshot(f"{label}-excursion")
    if persist:
        before = checkpoint_mtimes(driver.stage)
        driver.tap_key(VK_F6, f"save {label} surface checkpoint")
        payload = wait_for_checkpoint(driver.stage, before)
        checkpoint = decode_checkpoint(payload)
        require(checkpoint["mode"] == 1 and checkpoint["landed"] == 1,
                f"{label} surface save is not a settled landed checkpoint")
        report.data.setdefault("checkpoints", []).append({
            "label": f"{label}-surface",
            "sha256": file_sha256(driver.stage / "CURRENT.LIN"),
            "decoded": checkpoint,
        })
        report.check(f"{label} surface state saved as v18", checkpoint)
    returning = driver.hold_key(
        VK_S, f"walk back to capsule on {label}",
        lambda value: value["capsule_state"] == 2,
        180.0,
    )
    report.transition(f"{label}-capsule-sealing", returning)
    ship = driver.wait(
        returning["sequence"],
        lambda value: value["mode"] == 0
        and value["capsule_state"] == 0
        and value["capsule_return_pending"] == 0,
        f"complete {label} capsule ascent and ship handoff",
        JOURNEY_TIMEOUT,
    )
    report.transition(f"{label}-ship-return", ship)
    driver.snapshot(f"{label}-ship-return")
    return ship


def request_quit(driver: InputDriver, report: PhaseReport,
                 process: PrivateDesktopProcess, label: str) -> dict[str, Any]:
    quitting = driver.tap_key(
        VK_ESCAPE, f"quit after {label}", lambda value: value["quit"] == 1,
        INPUT_TIMEOUT,
    )
    report.transition(f"{label}-quit-requested", quitting)
    shutdown = wait_for_requested_shutdown(process, driver.stage)
    report.data.setdefault("shutdowns", []).append({"label": label, **shutdown})
    report.flush()
    return shutdown


def run_journey(report: PhaseReport, executable: Path) -> None:
    stage = report.stage
    staged = stage_product(stage, executable, None)
    arguments = (f"clock={CLOCK_SECONDS}", "controltrace", "profile")
    first_identity: tuple[tuple[int, int, int], int]
    first_body_type: int
    first_system_body_count: int
    saved_surface: dict[str, Any]

    with PrivateDesktopProcess(staged, stage, arguments) as process:
        driver = open_driver(process, stage, report, arguments)
        require(not (stage / "CURRENT.LIN").exists() and not (stage / "CURRENT.BAK").exists(),
                "fresh journey unexpectedly started with a checkpoint")
        calibrated = wait_star_reached(driver, driver.state["sequence"],
                                       "complete fresh Vimana calibration")
        report.transition("fresh-vimana-calibrated", calibrated)
        driver.snapshot("fresh-vimana-calibrated")
        opening_target = (calibrated["target_x"], calibrated["target_y"], calibrated["target_z"])
        arrived = travel_to_next_star(driver, report, "next")
        require(
            (arrived["target_x"], arrived["target_y"], arrived["target_z"])
            != opening_target,
            "NEXT did not leave the opening star",
        )
        selected = find_landable_system(
            driver, report, set(), "first-landable"
        )
        if selected is None:
            raise AcceptanceBlocked("NEXT route exposes no landable generated body")
        report.transition("first-body-selected", selected)
        first_identity = (
            (selected["target_x"], selected["target_y"], selected["target_z"]),
            selected["planet"],
        )
        first_body_type = selected["planet_type"]
        first_system_body_count = selected["system_body_count"]
        land_selected_body(driver, report, "first-body")
        settled = driver.state
        beta = settled["beta"]
        looked = driver.tap_key(VK_LEFT, "look on first body",
                                 lambda value: value["beta"] != beta)
        origin = (looked["x"], looked["z"])
        excursion = driver.hold_key(
            VK_W, "walk away on first body",
            lambda value: value["capsule_recover"] == 1
            and (value["x"], value["z"]) != origin,
            180.0,
        )
        report.transition("first-body-capsule-recovery-armed", excursion)
        driver.snapshot("first-body-excursion")
        before = checkpoint_mtimes(stage)
        driver.tap_key(VK_F6, "save first-body surface checkpoint")
        payload = wait_for_checkpoint(stage, before)
        saved_surface = decode_checkpoint(payload)
        require(saved_surface["mode"] == 1 and saved_surface["landed"] == 1,
                "first-body checkpoint is not settled on the surface")
        report.data.setdefault("checkpoints", []).append({
            "label": "first-body-surface",
            "sha256": file_sha256(stage / "CURRENT.LIN"),
            "decoded": saved_surface,
        })
        report.flush()
        request_quit(driver, report, process, "first-body-surface-save")

    clear_launch_outputs(stage)
    with PrivateDesktopProcess(staged, stage, arguments) as process:
        driver = open_driver(process, stage, report, arguments)
        resumed = driver.state
        require(
            resumed["mode"] == 1
            and resumed["landed"] == 1
            and resumed["planet"] == saved_surface["planet"]
            and resumed["planet_type"] == first_body_type
            and resumed["system_body_count"] == first_system_body_count
            and resumed["local_active"] == saved_surface["local_active"] == 1
            and resumed["local_target"] == saved_surface["local_target"]
            and resumed["local_reached"] == saved_surface["local_reached"] == 1
            and (resumed["x"], resumed["z"]) == (saved_surface["x"], saved_surface["z"]),
            "relaunch did not resume the complete first-body surface state",
        )
        rearmed = driver.wait(
            resumed["sequence"] - 1,
            lambda value: value["capsule_recover"] == 1,
            "re-arm capsule recovery after surface reload",
            60.0,
        )
        report.transition("first-body-surface-reloaded", rearmed)
        ship = return_saved_excursion(driver, report, "first-body-reload")

        selected = find_landable_system(
            driver, report, {first_identity}, "second-landable"
        )
        if selected is None:
            raise AcceptanceBlocked("no distinct second landable body was generated")
        report.transition("second-body-selected", selected)
        second_identity = (
            (selected["target_x"], selected["target_y"], selected["target_z"]),
            selected["planet"],
        )
        require(second_identity != first_identity, "second body repeats first body identity")
        land_selected_body(driver, report, "second-body")
        surface_excursion_and_return(driver, report, "second-body", persist=False)
        before = checkpoint_mtimes(stage)
        driver.tap_key(VK_F6, "save final ship checkpoint")
        payload = wait_for_checkpoint(stage, before)
        final_saved = decode_checkpoint(payload)
        require(final_saved["mode"] == 0 and final_saved["landed"] == 0,
                "final checkpoint is not aboard the Stardrifter")
        report.data.setdefault("checkpoints", []).append({
            "label": "final-ship",
            "sha256": file_sha256(stage / "CURRENT.LIN"),
            "decoded": final_saved,
        })
        report.flush()
        request_quit(driver, report, process, "second-body-return")

    clear_launch_outputs(stage)
    with PrivateDesktopProcess(staged, stage, arguments) as process:
        driver = open_driver(process, stage, report, arguments)
        final = driver.state
        require(
            final["mode"] == 0
            and final["landed"] == 0
            and final["planet"] == final_saved["planet"],
            "final relaunch did not resume aboard the Stardrifter",
        )
        report.transition("final-ship-reloaded", final)
        request_quit(driver, report, process, "final-reload-proof")
    report.check("fresh two-body journey, persistence, and capsule returns completed")


def parse_starmap(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    if len(data) < 4 or (len(data) - 4) % STARMAP_RECORD_BYTES:
        raise ValueError(f"malformed STARMAP.BIN length {len(data)}")
    boundary = struct.unpack_from("<I", data)[0]
    if not 4 <= boundary <= len(data) or (boundary - 4) % STARMAP_RECORD_BYTES:
        raise ValueError(f"malformed STARMAP.BIN boundary {boundary}")
    records = []
    for offset in range(4, len(data), STARMAP_RECORD_BYTES):
        raw = data[offset:offset + STARMAP_RECORD_BYTES]
        label = raw[8:28].decode("latin-1").rstrip(" \0")
        records.append({
            "offset": offset,
            "raw": raw,
            "identity_raw": raw[:8],
            "identity": struct.unpack_from("<d", raw)[0],
            "label": label,
            "kind": chr(raw[29]),
            "code": int(raw[30:32]),
            "consolidated": offset < boundary,
        })
    return {"bytes": data, "boundary": boundary, "records": records}


def parse_guide(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    if len(data) < 4 or (len(data) - 4) % GUIDE_RECORD_BYTES:
        raise ValueError(f"malformed GUIDE.BIN length {len(data)}")
    boundary = struct.unpack_from("<I", data)[0]
    if not 4 <= boundary <= len(data) or (boundary - 4) % GUIDE_RECORD_BYTES:
        raise ValueError(f"malformed GUIDE.BIN boundary {boundary}")
    records = []
    for offset in range(4, len(data), GUIDE_RECORD_BYTES):
        raw = data[offset:offset + GUIDE_RECORD_BYTES]
        message_raw = raw[8:]
        message = message_raw.split(b"\0", 1)[0].decode("latin-1").rstrip()
        records.append({
            "offset": offset,
            "raw": raw,
            "identity_raw": raw[:8],
            "identity": struct.unpack_from("<d", raw)[0],
            "message": message,
            "removed": raw[:8] == b"Removed:",
            "consolidated": offset < boundary,
        })
    return {"bytes": data, "boundary": boundary, "records": records}


def subject_records(guide: dict[str, Any], identity_raw: bytes) -> list[dict[str, Any]]:
    return [record for record in guide["records"]
            if not record["removed"] and record["identity_raw"] == identity_raw]


def find_subject(starmap: dict[str, Any], name: str) -> dict[str, Any]:
    matches = [record for record in starmap["records"] if record["label"] == name]
    require(len(matches) == 1, f"STARMAP has {len(matches)} exact {name} records")
    return matches[0]


def encoded_guide_record(identity_raw: bytes, message: str) -> bytes:
    encoded = message.encode("ascii")
    require(len(identity_raw) == 8, "Guide identity is not eight bytes")
    require(0 < len(encoded) <= 76, "Guide fixture message does not fit 76 bytes")
    return identity_raw + encoded.ljust(76, b"\0")


def validate_print_export(path: Path, expected_message: str) -> dict[str, Any]:
    data = path.read_bytes()
    require(data and b"\r\n" in data, f"{path.name} has no CRLF text")
    require(data.replace(b"\r\n", b"").find(b"\n") < 0,
            f"{path.name} contains a bare line feed")
    lines = data.split(b"\r\n")
    require(all(len(line) <= 72 for line in lines),
            f"{path.name} contains a line wider than 72 bytes")
    require(expected_message.encode("ascii") in data,
            f"{path.name} omits the selected corrected message")
    require(b"- END OF DATA -" in data, f"{path.name} omits its footer")
    require(any(line == b"_" * 72 for line in lines),
            f"{path.name} omits its 72-column separator")
    return {
        "path": str(path),
        "bytes": len(data),
        "sha256": file_sha256(path),
        "line_count": len(lines),
        "maximum_columns": max(map(len, lines)),
    }


def parse_exchange_packet(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    require(data.startswith(b"STARMAP_"), "OUTBOX does not start with STARMAP_ framing")
    marker = -1
    for offset in range(8, len(data) - 7, STARMAP_RECORD_BYTES):
        if data[offset:offset + 8] == b"GUIDE___":
            marker = offset
            break
    require(marker >= 8, "OUTBOX omits aligned GUIDE___ framing")
    labels = data[8:marker]
    notes = data[marker + 8:]
    require(len(labels) % STARMAP_RECORD_BYTES == 0,
            "OUTBOX label payload is not 32-byte aligned")
    require(len(notes) % GUIDE_RECORD_BYTES == 0,
            "OUTBOX Guide payload is not 84-byte aligned")
    return {
        "bytes": len(data),
        "sha256": file_sha256(path),
        "starmap_records": [
            labels[offset:offset + STARMAP_RECORD_BYTES]
            for offset in range(0, len(labels), STARMAP_RECORD_BYTES)
        ],
        "guide_records": [
            notes[offset:offset + GUIDE_RECORD_BYTES]
            for offset in range(0, len(notes), GUIDE_RECORD_BYTES)
        ],
    }


def run_guide(report: PhaseReport, executable: Path) -> None:
    stage = report.stage
    staged = stage_product(stage, executable, v18_checkpoint("stardrifter"))
    arguments = (f"clock={CLOCK_SECONDS}", "freeze", "controltrace", "profile")
    initial_map = parse_starmap(stage / "STARMAP.BIN")
    subject = find_subject(initial_map, "SURICRASIA")
    identity_raw = subject["identity_raw"]
    initial_guide = parse_guide(stage / "GUIDE.BIN")
    initial_subject = subject_records(initial_guide, identity_raw)
    require(initial_subject, "shipped Guide has no SURICRASIA records")
    require(all(record["consolidated"] for record in initial_subject),
            "shipped Guide unexpectedly contains local SURICRASIA records")
    initial_guide_hash = file_sha256(stage / "GUIDE.BIN")
    initial_map_hash = file_sha256(stage / "STARMAP.BIN")
    report.data["guide_fixture"] = {
        "initial_guide_sha256": initial_guide_hash,
        "initial_starmap_sha256": initial_map_hash,
        "guide_bytes": len(initial_guide["bytes"]),
        "guide_records": len(initial_guide["records"]),
        "guide_boundary": initial_guide["boundary"],
        "suricrasia_records": len(initial_subject),
        "suricrasia_identity_hex": identity_raw.hex(),
    }
    report.flush()

    original_note = "V1 PRIVATE DESKTOP ACCEPTANCE ORIGINAL"
    corrected_note = "V1 PRIVATE DESKTOP ACCEPTANCE CORRECTED"
    deleted_note = "V1 PRIVATE DESKTOP ACCEPTANCE DELETE"

    with PrivateDesktopProcess(staged, stage, arguments) as process:
        driver = open_driver(process, stage, report, arguments)
        require(driver.state["mode"] == 0, "Guide fixture did not start aboard ship")
        driver.command("CAT SURICRASIA:1..2")
        require(file_sha256(stage / "GUIDE.BIN") == initial_guide_hash,
                "CAT changed GUIDE.BIN")
        report.check("CAT reads protected consolidated SURICRASIA records without mutation")

        driver.command("REP SURICRASIA:1:PROTECTED ACCEPTANCE REPLACEMENT")
        require(file_sha256(stage / "GUIDE.BIN") == initial_guide_hash,
                "REP changed a protected consolidated Guide record")
        driver.command("DELE SURICRASIA:1..1")
        require(file_sha256(stage / "GUIDE.BIN") == initial_guide_hash,
                "DELE changed a protected consolidated Guide record")
        report.check("REP and DELE reject protected consolidated records", initial_guide_hash)

        driver.command(f"CAST SURICRASIA:{original_note}")
        cast_guide = parse_guide(stage / "GUIDE.BIN")
        cast_subject = subject_records(cast_guide, identity_raw)
        require(len(cast_guide["bytes"]) == len(initial_guide["bytes"]) + GUIDE_RECORD_BYTES,
                "CAST did not append exactly one 84-byte record")
        require(cast_guide["boundary"] == initial_guide["boundary"],
                "CAST moved the consolidated Guide boundary")
        require(cast_subject[-1]["message"] == original_note
                and not cast_subject[-1]["consolidated"],
                "CAST did not append the expected local SURICRASIA note")
        local_ordinal = len(cast_subject)
        report.check("CAST appends one local fixed-size Guide record",
                     {"ordinal": local_ordinal, "bytes": len(cast_guide["bytes"])})

        driver.command(f"REP SURICRASIA:{local_ordinal}:{corrected_note}")
        replaced = parse_guide(stage / "GUIDE.BIN")
        replaced_subject = subject_records(replaced, identity_raw)
        require(replaced_subject[-1]["message"] == corrected_note,
                "REP did not replace the selected local Guide record")
        require(len(replaced["bytes"]) == len(cast_guide["bytes"]),
                "REP changed GUIDE.BIN length")
        report.check("REP corrects the one-based local subject record", local_ordinal)

        driver.command(f"CAST SURICRASIA:{deleted_note}")
        added_delete = parse_guide(stage / "GUIDE.BIN")
        delete_ordinal = len(subject_records(added_delete, identity_raw))
        driver.command(f"DELE SURICRASIA:{delete_ordinal}..{delete_ordinal}")
        tombstoned = parse_guide(stage / "GUIDE.BIN")
        require(len(tombstoned["bytes"]) == len(added_delete["bytes"]),
                "DELE changed GUIDE.BIN length before CLEAN")
        require(tombstoned["records"][-1]["removed"],
                "DELE did not write the Removed: tombstone")
        report.check("DELE tombstones a selected local record", delete_ordinal)

        driver.command("CLEAN", 300.0)
        cleaned = parse_guide(stage / "GUIDE.BIN")
        cleaned_subject = subject_records(cleaned, identity_raw)
        require(len(cleaned["bytes"]) == len(replaced["bytes"]),
                "CLEAN did not compact exactly the tombstoned record")
        require(cleaned_subject[-1]["message"] == corrected_note,
                "CLEAN lost the surviving corrected local record")
        require(cleaned["bytes"][:initial_guide["boundary"]]
                == initial_guide["bytes"][:initial_guide["boundary"]],
                "CLEAN changed the consolidated Guide prefix")
        require(file_sha256(stage / "STARMAP.BIN") == initial_map_hash,
                "CLEAN changed a STARMAP with no tombstones")
        report.check("CLEAN compacts tombstones and preserves consolidated bytes")

        driver.command(f"PRI SURICRASIA:{local_ordinal}..{local_ordinal}")
        pri = validate_print_export(stage / "GUIDE-PRINT.TXT", corrected_note)
        driver.command(f"PRIF SURICRASIA:{local_ordinal}..{local_ordinal}")
        prif = validate_print_export(stage / "GDOUTPUT.TXT", corrected_note)
        require((stage / "GUIDE-PRINT.TXT").read_bytes()
                == (stage / "GDOUTPUT.TXT").read_bytes(),
                "PRI and PRIF selected exports differ")
        report.data["exports"] = {"PRI": pri, "PRIF": prif}
        report.check("PRI and PRIF emit byte-identical CRLF 72-column exports",
                     pri["sha256"])
        report.flush()

        driver.command("OUTBOX", 300.0)
        packet_path = stage / "OUTBOX.ZIP"
        packet = parse_exchange_packet(packet_path)
        packet_messages = [raw[8:].split(b"\0", 1)[0].decode("latin-1").rstrip()
                           for raw in packet["guide_records"]]
        require(corrected_note in packet_messages,
                "OUTBOX omits the surviving corrected local note")
        require(deleted_note not in packet_messages,
                "OUTBOX includes the deleted local note")
        report.data["outbox"] = {key: value for key, value in packet.items()
                                 if key not in {"starmap_records", "guide_records"}}
        report.data["outbox"].update({
            "starmap_record_count": len(packet["starmap_records"]),
            "guide_record_count": len(packet["guide_records"]),
        })
        report.check("OUTBOX framing contains only live local records",
                     report.data["outbox"])
        report.flush()
        request_quit(driver, report, process, "Guide sender")

    persisted_hash = file_sha256(stage / "GUIDE.BIN")
    clear_launch_outputs(stage)
    with PrivateDesktopProcess(staged, stage, arguments) as process:
        driver = open_driver(process, stage, report, arguments)
        driver.command(f"CAT SURICRASIA:{local_ordinal}..{local_ordinal}")
        persisted = parse_guide(stage / "GUIDE.BIN")
        require(file_sha256(stage / "GUIDE.BIN") == persisted_hash,
                "Guide persistence read changed the database")
        require(subject_records(persisted, identity_raw)[-1]["message"] == corrected_note,
                "corrected local record did not persist across restart")
        report.check("Guide mutation persists across clean restart", persisted_hash)
        request_quit(driver, report, process, "Guide persistence proof")

    receiver = stage / "receiver"
    receiver_executable = stage_product(
        receiver, executable, v18_checkpoint("stardrifter")
    )
    receiver_note = "V1 RECEIVER UNRELATED LOCAL NOTE"
    with PrivateDesktopProcess(receiver_executable, receiver, arguments) as process:
        driver = open_driver(process, receiver, report, arguments)
        driver.command(f"CAST SURICRASIA:{receiver_note}")
        shutil.copy2(packet_path, receiver / "INBOX.ZIP")
        driver.command("INBOX", 300.0)
        imported_guide = parse_guide(receiver / "GUIDE.BIN")
        imported_subject = subject_records(imported_guide, identity_raw)
        imported_messages = [record["message"] for record in imported_subject]
        require(corrected_note in imported_messages and receiver_note in imported_messages,
                "INBOX did not preserve both imported and unrelated local records")
        first_import_hashes = (
            file_sha256(receiver / "STARMAP.BIN"),
            file_sha256(receiver / "GUIDE.BIN"),
        )
        driver.command("INBOX", 300.0)
        second_import_hashes = (
            file_sha256(receiver / "STARMAP.BIN"),
            file_sha256(receiver / "GUIDE.BIN"),
        )
        require(second_import_hashes == first_import_hashes,
                "second INBOX import is not byte-identical and idempotent")
        report.data["inbox"] = {
            "packet_sha256": packet["sha256"],
            "first_import_starmap_sha256": first_import_hashes[0],
            "first_import_guide_sha256": first_import_hashes[1],
            "second_import_starmap_sha256": second_import_hashes[0],
            "second_import_guide_sha256": second_import_hashes[1],
            "corrected_record_present": True,
            "unrelated_record_present": True,
        }
        report.check("INBOX preserves unrelated local data and is idempotent",
                     report.data["inbox"])
        report.flush()
        request_quit(driver, report, process, "Guide receiver")

    repair_stage = stage / "repair"
    repair_executable = stage_product(
        repair_stage, executable, v18_checkpoint("stardrifter")
    )
    real_map = parse_starmap(repair_stage / "STARMAP.BIN")
    repair_subject = find_subject(real_map, "SURICRASIA")
    (repair_stage / "STARMAP.BIN").write_bytes(
        struct.pack("<I", 4 + STARMAP_RECORD_BYTES) + repair_subject["raw"]
    )
    first_consolidated = initial_guide["records"][0]["raw"]
    duplicate_note = "V1 REPAIR DUPLICATE NOTE"
    duplicate = encoded_guide_record(identity_raw, duplicate_note)
    (repair_stage / "GUIDE.BIN").write_bytes(
        struct.pack("<I", 4 + GUIDE_RECORD_BYTES)
        + first_consolidated + duplicate + duplicate
    )
    clear_launch_outputs(repair_stage)
    with PrivateDesktopProcess(repair_executable, repair_stage, arguments) as process:
        driver = open_driver(process, repair_stage, report, arguments)
        driver.command("REPAIR", 120.0)
        repaired = parse_guide(repair_stage / "GUIDE.BIN")
        require(len(repaired["records"]) == 3,
                "bounded REPAIR changed record count before CLEAN")
        require(not repaired["records"][1]["removed"]
                and repaired["records"][2]["removed"],
                "REPAIR did not preserve the first duplicate and tombstone the later one")
        driver.command("CLEAN", 120.0)
        repaired_clean = parse_guide(repair_stage / "GUIDE.BIN")
        require(len(repaired_clean["records"]) == 2,
                "CLEAN did not compact the repaired duplicate")
        require(repaired_clean["records"][1]["message"] == duplicate_note,
                "REPAIR/CLEAN lost the retained duplicate source")
        report.data["repair"] = {
            "strategy": (
                "shipping REPAIR command through the real UI against a structurally exact "
                "bounded database; the shipped 48,376-record O(n^2) implementation is not "
                "misreported as a practical full-corpus run"
            ),
            "records_before": 3,
            "records_after_clean": 2,
            "later_duplicate_tombstoned": True,
        }
        report.check("REPAIR preserves first duplicate, tombstones later duplicate, and cleans",
                     report.data["repair"])
        report.flush()
        request_quit(driver, report, process, "bounded Guide repair")

    require(file_sha256(TRACKED_GUIDE) == report.data["provenance"]["tracked_guide_sha256"],
            "tracked GUIDE.BIN changed during Guide phase")
    require(file_sha256(TRACKED_STARMAP) == report.data["provenance"]["tracked_starmap_sha256"],
            "tracked STARMAP.BIN changed during Guide phase")


def run_phase(phase: str, executable: Path, output_root: Path, *, force: bool) -> bool:
    stage = output_root / phase
    try:
        report = PhaseReport(phase, stage, executable, force=force)
    except FileExistsError as error:
        retained = json.loads((stage / "acceptance-report.json").read_text(encoding="utf-8"))
        provenance = retained.get("provenance", {})
        current = {
            "executable_sha256": file_sha256(executable),
            "game_source_sha256": file_sha256(GAME_SOURCE),
            "tracked_guide_sha256": file_sha256(TRACKED_GUIDE),
            "tracked_starmap_sha256": file_sha256(TRACKED_STARMAP),
        }
        matching = all(provenance.get(key) == value for key, value in current.items())
        if not matching:
            print(f"STALE {phase}: retained provenance differs; use --force ({error})")
            return False
        print(f"RETAINED {phase}: {error}")
        return retained.get("status") == "PASS"
    try:
        if phase == "menus":
            run_menus(report, executable)
        elif phase == "journey":
            run_journey(report, executable)
        else:
            run_guide(report, executable)
        provenance = report.data["provenance"]
        require(
            provenance["tracked_guide_sha256"] == file_sha256(TRACKED_GUIDE),
            "tracked GUIDE.BIN changed during isolated acceptance",
        )
        require(
            provenance["tracked_starmap_sha256"] == file_sha256(TRACKED_STARMAP),
            "tracked STARMAP.BIN changed during isolated acceptance",
        )
        report.finish("PASS")
        print(f"RESULT PASS {phase}: {report.path}")
        return True
    except BaseException as error:
        status = "BLOCKED" if isinstance(error, (AcceptanceBlocked, TimeoutError)) else "FAIL"
        report.finish(status, error=error)
        print(f"RESULT {status} {phase}: {error}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("menus", "journey", "guide"),
                        action="append", required=True)
    parser.add_argument("--executable", type=Path, default=DEFAULT_EXECUTABLE)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--force", action="store_true",
                        help="replace retained terminal evidence for selected phases")
    args = parser.parse_args()
    if os.name != "nt":
        print("SKIP Noctis playability acceptance requires Windows")
        return 0
    executable = args.executable.resolve()
    if not executable.is_file():
        parser.error(f"missing executable: {executable}")
    output_root = args.output_root.resolve()
    phases = list(dict.fromkeys(args.phase))
    results = [run_phase(phase, executable, output_root, force=args.force)
               for phase in phases]
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
