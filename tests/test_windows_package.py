#!/usr/bin/env python3
"""Launch the relocatable Windows package on a private inactive desktop."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from windows_hidden_process import PrivateDesktopProcess  # noqa: E402


WINDOWS_WORKFLOWS = (
    ROOT / ".github" / "workflows" / "windows-release.yml",
    ROOT / ".github" / "workflows" / "tagged-release.yml",
)
CDB_DIAGNOSTIC = ROOT / "tools" / "diagnose_windows_package_crash.py"
CHECKPOINT_BYTES = 268
CHECKPOINT_SCHEMA = 18
FIRST_FRAME_BYTES = 156
READINESS_TIMEOUT = 120.0
SHUTDOWN_TIMEOUT = 30.0
VK_ESCAPE = 0x1B


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def wait_for_first_frame(
        process: PrivateDesktopProcess, package: Path,
) -> tuple[int, tuple[int, int, int, int]]:
    sentinel = package / "game-vh-out.bin"
    deadline = time.monotonic() + READINESS_TIMEOUT
    last_rectangle: tuple[int, int, int, int] | None = None
    last_sentinel_size: int | None = None
    while time.monotonic() < deadline:
        handle = process.desktop_window_handle()
        if handle is not None:
            last_rectangle = process.window_rectangle(handle)
        if sentinel.is_file():
            last_sentinel_size = sentinel.stat().st_size
        return_code = process.poll()
        if return_code is not None:
            raise RuntimeError(
                f"package launcher exited during startup with code {return_code}; "
                f"last window {last_rectangle}, first-frame bytes "
                f"{last_sentinel_size}"
            )
        if handle is not None and last_sentinel_size == FIRST_FRAME_BYTES:
            rectangle = last_rectangle
            assert rectangle is not None
            width = rectangle[2] - rectangle[0]
            height = rectangle[3] - rectangle[1]
            require(width >= 320 and height >= 200,
                    f"game window is unexpectedly small: {rectangle}")
            return handle, rectangle
        time.sleep(0.10)
    raise TimeoutError(
        "packaged game did not expose its first rendered frame; "
        f"last window {last_rectangle}, first-frame bytes {last_sentinel_size}"
    )


def request_clean_shutdown(
        process: PrivateDesktopProcess, handle: int,
) -> int:
    deadline = time.monotonic() + SHUTDOWN_TIMEOUT
    next_escape = 0.0
    while time.monotonic() < deadline:
        return_code = process.poll()
        if return_code is not None:
            return return_code
        now = time.monotonic()
        if now >= next_escape:
            current = process.desktop_window_handle()
            if current is not None:
                handle = current
                process.post_key(handle, VK_ESCAPE, True)
                time.sleep(0.10)
                if process.poll() is None:
                    process.post_key(handle, VK_ESCAPE, False)
            next_escape = now + 2.0
        time.sleep(0.10)
    raise TimeoutError("packaged game did not exit through its save path")


def validate_checkpoint(package: Path) -> str:
    current = (package / "CURRENT.LIN").read_bytes()
    backup = (package / "CURRENT.BAK").read_bytes()
    require(len(current) == CHECKPOINT_BYTES,
            f"CURRENT.LIN is {len(current)} bytes, expected {CHECKPOINT_BYTES}")
    require(current == backup, "CURRENT.LIN and CURRENT.BAK differ")
    words = struct.unpack("<67i", current)
    require(words[1] == CHECKPOINT_SCHEMA,
            f"saved checkpoint schema is {words[1]}, expected {CHECKPOINT_SCHEMA}")
    return hashlib.sha256(current).hexdigest()


def validate_launcher_text() -> None:
    launcher = (ROOT / "Play Noctis IV.cmd").read_text(encoding="utf-8")
    require('pushd "%~dp0" || exit /b 2' in launcher,
            "launcher does not anchor mutable files to its package directory")
    require('"%~dp0Noctis-IV.exe"' in launcher and
            "start " not in launcher.lower(),
            "launcher must wait for the packaged executable")
    require("exit /b %noctis_exit%" in launcher,
            "launcher does not propagate the game exit status")

    command = "python tests\\test_windows_package.py --package dist\\Noctis-IV"
    for path in WINDOWS_WORKFLOWS:
        workflow = path.read_text(encoding="utf-8")
        require(workflow.count(command) == 1,
                f"{path.name} does not run the package playability gate once")
        require("Launch the package from an unrelated directory" in workflow,
                f"{path.name} does not describe the package launch boundary")
        require("read_bytes().replace(b'\\r\\n', b'\\n')" in workflow,
                f"{path.name} does not compare canonical LF source provenance")
        require("-DefaultDesktop" not in workflow,
                f"{path.name} opts into the interactive desktop")

    diagnostic = CDB_DIAGNOSTIC.read_text(encoding="utf-8")
    snapshot_workflow = WINDOWS_WORKFLOWS[0].read_text(encoding="utf-8")
    require("PrivateDesktopProcess(" in diagnostic and
            '"-cf", str(commands), "-logo", str(log), str(target)' in diagnostic,
            "CDB diagnostic does not launch the target on a private desktop")
    require("python tools\\diagnose_windows_package_crash.py" in snapshot_workflow and
            "Windows Kits\\10\\Debuggers\\x86\\cdb.exe" in snapshot_workflow,
            "snapshot workflow does not invoke the x86 CDB startup diagnostic")


def diagnose_without_music(package: Path, smoke_root: Path) -> str:
    diagnostic_package = smoke_root / "Noctis IV no music"
    diagnostic_caller = smoke_root / "no-music-caller"
    shutil.copytree(package, diagnostic_package)
    diagnostic_caller.mkdir()
    soundtrack = diagnostic_package / "noctis_music.pcm"
    require(soundtrack.is_file(), "no-music diagnostic lacks the soundtrack")
    soundtrack.unlink()
    launcher = diagnostic_package / "Play Noctis IV.cmd"
    command = Path(os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe"))
    try:
        with PrivateDesktopProcess(
            command, diagnostic_caller, ("/d", "/c", str(launcher)),
        ) as process:
            handle, rectangle = wait_for_first_frame(process, diagnostic_package)
            return_code = request_clean_shutdown(process, handle)
            require(return_code == 0,
                    f"no-music diagnostic launcher returned {return_code}")
    except (OSError, RuntimeError, TimeoutError) as error:
        return f"no-music diagnostic also failed: {error}"
    return f"no-music diagnostic reached first frame {rectangle} and exited 0"


def run_package(package: Path) -> None:
    if os.name != "nt":
        raise OSError("the package playability gate requires Windows")
    package = package.resolve()
    require(package.is_dir(), f"package directory does not exist: {package}")
    for name in ("Play Noctis IV.cmd", "Noctis-IV.exe", "MANIFEST.sha256"):
        require((package / name).is_file(), f"package is missing {name}")
    for name in ("CURRENT.LIN", "CURRENT.BAK", "game-vh-out.bin"):
        require(not (package / name).exists(),
                f"package is not fresh; unexpected mutable file {name}")

    original_hashes = tree_hashes(package)
    with tempfile.TemporaryDirectory(prefix="noctis-package-smoke-") as directory:
        smoke_root = Path(directory)
        smoke_package = smoke_root / "Noctis IV"
        caller = smoke_root / "unrelated-caller"
        shutil.copytree(package, smoke_package)
        caller.mkdir()
        launcher = smoke_package / "Play Noctis IV.cmd"
        command = Path(os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe"))

        try:
            with PrivateDesktopProcess(
                command, caller, ("/d", "/c", str(launcher)),
            ) as process:
                handle, rectangle = wait_for_first_frame(process, smoke_package)
                print(f"PASS packaged first frame on private desktop: {rectangle}")
                return_code = request_clean_shutdown(process, handle)
                require(return_code == 0,
                        f"package launcher returned {return_code}, expected 0")
        except (OSError, RuntimeError, TimeoutError) as error:
            diagnosis = diagnose_without_music(package, smoke_root)
            raise RuntimeError(f"{error}; {diagnosis}") from error

        checkpoint_hash = validate_checkpoint(smoke_package)
        require(not any(caller.iterdir()),
                "packaged launch wrote mutable files in the caller directory")
        print(f"PASS package-local v18 save: {checkpoint_hash}")
        print("PASS launcher exited 0 without writing outside the package")

    require(tree_hashes(package) == original_hashes,
            "package gate modified the release package it was given")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--package", type=Path,
        help="assembled package directory to launch (Windows only)",
    )
    args = parser.parse_args()

    try:
        validate_launcher_text()
        print("PASS launcher anchors and propagates package execution")
        if args.package is not None:
            run_package(args.package)
    except (OSError, RuntimeError, TimeoutError) as error:
        print(f"FAIL Windows package gate: {error}", file=sys.stderr)
        return 1
    print("Windows package gate: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
