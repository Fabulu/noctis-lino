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


def main() -> int:
    checks = lh.Check("NIVGEN binary64 geometry mode")
    nstopo = (ROOT / "work" / "nstopo.txt").read_text(encoding="utf-8")
    geoconv = (ROOT / "work" / "geoconv.txt").read_text(encoding="utf-8")
    vhground = (ROOT / "work" / "vhground.txt").read_text(encoding="utf-8")
    vhnivgen = (ROOT / "work" / "vhnivgen.txt").read_text(encoding="utf-8")
    vhgame = (ROOT / "work" / "vhgame.txt").read_text(encoding="utf-8")

    checks.eq(nstopo.count("nsgeometryf64\t= 0;"), 1,
              "the shared generator defaults to historical x87 geometry")
    checks.ok("=> GeoKMulChopSpill;" in nstopo and
              "=> GeoSeedTiltChopSpill;" in nstopo,
              "reference mode selects declared binary64 cast boundaries")
    checks.ok('"GeoEccStore2000F64"' in geoconv and
              "? [FI] = 0 -> GeoEcc f64 quotient ready;" in geoconv,
              "reference eccentricity rounds division and subtraction separately")
    checks.ok("VHGND rotation seed calculate f64" in vhground,
              "reference rotation seed multiplies stored binary64 factors")
    checks.eq(vhnivgen.count("[nsgeometryf64] = 1;"), 1,
              "only the NIVGEN driver enables reference precision")
    checks.eq(vhnivgen.count("[nsgeometryf64] = 0;"), 2,
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

    forbidden = ("MAGILLA", "-108980592", "25731476", "-852320",
                 "949B1F26", "4927A000", "85311E10")
    production = nstopo + geoconv + vhground + vhnivgen
    checks.eq([token for token in forbidden if token in production], [],
              "production precision policy contains no fixture-specific exception")
    return checks.done()


if __name__ == "__main__":
    raise SystemExit(main())
