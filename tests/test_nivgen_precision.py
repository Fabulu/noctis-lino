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
ATMO_FIXTURES = (
    ("GRUPA 5|14", (-61439376, 29916264, 239760), 14,
     "000000000000000000000000C5096055", "01F046A9"),
    ("GRUPA 5|11", (-61439376, 29916264, 239760), 11,
     "000000000000000000000000C5096055", "174C4959"),
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
    checks.ok("vhnivgen" not in vhgame.lower(),
              "the shipping game does not link the NIVGEN-only driver")

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

    forbidden = ("MAGILLA", "GRUPA 5", "-108980592", "25731476",
                 "-852320", "-61439376", "29916264", "239760",
                 "949B1F26", "4927A000", "85311E10", "01F046A9",
                 "174C4959")
    production = fpabi + nstopo + geoconv + suseed + supaint + vhground + vhnivgen
    checks.eq([token for token in forbidden if token in production], [],
              "production precision policy contains no fixture-specific exception")
    return checks.done()


if __name__ == "__main__":
    raise SystemExit(main())
