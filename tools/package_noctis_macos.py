#!/usr/bin/env python3
"""Build and verify a Finder-safe, ad-hoc-signed Noctis IV macOS app."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import struct
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "Noctis IV.app"
ARCHIVE_NAME = "Noctis-IV-macos-x86_64.zip"
BUNDLE_ID = "io.github.fabulu.noctis-iv"
DEPLOYMENT_TARGET = "10.15"
EXPECTED_NIV_HASHES = {
    "surf": "390A2CCB",
    "atmo": "114562E8",
    "pal": "26961E4A",
    "hm": "97022FD7",
    "oc": "22913F4E",
    "stex": "0D52F001",
    "sky": "1E308D29",
}

STATIC_ASSETS = (
    ("globes.map", 22_586),
    ("offsets.map", 7_340),
    ("vehicle.ncc", 5_802),
    ("mammal.ncc", 2_752),
    ("birdy.ncc", 1_002),
    ("digimap2.bin", 9_360),
)
MUTABLE_ASSETS = ("STARMAP.BIN", "GUIDE.BIN")
REQUIRED_PROVENANCE = {
    "commit",
    "source_sha256",
    "executable_sha256",
    "compile_script_sha256",
    "compiler_runtime_installer_sha256",
    "bootstrap_compiler_sha256",
    "compiler_source_sha256",
    "compiler_bits_library_sha256",
    "compiler_bytes_library_sha256",
    "compiler_build_script_sha256",
    "bootstrap_cpu_pack_sha256",
    "bootstrap_system_pack_sha256",
    "compiler_sha256",
    "cpu_pack_sha256",
    "cpu_pack_auditor_sha256",
    "runtime_provenance_tool_sha256",
    "runtime_provenance_sha256",
    "runtime_provenance_format",
    "runtime_sha256",
    "runtime_mode",
    "runtime_build_script_sha256",
    "runtime_source_tree_sha256",
    "runtime_architecture",
    "runtime_deployment_target",
    "runtime_host_arch",
    "runtime_macos_version",
    "runtime_xcode_version",
    "runtime_sdk_version",
    "runtime_clang_version",
    "runtime_signing",
    "runtime_provenance",
    "system_pack_sha256",
    "target",
    "build_provenance",
}
PACKAGE_PROVENANCE_KEYS = {
    "package_script_sha256",
    "launcher_source_sha256",
    "launcher_sha256",
    "signed_executable_sha256",
    "manifest_sha256",
    "nivtest_executable_sha256",
    "nivtest_build_provenance_sha256",
    "nivtest_headless_runtime_sha256",
    "rosetta_nivgen_result_sha256",
    "rosetta_nivgen_exact",
    "archive_sha256",
    "bundle_identifier",
    "deployment_target",
    "release_label",
    "signing",
    "package_provenance",
    "validation_reference_commit",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_macho(path: Path) -> None:
    data = path.read_bytes()
    if len(data) < 1024 or data[:4] != b"\xcf\xfa\xed\xfe":
        raise ValueError(f"{path} is not a thin little-endian 64-bit Mach-O")
    cpu_type = struct.unpack_from("<I", data, 4)[0]
    if cpu_type != 0x01000007:
        raise ValueError(f"{path} has Mach-O CPU type {cpu_type:#x}, expected x86_64")


def validate_assets(work: Path) -> list[Path]:
    assets: list[Path] = []
    for name, expected_size in STATIC_ASSETS:
        path = work / name
        if not path.is_file() or path.stat().st_size != expected_size:
            actual = path.stat().st_size if path.is_file() else "missing"
            raise ValueError(
                f"unexpected size for {name}: {actual}, expected {expected_size}"
            )
        assets.append(path)

    starmap = work / MUTABLE_ASSETS[0]
    starmap_data = starmap.read_bytes()
    consolidated = struct.unpack_from("<I", starmap_data, 0)[0] if len(starmap_data) >= 4 else 0
    if (
        len(starmap_data) < 4
        or (len(starmap_data) - 4) % 32
        or consolidated < 4
        or consolidated > len(starmap_data)
        or (consolidated - 4) % 32
        or len(starmap_data) > 1_280_004
    ):
        raise ValueError("STARMAP.BIN does not satisfy the bounded 4 + 32n contract")
    assets.append(starmap)

    guide = work / MUTABLE_ASSETS[1]
    guide_data = guide.read_bytes()
    consolidated = struct.unpack_from("<I", guide_data, 0)[0] if len(guide_data) >= 4 else 0
    if (
        len(guide_data) < 4
        or (len(guide_data) - 4) % 84
        or consolidated < 4
        or consolidated > len(guide_data)
        or (consolidated - 4) % 84
        or len(guide_data) > 8_388_608
    ):
        raise ValueError("GUIDE.BIN does not satisfy the bounded 4 + 84n contract")
    assets.append(guide)

    music = work / "noctis_music.pcm"
    music_size = music.stat().st_size if music.is_file() else 0
    if music_size <= 0 or music_size > 26_400_000 or music_size % 4:
        raise ValueError(
            "noctis_music.pcm must be non-empty interleaved stereo S16LE data"
        )
    assets.append(music)
    return assets


def read_provenance(path: Path) -> tuple[list[str], dict[str, str]]:
    lines = path.read_text(encoding="ascii").splitlines()
    values: dict[str, str] = {}
    for line in lines:
        if not line:
            continue
        if "=" not in line:
            raise ValueError(f"invalid provenance line: {line!r}")
        key, value = line.split("=", 1)
        if not key or key in values:
            raise ValueError(f"invalid or duplicate provenance key: {key!r}")
        values[key] = value
    reserved = PACKAGE_PROVENANCE_KEYS & values.keys()
    if reserved:
        raise ValueError(
            f"build provenance uses reserved package keys: {', '.join(sorted(reserved))}"
        )
    missing = REQUIRED_PROVENANCE - values.keys()
    if missing:
        raise ValueError(f"build provenance lacks: {', '.join(sorted(missing))}")
    expected = {
        "target": "macos/x64",
        "runtime_provenance_format": "1",
        "runtime_mode": "cocoa",
        "runtime_architecture": "x86_64",
        "runtime_deployment_target": DEPLOYMENT_TARGET,
        "runtime_host_arch": "arm64",
        "runtime_signing": "unsigned before the Lino image is appended",
    }
    mismatches = {
        key: (values.get(key), value)
        for key, value in expected.items()
        if values.get(key) != value
    }
    if mismatches:
        raise ValueError(f"unexpected build provenance values: {mismatches!r}")
    return lines, values


def validate_nivtest(
    executable: Path,
    provenance_path: Path,
    result_path: Path,
    game_provenance: dict[str, str],
) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in provenance_path.read_text(encoding="ascii").splitlines():
        if not line or "=" not in line:
            raise ValueError(f"invalid NIVTEST provenance line: {line!r}")
        key, value = line.split("=", 1)
        if not key or key in values:
            raise ValueError(f"invalid or duplicate NIVTEST provenance key: {key!r}")
        values[key] = value
    required = {
        "nivtest_provenance_format",
        "commit",
        "nivtest_executable_sha256",
        "nivtest_compile_script_sha256",
        "nivtest_tool_sha256",
        "compiler_sha256",
        "cpu_pack_sha256",
        "cpu_pack_auditor_sha256",
        "runtime_provenance_tool_sha256",
        "runtime_provenance_sha256",
        "runtime_sha256",
        "runtime_mode",
        "runtime_source_tree_sha256",
        "runtime_host_arch",
        "target",
        "nivtest_build_provenance",
    }
    missing = required - values.keys()
    if missing:
        raise ValueError(f"NIVTEST provenance lacks: {', '.join(sorted(missing))}")
    expected = {
        "nivtest_provenance_format": "1",
        "commit": game_provenance["commit"],
        "nivtest_executable_sha256": sha256(executable),
        "nivtest_tool_sha256": sha256(ROOT / "tools" / "nivtest.py"),
        "compiler_sha256": game_provenance["compiler_sha256"],
        "cpu_pack_sha256": game_provenance["cpu_pack_sha256"],
        "cpu_pack_auditor_sha256": game_provenance["cpu_pack_auditor_sha256"],
        "runtime_provenance_tool_sha256": game_provenance[
            "runtime_provenance_tool_sha256"
        ],
        "runtime_mode": "headless",
        "runtime_source_tree_sha256": game_provenance[
            "runtime_source_tree_sha256"
        ],
        "runtime_host_arch": "arm64",
        "target": "macos/x64",
    }
    if any(values.get(key) != value for key, value in expected.items()):
        raise ValueError("NIVTEST executable/provenance does not match the packaged build")

    result = json.loads(result_path.read_text(encoding="utf-8"))
    try:
        got = {
            name: result["hashes"][name]["fnv"] for name in EXPECTED_NIV_HASHES
        }
    except (KeyError, TypeError) as error:
        raise ValueError("Rosetta NIVGEN result lacks exact hash records") from error
    if result.get("status") != 0 or got != EXPECTED_NIV_HASHES:
        raise ValueError(f"Rosetta NIVGEN result is not exact: {got!r}")
    return values


def run(*command: str | Path, env: dict[str, str] | None = None) -> None:
    subprocess.run([str(item) for item in command], check=True, env=env)


def write_plist(
    path: Path,
    short_version: str,
    build_version: str,
    release_label: str,
) -> None:
    payload = {
        "CFBundleDevelopmentRegion": "en",
        "CFBundleDisplayName": "Noctis IV",
        "CFBundleExecutable": "Noctis-IV",
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundleName": "Noctis IV",
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": short_version,
        "CFBundleVersion": build_version,
        "CFBundleGetInfoString": f"Noctis IV L.in.oleum port {release_label}",
        "LSApplicationCategoryType": "public.app-category.games",
        "LSArchitecturePriority": ["x86_64"],
        "LSMinimumSystemVersion": DEPLOYMENT_TARGET,
        "NSHighResolutionCapable": True,
        "NSPrincipalClass": "NSApplication",
    }
    with path.open("wb") as output:
        plistlib.dump(payload, output, fmt=plistlib.FMT_XML, sort_keys=True)


def manifest_entries(app: Path) -> list[Path]:
    entries = [app / "Contents" / "Info.plist", app / "Contents" / "MacOS" / "Noctis-IV.game"]
    resources = app / "Contents" / "Resources"
    entries.extend(
        path for path in resources.iterdir()
        if path.is_file() and path.name != "MANIFEST.sha256"
    )
    return sorted(entries, key=lambda path: path.relative_to(app).as_posix())


def write_manifest(app: Path) -> Path:
    manifest = app / "Contents" / "Resources" / "MANIFEST.sha256"
    lines = [
        f"{sha256(path)} *{path.relative_to(app).as_posix()}\n"
        for path in manifest_entries(app)
    ]
    manifest.write_text("".join(lines), encoding="ascii", newline="\n")
    return manifest


def verify_manifest(app: Path) -> None:
    manifest = app / "Contents" / "Resources" / "MANIFEST.sha256"
    seen: set[str] = set()
    for raw in manifest.read_text(encoding="ascii").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64}) \*(.+)", raw)
        if not match:
            raise ValueError(f"invalid internal manifest line: {raw!r}")
        expected, relative = match.groups()
        if relative in seen or relative.startswith("/") or ".." in Path(relative).parts:
            raise ValueError(f"unsafe or duplicate manifest path: {relative!r}")
        seen.add(relative)
        path = app / relative
        if not path.is_file() or sha256(path) != expected:
            raise ValueError(f"internal manifest mismatch: {relative}")
    expected_paths = {
        path.relative_to(app).as_posix() for path in manifest_entries(app)
    }
    if seen != expected_paths:
        raise ValueError(
            f"internal manifest coverage differs: missing={sorted(expected_paths - seen)!r}, "
            f"extra={sorted(seen - expected_paths)!r}"
        )


def compile_launcher(source: Path, output: Path) -> None:
    env = os.environ.copy()
    env["MACOSX_DEPLOYMENT_TARGET"] = DEPLOYMENT_TARGET
    run(
        "xcrun",
        "--sdk",
        "macosx",
        "clang",
        "-arch",
        "x86_64",
        f"-mmacosx-version-min={DEPLOYMENT_TARGET}",
        "-std=c11",
        "-D_DARWIN_C_SOURCE",
        "-O2",
        "-Wall",
        "-Wextra",
        "-Werror",
        source,
        "-o",
        output,
        env=env,
    )


def build_package(args: argparse.Namespace) -> None:
    game = args.game.resolve()
    provenance_input = args.provenance.resolve()
    nivtest = args.nivtest.resolve()
    nivtest_provenance = args.nivtest_provenance.resolve()
    nivtest_result = args.nivtest_result.resolve()
    output = args.output.resolve()
    launcher_source = (ROOT / "src" / "noctis_macos_launcher" / "launcher.c").resolve()
    work = ROOT / "work"

    validate_macho(game)
    validate_macho(nivtest)
    assets = validate_assets(work)
    provenance_lines, provenance = read_provenance(provenance_input)
    nivtest_values = validate_nivtest(
        nivtest, nivtest_provenance, nivtest_result, provenance
    )
    if sha256(game) != provenance["executable_sha256"]:
        raise ValueError("game does not match its Linux build provenance")
    if args.expected_commit and provenance["commit"] != args.expected_commit:
        raise ValueError("build provenance does not identify the requested commit")
    if not launcher_source.is_file():
        raise ValueError(f"missing launcher source: {launcher_source}")

    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+){0,2}", args.short_version):
        raise ValueError("short version must contain one to three numeric components")
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)*", args.build_version):
        raise ValueError("build version must contain only numeric components")
    if not args.release_label or "\n" in args.release_label:
        raise ValueError("release label must be one non-empty line")
    if args.validation_reference_commit is not None and not re.fullmatch(
        r"[0-9a-f]{40}", args.validation_reference_commit
    ):
        raise ValueError("validation reference commit must be a full lowercase SHA-1")

    output.mkdir(parents=True, exist_ok=True)
    app_output = output / APP_NAME
    archive = output / ARCHIVE_NAME
    checksum = output / f"{ARCHIVE_NAME}.sha256"
    final_provenance = output / "Noctis-IV-macos-x86_64.provenance.txt"
    produced = (app_output, archive, checksum, final_provenance)
    collisions = [str(path) for path in produced if path.exists()]
    if collisions:
        raise FileExistsError(f"refusing to replace existing output: {', '.join(collisions)}")

    staging = Path(tempfile.mkdtemp(prefix=".noctis-macos-package-", dir=output))
    extract = Path(tempfile.mkdtemp(prefix=".noctis-macos-verify-", dir=output))
    try:
        app = staging / APP_NAME
        macos = app / "Contents" / "MacOS"
        resources = app / "Contents" / "Resources"
        macos.mkdir(parents=True)
        resources.mkdir()

        launcher = macos / "Noctis-IV"
        packaged_game = macos / "Noctis-IV.game"
        compile_launcher(launcher_source, launcher)
        shutil.copy2(game, packaged_game)
        launcher.chmod(0o755)
        packaged_game.chmod(0o755)

        write_plist(
            app / "Contents" / "Info.plist",
            args.short_version,
            args.build_version,
            args.release_label,
        )
        for asset in assets:
            shutil.copy2(asset, resources / asset.name)
        shutil.copy2(ROOT / "PLAYER_README.txt", resources / "README.txt")
        shutil.copy2(ROOT / "LICENSE.htm", resources / "WPL.htm")
        shutil.copy2(provenance_input, resources / "BUILD-PROVENANCE.txt")
        shutil.copy2(
            nivtest_provenance, resources / "NIVTEST-BUILD-PROVENANCE.txt"
        )
        shutil.copy2(nivtest_result, resources / "ROSETTA-NIVGEN-RESULT.json")
        (resources / "RESOURCE_VERSION").write_text(
            f"{args.release_label}\n{provenance['commit']}\n",
            encoding="ascii",
            newline="\n",
        )

        run("codesign", "--force", "--sign", "-", packaged_game)
        validate_macho(packaged_game)
        manifest = write_manifest(app)
        run("codesign", "--force", "--sign", "-", app)
        run("codesign", "--verify", "--deep", "--strict", "--verbose=2", app)
        verify_manifest(app)

        os.replace(app, app_output)
        run("ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", app_output, archive)
        archive_hash = sha256(archive)
        checksum.write_text(f"{archive_hash} *{archive.name}\n", encoding="ascii")

        package_records = [
            ("package_script_sha256", sha256(Path(__file__).resolve())),
            ("launcher_source_sha256", sha256(launcher_source)),
            ("launcher_sha256", sha256(app_output / "Contents" / "MacOS" / "Noctis-IV")),
            ("signed_executable_sha256", sha256(app_output / "Contents" / "MacOS" / "Noctis-IV.game")),
            ("manifest_sha256", sha256(app_output / "Contents" / "Resources" / "MANIFEST.sha256")),
            ("nivtest_executable_sha256", sha256(nivtest)),
            ("nivtest_build_provenance_sha256", sha256(nivtest_provenance)),
            ("nivtest_headless_runtime_sha256", nivtest_values["runtime_sha256"]),
            ("rosetta_nivgen_result_sha256", sha256(nivtest_result)),
            ("rosetta_nivgen_exact", "7/7 production output families"),
            ("archive_sha256", archive_hash),
            ("bundle_identifier", BUNDLE_ID),
            ("deployment_target", DEPLOYMENT_TARGET),
            ("release_label", args.release_label),
            ("signing", "ad-hoc; hardened runtime is not enabled"),
            ("package_provenance", "the archive was extracted; strict nested signatures reverified the launcher and app, while the complete non-launcher payload manifest was independently rechecked"),
        ]
        if args.validation_reference_commit is not None:
            package_records.append(
                ("validation_reference_commit", args.validation_reference_commit)
            )
        final_provenance.write_text(
            "".join(f"{line}\n" for line in provenance_lines if line)
            + "".join(f"{key}={value}\n" for key, value in package_records),
            encoding="ascii",
            newline="\n",
        )

        run("ditto", "-x", "-k", archive, extract)
        extracted_app = extract / APP_NAME
        run("codesign", "--verify", "--deep", "--strict", "--verbose=2", extracted_app)
        verify_manifest(extracted_app)
        if sha256(archive) != archive_hash:
            raise ValueError("archive changed after checksum generation")
    except BaseException:
        for path in produced:
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        shutil.rmtree(extract, ignore_errors=True)

    print(f"PACKAGED {archive} ({archive.stat().st_size} bytes)")
    print(f"SHA256 {archive_hash}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    parser.add_argument("--nivtest", type=Path, required=True)
    parser.add_argument("--nivtest-provenance", type=Path, required=True)
    parser.add_argument("--nivtest-result", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--short-version", default="0.1.0")
    parser.add_argument("--build-version", default="1")
    parser.add_argument("--release-label", default="development")
    parser.add_argument("--expected-commit")
    parser.add_argument("--validation-reference-commit")
    return parser.parse_args()


def main() -> int:
    build_package(parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
