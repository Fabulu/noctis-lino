#!/usr/bin/env python3
"""Create deterministic version-15 landed Noctis checkpoints."""

from __future__ import annotations

import argparse
from pathlib import Path
import struct


CHECKPOINT_MAGIC = 0x56485356
CHECKPOINT_UNITS = 66
DEFAULT_CLOCK = 1344638527


def build_landed_checkpoint(
    *,
    star_x: int,
    star_y: int,
    star_z: int,
    body: int,
    longitude: int,
    latitude: int,
    beta: int,
    pitch: int,
    player_x: int = 1638400,
    player_y: int = -600,
    player_z: int = 1638400,
    mode: int = 1,
    navigation_angle: int = 0,
    capsule_x: int = 131072,
    capsule_z: int = 131072,
    window_width: int = 642,
    window_height: int = 426,
    lens_mode: int = 0,
    open_hud: bool = False,
    fast: bool = False,
) -> bytes:
    """Return the exact 264-byte stable subset consumed by the game loader."""
    if lens_mode not in (-1, 0, 1):
        raise ValueError("lens mode must be -1, 0, or 1")
    if not 272 <= window_width <= 962 or not 120 <= window_height <= 626:
        raise ValueError("window dimensions exceed the checkpoint limits")

    pitch = max(-44, min(44, pitch))
    units = [0] * CHECKPOINT_UNITS
    units[0] = CHECKPOINT_MAGIC
    units[1] = 15
    units[2] = mode
    units[3] = body
    units[4:9] = (player_x, player_y, player_z, pitch, beta)
    units[11] = -300
    units[18] = 30000
    units[19] = 1
    units[22] = 1
    units[23] = 300
    units[24:27] = (star_x, star_y, star_z)
    units[27] = int(fast)
    units[31] = 3
    units[35:42] = (
        DEFAULT_CLOCK,
        window_width,
        window_height,
        1,
        12,
        longitude,
        latitude,
    )
    units[42:45] = (capsule_x, 0, capsule_z)
    units[47] = lens_mode + 5 + (16 if open_hud else 0)
    units[49] = -1
    units[64] = 4
    units[65] = navigation_angle

    try:
        return struct.pack(f"<{CHECKPOINT_UNITS}i", *units)
    except struct.error as error:
        raise ValueError(f"checkpoint field exceeds signed 32-bit range: {error}") from error


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--star-x", type=int, required=True)
    parser.add_argument("--star-y", type=int, required=True)
    parser.add_argument("--star-z", type=int, required=True)
    parser.add_argument("--body", type=int, required=True)
    parser.add_argument("--longitude", type=int, required=True)
    parser.add_argument("--latitude", type=int, required=True)
    parser.add_argument("--beta", type=int, required=True)
    parser.add_argument("--pitch", type=int, required=True)
    parser.add_argument("--player-x", type=int, default=1638400)
    parser.add_argument("--player-y", type=int, default=-600)
    parser.add_argument("--player-z", type=int, default=1638400)
    parser.add_argument("--mode", type=int, default=1)
    parser.add_argument("--navigation-angle", type=int, default=0)
    parser.add_argument("--capsule-x", type=int, default=131072)
    parser.add_argument("--capsule-z", type=int, default=131072)
    parser.add_argument("--window-width", type=int, default=642)
    parser.add_argument("--window-height", type=int, default=426)
    parser.add_argument("--lens-mode", type=int, choices=(-1, 0, 1), default=0)
    parser.add_argument("--open-hud", action="store_true")
    parser.add_argument("--fast", action="store_true")
    args = parser.parse_args()

    data = build_landed_checkpoint(
        star_x=args.star_x,
        star_y=args.star_y,
        star_z=args.star_z,
        body=args.body,
        longitude=args.longitude,
        latitude=args.latitude,
        beta=args.beta,
        pitch=args.pitch,
        player_x=args.player_x,
        player_y=args.player_y,
        player_z=args.player_z,
        mode=args.mode,
        navigation_angle=args.navigation_angle,
        capsule_x=args.capsule_x,
        capsule_z=args.capsule_z,
        window_width=args.window_width,
        window_height=args.window_height,
        lens_mode=args.lens_mode,
        open_hud=args.open_hud,
        fast=args.fast,
    )
    args.output.write_bytes(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
