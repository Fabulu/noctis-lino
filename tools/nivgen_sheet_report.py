#!/usr/bin/env python3
"""Snapshot and classify the complete public NIVGEN comparison sheet.

Live reads are sequential, rate-limited, and never retried. A canonical snapshot
can be retained and compared with a later snapshot without calling the service.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


API = "https://litterbox.moos.es/sheets/nivgen_planets"
SNAPSHOT_FORMAT = 1
IMPLEMENTATIONS = ("rust", "lr", "lino")
HASH_FIELDS = (
    "surf", "atmo", "pal", "sect_def_hm", "sect_def_oc",
    "sect_rand_hm", "sect_rand_oc", "sect_def_stex", "sect_def_sky",
    "sect_rand_stex", "sect_rand_sky",
)
IDENTITY_FIELDS = (
    "key", "star", "body", "type", "is_moon", "seedval", "rand_lon",
    "rand_lat", "updated_at",
)


def page_url(url: str, page: int, page_size: int) -> str:
    parsed = urllib.parse.urlsplit(url)
    query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    query.update(page=str(page), pageSize=str(page_size))
    return urllib.parse.urlunsplit(parsed._replace(
        query=urllib.parse.urlencode(query)))


def fetch_payload(url: str) -> dict[str, object]:
    request = urllib.request.Request(
        url, headers={"User-Agent": "noctis-lino-nivgen-audit/1"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError(
            f"NIVGEN sheet unavailable: {error}; not retrying") from error
    if not isinstance(payload, dict):
        raise ValueError("NIVGEN sheet response is not an object")
    return payload


def column_names(payload: dict[str, object]) -> list[str]:
    columns = payload.get("columns")
    if not isinstance(columns, list) or not columns:
        raise ValueError("NIVGEN sheet page has no columns")
    names = []
    for column in columns:
        if not isinstance(column, dict) or not isinstance(column.get("name"), str):
            raise ValueError("NIVGEN sheet has an invalid column descriptor")
        names.append(column["name"])
    if len(names) != len(set(names)):
        raise ValueError("NIVGEN sheet has duplicate column names")
    return names


def validate_required_columns(names: list[str]) -> None:
    required = set(IDENTITY_FIELDS)
    required.update(implementation + "_errors"
                    for implementation in IMPLEMENTATIONS)
    required.update("orig_" + field for field in HASH_FIELDS)
    required.update(
        implementation + "_" + field
        for implementation in IMPLEMENTATIONS for field in HASH_FIELDS
    )
    missing = sorted(required - set(names))
    if missing:
        raise ValueError(
            "NIVGEN sheet is missing required columns: " + ", ".join(missing))


def page_rows(payload: dict[str, object], names: list[str]) -> list[list[object]]:
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ValueError("NIVGEN sheet page has no row array")
    for index, row in enumerate(rows):
        if not isinstance(row, list) or len(row) != len(names):
            size = len(row) if isinstance(row, list) else "not-an-array"
            raise ValueError(
                f"NIVGEN sheet row {index} has {size} values; "
                f"expected {len(names)}")
    return rows


def fetch_live(url: str = API, page_size: int = 500,
               delay: float = 1.0) -> dict[str, object]:
    if page_size < 1 or page_size > 500:
        raise ValueError("page size must be between 1 and 500")
    if delay < 0:
        raise ValueError("request delay cannot be negative")

    payload = fetch_payload(page_url(url, 1, page_size))
    names = column_names(payload)
    validate_required_columns(names)
    total = int(payload.get("total", -1))
    effective_size = int(payload.get("pageSize", -1))
    first_page = int(payload.get("page", -1))
    if total < 0 or effective_size < 1 or first_page != 1:
        raise ValueError("NIVGEN sheet returned invalid first-page metadata")
    rows = list(page_rows(payload, names))
    pages = (total + effective_size - 1) // effective_size

    for page in range(2, pages + 1):
        if delay:
            time.sleep(delay)
        payload = fetch_payload(page_url(url, page, effective_size))
        if column_names(payload) != names:
            raise ValueError(f"NIVGEN sheet columns changed on page {page}")
        if (int(payload.get("page", -1)) != page or
                int(payload.get("pageSize", -1)) != effective_size or
                int(payload.get("total", -1)) != total):
            raise ValueError(
                f"NIVGEN sheet pagination changed while reading page {page}")
        rows.extend(page_rows(payload, names))

    snapshot = {
        "format": SNAPSHOT_FORMAT,
        "source": url,
        "pageSize": effective_size,
        "total": total,
        "columns": names,
        "rows": rows,
    }
    validate_snapshot(snapshot)
    return snapshot


def validate_snapshot(snapshot: dict[str, object]) -> None:
    if snapshot.get("format") != SNAPSHOT_FORMAT:
        raise ValueError(
            f"unsupported NIVGEN snapshot format {snapshot.get('format')!r}")
    names = snapshot.get("columns")
    if (not isinstance(names, list) or not names or
            not all(isinstance(name, str) for name in names)):
        raise ValueError("NIVGEN snapshot has invalid columns")
    if len(names) != len(set(names)):
        raise ValueError("NIVGEN snapshot has duplicate columns")
    validate_required_columns(names)
    rows = page_rows(snapshot, names)
    total = int(snapshot.get("total", -1))
    if total != len(rows):
        raise ValueError(
            f"NIVGEN snapshot claims {total} rows but contains {len(rows)}")
    key_index = names.index("key")
    keys = [row[key_index] for row in rows]
    if any(not isinstance(key, str) or not key for key in keys):
        raise ValueError("NIVGEN snapshot contains an invalid row key")
    if len(keys) != len(set(keys)):
        raise ValueError("NIVGEN snapshot contains duplicate row keys")


def canonical_bytes(snapshot: dict[str, object]) -> bytes:
    validate_snapshot(snapshot)
    return (json.dumps(snapshot, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode("utf-8")


def write_snapshot(path: Path, snapshot: dict[str, object]) -> str:
    data = canonical_bytes(snapshot)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def read_snapshot(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8-sig") as stream:
        snapshot = json.load(stream)
    if not isinstance(snapshot, dict):
        raise ValueError("NIVGEN snapshot is not an object")
    validate_snapshot(snapshot)
    return snapshot


def snapshot_hash(snapshot: dict[str, object]) -> str:
    return hashlib.sha256(canonical_bytes(snapshot)).hexdigest()


def mapped_rows(snapshot: dict[str, object]) -> list[dict[str, object]]:
    names = snapshot["columns"]
    return [dict(zip(names, row)) for row in snapshot["rows"]]


def field_state(row: dict[str, object], implementation: str,
                field: str) -> str:
    expected = row.get("orig_" + field)
    actual = row.get(implementation + "_" + field)
    if expected is None:
        return "unavailable"
    if actual is None:
        return "missing"
    if str(actual).upper() == str(expected).upper():
        return "exact"
    return "mismatch"


def row_state(row: dict[str, object], implementation: str) -> str:
    states = [field_state(row, implementation, field) for field in HASH_FIELDS]
    compared = [state for state in states if state != "unavailable"]
    if not compared:
        return "unavailable"
    if "missing" in compared:
        return "missing"
    if "mismatch" in compared:
        return "mismatch"
    return "exact"


def counts_record(counter: Counter[str], denominator: int) -> dict[str, object]:
    exact = counter["exact"]
    scored = denominator - counter["unavailable"]
    return {
        "exact": exact,
        "mismatch": counter["mismatch"],
        "missing": counter["missing"],
        "unavailable": counter["unavailable"],
        "scored": scored,
        "total": denominator,
        "exact_rate": exact / denominator if denominator else None,
        "exact_rate_scored": exact / scored if scored else None,
    }


def sheet_marker_record(rows: list[dict[str, object]],
                        implementation: str) -> dict[str, object]:
    field = implementation + "_errors"
    zero = [row for row in rows if row.get(field) == 0]
    missing = sum(row.get(field) is None for row in rows)
    return {
        "zero_errors": len(zero),
        "nonzero_errors": len(rows) - len(zero) - missing,
        "missing": missing,
        "total": len(rows),
        "zero_error_rate": len(zero) / len(rows) if rows else None,
        "zero_errors_hash_exact": sum(
            row_state(row, implementation) == "exact" for row in zero),
        "zero_errors_unavailable": sum(
            row_state(row, implementation) == "unavailable" for row in zero),
    }


def report(snapshot: dict[str, object]) -> dict[str, object]:
    validate_snapshot(snapshot)
    rows = mapped_rows(snapshot)
    result: dict[str, object] = {
        "format": 1,
        "snapshot_sha256": snapshot_hash(snapshot),
        "total_rows": len(rows),
        "implementations": {},
    }
    implementations = result["implementations"]
    assert isinstance(implementations, dict)
    for implementation in IMPLEMENTATIONS:
        row_counts = Counter(row_state(row, implementation) for row in rows)
        fields = {}
        for field in HASH_FIELDS:
            states = Counter(field_state(row, implementation, field)
                             for row in rows)
            fields[field] = counts_record(states, len(rows))
        by_type = {}
        for body_type in sorted({int(row["type"]) for row in rows}):
            selected = [row for row in rows if int(row["type"]) == body_type]
            states = Counter(row_state(row, implementation) for row in selected)
            by_type[str(body_type)] = counts_record(states, len(selected))
        by_moon = {}
        for moon_value, label in ((0, "planet"), (1, "moon")):
            selected = [row for row in rows
                        if int(row["is_moon"]) == moon_value]
            states = Counter(row_state(row, implementation) for row in selected)
            by_moon[label] = counts_record(states, len(selected))
        implementations[implementation] = {
            "sheet_zero_error_markers": sheet_marker_record(
                rows, implementation),
            "sheet_zero_error_markers_by_type": {
                body_type: sheet_marker_record(
                    [row for row in rows if int(row["type"]) == int(body_type)],
                    implementation)
                for body_type in by_type
            },
            "sheet_zero_error_markers_by_moon": {
                label: sheet_marker_record(
                    [row for row in rows
                     if int(row["is_moon"]) == (1 if label == "moon" else 0)],
                    implementation)
                for label in by_moon
            },
            "rows": counts_record(row_counts, len(rows)),
            "fields": fields,
            "by_type": by_type,
            "by_moon": by_moon,
        }
    return result


def compare_snapshots(old: dict[str, object],
                      new: dict[str, object]) -> dict[str, object]:
    old_rows = {str(row["key"]): row for row in mapped_rows(old)}
    new_rows = {str(row["key"]): row for row in mapped_rows(new)}
    common = sorted(set(old_rows) & set(new_rows))
    result: dict[str, object] = {
        "old_snapshot_sha256": snapshot_hash(old),
        "new_snapshot_sha256": snapshot_hash(new),
        "common_rows": len(common),
        "added_rows": sorted(set(new_rows) - set(old_rows)),
        "removed_rows": sorted(set(old_rows) - set(new_rows)),
        "implementations": {},
    }
    implementations = result["implementations"]
    assert isinstance(implementations, dict)
    for implementation in IMPLEMENTATIONS:
        row_transitions = Counter()
        field_transitions = {field: Counter() for field in HASH_FIELDS}
        for key in common:
            before = old_rows[key]
            after = new_rows[key]
            row_transitions[
                f"{row_state(before, implementation)}->"
                f"{row_state(after, implementation)}"] += 1
            for field in HASH_FIELDS:
                field_transitions[field][
                    f"{field_state(before, implementation, field)}->"
                    f"{field_state(after, implementation, field)}"] += 1
        implementations[implementation] = {
            "rows": dict(sorted(row_transitions.items())),
            "fields": {
                field: dict(sorted(transitions.items()))
                for field, transitions in field_transitions.items()
            },
        }
    return result


def percentage(record: dict[str, object]) -> str:
    rate = record["exact_rate"]
    return "n/a" if rate is None else f"{float(rate) * 100:.1f}%"


def print_report(result: dict[str, object], show: str) -> None:
    print(f"NIVGEN snapshot {result['snapshot_sha256']}")
    print(f"rows: {result['total_rows']}")
    implementations = result["implementations"]
    for implementation in IMPLEMENTATIONS:
        item = implementations[implementation]
        rows = item["rows"]
        markers = item["sheet_zero_error_markers"]
        marker_rate = markers["zero_error_rate"]
        marker_rate_text = (
            "n/a" if marker_rate is None else f"{float(marker_rate) * 100:.1f}%")
        scored_rate = rows["exact_rate_scored"]
        scored_rate_text = (
            "n/a" if scored_rate is None else f"{float(scored_rate) * 100:.1f}%")
        print(
            f"  {implementation}: sheet zero-error markers "
            f"{markers['zero_errors']}/{markers['total']} "
            f"({marker_rate_text}); independently hash-exact "
            f"{rows['exact']}/{rows['scored']} comparable "
            f"({scored_rate_text}); "
            f"unavailable={rows['unavailable']}, missing={rows['missing']}")
    selected = implementations[show]
    print(f"{show} fields:")
    for field in HASH_FIELDS:
        item = selected["fields"][field]
        rate = item["exact_rate_scored"]
        rate_text = "n/a" if rate is None else f"{float(rate) * 100:.1f}%"
        print(
            f"  {field}: {item['exact']}/{item['scored']} "
            f"({rate_text}), mismatch={item['mismatch']}, "
            f"missing={item['missing']}")
    print(f"{show} rows by type (sheet marker; independent comparable hashes):")
    marker_types = selected["sheet_zero_error_markers_by_type"]
    for body_type, item in selected["by_type"].items():
        marker = marker_types[body_type]
        rate = item["exact_rate_scored"]
        rate_text = "n/a" if rate is None else f"{float(rate) * 100:.1f}%"
        print(
            f"  type {body_type}: marker {marker['zero_errors']}/"
            f"{marker['total']}; hash-exact {item['exact']}/{item['scored']} "
            f"({rate_text})")
    marker_moon = selected["sheet_zero_error_markers_by_moon"]
    for label, item in selected["by_moon"].items():
        marker = marker_moon[label]
        rate = item["exact_rate_scored"]
        rate_text = "n/a" if rate is None else f"{float(rate) * 100:.1f}%"
        print(
            f"  {label}: marker {marker['zero_errors']}/{marker['total']}; "
            f"hash-exact {item['exact']}/{item['scored']} ({rate_text})")


def print_comparison(comparison: dict[str, object], show: str) -> None:
    print(
        f"comparison: {comparison['common_rows']} common, "
        f"{len(comparison['added_rows'])} added, "
        f"{len(comparison['removed_rows'])} removed")
    transitions = comparison["implementations"][show]["rows"]
    for name, count in transitions.items():
        if name.split("->", 1)[0] != name.split("->", 1)[1]:
            print(f"  {show} rows {name}: {count}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Snapshot and classify every public NIVGEN sheet row")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--live", action="store_true",
                        help="read every public API page once")
    source.add_argument("--snapshot", type=Path,
                        help="read a canonical snapshot without network access")
    parser.add_argument("--url", default=API)
    parser.add_argument("--page-size", type=int, default=500)
    parser.add_argument("--delay", type=float, default=1.0,
                        help="seconds between sequential page requests")
    parser.add_argument("--snapshot-out", type=Path,
                        help="write the canonical live snapshot")
    parser.add_argument("--compare", type=Path,
                        help="compare against an older canonical snapshot")
    parser.add_argument("--json-out", type=Path,
                        help="write the complete aggregate report and diff")
    parser.add_argument("--show", choices=IMPLEMENTATIONS, default="lino")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        snapshot = (fetch_live(args.url, args.page_size, args.delay)
                    if args.live else read_snapshot(args.snapshot))
        if args.snapshot_out:
            if not args.live:
                raise ValueError("--snapshot-out is only valid with --live")
            digest = write_snapshot(args.snapshot_out, snapshot)
            print(f"wrote {args.snapshot_out} sha256={digest}")
        result = report(snapshot)
        print_report(result, args.show)
        comparison = None
        if args.compare:
            comparison = compare_snapshots(read_snapshot(args.compare), snapshot)
            print_comparison(comparison, args.show)
        if args.json_out:
            output = {"report": result}
            if comparison is not None:
                output["comparison"] = comparison
            args.json_out.parent.mkdir(parents=True, exist_ok=True)
            args.json_out.write_text(
                json.dumps(output, indent=2, sort_keys=True) + "\n",
                encoding="utf-8", newline="\n")
    except (OSError, RuntimeError, ValueError) as error:
        print(f"nivgen_sheet_report: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
