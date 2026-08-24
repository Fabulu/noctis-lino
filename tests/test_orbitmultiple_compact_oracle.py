"""Grade a compact moon-and-companion orbital oracle independent of ROTOR IGNE."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "gen" / "recon_w7b" / "out"
ORACLE = OUT / "orbitmultiple_compact_3228_native.shot.BMP"
PROVENANCE = OUT / "orbitmultiple_compact_3228_native.provenance.json"
ECLIPSE = OUT / "orbitmultiple_compact_parent_eclipse_3227_native.shot.BMP"
ECLIPSE_PROVENANCE = (
    OUT / "orbitmultiple_compact_parent_eclipse_3227_native.provenance.json"
)
MKCURRENT = ROOT / "tests" / "gen" / "recon_w7b" / "mkcurrent.py"
CAPTURE_TOOL = ROOT / "tools" / "capture_noctis_scenes.ps1"
BMP_SHA256 = "2dd8a1470dd40def194363da9fe2be4100da57fdfbee9b95db64c69f7dbd547a"
PAGE_SHA256 = "7e8af381d96db273b9e4becfa056f0e6d56588143ad150a3a0517a24d8e54ec4"
PALETTE_SHA256 = "a23a8917d9dfdb0fbe8dea7422d58fa684ccc335a63a49f99fe269fc5fb33170"
PROVENANCE_SHA256 = "a0dd6dbdd86cbbf7a9ec3bce22bca86e88d8fbe50f004ff32b1aa8087cb4f877"
ECLIPSE_BMP_SHA256 = "16ca58d0b6c3324e87193b689f9f852672d94ec41fe722a526fce25d66b1816d"
ECLIPSE_PAGE_SHA256 = "d04299cf142c628866fb57e771c6ad671dbaa88f37ef60a10f1c7dc548aa0043"
ECLIPSE_PROVENANCE_SHA256 = (
    "af47195177a504590c03985903ea077a3fa0b743678b0ccdda2faba554086ad2"
)
STAR = (-546064, -439032, -1136208)
TARGET_SEED = (83, 100)
COMPANION_SEED = (232, 100)
ECLIPSE_NATIVE_TARGET_SEED = (155, 100)
ECLIPSE_PRODUCT_TARGET_SEED = (159, 100)
ECLIPSE_SOURCE_WINDOW = (120, 60, 205, 140)
DIAGNOSTIC_SIZES = (
    ("game-vh-out.bin", 156),
    ("game-sun-out.bin", 128),
    ("game-local-out.bin", 176),
    ("game-palette-out.bin", 3072),
    ("game-page-out.bin", 64000),
    ("game-s-background-out.bin", 64800),
    ("game-p-surfacemap-out.bin", 40000),
    ("game-p-background-out.bin", 65552),
    ("game-render-state-out.bin", 24),
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decode_bmp(data: bytes) -> tuple[bytes, tuple[int, ...]]:
    if len(data) != 65_078 or data[:2] != b"BM":
        raise AssertionError("expected one complete 65,078-byte indexed BMP")
    pixel_offset = struct.unpack_from("<I", data, 10)[0]
    width, height = struct.unpack_from("<ii", data, 18)
    depth = struct.unpack_from("<H", data, 28)[0]
    if (pixel_offset, width, height, depth) != (1078, 320, 200, 8):
        raise AssertionError("unexpected compact orbital BMP layout")
    palette = []
    for index in range(256):
        blue, green, red, reserved = data[54 + index * 4:58 + index * 4]
        if reserved or any(component & 3 for component in (red, green, blue)):
            raise AssertionError("compact orbital BMP palette is not exact six-bit BGR0")
        palette.extend((red >> 2, green >> 2, blue >> 2))
    rows = [
        data[pixel_offset + row * 320:pixel_offset + (row + 1) * 320]
        for row in range(200)
    ]
    rows.reverse()
    return b"".join(rows), tuple(palette)


def connected_component(
    page: bytes,
    seed: tuple[int, int],
    accepts,
) -> set[tuple[int, int]]:
    pending = [seed]
    points: set[tuple[int, int]] = set()
    while pending:
        x, y = pending.pop()
        if (x, y) in points or not (0 <= x < 320 and 0 <= y < 200):
            continue
        if not accepts(page[y * 320 + x]):
            continue
        points.add((x, y))
        pending.extend((
            (x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1),
            (x - 1, y - 1), (x + 1, y - 1),
            (x - 1, y + 1), (x + 1, y + 1),
        ))
    return points


def bounds(points: set[tuple[int, int]]) -> tuple[int, int, int, int] | None:
    if not points:
        return None
    return (
        min(x for x, _y in points), min(y for _x, y in points),
        max(x for x, _y in points), max(y for _x, y in points),
    )


def shifted(
    points: set[tuple[int, int]], dx: int, dy: int,
) -> set[tuple[int, int]]:
    return {(x + dx, y + dy) for x, y in points}


def window_pixel_count(
    page: bytes,
    window: tuple[int, int, int, int],
    accepts,
) -> int:
    left, top, right, bottom = window
    return sum(
        accepts(page[y * 320 + x])
        for y in range(top, bottom)
        for x in range(left, right)
    )


def product_paths(directory: Path) -> tuple[tuple[Path, int], ...]:
    return tuple(
        (directory / f"orbitmultiplecompact-{name}", size)
        for name, size in DIAGNOSTIC_SIZES
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-directory", type=Path)
    parser.add_argument("--eclipse-product-directory", type=Path)
    args = parser.parse_args()
    if args.eclipse_product_directory is not None and args.product_directory is None:
        parser.error("--eclipse-product-directory requires --product-directory as its positive control")
    failures: list[str] = []

    def check(condition: bool, message: str) -> None:
        print("PASS" if condition else "FAIL", message)
        if not condition:
            failures.append(message)

    capture = CAPTURE_TOOL.read_text(encoding="utf-8")
    compact_scene = capture.partition("@{ Name='orbitmultiplecompact'")[2].partition("},")[0]
    rotor_scene = capture.partition("@{ Name='orbitmultiple'")[2].partition("},")[0]
    check(
        "'orbitmultiplecompact'" in capture
        and all(token in compact_scene for token in (
            "X=-546064; Y=-439032; Z=-1136208; Body=3; Type=4",
            "Beta=0; Nav=162; Pitch=0",
            "PlayerX=0; PlayerY=0; PlayerZ=-500",
            "Sync=0; LocalX=0.0; LocalY=0.0; LocalZ=-0.05",
        )),
        "capture tool retains the compact exterior moon-and-companion pose",
    )
    check(
        all(token in rotor_scene for token in (
            "X=3866416; Y=-4813508; Z=-735695; Body=0; Type=5",
            "Beta=0; Nav=120; Pitch=-34",
            "OpenHud=$true; Sync=1",
        )),
        "independent compact scene leaves the ROTOR IGNE fixture unchanged",
    )

    sys.path.insert(0, str(ROOT / "noctis-harness"))
    import ns_spec  # noqa: E402

    system = ns_spec.System(*STAR)
    check(
        system.cls == 8 and system.nop == 3 and system.nob == 4
        and system.p_type[:4] == [9, 9, 10, 4]
        and system.p_owner[:4] == [-1, -1, -1, 2],
        "tracked generator identifies a compact class-8 [9,9,10,4] system",
    )
    check(
        abs(system.p_ray[2] - 8.94) < 1e-12
        and abs(system.p_ray[3] - 0.01449) < 1e-12,
        "generated companion and rocky moon retain their exact radii",
    )

    oracle_data = ORACLE.read_bytes()
    check(sha256(oracle_data) == BMP_SHA256,
          "retained compact native BMP has its pinned SHA-256")
    try:
        native_page, native_palette = decode_bmp(oracle_data)
    except (AssertionError, OSError, struct.error) as error:
        check(False, f"compact native BMP decodes safely: {error}")
        native_page, native_palette = b"", ()
    else:
        check(sha256(native_page) == PAGE_SHA256,
              "native oracle retains its complete indexed page")
        check(sha256(bytes(native_palette)) == PALETTE_SHA256,
              "native oracle retains all active six-bit palette components")

    native_source_core: set[tuple[int, int]] = set()
    if native_page:
        native_target = connected_component(
            native_page, TARGET_SEED, lambda value: value >> 6 == 2)
        native_companion = connected_component(
            native_page, COMPANION_SEED, lambda value: value > 64)
        native_core = connected_component(
            native_page, COMPANION_SEED, lambda value: value > 119)
        native_source_core = connected_component(
            native_page, COMPANION_SEED, lambda value: 96 <= value < 128)
        check(
            len(native_target) == 2723
            and bounds(native_target) == (51, 74, 115, 126),
            "native type-4 moon retains its complete terminator component",
        )
        check(
            len(native_companion) == 3427
            and bounds(native_companion) == (185, 43, 271, 141)
            and len(native_core) == 252
            and bounds(native_core) == (217, 91, 236, 108),
            "native type-10 parent retains a broad corona and radial core",
        )
        check(
            len(native_source_core) == 756
            and bounds(native_source_core) == (209, 83, 243, 116),
            "native positive control exposes the parent's bounded high-white core",
        )

    provenance_data = PROVENANCE.read_bytes()
    check(
        sha256(provenance_data.replace(b"\r\n", b"\n")) == PROVENANCE_SHA256,
        "compact native provenance has its pinned normalized SHA-256",
    )
    try:
        provenance = json.loads(provenance_data)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        check(False, f"compact native provenance decodes safely: {error}")
        provenance = {}
    continuity = provenance.get("continuity_after_snapshot", {})
    visibility = provenance.get("native_visibility", {})
    authority = provenance.get("authority", {})
    check(
        provenance.get("artifact_sha256") == BMP_SHA256
        and provenance.get("star") == list(STAR)
        and provenance.get("body_types") == [9, 9, 10, 4]
        and provenance.get("target_body") == 3
        and provenance.get("target_owner") == 2
        and provenance.get("companion_body") == 2,
        "provenance identifies the independent generated hierarchy",
    )
    check(
        provenance.get("camera") == {
            "position": [0.0, 0.0, -500.0],
            "user_alfa": 0.0,
            "user_beta": 0.0,
            "navigation_beta": 162.0,
        }
        and continuity.get("sync") == 0
        and continuity.get("ip_targetted") == 3
        and continuity.get("fcs_status") == "STANDBY"
        and abs(continuity.get("secs", 0) - 1345723227.8125) < 1e-9,
        "provenance brackets the exact native camera and adjacent-frame clock",
    )
    check(
        visibility.get("moon_terminator_and_companion_corona_visible_together") is True
        and authority.get("snapshot_camera_state_retained") is True
        and authority.get("snapshot_page_and_palette_retained") is True
        and authority.get("snapshot_simulation_state_retained") is False
        and authority.get("whole_page_same_state_contract") is False,
        "provenance limits grading to the retained joint-visibility contract",
    )

    eclipse_data = ECLIPSE.read_bytes()
    check(
        sha256(eclipse_data) == ECLIPSE_BMP_SHA256,
        "retained exact-clock parent-eclipse BMP has its pinned SHA-256",
    )
    try:
        eclipse_page, eclipse_palette = decode_bmp(eclipse_data)
    except (AssertionError, OSError, struct.error) as error:
        check(False, f"compact parent-eclipse BMP decodes safely: {error}")
        eclipse_page, eclipse_palette = b"", ()
    else:
        check(
            sha256(eclipse_page) == ECLIPSE_PAGE_SHA256,
            "parent-eclipse oracle retains its complete indexed page",
        )
        check(
            sha256(bytes(eclipse_palette)) == PALETTE_SHA256,
            "parent-eclipse oracle retains all active six-bit palette components",
        )

    eclipse_native_target: set[tuple[int, int]] = set()
    if eclipse_page:
        eclipse_native_target = connected_component(
            eclipse_page, ECLIPSE_NATIVE_TARGET_SEED,
            lambda value: value >> 6 == 2,
        )
        check(
            len(eclipse_native_target) == 19480
            and bounds(eclipse_native_target) == (69, 30, 241, 171),
            "native eclipse retains the complete central type-4 moon globe",
        )
        check(
            window_pixel_count(
                eclipse_page, ECLIPSE_SOURCE_WINDOW,
                lambda value: 96 <= value < 128,
            ) == 0,
            "native eclipse target removes every bounded high-white parent pixel",
        )

    eclipse_provenance_data = ECLIPSE_PROVENANCE.read_bytes()
    check(
        sha256(eclipse_provenance_data.replace(b"\r\n", b"\n")) ==
        ECLIPSE_PROVENANCE_SHA256,
        "parent-eclipse provenance has its pinned normalized SHA-256",
    )
    try:
        eclipse_provenance = json.loads(eclipse_provenance_data)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        check(False, f"parent-eclipse provenance decodes safely: {error}")
        eclipse_provenance = {}
    eclipse_system = eclipse_provenance.get("system", {})
    eclipse_camera = eclipse_provenance.get("camera", {})
    eclipse_native = eclipse_provenance.get("native_capture", {})
    eclipse_native_state = eclipse_native.get("eclipse", {})
    eclipse_positive_state = eclipse_native.get("positive_control", {})
    eclipse_products = eclipse_provenance.get("matched_product", {})
    eclipse_order = eclipse_provenance.get("renderer_order_contract", {})
    eclipse_raster = eclipse_provenance.get("indexed_raster_contract", {})
    eclipse_non_claims = eclipse_provenance.get("explicit_non_claims", {})
    check(
        eclipse_system == {
            "coordinates": list(STAR),
            "star_class": 8,
            "body_types": [9, 9, 10, 4],
            "target_body": 3,
            "target_owner": 2,
            "target_type": 4,
            "target_ray": 0.01449,
            "parent_body": 2,
            "parent_type": 10,
            "parent_ray": 8.94,
        },
        "parent-eclipse provenance identifies the exact generated hierarchy",
    )
    check(
        eclipse_camera == {
            "player": [0.0, 0.0, -500.0],
            "pitch": 0.0,
            "user_beta": 0.0,
            "navigation_beta": 144.0,
            "celestial_beta": 324.0,
        },
        "parent-eclipse provenance pins the exact exterior camera",
    )
    check(
        eclipse_native_state.get("bmp_sha256") == ECLIPSE_BMP_SHA256
        and eclipse_native_state.get("decoded_page_sha256") ==
        ECLIPSE_PAGE_SHA256
        and eclipse_native_state.get("six_bit_palette_sha256") == PALETTE_SHA256
        and eclipse_native_state.get("current_sha256") ==
        "d7aef1edca52bbfba07e4a3b1c36835250c2b0781e9db711ccba5fa1e9da9360"
        and eclipse_native_state.get("initial_clock") == 1345723226.0
        and eclipse_native_state.get("captured_clock") == 1345723227.0
        and eclipse_native_state.get("snapshot_wait_seconds") == 5
        and eclipse_native_state.get("sync") == 0
        and eclipse_native_state.get("target_reached") == 1
        and eclipse_native_state.get("draw_hud") == 0
        and eclipse_native_state.get("star_local") ==
        [1728.087772049359, -222.66334072733298, -167.73727823677473]
        and eclipse_native_state.get("bmp_vs_adapted_index_differences") == 24529,
        "parent-eclipse provenance retains the exact-clock settled native state",
    )
    check(
        "not draw_hud alone" in eclipse_native_state.get("draw_hud_limit", "")
        and "SYSTEM RESET" in eclipse_native_state.get("clock_method", "")
        and eclipse_positive_state.get("bmp_sha256") == BMP_SHA256
        and eclipse_positive_state.get("captured_clock") == 1345723227.8125
        and eclipse_positive_state.get("product_clock") == 1345723228,
        "provenance distinguishes settled overlay removal from its adjacent positive control",
    )
    check(
        eclipse_order.get("order") == [
            "type-10 parent white shell and flare",
            "primary premask and mask_pixels",
            "other bodies",
            "selected type-4 target globe",
        ]
        and eclipse_order.get("parent_distance") == 112.39022399999993
        and eclipse_order.get("lower_strict_gate") == 44.7
        and eclipse_order.get("upper_strict_gate") == 8940.0
        and eclipse_order.get("flare_admitted") is True
        and "later target globe overwrites" in eclipse_order.get("conclusion", ""),
        "provenance proves strict parent admission before target-globe overwrite",
    )
    check(
        eclipse_raster.get("eclipse_product_shift_to_native") == [-5, 2]
        and eclipse_raster.get("eclipse_shifted_overlap") == 19480
        and eclipse_raster.get("eclipse_shifted_native_only") == 0
        and eclipse_raster.get("eclipse_shifted_product_only") == 8
        and eclipse_raster.get("eclipse_native_source_core_pixels") == 0
        and eclipse_raster.get("eclipse_product_source_core_pixels") == 0
        and eclipse_raster.get("positive_native_source_core") == {
            "pixels": 756, "bbox": [209, 83, 243, 116],
        }
        and eclipse_raster.get("positive_product_source_core") == {
            "pixels": 737, "bbox": [209, 81, 242, 112],
        },
        "provenance pins shifted globe coverage and the positive/negative source core",
    )
    check(
        eclipse_non_claims.get("whole_page_equal") is False
        and eclipse_non_claims.get("whole_palette_equal") is False
        and eclipse_non_claims.get("same_state_bmp_and_adapted") is False
        and eclipse_non_claims.get("eclipse_native_product_index_differences") == 22842
        and eclipse_non_claims.get(
            "eclipse_native_product_palette_band_differences") == 1598
        and eclipse_non_claims.get(
            "eclipse_native_product_palette_component_differences") == 187
        and eclipse_non_claims.get("companion_intensity_tuning_supported") is False,
        "parent-eclipse provenance keeps full-page, palette, and tuning claims bounded",
    )

    try:
        mkcurrent_spec = importlib.util.spec_from_file_location(
            "orbitmultiple_compact_mkcurrent", MKCURRENT)
        if mkcurrent_spec is None or mkcurrent_spec.loader is None:
            raise RuntimeError("could not load mkcurrent.py")
        mkcurrent = importlib.util.module_from_spec(mkcurrent_spec)
        mkcurrent_spec.loader.exec_module(mkcurrent)
        rebuilt_eclipse, _star = mkcurrent.build(
            *STAR, 3, sync=0, secs=1345723226.0,
            charge=120, power=30000, draw_hud=0,
            pos=(0.0, 0.0, -500.0), angles=(0.0, 0.0, 144.0),
            local=(1728.0877720493675, -222.66334072733582,
                   -167.73727823688378),
        )
    except Exception as error:  # the generator imports the tracked model dynamically
        check(False, f"parent-eclipse native state rebuilds safely: {error}")
    else:
        check(
            len(rebuilt_eclipse) == 385
            and struct.unpack_from("<h", rebuilt_eclipse, 379)[0] == 0
            and sha256(rebuilt_eclipse) ==
            "d7aef1edca52bbfba07e4a3b1c36835250c2b0781e9db711ccba5fa1e9da9360",
            "mkcurrent reproduces the exact HUD-suppressed parent-eclipse state",
        )

    product_source_core: set[tuple[int, int]] = set()
    if args.product_directory is not None:
        directory = args.product_directory
        required = product_paths(directory)
        for path, size in required:
            check(path.is_file() and path.stat().st_size == size,
                  f"product emitted {path.name} at exactly {size} bytes")
        if all(path.is_file() and path.stat().st_size == size for path, size in required):
            positive_product_contract = eclipse_products.get("positive_control", {})
            positive_hashes = positive_product_contract.get("hashes", {})
            check(
                positive_hashes
                and all(
                    sha256(path.read_bytes()) == positive_hashes.get(path.name)
                    for path, _size in required
                ),
                "positive product diagnostics retain every provenance-pinned hash",
            )
            local = (directory / "orbitmultiplecompact-game-local-out.bin").read_bytes()
            page = (directory / "orbitmultiplecompact-game-page-out.bin").read_bytes()
            palette_data = (
                directory / "orbitmultiplecompact-game-palette-out.bin"
            ).read_bytes()
            product_palette = struct.unpack("<768I", palette_data)
            header = struct.unpack_from("<8i", local)
            binary64 = lambda unit: struct.unpack_from("<d", local, unit * 4)[0]
            ship = (binary64(8), binary64(10), binary64(12))
            target = (binary64(14), binary64(16), binary64(18))
            companion = (binary64(30), binary64(32), binary64(34))
            check(
                header[:2] == (0, 1) and header[3:] ==
                (1345723228, 3, 0, 162, 4),
                "product retains the matched exterior clock, target, and camera",
            )
            check(
                all(abs(value - expected) < 1e-12 for value, expected in zip(
                    ship, (0.0, 0.0, -0.05)))
                and abs(binary64(20) - 0.01449) < 1e-12
                and abs(binary64(22) - 0.05) < 1e-12,
                "product retains the exact moon-relative Stardrifter pose",
            )
            native_local = tuple(continuity.get("star_local", ()))
            product_local = tuple(target[index] + ship[index] for index in range(3))
            check(
                len(native_local) == 3 and all(
                    abs(native_local[index] - product_local[index]) < 0.000000001
                    for index in range(3)),
                "product and native retain the same star-relative Stardrifter position",
            )
            check(
                struct.unpack_from("<4i", local, 24 * 4)[:3] == (1, 89, 100),
                "product projects the rocky moon at the retained left-hand centre",
            )
            check(
                struct.unpack_from("<2i", local, 28 * 4) == (2, 10)
                and all(abs(value - expected) < 1e-9 for value, expected in zip(
                    companion, (66.67505933724146, 0.0, 90.50414965097791)))
                and struct.unpack_from("<3i", local, 40 * 4) == (1, 232, 100),
                "product projects and admits the separate type-10 parent flare",
            )

            product_target = connected_component(
                page, (89, 100), lambda value: value >> 6 == 2)
            product_companion = connected_component(
                page, (232, 100), lambda value: value > 64)
            product_core = connected_component(
                page, (232, 100), lambda value: value > 119)
            product_source_core = connected_component(
                page, (232, 100), lambda value: 96 <= value < 128)
            check(
                len(product_target) == 2780
                and bounds(product_target) == (57, 71, 121, 124),
                "product retains a substantial phase-bracketed moon terminator",
            )
            check(
                len(product_companion) > 2000
                and bounds(product_companion) is not None
                and bounds(product_companion)[0] <= 190
                and bounds(product_companion)[2] >= 260
                and len(product_core) > 200,
                "product companion is a broad indexed corona with a real core",
            )
            check(
                len(product_source_core) == 737
                and bounds(product_source_core) == (209, 81, 242, 112),
                "positive product control exposes the parent's bounded high-white core",
            )

            if native_page:
                index_mismatches = sum(a != b for a, b in zip(native_page, page))
                band_mismatches = sum(
                    (a & 0xC0) != (b & 0xC0)
                    for a, b in zip(native_page, page)
                )
                palette_mismatches = sum(
                    a != b for a, b in zip(native_palette, product_palette)
                )
                check(
                    len(product_target) >= 0.95 * len(native_target)
                    and len(product_companion) >= 0.55 * len(native_companion),
                    "product preserves substantial native globe and corona components",
                )
                print(
                    "INFO whole-page equality remains ungraded "
                    f"({index_mismatches} indices, {band_mismatches} bands, "
                    f"{palette_mismatches} palette components differ)"
                )
                print(
                    "INFO companion breadth remains open "
                    f"(native {len(native_companion)}, product {len(product_companion)})"
                )

    if args.eclipse_product_directory is not None:
        directory = args.eclipse_product_directory
        required = product_paths(directory)
        for path, size in required:
            check(
                path.is_file() and path.stat().st_size == size,
                f"eclipse product emitted {path.name} at exactly {size} bytes",
            )
        if all(path.is_file() and path.stat().st_size == size
               for path, size in required):
            product_contract = eclipse_products.get("eclipse", {})
            expected_hashes = product_contract.get("hashes", {})
            check(
                expected_hashes
                and all(
                    sha256(path.read_bytes()) == expected_hashes.get(path.name)
                    for path, _size in required
                ),
                "eclipse product diagnostics retain every provenance-pinned hash",
            )
            local = (directory / "orbitmultiplecompact-game-local-out.bin").read_bytes()
            page = (directory / "orbitmultiplecompact-game-page-out.bin").read_bytes()
            palette_data = (
                directory / "orbitmultiplecompact-game-palette-out.bin"
            ).read_bytes()
            product_palette = struct.unpack("<768I", palette_data)
            header = struct.unpack_from("<8i", local)
            binary64 = lambda unit: struct.unpack_from("<d", local, unit * 4)[0]
            ship = (binary64(8), binary64(10), binary64(12))
            target = (binary64(14), binary64(16), binary64(18))
            parent = (binary64(30), binary64(32), binary64(34))
            parent_distance = binary64(36)
            parent_ray = binary64(38)
            check(
                (header[0], header[1], *header[3:]) ==
                tuple(product_contract.get("local_header_ignoring_utc", ())),
                "eclipse product retains the exact clock, target, and camera header",
            )
            check(
                all(abs(value - expected) < 1e-12
                    for value, expected in zip(
                        ship, (-0.010680956489873435, 0.0,
                               -0.014488518504713672)))
                and all(abs(value - expected) < 1e-9
                        for value, expected in zip(
                            target, (1728.0984530058574,
                                     -222.66334072733582,
                                     -167.72278971837906)))
                and abs(binary64(20) - 0.01449) < 1e-12
                and abs(binary64(22) - 0.018) < 1e-12
                and struct.unpack_from("<3i", local, 24 * 4) == (1, 159, 100),
                "eclipse product retains the exact moon-relative pose and projection",
            )
            native_local = tuple(eclipse_native_state.get("star_local", ()))
            product_local = tuple(target[index] + ship[index] for index in range(3))
            check(
                len(native_local) == 3
                and all(abs(native_local[index] - product_local[index]) < 1e-9
                        for index in range(3)),
                "exact-clock product and native retain the same star-relative pose",
            )
            check(
                struct.unpack_from("<2i", local, 28 * 4) == (2, 10)
                and all(abs(value - expected) < 1e-9
                        for value, expected in zip(
                            parent, (66.69083846839602, 0.0,
                                     90.46488000960633)))
                and abs(parent_distance - 112.39022399999993) < 1e-12
                and abs(parent_ray - 8.94) < 1e-12
                and 5 * parent_ray < parent_distance < 1000 * parent_ray
                and struct.unpack_from("<3i", local, 40 * 4) == (1, 164, 100),
                "product independently projects and strictly admits the eclipsed parent",
            )

            eclipse_product_target = connected_component(
                page, ECLIPSE_PRODUCT_TARGET_SEED,
                lambda value: value >> 6 == 2,
            )
            shifted_product_target = shifted(eclipse_product_target, -5, 2)
            overlap = len(eclipse_native_target & shifted_product_target)
            native_only = len(eclipse_native_target - shifted_product_target)
            product_only = len(shifted_product_target - eclipse_native_target)
            check(
                len(eclipse_product_target) == 19488
                and bounds(eclipse_product_target) == (74, 28, 246, 169),
                "product eclipse retains the complete central type-4 moon globe",
            )
            check(
                overlap == 19480 and native_only == 0 and product_only == 8,
                "one explicit product shift covers the native globe plus eight edge pixels",
            )
            check(
                window_pixel_count(
                    page, ECLIPSE_SOURCE_WINDOW,
                    lambda value: 96 <= value < 128,
                ) == 0
                and len(native_source_core) == 756
                and len(product_source_core) == 737,
                "both eclipses hide the high-white parent shown by both positive controls",
            )
            if eclipse_page:
                index_mismatches = sum(
                    a != b for a, b in zip(eclipse_page, page))
                band_mismatches = sum(
                    (a & 0xC0) != (b & 0xC0)
                    for a, b in zip(eclipse_page, page)
                )
                palette_mismatches = sum(
                    a != b for a, b in zip(eclipse_palette, product_palette)
                )
                check(
                    (index_mismatches, band_mismatches, palette_mismatches) ==
                    (22842, 1598, 187),
                    "eclipse complete-page and palette non-claims remain pinned",
                )
                print(
                    "INFO parent source remains intentionally occluded "
                    f"({index_mismatches} indices, {band_mismatches} bands, "
                    f"{palette_mismatches} palette components differ)"
                )

    if failures:
        print(f"compact orbitmultiple oracle: {len(failures)} failure(s)")
        return 1
    print("compact orbitmultiple oracle: all requested checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
