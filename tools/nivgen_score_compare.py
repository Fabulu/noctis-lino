#!/usr/bin/env python3
"""Compare two local NIVGEN score artifacts over the same selected corpus."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import nivgen_score_transition as transition


FIELDS = transition.FIELDS
REPORT_METADATA = ("reported_type", "lino_seedval", "global_surface_seed")
REPORT_IDENTITY = ("type", "coords", "body", "random_site", "sheet_seedval")


def same_value(left: object, right: object) -> bool:
    if left is None or right is None:
        return left is right
    return transition.same_hash(left, right)


def sorted_counter(counter: Counter[str]) -> dict[str, int]:
    return dict(sorted(counter.items()))


def mapped_reports(score: dict[str, object], label: str) -> tuple[list[str], dict[str, dict[str, object]]]:
    reports = score.get("reports")
    if not isinstance(reports, list):
        raise ValueError(f"{label} score must contain a reports array")
    order = []
    mapped = {}
    for index, report in enumerate(reports):
        if not isinstance(report, dict):
            raise ValueError(f"{label} score report {index} is not an object")
        key = report.get("key")
        if not isinstance(key, str) or not key:
            raise ValueError(f"{label} score report {index} has an invalid key")
        if key in mapped:
            raise ValueError(f"{label} score contains duplicate key {key}")
        order.append(key)
        mapped[key] = report
    return order, mapped


def validated_comparisons(report: dict[str, object], label: str) -> dict[str, dict[str, object]]:
    key = report["key"]
    items = report.get("comparisons")
    if not isinstance(items, dict) or not items:
        raise ValueError(f"{label} score report {key} has no comparisons")
    unknown = sorted(set(items) - set(FIELDS))
    if unknown:
        raise ValueError(
            f"{label} score report {key} has unknown fields: " + ", ".join(unknown))
    result = {}
    for field, item in items.items():
        if not isinstance(item, dict):
            raise ValueError(f"{label} comparison {key}/{field} is not an object")
        expected = item.get("expected")
        got = item.get("got")
        claimed = item.get("match")
        exact = expected is not None and got is not None and same_value(expected, got)
        if not isinstance(claimed, bool) or claimed != exact:
            raise ValueError(f"{label} score match flag is invalid for {key}/{field}")
        result[field] = item
    return result


def compare(before_score: dict[str, object], after_score: dict[str, object],
            before_sha256: str | None = None,
            after_sha256: str | None = None) -> dict[str, object]:
    order, before_reports = mapped_reports(before_score, "before")
    after_order, after_reports = mapped_reports(after_score, "after")
    if set(order) != set(after_order):
        missing = sorted(set(order) - set(after_order))
        added = sorted(set(after_order) - set(order))
        raise ValueError(f"score selections differ: missing={missing[:3]} added={added[:3]}")

    field_transitions = {field: Counter() for field in FIELDS}
    field_changes = Counter()
    field_repairs = Counter()
    field_regressions = Counter()
    row_transitions = Counter()
    type_rows: dict[int, Counter[str]] = {}
    changed_values = []
    metadata_changes = []
    fields_seen = set()
    before_exact = after_exact = comparisons = 0
    before_rows_exact = after_rows_exact = 0
    zero_seed_before = zero_seed_after = 0
    different_wrong_values = 0

    for key in order:
        before = before_reports[key]
        after = after_reports[key]
        for name in REPORT_IDENTITY:
            if before.get(name) != after.get(name):
                raise ValueError(f"score identity differs for {key}/{name}")
        body_type = int(before["type"])

        before_items = validated_comparisons(before, "before")
        after_items = validated_comparisons(after, "after")
        if set(before_items) != set(after_items):
            raise ValueError(f"score comparison fields differ for {key}")

        before_row_states = []
        after_row_states = []
        for field in FIELDS:
            if field not in before_items:
                continue
            fields_seen.add(field)
            before_item = before_items[field]
            after_item = after_items[field]
            if not same_value(before_item.get("expected"), after_item.get("expected")):
                raise ValueError(f"score expected hashes differ for {key}/{field}")
            before_state = "exact" if before_item["match"] else "mismatch"
            after_state = "exact" if after_item["match"] else "mismatch"
            state_transition = f"{before_state}->{after_state}"
            changed = not same_value(before_item.get("got"), after_item.get("got"))

            comparisons += 1
            before_exact += before_state == "exact"
            after_exact += after_state == "exact"
            before_row_states.append(before_state)
            after_row_states.append(after_state)
            field_transitions[field][state_transition] += 1
            field_changes[field] += changed
            field_repairs[field] += state_transition == "mismatch->exact"
            field_regressions[field] += state_transition == "exact->mismatch"
            different_wrong_values += changed and state_transition == "mismatch->mismatch"
            if changed:
                changed_values.append({
                    "key": key,
                    "type": body_type,
                    "field": field,
                    "before": before_item.get("got"),
                    "after": after_item.get("got"),
                    "expected": after_item.get("expected"),
                    "transition": state_transition,
                })

        before_row = "exact" if all(state == "exact" for state in before_row_states) else "mismatch"
        after_row = "exact" if all(state == "exact" for state in after_row_states) else "mismatch"
        row_transition = f"{before_row}->{after_row}"
        row_transitions[row_transition] += 1
        type_rows.setdefault(body_type, Counter())[row_transition] += 1
        before_rows_exact += before_row == "exact"
        after_rows_exact += after_row == "exact"

        for name in REPORT_METADATA:
            before_value = before.get(name)
            after_value = after.get(name)
            if before_value != after_value:
                metadata_changes.append({
                    "key": key,
                    "type": body_type,
                    "field": name,
                    "before": before_value,
                    "after": after_value,
                })
        zero_seed_before += float(before.get("lino_seedval", 1.0)) == 0.0
        zero_seed_after += float(after.get("lino_seedval", 1.0)) == 0.0

    if int(before_score.get("graded", comparisons)) != comparisons:
        raise ValueError("before score graded total disagrees with its comparisons")
    if int(after_score.get("graded", comparisons)) != comparisons:
        raise ValueError("after score graded total disagrees with its comparisons")
    if int(before_score.get("exact", before_exact)) != before_exact:
        raise ValueError("before score exact total disagrees with its comparisons")
    if int(after_score.get("exact", after_exact)) != after_exact:
        raise ValueError("after score exact total disagrees with its comparisons")

    fields = {}
    for field in FIELDS:
        if field not in fields_seen:
            continue
        fields[field] = {
            "before_exact": sum(count for name, count in field_transitions[field].items()
                                if name.startswith("exact->")),
            "after_exact": sum(count for name, count in field_transitions[field].items()
                               if name.endswith("->exact")),
            "total": sum(field_transitions[field].values()),
            "changed_values": field_changes[field],
            "repairs": field_repairs[field],
            "regressions": field_regressions[field],
            "transitions": sorted_counter(field_transitions[field]),
        }

    return {
        "format": 1,
        "before_score_sha256": before_sha256,
        "after_score_sha256": after_sha256,
        "selection": {
            "rows": len(order),
            "types": sorted(type_rows),
            "fields": [field for field in FIELDS if field in fields_seen],
        },
        "comparisons": {
            "before_exact": before_exact,
            "after_exact": after_exact,
            "total": comparisons,
            "changed_values": len(changed_values),
            "repairs": sum(field_repairs.values()),
            "regressions": sum(field_regressions.values()),
            "different_wrong_values": different_wrong_values,
        },
        "rows": {
            "before_exact": before_rows_exact,
            "after_exact": after_rows_exact,
            "total": len(order),
            "transitions": sorted_counter(row_transitions),
        },
        "diagnostics": {
            "lino_seedval_zero_before": zero_seed_before,
            "lino_seedval_zero_after": zero_seed_after,
            "metadata_changes": len(metadata_changes),
            "changed_value_rows": len({item["key"] for item in changed_values}),
        },
        "fields": fields,
        "by_type": {
            str(body_type): {"rows": sorted_counter(type_rows[body_type])}
            for body_type in sorted(type_rows)
        },
        "changed_values": changed_values,
        "metadata_changes": metadata_changes,
    }


def read_json(path: Path) -> tuple[dict[str, object], str]:
    data = path.read_bytes()
    value = json.loads(data.decode("utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not a JSON object")
    return value, hashlib.sha256(data).hexdigest()


def transition_provenance(path: Path, score_sha256: str, label: str) -> dict[str, object]:
    value, _ = read_json(path)
    if value.get("score_sha256") != score_sha256:
        raise ValueError(f"{label} transition is bound to a different score")
    result = transition.file_provenance(path)
    result["score_sha256"] = score_sha256
    return result


def print_report(result: dict[str, object]) -> None:
    selection = result["selection"]
    comparisons = result["comparisons"]
    rows = result["rows"]
    diagnostics = result["diagnostics"]
    print(f"NIVGEN score comparison before={result['before_score_sha256']} "
          f"after={result['after_score_sha256']}")
    print(f"rows={selection['rows']} types={selection['types']} fields={len(selection['fields'])}")
    print(f"comparisons exact {comparisons['before_exact']}/{comparisons['total']} -> "
          f"{comparisons['after_exact']}/{comparisons['total']}; "
          f"changed={comparisons['changed_values']} repairs={comparisons['repairs']} "
          f"regressions={comparisons['regressions']} "
          f"different-wrong={comparisons['different_wrong_values']}")
    print(f"rows exact {rows['before_exact']}/{rows['total']} -> "
          f"{rows['after_exact']}/{rows['total']}")
    print(f"zero seedval {diagnostics['lino_seedval_zero_before']} -> "
          f"{diagnostics['lino_seedval_zero_after']}; "
          f"metadata changes={diagnostics['metadata_changes']}")
    for field, item in result["fields"].items():
        print(f"  {field}: {item['before_exact']}/{item['total']} -> "
              f"{item['after_exact']}/{item['total']}; changed={item['changed_values']} "
              f"repairs={item['repairs']} regressions={item['regressions']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare two local NIVGEN score artifacts")
    parser.add_argument("before_score", type=Path)
    parser.add_argument("after_score", type=Path)
    parser.add_argument("--before-transition", type=Path)
    parser.add_argument("--after-transition", type=Path)
    parser.add_argument("--json-out", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        before, before_digest = read_json(args.before_score)
        after, after_digest = read_json(args.after_score)
        result = compare(before, after, before_digest, after_digest)
        provenance = {}
        if args.before_transition:
            provenance["before_transition"] = transition_provenance(
                args.before_transition, before_digest, "before")
        if args.after_transition:
            provenance["after_transition"] = transition_provenance(
                args.after_transition, after_digest, "after")
        if provenance:
            result["provenance"] = provenance
        print_report(result)
        if args.json_out:
            args.json_out.write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n",
                encoding="utf-8", newline="\n")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        print(f"nivgen_score_compare: {error}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
