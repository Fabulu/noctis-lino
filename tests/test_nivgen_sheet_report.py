"""Focused checks for complete NIVGEN sheet snapshots and classification."""

from __future__ import annotations

import copy
from contextlib import redirect_stdout
import io
from pathlib import Path
import sys
import tempfile
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import nivgen_sheet_report as sheet  # noqa: E402


def check(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"PASS {label}")


def columns() -> list[str]:
    names = list(sheet.IDENTITY_FIELDS)
    names.extend(implementation + "_errors"
                 for implementation in sheet.IMPLEMENTATIONS)
    names.extend("orig_" + field for field in sheet.HASH_FIELDS)
    names.extend(
        implementation + "_" + field
        for implementation in sheet.IMPLEMENTATIONS
        for field in sheet.HASH_FIELDS
    )
    return names


def row(names: list[str], key: str, body_type: int, moon: int) -> list[object]:
    values: dict[str, object] = {
        "key": key,
        "star": key.split("|", 1)[0],
        "body": int(key.rsplit("|", 1)[1]),
        "type": body_type,
        "is_moon": moon,
        "seedval": -1.25,
        "rand_lon": 12,
        "rand_lat": -34,
        "updated_at": "2026-08-20T00:00:00Z",
        "rust_errors": 0,
        "lr_errors": 0,
        "lino_errors": 0,
    }
    for index, field in enumerate(sheet.HASH_FIELDS):
        expected = f"{index + 1:08X}"
        values["orig_" + field] = expected
        for implementation in sheet.IMPLEMENTATIONS:
            values[implementation + "_" + field] = expected
    return [values[name] for name in names]


def fixture() -> dict[str, object]:
    names = columns()
    exact = row(names, "ALPHA|0", 1, 0)
    broken = row(names, "BETA|1", 7, 1)
    broken[names.index("lino_errors")] = 2
    broken[names.index("lino_surf")] = "DEADBEEF"
    broken[names.index("lino_atmo")] = None
    unavailable = row(names, "GAMMA|2", 7, 1)
    for field in sheet.HASH_FIELDS:
        unavailable[names.index("orig_" + field)] = None
        for implementation in sheet.IMPLEMENTATIONS:
            unavailable[names.index(implementation + "_" + field)] = None
    return {
        "format": sheet.SNAPSHOT_FORMAT,
        "source": "fixture",
        "pageSize": 2,
        "total": 3,
        "columns": names,
        "rows": [exact, broken, unavailable],
    }


def payload(snapshot: dict[str, object], page: int,
            rows: list[list[object]]) -> dict[str, object]:
    return {
        "columns": [{"name": name} for name in snapshot["columns"]],
        "rows": rows,
        "total": snapshot["total"],
        "page": page,
        "pageSize": 2,
    }


def main() -> int:
    snapshot = fixture()
    sheet.validate_snapshot(snapshot)
    result = sheet.report(snapshot)
    lino = result["implementations"]["lino"]
    rust = result["implementations"]["rust"]

    check(lino["rows"] == {
        "exact": 1, "mismatch": 0, "missing": 1,
        "unavailable": 1, "scored": 2, "total": 3,
        "exact_rate": 1 / 3, "exact_rate_scored": 1 / 2,
    }, "row exactness distinguishes missing and unavailable Lino results")
    check(lino["sheet_zero_error_markers"] == {
        "zero_errors": 2, "nonzero_errors": 1, "missing": 0, "total": 3,
        "zero_error_rate": 2 / 3, "zero_errors_hash_exact": 1,
        "zero_errors_unavailable": 1,
    }, "sheet checkmarks distinguish hash-exact from unbackfilled rows")
    check(rust["rows"]["exact"] == 2 and
          rust["rows"]["unavailable"] == 1,
          "each implementation is classified independently")
    check(lino["fields"]["surf"]["exact"] == 1 and
          lino["fields"]["surf"]["mismatch"] == 1 and
          lino["fields"]["surf"]["scored"] == 2,
          "field counts use every authoritative expected hash")
    check(lino["fields"]["atmo"]["missing"] == 1,
          "a missing implementation hash is not treated as an unavailable field")
    check(lino["by_type"]["1"]["exact"] == 1 and
          lino["by_type"]["7"]["total"] == 2,
          "row exactness is classified by body type")
    check(lino["by_moon"]["planet"]["exact"] == 1 and
          lino["by_moon"]["moon"]["total"] == 2,
          "row exactness is classified by planet/moon status")

    unavailable_only = copy.deepcopy(snapshot)
    unavailable_only["rows"] = [unavailable_only["rows"][2]]
    unavailable_only["total"] = 1
    unavailable_only["pageSize"] = 1
    unavailable_report = sheet.report(unavailable_only)
    output = io.StringIO()
    with redirect_stdout(output):
        sheet.print_report(unavailable_report, "lino")
    check("0/0 comparable (n/a)" in output.getvalue(),
          "text reports handle a corpus with no authoritative hashes")

    with tempfile.TemporaryDirectory(prefix="nivgen-sheet-test-") as directory:
        path = Path(directory) / "snapshot.json"
        digest = sheet.write_snapshot(path, snapshot)
        loaded = sheet.read_snapshot(path)
        check(loaded == snapshot and digest == sheet.snapshot_hash(snapshot),
              "canonical snapshots round-trip with a stable SHA-256")

    changed = copy.deepcopy(snapshot)
    names = changed["columns"]
    rows = changed["rows"]
    rows[1][names.index("lino_surf")] = rows[1][names.index("orig_surf")]
    rows[1][names.index("lino_atmo")] = rows[1][names.index("orig_atmo")]
    rows[0][names.index("lino_pal")] = "BAD0C0DE"
    comparison = sheet.compare_snapshots(snapshot, changed)
    transitions = comparison["implementations"]["lino"]["rows"]
    check(transitions["missing->exact"] == 1 and
          transitions["exact->mismatch"] == 1,
          "snapshot comparison exposes row improvements and regressions")
    check(comparison["implementations"]["lino"]["fields"]["surf"]
          ["mismatch->exact"] == 1,
          "snapshot comparison exposes field-level transitions")

    page_one = payload(snapshot, 1, snapshot["rows"][:2])
    page_two = payload(snapshot, 2, snapshot["rows"][2:])
    with (mock.patch.object(sheet, "fetch_payload",
                            side_effect=[page_one, page_two]) as fetch,
          mock.patch.object(sheet.time, "sleep") as sleep):
        fetched = sheet.fetch_live("https://example.invalid/sheet", 2, 0.75)
    check(fetched["rows"] == snapshot["rows"] and fetch.call_count == 2,
          "live fetch reads every page exactly once in sequence")
    check("page=1" in fetch.call_args_list[0].args[0] and
          "page=2" in fetch.call_args_list[1].args[0],
          "live fetch requests explicit ordered page numbers")
    sleep.assert_called_once_with(0.75)
    check(True, "live fetch waits between pages and never uses a retry loop")

    duplicate = copy.deepcopy(snapshot)
    duplicate["rows"][1][duplicate["columns"].index("key")] = "ALPHA|0"
    try:
        sheet.validate_snapshot(duplicate)
    except ValueError as error:
        rejected = "duplicate row keys" in str(error)
    else:
        rejected = False
    check(rejected, "snapshot validation rejects duplicate sheet rows")

    print("NIVGEN full-sheet report: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
