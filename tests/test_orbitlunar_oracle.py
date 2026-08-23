"""Grade native lunar exterior, interior, limb, roof, and cupola-boundary oracles."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct


ROOT = Path(__file__).resolve().parents[1]
ORACLE_ROOT = ROOT / "tests" / "gen" / "recon_w7b" / "out"
EXTERIOR = ORACLE_ROOT / "orbitlunar_exterior_8736_native.shot.BMP"
INTERIOR = ORACLE_ROOT / "orbitlunar_interior_8736_native.shot.BMP"
LIMB = ORACLE_ROOT / "orbitlunar_limb_pair_8736_native.shot.BMP"
ROOF = ORACLE_ROOT / "orbitlunar_roof_8737_native.shot.BMP"
ROOF_ADAPTED = ORACLE_ROOT / "orbitlunar_roof_8737_native.adapted"
BOUNDARY_INSIDE = ORACLE_ROOT / "orbitlunar_cupola_boundary_inside_8737_native.shot.BMP"
BOUNDARY_ROOF = ORACLE_ROOT / "orbitlunar_cupola_boundary_roof_8737_native.shot.BMP"
PROVENANCE = ORACLE_ROOT / "orbitlunar_camera_pair_8736_native.provenance.json"
LIMB_PROVENANCE = ORACLE_ROOT / "orbitlunar_limb_pair_8736_native.provenance.json"
ROOF_PROVENANCE = ORACLE_ROOT / "orbitlunar_roof_8737_native.provenance.json"
BOUNDARY_PROVENANCE = ORACLE_ROOT / "orbitlunar_cupola_boundary_8737_native.provenance.json"
CAPTURE = ROOT / "tools" / "capture_noctis_scenes.ps1"
EXTERIOR_SHA256 = "89579c32aaee28a93e5b28675921ca055a72c870fb1e00b9381308d3ab9aa559"
INTERIOR_SHA256 = "f26d65b7c6a96aed4e34b7b4389cbfd65777e499f521a08f1e2d970ecdc20667"
LIMB_SHA256 = "c35d22468bdf6e83a181dde4fca6567285268b7b4abb05997b86ab1e8db583c0"
ROOF_SHA256 = "eac49d33b4596d74bee1896e37c344c84145668fa4367bf38f36da2e4b01cc06"
ROOF_ADAPTED_SHA256 = "a3cf70e2861584f4aee90f10226c691ee2a0c055eadf3f06dc5032b93a0d1539"
BOUNDARY_INSIDE_SHA256 = "07873d1191f192135c4050c619230264eebba85114d850b19cf4e12237b5cd0b"
BOUNDARY_INSIDE_ADAPTED_SHA256 = "b4d23838f12a91ebe2b67b291a7d8b6704ec1371af484eb663399314d731989f"
BOUNDARY_ROOF_SHA256 = "b2af5163ef04975a09d05043adb486f511205ef5654511b314677961a2a9dcdf"
BOUNDARY_ROOF_ADAPTED_SHA256 = "c4388de9bd149dea19864c8be6970cffa9167bc9128e6ed7bf7f19f2278ca7ea"
PROVENANCE_SHA256 = "2fcaea57d37f6e745942799d230dba252b873b439254ff3a73acb461d7500f45"
LIMB_PROVENANCE_SHA256 = "e98ee55bc77c8b0b9462cd66693da0e3bcbb96883e2b39c81598f7a336c39644"
ROOF_PROVENANCE_SHA256 = "a980eb8e695f91bbe72556893965d927dd60ac706a1b0843a52f380d72893e1d"
BOUNDARY_PROVENANCE_SHA256 = "198d1db85982088bde7509cbae2a6c47af5db3eac10b7732ee33449f01ec4c95"
PALETTE_SHA256 = "3f78ddd2036be9d6308517d9baff0c3f0d6b181bf46b6f93cd987e4200e98077"
INTERIOR_CROP = (30, 30, 180, 150)
INTERIOR_STATUS_CROP = (215, 160, 315, 190)
INTERIOR_BAND_SHA256 = "9652c9d0bcd76afa6917a52287633fc55b17dbef148db003813045438fd29bdb"
PRODUCT_INTERIOR_CROP_SHA256 = "c0ecb6a4f83c25e2e4f8155adead874be686643d37bc9747f61dafc7b5a8050f"
PRODUCT_INTERIOR_STATUS_SHA256 = "5f2a5a1c0fef751c0b8d359f4b886a54e89959c68311e0d029ed3afa20c524e8"
PRODUCT_INTERIOR_EXACT_INDICES = 17395
PRODUCT_INTERIOR_BRIGHTNESS = (8338, 8338, 8215, 8215)
LIMB_CROP = (10, 75, 90, 125)
LIMB_BAND_SHA256 = "9f7d58392998a5134aba50a131a59dde46c60be997ad446e161bda6bad511be0"
ROOF_CUPOLA_CROP = (10, 10, 310, 124)
ROOF_CUPOLA_INDEX_SHA256 = "f5e1422cd1daa982c3f92c572783c66eb27002299abe53dadb8b747883b478d3"
ROOF_CUPOLA_BAND_SHA256 = "1583adc5d2112dbea1f9898eeb26298ab777e3e06c1ced44f0189de68fc4bf45"
ROOF_HULL_CROP = (10, 124, 310, 190)
ROOF_HULL_INDEX_SHA256 = "9ac54f78e3f15c35df6b9bf60e0e949043a16c5bdf911cd529b1b80ab60669be"
ROOF_HULL_BAND_SHA256 = "b19a7b0de250f12d3670b81fe2fdcffccef6bc492ce6509525344d653e9eb923"
BOUNDARY_STATUS_CROP = (215, 160, 315, 190)
BOUNDARY_STATUS_INSIDE_SHA256 = "b01071ff806103b1223185b35282aacee691da7ca123c0ad53527914a79a2e37"
BOUNDARY_STATUS_ROOF_SHA256 = "b6fc311eea84bb7772eaf716f091a9719e1b8d022dc550900fb0e078634dff61"
BOUNDARY_STATUS_BAND_SHA256 = "60dd0511b3f6976a2e00fde549b9dc2a6a2b5aed1f776dba51d054c5eb553cb9"
BOUNDARY_TELEMETRY_CROP = (20, 140, 130, 182)
BOUNDARY_TELEMETRY_INSIDE_SHA256 = "2e9601d722a08754da45c990f015dee37716f260f822fd9c6beba6c02f8933cf"
BOUNDARY_TELEMETRY_ROOF_SHA256 = "3509a6265431f94460016074ea8f05cb95b744dc7981a2fbc21a548bd773bd1e"
BOUNDARY_LABEL_CROP = (27, 19, 294, 56)
BOUNDARY_LABEL_INSIDE_SHA256 = "495e8a2f4c68da9c7a5df93e906242934045fac38a8093e6cf7c8d5d3c1e8440"
BOUNDARY_LABEL_ROOF_SHA256 = "b8d447ca893d1aca46c7c427dfd1895e412640a89385cedd5715d1fade9cf9a5"
BOUNDARY_LABEL_BAND_SHA256 = "d33498e16b51ef474a86b2c7ea87676524f1954b39f67a2a9093dcd284aff78d"
ENVIRONMENT_GLYPH_CROP = (2, 192, 30, 197)
ENVIRONMENT_GLYPH_MASK_PIXELS = 69
ENVIRONMENT_GLYPH_MASK_SHA256 = "c9e6820e33c2dd344609b6d37d9eebc9462c786f6fb1d6640c21e0334c5a5941"
PRODUCT_BOUNDARY_STATUS_INSIDE_SHA256 = "af8dcb9a9dddfc09395804d136d3351f6d4a4973611ff23b5dac4946b08701dc"
PRODUCT_BOUNDARY_STATUS_ROOF_SHA256 = "2753eb145b19a5add9a9436a9b901e24844d1d713dc525a86803db9587d8ef4b"
PRODUCT_BOUNDARY_TELEMETRY_INSIDE_SHA256 = "1dfb3ab0ce02fe7beecd279a9231df77fd09824dc8b4c1829f09e80e6a0ccbd4"
PRODUCT_BOUNDARY_LABEL_INSIDE_SHA256 = "14597bc2053644ca0fb7f13bf239d4397b44a8078e18cddc67389bcd83da19ff"
PRODUCT_BOUNDARY_LABEL_ROOF_SHA256 = "bf06789b74452cf147d1bff2af08505c093acfeddfbc86bf85b3169055c41d88"
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


def decode_bmp(path: Path) -> tuple[bytes, tuple[int, ...]]:
    data = path.read_bytes()
    if len(data) != 65078 or data[:2] != b"BM":
        raise AssertionError(f"{path.name}: expected a complete 65,078-byte indexed BMP")
    pixel_offset = struct.unpack_from("<I", data, 10)[0]
    width, height = struct.unpack_from("<ii", data, 18)
    depth = struct.unpack_from("<H", data, 28)[0]
    if (pixel_offset, width, height, depth) != (1078, 320, 200, 8):
        raise AssertionError(f"{path.name}: unexpected BMP layout")
    palette = []
    for index in range(256):
        blue, green, red, reserved = data[54 + index * 4:58 + index * 4]
        if reserved or any(component & 3 for component in (red, green, blue)):
            raise AssertionError(f"{path.name}: palette is not exact six-bit BGR0")
        palette.extend((red >> 2, green >> 2, blue >> 2))
    pixels = data[pixel_offset:pixel_offset + 64000]
    rows = [pixels[row * 320:(row + 1) * 320] for row in range(200)]
    rows.reverse()
    return b"".join(rows), tuple(palette)


def crop_indices(page: bytes, box: tuple[int, int, int, int]) -> bytes:
    x0, y0, x1, y1 = box
    return bytes(page[y * 320 + x]
                 for y in range(y0, y1) for x in range(x0, x1))


def normalized_glyph_mask(
        page: bytes, box: tuple[int, int, int, int]) -> bytes:
    """Ignore unstable palette indices while retaining text and lamp geometry."""
    x0, y0, x1, y1 = box
    mask = bytearray()
    for y in range(y0, y1):
        row = page[y * 320:(y + 1) * 320]
        background = Counter(row).most_common(1)[0][0]
        mask.extend(page[y * 320 + x] != background for x in range(x0, x1))
    return bytes(mask)


def crop_bands(page: bytes, box: tuple[int, int, int, int]) -> bytes:
    return bytes(index >> 6 for index in crop_indices(page, box))


def band_geometry(page: bytes, band: int) -> tuple[int, tuple[int, int, int, int]]:
    points = [(x, y) for y in range(200) for x in range(320)
              if page[y * 320 + x] >> 6 == band]
    if not points:
        return 0, (0, 0, 0, 0)
    return len(points), (
        min(x for x, _y in points), min(y for _x, y in points),
        max(x for x, _y in points), max(y for _x, y in points),
    )


def bright_crop_count(page: bytes, palette: tuple[int, ...]) -> int:
    x0, y0, x1, y1 = INTERIOR_CROP
    return sum(
        max(palette[page[y * 320 + x] * 3:page[y * 320 + x] * 3 + 3]) > 32
        for y in range(y0, y1) for x in range(x0, x1)
    )


def bright_mask(page: bytes, palette: tuple[int, ...],
                box: tuple[int, int, int, int]) -> bytes:
    x0, y0, x1, y1 = box
    return bytes(
        max(palette[page[y * 320 + x] * 3:page[y * 320 + x] * 3 + 3]) > 32
        for y in range(y0, y1) for x in range(x0, x1)
    )


def diagnostic_paths(directory: Path) -> tuple[tuple[Path, int], ...]:
    return tuple((directory / f"orbitlunar-{name}", size)
                 for name, size in DIAGNOSTIC_SIZES)


def grade_product(directory: Path, camera_beta: int, native_page: bytes,
                  native_palette: tuple[int, ...], native_local: tuple[float, ...],
                  view: str, check) -> None:
    required = diagnostic_paths(directory)
    for path, size in required:
        check(path.is_file() and path.stat().st_size == size,
              f"product emitted {path.name} at exactly {size} bytes")
    if not all(path.is_file() and path.stat().st_size == size
               for path, size in required):
        return

    local = (directory / "orbitlunar-game-local-out.bin").read_bytes()
    header = struct.unpack_from("<8i", local)
    binary64 = lambda unit: struct.unpack_from("<d", local, unit * 4)[0]
    ship = (binary64(8), binary64(10), binary64(12))
    target = (binary64(14), binary64(16), binary64(18))
    product_local = tuple(target[index] + ship[index] for index in range(3))
    expected_clock = 1344638737 if view == "roof" else 1344638736
    check(
        header[:2] == (0, 1) and header[3:] ==
        (expected_clock, 0, camera_beta, 0, 1),
        "product retains the matched class-0/type-1 orbital clock and camera",
    )
    check(
        all(abs(native_local[index] - product_local[index]) < 0.000001
            for index in range(3)),
        "product brackets the native Stardrifter position within one millionth",
    )
    expected_distance = 0.012845967758806344 if view == "roof" else 0.01283555
    check(abs(binary64(20) - 0.007128) < 1e-12
          and abs(binary64(22) - expected_distance) < 1e-12,
          "product retains the native lunar radius and target distance")

    if view == "roof":
        view_state = struct.unpack(
            "<39i", (directory / "orbitlunar-game-vh-out.bin").read_bytes())
        check(view_state[:5] == (0, -750, -1900, 0, 180),
              "product retains the stable roof position and outward camera")

    sun = struct.unpack("<32i", (directory / "orbitlunar-game-sun-out.bin").read_bytes())
    check(sun[:4] == (0, 1, 1, 0),
          "product diagnostics identify local flight, the type-1 target, and class-0 star")

    page = (directory / "orbitlunar-game-page-out.bin").read_bytes()
    palette = struct.unpack(
        "<768I", (directory / "orbitlunar-game-palette-out.bin").read_bytes())
    check(not any(palette[3 * 128:3 * 192]),
          "planet-state product leaves the absent moon palette band black")
    if view == "interior":
        native_crop = crop_indices(native_page, INTERIOR_CROP)
        product_crop = crop_indices(page, INTERIOR_CROP)
        native_bands = crop_bands(native_page, INTERIOR_CROP)
        product_bands = crop_bands(page, INTERIOR_CROP)
        check(product_bands == native_bands,
              "product exactly retains the native interior/primary-flare palette-band geometry")
        exact = sum(native == product
                    for native, product in zip(native_crop, product_crop))
        check(sha256(product_crop) == PRODUCT_INTERIOR_CROP_SHA256
              and exact == PRODUCT_INTERIOR_EXACT_INDICES,
              "matched open-HUD product retains the pinned interior-flare indices")
        check(sha256(crop_indices(page, INTERIOR_STATUS_CROP)) ==
              PRODUCT_INTERIOR_STATUS_SHA256,
              "matched fixed-chase product renders the source TRACKING status")
        brightness = (
            bright_crop_count(native_page, native_palette),
            bright_crop_count(native_page, palette),
            bright_crop_count(page, native_palette),
            bright_crop_count(page, palette),
        )
        check(
            brightness == PRODUCT_INTERIOR_BRIGHTNESS
            and native_crop.count(77) == product_crop.count(77) == 0,
            "four-way interior brightness isolates the 123-pixel deficit to indexed raster state",
        )
        print("INFO interior-flare brightness remains ungraded "
              f"(native/native {brightness[0]}, native/product {brightness[1]}, "
              f"product/native {brightness[2]}, product/product {brightness[3]}; "
              "palette contribution zero)")
    elif view == "limb":
        native_bands = crop_bands(native_page, LIMB_CROP)
        product_bands = crop_bands(page, LIMB_CROP)
        check(product_bands == native_bands,
              "product exactly retains the native primary-window palette-band geometry")
        check(bright_mask(page, palette, LIMB_CROP) ==
              bright_mask(native_page, native_palette, LIMB_CROP),
              "product exactly retains the native primary-window brightness mask")
        check(band_geometry(page, 3) == (8535, (106, 51, 216, 148)),
              "product retains the bounded native lunar limb silhouette")
        globe_differences = [
            index for index, (native, product) in enumerate(zip(native_page, page))
            if (native >> 6 == 3) != (product >> 6 == 3)
        ]
        check(
            len(globe_differences) <= 99 and all(
                106 <= index % 320 <= 217 and 51 <= index // 320 <= 148
                for index in globe_differences
            ),
            "the beside-primary globe mask differs only at 99 bounded limb pixels",
        )
    elif view == "roof":
        exact_page = sum(native == product
                         for native, product in zip(native_page, page))
        band_differences = sum(
            native >> 6 != product >> 6
            for native, product in zip(native_page, page)
        )
        check(exact_page >= 59800 and band_differences <= 2850,
              "product retains at least 59,800 exact roof-view indices and bounded bands")

        native_cupola = crop_indices(native_page, ROOF_CUPOLA_CROP)
        product_cupola = crop_indices(page, ROOF_CUPOLA_CROP)
        cupola_exact = sum(native == product
                           for native, product in zip(native_cupola, product_cupola))
        cupola_band_differences = sum(
            native >> 6 != product >> 6
            for native, product in zip(native_cupola, product_cupola)
        )
        check(cupola_exact >= 31900 and cupola_band_differences <= 1660,
              "product retains the upper exterior cupola and roof-aperture geometry")

        native_hull = crop_indices(native_page, ROOF_HULL_CROP)
        product_hull = crop_indices(page, ROOF_HULL_CROP)
        hull_exact = sum(native == product
                         for native, product in zip(native_hull, product_hull))
        hull_band_differences = sum(
            native >> 6 != product >> 6
            for native, product in zip(native_hull, product_hull)
        )
        check(hull_exact >= 18500 and hull_band_differences <= 1190,
              "product retains the bounded roof-view hull geometry")
        print("INFO roof lighting remains ungraded "
              f"(cupola native {sum(bright_mask(native_page, native_palette, ROOF_CUPOLA_CROP))}, "
              f"product {sum(bright_mask(page, palette, ROOF_CUPOLA_CROP))}; "
              f"hull native {sum(bright_mask(native_page, native_palette, ROOF_HULL_CROP))}, "
              f"product {sum(bright_mask(page, palette, ROOF_HULL_CROP))})")
    else:
        count, bounding_box = band_geometry(page, 3)
        check(bounding_box == (98, 52, 216, 149) and 9232 <= count <= 9267,
              "product retains the native exterior lunar globe silhouette")
        band_differences = [
            index for index, (native, product) in enumerate(zip(native_page, page))
            if native >> 6 != product >> 6
        ]
        check(
            len(band_differences) <= 35 and all(
                native_page[index] >> 6 == 1
                and page[index] >> 6 == 3
                and 98 <= index % 320 <= 216
                and 52 <= index // 320 <= 149
                for index in band_differences
            ),
            "outside at most 35 product-only limb pixels, the exterior palette bands are exact",
        )

    mismatches = sum(a != b for a, b in zip(native_page, page))
    palette_mismatches = sum(a != b for a, b in zip(native_palette, palette))
    print(f"INFO complete-page equality is not graded ({mismatches} index mismatches)")
    print(f"INFO complete-palette equality is not graded ({palette_mismatches} component mismatches)")


def grade_boundary_product_pair(
        inside_directory: Path, roof_directory: Path,
        native_inside_page: bytes, native_inside_palette: tuple[int, ...],
        native_roof_page: bytes, native_roof_palette: tuple[int, ...],
        native_local: tuple[float, ...], check) -> None:
    directories = {
        "inside": (inside_directory, -500),
        "roof": (roof_directory, -501),
    }
    for label, (directory, _player_y) in directories.items():
        for path, size in diagnostic_paths(directory):
            check(path.is_file() and path.stat().st_size == size,
                  f"boundary {label} product emitted {path.name} at exactly {size} bytes")
    if not all(
            path.is_file() and path.stat().st_size == size
            for directory, _player_y in directories.values()
            for path, size in diagnostic_paths(directory)):
        return

    product = {}
    for label, (directory, player_y) in directories.items():
        local = (directory / "orbitlunar-game-local-out.bin").read_bytes()
        header = struct.unpack_from("<8i", local)
        binary64 = lambda unit: struct.unpack_from("<d", local, unit * 4)[0]
        ship = (binary64(8), binary64(10), binary64(12))
        target = (binary64(14), binary64(16), binary64(18))
        product_local = tuple(target[index] + ship[index] for index in range(3))
        check(
            header[:2] == (0, 1) and header[3:] ==
            (1344638737, 0, 180, 0, 1),
            f"boundary {label} product retains the matched orbital clock and camera",
        )
        check(
            all(abs(native_local[index] - product_local[index]) < 0.000001
                for index in range(3))
            and abs(binary64(20) - 0.007128) < 1e-12
            and abs(binary64(22) - 0.012845967758806344) < 1e-12,
            f"boundary {label} product retains the native local pose, radius, and distance",
        )
        view_state = struct.unpack(
            "<39i", (directory / "orbitlunar-game-vh-out.bin").read_bytes())
        check(view_state[:5] == (0, player_y, -1900, 0, 180),
              f"boundary {label} product retains its exact one-unit camera")
        sun = struct.unpack(
            "<32i", (directory / "orbitlunar-game-sun-out.bin").read_bytes())
        check(sun[:4] == (0, 1, 1, 0),
              f"boundary {label} product retains the class-0/type-1 local context")
        product[label] = (
            (directory / "orbitlunar-game-page-out.bin").read_bytes(),
            struct.unpack(
                "<768I", (directory / "orbitlunar-game-palette-out.bin").read_bytes()),
        )

    inside_page, inside_palette = product["inside"]
    roof_page, roof_palette = product["roof"]
    check(
        not any(inside_palette[3 * 128:3 * 192])
        and not any(roof_palette[3 * 128:3 * 192]),
        "boundary planet-state products leave the absent moon palette band black",
    )
    roof_exact = sum(native == current
                     for native, current in zip(native_roof_page, roof_page))
    roof_band_differences = sum(
        native >> 6 != current >> 6
        for native, current in zip(native_roof_page, roof_page)
    )
    check(roof_exact >= 61000 and roof_band_differences <= 1600,
          "product retains the native just-outside roof composition with bounded bands")

    native_inside_status = sum(bright_mask(
        native_inside_page, native_inside_palette, BOUNDARY_STATUS_CROP))
    native_roof_status = sum(bright_mask(
        native_roof_page, native_roof_palette, BOUNDARY_STATUS_CROP))
    product_inside_status_indices = crop_indices(
        inside_page, BOUNDARY_STATUS_CROP)
    product_roof_status_indices = crop_indices(
        roof_page, BOUNDARY_STATUS_CROP)
    product_inside_status = sum(bright_mask(
        inside_page, inside_palette, BOUNDARY_STATUS_CROP))
    product_roof_status = sum(bright_mask(
        roof_page, roof_palette, BOUNDARY_STATUS_CROP))
    # The complete product palette is intentionally ungraded and differs between
    # otherwise index-identical private launches.  Pin the stronger stable raster
    # contract here, while retaining the paired visibility/suppression delta.
    check(
        native_inside_status - native_roof_status == 465
        and sha256(product_inside_status_indices) ==
        PRODUCT_BOUNDARY_STATUS_INSIDE_SHA256
        and sha256(product_roof_status_indices) ==
        PRODUCT_BOUNDARY_STATUS_ROOF_SHA256
        and product_roof_status <= 220
        and product_inside_status - product_roof_status >= 350,
        "product crosses the strict boundary and suppresses the exact interior status raster",
    )

    product_inside_labels = crop_indices(inside_page, BOUNDARY_LABEL_CROP)
    product_roof_labels = crop_indices(roof_page, BOUNDARY_LABEL_CROP)
    check(
        sha256(product_inside_labels) == PRODUCT_BOUNDARY_LABEL_INSIDE_SHA256
        and sha256(product_roof_labels) == PRODUCT_BOUNDARY_LABEL_ROOF_SHA256,
        "product restores the fixed upper target-label raster only inside",
    )

    native_environment_indices = crop_indices(
        native_inside_page, ENVIRONMENT_GLYPH_CROP)
    native_environment = normalized_glyph_mask(
        native_inside_page, ENVIRONMENT_GLYPH_CROP)
    product_inside_environment_indices = crop_indices(
        inside_page, ENVIRONMENT_GLYPH_CROP)
    product_roof_environment_indices = crop_indices(
        roof_page, ENVIRONMENT_GLYPH_CROP)
    product_inside_environment = normalized_glyph_mask(
        inside_page, ENVIRONMENT_GLYPH_CROP)
    product_roof_environment = normalized_glyph_mask(
        roof_page, ENVIRONMENT_GLYPH_CROP)
    check(
        product_inside_environment_indices == native_environment_indices
        and product_roof_environment_indices == native_environment_indices
        and product_inside_environment == native_environment
        and product_roof_environment == native_environment
        and sum(product_inside_environment) == ENVIRONMENT_GLYPH_MASK_PIXELS
        and sha256(product_inside_environment) == ENVIRONMENT_GLYPH_MASK_SHA256,
        "product restores the exact environmental glyph and lamp-fringe mask in both modes",
    )

    native_roof_telemetry = crop_indices(
        native_roof_page, BOUNDARY_TELEMETRY_CROP)
    product_inside_telemetry_indices = crop_indices(
        inside_page, BOUNDARY_TELEMETRY_CROP)
    product_roof_telemetry = crop_indices(
        roof_page, BOUNDARY_TELEMETRY_CROP)
    check(
        sha256(product_inside_telemetry_indices) ==
        PRODUCT_BOUNDARY_TELEMETRY_INSIDE_SHA256
        and product_roof_telemetry == native_roof_telemetry,
        "product restores the exact inside range raster and retains the roof early-return crop",
    )

    inside_exact = sum(native == current
                       for native, current in zip(native_inside_page, inside_page))
    inside_band_differences = sum(
        native >> 6 != current >> 6
        for native, current in zip(native_inside_page, inside_page)
    )
    native_inside_telemetry = sum(bright_mask(
        native_inside_page, native_inside_palette, BOUNDARY_TELEMETRY_CROP))
    product_inside_telemetry = sum(bright_mask(
        inside_page, inside_palette, BOUNDARY_TELEMETRY_CROP))
    product_roof_telemetry_bright = sum(bright_mask(
        roof_page, roof_palette, BOUNDARY_TELEMETRY_CROP))
    check(
        native_inside_telemetry == 601
        and product_inside_telemetry >= 600
        and product_inside_telemetry - product_roof_telemetry_bright >= 500,
        "product restores materially visible inside L.Y. and DYAMS telemetry",
    )
    print("INFO complete inside-boundary parity remains open "
          f"({inside_exact} exact indices, {inside_band_differences} band differences; "
          f"native/product telemetry brightness {native_inside_telemetry}/"
          f"{product_inside_telemetry})")
    print("INFO boundary palettes remain ungraded "
          f"(inside {sum(a != b for a, b in zip(native_inside_palette, inside_palette))}, "
          f"roof {sum(a != b for a, b in zip(native_roof_palette, roof_palette))} "
          "component mismatches)")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exterior-product-directory", type=Path)
    parser.add_argument("--interior-product-directory", type=Path)
    parser.add_argument("--limb-product-directory", type=Path)
    parser.add_argument("--roof-product-directory", type=Path)
    parser.add_argument("--boundary-inside-product-directory", type=Path)
    parser.add_argument("--boundary-roof-product-directory", type=Path)
    args = parser.parse_args()
    if ((args.boundary_inside_product_directory is None) !=
            (args.boundary_roof_product_directory is None)):
        parser.error("boundary inside and roof product directories must be supplied together")
    failures = []

    def check(condition: bool, message: str) -> None:
        print("PASS" if condition else "FAIL", message)
        if not condition:
            failures.append(message)

    exterior_data = EXTERIOR.read_bytes()
    interior_data = INTERIOR.read_bytes()
    limb_data = LIMB.read_bytes()
    roof_data = ROOF.read_bytes()
    roof_adapted = ROOF_ADAPTED.read_bytes()
    boundary_inside_data = BOUNDARY_INSIDE.read_bytes()
    boundary_roof_data = BOUNDARY_ROOF.read_bytes()
    check(sha256(exterior_data) == EXTERIOR_SHA256,
          "retained lunar exterior BMP has its pinned SHA-256")
    check(sha256(interior_data) == INTERIOR_SHA256,
          "retained Stardrifter-interior BMP has its pinned SHA-256")
    check(sha256(limb_data) == LIMB_SHA256,
          "retained lunar limb-pair BMP has its pinned SHA-256")
    check(sha256(roof_data) == ROOF_SHA256,
          "retained Stardrifter roof BMP has its pinned SHA-256")
    check(len(roof_adapted) == 65540
          and sha256(roof_adapted) == ROOF_ADAPTED_SHA256,
          "retained post-snapshot roof state has its pinned size and SHA-256")
    check(sha256(boundary_inside_data) == BOUNDARY_INSIDE_SHA256,
          "retained just-inside cupola-boundary BMP has its pinned SHA-256")
    check(sha256(boundary_roof_data) == BOUNDARY_ROOF_SHA256,
          "retained just-outside cupola-boundary BMP has its pinned SHA-256")
    try:
        exterior_page, exterior_palette = decode_bmp(EXTERIOR)
        interior_page, interior_palette = decode_bmp(INTERIOR)
        limb_page, limb_palette = decode_bmp(LIMB)
        roof_page, roof_palette = decode_bmp(ROOF)
        boundary_inside_page, boundary_inside_palette = decode_bmp(BOUNDARY_INSIDE)
        boundary_roof_page, boundary_roof_palette = decode_bmp(BOUNDARY_ROOF)
    except (AssertionError, OSError, struct.error) as error:
        check(False, f"lunar native BMPs decode safely: {error}")
        exterior_page = interior_page = limb_page = roof_page = b""
        boundary_inside_page = boundary_roof_page = b""
        exterior_palette = interior_palette = limb_palette = roof_palette = ()
        boundary_inside_palette = boundary_roof_palette = ()
    else:
        check(sha256(exterior_page) ==
              "e032b578eff11f78ca220dbfa5f6df0aae4c4940f7b93ebbf3d47f7b6df2d83a",
              "native exterior retains its complete indexed page")
        check(sha256(interior_page) ==
              "ea08058aff4715a5ef9c27a27dcc27af134660653ce7edfaef251dce146e73fc",
              "native interior retains its complete indexed page")
        check(sha256(limb_page) ==
              "e888c0a1a1e1174ec13c6bace5319aa210a2092d64a2f742b21ff92882ecfb5f",
              "native limb pair retains its complete indexed page")
        check(sha256(roof_page) ==
              "87c6f02bb3a4df3f8e4b92eb5d2089d22302d4fa7836113d54202d0280b741c9",
              "native roof view retains its complete indexed page")
        check(sha256(boundary_inside_page) ==
              "1a622a00990b9be780d6dfa3311291657ac6722541dfea10eed07d163abe4bed",
              "native just-inside boundary retains its complete indexed page")
        check(sha256(boundary_roof_page) ==
              "021b27b9b824f4d090fbd7aa0beca4d5fe780eebd3a14f8e694256ae83d8a950",
              "native just-outside boundary retains its complete indexed page")
        check(roof_page == roof_adapted[:64000],
              "native roof BMP exactly retains the frozen post-snapshot framebuffer")
        check(sha256(bytes(exterior_palette)) == PALETTE_SHA256
              and exterior_palette == interior_palette == limb_palette == roof_palette
              == boundary_inside_palette == boundary_roof_palette,
              "all native lunar views retain the same exact active six-bit palette")
        check(band_geometry(exterior_page, 3) == (9232, (98, 52, 216, 149)),
              "native exterior retains the complete lunar globe silhouette")
        interior_bands = crop_bands(interior_page, INTERIOR_CROP)
        check(sha256(interior_bands) == INTERIOR_BAND_SHA256
              and interior_bands.count(0) == 10799
              and interior_bands.count(1) == 7201,
              "native interior retains the primary corona, rays, and Stardrifter occlusion")
        limb_bands = crop_bands(limb_page, LIMB_CROP)
        check(sha256(limb_bands) == LIMB_BAND_SHA256
              and limb_bands.count(0) == 2408
              and limb_bands.count(1) == 1592
              and band_geometry(limb_page, 3) == (8620, (106, 51, 217, 148)),
              "native limb view retains the primary beside the dark lunar globe")
        roof_cupola = crop_indices(roof_page, ROOF_CUPOLA_CROP)
        roof_cupola_bands = crop_bands(roof_page, ROOF_CUPOLA_CROP)
        check(sha256(roof_cupola) == ROOF_CUPOLA_INDEX_SHA256
              and sha256(roof_cupola_bands) == ROOF_CUPOLA_BAND_SHA256
              and roof_cupola_bands.count(0) == 4299
              and roof_cupola_bands.count(1) == 29901
              and sum(bright_mask(roof_page, roof_palette,
                                  ROOF_CUPOLA_CROP)) == 21521,
              "native roof view retains the upper cupola, grid, and aperture")
        roof_hull = crop_indices(roof_page, ROOF_HULL_CROP)
        roof_hull_bands = crop_bands(roof_page, ROOF_HULL_CROP)
        check(sha256(roof_hull) == ROOF_HULL_INDEX_SHA256
              and sha256(roof_hull_bands) == ROOF_HULL_BAND_SHA256
              and roof_hull_bands.count(0) == 17860
              and roof_hull_bands.count(1) == 1940
              and sum(bright_mask(roof_page, roof_palette,
                                  ROOF_HULL_CROP)) == 622,
              "native roof view retains the exterior hull below the aperture")

        boundary_pair_exact = sum(
            inside == outside
            for inside, outside in zip(boundary_inside_page, boundary_roof_page)
        )
        boundary_pair_band_differences = sum(
            inside >> 6 != outside >> 6
            for inside, outside in zip(boundary_inside_page, boundary_roof_page)
        )
        check(boundary_pair_exact == 59428
              and boundary_pair_band_differences == 649,
              "native one-unit pair retains its complete strict-boundary delta")

        boundary_inside_status = crop_indices(
            boundary_inside_page, BOUNDARY_STATUS_CROP)
        boundary_roof_status = crop_indices(
            boundary_roof_page, BOUNDARY_STATUS_CROP)
        boundary_inside_status_bright = bright_mask(
            boundary_inside_page, boundary_inside_palette, BOUNDARY_STATUS_CROP)
        boundary_roof_status_bright = bright_mask(
            boundary_roof_page, boundary_roof_palette, BOUNDARY_STATUS_CROP)
        check(
            sha256(boundary_inside_status) == BOUNDARY_STATUS_INSIDE_SHA256
            and sha256(boundary_roof_status) == BOUNDARY_STATUS_ROOF_SHA256
            and sha256(crop_bands(
                boundary_inside_page, BOUNDARY_STATUS_CROP)) ==
            BOUNDARY_STATUS_BAND_SHA256
            and crop_bands(boundary_inside_page, BOUNDARY_STATUS_CROP) ==
            crop_bands(boundary_roof_page, BOUNDARY_STATUS_CROP)
            and sum(boundary_inside_status_bright) == 699
            and sum(boundary_roof_status_bright) == 234
            and sum(inside and not outside for inside, outside in zip(
                boundary_inside_status_bright, boundary_roof_status_bright)) == 465,
            "native inside boundary adds the FCS status before the roof early return",
        )

        boundary_inside_telemetry = crop_indices(
            boundary_inside_page, BOUNDARY_TELEMETRY_CROP)
        boundary_roof_telemetry = crop_indices(
            boundary_roof_page, BOUNDARY_TELEMETRY_CROP)
        boundary_inside_telemetry_bright = bright_mask(
            boundary_inside_page, boundary_inside_palette, BOUNDARY_TELEMETRY_CROP)
        boundary_roof_telemetry_bright = bright_mask(
            boundary_roof_page, boundary_roof_palette, BOUNDARY_TELEMETRY_CROP)
        check(
            sha256(boundary_inside_telemetry) == BOUNDARY_TELEMETRY_INSIDE_SHA256
            and sha256(boundary_roof_telemetry) == BOUNDARY_TELEMETRY_ROOF_SHA256
            and sum(boundary_inside_telemetry_bright) == 601
            and sum(boundary_roof_telemetry_bright) == 63
            and sum(inside and not outside for inside, outside in zip(
                boundary_inside_telemetry_bright,
                boundary_roof_telemetry_bright)) == 538,
            "native inside boundary adds target telemetry that the roof branch omits",
        )

        boundary_inside_labels = crop_indices(
            boundary_inside_page, BOUNDARY_LABEL_CROP)
        boundary_roof_labels = crop_indices(
            boundary_roof_page, BOUNDARY_LABEL_CROP)
        boundary_inside_labels_bright = bright_mask(
            boundary_inside_page, boundary_inside_palette, BOUNDARY_LABEL_CROP)
        boundary_roof_labels_bright = bright_mask(
            boundary_roof_page, boundary_roof_palette, BOUNDARY_LABEL_CROP)
        check(
            sha256(boundary_inside_labels) == BOUNDARY_LABEL_INSIDE_SHA256
            and sha256(boundary_roof_labels) == BOUNDARY_LABEL_ROOF_SHA256
            and sha256(crop_bands(
                boundary_inside_page, BOUNDARY_LABEL_CROP)) ==
            BOUNDARY_LABEL_BAND_SHA256
            and crop_bands(boundary_inside_page, BOUNDARY_LABEL_CROP) ==
            crop_bands(boundary_roof_page, BOUNDARY_LABEL_CROP)
            and sum(boundary_inside_labels_bright) == 6522
            and sum(boundary_roof_labels_bright) == 6247
            and sum(inside and not outside for inside, outside in zip(
                boundary_inside_labels_bright,
                boundary_roof_labels_bright)) == 275,
            "native inside boundary adds both upper target-label rows before the roof return",
        )

        boundary_inside_environment_indices = crop_indices(
            boundary_inside_page, ENVIRONMENT_GLYPH_CROP)
        boundary_roof_environment_indices = crop_indices(
            boundary_roof_page, ENVIRONMENT_GLYPH_CROP)
        boundary_inside_environment = normalized_glyph_mask(
            boundary_inside_page, ENVIRONMENT_GLYPH_CROP)
        boundary_roof_environment = normalized_glyph_mask(
            boundary_roof_page, ENVIRONMENT_GLYPH_CROP)
        check(
            boundary_inside_environment_indices == boundary_roof_environment_indices
            and boundary_inside_environment == boundary_roof_environment
            and sum(boundary_inside_environment) == ENVIRONMENT_GLYPH_MASK_PIXELS
            and sha256(boundary_inside_environment) == ENVIRONMENT_GLYPH_MASK_SHA256,
            "native boundary pair retains the same environmental glyph and lamp-fringe mask",
        )

    provenance_data = PROVENANCE.read_bytes()
    check(sha256(provenance_data.replace(b"\r\n", b"\n")) == PROVENANCE_SHA256,
          "paired lunar provenance has its pinned normalized SHA-256")
    try:
        provenance = json.loads(provenance_data)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        check(False, f"paired lunar provenance decodes safely: {error}")
        provenance = {}
    authority = provenance.get("authority", {})
    continuity = provenance.get("continuity_after_snapshot", {})
    exterior_state = continuity.get("exterior", {})
    interior_state = continuity.get("interior", {})
    check(
        provenance.get("star") == [174288, -44389, -688771]
        and provenance.get("target_body") == 0
        and provenance.get("target_type") == 1
        and provenance.get("star_class") == 0,
        "native provenance identifies IDEAL I and its exact generated classes",
    )
    check(
        exterior_state.get("fcs_status") == "TRACKING"
        and interior_state.get("fcs_status") == "TRACKING"
        and exterior_state.get("secs") == interior_state.get("secs") == 1344638737.0,
        "paired provenance brackets the same raw clock and fixed-chase state",
    )
    check(
        authority.get("snapshot_camera_state_retained") is True
        and authority.get("snapshot_page_and_palette_retained") is True
        and authority.get("paired_simulation_bracket_retained") is True
        and authority.get("snapshot_simulation_state_retained") is False
        and authority.get("whole_page_same_state_contract") is False,
        "paired provenance states the admissible camera, page, palette, and state limits",
    )
    product_interior = provenance.get("matched_product_interior_contract", {})
    product_capture = product_interior.get("capture_state", {})
    product_fixed_chase = product_interior.get("fixed_chase_contract", {})
    product_brightness = product_interior.get("brightness_pixels", {})
    check(
        product_capture.get("private_inactive_desktop") is True
        and product_capture.get("diagnostic_only") is True
        and product_capture.get("raw_clock") == 1344638736
        and product_capture.get("open_hud_switch") is True
        and product_capture.get("sync") == 1
        and product_capture.get("fcs_status") == "TRACKING"
        and product_capture.get("authored_orbital_local") ==
        [0.0, 0.0, 0.012942215051003982]
        and product_capture.get("captured_orbital_local") ==
        [0.0, 0.0, 0.012835549999999932]
        and product_capture.get("camera", {}).get("user_beta") == -97.0
        and product_capture.get("player_position") == [0.0, 0.0, -500.0],
        "paired provenance pins the matched private fixed-chase open-HUD capture state",
    )
    check(
        product_interior.get("product_crop_index_sha256") ==
        PRODUCT_INTERIOR_CROP_SHA256
        and product_interior.get("exact_indices") == PRODUCT_INTERIOR_EXACT_INDICES
        and product_interior.get("differing_indices") == 605
        and product_interior.get("palette_band_differences") == 0
        and product_interior.get("product_status_crop_index_sha256") ==
        PRODUCT_INTERIOR_STATUS_SHA256
        and product_interior.get("complete_page_index_mismatches") == 4563
        and product_interior.get("complete_page_palette_band_mismatches") == 1190
        and product_fixed_chase.get("previous_sync") == 0
        and product_fixed_chase.get("captured_sync") == 1
        and product_fixed_chase.get("changed_complete_page_indices") == 491
        and product_fixed_chase.get("changed_graded_crop_indices") == 0
        and product_fixed_chase.get("previous_complete_page_palette_band_mismatches") == 1190
        and product_fixed_chase.get("captured_complete_page_palette_band_mismatches") == 1190
        and tuple(product_brightness.get(key) for key in (
            "native_page_native_palette",
            "native_page_product_palette",
            "product_page_native_palette",
            "product_page_product_palette",
        )) == PRODUCT_INTERIOR_BRIGHTNESS
        and product_interior.get("indexed_page_brightness_deficit_pixels") == 123
        and product_interior.get("palette_brightness_contribution_pixels") == 0
        and product_interior.get("source_repair_supported") is False,
        "paired provenance records the indexed-raster-only interior brightness discriminator",
    )

    limb_provenance_data = LIMB_PROVENANCE.read_bytes()
    check(sha256(limb_provenance_data.replace(b"\r\n", b"\n")) ==
          LIMB_PROVENANCE_SHA256,
          "limb-pair provenance has its pinned normalized SHA-256")
    try:
        limb_provenance = json.loads(limb_provenance_data)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        check(False, f"limb-pair provenance decodes safely: {error}")
        limb_provenance = {}
    limb_authority = limb_provenance.get("authority", {})
    limb_staged = limb_provenance.get("staged_state", {})
    limb_state = limb_provenance.get("continuity_after_snapshot", {})
    check(
        limb_provenance.get("star") == [174288, -44389, -688771]
        and limb_provenance.get("target_body") == 0
        and limb_provenance.get("target_type") == 1
        and limb_provenance.get("star_class") == 0,
        "limb provenance identifies the same IDEAL I system",
    )
    staged_local = tuple(limb_staged.get("star_local", ()))
    bracket_local = tuple(limb_state.get("star_local", ()))
    check(
        limb_staged.get("sync") == limb_state.get("sync") == 0
        and limb_state.get("fcs_status") == "STANDBY"
        and limb_state.get("secs") == 1344638737.0
        and len(staged_local) == len(bracket_local) == 3
        and all(abs(staged_local[index] - bracket_local[index]) < 0.00000000003
                for index in range(3)),
        "limb provenance brackets the staged sync-0 pose through the native snapshot",
    )
    check(
        limb_provenance.get("camera", {}).get("user_beta") == 67.0
        and limb_authority.get("snapshot_camera_state_retained") is True
        and limb_authority.get("snapshot_page_and_palette_retained") is True
        and limb_authority.get("adjacent_simulation_bracket_retained") is True
        and limb_authority.get("snapshot_simulation_state_retained") is False
        and limb_authority.get("whole_page_same_state_contract") is False,
        "limb provenance states the admissible camera, page, palette, and state limits",
    )

    roof_provenance_data = ROOF_PROVENANCE.read_bytes()
    check(sha256(roof_provenance_data.replace(b"\r\n", b"\n")) ==
          ROOF_PROVENANCE_SHA256,
          "roof/cupola provenance has its pinned normalized SHA-256")
    try:
        roof_provenance = json.loads(roof_provenance_data)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        check(False, f"roof/cupola provenance decodes safely: {error}")
        roof_provenance = {}
    roof_authority = roof_provenance.get("authority", {})
    roof_camera = roof_provenance.get("camera", {})
    roof_staged = roof_provenance.get("staged_state", {})
    roof_state = roof_provenance.get("continuity_after_snapshot", {})
    roof_capture = roof_provenance.get("capture", {})
    check(
        roof_provenance.get("star") == [174288, -44389, -688771]
        and roof_provenance.get("target_body") == 0
        and roof_provenance.get("target_type") == 1
        and roof_provenance.get("star_class") == 0,
        "roof provenance identifies the same IDEAL I system",
    )
    roof_staged_local = tuple(roof_staged.get("star_local", ()))
    roof_bracket_local = tuple(roof_state.get("star_local", ()))
    check(
        roof_staged.get("sync") == roof_state.get("sync") == 0
        and roof_state.get("fcs_status") == "STANDBY"
        and roof_state.get("secs") == 1344638737.0
        and roof_state.get("lifter") == 0
        and roof_state.get("position") == [0.0, -750.0, -1900.0]
        and len(roof_staged_local) == len(roof_bracket_local) == 3
        and all(abs(roof_staged_local[index] - roof_bracket_local[index]) < 0.00000000003
                for index in range(3)),
        "roof provenance brackets the stable staged pose through the native snapshot",
    )
    check(
        roof_camera.get("position") == [0.0, -750.0, -1900.0]
        and roof_camera.get("user_beta") == 180.0
        and roof_camera.get("source_ontheroof") is True
        and roof_camera.get("aperture_distance") == 1200.0
        and roof_camera.get("automatic_return_gate") == 1100.0,
        "roof provenance pins the source roof state outside the automatic return gate",
    )
    check(
        roof_capture.get("page_vs_frozen_adapted_differences") == 0
        and roof_capture.get("frozen_adapted_sha256") == ROOF_ADAPTED_SHA256
        and roof_capture.get("sandbox_restored") is True
        and roof_authority.get("snapshot_camera_state_retained") is True
        and roof_authority.get("snapshot_page_and_palette_retained") is True
        and roof_authority.get("post_snapshot_page_identity_retained") is True
        and roof_authority.get("adjacent_simulation_bracket_retained") is True
        and roof_authority.get("snapshot_simulation_state_retained") is False
        and roof_authority.get("whole_page_same_state_contract") is False,
        "roof provenance states the admissible page, palette, camera, and state limits",
    )

    boundary_provenance_data = BOUNDARY_PROVENANCE.read_bytes()
    check(sha256(boundary_provenance_data.replace(b"\r\n", b"\n")) ==
          BOUNDARY_PROVENANCE_SHA256,
          "cupola-boundary provenance has its pinned normalized SHA-256")
    try:
        boundary_provenance = json.loads(boundary_provenance_data)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        check(False, f"cupola-boundary provenance decodes safely: {error}")
        boundary_provenance = {}
    boundary_branch = boundary_provenance.get("source_branch", {})
    boundary_common = boundary_provenance.get(
        "continuity_after_snapshot", {}).get("common", {})
    boundary_capture = boundary_provenance.get("capture", {})
    boundary_transition = boundary_provenance.get("native_transition", {})
    boundary_product = boundary_provenance.get("product_contract", {})
    boundary_capture_state = boundary_product.get("capture_state", {})
    boundary_environment = boundary_product.get("environment_glyph_lamp_contract", {})
    boundary_absent_moon = boundary_product.get("absent_moon_palette_contract", {})
    boundary_cursor = boundary_product.get("editing_cursor_raster_contract", {})
    boundary_editing = boundary_product.get("editing_runtime_contract", {})
    boundary_authority = boundary_provenance.get("authority", {})
    check(
        boundary_provenance.get("star") == [174288, -44389, -688771]
        and boundary_provenance.get("target_body") == 0
        and boundary_provenance.get("target_type") == 1
        and boundary_provenance.get("star_class") == 0,
        "cupola-boundary provenance identifies the same IDEAL I system",
    )
    check(
        boundary_branch.get("predicate") == "pos_y < -500"
        and boundary_branch.get("inside_position") == [0.0, -500.0, -1900.0]
        and boundary_branch.get("roof_position") == [0.0, -501.0, -1900.0]
        and boundary_branch.get("inside_ontheroof") is False
        and boundary_branch.get("roof_ontheroof") is True,
        "cupola-boundary provenance pins the exact strict source branch",
    )
    check(
        boundary_common.get("sync") == 0
        and boundary_common.get("fcs_status") == "STANDBY"
        and boundary_common.get("secs") == 1344638737.0
        and boundary_common.get("lifter") == 0
        and boundary_common.get("user_beta") == 180.0
        and boundary_common.get("star_local") ==
        [-33.337344046565704, 0.006575896761205513, -4.090433066477999],
        "cupola-boundary provenance brackets one shared stopped-flight state",
    )
    inside_capture = boundary_capture.get("inside_boundary", {})
    outside_capture = boundary_capture.get("roof_boundary", {})
    check(
        inside_capture.get("frozen_adapted_sha256") ==
        BOUNDARY_INSIDE_ADAPTED_SHA256
        and inside_capture.get("page_vs_frozen_adapted_differences") == 7958
        and outside_capture.get("frozen_adapted_sha256") ==
        BOUNDARY_ROOF_ADAPTED_SHA256
        and outside_capture.get("page_vs_frozen_adapted_differences") == 12208
        and boundary_capture.get("sandbox_restored") is True,
        "cupola-boundary provenance retains both following-frame limits",
    )
    check(
        boundary_transition.get("complete_page_exact_indices") == 59428
        and boundary_transition.get(
            "complete_page_palette_band_differences") == 649
        and boundary_transition.get("status_inside_bright_pixels") == 699
        and boundary_transition.get("status_roof_bright_pixels") == 234
        and boundary_transition.get("telemetry_inside_bright_pixels") == 601
        and boundary_transition.get("telemetry_roof_bright_pixels") == 63
        and boundary_transition.get("label_crop") == list(BOUNDARY_LABEL_CROP)
        and boundary_transition.get("label_inside_index_sha256") ==
        BOUNDARY_LABEL_INSIDE_SHA256
        and boundary_transition.get("label_roof_index_sha256") ==
        BOUNDARY_LABEL_ROOF_SHA256
        and boundary_transition.get("label_inside_bright_pixels") == 6522
        and boundary_transition.get("label_roof_bright_pixels") == 6247
        and boundary_transition.get("label_brightness_mask_differences") == 275,
        "cupola-boundary provenance pins the native status, range, and target-label transition",
    )
    check(
        boundary_product.get("raw_clock") == 1344638737
        and boundary_product.get("inside_complete_page_exact_indices") == 23698
        and boundary_product.get("inside_complete_page_palette_band_differences") == 3932
        and boundary_product.get("roof_complete_page_exact_indices") == 61619
        and boundary_product.get("roof_complete_page_palette_band_differences") == 1588
        and boundary_product.get("complete_palette_component_differences") ==
        {"inside": 54, "roof": 54}
        and boundary_absent_moon.get("target_is_planet") is True
        and boundary_absent_moon.get("band_indices") == [128, 192]
        and boundary_absent_moon.get("components") == 192
        and boundary_absent_moon.get("native_nonzero_components") == 0
        and boundary_absent_moon.get("product_nonzero_components") == 0
        and boundary_absent_moon.get("exact_components") == 192
        and boundary_absent_moon.get("removed_bootstrap_component_mismatches") == 187
        and boundary_absent_moon.get("complete_palette_component_mismatches_remaining") == 54
        and boundary_absent_moon.get("complete_palette_equality_graded") is False
        and boundary_product.get("palette_independent_raster_contract") is True
        and boundary_capture_state.get("source_hud_enabled") is True
        and boundary_capture_state.get("open_hud_switch") is False
        and boundary_capture_state.get("scoped_rasters_repeated_after_recompile") is True
        and boundary_product.get("status_inside_index_sha256") ==
        PRODUCT_BOUNDARY_STATUS_INSIDE_SHA256
        and boundary_product.get("status_roof_index_sha256") ==
        PRODUCT_BOUNDARY_STATUS_ROOF_SHA256
        and boundary_product.get("telemetry_inside_index_sha256") ==
        PRODUCT_BOUNDARY_TELEMETRY_INSIDE_SHA256
        and boundary_product.get("roof_telemetry_crop_exact_indices") == 4620
        and boundary_product.get("label_crop") == list(BOUNDARY_LABEL_CROP)
        and boundary_product.get("label_inside_index_sha256") ==
        PRODUCT_BOUNDARY_LABEL_INSIDE_SHA256
        and boundary_product.get("label_roof_index_sha256") ==
        PRODUCT_BOUNDARY_LABEL_ROOF_SHA256
        and boundary_environment.get("crop") == list(ENVIRONMENT_GLYPH_CROP)
        and boundary_environment.get("foreground_pixels") ==
        ENVIRONMENT_GLYPH_MASK_PIXELS
        and boundary_environment.get("normalized_mask_sha256") ==
        ENVIRONMENT_GLYPH_MASK_SHA256
        and boundary_environment.get("native_pair_mask_equal") is True
        and boundary_environment.get("product_pair_matches_native_mask") is True
        and boundary_environment.get("product_scoped_indices_match_native") is True
        and boundary_environment.get("repeated_after_recompile") is True
        and boundary_product.get("left_range_telemetry_restored") is True
        and boundary_product.get("upper_target_labels_restored") is True
        and boundary_product.get("environmental_hud_row_restored") is True
        and boundary_product.get("environmental_numeric_state_exact") is False
        and boundary_product.get("editing_cursors_restored") is True
        and boundary_product.get("editing_cursor_runtime_test") ==
        "tests/test_label_editing_runtime.py"
        and boundary_cursor.get("glyph") == "_"
        and boundary_cursor.get("shader") == 0
        and boundary_cursor.get("complete_indexed_page_bytes") == 64000
        and boundary_cursor.get("phase_step") == 8
        and boundary_cursor.get("same_phase_recurrence_delta") == 32
        and boundary_cursor.get("same_phase_recurrence_difference_pixels") == 0
        and boundary_cursor.get("distinct_phase_difference_pixels") == 34
        and boundary_cursor.get("distinct_phase_bounds") == [83, 32, 91, 35]
        and boundary_cursor.get("movement_compared_at_same_phase") is True
        and boundary_cursor.get("one_space_position_move_pixels") == 72
        and boundary_cursor.get("one_space_position_move_bounds") == [83, 32, 102, 35]
        and boundary_cursor.get("one_position_translation_x") == 11
        and boundary_editing.get("label_state_diagnostic_bytes") == 32
        and boundary_editing.get("physical_escape_active_editor_precondition") is True
        and boundary_editing.get("physical_escape_held_through_followup_capture") is True
        and boundary_editing.get("physical_escape_release_survival_tested") is True
        and boundary_editing.get("physical_escape_latch_clear_observed") is True
        and boundary_editing.get("duplicate_editor_precondition") is True
        and boundary_editing.get("duplicate_result") == "EXTANT"
        and boundary_editing.get("duplicate_result_code") == 2
        and boundary_editing.get("consolidated_removal_result") == "DENIED"
        and boundary_editing.get("consolidated_removal_result_code") == 4
        and boundary_product.get("inside_full_overlay_parity") is False
        and "complete interior lighting" in boundary_product.get("open_gap", "")
        and "remaining unretained palette-easing state" in
        boundary_product.get("open_gap", "")
        and "whole-row numerical environmental-state equality" in
        boundary_product.get("open_gap", "")
        and "runtime-proven direct-edit cursors" in boundary_product.get("open_gap", ""),
        "cupola-boundary provenance pins restored ranges, labels, environmental HUD, absent-moon palette, and separately graded cursors",
    )
    check(
        boundary_authority.get("snapshot_camera_state_retained") is True
        and boundary_authority.get("snapshot_page_and_palette_retained") is True
        and boundary_authority.get("post_snapshot_page_identity_retained") is False
        and boundary_authority.get("adjacent_simulation_bracket_retained") is True
        and boundary_authority.get("paired_state_except_camera_y_retained") is True
        and boundary_authority.get("snapshot_simulation_state_retained") is False
        and boundary_authority.get("whole_page_same_state_contract") is False,
        "cupola-boundary provenance states the admissible branch and state limits",
    )

    capture = CAPTURE.read_text(encoding="utf-8")
    check(
        all(name in capture for name in (
            "$OrbitalLocalX", "$OrbitalLocalY", "$OrbitalLocalZ",
            "must be supplied together", "$OrbitalSync",
            "$spec.Sync = $OrbitalSync",
            "has no orbital sync state to override",
        )),
        "capture tool accepts only complete orbital-local poses and bounded sync overrides",
    )
    corrected_orbital_locals = (
        "LocalX=-0.046885; LocalY=0.0; LocalZ=0.110461",
        "LocalX=-0.025697; LocalY=0.0; LocalZ=0.060539",
        "LocalX=-0.010794; LocalY=0.0; LocalZ=0.025432",
        "LocalX=-0.034346; LocalY=0.0; LocalZ=0.080919",
        "LocalX=-0.032783; LocalY=0.0; LocalZ=0.077237",
        "LocalX=-0.027804; LocalY=0.0; LocalZ=0.065506",
        "LocalX=-0.030966; LocalY=0.0; LocalZ=0.072956",
        "LocalX=-0.261698; LocalY=0.0; LocalZ=0.616521",
        "LocalX=-0.039580; LocalY=0.0; LocalZ=0.093250",
        "LocalX=-0.055611; LocalY=0.0; LocalZ=0.131011",
        "LocalX=-0.333919; LocalY=0.0; LocalZ=0.786714",
    )
    check(
        capture.count(
            "Beta=23; Pitch=0; Warmup=1; PlayerX=2813; PlayerY=0; PlayerZ=-1397;"
        ) == 11
        and all(local in capture for local in corrected_orbital_locals)
        and "negate its target-local offset" in capture,
        "all generic orbital gallery poses compensate for the source exterior half-turn",
    )

    exterior_local = tuple(exterior_state.get("star_local", ()))
    interior_local = tuple(interior_state.get("star_local", ()))
    limb_local = tuple(limb_state.get("star_local", ()))
    roof_local = tuple(roof_state.get("star_local", ()))
    boundary_local = tuple(boundary_common.get("star_local", ()))
    if args.exterior_product_directory is not None and exterior_page:
        grade_product(args.exterior_product_directory, 0, exterior_page,
                      exterior_palette, exterior_local, "exterior", check)
    if args.interior_product_directory is not None and interior_page:
        grade_product(args.interior_product_directory, -97, interior_page,
                      interior_palette, interior_local, "interior", check)
    if args.limb_product_directory is not None and limb_page:
        grade_product(args.limb_product_directory, 67, limb_page,
                      limb_palette, limb_local, "limb", check)
    if args.roof_product_directory is not None and roof_page:
        grade_product(args.roof_product_directory, 180, roof_page,
                      roof_palette, roof_local, "roof", check)
    if (args.boundary_inside_product_directory is not None
            and boundary_inside_page and boundary_roof_page):
        grade_boundary_product_pair(
            args.boundary_inside_product_directory,
            args.boundary_roof_product_directory,
            boundary_inside_page, boundary_inside_palette,
            boundary_roof_page, boundary_roof_palette,
            boundary_local, check,
        )

    if failures:
        print(f"orbitlunar oracle: {len(failures)} failure(s)")
        return 1
    print("orbitlunar oracle: all requested checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
