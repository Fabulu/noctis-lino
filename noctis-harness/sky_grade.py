r"""Wave 7b sky framed-stream generator and grader.

This module keeps attribution explicit: D records grade sky generation,
R grades composition from independently supplied expected SBG, and J grades
the live join.  The binary capture is a fourth party only for FINAL_SBG and
the defined surface palette; screenshots are never treated as byte oracles.
"""

import argparse
import os
import struct

import sky_corpus as C
import sky_spec as S


def results_for(cases, replay_by_id=None):
    replay_by_id = replay_by_id or {}
    model = S.SkyModel()
    return [model.run(case, replay_by_id.get(case["case_id"])) for case in cases]


def expected_stream(cases):
    return S.encode_stream(results_for(cases))


def replay_blob(cases):
    """Fresh raw SBG authority for the corpus's single R/J page row."""
    selected = [c for c in cases if c["flags"] & S.GRADE_PAGE]
    if len(selected) != 1:
        raise ValueError("replay materialisation requires exactly one GRADE_PAGE row")
    return S.SkyModel().run(selected[0]).final_sbg


def validate_replay_blob(blob):
    blob = bytes(blob)
    if len(blob) != S.ST_BYTES:
        raise ValueError("sky replay must be exactly %d bytes" % S.ST_BYTES)
    return blob


def records_by_case(records):
    out = {}
    for r in records:
        if r.kind == S.STREAM_END:
            continue
        out.setdefault(r.case_id, []).append(r)
    return out


def significant_bytes(r):
    return S._unpack_units(r.body, r.body_bytes)


def compare_records(expected_blob, actual_blob, label="producer"):
    expected = S.decode_stream(expected_blob)
    actual = S.decode_stream(actual_blob)
    errors = []
    if len(expected) != len(actual):
        errors.append("%s record count %d != %d" %
                      (label, len(actual), len(expected)))
        return errors
    for n, (e, a) in enumerate(zip(expected, actual)):
        eh = (e.kind, e.width, e.height, e.case_id, e.phase, e.body_bytes,
              e.sequence, e.flags, len(e.body))
        ah = (a.kind, a.width, a.height, a.case_id, a.phase, a.body_bytes,
              a.sequence, a.flags, len(a.body))
        if eh != ah:
            errors.append("%s record %d framing %r != %r" %
                          (label, n, ah, eh))
            continue
        flags = e.flags
        if e.kind == S.PALETTE and flags & S.PALETTE_UNDEFINED:
            if any(significant_bytes(a)):
                errors.append("%s case %d undefined PALETTE leaked nonzero bytes" %
                              (label, e.case_id))
            continue
        if e.kind == S.PALETTE and not flags & S.GRADE_PALETTE:
            continue
        if e.kind == S.SCALARS and not flags & S.GRADE_SCALARS:
            continue
        if e.kind in (S.REPLAY_PAGE, S.JOIN_PAGE) and not flags & S.GRADE_PAGE:
            errors.append("%s case %d emitted unrequested page" %
                          (label, e.case_id))
            continue
        if e.body != a.body:
            eb, ab = significant_bytes(e), significant_bytes(a)
            first = next((i for i, (x, y) in enumerate(zip(eb, ab)) if x != y),
                         min(len(eb), len(ab)))
            errors.append("%s case %d kind %d phase %d differs at byte %d" %
                          (label, e.case_id, e.kind, e.phase, first))
    return errors


