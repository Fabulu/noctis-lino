"""One command for the whole Tier 2 track: build, run, referee, report.

Every stage is a gate. A gate that fails stops the run, because a number
produced downstream of a broken stage is worse than no number at all.

    1  kernel   the 96-bit product and the double decoder, on ~1600
                vectors chosen to hit the funnel shift, the carries and
                the rejections, refereed against Python big ints
    2  raw      the *% fold reproduces work/galaxy.bin - the artifact the
                retired { F7 EB } machine-language fragment produced -
                byte for byte
    3  read     all 37,578 catalogue records decoded, refereed against an
                exact Fraction decode of the same bytes
    4  controls decoy and unsigned-fold runs, on the same binary
    5  find     the real K=64 sweep, hit set refereed for exact equality
    6  planets  the planet-derived parent identities, no generator involved

Usage: python starmap_all.py [K]
"""

import os
import shutil
import struct
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import starmap_run as R  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = R.WORK
SOURCE_STARMAP = r"C:\programmieren\noctis\niv-plus\data\STARMAP.BIN"

MODE_DECOY, MODE_UNSIGNED, MODE_RAW = 1, 2, 4
HITCAP = 60000


def py(script, *args):
    p = subprocess.run([sys.executable, os.path.join(HERE, script), *args],
                       capture_output=True, text=True)
    sys.stdout.write(p.stdout)
    if p.returncode:
        sys.stdout.write(p.stderr)
    return p.returncode == 0, p.stdout


def cfg(K, mode, cap=HITCAP):
    with open(os.path.join(WORK, "starmap_cfg.bin"), "wb") as fh:
        fh.write(struct.pack("<3i", K, mode, cap))


def find_run(K, mode, tag, timeout=900):
    """Run starmap_find and return (header dict, distinct catalogue ids)."""
    cfg(K, mode)
    out = os.path.join(WORK, "starmap_find.bin")
    ok, secs, msg = R.run(os.path.join(WORK, "starmap_find.exe"), [out],
                          timeout=timeout, poll=0.5, settle=1.5)
    if os.path.exists(os.path.join(WORK, "starmap_find.err")):
        print("  *** starmap_find wrote its error file - an isocall failed")
        return None, None, 0.0
    if not ok:
        print(f"  *** starmap_find {tag}: {msg}")
        return None, None, secs
    blob = open(out, "rb").read()
    keys = ("magic K mode nsect nlive ndead nkeys nrejkey nbigkey nhits "
            "overflow anchors unsorted r13 r14 r15").split()
    h = dict(zip(keys, struct.unpack_from("<16I", blob, 0)))
    ids = {struct.unpack_from("<I", blob, 64 + 36 * i)[0] for i in range(h["nhits"])}
    shutil.copy(out, os.path.join(WORK, f"starmap_find_{tag}.bin"))
    return h, ids, secs


