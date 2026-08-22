"""NIVGEN binary64 geometry mode and historical-game isolation regression."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tools"))

import linoharness as lh  # noqa: E402
import nivtest  # noqa: E402


COORDS = (-108980592, 25731476, -852320)
GEOMETRY_BITS = {
    "ray": "3F9930BE0DED288D",
    "orb_ray": "408C1304724CFD8C",
    "orb_seed": "407CAB3333333333",
    "tilt": "3FF78D4FDF3B645A",
    "orb_tilt": "3FD82DE00D1B7176",
    "orb_ecc": "3FEDE353F7CED916",
    "orb_orient": "40125C6190C2DF86",
}
HASHES = {
    "surf": "949B1F26",
    "atmo": "4927A000",
    "pal": "85311E10",
    "hm": "97022FD7",
    "oc": "22913F4E",
    "stex": "0D52F001",
    "sky": "4119AE46",
}
TAGGED_ROSETTA_HASHES = {
    "surf": "390A2CCB",
    "atmo": "114562E8",
    "pal": "26961E4A",
    "hm": "97022FD7",
    "oc": "22913F4E",
    "stex": "0D52F001",
    "sky": "1E308D29",
}
ATMO_FIXTURES = (
    ("GRUPA 5|14", (-61439376, 29916264, 239760), 14,
     "000000000000000000000000C5096055", "01F046A9"),
    ("GRUPA 5|11", (-61439376, 29916264, 239760), 11,
     "000000000000000000000000C5096055", "174C4959"),
)
RANDOM_SKY_FIXTURES = (
    ("SOKUN|21", (-1323161232, -1306991, -1179428207), 21,
     236, 89, 106080, 2, "F9DCB00A"),
    ("COREGALAX|4", (-72910640, -1436861, 55966868), 4,
     38, 35, 2600381, 2, "1B1D7307"),
    ("JUNEA|21", (-61232592, 29255171, 664579), 21,
     207, 81, 160402, 1, "B7678039"),
)


def main() -> int:
    checks = lh.Check("NIVGEN binary64 geometry mode")
    fpabi = (ROOT / "work" / "fp" / "fpabi.txt").read_text(encoding="utf-8")
    nstopo = (ROOT / "work" / "nstopo.txt").read_text(encoding="utf-8")
    geoconv = (ROOT / "work" / "geoconv.txt").read_text(encoding="utf-8")
    suseed = (ROOT / "work" / "suseed.txt").read_text(encoding="utf-8")
    supaint = (ROOT / "work" / "supaint.txt").read_text(encoding="utf-8")
    vhground = (ROOT / "work" / "vhground.txt").read_text(encoding="utf-8")
    vhnivgen = (ROOT / "work" / "vhnivgen.txt").read_text(encoding="utf-8")
    vhgame = (ROOT / "work" / "vhgame.txt").read_text(encoding="utf-8")
    worker_build = (ROOT / "build" / "build_nivtest.sh").read_text(
        encoding="utf-8")

    checks.eq(fpabi.count("nivgenf64 = 0;"), 1,
              "the shared FP ABI defaults to historical x87 arithmetic")
    checks.eq(suseed.count("nivgenf64"), 0,
              "surface code uses the precision selector from the shared FP ABI")
    checks.eq(nstopo.count("nsgeometryf64"), 0,
              "the precision selector is shared beyond nearstar geometry")
    checks.ok("=> GeoKMulChopSpill;" in nstopo and
              "=> GeoSeedTiltChopSpill;" in nstopo,
              "reference mode selects declared binary64 cast boundaries")
    checks.ok('"GeoEccStore2000F64"' in geoconv and
              "? [FI] = 0 -> GeoEcc f64 quotient ready;" in geoconv,
              "reference eccentricity rounds division and subtraction separately")
    checks.ok("VHGND rotation seed calculate f64" in vhground,
              "reference rotation seed multiplies stored binary64 factors")
    checks.eq(supaint.count("=> SU NIVGEN f64 spill;"), 4,
              "reference surface coordinates spill both products and sums")
    checks.ok("=> XToF64;" in supaint and "=> XFromF64;" in supaint,
              "surface coordinate spills round and reload binary64 values")
    checks.eq(vhnivgen.count("[nivgenf64] = 1;"), 1,
              "only the NIVGEN driver enables reference precision")
    checks.eq(vhnivgen.count("[nivgenf64] = 0;"), 2,
              "both successful and invalid NIVGEN exits restore historical mode")
    checks.ok(
        "A = [GRgseed]; A % 15; A + 25; A + [NHtmp]; A '* 2;" in vhnivgen
        and "A = [GRlat]; A '/ 2; [GRlat] = A;" in vhnivgen,
        "type-3 seed correction compares exact doubled half-degree latitude")
    checks.ok("vhnivgen" not in vhgame.lower(),
              "the shipping game does not link the NIVGEN-only driver")
    checks.ok(
        'if [ "$source_env" = "$staged_env" ]' in worker_build
        and worker_build.index('if [ "$source_env" = "$staged_env" ]')
        < worker_build.index('rm -rf "$root/work" "$staged_env"'),
        "the macOS worker refuses a destructive staging-environment alias")
    checks.ok(
        'fix_x64_pack_flags.py" "$repo/main/cpu/x64.bin"' in worker_build
        and 'cat > "$1/cpu/x64.bin"' in worker_build
        and '--env:$2--src:$3' in worker_build,
        "the macOS worker audits and stages this checkout's x64 CPU pack")
    checks.ok(
        "nivtest-build.provenance.txt" in worker_build
        and "runtime_prefix_sha256" in worker_build
        and "system_pack_sha256" in worker_build
        and "compiler_sha256" in worker_build,
        "the macOS worker records external compiler/runtime provenance")
    checks.ok(
        all(value in worker_build for value in TAGGED_ROSETTA_HASHES.values())
        and "first_cirrus.get(\"reached\")" in worker_build
        and 'mv "$candidate" "$output"' in worker_build,
        "the macOS worker promotes only a seven-hash tagged fixture candidate")

    try:
        executable = nivtest.ensure_build(True)
        args = argparse.Namespace(
            x=COORDS[0], y=COORDS[1], z=COORDS[2], p=5,
            lon=0, lat=60, secs=0, sc=-1, albedo=-1, night=0,
            gap="000000000000000000000000C509F054", build=False,
            timeout=180, dump=None, o=None, exe=str(executable), diagnostic=False,
        )
        header, buffers, diagnostics = nivtest.run_lino(args)
        result = nivtest.results(header, buffers, diagnostics)
    except Exception as error:  # retain one clear failure instead of a traceback
        checks.ok(False, "production NIVGEN harness builds and runs", str(error))
        return checks.done()

    checks.eq(result["type"], 2, "MAGILLA PRIME body 5 remains a type-2 planet")
    checks.eq(result["geometry_bits"], GEOMETRY_BITS,
              "MAGILLA PRIME geometry matches the public binary64 hypothesis")
    checks.eq(result["seedval_bits"], "41D624674DAC7AA5",
              "the complete left-to-right rotation seed is exact")
    got_hashes = {name: result["hashes"][name]["fnv"] for name in HASHES}
    checks.eq(got_hashes, HASHES,
              "all seven default-site public hashes are exact")

    for key, coords, body, gap, expected_atmo in ATMO_FIXTURES:
        args = argparse.Namespace(
            x=coords[0], y=coords[1], z=coords[2], p=body,
            lon=0, lat=60, secs=0, sc=-1, albedo=-1, night=0,
            gap=gap, build=False, timeout=180, dump=None, o=None,
            exe=str(executable), diagnostic=False,
        )
        try:
            header, buffers, diagnostics = nivtest.run_lino(args)
            fixture = nivtest.results(header, buffers, diagnostics)
        except Exception as error:
            checks.ok(False, f"{key} atmosphere fixture runs", str(error))
            continue
        checks.eq(fixture["type"], 3, f"{key} remains a type-3 planet")
        checks.eq(fixture["hashes"]["atmo"]["fnv"], expected_atmo,
                  f"{key} atmosphere uses binary64 product and sum boundaries")

    gap = "000000000000000000000000C5096055"
    for (key, coords, body, lon, lat, expected_seed, expected_sctype,
         expected_sky) in RANDOM_SKY_FIXTURES:
        args = argparse.Namespace(
            x=coords[0], y=coords[1], z=coords[2], p=body,
            lon=lon, lat=lat, secs=0, sc=-1, albedo=-1, night=0,
            gap=gap, build=False, timeout=180, dump=None, o=None,
            exe=str(executable), diagnostic=False,
        )
        try:
            header, buffers, diagnostics = nivtest.run_lino(args)
            fixture = nivtest.results(header, buffers, diagnostics)
        except Exception as error:
            checks.ok(False, f"{key} random-sky fixture runs", str(error))
            continue
        checks.eq(fixture["global_surface_seed"], expected_seed,
                  f"{key} preserves the half-degree seed increment")
        checks.eq(fixture["sctype"], expected_sctype,
                  f"{key} retains the public random-site scenario")
        checks.eq(fixture["hashes"]["sky"]["fnv"], expected_sky,
                  f"{key} random sky matches the public generator")

    forbidden = ("MAGILLA", "GRUPA 5", "SOKUN", "COREGALAX", "JUNEA",
                 "-108980592", "25731476", "-852320", "-61439376",
                 "29916264", "239760", "-1323161232", "-1306991",
                 "-1179428207", "-72910640", "-1436861", "55966868",
                 "-61232592", "29255171", "664579", "949B1F26",
                 "4927A000", "85311E10", "01F046A9", "174C4959",
                 "F9DCB00A", "1B1D7307", "B7678039")
    production = fpabi + nstopo + geoconv + suseed + supaint + vhground + vhnivgen
    checks.eq([token for token in forbidden if token in production], [],
              "production precision policy contains no fixture-specific exception")
    return checks.done()


if __name__ == "__main__":
    raise SystemExit(main())
