from pathlib import Path
import hashlib
import os
import sys
import time

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/buffered-limb-restoring-fsqrt-20260830"
sys.path.insert(0, str(ROOT / "tools"))

from profile_noctis_desktop import (  # noqa: E402
    ASSETS,
    CLOCK_SECONDS,
    scenario_checkpoint,
    stage_scenario,
)
from windows_hidden_process import PrivateDesktopProcess  # noqa: E402

PRODUCTS = {
    "game-vh-out.bin": 156,
    "game-sun-out.bin": 128,
    "game-local-out.bin": 176,
    "game-page-out.bin": 64000,
    "game-palette-out.bin": 3072,
    "game-s-background-out.bin": 64800,
    "game-p-surfacemap-out.bin": 40000,
    "game-p-background-out.bin": 65552,
    "game-label-state-out.bin": 32,
    "game-render-state-out.bin": 24,
}
RUNS = (
    ("fidelity-baseline", EVIDENCE / "accepted/vhgame.exe"),
    ("fidelity-baseline-repeat", EVIDENCE / "accepted/vhgame.exe"),
    ("fidelity-candidate", EVIDENCE / "candidate/vhgame.exe"),
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


for name, executable in RUNS:
    stage = EVIDENCE / name
    if stage.exists():
        raise SystemExit(f"refusing to reuse fidelity stage: {stage}")
    staged_executable = stage_scenario(
        stage, executable, scenario_checkpoint("capsule"))
    cache = ROOT / "build/runtime-asset-cache-20260828"
    for asset in ASSETS:
        staged = stage / asset
        canonical = (ROOT / "work/noctis_music.pcm"
                     if asset == "noctis_music.pcm" else cache / asset)
        staged.unlink()
        os.link(canonical, staged)

    stable = 0
    deadline = time.monotonic() + 40.0
    with PrivateDesktopProcess(
            staged_executable, stage,
            (f"clock={CLOCK_SECONDS}", "quit", "freeze")) as process:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"{name} exited before products stabilized")
            complete = all(
                (stage / product).is_file()
                and (stage / product).stat().st_size == size
                for product, size in PRODUCTS.items())
            stable = stable + 1 if complete else 0
            if stable >= 10:
                break
            time.sleep(0.1)
        else:
            raise TimeoutError(f"{name} products did not stabilize")
        process.terminate(0)

    print(name, digest(staged_executable),
          digest(stage / "CURRENT.LIN"), "complete")