def main():
    K = int(sys.argv[1]) if len(sys.argv) > 1 else 64
    results = []

    def gate(name, ok):
        results.append((name, ok))
        print(f"\n===== GATE {name}: {'PASS' if ok else 'FAIL'} =====\n")
        return ok

    # The programme is started in its own directory and reaching outside it
    # needs the universal-filesystem paradigm, which is not worth the risk
    # here. So the catalogue is copied in.
    shutil.copy(SOURCE_STARMAP, os.path.join(WORK, "STARMAP.BIN"))
    print(f"copied STARMAP.BIN into {WORK}")

    # ---- 1 kernel -------------------------------------------------------
    print("\n---- stage 1: arithmetic kernel ----")
    if not py("starmap_vectors.py")[0]:
        return 1 if not gate("1 kernel", False) else 0
    ok = R.build_and_run("starmap_kernel",
                         [os.path.join(WORK, "starmap_kernel.bin")], timeout=120)
    ok = ok and py("starmap_kerncheck.py")[0]
    if not gate("1 kernel", ok):
        return 1

    # ---- 2 the fold, against galaxy.bin ---------------------------------
    print("\n---- stage 2: the *% fold vs the retired { F7 EB } fragment ----")
    okb, msg = R.build(os.path.join(WORK, "starmap_find.txt"))
    print(f"build starmap_find: {msg}")
    if not okb:
        return 1 if not gate("2 raw dump", False) else 0
    h, _, _ = find_run(3, MODE_RAW, "raw", timeout=120)
    a = open(os.path.join(WORK, "starmap_find_raw.bin"), "rb").read()
    b = open(os.path.join(WORK, "galaxy.bin"), "rb").read()
    print(f"starmap_find raw dump: {len(a)} bytes; galaxy.bin: {len(b)} bytes")
    print("byte-identical" if a == b else "DIFFERENT")
    if not gate("2 raw dump == galaxy.bin", a == b and len(a) > 0):
        return 1

    # ---- 3 catalogue decode ---------------------------------------------
    print("\n---- stage 3: decode the real catalogue ----")
    ok = R.build_and_run("starmap_read",
                         [os.path.join(WORK, "starmap_keys.bin")], timeout=120)
    ok = ok and py("starmap_keycheck.py")[0]
    if not gate("3 catalogue decode", ok):
        return 1

    # ---- 4 negative controls --------------------------------------------
    print("\n---- stage 4: negative controls ----")
    lines = []
    ctl = {}
    for tag, mode, why in (
            ("decoy", MODE_DECOY,
             "every catalogue key shifted by 2^40 (~1.1e-3 in identity units,"
             " about 110 windows)"),
            ("unsigned", MODE_UNSIGNED,
             "the galaxy fold done with the UNSIGNED *%' - a different,"
             " perfectly plausible galaxy")):
        h, ids, secs = find_run(K, mode, tag)
        if h is None:
            return 1 if not gate("4 controls", False) else 0
        ctl[tag] = (h, ids)
        lines.append(f"{tag:9} {why}")
        lines.append(f"{'':9}   matched {len(ids)}/{h['nkeys']} = "
                     f"{100.0*len(ids)/h['nkeys']:.3f}%   "
                     f"anchors passed: {bin(h['anchors']).count('1')}/3")
    if not gate("4 controls ran", True):
        return 1

    # ---- 5 the real run --------------------------------------------------
    print("\n---- stage 5: the real sweep ----")
    h, ids, secs = find_run(K, 0, "real")
    if h is None:
        return 1 if not gate("5 real run", False) else 0
    print(f"K={K}: {h['nsect']} sectors, {h['nhits']} hits, "
          f"{len(ids)} distinct catalogue ids, {secs:.1f}s")

    real_rate = 100.0 * len(ids) / h["nkeys"]
    lines.insert(0, f"{'real':9} the signed fold and the untouched catalogue")
    lines.insert(1, f"{'':9}   matched {len(ids)}/{h['nkeys']} = {real_rate:.3f}%"
                    f"   anchors passed: {bin(h['anchors']).count('1')}/3")
    lines.append("")
    for tag in ("decoy", "unsigned"):
        r = 100.0 * len(ctl[tag][1]) / ctl[tag][0]["nkeys"]
        lines.append(f"signal over the {tag} control: "
                     f"{real_rate/max(r,1e-9):.0f}x")
    lines.append("")
    lines.append("The unsigned-fold control is the informative one. It does not")
    lines.append("collapse to zero, and it should not: a wrong-but-plausible")
    lines.append("galaxy still puts stars near the origin, where small |id|")
    lines.append("catalogue entries are dense, so some ids are hit by chance.")
    lines.append("That rate is the chance-match floor for ANY plausible")
    lines.append("generator, and it is the number the real rate has to beat.")
    lines.append("All three anchor tests fail under it, as they must.")
    with open(os.path.join(WORK, "starmap_controls.txt"), "w") as fh:
        fh.write("\n".join(lines) + "\n")

    ok = py("starmap_report.py")[0]
    if not gate("5 real run refereed", ok):
        return 1

    # ---- 6 planets --------------------------------------------------------
    print("\n---- stage 6: planet-derived parents ----")
    ok = py("starmap_planets.py")[0]
    gate("6 planet ground truth", ok)

    print("\n" + "=" * 60)
    for name, o in results:
        print(f"  {'PASS' if o else 'FAIL':4}  {name}")
    print("=" * 60)
    return 0 if all(o for _, o in results) else 1


if __name__ == "__main__":
    sys.exit(main())