def grade_binary_anchor(blob, expected_ids=None):
    records = S.decode_stream(blob)
    by = records_by_case(records)
    sbg, pal = S.verify_anchor_assets()
    errors = []
    canonical = {c["case_id"]: c for _, c in C.CASES
                 if c["flags"] & S.BINARY_ANCHOR}
    if expected_ids is None:
        expected_ids = tuple(sorted(canonical))
    else:
        expected_ids = tuple(sorted(expected_ids))
    if not expected_ids:
        raise ValueError("binary anchor grading requires at least one expected anchor ID")
    unknown = [case_id for case_id in expected_ids if case_id not in canonical]
    if unknown:
        raise ValueError("unknown expected binary anchor ids %r" % unknown)
    actual_ids = [r.case_id for r in records
                  if r.kind == S.META and r.flags & S.BINARY_ANCHOR]
    if sorted(actual_ids) != list(expected_ids):
        errors.append("binary anchor IDs/count %r != expected %r" %
                      (sorted(actual_ids), list(expected_ids)))
    anchors = [canonical[case_id] for case_id in expected_ids]
    for case in anchors:
        recs = by.get(case["case_id"], [])
        final = next((r for r in recs if r.kind == S.FINAL_SBG), None)
        palette = next((r for r in recs if r.kind == S.PALETTE), None)
        if final is None or significant_bytes(final) != sbg:
            got = b"" if final is None else significant_bytes(final)
            diff = len(sbg) if not got else sum(x != y for x, y in zip(got, sbg))
            errors.append("anchor case %d FINAL_SBG differs from capture in %d bytes" %
                          (case["case_id"], diff))
        if palette is None or significant_bytes(palette) != pal:
            got = b"" if palette is None else significant_bytes(palette)
            diff = len(pal) if not got else sum(x != y for x, y in zip(got, pal))
            errors.append("anchor case %d PALETTE differs from capture in %d bytes" %
                          (case["case_id"], diff))
    return errors


def anchor_poison_independence():
    """Prove unqualified scalar poison cannot influence anchored outputs."""
    a = dict(C.ANCHOR)
    b = dict(a, dsd1_bits=C.bits(-17.5), exposure_bits=C.bits(89.75))
    ma, mb = S.SkyModel().run(a), S.SkyModel().run(b)
    if (ma.pre_horizon, ma.final_sbg, ma.palette) != \
       (mb.pre_horizon, mb.final_sbg, mb.palette):
        raise AssertionError("scalar poison affected pixel/palette anchor")
    if ma.scalars == mb.scalars:
        raise AssertionError("scalar poison did not exercise scalar path")
    return True


def anchor_input_separation():
    """Prove the output-derived anchor is not accepted by broad inputs."""
    anchor = S.SkyModel().run(C.ANCHOR)
    seed = S.SkyModel().run(dict(
        C.ANCHOR, global_surface_seed=S.u32(C.ANCHOR["global_surface_seed"] + 1)))
    albedo = S.SkyModel().run(dict(C.ANCHOR, albedo=40))
    if seed.final_sbg == anchor.final_sbg:
        raise AssertionError("anchor seed perturbation did not separate FINAL_SBG")
    if albedo.final_sbg == anchor.final_sbg:
        raise AssertionError("anchor separating albedo=40 did not separate FINAL_SBG")
    return True


def structural_selftest():
    text = C.validate_canonical()
    cases = C.parse_text(text)
    if len(cases) != len(C.CASES):
        raise AssertionError("corpus count drift")
    smoke = expected_stream([C.SMOKE_CASES[0][1]])
    recs = S.decode_stream(smoke)
    if recs[-1].kind != S.STREAM_END:
        raise AssertionError("missing trailer")
    bad = bytearray(smoke)
    struct.pack_into("<I", bad, 11 * 4, 1)  # reserved[0]
    try:
        S.decode_stream(bytes(bad))
    except ValueError:
        pass
    else:
        raise AssertionError("nonzero reserved header accepted")
    rejection = S.Record(S.STREAM_END, 4, 1, 0, 0, 16, 0, 0,
                         [0, 1, 0, 0])
    rejection_blob = struct.pack("<20I", *rejection.units())
    S.decode_rejection_stream(rejection_blob)
    try:
        S.decode_stream(rejection_blob)
    except ValueError:
        pass
    else:
        raise AssertionError("diagnostic rejection accepted as success stream")
    try:
        S.decode_rejection_stream(smoke)
    except ValueError:
        pass
    else:
        raise AssertionError("successful/partial stream accepted as rejection")
    try:
        C.parse_text(C.encode_text(C.SMOKE_CASES) + "7\n")
    except ValueError:
        pass
    else:
        raise AssertionError("tokens after terminator accepted")
    malformed = [
        "1 " + "0 " * 27 + "\n0\n",       # truncated row
        "7\n0\n",                           # unknown opcode
        C.encode_text(C.SMOKE_CASES).rsplit("0\n", 1)[0],  # no terminator
    ]
    vals = C.case_units(C.SMOKE_CASES[0][1])
    vals[5] = 2                              # atmosphere boolean
    malformed.append(" ".join(C.signed_token(v) for v in vals) + "\n0\n")
    malformed.extend(C.malformed_matrix().values())
    vals = C.case_units(C.SMOKE_CASES[0][1])
    vals[2] = S.GRADE_PALETTE | S.PALETTE_UNDEFINED
    malformed.append(" ".join(C.signed_token(v) for v in vals) + "\n0\n")
    for bad_text in malformed:
        try:
            C.parse_text(bad_text)
        except ValueError:
            pass
        else:
            raise AssertionError("malformed corpus accepted: %r" % bad_text[:80])
    try:
        validate_replay_blob(bytes(S.ST_BYTES + 1))
    except ValueError:
        pass
    else:
        raise AssertionError("oversized replay accepted")
    return smoke


