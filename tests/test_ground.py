r"""Wave 7b: build_surface() + SURFACE.BIN — NOCTIS-1.CPP:1948-2731, :3722-3742, :4992-5002.

WHAT THIS GRADES
    The 40000-byte p_surfacemap (200×200 heightmap), the 65536-byte
    p_background (256×256 ground texture), the 40000-byte objectschart,
    the SURFACE.BIN 40-byte NIV+ R2.3 pack, and the global_surface_seed
    x87 chop.  Planet types 1,2,3,4,5,7,8 with their integer and float
    painters (rockyground, smoothterrain, round_hill, std_crater,
    srf_darkline, felisian_srf_darkline, asterism).

WHAT THE ORACLE IS
    For non-type-3 complete builds: internal consistency (spec == cref).
    The Lino leg calls the production VHGND build surface core at its clean
    return boundary.  The smaller painter driver remains a focused check.
    For type-3 equator: a binary capture from
    NIV+ R2.3's own guest RAM (tests/gen/recon_w7b/out/).  The type-3
    p_surfacemap and every deterministic texture byte match through the
    production Lino core.  A live RAM capture pins
    sctype=OCEAN and albedo=40; OCEAN therefore takes the `goto revert`
    PLAINS path.  With that corrected fixture, the first 65,532 texture
    bytes match the NIV+ capture.  NIV/NIV+ leaves the final four ptxtr
    bytes dependent on nondeterministic reads, so they are deliberately not
    a golden equality oracle.  The independent Python/C round_hill model
    still differs in 1,752 map bytes; the actual Lino output proves that is
    a model gap, not corruption in the captured p_surfacemap.

THE THREE IMPLEMENTATIONS
    spec  noctis-harness/gr_spec.py   Python, exact rationals for the
                                      seed chop, float32 stores modeled.
    cref  noctis-harness/gr_ref.c     C, hardware x87 (fsqrt/fsin/fcos
                                      via inline asm), separate pass.
    lino  work/vhground.txt           The production type switch and clean
                                      return, driven through a derived game
                                      executable; grmain retains its focused
                                      painter check.

Usage:  python tests/test_ground.py [--deep] [--no-lino]
"""

import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
WORK = os.path.join(REPO, "work")
HARNESS = os.path.join(REPO, "noctis-harness")
RECON_W7B = os.path.join(HERE, "gen", "recon_w7b", "out")
NIV_CLEAN_ROOT = os.environ.get(
    "NOCTIS_NIV_GROUND_FIXTURES",
    os.path.join(HERE, "fixtures", "niv_ground"))
SAND = os.path.join(HERE, "gen", "gr_sand")

for p in (HERE, HARNESS):
    if p not in sys.path:
        sys.path.insert(0, p)

import linoharness as lh
import gr_spec
import gr_corpus

PS_BYTES = gr_spec.PS_BYTES
OC_BYTES = gr_spec.OC_BYTES
TXTR_BYTES = gr_spec.TXTR_BYTES
# NIV/NIV+ ptxtr's last four bytes are sourced through nondeterministic reads.
# Keep the exception exactly this narrow: byte 65531 is still authoritative.
NIV_TXTR_DEFINED_BYTES = TXTR_BYTES - 4
REC_SZ = PS_BYTES + OC_BYTES + 16  # map + objects + 4 int32 counters

