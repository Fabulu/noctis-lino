"""Grade the retained FUEL TWO class-6 orbital-primary suppression oracle.

FUEL TWO has no generated bodies, so this is an untargeted exterior checkpoint.
The authored distance is inside the ordinary orbital flare interval while the
source class-6 exclusion suppresses radial spokes.  Whole-page equality is not
a same-state contract.
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
ORACLE_ROOT = ROOT / "tests" / "native-oracles" / "orbital-class6-fuel-two"
HARNESS = ROOT / "noctis-harness"
STAR_SOURCE = ROOT / "work" / "vhstar.txt"
GAME = ROOT / "work" / "vhgame.txt"
CATALOGUE = ROOT / "work" / "starmap_exact.txt"
CAPTURE = ROOT / "tools" / "capture_noctis_scenes.ps1"
CURRENT_BUILDER = ROOT / "tests" / "gen" / "recon_w7b" / "mkcurrent.py"

RETAINED = {
    "README.md": (
        5519, "ecdcf071c8f2f4912dfa903057494b55485cfb21740f214a850f209b2b492992",
    ),
    "native-capture.cmd": (
        82, "3de94c13c72b31f0fc2df95e07fa53176b3a72e11f1d4ff1634805408cb19b93",
    ),
    "native-continuity.bin": (
        245, "e0b7bb2124d2da8ec3f4150acbe808c3f2301c0c62e1df78041771fd1c78af02",
    ),
    "native.CURRENT.BIN": (
        385, "fdc3a60686e73dab58ef2c5ea6b8540d0f4b5760fc1ae6fe44a14afc4c666beb",
    ),
    "native.adapted": (
        65540, "7514c719a671b0bfae39e87cd540a32ff5a8e6504e20d9c033a3e67baea7385f",
    ),
    "native.shot.BMP": (
        65078, "c24d13d64ca86f8b6ec975455752b771f87717c3425a47dea2b5e6c95bf6befa",
    ),
    "product-page.bin": (
        64000, "7add23f58bec10341faf4a6ace7b0eacda5aff857cf198b4c6f2045c1f631b26",
    ),
    "product-palette.bin": (
        3072, "bbcd3ab1be0c88fc151b25c541c94ce9f57b862218d7c13efdd8fe55cbdae821",
    ),
    "product-vh.bin": (
        156, "95eac6c93ff64af0585aa447ae6a8aedf10971336b5f83ecf700b535f6d8aac5",
    ),
    "provenance.json": (
        8894, "d66f1e8fcb40c07c367f311a6b99438f2e79d020bd1280ad06103f360d361372",
    ),
}
NATIVE_PAGE_SHA256 = "2f679a47a4f80119720fdccb4663df4bdb71f5cc06284181965a7a22088b931f"
NATIVE_PALETTE_SHA256 = "15c34e0e8a53b47986cc835782e6ef106c3d88cb91027d53d3b819bb3fd9a989"
CORE_CROP = (135, 75, 180, 120)
SEARCH_CROP = (120, 60, 195, 130)
UPPER_STRIP = (0, 64, 320, 127)
SCENE = "stardrifterclass6"
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
        raise AssertionError("unexpected FUEL TWO BMP layout")

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


def page_crop(page: bytes, box: tuple[int, int, int, int]) -> bytes:
    x0, y0, x1, y1 = box
    if not (0 <= x0 < x1 <= 320 and 0 <= y0 < y1 <= 200):
        raise AssertionError(f"invalid crop {box}")
    return b"".join(page[y * 320 + x0:y * 320 + x1] for y in range(y0, y1))


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


def band_bytes(data: bytes) -> bytes:
    return bytes(value & 0xC0 for value in data)


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


def components(page: bytes, box: tuple[int, int, int, int]) -> list[dict[str, object]]:
    x0, y0, x1, y1 = box
    active = {
        (x, y)
        for y in range(y0, y1)
        for x in range(x0, x1)
        if page[y * 320 + x] & 0x3F
    }
    result = []
    while active:
        seed = active.pop()
        todo = [seed]
        component = {seed}
        while todo:
            x, y = todo.pop()
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    point = (x + dx, y + dy)
                    if point in active:
                        active.remove(point)
                        component.add(point)
                        todo.append(point)
        bounds = (
            min(x for x, _y in component), min(y for _x, y in component),
            max(x for x, _y in component), max(y for _x, y in component),
        )
        result.append({
            "pixels": len(component),
            "bounds": bounds,
            "max_low_six": max(page[y * 320 + x] & 0x3F for x, y in component),
            "singleton": next(iter(component)) if len(component) == 1 else None,
        })
    return sorted(result, key=lambda item: (item["pixels"], item["bounds"]))


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
        print(f"FAIL {len(failures)} class-6 orbital-primary checks")
        return 1

    product = {
        "view": retained["product-vh.bin"],
        "palette": retained["product-palette.bin"],
        "page": retained["product-page.bin"],
    }
    if args.product_directory is not None:
        current_product = load_product(args.product_directory.resolve(), check)
        if current_product is None:
            print(f"FAIL {len(failures)} class-6 orbital-primary checks")
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
        check(False, f"retained class-6 oracle decodes safely: {error}")
        return 1

    if str(HARNESS) not in sys.path:
        sys.path.insert(0, str(HARNESS))
    import ns_spec
    system = ns_spec.System(-125712, -174213, -150246)
    check(
        system.cls == 6
        and math.isclose(system.ray, 5.129000186920166, rel_tol=0, abs_tol=1e-15)
        and system.ap_spin == 0
        and system.nop == 0
        and system.nob == 0,
        "tracked model identifies FUEL TWO as a bodyless class-6 system",
    )
    catalogue = CATALOGUE.read_text(encoding="utf-8")
    check(
        "FUEL TWO              np.float64(-3.290487261905376) -125712 -174213 -150246" in catalogue,
        "tracked catalogue retains the FUEL TWO label and coordinates",
    )

    ray = system.ray
    star = (-125712.0, -174213.0, -150246.0)
    expected_dzat = (-125812.20299790107, -174213.0, -150009.9365303321)
    authored_expected = {
        "sync": 0, "anti_rad": 1, "charge": 3,
        "ap_targetted": 1, "ap_reached": 1,
        "ip_targetted": -1, "ip_reached": 0,
        "pwr": 20000, "ap_target_class": 6, "nearstar_class": 6,
        "nearstar_nop": 0, "position": (2813.0, 0.0, -1397.0),
        "angles": (0.0, 23.0, 0.0), "rays": (ray, ray),
        "dzat": expected_dzat, "ap_target": star, "nearstar": star,
        "fcs_status": "STANDBY", "secs": 1345723200.0,
    }
    frozen_expected = dict(authored_expected)
    frozen_expected.update(pwr=19999, secs=1345723229.6666667)
    check(authored == authored_expected, "native input retains the exact untargeted exterior pose")
    check(frozen == frozen_expected, "extracted frozen continuity retains the live class-6 pose")
    check(
        retained["native-capture.cmd"].splitlines() == [
            b"date 24.08.2026", b"time 12:00:00.00", b"cd modules",
            b"autotype -w 30 -p 3 b", b"noctis.exe",
        ],
        "native command retains the matched source clock and silent capture path",
    )

    relative = tuple(star[index] - frozen["dzat"][index] for index in range(3))
    star_distance = math.sqrt(sum(component * component for component in relative))
    source_distance = star_distance + 1.0
    check(
        relative == (100.20299790106947, 0.0, -236.06346966788988)
        and math.isclose(star_distance, 256.45000000000874, rel_tol=0, abs_tol=1e-12)
        and math.isclose(source_distance, 257.45000000000874, rel_tol=0, abs_tol=1e-12)
        and 6 * ray < source_distance < 1000 * ray
        and 8 * ray < source_distance < 100 * ray,
        "native continuity is inside the orbital flare and white-corona intervals",
    )

    candidate = provenance.get("candidate", {})
    flare = provenance.get("orbital_flare_contract", {})
    check(
        provenance.get("schema") == 1
        and provenance.get("case") == "fuel-two-class6-primary"
        and candidate == {
            "star": [-125712, -174213, -150246],
            "star_label": "FUEL TWO",
            "hud_suffix": "S06",
            "star_class": 6,
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
        and flare.get("source_class_eligible") is False
        and flare.get("strictly_inside_distance_interval") is True
        and flare.get("strictly_inside_white_corona_interval") is True
        and flare.get("textured_globe_expected") is False
        and flare.get("radial_spokes_expected") is False,
        "provenance identifies the bodyless class-6 orbital suppression contract",
    )

    star_source = STAR_SOURCE.read_text(encoding="utf-8")
    game = GAME.read_text(encoding="utf-8")
    capture_source = CAPTURE.read_text(encoding="utf-8")
    current_builder = CURRENT_BUILDER.read_text(encoding="utf-8")
    check(
        "? A = 5 -> VHT premask smooth;" in star_source
        and "? A = 6 -> VHT premask smooth; ? A = 10 -> VHT premask smooth;" in star_source
        and "[FI] = 6; => IntToF;" in star_source
        and "A = [VHGbeta]; A + [VHGnavbeta]; A + 180; A % 360;" in game,
        "product retains the source class exclusion and exterior half-turn",
    )
    check(
        "Name='stardrifterclass6'" in capture_source
        and "X=-125712; Y=-174213; Z=-150246" in capture_source
        and "StarDistance=256.45" in capture_source
        and "$exteriorBeta = ($Spec.Beta + $navigation + 180.0)" in capture_source
        and "or -1 for an untargeted primary-star pose" in current_builder,
        "capture tooling authors the matched FUEL TWO untargeted pose",
    )

    view_ray = struct.unpack_from("<f", product["view"], 13 * 4)[0]
    view_dzat_x = struct.unpack_from("<d", product["view"], 8 * 4)[0]
    check(
        product_view[:5] == (2813, 0, -1397, 0, 23)
        and view_dzat_x == expected_dzat[0]
        and product_view[10:13] == (30000, 0, 6)
        and view_ray == ray
        and product_view[14:17] == (0, 0, 1),
        "product view retains the camera, class, ray, and zero-body system",
    )
    product_provenance = provenance.get("product", {})
    check(
        product_provenance.get("private_desktop") is True
        and product_provenance.get("scene") == "stardrifterclass6"
        and product_provenance.get("camera", {}).get("dzat_x") == view_dzat_x
        and product_provenance.get("stellar_state") == {
            "class": 6, "ray": ray, "nop": 0, "nob": 0, "ap_reached": 1,
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
    check(
        all(component <= 63 for component in product_palette)
        and product_palette[:576] == native_palette[:576]
        and palette_mismatches == list(range(581, 768)),
        "product matches all 576 space/stellar/planetary palette components",
    )

    native_core = page_crop(native_page, CORE_CROP)
    adapted_core = page_crop(adapted_page, CORE_CROP)
    product_core = page_crop(product_page, CORE_CROP)
    check(
        len(native_core) == 2025
        and sha256(native_core) == "63957d0f0aa1e3d387850becb6cbb5f582024e6e27f86c45301f7cb28644b30e"
        and adapted_core == native_core,
        "all 2,025 native core indices are snapshot-stable",
    )
    check(
        sha256(product_core) == "8214075a48ed10c37a2cc9a15c31cc1b0464d9ac478eec391a664b74a98d0a47"
        and band_bytes(product_core) == band_bytes(native_core)
        and sha256(band_bytes(native_core)) ==
            "8ee7fcf9ba6a42fd1a0964ee250cdce9944bd486d98f5bcc2beb2186498a0e50",
        "product reproduces every native palette band in the stable core",
    )

    native_strip = page_crop(native_page, UPPER_STRIP)
    product_strip = page_crop(product_page, UPPER_STRIP)
    check(
        len(native_strip) == 20160
        and sum(left != right for left, right in zip(native_strip, product_strip)) == 291
        and band_bytes(native_strip) == band_bytes(product_strip)
        and sha256(band_bytes(native_strip)) ==
            "fca8a1a99b406d674f62aa0e1458e362eaea33168f73a0b1352df556b331e82b",
        "all 20,160 upper-strip indices retain their native palette bands",
    )

    native_components = components(native_page, SEARCH_CROP)
    product_components = components(product_page, SEARCH_CROP)
    singleton_points = [(156, 66), (175, 67), (180, 91), (184, 115)]
    check(
        [item["singleton"] for item in native_components[:4]] == singleton_points
        and [item["singleton"] for item in product_components[:4]] == singleton_points
        and [item["max_low_six"] for item in native_components[:4]] == [3, 13, 22, 5]
        and [item["max_low_six"] for item in product_components[:4]] == [3, 13, 22, 5],
        "native and product retain the same four isolated background stars",
    )
    native_corona = native_components[-1]
    product_corona = product_components[-1]
    check(
        len(native_components) == 5
        and native_corona == {
            "pixels": 218, "bounds": (148, 92, 166, 106),
            "max_low_six": 59, "singleton": None,
        }
        and len(product_components) == 5
        and product_corona == {
            "pixels": 206, "bounds": (148, 89, 165, 103),
            "max_low_six": 56, "singleton": None,
        },
        "both frames retain one compact corona and no extended radial component",
    )

    native_product_indices = mismatch_bounds(native_page, product_page)
    native_product_bands = mismatch_bounds(native_page, product_page, bands=True)
    native_adapted_indices = mismatch_bounds(native_page, adapted_page)
    native_adapted_bands = mismatch_bounds(native_page, adapted_page, bands=True)
    comparison = provenance.get("native_product_comparison", {})
    check(
        native_adapted_indices[0] == 6648
        and native_adapted_bands[0] == 2217
        and comparison.get("whole_page_index_mismatches") == 16166
        and comparison.get("whole_page_palette_band_mismatches") == 1200
        and comparison.get("bmp_vs_adapted_index_mismatches") == 6648
        and comparison.get("bmp_vs_adapted_palette_band_mismatches") == 2217,
        "provenance records the historical nonzero whole-page authority limits",
    )
    if args.product_directory is None:
        check(
            native_product_indices == (16166, (10, 2, 313, 195))
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
        and authority.get("radial_spoke_absence_structurally_graded") is True
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
        print(f"FAIL {len(failures)} class-6 orbital-primary checks")
        return 1
    print("PASS FUEL TWO class-6 orbital-primary suppression oracle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
