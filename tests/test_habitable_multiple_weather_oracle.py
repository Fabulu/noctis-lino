"""Grade ROTOR IGNE's landed secondary weather gates.

The default non-GUI mode authenticates three NIV+ indexed BMPs, the retained
companion-moon source maps, the complete Borland weather stream, and the
inclusive secondary-disc/flare gates.  Optional product directories add exact
export hashes and bounded native/product painter-family comparisons::

    python tests/test_habitable_multiple_weather_oracle.py \
        --low-product-directory build/renderer-hab-multiple-posb-low232 \
        --painter-product-directory build/renderer-hab-multiple-posb-painter231 \
        --flare-product-directory build/renderer-hab-multiple-posb-flare236
"""

from __future__ import annotations

import argparse
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
PROVENANCE = OUT / "hab_multiple_secondary_weather_8020_native.provenance.json"
GROUND = ROOT / "work" / "vhground.txt"
STAR = (3866416, -4813508, -735695)
LATITUDE = 88
CURRENT_SHA256 = "574a3a62b1b96bd4cea2be57deaa2df0d019924844a4d27b09151b9a954a4608"
PROVENANCE_SHA256 = "f450db5209b0785ff3c8422d4e152edf65ba7fcd5f6958ac5023c8df1aaed731"

MAPS = {
    "s_background": (
        OUT / "rotor_igne_b08_t3.s_background",
        64800,
        "0ad37e03dcc757a8709c7c469e01a5d3c25a49e5c8bd164fb51bdf55e82acc3b",
    ),
    "objectschart": (
        OUT / "rotor_igne_b08_t3.objectschart",
        40000,
        "6dcc93913b612b0d658138f48e74b7cede3fa383f2aade412e36a23ea1065fb5",
    ),
}

NATIVE = {
    "low232": {
        "longitude": 232,
        "bmp": OUT / "hab_multiple_low232_weather8020_native.shot.BMP",
        "surface": OUT / "hab_multiple_low232_weather8020_native.SURFACE.BIN",
        "bmp_sha256": "81b8cfc6f5ec938c9440fdccd430fbb208e69cf8dec0c7d96df8a4dd0c06d120",
        "surface_sha256": "132d1a0f364aa6bae16ab3f851b4623670f5a413ca4ca0479c0b76eaffb46cda",
        "page_sha256": "b8c6656eb133f487b75ea8b7d8125bcec00dc0d3d57d0da0cd92782808b03fdb",
        "palette_sha256": "dfb2597dcb93dba37cb54aba97c2b607b3f50f1b581c0fb09917d4b3890f008e",
        "surface_state": (232, 88, 8, 8, 0, 0, 1327104.0, 1.0, 1884160.0, -20.0, -30.0),
        "surface_pointer": 31912,
        "cloud_pointer": 15956,
        "surface_sample": 48,
        "cloud": 31,
        "albedo": 32,
        "random100": 76,
        "divisor_draw": 2,
        "divisor": 3,
        "raw_rain": 5.0,
        "rain": 1.6666666269302368,
        "crop": (139, 73, 200, 134),
        "crop_sha256": "79a57a49edb9038b14745568babfb08a152366dbdf06d1713526b0be5e45433a",
        "product_crop_sha256": "e7c2befc03e4290e0df8a909c94c08e7c07dd22a7b5a355140a15068faa0d586",
        "native_range": (87, 124),
        "product_range": (87, 124),
        "bright_count": 4,
        "product_y": -113240,
        "flare": (1, 169, 103, 127),
    },
    "painter231": {
        "longitude": 231,
        "bmp": OUT / "hab_multiple_painter231_weather8020_native.shot.BMP",
        "surface": OUT / "hab_multiple_painter231_weather8020_native.SURFACE.BIN",
        "bmp_sha256": "552d93b9d8220b12c18a232473b364b601c3c1e57d545fd054230c78192243bb",
        "surface_sha256": "ce0c7c7b2d2e8e0de12d9391f51113ae3063955ab7af1863cbd05122be988c40",
        "page_sha256": "1feccec37b1752bb3ababc583d212d86828f10a033b0bf0ff8217bc1b9fdb8a4",
        "palette_sha256": "25a1556fce1fc2fafd961fc0dc8c4a83a9764c97e406f512b8ded12691aa57af",
        "surface_state": (231, 88, 8, 8, 0, 0, 1327104.0, 1.0, 1884160.0, -20.0, -30.0),
        "surface_pointer": 31911,
        "cloud_pointer": 15955,
        "surface_sample": 26,
        "cloud": 8,
        "albedo": 32,
        "random100": 83,
        "divisor_draw": 0,
        "divisor": 1,
        "raw_rain": 2.0,
        "rain": 2.0,
        "crop": (142, 74, 203, 135),
        "crop_sha256": "58c1b9ec5c53ff035b6bbbaafd3518347326682a3f9d1cd506e7aea2db12b93b",
        "product_crop_sha256": "40c6e63819e4b4d9fbb9b19a1432fcf0e956e0c6fbf5b55becefd046f50b8d50",
        "native_range": (87, 116),
        "product_range": (87, 114),
        "bright_count": 0,
        "product_y": -113240,
        "flare": (1, 172, 104, 91),
    },
    "flare236": {
        "longitude": 236,
        "bmp": OUT / "hab_multiple_flare236_weather8020_native.shot.BMP",
        "surface": OUT / "hab_multiple_flare236_weather8020_native.SURFACE.BIN",
        "bmp_sha256": "e2553110de97c31d1fbf471aa7fae2c6609b5c39ef875537e971e437db99dd1d",
        "surface_sha256": "09fabbc21028e8c13ae2be6b2f9188c11c02432f1d28186beadfe83f3d0e3cf5",
        "page_sha256": "86d819cc6744fd013a9187fc24963c8cc971560e8a40824e98f091f31761b895",
        "palette_sha256": "2e4da0dc409fb9dc4872c1bf7c3a98444920649d0dc403fb723b608b387f78a7",
        "surface_state": (236, 88, 8, 8, 0, 0, 1327104.0, 1.0, 1884160.0, -20.0, -30.0),
        "surface_pointer": 31916,
        "cloud_pointer": 15958,
        "surface_sample": 35,
        "cloud": 17,
        "albedo": 32,
        "random100": 48,
        "divisor_draw": 1,
        "divisor": 2,
        "raw_rain": 4.25,
        "rain": 2.125,
        "crop": (147, 90, 168, 111),
        "crop_sha256": "eb0f7470126eaa19794a7a6c1c4dc8c8d096285d17916576231861296682e507",
        "product_crop_sha256": "e61449203da52385d22de37dcc4dde2e8c8264dfc3b74ec1004cecf2430aa8d9",
        "native_range": (86, 94),
        "product_range": (90, 92),
        "bright_count": 0,
        "product_y": -82520,
        "flare": (0, 0, 0, 0),
    },
}

