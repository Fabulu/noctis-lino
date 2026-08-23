"""Grade the matched ROTOR IGNE orbital companion visibility oracle."""

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
GAME = ROOT / "work" / "vhgame.txt"
REFERENCE_ROOT = Path(os.environ.get(
    "NOCTIS_REFERENCE_ROOT",
    r"C:\programmieren\noctis\niv-plus\source",
))
ORIGINAL = REFERENCE_ROOT / "NOCTIS-0.CPP"
BMP_SHA256 = "27532a2fe2a284f76bf81b630bf28c9fff72a8b1a63146c719a5b9257f9a451b"
PROVENANCE_SHA256 = "34fa8bf9ab390967137938604781db99737ad336efb1a7637907cc4e1ab9a6f6"


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-directory", type=Path)
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
        required = ((local_path, 176), (page_path, 64000), (palette_path, 3072))
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

    if failures:
        print(f"orbitmultiple oracle: {len(failures)} failure(s)")
        return 1
    print("orbitmultiple oracle: all requested checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
