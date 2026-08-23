"""Grade matched behind-camera and front-facing ROTOR IGNE oracles."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import struct


ROOT = Path(__file__).resolve().parents[1]
ORACLE = ROOT / "tests" / "gen" / "recon_w7b" / "out" / "orbitmultiple_8526_native.shot.BMP"
PROVENANCE = ORACLE.with_name("orbitmultiple_8526_native.provenance.json")
VISIBLE_ORACLE = ORACLE.with_name("orbitmultiple_visible_8526_native.shot.BMP")
VISIBLE_PROVENANCE = ORACLE.with_name("orbitmultiple_visible_8526_native.provenance.json")
GAME = ROOT / "work" / "vhgame.txt"
REFERENCE_ROOT = Path(os.environ.get(
    "NOCTIS_REFERENCE_ROOT",
    r"C:\programmieren\noctis\niv-plus\source",
))
ORIGINAL = REFERENCE_ROOT / "NOCTIS-0.CPP"
BMP_SHA256 = "27532a2fe2a284f76bf81b630bf28c9fff72a8b1a63146c719a5b9257f9a451b"
PROVENANCE_SHA256 = "34fa8bf9ab390967137938604781db99737ad336efb1a7637907cc4e1ab9a6f6"
VISIBLE_BMP_SHA256 = "82eb4b7ba90286fe59b0d6494e397afd44f412b8fec8b97f77dd34359e9ae866"
VISIBLE_PROVENANCE_SHA256 = "7326b68779d287a9458ff3541f4ba259666e5f425ff6291b09d9c945a53a5d66"
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
    if len(data) != 65078 or data[:2] != b"BM":
        raise AssertionError("expected the complete 65,078-byte indexed BMP")
    pixel_offset = struct.unpack_from("<I", data, 10)[0]
    width, height = struct.unpack_from("<ii", data, 18)
    depth = struct.unpack_from("<H", data, 28)[0]
    if (pixel_offset, width, height, depth) != (1078, 320, 200, 8):
        raise AssertionError("unexpected orbital BMP layout")
    palette = []
    for index in range(256):
        blue, green, red, reserved = data[54 + index * 4:58 + index * 4]
        if reserved or any(component & 3 for component in (red, green, blue)):
            raise AssertionError("orbital BMP palette is not exact six-bit BGR0")
        palette.extend((red >> 2, green >> 2, blue >> 2))
    pixels = data[pixel_offset:pixel_offset + 64000]
    rows = [pixels[row * 320:(row + 1) * 320] for row in range(200)]
    rows.reverse()
    return b"".join(rows), tuple(palette)


def bright_crop_count(page: bytes, palette: tuple[int, ...]) -> int:
    count = 0
    for y in range(95, 140):
        for x in range(115, 175):
            index = page[y * 320 + x] * 3
            if max(palette[index:index + 3]) > 32:
                count += 1
    return count


def diagnostic_paths(directory: Path) -> tuple[tuple[Path, int], ...]:
    return tuple(
        (directory / f"orbitmultiple-{name}", size)
        for name, size in DIAGNOSTIC_SIZES
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-directory", type=Path)
    parser.add_argument("--visible-product-directory", type=Path)
    args = parser.parse_args()
    failures = []

    def check(condition: bool, message: str) -> None:
        print("PASS" if condition else "FAIL", message)
        if not condition:
            failures.append(message)

    oracle_data = ORACLE.read_bytes()
    check(sha256(oracle_data) == BMP_SHA256,
          "retained ROTOR IGNE native BMP has its pinned SHA-256")
    try:
        native_page, native_palette = decode_bmp(oracle_data)
    except (AssertionError, OSError, struct.error) as error:
        check(False, f"native orbital BMP decodes safely: {error}")
        native_page, native_palette = b"", ()
    else:
        check(sha256(native_page) ==
              "02456430527875871bd4700a2f1fc555457a76a4807aa1ef8a981c2fbeed6827",
              "native oracle retains its complete indexed page")
        check(sha256(bytes(native_palette)) ==
              "85d920807169b9699afe1fb0bb489907150f456cccf845ee95f5d806e0da3f56",
              "native oracle retains all 768 active six-bit palette components")
        check(bright_crop_count(native_page, native_palette) == 1,
              "native companion crop contains one ordinary star and no corona or radial flare")

    provenance_data = PROVENANCE.read_bytes()
    normalized_provenance = provenance_data.replace(b"\r\n", b"\n")
    check(sha256(normalized_provenance) == PROVENANCE_SHA256,
          "retained ROTOR IGNE provenance has its pinned normalized SHA-256")
    try:
        provenance = json.loads(provenance_data)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        check(False, f"native orbital provenance decodes safely: {error}")
        provenance = {}
    authority = provenance.get("authority", {})
    continuity = provenance.get("continuity_after_snapshot", {})
    check(
        provenance.get("artifact_sha256") == BMP_SHA256
        and provenance.get("star") == [3866416, -4813508, -735695]
        and provenance.get("target_body") == 0,
        "native provenance identifies the exact generated system and target",
    )
    check(
        provenance.get("camera") == {
            "position": [0.0, 0.0, -500.0],
            "user_alfa": -34.0,
            "user_beta": 0.0,
            "navigation_beta": 120.0,
        }
        and continuity.get("fcs_status") == "TRACKING"
        and abs(continuity.get("secs", 0) - 1344638526.8333333) < 1e-7,
        "native provenance brackets the exact camera and adjacent-frame clock",
    )
    check(
        authority.get("snapshot_camera_state_retained") is True
        and authority.get("snapshot_page_and_palette_retained") is True
        and authority.get("snapshot_simulation_state_retained") is False
        and authority.get("whole_page_same_state_contract") is False,
        "native provenance limits grading to its admissible visibility contract",
    )

    visible_data = VISIBLE_ORACLE.read_bytes()
    check(sha256(visible_data) == VISIBLE_BMP_SHA256,
          "retained front-facing ROTOR IGNE BMP has its pinned SHA-256")
    try:
        visible_page, visible_palette = decode_bmp(visible_data)
    except (AssertionError, OSError, struct.error) as error:
        check(False, f"front-facing native BMP decodes safely: {error}")
        visible_page, visible_palette = b"", ()
    else:
        check(sha256(visible_page) ==
              "d0aecd7c9492207cf3555ba32816b59c980ff83bc3ec064a05ab70e8ed322fcf",
              "front-facing native oracle retains its complete indexed page")
        check(sha256(bytes(visible_palette)) ==
              "c8cb93223c6ed82bd0631fce4d06d70314cb0fd91043fa5dd604234958a073bd",
              "front-facing native oracle retains all active palette components")
        check(bright_crop_count(visible_page, visible_palette) == 151,
              "native front-facing companion retains its corona and radial flare")

    visible_provenance_data = VISIBLE_PROVENANCE.read_bytes()
    normalized_visible_provenance = visible_provenance_data.replace(b"\r\n", b"\n")
    check(sha256(normalized_visible_provenance) == VISIBLE_PROVENANCE_SHA256,
          "front-facing provenance has its pinned normalized SHA-256")
    try:
        visible_provenance = json.loads(visible_provenance_data)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        check(False, f"front-facing provenance decodes safely: {error}")
        visible_provenance = {}
    visible_authority = visible_provenance.get("authority", {})
    visible_continuity = visible_provenance.get("continuity_after_snapshot", {})
    visible_contract = visible_provenance.get("native_visibility", {})
    check(
        visible_provenance.get("artifact_sha256") == VISIBLE_BMP_SHA256
        and visible_provenance.get("companion_body") == 3
        and visible_provenance.get("companion_type") == 10,
        "front-facing provenance identifies the exact type-10 companion",
    )
    check(
        visible_provenance.get("camera") == {
            "position": [0.0, 0.0, -500.0],
            "user_alfa": -34.0,
            "user_beta": 0.0,
            "navigation_beta": 300.0,
        }
        and visible_continuity.get("fcs_status") == "TRACKING"
        and abs(visible_continuity.get("secs", 0) - 1344638526.8) < 1e-7,
        "front-facing provenance brackets its camera and adjacent-frame clock",
    )
    check(
        visible_authority.get("snapshot_page_and_palette_retained") is True
        and visible_authority.get("whole_page_same_state_contract") is False
        and visible_contract.get("bright_pixel_count") == 151
        and visible_contract.get("companion_corona_and_radial_flare_visible") is True,
        "front-facing provenance limits and records its positive visibility contract",
    )

    game = GAME.read_text(encoding="utf-8")
    check(
        "A = [VHGbeta]; A + [VHGnavbeta]; A + 180; A % 360;" in game,
        "product retains the exterior-camera half-turn",
    )
    if ORIGINAL.is_file():
        original = ORIGINAL.read_text(encoding="latin-1")
        check(
            "beta = user_beta + navigation_beta + 180;" in original,
            "available NIV+ source confirms the exterior-camera half-turn",
        )
    else:
        print("INFO NIV+ source tree unavailable; retained native visibility evidence remains graded")

    if args.product_directory is not None:
        directory = args.product_directory
        local_path = directory / "orbitmultiple-game-local-out.bin"
        page_path = directory / "orbitmultiple-game-page-out.bin"
        palette_path = directory / "orbitmultiple-game-palette-out.bin"
        required = diagnostic_paths(directory)
        for path, size in required:
            check(path.is_file() and path.stat().st_size == size,
                  f"product emitted {path.name} at exactly {size} bytes")
        if all(path.is_file() and path.stat().st_size == size for path, size in required):
            local = local_path.read_bytes()
            header = struct.unpack_from("<8i", local)
            binary64 = lambda unit: struct.unpack_from("<d", local, unit * 4)[0]
            ship = (binary64(8), binary64(10), binary64(12))
            target = (binary64(14), binary64(16), binary64(18))
            companion = (binary64(30), binary64(32), binary64(34))
            flare, _cx, _cy = struct.unpack_from("<3i", local, 40 * 4)
            check(header[:2] == (0, 1) and header[3] == 1344638526
                  and header[4:8] == (0, 0, 120, 5),
                  "product diagnostic retains the matched orbital clock and pose")
            native_local = tuple(continuity.get("star_local", ()))
            product_local = tuple(target[index] + ship[index] for index in range(3))
            check(len(native_local) == 3 and all(
                      abs(native_local[index] - product_local[index]) < 0.00002
                      for index in range(3)),
                  "product and native retain the same target-relative Stardrifter position")

            beta = math.radians(120 + 180)
            alpha = math.radians(-34)
            x, y, z = companion
            z2 = z * math.cos(beta) - x * math.sin(beta)
            projected_depth = z2 * math.cos(alpha) + y * math.sin(alpha)
            check(projected_depth < -1500 and flare == 0,
                  "product rejects the source-behind-camera companion before flare rasterization")

            product_page = page_path.read_bytes()
            product_palette = struct.unpack("<768I", palette_path.read_bytes())
            check(bright_crop_count(product_page, product_palette) <= 2,
                  "product companion crop contains no false corona or radial flare")
            if native_page:
                mismatches = sum(a != b for a, b in zip(native_page, product_page))
                print(f"INFO complete-page equality is not graded ({mismatches} index mismatches)")

    if args.visible_product_directory is not None:
        directory = args.visible_product_directory
        local_path = directory / "orbitmultiple-game-local-out.bin"
        page_path = directory / "orbitmultiple-game-page-out.bin"
        palette_path = directory / "orbitmultiple-game-palette-out.bin"
        required = diagnostic_paths(directory)
        for path, size in required:
            check(path.is_file() and path.stat().st_size == size,
                  f"front-facing product emitted {path.name} at exactly {size} bytes")
        if all(path.is_file() and path.stat().st_size == size for path, size in required):
            local = local_path.read_bytes()
            header = struct.unpack_from("<8i", local)
            binary64 = lambda unit: struct.unpack_from("<d", local, unit * 4)[0]
            ship = (binary64(8), binary64(10), binary64(12))
            target = (binary64(14), binary64(16), binary64(18))
            companion = (binary64(30), binary64(32), binary64(34))
            flare, _cx, _cy = struct.unpack_from("<3i", local, 40 * 4)
            check(header[:2] == (0, 1) and header[3] == 1344638526
                  and header[4:8] == (0, 0, 300, 5),
                  "front-facing product retains the matched orbital clock and pose")
            native_local = tuple(visible_continuity.get("star_local", ()))
            product_local = tuple(target[index] + ship[index] for index in range(3))
            check(len(native_local) == 3 and all(
                      abs(native_local[index] - product_local[index]) < 0.003
                      for index in range(3)),
                  "front-facing product retains the native target-relative position bracket")

            beta = math.radians(300 + 180)
            alpha = math.radians(-34)
            x, y, z = companion
            z2 = z * math.cos(beta) - x * math.sin(beta)
            projected_depth = z2 * math.cos(alpha) + y * math.sin(alpha)
            check(projected_depth > 3000 and flare == 1,
                  "front-facing product projects and rasterizes the native-visible companion")

            product_page = page_path.read_bytes()
            product_palette = struct.unpack("<768I", palette_path.read_bytes())
            product_bright = bright_crop_count(product_page, product_palette)
            check(product_bright >= 50,
                  "front-facing product companion is a corona and rays, not an ordinary star")
            if visible_page:
                mismatches = sum(a != b for a, b in zip(visible_page, product_page))
                print(f"INFO front-facing whole-page equality is not graded ({mismatches} index mismatches)")
                print(f"INFO front-facing bright crop remains open (native 151, product {product_bright})")

    if failures:
        print(f"orbitmultiple oracle: {len(failures)} failure(s)")
        return 1
    print("orbitmultiple oracle: all requested checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
