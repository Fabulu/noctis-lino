"""Grade the retained native and hosted WIRE class-7 primary flare."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import struct


ROOT = Path(__file__).resolve().parents[1]
ORACLE_ROOT = ROOT / "tests" / "native-oracles" / "orbital-class7-wire"
ORACLE = ORACLE_ROOT / "native.shot.BMP"
PROVENANCE = ORACLE_ROOT / "provenance.json"
README = ORACLE_ROOT / "README.md"
STAR_SOURCE = ROOT / "work" / "vhstar.txt"
GAME = ROOT / "work" / "vhgame.txt"
CAPTURE = ROOT / "tools" / "capture_noctis_scenes.ps1"
CURRENT_BUILDER = ROOT / "tests" / "gen" / "recon_w7b" / "mkcurrent.py"
REFERENCE_ROOT = Path(os.environ.get(
    "NOCTIS_REFERENCE_ROOT",
    r"C:\programmieren\noctis\niv-plus\source",
))
ORIGINAL = REFERENCE_ROOT / "NOCTIS.CPP"
BMP_SHA256 = "254daba81c49072da33ec65f2aa9ac639fdf74f887114c22cdba71ce2c1feae1"
PAGE_SHA256 = "23c2c66529021bf43952b9e0f526f50fb710c4698cdcfc0032631c291e9e5995"
PALETTE_SHA256 = "78dff3c46c7cd75014e9e77a05ca9f07ae60bba3af6d3d09ad19c63f45634ec1"
PROVENANCE_SHA256 = "0727043d2ceb6f14a2709a7445a9ccdaf0e07f5cf125cffd71e9e72651bc7a8f"
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
CORE_CROP = (120, 60, 195, 115)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decode_bmp(data: bytes) -> tuple[bytes, tuple[int, ...]]:
    if len(data) != 65078 or data[:2] != b"BM":
        raise AssertionError("expected the complete 65,078-byte indexed BMP")
    pixel_offset = struct.unpack_from("<I", data, 10)[0]
    width, height = struct.unpack_from("<ii", data, 18)
    depth = struct.unpack_from("<H", data, 28)[0]
    if (pixel_offset, width, height, depth) != (1078, 320, 200, 8):
        raise AssertionError("unexpected orbital-primary BMP layout")
    palette = []
    for index in range(256):
        blue, green, red, reserved = data[54 + index * 4:58 + index * 4]
        if reserved or any(component & 3 for component in (red, green, blue)):
            raise AssertionError("orbital-primary BMP palette is not exact six-bit BGR0")
        palette.extend((red >> 2, green >> 2, blue >> 2))
    pixels = data[pixel_offset:pixel_offset + 64000]
    rows = [pixels[row * 320:(row + 1) * 320] for row in range(200)]
    rows.reverse()
    return b"".join(rows), tuple(palette)


def crop_offsets(box: tuple[int, int, int, int]):
    x0, y0, x1, y1 = box
    return tuple(y * 320 + x for y in range(y0, y1 + 1)
                 for x in range(x0, x1 + 1))


def bright_low_six_contract(
        page: bytes, box: tuple[int, int, int, int], threshold: int,
) -> tuple[int, tuple[int, int, int, int]]:
    x0, y0, x1, y1 = box
    points = [
        (x, y)
        for y in range(y0, y1 + 1)
        for x in range(x0, x1 + 1)
        if page[y * 320 + x] & 63 >= threshold
    ]
    if not points:
        return 0, (0, 0, 0, 0)
    return len(points), (
        min(x for x, _y in points), min(y for _x, y in points),
        max(x for x, _y in points), max(y for _x, y in points),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-directory", type=Path)
    args = parser.parse_args()
    failures = []

    def check(condition: bool, message: str) -> None:
        print("PASS" if condition else "FAIL", message)
        if not condition:
            failures.append(message)

    try:
        bmp = ORACLE.read_bytes()
        page, palette = decode_bmp(bmp)
        provenance_bytes = PROVENANCE.read_bytes()
        provenance = json.loads(provenance_bytes)
        readme = README.read_text(encoding="utf-8")
    except (OSError, ValueError, AssertionError, json.JSONDecodeError) as error:
        check(False, f"retained WIRE oracle decodes: {error}")
        return 1

    packed_palette = struct.pack("<768I", *palette)
    check(
        sha256(bmp) == BMP_SHA256
        and sha256(page) == PAGE_SHA256
        and sha256(packed_palette) == PALETTE_SHA256
        and sha256(provenance_bytes) == PROVENANCE_SHA256,
        "retained WIRE BMP, page, palette, and provenance hashes are exact",
    )
    check(
        provenance.get("star") == [-1187856, -195673, 1064757]
        and provenance.get("star_name") == "WIRE"
        and provenance.get("star_class") == 7
        and math.isclose(provenance.get("star_ray", 0), 2.191999912261963,
                         rel_tol=0, abs_tol=1e-15)
        and provenance.get("generated_system") == {
            "nop": 1, "nob": 1, "body_0_type": 9,
        },
        "WIRE provenance retains the authentic class-7 generated system",
    )
    continuity = provenance.get("continuity_after_snapshot", {})
    check(
        continuity.get("sync") == 0
        and continuity.get("ip_targetted") == -1
        and continuity.get("ip_reached") == 0
        and continuity.get("pwr") == 19999
        and continuity.get("star_local") == [
            85.64826336479746, 0.0, -201.77466387674212,
        ]
        and provenance.get("camera") == {
            "position": [2813.0, 0.0, -1397.0],
            "user_alfa": 0.0,
            "user_beta": 23.0,
            "navigation_beta": 0.0,
        },
        "post-snapshot continuity retains the untargeted exterior camera",
    )
    flare = provenance.get("flare_contract", {})
    distance = flare.get("distance", 0)
    ray = provenance.get("star_ray", 0)
    check(
        flare.get("source_class_eligible") is True
        and distance > 6 * ray
        and distance < 1000 * ray
        and flare.get("lower_threshold") == 6 * ray
        and flare.get("upper_threshold") == 1000 * ray,
        "WIRE is strictly inside the source-positive orbital primary gate",
    )
    count, bounds = bright_low_six_contract(page, CORE_CROP, 40)
    check(
        count == 148 and bounds == (149, 91, 165, 111)
        and flare.get("core_crop") == list(CORE_CROP)
        and flare.get("low_six_at_least_40") == count
        and flare.get("low_six_at_least_40_bounds") == list(bounds),
        "native WIRE frame retains the bright radial-flare core",
    )
    authority = provenance.get("authority", {})
    capture = provenance.get("capture", {})
    check(
        authority.get("snapshot_camera_state_retained") is True
        and authority.get("snapshot_page_and_palette_retained") is True
        and authority.get("snapshot_simulation_state_retained") is False
        and authority.get("whole_page_same_state_contract") is False
        and capture.get("page_vs_frozen_adapted_differences") == 30095
        and capture.get("sandbox_restored") is True
        and "Complete-page equality" in readme,
        "oracle authority excludes the non-atomic post-snapshot page",
    )

    star_source = STAR_SOURCE.read_text(encoding="utf-8")
    game = GAME.read_text(encoding="utf-8")
    capture_source = CAPTURE.read_text(encoding="utf-8")
    current_builder = CURRENT_BUILDER.read_text(encoding="utf-8")
    check(
        all(fragment in star_source for fragment in (
            "? A = 5 -> VHT premask smooth;",
            "? A = 6 -> VHT premask smooth; ? A = 10 -> VHT premask smooth;",
            "[FI] = 6; => IntToF;",
            "A = [VHTpalfar]; ? A != 0 -> VHT premask smooth;",
            "=> VH space flare;",
        ))
        and "A = [VHGbeta]; A + [VHGnavbeta]; A + 180; A % 360;" in game,
        "product keeps the source class gate and exterior-camera half-turn",
    )
    check(
        "Name='stardrifterclass7'" in capture_source
        and "StarDistance=219.2" in capture_source
        and "$exteriorBeta = ($Spec.Beta + $navigation + 180.0)" in capture_source
        and 'or -1 for an untargeted primary-star pose' in current_builder
        and 'i8("ip_reached", int(target >= 0))' in current_builder,
        "capture tooling authors the matched centred untargeted pose",
    )
    if ORIGINAL.is_file():
        original = ORIGINAL.read_text(encoding="latin-1")
        check(
            "if (l_dsd > 6 * nearstar_ray)" in original
            and "nearstar_class!=5&&nearstar_class!=6&&nearstar_class!=10" in original
            and "l_dsd>5*nearstar_ray&&l_dsd<1000*nearstar_ray" in original,
            "available NIV+ source confirms the strict orbital primary gate",
        )
    else:
        print("INFO NIV+ source tree unavailable; retained source capture remains graded")

    if args.product_directory is not None:
        prefix = "stardrifterclass7-"
        required = tuple(
            (args.product_directory / f"{prefix}{name}", size)
            for name, size in DIAGNOSTIC_SIZES
        )
        for path, size in required:
            check(path.is_file() and path.stat().st_size == size,
                  f"product emitted {path.name} at exactly {size} bytes")
        if all(path.is_file() and path.stat().st_size == size
               for path, size in required):
            view = (args.product_directory /
                    f"{prefix}game-vh-out.bin").read_bytes()
            view_units = struct.unpack("<39i", view)
            product_ray = struct.unpack_from("<f", view, 13 * 4)[0]
            ship_x = struct.unpack_from("<d", view, 8 * 4)[0]
            check(
                view_units[:5] == (2813, 0, -1397, 0, 23)
                and math.isclose(ship_x, -1187941.6482633648,
                                 rel_tol=0, abs_tol=1e-9)
                and view_units[10:13] == (30000, 0, 7)
                and product_ray == ray
                and view_units[14:17] == (1, 1, 1),
                "product retains the matched WIRE camera and stellar state",
            )
            product_page = (args.product_directory /
                            f"{prefix}game-page-out.bin").read_bytes()
            product_palette = struct.unpack(
                "<768I", (args.product_directory /
                          f"{prefix}game-palette-out.bin").read_bytes())
            offsets = crop_offsets(CORE_CROP)
            product_count, product_bounds = bright_low_six_contract(
                product_page, CORE_CROP, 40)
            check(
                product_palette[:192] == palette[:192],
                "product exactly reproduces the native space-palette band",
            )
            check(
                all((product_page[offset] & 0xC0) ==
                    (page[offset] & 0xC0) for offset in offsets),
                "product exactly reproduces all 4,256 native flare-crop bands",
            )
            check(
                product_count == 136
                and product_bounds == (148, 89, 164, 111),
                "product retains the centred class-7 radial-flare core",
            )
            complete_differences = sum(
                native != product for native, product in zip(page, product_page))
            print(
                "INFO complete-page equality is not graded "
                f"({complete_differences} index mismatches)"
            )

    if failures:
        print(f"FAIL {len(failures)} orbital-primary checks")
        return 1
    print("PASS WIRE class-7 orbital-primary oracle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
