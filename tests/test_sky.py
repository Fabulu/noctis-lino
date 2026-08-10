r"""Wave 7b sky: create_sky, palette/scalars, horizon, and SP join.

This registered test defaults to a lean canonical check.  The completed 2026
adversarial campaign remains available only through ``--deep`` as historical
evidence; it is not a routine development gate.  The test owns no stored dump:
Python/C artifacts are freshly materialised under ``tests/gen/w7bsky`` and
copied Lino builds under the adjacent guarded ``tests/gen/w7bskylino``.

Claims:
  * Python == rebuilt C == rebuilt Lino for strict SKY1 framing and D records.
  * R replays an independently materialised expected SBG; J composes the live
    producer SBG.  Pages grade only after the D and R records agree.
  * The stored NIV+ R2.3 binary claim is only FINAL_SBG + surface palette for
    the pinned type-3 OCEAN/night row.  Scalar-only dsd1/exposure values are
    finite poison with GRADE_SCALARS clear; screenshots are not byte oracles.
  * Undefined palettes are required to emit zero bytes and carry no exact
    palette claim.
  * Historical deep-audit mode can replay the old C/Lino mutation campaign.
    It is not part of normal development verification.

Usage:
    python tests/test_sky.py               # lean: Python/C + one Lino D/R/J row
    python tests/test_sky.py --deep        # historical exhaustive audit
    python tests/test_sky.py --quick       # schema/Python/C only; no Lino
    python tests/test_sky.py --no-lino
    python tests/test_sky.py --no-mutants
"""

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WORK = os.path.join(ROOT, "work")
HARNESS = os.path.join(ROOT, "noctis-harness")
SAND = os.path.join(HERE, "gen", "w7bsky")
LINO_SAND = os.path.join(HERE, "gen", "w7bskylino")

for path in (HERE, HARNESS):
    if path not in sys.path:
        sys.path.insert(0, path)

import linoharness as lh
import sky_break
import sky_corpus
import sky_grade
import sky_spec


LINO_LIBS = (
    "fbmem.txt", "fbpal.txt", "pgfp.txt", "spmem.txt", "spbg.txt",
    "brtl.txt", "mul64frag.txt", "suseed.txt", "surng.txt", "subuf.txt",
    "susm.txt", "sky.txt",
)
FP_LIBS = ("fpabi.txt", "fpctl.txt", "fpx87.txt", "fpconv.txt")
ASSETS = ("globes.map", "offsets.map")


def sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def remove_lino_sandbox():
    """Remove only the deterministic test-owned sandbox, never a redirect."""
    target = os.path.normcase(os.path.abspath(LINO_SAND))
    expected = os.path.normcase(os.path.abspath(
        os.path.join(HERE, "gen", "w7bskylino")))
    parent = os.path.normcase(os.path.abspath(os.path.join(HERE, "gen")))
    if (target != expected or os.path.dirname(target) != parent or
            os.path.basename(target) != "w7bskylino"):
        raise RuntimeError("refusing unexpected Lino sandbox %s" % target)
    if not os.path.exists(target):
        return
    resolved = os.path.normcase(os.path.realpath(target))
    if resolved != expected:
        raise RuntimeError("refusing redirected Lino sandbox %s -> %s" %
                           (target, resolved))
    shutil.rmtree(target)


def prepare_sandbox():
    # This directory is test-owned, explicit, and beneath tests/gen.
    if os.path.isdir(SAND):
        shutil.rmtree(SAND)
    os.makedirs(os.path.join(SAND, "fp"))
    corpus = os.path.join(SAND, "sky-corpus.txt")
    replay = os.path.join(SAND, "sky-replay.bin")
    expected = os.path.join(SAND, "python.bin")
    cases = [case for _, case in sky_corpus.CASES]
    with open(corpus, "w", encoding="ascii", newline="\n") as fh:
        fh.write(sky_corpus.encode_text(sky_corpus.CASES))
    replay_bytes = sky_grade.replay_blob(cases)
    with open(replay, "wb") as fh:
        fh.write(replay_bytes)
    results = sky_grade.results_for(cases)
    expected_blob = sky_spec.encode_stream(results)
    with open(expected, "wb") as fh:
        fh.write(expected_blob)
    return cases, corpus, replay, expected_blob


