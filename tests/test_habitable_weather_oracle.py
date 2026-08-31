"""Grade the atmospheric type-3 primary-sun rain-2.5 boundary.

The default mode is non-GUI.  It authenticates two same-command NIV+ indexed
BMPs, their landed states and retained source maps, independently reconstructs
the Borland weather stream, and protects the inclusive binary32 2.5 source
gate.  Optional product directories add all exported-state hashes and exact
native/product source-scene crops::

    python tests/test_habitable_weather_oracle.py \
        --control-product-directory build/renderer-hab-weather-sun-control104 \
        --threshold-product-directory build/renderer-hab-weather-sun-threshold105
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
PROVENANCE = OUT / "hab_weather_primary_gate_8020_native.provenance.json"
GROUND = ROOT / "work" / "vhground.txt"
STAR = (1463568, -4728350, -437812)
LATITUDE = 56
SOURCE_CROP = (145, 85, 176, 116)
CENTER_CROP = (155, 95, 166, 106)
SCENE_CROP = (0, 7, 320, 150)

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
    "control104": {
        "longitude": 104,
        "bmp": OUT / "hab_weather_control104_matchedsecond8020_native.shot.BMP",
        "surface": OUT / "hab_weather_control104_matchedsecond8020_native.SURFACE.BIN",
        "bmp_sha256": "8e34a5a6b6c272c4f26574b0b3f0ae4e6bd42d4b6c36157da42af554630bd434",
        "surface_sha256": "3de391a4c1c0823af2dd4e739e740b396d8fbc278592930266cbb3c2e3825d06",
        "page_sha256": "7f865640de2c00d2835f7cd19b986d3fb9a94a0297a1c4e35c92156765585ca1",
        "palette_sha256": "a4aafbd015f5eab2f798ab58e82d140dbea66ff1305f7fd5e3a341a882629b83",
        "surface_state": (104, 56, 8, 8, 0, 0, 1598248.0, 1.0, 2251369.0, -26.0, 87.0),
        "surface_sample": 38,
        "albedo": 32,
        "random100": 55,
        "random4": 2,
        "divisor": 3,
        "rain": 1.6666666269302368,
        "source_crop_sha256": "7d858b2b08fa16c2c7b95d6c3189df464a69f82a40abc69939d17284ba940f05",
        "scene_crop_sha256": "77112664096e846326784cc9f3edd1bc2be8cfeb3d8eadb7e2c712ece22d235b",
    },
    "threshold105": {
        "longitude": 105,
        "bmp": OUT / "hab_weather_threshold105_matchedsecond8020_native.shot.BMP",
        "surface": OUT / "hab_weather_threshold105_matchedsecond8020_native.SURFACE.BIN",
        "bmp_sha256": "b481c980ec50acf1c9ddb131e94e8ab427a7a5eda5a4c4bc3f2f0c34a5c3b49b",
        "surface_sha256": "be16eaaee291a5493dcdfc9b27d618705c7e0b39ecc298066d22b7283234935b",
        "page_sha256": "2709f8932c45aeac22ea5391bd8b2d7b131ad731c0df43c29c808ad281b50c62",
        "palette_sha256": "7aed89a74d2099e64526254a0a462bd5090e379a8d751b37315a92da4e3b68de",
        "surface_state": (105, 56, 8, 8, 0, 0, 1598248.0, 1.0, 2251369.0, -26.0, 87.0),
        "surface_sample": 41,
        "albedo": 40,
        "random100": 14,
        "random4": 1,
        "divisor": 2,
        "rain": 2.5,
        "source_crop_sha256": "edaa518d33558b2de4d52aef63cda576dbe2246dab9704becd96049b59bc145a",
        "scene_crop_sha256": "a855d445287a216295355b2c8975aad5b90f314ebdfdfacbae056a741931720e",
    },
}

PROVENANCE_PRODUCT_HASHES = {
    "control104": {
        "habitable-game-local-out.bin": "0655bb132a48420176c1264dc6eaf30bf5c306041bca44de450648828882cd11",
        "habitable-game-p-background-out.bin": "b188c116196f6d5510c596ab16521bd7f324460e77ab8321b09a45cd16b83f68",
        "habitable-game-p-surfacemap-out.bin": "592f2f226f6402e89c53e822c0703f52c88ba14d8f14d692bb922fa7ae2606e2",
        "habitable-game-page-out.bin": "3d4e2b9bb217a4410929b9ff8ba84df514bc540b627153550c3258aa003f5ee5",
        "habitable-game-palette-out.bin": "a4aafbd015f5eab2f798ab58e82d140dbea66ff1305f7fd5e3a341a882629b83",
        "habitable-game-render-state-out.bin": "847666f3fe1ac0d5bbfa9f63df98231addee318107146a410e3d49e1569f1251",
        "habitable-game-s-background-out.bin": "79bd1c30083c26d93f96d19b21b617d8d0f212a36c70fb4a4d0ad0c99465170d",
        "habitable-game-sun-out.bin": "23bbbee69fa5c3771afeedafe193012b9cfa01304aec48064afc3e811fa68781",
        "habitable-game-vh-out.bin": "66f1df863422d968e8cb85e2d273a24ecc56262ca099c84e9b3e627c97c273b7",
    },
    "threshold105": {
        "habitable-game-local-out.bin": "46496e7ec691a271ef9083e33868acea0a19c7bcfacc66cc1a15c644c13c0c05",
        "habitable-game-p-background-out.bin": "def68f45fdb6c4060085135966a7c8f9be3125931e5f3bb6e8eb1ebbbf04801f",
        "habitable-game-p-surfacemap-out.bin": "d31b9bec62653b71c593c2fd7bc20ac69317226616b4045bc0eece21826788da",
        "habitable-game-page-out.bin": "fe64894edfd7cf3366131427b035ec2dc64458ddd9ceca30b657c45c9bf28ced",
        "habitable-game-palette-out.bin": "9f4b52a68ba74de19dc5686257c5069793267ec1bae49f00aa3cdb6f9915a6e3",
        "habitable-game-render-state-out.bin": "fd4cdef79fa5f9b318007c2aed8d244ea9b561eba505a9ff6a4e550b826e4e3e",
        "habitable-game-s-background-out.bin": "116f96d5c6ea7b14d6ffb773c0fcdca4af17c5b708df340067672dc53890e71b",
        "habitable-game-sun-out.bin": "b8d66b10d245b8667f339f430706cf81a6fd001416a875a0d1a7156c54f6330d",
        "habitable-game-vh-out.bin": "faa7dfb376ebcb461f610574662f57554b5ca813edeb3c6115a7aaba4abfa7e1",
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

PROVENANCE_SHA256 = "85fcb87a27d98bdacf6dde68f5c96ba1a87ec2360a42dbf94e1325f53d76cbd7"
CURRENT_SHA256 = "c80a05f35cfb5c1332ab48ac5e0871b6d360f204665c060ffd9282cd3de4f7eb"


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
    check(
        struct.unpack("<f", bytes.fromhex("00002040"))[0] == 2.5,
        "the inclusive primary-gate word 0x40200000 is binary32 2.5",
    )


def check_provenance(check) -> dict[str, object]:
    data = PROVENANCE.read_bytes()
    check(
        sha256(data.replace(b"\r\n", b"\n")) == PROVENANCE_SHA256,
        "habitable-weather provenance has its pinned normalized SHA-256",
    )
    try:
        state = json.loads(data)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        check(False, f"habitable-weather provenance decodes safely: {error}")
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
        "provenance identifies the same atmospheric class-0/type-3 world and DESERT scenario",
    )
    control_clock = native.get("control104", {}).get("captured_clock")
    threshold_clock = native.get("threshold105", {}).get("captured_clock")
    check(
        native.get("authored_clock") == 1344168020.0
        and native.get("product_clock") == 1344168020
        and native.get("snapshot_wait_seconds") == 20
        and int(control_clock) == int(threshold_clock) == 1344168020
        and control_clock != threshold_clock,
        "same-command native captures share the matched integer second without claiming raw-clock identity",
    )
    check(
        weather.get("control104") == {
            "rainy": 1.6666666269302368,
            "albedo": 32,
            "scenario": 3,
            "desert_divisor": 3,
        }
        and weather.get("threshold105") == {
            "rainy": 2.5,
            "albedo": 40,
            "scenario": 3,
            "desert_divisor": 2,
        },
        "native RAM provenance retains the exact below-gate and at-gate weather states",
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
        "native state retains one discrete rotation/terminator contract and daylight in both cases",
    )
    check(
        visual.get("source_crop") == list(SOURCE_CROP)
        and visual.get("source_crop_pixels") == 961
        and visual.get("exact_scene_crop") == list(SCENE_CROP)
        and visual.get("exact_scene_crop_pixels") == 45760,
        "provenance bounds the exact centred source and full-width scene crops",
    )
    check(
        visual.get("authority_limit")
        == (
            "The 45,760 indexed pixels in rows 7..149 and the centred 31x31 "
            "source discriminator are exact across engines in both states; the "
            "control palette is also exact. Complete pages, the threshold "
            "palette/RGB image, lower terrain affected by the bounded settled-height "
            "difference, raw binary64 clock identity, admitted-vector diagnostic "
            "semantics at the suppressed threshold, and later adapted pages are "
            "explicit non-claims."
        )
        and visual.get("control104_native_product_index_differences") == 5522
        and visual.get("control104_native_product_palette_band_differences") == 352
        and visual.get("control104_native_product_palette_component_differences") == 0
        and visual.get("threshold105_native_product_index_differences") == 309
        and visual.get("threshold105_native_product_palette_band_differences") == 0
        and visual.get("threshold105_native_product_palette_component_differences") == 754
        and visual.get("product_pair_index_differences") == 15738
        and visual.get("product_pair_palette_band_differences") == 4337
        and visual.get("product_pair_palette_component_differences") == 439,
        "historical complete-output non-claims remain pinned in provenance",
    )
    return state


def grade_maps_and_weather(check) -> None:
    blobs: dict[str, bytes] = {}
    for name, (path, expected_hash) in MAPS.items():
        data = path.read_bytes()
        blobs[name] = data
        check(sha256(data) == expected_hash, f"retained {name} map has its pinned SHA-256")

    if set(blobs) != set(MAPS):
        return
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
        "independent system model reproduces the class-0/type-3 hierarchy and DESERT orientation scenario",
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
            pointer == (20264 if name == "control104" else 20265)
            and cloud_pointer == 10132
            and sample == expected["surface_sample"]
            and cloud == 21
            and recovered == expected["albedo"],
            f"{name} independently recovers its adjacent surface sample, shared cloud byte, and albedo",
        )
        check(
            random100 == expected["random100"]
            and random4 == expected["random4"]
            and divisor == expected["divisor"]
            and raw_rain == 5.0
            and rain == expected["rain"],
            f"{name} independent Borland stream reproduces its DESERT divisor and binary32 rain",
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
        scene_crop = page_crop(page, SCENE_CROP)
        check(
            len(source_crop) == 961
            and sha256(source_crop) == expected["source_crop_sha256"]
            and sha256(scene_crop) == expected["scene_crop_sha256"],
            f"{name} retains its exact centred discriminator and 45,760-index scene crop",
        )

    if set(pages) == set(NATIVE):
        control_crop = page_crop(pages["control104"], SOURCE_CROP)
        threshold_crop = page_crop(pages["threshold105"], SOURCE_CROP)
        check(
            min(control_crop) == 83
            and max(control_crop) == 127
            and Counter(control_crop)[127] == 8,
            "control104 retains the bright radial primary through index 127",
        )
        check(
            Counter(threshold_crop) == {85: 254, 86: 563, 87: 144}
            and page_crop(pages["threshold105"], CENTER_CROP) == bytes((86,) * 121),
            "threshold105 retains the exact source-free centre at the inclusive gate",
        )
        check(
            mismatch_count(pages["control104"], pages["threshold105"]) == 16195
            and band_mismatch_count(pages["control104"], pages["threshold105"]) == 4689,
            "native paired pages retain the bounded complete-page non-claim",
        )
    if set(palettes) == set(NATIVE):
        check(
            mismatch_count(palettes["control104"], palettes["threshold105"]) == 678,
            "native paired palettes retain their explicit complete-palette non-claim",
        )
    return pages, palettes


def check_reproducible_current(check) -> None:
    try:
        mkcurrent = load_mkcurrent()
        rebuilt, system = mkcurrent.build(
            *STAR, 3, sync=3, secs=1344168020.0,
            charge=120, power=30000, draw_hud=0,
            angles=(-26.0, 87.0, 0.0),
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
        "control104": control_directory.resolve(),
        "threshold105": threshold_directory.resolve(),
    }
    pages: dict[str, bytes] = {}
    palettes: dict[str, tuple[int, ...]] = {}
    sun_ints: dict[str, tuple[int, ...]] = {}
    sun_floats: dict[str, tuple[float, ...]] = {}
    vectors: dict[str, tuple[float, ...]] = {}
    views: dict[str, tuple[int, ...]] = {}
    matched = provenance.get("matched_product", {})
    stable_diagnostics = {
        "habitable-game-p-background-out.bin",
        "habitable-game-p-surfacemap-out.bin",
        "habitable-game-palette-out.bin",
        "habitable-game-render-state-out.bin",
        "habitable-game-s-background-out.bin",
        "habitable-game-sun-out.bin",
    }

    for name, directory in directories.items():
        provenance_hashes = PROVENANCE_PRODUCT_HASHES[name]
        for filename, historical_hash in provenance_hashes.items():
            path = directory / filename
            check(
                path.is_file() and path.stat().st_size == PRODUCT_SIZES[filename],
                f"{name} product emitted {filename} at its exact size",
            )
            if path.is_file() and filename in stable_diagnostics:
                check(sha256(path.read_bytes()) == historical_hash,
                      f"{name} product retains the pinned state-independent {filename}")
        if not all((directory / filename).is_file() for filename in provenance_hashes):
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
        expected_y = -90354 if name == "control104" else -56865
        check(
            views[name][:6] == (1598248, expected_y, 2251369, -26, 87, 0),
            f"{name} product retains its exact landed source-camera pose",
        )
        source_crop = page_crop(page, SOURCE_CROP)
        scene_crop = page_crop(page, SCENE_CROP)
        check(
            source_crop == page_crop(native_pages[name], SOURCE_CROP)
            and scene_crop == page_crop(native_pages[name], SCENE_CROP)
            and len(scene_crop) == 45760,
            f"{name} product exactly matches the native source crop and all 45,760 scoped indices",
        )
        expected_provenance_hashes = matched.get(name, {}).get("hashes", {})
        check(expected_provenance_hashes == provenance_hashes,
              f"{name} historical product hashes remain pinned in provenance")

    if set(pages) != set(NATIVE):
        return

    control_i = sun_ints["control104"]
    threshold_i = sun_ints["threshold105"]
    control_f = sun_floats["control104"]
    threshold_f = sun_floats["threshold105"]
    check(
        control_i[:6] == threshold_i[:6] == (1, 1, 3, 0, 1, 0),
        "product diagnostics retain one landed atmospheric daylight class/type state",
    )
    check(
        control_f[6:10] == (
            1.6666666269302368,
            25.8257999420166,
            243.80813598632812,
            5.150000095367432,
        )
        and threshold_f[6:10] == (
            2.5,
            25.04319953918457,
            243.80813598632812,
            0.0,
        ),
        "product diagnostics preserve below-2.5 admission and inclusive 2.5 suppression",
    )
    check(
        vectors["control104"] == (
            -219.4572296142578,
            -105.62987518310547,
            11.102143287658691,
        )
        and vectors["threshold105"] == (0.0, 0.0, 0.0)
        and control_i[16:24] == threshold_i[16:24] == (0,) * 8,
        "product keeps the control primary vector while both rain states suppress the separate flare",
    )
    check(
        control_i[24:32] == (694, 281, 268, 102, 137, 267, 33, 1)
        and threshold_i[24:32] == (694, 281, 268, 102, 137, 267, 32, 1),
        "product shares the native discrete rotation and terminator state exactly",
    )
    check(
        page_crop(pages["control104"], SOURCE_CROP)
        == page_crop(native_pages["control104"], SOURCE_CROP)
        and page_crop(pages["threshold105"], CENTER_CROP) == bytes((86,) * 121),
        "native and product share the exact bright-control and suppressed-threshold discriminators",
    )
    for name in ("control104", "threshold105"):
        print(
            f"INFO {name} current complete page/palette equality is not graded "
            f"({mismatch_count(native_pages[name], pages[name])} index, "
            f"{band_mismatch_count(native_pages[name], pages[name])} band, "
            f"{mismatch_count(native_palettes[name], palettes[name])} palette-component "
            "mismatches)"
        )
    print(
        "INFO current product control/threshold complete-output equality is not graded "
        f"({mismatch_count(pages['control104'], pages['threshold105'])} index, "
        f"{band_mismatch_count(pages['control104'], pages['threshold105'])} band, "
        f"{mismatch_count(palettes['control104'], palettes['threshold105'])} "
        "palette-component mismatches)"
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
        print(f"habitable weather oracle: {len(errors)} failure(s)")
        return 1
    print("habitable weather oracle: all requested checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
