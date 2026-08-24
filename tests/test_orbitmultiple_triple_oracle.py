"""Grade two generated companion suns across three Stardrifter views."""

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
ROOF_ORACLE = OUT / "orbitmultiple_triple_roof_3229_native.shot.BMP"
ROOF_PROVENANCE = OUT / "orbitmultiple_triple_roof_3229_native.provenance.json"
EXTERIOR_ORACLE = OUT / "orbitmultiple_triple_exterior_3226_native.shot.BMP"
EXTERIOR_PROVENANCE = OUT / "orbitmultiple_triple_exterior_3226_native.provenance.json"
CAPTURE_TOOL = ROOT / "tools" / "capture_noctis_scenes.ps1"
BMP_SHA256 = "e3ea5a56146280907a11073704a8227b40006edc7a0c1dbaf17bd8ca43eeaeeb"
PAGE_SHA256 = "3d7f9ea0cd369edbd7e6a16196082b0fa49d532923ad6f3093bff671bf2f8f7a"
PALETTE_SHA256 = "836c0249a021dd30dbfdd743846d98163af3a8ee316b25c09a79043f80125dd2"
PROVENANCE_SHA256 = "65b05da7905cbfe640ea642d9a427b6e87a1eeafc4a7f1e5cb87020c3a67f5a3"
ROOF_BMP_SHA256 = "ff447b2c7025a0b91073c758d2929a72d804bedfb14e3ea79779e67321037b6b"
ROOF_PAGE_SHA256 = "d4b230cba9f010062598e7436dd4e35ca4aa0f76090454662582eb4d8f9f3609"
ROOF_PROVENANCE_SHA256 = "f577cc38c154fcb5361c7151c5c03495345e3088af6a45a0f2c5b5d41beffd0f"
EXTERIOR_BMP_SHA256 = "c699b068d9044d8e5ef5401648dc388fb08cc1e274107ceda8c16dcc08ce8f78"
EXTERIOR_PAGE_SHA256 = "a57b6fa34165b1423e7c432493fe093ebc9af6f3a463478e9efd7cc9997a0a9d"
EXTERIOR_PROVENANCE_SHA256 = "26a8a8fa16f3a4b4c76cefcb4839288d51c0fa0ce27f7ad0c68acb174e496a2a"
EXTERIOR_PRODUCT_PAGE_SHA256 = "5ac348482a7efa1ad6fe98bf12caca007396b3a326fe776ed9e620c4965f96b6"
EXTERIOR_PRODUCT_PALETTE_SHA256 = "e1775b253fd37e9f863a944287358524fbcc46b83a0b0f27d51a2a1a59593555"
STAR = (4142128, -5182625, -629021)
TARGET_NATIVE_SEED = (251, 99)
SECOND_NATIVE_SEED = (68, 101)
TARGET_PRODUCT_SEED = (249, 96)
SECOND_PRODUCT_SEED = (67, 98)
ROOF_TARGET_PRODUCT_SEED = (249, 99)
ROOF_SECOND_PRODUCT_SEED = (68, 100)
EXTERIOR_SECOND_NATIVE_SEED = (68, 101)
EXTERIOR_SECOND_PRODUCT_SEED = (67, 98)
PRIMARY_PROJECTION = (232, 99)
TARGET_PROJECTION = (255, 99)
PRIMARY_HULL_WINDOW = (222, 91, 242, 107)
TARGET_HULL_WINDOW = (245, 91, 265, 107)
RIGHT_HULL = (209, 40, 319, 145)
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
ROOF_TARGET_RELATIVE_SHIP = (
    -2835.414399641379,
    17.236258154580206,
    35.8916321792845,
)
ROOF_TARGET_ABSOLUTE = (
    101.31336717754519,
    -2.6696913799585995,
    -264.4883958869819,
)
ROOF_SECOND_RELATIVE = (
    1958.3532561629777,
    17.23625815470804,
    2050.784101463341,
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


def crop_values(
    page: bytes,
    box: tuple[int, int, int, int],
) -> tuple[int, ...]:
    x0, y0, x1, y1 = box
    return tuple(
        page[y * 320 + x]
        for y in range(y0, y1 + 1)
        for x in range(x0, x1 + 1)
    )


def shifted(
    points: set[tuple[int, int]],
    dx: int,
    dy: int,
) -> set[tuple[int, int]]:
    return {(x + dx, y + dy) for x, y in points}


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


def product_paths(
    directory: Path,
    prefix: str = "orbitmultipletriple",
) -> tuple[tuple[Path, int], ...]:
    return tuple(
        (directory / f"{prefix}-{name}", size)
        for name, size in DIAGNOSTIC_SIZES
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-directory", type=Path)
    parser.add_argument("--roof-product-directory", type=Path)
    parser.add_argument("--exterior-product-directory", type=Path)
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
    roof_scene = capture.partition(
        "@{ Name='orbitmultipletripleroof'"
    )[2].partition("},")[0]
    check(
        "'orbitmultipletripleroof'" in capture
        and all(token in roof_scene for token in (
            "X=4142128; Y=-5182625; Z=-629021; Body=0; Type=10",
            "Lon=0; Lat=60",
            "Beta=0; Nav=113; Pitch=0",
            "PlayerX=0; PlayerY=-750; PlayerZ=-1900",
            "Sync=0",
            "LocalX=-2835.414399641379",
            "LocalY=17.236258154580206",
            "LocalZ=35.8916321792845",
        )),
        "capture tool retains the stable dual-companion roof/cupola pose",
    )
    exterior_scene = capture.partition(
        "@{ Name='orbitmultipletripleexterior'"
    )[2].partition("},")[0]
    check(
        "'orbitmultipletripleexterior'" in capture
        and all(token in exterior_scene for token in (
            "X=4142128; Y=-5182625; Z=-629021; Body=0; Type=10",
            "Lon=0; Lat=60",
            "Beta=0; Nav=113; Pitch=0",
            "PlayerX=2813; PlayerY=0; PlayerZ=-1397",
            "Sync=0",
            "LocalX=-2835.4143674072257",
            "LocalY=17.236258154580206",
            "LocalZ=35.891644488482996",
        )),
        "capture tool retains the dual-companion exterior hull pose",
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

    roof_oracle_data = ROOF_ORACLE.read_bytes()
    check(sha256(roof_oracle_data) == ROOF_BMP_SHA256,
          "retained dual-companion roof BMP has its pinned SHA-256")
    try:
        roof_native_page, roof_native_palette = decode_bmp(roof_oracle_data)
    except (AssertionError, OSError, struct.error) as error:
        check(False, f"dual-companion roof BMP decodes safely: {error}")
        roof_native_page, roof_native_palette = b"", ()
    else:
        check(sha256(roof_native_page) == ROOF_PAGE_SHA256,
              "roof oracle retains its complete indexed page")
        check(sha256(bytes(roof_native_palette)) == PALETTE_SHA256,
              "roof oracle retains all active six-bit palette components")

    roof_native_target: set[tuple[int, int]] = set()
    roof_native_second: set[tuple[int, int]] = set()
    roof_native_target_core: set[tuple[int, int]] = set()
    roof_native_second_core: set[tuple[int, int]] = set()
    if roof_native_page:
        roof_native_target = connected_component(
            roof_native_page, TARGET_NATIVE_SEED, 79)
        roof_native_second = connected_component(
            roof_native_page, SECOND_NATIVE_SEED, 79)
        roof_native_target_core = connected_component(
            roof_native_page, TARGET_NATIVE_SEED, 87)
        roof_native_second_core = connected_component(
            roof_native_page, SECOND_NATIVE_SEED, 87)
        check(
            len(roof_native_target) == 236
            and bounds(roof_native_target) == (212, 97, 264, 104)
            and len(roof_native_target_core) == 48
            and bounds(roof_native_target_core) == (244, 97, 256, 101),
            "native roof view retains the isolated right corona and core",
        )
        check(
            len(roof_native_second) == 115
            and bounds(roof_native_second) == (56, 97, 77, 106)
            and len(roof_native_second_core) == 57
            and bounds(roof_native_second_core) == (64, 97, 73, 104),
            "native roof view retains the isolated left corona and core",
        )

    roof_provenance_data = ROOF_PROVENANCE.read_bytes()
    check(
        sha256(roof_provenance_data.replace(b"\r\n", b"\n")) ==
        ROOF_PROVENANCE_SHA256,
        "dual-companion roof provenance has its pinned normalized SHA-256",
    )
    try:
        roof_provenance = json.loads(roof_provenance_data)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        check(False, f"dual-companion roof provenance decodes safely: {error}")
        roof_provenance = {}
    roof_continuity = roof_provenance.get("continuity_after_snapshot", {})
    roof_visibility = roof_provenance.get("native_visibility", {})
    roof_matched = roof_provenance.get("matched_product_contract", {})
    roof_authority = roof_provenance.get("authority", {})
    check(
        roof_provenance.get("artifact_sha256") == ROOF_BMP_SHA256
        and roof_provenance.get("star") == list(STAR)
        and roof_provenance.get("body_types") == [10, 10, 1]
        and roof_provenance.get("target_body") == 0
        and roof_provenance.get("second_companion_body") == 1,
        "roof provenance identifies both generated type-10 bodies",
    )
    check(
        roof_provenance.get("camera") == {
            "position": [0.0, -750.0, -1900.0],
            "user_alfa": 0.0,
            "user_beta": 0.0,
            "navigation_beta": 113.0,
            "on_roof": True,
            "cupola_aperture_distance": 1200.0,
        }
        and roof_continuity.get("sync") == 0
        and roof_continuity.get("ip_targetted") == 0
        and roof_continuity.get("ip_reached") == 1
        and roof_continuity.get("lifter") == 0
        and roof_continuity.get("fcs_status") == "STANDBY"
        and math.isclose(roof_continuity.get("secs", 0),
                         1345723228.9444444, abs_tol=1e-9)
        and tuple(roof_continuity.get("star_local", ())) == NATIVE_STAR_LOCAL,
        "roof provenance retains the stable camera and adjacent native state",
    )
    check(
        roof_visibility.get("target_companion_component_pixel_count") == 236
        and roof_visibility.get("second_companion_component_pixel_count") == 115
        and roof_visibility.get(
            "both_companions_visible_through_separate_cupola_panels"
        ) is True
        and roof_matched.get("complete_page_index_mismatches") == 416
        and roof_matched.get("complete_page_palette_band_mismatches") == 0
        and roof_matched.get("target_component_mask_mismatches_at_index_79") == 0
        and roof_matched.get("second_component_mask_mismatches_at_index_79") == 0,
        "roof provenance records exact two-source masks and complete-page bands",
    )
    check(
        roof_authority.get("snapshot_camera_state_retained") is True
        and roof_authority.get("snapshot_page_and_palette_retained") is True
        and roof_authority.get("snapshot_simulation_state_retained") is False
        and roof_authority.get("whole_page_same_state_contract") is False
        and math.isclose(
            roof_authority.get("matched_product_phase_bracket_seconds", 0),
            0.05555558204650879,
            abs_tol=1e-12,
        ),
        "roof provenance limits grading to its adjacent two-source phase",
    )

    exterior_oracle_data = EXTERIOR_ORACLE.read_bytes()
    check(
        sha256(exterior_oracle_data) == EXTERIOR_BMP_SHA256,
        "retained exterior hull-occlusion BMP has its pinned SHA-256",
    )
    try:
        exterior_native_page, exterior_native_palette = decode_bmp(
            exterior_oracle_data)
    except (AssertionError, OSError, struct.error) as error:
        check(False, f"dual-companion exterior BMP decodes safely: {error}")
        exterior_native_page, exterior_native_palette = b"", ()
    else:
        check(
            sha256(exterior_native_page) == EXTERIOR_PAGE_SHA256,
            "exterior oracle retains its complete indexed page",
        )
        check(
            sha256(bytes(exterior_native_palette)) == PALETTE_SHA256,
            "exterior oracle retains all active six-bit palette components",
        )

    exterior_native_second: set[tuple[int, int]] = set()
    exterior_native_second_core: set[tuple[int, int]] = set()
    exterior_native_primary_window: tuple[int, ...] = ()
    exterior_native_target_window: tuple[int, ...] = ()
    if exterior_native_page:
        exterior_native_second = connected_component(
            exterior_native_page, EXTERIOR_SECOND_NATIVE_SEED, 87)
        exterior_native_second_core = connected_component(
            exterior_native_page, EXTERIOR_SECOND_NATIVE_SEED, 95)
        exterior_native_primary_window = crop_values(
            exterior_native_page, PRIMARY_HULL_WINDOW)
        exterior_native_target_window = crop_values(
            exterior_native_page, TARGET_HULL_WINDOW)
        check(
            len(exterior_native_second) == 58
            and bounds(exterior_native_second) == (64, 97, 73, 104)
            and len(exterior_native_second_core) == 29
            and bounds(exterior_native_second_core) == (65, 97, 71, 104),
            "native exterior view retains the visible companion bright component",
        )
        check(
            (min(exterior_native_primary_window),
             max(exterior_native_primary_window)) == (46, 57)
            and (min(exterior_native_target_window),
                 max(exterior_native_target_window)) == (47, 62)
            and all(value < 64 for value in (
                exterior_native_primary_window + exterior_native_target_window
            )),
            "native primary and selected companion projections stay behind the hull",
        )

    exterior_provenance_data = EXTERIOR_PROVENANCE.read_bytes()
    check(
        sha256(exterior_provenance_data.replace(b"\r\n", b"\n")) ==
        EXTERIOR_PROVENANCE_SHA256,
        "dual-companion exterior provenance has its pinned normalized SHA-256",
    )
    try:
        exterior_provenance = json.loads(exterior_provenance_data)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        check(False, f"dual-companion exterior provenance decodes safely: {error}")
        exterior_provenance = {}
    exterior_continuity = exterior_provenance.get(
        "continuity_after_snapshot", {})
    exterior_visibility = exterior_provenance.get("native_visibility", {})
    exterior_matched = exterior_provenance.get("matched_product_contract", {})
    exterior_authority = exterior_provenance.get("authority", {})
    check(
        exterior_provenance.get("artifact_sha256") == EXTERIOR_BMP_SHA256
        and exterior_provenance.get("star") == list(STAR)
        and exterior_provenance.get("body_types") == [10, 10, 1]
        and exterior_provenance.get("target_body") == 0
        and exterior_provenance.get("second_companion_body") == 1,
        "exterior provenance identifies all independently graded sources",
    )
    check(
        exterior_provenance.get("camera") == {
            "position": [2813.0, 0.0, -1397.0],
            "user_alfa": 0.0,
            "user_beta": 0.0,
            "navigation_beta": 113.0,
            "outside_hull": True,
        }
        and exterior_continuity.get("sync") == 0
        and exterior_continuity.get("ip_targetted") == 0
        and exterior_continuity.get("ip_reached") == 1
        and exterior_continuity.get("lifter") == 0
        and exterior_continuity.get("fcs_status") == "STANDBY"
        and exterior_continuity.get("position") == [2813.0, 0.0, -1397.0]
        and exterior_continuity.get("angles") == [0.0, 0.0, 113.0]
        and math.isclose(
            exterior_continuity.get("secs", 0),
            1345723226.4444444,
            abs_tol=1e-9,
        )
        and tuple(exterior_continuity.get("star_local", ())) ==
        NATIVE_STAR_LOCAL,
        "exterior provenance retains the exact native camera and adjacent state",
    )
    check(
        exterior_visibility.get("bright_component_pixel_count") == 58
        and exterior_visibility.get("core_pixel_count") == 29
        and exterior_visibility.get("selected_companion_projection") == [255, 99]
        and exterior_visibility.get("primary_projection") == [232, 99]
        and exterior_visibility.get("visible_and_occluded_source_contract") is True,
        "exterior provenance records one visible and two hull-occluded sources",
    )
    check(
        exterior_matched.get("raw_clock") == 1345723226
        and tuple(exterior_matched.get("target_relative_stardrifter", ())) ==
        TARGET_RELATIVE_SHIP
        and tuple(exterior_matched.get("star_local", ())) == NATIVE_STAR_LOCAL
        and exterior_matched.get("complete_page_index_mismatches") == 37737
        and exterior_matched.get("complete_page_palette_band_mismatches") == 824
        and exterior_matched.get("right_hull_palette_band_mismatches") == 0
        and exterior_matched.get(
            "visible_companion_bright_mask_symmetric_difference") == 9
        and exterior_matched.get(
            "visible_companion_core_mask_symmetric_difference") == 7,
        "exterior provenance records matched hull bands and visible-source masks",
    )
    check(
        exterior_authority.get("snapshot_camera_state_retained") is True
        and exterior_authority.get("snapshot_page_and_palette_retained") is True
        and exterior_authority.get("snapshot_simulation_state_retained") is False
        and exterior_authority.get("whole_page_same_state_contract") is False
        and math.isclose(
            exterior_authority.get("matched_product_phase_bracket_seconds", 0),
            0.4444444179534912,
            abs_tol=1e-12,
        ),
        "exterior provenance limits grading to its adjacent hull-occlusion phase",
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

    if args.roof_product_directory is not None:
        directory = args.roof_product_directory
        prefix = "orbitmultipletripleroof"
        required = product_paths(directory, prefix)
        for path, size in required:
            check(path.is_file() and path.stat().st_size == size,
                  f"roof product emitted {path.name} at exactly {size} bytes")
        if all(path.is_file() and path.stat().st_size == size for path, size in required):
            local = (directory / f"{prefix}-game-local-out.bin").read_bytes()
            page = (directory / f"{prefix}-game-page-out.bin").read_bytes()
            palette_data = (directory / f"{prefix}-game-palette-out.bin").read_bytes()
            product_palette = struct.unpack("<768I", palette_data)
            header = struct.unpack_from("<8i", local)
            binary64 = lambda unit: struct.unpack_from("<d", local, unit * 4)[0]
            ship = (binary64(8), binary64(10), binary64(12))
            target = (binary64(14), binary64(16), binary64(18))
            second = (binary64(30), binary64(32), binary64(34))
            check(
                header[:2] == (0, 1)
                and header[3:] == (1345723229, 0, 0, 113, 0),
                "roof product retains the adjacent clock, target, and camera",
            )
            check(
                ship == ROOF_TARGET_RELATIVE_SHIP
                and target == ROOF_TARGET_ABSOLUTE
                and tuple(target[index] + ship[index] for index in range(3)) ==
                NATIVE_STAR_LOCAL,
                "roof product exactly matches the native star-relative pose",
            )
            check(
                struct.unpack_from("<2i", local, 28 * 4) == (1, 10)
                and all(math.isclose(value, expected, abs_tol=1e-9)
                        for value, expected in zip(second, ROOF_SECOND_RELATIVE))
                and math.isclose(binary64(36), 2835.6415335403276,
                                 abs_tol=1e-9)
                and math.isclose(binary64(38), 10.86, abs_tol=1e-12)
                and struct.unpack_from("<3i", local, 40 * 4) == (1, 73, 101),
                "roof product independently retains the second companion flare",
            )

            target_relative = tuple(-value for value in ship)
            target_distance = math.sqrt(sum(value * value for value in target_relative))
            check(
                project_flare(target_relative) == (255, 99)
                and project_flare(second) == (73, 101)
                and 5 * binary64(20) < target_distance < 1000 * binary64(20)
                and 5 * binary64(38) < binary64(36) < 1000 * binary64(38),
                "roof source projection and strict gates admit both companions",
            )

            roof_product_target = connected_component(
                page, ROOF_TARGET_PRODUCT_SEED, 79)
            roof_product_second = connected_component(
                page, ROOF_SECOND_PRODUCT_SEED, 79)
            roof_product_target_core = connected_component(
                page, ROOF_TARGET_PRODUCT_SEED, 87)
            roof_product_second_core = connected_component(
                page, ROOF_SECOND_PRODUCT_SEED, 87)
            check(
                len(roof_product_target) == 236
                and bounds(roof_product_target) == (212, 97, 264, 104)
                and len(roof_product_target_core) == 48
                and bounds(roof_product_target_core) == (244, 97, 256, 101),
                "roof product retains the isolated right corona and core",
            )
            check(
                len(roof_product_second) == 115
                and bounds(roof_product_second) == (56, 97, 77, 106)
                and len(roof_product_second_core) == 57
                and bounds(roof_product_second_core) == (64, 97, 73, 104),
                "roof product retains the isolated left corona and core",
            )

            if roof_native_page:
                index_mismatches = sum(
                    a != b for a, b in zip(roof_native_page, page))
                band_mismatches = sum(
                    (a & 0xC0) != (b & 0xC0)
                    for a, b in zip(roof_native_page, page)
                )
                palette_mismatches = sum(
                    a != b for a, b in zip(roof_native_palette, product_palette)
                )
                check(
                    roof_product_target == roof_native_target
                    and roof_product_second == roof_native_second
                    and roof_product_target_core == roof_native_target_core
                    and roof_product_second_core == roof_native_second_core,
                    "native and product have exact per-source roof component masks",
                )
                check(
                    band_mismatches == 0,
                    "roof product matches all 64,000 native palette bands",
                )
                print(
                    "INFO roof low-six and palette equality remain ungraded "
                    f"({index_mismatches} indices, {band_mismatches} bands, "
                    f"{palette_mismatches} palette components differ)"
                )

    if args.exterior_product_directory is not None:
        directory = args.exterior_product_directory
        prefix = "orbitmultipletripleexterior"
        required = product_paths(directory, prefix)
        for path, size in required:
            check(
                path.is_file() and path.stat().st_size == size,
                f"exterior product emitted {path.name} at exactly {size} bytes",
            )
        if all(path.is_file() and path.stat().st_size == size
               for path, size in required):
            local = (directory / f"{prefix}-game-local-out.bin").read_bytes()
            page = (directory / f"{prefix}-game-page-out.bin").read_bytes()
            palette_data = (
                directory / f"{prefix}-game-palette-out.bin"
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
                "exterior product retains the adjacent clock, target, and camera",
            )
            check(
                ship == TARGET_RELATIVE_SHIP
                and target == TARGET_ABSOLUTE
                and tuple(target[index] + ship[index] for index in range(3)) ==
                NATIVE_STAR_LOCAL,
                "exterior product exactly matches the native star-relative pose",
            )
            check(
                struct.unpack_from("<2i", local, 28 * 4) == (1, 10)
                and second == SECOND_RELATIVE
                and math.isclose(
                    binary64(36), 2835.641565056107, abs_tol=1e-9)
                and math.isclose(binary64(38), 10.86, abs_tol=1e-12)
                and struct.unpack_from("<3i", local, 40 * 4) == (1, 73, 101),
                "exterior product independently retains the visible companion flare",
            )

            target_relative = tuple(-value for value in ship)
            target_distance = math.sqrt(
                sum(value * value for value in target_relative))
            primary_relative = tuple(-value for value in NATIVE_STAR_LOCAL)
            primary_distance = math.sqrt(
                sum(value * value for value in primary_relative))
            check(
                project_flare(primary_relative) == PRIMARY_PROJECTION
                and project_flare(target_relative) == TARGET_PROJECTION
                and project_flare(second) == (73, 101)
                and 6 * system.ray < primary_distance < 1000 * system.ray
                and 5 * binary64(20) < target_distance < 1000 * binary64(20)
                and 5 * binary64(38) < binary64(36) < 1000 * binary64(38),
                "exterior projections and strict gates admit all three sources",
            )

            exterior_product_second = connected_component(
                page, EXTERIOR_SECOND_PRODUCT_SEED, 87)
            exterior_product_second_core = connected_component(
                page, EXTERIOR_SECOND_PRODUCT_SEED, 95)
            product_primary_window = crop_values(page, PRIMARY_HULL_WINDOW)
            product_target_window = crop_values(page, TARGET_HULL_WINDOW)
            check(
                len(exterior_product_second) == 53
                and bounds(exterior_product_second) == (63, 94, 71, 101)
                and len(exterior_product_second_core) == 24
                and bounds(exterior_product_second_core) == (65, 95, 70, 100),
                "exterior product retains the visible companion bright component",
            )
            check(
                (min(product_primary_window), max(product_primary_window)) ==
                (47, 50)
                and (min(product_target_window), max(product_target_window)) ==
                (47, 60)
                and all(value < 64 for value in (
                    product_primary_window + product_target_window
                )),
                "product primary and selected companion projections stay behind the hull",
            )
            check(
                sha256(page) == EXTERIOR_PRODUCT_PAGE_SHA256
                and sha256(palette_data) == EXTERIOR_PRODUCT_PALETTE_SHA256,
                "exterior product retains its matched page and palette hashes",
            )

            if exterior_native_page:
                index_mismatches = sum(
                    a != b for a, b in zip(exterior_native_page, page))
                band_mismatches = sum(
                    (a & 0xC0) != (b & 0xC0)
                    for a, b in zip(exterior_native_page, page)
                )
                palette_mismatches = sum(
                    a != b
                    for a, b in zip(exterior_native_palette, product_palette)
                )
                native_hull = crop_values(exterior_native_page, RIGHT_HULL)
                product_hull = crop_values(page, RIGHT_HULL)
                hull_band_mismatches = sum(
                    (a & 0xC0) != (b & 0xC0)
                    for a, b in zip(native_hull, product_hull)
                )
                primary_center = (
                    PRIMARY_PROJECTION[0] - 1, PRIMARY_PROJECTION[1] - 1,
                    PRIMARY_PROJECTION[0] + 1, PRIMARY_PROJECTION[1] + 1,
                )
                target_center = (
                    TARGET_PROJECTION[0] - 1, TARGET_PROJECTION[1] - 1,
                    TARGET_PROJECTION[0] + 1, TARGET_PROJECTION[1] + 1,
                )
                check(
                    crop_values(exterior_native_page, primary_center) ==
                    crop_values(page, primary_center)
                    and crop_values(exterior_native_page, target_center) ==
                    crop_values(page, target_center),
                    "native and product have index-exact occluded source centres",
                )
                check(
                    hull_band_mismatches == 0
                    and all(
                        (a & 0xC0) == (b & 0xC0)
                        for a, b in zip(
                            exterior_native_primary_window,
                            product_primary_window,
                        )
                    )
                    and all(
                        (a & 0xC0) == (b & 0xC0)
                        for a, b in zip(
                            exterior_native_target_window,
                            product_target_window,
                        )
                    ),
                    "native and product match every right-hull palette band",
                )
                check(
                    len(
                        exterior_native_second ^
                        shifted(exterior_product_second, 1, 3)
                    ) == 9
                    and len(
                        exterior_native_second_core ^
                        shifted(exterior_product_second_core, 1, 3)
                    ) == 7,
                    "visible companion retains its bounded cross-host placement masks",
                )
                check(
                    (index_mismatches, band_mismatches, palette_mismatches) ==
                    (37737, 824, 365),
                    "exterior complete-page differences remain explicit and bounded",
                )
                print(
                    "INFO exterior complete-page equality remains ungraded "
                    f"({index_mismatches} indices, {band_mismatches} bands, "
                    f"{palette_mismatches} palette components differ; "
                    f"{hull_band_mismatches} right-hull bands differ)"
                )

    if failures:
        print(f"dual-companion orbitmultiple oracle: {len(failures)} failure(s)")
        return 1
    print("dual-companion orbitmultiple oracle: all requested checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
