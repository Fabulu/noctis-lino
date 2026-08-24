"""Grade the retained POE class-11 phase-positive orbital-primary oracle.

POE has no generated bodies. Fresh native and product processes hold it fifty
stellar radii away, above the textured-globe threshold, so their class-11 phase
starts and remains at zero while the source's phase<90 radial flare is admitted.
Whole-page equality and a directly retained phase scalar are not claimed.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import struct
import sys


ROOT = Path(__file__).resolve().parents[1]
ORACLE_ROOT = ROOT / "tests" / "native-oracles" / "orbital-class11-poe"
HARNESS = ROOT / "noctis-harness"
STAR_SOURCE = ROOT / "work" / "vhstar.txt"
GAME = ROOT / "work" / "vhgame.txt"
CATALOGUE = ROOT / "work" / "starmap_exact.txt"
CAPTURE = ROOT / "tools" / "capture_noctis_scenes.ps1"
CURRENT_BUILDER = ROOT / "tests" / "gen" / "recon_w7b" / "mkcurrent.py"
HISTORICAL = ROOT / "tests" / "gen" / "recon_nivplus_sheetbot" / "source"

RETAINED = {
    "README.md": (
        5070, "fb6ad45b8f95fd8e7d58e1a82ad60e59628dd90ab295aef87c1f80f93878ade4",
    ),
    "native-capture.cmd": (
        82, "3de94c13c72b31f0fc2df95e07fa53176b3a72e11f1d4ff1634805408cb19b93",
    ),
    "native-continuity.bin": (
        245, "d3474dcfe7ce0bb78d39fe6e6f02ce3c999eac14789e849c6a9486110c688063",
    ),
    "native.CURRENT.BIN": (
        385, "86386975eb4dc7813e4541ff87dbf67925b13073c5eeb6e12f4c6da1c534e1e4",
    ),
    "native.adapted": (
        65540, "58f54ade34d1396d0fa6bc76253196a2a53f93658c7f5dbf0761cff437a7b513",
    ),
    "native.shot.BMP": (
        65078, "15768fbdb7d1cffd7aa432a4d3a9f8086f15fd09fabf0c044e2a02ec39b33e21",
    ),
    "product-page.bin": (
        64000, "1f3df10679ec282d319826731488147eecb415e14181b7ea2fac3729f2a0ace7",
    ),
    "product-palette.bin": (
        3072, "5b99378c6c77603fd9dc07b22e3a3db05430a68a3d00e4d8adb802edff434541",
    ),
    "product-vh.bin": (
        156, "ad3cc11594159c58c815616af39bca29069ee0aedd31f5046701ce7f4729839c",
    ),
    "provenance.json": (
        10388, "9254e0fa2735ced685ee37237c813cd68cb3a1c3f97b5e5367d59fc1c0fef2ee",
    ),
}
NATIVE_PAGE_SHA256 = "9761c86f8a18b2aa9bb88967debd38ea843cfe3040ec55b518a8447f042e7bbb"
NATIVE_PALETTE_SHA256 = "a0fb50e837de43ee2a7b15975b8124036d3aeb25527ea7d45dc31ac399f3a7d4"
FLARE_CROP = (120, 60, 195, 115)

OFF = {
    "sync": 0, "anti_rad": 1, "charge": 6, "ap_targetted": 9,
    "ip_targetted": 11, "ip_reached": 13, "pwr": 27,
    "ap_target_class": 31, "nearstar_class": 35, "nearstar_nop": 37,
    "pos_x": 39, "pos_y": 43, "pos_z": 47, "user_alfa": 51,
    "user_beta": 55, "navigation_beta": 59, "ap_target_ray": 63,
    "nearstar_ray": 67, "dzat_x": 71, "dzat_y": 79, "dzat_z": 87,
    "ap_target_x": 95, "ap_target_y": 103, "ap_target_z": 111,
    "nearstar_x": 119, "nearstar_y": 127, "nearstar_z": 135,
    "fcs_status": 183, "ap_reached": 232, "secs": 235,
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
        raise AssertionError("unexpected POE BMP layout")

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

    def u8(name: str) -> int:
        return data[OFF[name]]

    def i8(name: str) -> int:
        return struct.unpack_from("<b", data, OFF[name])[0]

    def i16(name: str) -> int:
        return struct.unpack_from("<h", data, OFF[name])[0]

    def f32(name: str) -> float:
        return struct.unpack_from("<f", data, OFF[name])[0]

    def f64(name: str) -> float:
        return struct.unpack_from("<d", data, OFF[name])[0]

    return {
        "sync": u8("sync"), "anti_rad": u8("anti_rad"),
        "charge": u8("charge"), "ap_targetted": u8("ap_targetted"),
        "ap_reached": u8("ap_reached"), "ip_targetted": i8("ip_targetted"),
        "ip_reached": u8("ip_reached"), "pwr": i16("pwr"),
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
        "fcs_status": data[183:194].split(b"\0")[0].decode(),
        "secs": f64("secs"),
    }


def crop_offsets(box: tuple[int, int, int, int]) -> tuple[int, ...]:
    x0, y0, x1, y1 = box
    return tuple(y * 320 + x for y in range(y0, y1 + 1) for x in range(x0, x1 + 1))


def bright_contract(page: bytes) -> dict[str, object]:
    x0, y0, x1, y1 = FLARE_CROP
    points = {
        (x, y)
        for y in range(y0, y1 + 1)
        for x in range(x0, x1 + 1)
        if (page[y * 320 + x] & 0x3F) >= 40
    }
    remaining = set(points)
    components: list[set[tuple[int, int]]] = []
    while remaining:
        seed = min(remaining)
        component = {seed}
        pending = [seed]
        remaining.remove(seed)
        while pending:
            x, y = pending.pop()
            for next_y in range(y - 1, y + 2):
                for next_x in range(x - 1, x + 2):
                    point = (next_x, next_y)
                    if point in remaining:
                        remaining.remove(point)
                        component.add(point)
                        pending.append(point)
        components.append(component)
    components.sort(key=lambda component: (-len(component), min(component)))
    core = components[0]
    return {
        "low_six_threshold": 40,
        "total_pixels": len(points),
        "largest_eight_connected_component_pixels": len(core),
        "largest_component_bounds": [
            min(x for x, _y in core), min(y for _x, y in core),
            max(x for x, _y in core), max(y for _x, y in core),
        ],
        "singleton_satellites": sorted(
            [list(next(iter(component))) for component in components if len(component) == 1]
        ),
    }


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
        print(f"FAIL {len(failures)} class-11 orbital-primary checks")
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
        check(False, f"retained class-11 oracle decodes safely: {error}")
        return 1

    if str(HARNESS) not in sys.path:
        sys.path.insert(0, str(HARNESS))
    import ns_spec
    system = ns_spec.System(3131408, -4623621, 1755683)
    ray = 0.2590000033378601
    check(
        system.cls == 11
        and system.ray == ray
        and system.ap_spin == 21
        and system.nop == 0
        and system.nob == 0,
        "tracked model identifies POE as a bodyless spinning class-11 system",
    )
    catalogue = CATALOGUE.read_text(encoding="utf-8")
    check(
        "POE                   np.float64(-25419.557625693295) 3131408 -4623621 1755683 1" in catalogue,
        "tracked catalogue retains the POE label, identity, and coordinates",
    )

    star = (3131408.0, -4623621.0, 1755683.0)
    expected_dzat = (3131402.940031821, -4623621.0, 1755694.920538006)
    authored_expected = {
        "sync": 0, "anti_rad": 1, "charge": 3,
        "ap_targetted": 1, "ap_reached": 1,
        "ip_targetted": -1, "ip_reached": 0,
        "pwr": 20000, "ap_target_class": 11, "nearstar_class": 11,
        "nearstar_nop": 0, "position": (2813.0, 0.0, -1397.0),
        "angles": (0.0, 23.0, 0.0), "rays": (ray, ray),
        "dzat": expected_dzat, "ap_target": star, "nearstar": star,
        "fcs_status": "STANDBY", "secs": 1345723200.0,
    }
    frozen_expected = dict(authored_expected)
    frozen_expected.update(pwr=19999, secs=1345723228.1875)
    check(authored == authored_expected, "native input retains the exact POE exterior pose")
    check(frozen == frozen_expected, "frozen continuity retains the live POE pose")
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
        relative == (5.059968179091811, 0.0, -11.920538005884737)
        and math.isclose(star_distance, 12.950000166917533, rel_tol=0, abs_tol=1e-15)
        and math.isclose(source_distance, 13.950000166917533, rel_tol=0, abs_tol=1e-15)
        and 6 * ray < source_distance < 1000 * ray
        and 8 * ray < source_distance < 100 * ray,
        "native continuity is inside the flare and no-textured-globe intervals",
    )

    flare = provenance.get("orbital_flare_contract", {})
    phase = provenance.get("class11_phase_contract", {})
    authority = provenance.get("authority", {})
    check(
        provenance.get("schema") == 1
        and provenance.get("case") == "poe-class11-phase-positive-primary"
        and provenance.get("candidate", {}).get("star_class") == 11
        and provenance.get("candidate", {}).get("ap_spin") == 21
        and provenance.get("candidate", {}).get("generated_system") == {
            "nop": 0, "nob": 0,
            "has_authentic_body": False, "has_landable_surface": False,
        }
        and flare.get("strictly_inside_distance_interval") is True
        and flare.get("strictly_inside_white_corona_interval") is True
        and flare.get("textured_globe_expected") is False
        and flare.get("radial_spokes_expected") is True,
        "provenance identifies the bodyless positive class-11 geometry",
    )
    check(
        phase.get("historical_initial_gl_start") == 0
        and phase.get("product_initial_phase") == 0
        and phase.get("star_spin") == 21
        and phase.get("phase_advance_requires_textured_globe") is True
        and phase.get("source_l_dsd_above_textured_globe_threshold") is True
        and phase.get("fresh_native_process") is True
        and phase.get("fresh_product_process") is True
        and phase.get("phase_advance_path_entered") is False
        and phase.get("phase_at_render") == 0
        and phase.get("positive_branch_admitted") is True
        and phase.get("direct_phase_scalar_retained") is False,
        "provenance retains the source-grounded phase-zero admission chain",
    )

    star_source = STAR_SOURCE.read_text(encoding="utf-8")
    game = GAME.read_text(encoding="utf-8")
    historical_main = (HISTORICAL / "NOCTIS.CPP").read_text(encoding="latin-1")
    historical_globals = (HISTORICAL / "NOCTIS-0.CPP").read_text(encoding="latin-1")
    check(
        "unsigned      gl_start \t     = 0;" in historical_globals
        and "if (nearstar_class!=11||gl_start<90)" in historical_main
        and "if (l_dsd < 8 * nearstar_ray)" in historical_main
        and "gl_start += nearstar_spin;" in historical_main
        and historical_main.index("if (nearstar_class!=11||gl_start<90)")
            < historical_main.index("if (l_dsd < 8 * nearstar_ray)")
            < historical_main.index("gl_start += nearstar_spin;"),
        "historical source starts at zero and advances only in the close globe branch",
    )
    check(
        "[VHTphase] = 0; [VHTprevphase] = 0; [VHTrenderphase] = 0; [VHTspin] = 0;" in star_source
        and "A = [VHTclass]; ? A = 11 -> VHT spin class11;" in star_source
        and "? A != 11 -> VHT premask flare range;" in star_source
        and "A = [VHTphase]; A % 360; ? A >= 90 -> VHT premask smooth;" in star_source
        and star_source.count("=> VHT phase advance;") == 1
        and star_source.index("A = [VHTglobeok]; ? A = 0 -> VHT render far;")
            < star_source.index("=> VHT phase advance;")
        and "A = [VHGbeta]; A + [VHGnavbeta]; A + 180; A % 360;" in game,
        "product source mirrors the class-11 gate and globe-only phase advance",
    )

    capture_source = CAPTURE.read_text(encoding="utf-8")
    current_builder = CURRENT_BUILDER.read_text(encoding="utf-8")
    check(
        "Name='stardrifterclass11'" in capture_source
        and "X=3131408; Y=-4623621; Z=1755683" in capture_source
        and "StarDistance=12.950000166893005" in capture_source
        and "$exteriorBeta = ($Spec.Beta + $navigation + 180.0)" in capture_source
        and "or -1 for an untargeted primary-star pose" in current_builder,
        "capture tooling authors the matched phase-positive POE pose",
    )

    view_ray = struct.unpack_from("<f", retained["product-vh.bin"], 13 * 4)[0]
    view_dzat_x = struct.unpack_from("<d", retained["product-vh.bin"], 8 * 4)[0]
    check(
        product_view[:5] == (2813, 0, -1397, 0, 23)
        and view_dzat_x == expected_dzat[0]
        and product_view[10:13] == (30000, 0, 11)
        and view_ray == ray
        and product_view[14:17] == (0, 0, 1),
        "product view retains the camera, class, ray, and zero-body system",
    )
    product_provenance = provenance.get("product", {})
    check(
        product_provenance.get("private_desktop") is True
        and product_provenance.get("scene") == "stardrifterclass11"
        and product_provenance.get("warmup_seconds") == 30
        and product_provenance.get("fast_mode") is False
        and product_provenance.get("camera", {}).get("dzat_x") == view_dzat_x
        and product_provenance.get("stellar_state") == {
            "class": 11, "ray": ray, "nop": 0, "nob": 0, "ap_reached": 1,
        }
        and product_provenance.get("live_orbital_distance_retained") is False
        and product_provenance.get("clock_matches_native") is False
        and product_provenance.get("clock_independent_contract") is True,
        "product provenance rejects unsupported distance and matched-clock claims",
    )

    check(
        len(native_page) == 64000 and sha256(native_page) == NATIVE_PAGE_SHA256,
        "native BMP yields the pinned top-down indexed page",
    )
    packed_native_palette = struct.pack("<768I", *native_palette)
    check(
        len(native_palette) == 768
        and sha256(packed_native_palette) == NATIVE_PALETTE_SHA256,
        "native BMP yields the pinned six-bit RGB palette",
    )
    palette_mismatches = [
        index for index, (native, product) in
        enumerate(zip(native_palette, product_palette)) if native != product
    ]
    check(
        all(component <= 63 for component in product_palette)
        and product_palette[:203] == native_palette[:203]
        and len(palette_mismatches) == 247
        and (min(palette_mismatches), max(palette_mismatches)) == (203, 767),
        "product matches the first 203 native palette components",
    )

    flare_offsets = crop_offsets(FLARE_CROP)
    native_crop = bytes(native_page[offset] for offset in flare_offsets)
    product_crop = bytes(product_page[offset] for offset in flare_offsets)
    adapted_crop = bytes(adapted_page[offset] for offset in flare_offsets)
    check(
        len(flare_offsets) == 4256
        and sum(left != right for left, right in zip(native_crop, product_crop)) == 3406
        and bytes(value & 0xC0 for value in native_crop)
            == bytes(value & 0xC0 for value in product_crop)
        and sum(left != right for left, right in zip(native_crop, adapted_crop)) == 2
        and bytes(value & 0xC0 for value in native_crop)
            == bytes(value & 0xC0 for value in adapted_crop)
        and sha256(bytes(value & 0xC0 for value in native_crop))
            == "54f421304ba7e5d7a91209dd2f5f42769db4c430e4849ea47b596c5b615a9fda",
        "native, adapted, and product retain every band in the flare crop",
    )

    native_bright = bright_contract(native_page)
    product_bright = bright_contract(product_page)
    comparison = provenance.get("native_product_comparison", {})
    check(
        native_bright == {
            "low_six_threshold": 40, "total_pixels": 161,
            "largest_eight_connected_component_pixels": 160,
            "largest_component_bounds": [151, 91, 165, 106],
            "singleton_satellites": [[140, 104]],
        }
        and product_bright == {
            "low_six_threshold": 40, "total_pixels": 158,
            "largest_eight_connected_component_pixels": 157,
            "largest_component_bounds": [150, 89, 164, 103],
            "singleton_satellites": [[140, 104]],
        }
        and comparison.get("native_bright") == native_bright
        and comparison.get("product_bright") == product_bright,
        "both frames retain the centred phase-positive class-11 radial flare",
    )

    native_product_indices = mismatch_bounds(native_page, product_page)
    native_product_bands = mismatch_bounds(native_page, product_page, bands=True)
    native_adapted_indices = mismatch_bounds(native_page, adapted_page)
    native_adapted_bands = mismatch_bounds(native_page, adapted_page, bands=True)
    check(
        native_product_indices == (30632, (10, 2, 313, 196))
        and native_product_bands == (1200, (10, 31, 309, 152))
        and native_adapted_indices == (18421, (0, 9, 319, 190))
        and native_adapted_bands == (11690, (5, 10, 311, 185))
        and comparison.get("whole_page_index_mismatches") == 30632
        and comparison.get("whole_page_palette_band_mismatches") == 1200
        and comparison.get("bmp_vs_adapted_index_mismatches") == 18421
        and comparison.get("bmp_vs_adapted_palette_band_mismatches") == 11690,
        "provenance records the nonzero whole-page authority limits",
    )
    check(
        authority.get("native_snapshot_page_and_palette_retained") is True
        and authority.get("native_post_snapshot_continuity_retained") is True
        and authority.get("native_snapshot_simulation_state_retained") is False
        and authority.get("native_live_orbital_distance_retained") is True
        and authority.get("product_live_orbital_distance_retained") is False
        and authority.get("surface_or_body_claim") is False
        and authority.get("phase_scalar_directly_retained") is False
        and authority.get("phase_positive_branch_source_grounded") is True
        and authority.get("radial_spoke_presence_structurally_graded") is True
        and authority.get("whole_page_same_state_contract") is False
        and authority.get("matched_clock_hud_contract") is False,
        "authority excludes unsupported phase, body, clock, and whole-page claims",
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
        print(f"FAIL {len(failures)} class-11 orbital-primary checks")
        return 1
    print("PASS POE class-11 phase-positive orbital-primary flare oracle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