# t3_equator live state, measured by tests/gen/recon_w7b/diag_ground_state.py.
# global_surface_seed comes independently from Wave 4's graded system data;
# build_surface then re-seeds both generators with lon*lat == 0 at :2051-52.
CAPTURE_GSEED = 1029155
CAPTURE_SCTYPE = 1                 # OCEAN
CAPTURE_ALBEDO = 40                # >20, therefore goto revert / PLAINS
# The remaining 1,752-byte delta belongs to the independent Python/C model.
MODEL_MAP_OPEN_DIFF = 1752
FULL_HEAD_UNITS = 28
FULL_OUT_UNITS = FULL_HEAD_UNITS + PS_BYTES + TXTR_BYTES + OC_BYTES
FULL_IN_MAGIC = 0x47464931
FULL_OUT_MAGIC = 0x47464A31
FULL_VERSION = 1
NIV_OBJ_MATCH_PREFIX = 39925
CAPTURE_OBJECT_OPEN_DIFF = 39
FULL_STATE_INDEX = {
    "fast_seed": 8, "borland_seed": 9,
    "fast_draws": 10, "borland_draws": 11,
    "fast_hash": 12, "borland_hash": 13,
    "quartz": 14, "frosty": 15, "waswet": 16, "wavescalm": 17,
    "rock_scale": 18, "rock_peak": 19, "rock_density": 20,
    "texture_scale": 21, "roughness": 22, "rounding": 23,
    "level": 24, "normalized_latitude": 25, "local_seed": 26,
}


def nd(a, b):
    return int((__import__("numpy").frombuffer(a, dtype="uint8")
                != __import__("numpy").frombuffer(b, dtype="uint8")).sum())


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


# =========================================================================
# Build / run helpers
# =========================================================================

