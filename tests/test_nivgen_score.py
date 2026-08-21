"""Focused API checks for the NIVGEN sheet scorer."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import nivgen_score  # noqa: E402
import nivgen_score_compare  # noqa: E402
import nivgen_score_transition  # noqa: E402


def check(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"PASS {label}")


def main() -> int:
    args = argparse.Namespace(timeout=17, exe="fixture.exe")
    call = nivgen_score.namespace(
        args, -11, 22, -33, 4, 123, -45, "00" * 16, True)
    check(call.diagnostic is False,
          "sheet calls explicitly disable the optional diagnostic trailer")
    check((call.x, call.y, call.z, call.p, call.lon, call.lat) ==
          (-11, 22, -33, 4, 123, -45),
          "sheet coordinates survive namespace construction")
    check(call.build is True and call.timeout == 17 and call.exe == "fixture.exe",
          "build, timeout, and executable controls survive namespace construction")

    header = [0x4E494E32, 1]
    buffers = {"surface": b"surface"}
    expected = {"hashes": {"surf": {"fnv": "12345678"}}}
    with (mock.patch.object(
            nivgen_score.nivtest, "run_lino",
            return_value=(header, buffers, None)) as run_lino,
          mock.patch.object(
              nivgen_score.nivtest, "results",
              return_value=expected) as results):
        got = nivgen_score.run_site(
            args, (-11, 22, -33, 4), 123, -45, "00" * 16, True)

    check(got is expected,
          "run_site accepts nivtest's header/buffers/diagnostics return contract")
    emitted = run_lino.call_args.args[0]
    check(emitted.diagnostic is False and emitted.gap == "00" * 16,
          "run_site forwards a non-diagnostic call and the original heap gap")
    results.assert_called_once_with(header, buffers)
    check(True, "run_site scores only the public header and byte buffers")

    first = {
        "columns": [{"name": "key"}],
        "rows": [["A"], ["B"]],
        "total": 3,
        "page": 1,
        "pageSize": 2,
    }
    second = {
        "columns": [{"name": "key"}],
        "rows": [["C"]],
        "total": 3,
        "page": 2,
        "pageSize": 2,
    }
    with (mock.patch.object(nivgen_score, "fetch_payload",
                            side_effect=[first, second]) as fetch,
          mock.patch.object(nivgen_score.time, "sleep") as sleep):
        rows = nivgen_score.fetch_rows(
            "https://example.invalid/sheet?page=1&pageSize=2",
            None, True, 0.75)
    check([row["key"] for row in rows] == ["A", "B", "C"] and
          fetch.call_count == 2,
          "all-pages scoring reads every advertised page exactly once")
    sleep.assert_called_once_with(0.75)
    check(True, "all-pages scoring waits between sequential requests")

    normalized = {
        "columns": ["key", "type", "orig_sect_def_hm"],
        "rows": [["NORMALIZED|0", 5, "301D7754"]],
        "total": 1,
        "page": 1,
        "pageSize": 1,
    }
    with tempfile.TemporaryDirectory(prefix="nivgen-score-") as temp_name:
        snapshot = Path(temp_name) / "sheet.json"
        snapshot.write_text(json.dumps(normalized), encoding="utf-8")
        with mock.patch.object(nivgen_score, "fetch_payload") as fetch:
            rows = nivgen_score.fetch_rows(
                "https://example.invalid/sheet", str(snapshot), True, 0.75)
    check(rows == [{"key": "NORMALIZED|0", "type": 5,
                    "orig_sect_def_hm": "301D7754"}],
          "normalized snapshots with string columns load offline")
    fetch.assert_not_called()
    check(True, "offline normalized snapshots never fetch a live page")

    transition_fields = nivgen_score_transition.FIELDS
    columns = (["key", "type"] +
               ["orig_" + field for field in transition_fields] +
               ["lino_" + field for field in transition_fields])

    def snapshot_row(key, body_type, orig_surf, lino_surf,
                     orig_pal, lino_pal):
        values = {name: None for name in columns}
        values.update({
            "key": key, "type": body_type,
            "orig_surf": orig_surf, "lino_surf": lino_surf,
            "orig_pal": orig_pal, "lino_pal": lino_pal,
        })
        return [values[name] for name in columns]

    snapshot_data = {
        "columns": columns,
        "rows": [
            snapshot_row("A|0", 1, "AAAAAAAA", "BBBBBBBB",
                         "CCCCCCCC", "CCCCCCCC"),
            snapshot_row("B|0", 5, "DDDDDDDD", "DDDDDDDD",
                         "EEEEEEEE", None),
        ],
    }
    score_data = {
        "reports": [
            {
                "key": "A|0", "type": 1,
                "comparisons": {
                    "surf": {"got": "AAAAAAAA", "expected": "AAAAAAAA",
                             "match": True},
                    "pal": {"got": "FFFFFFFF", "expected": "CCCCCCCC",
                            "match": False},
                },
            },
            {
                "key": "B|0", "type": 5,
                "comparisons": {
                    "surf": {"got": "DDDDDDDD", "expected": "DDDDDDDD",
                             "match": True},
                    "pal": {"got": "EEEEEEEE", "expected": "EEEEEEEE",
                            "match": True},
                },
            },
        ],
        "exact": 3,
        "graded": 4,
    }
    transition = nivgen_score_transition.compare(
        snapshot_data, score_data, "snapshot-digest", "score-digest")
    check(transition["comparisons"] == {
              "before_exact": 2, "after_exact": 3, "total": 4,
              "changed_values": 3},
          "local transition report measures exactness and changed values")
    check(transition["rows"]["before_exact"] == 0 and
          transition["rows"]["after_exact"] == 1 and
          transition["fields"]["surf"]["transitions"] == {
              "exact->exact": 1, "mismatch->exact": 1} and
          transition["fields"]["pal"]["transitions"] == {
              "exact->mismatch": 1, "missing->exact": 1},
          "local transition report retains row and field transitions")
    check(transition["by_type"]["1"]["after_mismatch_clusters"] ==
          {"pal": 1} and
          transition["by_type"]["5"]["after_mismatch_clusters"] ==
          {"(exact)": 1},
          "local transition report classifies remaining mismatches by type")

    before_score = json.loads(json.dumps(score_data))
    after_score = json.loads(json.dumps(score_data))
    before_score["reports"][0]["comparisons"] = {
        "surf": {"got": "BBBBBBBB", "expected": "AAAAAAAA",
                 "match": False},
        "pal": {"got": "CCCCCCCC", "expected": "CCCCCCCC",
                "match": True},
        "sect_def_hm": {"got": "11111111", "expected": "33333333",
                        "match": False},
    }
    after_score["reports"][0]["comparisons"]["sect_def_hm"] = {
        "got": "22222222", "expected": "33333333", "match": False}
    before_score["reports"][1]["comparisons"]["pal"] = {
        "got": None, "expected": "EEEEEEEE", "match": False}
    before_score["reports"][0].update({
        "lino_seedval": 0.0, "global_surface_seed": 0})
    after_score["reports"][0].update({
        "lino_seedval": 1.25, "global_surface_seed": 17})
    before_score["exact"] = 2
    after_score["exact"] = 3
    before_score["graded"] = 5
    after_score["graded"] = 5
    comparison = nivgen_score_compare.compare(
        before_score, after_score, "before-digest", "after-digest")
    check(comparison["comparisons"] == {
              "before_exact": 2, "after_exact": 3, "total": 5,
              "changed_values": 4, "repairs": 2, "regressions": 1,
              "different_wrong_values": 1},
          "score-to-score comparison measures repairs, regressions, and changed mismatches")
    check(comparison["rows"] == {
              "before_exact": 0, "after_exact": 1, "total": 2,
              "transitions": {"mismatch->exact": 1,
                              "mismatch->mismatch": 1}} and
          comparison["fields"]["surf"]["repairs"] == 1 and
          comparison["fields"]["pal"]["regressions"] == 1,
          "score-to-score comparison retains row and field transitions")
    check(comparison["diagnostics"] == {
              "lino_seedval_zero_before": 1,
              "lino_seedval_zero_after": 0,
              "metadata_changes": 2,
              "changed_value_rows": 2},
          "score-to-score comparison records zero-seed and metadata effects")

    invalid_before = json.loads(json.dumps(before_score))
    invalid_before["reports"][0]["comparisons"]["surf"]["match"] = True
    try:
        nivgen_score_compare.compare(invalid_before, after_score)
    except ValueError:
        rejected = True
    else:
        rejected = False
    check(rejected, "score-to-score comparison rejects invalid match flags")

    with tempfile.TemporaryDirectory(prefix="nivgen-comparison-transition-") as temp_name:
        transition_path = Path(temp_name) / "transition.json"
        transition_bytes = b'{"score_sha256":"bound-score"}\n'
        transition_path.write_bytes(transition_bytes)
        bound = nivgen_score_compare.transition_provenance(
            transition_path, "bound-score", "synthetic")
        try:
            nivgen_score_compare.transition_provenance(
                transition_path, "different-score", "synthetic")
        except ValueError:
            rejected = True
        else:
            rejected = False
    check(bound == {
              "path": transition_path.as_posix(),
              "bytes": len(transition_bytes),
              "sha256": hashlib.sha256(transition_bytes).hexdigest(),
              "score_sha256": "bound-score",
          } and rejected,
          "score comparison provenance hashes transitions and enforces score binding")

    with tempfile.TemporaryDirectory(prefix="nivgen-source-state-") as temp_name:
        source_state = Path(temp_name) / "dirty-source.patch"
        source_bytes = b"exact dirty source state\n"
        source_state.write_bytes(source_bytes)
        recorded = nivgen_score_transition.file_provenance(source_state)
        manifest = Path(temp_name) / "source-closure.sha256"
        with mock.patch.object(sys, "argv", [
                "nivgen_score_transition.py", "snapshot.json", "score.json",
                "--source-state", str(manifest),
                "--source-state", str(source_state),
        ]):
            transition_args = nivgen_score_transition.parse_args()
    check(recorded == {
              "path": source_state.as_posix(),
              "bytes": len(source_bytes),
              "sha256": hashlib.sha256(source_bytes).hexdigest(),
          },
          "local transition provenance hashes an exact dirty source artifact")
    check(transition_args.source_state == [manifest, source_state],
          "local transition provenance retains every source-state artifact")

    with tempfile.TemporaryDirectory(prefix="nivgen-transition-cli-") as temp_name:
        temp = Path(temp_name)
        snapshot_path = temp / "snapshot.json"
        score_path = temp / "score.json"
        executable_path = temp / "nivtest.exe"
        manifest_path = temp / "source-closure.sha256"
        patch_path = temp / "dirty-source.patch"
        output_path = temp / "transition.json"
        snapshot_path.write_text(json.dumps(snapshot_data), encoding="utf-8")
        score_path.write_text(json.dumps(score_data), encoding="utf-8")
        executable_path.write_bytes(b"exact executable")
        manifest_path.write_bytes(b"manifest\n")
        patch_path.write_bytes(b"patch\n")
        with (mock.patch.object(sys, "argv", [
                "nivgen_score_transition.py", str(snapshot_path),
                str(score_path), "--executable", str(executable_path),
                "--source-revision", "exact revision and dirty state",
                "--source-state", str(manifest_path),
                "--source-state", str(patch_path),
                "--json-out", str(output_path),
        ]), mock.patch("builtins.print")):
            transition_status = nivgen_score_transition.main()
        emitted_transition = json.loads(output_path.read_text(encoding="utf-8"))
    emitted_provenance = emitted_transition["provenance"]
    check(transition_status == 0 and
          emitted_provenance["source_revision"] ==
          "exact revision and dirty state" and
          emitted_provenance["executable"]["sha256"] ==
          hashlib.sha256(b"exact executable").hexdigest() and
          [item["sha256"] for item in emitted_provenance["source_state"]] == [
              hashlib.sha256(b"manifest\n").hexdigest(),
              hashlib.sha256(b"patch\n").hexdigest(),
          ],
          "transition CLI binds executable, revision, and every source artifact")

    bad_score = json.loads(json.dumps(score_data))
    bad_score["reports"][0]["comparisons"]["surf"]["expected"] = "00000000"
    try:
        nivgen_score_transition.compare(snapshot_data, bad_score)
    except ValueError:
        rejected = True
    else:
        rejected = False
    check(rejected,
          "local transition report rejects results from a different snapshot")

    duplicate_score = json.loads(json.dumps(score_data))
    duplicate_score["reports"][1]["key"] = "A|0"
    duplicate_score["reports"][1]["type"] = 1
    try:
        nivgen_score_transition.compare(snapshot_data, duplicate_score)
    except ValueError:
        rejected = True
    else:
        rejected = False
    check(rejected, "local transition report rejects duplicate score keys")

    print("NIVGEN scorer API: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
