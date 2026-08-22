"""Grade a retained native surface-sun frame against product diagnostics.

The default mode is non-GUI: it validates the pinned NIV+ BMP oracle and the
shipping diagnostic/export contracts.  The hosted native Apple-Silicon product
run supplies the product view, page, palette, and flare-state files.  Exact
whole-page equality is reported but cannot be graded until the native rig
retains the live camera and HUD state at the instant of its timed snapshot::

    python tests/test_sun_gallery.py --case hab-sun270 \
        --product-directory build/sun-gallery
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import struct
import sys


ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / "work" / "vhgame.txt"
NATIVE_LOOP = ROOT / "tests" / "gen" / "recon_nivplus_sheetbot" / "source" / "NOCTIS-1.CPP"
NATIVE_CAPTURE = ROOT / "tests" / "gen" / "recon_w7b" / "capture_w7b.ps1"
NATIVE_DRIVER = ROOT / "tests" / "gen" / "recon_w7b" / "godos_w7b.ps1"
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
        "bmp_sha256": "c08cdb6f74f82c83170848e0071e2f7c0c82cfb35d20d097a8db7409fcf76d84",
        "surface_sha256": "74eed5198ed6de0c725f610b05d5ee9a60a531fe64e1791e4fe363351febf1d6",
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
    }
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


def check_source_contract(check) -> None:
    game = GAME.read_text(encoding="utf-8")
    native_loop = NATIVE_LOOP.read_text(encoding="latin-1")
    native_capture = NATIVE_CAPTURE.read_text(encoding="utf-8")
    native_driver = NATIVE_DRIVER.read_text(encoding="utf-8")
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
    check("VHGsentinelquit" in game and
          "[VHGesc] = 1; [Quit Now] = YES;" in game,
          "explicit quit token exits only after complete sentinel diagnostics")
    check("'game-page-out.bin' = 64000" in capture and
          "'game-sun-out.bin' = 128" in capture and
          "'game-palette-out.bin' = 3072" in capture and
          "$Spec.Name, $entry.Key" in capture,
          "diagnostic capture validates and exports scene-qualified product files")
    check("[int]$Wait = 30" in native_capture and
          "[int]$TimeoutSec = 60" in native_capture and
          "autotype -w $Wait -p 3 b" in native_capture and
          "WaitForExit($TimeoutSec * 1000)" in native_driver and
          "Stop-Process -Id $p.Id -Force" in native_driver,
          "native rig keeps the timed BMP shot distinct from later timeout RAM")
    check("getsecs ();" in native_loop and
          "mouse_input ();" in native_loop and
          "if (w == 'b')" in native_loop and
          "snapshot (0, 0)" in native_loop,
          "native landed loop advances live time and input before the gallery shot")
    check("windows_hidden_process.run" in private_runner and
          "subprocess.run" in private_runner and
          "--default-desktop" in private_runner,
          "retained Windows diagnostic runner preserves both launch controls")
    check("CHECKPOINT_UNITS = 66" in checkpoint_tool and
          "struct.pack" in checkpoint_tool and
          "units[35:42]" in checkpoint_tool,
          "cross-platform checkpoint builder emits the stable 264-byte subset")
    check(all(fragment in macos_workflow for fragment in (
              "make_noctis_checkpoint.py",
              "--longitude 270",
              "--beta 270",
              "--pitch -44",
              '"clock=1344638527"',
              "--case hab-sun270",
              "--product-directory build/sun-gallery",
          )),
          "hosted Apple-Silicon gate executes the pinned product comparison")
    check("Grade the pinned habitable-world sun frame" not in windows_workflow,
          "Windows packaging no longer depends on an unusable hosted GUI desktop")


def grade_product(case: dict[str, object], directory: Path, oracle_page: bytes,
                  oracle_palette: tuple[int, ...], check) -> None:
    scene = str(case["scene"])
    page_path = directory / f"{scene}-game-page-out.bin"
    palette_path = directory / f"{scene}-game-palette-out.bin"
    sun_path = directory / f"{scene}-game-sun-out.bin"
    view_path = directory / f"{scene}-game-vh-out.bin"

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
        check(not band_differences,
              f"all product pixels retain the native palette band ({detail})")
        cx, cy = case["center"]
        center_offset = cy * 320 + cx
        check(page[center_offset] == oracle_page[center_offset] == 126,
              "product page retains the native indexed flare-centre sample 126")
        # Surface.BIN authenticates the native resume input, not the later live
        # frame: the rig types `b` after 30 seconds but dumps RAM only when the
        # emulator is killed at 60 seconds.  The landed loop advances input and
        # ordinary HUD time in between.  Until snapshot-time state is retained,
        # a whole-page mismatch is evidence to report, not a same-state failure.
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
        check(palette == oracle_palette,
              f"all 768 six-bit product palette components match native ({detail})")

    sun_data = sun_path.read_bytes()
    if len(sun_data) == 128:
        sun = struct.unpack("<32i", sun_data)
        floats = struct.unpack("<32f", sun_data)
        cx, cy = case["center"]
        check(sun[0] == 1 and sun[1] == 1 and sun[2] == 3,
              "product diagnostic identifies landed type-3 rendering")
        check(sun[4] == 1 and sun[5] == 0 and floats[6] == 0.0,
              "product diagnostic retains clear daytime atmosphere")
        check(sun[16] == 1,
              "product diagnostic confirms the source flare gate is active")
        check(abs(sun[17] - cx) <= 1 and abs(sun[18] - cy) <= 1,
              f"product flare centre {sun[17]},{sun[18]} aligns with native {cx},{cy}")
        check(abs(floats[7] - 35.9996) < 0.01 and
              abs(floats[8] - 243.633) < 0.01,
              "product retains the pinned native exposure and live solar distance")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=sorted(CASES), default="hab-sun270")
    parser.add_argument("--product-directory", type=Path)
    args = parser.parse_args()

    errors: list[str] = []

    def check(condition: bool, message: str) -> None:
        print("PASS" if condition else "FAIL", message)
        if not condition:
            errors.append(message)

    case = CASES[args.case]
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
              "native oracle records longitude 270 and heading 270 explicitly")

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
        check(page[cy * 320 + cx] == 126,
              "native positive flare retains indexed centre sample 126")

    checkpoint_arguments = case["checkpoint"]
    assert isinstance(checkpoint_arguments, dict)
    checkpoint = build_landed_checkpoint(**checkpoint_arguments)
    check(len(checkpoint) == 264 and
          sha256(checkpoint) == case["checkpoint_sha256"],
          "cross-platform builder reproduces the pinned habitable checkpoint")

    check_source_contract(check)
    if args.product_directory is not None and page and palette:
        grade_product(case, args.product_directory.resolve(), page, palette, check)
    else:
        print("SKIP product comparison requires --product-directory (non-GUI contract mode)")

    if errors:
        print(f"sun gallery: {len(errors)} failure(s)")
        return 1
    print("sun gallery: all requested checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
