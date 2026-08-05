"""Run the Noctis IV port's regression suite.

    python tests/run_all.py            everything
    python tests/run_all.py galaxy     only tests whose name contains "galaxy"
    python tests/run_all.py site       only the site-census tests (no builds)
    python tests/run_all.py star       only the Tier 2 catalogue tests
    python tests/run_all.py brtl       only the Wave 1 LCG test
    python tests/run_all.py wave2      only the Wave 2 decoder pin
    python tests/run_all.py float      only the Wave 3 float contract

Each test is a standalone program - `python tests/test_galaxy.py` works on its
own and prints the same output - so this driver only sequences them and sums up
the exit codes. Non-zero means something in the port drifted.

Everything is rebuilt from source on every run: both lino programs, the C
reference, the Python references, and the deliberately-wrong negative controls.
Nothing is graded against a stored .bin, because a stored .bin is exactly the
thing that goes stale without anyone noticing.

Prerequisites: the extended toolchain (main/lib/gen/compiler114m.exe and
main/cpu/i386m.bin) and gcc on PATH. test_toolchain checks the first and says
what to do about it; the C reference needs the second. The two census tests
and the four star tests also need the reference clones under
C:\\programmieren\\noctis - the DOS sources and the real STARMAP.BIN.

The star tests never write into work/. Each copies the programme it is testing
into its own sandbox under tests/gen with only the file-name literals changed,
so the delivered Tier 2 artifacts are left exactly as the pipeline left them.
"""

import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))

TESTS = [
    ("test_toolchain.py", "extended toolchain present; wrong pairings refused"),
    ("test_galaxy.py", "the *% rewrite is bit-exact with C, Python and the fragment"),
    ("test_galaxy_stress.py", "same, on coordinates the acceptance sweep cannot reach"),
    ("test_mulsplit.py", "the *% operand/register contract galaxy2.txt cannot self-test"),
    ("test_sitecensus.py", "Noctis IV has exactly 20 multiply sites, 5 that matter"),
    ("test_sitevectors.py", "the operand table fits its buffer and can see signedness"),
    ("test_fastrandom.py", "fast_random, the unsigned 64-bit site, on all three backends"),
    ("test_mul64clobber.py", "the Mul64 interface damages only the registers it declares"),
    ("test_starkeys.py", "the catalogue decoder and the key-table guards"),
    ("test_starcatalogue.py", "the sweep's hit set against the real STARMAP.BIN"),
    ("test_starwindow.py", "the 1e10 acceptance window and the outward scan"),
    ("test_staranchor.py", "the author's three hard-coded stars, uniquely"),
    ("test_brtlrand.py", "Borland's rand/srand/random over all 65,536 seeds"),
    ("test_wave2.py", "the random() argument type and zrandom's operand order"),
    ("test_floatcontract.py", "the Wave 3 float contract, graded by STARMAP.BIN"),
]

# Tests that have a slower, more complete mode of their own. run_all always
# takes the fast path; the flag is for when you are about to trust the result.
DEEPER = {"test_brtlrand.py": "--exhaustive",
          "test_floatcontract.py": "--K 96"}


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    selected = [t for t in TESTS if which in t[0]]
    if not selected:
        print("no test matches %r; known: %s" % (which, ", ".join(t[0] for t in TESTS)))
        return 2

    results = []
    t0 = time.time()
    for name, blurb in selected:
        started = time.time()
        p = subprocess.run([sys.executable, os.path.join(HERE, name)], cwd=HERE)
        results.append((name, blurb, p.returncode, time.time() - started))
        print()

    print("=" * 72)
    print("SUITE SUMMARY")
    print("=" * 72)
    failed = 0
    for name, blurb, rc, secs in results:
        print("  %-4s %-24s %5.1fs  %s" % ("PASS" if rc == 0 else "FAIL", name, secs, blurb))
        failed += (rc != 0)
    print()
    for name, flag in sorted(DEEPER.items()):
        if any(r[0] == name for r in results):
            print("  note: %s has a slower complete mode: python tests/%s %s"
                  % (name, name, flag))
    print()
    print("%d passed, %d failed, %.1fs total" % (len(results) - failed, failed, time.time() - t0))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
