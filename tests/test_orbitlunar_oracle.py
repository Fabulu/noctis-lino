"""Grade paired native lunar exterior and Stardrifter-interior oracles."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct


ROOT = Path(__file__).resolve().parents[1]
ORACLE_ROOT = ROOT / "tests" / "gen" / "recon_w7b" / "out"
EXTERIOR = ORACLE_ROOT / "orbitlunar_exterior_8736_native.shot.BMP"
INTERIOR = ORACLE_ROOT / "orbitlunar_interior_8736_native.shot.BMP"
LIMB = ORACLE_ROOT / "orbitlunar_limb_pair_8736_native.shot.BMP"
PROVENANCE = ORACLE_ROOT / "orbitlunar_camera_pair_8736_native.provenance.json"
LIMB_PROVENANCE = ORACLE_ROOT / "orbitlunar_limb_pair_8736_native.provenance.json"
CAPTURE = ROOT / "tools" / "capture_noctis_scenes.ps1"
EXTERIOR_SHA256 = "89579c32aaee28a93e5b28675921ca055a72c870fb1e00b9381308d3ab9aa559"
INTERIOR_SHA256 = "f26d65b7c6a96aed4e34b7b4389cbfd65777e499f521a08f1e2d970ecdc20667"
LIMB_SHA256 = "c35d22468bdf6e83a181dde4fca6567285268b7b4abb05997b86ab1e8db583c0"
PROVENANCE_SHA256 = "da981004d14e9ea86ceb608b419122b51ebd76c2d03c1c9e473e36d9d927e2cb"
LIMB_PROVENANCE_SHA256 = "e98ee55bc77c8b0b9462cd66693da0e3bcbb96883e2b39c81598f7a336c39644"
PALETTE_SHA256 = "3f78ddd2036be9d6308517d9baff0c3f0d6b181bf46b6f93cd987e4200e98077"
INTERIOR_CROP = (30, 30, 180, 150)
INTERIOR_BAND_SHA256 = "9652c9d0bcd76afa6917a52287633fc55b17dbef148db003813045438fd29bdb"
LIMB_CROP = (10, 75, 90, 125)
LIMB_BAND_SHA256 = "9f7d58392998a5134aba50a131a59dde46c60be997ad446e161bda6bad511be0"
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


def crop_bands(page: bytes, box: tuple[int, int, int, int]) -> bytes:
    x0, y0, x1, y1 = box
    return bytes(page[y * 320 + x] >> 6
                 for y in range(y0, y1) for x in range(x0, x1))


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
    check(
        header[:2] == (0, 1) and header[3:] ==
        (1344638736, 0, camera_beta, 0, 1),
        "product retains the matched class-0/type-1 orbital clock and camera",
    )
    check(
        all(abs(native_local[index] - product_local[index]) < 0.000001
            for index in range(3)),
        "product brackets the native Stardrifter position within one millionth",
    )
    check(abs(binary64(20) - 0.007128) < 1e-12
          and abs(binary64(22) - 0.01283555) < 1e-12,
          "product retains the native lunar radius and target distance")

    sun = struct.unpack("<32i", (directory / "orbitlunar-game-sun-out.bin").read_bytes())
    check(sun[:4] == (0, 1, 1, 0),
          "product diagnostics identify local flight, the type-1 target, and class-0 star")

    page = (directory / "orbitlunar-game-page-out.bin").read_bytes()
    palette = struct.unpack(
        "<768I", (directory / "orbitlunar-game-palette-out.bin").read_bytes())
    if view == "interior":
        native_bands = crop_bands(native_page, INTERIOR_CROP)
        product_bands = crop_bands(page, INTERIOR_CROP)
        check(product_bands == native_bands,
              "product exactly retains the native interior/primary-flare palette-band geometry")
        exact = sum(a == b for a, b in zip(
            (native_page[y * 320 + x] for y in range(30, 150) for x in range(30, 180)),
            (page[y * 320 + x] for y in range(30, 150) for x in range(30, 180)),
        ))
        check(exact >= 17000,
              f"product retains at least 17,000 of 18,000 exact interior-flare indices ({exact})")
        print("INFO interior-flare brightness remains ungraded "
              f"(native {bright_crop_count(native_page, native_palette)}, "
              f"product {bright_crop_count(page, palette)} pixels above component 32)")
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exterior-product-directory", type=Path)
    parser.add_argument("--interior-product-directory", type=Path)
    parser.add_argument("--limb-product-directory", type=Path)
    args = parser.parse_args()
    failures = []

    def check(condition: bool, message: str) -> None:
        print("PASS" if condition else "FAIL", message)
        if not condition:
            failures.append(message)

    exterior_data = EXTERIOR.read_bytes()
    interior_data = INTERIOR.read_bytes()
    limb_data = LIMB.read_bytes()
    check(sha256(exterior_data) == EXTERIOR_SHA256,
          "retained lunar exterior BMP has its pinned SHA-256")
    check(sha256(interior_data) == INTERIOR_SHA256,
          "retained Stardrifter-interior BMP has its pinned SHA-256")
    check(sha256(limb_data) == LIMB_SHA256,
          "retained lunar limb-pair BMP has its pinned SHA-256")
    try:
        exterior_page, exterior_palette = decode_bmp(EXTERIOR)
        interior_page, interior_palette = decode_bmp(INTERIOR)
        limb_page, limb_palette = decode_bmp(LIMB)
    except (AssertionError, OSError, struct.error) as error:
        check(False, f"lunar native BMPs decode safely: {error}")
        exterior_page = interior_page = limb_page = b""
        exterior_palette = interior_palette = limb_palette = ()
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
        check(sha256(bytes(exterior_palette)) == PALETTE_SHA256
              and exterior_palette == interior_palette == limb_palette,
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

    capture = CAPTURE.read_text(encoding="utf-8")
    check(
        all(name in capture for name in (
            "$OrbitalLocalX", "$OrbitalLocalY", "$OrbitalLocalZ",
            "must be supplied together",
        )),
        "capture tool accepts only complete exact orbital-local pose overrides",
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
    if args.exterior_product_directory is not None and exterior_page:
        grade_product(args.exterior_product_directory, 0, exterior_page,
                      exterior_palette, exterior_local, "exterior", check)
    if args.interior_product_directory is not None and interior_page:
        grade_product(args.interior_product_directory, -97, interior_page,
                      interior_palette, interior_local, "interior", check)
    if args.limb_product_directory is not None and limb_page:
        grade_product(args.limb_product_directory, 67, limb_page,
                      limb_palette, limb_local, "limb", check)

    if failures:
        print(f"orbitlunar oracle: {len(failures)} failure(s)")
        return 1
    print("orbitlunar oracle: all requested checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
