"""Grade retained native surface-sun frames against product diagnostics.

The default mode is non-GUI: it validates a pinned NIV+ BMP oracle and the
shipping diagnostic/export contracts.  The hosted native Apple-Silicon product
run supplies the product view, page, palette, and flare-state files.  Exact
whole-page and post-smoothing palette-index equality are reported but cannot be
graded where the native rig did not retain the live camera, simulation, and HUD
state at the instant of its timed snapshot::

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
              "make_noctis_checkpoint.py",
              "--longitude 270",
              "--beta 270",
              "--pitch -44",
              '"clock=1344638527"',
              "--case hab-sun270",
              "--product-directory build/sun-gallery",
          )),
          "hosted Apple-Silicon gate executes the pinned habitable product comparison")
    check(all(fragment in macos_workflow for fragment in (
              "--body 2 --longitude 45 --latitude 60",
              "--beta 90 --pitch -30",
              "--player-x 1645000 --player-z 1641000 --fast",
              "--case thin-sun45",
              "build/macos-aarch64-thin-sun-oracle.txt",
              "build/sun-gallery/thin-game-*-out.bin",
          )),
          "hosted Apple-Silicon gate executes and retains the pinned thin-world comparison")
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
        check(
            (page[center_offset] & 0xC0)
            == (oracle_page[center_offset] & 0xC0)
            == 64,
            "product flare centre retains the native sky palette band after source smoothing",
        )
        # The retained BMP authenticates the native view and indexed output, but
        # these historical captures do not retain every live HUD/simulation value
        # at the screenshot instant.  Exact whole-page and low-six-bit centre
        # equality therefore remain informational: the source's two post-render
        # psmooth_64 passes mix the centre with snapshot-dependent neighbours.
        # The complete palette, palette bands, and pinned sun state below are the
        # admissible cross-product contracts.
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
              "product diagnostic confirms the expected source flare gate")
        check(64 <= sun[19] <= 127,
              "product diagnostic retains the sky-band sample that admitted the flare")
        check(abs(sun[17] - cx) <= 1 and abs(sun[18] - cy) <= 1,
              f"product flare centre {sun[17]},{sun[18]} aligns with native {cx},{cy}")
        check(
            abs(floats[7] - expected["exposure"]) < 0.01
            and abs(floats[8] - expected["distance"]) < 0.01,
            "product retains the pinned native exposure and live solar distance",
        )
        if "ray" in expected:
            check(abs(floats[9] - expected["ray"]) < 0.001,
                  "product retains the pinned native stellar ray")


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
        check(page[cy * 320 + cx] == 126,
              "native positive flare retains indexed centre sample 126")

    checkpoint_arguments = case["checkpoint"]
    assert isinstance(checkpoint_arguments, dict)
    checkpoint = build_landed_checkpoint(**checkpoint_arguments)
    check(len(checkpoint) == 264 and
          sha256(checkpoint) == case["checkpoint_sha256"],
          "cross-platform builder reproduces the pinned product checkpoint")

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
