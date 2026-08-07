r"""gr_break.py - break every check, and show which one catches it.

A check with no demonstrated falsifier is a claim, not a check.  This file
takes gr_spec.py / gr_ref.c, applies ONE localised edit, re-runs the corpus,
and reports which check fired and on how many cases.

Each row reports which check fired.  A sabotage that NOTHING catches is
printed as such and is evidence about the check set, not a pass.
"""

import importlib
import os
import shutil
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import gr_corpus
import gr_spec
import gr_grade

SAND = gr_grade.SAND
SEED_SZ = gr_grade.SEED_SZ
SBBIN_SZ = gr_grade.SBBIN_SZ
BUILD_REC_SZ = gr_grade.BUILD_REC_SZ
PS_BYTES = gr_spec.PS_BYTES
OC_BYTES = gr_spec.OC_BYTES


# name -> (file, old, new, what it models)
SPEC_MUTS = [
    ("SB_SWAP_LONLAT", "gr_spec.py",
     "struct.pack(\"<hh4i5f\",",
     "struct.pack(\"<hh4i5f\",  #",  # won't actually work — need real swap
     "placeholder"),
]

# Better: define mutations as functions that transform the source text.
# Each mutation is (name, file, find, replace, description).

MUTATIONS = [
    # ---- SURFACE.BIN layout mutations ----
    ("SB_SWAP_ATLXZ", "gr_spec.py",
     "d[\"atl_x\"], d[\"atl_z\"], d[\"atl_x2\"], d[\"atl_z2\"],",
     "d[\"atl_z\"], d[\"atl_x\"], d[\"atl_x2\"], d[\"atl_z2\"],",
     "swap atl_x and atl_z field order in SURFACE.BIN pack"),

    ("SB_FLOAT_ENDIAN", "gr_ref.c",
     "memcpy(out + 20, &px, 4);",
     "{ unsigned char tmp[4]; memcpy(tmp,&px,4); out[20]=tmp[3]; out[21]=tmp[2]; out[22]=tmp[1]; out[23]=tmp[0]; }",
     "wrong float32 endianness in SURFACE.BIN pack"),

    # ---- SEED chop mutations ----
    ("SEED_TRUNC_FIRST", "gr_spec.py",
     "s = ext(Fraction(ray)) + ext(Fraction(orb_ray)) + ext(Fraction(orb_orient))",
     "s = ext(Fraction(ftol32(ext(Fraction(ray)) + ext(Fraction(orb_ray)) + ext(Fraction(orb_orient)))))",
     "truncate the sum BEFORE multiplying by 4112 (niv-lr's order)"),

    ("SEED_SATURATE", "gr_spec.py",
     "return ftol32(p)",
     "t = int(p); return max(-2147483648, min(2147483647, t))",
     "saturating __ftol instead of wrapping"),

    # ---- BUILD mutations ----
    ("BUILD_ASSIGN", "gr_spec.py",
     "v = self.smap[i] + F.raw(3, 2282)",
     "v = F.raw(3, 2282)",
     "ASSIGN the plains noise instead of ADDing it (niv-lr's bug at :2280)"),

    ("BUILD_SKIPPROL", "gr_spec.py",
     "_ = B.random(32767, 2005)   # flandom() for treepeaking",
     "pass  # SKIP flandom()",
     "skip one prologue draw — desynchronises the brtl stream"),
]


def build_and_run_cref(src_path, sandbox):
    """Build a C reference from a source path, run it, return blob or None."""
    exe = os.path.join(sandbox, "grbreak.exe")
    if os.path.exists(exe):
        os.remove(exe)
    p = subprocess_run(["gcc", "-O2", "-fno-fast-math", "-o", exe, src_path])
    if p.returncode != 0:
        return None, "gcc: " + p.stderr[:120]
    spc = os.path.join(sandbox, "gr_corpus.spc")
    out = os.path.join(sandbox, "grbreak.bin")
    if os.path.exists(out):
        os.remove(out)
    p = subprocess_run([exe, spc, out], cwd=sandbox)
    if not os.path.exists(out):
        return None, "no output"
    return open(out, "rb").read(), "ok"


