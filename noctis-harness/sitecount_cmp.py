# Runs the whole 3x3 grid and prints it. Exits non-zero on any disagreement.
#
#                        frag (stock)  limb (stock)  *% (patched)   anchor
#   sitecount-mul64.bin       .             .             .         Python bignum
#   sitecount-rnd.bin         .             .             .         Python asm-oracle + niv-lr C
#   sitecount-galaxy2.bin     .             .             .         frozen galaxy.bin
#
# The columns agreeing with each other is the weak result: three routes could
# in principle share a wrong idea about the hardware. What makes it non-circular
# is the anchor column, where every row is checked against something written in
# another language, by another author, or in exact arithmetic.
#
#   python noctis-harness/sitecount_cmp.py           full grid, all nine builds
#   python noctis-harness/sitecount_cmp.py --quick   verify already-built .bins

import hashlib
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sitecount_run as R
import sitecount_vectors as V
import sitecount_rndoracle as O

WORK = R.WORK
BACKENDS = ("frag", "limb", "star")

# (program source, live output name, fields per record)
PROGRAMS = [
    ("sitecount_mul64.txt", "sitecount-mul64.bin", 4),
    ("sitecount_rnd.txt", "sitecount-rnd.bin", 2),
    ("sitecount_galaxy2.txt", "sitecount-galaxy2.bin", 5),
]

GALAXY_REF = os.path.join(WORK, "galaxy.bin")


def per_backend(stem, be):
    root, ext = os.path.splitext(stem)
    return os.path.join(WORK, "%s-%s%s" % (root, be, ext))


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest().upper()


def build_all():
    for be in BACKENDS:
        compiler, cpu = R.select_backend(be)
        for src, out, _ in PROGRAMS:
            R.build_and_run(os.path.join(WORK, src), os.path.join(WORK, out),
                            compiler=compiler, cpu=cpu, timeout=60, quiet=True)
            shutil.copyfile(os.path.join(WORK, out), per_backend(out, be))
        print("  built and ran all %d programs under %-5s (%s, -Cpu %s)"
              % (len(PROGRAMS), be, os.path.basename(compiler), cpu))


def check_anchors(fail):
    print()
    print("EXTERNAL ANCHORS (each row checked against something not under test)")

    pairs = V.vectors()
    exp = V.expected(pairs)
    rnd_ref = O.py_draws()
    rnd_c = O.c_draws()
    if rnd_ref != rnd_c:
        fail("fast_random: the Python and C oracles disagree with each other")
        return
    print("  fast_random oracles: python == niv-lr C over %d draws" % len(rnd_ref))

    galaxy_ref = open(GALAXY_REF, "rb").read()
    print("  galaxy reference   : %s  %d bytes  %s"
          % (os.path.basename(GALAXY_REF), len(galaxy_ref), sha(GALAXY_REF)[:24]))

    for be in BACKENDS:
        # --- mul64 vs Python arbitrary precision -------------------------
        got = R.read_units(per_backend("sitecount-mul64.bin", be), signed=False)
        if len(got) != len(exp) * 4:
            fail("mul64/%s: %d units, expected %d" % (be, len(got), len(exp) * 4))
        bad = sum(1 for k, e in enumerate(exp) if tuple(got[k * 4:k * 4 + 4]) != e)
        print("  mul64  /%-5s vs Python bignum   : %d pairs, %d mismatches"
              % (be, len(exp), bad))
        if bad:
            fail("mul64/%s disagrees with exact arithmetic" % be)

        # the table must be able to tell MUL from IMUL at all
        differing = sum(1 for k in range(len(exp))
                        if got[k * 4 + 1] != got[k * 4 + 3])
        if differing == 0:
            fail("mul64/%s: signed and unsigned high halves never differ - "
                 "the vector table cannot detect a MUL/IMUL swap" % be)

        # --- fast_random vs both oracles ---------------------------------
        g = R.read_units(per_backend("sitecount-rnd.bin", be), signed=False)
        rows = [(g[i * 2], g[i * 2 + 1]) for i in range(len(g) // 2)]
        if len(rows) != len(rnd_ref):
            fail("rnd/%s: %d draws, expected %d" % (be, len(rows), len(rnd_ref)))
        bad = sum(1 for i in range(min(len(rows), len(rnd_ref)))
                  if rows[i] != rnd_ref[i])
        print("  rnd    /%-5s vs both oracles     : %d draws, %d mismatches"
              % (be, len(rows), bad))
        if bad:
            fail("rnd/%s disagrees with the fast_random oracles" % be)

        # --- galaxy vs the frozen, externally verified reference ----------
        blob = open(per_backend("sitecount-galaxy2.bin", be), "rb").read()
        same = blob == galaxy_ref
        print("  galaxy /%-5s vs frozen galaxy.bin: %s (%d bytes)"
              % (be, "IDENTICAL" if same else "DIFFERS", len(blob)))
        if not same:
            fail("galaxy/%s does not reproduce galaxy.bin" % be)


def check_grid(fail):
    print()
    print("SHA-256 GRID (every column must be identical down its row)")
    print("  %-24s %-18s %-18s %-18s" % ("output", "frag (stock)",
                                         "limb (stock)", "*% (patched)"))
    for _, out, fields in PROGRAMS:
        digests = []
        for be in BACKENDS:
            path = per_backend(out, be)
            digests.append(sha(path)[:16])
            size = os.path.getsize(path)
            if size % (fields * 4):
                fail("%s: %d bytes is not a whole number of %d-field records"
                     % (path, size, fields))
        print("  %-24s %-18s %-18s %-18s" % (out, *digests))
        if len(set(digests)) != 1:
            fail("%s: backends disagree" % out)


def main():
    failures = []

    def fail(msg):
        failures.append(msg)
        print("  FAIL: %s" % msg)

    if "--quick" not in sys.argv:
        print("BUILDING (3 backends x %d programs = %d builds)"
              % (len(PROGRAMS), 3 * len(PROGRAMS)))
        build_all()

    check_grid(fail)
    check_anchors(fail)

    print()
    if failures:
        print("RESULT: %d failure(s)" % len(failures))
        for f in failures:
            print("  - %s" % f)
        return 1
    print("RESULT: all three backends agree with each other and with every "
          "external anchor.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
