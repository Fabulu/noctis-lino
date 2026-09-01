"""Grade the retained six-case positive orbital-primary class gallery.

The gallery covers bodyless classes 1, 2, 3, 4, 8, and 9 at fifty stellar
radii. Every class is inside the ordinary flare and white-corona intervals and
outside the source's 5/6/10 exclusions. The retained pages grade exact local
palette-band morphology and independent centred bright components; non-atomic
whole-page equality remains informational.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys


ROOT = Path(__file__).resolve().parents[1]
ORACLE_ROOT = ROOT / "tests" / "native-oracles" / "orbital-positive-class-gallery"
HARNESS = ROOT / "noctis-harness"
STAR_SOURCE = ROOT / "work" / "vhstar.txt"
GAME = ROOT / "work" / "vhgame.txt"
CATALOGUE = ROOT / "work" / "starmap_exact.txt"
CAPTURE = ROOT / "tools" / "capture_noctis_scenes.ps1"
CURRENT_BUILDER = ROOT / "tests" / "gen" / "recon_w7b" / "mkcurrent.py"
FLARE_CROP = (120, 60, 195, 115)
CROP_BAND_SHA256 = "54f421304ba7e5d7a91209dd2f5f42769db4c430e4849ea47b596c5b615a9fda"
PRODUCT_FILES = {
    "view": ("game-vh-out.bin", 156),
    "palette": ("game-palette-out.bin", 3072),
    "page": ("game-page-out.bin", 64000),
}

METADATA = {
    "README.md": (
        7571,
        "23afa43942ce4728ea8491f303169babe60196b9f144031f2dcc334355557732",
    ),
    "provenance.json": (
        54445,
        "6ff958027eb1fe3e245db2e13b63e68d649c2c7ef613f0eddb9d66cb43122815",
    ),
}

CASES = {
    "class1-ybarra": {
        "scene": "stardrifterclass1",
        "label": "YBARRA",
        "catalogue": "YBARRA                np.float64(-2698.482807478778) 5476048 -5957484 82716 1",
        "star": (5476048, -5957484, 82716),
        "class": 1,
        "ray": 19.466999053955078,
        "spin": 0,
        "requested_distance": 973.3499526977539,
    },
    "class2-eogilie": {
        "scene": "stardrifterclass2",
        "label": "EOGILIE",
        "catalogue": "EOGILIE               np.float64(-63242.71270398989) 4265328 -5738799 2583670 1",
        "star": (4265328, -5738799, 2583670),
        "class": 2,
        "ray": 0.4819999933242798,
        "spin": 3,
        "requested_distance": 24.09999966621399,
    },
    "class3-redian": {
        "scene": "stardrifterclass3",
        "label": "REDIAN",
        "catalogue": "REDIAN                np.float64(-4758.331299749384) 4700336 -4332862 233642 1",
        "star": (4700336, -4332862, 233642),
        "class": 3,
        "ray": 20.06599998474121,
        "spin": 0,
        "requested_distance": 1003.2999992370605,
    },
    "class4-marrin": {
        "scene": "stardrifterclass4",
        "label": "MARRIN",
        "catalogue": "MARRIN                np.float64(-776.3305940460623) -1325712 773546 757027 1",
        "star": (-1325712, 773546, 757027),
        "class": 4,
        "ray": 18.986000061035156,
        "spin": 0,
        "requested_distance": 949.3000030517578,
    },
    "class8-solo": {
        "scene": "stardrifterclass8",
        "label": "SOLO",
        "catalogue": "SOLO                  np.float64(-31212.574237046658) 3844976 -4358971 1862310 1",
        "star": (3844976, -4358971, 1862310),
        "class": 8,
        "ray": 4.546999931335449,
        "spin": 0,
        "requested_distance": 227.34999656677246,
    },
    "class9-akyaasle": {
        "scene": "stardrifterclass9",
        "label": "AKYAASLE",
        "catalogue": "AKYAASLE              np.float64(-3199.875) -1150000 2650000 1050000 2",
        "star": (-1150000, 2650000, 1050000),
        "class": 9,
        "ray": 8.9399995803833,
        "spin": 0,
        "requested_distance": 446.99997901916504,
    },
}

OFF = {
    "sync": 0,
    "anti_rad": 1,
    "charge": 6,
    "ap_targetted": 9,
    "ip_targetted": 11,
    "ip_reached": 13,
    "pwr": 27,
    "ap_target_class": 31,
    "nearstar_class": 35,
    "nearstar_nop": 37,
    "pos_x": 39,
    "pos_y": 43,
    "pos_z": 47,
    "user_alfa": 51,
    "user_beta": 55,
    "navigation_beta": 59,
    "ap_target_ray": 63,
    "nearstar_ray": 67,
    "dzat_x": 71,
    "dzat_y": 79,
    "dzat_z": 87,
    "ap_target_x": 95,
    "ap_target_y": 103,
    "ap_target_z": 111,
    "nearstar_x": 119,
    "nearstar_y": 127,
    "nearstar_z": 135,
    "fcs_status": 183,
    "ap_reached": 232,
    "secs": 235,
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decode_bmp(data: bytes) -> tuple[bytes, tuple[int, ...]]:
    if len(data) != 65078 or data[:2] != b"BM":
        raise AssertionError("expected the complete 65,078-byte indexed BMP")
    declared_size = struct.unpack_from("<I", data, 2)[0]
    pixel_offset = struct.unpack_from("<I", data, 10)[0]
    layout = struct.unpack_from("<IiiHHI", data, 14)
    if declared_size != 116326:
        raise AssertionError(f"unexpected historical BMP size field {declared_size}")
    if (pixel_offset,) + layout != (1078, 40, 320, 200, 1, 8, 0):
        raise AssertionError("unexpected gallery BMP layout")

    palette: list[int] = []
    for index in range(256):
        blue, green, red, reserved = data[54 + 4 * index : 58 + 4 * index]
        if reserved or any(component & 3 for component in (red, green, blue)):
            raise AssertionError(f"palette entry {index} is not exact six-bit BGR0")
        palette.extend((red >> 2, green >> 2, blue >> 2))

    pixels = data[pixel_offset : pixel_offset + 64000]
    rows = [pixels[row * 320 : (row + 1) * 320] for row in range(200)]
    rows.reverse()
    return b"".join(rows), tuple(palette)


def decode_continuity(data: bytes) -> dict[str, object]:
    if len(data) < 245:
        raise AssertionError("continuity block is shorter than 245 bytes")

    def f32(name: str) -> float:
        return struct.unpack_from("<f", data, OFF[name])[0]

    def f64(name: str) -> float:
        return struct.unpack_from("<d", data, OFF[name])[0]

    return {
        "sync": data[OFF["sync"]],
        "anti_rad": data[OFF["anti_rad"]],
        "charge": data[OFF["charge"]],
        "ap_targetted": data[OFF["ap_targetted"]],
        "ap_reached": data[OFF["ap_reached"]],
        "ip_targetted": struct.unpack_from("<b", data, OFF["ip_targetted"])[0],
        "ip_reached": data[OFF["ip_reached"]],
        "pwr": struct.unpack_from("<h", data, OFF["pwr"])[0],
        "ap_target_class": struct.unpack_from("<h", data, OFF["ap_target_class"])[0],
        "nearstar_class": struct.unpack_from("<h", data, OFF["nearstar_class"])[0],
        "nearstar_nop": struct.unpack_from("<h", data, OFF["nearstar_nop"])[0],
        "ap_target_ray": f32("ap_target_ray"),
        "nearstar_ray": f32("nearstar_ray"),
        "camera_position": [f32(name) for name in ("pos_x", "pos_y", "pos_z")],
        "user_alfa": f32("user_alfa"),
        "user_beta": f32("user_beta"),
        "navigation_beta": f32("navigation_beta"),
        "dzat": [f64(name) for name in ("dzat_x", "dzat_y", "dzat_z")],
        "ap_target": [f64(name) for name in ("ap_target_x", "ap_target_y", "ap_target_z")],
        "nearstar": [f64(name) for name in ("nearstar_x", "nearstar_y", "nearstar_z")],
        "fcs_status": data[OFF["fcs_status"] : OFF["fcs_status"] + 11]
        .split(b"\0")[0]
        .decode(),
        "secs": f64("secs"),
    }


def crop_offsets(box: tuple[int, int, int, int]) -> tuple[int, ...]:
    x0, y0, x1, y1 = box
    if not (0 <= x0 <= x1 < 320 and 0 <= y0 <= y1 < 200):
        raise AssertionError(f"invalid inclusive crop {box}")
    return tuple(
        y * 320 + x
        for y in range(y0, y1 + 1)
        for x in range(x0, x1 + 1)
    )


def product_file(directory: Path, scene: str, name: str) -> Path:
    prefixed = directory / f"{scene}-{name}"
    return prefixed if prefixed.is_file() else directory / name


def load_product(directory: Path, scene: str, check) -> dict[str, bytes] | None:
    product: dict[str, bytes] = {}
    for key, (name, size) in PRODUCT_FILES.items():
        path = product_file(directory, scene, name)
        try:
            data = path.read_bytes()
        except OSError as error:
            check(False, f"current product {path.name} is readable: {error}")
            continue
        check(len(data) == size, f"current product emitted {path.name} at exactly {size} bytes")
        if len(data) == size:
            product[key] = data
    return product if len(product) == len(PRODUCT_FILES) else None


def mismatch_bounds(
    first: bytes, second: bytes, *, bands: bool = False
) -> tuple[int, tuple[int, int, int, int] | None]:
    points = []
    for offset, (left, right) in enumerate(zip(first, second)):
        different = ((left & 0xC0) != (right & 0xC0)) if bands else left != right
        if different:
            points.append((offset % 320, offset // 320))
    if not points:
        return 0, None
    return len(points), (
        min(x for x, _y in points),
        min(y for _x, y in points),
        max(x for x, _y in points),
        max(y for _x, y in points),
    )


def bright_contract(page: bytes) -> dict[str, object]:
    x0, y0, x1, y1 = FLARE_CROP
    points = {
        (x, y)
        for y in range(y0, y1 + 1)
        for x in range(x0, x1 + 1)
        if (page[y * 320 + x] & 0x3F) >= 40
    }
    total = len(points)
    components: list[list[tuple[int, int]]] = []
    while points:
        seed = next(iter(points))
        points.remove(seed)
        stack = [seed]
        component = []
        while stack:
            x, y = stack.pop()
            component.append((x, y))
            for neighbour_y in range(y - 1, y + 2):
                for neighbour_x in range(x - 1, x + 2):
                    neighbour = (neighbour_x, neighbour_y)
                    if neighbour in points:
                        points.remove(neighbour)
                        stack.append(neighbour)
        components.append(component)
    if not components:
        raise AssertionError("positive flare crop has no bright component")
    components.sort(key=lambda component: (-len(component), min(component)))
    core = components[0]
    return {
        "low_six_threshold": 40,
        "total_pixels": total,
        "largest_eight_connected_component_pixels": len(core),
        "largest_component_bounds": [
            min(x for x, _y in core),
            min(y for _x, y in core),
            max(x for x, _y in core),
            max(y for _x, y in core),
        ],
        "singleton_satellites": sorted(
            [list(component[0]) for component in components[1:] if len(component) == 1]
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=CASES)
    parser.add_argument("--product-directory", type=Path)
    args = parser.parse_args()

    failures: list[str] = []

    def check(condition: bool, message: str) -> None:
        print("PASS" if condition else "FAIL", message)
        if not condition:
            failures.append(message)

    metadata: dict[str, bytes] = {}
    for name, (expected_size, expected_hash) in METADATA.items():
        try:
            data = (ORACLE_ROOT / name).read_bytes()
        except OSError as error:
            check(False, f"retained gallery {name} is readable: {error}")
            continue
        metadata[name] = data
        check(
            len(data) == expected_size and sha256(data) == expected_hash,
            f"retained gallery {name} has its pinned size and SHA-256",
        )
    if len(metadata) != len(METADATA):
        return 1

    try:
        provenance = json.loads(metadata["provenance.json"])
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        check(False, f"gallery provenance decodes safely: {error}")
        return 1

    common = provenance.get("common", {})
    check(
        provenance.get("schema") == 1
        and provenance.get("case") == "orbital-positive-class-gallery"
        and provenance.get("classes") == [1, 2, 3, 4, 8, 9]
        and common.get("mode") == "untargeted-exterior-primary"
        and common.get("source_excluded_classes") == [5, 6, 10]
        and common.get("requested_distance_in_stellar_radii") == 50
        and common.get("camera")
        == {
            "position": [2813, 0, -1397],
            "user_alfa": 0,
            "user_beta": 23,
            "navigation_beta": 0,
            "source_exterior_beta": 203,
        }
        and common.get("flare_crop") == [120, 60, 195, 115]
        and common.get("flare_crop_pixels") == 4256
        and common.get("flare_crop_band_sha256") == CROP_BAND_SHA256,
        "provenance pins the common bodyless positive-primary geometry",
    )
    authority = common.get("authority", {})
    check(
        authority.get("native_snapshot_page_and_palette_retained") is True
        and authority.get("native_post_snapshot_continuity_retained") is True
        and authority.get("native_snapshot_simulation_state_retained") is False
        and authority.get("native_live_orbital_distance_retained") is True
        and authority.get("product_live_orbital_distance_retained") is False
        and authority.get("surface_or_body_claim") is False
        and authority.get("radial_spoke_presence_structurally_graded") is True
        and authority.get("whole_page_same_state_contract") is False
        and authority.get("matched_clock_hud_contract") is False,
        "gallery authority rejects unsupported body, clock, distance, and whole-page claims",
    )

    star_source = STAR_SOURCE.read_text(encoding="utf-8")
    game_source = GAME.read_text(encoding="utf-8")
    capture_source = CAPTURE.read_text(encoding="utf-8")
    builder_source = CURRENT_BUILDER.read_text(encoding="utf-8")
    check(
        "? A = 5 -> VHT premask smooth;" in star_source
        and "? A = 6 -> VHT premask smooth; ? A = 10 -> VHT premask smooth;"
        in star_source
        and "? A != 11 -> VHT premask flare range;" in star_source
        and "A = [VHTphase]; A % 360; ? A >= 90 -> VHT premask smooth;"
        in star_source
        and "[VHFdist0] = [VHTdist0]; [VHFdist1] = [VHTdist1]; => VH space flare;"
        in star_source
        and "[FI] = 6; => IntToF;" in star_source
        and "A = [VHGbeta]; A + [VHGnavbeta]; A + 180; A % 360;" in game_source,
        "product retains the ordinary positive class gate, class-11 exception, and exterior half-turn",
    )
    check(
        "$exteriorBeta = ($Spec.Beta + $navigation + 180.0)" in capture_source
        and "or -1 for an untargeted primary-star pose" in builder_source,
        "capture tooling retains the matched untargeted exterior authoring path",
    )

    records = provenance.get("cases", [])
    check(
        [record.get("slug") for record in records] == list(CASES),
        "provenance retains all six gallery cases in class order",
    )
    records_by_slug = {record.get("slug"): record for record in records}
    catalogue = CATALOGUE.read_text(encoding="utf-8")
    if str(HARNESS) not in sys.path:
        sys.path.insert(0, str(HARNESS))
    import ns_spec

    flare_offsets = crop_offsets(FLARE_CROP)
    selected_cases = (
        CASES.items()
        if args.case is None
        else ((args.case, CASES[args.case]),)
    )
    for slug, expected in selected_cases:
        print(f"--- {slug} ---")
        record = records_by_slug.get(slug)
        if not isinstance(record, dict):
            check(False, f"{slug} has structured provenance")
            continue
        case_root = ORACLE_ROOT / slug
        retained: dict[str, bytes] = {}
        retained_manifest = record.get("retained", {})
        for name, pin in retained_manifest.items():
            try:
                data = (case_root / name).read_bytes()
            except OSError as error:
                check(False, f"{slug} retained {name} is readable: {error}")
                continue
            retained[name] = data
            check(
                len(data) == pin.get("size") and sha256(data) == pin.get("sha256"),
                f"{slug} {name} has its pinned size and SHA-256",
            )
        if len(retained) != 8:
            check(False, f"{slug} retains all eight oracle artifacts")
            continue

        product_data = {
            "view": retained["product-vh.bin"],
            "palette": retained["product-palette.bin"],
            "page": retained["product-page.bin"],
        }
        if args.product_directory is not None:
            current_product = load_product(
                args.product_directory.resolve(), str(expected["scene"]), check,
            )
            if current_product is None:
                continue
            product_data = current_product

        try:
            native_page, native_palette = decode_bmp(retained["native.shot.BMP"])
            authored = decode_continuity(retained["native.CURRENT.BIN"])
            frozen = decode_continuity(retained["native-continuity.bin"])
            product_view = struct.unpack("<39i", product_data["view"])
            product_palette = struct.unpack("<768I", product_data["palette"])
        except (AssertionError, struct.error, UnicodeDecodeError) as error:
            check(False, f"{slug} retained oracle decodes safely: {error}")
            continue

        candidate = record.get("candidate", {})
        system = ns_spec.System(*expected["star"])
        check(
            candidate.get("star") == list(expected["star"])
            and candidate.get("star_label") == expected["label"]
            and candidate.get("star_class") == expected["class"]
            and candidate.get("star_ray") == expected["ray"]
            and candidate.get("ap_spin") == expected["spin"]
            and candidate.get("generated_system")
            == {
                "nop": 0,
                "nob": 0,
                "has_authentic_body": False,
                "has_landable_surface": False,
            }
            and system.cls == expected["class"]
            and system.ray == expected["ray"]
            and system.ap_spin == expected["spin"]
            and system.nop == 0
            and system.nob == 0,
            f"tracked model identifies {expected['label']} as the pinned bodyless class-{expected['class']} system",
        )
        check(
            expected["catalogue"] in catalogue,
            f"tracked catalogue retains the {expected['label']} label, identity, and coordinates",
        )

        native_provenance = record.get("native", {})
        check(
            authored == native_provenance.get("authored_continuity")
            and frozen == native_provenance.get("frozen_continuity")
            and authored["sync"] == 0
            and authored["ip_targetted"] == -1
            and authored["pwr"] == 20000
            and authored["nearstar_class"] == expected["class"]
            and authored["nearstar_nop"] == 0
            and authored["camera_position"] == [2813.0, 0.0, -1397.0]
            and authored["user_alfa"] == 0.0
            and authored["user_beta"] == 23.0
            and authored["navigation_beta"] == 0.0
            and authored["fcs_status"] == "STANDBY"
            and authored["secs"] == 1345723200.0
            and frozen["pwr"] == 19999,
            f"{expected['label']} input and frozen continuity retain the exact untargeted exterior pose",
        )
        check(
            retained["native-capture.cmd"].splitlines()
            == [
                b"date 24.08.2026",
                b"time 12:00:00.00",
                b"cd modules",
                b"autotype -w 30 -p 3 b",
                b"noctis.exe",
            ],
            f"{expected['label']} command retains the authored clock and silent capture path",
        )

        pose = record.get("authored_pose", {})
        star = tuple(float(value) for value in expected["star"])
        relative = tuple(star[index] - frozen["dzat"][index] for index in range(3))
        distance = math.sqrt(sum(component * component for component in relative))
        source_distance = distance + 1.0
        flare = record.get("orbital_flare_contract", {})
        check(
            pose.get("requested_star_distance") == expected["requested_distance"]
            and tuple(pose.get("star_minus_dzat", ())) == relative
            and tuple(pose.get("dzat", ())) == tuple(frozen["dzat"])
            and math.isclose(distance, pose.get("retained_star_distance"), rel_tol=0, abs_tol=1e-12)
            and math.isclose(source_distance, pose.get("source_l_dsd"), rel_tol=0, abs_tol=1e-12)
            and 6 * expected["ray"] < source_distance < 1000 * expected["ray"]
            and 8 * expected["ray"] < source_distance < 100 * expected["ray"]
            and flare.get("strictly_inside_distance_interval") is True
            and flare.get("strictly_inside_white_corona_interval") is True
            and flare.get("source_class_eligible") is True
            and flare.get("class11_phase_gate_applies") is False
            and flare.get("textured_globe_expected") is False
            and flare.get("radial_spokes_expected") is True,
            f"{expected['label']} continuity is inside both positive orbital intervals",
        )

        scene_fragment = f"Name='{expected['scene']}'"
        coordinate_fragment = (
            f"X={expected['star'][0]}; Y={expected['star'][1]}; Z={expected['star'][2]}"
        )
        distance_fragment = f"StarDistance={expected['requested_distance']}"
        check(
            scene_fragment in capture_source
            and coordinate_fragment in capture_source
            and distance_fragment in capture_source,
            f"capture tooling authors the matched {expected['label']} bodyless pose",
        )

        view_ray = struct.unpack_from("<f", product_data["view"], 13 * 4)[0]
        view_dzat_x = struct.unpack_from("<d", product_data["view"], 8 * 4)[0]
        product = record.get("product", {})
        check(
            product_view[:5] == (2813, 0, -1397, 0, 23)
            and view_dzat_x == frozen["dzat"][0]
            and product_view[10:13] == (30000, 0, expected["class"])
            and view_ray == expected["ray"]
            and product_view[14:17] == (0, 0, 1)
            and product.get("camera", {}).get("dzat_x") == view_dzat_x
            and product.get("stellar_state")
            == {
                "class": expected["class"],
                "ray": expected["ray"],
                "nop": 0,
                "nob": 0,
                "ap_reached": 1,
            }
            and product.get("clock_matches_native") is False
            and product.get("clock_independent_contract") is True
            and product.get("live_orbital_distance_retained") is False,
            f"product view retains {expected['label']} camera, class, ray, and zero-body state",
        )

        packed_native_palette = struct.pack("<768I", *native_palette)
        check(
            len(native_page) == 64000
            and sha256(native_page) == native_provenance.get("indexed_page_sha256")
            and len(native_palette) == 768
            and sha256(packed_native_palette)
            == native_provenance.get("six_bit_palette_sha256"),
            f"{expected['label']} BMP yields the pinned indexed page and six-bit palette",
        )
        palette_mismatches = [
            index
            for index, (native, product_component) in enumerate(
                zip(native_palette, product_palette)
            )
            if native != product_component
        ]
        comparison = record.get("native_product_comparison", {})
        exact_prefix = palette_mismatches[0] if palette_mismatches else 768
        mismatch_component_bounds = (
            None
            if not palette_mismatches
            else [min(palette_mismatches), max(palette_mismatches)]
        )
        check(
            all(component <= 63 for component in product_palette)
            and exact_prefix == comparison.get("palette_exact_prefix_components")
            and len(palette_mismatches)
            == comparison.get("palette_component_mismatches")
            and mismatch_component_bounds
            == comparison.get("palette_mismatch_component_bounds"),
            f"product retains {expected['label']}'s pinned native palette prefix",
        )

        product_page = product_data["page"]
        adapted_page = retained["native.adapted"][:64000]
        native_crop = bytes(native_page[offset] for offset in flare_offsets)
        product_crop = bytes(product_page[offset] for offset in flare_offsets)
        adapted_crop = bytes(adapted_page[offset] for offset in flare_offsets)
        native_product_crop_indices = sum(
            left != right for left, right in zip(native_crop, product_crop)
        )
        native_adapted_crop_indices = sum(
            left != right for left, right in zip(native_crop, adapted_crop)
        )
        native_bands = bytes(value & 0xC0 for value in native_crop)
        check(
            len(flare_offsets) == 4256
            and native_adapted_crop_indices
            == comparison.get("native_adapted_flare_crop_index_mismatches")
            and native_bands == bytes(value & 0xC0 for value in product_crop)
            and native_bands == bytes(value & 0xC0 for value in adapted_crop)
            and sha256(native_bands) == CROP_BAND_SHA256
            and comparison.get("native_product_flare_crop_palette_band_mismatches")
            == 0
            and comparison.get("native_adapted_flare_crop_palette_band_mismatches")
            == 0,
            f"native, adapted, and product retain every {expected['label']} flare-crop band",
        )
        if args.product_directory is None:
            check(
                native_product_crop_indices
                == comparison.get("native_product_flare_crop_index_mismatches"),
                f"retained product preserves {expected['label']}'s provenance-pinned crop comparison",
            )

        native_bright = bright_contract(native_page)
        product_bright = bright_contract(product_page)
        check(
            native_bright == comparison.get("native_bright")
            and product_bright == comparison.get("product_bright")
            and native_bright["largest_eight_connected_component_pixels"] >= 111
            and product_bright["largest_eight_connected_component_pixels"] >= 108,
            f"native and product retain {expected['label']}'s centred bright positive-flare component",
        )

        native_product_indices = mismatch_bounds(native_page, product_page)
        native_product_bands = mismatch_bounds(native_page, product_page, bands=True)
        native_adapted_indices = mismatch_bounds(native_page, adapted_page)
        native_adapted_bands = mismatch_bounds(native_page, adapted_page, bands=True)
        check(
            native_adapted_indices
            == (
                comparison.get("bmp_vs_adapted_index_mismatches"),
                tuple(comparison.get("bmp_vs_adapted_index_mismatch_bounds")),
            )
            and native_adapted_bands
            == (
                comparison.get("bmp_vs_adapted_palette_band_mismatches"),
                tuple(comparison.get("bmp_vs_adapted_palette_band_mismatch_bounds")),
            ),
            f"{expected['label']} provenance records the historical whole-page authority limits",
        )
        if args.product_directory is None:
            check(
                native_product_indices
                == (
                    comparison.get("whole_page_index_mismatches"),
                    tuple(comparison.get("whole_page_index_mismatch_bounds")),
                )
                and native_product_bands
                == (
                    comparison.get("whole_page_palette_band_mismatches"),
                    tuple(comparison.get("whole_page_palette_band_mismatch_bounds")),
                ),
                f"retained {expected['label']} product page preserves its provenance-pinned comparisons",
            )
        print(
            "INFO complete native/product equality is not graded "
            f"({native_product_indices[0]} indices, {native_product_bands[0]} bands)"
        )

    if failures:
        print(f"FAIL {len(failures)} positive orbital-primary gallery checks")
        return 1
    print("PASS six-case positive orbital-primary class gallery")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
