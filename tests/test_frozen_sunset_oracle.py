"""Grade the exact frozen-world sunset/day-night boundary oracle.

The default mode is non-GUI and authenticates two exact-clock NIV+ indexed BMPs,
their landed resume states, RAM-derived provenance, and the exclusive terminator
end gate. Optional matched product directories add every exported-state hash,
exact diagnostics, a source-free crop, and a 25,800-pixel palette-band crop::

    python tests/test_frozen_sunset_oracle.py \
        --night-product-directory build/renderer-frozen-boundary-night204 \
        --day-product-directory build/renderer-frozen-boundary-day205
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct

from test_frozen_sunrise_oracle import (
    band_mismatch_count,
    decode_bmp,
    load_mkcurrent,
    mismatch_count,
    page_crop,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "gen" / "recon_w7b" / "out"
PROVENANCE = OUT / "frozen_sunset_boundary_8527_native.provenance.json"
GROUND = ROOT / "work" / "vhground.txt"
STAR = (2952848, -6448045, -840503)
SOURCE_CROP = (154, 92, 160, 94)
UPPER_SKY_CROP = (10, 10, 310, 96)
NO_SOURCE = bytes((64,) * 12)

NATIVE = {
    "night204": {
        "bmp": OUT / "frozen_sunset_night204_8527_native.shot.BMP",
        "surface": OUT / "frozen_sunset_night204_8527_native.SURFACE.BIN",
        "bmp_sha256": "ddcb170956d50411a0add56bef2a1b769ee5eee49707ae9fe9b396a88490a8a2",
        "surface_sha256": "8c5566a6fed964383428957209b7dbc5c83b7f6b2bc20a0f263750d1c2b91564",
        "page_sha256": "8709c41100d84ca9c2fad13146c53e3a95d9c29d5bf0317039d5684b5427a43f",
        "palette_sha256": "0b8946aab73ab92bb7485d513cd8178e8b5a9225e66e943cc9bcc8ba5cd823f7",
        "surface_state": (204, 60, 8, 8, 0, 0, 1645000.0, 1.0, 1641000.0, 0.0, 90.0),
    },
    "day205": {
        "bmp": OUT / "frozen_sunset_day205_8527_native.shot.BMP",
        "surface": OUT / "frozen_sunset_day205_8527_native.SURFACE.BIN",
        "bmp_sha256": "ba047f363e7a682a22896beb9c3b8e8fd8182d75c09c357f0fdef2ae2a8f1fd5",
        "surface_sha256": "6bb0d59cb2f062ed8f3d62f62bd6fdde0f578274f8f1fcc0163a8a08928ec55f",
        "page_sha256": "a6d80d26d9117aa9e2465bf9a6e2315ca27c6ec65aedb4dcd2d06eb1b2be9ea4",
        "palette_sha256": "cd1b3921fa3483937d12738e7f26238c1e38977fbacd734c116aaebd738fdf87",
        "surface_state": (205, 60, 8, 8, 0, 0, 1645000.0, 1.0, 1641000.0, 0.0, 90.0),
    },
}

PRODUCT_HASHES = {
    "night204": {
        "frozensun-game-local-out.bin": "6068d747b4ced0aca8a1d6b04dec4a1e3bc0ba21f19de565473ee57de5f24662",
        "frozensun-game-p-background-out.bin": "2adfe0da5862517f881bccb811c8c6cdef477beaedd184d5f0a359e9de296017",
        "frozensun-game-p-surfacemap-out.bin": "e7e2dcff542de95352682dc186432e98f0188084896773f1973276b0577d5305",
        "frozensun-game-page-out.bin": "9e7de4c05c7c87f96fe0f89fdf8b83738eb0b41c0490a0c39e15ad2c696fa384",
        "frozensun-game-palette-out.bin": "f2000e40ef6554f39caaf450ced9d338987ae51376898d6cd66e4913de76404a",
        "frozensun-game-render-state-out.bin": "85129fff180c897afc4462822857187249e28a9d59e2a20ff35d0a2cd0868efd",
        "frozensun-game-s-background-out.bin": "d043a2d604f110e5746b2875778ccc2f90f76c0e8056aa8d5dd0cca27501ed2c",
        "frozensun-game-sun-out.bin": "d4edd4ae98b2fb7497ca386fa2d2563e5ca49564dedc8fd49f6019e8b2047898",
        "frozensun-game-vh-out.bin": "6d54a2c3fc472f046571e9b3d84f9df30d8b23600ca90eaeac157a60fe2148bd",
    },
    "day205": {
        "frozensun-game-local-out.bin": "c2105ba1bfaf69d1e1ff1802b3b1e9cd6c586369d914ee9f797f9fb854c35a75",
        "frozensun-game-p-background-out.bin": "e0fccdb7f4a88dc267f30adb63d36154575279bcd318b2cadd338668f01e7ca3",
        "frozensun-game-p-surfacemap-out.bin": "e7e2dcff542de95352682dc186432e98f0188084896773f1973276b0577d5305",
        "frozensun-game-page-out.bin": "913cdf1a7af54c169fc72732649e638bd79d9b06c77e04b09f74e326378ae344",
        "frozensun-game-palette-out.bin": "22b0ddeda26fe9fca816f7ad718f5532289f0c2b0e29a05ba41155e3392eed44",
        "frozensun-game-render-state-out.bin": "85129fff180c897afc4462822857187249e28a9d59e2a20ff35d0a2cd0868efd",
        "frozensun-game-s-background-out.bin": "d043a2d604f110e5746b2875778ccc2f90f76c0e8056aa8d5dd0cca27501ed2c",
        "frozensun-game-sun-out.bin": "d3a84e6189b20fdc194c662a01b47e6f3a31247ec60570e49dfb486d8c1bb8bc",
        "frozensun-game-vh-out.bin": "51d636c63179134d8bd5bd8d3e0553569c67c9a3742d680177d11e2ce177d8d3",
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

PROVENANCE_SHA256 = "b8c31a9c41523199d026c5972315e90e24b8f3318fb84c2d510b158bc6911766"
CURRENT_SHA256 = "65a21c1a63f1c6b54595edb42d10c7ec13209c7b130c6a61ac6820cf4b70c165"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check_source_contract(check) -> None:
    source = GROUND.read_text(encoding="utf-8")
    check(all(fragment in source for fragment in (
        "[VHGNDtermend] = A; [GRSKnightzone] = 0;",
        "A = [VHGNDlon]; ? A < [VHGNDtermstart] -> VHGND night ready;",
        "? A >= [VHGNDtermend] -> VHGND night ready;",
        "[GRSKnightzone] = 1;",
        "A = [GRSKnightzone]; ? A != 0 -> VHGND local primary done;",
    )), "surface renderer retains the exclusive terminator-end and night-source gates")


def check_provenance(check) -> dict[str, object]:
    data = PROVENANCE.read_bytes()
    check(
        sha256(data.replace(b"\r\n", b"\n")) == PROVENANCE_SHA256,
        "frozen-sunset provenance has its pinned normalized SHA-256",
    )
    try:
        state = json.loads(data)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        check(False, f"frozen-sunset provenance decodes safely: {error}")
        return {}

    system = state.get("system", {})
    native = state.get("native_capture", {})
    ram = state.get("native_ram_contract", {})
    rotation = ram.get("rotation_arrays", {}).get("both", {})
    solar = ram.get("solar_globals", {})
    visual = state.get("visual_contract", {})
    check(
        system.get("coordinates") == list(STAR)
        and system.get("star_class") == 1
        and system.get("target_body") == 9
        and system.get("target_owner") == -1
        and system.get("target_type") == 7
        and system.get("atmosphere") is False,
        "provenance identifies the same airless class-1/type-7 frozen world",
    )
    check(
        native.get("initial_clock") == 1344638526.0
        and native.get("captured_clock") == 1344638527.0
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
    check(rotation == {
        "rtperiod": 866,
        "raw_rotation": -4,
        "normalized_rotation": 356,
        "term_start": 75,
        "term_end": 205,
    }, "native arrays retain period, wrapped rotation, and the 75..205 night interval")
    check(
        solar.get("night204", {}).get("crepzone") == 1
        and solar.get("night204", {}).get("nightzone") == 1
        and solar.get("night204", {}).get("sun_x_factor") == -1
        and solar.get("night204", {}).get("exposure") == 0.7825999855995178
        and solar.get("day205", {}).get("crepzone") == 0
        and solar.get("day205", {}).get("nightzone") == 0
        and solar.get("day205", {}).get("sun_x_factor") == -1
        and solar.get("day205", {}).get("exposure") == 0.0,
        "native solar globals leave night at the exclusive longitude-205 boundary",
    )
    check(
        visual.get("source_crop") == list(SOURCE_CROP)
        and visual.get("upper_sky_band_crop") == list(UPPER_SKY_CROP)
        and visual.get("upper_sky_band_pixels") == 25800,
        "provenance bounds the exact source and upper-sky palette-band contracts",
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
        check(page_crop(page, SOURCE_CROP) == NO_SOURCE,
              f"{name} retains the exact source-free 12-index horizon crop")

    if set(pages) == set(NATIVE):
        check(
            mismatch_count(pages["night204"], pages["day205"]) == 27615
            and band_mismatch_count(pages["night204"], pages["day205"]) == 18,
            "native paired pages retain the bounded complete-page non-claim",
        )
    if set(palettes) == set(NATIVE):
        night = palettes["night204"]
        day = palettes["day205"]
        check(
            mismatch_count(night, day) == 63
            and night[64 * 3:128 * 3] == day[64 * 3:128 * 3],
            "native palette differences spare the complete source band",
        )
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
    night_directory: Path,
    day_directory: Path,
    native_pages: dict[str, bytes],
    native_palettes: dict[str, tuple[int, ...]],
    provenance: dict[str, object],
    check,
) -> None:
    directories = {"night204": night_directory.resolve(), "day205": day_directory.resolve()}
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
        check(page_crop(page, SOURCE_CROP) == NO_SOURCE,
              f"{name} product matches the native source-free horizon crop")
        native_crop = page_crop(native_pages[name], UPPER_SKY_CROP)
        product_crop = page_crop(page, UPPER_SKY_CROP)
        check(
            len(native_crop) == 25800
            and band_mismatch_count(native_crop, product_crop) == 0,
            f"{name} product retains all 25,800 native upper-sky palette bands",
        )
        check(matched.get(name, {}).get("hashes", {}) == expected_hashes,
              f"{name} product hashes agree with retained provenance")

    if set(pages) != set(NATIVE):
        return

    night_sun = sun_states["night204"]
    day_sun = sun_states["day205"]
    night_float = sun_floats["night204"]
    day_float = sun_floats["day205"]
    check(
        night_sun[:6] == (1, 1, 7, 1, 0, 1)
        and day_sun[:6] == (1, 1, 7, 1, 0, 0),
        "product diagnostics leave night at the exclusive longitude-205 boundary",
    )
    check(
        night_float[6] == day_float[6] == 0.0
        and night_float[7] == 0.7825999855995178
        and day_float[7] == 0.0
        and night_float[8] == day_float[8] == 34167.40234375,
        "product diagnostics match native dry weather, exposure, and solar distance",
    )
    check(
        night_float[9] == 0.0
        and day_float[9] == 21.878999710083008
        and night_sun[16:24] == day_sun[16:24] == (0,) * 8,
        "night suppression and the behind-camera day source both remain unprojected",
    )
    check(
        night_sun[24:32] == (866, 356, 45, 40, 75, 205, 1, -1)
        and day_sun[24:32] == (866, 356, 45, 40, 75, 205, 0, -1),
        "product matches the native single-source sunset state exactly",
    )
    check(
        page_crop(pages["night204"], SOURCE_CROP) == NO_SOURCE
        and page_crop(pages["day205"], SOURCE_CROP) == NO_SOURCE,
        "native and product share the exact source-free edge discriminator",
    )
    check(
        mismatch_count(palettes["night204"], palettes["day205"]) == 458
        and palettes["night204"][64 * 3:128 * 3]
        == palettes["day205"][64 * 3:128 * 3],
        "product palette differences spare the complete source band",
    )
    check(
        mismatch_count(native_pages["night204"], pages["night204"]) == 27264
        and band_mismatch_count(native_pages["night204"], pages["night204"]) == 636
        and mismatch_count(native_palettes["night204"], palettes["night204"]) == 652,
        "night product comparison retains its explicit page/palette non-claim",
    )
    check(
        mismatch_count(native_pages["day205"], pages["day205"]) == 27883
        and band_mismatch_count(native_pages["day205"], pages["day205"]) == 645
        and mismatch_count(native_palettes["day205"], palettes["day205"]) == 736,
        "day product comparison retains its explicit page/palette non-claim",
    )
    check(
        mismatch_count(pages["night204"], pages["day205"]) == 25909
        and band_mismatch_count(pages["night204"], pages["day205"]) == 29,
        "product paired pages retain the bounded complete-page non-claim",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--night-product-directory", type=Path)
    parser.add_argument("--day-product-directory", type=Path)
    args = parser.parse_args()
    if (args.night_product_directory is None) != (args.day_product_directory is None):
        parser.error("night and day product directories must be supplied together")

    errors: list[str] = []

    def check(condition: bool, message: str) -> None:
        print("PASS" if condition else "FAIL", message)
        if not condition:
            errors.append(message)

    check_source_contract(check)
    provenance = check_provenance(check)
    native_pages, native_palettes = grade_native(check)
    check_reproducible_current(check)

    if args.night_product_directory is not None and set(native_pages) == set(NATIVE):
        assert args.day_product_directory is not None
        grade_product_pair(
            args.night_product_directory,
            args.day_product_directory,
            native_pages,
            native_palettes,
            provenance,
            check,
        )
    else:
        print("SKIP product comparison requires both matched product directories")

    if errors:
        print(f"frozen sunset oracle: {len(errors)} failure(s)")
        return 1
    print("frozen sunset oracle: all requested checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
