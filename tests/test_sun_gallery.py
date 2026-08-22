"""Grade a retained native surface-sun frame against product diagnostics.

The default mode is non-GUI: it validates the pinned NIV+ BMP oracle and the
shipping diagnostic/export contracts.  A hosted Windows capture supplies the
three product files for the exact page, palette, and flare-state comparison::

    python tests/test_sun_gallery.py --case hab-sun270 \
        --product-directory build/sun-gallery
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import struct


ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / "work" / "vhgame.txt"
CAPTURE = ROOT / "tools" / "capture_noctis_scenes.ps1"
PRIVATE_RUNNER = ROOT / "tools" / "run_hidden_noctis.py"
WORKFLOW = ROOT / ".github" / "workflows" / "windows-release.yml"

CASES = {
    "hab-sun270": {
        "scene": "habitable",
        "oracle": ROOT / "tests" / "gen" / "recon_w7b" / "out"
        / "hab_sun270_pinned_oracle.shot.BMP",
        "bmp_sha256": "c08cdb6f74f82c83170848e0071e2f7c0c82cfb35d20d097a8db7409fcf76d84",
        "page_sha256": "9e563cff6b6703f382ad15f353da71eaad8e087eba79b3b08ae757e5a45d3d8b",
        "palette_sha256": "c874d98235a9649a4e468d7f8b35f19cea923bdb72d550590ec1097b402fb7ee",
        "center": (161, 130),
    }
}


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
    # The retained Borland capture preserves its historical stale bfSize/image
    # size fields.  Its dimensions, pixel offset, actual extent, and whole-file
    # hash are authoritative; do not rewrite the source artifact to normalize it.
    if file_size != 116326:
        raise AssertionError(f"{path}: unexpected historical header size {file_size}")
    if (dib_size, width, abs(height), planes, depth, compression, pixel_offset) != (
        40,
        320,
        200,
        1,
        8,
        0,
        1078,
    ):
        raise AssertionError(
            f"{path}: expected 320x200 uncompressed 8-bit BMP, got "
            f"dib={dib_size} size={width}x{height} planes={planes} "
            f"depth={depth} compression={compression} offset={pixel_offset}"
        )

    table = data[14 + dib_size : pixel_offset]
    if len(table) != 1024:
        raise AssertionError(f"{path}: expected 256-entry palette, got {len(table)} bytes")
    palette: list[int] = []
    for index in range(256):
        blue, green, red, reserved = table[index * 4 : index * 4 + 4]
        if reserved != 0 or any(component & 3 for component in (red, green, blue)):
            raise AssertionError(
                f"{path}: palette entry {index} is not an exact six-bit BGR0 value"
            )
        palette.extend((red >> 2, green >> 2, blue >> 2))

    stride = (width + 3) & ~3
    end = pixel_offset + stride * abs(height)
    if end != len(data):
        raise AssertionError(f"{path}: pixel extent {end} != file size {len(data)}")
    rows = [
        data[pixel_offset + row * stride : pixel_offset + row * stride + width]
        for row in range(abs(height))
    ]
    if height > 0:
        rows.reverse()
    return b"".join(rows), tuple(palette)


def mismatch_summary(expected: bytes, actual: bytes, width: int = 320) -> str:
    mismatches = [index for index, pair in enumerate(zip(expected, actual)) if pair[0] != pair[1]]
    if not mismatches:
        return "0 mismatches"
    xs = [index % width for index in mismatches]
    ys = [index // width for index in mismatches]
    first = mismatches[0]
    return (
        f"{len(mismatches)} mismatches in ({min(xs)},{min(ys)}).."
        f"({max(xs)},{max(ys)}); first offset {first}: "
        f"native={expected[first]} product={actual[first]}"
    )


def check_source_contract(check) -> None:
    game = GAME.read_text(encoding="utf-8")
    capture = CAPTURE.read_text(encoding="utf-8")
    private_runner = PRIVATE_RUNNER.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    check("vhgpagename = { game-page-out.bin };" in game,
          "game declares a separate packed-page diagnostic")
    check("[SPpreg] = RGADP; [SPpn] = NPIX; => SP packpage;" in game and
          "[Block Pointer] = sppack; [Block Size] = 64000; isocall;" in game and
          "[File Size] = 64000; isocall;" in game,
          "sentinel packs and size-pins all 64,000 final page indices")
    check("[Block Pointer] = vhgsun; [Block Size] = 128; isocall;" in game and
          "[Block Pointer] = curpal6; [Block Size] = 3072; isocall;" in game,
          "existing sun and six-bit palette contracts remain intact")
    check("VHGsentinelquit" in game and
          "[VHGesc] = 1; [Quit Now] = YES;" in game,
          "explicit quit token exits only after complete sentinel diagnostics")
    check("'game-page-out.bin' = 64000" in capture and
          "'game-sun-out.bin' = 128" in capture and
          "'game-palette-out.bin' = 3072" in capture and
          "$Spec.Name, $entry.Key" in capture,
          "diagnostic capture validates and exports scene-qualified product files")
    check("windows_hidden_process.run" in private_runner and
          "private Noctis sentinel run exited cleanly" in private_runner and
          "run_hidden_noctis.py" in capture and "quit" in capture,
          "diagnostic-only product execution uses a private inactive desktop")
    check(all(fragment in workflow for fragment in (
              "-Scene habitable",
              "-Longitude 270",
              "-ViewPitch -44",
              "-ClockSeconds 1344638527",
              "-DiagnosticOnly",
              "--case hab-sun270",
              "--product-directory build\\sun-gallery",
          )),
          "hosted Windows package gate executes the pinned product comparison")


def grade_product(case: dict[str, object], directory: Path, oracle_page: bytes,
                  oracle_palette: tuple[int, ...], check) -> None:
    scene = str(case["scene"])
    page_path = directory / f"{scene}-game-page-out.bin"
    palette_path = directory / f"{scene}-game-palette-out.bin"
    sun_path = directory / f"{scene}-game-sun-out.bin"

    for path, size in ((page_path, 64000), (palette_path, 3072), (sun_path, 128)):
        check(path.is_file() and path.stat().st_size == size,
              f"product emitted {path.name} at exactly {size} bytes")
    if not all(path.is_file() for path in (page_path, palette_path, sun_path)):
        return

    page = page_path.read_bytes()
    if len(page) == len(oracle_page):
        summary = mismatch_summary(oracle_page, page)
        check(page == oracle_page,
              f"complete indexed product page matches native ({summary})")

    palette_data = palette_path.read_bytes()
    if len(palette_data) == 3072:
        palette = struct.unpack("<768I", palette_data)
        differences = [
            index for index, pair in enumerate(zip(oracle_palette, palette))
            if pair[0] != pair[1]
        ]
        detail = "0 mismatches" if not differences else (
            f"{len(differences)} mismatches; first component {differences[0]}: "
            f"native={oracle_palette[differences[0]]} "
            f"product={palette[differences[0]]}"
        )
        check(palette == oracle_palette,
              f"all 768 six-bit product palette components match native ({detail})")

    sun_data = sun_path.read_bytes()
    if len(sun_data) == 128:
        sun = struct.unpack("<32i", sun_data)
        floats = struct.unpack("<32f", sun_data)
        cx, cy = case["center"]
        check(sun[0] == 1 and sun[1] == 1 and sun[2] == 3,
              "product diagnostic identifies landed type-3 rendering")
        check(sun[4] == 1 and sun[5] == 0 and floats[6] == 0.0,
              "product diagnostic retains clear daytime atmosphere")
        check(sun[16] == 1,
              "product diagnostic confirms the source flare gate is active")
        check(abs(sun[17] - cx) <= 1 and abs(sun[18] - cy) <= 1,
              f"product flare centre {sun[17]},{sun[18]} aligns with native {cx},{cy}")
        check(abs(floats[7] - 35.9996) < 0.01 and
              abs(floats[8] - 243.633) < 0.01,
              "product retains the pinned native exposure and live solar distance")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=sorted(CASES), default="hab-sun270")
    parser.add_argument("--product-directory", type=Path)
    args = parser.parse_args()

    errors: list[str] = []

    def check(condition: bool, message: str) -> None:
        print("PASS" if condition else "FAIL", message)
        if not condition:
            errors.append(message)

    case = CASES[args.case]
    oracle = case["oracle"]
    assert isinstance(oracle, Path)
    data = oracle.read_bytes()
    check(sha256(data) == case["bmp_sha256"],
          "retained native BMP has its pinned SHA-256")
    try:
        page, palette = decode_bmp(oracle)
    except (AssertionError, OSError, struct.error) as error:
        check(False, f"retained native BMP decodes safely: {error}")
        page, palette = b"", ()
    else:
        check(len(page) == 64000 and sha256(page) == case["page_sha256"],
              "native BMP yields the pinned top-down 64,000-byte indexed page")
        raw_palette = struct.pack("<768I", *palette)
        check(len(palette) == 768 and sha256(raw_palette) == case["palette_sha256"],
              "native BMP yields the pinned 768-component six-bit RGB palette")
        cx, cy = case["center"]
        check(page[cy * 320 + cx] == 126,
              "native positive flare retains indexed centre sample 126")

    check_source_contract(check)
    if args.product_directory is not None and page and palette:
        grade_product(case, args.product_directory.resolve(), page, palette, check)
    else:
        print("SKIP product comparison requires --product-directory (non-GUI contract mode)")

    if errors:
        print(f"sun gallery: {len(errors)} failure(s)")
        return 1
    print("sun gallery: all requested checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
