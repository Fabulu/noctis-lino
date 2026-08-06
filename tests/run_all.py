"""Run the Noctis IV port's regression suite.

    python tests/run_all.py            everything
    python tests/run_all.py galaxy     only tests whose name contains "galaxy"
    python tests/run_all.py site       only the site-census tests (no builds)
    python tests/run_all.py star       only the Tier 2 catalogue tests
    python tests/run_all.py brtl       only the Wave 1 LCG test
    python tests/run_all.py wave2      only the Wave 2 decoder pin
    python tests/run_all.py float      only the Wave 3 float contract
    python tests/run_all.py nearstar   only the Wave 4 generation test
    python tests/run_all.py wave5      only the Wave 5 buffer model / framebuffer

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
test_nearstar does the same for the Wave 4 driver and its six libraries, and
additionally builds seven deliberately sabotaged copies of them; it also needs
the DL.EXE captures under tests/gen/recon_c, and reports the leg as skipped
rather than passing quietly if they are missing.

test_wave5 rebuilds tests/gen/w5 from scratch on every run - the three Wave 5
libraries out of work/, the Wave 3 float engine, and its own probe - and then
builds twenty-three deliberately broken variants of them. It needs the DOS
sources under the noctis clone root, because the workspace layout it grades is
parsed out of NOCTIS-D.H and NOCTIS.CPP rather than typed in. It also builds
ONE variant that opens a 320x200 window for about two seconds; --nodisp turns
that off. Two of its checks are XFAIL - defects the code as shipped still
has, listed in docs-notes/BUFFERMODEL.md section 10 - and it fails if one of
them starts passing without the document being updated. Wave 5b's three
original XFAILs were converted to positive assertions; these two are new.
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
    ("test_nearstar.py", "Wave 4 draw accounting, graded by STARMAP.BIN and DL.EXE"),
    ("test_wave5.py", "Wave 5 buffer model, framebuffer and the 54.9254 ms tick"),
    ("test_geometry.py", "the cast boundary from __ftol; geometry bit-exact between engines but UNGRADED against 1996"),
    ("test_raster.py", "Wave 6a: rasteriser pages byte-exact over 64,000 pixels; projection measured at delta 0"),
    ("test_spheres.py", "Wave 6b: spheres, background and .NCC loading byte-exact over 2.56 MB of pages; the table's projective model bounded and cross-validated"),
]

# Tests that have a slower, more complete mode of their own. run_all always
# takes the fast path; the flag is for when you are about to trust the result.
DEEPER = {"test_brtlrand.py": "--exhaustive",
          "test_floatcontract.py": "--K 96"}

# The reverse of DEEPER: modes that trade coverage for speed. Named here so a
# reader knows they exist, and so nobody mistakes the fast path for the test.
# test_nearstar --quick skips the seven sabotages, which is exactly the part
# that shows the graders can fail; run_all never takes it.
FASTER = {"test_nearstar.py": "--quick  (skips the sabotages - not a pass)",
          "test_wave5.py": "--quick  (skips the sabotages - not a pass); "
                           "--nodisp skips the one probe that opens a window"}


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
    for name, flag in sorted(FASTER.items()):
        if any(r[0] == name for r in results):
            print("  note: %s has a faster INCOMPLETE mode: python tests/%s %s"
                  % (name, name, flag))
    print()
    print("%d passed, %d failed, %.1fs total" % (len(results) - failed, failed, time.time() - t0))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
