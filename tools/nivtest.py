#!/usr/bin/env python3
"""Drive the production Lino generators with the public NIVGEN protocol."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import zlib


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work"
TESTS = ROOT / "tests"
sys.path.insert(0, str(TESTS))
import linoharness as lh  # noqa: E402


IN_MAGIC = 0x4E494E31
OUT_MAGIC = 0x4E494E32
VERSION = 1
HEAD = 32
LAYOUT = {
    "surface": (32, 64800),
    "atmo": (64832, 32400),
    "palette": (97232, 768),
    "height": (98000, 40000),
    "gap": (138000, 16),
    "objects": (138016, 40000),
    "surftex": (178016, 65536),
    "sky": (243552, 64800),
    "surface_palette": (308352, 768),
}
HASH_EXTENTS = {
    "surface": 360 * 128,
    "surftex": 256 * 254,
    "sky": 360 * 128,
}
OUT_UNITS = 309120
DIAG_MAGIC = 0x3147444E
DIAG_VERSION = 1
DIAG_UNITS = 256
DIAG_RECORD_OFFSET = 64
DIAG_RECORD_UNITS = 8
DIAG_MAX_RECORDS = 24
PHASE_NAMES = {
    0: "entry", 1: "prologue", 2: "seed", 3: "rndpat",
    4: "case", 5: "sda", 6: "switch_end", 7: "normalize",
    8: "merge", 9: "terminator", 10: "post", 11: "palette",
    12: "done",
}
DEFAULT_GAP = bytes.fromhex("000000000000000000000000C509F054")


def u32(value: int) -> int:
    return value & 0xFFFFFFFF


def signed(value: int) -> int:
    return value if value < 0x80000000 else value - 0x100000000


def fnv1a(data: bytes) -> int:
    value = 2166136261
    for byte in data:
        value = ((value ^ byte) * 16777619) & 0xFFFFFFFF
    return value


def hash_record(data: bytes) -> dict[str, object]:
    return {
        "len": len(data),
        "fnv": f"{fnv1a(data):08X}",
        "crc": f"{zlib.crc32(data) & 0xFFFFFFFF:08X}",
    }


def derive_main() -> tuple[Path, bool]:
    source_path = WORK / "vhgame.txt"
    generated = WORK / "nivtestmain.txt"
    text = source_path.read_text(encoding="utf-8")
    libs_old = "vhspace; vhstar; vhground; vhcapsule;"
    libs_new = "vhspace; vhstar; vhground; vhnivgen; vhcapsule;"
    entry_old = "\t=> VHG run;\n\tend;"
    entry_new = "\t=> VHNIV run;\n\tend;"
    if text.count(libs_old) != 1 or text.count(entry_old) != 1:
        raise RuntimeError("vhgame NIVGEN splice point changed")
    text = text.replace(libs_old, libs_new, 1)
    text = text.replace("program name = { vhgame };",
                        "program name = { nivtestmain };", 1)
    text = text.replace(entry_old, entry_new, 1)
    changed = not generated.exists() or generated.read_text(
        encoding="utf-8") != text
    if changed:
        generated.write_text(text, encoding="utf-8", newline="\n")
    return generated, changed


def ensure_build(force: bool) -> Path:
    source, changed = derive_main()
    exe = source.with_suffix(".exe")
    source_files = list(WORK.glob("*.txt")) + list((WORK / "fp").glob("*.txt"))
    stale = (not exe.exists() or changed or
             any(path.stat().st_mtime > exe.stat().st_mtime
                 for path in source_files))
    if force or stale:
        rc, note = lh.build(str(source), timeout_sec=300)
        if rc or not exe.exists():
            raise RuntimeError("Lino NIVGEN build failed: " + note[-2000:])
    return exe


def resolve_executable(args: argparse.Namespace) -> Path:
    """Use a supplied portable build, or build the Windows harness locally."""
    supplied = getattr(args, "exe", None) or os.environ.get("LINO_NIVTEST_EXE")
    if supplied:
        if getattr(args, "build", False):
            raise ValueError("--build cannot be combined with --exe")
        executable = Path(supplied).expanduser().resolve()
        if not executable.is_file():
            raise FileNotFoundError(f"NIVGEN executable not found: {executable}")
        return executable
    if os.name != "nt":
        raise RuntimeError(
            "no portable NIVGEN executable supplied; pass --exe or set "
            "LINO_NIVTEST_EXE (build/build_nivtest.sh builds the macOS host)")
    return ensure_build(getattr(args, "build", False))


def decode_units(
        path: Path, diagnostic: bool = False,
) -> tuple[list[int], dict[str, bytes], list[int] | None]:
    raw = path.read_bytes()
    expected_units = OUT_UNITS + (DIAG_UNITS if diagnostic else 0)
    if len(raw) != expected_units * 4:
        raise RuntimeError(f"wrong Lino output size {len(raw)}")
    units = list(struct.unpack(f"<{expected_units}I", raw))
    header = units[:HEAD]
    if header[0] != OUT_MAGIC or header[1] != VERSION:
        raise RuntimeError(
            f"bad Lino output header {header[0]:08X}/{header[1]}")
    buffers = {
        name: bytes(value & 0xFF for value in units[start:start + length])
        for name, (start, length) in LAYOUT.items()
    }
    diagnostic_units = units[OUT_UNITS:] if diagnostic else None
    if diagnostic_units is not None:
        if (diagnostic_units[0] != DIAG_MAGIC or
                diagnostic_units[1] != DIAG_VERSION or
                diagnostic_units[2] != DIAG_UNITS):
            raise RuntimeError(
                "bad Lino diagnostic trailer "
                f"{diagnostic_units[0]:08X}/{diagnostic_units[1]}/"
                f"{diagnostic_units[2]}")
    return header, buffers, diagnostic_units


def run_lino(
        args: argparse.Namespace,
) -> tuple[list[int], dict[str, bytes], list[int] | None]:
    exe = resolve_executable(args)
    gap = bytes.fromhex(args.gap) if args.gap else DEFAULT_GAP
    if len(gap) != 16:
        raise ValueError("-gap must contain exactly 32 hexadecimal digits")
    values = [
        IN_MAGIC, VERSION, u32(args.x), u32(args.y), u32(args.z),
        u32(args.p), u32(args.lon), u32(args.lat), u32(args.secs),
        u32(args.sc), u32(args.albedo), u32(args.night), 1,
        1 if args.diagnostic else 0, 0, 0,
        *gap,
    ]
    with tempfile.TemporaryDirectory(prefix="nivtest-") as temp_name:
        temp = Path(temp_name)
        (temp / "niv-input.bin").write_bytes(struct.pack("<32I", *values))
        if os.name == "nt":
            import windows_hidden_process
            proc = windows_hidden_process.run(exe, temp, args.timeout)
        else:
            proc = subprocess.run(
                [str(exe)], cwd=temp, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=args.timeout,
            )
        output = temp / "niv-output.bin"
        if proc.returncode or not output.exists():
            detail = ((proc.stdout or "") + (proc.stderr or ""))[-2000:]
            raise RuntimeError(
                f"Lino NIVGEN run failed with exit {proc.returncode}: {detail}")
        return decode_units(output, args.diagnostic)


def hex32(value: int) -> str:
    return f"{value:08X}"


def diagnostic_results(units: list[int]) -> dict[str, object]:
    record_count = units[3]
    if record_count > DIAG_MAX_RECORDS:
        raise RuntimeError(f"bad Lino diagnostic record count {record_count}")
    ledger = []
    for index in range(record_count):
        start = DIAG_RECORD_OFFSET + index * DIAG_RECORD_UNITS
        (
            phase, tag, fast_count, borland_count,
            fast_hash, borland_hash, map_hash, overlay_hash,
        ) = units[start:start + DIAG_RECORD_UNITS]
        ledger.append({
            "phase": PHASE_NAMES.get(phase, f"unknown_{phase}"),
            "phase_id": phase,
            "tag": signed(tag),
            "fast_count": fast_count,
            "borland_count": borland_count,
            "fast_hash": hex32(fast_hash),
            "borland_hash": hex32(borland_hash),
            "map_hash": hex32(map_hash),
            "overlay_hash": hex32(overlay_hash),
        })
    return {
        "outer": {
            "seed_a": hex32(units[4]),
            "fast_seed": hex32(units[5]),
            "draws": units[6:9],
            "period": units[9],
        },
        "prologue": {
            "period": units[10],
            "period_fast_seed": hex32(units[11]),
            "period_fast_count": units[12],
            "period_fast_hash": hex32(units[13]),
            "surface_seed": hex32(units[14]),
            "surface_fast_seed": hex32(units[15]),
            "surface_fast_count": units[16],
            "surface_fast_hash": hex32(units[17]),
            "rndpat_borland_seed": hex32(units[18]),
            "rndpat_borland_count": units[19],
        },
        "palette": {
            "star_rgb": [signed(value) for value in units[20:23]],
            "id": signed(units[23]),
            "type": signed(units[24]),
            "owner": signed(units[25]),
            "color_base": units[26],
            "entry_borland_count": units[27],
            "entry_borland_hash": hex32(units[28]),
            "entry_borland_seed": hex32(units[29]),
            "mixed_rgbc": [signed(value) for value in units[30:34]],
            "exit_borland_count": units[34],
            "exit_borland_hash": hex32(units[35]),
            "exit_borland_seed": hex32(units[36]),
            "hash": hex32(units[37]),
        },
        "first_cirrus": {
            "reached": bool(units[40]),
            "case": signed(units[41]),
            "ring": signed(units[42]),
            "angle_bits": hex32(units[43]),
            "px": units[44],
            "py": units[45],
            "offset": units[46],
            "value": units[47],
            "overlay_segment": hex32(units[48]),
            "overlay_base": hex32(units[49]),
            "workspace_base": hex32(units[50]),
            "effective_address": hex32(units[51]),
            "effective_byte": units[52],
            "canonical_address": hex32(units[53]),
            "canonical_byte": units[54],
            "gray": signed(units[55]),
            "radius": signed(units[56]),
            "center_x": signed(units[57]),
            "center_y": signed(units[58]),
            "surface_segment": hex32(units[59]),
            "surface_base": hex32(units[60]),
            "sobj": hex32(units[61]),
            "robj": hex32(units[62]),
            "mode": units[63],
        },
        "record_count": record_count,
        "ledger": ledger,
    }


def results(
        header: list[int], buffers: dict[str, bytes],
        diagnostic_units: list[int] | None = None,
) -> dict[str, object]:
    owner = signed(header[9])
    def f64(index: int) -> float:
        return struct.unpack("<d", struct.pack("<II", header[index],
                                               header[index + 1]))[0]
    def f64_bits(index: int) -> str:
        return f"{header[index + 1]:08X}{header[index]:08X}"
    seedval = f64(30)
    palette_base = (128 if owner >= 0 else 192) * 3
    hashes = {
        "surf": hash_record(buffers["surface"][:HASH_EXTENTS["surface"]]),
        "atmo": hash_record(buffers["atmo"]),
        "pal": hash_record(buffers["palette"][palette_base:palette_base + 192]),
        "hm": hash_record(buffers["height"]),
        "oc": hash_record(buffers["objects"]),
        "stex": hash_record(buffers["surftex"][:HASH_EXTENTS["surftex"]]),
        "sky": hash_record(buffers["sky"][:HASH_EXTENTS["sky"]]),
    }
    result = {
        "body": header[6], "body_count": header[7], "type": header[8],
        "status": header[2],
        "owner": owner, "global_surface_seed": signed(header[10]),
        "seedval": seedval, "seedval_bits": f64_bits(30),
        "sctype": header[11], "albedo": signed(header[12]),
        "night": signed(header[13]), "secs": signed(header[14]),
        "geometry": {
            "ray": f64(15), "orb_ray": f64(17), "orb_seed": f64(19),
            "tilt": f64(21), "orb_tilt": f64(23), "orb_ecc": f64(25),
            "orb_orient": f64(27), "plwp": header[29],
        },
        "geometry_bits": {
            "ray": f64_bits(15), "orb_ray": f64_bits(17),
            "orb_seed": f64_bits(19), "tilt": f64_bits(21),
            "orb_tilt": f64_bits(23), "orb_ecc": f64_bits(25),
            "orb_orient": f64_bits(27),
        },
        "gap": buffers["gap"].hex().upper(), "hashes": hashes,
    }
    if diagnostic_units is not None:
        result["diagnostic"] = diagnostic_results(diagnostic_units)
    return result


def dump_buffers(args: argparse.Namespace, buffers: dict[str, bytes]) -> None:
    target = args.dump or os.environ.get("NIVDUMP")
    if not target:
        return
    folder = Path(target)
    folder.mkdir(parents=True, exist_ok=True)
    files = {
        "surfmap.bin": buffers["surface"],
        "atmover.bin": buffers["atmo"],
        "palette.raw": buffers["palette"],
        "height.bin": buffers["height"],
        "objects.bin": buffers["objects"],
        "surftex.bin": buffers["surftex"][:HASH_EXTENTS["surftex"]],
        "sky.bin": buffers["sky"],
    }
    for name, data in files.items():
        (folder / name).write_bytes(data)
    if os.environ.get("NIVDUMP"):
        aliases = {
            "HEIGHT.bin": buffers["height"],
            "OBJECTS.bin": buffers["objects"],
            "SURFTEX.bin": buffers["surftex"][:HASH_EXTENTS["surftex"]],
            "SKY.bin": buffers["sky"],
            "palette.raw": buffers["palette"],
        }
        for name, data in aliases.items():
            (folder / name).write_bytes(data)


def line(label: str, record: dict[str, object]) -> str:
    return (f"{label:<16} len={record['len']:<6} "
            f"fnv={record['fnv']} crc={record['crc']}")


def emit_text(command: str, result: dict[str, object],
              args: argparse.Namespace) -> str:
    h = result["hashes"]
    if command == "planet":
        rows = ["=== PLANET TEXTURE ===",
                f"PLANET body={result['body']} type={result['type']} "
                f"owner={result['owner']} seedval={result['seedval']:.6f}",
                line("surface_map", h["surf"]),
                line("atmo_overlay", h["atmo"]),
                line("palette64", h["pal"])]
    elif command == "sector":
        rows = ["=== SURFACE SECTOR (heightmap) ===",
                f"SECTOR body={result['body']} type={result['type']} "
                f"lon={args.lon} lat={args.lat} "
                f"sctype={result['sctype']} albedo={result['albedo']} "
                f"night={result['night']}",
                f"  global_surface_seed={result['global_surface_seed']}",
                line("heightmap", h["hm"]), line("objectchart", h["oc"]),
                f"gap               len=16   {result['gap']}"]
    elif command == "surftex":
        rows = ["=== SURFACE SECTOR (texture) ===",
                f"SURFTEX body={result['body']} type={result['type']} "
                f"lon={args.lon} lat={args.lat} "
                f"sctype={result['sctype']} albedo={result['albedo']}",
                line("surf_texture", h["stex"]),
                line("sky_texture", h["sky"])]
    else:
        rows = [json.dumps(result, sort_keys=True)]
    return "\n".join(rows) + "\n"


def emit_planet_all(results_by_body: list[dict[str, object]]) -> str:
    rows = [f"=== PLANET TEXTURES (all {len(results_by_body)} bodies) ==="]
    for result in results_by_body:
        hashes = result["hashes"]
        rows.append(
            f"PLANET {result['body']} type={result['type']} "
            f"is_moon={1 if result['owner'] >= 0 else 0} "
            f"surf={hashes['surf']['fnv']} atmo={hashes['atmo']['fnv']} "
            f"pal={hashes['pal']['fnv']}")
    return "\n".join(rows) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Production Lino NIVGEN output harness")
    parser.add_argument(
        "command", choices=("planet", "planet-all", "sector", "surftex", "json"))
    parser.add_argument("-x", type=int, required=True)
    parser.add_argument("-y", type=int, required=True)
    parser.add_argument("-z", type=int, required=True)
    parser.add_argument("-p", type=int, default=0)
    parser.add_argument("-lon", type=int, default=0)
    parser.add_argument("-lat", type=int, default=60)
    parser.add_argument("-secs", type=int, default=0)
    parser.add_argument("-sc", type=int, default=-1)
    parser.add_argument("-albedo", type=int, default=-1)
    parser.add_argument("-night", type=int, default=0)
    parser.add_argument("-gap")
    parser.add_argument("-o")
    parser.add_argument("-dump")
    parser.add_argument(
        "--diagnostic", action="store_true",
        help="append and decode the opt-in surface boundary trailer")
    parser.add_argument("--build", action="store_true")
    parser.add_argument(
        "--exe", help="use this prebuilt native harness instead of compiling")
    parser.add_argument("--timeout", type=int, default=180)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "planet-all":
            args.p = 0
            header, buffers, diagnostic_units = run_lino(args)
            all_results = [results(header, buffers, diagnostic_units)]
            body_count = int(all_results[0]["body_count"])
            args.build = False
            for body in range(1, body_count):
                args.p = body
                header, buffers, diagnostic_units = run_lino(args)
                all_results.append(results(header, buffers, diagnostic_units))
            text = emit_planet_all(all_results)
            if args.o:
                with open(args.o, "a", encoding="utf-8", newline="\n") as stream:
                    stream.write(text)
            else:
                sys.stdout.write(text)
            return 0
        header, buffers, diagnostic_units = run_lino(args)
        result = results(header, buffers, diagnostic_units)
        dump_buffers(args, buffers)
        text = emit_text(args.command, result, args)
        if args.o:
            with open(args.o, "a", encoding="utf-8", newline="\n") as stream:
                stream.write(text)
        else:
            sys.stdout.write(text)
        return 0
    except Exception as exc:
        print(f"nivtest: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
