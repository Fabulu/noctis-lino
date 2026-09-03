#!/usr/bin/env python3
"""Decode the opt-in Noctis gameplay acceptance trace."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import struct
import time
from typing import TypeAlias


TRACE_NAME = "game-controls-state-out.bin"
TRACE_MAGIC = 0x56484354
TRACE_SCHEMA = 3
TRACE_WORDS = 83
TRACE_BYTES = TRACE_WORDS * 4
TRACE_FIELDS = (
    "magic", "schema", "sequence", "quit", "escape_held", "preferences",
    "device", "browser_valid", "browser_origin", "fcs_open", "roofspeed",
    "mouselook", "x", "y", "z", "alpha", "beta", "landing_select",
    "landing_pending", "landing_longitude", "landing_latitude", "output_view",
    "fcs_row9_class", "ctrl_used", "mode", "ascii", "screen", "console",
    "console_view", "info", "graphics", "movie_view", "movie_recording",
    "help", "about", "fast_presentation", "fps_show", "draw_hud",
    "lens_mode", "seamless", "landed", "capsule_state", "capsule_count",
    "capsule_recover", "capsule_start_pending", "capsule_return_pending",
    "planet", "planet_type", "system_body_count", "local_active",
    "local_target", "local_approaching", "local_reached", "star_drive",
    "star_reached", "drive_status", "target_x", "target_y", "target_z",
    "current_x_low", "current_x_high", "current_y_low", "current_y_high",
    "current_z_low", "current_z_high", "frame", "autoscreen_off",
    "reverse_controls", "menus_always_on", "depolarize", "amplifier",
    "finder", "sync", "antirad", "interior_light", "exterior_light",
    "reset_count", "gburst", "menu_hover", "menu_key", "device_access",
    "info_scroll", "notice_frames",
)

ControlState: TypeAlias = dict[str, int]
Predicate: TypeAlias = Callable[[ControlState], bool]


def decode_trace_record(data: bytes) -> ControlState:
    if len(data) != TRACE_BYTES:
        raise ValueError(
            f"control trace record is {len(data)} bytes, expected {TRACE_BYTES}"
        )
    record = dict(zip(TRACE_FIELDS, struct.unpack(f"<{TRACE_WORDS}i", data)))
    if record["magic"] != TRACE_MAGIC:
        raise ValueError(f"bad control trace magic 0x{record['magic'] & 0xffffffff:08x}")
    if record["schema"] != TRACE_SCHEMA:
        raise ValueError(f"unsupported control trace schema {record['schema']}")
    return record


def decode_trace(path: Path) -> list[ControlState]:
    data = path.read_bytes()
    if not data or len(data) % TRACE_BYTES:
        raise ValueError(f"control trace has incomplete length {len(data)}")
    records = [
        decode_trace_record(data[offset:offset + TRACE_BYTES])
        for offset in range(0, len(data), TRACE_BYTES)
    ]
    sequences = [record["sequence"] for record in records]
    if sequences != list(range(1, len(records) + 1)):
        raise ValueError("control trace sequence is stale, duplicated, or incomplete")
    return records


class TraceReader:
    """Consume complete appended trace records exactly once."""

    def __init__(self, path: Path, *, records_per_read: int = 256) -> None:
        if records_per_read < 1:
            raise ValueError("records_per_read must be positive")
        self.path = path
        self.records_per_read = records_per_read
        self.offset = 0
        self.next_sequence = 1
        self.last: ControlState | None = None

    def read_new(self) -> list[ControlState]:
        try:
            size = self.path.stat().st_size
        except FileNotFoundError:
            return []
        if size < self.offset:
            raise ValueError("control trace was truncated while being consumed")
        complete = (size - self.offset) // TRACE_BYTES
        if not complete:
            return []
        count = min(complete, self.records_per_read)
        with self.path.open("rb") as stream:
            stream.seek(self.offset)
            data = stream.read(count * TRACE_BYTES)
        if len(data) != count * TRACE_BYTES:
            return []
        records: list[ControlState] = []
        for offset in range(0, len(data), TRACE_BYTES):
            record = decode_trace_record(data[offset:offset + TRACE_BYTES])
            if record["sequence"] != self.next_sequence:
                raise ValueError(
                    "control trace sequence is stale, duplicated, or incomplete: "
                    f"expected {self.next_sequence}, got {record['sequence']}"
                )
            records.append(record)
            self.next_sequence += 1
        self.offset += len(data)
        self.last = records[-1]
        return records

    def drain(self) -> ControlState | None:
        while self.read_new():
            pass
        return self.last

    def wait(
        self,
        process,
        after: int,
        predicate: Predicate,
        description: str,
        timeout: float,
        *,
        allow_exit: bool = False,
        progress: Callable[[float, ControlState | None], None] | None = None,
    ) -> ControlState:
        deadline = time.monotonic() + timeout
        next_progress = time.monotonic() + 10.0
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            return_code = process.poll()
            if return_code not in (None, 0):
                raise RuntimeError(
                    f"game host exited while waiting for {description} "
                    f"with code {return_code}"
                )
            try:
                for record in self.read_new():
                    if record["sequence"] > after and predicate(record):
                        return record
                last_error = None
            except (OSError, ValueError) as error:
                last_error = error
            now = time.monotonic()
            if progress is not None and now >= next_progress:
                progress(max(0.0, deadline - now), self.last)
                next_progress = now + 10.0
            if return_code == 0 and allow_exit:
                break
            time.sleep(0.03)
        suffix = f"; last trace error: {last_error}" if last_error else ""
        raise TimeoutError(
            f"timed out waiting for {description} after sequence {after}; "
            f"last sequence {self.next_sequence - 1}{suffix}"
        )

    def wait_next(self, process, description: str, timeout: float) -> ControlState:
        after = self.last["sequence"] if self.last is not None else 0
        return self.wait(process, after, lambda _record: True, description, timeout)
