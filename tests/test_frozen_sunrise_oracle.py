"""Grade the exact frozen-world sunrise/day-night boundary oracle.

The default mode is non-GUI and authenticates two exact-clock NIV+ indexed BMPs,
their landed resume states, retained RAM-derived provenance, and the shipping
terminator/source-order implementation.  Optional matched product directories
add all exported-state hashes, exact diagnostics, and the native/product
12-index horizon-source discriminator::

    python tests/test_frozen_sunrise_oracle.py \
        --day-product-directory build/renderer-frozen-boundary-day74 \
        --night-product-directory build/renderer-frozen-boundary-night75
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "gen" / "recon_w7b" / "out"
DAY_BMP = OUT / "frozen_sunrise_day74_8527_native.shot.BMP"
NIGHT_BMP = OUT / "frozen_sunrise_night75_8527_native.shot.BMP"
DAY_SURFACE = OUT / "frozen_sunrise_day74_8527_native.SURFACE.BIN"
NIGHT_SURFACE = OUT / "frozen_sunrise_night75_8527_native.SURFACE.BIN"
PROVENANCE = OUT / "frozen_sunrise_boundary_8527_native.provenance.json"
MKCURRENT = ROOT / "tests" / "gen" / "recon_w7b" / "mkcurrent.py"
GROUND = ROOT / "work" / "vhground.txt"

STAR = (2952848, -6448045, -840503)
CLOCK = 1344638527
SOURCE_CROP = (154, 92, 160, 94)
DAY_SOURCE = bytes((64, 66, 70, 70, 66, 64, 67, 78, 90, 90, 78, 67))
NIGHT_SOURCE = bytes((64,) * 12)

NATIVE = {
    "day74": {
        "bmp": DAY_BMP,
        "surface": DAY_SURFACE,
        "bmp_sha256": "8710927009b7c3d8f9c2130e97bd070197c49c346a8a79a3a8570ad52c40cbd7",
        "surface_sha256": "17d80bf1edafcfc95ebc37d39e2a8c1df8b109b23543a6ca9f16cd8f475ad1f2",
        "page_sha256": "7a4e4acf25f3187268a7fbdfbb3fc57583599db1afd5c651ee0d888bb2610df7",
        "palette_sha256": "970c8193f375a479f74da53f373dc1e25a264036b8376c1ea16698c0e36274c9",
        "surface_state": (74, 60, 8, 8, 0, 0, 1645000.0, 1.0, 1641000.0, 0.0, 90.0),
        "source": DAY_SOURCE,
    },
    "night75": {
        "bmp": NIGHT_BMP,
        "surface": NIGHT_SURFACE,
        "bmp_sha256": "2f25d7b8d5cfc76909ebdd0aeea5fd834db0fd83ef067531969f4558861dbc31",
        "surface_sha256": "917b085650350bf18553060494554431cfe07afb18a12dd0254348e4d1496afc",
        "page_sha256": "e212e44eabc6291d7334f8d704d3c9e9521170d820e8653a0fc915e96ce67742",
        "palette_sha256": "0b8946aab73ab92bb7485d513cd8178e8b5a9225e66e943cc9bcc8ba5cd823f7",
        "surface_state": (75, 60, 8, 8, 0, 0, 1645000.0, 1.0, 1641000.0, 0.0, 90.0),
        "source": NIGHT_SOURCE,
    },
}

PRODUCT_HASHES = {
    "day74": {
        "frozensun-game-local-out.bin": "746e01efa7e5359a4662f1c5ce183c5431f80a336fff1918b7d13a56b9b51604",
        "frozensun-game-p-background-out.bin": "68f9df0efa4d17b63d021150e90157829f354b633627e757b935a0f22739bf54",
        "frozensun-game-p-surfacemap-out.bin": "e7e2dcff542de95352682dc186432e98f0188084896773f1973276b0577d5305",
        "frozensun-game-page-out.bin": "e1763f06ddcc00e3b2c75431dc5b40c9d3a5eb9c9418f29af6d67d31b6c65d4c",
        "frozensun-game-palette-out.bin": "17df64bbe8c296bd0612bbcd1f168503ead4ee5b59def7c566b0eb52335e8579",
        "frozensun-game-render-state-out.bin": "85129fff180c897afc4462822857187249e28a9d59e2a20ff35d0a2cd0868efd",
        "frozensun-game-s-background-out.bin": "d043a2d604f110e5746b2875778ccc2f90f76c0e8056aa8d5dd0cca27501ed2c",
        "frozensun-game-sun-out.bin": "f8d341a22c28e1679c22bfb39a66b87785ede0bd9ab4d348646fcf76e126432f",
        "frozensun-game-vh-out.bin": "bc47c3621a1bf95dfbfcf364bc45252d44b605da79d542320dc7d32f4a18c0a4",
    },
    "night75": {
        "frozensun-game-local-out.bin": "2a9edbacb343791ac62ba70d9ffe28faf4e306a44c8ba0c8d3f2f3f76faca5ae",
        "frozensun-game-p-background-out.bin": "a016b76152fa28045bbc3963c0ab7b6d0c889b97e06d12e32442a699577169c6",
        "frozensun-game-p-surfacemap-out.bin": "e7e2dcff542de95352682dc186432e98f0188084896773f1973276b0577d5305",
        "frozensun-game-page-out.bin": "a09986fead54318ae5943dfe2f3451d5dbca39a75ba22f0e7f607e64e5977acf",
        "frozensun-game-palette-out.bin": "f2000e40ef6554f39caaf450ced9d338987ae51376898d6cd66e4913de76404a",
        "frozensun-game-render-state-out.bin": "85129fff180c897afc4462822857187249e28a9d59e2a20ff35d0a2cd0868efd",
        "frozensun-game-s-background-out.bin": "d043a2d604f110e5746b2875778ccc2f90f76c0e8056aa8d5dd0cca27501ed2c",
        "frozensun-game-sun-out.bin": "b83882935a5989e7ecac32c25223c5092c1b04730eaa1b576c6c61b78a71e9a0",
        "frozensun-game-vh-out.bin": "4afc331f209858d7523f035e22178221a0222d417b32b907d219967a50558e5c",
    },
}

PRODUCT_SIZES = {
    "frozensun-game-local-out.bin": 176,
    "frozensun-game-p-background-out.bin": 65552,
    "frozensun-game-p-surfacemap-out.bin": 40000,
    "frozensun-game-page-out.bin": 64000,
    "frozensun-game-palette-out.bin": 3072,
    "frozensun-game-render-state-out.bin": 24,
    "frozensun-game-s-background-out.bin": 64800,
    "frozensun-game-sun-out.bin": 128,
    "frozensun-game-vh-out.bin": 156,
}

PROVENANCE_SHA256 = "a72bde12607b4d43aa81bb5bdf43183b6d45728369a7aa7ea0e76997ee750fdf"
CURRENT_SHA256 = "65a21c1a63f1c6b54595edb42d10c7ec13209c7b130c6a61ac6820cf4b70c165"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decode_bmp(path: Path) -> tuple[bytes, tuple[int, ...]]:
    data = path.read_bytes()
    if len(data) < 1078 or data[:2] != b"BM":
        raise AssertionError(f"{path}: not a complete indexed BMP")
    file_size = struct.unpack_from("<I", data, 2)[0]
    pixel_offset = struct.unpack_from("<I", data, 10)[0]
    dib_size, width, height, planes, depth, compression = struct.unpack_from(
        "<IiiHHI", data, 14
    )
    if file_size != 116326:
        raise AssertionError(f"{path}: unexpected historical header size {file_size}")
    if (dib_size, width, abs(height), planes, depth, compression, pixel_offset) != (
        40, 320, 200, 1, 8, 0, 1078
    ):
        raise AssertionError(f"{path}: unexpected indexed BMP geometry")

    table = data[14 + dib_size:pixel_offset]
    if len(table) != 1024:
        raise AssertionError(f"{path}: incomplete 256-entry palette")
    palette: list[int] = []
    for index in range(256):
        blue, green, red, reserved = table[index * 4:index * 4 + 4]
        if reserved != 0 or any(value & 3 for value in (red, green, blue)):
            raise AssertionError(f"{path}: palette entry {index} is not exact six-bit BGR0")
        palette.extend((red >> 2, green >> 2, blue >> 2))

    stride = (width + 3) & ~3
    if pixel_offset + stride * abs(height) != len(data):
        raise AssertionError(f"{path}: incomplete pixel extent")
    rows = [
        data[pixel_offset + row * stride:pixel_offset + row * stride + width]
        for row in range(abs(height))
    ]
    if height > 0:
        rows.reverse()
    return b"".join(rows), tuple(palette)


def page_crop(page: bytes, rectangle: tuple[int, int, int, int]) -> bytes:
    x0, y0, x1, y1 = rectangle
    return b"".join(page[y * 320 + x0:y * 320 + x1] for y in range(y0, y1))


def mismatch_count(left: bytes | tuple[int, ...], right: bytes | tuple[int, ...]) -> int:
    return sum(a != b for a, b in zip(left, right))


def band_mismatch_count(left: bytes, right: bytes) -> int:
    return sum((a & 0xC0) != (b & 0xC0) for a, b in zip(left, right))


def load_mkcurrent():
    spec = importlib.util.spec_from_file_location("frozen_boundary_mkcurrent", MKCURRENT)
    if spec is None or spec.loader is None:
        raise AssertionError("cannot load tracked CURRENT builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_source_contract(check) -> None:
    source = GROUND.read_text(encoding="utf-8")
    check(all(fragment in source for fragment in (
        "A = 89; A - [FI]; A + [VHGNDrotation]; A % 360;",
        "[VHGNDplwp] = A; A + 35;",
        "[VHGNDtermstart] = A; A + 130;",
        "[VHGNDtermend] = A; [GRSKnightzone] = 0;",
        "A = [VHGNDlon]; ? A < [VHGNDtermstart] -> VHGND night ready;",
        "? A >= [VHGNDtermend] -> VHGND night ready;",
        "[GRSKnightzone] = 1;",
        "[VHGNDcrep] = A;",
        "[GRSKexposure] = [FS0];",
    )), "surface renderer retains the historical inclusive terminator calculation")
    check(
        "A = [GRSKnightzone]; ? A != 0 -> VHGND local primary done;" in source
        and "A = [GRSKrainy]; ? A '>= 40200000h -> VHGND local primary done;" in source,
        "night and heavy weather suppress the local primary before terrain",
    )


def check_provenance(check) -> dict[str, object]:
    data = PROVENANCE.read_bytes()
    check(
        sha256(data.replace(b"\r\n", b"\n")) == PROVENANCE_SHA256,
        "frozen-boundary provenance has its pinned normalized SHA-256",
    )
    try:
        state = json.loads(data)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        check(False, f"frozen-boundary provenance decodes safely: {error}")
        return {}

    system = state.get("system", {})
    native = state.get("native_capture", {})
    ram = state.get("native_ram_contract", {})
    rotation = ram.get("rotation_arrays", {})
    solar = ram.get("solar_globals", {})
    derivation = ram.get("terminator_derivation", {})
    check(
        system.get("coordinates") == list(STAR)
        and system.get("star_class") == 1
        and system.get("target_body") == 9
        and system.get("target_owner") == -1
        and system.get("target_type") == 7
        and system.get("atmosphere") is False,
        "provenance identifies the airless class-1/type-7 frozen world",
    )
    check(
        native.get("initial_clock") == 1344638526.0
        and native.get("captured_clock") == float(CLOCK)
        and native.get("snapshot_wait_seconds") == 5
        and native.get("sync") == 3
        and native.get("target_reached") == 1,
        "both native captures retain the exact settled integer clock and target state",
    )
    check(
        ram.get("continuity", {}).get("both", {}).get("settled_player")
        == [1645000.0, 0.0, 1641000.0]
        and ram.get("weather", {}).get("both", {}).get("rainy") == 0.0,
        "native RAM retains the landed camera and dry weather state",
    )
    values = rotation.get("both", {})
    check(
        values == {
            "rtperiod": 866,
            "raw_rotation": -4,
            "normalized_rotation": 356,
            "term_start": 75,
            "term_end": 205,
        },
        "native arrays retain period, wrapped rotation, and the 75..205 night interval",
    )
    check(
        derivation.get("viewpoint") == 45
        and derivation.get("plwp") == 40
        and (89 - 45 + (-4)) % 360 == 40
        and (40 + 35) % 360 == 75
        and (75 + 130) % 360 == 205,
        "native array values reconstruct the exact viewpoint and terminators",
    )
    check(
        solar.get("day74", {}).get("crepzone") == 1
        and solar.get("day74", {}).get("nightzone") == 0
        and solar.get("day74", {}).get("exposure") == 0.7825999855995178
        and solar.get("night75", {}).get("crepzone") == 0
        and solar.get("night75", {}).get("nightzone") == 1
        and solar.get("night75", {}).get("exposure") == 0.0,
        "native solar globals cross from exposed day at 74 to night exactly at 75",
    )
    check(
        solar.get("day74", {}).get("primary_distance") == 34167.40234375
        and solar.get("night75", {}).get("primary_distance") == 34167.40234375
        and solar.get("day74", {}).get("primary_ray") == 21.878999710083008,
        "paired native RAM keeps the same live primary distance and ray",
    )
    return state


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
        crop = page_crop(page, SOURCE_CROP)
        check(crop == expected["source"],
              f"{name} retains the exact 12-index horizon-source crop")

    if set(pages) == set(NATIVE):
        day = pages["day74"]
        night = pages["night75"]
        check(
            sum(value != 64 for value in page_crop(day, SOURCE_CROP)) == 10
            and sum(value != 64 for value in page_crop(night, SOURCE_CROP)) == 0,
            "native longitude 74 exposes ten source-core pixels and 75 exposes none",
        )
        check(
            mismatch_count(day, night) == 27618
            and band_mismatch_count(day, night) == 16,
            "native paired pages retain the bounded complete-page non-claim",
        )
    if set(palettes) == set(NATIVE):
        day_band = palettes["day74"][64 * 3:128 * 3]
        night_band = palettes["night75"][64 * 3:128 * 3]
        check(day_band == night_band,
              "native day and night retain the same complete source palette band")
    return pages, palettes


def check_reproducible_current(check) -> None:
    try:
        mkcurrent = load_mkcurrent()
        rebuilt, system = mkcurrent.build(
            *STAR, 9, sync=3, secs=1344638526.0,
            charge=120, power=30000, draw_hud=0,
        )
    except (AssertionError, OSError, ImportError) as error:
        check(False, f"tracked CURRENT builder runs safely: {error}")
        return
    check(len(rebuilt) == 385 and sha256(rebuilt) == CURRENT_SHA256,
          "tracked builder reproduces the exact native CURRENT input")
    check(
        system["cls"] == 1
        and system["ray"] == 21.878999710083008
        and system["owner"][9] == -1
        and system["ptype"][9] == 7,
        "tracked generator independently reproduces the frozen-world hierarchy",
    )


def grade_product_pair(
    day_directory: Path,
    night_directory: Path,
    native_pages: dict[str, bytes],
    native_palettes: dict[str, tuple[int, ...]],
    provenance: dict[str, object],
    check,
) -> None:
    directories = {"day74": day_directory.resolve(), "night75": night_directory.resolve()}
    pages: dict[str, bytes] = {}
    palettes: dict[str, tuple[int, ...]] = {}
    sun_states: dict[str, tuple[int, ...]] = {}
    sun_floats: dict[str, tuple[float, ...]] = {}

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

        page = (directory / "frozensun-game-page-out.bin").read_bytes()
        palette_data = (directory / "frozensun-game-palette-out.bin").read_bytes()
        sun_data = (directory / "frozensun-game-sun-out.bin").read_bytes()
        view_data = (directory / "frozensun-game-vh-out.bin").read_bytes()
        pages[name] = page
        palettes[name] = struct.unpack("<768I", palette_data)
        sun_states[name] = struct.unpack("<32i", sun_data)
        sun_floats[name] = struct.unpack("<32f", sun_data)
        view = struct.unpack("<39i", view_data)
        check(view[:5] == (1645000, -600, 1641000, 0, 90),
              f"{name} product retains the exact settled landed camera")
        check(page_crop(page, SOURCE_CROP) == page_crop(native_pages[name], SOURCE_CROP),
              f"{name} product exactly matches the native 12-index source crop")
        expected_provenance_hashes = matched.get(name, {}).get("hashes", {})
        check(expected_provenance_hashes == expected_hashes,
              f"{name} product hashes agree with retained provenance")

    if set(pages) != set(NATIVE):
        return

    day_sun = sun_states["day74"]
    night_sun = sun_states["night75"]
    day_float = sun_floats["day74"]
    night_float = sun_floats["night75"]
    check(
        day_sun[:6] == (1, 1, 7, 1, 0, 0)
        and night_sun[:6] == (1, 1, 7, 1, 0, 1),
        "product diagnostics cross from the same airless frozen world into night",
    )
    check(
        day_float[6] == night_float[6] == 0.0
        and day_float[7] == 0.7825999855995178
        and night_float[7] == 0.0
        and day_float[8] == night_float[8] == 34167.40234375,
        "product diagnostics match native dry weather, exposure, and solar distance",
    )
    check(
        day_sun[16:20] == (1, 161, 99, 71)
        and night_sun[16:20] == (0, 0, 0, 0),
        "product admits the horizon source at 74 and suppresses it at night 75",
    )
    check(
        day_sun[20:24] == night_sun[20:24] == (0, 0, 0, 0)
        and day_sun[24:32] == (866, 356, 45, 40, 75, 205, 1, 1)
        and night_sun[24:32] == (866, 356, 45, 40, 75, 205, 0, 1),
        "product matches the native single-source terminator state exactly",
    )
    check(
        page_crop(pages["day74"], SOURCE_CROP) == DAY_SOURCE
        and page_crop(pages["night75"], SOURCE_CROP) == NIGHT_SOURCE,
        "native and product share the exact ten-pixel day/zero-pixel night discriminator",
    )
    check(
        palettes["day74"][64 * 3:128 * 3] == palettes["night75"][64 * 3:128 * 3],
        "product day and night retain the same complete source palette band",
    )
    check(
        mismatch_count(native_pages["day74"], pages["day74"]) == 27626
        and band_mismatch_count(native_pages["day74"], pages["day74"]) == 640
        and mismatch_count(native_palettes["day74"], palettes["day74"]) == 730,
        "day product comparison retains its explicit page/palette non-claim",
    )
    check(
        mismatch_count(native_pages["night75"], pages["night75"]) == 28155
        and band_mismatch_count(native_pages["night75"], pages["night75"]) == 631
        and mismatch_count(native_palettes["night75"], palettes["night75"]) == 652,
        "night product comparison retains its explicit page/palette non-claim",
    )
    check(
        mismatch_count(pages["day74"], pages["night75"]) == 26707
        and band_mismatch_count(pages["day74"], pages["night75"]) == 37,
        "product paired pages retain the bounded complete-page non-claim",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--day-product-directory", type=Path)
    parser.add_argument("--night-product-directory", type=Path)
    args = parser.parse_args()
    if (args.day_product_directory is None) != (args.night_product_directory is None):
        parser.error("day and night product directories must be supplied together")

    errors: list[str] = []

    def check(condition: bool, message: str) -> None:
        print("PASS" if condition else "FAIL", message)
        if not condition:
            errors.append(message)

    check_source_contract(check)
    provenance = check_provenance(check)
    native_pages, native_palettes = grade_native(check)
    check_reproducible_current(check)

    if args.day_product_directory is not None and set(native_pages) == set(NATIVE):
        assert args.night_product_directory is not None
        grade_product_pair(
            args.day_product_directory,
            args.night_product_directory,
            native_pages,
            native_palettes,
            provenance,
            check,
        )
    else:
        print("SKIP product comparison requires both matched product directories")

    if errors:
        print(f"frozen sunrise oracle: {len(errors)} failure(s)")
        return 1
    print("frozen sunrise oracle: all requested checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
