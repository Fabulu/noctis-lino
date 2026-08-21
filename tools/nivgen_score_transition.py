#!/usr/bin/env python3
"""Compare a local NIVGEN score with the Lino values in its source snapshot."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


FIELDS = (
    "surf", "atmo", "pal", "sect_def_hm", "sect_def_oc",
    "sect_def_stex", "sect_def_sky", "sect_rand_hm", "sect_rand_oc",
    "sect_rand_stex", "sect_rand_sky",
)


def same_hash(left: object, right: object) -> bool:
    return str(left).upper() == str(right).upper()


def field_state(expected: object, actual: object) -> str:
    if expected is None:
        return "unavailable"
    if actual is None:
        return "missing"
    return "exact" if same_hash(expected, actual) else "mismatch"


def row_state(states: list[str]) -> str:
    if not states:
        return "unavailable"
    if "missing" in states:
        return "missing"
    if "mismatch" in states:
        return "mismatch"
    return "exact"


def mapped_snapshot(snapshot: dict[str, object]) -> dict[str, dict[str, object]]:
    columns = snapshot.get("columns")
    values = snapshot.get("rows")
    if not isinstance(columns, list) or not isinstance(values, list):
        raise ValueError("snapshot must contain columns and rows arrays")
    names = [column if isinstance(column, str) else column.get("name")
             if isinstance(column, dict) else None for column in columns]
    if not names or any(not isinstance(name, str) for name in names):
        raise ValueError("snapshot contains an invalid column descriptor")
    if len(names) != len(set(names)):
        raise ValueError("snapshot contains duplicate columns")
    required = {"key", "type"}
    required.update("orig_" + field for field in FIELDS)
    required.update("lino_" + field for field in FIELDS)
    missing = sorted(required - set(names))
    if missing:
        raise ValueError("snapshot is missing columns: " + ", ".join(missing))

    mapped = {}
    for index, values_row in enumerate(values):
        if not isinstance(values_row, list) or len(values_row) != len(names):
            raise ValueError(f"snapshot row {index} has the wrong width")
        row = dict(zip(names, values_row))
        key = row.get("key")
        if not isinstance(key, str) or not key:
            raise ValueError(f"snapshot row {index} has an invalid key")
        if key in mapped:
            raise ValueError(f"snapshot contains duplicate key {key}")
        mapped[key] = row
    return mapped


def sorted_counter(counter: Counter[str]) -> dict[str, int]:
    return dict(sorted(counter.items()))


def compare(snapshot: dict[str, object], score: dict[str, object],
            snapshot_sha256: str | None = None,
            score_sha256: str | None = None) -> dict[str, object]:
    source_rows = mapped_snapshot(snapshot)
    reports = score.get("reports")
    if not isinstance(reports, list):
        raise ValueError("score must contain a reports array")

    seen = set()
    fields_seen = set()
    types_seen = set()
    field_transitions = {field: Counter() for field in FIELDS}
    field_values = {field: Counter() for field in FIELDS}
    row_transitions = Counter()
    type_rows: dict[int, Counter[str]] = {}
    mismatch_clusters: dict[int, Counter[str]] = {}
    before_exact = after_exact = comparisons = changed = 0
    reported_type_compared = reported_type_exact = 0
    seedval_compared = seedval_published_exact = seedval_zero = 0

    for index, report in enumerate(reports):
        if not isinstance(report, dict):
            raise ValueError(f"score report {index} is not an object")
        key = report.get("key")
        if not isinstance(key, str) or key not in source_rows:
            raise ValueError(f"score report {index} has unknown key {key!r}")
        if key in seen:
            raise ValueError(f"score contains duplicate key {key}")
        seen.add(key)
        source = source_rows[key]
        body_type = int(source["type"])
        if int(report.get("type", -1)) != body_type:
            raise ValueError(f"score type disagrees with snapshot for {key}")
        types_seen.add(body_type)

        reported_type = report.get("reported_type")
        if reported_type is not None:
            reported_type_compared += 1
            reported_type_exact += int(reported_type) == body_type
        sheet_seedval = report.get("sheet_seedval")
        lino_seedval = report.get("lino_seedval")
        if sheet_seedval is not None and lino_seedval is not None:
            sheet_value = float(sheet_seedval)
            lino_value = float(lino_seedval)
            seedval_compared += 1
            seedval_published_exact += (
                f"{sheet_value:.6f}" == f"{lino_value:.6f}")
            seedval_zero += lino_value == 0.0

        items = report.get("comparisons")
        if not isinstance(items, dict) or not items:
            raise ValueError(f"score report {key} has no comparisons")
        unknown = sorted(set(items) - set(FIELDS))
        if unknown:
            raise ValueError(
                f"score report {key} has unknown fields: " + ", ".join(unknown))

        before_states = []
        after_states = []
        mismatches = []
        for field in FIELDS:
            if field not in items:
                continue
            item = items[field]
            if not isinstance(item, dict):
                raise ValueError(f"score comparison {key}/{field} is not an object")
            expected = source.get("orig_" + field)
            if expected is None or not same_hash(expected, item.get("expected")):
                raise ValueError(
                    f"score expected hash disagrees with snapshot for {key}/{field}")
            got = item.get("got")
            after = field_state(expected, got)
            claimed = item.get("match")
            if not isinstance(claimed, bool) or claimed != (after == "exact"):
                raise ValueError(f"score match flag is invalid for {key}/{field}")
            before_got = source.get("lino_" + field)
            before = field_state(expected, before_got)
            value_change = "unchanged" if (
                (before_got is None and got is None) or
                (before_got is not None and got is not None and
                 same_hash(before_got, got))) else "changed"

            fields_seen.add(field)
            comparisons += 1
            before_exact += before == "exact"
            after_exact += after == "exact"
            changed += value_change == "changed"
            before_states.append(before)
            after_states.append(after)
            if after != "exact":
                mismatches.append(field)
            field_transitions[field][f"{before}->{after}"] += 1
            field_values[field][value_change] += 1

        before_row = row_state(before_states)
        after_row = row_state(after_states)
        transition = f"{before_row}->{after_row}"
        row_transitions[transition] += 1
        type_rows.setdefault(body_type, Counter())[transition] += 1
        cluster = ",".join(mismatches) if mismatches else "(exact)"
        mismatch_clusters.setdefault(body_type, Counter())[cluster] += 1

    if int(score.get("graded", comparisons)) != comparisons:
        raise ValueError("score graded total disagrees with its comparisons")
    if int(score.get("exact", after_exact)) != after_exact:
        raise ValueError("score exact total disagrees with its comparisons")

    fields = {}
    for field in FIELDS:
        if field not in fields_seen:
            continue
        transitions = field_transitions[field]
        total = sum(transitions.values())
        fields[field] = {
            "before_exact": sum(count for name, count in transitions.items()
                                if name.startswith("exact->")),
            "after_exact": sum(count for name, count in transitions.items()
                               if name.endswith("->exact")),
            "total": total,
            "values": sorted_counter(field_values[field]),
            "transitions": sorted_counter(transitions),
        }

    before_rows_exact = sum(count for name, count in row_transitions.items()
                            if name.startswith("exact->"))
    after_rows_exact = sum(count for name, count in row_transitions.items()
                           if name.endswith("->exact"))
    result: dict[str, object] = {
        "format": 1,
        "snapshot_sha256": snapshot_sha256,
        "score_sha256": score_sha256,
        "selection": {
            "rows": len(reports),
            "types": sorted(types_seen),
            "fields": [field for field in FIELDS if field in fields_seen],
        },
        "comparisons": {
            "before_exact": before_exact,
            "after_exact": after_exact,
            "total": comparisons,
            "changed_values": changed,
        },
        "diagnostics": {
            "reported_type_exact": reported_type_exact,
            "reported_type_compared": reported_type_compared,
            "seedval_published_6dp_exact": seedval_published_exact,
            "seedval_compared": seedval_compared,
            "lino_seedval_zero": seedval_zero,
        },
        "rows": {
            "before_exact": before_rows_exact,
            "after_exact": after_rows_exact,
            "total": len(reports),
            "transitions": sorted_counter(row_transitions),
        },
        "fields": fields,
        "by_type": {
            str(body_type): {
                "rows": sorted_counter(type_rows[body_type]),
                "after_mismatch_clusters": sorted_counter(
                    mismatch_clusters[body_type]),
            }
            for body_type in sorted(types_seen)
        },
    }
    return result


def file_provenance(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {
        "path": path.as_posix(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def read_json(path: Path) -> tuple[dict[str, object], str]:
    data = path.read_bytes()
    value = json.loads(data.decode("utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not a JSON object")
    return value, hashlib.sha256(data).hexdigest()


def print_report(result: dict[str, object]) -> None:
    selection = result["selection"]
    comparisons = result["comparisons"]
    rows = result["rows"]
    print(f"NIVGEN local transition snapshot={result['snapshot_sha256']} "
          f"score={result['score_sha256']}")
    provenance = result.get("provenance", {})
    if provenance:
        executable = provenance.get("executable")
        if executable:
            print(f"executable={executable['sha256']} ({executable['bytes']} bytes)")
        if provenance.get("source_revision"):
            print(f"source={provenance['source_revision']}")
        for source_state in provenance.get("source_state", []):
            print(f"source-state={source_state['sha256']} "
                  f"({source_state['bytes']} bytes; {source_state['path']})")
    print(f"rows={selection['rows']} types={selection['types']} "
          f"fields={len(selection['fields'])}")
    print(f"comparisons exact {comparisons['before_exact']}/"
          f"{comparisons['total']} -> {comparisons['after_exact']}/"
          f"{comparisons['total']}; changed values={comparisons['changed_values']}")
    print(f"rows exact {rows['before_exact']}/{rows['total']} -> "
          f"{rows['after_exact']}/{rows['total']}")
    diagnostics = result["diagnostics"]
    if diagnostics["reported_type_compared"]:
        print(f"reported type {diagnostics['reported_type_exact']}/"
              f"{diagnostics['reported_type_compared']}; seedval at published "
              f"6dp {diagnostics['seedval_published_6dp_exact']}/"
              f"{diagnostics['seedval_compared']}; "
              f"zero seedval={diagnostics['lino_seedval_zero']}")
    for field, item in result["fields"].items():
        print(f"  {field}: {item['before_exact']}/{item['total']} -> "
              f"{item['after_exact']}/{item['total']}")
    for body_type, item in result["by_type"].items():
        clusters = "; ".join(
            f"{name}={count}"
            for name, count in item["after_mismatch_clusters"].items())
        print(f"  type {body_type} after clusters: {clusters}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare local NIVGEN results with snapshot Lino hashes")
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("score", type=Path)
    parser.add_argument("--executable", type=Path,
                        help="record the exact locally scored executable")
    parser.add_argument("--source-revision",
                        help="record the named source revision or dirty state")
    parser.add_argument(
        "--source-state", action="append", default=[], type=Path,
        help="record an exact source-state manifest or patch (repeatable)")
    parser.add_argument("--json-out", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        snapshot, snapshot_digest = read_json(args.snapshot)
        score, score_digest = read_json(args.score)
        result = compare(snapshot, score, snapshot_digest, score_digest)
        provenance = {}
        if args.source_revision:
            provenance["source_revision"] = args.source_revision
        if args.executable:
            provenance["executable"] = file_provenance(args.executable)
        if args.source_state:
            provenance["source_state"] = [
                file_provenance(path) for path in args.source_state
            ]
        if provenance:
            result["provenance"] = provenance
        print_report(result)
        if args.json_out:
            args.json_out.write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n",
                encoding="utf-8", newline="\n")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        print(f"nivgen_score_transition: {error}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
