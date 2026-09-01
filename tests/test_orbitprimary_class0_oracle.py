"""Grade the retained EMPTY class-0 positive orbital-primary flare oracle.

EMPTY has no generated bodies, so this is an untargeted exterior checkpoint.
The authored distance is inside both the ordinary orbital flare and white-corona
intervals, while eligible class 0 admits the source's radial spokes. Whole-page
equality is not a same-state contract.
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
ORACLE_ROOT = ROOT / "tests" / "native-oracles" / "orbital-class0-empty"
HARNESS = ROOT / "noctis-harness"
STAR_SOURCE = ROOT / "work" / "vhstar.txt"
GAME = ROOT / "work" / "vhgame.txt"
CATALOGUE = ROOT / "work" / "starmap_exact.txt"
CAPTURE = ROOT / "tools" / "capture_noctis_scenes.ps1"
CURRENT_BUILDER = ROOT / "tests" / "gen" / "recon_w7b" / "mkcurrent.py"

RETAINED = {
    "README.md": (
        5545, "feb722987a2f29361396aeac9a80d8a264510268b8918bfebbd2de43964eb517",
    ),
    "native-capture.cmd": (
        82, "3de94c13c72b31f0fc2df95e07fa53176b3a72e11f1d4ff1634805408cb19b93",
    ),
    "native-continuity.bin": (
        245, "d01d0c29f771a56f126426c04ab7e5e82ceaef09453c86eb16673162e3d4eef3",
    ),
    "native.CURRENT.BIN": (
        385, "772bc1ad76fc36244bfa2398fe9c57c1a0994ab3795355d4521973831072afce",
    ),
    "native.adapted": (
        65540, "3be09754365343bfd7288d82d0d27ba003bc403b397722740dc3caeea661c989",
    ),
    "native.shot.BMP": (
        65078, "30c4ccf033a01b3d8046c31c861d457f5c28f0634eccd93f1f0c9022a52a3ced",
    ),
    "product-page.bin": (
        64000, "79ad249a665edfa49be6a9277496c62954ad60636db35c5996d43ec19aee60fd",
    ),
    "product-palette.bin": (
        3072, "2cf1c3be9905561ca8f53afddf7b078ab23f4f993b6890ab62a9afea06babac2",
    ),
    "product-vh.bin": (
        156, "5a89fcb4362ab22468ff3b14fd8af728421ff60e7bc4ac71f7dfcdbe154b7d08",
    ),
    "provenance.json": (
        8354, "dfa2a1318897bf8edfce05a1d73caac2784cdeceea4da338548b05e2418ca5db",
    ),
}
NATIVE_PAGE_SHA256 = "d3d99be81f6d4a5f84b76762f30bfb313fa156e6b5e2cb21391dd0f3e020d125"
NATIVE_PALETTE_SHA256 = "d492ce31940e0b5ae3e05ecd576d061117c9a7e3645a7c6b0fa5d6ab8f16d9b8"
FLARE_CROP = (120, 60, 195, 115)
SCENE = "stardrifterclass0"
PRODUCT_FILES = {
    "view": ("game-vh-out.bin", 156),
    "palette": ("game-palette-out.bin", 3072),
    "page": ("game-page-out.bin", 64000),
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
        raise AssertionError("unexpected EMPTY BMP layout")

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


def decode_continuity(data: bytes) -> dict[str, object]:
    if len(data) < 245:
        raise AssertionError("continuity block is shorter than 245 bytes")

    def i8(name: str) -> int:
        return struct.unpack_from("<b", data, OFF[name])[0]

    def u8(name: str) -> int:
        return data[OFF[name]]

    def i16(name: str) -> int:
        return struct.unpack_from("<h", data, OFF[name])[0]

    def f32(name: str) -> float:
        return struct.unpack_from("<f", data, OFF[name])[0]

    def f64(name: str) -> float:
        return struct.unpack_from("<d", data, OFF[name])[0]

    return {
        "sync": u8("sync"),
        "anti_rad": u8("anti_rad"),
        "charge": u8("charge"),
        "ap_targetted": u8("ap_targetted"),
        "ap_reached": u8("ap_reached"),
        "ip_targetted": i8("ip_targetted"),
        "ip_reached": u8("ip_reached"),
        "pwr": i16("pwr"),
        "ap_target_class": i16("ap_target_class"),
        "nearstar_class": i16("nearstar_class"),
        "nearstar_nop": i16("nearstar_nop"),
        "position": tuple(f32(name) for name in ("pos_x", "pos_y", "pos_z")),
        "angles": tuple(f32(name) for name in
                        ("user_alfa", "user_beta", "navigation_beta")),
        "rays": (f32("ap_target_ray"), f32("nearstar_ray")),
        "dzat": tuple(f64(name) for name in ("dzat_x", "dzat_y", "dzat_z")),
        "ap_target": tuple(f64(name) for name in
                           ("ap_target_x", "ap_target_y", "ap_target_z")),
        "nearstar": tuple(f64(name) for name in
                          ("nearstar_x", "nearstar_y", "nearstar_z")),
        "fcs_status": data[OFF["fcs_status"]:OFF["fcs_status"] + 11].split(b"\0")[0].decode(),
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


def bright_low_six_contract(
        page: bytes, box: tuple[int, int, int, int], threshold: int,
) -> tuple[int, tuple[int, int, int, int]]:
    x0, y0, x1, y1 = box
    points = [
        (x, y)
        for y in range(y0, y1 + 1)
        for x in range(x0, x1 + 1)
        if page[y * 320 + x] & 0x3F >= threshold
    ]
    if not points:
        return 0, (0, 0, 0, 0)
    return len(points), (
        min(x for x, _y in points), min(y for _x, y in points),
        max(x for x, _y in points), max(y for _x, y in points),
    )


def mismatch_bounds(
        first: bytes, second: bytes, *, bands: bool = False,
) -> tuple[int, tuple[int, int, int, int] | None]:
    points = []
    for offset, (left, right) in enumerate(zip(first, second)):
        different = ((left & 0xC0) != (right & 0xC0)) if bands else left != right
        if different:
            points.append((offset % 320, offset // 320))
    if not points:
        return 0, None
    return len(points), (
        min(x for x, _y in points), min(y for _x, y in points),
        max(x for x, _y in points), max(y for _x, y in points),
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

    retained: dict[str, bytes] = {}
    for name, (expected_size, expected_hash) in RETAINED.items():
        try:
            data = (ORACLE_ROOT / name).read_bytes()
        except OSError as error:
            check(False, f"retained {name} is readable: {error}")
            continue
        retained[name] = data
        check(
            len(data) == expected_size and sha256(data) == expected_hash,
            f"retained {name} has its pinned size and SHA-256",
        )
    if len(retained) != len(RETAINED):
        print(f"FAIL {len(failures)} class-0 orbital-primary checks")
        return 1

    product = {
        "view": retained["product-vh.bin"],
        "palette": retained["product-palette.bin"],
        "page": retained["product-page.bin"],
    }
    if args.product_directory is not None:
        current_product = load_product(args.product_directory.resolve(), check)
        if current_product is None:
            print(f"FAIL {len(failures)} class-0 orbital-primary checks")
            return 1
        product = current_product

    try:
        provenance = json.loads(retained["provenance.json"])
        native_page, native_palette = decode_bmp(retained["native.shot.BMP"])
        authored = decode_continuity(retained["native.CURRENT.BIN"])
        frozen = decode_continuity(retained["native-continuity.bin"])
        adapted_page = retained["native.adapted"][:64000]
        product_view = struct.unpack("<39i", product["view"])
        product_palette = struct.unpack("<768I", product["palette"])
        product_page = product["page"]
    except (AssertionError, json.JSONDecodeError, struct.error, UnicodeDecodeError) as error:
        check(False, f"retained class-0 oracle decodes safely: {error}")
        return 1

    if str(HARNESS) not in sys.path:
        sys.path.insert(0, str(HARNESS))
    import ns_spec
    system = ns_spec.System(2931408, -6222148, 1891299)
    check(
        system.cls == 0
        and math.isclose(system.ray, 6.445000171661377, rel_tol=0, abs_tol=1e-15)
        and system.ap_spin == 0
        and system.nop == 0
        and system.nob == 0,
        "tracked model identifies EMPTY as a bodyless class-0 system",
    )
    catalogue = CATALOGUE.read_text(encoding="utf-8")
    check(
        "EMPTY                 np.float64(-34496.640173183034) 2931408 -6222148 1891299" in catalogue,
        "tracked catalogue retains the EMPTY label and coordinates",
    )

    ray = system.ray
    star = (2931408.0, -6222148.0, 1891299.0)
    expected_dzat = (2931282.0868904907, -6222148.0, 1891595.632696926)
    authored_expected = {
        "sync": 0, "anti_rad": 1, "charge": 3,
        "ap_targetted": 1, "ap_reached": 1,
        "ip_targetted": -1, "ip_reached": 0,
        "pwr": 20000, "ap_target_class": 0, "nearstar_class": 0,
        "nearstar_nop": 0, "position": (2813.0, 0.0, -1397.0),
        "angles": (0.0, 23.0, 0.0), "rays": (ray, ray),
        "dzat": expected_dzat, "ap_target": star, "nearstar": star,
        "fcs_status": "STANDBY", "secs": 1345723200.0,
    }
    frozen_expected = dict(authored_expected)
    frozen_expected.update(pwr=19999, secs=1345723227.4444444)
    check(authored == authored_expected, "native input retains the exact untargeted exterior pose")
    check(frozen == frozen_expected, "extracted frozen continuity retains the live class-0 pose")
    check(
        retained["native-capture.cmd"].splitlines() == [
            b"date 24.08.2026", b"time 12:00:00.00", b"cd modules",
            b"autotype -w 30 -p 3 b", b"noctis.exe",
        ],
        "native command retains the authored source clock and silent capture path",
    )

    relative = tuple(star[index] - frozen["dzat"][index] for index in range(3))
    star_distance = math.sqrt(sum(component * component for component in relative))
    source_distance = star_distance + 1.0
    check(
        relative == (125.91310950927436, 0.0, -296.6326969258953)
        and math.isclose(star_distance, 322.25000858312563, rel_tol=0, abs_tol=1e-12)
        and math.isclose(source_distance, 323.25000858312563, rel_tol=0, abs_tol=1e-12)
        and 6 * ray < source_distance < 1000 * ray
        and 8 * ray < source_distance < 100 * ray,
        "native continuity is inside the orbital flare and white-corona intervals",
    )

    candidate = provenance.get("candidate", {})
    flare = provenance.get("orbital_flare_contract", {})
    check(
        provenance.get("schema") == 1
        and provenance.get("case") == "empty-class0-primary"
        and candidate == {
            "star": [2931408, -6222148, 1891299],
            "star_label": "EMPTY",
            "hud_suffix": "S00",
            "star_class": 0,
            "star_ray": ray,
            "ap_spin": 0,
            "generated_system": {
                "nop": 0, "nob": 0,
                "has_authentic_body": False,
                "has_landable_surface": False,
            },
            "mode": "untargeted-exterior-primary",
        }
        and flare.get("source_excluded_classes") == [5, 6, 10]
        and flare.get("source_class_eligible") is True
        and flare.get("strictly_inside_distance_interval") is True
        and flare.get("strictly_inside_white_corona_interval") is True
        and flare.get("textured_globe_expected") is False
        and flare.get("radial_spokes_expected") is True,
        "provenance identifies the bodyless class-0 positive orbital-flare contract",
    )

    star_source = STAR_SOURCE.read_text(encoding="utf-8")
    game = GAME.read_text(encoding="utf-8")
    capture_source = CAPTURE.read_text(encoding="utf-8")
    current_builder = CURRENT_BUILDER.read_text(encoding="utf-8")
    check(
        "? A = 5 -> VHT premask smooth;" in star_source
        and "? A = 6 -> VHT premask smooth; ? A = 10 -> VHT premask smooth;" in star_source
        and "[VHTphase] = 0; [VHTprevphase] = 0; [VHTrenderphase] = 0; [VHTspin] = 0;" in star_source
        and "A = [VHTclass]; ? A = 11 -> VHT spin class11;" in star_source
        and "? A != 11 -> VHT premask flare range;" in star_source
        and "[VHFdist0] = [VHTdist0]; [VHFdist1] = [VHTdist1]; => VH space flare;" in star_source
        and "[FI] = 6; => IntToF;" in star_source
        and "A = [VHGbeta]; A + [VHGnavbeta]; A + 180; A % 360;" in game,
        "product retains the source positive class gate and exterior half-turn",
    )
    check(
        "Name='stardrifterclass0'" in capture_source
        and "X=2931408; Y=-6222148; Z=1891299" in capture_source
        and "StarDistance=322.25000858306885" in capture_source
        and "$exteriorBeta = ($Spec.Beta + $navigation + 180.0)" in capture_source
        and "or -1 for an untargeted primary-star pose" in current_builder,
        "capture tooling authors the matched EMPTY untargeted pose",
    )

    view_ray = struct.unpack_from("<f", product["view"], 13 * 4)[0]
    view_dzat_x = struct.unpack_from("<d", product["view"], 8 * 4)[0]
    check(
        product_view[:5] == (2813, 0, -1397, 0, 23)
        and view_dzat_x == expected_dzat[0]
        and product_view[10:13] == (30000, 0, 0)
        and view_ray == ray
        and product_view[14:17] == (0, 0, 1),
        "product view retains the camera, class, ray, and zero-body system",
    )
    product_provenance = provenance.get("product", {})
    check(
        product_provenance.get("private_desktop") is True
        and product_provenance.get("scene") == "stardrifterclass0"
        and product_provenance.get("warmup_seconds") == 30
        and product_provenance.get("fast_mode") is False
        and product_provenance.get("camera", {}).get("dzat_x") == view_dzat_x
        and product_provenance.get("stellar_state") == {
            "class": 0, "ray": ray, "nop": 0, "nob": 0, "ap_reached": 1,
        }
        and product_provenance.get("live_orbital_distance_retained") is False
        and product_provenance.get("clock_matches_native") is False
        and product_provenance.get("clock_independent_contract") is True,
        "product provenance rejects unsupported distance and matched-clock claims",
    )

    check(
        len(native_page) == 64000 and sha256(native_page) == NATIVE_PAGE_SHA256,
        "native BMP yields the pinned top-down 64,000-byte indexed page",
    )
    packed_native_palette = struct.pack("<768I", *native_palette)
    check(
        len(native_palette) == 768
        and sha256(packed_native_palette) == NATIVE_PALETTE_SHA256,
        "native BMP yields the pinned 768-component six-bit RGB palette",
    )
    palette_mismatches = [
        index for index, (native, product) in
        enumerate(zip(native_palette, product_palette)) if native != product
    ]
    expected_palette_mismatches = (
        [201] + list(range(207, 364, 3)) + list(range(581, 768))
    )
    check(
        all(component <= 63 for component in product_palette)
        and product_palette[:201] == native_palette[:201]
        and palette_mismatches == expected_palette_mismatches,
        "product matches the first 201 native palette components",
    )

    flare_offsets = crop_offsets(FLARE_CROP)
    native_crop = bytes(native_page[offset] for offset in flare_offsets)
    product_crop = bytes(product_page[offset] for offset in flare_offsets)
    adapted_crop = bytes(adapted_page[offset] for offset in flare_offsets)
    check(
        len(flare_offsets) == 4256
        and bytes(value & 0xC0 for value in native_crop) ==
            bytes(value & 0xC0 for value in product_crop)
        and sum(left != right for left, right in zip(native_crop, adapted_crop)) == 2
        and bytes(value & 0xC0 for value in native_crop) ==
            bytes(value & 0xC0 for value in adapted_crop)
        and sha256(bytes(value & 0xC0 for value in native_crop)) ==
            "54f421304ba7e5d7a91209dd2f5f42769db4c430e4849ea47b596c5b615a9fda",
        "native, adapted, and product retain every band in the 4,256-pixel flare crop",
    )
    if args.product_directory is None:
        check(
            sum(left != right for left, right in zip(native_crop, product_crop)) == 3395,
            "retained product preserves its provenance-pinned flare-crop comparison",
        )

    native_bright = bright_low_six_contract(native_page, FLARE_CROP, 40)
    product_bright = bright_low_six_contract(product_page, FLARE_CROP, 40)
    comparison = provenance.get("native_product_comparison", {})
    check(
        native_bright == (162, (150, 91, 165, 106))
        and product_bright == (153, (149, 89, 164, 103))
        and comparison.get("native_bright_core") == {
            "low_six_threshold": 40,
            "pixels": 162,
            "bounds": [150, 91, 165, 106],
        }
        and comparison.get("product_bright_core") == {
            "low_six_threshold": 40,
            "pixels": 153,
            "bounds": [149, 89, 164, 103],
        },
        "both frames retain the centred bright class-0 radial-flare core",
    )

    native_product_indices = mismatch_bounds(native_page, product_page)
    native_product_bands = mismatch_bounds(native_page, product_page, bands=True)
    native_adapted_indices = mismatch_bounds(native_page, adapted_page)
    native_adapted_bands = mismatch_bounds(native_page, adapted_page, bands=True)
    comparison = provenance.get("native_product_comparison", {})
    check(
        native_adapted_indices[0] == 6568
        and native_adapted_bands[0] == 2217
        and comparison.get("whole_page_index_mismatches") == 30058
        and comparison.get("whole_page_palette_band_mismatches") == 1200
        and comparison.get("bmp_vs_adapted_index_mismatches") == 6568
        and comparison.get("bmp_vs_adapted_palette_band_mismatches") == 2217,
        "provenance records the historical nonzero whole-page authority limits",
    )
    if args.product_directory is None:
        check(
            native_product_indices == (30058, (10, 2, 313, 195))
            and native_product_bands == (1200, (10, 31, 309, 152)),
            "retained product page preserves its provenance-pinned comparisons",
        )
    authority = provenance.get("authority", {})
    check(
        authority.get("native_snapshot_page_and_palette_retained") is True
        and authority.get("native_post_snapshot_continuity_retained") is True
        and authority.get("native_snapshot_simulation_state_retained") is False
        and authority.get("native_live_orbital_distance_retained") is True
        and authority.get("product_live_orbital_distance_retained") is False
        and authority.get("surface_or_body_claim") is False
        and authority.get("radial_spoke_presence_structurally_graded") is True
        and authority.get("whole_page_same_state_contract") is False,
        "authority excludes surface, unsupported product-distance, and whole-page claims",
    )
    print(
        "INFO complete native/product equality is not graded "
        f"({native_product_indices[0]} indices, {native_product_bands[0]} bands)"
    )
    print(
        "INFO BMP/post-snapshot adapted equality is not graded "
        f"({native_adapted_indices[0]} indices, {native_adapted_bands[0]} bands)"
    )

    if failures:
        print(f"FAIL {len(failures)} class-0 orbital-primary checks")
        return 1
    print("PASS EMPTY class-0 positive orbital-primary flare oracle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
