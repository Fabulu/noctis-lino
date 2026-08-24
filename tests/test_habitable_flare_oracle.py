"""Grade the atmospheric type-3 primary lens-flare rain-1.2 boundary.

The default mode is non-GUI.  It authenticates two same-command NIV+ indexed
BMPs and landed states, independently reconstructs their one-variable Borland
weather bracket, and protects the inclusive binary32 flare gate.  Optional
product directories add exported-state hashes and exact native/product source
crops::

    python tests/test_habitable_flare_oracle.py \
        --control-product-directory build/renderer-hab-flare-control50 \
        --threshold-product-directory build/renderer-hab-flare-threshold51
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import sys

from test_frozen_sunrise_oracle import (
    band_mismatch_count,
    decode_bmp,
    load_mkcurrent,
    mismatch_count,
    page_crop,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "gen" / "recon_w7b" / "out"
MAP_OUT = ROOT / "tests" / "gen" / "recon_w7a" / "out"
PROVENANCE = OUT / "hab_flare_primary_gate_8020_native.provenance.json"
GROUND = ROOT / "work" / "vhground.txt"
STAR = (1463568, -4728350, -437812)
LATITUDE = 34
SOURCE_CROP = (145, 77, 180, 112)

MAPS = {
    "p_background": (
        MAP_OUT / "lane_b03_t3.p_background",
        "17769375e8e5e46f0ec4f4ff762386e4a01c130879de7322cd6abb2cfdeab9c1",
    ),
    "objectschart": (
        MAP_OUT / "lane_b03_t3.objectschart",
        "b5b6e995dd6479326491880b6ecfda0f8a7e9757bda110e8a511b24923099aa3",
    ),
}

NATIVE = {
    "control50": {
        "longitude": 50,
        "bmp": OUT / "hab_flare_control50_8020_native.shot.BMP",
        "surface": OUT / "hab_flare_control50_8020_native.SURFACE.BIN",
        "bmp_sha256": "25da4331d409d61abee4ff90d697e120ebbbaa14eeec55e42bda30dddb124f58",
        "surface_sha256": "72fd1d99323a68e8b9a9e7ce258b5e6b8e8c49b6af9303f3653ffdff3fa28fea",
        "page_sha256": "d7b530e55eb5bc100b8acd5b567e59ff4b00aee85bfcee9755a2849daaf5d311",
        "palette_sha256": "164bc464ab20ccbe0499f0625ab5c302564b91ec25fb80b878ed02953964f124",
        "surface_state": (50, 34, 8, 8, 0, 0, 1598248.0, 1.0, 2251369.0, -44.0, 33.0),
        "random100": 96,
        "random4": 3,
        "divisor": 4,
        "rain": 0.9375,
        "source_crop_sha256": "10355bcc2d40f2ea340f4fee49ad9f30aa83c45373756ea5105eb0229b76116e",
    },
    "threshold51": {
        "longitude": 51,
        "bmp": OUT / "hab_flare_threshold51_8020_native.shot.BMP",
        "surface": OUT / "hab_flare_threshold51_8020_native.SURFACE.BIN",
        "bmp_sha256": "3f084b52024c8ab79487df6516966792bddce04dafbf372a47620a07d82458d5",
        "surface_sha256": "c270e67e6e4184ebf5400c963d0665a02ed05a42698abe09c0f5ea1982387c3e",
        "page_sha256": "0aed6fa483eebfcf90b8946e910d00cf971905d6e77c7f764c2851177db93272",
        "palette_sha256": "cfb6e8e8304b80c5ebd9ee8fb4b23d63c9820c1e27bf0eae2e0fdfb7be92d4cc",
        "surface_state": (51, 34, 8, 8, 0, 0, 1598248.0, 1.0, 2251369.0, -44.0, 33.0),
        "random100": 32,
        "random4": 2,
        "divisor": 3,
        "rain": 1.25,
        "source_crop_sha256": "ca9806b3e72ee72cdf96f2cd03585a4665469828ac5e9ba6c837ad931e9da970",
    },
}

PRODUCT_HASHES = {
    "control50": {
        "habitable-game-local-out.bin": "5168c839d29f992d3aac93ec165319904df76ed166c06b7d150f35727b49064a",
        "habitable-game-p-background-out.bin": "882534216d182ded8d042f55d07fe94fba3fd42a43d957d2d442391047847144",
        "habitable-game-p-surfacemap-out.bin": "68f60a24f8ab3b2b5e3c75cfe6535d1b9492a7afd817149b255685e117d9d8d1",
        "habitable-game-page-out.bin": "02a4065644888ea051289f91a813f98cbbdd4eb5bf9b01c7a1af831eed02372b",
        "habitable-game-palette-out.bin": "c289ce6f7df957ad007300cbf18610faf84a3706b002652f4c268ad6e641d1c9",
        "habitable-game-render-state-out.bin": "969a71e42b159c26a7a12145a7b996e7daa70f0f7dc1f6b09b65dc36eff1de65",
        "habitable-game-s-background-out.bin": "79bd1c30083c26d93f96d19b21b617d8d0f212a36c70fb4a4d0ad0c99465170d",
        "habitable-game-sun-out.bin": "1f0712a1a0a42714d9f5e1f5105e68a4401b748af5c30e81088ec9e1cba4212f",
        "habitable-game-vh-out.bin": "70b332b377eab8e18d2bae163f34f7d1e47e4d5f4c291277594690a0e889b1b8",
    },
    "threshold51": {
        "habitable-game-local-out.bin": "69c2be8e8c110ad0d6ec45a9b4b9776607a218fa08b15ad9541ca9ba6327ada0",
        "habitable-game-p-background-out.bin": "a8337e09747d70774f546cfc18a45cc2a2df6bda3514d3dd4291960033900f24",
        "habitable-game-p-surfacemap-out.bin": "4a6fb0e63a541c5e6c94e70168caa331f88f5bd903b7fa74c26b06bb5cfba296",
        "habitable-game-page-out.bin": "cd28dd26685facb8d9d72dd4cc713a6ab3e0272f9ae34804346c642f1450f15c",
        "habitable-game-palette-out.bin": "b1b9022ba23b6f50c3ba0433e5a4f4491301d00f63dc120a9eb633fdeb331acd",
        "habitable-game-render-state-out.bin": "a6abdbfda62a6a764f0ef7ef9b7415597de116dd02ec74c14ec5bce2d0048be3",
        "habitable-game-s-background-out.bin": "79bd1c30083c26d93f96d19b21b617d8d0f212a36c70fb4a4d0ad0c99465170d",
        "habitable-game-sun-out.bin": "48c995e7970dca1b38126ec8b297c7289022857e2e852af373a60e2a67c8bd11",
        "habitable-game-vh-out.bin": "c46bb4dc57136e653aa52144db9713be60cd44391bcf0422905ec445e1122943",
    },
}

PRODUCT_SIZES = {
    "habitable-game-local-out.bin": 176,
    "habitable-game-p-background-out.bin": 65552,
    "habitable-game-p-surfacemap-out.bin": 40000,
    "habitable-game-page-out.bin": 64000,
    "habitable-game-palette-out.bin": 3072,
    "habitable-game-render-state-out.bin": 24,
    "habitable-game-s-background-out.bin": 64800,
    "habitable-game-sun-out.bin": 128,
    "habitable-game-vh-out.bin": 156,
}

PROVENANCE_SHA256 = "a15599f087520c18cf0c77dd3776c42570a78c1e6ffe9a5870ed020a6eba5d01"
CURRENT_SHA256 = "4a73b344c10b34221bb21f32f09013ac9baa7889ab8de2ff665c52f23ee70bc1"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def check_source_contract(check) -> None:
    source = GROUND.read_text(encoding="utf-8")
    check(all(fragment in source for fragment in (
        "A = [VHGNDlat]; A '* 360; A + [VHGNDlon]; [VHGNDptr] = A;",
        "A = [VHGNDptr]; A > 1; A + ROBJ; [MBptr] = A; => MEM get byte;",
        "A = [VHGNDlocseed]; A & 0FFFFh; => SU srand;",
        "A = [VHGNDsctype]; ? A = 3 -> VHGND scenario desert rain;",
        "C = 4; => SU rnd; C + 1; -> VHGND scenario scale rain;",
        "A = [GRSKrainy]; ? A '>= 40200000h -> VHGND local primary done;",
        "A = [GRSKrainy]; ? A '>= 3F99999Ah -> VHGND primary flare done;",
    )), "surface renderer retains the source map, Borland weather, primary, and flare gates")
    flare_gate = struct.unpack("<f", bytes.fromhex("9a99993f"))[0]
    check(
        flare_gate == 1.2000000476837158
        and NATIVE["control50"]["rain"] < flare_gate <= NATIVE["threshold51"]["rain"],
        "binary32 rains 0.9375 and 1.25 bracket the inclusive 0x3F99999A flare gate",
    )
    lattice = {
        f32(f32(min(cloud, 20) * 0.25) / divisor)
        for cloud in range(256)
        for divisor in range(1, 5)
    }
    check(flare_gate not in lattice,
          "the retained quarter-unit cloud/divisor lattice cannot fabricate exact rain 1.2")


def check_provenance(check) -> dict[str, object]:
    data = PROVENANCE.read_bytes()
    check(
        sha256(data.replace(b"\r\n", b"\n")) == PROVENANCE_SHA256,
        "habitable-flare provenance has its pinned normalized SHA-256",
    )
    try:
        state = json.loads(data)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        check(False, f"habitable-flare provenance decodes safely: {error}")
        return {}

    system = state.get("system", {})
    native = state.get("native_capture", {})
    weather = state.get("native_ram_contract", {}).get("weather", {})
    rotation = state.get("native_ram_contract", {}).get("rotation_arrays", {}).get("both", {})
    gate = state.get("native_ram_contract", {}).get("terminator_and_source_gate", {})
    visual = state.get("visual_contract", {})
    check(
        system.get("coordinates") == list(STAR)
        and system.get("star_class") == 0
        and system.get("target_body") == 3
        and system.get("target_owner") == -1
        and system.get("target_type") == 3
        and system.get("atmosphere") is True
        and system.get("orientation_scenario") == 3,
        "provenance identifies the atmospheric class-0/type-3 world and DESERT scenario",
    )
    control_clock = native.get("control50", {}).get("captured_clock")
    threshold_clock = native.get("threshold51", {}).get("captured_clock")
    check(
        native.get("authored_clock") == 1344168020.0
        and native.get("product_clock") == 1344168020
        and native.get("snapshot_wait_seconds") == 20
        and int(control_clock) == int(threshold_clock) == 1344168019
        and control_clock != threshold_clock,
        "same-command native captures share one integer second without claiming product-clock identity",
    )
    check(
        weather.get("control50") == {
            "rainy": 0.9375, "albedo": 32, "scenario": 3, "desert_divisor": 4,
        }
        and weather.get("threshold51") == {
            "rainy": 1.25, "albedo": 32, "scenario": 3, "desert_divisor": 3,
        },
        "native RAM provenance retains the exact below/above flare-gate weather states",
    )
    check(
        rotation == {
            "rtperiod": 694,
            "raw_rotation": -79,
            "normalized_rotation": 281,
            "term_start": 137,
            "term_end": 267,
        }
        and gate.get("viewpoint") == 268
        and gate.get("plwp") == 102
        and gate.get("both_daylight") is True,
        "native state retains one discrete rotation/terminator contract and daylight",
    )
    check(
        visual.get("source_crop") == list(SOURCE_CROP)
        and visual.get("source_crop_pixels") == 1225
        and visual.get("native_pair_source_crop_index_differences") == 1222,
        "provenance bounds the exact 35x35 source discriminator and its transition",
    )
    return state


def grade_maps_and_weather(check) -> None:
    blobs: dict[str, bytes] = {}
    for name, (path, expected_hash) in MAPS.items():
        data = path.read_bytes()
        blobs[name] = data
        check(sha256(data) == expected_hash, f"retained {name} map has its pinned SHA-256")

    surface = blobs["p_background"]
    clouds = blobs["objectschart"]
    check(len(surface) >= 64800 and len(clouds) == 40000,
          "retained surface and object maps cover the complete landing lookup")

    harness = ROOT / "noctis-harness"
    if str(harness) not in sys.path:
        sys.path.insert(0, str(harness))
    try:
        from brtl_oracle import Brtl
        import ns_spec
    except ImportError as error:
        check(False, f"independent weather oracles import safely: {error}")
        return

    system = ns_spec.System(*STAR)
    orient = system.p_orb_orient[3]
    scenario_chop = int(555 * orient)
    check(
        system.cls == 0
        and system.ray == 5.150000095367432
        and system.nop == 12
        and system.nob == 78
        and system.p_owner[3] == -1
        and system.p_type[3] == 3
        and orient == 2.548180707911721
        and scenario_chop == 1414
        and scenario_chop % 4 + 1 == 3,
        "independent system model reproduces the class-0/type-3 hierarchy and DESERT scenario",
    )

    for name, expected in NATIVE.items():
        longitude = expected["longitude"]
        pointer = LATITUDE * 360 + longitude
        cloud_pointer = pointer >> 1
        sample = surface[pointer]
        cloud = clouds[cloud_pointer]
        recovered = ((sample - cloud) // 4) * 4 * 2
        raw_rain = f32(min(cloud * 0.25, 5.0))
        rng = Brtl()
        rng.srand(LATITUDE * longitude)
        random100 = rng.random(100)
        random4 = rng.random(4)
        divisor = random4 + 1
        rain = f32(raw_rain / divisor)
        check(
            pointer == (12290 if name == "control50" else 12291)
            and cloud_pointer == 6145
            and sample == cloud + 19 == 34
            and cloud == 15
            and recovered == 32,
            f"{name} recovers its adjacent pointer and shared surface/cloud/albedo state",
        )
        check(
            random100 == expected["random100"]
            and random4 == expected["random4"]
            and divisor == expected["divisor"]
            and raw_rain == 3.75
            and rain == expected["rain"],
            f"{name} independent Borland stream reproduces its sole changing divisor and rain",
        )


def grade_native(check) -> tuple[dict[str, bytes], dict[str, tuple[int, ...]]]:
    pages: dict[str, bytes] = {}
    palettes: dict[str, tuple[int, ...]] = {}
    for name, expected in NATIVE.items():
        bmp = expected["bmp"]
        surface = expected["surface"]
        assert isinstance(bmp, Path) and isinstance(surface, Path)
        bmp_data = bmp.read_bytes()
        surface_data = surface.read_bytes()
        check(sha256(bmp_data) == expected["bmp_sha256"],
              f"{name} native BMP has its pinned SHA-256")
        check(sha256(surface_data) == expected["surface_sha256"],
              f"{name} native surface state has its pinned SHA-256")
        try:
            surface_state = struct.unpack("<hhiiiifffff", surface_data)
        except struct.error as error:
            check(False, f"{name} surface state decodes safely: {error}")
        else:
            check(surface_state == expected["surface_state"],
                  f"{name} retains the exact authored landed resume state")
        try:
            page, palette = decode_bmp(bmp)
        except (AssertionError, OSError, struct.error) as error:
            check(False, f"{name} native BMP decodes safely: {error}")
            continue
        pages[name] = page
        palettes[name] = palette
        check(len(page) == 64000 and sha256(page) == expected["page_sha256"],
              f"{name} BMP yields its pinned top-down indexed page")
        check(
            len(palette) == 768
            and sha256(struct.pack("<768I", *palette)) == expected["palette_sha256"],
            f"{name} BMP yields its pinned active six-bit palette",
        )
        source_crop = page_crop(page, SOURCE_CROP)
        check(
            len(source_crop) == 1225
            and sha256(source_crop) == expected["source_crop_sha256"],
            f"{name} retains its exact centred 35x35 source discriminator",
        )

    if set(pages) == set(NATIVE):
        control_crop = page_crop(pages["control50"], SOURCE_CROP)
        threshold_crop = page_crop(pages["threshold51"], SOURCE_CROP)
        check(
            min(control_crop) == 80
            and max(control_crop) == 126
            and Counter(control_crop)[126] == 81
            and len(set(control_crop[23 * 35:])) > 30,
            "control50 retains the admitted radial flare gradient through the lower crop",
        )
        check(
            min(threshold_crop) == 74
            and max(threshold_crop) == 127
            and Counter(threshold_crop)[127] == 1
            and threshold_crop[23 * 35:28 * 35] == bytes((77,) * 175)
            and threshold_crop[28 * 35:] == bytes((78,) * 245),
            "threshold51 retains the local primary but no lower-crop lens flare",
        )
        check(
            mismatch_count(control_crop, threshold_crop) == 1222
            and band_mismatch_count(control_crop, threshold_crop) == 0
            and mismatch_count(pages["control50"], pages["threshold51"]) == 25024
            and band_mismatch_count(pages["control50"], pages["threshold51"]) == 0,
            "native pair retains its exact source transition and bounded complete-page non-claim",
        )
    if set(palettes) == set(NATIVE):
        check(
            mismatch_count(palettes["control50"], palettes["threshold51"]) == 229,
            "native paired palettes retain their explicit complete-palette non-claim",
        )
    return pages, palettes


def check_reproducible_current(check) -> None:
    try:
        mkcurrent = load_mkcurrent()
        rebuilt, system = mkcurrent.build(
            *STAR, 3, sync=3, secs=1344168020.0,
            charge=120, power=30000, draw_hud=0,
            angles=(-44.0, 33.0, 0.0),
        )
    except (AssertionError, OSError, ImportError) as error:
        check(False, f"tracked CURRENT builder runs safely: {error}")
        return
    check(len(rebuilt) == 385 and sha256(rebuilt) == CURRENT_SHA256,
          "tracked builder reproduces the exact native CURRENT input")
    check(
        system["cls"] == 0
        and system["ray"] == 5.150000095367432
        and system["nop"] == 12
        and system["nob"] == 78
        and system["owner"][3] == -1
        and system["ptype"][3] == 3,
        "tracked generator independently reproduces the habitable-world hierarchy",
    )


def grade_product_pair(
    control_directory: Path,
    threshold_directory: Path,
    native_pages: dict[str, bytes],
    native_palettes: dict[str, tuple[int, ...]],
    provenance: dict[str, object],
    check,
) -> None:
    directories = {
        "control50": control_directory.resolve(),
        "threshold51": threshold_directory.resolve(),
    }
    pages: dict[str, bytes] = {}
    palettes: dict[str, tuple[int, ...]] = {}
    sun_ints: dict[str, tuple[int, ...]] = {}
    sun_floats: dict[str, tuple[float, ...]] = {}
    vectors: dict[str, tuple[float, ...]] = {}
    views: dict[str, tuple[int, ...]] = {}
    matched = provenance.get("matched_product", {})

    for name, directory in directories.items():
        expected_hashes = PRODUCT_HASHES[name]
        for filename, expected_hash in expected_hashes.items():
            path = directory / filename
            check(
                path.is_file() and path.stat().st_size == PRODUCT_SIZES[filename],
                f"{name} product emitted {filename} at its exact size",
            )
            if path.is_file():
                check(sha256(path.read_bytes()) == expected_hash,
                      f"{name} product {filename} has its pinned SHA-256")
        if not all((directory / filename).is_file() for filename in expected_hashes):
            continue

        page = (directory / "habitable-game-page-out.bin").read_bytes()
        palette_data = (directory / "habitable-game-palette-out.bin").read_bytes()
        sun_data = (directory / "habitable-game-sun-out.bin").read_bytes()
        view_data = (directory / "habitable-game-vh-out.bin").read_bytes()
        pages[name] = page
        palettes[name] = struct.unpack("<768I", palette_data)
        sun_ints[name] = struct.unpack("<32i", sun_data)
        sun_floats[name] = struct.unpack("<32f", sun_data)
        vectors[name] = struct.unpack_from("<3d", sun_data, 40)
        views[name] = struct.unpack("<39i", view_data)
        expected_y = -130749 if name == "control50" else -77578
        check(
            views[name][:6] == (1598248, expected_y, 2251369, -44, 33, 0),
            f"{name} product retains its exact landed source-camera pose",
        )
        source_crop = page_crop(page, SOURCE_CROP)
        check(
            source_crop == page_crop(native_pages[name], SOURCE_CROP)
            and len(source_crop) == 1225,
            f"{name} product exactly matches the native 35x35 source crop",
        )
        check(matched.get(name, {}).get("hashes", {}) == expected_hashes,
              f"{name} product hashes agree with retained provenance")

    if set(pages) != set(NATIVE):
        return

    control_i = sun_ints["control50"]
    threshold_i = sun_ints["threshold51"]
    control_f = sun_floats["control50"]
    threshold_f = sun_floats["threshold51"]
    check(
        control_i[:6] == threshold_i[:6] == (1, 1, 3, 0, 1, 0),
        "product diagnostics retain one landed atmospheric daylight class/type state",
    )
    check(
        control_f[6:10] == (
            0.9375, 68.08619689941406, 243.80813598632812, 5.150000095367432,
        )
        and threshold_f[6:10] == (
            1.25, 67.30359649658203, 243.80813598632812, 5.150000095367432,
        ),
        "product keeps both local primaries admitted while rain brackets the flare gate",
    )
    check(
        vectors["control50"] == (
            -90.99195861816406, -175.78428649902344, 142.34730529785156,
        )
        and vectors["threshold51"] == (
            -94.07290649414062, -174.8020477294922, 141.55189514160156,
        ),
        "product retains both primary vectors across the separate flare transition",
    )
    check(
        control_i[16:24] == (1, 162, 94, 122, 0, 0, 0, 0)
        and threshold_i[16:24] == (0,) * 8,
        "product projects the 0.9375 flare and suppresses it at 1.25",
    )
    check(
        control_i[24:32] == (694, 281, 268, 102, 137, 267, 87, 1)
        and threshold_i[24:32] == (694, 281, 268, 102, 137, 267, 86, 1),
        "product shares the native discrete rotation and terminator state exactly",
    )
    check(
        mismatch_count(native_pages["control50"], pages["control50"]) == 13211
        and band_mismatch_count(native_pages["control50"], pages["control50"]) == 0
        and mismatch_count(native_palettes["control50"], palettes["control50"]) == 465,
        "control comparison has exact complete-page painter families and bounded non-claims",
    )
    check(
        mismatch_count(native_pages["threshold51"], pages["threshold51"]) == 13138
        and band_mismatch_count(native_pages["threshold51"], pages["threshold51"]) == 0
        and mismatch_count(native_palettes["threshold51"], palettes["threshold51"]) == 478,
        "threshold comparison has exact complete-page painter families and bounded non-claims",
    )
    check(
        mismatch_count(pages["control50"], pages["threshold51"]) == 24990
        and band_mismatch_count(pages["control50"], pages["threshold51"]) == 0
        and mismatch_count(palettes["control50"], palettes["threshold51"]) == 268,
        "product paired pages and palettes retain the bounded complete-output non-claim",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-product-directory", type=Path)
    parser.add_argument("--threshold-product-directory", type=Path)
    args = parser.parse_args()
    if ((args.control_product_directory is None)
            != (args.threshold_product_directory is None)):
        parser.error("control and threshold product directories must be supplied together")

    errors: list[str] = []

    def check(condition: bool, message: str) -> None:
        print("PASS" if condition else "FAIL", message)
        if not condition:
            errors.append(message)

    check_source_contract(check)
    provenance = check_provenance(check)
    grade_maps_and_weather(check)
    native_pages, native_palettes = grade_native(check)
    check_reproducible_current(check)

    if args.control_product_directory is not None and set(native_pages) == set(NATIVE):
        assert args.threshold_product_directory is not None
        grade_product_pair(
            args.control_product_directory,
            args.threshold_product_directory,
            native_pages,
            native_palettes,
            provenance,
            check,
        )
    else:
        print("SKIP product comparison requires both matched product directories")

    if errors:
        print(f"habitable flare oracle: {len(errors)} failure(s)")
        return 1
    print("habitable flare oracle: all requested checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
