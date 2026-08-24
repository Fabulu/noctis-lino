"""Grade a compact moon-and-companion orbital oracle independent of ROTOR IGNE."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "gen" / "recon_w7b" / "out"
ORACLE = OUT / "orbitmultiple_compact_3228_native.shot.BMP"
PROVENANCE = OUT / "orbitmultiple_compact_3228_native.provenance.json"
CAPTURE_TOOL = ROOT / "tools" / "capture_noctis_scenes.ps1"
BMP_SHA256 = "2dd8a1470dd40def194363da9fe2be4100da57fdfbee9b95db64c69f7dbd547a"
PAGE_SHA256 = "7e8af381d96db273b9e4becfa056f0e6d56588143ad150a3a0517a24d8e54ec4"
PALETTE_SHA256 = "a23a8917d9dfdb0fbe8dea7422d58fa684ccc335a63a49f99fe269fc5fb33170"
PROVENANCE_SHA256 = "a0dd6dbdd86cbbf7a9ec3bce22bca86e88d8fbe50f004ff32b1aa8087cb4f877"
STAR = (-546064, -439032, -1136208)
TARGET_SEED = (83, 100)
COMPANION_SEED = (232, 100)
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


def product_paths(directory: Path) -> tuple[tuple[Path, int], ...]:
    return tuple(
        (directory / f"orbitmultiplecompact-{name}", size)
        for name, size in DIAGNOSTIC_SIZES
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-directory", type=Path)
    args = parser.parse_args()
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

    if native_page:
        native_target = connected_component(
            native_page, TARGET_SEED, lambda value: value >> 6 == 2)
        native_companion = connected_component(
            native_page, COMPANION_SEED, lambda value: value > 64)
        native_core = connected_component(
            native_page, COMPANION_SEED, lambda value: value > 119)
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

    if args.product_directory is not None:
        directory = args.product_directory
        required = product_paths(directory)
        for path, size in required:
            check(path.is_file() and path.stat().st_size == size,
                  f"product emitted {path.name} at exactly {size} bytes")
        if all(path.is_file() and path.stat().st_size == size for path, size in required):
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

    if failures:
        print(f"compact orbitmultiple oracle: {len(failures)} failure(s)")
        return 1
    print("compact orbitmultiple oracle: all requested checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
