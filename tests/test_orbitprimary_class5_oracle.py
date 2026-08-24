"""Grade the retained ASKEW 184 class-5 orbital-primary suppression oracle.

ASKEW 184 has no generated bodies, so this is an untargeted exterior checkpoint.
The authored distance is inside the ordinary orbital flare interval while the
source class-5 exclusion suppresses radial spokes.  Whole-page equality is not
a same-state contract.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import struct
import sys


ROOT = Path(__file__).resolve().parents[1]
ORACLE_ROOT = ROOT / "tests" / "native-oracles" / "orbital-class5-askew-184"
HARNESS = ROOT / "noctis-harness"
STAR_SOURCE = ROOT / "work" / "vhstar.txt"
GAME = ROOT / "work" / "vhgame.txt"
CATALOGUE = ROOT / "work" / "starmap_exact.txt"
CAPTURE = ROOT / "tools" / "capture_noctis_scenes.ps1"
CURRENT_BUILDER = ROOT / "tests" / "gen" / "recon_w7b" / "mkcurrent.py"

RETAINED = {
    "README.md": (
        5686, "9b42a1b577038a7ef72764d7a37e3ed41cb27e94a123f2d0e293819b211a6d95",
    ),
    "native-capture.cmd": (
        82, "3de94c13c72b31f0fc2df95e07fa53176b3a72e11f1d4ff1634805408cb19b93",
    ),
    "native-continuity.bin": (
        245, "b300a5e588dbbab4b1a4e6ebcea705a2c589d72efd93f83eb6b9f149ede71ac3",
    ),
    "native.CURRENT.BIN": (
        385, "c8ce191a8ae44e50c92372aa4456591827a46525550f0bf82b273ea17561cc26",
    ),
    "native.adapted": (
        65540, "a0d6c236583be4f477482092a38817a55eba97e3b2d9cb431869d075a6a330c4",
    ),
    "native.shot.BMP": (
        65078, "8fc168d4f0d0578ce13c4ce7ab9d2662dde00f8f8747b167ba6669f33c26f9d3",
    ),
    "product-page.bin": (
        64000, "a362a0e3660a533c5a804686ce4f2a3d9972b698c0abfeff408bfc06661cfd0a",
    ),
    "product-palette.bin": (
        3072, "476fc4a6453fcde7eb6e7b907284905fb8b136a9326d517ede47e09d4cae5de1",
    ),
    "product-vh.bin": (
        156, "e7b1d0dd9591a7651554832d09df66c8e0c0eabbcd2db8ea7421c299d3553938",
    ),
    "provenance.json": (
        9251, "08dca519891aa7eaa744f612fd4d21467a15abfd274edc16eb821a4c1954677c",
    ),
}
NATIVE_PAGE_SHA256 = "f3fedbd6c2ab294b2720b1c58569b7e98daf7ffed4fe794a7716fc71735f4578"
NATIVE_PALETTE_SHA256 = "a055ef67edf7b3482ecdeefbacdb7a2615a75be5a7f871b5b56867ad0a761f6d"
CORE_CROP = (135, 75, 180, 120)
SEARCH_CROP = (120, 60, 195, 130)
UPPER_STRIP = (0, 64, 320, 127)

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
        raise AssertionError("unexpected ASKEW 184 BMP layout")

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
        print(f"FAIL {len(failures)} class-5 orbital-primary checks")
        return 1

    try:
        provenance = json.loads(retained["provenance.json"])
        native_page, native_palette = decode_bmp(retained["native.shot.BMP"])
        authored = decode_continuity(retained["native.CURRENT.BIN"])
        frozen = decode_continuity(retained["native-continuity.bin"])
        adapted_page = retained["native.adapted"][:64000]
        product_view = struct.unpack("<39i", retained["product-vh.bin"])
        product_palette = struct.unpack("<768I", retained["product-palette.bin"])
        product_page = retained["product-page.bin"]
    except (AssertionError, json.JSONDecodeError, struct.error, UnicodeDecodeError) as error:
        check(False, f"retained class-5 oracle decodes safely: {error}")
        return 1

    if str(HARNESS) not in sys.path:
        sys.path.insert(0, str(HARNESS))
    import ns_spec
    system = ns_spec.System(3438192, -1233198, 1856484)
    check(
        system.cls == 5
        and math.isclose(system.ray, 1.4919999837875366, rel_tol=0, abs_tol=1e-15)
        and system.ap_spin == 0
        and system.nop == 0
        and system.nob == 0,
        "tracked model identifies ASKEW 184 as a bodyless class-5 system",
    )
    catalogue = CATALOGUE.read_text(encoding="utf-8")
    check(
        "ASKEW 184             np.float64(-7871.439246522736) 3438192 -1233198 1856484" in catalogue,
        "tracked catalogue retains the ASKEW 184 label and coordinates",
    )

    ray = system.ray
    star = (3438192.0, -1233198.0, 1856484.0)
    expected_dzat = (3438162.8514581313, -1233198.0, 1856552.6696613214)
    authored_expected = {
        "sync": 0, "anti_rad": 1, "charge": 3,
        "ap_targetted": 1, "ap_reached": 1,
        "ip_targetted": -1, "ip_reached": 0,
        "pwr": 20000, "ap_target_class": 5, "nearstar_class": 5,
        "nearstar_nop": 0, "position": (2813.0, 0.0, -1397.0),
        "angles": (0.0, 23.0, 0.0), "rays": (ray, ray),
        "dzat": expected_dzat, "ap_target": star, "nearstar": star,
        "fcs_status": "STANDBY", "secs": 1345723200.0,
    }
    frozen_expected = dict(authored_expected)
    frozen_expected.update(pwr=19999, secs=1345723229.368421)
    check(authored == authored_expected, "native input retains the exact untargeted exterior pose")
    check(frozen == frozen_expected, "extracted frozen continuity retains the live class-5 pose")
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
        relative == (29.148541868664324, 0.0, -68.66966132144444)
        and math.isclose(star_distance, 74.59999918948498, rel_tol=0, abs_tol=1e-12)
        and math.isclose(source_distance, 75.59999918948498, rel_tol=0, abs_tol=1e-12)
        and 6 * ray < source_distance < 1000 * ray
        and 8 * ray < source_distance < 100 * ray,
        "native continuity is inside the orbital flare and white-corona intervals",
    )

    candidate = provenance.get("candidate", {})
    flare = provenance.get("orbital_flare_contract", {})
    check(
        provenance.get("schema") == 1
        and provenance.get("case") == "askew-184-class5-primary"
        and candidate == {
            "star": [3438192, -1233198, 1856484],
            "star_label": "ASKEW 184",
            "hud_suffix": "S05",
            "star_class": 5,
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
        "provenance identifies the bodyless class-5 orbital suppression contract",
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
        "Name='stardrifterclass5'" in capture_source
        and "X=3438192; Y=-1233198; Z=1856484" in capture_source
        and "StarDistance=74.59999918937683" in capture_source
        and "$exteriorBeta = ($Spec.Beta + $navigation + 180.0)" in capture_source
        and "or -1 for an untargeted primary-star pose" in current_builder,
        "capture tooling authors the matched ASKEW 184 untargeted pose",
    )

    view_ray = struct.unpack_from("<f", retained["product-vh.bin"], 13 * 4)[0]
    view_dzat_x = struct.unpack_from("<d", retained["product-vh.bin"], 8 * 4)[0]
    check(
        product_view[:5] == (2813, 0, -1397, 0, 23)
        and view_dzat_x == expected_dzat[0]
        and product_view[10:13] == (30000, 0, 5)
        and view_ray == ray
        and product_view[14:17] == (0, 0, 1),
        "product view retains the camera, class, ray, and zero-body system",
    )
    product_provenance = provenance.get("product", {})
    check(
        product_provenance.get("private_desktop") is True
        and product_provenance.get("scene") == "stardrifterclass5"
        and product_provenance.get("warmup_seconds") == 30
        and product_provenance.get("fast_mode") is False
        and product_provenance.get("camera", {}).get("dzat_x") == view_dzat_x
        and product_provenance.get("stellar_state") == {
            "class": 5, "ray": ray, "nop": 0, "nob": 0, "ap_reached": 1,
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
        and sha256(native_core) == "586ce39e9499ee35792ab39a12f4a74020311964c9a1c81339f75f6a721203c5"
        and adapted_core == native_core,
        "all 2,025 native core indices are snapshot-stable",
    )
    check(
        sha256(product_core) == "daafbf5ca912728adc76dae5ad38d70b90e039fbaa1b13552f85887386748a09"
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
    singleton_points = [(126, 86), (131, 91), (155, 70), (185, 105), (187, 62)]
    check(
        [item["singleton"] for item in native_components[:5]] == singleton_points
        and [item["singleton"] for item in product_components[:5]] == singleton_points
        and [item["max_low_six"] for item in native_components[:5]] == [40, 8, 24, 5, 3]
        and [item["max_low_six"] for item in product_components[:5]] == [40, 8, 24, 5, 3],
        "native and product retain the same five isolated background stars",
    )
    native_corona = native_components[-1]
    product_corona = product_components[-1]
    check(
        len(native_components) == 6
        and native_corona == {
            "pixels": 218, "bounds": (148, 93, 166, 107),
            "max_low_six": 59, "singleton": None,
        }
        and len(product_components) == 6
        and product_corona == {
            "pixels": 206, "bounds": (148, 90, 165, 104),
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
        native_product_indices == (16265, (10, 2, 313, 196))
        and native_product_bands == (1200, (10, 31, 309, 152))
        and native_adapted_indices[0] == 6743
        and native_adapted_bands[0] == 2217
        and comparison.get("whole_page_index_mismatches") == 16265
        and comparison.get("whole_page_palette_band_mismatches") == 1200
        and comparison.get("bmp_vs_adapted_index_mismatches") == 6743
        and comparison.get("bmp_vs_adapted_palette_band_mismatches") == 2217,
        "provenance records the nonzero whole-page authority limits",
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
        print(f"FAIL {len(failures)} class-5 orbital-primary checks")
        return 1
    print("PASS ASKEW 184 class-5 orbital-primary suppression oracle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
