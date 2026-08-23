"""Rebuild the exact ten-case NIV+ surface-flare page oracle."""

from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work"
SANDBOX = ROOT / "tests" / "gen" / "surface-flare-oracle"
SOURCE = WORK / "vhsurfaceprobe.txt"
sys.path.insert(0, str(ROOT / "tests"))

import linoharness as lh  # noqa: E402


LIBRARIES = (
    "fp/fpabi.txt", "fp/fpctl.txt", "fp/fpx87.txt", "fp/fpsoft.txt",
    "fp/fpconv.txt", "fp/fpchains.txt", "geoconv.txt",
    "fbmem.txt", "fbpal.txt", "pgfp.txt", "pgmem.txt", "pgrast.txt",
    "pgtex.txt", "pgproj.txt", "spmem.txt", "spscale.txt", "spmap.txt",
    "spglobe.txt", "spbg.txt", "spwhite.txt", "spncc.txt",
    "mul64frag.txt", "brtl.txt", "suseed.txt", "surng.txt", "subuf.txt",
    "susm.txt", "supaint.txt", "supal.txt", "sucase.txt", "grnd.txt",
    "sky.txt", "vhjoin.txt", "vhrmap.txt", "vhstick.txt", "vhcupola.txt",
    "vhview.txt", "vhflare.txt",
)
PAGE_BYTES = 64000
PAGE_COUNT = 10
UNIFORM_PAGE_SHA256 = (
    "07be0786c5b0bf5fc4bb673363c9b876e87376fb5795b7f7d6177902be488019"
)
NATIVE_FIRST_SIX = {
    "before": "aab1ee2e97abb322ca8f2a6eab21829fd12604928ee5391ac2a53251c22cd179",
    "after": "2ae4bf3b1ef32b12108ad51d6b94c1682439c45e94822eea5c69460ce38f22af",
}
CONTEXT_AFTER = {
    6: "1bf100baf523624ab44bcc9dcda60d5e0663b36e9e22f8cc73e17ef20f1581e9",
    7: "17835a159fa70ba49c6842e37ed6088128e988744514f5f537719391d73abdd8",
    8: "89f0d4288d0a73f3c9c446e07dba74c14f9e439efc6ebd81d29e3f902b41f47c",
    9: UNIFORM_PAGE_SHA256,
}
COMPLETE_SHA256 = {
    "before": "c2e7d2dc70b7a1194141126e8f63fc7b8c463b1f35b860dd0a3a788bf37f33ee",
    "after": "dec74926989c514c0a977d7aeccca3888856aba03fd7f1d80e87c42274fe2c83",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def remove_sandbox() -> None:
    expected = (ROOT / "tests" / "gen" / "surface-flare-oracle").resolve()
    target = SANDBOX.resolve()
    if target != expected or target.parent != (ROOT / "tests" / "gen").resolve():
        raise RuntimeError(f"refusing unexpected flare sandbox {target}")
    if not target.exists():
        return
    if target.is_symlink():
        raise RuntimeError(f"refusing redirected flare sandbox {target}")
    shutil.rmtree(target)


def stage_source() -> Path:
    remove_sandbox()
    SANDBOX.mkdir(parents=True)
    for relative in LIBRARIES:
        source = WORK / relative
        destination = SANDBOX / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    main = SANDBOX / SOURCE.name
    shutil.copy2(SOURCE, main)
    return main


def main() -> int:
    errors: list[str] = []

    def check(condition: bool, message: str) -> None:
        print("PASS" if condition else "FAIL", message)
        if not condition:
            errors.append(message)

    source = SOURCE.read_text(encoding="utf-8")
    check("vhsprays = 10; vhspdists = 10; vhsppages = 10;" in source,
          "surface-flare probe retains exactly ten native fixtures")
    check("mgmain;" not in source and "vhstar;" not in source,
          "focused probe excludes unrelated programme dependencies")

    try:
        probe = stage_source()
        return_code, note = lh.build(str(probe), timeout_sec=300)
        check(return_code == 0, f"isolated surface-flare probe builds ({note[-300:]})")
        if return_code:
            return 1

        executable = probe.with_suffix(".exe")
        after_path = SANDBOX / "vhsurface-after.bin"
        return_code, note, after = lh.run(
            str(executable), str(after_path), timeout_sec=120,
            expected_bytes=PAGE_BYTES * PAGE_COUNT)
        check(return_code == 0 and after is not None,
              f"isolated surface-flare probe runs ({note[-300:]})")
        before_path = SANDBOX / "vhsurface-before.bin"
        before = before_path.read_bytes() if before_path.is_file() else b""
        after = after or b""

        expected_size = PAGE_BYTES * PAGE_COUNT
        check(len(before) == len(after) == expected_size,
              "probe emits ten complete before/after indexed pages")
        if len(before) == len(after) == expected_size:
            check(sha256(before[:6 * PAGE_BYTES]) == NATIVE_FIRST_SIX["before"]
                  and sha256(after[:6 * PAGE_BYTES]) == NATIVE_FIRST_SIX["after"],
                  "six synthetic pages equal the concatenated Borland NIV+ oracle")
            for index, name in ((6, "thin"), (7, "quartz"), (8, "habitable")):
                before_page = before[index * PAGE_BYTES:(index + 1) * PAGE_BYTES]
                after_page = after[index * PAGE_BYTES:(index + 1) * PAGE_BYTES]
                check(sha256(before_page) == UNIFORM_PAGE_SHA256
                      and sha256(after_page) == CONTEXT_AFTER[index],
                      f"{name} ray/distance pair equals its exact native flare page")
            lunar_before = before[9 * PAGE_BYTES:10 * PAGE_BYTES]
            lunar_after = after[9 * PAGE_BYTES:10 * PAGE_BYTES]
            check(lunar_before == lunar_after
                  and sha256(lunar_after) == CONTEXT_AFTER[9],
                  "lunar lower-distance gate preserves the exact native no-beam page")
            check(sha256(before) == COMPLETE_SHA256["before"]
                  and sha256(after) == COMPLETE_SHA256["after"],
                  "all ten rebuilt product pages retain their pinned aggregate hashes")
    except (OSError, RuntimeError) as error:
        check(False, f"surface-flare oracle executes safely: {error}")
    finally:
        remove_sandbox()

    if errors:
        print(f"surface flare oracle: {len(errors)} failure(s)")
        return 1
    print("surface flare oracle: all requested checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