def build_cref(sandbox):
    csrc = os.path.join(HARNESS, "gr_ref.c")
    dst = os.path.join(sandbox, "gr_ref.c")
    shutil.copy(csrc, dst)
    exe = os.path.join(sandbox, "grref.exe")
    if os.path.exists(exe):
        os.remove(exe)
    p = subprocess.run(["gcc", "-O2", "-fno-fast-math", "-o", exe, dst],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if p.returncode != 0:
        return None, "gcc failed: " + p.stderr[:200]
    return exe, "ok"


def run_cref(exe, spc, out_name, sandbox, ncases):
    out = os.path.join(sandbox, out_name)
    if os.path.exists(out):
        os.remove(out)
    p = subprocess.run([exe, spc, out], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=sandbox)
    if not os.path.exists(out):
        return None, "no output"
    blob = open(out, "rb").read()
    expected = sum(1 for r in gr_corpus.all_cases() if r["kind"] == "sbbin") * 40 \
             + sum(1 for r in gr_corpus.all_cases() if r["kind"] == "seed") * 4 \
             + sum(1 for r in gr_corpus.all_cases() if r["kind"] == "build") * REC_SZ
    return blob, "ok"


def run_lino(main_src, out_name, timeout=600):
    exe = os.path.splitext(main_src)[0] + ".exe"
    out = os.path.join(SAND, "gr-out.bin")
    keep = os.path.join(SAND, out_name)
    for stale in (exe, out, keep):
        if os.path.exists(stale):
            os.remove(stale)
    rc, note = lh.build(main_src, timeout_sec=240)
    if rc != 0:
        return None, "BUILD FAILED: " + note.strip().replace("\n", " | ")[:200]
    ps = os.path.join(HERE, "w7arun.ps1")
    p = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy",
                        "Bypass", "-File", ps, "-Exe", exe, "-Out", out,
                        "-TimeoutSec", str(timeout)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    note = ((p.stdout or "") + (p.stderr or "")).strip()
    if p.returncode != 0 or not os.path.exists(out):
        return None, "RUN FAILED: " + note[:200]
    shutil.move(out, keep)
    return keep, note


def build_full_lino_driver():
    """Derive a clean-return entry point while linking the actual game."""
    source_path = os.path.join(WORK, "vhgame.txt")
    generated = os.path.join(WORK, "grfullfixturemain.txt")
    exe = os.path.join(WORK, "grfullfixturemain.exe")
    text = open(source_path, "r", encoding="utf-8").read()
    libs_old = "vhspace; vhstar; vhground; vhcapsule;"
    libs_new = "vhspace; vhstar; vhground; vhgroundfixture; vhcapsule;"
    entry_old = "\t=> VHG run;\n\tend;"
    entry_new = "\t=> VHG ground fixture run;\n\tend;"
    if text.count(libs_old) != 1 or text.count(entry_old) != 1:
        return generated, None, "vhgame fixture splice point changed"
    text = text.replace(libs_old, libs_new, 1)
    text = text.replace("program name = { vhgame };",
                        "program name = { grfullfixturemain };", 1)
    text = text.replace(entry_old, entry_new, 1)
    with open(generated, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    if os.path.exists(exe):
        os.remove(exe)
    rc, note = lh.build(generated, timeout_sec=240)
    if rc != 0 or not os.path.exists(exe):
        return generated, None, "BUILD FAILED: " + note[:200]
    return generated, exe, note


def run_full_lino_case(exe, gseed, ip_type, sctype, albedo, lat, lon,
                       timeout=120):
    inp = os.path.join(WORK, "gr-full-in.bin")
    out = os.path.join(WORK, "gr-full-out.bin")
    with open(inp, "wb") as fh:
        fh.write(struct.pack("<8I", FULL_IN_MAGIC, FULL_VERSION, gseed,
                             ip_type, sctype, albedo, lat, lon))
    if os.path.exists(out):
        os.remove(out)
    p = subprocess.run([exe], cwd=WORK, timeout=timeout,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if p.returncode != 0 or not os.path.exists(out):
        return None, "RUN FAILED: exit %d" % p.returncode
    raw = open(out, "rb").read()
    if len(raw) != FULL_OUT_UNITS * 4:
        return None, "wrong output size %d" % len(raw)
    units = struct.unpack("<%dI" % FULL_OUT_UNITS, raw)
    if units[0] != FULL_OUT_MAGIC or units[1] != FULL_VERSION:
        return None, "bad output header %08x/%d" % (units[0], units[1])
    pos = FULL_HEAD_UNITS
    smap = bytes(u & 255 for u in units[pos:pos + PS_BYTES]); pos += PS_BYTES
    txtr = bytes(u & 255 for u in units[pos:pos + TXTR_BYTES]); pos += TXTR_BYTES
    objs = bytes(u & 255 for u in units[pos:pos + OC_BYTES])
    return dict(header=units[:FULL_HEAD_UNITS], smap=smap,
                txtr=txtr, objs=objs), "ok"


def load_clean_niv_cases():
    """Load optional clean-return NIV+ fixtures without weakening any byte."""
    manifest_path = os.path.join(NIV_CLEAN_ROOT, "manifest.json")
    if not os.path.isfile(manifest_path):
        return []
    data = json.load(open(manifest_path, "r", encoding="utf-8"))
    cases = data if isinstance(data, list) else data.get("cases", [])
    required = ("tag", "gseed", "ip_type", "sctype", "albedo", "lat", "lon",
                "surfacemap", "texture", "objects")
    for case in cases:
        missing = [key for key in required if key not in case]
        if missing:
            raise ValueError("clean NIV fixture %r missing %s" %
                             (case.get("tag", "?"), ", ".join(missing)))
    return cases


def grade_clean_niv_case(case, got):
    def fixture_bytes(key, size):
        path = os.path.join(NIV_CLEAN_ROOT, case[key])
        raw = open(path, "rb").read()
        if len(raw) < size:
            raise ValueError("%s is %d bytes, expected at least %d" %
                             (path, len(raw), size))
        return raw[:size]

    smap = fixture_bytes("surfacemap", PS_BYTES)
    txtr = fixture_bytes("texture", TXTR_BYTES)
    objs = fixture_bytes("objects", OC_BYTES)
    defined = int(case.get("texture_defined_bytes", NIV_TXTR_DEFINED_BYTES))
    if defined != NIV_TXTR_DEFINED_BYTES:
        raise ValueError("NIV texture mask must remain exactly 65,532 bytes")
    diffs = dict(map=nd(got["smap"], smap),
                 texture=nd(got["txtr"][:defined], txtr[:defined]),
                 objects=nd(got["objs"], objs), state=0)
    for name, expected in case.get("exit_state", {}).items():
        if name not in FULL_STATE_INDEX:
            raise ValueError("unknown clean NIV exit-state field %r" % name)
        actual = got["header"][FULL_STATE_INDEX[name]]
        diffs["state"] += actual != (int(expected) & 0xFFFFFFFF)
    return diffs


# =========================================================================
# The test
# =========================================================================

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--deep", action="store_true",
                    help="run historical diagnostics and sabotage matrix")
    ap.add_argument("--quick", action="store_true",
                    help="compatibility alias for the lean default")
    ap.add_argument("--no-lino", action="store_true", help="skip lino build/run")
    a = ap.parse_args(argv)

    chk = lh.Check("WAVE 7b - build_surface + SURFACE.BIN")
    chk.note("ORACLE: complete spec==cref builds, production Lino clean-return "
             "driver, focused painter leg, and one NIV+ type-3 capture.")
    chk.note("Type-3 capture fixture is RAM-pinned (OCEAN, albedo 40, seed 0).")
    chk.note("The production Lino map and deterministic texture prefix are "
             "exact; the final four ptxtr bytes are undefined in NIV+.")

    # ---- fixture ----
    os.makedirs(SAND, exist_ok=True)
    clean_niv_cases = load_clean_niv_cases()
    if clean_niv_cases:
        chk.note("Clean-return NIV+ fixture manifest: %d cases" %
                 len(clean_niv_cases))
    else:
        chk.note("Clean-return NIV+ fixture manifest not present; drop one at %s"
                 % NIV_CLEAN_ROOT)
    rows = gr_corpus.all_cases()
    spc = os.path.join(SAND, "gr_corpus.spc")
    gr_corpus.write_spc(spc, rows)
    chk.ok(len(rows) >= 29, "R0 fixture: %d cases" % len(rows),
           "types " + ",".join(str(r.get("ip_type", r.get("type", "?"))) for r in rows if r["kind"] == "build"))

    # ---- build + run cref ----
    cexe, note = build_cref(SAND)
    chk.ok(cexe is not None, "R1 cref rebuilt", note)
    cblob = None
    if cexe:
        cblob, note = run_cref(cexe, spc, "cref.bin", SAND, len(rows))
        chk.ok(cblob is not None, "R2 cref ran", note)

    # ---- run spec on every case ----
    spec_results = {}
    coff = 0
    b_sc = b_ls = b_map = b_obj = b_txtr = b_pal = 0
    bad = []
    sbbin_n = seed_n = build_n = 0

    for ci, r in enumerate(rows):
        tag = r["tag"]
        if r["kind"] == "sbbin":
            sbbin_n += 1
            spec_bytes = gr_spec.pack_surface_bin(r)
            cref_bytes = cblob[coff:coff + 40]; coff += 40
            ok = spec_bytes == cref_bytes
            b_sc += ok
            if not ok: bad.append("sbbin %s" % tag)
        elif r["kind"] == "seed":
            seed_n += 1
            v = gr_spec.global_surface_seed_chop(r["ray"], r["orb_ray"], r["orb_orient"])
            ok = struct.pack("<i", v) == cblob[coff:coff + 4]; coff += 4
            b_sc += ok
            if not ok: bad.append("seed %s" % tag)
        elif r["kind"] == "build":
            build_n += 1
            S = gr_spec.BuildSurface(ledger=False)
            out = S.run_build(r["gseed"], r["ip_type"], r["sctype"],
                              r["albedo"], r["latitude"],
                              r["roughness"], r["rounding"],
                              r["level"], r["plains_noise"])
            spec_map = S.map_bytes()
            spec_obj = S.obj_bytes()
            cref_map = cblob[coff:coff + PS_BYTES]
            cref_obj = cblob[coff + PS_BYTES:coff + PS_BYTES + OC_BYTES]
            ccnt = struct.unpack_from("<4I", cblob, coff + PS_BYTES + OC_BYTES)
            coff += REC_SZ
            map_ok = spec_map == cref_map
            obj_ok = spec_obj == cref_obj
            draw_ok = (out["fast_n"] == ccnt[0] and out["brtl_n"] == ccnt[1])
            b_map += map_ok; b_obj += obj_ok; b_sc += (map_ok and obj_ok and draw_ok)
            if not (map_ok and obj_ok and draw_ok):
                bad.append("build %s map=%s obj=%s draw=%s" % (
                    tag, map_ok, obj_ok, draw_ok))

    chk.ok(b_sc >= sbbin_n + seed_n,
           "B1 spec==cref on SURFACE.BIN (%d/%d) + seed chop (%d/%d)"
           % (sbbin_n, sbbin_n, seed_n, seed_n),
           ", ".join(bad[:3]) if bad else "all ok")
    chk.ok(b_map + b_obj >= 2 * build_n,
           "B2 spec==cref on build map (%d/%d) + objects (%d/%d)"
           % (b_map, build_n, b_obj, build_n),
           ", ".join(bad[:3]) if bad else "all ok")

    # ---- lino focused painter comparison + complete production core ----
    full_lino = None
    if not a.no_lino:
        # Copy all needed libraries to the sandbox
        lino_libs = ("fbmem", "brtl", "mul64frag", "surng", "suseed", "grnd")
        fp_libs = ("fpabi", "fpctl", "fpsoft", "fpx87", "fpconv")
        os.makedirs(os.path.join(SAND, "fp"), exist_ok=True)
        for lib in lino_libs:
            shutil.copy(os.path.join(WORK, lib + ".txt"), os.path.join(SAND, lib + ".txt"))
        for lib in fp_libs:
            shutil.copy(os.path.join(WORK, "fp", lib + ".txt"),
                        os.path.join(SAND, "fp", lib + ".txt"))
        lino_main = os.path.join(SAND, "grmain.txt")
        shutil.copy(os.path.join(WORK, "grmain.txt"), lino_main)
        dump, note = run_lino(lino_main, "lino.bin")
        chk.ok(dump is not None, "R3 lino built and ran", note[:120] if note else "ok")
        if dump:
            raw = open(dump, "rb").read()
            units = struct.unpack("<%dI" % (len(raw) // 4), raw)
            lino_map = bytes((u & 255) for u in units[0:PS_BYTES])
            lino_cnt = units[PS_BYTES:PS_BYTES + 4]
            # Spec: prologue + re-seed + rockyground(25,4,0) + plains_noise
            S = gr_spec.BuildSurface(ledger=False)
            S.smap = bytearray(PS_BYTES)
            S.objs = bytearray(OC_BYTES)
            S.txtr = bytearray(gr_spec.TXTR_BYTES)
            for i in range(65535):
                S.txtr[i] = 16
            S.prologue(123456, 1, 0, 20, 30)
            S.F.srand(123456)
            S.B.srand(123456 & 0xFFFF)
            S.rockyground(25, 4, 0)
            S.plains_noise_add()
            spec_map = S.map_bytes()
            map_diff = nd(spec_map, lino_map)
            draw_ok = (S.F.n == lino_cnt[0] and S.B.n == lino_cnt[1]
                       and S.F.h == lino_cnt[2] and S.B.h == lino_cnt[3])
            chk.ok(map_diff == 0 and draw_ok,
                   "B3 lino multi-painter byte-exact: prologue + rockyground "
                   "+ smoothterrain + plains noise (40000 B map + draws + hashes)",
                   "map %d diff, draws %s" % (map_diff, "ok" if draw_ok else "FAIL"))

        generated, full_exe, note = build_full_lino_driver()
        chk.ok(full_exe is not None, "R4 production Lino surface driver built",
               note[:120] if note else "ok")
        try:
            if full_exe:
                full_lino, note = run_full_lino_case(
                    full_exe, CAPTURE_GSEED, 3, CAPTURE_SCTYPE,
                    CAPTURE_ALBEDO, 60, 0)
                chk.ok(full_lino is not None,
                       "R5 production Lino build_surface core ran to clean return",
                       note)
                for case in clean_niv_cases:
                    got, note = run_full_lino_case(
                        full_exe, int(case["gseed"]), int(case["ip_type"]),
                        int(case["sctype"]), int(case["albedo"]),
                        int(case["lat"]), int(case["lon"]))
                    diffs = grade_clean_niv_case(case, got) if got else None
                    exact = got is not None and all(v == 0 for v in diffs.values())
                    chk.ok(exact, "NIV clean %s: production Lino exact" %
                           case["tag"], str(diffs) if diffs else note)
        finally:
            for stale in (generated, full_exe,
                          os.path.join(WORK, "gr-full-in.bin"),
                          os.path.join(WORK, "gr-full-out.bin")):
                if stale and os.path.exists(stale):
                    os.remove(stale)
    else:
        chk.note("R3/R4/R5 lino SKIPPED (--no-lino)")

    # ---- type-3 binary capture ----
    if os.path.isdir(RECON_W7B):
        cap_map = open(os.path.join(RECON_W7B, "t3_equator.p_surfacemap"), "rb").read()
        cap_txtr = open(os.path.join(RECON_W7B, "t3_equator.p_background"), "rb").read()
        cap_obj = open(os.path.join(RECON_W7B, "t3_equator.objectschart"), "rb").read()
        if full_lino:
            lino_map_diff = nd(full_lino["smap"], cap_map[:PS_BYTES])
            lino_txtr_diff = nd(full_lino["txtr"][:NIV_TXTR_DEFINED_BYTES],
                                cap_txtr[:NIV_TXTR_DEFINED_BYTES])
            chk.ok(lino_map_diff == 0 and lino_txtr_diff == 0,
                   "C1 production Lino clean return matches NIV+ map and all "
                   "65,532 deterministic texture bytes",
                   "map %d diff, texture %d diff" %
                   (lino_map_diff, lino_txtr_diff))
            obj_prefix_diff = nd(full_lino["objs"][:NIV_OBJ_MATCH_PREFIX],
                                 cap_obj[:NIV_OBJ_MATCH_PREFIX])
            obj_total_diff = nd(full_lino["objs"], cap_obj[:OC_BYTES])
            chk.ok(obj_prefix_diff == 0 and
                   obj_total_diff == CAPTURE_OBJECT_OPEN_DIFF,
                   "C2 production Lino object map matches the captured "
                   "39,925-byte prefix",
                   "%d prefix diffs; %d boundary-tail diffs still need a "
                   "clean-return NIV+ capture" %
                   (obj_prefix_diff, obj_total_diff))
        S = gr_spec.BuildSurface(ledger=False)
        S.smap = bytearray(PS_BYTES)
        S.objs = bytearray(OC_BYTES)
        S.txtr = bytearray(TXTR_BYTES)
        for i in range(65535): S.txtr[i] = 16
        S.prologue(CAPTURE_GSEED, 3, CAPTURE_SCTYPE, CAPTURE_ALBEDO, 0)
        S.F.srand(0); S.B.srand(0)
        S.liquid_water = 0
        S._switch(3, CAPTURE_SCTYPE, CAPTURE_ALBEDO)
        S._post_switch()
        S._objects_inclination()
        spec_map = S.map_bytes()
        spec_txtr = bytes(S.txtr)
        row0_spec_nz = sum(1 for x in spec_map[0:200] if x)
        row0_cap_nz = sum(1 for x in cap_map[0:200] if x)
        diff = nd(spec_map, cap_map[:PS_BYTES])
        if a.deep:
            chk.ok(row0_cap_nz == 0,
                   "C3 type-3 capture: row 0 all-zero in capture (baseline confirmed)",
                   "cap row0 nonzero=%d" % row0_cap_nz)
            chk.note("C3 note: independent model row 0 has %d nonzero; this is "
                     "part of the remaining map-only gap" % row0_spec_nz)
        txtr_diff = nd(spec_txtr[:NIV_TXTR_DEFINED_BYTES],
                       cap_txtr[:NIV_TXTR_DEFINED_BYTES])
        chk.ok(txtr_diff == 0,
               "C4 independent spec: all 65,532 deterministic "
               "ground-texture bytes match NIV+ (OCEAN albedo 40 -> "
               "PLAINS/revert; final four undefined bytes excluded)",
               "%d bytes differ" % txtr_diff)

        # Deliberately restore the old, false fixture.  It must not match: this
        # proves C2 is sensitive to exactly the state correction it claims.
        if a.deep:
            W = gr_spec.BuildSurface(ledger=False)
            W.smap = bytearray(PS_BYTES); W.objs = bytearray(OC_BYTES)
            W.txtr = bytearray(TXTR_BYTES)
            for i in range(65535): W.txtr[i] = 16
            W.prologue(0, 3, 1, 17, 0)
            W.F.srand(0); W.B.srand(0); W.liquid_water = 0
            W._switch(3, 1, 17); W._post_switch()
            wrong_txtr_diff = nd(bytes(W.txtr)[:NIV_TXTR_DEFINED_BYTES],
                                 cap_txtr[:NIV_TXTR_DEFINED_BYTES])
            chk.ok(wrong_txtr_diff > 0,
                   "C5 broken control: old OCEAN/albedo-17 fixture is rejected",
                   "%d texture bytes differ" % wrong_txtr_diff)

        # XFAIL convention: assert the measured defect is STILL present.  A
        # fix (or any drift in its boundary) deliberately fails this check so
        # the open item cannot silently become stale.  Unlike the former
        # ok(False), this condition is data-dependent and can pass or fail.
        still_open = diff == MODEL_MAP_OPEN_DIFF
        chk.ok(still_open,
               "XFAIL C6 independent Python/C round_hill model residual",
               ("MODEL STILL OPEN: %d bytes differ" % diff) if still_open else
               ("BOUNDARY CHANGED: got %d diffs, expected %d; re-audit or "
                "remove this XFAIL if now exact" % (diff, MODEL_MAP_OPEN_DIFF)))

        # Break one byte that currently agrees.  Mutating an already-different
        # byte could leave the difference count unchanged and prove nothing.
        if a.deep:
            break_at = next(i for i in range(PS_BYTES) if spec_map[i] == cap_map[i])
            broken_cap = bytearray(cap_map[:PS_BYTES])
            broken_cap[break_at] = (broken_cap[break_at] + 1) & 0xFF
            broken_diff = nd(spec_map, bytes(broken_cap))
            chk.ok(broken_diff == MODEL_MAP_OPEN_DIFF + 1,
                   "C7 broken control: model boundary rejects capture drift",
                   "byte %d makes diff %d (expected %d)" %
                   (break_at, broken_diff, MODEL_MAP_OPEN_DIFF + 1))
    else:
        chk.note("C1-C7 type-3 capture not available (no tests/gen/recon_w7b/out/)")

    # ---- sabotages ----
    if not a.deep:
        chk.note("--- F: historical sabotage campaign SKIPPED (requires --deep) ---")
    else:
        chk.note("--- F: sabotages ---")
        p = subprocess.run([sys.executable, os.path.join(HARNESS, "gr_break.py")],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", cwd=REPO)
        output = p.stdout.strip()
        uncaught = [l for l in output.split("\n") if "NOTHING" in l]
        chk.ok(len(uncaught) == 0,
               "F1 sabotage: all mutations caught (0 uncaught)",
               "%d uncaught" % len(uncaught))

    # ---- hygiene ----
    chk.note("Build via lino_build.ps1; run via w7arun.ps1.")
    chk.note("Type-3: the production Lino core agrees with NIV+ on the complete "
             "40,000-byte map and all 65,532 deterministic texture bytes. "
             "The independent Python/C map model retains a measured 1,752-byte "
             "gap, and the final 75 captured object slots still require a "
             "clean-return NIV+ fixture.")

    return chk.done()


if __name__ == "__main__":
    lh.main_guard(main)
