r"""gr_grade.py - Wave 7b, the three-way comparison for build_surface + SURFACE.BIN.

Producers:
  spec  gr_spec.py           Python, exact rationals for the float chop,
                             transliterated from NOCTIS-1.CPP.
  cref  gr_ref.exe (gr_ref.c) C, hardware x87, transliterated from the same
                             DOS text in a separate pass.
  lino  work/grnd.txt + work/surfio.txt  the DELIVERABLE (added in phase 2).

spec and cref agreeing proves the transliteration is unambiguous.  Either
agreeing with lino proves the port is right.

Usage:  python gr_grade.py
"""

import collections
import os
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import numpy as np

import gr_corpus
import gr_spec

PS_BYTES = gr_spec.PS_BYTES
OC_BYTES = gr_spec.OC_BYTES
SBBIN_SZ = 40
SEED_SZ = 4
BUILD_REC_SZ = PS_BYTES + OC_BYTES + 16   # map + objects + 4 int32

SAND = os.path.join(os.path.dirname(HERE), "tests", "gen", "gr_sand")


def nd(a, b):
    """Count differing bytes between two byte buffers."""
    la, lb = len(a), len(b)
    n = abs(la - lb)
    for x, y in zip(a, b):
        n += (x != y)
    return n


def build_cref(c_src, exe_name, sandbox):
    exe = os.path.join(sandbox, exe_name)
    if os.path.exists(exe):
        os.remove(exe)
    p = subprocess.run(["gcc", "-O2", "-fno-fast-math", "-o", exe, c_src],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if p.returncode != 0:
        return None, "gcc failed: " + (p.stdout or "") + (p.stderr or "")
    return exe, "ok"


def run_cref(exe, spc, out_name, sandbox):
    out = os.path.join(sandbox, out_name)
    if os.path.exists(out):
        os.remove(out)
    p = subprocess.run([exe, spc, out], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=sandbox)
    if not os.path.exists(out):
        return None, "no output: " + (p.stdout or "") + (p.stderr or "")
    return open(out, "rb").read(), (p.stderr or "").strip()


def main(argv=None):
    rows = gr_corpus.all_cases()
    os.makedirs(SAND, exist_ok=True)

    # Write corpus
    spc = os.path.join(SAND, "gr_corpus.spc")
    gr_corpus.write_spc(spc, rows)

    # Build and run the C reference
    csrc = os.path.join(HERE, "gr_ref.c")
    import shutil
    shutil.copy(csrc, os.path.join(SAND, "gr_ref.c"))
    cexe, note = build_cref(os.path.join(SAND, "gr_ref.c"), "grref.exe", SAND)
    if cexe is None:
        print("CREF BUILD FAILED:", note)
        return 2
    cblob, cnote = run_cref(cexe, spc, "gr_ref.bin", SAND)
    if cblob is None:
        print("CREF RUN FAILED:", cnote)
        return 2

    # Run the spec and compare
    all_ok = True
    results = []
    coff = 0  # offset into cref blob

    sbbin_ok = seed_ok = build_map_ok = build_obj_ok = build_draw_ok = 0
    sbbin_n = seed_n = build_n = 0

    for r in rows:
        tag = r["tag"]
        if r["kind"] == "sbbin":
            sbbin_n += 1
            # Spec
            spec_bytes = gr_spec.pack_surface_bin(r)
            # cref is 40 bytes
            cref_bytes = cblob[coff:coff + SBBIN_SZ]
            coff += SBBIN_SZ
            ok = (spec_bytes == cref_bytes)
            diff = nd(spec_bytes, cref_bytes) if not ok else 0
            results.append(("SBBIN", tag, "EXACT", ok,
                            "%d byte diff" % diff if not ok else "byte-exact"))
            sbbin_ok += ok
            all_ok &= ok

        elif r["kind"] == "seed":
            seed_n += 1
            # Spec
            spec_val = gr_spec.global_surface_seed_chop(
                r["ray"], r["orb_ray"], r["orb_orient"])
            spec_bytes = struct.pack("<i", spec_val)
            # cref is 4 bytes
            cref_bytes = cblob[coff:coff + SEED_SZ]
            coff += SEED_SZ
            cref_val = struct.unpack("<i", cref_bytes)[0]
            ok = (spec_val == cref_val)
            results.append(("SEED", tag, "EXACT", ok,
                            "spec=%d cref=%d" % (spec_val, cref_val)
                            if not ok else "chop=%d" % spec_val))
            seed_ok += ok
            all_ok &= ok

        elif r["kind"] == "build":
            build_n += 1
            # Spec
            S = gr_spec.BuildSurface(ledger=False)
            out = S.run_build(r["gseed"], r["ip_type"], r["sctype"],
                              r["albedo"], r["latitude"],
                              r["roughness"], r["rounding"],
                              r["level"], r["plains_noise"])
            spec_map = S.map_bytes()
            spec_obj = S.obj_bytes()
            # cref: PS_BYTES + OC_BYTES + 16
            cref_map = cblob[coff:coff + PS_BYTES]
            cref_obj = cblob[coff + PS_BYTES:coff + PS_BYTES + OC_BYTES]
            cnt = struct.unpack_from("<4I", cblob,
                                     coff + PS_BYTES + OC_BYTES)
            coff += BUILD_REC_SZ

            map_ok = (spec_map == cref_map)
            obj_ok = (spec_obj == cref_obj)
            draw_ok = (out["fast_n"] == cnt[0] and out["brtl_n"] == cnt[1]
                       and out["fast_h"] == cnt[2] and out["brtl_h"] == cnt[3])

            build_map_ok += map_ok
            build_obj_ok += obj_ok
            build_draw_ok += draw_ok
            all_ok &= map_ok and obj_ok and draw_ok

            note = "map %s (%d diff), obj %s, draws (%d,%d)==(%d,%d) h(%u,%u)==(%u,%u)" % (
                "ok" if map_ok else "FAIL", nd(spec_map, cref_map) if not map_ok else 0,
                "ok" if obj_ok else "FAIL",
                out["fast_n"], out["brtl_n"], cnt[0], cnt[1],
                out["fast_h"], out["brtl_h"], cnt[2], cnt[3])
            results.append(("BUILD", tag, "EXACT",
                            map_ok and obj_ok and draw_ok, note))

    # Report
    print("=" * 80)
    print("Wave 7b gr_grade.py — spec vs cref (the two independent transliterations)")
    print("=" * 80)
    for cid, tag, claim, ok, note in results:
        status = "ok" if ok else "FAIL"
        print("%-6s %-20s %-6s %s" % (cid, tag, status, note))
    print()
    print("SBBIN  %d/%d byte-exact (SURFACE.BIN 40-byte pack)" % (sbbin_ok, sbbin_n))
    print("SEED   %d/%d byte-exact (global_surface_seed chop)" % (seed_ok, seed_n))
    print("BUILD  map %d/%d, objects %d/%d, draws %d/%d byte-exact" % (
        build_map_ok, build_n, build_obj_ok, build_n, build_draw_ok, build_n))
    print()
    if all_ok:
        print("ALL CHECKS PASS — spec and cref agree on every case.")
    else:
        print("SOME CHECKS FAILED — see above.")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
