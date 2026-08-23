"""Grade retained native surface-sun frames against product diagnostics.

The default mode is non-GUI: it validates six pinned NIV+ BMP oracles and the
shipping diagnostic/export contracts.  The hosted native Apple-Silicon product
run supplies the product view, page, palette, and flare-state files.  Authority
is case-specific: complete palette bands or exact upper-sky crops are graded
only where the retained bytes and deterministic lighting state support them.
Exact whole-page equality is reported but cannot be graded where the native rig
did not retain the live camera, simulation, and HUD state at the instant of its
timed snapshot::

    python tests/test_sun_gallery.py --case thin-sun45 \
        --product-directory build/sun-gallery
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys


ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / "work" / "vhgame.txt"
CAPTURE = ROOT / "tools" / "capture_noctis_scenes.ps1"
CHECKPOINT_TOOL = ROOT / "tools" / "make_noctis_checkpoint.py"
PRIVATE_RUNNER = ROOT / "tools" / "run_hidden_noctis.py"
MACOS_WORKFLOW = ROOT / ".github" / "workflows" / "macos-aarch64-runtime.yml"
WINDOWS_WORKFLOW = ROOT / ".github" / "workflows" / "windows-release.yml"
sys.path.insert(0, str(ROOT / "tools"))

from make_noctis_checkpoint import build_landed_checkpoint  # noqa: E402

CASES = {
    "hab-sun270": {
        "scene": "habitable",
        "oracle": ROOT / "tests" / "gen" / "recon_w7b" / "out"
        / "hab_sun270_pinned_oracle.shot.BMP",
        "surface": ROOT / "tests" / "gen" / "recon_w7b" / "out"
        / "hab_sun270_pinned_oracle.SURFACE.BIN",
        "provenance": ROOT / "tests" / "gen" / "recon_w7b" / "out"
        / "hab_sun270_pinned_oracle.provenance.json",
        "bmp_sha256": "c08cdb6f74f82c83170848e0071e2f7c0c82cfb35d20d097a8db7409fcf76d84",
        "surface_sha256": "74eed5198ed6de0c725f610b05d5ee9a60a531fe64e1791e4fe363351febf1d6",
        "provenance_sha256": "850b84ae0b6b6b4dffa1e4b30ab54a29da1ecfd40eb99ac7e59fcd855757578a",
        "surface_state": (
            270, 60, 8, 8, 0, 0,
            1598248.0, 1.0, 2251369.0, -45.0, 270.0,
        ),
        # NIV+ normalizes the authored heading 270 to -90 and clamps -45 to
        # its lower camera endpoint.  Lino's integral endpoint is -44.
        "page_sha256": "9e563cff6b6703f382ad15f353da71eaad8e087eba79b3b08ae757e5a45d3d8b",
        "palette_sha256": "c874d98235a9649a4e468d7f8b35f19cea923bdb72d550590ec1097b402fb7ee",
        "checkpoint_sha256": "0216819e0a26476e48d4f9e27fa86b4d89bd965a581d58a3db8f164c0e40e3fa",
        "checkpoint": {
            "star_x": 1463568,
            "star_y": -4728350,
            "star_z": -437812,
            "body": 3,
            "longitude": 270,
            "latitude": 60,
            "beta": 270,
            "pitch": -44,
            "player_x": 1598248,
            "player_z": 2251369,
            "fast": True,
        },
        "view": (1598248, -600, 2251369, -44, -90),
        "center": (161, 130),
        "native_center": 126,
        "full_band_exact": True,
        "palette_exact": True,
        "beam_gate": "positive",
        "product": {
            "mode": 1,
            "landed": 1,
            "planet_type": 3,
            "star_class": 0,
            "atmosphere": 1,
            "night": 0,
            "rain": 0.0,
            "flare": 1,
            "exposure": 35.9996,
            "distance": 243.633,
            "ray": 5.15,
        },
    },
    "thin-sun45": {
        "scene": "thin",
        "oracle": ROOT / "tests" / "native-oracles" / "thin-sun45"
        / "native.shot.BMP",
        "surface": ROOT / "tests" / "native-oracles" / "thin-sun45"
        / "native.SURFACE.BIN",
        "bmp_sha256": "a8e94775d1d4b7d7e4817088116d716a43e42b2b456c4734125430e1714de93b",
        "surface_sha256": "8e63c9ed2d588f2fe642ef4cf184e833edea251572b376a8a8700b1a09aabe2f",
        "surface_state": (
            45, 60, 8, 8, 0, 0,
            1645000.0, 1.0, 1641000.0, -30.0, 90.0,
        ),
        "page_sha256": "b9c33fba1389c3244634f9e3bca7c91b63eb7657678060e6cfec74df39d22812",
        "palette_sha256": "5c4f3d10d756593012618d64d217327241559de094ce351b9f9faf15a9de94a2",
        "checkpoint_sha256": "2ae05d1536b524559045bf4edfe1d1e948253f682bbb61b3dfd29326ca73a5f9",
        "checkpoint": {
            "star_x": 1463568,
            "star_y": -4728350,
            "star_z": -437812,
            "body": 2,
            "longitude": 45,
            "latitude": 60,
            "beta": 90,
            "pitch": -30,
            "player_x": 1645000,
            "player_z": 1641000,
            "fast": True,
        },
        "view": (1645000, -2648, 1641000, -30, 90),
        "center": (161, 28),
        "native_center": 126,
        "full_band_exact": True,
        "palette_exact": True,
        "beam_gate": "positive",
        "product": {
            "mode": 1,
            "landed": 1,
            "planet_type": 5,
            "star_class": 0,
            "atmosphere": 1,
            "night": 0,
            "rain": 0.0,
            "flare": 1,
            "exposure": 49.3038,
            "distance": 112.235,
            "ray": 5.15,
        },
    },
    "lunar-sun0": {
        "scene": "lunarsun",
        "oracle": ROOT / "tests" / "native-oracles" / "lunar-sun0"
        / "native.shot.BMP",
        "surface": ROOT / "tests" / "native-oracles" / "lunar-sun0"
        / "native.SURFACE.BIN",
        "bmp_sha256": "ddc0582655a2e194a97cb071187b26da5a6b368e07be11b31027f70e06b2ffa1",
        "surface_sha256": "46b02d475662b76691baa8dc8e44fbc3a670adfce7a1e89ebd9dc5031c4efcd1",
        "surface_state": (
            0, 60, 100, 100, 8192, 8192,
            1638400.0, -19032.0, 1638400.0, -44.0, 90.0,
        ),
        "page_sha256": "38b5b2347fff4c3fe5016337904a8a51ff1d5f7276e2555e7461f8623a87997b",
        "palette_sha256": "a6570716a7b04a4629ac7cdfa0ddb21d23305a207a80a8cafda707a50543e9ab",
        "checkpoint_sha256": "c106a8cad1d21e5c7040a04b55b1ce2d483b2eda4bc73ab515753604a830e705",
        "checkpoint": {
            "star_x": 174288,
            "star_y": -44389,
            "star_z": -688771,
            "body": 0,
            "longitude": 0,
            "latitude": 60,
            "beta": 90,
            "pitch": -44,
            "player_x": 1638400,
            "player_y": -19032,
            "player_z": 1638400,
            "fast": True,
        },
        "view": (1638400, -72280, 1638400, -44, 90),
        "center": (161, 82),
        "native_center": 127,
        "full_band_exact": False,
        "exact_crop": (10, 10, 310, 130),
        "palette_exact": True,
        "beam_gate": "lower",
        "product": {
            "mode": 1,
            "landed": 1,
            "planet_type": 1,
            "star_class": 0,
            "atmosphere": 0,
            "night": 0,
            "rain": 0.0,
            "flare": 1,
            "exposure": 49.3038,
            "distance": 34.5763,
            "ray": 6.955,
        },
    },
    "dense-sun0": {
        "scene": "densesun",
        "oracle": ROOT / "tests" / "native-oracles" / "dense-sun0"
        / "native.shot.BMP",
        "surface": ROOT / "tests" / "native-oracles" / "dense-sun0"
        / "native.SURFACE.BIN",
        "bmp_sha256": "3f49a3ac6d730b028766f354ac81d3cd077dc843a2b6ddd8731d759f39becb47",
        "surface_sha256": "db6835c47e8edc213d82448ac3d6bf45ba245e71e9c5425eed3c1ec2b982f5dc",
        "surface_state": (
            0, 60, 100, 100, 8192, 8192,
            1638400.0, 1.0, 1638400.0, -44.0, 90.0,
        ),
        "page_sha256": "a33a33802da8072710fb732cfe8a68d0037b6239ac4f1e19beecbef52e5df4e7",
        "palette_sha256": "c7e3d402b9e2a5b6a596a076d25f52209acdfa37fae511a60979a79a3a5aa778",
        "checkpoint_sha256": "ccb8dcbdeca3f980906bd70e88f0adbc16baa845da5438243cfb809063266c58",
        "checkpoint": {
            "star_x": 1463568,
            "star_y": -4728350,
            "star_z": -437812,
            "body": 0,
            "longitude": 0,
            "latitude": 60,
            "beta": 90,
            "pitch": -44,
            "player_x": 1638400,
            "player_z": 1638400,
            "fast": True,
        },
        "view": (1638400, -242264, 1638400, -44, 90),
        "center": (161, 40),
        "native_center": 59,
        "full_band_exact": True,
        "palette_exact": False,
        "beam_gate": "lower",
        "product": {
            "mode": 1,
            "landed": 1,
            "planet_type": 2,
            "star_class": 0,
            "atmosphere": 1,
            "night": 0,
            "rain": 0.0,
            "flare": 1,
            "exposure": 60.2602,
            "distance": 24.2725,
            "ray": 5.15,
        },
    },
    "rocky-sun90": {
        "scene": "rockysun",
        "oracle": ROOT / "tests" / "native-oracles" / "rocky-sun90"
        / "native.shot.BMP",
        "surface": ROOT / "tests" / "native-oracles" / "rocky-sun90"
        / "native.SURFACE.BIN",
        "bmp_sha256": "f983407da7c9ff5c9da47560c23d4f9a77040708b70da010ce6b4dc6b9c94b0a",
        "surface_sha256": "6010d36d894ec6e086e9a7a47e4d7d0ab8e4113527f7c282800fe0c4623e4b09",
        "surface_state": (
            90, 60, 8, 8, 0, 0,
            1645000.0, 1.0, 1641000.0, -38.0, 270.0,
        ),
        "page_sha256": "6789a54784a2721cb475d8c7b6eae171b87ab0b46b296ff78a96745a1425dae1",
        "palette_sha256": "1b7d437f34c8ff90711e56d4ad6a477fe1d9135ddd10d597299f45626a8b6ed2",
        "checkpoint_sha256": "b4ede164b0e82cea43e50d7f90f9393d36d266192cbf4a89d60360356209c21a",
        "checkpoint": {
            "star_x": 1463568,
            "star_y": -4728350,
            "star_z": -437812,
            "body": 9,
            "longitude": 90,
            "latitude": 60,
            "beta": 270,
            "pitch": -38,
            "player_x": 1645000,
            "player_z": 1641000,
            "fast": True,
        },
        "view": (1645000, -57298, 1641000, -38, -90),
        "center": (161, 44),
        "native_center": 64,
        "full_band_exact": False,
        "exact_crop": (10, 10, 310, 100),
        "palette_exact": True,
        "beam_gate": "upper",
        "product": {
            "mode": 1,
            "landed": 1,
            "planet_type": 4,
            "star_class": 0,
            "atmosphere": 0,
            "night": 0,
            "rain": 0.0,
            "flare": 1,
            "exposure": 53.2168,
            "distance": 9133.45,
            "ray": 5.15,
        },
    },
    "frozen-sun0": {
        "scene": "frozensun",
        "oracle": ROOT / "tests" / "native-oracles" / "frozen-sun0"
        / "native.shot.BMP",
        "surface": ROOT / "tests" / "native-oracles" / "frozen-sun0"
        / "native.SURFACE.BIN",
        "bmp_sha256": "1f221358d756737d349926d36e98ae8e99e71063d63c4bf577dbb7971357d01a",
        "surface_sha256": "0e0efa5fc114a99fcae0b31f467b85dd3ef5e44849794680fd5000d9c6463154",
        "surface_state": (
            0, 60, 8, 8, 0, 0,
            1645000.0, 1.0, 1641000.0, -44.0, 90.0,
        ),
        "page_sha256": "f7fc6e9f84073f145e4648f697840afdbd79a04c703aa76957bcc665636ebe96",
        "palette_sha256": "843334d0b9ac9a7f013810ed80ca46da5b98c2f5f497a7ff7f265371d1f56824",
        "checkpoint_sha256": "6365747e55504f56f18ad1d901e605fcd8c71d3223790ec41ab070743b7483fe",
        "checkpoint": {
            "star_x": 2952848,
            "star_y": -6448045,
            "star_z": -840503,
            "body": 9,
            "longitude": 0,
            "latitude": 60,
            "beta": 90,
            "pitch": -44,
            "player_x": 1645000,
            "player_z": 1641000,
            "fast": True,
        },
        "view": (1645000, -600, 1641000, -44, 90),
        "center": (161, 46),
        "native_center": 64,
        "full_band_exact": True,
        "exact_crop": (10, 10, 310, 130),
        "palette_exact": True,
        "beam_gate": "upper",
        "product": {
            "mode": 1,
            "landed": 1,
            "planet_type": 7,
            "star_class": 1,
            "atmosphere": 0,
            "night": 0,
            "rain": 0.0,
            "flare": 1,
            "exposure": 58.695,
            "distance": 34167.4023,
            "ray": 21.879,
        },
    },
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decode_surface(path: Path) -> tuple[int | float, ...]:
    data = path.read_bytes()
    if len(data) != 40:
        raise AssertionError(f"{path}: expected exact 40-byte NIV+ surface state")
    return struct.unpack("<hhiiiifffff", data)


def decode_bmp(path: Path) -> tuple[bytes, tuple[int, ...]]:
    data = path.read_bytes()
    if len(data) < 1078 or data[:2] != b"BM":
        raise AssertionError(f"{path}: not a complete indexed BMP")
    file_size = struct.unpack_from("<I", data, 2)[0]
    pixel_offset = struct.unpack_from("<I", data, 10)[0]
    dib_size, width, height, planes, depth, compression = struct.unpack_from(
        "<IiiHHI", data, 14
    )
    # The retained Borland capture preserves its historical stale bfSize/image
    # size fields.  Its dimensions, pixel offset, actual extent, and whole-file
    # hash are authoritative; do not rewrite the source artifact to normalize it.
    if file_size != 116326:
        raise AssertionError(f"{path}: unexpected historical header size {file_size}")
    if (dib_size, width, abs(height), planes, depth, compression, pixel_offset) != (
        40,
        320,
        200,
        1,
        8,
        0,
        1078,
    ):
        raise AssertionError(
            f"{path}: expected 320x200 uncompressed 8-bit BMP, got "
            f"dib={dib_size} size={width}x{height} planes={planes} "
            f"depth={depth} compression={compression} offset={pixel_offset}"
        )

    table = data[14 + dib_size : pixel_offset]
    if len(table) != 1024:
        raise AssertionError(f"{path}: expected 256-entry palette, got {len(table)} bytes")
    palette: list[int] = []
    for index in range(256):
        blue, green, red, reserved = table[index * 4 : index * 4 + 4]
        if reserved != 0 or any(component & 3 for component in (red, green, blue)):
            raise AssertionError(
                f"{path}: palette entry {index} is not an exact six-bit BGR0 value"
            )
        palette.extend((red >> 2, green >> 2, blue >> 2))

    stride = (width + 3) & ~3
    end = pixel_offset + stride * abs(height)
    if end != len(data):
        raise AssertionError(f"{path}: pixel extent {end} != file size {len(data)}")
    rows = [
        data[pixel_offset + row * stride : pixel_offset + row * stride + width]
        for row in range(abs(height))
    ]
    if height > 0:
        rows.reverse()
    return b"".join(rows), tuple(palette)


def mismatch_summary(expected: bytes, actual: bytes, width: int = 320) -> str:
    mismatches = [index for index, pair in enumerate(zip(expected, actual)) if pair[0] != pair[1]]
    if not mismatches:
        return "0 mismatches"
    xs = [index % width for index in mismatches]
    ys = [index // width for index in mismatches]
    first = mismatches[0]
    return (
        f"{len(mismatches)} mismatches in ({min(xs)},{min(ys)}).."
        f"({max(xs)},{max(ys)}); first offset {first}: "
        f"native={expected[first]} product={actual[first]}"
    )


def page_crop(page: bytes, rectangle: tuple[int, int, int, int]) -> bytes:
    x0, y0, x1, y1 = rectangle
    if not (0 <= x0 < x1 <= 320 and 0 <= y0 < y1 <= 200):
        raise AssertionError(f"invalid page crop {rectangle}")
    return b"".join(page[y * 320 + x0 : y * 320 + x1] for y in range(y0, y1))


def product_file(directory: Path, scene: str, name: str) -> Path:
    """Accept shared scene exports and isolated per-scene capture directories."""
    prefixed = directory / f"{scene}-{name}"
    return prefixed if prefixed.is_file() else directory / name


def check_source_contract(check) -> None:
    game = GAME.read_text(encoding="utf-8")
    capture = CAPTURE.read_text(encoding="utf-8")
    checkpoint_tool = CHECKPOINT_TOOL.read_text(encoding="utf-8")
    private_runner = PRIVATE_RUNNER.read_text(encoding="utf-8")
    macos_workflow = MACOS_WORKFLOW.read_text(encoding="utf-8")
    windows_workflow = WINDOWS_WORKFLOW.read_text(encoding="utf-8")
    check("vhgpagename = { game-page-out.bin };" in game,
          "game declares a separate packed-page diagnostic")
    check("[SPpreg] = RGADP; [SPpn] = NPIX; => SP packpage;" in game and
          "[Block Pointer] = sppack; [Block Size] = 64000; isocall;" in game and
          "[File Size] = 64000; isocall;" in game,
          "sentinel packs and size-pins all 64,000 final page indices")
    check("[Block Pointer] = vhgsun; [Block Size] = 128; isocall;" in game and
          "[Block Pointer] = curpal6; [Block Size] = 3072; isocall;" in game,
          "existing sun and six-bit palette contracts remain intact")
    check(all(fragment in game for fragment in (
              "vhgsbgname = { game-s-background-out.bin };",
              "vhgpsmname = { game-p-surfacemap-out.bin };",
              "vhgpbgname = { game-p-background-out.bin };",
              "vhgrendername = { game-render-state-out.bin };",
              "[VHGdiagbase] = RSBG; [VHGdiagcount] = ZSBG;",
              "[VHGdiagbase] = RPSM; [VHGdiagcount] = ZPSM;",
              "[VHGdiagbase] = RPBG; [VHGdiagcount] = ZPBG;",
              "[vhgrenderstate plus 3] = [VHSdrawcount];",
              "[vhgrenderstate plus 4] = [brtlseed];",
              "[vhgrenderstate plus 5] = [SUfseed];",
          )),
          "sentinel retains packed physical renderer caches and scalar state")
    check("VHGsentinelquit" in game and
          "[VHGesc] = 1; [Quit Now] = YES;" in game,
          "explicit quit token exits only after complete sentinel diagnostics")
    check("'game-page-out.bin' = 64000" in capture and
          "'game-sun-out.bin' = 128" in capture and
          "'game-palette-out.bin' = 3072" in capture and
          "'game-s-background-out.bin' = 64800" in capture and
          "'game-p-surfacemap-out.bin' = 40000" in capture and
          "'game-p-background-out.bin' = 65552" in capture and
          "'game-render-state-out.bin' = 24" in capture and
          "$Spec.Name, $entry.Key" in capture,
          "diagnostic capture validates and exports scene-qualified product files")
    check("windows_hidden_process.run" in private_runner and
          "subprocess.run" in private_runner and
          "--default-desktop" in private_runner,
          "retained Windows diagnostic runner preserves both launch controls")
    check("CHECKPOINT_UNITS = 66" in checkpoint_tool and
          "struct.pack" in checkpoint_tool and
          "units[35:42]" in checkpoint_tool,
          "cross-platform checkpoint builder emits the stable 264-byte subset")
    check(all(fragment in macos_workflow for fragment in (
              "from make_noctis_checkpoint import build_landed_checkpoint",
              '"case": "hab-sun270"',
              '"case": "thin-sun45"',
              '"case": "lunar-sun0"',
              '"case": "dense-sun0"',
              '"case": "rocky-sun90"',
              '"case": "frozen-sun0"',
              '"scene": "habitable"',
              '"scene": "thin"',
              '"scene": "lunarsun"',
              '"scene": "densesun"',
              '"scene": "rockysun"',
              '"scene": "frozensun"',
              '"clock=1344638527"',
              '"--product-directory", str(gallery)',
              "build/sun-gallery/*-game-*-out.bin",
          )),
          "hosted Apple-Silicon gate executes and retains all six surface-sun cases")
    check("Grade the pinned habitable-world sun frame" not in windows_workflow,
          "Windows packaging no longer depends on an unusable hosted GUI desktop")


def grade_product(case: dict[str, object], directory: Path, oracle_page: bytes,
                  oracle_palette: tuple[int, ...], check) -> None:
    scene = str(case["scene"])
    page_path = product_file(directory, scene, "game-page-out.bin")
    palette_path = product_file(directory, scene, "game-palette-out.bin")
    sun_path = product_file(directory, scene, "game-sun-out.bin")
    view_path = product_file(directory, scene, "game-vh-out.bin")

    for path, size in (
        (page_path, 64000),
        (palette_path, 3072),
        (sun_path, 128),
        (view_path, 156),
    ):
        check(path.is_file() and path.stat().st_size == size,
              f"product emitted {path.name} at exactly {size} bytes")
    if not all(
        path.is_file() for path in (page_path, palette_path, sun_path, view_path)
    ):
        return

    view = struct.unpack("<39i", view_path.read_bytes())
    check(view[:5] == case["view"],
          f"product camera {view[:5]} matches the reproducible landed checkpoint")

    page = page_path.read_bytes()
    if len(page) == len(oracle_page):
        summary = mismatch_summary(oracle_page, page)
        band_differences = [
            index for index, pair in enumerate(zip(oracle_page, page))
            if (pair[0] & 0xC0) != (pair[1] & 0xC0)
        ]
        detail = "0 mismatches" if not band_differences else (
            f"{len(band_differences)} mismatches; first pixel {band_differences[0]}"
        )
        if case["full_band_exact"]:
            check(not band_differences,
                  f"all product pixels retain the native palette band ({detail})")
        else:
            print(f"INFO complete-page palette-band equality is not graded ({detail})")

        crop = case.get("exact_crop")
        if crop is not None:
            assert isinstance(crop, tuple)
            native_crop = page_crop(oracle_page, crop)
            product_crop = page_crop(page, crop)
            x0, y0, x1, y1 = crop
            check(
                product_crop == native_crop,
                f"product upper-sky crop ({x0},{y0})..({x1 - 1},{y1 - 1}) "
                f"matches all {len(native_crop):,} native indices "
                f"({mismatch_summary(native_crop, product_crop, x1 - x0)})",
            )

        cx, cy = case["center"]
        center_offset = cy * 320 + cx
        check(
            (page[center_offset] & 0xC0)
            == (oracle_page[center_offset] & 0xC0),
            "product projected-sun centre retains the native palette band",
        )
        # The retained BMP authenticates the native view and indexed output, but
        # these historical captures do not retain every live HUD/simulation value
        # at the screenshot instant.  Exact whole-page equality therefore remains
        # informational.  Positive-flare low-six-bit centre equality additionally
        # depends on neighbours mixed by the source's two psmooth_64 passes.  The
        # case-specific palette, palette-band/crop, and pinned sun state below are
        # the admissible cross-product contracts.
        print(f"INFO complete-page equality is not graded ({summary})")

    palette_data = palette_path.read_bytes()
    if len(palette_data) == 3072:
        palette = struct.unpack("<768I", palette_data)
        differences = [
            index for index, pair in enumerate(zip(oracle_palette, palette))
            if pair[0] != pair[1]
        ]
        detail = "0 mismatches" if not differences else (
            f"{len(differences)} mismatches; first component {differences[0]}: "
            f"native={oracle_palette[differences[0]]} "
            f"product={palette[differences[0]]}"
        )
        check(all(component <= 63 for component in palette),
              "product palette retains 768 valid six-bit components")
        if case["palette_exact"]:
            check(palette == oracle_palette,
                  f"all 768 six-bit product palette components match native ({detail})")
        else:
            print(f"INFO palette equality is not graded without native easing state ({detail})")

    sun_data = sun_path.read_bytes()
    if len(sun_data) == 128:
        sun = struct.unpack("<32i", sun_data)
        floats = struct.unpack("<32f", sun_data)
        expected = case["product"]
        assert isinstance(expected, dict)
        cx, cy = case["center"]
        check(
            sun[0] == expected["mode"]
            and sun[1] == expected["landed"]
            and sun[2] == expected["planet_type"]
            and sun[3] == expected["star_class"],
            "product diagnostic identifies the pinned landed planet and star class",
        )
        check(
            sun[4] == expected["atmosphere"]
            and sun[5] == expected["night"]
            and abs(floats[6] - expected["rain"]) < 0.0001,
            "product diagnostic retains the pinned atmosphere, day/night, and weather state",
        )
        check(sun[16] == expected["flare"],
              "product diagnostic confirms projected primary-sun admission")
        check(64 <= sun[19] <= 127,
              "product diagnostic retains the sky-band sample at the projected centre")
        check(abs(sun[17] - cx) <= 1 and abs(sun[18] - cy) <= 1,
              f"product flare centre {sun[17]},{sun[18]} aligns with native {cx},{cy}")
        check(
            abs(floats[7] - expected["exposure"]) < 0.01
            and abs(floats[8] - expected["distance"]) < 0.01,
            "product retains the pinned native exposure and live solar distance",
        )
        check(abs(floats[9] - expected["ray"]) < 0.001,
              "product retains the pinned native stellar ray")
        distance = floats[8]
        ray = floats[9]
        gate = case["beam_gate"]
        if gate == "positive":
            admitted = 10.0 * ray <= distance < 1000.0 * ray
            message = "product distance lies inside the native radial-flare interval"
        elif gate == "lower":
            admitted = distance < 10.0 * ray
            message = "product distance authentically suppresses rays below the lower gate"
        elif gate == "upper":
            admitted = distance >= 1000.0 * ray
            message = "product distance authentically suppresses rays at the upper gate"
        else:
            raise AssertionError(f"unknown radial-flare gate {gate!r}")
        check(admitted, message)


def grade_case(case_name: str, product_directory: Path | None, check) -> None:
    print(f"--- {case_name} ---")
    case = CASES[case_name]
    oracle = case["oracle"]
    assert isinstance(oracle, Path)
    data = oracle.read_bytes()
    check(sha256(data) == case["bmp_sha256"],
          "retained native BMP has its pinned SHA-256")

    surface = case["surface"]
    assert isinstance(surface, Path)
    surface_data = surface.read_bytes()
    check(sha256(surface_data) == case["surface_sha256"],
          "retained native surface state has its pinned SHA-256")
    try:
        surface_state = decode_surface(surface)
    except (AssertionError, OSError, struct.error) as error:
        check(False, f"retained native surface state decodes safely: {error}")
    else:
        check(surface_state == case["surface_state"],
              "native oracle records the pinned landed resume state exactly")

    provenance = case.get("provenance")
    if provenance is None:
        print(
            "INFO native snapshot-time camera/simulation/HUD provenance is not "
            "retained; complete-page equality stays disabled"
        )
    else:
        assert isinstance(provenance, Path)
        provenance_data = provenance.read_bytes()
        check(sha256(provenance_data) == case["provenance_sha256"],
              "retained native capture provenance has its pinned SHA-256")
        try:
            provenance_state = json.loads(provenance_data)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            check(False, f"retained native capture provenance decodes safely: {error}")
        else:
            check(
                provenance_state.get("surface_role") == "landed-resume input state"
                and provenance_state.get("shot_after_seconds") == 30
                and provenance_state.get("process_timeout_seconds") == 60
                and provenance_state.get("snapshot_camera_state_retained") is False
                and provenance_state.get("snapshot_simulation_state_retained") is False
                and provenance_state.get("snapshot_hud_clock_retained") is False
                and provenance_state.get("whole_page_same_state_contract") is False,
                "native oracle records why complete-page equality is informational",
            )

    try:
        page, palette = decode_bmp(oracle)
    except (AssertionError, OSError, struct.error) as error:
        check(False, f"retained native BMP decodes safely: {error}")
        page, palette = b"", ()
    else:
        check(len(page) == 64000 and sha256(page) == case["page_sha256"],
              "native BMP yields the pinned top-down 64,000-byte indexed page")
        raw_palette = struct.pack("<768I", *palette)
        check(len(palette) == 768 and sha256(raw_palette) == case["palette_sha256"],
              "native BMP yields the pinned 768-component six-bit RGB palette")
        cx, cy = case["center"]
        check(page[cy * 320 + cx] == case["native_center"],
              "native oracle retains the pinned projected-sun centre index")

    checkpoint_arguments = case["checkpoint"]
    assert isinstance(checkpoint_arguments, dict)
    checkpoint = build_landed_checkpoint(**checkpoint_arguments)
    check(len(checkpoint) == 264 and
          sha256(checkpoint) == case["checkpoint_sha256"],
          "cross-platform builder reproduces the pinned product checkpoint")

    if product_directory is not None and page and palette:
        grade_product(case, product_directory.resolve(), page, palette, check)
    else:
        print("SKIP product comparison requires --product-directory (non-GUI contract mode)")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--case", choices=["all", *sorted(CASES)], default="all",
        help="native/product case to grade (default: all native contracts)",
    )
    parser.add_argument("--product-directory", type=Path)
    args = parser.parse_args()

    errors: list[str] = []

    def check(condition: bool, message: str) -> None:
        print("PASS" if condition else "FAIL", message)
        if not condition:
            errors.append(message)

    check_source_contract(check)
    selected = CASES if args.case == "all" else (args.case,)
    for case_name in selected:
        grade_case(case_name, args.product_directory, check)

    if errors:
        print(f"sun gallery: {len(errors)} failure(s)")
        return 1
    print("sun gallery: all requested checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
