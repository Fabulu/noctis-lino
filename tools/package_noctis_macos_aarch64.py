#!/usr/bin/env python3
"""Build and verify the native Apple-Silicon Noctis IV app archive."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import plistlib
import re
import shutil
import struct
import subprocess
import tempfile

from finalize_macos_aarch64 import validate_final
from package_noctis_macos import (
    APP_NAME,
    BUNDLE_ID,
    sha256,
    validate_assets,
    verify_manifest,
    write_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_NAME = "Noctis-IV-macos-arm64.zip"
PROVENANCE_NAME = "Noctis-IV-macos-arm64.provenance.txt"
DEPLOYMENT_TARGET = "11.0"
CPU_TYPE_ARM64 = 0x0100000C
REQUIRED_BUILD_KEYS = {
    "commit",
    "build/linux-compiler114m.bin_sha256",
    "build/macos-aarch64-rtm/rtm01.bin_sha256",
    "tests/fixtures/macos_aarch64_runtime.txt_sha256",
    "build/macos-aarch64-fixture.unsigned_sha256",
    "work/vhgame.txt_sha256",
    "build/macos-aarch64-noctis.unsigned_sha256",
}


def run(*command: str | Path, env: dict[str, str] | None = None) -> None:
    subprocess.run([str(item) for item in command], check=True, env=env)


def read_build_provenance(path: Path) -> tuple[list[str], dict[str, str]]:
    lines = path.read_text(encoding="ascii").splitlines()
    values: dict[str, str] = {}
    for line in lines:
        if not line or "=" not in line:
            raise ValueError(f"invalid build provenance line: {line!r}")
        key, value = line.split("=", 1)
        if not key or not value or key in values:
            raise ValueError(f"invalid or duplicate build provenance key: {key!r}")
        values[key] = value
    missing = REQUIRED_BUILD_KEYS - values.keys()
    if missing:
        raise ValueError(f"build provenance lacks: {', '.join(sorted(missing))}")
    return lines, values


def validate_arm64_macho(path: Path) -> None:
    data = path.read_bytes()
    if len(data) < 8 or data[:4] != b"\xcf\xfa\xed\xfe":
        raise ValueError(f"{path} is not a thin little-endian 64-bit Mach-O")
    if struct.unpack_from("<I", data, 4)[0] != CPU_TYPE_ARM64:
        raise ValueError(f"{path} is not arm64")


def validate_signed_game(path: Path) -> None:
    validate_arm64_macho(path)
    validate_final(path.read_bytes())
    run("codesign", "--verify", "--strict", "--verbose=2", path)


def compile_launcher(source: Path, output: Path) -> None:
    environment = os.environ.copy()
    environment["MACOSX_DEPLOYMENT_TARGET"] = DEPLOYMENT_TARGET
    run(
        "xcrun", "--sdk", "macosx", "clang", "-arch", "arm64",
        f"-mmacosx-version-min={DEPLOYMENT_TARGET}", "-std=c11",
        "-D_DARWIN_C_SOURCE", "-O2", "-Wall", "-Wextra", "-Werror",
        source, "-o", output, env=environment,
    )
    validate_arm64_macho(output)


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
        "LSArchitecturePriority": ["arm64"],
        "LSMinimumSystemVersion": DEPLOYMENT_TARGET,
        "NSHighResolutionCapable": True,
        "NSPrincipalClass": "NSApplication",
    }
    with path.open("wb") as output:
        plistlib.dump(payload, output, fmt=plistlib.FMT_XML, sort_keys=True)


def validate_versions(args: argparse.Namespace) -> None:
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+){0,2}", args.short_version):
        raise ValueError("short version must contain one to three numeric components")
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)*", args.build_version):
        raise ValueError("build version must contain only numeric components")
    if not args.release_label or "\n" in args.release_label:
        raise ValueError("release label must be one non-empty line")
    if not re.fullmatch(r"[0-9a-f]{40}", args.expected_commit):
        raise ValueError("expected commit must be a full lowercase SHA-1")


def build_package(args: argparse.Namespace) -> None:
    game = args.game.resolve()
    unsigned_game = args.unsigned_game.resolve()
    build_provenance = args.build_provenance.resolve()
    output = args.output.resolve()
    launcher_source = (
        ROOT / "src" / "noctis_macos_launcher" / "launcher.c"
    ).resolve()

    validate_versions(args)
    validate_signed_game(game)
    assets = validate_assets(ROOT / "work")
    provenance_lines, provenance = read_build_provenance(build_provenance)
    if provenance["commit"] != args.expected_commit:
        raise ValueError("build provenance identifies the wrong commit")
    if sha256(unsigned_game) != provenance[
        "build/macos-aarch64-noctis.unsigned_sha256"
    ]:
        raise ValueError("unsigned game does not match its build provenance")
    if not launcher_source.is_file():
        raise ValueError(f"missing launcher source: {launcher_source}")

    output.mkdir(parents=True, exist_ok=True)
    app_output = output / APP_NAME
    archive = output / ARCHIVE_NAME
    checksum = output / f"{ARCHIVE_NAME}.sha256"
    final_provenance = output / PROVENANCE_NAME
    produced = (app_output, archive, checksum, final_provenance)
    collisions = [str(path) for path in produced if path.exists()]
    if collisions:
        raise FileExistsError(
            f"refusing to replace existing output: {', '.join(collisions)}"
        )

    staging = Path(tempfile.mkdtemp(prefix=".noctis-arm64-package-", dir=output))
    extracted = Path(tempfile.mkdtemp(prefix=".noctis-arm64-verify-", dir=output))
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
        signed_game_hash = sha256(packaged_game)

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
        shutil.copy2(build_provenance, resources / "BUILD-PROVENANCE.txt")
        (resources / "RESOURCE_VERSION").write_text(
            f"{args.release_label}\n{args.expected_commit}\n",
            encoding="ascii",
            newline="\n",
        )

        write_manifest(app)
        run("codesign", "--force", "--sign", "-", app)
        run("codesign", "--verify", "--deep", "--strict", "--verbose=2", app)
        verify_manifest(app)
        if sha256(packaged_game) != signed_game_hash:
            raise ValueError("bundle signing changed the finalized game")

        os.replace(app, app_output)
        run("ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", app_output, archive)
        archive_hash = sha256(archive)
        checksum.write_text(f"{archive_hash} *{archive.name}\n", encoding="ascii")

        package_records = (
            ("package_format", "1"),
            ("package_script_sha256", sha256(Path(__file__).resolve())),
            ("build_provenance_sha256", sha256(build_provenance)),
            ("launcher_source_sha256", sha256(launcher_source)),
            ("launcher_sha256", sha256(app_output / "Contents" / "MacOS" / "Noctis-IV")),
            ("unsigned_game_sha256", sha256(unsigned_game)),
            ("signed_game_sha256", signed_game_hash),
            ("manifest_sha256", sha256(app_output / "Contents" / "Resources" / "MANIFEST.sha256")),
            ("archive_sha256", archive_hash),
            ("architecture", "arm64"),
            ("deployment_target", DEPLOYMENT_TARGET),
            ("bundle_identifier", BUNDLE_ID),
            ("release_label", args.release_label),
            ("signing", "ad-hoc application and exact-final-suffix game signatures"),
        )
        final_provenance.write_text(
            "".join(f"{line}\n" for line in provenance_lines)
            + "".join(f"{key}={value}\n" for key, value in package_records),
            encoding="ascii",
            newline="\n",
        )

        run("ditto", "-x", "-k", archive, extracted)
        extracted_app = extracted / APP_NAME
        extracted_launcher = extracted_app / "Contents" / "MacOS" / "Noctis-IV"
        extracted_game = extracted_app / "Contents" / "MacOS" / "Noctis-IV.game"
        validate_arm64_macho(extracted_launcher)
        validate_signed_game(extracted_game)
        run(
            "codesign", "--verify", "--deep", "--strict", "--verbose=2",
            extracted_app,
        )
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
        shutil.rmtree(extracted, ignore_errors=True)

    print(f"PACKAGED {archive} ({archive.stat().st_size} bytes)")
    print(f"SHA256 {archive_hash}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", type=Path, required=True)
    parser.add_argument("--unsigned-game", type=Path, required=True)
    parser.add_argument("--build-provenance", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--short-version", default="0.1.0")
    parser.add_argument("--build-version", default="1")
    parser.add_argument("--release-label", default="development")
    parser.add_argument("--expected-commit", required=True)
    return parser.parse_args()


def main() -> int:
    build_package(parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