PROVENANCE_PRODUCT_HASHES = {
    "low232": {
        "habitablemultiple-game-local-out.bin": "aaf7b6ac646f5bc1e64e66b9a27df66c85b99c46a9451a4f1db79c22c9102209",
        "habitablemultiple-game-p-background-out.bin": "46a3d5722c74ddc7f819e3e7486c3d2543e6d7e7badcc8e8a1d5ecf17cad561f",
        "habitablemultiple-game-p-surfacemap-out.bin": "0fe7bf1be251383f40d64614721050fc2e3f7253e465ad82da2053c358105b35",
        "habitablemultiple-game-page-out.bin": "92973c41f58c37c85512cc153aa22f298bb62552d1ec9917588019022e7391f6",
        "habitablemultiple-game-palette-out.bin": "476a9eddbba2a4bd6185c9135046bfb1e8b828ffd8a2f5c2ebfa069e958f227f",
        "habitablemultiple-game-render-state-out.bin": "d8158f6abd7c75a050558d68d1ac1a164cfd1bd649d2882f0cec7a4a835abc95",
        "habitablemultiple-game-s-background-out.bin": "16eb45ca532c32748603b8528941f6fc02b9b5cfee99824574c588d528a04d2c",
        "habitablemultiple-game-sun-out.bin": "0e116b5f4fe6bf1b2a636e2881719e8b8b156e28d53aeb1fbbff7e956dbc491d",
        "habitablemultiple-game-vh-out.bin": "dfc5973189523db068bbf6c24d9931055d7f4eb1c34b5571be83a3b2e547b8c2",
    },
    "painter231": {
        "habitablemultiple-game-local-out.bin": "847cc7a7d3f0b04f8d100dbb80adfcbcde0d1a29e5097ea078228f85137de2db",
        "habitablemultiple-game-p-background-out.bin": "881d98127ebb3773dc1260d6a7c07cf712cd096f1c6dbedfed0c944e7d767076",
        "habitablemultiple-game-p-surfacemap-out.bin": "2c4879de165fab7615c72e5e6f8d900ad8bd21c740f9d937bd396e520c69028f",
        "habitablemultiple-game-page-out.bin": "637b97e9ad98a374bea352c07b8781c4a54acf14057c1bf5a31d8c94bf32632a",
        "habitablemultiple-game-palette-out.bin": "3375816c160cc8d6d27e67da7635ad234e35c72032296de789d43c4a5ea4da19",
        "habitablemultiple-game-render-state-out.bin": "4218cf4c062ae31bd7c3d5a47a9c32e1dafeb5642caa268f0a791f5e9637e7b0",
        "habitablemultiple-game-s-background-out.bin": "16eb45ca532c32748603b8528941f6fc02b9b5cfee99824574c588d528a04d2c",
        "habitablemultiple-game-sun-out.bin": "df548f9a7ffc1820c797d0929d7e2965163134801c86f4dac122d135d72386e3",
        "habitablemultiple-game-vh-out.bin": "9970a3e7dd275adf4b29f81d3d7fb9847842d5c51adb55e4f090c039374da148",
    },
    "flare236": {
        "habitablemultiple-game-local-out.bin": "976d1c25b64690ac62c6a2b617351570b9843468571c729e72efd8d31f271bb7",
        "habitablemultiple-game-p-background-out.bin": "5aba0586ff67061be9d0b0f616aec8dc1f7f74ba4dcad572dbf2059f91ab7888",
        "habitablemultiple-game-p-surfacemap-out.bin": "1f797761c9a8b6660ed6ebbf3ef6e0eb57328831f2c1843a6c9eb6e9deda858d",
        "habitablemultiple-game-page-out.bin": "21e1e6c42b18ed7e206dc322ada74366f108dbbc161ab83506453aa59ad00bda",
        "habitablemultiple-game-palette-out.bin": "c764edc8a346d267e34339b94538ce72449cab83956c06dd2788bdbfa0f23245",
        "habitablemultiple-game-render-state-out.bin": "d8158f6abd7c75a050558d68d1ac1a164cfd1bd649d2882f0cec7a4a835abc95",
        "habitablemultiple-game-s-background-out.bin": "16eb45ca532c32748603b8528941f6fc02b9b5cfee99824574c588d528a04d2c",
        "habitablemultiple-game-sun-out.bin": "a4a67e8e3ef90a2fe8d9c13ed8a332ea9572855dca139c1ce1faad6c35a08356",
        "habitablemultiple-game-vh-out.bin": "172aaa6f5dc106666e67e2ad93e305ee134e18a199d3814d3cb050683735c904",
    },
}