def subprocess_run(cmd, cwd=None):
    import subprocess
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", cwd=cwd)


def run_spec_all(rows):
    """Run the spec on all cases, return list of (kind, tag, data)."""
    out = []
    for r in rows:
        if r["kind"] == "sbbin":
            out.append(("sbbin", r["tag"], gr_spec.pack_surface_bin(r)))
        elif r["kind"] == "seed":
            v = gr_spec.global_surface_seed_chop(r["ray"], r["orb_ray"], r["orb_orient"])
            out.append(("seed", r["tag"], struct.pack("<i", v)))
        elif r["kind"] == "build":
            S = gr_spec.BuildSurface(ledger=False)
            o = S.run_build(r["gseed"], r["ip_type"], r["sctype"],
                            r["albedo"], r["latitude"], r["roughness"],
                            r["rounding"], r["level"], r["plains_noise"])
            out.append(("build", r["tag"], dict(map=S.map_bytes(),
                         obj=S.obj_bytes(), fast_n=o["fast_n"],
                         brtl_n=o["brtl_n"], fast_h=o["fast_h"],
                         brtl_h=o["brtl_h"])))
    return out


def compare(base, mut, rows):
    """Count how many cases differ between base and mutant results."""
    sbbin = seed = build = 0
    for i, r in enumerate(rows):
        if r["kind"] == "sbbin":
            sbbin += (base[i][2] != mut[i][2])
        elif r["kind"] == "seed":
            seed += (base[i][2] != mut[i][2])
        elif r["kind"] == "build":
            b, m = base[i][2], mut[i][2]
            if (b["map"] != m["map"] or b["obj"] != m["obj"]
                    or b["fast_n"] != m["fast_n"] or b["brtl_n"] != m["brtl_n"]):
                build += 1
    return dict(sbbin=sbbin, seed=seed, build=build)


