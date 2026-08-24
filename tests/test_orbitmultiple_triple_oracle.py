"""Grade two generated companion suns independently in one Stardrifter frame."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "gen" / "recon_w7b" / "out"
ORACLE = OUT / "orbitmultiple_triple_3226_native.shot.BMP"
PROVENANCE = OUT / "orbitmultiple_triple_3226_native.provenance.json"
CAPTURE_TOOL = ROOT / "tools" / "capture_noctis_scenes.ps1"
BMP_SHA256 = "e3ea5a56146280907a11073704a8227b40006edc7a0c1dbaf17bd8ca43eeaeeb"
PAGE_SHA256 = "3d7f9ea0cd369edbd7e6a16196082b0fa49d532923ad6f3093bff671bf2f8f7a"
PALETTE_SHA256 = "836c0249a021dd30dbfdd743846d98163af3a8ee316b25c09a79043f80125dd2"
PROVENANCE_SHA256 = "65b05da7905cbfe640ea642d9a427b6e87a1eeafc4a7f1e5cb87020c3a67f5a3"
STAR = (4142128, -5182625, -629021)
TARGET_NATIVE_SEED = (251, 99)
SECOND_NATIVE_SEED = (68, 101)
TARGET_PRODUCT_SEED = (249, 96)
SECOND_PRODUCT_SEED = (67, 98)
TARGET_RELATIVE_SHIP = (
    -2835.4143674072257,
    17.236258154580206,
    35.891644488482996,
)
TARGET_ABSOLUTE = (
    101.31333494339185,
    -2.6696913799585995,
    -264.4884081961804,
)
SECOND_RELATIVE = (
    1958.3532877333696,
    17.23625815470804,
    2050.7841148930697,
)
NATIVE_STAR_LOCAL = (
    -2734.1010324638337,
    14.566566774621606,
    -228.5967637076974,
)
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


def f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def decode_bmp(data: bytes) -> tuple[bytes, tuple[int, ...]]:
    if len(data) != 65_078 or data[:2] != b"BM":
        raise AssertionError("expected one complete 65,078-byte indexed BMP")
    pixel_offset = struct.unpack_from("<I", data, 10)[0]
    width, height = struct.unpack_from("<ii", data, 18)
    depth = struct.unpack_from("<H", data, 28)[0]
    if (pixel_offset, width, height, depth) != (1078, 320, 200, 8):
        raise AssertionError("unexpected dual-companion orbital BMP layout")
    palette = []
    for index in range(256):
        blue, green, red, reserved = data[54 + index * 4:58 + index * 4]
        if reserved or any(component & 3 for component in (red, green, blue)):
            raise AssertionError("dual-companion BMP palette is not exact six-bit BGR0")
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
    threshold: int,
) -> set[tuple[int, int]]:
    pending = [seed]
    points: set[tuple[int, int]] = set()
    while pending:
        x, y = pending.pop()
        if (x, y) in points or not (0 <= x < 320 and 0 <= y < 200):
            continue
        if page[y * 320 + x] <= threshold:
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


def project_flare(relative: tuple[float, float, float]) -> tuple[int, int]:
    beta = math.radians(0.0 + 113.0 + 180.0)
    sin_beta = f32(math.sin(beta))
    cos_beta = f32(math.cos(beta))
    plane = f32(210.0)
    x, y, z = relative
    rx = x * f32(cos_beta * plane) + z * f32(sin_beta * plane)
    z2 = z * cos_beta - x * sin_beta
    ry = y * plane
    return int(rx / z2) + 3 + 160, int(ry / z2) + 100


def product_paths(directory: Path) -> tuple[tuple[Path, int], ...]:
    return tuple(
        (directory / f"orbitmultipletriple-{name}", size)
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
    scene = capture.partition("@{ Name='orbitmultipletriple'")[2].partition("},")[0]
    check(
        "'orbitmultipletriple'" in capture
        and all(token in scene for token in (
            "X=4142128; Y=-5182625; Z=-629021; Body=0; Type=10",
            "Lon=0; Lat=60",
            "Beta=0; Nav=113; Pitch=0",
            "PlayerX=0; PlayerY=0; PlayerZ=-500",
            "Sync=0",
            "LocalX=-2835.4143674072257",
            "LocalY=17.236258154580206",
            "LocalZ=35.891644488482996",
        )),
        "capture tool retains the balanced dual-companion interior pose",
    )

    sys.path.insert(0, str(ROOT / "noctis-harness"))
    import ns_spec  # noqa: E402

    system = ns_spec.System(*STAR)
    check(
        system.cls == 8 and system.nop == 3 and system.nob == 3
        and system.p_type[:3] == [10, 10, 1]
        and system.p_owner[:3] == [-1, -1, -1],
        "tracked generator identifies the genuine class-8 [10,10,1] system",
    )
    check(
        math.isclose(system.ray, 4.706999778747559, abs_tol=1e-12)
        and all(math.isclose(value, expected, abs_tol=1e-12) for value, expected in zip(
            system.p_ray[:3], (12.719999999999999, 10.860000000000001, 0.007056)
        )),
        "generated primary and both companion radii remain exact",
    )

    oracle_data = ORACLE.read_bytes()
    check(sha256(oracle_data) == BMP_SHA256,
          "retained dual-companion native BMP has its pinned SHA-256")
    try:
        native_page, native_palette = decode_bmp(oracle_data)
    except (AssertionError, OSError, struct.error) as error:
        check(False, f"dual-companion native BMP decodes safely: {error}")
        native_page, native_palette = b"", ()
    else:
        check(sha256(native_page) == PAGE_SHA256,
              "native oracle retains its complete indexed page")
        check(sha256(bytes(native_palette)) == PALETTE_SHA256,
              "native oracle retains all active six-bit palette components")

    if native_page:
        native_target = connected_component(native_page, TARGET_NATIVE_SEED, 79)
        native_second = connected_component(native_page, SECOND_NATIVE_SEED, 79)
        native_target_core = connected_component(native_page, TARGET_NATIVE_SEED, 87)
        native_second_core = connected_component(native_page, SECOND_NATIVE_SEED, 87)
        check(
            len(native_target) == 328
            and bounds(native_target) == (212, 90, 264, 104)
            and len(native_target_core) == 61
            and bounds(native_target_core) == (244, 94, 256, 101),
            "native selected companion retains its isolated right corona and core",
        )
        check(
            len(native_second) == 125
            and bounds(native_second) == (56, 94, 77, 106)
            and len(native_second_core) == 57
            and bounds(native_second_core) == (64, 97, 73, 104),
            "native second companion retains its isolated left corona and core",
        )

    provenance_data = PROVENANCE.read_bytes()
    check(
        sha256(provenance_data.replace(b"\r\n", b"\n")) == PROVENANCE_SHA256,
        "dual-companion native provenance has its pinned normalized SHA-256",
    )
    try:
        provenance = json.loads(provenance_data)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        check(False, f"dual-companion native provenance decodes safely: {error}")
        provenance = {}
    continuity = provenance.get("continuity_after_snapshot", {})
    visibility = provenance.get("native_visibility", {})
    matched = provenance.get("matched_product_contract", {})
    authority = provenance.get("authority", {})
    check(
        provenance.get("artifact_sha256") == BMP_SHA256
        and provenance.get("star") == list(STAR)
        and provenance.get("body_types") == [10, 10, 1]
        and provenance.get("body_owners") == [-1, -1, -1]
        and provenance.get("target_body") == 0
        and provenance.get("second_companion_body") == 1,
        "provenance identifies both generated type-10 bodies independently",
    )
    check(
        provenance.get("camera") == {
            "position": [0.0, 0.0, -500.0],
            "user_alfa": 0.0,
            "user_beta": 0.0,
            "navigation_beta": 113.0,
        }
        and continuity.get("sync") == 0
        and continuity.get("ip_targetted") == 0
        and continuity.get("ip_reached") == 1
        and continuity.get("fcs_status") == "STANDBY"
        and math.isclose(continuity.get("secs", 0), 1345723225.764706,
                         abs_tol=1e-9)
        and tuple(continuity.get("star_local", ())) == NATIVE_STAR_LOCAL,
        "provenance retains the exact native camera, target, clock, and local pose",
    )
    check(
        visibility.get("target_companion_component_pixel_count") == 328
        and visibility.get("second_companion_component_pixel_count") == 125
        and visibility.get("both_companion_coronas_and_radial_flares_visible_together")
        is True,
        "provenance records two separate native light-source components",
    )
    check(
        matched.get("raw_clock") == 1345723226
        and tuple(matched.get("target_relative_stardrifter", ())) ==
        TARGET_RELATIVE_SHIP
        and tuple(matched.get("star_local", ())) == NATIVE_STAR_LOCAL
        and matched.get("complete_page_palette_band_mismatches") == 0,
        "provenance records the exact adjacent product pose and palette-band match",
    )
    check(
        authority.get("snapshot_camera_state_retained") is True
        and authority.get("snapshot_page_and_palette_retained") is True
        and authority.get("snapshot_simulation_state_retained") is False
        and authority.get("whole_page_same_state_contract") is False
        and math.isclose(
            authority.get("matched_product_phase_bracket_seconds", 0),
            0.23529410362243652,
            abs_tol=1e-12,
        ),
        "provenance limits grading to the retained two-source phase bracket",
    )

    if args.product_directory is not None:
        directory = args.product_directory
        required = product_paths(directory)
        for path, size in required:
            check(path.is_file() and path.stat().st_size == size,
                  f"product emitted {path.name} at exactly {size} bytes")
        if all(path.is_file() and path.stat().st_size == size for path, size in required):
            local = (directory / "orbitmultipletriple-game-local-out.bin").read_bytes()
            page = (directory / "orbitmultipletriple-game-page-out.bin").read_bytes()
            palette_data = (
                directory / "orbitmultipletriple-game-palette-out.bin"
            ).read_bytes()
            product_palette = struct.unpack("<768I", palette_data)
            header = struct.unpack_from("<8i", local)
            binary64 = lambda unit: struct.unpack_from("<d", local, unit * 4)[0]
            ship = (binary64(8), binary64(10), binary64(12))
            target = (binary64(14), binary64(16), binary64(18))
            second = (binary64(30), binary64(32), binary64(34))
            check(
                header[:2] == (0, 1)
                and header[3:] == (1345723226, 0, 0, 113, 0),
                "product retains the matched interior clock, target, and camera",
            )
            check(
                ship == TARGET_RELATIVE_SHIP
                and target == TARGET_ABSOLUTE
                and math.isclose(binary64(20), 12.72, abs_tol=1e-12),
                "product retains the exact selected-companion-relative pose",
            )
            product_local = tuple(target[index] + ship[index] for index in range(3))
            check(
                product_local == NATIVE_STAR_LOCAL,
                "product and native retain the exact same star-relative Stardrifter pose",
            )
            check(
                struct.unpack_from("<2i", local, 28 * 4) == (1, 10)
                and all(math.isclose(value, expected, abs_tol=1e-9)
                        for value, expected in zip(second, SECOND_RELATIVE))
                and math.isclose(binary64(36), 2835.641565056107, abs_tol=1e-9)
                and math.isclose(binary64(38), 10.86, abs_tol=1e-12)
                and struct.unpack_from("<3i", local, 40 * 4) == (1, 73, 101),
                "product independently retains and admits the second companion flare",
            )

            target_relative = tuple(-value for value in ship)
            target_distance = math.sqrt(sum(value * value for value in target_relative))
            second_distance = binary64(36)
            check(
                project_flare(target_relative) == (255, 99)
                and project_flare(second) == (73, 101)
                and 5 * binary64(20) < target_distance < 1000 * binary64(20)
                and 5 * binary64(38) < second_distance < 1000 * binary64(38),
                "source projection and strict distance gates admit both companions",
            )

            product_target = connected_component(page, TARGET_PRODUCT_SEED, 79)
            product_second = connected_component(page, SECOND_PRODUCT_SEED, 79)
            product_target_core = connected_component(page, TARGET_PRODUCT_SEED, 87)
            product_second_core = connected_component(page, SECOND_PRODUCT_SEED, 87)
            check(
                len(product_target) >= 240
                and bounds(product_target) is not None
                and bounds(product_target)[0] >= 200
                and bounds(product_target)[2] < 280
                and len(product_target_core) >= 40,
                "product retains a substantial isolated right companion corona and core",
            )
            check(
                len(product_second) >= 80
                and bounds(product_second) is not None
                and bounds(product_second)[0] >= 40
                and bounds(product_second)[2] < 100
                and len(product_second_core) >= 35,
                "product retains a substantial isolated left companion corona and core",
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
                    band_mismatches == 0,
                    "product matches all 64,000 native complete-page palette bands",
                )
                check(
                    len(product_target) >= 0.70 * len(native_target)
                    and len(product_second) >= 0.70 * len(native_second),
                    "product preserves substantial native components for both lights",
                )
                print(
                    "INFO whole-page equality remains ungraded "
                    f"({index_mismatches} indices, {band_mismatches} bands, "
                    f"{palette_mismatches} palette components differ)"
                )

    if failures:
        print(f"dual-companion orbitmultiple oracle: {len(failures)} failure(s)")
        return 1
    print("dual-companion orbitmultiple oracle: all requested checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