PRODUCT_SIZES = {
    "habitablemultiple-game-local-out.bin": 176,
    "habitablemultiple-game-p-background-out.bin": 65552,
    "habitablemultiple-game-p-surfacemap-out.bin": 40000,
    "habitablemultiple-game-page-out.bin": 64000,
    "habitablemultiple-game-palette-out.bin": 3072,
    "habitablemultiple-game-render-state-out.bin": 24,
    "habitablemultiple-game-s-background-out.bin": 64800,
    "habitablemultiple-game-sun-out.bin": 128,
    "habitablemultiple-game-vh-out.bin": 156,
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def check_source_contract(check) -> None:
    source = GROUND.read_text(encoding="utf-8")
    check(all(fragment in source for fragment in (
        "A = [VHGNDlat]; A '* 360; A + [VHGNDlon]; [VHGNDptr] = A;",
        "A = [SUpbase]; A + [VHGNDptr]; [MBptr] = A; => MEM get byte;",
        "A = [VHGNDlocseed]; A & 0FFFFh; => SU srand;",
        "C = 100; => SU rnd; A = C; ? A '<= 5 -> VHGND scenario local;",
        "A = [GRalbedo]; ? A '>= 25 -> VHGND scenario polar; [VHGNDsctype] = 1;",
        "A = [VHGNDsctype]; ? A = 3 -> VHGND scenario desert rain;",
        "A = [GRSKrainy]; ? A '>= 40000000h -> VHGND secondary sun done;",
        "A = [GRSKrainy]; ? A '>= 40066666h -> VHGND sun flares done;",
    )), "surface source retains map ownership, full weather ordering, and both secondary gates")
    check(
        struct.unpack("<f", struct.pack("<I", 0x40000000))[0] == 2.0
        and struct.unpack("<f", struct.pack("<I", 0x40066666))[0]
        == 2.0999999046325684,
        "secondary painter and flare words decode to exact binary32 thresholds",
    )


def check_provenance(check) -> dict[str, object]:
    data = PROVENANCE.read_bytes()
    check(
        sha256(data.replace(b"\r\n", b"\n")) == PROVENANCE_SHA256,
        "multiple-sun provenance has its pinned normalized SHA-256",
    )
    try:
        state = json.loads(data)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        check(False, f"multiple-sun provenance decodes safely: {error}")
        return {}

    system = state.get("system", {})
    native = state.get("native_capture", {})
    ram = state.get("native_ram_contract", {})
    visual = state.get("visual_contract", {})
    check(
        system.get("coordinates") == list(STAR)
        and system.get("star_class") == 8
        and system.get("companion_body") == 3
        and system.get("companion_type") == 10
        and system.get("target_body") == 8
        and system.get("target_owner") == 3
        and system.get("target_type") == 3
        and system.get("orientation_scenario") == 3,
        "provenance identifies the class-8/type-10/type-3 companion hierarchy",
    )
    clocks = [native.get(name, {}).get("captured_clock") for name in NATIVE]
    check(
        native.get("authored_clock") == 1344168020.0
        and native.get("product_clock") == 1344168020
        and native.get("snapshot_wait_seconds") == 20
        and all(isinstance(clock, float) and int(clock) == 1344168020 for clock in clocks)
        and len(set(clocks)) == 3,
        "native captures share the product integer second without claiming raw-clock identity",
    )
    check(
        ram.get("both_sources_daylight") is True
        and ram.get("shared_discrete") == {
            "period": 620,
            "rotation": 284,
            "primary_term_start": 71,
            "primary_term_end": 201,
        }
        and ram.get("weather", {}).get("low232", {}).get("rainy")
        == 1.6666666269302368
        and ram.get("weather", {}).get("painter231", {}).get("rainy") == 2.0
        and ram.get("weather", {}).get("flare236", {}).get("rainy") == 2.125,
        "provenance retains both daylight sources, one rotation, and the exact rain bracket",
    )
    crops = visual.get("crops", {})
    check(
        all(crops.get(name, {}).get(
            "native_product_painter_family_differences") == 0 for name in NATIVE)
        and "complete pages" in visual.get("authority_limit", ""),
        "provenance scopes painter-family authority and explicit complete-output non-claims",
    )
    check(
        crops.get("low232", {}).get("complete_native_product")
        == {"indices": 44551, "bands": 168, "palette_components": 578}
        and crops.get("painter231", {}).get("complete_native_product")
        == {"indices": 44515, "bands": 207, "palette_components": 737}
        and crops.get("flare236", {}).get("complete_native_product")
        == {"indices": 45860, "bands": 573, "palette_components": 578}
        and visual.get("native_pairs", {}).get(
            "low232-painter231", {}).get("product")
        == {"indices": 25579, "bands": 2367, "palette_components": 435}
        and visual.get("native_pairs", {}).get(
            "painter231-flare236", {}).get("product")
        == {"indices": 31492, "bands": 11980, "palette_components": 741},
        "historical complete-output non-claims remain pinned in provenance",
    )
    return state


def grade_maps_and_weather(check) -> None:
    blobs: dict[str, bytes] = {}
    for name, (path, expected_size, expected_hash) in MAPS.items():
        data = path.read_bytes()
        blobs[name] = data
        check(
            len(data) == expected_size and sha256(data) == expected_hash,
            f"retained {name} has its complete size and pinned SHA-256",
        )

    harness = ROOT / "noctis-harness"
    if str(harness) not in sys.path:
        sys.path.insert(0, str(harness))
    try:
        from brtl_oracle import Brtl
        import ns_spec
    except ImportError as error:
        check(False, f"independent multiple-sun oracles import safely: {error}")
        return

    system = ns_spec.System(*STAR)
    orient = system.p_orb_orient[8]
    scenario_chop = int(555 * orient)
    check(
        system.cls == 8
        and system.ray == 8.48799991607666
        and system.nop == 4
        and system.nob == 23
        and system.p_owner[3] == -1
        and system.p_type[3] == 10
        and system.p_owner[8] == 3
        and system.p_type[8] == 3
        and orient == 1.2217304763960306
        and scenario_chop == 678
        and scenario_chop % 4 + 1 == 3,
        "independent model reproduces ROTOR IGNE's genuine companion-owned DESERT moon",
    )

    surface = blobs["s_background"]
    clouds = blobs["objectschart"]
    for name, expected in NATIVE.items():
        longitude = expected["longitude"]
        pointer = LATITUDE * 360 + longitude
        cloud_pointer = pointer >> 1
        sample = surface[pointer]
        cloud = clouds[cloud_pointer]
        albedo = ((sample - cloud) // 4) * 8
        raw_rain = f32(min(cloud * 0.25, 5.0))

        rng = Brtl()
        rng.srand(LATITUDE * longitude)
        random100 = rng.random(100)
        scenario = 3
        if random100 <= 5:
            scenario = rng.random(4) + 1
        grlat = abs(LATITUDE - 60) * 3 // 2
        if albedo < 25:
            scenario = 1
        elif grlat > 75:
            scenario = 4
        elif grlat > 60 and rng.random(3) != 0:
            scenario = 4
        divisor_draw = 0
        divisor = 1
        if scenario == 3:
            divisor_draw = rng.random(4)
            divisor = divisor_draw + 1
        elif scenario == 4:
            divisor_draw = rng.random(3)
            divisor = divisor_draw + 2
        rain = f32(raw_rain / divisor)

        check(
            pointer == expected["surface_pointer"]
            and cloud_pointer == expected["cloud_pointer"]
            and sample == expected["surface_sample"]
            and cloud == expected["cloud"]
            and albedo == expected["albedo"],
            f"{name} independently recovers its companion-moon map samples and albedo",
        )
        check(
            random100 == expected["random100"]
            and scenario == 3
            and divisor_draw == expected["divisor_draw"]
            and divisor == expected["divisor"]
            and raw_rain == expected["raw_rain"]
            and rain == expected["rain"],
            f"{name} replays the full Borland scenario stream and exact binary32 rain",
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
                  f"{name} retains its exact authored landed resume state")
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
        crop = page_crop(page, expected["crop"])
        check(
            sha256(crop) == expected["crop_sha256"]
            and (min(crop), max(crop)) == expected["native_range"]
            and sum(value >= 120 for value in crop) == expected["bright_count"],
            f"{name} retains its exact secondary-source discriminator",
        )

    if set(pages) == set(NATIVE):
        check(
            max(page_crop(pages["low232"], NATIVE["low232"]["crop"])) == 124
            and max(page_crop(pages["painter231"], NATIVE["painter231"]["crop"])) == 116,
            "native below-2.0 core is brighter than the exact-2.0 flare-only core",
        )
        check(
            mismatch_count(pages["low232"], pages["painter231"]) == 27469
            and band_mismatch_count(pages["low232"], pages["painter231"]) == 2384
            and mismatch_count(pages["painter231"], pages["flare236"]) == 32964
            and band_mismatch_count(pages["painter231"], pages["flare236"]) == 12348,
            "native paired pages retain bounded complete-page non-claims",
        )
    if set(palettes) == set(NATIVE):
        check(
            mismatch_count(palettes["low232"], palettes["painter231"]) == 676
            and mismatch_count(palettes["painter231"], palettes["flare236"]) == 520,
            "native paired palettes retain explicit complete-palette non-claims",
        )
    return pages, palettes


def check_reproducible_current(check) -> None:
    try:
        mkcurrent = load_mkcurrent()
        rebuilt, system = mkcurrent.build(
            *STAR, 8, sync=3, secs=1344168020.0,
            charge=120, power=30000, draw_hud=0,
            angles=(-20.0, -30.0, 0.0),
        )
    except (AssertionError, OSError, ImportError) as error:
        check(False, f"tracked CURRENT builder runs safely: {error}")
        return
    check(len(rebuilt) == 385 and sha256(rebuilt) == CURRENT_SHA256,
          "tracked builder reproduces the exact native CURRENT input")
    check(
        system["cls"] == 8
        and system["ray"] == 8.48799991607666
        and system["nop"] == 4
        and system["nob"] == 23
        and system["owner"][3] == -1
        and system["ptype"][3] == 10
        and system["owner"][8] == 3
        and system["ptype"][8] == 3,
        "tracked generator independently reproduces the multiple-star hierarchy",
    )


def grade_products(
    directories: dict[str, Path],
    native_pages: dict[str, bytes],
    native_palettes: dict[str, tuple[int, ...]],
    provenance: dict[str, object],
    check,
) -> None:
    pages: dict[str, bytes] = {}
    palettes: dict[str, tuple[int, ...]] = {}
    matched = provenance.get("matched_product", {})
    stable_diagnostics = {
        "habitablemultiple-game-p-background-out.bin",
        "habitablemultiple-game-p-surfacemap-out.bin",
        "habitablemultiple-game-palette-out.bin",
        "habitablemultiple-game-render-state-out.bin",
        "habitablemultiple-game-s-background-out.bin",
        "habitablemultiple-game-sun-out.bin",
    }
    for name, directory in directories.items():
        expected = NATIVE[name]
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

        page = (directory / "habitablemultiple-game-page-out.bin").read_bytes()
        palette = struct.unpack(
            "<768i", (directory / "habitablemultiple-game-palette-out.bin").read_bytes())
        sun_data = (directory / "habitablemultiple-game-sun-out.bin").read_bytes()
        sun_i = struct.unpack("<32i", sun_data)
        sun_f = struct.unpack("<32f", sun_data)
        view = struct.unpack(
            "<39i", (directory / "habitablemultiple-game-vh-out.bin").read_bytes())
        pages[name] = page
        palettes[name] = palette
        check(
            view[:6] == (1327104, expected["product_y"], 1884160, -20, -30, 0),
            f"{name} product retains its exact landed source-camera pose",
        )
        check(
            sun_i[:6] == (1, 1, 3, 8, 1, 0)
            and sun_f[6] == expected["rain"]
            and sun_f[8:10] == (1009.3336181640625, 15.600000381469727)
            and sun_i[16:20] == expected["flare"]
            and sun_i[20:22] == (1, 0)
            and sun_f[22:24] == (8.48799991607666, 4174.10888671875),
            f"{name} product retains both daylight sources, weather, and flare admission",
        )
        check(
            sun_i[24:30] == (620, 284, 337, 36, 71, 201),
            f"{name} product retains the shared rotation and terminator state",
        )
        crop = page_crop(page, expected["crop"])
        native_crop = page_crop(native_pages[name], expected["crop"])
        check(
            sha256(crop) == expected["product_crop_sha256"]
            and (min(crop), max(crop)) == expected["product_range"]
            and sum(value >= 120 for value in crop) == expected["bright_count"],
            f"{name} product retains its exact secondary-source discriminator",
        )
        check(
            band_mismatch_count(native_crop, crop) == 0,
            f"{name} native/product source crop has 0 painter-family differences",
        )
        expected_provenance_hashes = matched.get(name, {}).get("hashes", {})
        check(
            expected_provenance_hashes == provenance_hashes,
            f"{name} historical product hashes remain pinned in provenance",
        )

    if set(pages) != set(NATIVE):
        return
    for name in NATIVE:
        print(
            f"INFO {name} current complete page/palette equality is not graded "
            f"({mismatch_count(native_pages[name], pages[name])} index, "
            f"{band_mismatch_count(native_pages[name], pages[name])} band, "
            f"{mismatch_count(native_palettes[name], palettes[name])} palette-component "
            "mismatches)"
        )
    for left, right in (("low232", "painter231"), ("painter231", "flare236")):
        print(
            f"INFO current product {left}/{right} complete-output equality is not graded "
            f"({mismatch_count(pages[left], pages[right])} index, "
            f"{band_mismatch_count(pages[left], pages[right])} band, "
            f"{mismatch_count(palettes[left], palettes[right])} palette-component "
            "mismatches)"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--low-product-directory", type=Path)
    parser.add_argument("--painter-product-directory", type=Path)
    parser.add_argument("--flare-product-directory", type=Path)
    args = parser.parse_args()
    supplied = (
        args.low_product_directory,
        args.painter_product_directory,
        args.flare_product_directory,
    )
    if any(path is not None for path in supplied) and not all(
            path is not None for path in supplied):
        parser.error("low, painter, and flare product directories must be supplied together")

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

    if all(path is not None for path in supplied) and set(native_pages) == set(NATIVE):
        assert args.low_product_directory is not None
        assert args.painter_product_directory is not None
        assert args.flare_product_directory is not None
        grade_products({
            "low232": args.low_product_directory.resolve(),
            "painter231": args.painter_product_directory.resolve(),
            "flare236": args.flare_product_directory.resolve(),
        }, native_pages, native_palettes, provenance, check)
    else:
        print("SKIP product comparison requires all three matched product directories")

    if errors:
        print(f"habitable multiple weather oracle: {len(errors)} failure(s)")
        return 1
    print("habitable multiple weather oracle: all requested checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