def build_run_c(corpus, replay):
    src = os.path.join(SAND, "skyref.c")
    exe = os.path.join(SAND, "skyref.exe")
    out = os.path.join(SAND, "c.bin")
    shutil.copy2(os.path.join(HARNESS, "sky_ref.c"), src)
    cmd = [os.environ.get("CC", "gcc"), "-std=c11", "-O2", "-Wall",
           "-Wextra", "-Werror", "-o", exe, src, "-lm"]
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if p.returncode:
        return None, None, "gcc failed: " + ((p.stdout or "") + (p.stderr or ""))[:500]
    p = subprocess.run([exe, corpus, out, "--offsets",
                        os.path.join(WORK, "offsets.map"), "--replay", replay],
                       cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if p.returncode or not os.path.isfile(out):
        return None, exe, "C run failed: " + ((p.stdout or "") + (p.stderr or ""))[:500]
    with open(out, "rb") as fh:
        return fh.read(), exe, "ok"


def run_c_case(exe, corpus, replay, out):
    p = subprocess.run([exe, corpus, out, "--offsets",
                        os.path.join(WORK, "offsets.map"), "--replay", replay],
                       cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if p.returncode or not os.path.isfile(out):
        return None, "C case run failed: " + \
            ((p.stdout or "") + (p.stderr or ""))[:500]
    with open(out, "rb") as fh:
        return fh.read(), "ok"


def prepare_lino(corpus, replay):
    if "--" in LINO_SAND or "_" in LINO_SAND:
        raise RuntimeError("unsafe Lino sandbox path: %s" % LINO_SAND)
    remove_lino_sandbox()
    os.makedirs(os.path.join(LINO_SAND, "fp"))
    for name in LINO_LIBS:
        shutil.copy2(os.path.join(WORK, name), os.path.join(LINO_SAND, name))
    for name in FP_LIBS:
        shutil.copy2(os.path.join(WORK, "fp", name),
                     os.path.join(LINO_SAND, "fp", name))
    for name in ASSETS:
        shutil.copy2(os.path.join(WORK, name), os.path.join(LINO_SAND, name))
    corpus_dst = os.path.join(LINO_SAND, "sky-corpus.txt")
    replay_dst = os.path.join(LINO_SAND, "sky-replay.bin")
    if os.path.abspath(corpus) != os.path.abspath(corpus_dst):
        shutil.copy2(corpus, corpus_dst)
    if os.path.abspath(replay) != os.path.abspath(replay_dst):
        shutil.copy2(replay, replay_dst)
    source = open(os.path.join(WORK, "skymain.txt"), "r",
                  encoding="utf-8").read()
    relative = "GRSKHcorpname = { sky-corpus.txt };"
    if source.count(relative) != 1:
        raise RuntimeError("skymain must use exactly one relative sky-corpus.txt literal")
    main = os.path.join(LINO_SAND, "skymain.txt")
    with open(main, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(source)
    return main


def build_lino(corpus, replay):
    try:
        main = prepare_lino(corpus, replay)
    except Exception as e:
        return None, "sandbox preparation failed: %s" % e
    rc, note = lh.build(main, timeout_sec=300)
    if rc:
        return None, "Lino build failed: " + note.strip()[:500]
    exe = os.path.splitext(main)[0] + ".exe"
    return exe, note.strip()


def run_lino_case(exe, timeout):
    out = os.path.join(LINO_SAND, "sky-out.bin")
    p = subprocess.run([
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
        os.path.join(HERE, "w7arun.ps1"), "-Exe", exe, "-Out", out,
        "-TimeoutSec", str(timeout),
    ], cwd=LINO_SAND, capture_output=True, text=True, encoding="utf-8",
       errors="replace")
    note = ((p.stdout or "") + (p.stderr or "")).strip()
    if p.returncode or not os.path.isfile(out):
        return None, "Lino run failed: " + note[:500]
    with open(out, "rb") as fh:
        return fh.read(), note


def rejection_stream(blob):
    """A rejection may contain only its explicit failing STREAM_END."""
    try:
        sky_spec.decode_rejection_stream(blob)
    except Exception:
        return False
    return True


def run_c_rejection(exe, corpus, replay, out):
    if os.path.exists(out):
        os.remove(out)
    p = subprocess.run([exe, corpus, out, "--offsets",
                        os.path.join(WORK, "offsets.map"), "--replay", replay],
                       cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if not os.path.exists(out):
        return p.returncode != 0, "rc=%d no output" % p.returncode
    with open(out, "rb") as fh:
        blob = fh.read()
    return rejection_stream(blob), "rc=%d output=%d" % (p.returncode, len(blob))


def run_malformed_matrix(chk, lexe, cexe, case_timeout):
    """Require Python, C, and Lino to reject without partial valid records."""
    corpus = os.path.join(LINO_SAND, "sky-corpus.txt")
    replay = os.path.join(LINO_SAND, "sky-replay.bin")
    cout = os.path.join(SAND, "c-reject.bin")
    failures = []
    matrix = list(sorted(sky_corpus.malformed_matrix().items()))
    page = next((name, case) for name, case in sky_corpus.CASES
                if case["flags"] & sky_spec.GRADE_PAGE)
    matrix.append(("oversized_replay", sky_corpus.encode_text([page])))
    for name, text in matrix:
        if name == "oversized_replay":
            try:
                sky_grade.validate_replay_blob(bytes(sky_spec.ST_BYTES + 1))
            except ValueError:
                pass
            else:
                failures.append((name, "Python accepted oversized replay"))
        else:
            try:
                sky_corpus.parse_text(text)
            except ValueError:
                pass
            else:
                failures.append((name, "Python accepted malformed corpus"))
        with open(corpus, "w", encoding="ascii", newline="\n") as fh:
            fh.write(text)
        with open(replay, "wb") as fh:
            fh.write(bytes(sky_spec.ST_BYTES +
                           (1 if name == "oversized_replay" else 0)))
        cok, cnote = run_c_rejection(cexe, corpus, replay, cout)
        if not cok:
            failures.append((name, "C did not cleanly reject: " + cnote))
        lblob, lnote = run_lino_case(lexe, case_timeout)
        if lblob is None or not rejection_stream(lblob):
            failures.append((name, "Lino did not emit rejection-only stream: " +
                             lnote[:200]))
    failed_names = {name for name, _ in failures}
    chk.ok(not failures,
           "X1 Python/C/Lino reject malformed corpus/replay without partial records",
           "%d/%d" % (len(matrix) - len(failed_names), len(matrix)) if failures else
           "%d/%d" % (len(matrix), len(matrix)))
    if failures:
        chk.note("X1 first failure %s: %s" % failures[0])
    return not failures


def run_lino_batches(chk, exe, cexe, case_timeout, rows=None):
    """Run selected canonical rows independently through one compiled runner."""
    corpus = os.path.join(LINO_SAND, "sky-corpus.txt")
    replay = os.path.join(LINO_SAND, "sky-replay.bin")
    cout = os.path.join(SAND, "c-case.bin")
    failures = []
    passed = 0
    all_rows = rows is None
    rows = list(sky_corpus.CASES if all_rows else rows)
    for name, case in rows:
        t0 = time.monotonic()
        result = sky_spec.SkyModel().run(case)
        expected = sky_spec.encode_stream([result])
        with open(corpus, "w", encoding="ascii", newline="\n") as fh:
            fh.write(sky_corpus.encode_text([(name, case)]))
        with open(replay, "wb") as fh:
            fh.write(result.final_sbg)
        cblob, cnote = run_c_case(cexe, corpus, replay, cout)
        if cblob is None:
            failures.append((name, time.monotonic() - t0, cnote))
            continue
        cerrors = sky_grade.compare_records(expected, cblob, "C/%s" % name)
        if cerrors:
            failures.append((name, time.monotonic() - t0, cerrors[0]))
            continue
        lblob, lnote = run_lino_case(exe, case_timeout)
        elapsed = time.monotonic() - t0
        if lblob is None:
            failures.append((name, elapsed, lnote))
            continue
        lerrors = sky_grade.compare_records(expected, lblob, "Lino/%s" % name)
        anchor_errors = (sky_grade.grade_binary_anchor(
            lblob, expected_ids=(case["case_id"],))
            if case["flags"] & sky_spec.BINARY_ANCHOR else [])
        if lerrors or anchor_errors or lblob != cblob:
            why = (lerrors or anchor_errors or ["Lino/C one-case streams differ"])[0]
            failures.append((name, elapsed, why))
            continue
        passed += 1
    total = len(rows)
    detail = ("%d/%d" % (total, total) if not failures else
              "%d/%d; first failure %s at %.1fs: %s" %
              (passed, total, failures[0][0], failures[0][1], failures[0][2]))
    chk.ok(not failures and passed == total,
           "L1 per-case Lino == C == Python across %s canonical D/R/J rows" %
           ("all" if all_rows else "selected"),
           detail)
    return not failures


def compare(chk, expected, actual, producer):
    try:
        errors = sky_grade.compare_records(expected, actual, producer)
    except Exception as e:
        chk.ok(False, "%s SKY1 stream is structurally valid" % producer, str(e))
        return False
    chk.ok(not errors, "%s == Python on all graded D/R/J records" % producer,
           errors[0] if errors else "strict framing and bodies")
    try:
        anchor_errors = sky_grade.grade_binary_anchor(actual)
    except Exception as e:
        anchor_errors = [str(e)]
    chk.ok(not anchor_errors,
           "%s binary anchor FINAL_SBG + PALETTE exact" % producer,
           anchor_errors[0] if anchor_errors else
           "%s / %s" % (sky_spec.ANCHOR_SBG_SHA256,
                          sky_spec.ANCHOR_PALETTE_SHA256))
    return not errors and not anchor_errors


def run_mutants(chk, require_lino, lino_timeout):
    killed = []
    failed = []
    for name in sorted(sky_break.MUTANTS):
        ok, detail = sky_break.qualify(name)
        (killed if ok else failed).append((name, detail))
    chk.ok(not failed and len(killed) == len(sky_break.MUTANTS),
           "M1 all applicable C one-edit mutants killed at declared witnesses",
           "%d killed; %s" % (len(killed), failed[0] if failed else "0 failed"))
    try:
        den = sky_spec.cloudy_denominator_bound()
        horiz = sky_spec.horizon_operation_proof()
        proof_ok = den == (1, 5, -5, -4) and horiz[0] == 0 and horiz[1] is not None
    except Exception as e:
        proof_ok = False; den = horiz = str(e)
    chk.ok(proof_ok,
           "M2 unkillable proposals replaced by reachable denominator/int-div controls",
           "cloud=%r horizon=%r" % (den, horiz))
    static_failures = sky_break.static_check_lino_mutants()
    required_lino = sky_break.REQUIRED_LINO_MUTANT_COUNT
    required_names = {"FLOAT_STORE_BOUNDARY", "SBG_OOB_ADDR"}
    matrix_names = set(sky_break.LINO_MUTANTS)
    static_ok = (not static_failures and len(matrix_names) == required_lino and
                 required_names <= matrix_names)
    chk.ok(static_ok,
           "M3 all Lino one-edit substitutions are unique and statically guarded",
           "%d/%d qualified; %s" %
           (required_lino - len(static_failures), required_lino,
            static_failures[0] if static_failures else "0 drift"))
    if require_lino and static_ok:
        lino_killed = []
        lino_failed = []
        for name in sorted(sky_break.LINO_MUTANTS):
            ok, detail = sky_break.qualify_lino(
                name, sandbox_root=LINO_SAND, timeout=lino_timeout, keep=False)
            (lino_killed if ok else lino_failed).append((name, detail))
        chk.ok(not lino_failed and len(lino_killed) == required_lino,
               "M4 all copied Lino one-edit mutants killed at declared witnesses",
               "%d killed; %s" %
               (len(lino_killed), lino_failed[0] if lino_failed else "0 failed"))
    elif not require_lino:
        chk.note("Dynamic Lino mutation matrix skipped with --no-lino.")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--deep", action="store_true",
                    help="run the historical malformed/full-corpus/mutation audit")
    ap.add_argument("--quick", action="store_true",
                    help="compatibility alias: skip Lino and deep audit")
    ap.add_argument("--no-lino", action="store_true")
    ap.add_argument("--no-mutants", action="store_true")
    ap.add_argument("--lino-case-timeout", type=int, default=600)
    args = ap.parse_args(argv)
    if args.quick:
        args.no_lino = True
        args.no_mutants = True

    chk = lh.Check("WAVE 7b - create_sky + horizon + SP D/R/J")
    chk.note("Binary claim: pinned OCEAN/night FINAL_SBG + surface palette only.")
    chk.note("All Python/C/Lino products use guarded private sandboxes under tests/gen.")

    source_paths = ([os.path.join(HARNESS, x) for x in
                     ("sky_spec.py", "sky_corpus.py", "sky_grade.py",
                      "sky_ref.c", "sky_break.py")]
                    + [os.path.join(WORK, x) for x in LINO_LIBS]
                    + [os.path.join(WORK, "skymain.txt"),
                       os.path.join(ROOT, "lino_build.ps1"),
                       os.path.join(HERE, "w7arun.ps1")])
    before = ({p: sha_file(p) for p in source_paths} if args.deep else None)

    try:
        structural = sky_grade.structural_selftest()
        chk.ok(bool(structural), "P1 schema/framing malformed-input selftest",
               "%d-byte smoke stream" % len(structural))
    except Exception as e:
        chk.ok(False, "P1 schema/framing malformed-input selftest", str(e))
    try:
        sky_grade.python_semantic_selftest()
        chk.ok(True, "P2 Python determinism/draw/tail/QW/band/poison witnesses")
    except Exception as e:
        chk.ok(False, "P2 Python determinism/draw/tail/QW/band/poison witnesses", str(e))

    cases = corpus = replay = expected = None
    try:
        cases, corpus, replay, expected = prepare_sandbox()
        recs = sky_spec.decode_stream(expected)
        chk.ok(len(cases) == len(sky_corpus.CASES) and
               recs[-1].body[0] == len(sky_corpus.CASES),
               "P3 canonical private corpus/stream is nonempty and complete",
               "%d cases, %d records" % (len(cases), len(recs)))
        chk.ok(len(open(replay, "rb").read()) == sky_spec.ST_BYTES,
               "R0 replay blob freshly materialised and length-checked",
               "sha256 " + sha_file(replay))
    except Exception as e:
        chk.ok(False, "P3 canonical private corpus/stream is nonempty and complete", str(e))

    cblob = cexe = None
    if corpus and replay:
        cblob, cexe, note = build_run_c(corpus, replay)
        chk.ok(cblob is not None, "C0 rebuilt C reference ran", note)
        if cblob is not None:
            compare(chk, expected, cblob, "C")

    if not args.no_lino and corpus and replay and cexe:
        lexe, note = build_lino(corpus, replay)
        chk.ok(lexe is not None, "L0 copied Lino sky runner built once", note[:300])
        if lexe is not None:
            if args.deep:
                malformed_ok = run_malformed_matrix(
                    chk, lexe, cexe, args.lino_case_timeout)
            else:
                malformed_ok = True
            if malformed_ok and args.deep:
                run_lino_batches(chk, lexe, cexe, args.lino_case_timeout)
            elif malformed_ok:
                lean_rows = [row for row in sky_corpus.CASES
                             if row[0] == "page_shifted"]
                run_lino_batches(chk, lexe, cexe, args.lino_case_timeout,
                                 rows=lean_rows)
                chk.note("Lean default: one end-to-end Lino D/R/J row; use --deep only for the historical audit.")
            else:
                chk.note("Lino canonical batches skipped after parser gate failure.")
    else:
        chk.note("Lino D/R/J: SKIPPED (--quick/--no-lino); this is not full acceptance.")

    if args.deep and not args.no_mutants:
        run_mutants(chk, require_lino=not args.no_lino,
                    lino_timeout=args.lino_case_timeout)
    else:
        chk.note("Historical mutation campaign: SKIPPED (requires --deep).")

    if args.deep:
        after = {p: sha_file(p) for p in source_paths}
        chk.ok(before == after, "H1 source/work inputs unchanged by private-sandbox run")
    chk.note("No screenshot is graded. Undefined palettes are zero-only framing records.")
    chk.note("Build uses lino_build.ps1; run uses tests/w7arun.ps1.")
    result = chk.done()
    remove_lino_sandbox()
    return result


if __name__ == "__main__":
    lh.main_guard(main)
