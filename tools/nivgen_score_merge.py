#!/usr/bin/env python3
"""Merge ordered, non-overlapping NIVGEN score shards."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import nivgen_score_compare as score_compare


def merge(scores: list[dict[str, object]]) -> dict[str, object]:
    reports = []
    seen = set()
    exact = 0
    graded = 0
    for shard_index, score in enumerate(scores):
        shard_reports = score.get("reports")
        if not isinstance(shard_reports, list):
            raise ValueError(f"score shard {shard_index} has no reports array")
        shard_exact = 0
        shard_graded = 0
        for report in shard_reports:
            if not isinstance(report, dict):
                raise ValueError(f"score shard {shard_index} contains a non-object report")
            key = report.get("key")
            if not isinstance(key, str) or not key:
                raise ValueError(f"score shard {shard_index} contains an invalid key")
            if key in seen:
                raise ValueError(f"score shards contain duplicate key {key}")
            seen.add(key)
            comparisons = score_compare.validated_comparisons(
                report, f"shard {shard_index}")
            shard_graded += len(comparisons)
            shard_exact += sum(item["match"] for item in comparisons.values())
            reports.append(report)
        if int(score.get("graded", shard_graded)) != shard_graded:
            raise ValueError(f"score shard {shard_index} has an invalid graded total")
        if int(score.get("exact", shard_exact)) != shard_exact:
            raise ValueError(f"score shard {shard_index} has an invalid exact total")
        exact += shard_exact
        graded += shard_graded
    return {"reports": reports, "exact": exact, "graded": graded}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scores", nargs="+", type=Path)
    parser.add_argument("--json-out", required=True, type=Path)
    args = parser.parse_args()
    try:
        shards = [json.loads(path.read_text(encoding="utf-8-sig"))
                  for path in args.scores]
        if any(not isinstance(shard, dict) for shard in shards):
            raise ValueError("every score shard must be a JSON object")
        result = merge(shards)
        args.json_out.write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        print(f"nivgen_score_merge: {error}", file=sys.stderr)
        return 2
    print(f"merged {len(args.scores)} shards: exact={result['exact']}/"
          f"{result['graded']} rows={len(result['reports'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
