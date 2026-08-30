from pathlib import Path
import hashlib
import json

ROOT = Path("C:/programmieren/linoleum/build/restoring-fsqrt-20260830")
PRODUCTS = (
    "game-vh-out.bin",
    "game-sun-out.bin",
    "game-local-out.bin",
    "game-page-out.bin",
    "game-palette-out.bin",
    "game-s-background-out.bin",
    "game-p-surfacemap-out.bin",
    "game-p-background-out.bin",
    "game-label-state-out.bin",
    "game-render-state-out.bin",
)
RUNS = {
    "baseline": ROOT / "fidelity-baseline",
    "baseline_repeat": ROOT / "fidelity-baseline-repeat",
    "candidate": ROOT / "fidelity-candidate",
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def mismatch(left, right, *, page=False):
    positions = [index for index, pair in enumerate(zip(left, right))
                 if pair[0] != pair[1]]
    result = {
        "exact": not positions,
        "mismatch_count": len(positions),
        "first_mismatch": positions[0] if positions else None,
    }
    if page and positions:
        xs = [index % 320 for index in positions]
        ys = [index // 320 for index in positions]
        result["mismatch_bounds_xy"] = [min(xs), min(ys), max(xs), max(ys)]
    return result


def normalized(name, data):
    data = bytearray(data)
    if name == "game-vh-out.bin":
        data[72:156] = b"\0" * 84
    elif name == "game-local-out.bin":
        data[8:12] = b"\0" * 4
    elif name == "game-page-out.bin":
        for y in range(2, 7):
            for x in range(74, 93):
                data[y * 320 + x] = 0
    return bytes(data)


raw = {
    run: {name: directory.joinpath(name).read_bytes() for name in PRODUCTS}
    for run, directory in RUNS.items()
}
report = {
    "schema": 1,
    "clock": 1344638527,
    "arguments": ["clock=1344638527", "quit", "freeze"],
    "runs": {},
    "comparisons": {},
    "baseline_reproducibility": {},
    "normalized_exact": {},
}
for run, directory in RUNS.items():
    report["runs"][run] = {
        "executable_sha256": digest((directory / "Noctis-IV.exe").read_bytes()),
        "checkpoint_sha256": digest((directory / "CURRENT.LIN").read_bytes()),
        "products": {
            name: {"size": len(raw[run][name]), "sha256": digest(raw[run][name])}
            for name in PRODUCTS
        },
    }

for name in PRODUCTS:
    page = name == "game-page-out.bin"
    report["comparisons"][name] = mismatch(
        raw["baseline"][name], raw["candidate"][name], page=page)
    report["baseline_reproducibility"][name] = mismatch(
        raw["baseline"][name], raw["baseline_repeat"][name], page=page)
    report["normalized_exact"][name] = {
        "candidate": normalized(name, raw["baseline"][name])
        == normalized(name, raw["candidate"][name]),
        "baseline_repeat": normalized(name, raw["baseline"][name])
        == normalized(name, raw["baseline_repeat"][name]),
    }

passed = all(
    values[comparison]
    for values in report["normalized_exact"].values()
    for comparison in ("candidate", "baseline_repeat")
)
report["fidelity_verdict"] = {
    "status": "pass" if passed else "fail",
    "authoritative_renderer_products_exact": [
        name for name in PRODUCTS
        if report["comparisons"][name]["exact"]
        and report["baseline_reproducibility"][name]["exact"]
    ],
    "game_vh_authoritative_state_bytes_0_71_exact":
        raw["baseline"]["game-vh-out.bin"][:72]
        == raw["candidate"]["game-vh-out.bin"][:72]
        == raw["baseline_repeat"]["game-vh-out.bin"][:72],
    "game_vh_host_timing_bytes_72_155_excluded": True,
    "game_local_exact_except_live_utc_unit_2_bytes_8_11":
        report["normalized_exact"]["game-local-out.bin"]["candidate"],
    "game_page_exact_outside_live_utc_telemetry_bounds_xy_74_2_92_6":
        report["normalized_exact"]["game-page-out.bin"]["candidate"],
    "baseline_repeat_control": "pass" if all(
        value["baseline_repeat"]
        for value in report["normalized_exact"].values()) else "fail",
}
(ROOT / "fidelity.json").write_text(
    json.dumps(report, indent=2) + "\n", encoding="utf-8")
print("fidelity", report["fidelity_verdict"]["status"])
for name, value in report["comparisons"].items():
    print(name, value)
if not passed:
    raise SystemExit(1)