def python_semantic_selftest():
    by_name = dict(C.CASES)
    model = S.SkyModel()
    if S.cloudy_denominator_bound() != (1, 5, -5, -4):
        raise AssertionError("cloud denominator proof drift")
    reassoc, premature = S.horizon_operation_proof()
    if reassoc != 0 or premature is None:
        raise AssertionError("horizon operation-order proof drift")
    radii = S.ocean_cloud_radii(by_name["ocean_11draw_b_min_denominator"])
    if 5 not in radii:
        raise AssertionError("minimum-denominator corpus row has no radius-5 cloud")
    gates = {
        "venus_both_optional_smoothers": (True, True),
        "venus_psmooth_only": (False, True),
        "venus_ssmooth_only": (True, False),
    }
    for name, want in gates.items():
        got = S.venus_optional_gates(by_name[name])
        if got != want:
            raise AssertionError("%s gates %r != %r" % (name, got, want))
    anchor = model.run(by_name["anchor_ocean_night_pixels"])
    repeat = model.run(by_name["anchor_repeat"])
    if (anchor.pre_horizon, anchor.final_sbg, anchor.palette,
            anchor.scalars, anchor.guards) != \
       (repeat.pre_horizon, repeat.final_sbg, repeat.palette,
            repeat.scalars, repeat.guards):
        raise AssertionError("repeated anchor retained cross-case state")
    sbg, pal = S.verify_anchor_assets()
    if anchor.final_sbg != sbg or anchor.palette != pal:
        raise AssertionError("binary anchor bytes drift")
    float_witness = model.run(by_name["float_store_palette_witness"])
    if float_witness.palette[267] != 24:
        raise AssertionError("float-store palette witness byte267=%d, want 24" %
                             float_witness.palette[267])
    double_witness = model.run(by_name["double_expression_spill_witness"])
    if double_witness.palette[462] != 53:
        raise AssertionError(
            "double-expression spill witness byte462=%d, want 53" %
            double_witness.palette[462])
    page = model.run(by_name["page_shifted"])
    page_sha = "a68a5775f2ad05d04cdd6c399b42f06a5d2a24cd555e81348ef7e47f70ecf421"
    if S.sha256(page.replay_page) != page_sha or \
       S.sha256(page.join_page) != page_sha:
        raise AssertionError("SSBG/offsets-map page composition witness drift")
    if anchor.ledgers[2][1] != 11:
        raise AssertionError("OCEAN colours consumed %d BRTL draws, want 11" %
                             anchor.ledgers[2][1])
    thin = model.run(by_name["thin_type5_sixdraw"])
    if thin.ledgers[2][1] != 6:
        raise AssertionError("type5 colours consumed %d BRTL draws, want 6" %
                             thin.ledgers[2][1])
    if thin.scalars[0] != 26 or thin.palette[135] != 37:
        raise AssertionError(
            "type5 pre-switch sb witness drift: brightness=%d palette135=%d" %
            (thin.scalars[0], thin.palette[135]))
    tz = model.run(by_name["venus_tail_zero"])
    th = model.run(by_name["venus_tail_hostile"])
    if tz.final_sbg == th.final_sbg:
        raise AssertionError("hostile tail did not witness lssmooth overread")
    for name, result in (("zero", tz), ("hostile", th)):
        g = result.guards
        if g[3] or g[4] != g[5] or g[6] != g[7]:
            raise AssertionError("%s tail/canary guard failure: %r" % (name, g))
        if g[8] != g[9]:
            raise AssertionError("%s QUADWORDS was not restored" % name)
    if set(anchor.final_sbg[119 * 360:120 * 360]) != {3, 4}:
        raise AssertionError("anchor row119 witness drift")
    if set(anchor.final_sbg[120 * 360:121 * 360]) != {8, 9}:
        raise AssertionError("anchor row120 witness drift")
    if set(anchor.final_sbg[150 * 360:151 * 360]) != {8} or \
       set(anchor.final_sbg[179 * 360:180 * 360]) != {8}:
        raise AssertionError("anchor bottom-band witness drift")
    anchor_poison_independence()
    anchor_input_separation()
    # Absence is not success: the canonical anchor grader requires both exact
    # stable IDs, while a batched call may explicitly request one of them.
    if not grade_binary_anchor(S.encode_stream([anchor, repeat])) == []:
        raise AssertionError("complete binary anchor pair failed grading")
    if not grade_binary_anchor(S.encode_stream([anchor]), expected_ids=(1,)) == []:
        raise AssertionError("explicit one-row binary anchor failed grading")
    if not grade_binary_anchor(S.encode_stream([float_witness])):
        raise AssertionError("zero-anchor stream passed binary anchor grading")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--write-expected")
    ap.add_argument("--write-replay")
    ap.add_argument("--write-oversized-replay",
                    help="write the 64,801-byte negative replay fixture")
    ap.add_argument("--compare", action="append", default=[])
    ap.add_argument("--check-anchor", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--python-selftest", action="store_true")
    args = ap.parse_args()

    if args.write_oversized_replay:
        with open(args.write_oversized_replay, "wb") as fh:
            fh.write(bytes(S.ST_BYTES + 1))
        print("wrote oversized negative replay %s: %d bytes" %
              (os.path.abspath(args.write_oversized_replay), S.ST_BYTES + 1))

    if args.corpus:
        with open(args.corpus, encoding="ascii") as fh:
            cases = C.parse_text(fh.read())
    elif args.smoke:
        cases = [C.SMOKE_CASES[0][1]]
    else:
        cases = [case for _, case in C.CASES]

    if args.selftest:
        structural_selftest()
        print("structural selftest PASS")
    if args.python_selftest:
        python_semantic_selftest()
        print("Python semantic selftest PASS")

    expected = None
    if args.write_expected or args.compare or args.check_anchor:
        expected = expected_stream(cases)
    if args.write_expected:
        with open(args.write_expected, "wb") as fh:
            fh.write(expected)
        print("wrote %s: %d bytes" %
              (os.path.abspath(args.write_expected), len(expected)))
    if args.write_replay:
        replay = replay_blob(cases)
        with open(args.write_replay, "wb") as fh:
            fh.write(replay)
        print("wrote %s: %d bytes, sha256=%s" %
              (os.path.abspath(args.write_replay), len(replay), S.sha256(replay)))

    failures = []
    corpus_anchor_ids = tuple(sorted(
        c["case_id"] for c in cases if c["flags"] & S.BINARY_ANCHOR))
    anchor_checked_actual = False
    for path in args.compare:
        with open(path, "rb") as fh:
            actual = fh.read()
        err = compare_records(expected, actual, os.path.basename(path))
        if args.check_anchor:
            try:
                err.extend(grade_binary_anchor(
                    actual, expected_ids=corpus_anchor_ids or None))
            except ValueError as exc:
                err.append(str(exc))
            anchor_checked_actual = True
        failures.extend(err)
        print("%s: %s" % (path, "PASS" if not err else "FAIL (%d)" % len(err)))
    if args.check_anchor and not anchor_checked_actual:
        try:
            failures.extend(grade_binary_anchor(
                expected, expected_ids=corpus_anchor_ids or None))
        except ValueError as exc:
            failures.append(str(exc))
    if failures:
        for e in failures:
            print("FAIL:", e)
        raise SystemExit(1)
    if args.write_expected or args.compare or args.check_anchor:
        print("sky grade PASS")


if __name__ == "__main__":
    main()
