"""Grade the retained BISTARIAL/SORZ class-10 surface-sun oracle.

The native BMP authenticates the visible landed result.  Post-snapshot native
continuity and retained product diagnostics authenticate the pose and prove that
the ordinary radial distance gate is open while the class-10 exclusion suppresses
its spokes.  Whole-page equality is deliberately not a same-state contract.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import struct


ROOT = Path(__file__).resolve().parents[1]
ORACLE_ROOT = ROOT / "tests" / "native-oracles" / "quartz-class10-sun333"
GROUND = ROOT / "work" / "vhground.txt"

RETAINED = {
    "README.md": (
        4079, "b5a8374dbcbeae496bb5d431efaaf4700d428f3f969625ab9f777ca2a9643e54",
    ),
    "native-capture.cmd": (
        77, "1054cdca274994e7771f958056c4402109e8bb3b1ba8c98b493227ff5dd0f1bc",
    ),
    "native.CURRENT.BIN": (
        385, "bec49d24ba3bc946ea774768a96b401f7db0d0e998bc0de84a05620a7ce5d57f",
    ),
    "native.shot.BMP": (
        65078, "384c61522050fb75a63994dc1569e484b769d056c671845d272b09112f68876a",
    ),
    "native.SURFACE.BIN": (
        40, "742e907ee37d877ee6a720787d769d9aaba1723e511be9130d77221437e54d52",
    ),
    "product.CURRENT.LIN": (
        264, "d300e89708c8c6043cea06d4806ab3e7a9a24a236ef5f480451ae24c3667cc7c",
    ),
    "product-local.bin": (
        176, "da7a1883067a5f52b2c52349282a92a4d434af9693f9aa759e835ece5a200261",
    ),
    "product-page.bin": (
        64000, "846a72617a070ba4ff94dc40618c410421de655d797a983de2637e33ed9e2a9d",
    ),
    "product-palette.bin": (
        3072, "d8c5ee1c69ab373a2670511c1d020ceb66e19153873abc615270d1a6f27c7e40",
    ),
    "product-sun.bin": (
        128, "eeaaf19ce8d1951ee79af6d53163d331749067303c8013ea0d64f1653693f1c0",
    ),
    "product-vh.bin": (
        156, "f78bfc9837bc608a243018d55377287a351f366f8c0c75f075af84f8d8cdfe08",
    ),
    "provenance.json": (
        5418, "0f9ed75fda4a1d39add6343cc141309a25ef695ec40d16625eb5b944ce0a7ce0",
    ),
}
NATIVE_PAGE_SHA256 = "2477cfc669cbfd537321c72f262a141eec1b05c59f0b8700f5cc0f409d62f6cd"
PALETTE_SHA256 = "d8c5ee1c69ab373a2670511c1d020ceb66e19153873abc615270d1a6f27c7e40"
SUN_CROP = (145, 88, 171, 110)
UPPER_SKY_CROP = (40, 10, 310, 120)
SCENE = "quartzclass10"
PRODUCT_FILES = {
    "view": ("game-vh-out.bin", 156),
    "sun": ("game-sun-out.bin", 128),
    "local": ("game-local-out.bin", 176),
    "palette": ("game-palette-out.bin", 3072),
    "page": ("game-page-out.bin", 64000),
}


CURRENT_OFFSETS = {
    "sync": (0, "b"),
    "ip_targetted": (11, "b"),
    "ip_reached": (13, "b"),
    "power": (27, "h"),
    "star_class": (35, "h"),
    "nearstar_nop": (37, "h"),
    "player_x": (39, "f"),
    "player_y": (43, "f"),
    "player_z": (47, "f"),
    "pitch": (51, "f"),
    "heading": (55, "f"),
    "navigation": (59, "f"),
    "star_ray": (67, "f"),
    "clock": (235, "d"),
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decode_bmp(data: bytes) -> tuple[bytes, tuple[int, ...]]:
    if len(data) != 65078 or data[:2] != b"BM":
        raise AssertionError("expected the complete 65,078-byte indexed BMP")
    declared_size = struct.unpack_from("<I", data, 2)[0]
    pixel_offset = struct.unpack_from("<I", data, 10)[0]
    dib_size, width, height, planes, depth, compression = struct.unpack_from(
        "<IiiHHI", data, 14
    )
    # NIV+ retains the historical stale size fields; the actual indexed extent,
    # dimensions, and pinned whole-file hash are authoritative.
    if declared_size != 116326:
        raise AssertionError(f"unexpected historical BMP size field {declared_size}")
    if (pixel_offset, dib_size, width, height, planes, depth, compression) != (
        1078, 40, 320, 200, 1, 8, 0,
    ):
        raise AssertionError("unexpected class-10 BMP layout")

    palette: list[int] = []
    for index in range(256):
        blue, green, red, reserved = data[54 + 4 * index:58 + 4 * index]
        if reserved or any(component & 3 for component in (red, green, blue)):
            raise AssertionError(f"palette entry {index} is not exact six-bit BGR0")
        palette.extend((red >> 2, green >> 2, blue >> 2))

    pixels = data[pixel_offset:pixel_offset + 64000]
    rows = [pixels[row * 320:(row + 1) * 320] for row in range(200)]
    rows.reverse()
    return b"".join(rows), tuple(palette)


def page_crop(page: bytes, box: tuple[int, int, int, int]) -> bytes:
    x0, y0, x1, y1 = box
    if not (0 <= x0 < x1 <= 320 and 0 <= y0 < y1 <= 200):
        raise AssertionError(f"invalid page crop {box}")
    return b"".join(page[y * 320 + x0:y * 320 + x1] for y in range(y0, y1))


def product_file(directory: Path, name: str) -> Path:
    prefixed = directory / f"{SCENE}-{name}"
    return prefixed if prefixed.is_file() else directory / name


def load_product(directory: Path, check) -> dict[str, bytes] | None:
    product: dict[str, bytes] = {}
    for key, (name, size) in PRODUCT_FILES.items():
        path = product_file(directory, name)
        try:
            data = path.read_bytes()
        except OSError as error:
            check(False, f"current product {path.name} is readable: {error}")
            continue
        check(len(data) == size, f"current product emitted {path.name} at exactly {size} bytes")
        if len(data) == size:
            product[key] = data
    return product if len(product) == len(PRODUCT_FILES) else None


def decode_current(data: bytes) -> dict[str, int | float]:
    if len(data) != 385:
        raise AssertionError("expected exact 385-byte NIV+ continuity input")
    return {
        name: struct.unpack_from(f"<{kind}", data, offset)[0]
        for name, (offset, kind) in CURRENT_OFFSETS.items()
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-directory", type=Path)
    args = parser.parse_args()

    failures: list[str] = []

    def check(condition: bool, message: str) -> None:
        print("PASS" if condition else "FAIL", message)
        if not condition:
            failures.append(message)

    retained: dict[str, bytes] = {}
    for name, (expected_size, expected_hash) in RETAINED.items():
        path = ORACLE_ROOT / name
        try:
            data = path.read_bytes()
        except OSError as error:
            check(False, f"retained {name} is readable: {error}")
            continue
        retained[name] = data
        check(
            len(data) == expected_size and sha256(data) == expected_hash,
            f"retained {name} has its pinned size and SHA-256",
        )
    if len(retained) != len(RETAINED):
        print(f"FAIL {len(failures)} class-10 surface-oracle checks")
        return 1

    product = {
        "view": retained["product-vh.bin"],
        "sun": retained["product-sun.bin"],
        "local": retained["product-local.bin"],
        "palette": retained["product-palette.bin"],
        "page": retained["product-page.bin"],
    }
    if args.product_directory is not None:
        current_product = load_product(args.product_directory.resolve(), check)
        if current_product is None:
            print(f"FAIL {len(failures)} class-10 surface-oracle checks")
            return 1
        product = current_product

    try:
        provenance = json.loads(retained["provenance.json"])
        native_page, native_palette = decode_bmp(retained["native.shot.BMP"])
        native_current = decode_current(retained["native.CURRENT.BIN"])
        native_surface = struct.unpack("<hhiiiifffff", retained["native.SURFACE.BIN"])
        product_checkpoint = struct.unpack("<66i", retained["product.CURRENT.LIN"])
        product_view = struct.unpack("<39i", product["view"])
        product_sun = struct.unpack("<32i", product["sun"])
        product_sun_floats = struct.unpack("<32f", product["sun"])
        product_local = struct.unpack("<44i", product["local"])
        product_palette = struct.unpack("<768I", product["palette"])
    except (AssertionError, json.JSONDecodeError, struct.error, UnicodeDecodeError) as error:
        check(False, f"retained class-10 oracle decodes safely: {error}")
        return 1

    check(
        len(native_page) == 64000 and sha256(native_page) == NATIVE_PAGE_SHA256,
        "native BMP yields the pinned top-down 64,000-byte indexed page",
    )
    native_palette_bytes = struct.pack("<768I", *native_palette)
    check(
        len(native_palette) == 768 and sha256(native_palette_bytes) == PALETTE_SHA256,
        "native BMP yields the pinned 768-component six-bit RGB palette",
    )
    check(
        native_surface == (
            333, 60, 100, 100, 8192, 8192,
            1638400.0, 1.0, 1638400.0, -30.0, 270.0,
        ),
        "native surface input retains the authored type-8 landed pose",
    )
    check(
        native_current == {
            "sync": 1,
            "ip_targetted": 1,
            "ip_reached": 1,
            "power": 30000,
            "star_class": 10,
            "nearstar_nop": 2,
            "player_x": 0.0,
            "player_y": 0.0,
            "player_z": -500.0,
            "pitch": 0.0,
            "heading": 0.0,
            "navigation": 0.0,
            "star_ray": 30.8439998626709,
            "clock": 1344638497.0,
        },
        "native continuity input targets body 1 of the class-10 two-body system",
    )
    check(
        product_checkpoint[:9] == (
            0x56485356, 15, 1, 1, 1638400, -600, 1638400, -30, 270,
        )
        and product_checkpoint[24:28] == (5411056, -7441017, -1775473, 1)
        and product_checkpoint[35:42] == (1344638527, 642, 426, 1, 12, 333, 60),
        "product checkpoint retains the matched landed star, body, camera, and clock",
    )

    candidate = provenance.get("candidate", {})
    generated = candidate.get("generated_system", {})
    check(
        provenance.get("schema") == 1
        and provenance.get("case") == "bistarial-class10-sun333"
        and candidate.get("star") == [5411056, -7441017, -1775473]
        and candidate.get("star_label") == "BISTARIAL/SORZ"
        and candidate.get("star_class") == 10
        and math.isclose(candidate.get("star_ray", 0), 30.8439998626709,
                         rel_tol=0, abs_tol=1e-15)
        and generated == {
            "nop": 2,
            "nob": 2,
            "body_index": 1,
            "body_owner": -1,
            "body_owner_role": "primary",
            "body_type": 8,
            "body_ray": 0.031824,
        },
        "provenance identifies the authentic class-10 primary-owned quartz body",
    )
    check(
        candidate.get("surface_pose") == {
            "clock": 1344638527,
            "longitude": 333,
            "latitude": 60,
            "player": [1638400, 1, 1638400],
            "pitch": -30,
            "heading": 270,
        },
        "provenance retains the authored BISTARIAL/SORZ surface pose",
    )

    product_provenance = provenance.get("product", {})
    native_provenance = provenance.get("native", {})
    check(
        product_provenance.get("checkpoint") == "product.CURRENT.LIN"
        and product_provenance.get("checkpoint_sha256") == RETAINED["product.CURRENT.LIN"][1]
        and product_provenance.get("diagnostic_sha256") == {
            name: RETAINED[name][1]
            for name in (
                "product-vh.bin", "product-sun.bin", "product-local.bin",
                "product-palette.bin", "product-page.bin",
            )
        }
        and product_provenance.get("private_desktop") is True,
        "provenance names only the retained product checkpoint and diagnostics",
    )
    check(
        native_provenance.get("current") == "native.CURRENT.BIN"
        and native_provenance.get("current_sha256") == RETAINED["native.CURRENT.BIN"][1]
        and native_provenance.get("surface") == "native.SURFACE.BIN"
        and native_provenance.get("surface_sha256") == RETAINED["native.SURFACE.BIN"][1]
        and native_provenance.get("command") == "native-capture.cmd"
        and native_provenance.get("command_sha256") == RETAINED["native-capture.cmd"][1]
        and native_provenance.get("bmp") == "native.shot.BMP"
        and native_provenance.get("bmp_sha256") == RETAINED["native.shot.BMP"][1]
        and native_provenance.get("frozen_ram_retained") is False
        and native_provenance.get("post_snapshot_adapted_retained") is False,
        "provenance separates retained native artifacts from capture-only RAM",
    )
    continuity = native_provenance.get("continuity", {})
    check(
        continuity == {
            "offset": 206300,
            "sync": 1,
            "ip_targetted": 1,
            "ip_reached": 1,
            "landed": 1,
            "star_class": 10,
            "nearstar_nop": 2,
            "star_ray": 30.8439998626709,
            "player": [1638400.0, -45056.0, 1638400.0],
            "pitch": -30.0,
            "heading_normalized": -90.0,
            "navigation_angle": 0.0,
            "frozen_clock": 1344638526.9,
        },
        "post-snapshot native continuity retains the landed class-10 camera and clock",
    )

    check(
        product_view[:5] == (1638400, -45656, 1638400, -30, -90)
        and product_view[10:13] == (30000, 0, 10)
        and math.isclose(struct.unpack_from("<f", product["view"], 13 * 4)[0],
                         30.8439998626709, rel_tol=0, abs_tol=1e-15)
        and product_view[14:17] == (2, 2, 1),
        "product view diagnostic retains the landed camera and generated stellar state",
    )
    check(
        product_local[:2] == (1, 0)
        and product_local[3:8] == (1344638527, 1, -90, 0, 8)
        and math.isclose(
            struct.unpack_from("<d", product["local"], 20 * 4)[0],
            0.031824, rel_tol=0, abs_tol=1e-15,
        )
        and product_local[28] == -1,
        "product local diagnostic retains body 1, type 8, its radius, and no companion",
    )
    if args.product_directory is not None:
        print(
            "INFO current generated-system epoch is not graded "
            f"({product_local[2]}; retained capture {1345695831})"
        )

    distance = product_sun_floats[8]
    ray = product_sun_floats[9]
    primary = tuple(
        struct.unpack_from("<d", product["sun"], unit * 4)[0]
        for unit in (10, 12, 14)
    )
    check(
        product_sun[:6] == (1, 1, 8, 10, 1, 0)
        and product_sun_floats[6] == 0.0
        and math.isclose(product_sun_floats[7], 29.7388, rel_tol=0, abs_tol=0.0001)
        and math.isclose(distance, 400.133026, rel_tol=0, abs_tol=0.0001)
        and math.isclose(ray, 30.8439998626709, rel_tol=0, abs_tol=1e-15)
        and abs(math.sqrt(sum(component * component for component in primary)) - distance) < 0.00002,
        "product sun diagnostic retains the landed day state and live primary vector",
    )
    check(
        10.0 * ray < distance < 1000.0 * ray,
        "product primary distance is strictly inside the ordinary radial-flare interval",
    )
    ground = GROUND.read_text(encoding="utf-8")
    check(
        candidate.get("star_class") == 10
        and "A = [nsclass]; ? A = 5 -> VHGND primary flare done;" in ground
        and "? A = 6 -> VHGND primary flare done; ? A = 10 -> VHGND primary flare done;" in ground
        and product_sun[16:20] == (0, 0, 0, 0),
        "source class-10 exclusion suppresses spokes despite the admitted distance",
    )

    check(
        all(component <= 63 for component in product_palette)
        and product_palette == native_palette,
        "all 768 six-bit product palette components exactly match native",
    )
    product_page = product["page"]
    native_sun = page_crop(native_page, SUN_CROP)
    product_sun_crop = page_crop(product_page, SUN_CROP)
    check(
        len(native_sun) == 572 and product_sun_crop == native_sun,
        "all 572 indices in the half-open native/product sun-core crop are exact",
    )
    native_upper = page_crop(native_page, UPPER_SKY_CROP)
    product_upper = page_crop(product_page, UPPER_SKY_CROP)
    upper_band_mismatches = sum(
        (native & 0xC0) != (product & 0xC0)
        for native, product in zip(native_upper, product_upper)
    )
    check(
        len(native_upper) == 29700 and upper_band_mismatches == 0,
        "all 29,700 upper-sky indices retain their native palette bands",
    )

    comparison = provenance.get("native_product_comparison", {})
    authority = provenance.get("authority", {})
    check(
        comparison.get("sun_core_crop") == list(SUN_CROP)
        and comparison.get("sun_core_crop_pixels") == 572
        and comparison.get("sun_core_exact") is True
        and comparison.get("upper_sky_crop") == list(UPPER_SKY_CROP)
        and comparison.get("upper_sky_crop_pixels") == 29700
        and comparison.get("upper_sky_palette_band_mismatches") == 0,
        "provenance records only the supported crop and palette-band visual contracts",
    )
    check(
        authority.get("native_snapshot_page_and_palette_retained") is True
        and authority.get("native_post_snapshot_camera_state_retained") is True
        and authority.get("native_snapshot_simulation_state_retained") is False
        and authority.get("native_live_distance_retained") is False
        and authority.get("whole_page_same_state_contract") is False,
        "authority explicitly rejects native live-distance and whole-page claims",
    )

    whole_index_mismatches = sum(
        native != product for native, product in zip(native_page, product_page)
    )
    whole_band_mismatches = sum(
        (native & 0xC0) != (product & 0xC0)
        for native, product in zip(native_page, product_page)
    )
    print(
        "INFO whole-page equality is not graded "
        f"({whole_index_mismatches} index, {whole_band_mismatches} palette-band mismatches)"
    )
    print(
        "INFO post-snapshot adapted-page equality is not graded "
        f"({native_provenance.get('bmp_vs_post_snapshot_page_mismatches')} mismatches)"
    )

    if failures:
        print(f"FAIL {len(failures)} class-10 surface-oracle checks")
        return 1
    print("PASS BISTARIAL/SORZ class-10 surface-sun oracle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
