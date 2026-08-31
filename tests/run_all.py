"""Run the Noctis IV port's regression suite.

    python tests/run_all.py            lean regression suite
    python tests/run_all.py --deep     historical exhaustive audits too
    python tests/run_all.py galaxy     only tests whose name contains "galaxy"
    python tests/run_all.py site       only the site-census tests (no builds)
    python tests/run_all.py star       only the Tier 2 catalogue tests
    python tests/run_all.py brtl       only the Wave 1 LCG test
    python tests/run_all.py wave2      only the Wave 2 decoder pin
    python tests/run_all.py float      only the Wave 3 float contract
    python tests/run_all.py nearstar   only the Wave 4 generation test
    python tests/run_all.py wave5      only the Wave 5 buffer model / framebuffer
    python tests/run_all.py geometry   only the cast-boundary / geometry test
    python tests/run_all.py raster     only the Wave 6a rasteriser
    python tests/run_all.py spheres    only the Wave 6b spheres and .NCC loading

A full run warns if tests/ contains an unregistered test_*.py.  It does not
turn that process-hygiene issue into a product-development blocker.

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
    ("test_inttof.py", "guarded native IntToF is bit-exact through inclusive binary32 bounds, falls back exactly outside them, and preserves FS0"),
    ("test_fractional_pow.py", "fractional crater power is exact against historical x87 with intact soft-stack state"),
    ("test_nearstar.py", "Wave 4 draw accounting, graded by STARMAP.BIN and DL.EXE"),
    ("test_wave5.py", "Wave 5 buffer model, framebuffer and the 54.9254 ms tick"),
    ("test_geometry.py", "the cast boundary from __ftol; geometry bit-exact between engines but UNGRADED against 1996"),
    ("test_geoconv_zero.py", "zero geometry numerators bypass the normalized-only quotient core without changing nonzero results or FP state"),
    ("test_suseed_zero.py", "zero surface contrast numerators bypass the normalized-only quotient core without changing nonzero results or FP state"),
    ("test_grnd_zero.py", "zero tree-parameter numerators bypass the normalized-only quotient core without changing historical scales or FP state"),
    ("test_tree_polar_madd.py", "guarded p53 tree polar multiply-adds fall back on every binary32 midpoint and remain exact against the p64 schedule"),
    ("test_raster.py", "Wave 6a: rasteriser pages byte-exact over 64,000 pixels; projection measured at delta 0"),
    ("test_spheres.py", "Wave 6b: spheres, background and .NCC loading byte-exact over 2.56 MB of pages; the table's projective model bounded and cross-validated"),
    ("test_surface.py", "Wave 7a: surface() texture byte-exact lino==spec==cref on 10 captures and 14 synthetics; 17 sabotages caught; graded against NIV+ 2.3, NOT 1996"),
    ("test_ground.py", "Wave 7b: build_surface() and SURFACE.BIN - generated outputs three-way over types 1,2,3,4,5,7,8; the captured type-3 texture is exact and its post-landing p_surfacemap RAM residual is measured"),
    ("test_tile_depth.py", "portable integer terrain distance bins equal the historical floor(sqrt) result over every reachable reduced square"),
    ("test_terrain_inputs.py", "shared terrain vertex inputs are loaded once and reconstructed exactly on every cache, mirror, and clipping fallback"),
    ("test_terrain_empty_spans.py", "cached terrain rejects exact empty edge spans before texture-basis work while preserving visible polymap scratch writes"),
    ("test_sky.py", "Wave 7b: lean create_sky()/horizon/SP join regression; the historical --deep audit established 27 cases/408 records, exact NIV+ anchors, and caught 26 C plus 27 Lino mutants"),
    ("test_sun_gallery.py", "sixteen retained surface-sun oracles across types 1/2/3/4/5/7/8 plus case-specific palette, band/crop, camera, admission, and positive/lower/upper/class-suppressed ray-distance contracts"),
    ("test_sun_gallery_runtime_baseline.py", "private-desktop baseline gallery protects live habitable, thin-atmosphere, lunar, and dense-atmosphere surface suns"),
    ("test_sun_gallery_runtime_lunar.py", "private-desktop lunar gallery protects live class-1/3/4/5 surface suns and class-5 radial-flare suppression"),
    ("test_sun_gallery_runtime_classes.py", "private-desktop class gallery protects live lunar class-9/11, dense class-8, and frozen-world surface suns"),
    ("test_sun_gallery_runtime_rocky.py", "private-desktop rocky/quartz gallery protects live class-0/1/2 airless suns and the atmospheric quartz view"),
    ("test_frozen_sunrise_oracle.py", "exact-clock airless frozen-world evidence protects dry longitude-74 day and inclusive longitude-75 night state, native terminator globals, and an exact ten-pixel-to-zero horizon-source transition"),
    ("test_frozen_sunrise_runtime.py", "private-desktop frozen-world pair enforces the current longitude-74 day to inclusive longitude-75 night source transition"),
    ("test_frozen_sunset_oracle.py", "exact-clock airless frozen-world evidence protects longitude-204 night and exclusive longitude-205 day state, native terminator globals, source gating, and 25,800 exact upper-sky palette bands"),
    ("test_frozen_sunset_runtime.py", "private-desktop frozen-world pair enforces the current longitude-204 night to exclusive longitude-205 day source-free transition"),
    ("test_habitable_weather_oracle.py", "same-command atmospheric type-3 evidence independently reconstructs shared-cloud DESERT rain below and at 2.5, inclusive primary suppression, and 45,760 exact native/product scene indices"),
    ("test_habitable_weather_runtime.py", "private-desktop LANE IV pair enforces the current below-2.5 primary admission and inclusive 2.5 weather suppression boundary"),
    ("test_habitable_flare_oracle.py", "same-map atmospheric type-3 evidence independently reconstructs the 0.9375/1.25 DESERT bracket, inclusive rain-1.2 flare suppression, exact source crops, and 64,000 matching painter families"),
    ("test_habitable_flare_runtime.py", "private-desktop LANE IV pair enforces the current below-1.2 primary-flare admission and inclusive above-threshold suppression bracket"),
    ("test_habitable_multiple_weather_oracle.py", "companion-owned atmospheric type-3 evidence independently reconstructs the 1.6667/2.0/2.125 DESERT states, inclusive secondary-disc/flare weather gates, exact source crops, and native/product painter families"),
    ("test_habitable_multiple_weather_runtime.py", "private-desktop ROTOR IGNE trio enforces the current below-disc, exact-disc, and above-flare companion-weather boundaries"),
    ("test_surfaceclass10_oracle.py", "matched BISTARIAL/SORZ class-10 surface evidence protects the landed type-8 pose, in-gate class exclusion, exact palette and sun crop, and non-atomic authority boundary"),
    ("test_orbitprimary_class0_oracle.py", "matched EMPTY class-0 evidence protects the bodyless untargeted exterior pose, strict orbital interval, positive radial flare, exact crop bands, and non-atomic authority boundary"),
    ("test_orbitprimary_positive_gallery.py", "six retained bodyless class-1/2/3/4/8/9 positive orbital primaries protect strict flare/corona intervals, exact crop bands, class-colour palette prefixes, centred bright components, and non-atomic authority limits"),
    ("test_orbitprimary_class11_oracle.py", "matched POE class-11 evidence protects the fresh phase-zero admission chain, no-globe phase freeze, strict flare/corona intervals, centred radial spokes, exact crop bands, and non-atomic authority limits"),
    ("test_orbitprimary_class5_oracle.py", "matched ASKEW 184 class-5 evidence protects the bodyless untargeted exterior pose, strict orbital interval, compact corona, spoke exclusion, palette bands, and non-atomic authority boundary"),
    ("test_orbitprimary_class6_oracle.py", "matched FUEL TWO class-6 evidence protects the bodyless untargeted exterior pose, strict orbital interval, compact corona, spoke exclusion, palette bands, and non-atomic authority boundary"),
    ("test_orbitprimary_class10_oracle.py", "matched OUTER RUN WIND class-10 evidence protects the bodyless untargeted exterior pose, strict orbital interval, compact corona, spoke exclusion, palette bands, and non-atomic authority boundary"),
    ("test_orbitprimary_oracle.py", "matched WIRE class-7 native/product evidence protects the untargeted exterior camera, strict primary gate, space palette, complete flare-crop bands, and radial core"),
    ("test_orbitprimary_runtime.py", "private-desktop WIRE class-7 capture protects the current shipping primary flare, exact crop bands, and strict source gate"),
    ("test_orbitmultiple_oracle.py", "matched ROTOR IGNE negative and front-facing native pages/palettes protect the source exterior half-turn and a real type-10 companion flare"),
    ("test_orbitmultiple_runtime.py", "private-desktop ROTOR IGNE navigation pair protects behind-camera rejection and front-facing type-10 companion corona admission"),
    ("test_orbitmultiple_compact_oracle.py", "independent compact class-8 native/product evidence protects a beside-parent positive and exact-clock parent-behind-moon eclipse, strict source admission, shifted globe masks, and bounded overwrite without tuning ROTOR IGNE"),
    ("test_orbitmultiple_compact_runtime.py", "private-desktop compact-system pair protects a broad parent corona and exact-clock parent-behind-moon overwrite with shifted globe coverage"),
    ("test_orbitmultiple_triple_oracle.py", "genuine class-8 [10,10,1] native/product evidence independently grades two separated companion coronas in interior and roof/cupola views plus one visible and two hull-occluded sources outside, source projections, strict gates, and scoped palette bands"),
    ("test_orbitmultiple_triple_runtime.py", "private-desktop TRIUMVIRATE interior/exterior pair protects two admitted companion coronas, hull occlusion, source-centre indices, and scoped palette bands"),
    ("test_orbitmultiple_triple_roof_runtime.py", "private-desktop TRIUMVIRATE roof capture protects two independent companion masks, strict source gates, exact star-local pose, and all 64,000 palette bands"),
    ("test_orbitlunar_oracle.py", "matched IDEAL lunar exterior/interior/limb/roof/cupola-boundary and globe-before-primary eclipse pages protect orbital, globe, primary, Stardrifter, and source-order geometry"),
    ("test_orbitlunar_viewpoints_runtime.py", "private-desktop IDEAL exterior/interior/roof views retain aligned lunar, primary, Stardrifter, and shared-TEX4 geometry"),
    ("test_orbitlunar_boundary_runtime.py", "private-desktop IDEAL pair crosses the strict interior-to-cupola boundary against retained native pages"),
    ("test_orbitlunar_limb_runtime.py", "private-desktop IDEAL beside-primary view retains the aligned lunar limb and source-window geometry"),
    ("test_orbitlunar_eclipse_runtime.py", "private-desktop IDEAL pair protects globe-before-primary overwrite and the beside-primary positive control"),
    ("test_surface_flare_oracle.py", "rebuilt ten-case surface-flare probe equals six concatenated Borland pages, three real positive ray/distance pages, and the exact lunar no-beam boundary"),
    ("test_release_notes.py", "tagged GitHub releases contain only their own RELEASE_NOTES section"),
    ("test_fp_transgrade.py", "independent transcendental grading preserves signed zero and the one-ULP boundary"),
    ("test_native_closure.py", "all shipping targets share the canonical tracked Lino source closure, which contains zero target blocks and retains the exact reviewed 324-operation float inventory"),
    ("test_fp_runtime_boundary.py", "generated Windows PEs and Linux/macOS runtimes install exact FCWEXT below the portable Lino boundary while protected runtime inputs remain upstream-exact"),
    ("test_aarch64_runtime.py", "checked full-width AArch64 ABI, W^X mappings, relocation, image validation, and hosted QEMU execution"),
    ("test_macos_aarch64_runtime.py", "native arm64 Mach-O geometry, Darwin ABI, code-signature suffix, and W^X policy"),
    ("test_transcendental_consumers.py", "portable transcendental wrappers are byte-identical to direct x87 at capsule, flare, tree, camera/walk, globe, model Euler, animal, and orbital-viewpoint boundaries"),
    ("test_nivgen_score.py", "bounded NIVGEN scoring preserves harness inputs, rate-limits live pages, and reports local before/after transitions"),
    ("test_nivgen_precision.py", "public NIVGEN uses binary64 geometry boundaries while the shipping game retains historical x87 behavior"),
    ("test_nivgen_sheet_report.py", "complete NIVGEN snapshots distinguish backfill checkmarks from independently comparable hashes and expose before/after transitions"),
    ("test_desktop_profile.py", "private-desktop sustained timing records presentations, simulation ticks, deadlines, renderer cost, and W-response latency"),
    ("test_vhgame.py", "live Stardrifter: original lift/aperture constants, synchronized loop, and safe provisional landing renderer"),
    ("test_lift_runtime.py", "private-desktop lift traces retain every source-ordered state and indexed interior/roof transition"),
    ("test_capsule_runtime.py", "private-desktop capsule trace retains every sealing/ascent tick and the complete surface-to-ship handoff"),
    ("test_capsule_descent_runtime.py", "private-desktop capsule trace retains every fall, bounce, wind-driven terrain sample, and the clean airborne-to-walking settlement"),
    ("test_label_editing_runtime.py", "private-desktop star/body editor ownership, exact STARMAP mutation rules, and isolated blinking cursor raster"),
    ("test_controls_runtime.py", "private-desktop Stardrifter modifier ownership, modal Escape latching, and ordinary control preservation"),
]

# Tests that have a slower, more complete mode of their own. run_all always
# takes the fast path; the flag is for when you are about to trust the result.
DEEPER = {"test_brtlrand.py": "--exhaustive",
          "test_floatcontract.py": "--K 96",
          "test_fractional_pow.py": "--deep  (model/x87 all 9,564,210 reachable pairs; compiled Lino 4,096 cases)",
          "test_ground.py": "--deep  (historical sabotage/diagnostic audit)",
          "test_sky.py": "--deep  (historical malformed/full-corpus/mutation audit)"}

# The reverse of DEEPER: modes that trade coverage for speed. Named here so a
# reader knows they exist, and so nobody mistakes the fast path for the test.
# test_nearstar --quick skips the seven sabotages, which is exactly the part
# that shows the graders can fail; run_all never takes it.
FASTER = {"test_nearstar.py": "--quick  (skips the sabotages - not a pass)",
          "test_wave5.py": "--quick  (skips the sabotages - not a pass); "
                           "--nodisp skips the one probe that opens a window"}


def unregistered():
    """test_*.py files on disk that TESTS does not list.

    A wave that writes a test but forgets to register it would otherwise leave
    a suite that passes without ever running it - which looks exactly like a
    suite that passes. Counting files in tests/ is not a substitute: this
    directory also holds shared oracles and sandbox builders.
    """
    known = set(t[0] for t in TESTS)
    found = set(f for f in os.listdir(HERE)
                if f.startswith("test_") and f.endswith(".py"))
    return sorted(found - known)


def main():
    raw_args = sys.argv[1:]
    deep = "--deep" in raw_args
    selectors = [arg for arg in raw_args if arg != "--deep"]
    if len(selectors) > 1:
        print("usage: python tests/run_all.py [selector] [--deep]")
        return 2
    which = selectors[0] if selectors else ""
    selected = [t for t in TESTS if which in t[0]]
    if not selected:
        print("no test matches %r; known: %s" % (which, ", ".join(t[0] for t in TESTS)))
        return 2

    # This is a warning, not a governance gate. An unregistered helper test
    # does not make the actual port regressions invalid.
    if not which:
        orphans = unregistered()
        if orphans:
            print("WARNING: %d unregistered test file(s):" % len(orphans))
            for f in orphans:
                print("    %s" % f)

    results = []
    t0 = time.time()
    for name, blurb in selected:
        started = time.time()
        cmd = [sys.executable, os.path.join(HERE, name)]
        if deep and name in ("test_fractional_pow.py", "test_ground.py", "test_sky.py"):
            cmd.append("--deep")
        p = subprocess.run(cmd, cwd=HERE)
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