def main():
    rows = gr_corpus.all_cases()
    os.makedirs(SAND, exist_ok=True)
    spc = os.path.join(SAND, "gr_corpus.spc")
    gr_corpus.write_spc(spc, rows)

    # Baseline spec results
    base_spec = run_spec_all(rows)

    print("%-20s %-30s %s" % ("sabotage", "caught by", "modelled defect"))
    print("-" * 100)

    uncaught = []
    for name, fname, old, new, why in MUTATIONS:
        if fname.endswith(".py"):
            # Mutate the spec
            tmp = tempfile.mkdtemp(prefix="grbrk_")
            try:
                shutil.copy(os.path.join(HERE, "gr_spec.py"),
                            os.path.join(tmp, "gr_spec.py"))
                shutil.copy(os.path.join(HERE, "su_fp.py"),
                            os.path.join(tmp, "su_fp.py"))
                shutil.copy(os.path.join(HERE, "brtl_oracle.py"),
                            os.path.join(tmp, "brtl_oracle.py"))
                p = os.path.join(tmp, fname)
                s = open(p, encoding="utf-8").read()
                if old not in s:
                    print("%-20s %-30s %s" % (name, "EDIT DID NOT APPLY", why))
                    continue
                s = s.replace(old, new, 1)
                open(p, "w", encoding="utf-8").write(s)
                sys.path.insert(0, tmp)
                for m in ("gr_spec", "su_fp"):
                    sys.modules.pop(m, None)
                mod = importlib.import_module("gr_spec")
                try:
                    mut_spec = []
                    for r in rows:
                        if r["kind"] == "sbbin":
                            mut_spec.append(("sbbin", r["tag"], mod.pack_surface_bin(r)))
                        elif r["kind"] == "seed":
                            v = mod.global_surface_seed_chop(r["ray"], r["orb_ray"], r["orb_orient"])
                            mut_spec.append(("seed", r["tag"], struct.pack("<i", v)))
                        elif r["kind"] == "build":
                            S = mod.BuildSurface(ledger=False)
                            o = S.run_build(r["gseed"], r["ip_type"], r["sctype"],
                                            r["albedo"], r["latitude"], r["roughness"],
                                            r["rounding"], r["level"], r["plains_noise"])
                            mut_spec.append(("build", r["tag"], dict(
                                map=S.map_bytes(), obj=S.obj_bytes(),
                                fast_n=o["fast_n"], brtl_n=o["brtl_n"],
                                fast_h=o["fast_h"], brtl_h=o["brtl_h"])))
                    hit = compare(base_spec, mut_spec, rows)
                    fired = ", ".join("%s %d/%d" % (k, v, sum(1 for r in rows if r["kind"] == k))
                                      for k, v in sorted(hit.items()) if v)
                except Exception as exc:
                    fired = "CRASH: %s" % str(exc)[:60]
                sys.path.remove(tmp)
                for m in ("gr_spec", "su_fp"):
                    sys.modules.pop(m, None)
                import gr_spec  # restore
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
        elif fname.endswith(".c"):
            # Mutate the C reference — build and run in SAND (corpus is there)
            src = open(os.path.join(HERE, "gr_ref.c"), encoding="latin-1").read()
            if old not in src:
                print("%-20s %-30s %s" % (name, "EDIT DID NOT APPLY", why))
                continue
            src = src.replace(old, new, 1)
            mut_src = os.path.join(SAND, "gr_brk_%s.c" % name.lower())
            open(mut_src, "w", encoding="latin-1").write(src)
            blob, note = build_and_run_cref(mut_src, SAND)
            if blob is None:
                print("%-20s %-30s %s" % (name, "BUILD/RUN FAILED: %s" % note, why))
                continue
            # Baseline cref blob
            cexe, _ = gr_grade.build_cref(os.path.join(SAND, "gr_ref.c"),
                                          "grbase.exe", SAND)
            base_blob, _ = gr_grade.run_cref(cexe, spc, "gr_base.bin", SAND)
            # count differing records
            coff_b = coff_m = 0
            sbbin = seed = build = 0
            for r in rows:
                if r["kind"] == "sbbin":
                    sbbin += (base_blob[coff_b:coff_b+SBBIN_SZ] != blob[coff_m:coff_m+SBBIN_SZ])
                    coff_b += SBBIN_SZ; coff_m += SBBIN_SZ
                elif r["kind"] == "seed":
                    seed += (base_blob[coff_b:coff_b+SEED_SZ] != blob[coff_m:coff_m+SEED_SZ])
                    coff_b += SEED_SZ; coff_m += SEED_SZ
                elif r["kind"] == "build":
                    b_map = base_blob[coff_b:coff_b+PS_BYTES]
                    m_map = blob[coff_m:coff_m+PS_BYTES]
                    b_cnt = struct.unpack_from("<4I", base_blob, coff_b+PS_BYTES+OC_BYTES)
                    m_cnt = struct.unpack_from("<4I", blob, coff_m+PS_BYTES+OC_BYTES)
                    build += (b_map != m_map or b_cnt != m_cnt)
                    coff_b += BUILD_REC_SZ; coff_m += BUILD_REC_SZ
            hit = dict(sbbin=sbbin, seed=seed, build=build)
            fired = ", ".join("%s %d/%d" % (k, v, sum(1 for r in rows if r["kind"] == k))
                              for k, v in sorted(hit.items()) if v)
        else:
            fired = "UNKNOWN FILE TYPE"

        if not fired:
            uncaught.append(name)
            print("%-20s %-30s %s" % (name, "*** NOTHING ***", why))
        else:
            print("%-20s %-30s %s" % (name, fired, why))

    print("\nuncaught:", uncaught or "none")


if __name__ == "__main__":
    main()
